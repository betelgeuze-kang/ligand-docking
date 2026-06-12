from __future__ import annotations

import json
import os
from pathlib import Path

from tools.product import build_product_release_source_of_truth_gate as mod
from tools.product import run_product_release_current_refresh as refresh_mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _accuracy_payload() -> dict:
    return {
        "summary": {
            "status": "green",
            "row_count": 5,
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
        }
    }


def test_release_source_of_truth_gate_blocks_stale_artifact_and_readme_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "operator_packet.json"
    dependency = tmp_path / "runs" / "goal_audit.json"
    _write_json(artifact, {"summary": {"status": "old_operator_packet"}})
    _write_json(dependency, {"summary": {"status": "new_goal_audit"}})
    os.utime(artifact, (1_700_000_000, 1_700_000_000))
    os.utime(dependency, (1_700_000_100, 1_700_000_100))

    _write_json(tmp_path / "runs" / "accuracy_parity_scorecard_current.json", _accuracy_payload())
    (tmp_path / "README.md").write_text(
        "runs/accuracy_parity_scorecard_current.json status=green pass=5 blocked=0\n",
        encoding="utf-8",
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[
            {
                "artifact_id": "operator_packet",
                "artifact_path": "runs/operator_packet.json",
                "builder_command": "python3 tools/build_operator_packet.py",
                "depends_on": ["runs/goal_audit.json"],
            }
        ],
        readme_paths=["README.md"],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["release_source_of_truth_ready"] is False
    assert summary["stale_artifact_count"] == 1
    assert summary["readme_drift_count"] == 1
    assert summary["blocked_artifact_ids"] == ["operator_packet", "readme_accuracy_parity:README.md"]
    stale_row = next(row for row in payload["rows"] if row["artifact_id"] == "operator_packet")
    assert stale_row["stale_dependency_paths"] == ["runs/goal_audit.json"]
    readme_row = next(row for row in payload["rows"] if row["row_type"] == "readme_metric_drift")
    assert "pass=5" in readme_row["obsolete_fragments_present"]


def test_release_source_of_truth_gate_passes_current_artifact_and_readme_metrics(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "operator_packet.json"
    dependency = tmp_path / "runs" / "goal_audit.json"
    _write_json(artifact, {"summary": {"status": "current_operator_packet"}})
    _write_json(dependency, {"summary": {"status": "current_goal_audit"}})
    os.utime(dependency, (1_700_000_000, 1_700_000_000))
    os.utime(artifact, (1_700_000_100, 1_700_000_100))

    _write_json(tmp_path / "runs" / "accuracy_parity_scorecard_current.json", _accuracy_payload())
    (tmp_path / "README.md").write_text(
        "runs/accuracy_parity_scorecard_current.json status=green pass=4 restricted_pass=1 blocked=0\n",
        encoding="utf-8",
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[
            {
                "artifact_id": "operator_packet",
                "artifact_path": "runs/operator_packet.json",
                "builder_command": "python3 tools/build_operator_packet.py",
                "depends_on": ["runs/goal_audit.json"],
            }
        ],
        readme_paths=["README.md"],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    assert payload["summary"]["release_source_of_truth_ready"] is True
    assert payload["blockers"] == []


def test_product_release_current_refresh_defaults_to_dry_run_plan(tmp_path: Path) -> None:
    payload = refresh_mod.run_product_release_current_refresh(
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "product_release_current_refresh_planned"
    assert payload["summary"]["execute"] is False
    assert payload["summary"]["command_count"] == 1
    assert payload["rows"][0]["executed"] is False
    assert payload["rows"][0]["status"] == "planned"
    assert payload["summary"]["final_gate_verification_ready"] is False
    assert payload["verification_rows"] == []


def test_product_release_current_refresh_blocks_if_final_gate_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "blocked_product_release_source_of_truth_gate",
                "release_source_of_truth_ready": False,
                "blocker_count": 1,
                "stale_artifact_count": 1,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        {"summary": {"status": "goal_release_ready", "release_allowed": True, "blocker_count": 0}},
    )

    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": 0, "timed_out": False},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "blocked_product_release_current_refresh"
    assert payload["summary"]["final_gate_verification_ready"] is False
    assert payload["summary"]["final_gate_blocker_count"] == 1
    assert payload["verification_rows"][0]["gate_id"] == "product_release_source_of_truth_gate"
    assert payload["verification_rows"][0]["status"] == "fail"


def test_product_release_current_refresh_verifies_final_gates_after_execute(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "product_release_source_of_truth_gate_ready",
                "release_source_of_truth_ready": True,
                "blocker_count": 0,
                "stale_artifact_count": 0,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        {"summary": {"status": "goal_release_ready", "release_allowed": True, "blocker_count": 0}},
    )

    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": 0, "timed_out": False},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "product_release_current_refresh_verified"
    assert payload["summary"]["final_gate_verification_ready"] is True
    assert payload["summary"]["final_gate_blocker_count"] == 0


def test_product_release_current_refresh_blocks_timed_out_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": -9, "timed_out": True},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/hangs.py"],
        command_timeout_seconds=7,
    )

    assert payload["summary"]["status"] == "blocked_product_release_current_refresh"
    assert payload["summary"]["timed_out_count"] == 1
    assert payload["summary"]["command_timeout_seconds"] == 7
    assert payload["rows"][0]["status"] == "timeout"
    assert payload["rows"][0]["release_blocker"] is True
    assert payload["verification_rows"] == []


def test_release_source_of_truth_tracks_customer_report_ux_artifacts() -> None:
    artifact_ids = {spec["artifact_id"] for spec in mod.DEFAULT_ARTIFACT_SPECS}
    status_ids = {spec["artifact_id"] for spec in mod.DEFAULT_STATUS_SPECS}

    assert "product_ai_report_explanation_packet" in artifact_ids
    assert "product_ai_report_ux_contract" in artifact_ids
    assert "product_ai_report_explanation_packet_semantic_ready" in status_ids
    assert "product_ai_report_ux_contract_semantic_ready" in status_ids
    assert "product_ledger_privacy_scan" in artifact_ids
    assert "product_launch_r4_preflight" in artifact_ids
    assert "engine_refinement_claim_promotion_action_board" in artifact_ids
    goal_action_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_operator_action_board"
    )
    assert "runs/engine_refinement_claim_promotion_action_board_current.csv" in goal_action_spec["depends_on"]
    assert "product_ledger_privacy_scan_semantic_ready" in status_ids
    assert "python3 tools/build_product_ai_report_explanation_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_ai_report_ux_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_engine_refinement_tier_readiness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_product_launch_r4_preflight.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_ledger_privacy_scan.py" in mod.RELEASE_REFRESH_COMMANDS


def test_release_source_of_truth_blocks_fresh_but_semantically_blocked_report(tmp_path: Path) -> None:
    report = tmp_path / "runs" / "product_ai_report_ux_contract_current.json"
    _write_json(
        report,
        {
            "summary": {
                "status": "blocked_product_ai_report_ux_contract",
                "ai_report_ux_ready": False,
                "customer_report_viewer_binding_ready": False,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_ai_report_ux_contract_semantic_ready",
                "artifact_path": "runs/product_ai_report_ux_contract_current.json",
                "builder_command": "python3 tools/build_product_ai_report_ux_contract.py",
                "required_status": "product_ai_report_ux_contract_ready",
                "required_true_fields": ["ai_report_ux_ready", "customer_report_viewer_binding_ready"],
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_row_count"] == 1
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["row_type"] == "artifact_semantic_status"
    assert row["observed_status"] == "blocked_product_ai_report_ux_contract"
    assert row["missing_true_fields"] == ["ai_report_ux_ready", "customer_report_viewer_binding_ready"]
