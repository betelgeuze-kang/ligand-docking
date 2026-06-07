from __future__ import annotations

from tools.product import build_glut1_next_verification_slice as mod


def test_build_glut1_next_verification_slice() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "candidate_name": "cytochalasin B",
                    "proposed_packet_step": "core_binder_01",
                    "recommended_review_bucket": "review_only_second_wave",
                    "source_anchor": "PMID 27078104",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "replacement_is_binder": "0",
                    "current_ligand_id": "glut1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "next_required_action": "manual_negative_evidence_review",
                }
            ]
        },
    )
    assert payload["summary"]["row_count"] == 2
    assert payload["rows"][0]["label"] == "cytochalasin B"
    assert payload["rows"][1]["work_item_type"] == "negative_slot_review"
