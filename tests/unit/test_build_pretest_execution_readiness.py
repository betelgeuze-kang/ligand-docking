from __future__ import annotations

from tools import build_pretest_execution_readiness as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_pretest_execution_readiness() -> None:
    payload = mod.build_payload(
        {
            "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
            "rows": [
                {"family": "gpcr", "score": 82},
                {"family": "ion_channel", "score": 88},
                {"family": "kinase", "score": 90},
                {"family": "idp", "score": 70},
                {"family": "non_kinase_enzyme_ca2", "score": 58},
                {"family": "nuclear_receptor_pxr", "score": 62},
                {"family": "transporter", "score": 32},
            ],
        },
        {
            "rows": [
                {"family": "gpcr", "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked"},
                {"family": "ion_channel", "current_state": "locked_decoy_shadow_ready", "next_required_step": "keep ion stable"},
                {"family": "kinase", "current_state": "locked_decoy_shadow_ready", "next_required_step": "keep kinase stable"},
                {"family": "idp", "current_state": "literature_anchor_default_mask_ready_broader_corrected_promotion_blocked"},
                {"family": "non_kinase_enzyme_ca2", "current_state": "binding_verification_in_progress"},
                {"family": "nuclear_receptor_pxr", "current_state": "binding_verification_in_progress"},
                {"family": "transporter", "current_state": "draft_packet_external_seeded_local_evidence_blocked"},
            ]
        },
        {"summary": {"next_required_step": "keep gpcr endpoint only"}},
        {"summary": {"next_required_step": "keep idp subset only"}},
        {"summary": {"status": "operator_packet_ready", "next_required_step": "run the controlled idp commercial pretest"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2 negatives"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR negatives"}},
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "binder_seed_row_count": 6,
                "placeholder_row_count_total": 12,
                "next_required_step": "keep transporter manual-review only",
            }
        },
        {"summary": {"top_blocker_id": "placeholder_packet_rows", "next_required_step": "promote AQP1 seed rows first"}},
        {
            "summary": {
                "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe",
                "blocking_class": "bounded_review_required",
                "additional_anchor_backed_target_count": 0,
                "next_required_step": "keep broader_full_idp_promotion blocked and use a same-scope process check or curate an additional anchor-backed target first",
            }
        },
    )

    assert payload["summary"]["family_count"] == 7
    assert payload["summary"]["pretest_ready_count"] == 4
    assert payload["summary"]["partial_pretest_ready_count"] == 2
    assert payload["summary"]["blocked_pretest_count"] == 1
    assert payload["summary"]["controlled_shadow_only_count"] == 1
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["gpcr"]["pretest_ready"] == "yes"
    assert rows["gpcr"]["router_ready"] == "no"
    assert rows["idp"]["claim_safe_test_ready"] == "controlled_shadow_only"
    assert rows["idp"]["runtime_scope_now"] == "controlled_shadow_only_commercial_pretest"
    _contains_tokens(rows["idp"]["next_required_step"], "broader_full_idp_promotion", "same-scope", "anchor-backed")
    assert rows["non_kinase_enzyme_ca2"]["pretest_ready"] == "partial"
    assert rows["transporter"]["pretest_ready"] == "no"
    assert rows["transporter"]["runtime_scope_now"] == "blocker_closure_seed_row_promotion_only"
    assert rows["transporter"]["primary_blocker"] == "placeholder_packet_rows"
    _contains_tokens(rows["transporter"]["next_required_step"], "aqp1", "seed")
    assert payload["summary"]["transporter_seed_row_count"] == 6
    assert payload["summary"]["transporter_placeholder_row_count"] == 12
    _contains_tokens(payload["summary"]["next_required_step"], "controlled", "idp", "commercial-pretest", "same-scope", "anchor-backed")


def test_build_pretest_execution_readiness_prefers_idp_commercial_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9}, "rows": []},
        {"rows": [{"family": "idp", "current_state": "old_state"}]},
        {"summary": {"next_required_step": "keep gpcr endpoint only"}},
        {"summary": {"next_required_step": "keep idp subset only"}},
        {"summary": {"status": "operator_packet_ready", "next_required_step": "run the controlled idp commercial pretest"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2 negatives"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR negatives"}},
        {"summary": {"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6, "placeholder_row_count_total": 12}},
        {"summary": {"top_blocker_id": "placeholder_packet_rows", "next_required_step": "promote AQP1 seed rows first"}},
        {
            "summary": {
                "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe",
                "blocking_class": "corrected_path_fragility",
                "next_required_step": "keep broader promotion blocked and move the next tau_k18 slice to the remaining base/ph_low compact-state gap",
            }
        },
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["idp"]["current_state"] == "controlled_shadow_only_commercial_pretest_completed_shadow_safe"
    assert rows["idp"]["primary_blocker"] == "corrected_path_fragility"
    _contains_tokens(rows["idp"]["next_required_step"], "tau_k18", "base/ph_low", "compact-state")


def test_build_pretest_execution_readiness_moves_to_page4_quantitative_anchor_replacement() -> None:
    payload = mod.build_payload(
        {"summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9}, "rows": []},
        {"rows": [{"family": "idp", "current_state": "old_state"}]},
        {"summary": {"next_required_step": "keep gpcr endpoint only"}},
        {"summary": {"next_required_step": "keep idp subset only"}},
        {"summary": {"status": "operator_packet_ready", "next_required_step": "run the controlled idp commercial pretest"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2 negatives"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR negatives"}},
        {"summary": {"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6, "placeholder_row_count_total": 12}},
        {"summary": {"top_blocker_id": "placeholder_packet_rows", "next_required_step": "promote AQP1 seed rows first"}},
        {
            "summary": {
                "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe",
                "blocking_class": "page4_quantitative_anchor_replacement_required",
                "same_scope_reproducibility_confirmed": True,
                "additional_anchor_backed_target_count": 0,
                "page4_candidate_ready_now": True,
                "next_required_step": "move the next improvement to page4 quantitative anchor replacement before any true broader rerun",
            }
        },
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["idp"]["primary_blocker"] == "page4_quantitative_anchor_replacement_required"
    _contains_tokens(payload["summary"]["next_required_step"], "page4", "quantitative", "anchor", "replacement")


def test_build_pretest_execution_readiness_prefers_broader_promotion_resolution() -> None:
    payload = mod.build_payload(
        {"summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9}, "rows": []},
        {"rows": [{"family": "idp", "current_state": "old_state"}]},
        {"summary": {"next_required_step": "keep gpcr endpoint only"}},
        {"summary": {"next_required_step": "keep idp subset only"}},
        {"summary": {"status": "operator_packet_ready", "next_required_step": "run the controlled idp commercial pretest"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2 negatives"}},
        {"summary": {"most_common_missing_field": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR negatives"}},
        {"summary": {"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6, "placeholder_row_count_total": 12}},
        {"summary": {"top_blocker_id": "placeholder_packet_rows", "next_required_step": "promote AQP1 seed rows first"}},
        {"summary": {"status": "controlled_shadow_only_commercial_pretest_broader_shadow_completed", "blocking_class": "explicit_promotion_decision_required"}},
        {},
        {"summary": {"status": "one_wider_shadow_safe_lane_admitted_not_commercialized", "blocking_class": "bounded_wider_lane_only", "next_required_step": "run only the admitted one-wider shadow-safe lane and keep commercialization blocked"}},
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["idp"]["current_state"] == "one_wider_shadow_safe_lane_admitted_not_commercialized"
    assert rows["idp"]["runtime_scope_now"] == "one_wider_shadow_safe_lane_only"
    assert rows["idp"]["primary_blocker"] == "bounded_wider_lane_only"
    _contains_tokens(rows["idp"]["next_required_step"], "one-wider", "commercialization", "blocked")
