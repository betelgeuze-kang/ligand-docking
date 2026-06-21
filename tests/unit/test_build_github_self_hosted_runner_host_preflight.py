from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_github_self_hosted_runner_host_preflight as mod


def _write_product_preflight(path: Path, *, ready: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_image_smoke_preflight_ready"
                    if ready
                    else "blocked_product_image_smoke_preflight",
                    "receipt_status": "product_image_smoke_ready" if ready else "",
                    "receipt_mode": "rocm-runtime" if ready else "build",
                    "clean_container_smoke_ready": ready,
                    "container_runtime_receipt_ready": ready,
                    "container_runtime_rust_hip_backend_enabled": ready,
                    "product_runner_claim_metadata_ready": ready,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_runner_inventory(path: Path, runners: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"total_count": len(runners), "runners": runners}) + "\n",
        encoding="utf-8",
    )


def test_self_hosted_runner_host_preflight_blocks_only_registration_when_local_rocm_ready(
    tmp_path: Path,
) -> None:
    product_preflight = tmp_path / "product_image_smoke_preflight_current.json"
    runner_inventory = tmp_path / "github_self_hosted_runner_inventory_current.json"
    _write_product_preflight(product_preflight, ready=True)
    _write_runner_inventory(runner_inventory, [])

    payload = mod.build_github_self_hosted_runner_host_preflight(
        root=tmp_path,
        product_image_preflight_json=product_preflight,
        runner_inventory_json=runner_inventory,
        docker_cli_present=True,
        docker_daemon_accessible=True,
        rocm_device_nodes_ready=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_github_self_hosted_runner_registration_required"
    assert summary["local_runner_host_ready"] is True
    assert summary["repo_self_hosted_runner_ready"] is False
    assert summary["repo_runner_registration_required"] is True
    assert summary["runner_inventory_total_count"] == 0
    assert summary["linux_runner_online_count"] == 0
    assert summary["rocm_runner_online_count"] == 0
    assert summary["github_registration_token_requested"] is False
    assert summary["external_state_mutated"] is False
    assert {"code": "github_self_hosted_runner_registration_required"} in payload["blockers"]
    assert {"code": "github_self_hosted_linux_runner_not_online"} in payload["blockers"]
    assert {"code": "github_self_hosted_rocm_runner_not_online"} in payload["blockers"]
    assert "rocm" == summary["recommended_rocm_custom_label"]
    assert any("Rerun ROCm runtime smoke" in step for step in summary["next_required_steps"])


def test_self_hosted_runner_host_preflight_ready_when_repo_runner_online(tmp_path: Path) -> None:
    product_preflight = tmp_path / "product_image_smoke_preflight_current.json"
    runner_inventory = tmp_path / "github_self_hosted_runner_inventory_current.json"
    _write_product_preflight(product_preflight, ready=True)
    _write_runner_inventory(
        runner_inventory,
        [
            {
                "name": "local-rocm-runner",
                "status": "online",
                "labels": [{"name": "self-hosted"}, {"name": "linux"}, {"name": "rocm"}],
            }
        ],
    )

    payload = mod.build_github_self_hosted_runner_host_preflight(
        root=tmp_path,
        product_image_preflight_json=product_preflight,
        runner_inventory_json=runner_inventory,
        docker_cli_present=True,
        docker_daemon_accessible=True,
        rocm_device_nodes_ready=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "github_self_hosted_runner_host_preflight_ready"
    assert summary["local_runner_host_ready"] is True
    assert summary["repo_self_hosted_runner_ready"] is True
    assert summary["repo_runner_registration_required"] is False
    assert summary["linux_runner_online_count"] == 1
    assert summary["rocm_runner_online_count"] == 1
    assert payload["blockers"] == []
    assert all("create a Linux x64 self-hosted runner" not in step for step in summary["next_required_steps"])
    assert any("Rerun API worker" in step for step in summary["next_required_steps"])
    assert any("Rerun ROCm runtime smoke" in step for step in summary["next_required_steps"])


def test_self_hosted_runner_host_preflight_blocks_local_host_without_docker_or_rocm(
    tmp_path: Path,
) -> None:
    product_preflight = tmp_path / "product_image_smoke_preflight_current.json"
    runner_inventory = tmp_path / "github_self_hosted_runner_inventory_current.json"
    _write_product_preflight(product_preflight, ready=False)
    _write_runner_inventory(runner_inventory, [])

    payload = mod.build_github_self_hosted_runner_host_preflight(
        root=tmp_path,
        product_image_preflight_json=product_preflight,
        runner_inventory_json=runner_inventory,
        docker_cli_present=False,
        docker_daemon_accessible=False,
        rocm_device_nodes_ready=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_github_self_hosted_runner_host_preflight"
    assert summary["local_runner_host_ready"] is False
    assert {"code": "docker_cli_missing"} in payload["blockers"]
    assert {"code": "docker_daemon_unreachable"} in payload["blockers"]
    assert {"code": "rocm_device_nodes_missing"} in payload["blockers"]
    assert {"code": "product_image_rocm_runtime_receipt_missing"} in payload["blockers"]
