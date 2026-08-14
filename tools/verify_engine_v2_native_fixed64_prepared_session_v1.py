#!/usr/bin/env python3
"""Verify the non-authoritative native fixed64 prepared-session contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_native_fixed64_prepared_session_v1.json"
)
DEFAULT_RUST_SOURCE = (
    REPOSITORY_ROOT / "rust_engine_v2/src/complete_fixed64_pipeline.rs"
)
DEFAULT_PYTHON_SOURCE = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2/docking/native_fixed64_consumers.py"
)
DEFAULT_TEST_SOURCE = (
    REPOSITORY_ROOT
    / "tests/unit/test_engine_v2_native_fixed64_complete_pipeline.py"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_native_fixed64_prepared_session_v1.md"
)

EXPECTED_AUTHORITY_FIELDS = frozenset(
    {
        "customer_pose_emission_authorized",
        "d1_d2_molecular_execution_authorized",
        "existing_rank_auto_change_authorized",
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_performance_claim_authorized",
        "production_claim_authorized",
        "public_benchmark_authorized",
        "qualification_rerun_authorized",
        "reservation_authorized",
        "stage0_admission_authorized",
    }
)
EXPECTED_API = {
    "consumer_surfaces": ["cli", "benchmark", "api", "product_shadow"],
    "native_class": "NativeFixed64PreparedSessionV1",
    "native_entrypoint": "native_fixed64_prepare_session_v1",
    "python_factory": "prepare_native_fixed64_session",
    "stateless_entrypoint": "native_fixed64_complete_pipeline_v3",
    "transport_schema_id": (
        "betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0"
    ),
}
EXPECTED_LIFECYCLE = {
    "bounded_preflight_before_owned_copy": True,
    "consumer_identity_excluded_from_prepared_projection": True,
    "consumer_view_receipt_domain_separated": True,
    "context_created_once_per_session": True,
    "input_mutation_after_prepare_changes_session": False,
    "native_pipeline_created_once_per_session": True,
    "native_pipeline_destroyed_before_owned_input": True,
    "prepared_input_owned_by_rust": True,
    "repeated_run_executes_scientific_pipeline": True,
    "run_count_in_scientific_receipt": False,
    "scientific_result_cached": False,
    "session_send": False,
    "session_sync": False,
    "stateless_v3_uses_same_owned_input_parser": True,
}
EXPECTED_SCOPE = {
    "candidate_denominator": 64,
    "hip_disposition": "compile_only_no_device_execution_or_parity_claim",
    "validated_backends": ["cpp_cpu_reference", "rust_cpu"],
    "validation_mode": "synthetic_native_cpu_only",
}


class ContractError(RuntimeError):
    """The prepared-session contract or source binding failed closed."""


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
    rust_source_path: Path = DEFAULT_RUST_SOURCE,
    python_source_path: Path = DEFAULT_PYTHON_SOURCE,
    test_source_path: Path = DEFAULT_TEST_SOURCE,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
) -> dict[str, object]:
    document, raw = _read_json(contract_path)
    _require_exact_keys(
        document,
        {"api", "authority", "lifecycle", "schema_id", "scope", "status"},
        label="contract",
    )
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_native_fixed64_prepared_session/1.0.0"
        or document["status"]
        != "synthetic_native_cpu_development_authority_false"
    ):
        raise ContractError("contract identity or status changed")
    api = _require_exact_keys(document["api"], set(EXPECTED_API), label="api")
    if api != EXPECTED_API:
        raise ContractError("prepared-session API contract changed")
    authority = _require_exact_keys(
        document["authority"], set(EXPECTED_AUTHORITY_FIELDS), label="authority"
    )
    if any(value is not False for value in authority.values()):
        raise ContractError("prepared-session contract acquired execution authority")
    lifecycle = _require_exact_keys(
        document["lifecycle"], set(EXPECTED_LIFECYCLE), label="lifecycle"
    )
    if lifecycle != EXPECTED_LIFECYCLE:
        raise ContractError("prepared-session lifecycle policy changed")
    scope = _require_exact_keys(
        document["scope"], set(EXPECTED_SCOPE), label="scope"
    )
    if scope != EXPECTED_SCOPE:
        raise ContractError("prepared-session validation scope changed")

    rust_source = _read_text(rust_source_path, label="Rust prepared-session source")
    _require_snippets(
        rust_source,
        (
            '#[pyclass(unsendable, name = "NativeFixed64PreparedSessionV1")]',
            "struct OwnedCompletePipelineInput {",
            "native_fixed64_prepare_session_v1(input: &PyDict)",
            "parse_complete_pipeline_input(input, CompleteTransportVersion::V3)",
            "prepared session v1 is synthetic CPU-only; HIP device execution is unauthorized",
            "let pipeline = input.create_pipeline().map_err(runtime_error)?;",
            ".allow_threads(move || input.run_once())",
            "let receipt = self.input.run(&self.pipeline).map_err(runtime_error)?;",
            'output.set_item("scientific_result_cached", false)?;',
            "PREPARED_SESSION_RECEIPT_DOMAIN",
        ),
        label="Rust prepared-session source",
    )
    session_owner = rust_source.index("struct NativeFixed64PreparedSession {")
    pipeline_field = rust_source.index("pipeline: Fixed64Pipeline,", session_owner)
    input_field = rust_source.index("input: OwnedCompletePipelineInput,", session_owner)
    if not pipeline_field < input_field:
        raise ContractError("prepared-session dependent drop order changed")
    python_source = _read_text(
        python_source_path, label="Python prepared-session source"
    )
    _require_snippets(
        python_source,
        (
            'name = "native_fixed64_prepare_session_v1"',
            "class NativeFixed64PreparedSessionV1:",
            "def prepare_native_fixed64_session(",
            "Rust copies every admitted collection into owned native state.",
            'metadata.get("scientific_result_cached") is not False',
            'len(_NATIVE_FIXED64_PIPELINE_ID).to_bytes(8, "big")',
            '_NATIVE_FIXED64_PIPELINE_ID.encode("ascii")',
        ),
        label="Python prepared-session source",
    )
    test_source = _read_text(test_source_path, label="prepared-session tests")
    _require_snippets(
        test_source,
        (
            "test_prepared_session_reuses_one_native_context_without_caching_science",
            "test_prepared_session_owns_input_after_bounded_native_copy",
            "test_prepared_session_cpu_backends_match_stateless_v3",
            "test_prepared_session_rejects_hip_before_context_creation",
            "test_prepared_session_rejects_mapping_subclass_before_native_lookup",
            "test_prepared_session_does_not_deepcopy_before_native_preflight",
            "test_prepared_session_facade_rejects_metadata_mapping_subclass",
            "rerun.to_dict() == results[\"cli\"].to_dict() == stateless",
            "len({item.consumer_view_receipt_sha256 for item in results.values()}) == 4",
        ),
        label="prepared-session tests",
    )
    documentation = _read_text(
        documentation_path, label="prepared-session documentation"
    )
    _require_snippets(
        documentation,
        (
            "Repeated session calls reuse that exact",
            "Scientific results are not cached.",
            "External authority must reach blocker zero",
            "The class is deliberately `!Send` and `!Sync`.",
            "both HIP backend identifiers fail before a",
        ),
        label="prepared-session documentation",
    )
    return {
        "all_authority_false": True,
        "candidate_denominator": 64,
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "native_entrypoint": EXPECTED_API["native_entrypoint"],
        "persistent_context_reuse": True,
        "scientific_result_cached": False,
        "status": "verified_static_non_authoritative",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--rust-source", type=Path, default=DEFAULT_RUST_SOURCE)
    parser.add_argument("--python-source", type=Path, default=DEFAULT_PYTHON_SOURCE)
    parser.add_argument("--test-source", type=Path, default=DEFAULT_TEST_SOURCE)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify(
            contract_path=args.contract,
            rust_source_path=args.rust_source,
            python_source_path=args.python_source,
            test_source_path=args.test_source,
            documentation_path=args.documentation,
        )
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
