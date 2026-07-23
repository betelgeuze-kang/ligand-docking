from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline.s0_production_evidence_bundle import (
    FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256,
    S0FinalReviewerTrustAnchor,
    S0ProductionEvidenceBundleError,
    require_s0_production_evidence_bundle_contract_document,
    s0_production_evidence_bundle_contract_decision,
    s0_production_evidence_bundle_contract_document,
)


def test_s0_bundle_contract_is_frozen_and_narrowly_scoped() -> None:
    contract = s0_production_evidence_bundle_contract_document()

    assert (
        contract["contract_sha256"]
        == FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256
        == "549fbdb865704a84df4ecb525f4ea27a7c5ab8526f7f1be0b0f666cd9c6fd08d"
    )
    assert require_s0_production_evidence_bundle_contract_document(contract) == contract
    assert contract["host_policy"]["required_host_count"] == 2
    assert contract["host_policy"]["energy_force_physics_projection_exactly_equal"]
    assert contract["host_policy"]["minimization_physics_projection_exactly_equal"]
    assert contract["host_policy"][
        "native_minimization_physics_projection_exactly_equal"
    ]
    assert contract["host_policy"][
        "both_native_endpoint_health_dispositions_must_be_accepted"
    ]
    assert contract["host_policy"][
        "accepted_host_failure_disposition_must_be_not_applicable"
    ]
    assert contract["host_policy"][
        "failure_disposition_completion_cannot_substitute_for_native_endpoint_acceptance"
    ]
    assert contract["final_review_policy"]["algorithm"] == "ed25519"
    assert (
        contract["final_review_policy"][
            "secret_free_detached_signing_request_supported"
        ]
        is True
    )
    assert (
        contract["final_review_policy"][
            "private_key_forbidden_in_signing_request_and_cli"
        ]
        is True
    )
    assert contract["accepted_bundle_policy"]["s0_accepted"] is True
    assert contract["accepted_bundle_policy"]["s1_admission_authorized"] is True
    for field in (
        "scientifically_validated",
        "chemical_applicability_validated",
        "validated_refinement_claim_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert contract["accepted_bundle_policy"][field] is False


def test_static_contract_decision_has_no_evidence_or_promotion() -> None:
    decision = s0_production_evidence_bundle_contract_decision()

    assert decision["bundle_contract_implemented"] is True
    assert decision["two_host_evidence_present"] is False
    assert decision["final_human_approval_present"] is False
    assert decision["two_cpu_host_reproducibility_verified"] is False
    assert decision["production_validation_evidence"] is False
    assert decision["s0_accepted"] is False
    assert decision["s1_admission_authorized"] is False
    assert decision["scientifically_validated"] is False
    assert decision["claim_safe"] is False
    assert "final_independent_human_s0_approval_not_provisioned" in decision["blockers"]


def test_contract_rejects_drift_and_bad_final_trust_material() -> None:
    contract = json.loads(json.dumps(s0_production_evidence_bundle_contract_document()))
    contract["accepted_bundle_policy"]["scientifically_validated"] = True
    with pytest.raises(S0ProductionEvidenceBundleError):
        require_s0_production_evidence_bundle_contract_document(contract)
    with pytest.raises(S0ProductionEvidenceBundleError):
        S0FinalReviewerTrustAnchor("0" * 63, b"x" * 32)
    with pytest.raises(S0ProductionEvidenceBundleError):
        S0FinalReviewerTrustAnchor("0" * 64, b"x" * 31)


def test_s0_bundle_import_does_not_load_optional_openmm_runtime() -> None:
    source = (
        "import sys;"
        "import betelgeuze_engine_v2.offline.s0_production_evidence_bundle;"
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


def test_source_freshly_reverifies_hosts_and_enforces_cross_host_equality() -> None:
    source = Path(
        "betelgeuze_engine_v2/offline/s0_production_evidence_bundle.py"
    ).read_text(encoding="utf-8")

    assert "verify_signed_openmm_reference_result_review_attestation" in source
    assert "_verify_host_evidence(item, checked_at=checked_at)" in source
    assert "len(host_evidence) != S0_PRODUCTION_EVIDENCE_BUNDLE_HOST_COUNT" in source
    assert "host-to-host {field_name} equality failed" in source
    assert "host-to-host {field_name} identities must be distinct" in source
    assert (
        "S0 host result review does not have accepted native endpoint health" in source
    )
    assert "final S0 reviewer must be distinct from every nested role" in source
    assert "verify_ed25519" in source
    assert '"signing-bytes"' in source
    assert '"attach-signature"' in source
    assert '"--private-key"' not in source
