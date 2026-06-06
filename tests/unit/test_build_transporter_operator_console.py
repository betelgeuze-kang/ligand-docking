from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from tools.product import build_transporter_operator_console as mod


ROOT = Path(__file__).resolve().parents[2]


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_operator_console_outputs_expected_open_order() -> None:
    follow_on_path = ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json"
    follow_on_path.write_text(
        json.dumps(
            {
                "summary": {
                    "row_count": 2,
                    "follow_on_targets": "core_binder_02, core_binder_03",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    blocker_path = ROOT / "runs/aqp1_follow_on_blocker_decomposition_current.json"
    blocker_path.write_text(
        json.dumps(
            {
                "summary": {
                    "blocker_row_count": 2,
                    "follow_on_targets": "core_binder_02, core_binder_03",
                    "primary_focus_ligand": "AqB013",
                    "exact_human_guardrail_ligand": "AqB013",
                    "exact_human_nonbinding_count": 1,
                    "exact_target_pair_absent_count": 1,
                    "next_required_step": "Keep core_binder_02 as the guardrail while core_binder_03 closes the target-pair gap.",
                    "blocker_decomposition_artifact": "runs/aqp1_follow_on_blocker_decomposition_current.md",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "tools/product/build_aqp1_manual_verdict_handoff_packet.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/product/build_glut1_manual_verdict_handoff_packet.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/build_aqp1_first_seed_row_packet.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/build_transporter_seed_row_execution_packet.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/build_aqp1_seed_row_fill_draft.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/build_aqp1_seed_row_sync_apply_preview.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/product/build_aqp1_quantitative_provenance_packet.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/product/build_aqp1_first_wave_source_confirmation_packet.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/build_glut1_second_wave_source_confirmation_packet.py"],
        cwd=ROOT,
        check=True,
    )
    rows = mod.build_target_rows(
        json.loads((ROOT / "runs/aqp1_manual_verdict_handoff_packet_current.json").read_text()),
        json.loads((ROOT / "runs/glut1_manual_verdict_handoff_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_first_seed_row_packet_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_seed_row_execution_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_seed_row_fill_draft_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_seed_row_sync_apply_preview_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_first_wave_source_confirmation_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_follow_on_blocker_decomposition_current.json").read_text()),
        json.loads((ROOT / "runs/glut1_second_wave_source_confirmation_packet_current.json").read_text()),
    )
    summary = mod.build_summary(
        json.loads((ROOT / "runs/transporter_reviewer_day_plan_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_apply_draft_status_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_manual_review_dashboard_current.json").read_text()),
        json.loads((ROOT / "runs/transporter_seed_row_execution_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_seed_row_sync_apply_preview_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_first_wave_follow_on_packet_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_follow_on_blocker_decomposition_current.json").read_text()),
        json.loads((ROOT / "runs/glut1_second_wave_source_confirmation_packet_current.json").read_text()),
        rows,
    )

    assert summary["target_count"] == 2
    assert summary["aqp1_open_first"] == "runs/aqp1_first_seed_row_packet_current.md"
    assert summary["aqp1_open_second"] == "runs/transporter_seed_row_execution_packet_current.md"
    assert summary["aqp1_open_source_confirmation"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert summary["aqp1_open_provenance"] == "runs/aqp1_quantitative_provenance_packet_current.md"
    assert summary["aqp1_open_follow_on"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert summary["glut1_open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert summary["aqp1_open_execution"] == "runs/transporter_seed_row_execution_packet_current.md"
    assert summary["aqp1_open_third"] == "runs/aqp1_seed_row_fill_draft_current.md"
    assert summary["glut1_open_first"] == "runs/glut1_manual_verdict_packet_current.md"
    assert summary["glut1_open_third"] == "runs/glut1_binder_confirmation_card_current.md"
    assert summary["aqp1_open_fourth"] == "runs/aqp1_seed_row_sync_apply_preview_current.md"
    assert summary["aqp1_open_fifth"] == "runs/aqp1_negative_review_handoff_packet_current.md"
    assert summary["glut1_open_fourth"] == "runs/glut1_manual_verdict_staging_sheet_current.md"
    assert summary["aqp1_execution_packet_ready"] is True
    assert summary["aqp1_seed_fill_ready"] is True
    assert summary["aqp1_seed_fill_safe_prefill_count"] == 4
    assert summary["aqp1_sync_preview_ready"] is True
    assert summary["aqp1_sync_preview_safe_staged_field_count"] == 4
    assert summary["aqp1_exact_human_activity_count"] == 1
    assert summary["aqp1_quantitative_provenance_primary_focus_ligand"] == "AqB013"
    assert summary["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert summary["glut1_second_wave_source_confirmation_ready"] is True
    assert summary["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert summary["glut1_second_wave_source_confirmation_row_count"] == 3
    assert summary["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_direct_quantitative_binding_count"] == 1
    assert summary["glut1_exact_target_pair_activity_count"] == 2
    assert summary["glut1_structured_pair_absent_count"] == 1
    assert summary["aqp1_follow_on_packet_ready"] is True
    assert summary["aqp1_follow_on_row_count"] == 2
    assert summary["aqp1_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_follow_on_blocker_decomposition_ready"] is True
    assert summary["aqp1_open_follow_on_blocker_decomposition"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert summary["aqp1_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert summary["aqp1_follow_on_blocker_decomposition_row_count"] == 2
    assert summary["aqp1_follow_on_blocker_decomposition_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_follow_on_blocker_decomposition_primary_focus_ligand"] == "AqB013"
    assert summary["aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand"] == "AqB013"
    assert summary["aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count"] == 1
    assert summary["aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count"] == 1
    _contains_tokens(
        summary["aqp1_follow_on_blocker_decomposition_next_required_step"],
        "core_binder_02",
        "guardrail",
        "core_binder_03",
        "target-pair",
    )
    assert summary["binder_pending_manual_verdict_count"] == 0

    row_map = {row["target"]: row for row in rows}
    assert row_map["aqp1"]["wave"] == "first"
    assert row_map["aqp1"]["open_first"] == "runs/aqp1_first_seed_row_packet_current.md"
    assert row_map["aqp1"]["open_second"] == "runs/transporter_seed_row_execution_packet_current.md"
    assert row_map["aqp1"]["open_source_confirmation"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert row_map["aqp1"]["open_provenance"] == "runs/aqp1_quantitative_provenance_packet_current.md"
    assert row_map["aqp1"]["open_follow_on"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert row_map["aqp1"]["open_third"] == "runs/aqp1_seed_row_fill_draft_current.md"
    assert row_map["aqp1"]["open_fourth"] == "runs/aqp1_seed_row_sync_apply_preview_current.md"
    assert row_map["aqp1"]["open_fifth"] == "runs/aqp1_negative_review_handoff_packet_current.md"
    assert row_map["aqp1"]["pending_manual_verdict_count"] == 0
    assert row_map["aqp1"]["exact_human_activity_count"] == 1
    assert row_map["aqp1"]["quantitative_provenance_primary_focus_ligand"] == "AqB013"
    assert row_map["aqp1"]["quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert "AqB013" in row_map["aqp1"]["operator_instruction"]
    assert "follow-on packet" in row_map["aqp1"]["operator_instruction"]
    assert "follow-on blocker decomposition" in row_map["aqp1"]["operator_instruction"].lower()
    assert row_map["glut1"]["wave"] == "second"
    assert row_map["glut1"]["open_first"] == "runs/glut1_manual_verdict_packet_current.md"
    assert row_map["glut1"]["open_second"] == "runs/glut1_negative_review_handoff_packet_current.md"
    assert row_map["glut1"]["open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert row_map["glut1"]["open_third"] == "runs/glut1_binder_confirmation_card_current.md"
    assert row_map["glut1"]["open_fourth"] == "runs/glut1_manual_verdict_staging_sheet_current.md"
    assert row_map["glut1"]["open_fifth"] == ""
    assert row_map["glut1"]["pending_manual_verdict_count"] == 0
    assert row_map["glut1"]["glut1_second_wave_source_confirmation_ready"] is True
    assert row_map["glut1"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert row_map["glut1"]["glut1_direct_quantitative_binding_count"] == 1
    assert row_map["glut1"]["glut1_exact_target_pair_activity_count"] == 2
    assert row_map["glut1"]["glut1_structured_pair_absent_count"] == 1
    _contains_tokens(
        row_map["glut1"]["operator_instruction"],
        "cytochalasin b",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
    )


@pytest.mark.xfail(
    reason="GLUT1 second-wave source-confirmation wiring is not yet exposed on the operator console row.",
    strict=True,
)
def test_build_transporter_operator_console_exposes_glut1_second_wave_source_confirmation_row() -> None:
    from tools.product import build_transporter_operator_console as mod

    rows = mod.build_target_rows(
        {"summary": {"binder_first_wave_count": 3, "pending_manual_verdict_count": 0}},
        {"summary": {"binder_slot_count": 3, "binder_pending_manual_verdict_count": 0}},
        {"summary": {"candidate_name": "bacopaside II"}},
        {"summary": {"safe_staged_field_count": 1}},
        {"summary": {"safe_prefill_field_count": 1}},
        {"summary": {"safe_staged_field_count": 1}},
        {"summary": {"exact_human_aqp1_activity_count": 1, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank"}},
        {"summary": {"row_count": 2}},
        {"summary": {"row_count": 2, "follow_on_targets": "core_binder_02, core_binder_03"}},
        {
            "summary": {
                "blocker_row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_focus_ligand": "AqB013",
                "exact_human_guardrail_ligand": "AqB013",
                "exact_human_nonbinding_count": 1,
                "exact_target_pair_absent_count": 1,
                "next_required_step": "Keep core_binder_02 as the guardrail while core_binder_03 closes the target-pair gap.",
            }
        },
    )

    row_map = {row["target"]: row for row in rows}
    assert row_map["glut1"]["open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
