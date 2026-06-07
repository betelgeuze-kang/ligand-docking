from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_pxr_exact_evidence_review_intake_template as mod


ROOT = Path(__file__).resolve().parents[2]


def _reconciliation() -> dict[str, object]:
    return {
        "summary": {
            "reconciliation_packet_ready": True,
            "reconciled_blocked_row_count": 3,
            "gate_blocked_row_count": 3,
            "authoritative_apply_allowed_count": 0,
        },
        "rows": [
            {
                "rank": 1,
                "packet_step": "core_eval_non_binder_01",
                "candidate_name": "acetaminophen",
                "current_label": "non_binder",
                "review_bucket": "defer_pending_target_specific_evidence",
                "request_mode": "exact_human_pxr_conflict_resolution_or_negative_quantitative_value_required",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "workbook_replacement_ligand_id": "acetaminophen",
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,activity_proxy_conflicts_with_non_binder",
                "gate_authoritative_apply_allowed": False,
            },
            {
                "rank": 2,
                "packet_step": "ood_eval_non_binder_01",
                "candidate_name": "nicotinamide",
                "current_label": "non_binder",
                "review_bucket": "review_only_negative",
                "request_mode": "exact_human_pxr_negative_or_inactive_quantitative_value_required",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "workbook_replacement_ligand_id": "nicotinamide",
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,review_only_not_authoritative_apply",
                "gate_authoritative_apply_allowed": False,
            },
            {
                "rank": 3,
                "packet_step": "ood_fit_binder_01",
                "candidate_name": "bexarotene",
                "current_label": "binder",
                "review_bucket": "defer_pending_target_specific_evidence",
                "request_mode": "exact_human_pxr_quantitative_binder_value_required",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "workbook_replacement_ligand_id": "bexarotene",
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,claim_safe_quantitative_value_missing",
                "gate_authoritative_apply_allowed": False,
            },
        ],
    }


def test_pxr_exact_evidence_review_intake_template_prefills_blocked_rows() -> None:
    payload = mod.build_payload(reconciliation_packet=_reconciliation())

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}
    assert summary["pxr_exact_review_intake_ready"] is True
    assert summary["review_template_row_count"] == 3
    assert summary["unique_review_row_id_count"] == 3
    assert summary["unique_review_row_ids_ready"] is True
    assert summary["binder_review_row_count"] == 1
    assert summary["non_binder_review_row_count"] == 2
    assert summary["conflict_resolution_required_count"] == 2
    assert summary["kcal_placeholder_count"] == 3
    assert summary["source_placeholder_count"] == 3
    assert summary["next_review_completion_packet_ready"] is True
    assert summary["next_review_return_bundle_required_artifact_count"] == 5
    assert summary["next_review_return_bundle_completion_matrix_count"] == 5
    assert summary["next_review_return_bundle_blocker_count"] == 5
    assert summary["next_review_return_bundle_next_artifact_id"] == "operator_review_row"
    assert summary["next_review_return_bundle_next_artifact_path"] == (
        "runs/pxr_exact_evidence_review_intake_template_current.csv"
    )
    assert "next_review_placeholder_fields" in summary[
        "next_review_return_bundle_next_artifact_failed_check_ids"
    ]
    assert summary["next_review_candidate_name"] == "acetaminophen"
    assert summary["next_review_packet_step"] == "core_eval_non_binder_01"
    assert summary["next_review_required_evidence_mode"] == (
        "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required"
    )
    assert summary["next_review_operator_review_artifact"] == (
        "runs/pxr_exact_evidence_review_intake_template_current.csv"
    )
    next_packet = payload["next_review_completion_packet"]
    assert next_packet["candidate_name"] == "acetaminophen"
    assert next_packet["conflict_resolution_required"] is True
    assert "conflict_resolution_decision" in next_packet["required_operator_intake_columns"]
    assert "conflict_resolution_decision" in next_packet["required_exact_evidence_fields"]
    assert "target_match_confirmed" in next_packet["required_exact_evidence_fields"]
    assert "human_NR1I2_PXR_target_match_required" in next_packet["required_claim_guardrails"]
    assert "activity_proxy_conflict_must_be_resolved_or_deferred" in next_packet[
        "required_claim_guardrails"
    ]
    assert next_packet["required_claim_guardrail_count"] == 5
    assert "replacement_reference_binding_kcal_mol" in next_packet["placeholder_fields"]
    assert next_packet["return_bundle_required_artifact_count"] == 5
    assert "runs/pxr_blocked_row_promotion_gate_current.json" in next_packet[
        "return_bundle_required_artifacts"
    ]
    matrix = payload["next_review_return_bundle_completion_matrix"]
    assert matrix[0]["artifact_id"] == "operator_review_row"
    assert matrix[0]["review_row_id"].startswith("pxr_review_")
    assert "replacement_reference_binding_kcal_mol" in matrix[0]["required_fields_or_columns"]
    assert matrix[1]["artifact_id"] == "pxr_fill_readiness"
    assert matrix[1]["validation_command"] == "python3 tools/validate_pxr_packet_fill_readiness.py"
    assert matrix[-1]["artifact_id"] == "scope_breadth_contract"
    assert any(
        "build_product_scope_breadth_contract.py" in command
        for command in next_packet["validation_commands"]
    )
    assert rows["core_eval_non_binder_01"]["conflict_resolution_decision"] == mod.DECISION_PLACEHOLDER
    assert rows["core_eval_non_binder_01"]["review_row_id"].startswith("pxr_review_")
    assert len(rows["core_eval_non_binder_01"]["source_row_fingerprint"]) == 64
    assert rows["ood_eval_non_binder_01"]["conflict_resolution_decision"] == ""
    assert rows["ood_fit_binder_01"]["required_evidence_mode"] == "exact_human_nr1i2_pxr_quantitative_binder_value_required"
    assert all(row["authoritative_apply_allowed"] is False for row in payload["rows"])


def test_pxr_exact_evidence_review_intake_template_blocks_without_reconciliation() -> None:
    payload = mod.build_payload(reconciliation_packet={"summary": {"reconciliation_packet_ready": False}})

    summary = payload["summary"]
    assert summary["pxr_exact_review_intake_ready"] is False
    assert "reconciliation_packet_ready" in summary["blockers"]
    assert "blocked_review_rows" in summary["blockers"]


def test_pxr_exact_evidence_review_intake_template_cli_writes_outputs(tmp_path: Path) -> None:
    reconciliation = tmp_path / "reconciliation.json"
    out_json = tmp_path / "review.json"
    out_csv = tmp_path / "review.csv"
    out_md = tmp_path / "review.md"
    reconciliation.write_text(json.dumps(_reconciliation()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_pxr_exact_evidence_review_intake_template.py",
            "--reconciliation-json",
            str(reconciliation),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["pxr_exact_review_intake_ready"] is True
    assert "review_row_id" in out_csv.read_text(encoding="utf-8")
    assert "replacement_reference_binding_kcal_mol" in out_csv.read_text(encoding="utf-8")
    assert "PXR Exact Evidence Review Intake Template" in out_md.read_text(encoding="utf-8")
    assert "Next Review Return Bundle" in out_md.read_text(encoding="utf-8")
