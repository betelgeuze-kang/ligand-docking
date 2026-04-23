from __future__ import annotations

from tools import build_pretest_command_checklist as mod


def test_build_pretest_command_checklist() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "sequence_order": 1,
                    "family": "gpcr",
                    "execution_lane": "run_now",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "blocked_scope": "100k_router_promotion",
                    "next_action": "locked-decoy variant only",
                    "source_artifact": "runs/gpcr_handoff_bundle_current.md",
                },
                {
                    "sequence_order": 5,
                    "family": "transporter",
                    "execution_lane": "later_blocked",
                    "safe_scope_now": "manual_review_only_draft_packets",
                    "blocked_scope": "authoritative_apply_and_donor_reopen",
                    "next_action": "manual review only",
                    "source_artifact": "runs/transporter_manual_review_dashboard_current.md",
                },
            ]
        }
    )
    assert payload["summary"]["check_count"] == 2
    assert payload["summary"]["run_now_check_count"] == 1
    assert payload["summary"]["later_blocked_check_count"] == 1
    assert payload["rows"][0]["artifact_check_command"] == "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md"
    assert "100k/router" in payload["rows"][0]["do_not_do"]
    assert "transporter_manual_verdict_packets_current.md" in payload["rows"][1]["guardrail_check_command"]


def test_build_pretest_command_checklist_prefers_idp_broader_shadow_artifacts() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "sequence_order": 4,
                    "family": "idp",
                    "execution_lane": "run_now",
                    "safe_scope_now": "controlled_shadow_only_commercial_pretest",
                    "blocked_scope": "broader_full_idp_promotion",
                    "next_action": "reopen promotion review",
                    "source_artifact": "runs/idp_broader_shadow_decision_current.md",
                }
            ]
        }
    )
    row = payload["rows"][0]
    assert row["guardrail_check_command"] == "sed -n '1,220p' runs/idp_broader_shadow_decision_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_broader_shadow_result_current.md"
