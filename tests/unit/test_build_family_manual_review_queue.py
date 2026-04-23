from __future__ import annotations

from tools.build_family_manual_review_queue import build_payload


def test_build_payload_uses_pending_disposition_for_pxr() -> None:
    rows = [
        {
            "priority_rank": "5",
            "packet": "core",
            "packet_step": "core_eval_non_binder_01",
            "replacement_ligand_id": "acetaminophen",
            "replacement_is_binder": "0",
            "verification_status": "pending_binding_provenance_review",
        },
        {
            "priority_rank": "10",
            "packet": "ood",
            "packet_step": "ood_fit_binder_01",
            "replacement_ligand_id": "bexarotene",
            "replacement_is_binder": "1",
            "verification_status": "pending_binding_provenance_review",
        },
    ]
    pending_disposition = {
        "rows": [
            {
                "priority_rank": "5",
                "packet_step": "core_eval_non_binder_01",
                "replacement_ligand_id": "acetaminophen",
                "disposition": "defer_pending_target_specific_evidence",
                "promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                "next_required_action": "manual_curated_search_or_defer",
                "notes": "defer",
            },
            {
                "priority_rank": "10",
                "packet_step": "ood_fit_binder_01",
                "replacement_ligand_id": "bexarotene",
                "disposition": "defer_pending_target_specific_evidence",
                "promotion_blocker": "no_local_target_activity_curated",
                "next_required_action": "manual_curated_search_or_defer",
                "notes": "defer",
            },
        ]
    }
    payload = build_payload("pxr", rows, pending_disposition)
    assert payload["summary"]["uses_pending_disposition"] is True
    assert payload["summary"]["defer_binder_count"] == 2
    assert payload["summary"]["policy_fixed_pending_count"] == 2
    assert all(row["review_bucket"] == "defer_pending_target_specific_evidence" for row in payload["rows"])
