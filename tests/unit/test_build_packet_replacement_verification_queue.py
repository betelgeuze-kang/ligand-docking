from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_packet_replacement_verification_queue_ca2(tmp_path: Path) -> None:
    draft = tmp_path / "runs" / "ca2_packet_replacement_draft_current.csv"
    draft.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "packet",
        "packet_step",
        "target",
        "replacement_ligand_id",
        "draft_replacement_ligand_id",
        "replacement_is_binder",
        "replacement_source",
        "draft_replacement_source",
        "draft_candidate_reference_hint",
        "draft_candidate_anchor_pdb_id",
        "draft_missing_claim_fields",
        "draft_verification_status",
        "draft_apply_block_reason",
    ]
    with draft.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "packet": "ood",
                    "packet_step": "ood_non_binder_01",
                    "target": "CA2",
                    "replacement_ligand_id": "",
                    "draft_replacement_ligand_id": "aspirin",
                    "replacement_is_binder": "0",
                    "replacement_source": "",
                    "draft_replacement_source": "draft_seed::generic_negative_seed",
                    "draft_candidate_reference_hint": "hint",
                    "draft_candidate_anchor_pdb_id": "1CA2",
                    "draft_missing_claim_fields": "binding,smiles",
                    "draft_verification_status": "pending",
                    "draft_apply_block_reason": "missing_claim_fields",
                },
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "target": "CA2",
                    "replacement_ligand_id": "",
                    "draft_replacement_ligand_id": "acetazolamide",
                    "replacement_is_binder": "1",
                    "replacement_source": "",
                    "draft_replacement_source": "draft_seed::known_ca2_inhibitor_seed",
                    "draft_candidate_reference_hint": "hint",
                    "draft_candidate_anchor_pdb_id": "1CA2",
                    "draft_missing_claim_fields": "binding,smiles",
                    "draft_verification_status": "pending",
                    "draft_apply_block_reason": "missing_claim_fields",
                },
            ]
        )
    out_json = tmp_path / "runs" / "queue.json"
    out_csv = tmp_path / "runs" / "queue.csv"
    out_md = tmp_path / "runs" / "queue.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_packet_replacement_verification_queue.py"),
            "--family",
            "ca2",
            "--draft-csv",
            str(draft),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["binder_row_count"] == 1
    assert payload["queue_rows"][0]["packet_step"] == "core_binder_01"
