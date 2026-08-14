#!/usr/bin/env python3
"""Verify the frozen, non-authoritative repository synthetic D0 CPU parity policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_cpu_parity_v1.json"
DEFAULT_SOURCE_CONTRACT = REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_source_v1.json"
DEFAULT_SESSION_CONTRACT = REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_session_v1.json"
DEFAULT_RUST_SOURCE = REPOSITORY_ROOT / "rust_engine_v2/src/complete_fixed64_pipeline.rs"
DEFAULT_RUNTIME_SOURCE = REPOSITORY_ROOT / "rust/betelgeuze-runtime/src/qualification.rs"
DEFAULT_RUNTIME_EXPORT = REPOSITORY_ROOT / "rust/betelgeuze-runtime/src/lib.rs"
DEFAULT_PYTHON_SOURCE = REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_cpu_parity.py"
DEFAULT_CLI_SOURCE = REPOSITORY_ROOT / "betelgeuze_engine_v2/standalone_cli.py"
DEFAULT_TEST_SOURCE = REPOSITORY_ROOT / "tests/unit/test_engine_v2_native_fixed64_complete_pipeline.py"
DEFAULT_DOCUMENTATION = REPOSITORY_ROOT / "docs/engine_v2_repository_synthetic_d0_cpu_parity_v1.md"
DEFAULT_RELEASE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml"
DEFAULT_NATIVE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml"

POLICY_SHA256 = "47d3fd8a0fe341591d46c0427dc45d726898813e953b039ce66fd47816ad1511"
SOURCE_CONTRACT_SHA256 = "2dbd7da6c8a2b7e6612eabbf15c118bddd659629f974374aac6bccc22deb7e96"
SESSION_CONTRACT_SHA256 = "51f314de529f1ed3b000bdfff2f7f3494a308303f5d6acf19ab517b3e7054de3"
ACKNOWLEDGMENT = (
    "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:"
    "no-qualification-rerun:no-product-action:no-public-or-scientific-claim"
)
PRIMARY = [23, 63, 9, 10, 29, 16, 61, 8, 11, 52, 20, 13, 33, 26, 34, 22]
REPRESENTATIVES = [23, 9, 10, 29, 16, 8, 11, 52, 20, 13, 33, 22]
TOP_K = [23, 9, 10, 29, 16]
EXPECTED_AUTHORITY = {
    "fresh_holdout_execution_authorized": False,
    "historical_ab_execution_authorized": False,
    "hip_device_execution_authorized": False,
    "molecular_execution_authorized": False,
    "product_performance_claim_authorized": False,
    "public_benchmark_authorized": False,
    "qualification_rerun_authorized": False,
    "reservation_authorized": False,
    "scientific_claim_authorized": False,
    "stage0_admission_authorized": False,
}
EXPECTED_COMPARISON = {
    "absolute_tolerance": 1e-11,
    "all_coordinate_states_compared": True,
    "all_geometric_measurements_compared": True,
    "all_refinement_objectives_compared": True,
    "all_scorer_v1_terms_compared": True,
    "all_validity_measurements_compared": True,
    "backend_bound_receipt_identity_parity_required": False,
    "coordinate_sha256_identity_parity_required": False,
    "exact_decision_sha256_parity_required": True,
    "exact_denominator_and_stage_counts_required": True,
    "exact_failure_status_and_validity_masks_required": True,
    "exact_rank_and_v7_selection_required": True,
    "exact_source_and_allocation_identity_parity_required": True,
    "nonfinite_values_allowed": False,
    "relative_tolerance": 4e-12,
    "repeat_stability_required": True,
}
EXPECTED_RESULT = {
    "allocation_receipt_sha256": ("8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb"),
    "candidate_denominator": 64,
    "cluster_count": 12,
    "compared_f64_count": 16_896,
    "generated_count": 54,
    "initial_admitted_count": 30,
    "ligand_atom_count": 5,
    "native_source_bundle_receipt_sha256": ("80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f"),
    "post_admitted_count": 16,
    "post_rejected_count": 0,
    "prepared_input_receipt_sha256": ("9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e"),
    "primary_slot_indices": PRIMARY,
    "receptor_atom_count": 5,
    "refined_count": 16,
    "representative_slot_indices": REPRESENTATIVES,
    "scientific_decision_sha256": ("8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4"),
    "scored_count": 16,
    "scorer_v1_term_count": 8,
    "top_k_slot_indices": TOP_K,
    "typed_failure_count": 10,
    "valid_count": 16,
    "valid_slot_indices": PRIMARY,
}
EXPECTED_RESTRICTIONS = {
    "actual_molecular_execution_allowed": False,
    "contains_molecular_cases": False,
    "fresh_or_historical_case_input_allowed": False,
    "github_actions_production_authority_allowed": False,
    "performance_measurement_allowed": False,
    "reservation_allowed": False,
    "result_dependent_configuration_allowed": False,
    "test_double_production_authority_allowed": False,
}
EXPECTED_RUNTIME = {
    "entrypoint": "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
    "native_backends": ["cpp_cpu_reference", "rust_cpu"],
    "no_caller_science_input": True,
    "source_contract_sha256": SOURCE_CONTRACT_SHA256,
    "source_session_contract_sha256": SESSION_CONTRACT_SHA256,
    "synthetic_only_acknowledgment": ACKNOWLEDGMENT,
    "timing_fields_forbidden": True,
}


class ContractError(RuntimeError):
    """Raised when the frozen CPU parity contract drifts."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_contract(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("ascii"), object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid parity policy JSON: {exc}") from exc
    if type(document) is not dict:
        raise ContractError("parity policy must be an exact object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != canonical:
        raise ContractError("parity policy is not canonical JSON")
    return document, raw


def _require_exact(value: object, expected: object, *, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ContractError(f"{name} changed")


def _require_snippets(path: Path, snippets: tuple[str, ...]) -> None:
    raw = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in raw]
    if missing:
        raise ContractError(f"{path.name} missing frozen snippets: {missing}")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    source_contract_path: Path = DEFAULT_SOURCE_CONTRACT,
    session_contract_path: Path = DEFAULT_SESSION_CONTRACT,
    rust_source_path: Path = DEFAULT_RUST_SOURCE,
    runtime_source_path: Path = DEFAULT_RUNTIME_SOURCE,
    runtime_export_path: Path = DEFAULT_RUNTIME_EXPORT,
    python_source_path: Path = DEFAULT_PYTHON_SOURCE,
    cli_source_path: Path = DEFAULT_CLI_SOURCE,
    test_source_path: Path = DEFAULT_TEST_SOURCE,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    release_workflow_path: Path = DEFAULT_RELEASE_WORKFLOW,
    native_workflow_path: Path = DEFAULT_NATIVE_WORKFLOW,
) -> dict[str, object]:
    document, raw = _load_contract(contract_path)
    _require_exact(
        frozenset(document),
        frozenset(
            {
                "authority",
                "comparison",
                "expected",
                "profile_id",
                "restrictions",
                "runtime",
                "schema_id",
                "status",
            }
        ),
        name="parity policy keys",
    )
    _require_exact(
        document["schema_id"],
        "betelgeuze.engine_v2_repository_synthetic_d0_cpu_parity_policy/1.0.0",
        name="schema_id",
    )
    _require_exact(
        document["profile_id"],
        "engine_v2_repository_synthetic_d0_cpu_parity_v1",
        name="profile_id",
    )
    _require_exact(
        document["status"],
        "frozen_synthetic_non_authoritative_cpu_parity_policy",
        name="status",
    )
    _require_exact(document["authority"], EXPECTED_AUTHORITY, name="authority")
    _require_exact(document["comparison"], EXPECTED_COMPARISON, name="comparison")
    _require_exact(document["expected"], EXPECTED_RESULT, name="expected result")
    _require_exact(document["restrictions"], EXPECTED_RESTRICTIONS, name="restrictions")
    _require_exact(document["runtime"], EXPECTED_RUNTIME, name="runtime")
    contract_sha256 = hashlib.sha256(raw).hexdigest()
    if contract_sha256 != POLICY_SHA256:
        raise ContractError("parity policy SHA-256 changed")
    if _file_sha256(source_contract_path) != SOURCE_CONTRACT_SHA256:
        raise ContractError("parity policy is cross-wired to its source contract")
    if _file_sha256(session_contract_path) != SESSION_CONTRACT_SHA256:
        raise ContractError("parity policy is cross-wired to its source session contract")

    _require_snippets(
        rust_source_path,
        (
            "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
            "compare_fixed64_scientific_numeric_parity(",
            "performance_measurement_performed",
            '"qualification_rerun_authorized"',
            POLICY_SHA256,
        ),
    )
    _require_snippets(
        runtime_source_path,
        (
            "pub fn compare_fixed64_scientific_numeric_parity(",
            "fixed64 scientific parity tolerances must be finite and non-negative",
        ),
    )
    _require_snippets(
        runtime_export_path,
        ("compare_fixed64_scientific_numeric_parity",),
    )
    _require_snippets(
        python_source_path,
        (
            "def _rederive_receipt_sha256(",
            "def run_repository_synthetic_d0_cpu_parity(",
            "CPU parity receipt is not independently rederivable",
            POLICY_SHA256,
        ),
    )
    _require_snippets(
        cli_source_path,
        (
            '"--repository-native-d0-cpu-parity"',
            "verify_repository_synthetic_d0_native_cpu_parity(",
        ),
    )
    _require_snippets(
        test_source_path,
        (
            "test_repository_d0_cpu_parity_is_native_complete_and_non_authoritative",
            "test_cli_runs_repository_d0_cpu_parity_without_result_input",
        ),
    )
    _require_snippets(
        documentation_path,
        (
            "all 16,896 binary64 values",
            "does not call or reopen the consumed exactly-once CPU V7 qualification",
            "External authority must reach blocker zero",
        ),
    )
    workflow_snippets = (
        "config/engine_v2_repository_synthetic_d0_cpu_parity_v1.json",
        "tools/verify_engine_v2_repository_synthetic_d0_cpu_parity_v1.py",
        "tests/unit/test_verify_engine_v2_repository_synthetic_d0_cpu_parity_v1.py",
    )
    _require_snippets(release_workflow_path, workflow_snippets)
    _require_snippets(native_workflow_path, workflow_snippets)
    return {
        "schema_id": document["schema_id"],
        "status": "verified_static_non_authoritative",
        "contract_sha256": contract_sha256,
        "all_authority_false": all(value is False for value in EXPECTED_AUTHORITY.values()),
        "candidate_denominator": EXPECTED_RESULT["candidate_denominator"],
        "compared_f64_count": EXPECTED_RESULT["compared_f64_count"],
        "absolute_tolerance": EXPECTED_COMPARISON["absolute_tolerance"],
        "relative_tolerance": EXPECTED_COMPARISON["relative_tolerance"],
        "scientific_decision_sha256": EXPECTED_RESULT["scientific_decision_sha256"],
        "performance_measurement_allowed": False,
        "qualification_rerun_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    arguments = parser.parse_args()
    print(json.dumps(verify(contract_path=arguments.contract), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
