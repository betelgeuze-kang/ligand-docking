import json

import pandas as pd

from tools import build_target_ai_interval_policy as bp


def _sample_df():
    rows = [
        # Chignolin: interval 8 is feasible and faster
        {"target": "Chignolin", "ai_interval": 1, "speedup_vs_interval1": 1.0, "rmsd_vs_interval1_aligned": 0.0},
        {"target": "Chignolin", "ai_interval": 8, "speedup_vs_interval1": 2.0, "rmsd_vs_interval1_aligned": 0.05},
        # BBA5: high-speed candidate violates aligned-loss threshold
        {"target": "BBA5", "ai_interval": 1, "speedup_vs_interval1": 1.0, "rmsd_vs_interval1_aligned": 0.0},
        {"target": "BBA5", "ai_interval": 10, "speedup_vs_interval1": 2.4, "rmsd_vs_interval1_aligned": 6.0},
    ]
    return pd.DataFrame(rows)


def test_build_policy_from_sweep_df_threshold_and_fallback():
    df = _sample_df()
    rows_df, policy, summary = bp.build_policy_from_sweep_df(
        df=df,
        targets=["Chignolin", "BBA5"],
        min_speedup=1.2,
        max_aligned_loss=0.2,
        baseline_interval=1,
    )
    assert policy["Chignolin"] == 8
    assert policy["BBA5"] == 1
    assert summary["targets_threshold_pass"] == 1
    assert summary["targets_fallback_baseline"] == 1
    assert set(rows_df["selection_reason"]) == {"threshold_pass", "fallback_baseline"}


def test_run_build_writes_json_csv_and_spec(tmp_path):
    in_csv = tmp_path / "sweep.csv"
    out_csv = tmp_path / "policy.csv"
    out_json = tmp_path / "policy.json"
    out_spec = tmp_path / "policy.spec.txt"
    _sample_df().to_csv(in_csv, index=False)

    args = bp.build_parser().parse_args(
        [
            "--sweep-target-csv",
            str(in_csv),
            "--targets",
            "Chignolin,BBA5",
            "--min-speedup",
            "1.2",
            "--max-aligned-loss",
            "0.2",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-spec",
            str(out_spec),
        ]
    )
    payload = bp.run_build(args)
    assert out_csv.exists()
    assert out_json.exists()
    assert out_spec.exists()
    assert "policy" in payload
    assert payload["policy"]["Chignolin"] == 8
    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert saved["policy"]["BBA5"] == 1
