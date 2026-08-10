#!/usr/bin/env python3
"""Build a deterministic inventory of Engine V2 CI authority surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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
    "config/engine_v2_cpu_performance_profile.json",
    "config/engine_v2_cpu_performance_v2_terminal_decision.json",
    "tools/run_engine_v2_cpu_performance_qualification.py",
    "tools/verify_engine_v2_cpu_performance_profile.py",
    "tools/verify_engine_v2_cpu_performance_v2_terminal_decision.py",
    "tests/unit/test_engine_v2_cpu_performance_sidecar.py",
    "tests/unit/test_verify_engine_v2_cpu_performance_profile.py",
    "tests/unit/test_verify_engine_v2_cpu_performance_v2_terminal_decision.py",
    "tests/unit/test_engine_v2_native_geometric_admission.py",
    "docs/engine_v2_cpu_performance_qualification.md",
)
CPU_PERFORMANCE_REQUIRED_TOKEN_COUNTS = {
    "config/engine_v2_cpu_performance_profile.json": 2,
    "config/engine_v2_cpu_performance_v2_terminal_decision.json": 2,
    "tools/run_engine_v2_cpu_performance_qualification.py": 3,
    "tools/verify_engine_v2_cpu_performance_profile.py": 4,
    "tools/verify_engine_v2_cpu_performance_v2_terminal_decision.py": 3,
    "tests/unit/test_engine_v2_cpu_performance_sidecar.py": 2,
    "tests/unit/test_verify_engine_v2_cpu_performance_profile.py": 2,
    "tests/unit/test_verify_engine_v2_cpu_performance_v2_terminal_decision.py": 2,
    "tests/unit/test_engine_v2_native_geometric_admission.py": 2,
    "docs/engine_v2_cpu_performance_qualification.md": 1,
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
    return bool(
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


def build_inventory(repo_root: Path) -> dict[str, Any]:
    workflow_root = repo_root / ".github/workflows"
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
