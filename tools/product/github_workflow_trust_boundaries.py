#!/usr/bin/env python3
"""Semantic policy for untrusted and trusted GitHub Actions workflows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


WORKFLOW_DIR = Path(".github/workflows")
FULL_SHA_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")

PR_WORKFLOWS = {
    "ci-api-h4-hosted.yml": {"api-security"},
    "product-api-worker.yml": {"api-worker-contract"},
    "product-image-smoke.yml": {"product-image-build-smoke"},
}

TRUSTED_WORKFLOWS = {
    "product-api-worker-trusted.yml": {
        "triggers": {"push", "workflow_dispatch"},
        "jobs": {
            "api-worker-contract-trusted": {
                "runs_on": ["self-hosted", "linux"],
                "condition": (
                    "${{ vars.TRUSTED_SELF_HOSTED_CI_ENABLED == 'true' "
                    "&& ((github.event_name == 'push' "
                    "&& (github.ref == 'refs/heads/main' "
                    "|| startsWith(github.ref, 'refs/tags/v') "
                    "|| startsWith(github.ref, 'refs/tags/product-'))) "
                    "|| (github.event_name == 'workflow_dispatch' "
                    "&& (github.ref == 'refs/heads/main' "
                    "|| startsWith(github.ref, 'refs/tags/v') "
                    "|| startsWith(github.ref, 'refs/tags/product-')))) }}"
                ),
                "temp_tokens": (
                    'artifact_root="${RUNNER_TEMP}/product-api-worker-',
                    'ln -s "${artifact_root}" product-ci-checkout/runs',
                ),
            },
        },
    },
    "product-image-smoke-trusted.yml": {
        "triggers": {"push", "schedule", "workflow_dispatch"},
        "jobs": {
            "product-image-build-smoke-trusted": {
                "runs_on": ["self-hosted", "linux"],
                "condition": (
                    "${{ vars.TRUSTED_SELF_HOSTED_CI_ENABLED == 'true' "
                    "&& ((github.event_name == 'push' && github.ref == 'refs/heads/main') "
                    "|| (github.event_name == 'workflow_dispatch' "
                    "&& github.event.inputs.verify_mode == 'build' "
                    "&& (github.ref == 'refs/heads/main' "
                    "|| startsWith(github.ref, 'refs/tags/v') "
                    "|| startsWith(github.ref, 'refs/tags/product-')))) }}"
                ),
                "temp_tokens": (
                    'artifact_root="${RUNNER_TEMP}/product-image-build-',
                    'smoke_root="${RUNNER_TEMP}/product-image-build-smoke-',
                    'ln -s "${artifact_root}" product-ci-checkout/runs',
                ),
                "upload_paths": (
                    "${{ runner.temp }}/product-image-build-${{ github.run_id }}-${{ github.run_attempt }}/**",
                    "${{ runner.temp }}/product-image-build-smoke-${{ github.run_id }}-${{ github.run_attempt }}/**",
                ),
            },
            "product-image-rocm-runtime-smoke": {
                "runs_on": ["self-hosted", "linux", "rocm"],
                "condition": (
                    "${{ vars.TRUSTED_SELF_HOSTED_CI_ENABLED == 'true' "
                    "&& (github.event_name == 'schedule' "
                    "|| (github.event_name == 'push' "
                    "&& startsWith(github.ref, 'refs/tags/v')) "
                    "|| (github.event_name == 'push' "
                    "&& startsWith(github.ref, 'refs/tags/product-')) "
                    "|| (github.event_name == 'workflow_dispatch' "
                    "&& github.event.inputs.verify_mode == 'rocm-runtime' "
                    "&& (github.ref == 'refs/heads/main' "
                    "|| startsWith(github.ref, 'refs/tags/v') "
                    "|| startsWith(github.ref, 'refs/tags/product-')))) }}"
                ),
                "temp_tokens": (
                    'artifact_root="${RUNNER_TEMP}/product-image-rocm-',
                    'smoke_root="${RUNNER_TEMP}/product-image-rocm-smoke-',
                    'ln -s "${artifact_root}" product-ci-checkout/runs',
                ),
                "upload_paths": (
                    "${{ runner.temp }}/product-image-rocm-${{ github.run_id }}-${{ github.run_attempt }}/**",
                    "${{ runner.temp }}/product-image-rocm-smoke-${{ github.run_id }}-${{ github.run_attempt }}/**",
                ),
            },
        },
    },
}


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").split())


def _checkout_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for step in job.get("steps", [])
        if isinstance(step, dict)
        and str(step.get("uses", "")).startswith("actions/checkout@")
    ]


def _run_source(job: dict[str, Any]) -> str:
    return "\n".join(
        str(step.get("run", ""))
        for step in job.get("steps", [])
        if isinstance(step, dict)
    )


def _validate_checkout(
    workflow_name: str,
    job_id: str,
    job: dict[str, Any],
    errors: list[str],
) -> None:
    checkouts = _checkout_steps(job)
    if not checkouts:
        errors.append(f"{workflow_name}:{job_id}:missing_checkout")
        return
    for checkout in checkouts:
        options = checkout.get("with", {})
        if options.get("persist-credentials") != "false":
            errors.append(f"{workflow_name}:{job_id}:checkout_credentials_persisted")
        if options.get("clean") != "true":
            errors.append(f"{workflow_name}:{job_id}:checkout_not_clean")


def _validate_pinned_actions(
    workflow_name: str,
    jobs: dict[str, Any],
    errors: list[str],
) -> None:
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            errors.append(f"{workflow_name}:{job_id}:job_not_mapping")
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            uses = str(step.get("uses", ""))
            if not uses or uses.startswith("./") or uses.startswith("docker://"):
                continue
            if FULL_SHA_ACTION.fullmatch(uses) is None:
                errors.append(f"{workflow_name}:{job_id}:action_not_sha_pinned:{uses}")


def audit_workflow_trust_boundaries(root: str | Path) -> list[str]:
    root_path = Path(root)
    workflow_dir = root_path / WORKFLOW_DIR
    errors: list[str] = []

    for workflow_name, expected_jobs in PR_WORKFLOWS.items():
        path = workflow_dir / workflow_name
        if not path.is_file():
            errors.append(f"{workflow_name}:workflow_missing")
            continue
        workflow = _load(path)
        triggers = workflow.get("on", {})
        jobs = workflow.get("jobs", {})
        if set(triggers) != {"pull_request"}:
            errors.append(f"{workflow_name}:unexpected_triggers")
        if workflow.get("permissions") != {"contents": "read"}:
            errors.append(f"{workflow_name}:permissions_not_read_only")
        if set(jobs) != expected_jobs:
            errors.append(f"{workflow_name}:unexpected_jobs")
        if "self-hosted" in path.read_text(encoding="utf-8").lower():
            errors.append(f"{workflow_name}:self_hosted_token_in_pr_workflow")
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                errors.append(f"{workflow_name}:{job_id}:job_not_mapping")
                continue
            if _normalize(job.get("if")) != "${{ github.event_name == 'pull_request' }}":
                errors.append(f"{workflow_name}:{job_id}:condition_not_exact_pr")
            if job.get("runs-on") != "ubuntu-latest":
                errors.append(f"{workflow_name}:{job_id}:runner_not_hosted")
            if "uses" in job:
                errors.append(f"{workflow_name}:{job_id}:reusable_workflow_forbidden")
            lowered = _run_source(job).lower()
            for token in ("sudo", " chown", " chmod", "/dev/kfd", "/dev/dri"):
                if token in lowered:
                    errors.append(f"{workflow_name}:{job_id}:forbidden_run_token:{token.strip()}")
            _validate_checkout(workflow_name, job_id, job, errors)
        _validate_pinned_actions(workflow_name, jobs, errors)

    for workflow_name, policy in TRUSTED_WORKFLOWS.items():
        path = workflow_dir / workflow_name
        if not path.is_file():
            errors.append(f"{workflow_name}:workflow_missing")
            continue
        workflow = _load(path)
        triggers = workflow.get("on", {})
        jobs = workflow.get("jobs", {})
        if set(triggers) != policy["triggers"]:
            errors.append(f"{workflow_name}:unexpected_triggers")
        if "pull_request" in triggers or "pull_request_target" in triggers:
            errors.append(f"{workflow_name}:untrusted_trigger")
        if workflow.get("permissions") != {"contents": "read"}:
            errors.append(f"{workflow_name}:permissions_not_read_only")
        if set(jobs) != set(policy["jobs"]):
            errors.append(f"{workflow_name}:unexpected_jobs")
        push = triggers.get("push", {})
        if push.get("branches") != ["main"]:
            errors.append(f"{workflow_name}:push_branches_not_main_only")
        if set(push.get("tags", [])) != {"v*", "product-*"}:
            errors.append(f"{workflow_name}:push_tags_not_allowlisted")
        for job_id, job_policy in policy["jobs"].items():
            job = jobs.get(job_id, {})
            if _normalize(job.get("if")) != _normalize(job_policy["condition"]):
                errors.append(f"{workflow_name}:{job_id}:condition_not_allowlisted")
            if job.get("runs-on") != job_policy["runs_on"]:
                errors.append(f"{workflow_name}:{job_id}:runner_not_literal_allowlist")
            steps = job.get("steps", [])
            if not steps or not str(steps[0].get("uses", "")).startswith("actions/checkout@"):
                errors.append(f"{workflow_name}:{job_id}:checkout_not_first")
            _validate_checkout(workflow_name, job_id, job, errors)
            source = _run_source(job)
            if "${GITHUB_WORKSPACE}" in source:
                errors.append(f"{workflow_name}:{job_id}:workspace_artifact_root")
            for token in job_policy["temp_tokens"]:
                if token not in source:
                    errors.append(f"{workflow_name}:{job_id}:missing_temp_contract:{token}")
            expected_upload_paths = job_policy.get("upload_paths")
            if expected_upload_paths is not None:
                upload_steps = [
                    step
                    for step in steps
                    if str(step.get("uses", "")).startswith("actions/upload-artifact@")
                ]
                if len(upload_steps) != 1:
                    errors.append(f"{workflow_name}:{job_id}:artifact_upload_count")
                else:
                    upload_step = upload_steps[0]
                    actual_paths = tuple(
                        line.strip()
                        for line in str(upload_step.get("with", {}).get("path", "")).splitlines()
                        if line.strip()
                    )
                    if actual_paths != expected_upload_paths:
                        errors.append(f"{workflow_name}:{job_id}:artifact_paths_not_allowlisted")
                    if _normalize(upload_step.get("if")) != "always()":
                        errors.append(f"{workflow_name}:{job_id}:artifact_upload_not_always")
        _validate_pinned_actions(workflow_name, jobs, errors)

    for path in sorted(workflow_dir.glob("*.y*ml")):
        workflow = _load(path)
        triggers = workflow.get("on", {})
        if "pull_request_target" in triggers:
            errors.append(f"{path.name}:pull_request_target_forbidden")
        if "pull_request" not in triggers:
            continue
        for job_id, job in workflow.get("jobs", {}).items():
            if not isinstance(job, dict):
                errors.append(f"{path.name}:{job_id}:job_not_mapping")
                continue
            if "uses" in job:
                errors.append(f"{path.name}:{job_id}:reusable_pr_job_forbidden")
            if job.get("runs-on") != "ubuntu-latest":
                errors.append(f"{path.name}:{job_id}:pr_runner_not_hosted")
            if "sudo" in _run_source(job).lower():
                errors.append(f"{path.name}:{job_id}:sudo_in_pr_job")

    return sorted(set(errors))


def workflow_trust_boundaries_ready(root: str | Path) -> bool:
    return not audit_workflow_trust_boundaries(root)
