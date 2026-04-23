from __future__ import annotations

import json
from pathlib import Path

from tools import run_wetlab_plpro_manual_retry as mod


def test_run_wetlab_plpro_manual_retry_invokes_primary_runner(monkeypatch, tmp_path: Path) -> None:
    lane_json = tmp_path / "lane.json"
    lane_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_plpro_manual_retry_lane_ready",
                    "target_id": "SARS-CoV-2 PLpro",
                    "shard_id": "16_of_20",
                    "selected_command_kind": "throughput_preflight",
                    "ready_for_manual_retry": True,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {"summary": {"compute_pid": 1234, "heartbeat_pid": 4321}}

    out_md = tmp_path / "runner_current.md"
    monkeypatch.setattr(mod.primary_runner_mod, "run", _fake_run)
    monkeypatch.setattr(mod, "DEFAULT_OUT_MD", str(out_md))

    payload = mod.run(
        lane_json=str(lane_json),
        python_bin="python3",
        shard_id="",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=5.0,
        replace_heartbeat=True,
    )

    assert captured["target_id"] == "SARS-CoV-2 PLpro"
    assert captured["shard_id"] == "16_of_20"
    assert captured["command_kind"] == "throughput_preflight"
    assert captured["replace_heartbeat"] is True
    assert payload["summary"]["status"] == "wetlab_plpro_manual_retry_runner_ready"
    assert out_md.exists()
