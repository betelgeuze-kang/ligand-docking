from __future__ import annotations

import json
from pathlib import Path

from tools import run_wetlab_hard_target_rescue_lane as mod


class _DummyCompleted:
    def __init__(self, stdout: str = "0\n") -> None:
        self.stdout = stdout


class _DummyPopen:
    def __init__(self, pid: int) -> None:
        self.pid = pid


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_wetlab_hard_target_rescue_lane_rewrites_bridge_command_and_launches_sidecars(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DEFAULT_OUT_MD", str(tmp_path / "runs" / "wetlab_hard_target_rescue_runner_current.md"))
    monkeypatch.setattr(mod, "DEFAULT_WATCH_LAUNCHER", "tools/launch_wetlab_broad_screen_primary_watch_loop.py")

    rescue_lane_json = tmp_path / "runs" / "wetlab_hard_target_rescue_lane_current.json"
    rescue_anchor_json = tmp_path / "runs" / "wetlab_rescue_anchor_artifacts_current.json"
    execution_queue_json = tmp_path / "runs" / "wetlab_broad_screen_execution_queue_current.json"
    compound_universe_json = tmp_path / "runs" / "wetlab_broad_screen_compound_universe_current.json"
    portfolio_json = tmp_path / "runs" / "wetlab_partner_target_portfolio_current.json"
    target_native_csv = tmp_path / "config" / "real_drug_targets_native_v1.csv"

    _write_json(
        rescue_lane_json,
        {
            "summary": {
                "focus_target_id": "T. cruzi PDE",
                "focus_shard_id": "20_of_20",
                "focus_ready_for_manual_retry": True,
                "focus_rescue_base_command_kind": "throughput_preflight_tuned_gate51",
            },
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "shard_id": "20_of_20",
                    "rescue_base_command_kind": "throughput_preflight_tuned_gate51",
                }
            ],
        },
    )
    _write_json(
        rescue_anchor_json,
        {
            "summary": {
                "rescue_target_native_csv": str(tmp_path / "runs" / "rescues" / "native.csv"),
                "rescue_target_pocket_csv": str(tmp_path / "runs" / "rescues" / "pocket.csv"),
                "rescue_target_ligand_csv": str(tmp_path / "runs" / "rescues" / "ligand.csv"),
                "attach_rescue_target_native_csv": True,
                "attach_rescue_target_pocket_csv": True,
                "attach_rescue_target_ligand_csv": True,
            }
        },
    )
    _write_json(execution_queue_json, {"rows": []})
    _write_json(compound_universe_json, {"rows": []})
    _write_json(portfolio_json, {"rows": []})
    target_native_csv.parent.mkdir(parents=True, exist_ok=True)
    target_native_csv.write_text("target,native_pdb_path,pdb_id,notes\n", encoding="utf-8")

    artifact_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        mod.bridge_mod,
        "build_payload",
        lambda **_: {
            "summary": {},
            "structured": {
                "preferred_log_path": str(artifact_dir / "throughput_preflight.log"),
                "preferred_pid_path": str(artifact_dir / "throughput_preflight.pid"),
                "preferred_summary_json": str(artifact_dir / "throughput_run_gate51_summary.json"),
            },
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate51",
                    "command": (
                        "python3 tools/run_ligand_htvs_pipeline.py "
                        "--target-native-csv old_native.csv "
                        "--target-pocket-csv old_pocket.csv "
                        "--target-ligand-csv old_ligands.csv "
                        "--target-ligand-roles fit,eval "
                        "--gate-max-mean-min-distance-A 5.1 "
                        "--strict-gate-max-mean-min-distance-A 5.1 "
                        "--traj-prod-speedpack "
                        "--traj-prod-light-artifacts"
                    ),
                }
            ],
        },
    )

    runtime_calls: list[dict] = []
    monkeypatch.setattr(mod.runtime_mod, "run_event", lambda **kwargs: runtime_calls.append(kwargs))

    run_calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs):
        run_calls.append(cmd)
        if "launch_wetlab_broad_screen_heartbeat_loop.py" in " ".join(cmd):
            return _DummyCompleted("111\n")
        if "launch_wetlab_broad_screen_primary_watch_loop.py" in " ".join(cmd):
            return _DummyCompleted("222\n")
        return _DummyCompleted("0\n")

    popen_calls: list[list[str]] = []

    def _fake_popen(cmd: list[str], **kwargs):
        popen_calls.append(cmd)
        return _DummyPopen(333)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(mod.subprocess, "Popen", _fake_popen)

    payload = mod.run(
        rescue_lane_json=str(rescue_lane_json),
        rescue_anchor_json=str(rescue_anchor_json),
        python_bin="python3",
        execution_queue_json=str(execution_queue_json),
        compound_universe_json=str(compound_universe_json),
        portfolio_json=str(portfolio_json),
        target_native_csv=str(target_native_csv),
        shard_id="",
        interval_sec=15.0,
        replace_heartbeat=True,
        refresh_lane=False,
        refresh_anchor=False,
    )

    assert payload["summary"]["target_id"] == "T. cruzi PDE"
    assert payload["summary"]["shard_id"] == "20_of_20"
    assert payload["summary"]["selected_command_kind"] == "throughput_preflight_hard_target_rescue"
    assert payload["summary"]["rescue_base_command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["compute_pid"] == 333
    assert payload["summary"]["heartbeat_pid"] == 111
    assert payload["summary"]["watcher_pid"] == 222
    assert runtime_calls and runtime_calls[0]["event"] == "start"
    assert runtime_calls[0]["active_stage_label"] == "broad_screen_primary_shard_hard_target_rescue"

    heartbeat_cmd = next(cmd for cmd in run_calls if "launch_wetlab_broad_screen_heartbeat_loop.py" in " ".join(cmd))
    assert "--replace" in heartbeat_cmd

    rewritten_command = payload["rows"][0]["rewritten_command"]
    assert "--target-native-csv" in rewritten_command
    assert "rescues/native.csv" in rewritten_command
    assert "--target-pocket-csv" in rewritten_command
    assert "rescues/pocket.csv" in rewritten_command
    assert "--eval-split-csv" in rewritten_command
    assert "rescues/ligand.csv" in rewritten_command
    assert "--target-ligand-csv" not in rewritten_command
    assert "--target-ligand-roles" not in rewritten_command
    assert "--gate-max-mean-min-distance-A" in rewritten_command and "2.5" in rewritten_command
    assert "--no-traj-prod-speedpack" in rewritten_command
    assert "--no-traj-prod-light-artifacts" in rewritten_command
    assert "--traj-prod-profile-intent" in rewritten_command and "hard_target_rescue_local_refine_v1" in rewritten_command

    pid_path = artifact_dir / "throughput_preflight.pid"
    assert pid_path.read_text(encoding="utf-8").strip() == "333"
    out_json = tmp_path / "runs" / "wetlab_hard_target_rescue_runner_current.json"
    assert out_json.exists()
