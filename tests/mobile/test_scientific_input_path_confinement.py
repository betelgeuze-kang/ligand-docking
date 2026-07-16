from __future__ import annotations

import hashlib
import json
from pathlib import Path

from betelgeuze_product.scientific_input_provenance import build_scientific_input_provenance


def _request_sha(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_relative_structure_path_cannot_escape_receipt_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.pdb"
    outside.write_text(
        "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 10.00           C\n",
        encoding="utf-8",
    )
    payload = {
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_path": "../outside.pdb",
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
        "pocket_residue_indices": [0],
    }
    manifest = {
        "job_id": "job-relative-escape",
        "runner_profile_id": "ligand_htvs_pipeline_default",
        "execution_mode": "smoke",
    }

    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=manifest,
        root=root,
    )

    assert receipt["structure"]["content_bytes_verified"] is False
    assert receipt["structure"]["source_sha256"] == ""
    assert receipt["execution_input_ready"] is False
    assert "scientific_input_file_unavailable_or_unsafe" in receipt["blockers"]
    serialized = json.dumps(receipt, sort_keys=True)
    assert str(outside) not in serialized
    assert outside.read_text(encoding="utf-8").strip() not in serialized
