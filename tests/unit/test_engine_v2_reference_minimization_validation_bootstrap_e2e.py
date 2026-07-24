from __future__ import annotations

from io import BytesIO
import json
import time
from types import SimpleNamespace

import pytest

import betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap as bootstrap
import betelgeuze_engine_v2.physics.reference_minimization_validation_runner as runner


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


def test_bootstrap_keeps_scientific_execution_in_the_verified_runner() -> None:
    assert not hasattr(bootstrap, "_execute_verified_request")
    assert callable(runner._main_from_canonical_request)


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

    state = (
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
        "bootstrap",
        "/checkout",
        ("/dependencies",),
        ("/dependencies",),
        "7" * 64,
        "8" * 64,
    )
    finder = SimpleNamespace(
        verify_repository_binding=lambda: observed.append("finder")
    )
    monkeypatch.setattr(
        bootstrap,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: state,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(bootstrap, "_require_verified_source_finder", lambda: finder)
    monkeypatch.setattr(bootstrap, "_read_bootstrap_request", lambda: (raw, request))
    monkeypatch.setattr(
        bootstrap,
        "_require_signed_clean_checkout_before_import",
        lambda repository_root, supplied, **kwargs: (
            observed.append("source")
            or ({"verified": True}, dict(DEPENDENCIES), "9" * 64)
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_observed_dependency_artifact_rows_before_import",
        lambda *args, **kwargs: observed.append("dependencies"),
    )
    def execute(supplied_raw: bytes) -> int:
        assert supplied_raw == raw
        observed.append("execute")
        output.write(bootstrap._canonical_bytes(response) + b"\n")
        return 0

    monkeypatch.setattr(runner, "_main_from_canonical_request", execute)
    monkeypatch.setattr(bootstrap.sys, "stdout", SimpleNamespace(buffer=output))

    assert bootstrap.main() == 0
    assert observed == ["source", "dependencies", "finder", "execute"]
    assert output.getvalue() == bootstrap._canonical_bytes(response) + b"\n"
    assert json.loads(output.getvalue()) == response


def test_bootstrap_main_returns_two_and_emits_nothing_on_execution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = BytesIO()
    monkeypatch.setattr(bootstrap.sys, "stdout", SimpleNamespace(buffer=output))
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(
        bootstrap,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("preflight failed")),
    )

    assert bootstrap.main() == 2
    assert output.getvalue() == b""
