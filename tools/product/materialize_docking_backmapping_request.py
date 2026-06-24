"""Materialize backmapping queue artifacts from a docking simulate request.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from betelgeuze_product.atomic_io import atomic_write_json
from tools.product.materialize_docking_htvs_request import (
    MATERIALIZATION_CONTRACT_VERSION,
    _ligand_row_from_intake,
    _materialize_structure_source,
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

    queue_csv = os.path.join(out_dir, "backmapping_queue.csv")
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
    }
    meta_path = os.path.join(out_dir, "docking_backmapping_materialized.json")
    atomic_write_json(meta_path, materialized, mode=0o600)
    materialized["materialized_json"] = meta_path
    return materialized
