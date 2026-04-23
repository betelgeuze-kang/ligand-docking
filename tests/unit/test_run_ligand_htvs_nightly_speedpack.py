from __future__ import annotations

import json
from pathlib import Path

from tools import run_ligand_htvs_nightly as nightly


def test_run_ligand_htvs_nightly_forwards_speedpack_profile_flags(tmp_path: Path, monkeypatch) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "version": "pilot_profile",
                "targets": "ADRB2_GPCR_BLIND",
                "run_scope": "full",
                "ligand_csv": "config/mock.csv",
                "trajectory_engine_mode": "rust_hip",
                "stage3_score_only": True,
                "emit_sla_summary": True,
                "make_bundle_zip": False,
                "run_calibration": False,
                "run_ranking_eval": False,
                "gate_distance_override_csv": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
                "traj_auto_fast_output": True,
                "traj_job_batch_autotune_candidates": "2,4,8,16",
                "traj_writer_workers": 5,
                "traj_writer_max_pending": 128,
                "traj_prod_speedpack": True,
                "traj_prod_adaptive_frame_budget": True,
                "traj_prod_early_stop_enabled": True,
                "traj_prod_early_stop_min_frames_full": 220,
                "traj_prod_early_stop_window": 16,
                "traj_dynamic_adress_fraction": 0.2,
                "smoke": {"replicas": 8, "max_ligands": 8, "jobs_per_target": 8, "traj_frames": 80, "max_jobs_score": 8},
                "full": {"replicas": 64, "max_ligands": 64, "jobs_per_target": 64, "traj_frames": 120, "max_jobs_score": 64},
                "gate": {"enforce_operational_gate": False, "strict_fail_fast": False},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    seen = {}

    def _fake_run(cmd, env):
        seen["cmd"] = list(cmd)
        return {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "ok": True,
            "returncode": 0,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(nightly, "_run", _fake_run)

    payload = nightly.run_nightly(
        nightly.build_parser().parse_args(
            [
                "--profile-json",
                str(profile),
                "--out-prefix",
                str(tmp_path / "nightly"),
                "--dry-run",
            ]
        )
    )

    cmd = seen["cmd"]
    assert "--traj-prod-speedpack" in cmd
    assert "--traj-prod-adaptive-frame-budget" in cmd
    assert "--traj-prod-early-stop-enabled" in cmd
    assert cmd[cmd.index("--traj-prod-early-stop-min-frames-full") + 1] == "220"
    assert "--traj-job-batch-autotune-candidates" in cmd
    assert cmd[cmd.index("--traj-job-batch-autotune-candidates") + 1] == "2,4,8,16"
    assert "--traj-writer-workers" in cmd
    assert cmd[cmd.index("--traj-writer-workers") + 1] == "5"
    assert "--stage3-score-only" in cmd
    assert "--gate-distance-override-csv" in cmd
    assert cmd[cmd.index("--gate-distance-override-csv") + 1] == "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
    assert "--emit-sla-summary" in cmd
    assert "--no-make-bundle-zip" in cmd
    assert "--no-run-calibration" in cmd
    assert "--no-run-ranking-eval" in cmd
    assert "--traj-dynamic-adress-fraction" in cmd
    assert cmd[cmd.index("--traj-dynamic-adress-fraction") + 1] == "0.2"
    assert payload["command"]["cmd"] == cmd
