from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_ci_runtime_gate as mod


def _write_preflight(path: Path, *, ready: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_image_smoke_preflight_ready"
                    if ready
                    else "blocked_product_image_smoke_preflight",
                    "clean_container_smoke_ready": ready,
                    "receipt_status": "product_image_smoke_ready" if ready else "",
                    "receipt_mode": "rocm-runtime" if ready else "",
                    "container_runtime_receipt_ready": ready,
                    "container_runtime_rust_hip_backend_enabled": ready,
                    "product_runner_smoke_ready": ready,
                }
            }
        ),
        encoding="utf-8",
    )


def _write_runner_inventory(path: Path, runners: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"total_count": len(runners), "runners": runners}),
        encoding="utf-8",
    )


def _write_runner_host_preflight(path: Path, *, local_ready: bool = True, repo_ready: bool = False) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": (
                        "github_self_hosted_runner_host_preflight_ready"
                        if repo_ready
                        else "blocked_github_self_hosted_runner_registration_required"
                    ),
                    "local_runner_host_ready": local_ready,
                    "repo_self_hosted_runner_ready": repo_ready,
                    "repo_runner_registration_required": not repo_ready,
                    "docker_daemon_accessible": local_ready,
                    "rocm_device_nodes_ready": local_ready,
                    "product_image_rocm_runtime_ready": local_ready,
                    "github_registration_token_requested": False,
                    "runner_configured": repo_ready,
                    "runner_service_started": repo_ready,
                    "external_state_mutated": False,
                }
            }
        ),
        encoding="utf-8",
    )


def test_product_ci_runtime_gate_blocks_github_billing_without_mutation(tmp_path: Path) -> None:
    preflight = tmp_path / "product_image_smoke_preflight_current.json"
    runner_inventory = tmp_path / "github_self_hosted_runner_inventory_current.json"
    runner_host_preflight = tmp_path / "github_self_hosted_runner_host_preflight_current.json"
    _write_preflight(preflight)
    _write_runner_inventory(runner_inventory, [])
    _write_runner_host_preflight(runner_host_preflight, local_ready=True, repo_ready=False)
    annotation = (
        "The job was not started because recent account payments have failed or your spending limit "
        "needs to be increased."
    )

    payload = mod.build_product_ci_runtime_gate(
        root=tmp_path,
        product_image_preflight_json=preflight,
        self_hosted_runner_inventory_json=runner_inventory,
        self_hosted_runner_host_preflight_json=runner_host_preflight,
        product_api_worker_run_id="27770545121",
        product_api_worker_url="https://github.com/example/actions/runs/27770545121",
        product_api_worker_conclusion="failure",
        product_api_worker_job_started=False,
        product_api_worker_annotation=annotation,
        product_api_worker_created_at_utc="2026-06-20T15:26:47Z",
        product_image_smoke_run_id="27770546783",
        product_image_smoke_url="https://github.com/example/actions/runs/27770546783",
        product_image_smoke_conclusion="failure",
        product_image_smoke_job_started=False,
        product_image_smoke_annotation=annotation,
        product_image_smoke_created_at_utc="2026-06-20T15:26:47Z",
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_ci_runtime_gate"
    assert summary["runtime_gate_ready"] is False
    assert summary["remote_product_ci_green"] is False
    assert summary["github_actions_started"] is False
    assert summary["external_blocker"] is True
    assert summary["blocker_code"] == "github_actions_billing_or_spending_limit"
    assert summary["billing_free_self_hosted_path_recommended"] is True
    assert summary["hosted_spending_limit_increase_required"] is False
    assert summary["self_hosted_runner_inventory_present"] is True
    assert summary["self_hosted_runner_total_count"] == 0
    assert summary["self_hosted_linux_runner_online"] is False
    assert summary["self_hosted_linux_runner_count"] == 0
    assert summary["self_hosted_rocm_runner_online"] is False
    assert summary["self_hosted_rocm_runner_count"] == 0
    assert summary["self_hosted_runner_inventory_external_state_mutated"] is False
    assert summary["self_hosted_runner_host_preflight_present"] is True
    assert summary["self_hosted_runner_host_local_ready"] is True
    assert summary["self_hosted_runner_host_repo_ready"] is False
    assert summary["self_hosted_runner_host_registration_required"] is True
    assert summary["self_hosted_runner_host_docker_daemon_accessible"] is True
    assert summary["self_hosted_runner_host_rocm_device_nodes_ready"] is True
    assert summary["self_hosted_runner_host_product_image_rocm_runtime_ready"] is True
    assert summary["self_hosted_runner_host_github_registration_token_requested"] is False
    assert summary["self_hosted_runner_host_external_state_mutated"] is False
    assert summary["billing_free_self_hosted_api_worker_command"] == (
        "gh workflow run product-api-worker.yml -f runner_labels_json='[\"self-hosted\",\"linux\"]'"
    )
    assert summary["billing_free_self_hosted_rocm_runtime_command"] == (
        "gh workflow run product-image-smoke.yml -f verify_mode=rocm-runtime"
    )
    assert summary["local_rocm_clean_container_ready"] is True
    assert summary["workflow_dispatch_executed"] is False
    assert summary["latest_github_actions_record_kst_date"] == "2026-06-21"
    assert summary["github_actions_record_dates_kst"] == ["2026-06-21"]
    assert summary["billing_mutated"] is False
    assert summary["external_state_mutated"] is False
    assert {"code": "github_actions_billing_or_spending_limit"} in payload["blockers"]
    assert {"code": "self_hosted_linux_runner_missing"} in payload["blockers"]
    assert {"code": "self_hosted_rocm_runner_missing"} in payload["blockers"]
    assert {"code": "self_hosted_runner_registration_required"} in payload["blockers"]
    assert {"code": "product-api-worker_not_green"} in payload["blockers"]
    assert {"code": "product-image-smoke_not_green"} in payload["blockers"]
    assert any("self-hosted runners" in step for step in summary["next_required_steps"])
    assert any("self-hosted, linux" in step for step in summary["next_required_steps"])
    assert any("self-hosted, linux, rocm" in step for step in summary["next_required_steps"])
    assert any("runner_labels_json" in step for step in summary["next_required_steps"])
    assert not any(step.startswith("Owner resolves GitHub Billing") for step in summary["next_required_steps"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])
    assert {row["created_at_kst_date"] for row in payload["rows"]} == {"2026-06-21"}


def test_product_ci_runtime_gate_ready_requires_remote_green_and_local_rocm_preflight(
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "product_image_smoke_preflight_current.json"
    _write_preflight(preflight)

    payload = mod.build_product_ci_runtime_gate(
        root=tmp_path,
        product_image_preflight_json=preflight,
        product_api_worker_run_id="1",
        product_api_worker_conclusion="success",
        product_api_worker_job_started=True,
        product_image_smoke_run_id="2",
        product_image_smoke_conclusion="success",
        product_image_smoke_job_started=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_ci_runtime_gate_ready"
    assert summary["runtime_gate_ready"] is True
    assert summary["remote_product_ci_green"] is True
    assert summary["github_actions_started"] is True
    assert summary["local_rocm_clean_container_ready"] is True
    assert summary["billing_free_self_hosted_path_recommended"] is False
    assert summary["hosted_spending_limit_increase_required"] is False
    assert payload["blockers"] == []


def test_product_ci_runtime_gate_detects_online_self_hosted_runner_labels(tmp_path: Path) -> None:
    preflight = tmp_path / "product_image_smoke_preflight_current.json"
    runner_inventory = tmp_path / "github_self_hosted_runner_inventory_current.json"
    runner_host_preflight = tmp_path / "github_self_hosted_runner_host_preflight_current.json"
    _write_preflight(preflight)
    _write_runner_host_preflight(runner_host_preflight, local_ready=True, repo_ready=True)
    _write_runner_inventory(
        runner_inventory,
        [
            {
                "name": "local-linux",
                "status": "online",
                "labels": [{"name": "self-hosted"}, {"name": "linux"}],
            },
            {
                "name": "local-rocm",
                "status": "online",
                "labels": [{"name": "self-hosted"}, {"name": "linux"}, {"name": "rocm"}],
            },
        ],
    )
    annotation = "spending limit reached"

    payload = mod.build_product_ci_runtime_gate(
        root=tmp_path,
        product_image_preflight_json=preflight,
        self_hosted_runner_inventory_json=runner_inventory,
        self_hosted_runner_host_preflight_json=runner_host_preflight,
        product_api_worker_conclusion="failure",
        product_api_worker_annotation=annotation,
        product_image_smoke_conclusion="failure",
        product_image_smoke_annotation=annotation,
    )
    summary = payload["summary"]

    assert summary["billing_free_self_hosted_path_recommended"] is True
    assert summary["self_hosted_runner_total_count"] == 2
    assert summary["self_hosted_linux_runner_online"] is True
    assert summary["self_hosted_linux_runner_count"] == 2
    assert summary["self_hosted_rocm_runner_online"] is True
    assert summary["self_hosted_rocm_runner_count"] == 1
    assert summary["self_hosted_runner_host_local_ready"] is True
    assert summary["self_hosted_runner_host_repo_ready"] is True
    assert summary["self_hosted_runner_host_registration_required"] is False
    assert {"code": "self_hosted_linux_runner_missing"} not in payload["blockers"]
    assert {"code": "self_hosted_rocm_runner_missing"} not in payload["blockers"]
    assert {"code": "self_hosted_runner_registration_required"} not in payload["blockers"]


def test_product_ci_runtime_gate_rejects_remote_green_without_local_rocm_preflight(
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "product_image_smoke_preflight_current.json"
    _write_preflight(preflight, ready=False)

    payload = mod.build_product_ci_runtime_gate(
        root=tmp_path,
        product_image_preflight_json=preflight,
        product_api_worker_run_id="1",
        product_api_worker_conclusion="success",
        product_api_worker_job_started=True,
        product_image_smoke_run_id="2",
        product_image_smoke_conclusion="success",
        product_image_smoke_job_started=True,
    )

    assert payload["summary"]["status"] == "blocked_product_ci_runtime_gate"
    assert payload["summary"]["remote_product_ci_green"] is True
    assert payload["summary"]["local_rocm_clean_container_ready"] is False
    assert {"code": "local_rocm_clean_container_evidence_missing"} in payload["blockers"]
