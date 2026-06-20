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


def test_product_ci_runtime_gate_blocks_github_billing_without_mutation(tmp_path: Path) -> None:
    preflight = tmp_path / "product_image_smoke_preflight_current.json"
    _write_preflight(preflight)
    annotation = (
        "The job was not started because recent account payments have failed or your spending limit "
        "needs to be increased."
    )

    payload = mod.build_product_ci_runtime_gate(
        root=tmp_path,
        product_image_preflight_json=preflight,
        product_api_worker_run_id="27770545121",
        product_api_worker_url="https://github.com/example/actions/runs/27770545121",
        product_api_worker_conclusion="failure",
        product_api_worker_job_started=False,
        product_api_worker_annotation=annotation,
        product_image_smoke_run_id="27770546783",
        product_image_smoke_url="https://github.com/example/actions/runs/27770546783",
        product_image_smoke_conclusion="failure",
        product_image_smoke_job_started=False,
        product_image_smoke_annotation=annotation,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_ci_runtime_gate"
    assert summary["runtime_gate_ready"] is False
    assert summary["remote_product_ci_green"] is False
    assert summary["github_actions_started"] is False
    assert summary["external_blocker"] is True
    assert summary["blocker_code"] == "github_actions_billing_or_spending_limit"
    assert summary["local_rocm_clean_container_ready"] is True
    assert summary["workflow_dispatch_executed"] is False
    assert summary["billing_mutated"] is False
    assert summary["external_state_mutated"] is False
    assert {"code": "github_actions_billing_or_spending_limit"} in payload["blockers"]
    assert {"code": "product-api-worker_not_green"} in payload["blockers"]
    assert {"code": "product-image-smoke_not_green"} in payload["blockers"]
    assert any("Billing & plans" in step for step in summary["next_required_steps"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


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
    assert payload["blockers"] == []


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
