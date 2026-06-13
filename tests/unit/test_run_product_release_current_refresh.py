from __future__ import annotations

import json
from pathlib import Path

from tools.product import run_product_release_current_refresh as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _source_of_truth_ready() -> dict:
    spec = next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "product_release_source_of_truth_gate"
    )
    return {
        "summary": {
            "status": "product_release_source_of_truth_gate_ready",
            "release_source_of_truth_ready": True,
            "blocker_count": 0,
            "stale_artifact_count": 0,
            "readme_drift_count": 0,
            **dict(spec.get("required_int_exact_fields", {})),
        }
    }


def _goal_release_decision_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "goal_release_decision_gate"
    )


def _quality_gate_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "product_quality_gate_verification"
    )


def _quality_gate_ready() -> dict:
    spec = _quality_gate_spec()
    return {
        "summary": {
            "status": spec["required_status"],
            **{field: True for field in spec.get("required_true_fields", [])},
            **{field: 0 for field in spec.get("required_zero_fields", [])},
            **dict(spec.get("required_int_exact_fields", {})),
            **dict(spec.get("required_text_exact_fields", {})),
        }
    }


def _goal_operator_action_board_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "goal_operator_action_board"
    )


def _release_decision_ready(*, bottleneck_recorded: bool = True) -> dict:
    spec = _goal_release_decision_spec()
    summary = {
        "status": spec["required_status"],
        **{field: True for field in spec.get("required_true_fields", [])},
        **{field: 0 for field in spec.get("required_zero_fields", [])},
        **dict(spec.get("required_int_exact_fields", {})),
        **dict(spec.get("required_int_min_fields", {})),
        **dict(spec.get("required_text_exact_fields", {})),
    }
    summary["goal_bottleneck_briefing_full_commercial_receipts_recorded"] = bottleneck_recorded
    return {
        "summary": summary
    }


def _action_board_ready() -> dict:
    spec = _goal_operator_action_board_spec()
    summary = {
        "status": spec["required_status"],
        **{field: True for field in spec.get("required_true_fields", [])},
        **{field: 0 for field in spec.get("required_zero_fields", [])},
        **dict(spec.get("required_text_exact_fields", {})),
    }
    return {
        "summary": summary
    }


def _action_board_stale_release_echo() -> dict:
    payload = _action_board_ready()
    payload["summary"].update(
        {
            "goal_release_decision_gate_status": "blocked_goal_release_decision",
            "goal_release_allowed": False,
            "goal_release_blocker_count": 1,
        }
    )
    return payload


def test_refresh_final_gate_requires_release_decision_bottleneck_receipt_linkage(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "product_release_current_refresh_verified"
    assert summary["final_gate_verification_ready"] is True
    assert summary["final_gate_blocker_count"] == 0
    assert summary["final_gate_count"] == 4
    assert decision_row["status"] == "pass"
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in decision_row[
        "required_true_fields"
    ]
    assert decision_row["required_int_exact_fields"][
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count"
    ] == 2
    assert "product_pose_sampling_readiness_recorded" in decision_row["required_true_fields"]
    assert "product_pose_sampling_readiness_docking_results_emitted" in decision_row[
        "required_zero_fields"
    ]
    assert decision_row["required_int_exact_fields"][
        "product_pose_sampling_readiness_pose_count"
    ] == 6
    assert decision_row["required_text_exact_fields"][
        "product_pose_sampling_readiness_status"
    ] == "product_pose_sampling_readiness_ready"
    assert "product_ledger_privacy_scan_recorded" in decision_row["required_true_fields"]
    assert "product_ledger_privacy_scan_leak_count" in decision_row["required_zero_fields"]
    assert decision_row["required_int_min_fields"][
        "product_ledger_privacy_scan_scan_file_count"
    ] == 285
    assert decision_row["required_int_equal_fields"][
        "product_ledger_privacy_scan_pass_count"
    ] == "product_ledger_privacy_scan_scan_file_count"
    assert decision_row["required_text_exact_fields"][
        "product_ledger_privacy_scan_status"
    ] == "product_ledger_privacy_scan_ready"
    assert decision_row["required_text_exact_fields"][
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs"
    ] == (
        "config/product_scope_breadth_evidence_receipt_current.csv;"
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )


def test_refresh_final_gate_blocks_missing_release_decision_bottleneck_receipt_linkage(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(bottleneck_recorded=False),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in decision_row[
        "missing_true_fields"
    ]


def test_refresh_final_gate_blocks_source_of_truth_coverage_drift(tmp_path: Path) -> None:
    source_payload = _source_of_truth_ready()
    source_payload["summary"]["row_count"] -= 1
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        source_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    source_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "product_release_source_of_truth_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert source_row["status"] == "fail"
    assert source_row["failed_int_exact_fields"] == ["row_count"]


def test_refresh_final_gate_blocks_quality_gate_verification_drift(tmp_path: Path) -> None:
    quality_payload = _quality_gate_ready()
    quality_payload["summary"]["pass_count"] -= 1
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        quality_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    quality_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "product_quality_gate_verification"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert quality_row["status"] == "fail"
    assert quality_row["failed_int_exact_fields"] == ["pass_count"]


def test_refresh_final_gate_blocks_pose_sampling_release_decision_drift(tmp_path: Path) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"]["product_pose_sampling_readiness_pose_count"] = 4
    decision_payload["summary"]["product_pose_sampling_readiness_docking_results_emitted"] = True
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["nonzero_fields"] == [
        "product_pose_sampling_readiness_docking_results_emitted"
    ]
    assert decision_row["failed_int_exact_fields"] == [
        "product_pose_sampling_readiness_pose_count"
    ]


def test_refresh_final_gate_blocks_ledger_privacy_scan_release_decision_drift(
    tmp_path: Path,
) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"]["product_ledger_privacy_scan_leak_count"] = 1
    decision_payload["summary"]["product_ledger_privacy_scan_scan_file_count"] = 284
    decision_payload["summary"]["product_ledger_privacy_scan_pass_count"] = 284
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["nonzero_fields"] == ["product_ledger_privacy_scan_leak_count"]
    assert decision_row["failed_int_min_fields"] == [
        "product_ledger_privacy_scan_scan_file_count",
        "product_ledger_privacy_scan_pass_count",
    ]
    assert decision_row["failed_int_equal_fields"] == []
    assert decision_row["failed_int_exact_fields"] == []


def test_refresh_final_gate_blocks_ledger_privacy_scan_pass_count_mismatch(
    tmp_path: Path,
) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"]["product_ledger_privacy_scan_pass_count"] = 286
    decision_payload["summary"]["product_ledger_privacy_scan_scan_file_count"] = 287
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["failed_int_min_fields"] == []
    assert decision_row["failed_int_equal_fields"] == [
        "product_ledger_privacy_scan_pass_count"
    ]


def test_refresh_final_gate_blocks_stale_action_board_release_decision_echo(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_stale_release_echo(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    action_board_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_operator_action_board"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert action_board_row["status"] == "fail"
    assert action_board_row["missing_true_fields"] == ["goal_release_allowed"]
    assert action_board_row["nonzero_fields"] == ["goal_release_blocker_count"]
    assert action_board_row["failed_text_exact_fields"] == ["goal_release_decision_gate_status"]
