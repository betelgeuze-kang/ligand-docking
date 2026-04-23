from __future__ import annotations

import json
import os
from pathlib import Path

from tools import build_wetlab_broad_screen_primary_watch_state as mod


def _bridge_payload(summary_json: Path, pid_path: Path) -> dict[str, object]:
    return {
        "summary": {"preferred_command_kind": "throughput_preflight_tuned_gate55"},
        "structured": {
            "preferred_summary_json": str(summary_json),
            "preferred_summary_md": str(summary_json.with_suffix(".md")),
            "preferred_log_path": str(summary_json.with_suffix(".log")),
            "preferred_pid_path": str(pid_path),
            "preferred_out_prefix": str(summary_json.with_suffix("")),
            "artifact_dir": str(summary_json.parent / "artifacts"),
        },
    }


def test_primary_watch_state_auto_completes_on_summary_ok_even_with_null_failed_stage(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "summary": {"status": "wetlab_broad_screen_throughput_ready"},
                "service_result": {"status": "ok", "failed_stage": None},
                "failed_stage": None,
            }
        ),
        encoding="utf-8",
    )
    pid_path = tmp_path / "compute.pid"
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    monkeypatch.setattr(mod.bridge_mod, "build_payload", lambda *args, **kwargs: _bridge_payload(summary_json, pid_path))

    payload = mod.build_payload(
        execution_queue_payload={"rows": [{"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "running"}]},
        compound_universe_payload={},
        portfolio_payload={},
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["watcher_decision"] == "auto_complete_candidate_summary_ok"
    assert row["throughput_ok"] is True
    assert row["throughput_failed"] is False


def test_primary_watch_state_holds_when_pid_exited_without_summary(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    pid_path = tmp_path / "dead.pid"
    pid_path.write_text("999999", encoding="utf-8")

    monkeypatch.setattr(mod.bridge_mod, "build_payload", lambda *args, **kwargs: _bridge_payload(summary_json, pid_path))

    payload = mod.build_payload(
        execution_queue_payload={"rows": [{"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "running"}]},
        compound_universe_payload={},
        portfolio_payload={},
    )

    summary = payload["summary"]
    assert summary["watcher_decision"] == "auto_hold_candidate_pid_exited_no_summary"
    assert summary["compute_pid"] == 999999
    assert summary["compute_pid_alive"] is False
    assert summary["throughput_summary_detected"] is False


def test_primary_watch_state_reports_heartbeat_pid_fields(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    pid_path = tmp_path / "compute.pid"
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    monkeypatch.setattr(mod.bridge_mod, "build_payload", lambda *args, **kwargs: _bridge_payload(summary_json, pid_path))
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    hb_pid = tmp_path / "runs" / "wetlab_broad_screen_heartbeat_loop.pid"
    hb_pid.parent.mkdir(parents=True, exist_ok=True)
    hb_pid.write_text(str(os.getpid()), encoding="utf-8")

    payload = mod.build_payload(
        execution_queue_payload={"rows": [{"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "running"}]},
        compound_universe_payload={},
        portfolio_payload={},
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["heartbeat_pid"] == os.getpid()
    assert summary["heartbeat_pid_alive"] is True
    assert row["heartbeat_pid"] == os.getpid()
    assert row["heartbeat_pid_alive"] is True


def test_primary_watch_state_ignores_stale_summary_older_than_active_start(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "service_result": {"status": "error", "failed_stage": "stage1_ligand_mapping"},
                "failed_stage": "stage1_ligand_mapping",
            }
        ),
        encoding="utf-8",
    )
    stale_mtime = dt = 1711843200  # 2024-03-31T00:00:00 local-ish anchor, intentionally old
    os.utime(summary_json, (stale_mtime, stale_mtime))
    pid_path = tmp_path / "compute.pid"
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    monkeypatch.setattr(mod.bridge_mod, "build_payload", lambda *args, **kwargs: _bridge_payload(summary_json, pid_path))

    payload = mod.build_payload(
        execution_queue_payload={
            "rows": [
                {
                    "target_id": "CA IX",
                    "shard_id": "08_of_20",
                    "queue_status": "running",
                    "progress_started_at": "2026-04-07T00:03:31",
                }
            ]
        },
        compound_universe_payload={},
        portfolio_payload={},
    )

    summary = payload["summary"]
    assert summary["throughput_summary_detected"] is False
    assert summary["watcher_decision"] == "continue_running_compute_alive"


def test_primary_watch_state_reports_exploratory_hard_freeze_when_followup_ready() -> None:
    payload = mod.build_payload(
        execution_queue_payload={
            "rows": [
                {"queue_rank": 1, "target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "result_ready"},
                {"queue_rank": 2, "target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        compound_universe_payload={},
        portfolio_payload={},
        exploratory_lane_payload={
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "17_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "ready_for_manual_retry": True,
            }
        },
    )

    summary = payload["summary"]
    assert summary["watcher_decision"] == "idle_exploratory_hard_freeze_pending_followup"
    assert summary["exploratory_hard_freeze_active"] is True
    assert summary["exploratory_hard_freeze_target_id"] == "STK17B (DRAK2)"
    assert summary["exploratory_hard_freeze_success_shard_id"] == "17_of_20"
    assert summary["exploratory_hard_freeze_blocked_shard_id"] == "18_of_20"
    assert "Default auto-start is frozen" in summary["next_required_step"]


def test_primary_watch_state_surfaces_preset_mismatch_hard_guard(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
                "failed_stage": "stage6_operational_gate",
                "stages": {
                    "stage2_trajectory_generation": {
                        "traj_stage2_preset_diagnostics": {
                            "requested": "kinase_protease",
                            "resolved": "kinase_protease",
                            "hinted_families": ["default"],
                            "warnings": [
                                "traj_prod_stage2_preset=kinase_protease does not match detected target-family hints ['default']; using explicit preset."
                            ],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    pid_path = tmp_path / "compute.pid"
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(mod.bridge_mod, "build_payload", lambda *args, **kwargs: _bridge_payload(summary_json, pid_path))

    payload = mod.build_payload(
        execution_queue_payload={"rows": [{"target_id": "Cathepsin K", "shard_id": "04_of_20", "queue_status": "running"}]},
        compound_universe_payload={},
        portfolio_payload={},
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["preset_mismatch_hard_guard_active"] is True
    assert summary["stage2_requested_preset"] == "kinase_protease"
    assert summary["stage2_hinted_families"] == "default"
    assert "block default-lane auto-start" in summary["preset_mismatch_hard_guard_reason"]
    assert row["preset_mismatch_hard_guard_active"] is True


def test_primary_watch_state_surfaces_hard_target_rescue_lane_when_no_active_row(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "detect_hard_target_rescue_lane",
        lambda execution_queue_payload: {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "throughput_preflight_hard_target_rescue",
            "stage2_preset_override": "",
            "anchor_artifact_required": True,
            "three_bead_recommended": True,
            "next_required_step": "Run the hard-target rescue lane for T. cruzi PDE 20_of_20 with slow local refinement and rescue-only anchors.",
        },
    )

    payload = mod.build_payload(
        execution_queue_payload={"rows": [{"target_id": "DprE1", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"}]},
        compound_universe_payload={},
        portfolio_payload={},
    )

    summary = payload["summary"]
    assert summary["watcher_decision"] == "idle_hard_target_rescue_lane_pending_review"
    assert summary["hard_target_rescue_lane_active"] is True
    assert summary["hard_target_rescue_target_id"] == "T. cruzi PDE"
    assert summary["hard_target_rescue_three_bead_recommended"] is True
