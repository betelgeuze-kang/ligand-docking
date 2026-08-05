from __future__ import annotations

import copy
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    OneShotABAuthorityError,
    load_json_document,
    verify_one_shot_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _REPO_ROOT / "config/engine_v2_source_paired_clearance_one_shot_ab.json"
_PHASE25_PATH = _REPO_ROOT / "config/engine_v2_phase25_cohort_admission.json"
_ACTIVATION_PATH = _REPO_ROOT / "config/engine_v2_source_paired_clearance_activation.json"


def _documents() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return (
        load_json_document(_POLICY_PATH, name="one-shot policy"),
        load_json_document(_PHASE25_PATH, name="Phase 2.5 policy"),
        load_json_document(_ACTIVATION_PATH, name="activation policy"),
    )


def test_phase25_payload_mutation_with_stale_expected_hash_is_rejected() -> None:
    policy, phase25, activation = _documents()
    changed = copy.deepcopy(phase25)
    changed["authority_boundary"]["product_authority"] = True

    with pytest.raises(OneShotABAuthorityError, match="Phase 2.5 cohort policy self-hash"):
        verify_one_shot_policy(
            policy,
            phase25_policy=changed,
            activation_policy=activation,
        )


def test_activation_payload_mutation_with_stale_expected_hash_is_rejected() -> None:
    policy, phase25, activation = _documents()
    changed = copy.deepcopy(activation)
    changed["execution_boundary"]["product_path_wired"] = True

    with pytest.raises(OneShotABAuthorityError, match="activation policy self-hash"):
        verify_one_shot_policy(
            policy,
            phase25_policy=phase25,
            activation_policy=changed,
        )
