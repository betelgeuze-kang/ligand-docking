from __future__ import annotations

from tools.product import build_aqp1_manual_review_queue as mod


def test_build_aqp1_manual_review_queue() -> None:
    payload = mod.build_payload(
        [
            {
                "packet": "core",
                "packet_step": "core_binder_01",
                "current_ligand_id": "aqp1_placeholder_binder_01",
                "replacement_is_binder": "1",
                "required_missing_fields": "replacement_ligand_id",
            },
            {
                "packet": "core",
                "packet_step": "core_non_binder_01",
                "current_ligand_id": "aqp1_placeholder_nonbinder_01",
                "replacement_is_binder": "0",
                "required_missing_fields": "replacement_ligand_id",
            },
        ],
        {
            "rows": [
                {
                    "proposed_packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "recommended_review_bucket": "review_only_first_wave",
                    "source_anchor": "PMID 27474162",
                }
            ]
        },
    )
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["defer_binder_count"] == 1
    assert payload["summary"]["review_only_negative_count"] == 1
    rows = {row["packet_step"]: row for row in payload["rows"]}
    assert rows["core_binder_01"]["review_bucket"] == "defer_pending_target_specific_evidence"
    assert rows["core_non_binder_01"]["review_bucket"] == "review_only_negative_evidence"
    assert rows["core_binder_01"]["suggested_external_candidate"] == "bacopaside II"


def test_build_aqp1_manual_review_queue_promotes_exact_human_activity_lane() -> None:
    payload = mod.build_payload(
        [
            {
                "packet": "core",
                "packet_step": "core_binder_02",
                "current_ligand_id": "aqp1_placeholder_binder_02",
                "replacement_is_binder": "1",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
            }
        ],
        {
            "rows": [
                {
                    "proposed_packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "recommended_review_bucket": "review_only_first_wave",
                    "source_anchor": "PMID 22427546",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                    "state_change_potential": "medium",
                    "chembl_activity_record_count": 1,
                    "chembl_best_activity_type": "IC50",
                    "chembl_best_activity_value": "20000.0",
                    "chembl_best_activity_units": "nM",
                }
            ]
        },
    )
    assert payload["summary"]["exact_human_activity_binder_count"] == 1
    row = payload["rows"][0]
    assert row["review_bucket"] == "defer_exact_human_activity_nonbinding"
    assert row["promotion_blocker"] == "no_claim_safe_aqp1_binding_kcal_curated"
    assert row["next_required_action"] == "carry_exact_human_activity_provenance_keep_kcal_blank"
    assert row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
