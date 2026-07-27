from __future__ import annotations

import hashlib
import subprocess
from types import SimpleNamespace

import pytest

from betelgeuze_engine_v2.physics import (
    reference_minimization_validation_authorization as authorization,
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
    projection = authorization._receipt_projection(
        review=SimpleNamespace(
            attestation_sha256="1" * 64,
            implementation_author_identity_sha256="2" * 64,
            independent_reviewer_identity_sha256="3" * 64,
        ),
        authorization_operator_identity_sha256="b" * 64,
        authorization_key_id="operator-key",
        issued_at_utc="2026-07-18T00:00:00Z",
        expires_at_utc="2026-07-18T01:00:00Z",
        authorization_nonce_sha256=nonce,
        code_commit_sha="d" * 40,
        runner_source_sha256="e" * 64,
        dependency_artifact_sha256_rows=_dependency_rows(digest_character),
    )
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


def test_bootstrap_authorization_schema_matches_the_canonical_receipt_builder() -> None:
    receipt = _signed_authorization_receipt()

    assert bootstrap._REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_FIELDS == (
        set(receipt)
    )


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


@pytest.mark.parametrize("mutation", ("add", "remove"))
def test_bootstrap_authorization_schema_rejects_unknown_or_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    signature_verification_attempted = False

    def observe_signature_verification(
        message: bytes,
        signature: str,
        key: bytes,
    ) -> bool:
        del message, signature, key
        nonlocal signature_verification_attempted
        signature_verification_attempted = True
        return True

    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_operator_keys",
        lambda: {"operator-key": ("b" * 64, b"k" * 32)},
    )
    monkeypatch.setattr(
        bootstrap,
        "_verify_ed25519_with_trusted_openssl",
        observe_signature_verification,
    )
    receipt = _signed_authorization_receipt()
    if mutation == "add":
        receipt["extension"] = {"opens_execution": False}
    else:
        receipt.pop("runner_source_sha256")
    request = {
        "authorization_receipt": receipt,
        "authorization_nonce_sha256": "c" * 64,
    }

    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="not the exact schema",
    ):
        bootstrap._require_bootstrap_authorization_signature(
            request,
            expected_commit="d" * 40,
            expected_source="e" * 64,
        )

    assert signature_verification_attempted is False


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


@pytest.mark.parametrize(
    "path",
    (
        b"torch.so",
        b"package/__init__.py",
        b"package/cache.PYC",
        b"native/extension.pyd",
        b"native/extension.dll",
        b"native/extension.dylib",
    ),
)
def test_ignored_importable_checkout_paths_include_python_and_native_modules(
    path: bytes,
) -> None:
    assert bootstrap._ignored_importable_checkout_paths(path + b"\0") == (path,)


def test_ignored_non_importable_checkout_paths_remain_allowed() -> None:
    assert bootstrap._ignored_importable_checkout_paths(
        b"reports/result.json\0artifacts/receipt.txt\0"
    ) == ()


def test_ignored_checkout_path_inventory_must_be_nul_terminated() -> None:
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="inventory is invalid",
    ):
        bootstrap._ignored_importable_checkout_paths(b"torch.so")


def test_clean_checkout_rejects_an_ignored_importable_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_commit = "d" * 40
    expected_source = "e" * 64
    monkeypatch.setattr(
        bootstrap,
        "_require_external_private_root",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_bootstrap_authorization_signature",
        lambda *args, **kwargs: _dependency_rows(),
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_trusted_root_executable",
        lambda *args, **kwargs: "/usr/bin/git",
    )
    monkeypatch.setattr(
        bootstrap,
        "reference_minimization_validation_execution_source_sha256",
        lambda: expected_source,
    )

    def git_result(command: list[str], **kwargs: object) -> SimpleNamespace:
        del kwargs
        if "rev-parse" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=expected_commit.encode("ascii") + b"\n",
            )
        if "status" in command or "replace" in command:
            return SimpleNamespace(returncode=0, stdout=b"")
        if "ls-files" in command:
            return SimpleNamespace(returncode=0, stdout=b"torch.so\0")
        raise AssertionError(f"unexpected Git command: {command!r}")

    monkeypatch.setattr(subprocess, "run", git_result)
    request = {
        "reservation_root": "/private/reservations",
        "artifact_output_root": "/private/artifacts",
        "expected_code_commit_sha": expected_commit,
        "expected_runner_source_sha256": expected_source,
    }

    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="not the signed clean source",
    ):
        bootstrap._require_signed_clean_checkout_before_import(
            "/checkout",
            request,
        )
