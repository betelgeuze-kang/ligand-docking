from __future__ import annotations

from tools import build_transporter_binder_decision_rubric as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_binder_decision_rubric() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "current_recommended_verdict": "keep_review_only",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "current_recommended_verdict": "keep_review_only",
                },
                {
                    "packet_step": "core_binder_02",
                    "candidate_name": "WZB117",
                    "current_recommended_verdict": "keep_review_only",
                },
                {
                    "packet_step": "core_binder_03",
                    "candidate_name": "STF-31",
                    "current_recommended_verdict": "keep_review_only",
                },
            ]
        },
        {
            "summary": {
                "packet_artifact": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "row_count": 3,
                "primary_focus_ligand": "cytochalasin B",
                "direct_quantitative_binding_count": 1,
                "exact_target_pair_activity_count": 2,
                "structured_pair_absent_count": 1,
            }
        },
    )

    assert payload["summary"]["binder_slot_count"] == 4
    assert payload["summary"]["policy_status"] == "reviewer_state_only_blocker_closure"
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_row_count"] == 3
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["glut1_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["glut1_exact_target_pair_activity_count"] == 2
    assert payload["summary"]["glut1_structured_pair_absent_count"] == 1
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "blocker closure",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
        "wzb117",
        "exact-target-pair functional lane",
        "stf-31",
        "structured-pair caveat",
    )

    row_map = {row["candidate_name"]: row for row in payload["rows"]}

    assert row_map["bacopaside II"]["target_id"] == "AQP1"
    assert row_map["bacopaside II"]["source_confirmation_packet_artifact"] == ""
    assert "direct human AQP1 target-binding" in row_map["bacopaside II"]["authoritative_apply_blocker"]

    cyto = row_map["cytochalasin B"]
    assert cyto["target_id"] == "GLUT1"
    assert cyto["source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert cyto["source_confirmation_packet_primary_focus_ligand"] == "cytochalasin B"
    assert cyto["source_confirmation_packet_row_count"] == 3
    _contains_tokens(cyto["keep_review_only_reason"], "lead review-only row", "direct quantitative human glut1 binding lane")
    _contains_tokens(cyto["authoritative_apply_blocker"], "non-authoritative", "claim-safe kcal", "donor-policy")
    _contains_tokens(cyto["minimum_next_evidence"], "3-row second-wave handoff", "claim-safe curated transporter packet row")

    wzb117 = row_map["WZB117"]
    assert wzb117["source_confirmation_packet_row_count"] == 3
    _contains_tokens(wzb117["keep_review_only_reason"], "exact-target-pair functional lane", "not as a direct-binding row")
    _contains_tokens(wzb117["authoritative_apply_blocker"], "authoritative binder claim")
    _contains_tokens(wzb117["minimum_next_evidence"], "exact-target-pair functional lane", "direct transporter-specific binding")

    stf31 = row_map["STF-31"]
    assert stf31["source_confirmation_packet_primary_focus_ligand"] == "cytochalasin B"
    _contains_tokens(stf31["keep_review_only_reason"], "structured-pair caveat lane")
    _contains_tokens(stf31["authoritative_apply_blocker"], "structured-pair gap", "nampt")
    _contains_tokens(stf31["minimum_next_evidence"], "structured-pair caveat", "exact-target-pair evidence")
