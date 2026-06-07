from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from deploy import product_rollout as mod


def test_rollout_plan_includes_target_action_risk_rollback_verification() -> None:
    args = mod.argparse.Namespace(
        mode="k8s",
        image="micf-api:product",
        publish_image="registry.local/micf-api:sha",
        push=True,
        dockerfile="Dockerfile.product",
        compose_file="deploy/docker-compose.product.yml",
        compose_api_port="8000",
        k8s_dir="deploy/k8s",
        namespace="micf-product",
        rollout_timeout="180s",
        execute=False,
        approval_token="",
        out_json="",
    )

    plan = mod.build_rollout_plan(args)

    assert plan["status"] == "planned"
    assert plan["dry_run"] is True
    assert plan["approval_token_required"] == "APPROVE_PRODUCT_ROLLOUT"
    assert plan["target"]["publish_image"] == "registry.local/micf-api:sha"
    assert "Build product API image" in plan["action"]
    assert "Can publish a container image" in plan["impact"]
    assert "interrupt the self-hosted product API" in plan["risk"]
    assert any("previous image digest" in row for row in plan["rollback"])
    assert any("/metrics" in row for row in plan["verification"])

    stages = [row["stage"] for row in plan["commands"]]
    assert stages == [
        "docker_build",
        "docker_tag",
        "docker_push",
        "k8s_apply",
        "k8s_set_api_image",
        "k8s_set_worker_image",
        "k8s_rollout_status_micf-api-server",
        "k8s_rollout_status_micf-api-worker",
    ]
    assert any(row["mutates_external_state"] for row in plan["commands"])


def test_rollout_execute_requires_approval_token(tmp_path: Path) -> None:
    out_json = tmp_path / "rollout.json"
    result = subprocess.run(
        [
            sys.executable,
            "deploy/product_rollout.py",
            "--mode",
            "build-only",
            "--execute",
            "--out-json",
            str(out_json),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_approval_required"
    assert payload["approval_token_required"] == "APPROVE_PRODUCT_ROLLOUT"
    assert json.loads(out_json.read_text(encoding="utf-8"))["status"] == "blocked_approval_required"


def test_rollout_dry_run_cli_writes_plan_without_executing(tmp_path: Path) -> None:
    out_json = tmp_path / "plan.json"
    result = subprocess.run(
        [
            sys.executable,
            "deploy/product_rollout.py",
            "--mode",
            "compose",
            "--image",
            "micf-api:product",
            "--out-json",
            str(out_json),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "planned"
    assert saved["dry_run"] is True
    assert "results" not in saved
    assert any(row["stage"] == "compose_up" for row in saved["commands"])
