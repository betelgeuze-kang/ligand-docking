#!/usr/bin/env python3
"""Verify the non-authoritative native fixed64 context-lease contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_native_fixed64_context_lease_v1.json"
)
DEFAULT_CONTEXT_SOURCE = REPOSITORY_ROOT / "rust/betelgeuze-runtime/src/lib.rs"
DEFAULT_PIPELINE_SOURCE = (
    REPOSITORY_ROOT / "rust/betelgeuze-runtime/src/docking.rs"
)
DEFAULT_TEST_SOURCE = (
    REPOSITORY_ROOT / "rust/betelgeuze-runtime/tests/docking_fixed64_pipeline.rs"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_native_fixed64_context_lease_v1.md"
)

EXPECTED_AUTHORITY_FIELDS = frozenset(
    {
        "d1_d2_molecular_execution_authorized",
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_performance_claim_authorized",
        "public_benchmark_authorized",
        "qualification_rerun_authorized",
        "reservation_authorized",
        "stage0_admission_authorized",
    }
)
EXPECTED_LIFECYCLE = {
    "context_owner": "std::rc::Rc<ContextInner>",
    "context_wrapper_may_drop_before_pipeline": True,
    "last_context_lease_destroys_native_context": True,
    "native_pipeline_handles_destroy_before_context_lease_release": True,
    "pipeline_constructor_deep_copies_scientific_input": True,
    "pipeline_owns_context_lease": True,
    "send": False,
    "shared_context_supports_multiple_pipelines": True,
    "sync": False,
}
EXPECTED_SCOPE = {
    "candidate_denominator": 64,
    "component": "betelgeuze-runtime::Fixed64Pipeline",
    "hip_disposition": "compile_only_no_device_execution_or_parity_claim",
    "validated_backends": ["cpp_cpu_reference", "rust_cpu"],
    "validation_mode": "synthetic_native_cpu_only",
}


class ContractError(RuntimeError):
    """The context-lease contract or its source binding failed closed."""


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"contract is unavailable: {path}") from exc
    try:
        document = json.loads(raw, object_pairs_hook=_pairs_no_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError("contract is not valid UTF-8 JSON") from exc
    if type(document) is not dict:
        raise ContractError("contract must be an object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if raw != canonical:
        raise ContractError("contract JSON is not canonical pretty ASCII")
    return document, raw


def _read_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"{label} is unavailable or not UTF-8: {path}") from exc


def _require_exact_keys(
    value: object, expected: set[str], *, label: str
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ContractError(f"{label} key schema changed")
    return value


def _require_snippets(source: str, snippets: tuple[str, ...], *, label: str) -> None:
    missing = [snippet for snippet in snippets if snippet not in source]
    if missing:
        raise ContractError(f"{label} is missing frozen contract snippets: {missing}")


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    context_source_path: Path = DEFAULT_CONTEXT_SOURCE,
    pipeline_source_path: Path = DEFAULT_PIPELINE_SOURCE,
    test_source_path: Path = DEFAULT_TEST_SOURCE,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
) -> dict[str, object]:
    document, raw = _read_json(contract_path)
    _require_exact_keys(
        document,
        {"authority", "lifecycle", "schema_id", "scope", "status"},
        label="contract",
    )
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_native_fixed64_context_lease/1.0.0"
        or document["status"]
        != "synthetic_native_cpu_development_authority_false"
    ):
        raise ContractError("contract identity or status changed")
    authority = _require_exact_keys(
        document["authority"], set(EXPECTED_AUTHORITY_FIELDS), label="authority"
    )
    if any(value is not False for value in authority.values()):
        raise ContractError("context-lease contract acquired execution authority")
    lifecycle = _require_exact_keys(
        document["lifecycle"], set(EXPECTED_LIFECYCLE), label="lifecycle"
    )
    if lifecycle != EXPECTED_LIFECYCLE:
        raise ContractError("context-lease lifecycle policy changed")
    scope = _require_exact_keys(
        document["scope"], set(EXPECTED_SCOPE), label="scope"
    )
    if scope != EXPECTED_SCOPE:
        raise ContractError("context-lease validation scope changed")

    context_source = _read_text(context_source_path, label="Rust context source")
    _require_snippets(
        context_source,
        (
            "pub(crate) struct ContextInner {",
            "impl Drop for ContextInner {",
            "unsafe { sys::bg_context_destroy(self.handle.as_ptr()) };",
            "inner: Rc<ContextInner>,",
            "pub(crate) fn lease(&self) -> Rc<ContextInner>",
            "Rc::clone(&self.inner)",
            "require_send_sync::<Context>();",
        ),
        label="Rust context source",
    )
    pipeline_source = _read_text(pipeline_source_path, label="Rust pipeline source")
    _require_snippets(
        pipeline_source,
        (
            "context_lease: Rc<ContextInner>,",
            "context_lease: context.lease(),",
            "self.context_lease.raw_handle()",
            "impl Drop for Fixed64Pipeline {",
            "sys::bg_docking_fixed64_pipeline_v2_destroy(self.handle.as_ptr());",
            "sys::bg_docking_geometric_admission_v1_destroy(",
            "require_send_sync::<Fixed64Pipeline>();",
            "native constructor deep-copies every molecular channel",
        ),
        label="Rust pipeline source",
    )
    test_source = _read_text(test_source_path, label="Rust integration test source")
    _require_snippets(
        test_source,
        (
            "multiple_pipelines_keep_the_shared_context_alive_after_wrapper_drop",
            "safe_run_returns_complete_fixed64_receipt_and_preserves_typed_failures",
            "let (pipeline, sibling_pipeline) = {",
            "drop(pipeline);",
            "sibling_pipeline.run(run).unwrap()",
            "assert_eq!(receipt, repeated);",
        ),
        label="Rust integration test source",
    )
    documentation = _read_text(documentation_path, label="context-lease documentation")
    _require_snippets(
        documentation,
        (
            "The last lease destroys the context exactly",
            "Both `Context` and `Fixed64Pipeline` remain `!Send` and `!Sync`.",
            "External authority must reach blocker zero",
        ),
        label="context-lease documentation",
    )
    return {
        "all_authority_false": True,
        "candidate_denominator": 64,
        "context_wrapper_may_drop_before_pipeline": True,
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "last_context_lease_destroys_native_context": True,
        "status": "verified_static_non_authoritative",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--context-source", type=Path, default=DEFAULT_CONTEXT_SOURCE)
    parser.add_argument("--pipeline-source", type=Path, default=DEFAULT_PIPELINE_SOURCE)
    parser.add_argument("--test-source", type=Path, default=DEFAULT_TEST_SOURCE)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify(
            contract_path=args.contract,
            context_source_path=args.context_source,
            pipeline_source_path=args.pipeline_source,
            test_source_path=args.test_source,
            documentation_path=args.documentation,
        )
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
