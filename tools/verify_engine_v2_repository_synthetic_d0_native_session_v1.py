#!/usr/bin/env python3
"""Verify the source-bound, non-authoritative repository D0 native session."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_session_v1.json"
)
DEFAULT_SOURCE_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_source_v1.json"
)
DEFAULT_RUST_SOURCE = (
    REPOSITORY_ROOT / "rust_engine_v2/src/complete_fixed64_pipeline.rs"
)
DEFAULT_PYTHON_SOURCE = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_fixed64_consumers.py"
)
DEFAULT_CLI_SOURCE = REPOSITORY_ROOT / "betelgeuze_engine_v2/standalone_cli.py"
DEFAULT_TEST_SOURCE = (
    REPOSITORY_ROOT / "tests/unit/test_engine_v2_native_fixed64_complete_pipeline.py"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_repository_synthetic_d0_native_session_v1.md"
)
DEFAULT_RELEASE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml"
)
DEFAULT_NATIVE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml"
)

ACKNOWLEDGMENT = (
    "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:"
    "no-qualification-rerun:no-product-action:no-public-or-scientific-claim"
)
EXPECTED_API = {
    "consumer_surfaces": ["cli", "benchmark", "api", "product_shadow"],
    "native_entrypoint": ("native_fixed64_prepare_repository_synthetic_d0_session_v1"),
    "python_factory": "prepare_repository_synthetic_d0_session",
    "synthetic_only_acknowledgment": ACKNOWLEDGMENT,
}
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
        "scientific_claim_authorized",
        "stage0_admission_authorized",
    }
)
EXPECTED_BUILD_BINDING_POLICY = {
    "allowed_cpu_backends": ["cpp_cpu_reference", "rust_cpu"],
    "attested_profile_feature_sets": {
        "cpu-manylinux_2_28-gcc14": "extension-module",
        "hip-gfx1030-rocm602": "extension-module,hip",
    },
    "required_attested_wrapper_control": "verified_frozen_wrapper",
    "unattested_build_profile_id": "direct-cargo-unattested",
    "unattested_status": "unattested_direct_cargo",
    "unattested_toolchain_identity": "unattested",
    "unattested_wrapper_control": "direct_cargo_unattested",
}
EXPECTED_FIXED_INPUT = {
    "allocation_receipt_sha256": (
        "8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb"
    ),
    "candidate_denominator": 64,
    "exact_cartesian_pair_count": 25,
    "feature_geometry_count": 13,
    "feature_geometry_inventory_receipt_sha256": (
        "0a13f3fd3ee9a95ef496135c6834dd3528aff729e20aa032df07182f6abe78f0"
    ),
    "ligand_atom_count": 5,
    "prepared_input_scalar_count": 1_178,
    "prepared_source_receipt_sha256": (
        "9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e"
    ),
    "ready_slot_count": 54,
    "receptor_atom_count": 5,
    "source_bundle_receipt_sha256": (
        "80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f"
    ),
    "typed_failure_count": 10,
}
EXPECTED_FROZEN_DECISION = {
    "cluster_count": 12,
    "initial_admitted_count": 30,
    "post_admitted_count": 16,
    "post_rejected_count": 0,
    "primary_slot_indices": [
        23,
        63,
        9,
        10,
        29,
        16,
        61,
        8,
        11,
        52,
        20,
        13,
        33,
        26,
        34,
        22,
    ],
    "refined_count": 16,
    "representative_slot_indices": [23, 9, 10, 29, 16, 8, 11, 52, 20, 13, 33, 22],
    "scientific_decision_sha256": (
        "8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4"
    ),
    "scored_count": 16,
    "top_k_slot_indices": [23, 9, 10, 29, 16],
    "valid_count": 16,
    "valid_slot_indices": [
        23,
        63,
        9,
        10,
        29,
        16,
        61,
        8,
        11,
        52,
        20,
        13,
        33,
        26,
        34,
        22,
    ],
}
EXPECTED_REFINEMENT_POLICY = {
    "baseline_torsion_angles_radians": "all_zero_64_by_5",
    "candidate_denominator": 64,
    "candidate_mode_lanes": [
        {
            "end_exclusive": 24,
            "mode": "v6_baseline_v2_lane",
            "start_inclusive": 0,
        },
        {
            "end_exclusive": 44,
            "mode": "v6_baseline_v3_lane",
            "start_inclusive": 24,
        },
        {
            "end_exclusive": 64,
            "mode": "v6_baseline_v2_lane",
            "start_inclusive": 44,
        },
    ],
    "result_dependent_retry_allowed": False,
    "rigid_max_steps": 20,
    "rmsd_threshold_angstrom_binary64_hex": "0x1.8000000000000p+0",
    "schema_id": (
        "betelgeuze.engine_v2_repository_synthetic_d0_native_refinement_policy/1.0.0"
    ),
    "torsion_eligible_slot_indices": list(range(24, 44)),
    "torsion_max_steps_eligible": 4,
    "torsion_max_steps_ineligible": 0,
}
EXPECTED_POST_ADMISSION_POLICY = {
    "candidate_denominator": 64,
    "hard_rejection_minimum_vdw_ratio_binary64_hex": "0x1.199999999999ap-1",
    "maximum_batch_exact_pair_evaluations": 16_777_216,
    "post_rejection_deleted": False,
    "result_dependent_retry_allowed": False,
    "schema_id": (
        "betelgeuze.engine_v2_repository_synthetic_d0_native_post_admission_policy/1.0.0"
    ),
    "traversal": "full_cartesian_ligand_index_major_receptor_index_minor",
}
EXPECTED_REFINEMENT_POLICY_SHA256 = (
    "6508cf3aca1713f0d8f2432f227996694f47c32ea93e2f444a4d792414152082"
)
EXPECTED_POST_ADMISSION_POLICY_SHA256 = (
    "f6edd080650c824fdb13c33153d20f88d1b7958840ccb75bbaf2c7e4fe7f2841"
)
EXPECTED_RUNTIME_EVIDENCE = {
    "backend_binding_inputs_exposed": True,
    "backend_binding_rederived_in_python": True,
    "backend_independent_scientific_decision_sha256_exposed": True,
    "caller_science_transport_consumed": False,
    "complete_scorer_v1_weighted_term_count": 8,
    "complete_validity_evidence_required": True,
    "cpp_rust_decision_parity_required": True,
    "persistent_native_context": True,
    "qualification_runner_called": False,
    "scientific_result_cached": False,
    "source_materializer_called_in_rust": True,
    "unattested_direct_cargo_status_explicit": True,
}
EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS = {
    "contact_policy_sha256": (
        "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
    ),
    "validity_scorer_context_receipt_sha256": (
        "8471a70101541cb974ac334db79ea14607024ecce17e2ca3838f679c3eb5271e"
    ),
}


class ContractError(RuntimeError):
    """The repository D0 native-session contract failed closed."""


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"{label} is unavailable: {path}") from exc
    try:
        value = json.loads(raw, object_pairs_hook=_pairs_no_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError(f"{label} is not valid UTF-8 JSON") from exc
    if type(value) is not dict:
        raise ContractError(f"{label} must be an object")
    canonical = (
        json.dumps(value, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True)
        + "\n"
    ).encode("ascii")
    if raw != canonical:
        raise ContractError(f"{label} is not canonical pretty ASCII JSON")
    return value, raw


def _read_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"{label} is unavailable or not UTF-8: {path}") from exc


def _exact_dict(value: object, expected: set[str], *, label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ContractError(f"{label} key schema changed")
    return value


def _policy_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _require_snippets(source: str, snippets: tuple[str, ...], *, label: str) -> None:
    missing = [snippet for snippet in snippets if snippet not in source]
    if missing:
        raise ContractError(f"{label} is missing frozen snippets: {missing}")


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    source_contract_path: Path = DEFAULT_SOURCE_CONTRACT,
    rust_source_path: Path = DEFAULT_RUST_SOURCE,
    python_source_path: Path = DEFAULT_PYTHON_SOURCE,
    cli_source_path: Path = DEFAULT_CLI_SOURCE,
    test_source_path: Path = DEFAULT_TEST_SOURCE,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    release_workflow_path: Path = DEFAULT_RELEASE_WORKFLOW,
    native_workflow_path: Path = DEFAULT_NATIVE_WORKFLOW,
) -> dict[str, object]:
    document, raw = _read_json(contract_path, label="session contract")
    _exact_dict(
        document,
        {
            "api",
            "authority",
            "build_binding_policy",
            "fixed_input",
            "frozen_decision",
            "policy_receipts",
            "runtime_evidence",
            "schema_id",
            "scientific_context_receipts",
            "status",
        },
        label="session contract",
    )
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_repository_synthetic_d0_native_session_policy/1.0.0"
        or document["status"] != "synthetic_native_cpu_common_session_authority_false"
    ):
        raise ContractError("session contract identity or status changed")
    api = _exact_dict(document["api"], set(EXPECTED_API), label="api")
    if api != EXPECTED_API:
        raise ContractError("repository D0 session API changed")
    authority = _exact_dict(
        document["authority"], set(EXPECTED_AUTHORITY_FIELDS), label="authority"
    )
    if any(value is not False for value in authority.values()):
        raise ContractError("repository D0 session acquired execution authority")
    build_binding_policy = _exact_dict(
        document["build_binding_policy"],
        set(EXPECTED_BUILD_BINDING_POLICY),
        label="build binding policy",
    )
    if build_binding_policy != EXPECTED_BUILD_BINDING_POLICY:
        raise ContractError("repository D0 build binding policy changed")
    fixed_input = _exact_dict(
        document["fixed_input"], set(EXPECTED_FIXED_INPUT), label="fixed input"
    )
    if fixed_input != EXPECTED_FIXED_INPUT:
        raise ContractError("repository D0 fixed input changed")
    frozen_decision = _exact_dict(
        document["frozen_decision"],
        set(EXPECTED_FROZEN_DECISION),
        label="frozen decision",
    )
    if frozen_decision != EXPECTED_FROZEN_DECISION:
        raise ContractError("repository D0 frozen decision changed")
    runtime_evidence = _exact_dict(
        document["runtime_evidence"],
        set(EXPECTED_RUNTIME_EVIDENCE),
        label="runtime evidence",
    )
    if runtime_evidence != EXPECTED_RUNTIME_EVIDENCE:
        raise ContractError("repository D0 runtime evidence policy changed")
    scientific_context_receipts = _exact_dict(
        document["scientific_context_receipts"],
        set(EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS),
        label="scientific context receipts",
    )
    if scientific_context_receipts != EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS:
        raise ContractError("repository D0 scientific context receipt changed")
    policies = _exact_dict(
        document["policy_receipts"],
        {
            "post_admission_policy",
            "post_admission_policy_sha256",
            "refinement_policy",
            "refinement_policy_sha256",
        },
        label="policy receipts",
    )
    if policies["refinement_policy"] != EXPECTED_REFINEMENT_POLICY:
        raise ContractError("repository D0 refinement policy changed")
    if policies["post_admission_policy"] != EXPECTED_POST_ADMISSION_POLICY:
        raise ContractError("repository D0 post-admission policy changed")
    refinement_sha256 = _policy_sha256(policies["refinement_policy"])
    post_admission_sha256 = _policy_sha256(policies["post_admission_policy"])
    if (
        refinement_sha256 != EXPECTED_REFINEMENT_POLICY_SHA256
        or policies["refinement_policy_sha256"] != refinement_sha256
        or post_admission_sha256 != EXPECTED_POST_ADMISSION_POLICY_SHA256
        or policies["post_admission_policy_sha256"] != post_admission_sha256
    ):
        raise ContractError("repository D0 policy receipt is not rederivable")

    source_contract, _ = _read_json(source_contract_path, label="source contract")
    source_identities = source_contract.get("receipt_identities")
    if type(source_identities) is not dict or (
        source_identities.get("native_source_bundle_receipt_sha256")
        != EXPECTED_FIXED_INPUT["source_bundle_receipt_sha256"]
        or source_identities.get("prepared_input_receipt_sha256")
        != EXPECTED_FIXED_INPUT["prepared_source_receipt_sha256"]
        or source_identities.get("feature_inventory_receipt_sha256")
        != EXPECTED_FIXED_INPUT["feature_geometry_inventory_receipt_sha256"]
        or source_identities.get("allocation_receipt_sha256")
        != EXPECTED_FIXED_INPUT["allocation_receipt_sha256"]
    ):
        raise ContractError(
            "repository D0 session is cross-wired to its source contract"
        )

    rust_source = _read_text(rust_source_path, label="Rust session source")
    _require_snippets(
        rust_source,
        (
            "native_fixed64_prepare_repository_synthetic_d0_session_v1",
            "materialize_repository_synthetic_d0_sources()",
            "repository_d0_scoring_features(",
            "repository_d0_topology(",
            EXPECTED_REFINEMENT_POLICY_SHA256,
            EXPECTED_POST_ADMISSION_POLICY_SHA256,
            EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS["contact_policy_sha256"],
            EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS[
                "validity_scorer_context_receipt_sha256"
            ],
            EXPECTED_FROZEN_DECISION["scientific_decision_sha256"],
            "repository_d0_toolchain_attestation_status()",
            "repository_d0_toolchain_attestation_status_for(",
            '"verified_frozen_wrapper"',
            'return Ok("unattested_direct_cargo")',
            "append_repository_d0_binding(",
            ".scientific_projection()",
            "HIP device execution is unauthorized",
            ACKNOWLEDGMENT,
        ),
        label="Rust session source",
    )
    if (
        "b23d517b1b5d477129670c70fd9894219f14eb5f7bdb4ab06805ff0243e93beb"
        in rust_source
    ):
        raise ContractError(
            "repository D0 session retained the obsolete unmerged policy SHA"
        )

    python_source = _read_text(python_source_path, label="Python session facade")
    _require_snippets(
        python_source,
        (
            "class NativeRepositorySyntheticD0EvidenceV1",
            "class NativeRepositorySyntheticD0PreparedSessionV1",
            "def prepare_repository_synthetic_d0_session(",
            "def _repository_d0_backend_binding_digest(",
            "repository D0 session is synthetic CPU-only; HIP execution is unauthorized",
            EXPECTED_FROZEN_DECISION["scientific_decision_sha256"],
            "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:",
            "no-qualification-rerun:no-product-action:no-public-or-scientific-claim",
        ),
        label="Python session facade",
    )
    cli_source = _read_text(cli_source_path, label="standalone CLI source")
    _require_snippets(
        cli_source,
        (
            "def dock_repository_synthetic_d0_native(",
            '"--repository-native-d0-backend"',
            "REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT",
            "repository native D0 docking requires --test-only-synthetic",
        ),
        label="standalone CLI source",
    )
    tests = _read_text(test_source_path, label="native session tests")
    _require_snippets(
        tests,
        (
            "test_repository_d0_native_session_uses_one_source_bound_core_across_surfaces",
            "test_repository_d0_native_session_rejects_authority_and_binding_drift",
            "test_cli_routes_repository_d0_without_caller_science",
            "len(set(decisions.values())) == 1",
            "len({result.pipeline_receipt_sha256 for result in results.values()}) == 1",
        ),
        label="native session tests",
    )
    documentation = _read_text(documentation_path, label="session documentation")
    _require_snippets(
        documentation,
        (
            "no-caller-science entrypoint",
            "Every returned candidate retains an eight-value `ScorerV1`",
            EXPECTED_FROZEN_DECISION["scientific_decision_sha256"],
            "Numeric score-term and validity tolerance qualification is",
            "External authority must reach blocker zero",
        ),
        label="session documentation",
    )
    release_workflow = _read_text(
        release_workflow_path, label="release-candidate workflow"
    )
    native_workflow = _read_text(native_workflow_path, label="native workflow")
    workflow_snippets = (
        "config/engine_v2_repository_synthetic_d0_native_session_v1.json",
        "tools/verify_engine_v2_repository_synthetic_d0_native_session_v1.py",
        "docs/engine_v2_repository_synthetic_d0_native_session_v1.md",
        "Verify repository synthetic D0 native session v1 contract",
    )
    _require_snippets(
        release_workflow,
        workflow_snippets
        + (
            "python tools/verify_engine_v2_repository_synthetic_d0_native_session_v1.py",
        ),
        label="release-candidate workflow",
    )
    _require_snippets(
        native_workflow,
        workflow_snippets
        + (
            "python3 tools/verify_engine_v2_repository_synthetic_d0_native_session_v1.py",
            "rust_engine_v2/**",
            "betelgeuze_engine_v2/docking/native_fixed64_consumers.py",
            "betelgeuze_engine_v2/standalone_cli.py",
            "tests/unit/test_engine_v2_native_fixed64_complete_pipeline.py",
        ),
        label="native workflow",
    )
    return {
        "all_authority_false": True,
        "candidate_denominator": 64,
        "complete_scorer_v1_weighted_term_count": 8,
        "contact_policy_sha256": EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS[
            "contact_policy_sha256"
        ],
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "cpp_rust_decision_parity_required": True,
        "post_admission_policy_sha256": post_admission_sha256,
        "refinement_policy_sha256": refinement_sha256,
        "scientific_decision_sha256": EXPECTED_FROZEN_DECISION[
            "scientific_decision_sha256"
        ],
        "status": "verified_static_non_authoritative",
        "validity_scorer_context_receipt_sha256": (
            EXPECTED_SCIENTIFIC_CONTEXT_RECEIPTS[
                "validity_scorer_context_receipt_sha256"
            ]
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--source-contract", type=Path, default=DEFAULT_SOURCE_CONTRACT)
    parser.add_argument("--rust-source", type=Path, default=DEFAULT_RUST_SOURCE)
    parser.add_argument("--python-source", type=Path, default=DEFAULT_PYTHON_SOURCE)
    parser.add_argument("--cli-source", type=Path, default=DEFAULT_CLI_SOURCE)
    parser.add_argument("--test-source", type=Path, default=DEFAULT_TEST_SOURCE)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    parser.add_argument(
        "--release-workflow", type=Path, default=DEFAULT_RELEASE_WORKFLOW
    )
    parser.add_argument("--native-workflow", type=Path, default=DEFAULT_NATIVE_WORKFLOW)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify(
            contract_path=args.contract,
            source_contract_path=args.source_contract,
            rust_source_path=args.rust_source,
            python_source_path=args.python_source,
            cli_source_path=args.cli_source,
            test_source_path=args.test_source,
            documentation_path=args.documentation,
            release_workflow_path=args.release_workflow,
            native_workflow_path=args.native_workflow,
        )
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
