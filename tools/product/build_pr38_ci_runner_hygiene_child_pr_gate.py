#!/usr/bin/env python3
"""Build a fail-closed gate for PR #38's first CI runner hygiene child PR.

The gate reads existing PR #38 split artifacts and local product-image runner
hygiene receipts. It writes local evidence only; it does not create branches,
stage, commit, push, open PRs, dispatch workflows, or mutate external state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from tools.builder_table_utils import write_csv_rows


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXTRACTION_PLAN_JSON = ".betelgeuze/pr38_child_pr_extraction_plan_current.json"
DEFAULT_PATCH_BUNDLE_JSON = ".betelgeuze/pr38_slice_patch_bundle_current.json"
DEFAULT_APPLY_PREFLIGHT_JSON = ".betelgeuze/pr38_slice_patch_apply_preflight_current.json"
DEFAULT_LAUNCH_COMMAND_PACK_JSON = ".betelgeuze/pr38_child_pr_launch_command_pack_current.json"
DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON = "runs/product_ci_runtime_gate_current.json"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.md"

PACKET_TYPE = "pr38_ci_runner_hygiene_child_pr_gate"
SCHEMA_VERSION = "pr38_ci_runner_hygiene_child_pr_gate_v1"
SLICE_ID = "ci_runner_hygiene"

REQUIRED_PATCH_FILES = [
    ".github/dependabot.yml",
    ".github/workflows/product-api-worker.yml",
    ".github/workflows/product-api-worker-trusted.yml",
    ".github/workflows/product-image-smoke.yml",
    ".github/workflows/product-image-smoke-trusted.yml",
    "docs/roadmaps/2026-07-repository-recovery-and-engine-roadmap.md",
    "Dockerfile.product",
    "deploy/verify_product_image.sh",
    "scripts/ai-verify.sh",
    "scripts/normalize_product_image_smoke_artifact_ownership.sh",
    "tests/unit/test_ai_design_kiro_wrapper_contract.py",
    "tests/unit/test_api_worker_deploy_artifacts.py",
    "tests/unit/test_build_github_self_hosted_runner_host_preflight.py",
    "tests/unit/test_build_product_ci_runtime_gate.py",
    "tests/unit/test_build_product_image_smoke_preflight.py",
    "tests/unit/test_build_release_ci_remote_green_receipt.py",
    "tests/unit/test_github_workflow_trust_boundaries.py",
    "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py",
    "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
    "tests/unit/test_build_pr38_child_pr_verification_matrix.py",
    "tests/unit/test_observe_product_ci_runtime_gate_from_github.py",
    "tests/unit/test_product_runtime_reality.py",
    "tests/unit/test_release_ci_remote_green_evidence_contract.py",
    "tools/product/build_pr38_ci_runner_hygiene_child_pr_gate.py",
    "tools/product/github_workflow_trust_boundaries.py",
    "tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
    "tools/product/build_pr38_child_pr_verification_matrix.py",
    "tools/product/build_github_self_hosted_runner_host_preflight.py",
    "tools/product/build_product_ci_runtime_gate.py",
    "tools/product/build_product_image_smoke_preflight.py",
    "tools/product/build_release_ci_remote_green_receipt.py",
    "tools/product/observe_product_ci_runtime_gate_from_github.py",
    "tools/product/release_ci_remote_green_evidence_contract.py",
]

REQUIRED_FOCUSED_TEST_TOKENS = [
    "tests/unit/test_ai_design_kiro_wrapper_contract.py",
    "tests/unit/test_api_worker_deploy_artifacts.py",
    "tests/unit/test_build_github_self_hosted_runner_host_preflight.py",
    "tests/unit/test_build_product_ci_runtime_gate.py",
    "tests/unit/test_build_product_image_smoke_preflight.py",
    "tests/unit/test_build_release_ci_remote_green_receipt.py",
    "tests/unit/test_github_workflow_trust_boundaries.py",
    "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py",
    "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
    "tests/unit/test_build_pr38_child_pr_verification_matrix.py",
    "tests/unit/test_observe_product_ci_runtime_gate_from_github.py",
    "tests/unit/test_release_ci_remote_green_evidence_contract.py",
    "tests/unit/test_product_runtime_reality.py",
]

REQUIRED_PATCH_TOKENS = {
    "pull_request_hosted_runner": "runs-on: ubuntu-latest",
    "trusted_product_image_job": "product-image-build-smoke-trusted",
    "checkout_clean_true": "clean: true",
    "checkout_credentials_disabled": "persist-credentials: false",
    "checkout_subdir_path": "path: product-ci-checkout",
    "checkout_subdir_working_directory": "working-directory: product-ci-checkout",
    "runner_temp_artifact_upload_path": "${{ runner.temp }}/product-image-build-",
    "release_ci_checkout_subdir_contract": "checkout_subdir_isolated",
    "runner_temp_output_dir": "${{ runner.temp }}/product-image-",
    "workflow_policy_test": "test_github_workflow_trust_boundaries.py",
    "container_uid_gid_export": 'PRODUCT_IMAGE_CONTAINER_UID_GID="$(id -u):$(id -g)"',
    "container_output_dirs_writable": "chmod -R a+rwX logs runs",
    "ownership_normalizer": "normalize_product_image_smoke_artifact_ownership.sh",
    "default_temp_runner_dir": 'DEFAULT_RUNNER_SMOKE_DIR="${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts"',
    "workspace_runner_dir_guard": "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR",
    "uid_gid_invalid_guard": "container_uid_gid_invalid",
    "uid_gid_root_guard": "container_uid_gid_root",
    "uid_gid_not_host_guard": "container_uid_gid_not_host",
    "runner_hygiene_schema": "product_image_runner_hygiene_v1",
    "ai_verify_unique_kiro_prompt": "mktemp .betelgeuze/ai_verify_kiro_design_prompt",
    "remote_rerun_preflight": "build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
    "github_runtime_observer": "observe_product_ci_runtime_gate_from_github.py",
    "host_runner_workspace_cleanup_command": "runner_workspace_cleanup_command",
}

VERIFICATION_MATRIX_SOURCE_PATH = "tools/product/build_pr38_child_pr_verification_matrix.py"
PROHIBITED_VERIFICATION_MATRIX_IMPORT_TOKENS = [
    "from tools.product.build_pr38_split_acceptance_packet import",
    "import tools.product.build_pr38_split_acceptance_packet",
]

RUNNER_TEMP_ARTIFACT_UPLOAD_GLOB = (
    "${{ runner.temp }}/product-image-"
)
WORKSPACE_ARTIFACT_UPLOAD_GLOB = "runs/product_image_smoke_runner_artifacts/**"
RUNNER_TEMP_ARTIFACT_UPLOAD_COUNT_GUARD = (
    'workflow.count("${{ runner.temp }}/product-image-") >= 2'
)

CLAIM_BOUNDARY = (
    "PR #38 CI runner hygiene child-PR gate only; it proves local first-slice "
    "ordering, patch coverage, runner-hygiene remediation evidence, and fail-closed "
    "handoff status. It does not create branches, stage, commit, push, open PRs, "
    "rerun GitHub Actions, mark remote CI green, promote product claims, or mutate "
    "external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path: Path, *, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows_by_slice(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    return {
        _text(row.get("slice_id")): row
        for row in rows
        if isinstance(row, dict) and _text(row.get("slice_id"))
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _git_output(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_dirty_required_patch_files(root: Path) -> list[dict[str, str]]:
    output = _git_output(
        root,
        "status",
        "--porcelain=v1",
        "--",
        *REQUIRED_PATCH_FILES,
    )
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2].strip() or line[:2]
        path = line[2:].lstrip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1]
        rows.append({"status": status, "path": path})
    return rows


def _git_publication_state(root: Path) -> dict[str, Any]:
    head_sha = _git_output(root, "rev-parse", "HEAD")
    current_branch = _git_output(root, "branch", "--show-current")
    upstream_ref = _git_output(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    upstream_sha = _git_output(root, "rev-parse", upstream_ref) if upstream_ref else ""
    dirty_rows = _git_dirty_required_patch_files(root) if head_sha else []
    dirty_paths = [row["path"] for row in dirty_rows]
    head_matches_upstream = bool(head_sha and upstream_sha and head_sha == upstream_sha)
    required_patch_files_pending_commit = bool(dirty_paths)
    current_patch_published = bool(
        head_sha
        and upstream_sha
        and head_matches_upstream
        and not required_patch_files_pending_commit
    )
    return {
        "local_git_state_available": bool(head_sha),
        "local_git_current_branch": current_branch,
        "local_git_head_sha": head_sha,
        "local_git_upstream_ref": upstream_ref,
        "local_git_upstream_sha": upstream_sha,
        "local_git_head_matches_upstream": head_matches_upstream,
        "local_runner_hygiene_required_patch_file_dirty_count": len(dirty_rows),
        "local_runner_hygiene_required_patch_file_dirty_paths": dirty_paths,
        "local_runner_hygiene_required_patch_files_pending_commit": (
            required_patch_files_pending_commit
        ),
        "remote_ci_rerun_current_patch_published": current_patch_published,
        "remote_ci_rerun_after_push_required": not current_patch_published,
    }


def _check_row(
    *,
    check_id: str,
    passed: bool,
    observed: str,
    required: str,
    blocker: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "passed": passed,
        "observed": observed,
        "required": required,
        "blocker": "" if passed else blocker,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }


def build_pr38_ci_runner_hygiene_child_pr_gate(
    *,
    extraction_plan_json: str | Path = DEFAULT_EXTRACTION_PLAN_JSON,
    patch_bundle_json: str | Path = DEFAULT_PATCH_BUNDLE_JSON,
    apply_preflight_json: str | Path = DEFAULT_APPLY_PREFLIGHT_JSON,
    launch_command_pack_json: str | Path = DEFAULT_LAUNCH_COMMAND_PACK_JSON,
    product_image_preflight_json: str | Path = DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    product_ci_runtime_gate_json: str | Path = DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    plan_payload = _read_json(extraction_plan_json, root=root_path)
    bundle_payload = _read_json(patch_bundle_json, root=root_path)
    apply_payload = _read_json(apply_preflight_json, root=root_path)
    launch_payload = _read_json(launch_command_pack_json, root=root_path)
    image_payload = _read_json(product_image_preflight_json, root=root_path)
    runtime_payload = _read_json(product_ci_runtime_gate_json, root=root_path)

    plan_row = _rows_by_slice(plan_payload).get(SLICE_ID, {})
    bundle_row = _rows_by_slice(bundle_payload).get(SLICE_ID, {})
    apply_row = _rows_by_slice(apply_payload).get(SLICE_ID, {})
    launch_row = _rows_by_slice(launch_payload).get(SLICE_ID, {})
    launch_summary = _summary(launch_payload)
    image_summary = _summary(image_payload)
    runtime_summary = _summary(runtime_payload)
    git_state = _git_publication_state(root_path)
    runtime_blockers = _string_list(runtime_summary.get("blockers"))
    remote_ci_not_green_blockers = [
        blocker
        for blocker in runtime_blockers
        if blocker in {"product-api-worker_not_green", "product-image-smoke_not_green"}
    ]
    remote_ci_handoff_recorded = bool(
        runtime_summary.get("remote_ci_rerun_handoff_ready") is True
        or (
            runtime_summary.get("local_product_image_runner_hygiene_remediation_ready") is True
            and runtime_summary.get("runtime_gate_ready") is False
            and (
                runtime_summary.get("remote_workspace_cleanup_permission_blocked") is True
                or remote_ci_not_green_blockers
            )
        )
    )

    patch_path_text = _text(bundle_row.get("patch_path"))
    patch_text = _read_text(patch_path_text, root=root_path) if patch_path_text else ""
    verification_matrix_source_text = _read_text(
        VERIFICATION_MATRIX_SOURCE_PATH,
        root=root_path,
    )
    bundle_file_paths = set(_string_list(bundle_row.get("file_paths")))
    focused_test_command = _text(plan_row.get("focused_test_command") or launch_row.get("focused_test_command"))

    missing_patch_files = [
        path for path in REQUIRED_PATCH_FILES if path not in bundle_file_paths
    ]
    missing_focused_test_tokens = [
        token for token in REQUIRED_FOCUSED_TEST_TOKENS if token not in focused_test_command
    ]
    missing_patch_tokens = [
        token_id for token_id, token in REQUIRED_PATCH_TOKENS.items() if token not in patch_text
    ]
    verification_matrix_source_prohibited_import_tokens = [
        token
        for token in PROHIBITED_VERIFICATION_MATRIX_IMPORT_TOKENS
        if token in verification_matrix_source_text
    ]
    verification_matrix_patch_prohibited_import_tokens = [
        token
        for token in PROHIBITED_VERIFICATION_MATRIX_IMPORT_TOKENS
        if f"+{token}" in patch_text and f"-{token}" not in patch_text
    ]
    verification_matrix_self_contained_imports_ready = bool(
        verification_matrix_source_text
        and not verification_matrix_source_prohibited_import_tokens
        and not verification_matrix_patch_prohibited_import_tokens
    )
    runner_temp_artifact_upload_glob_count = patch_text.count(RUNNER_TEMP_ARTIFACT_UPLOAD_GLOB)
    runner_temp_artifact_upload_count_guard_present = (
        RUNNER_TEMP_ARTIFACT_UPLOAD_COUNT_GUARD in patch_text
    )
    build_runner_temp_artifact_upload_hunk_present = (
        "path: ${{ runner.temp }}/product-image-build-" in patch_text
    )
    workspace_artifact_upload_glob_added = (
        f"+            {WORKSPACE_ARTIFACT_UPLOAD_GLOB}" in patch_text
    )

    sequence_values = {
        "extraction_plan_sequence": int(plan_row.get("sequence") or 0),
        "patch_bundle_sequence": int(bundle_row.get("sequence") or 0),
        "apply_preflight_sequence": int(apply_row.get("sequence") or 0),
        "launch_command_pack_sequence": int(launch_row.get("sequence") or 0),
    }
    first_slice_ready = all(value == 1 for value in sequence_values.values())

    rows = [
        _check_row(
            check_id="ci_runner_hygiene_slice_present",
            passed=bool(plan_row and bundle_row and apply_row and launch_row),
            observed=f"plan={bool(plan_row)};bundle={bool(bundle_row)};apply={bool(apply_row)};launch={bool(launch_row)}",
            required="ci_runner_hygiene row exists in extraction plan, patch bundle, apply preflight, and launch pack",
            blocker="ci_runner_hygiene_slice_missing",
        ),
        _check_row(
            check_id="ci_runner_hygiene_first_child_pr",
            passed=first_slice_ready,
            observed=";".join(f"{key}={value}" for key, value in sequence_values.items()),
            required="all ci_runner_hygiene sequence values equal 1",
            blocker="ci_runner_hygiene_not_first_child_pr",
        ),
        _check_row(
            check_id="ci_runner_hygiene_branch_named",
            passed=_text(plan_row.get("draft_branch_name")) == "codex/pr38-ci-runner-hygiene",
            observed=_text(plan_row.get("draft_branch_name")),
            required="codex/pr38-ci-runner-hygiene",
            blocker="ci_runner_hygiene_branch_name_mismatch",
        ),
        _check_row(
            check_id="ci_runner_hygiene_patch_apply_passed",
            passed=bool(apply_row.get("apply_check_ready") is True),
            observed=_text(apply_row.get("apply_check_status")),
            required="apply_check_ready=true",
            blocker="ci_runner_hygiene_patch_apply_not_ready",
        ),
        _check_row(
            check_id="required_patch_files_present",
            passed=not missing_patch_files,
            observed="missing=" + ",".join(missing_patch_files),
            required="all required CI runner hygiene files assigned to ci_runner_hygiene patch",
            blocker="ci_runner_hygiene_required_patch_files_missing",
        ),
        _check_row(
            check_id="required_patch_tokens_present",
            passed=not missing_patch_tokens,
            observed="missing=" + ",".join(missing_patch_tokens),
            required="workflow cleanup, checkout clean:false, runner temp output, UID/GID pinning, ownership normalization, and fail-closed UID guards",
            blocker="ci_runner_hygiene_required_patch_tokens_missing",
        ),
        _check_row(
            check_id="verification_matrix_self_contained_imports",
            passed=verification_matrix_self_contained_imports_ready,
            observed=(
                f"source_present={bool(verification_matrix_source_text)};"
                "source_prohibited_imports="
                f"{','.join(verification_matrix_source_prohibited_import_tokens)};"
                "patch_prohibited_imports="
                f"{','.join(verification_matrix_patch_prohibited_import_tokens)}"
            ),
            required=(
                "ci_runner_hygiene verification matrix source and patch must not depend on "
                "cross-slice PR38 modules that are absent from the sequence-1 child patch"
            ),
            blocker="ci_runner_hygiene_verification_matrix_cross_slice_imports_present",
        ),
        _check_row(
            check_id="patch_bundle_runner_temp_artifact_upload_semantics",
            passed=bool(
                runner_temp_artifact_upload_glob_count >= 2
                and runner_temp_artifact_upload_count_guard_present
                and build_runner_temp_artifact_upload_hunk_present
                and not workspace_artifact_upload_glob_added
            ),
            observed=(
                f"runner_temp_upload_glob_count={runner_temp_artifact_upload_glob_count};"
                f"count_guard={runner_temp_artifact_upload_count_guard_present};"
                f"build_upload_hunk={build_runner_temp_artifact_upload_hunk_present};"
                f"workspace_upload_added={workspace_artifact_upload_glob_added}"
            ),
            required=(
                "ci_runner_hygiene patch uploads build and ROCm smoke artifacts from runner.temp, "
                "requires the preflight count guard, and does not add workspace smoke artifact uploads"
            ),
            blocker="ci_runner_hygiene_runner_temp_artifact_upload_semantics_missing",
        ),
        _check_row(
            check_id="focused_tests_cover_ci_runner_hygiene",
            passed=not missing_focused_test_tokens,
            observed="missing=" + ",".join(missing_focused_test_tokens),
            required="focused tests cover ai-verify wrapper concurrency, remote rerun preflight, GitHub runtime observation, product image preflight, runner host preflight, CI runtime gate, remote green receipt, evidence contract, and runtime reality",
            blocker="ci_runner_hygiene_focused_tests_incomplete",
        ),
        _check_row(
            check_id="local_product_image_runner_hygiene_ready",
            passed=bool(
                image_summary.get("receipt_runner_hygiene_ready") is True
                and image_summary.get("receipt_runner_smoke_dir_outside_workspace") is True
                and image_summary.get("receipt_container_output_uid_gid_pinned") is True
                and image_summary.get("receipt_container_output_uid_gid_matches_host") is True
                and image_summary.get("receipt_container_output_uid_gid_non_root") is True
                and image_summary.get("receipt_workspace_runner_smoke_dir_cleanup_ready") is True
            ),
            observed=_text(image_summary.get("status")) or "missing",
            required="product image preflight runner hygiene ready with outside-workspace smoke dir and non-root host UID/GID pinning",
            blocker="local_product_image_runner_hygiene_not_ready",
        ),
        _check_row(
            check_id="local_product_ci_runtime_gate_records_remote_blocker",
            passed=remote_ci_handoff_recorded,
            observed=(
                f"primary={_text(runtime_summary.get('primary_blocker')) or 'missing'};"
                f"blockers={','.join(runtime_blockers)}"
            ),
            required="local runner hygiene remediation ready while remote CI remains blocked until rerun",
            blocker="product_ci_runtime_gate_remote_blocker_not_recorded",
        ),
        _check_row(
            check_id="launch_pack_review_only",
            passed=bool(
                launch_summary.get("launch_command_pack_ready") is True
                and launch_summary.get("operator_branch_pr_launch_allowed_by_this_packet") is False
                and launch_summary.get("shell_pack_prints_commands_only") is True
                and launch_summary.get("post_push_remote_ci_branch_filter_uses_json_head_branch") is True
                and launch_summary.get("post_push_remote_ci_unsupported_branch_flag_present") is False
                and launch_summary.get("post_push_remote_ci_dispatch_guard_present") is True
                and launch_summary.get("post_push_remote_ci_remote_ref_guard_present") is True
                and launch_summary.get("post_push_remote_ci_uses_isolated_worktree") is True
                and launch_summary.get("post_push_remote_ci_bootstraps_local_evidence") is True
                and launch_summary.get("post_push_remote_ci_syncs_local_evidence_back") is True
                and launch_summary.get("post_push_remote_ci_rebuilds_root_release_gate") is True
                and launch_summary.get("post_push_remote_ci_waits_for_expected_head_sha") is True
                and launch_summary.get("post_push_remote_ci_requires_all_dispatched_runs_observed") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_launch_preconditions_ready") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet") is False
                and launch_summary.get("bootstrap_ci_runner_hygiene_isolated_worktree_launch_present") is True
                and launch_summary.get("bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree") is True
                and launch_summary.get("isolated_worktree_launch_preserves_current_worktree") is True
                and launch_summary.get("isolated_worktree_launch_uses_absolute_patch_and_body_paths") is True
                and int(launch_summary.get("isolated_worktree_launch_script_count") or 0)
                >= int(launch_summary.get("child_pr_count") or 0)
                and int(launch_summary.get("post_push_remote_ci_script_count") or 0)
                >= int(launch_summary.get("post_push_remote_ci_verification_slice_count") or 0)
                and launch_summary.get("launch_scripts_non_executable") is True
            ),
            observed=(
                f"launch_ready={launch_summary.get('launch_command_pack_ready')};"
                f"launch_allowed={launch_summary.get('operator_branch_pr_launch_allowed_by_this_packet')};"
                "json_head_branch_filter="
                f"{launch_summary.get('post_push_remote_ci_branch_filter_uses_json_head_branch')};"
                "unsupported_branch_flag="
                f"{launch_summary.get('post_push_remote_ci_unsupported_branch_flag_present')};"
                "dispatch_guard="
                f"{launch_summary.get('post_push_remote_ci_dispatch_guard_present')};"
                "remote_ref_guard="
                f"{launch_summary.get('post_push_remote_ci_remote_ref_guard_present')};"
                "uses_isolated_worktree="
                f"{launch_summary.get('post_push_remote_ci_uses_isolated_worktree')};"
                "bootstraps_local_evidence="
                f"{launch_summary.get('post_push_remote_ci_bootstraps_local_evidence')};"
                "syncs_local_evidence_back="
                f"{launch_summary.get('post_push_remote_ci_syncs_local_evidence_back')};"
                "rebuilds_root_release_gate="
                f"{launch_summary.get('post_push_remote_ci_rebuilds_root_release_gate')};"
                "waits_for_expected_head_sha="
                f"{launch_summary.get('post_push_remote_ci_waits_for_expected_head_sha')};"
                "requires_all_dispatched_runs_observed="
                f"{launch_summary.get('post_push_remote_ci_requires_all_dispatched_runs_observed')};"
                "bootstrap_ready="
                f"{launch_summary.get('bootstrap_ci_runner_hygiene_launch_preconditions_ready')};"
                "isolated_worktree_preserves_current="
                f"{launch_summary.get('isolated_worktree_launch_preserves_current_worktree')};"
                "isolated_worktree_absolute_paths="
                f"{launch_summary.get('isolated_worktree_launch_uses_absolute_patch_and_body_paths')};"
                "isolated_launch_scripts="
                f"{launch_summary.get('isolated_worktree_launch_script_count')};"
                "post_push_scripts="
                f"{launch_summary.get('post_push_remote_ci_script_count')};"
                "scripts_non_executable="
                f"{launch_summary.get('launch_scripts_non_executable')}"
            ),
            required="launch pack is ready for command review, guards remote workflow dispatch behind the preflight and a published remote ref check, copies required local .betelgeuze/runs evidence into the isolated ci_runner_hygiene worktree before post-push checks, syncs refreshed CI evidence back to the orchestration worktree, rebuilds the root release source-of-truth gate, uses gh run list JSON headBranch filtering, exposes the CI runner hygiene bootstrap blocker-clearance path, includes isolated worktree launch commands and non-executable launch scripts for dirty PR38 worktrees, and does not authorize branch/commit/push/PR launch",
            blocker="launch_pack_review_only_contract_not_ready",
        ),
    ]

    failed_rows = [row for row in rows if not row["passed"]]
    ready = not failed_rows
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "pr38_ci_runner_hygiene_child_pr_gate_ready"
            if ready
            else "blocked_pr38_ci_runner_hygiene_child_pr_gate"
        ),
        "ci_runner_hygiene_child_pr_gate_ready": ready,
        "ci_runner_hygiene_child_pr_review_ready": ready,
        "ci_runner_hygiene_remote_ci_verified": False,
        "ci_runner_hygiene_remote_ci_verification_required": True,
        "remote_ci_rerun_current_patch_verification_required": True,
        "operator_branch_pr_launch_allowed_by_this_gate": False,
        "external_state_mutated": False,
        "execution_enabled": False,
        "claim_promotion_allowed": False,
        **git_state,
        "slice_id": SLICE_ID,
        "sequence": int(plan_row.get("sequence") or 0),
        "draft_branch_name": _text(plan_row.get("draft_branch_name")),
        "patch_path": patch_path_text,
        "patch_sha256": _text(bundle_row.get("patch_sha256")),
        "changed_file_count": int(bundle_row.get("changed_file_count") or 0),
        "required_patch_file_count": len(REQUIRED_PATCH_FILES),
        "missing_required_patch_file_count": len(missing_patch_files),
        "missing_required_patch_files": missing_patch_files,
        "required_patch_token_count": len(REQUIRED_PATCH_TOKENS),
        "missing_required_patch_token_count": len(missing_patch_tokens),
        "missing_required_patch_tokens": missing_patch_tokens,
        "verification_matrix_source_path": VERIFICATION_MATRIX_SOURCE_PATH,
        "verification_matrix_self_contained_imports_ready": (
            verification_matrix_self_contained_imports_ready
        ),
        "verification_matrix_source_prohibited_import_count": len(
            verification_matrix_source_prohibited_import_tokens
        ),
        "verification_matrix_source_prohibited_import_tokens": (
            verification_matrix_source_prohibited_import_tokens
        ),
        "verification_matrix_patch_prohibited_import_count": len(
            verification_matrix_patch_prohibited_import_tokens
        ),
        "verification_matrix_patch_prohibited_import_tokens": (
            verification_matrix_patch_prohibited_import_tokens
        ),
        "patch_runner_temp_artifact_upload_glob_count": runner_temp_artifact_upload_glob_count,
        "patch_runner_temp_artifact_upload_count_guard_present": runner_temp_artifact_upload_count_guard_present,
        "patch_build_runner_temp_artifact_upload_hunk_present": build_runner_temp_artifact_upload_hunk_present,
        "patch_workspace_artifact_upload_glob_added": workspace_artifact_upload_glob_added,
        "required_focused_test_token_count": len(REQUIRED_FOCUSED_TEST_TOKENS),
        "missing_focused_test_token_count": len(missing_focused_test_tokens),
        "missing_focused_test_tokens": missing_focused_test_tokens,
        "focused_test_command": focused_test_command,
        "local_product_image_runner_hygiene_ready": bool(
            image_summary.get("receipt_runner_hygiene_ready") is True
        ),
        "local_product_image_runner_smoke_dir_outside_workspace": bool(
            image_summary.get("receipt_runner_smoke_dir_outside_workspace") is True
        ),
        "local_product_image_container_output_uid_gid_pinned": bool(
            image_summary.get("receipt_container_output_uid_gid_pinned") is True
        ),
        "local_product_image_container_output_uid_gid_matches_host": bool(
            image_summary.get("receipt_container_output_uid_gid_matches_host") is True
        ),
        "local_product_image_container_output_uid_gid_non_root": bool(
            image_summary.get("receipt_container_output_uid_gid_non_root") is True
        ),
        "product_ci_runtime_gate_status": _text(runtime_summary.get("status")) or "missing",
        "product_ci_runtime_gate_ready": bool(runtime_summary.get("runtime_gate_ready") is True),
        "product_ci_runtime_primary_blocker": _text(runtime_summary.get("primary_blocker")),
        "product_ci_runtime_blockers": runtime_blockers,
        "product_ci_runtime_remote_ci_not_green_blockers": remote_ci_not_green_blockers,
        "product_ci_runtime_remote_ci_handoff_recorded": remote_ci_handoff_recorded,
        "product_ci_runtime_remote_ci_rerun_handoff_ready": bool(
            runtime_summary.get("remote_ci_rerun_handoff_ready") is True
        ),
        "product_ci_runtime_remote_ci_failure_class": _text(
            runtime_summary.get("remote_ci_failure_class")
        ),
        "local_product_image_runner_hygiene_remediation_ready": bool(
            runtime_summary.get("local_product_image_runner_hygiene_remediation_ready") is True
        ),
        "remote_workspace_cleanup_permission_blocked": bool(
            runtime_summary.get("remote_workspace_cleanup_permission_blocked") is True
        ),
        "launch_command_pack_ready": bool(launch_summary.get("launch_command_pack_ready") is True),
        "launch_pack_prints_commands_only": bool(
            launch_summary.get("shell_pack_prints_commands_only") is True
        ),
        "launch_pack_post_push_remote_ci_branch_filter_uses_json_head_branch": bool(
            launch_summary.get("post_push_remote_ci_branch_filter_uses_json_head_branch") is True
        ),
        "launch_pack_post_push_remote_ci_dispatch_guard_present": bool(
            launch_summary.get("post_push_remote_ci_dispatch_guard_present") is True
        ),
        "launch_pack_post_push_remote_ci_remote_ref_guard_present": bool(
            launch_summary.get("post_push_remote_ci_remote_ref_guard_present") is True
        ),
        "launch_pack_post_push_remote_ci_uses_isolated_worktree": bool(
            launch_summary.get("post_push_remote_ci_uses_isolated_worktree") is True
        ),
        "launch_pack_post_push_remote_ci_bootstraps_local_evidence": bool(
            launch_summary.get("post_push_remote_ci_bootstraps_local_evidence") is True
        ),
        "launch_pack_post_push_remote_ci_syncs_local_evidence_back": bool(
            launch_summary.get("post_push_remote_ci_syncs_local_evidence_back") is True
        ),
        "launch_pack_post_push_remote_ci_rebuilds_root_release_gate": bool(
            launch_summary.get("post_push_remote_ci_rebuilds_root_release_gate") is True
        ),
        "launch_pack_post_push_remote_ci_waits_for_expected_head_sha": bool(
            launch_summary.get("post_push_remote_ci_waits_for_expected_head_sha") is True
        ),
        "launch_pack_post_push_remote_ci_requires_all_dispatched_runs_observed": bool(
            launch_summary.get("post_push_remote_ci_requires_all_dispatched_runs_observed") is True
        ),
        "launch_pack_post_push_remote_ci_unsupported_branch_flag_present": bool(
            launch_summary.get("post_push_remote_ci_unsupported_branch_flag_present") is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present"
            )
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present"
            )
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree"
            )
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence"
            )
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back"
            )
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate"
            )
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path": bool(
            launch_summary.get("bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path") is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_launch_preconditions_ready": bool(
            launch_summary.get("bootstrap_ci_runner_hygiene_launch_preconditions_ready") is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_operator_launch_allowed": bool(
            launch_summary.get("bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet") is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_launch_present": bool(
            launch_summary.get("bootstrap_ci_runner_hygiene_isolated_worktree_launch_present")
            is True
        ),
        "launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree": bool(
            launch_summary.get(
                "bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree"
            )
            is True
        ),
        "launch_pack_isolated_worktree_launch_script_count": int(
            launch_summary.get("isolated_worktree_launch_script_count") or 0
        ),
        "launch_pack_post_push_remote_ci_script_count": int(
            launch_summary.get("post_push_remote_ci_script_count") or 0
        ),
        "launch_pack_launch_scripts_non_executable": bool(
            launch_summary.get("launch_scripts_non_executable") is True
        ),
        "launch_pack_isolated_worktree_launch_preserves_current_worktree": bool(
            launch_summary.get("isolated_worktree_launch_preserves_current_worktree")
            is True
        ),
        "launch_pack_isolated_worktree_launch_uses_absolute_patch_and_body_paths": bool(
            launch_summary.get("isolated_worktree_launch_uses_absolute_patch_and_body_paths")
            is True
        ),
        "launch_pack_isolated_worktree_root": _text(
            launch_summary.get("isolated_worktree_root")
        ),
        "launch_pack_branch_pr_launch_allowed": bool(
            launch_summary.get("operator_branch_pr_launch_allowed_by_this_packet") is True
        ),
        "check_count": len(rows),
        "pass_count": len(rows) - len(failed_rows),
        "fail_count": len(failed_rows),
        "blocker_count": len(failed_rows),
        "blockers": [row["blocker"] for row in failed_rows],
        "primary_blocker": failed_rows[0]["blocker"] if failed_rows else "",
        "next_required_step": (
            (
                "Commit and push the local CI runner hygiene patch before rerunning product-api-worker and product-image-smoke; current remote runs cannot validate uncommitted local workflow/script changes."
                if git_state["remote_ci_rerun_after_push_required"]
                else "Use this as the first child-PR review gate; after human approval and split acceptance clearance, launch ci_runner_hygiene first, rerun the remote product-api-worker and product-image-smoke workflows, then rebuild product_ci_runtime_gate."
            )
            if ready
            else "Repair the CI runner hygiene split artifacts before treating the first child PR as ready for review."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# PR #38 CI Runner Hygiene Child PR Gate",
        "",
        f"- status: `{summary['status']}`",
        f"- ci_runner_hygiene_child_pr_gate_ready: `{summary['ci_runner_hygiene_child_pr_gate_ready']}`",
        f"- ci_runner_hygiene_child_pr_review_ready: `{summary['ci_runner_hygiene_child_pr_review_ready']}`",
        f"- ci_runner_hygiene_remote_ci_verified: `{summary['ci_runner_hygiene_remote_ci_verified']}`",
        f"- remote_ci_rerun_after_push_required: `{summary['remote_ci_rerun_after_push_required']}`",
        f"- remote_ci_rerun_current_patch_published: `{summary['remote_ci_rerun_current_patch_published']}`",
        f"- local_git_head_sha: `{summary['local_git_head_sha'] or '-'}`",
        f"- local_git_upstream_ref: `{summary['local_git_upstream_ref'] or '-'}`",
        f"- local_git_upstream_sha: `{summary['local_git_upstream_sha'] or '-'}`",
        f"- local_git_head_matches_upstream: `{summary['local_git_head_matches_upstream']}`",
        f"- local_runner_hygiene_required_patch_file_dirty_count: `{summary['local_runner_hygiene_required_patch_file_dirty_count']}`",
        f"- operator_branch_pr_launch_allowed_by_this_gate: `{summary['operator_branch_pr_launch_allowed_by_this_gate']}`",
        f"- patch_runner_temp_artifact_upload_glob_count: `{summary['patch_runner_temp_artifact_upload_glob_count']}`",
        f"- patch_runner_temp_artifact_upload_count_guard_present: `{summary['patch_runner_temp_artifact_upload_count_guard_present']}`",
        f"- patch_build_runner_temp_artifact_upload_hunk_present: `{summary['patch_build_runner_temp_artifact_upload_hunk_present']}`",
        f"- patch_workspace_artifact_upload_glob_added: `{summary['patch_workspace_artifact_upload_glob_added']}`",
        f"- verification_matrix_self_contained_imports_ready: `{summary['verification_matrix_self_contained_imports_ready']}`",
        f"- verification_matrix_source_prohibited_import_count: `{summary['verification_matrix_source_prohibited_import_count']}`",
        f"- verification_matrix_patch_prohibited_import_count: `{summary['verification_matrix_patch_prohibited_import_count']}`",
        f"- launch_pack_post_push_remote_ci_dispatch_guard_present: `{summary['launch_pack_post_push_remote_ci_dispatch_guard_present']}`",
        f"- launch_pack_post_push_remote_ci_remote_ref_guard_present: `{summary['launch_pack_post_push_remote_ci_remote_ref_guard_present']}`",
        f"- launch_pack_post_push_remote_ci_uses_isolated_worktree: `{summary['launch_pack_post_push_remote_ci_uses_isolated_worktree']}`",
        f"- launch_pack_post_push_remote_ci_bootstraps_local_evidence: `{summary['launch_pack_post_push_remote_ci_bootstraps_local_evidence']}`",
        f"- launch_pack_post_push_remote_ci_syncs_local_evidence_back: `{summary['launch_pack_post_push_remote_ci_syncs_local_evidence_back']}`",
        f"- launch_pack_post_push_remote_ci_rebuilds_root_release_gate: `{summary['launch_pack_post_push_remote_ci_rebuilds_root_release_gate']}`",
        f"- launch_pack_post_push_remote_ci_waits_for_expected_head_sha: `{summary['launch_pack_post_push_remote_ci_waits_for_expected_head_sha']}`",
        f"- launch_pack_post_push_remote_ci_requires_all_dispatched_runs_observed: `{summary['launch_pack_post_push_remote_ci_requires_all_dispatched_runs_observed']}`",
        f"- launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_launch_present: `{summary['launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_launch_present']}`",
        f"- launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree: `{summary['launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree']}`",
        f"- launch_pack_isolated_worktree_launch_script_count: `{summary['launch_pack_isolated_worktree_launch_script_count']}`",
        f"- launch_pack_post_push_remote_ci_script_count: `{summary['launch_pack_post_push_remote_ci_script_count']}`",
        f"- launch_pack_launch_scripts_non_executable: `{summary['launch_pack_launch_scripts_non_executable']}`",
        f"- launch_pack_isolated_worktree_launch_preserves_current_worktree: `{summary['launch_pack_isolated_worktree_launch_preserves_current_worktree']}`",
        f"- launch_pack_isolated_worktree_launch_uses_absolute_patch_and_body_paths: `{summary['launch_pack_isolated_worktree_launch_uses_absolute_patch_and_body_paths']}`",
        f"- draft_branch_name: `{summary['draft_branch_name']}`",
        f"- patch_path: `{summary['patch_path']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker: `{summary['primary_blocker'] or '-'}`",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            summary["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build PR #38 CI runner hygiene child PR gate.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--extraction-plan-json", default=DEFAULT_EXTRACTION_PLAN_JSON)
    parser.add_argument("--patch-bundle-json", default=DEFAULT_PATCH_BUNDLE_JSON)
    parser.add_argument("--apply-preflight-json", default=DEFAULT_APPLY_PREFLIGHT_JSON)
    parser.add_argument("--launch-command-pack-json", default=DEFAULT_LAUNCH_COMMAND_PACK_JSON)
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--product-ci-runtime-gate-json", default=DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=args.extraction_plan_json,
        patch_bundle_json=args.patch_bundle_json,
        apply_preflight_json=args.apply_preflight_json,
        launch_command_pack_json=args.launch_command_pack_json,
        product_image_preflight_json=args.product_image_preflight_json,
        product_ci_runtime_gate_json=args.product_ci_runtime_gate_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["ci_runner_hygiene_child_pr_gate_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
