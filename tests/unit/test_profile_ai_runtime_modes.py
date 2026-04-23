import pandas as pd

from tools.profile_ai_runtime_modes import build_mode_summary


def test_build_mode_summary_prefers_error_free_modes():
    df = pd.DataFrame(
        [
            {
                "target": "A",
                "runtime_mode": "scripted",
                "throughput_steps_per_sec": 200.0,
                "runtime_error": "",
            },
            {
                "target": "B",
                "runtime_mode": "scripted",
                "throughput_steps_per_sec": 180.0,
                "runtime_error": "",
            },
            {
                "target": "A",
                "runtime_mode": "compiled",
                "throughput_steps_per_sec": 250.0,
                "runtime_error": "compile fail",
            },
            {
                "target": "B",
                "runtime_mode": "compiled",
                "throughput_steps_per_sec": 240.0,
                "runtime_error": "",
            },
        ]
    )
    summary = build_mode_summary(df)
    assert summary["best_mode"] == "scripted"
    assert summary["modes"][0]["all_rows_error_free"] is True
    assert summary["modes"][1]["all_rows_error_free"] is False


def test_build_mode_summary_empty():
    df = pd.DataFrame(columns=["runtime_mode", "throughput_steps_per_sec", "runtime_error"])
    summary = build_mode_summary(df)
    assert summary["best_mode"] is None
    assert summary["modes"] == []
