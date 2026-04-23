import json
from pathlib import Path

import pandas as pd

from tools import run_active_learning_cycle as mod


def test_run_active_learning_cycle_dry_run_creates_summary(tmp_path):
    pair_csv = tmp_path / "pair.csv"
    acc_csv = tmp_path / "acc.csv"
    st2_csv = tmp_path / "stage2.csv"
    out_prefix = tmp_path / "al_cycle"

    pd.DataFrame(
        [
            {"target": "A", "paired": 0, "reason": "missing", "rmsd_aligned_A": None},
            {"target": "B", "paired": 1, "reason": "ok", "rmsd_aligned_A": 8.0},
            {"target": "C", "paired": 1, "reason": "ok", "rmsd_aligned_A": 1.0},
        ]
    ).to_csv(pair_csv, index=False)
    pd.DataFrame(
        [
            {"target": "A", "avg_rmsd_vs_native_aligned": 1.0},
            {"target": "B", "avg_rmsd_vs_native_aligned": 0.8},
            {"target": "C", "avg_rmsd_vs_native_aligned": 0.1},
        ]
    ).to_csv(acc_csv, index=False)
    pd.DataFrame(
        [
            {"target": "A", "ai_uncertainty_score_on": 0.6, "ai_uncertainty_fallback_ratio_on": 0.1, "physics_violations_on": 1.0},
            {"target": "B", "ai_uncertainty_score_on": 0.4, "ai_uncertainty_fallback_ratio_on": 0.08, "physics_violations_on": 0.0},
            {"target": "C", "ai_uncertainty_score_on": 0.1, "ai_uncertainty_fallback_ratio_on": 0.0, "physics_violations_on": 0.0},
        ]
    ).to_csv(st2_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--targets",
            "A,B,C",
            "--ood-pair-csv",
            str(pair_csv),
            "--accuracy-external-csv",
            str(acc_csv),
            "--stage2-csv",
            str(st2_csv),
            "--out-prefix",
            str(out_prefix),
            "--dry-run",
        ]
    )
    payload = mod.run_cycle(args)

    assert payload["pass"] is True
    assert payload["dry_run"] is True
    assert payload["summary"]["hard_mining_selected_targets_count"] >= 1
    assert Path(f"{out_prefix}_summary.json").exists()
    assert Path(f"{out_prefix}_summary.md").exists()

    saved = json.loads(Path(f"{out_prefix}_summary.json").read_text(encoding="utf-8"))
    assert saved["summary"]["curriculum_executed"] is False
