from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import tools.verify_product_supply_chain as supply_chain_module
from tools.verify_product_supply_chain import (
    ProductSupplyChainError,
    verify_supply_chain,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _REPO_ROOT / "config/product_supply_chain_policy.json"
_GUARDRAIL_PATHS = (
    "config/product_supply_chain_policy.json",
    "Dockerfile.product",
    "requirements-api-runtime.txt",
    "requirements-api.txt",
    "requirements-deploy.txt",
    ".github/dependabot.yml",
    ".dockerignore",
    "deploy/docker-compose.product.yml",
)


def _copy_guardrail_fixture(target_root: Path) -> None:
    """Copy only the supply-chain surfaces verified by this contract."""

    for relative in _GUARDRAIL_PATHS:
        source = _REPO_ROOT / relative
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("policy_sha256", None)
    changed["policy_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return changed


def test_current_product_supply_chain_guardrails_verify() -> None:
    observed = verify_supply_chain(_REPO_ROOT)
    assert len(observed) == 64


def test_release_authority_escalation_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _copy_guardrail_fixture(tmp_path)
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    policy["release_authority"]["product_release_authorized"] = True
    changed = _reseal(policy)
    monkeypatch.setattr(
        supply_chain_module,
        "EXPECTED_POLICY_SHA256",
        changed["policy_sha256"],
    )

    target = tmp_path / "config/product_supply_chain_policy.json"
    target.write_text(
        json.dumps(changed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="authority"):
        verify_supply_chain(tmp_path)


def test_resealed_nested_policy_drift_fails_identity(tmp_path: Path) -> None:
    _copy_guardrail_fixture(tmp_path)
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    policy["container"]["base_image_release_digest_required"] = False
    changed = _reseal(policy)

    target = tmp_path / "config/product_supply_chain_policy.json"
    target.write_text(
        json.dumps(changed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="identity"):
        verify_supply_chain(tmp_path)


def test_nested_policy_shape_is_exact_at_reviewed_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _copy_guardrail_fixture(tmp_path)
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    policy["container"]["base_image_release_digest_required"] = False
    changed = _reseal(policy)
    monkeypatch.setattr(
        supply_chain_module,
        "EXPECTED_POLICY_SHA256",
        changed["policy_sha256"],
    )

    target = tmp_path / "config/product_supply_chain_policy.json"
    target.write_text(
        json.dumps(changed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="container policy"):
        verify_supply_chain(tmp_path)


def test_unpinned_runtime_dependency_fails_closed(tmp_path: Path) -> None:
    _copy_guardrail_fixture(tmp_path)
    path = tmp_path / "requirements-api-runtime.txt"
    path.write_text(
        path.read_text(encoding="utf-8").replace("fastapi==0.139.0", "fastapi"),
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="exact direct pin"):
        verify_supply_chain(tmp_path)


def test_permissive_runtime_permissions_fail_closed(tmp_path: Path) -> None:
    _copy_guardrail_fixture(tmp_path)
    path = tmp_path / "Dockerfile.product"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nRUN chmod -R a+rwX /app/runs\n",
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="forbidden token"):
        verify_supply_chain(tmp_path)


def test_weak_release_base_digest_pattern_fails_closed(tmp_path: Path) -> None:
    _copy_guardrail_fixture(tmp_path)
    path = tmp_path / "Dockerfile.product"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "grep -Eq '^.+@sha256:[0-9a-f]{64}$'",
            "grep -Eq '^.+@sha256:[0-9a-f]*$'",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="exact SHA-256"):
        verify_supply_chain(tmp_path)


def test_build_time_readiness_fixture_fails_closed(tmp_path: Path) -> None:
    _copy_guardrail_fixture(tmp_path)
    path = tmp_path / "Dockerfile.product"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\nRUN echo product_image_build_time_fixture > /app/runs/status\n",
        encoding="utf-8",
    )

    with pytest.raises(ProductSupplyChainError, match="forbidden token"):
        verify_supply_chain(tmp_path)


def test_missing_docker_dependabot_coverage_fails_closed(tmp_path: Path) -> None:
    _copy_guardrail_fixture(tmp_path)
    path = tmp_path / ".github/dependabot.yml"
    text = path.read_text(encoding="utf-8")
    docker_block = """\n  - package-ecosystem: docker\n    directory: /\n    schedule:\n      interval: weekly\n    open-pull-requests-limit: 3\n"""
    path.write_text(text.replace(docker_block, "\n"), encoding="utf-8")

    with pytest.raises(ProductSupplyChainError, match="ecosystem"):
        verify_supply_chain(tmp_path)
