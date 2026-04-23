from __future__ import annotations

import json
from pathlib import Path

from tools import run_wetlab_mapping_fix_retry as mod


def test_run_wetlab_mapping_fix_retry_invokes_primary_runner(monkeypatch, tmp_path: Path) -> None:
    lane_json = tmp_path / "lane.json"
    lane_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_mapping_fix_retry_lane_ready",
                    "target_id": "SARS-CoV-2 Mpro",
                    "shard_id": "01_of_20",
                    "selected_command_kind": "throughput_preflight",
                    "ready_for_mapping_fix_retry": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "summary": {
                "status": "wetlab_broad_screen_primary_runner_ready",
                "compute_pid": 1234,
                "heartbeat_pid": 5678,
            }
        }

    monkeypatch.setattr(mod.primary_runner_mod, "run", fake_run)

    payload = mod.run(
        lane_json=str(lane_json),
        python_bin="python3",
        target_id="",
        shard_id="",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
        out_md=str(tmp_path / "runner.md"),
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_mapping_fix_retry_runner_ready"
    assert summary["target_id"] == "SARS-CoV-2 Mpro"
    assert summary["shard_id"] == "01_of_20"
    assert captured["target_id"] == "SARS-CoV-2 Mpro"
    assert captured["shard_id"] == "01_of_20"
    assert captured["command_kind"] == "throughput_preflight"


def test_run_wetlab_mapping_fix_retry_resolves_target_specific_lane_when_generic_missing(monkeypatch, tmp_path: Path) -> None:
    target_lane = tmp_path / "runs" / "tcruzi_pde_mapping_fix_retry_lane_current.json"
    target_lane.parent.mkdir(parents=True, exist_ok=True)
    target_lane.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_mapping_fix_retry_lane_ready",
                    "target_id": "T. cruzi PDE",
                    "shard_id": "07_of_20",
                    "selected_command_kind": "throughput_preflight",
                    "ready_for_mapping_fix_retry": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    captured: dict[str, object] = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"summary": {"status": "wetlab_broad_screen_primary_runner_ready", "compute_pid": 1, "heartbeat_pid": 2}}

    monkeypatch.setattr(mod.primary_runner_mod, "run", fake_run)

    payload = mod.run(
        lane_json=str(tmp_path / "runs" / "wetlab_mapping_fix_retry_lane_current.json"),
        python_bin="python3",
        target_id="T. cruzi PDE",
        shard_id="",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
        out_md=str(tmp_path / "runner.md"),
    )

    assert payload["summary"]["target_id"] == "T. cruzi PDE"
    assert payload["summary"]["shard_id"] == "07_of_20"
    assert payload["structured"]["mapping_fix_retry_lane_artifact"].endswith("runs/tcruzi_pde_mapping_fix_retry_lane_current.json")
    assert captured["target_id"] == "T. cruzi PDE"
    assert captured["shard_id"] == "07_of_20"


def test_run_wetlab_mapping_fix_retry_clears_stage_artifacts_before_launch(monkeypatch, tmp_path: Path) -> None:
    lane_json = tmp_path / "lane.json"
    lane_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_mapping_fix_retry_lane_ready",
                    "target_id": "SARS-CoV-2 Mpro",
                    "shard_id": "01_of_20",
                    "selected_command_kind": "throughput_preflight",
                    "ready_for_mapping_fix_retry": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cleanup_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        mod.primary_runner_mod,
        "prepare_fresh_stage_artifacts",
        lambda **kwargs: cleanup_calls.append(kwargs) or {},
    )
    monkeypatch.setattr(
        mod.primary_runner_mod,
        "run",
        lambda **kwargs: {"summary": {"status": "wetlab_broad_screen_primary_runner_ready", "compute_pid": 1, "heartbeat_pid": 2}},
    )

    mod.run(
        lane_json=str(lane_json),
        python_bin="python3",
        target_id="",
        shard_id="",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
        out_md=str(tmp_path / "runner.md"),
    )

    assert cleanup_calls
    assert cleanup_calls[0]["target_id"] == "SARS-CoV-2 Mpro"
    assert cleanup_calls[0]["shard_id"] == "01_of_20"
    assert cleanup_calls[0]["clear_stage_artifacts"] is True
