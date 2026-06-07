from __future__ import annotations

import json
from pathlib import Path

from tools import build_pxr_blocked_row_promotion_gate as mod


def test_build_pxr_blocked_row_promotion_gate_blocks_review_only_and_deferred_rows() -> None:
    payload = mod.build_payload(
        {
            "readiness_rows": [
                {
                    "packet": "core",
                    "packet_step": "core_eval_non_binder_01",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                    "ready_for_apply": "no",
                },
                {
                    "packet": "ood",
                    "packet_step": "ood_fit_binder_01",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                    "ready_for_apply": "no",
                },
                {
                    "packet": "ood",
                    "packet_step": "ood_eval_non_binder_01",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                    "ready_for_apply": "no",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "binder": "0",
                    "review_bucket": "defer_pending_target_specific_evidence",
                    "assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                },
                {
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "binder": "1",
                    "review_bucket": "defer_pending_target_specific_evidence",
                    "assay_type_honesty": "activity_present_manual_confirmation_required",
                },
                {
                    "packet_step": "ood_eval_non_binder_01",
                    "ligand": "nicotinamide",
                    "binder": "0",
                    "review_bucket": "review_only_negative",
                    "assay_type_honesty": "inactive_only_human_pxr_qhts_review_only",
                },
            ]
        },
        {"rows": []},
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "conflict_lane": "exact_human_dual_mode_activity_conflict",
                    "recommended_resolution": "keep_deferred_exact_human_dual_mode_conflict",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "provenance_scope": "supportive_manual_confirmation_quantitative_gap",
                    "quantitative_value_found": "no",
                }
            ]
        },
        {"rows": []},
        {"rows": []},
    )

    summary = payload["summary"]
    assert summary["blocked_row_count"] == 3
    assert summary["review_only_row_count"] == 1
    assert summary["defer_row_count"] == 2
    assert summary["claim_safe_quantitative_ready_count"] == 0
    assert summary["authoritative_apply_allowed_count"] == 0
    assert summary["promotion_ready"] is False

    rows = {row["packet_step"]: row for row in payload["rows"]}
    assert "keep_deferred_exact_human_dual_mode_conflict" in rows["core_eval_non_binder_01"]["fail_closed_blockers"]
    assert "claim_safe_quantitative_value_missing" in rows["ood_fit_binder_01"]["fail_closed_blockers"]
    assert "review_only_not_authoritative_apply" in rows["ood_eval_non_binder_01"]["fail_closed_blockers"]


def test_build_pxr_blocked_row_promotion_gate_skips_ready_rows() -> None:
    payload = mod.build_payload(
        {
            "readiness_rows": [
                {"packet_step": "ready_step", "ready_for_apply": "yes"},
                {"packet_step": "blocked_step", "required_missing_fields": "replacement_reference_binding_kcal_mol", "ready_for_apply": "no"},
            ]
        },
        {"rows": [{"packet_step": "blocked_step", "ligand": "x", "binder": "0", "review_bucket": "review_only_negative"}]},
        {"rows": []},
        {"rows": []},
        {"rows": []},
        {"rows": []},
        {"rows": []},
    )

    assert [row["packet_step"] for row in payload["rows"]] == ["blocked_step"]


def test_build_pxr_blocked_row_promotion_gate_promotes_numeric_zero_blocked_summary() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "blocked_row_count": 0,
                "ready_for_apply_row_count": 14,
            },
            "readiness_rows": [
                {"packet_step": "ready_step", "ready_for_apply": "yes"},
            ],
        },
        {"rows": []},
        {"rows": []},
        {"rows": []},
        {"rows": []},
        {"rows": []},
        {"rows": []},
    )

    summary = payload["summary"]
    assert summary["blocked_row_count"] == 0
    assert summary["claim_safe_quantitative_ready_count"] == 14
    assert summary["authoritative_apply_allowed_count"] == 14
    assert summary["promotion_ready"] is True
    assert summary["primary_blocker"] == "none"


def test_build_pxr_blocked_row_promotion_gate_cli_writes_outputs(tmp_path: Path) -> None:
    fill = tmp_path / "fill.json"
    review = tmp_path / "review.json"
    public = tmp_path / "public.json"
    conflict = tmp_path / "conflict.json"
    quantitative = tmp_path / "quant.json"
    exact = tmp_path / "exact.json"
    pending = tmp_path / "pending.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    fill.write_text(
        json.dumps({"readiness_rows": [{"packet_step": "blocked_step", "required_missing_fields": "replacement_reference_binding_kcal_mol", "ready_for_apply": "no"}]}) + "\n",
        encoding="utf-8",
    )
    review.write_text(json.dumps({"rows": [{"packet_step": "blocked_step", "ligand": "x", "binder": "0", "review_bucket": "defer_pending_target_specific_evidence"}]}) + "\n", encoding="utf-8")
    public.write_text(json.dumps({"rows": []}) + "\n", encoding="utf-8")
    conflict.write_text(json.dumps({"rows": []}) + "\n", encoding="utf-8")
    quantitative.write_text(json.dumps({"rows": []}) + "\n", encoding="utf-8")
    exact.write_text(json.dumps({"rows": []}) + "\n", encoding="utf-8")
    pending.write_text(json.dumps({"rows": []}) + "\n", encoding="utf-8")

    mod.main(
        [
            "--fill-readiness-json",
            str(fill),
            "--review-packet-json",
            str(review),
            "--public-overlay-json",
            str(public),
            "--conflict-resolver-json",
            str(conflict),
            "--quantitative-json",
            str(quantitative),
            "--exact-confirmation-json",
            str(exact),
            "--pending-disposition-json",
            str(pending),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["promotion_ready"] is False
    assert "replacement_reference_binding_kcal_mol" in out_csv.read_text(encoding="utf-8")
    assert "PXR Blocked Row Promotion Gate" in out_md.read_text(encoding="utf-8")
