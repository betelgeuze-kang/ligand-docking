"""Materialize HTVS queue/config artifacts from a docking simulate request.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from betelgeuze_product.atomic_io import atomic_write_json, atomic_write_text
from betelgeuze_product.job_orchestration import read_job_record
from betelgeuze_product.private_payload_store import PrivatePayloadStore

ROOT = Path(__file__).resolve().parents[2]
MATERIALIZATION_CONTRACT_VERSION = "docking_materialization_v3"
SYNTHETIC_SMOKE_SMILES = "CCO"
SYNTHETIC_SMOKE_MW = 46.069
_RAW_SMILES_FIELDS = ("smiles", "ligand_smiles")
_PATH_SOURCE_FIELDS = ("sdf_path", "mol2_path", "pdbqt_path")


class DockingMaterializationError(ValueError):
    """Raised when the runner cannot prove which customer input it materialized."""


def _settings() -> Any:
    from api.config import settings

    return settings


def _jobs_dir() -> Path:
    return Path(_settings().results_storage_path) / "product_docking_jobs"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rdkit() -> tuple[Any, Any]:
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
    except ImportError as exc:
        raise DockingMaterializationError("ligand_materialization_requires_rdkit") from exc
    return Chem, Descriptors


def _estimate_ligand_mw(smiles: str, *, synthetic_smoke: bool = False) -> float:
    text = _text(smiles)
    if not text:
        raise DockingMaterializationError("ligand_smiles_missing_after_source_resolution")
    if synthetic_smoke:
        if text != SYNTHETIC_SMOKE_SMILES:
            raise DockingMaterializationError("synthetic_smoke_ligand_contract_mismatch")
        # The lightweight contract CI intentionally does not install RDKit.
        # This constant is scoped exclusively to the fixed, visibly-labelled
        # internal CCO smoke ligand and is never used for customer inputs.
        return SYNTHETIC_SMOKE_MW
    Chem, Descriptors = _rdkit()
    mol = Chem.MolFromSmiles(text)
    if mol is None:
        raise DockingMaterializationError("invalid_ligand_smiles")
    return float(Descriptors.MolWt(mol))


def _canonical_smiles_from_path(path_value: str, source_kind: str) -> str:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise DockingMaterializationError(f"ligand_source_file_missing:{source_kind}")
    Chem, _ = _rdkit()
    mol = None
    if source_kind == "sdf_path":
        supplier = Chem.SDMolSupplier(str(path), removeHs=False)
        mol = next((item for item in supplier if item is not None), None)
    elif source_kind == "mol2_path":
        mol = Chem.MolFromMol2File(str(path), removeHs=False)
    elif source_kind == "pdbqt_path":
        raise DockingMaterializationError(
            "unsupported_ligand_source_for_htvs_materialization:pdbqt_path"
        )
    if mol is None:
        raise DockingMaterializationError(f"invalid_ligand_source_file:{source_kind}")
    return str(Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True))


def _resolve_ligand_smiles(ligand: dict[str, Any]) -> tuple[str, str]:
    if ligand.get("_synthetic_smoke_input") is True:
        value = _text(ligand.get("smiles"))
        if value != SYNTHETIC_SMOKE_SMILES:
            raise DockingMaterializationError("synthetic_smoke_ligand_contract_mismatch")
        return SYNTHETIC_SMOKE_SMILES, "synthetic_smoke"

    for key in _RAW_SMILES_FIELDS:
        value = _text(ligand.get(key))
        if value:
            Chem, _ = _rdkit()
            mol = Chem.MolFromSmiles(value)
            if mol is None:
                raise DockingMaterializationError("invalid_ligand_smiles")
            return str(Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)), key

    inchi = _text(ligand.get("inchi"))
    if inchi:
        Chem, _ = _rdkit()
        mol = Chem.MolFromInchi(inchi)
        if mol is None:
            raise DockingMaterializationError("invalid_ligand_inchi")
        return str(Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)), "inchi"

    for source_kind in _PATH_SOURCE_FIELDS:
        path_value = _text(ligand.get(source_kind))
        if path_value:
            return _canonical_smiles_from_path(path_value, source_kind), source_kind

    if ligand.get("source_redacted") is True or _text(ligand.get("source_value_sha256")):
        raise DockingMaterializationError("redacted_ligand_source_cannot_be_materialized")
    if _text(ligand.get("compound_id")):
        raise DockingMaterializationError("compound_id_is_not_a_molecular_source")
    raise DockingMaterializationError("ligand_source_unavailable_for_materialization")


def _has_materializable_source(ligand: Any) -> bool:
    if not isinstance(ligand, dict):
        return False
    return bool(
        ligand.get("_synthetic_smoke_input") is True
        or any(_text(ligand.get(key)) for key in _RAW_SMILES_FIELDS)
        or _text(ligand.get("inchi"))
        or any(_text(ligand.get(key)) for key in _PATH_SOURCE_FIELDS)
    )


def _load_private_request(
    params: dict[str, Any],
    *,
    docking_job_id: str,
) -> dict[str, Any]:
    reference = _text(params.get("private_payload_ref"))
    if not reference:
        return {}
    expected_sha = _text(params.get("private_payload_request_sha256"))
    try:
        return PrivatePayloadStore.from_settings(_settings()).get(
            reference,
            expected_job_id=docking_job_id,
            expected_request_sha256=expected_sha,
        )
    except Exception as exc:
        raise DockingMaterializationError(
            f"private_payload_resolution_failed:{exc}"
        ) from exc


def _estimate_expected_ligand_count(
    *,
    params: dict[str, Any],
    ledger: dict[str, Any],
    private_request: dict[str, Any],
    candidate_count: int,
) -> int:
    for value in (
        params.get("ligand_count"),
        ledger.get("ligand_count"),
        private_request.get("ligand_count"),
        len(private_request.get("ligands") or []) if private_request else None,
        (ledger.get("intake_payload") or {}).get("ligand_count")
        if isinstance(ledger.get("intake_payload"), dict)
        else None,
    ):
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return int(candidate_count)


def _raise_specific_materialization_error(candidate_lists: list[list[dict[str, Any]]]) -> None:
    for rows in candidate_lists:
        for row in rows:
            if isinstance(row, dict):
                _resolve_ligand_smiles(row)
    raise DockingMaterializationError("ligand_source_unavailable_for_materialization")


def _resolve_materialization_inputs(
    payload: dict[str, Any],
    params: dict[str, Any],
    *,
    docking_job_id: str,
    target: str,
    family: str,
) -> tuple[list[dict[str, Any]], str, str, int, bool, dict[str, Any]]:
    ledger: dict[str, Any] = {}
    private_request = _load_private_request(params, docking_job_id=docking_job_id)
    candidate_lists: list[list[dict[str, Any]]] = []

    if private_request:
        target = _text(
            private_request.get("target_id") or private_request.get("target_name")
        ) or target
        family = _text(private_request.get("family")) or family
        private_ligands = private_request.get("ligands")
        if isinstance(private_ligands, list) and private_ligands:
            candidate_lists.append(
                [row for row in private_ligands if isinstance(row, dict)]
            )

    if docking_job_id:
        ledger = read_job_record(_jobs_dir(), docking_job_id)
        intake = ledger.get("intake_payload", {})
        if isinstance(intake, dict):
            family = _text(intake.get("family")) or family
            target = _text(intake.get("target_id")) or target
        materialization_ligands = ledger.get("materialization_ligands")
        if isinstance(materialization_ligands, list) and materialization_ligands:
            candidate_lists.append(
                [row for row in materialization_ligands if isinstance(row, dict)]
            )
        if isinstance(intake, dict):
            intake_ligands = intake.get("ligands")
            if isinstance(intake_ligands, list) and intake_ligands:
                candidate_lists.append(
                    [row for row in intake_ligands if isinstance(row, dict)]
                )

    param_ligands = params.get("ligands")
    if isinstance(param_ligands, list) and param_ligands:
        candidate_lists.append([row for row in param_ligands if isinstance(row, dict)])

    ligands = next(
        (
            rows
            for rows in candidate_lists
            if rows and all(_has_materializable_source(row) for row in rows)
        ),
        [],
    )
    expected_count = _estimate_expected_ligand_count(
        params=params,
        ledger=ledger,
        private_request=private_request,
        candidate_count=len(ligands),
    )
    allow_synthetic = bool(
        params.get("allow_synthetic_ligand_input") is True
        and _text(params.get("runner_execution_mode")) == "smoke"
        and params.get("runner_synthetic_input_allowed") is True
    )
    synthetic_used = False
    if not ligands:
        if not allow_synthetic:
            _raise_specific_materialization_error(candidate_lists)
        if expected_count not in {0, 1}:
            raise DockingMaterializationError(
                "synthetic_smoke_materialization_requires_exactly_one_ligand"
            )
        ligands = [
            {
                "ligand_id": "synthetic_smoke_ligand_1",
                "smiles": SYNTHETIC_SMOKE_SMILES,
                "_synthetic_smoke_input": True,
            }
        ]
        expected_count = 1
        synthetic_used = True

    if expected_count <= 0:
        raise DockingMaterializationError("expected_ligand_count_missing")
    if len(ligands) != expected_count:
        raise DockingMaterializationError(
            f"materialized_ligand_count_mismatch:expected={expected_count}:observed={len(ligands)}"
        )
    return ligands, target, family, expected_count, synthetic_used, private_request


def _resolve_native_pdb_path(target: str) -> str:
    target_text = _text(target)
    if not target_text:
        return ""
    csv_path = ROOT / "config/real_drug_targets_blind_gpcr_adrb2_v1.csv"
    if not csv_path.exists():
        return ""
    import csv

    aliases = {target_text.upper(), target_text.upper().replace("-", "_")}
    if target_text.upper() in {"ADRB2", "ADRB2_GPCR", "ADRB2_GPCR_BLIND"}:
        aliases.add("ADRB2_GPCR_BLIND")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if _text(row.get("target")).upper() in aliases:
                native = _text(row.get("native_pdb_path"))
                if native:
                    return native
    return ""


def _materialize_structure_source(
    request_payload: dict[str, Any],
    *,
    out_dir: str,
    target: str,
) -> tuple[str, str]:
    pdb_content = _text(request_payload.get("pdb_content"))
    if pdb_content:
        if not any(line.startswith(("ATOM  ", "HETATM")) for line in pdb_content.splitlines()):
            raise DockingMaterializationError("private_pdb_content_has_no_coordinates")
        path = Path(out_dir) / "private_input_structure.pdb"
        atomic_write_text(path, pdb_content.rstrip() + "\n", mode=0o600)
        return str(path), "private_pdb_content"

    pdb_path_value = _text(request_payload.get("pdb_path"))
    if pdb_path_value:
        path = Path(pdb_path_value).expanduser()
        if not path.is_file():
            raise DockingMaterializationError("private_pdb_path_missing")
        return str(path.resolve()), "private_pdb_path"

    if _text(request_payload.get("mmcif_content")) or _text(
        request_payload.get("mmcif_path")
    ):
        raise DockingMaterializationError(
            "unsupported_structure_source_for_htvs_materialization:mmcif"
        )

    resolved = _resolve_native_pdb_path(
        _text(request_payload.get("pdb_id")) or target
    )
    if resolved:
        return resolved, "validated_target_native_registry"
    raise DockingMaterializationError("native_pdb_path_unavailable")


def _ligand_row_from_intake(
    ligand: dict[str, Any],
    *,
    target: str,
    replica_idx: int,
    native_pdb_path: str = "",
) -> dict[str, Any]:
    ligand_id = _text(
        ligand.get("compound_id")
        or ligand.get("ligand_id")
        or ligand.get("id")
        or f"ligand_{replica_idx}"
    )
    synthetic_smoke = ligand.get("_synthetic_smoke_input") is True
    smiles, source_kind = _resolve_ligand_smiles(ligand)
    slug = "".join(ch if ch.isalnum() else "_" for ch in ligand_id.lower())[:40]
    slug = slug or f"ligand_{replica_idx:04d}"
    queue_id = f"{target.lower()}__rep{replica_idx:04d}__{slug}"
    resolved_native = _text(
        native_pdb_path
        or ligand.get("native_pdb_path")
        or _resolve_native_pdb_path(target)
    )
    return {
        "queue_id": queue_id,
        "target": str(target),
        "family": "",
        "target_family": "",
        "replica_idx": int(replica_idx),
        "ligand_id": ligand_id,
        "ligand_smiles": smiles,
        "ligand_mw": _estimate_ligand_mw(
            smiles,
            synthetic_smoke=synthetic_smoke,
        ),
        "materialization_source_kind": source_kind,
        "synthetic_smoke_input": synthetic_smoke,
        "ligand_bead0_x": -0.8,
        "ligand_bead0_y": 0.0,
        "ligand_bead0_z": 0.0,
        "ligand_bead1_x": 0.8,
        "ligand_bead1_y": 0.0,
        "ligand_bead1_z": 0.0,
        "ligand_model_hint": "2bead",
        "native_pdb_path": resolved_native,
    }


def _pocket_metadata_from_native_pdb(native_pdb_path: str) -> dict[str, Any]:
    path = Path(native_pdb_path)
    if not path.is_file():
        return {"pocket_status": "native_pdb_missing"}
    try:
        import numpy as np

        from core.pocket_detection import detect_pocket_geometric

        coords: list[list[float]] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 54:
                continue
            try:
                coords.append(
                    [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                )
            except ValueError:
                continue
        if not coords:
            return {"pocket_status": "native_pdb_no_coords"}
        pocket = detect_pocket_geometric(np.asarray(coords, dtype=np.float64))
        center = pocket.get("pocket_center") or [0.0, 0.0, 0.0]
        return {
            "pocket_status": pocket.get("status"),
            "pocket_center_x": float(center[0]),
            "pocket_center_y": float(center[1]),
            "pocket_center_z": float(center[2]),
            "pocket_radius_a": float(pocket.get("pocket_radius_a") or 0.0),
            "pocket_method": pocket.get("method", "geometric"),
        }
    except Exception as exc:
        return {"pocket_status": "pocket_detection_failed", "pocket_error": str(exc)}


def materialize_from_docking_request(
    request_json_path: str,
    *,
    out_dir: str,
) -> dict[str, Any]:
    payload = json.loads(Path(request_json_path).read_text(encoding="utf-8"))
    params = payload.get("runner_profile_params", {})
    if not isinstance(params, dict):
        params = {}
    docking_job_id = _text(params.get("docking_job_id") or payload.get("job_id"))
    target = _text(payload.get("target_name") or params.get("target_id")) or "target"
    family = _text(params.get("family"))
    ligands, target, family, expected_count, synthetic_used, private_request = (
        _resolve_materialization_inputs(
            payload,
            params,
            docking_job_id=docking_job_id,
            target=target,
            family=family,
        )
    )

    os.makedirs(out_dir, exist_ok=True)
    structure_request = private_request if private_request else payload
    native_pdb_path, structure_source = _materialize_structure_source(
        structure_request,
        out_dir=out_dir,
        target=target,
    )
    rows = [
        _ligand_row_from_intake(
            ligand,
            target=target,
            replica_idx=index,
            native_pdb_path=native_pdb_path,
        )
        for index, ligand in enumerate(ligands)
    ]
    for row in rows:
        row["family"] = family
        row["target_family"] = family
    pocket_meta = _pocket_metadata_from_native_pdb(native_pdb_path)
    for row in rows:
        row.update(pocket_meta)

    queue_csv = os.path.join(out_dir, "docking_queue.csv")
    pd.DataFrame(rows).to_csv(queue_csv, index=False)
    materialized = {
        "materialization_contract_version": MATERIALIZATION_CONTRACT_VERSION,
        "input_materialization_ready": True,
        "private_payload_verified": bool(private_request),
        "private_payload_ref_present": bool(_text(params.get("private_payload_ref"))),
        "queue_csv": queue_csv,
        "target": target,
        "family": family,
        "ligand_count": int(len(rows)),
        "expected_ligand_count": int(expected_count),
        "materialization_source_count": int(len(rows)),
        "materialization_source_kinds": sorted(
            {str(row.get("materialization_source_kind") or "") for row in rows}
        ),
        "structure_source": structure_source,
        "native_pdb_path": native_pdb_path,
        "synthetic_input_used": synthetic_used,
        "docking_job_id": docking_job_id,
        "request_json_path": str(request_json_path),
        "pocket_metadata": pocket_meta,
    }
    meta_path = os.path.join(out_dir, "docking_htvs_materialized.json")
    atomic_write_json(meta_path, materialized, mode=0o600)
    materialized["materialized_json"] = meta_path
    return materialized
