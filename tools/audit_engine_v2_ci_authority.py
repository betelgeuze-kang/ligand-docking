#!/usr/bin/env python3
"""Build a deterministic inventory of Engine V2 CI authority surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
from typing import Any

import yaml


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
NATIVE_FIXED64_CPU_V4_CONTRACT_PATHS = (
    "config/engine_v2_native_fixed64_cpu_profile_v4.json",
    "rust/betelgeuze-runtime/src/docking.rs",
    "rust/betelgeuze-runtime/src/lib.rs",
    "rust/betelgeuze-runtime/src/qualification.rs",
    "native/src/docking/fixed64_pipeline.cpp",
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs",
    "rust/betelgeuze-runtime/tests/docking_fixed64_pipeline.rs",
    "rust/betelgeuze-runtime/tests/fixed64_cpu_probe_activation.rs",
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py",
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v4.py",
    "docs/engine_v2_native_fixed64_cpu_qualification_v4.md",
)
NATIVE_FIXED64_CPU_V4_REQUIRED_TOKEN_COUNTS = {
    "**/action.yml": 2,
    "**/action.yaml": 2,
    ".github/workflows/*.yml": 2,
    ".github/workflows/*.yaml": 2,
    "sparse-checkout-cone-mode: false": 1,
    "config/engine_v2_native_fixed64_cpu_profile_v4.json": 2,
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py": 4,
    "tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v4.py": 2,
    "docs/engine_v2_native_fixed64_cpu_qualification_v4.md": 1,
}
NATIVE_FIXED64_CPU_V4_REQUIRED_TOKENS = tuple(
    NATIVE_FIXED64_CPU_V4_REQUIRED_TOKEN_COUNTS
)
NATIVE_FIXED64_CPU_V4_FALSE_AUTHORITY_KEYS = (
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
NATIVE_FIXED64_CPU_V4_FALSE_RESTRICTION_KEYS = (
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
NATIVE_FIXED64_CPU_V4_FORBIDDEN_WORKFLOW_TOKENS = (
    "betelgeuze-fixed64-cpu-probe-v4",
)
NATIVE_FIXED64_CPU_V4_CARGO_RUN_PATTERN = (
    r"\bcargo\b[^\n]*?\b(?:run|r)\b[^\n]*"
)
NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS = ("run", "r")
NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITH_VALUE = (
    "--color",
    "--config",
    "-C",
    "-Z",
)
NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITHOUT_VALUE = (
    "--frozen",
    "--locked",
    "--offline",
    "--quiet",
    "--verbose",
    "-q",
    "-v",
)
NATIVE_FIXED64_CPU_V4_CARGO_TERMINAL_OPTIONS_WITH_VALUE = ("--explain",)
NATIVE_FIXED64_CPU_V4_CARGO_TERMINAL_OPTIONS_WITHOUT_VALUE = (
    "--help",
    "--list",
    "--version",
    "-V",
    "-h",
)
NATIVE_FIXED64_CPU_V4_CARGO_TARGET_SELECTORS = ("--bin", "--example")
NATIVE_FIXED64_CPU_V4_STATIC_TARGET_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
)
NATIVE_FIXED64_CPU_V4_SHELL_EXPANSION_MARKERS = (
    "$",
    "`",
    "*",
    "?",
    "[",
    "]",
    "{",
    "}",
)
NATIVE_FIXED64_CPU_V4_FOLDED_RUN_PATTERN = re.compile(
    r"^(?P<indent>[ ]*)(?:-[ ]+)?run:[ ]*>[+-]?[1-9]?[+-]?[ ]*(?:#.*)?$"
)
NATIVE_FIXED64_CPU_V4_MAX_WORKFLOW_UTF8_BYTES = 1_048_576
NATIVE_FIXED64_CPU_V4_MAX_YAML_NODES = 100_000
NATIVE_FIXED64_CPU_V4_MAX_LOCAL_ACTION_FILES = 1_000
NATIVE_FIXED64_CPU_V4_MAX_LOCAL_ACTION_UTF8_BYTES = 8_388_608
_INVALID_SHELL = object()
_AMBIGUOUS_COMMAND_INDEX = -1
_UNSUPPORTED_DEFAULT_SHELL = "__betelgeuze_unsupported_default_shell__"
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
STANDALONE_CONSUMER_CONTRACT_PATHS = (
    "betelgeuze_engine_v2/docking/consumers.py",
)
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


def _workflow_yaml_run_steps(
    text: str,
) -> tuple[tuple[str, str | None], ...] | None:
    if len(text.encode("utf-8")) > NATIVE_FIXED64_CPU_V4_MAX_WORKFLOW_UTF8_BYTES:
        return None
    try:
        document = yaml.safe_load(text)
    except (yaml.YAMLError, RecursionError):
        return None
    stack = [document]
    visited: set[int] = set()
    observed_run_scalars = 0
    observed_nodes = 0
    while stack:
        value = stack.pop()
        if isinstance(value, (dict, list)):
            identity = id(value)
            if identity in visited:
                continue
            visited.add(identity)
        observed_nodes += 1
        if observed_nodes > NATIVE_FIXED64_CPU_V4_MAX_YAML_NODES:
            return None
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "run" and isinstance(child, str):
                    observed_run_scalars += 1
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)

    if document is None:
        return ()
    if not isinstance(document, dict):
        return None

    def default_shell(
        container: dict[object, object],
        inherited: str | None,
    ) -> str | None | object:
        defaults = container.get("defaults")
        if defaults is None:
            return inherited
        if not isinstance(defaults, dict):
            return _INVALID_SHELL
        run_defaults = defaults.get("run")
        if run_defaults is None:
            return inherited
        if not isinstance(run_defaults, dict):
            return _INVALID_SHELL
        shell = run_defaults.get("shell")
        if shell is None:
            return inherited
        return shell if isinstance(shell, str) else _INVALID_SHELL

    def append_steps(
        value: object,
        inherited_shell: str | None,
        destination: list[tuple[str, str | None]],
    ) -> bool:
        if value is None:
            return True
        if not isinstance(value, list):
            return False
        for step in value:
            if not isinstance(step, dict):
                return False
            run = step.get("run")
            if run is None:
                continue
            if not isinstance(run, str):
                return False
            shell = step.get("shell", inherited_shell)
            if shell is not None and not isinstance(shell, str):
                return False
            destination.append((run, shell))
        return True

    def runner_default_shell(job: dict[object, object]) -> str | None:
        runs_on = job.get("runs-on")
        if runs_on is None:
            return None
        labels: tuple[str, ...]
        if isinstance(runs_on, str):
            labels = (runs_on.lower(),)
        elif isinstance(runs_on, list) and all(
            isinstance(label, str) for label in runs_on
        ):
            labels = tuple(str(label).lower() for label in runs_on)
        else:
            return _UNSUPPORTED_DEFAULT_SHELL
        if any("${{" in label or "windows" in label for label in labels):
            return _UNSUPPORTED_DEFAULT_SHELL
        if any(
            marker in label
            for label in labels
            for marker in ("linux", "ubuntu", "macos")
        ):
            return None
        return _UNSUPPORTED_DEFAULT_SHELL

    run_steps: list[tuple[str, str | None]] = []
    workflow_shell = default_shell(document, None)
    if workflow_shell is _INVALID_SHELL:
        return None

    jobs = document.get("jobs")
    if jobs is not None:
        if not isinstance(jobs, dict):
            return None
        for job in jobs.values():
            if not isinstance(job, dict):
                return None
            job_shell = default_shell(job, workflow_shell)
            if job_shell is None:
                job_shell = runner_default_shell(job)
            if job_shell is _INVALID_SHELL or not append_steps(
                job.get("steps"),
                job_shell,
                run_steps,
            ):
                return None

    runs = document.get("runs")
    if runs is not None:
        if not isinstance(runs, dict):
            return None
        if runs.get("using") == "composite" and not append_steps(
            runs.get("steps"),
            None,
            run_steps,
        ):
            return None

    if len(run_steps) != observed_run_scalars:
        return None
    return tuple(run_steps)


def _cargo_subcommand_index(invocation: list[str]) -> int | None:
    index = 1
    if index < len(invocation) and invocation[index].startswith("+"):
        index += 1
    while index < len(invocation):
        token = invocation[index]
        if (
            token in NATIVE_FIXED64_CPU_V4_CARGO_TERMINAL_OPTIONS_WITHOUT_VALUE
            or token in NATIVE_FIXED64_CPU_V4_CARGO_TERMINAL_OPTIONS_WITH_VALUE
            or any(
                token.startswith(option + "=")
                for option in NATIVE_FIXED64_CPU_V4_CARGO_TERMINAL_OPTIONS_WITH_VALUE
            )
            or any(
                token.startswith(option + "=")
                for option in NATIVE_FIXED64_CPU_V4_CARGO_TERMINAL_OPTIONS_WITHOUT_VALUE
                if option.startswith("--")
            )
            or (
                re.fullmatch(r"-[qvVh]+", token) is not None
                and ("V" in token or "h" in token)
            )
        ):
            return -1
        if token in NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if any(
            token.startswith(option + "=")
            for option in NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITH_VALUE
            if option.startswith("--")
        ) or (token.startswith(("-C", "-Z")) and len(token) > 2):
            index += 1
            continue
        if (
            token in NATIVE_FIXED64_CPU_V4_CARGO_GLOBAL_OPTIONS_WITHOUT_VALUE
            or re.fullmatch(r"-[qv]+", token)
        ):
            index += 1
            continue
        if token.startswith("-"):
            return None
        return index
    return None


def _timeout_wrapped_command_index(
    segment: list[str],
    timeout_index: int,
) -> int | None:
    index = timeout_index + 1
    while index < len(segment):
        token = segment[index]
        if token in {"--help", "--version"}:
            return None
        if token == "--":
            index += 1
            break
        if token in {"-k", "--kill-after", "-s", "--signal"}:
            if index + 1 >= len(segment):
                return _AMBIGUOUS_COMMAND_INDEX
            index += 2
            continue
        if token.startswith(("--kill-after=", "--signal=")):
            index += 1
            continue
        if token in {
            "--foreground",
            "--preserve-status",
            "--verbose",
        }:
            index += 1
            continue
        if token.startswith("--"):
            return _AMBIGUOUS_COMMAND_INDEX
        if token.startswith("-") and token != "-":
            cluster = token[1:]
            cluster_index = 0
            consumes_next = False
            while cluster_index < len(cluster):
                option = cluster[cluster_index]
                if option in {"f", "p", "v"}:
                    cluster_index += 1
                    continue
                if option in {"k", "s"}:
                    if cluster_index + 1 == len(cluster):
                        consumes_next = True
                    cluster_index = len(cluster)
                    continue
                return _AMBIGUOUS_COMMAND_INDEX
            index += 1
            if consumes_next:
                if index >= len(segment):
                    return _AMBIGUOUS_COMMAND_INDEX
                index += 1
            continue
        break
    if index + 1 >= len(segment):
        return _AMBIGUOUS_COMMAND_INDEX
    return index + 1


def _shell_outer_command_word_index(segment: list[str]) -> int | None:
    index = 0
    while index < len(segment):
        while index < len(segment) and (
            segment[index]
            in {
                "!",
                "do",
                "elif",
                "else",
                "if",
                "then",
                "until",
                "while",
            }
            or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*=.*", segment[index]
            )
        ):
            index += 1
        if index >= len(segment):
            return None
        if segment[index] == "command":
            index += 1
            if index < len(segment) and re.fullmatch(
                r"-[pVv]*[Vv][pVv]*", segment[index]
            ):
                return None
            while index < len(segment) and (
                segment[index] == "--" or segment[index].startswith("-p")
            ):
                index += 1
            continue
        if segment[index] == "exec":
            index += 1
            while index < len(segment):
                token = segment[index]
                if token == "--":
                    index += 1
                elif token == "-a" or re.fullmatch(r"-[cl]*a[cl]*", token):
                    index += 2
                elif re.fullmatch(r"-[cl]+", token):
                    index += 1
                else:
                    break
            continue
        if segment[index] == "time":
            index += 1
            while index < len(segment) and segment[index] in {"--", "-p"}:
                index += 1
            continue
        if segment[index].rsplit("/", 1)[-1] == "timeout":
            nested_index = _timeout_wrapped_command_index(segment, index)
            if nested_index is None or nested_index == _AMBIGUOUS_COMMAND_INDEX:
                return nested_index
            index = nested_index
            continue
        return index
    return None


def _shell_command_word_index(segment: list[str]) -> int | None:
    index = _shell_outer_command_word_index(segment)
    if (
        index is None
        or index == _AMBIGUOUS_COMMAND_INDEX
        or segment[index].rsplit("/", 1)[-1] != "env"
    ):
        return index
    index += 1
    while index < len(segment):
        token = segment[index]
        if token in {"--help", "--version"}:
            return None
        if token == "--":
            index += 1
            break
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            index += 1
            continue
        if token in {
            "-u",
            "--unset",
            "-C",
            "--chdir",
            "-S",
            "--split-string",
        }:
            index += 2
            continue
        if token.startswith(
            ("-u", "-C", "--unset=", "--chdir=", "--split-string=")
        ) or token in {
            "-i",
            "--ignore-environment",
            "-0",
            "--null",
            "-v",
            "--debug",
        }:
            index += 1
            continue
        break
    if index >= len(segment):
        return None
    nested = _shell_outer_command_word_index(segment[index:])
    if nested is None or nested == _AMBIGUOUS_COMMAND_INDEX:
        return nested
    return index + nested


def _shell_without_static_heredoc_bodies(script: str) -> str | None:
    def parse_delimiter(
        content: str,
        start: int,
    ) -> tuple[str, int, bool, bool] | None:
        index = start
        strip_tabs = index < len(content) and content[index] == "-"
        if strip_tabs:
            index += 1
        while index < len(content) and content[index] in " \t":
            index += 1

        delimiter: list[str] = []
        quote: str | None = None
        delimiter_was_quoted = False
        while index < len(content):
            character = content[index]
            if quote is not None:
                if character == quote:
                    quote = None
                    index += 1
                    continue
                if quote == '"' and character == "\\":
                    index += 1
                    if index >= len(content):
                        return None
                    delimiter.append(content[index])
                    index += 1
                    continue
                delimiter.append(character)
                index += 1
                continue
            if character in {"'", '"'}:
                delimiter_was_quoted = True
                quote = character
                index += 1
                continue
            if character == "\\":
                delimiter_was_quoted = True
                index += 1
                if index >= len(content):
                    return None
                delimiter.append(content[index])
                index += 1
                continue
            if character in " \t;&|()<>":
                break
            delimiter.append(character)
            index += 1

        value = "".join(delimiter)
        if (
            quote is not None
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", value) is None
        ):
            return None
        return value, index, strip_tabs, delimiter_was_quoted

    def has_executable_expansion(content: str) -> bool:
        index = 0
        while index < len(content):
            character = content[index]
            if character == "\\" and index + 1 < len(content):
                if content[index + 1] in {"\\", "$", "`"}:
                    index += 2
                    continue
            if character == "`" or content.startswith("$(", index):
                return True
            index += 1
        return False

    output: list[str] = []
    pending_delimiters: list[tuple[str, bool, bool]] = []
    quote: str | None = None
    for line in script.splitlines(keepends=True):
        content = line
        newline = ""
        if content.endswith("\n"):
            content = content[:-1]
            newline = "\n"
            if content.endswith("\r"):
                content = content[:-1]
                newline = "\r\n"

        if pending_delimiters:
            delimiter, strip_tabs, expansion_disabled = pending_delimiters[0]
            candidate = content.lstrip("\t") if strip_tabs else content
            if candidate == delimiter:
                pending_delimiters.pop(0)
            elif not expansion_disabled and has_executable_expansion(content):
                return None
            output.append(newline)
            continue

        output.append(line)
        index = 0
        while index < len(content):
            character = content[index]
            if quote is not None:
                if character == quote:
                    quote = None
                    index += 1
                    continue
                if quote != "'" and character == "\\":
                    index += 2
                    continue
                index += 1
                continue
            if character in {"'", '"', "`"}:
                quote = character
                index += 1
                continue
            if character == "\\":
                index += 2
                continue
            if character == "#" and (
                index == 0 or content[index - 1] in " \t;&|()"
            ):
                break
            if (
                content.startswith("<<", index)
                and not content.startswith("<<<", index)
            ):
                parsed = parse_delimiter(content, index + 2)
                if parsed is None:
                    return None
                delimiter, index, strip_tabs, expansion_disabled = parsed
                pending_delimiters.append(
                    (delimiter, strip_tabs, expansion_disabled)
                )
                continue
            index += 1

    return None if pending_delimiters else "".join(output)


def _shell_command_segments(tokens: list[str]) -> tuple[tuple[str, ...], ...]:
    segments: list[tuple[str, ...]] = []
    segment: list[str] = []
    conditional_depth = 0
    for token in [*tokens, ";"]:
        if token in {"[[", "(("}:
            conditional_depth += 1
        if (
            token
            and set(token) <= set(";&|()\n")
            and conditional_depth == 0
        ):
            if segment:
                segments.append(tuple(segment))
            segment = []
        else:
            segment.append(token)
        if token in {"]]", "))"} and conditional_depth:
            conditional_depth -= 1
    return tuple(segments)


def _workflow_has_dynamic_cargo_run_command(tokens: list[str]) -> bool:
    for immutable_segment in _shell_command_segments(tokens):
        segment = list(immutable_segment)
        if segment:
            command_index = _shell_command_word_index(segment)
            if command_index == _AMBIGUOUS_COMMAND_INDEX:
                return True
            nonexecuting_display = (
                command_index is not None
                and segment[command_index].rsplit("/", 1)[-1] in {"echo", "printf"}
            )
            if (
                command_index is not None
                and not nonexecuting_display
                and (
                    segment[command_index].startswith("${{")
                    or re.fullmatch(
                        r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^{}]+\})",
                        segment[command_index],
                    )
                )
            ):
                return True
            for index, candidate in enumerate(segment[:-1]):
                if (
                    any(
                        marker in candidate
                        for marker in NATIVE_FIXED64_CPU_V4_SHELL_EXPANSION_MARKERS
                    )
                    and not (
                        nonexecuting_display
                        and index > command_index
                        and re.fullmatch(
                            r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^{}]+\})",
                            candidate,
                        )
                    )
                ):
                    invocation = ["cargo", *segment[index + 1 :]]
                    subcommand_index = _cargo_subcommand_index(invocation)
                    if subcommand_index == -1:
                        continue
                    if subcommand_index is None:
                        if any(
                            command in invocation[1:]
                            for command in NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS
                        ):
                            return True
                        continue
                    if (
                        invocation[subcommand_index]
                        in NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS
                        and not _cargo_run_has_static_non_probe_target(
                            invocation[subcommand_index + 1 :]
                        )
                    ):
                        return True
    return False


def _cargo_run_has_static_non_probe_target(arguments: list[str]) -> bool:
    pre_separator = arguments[: arguments.index("--")] if "--" in arguments else arguments
    if any(
        marker in token
        for token in pre_separator
        for marker in NATIVE_FIXED64_CPU_V4_SHELL_EXPANSION_MARKERS
    ):
        return False

    targets: list[str] = []
    index = 0
    while index < len(pre_separator):
        token = pre_separator[index]
        if token in NATIVE_FIXED64_CPU_V4_CARGO_TARGET_SELECTORS:
            if index + 1 >= len(pre_separator):
                return False
            targets.append(pre_separator[index + 1])
            index += 2
            continue
        for selector in NATIVE_FIXED64_CPU_V4_CARGO_TARGET_SELECTORS:
            prefix = selector + "="
            if token.startswith(prefix):
                targets.append(token[len(prefix) :])
                break
        index += 1

    return (
        len(targets) == 1
        and NATIVE_FIXED64_CPU_V4_STATIC_TARGET_PATTERN.fullmatch(targets[0])
        is not None
        and targets[0] not in NATIVE_FIXED64_CPU_V4_FORBIDDEN_WORKFLOW_TOKENS
    )


def _shell_tokens_invoke_native_fixed64_cpu_v4_live_probe(
    tokens: list[str],
    *,
    embedded_depth: int = 0,
) -> bool:
    if embedded_depth > 8:
        return True
    if _workflow_has_dynamic_cargo_run_command(tokens):
        return True

    for immutable_segment in _shell_command_segments(tokens):
        segment = list(immutable_segment)
        outer_command_index = _shell_outer_command_word_index(segment)
        command_index = _shell_command_word_index(segment)
        if (
            outer_command_index == _AMBIGUOUS_COMMAND_INDEX
            or command_index == _AMBIGUOUS_COMMAND_INDEX
        ):
            return True
        if command_index is None:
            command_index = 0
            while command_index < len(segment) and (
                segment[command_index]
                in {"!", "do", "elif", "else", "if", "then", "until", "while"}
                or re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*=.*", segment[command_index]
                )
            ):
                command_index += 1
        command = (
            segment[command_index].rsplit("/", 1)[-1]
            if command_index < len(segment)
            else ""
        )

        embedded: str | None = None
        remaining: list[str] = []
        outer_command = (
            segment[outer_command_index].rsplit("/", 1)[-1]
            if outer_command_index is not None
            else ""
        )
        if outer_command == "env":
            index = outer_command_index + 1
            while index < len(segment):
                token = segment[index]
                if token in {"-S", "--split-string"}:
                    if index + 1 >= len(segment):
                        return True
                    embedded = segment[index + 1]
                    remaining = segment[index + 2 :]
                    break
                if token.startswith("--split-string="):
                    embedded = token.removeprefix("--split-string=")
                    remaining = segment[index + 1 :]
                    break
                if token.startswith("-S") and len(token) > 2:
                    embedded = token[2:]
                    remaining = segment[index + 1 :]
                    break
                if token.startswith("-") and not token.startswith("--"):
                    cluster = token[1:]
                    split_index = cluster.find("S")
                    if split_index >= 0:
                        attached = cluster[split_index + 1 :]
                        if attached:
                            embedded = attached
                            remaining = segment[index + 1 :]
                        elif index + 1 < len(segment):
                            embedded = segment[index + 1]
                            remaining = segment[index + 2 :]
                        else:
                            return True
                        break
                if token == "--" or not (
                    token.startswith("-")
                    or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token)
                ):
                    break
                index += 1
        if embedded is None and command == "eval":
            if command_index + 1 < len(segment):
                embedded = " ".join(segment[command_index + 1 :])
        if embedded is None and command in {"bash", "dash", "ksh", "sh", "zsh"}:
            index = command_index + 1
            has_command_option = False
            while index < len(segment):
                token = segment[index]
                if token == "--":
                    index += 1
                    break
                if token in {"-O", "-o", "--init-file", "--rcfile"}:
                    if index + 1 >= len(segment):
                        return True
                    index += 2
                    continue
                if token.startswith(("--init-file=", "--rcfile=")):
                    index += 1
                    continue
                if token.startswith("--"):
                    if token not in {
                        "--debugger",
                        "--dump-po-strings",
                        "--dump-strings",
                        "--help",
                        "--login",
                        "--noediting",
                        "--noprofile",
                        "--norc",
                        "--posix",
                        "--pretty-print",
                        "--restricted",
                        "--verbose",
                        "--version",
                    }:
                        return True
                    index += 1
                    continue
                if token.startswith(("-", "+")) and token not in {"-", "+"}:
                    cluster = token[1:]
                    value_option_indexes = [
                        option_index
                        for option_index, option in enumerate(cluster)
                        if option in {"O", "o"}
                    ]
                    if any(
                        option not in "abefhklmnptuvxBCEHPTDcsOo"
                        for option in cluster
                    ):
                        return True
                    has_command_option = has_command_option or "c" in cluster
                    if value_option_indexes:
                        if (
                            len(value_option_indexes) != 1
                            or value_option_indexes[0] != len(cluster) - 1
                            or index + 1 >= len(segment)
                        ):
                            return True
                        index += 2
                        continue
                    index += 1
                    continue
                if not token.startswith(("-", "+")):
                    break
                return True
            if has_command_option:
                if index >= len(segment):
                    return True
                embedded = segment[index]
        if embedded is None:
            continue
        embedded_executable = _shell_without_static_heredoc_bodies(embedded)
        if embedded_executable is None:
            return True
        lexer = shlex.shlex(
            embedded_executable,
            posix=True,
            punctuation_chars=";&|()\n",
        )
        lexer.whitespace_split = True
        lexer.whitespace = " \t\r"
        lexer.commenters = "#"
        try:
            embedded_tokens = [*list(lexer), *remaining]
        except ValueError:
            return True
        if _shell_tokens_invoke_native_fixed64_cpu_v4_live_probe(
            embedded_tokens,
            embedded_depth=embedded_depth + 1,
        ):
            return True

    for index, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] != "cargo":
            continue
        invocation: list[str] = []
        for candidate in tokens[index:]:
            if invocation and (
                candidate.rsplit("/", 1)[-1] == "cargo"
                or (candidate and set(candidate) <= set(";&|()\n"))
            ):
                break
            invocation.append(candidate)
        subcommand_index = _cargo_subcommand_index(invocation)
        if subcommand_index == -1:
            continue
        if subcommand_index is None and any(
            command in invocation[1:]
            for command in NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS
        ):
            return True
        if (
            subcommand_index is not None
            and invocation[subcommand_index]
            in NATIVE_FIXED64_CPU_V4_CARGO_RUN_SUBCOMMANDS
            and not _cargo_run_has_static_non_probe_target(
                invocation[subcommand_index + 1 :]
            )
        ):
            return True
    return False


def _is_supported_bourne_shell(shell: str | None) -> bool:
    if shell is None:
        return True
    if any(marker in shell for marker in ("$", "`", "${{")):
        return False
    try:
        tokens = shlex.split(shell, posix=True)
    except ValueError:
        return False
    return bool(tokens) and tokens[0].rsplit("/", 1)[-1] in {
        "bash",
        "dash",
        "ksh",
        "sh",
        "zsh",
    }


def _workflow_invokes_native_fixed64_cpu_v4_live_probe(text: str) -> bool:
    logical = text.replace("\\\n", " ")
    yaml_run_steps = _workflow_yaml_run_steps(logical)
    if yaml_run_steps is None:
        return True
    for line, shell in yaml_run_steps:
        if not _is_supported_bourne_shell(shell):
            return True
        executable = _shell_without_static_heredoc_bodies(line)
        if executable is None:
            return True
        if any(
            token in executable
            for token in NATIVE_FIXED64_CPU_V4_FORBIDDEN_WORKFLOW_TOKENS
        ):
            return True
        lexer = shlex.shlex(executable, posix=True, punctuation_chars=";&|()\n")
        lexer.whitespace_split = True
        lexer.whitespace = " \t\r"
        lexer.commenters = "#"
        try:
            tokens = list(lexer)
        except ValueError:
            return True
        if _shell_tokens_invoke_native_fixed64_cpu_v4_live_probe(tokens):
            return True
    return False


def _implementation_text_invokes_native_fixed64_cpu_v4_live_probe(
    text: str,
) -> bool:
    if any(
        token in text
        for token in NATIVE_FIXED64_CPU_V4_FORBIDDEN_WORKFLOW_TOKENS
    ):
        return True
    return re.search(NATIVE_FIXED64_CPU_V4_CARGO_RUN_PATTERN, text) is not None


def _resolve_local_action_path(
    repo_root: Path,
    manifest: Path,
    raw_path: str,
) -> Path | None:
    if (
        not raw_path
        or raw_path.startswith("docker://")
        or any(marker in raw_path for marker in ("$", "`", "${{"))
    ):
        return None
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = manifest.parent / relative
    try:
        resolved_root = repo_root.resolve(strict=True)
        lexical_candidate = candidate.absolute()
        lexical_relative = lexical_candidate.relative_to(resolved_root)
        current = resolved_root
        for part in lexical_relative.parts:
            current /= part
            if current.is_symlink():
                return None
        resolved = current.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _local_action_execution_surface(
    repo_root: Path,
    manifests: tuple[str, ...],
) -> tuple[tuple[str, ...], bool, bool]:
    implementation_files: set[str] = set()
    surface_complete = True
    invokes_live_probe = False
    resolved_root = repo_root.resolve()

    for manifest_raw in manifests:
        manifest = repo_root / manifest_raw
        try:
            manifest_text = manifest.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            surface_complete = False
            continue
        if len(manifest_text.encode("utf-8")) > (
            NATIVE_FIXED64_CPU_V4_MAX_WORKFLOW_UTF8_BYTES
        ):
            surface_complete = False
            continue
        try:
            document = yaml.safe_load(manifest_text)
        except (yaml.YAMLError, RecursionError):
            surface_complete = False
            continue
        if not isinstance(document, dict) or not isinstance(
            document.get("runs"), dict
        ):
            surface_complete = False
            continue
        runs = document["runs"]
        using = runs.get("using")
        if not isinstance(using, str):
            surface_complete = False
            continue
        if _implementation_text_invokes_native_fixed64_cpu_v4_live_probe(
            manifest_text
        ):
            invokes_live_probe = True

        if using == "composite":
            if _workflow_invokes_native_fixed64_cpu_v4_live_probe(
                manifest_text
            ):
                invokes_live_probe = True
            continue

        primary_paths: list[Path] = []
        if using == "docker":
            image = runs.get("image")
            if not isinstance(image, str) or image.startswith("docker://"):
                surface_complete = False
                continue
            resolved_image = _resolve_local_action_path(
                repo_root,
                manifest,
                image,
            )
            if resolved_image is None:
                surface_complete = False
                continue
            primary_paths.append(resolved_image)
        elif using.startswith("node"):
            for key in ("main", "pre", "post"):
                raw_path = runs.get(key)
                if raw_path is None and key != "main":
                    continue
                if not isinstance(raw_path, str):
                    surface_complete = False
                    continue
                resolved_path = _resolve_local_action_path(
                    repo_root,
                    manifest,
                    raw_path,
                )
                if resolved_path is None:
                    surface_complete = False
                    continue
                primary_paths.append(resolved_path)
        else:
            surface_complete = False
            continue

        action_files = tuple(
            path
            for path in manifest.parent.rglob("*")
            if path.is_file() and path != manifest
        )
        if len(action_files) > NATIVE_FIXED64_CPU_V4_MAX_LOCAL_ACTION_FILES:
            surface_complete = False
            continue
        total_utf8_bytes = 0
        for implementation in sorted(set((*primary_paths, *action_files))):
            try:
                resolved = implementation.resolve(strict=True)
                relative = resolved.relative_to(resolved_root).as_posix()
            except (OSError, ValueError):
                surface_complete = False
                continue
            if implementation.is_symlink() or not resolved.is_file():
                surface_complete = False
                continue
            try:
                text = resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                surface_complete = False
                continue
            total_utf8_bytes += len(text.encode("utf-8"))
            if total_utf8_bytes > (
                NATIVE_FIXED64_CPU_V4_MAX_LOCAL_ACTION_UTF8_BYTES
            ):
                surface_complete = False
                break
            implementation_files.add(relative)
            if _implementation_text_invokes_native_fixed64_cpu_v4_live_probe(
                text
            ):
                invokes_live_probe = True

    return (
        tuple(sorted(implementation_files)),
        surface_complete,
        invokes_live_probe,
    )


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
    canonical_text = json.dumps(
        contract,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
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
        and all(authority.get(key) is False for key in CPU_PERFORMANCE_FALSE_AUTHORITY_KEYS)
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

    profile_v3_path = (
        repo_root / "config/engine_v2_cpu_performance_profile_v3.json"
    )
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
        and reader.get("exact_path")
        == "/sys/devices/system/cpu/cpufreq/boost"
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
        or activation.get("status")
        != "implementation_admitted_execution_not_attested"
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
            activation_restrictions.get(key) is False
            for key in expected_restrictions
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


def _native_fixed64_cpu_v4_authority_is_fail_closed(repo_root: Path) -> bool:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise ValueError(f"duplicate JSON key: {key}")
            observed[key] = value
        return observed

    def reject_nonfinite(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    path = repo_root / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
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
        != "betelgeuze.engine_v2_native_fixed64_cpu_profile/4.0.0"
        or profile.get("profile_id")
        != "engine_v2_native_fixed64_cpu_synthetic_v4"
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
    return bool(
        type(authority) is dict
        and set(authority) == set(NATIVE_FIXED64_CPU_V4_FALSE_AUTHORITY_KEYS)
        and all(
            authority.get(key) is False
            for key in NATIVE_FIXED64_CPU_V4_FALSE_AUTHORITY_KEYS
        )
        and type(restrictions) is dict
        and set(restrictions) == set(NATIVE_FIXED64_CPU_V4_FALSE_RESTRICTION_KEYS)
        and all(
            restrictions.get(key) is False
            for key in NATIVE_FIXED64_CPU_V4_FALSE_RESTRICTION_KEYS
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
            for row in fixtures
        ]
        == [(64, 12, 12, 64, 0), (64, 12, 12, 48, 16)]
        and all(row.get("contains_molecular_data") is False for row in fixtures)
        and type(core) is dict
        and core.get("python_scientific_work_allowed") is False
        and core.get("receptor_context_recreated_inside_samples") is False
        and type(performance) is dict
        and performance.get("performance_claim_authorized") is False
    )


def _native_fixed64_cpu_v4_binary_is_activation_blocked(repo_root: Path) -> bool:
    path = (
        repo_root
        / "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"
    )
    try:
        source = path.read_bytes().decode("ascii")
    except (OSError, UnicodeError):
        return False
    activation_constant = (
        "const FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = false;"
    )
    activation_function = re.compile(
        r"const\s+fn\s+live_activation_admitted\(\)\s*->\s*bool\s*"
        r"\{\s*FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED\s*\}"
    )
    activation_guard = "if !live_activation_admitted()"
    qualification_binding = (
        "let config = Fixed64CpuProbeConfigV4::qualification_profile();"
    )
    qualification_call = "Fixed64CpuProbeConfigV4::qualification_profile()"
    measurement_call = "run_native_fixed64_cpu_probe_v4(config)"
    return bool(
        source.count(activation_constant) == 1
        and "FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = true" not in source
        and len(activation_function.findall(source)) == 1
        and source.count(activation_guard) == 1
        and source.count("return ExitCode::from(3);") == 1
        and source.count(qualification_call) == 1
        and source.count(qualification_binding) == 1
        and source.count("Fixed64CpuProbeConfigV4") == 2
        and "Fixed64CpuProbeConfigV4 {" not in source
        and source.count(measurement_call) == 1
        and source.count("run_native_fixed64_cpu_probe_v4") == 2
        and source.index(activation_guard)
        < source.index(qualification_binding)
        < source.index(measurement_call)
    )


def build_inventory(repo_root: Path) -> dict[str, Any]:
    workflow_root = repo_root / ".github/workflows"
    github_workflows = tuple(
        sorted(
            {
                path.relative_to(repo_root).as_posix()
                for pattern in ("*.yml", "*.yaml")
                for path in workflow_root.glob(pattern)
                if path.is_file()
            }
        )
    )
    github_workflow_text = {
        path: (repo_root / path).read_text(encoding="utf-8")
        for path in github_workflows
    }
    github_action_candidates = tuple(
        sorted(
            {
                path
                for pattern in ("**/action.yml", "**/action.yaml")
                for path in repo_root.glob(pattern)
            }
        )
    )
    github_action_manifest_surface_complete = all(
        path.is_file() and not path.is_symlink()
        for path in github_action_candidates
    )
    github_action_manifests = tuple(
        path.relative_to(repo_root).as_posix()
        for path in github_action_candidates
        if path.is_file() and not path.is_symlink()
    )
    (
        github_action_implementation_files,
        github_action_execution_surface_complete,
        github_action_invokes_native_fixed64_cpu_v4_live_probe,
    ) = _local_action_execution_surface(repo_root, github_action_manifests)
    github_action_surface_complete = (
        github_action_manifest_surface_complete
        and github_action_execution_surface_complete
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
    mixed64_v2_authority_fail_closed = (
        not mixed64_v2_contract_present
        or (
            mixed64_v2_contract_files_complete
            and _mixed64_v2_authority_is_fail_closed(repo_root)
        )
    )
    mixed64_v2_contract_in_authoritative_ci = (
        not mixed64_v2_contract_present
        or (
            mixed64_v2_contract_files_complete
            and mixed64_v2_authority_fail_closed
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in MIXED64_V2_REQUIRED_TOKEN_COUNTS.items()
            )
        )
    )

    cpu_performance_contract_present = any(
        (repo_root / path).is_file() for path in CPU_PERFORMANCE_CONTRACT_PATHS
    )
    cpu_performance_contract_files_complete = all(
        (repo_root / path).is_file() for path in CPU_PERFORMANCE_CONTRACT_PATHS
    )
    cpu_performance_authority_fail_closed = (
        not cpu_performance_contract_present
        or (
            cpu_performance_contract_files_complete
            and _cpu_performance_authority_is_fail_closed(repo_root)
        )
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

    native_fixed64_cpu_v4_contract_present = any(
        (repo_root / path).is_file()
        for path in NATIVE_FIXED64_CPU_V4_CONTRACT_PATHS
    )
    native_fixed64_cpu_v4_contract_files_complete = all(
        (repo_root / path).is_file()
        for path in NATIVE_FIXED64_CPU_V4_CONTRACT_PATHS
    )
    native_fixed64_cpu_v4_live_qualification_absent_from_github_actions = not any(
        _workflow_invokes_native_fixed64_cpu_v4_live_probe(text)
        for text in github_workflow_text.values()
    ) and not github_action_invokes_native_fixed64_cpu_v4_live_probe
    native_fixed64_cpu_v4_live_qualification_absent_from_github_actions = (
        native_fixed64_cpu_v4_live_qualification_absent_from_github_actions
        and github_action_surface_complete
    )
    native_fixed64_cpu_v4_binary_activation_blocked = (
        _native_fixed64_cpu_v4_binary_is_activation_blocked(repo_root)
    )
    native_fixed64_cpu_v4_authority_fail_closed = (
        not native_fixed64_cpu_v4_contract_present
        or (
            native_fixed64_cpu_v4_contract_files_complete
            and _native_fixed64_cpu_v4_authority_is_fail_closed(repo_root)
            and native_fixed64_cpu_v4_binary_activation_blocked
            and native_fixed64_cpu_v4_live_qualification_absent_from_github_actions
        )
    )
    native_fixed64_cpu_v4_contract_in_authoritative_ci = (
        not native_fixed64_cpu_v4_contract_present
        or (
            native_fixed64_cpu_v4_contract_files_complete
            and native_fixed64_cpu_v4_authority_fail_closed
            and all(
                main_text.count(token) >= minimum_count
                for token, minimum_count in (
                    NATIVE_FIXED64_CPU_V4_REQUIRED_TOKEN_COUNTS.items()
                )
            )
        )
    )

    one_shot_contract_present = any(
        (repo_root / path).is_file() for path in ONE_SHOT_CONTRACT_PATHS
    )
    external_reservation_contract_present = any(
        (repo_root / path).is_file()
        for path in EXTERNAL_RESERVATION_CONTRACT_PATHS
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

    one_shot_contract_in_authoritative_ci = (
        not one_shot_contract_present
        or all(token in main_text for token in required_one_shot_tokens)
    )
    external_reservation_contract_in_authoritative_ci = (
        not external_reservation_contract_present
        or all(
            token in main_text
            for token in EXTERNAL_RESERVATION_REQUIRED_TOKENS
        )
    )
    standalone_pipeline_contract_present = any(
        (repo_root / path).is_file()
        for path in STANDALONE_PIPELINE_CONTRACT_PATHS
    )
    standalone_pipeline_contract_in_authoritative_ci = (
        not standalone_pipeline_contract_present
        or all(
            main_text.count(token) >= 2
            for token in STANDALONE_PIPELINE_REQUIRED_TOKENS
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
    standalone_contract_in_authoritative_ci = (
        not standalone_contract_present
        or all(token in main_text for token in STANDALONE_REQUIRED_TOKENS)
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
        "native_fixed64_cpu_v4_contract_in_authoritative_ci": (
            native_fixed64_cpu_v4_contract_in_authoritative_ci
        ),
        "native_fixed64_cpu_v4_authority_fail_closed": (
            native_fixed64_cpu_v4_authority_fail_closed
        ),
        "native_fixed64_cpu_v4_binary_activation_blocked": (
            native_fixed64_cpu_v4_binary_activation_blocked
        ),
        "native_fixed64_cpu_v4_live_qualification_absent_from_github_actions": (
            native_fixed64_cpu_v4_live_qualification_absent_from_github_actions
        ),
        "native_fixed64_cpu_v4_github_action_manifests": list(
            github_action_manifests
        ),
        "native_fixed64_cpu_v4_github_action_implementation_files": list(
            github_action_implementation_files
        ),
        "native_fixed64_cpu_v4_github_action_surface_complete": (
            github_action_surface_complete
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
