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




def _trust_payload(
    *,
    revoked_authorizations: tuple[str, ...] = (),
    revoked_reviews: tuple[str, ...] = (),
    conflicting_nonces: tuple[str, ...] = (),
    revoked_network: tuple[str, ...] = (),
    superseded_operators: tuple[str, ...] = (),
    superseded_reviewers: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID,
        "reviewer_keys": [],
        "operator_keys": [
            {
                "key_id": "operator-key",
                "operator_identity_sha256": "b" * 64,
                "verification_key_hex": "6b" * 32,
            }
        ],
        "revoked_authorization_receipt_sha256s": list(revoked_authorizations),
        "revoked_review_attestation_sha256s": list(revoked_reviews),
        "externally_conflicting_nonce_sha256s": list(conflicting_nonces),
        "revoked_network_attestation_sha256s": list(revoked_network),
        "superseded_operator_key_ids": list(superseded_operators),
        "superseded_reviewer_key_ids": list(superseded_reviewers),
        "minimum_authorization_receipt_schema_id": (
            bootstrap._REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        ),
        "minimum_review_attestation_schema_id": (
            bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
        ),
    }


def _revocation_state(payload: dict[str, object]) -> dict[str, tuple[str, ...]]:
    return {
        name: tuple(payload[name])
        for name in (
            "revoked_authorization_receipt_sha256s",
            "revoked_review_attestation_sha256s",
            "externally_conflicting_nonce_sha256s",
            "revoked_network_attestation_sha256s",
            "superseded_operator_key_ids",
            "superseded_reviewer_key_ids",
        )
    }

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
        lambda payload=None: {"operator-key": ("b" * 64, b"k" * 32)},
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
        trust_payload=_trust_payload(),
        trusted_revocation_state=_revocation_state(_trust_payload()),
    ) == _dependency_rows()


def test_bootstrap_authorization_binds_the_request_nonce_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_operator_keys",
        lambda payload=None: {"operator-key": ("b" * 64, b"k" * 32)},
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
            trust_payload=_trust_payload(),
            trusted_revocation_state=_revocation_state(_trust_payload()),
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


def test_preimport_revocation_state_rejects_hidden_or_added_entries() -> None:
    review_sha = "7" * 64
    network_sha = "8" * 64
    payload = _trust_payload(revoked_reviews=(review_sha,))
    request = {
        "authorization_nonce_sha256": "c" * 64,
        "review_attestation": {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
            "attestation_sha256": "9" * 64,
        },
        "network_isolation_attestation": {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID,
            "attestation_sha256": network_sha,
        },
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="does not match the trusted store",
    ):
        bootstrap._require_trusted_revocation_state(request, payload)


def test_preimport_revocation_state_rejects_conflicting_nonce_and_revoked_attestations() -> None:
    nonce = "c" * 64
    review_sha = "7" * 64
    network_sha = "8" * 64
    request = {
        "authorization_nonce_sha256": nonce,
        "review_attestation": {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
            "attestation_sha256": review_sha,
        },
        "network_isolation_attestation": {
            "schema_id": bootstrap._REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID,
            "attestation_sha256": network_sha,
        },
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [review_sha],
        "externally_conflicting_nonce_sha256s": [nonce],
        "revoked_network_attestation_sha256s": [network_sha],
    }
    payload = _trust_payload(
        revoked_reviews=(review_sha,),
        conflicting_nonces=(nonce,),
        revoked_network=(network_sha,),
    )
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="nonce is externally conflicting",
    ):
        bootstrap._require_trusted_revocation_state(request, payload)

    request["externally_conflicting_nonce_sha256s"] = []
    payload = _trust_payload(
        revoked_reviews=(review_sha,),
        revoked_network=(network_sha,),
    )
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="review attestation is externally revoked",
    ):
        bootstrap._require_trusted_revocation_state(request, payload)


def test_authorization_rejects_revoked_receipt_superseded_key_and_schema_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_operator_keys",
        lambda payload=None: {"operator-key": ("b" * 64, b"k" * 32)},
    )
    monkeypatch.setattr(
        bootstrap,
        "_verify_ed25519_with_trusted_openssl",
        lambda message, signature, key: True,
    )
    request = {
        "authorization_receipt": _signed_authorization_receipt(),
        "authorization_nonce_sha256": "c" * 64,
    }
    receipt_sha = request["authorization_receipt"]["receipt_sha256"]
    payload = _trust_payload(revoked_authorizations=(receipt_sha,))
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="externally revoked",
    ):
        bootstrap._require_bootstrap_authorization_signature(
            request,
            expected_commit="d" * 40,
            expected_source="e" * 64,
            trust_payload=payload,
            trusted_revocation_state=_revocation_state(payload),
        )

    payload = _trust_payload(superseded_operators=("operator-key",))
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="key is superseded",
    ):
        bootstrap._require_bootstrap_authorization_signature(
            request,
            expected_commit="d" * 40,
            expected_source="e" * 64,
            trust_payload=payload,
            trusted_revocation_state=_revocation_state(payload),
        )

    downgraded = _signed_authorization_receipt()
    downgraded["schema_id"] = (
        "betelgeuze.engine_v2_reference_minimization_validation_authorization_receipt/0.9.0"
    )
    request["authorization_receipt"] = downgraded
    payload = _trust_payload()
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="source binding",
    ):
        bootstrap._require_bootstrap_authorization_signature(
            request,
            expected_commit="d" * 40,
            expected_source="e" * 64,
            trust_payload=payload,
            trusted_revocation_state=_revocation_state(payload),
        )
