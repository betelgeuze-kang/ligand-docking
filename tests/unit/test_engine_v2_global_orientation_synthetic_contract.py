from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_global_orientation_synthetic_contract import (
    EXPECTED_ADVERSARIAL_FIXTURE_IDS,
    GlobalOrientationSyntheticContractError,
    load_contract,
    load_fixture_suite,
    verify_contract,
    verify_fixture_suite,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_PATH = (
    _REPO_ROOT / "config/engine_v2_global_orientation_synthetic_contract.json"
)
_FIXTURE_PATH = (
    _REPO_ROOT / "tests/fixtures/engine_v2_global_orientation_adversarial_v1.json"
)


def _contract() -> dict[str, object]:
    return load_contract(_CONTRACT_PATH)


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("contract_sha256", None)
    changed["contract_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return changed


def _reseal_fixture_suite(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("suite_sha256", None)
    changed["suite_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return changed


def test_current_synthetic_global_orientation_contract_verifies() -> None:
    observed = verify_contract(_contract())
    assert len(observed) == 64
    receipt = _contract()["orientation_receipt"]
    assert receipt["source_seed_sha256_required"] is True
    assert receipt["raw_sequence_indices_required"] is True
    assert receipt["accepted_sequence_indices_required"] is True
    assert receipt["coverage_statistics_required"] is True
    assert receipt["duplicate_statistics_required"] is True
    fixture_contract = _contract()["adversarial_fixture_suite"]
    assert tuple(fixture_contract["ordered_fixture_ids"]) == (
        EXPECTED_ADVERSARIAL_FIXTURE_IDS
    )
    assert fixture_contract["portable_observation_receipts_required"] is True
    assert (
        fixture_contract["runtime_float_fields_forbidden_in_portable_receipt"] is True
    )
    assert fixture_contract["invariant_rederivation_required"] is True


def test_current_adversarial_fixture_suite_verifies() -> None:
    suite = load_fixture_suite(_FIXTURE_PATH)

    assert verify_fixture_suite(suite) == suite["suite_sha256"]
    assert tuple(fixture["fixture_id"] for fixture in suite["fixtures"]) == (
        EXPECTED_ADVERSARIAL_FIXTURE_IDS
    )


def test_resealed_native_pose_input_escalation_fails_closed() -> None:
    changed = _contract()
    changed["algorithm"]["native_pose_input_allowed"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="native_pose_input_allowed",
    ):
        verify_contract(changed)


def test_resealed_product_authority_escalation_fails_closed() -> None:
    changed = _contract()
    changed["authority"]["product_execution_authorized"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="product_execution_authorized",
    ):
        verify_contract(changed)


def test_failure_class_drift_fails_closed() -> None:
    changed = _contract()
    changed["metrics"]["failure_classes"] = [
        "success",
        "ranking_failure",
        "proposal_failure",
        "validity_failure",
    ]
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="failure class order",
    ):
        verify_contract(changed)


def test_resealed_source_rederivation_requirement_cannot_be_disabled() -> None:
    changed = _contract()
    changed["algorithm"]["source_rederivation_evidence_required"] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="source_rederivation_evidence_required",
    ):
        verify_contract(changed)


def test_resealed_full_observation_requirement_cannot_be_disabled() -> None:
    changed = _contract()
    changed["metrics"]["full_observation_rederivation_required"] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="full_observation_rederivation_required",
    ):
        verify_contract(changed)


@pytest.mark.parametrize(
    "key",
    (
        "source_seed_sha256_required",
        "raw_sequence_indices_required",
        "accepted_sequence_indices_required",
        "canonical_quaternion_binary64_hex_required",
        "quaternion_sign_canonicalization_required",
        "coverage_statistics_required",
        "duplicate_statistics_required",
    ),
)
def test_resealed_orientation_receipt_requirement_cannot_be_disabled(
    key: str,
) -> None:
    changed = _contract()
    changed["orientation_receipt"][key] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match=key,
    ):
        verify_contract(changed)


def test_resealed_source_seed_binding_field_drift_fails_closed() -> None:
    changed = _contract()
    changed["orientation_receipt"]["source_seed_binding_fields"] = [
        "source_receipt_sha256",
        "ligand_input_sha256",
        "profile_id",
    ]
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="source seed binding fields",
    ):
        verify_contract(changed)


def test_resealed_duplicate_threshold_drift_fails_closed() -> None:
    changed = _contract()
    changed["orientation_receipt"][
        "geodesic_duplicate_threshold_radians_binary64_hex"
    ] = (1.0e-8).hex()
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="duplicate threshold drifted",
    ):
        verify_contract(changed)


def test_resealed_coverage_statistic_field_drift_fails_closed() -> None:
    changed = _contract()
    changed["orientation_receipt"]["coverage_statistic_fields"] = [
        "requested_orientation_count",
        "raw_sequence_count",
        "accepted_sequence_count",
        "duplicate_orientation_count",
    ]
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="coverage statistic fields",
    ):
        verify_contract(changed)


@pytest.mark.parametrize(
    "key",
    (
        "index_stable_orientation_sequence_required",
        "orientation_count_prefix_invariant_required",
        "source_dependent_seed_required",
    ),
)
def test_resealed_index_stability_requirement_cannot_be_disabled(
    key: str,
) -> None:
    changed = _contract()
    changed["algorithm"][key] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match=key,
    ):
        verify_contract(changed)


def test_resealed_fixture_id_drift_fails_closed() -> None:
    changed = _contract()
    changed["adversarial_fixture_suite"]["ordered_fixture_ids"][-1] = (
        "result_dependent_translation"
    )
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="fixture contract IDs",
    ):
        verify_contract(changed)


def test_resealed_fixture_file_hash_drift_fails_closed() -> None:
    changed = _contract()
    changed["adversarial_fixture_suite"]["fixture_file_sha256"] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="fixture file SHA-256 drifted",
    ):
        verify_contract(changed)


def test_resealed_fixture_invariant_drift_fails_closed() -> None:
    changed = load_fixture_suite(_FIXTURE_PATH)
    changed["fixtures"][0]["required_invariants"][-1] = (
        "accept_every_channel_orientation"
    )
    changed = _reseal_fixture_suite(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="fixture invariant set drifted",
    ):
        verify_fixture_suite(changed)


def test_resealed_fixture_authority_escalation_fails_closed() -> None:
    changed = load_fixture_suite(_FIXTURE_PATH)
    changed["authority"]["product_execution_authorized"] = True
    changed = _reseal_fixture_suite(changed)

    with pytest.raises(
        GlobalOrientationSyntheticContractError,
        match="fixture suite authority must remain false",
    ):
        verify_fixture_suite(changed)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda fixture: fixture["ligand_coordinates"][0].append(0.0),
            "ligand_coordinates.*exactly three",
        ),
        (
            lambda fixture: fixture["pocket_normal"].__setitem__(0, "infinite"),
            "pocket_normal.*finite number",
        ),
        (
            lambda fixture: fixture["config"].__setitem__(
                "translation_shell_radii", [1.0, 1.0]
            ),
            "translation shell radii must be unique and increasing",
        ),
        (
            lambda fixture: fixture.__setitem__(
                "expected_candidate_slot_count",
                fixture["expected_candidate_slot_count"] + 1,
            ),
            "candidate count does not match config",
        ),
    ),
)
def test_resealed_malformed_fixture_geometry_or_config_fails_closed(
    mutation,
    message: str,
) -> None:
    changed = load_fixture_suite(_FIXTURE_PATH)
    mutation(changed["fixtures"][0])
    changed = _reseal_fixture_suite(changed)

    with pytest.raises(GlobalOrientationSyntheticContractError, match=message):
        verify_fixture_suite(changed)
