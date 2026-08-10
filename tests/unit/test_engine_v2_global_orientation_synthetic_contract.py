from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_global_orientation_synthetic_contract import (
    GlobalOrientationSyntheticContractError,
    load_contract,
    verify_contract,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_PATH = (
    _REPO_ROOT / "config/engine_v2_global_orientation_synthetic_contract.json"
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


def test_current_synthetic_global_orientation_contract_verifies() -> None:
    observed = verify_contract(_contract())
    assert len(observed) == 64
    receipt = _contract()["orientation_receipt"]
    assert receipt["source_seed_sha256_required"] is True
    assert receipt["raw_sequence_indices_required"] is True
    assert receipt["accepted_sequence_indices_required"] is True
    assert receipt["coverage_statistics_required"] is True
    assert receipt["duplicate_statistics_required"] is True


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
