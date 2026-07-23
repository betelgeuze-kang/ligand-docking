from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import betelgeuze_engine_v2.offline.s0_production_evidence_bundle as s0_bundle_module
from betelgeuze_engine_v2.offline.openmm_reference_fixed_born_disposition import (
    FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256,
)
from betelgeuze_engine_v2.offline.openmm_reference_result_review import (
    EnergyForceResultReviewEvidence,
    MinimizationResultReviewEvidence,
    OpenMMReferenceResultReviewVerification,
)
from betelgeuze_engine_v2.offline.s0_production_evidence_bundle import (
    S0FinalReviewerTrustAnchor,
    S0HostEvidence,
    S0ProductionEvidenceBundleError,
    attach_s0_production_evidence_bundle_approval_signature,
    build_s0_production_evidence_bundle_approval_signing_request,
    build_signed_s0_production_evidence_bundle_approval,
    main,
    require_s0_production_evidence_bundle_approval_signing_request,
    s0_production_evidence_bundle_approval_signing_bytes,
    verify_signed_s0_production_evidence_bundle_approval,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)


HOST_REVIEWED_AT = datetime(2026, 7, 22, 10, 0, 0, tzinfo=timezone.utc)
HOST_EXPIRES_AT = HOST_REVIEWED_AT + timedelta(days=10)
FINAL_REVIEWED_AT = HOST_REVIEWED_AT + timedelta(hours=2)
FINAL_EXPIRES_AT = HOST_REVIEWED_AT + timedelta(days=8)
CHECKED_AT = HOST_REVIEWED_AT + timedelta(days=1)
FINAL_REVIEWER_IDENTITY = hashlib.sha256(b"final-reviewer").hexdigest()
FINAL_REVIEWER_KEY_ID = "test-final-s0-reviewer"
FINAL_REVIEWER_KEY = bytes.fromhex("71" * 32)
FINAL_REVIEWER_PUBLIC_KEY = ed25519_public_key_bytes(FINAL_REVIEWER_KEY)
FINAL_NONCE = hashlib.sha256(b"final-nonce").hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _host_verification(index: int) -> OpenMMReferenceResultReviewVerification:
    def unique(label: str) -> str:
        return _digest(f"host-{index}:{label}")

    def role(label: str) -> str:
        return _digest(f"role-{index}:{label}")

    return OpenMMReferenceResultReviewVerification(
        contract_sha256=_digest("host-review-contract"),
        attestation_sha256=unique("attestation"),
        enrolled_host_identity_sha256=unique("host"),
        cpu_identity_sha256=unique("cpu"),
        production_evidence_session_sha256=unique("session"),
        custody_terminal_sha256=unique("custody"),
        energy_force_result_receipt_sha256=unique("energy-result"),
        energy_force_result_review_attestation_sha256=unique("energy-review"),
        minimization_result_receipt_sha256=unique("min-result"),
        minimization_result_review_attestation_sha256=unique("min-review"),
        openmm_energy_force_receipt_sha256=unique("openmm-energy"),
        openmm_minimization_trace_receipt_sha256=unique("openmm-min"),
        openmm_reference_materialization_sha256=unique("openmm-materialization"),
        openmm_native_minimization_receipt_sha256=unique("openmm-native"),
        openmm_fixed_born_disposition_receipt_sha256=None,
        energy_force_physics_projection_sha256=_digest("energy-physics"),
        minimization_physics_projection_sha256=_digest("min-physics"),
        native_minimization_physics_projection_sha256=_digest("native-physics"),
        fixed_born_disposition_physics_projection_sha256=None,
        energy_force_source_manifest_sha256=_digest("energy-source"),
        minimization_source_manifest_sha256=_digest("min-source"),
        energy_force_execution_environment_receipt_sha256=unique("energy-env"),
        minimization_execution_environment_receipt_sha256=unique("min-env"),
        openmm_runtime_identity_sha256=_digest("openmm-runtime"),
        openmm_source_identity_sha256=_digest("openmm-source"),
        native_minimization_configuration_sha256=_digest("native-config"),
        fixed_born_disposition_configuration_sha256=None,
        code_commit_sha="a" * 40,
        dependency_rows_sha256=_digest("dependencies"),
        seed=20260722,
        energy_force_authorization_nonce_sha256=unique("energy-auth-nonce"),
        minimization_authorization_nonce_sha256=unique("min-auth-nonce"),
        nonce_sha256=unique("outer-nonce"),
        implementation_author_identity_sha256=role("author"),
        independent_scientific_reviewer_identity_sha256=role("science"),
        authorization_operator_identity_sha256=role("operator"),
        energy_force_result_reviewer_identity_sha256=role("energy-reviewer"),
        minimization_result_reviewer_identity_sha256=role("min-reviewer"),
        external_result_reviewer_identity_sha256=role("external-reviewer"),
        external_result_reviewer_key_id=f"test-host-reviewer-{index}",
        reviewed_at_utc=HOST_REVIEWED_AT.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at_utc=HOST_EXPIRES_AT.strftime("%Y-%m-%dT%H:%M:%SZ"),
        failure_inclusive_native_minimization_evidence_verified=True,
        native_minimization_status="accepted_offline_native_endpoint_comparison",
        native_endpoint_health_passed_case_count=8,
        native_endpoint_health_failed_case_ids=(),
        fixed_born_failure_disposition_required=False,
        fixed_born_failure_disposition_verified=False,
        fixed_born_failure_disposition_complete=False,
        fixed_born_failure_disposition_status=(
            "not_applicable_native_endpoint_accepted"
        ),
        fixed_born_failure_disposition_classification=None,
        external_oracle_comparison_verified=True,
        result_review_outcome="accepted",
        production_validation_evidence=False,
        scientifically_validated=False,
        s0_admission_authorized=False,
        s1_admission_authorized=False,
        claim_safe=False,
        blockers=("second_host_and_final_approval_required",),
    )


def _empty_review_evidence() -> EnergyForceResultReviewEvidence:
    return EnergyForceResultReviewEvidence(
        result_receipt={},
        result_review_attestation={},
        pre_execution_review_attestation={},
        authorization_receipt={},
        trusted_scientific_reviewer_keys={},
        trusted_authorization_operator_keys={},
        trusted_result_reviewer_keys={},
        expected_implementation_author_identity_sha256="0" * 64,
        expected_independent_scientific_reviewer_identity_sha256="1" * 64,
        expected_authorization_operator_identity_sha256="2" * 64,
    )


def _empty_minimization_evidence() -> MinimizationResultReviewEvidence:
    return MinimizationResultReviewEvidence(
        result_receipt={},
        result_review_attestation={},
        pre_execution_review_attestation={},
        authorization_receipt={},
        trusted_scientific_reviewer_keys={},
        trusted_authorization_operator_keys={},
        trusted_result_reviewer_keys={},
        expected_implementation_author_identity_sha256="0" * 64,
        expected_independent_scientific_reviewer_identity_sha256="1" * 64,
        expected_authorization_operator_identity_sha256="2" * 64,
    )


def _host_input(index: int) -> S0HostEvidence:
    return S0HostEvidence(
        result_review_attestation={},
        energy_force_evidence=_empty_review_evidence(),
        minimization_evidence=_empty_minimization_evidence(),
        openmm_energy_force_receipt={},
        openmm_minimization_trace_receipt={},
        openmm_reference_materialization={},
        openmm_native_minimization_receipt={},
        expected_openmm_reference_materialization_sha256=_digest(
            f"input-materialization-{index}"
        ),
        expected_enrolled_host_identity_sha256=_digest(f"input-host-{index}"),
        expected_cpu_identity_sha256=_digest(f"input-cpu-{index}"),
        expected_production_evidence_session_sha256=_digest(f"input-session-{index}"),
        expected_custody_terminal_sha256=_digest(f"input-custody-{index}"),
        trusted_external_result_reviewer_keys={},
        openmm_fixed_born_disposition_receipt=None,
        expected_openmm_fixed_born_disposition_receipt_sha256=None,
    )


@dataclass(frozen=True)
class _Bundle:
    host_inputs: tuple[S0HostEvidence, S0HostEvidence]
    host_verifications: tuple[
        OpenMMReferenceResultReviewVerification,
        OpenMMReferenceResultReviewVerification,
    ]
    signing_request: dict[str, Any]
    approval: dict[str, Any]


def _install_host_verifier(
    monkeypatch: pytest.MonkeyPatch,
    host_inputs: tuple[S0HostEvidence, S0HostEvidence],
    verifications: tuple[
        OpenMMReferenceResultReviewVerification,
        OpenMMReferenceResultReviewVerification,
    ],
) -> None:
    by_input_host = {
        item.expected_enrolled_host_identity_sha256: verification
        for item, verification in zip(host_inputs, verifications, strict=True)
    }

    def verify(
        evidence: S0HostEvidence, *, checked_at: datetime
    ) -> OpenMMReferenceResultReviewVerification:
        assert checked_at.tzinfo is not None
        return by_input_host[evidence.expected_enrolled_host_identity_sha256]

    monkeypatch.setattr(s0_bundle_module, "_verify_host_evidence", verify)


@pytest.fixture
def bundle(monkeypatch: pytest.MonkeyPatch) -> _Bundle:
    host_inputs = (_host_input(1), _host_input(2))
    host_verifications = (_host_verification(1), _host_verification(2))
    _install_host_verifier(monkeypatch, host_inputs, host_verifications)
    signing_request = build_s0_production_evidence_bundle_approval_signing_request(
        host_evidence=host_inputs,
        final_reviewer_identity_sha256=FINAL_REVIEWER_IDENTITY,
        final_reviewer_key_id=FINAL_REVIEWER_KEY_ID,
        reviewed_at=FINAL_REVIEWED_AT,
        expires_at=FINAL_EXPIRES_AT,
        nonce_sha256=FINAL_NONCE,
        revoked_host_review_attestation_sha256s=(),
        superseded_host_review_attestation_sha256s=(),
    )
    signature = sign_ed25519(
        s0_production_evidence_bundle_approval_signing_bytes(signing_request),
        FINAL_REVIEWER_KEY,
    )
    approval = attach_s0_production_evidence_bundle_approval_signature(
        signing_request,
        signature_hex=signature,
        verification_key=FINAL_REVIEWER_PUBLIC_KEY,
    )
    return _Bundle(host_inputs, host_verifications, signing_request, approval)


def _verify(bundle: _Bundle, source: object | None = None, **overrides: object):
    values: dict[str, object] = {
        "source": bundle.approval if source is None else source,
        "host_evidence": bundle.host_inputs,
        "trusted_final_reviewer_keys": {
            FINAL_REVIEWER_KEY_ID: S0FinalReviewerTrustAnchor(
                FINAL_REVIEWER_IDENTITY, FINAL_REVIEWER_PUBLIC_KEY
            )
        },
        "checked_at": CHECKED_AT,
        "revoked_final_reviewer_key_ids": (),
        "revoked_host_review_attestation_sha256s": (),
        "superseded_host_review_attestation_sha256s": (),
        "revoked_approval_sha256s": (),
        "superseded_approval_sha256s": (),
    }
    values.update(overrides)
    return verify_signed_s0_production_evidence_bundle_approval(  # type: ignore[arg-type]
        **values
    )


def test_signed_bundle_accepts_only_narrow_s0_and_s1_entry(bundle: _Bundle) -> None:
    verification = _verify(bundle)

    assert verification.two_cpu_host_reproducibility_verified is True
    assert verification.independent_external_implementation_comparison_verified is True
    assert verification.production_validation_evidence is True
    assert verification.s0_accepted is True
    assert verification.s1_admission_authorized is True
    assert verification.scientifically_validated is False
    assert verification.chemical_applicability_validated is False
    assert verification.validated_refinement_claim_authorized is False
    assert verification.parameter_fitting_authorized is False
    assert verification.benchmark_validated is False
    assert verification.product_qualified is False
    assert verification.customer_execution_enabled is False
    assert verification.claim_safe is False
    assert len(set(verification.enrolled_host_identity_sha256s)) == 2
    assert len(set(verification.cpu_identity_sha256s)) == 2


def test_detached_signing_request_round_trip_matches_convenience_builder(
    bundle: _Bundle,
) -> None:
    request = require_s0_production_evidence_bundle_approval_signing_request(
        bundle.signing_request
    )
    signing_bytes = s0_production_evidence_bundle_approval_signing_bytes(request)
    assert hashlib.sha256(signing_bytes).hexdigest() == request["signing_bytes_sha256"]
    signature = sign_ed25519(signing_bytes, FINAL_REVIEWER_KEY)
    detached = attach_s0_production_evidence_bundle_approval_signature(
        request,
        signature_hex=signature,
        verification_key=FINAL_REVIEWER_PUBLIC_KEY,
    )
    convenience = build_signed_s0_production_evidence_bundle_approval(
        host_evidence=bundle.host_inputs,
        final_reviewer_identity_sha256=FINAL_REVIEWER_IDENTITY,
        final_reviewer_key_id=FINAL_REVIEWER_KEY_ID,
        signing_key=FINAL_REVIEWER_KEY,
        reviewed_at=FINAL_REVIEWED_AT,
        expires_at=FINAL_EXPIRES_AT,
        nonce_sha256=FINAL_NONCE,
        revoked_host_review_attestation_sha256s=(),
        superseded_host_review_attestation_sha256s=(),
    )
    assert detached == convenience == bundle.approval
    assert _verify(bundle, detached).s0_accepted is True


def _refresh_signing_request(request: dict[str, Any]) -> dict[str, Any]:
    payload = request["approval_payload"]
    payload.pop("approval_sha256", None)
    payload["approval_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    request["signing_bytes_sha256"] = hashlib.sha256(
        _canonical_bytes(payload)
    ).hexdigest()
    request.pop("request_sha256", None)
    request["request_sha256"] = hashlib.sha256(_canonical_bytes(request)).hexdigest()
    return request


def test_signing_request_rejects_claim_tamper_crosswire_and_private_material(
    bundle: _Bundle,
) -> None:
    claim_tamper = deepcopy(bundle.signing_request)
    claim_tamper["approval_payload"]["scientifically_validated"] = True
    _refresh_signing_request(claim_tamper)
    with pytest.raises(S0ProductionEvidenceBundleError, match="claim projection"):
        require_s0_production_evidence_bundle_approval_signing_request(claim_tamper)

    crosswired = deepcopy(bundle.signing_request)
    crosswired["final_reviewer_key_id"] = "crosswired-final-reviewer"
    _refresh_signing_request(crosswired)
    with pytest.raises(S0ProductionEvidenceBundleError, match="cross-wired"):
        require_s0_production_evidence_bundle_approval_signing_request(crosswired)

    leaked = deepcopy(bundle.signing_request)
    leaked_payload = leaked["approval_payload"]
    leaked_payload["bundle"]["host_rows"][0]["private_key_hex"] = "7f" * 32
    leaked_payload["bundle_sha256"] = hashlib.sha256(
        _canonical_bytes(leaked_payload["bundle"])
    ).hexdigest()
    _refresh_signing_request(leaked)
    with pytest.raises(S0ProductionEvidenceBundleError, match="private signing"):
        require_s0_production_evidence_bundle_approval_signing_request(leaked)


def test_signing_request_rejects_recomputed_duplicate_host_and_role_reuse(
    bundle: _Bundle,
) -> None:
    duplicate = deepcopy(bundle.signing_request)
    duplicate_payload = duplicate["approval_payload"]
    duplicate_rows = duplicate_payload["bundle"]["host_rows"]
    duplicate_rows[1]["cpu_identity_sha256"] = duplicate_rows[0]["cpu_identity_sha256"]
    duplicate_payload["bundle_sha256"] = hashlib.sha256(
        _canonical_bytes(duplicate_payload["bundle"])
    ).hexdigest()
    _refresh_signing_request(duplicate)
    with pytest.raises(S0ProductionEvidenceBundleError, match="must be distinct"):
        require_s0_production_evidence_bundle_approval_signing_request(duplicate)

    role_reuse = deepcopy(bundle.signing_request)
    role_payload = role_reuse["approval_payload"]
    nested_role = role_payload["bundle"]["host_rows"][0][
        "external_result_reviewer_identity_sha256"
    ]
    role_payload["final_review"]["final_reviewer_identity_sha256"] = nested_role
    role_reuse["final_reviewer_identity_sha256"] = nested_role
    _refresh_signing_request(role_reuse)
    with pytest.raises(S0ProductionEvidenceBundleError, match="nested role"):
        require_s0_production_evidence_bundle_approval_signing_request(role_reuse)


def test_signing_request_rejects_noncanonical_transport_and_bad_signature(
    bundle: _Bundle,
) -> None:
    pretty = json.dumps(bundle.signing_request, indent=2).encode("utf-8")
    with pytest.raises(S0ProductionEvidenceBundleError, match="canonical"):
        require_s0_production_evidence_bundle_approval_signing_request(pretty)
    signature = sign_ed25519(
        s0_production_evidence_bundle_approval_signing_bytes(bundle.signing_request),
        FINAL_REVIEWER_KEY,
    )
    with pytest.raises(S0ProductionEvidenceBundleError, match="verification failed"):
        attach_s0_production_evidence_bundle_approval_signature(
            bundle.signing_request,
            signature_hex=signature,
            verification_key=bytes.fromhex("72" * 32),
        )
    with pytest.raises(S0ProductionEvidenceBundleError, match="verification failed"):
        attach_s0_production_evidence_bundle_approval_signature(
            bundle.signing_request,
            signature_hex="0" * 128,
            verification_key=FINAL_REVIEWER_PUBLIC_KEY,
        )


def test_secret_free_cli_emits_signing_bytes_and_attaches_signature(
    bundle: _Bundle, tmp_path: Path
) -> None:
    request_path = tmp_path / "request.json"
    signing_path = tmp_path / "signing.json"
    approval_path = tmp_path / "approval.json"
    request_path.write_bytes(_canonical_bytes(bundle.signing_request))

    assert (
        main(
            [
                "signing-bytes",
                "--request",
                str(request_path),
                "--output",
                str(signing_path),
            ]
        )
        == 0
    )
    assert signing_path.read_bytes() == (
        s0_production_evidence_bundle_approval_signing_bytes(bundle.signing_request)
    )
    assert signing_path.stat().st_mode & 0o777 == 0o600
    signature = sign_ed25519(signing_path.read_bytes(), FINAL_REVIEWER_KEY)
    assert (
        main(
            [
                "attach-signature",
                "--request",
                str(request_path),
                "--signature-hex",
                signature,
                "--verification-key-hex",
                FINAL_REVIEWER_PUBLIC_KEY.hex(),
                "--output",
                str(approval_path),
            ]
        )
        == 0
    )
    attached = json.loads(approval_path.read_text(encoding="ascii"))
    assert attached == bundle.approval
    assert approval_path.stat().st_mode & 0o777 == 0o600
    original = approval_path.read_bytes()
    assert (
        main(
            [
                "attach-signature",
                "--request",
                str(request_path),
                "--signature-hex",
                signature,
                "--verification-key-hex",
                FINAL_REVIEWER_PUBLIC_KEY.hex(),
                "--output",
                str(approval_path),
            ]
        )
        == 2
    )
    assert approval_path.read_bytes() == original


def test_secret_free_cli_rejects_symlinked_request(
    bundle: _Bundle, tmp_path: Path
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_bytes(_canonical_bytes(bundle.signing_request))
    symlink = tmp_path / "request-link.json"
    symlink.symlink_to(request_path)
    output = tmp_path / "signing.json"

    assert (
        main(
            [
                "signing-bytes",
                "--request",
                str(symlink),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


@pytest.mark.parametrize(
    "field_name",
    (
        "attestation_sha256",
        "enrolled_host_identity_sha256",
        "cpu_identity_sha256",
        "production_evidence_session_sha256",
        "custody_terminal_sha256",
        "energy_force_result_receipt_sha256",
        "minimization_result_receipt_sha256",
        "openmm_energy_force_receipt_sha256",
        "openmm_minimization_trace_receipt_sha256",
        "openmm_reference_materialization_sha256",
        "openmm_native_minimization_receipt_sha256",
        "energy_force_execution_environment_receipt_sha256",
        "minimization_execution_environment_receipt_sha256",
        "energy_force_authorization_nonce_sha256",
        "minimization_authorization_nonce_sha256",
        "nonce_sha256",
    ),
)
def test_bundle_rejects_reused_host_execution_identity(
    monkeypatch: pytest.MonkeyPatch, field_name: str
) -> None:
    host_inputs = (_host_input(1), _host_input(2))
    first = _host_verification(1)
    second = replace(_host_verification(2), **{field_name: getattr(first, field_name)})
    _install_host_verifier(monkeypatch, host_inputs, (first, second))

    with pytest.raises(S0ProductionEvidenceBundleError, match="must be distinct"):
        build_signed_s0_production_evidence_bundle_approval(
            host_evidence=host_inputs,
            final_reviewer_identity_sha256=FINAL_REVIEWER_IDENTITY,
            final_reviewer_key_id=FINAL_REVIEWER_KEY_ID,
            signing_key=FINAL_REVIEWER_KEY,
            reviewed_at=FINAL_REVIEWED_AT,
            expires_at=FINAL_EXPIRES_AT,
            nonce_sha256=FINAL_NONCE,
            revoked_host_review_attestation_sha256s=(),
            superseded_host_review_attestation_sha256s=(),
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "code_commit_sha",
        "energy_force_source_manifest_sha256",
        "minimization_source_manifest_sha256",
        "dependency_rows_sha256",
        "seed",
        "openmm_runtime_identity_sha256",
        "openmm_source_identity_sha256",
        "energy_force_physics_projection_sha256",
        "minimization_physics_projection_sha256",
        "native_minimization_physics_projection_sha256",
        "native_minimization_configuration_sha256",
    ),
)
def test_bundle_rejects_cross_host_identity_or_physics_mismatch(
    monkeypatch: pytest.MonkeyPatch, field_name: str
) -> None:
    host_inputs = (_host_input(1), _host_input(2))
    first = _host_verification(1)
    mismatch: object = (
        20260723
        if field_name == "seed"
        else (
            "b" * 40
            if field_name == "code_commit_sha"
            else _digest(f"mismatch:{field_name}")
        )
    )
    second = replace(_host_verification(2), **{field_name: mismatch})
    _install_host_verifier(monkeypatch, host_inputs, (first, second))

    with pytest.raises(S0ProductionEvidenceBundleError, match="equality failed"):
        build_signed_s0_production_evidence_bundle_approval(
            host_evidence=host_inputs,
            final_reviewer_identity_sha256=FINAL_REVIEWER_IDENTITY,
            final_reviewer_key_id=FINAL_REVIEWER_KEY_ID,
            signing_key=FINAL_REVIEWER_KEY,
            reviewed_at=FINAL_REVIEWED_AT,
            expires_at=FINAL_EXPIRES_AT,
            nonce_sha256=FINAL_NONCE,
            revoked_host_review_attestation_sha256s=(),
            superseded_host_review_attestation_sha256s=(),
        )


def test_bundle_rejects_signed_host_review_with_native_endpoint_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host_inputs = (_host_input(1), _host_input(2))
    rejected = replace(
        _host_verification(1),
        native_minimization_status=("rejected_offline_native_endpoint_comparison"),
        native_endpoint_health_passed_case_count=6,
        native_endpoint_health_failed_case_ids=(
            "v2_fixed_born_constrained_energy_decrease",
            "v2_fixed_born_checkpoint_restart_exact",
        ),
        openmm_fixed_born_disposition_receipt_sha256=_digest(
            "rejected-fixed-born-disposition"
        ),
        fixed_born_disposition_physics_projection_sha256=_digest(
            "rejected-fixed-born-physics"
        ),
        fixed_born_disposition_configuration_sha256=(
            FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256
        ),
        fixed_born_failure_disposition_required=True,
        fixed_born_failure_disposition_verified=True,
        fixed_born_failure_disposition_complete=True,
        fixed_born_failure_disposition_status=("accepted_failure_disposition_evidence"),
        fixed_born_failure_disposition_classification=(
            "final_constraint_projection_tradeoff_observed"
        ),
        external_oracle_comparison_verified=False,
        result_review_outcome="rejected",
        blockers=("openmm_native_minimization_endpoint_health_failed",),
    )
    _install_host_verifier(
        monkeypatch,
        host_inputs,
        (rejected, _host_verification(2)),
    )

    with pytest.raises(
        S0ProductionEvidenceBundleError,
        match="does not have accepted native endpoint health",
    ):
        build_signed_s0_production_evidence_bundle_approval(
            host_evidence=host_inputs,
            final_reviewer_identity_sha256=FINAL_REVIEWER_IDENTITY,
            final_reviewer_key_id=FINAL_REVIEWER_KEY_ID,
            signing_key=FINAL_REVIEWER_KEY,
            reviewed_at=FINAL_REVIEWED_AT,
            expires_at=FINAL_EXPIRES_AT,
            nonce_sha256=FINAL_NONCE,
            revoked_host_review_attestation_sha256s=(),
            superseded_host_review_attestation_sha256s=(),
        )


def test_bundle_rejects_final_reviewer_role_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host_inputs = (_host_input(1), _host_input(2))
    first = _host_verification(1)
    second = _host_verification(2)
    _install_host_verifier(monkeypatch, host_inputs, (first, second))

    with pytest.raises(S0ProductionEvidenceBundleError, match="every nested role"):
        build_signed_s0_production_evidence_bundle_approval(
            host_evidence=host_inputs,
            final_reviewer_identity_sha256=first.external_result_reviewer_identity_sha256,
            final_reviewer_key_id=FINAL_REVIEWER_KEY_ID,
            signing_key=FINAL_REVIEWER_KEY,
            reviewed_at=FINAL_REVIEWED_AT,
            expires_at=FINAL_EXPIRES_AT,
            nonce_sha256=FINAL_NONCE,
            revoked_host_review_attestation_sha256s=(),
            superseded_host_review_attestation_sha256s=(),
        )


def test_bundle_rejects_tampering_and_noncanonical_transport(bundle: _Bundle) -> None:
    tampered = deepcopy(bundle.approval)
    tampered["s1_admission_authorized"] = False
    with pytest.raises(S0ProductionEvidenceBundleError):
        _verify(bundle, tampered)

    noncanonical = json.dumps(bundle.approval).encode("utf-8")
    with pytest.raises(S0ProductionEvidenceBundleError, match="canonical"):
        _verify(bundle, noncanonical)


def test_bundle_honors_revocation_and_supersession_inputs(bundle: _Bundle) -> None:
    approval_sha = bundle.approval["approval_sha256"]
    host_sha = bundle.host_verifications[0].attestation_sha256

    with pytest.raises(S0ProductionEvidenceBundleError, match="key is revoked"):
        _verify(bundle, revoked_final_reviewer_key_ids=(FINAL_REVIEWER_KEY_ID,))
    with pytest.raises(S0ProductionEvidenceBundleError, match="approval is revoked"):
        _verify(bundle, revoked_approval_sha256s=(approval_sha,))
    with pytest.raises(S0ProductionEvidenceBundleError, match="approval is superseded"):
        _verify(bundle, superseded_approval_sha256s=(approval_sha,))
    with pytest.raises(
        S0ProductionEvidenceBundleError, match="attestation is externally revoked"
    ):
        _verify(bundle, revoked_host_review_attestation_sha256s=(host_sha,))
    with pytest.raises(
        S0ProductionEvidenceBundleError, match="attestation is externally superseded"
    ):
        _verify(bundle, superseded_host_review_attestation_sha256s=(host_sha,))


def test_bundle_rejects_missing_second_host(bundle: _Bundle) -> None:
    with pytest.raises(S0ProductionEvidenceBundleError, match="exactly two"):
        _verify(bundle, host_evidence=bundle.host_inputs[:1])
