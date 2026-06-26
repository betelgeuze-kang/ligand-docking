from __future__ import annotations

import json
from pathlib import Path

from tools.product.build_release_claim_evidence_ladder_gate import (
    CLAIM_LOCAL_ONLY,
    CLAIM_NONE,
    CLAIM_REMOTE_GREEN,
    CLAIM_RUNTIME_GREEN,
    build_release_claim_evidence_ladder_gate,
)


def _write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path.name


def test_local_observed_green_never_promotes_remote_claim(tmp_path: Path) -> None:
    local = _write_json(
        tmp_path / "local.json",
        {"summary": {"evidence_scope": "local_observed", "status": "product_image_smoke_ready"}},
    )

    packet = build_release_claim_evidence_ladder_gate(
        root=tmp_path,
        local_receipt_json=local,
        main_head_sha="abc123",
    )

    summary = packet["summary"]
    assert summary["local_observed_green"] is True
    assert summary["remote_green"] is False
    assert summary["runtime_green"] is False
    assert summary["highest_supported_claim"] == CLAIM_LOCAL_ONLY
    assert summary["claim_promotion"]["ci_wired_and_green_on_main"] is False
    assert summary["claim_promotion"]["runtime_or_production_claim"] is False


def test_remote_green_requires_workflow_run_attributed_to_main_head(tmp_path: Path) -> None:
    local = _write_json(
        tmp_path / "local.json",
        {"summary": {"evidence_scope": "local_observed", "green": True}},
    )
    remote = _write_json(
        tmp_path / "remote.json",
        {"summary": {"status": "release_ci_remote_green_ready", "pass": True}},
    )
    wrong_head_runs = _write_json(
        tmp_path / "runs.json",
        {
            "workflow_runs": [
                {
                    "name": "product-image-smoke",
                    "head_sha": "other-sha",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
    )

    packet = build_release_claim_evidence_ladder_gate(
        root=tmp_path,
        local_receipt_json=local,
        remote_receipt_json=remote,
        head_runs_json=wrong_head_runs,
        main_head_sha="main-sha",
    )

    summary = packet["summary"]
    assert summary["remote_green"] is True
    assert summary["merge_commit_workflow_run_present"] is False
    assert summary["remote_green_attributable_to_head"] is False
    assert summary["highest_supported_claim"] == CLAIM_LOCAL_ONLY


def test_remote_green_attributed_to_head_still_does_not_promote_runtime(tmp_path: Path) -> None:
    local = _write_json(
        tmp_path / "local.json",
        {"summary": {"evidence_scope": "local_observed", "pass": True}},
    )
    remote = _write_json(
        tmp_path / "remote.json",
        {
            "summary": {
                "status": "release_ci_remote_green_ready",
                "pass": True,
                "rocm_self_hosted_runner_ready": False,
                "weekly_rocm_schedule_green": False,
            }
        },
    )
    head_runs = _write_json(
        tmp_path / "runs.json",
        {
            "workflow_runs": [
                {
                    "name": "product-image-smoke",
                    "head_sha": "main-sha",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
    )

    packet = build_release_claim_evidence_ladder_gate(
        root=tmp_path,
        local_receipt_json=local,
        remote_receipt_json=remote,
        head_runs_json=head_runs,
        main_head_sha="main-sha",
    )

    summary = packet["summary"]
    assert summary["remote_green_attributable_to_head"] is True
    assert summary["runtime_green"] is False
    assert summary["highest_supported_claim"] == CLAIM_REMOTE_GREEN
    assert summary["claim_promotion"]["runtime_or_production_claim"] is False


def test_runtime_claim_requires_rocm_runtime_green_and_head_attribution(tmp_path: Path) -> None:
    local = _write_json(
        tmp_path / "local.json",
        {"summary": {"evidence_scope": "local_observed", "pass": True}},
    )
    remote = _write_json(
        tmp_path / "remote.json",
        {
            "summary": {
                "status": "release_ci_remote_green_ready",
                "pass": True,
                "rocm_self_hosted_runner_ready": True,
                "weekly_rocm_schedule_green": True,
            }
        },
    )
    head_runs = _write_json(
        tmp_path / "runs.json",
        {
            "workflow_runs": [
                {
                    "workflow_name": "product-image-smoke",
                    "head_sha": "main-sha",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
    )

    packet = build_release_claim_evidence_ladder_gate(
        root=tmp_path,
        local_receipt_json=local,
        remote_receipt_json=remote,
        head_runs_json=head_runs,
        main_head_sha="main-sha",
    )

    summary = packet["summary"]
    assert summary["runtime_green"] is True
    assert summary["highest_supported_claim"] == CLAIM_RUNTIME_GREEN
    assert summary["claim_promotion"]["runtime_or_production_claim"] is True


def test_missing_everything_stays_claim_none(tmp_path: Path) -> None:
    packet = build_release_claim_evidence_ladder_gate(root=tmp_path)

    summary = packet["summary"]
    assert summary["highest_supported_claim"] == CLAIM_NONE
    assert summary["local_observed_green"] is False
    assert summary["remote_green"] is False
    assert summary["runtime_green"] is False
    assert packet["blockers"]
