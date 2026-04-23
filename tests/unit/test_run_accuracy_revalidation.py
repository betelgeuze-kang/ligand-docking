from pathlib import Path

from tools import run_accuracy_revalidation as rar


def test_run_gate_with_retries_stops_on_first_pass(monkeypatch, tmp_path):
    calls = []

    def _fake_run_gate(**kwargs):
        calls.append(
            (
                kwargs["speed_mode"],
                int(kwargs["speed_mode_replicas"]),
                int(kwargs["speed_profile_max_replicas"]),
            )
        )
        passed = len(calls) >= 2
        return {
            "cmd": [],
            "exit_code": 0 if passed else 2,
            "out_json": str(kwargs["out_json"]),
            "out_csv": str(kwargs["out_csv"]),
            "summary_pass": bool(passed),
            "failed_metrics_count": 0 if passed else 1,
            "failed_targets": [],
        }

    monkeypatch.setattr(rar, "_run_gate", _fake_run_gate)

    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    ret = rar._run_gate_with_retries(
        gate_script="tools/validate_accuracy_gate.py",
        targets="Chignolin",
        samples=1,
        steps=10,
        runs=1,
        noise=0.08,
        strict_mode=True,
        enforce_speed_gate=True,
        speedup_threshold=12.0,
        speedup_per_target_threshold=0.0,
        sample_gpu_metrics=None,
        disable_stochastic_noise=None,
        precompute_stochastic_noise=None,
        precompute_stochastic_noise_block_steps=None,
        retry_profiles=[
            {"speed_mode": "fast", "speed_mode_replicas": 32, "speed_profile_max_replicas": 128},
            {"speed_mode": "turbo", "speed_mode_replicas": 64, "speed_profile_max_replicas": 256},
            {"speed_mode": "extreme", "speed_mode_replicas": 128, "speed_profile_max_replicas": 512},
        ],
        gate_retry_max=3,
        out_json=str(out_json),
        out_csv=str(out_csv),
        env={},
    )

    assert ret["attempt_count"] == 2
    assert ret["summary_pass"] is True
    assert calls[0] == ("fast", 32, 128)
    assert calls[1] == ("turbo", 64, 256)
    assert Path(ret["out_json"]).name == "gate.json"
    assert Path(ret["out_csv"]).name == "gate.csv"


def test_attempt_rows_csv_written(tmp_path):
    stages = [
        {
            "name": "smoke",
            "attempts": [
                {
                    "attempt": 1,
                    "exit_code": 2,
                    "summary_pass": False,
                    "failed_metrics_count": 1,
                    "failed_metrics": [{"metric": "avg_speedup_on_vs_off"}],
                    "profile": {
                        "speed_mode": "fast",
                        "speed_mode_replicas": 32,
                        "speed_profile_max_replicas": 128,
                    },
                    "avg_speedup_on_vs_off": 8.5,
                    "avg_throughput_on": 1000.0,
                    "avg_throughput_off": 120.0,
                    "out_json": "runs/a.json",
                    "out_csv": "runs/a.csv",
                },
                {
                    "attempt": 2,
                    "exit_code": 0,
                    "summary_pass": True,
                    "failed_metrics_count": 0,
                    "failed_metrics": [],
                    "profile": {
                        "speed_mode": "turbo",
                        "speed_mode_replicas": 64,
                        "speed_profile_max_replicas": 256,
                    },
                    "avg_speedup_on_vs_off": 15.1,
                    "avg_throughput_on": 2000.0,
                    "avg_throughput_off": 132.0,
                    "out_json": "runs/b.json",
                    "out_csv": "runs/b.csv",
                },
            ]
        }
    ]
    rows = rar._build_attempt_rows(stages)
    out_csv = tmp_path / "attempts.csv"
    rar._write_attempt_rows_csv(str(out_csv), rows)
    text = out_csv.read_text(encoding="utf-8")
    assert "speed_mode_profile" in text
    assert "turbo" in text


def test_archive_attempt_artifacts_removes_attempt_files(tmp_path):
    out_prefix = tmp_path / "runs" / "accuracy_revalidation_case"
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    f1 = Path(f"{out_prefix}_smoke.json.attempt1.json")
    f2 = Path(f"{out_prefix}_smoke.csv.attempt1.csv")
    f1.write_text("{}", encoding="utf-8")
    f2.write_text("target,pass\nA,1\n", encoding="utf-8")

    result = rar._archive_attempt_artifacts(
        out_prefix=str(out_prefix),
        archive_dir=str(tmp_path / "archive"),
        compress=True,
        remove_original=True,
    )
    assert result["archived_files"] == 2
    assert result["removed_files"] == 2
    assert Path(result["archive_path"]).exists()
    assert not f1.exists()
    assert not f2.exists()
