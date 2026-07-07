from __future__ import annotations

from betelgeuze_product.docking_response import docking_claim_summary, proxy_score_contract


def test_proxy_score_contract_uses_customer_safe_name() -> None:
    contract = proxy_score_contract()

    assert contract["customer_score_name"] == "proxy_binding_energy_score"
    assert contract["method_kind"] == "heuristic_proxy"
    assert "true_mm_pbsa" in contract["not_claimed_as"]
    assert "experimental_delta_g" in contract["not_claimed_as"]
    assert all(name.endswith("_proxy") or name == "binding_energy_proxy" for name in contract["internal_proxy_columns"])


def test_docking_claim_summary_embeds_proxy_score_contract() -> None:
    summary = docking_claim_summary(
        {
            "scope_claim_status": "allowed_restricted_delivery_scope",
            "scope_claim_allowed_for_request": True,
            "general_platform_claim_allowed": False,
            "production_ai_promotion_allowed": False,
            "docking_results_emitted": False,
            "claim_boundary": "restricted",
        }
    )

    assert summary["score_contract"]["customer_score_name"] == "proxy_binding_energy_score"
    assert summary["score_contract"]["method_kind"] == "heuristic_proxy"
    assert summary["customer_pose_emission_allowed"] is False
