from __future__ import annotations

from tools import build_family_readiness_heatmap as mod


def test_build_family_readiness_heatmap() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "family": "gpcr",
                    "commercialization_score": 82,
                    "current_state": "endpoint",
                    "runtime_scope_now": "locked_decoy_apply_safe_endpoint_only",
                    "pretest_ready": "yes",
                    "claim_safe_test_ready": "yes",
                    "primary_blocker": "100k_router_still_blocked",
                    "next_required_step": "keep endpoint",
                },
                {
                    "family": "non_kinase_enzyme_ca2",
                    "commercialization_score": 58,
                    "current_state": "prep",
                    "runtime_scope_now": "authoritative_partial_rows_only",
                    "pretest_ready": "partial",
                    "claim_safe_test_ready": "no",
                    "primary_blocker": "replacement_reference_binding_kcal_mol",
                    "next_required_step": "fill ca2",
                },
                {
                    "family": "transporter",
                    "commercialization_score": 32,
                    "current_state": "manual",
                    "runtime_scope_now": "manual_review_only_draft_packets",
                    "pretest_ready": "no",
                    "claim_safe_test_ready": "no",
                    "primary_blocker": "local_evidence_and_donor_policy_blocked",
                    "next_required_step": "keep manual review",
                },
            ]
        },
        {
            "rows": [
                {
                    "family": "gpcr",
                    "score": 82,
                    "claim_safe_scope": "locked-decoy equal-size shadow/apply endpoint",
                    "primary_blocker": "tiny residual chembl50 PR regression",
                },
                {
                    "family": "non_kinase_enzyme_ca2",
                    "score": 58,
                    "claim_safe_scope": "authoritative-ready rows 6/12",
                    "primary_blocker": "negative evidence missing",
                },
                {
                    "family": "transporter",
                    "score": 32,
                    "claim_safe_scope": "draft/manual-review only",
                    "primary_blocker": "no authoritative transporter packet rows",
                },
            ]
        },
        {
            "rows": [
                {"family": "gpcr", "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked"},
                {"family": "non_kinase_enzyme_ca2", "current_state": "binding_verification_in_progress"},
                {"family": "transporter", "current_state": "draft_packet_external_seeded_local_evidence_blocked"},
            ]
        },
    )

    assert payload["summary"]["family_count"] == 3
    assert payload["summary"]["run_now_count"] == 1
    assert payload["summary"]["prep_count"] == 1
    assert payload["summary"]["manual_review_count"] == 1
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["gpcr"]["heat_bucket"] == "run-now"
    assert rows["gpcr"]["blocked_subscope"] == "100k_router"
    assert rows["non_kinase_enzyme_ca2"]["heat_bucket"] == "prep"
    assert rows["transporter"]["heat_bucket"] == "manual-review"
