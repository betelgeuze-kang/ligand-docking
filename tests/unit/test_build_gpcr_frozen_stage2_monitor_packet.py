from __future__ import annotations

import json
from pathlib import Path

from tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet import build_packet


def test_stage2_monitor_reports_running_progress(tmp_path: Path, monkeypatch) -> None:
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "status": "running",
                "queue_rows_total": 40000,
                "processed_rows": 8500,
                "ok_rows": 8500,
                "failed_rows": 0,
                "progress_ratio": 0.2125,
                "current_target": "ADRB2_GPCR_BLIND",
            }
        ),
        encoding="utf-8",
    )
    mount = tmp_path / "mount"
    stage2 = mount / "run1" / "stage2_trajectory_frames" / "shard_00001"
    stage2.mkdir(parents=True)
    (stage2 / "a.npz").write_bytes(b"x")

    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._pid_alive",
        lambda _pid: True,
    )
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._stage2_engine_running",
        lambda: True,
    )
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._htvs_pipeline_running",
        lambda: False,
    )

    payload = build_packet(
        pid=204429,
        mount_root=mount,
        frozen_run_id="run1",
        stage2_progress_json=progress,
        stage2_summary_json=tmp_path / "missing_summary.json",
        stage3_scores_csv=tmp_path / "missing_stage3.csv",
        generated_at_local="2026-06-07T19:20:00+09:00",
    )
    summary = payload["summary"]
    assert summary["status"] == "stage2_running"
    assert summary["next_action"] == "wait_stage2_npz_accumulation"
    assert summary["mount_stage2_npz_count"] == 1
    assert summary["claim_promotion_allowed"] is False


def test_stage2_monitor_triggers_htvs_when_stage2_done(tmp_path: Path, monkeypatch) -> None:
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "status": "done",
                "queue_rows_total": 40000,
                "processed_rows": 40000,
                "ok_rows": 40000,
                "failed_rows": 0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._pid_alive",
        lambda _pid: False,
    )
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._stage2_engine_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._htvs_pipeline_running",
        lambda: False,
    )
    payload = build_packet(
        stage2_progress_json=progress,
        stage2_summary_json=tmp_path / "missing_summary.json",
        stage3_scores_csv=tmp_path / "missing_stage3.csv",
        mount_root=tmp_path / "mount",
        frozen_run_id="run1",
    )
    assert payload["summary"]["next_action"] == "launch_htvs_stage3_resume"


def test_stage2_monitor_triggers_post_stage3_when_csv_present(tmp_path: Path, monkeypatch) -> None:
    stage3 = tmp_path / "stage3_scores.csv"
    stage3.write_text("target,ligand_id\n", encoding="utf-8")
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_stage2_monitor_packet._pid_alive",
        lambda _pid: False,
    )
    payload = build_packet(
        pid=0,
        mount_root=tmp_path / "mount",
        frozen_run_id="run1",
        stage2_progress_json=tmp_path / "missing_progress.json",
        stage2_summary_json=tmp_path / "missing_summary.json",
        stage3_scores_csv=stage3,
        generated_at_local="2026-06-07T19:20:00+09:00",
    )
    assert payload["summary"]["next_action"] == "run_post_stage3_v11_claim_review_chain"
