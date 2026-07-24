from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
    build_signed_reference_validation_authorization_receipt,
    verify_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    ScientificReviewerTrustAnchor,
    build_signed_reference_validation_review_attestation,
    verify_signed_reference_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_runner import (
    run_bounded_cpu_reference_validation,
)
from betelgeuze_engine_v2.physics.reference_validation_result_review import (
    CASE_DISPOSITION_ACCEPTED,
    CASE_DISPOSITION_REJECTED,
    FAILURE_DISPOSITION_ACCEPTED,
    FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256,
    METRIC_DISPOSITION_ACCEPTED,
    METRIC_DISPOSITION_REJECTED,
    REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
    REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID,
    RESULT_REVIEW_OUTCOME_ACCEPTED,
    RESULT_REVIEW_OUTCOME_REJECTED,
    VARIANT_DISPOSITION_ACCEPTED,
    WORKER_EXECUTION_DISPOSITION_ACCEPTED,
    WORKER_EXECUTION_DISPOSITION_REJECTED,
    ReferenceValidationResultReviewError,
    ReferenceValidationResultReviewerTrustAnchor,
    build_signed_reference_validation_result_review_attestation,
    reference_validation_result_review_contract_decision,
    reference_validation_result_review_contract_document,
    require_reference_validation_result_review_contract_document,
    verify_signed_reference_validation_result_review_attestation,
)
import betelgeuze_engine_v2.physics.reference_validation_result_review as module
import betelgeuze_engine_v2.physics.reference_validation_runner as runner_module
import betelgeuze_engine_v2.physics.validation_native_runtime_identity as native_identity
import tests.unit.test_engine_v2_reference_validation_result_writer as writer_support


RESULT_REVIEWER_IDENTITY_SHA256 = "9" * 64
RESULT_REVIEWER_KEY_ID = "test-energy-result-reviewer"
RESULT_REVIEW_SIGNING_KEY = b"r" * 32
RESULT_REVIEW_VERIFICATION_KEY = ed25519_public_key_bytes(RESULT_REVIEW_SIGNING_KEY)
RESULT_REVIEW_NONCE_SHA256 = "a" * 64
UPSTREAM_REVIEW_KEY_ID = "test-energy-scientific-reviewer"
UPSTREAM_AUTHORIZATION_KEY_ID = "test-energy-authorization-operator"
UPSTREAM_REVIEW_SIGNING_KEY = b"s" * 32
UPSTREAM_AUTHORIZATION_SIGNING_KEY = b"o" * 32
UPSTREAM_REVIEW_VERIFICATION_KEY = ed25519_public_key_bytes(UPSTREAM_REVIEW_SIGNING_KEY)
UPSTREAM_AUTHORIZATION_VERIFICATION_KEY = ed25519_public_key_bytes(
    UPSTREAM_AUTHORIZATION_SIGNING_KEY
)
UPSTREAM_REVIEW_NONCE_SHA256 = "b" * 64
REVIEWED_AT = writer_support.FINAL_NOW + timedelta(minutes=1)
EXPIRES_AT = REVIEWED_AT + timedelta(days=1)
CHECKED_AT = REVIEWED_AT + timedelta(hours=1)
_DEFAULT_ATTESTATION_CACHE: dict[str, dict[str, Any]] = {}
_DEFAULT_VERIFICATION_CACHE: dict[tuple[str, str], Any] = {}


@dataclass(frozen=True)
class ReceiptBundle:
    baseline_rejected: dict[str, Any]
    accepted: dict[str, Any]
    incomplete_worker_rejected: dict[str, Any]


def _all_pass_case_rows(protocol: Any, manifest_cases: Any) -> tuple[Any, ...]:
    rows = runner_module._run_case_matrix_in_process(
        protocol,
        manifest_cases,
        deadline=runner_module.time.monotonic() + 120.0,
    )
    metric_map = {metric.metric_id: metric for metric in protocol.metrics}
    accepted_rows = []
    for case_contract, row in zip(protocol.cases, rows, strict=True):
        variants = tuple(
            replace(
                variant,
                oracle_total_energy_kcal_per_mol=(variant.total_energy_kcal_per_mol),
                oracle_forces_kcal_per_mol_angstrom=(
                    variant.forces_kcal_per_mol_angstrom
                ),
                oracle_force_array_sha256=variant.force_array_sha256,
            )
            if variant.observed_status == "success"
            else variant
            for variant in row.variant_results
        )
        metrics = runner_module._metric_observations(
            case_contract,
            variants,
            metric_map,
        )
        status = (
            "metrics_passed"
            if case_contract.expected_outcome == "pass"
            and all(metric.passed for metric in metrics)
            else row.observed_status
        )
        accepted_rows.append(
            replace(
                row,
                variant_results=variants,
                metric_values=metrics,
                observed_status=status,
                observed_error_code=(
                    None if status == "metrics_passed" else row.observed_error_code
                ),
                case_passed=status in {"metrics_passed", "fail_closed_as_expected"},
            )
        )
    assert len(accepted_rows) == 27
    assert sum(row.case_passed for row in accepted_rows) == 27
    return tuple(accepted_rows)


def _complete_accepted_case_worker_result(
    protocol: Any,
    manifest_cases: Any,
    *,
    environment: SimpleNamespace,
    runner_start_record_sha256: str,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    rows = _all_pass_case_rows(protocol, manifest_cases)
    _, manifest = runner_module._load_frozen_case_manifest_document()
    request = writer_support._worker_request(
        worker_kind="case",
        environment=environment,
        materialization_manifest_sha256=manifest["materialization_manifest_sha256"],
        runner_start_record_sha256=runner_start_record_sha256,
    )
    request_sha256 = runner_module._worker_request_sha256(request)
    snapshot = writer_support._synthetic_native_runtime_snapshot()
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    payload_rows = [row.to_dict() for row in rows]
    lifecycle = native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=payload_rows,
        post_snapshot=snapshot,
    )
    transcript = writer_support._worker_transcript(
        worker_kind="case",
        request=request,
        lifecycle=lifecycle,
        payload_rows=payload_rows,
    )
    provenance = runner_module._build_worker_execution_provenance(
        worker_kind="case",
        request=request,
        supervisor_launched_child_process_id=1,
        transcript=transcript,
        lifecycle=lifecycle,
        accepted_payload_rows=payload_rows,
        failure_stage=None,
        child_exit_code=0,
        timed_out=False,
        output_overflow=False,
        communication_failed=False,
        request_fully_written=True,
    )
    return rows, lifecycle, provenance


def _accepted_observation(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: SimpleNamespace,
) -> Any:
    selected = environment
    monkeypatch.setattr(runner_module, "_utc_now", lambda: writer_support.RUN_NOW)
    monkeypatch.setattr(
        runner_module,
        "require_reference_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: selected,
    )
    monkeypatch.setattr(
        runner_module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: selected.code_commit_sha,
    )
    monkeypatch.setattr(
        runner_module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        runner_module,
        "_require_isolated_python_bootstrap_runtime",
        lambda **_kwargs: (Path("/trusted"),),
    )
    monkeypatch.setattr(
        runner_module,
        "_observe_dependency_artifact_sha256_rows",
        lambda _roots, **kwargs: dict(writer_support.DEPENDENCY_ROWS),
    )
    monkeypatch.setattr(
        runner_module,
        "_require_source_only_python_runtime",
        lambda: None,
    )

    def run_accepted(
        protocol: Any,
        manifest_cases: Any,
        **kwargs: Any,
    ) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        return _complete_accepted_case_worker_result(
            protocol,
            manifest_cases,
            environment=selected,
            runner_start_record_sha256=kwargs["expected_runner_start_record_sha256"],
        )

    monkeypatch.setattr(runner_module, "_run_supervised_case_matrix", run_accepted)
    monkeypatch.setattr(
        runner_module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: writer_support._complete_manifest_supervised_result(selected),
    )
    return run_bounded_cpu_reference_validation(
        root,
        writer_support.AUTHORIZATION_NONCE,
        expected_environment_receipt_sha256=(writer_support.ENVIRONMENT_RECEIPT_SHA256),
        expected_code_commit_sha=writer_support.CODE_COMMIT_SHA,
        expected_dependency_artifact_sha256_rows=writer_support.DEPENDENCY_ROWS,
    )


def _make_receipt(root: Path, *, mode: str) -> dict[str, Any]:
    monkeypatch = pytest.MonkeyPatch()
    try:
        environment = writer_support._environment(root)
        if mode == "accepted":
            observation = _accepted_observation(
                root,
                monkeypatch,
                environment=environment,
            )
        else:
            observation = writer_support._observation(
                root,
                monkeypatch,
                environment=environment,
                worker_failure_code=(
                    "case_worker_nonzero_exit" if mode == "incomplete" else None
                ),
            )
        writer_support._install_verified_chain(monkeypatch, environment)
        return writer_support._write(root, observation).to_dict()
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="module")
def receipts(tmp_path_factory: pytest.TempPathFactory) -> ReceiptBundle:
    root = tmp_path_factory.mktemp("energy-result-review")
    baseline_root = writer_support._private_root(root, "baseline")
    accepted_root = writer_support._private_root(root, "accepted")
    incomplete_root = writer_support._private_root(root, "incomplete")
    return ReceiptBundle(
        baseline_rejected=_make_receipt(baseline_root, mode="baseline"),
        accepted=_make_receipt(accepted_root, mode="accepted"),
        incomplete_worker_rejected=_make_receipt(
            incomplete_root,
            mode="incomplete",
        ),
    )


def _authorization_for_receipt(result_receipt: dict[str, Any]) -> SimpleNamespace:
    binding = module._result_receipt_binding(result_receipt)
    return SimpleNamespace(
        receipt_sha256=binding["authorization_receipt_sha256"],
        review_attestation_sha256=binding["review_attestation_sha256"],
        implementation_author_identity_sha256=(writer_support.AUTHOR_IDENTITY_SHA256),
        independent_reviewer_identity_sha256=(writer_support.REVIEWER_IDENTITY_SHA256),
        authorization_operator_identity_sha256=(
            writer_support.OPERATOR_IDENTITY_SHA256
        ),
        authorization_nonce_sha256=binding["authorization_nonce_sha256"],
        code_commit_sha=binding["code_commit_sha"],
        runner_source_sha256=binding["runner_source_sha256"],
        execution_environment_contract_sha256=binding[
            "execution_environment_contract_sha256"
        ],
        result_receipt_contract_sha256=binding["result_contract_sha256"],
        dependency_artifact_sha256_rows=tuple(
            (row["artifact_id"], row["sha256"])
            for row in binding["dependency_artifact_sha256_rows"]
        ),
    )


def _patch_upstream(
    monkeypatch: pytest.MonkeyPatch,
    result_receipt: dict[str, Any],
    *,
    seen: dict[str, Any] | None = None,
) -> None:
    authorization = _authorization_for_receipt(result_receipt)

    def verify(raw: object, **kwargs: Any) -> SimpleNamespace:
        if seen is not None:
            seen["raw"] = raw
            seen["kwargs"] = kwargs
        return authorization

    monkeypatch.setattr(
        module,
        "verify_signed_reference_validation_authorization_receipt",
        verify,
    )


def _build(
    monkeypatch: pytest.MonkeyPatch,
    result_receipt: dict[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    _patch_upstream(monkeypatch, result_receipt)
    cache_key = result_receipt["receipt_sha256"]
    if not overrides and cache_key in _DEFAULT_ATTESTATION_CACHE:
        return deepcopy(_DEFAULT_ATTESTATION_CACHE[cache_key])
    values: dict[str, Any] = {
        "result_receipt": result_receipt,
        "expected_result_receipt_sha256": result_receipt["receipt_sha256"],
        "pre_execution_review_attestation": {"raw_review": True},
        "authorization_receipt": {"raw_authorization": True},
        "trusted_scientific_reviewer_keys": {},
        "trusted_authorization_operator_keys": {},
        "implementation_author_identity_sha256": (
            writer_support.AUTHOR_IDENTITY_SHA256
        ),
        "independent_scientific_reviewer_identity_sha256": (
            writer_support.REVIEWER_IDENTITY_SHA256
        ),
        "authorization_operator_identity_sha256": (
            writer_support.OPERATOR_IDENTITY_SHA256
        ),
        "independent_result_reviewer_identity_sha256": (
            RESULT_REVIEWER_IDENTITY_SHA256
        ),
        "result_reviewer_key_id": RESULT_REVIEWER_KEY_ID,
        "signing_key": RESULT_REVIEW_SIGNING_KEY,
        "reviewed_at": REVIEWED_AT,
        "expires_at": EXPIRES_AT,
        "nonce_sha256": RESULT_REVIEW_NONCE_SHA256,
        "revoked_pre_execution_review_attestation_sha256s": (),
        "revoked_authorization_receipt_sha256s": (),
        "revoked_execution_environment_receipt_sha256s": (),
        "revoked_result_receipt_sha256s": (),
        "superseded_result_receipt_sha256s": (),
    }
    values.update(overrides)
    result = build_signed_reference_validation_result_review_attestation(**values)
    if not overrides:
        _DEFAULT_ATTESTATION_CACHE[cache_key] = deepcopy(result)
    return result


def _verify(
    monkeypatch: pytest.MonkeyPatch,
    result_receipt: dict[str, Any],
    attestation: dict[str, Any],
    **overrides: Any,
) -> Any:
    _patch_upstream(monkeypatch, result_receipt)
    attestation_cache_identity = (
        module._sha256(attestation)
        if isinstance(attestation, dict)
        else hashlib.sha256(attestation).hexdigest()
    )
    cache_key = (result_receipt["receipt_sha256"], attestation_cache_identity)
    if not overrides and cache_key in _DEFAULT_VERIFICATION_CACHE:
        return _DEFAULT_VERIFICATION_CACHE[cache_key]
    values: dict[str, Any] = {
        "source": attestation,
        "result_receipt": result_receipt,
        "pre_execution_review_attestation": {"raw_review": True},
        "authorization_receipt": {"raw_authorization": True},
        "trusted_scientific_reviewer_keys": {},
        "trusted_authorization_operator_keys": {},
        "expected_result_receipt_sha256": result_receipt["receipt_sha256"],
        "trusted_result_reviewer_keys": {
            RESULT_REVIEWER_KEY_ID: ReferenceValidationResultReviewerTrustAnchor(
                RESULT_REVIEWER_IDENTITY_SHA256,
                RESULT_REVIEW_VERIFICATION_KEY,
            )
        },
        "expected_implementation_author_identity_sha256": (
            writer_support.AUTHOR_IDENTITY_SHA256
        ),
        "expected_independent_scientific_reviewer_identity_sha256": (
            writer_support.REVIEWER_IDENTITY_SHA256
        ),
        "expected_authorization_operator_identity_sha256": (
            writer_support.OPERATOR_IDENTITY_SHA256
        ),
        "checked_at": CHECKED_AT,
        "revoked_pre_execution_review_attestation_sha256s": (),
        "revoked_authorization_receipt_sha256s": (),
        "revoked_execution_environment_receipt_sha256s": (),
        "revoked_result_receipt_sha256s": (),
        "superseded_result_receipt_sha256s": (),
        "revoked_result_review_attestation_sha256s": (),
        "superseded_result_review_attestation_sha256s": (),
    }
    values.update(overrides)
    result = verify_signed_reference_validation_result_review_attestation(**values)
    if not overrides:
        _DEFAULT_VERIFICATION_CACHE[cache_key] = result
    return result


def _rehash_receipt(document: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(document)
    result.pop("receipt_sha256", None)
    result["receipt_sha256"] = module._sha256(result)
    return result


def _resign_attestation(document: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(document)
    result.pop("signature", None)
    result.pop("attestation_sha256", None)
    result["attestation_sha256"] = module._sha256(result)
    result["signature"] = {
        "algorithm": "ed25519",
        "key_id": RESULT_REVIEWER_KEY_ID,
        "value": sign_ed25519(
            module._canonical_bytes(result),
            RESULT_REVIEW_SIGNING_KEY,
        ),
    }
    return result


def test_contract_is_frozen_with_exact_energy_force_coverage() -> None:
    contract = reference_validation_result_review_contract_document()
    assert (
        contract["schema_id"] == REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID
    )
    assert contract["frozen_at_utc"] == "2026-07-24T18:50:00Z"
    assert contract["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
    )
    assert contract["coverage"]["case_count"] == 27
    assert contract["coverage"]["variant_count"] == 59
    assert contract["coverage"]["metric_definition_count"] == 19
    assert contract["coverage"]["required_metric_occurrence_count"] == 56
    assert contract["coverage"]["expected_pass_case_count"] == 15
    assert contract["coverage"]["expected_fail_closed_case_count"] == 12
    assert len(contract["coverage"]["expected_fail_closed_error_codes"]) == 12
    assert (
        require_reference_validation_result_review_contract_document(contract)
        == contract
    )


def test_contract_documents_complete_ed25519_chain() -> None:
    dependencies = reference_validation_result_review_contract_document()[
        "dependencies"
    ]
    assert dependencies["upstream_signature_algorithm"] == "ed25519"
    assert dependencies["leaf_result_review_signature_algorithm"] == "ed25519"
    assert dependencies["full_asymmetric_signature_chain_verified"] is True
    assert (
        dependencies["upstream_verifier_trust_anchors_contain_public_keys_only"] is True
    )
    assert dependencies["private_or_symmetric_verification_keys_allowed"] is False


def test_contract_decision_remains_closed_and_nonpromotional() -> None:
    decision = reference_validation_result_review_contract_decision()
    assert decision["result_review_contract_implemented"] is True
    assert decision["signed_independent_result_review_present"] is False
    assert decision["force_or_energy_validated"] is False
    assert decision["scientifically_validated"] is False
    assert decision["parameter_fitting_authorized"] is False
    assert decision["benchmark_validated"] is False
    assert decision["product_qualified"] is False
    assert decision["claim_safe"] is False
    assert "energy_force_upstream_symmetric_hmac_chain" not in decision["blockers"]
    assert (
        "independent_result_review_dependency_manifest_reverification_missing"
        in decision["blockers"]
    )
    assert (
        "worker_process_starttime_and_boot_id_binding_missing" in decision["blockers"]
    )


def test_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_result_review_contract_document())
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(ReferenceValidationResultReviewError):
        require_reference_validation_result_review_contract_document(tampered)


def test_baseline_complete_receipt_is_signed_and_verified_rejected(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.baseline_rejected)
    assert attestation["schema_id"] == (
        REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID
    )
    assert (
        attestation["result_receipt_review_outcome"] == RESULT_REVIEW_OUTCOME_REJECTED
    )
    assert attestation["result_receipt_accepted"] is False
    verification = _verify(
        monkeypatch,
        receipts.baseline_rejected,
        attestation,
    )
    assert verification.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_REJECTED
    assert verification.result_receipt_accepted is False
    assert "energy_force_result_receipt_review_rejected" in verification.blockers


def test_baseline_rejection_is_exactly_three_metric_threshold_cases(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.baseline_rejected)
    rejected = [
        row
        for row in attestation["case_review_rows"]
        if row["disposition"] == CASE_DISPOSITION_REJECTED
    ]
    assert [row["case_id"] for row in rejected] == [
        "angle_energy_force",
        "proper_torsion_energy_force",
        "quintic_switch_window_and_cutoff",
    ]
    assert (
        sum(
            metric["disposition"] == METRIC_DISPOSITION_REJECTED
            for row in rejected
            for metric in row["metric_dispositions"]
        )
        == 4
    )


def test_all_pass_receipt_is_signed_and_verified_accepted(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    assert (
        attestation["result_receipt_review_outcome"] == RESULT_REVIEW_OUTCOME_ACCEPTED
    )
    assert attestation["result_receipt_accepted"] is True
    verification = _verify(monkeypatch, receipts.accepted, attestation)
    assert verification.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED
    assert verification.result_receipt_accepted is True
    assert "energy_force_result_receipt_review_rejected" not in verification.blockers


def test_accepted_review_has_exact_case_variant_metric_and_failure_dispositions(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _build(monkeypatch, receipts.accepted)["case_review_rows"]
    assert len(rows) == 27
    assert all(row["disposition"] == CASE_DISPOSITION_ACCEPTED for row in rows)
    assert sum(len(row["variant_dispositions"]) for row in rows) == 59
    assert sum(len(row["metric_dispositions"]) for row in rows) == 56
    assert sum(len(row["failure_dispositions"]) for row in rows) == 12
    assert all(
        variant["disposition"] == VARIANT_DISPOSITION_ACCEPTED
        for row in rows
        for variant in row["variant_dispositions"]
    )
    assert all(
        metric["disposition"] == METRIC_DISPOSITION_ACCEPTED
        for row in rows
        for metric in row["metric_dispositions"]
    )
    assert all(
        failure["disposition"] == FAILURE_DISPOSITION_ACCEPTED
        for row in rows
        for failure in row["failure_dispositions"]
    )


def test_exact_twelve_fail_closed_codes_are_accepted_in_protocol_order(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _build(monkeypatch, receipts.accepted)["case_review_rows"]
    assert [
        row["expected_error_code"]
        for row in rows
        if row["expected_outcome"] == "fail_closed"
    ] == [
        "parameter_topology_identity_mismatch",
        "nonbonded_parameters_do_not_cover_all_atoms",
        "bond_parameters_do_not_exactly_cover_system_bonds",
        "angle_parameters_do_not_exactly_cover_system_topology",
        "torsion_parameters_do_not_exactly_cover_system_topology",
        "neighbor_graph_not_bound_to_current_system",
        "neighbor_cutoff_shorter_than_parameter_cutoff",
        "atom_count_outside_applicability_domain",
        "nonbonded_pair_below_minimum_pair_distance_angstrom",
        "periodic_cutoff_not_below_half_smallest_box_length",
        "angle_zero_length_vector",
        "torsion_undefined_for_collinear_atoms",
    ]


def test_all_forty_seven_success_variants_bind_exact_force_digests(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _build(monkeypatch, receipts.accepted)["case_review_rows"]
    evidence = [
        variant["successful_result_evidence"]
        for row in rows
        for variant in row["variant_dispositions"]
        if variant["successful_result_evidence"] is not None
    ]
    assert len(evidence) == 47
    assert all(
        row["force_array_sha256"] == row["recomputed_force_array_sha256"]
        and row["oracle_force_array_sha256"]
        == row["recomputed_oracle_force_array_sha256"]
        for row in evidence
    )


def test_manifest_and_case_worker_reviews_bind_three_and_twenty_nine_frames(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_rows = _build(monkeypatch, receipts.accepted)["worker_execution_review"]
    assert [row["worker_kind"] for row in worker_rows] == ["manifest", "case"]
    assert [row["payload_frame_count"] for row in worker_rows] == [1, 27]
    assert [row["transcript_frame_count"] for row in worker_rows] == [3, 29]
    assert all(
        row["disposition"] == WORKER_EXECUTION_DISPOSITION_ACCEPTED
        and row["transcript_sha256"] == row["reconstructed_transcript_sha256"]
        and row["worker_request_sha256"] == row["recomputed_worker_request_sha256"]
        and row["supervisor_child_pid_matches_native_endpoints"] is True
        for row in worker_rows
    )


def test_incomplete_case_worker_receipt_is_signed_and_verified_rejected(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.incomplete_worker_rejected)
    assert (
        attestation["result_receipt_review_outcome"] == RESULT_REVIEW_OUTCOME_REJECTED
    )
    worker_rows = attestation["worker_execution_review"]
    assert worker_rows[0]["disposition"] == WORKER_EXECUTION_DISPOSITION_ACCEPTED
    assert worker_rows[1]["disposition"] == WORKER_EXECUTION_DISPOSITION_REJECTED
    assert "worker_execution_is_incomplete" in worker_rows[1]["rejection_reasons"]
    assert (
        _verify(
            monkeypatch,
            receipts.incomplete_worker_rejected,
            attestation,
        ).result_receipt_accepted
        is False
    )


def test_metric_threshold_is_recomputed_without_trusting_retained_passed_flag(
    receipts: ReceiptBundle,
) -> None:
    tampered = deepcopy(receipts.baseline_rejected)
    metric = tampered["case_results"][1]["metric_values"][3]
    assert metric["passed"] is False
    metric["passed"] = True
    rows = module._case_review_rows_from_result_receipt(tampered)
    reviewed = rows[1]["metric_dispositions"][3]
    assert reviewed["retained_passed"] is True
    assert reviewed["recomputed_passed"] is False
    assert reviewed["disposition"] == METRIC_DISPOSITION_REJECTED


def test_raw_force_tamper_with_updated_digest_cannot_reuse_retained_metric_ledger(
    receipts: ReceiptBundle,
) -> None:
    tampered = deepcopy(receipts.accepted)
    variant = tampered["case_results"][0]["variant_results"][0]
    variant["force_array_values"][0][0] += 1.0
    variant["force_array_sha256"] = module._force_array_sha256(
        variant["force_array_values"]
    )
    rows = module._case_review_rows_from_result_receipt(tampered)
    first = rows[0]
    mismatched_metrics = [
        metric
        for metric in first["metric_dispositions"]
        if metric["retained_value_matches_recomputed"] is False
    ]
    assert mismatched_metrics
    assert all(
        metric["disposition"] == METRIC_DISPOSITION_REJECTED
        for metric in mismatched_metrics
    )
    assert first["variant_dispositions"][0]["disposition"] != (
        VARIANT_DISPOSITION_ACCEPTED
    )
    assert first["disposition"] == CASE_DISPOSITION_REJECTED


@pytest.mark.parametrize("mutation", ["component_name", "component_sum"])
def test_component_identity_and_evaluator_order_total_are_independently_bound(
    receipts: ReceiptBundle,
    mutation: str,
) -> None:
    tampered = deepcopy(receipts.accepted)
    variant = tampered["case_results"][0]["variant_results"][0]
    components = variant["component_energy_values_and_units"]
    if mutation == "component_name":
        components[0]["name"] = "unfrozen_component"
    else:
        components[0]["value"] += 1.0
    rows = module._case_review_rows_from_result_receipt(tampered)
    first = rows[0]
    reasons = first["variant_dispositions"][0]["rejection_reasons"]
    assert any(
        reason
        in {
            "component_energy_order_or_identity_invalid",
            "component_energy_sum_does_not_equal_total_energy",
        }
        for reason in reasons
    )
    assert first["variant_dispositions"][0]["disposition"] != (
        VARIANT_DISPOSITION_ACCEPTED
    )
    assert first["disposition"] == CASE_DISPOSITION_REJECTED


def test_success_force_arrays_must_match_frozen_fixture_atom_count(
    receipts: ReceiptBundle,
) -> None:
    tampered = deepcopy(receipts.accepted)
    variant = tampered["case_results"][0]["variant_results"][0]
    variant["force_array_values"].append([0.0, 0.0, 0.0])
    variant["oracle_force_array_values"].append([0.0, 0.0, 0.0])
    variant["force_array_shape"] = [3, 3]
    variant["force_array_sha256"] = module._force_array_sha256(
        variant["force_array_values"]
    )
    variant["oracle_force_array_sha256"] = module._force_array_sha256(
        variant["oracle_force_array_values"]
    )
    rows = module._case_review_rows_from_result_receipt(tampered)
    first = rows[0]
    reasons = first["variant_dispositions"][0]["rejection_reasons"]
    assert "force_array_evidence_invalid" in reasons
    assert "oracle_force_array_evidence_invalid" in reasons
    assert first["variant_dispositions"][0]["disposition"] != (
        VARIANT_DISPOSITION_ACCEPTED
    )
    assert first["disposition"] == CASE_DISPOSITION_REJECTED


@pytest.mark.parametrize(
    "mutation",
    [
        "case_omission",
        "case_reorder",
        "case_duplicate",
        "variant_omission",
        "variant_reorder",
        "metric_omission",
        "metric_reorder",
    ],
)
def test_structural_omission_reorder_and_duplicate_fail_validation(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    tampered = deepcopy(receipts.accepted)
    if mutation == "case_omission":
        tampered["case_results"].pop()
    elif mutation == "case_reorder":
        tampered["case_results"][0], tampered["case_results"][1] = (
            tampered["case_results"][1],
            tampered["case_results"][0],
        )
    elif mutation == "case_duplicate":
        tampered["case_results"][1] = deepcopy(tampered["case_results"][0])
    elif mutation == "variant_omission":
        tampered["case_results"][10]["variant_results"].pop()
    elif mutation == "variant_reorder":
        variants = tampered["case_results"][10]["variant_results"]
        variants[0], variants[1] = variants[1], variants[0]
    elif mutation == "metric_omission":
        tampered["case_results"][0]["metric_values"].pop()
    else:
        metrics = tampered["case_results"][0]["metric_values"]
        metrics[0], metrics[1] = metrics[1], metrics[0]
    tampered = _rehash_receipt(tampered)
    with pytest.raises(ReferenceValidationResultReviewError):
        _build(monkeypatch, tampered)


@pytest.mark.parametrize(
    "mutation",
    [
        "variant_input",
        "worker_request",
        "transcript",
        "pid",
        "lifecycle",
    ],
)
def test_transplant_request_transcript_pid_and_lifecycle_tamper_fail_validation(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    tampered = deepcopy(receipts.accepted)
    observation = tampered["run_observation"]
    if mutation == "variant_input":
        tampered["case_results"][0]["variant_results"][0]["runtime_input_sha256"] = (
            "0" * 64
        )
    elif mutation == "worker_request":
        observation["case_worker_execution_provenance"]["worker_request_sha256"] = (
            "0" * 64
        )
    elif mutation == "transcript":
        observation["case_worker_execution_provenance"]["transcript_sha256"] = "0" * 64
    elif mutation == "pid":
        observation["case_worker_execution_provenance"][
            "supervisor_launched_child_process_id"
        ] = 2
    else:
        observation["case_worker_lifecycle_evidence"]["completion_state"] = "incomplete"
    tampered = _rehash_receipt(tampered)
    with pytest.raises(ReferenceValidationResultReviewError):
        _build(monkeypatch, tampered)


def test_out_of_band_expected_receipt_hash_is_mandatory(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ReferenceValidationResultReviewError, match="cross-wired"):
        _build(
            monkeypatch,
            receipts.accepted,
            expected_result_receipt_sha256="0" * 64,
        )


def test_real_upstream_ed25519_chain_verifies_before_ed25519_result_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_reviewed_at = writer_support.RUN_NOW - timedelta(hours=2)
    upstream_review_expires_at = writer_support.FINAL_NOW + timedelta(days=1)
    upstream_authorization_issued_at = writer_support.RUN_NOW - timedelta(hours=1)
    upstream_authorization_expires_at = writer_support.FINAL_NOW + timedelta(hours=4)
    reviewer_keys = {
        UPSTREAM_REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
            writer_support.REVIEWER_IDENTITY_SHA256,
            UPSTREAM_REVIEW_VERIFICATION_KEY,
        )
    }
    operator_keys = {
        UPSTREAM_AUTHORIZATION_KEY_ID: AuthorizationOperatorTrustAnchor(
            writer_support.OPERATOR_IDENTITY_SHA256,
            UPSTREAM_AUTHORIZATION_VERIFICATION_KEY,
        )
    }
    pre_execution_review = build_signed_reference_validation_review_attestation(
        implementation_author_identity_sha256=(writer_support.AUTHOR_IDENTITY_SHA256),
        independent_reviewer_identity_sha256=(writer_support.REVIEWER_IDENTITY_SHA256),
        reviewer_key_id=UPSTREAM_REVIEW_KEY_ID,
        signing_key=UPSTREAM_REVIEW_SIGNING_KEY,
        reviewed_at=upstream_reviewed_at,
        expires_at=upstream_review_expires_at,
        nonce_sha256=UPSTREAM_REVIEW_NONCE_SHA256,
    )
    review_verification = verify_signed_reference_validation_review_attestation(
        pre_execution_review,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=(
            writer_support.AUTHOR_IDENTITY_SHA256
        ),
        checked_at=writer_support.FINAL_NOW,
    )
    authorization = build_signed_reference_validation_authorization_receipt(
        review_attestation=pre_execution_review,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=(
            writer_support.AUTHOR_IDENTITY_SHA256
        ),
        authorization_operator_identity_sha256=(
            writer_support.OPERATOR_IDENTITY_SHA256
        ),
        authorization_key_id=UPSTREAM_AUTHORIZATION_KEY_ID,
        signing_key=UPSTREAM_AUTHORIZATION_SIGNING_KEY,
        issued_at=upstream_authorization_issued_at,
        expires_at=upstream_authorization_expires_at,
        authorization_nonce_sha256=writer_support.AUTHORIZATION_NONCE,
        code_commit_sha=writer_support.CODE_COMMIT_SHA,
        runner_source_sha256=(
            writer_support.reference_validation_runner_source_sha256()
        ),
        execution_environment_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        result_receipt_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        dependency_artifact_sha256_rows=writer_support.DEPENDENCY_ROWS,
    )
    authorization_verification = (
        verify_signed_reference_validation_authorization_receipt(
            authorization,
            review_attestation=pre_execution_review,
            trusted_reviewer_keys=reviewer_keys,
            expected_implementation_author_identity_sha256=(
                writer_support.AUTHOR_IDENTITY_SHA256
            ),
            trusted_operator_keys=operator_keys,
            checked_at=writer_support.FINAL_NOW,
            expected_code_commit_sha=writer_support.CODE_COMMIT_SHA,
            expected_runner_source_sha256=(
                writer_support.reference_validation_runner_source_sha256()
            ),
            expected_execution_environment_contract_sha256=(
                FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            expected_result_receipt_contract_sha256=(
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            expected_dependency_artifact_sha256_rows=writer_support.DEPENDENCY_ROWS,
        )
    )

    root = writer_support._private_root(tmp_path, "real-upstream-ed25519-chain")
    environment = writer_support._environment(
        root,
        review_attestation_sha256=pre_execution_review["attestation_sha256"],
        authorization_receipt_sha256=authorization["receipt_sha256"],
    )
    observation = writer_support._observation(
        root,
        monkeypatch,
        environment=environment,
    )
    monkeypatch.setattr(
        writer_support.module,
        "_utc_now",
        lambda: writer_support.FINAL_NOW,
    )
    monkeypatch.setattr(
        writer_support.module,
        "require_reference_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: environment,
    )
    result_receipt = writer_support.write_reference_validation_result_receipt(
        root,
        writer_support.AUTHORIZATION_NONCE,
        observation,
        review_attestation=pre_execution_review,
        authorization_receipt=authorization,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=(
            writer_support.AUTHOR_IDENTITY_SHA256
        ),
        trusted_operator_keys=operator_keys,
        revoked_authorization_receipt_sha256s=(),
        revoked_review_attestation_sha256s=(),
        externally_conflicting_nonce_sha256s=(),
    ).to_dict()

    assert pre_execution_review["signature"]["algorithm"] == "ed25519"
    assert authorization["signature"]["algorithm"] == "ed25519"
    assert review_verification.independent_scientific_review_verified is True
    assert review_verification.implementation_author_separation_verified is True
    assert review_verification.validation_execution_authorized is False
    assert review_verification.parameter_fitting_proposal_authorized is False
    assert review_verification.parameter_fitting_authorized is False
    assert authorization_verification.receipt_authorization_verified is True
    assert authorization_verification.validation_execution_authorized is False
    assert authorization_verification.parameter_fitting_proposal_authorized is False
    assert authorization_verification.parameter_fitting_authorized is False
    assert (
        authorization_verification.review_attestation_sha256
        == (pre_execution_review["attestation_sha256"])
    )
    assert authorization_verification.receipt_sha256 == authorization["receipt_sha256"]
    assert (
        result_receipt["review_attestation_sha256"]
        == (pre_execution_review["attestation_sha256"])
    )
    assert (
        result_receipt["authorization_receipt_sha256"]
        == (authorization["receipt_sha256"])
    )

    attestation = build_signed_reference_validation_result_review_attestation(
        result_receipt=result_receipt,
        expected_result_receipt_sha256=result_receipt["receipt_sha256"],
        pre_execution_review_attestation=pre_execution_review,
        authorization_receipt=authorization,
        trusted_scientific_reviewer_keys=reviewer_keys,
        trusted_authorization_operator_keys=operator_keys,
        implementation_author_identity_sha256=(writer_support.AUTHOR_IDENTITY_SHA256),
        independent_scientific_reviewer_identity_sha256=(
            writer_support.REVIEWER_IDENTITY_SHA256
        ),
        authorization_operator_identity_sha256=(
            writer_support.OPERATOR_IDENTITY_SHA256
        ),
        independent_result_reviewer_identity_sha256=(RESULT_REVIEWER_IDENTITY_SHA256),
        result_reviewer_key_id=RESULT_REVIEWER_KEY_ID,
        signing_key=RESULT_REVIEW_SIGNING_KEY,
        reviewed_at=REVIEWED_AT,
        expires_at=EXPIRES_AT,
        nonce_sha256=RESULT_REVIEW_NONCE_SHA256,
        revoked_pre_execution_review_attestation_sha256s=(),
        revoked_authorization_receipt_sha256s=(),
        revoked_execution_environment_receipt_sha256s=(),
        revoked_result_receipt_sha256s=(),
        superseded_result_receipt_sha256s=(),
    )
    verification = verify_signed_reference_validation_result_review_attestation(
        attestation,
        result_receipt=result_receipt,
        pre_execution_review_attestation=pre_execution_review,
        authorization_receipt=authorization,
        trusted_scientific_reviewer_keys=reviewer_keys,
        trusted_authorization_operator_keys=operator_keys,
        expected_result_receipt_sha256=result_receipt["receipt_sha256"],
        trusted_result_reviewer_keys={
            RESULT_REVIEWER_KEY_ID: ReferenceValidationResultReviewerTrustAnchor(
                RESULT_REVIEWER_IDENTITY_SHA256,
                RESULT_REVIEW_VERIFICATION_KEY,
            )
        },
        expected_implementation_author_identity_sha256=(
            writer_support.AUTHOR_IDENTITY_SHA256
        ),
        expected_independent_scientific_reviewer_identity_sha256=(
            writer_support.REVIEWER_IDENTITY_SHA256
        ),
        expected_authorization_operator_identity_sha256=(
            writer_support.OPERATOR_IDENTITY_SHA256
        ),
        checked_at=CHECKED_AT,
        revoked_pre_execution_review_attestation_sha256s=(),
        revoked_authorization_receipt_sha256s=(),
        revoked_execution_environment_receipt_sha256s=(),
        revoked_result_receipt_sha256s=(),
        superseded_result_receipt_sha256s=(),
        revoked_result_review_attestation_sha256s=(),
        superseded_result_review_attestation_sha256s=(),
    )

    expected_roles = {
        writer_support.AUTHOR_IDENTITY_SHA256,
        writer_support.REVIEWER_IDENTITY_SHA256,
        writer_support.OPERATOR_IDENTITY_SHA256,
        RESULT_REVIEWER_IDENTITY_SHA256,
    }
    assert len(expected_roles) == 4
    assert {
        attestation["implementation_author_identity_sha256"],
        attestation["independent_scientific_reviewer_identity_sha256"],
        attestation["authorization_operator_identity_sha256"],
        attestation["independent_result_reviewer_identity_sha256"],
    } == expected_roles
    assert {
        verification.implementation_author_identity_sha256,
        verification.independent_scientific_reviewer_identity_sha256,
        verification.authorization_operator_identity_sha256,
        verification.independent_result_reviewer_identity_sha256,
    } == expected_roles
    assert attestation["signature"]["algorithm"] == "ed25519"
    assert attestation["result_receipt_review_outcome"] == (
        RESULT_REVIEW_OUTCOME_REJECTED
    )
    assert attestation["result_receipt_accepted"] is False
    assert verification.independent_result_review_verified is True
    assert verification.implementation_author_separation_verified is True
    assert verification.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_REJECTED
    assert verification.result_receipt_accepted is False

    for claim in (
        "production_validation_evidence",
        "force_or_energy_validated",
        "scientific_validation_recommended",
        "parameter_fitting_proposal_recommended",
        "parameter_fitting_recommended",
        "scientifically_validated",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert attestation[claim] is False
    for claim in (
        "production_validation_evidence",
        "force_or_energy_validated",
        "scientifically_validated",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "claim_safe",
    ):
        assert verification.to_dict()[claim] is False


def test_raw_upstream_ed25519_chain_is_reverified_with_exact_receipt_time(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    _patch_upstream(monkeypatch, receipts.accepted, seen=seen)
    build_signed_reference_validation_result_review_attestation(
        result_receipt=receipts.accepted,
        expected_result_receipt_sha256=receipts.accepted["receipt_sha256"],
        pre_execution_review_attestation={"raw_review": True},
        authorization_receipt={"raw_authorization": True},
        trusted_scientific_reviewer_keys={},
        trusted_authorization_operator_keys={},
        implementation_author_identity_sha256=writer_support.AUTHOR_IDENTITY_SHA256,
        independent_scientific_reviewer_identity_sha256=(
            writer_support.REVIEWER_IDENTITY_SHA256
        ),
        authorization_operator_identity_sha256=writer_support.OPERATOR_IDENTITY_SHA256,
        independent_result_reviewer_identity_sha256=RESULT_REVIEWER_IDENTITY_SHA256,
        result_reviewer_key_id=RESULT_REVIEWER_KEY_ID,
        signing_key=RESULT_REVIEW_SIGNING_KEY,
        reviewed_at=REVIEWED_AT,
        expires_at=EXPIRES_AT,
        nonce_sha256=RESULT_REVIEW_NONCE_SHA256,
        revoked_pre_execution_review_attestation_sha256s=(),
        revoked_authorization_receipt_sha256s=(),
        revoked_execution_environment_receipt_sha256s=(),
        revoked_result_receipt_sha256s=(),
        superseded_result_receipt_sha256s=(),
    )
    assert seen["raw"] == {"raw_authorization": True}
    assert seen["kwargs"]["review_attestation"] == {"raw_review": True}
    assert (
        seen["kwargs"]["checked_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
        == (receipts.accepted["receipt_created_at_utc"])
    )


def test_caller_supplied_disposition_rows_are_never_accepted(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        ReferenceValidationResultReviewError,
        match="caller-supplied result dispositions",
    ):
        _build(monkeypatch, receipts.accepted, case_review_rows=[])


def test_validly_signed_false_disposition_is_rejected_by_recomputation(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    attestation["case_review_rows"][0]["disposition"] = CASE_DISPOSITION_REJECTED
    attestation["result_receipt_review_outcome"] = RESULT_REVIEW_OUTCOME_REJECTED
    attestation["result_receipt_accepted"] = False
    attestation = _resign_attestation(attestation)
    with pytest.raises(
        ReferenceValidationResultReviewError, match="derived dispositions"
    ):
        _verify(monkeypatch, receipts.accepted, attestation)


def test_signature_tamper_is_rejected(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    attestation["signature"]["value"] = "0" * 128
    with pytest.raises(
        ReferenceValidationResultReviewError, match="signature verification"
    ):
        _verify(monkeypatch, receipts.accepted, attestation)


def test_untrusted_result_reviewer_key_is_rejected(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    with pytest.raises(ReferenceValidationResultReviewError, match="not trusted"):
        _verify(
            monkeypatch,
            receipts.accepted,
            attestation,
            trusted_result_reviewer_keys={},
        )


def test_wrong_result_reviewer_public_key_is_rejected(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    with pytest.raises(
        ReferenceValidationResultReviewError, match="signature verification"
    ):
        _verify(
            monkeypatch,
            receipts.accepted,
            attestation,
            trusted_result_reviewer_keys={
                RESULT_REVIEWER_KEY_ID: ReferenceValidationResultReviewerTrustAnchor(
                    RESULT_REVIEWER_IDENTITY_SHA256,
                    ed25519_public_key_bytes(b"x" * 32),
                )
            },
        )


@pytest.mark.parametrize(
    "identity_field,duplicate_value",
    [
        (
            "independent_result_reviewer_identity_sha256",
            writer_support.AUTHOR_IDENTITY_SHA256,
        ),
        (
            "authorization_operator_identity_sha256",
            writer_support.REVIEWER_IDENTITY_SHA256,
        ),
    ],
)
def test_four_review_roles_must_be_pairwise_distinct(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    identity_field: str,
    duplicate_value: str,
) -> None:
    with pytest.raises(ReferenceValidationResultReviewError, match="pairwise distinct"):
        _build(
            monkeypatch,
            receipts.accepted,
            **{identity_field: duplicate_value},
        )


@pytest.mark.parametrize(
    "reviewed_at,expires_at,error",
    [
        (
            writer_support.FINAL_NOW - timedelta(seconds=1),
            EXPIRES_AT,
            "predates",
        ),
        (REVIEWED_AT, REVIEWED_AT, "expiry"),
        (REVIEWED_AT, REVIEWED_AT + timedelta(days=31), "frozen maximum"),
    ],
)
def test_builder_enforces_result_review_time_window(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    reviewed_at: Any,
    expires_at: Any,
    error: str,
) -> None:
    with pytest.raises(ReferenceValidationResultReviewError, match=error):
        _build(
            monkeypatch,
            receipts.accepted,
            reviewed_at=reviewed_at,
            expires_at=expires_at,
        )


@pytest.mark.parametrize(
    "checked_at,error",
    [
        (REVIEWED_AT - timedelta(seconds=1), "not yet valid"),
        (EXPIRES_AT, "expired"),
    ],
)
def test_verifier_enforces_freshness(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    checked_at: Any,
    error: str,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    with pytest.raises(ReferenceValidationResultReviewError, match=error):
        _verify(
            monkeypatch,
            receipts.accepted,
            attestation,
            checked_at=checked_at,
        )


@pytest.mark.parametrize(
    "revocation_field,receipt_field,error",
    [
        (
            "revoked_pre_execution_review_attestation_sha256s",
            "review_attestation_sha256",
            "pre-execution review",
        ),
        (
            "revoked_authorization_receipt_sha256s",
            "authorization_receipt_sha256",
            "authorization receipt",
        ),
        (
            "revoked_execution_environment_receipt_sha256s",
            "execution_environment_receipt_sha256",
            "execution environment",
        ),
        (
            "revoked_result_receipt_sha256s",
            "receipt_sha256",
            "result receipt",
        ),
        (
            "superseded_result_receipt_sha256s",
            "receipt_sha256",
            "superseded",
        ),
    ],
)
def test_verifier_rechecks_upstream_result_revocation_and_supersession(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    revocation_field: str,
    receipt_field: str,
    error: str,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    with pytest.raises(ReferenceValidationResultReviewError, match=error):
        _verify(
            monkeypatch,
            receipts.accepted,
            attestation,
            **{revocation_field: (receipts.accepted[receipt_field],)},
        )


@pytest.mark.parametrize(
    "field,error",
    [
        ("revoked_result_review_attestation_sha256s", "externally revoked"),
        ("superseded_result_review_attestation_sha256s", "externally superseded"),
    ],
)
def test_verifier_rechecks_result_review_revocation_and_supersession(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    error: str,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    with pytest.raises(ReferenceValidationResultReviewError, match=error):
        _verify(
            monkeypatch,
            receipts.accepted,
            attestation,
            **{field: (attestation["attestation_sha256"],)},
        )


def test_every_attestation_and_verification_claim_flag_remains_false(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    for field in (
        "production_validation_evidence",
        "force_or_energy_validated",
        "scientific_validation_recommended",
        "parameter_fitting_proposal_recommended",
        "parameter_fitting_recommended",
        "scientifically_validated",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert attestation[field] is False
    verification = _verify(monkeypatch, receipts.accepted, attestation).to_dict()
    for field in (
        "production_validation_evidence",
        "force_or_energy_validated",
        "scientifically_validated",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "claim_safe",
    ):
        assert verification[field] is False


def test_noncanonical_and_duplicate_key_attestation_transport_is_rejected(
    receipts: ReceiptBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attestation = _build(monkeypatch, receipts.accepted)
    raw = json.dumps(attestation, indent=2).encode("utf-8")
    with pytest.raises(ReferenceValidationResultReviewError, match="not canonical"):
        _verify(monkeypatch, receipts.accepted, raw)  # type: ignore[arg-type]
    duplicate = b'{"x":1,"x":2}'
    with pytest.raises(
        ReferenceValidationResultReviewError, match="duplicate JSON key"
    ):
        module._load_attestation(duplicate)


def test_result_reviewer_trust_anchor_rejects_invalid_key_material() -> None:
    with pytest.raises(ReferenceValidationResultReviewError, match="32 bytes"):
        ReferenceValidationResultReviewerTrustAnchor(
            RESULT_REVIEWER_IDENTITY_SHA256,
            b"short",
        )


def test_source_contains_no_bundled_private_or_trusted_result_key() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert RESULT_REVIEW_SIGNING_KEY.hex() not in source
    assert "BEGIN PRIVATE KEY" not in source
    assert hashlib.sha256(RESULT_REVIEW_VERIFICATION_KEY).hexdigest() not in source
