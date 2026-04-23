from __future__ import annotations

import json

from tools import run_wetlab_tcruzi_krs1_exploratory_retry as mod


def test_run_wetlab_tcruzi_krs1_exploratory_retry_prefers_execute_command(monkeypatch, tmp_path) -> None:
    lane_json = tmp_path / "lane.json"
    lane_json.write_text("{}", encoding="utf-8")
    (tmp_path / "hold.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    (tmp_path / "queue.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    (tmp_path / "bridge.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    (tmp_path / "tuning.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")

    monkeypatch.setattr(
        mod.lane_mod,
        "build_payload",
        lambda *args, **kwargs: {
            "summary": {
                "status": "wetlab_tcruzi_krs1_exploratory_retry_lane_ready",
                "target_id": "T. cruzi KRS1",
                "shard_id": "03_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate51",
                "throughput_execute_ready": True,
                "ready_for_manual_retry": True,
                "lane_label": "exploratory_gate5.1_candidate",
            },
            "rows": [],
        },
    )

    captured: dict[str, object] = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {"summary": {"compute_pid": 123, "heartbeat_pid": 456}}

    monkeypatch.setattr(mod.primary_runner_mod, "run", _fake_run)
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)

    payload = mod.run(
        lane_json=str(lane_json),
        hold_guard_json=str(tmp_path / "hold.json"),
        python_bin="python3",
        shard_id="",
        command_kind="",
        execution_queue_json=str(tmp_path / "queue.json"),
        throughput_bridge_json=str(tmp_path / "bridge.json"),
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        stage6_tuning_surface_json=str(tmp_path / "tuning.json"),
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
    )

    assert captured["target_id"] == "T. cruzi KRS1"
    assert captured["shard_id"] == "03_of_20"
    assert captured["command_kind"] == "throughput_execute_tuned_gate51"
    assert payload["summary"]["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["launched_command_kind"] == "throughput_execute_tuned_gate51"


def test_run_wetlab_tcruzi_krs1_exploratory_retry_can_force_preflight_only(monkeypatch, tmp_path) -> None:
    lane_json = tmp_path / "lane.json"
    lane_json.write_text("{}", encoding="utf-8")
    (tmp_path / "hold.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    (tmp_path / "queue.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    (tmp_path / "bridge.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    (tmp_path / "tuning.json").write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")

    monkeypatch.setattr(
        mod.lane_mod,
        "build_payload",
        lambda *args, **kwargs: {
            "summary": {
                "status": "wetlab_tcruzi_krs1_exploratory_retry_lane_ready",
                "target_id": "T. cruzi KRS1",
                "shard_id": "03_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate51",
                "throughput_execute_ready": True,
                "ready_for_manual_retry": True,
                "lane_label": "exploratory_gate5.1_candidate",
            },
            "rows": [],
        },
    )

    captured: dict[str, object] = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {"summary": {"compute_pid": 123, "heartbeat_pid": 456}}

    monkeypatch.setattr(mod.primary_runner_mod, "run", _fake_run)
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)

    payload = mod.run(
        lane_json=str(lane_json),
        hold_guard_json=str(tmp_path / "hold.json"),
        python_bin="python3",
        shard_id="",
        command_kind="",
        execution_queue_json=str(tmp_path / "queue.json"),
        throughput_bridge_json=str(tmp_path / "bridge.json"),
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        stage6_tuning_surface_json=str(tmp_path / "tuning.json"),
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
        preflight_only=True,
    )

    assert captured["command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["launched_command_kind"] == "throughput_preflight_tuned_gate51"
