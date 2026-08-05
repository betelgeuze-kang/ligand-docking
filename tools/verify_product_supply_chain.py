#!/usr/bin/env python3
"""Verify product image and direct-dependency supply-chain guardrails."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


POLICY_SCHEMA_ID = "betelgeuze.product_supply_chain_policy/1.0.0"
EXPECTED_RUSTUP_COMMIT = "28d1352dbcb436d3111c3594b9e1588e94950464"
EXPECTED_RUSTUP_VERSION = "1.29.0"
EXPECTED_RUST_TOOLCHAIN = "1.93.0"
EXPECTED_RUNTIME_REQUIREMENTS = {
    "fastapi": "0.139.0",
    "starlette": "1.3.1",
    "uvicorn[standard]": "0.45.0",
    "pydantic-settings": "2.14.2",
    "prometheus-client": "0.25.0",
    "httpx2": "2.5.0",
}
EXPECTED_DEVELOPMENT_REQUIREMENTS = {"pytest": "9.1.1"}
EXPECTED_DEPLOY_REQUIREMENTS = {"mlflow": "3.14.0"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?)==([^\s;]+)$")


class ProductSupplyChainError(ValueError):
    """Raised when product supply-chain guardrails fail closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_text(path: Path, *, name: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ProductSupplyChainError(f"{name} cannot be read: {exc}") from exc


def _read_json(path: Path, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductSupplyChainError(f"{name} cannot be read as JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProductSupplyChainError(f"{name} must be a JSON object")
    return payload


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ProductSupplyChainError(f"{name} must be an object")
    return value


def _exact_requirements(path: Path, *, name: str) -> tuple[dict[str, str], tuple[str, ...]]:
    pins: dict[str, str] = {}
    includes: list[str] = []
    for line_number, raw_line in enumerate(_read_text(path, name=name).splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            include = line[3:].strip()
            if not include or any(part in {"", ".", ".."} for part in Path(include).parts):
                raise ProductSupplyChainError(
                    f"{name}:{line_number} has an unsafe include"
                )
            includes.append(include)
            continue
        match = _REQUIREMENT_RE.fullmatch(line)
        if match is None:
            raise ProductSupplyChainError(
                f"{name}:{line_number} is not an exact direct pin"
            )
        package, version = match.groups()
        normalized = package.lower()
        if normalized in pins:
            raise ProductSupplyChainError(f"{name} repeats {package}")
        pins[normalized] = version
    return pins, tuple(includes)


def _require_tokens(text: str, tokens: tuple[str, ...], *, name: str) -> None:
    missing = [token for token in tokens if token not in text]
    if missing:
        raise ProductSupplyChainError(
            f"{name} is missing required tokens: {', '.join(missing)}"
        )


def verify_supply_chain(repo_root: Path) -> str:
    root = repo_root.resolve(strict=True)
    policy = _read_json(
        root / "config/product_supply_chain_policy.json",
        name="product supply-chain policy",
    )
    required_policy_keys = {
        "container",
        "dependency_profiles",
        "monitoring",
        "policy_role",
        "policy_sha256",
        "release_authority",
        "rust",
        "schema_id",
        "status",
    }
    if set(policy) != required_policy_keys:
        raise ProductSupplyChainError("policy key set is invalid")
    if policy.get("schema_id") != POLICY_SCHEMA_ID:
        raise ProductSupplyChainError("policy schema is invalid")
    if policy.get("policy_role") != "product_image_build_and_dependency_guardrails":
        raise ProductSupplyChainError("policy role is invalid")
    observed_hash = policy.get("policy_sha256")
    if not isinstance(observed_hash, str) or _SHA256_RE.fullmatch(observed_hash) is None:
        raise ProductSupplyChainError("policy SHA-256 is invalid")
    projection = dict(policy)
    projection.pop("policy_sha256")
    expected_hash = _sha256(projection)
    if observed_hash != expected_hash:
        raise ProductSupplyChainError("policy self-hash is invalid")

    release_authority = _mapping(policy.get("release_authority"), name="release_authority")
    if any(value is not False for value in release_authority.values()):
        raise ProductSupplyChainError("release or claim authority must remain false")
    if policy.get("status") != "guardrails_implemented_release_not_qualified":
        raise ProductSupplyChainError("policy status is invalid")

    rust = _mapping(policy.get("rust"), name="rust")
    if rust.get("installer_source_commit") != EXPECTED_RUSTUP_COMMIT:
        raise ProductSupplyChainError("Rustup source commit drifted")
    if rust.get("installer_version") != EXPECTED_RUSTUP_VERSION:
        raise ProductSupplyChainError("Rustup version drifted")
    if rust.get("toolchain") != EXPECTED_RUST_TOOLCHAIN:
        raise ProductSupplyChainError("Rust toolchain drifted")
    if rust.get("installer_checksum_required_for_release") is not True:
        raise ProductSupplyChainError("release Rustup checksum must be required")

    dockerfile = _read_text(root / "Dockerfile.product", name="Dockerfile.product")
    _require_tokens(
        dockerfile,
        (
            "FROM ${PRODUCT_ROCM_BASE} AS builder",
            "FROM ${PRODUCT_ROCM_BASE} AS runtime",
            "ARG PRODUCT_IMAGE_RELEASE_BUILD=0",
            "ARG RUSTUP_INIT_SHA256=\"\"",
            f"rust-lang/rustup/{EXPECTED_RUSTUP_COMMIT}/rustup-init.sh",
            f"ARG RUSTUP_VERSION={EXPECTED_RUSTUP_VERSION}",
            f"ARG RUST_TOOLCHAIN={EXPECTED_RUST_TOOLCHAIN}",
            "@sha256:",
            "release builds require PRODUCT_ROCM_BASE pinned by @sha256",
            "sha256sum -c -",
            "requirements-api-runtime.txt",
            "python -m venv --system-site-packages /opt/venv",
            "COPY --from=builder /opt/venv /opt/venv",
            "COPY --from=builder /app /app",
            "python -m pip install --no-cache-dir \"pip==${PIP_VERSION}\"",
            "python -m pip check",
            "USER 10001:10001",
            "chmod 0700 /app/logs /app/runs /data",
        ),
        name="Dockerfile.product",
    )
    if dockerfile.count("python -m pip check") < 2:
        raise ProductSupplyChainError("builder and runtime must both run pip check")
    for forbidden in (
        "https://sh.rustup.rs",
        "pip install --no-cache-dir --upgrade pip",
        "chmod -R a+rwX",
        "product_image_build_time_fixture",
        "independent_engine_roadmap_closed",
        "-r requirements-api.txt ",
    ):
        if forbidden in dockerfile:
            raise ProductSupplyChainError(
                f"Dockerfile.product contains forbidden token: {forbidden}"
            )

    runtime_pins, runtime_includes = _exact_requirements(
        root / "requirements-api-runtime.txt",
        name="requirements-api-runtime.txt",
    )
    if runtime_includes:
        raise ProductSupplyChainError("runtime API requirements cannot include profiles")
    if runtime_pins != {key.lower(): value for key, value in EXPECTED_RUNTIME_REQUIREMENTS.items()}:
        raise ProductSupplyChainError("runtime API direct pins drifted")
    if "pytest" in runtime_pins:
        raise ProductSupplyChainError("runtime API requirements include pytest")

    development_pins, development_includes = _exact_requirements(
        root / "requirements-api.txt",
        name="requirements-api.txt",
    )
    if development_includes != ("requirements-api-runtime.txt",):
        raise ProductSupplyChainError("API development profile must include runtime once")
    if development_pins != EXPECTED_DEVELOPMENT_REQUIREMENTS:
        raise ProductSupplyChainError("API development direct pins drifted")

    deploy_pins, deploy_includes = _exact_requirements(
        root / "requirements-deploy.txt",
        name="requirements-deploy.txt",
    )
    if deploy_includes or deploy_pins != EXPECTED_DEPLOY_REQUIREMENTS:
        raise ProductSupplyChainError("deployment direct pins drifted")

    dependabot = _read_text(root / ".github/dependabot.yml", name="Dependabot config")
    ecosystems = set(re.findall(r"package-ecosystem:\s*([a-z-]+)", dependabot))
    if ecosystems != {"github-actions", "pip", "docker"}:
        raise ProductSupplyChainError("Dependabot ecosystem coverage is incomplete")

    dockerignore = _read_text(root / ".dockerignore", name=".dockerignore")
    _require_tokens(
        dockerignore,
        (
            "!requirements-api-runtime.txt",
            "runs\nruns/**",
            ".betelgeuze\n.betelgeuze/**",
        ),
        name=".dockerignore",
    )
    if "!runs" in dockerignore:
        raise ProductSupplyChainError("runtime evidence artifacts entered build context")

    compose = _read_text(
        root / "deploy/docker-compose.product.yml",
        name="product compose file",
    )
    _require_tokens(
        compose,
        (
            "x-product-build: &product-build",
            "build: *product-build",
            "PRODUCT_ROCM_BASE:",
            "PRODUCT_IMAGE_RELEASE_BUILD:",
            "RUSTUP_INIT_SHA256:",
        ),
        name="product compose file",
    )
    if compose.count("build: *product-build") != 3:
        raise ProductSupplyChainError("all three product services must share the build contract")

    dependency_profiles = _mapping(
        policy.get("dependency_profiles"),
        name="dependency_profiles",
    )
    if dependency_profiles.get("top_level_exact_pins_required") is not True:
        raise ProductSupplyChainError("top-level exact pinning is not required")
    if (
        dependency_profiles.get("transitive_hash_lock_status")
        != "not_implemented_blocks_signed_release"
    ):
        raise ProductSupplyChainError("hash-lock limitation must remain explicit")

    monitoring = _mapping(policy.get("monitoring"), name="monitoring")
    if sorted(monitoring.get("dependabot_ecosystems_required", [])) != [
        "docker",
        "github-actions",
        "pip",
    ]:
        raise ProductSupplyChainError("policy Dependabot ecosystems drifted")
    for field in (
        "dependency_license_scan_status",
        "sbom_status",
        "vulnerability_scan_status",
    ):
        if monitoring.get(field) != "not_implemented":
            raise ProductSupplyChainError(
                f"{field} must not claim completion without an implementation"
            )

    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    print(verify_supply_chain(arguments.repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
