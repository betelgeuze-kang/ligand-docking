from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_global_orientation_development_protocol import (
    GlobalOrientationDevelopmentProtocolError,
    load_protocol,
    verify_protocol,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROTOCOL_PATH = (
    _REPO_ROOT / "config/engine_v2_global_orientation_development_protocol.json"
)


def _protocol() -> dict[str, object]:
    return load_protocol(_PROTOCOL_PATH)


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("protocol_sha256", None)
    changed["protocol_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return changed


def test_current_development_protocol_verifies() -> None:
    observed = verify_protocol(_protocol(), repo_root=_REPO_ROOT)
    assert len(observed) == 64


def test_resealed_authority_escalation_fails_closed() -> None:
    changed = _protocol()
    changed["authority"]["historical_execution_authorized"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="historical_execution_authorized",
    ):
        verify_protocol(changed)


def test_resealed_denominator_drift_fails_closed() -> None:
    changed = _protocol()
    changed["arms"]["experimental"]["orientation_count"] = 15
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="candidate budget",
    ):
        verify_protocol(changed)


def test_resealed_reference_input_escalation_fails_closed() -> None:
    changed = _protocol()
    changed["arms"]["shared_contract"][
        "reference_pose_input_to_generator_allowed"
    ] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="reference_pose_input_to_generator_allowed",
    ):
        verify_protocol(changed)


def test_resealed_case_roster_drift_fails_closed() -> None:
    changed = _protocol()
    changed["cohort"]["ordered_case_ids"][0] = "FRESH_CASE"
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="historical case roster",
    ):
        verify_protocol(changed)


def test_resealed_pr245_dependency_cannot_be_disabled() -> None:
    changed = _protocol()
    changed["decision"][
        "actual_execution_requires_pr_245_reviewed_terminal_state"
    ] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="PR #245",
    ):
        verify_protocol(changed)


def test_resealed_source_rederivation_cannot_be_disabled() -> None:
    changed = _protocol()
    changed["evaluation"]["source_rederivation_required"] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="source_rederivation_required",
    ):
        verify_protocol(changed)


def test_resealed_frozen_dependency_crosswire_fails_closed() -> None:
    changed = _protocol()
    changed["frozen_dependencies"]["phase25_policy_sha256"] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="frozen dependency",
    ):
        verify_protocol(changed)
