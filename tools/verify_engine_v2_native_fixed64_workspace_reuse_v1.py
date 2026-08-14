#!/usr/bin/env python3
"""Verify non-authoritative native fixed64 v2 workspace reuse."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_native_fixed64_workspace_reuse_v1.json"
)
DEFAULT_PUBLIC_HEADER = REPOSITORY_ROOT / "include/betelgeuze/engine.h"
DEFAULT_VENDOR_PUBLIC_HEADER = (
    REPOSITORY_ROOT / "rust/betelgeuze-sys/vendor/include/betelgeuze/engine.h"
)
DEFAULT_INTERNAL_HEADER = REPOSITORY_ROOT / "native/src/internal.hpp"
DEFAULT_VENDOR_INTERNAL_HEADER = (
    REPOSITORY_ROOT / "rust/betelgeuze-sys/vendor/native/src/internal.hpp"
)
DEFAULT_PIPELINE_SOURCE = (
    REPOSITORY_ROOT / "native/src/docking/fixed64_pipeline.cpp"
)
DEFAULT_VENDOR_PIPELINE_SOURCE = (
    REPOSITORY_ROOT
    / "rust/betelgeuze-sys/vendor/native/src/docking/fixed64_pipeline.cpp"
)
DEFAULT_REFINEMENT_PIPELINE_SOURCE = (
    REPOSITORY_ROOT / "native/src/docking/fixed64_refinement_pipeline.cpp"
)
DEFAULT_VENDOR_REFINEMENT_PIPELINE_SOURCE = (
    REPOSITORY_ROOT
    / "rust/betelgeuze-sys/vendor/native/src/docking/fixed64_refinement_pipeline.cpp"
)
DEFAULT_NATIVE_TEST = REPOSITORY_ROOT / "native/tests/docking_fixed64_producer.cpp"
DEFAULT_CMAKE_SOURCE = REPOSITORY_ROOT / "native/CMakeLists.txt"
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_native_fixed64_workspace_reuse_v1.md"
)
DEFAULT_NATIVE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml"
DEFAULT_RELEASE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml"
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
EXPECTED_ABI = {
    "public_abi_major": 1,
    "public_abi_minor": 21,
    "public_handle_remains_incomplete": True,
    "public_struct_layout_changed": False,
    "run_signature_changed": False,
    "same_handle_requires_external_synchronization": True,
}
EXPECTED_RECEIPT_INVARIANTS = {
    "candidate_denominator": 64,
    "receipt_schema_changed": False,
    "run_count_in_scientific_receipt": False,
    "same_input_repeated_output_byte_identical_required": True,
    "scientific_result_cached": False,
    "workspace_identity_in_scientific_receipt": False,
}
EXPECTED_SCOPE = {
    "component": "bg_docking_fixed64_pipeline_v2",
    "hip_disposition": "compile_only_no_device_execution_or_parity_claim",
    "performance_claim": "none_structural_allocation_evidence_only",
    "validated_backends": ["cpp_cpu_reference", "rust_cpu"],
    "validation_mode": "synthetic_native_cpu_only",
}
EXPECTED_VALIDATION = {
    "caller_alias_validation_precedes_workspace_preparation": True,
    "canonical_vendor_source_identity_required": True,
    "descriptor_validation_precedes_workspace_preparation": True,
    "failed_preflight_mutates_workspace": False,
    "native_internal_test_required": True,
    "successful_run_counter_commits_after_output": True,
}
EXPECTED_WORKSPACE = {
    "coordinate_buffer_count": 26,
    "coordinate_element_type": "double",
    "final_coordinate_buffer_count": 3,
    "owner": "opaque_bg_docking_fixed64_pipeline_v2_handle",
    "producer_coordinate_buffer_count": 3,
    "rigid_coordinate_buffer_count": 12,
    "same_shape_second_run_reallocates": False,
    "same_shape_two_run_logical_growth_count": 1,
    "torsion_coordinate_buffer_count": 8,
    "workspace_observability": "internal_test_only_not_public_abi",
    "zero_filled_before_every_run": True,
}


class ContractError(RuntimeError):
    """The workspace-reuse contract or source binding failed closed."""


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"{label} is unavailable: {path}") from exc


def _read_text(path: Path, *, label: str) -> str:
    raw = _read_bytes(path, label=label)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"{label} is not UTF-8: {path}") from exc


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes(path, label="contract")
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


def _require_identical(
    canonical_path: Path, vendor_path: Path, *, label: str
) -> bytes:
    canonical = _read_bytes(canonical_path, label=f"canonical {label}")
    vendor = _read_bytes(vendor_path, label=f"vendored {label}")
    if canonical != vendor:
        raise ContractError(f"canonical and vendored {label} differ")
    return canonical


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    public_header_path: Path = DEFAULT_PUBLIC_HEADER,
    vendor_public_header_path: Path = DEFAULT_VENDOR_PUBLIC_HEADER,
    internal_header_path: Path = DEFAULT_INTERNAL_HEADER,
    vendor_internal_header_path: Path = DEFAULT_VENDOR_INTERNAL_HEADER,
    pipeline_source_path: Path = DEFAULT_PIPELINE_SOURCE,
    vendor_pipeline_source_path: Path = DEFAULT_VENDOR_PIPELINE_SOURCE,
    refinement_pipeline_source_path: Path = DEFAULT_REFINEMENT_PIPELINE_SOURCE,
    vendor_refinement_pipeline_source_path: Path = (
        DEFAULT_VENDOR_REFINEMENT_PIPELINE_SOURCE
    ),
    native_test_path: Path = DEFAULT_NATIVE_TEST,
    cmake_source_path: Path = DEFAULT_CMAKE_SOURCE,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    native_workflow_path: Path = DEFAULT_NATIVE_WORKFLOW,
    release_workflow_path: Path = DEFAULT_RELEASE_WORKFLOW,
) -> dict[str, object]:
    document, raw = _read_json(contract_path)
    _require_exact_keys(
        document,
        {
            "abi",
            "authority",
            "receipt_invariants",
            "schema_id",
            "scope",
            "status",
            "validation",
            "workspace",
        },
        label="contract",
    )
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_native_fixed64_workspace_reuse/1.0.0"
        or document["status"]
        != "synthetic_native_cpu_development_authority_false"
    ):
        raise ContractError("contract identity or status changed")
    abi = _require_exact_keys(document["abi"], set(EXPECTED_ABI), label="abi")
    if abi != EXPECTED_ABI:
        raise ContractError("public ABI policy changed")
    authority = _require_exact_keys(
        document["authority"], set(EXPECTED_AUTHORITY_FIELDS), label="authority"
    )
    if any(value is not False for value in authority.values()):
        raise ContractError("workspace-reuse contract acquired execution authority")
    receipt = _require_exact_keys(
        document["receipt_invariants"],
        set(EXPECTED_RECEIPT_INVARIANTS),
        label="receipt_invariants",
    )
    if receipt != EXPECTED_RECEIPT_INVARIANTS:
        raise ContractError("receipt invariants changed")
    scope = _require_exact_keys(document["scope"], set(EXPECTED_SCOPE), label="scope")
    if scope != EXPECTED_SCOPE:
        raise ContractError("validation scope changed")
    validation = _require_exact_keys(
        document["validation"], set(EXPECTED_VALIDATION), label="validation"
    )
    if validation != EXPECTED_VALIDATION:
        raise ContractError("workspace validation policy changed")
    workspace = _require_exact_keys(
        document["workspace"], set(EXPECTED_WORKSPACE), label="workspace"
    )
    if workspace != EXPECTED_WORKSPACE:
        raise ContractError("workspace layout policy changed")

    public_header = _require_identical(
        public_header_path, vendor_public_header_path, label="public headers"
    ).decode("utf-8")
    _require_snippets(
        public_header,
        (
            "#define BG_ABI_VERSION_MAJOR UINT32_C(1)",
            "#define BG_ABI_VERSION_MINOR UINT32_C(21)",
            "typedef struct bg_docking_fixed64_pipeline_v2",
            "A v2 pipeline handle owns mutable internal coordinate workspace.",
            "same handle require external synchronization",
            "never enter scientific receipts",
        ),
        label="public header",
    )
    internal_header = _require_identical(
        internal_header_path, vendor_internal_header_path, label="internal headers"
    ).decode("utf-8")
    _require_snippets(
        internal_header,
        (
            "struct bg_docking_fixed64_pipeline_v2_workspace final {",
            "uint64_t successful_run_count = 0;",
            "uint64_t coordinate_capacity_growth_count = 0;",
            "std::array<std::vector<double>, 12> rigid_coordinates;",
            "std::array<std::vector<double>, 8> torsion_coordinates;",
            "std::array<std::vector<double>, 3> final_coordinates;",
            "mutable bg_docking_fixed64_pipeline_v2_workspace workspace;",
            "validate_outputs_for_composition(",
            "validate_input_and_overlap_for_composition(",
        ),
        label="internal header",
    )
    pipeline_source = _require_identical(
        pipeline_source_path,
        vendor_pipeline_source_path,
        label="fixed64 pipeline sources",
    ).decode("utf-8")
    _require_snippets(
        pipeline_source,
        (
            "void prepare_coordinate_buffer(",
            "std::fill(buffer.begin(), buffer.end(), 0.0);",
            "prepare_coordinate_buffers(\n        workspace.rigid_coordinates",
            "auto &producer_x = workspace.producer_x;",
            "auto &rigid_coordinates = workspace.rigid_coordinates;",
            "auto &torsion_coordinates = workspace.torsion_coordinates;",
            "auto &final_coordinates = workspace.final_coordinates;",
            "++workspace.successful_run_count;",
        ),
        label="fixed64 pipeline source",
    )
    refinement_pipeline_source = _require_identical(
        refinement_pipeline_source_path,
        vendor_refinement_pipeline_source_path,
        label="fixed64 refinement-pipeline sources",
    ).decode("utf-8")
    _require_snippets(
        refinement_pipeline_source,
        (
            "bg_status validate_outputs_for_composition(",
            "bg_status validate_input_and_overlap_for_composition(",
            "status = validate_component_outputs(",
            "status = validate_cluster_output(pipeline, cluster);",
            "status = validate_pipeline_output(pipeline, output, coordinate_count);",
            "status = validate_outputs_for_composition(\n        pipeline,",
        ),
        label="fixed64 refinement-pipeline source",
    )
    run_start = pipeline_source.index(
        'extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v2_run('
    )
    producer_preflight = pipeline_source.index(
        "validate_for_composition(\n                *context,", run_start
    )
    output_preflight = pipeline_source.index(
        "validate_outputs_for_composition(", producer_preflight
    )
    overlap = pipeline_source.index("status = validate_v2_overlap(", output_preflight)
    prepare = pipeline_source.index("status = prepare_v2_workspace(", overlap)
    commit = pipeline_source.index("*pipeline_output = committed;", prepare)
    successful_count = pipeline_source.index(
        "++workspace.successful_run_count;", commit
    )
    if not (
        run_start
        < producer_preflight
        < output_preflight
        < overlap
        < prepare
        < commit
        < successful_count
    ):
        raise ContractError("workspace validation or commit ordering changed")
    v2_run_source = pipeline_source[run_start:]
    if v2_run_source.count("validate_outputs_for_composition(") != 1 or (
        v2_run_source.count("validate_input_and_overlap_for_composition(") != 1
    ):
        raise ContractError("v2 output or generated-input validation is duplicated")
    for forbidden in (
        "std::vector<double> producer_x(coordinate_count",
        "std::array<std::vector<double>, 12> rigid_coordinates",
        "std::array<std::vector<double>, 8> torsion_coordinates",
        "std::array<std::vector<double>, 3> final_coordinates",
    ):
        if forbidden in v2_run_source:
            raise ContractError("v2 run restored per-call coordinate allocation")

    native_test = _read_text(native_test_path, label="native workspace test")
    _require_snippets(
        native_test,
        (
            '#include "internal.hpp"',
            "workspace.coordinate_capacity_growth_count ==\n        UINT64_C(1)",
            "std::numeric_limits<double>::quiet_NaN()",
            "const CompletePipelineResult first_reused = reused;",
            "repeat_options.repeat_same_output_descriptors = true;",
            "options.undersize_rigid_rows = true;",
            "std::memcmp(\n               &first_reused, &reused, sizeof(first_reused)) == 0",
            "pipeline->workspace.producer_x.empty()",
            "workspace.producer_y.data() == producer_y_workspace",
            "workspace.producer_z.data() == producer_z_workspace",
            "pipeline->workspace.rigid_coordinates.begin()",
        ),
        label="native workspace test",
    )
    cmake_source = _read_text(cmake_source_path, label="native CMake source")
    _require_snippets(
        cmake_source,
        (
            "betelgeuze_engine_docking_fixed64_producer",
            "PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src",
        ),
        label="native CMake source",
    )
    documentation = _read_text(documentation_path, label="documentation")
    _require_snippets(
        documentation,
        (
            "owns 26 reusable `double` buffers",
            "same v2 handle require external synchronization",
            "buffer reuse, not a scientific-result cache.",
            "External authority must reach blocker zero",
            "consumed native fixed64 CPU v7 qualification is never rerun",
        ),
        label="documentation",
    )
    native_workflow = _read_text(native_workflow_path, label="native ABI workflow")
    release_workflow = _read_text(
        release_workflow_path, label="release-candidate workflow"
    )
    workflow_snippets = (
        "config/engine_v2_native_fixed64_workspace_reuse_v1.json",
        "tools/verify_engine_v2_native_fixed64_workspace_reuse_v1.py",
        "docs/engine_v2_native_fixed64_workspace_reuse_v1.md",
        "Verify native fixed64 workspace reuse v1 contract",
        "python3 tools/verify_engine_v2_native_fixed64_workspace_reuse_v1.py",
    )
    _require_snippets(native_workflow, workflow_snippets, label="native ABI workflow")
    _require_snippets(
        release_workflow,
        workflow_snippets[:-1]
        + ("python tools/verify_engine_v2_native_fixed64_workspace_reuse_v1.py",),
        label="release-candidate workflow",
    )
    return {
        "all_authority_false": True,
        "candidate_denominator": 64,
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "coordinate_buffer_count": 26,
        "public_abi": "1.21",
        "same_shape_second_run_reallocates": False,
        "scientific_result_cached": False,
        "status": "verified_static_non_authoritative",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--public-header", type=Path, default=DEFAULT_PUBLIC_HEADER)
    parser.add_argument(
        "--vendor-public-header", type=Path, default=DEFAULT_VENDOR_PUBLIC_HEADER
    )
    parser.add_argument("--internal-header", type=Path, default=DEFAULT_INTERNAL_HEADER)
    parser.add_argument(
        "--vendor-internal-header", type=Path, default=DEFAULT_VENDOR_INTERNAL_HEADER
    )
    parser.add_argument("--pipeline-source", type=Path, default=DEFAULT_PIPELINE_SOURCE)
    parser.add_argument(
        "--vendor-pipeline-source",
        type=Path,
        default=DEFAULT_VENDOR_PIPELINE_SOURCE,
    )
    parser.add_argument(
        "--refinement-pipeline-source",
        type=Path,
        default=DEFAULT_REFINEMENT_PIPELINE_SOURCE,
    )
    parser.add_argument(
        "--vendor-refinement-pipeline-source",
        type=Path,
        default=DEFAULT_VENDOR_REFINEMENT_PIPELINE_SOURCE,
    )
    parser.add_argument("--native-test", type=Path, default=DEFAULT_NATIVE_TEST)
    parser.add_argument("--cmake-source", type=Path, default=DEFAULT_CMAKE_SOURCE)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    parser.add_argument(
        "--native-workflow", type=Path, default=DEFAULT_NATIVE_WORKFLOW
    )
    parser.add_argument(
        "--release-workflow", type=Path, default=DEFAULT_RELEASE_WORKFLOW
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify(
            contract_path=args.contract,
            public_header_path=args.public_header,
            vendor_public_header_path=args.vendor_public_header,
            internal_header_path=args.internal_header,
            vendor_internal_header_path=args.vendor_internal_header,
            pipeline_source_path=args.pipeline_source,
            vendor_pipeline_source_path=args.vendor_pipeline_source,
            refinement_pipeline_source_path=args.refinement_pipeline_source,
            vendor_refinement_pipeline_source_path=(
                args.vendor_refinement_pipeline_source
            ),
            native_test_path=args.native_test,
            cmake_source_path=args.cmake_source,
            documentation_path=args.documentation,
            native_workflow_path=args.native_workflow,
            release_workflow_path=args.release_workflow,
        )
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
