from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline.openmm_reference_result_review import (
    FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256,
    OpenMMReferenceResultReviewError,
    OpenMMReferenceResultReviewerTrustAnchor,
    openmm_reference_result_review_contract_decision,
    openmm_reference_result_review_contract_document,
    require_openmm_reference_result_review_contract_document,
)


def test_result_review_contract_is_frozen_and_claim_closed() -> None:
    contract = openmm_reference_result_review_contract_document()
    assert (
        contract["contract_sha256"]
        == FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256
        == "8481d89bd4d3593fd220d0fc42cd3c3a09462a50cb7f65321ef7c5a1b6aa9b47"
    )
    assert (
        require_openmm_reference_result_review_contract_document(contract) == contract
    )
    assert contract["required_nested_outcomes"] == {
        "energy_force_result_review_accepted": True,
        "minimization_result_review_accepted": True,
        "openmm_energy_force_status": "accepted_offline_reference_agreement",
        "openmm_minimization_status": "accepted_offline_reference_trace_agreement",
        "energy_force_case_count": 27,
        "energy_force_variant_count": 59,
        "minimization_case_count": 14,
        "all_failure_rows_retained": True,
    }
    assert contract["signature_policy"]["algorithm"] == "ed25519"
    assert (
        contract["claim_policy"][
            "single_host_external_oracle_comparison_may_be_verified"
        ]
        is True
    )
    for field in (
        "production_validation_evidence",
        "scientifically_validated",
        "s0_admission_authorized",
        "s1_admission_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "claim_safe",
    ):
        assert contract["claim_policy"][field] is False


def test_contract_decision_has_no_bundled_evidence_or_promotion() -> None:
    decision = openmm_reference_result_review_contract_decision()
    assert decision["result_review_contract_implemented"] is True
    assert decision["signed_result_review_attestation_present"] is False
    assert decision["external_oracle_comparison_verified"] is False
    assert decision["production_validation_evidence"] is False
    assert decision["scientifically_validated"] is False
    assert decision["s0_admission_authorized"] is False
    assert decision["s1_admission_authorized"] is False
    assert decision["claim_safe"] is False
    assert "two_distinct_cpu_host_attestations_missing" in decision["blockers"]
    assert "final_independent_human_s0_approval_missing" in decision["blockers"]


def test_contract_rejects_drift_and_trust_anchor_rejects_bad_material() -> None:
    contract = openmm_reference_result_review_contract_document()
    drifted = json.loads(json.dumps(contract))
    drifted["claim_policy"]["s0_admission_authorized"] = True
    with pytest.raises(OpenMMReferenceResultReviewError):
        require_openmm_reference_result_review_contract_document(drifted)
    with pytest.raises(OpenMMReferenceResultReviewError):
        OpenMMReferenceResultReviewerTrustAnchor("0" * 63, b"x" * 32)
    with pytest.raises(OpenMMReferenceResultReviewError):
        OpenMMReferenceResultReviewerTrustAnchor("0" * 64, b"x" * 31)


def test_offline_review_import_does_not_load_openmm_runtime() -> None:
    source = (
        "import sys;"
        "import betelgeuze_engine_v2.offline.openmm_reference_result_review;"
        "assert 'openmm' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_source_contains_fresh_nested_verification_and_exact_crosschecks() -> None:
    source = Path(
        "betelgeuze_engine_v2/offline/openmm_reference_result_review.py"
    ).read_text(encoding="utf-8")
    assert "verify_signed_reference_validation_result_review_attestation" in source
    assert (
        "verify_signed_reference_minimization_validation_result_review_attestation"
        in source
    )
    assert "require_openmm_reference_energy_force_receipt" in source
    assert "require_openmm_reference_minimization_trace_receipt" in source
    assert "_crosscheck_energy_force_outputs" in source
    assert "_crosscheck_minimization_traces" in source
    assert "external result reviewer must be distinct from every nested role" in source
