from __future__ import annotations

from tools import build_run_now_family_operator_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_run_now_family_operator_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "family": "gpcr",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "blocked_scope": "100k_router_promotion",
                },
                {
                    "family": "idp",
                    "safe_scope_now": "controlled_shadow_only_commercial_pretest",
                    "blocked_scope": "broader_full_idp_promotion",
                },
            ]
        },
        {
            "rows": [
                {
                    "family": "gpcr",
                    "artifact_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md",
                    "do_not_do": "Do not launch any 100k/router GPCR run.",
                },
                {
                    "family": "idp",
                    "artifact_check_command": "sed -n '1,200p' runs/idp_commercial_pretest_packet_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/idp_pretest_scope_note_current.md && printf '\\n---\\n' && sed -n '1,160p' runs/idp_broader_promotion_blocker_note_current.md",
                    "do_not_do": "Do not broaden beyond literature-anchor subset or enable ranking/gate override.",
                },
            ]
        },
        {
            "summary": {
                "next_required_step": "Stay inside the GPCR apply-safe endpoint scope.",
            }
        },
        {
            "summary": {
                "default_feature_mask": "rg_sasa_only",
                "core_target_count": 4,
                "watchlist_target_count": 3,
            }
        },
        {},
        {},
        {
            "summary": {
                "default_feature_mask": "rg_sasa_only",
                "guardrail": "Require zero state/gate changes.",
            }
        },
        {
            "summary": {
                "next_required_step": "Keep broader promotion blocked.",
            }
        },
        {
            "summary": {
                "decision": "keep_shadow_noop_contract_for_ion_kinase",
            },
            "family_rows": [
                {
                    "family": "ion_channel",
                    "completed_candidate_tasks": 2,
                    "task_count": 2,
                    "max_abs_delta_pr_auc": 0.001,
                },
                {
                    "family": "kinase",
                    "completed_candidate_tasks": 2,
                    "task_count": 2,
                    "max_abs_delta_pr_auc": 0.0,
                },
            ],
        },
    )
    assert payload["summary"]["family_count"] == 4
    assert payload["summary"]["run_now_packet_count"] == 2
    assert payload["summary"]["measured_noop_packet_count"] == 2
    assert payload["summary"]["ion_kinase_decision"] == "keep_shadow_noop_contract_for_ion_kinase"
    assert payload["rows"][0]["family"] == "gpcr"
    assert "100k/router GPCR" in payload["rows"][0]["no_go_rule"]
    assert payload["rows"][1]["family"] == "ion_channel"
    assert payload["rows"][1]["safe_scope_now"] == "measured_noop_shadow_family"
    assert payload["rows"][2]["family"] == "kinase"
    assert "completed_tasks=2/2" in payload["rows"][2]["operator_handoff"]
    assert payload["rows"][3]["family"] == "idp"
    _contains_tokens(payload["rows"][3]["no_go_rule"], "controlled", "shadow-only", "commercial-pretest", "ranking/gate", "override")
    assert "rg_sasa_only" in payload["rows"][3]["operator_handoff"]
    assert "core=4" in payload["rows"][3]["operator_handoff"]
    assert payload["rows"][3]["artifact_check_command"] == "sed -n '1,220p' runs/idp_commercial_pretest_packet_current.md"
    assert payload["rows"][3]["source_artifact"] == "runs/idp_commercial_pretest_packet_current.md"


def test_build_run_now_family_operator_packet_prefers_idp_decision_artifact() -> None:
    payload = mod.build_payload(
        {"rows": [{"family": "gpcr", "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint", "blocked_scope": "100k_router_promotion"}, {"family": "idp", "safe_scope_now": "controlled_shadow_only_commercial_pretest", "blocked_scope": "broader_full_idp_promotion"}]},
        {"rows": [{"family": "gpcr", "artifact_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md", "guardrail_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md", "do_not_do": "Do not launch any 100k/router GPCR run."}, {"family": "idp", "artifact_check_command": "sed -n '1,200p' runs/idp_commercial_pretest_packet_current.md", "guardrail_check_command": "sed -n '1,200p' runs/idp_pretest_scope_note_current.md && printf '\\n---\\n' && sed -n '1,160p' runs/idp_broader_promotion_blocker_note_current.md", "do_not_do": "Do not broaden beyond literature-anchor subset or enable ranking/gate override."}]},
        {"summary": {"next_required_step": "Stay inside the GPCR apply-safe endpoint scope."}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "core_target_count": 4, "watchlist_target_count": 3}},
        {
            "summary": {
                "broader_shadow_passed": True,
                "shadow_safe_retained": True,
                "corrected_pass_folds": 8,
                "fold_count": 8,
                "page4_fold_pass": True,
                "tau_k18_fold_pass": True,
                "default_feature_mask": "rg_sasa_only",
                "next_required_step": "reopen explicit promotion review using the completed broader-shadow result",
            }
        },
        {"summary": {"true_broader_shadow_passed": True}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "guardrail": "Require zero state/gate changes."}},
        {"summary": {"next_required_step": "Keep broader promotion blocked."}},
        {"summary": {"decision": "keep_shadow_noop_contract_for_ion_kinase"}, "family_rows": [{"family": "ion_channel", "completed_candidate_tasks": 2, "task_count": 2, "max_abs_delta_pr_auc": 0.001}, {"family": "kinase", "completed_candidate_tasks": 2, "task_count": 2, "max_abs_delta_pr_auc": 0.0}]},
        {"summary": {"shadow_safe_retained": True, "default_feature_mask": "rg_sasa_only", "next_required_step": "route follow-up work through tau_k18 corrected-path stabilization"}},
    )
    idp_row = payload["rows"][3]
    assert idp_row["artifact_check_command"] == "sed -n '1,220p' runs/idp_broader_shadow_decision_current.md"
    assert idp_row["source_artifact"] == "runs/idp_broader_shadow_decision_current.md"
    assert "shadow_safe=True" in idp_row["operator_handoff"]
    assert "broader_shadow_passed=True" in idp_row["operator_handoff"]
    assert "page4_fold_pass=True" in idp_row["operator_handoff"]
    assert "tau_k18_fold_pass=True" in idp_row["operator_handoff"]


def test_build_run_now_family_operator_packet_prefers_broader_promotion_resolution() -> None:
    payload = mod.build_payload(
        {"rows": [{"family": "gpcr", "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint", "blocked_scope": "100k_router_promotion"}, {"family": "idp", "safe_scope_now": "one_wider_shadow_safe_lane_only", "blocked_scope": "broader_full_idp_promotion"}]},
        {"rows": [{"family": "gpcr", "artifact_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md", "guardrail_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md", "do_not_do": "Do not launch any 100k/router GPCR run."}, {"family": "idp", "artifact_check_command": "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md", "guardrail_check_command": "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_broader_shadow_result_current.md", "do_not_do": "Do not broaden beyond the admitted one-wider shadow-safe lane."}]},
        {"summary": {"next_required_step": "Stay inside the GPCR apply-safe endpoint scope."}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "core_target_count": 4, "watchlist_target_count": 3}},
        {"summary": {"broader_shadow_passed": True, "shadow_safe_retained": True, "corrected_pass_folds": 8, "fold_count": 8, "page4_fold_pass": True, "tau_k18_fold_pass": True, "default_feature_mask": "rg_sasa_only", "next_required_step": "reopen explicit promotion review using the completed broader-shadow result"}},
        {"summary": {"true_broader_shadow_passed": True}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "guardrail": "Require zero state/gate changes."}},
        {"summary": {"next_required_step": "Keep broader promotion blocked."}},
        {"summary": {"decision": "keep_shadow_noop_contract_for_ion_kinase"}, "family_rows": [{"family": "ion_channel", "completed_candidate_tasks": 2, "task_count": 2, "max_abs_delta_pr_auc": 0.001}, {"family": "kinase", "completed_candidate_tasks": 2, "task_count": 2, "max_abs_delta_pr_auc": 0.0}]},
        {"summary": {"shadow_safe_retained": True, "default_feature_mask": "rg_sasa_only", "next_required_step": "route follow-up work through tau_k18 corrected-path stabilization"}},
        {"summary": {"decision": "one_wider_shadow_safe_lane_admitted", "wider_shadow_safe_lane_admitted": True, "frozen_total_target_count": 8, "page4_fold_pass": True, "tau_k18_fold_pass": True, "next_required_step": "run only the admitted one-wider shadow-safe lane"}},
    )
    idp_row = payload["rows"][3]
    assert idp_row["operator_lane"] == "run_now_one_wider_shadow_safe"
    assert idp_row["safe_scope_now"] == "one_wider_shadow_safe_lane_only"
    assert idp_row["artifact_check_command"] == "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md"
    assert idp_row["source_artifact"] == "runs/idp_broader_promotion_resolution_current.md"
    assert "wider_lane_admitted=True" in idp_row["operator_handoff"]
    assert "frozen_total_targets=8" in idp_row["operator_handoff"]


def test_build_run_now_family_operator_packet_prefers_repeatability_packet_after_resolution() -> None:
    payload = mod.build_payload(
        {"rows": [{"family": "gpcr", "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint", "blocked_scope": "100k_router_promotion"}, {"family": "idp", "safe_scope_now": "one_wider_shadow_safe_lane_only", "blocked_scope": "broader_full_idp_promotion"}]},
        {"rows": [{"family": "gpcr", "artifact_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md", "guardrail_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md", "do_not_do": "Do not launch any 100k/router GPCR run."}, {"family": "idp", "artifact_check_command": "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md", "guardrail_check_command": "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_broader_shadow_result_current.md", "do_not_do": "Do not broaden beyond the admitted one-wider shadow-safe lane."}]},
        {"summary": {"next_required_step": "Stay inside the GPCR apply-safe endpoint scope."}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "core_target_count": 4, "watchlist_target_count": 3}},
        {"summary": {"broader_shadow_passed": True, "shadow_safe_retained": True, "corrected_pass_folds": 8, "fold_count": 8, "page4_fold_pass": True, "tau_k18_fold_pass": True, "default_feature_mask": "rg_sasa_only"}},
        {"summary": {"true_broader_shadow_passed": True}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "guardrail": "Require zero state/gate changes."}},
        {"summary": {"next_required_step": "Keep broader promotion blocked."}},
        {"summary": {"decision": "keep_shadow_noop_contract_for_ion_kinase"}, "family_rows": [{"family": "ion_channel", "completed_candidate_tasks": 2, "task_count": 2, "max_abs_delta_pr_auc": 0.001}, {"family": "kinase", "completed_candidate_tasks": 2, "task_count": 2, "max_abs_delta_pr_auc": 0.0}]},
        {},
        {"summary": {"decision": "one_wider_shadow_safe_lane_admitted", "wider_shadow_safe_lane_admitted": True, "frozen_total_target_count": 8, "page4_fold_pass": True, "tau_k18_fold_pass": True, "next_required_step": "run only the admitted one-wider shadow-safe lane"}},
        {"summary": {"status": "one_wider_shadow_repeatability_packet_ready", "next_required_step": "launch repeatability rerun"}},
    )
    idp_row = payload["rows"][3]
    assert "idp_one_wider_shadow_repeatability_packet_current.md" in idp_row["source_artifact"]
    assert "idp_one_wider_shadow_repeatability_packet_current.md" in idp_row["artifact_check_command"]
    assert "repeatability_status=one_wider_shadow_repeatability_packet_ready" in idp_row["operator_handoff"]
