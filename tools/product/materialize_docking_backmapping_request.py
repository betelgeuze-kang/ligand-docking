"""Materialize backmapping queue artifacts from a docking simulate request.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from betelgeuze_product.job_orchestration import read_job_record
from tools.product.materialize_docking_htvs_request import _jobs_dir, _ligand_row_from_intake


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
    queue_csv = os.path.join(out_dir, "backmapping_queue.csv")
    pd.DataFrame(rows).to_csv(queue_csv, index=False)
    materialized = {
        "queue_csv": queue_csv,
        "target": target,
        "family": family,
        "ligand_count": int(len(rows)),
        "docking_job_id": docking_job_id,
        "request_json_path": str(request_json_path),
    }
    meta_path = os.path.join(out_dir, "docking_backmapping_materialized.json")
    Path(meta_path).write_text(json.dumps(materialized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    materialized["materialized_json"] = meta_path
    return materialized
