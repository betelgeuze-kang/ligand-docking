#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_ci_runtime_gate_current.json"
DEFAULT_OUT_MD = "runs/product_ci_runtime_gate_current.md"
DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_SELF_HOSTED_RUNNER_INVENTORY_JSON = "runs/github_self_hosted_runner_inventory_current.json"
DEFAULT_SELF_HOSTED_RUNNER_HOST_PREFLIGHT_JSON = "runs/github_self_hosted_runner_host_preflight_current.json"

CLAIM_BOUNDARY = (
    "Product CI runtime gate only; records observed GitHub Actions run status and local ROCm product "
    "image preflight evidence. It does not dispatch workflows, mutate billing, change branch protection, "
    "deploy, publish, upload, or delete files."
)

BILLING_BLOCKER_CODE = "github_actions_billing_or_spending_limit"
WORKSPACE_CLEANUP_BLOCKER_CODE = "github_actions_workspace_cleanup_permission_denied"
SELF_HOSTED_API_WORKER_COMMAND = (
    "gh workflow run product-api-worker-trusted.yml --ref main"
)
SELF_HOSTED_ROCM_RUNTIME_COMMAND = (
    "gh workflow run product-image-smoke-trusted.yml --ref main -f verify_mode=rocm-runtime"
)
SELF_HOSTED_LINUX_LABELS = ("self-hosted", "linux")
SELF_HOSTED_ROCM_LABELS = ("self-hosted", "linux", "rocm")
WORKFLOW_OBSERVATION_ARGUMENT_NAMES = (
    "product_api_worker_run_id",
    "product_api_worker_url",
    "product_api_worker_conclusion",
    "product_api_worker_job_started",
    "product_api_worker_annotation",
    "product_api_worker_head_sha",
    "product_api_worker_head_branch",
    "product_api_worker_checkout_clean",
    "product_api_worker_created_at_utc",
    "product_api_worker_updated_at_utc",
    "product_image_build_smoke_run_id",
    "product_image_build_smoke_url",
    "product_image_build_smoke_conclusion",
    "product_image_build_smoke_job_started",
    "product_image_build_smoke_annotation",
    "product_image_build_smoke_head_sha",
    "product_image_build_smoke_head_branch",
    "product_image_build_smoke_checkout_clean",
    "product_image_build_smoke_created_at_utc",
    "product_image_build_smoke_updated_at_utc",
    "product_image_smoke_run_id",
    "product_image_smoke_url",
    "product_image_smoke_conclusion",
    "product_image_smoke_job_started",
    "product_image_smoke_annotation",
    "product_image_smoke_head_sha",
    "product_image_smoke_head_branch",
    "product_image_smoke_checkout_clean",
    "product_image_smoke_created_at_utc",
    "product_image_smoke_updated_at_utc",
)


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Product CI Runtime Gate",
        "",
        f"- status: `{s['status']}`",
        f"- remote_product_ci_green: `{s['remote_product_ci_green']}`",
        f"- github_actions_started: `{s['github_actions_started']}`",
        f"- external_blocker: `{s['external_blocker']}`",
        f"- blocker_code: `{s['blocker_code']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        f"- remote_ci_failure_class: `{s['remote_ci_failure_class']}`",
        f"- remote_ci_rerun_required: `{s['remote_ci_rerun_required']}`",
        f"- remote_ci_rerun_handoff_ready: `{s['remote_ci_rerun_handoff_ready']}`",
        f"- remote_ci_observed_head_sha: `{s['remote_ci_observed_head_sha'] or '-'}`",
        f"- remote_ci_observed_head_branch: `{s['remote_ci_observed_head_branch'] or '-'}`",
        f"- remote_ci_observed_checkout_clean_mode: `{s['remote_ci_observed_checkout_clean_mode']}`",
        f"- remote_ci_current_workflow_patch_unverified: `{s['remote_ci_current_workflow_patch_unverified']}`",
        f"- remote_ci_rerun_after_workflow_publication_required: `{s['remote_ci_rerun_after_workflow_publication_required']}`",
        f"- remote_ci_science_tests_unverified: `{s['remote_ci_science_tests_unverified']}`",
        f"- remote_workspace_cleanup_permission_blocked: `{s['remote_workspace_cleanup_permission_blocked']}`",
        f"- remote_workspace_cleanup_permission_blocker_code: `{s['remote_workspace_cleanup_permission_blocker_code']}`",
        f"- product_api_worker_conclusion: `{s['product_api_worker_conclusion']}`",
        f"- product_image_build_smoke_observed: `{s['product_image_build_smoke_observed']}`",
        f"- product_image_build_smoke_conclusion: `{s['product_image_build_smoke_conclusion'] or '-'}`",
        f"- product_image_smoke_conclusion: `{s['product_image_smoke_conclusion']}`",
        f"- latest_github_actions_record_kst_date: `{s['latest_github_actions_record_kst_date']}`",
        f"- local_rocm_clean_container_ready: `{s['local_rocm_clean_container_ready']}`",
        f"- local_product_image_runner_hygiene_remediation_ready: `{s['local_product_image_runner_hygiene_remediation_ready']}`",
        f"- local_product_image_workflow_contract_ready: `{s['local_product_image_workflow_contract_ready']}`",
        f"- local_product_image_workflow_workspace_artifact_recovery_ready: `{s['local_product_image_workflow_workspace_artifact_recovery_ready']}`",
        f"- local_product_image_runner_smoke_dir_contract_ready: `{s['local_product_image_runner_smoke_dir_contract_ready']}`",
        f"- local_product_image_receipt_runner_hygiene_ready: `{s['local_product_image_receipt_runner_hygiene_ready']}`",
        f"- local_product_image_workspace_smoke_artifact_current_cleanup_ready: `{s['local_product_image_workspace_smoke_artifact_current_cleanup_ready']}`",
        f"- local_product_image_workspace_smoke_artifact_current_blocker_count: `{s['local_product_image_workspace_smoke_artifact_current_blocker_count']}`",
        f"- local_product_image_workspace_smoke_artifact_current_bad_owner_path: `{s['local_product_image_workspace_smoke_artifact_current_bad_owner_path']}`",
        f"- local_product_image_workspace_smoke_artifact_current_not_writable_path: `{s['local_product_image_workspace_smoke_artifact_current_not_writable_path']}`",
        f"- billing_free_self_hosted_path_recommended: `{s['billing_free_self_hosted_path_recommended']}`",
        f"- hosted_spending_limit_increase_required: `{s['hosted_spending_limit_increase_required']}`",
        f"- self_hosted_runner_inventory_present: `{s['self_hosted_runner_inventory_present']}`",
        f"- self_hosted_runner_total_count: `{s['self_hosted_runner_total_count']}`",
        f"- self_hosted_linux_runner_online: `{s['self_hosted_linux_runner_online']}`",
        f"- self_hosted_linux_runner_count: `{s['self_hosted_linux_runner_count']}`",
        f"- self_hosted_rocm_runner_online: `{s['self_hosted_rocm_runner_online']}`",
        f"- self_hosted_rocm_runner_count: `{s['self_hosted_rocm_runner_count']}`",
        f"- self_hosted_runner_host_preflight_present: `{s['self_hosted_runner_host_preflight_present']}`",
        f"- self_hosted_runner_host_preflight_status: `{s['self_hosted_runner_host_preflight_status']}`",
        f"- self_hosted_runner_host_local_ready: `{s['self_hosted_runner_host_local_ready']}`",
        f"- self_hosted_runner_host_registration_required: `{s['self_hosted_runner_host_registration_required']}`",
        f"- workflow_dispatch_executed: `{s['workflow_dispatch_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- next_required_step: {s['next_required_step']}",
        "",
        "## Runs",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['workflow']}",
                "",
                f"- run_id: `{row['run_id']}`",
                f"- head_sha: `{row['head_sha'] or '-'}`",
                f"- head_branch: `{row['head_branch'] or '-'}`",
                f"- checkout_clean: `{row['checkout_clean'] or 'unobserved'}`",
                f"- created_at_utc: `{row['created_at_utc']}`",
                f"- created_at_kst_date: `{row['created_at_kst_date']}`",
                f"- conclusion: `{row['conclusion']}`",
                f"- job_started: `{row['job_started']}`",
                f"- url: {row['url'] or 'n/a'}",
                f"- release_blocker: `{row['release_blocker']}`",
                "",
            ]
        )
    lines.extend(["## Blockers", ""])
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{row['code']}`" for row in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {step}" for step in s["next_required_steps"])
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _is_truthy_text(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "started"}


def _has_cli_workflow_observation(args: argparse.Namespace) -> bool:
    for name in WORKFLOW_OBSERVATION_ARGUMENT_NAMES:
        value = getattr(args, name)
        if name.endswith("_job_started"):
            if _is_truthy_text(str(value or "")):
                return True
        elif str(value or "").strip():
            return True
    return False


def _existing_observation_kwargs(root: Path, path_like: str | Path) -> dict[str, Any]:
    packet = _read_json(root, path_like)
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return {}
    by_workflow = {
        str(row.get("workflow") or ""): row
        for row in rows
        if isinstance(row, dict) and row.get("workflow")
    }
    mapping = {
        "product-api-worker": "product_api_worker",
        "product-image-build-smoke": "product_image_build_smoke",
        "product-image-smoke": "product_image_smoke",
    }
    kwargs: dict[str, Any] = {}
    for workflow, prefix in mapping.items():
        row = by_workflow.get(workflow)
        if not row:
            continue
        kwargs[f"{prefix}_run_id"] = str(row.get("run_id") or "")
        kwargs[f"{prefix}_url"] = str(row.get("url") or "")
        kwargs[f"{prefix}_conclusion"] = str(row.get("conclusion") or "")
        kwargs[f"{prefix}_job_started"] = bool(row.get("job_started") is True)
        kwargs[f"{prefix}_annotation"] = str(row.get("annotation") or "")
        kwargs[f"{prefix}_head_sha"] = str(row.get("head_sha") or "")
        kwargs[f"{prefix}_head_branch"] = str(row.get("head_branch") or "")
        kwargs[f"{prefix}_checkout_clean"] = str(row.get("checkout_clean") or "")
        kwargs[f"{prefix}_created_at_utc"] = str(row.get("created_at_utc") or "")
        kwargs[f"{prefix}_updated_at_utc"] = str(row.get("updated_at_utc") or "")
    return kwargs


def _billing_blocked(*messages: str) -> bool:
    joined = " ".join(message.lower() for message in messages if message)
    return "payments have failed" in joined or "spending limit" in joined or "billing" in joined


def _workspace_cleanup_blocked(*messages: str) -> bool:
    joined = " ".join(message.lower() for message in messages if message)
    if not joined:
        return False
    cleanup_signal = (
        "product_image_smoke_runner_artifacts" in joined
        or "deleting the contents" in joined
        or "workspace cleanup" in joined
    )
    permission_signal = (
        "eacces" in joined
        or "permission denied" in joined
        or "unable to be removed" in joined
    )
    return bool(cleanup_signal and permission_signal)


def _kst_date_from_utc(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.astimezone(timezone(timedelta(hours=9))).date().isoformat()


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _runner_label_names(runner: dict[str, Any]) -> set[str]:
    labels = runner.get("labels")
    names: set[str] = set()
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                value = label.get("name")
            else:
                value = label
            if value:
                names.add(str(value).strip().lower())
    elif isinstance(labels, dict):
        for key, value in labels.items():
            if value is True:
                names.add(str(key).strip().lower())
            elif isinstance(value, str):
                names.add(value.strip().lower())
    elif isinstance(labels, str):
        names.update(part.strip().lower() for part in labels.split(",") if part.strip())
    return names


def _runner_online(runner: dict[str, Any]) -> bool:
    return str(runner.get("status") or "").strip().lower() == "online"


def _runner_has_labels(runner: dict[str, Any], required: tuple[str, ...]) -> bool:
    labels = _runner_label_names(runner)
    return all(label in labels for label in required)


def _runner_inventory_summary(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    packet = _read_json(root, path_like)
    runners = packet.get("runners")
    if not isinstance(runners, list):
        runners = []
    linux_runners = [
        runner
        for runner in runners
        if isinstance(runner, dict) and _runner_online(runner) and _runner_has_labels(runner, SELF_HOSTED_LINUX_LABELS)
    ]
    rocm_runners = [
        runner
        for runner in runners
        if isinstance(runner, dict) and _runner_online(runner) and _runner_has_labels(runner, SELF_HOSTED_ROCM_LABELS)
    ]
    total_count = packet.get("total_count")
    if not isinstance(total_count, int):
        total_count = len(runners)
    return {
        "self_hosted_runner_inventory_json": str(path_like),
        "self_hosted_runner_inventory_present": path.exists() and path.is_file() and bool(packet),
        "self_hosted_runner_total_count": int(total_count),
        "self_hosted_linux_runner_online": bool(linux_runners),
        "self_hosted_linux_runner_count": len(linux_runners),
        "self_hosted_rocm_runner_online": bool(rocm_runners),
        "self_hosted_rocm_runner_count": len(rocm_runners),
        "self_hosted_linux_required_labels": list(SELF_HOSTED_LINUX_LABELS),
        "self_hosted_rocm_required_labels": list(SELF_HOSTED_ROCM_LABELS),
        "self_hosted_runner_inventory_external_state_mutated": False,
    }


def _runner_host_preflight_summary(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    packet = _read_json(root, path_like)
    summary = _summary(packet)
    return {
        "self_hosted_runner_host_preflight_json": str(path_like),
        "self_hosted_runner_host_preflight_present": path.exists() and path.is_file() and bool(summary),
        "self_hosted_runner_host_preflight_status": str(summary.get("status") or ""),
        "self_hosted_runner_host_local_ready": bool(summary.get("local_runner_host_ready") is True),
        "self_hosted_runner_host_repo_ready": bool(summary.get("repo_self_hosted_runner_ready") is True),
        "self_hosted_runner_host_registration_required": bool(
            summary.get("repo_runner_registration_required") is True
        ),
        "self_hosted_runner_host_docker_daemon_accessible": bool(
            summary.get("docker_daemon_accessible") is True
        ),
        "self_hosted_runner_host_rocm_device_nodes_ready": bool(
            summary.get("rocm_device_nodes_ready") is True
        ),
        "self_hosted_runner_host_product_image_rocm_runtime_ready": bool(
            summary.get("product_image_rocm_runtime_ready") is True
        ),
        "self_hosted_runner_host_github_registration_token_requested": bool(
            summary.get("github_registration_token_requested") is True
        ),
        "self_hosted_runner_host_runner_configured": bool(summary.get("runner_configured") is True),
        "self_hosted_runner_host_runner_service_started": bool(
            summary.get("runner_service_started") is True
        ),
        "self_hosted_runner_host_external_state_mutated": bool(
            summary.get("external_state_mutated") is True
        ),
    }


def _product_image_runner_hygiene_ready(summary: dict[str, Any]) -> bool:
    workspace_cleanup_ready = bool(
        "workspace_smoke_artifact_current_cleanup_ready" not in summary
        or summary.get("workspace_smoke_artifact_current_cleanup_ready") is True
    )
    return bool(
        summary.get("receipt_runner_hygiene_ready") is True
        and summary.get("receipt_runner_smoke_dir_outside_workspace") is True
        and summary.get("receipt_container_output_uid_gid_pinned") is True
        and summary.get("receipt_container_output_uid_gid_matches_host") is True
        and summary.get("receipt_container_output_uid_gid_non_root") is True
        and summary.get("receipt_workspace_runner_smoke_dir_cleanup_ready") is True
        and workspace_cleanup_ready
    )


def _product_image_workflow_contract_ready(summary: dict[str, Any]) -> bool:
    return bool(
        ("workflow_contract_ready" not in summary or summary.get("workflow_contract_ready") is True)
        and (
            "workflow_workspace_artifact_recovery_ready" not in summary
            or summary.get("workflow_workspace_artifact_recovery_ready") is True
        )
        and (
            "runner_smoke_dir_contract_ready" not in summary
            or summary.get("runner_smoke_dir_contract_ready") is True
        )
    )


def _workflow_row(
    *,
    workflow: str,
    run_id: str,
    url: str,
    conclusion: str,
    job_started: bool,
    annotation: str,
    head_sha: str = "",
    head_branch: str = "",
    checkout_clean: str = "",
    created_at_utc: str = "",
    updated_at_utc: str = "",
) -> dict[str, Any]:
    green = conclusion == "success" and job_started
    checkout_clean_normalized = str(checkout_clean or "").strip().lower()
    if checkout_clean_normalized not in {"true", "false"}:
        checkout_clean_normalized = ""
    return {
        "workflow": workflow,
        "run_id": run_id,
        "url": url,
        "conclusion": conclusion,
        "job_started": job_started,
        "annotation": annotation,
        "head_sha": str(head_sha or "").strip(),
        "head_branch": str(head_branch or "").strip(),
        "checkout_clean": checkout_clean_normalized,
        "checkout_clean_observed": bool(checkout_clean_normalized),
        "checkout_clean_true_observed": checkout_clean_normalized == "true",
        "checkout_clean_false_observed": checkout_clean_normalized == "false",
        "created_at_utc": created_at_utc,
        "updated_at_utc": updated_at_utc,
        "created_at_kst_date": _kst_date_from_utc(created_at_utc),
        "green": green,
        "release_blocker": not green,
        "external_state_mutated": False,
    }


def _workflow_observed(
    *,
    run_id: str = "",
    url: str = "",
    conclusion: str = "",
    job_started: bool = False,
    annotation: str = "",
    head_sha: str = "",
    head_branch: str = "",
    checkout_clean: str = "",
    created_at_utc: str = "",
    updated_at_utc: str = "",
) -> bool:
    return any(
        str(value or "").strip()
        for value in (
            run_id,
            url,
            conclusion,
            annotation,
            head_sha,
            head_branch,
            checkout_clean,
            created_at_utc,
            updated_at_utc,
        )
    ) or bool(job_started)


def build_product_ci_runtime_gate(
    *,
    root: str | Path = ROOT,
    product_image_preflight_json: str | Path = DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    self_hosted_runner_inventory_json: str | Path = DEFAULT_SELF_HOSTED_RUNNER_INVENTORY_JSON,
    self_hosted_runner_host_preflight_json: str | Path = DEFAULT_SELF_HOSTED_RUNNER_HOST_PREFLIGHT_JSON,
    product_api_worker_run_id: str = "",
    product_api_worker_url: str = "",
    product_api_worker_conclusion: str = "",
    product_api_worker_job_started: bool = False,
    product_api_worker_annotation: str = "",
    product_api_worker_head_sha: str = "",
    product_api_worker_head_branch: str = "",
    product_api_worker_checkout_clean: str = "",
    product_api_worker_created_at_utc: str = "",
    product_api_worker_updated_at_utc: str = "",
    product_image_build_smoke_run_id: str = "",
    product_image_build_smoke_url: str = "",
    product_image_build_smoke_conclusion: str = "",
    product_image_build_smoke_job_started: bool = False,
    product_image_build_smoke_annotation: str = "",
    product_image_build_smoke_head_sha: str = "",
    product_image_build_smoke_head_branch: str = "",
    product_image_build_smoke_checkout_clean: str = "",
    product_image_build_smoke_created_at_utc: str = "",
    product_image_build_smoke_updated_at_utc: str = "",
    product_image_smoke_run_id: str = "",
    product_image_smoke_url: str = "",
    product_image_smoke_conclusion: str = "",
    product_image_smoke_job_started: bool = False,
    product_image_smoke_annotation: str = "",
    product_image_smoke_head_sha: str = "",
    product_image_smoke_head_branch: str = "",
    product_image_smoke_checkout_clean: str = "",
    product_image_smoke_created_at_utc: str = "",
    product_image_smoke_updated_at_utc: str = "",
) -> dict[str, Any]:
    root_path = Path(root)
    preflight_summary = _summary(_read_json(root_path, product_image_preflight_json))
    runner_inventory = _runner_inventory_summary(root_path, self_hosted_runner_inventory_json)
    runner_host_preflight = _runner_host_preflight_summary(root_path, self_hosted_runner_host_preflight_json)
    product_image_runner_hygiene_ready = _product_image_runner_hygiene_ready(preflight_summary)
    product_image_workflow_contract_ready = _product_image_workflow_contract_ready(preflight_summary)
    product_image_workspace_cleanup_ready = bool(
        "workspace_smoke_artifact_current_cleanup_ready" not in preflight_summary
        or preflight_summary.get("workspace_smoke_artifact_current_cleanup_ready") is True
    )
    product_image_workspace_blockers = [
        str(blocker)
        for blocker in preflight_summary.get("workspace_smoke_artifact_current_blockers") or []
        if str(blocker)
    ]
    if (
        not product_image_workspace_blockers
        and preflight_summary.get("workspace_smoke_artifact_current_cleanup_ready") is False
    ):
        product_image_workspace_blockers.append(
            "workspace_smoke_artifact_current_cleanup_not_ready"
        )
        if preflight_summary.get("workspace_smoke_artifact_current_bad_owner_path"):
            product_image_workspace_blockers.append(
                "workspace_smoke_artifact_current_owner_not_normalized"
            )
        if preflight_summary.get("workspace_smoke_artifact_current_not_writable_path"):
            product_image_workspace_blockers.append(
                "workspace_smoke_artifact_current_not_writable"
            )
    local_rocm_clean_container_ready = bool(
        preflight_summary.get("status") == "product_image_smoke_preflight_ready"
        and preflight_summary.get("clean_container_smoke_ready") is True
        and preflight_summary.get("receipt_status") == "product_image_smoke_ready"
        and preflight_summary.get("receipt_mode") == "rocm-runtime"
        and preflight_summary.get("container_runtime_receipt_ready") is True
        and preflight_summary.get("container_runtime_rust_hip_backend_enabled") is True
        and preflight_summary.get("product_runner_smoke_ready") is True
        and product_image_runner_hygiene_ready
    )
    rows = [
        _workflow_row(
            workflow="product-api-worker",
            run_id=product_api_worker_run_id,
            url=product_api_worker_url,
            conclusion=product_api_worker_conclusion,
            job_started=product_api_worker_job_started,
            annotation=product_api_worker_annotation,
            head_sha=product_api_worker_head_sha,
            head_branch=product_api_worker_head_branch,
            checkout_clean=product_api_worker_checkout_clean,
            created_at_utc=product_api_worker_created_at_utc,
            updated_at_utc=product_api_worker_updated_at_utc,
        ),
    ]
    if _workflow_observed(
        run_id=product_image_build_smoke_run_id,
        url=product_image_build_smoke_url,
        conclusion=product_image_build_smoke_conclusion,
        job_started=product_image_build_smoke_job_started,
        annotation=product_image_build_smoke_annotation,
        head_sha=product_image_build_smoke_head_sha,
        head_branch=product_image_build_smoke_head_branch,
        checkout_clean=product_image_build_smoke_checkout_clean,
        created_at_utc=product_image_build_smoke_created_at_utc,
        updated_at_utc=product_image_build_smoke_updated_at_utc,
    ):
        rows.append(
            _workflow_row(
                workflow="product-image-build-smoke",
                run_id=product_image_build_smoke_run_id,
                url=product_image_build_smoke_url,
                conclusion=product_image_build_smoke_conclusion,
                job_started=product_image_build_smoke_job_started,
                annotation=product_image_build_smoke_annotation,
                head_sha=product_image_build_smoke_head_sha,
                head_branch=product_image_build_smoke_head_branch,
                checkout_clean=product_image_build_smoke_checkout_clean,
                created_at_utc=product_image_build_smoke_created_at_utc,
                updated_at_utc=product_image_build_smoke_updated_at_utc,
            )
        )
    rows.append(
        _workflow_row(
            workflow="product-image-smoke",
            run_id=product_image_smoke_run_id,
            url=product_image_smoke_url,
            conclusion=product_image_smoke_conclusion,
            job_started=product_image_smoke_job_started,
            annotation=product_image_smoke_annotation,
            head_sha=product_image_smoke_head_sha,
            head_branch=product_image_smoke_head_branch,
            checkout_clean=product_image_smoke_checkout_clean,
            created_at_utc=product_image_smoke_created_at_utc,
            updated_at_utc=product_image_smoke_updated_at_utc,
        )
    )
    rows_by_workflow = {row["workflow"]: row for row in rows}
    image_build_row = rows_by_workflow.get("product-image-build-smoke", {})
    image_smoke_row = rows_by_workflow["product-image-smoke"]
    observed_dates = sorted({row["created_at_kst_date"] for row in rows if row["created_at_kst_date"]})
    observed_head_shas = sorted({row["head_sha"] for row in rows if row["head_sha"]})
    observed_head_branches = sorted({row["head_branch"] for row in rows if row["head_branch"]})
    observed_checkout_clean_modes = sorted(
        {row["checkout_clean"] for row in rows if row["checkout_clean"]}
    )
    observed_checkout_clean_mode = (
        observed_checkout_clean_modes[0]
        if len(observed_checkout_clean_modes) == 1
        else ("mixed" if observed_checkout_clean_modes else "unobserved")
    )
    billing_blocked = _billing_blocked(product_api_worker_annotation, product_image_smoke_annotation)
    workspace_cleanup_blocked = _workspace_cleanup_blocked(
        product_api_worker_annotation,
        product_image_smoke_annotation,
    )
    local_product_image_runner_hygiene_remediation_ready = bool(
        product_image_runner_hygiene_ready
        and product_image_workflow_contract_ready
        and product_image_workspace_cleanup_ready
    )
    remote_product_ci_green = all(row["green"] for row in rows)
    github_actions_started = all(row["job_started"] for row in rows)
    runtime_gate_ready = bool(remote_product_ci_green and local_rocm_clean_container_ready)
    remote_ci_rerun_required = not remote_product_ci_green
    remote_ci_rerun_handoff_ready = bool(
        remote_ci_rerun_required
        and local_rocm_clean_container_ready
        and local_product_image_runner_hygiene_remediation_ready
        and not billing_blocked
    )
    remote_ci_failure_class = (
        "workspace_cleanup_permission"
        if workspace_cleanup_blocked
        else ("remote_workflows_not_green" if remote_ci_rerun_required else "")
    )
    remote_ci_observed_checkout_clean_true = any(
        row["checkout_clean_true_observed"] for row in rows
    )
    remote_ci_observed_checkout_clean_false = any(
        row["checkout_clean_false_observed"] for row in rows
    )
    remote_ci_current_workflow_patch_unverified = bool(
        workspace_cleanup_blocked
        and local_product_image_runner_hygiene_remediation_ready
        and remote_ci_observed_checkout_clean_true
    )
    remote_ci_rerun_after_workflow_publication_required = bool(
        remote_ci_rerun_required and remote_ci_current_workflow_patch_unverified
    )
    remote_ci_science_tests_unverified = bool(workspace_cleanup_blocked)
    billing_free_self_hosted_path_recommended = bool(billing_blocked and not remote_product_ci_green)
    hosted_spending_limit_increase_required = False
    blockers: list[dict[str, str]] = []
    if billing_blocked:
        blockers.append({"code": BILLING_BLOCKER_CODE})
    if workspace_cleanup_blocked:
        blockers.append({"code": WORKSPACE_CLEANUP_BLOCKER_CODE})
    if (
        billing_free_self_hosted_path_recommended
        and runner_inventory["self_hosted_linux_runner_online"] is not True
    ):
        blockers.append({"code": "self_hosted_linux_runner_missing"})
    if (
        billing_free_self_hosted_path_recommended
        and runner_inventory["self_hosted_rocm_runner_online"] is not True
    ):
        blockers.append({"code": "self_hosted_rocm_runner_missing"})
    if (
        billing_free_self_hosted_path_recommended
        and runner_host_preflight["self_hosted_runner_host_local_ready"] is True
        and runner_host_preflight["self_hosted_runner_host_registration_required"] is True
    ):
        blockers.append({"code": "self_hosted_runner_registration_required"})
    if not local_rocm_clean_container_ready:
        blockers.append({"code": "local_rocm_clean_container_evidence_missing"})
    if not product_image_runner_hygiene_ready:
        blockers.append({"code": "local_product_image_runner_hygiene_evidence_missing"})
    if not product_image_workspace_cleanup_ready:
        for blocker in product_image_workspace_blockers:
            blockers.append({"code": f"product_image_{blocker}"})
    if workspace_cleanup_blocked and not local_product_image_runner_hygiene_remediation_ready:
        blockers.append({"code": "local_product_image_runner_hygiene_remediation_missing"})
    for blocker in preflight_summary.get("receipt_runner_hygiene_blockers") or []:
        if isinstance(blocker, str) and blocker:
            blockers.append({"code": f"product_image_{blocker}"})
    for row in rows:
        if not row["green"]:
            blockers.append({"code": f"{row['workflow']}_not_green"})
    blocker_codes = [blocker["code"] for blocker in blockers if blocker.get("code")]
    status = "product_ci_runtime_gate_ready" if runtime_gate_ready else "blocked_product_ci_runtime_gate"
    next_required_steps = (
        [
            "Keep the public personal-repository runner inventory empty while the previously exposed host is rebuilt or replaced and host-accessible credentials are reviewed and rotated.",
            "Create a protected organization/private selected-workflow execution surface pinned to main for self-hosted runners, or use an isolated ephemeral runner; do not restore a persistent public repository runner.",
            "After that boundary exists, configure Linux labels self-hosted, linux and ROCm labels self-hosted, linux, rocm.",
            f"Then run the trusted API worker contract: {SELF_HOSTED_API_WORKER_COMMAND}",
            f"Then run the trusted ROCm runtime smoke: {SELF_HOSTED_ROCM_RUNTIME_COMMAND}",
            "Only raise GitHub-hosted Actions spending limits if intentionally choosing hosted CI.",
        ]
        if billing_blocked
        else (
            ["Remote product CI is green; attach this gate to the product evidence bundle."]
            if runtime_gate_ready
            else (
                [
                    "Observed failed remote runs still used actions/checkout clean:true; after the local runner-hygiene workflow remediation is pushed, rerun product-api-worker and product-image-smoke workflows, then rebuild this gate from observed green runs.",
                ]
                if remote_ci_rerun_after_workflow_publication_required
                else (
                    [
                        "After the local runner-hygiene workflow remediation is pushed, rerun product-api-worker and product-image-smoke workflows, then rebuild this gate from observed green runs.",
                    ]
                    if workspace_cleanup_blocked and local_product_image_runner_hygiene_remediation_ready
                    else [
                        "Rerun product-api-worker and product-image-smoke workflows, then rebuild this gate from observed green runs.",
                    ]
                )
            )
        )
    )
    summary = {
        "packet_type": "product_ci_runtime_gate",
        "status": status,
        "runtime_gate_ready": runtime_gate_ready,
        "remote_product_ci_green": remote_product_ci_green,
        "github_actions_started": github_actions_started,
        "external_blocker": billing_blocked,
        "blocker_code": BILLING_BLOCKER_CODE if billing_blocked else "",
        "blocker_count": len(blocker_codes),
        "blockers": blocker_codes,
        "primary_blocker": blocker_codes[0] if blocker_codes else "",
        "remote_ci_failure_class": remote_ci_failure_class,
        "remote_ci_rerun_required": remote_ci_rerun_required,
        "remote_ci_rerun_handoff_ready": remote_ci_rerun_handoff_ready,
        "remote_ci_observed_head_shas": observed_head_shas,
        "remote_ci_observed_head_sha": (
            observed_head_shas[0]
            if len(observed_head_shas) == 1
            else ("mixed" if observed_head_shas else "")
        ),
        "remote_ci_observed_head_branches": observed_head_branches,
        "remote_ci_observed_head_branch": (
            observed_head_branches[0]
            if len(observed_head_branches) == 1
            else ("mixed" if observed_head_branches else "")
        ),
        "remote_ci_observed_checkout_clean_modes": observed_checkout_clean_modes,
        "remote_ci_observed_checkout_clean_mode": observed_checkout_clean_mode,
        "remote_ci_observed_checkout_clean_true": remote_ci_observed_checkout_clean_true,
        "remote_ci_observed_checkout_clean_false": remote_ci_observed_checkout_clean_false,
        "remote_ci_current_workflow_patch_unverified": remote_ci_current_workflow_patch_unverified,
        "remote_ci_rerun_after_workflow_publication_required": (
            remote_ci_rerun_after_workflow_publication_required
        ),
        "remote_ci_science_tests_unverified": remote_ci_science_tests_unverified,
        "remote_workspace_cleanup_permission_blocked": workspace_cleanup_blocked,
        "remote_workspace_cleanup_permission_blocker_code": (
            WORKSPACE_CLEANUP_BLOCKER_CODE if workspace_cleanup_blocked else ""
        ),
        "local_product_image_runner_hygiene_remediation_ready": (
            local_product_image_runner_hygiene_remediation_ready
        ),
        "local_product_image_workflow_contract_ready": product_image_workflow_contract_ready,
        "local_product_image_workflow_workspace_artifact_recovery_ready": bool(
            "workflow_workspace_artifact_recovery_ready" not in preflight_summary
            or preflight_summary.get("workflow_workspace_artifact_recovery_ready") is True
        ),
        "local_product_image_runner_smoke_dir_contract_ready": bool(
            "runner_smoke_dir_contract_ready" not in preflight_summary
            or preflight_summary.get("runner_smoke_dir_contract_ready") is True
        ),
        "billing_free_self_hosted_path_recommended": billing_free_self_hosted_path_recommended,
        "billing_free_self_hosted_api_worker_command": SELF_HOSTED_API_WORKER_COMMAND,
        "billing_free_self_hosted_rocm_runtime_command": SELF_HOSTED_ROCM_RUNTIME_COMMAND,
        "hosted_spending_limit_increase_required": hosted_spending_limit_increase_required,
        **runner_inventory,
        **runner_host_preflight,
        "product_api_worker_run_id": product_api_worker_run_id,
        "product_api_worker_url": product_api_worker_url,
        "product_api_worker_conclusion": product_api_worker_conclusion,
        "product_api_worker_job_started": product_api_worker_job_started,
        "product_api_worker_head_sha": str(product_api_worker_head_sha or "").strip(),
        "product_api_worker_head_branch": str(product_api_worker_head_branch or "").strip(),
        "product_api_worker_checkout_clean": rows[0]["checkout_clean"],
        "product_api_worker_created_at_utc": product_api_worker_created_at_utc,
        "product_api_worker_created_at_kst_date": _kst_date_from_utc(product_api_worker_created_at_utc),
        "product_image_build_smoke_observed": bool(image_build_row),
        "product_image_build_smoke_run_id": str(image_build_row.get("run_id") or ""),
        "product_image_build_smoke_url": str(image_build_row.get("url") or ""),
        "product_image_build_smoke_conclusion": str(
            image_build_row.get("conclusion") or ""
        ),
        "product_image_build_smoke_job_started": bool(
            image_build_row.get("job_started") is True
        ),
        "product_image_build_smoke_head_sha": str(
            image_build_row.get("head_sha") or ""
        ),
        "product_image_build_smoke_head_branch": str(
            image_build_row.get("head_branch") or ""
        ),
        "product_image_build_smoke_checkout_clean": str(
            image_build_row.get("checkout_clean") or ""
        ),
        "product_image_build_smoke_created_at_utc": str(
            image_build_row.get("created_at_utc") or ""
        ),
        "product_image_build_smoke_created_at_kst_date": str(
            image_build_row.get("created_at_kst_date") or ""
        ),
        "product_image_smoke_run_id": product_image_smoke_run_id,
        "product_image_smoke_url": product_image_smoke_url,
        "product_image_smoke_conclusion": product_image_smoke_conclusion,
        "product_image_smoke_job_started": product_image_smoke_job_started,
        "product_image_smoke_head_sha": str(product_image_smoke_head_sha or "").strip(),
        "product_image_smoke_head_branch": str(product_image_smoke_head_branch or "").strip(),
        "product_image_smoke_checkout_clean": image_smoke_row["checkout_clean"],
        "product_image_smoke_created_at_utc": product_image_smoke_created_at_utc,
        "product_image_smoke_created_at_kst_date": _kst_date_from_utc(product_image_smoke_created_at_utc),
        "latest_github_actions_record_kst_date": observed_dates[-1] if observed_dates else "",
        "github_actions_record_dates_kst": observed_dates,
        "product_image_preflight_json": str(product_image_preflight_json),
        "local_rocm_clean_container_ready": local_rocm_clean_container_ready,
        "local_product_image_preflight_status": str(preflight_summary.get("status") or ""),
        "local_product_image_receipt_mode": str(preflight_summary.get("receipt_mode") or ""),
        "local_product_image_receipt_status": str(preflight_summary.get("receipt_status") or ""),
        "local_product_image_receipt_runner_hygiene_ready": product_image_runner_hygiene_ready,
        "local_product_image_receipt_runner_hygiene_blockers": [
            str(blocker)
            for blocker in preflight_summary.get("receipt_runner_hygiene_blockers") or []
            if str(blocker)
        ],
        "local_product_image_workspace_smoke_artifact_current_cleanup_ready": (
            product_image_workspace_cleanup_ready
        ),
        "local_product_image_workspace_smoke_artifact_current_blocker_count": len(
            product_image_workspace_blockers
        ),
        "local_product_image_workspace_smoke_artifact_current_blockers": (
            product_image_workspace_blockers
        ),
        "local_product_image_workspace_smoke_artifact_current_bad_owner_path": str(
            preflight_summary.get("workspace_smoke_artifact_current_bad_owner_path") or ""
        ),
        "local_product_image_workspace_smoke_artifact_current_not_writable_path": str(
            preflight_summary.get("workspace_smoke_artifact_current_not_writable_path") or ""
        ),
        "local_product_image_workspace_smoke_artifact_current_required_action": str(
            preflight_summary.get("workspace_smoke_artifact_current_required_action") or ""
        ),
        "local_product_image_workspace_smoke_artifact_current_verification_command": str(
            preflight_summary.get("workspace_smoke_artifact_current_verification_command")
            or ""
        ),
        "workflow_dispatch_executed": False,
        "billing_mutated": False,
        "branch_protection_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_steps[0] if next_required_steps else "",
        "next_required_steps": next_required_steps,
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product CI runtime gate evidence.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--self-hosted-runner-inventory-json", default=DEFAULT_SELF_HOSTED_RUNNER_INVENTORY_JSON)
    parser.add_argument(
        "--self-hosted-runner-host-preflight-json",
        default=DEFAULT_SELF_HOSTED_RUNNER_HOST_PREFLIGHT_JSON,
    )
    parser.add_argument("--product-api-worker-run-id", default="")
    parser.add_argument("--product-api-worker-url", default="")
    parser.add_argument("--product-api-worker-conclusion", default="")
    parser.add_argument("--product-api-worker-job-started", default="false")
    parser.add_argument("--product-api-worker-annotation", default="")
    parser.add_argument("--product-api-worker-head-sha", default="")
    parser.add_argument("--product-api-worker-head-branch", default="")
    parser.add_argument("--product-api-worker-checkout-clean", default="")
    parser.add_argument("--product-api-worker-created-at-utc", default="")
    parser.add_argument("--product-api-worker-updated-at-utc", default="")
    parser.add_argument("--product-image-build-smoke-run-id", default="")
    parser.add_argument("--product-image-build-smoke-url", default="")
    parser.add_argument("--product-image-build-smoke-conclusion", default="")
    parser.add_argument("--product-image-build-smoke-job-started", default="false")
    parser.add_argument("--product-image-build-smoke-annotation", default="")
    parser.add_argument("--product-image-build-smoke-head-sha", default="")
    parser.add_argument("--product-image-build-smoke-head-branch", default="")
    parser.add_argument("--product-image-build-smoke-checkout-clean", default="")
    parser.add_argument("--product-image-build-smoke-created-at-utc", default="")
    parser.add_argument("--product-image-build-smoke-updated-at-utc", default="")
    parser.add_argument("--product-image-smoke-run-id", default="")
    parser.add_argument("--product-image-smoke-url", default="")
    parser.add_argument("--product-image-smoke-conclusion", default="")
    parser.add_argument("--product-image-smoke-job-started", default="false")
    parser.add_argument("--product-image-smoke-annotation", default="")
    parser.add_argument("--product-image-smoke-head-sha", default="")
    parser.add_argument("--product-image-smoke-head-branch", default="")
    parser.add_argument("--product-image-smoke-checkout-clean", default="")
    parser.add_argument("--product-image-smoke-created-at-utc", default="")
    parser.add_argument("--product-image-smoke-updated-at-utc", default="")
    parser.add_argument(
        "--no-preserve-existing-observations",
        action="store_true",
        help=(
            "Do not reuse existing workflow observation rows from --out-json when no "
            "new workflow observation arguments are supplied."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    observation_kwargs = {}
    if not args.no_preserve_existing_observations and not _has_cli_workflow_observation(args):
        observation_kwargs = _existing_observation_kwargs(ROOT, args.out_json)
    payload = build_product_ci_runtime_gate(
        product_image_preflight_json=args.product_image_preflight_json,
        self_hosted_runner_inventory_json=args.self_hosted_runner_inventory_json,
        self_hosted_runner_host_preflight_json=args.self_hosted_runner_host_preflight_json,
        product_api_worker_run_id=observation_kwargs.get(
            "product_api_worker_run_id", args.product_api_worker_run_id
        ),
        product_api_worker_url=observation_kwargs.get(
            "product_api_worker_url", args.product_api_worker_url
        ),
        product_api_worker_conclusion=observation_kwargs.get(
            "product_api_worker_conclusion", args.product_api_worker_conclusion
        ),
        product_api_worker_job_started=observation_kwargs.get(
            "product_api_worker_job_started", _is_truthy_text(args.product_api_worker_job_started)
        ),
        product_api_worker_annotation=observation_kwargs.get(
            "product_api_worker_annotation", args.product_api_worker_annotation
        ),
        product_api_worker_head_sha=observation_kwargs.get(
            "product_api_worker_head_sha", args.product_api_worker_head_sha
        ),
        product_api_worker_head_branch=observation_kwargs.get(
            "product_api_worker_head_branch", args.product_api_worker_head_branch
        ),
        product_api_worker_checkout_clean=observation_kwargs.get(
            "product_api_worker_checkout_clean", args.product_api_worker_checkout_clean
        ),
        product_api_worker_created_at_utc=observation_kwargs.get(
            "product_api_worker_created_at_utc", args.product_api_worker_created_at_utc
        ),
        product_api_worker_updated_at_utc=observation_kwargs.get(
            "product_api_worker_updated_at_utc", args.product_api_worker_updated_at_utc
        ),
        product_image_build_smoke_run_id=observation_kwargs.get(
            "product_image_build_smoke_run_id", args.product_image_build_smoke_run_id
        ),
        product_image_build_smoke_url=observation_kwargs.get(
            "product_image_build_smoke_url", args.product_image_build_smoke_url
        ),
        product_image_build_smoke_conclusion=observation_kwargs.get(
            "product_image_build_smoke_conclusion", args.product_image_build_smoke_conclusion
        ),
        product_image_build_smoke_job_started=observation_kwargs.get(
            "product_image_build_smoke_job_started",
            _is_truthy_text(args.product_image_build_smoke_job_started),
        ),
        product_image_build_smoke_annotation=observation_kwargs.get(
            "product_image_build_smoke_annotation", args.product_image_build_smoke_annotation
        ),
        product_image_build_smoke_head_sha=observation_kwargs.get(
            "product_image_build_smoke_head_sha", args.product_image_build_smoke_head_sha
        ),
        product_image_build_smoke_head_branch=observation_kwargs.get(
            "product_image_build_smoke_head_branch", args.product_image_build_smoke_head_branch
        ),
        product_image_build_smoke_checkout_clean=observation_kwargs.get(
            "product_image_build_smoke_checkout_clean", args.product_image_build_smoke_checkout_clean
        ),
        product_image_build_smoke_created_at_utc=observation_kwargs.get(
            "product_image_build_smoke_created_at_utc",
            args.product_image_build_smoke_created_at_utc,
        ),
        product_image_build_smoke_updated_at_utc=observation_kwargs.get(
            "product_image_build_smoke_updated_at_utc",
            args.product_image_build_smoke_updated_at_utc,
        ),
        product_image_smoke_run_id=observation_kwargs.get(
            "product_image_smoke_run_id", args.product_image_smoke_run_id
        ),
        product_image_smoke_url=observation_kwargs.get(
            "product_image_smoke_url", args.product_image_smoke_url
        ),
        product_image_smoke_conclusion=observation_kwargs.get(
            "product_image_smoke_conclusion", args.product_image_smoke_conclusion
        ),
        product_image_smoke_job_started=observation_kwargs.get(
            "product_image_smoke_job_started", _is_truthy_text(args.product_image_smoke_job_started)
        ),
        product_image_smoke_annotation=observation_kwargs.get(
            "product_image_smoke_annotation", args.product_image_smoke_annotation
        ),
        product_image_smoke_head_sha=observation_kwargs.get(
            "product_image_smoke_head_sha", args.product_image_smoke_head_sha
        ),
        product_image_smoke_head_branch=observation_kwargs.get(
            "product_image_smoke_head_branch", args.product_image_smoke_head_branch
        ),
        product_image_smoke_checkout_clean=observation_kwargs.get(
            "product_image_smoke_checkout_clean", args.product_image_smoke_checkout_clean
        ),
        product_image_smoke_created_at_utc=observation_kwargs.get(
            "product_image_smoke_created_at_utc", args.product_image_smoke_created_at_utc
        ),
        product_image_smoke_updated_at_utc=observation_kwargs.get(
            "product_image_smoke_updated_at_utc", args.product_image_smoke_updated_at_utc
        ),
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps({"status": payload["summary"]["status"], "out_json": args.out_json}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
