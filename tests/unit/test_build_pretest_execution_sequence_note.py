from __future__ import annotations

from tools import build_pretest_execution_sequence_note as mod


def test_build_pretest_execution_sequence_note() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "family": "transporter",
                    "safe_scope_now": "manual_review_only_draft_packets",
                    "blocked_scope": "authoritative_apply_and_donor_reopen",
                    "operator_status": "blocked_manual_review_only",
                    "next_safe_experiment": "manual review only",
                    "source_artifact": "runs/transporter_manual_review_dashboard_current.md",
                },
                {
                    "family": "gpcr",
                    "safe_scope_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                    "blocked_scope": "100k_router_promotion",
                    "operator_status": "ready_endpoint_only",
                    "next_safe_experiment": "locked-decoy variant only",
                    "source_artifact": "runs/gpcr_handoff_bundle_current.md",
                },
                {
                    "family": "idp",
                    "safe_scope_now": "controlled_shadow_only_commercial_pretest",
                    "blocked_scope": "broader_full_idp_promotion",
                    "operator_status": "subset_safe_controlled_pretest_ready",
                    "next_safe_experiment": "expand controlled shadow-only slice",
                    "source_artifact": "runs/idp_commercial_pretest_packet_current.md",
                },
                {
                    "family": "non_kinase_enzyme_ca2",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "blocked_scope": "remaining_negative_like_rows",
                    "operator_status": "partial_authoritative_only",
                    "next_safe_experiment": "fill CA2 remaining rows",
                    "source_artifact": "runs/ca2_packet_replacement_readiness_current.md",
                },
                {
                    "family": "nuclear_receptor_pxr",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "blocked_scope": "remaining_unresolved_pending_rows",
                    "operator_status": "partial_authoritative_only",
                    "next_safe_experiment": "keep unresolved PXR rows deferred",
                    "source_artifact": "runs/pxr_pending_policy_note_current.md",
                },
            ]
        }
    )
    assert payload["summary"]["sequence_count"] == 5
    assert payload["summary"]["run_now_count"] == 2
    assert payload["summary"]["partial_prep_count"] == 2
    assert payload["summary"]["later_blocked_count"] == 1
    assert payload["rows"][0]["family"] == "gpcr"
    assert payload["rows"][0]["execution_lane"] == "run_now"
    assert payload["rows"][-1]["family"] == "transporter"
    assert payload["rows"][-1]["execution_lane"] == "later_blocked"
