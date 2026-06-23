from __future__ import annotations

import json
from pathlib import Path

from tools.product.build_release_ci_remote_green_receipt import build_release_ci_remote_green_receipt


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _runner_inventory() -> dict[str, object]:
    return {
        "total_count": 1,
        "runners": [
            {
                "id": 7,
                "name": "betelgeuze-rocm",
                "status": "online",
                "labels": [
                    {"name": "self-hosted"},
                    {"name": "Linux"},
                    {"name": "X64"},
                    {"name": "rocm"},
                ],
            }
        ],
    }


def _green_inputs(tmp_path: Path) -> dict[str, Path]:
    return {
        "runner_inventory_json": _write_json(tmp_path / "runners.json", _runner_inventory()),
        "branch_json": _write_json(
            tmp_path / "branch.json",
            {
                "name": "main",
                "protected": True,
                "protection": {
                    "required_status_checks": {
                        "contexts": [
                            "product-image-build-smoke",
                            "product-image-rocm-runtime-smoke",
                        ],
                    }
                },
            },
        ),
        "required_checks_json": _write_json(
            tmp_path / "required_checks.json",
            {
                "contexts": [
                    "product-image-build-smoke",
                    "product-image-rocm-runtime-smoke",
                ],
                "checks": [],
            },
        ),
        "schedule_runs_json": _write_json(
            tmp_path / "schedule_runs.json",
            {
                "total_count": 1,
                "workflow_runs": [
                    {
                        "id": 101,
                        "event": "schedule",
                        "name": "product-image-smoke",
                        "display_title": "Product image ROCm runtime smoke",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://example.invalid/schedule",
                    }
                ],
            },
        ),
        "failed_run_artifacts_json": _write_json(
            tmp_path / "failed_artifacts.json",
            {
                "total_count": 2,
                "artifacts": [
                    {"name": "product-image-rocm-runtime-smoke-101"},
                    {"name": "product-image-rocm-runtime-smoke-log-receipt-101"},
                ],
            },
        ),
        "release_tag_runs_json": _write_json(
            tmp_path / "tag_runs.json",
            {
                "total_count": 1,
                "workflow_runs": [
                    {
                        "id": 202,
                        "event": "push",
                        "head_branch": "refs/tags/v0.1.0",
                        "name": "product-image-smoke",
                        "display_title": "Product image ROCm runtime smoke",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://example.invalid/tag",
                    }
                ],
            },
        ),
    }


def test_release_ci_remote_green_receipt_passes_with_complete_evidence(tmp_path: Path) -> None:
    payload = build_release_ci_remote_green_receipt(root=tmp_path, **_green_inputs(tmp_path))
    summary = payload["summary"]
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert summary["status"] == "release_ci_remote_green_ready"
    assert summary["pass"] is True
    assert summary["linux_self_hosted_runner_ready"] is True
    assert summary["rocm_self_hosted_runner_ready"] is True
    assert summary["main_required_checks_ready"] is True
    assert summary["weekly_rocm_schedule_green"] is True
    assert summary["failure_artifacts_preserved"] is True
    assert summary["release_tag_rocm_gate_green"] is True
    assert payload["blockers"] == []
    assert rows_by_id["main_branch_required_checks_configured"]["external_state_mutated"] is False
    assert "does not register runners" in summary["claim_boundary"]


def test_release_ci_remote_green_receipt_blocks_unprotected_main_and_missing_remote_runs(tmp_path: Path) -> None:
    inputs = _green_inputs(tmp_path)
    inputs["branch_json"] = _write_json(tmp_path / "branch.json", {"name": "main", "protected": False})
    inputs["required_checks_json"] = _write_json(tmp_path / "required_checks.json", {"contexts": []})
    inputs["schedule_runs_json"] = _write_json(tmp_path / "schedule_runs.json", {"total_count": 0, "workflow_runs": []})
    inputs["failed_run_artifacts_json"] = _write_json(
        tmp_path / "failed_artifacts.json",
        {"total_count": 0, "artifacts": []},
    )
    inputs["release_tag_runs_json"] = _write_json(tmp_path / "tag_runs.json", {"total_count": 0, "workflow_runs": []})

    payload = build_release_ci_remote_green_receipt(root=tmp_path, **inputs)
    blocker_codes = {row["code"] for row in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_release_ci_remote_green"
    assert "main_branch_required_checks_configured" in blocker_codes
    assert "weekly_rocm_runtime_schedule_green" in blocker_codes
    assert "failed_run_artifacts_preserved" in blocker_codes
    assert "release_tag_rocm_runtime_gate_green" in blocker_codes
    assert payload["summary"]["linux_self_hosted_runner_ready"] is True
    assert payload["summary"]["rocm_self_hosted_runner_ready"] is True


def test_release_ci_remote_green_receipt_blocks_missing_rocm_runner_label(tmp_path: Path) -> None:
    inputs = _green_inputs(tmp_path)
    runners = _runner_inventory()
    runners["runners"][0]["labels"] = [{"name": "self-hosted"}, {"name": "Linux"}]
    inputs["runner_inventory_json"] = _write_json(tmp_path / "runners.json", runners)

    payload = build_release_ci_remote_green_receipt(root=tmp_path, **inputs)
    blocker_codes = {row["code"] for row in payload["blockers"]}

    assert payload["summary"]["linux_self_hosted_runner_ready"] is True
    assert payload["summary"]["rocm_self_hosted_runner_ready"] is False
    assert "rocm_self_hosted_runner_registered" in blocker_codes
