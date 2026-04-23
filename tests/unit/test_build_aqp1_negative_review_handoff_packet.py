from __future__ import annotations

from tools import build_aqp1_negative_review_handoff_packet as mod


def test_build_aqp1_negative_review_handoff_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "AQP1_TRANSPORT_BLIND",
                "endpoint_status": "draft_only_local_evidence_blocked",
                "local_quantitative_negative_evidence_curated": False,
            },
            "rows": [
                {
                    "check_id": "negative_evidence",
                    "status": "blocked",
                    "signal": "review_only_negative_count=3",
                    "notes": "Keep negative slots review-only.",
                },
                {
                    "check_id": "fit_donor_policy",
                    "status": "blocked",
                    "signal": "hard_decoy_fit_targets=EGFR_KINASE",
                    "notes": "Temporary donor target.",
                },
            ],
        },
        {
            "rows": [
                {
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "current_ligand_id": "aqp1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "notes": "No proxy negatives.",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "next_action": "manual_negative_evidence_review",
                    "notes": "No proxy negatives.",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "tetraethylammonium",
                    "proposed_packet_step": "caution_only",
                    "review_bucket": "review_only_tool_reference",
                    "recommended_verdict": "caution_only",
                    "promotion_policy": "caution_only_not_for_authoritative_apply",
                    "caution": "Tool only.",
                },
                {
                    "candidate_name": "acetazolamide",
                    "proposed_packet_step": "caution_only",
                    "review_bucket": "defer_contested_system_effect",
                    "recommended_verdict": "defer",
                    "promotion_policy": "caution_only_not_for_authoritative_apply",
                    "caution": "Contested system effect.",
                },
            ]
        },
    )

    assert payload["summary"]["target_id"] == "AQP1_TRANSPORT_BLIND"
    assert payload["summary"]["authoritative_negative_apply_allowed"] is False
    assert payload["summary"]["negative_slot_count"] == 1
    assert payload["summary"]["caution_or_defer_reference_count"] == 2
    assert payload["summary"]["local_blocker_signal_count"] == 2
    assert len(payload["checklist"]) == 3
    assert payload["rows"][0]["section"] == "negative_slot_policy"
    assert payload["rows"][1]["section"] == "caution_or_defer_signal"
    assert payload["rows"][-1]["section"] == "local_blocker_signal"
