#!/usr/bin/env python3
"""Build a deterministic inventory of Engine V2 CI authority surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, cast

if __package__:
    from . import verify_engine_v2_native_fixed64_cpu_profile_v7 as v7_profile_verifier
    from .verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt import (
        NativeFixed64CPUV7ExecutionReceiptError,
        require_execution_receipt_bytes,
    )
else:
    import verify_engine_v2_native_fixed64_cpu_profile_v7 as v7_profile_verifier
    from verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt import (
        NativeFixed64CPUV7ExecutionReceiptError,
        require_execution_receipt_bytes,
    )


SCHEMA_ID = "betelgeuze.engine_v2_ci_authority_inventory/1.0.0"
AUTHORITATIVE_WORKFLOWS = (
    ".github/workflows/ci-engine-v2-main.yml",
    ".github/workflows/ci-engine-v2-release-candidate.yml",
    ".github/workflows/ci-engine-v2-cpu-reference-validation-protocol.yml",
)
CLEARANCE_ACTIVATION_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
    "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
    "config/engine_v2_source_paired_clearance_activation.json",
)
CLEARANCE_ACTIVATION_REQUIRED_TOKENS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
    "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
    "config/engine_v2_source_paired_clearance_activation.json",
    "tools/verify_engine_v2_source_paired_clearance_activation.py",
    "tests/unit/test_source_paired_clearance_activation.py",
    "tests/unit/test_source_paired_clearance_activation_evidence.py",
    "tests/unit/test_source_paired_torsion_rescue_activation_snapshot.py",
    "tests/unit/test_verify_engine_v2_source_paired_clearance_activation.py",
    "docs/engine_v2_source_paired_clearance_activation.md",
    "docs/engine_v2_source_paired_clearance_selection_policy.md",
    "docs/engine_v2_stage0_status.md",
)
GLOBAL_ORIENTATION_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/docking/global_orientation.py",
    "betelgeuze_engine_v2/docking/global_orientation_evidence.py",
    "betelgeuze_engine_v2/benchmark/oracle_selection_metrics.py",
    "betelgeuze_engine_v2/benchmark/oracle_selection_evidence.py",
    "config/engine_v2_global_orientation_synthetic_contract.json",
)
GLOBAL_ORIENTATION_REQUIRED_TOKENS = (
    *GLOBAL_ORIENTATION_CONTRACT_PATHS,
    "tools/verify_engine_v2_global_orientation_synthetic_contract.py",
    "tests/unit/test_engine_v2_global_orientation.py",
    "tests/unit/test_engine_v2_global_orientation_evidence.py",
    "tests/unit/test_engine_v2_global_orientation_synthetic_contract.py",
    "tests/unit/test_engine_v2_oracle_selection_metrics.py",
    "tests/unit/test_engine_v2_oracle_selection_evidence.py",
    "docs/engine_v2_global_orientation_design.md",
    "tools/build_engine_v2_wheel.py",
    "dist-engine-v2",
    "import betelgeuze_engine_v2.benchmark.oracle_selection_evidence",
    "import betelgeuze_engine_v2.benchmark.oracle_selection_metrics",
    "import betelgeuze_engine_v2.docking.global_orientation",
    "import betelgeuze_engine_v2.docking.global_orientation_evidence",
)
MIXED64_V2_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/docking/mixed64_allocation.py",
    "betelgeuze_engine_v2/docking/geometric_admission_v2.py",
    "betelgeuze_engine_v2/docking/pipeline_candidate_evidence_v2.py",
    "tools/verify_engine_v2_mixed64_candidate_evidence_artifact.py",
    "tests/unit/test_verify_engine_v2_mixed64_candidate_evidence_artifact.py",
    "docs/engine_v2_mixed64_geometric_candidate_evidence_v2.md",
    "config/engine_v2_mixed64_geometric_candidate_evidence_v2.json",
)
MIXED64_V2_REQUIRED_TOKEN_COUNTS = {
    "betelgeuze_engine_v2/docking/mixed64_allocation.py": 1,
    "betelgeuze_engine_v2/docking/geometric_admission_v2.py": 1,
    "betelgeuze_engine_v2/docking/pipeline_candidate_evidence_v2.py": 1,
    "config/engine_v2_mixed64_geometric_candidate_evidence_v2.json": 2,
    "tools/verify_engine_v2_mixed64_geometric_candidate_evidence_v2.py": 4,
    "tools/verify_engine_v2_mixed64_candidate_evidence_artifact.py": 3,
    "tests/unit/test_engine_v2_fixed_mixed64_allocation.py": 2,
    "tests/unit/test_engine_v2_geometric_admission_v2.py": 2,
    "tests/unit/test_engine_v2_pipeline_candidate_evidence_v2.py": 2,
    "tests/unit/test_verify_engine_v2_mixed64_geometric_candidate_evidence_v2.py": 2,
    "tests/unit/test_verify_engine_v2_mixed64_candidate_evidence_artifact.py": 2,
    "docs/engine_v2_mixed64_geometric_candidate_evidence_v2.md": 1,
    "import betelgeuze_engine_v2.docking.mixed64_allocation": 1,
    "import betelgeuze_engine_v2.docking.geometric_admission_v2": 1,
    "import betelgeuze_engine_v2.docking.pipeline_candidate_evidence_v2": 1,
}
MIXED64_V2_REQUIRED_TOKENS = tuple(MIXED64_V2_REQUIRED_TOKEN_COUNTS)
MIXED64_V2_FORBIDDEN_TRUE_AUTHORITY_KEYS = (
    "customer_pose_emission_authorized",
    "existing_rank_auto_change_authorized",
    "fresh_holdout_execution_authorized",
    "historical_execution_authorized",
    "molecular_execution_authorized",
    "product_execution_authorized",
    "product_mutation_authorized",
    "profile_promotion_authority",
    "public_benchmark_execution_authorized",
    "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
)
CPU_PERFORMANCE_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/docking/performance_sidecar.py",
    "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py",
    "betelgeuze_engine_v2/docking/performance_qualification_v3.py",
    "config/engine_v2_cpu_performance_profile.json",
    "config/engine_v2_cpu_performance_v2_terminal_decision.json",
    "config/engine_v2_cpu_performance_profile_v3.json",
    "config/engine_v2_cpu_performance_v3_runner_activation.json",
    "tools/run_engine_v2_cpu_performance_qualification.py",
    "tools/run_engine_v2_cpu_performance_qualification_v3.py",
    "tools/verify_engine_v2_cpu_performance_profile.py",
    "tools/verify_engine_v2_cpu_performance_v2_terminal_decision.py",
    "tools/verify_engine_v2_cpu_performance_profile_v3.py",
    "tools/preflight_engine_v2_cpu_performance_v3.py",
    "tests/unit/test_engine_v2_cpu_performance_sidecar.py",
    "tests/unit/test_verify_engine_v2_cpu_performance_profile.py",
    "tests/unit/test_verify_engine_v2_cpu_performance_v2_terminal_decision.py",
    "tests/unit/test_engine_v2_cpu_performance_host_preflight_v3.py",
    "tests/unit/test_engine_v2_cpu_performance_qualification_v3.py",
    "tests/unit/test_verify_engine_v2_cpu_performance_profile_v3.py",
    "tests/unit/test_engine_v2_native_geometric_admission.py",
    "docs/engine_v2_cpu_performance_qualification.md",
)
CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS = {
    "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py": 1,
    "betelgeuze_engine_v2/docking/performance_qualification_v3.py": 1,
    "config/engine_v2_cpu_performance_profile.json": 2,
    "config/engine_v2_cpu_performance_v2_terminal_decision.json": 2,
    "config/engine_v2_cpu_performance_profile_v3.json": 2,
    "config/engine_v2_cpu_performance_v3_runner_activation.json": 2,
    "tools/run_engine_v2_cpu_performance_qualification.py": 3,
    "tools/run_engine_v2_cpu_performance_qualification_v3.py": 4,
    "tools/verify_engine_v2_cpu_performance_profile.py": 4,
    "tools/verify_engine_v2_cpu_performance_v2_terminal_decision.py": 3,
    "tools/verify_engine_v2_cpu_performance_profile_v3.py": 3,
    "tools/preflight_engine_v2_cpu_performance_v3.py": 3,
    "tests/unit/test_engine_v2_cpu_performance_sidecar.py": 2,
    "tests/unit/test_verify_engine_v2_cpu_performance_profile.py": 2,
    "tests/unit/test_verify_engine_v2_cpu_performance_v2_terminal_decision.py": 2,
    "tests/unit/test_engine_v2_cpu_performance_host_preflight_v3.py": 2,
    "tests/unit/test_engine_v2_cpu_performance_qualification_v3.py": 2,
    "tests/unit/test_verify_engine_v2_cpu_performance_profile_v3.py": 2,
    "tests/unit/test_engine_v2_native_geometric_admission.py": 2,
    "docs/engine_v2_cpu_performance_qualification.md": 1,
    "import betelgeuze_engine_v2.docking.performance_host_preflight_v3": 1,
    "import betelgeuze_engine_v2.docking.performance_qualification_v3": 1,
    "import betelgeuze_engine_v2.docking.performance_sidecar": 1,
}
CPU_PERFORMANCE_REQUIRED_TOKENS = tuple(CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS)
CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS = (
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
)
NATIVE_FIXED64_CPU_V5_CONTRACT_PATHS = (
    "config/engine_v2_native_fixed64_cpu_profile_v5.json",
    "config/engine_v2_native_fixed64_cpu_profile_v5_archive.json",
    "rust/betelgeuze-runtime/src/docking.rs",
    "rust/betelgeuze-runtime/src/lib.rs",
    "rust/betelgeuze-runtime/src/qualification.rs",
    "native/src/docking/fixed64_pipeline.cpp",
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v5.rs",
    "rust/betelgeuze-runtime/tests/docking_fixed64_pipeline.rs",
    "rust/betelgeuze-runtime/tests/fixed64_cpu_probe_v5_activation.rs",
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v5.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v5.py",
    "docs/engine_v2_native_fixed64_cpu_qualification_v5.md",
)
NATIVE_FIXED64_CPU_V5_REQUIRED_TOKEN_COUNTS = {
    "config/engine_v2_native_fixed64_cpu_profile_v5.json": 2,
    "config/engine_v2_native_fixed64_cpu_profile_v5_archive.json": 2,
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v5.py": 4,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v5.py": 2,
    "docs/engine_v2_native_fixed64_cpu_qualification_v5.md": 1,
}
NATIVE_FIXED64_CPU_V5_REQUIRED_TOKENS = tuple(
    NATIVE_FIXED64_CPU_V5_REQUIRED_TOKEN_COUNTS
)
NATIVE_FIXED64_CPU_V5_FALSE_AUTHORITY_KEYS = (
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "qualification_authority",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
)
NATIVE_FIXED64_CPU_V5_FALSE_RESTRICTION_KEYS = (
    "actual_molecular_execution_allowed",
    "contains_molecular_cases",
    "fresh_or_historical_case_input_allowed",
    "github_actions_live_qualification_allowed",
    "github_actions_production_authority_allowed",
    "hip_device_execution_allowed",
    "public_or_scientific_performance_claim_allowed",
    "reservation_allowed",
    "result_dependent_configuration_allowed",
    "test_double_production_authority_allowed",
)
NATIVE_FIXED64_CPU_V6_CONTRACT_PATHS = (
    "config/engine_v2_native_fixed64_cpu_profile_v6.json",
    "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json",
    "config/engine_v2_native_fixed64_cpu_profile_v6_sources.json",
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6.json",
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json",
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json",
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py",
    "tools/verify_engine_v2_native_fixed64_cpu_v6_rustc_wrapper.py",
    "tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v6.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_v6_evidence.py",
    "docs/engine_v2_native_fixed64_cpu_qualification_v6.md",
)
NATIVE_FIXED64_CPU_V6_QUALIFICATION_BUILD_ENV = "BETELGEUZE_V6_QUALIFICATION_BUILD"
NATIVE_FIXED64_CPU_V6_REQUIRED_TOKEN_COUNTS = {
    "config/engine_v2_native_fixed64_cpu_profile_v6.json": 2,
    "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json": 2,
    "config/engine_v2_native_fixed64_cpu_profile_v6_sources.json": 2,
    "docs/engine_v2_native_fixed64_cpu_qualification_v6.md": 1,
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6.json": 1,
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json": 1,
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json": 1,
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py": 4,
    "tools/verify_engine_v2_native_fixed64_cpu_v6_rustc_wrapper.py": 3,
    "tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py": 4,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v6.py": 3,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_v6_evidence.py": 3,
}
NATIVE_FIXED64_CPU_V6_REQUIRED_TOKENS = tuple(
    NATIVE_FIXED64_CPU_V6_REQUIRED_TOKEN_COUNTS
)
NATIVE_FIXED64_CPU_V6_FALSE_AUTHORITY_KEYS = (
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "qualification_authority",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
)
NATIVE_FIXED64_CPU_V6_FALSE_RESTRICTION_KEYS = (
    "actual_molecular_execution_allowed",
    "contains_molecular_cases",
    "fresh_or_historical_case_input_allowed",
    "github_actions_live_qualification_allowed",
    "github_actions_production_authority_allowed",
    "hip_device_execution_allowed",
    "public_or_scientific_performance_claim_allowed",
    "reservation_allowed",
    "result_dependent_configuration_allowed",
    "test_double_production_authority_allowed",
)
NATIVE_FIXED64_CPU_V7_CONTRACT_PATHS = (
    ".github/workflows/ci-native-compute-abi.yml",
    ".github/workflows/ci-native-hip-safe-trusted.yml",
    ".github/workflows/ci-engine-v2-release-candidate.yml",
    "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json",
    "config/engine_v2_native_fixed64_cpu_profile_v7.json",
    "config/engine_v2_native_fixed64_cpu_profile_v7_sources.json",
    "config/engine_v2_native_fixed64_cpu_post_qualification_build_boundary_v1.json",
    "config/engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.json",
    "rust/Cargo.lock",
    "rust/Cargo.toml",
    "rust_engine_v2/Cargo.lock",
    "rust/betelgeuze-runtime/Cargo.toml",
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json",
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7.json",
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7_sources.json",
    "rust/betelgeuze-runtime/assets/original-Cargo.toml",
    "rust/betelgeuze-runtime/assets/workspace-Cargo.lock",
    "rust/betelgeuze-runtime/build.rs",
    "rust/betelgeuze-runtime/src/lib.rs",
    "rust/betelgeuze-runtime/src/fixed64_lane_metrics.rs",
    "rust/betelgeuze-runtime/src/qualification.rs",
    "rust/betelgeuze-runtime/src/qualification_v7.rs",
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-qualify-v7.rs",
    "rust/betelgeuze-sys/build.rs",
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py",
    "tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py",
    "tools/verify_engine_v2_native_fixed64_cpu_v7_evidence.py",
    "tools/verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v7.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_v7_evidence.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py",
    "docs/engine_v2_native_fixed64_cpu_qualification_v7.md",
    "docs/engine_v2_native_fixed64_cpu_qualification_v7_result.md",
)
NATIVE_FIXED64_CPU_V7_BUILD_CONFIGURATION_SHA256 = (
    "6e39e4e07bcb2f9324f242adcf3f48428191b2a91418d34520c6acc1cf046068"
)
NATIVE_FIXED64_CPU_V7_QUALIFICATION_BUILD_ENV = "BETELGEUZE_V7_QUALIFICATION_BUILD"
NATIVE_FIXED64_CPU_V7_COMPILE_BOUND_CONFIG_PATHS = (
    "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json",
    "config/engine_v2_native_fixed64_cpu_profile_v7.json",
    "config/engine_v2_native_fixed64_cpu_profile_v7_sources.json",
)
NATIVE_FIXED64_CPU_V7_REQUIRED_TOKEN_COUNTS = {
    ".github/workflows/ci-native-compute-abi.yml": 1,
    "git fetch --no-tags --depth=1 origin 5c1e4791e988d4c75a5111f933feac85236ba821": 1,
    "git rev-parse --verify '5c1e4791e988d4c75a5111f933feac85236ba821^{commit}'": 1,
    "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json": 2,
    "config/engine_v2_native_fixed64_cpu_profile_v7.json": 2,
    "config/engine_v2_native_fixed64_cpu_profile_v7_sources.json": 2,
    "config/engine_v2_native_fixed64_cpu_post_qualification_build_boundary_v1.json": 1,
    "config/engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.json": 2,
    "docs/engine_v2_native_fixed64_cpu_qualification_v7.md": 1,
    "docs/engine_v2_native_fixed64_cpu_qualification_v7_result.md": 1,
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json": 1,
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7.json": 1,
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7_sources.json": 1,
    "rust/betelgeuze-runtime/assets/original-Cargo.toml": 1,
    "rust/betelgeuze-runtime/assets/workspace-Cargo.lock": 1,
    "rust/betelgeuze-runtime/build.rs": 1,
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py": 4,
    "tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py": 3,
    "tools/verify_engine_v2_native_fixed64_cpu_v7_evidence.py": 4,
    "tools/verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py": 4,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v7.py": 3,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_v7_evidence.py": 3,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py": 3,
}
NATIVE_FIXED64_CPU_V7_REQUIRED_TOKENS = tuple(
    NATIVE_FIXED64_CPU_V7_REQUIRED_TOKEN_COUNTS
)
NATIVE_FIXED64_CPU_V7_FALSE_AUTHORITY_KEYS = (
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "qualification_authority",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
)
NATIVE_FIXED64_CPU_V7_FALSE_RESTRICTION_KEYS = (
    "actual_molecular_execution_allowed",
    "contains_molecular_cases",
    "fresh_or_historical_case_input_allowed",
    "github_actions_live_qualification_allowed",
    "github_actions_production_authority_allowed",
    "hip_device_execution_allowed",
    "public_or_scientific_performance_claim_allowed",
    "reservation_allowed",
    "result_dependent_configuration_allowed",
    "test_double_production_authority_allowed",
)
ONE_SHOT_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_ab.py",
    "config/engine_v2_source_paired_clearance_one_shot_ab.json",
)
ONE_SHOT_REQUIRED_TOKENS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_ab.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_legacy.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_binding.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_evidence.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_external_gate.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_full_evidence.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_result.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_result_legacy.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_result_binding.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_verdict_diagnostics.py",
    "config/engine_v2_source_paired_clearance_one_shot_ab.json",
    "tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py",
    "tools/verify_engine_v2_source_paired_clearance_one_shot_ab.py",
    "tests/unit/test_source_paired_clearance_one_shot_ab.py",
    "tests/unit/test_source_paired_clearance_one_shot_canonical_imports.py",
    "tests/unit/test_source_paired_clearance_one_shot_evidence.py",
    "tests/unit/test_source_paired_clearance_one_shot_external_gate.py",
    "tests/unit/test_source_paired_clearance_one_shot_full_evidence.py",
    "tests/unit/test_source_paired_clearance_one_shot_result.py",
    "tests/unit/test_source_paired_clearance_one_shot_source_policy_tamper.py",
    "tests/unit/test_source_paired_clearance_one_shot_verdict_semantics.py",
    "docs/engine_v2_source_paired_clearance_one_shot_ab.md",
    "dist-engine-v2",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_binding",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_evidence",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_external_gate",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_full_evidence",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_legacy",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result_binding",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result_legacy",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_verdict_diagnostics",
)
EXTERNAL_RESERVATION_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_external_reservation.py",
    "config/engine_v2_source_paired_clearance_external_reservation.json",
)
EXTERNAL_RESERVATION_REQUIRED_TOKENS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_external_reservation.py",
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_one_shot_external_gate.py",
    "config/engine_v2_source_paired_clearance_external_reservation.json",
    "tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py",
    "tools/verify_engine_v2_source_paired_clearance_one_shot_ab.py",
    "tools/verify_engine_v2_source_paired_clearance_external_reservation.py",
    "tests/unit/test_source_paired_clearance_external_reservation.py",
    "tests/unit/test_source_paired_clearance_external_reservation_concurrency.py",
    "tests/unit/test_source_paired_clearance_one_shot_external_gate.py",
    "docs/engine_v2_source_paired_clearance_external_reservation.md",
    "dist-engine-v2",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation",
    "import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_external_gate",
)
STANDALONE_PIPELINE_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/docking/pipeline.py",
    "betelgeuze_engine_v2/docking/synthetic_d0_fixture_admission.json",
)
STANDALONE_PIPELINE_REQUIRED_TOKENS = (
    "tests/unit/test_engine_v2_standalone_pipeline_core.py",
)
STANDALONE_CONSUMER_CONTRACT_PATHS = ("betelgeuze_engine_v2/docking/consumers.py",)
STANDALONE_CONSUMER_REQUIRED_TOKENS = (
    "tests/unit/test_engine_v2_standalone_consumers.py",
)
STANDALONE_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/standalone_cli.py",
    "betelgeuze_engine_v2/docking/pipeline.py",
    "betelgeuze_engine_v2/docking/synthetic_d0_fixture_admission.json",
)
STANDALONE_REQUIRED_TOKENS = (
    "tests/unit/test_engine_v2_standalone_cli.py",
    "tests/unit/test_engine_v2_standalone_pipeline_core.py",
    "tools/run_engine_v2_standalone_cli_wheel_smoke.py",
    "docs/engine_v2_public_api.md",
    "Run installed standalone synthetic D0 fixed64 flow outside checkout",
)
EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS = (
    "config/engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision.json",
    "tools/verify_engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision.py",
)
EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKEN_COUNTS = {
    "config/engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision.json": 2,
    "tools/verify_engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision.py": 4,
    "tests/unit/test_verify_engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision.py": 3,
    "docs/engine_v2_source_paired_clearance_external_reservation.md": 1,
    "operations_decision_ready": 1,
}
EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKENS = tuple(
    EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKEN_COUNTS
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mixed64_v2_authority_is_fail_closed(repo_root: Path) -> bool:
    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise ValueError(f"duplicate JSON key: {key}")
            observed[key] = value
        return observed

    def reject_nonfinite_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    contract_path = (
        repo_root / "config/engine_v2_mixed64_geometric_candidate_evidence_v2.json"
    )
    try:
        text = contract_path.read_bytes().decode("ascii")
        contract = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
    except (OSError, UnicodeError, ValueError):
        return False
    if type(contract) is not dict or set(contract) != {
        "allocation",
        "authority",
        "candidate_evidence",
        "contract_sha256",
        "geometric_admission",
        "schema_id",
        "status",
    }:
        return False
    canonical_text = (
        json.dumps(
            contract,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    )
    if text != canonical_text:
        return False
    authority = contract.get("authority")
    return bool(
        type(authority) is dict
        and set(authority) == set(MIXED64_V2_FORBIDDEN_TRUE_AUTHORITY_KEYS)
        and all(
            type(authority.get(key)) is bool and authority.get(key) is False
            for key in MIXED64_V2_FORBIDDEN_TRUE_AUTHORITY_KEYS
        )
    )


def _cpu_performance_authority_is_fail_closed(repo_root: Path) -> bool:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise ValueError(f"duplicate JSON key: {key}")
            observed[key] = value
        return observed

    def reject_float(value: str) -> object:
        raise ValueError(f"JSON float is forbidden: {value}")

    path = repo_root / "config/engine_v2_cpu_performance_profile.json"
    try:
        raw = path.read_bytes()
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            return False
        document = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (OSError, UnicodeError, ValueError):
        return False
    if type(document) is not dict or document.get("schema_id") != (
        "betelgeuze.engine_v2_cpu_performance_profile/2.0.0"
    ):
        return False
    if _canonical_bytes(document) + b"\n" != raw:
        return False
    authority = document.get("authority")
    restrictions = document.get("restrictions")
    profile_fail_closed = bool(
        type(authority) is dict
        and set(authority) == set(CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS)
        and all(
            authority.get(key) is False for key in CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS
        )
        and type(restrictions) is dict
        and restrictions
        and all(value is False for value in restrictions.values())
    )
    if not profile_fail_closed:
        return False

    terminal_path = (
        repo_root / "config/engine_v2_cpu_performance_v2_terminal_decision.json"
    )
    try:
        terminal_raw = terminal_path.read_bytes()
        if not terminal_raw.endswith(b"\n") or terminal_raw.endswith(b"\n\n"):
            return False
        terminal = json.loads(
            terminal_raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (OSError, UnicodeError, ValueError):
        return False
    if (
        type(terminal) is not dict
        or terminal.get("schema_id")
        != "betelgeuze.engine_v2_cpu_performance_terminal_decision/1.0.0"
        or _canonical_bytes(terminal) + b"\n" != terminal_raw
    ):
        return False
    terminal_authority = terminal.get("authority")
    disposition = terminal.get("disposition")
    terminal_fail_closed = bool(
        type(terminal_authority) is dict
        and set(terminal_authority) == set(CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS)
        and all(
            terminal_authority.get(key) is False
            for key in CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS
        )
        and type(disposition) is dict
        and disposition.get("profile_closed") is True
        and disposition.get("profile_mutation_allowed") is False
        and disposition.get("qualification_consumed") is True
        and disposition.get("rerun_allowed") is False
        and disposition.get("successor_requires_new_profile_id") is True
        and disposition.get("terminal_decision") == "BLOCKED"
    )
    if not terminal_fail_closed:
        return False

    profile_v3_path = repo_root / "config/engine_v2_cpu_performance_profile_v3.json"
    try:
        profile_v3_raw = profile_v3_path.read_bytes()
        if not profile_v3_raw.endswith(b"\n") or profile_v3_raw.endswith(b"\n\n"):
            return False
        profile_v3 = json.loads(
            profile_v3_raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (OSError, UnicodeError, ValueError):
        return False
    expected_v3_bytes = (
        json.dumps(
            profile_v3,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    if (
        type(profile_v3) is not dict
        or profile_v3.get("schema_id")
        != "betelgeuze.engine_v2_cpu_performance_profile/3.0.0"
        or profile_v3_raw != expected_v3_bytes
    ):
        return False
    authority_v3 = profile_v3.get("authority")
    restrictions_v3 = profile_v3.get("restrictions")
    change_control = profile_v3.get("change_control")
    host_preflight = profile_v3.get("host_preflight")
    reader = (
        host_preflight.get("boost_state_reader")
        if type(host_preflight) is dict
        else None
    )
    profile_v3_fail_closed = bool(
        type(authority_v3) is dict
        and set(authority_v3) == set(CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS)
        and all(
            authority_v3.get(key) is False
            for key in CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS
        )
        and type(restrictions_v3) is dict
        and restrictions_v3
        and all(value is False for value in restrictions_v3.values())
        and type(change_control) is dict
        and change_control.get("numeric_contract_changed") is False
        and type(host_preflight) is dict
        and host_preflight.get("consumes_qualification") is False
        and host_preflight.get("launches_measurements") is False
        and host_preflight.get("molecular_inputs_allowed") is False
        and host_preflight.get("persists_result") is False
        and host_preflight.get("reservation_allowed") is False
        and type(reader) is dict
        and reader.get("exact_path") == "/sys/devices/system/cpu/cpufreq/boost"
        and reader.get("reported_size_is_advisory") is True
        and reader.get("maximum_actual_bytes") == 32
        and reader.get("nofollow_required") is True
        and reader.get("group_or_world_writable_allowed") is False
        and reader.get("stable_value_read_count") == 2
    )
    if not profile_v3_fail_closed:
        return False

    activation_path = (
        repo_root / "config/engine_v2_cpu_performance_v3_runner_activation.json"
    )
    try:
        activation_raw = activation_path.read_bytes()
        if not activation_raw.endswith(b"\n") or activation_raw.endswith(b"\n\n"):
            return False
        activation = json.loads(
            activation_raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (OSError, UnicodeError, ValueError):
        return False
    expected_activation_bytes = (
        json.dumps(
            activation,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    if (
        type(activation) is not dict
        or activation.get("schema_id")
        != "betelgeuze.engine_v2_cpu_performance_runner_activation/3.0.0"
        or activation_raw != expected_activation_bytes
        or activation.get("status") != "implementation_admitted_execution_not_attested"
    ):
        return False
    activation_authority = activation.get("authority")
    activation_restrictions = activation.get("restrictions")
    runner = activation.get("runner")
    expected_restrictions = {
        "actual_molecular_execution_allowed",
        "contains_molecular_cases",
        "fresh_or_historical_case_input_allowed",
        "github_actions_production_authority_allowed",
        "public_or_scientific_performance_claim_allowed",
        "reservation_allowed",
        "test_double_production_authority_allowed",
    }
    expected_runner_keys = {
        "attempt_ledger_policy",
        "caller_supplied_probe_allowed",
        "decision_return_policy",
        "exactly_once_profile_attempt",
        "execution_state_recorded_only_by_terminal_decision",
        "github_actions_live_execution_allowed",
        "isolated_live_entrypoint_required",
        "live_synthetic_local_execution_implemented",
        "molecular_execution_allowed",
        "output_policy",
        "reservation_created",
        "result_dependent_configuration_allowed",
        "terminal_state_policy",
        "test_double_execution_authority",
    }
    return bool(
        type(activation_authority) is dict
        and set(activation_authority) == set(CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS)
        and all(
            activation_authority.get(key) is False
            for key in CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS
        )
        and type(activation_restrictions) is dict
        and set(activation_restrictions) == expected_restrictions
        and all(
            activation_restrictions.get(key) is False for key in expected_restrictions
        )
        and type(runner) is dict
        and set(runner) == expected_runner_keys
        and runner.get("attempt_ledger_policy")
        == "fixed_account_scoped_profile_sha_o_excl_before_preflight"
        and runner.get("caller_supplied_probe_allowed") is False
        and runner.get("decision_return_policy")
        == "artifact_and_terminal_persisted_before_return"
        and runner.get("exactly_once_profile_attempt") is True
        and runner.get("execution_state_recorded_only_by_terminal_decision") is True
        and runner.get("github_actions_live_execution_allowed") is False
        and runner.get("isolated_live_entrypoint_required") is True
        and runner.get("live_synthetic_local_execution_implemented") is True
        and runner.get("molecular_execution_allowed") is False
        and runner.get("output_policy")
        == "owner_only_absent_only_single_artifact_plus_terminal"
        and runner.get("reservation_created") is False
        and runner.get("result_dependent_configuration_allowed") is False
        and runner.get("terminal_state_policy")
        == "owner_only_absent_only_attempt_and_artifact_bound"
        and runner.get("test_double_execution_authority") is False
    )


def _native_fixed64_cpu_v5_authority_is_fail_closed(repo_root: Path) -> bool:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise ValueError(f"duplicate JSON key: {key}")
            observed[key] = value
        return observed

    def reject_nonfinite(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    path = repo_root / "config/engine_v2_native_fixed64_cpu_profile_v5.json"
    try:
        raw = path.read_bytes()
        profile = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except (OSError, UnicodeError, ValueError):
        return False
    expected = (
        json.dumps(
            profile,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    if (
        type(profile) is not dict
        or raw != expected
        or profile.get("schema_id")
        != "betelgeuze.engine_v2_native_fixed64_cpu_profile/5.0.0"
        or profile.get("profile_id") != "engine_v2_native_fixed64_cpu_synthetic_v5"
        or profile.get("status")
        != "implementation_profile_frozen_execution_not_consumed"
    ):
        return False
    authority = profile.get("authority")
    restrictions = profile.get("restrictions")
    backends = profile.get("backends")
    fixtures = profile.get("fixtures")
    core = profile.get("measurement_core")
    performance = profile.get("performance")
    fixture_rows = cast(list[dict[str, object]], fixtures)
    return bool(
        type(authority) is dict
        and set(authority) == set(NATIVE_FIXED64_CPU_V5_FALSE_AUTHORITY_KEYS)
        and all(
            authority.get(key) is False
            for key in NATIVE_FIXED64_CPU_V5_FALSE_AUTHORITY_KEYS
        )
        and type(restrictions) is dict
        and set(restrictions) == set(NATIVE_FIXED64_CPU_V5_FALSE_RESTRICTION_KEYS)
        and all(
            restrictions.get(key) is False
            for key in NATIVE_FIXED64_CPU_V5_FALSE_RESTRICTION_KEYS
        )
        and type(backends) is dict
        and backends.get("reference") == "cpp_cpu_reference"
        and backends.get("comparison") == "rust_cpu"
        and backends.get("fallback_allowed") is False
        and type(fixtures) is list
        and all(type(row) is dict for row in fixtures)
        and [
            (
                row.get("candidate_denominator"),
                row.get("receptor_atom_count"),
                row.get("ligand_atom_count"),
                row.get("expected_generated_count"),
                row.get("expected_typed_failure_count"),
            )
            for row in fixture_rows
        ]
        == [(64, 12, 12, 64, 0), (64, 12, 12, 48, 16)]
        and all(row.get("contains_molecular_data") is False for row in fixture_rows)
        and type(core) is dict
        and core.get("python_scientific_work_allowed") is False
        and core.get("receptor_context_recreated_inside_samples") is False
        and type(performance) is dict
        and performance.get("performance_claim_authorized") is False
    )


def _native_fixed64_cpu_v5_binary_is_activation_blocked(repo_root: Path) -> bool:
    probe_path = (
        repo_root / "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v5.rs"
    )
    qualification_path = repo_root / "rust/betelgeuze-runtime/src/qualification.rs"
    try:
        probe = probe_path.read_bytes().decode("ascii")
        qualification = qualification_path.read_bytes().decode("ascii")
    except (OSError, UnicodeError):
        return False
    activation_constant = (
        "pub const FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED: bool = false;"
    )
    activation_function = re.compile(
        r"pub\s+const\s+fn\s+fixed64_cpu_v5_live_activation_admitted\(\)"
        r"\s*->\s*bool\s*"
        r"\{\s*FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED\s*\}"
    )
    activation_guard = "if !fixed64_cpu_v5_live_activation_admitted()"
    unit_test_profile_gate = "if config != Fixed64CpuProbeConfigV5::unit_test()"
    qualification_profile_gate = (
        "&& config != Fixed64CpuProbeConfigV5::qualification_profile()"
    )
    fixture_construction = "let fixture = SyntheticFixture::new();"
    qualification_binding = (
        "let config = Fixed64CpuProbeConfigV5::qualification_profile();"
    )
    qualification_call = "Fixed64CpuProbeConfigV5::qualification_profile()"
    measurement_call = "run_native_fixed64_cpu_probe_v5(config)"
    public_start = qualification.find("pub fn run_native_fixed64_cpu_probe_v5(")
    successor_start = qualification.find(
        "pub(crate) fn run_native_fixed64_cpu_qualification_successor("
    )
    if public_start < 0 or successor_start < public_start:
        return False
    public_body = qualification[public_start:successor_start]
    public_profile_gate = (
        "if config == Fixed64CpuProbeConfigV5::qualification_profile()"
    )
    public_activation_gate = "&& !fixed64_cpu_v5_live_activation_admitted()"
    public_rejection = "fixed64 CPU qualification profile failed closed"
    private_start = qualification.find("fn run_native_fixed64_cpu_probe_with_identity(")
    private_end = public_start
    if private_start < 0 or private_end < private_start:
        return False
    private_body = qualification[private_start:private_end]
    successor_end = qualification.find("\n#[cfg(test)]", successor_start)
    if successor_end < successor_start:
        return False
    successor_body = qualification[successor_start:successor_end]
    return bool(
        qualification.count(activation_constant) == 1
        and "FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED: bool = true" not in qualification
        and len(activation_function.findall(qualification)) == 1
        and private_body.count(unit_test_profile_gate) == 1
        and private_body.count(qualification_profile_gate) == 1
        and qualification.count(fixture_construction) == 1
        and private_body.index(unit_test_profile_gate)
        < private_body.index(qualification_profile_gate)
        < qualification.index(fixture_construction) - private_start
        and public_body.count(public_profile_gate) == 1
        and public_body.count(public_activation_gate) == 1
        and public_body.count(public_rejection) == 1
        and public_body.index(public_profile_gate)
        < public_body.index(public_activation_gate)
        < public_body.index(public_rejection)
        < public_body.rindex("run_native_fixed64_cpu_probe_with_identity(")
        and "pub fn run_native_fixed64_cpu_qualification_successor" not in qualification
        and successor_body.count("Fixed64CpuProbeConfigV5::qualification_profile()")
        == 1
        and successor_body.count("run_native_fixed64_cpu_probe_with_identity(") == 1
        and probe.count("fixed64_cpu_v5_live_activation_admitted") == 2
        and "FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED" not in probe
        and probe.count(activation_guard) == 1
        and probe.count("return ExitCode::from(3);") == 1
        and probe.count(qualification_call) == 1
        and probe.count(qualification_binding) == 1
        and probe.count("Fixed64CpuProbeConfigV5") == 2
        and "Fixed64CpuProbeConfigV5 {" not in probe
        and probe.count(measurement_call) == 1
        and probe.count("run_native_fixed64_cpu_probe_v5") == 2
        and probe.index(activation_guard)
        < probe.index(qualification_binding)
        < probe.index(measurement_call)
    )


def _native_fixed64_cpu_v6_archive_is_fail_closed(repo_root: Path) -> bool:
    profile_path = repo_root / "config/engine_v2_native_fixed64_cpu_profile_v6.json"
    archive_path = (
        repo_root / "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
    )
    source_manifest_path = (
        repo_root / "config/engine_v2_native_fixed64_cpu_profile_v6_sources.json"
    )
    try:
        profile_raw = profile_path.read_bytes()
        archive_raw = archive_path.read_bytes()
        source_manifest_raw = source_manifest_path.read_bytes()
        packaged_profile_raw = (
            repo_root
            / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6.json"
        ).read_bytes()
        packaged_archive_raw = (
            repo_root
            / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
        ).read_bytes()
        packaged_source_manifest_raw = (
            repo_root
            / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json"
        ).read_bytes()
        profile = json.loads(profile_raw.decode("ascii"))
        archive = json.loads(archive_raw.decode("ascii"))
        source_manifest = json.loads(source_manifest_raw.decode("ascii"))
    except (OSError, UnicodeError, ValueError):
        return False

    def canonical_document(value: object) -> bytes:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
            + b"\n"
        )

    authority = archive.get("authority") if type(archive) is dict else None
    profile_authority = profile.get("authority") if type(profile) is dict else None
    profile_restrictions = (
        profile.get("restrictions") if type(profile) is dict else None
    )
    review = archive.get("review") if type(archive) is dict else None
    sources = source_manifest.get("files") if type(source_manifest) is dict else None
    return bool(
        type(profile) is dict
        and type(archive) is dict
        and type(source_manifest) is dict
        and profile_raw == canonical_document(profile)
        and archive_raw == canonical_document(archive)
        and source_manifest_raw == canonical_document(source_manifest)
        and packaged_profile_raw == profile_raw
        and packaged_archive_raw == archive_raw
        and packaged_source_manifest_raw == source_manifest_raw
        and archive.get("schema_id")
        == "betelgeuze.engine_v2_native_fixed64_cpu_profile_archive/1.0.0"
        and archive.get("profile_id") == "engine_v2_native_fixed64_cpu_synthetic_v6"
        and archive.get("status") == "archived_frozen_superseded_by_v7_lane_metrics"
        and archive.get("profile_sha256") == hashlib.sha256(profile_raw).hexdigest()
        and archive.get("transitive_source_manifest_sha256")
        == hashlib.sha256(source_manifest_raw).hexdigest()
        and archive.get("transitive_source_count") == 193
        and source_manifest.get("source_count") == 193
        and type(sources) is list
        and len(sources) == 193
        and archive.get("implementation_main_commit_oid")
        == "12b220e096665ec5664e729d3d60baf577578c56"
        and archive.get("execution_consumed") is False
        and archive.get("reservation_created") is False
        and type(review) is dict
        and review.get("reviewed_head_oid")
        == "0c4d0b911fbc6e75b1e806620d36a282fc24893a"
        and review.get("required_checks_success") == 33
        and review.get("unresolved_review_threads") == 0
        and type(authority) is dict
        and set(authority) == set(NATIVE_FIXED64_CPU_V6_FALSE_AUTHORITY_KEYS)
        and all(value is False for value in authority.values())
        and type(profile_authority) is dict
        and set(profile_authority) == set(NATIVE_FIXED64_CPU_V6_FALSE_AUTHORITY_KEYS)
        and all(value is False for value in profile_authority.values())
        and type(profile_restrictions) is dict
        and set(profile_restrictions)
        == set(NATIVE_FIXED64_CPU_V6_FALSE_RESTRICTION_KEYS)
        and all(value is False for value in profile_restrictions.values())
    )


def _native_fixed64_cpu_v7_execution_receipt_is_consumed(repo_root: Path) -> bool:
    path = (
        repo_root
        / "config/engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.json"
    )
    try:
        projection = require_execution_receipt_bytes(path.read_bytes())
    except (OSError, NativeFixed64CPUV7ExecutionReceiptError):
        return False
    execution = projection.get("execution")
    authority = projection.get("authority")
    claims = projection.get("claims")
    restrictions = projection.get("restrictions")
    return bool(
        projection.get("status") == "recorded_pass_non_authoritative"
        and type(execution) is dict
        and execution.get("execution_consumed") is True
        and execution.get("execution_attested") is False
        and execution.get("recorded_decision") == "PASS"
        and type(authority) is dict
        and authority
        and all(value is False for value in authority.values())
        and type(claims) is dict
        and claims
        and all(value is False for value in claims.values())
        and type(restrictions) is dict
        and restrictions
        and all(value is False for value in restrictions.values())
    )


def _native_fixed64_cpu_v7_authority_is_fail_closed(repo_root: Path) -> bool:
    profile_path = repo_root / "config/engine_v2_native_fixed64_cpu_profile_v7.json"
    release_workflow_path = (
        repo_root / ".github/workflows/ci-engine-v2-release-candidate.yml"
    )
    main_workflow_path = repo_root / ".github/workflows/ci-engine-v2-main.yml"
    native_workflow_path = repo_root / ".github/workflows/ci-native-compute-abi.yml"
    hip_workflow_path = repo_root / ".github/workflows/ci-native-hip-safe-trusted.yml"
    wrapper_lock_path = repo_root / "rust_engine_v2/Cargo.lock"
    try:
        raw = profile_path.read_bytes()
        v6_archive_raw = (
            repo_root / "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
        ).read_bytes()
        source_manifest_raw = (
            repo_root / "config/engine_v2_native_fixed64_cpu_profile_v7_sources.json"
        ).read_bytes()
        cargo_lock_raw = (repo_root / "rust/Cargo.lock").read_bytes()
        packaged_profile_raw = (
            repo_root
            / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7.json"
        ).read_bytes()
        packaged_v6_archive_raw = (
            repo_root
            / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
        ).read_bytes()
        packaged_source_manifest_raw = (
            repo_root
            / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7_sources.json"
        ).read_bytes()
        packaged_cargo_lock_raw = (
            repo_root / "rust/betelgeuze-runtime/assets/workspace-Cargo.lock"
        ).read_bytes()
        packaged_cargo_manifest_raw = (
            repo_root / "rust/betelgeuze-runtime/assets/original-Cargo.toml"
        ).read_bytes()
        cargo_manifest_raw = (
            repo_root / "rust/betelgeuze-runtime/Cargo.toml"
        ).read_bytes()
        build_source = (repo_root / "rust/betelgeuze-runtime/build.rs").read_text(
            encoding="utf-8"
        )
        sys_build_source = (repo_root / "rust/betelgeuze-sys/build.rs").read_text(
            encoding="utf-8"
        )
        rustc_wrapper_source = (
            repo_root / "tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py"
        ).read_text(encoding="utf-8")
        source_manifest = v7_profile_verifier.require_source_manifest_document(
            source_manifest_raw
        )
        historical_sources = v7_profile_verifier.require_bound_source_commit(
            repo_root,
            source_manifest,
            commit_oid=v7_profile_verifier.QUALIFIED_SOURCE_COMMIT_OID,
        )
        cargo_lock_raw = historical_sources["rust/Cargo.lock"]
        cargo_manifest_raw = historical_sources["rust/betelgeuze-runtime/Cargo.toml"]
        qualification_source_raw = historical_sources[
            "rust/betelgeuze-runtime/src/qualification.rs"
        ]
        lane_metrics_source_raw = historical_sources[
            "rust/betelgeuze-runtime/src/fixed64_lane_metrics.rs"
        ]
        runner_source_raw = historical_sources[
            "rust/betelgeuze-runtime/src/qualification_v7.rs"
        ]
        binary_source_raw = historical_sources[
            "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-qualify-v7.rs"
        ]
        post_qualification_boundary_raw = (
            repo_root
            / "config/engine_v2_native_fixed64_cpu_post_qualification_build_boundary_v1.json"
        ).read_bytes()
        v7_profile_verifier.require_post_qualification_build_contract(
            post_qualification_boundary_raw
        )
        v7_profile_verifier.require_post_qualification_build_boundary(repo_root)
        profile = json.loads(raw.decode("ascii"))
        runner = runner_source_raw.decode("utf-8")
        binary = binary_source_raw.decode("utf-8")
        release_workflow = release_workflow_path.read_text(encoding="utf-8")
        main_workflow = main_workflow_path.read_text(encoding="utf-8")
        native_workflow = native_workflow_path.read_text(encoding="utf-8")
        hip_workflow = hip_workflow_path.read_text(encoding="utf-8")
        wrapper_lock = wrapper_lock_path.read_text(encoding="utf-8")
    except (
        OSError,
        UnicodeError,
        ValueError,
        v7_profile_verifier.NativeFixed64CPUProfileV7Error,
    ):
        return False
    expected = (
        json.dumps(
            profile,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    authority = profile.get("authority")
    restrictions = profile.get("restrictions")
    runner_contract = profile.get("runner")
    build_configuration = profile.get("build_configuration")
    source_bindings = profile.get("source_bindings")
    change_control = profile.get("change_control")
    gates = profile.get("gates")
    measurement_core = profile.get("measurement_core")
    if not (
        type(profile) is dict
        and raw == expected
        and packaged_profile_raw == raw
        and packaged_v6_archive_raw == v6_archive_raw
        and packaged_source_manifest_raw == source_manifest_raw
        and packaged_cargo_lock_raw == cargo_lock_raw
        and packaged_cargo_manifest_raw == cargo_manifest_raw
        and profile.get("schema_id")
        == "betelgeuze.engine_v2_native_fixed64_cpu_profile/7.0.0"
        and profile.get("profile_id") == "engine_v2_native_fixed64_cpu_synthetic_v7"
        and profile.get("status")
        == "native_lane_metrics_activation_frozen_execution_not_consumed"
        and type(authority) is dict
        and set(authority) == set(NATIVE_FIXED64_CPU_V7_FALSE_AUTHORITY_KEYS)
        and all(
            authority.get(key) is False
            for key in NATIVE_FIXED64_CPU_V7_FALSE_AUTHORITY_KEYS
        )
        and type(restrictions) is dict
        and set(restrictions) == set(NATIVE_FIXED64_CPU_V7_FALSE_RESTRICTION_KEYS)
        and all(
            restrictions.get(key) is False
            for key in NATIVE_FIXED64_CPU_V7_FALSE_RESTRICTION_KEYS
        )
        and type(runner_contract) is dict
        and type(build_configuration) is dict
        and hashlib.sha256(
            json.dumps(
                build_configuration,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
        ).hexdigest()
        == NATIVE_FIXED64_CPU_V7_BUILD_CONFIGURATION_SHA256
        and runner_contract.get("account_scoped_exactly_once") is True
        and runner_contract.get("attempt_created_before_host_preflight") is True
        and runner_contract.get("artifact_and_terminal_persisted_before_return") is True
        and runner_contract.get("caller_supplied_probe_allowed") is False
        and runner_contract.get("build_commit_bound") is True
        and runner_contract.get("build_source_root_bound") is True
        and runner_contract.get("compiled_activation_profile_verified_at_build") is True
        and runner_contract.get("compiled_transitive_sources_verified_at_build") is True
        and runner_contract.get("effective_rustc_flags_wrapper_verified_at_build")
        is True
        and runner_contract.get("frozen_build_configuration_required") is True
        and runner_contract.get("non_authoritative_package_build_activation_rejected")
        is True
        and runner_contract.get("normal_and_ci_build_activation_rejected") is True
        and runner_contract.get("output_path_utf8_required") is True
        and runner_contract.get("post_measurement_host_revalidation_required") is True
        and runner_contract.get("qualification_build_opt_in_required") is True
        and runner_contract.get("test_only_profile_execution_allowed") is False
        and type(change_control) is dict
        and change_control.get("candidate_graph_changed") is False
        and change_control.get("evidence_contract_changed") is True
        and change_control.get("fixture_payloads_changed") is False
        and change_control.get("metric_contract_changed") is True
        and change_control.get("numeric_contract_changed") is False
        and change_control.get("predecessor_execution_consumed") is False
        and change_control.get("predecessor_main_commit_oid")
        == "12b220e096665ec5664e729d3d60baf577578c56"
        and change_control.get("predecessor_profile_id")
        == "engine_v2_native_fixed64_cpu_synthetic_v6"
        and change_control.get("predecessor_profile_sha256")
        == "fd83f1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928"
        and type(gates) is dict
        and gates.get("candidate_denominator_exact") == 64
        and gates.get("lane_metrics_candidate_denominator_exact") == 64
        and gates.get("lane_metrics_observation_count_exact") == 64
        and gates.get("lane_metrics_lane_count_exact") == 10
        and gates.get("oracle_rmsd_definition")
        == "symmetry_aware_direct_heavy_atom_no_alignment"
        and gates.get("oracle_rmsd_threshold_angstrom_exact") == 2
        and gates.get("symmetry_permutation_limit_exact") == 1024
        and gates.get("lane_metrics_authority_false_required") is True
        and gates.get("lane_metrics_rank_mutation_forbidden") is True
        and gates.get("lane_metrics_result_dependent_allocation_forbidden") is True
        and gates.get("lane_metrics_receipt_rederivable_required") is True
        and gates.get("lane_metrics_full_receipts_recorded_required") is True
        and gates.get(
            "lane_metrics_decision_sha256_exact_between_cpu_backends_required"
        )
        is True
        and gates.get("typed_failures_preserved_in_lane_metrics_required") is True
        and type(measurement_core) is dict
        and measurement_core.get("lane_metrics_downstream_only") is True
        and measurement_core.get("lane_metrics_reference_materialized") is True
        and measurement_core.get("lane_metrics_reference_receipt_and_topology_bound")
        is True
        and measurement_core.get(
            "lane_metrics_symmetry_permutations_canonical_unique_identity_required"
        )
        is True
        and measurement_core.get("lane_metrics_symmetry_mapping")
        == "reference_position_to_candidate_position"
        and measurement_core.get("python_scientific_work_allowed") is False
        and measurement_core.get("conformer_orientation_pairs")
        == [
            "24:36",
            "25:37",
            "26:38",
            "27:39",
            "28:40",
            "29:41",
            "30:42",
            "31:43",
        ]
        and type(source_bindings) is dict
        and set(source_bindings)
        == {
            "cargo_lock_sha256",
            "cargo_manifest_sha256",
            "lane_metrics_source_sha256",
            "native_binary_source_sha256",
            "native_qualification_source_sha256",
            "native_runner_source_sha256",
            "predecessor_archive_sha256",
            "transitive_source_manifest_sha256",
        }
        and all(
            type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in source_bindings.values()
        )
        and source_bindings.get("cargo_lock_sha256")
        == hashlib.sha256(cargo_lock_raw).hexdigest()
        and source_bindings.get("cargo_manifest_sha256")
        == hashlib.sha256(cargo_manifest_raw).hexdigest()
        and source_bindings.get("lane_metrics_source_sha256")
        == hashlib.sha256(lane_metrics_source_raw).hexdigest()
        and source_bindings.get("native_binary_source_sha256")
        == hashlib.sha256(binary_source_raw).hexdigest()
        and source_bindings.get("native_qualification_source_sha256")
        == hashlib.sha256(qualification_source_raw).hexdigest()
        and source_bindings.get("native_runner_source_sha256")
        == hashlib.sha256(runner_source_raw).hexdigest()
        and source_bindings.get("predecessor_archive_sha256")
        == hashlib.sha256(v6_archive_raw).hexdigest()
        and source_bindings.get("transitive_source_manifest_sha256")
        == hashlib.sha256(source_manifest_raw).hexdigest()
        and build_configuration.get("cargo_profile") == "qualification-v7"
        and build_configuration.get("qualification_build_opt_in")
        == "BETELGEUZE_V7_QUALIFICATION_BUILD=1"
        and build_configuration.get("rustc_wrapper_cfg")
        == "betelgeuze_v7_effective_rust_flags_verified"
        and all(
            release_workflow.count(path) == 4
            for path in NATIVE_FIXED64_CPU_V7_COMPILE_BOUND_CONFIG_PATHS
        )
        and all(
            hip_workflow.count(path) == 1
            for path in NATIVE_FIXED64_CPU_V7_COMPILE_BOUND_CONFIG_PATHS
        )
        and release_workflow.count("-e BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1")
        == 1
        and all(
            workflow.count(
                "git fetch --no-tags --depth=1 origin 5c1e4791e988d4c75a5111f933feac85236ba821"
            )
            == 1
            and workflow.count(
                "git rev-parse --verify '5c1e4791e988d4c75a5111f933feac85236ba821^{commit}'"
            )
            == 1
            for workflow in (main_workflow, native_workflow)
        )
        and "native fixed64 CPU v7 non-authoritative build cannot activate"
        in release_workflow
        and re.search(
            r'\[\[package\]\]\nname = "betelgeuze-runtime"\n'
            r'version = "0\.1\.0"\ndependencies = \[\n'
            r'(?: "[^"]+",\n)* "libc",\n',
            wrapper_lock,
        )
        is not None
    ):
        return False
    start = runner.find("pub fn run_native_fixed64_cpu_qualification_v7(")
    end = runner.find("\n#[cfg(test)]", start)
    if start < 0 or end < 0:
        return False
    body = runner[start:end]
    ordered = (
        "deny_github_actions_live_execution()?;",
        "verify_native_fixed64_cpu_v7_activation()?;",
        "validate_absent_output(output_path)?;",
        "open_account_state(&activation.profile_sha256)?;",
        "create_attempt(",
        "preflight_native_fixed64_cpu_v7()?;",
        "execute_measurement(&preflight);",
        "build_artifact(",
    )
    cursor = -1
    for token in ordered:
        position = body.find(token, cursor + 1)
        if position < 0:
            return False
        cursor = position
    artifact_publish = body.find("publish_absent_file_at(", cursor + 1)
    terminal_build = body.find("build_terminal(", artifact_publish + 1)
    terminal_publish = body.find("publish_absent_file_at(", terminal_build + 1)
    returned = body.rfind("Ok(Fixed64CpuPersistedQualificationV7")
    return bool(
        cursor < artifact_publish < terminal_build < terminal_publish < returned
        and "libc::O_EXCL" in runner
        and "libc::O_NOFOLLOW" in runner
        and "output filename cannot support atomic staging" in runner
        and "../assets/engine_v2_native_fixed64_cpu_profile_v7.json" in runner
        and "../assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json" in runner
        and "../assets/engine_v2_native_fixed64_cpu_profile_v7_sources.json" in runner
        and "../assets/workspace-Cargo.lock" in runner
        and "../assets/original-Cargo.toml" in runner
        and "bind_compiled_source_graph(&source_root)" in build_source
        and "BETELGEUZE_V7_SOURCE_ROOT" in build_source
        and "cargo:rustc-env={COMPILED_MANIFEST_ENV}" in build_source
        and "cargo:rustc-env={COMPILED_PROFILE_ENV}" in build_source
        and "cargo:rustc-env={BUILD_COMMIT_ENV}" in build_source
        and "cargo:rustc-env={BUILD_COMMIT_BOUND_ENV}" in build_source
        and "cargo:rustc-env={VERIFIED_SOURCE_ROOT_ENV}" in build_source
        and "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD" in build_source
        and NATIVE_FIXED64_CPU_V7_QUALIFICATION_BUILD_ENV in build_source
        and "BUILD_CONFIGURATION_SHA256_ENV" in build_source
        and "BUILD_CONFIGURATION_BOUND_ENV" in build_source
        and "EXPECTED_BUILD_CONFIGURATION_SHA256" in build_source
        and "EXPECTED_RUSTC_SHA256" in build_source
        and "EXPECTED_CARGO_SHA256" in build_source
        and "EXPECTED_CPP_SHA256" in build_source
        and "EXPECTED_RUSTC_WRAPPER_SHA256" in build_source
        and "EXPECTED_RUSTC_WRAPPER_INTERPRETER_SHA256" in build_source
        and "qualification_rustc_wrapper_is_exact" in build_source
        and "betelgeuze_v7_effective_rust_flags_verified" in build_source
        and 'const QUALIFICATION_CPP_COMPILER: &str = "/usr/bin/x86_64-linux-gnu-g++-11";'
        in sys_build_source
        and "const QUALIFICATION_CPP_FLAGS: &[&str]" in sys_build_source
        and ".no_default_flags(true)" in sys_build_source
        and '"-ffp-contract=off"' in sys_build_source
        and '"-fno-fast-math"' in sys_build_source
        and "QUALIFICATION_RUSTC_WRAPPER_RELATIVE_PATH" in sys_build_source
        and 'std::env::var_os("RUSTC_WRAPPER")' in sys_build_source
        and "CONTROLLED_LIBRARY_CRATES" in rustc_wrapper_source
        and "CONTROLLED_CFG_VALUES" in rustc_wrapper_source
        and "ALLOWED_QUERY_ARGUMENTS" in rustc_wrapper_source
        and '"opt-level": "3"' in rustc_wrapper_source
        and 'expected["lto"] = "fat"' in rustc_wrapper_source
        and 'arguments.extend(["-C", "linker-plugin-lto"])' in rustc_wrapper_source
        and "effective -C option names differ from the frozen profile"
        in rustc_wrapper_source
        and "cfg values differ from the frozen profile" in rustc_wrapper_source
        and "unstable rustc options are forbidden" in rustc_wrapper_source
        and "os.execv(rustc" in rustc_wrapper_source
        and "UNBOUND_BUILD_COMMIT_OID" in build_source
        and "committed_blob(source_root, commit_oid, PROFILE_RELATIVE_PATH)"
        in build_source
        and "track_git_commit_inputs(source_root)" in build_source
        and 'git_path(source_root, "HEAD")' in build_source
        and 'git_path(source_root, "packed-refs")' in build_source
        and 'emit_rerun_if_changed(&reference_path, "symbolic HEAD reference")'
        in build_source
        and 'BUILD_COMMIT_BOUND != "true"' in runner
        and 'BUILD_CONFIGURATION_BOUND != "true"' in runner
        and "build configuration is not frozen" in runner
        and "v7 qualification effective rustc flags were not wrapper-verified" in runner
        and "non-authoritative package build cannot activate" in runner
        and "decision_returned_only_after_terminal_persistence" in runner
        and runner.count("run_native_fixed64_cpu_qualification_successor(") == 1
        and "Fixed64LaneMetricsReference" in qualification_source_raw.decode("utf-8")
        and qualification_source_raw.decode("utf-8").count(
            "Fixed64LaneMetricsReceipt::build("
        )
        == 2
        and qualification_source_raw.decode("utf-8").count(".verify_against(") >= 2
        and "lane_metrics_decision_parity" in qualification_source_raw.decode("utf-8")
        and "lane_metrics_rederivable" in qualification_source_raw.decode("utf-8")
        and "lane_metrics_authority_false" in qualification_source_raw.decode("utf-8")
        and "FIXED64_ORACLE_RMSD_THRESHOLD_ANGSTROM: f64 = 2.0"
        in lane_metrics_source_raw.decode("utf-8")
        and "FIXED64_MAX_SYMMETRY_PERMUTATIONS: usize = 1024"
        in lane_metrics_source_raw.decode("utf-8")
        and "pub result_dependent_allocation_consumed: bool"
        in lane_metrics_source_raw.decode("utf-8")
        and "pub fn verify_against(" in lane_metrics_source_raw.decode("utf-8")
        and "lane_metrics_decision_sha256" in lane_metrics_source_raw.decode("utf-8")
        and "--verify-activation" in binary
        and "--preflight" in binary
        and "--run-output" in binary
        and "Fixed64CpuProbeConfigV5" not in binary
        and "run_native_fixed64_cpu_probe_v5" not in binary
    )


def build_inventory(repo_root: Path) -> dict[str, Any]:
    workflow_root = repo_root / ".github/workflows"
    all_action_workflows = tuple(
        sorted(
            path.relative_to(repo_root).as_posix()
            for path in workflow_root.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )
    )
    workflows = tuple(
        sorted(
            path.relative_to(repo_root).as_posix()
            for path in workflow_root.glob("ci-engine-v2-*.yml")
            if path.is_file()
        )
    )
    authoritative = tuple(path for path in AUTHORITATIVE_WORKFLOWS if path in workflows)
    specialized = tuple(
        path for path in workflows if path not in AUTHORITATIVE_WORKFLOWS
    )
    hashes = {path: _sha256(repo_root / path) for path in workflows}
    main_text = (repo_root / AUTHORITATIVE_WORKFLOWS[0]).read_text(encoding="utf-8")
    all_workflow_text = "\n".join(
        (repo_root / path).read_text(encoding="utf-8") for path in all_action_workflows
    )
    stage0_required_tokens = (
        "tools/__init__.py",
        "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
        "config/engine_v2_phase25_cohort_admission.json",
        "tests/unit/test_analyze_engine_v2_score_terms.py",
        "tests/unit/test_engine_v2_blind_stage0.py",
        "tests/unit/test_build_engine_v2_stage0_development_gate_ledger.py",
        "tests/unit/test_verify_engine_v2_phase25_cohort_admission.py",
        "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
        "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
        "tools/verify_engine_v2_public_redocking_stage0.py",
        "tools/verify_engine_v2_phase25_cohort_admission.py",
        "tools/build_engine_v2_stage0_development_gate_ledger.py",
        "tools/classify_engine_v2_stage0_full_suite.py",
        "tools/reconcile_engine_v2_stage0_full_suites.py",
    )
    clearance_activation_contract_present = any(
        (repo_root / path).is_file() for path in CLEARANCE_ACTIVATION_CONTRACT_PATHS
    )
    if clearance_activation_contract_present:
        stage0_required_tokens += CLEARANCE_ACTIVATION_REQUIRED_TOKENS

    global_orientation_contract_present = any(
        (repo_root / path).is_file() for path in GLOBAL_ORIENTATION_CONTRACT_PATHS
    )
    global_orientation_contract_in_authoritative_ci = (
        not global_orientation_contract_present
        or all(token in main_text for token in GLOBAL_ORIENTATION_REQUIRED_TOKENS)
    )

    mixed64_v2_contract_present = any(
        (repo_root / path).is_file() for path in MIXED64_V2_CONTRACT_PATHS
    )
    mixed64_v2_contract_files_complete = all(
        (repo_root / path).is_file() for path in MIXED64_V2_CONTRACT_PATHS
    )
    mixed64_v2_authority_fail_closed = not mixed64_v2_contract_present or (
        mixed64_v2_contract_files_complete
        and _mixed64_v2_authority_is_fail_closed(repo_root)
    )
    mixed64_v2_contract_in_authoritative_ci = not mixed64_v2_contract_present or (
        mixed64_v2_contract_files_complete
        and mixed64_v2_authority_fail_closed
        and all(
            main_text.count(token) >= minimum_count
            for token, minimum_count in MIXED64_V2_REQUIRED_TOKEN_COUNTS.items()
        )
    )

    cpu_performance_contract_present = any(
        (repo_root / path).is_file() for path in CPU_PERFORMANCE_CONTRACT_PATHS
    )
    cpu_performance_contract_files_complete = all(
        (repo_root / path).is_file() for path in CPU_PERFORMANCE_CONTRACT_PATHS
    )
    cpu_performance_authority_fail_closed = not cpu_performance_contract_present or (
        cpu_performance_contract_files_complete
        and _cpu_performance_authority_is_fail_closed(repo_root)
    )
    cpu_performance_contract_in_authoritative_ci = (
        not cpu_performance_contract_present
        or (
            cpu_performance_contract_files_complete
            and cpu_performance_authority_fail_closed
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in (
                    CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS.items()
                )
            )
        )
    )

    native_fixed64_cpu_v5_contract_present = any(
        (repo_root / path).is_file() for path in NATIVE_FIXED64_CPU_V5_CONTRACT_PATHS
    )
    native_fixed64_cpu_v5_contract_files_complete = all(
        (repo_root / path).is_file() for path in NATIVE_FIXED64_CPU_V5_CONTRACT_PATHS
    )
    native_fixed64_cpu_v5_binary_activation_blocked = (
        _native_fixed64_cpu_v5_binary_is_activation_blocked(repo_root)
    )
    native_fixed64_cpu_v5_profile_authority_false = (
        not native_fixed64_cpu_v5_contract_present
        or (
            native_fixed64_cpu_v5_contract_files_complete
            and _native_fixed64_cpu_v5_authority_is_fail_closed(repo_root)
        )
    )
    native_fixed64_cpu_v5_qualification_admission_authority_false = (
        not native_fixed64_cpu_v5_contract_present
        or (
            native_fixed64_cpu_v5_profile_authority_false
            and native_fixed64_cpu_v5_binary_activation_blocked
        )
    )
    native_fixed64_cpu_v5_authority_fail_closed = (
        native_fixed64_cpu_v5_qualification_admission_authority_false
    )
    native_fixed64_cpu_v5_contract_in_authoritative_ci = (
        not native_fixed64_cpu_v5_contract_present
        or (
            native_fixed64_cpu_v5_contract_files_complete
            and native_fixed64_cpu_v5_authority_fail_closed
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in (
                    NATIVE_FIXED64_CPU_V5_REQUIRED_TOKEN_COUNTS.items()
                )
            )
        )
    )

    native_fixed64_cpu_v6_contract_present = any(
        (repo_root / path).is_file() for path in NATIVE_FIXED64_CPU_V6_CONTRACT_PATHS
    )
    native_fixed64_cpu_v6_contract_files_complete = all(
        (repo_root / path).is_file() for path in NATIVE_FIXED64_CPU_V6_CONTRACT_PATHS
    )
    native_fixed64_cpu_v6_profile_authority_false = (
        not native_fixed64_cpu_v6_contract_present
        or (
            native_fixed64_cpu_v6_contract_files_complete
            and _native_fixed64_cpu_v6_archive_is_fail_closed(repo_root)
        )
    )
    native_fixed64_cpu_v6_live_qualification_absent_from_github_actions = (
        "--run-output" not in all_workflow_text
        and "run_native_fixed64_cpu_qualification_v6" not in all_workflow_text
        and NATIVE_FIXED64_CPU_V6_QUALIFICATION_BUILD_ENV not in all_workflow_text
    )
    native_fixed64_cpu_v6_authority_fail_closed = (
        native_fixed64_cpu_v6_profile_authority_false
        and native_fixed64_cpu_v6_live_qualification_absent_from_github_actions
    )
    native_fixed64_cpu_v6_contract_in_authoritative_ci = (
        not native_fixed64_cpu_v6_contract_present
        or (
            native_fixed64_cpu_v6_contract_files_complete
            and native_fixed64_cpu_v6_authority_fail_closed
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in (
                    NATIVE_FIXED64_CPU_V6_REQUIRED_TOKEN_COUNTS.items()
                )
            )
        )
    )

    native_fixed64_cpu_v7_contract_present = any(
        (repo_root / path).is_file() for path in NATIVE_FIXED64_CPU_V7_CONTRACT_PATHS
    )
    native_fixed64_cpu_v7_contract_files_complete = all(
        (repo_root / path).is_file() for path in NATIVE_FIXED64_CPU_V7_CONTRACT_PATHS
    )
    native_fixed64_cpu_v7_profile_authority_false = (
        not native_fixed64_cpu_v7_contract_present
        or (
            native_fixed64_cpu_v7_contract_files_complete
            and _native_fixed64_cpu_v7_authority_is_fail_closed(repo_root)
        )
    )
    native_fixed64_cpu_v7_execution_consumed = bool(
        native_fixed64_cpu_v7_contract_files_complete
        and _native_fixed64_cpu_v7_execution_receipt_is_consumed(repo_root)
    )
    native_fixed64_cpu_v7_live_qualification_absent_from_github_actions = (
        "--run-output" not in all_workflow_text
        and "run_native_fixed64_cpu_qualification_v7" not in all_workflow_text
        and NATIVE_FIXED64_CPU_V7_QUALIFICATION_BUILD_ENV not in all_workflow_text
    )
    native_fixed64_cpu_v7_authority_fail_closed = (
        native_fixed64_cpu_v7_profile_authority_false
        and native_fixed64_cpu_v7_live_qualification_absent_from_github_actions
        and (
            not native_fixed64_cpu_v7_contract_present
            or native_fixed64_cpu_v7_execution_consumed
        )
    )
    native_fixed64_cpu_v7_contract_in_authoritative_ci = (
        not native_fixed64_cpu_v7_contract_present
        or (
            native_fixed64_cpu_v7_contract_files_complete
            and native_fixed64_cpu_v7_authority_fail_closed
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in (
                    NATIVE_FIXED64_CPU_V7_REQUIRED_TOKEN_COUNTS.items()
                )
            )
        )
    )

    one_shot_contract_present = any(
        (repo_root / path).is_file() for path in ONE_SHOT_CONTRACT_PATHS
    )
    external_reservation_contract_present = any(
        (repo_root / path).is_file() for path in EXTERNAL_RESERVATION_CONTRACT_PATHS
    )
    external_operations_decision_contract_present = any(
        (repo_root / path).is_file()
        for path in EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS
    )
    external_operations_decision_contract_files_complete = all(
        (repo_root / path).is_file()
        for path in EXTERNAL_RESERVATION_OPERATIONS_DECISION_CONTRACT_PATHS
    )
    required_one_shot_tokens = ONE_SHOT_REQUIRED_TOKENS
    if external_reservation_contract_present:
        required_one_shot_tokens += EXTERNAL_RESERVATION_REQUIRED_TOKENS

    one_shot_contract_in_authoritative_ci = not one_shot_contract_present or all(
        token in main_text for token in required_one_shot_tokens
    )
    external_reservation_contract_in_authoritative_ci = (
        not external_reservation_contract_present
        or all(token in main_text for token in EXTERNAL_RESERVATION_REQUIRED_TOKENS)
    )
    standalone_pipeline_contract_present = any(
        (repo_root / path).is_file() for path in STANDALONE_PIPELINE_CONTRACT_PATHS
    )
    standalone_pipeline_contract_in_authoritative_ci = (
        not standalone_pipeline_contract_present
        or all(
            main_text.count(token) >= 2 for token in STANDALONE_PIPELINE_REQUIRED_TOKENS
        )
    )
    standalone_consumer_contract_present = any(
        (repo_root / path).is_file() for path in STANDALONE_CONSUMER_CONTRACT_PATHS
    )
    standalone_consumer_contract_in_authoritative_ci = (
        not standalone_consumer_contract_present
        or all(
            main_text.count(token) == 2 for token in STANDALONE_CONSUMER_REQUIRED_TOKENS
        )
    )
    standalone_contract_present = any(
        (repo_root / path).is_file() for path in STANDALONE_CONTRACT_PATHS
    )
    standalone_contract_in_authoritative_ci = not standalone_contract_present or all(
        token in main_text for token in STANDALONE_REQUIRED_TOKENS
    )
    external_operations_decision_contract_in_authoritative_ci = (
        not external_operations_decision_contract_present
        or (
            external_operations_decision_contract_files_complete
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in (
                    EXTERNAL_RESERVATION_OPERATIONS_DECISION_REQUIRED_TOKEN_COUNTS.items()
                )
            )
        )
    )

    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "workflow_count": len(workflows),
        "authoritative_workflows": list(authoritative),
        "specialized_workflows": list(specialized),
        "workflow_sha256s": hashes,
        "workflow_inventory_sha256": hashlib.sha256(
            _canonical_bytes(hashes)
        ).hexdigest(),
        "stage0_tests_in_authoritative_main": all(
            token in main_text for token in stage0_required_tokens
        ),
        "global_orientation_contract_in_authoritative_ci": (
            global_orientation_contract_in_authoritative_ci
        ),
        "mixed64_v2_contract_in_authoritative_ci": (
            mixed64_v2_contract_in_authoritative_ci
        ),
        "mixed64_v2_authority_fail_closed": mixed64_v2_authority_fail_closed,
        "cpu_performance_contract_in_authoritative_ci": (
            cpu_performance_contract_in_authoritative_ci
        ),
        "cpu_performance_authority_fail_closed": (
            cpu_performance_authority_fail_closed
        ),
        "native_fixed64_cpu_v5_contract_in_authoritative_ci": (
            native_fixed64_cpu_v5_contract_in_authoritative_ci
        ),
        "native_fixed64_cpu_v5_authority_fail_closed": (
            native_fixed64_cpu_v5_authority_fail_closed
        ),
        "native_fixed64_cpu_v5_binary_activation_blocked": (
            native_fixed64_cpu_v5_binary_activation_blocked
        ),
        "native_fixed64_cpu_v5_github_actions_production_authority_false": (
            native_fixed64_cpu_v5_profile_authority_false
        ),
        "native_fixed64_cpu_v5_qualification_admission_authority_false": (
            native_fixed64_cpu_v5_qualification_admission_authority_false
        ),
        "native_fixed64_cpu_v5_test_double_production_authority_false": (
            native_fixed64_cpu_v5_profile_authority_false
        ),
        "native_fixed64_cpu_v6_contract_in_authoritative_ci": (
            native_fixed64_cpu_v6_contract_in_authoritative_ci
        ),
        "native_fixed64_cpu_v6_authority_fail_closed": (
            native_fixed64_cpu_v6_authority_fail_closed
        ),
        "native_fixed64_cpu_v6_archived": (
            native_fixed64_cpu_v6_profile_authority_false
        ),
        "native_fixed64_cpu_v6_execution_consumed": False,
        "native_fixed64_cpu_v6_github_actions_production_authority_false": (
            native_fixed64_cpu_v6_profile_authority_false
        ),
        "native_fixed64_cpu_v6_live_qualification_absent_from_github_actions": (
            native_fixed64_cpu_v6_live_qualification_absent_from_github_actions
        ),
        "native_fixed64_cpu_v6_qualification_authority_false": (
            native_fixed64_cpu_v6_profile_authority_false
        ),
        "native_fixed64_cpu_v6_test_double_production_authority_false": (
            native_fixed64_cpu_v6_profile_authority_false
        ),
        "native_fixed64_cpu_v7_contract_in_authoritative_ci": (
            native_fixed64_cpu_v7_contract_in_authoritative_ci
        ),
        "native_fixed64_cpu_v7_authority_fail_closed": (
            native_fixed64_cpu_v7_authority_fail_closed
        ),
        "native_fixed64_cpu_v7_execution_consumed": (
            native_fixed64_cpu_v7_execution_consumed
        ),
        "native_fixed64_cpu_v7_execution_receipt_verified": (
            native_fixed64_cpu_v7_execution_consumed
        ),
        "native_fixed64_cpu_v7_github_actions_production_authority_false": (
            native_fixed64_cpu_v7_profile_authority_false
        ),
        "native_fixed64_cpu_v7_live_qualification_absent_from_github_actions": (
            native_fixed64_cpu_v7_live_qualification_absent_from_github_actions
        ),
        "native_fixed64_cpu_v7_qualification_authority_false": (
            native_fixed64_cpu_v7_profile_authority_false
        ),
        "native_fixed64_cpu_v7_test_double_production_authority_false": (
            native_fixed64_cpu_v7_profile_authority_false
        ),
        "one_shot_contract_in_authoritative_ci": (
            one_shot_contract_in_authoritative_ci
        ),
        "external_reservation_contract_in_authoritative_ci": (
            external_reservation_contract_in_authoritative_ci
        ),
        "standalone_pipeline_contract_in_authoritative_ci": (
            standalone_pipeline_contract_in_authoritative_ci
        ),
        "standalone_consumer_contract_in_authoritative_ci": (
            standalone_consumer_contract_in_authoritative_ci
        ),
        "standalone_contract_in_authoritative_ci": (
            standalone_contract_in_authoritative_ci
        ),
        "external_operations_decision_contract_in_authoritative_ci": (
            external_operations_decision_contract_in_authoritative_ci
        ),
        "new_feature_workflow_policy": "consolidate_into_authoritative_workflows",
        "specialized_workflows_hidden": False,
        "issue_199_external_state_mutated": False,
    }
    payload["receipt_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    payload = build_inventory(arguments.repo_root.resolve())
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(payload["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
