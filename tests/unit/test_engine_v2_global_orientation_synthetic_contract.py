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
