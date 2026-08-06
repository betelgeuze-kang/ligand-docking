from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tools.verify_product_capability_registry import (
    ProductCapabilityRegistryError,
    load_registry,
    verify_registry,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / "config/product_capability_registry.json"


def _registry() -> dict[str, object]:
    return load_registry(_REGISTRY_PATH)


def test_current_product_capability_registry_verifies() -> None:
    observed = verify_registry(_registry())
    assert len(observed) == 64


def test_engine_v2_redocking_claim_escalation_fails_closed() -> None:
    changed = copy.deepcopy(_registry())
    capability = next(
        row
        for row in changed["capabilities"]
        if row["capability_id"] == "engine_v2_redocking"
    )
    capability["claim_safe"] = True

    with pytest.raises(ProductCapabilityRegistryError, match="self-hash"):
        verify_registry(changed)


def test_resealed_broad_gpcr_execution_escalation_fails_closed() -> None:
    changed = copy.deepcopy(_registry())
    capability = next(
        row
        for row in changed["capabilities"]
        if row["capability_id"] == "gpcr_broad_router"
    )
    capability["customer_execution"] = "guarded_operator_only"
    changed.pop("registry_sha256")
    import hashlib
    import json

    changed["registry_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()

    with pytest.raises(ProductCapabilityRegistryError, match="opened execution"):
        verify_registry(changed)


def test_resealed_canonical_workflow_drift_fails_closed() -> None:
    changed = copy.deepcopy(_registry())
    changed["canonical_workflow"][0]["step_id"] = "upload"
    changed.pop("registry_sha256")
    import hashlib
    import json

    changed["registry_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()

    with pytest.raises(ProductCapabilityRegistryError, match="workflow order"):
        verify_registry(changed)


def test_resealed_default_enablement_without_qualification_fails_closed() -> None:
    changed = copy.deepcopy(_registry())
    capability = next(
        row
        for row in changed["capabilities"]
        if row["capability_id"] == "legacy_restricted_docking"
    )
    capability["default_enabled"] = True
    changed.pop("registry_sha256")
    import hashlib
    import json

    changed["registry_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()

    with pytest.raises(ProductCapabilityRegistryError, match="default enablement"):
        verify_registry(changed)
