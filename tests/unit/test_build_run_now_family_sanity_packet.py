from __future__ import annotations

from tools import build_run_now_family_sanity_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_run_now_family_sanity_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "family": "gpcr",
                    "execution_lane": "run_now",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "blocked_scope": "100k_router_promotion",
                },
                {
                    "family": "idp",
                    "execution_lane": "run_now",
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
                    "do_not_do": "Do not broaden beyond the controlled shadow-only commercial-pretest scope or enable ranking/gate override.",
                },
            ]
        },
        {
            "summary": {
                "next_required_step": "Use GPCR apply-safe endpoint only.",
            }
        },
        {
            "summary": {
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
                {"family": "ion_channel"},
                {"family": "kinase"},
            ],
        },
        {
            "rows": [
                {
                    "family": "ion_channel",
                    "next_required_step": "Keep ion_channel in conservative noop shadow mode.",
                },
                {
                    "family": "kinase",
                    "next_required_step": "Keep kinase in conservative noop shadow mode.",
                },
            ]
        },
    )
    assert payload["summary"]["family_count"] == 4
    assert payload["summary"]["run_now_family_count"] == 2
    assert payload["summary"]["measured_noop_family_count"] == 2
    assert payload["summary"]["ion_kinase_decision"] == "keep_shadow_noop_contract_for_ion_kinase"
    assert payload["rows"][0]["family"] == "gpcr"
    assert payload["rows"][1]["family"] == "ion_channel"
    assert payload["rows"][1]["artifact_check_command"] == "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md"
    assert "non-noop" in payload["rows"][1]["do_not_do"]
    assert payload["rows"][3]["family"] == "idp"
    _contains_tokens(payload["rows"][3]["operator_note"], "broader", "promotion", "blocked")
