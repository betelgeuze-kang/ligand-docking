#!/usr/bin/env python3
"""Verify the compact Engine V2 current-state registry.

This verifier is intentionally read-only.  It synchronizes a small, reviewable
implementation-stage record with the existing human and machine-readable status
surfaces without granting any scientific, benchmark, product, or GPU authority.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
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

TOP_LEVEL_KEYS = {
    "schema_id",
    "engine_id",
    "implementation_stage",
    "evidence_anchor_commit",
    "native_compute",
    "maturity",
    "evidence",
    "claim_policy",
    "canonical_companions",
    "generated_or_updated_utc",
}

MATURITY_MEANINGS = {
    "software_api": (
        "Versioned packages, CLI/API surfaces, strict schemas, and extensive tests "
        "exist."
    ),
    "native_docking_core": (
        "The bounded native graph is end-to-end, but molecular applicability and "
        "search breadth remain limited."
    ),
    "docking_science": (
        "Historical development evidence exists, while Stage 0 and Fresh-128 remain "
        "blocked."
    ),
    "hip_performance": (
        "Device kernels and parity lanes exist; representative molecular throughput "
        "is not qualified."
    ),
    "molecular_dynamics": (
        "Deterministic short-MD primitives exist without production solvent, PME, "
        "NPT, or broad biomolecular validation."
    ),
}

NATIVE_LABELS = {
    "abi_version": "Native ABI version",
    "fixed_candidate_denominator": "Fixed candidate denominator",
    "complete_pipeline": "Complete fixed64 pipeline",
    "prepared_input_transport": "Prepared-input transport",
    "cpu_reference_backend": "CPU reference backend",
    "production_cpu_backend": "Production CPU backend",
    "hip_safe_backend": "HIP safe backend",
    "hip_fast_backend": "HIP fast backend",
}

EVIDENCE_LABELS = {
    "native_fixed64_cpu_v7_consumed": "Native fixed64 CPU v7 consumed",
    "native_fixed64_cpu_v7_terminal_decision": "Native fixed64 CPU v7 terminal decision",
    "native_fixed64_cpu_v7_authoritative": "Native fixed64 CPU v7 authoritative",
    "molecular_development_evidence_available": "Molecular development evidence available",
    "fresh_128_executed": "Fresh-128 executed",
    "stage0_admitted": "Stage 0 admitted",
    "hip_molecular_performance_qualified": "HIP molecular performance qualified",
    "production_md_validated": "Production MD validated",
}

CLAIM_LABELS = {
    "customer_execution_enabled": "Customer execution enabled",
    "scientific_validity_green": "Scientific validity green",
    "benchmark_validity_green": "Benchmark validity green",
    "gpu_acceleration_claim_allowed": "GPU acceleration claim allowed",
    "docking_accuracy_claim_allowed": "Docking accuracy claim allowed",
    "free_energy_claim_allowed": "Free-energy claim allowed",
}


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


def _require_exact_keys(
    mapping: dict[str, Any], expected: set[str], label: str
) -> None:
    observed = set(mapping)
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise CurrentStateError(
            f"{label} keys changed: missing={missing}, unexpected={unexpected}"
        )


def _require_generated_utc(value: Any) -> str:
    if type(value) is not str or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ) is None:
        raise CurrentStateError(
            "generated_or_updated_utc must use canonical RFC3339 UTC seconds"
        )
    try:
        dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise CurrentStateError(
            "generated_or_updated_utc must be a valid UTC calendar timestamp"
        ) from exc
    return value


def _require_text(path: Path, markers: tuple[str, ...]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CurrentStateError(f"cannot read companion {path}: {exc}") from exc
    for marker in markers:
        if marker not in text:
            raise CurrentStateError(f"{path} is missing marker: {marker}")


def _markdown_value(value: Any) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def render_markdown(registry: dict[str, Any]) -> str:
    """Render the review-facing current-state summary from the JSON source."""

    _require_exact_keys(registry, TOP_LEVEL_KEYS, "current-state registry")
    generated_or_updated_utc = _require_generated_utc(
        registry.get("generated_or_updated_utc")
    )
    sections = {
        "native_compute": set(NATIVE_LABELS),
        "maturity": set(MATURITY_MEANINGS),
        "evidence": set(EVIDENCE_LABELS),
        "claim_policy": set(CLAIM_LABELS),
    }
    for key, expected_keys in sections.items():
        value = registry.get(key)
        if type(value) is not dict:
            raise CurrentStateError(f"{key} must be an object")
        _require_exact_keys(value, expected_keys, key)

    native = registry["native_compute"]
    maturity = registry["maturity"]
    evidence = registry["evidence"]
    claims = registry["claim_policy"]

    lines = [
        "<!-- Generated by tools/render_engine_v2_current_state_v1.py from",
        "config/engine_v2_current_state_v1.json. Do not edit by hand. -->",
        "",
        "# Engine V2 current implementation state v1",
        "",
        "This compact companion is generated from the machine-readable current-state",
        "registry. The renderer and verifier require exact byte identity, so the JSON is",
        "the single source for every value below.",
        "",
        "## Registry metadata",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Schema | `{registry['schema_id']}` |",
        f"| Engine | `{registry['engine_id']}` |",
        f"| Implementation stage | `{registry['implementation_stage']}` |",
        f"| Evidence anchor commit | `{registry['evidence_anchor_commit']}` |",
        f"| Generated or updated UTC | `{generated_or_updated_utc}` |",
        "",
        "## Native compute surface",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    for key, label in NATIVE_LABELS.items():
        lines.append(f"| {label} | `{_markdown_value(native[key])}` |")

    lines.extend(
        [
            "",
            "The complete fixed64 surface includes post-refinement geometric admission,",
            "ScorerV1, pose validity, stable ranking, clustering, and the declared backend",
            "boundaries. This implementation record does not establish molecular",
            "applicability, benchmark validity, acceleration, or product authority.",
            "",
            "## Maturity labels",
            "",
            "| Surface | Maturity | Meaning |",
            "| --- | --- | --- |",
        ]
    )
    for key, meaning in MATURITY_MEANINGS.items():
        label = (
            key.replace("_", " ")
            .title()
            .replace("Hip", "HIP")
            .replace("Api", "API")
        )
        lines.append(f"| {label} | `{maturity[key]}` | {meaning} |")

    lines.extend(
        [
            "",
            "## Recorded evidence boundary",
            "",
            "| Evidence field | Recorded value |",
            "| --- | --- |",
        ]
    )
    for key, label in EVIDENCE_LABELS.items():
        lines.append(f"| {label} | `{_markdown_value(evidence[key])}` |")

    lines.extend(
        [
            "",
            "The consumed CPU-v7 result is synthetic engineering evidence and remains",
            "explicitly non-authoritative. It grants no molecular, benchmark, product,",
            "scientific, or performance claim.",
            "",
            "## Claim policy",
            "",
            "| Claim or execution field | Allowed |",
            "| --- | --- |",
        ]
    )
    for key, label in CLAIM_LABELS.items():
        lines.append(f"| {label} | `{_markdown_value(claims[key])}` |")

    lines.extend(
        [
            "",
            "## Canonical companions",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in registry["canonical_companions"])
    lines.extend(
        [
            "",
            "## Change policy",
            "",
            "A successor registry version is required when the public native ABI,",
            "prepared-input transport, fixed denominator, backend identities, maturity",
            "labels, Fresh-128 or Stage 0 state, or any public claim authorization changes.",
            "",
            "Rendering or changing this document cannot grant authority. Existing",
            "machine-readable capability, benchmark, execution, and release gates remain",
            "controlling.",
            "",
        ]
    )
    return "\n".join(lines)


def verify_root(root: Path) -> dict[str, Any]:
    root = root.resolve()
    registry_path = root / "config/engine_v2_current_state_v1.json"
    registry = _load_json(registry_path)

    _require_exact_keys(registry, TOP_LEVEL_KEYS, "current-state registry")
    _require_generated_utc(registry.get("generated_or_updated_utc"))

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
    _require_exact_keys(native, set(NATIVE_LABELS), "native_compute")
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
    _require_exact_keys(evidence, set(EVIDENCE_LABELS), "evidence")
    _require_bool(evidence, "native_fixed64_cpu_v7_consumed", True)
    if evidence.get("native_fixed64_cpu_v7_terminal_decision") != "PASS":
        raise CurrentStateError("CPU v7 terminal decision must remain PASS")
    _require_bool(evidence, "native_fixed64_cpu_v7_authoritative", False)
    _require_bool(evidence, "molecular_development_evidence_available", True)
    _require_bool(evidence, "fresh_128_executed", False)
    _require_bool(evidence, "stage0_admitted", False)
    _require_bool(evidence, "hip_molecular_performance_qualified", False)
    _require_bool(evidence, "production_md_validated", False)

    claims = registry.get("claim_policy")
    if type(claims) is not dict:
        raise CurrentStateError("claim_policy must be an object")
    _require_exact_keys(claims, set(CLAIM_LABELS), "claim_policy")
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

    current_state_document = root / "docs/engine_v2_current_state_v1.md"
    try:
        observed_document = current_state_document.read_bytes()
    except OSError as exc:
        raise CurrentStateError(
            f"cannot read generated current-state document: {exc}"
        ) from exc
    expected_document = render_markdown(registry).encode("utf-8")
    if observed_document != expected_document:
        raise CurrentStateError(
            "docs/engine_v2_current_state_v1.md is not the exact rendered JSON summary"
        )

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
