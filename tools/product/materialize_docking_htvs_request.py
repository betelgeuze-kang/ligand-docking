"""Materialize HTVS queue/config artifacts from a docking simulate request.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from betelgeuze_product.docking_materialization_errors import DockingMaterializationError
from betelgeuze_product.job_orchestration import read_job_record
from betelgeuze_product.scientific_input_materialization import (
    recheck_scientific_input_for_materialization,
)

ROOT = Path(__file__).resolve().parents[2]
MATERIALIZATION_CONTRACT_VERSION = "docking_materialization_v2"
SYNTHETIC_SMOKE_SMILES = "CCO"
_RAW_SMILES_FIELDS = ("smiles", "ligand_smiles")
_PATH_SOURCE_FIELDS = ("sdf_path", "mol2_path", "pdbqt_path")


def _jobs_dir() -> Path:
    from api.config import settings

    return Path(settings.results_storage_path) / "product_docking_jobs"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _estimate_ligand_mw(smiles: str) -> float:
    text = _text(smiles)
    if not text:
        raise DockingMaterializationError("ligand_smiles_missing_after_source_resolution")
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors

        mol = Chem.MolFromSmiles(text)
        if mol is None:
            raise DockingMaterializationError("invalid_ligand_smiles")
        return float(Descriptors.MolWt(mol))
    except DockingMaterializationError:
        raise
    except ImportError:
        # RDKit is part of the product image, but queue materialization should
        # remain usable in lightweight contract tests.
        return 200.0


def _resolve_ligand_smiles(ligand: dict[str, Any]) -> tuple[str, str]:
    for key in _RAW_SMILES_FIELDS:
        value = _text(ligand.get(key))
        if value:
            return value, key

    inchi = _text(ligand.get("inchi"))
    if inchi:
        try:
            from rdkit import Chem
        except ImportError as exc:
            raise DockingMaterializationError("inchi_conversion_requires_rdkit") from exc
        mol = Chem.MolFromInchi(inchi)
        if mol is None:
            raise DockingMaterializationError("invalid_ligand_inchi")
        return str(Chem.MolToSmiles(mol, canonical=True)), "inchi"

    unsupported_kind = next((key for key in _PATH_SOURCE_FIELDS if _text(ligand.get(key))), "")
    if unsupported_kind:
        raise DockingMaterializationError(
            "unsupported_ligand_source_for_htvs_materialization", unsupported_kind
        )
    if ligand.get("source_redacted") is True or _text(ligand.get("source_value_sha256")):
        raise DockingMaterializationError("redacted_ligand_source_cannot_be_materialized")
    raise DockingMaterializationError("ligand_source_unavailable_for_materialization")


def _has_materializable_source(ligand: Any) -> bool:
    if not isinstance(ligand, dict):
        return False
    return bool(
        any(_text(ligand.get(key)) for key in _RAW_SMILES_FIELDS)
        or _text(ligand.get("inchi"))
    )


def _first_unsupported_path_source_kind(candidate_lists: list[list[dict[str, Any]]]) -> str:
    for rows in candidate_lists:
        for ligand in rows:
            for key in _PATH_SOURCE_FIELDS:
                if _text(ligand.get(key)):
                    return key
    return ""


def _estimate_expected_ligand_count(
    *,
    params: dict[str, Any],
    ledger: dict[str, Any],
    candidate_count: int,
) -> int:
    for value in (
        params.get("ligand_count"),
        ledger.get("ligand_count"),
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


def _resolve_materialization_inputs(
    payload: dict[str, Any],
    params: dict[str, Any],
    *,
    docking_job_id: str,
    target: str,
    family: str,
) -> tuple[list[dict[str, Any]], str, str, int, bool]:
    ledger: dict[str, Any] = {}
    candidate_lists: list[list[dict[str, Any]]] = []
    if docking_job_id:
        ledger = read_job_record(_jobs_dir(), docking_job_id)
        intake = ledger.get("intake_payload", {})
        if isinstance(intake, dict):
            family = _text(intake.get("family")) or family
            target = _text(intake.get("target_id")) or target
        materialization_ligands = ledger.get("materialization_ligands")
        if isinstance(materialization_ligands, list) and materialization_ligands:
            candidate_lists.append([row for row in materialization_ligands if isinstance(row, dict)])
        if isinstance(intake, dict):
            intake_ligands = intake.get("ligands")
            if isinstance(intake_ligands, list) and intake_ligands:
                candidate_lists.append([row for row in intake_ligands if isinstance(row, dict)])

    param_ligands = params.get("ligands")
    if isinstance(param_ligands, list) and param_ligands:
        candidate_lists.append([row for row in param_ligands if isinstance(row, dict)])

    recovered_request, provenance_recheck = recheck_scientific_input_for_materialization(
        params=params,
        ledger=ledger,
        docking_job_id=docking_job_id,
        root=ROOT,
    )
    params["_scientific_input_provenance_recheck"] = provenance_recheck
    if isinstance(recovered_request, dict):
        recovered_ligands = recovered_request.get("ligands")
        if isinstance(recovered_ligands, list) and recovered_ligands:
            rows = [row for row in recovered_ligands if isinstance(row, dict)]
            if rows:
                candidate_lists.insert(0, rows)

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
            unsupported_kind = _first_unsupported_path_source_kind(candidate_lists)
            if unsupported_kind:
                raise DockingMaterializationError(
                    "unsupported_ligand_source_for_htvs_materialization",
                    unsupported_kind,
                )
            raise DockingMaterializationError("ligand_source_unavailable_for_materialization")
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
            "materialized_ligand_count_mismatch",
            f"expected={expected_count}:observed={len(ligands)}",
        )
    return ligands, target, family, expected_count, synthetic_used


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
            row_target = _text(row.get("target")).upper()
            if row_target in aliases:
                native = _text(row.get("native_pdb_path"))
                if native:
                    return native
    return ""


def _ligand_row_from_intake(ligand: dict[str, Any], *, target: str, replica_idx: int) -> dict[str, Any]:
    ligand_id = _text(
        ligand.get("compound_id")
        or ligand.get("ligand_id")
        or ligand.get("id")
        or f"ligand_{replica_idx}"
    )
    smiles, source_kind = _resolve_ligand_smiles(ligand)
    slug = "".join(ch if ch.isalnum() else "_" for ch in ligand_id.lower())[:40] or f"ligand_{replica_idx:04d}"
    queue_id = f"{target.lower()}__rep{replica_idx:04d}__{slug}"
    native_pdb_path = _text(ligand.get("native_pdb_path") or _resolve_native_pdb_path(target))
    return {
        "queue_id": queue_id,
        "target": str(target),
        "family": "",
        "target_family": "",
        "replica_idx": int(replica_idx),
        "ligand_id": ligand_id,
        "ligand_smiles": smiles,
        "ligand_mw": _estimate_ligand_mw(smiles),
        "materialization_source_kind": source_kind,
        "synthetic_smoke_input": ligand.get("_synthetic_smoke_input") is True,
        "ligand_bead0_x": -0.8,
        "ligand_bead0_y": 0.0,
        "ligand_bead0_z": 0.0,
        "ligand_bead1_x": 0.8,
        "ligand_bead1_y": 0.0,
        "ligand_bead1_z": 0.0,
        "ligand_model_hint": "2bead",
        "native_pdb_path": native_pdb_path,
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
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            if len(line) < 54:
                continue
            try:
                coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
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
    ligands, target, family, expected_count, synthetic_used = _resolve_materialization_inputs(
        payload,
        params,
        docking_job_id=docking_job_id,
        target=target,
        family=family,
    )
    rows = [
        _ligand_row_from_intake(ligand, target=target, replica_idx=index)
        for index, ligand in enumerate(ligands)
    ]
    for row in rows:
        row["family"] = family
        row["target_family"] = family
    pocket_meta = _pocket_metadata_from_native_pdb(_text(rows[0].get("native_pdb_path")))
    for row in rows:
        row.update(pocket_meta)
    os.makedirs(out_dir, exist_ok=True)
    queue_csv = os.path.join(out_dir, "docking_queue.csv")
    pd.DataFrame(rows).to_csv(queue_csv, index=False)
    materialized = {
        "materialization_contract_version": MATERIALIZATION_CONTRACT_VERSION,
        "input_materialization_ready": True,
        "queue_csv": queue_csv,
        "target": target,
        "family": family,
        "ligand_count": int(len(rows)),
        "expected_ligand_count": int(expected_count),
        "materialization_source_count": int(len(rows)),
        "materialization_source_kinds": sorted(
            {str(row.get("materialization_source_kind") or "") for row in rows}
        ),
        "synthetic_input_used": synthetic_used,
        "docking_job_id": docking_job_id,
        "request_json_path": str(request_json_path),
        "pocket_metadata": pocket_meta,
        "scientific_input_provenance_recheck": dict(
            params.get("_scientific_input_provenance_recheck") or {}
        ),
    }
    meta_path = os.path.join(out_dir, "docking_htvs_materialized.json")
    Path(meta_path).write_text(
        json.dumps(materialized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    materialized["materialized_json"] = meta_path
    return materialized
