from __future__ import annotations

from tools.product import build_glut1_manual_review_queue as mod


def test_build_glut1_manual_review_queue() -> None:
    payload = mod.build_payload(
        [
            {
                "packet": "core",
                "packet_step": "core_binder_01",
                "current_ligand_id": "glut1_placeholder_binder_01",
                "replacement_is_binder": "1",
                "required_missing_fields": "replacement_ligand_id",
            },
            {
                "packet": "core",
                "packet_step": "core_non_binder_01",
                "current_ligand_id": "glut1_placeholder_nonbinder_01",
                "replacement_is_binder": "0",
                "required_missing_fields": "replacement_ligand_id",
            },
        ],
        {
            "rows": [
                {
                    "proposed_packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "recommended_review_bucket": "review_only_second_wave",
                    "source_anchor": "PMID 27078104",
                }
            ]
        },
    )
    assert payload["summary"]["defer_binder_count"] == 1
    assert payload["summary"]["review_only_negative_count"] == 1
    assert payload["rows"][0]["suggested_external_candidate"] == "cytochalasin B"
