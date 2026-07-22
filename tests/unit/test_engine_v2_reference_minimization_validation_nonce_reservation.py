from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    MinimizationAuthorizationOperatorTrustAnchor,
    build_signed_reference_minimization_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_nonce_reservation import (
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V4,
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V3,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES,
    ReferenceMinimizationValidationNonceAlreadyReservedError,
    ReferenceMinimizationValidationNonceReservationError,
    read_reference_minimization_validation_nonce_reservation,
    reference_minimization_validation_nonce_reservation_contract_decision,
    reference_minimization_validation_nonce_reservation_contract_document,
    require_reference_minimization_validation_nonce_reservation_contract_document,
    reserve_reference_minimization_validation_authorization_nonce,
    verify_reference_minimization_validation_nonce_reservation_record,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
    build_signed_reference_minimization_validation_review_attestation,
)


AUTHOR = "a" * 64
REVIEWER = "b" * 64
OPERATOR = "c" * 64
REVIEW_NONCE = "d" * 64
AUTH_NONCE = "e" * 64
REVIEW_KEY_ID = "minimization-reviewer-2026-07"
OPERATOR_KEY_ID = "minimization-operator-2026-07"
REVIEW_KEY = bytes.fromhex("11" * 32)
OPERATOR_KEY = bytes.fromhex("21" * 32)
REVIEW_PUBLIC_KEY = ed25519_public_key_bytes(REVIEW_KEY)
OPERATOR_PUBLIC_KEY = ed25519_public_key_bytes(OPERATOR_KEY)
REVIEWED_AT = datetime(2026, 7, 18, 1, 0, tzinfo=timezone.utc)
REVIEW_EXPIRES = REVIEWED_AT + timedelta(days=7)
ISSUED_AT = REVIEWED_AT + timedelta(hours=2)
EXPIRES_AT = ISSUED_AT + timedelta(hours=4)
RESERVED_AT = ISSUED_AT + timedelta(hours=1)
CODE_COMMIT = "1" * 40
RUNNER_SOURCE = "2" * 64
DEPENDENCIES = {
    "cryptography-distribution": "3" * 64,
    "numpy-distribution": "4" * 64,
    "openssl-executable": "5" * 64,
    "python-runtime-executable": "6" * 64,
    "python-standard-library": "7" * 64,
    "torch-distribution": "8" * 64,
}


def _review() -> dict[str, object]:
    return build_signed_reference_minimization_validation_review_attestation(
        implementation_author_identity_sha256=AUTHOR,
        independent_reviewer_identity_sha256=REVIEWER,
        reviewer_key_id=REVIEW_KEY_ID,
        signing_key=REVIEW_KEY,
        reviewed_at=REVIEWED_AT,
        expires_at=REVIEW_EXPIRES,
        nonce_sha256=REVIEW_NONCE,
    )


def _receipt(review: object | None = None) -> dict[str, object]:
    return build_signed_reference_minimization_validation_authorization_receipt(
        review_attestation=review or _review(),  # type: ignore[arg-type]
        trusted_reviewer_keys={REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(REVIEWER, REVIEW_PUBLIC_KEY)},
        expected_implementation_author_identity_sha256=AUTHOR,
        authorization_operator_identity_sha256=OPERATOR,
        authorization_key_id=OPERATOR_KEY_ID,
        signing_key=OPERATOR_KEY,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        authorization_nonce_sha256=AUTH_NONCE,
        code_commit_sha=CODE_COMMIT,
        runner_source_sha256=RUNNER_SOURCE,
        dependency_artifact_sha256_rows=DEPENDENCIES,
    )


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "reservations"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _reserve(root: Path, **overrides: object):
    values: dict[str, object] = {
        "reservation_root": root,
        "authorization_receipt": _receipt(),
        "review_attestation": _review(),
        "trusted_reviewer_keys": {
            REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(REVIEWER, REVIEW_PUBLIC_KEY)
        },
        "expected_implementation_author_identity_sha256": AUTHOR,
        "trusted_operator_keys": {
            OPERATOR_KEY_ID: MinimizationAuthorizationOperatorTrustAnchor(OPERATOR, OPERATOR_PUBLIC_KEY)
        },
        "reserved_at": RESERVED_AT,
        "expected_code_commit_sha": CODE_COMMIT,
        "expected_runner_source_sha256": RUNNER_SOURCE,
        "expected_dependency_artifact_sha256_rows": DEPENDENCIES,
    }
    values.update(overrides)
    return reserve_reference_minimization_validation_authorization_nonce(  # type: ignore[arg-type]
        **values
    )


def test_contract_is_frozen_and_current_decision_stays_closed() -> None:
    contract = reference_minimization_validation_nonce_reservation_contract_document()
    decision = reference_minimization_validation_nonce_reservation_contract_decision()

    assert contract["schema_id"] == REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID
    assert contract["contract_sha256"] == (FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256)
    assert contract["superseded_contract_sha256"] == (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V4
    )
    assert (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V3
        == "c5397b6ea8ea1d8291630dc5b5a0f0761133509cc3d1b5ce3403464a498635a3"
    )
    assert contract["dependencies"]["authorization_contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    )
    assert contract["storage_contract"]["root_mode"] == "0700"
    assert contract["storage_contract"]["record_mode"] == "0600"
    assert contract["storage_contract"]["duplicate_nonce_fails_closed"] is True
    assert contract["storage_contract"]["release_or_delete_api_present"] is False
    assert contract["claim_policy"]["scientifically_validated"] is False
    assert contract["claim_policy"]["claim_safe"] is False
    assert require_reference_minimization_validation_nonce_reservation_contract_document(contract) == contract
    assert decision["atomic_nonce_reservation_primitive_implemented"] is True
    assert decision["authorization_nonce_reserved"] is False
    assert decision["validation_execution_authorized"] is False


def test_contract_rejects_tamper() -> None:
    contract = deepcopy(reference_minimization_validation_nonce_reservation_contract_document())
    contract["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="does not match the frozen record",
    ):
        require_reference_minimization_validation_nonce_reservation_contract_document(contract)


def test_reservation_reverifies_and_persists_canonical_private_record(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    reservation = _reserve(root)
    record = root / f"{AUTH_NONCE}.json"

    assert reservation.reservation_persisted is True
    assert reservation.validation_execution_authorized is False
    assert reservation.validation_results_collected is False
    assert reservation.parameter_fitting_authorized is False
    assert "execution_environment_receipt_missing" in reservation.blockers
    assert record.is_file()
    record_stat = record.stat()
    assert stat.S_IMODE(record_stat.st_mode) == 0o600
    assert record_stat.st_nlink == 1
    raw = record.read_bytes()
    assert len(raw) <= REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES
    assert raw.endswith(b"\n")
    assert b"review-key-material" not in raw
    assert b"operator-key-material" not in raw

    loaded = read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=AUTH_NONCE)
    assert loaded == reservation
    assert loaded.reservation_record_sha256 == reservation.reservation_record_sha256


def test_duplicate_reservation_is_atomic_and_keeps_first_record(tmp_path: Path) -> None:
    root = _root(tmp_path)
    first = _reserve(root)
    before = (root / f"{AUTH_NONCE}.json").read_bytes()
    with pytest.raises(
        ReferenceMinimizationValidationNonceAlreadyReservedError,
        match="already reserved",
    ):
        _reserve(root)
    assert (root / f"{AUTH_NONCE}.json").read_bytes() == before
    assert (
        read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=AUTH_NONCE) == first
    )


def test_concurrent_duplicate_has_exactly_one_winner(tmp_path: Path) -> None:
    root = _root(tmp_path)

    def attempt() -> str:
        try:
            _reserve(root)
        except ReferenceMinimizationValidationNonceAlreadyReservedError:
            return "duplicate"
        return "reserved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: attempt(), range(2)))
    assert outcomes == ["duplicate", "reserved"]


def test_invalid_signed_chain_or_consumed_nonce_creates_no_path(tmp_path: Path) -> None:
    root = _root(tmp_path)
    tampered = deepcopy(_receipt())
    tampered["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="authorization verification failed",
    ):
        _reserve(root, authorization_receipt=tampered)
    assert list(root.iterdir()) == []

    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="authorization verification failed",
    ):
        _reserve(root, externally_consumed_nonce_sha256s=(AUTH_NONCE,))
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("mode", (0o755, 0o750, 0o700 | stat.S_ISGID))
def test_reservation_rejects_nonprivate_root_mode(tmp_path: Path, mode: int) -> None:
    root = _root(tmp_path)
    root.chmod(mode)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="mode-0700",
    ):
        _reserve(root)
    assert list(root.iterdir()) == []


def test_reservation_rejects_relative_parent_and_symlink_roots(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="absolute POSIX path",
    ):
        _reserve(Path("relative-reservations"))
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="without '..'",
    ):
        _reserve(Path(f"{root}/../reservations"))

    link = tmp_path / "reservation-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="traverses a symlink",
    ):
        _reserve(link)
    assert list(root.iterdir()) == []


def test_reader_rejects_tamper_hardlink_and_filename_crosswire(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _reserve(root)
    record = root / f"{AUTH_NONCE}.json"
    payload = json.loads(record.read_text(encoding="ascii"))
    payload["claim_safe"] = True
    record.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    record.chmod(0o600)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="fixed fields drifted",
    ):
        read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=AUTH_NONCE)

    record.unlink()
    _reserve(root)
    hardlink = root / "hardlink.json"
    os.link(record, hardlink)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="single-link regular file",
    ):
        read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=AUTH_NONCE)
    hardlink.unlink()

    other_nonce = "f" * 64
    other = root / f"{other_nonce}.json"
    record.rename(other)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="cross-wired",
    ):
        read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=other_nonce)


def test_reader_rejects_symlink_and_noncanonical_record(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _reserve(root)
    record = root / f"{AUTH_NONCE}.json"
    target = root / "target.json"
    record.rename(target)
    record.symlink_to(target.name)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="cannot be opened securely",
    ):
        read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=AUTH_NONCE)

    record.unlink()
    target.rename(record)
    payload = json.loads(record.read_text(encoding="ascii"))
    record.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    record.chmod(0o600)
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="bytes are not canonical",
    ):
        read_reference_minimization_validation_nonce_reservation(root, authorization_nonce_sha256=AUTH_NONCE)


def test_reader_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    root = _root(tmp_path)
    path = root / f"{AUTH_NONCE}.json"
    try:
        os.mkfifo(path, mode=0o600)
    except (AttributeError, OSError):
        pytest.skip("POSIX FIFO creation unavailable")
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="single-link regular file",
    ):
        read_reference_minimization_validation_nonce_reservation(
            root,
            authorization_nonce_sha256=AUTH_NONCE,
        )


def test_exact_raw_record_verifier_rejects_nonbytes_and_bool_integer_alias(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    expected = _reserve(root)
    raw = (root / f"{AUTH_NONCE}.json").read_bytes()
    assert (
        verify_reference_minimization_validation_nonce_reservation_record(
            raw,
            expected_authorization_nonce_sha256=AUTH_NONCE,
        )
        == expected
    )
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="must be bytes",
    ):
        verify_reference_minimization_validation_nonce_reservation_record(  # type: ignore[arg-type]
            raw.decode("ascii"),
            expected_authorization_nonce_sha256=AUTH_NONCE,
        )
    payload = json.loads(raw)
    payload["reservation_persisted"] = 1
    aliased = (
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="fixed fields drifted",
    ):
        verify_reference_minimization_validation_nonce_reservation_record(
            aliased,
            expected_authorization_nonce_sha256=AUTH_NONCE,
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"value":' + b"1" * 5_000 + b"}\n",
        b'{"value":' + b"[" * 1_100 + b"0" + b"]" * 1_100 + b"}\n",
    ],
)
def test_exact_raw_record_verifier_wraps_json_decoder_limits(raw: bytes) -> None:
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="must be canonical ASCII JSON",
    ):
        verify_reference_minimization_validation_nonce_reservation_record(
            raw,
            expected_authorization_nonce_sha256=AUTH_NONCE,
        )


def test_contract_rejects_bool_integer_alias() -> None:
    document = reference_minimization_validation_nonce_reservation_contract_document()
    document["claim_policy"]["claim_safe"] = 0
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="does not match",
    ):
        require_reference_minimization_validation_nonce_reservation_contract_document(document)

    deeply_nested: dict[str, object] = {}
    cursor = deeply_nested
    for _ in range(1_200):
        child: dict[str, object] = {}
        cursor["next"] = child
        cursor = child
    with pytest.raises(
        ReferenceMinimizationValidationNonceReservationError,
        match="not canonical JSON",
    ):
        require_reference_minimization_validation_nonce_reservation_contract_document(deeply_nested)


def test_module_exposes_no_release_or_delete_api() -> None:
    import betelgeuze_engine_v2.physics.reference_minimization_validation_nonce_reservation as module

    exported = set(module.__all__)
    assert not any("release" in name or "delete" in name for name in exported)
