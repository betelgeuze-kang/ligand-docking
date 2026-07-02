from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from tools.run_external_validation_baselines import main


def test_run_external_validation_baselines(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"
    queue_csv = tmp_path / "queue.csv"
    current_json = tmp_path / "current_summary.json"
    current_md = tmp_path / "current_summary.md"
    current_rows = tmp_path / "current_rows.csv"
    current_topk = tmp_path / "current_topk.csv"
    current_unique = tmp_path / "current_unique.csv"

    scores_df = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "binder1", "binding_score_composite_v7": -10.0, "binding_energy_mmpbsa_kcal_mol_proxy": -1.0, "mean_min_distance_A": 3.0},
            {"target": "T1", "ligand_id": "decoy1", "binding_score_composite_v7": -5.0, "binding_energy_mmpbsa_kcal_mol_proxy": -2.0, "mean_min_distance_A": 2.0},
            {"target": "T1", "ligand_id": "decoy2", "binding_score_composite_v7": -4.0, "binding_energy_mmpbsa_kcal_mol_proxy": -3.0, "mean_min_distance_A": 1.0},
        ]
    )
    scores_df.to_csv(scores_csv, index=False)

    labels_df = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "binder1", "is_binder": 1, "reference_binding_kcal_mol": -9.0},
            {"target": "T1", "ligand_id": "decoy1", "is_binder": 0, "reference_binding_kcal_mol": 0.0},
            {"target": "T1", "ligand_id": "decoy2", "is_binder": 0, "reference_binding_kcal_mol": 0.0},
        ]
    )
    labels_df.to_csv(labels_csv, index=False)

    split_df = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "binder1", "role": "far_ood_eval"},
            {"target": "T1", "ligand_id": "decoy1", "role": "far_ood_eval"},
            {"target": "T1", "ligand_id": "decoy2", "role": "far_ood_eval"},
        ]
    )
    split_df.to_csv(split_csv, index=False)
    split_df[["target", "ligand_id"]].to_csv(queue_csv, index=False)

    eval_cmd = [
        sys.executable,
        "tools/evaluate_ligand_ranking_metrics.py",
        "--scores-csv",
        str(scores_csv),
        "--labels-csv",
        str(labels_csv),
        "--score-col",
        "binding_score_composite_v7",
        "--probability-score-col",
        "binding_score_composite_v7",
        "--binder-col",
        "is_binder",
        "--ref-energy-col",
        "reference_binding_kcal_mol",
        "--binder-threshold-kcal-mol",
        "-3.0",
        "--split-csv",
        str(split_csv),
        "--split-role-col",
        "role",
        "--split-target-col",
        "target",
        "--split-ligand-col",
        "ligand_id",
        "--expected-keys-csv",
        str(queue_csv),
        "--expected-target-col",
        "target",
        "--expected-ligand-col",
        "ligand_id",
        "--min-expected-score-coverage",
        "1.0",
        "--eval-roles",
        "far_ood_eval",
        "--ood-eval-roles",
        "",
        "--require-split-for-eval",
        "--no-require-ood-eval",
        "--topk-list",
        "10,20,50",
        "--bootstrap-n",
        "30",
        "--bootstrap-seed",
        "7",
        "--bootstrap-bedroc-alpha",
        "20.0",
        "--ece-bins",
        "10",
        "--probability-logit-scale",
        "1.4",
        "--labels-driven-eval",
        "--missing-score-policy",
        "worst",
        "--missing-score-worst-margin",
        "1000.0",
        "--out-detail-csv",
        str(current_rows),
        "--out-topk-csv",
        str(current_topk),
        "--out-unique-csv",
        str(current_unique),
        "--out-json",
        str(current_json),
        "--out-md",
        str(current_md),
    ]
    import subprocess

    subprocess.run(eval_cmd, check=True, cwd=Path.cwd())

    inner_summary = tmp_path / "pipeline_summary.json"
    inner_summary.write_text(
        json.dumps(
            {
                "stages": {
                    "stage5_ranking_eval": {
                        "cmd": eval_cmd,
                    }
                }
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    run_root = tmp_path / "run_root"
    set_dir = run_root / "set1_core_blind"
    set_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "set_id": "set1_core_blind",
        "tasks": [
            {
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "pass": True,
                "profile_json": "config/mock.json",
                "pipeline_summary_json": str(inner_summary),
                "metrics": {
                    "operational_gate_pass": True,
                    "strict_gate_pass": True,
                },
            }
        ],
    }
    (set_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    out_root = tmp_path / "out"
    rc = main(
        [
            "--run-root",
            str(run_root),
            "--out-root",
            str(out_root),
            "--label",
            "test",
            "--spec-json",
            "config/external_validation_baselines_v1.json",
        ]
    )
    assert rc == 0

    summary = json.loads((out_root / "biorxiv_baseline_comparison_test" / "summary.json").read_text(encoding="utf-8"))
    assert summary["task_count"] == 1
    assert summary["task_winner_count_current"] == 1
    assert summary["tasks"][0]["primary_winner"]["score_col"] == "binding_score_composite_v7"

    leaderboard = pd.read_csv(out_root / "biorxiv_baseline_comparison_test" / "score_leaderboard.csv")
    assert set(leaderboard["score_alias"]) >= {"composite_v7", "proxy_energy", "distance_only"}


def test_run_external_validation_baselines_require_tasks_blocks_empty_root(tmp_path: Path) -> None:
    run_root = tmp_path / "missing_run_root"
    out_root = tmp_path / "out"

    rc = main(
        [
            "--run-root",
            str(run_root),
            "--out-root",
            str(out_root),
            "--label",
            "empty",
            "--spec-json",
            "config/external_validation_baselines_v1.json",
            "--require-tasks",
        ]
    )

    assert rc == 1
    summary = json.loads(
        (out_root / "biorxiv_baseline_comparison_empty" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["ok"] is False
    assert summary["run_root_exists"] is False
    assert summary["task_count"] == 0
    assert "run_root_missing" in summary["blockers"]
    assert "set_manifest_missing" in summary["blockers"]
    assert "ligand_stress_tasks_missing" in summary["blockers"]
