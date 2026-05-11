from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_negative_evidence_closure_queue as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_transporter_negative_evidence_closure_queue_reads_current_artifacts() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_negative_reviewer_day_plan_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/transporter_placeholder_burndown_queue_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/transporter_negative_evidence_target_packets_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/glut1_negative_review_handoff_packet_current.json").read_text(encoding="utf-8")),
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["review_mode"] == "negative_evidence_closure_only"
    assert summary["row_count"] == 6
    assert summary["aqp1_negative_slot_count"] == 3
    assert summary["glut1_negative_slot_count"] == 3
    assert summary["placeholder_driven_rows_remaining"] == 6
    assert summary["staged_non_authoritative_rows"] == 6
    assert summary["top_queue_id"] == "AQP1__core_non_binder_01"
    assert summary["top_source_context_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert summary["top_source_context_role"] == "exact_source_confirmation_not_authoritative_negative"
    assert summary["aqp1_source_context_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert summary["aqp1_source_context_focus_ligand"] == "sodium nitroprusside"
    assert summary["aqp1_source_context_direct_negative_quantitative_row_found_count"] == 0
    assert summary["aqp1_source_context_authoritative_negative_apply_allowed_count"] == 0
    assert summary["glut1_negative_handoff_artifact"] == "runs/glut1_negative_review_handoff_packet_current.md"
    assert rows[0]["target_id"] == "AQP1"
    assert rows[0]["packet_step"] == "core_non_binder_01"
    assert rows[0]["source_context_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert rows[0]["source_context_support_artifact"] == "runs/aqp1_negative_exact_source_outcome_packet_current.md"
    assert rows[0]["negative_handoff_artifact"] == "runs/aqp1_negative_slot_resolution_packet_current.md"
    assert rows[0]["source_context_role"] == "exact_source_confirmation_not_authoritative_negative"
    assert rows[0]["source_context_direct_negative_quantitative_row_found_count"] == 0
    assert rows[0]["source_context_authoritative_negative_apply_allowed_count"] == 0
    assert rows[-1]["target_id"] == "GLUT1"
    assert rows[-1]["packet_step"] == "core_non_binder_03"
    assert rows[-1]["source_context_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert rows[-1]["negative_handoff_artifact"] == "runs/glut1_negative_review_handoff_packet_current.md"
    assert rows[-1]["source_context_role"] == "positive_or_binder_context_not_negative_evidence"


def test_build_transporter_negative_evidence_closure_queue_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "queue.json"
    out_csv = tmp_path / "queue.csv"
    out_md = tmp_path / "queue.md"
    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_negative_evidence_closure_queue.py",
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
    assert payload["summary"]["row_count"] == 6
    assert out_md.read_text(encoding="utf-8").startswith("# Transporter Negative Evidence Closure Queue")
