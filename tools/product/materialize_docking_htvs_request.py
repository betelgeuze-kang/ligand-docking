"""Materialize HTVS queue/config artifacts from a docking simulate request.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from betelgeuze_product.job_orchestration import read_job_record

ROOT = Path(__file__).resolve().parents[2]


def _jobs_dir() -> Path:
    from api.config import settings

    return Path(settings.results_storage_path) / "product_docking_jobs"


def _estimate_ligand_mw(smiles: str) -> float:
    text = str(smiles or "").strip()
    if not text:
        return 200.0
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors

        mol = Chem.MolFromSmiles(text)
        if mol is None:
            return 200.0
        return float(Descriptors.MolWt(mol))
    except Exception:
        return 200.0


def _resolve_native_pdb_path(target: str) -> str:
    target_text = str(target or "").strip()
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
            row_target = str(row.get("target") or "").strip().upper()
            if row_target in aliases:
                native = str(row.get("native_pdb_path") or "").strip()
                if native:
                    return native
    return ""


def _ligand_row_from_intake(ligand: dict[str, Any], *, target: str, replica_idx: int) -> dict[str, Any]:
    ligand_id = str(ligand.get("compound_id") or ligand.get("ligand_id") or ligand.get("id") or f"ligand_{replica_idx}")
    smiles = str(ligand.get("smiles") or ligand.get("inchi") or ligand.get("ligand_smiles") or "")
    slug = "".join(ch if ch.isalnum() else "_" for ch in ligand_id.lower())[:40] or f"ligand_{replica_idx:04d}"
    queue_id = f"{target.lower()}__rep{replica_idx:04d}__{slug}"
    native_pdb_path = str(ligand.get("native_pdb_path") or _resolve_native_pdb_path(target) or "")
    return {
        "queue_id": queue_id,
        "target": str(target),
        "family": "",
        "target_family": "",
        "replica_idx": int(replica_idx),
        "ligand_id": ligand_id,
        "ligand_smiles": smiles,
        "ligand_mw": _estimate_ligand_mw(smiles),
        "ligand_bead0_x": -0.8,
        "ligand_bead0_y": 0.0,
        "ligand_bead0_z": 0.0,
        "ligand_bead1_x": 0.8,
        "ligand_bead1_y": 0.0,
        "ligand_bead1_z": 0.0,
        "ligand_model_hint": "2bead",
        "native_pdb_path": native_pdb_path,
    }


def materialize_from_docking_request(
    request_json_path: str,
    *,
    out_dir: str,
) -> dict[str, Any]:
    payload = json.loads(Path(request_json_path).read_text(encoding="utf-8"))
    params = payload.get("runner_profile_params", {})
    if not isinstance(params, dict):
        params = {}
    docking_job_id = str(params.get("docking_job_id", payload.get("job_id", "")) or "")
    target = str(payload.get("target_name") or params.get("target_id") or "target")
    family = str(params.get("family", "") or "")
    ligands: list[dict[str, Any]] = []
    if docking_job_id:
        ledger = read_job_record(_jobs_dir(), docking_job_id)
        materialization_ligands = ledger.get("materialization_ligands")
        if isinstance(materialization_ligands, list) and materialization_ligands:
            ligands = list(materialization_ligands)
            intake = ledger.get("intake_payload", {})
            if isinstance(intake, dict):
                family = str(intake.get("family", family) or family)
                target = str(intake.get("target_id", target) or target)
        else:
            intake = ledger.get("intake_payload", {})
            if isinstance(intake, dict):
                family = str(intake.get("family", family) or family)
                target = str(intake.get("target_id", target) or target)
                ligands = list(intake.get("ligands", []) or [])
    if not ligands:
        ligands = list(params.get("ligands", []) or [])
    rows = [_ligand_row_from_intake(lig, target=target, replica_idx=i) for i, lig in enumerate(ligands)]
    if not rows:
        rows = [_ligand_row_from_intake({}, target=target, replica_idx=0)]
    for row in rows:
        row["family"] = family
        row["target_family"] = family
    os.makedirs(out_dir, exist_ok=True)
    queue_csv = os.path.join(out_dir, "docking_queue.csv")
    pd.DataFrame(rows).to_csv(queue_csv, index=False)
    materialized = {
        "queue_csv": queue_csv,
        "target": target,
        "family": family,
        "ligand_count": int(len(rows)),
        "docking_job_id": docking_job_id,
        "request_json_path": str(request_json_path),
    }
    meta_path = os.path.join(out_dir, "docking_htvs_materialized.json")
    Path(meta_path).write_text(json.dumps(materialized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    materialized["materialized_json"] = meta_path
    return materialized
