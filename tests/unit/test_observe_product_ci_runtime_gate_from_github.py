from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.product import observe_product_ci_runtime_gate_from_github as mod


def _completed(args: list[str], payload: object | str) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")


def _write_preflight(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_image_smoke_preflight_ready",
                    "clean_container_smoke_ready": True,
                    "receipt_status": "product_image_smoke_ready",
                    "receipt_mode": "rocm-runtime",
                    "container_runtime_receipt_ready": True,
                    "container_runtime_rust_hip_backend_enabled": True,
                    "product_runner_smoke_ready": True,
                    "receipt_runner_hygiene_ready": True,
                    "receipt_runner_smoke_dir_outside_workspace": True,
                    "receipt_container_output_uid_gid_pinned": True,
                    "receipt_container_output_uid_gid_matches_host": True,
                    "receipt_container_output_uid_gid_non_root": True,
                    "receipt_workspace_runner_smoke_dir_cleanup_ready": True,
                    "receipt_runner_hygiene_blockers": [],
                    "workflow_contract_ready": True,
                    "workflow_workspace_artifact_recovery_ready": True,
                    "runner_smoke_dir_contract_ready": True,
                }
            }
        ),
        encoding="utf-8",
    )


def test_observe_product_ci_runtime_gate_from_github_rebuilds_workspace_cleanup_gate(
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "product_image_smoke_preflight_current.json"
    _write_preflight(preflight)
    calls: list[list[str]] = []
    branch = "codex/pr38-ci-runner-hygiene"
    sha = "f28bab0aa1067b154b1f6dc7ce8a774274ba1cc6"
    repo = "example/repo"
    runs_by_workflow = {
        "product-api-worker.yml": [
            {
                "databaseId": 101,
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-07-05T07:22:22Z",
                "updatedAt": "2026-07-05T07:22:36Z",
                "headSha": sha,
                "headBranch": branch,
                "url": "https://github.com/example/repo/actions/runs/101",
                "event": "workflow_dispatch",
                "name": "product-api-worker",
            }
        ],
        "product-image-smoke.yml": [
            {
                "databaseId": 303,
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-07-05T07:22:25Z",
                "updatedAt": "2026-07-05T07:23:03Z",
                "headSha": sha,
                "headBranch": branch,
                "url": "https://github.com/example/repo/actions/runs/303",
                "event": "workflow_dispatch",
                "name": "product-image-smoke",
            },
            {
                "databaseId": 202,
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-07-05T07:22:23Z",
                "updatedAt": "2026-07-05T07:22:49Z",
                "headSha": sha,
                "headBranch": branch,
                "url": "https://github.com/example/repo/actions/runs/202",
                "event": "workflow_dispatch",
                "name": "product-image-smoke",
            },
        ],
    }
    jobs_by_run = {
        "101": [{"name": "api-worker-contract", "status": "completed", "conclusion": "failure", "started_at": "2026-07-05T07:22:26Z"}],
        "202": [
            {"name": "product-image-build-smoke", "status": "completed", "conclusion": "failure", "started_at": "2026-07-05T07:22:38Z"},
            {"name": "product-image-rocm-runtime-smoke", "status": "completed", "conclusion": "skipped", "started_at": "2026-07-05T07:22:25Z"},
        ],
        "303": [
            {"name": "product-image-rocm-runtime-smoke", "status": "completed", "conclusion": "failure", "started_at": "2026-07-05T07:22:50Z"},
            {"name": "product-image-build-smoke", "status": "completed", "conclusion": "skipped", "started_at": "2026-07-05T07:22:26Z"},
        ],
    }
    log = (
        "Checkout\t2026-07-05T07:22:41Z Deleting the contents of '/runner/work/repo/repo'\n"
        "Checkout\t2026-07-05T07:22:41Z ##[error]File was unable to be removed "
        "Error: EACCES: permission denied, unlink 'runs/product_image_smoke_runner_artifacts/backmapping_out/summary.md'\n"
    )

    def fake_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ["gh", "run", "list"]:
            workflow = args[args.index("--workflow") + 1]
            return _completed(args, runs_by_workflow[workflow])
        if args[:2] == ["gh", "api"]:
            run_id = args[2].split("/runs/", 1)[1].split("/jobs", 1)[0]
            return _completed(args, {"jobs": jobs_by_run[run_id]})
        if args[:3] == ["gh", "run", "view"]:
            return _completed(args, log)
        raise AssertionError(f"unexpected command: {args}")

    payload = mod.build_product_ci_runtime_gate_from_github(
        repo=repo,
        branch=branch,
        root=tmp_path,
        product_image_preflight_json=preflight,
        runner=fake_runner,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_ci_runtime_gate"
    assert summary["primary_blocker"] == "github_actions_workspace_cleanup_permission_denied"
    assert summary["remote_ci_failure_class"] == "workspace_cleanup_permission"
    assert summary["remote_ci_observed_checkout_clean_mode"] == "true"
    assert summary["product_api_worker_run_id"] == "101"
    assert summary["product_image_build_smoke_run_id"] == "202"
    assert summary["product_image_smoke_run_id"] == "303"
    assert summary["product_image_smoke_head_branch"] == branch
    assert summary["github_observation_repo"] == repo
    assert summary["github_observation_branch"] == branch
    assert summary["github_observation_external_state_mutated"] is False
    assert {"code": "github_actions_workspace_cleanup_permission_denied"} in payload["blockers"]
    assert not any(call[:3] == ["gh", "workflow", "run"] for call in calls)
