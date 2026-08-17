#!/usr/bin/env python3
"""Verify the compact Engine V2 current-state registry.

This verifier is intentionally read-only.  It synchronizes a small, reviewable
implementation-stage record with the existing human and machine-readable status
surfaces without granting any scientific, benchmark, product, or GPU authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_ID = "betelgeuze.engine_v2_current_state/1.0.0"
IMPLEMENTATION_STAGE = "v2_native_fixed64_pipeline_alpha_abi121"
EXPECTED_BACKENDS = {
    "cpu_reference_backend": "cpp_cpu_reference",
    "production_cpu_backend": "rust_cpu",
    "hip_safe_backend": "hip_safe",
    "hip_fast_backend": "hip_fast",
}
FALSE_CLAIMS = (
    "customer_execution_enabled",
    "scientific_validity_green",
    "benchmark_validity_green",
    "gpu_acceleration_claim_allowed",
    "docking_accuracy_claim_allowed",
    "free_energy_claim_allowed",
)


class CurrentStateError(ValueError):
    """The current-state registry or one of its companions is inconsistent."""


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CurrentStateError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_object_no_duplicates
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise CurrentStateError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise CurrentStateError(f"{path} must contain a JSON object")
    return value


def _require_bool(mapping: dict[str, Any], key: str, expected: bool) -> None:
    value = mapping.get(key)
    if type(value) is not bool or value is not expected:
        raise CurrentStateError(f"{key} must be exactly {expected}")


def _require_text(path: Path, markers: tuple[str, ...]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CurrentStateError(f"cannot read companion {path}: {exc}") from exc
    for marker in markers:
        if marker not in text:
            raise CurrentStateError(f"{path} is missing marker: {marker}")


def verify_root(root: Path) -> dict[str, Any]:
    root = root.resolve()
    registry_path = root / "config/engine_v2_current_state_v1.json"
    registry = _load_json(registry_path)

    if registry.get("schema_id") != SCHEMA_ID:
        raise CurrentStateError("current-state schema_id changed")
    if registry.get("engine_id") != "betelgeuze_independent_engine_v2":
        raise CurrentStateError("current-state engine_id changed")
    if registry.get("implementation_stage") != IMPLEMENTATION_STAGE:
        raise CurrentStateError("implementation_stage changed")

    anchor = registry.get("evidence_anchor_commit")
    if (
        type(anchor) is not str
        or len(anchor) != 40
        or any(character not in "0123456789abcdef" for character in anchor)
    ):
        raise CurrentStateError("evidence_anchor_commit must be a lowercase 40-hex SHA")

    native = registry.get("native_compute")
    if type(native) is not dict:
        raise CurrentStateError("native_compute must be an object")
    if native.get("abi_version") != "1.21":
        raise CurrentStateError("native ABI must remain 1.21 for this registry version")
    if type(native.get("fixed_candidate_denominator")) is not int or native.get(
        "fixed_candidate_denominator"
    ) != 64:
        raise CurrentStateError("fixed candidate denominator must be exactly 64")
    _require_bool(native, "complete_pipeline", True)
    if native.get("prepared_input_transport") != "native_fixed64_complete_pipeline_v3":
        raise CurrentStateError("prepared-input transport changed")
    for key, expected in EXPECTED_BACKENDS.items():
        if native.get(key) != expected:
            raise CurrentStateError(f"{key} changed")

    maturity = registry.get("maturity")
    expected_maturity = {
        "software_api": "beta",
        "native_docking_core": "alpha",
        "docking_science": "alpha",
        "hip_performance": "experimental",
        "molecular_dynamics": "pre_alpha",
    }
    if maturity != expected_maturity:
        raise CurrentStateError("maturity map changed")

    evidence = registry.get("evidence")
    if type(evidence) is not dict:
        raise CurrentStateError("evidence must be an object")
    _require_bool(evidence, "native_fixed64_cpu_v7_consumed", True)
    if evidence.get("native_fixed64_cpu_v7_terminal_decision") != "PASS":
        raise CurrentStateError("CPU v7 terminal decision must remain PASS")
    _require_bool(evidence, "native_fixed64_cpu_v7_authoritative", False)
    _require_bool(evidence, "fresh_128_executed", False)
    _require_bool(evidence, "stage0_admitted", False)
    _require_bool(evidence, "hip_molecular_performance_qualified", False)
    _require_bool(evidence, "production_md_validated", False)

    claims = registry.get("claim_policy")
    if type(claims) is not dict:
        raise CurrentStateError("claim_policy must be an object")
    for key in FALSE_CLAIMS:
        _require_bool(claims, key, False)

    companions = registry.get("canonical_companions")
    if type(companions) is not list or not companions:
        raise CurrentStateError("canonical_companions must be a non-empty list")
    if any(type(value) is not str or not value for value in companions):
        raise CurrentStateError("canonical_companions must contain non-empty paths")
    for relative_path in companions:
        path = root / relative_path
        if not path.is_file():
            raise CurrentStateError(f"missing canonical companion: {relative_path}")

    _require_text(
        root / "docs/engine_v2_native_fixed64_cpu_qualification_v7_result.md",
        ("terminal decision is `PASS`", "recorded_pass_non_authoritative"),
    )
    _require_text(
        root / "docs/engine_v2_stage0_status.md",
        ("`BLIND_RUN_BLOCKED`", "| Fresh 128 executed | false |"),
    )
    _require_text(
        root / "docs/engine_v2_status.md",
        ("ABI 1.21", "exactly-once-consumed native CPU qualification-v7"),
    )
    _require_text(
        root / "config/independent_engine_v2_capabilities.yaml",
        tuple(f"{key}: false" for key in FALSE_CLAIMS),
    )

    return {
        "verified": True,
        "schema_id": SCHEMA_ID,
        "implementation_stage": IMPLEMENTATION_STAGE,
        "evidence_anchor_commit": anchor,
        "claim_authority_granted": False,
        "companion_count": len(companions),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_root(args.root)
    except CurrentStateError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
