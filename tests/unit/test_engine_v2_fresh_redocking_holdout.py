from __future__ import annotations

import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.fresh_redocking_holdout import (
    FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256,
    FreshRedockingHoldoutError,
    load_fresh_redocking_holdout_manifest,
    require_fresh_redocking_holdout_manifest,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
)


_MANIFEST = Path("config/engine_v2_fresh_redocking_holdout_manifest.json")


def test_fresh_holdout_manifest_is_frozen_and_disjoint() -> None:
    holdout = load_fresh_redocking_holdout_manifest(_MANIFEST)

    assert holdout.manifest_sha256 == FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256
    assert holdout.case_ids == FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS
    assert len(holdout.cases) == 128
    assert not set(holdout.case_ids) & set(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    assert all(len(case.artifact_sha256s) == 4 for case in holdout.cases)


def test_fresh_holdout_manifest_tampering_fails_closed() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="ascii"))
    payload["cases"][0]["artifact_sha256s"]["native"] = "0" * 64

    with pytest.raises(FreshRedockingHoldoutError, match="self-hash mismatch"):
        require_fresh_redocking_holdout_manifest(payload)
