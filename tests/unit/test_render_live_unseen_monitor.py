import json

from tools import render_live_unseen_monitor as mon


def test_summarize_recent_quality_reads_training_metrics(tmp_path):
    s1 = tmp_path / "c1_summary.json"
    s2 = tmp_path / "c2_summary.json"
    s1.write_text(
        json.dumps(
            {
                "training_payload": {
                    "result": {
                        "best_val_loss": 0.120,
                        "test_rmse": 0.180,
                        "test_mae": 0.090,
                        "epochs_trained": 6,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    s2.write_text(
        json.dumps(
            {
                "training_payload": {
                    "result": {
                        "best_val_loss": 0.100,
                        "test_rmse": 0.150,
                        "test_mae": 0.080,
                        "epochs_trained": 7,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    history = [
        {"summary_json": str(s1)},
        {"summary_json": str(s2)},
    ]
    out = mon._summarize_recent_quality(history, window=12)
    assert out["rows"] == 2
    assert out["metrics_rows"] == 2
    assert out["coverage_pct"] == 100.0
    assert isinstance(out.get("latest", {}), dict)
    assert float(out["latest"]["test_rmse"]) == 0.150


def test_build_snapshot_uses_state_target_fallback(tmp_path):
    state_json = tmp_path / "state.json"
    history_jsonl = tmp_path / "history.jsonl"
    state_json.write_text(
        json.dumps(
            {
                "cycles_completed": 3,
                "trained_protein_ids": [],
                "failed_protein_ids": [],
                "phase": "fetch",
                "current_target": "Live_test_target",
                "current_note": "testing",
                "current_cycle": 4,
                "current_date_tag": "tag_004",
            }
        ),
        encoding="utf-8",
    )
    history_jsonl.write_text("", encoding="utf-8")
    snap = mon._build_snapshot(
        state_json=str(state_json),
        history_jsonl=str(history_jsonl),
        process_pattern="run_live_unseen_protein_learning_loop.py",
        tail_lines=5,
        quality_window=6,
    )
    ac = snap.get("active_cycle", {})
    assert isinstance(ac, dict)
    assert str(ac.get("current_target", "")).strip() == "Live_test_target"
    assert str(ac.get("phase", "")).strip().lower() == "fetch"


def test_build_snapshot_prefers_profile_training_log_over_legacy(tmp_path):
    state_json = tmp_path / "live_unseen_learning_state_hip.json"
    history_jsonl = tmp_path / "history.jsonl"
    state_json.write_text(
        json.dumps(
            {
                "cycles_completed": 1,
                "phase": "sleep",
                "current_cycle": 2,
                "current_date_tag": "live_unseen_hip_002_000000",
                "trained_protein_ids": [],
                "failed_protein_ids": [],
            }
        ),
        encoding="utf-8",
    )
    history_jsonl.write_text("", encoding="utf-8")

    legacy_log = tmp_path / "live_unseen_learning_v5_live_unseen_v5_003_040342_training.log"
    legacy_log.write_text(
        "Epoch 1/1, Train Throughput: 40.8 samples/s\n",
        encoding="utf-8",
    )
    hip_log = tmp_path / "live_unseen_learning_hip_live_unseen_hip_002_000000_training.log"
    hip_log.write_text(
        "Epoch 1/1, Train Throughput: 150.5 samples/s\n",
        encoding="utf-8",
    )

    snap = mon._build_snapshot(
        state_json=str(state_json),
        history_jsonl=str(history_jsonl),
        process_pattern="run_live_unseen_protein_learning_loop.py",
        tail_lines=5,
        quality_window=6,
    )
    assert str(snap.get("latest_training_log", "")).endswith("live_unseen_learning_hip_live_unseen_hip_002_000000_training.log")
    assert float(snap.get("latest_training_throughput_samples_per_sec", 0.0)) == 150.5
