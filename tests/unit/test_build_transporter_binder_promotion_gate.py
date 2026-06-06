from __future__ import annotations

import json
from pathlib import Path

from tools import build_transporter_binder_promotion_gate as mod


def test_build_transporter_binder_promotion_gate_blocks_without_claim_safe_kcal() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "AqB013",
                    "current_recommended_verdict": "keep_review_only",
                    "authoritative_apply_blocker": "functional only",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "claim_safe_binding_kcal_ready": "no",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                    "assay_type_honesty": "functional_not_direct_binding",
                }
            ]
        },
        {"rows": []},
        {"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "yes"}]},
        {"workbook_rows": []},
    )

    assert payload["summary"]["binder_promotion_gate_ready"] is True
    assert payload["summary"]["binder_promotion_ready"] is False
    assert payload["summary"]["claim_safe_kcal_ready_count"] == 0
    assert payload["summary"]["workbook_ready_binder_row_count"] == 1
    assert payload["summary"]["authoritative_binder_apply_allowed_count"] == 0
    assert payload["summary"]["target_ready_for_promotion_ids"] == []
    assert payload["summary"]["target_blocked_for_promotion_ids"] == ["AQP1"]
    assert payload["summary"]["primary_blocker_target_id"] == "AQP1"
    assert payload["summary"]["primary_blocker_packet_step"] == "core_binder_01"
    assert payload["rows"][0]["promotion_blocker"] == "claim_safe_binding_kcal_missing"


def test_build_transporter_binder_promotion_gate_allows_claim_safe_row() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "current_recommended_verdict": "promote_authoritative_apply",
                    "authoritative_apply_blocker": "",
                }
            ]
        },
        {"rows": []},
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "claim_safe_binding_kcal_ready": "yes",
                    "public_provenance_signal": "direct_binding_kcal_curated",
                    "assay_type_honesty": "direct_quantitative_binding",
                }
            ]
        },
        {"workbook_rows": []},
        {"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "yes"}]},
    )

    assert payload["summary"]["binder_promotion_ready"] is True
    assert payload["summary"]["claim_safe_kcal_ready_count"] == 1
    assert payload["summary"]["workbook_ready_binder_row_count"] == 1
    assert payload["summary"]["authoritative_binder_apply_allowed_count"] == 1
    assert payload["summary"]["target_ready_for_promotion_ids"] == ["GLUT1"]
    assert payload["summary"]["target_blocked_for_promotion_ids"] == []
    assert payload["rows"][0]["promotion_blocker"] == ""


def test_build_transporter_binder_promotion_gate_keeps_target_blockers_visible() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "current_recommended_verdict": "keep_review_only",
                    "authoritative_apply_blocker": "functional only",
                },
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "current_recommended_verdict": "promote_authoritative_apply",
                    "authoritative_apply_blocker": "",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "claim_safe_binding_kcal_ready": "no",
                    "public_provenance_signal": "compound_resolved_target_activity_absent",
                    "assay_type_honesty": "functional_not_direct_binding",
                }
            ]
        },
        {"rows": []},
        {"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "no"}]},
        {"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "yes"}]},
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "claim_safe_binding_kcal_ready": "yes",
                    "manual_verdict": "promote_authoritative_apply",
                    "delta_g_method": "RTln(Kd_M) at 298.15 K",
                }
            ]
        },
    )

    assert payload["summary"]["binder_promotion_ready"] is True
    assert payload["summary"]["target_ready_for_promotion_ids"] == ["GLUT1"]
    assert payload["summary"]["target_blocked_for_promotion_ids"] == ["AQP1"]
    assert payload["summary"]["primary_blocker_target_id"] == "AQP1"
    assert payload["summary"]["primary_blocker_candidate_name"] == "bacopaside II"
    assert "target_blocked_for_promotion_ids=AQP1" in payload["summary"]["primary_blocker_signal"]
    assert "blocked targets" in payload["summary"]["next_required_step"]


def test_build_transporter_binder_promotion_gate_uses_glut1_claim_safe_override() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "current_recommended_verdict": "keep_review_only",
                    "authoritative_apply_blocker": "previously blocked",
                }
            ]
        },
        {"rows": []},
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "claim_safe_binding_kcal_ready": "no",
                    "public_provenance_signal": "direct_quantitative_binding_present_leave_kcal_blank",
                }
            ]
        },
        {"workbook_rows": []},
        {"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "yes"}]},
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "claim_safe_binding_kcal_ready": "yes",
                    "manual_verdict": "promote_authoritative_apply",
                    "delta_g_method": "RTln(Kd_M) at 298.15 K",
                }
            ]
        },
    )

    assert payload["summary"]["binder_promotion_ready"] is True
    assert payload["summary"]["claim_safe_kcal_ready_count"] == 1
    assert payload["summary"]["authoritative_binder_apply_allowed_count"] == 1
    assert payload["rows"][0]["current_recommended_verdict"] == "promote_authoritative_apply"
    assert payload["rows"][0]["claim_safe_override_applied"] is True


def test_build_transporter_binder_promotion_gate_cli_writes_outputs(tmp_path: Path) -> None:
    rubric = tmp_path / "rubric.json"
    aqp1 = tmp_path / "aqp1.json"
    glut1 = tmp_path / "glut1.json"
    glut1_claim_safe = tmp_path / "glut1_claim_safe.json"
    aqp1_workbook = tmp_path / "aqp1_workbook.json"
    glut1_workbook = tmp_path / "glut1_workbook.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    rubric.write_text(json.dumps({"rows": [{"target_id": "AQP1", "packet_step": "core_binder_01", "candidate_name": "x"}]}) + "\n")
    aqp1.write_text(json.dumps({"rows": [{"packet_step": "core_binder_01", "claim_safe_binding_kcal_ready": "no"}]}) + "\n")
    glut1.write_text(json.dumps({"rows": []}) + "\n")
    glut1_claim_safe.write_text(json.dumps({"rows": []}) + "\n")
    aqp1_workbook.write_text(json.dumps({"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "no"}]}) + "\n")
    glut1_workbook.write_text(json.dumps({"workbook_rows": []}) + "\n")

    mod.main(
        [
            "--rubric-json",
            str(rubric),
            "--aqp1-provenance-json",
            str(aqp1),
            "--glut1-source-json",
            str(glut1),
            "--glut1-claim-safe-kcal-json",
            str(glut1_claim_safe),
            "--aqp1-workbook-json",
            str(aqp1_workbook),
            "--glut1-workbook-json",
            str(glut1_workbook),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["binder_promotion_ready"] is False
    assert "claim_safe_binding_kcal_missing" in out_csv.read_text(encoding="utf-8")
    assert "Transporter Binder Promotion Gate" in out_md.read_text(encoding="utf-8")
