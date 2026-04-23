from __future__ import annotations

from tools import run_wetlab_stk17b_manual_retry as mod


def test_run_wetlab_stk17b_manual_retry_invokes_primary_runner(monkeypatch, tmp_path) -> None:
    lane_json = tmp_path / "lane.json"
    lane_json.write_text(
        '{"summary":{"status":"wetlab_stk17b_manual_retry_lane_ready","target_id":"STK17B (DRAK2)","shard_id":"12_of_20","selected_command_kind":"throughput_preflight_tuned_gate55","ready_for_manual_retry":true}}',
        encoding="utf-8",
    )

    captured = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {"summary": {"compute_pid": 123, "heartbeat_pid": 456}}

    monkeypatch.setattr(mod.primary_runner_mod, "run", _fake_run)
    monkeypatch.setattr(mod, "DEFAULT_OUT_MD", str(tmp_path / "out.md"))

    payload = mod.run(
        lane_json=str(lane_json),
        python_bin="python3",
        shard_id="",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
    )

    assert captured["target_id"] == "STK17B (DRAK2)"
    assert captured["shard_id"] == "12_of_20"
    assert captured["command_kind"] == "throughput_preflight_tuned_gate55"
    assert payload["summary"]["status"] == "wetlab_stk17b_manual_retry_runner_ready"
