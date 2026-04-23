from __future__ import annotations

from tools import build_pxr_pending_resolution_packet as mod


def test_build_pxr_pending_resolution_packet_merges_policy_slice_and_readiness() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "policy_line": "Keep ibuprofen review-only and defer the rest.",
                "next_required_step": "Do not auto-promote deferred rows.",
            }
        },
        {
            "summary": {"next_required_step": "Defer unresolved rows."},
            "rows": [
                {
                    "priority_rank": "13",
                    "packet_step": "ood_eval_non_binder_02",
                    "replacement_ligand_id": "ibuprofen",
                    "replacement_is_binder": "0",
                    "verification_status": "pending_binding_provenance_review",
                    "review_reason": "weak upper bound only",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "ready_for_authoritative_apply": "no",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "replacement_is_binder": "1",
                    "verification_status": "pending_binding_provenance_review",
                    "review_reason": "supportive human PXR evidence is confirmed but still needs quantitative provenance",
                    "assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "ready_for_authoritative_apply": "no",
                    "next_required_action": "curate_quantitative_binding_value",
                },
            ],
        },
        {
            "target": "PXR_NR1I2_BLIND",
            "summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6},
            "readiness_rows": [
                {"packet_step": "ood_eval_non_binder_02", "missing_fields": "replacement_reference_binding_kcal_mol", "ready_for_apply": "no"},
                {"packet_step": "ood_fit_binder_01", "missing_fields": "replacement_reference_binding_kcal_mol", "ready_for_apply": "no"},
            ],
        },
        {
            "rows": [
                {
                    "packet_step": "ood_eval_non_binder_02",
                    "disposition": "review_only_negative_evidence",
                    "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "packet_step": "ood_fit_binder_01",
                    "disposition": "pending_binder_curation",
                    "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "next_required_action": "curate_quantitative_binding_value",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "binder": "0",
                    "review_bucket": "review_only_negative",
                },
                {
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "binder": "1",
                    "review_bucket": "defer_pending_target_specific_evidence",
                },
            ]
        },
    )
    assert payload["summary"]["pending_resolution_row_count"] == 2
    assert payload["summary"]["review_only_row_count"] == 1
    assert payload["summary"]["defer_row_count"] == 0
    assert payload["summary"]["binder_gap_count"] == 1
    assert payload["summary"]["supportive_binder_review_count"] == 0
    assert payload["summary"]["confirmed_binder_quantitative_gap_count"] == 1
    assert payload["rows"][0]["ligand"] == "ibuprofen"
    assert payload["rows"][1]["promotion_blocker"] == "quantitative_binding_value_or_activity_proxy_missing"


def test_pxr_readiness_lookup_keys_by_packet_step() -> None:
    lookup = mod._readiness_lookup(
        {
            "readiness_rows": [
                {"packet_step": "core_eval_non_binder_01", "missing_fields": "replacement_reference_binding_kcal_mol"},
            ]
        }
    )
    assert lookup["core_eval_non_binder_01"]["missing_fields"] == "replacement_reference_binding_kcal_mol"
