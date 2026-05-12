from __future__ import annotations

import json
from pathlib import Path

from tools.compare_biorxiv_external_validation_runs import main


def _write_manifest(root: Path, set_id: str, pass_value: bool, task_id: str, profile: str, pr_auc: float, ef1: float, top20: float, score_col: str) -> None:
    set_dir = root / set_id
    set_dir.mkdir(parents=True, exist_ok=True)
    pipe = root / f"{set_id}_{task_id}_pipe.json"
    pipe.write_text(
        json.dumps(
            {
                "stages": {
                    "stage6_operational_gate": {
                        "ranking_pr_auc": pr_auc,
                        "ranking_ef1": ef1,
                        "ranking_topk_hit_rate": top20,
                        "ranking_score_col_used": score_col,
                        "operational_gate_pass": True,
                        "mean_min_distance_A": 3.0,
                    }
                }
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "set_id": set_id,
        "pass": pass_value,
        "tasks": [
            {
                "task_id": task_id,
                "domain": "gpcr",
                "kind": "ligand_stress",
                "pass": True,
                "profile_json": profile,
                "pipeline_summary_json": str(pipe),
                "metrics": {
                    "ranking_pr_auc": pr_auc,
                    "ranking_ef1": ef1,
                    "operational_gate_pass": True,
                },
            }
        ],
    }
    (set_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_compare_biorxiv_external_validation_runs(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    (baseline / "summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    (candidate / "summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    _write_manifest(baseline, "set1_core_blind", True, "gpcr_core_full", "config/v6.json", 0.4, 80.0, 0.15, "binding_score_composite_v4")
    _write_manifest(candidate, "set1_core_blind", True, "gpcr_core_full", "config/v7.json", 0.9, 90.0, 0.30, "binding_score_composite_v7")

    out_root = tmp_path / "out"
    rc = main([
        "--baseline-run-root", str(baseline),
        "--candidate-run-root", str(candidate),
        "--out-root", str(out_root),
        "--label", "test",
    ])
    assert rc == 0
    summary = json.loads((out_root / "biorxiv_run_comparison_test" / "summary.json").read_text(encoding="utf-8"))
    assert summary["tasks_with_pr_improvement"] == 1
    assert summary["tasks_with_pr_regression"] == 0
    row = summary["task_rows"][0]
    assert row["baseline_score_col"] == "binding_score_composite_v4"
    assert row["candidate_score_col"] == "binding_score_composite_v7"
    assert row["delta_pr_auc"] == 0.5


def test_compare_biorxiv_candidate_scope_ignores_baseline_only_sets(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    (baseline / "summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    (candidate / "summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    _write_manifest(
        baseline,
        "set3_operational_smoke",
        True,
        "gpcr_smoke",
        "config/v6.json",
        0.7,
        80.0,
        0.2,
        "binding_score_composite_v4",
    )
    _write_manifest(
        baseline,
        "set1_core_blind",
        True,
        "gpcr_core_full",
        "config/v6.json",
        0.4,
        80.0,
        0.15,
        "binding_score_composite_v4",
    )
    _write_manifest(
        candidate,
        "set1_core_blind",
        True,
        "gpcr_core_full",
        "config/v7.json",
        0.9,
        90.0,
        0.30,
        "binding_score_composite_v7",
    )

    out_root = tmp_path / "out"
    rc = main(
        [
            "--baseline-run-root",
            str(baseline),
            "--candidate-run-root",
            str(candidate),
            "--out-root",
            str(out_root),
            "--label",
            "candidate_scope",
            "--task-scope",
            "candidate",
        ]
    )

    assert rc == 0
    summary = json.loads(
        (out_root / "biorxiv_run_comparison_candidate_scope" / "summary.json").read_text(encoding="utf-8")
    )
    assert summary["task_scope"] == "candidate"
    assert summary["baseline_task_count_total"] == 2
    assert summary["candidate_task_count_total"] == 1
    assert summary["task_count"] == 1
    assert list(summary["set_summary"]) == ["set1_core_blind"]
