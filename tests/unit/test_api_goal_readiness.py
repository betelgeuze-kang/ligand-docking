from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api import goal as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_goal_readiness_returns_dashboard_safe_rows(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "runs/goal_readiness_rollup_current.json"
    monkeypatch.setattr(mod, "GOAL_READINESS_ROLLUP_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "summary": {
                "status": "blocked_goal_readiness",
                "lane_count": 2,
                "blocked_lane_count": 1,
                "operator_approval_pending_count": 1,
                "external_results_pending_count": 0,
                "release_allowed": False,
                "claim_boundary": "goal readiness fixture boundary",
            },
            "rows": [
                {
                    "lane_id": "commercial_product_execution",
                    "lane_status": "operator_approval_pending",
                    "artifact_path": "runs/product_pilot_packet_current.json",
                    "artifact_present": True,
                    "observed_status": "product_pilot_packet_ready",
                    "next_required_step": "Review restricted customer handoff.",
                    "blocker_count": 0,
                    "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                    "reclaim_size_gb": 1.5,
                    "execution_enabled": True,
                    "action_executed": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "lane_id": "public_benchmark",
                    "lane_status": "blocked",
                    "artifact_path": "runs/public_benchmark_external_receipts_audit_current.json",
                    "artifact_present": True,
                    "observed_status": "missing_external_receipts",
                    "next_required_step": "Attach benchmark receipts.",
                    "blocker_count": 2,
                    "approval_token_required": "",
                    "reclaim_size_gb": 0,
                    "blockers": "pose_rmsd_missing;posebusters_missing",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                },
            ],
            "blockers": [{"blocker_id": "public_benchmark_receipts_missing"}],
        },
    )

    response = asyncio.run(mod.get_goal_readiness())

    assert response["status"] == "blocked_goal_readiness"
    assert response["readiness_row_count"] == 2
    assert response["readiness_action_required_row_count"] == 2
    assert len(response["rows"]) == 2
    assert response["blockers"] == [{"blocker_id": "public_benchmark_receipts_missing"}]
    assert response["readiness_rows"] == [
        {
            "lane_id": "commercial_product_execution",
            "lane_status": "operator_approval_pending",
            "artifact_path": "runs/product_pilot_packet_current.json",
            "artifact_present": True,
            "observed_status": "product_pilot_packet_ready",
            "next_required_step": "Review restricted customer handoff.",
            "blocker_count": 0,
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "operator_action_required": True,
            "reclaim_size_gb": 1.5,
            "blockers": [],
            "execution_enabled": False,
            "action_executed": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "lane_id": "public_benchmark",
            "lane_status": "blocked",
            "artifact_path": "runs/public_benchmark_external_receipts_audit_current.json",
            "artifact_present": True,
            "observed_status": "missing_external_receipts",
            "next_required_step": "Attach benchmark receipts.",
            "blocker_count": 2,
            "approval_token_required": "",
            "operator_action_required": True,
            "reclaim_size_gb": 0.0,
            "blockers": ["pose_rmsd_missing", "posebusters_missing"],
            "execution_enabled": False,
            "action_executed": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert response["execution_enabled"] is False
    assert response["action_executed"] is False
    assert response["external_state_mutated"] is False


def test_goal_readiness_missing_artifact_keeps_dashboard_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "GOAL_READINESS_ROLLUP_ARTIFACT",
        tmp_path / "runs/missing_goal_readiness_rollup_current.json",
    )

    response = asyncio.run(mod.get_goal_readiness())

    assert response["status"] == "missing_goal_readiness_rollup"
    assert response["readiness_row_count"] == 0
    assert response["readiness_action_required_row_count"] == 0
    assert response["readiness_rows"] == []
    assert response["rows"] == []
    assert response["blockers"] == []
    assert response["execution_enabled"] is False
    assert response["action_executed"] is False
    assert response["external_state_mutated"] is False
