from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_release_source_of_truth_gap5_scan as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _source_payload() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_product_release_source_of_truth_gate",
            "release_source_of_truth_ready": False,
            "blocker_count": 89,
            "stale_artifact_count": 59,
        },
        "rows": [
            {
                "row_type": "artifact_freshness",
                "artifact_id": artifact_id,
                "status": "pass",
                "artifact_path": artifact_path,
                "release_blocker": False,
            }
            for artifact_id, artifact_path in [
                ("accuracy_parity_scorecard", "runs/accuracy_parity_scorecard_current.json"),
                (
                    "product_production_ai_checkpoint_readiness",
                    "runs/product_production_ai_checkpoint_readiness_current.json",
                ),
                ("goal_readiness_rollup", "runs/goal_readiness_rollup_current.json"),
                ("product_goal_completion_audit", "runs/product_goal_completion_audit_current.json"),
                ("goal_operator_action_board", "runs/goal_operator_action_board_current.json"),
            ]
        ]
        + [
            {
                "row_type": "artifact_freshness",
                "artifact_id": "product_production_ai_promotion_workbench",
                "status": "fail",
                "artifact_path": "runs/product_production_ai_promotion_workbench_current.json",
                "release_blocker": True,
                "stale_dependency_paths": [
                    "runs/product_production_ai_checkpoint_readiness_current.json",
                ],
            },
            {
                "row_type": "artifact_freshness",
                "artifact_id": "goal_bottleneck_briefing",
                "status": "fail",
                "artifact_path": "runs/goal_bottleneck_briefing_current.json",
                "release_blocker": True,
                "stale_dependency_paths": [
                    "runs/product_goal_completion_audit_current.json",
                    "runs/goal_operator_action_board_current.json",
                ],
            },
        ],
    }


def _write_candidate_artifacts(root: Path) -> None:
    statuses = {
        "accuracy_parity_scorecard_current.json": "blocked_accuracy_parity",
        "product_production_ai_checkpoint_readiness_current.json": (
            "blocked_product_production_ai_checkpoint_readiness"
        ),
        "goal_readiness_rollup_current.json": "blocked_goal_readiness",
        "product_goal_completion_audit_current.json": "blocked_product_goal_completion_audit",
        "goal_operator_action_board_current.json": "operator_actions_required",
    }
    for filename, status in statuses.items():
        _write_json(root / "runs" / filename, {"summary": {"status": status}})


def test_gap5_scan_classifies_requested_candidates_without_promoting_release(tmp_path: Path) -> None:
    _write_candidate_artifacts(tmp_path)
    source = tmp_path / "runs" / "product_release_source_of_truth_gate_current.json"
    _write_json(source, _source_payload())

    payload = mod.build_release_source_of_truth_gap5_scan(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "release_source_of_truth_gap5_scan_ready"
    assert summary["gap5_scan_ready"] is True
    assert summary["candidate_count"] == 5
    assert summary["classified_count"] == 5
    assert summary["source_of_truth_ready"] is False
    assert summary["source_of_truth_blocker_count"] == 89
    assert summary["fix_count"] == 3
    assert summary["no_op_count"] == 0
    assert summary["aggregator_review_count"] == 2
    assert summary["secondary_aggregator_review_count"] == 1
    assert summary["downstream_stale_blocker_count"] == 3
    assert summary["downstream_refresh_candidate_count"] == 3
    assert summary["science_scorecard_reviewed"] is True
    rows = {row["artifact_id"]: row for row in payload["rows"]}
    assert rows["accuracy_parity_scorecard"]["requested_classification"] == "fix"
    assert rows["accuracy_parity_scorecard"]["review_priority"] == "science_scorecard_priority"
    assert rows["product_production_ai_checkpoint_readiness"]["secondary_classification"] == "aggregator-review"
    assert rows["product_production_ai_checkpoint_readiness"]["downstream_refresh_required"] is True
    assert rows["product_production_ai_checkpoint_readiness"]["downstream_stale_artifact_ids"] == [
        "product_production_ai_promotion_workbench"
    ]
    assert rows["product_goal_completion_audit"]["requested_classification"] == "aggregator-review"
    assert rows["product_goal_completion_audit"]["downstream_stale_blocker_count"] == 1
    assert rows["goal_operator_action_board"]["requested_classification"] == "aggregator-review"
    assert rows["goal_operator_action_board"]["downstream_stale_blocker_count"] == 1
    assert all(row["source_of_truth_row_status"] == "pass" for row in payload["rows"])
    assert all(row["execution_enabled"] is False for row in payload["rows"])


def test_gap5_scan_blocks_if_a_requested_source_row_is_not_passing(tmp_path: Path) -> None:
    _write_candidate_artifacts(tmp_path)
    source_payload = _source_payload()
    rows = source_payload["rows"]
    assert isinstance(rows, list)
    rows[0]["status"] = "fail"
    rows[0]["release_blocker"] = True
    _write_json(tmp_path / "runs" / "product_release_source_of_truth_gate_current.json", source_payload)

    payload = mod.build_release_source_of_truth_gap5_scan(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_release_source_of_truth_gap5_scan"
    assert payload["summary"]["classified_count"] == 4
    accuracy = payload["rows"][0]
    assert accuracy["artifact_id"] == "accuracy_parity_scorecard"
    assert accuracy["classification_status"] == "needs_review"


def test_main_writes_gap5_scan_artifacts(tmp_path: Path) -> None:
    _write_candidate_artifacts(tmp_path)
    _write_json(tmp_path / "runs" / "product_release_source_of_truth_gate_current.json", _source_payload())
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "release_source_of_truth_gap5_scan_ready"
    assert out_md.read_text(encoding="utf-8").startswith("# Release Source-Of-Truth Gap-5 Scan")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["artifact_id"] for row in rows] == [
        "accuracy_parity_scorecard",
        "product_production_ai_checkpoint_readiness",
        "goal_readiness_rollup",
        "product_goal_completion_audit",
        "goal_operator_action_board",
    ]
    assert "downstream_stale_blocker_count" in rows[0]
