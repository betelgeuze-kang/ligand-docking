#!/usr/bin/env python3
"""Build a fail-closed preflight for rerunning PR #38 CI hygiene remote workflows.

The preflight refreshes the CI runner hygiene child gate in memory and verifies
that the current branch has published the runner-hygiene patch before an
operator runs the GitHub Actions workflow_dispatch commands. It writes local
evidence only; it does not dispatch workflows, push, create PRs, or mutate
external state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_pr38_ci_runner_hygiene_child_pr_gate import (
    DEFAULT_APPLY_PREFLIGHT_JSON,
    DEFAULT_EXTRACTION_PLAN_JSON,
    DEFAULT_LAUNCH_COMMAND_PACK_JSON,
    DEFAULT_PATCH_BUNDLE_JSON,
    DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON,
    DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    build_pr38_ci_runner_hygiene_child_pr_gate,
)


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.md"

PACKET_TYPE = "pr38_ci_runner_hygiene_remote_rerun_preflight"
SCHEMA_VERSION = "pr38_ci_runner_hygiene_remote_rerun_preflight_v1"

CLAIM_BOUNDARY = (
    "PR #38 CI runner hygiene remote-rerun preflight only; it verifies that the "
    "current local branch is the ci_runner_hygiene child branch, that required "
    "runner-hygiene files are committed and pushed to upstream, and that remote "
    "CI still needs verification. It does not dispatch workflows, create commits, "
    "push, open PRs, mark CI green, promote product claims, or mutate external state."
)


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


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


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
        "workflow_dispatch_executed": False,
        "operator_remote_ci_dispatch_allowed_by_this_preflight": False,
        "claim_promotion_allowed": False,
    }


def build_pr38_ci_runner_hygiene_remote_rerun_preflight(
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
    child_gate = build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=extraction_plan_json,
        patch_bundle_json=patch_bundle_json,
        apply_preflight_json=apply_preflight_json,
        launch_command_pack_json=launch_command_pack_json,
        product_image_preflight_json=product_image_preflight_json,
        product_ci_runtime_gate_json=product_ci_runtime_gate_json,
        root=root_path,
    )
    child_summary = child_gate.get("summary", {})
    product_ci_runtime_summary = _summary(
        _read_json(product_ci_runtime_gate_json, root=root_path)
    )
    expected_branch = _text(child_summary.get("draft_branch_name"))
    current_branch = _text(child_summary.get("local_git_current_branch"))
    upstream_ref = _text(child_summary.get("local_git_upstream_ref"))
    dirty_count = int(child_summary.get("local_runner_hygiene_required_patch_file_dirty_count") or 0)
    latest_remote_head_branch = _text(
        product_ci_runtime_summary.get("remote_ci_observed_head_branch")
    )
    latest_remote_head_matches_expected_branch = bool(
        expected_branch and latest_remote_head_branch == expected_branch
    )
    latest_remote_wrong_branch_for_child_rerun = bool(
        expected_branch
        and latest_remote_head_branch
        and latest_remote_head_branch != expected_branch
    )
    expected_upstream_ref = f"origin/{expected_branch}" if expected_branch else ""
    expected_ref_published_for_dispatch = bool(
        expected_branch
        and current_branch == expected_branch
        and upstream_ref == expected_upstream_ref
        and child_summary.get("local_git_head_matches_upstream") is True
        and child_summary.get("remote_ci_rerun_current_patch_published") is True
    )

    rows = [
        _check_row(
            check_id="ci_runner_hygiene_child_gate_ready",
            passed=bool(child_summary.get("ci_runner_hygiene_child_pr_gate_ready") is True),
            observed=_text(child_summary.get("status")) or "missing",
            required="ci runner hygiene child gate is ready",
            blocker="ci_runner_hygiene_child_gate_not_ready",
        ),
        _check_row(
            check_id="current_branch_is_ci_runner_hygiene_child",
            passed=bool(expected_branch and current_branch == expected_branch),
            observed=current_branch or "missing",
            required=expected_branch or "codex/pr38-ci-runner-hygiene",
            blocker="ci_runner_hygiene_wrong_branch_for_remote_rerun",
        ),
        _check_row(
            check_id="required_patch_files_committed",
            passed=dirty_count == 0,
            observed=str(dirty_count),
            required="0 dirty required runner-hygiene patch files",
            blocker="ci_runner_hygiene_required_patch_files_uncommitted",
        ),
        _check_row(
            check_id="current_head_published_to_upstream",
            passed=bool(
                upstream_ref
                and child_summary.get("local_git_head_matches_upstream") is True
                and child_summary.get("remote_ci_rerun_current_patch_published") is True
            ),
            observed=(
                f"upstream={upstream_ref or 'missing'};"
                f"head_matches_upstream={child_summary.get('local_git_head_matches_upstream')};"
                f"published={child_summary.get('remote_ci_rerun_current_patch_published')}"
            ),
            required="current HEAD matches upstream after git push -u origin ci_runner_hygiene branch",
            blocker="ci_runner_hygiene_patch_not_published_for_remote_rerun",
        ),
        _check_row(
            check_id="remote_ci_verification_still_required",
            passed=bool(
                child_summary.get("ci_runner_hygiene_remote_ci_verification_required") is True
                and child_summary.get("ci_runner_hygiene_remote_ci_verified") is False
            ),
            observed=(
                f"required={child_summary.get('ci_runner_hygiene_remote_ci_verification_required')};"
                f"verified={child_summary.get('ci_runner_hygiene_remote_ci_verified')}"
            ),
            required="remote CI verification required and not already marked green",
            blocker="ci_runner_hygiene_remote_ci_verification_state_unexpected",
        ),
    ]
    failed_rows = [row for row in rows if not row["passed"]]
    preconditions_ready = not failed_rows
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "pr38_ci_runner_hygiene_remote_rerun_preflight_ready"
            if preconditions_ready
            else "blocked_pr38_ci_runner_hygiene_remote_rerun_preflight"
        ),
        "remote_rerun_preflight_ready": preconditions_ready,
        "operator_remote_ci_dispatch_preconditions_ready": preconditions_ready,
        "operator_remote_ci_dispatch_allowed_by_this_preflight": False,
        "workflow_dispatch_executed": False,
        "external_state_mutated": False,
        "execution_enabled": False,
        "claim_promotion_allowed": False,
        "expected_branch": expected_branch,
        "expected_remote_ci_rerun_ref": (
            f"refs/heads/{expected_branch}" if expected_branch else ""
        ),
        "expected_remote_ci_rerun_upstream_ref": expected_upstream_ref,
        "expected_remote_ci_rerun_ref_published_for_dispatch": (
            expected_ref_published_for_dispatch
        ),
        "expected_remote_ci_rerun_ref_missing_for_dispatch": bool(
            expected_branch and not expected_ref_published_for_dispatch
        ),
        "gh_workflow_dispatch_422_expected_until_ref_published": bool(
            expected_branch and not expected_ref_published_for_dispatch
        ),
        "expected_remote_ci_rerun_ref_missing_required_action": (
            f"Create, commit, and push {expected_branch} before any gh workflow run --ref {expected_branch} command."
            if expected_branch and not expected_ref_published_for_dispatch
            else ""
        ),
        "local_git_current_branch": current_branch,
        "local_git_upstream_ref": upstream_ref,
        "local_git_head_sha": _text(child_summary.get("local_git_head_sha")),
        "local_git_upstream_sha": _text(child_summary.get("local_git_upstream_sha")),
        "local_git_head_matches_upstream": bool(
            child_summary.get("local_git_head_matches_upstream") is True
        ),
        "local_runner_hygiene_required_patch_file_dirty_count": dirty_count,
        "local_runner_hygiene_required_patch_file_dirty_paths": list(
            child_summary.get("local_runner_hygiene_required_patch_file_dirty_paths") or []
        ),
        "remote_ci_rerun_current_patch_published": bool(
            child_summary.get("remote_ci_rerun_current_patch_published") is True
        ),
        "remote_ci_rerun_after_push_required": bool(
            child_summary.get("remote_ci_rerun_after_push_required") is True
        ),
        "product_ci_runtime_gate_json": str(product_ci_runtime_gate_json),
        "product_ci_runtime_gate_status": _text(product_ci_runtime_summary.get("status")),
        "product_ci_runtime_primary_blocker": _text(
            product_ci_runtime_summary.get("primary_blocker")
        ),
        "product_ci_runtime_blockers": _string_list(
            product_ci_runtime_summary.get("blockers")
        ),
        "product_ci_runtime_remote_ci_failure_class": _text(
            product_ci_runtime_summary.get("remote_ci_failure_class")
        ),
        "product_ci_runtime_remote_workspace_cleanup_permission_blocked": bool(
            product_ci_runtime_summary.get("remote_workspace_cleanup_permission_blocked")
            is True
        ),
        "latest_product_api_worker_run_id": _text(
            product_ci_runtime_summary.get("product_api_worker_run_id")
        ),
        "latest_product_image_build_smoke_run_id": _text(
            product_ci_runtime_summary.get("product_image_build_smoke_run_id")
        ),
        "latest_product_image_smoke_run_id": _text(
            product_ci_runtime_summary.get("product_image_smoke_run_id")
        ),
        "latest_remote_ci_observed_head_sha": _text(
            product_ci_runtime_summary.get("remote_ci_observed_head_sha")
        ),
        "latest_remote_ci_observed_head_branch": _text(
            product_ci_runtime_summary.get("remote_ci_observed_head_branch")
        ),
        "expected_remote_ci_rerun_branch": expected_branch,
        "latest_remote_ci_observed_head_matches_expected_branch": (
            latest_remote_head_matches_expected_branch
        ),
        "latest_remote_ci_observed_wrong_branch_for_child_rerun": (
            latest_remote_wrong_branch_for_child_rerun
        ),
        "latest_remote_ci_observed_wrong_branch_required_action": (
            f"Rerun product-api-worker and product-image-smoke with --ref {expected_branch}"
            if latest_remote_wrong_branch_for_child_rerun
            else ""
        ),
        "latest_remote_ci_observed_checkout_clean_mode": _text(
            product_ci_runtime_summary.get("remote_ci_observed_checkout_clean_mode")
        ),
        "latest_remote_ci_observed_checkout_clean_true": bool(
            product_ci_runtime_summary.get("remote_ci_observed_checkout_clean_true")
            is True
        ),
        "latest_remote_ci_current_workflow_patch_unverified": bool(
            product_ci_runtime_summary.get("remote_ci_current_workflow_patch_unverified")
            is True
        ),
        "latest_remote_ci_rerun_after_workflow_publication_required": bool(
            product_ci_runtime_summary.get(
                "remote_ci_rerun_after_workflow_publication_required"
            )
            is True
        ),
        "latest_remote_ci_science_tests_unverified": bool(
            product_ci_runtime_summary.get("remote_ci_science_tests_unverified") is True
        ),
        "latest_remote_rerun_observed": bool(
            _text(product_ci_runtime_summary.get("product_api_worker_run_id"))
            or _text(product_ci_runtime_summary.get("product_image_build_smoke_run_id"))
            or _text(product_ci_runtime_summary.get("product_image_smoke_run_id"))
        ),
        "latest_remote_rerun_observed_head_matches_local_head": bool(
            _text(product_ci_runtime_summary.get("remote_ci_observed_head_sha"))
            and _text(product_ci_runtime_summary.get("remote_ci_observed_head_sha"))
            == _text(child_summary.get("local_git_head_sha"))
        ),
        "latest_remote_rerun_cannot_validate_local_patch": bool(
            product_ci_runtime_summary.get("remote_ci_current_workflow_patch_unverified")
            is True
            or child_summary.get("remote_ci_rerun_current_patch_published") is not True
        ),
        "latest_remote_rerun_cannot_validate_child_branch_patch": bool(
            latest_remote_wrong_branch_for_child_rerun
            or product_ci_runtime_summary.get("remote_ci_current_workflow_patch_unverified")
            is True
            or child_summary.get("remote_ci_rerun_current_patch_published") is not True
        ),
        "ci_runner_hygiene_child_pr_gate_status": _text(child_summary.get("status")),
        "ci_runner_hygiene_remote_ci_verified": bool(
            child_summary.get("ci_runner_hygiene_remote_ci_verified") is True
        ),
        "ci_runner_hygiene_remote_ci_verification_required": bool(
            child_summary.get("ci_runner_hygiene_remote_ci_verification_required") is True
        ),
        "check_count": len(rows),
        "pass_count": len(rows) - len(failed_rows),
        "fail_count": len(failed_rows),
        "blocker_count": len(failed_rows),
        "blockers": [row["blocker"] for row in failed_rows],
        "primary_blocker": failed_rows[0]["blocker"] if failed_rows else "",
        "next_required_step": (
            "Human owner may run the printed gh workflow commands for this child branch, then run the GitHub observer and rebuild the CI hygiene child gate."
            if preconditions_ready
            else "Commit and push the ci_runner_hygiene child branch, then rerun this preflight before any gh workflow run command."
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
        "# PR #38 CI Runner Hygiene Remote Rerun Preflight",
        "",
        f"- status: `{summary['status']}`",
        f"- remote_rerun_preflight_ready: `{summary['remote_rerun_preflight_ready']}`",
        f"- operator_remote_ci_dispatch_preconditions_ready: `{summary['operator_remote_ci_dispatch_preconditions_ready']}`",
        f"- operator_remote_ci_dispatch_allowed_by_this_preflight: `{summary['operator_remote_ci_dispatch_allowed_by_this_preflight']}`",
        f"- workflow_dispatch_executed: `{summary['workflow_dispatch_executed']}`",
        f"- expected_branch: `{summary['expected_branch'] or '-'}`",
        f"- expected_remote_ci_rerun_ref: `{summary['expected_remote_ci_rerun_ref'] or '-'}`",
        f"- expected_remote_ci_rerun_ref_published_for_dispatch: `{summary['expected_remote_ci_rerun_ref_published_for_dispatch']}`",
        f"- expected_remote_ci_rerun_ref_missing_for_dispatch: `{summary['expected_remote_ci_rerun_ref_missing_for_dispatch']}`",
        f"- gh_workflow_dispatch_422_expected_until_ref_published: `{summary['gh_workflow_dispatch_422_expected_until_ref_published']}`",
        f"- expected_remote_ci_rerun_ref_missing_required_action: `{summary['expected_remote_ci_rerun_ref_missing_required_action'] or '-'}`",
        f"- local_git_current_branch: `{summary['local_git_current_branch'] or '-'}`",
        f"- local_git_upstream_ref: `{summary['local_git_upstream_ref'] or '-'}`",
        f"- local_git_head_matches_upstream: `{summary['local_git_head_matches_upstream']}`",
        f"- local_runner_hygiene_required_patch_file_dirty_count: `{summary['local_runner_hygiene_required_patch_file_dirty_count']}`",
        f"- remote_ci_rerun_current_patch_published: `{summary['remote_ci_rerun_current_patch_published']}`",
        f"- product_ci_runtime_gate_status: `{summary['product_ci_runtime_gate_status'] or '-'}`",
        f"- product_ci_runtime_primary_blocker: `{summary['product_ci_runtime_primary_blocker'] or '-'}`",
        f"- product_ci_runtime_remote_ci_failure_class: `{summary['product_ci_runtime_remote_ci_failure_class'] or '-'}`",
        f"- product_ci_runtime_remote_workspace_cleanup_permission_blocked: `{summary['product_ci_runtime_remote_workspace_cleanup_permission_blocked']}`",
        f"- latest_product_api_worker_run_id: `{summary['latest_product_api_worker_run_id'] or '-'}`",
        f"- latest_product_image_build_smoke_run_id: `{summary['latest_product_image_build_smoke_run_id'] or '-'}`",
        f"- latest_product_image_smoke_run_id: `{summary['latest_product_image_smoke_run_id'] or '-'}`",
        f"- latest_remote_ci_observed_head_sha: `{summary['latest_remote_ci_observed_head_sha'] or '-'}`",
        f"- latest_remote_ci_observed_head_branch: `{summary['latest_remote_ci_observed_head_branch'] or '-'}`",
        f"- expected_remote_ci_rerun_branch: `{summary['expected_remote_ci_rerun_branch'] or '-'}`",
        f"- latest_remote_ci_observed_head_matches_expected_branch: `{summary['latest_remote_ci_observed_head_matches_expected_branch']}`",
        f"- latest_remote_ci_observed_wrong_branch_for_child_rerun: `{summary['latest_remote_ci_observed_wrong_branch_for_child_rerun']}`",
        f"- latest_remote_ci_observed_wrong_branch_required_action: `{summary['latest_remote_ci_observed_wrong_branch_required_action'] or '-'}`",
        f"- latest_remote_ci_observed_checkout_clean_mode: `{summary['latest_remote_ci_observed_checkout_clean_mode'] or '-'}`",
        f"- latest_remote_ci_current_workflow_patch_unverified: `{summary['latest_remote_ci_current_workflow_patch_unverified']}`",
        f"- latest_remote_ci_rerun_after_workflow_publication_required: `{summary['latest_remote_ci_rerun_after_workflow_publication_required']}`",
        f"- latest_remote_ci_science_tests_unverified: `{summary['latest_remote_ci_science_tests_unverified']}`",
        f"- latest_remote_rerun_cannot_validate_local_patch: `{summary['latest_remote_rerun_cannot_validate_local_patch']}`",
        f"- latest_remote_rerun_cannot_validate_child_branch_patch: `{summary['latest_remote_rerun_cannot_validate_child_branch_patch']}`",
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
    parser = argparse.ArgumentParser(
        description="Build PR #38 CI runner hygiene remote-rerun preflight."
    )
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
    payload = build_pr38_ci_runner_hygiene_remote_rerun_preflight(
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
    return 0 if payload["summary"]["remote_rerun_preflight_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
