from __future__ import annotations

import hashlib

import pytest

from betelgeuze_engine_v2.physics import (
    reference_minimization_validation_bootstrap as bootstrap,
)


def _dependency_rows(digest_character: str = "a") -> dict[str, str]:
    return {
        artifact_id: digest_character * 64
        for artifact_id in bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    }


def _signed_dependency_rows(digest_character: str = "a") -> list[dict[str, str]]:
    return [
        {"artifact_id": artifact_id, "sha256": digest}
        for artifact_id, digest in sorted(_dependency_rows(digest_character).items())
    ]


def _signed_authorization_receipt(
    *,
    nonce: str = "c" * 64,
    digest_character: str = "a",
) -> dict[str, object]:
    projection: dict[str, object] = {
        "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
        "authorization_key_id": "operator-key",
        "authorization_operator_identity_sha256": "b" * 64,
        "authorization_nonce_sha256": nonce,
        "code_commit_sha": "d" * 40,
        "runner_source_sha256": "e" * 64,
        "dependency_artifact_sha256_rows": _signed_dependency_rows(digest_character),
    }
    payload = dict(projection)
    payload["receipt_sha256"] = hashlib.sha256(
        bootstrap._canonical_bytes(projection)
    ).hexdigest()
    payload["signature"] = {
        "algorithm": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
        "key_id": "operator-key",
        "value": "f" * 128,
    }
    return payload


def test_signed_dependency_rows_are_normalized_to_the_required_mapping() -> None:
    assert bootstrap._require_signed_dependency_artifact_rows(
        _signed_dependency_rows()
    ) == _dependency_rows()


@pytest.mark.parametrize(
    "rows",
    (
        _signed_dependency_rows()[:-1],
        [*_signed_dependency_rows(), {"artifact_id": "extra", "sha256": "a" * 64}],
        [*_signed_dependency_rows(), _signed_dependency_rows()[0]],
        [{"artifact_id": "numpy-distribution", "sha256": "not-a-digest"}],
    ),
)
def test_signed_dependency_rows_reject_missing_extra_duplicate_or_invalid_rows(
    rows: list[dict[str, str]],
) -> None:
    with pytest.raises(bootstrap._ReferenceMinimizationValidationBootstrapError):
        bootstrap._require_signed_dependency_artifact_rows(rows)


def test_bootstrap_authorization_returns_only_verified_signed_dependency_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_operator_keys",
        lambda: {"operator-key": ("b" * 64, b"k" * 32)},
    )
    monkeypatch.setattr(
        bootstrap,
        "_verify_ed25519_with_trusted_openssl",
        lambda message, signature, key: bool(message and signature and key),
    )
    request = {
        "authorization_receipt": _signed_authorization_receipt(),
        "authorization_nonce_sha256": "c" * 64,
    }

    assert bootstrap._require_bootstrap_authorization_signature(
        request,
        expected_commit="d" * 40,
        expected_source="e" * 64,
    ) == _dependency_rows()


def test_bootstrap_authorization_binds_the_request_nonce_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_operator_keys",
        lambda: {"operator-key": ("b" * 64, b"k" * 32)},
    )
    monkeypatch.setattr(
        bootstrap,
        "_verify_ed25519_with_trusted_openssl",
        lambda message, signature, key: True,
    )
    request = {
        "authorization_receipt": _signed_authorization_receipt(nonce="c" * 64),
        "authorization_nonce_sha256": "9" * 64,
    }

    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="source binding",
    ):
        bootstrap._require_bootstrap_authorization_signature(
            request,
            expected_commit="d" * 40,
            expected_source="e" * 64,
        )


def test_request_dependency_mismatch_fails_before_loading_the_measurement_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper_load_attempted = False

    def fail_if_helper_is_loaded(*args: object, **kwargs: object) -> object:
        nonlocal helper_load_attempted
        helper_load_attempted = True
        raise AssertionError("measurement helper must not load before signed-row binding")

    monkeypatch.setattr(
        bootstrap.importlib.util,
        "spec_from_file_location",
        fail_if_helper_is_loaded,
    )
    request = {
        "expected_dependency_artifact_sha256_rows": _dependency_rows("9"),
    }

    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="do not match the signed authorization",
    ):
        bootstrap._require_observed_dependency_artifact_rows_before_import(
            "/checkout",
            ("/dependencies",),
            request,
            signed_expected=_dependency_rows("a"),
        )

    assert helper_load_attempted is False
