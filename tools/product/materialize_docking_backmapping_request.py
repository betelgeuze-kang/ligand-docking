"""Materialize backmapping queue artifacts from a docking simulate request.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from tools.product.materialize_docking_htvs_request import (
    MATERIALIZATION_CONTRACT_VERSION,
    _ligand_row_from_intake,
    _materialize_target_structure,
    _recover_private_request,
    _resolve_materialization_inputs,
    _text,
)


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
    private_request = _recover_private_request(
        docking_job_id,
        _text(params.get("request_sha256")),
    )
    target_structure = _materialize_target_structure(private_request, out_dir=out_dir)
    if _text(params.get("runner_execution_mode")) == "restricted-production" and not target_structure:
        from betelgeuze_product.docking_materialization_errors import DockingMaterializationError

        raise DockingMaterializationError("target_structure_unavailable_for_materialization")
    rows = [
        _ligand_row_from_intake(
            ligand,
            target=target,
            replica_idx=index,
            target_structure_path=_text(target_structure.get("target_structure_path")),
        )
        for index, ligand in enumerate(ligands)
    ]
    for row in rows:
        row["family"] = family
        row["target_family"] = family
    os.makedirs(out_dir, exist_ok=True)
    queue_csv = os.path.join(out_dir, "backmapping_queue.csv")
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
        **target_structure,
    }
    meta_path = os.path.join(out_dir, "docking_backmapping_materialized.json")
    Path(meta_path).write_text(
        json.dumps(materialized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    materialized["materialized_json"] = meta_path
    return materialized
