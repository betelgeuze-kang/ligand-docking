#!/usr/bin/env python3
"""Observe product CI GitHub Actions runs and rebuild the runtime gate.

This tool is intentionally read-only against GitHub. It lists workflow runs,
reads run jobs, and fetches failed logs to populate
``runs/product_ci_runtime_gate_current.*``. It does not dispatch workflows,
create branches, push, comment, merge, or mutate external state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any, Callable

from tools.product.build_product_ci_runtime_gate import (
    DEFAULT_OUT_JSON,
    DEFAULT_OUT_MD,
    DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    DEFAULT_SELF_HOSTED_RUNNER_HOST_PREFLIGHT_JSON,
    DEFAULT_SELF_HOSTED_RUNNER_INVENTORY_JSON,
    build_product_ci_runtime_gate,
    _write_json,
    _write_markdown,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "betelgeuze-kang/ligand-docking"
DEFAULT_BRANCH = "codex/source-of-truth-benchmark-gpcr-pocketmd"

GH_RUN_FIELDS = "databaseId,status,conclusion,createdAt,updatedAt,headSha,headBranch,url,event,name"

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def _run_json(args: list[str], *, runner: CommandRunner) -> Any:
    result = runner(args)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "gh command failed").strip())
    return json.loads(result.stdout or "null")


def _run_text(args: list[str], *, runner: CommandRunner) -> str:
    result = runner(args)
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _list_workflow_runs(
    *,
    repo: str,
    workflow: str,
    branch: str,
    limit: int,
    runner: CommandRunner,
) -> list[dict[str, Any]]:
    payload = _run_json(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--limit",
            str(limit),
            "--json",
            GH_RUN_FIELDS,
        ],
        runner=runner,
    )
    rows = payload if isinstance(payload, list) else []
    return [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("headBranch") or "") == branch
    ]


def _run_jobs(*, repo: str, run_id: str, runner: CommandRunner) -> list[dict[str, Any]]:
    payload = _run_json(
        ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs"],
        runner=runner,
    )
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    return [job for job in jobs if isinstance(job, dict)]


def _active_job(jobs: list[dict[str, Any]], *, job_name: str) -> dict[str, Any]:
    for job in jobs:
        if str(job.get("name") or "") != job_name:
            continue
        if str(job.get("conclusion") or "").lower() == "skipped":
            continue
        return job
    return {}


def _job_started(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "").lower()
    return bool(job.get("started_at") or status in {"in_progress", "completed"})


def _failure_log(*, repo: str, run_id: str, runner: CommandRunner) -> str:
    return _run_text(
        ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"],
        runner=runner,
    )


def _failure_annotation(log_text: str) -> str:
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if "##[error]" in line:
            return line.split("##[error]", 1)[1].strip()[:1000]
        if (
            "eacces" in lowered
            or "permission denied" in lowered
            or "file was unable to be removed" in lowered
        ):
            return line[:1000]
    return ""


def _checkout_clean_from_log(log_text: str) -> str:
    lowered = log_text.lower()
    if "deleting the contents of" in lowered:
        return "true"
    if "clean: false" in lowered or "clean = false" in lowered or "clean=false" in lowered:
        return "false"
    return ""


def _select_observation(
    *,
    repo: str,
    workflow: str,
    branch: str,
    job_name: str,
    limit: int,
    runner: CommandRunner,
) -> dict[str, Any]:
    for run in _list_workflow_runs(
        repo=repo,
        workflow=workflow,
        branch=branch,
        limit=limit,
        runner=runner,
    ):
        run_id = str(run.get("databaseId") or "")
        if not run_id:
            continue
        job = _active_job(_run_jobs(repo=repo, run_id=run_id, runner=runner), job_name=job_name)
        if not job:
            continue
        log_text = _failure_log(repo=repo, run_id=run_id, runner=runner)
        return {
            "run_id": run_id,
            "url": str(run.get("url") or ""),
            "conclusion": str(run.get("conclusion") or ""),
            "job_started": _job_started(job),
            "annotation": _failure_annotation(log_text),
            "checkout_clean": _checkout_clean_from_log(log_text),
            "head_sha": str(run.get("headSha") or ""),
            "head_branch": str(run.get("headBranch") or ""),
            "created_at_utc": str(run.get("createdAt") or ""),
            "updated_at_utc": str(run.get("updatedAt") or ""),
        }
    return {}


def collect_product_ci_runtime_observations(
    *,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    limit: int = 30,
    runner: CommandRunner = _default_runner,
) -> dict[str, dict[str, Any]]:
    return {
        "product_api_worker": _select_observation(
            repo=repo,
            workflow="product-api-worker.yml",
            branch=branch,
            job_name="api-worker-contract",
            limit=limit,
            runner=runner,
        ),
        "product_image_build_smoke": _select_observation(
            repo=repo,
            workflow="product-image-smoke.yml",
            branch=branch,
            job_name="product-image-build-smoke",
            limit=limit,
            runner=runner,
        ),
        "product_image_smoke": _select_observation(
            repo=repo,
            workflow="product-image-smoke.yml",
            branch=branch,
            job_name="product-image-rocm-runtime-smoke",
            limit=limit,
            runner=runner,
        ),
    }


def build_product_ci_runtime_gate_from_github(
    *,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    limit: int = 30,
    product_image_preflight_json: str | Path = DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    self_hosted_runner_inventory_json: str | Path = DEFAULT_SELF_HOSTED_RUNNER_INVENTORY_JSON,
    self_hosted_runner_host_preflight_json: str | Path = DEFAULT_SELF_HOSTED_RUNNER_HOST_PREFLIGHT_JSON,
    root: str | Path = ROOT,
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    observations = collect_product_ci_runtime_observations(
        repo=repo,
        branch=branch,
        limit=limit,
        runner=runner,
    )
    api = observations["product_api_worker"]
    build = observations["product_image_build_smoke"]
    smoke = observations["product_image_smoke"]
    payload = build_product_ci_runtime_gate(
        root=Path(root),
        product_image_preflight_json=product_image_preflight_json,
        self_hosted_runner_inventory_json=self_hosted_runner_inventory_json,
        self_hosted_runner_host_preflight_json=self_hosted_runner_host_preflight_json,
        product_api_worker_run_id=api.get("run_id", ""),
        product_api_worker_url=api.get("url", ""),
        product_api_worker_conclusion=api.get("conclusion", ""),
        product_api_worker_job_started=api.get("job_started", False),
        product_api_worker_annotation=api.get("annotation", ""),
        product_api_worker_head_sha=api.get("head_sha", ""),
        product_api_worker_head_branch=api.get("head_branch", ""),
        product_api_worker_checkout_clean=api.get("checkout_clean", ""),
        product_api_worker_created_at_utc=api.get("created_at_utc", ""),
        product_api_worker_updated_at_utc=api.get("updated_at_utc", ""),
        product_image_build_smoke_run_id=build.get("run_id", ""),
        product_image_build_smoke_url=build.get("url", ""),
        product_image_build_smoke_conclusion=build.get("conclusion", ""),
        product_image_build_smoke_job_started=build.get("job_started", False),
        product_image_build_smoke_annotation=build.get("annotation", ""),
        product_image_build_smoke_head_sha=build.get("head_sha", ""),
        product_image_build_smoke_head_branch=build.get("head_branch", ""),
        product_image_build_smoke_checkout_clean=build.get("checkout_clean", ""),
        product_image_build_smoke_created_at_utc=build.get("created_at_utc", ""),
        product_image_build_smoke_updated_at_utc=build.get("updated_at_utc", ""),
        product_image_smoke_run_id=smoke.get("run_id", ""),
        product_image_smoke_url=smoke.get("url", ""),
        product_image_smoke_conclusion=smoke.get("conclusion", ""),
        product_image_smoke_job_started=smoke.get("job_started", False),
        product_image_smoke_annotation=smoke.get("annotation", ""),
        product_image_smoke_head_sha=smoke.get("head_sha", ""),
        product_image_smoke_head_branch=smoke.get("head_branch", ""),
        product_image_smoke_checkout_clean=smoke.get("checkout_clean", ""),
        product_image_smoke_created_at_utc=smoke.get("created_at_utc", ""),
        product_image_smoke_updated_at_utc=smoke.get("updated_at_utc", ""),
    )
    payload["summary"]["github_observation_repo"] = repo
    payload["summary"]["github_observation_branch"] = branch
    payload["summary"]["github_observation_external_state_mutated"] = False
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read GitHub Actions product CI runs and rebuild product CI runtime gate evidence."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--self-hosted-runner-inventory-json", default=DEFAULT_SELF_HOSTED_RUNNER_INVENTORY_JSON)
    parser.add_argument(
        "--self-hosted-runner-host-preflight-json",
        default=DEFAULT_SELF_HOSTED_RUNNER_HOST_PREFLIGHT_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--root", default=str(ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root)
    payload = build_product_ci_runtime_gate_from_github(
        repo=args.repo,
        branch=args.branch,
        limit=args.limit,
        product_image_preflight_json=args.product_image_preflight_json,
        self_hosted_runner_inventory_json=args.self_hosted_runner_inventory_json,
        self_hosted_runner_host_preflight_json=args.self_hosted_runner_host_preflight_json,
        root=root,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["status"],
                "out_json": args.out_json,
                "github_observation_branch": args.branch,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
