from __future__ import annotations

import json
from pathlib import Path

from tools import build_glut1_second_wave_seed_row_fill_draft as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_glut1_second_wave_seed_row_fill_draft_reads_current_artifacts() -> None:
    seed_packet = json.loads((ROOT / "runs/glut1_second_wave_seed_row_packet_current.json").read_text(encoding="utf-8"))
    workbook = json.loads((ROOT / "runs/glut1_packet_replacement_workbook_current.json").read_text(encoding="utf-8"))
    manual_apply = json.loads((ROOT / "runs/glut1_manual_verdict_apply_draft_current.json").read_text(encoding="utf-8"))

    rows = mod.build_rows(seed_packet, workbook, manual_apply, "core_binder_01")
    summary = mod.build_summary(seed_packet, rows, "core_binder_01")

    assert summary["target_id"] == "GLUT1"
    assert summary["wave"] == "second"
    assert summary["safe_prefill_field_count"] == 1
    assert summary["blocked_field_count"] == 4
    assert summary["authoritative_apply_allowed"] is False
    assert rows[2]["field_name"] == "replacement_source"
    assert rows[2]["reviewer_safe_now"] == "yes"
