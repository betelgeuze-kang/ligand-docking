from __future__ import annotations

from io import BytesIO
import json
from types import SimpleNamespace

import pytest

import betelgeuze_engine_v2.physics as physics
import betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap as bootstrap


DEPENDENCIES = {
    artifact_id: character * 64
    for artifact_id, character in zip(
        bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
        "abcdef",
        strict=True,
    )
}


def _request() -> dict[str, object]:
    return {
        "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": "/private/reservation",
        "artifact_output_root": "/private/artifacts",
        "authorization_nonce_sha256": "1" * 64,
        "authorization_receipt": {"signed": True},
        "review_attestation": {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
            "attestation_sha256": "7" * 64,
        },
        "expected_implementation_author_identity_sha256": "2" * 64,
        "network_isolation_attestation": {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID,
            "attestation_sha256": "8" * 64,
        },
        "expected_code_commit_sha": "3" * 40,
        "expected_runner_source_sha256": "4" * 64,
        "expected_dependency_artifact_sha256_rows": dict(DEPENDENCIES),
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }


def test_verified_request_runs_environment_runner_and_writer_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    environment = SimpleNamespace(receipt_sha256="5" * 64)
    observation = SimpleNamespace(to_dict=lambda: {"observation": "bounded"})
    result = SimpleNamespace(receipt_sha256="6" * 64)

    monkeypatch.setattr(
        bootstrap,
        "_configure_deterministic_torch_runtime",
        lambda torch_module: calls.append("determinism"),
    )
    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_trust_store_payload",
        lambda: {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID,
            "reviewer_keys": [{}],
            "operator_keys": [{}],
            "revoked_authorization_receipt_sha256s": [],
            "revoked_review_attestation_sha256s": [],
            "externally_conflicting_nonce_sha256s": [],
            "revoked_network_attestation_sha256s": [],
            "superseded_operator_key_ids": [],
            "superseded_reviewer_key_ids": [],
            "minimum_authorization_receipt_schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
            "minimum_review_attestation_schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
        },
    )
    monkeypatch.setattr(
        bootstrap,
        "_runtime_trust_anchors",
        lambda payload, reviewer_class, operator_class: (
            {"reviewer": object()},
            {"operator": object()},
        ),
    )

    def create_environment(*args: object, **kwargs: object) -> object:
        calls.append("environment")
        assert kwargs["expected_dependency_artifact_sha256_rows"] == DEPENDENCIES
        return environment

    def run_matrix(*args: object, **kwargs: object) -> object:
        calls.append("runner")
        assert kwargs["expected_environment_receipt_sha256"] == "5" * 64
        return observation

    def write_result(*args: object, **kwargs: object) -> object:
        calls.append("writer")
        assert args[2] is observation
        return result

    monkeypatch.setattr(
        physics,
        "create_reference_minimization_validation_execution_environment_receipt",
        create_environment,
    )
    monkeypatch.setattr(
        physics,
        "run_bounded_cpu_reference_minimization_validation",
        run_matrix,
    )
    monkeypatch.setattr(
        physics,
        "write_reference_minimization_validation_result_receipt",
        write_result,
    )

    trust_payload = bootstrap._load_bootstrap_trust_store_payload()
    response = bootstrap._execute_verified_request(
        b"ignored",
        _request(),
        expected_trust_store_sha256=bootstrap._sha256(trust_payload),
    )

    assert calls == ["determinism", "environment", "runner", "writer"]
    assert response["environment_receipt_sha256"] == "5" * 64
    assert response["result_receipt_sha256"] == "6" * 64
    assert response["bounded_validation_observation_collected"] is True
    assert response["failure_inclusive_result_receipt_written"] is True
    for field in (
        "production_validation_results_collected",
        "minimization_scientifically_validated",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert response[field] is False


def test_bootstrap_main_emits_one_canonical_response_after_all_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    raw = bootstrap._canonical_bytes(request) + b"\n"
    output = BytesIO()
    response = {
        "schema_id": bootstrap.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "claim_safe": False,
    }
    observed: list[str] = []

    monkeypatch.setattr(
        bootstrap,
        "_prepare_isolated_import_boundary",
        lambda: ("bootstrap", "/checkout", ("/dependencies",), ("/checkout",)),
    )
    monkeypatch.setattr(bootstrap, "_read_bootstrap_request", lambda: (raw, request))
    monkeypatch.setattr(
        bootstrap,
        "_require_signed_clean_checkout_before_import",
        lambda repository_root, supplied: (
            observed.append("source") or (dict(DEPENDENCIES), "9" * 64)
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_observed_dependency_artifact_rows_before_import",
        lambda *args, **kwargs: observed.append("dependencies"),
    )
    monkeypatch.setattr(
        bootstrap,
        "_execute_verified_request",
        lambda supplied_raw, supplied_request, **kwargs: (
            observed.append("execute") or response
        ),
    )
    monkeypatch.setattr(bootstrap.sys, "stdout", SimpleNamespace(buffer=output))

    assert bootstrap.main() == 0
    assert observed == ["source", "dependencies", "execute"]
    assert output.getvalue() == bootstrap._canonical_bytes(response) + b"\n"
    assert json.loads(output.getvalue()) == response


def test_bootstrap_main_returns_two_and_emits_nothing_on_execution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = BytesIO()
    monkeypatch.setattr(bootstrap.sys, "stdout", SimpleNamespace(buffer=output))
    monkeypatch.setattr(
        bootstrap,
        "_prepare_isolated_import_boundary",
        lambda: (_ for _ in ()).throw(RuntimeError("preflight failed")),
    )

    assert bootstrap.main() == 2
    assert output.getvalue() == b""
