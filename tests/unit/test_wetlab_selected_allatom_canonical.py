from tools.wetlab_selected_allatom_canonical import resolve_selected_allatom_canonical


def test_claim_only_commercial_block_is_semi_hard_not_translation_hard() -> None:
    payload = resolve_selected_allatom_canonical(
        review_packet_summary={
            "target_id": "T. cruzi PDE",
            "surface_label": "tcruzi_pde_allatom_review_packet",
            "packet_ready_for_operator_review": True,
            "wetlab_final_gate_pass": False,
            "commercial_schema_version_v2": "wetlab_commercial_grade_v2",
            "commercial_hard_gate_pass_v2": False,
            "commercial_primary_upgrade_actions_v2": ["resolve_claim_equivalence_gate"],
            "translation_gate_focus_status": "borderline",
            "best_mean_min_distance_A": 2.12,
            "wetlab_gate_thresholds": {"selected_threshold_A": 2.5},
            "claim_gate_available": True,
            "claim_ready_for_allatom": False,
            "claim_gate_primary_action": "resolve_claim_equivalence_gate",
            "claim_gate_requirement_mode": "semi_hard",
            "claim_gate_required_for_final_wetlab": True,
            "claim_gate_required_for_commercial_readiness": True,
        },
        retry_handoff_summary={
            "selected_allatom_target_id": "T. cruzi PDE",
            "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
        },
        allow_translation_fallback=False,
    )

    assert payload["effective_actionability_status"] == "semi_hard_blocked"
    assert payload["effective_primary_blocking_domain"] == "claim_equivalence"
    assert payload["effective_blocking_order"] == "claim_block_first"
    assert payload["action_recipe_codes"][0] == "resolve_claim_equivalence_gate"
    assert "resolve_claim_equivalence_gate" in payload["action_recipe_codes"]
    assert all(row["severity"] != "hard" for row in payload["action_recipe_rows"])
