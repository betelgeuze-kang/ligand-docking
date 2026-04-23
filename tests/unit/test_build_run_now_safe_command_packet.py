from __future__ import annotations

from tools import build_run_now_safe_command_packet as mod


def test_build_run_now_safe_command_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "family": "gpcr",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "blocked_scope": "100k_router_promotion",
                    "operator_status": "ready_endpoint_only",
                    "next_safe_experiment": "locked-decoy variant only",
                    "primary_handoff_note": "Use apply-safe endpoint only.",
                    "source_artifact": "runs/gpcr_handoff_bundle_current.md",
                },
                {
                    "family": "idp",
                    "safe_scope_now": "controlled_shadow_only_commercial_pretest",
                    "blocked_scope": "broader_full_idp_promotion",
                    "operator_status": "subset_safe_controlled_pretest_ready",
                    "next_safe_experiment": "next controlled anchor-backed shadow-only slice",
                    "primary_handoff_note": "Keep broader promotion blocked.",
                    "source_artifact": "runs/idp_commercial_pretest_packet_current.md",
                },
            ]
        },
        {
            "rows": [
                {
                    "family": "gpcr",
                    "execution_lane": "run_now",
                    "artifact_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "blocked_scope": "100k_router_promotion",
                    "do_not_do": "Do not launch any 100k/router GPCR run.",
                    "next_action": "locked-decoy variant only",
                    "source_artifact": "runs/gpcr_handoff_bundle_current.md",
                },
                {
                    "family": "idp",
                    "execution_lane": "run_now",
                    "artifact_check_command": "sed -n '1,200p' runs/idp_commercial_pretest_packet_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/idp_pretest_scope_note_current.md && printf '\\n---\\n' && sed -n '1,160p' runs/idp_broader_promotion_blocker_note_current.md",
                    "safe_scope_now": "controlled_shadow_only_commercial_pretest",
                    "blocked_scope": "broader_full_idp_promotion",
                    "do_not_do": "Do not broaden beyond the controlled shadow-only commercial-pretest scope or enable ranking/gate override.",
                    "next_action": "controlled anchor-backed shadow-only slice",
                    "source_artifact": "runs/idp_commercial_pretest_packet_current.md",
                },
                {
                    "family": "transporter",
                    "execution_lane": "later_blocked",
                },
            ]
        },
    )

    summary = payload["summary"]
    assert summary["run_now_family_count"] == 2
    assert summary["bounded_family_count"] == 2
    assert summary["guardrail_count"] == 2
    assert summary["families"] == ["gpcr", "idp"]

    rows = payload["rows"]
    assert rows[0]["family"] == "gpcr"
    assert rows[0]["operator_status"] == "ready_endpoint_only"
    assert rows[1]["family"] == "idp"
    assert rows[1]["blocked_scope"] == "broader_full_idp_promotion"
