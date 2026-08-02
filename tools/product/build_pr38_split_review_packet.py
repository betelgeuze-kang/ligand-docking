#!/usr/bin/env python3
"""Build a read-only PR #38 split review packet.

The packet maps each changed file in the large PR #38 branch to one proposed
child PR slice and verifies that each slice has a task spec, focused tests, and
an explicit claim boundary. It does not create branches, stage files, post to
GitHub, or mutate external state.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASE_REF = "origin/main"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_split_review_packet_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_split_review_packet_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_split_review_packet_current.md"

PACKET_TYPE = "pr38_split_review_packet"
SCHEMA_VERSION = "pr38_split_review_packet_v1"
MINIMUM_CHILD_PR_COUNT = 5

CLAIM_BOUNDARY = (
    "PR #38 split review packet only; it maps local changed files to review slices and checks that each slice "
    "has focused verification and claim-boundary text. It does not merge PR #38, create branches, stage, commit, "
    "push, post comments, run external benchmark jobs, submit CASP targets, promote paid-pilot wording, or mutate "
    "external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
}


_SLICE_SPECS: list[dict[str, Any]] = [
    {
        "slice_id": "ci_runner_hygiene",
        "title": "self-hosted runner cleanup and product image smoke hygiene",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-ci-runner-hygiene.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_product_image_smoke_preflight.py "
            "tests/unit/test_build_github_self_hosted_runner_host_preflight.py "
            "tests/unit/test_build_product_ci_runtime_gate.py "
            "tests/unit/test_build_release_ci_remote_green_receipt.py "
            "tests/unit/test_release_ci_remote_green_evidence_contract.py "
            "tests/unit/test_api_worker_deploy_artifacts.py "
            "tests/unit/test_ai_design_kiro_wrapper_contract.py "
            "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py "
            "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py "
            "tests/unit/test_build_pr38_child_pr_verification_matrix.py "
            "tests/unit/test_observe_product_ci_runtime_gate_from_github.py "
            "tests/unit/test_product_runtime_reality.py"
        ),
        "claim_boundary": (
            "CI hygiene proves fail-closed runner cleanup and artifact ownership only; it does not make product "
            "runtime, ROCm, scientific, paid-pilot, or release-readiness claims green."
        ),
        "patterns": [
            ".github/workflows/product-api-worker.yml",
            ".github/workflows/product-image-smoke.yml",
            "Dockerfile.product",
            "deploy/verify_product_image.sh",
            "scripts/ai-verify.sh",
            "scripts/normalize_product_image_smoke_artifact_ownership.sh",
            "tests/unit/test_api_worker_deploy_artifacts.py",
            "tests/unit/test_ai_design_kiro_wrapper_contract.py",
            "tests/unit/test_build_product_image_smoke_preflight.py",
            "tests/unit/test_build_github_self_hosted_runner_host_preflight.py",
            "tests/unit/test_build_product_ci_runtime_gate.py",
            "tests/unit/test_build_release_ci_remote_green_receipt.py",
            "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py",
            "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
            "tests/unit/test_build_pr38_child_pr_verification_matrix.py",
            "tests/unit/test_observe_product_ci_runtime_gate_from_github.py",
            "tests/unit/test_product_runtime_reality.py",
            "tests/unit/test_release_ci_remote_green_evidence_contract.py",
            "tools/product/build_pr38_ci_runner_hygiene_child_pr_gate.py",
            "tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
            "tools/product/build_pr38_child_pr_verification_matrix.py",
            "tools/product/build_github_self_hosted_runner_host_preflight.py",
            "tools/product/build_product_ci_runtime_gate.py",
            "tools/product/build_product_image_smoke_preflight.py",
            "tools/product/build_release_ci_remote_green_receipt.py",
            "tools/product/observe_product_ci_runtime_gate_from_github.py",
            "tools/product/release_ci_remote_green_evidence_contract.py",
        ],
    },
    {
        "slice_id": "source_of_truth_refresh",
        "title": "source-of-truth gap scan + release refresh path",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-source-of-truth-refresh.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_release_source_of_truth_gap5_scan.py "
            "tests/unit/test_build_product_release_source_of_truth_gate.py"
        ),
        "claim_boundary": (
            "No release-ready, paid-pilot-ready, final-refresh-success, or full-commercial-release claim until "
            "source-of-truth and final refresh gates are fresh and verified."
        ),
        "patterns": [
            "betelgeuze_product/capability_surface.py",
            "docs/product_stage_and_roadmap_2026_06_30.md",
            "tests/unit/test_build_product_capability_surface_contract.py",
            "tests/unit/test_build_product_release_source_of_truth_gate.py",
            "tests/unit/test_build_release_source_of_truth_gap5_scan.py",
            "tests/unit/test_run_product_release_current_refresh.py",
            "tools/product/build_product_release_source_of_truth_gate.py",
            "tools/product/build_release_source_of_truth_gap5_scan.py",
            "tools/product/run_product_release_current_refresh.py",
        ],
    },
    {
        "slice_id": "public_benchmark_phase2",
        "title": "public benchmark Phase 2 audit surfaces",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-public-benchmark-phase2.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_betelgeuze_product_public_benchmark.py "
            "tests/unit/test_betelgeuze_product_public_benchmark_provenance.py "
            "tests/unit/test_build_public_benchmark_phase2_harness_audit.py "
            "tests/unit/test_build_product_public_benchmark_contract.py "
            "tests/unit/test_build_product_public_benchmark_work_order.py "
            "tests/unit/test_build_pdbbind_casf_pose_affinity_results.py "
            "tests/unit/test_docking_gold_benchmark_metrics.py"
        ),
        "claim_boundary": (
            "No external beta, benchmark-success, or broad docking-accuracy claim until real reviewed benchmark "
            "receipts are attached and ledger-approved."
        ),
        "patterns": [
            "betelgeuze_engine/benchmark/docking_gold.py",
            "betelgeuze_product/public_benchmark.py",
            "betelgeuze_product/public_benchmark_provenance.py",
            "betelgeuze_product/public_benchmark_work_order.py",
            "config/refine_tier_public_benchmark_*.json",
            "docs/refine_tier_public_benchmark_*.md",
            "tests/unit/test_betelgeuze_product_public_benchmark.py",
            "tests/unit/test_betelgeuze_product_public_benchmark_provenance.py",
            "tests/unit/test_build_engine_refinement_claim_evidence_priority_packet.py",
            "tests/unit/test_build_pdbbind_casf_pose_affinity_results.py",
            "tests/unit/test_build_product_public_benchmark_contract.py",
            "tests/unit/test_build_product_public_benchmark_work_order.py",
            "tests/unit/test_build_public_benchmark_*.py",
            "tests/unit/test_build_refine_tier_public_benchmark_*.py",
            "tests/unit/test_docking_gold_benchmark_metrics.py",
            "tests/unit/test_run_external_validation_baselines.py",
            "tools/accounting/build_pdbbind_casf_pose_affinity_results.py",
            "tools/accounting/build_product_public_benchmark_contract.py",
            "tools/product/build_engine_refinement_claim_evidence_priority_packet.py",
            "tools/product/build_public_benchmark_*.py",
            "tools/product/build_refine_tier_public_benchmark_*.py",
            "tools/product/materialize_refine_tier_public_benchmark_*.py",
            "tools/run_external_validation_baselines.py",
        ],
    },
    {
        "slice_id": "gpcr_hard_decoy_closure",
        "title": "GPCR hard-decoy closure tools",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-gpcr-hard-decoy-closure.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_gpcr_hard_decoy_suite.py "
            "tests/unit/test_build_gpcr_hard_decoy_*.py tests/unit/test_build_gpcr_residual_prototype_spec.py"
        ),
        "claim_boundary": (
            "Broad GPCR and hard-decoy closure claims stay locked until DRD2/HTR2A/OPRM1 rows meet the registered "
            "numeric thresholds and ledger approval exists."
        ),
        "patterns": [
            "betelgeuze_product/gpcr_hard_decoy_suite.py",
            "config/gpcr_hard_decoy*.csv",
            "docs/gpcr_hard_decoy_suite_*.md",
            "tests/unit/test_build_gpcr_hard_decoy_*.py",
            "tests/unit/test_build_gpcr_residual_prototype_spec.py",
            "tests/unit/test_gpcr_hard_decoy_suite.py",
            "tools/accounting/build_gpcr_residual_prototype_spec.py",
            "tools/product/build_gpcr_hard_decoy_*.py",
        ],
    },
    {
        "slice_id": "competition_benchmark_credibility",
        "title": "CASP16/BM5/CAPRI/CAMEO competition credibility lane",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-competition-benchmark-credibility.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_betelgeuze_cameo_official_results.py "
            "tests/unit/test_build_cameo_official_results_intake_gate.py "
            "tests/unit/test_build_casp16_ligand_source_manifest.py "
            "tests/unit/test_build_casp16_ligand_materialization_manifest.py "
            "tests/unit/test_build_casp16_ligand_scorecard.py "
            "tests/unit/test_build_bm5_capri_complex_source_manifest.py "
            "tests/unit/test_build_bm5_capri_raw_data_custody_plan.py "
            "tests/unit/test_apply_bm5_capri_raw_data_custody_plan.py "
            "tests/unit/test_build_competition_benchmark_custody_work_order.py "
            "tests/unit/test_build_competition_benchmark_rollup.py "
            "tests/unit/test_build_package_b_competition_bridge.py"
        ),
        "claim_boundary": (
            "Competition benchmark work is credibility evidence only; it does not import CASP/native/template "
            "structures as internal predictions, store raw benchmark payloads in git, or unlock ligand commercial "
            "claims without separate Package B public ligand benchmark closure."
        ),
        "patterns": [
            "betelgeuze_cameo/official_results.py",
            "betelgeuze_product/bm5_capri_complex_source_manifest.py",
            "betelgeuze_product/casp16_ligand_source_manifest.py",
            "casp17/CASP17_*.md",
            "casp17/casp17_*_current.json",
            "docs/competition_benchmark*.md",
            "docs/package_b_competition_bridge_current.md",
            "tests/unit/test_apply_bm5_capri_raw_data_custody_plan.py",
            "tests/unit/test_betelgeuze_cameo_official_results.py",
            "tests/unit/test_build_bm5_capri_*.py",
            "tests/unit/test_build_cameo_official_results_intake_gate.py",
            "tests/unit/test_build_casp16_ligand_*.py",
            "tests/unit/test_build_competition_benchmark_*.py",
            "tests/unit/test_build_package_b_competition_bridge.py",
            "tools/accounting/build_cameo_official_results_intake_gate.py",
            "tools/apply_bm5_capri_raw_data_custody_plan.py",
            "tools/build_bm5_capri_*.py",
            "tools/build_casp16_ligand_*.py",
            "tools/build_competition_benchmark_*.py",
            "tools/build_package_b_competition_bridge.py",
            "tools/product/apply_bm5_capri_raw_data_custody_plan.py",
            "tools/product/build_bm5_capri_*.py",
            "tools/product/build_casp16_ligand_*.py",
            "tools/product/build_competition_benchmark_*.py",
            "tools/product/build_package_b_competition_bridge.py",
            "tools/product/run_competition_benchmark_regeneration.py",
        ],
    },
    {
        "slice_id": "pocketmd_lite_recovery",
        "title": "PocketMD Lite API/reporting/evidence recovery",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-pocketmd-lite-recovery.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_api_product_import.py "
            "tests/unit/test_product_pocketmd_lite_api.py tests/unit/test_pocketmd_lite_contract.py "
            "tests/unit/test_run_ligand_backmapping_scoring.py tests/unit/test_build_pocketmd_lite_*.py"
        ),
        "claim_boundary": (
            "PocketMD Lite recovery outputs are collector inputs only; no green-band or claim-grade metric claim "
            "until reviewed local-min, H-bond, contact, clash, relief, and banding evidence exists."
        ),
        "patterns": [
            "api/main.py",
            "api/product_pocketmd_lite.py",
            "betelgeuze_engine/product/runners/backmapping_scoring.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "config/pocketmd_lite_candidates_current.csv",
            "docs/pocketmd_lite_contract.md",
            "tests/unit/test_api_product_import.py",
            "tests/unit/test_build_pocketmd_lite_*.py",
            "tests/unit/test_build_hbond_backmap_report_builder.py",
            "tests/unit/test_pocketmd_lite_contract.py",
            "tests/unit/test_product_pocketmd_lite_api.py",
            "tests/unit/test_run_ligand_backmapping_scoring.py",
            "tools/product/build_hbond_backmap_report.py",
            "tools/product/build_pocketmd_lite_*.py",
        ],
    },
    {
        "slice_id": "developer_preview_reproducibility",
        "title": "Developer Preview reproducibility gates",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-developer-preview-reproducibility.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_developer_preview_clean_checkout_benchmark_receipt.py "
            "tests/unit/test_build_developer_preview_platform_reproducibility_receipt.py "
            "tests/unit/test_build_developer_preview_new_user_observation_receipt.py "
            "tests/unit/test_build_developer_preview_final_gate_audit.py"
        ),
        "claim_boundary": (
            "Developer Preview gates may show reproducibility blockers and fail-closed receipts only; no paid-pilot, "
            "release-ready, enterprise, or unattended execution claim opens from this slice alone."
        ),
        "patterns": [
            "docs/developer_preview_*.md",
            "tests/unit/test_build_developer_preview_*.py",
            "tests/unit/test_build_enterprise_on_prem_readiness_gate.py",
            "tests/unit/test_build_restricted_unattended_execution_readiness.py",
            "tests/unit/test_build_support_bundle.py",
            "tools/product/build_developer_preview_*.py",
            "tools/build_developer_preview_*.py",
            "tools/product/build_enterprise_on_prem_readiness_gate.py",
            "tools/product/build_restricted_unattended_execution_readiness.py",
            "tools/product/build_support_bundle.py",
        ],
    },
    {
        "slice_id": "api_operator_cockpit",
        "title": "API/operator cockpit and read-only status surfaces",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-api-operator-cockpit.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_api_goal_import.py tests/unit/test_api_goal_readiness.py "
            "tests/unit/test_api_product_operator_cockpit.py tests/unit/test_api_product_operator_cockpit_registration.py "
            "tests/unit/test_build_product_operator_cockpit.py tests/unit/test_build_goal_api_surface_contract.py "
            "tests/unit/test_build_goal_release_decision_gate.py"
        ),
        "claim_boundary": (
            "API/operator cockpit surfaces are read-only status and gate visibility; they must not execute jobs, "
            "mutate external state, or imply paid-pilot/full-commercial readiness."
        ),
        "patterns": [
            "api/goal.py",
            "api/product.py",
            "api/product_benchmark.py",
            "api/product_capabilities.py",
            "api/product_gpcr_hard_decoy.py",
            "api/product_hbond_backmap.py",
            "api/product_operator_cockpit.py",
            "api/product_architecture.py",
            "betelgeuze_product/architecture.py",
            "betelgeuze_product/service_boundary.py",
            "deploy/product_release_bundle.py",
            "docs/customer_shadow_intake.md",
            "tests/unit/test_api_cameo_import.py",
            "tests/unit/test_api_casp17_import.py",
            "tests/unit/test_api_goal_import.py",
            "tests/unit/test_api_goal_readiness.py",
            "tests/unit/test_api_product_benchmark.py",
            "tests/unit/test_api_product_capabilities.py",
            "tests/unit/test_api_product_gpcr_hard_decoy.py",
            "tests/unit/test_api_product_hbond_backmap.py",
            "tests/unit/test_api_product_operator_cockpit.py",
            "tests/unit/test_api_product_operator_cockpit_registration.py",
            "tests/unit/test_api_product_architecture_validation.py",
            "tests/unit/test_build_api_customer_flow_release_evidence.py",
            "tests/unit/test_build_api_runner_profile_promotion_readiness.py",
            "tests/unit/test_build_architecture_validation_package_report.py",
            "tests/unit/test_build_customer_shadow_evidence_status.py",
            "tests/unit/test_build_goal_api_surface_contract.py",
            "tests/unit/test_build_goal_release_decision_gate.py",
            "tests/unit/test_build_pm_priority_queue_status.py",
            "tests/unit/test_build_product_architecture_contract.py",
            "tests/unit/test_build_product_operator_cockpit.py",
            "tests/unit/test_product_release_bundle.py",
            "tools/accounting/build_goal_api_surface_contract.py",
            "tools/accounting/build_goal_release_decision_gate.py",
            "tools/product/build_architecture_validation_package_report.py",
            "tools/product/build_api_customer_flow_release_evidence.py",
            "tools/product/build_api_runner_profile_promotion_readiness.py",
            "tools/product/build_customer_shadow_evidence_status.py",
            "tools/product/build_pm_priority_queue_status.py",
            "tools/product/build_product_operator_cockpit.py",
        ],
    },
    {
        "slice_id": "docs_tests_reconciliation",
        "title": "docs/tests and split-orchestration reconciliation",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-docs-tests-reconciliation.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_pr38_split_review_packet.py "
            "tests/unit/test_build_pr38_child_pr_extraction_plan.py "
            "tests/unit/test_build_pr38_slice_patch_bundle.py "
            "tests/unit/test_build_pr38_slice_patch_apply_preflight.py "
            "tests/unit/test_build_pr38_split_acceptance_packet.py "
            "tests/unit/test_build_pr38_child_pr_verification_matrix.py "
            "tests/unit/test_improvement_items_remaining_work_doc.py"
        ),
        "claim_boundary": (
            "Docs/tests reconciliation may align wording and local split receipts only; it must not introduce product "
            "behavior, external evidence claims, or readiness wording not backed by the owning child PR."
        ),
        "patterns": [
            "docs/ai/tasks/TASK-pr38*.md",
            "docs/improvement_items_remaining_work.md",
            "tests/unit/test_build_pr38_*.py",
            "tests/unit/test_improvement_items_remaining_work_doc.py",
            "tools/build_pr38_*.py",
            "tools/product/build_pr38_*.py",
        ],
    },
    {
        "slice_id": "f2g_f2h_preflight",
        "title": "F2g/F2h preflight/work order",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-f2g-f2h-preflight.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py"
        ),
        "claim_boundary": (
            "F2g/F2h remains non-promoting: no placeholder surfaces, F2g audit, F2h continuation, 0.656 "
            "regeneration, G1 claim, or solver claim without restored authoritative inputs."
        ),
        "patterns": [
            "docs/f2g_f2h_surface_preflight.md",
            "tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py",
            "tools/accounting/build_f2g_f2h_authoritative_surface_recovery_packet.py",
            "tools/build_f2g_f2h_authoritative_surface_recovery_packet.py",
            "tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py",
        ],
    },
]

_INTEGRATION_TOUCHPOINTS = {
    "api/goal.py",
    "api/main.py",
    "api/product.py",
    "api/product_benchmark.py",
    "api/product_capabilities.py",
    "api/product_gpcr_hard_decoy.py",
    "api/product_hbond_backmap.py",
    "api/product_operator_cockpit.py",
    "deploy/product_release_bundle.py",
    "tools/accounting/build_goal_api_surface_contract.py",
    "tools/accounting/build_goal_release_decision_gate.py",
    "tools/product/build_product_operator_cockpit.py",
    "api/main.py",
    "betelgeuze_product/capability_surface.py",
    "tests/unit/test_api_product_import.py",
    "tests/unit/test_build_product_capability_surface_contract.py",
    "tests/unit/test_build_product_release_source_of_truth_gate.py",
    "tools/product/build_product_release_source_of_truth_gate.py",
    "tools/product/run_product_release_current_refresh.py",
}

_TASK_SPEC_REQUIRED_TERMS = ("Do not", "claim", "Verification", "Stop Conditions")
_FORBIDDEN_ENV_NAMES = {".env"}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_name_status(path_like: str | Path, *, root: Path = ROOT) -> list[tuple[str, str]]:
    path = _resolve(path_like, root=root)
    rows: list[tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            rows.append(("?", parts[0]))
            continue
        status = parts[0]
        file_path = parts[-1]
        if not _forbidden_env_path(file_path):
            rows.append((status, file_path))
    return rows


def _forbidden_env_path(file_path: str) -> bool:
    parts = Path(file_path).parts
    name = parts[-1] if parts else file_path
    return (
        name in _FORBIDDEN_ENV_NAMES
        or name.startswith(".env.")
        or name.endswith(".env")
        or ".env." in name
    )


def _merge_name_status_rows(*row_sets: list[tuple[str, str]]) -> list[tuple[str, str]]:
    merged: dict[str, str] = {}
    for rows in row_sets:
        for status, file_path in rows:
            if _forbidden_env_path(file_path):
                continue
            if file_path not in merged:
                merged[file_path] = status
            elif status != merged[file_path]:
                merged[file_path] = f"{merged[file_path]}+{status}"
    return [(status, file_path) for file_path, status in sorted(merged.items())]


def _git_name_status(*, base_ref: str, root: Path) -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[tuple[str, str]] = []
    for raw_line in proc.stdout.splitlines():
        parts = raw_line.split("\t")
        if len(parts) >= 2:
            file_path = parts[-1]
            if not _forbidden_env_path(file_path):
                rows.append((parts[0], file_path))
    return rows


def _git_worktree_name_status(*, root: Path) -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "diff", "--name-status"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[tuple[str, str]] = []
    for raw_line in proc.stdout.splitlines():
        parts = raw_line.split("\t")
        if len(parts) >= 2:
            file_path = parts[-1]
            if not _forbidden_env_path(file_path):
                rows.append((parts[0], file_path))
    untracked_proc = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    for raw_line in untracked_proc.stdout.splitlines():
        file_path = raw_line.strip()
        if file_path and not _forbidden_env_path(file_path):
            rows.append(("A", file_path))
    return rows


def _matches(patterns: list[str], file_path: str) -> bool:
    return any(fnmatch.fnmatchcase(file_path, pattern) for pattern in patterns)


def _slice_for_path(file_path: str) -> tuple[dict[str, Any] | None, list[str]]:
    matches = [spec for spec in _SLICE_SPECS if _matches(spec["patterns"], file_path)]
    exact_matches = [
        spec
        for spec in matches
        if any(pattern == file_path for pattern in spec["patterns"])
    ]
    if len(exact_matches) == 1:
        return (exact_matches[0], [exact_matches[0]["slice_id"]])
    return (matches[0] if len(matches) == 1 else None, [spec["slice_id"] for spec in matches])


def _task_spec_status(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    path = _resolve(spec["task_spec_path"], root=root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    missing_terms = [term for term in _TASK_SPEC_REQUIRED_TERMS if term not in text]
    return {
        "task_spec_path": spec["task_spec_path"],
        "task_spec_present": path.exists(),
        "task_spec_has_claim_boundary_terms": not missing_terms,
        "task_spec_missing_terms": missing_terms,
    }


def build_pr38_split_review_packet(
    *,
    changed_files: str | Path | None = None,
    base_ref: str = DEFAULT_BASE_REF,
    include_worktree: bool = True,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    worktree_rows: list[tuple[str, str]] = []
    if changed_files is not None:
        base_rows = _read_name_status(changed_files, root=root_path)
        name_status_rows = _merge_name_status_rows(base_rows)
    else:
        base_rows = _git_name_status(base_ref=base_ref, root=root_path)
        if include_worktree:
            worktree_rows = _git_worktree_name_status(root=root_path)
        name_status_rows = _merge_name_status_rows(base_rows, worktree_rows)
    rows: list[dict[str, Any]] = []
    for status, file_path in name_status_rows:
        spec, matching_slice_ids = _slice_for_path(file_path)
        assigned = spec is not None
        slice_id = _text(spec.get("slice_id")) if spec else ""
        rows.append(
            {
                "file_path": file_path,
                "git_status": status,
                "assigned": assigned,
                "slice_id": slice_id or "unassigned",
                "matching_slice_ids": matching_slice_ids,
                "integration_touchpoint": file_path in _INTEGRATION_TOUCHPOINTS,
                "hunk_split_review_required": file_path in _INTEGRATION_TOUCHPOINTS,
                "focused_test_command": _text(spec.get("focused_test_command")) if spec else "",
                "claim_boundary": _text(spec.get("claim_boundary")) if spec else "",
            }
        )

    slice_rows: list[dict[str, Any]] = []
    for spec in _SLICE_SPECS:
        slice_id = spec["slice_id"]
        assigned_rows = [row for row in rows if row["slice_id"] == slice_id]
        task_status = _task_spec_status(spec, root=root_path)
        slice_ready = bool(
            assigned_rows
            and task_status["task_spec_present"]
            and task_status["task_spec_has_claim_boundary_terms"]
            and spec.get("focused_test_command")
            and spec.get("claim_boundary")
        )
        slice_rows.append(
            {
                "slice_id": slice_id,
                "title": spec["title"],
                "changed_file_count": len(assigned_rows),
                "integration_touchpoint_count": sum(1 for row in assigned_rows if row["integration_touchpoint"]),
                "slice_ready_for_child_pr_review": slice_ready,
                "focused_test_command": spec["focused_test_command"],
                "claim_boundary": spec["claim_boundary"],
                **task_status,
                **_READ_ONLY_FLAGS,
            }
        )

    unassigned_rows = [row for row in rows if not row["assigned"]]
    ambiguous_rows = [row for row in rows if len(row["matching_slice_ids"]) > 1]
    nonempty_slice_count = sum(1 for row in slice_rows if int(row["changed_file_count"]) > 0)
    minimum_child_pr_count_met = nonempty_slice_count >= MINIMUM_CHILD_PR_COUNT
    empty_slices = [row["slice_id"] for row in slice_rows if int(row["changed_file_count"]) == 0]
    missing_task_specs = [row["slice_id"] for row in slice_rows if not row["task_spec_present"]]
    weak_task_specs = [row["slice_id"] for row in slice_rows if not row["task_spec_has_claim_boundary_terms"]]
    ready = (
        not unassigned_rows
        and not ambiguous_rows
        and minimum_child_pr_count_met
        and not empty_slices
        and not missing_task_specs
        and not weak_task_specs
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_split_review_packet_ready" if ready else "blocked_pr38_split_review_packet",
        "split_review_ready": ready,
        "base_ref": base_ref,
        "worktree_overlay_enabled": bool(changed_files is None and include_worktree),
        "base_changed_file_count": len(_merge_name_status_rows(base_rows)),
        "worktree_changed_file_count": len(_merge_name_status_rows(worktree_rows)),
        "changed_file_count": len(rows),
        "assigned_file_count": sum(1 for row in rows if row["assigned"]),
        "unassigned_file_count": len(unassigned_rows),
        "unassigned_file_paths": [row["file_path"] for row in unassigned_rows],
        "ambiguous_file_count": len(ambiguous_rows),
        "ambiguous_file_paths": [row["file_path"] for row in ambiguous_rows],
        "slice_count": len(slice_rows),
        "minimum_child_pr_count": MINIMUM_CHILD_PR_COUNT,
        "nonempty_child_pr_count": nonempty_slice_count,
        "minimum_child_pr_count_met": minimum_child_pr_count_met,
        "empty_slice_count": len(empty_slices),
        "empty_slice_ids": empty_slices,
        "missing_task_spec_count": len(missing_task_specs),
        "missing_task_spec_slice_ids": missing_task_specs,
        "weak_task_spec_count": len(weak_task_specs),
        "weak_task_spec_slice_ids": weak_task_specs,
        "integration_touchpoint_count": sum(1 for row in rows if row["integration_touchpoint"]),
        "hunk_split_review_required_count": sum(1 for row in rows if row["hunk_split_review_required"]),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Create child branches/PRs from the mapped slices, reviewing integration touchpoints hunk-by-hunk."
            if ready
            else "Assign unassigned/ambiguous files or repair missing task specs before child PR extraction."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "slices": slice_rows, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# PR #38 Split Review Packet",
        "",
        f"- status: `{s['status']}`",
        f"- changed_file_count: `{s['changed_file_count']}`",
        f"- assigned_file_count: `{s['assigned_file_count']}`",
        f"- unassigned_file_count: `{s['unassigned_file_count']}`",
        f"- ambiguous_file_count: `{s['ambiguous_file_count']}`",
        f"- minimum_child_pr_count: `{s['minimum_child_pr_count']}`",
        f"- nonempty_child_pr_count: `{s['nonempty_child_pr_count']}`",
        f"- minimum_child_pr_count_met: `{s['minimum_child_pr_count_met']}`",
        f"- integration_touchpoint_count: `{s['integration_touchpoint_count']}`",
        f"- hunk_split_review_required_count: `{s['hunk_split_review_required_count']}`",
        "",
        "| slice | files | integration touchpoints | task spec | ready |",
        "| --- | --: | --: | --- | --- |",
    ]
    for row in payload["slices"]:
        lines.append(
            "| `{slice_id}` | {files} | {integration} | `{task}` | `{ready}` |".format(
                slice_id=row["slice_id"],
                files=row["changed_file_count"],
                integration=row["integration_touchpoint_count"],
                task=row["task_spec_path"],
                ready=row["slice_ready_for_child_pr_review"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a PR #38 split review packet.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--changed-files", default=None)
    parser.add_argument(
        "--no-include-worktree",
        action="store_true",
        help="Use only base-ref...HEAD when --changed-files is omitted.",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_split_review_packet(
        changed_files=args.changed_files,
        base_ref=args.base_ref,
        include_worktree=not args.no_include_worktree,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["split_review_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
