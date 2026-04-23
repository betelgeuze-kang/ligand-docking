from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_slot_closure_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_slot_closure_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_review_handoff_packet_current.json").read_text(encoding="utf-8")),
        {
            "summary": {
                "packet_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
                "row_count": 2,
                "primary_focus_ligand": "tetraethylammonium",
                "exact_target_pair_absent_count": 2,
            }
        },
        json.loads((ROOT / "runs/aqp1_manual_review_queue_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_next_verification_slice_current.json").read_text(encoding="utf-8")),
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 3
    assert summary["review_only_slot_count"] == 3
    assert summary["primary_focus_ligand"] == "aqp1_placeholder_nonbinder_01"
    assert summary["top_packet_step"] == "core_non_binder_01"
    assert summary["exclusion_exact_target_pair_absent_count"] == 2
    assert rows[0]["packet_step"] == "core_non_binder_01"
    assert rows[0]["review_bucket"] == "review_only_negative_evidence"
    assert rows[0]["exclusion_context_primary_focus_ligand"] == "tetraethylammonium"
    assert rows[0]["shared_blocker_signal_count"] == 3


def test_build_aqp1_negative_slot_closure_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_slot_closure.json"
    out_csv = tmp_path / "aqp1_negative_slot_closure.csv"
    out_md = tmp_path / "aqp1_negative_slot_closure.md"
    exclusion_json = tmp_path / "aqp1_negative_source_exclusion.json"
    exclusion_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
                    "row_count": 2,
                    "primary_focus_ligand": "tetraethylammonium",
                    "exact_target_pair_absent_count": 2,
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_slot_closure_packet.py",
            "--negative-source-exclusion-json",
            str(exclusion_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["top_packet_step"] == "core_non_binder_01"
    assert out_csv.exists()
    assert out_md.exists()
