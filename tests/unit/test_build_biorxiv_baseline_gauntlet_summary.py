from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_baseline_gauntlet_summary(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    comp_dir = runs / "cmp"
    comp_dir.mkdir(parents=True)
    comparison = {
        "tasks_with_pr_improvement": 2,
        "tasks_with_pr_regression": 0,
        "profile_changed_task_count": 3,
        "task_rows": [
            {
                "set_id": "set1_core_blind",
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "profile_changed": False,
                "baseline_score_col": "binding_score_composite_v7",
                "candidate_score_col": "binding_score_composite_v7",
                "delta_pr_auc": 0.0,
                "delta_ef1": 0.0,
                "delta_top20_hit_rate": 0.0,
            },
            {
                "set_id": "set2_expanded_ood",
                "task_id": "gpcr_chembl50_full",
                "domain": "gpcr",
                "profile_changed": True,
                "baseline_score_col": "binding_score_composite_v4",
                "candidate_score_col": "binding_score_composite_v7",
                "delta_pr_auc": 0.1655,
                "delta_ef1": 15.9422,
                "delta_top20_hit_rate": 0.0,
            },
            {
                "set_id": "set2_expanded_ood",
                "task_id": "ion_trpv1_chembl50_full",
                "domain": "ion_channel",
                "profile_changed": True,
                "baseline_score_col": "binding_score_composite_v4",
                "candidate_score_col": "binding_score_composite_v6",
                "delta_pr_auc": 0.0171,
                "delta_ef1": 1.9804,
                "delta_top20_hit_rate": 0.0,
            },
        ],
    }
    comp_json = comp_dir / "summary.json"
    comp_json.write_text(json.dumps(comparison), encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_baseline_gauntlet_summary.py"),
            "--comparison-json",
            str(comp_json),
            "--out-root",
            str(runs),
            "--label",
            "test",
        ],
        check=True,
    )

    assert (runs / "biorxiv_baseline_gauntlet_main_table_test.csv").exists()
    assert (runs / "biorxiv_baseline_gauntlet_main_table_test.md").exists()
    para = (runs / "biorxiv_baseline_gauntlet_results_paragraph_test.md").read_text(encoding="utf-8")
    assert "v7r1" in para
    assert "gpcr_chembl50_full" in para

