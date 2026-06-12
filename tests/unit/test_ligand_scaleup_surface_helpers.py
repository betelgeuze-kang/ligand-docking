from __future__ import annotations

from tools.product.ligand_scaleup_surface_helpers import summarize_ligand_scaleup_blocker


def test_summarize_ligand_scaleup_blocker_uses_gpcr_frontier_recovery() -> None:
    payload = summarize_ligand_scaleup_blocker(
        {
            "summary": {
                "suite_count": 3,
                "ready_suite_count": 2,
                "comparison_ready_suite_count": 2,
                "commercialization_ready_suite_count": 0,
                "pending_suite_ids": ["equal_size_ab", "pilot_100k", "pilot_1m"],
            }
        },
        {
            "benchmark_stage": "post_run_comparison",
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "recommended_next_action": "rerun GPCR 100k comparison",
        },
        {
            "summary": {
                "claim_safe": True,
                "claim_safe_status": "guardrail_recovered_candidate_available",
                "top_candidate_id": "family_balanced100k_r1",
                "packet_artifact": "runs/gpcr_scaleup_guardrail_frontier_packet_current.md",
                "next_required_step": "promote the family-balanced recovery candidate",
            }
        },
    )

    assert payload["ligand_scaleup_claim_safe"] is True
    assert payload["ligand_scaleup_claim_safe_status"] == "guardrail_recovered_candidate_available"
    assert payload["ligand_scaleup_blocked"] is True
    assert payload["ligand_scaleup_gpcr_guardrail_frontier_ready"] is True
    assert payload["ligand_scaleup_gpcr_guardrail_frontier_top_candidate_id"] == "family_balanced100k_r1"
    assert "family_balanced100k_r1" in payload["ligand_scaleup_blocker_signal"]
    assert payload["ligand_scaleup_recommended_next_action"] == "promote the family-balanced recovery candidate"
