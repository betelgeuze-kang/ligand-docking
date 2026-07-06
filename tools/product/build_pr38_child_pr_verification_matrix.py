#!/usr/bin/env python3
"""Build the PR #38 child-PR verification matrix.

This read-only matrix turns the split acceptance packet into per-child-PR
verification requirements: focused tests, ai-verify, product-mode expectations,
hunk review, and claim-boundary review. It does not run tests, create branches,
stage, commit, push, post comments, merge PR #38, or promote claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACCEPTANCE_PACKET_JSON = ".betelgeuze/pr38_split_acceptance_packet_current.json"
DEFAULT_LAUNCH_COMMAND_PACK_JSON = ".betelgeuze/pr38_child_pr_launch_command_pack_current.json"
DEFAULT_CI_RUNNER_HYGIENE_REMOTE_RERUN_PREFLIGHT_JSON = (
    ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.json"
)
DEFAULT_OUT_JSON = ".betelgeuze/pr38_child_pr_verification_matrix_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_child_pr_verification_matrix_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_child_pr_verification_matrix_current.md"

PACKET_TYPE = "pr38_child_pr_verification_matrix"
SCHEMA_VERSION = "pr38_child_pr_verification_matrix_v1"
MINIMUM_CHILD_PR_COUNT = 5

AI_VERIFY_COMMAND = "./scripts/ai-verify.sh"
PRODUCT_VERIFY_COMMAND = "AI_VERIFY_MODE=product ./scripts/ai-verify.sh"
KNOWN_PRODUCT_MODE_BLOCKERS: list[str] = []
PRODUCT_MODE_PASS_RESULT = "pass_product_smoke_claim_boundaries_locked"
PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS = [
    "product_image_workspace_artifact_root_allowed=false",
    "container_smoke_root_owned_artifacts_allowed=false",
    "paid_pilot_wording_allowed=false",
    "developer_preview_exit_allowed_without_clean_checkout=false",
    "api_operator_cockpit_mutation_allowed=false",
    "public_benchmark_claim_allowed=false",
    "competition_benchmark_competition_ligand_commercial_claim_allowed=false",
    "gpcr_broad_claim_allowed=false",
    "pocketmd_lite_claim_allowed=false",
    "f2g_f2h_placeholder_surface_creation_allowed=false",
    "f2h_continuation_allowed=false",
]

PRODUCT_MODE_REQUIRED_SLICE_IDS = {
    "ci_runner_hygiene",
    "f2g_f2h_preflight",
    "public_benchmark_phase2",
    "gpcr_hard_decoy_closure",
    "pocketmd_lite_recovery",
    "developer_preview_reproducibility",
    "api_operator_cockpit",
    "source_of_truth_refresh",
}

CLAIM_BOUNDARY = (
    "PR #38 child-PR verification matrix only; it records required local verification and claim-boundary checks "
    "for already-prepared split slices. It does not create branches, stage, commit, push, post comments, merge "
    "PR #38, mark product-mode readiness green, promote paid-pilot wording, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
    "patches_applied": False,
    "branches_created": False,
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]
    return []


def _rows_by_slice(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    return {
        _text(row.get("slice_id")): row
        for row in rows
        if isinstance(row, dict) and _text(row.get("slice_id"))
    }


def _launch_command_pack_safe(summary: dict[str, Any]) -> bool:
    return bool(
        summary.get("operator_launch_requires_human_approval") is True
        and summary.get("shell_pack_prints_commands_only") is True
        and summary.get("post_push_remote_ci_waits_for_expected_head_sha") is True
        and summary.get("post_push_remote_ci_requires_all_dispatched_runs_observed") is True
        and summary.get("execution_enabled") is False
        and summary.get("external_state_mutated") is False
        and summary.get("branches_created") is False
        and summary.get("commits_created") is False
        and summary.get("pushes_executed") is False
        and summary.get("pull_requests_created") is False
        and summary.get("claim_promotion_allowed") is False
    )


def _expected_draft_branch_name(slice_id: str, row: dict[str, Any] | None = None) -> str:
    explicit = _text((row or {}).get("draft_branch_name"))
    if explicit:
        return explicit
    return f"codex/pr38-{slice_id.replace('_', '-')}" if slice_id else ""


def _launch_row_blockers(
    row: dict[str, Any],
    *,
    slice_id: str,
    expected_branch_name: str,
) -> list[str]:
    if not row:
        return ["launch_command_pack_row_missing"]
    blockers: list[str] = []
    draft_branch_name = _text(row.get("draft_branch_name"))
    if not draft_branch_name:
        blockers.append("launch_command_pack_draft_branch_missing")
    elif expected_branch_name and draft_branch_name != expected_branch_name:
        blockers.append(
            f"launch_command_pack_draft_branch_mismatch:{draft_branch_name}!={expected_branch_name}"
        )
    if not _text(row.get("draft_pr_title")):
        blockers.append("launch_command_pack_draft_pr_title_missing")
    if not _text(row.get("pr_body_path")):
        blockers.append("launch_command_pack_pr_body_missing")
    if not _text(row.get("patch_path")):
        blockers.append("launch_command_pack_patch_path_missing")
    if row.get("operator_launch_requires_human_approval") is not True:
        blockers.append("launch_command_pack_human_approval_not_required")
    if row.get("branch_commit_push_pr_mutation_required") is not True:
        blockers.append("launch_command_pack_mutation_requirement_not_declared")
    for field in (
        "execution_enabled",
        "external_state_mutated",
        "branches_created",
        "commits_created",
        "pushes_executed",
        "pull_requests_created",
        "claim_promotion_allowed",
    ):
        if row.get(field) is not False:
            blockers.append(f"launch_command_pack_{field}_not_false")
    return blockers


def build_pr38_child_pr_verification_matrix(
    *,
    acceptance_packet_json: str | Path = DEFAULT_ACCEPTANCE_PACKET_JSON,
    launch_command_pack_json: str | Path = DEFAULT_LAUNCH_COMMAND_PACK_JSON,
    ci_runner_hygiene_remote_rerun_preflight_json: str
    | Path = DEFAULT_CI_RUNNER_HYGIENE_REMOTE_RERUN_PREFLIGHT_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    acceptance_payload = _read_json(acceptance_packet_json, root=root_path)
    launch_payload = _read_json(launch_command_pack_json, root=root_path)
    ci_remote_preflight_payload = _read_json(
        ci_runner_hygiene_remote_rerun_preflight_json,
        root=root_path,
    )
    acceptance_summary = _summary(acceptance_payload)
    launch_summary = _summary(launch_payload)
    ci_remote_preflight_summary = _summary(ci_remote_preflight_payload)
    launch_rows = _rows_by_slice(launch_payload)
    ci_remote_preflight_present = bool(ci_remote_preflight_summary)
    ci_remote_preflight_ready = bool(
        ci_remote_preflight_summary.get("remote_rerun_preflight_ready") is True
        and ci_remote_preflight_summary.get("operator_remote_ci_dispatch_preconditions_ready")
        is True
    )
    ci_remote_preflight_blockers = _string_list(
        ci_remote_preflight_summary.get("blockers")
    )
    ci_remote_preflight_primary_blocker = _text(
        ci_remote_preflight_summary.get("primary_blocker")
    )
    ci_remote_preflight_next_required_step = _text(
        ci_remote_preflight_summary.get("next_required_step")
    )
    product_mode_expected_result = (
        _text(acceptance_summary.get("product_mode_expected_result")) or PRODUCT_MODE_PASS_RESULT
    )
    product_mode_expected_blockers = (
        _string_list(acceptance_summary.get("product_mode_expected_fail_closed_blockers"))
        or KNOWN_PRODUCT_MODE_BLOCKERS
    )
    product_mode_verification_ready = bool(
        acceptance_summary.get("product_mode_verification_ready") is True
        or (product_mode_expected_result == PRODUCT_MODE_PASS_RESULT and not product_mode_expected_blockers)
    )
    rows: list[dict[str, Any]] = []

    for row_in in _rows(acceptance_payload):
        slice_id = _text(row_in.get("slice_id"))
        launch_row = launch_rows.get(slice_id, {})
        focused_test_command = _text(row_in.get("focused_test_command"))
        claim_boundary = _text(row_in.get("claim_boundary"))
        product_mode_required = slice_id in PRODUCT_MODE_REQUIRED_SLICE_IDS
        blockers: list[str] = []
        if row_in.get("slice_acceptance_ready") is not True:
            blockers.append("slice_acceptance_not_ready")
        if not focused_test_command:
            blockers.append("focused_test_command_missing")
        if not claim_boundary:
            blockers.append("claim_boundary_missing")
        expected_draft_branch_name = _expected_draft_branch_name(slice_id, row_in)
        launch_blockers = _launch_row_blockers(
            launch_row,
            slice_id=slice_id,
            expected_branch_name=expected_draft_branch_name,
        )
        blockers.extend(launch_blockers)
        ci_remote_preflight_required = bool(
            slice_id == "ci_runner_hygiene" and ci_remote_preflight_present
        )
        if ci_remote_preflight_required and not ci_remote_preflight_ready:
            blockers.append("ci_runner_hygiene_remote_rerun_preflight_not_ready")
        rows.append(
            {
                "sequence": int(row_in.get("sequence") or len(rows) + 1),
                "slice_id": slice_id,
                "changed_file_count": int(row_in.get("changed_file_count") or 0),
                "integration_touchpoint_count": int(row_in.get("integration_touchpoint_count") or 0),
                "hunk_split_review_required": int(row_in.get("integration_touchpoint_count") or 0) > 0,
                "draft_branch_name": _text(launch_row.get("draft_branch_name")),
                "expected_draft_branch_name": expected_draft_branch_name,
                "draft_branch_name_matches_expected": _text(launch_row.get("draft_branch_name"))
                == expected_draft_branch_name,
                "draft_pr_title": _text(launch_row.get("draft_pr_title")),
                "pr_body_path": _text(launch_row.get("pr_body_path")),
                "launch_patch_path": _text(launch_row.get("patch_path")),
                "launch_command_pack_row_ready": not launch_blockers,
                "operator_launch_requires_human_approval": bool(
                    launch_row.get("operator_launch_requires_human_approval") is True
                ),
                "branch_commit_push_pr_mutation_required": bool(
                    launch_row.get("branch_commit_push_pr_mutation_required") is True
                ),
                "ci_runner_hygiene_remote_rerun_preflight_required": (
                    ci_remote_preflight_required
                ),
                "ci_runner_hygiene_remote_rerun_preflight_ready": bool(
                    ci_remote_preflight_required and ci_remote_preflight_ready
                ),
                "ci_runner_hygiene_remote_rerun_preflight_status": (
                    _text(ci_remote_preflight_summary.get("status"))
                    if ci_remote_preflight_required
                    else ""
                ),
                "ci_runner_hygiene_remote_rerun_preflight_blockers": (
                    ci_remote_preflight_blockers if ci_remote_preflight_required else []
                ),
                "ci_runner_hygiene_latest_remote_rerun_cannot_validate_local_patch": bool(
                    ci_remote_preflight_required
                    and ci_remote_preflight_summary.get(
                        "latest_remote_rerun_cannot_validate_local_patch"
                    )
                    is True
                ),
                "ci_runner_hygiene_latest_remote_ci_observed_checkout_clean_mode": (
                    _text(
                        ci_remote_preflight_summary.get(
                            "latest_remote_ci_observed_checkout_clean_mode"
                        )
                    )
                    if ci_remote_preflight_required
                    else ""
                ),
                "ci_runner_hygiene_latest_product_api_worker_run_id": (
                    _text(ci_remote_preflight_summary.get("latest_product_api_worker_run_id"))
                    if ci_remote_preflight_required
                    else ""
                ),
                "ci_runner_hygiene_latest_product_image_build_smoke_run_id": (
                    _text(
                        ci_remote_preflight_summary.get(
                            "latest_product_image_build_smoke_run_id"
                        )
                    )
                    if ci_remote_preflight_required
                    else ""
                ),
                "ci_runner_hygiene_latest_product_image_smoke_run_id": (
                    _text(ci_remote_preflight_summary.get("latest_product_image_smoke_run_id"))
                    if ci_remote_preflight_required
                    else ""
                ),
                "focused_test_required": True,
                "focused_test_command": focused_test_command,
                "ai_verify_required": True,
                "ai_verify_command": AI_VERIFY_COMMAND,
                "product_mode_required": product_mode_required,
                "product_mode_command": PRODUCT_VERIFY_COMMAND if product_mode_required else "",
                "product_mode_expected_result": (
                    product_mode_expected_result
                    if product_mode_required
                    else "not_required_for_this_slice"
                ),
                "product_mode_expected_blockers": product_mode_expected_blockers if product_mode_required else [],
                "product_mode_claim_boundary_expected_locks": (
                    PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS if product_mode_required else []
                ),
                "claim_boundary_review_required": True,
                "claim_boundary": claim_boundary,
                "paid_pilot_wording_allowed": False,
                "branch_commit_work_allowed_by_this_matrix": False,
                "verification_blockers": blockers,
                "child_pr_verification_matrix_ready": not blockers,
                **_READ_ONLY_FLAGS,
            }
        )

    blocked_rows = [row for row in rows if not row["child_pr_verification_matrix_ready"]]
    ci_remote_preflight_blocked = any(
        "ci_runner_hygiene_remote_rerun_preflight_not_ready"
        in row["verification_blockers"]
        for row in blocked_rows
    )
    branch_mismatch_rows = [
        row for row in rows if row["draft_branch_name_matches_expected"] is not True
    ]
    child_pr_rows_ready = bool(rows) and not blocked_rows
    minimum_child_pr_count = int(
        acceptance_summary.get("minimum_child_pr_count") or MINIMUM_CHILD_PR_COUNT
    )
    minimum_child_pr_count_met = (
        len(rows) >= minimum_child_pr_count
        and acceptance_summary.get("minimum_child_pr_count_met") is not False
    )
    upstream_acceptance_ready = acceptance_summary.get("split_acceptance_ready") is True
    launch_command_pack_ready = launch_summary.get("launch_command_pack_ready") is True
    launch_command_pack_safe_ready = _launch_command_pack_safe(launch_summary)
    launch_command_pack_alignment_ready = (
        int(launch_summary.get("child_pr_count") or 0) == len(rows)
        and int(launch_summary.get("body_file_count") or 0) == len(rows)
    )
    launch_command_pack_blockers: list[str] = []
    if not launch_command_pack_ready:
        observed_status = _text(launch_summary.get("status")) or "missing"
        launch_command_pack_blockers.append(f"launch_command_pack_not_ready:{observed_status}")
    if not launch_command_pack_alignment_ready:
        launch_command_pack_blockers.append("launch_command_pack_alignment_not_ready")
    if not launch_command_pack_safe_ready:
        launch_command_pack_blockers.append("launch_command_pack_safety_contract_not_ready")
    upstream_acceptance_blockers = (
        _string_list(acceptance_summary.get("blockers"))
        or _string_list(acceptance_summary.get("split_acceptance_blockers"))
    )
    if not minimum_child_pr_count_met:
        upstream_acceptance_blockers.append(
            f"minimum_child_pr_count_not_met:{len(rows)}<{minimum_child_pr_count}"
        )
    if not upstream_acceptance_ready and not upstream_acceptance_blockers:
        upstream_acceptance_blockers.append(
            f"split_acceptance_not_ready:{_text(acceptance_summary.get('status')) or 'missing'}"
        )
    row_blockers = [
        f"{row['slice_id']}:{blocker}"
        for row in blocked_rows
        for blocker in row["verification_blockers"]
    ]
    matrix_blockers = list(
        dict.fromkeys(
            [
                *upstream_acceptance_blockers,
                *launch_command_pack_blockers,
                *row_blockers,
            ]
        )
    )
    ready = bool(
        upstream_acceptance_ready
        and launch_command_pack_ready
        and launch_command_pack_safe_ready
        and launch_command_pack_alignment_ready
        and minimum_child_pr_count_met
        and child_pr_rows_ready
    )
    acceptance_next_required_step = _text(acceptance_summary.get("next_required_step"))
    if ready:
        next_required_step = (
            "After explicit human approval for branch/commit work, run each row's focused test command and "
            "ai-verify before child PR review; product-mode rows should pass smoke while claim locks remain false."
        )
    elif not blocked_rows and acceptance_summary.get("split_acceptance_ready") is not True:
        next_required_step = (
            acceptance_next_required_step
            or "Resolve PR #38 split acceptance blockers before branch extraction or review."
        )
    elif not blocked_rows and launch_command_pack_blockers:
        next_required_step = "Repair the PR #38 child PR launch command pack before branch extraction or review."
    elif ci_remote_preflight_blocked:
        next_required_step = (
            ci_remote_preflight_next_required_step
            or "Commit and push the ci_runner_hygiene child branch, then rerun the remote-rerun preflight before treating PR #38 child PRs as verified."
        )
    else:
        next_required_step = "Repair blocked verification rows before branch extraction or review."
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_child_pr_verification_matrix_ready" if ready else "blocked_pr38_child_pr_verification_matrix",
        "verification_matrix_ready": ready,
        "blocker_count": len(matrix_blockers),
        "blockers": matrix_blockers,
        "primary_blocker": matrix_blockers[0] if matrix_blockers else "",
        "verification_matrix_blocker_count": len(matrix_blockers),
        "verification_matrix_blockers": matrix_blockers,
        "acceptance_packet_status": _text(acceptance_summary.get("status")) or "missing",
        "launch_command_pack_status": _text(launch_summary.get("status")) or "missing",
        "launch_command_pack_ready": launch_command_pack_ready,
        "launch_command_pack_blocker_count": len(launch_command_pack_blockers),
        "launch_command_pack_blockers": launch_command_pack_blockers,
        "launch_command_pack_child_pr_count": int(launch_summary.get("child_pr_count") or 0),
        "launch_command_pack_minimum_child_pr_count": int(
            launch_summary.get("minimum_child_pr_count") or 0
        ),
        "launch_command_pack_alignment_ready": launch_command_pack_alignment_ready,
        "launch_command_pack_safe_ready": launch_command_pack_safe_ready,
        "launch_command_pack_operator_launch_requires_human_approval": bool(
            launch_summary.get("operator_launch_requires_human_approval") is True
        ),
        "launch_command_pack_branch_commit_push_pr_mutation_required": bool(
            launch_summary.get("branch_commit_push_pr_mutation_required") is True
        ),
        "launch_command_pack_shell_prints_commands_only": bool(
            launch_summary.get("shell_pack_prints_commands_only") is True
        ),
        "launch_command_pack_post_push_remote_ci_waits_for_expected_head_sha": bool(
            launch_summary.get("post_push_remote_ci_waits_for_expected_head_sha") is True
        ),
        "launch_command_pack_post_push_remote_ci_requires_all_dispatched_runs_observed": bool(
            launch_summary.get("post_push_remote_ci_requires_all_dispatched_runs_observed") is True
        ),
        "launch_command_pack_branches_created": bool(launch_summary.get("branches_created") is True),
        "launch_command_pack_pull_requests_created": bool(
            launch_summary.get("pull_requests_created") is True
        ),
        "split_acceptance_ready": upstream_acceptance_ready,
        "upstream_acceptance_ready": upstream_acceptance_ready,
        "upstream_acceptance_blocker_count": len(upstream_acceptance_blockers),
        "upstream_acceptance_blockers": upstream_acceptance_blockers,
        "child_pr_rows_ready": child_pr_rows_ready,
        "all_child_prs_ready": child_pr_rows_ready,
        "child_pr_count": len(rows),
        "minimum_child_pr_count": minimum_child_pr_count,
        "minimum_child_pr_count_met": minimum_child_pr_count_met,
        "ready_child_pr_count": sum(1 for row in rows if row["child_pr_verification_matrix_ready"]),
        "blocked_child_pr_count": len(blocked_rows),
        "blocked_slice_ids": [row["slice_id"] for row in blocked_rows],
        "draft_branch_name_mismatch_count": len(branch_mismatch_rows),
        "draft_branch_name_mismatch_slice_ids": [
            row["slice_id"] for row in branch_mismatch_rows
        ],
        "ci_runner_hygiene_remote_rerun_preflight_json": str(
            ci_runner_hygiene_remote_rerun_preflight_json
        ),
        "ci_runner_hygiene_remote_rerun_preflight_present": (
            ci_remote_preflight_present
        ),
        "ci_runner_hygiene_remote_rerun_preflight_status": _text(
            ci_remote_preflight_summary.get("status")
        ),
        "ci_runner_hygiene_remote_rerun_preflight_ready": (
            ci_remote_preflight_ready
        ),
        "ci_runner_hygiene_remote_rerun_preflight_primary_blocker": (
            ci_remote_preflight_primary_blocker
        ),
        "ci_runner_hygiene_remote_rerun_preflight_blockers": (
            ci_remote_preflight_blockers
        ),
        "ci_runner_hygiene_remote_rerun_preflight_blocker_count": len(
            ci_remote_preflight_blockers
        ),
        "ci_runner_hygiene_remote_rerun_current_patch_published": bool(
            ci_remote_preflight_summary.get("remote_ci_rerun_current_patch_published")
            is True
        ),
        "ci_runner_hygiene_remote_rerun_after_push_required": bool(
            ci_remote_preflight_summary.get("remote_ci_rerun_after_push_required")
            is True
        ),
        "ci_runner_hygiene_latest_remote_rerun_cannot_validate_local_patch": bool(
            ci_remote_preflight_summary.get(
                "latest_remote_rerun_cannot_validate_local_patch"
            )
            is True
        ),
        "ci_runner_hygiene_latest_remote_ci_observed_checkout_clean_mode": _text(
            ci_remote_preflight_summary.get(
                "latest_remote_ci_observed_checkout_clean_mode"
            )
        ),
        "ci_runner_hygiene_latest_product_api_worker_run_id": _text(
            ci_remote_preflight_summary.get("latest_product_api_worker_run_id")
        ),
        "ci_runner_hygiene_latest_product_image_build_smoke_run_id": _text(
            ci_remote_preflight_summary.get("latest_product_image_build_smoke_run_id")
        ),
        "ci_runner_hygiene_latest_product_image_smoke_run_id": _text(
            ci_remote_preflight_summary.get("latest_product_image_smoke_run_id")
        ),
        "ci_runner_hygiene_remote_rerun_preflight_next_required_step": (
            ci_remote_preflight_next_required_step
        ),
        "focused_test_required_count": len(rows),
        "ai_verify_required_count": len(rows),
        "product_mode_required_count": sum(1 for row in rows if row["product_mode_required"]),
        "hunk_split_review_required_count": sum(1 for row in rows if row["hunk_split_review_required"]),
        "claim_boundary_review_required_count": len(rows),
        "product_mode_verification_ready": product_mode_verification_ready,
        "product_mode_expected_fail_closed_blockers": product_mode_expected_blockers,
        "product_mode_expected_result": product_mode_expected_result,
        "product_mode_claim_boundary_expected_locks": PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS,
        "paid_pilot_wording_allowed": False,
        "branch_commit_work_allowed_by_this_matrix": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# PR #38 Child PR Verification Matrix",
        "",
        f"- status: `{s['status']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- primary_blocker: `{s['primary_blocker'] or '-'}`",
        f"- acceptance_packet_status: `{s['acceptance_packet_status']}`",
        f"- launch_command_pack_status: `{s['launch_command_pack_status']}`",
        f"- launch_command_pack_ready: `{s['launch_command_pack_ready']}`",
        f"- launch_command_pack_safe_ready: `{s['launch_command_pack_safe_ready']}`",
        f"- launch_command_pack_shell_prints_commands_only: `{s['launch_command_pack_shell_prints_commands_only']}`",
        f"- launch_command_pack_post_push_remote_ci_waits_for_expected_head_sha: `{s['launch_command_pack_post_push_remote_ci_waits_for_expected_head_sha']}`",
        f"- launch_command_pack_post_push_remote_ci_requires_all_dispatched_runs_observed: `{s['launch_command_pack_post_push_remote_ci_requires_all_dispatched_runs_observed']}`",
        f"- upstream_acceptance_ready: `{s['upstream_acceptance_ready']}`",
        f"- upstream_acceptance_blocker_count: `{s['upstream_acceptance_blocker_count']}`",
        f"- child_pr_rows_ready: `{s['child_pr_rows_ready']}`",
        f"- child_pr_count: `{s['child_pr_count']}`",
        f"- minimum_child_pr_count: `{s['minimum_child_pr_count']}`",
        f"- minimum_child_pr_count_met: `{s['minimum_child_pr_count_met']}`",
        f"- draft_branch_name_mismatch_count: `{s['draft_branch_name_mismatch_count']}`",
        f"- ci_runner_hygiene_remote_rerun_preflight_present: `{s['ci_runner_hygiene_remote_rerun_preflight_present']}`",
        f"- ci_runner_hygiene_remote_rerun_preflight_ready: `{s['ci_runner_hygiene_remote_rerun_preflight_ready']}`",
        f"- ci_runner_hygiene_remote_rerun_preflight_status: `{s['ci_runner_hygiene_remote_rerun_preflight_status'] or '-'}`",
        f"- ci_runner_hygiene_remote_rerun_preflight_primary_blocker: `{s['ci_runner_hygiene_remote_rerun_preflight_primary_blocker'] or '-'}`",
        f"- ci_runner_hygiene_remote_rerun_preflight_blocker_count: `{s['ci_runner_hygiene_remote_rerun_preflight_blocker_count']}`",
        f"- ci_runner_hygiene_latest_remote_rerun_cannot_validate_local_patch: `{s['ci_runner_hygiene_latest_remote_rerun_cannot_validate_local_patch']}`",
        f"- ci_runner_hygiene_latest_remote_ci_observed_checkout_clean_mode: `{s['ci_runner_hygiene_latest_remote_ci_observed_checkout_clean_mode'] or '-'}`",
        f"- ci_runner_hygiene_latest_product_api_worker_run_id: `{s['ci_runner_hygiene_latest_product_api_worker_run_id'] or '-'}`",
        f"- ci_runner_hygiene_latest_product_image_build_smoke_run_id: `{s['ci_runner_hygiene_latest_product_image_build_smoke_run_id'] or '-'}`",
        f"- ci_runner_hygiene_latest_product_image_smoke_run_id: `{s['ci_runner_hygiene_latest_product_image_smoke_run_id'] or '-'}`",
        f"- focused_test_required_count: `{s['focused_test_required_count']}`",
        f"- ai_verify_required_count: `{s['ai_verify_required_count']}`",
        f"- product_mode_required_count: `{s['product_mode_required_count']}`",
        f"- paid_pilot_wording_allowed: `{s['paid_pilot_wording_allowed']}`",
        "",
        "| seq | slice | branch | expected branch | branch ok | focused test | ai-verify | product-mode | claim review |",
        "| --: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {seq} | `{slice_id}` | `{branch}` | `{expected_branch}` | `{branch_ok}` | "
            "`{focused}` | `{ai}` | `{product}` | `{claim}` |".format(
                seq=row["sequence"],
                slice_id=row["slice_id"],
                branch=row["draft_branch_name"],
                expected_branch=row["expected_draft_branch_name"],
                branch_ok=row["draft_branch_name_matches_expected"],
                focused=row["focused_test_required"],
                ai=row["ai_verify_required"],
                product=row["product_mode_required"],
                claim=row["claim_boundary_review_required"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PR #38 child-PR verification matrix.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--acceptance-packet-json", default=DEFAULT_ACCEPTANCE_PACKET_JSON)
    parser.add_argument("--launch-command-pack-json", default=DEFAULT_LAUNCH_COMMAND_PACK_JSON)
    parser.add_argument(
        "--ci-runner-hygiene-remote-rerun-preflight-json",
        default=DEFAULT_CI_RUNNER_HYGIENE_REMOTE_RERUN_PREFLIGHT_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=args.acceptance_packet_json,
        launch_command_pack_json=args.launch_command_pack_json,
        ci_runner_hygiene_remote_rerun_preflight_json=(
            args.ci_runner_hygiene_remote_rerun_preflight_json
        ),
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
