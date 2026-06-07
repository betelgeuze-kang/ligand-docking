from __future__ import annotations

from tools.product import build_transporter_fit_donor_policy_decision as mod


def test_build_transporter_fit_donor_policy_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"endpoint_status": "draft_only_local_evidence_blocked", "temporary_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"endpoint_status": "draft_only_local_evidence_blocked", "temporary_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"p0_open_count": 9}},
    )
    assert payload["summary"]["decision_status"] == "scaffold_default_keep_existing_fit_donor_pool"
    assert payload["summary"]["scaffold_fit_donor_target"] == "EGFR_KINASE"
    assert payload["summary"]["scaffold_policy_frozen"] is True
    assert payload["summary"]["claim_bearing_policy_frozen"] is False
