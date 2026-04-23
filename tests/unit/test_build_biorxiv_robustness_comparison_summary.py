from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_robustness_comparison_summary(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    comparison = runs / "comparison.json"
    comparison.write_text(
        json.dumps(
            {
                "set_summary": {
                    "set1_core_blind": {"candidate_pass": True},
                    "set2_expanded_ood": {"candidate_pass": True},
                    "set3_operational_smoke": {"candidate_pass": True},
                },
                "task_rows": [
                    {
                        "set_id": "set1_core_blind",
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "baseline_pr_auc": 1.0,
                        "candidate_pr_auc": 0.85,
                        "delta_pr_auc": -0.15,
                        "baseline_ef1": 98.2,
                        "candidate_ef1": 98.2,
                        "delta_ef1": 0.0,
                        "baseline_top20_hit_rate": 0.30,
                        "candidate_top20_hit_rate": 0.25,
                        "delta_top20_hit_rate": -0.05,
                        "candidate_pass": True,
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "task_id": "ion_trpv1_chembl50_full",
                        "domain": "ion_channel",
                        "kind": "ligand_stress",
                        "baseline_pr_auc": 0.98,
                        "candidate_pr_auc": 0.99,
                        "delta_pr_auc": 0.01,
                        "baseline_ef1": 95.0,
                        "candidate_ef1": 95.0,
                        "delta_ef1": 0.0,
                        "baseline_top20_hit_rate": 1.0,
                        "candidate_top20_hit_rate": 1.0,
                        "delta_top20_hit_rate": 0.0,
                        "candidate_pass": True,
                    },
                ],
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    out_json = runs / "summary.json"
    out_csv = runs / "summary.csv"
    out_md = runs / "summary.md"
    out_para = runs / "paragraph.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_robustness_comparison_summary.py"),
            "--comparison-json",
            str(comparison),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-paragraph-md",
            str(out_para),
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["ligand_task_count"] == 2
    assert payload["all_sets_preserved"] is True
    assert payload["tasks_with_pr_regression"] == 1
    assert payload["tasks_with_pr_improvement"] == 1
    assert out_csv.exists()
    assert out_md.exists()
    assert out_para.exists()


def test_build_biorxiv_robustness_comparison_summary_multi_scenario(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    embed = runs / "biorxiv_run_comparison_2026-03-23_embed_seed_shift1_vs_current" / "summary.json"
    embed.parent.mkdir(parents=True)
    embed.write_text(
        json.dumps(
            {
                "set_summary": {
                    "set1_core_blind": {"candidate_pass": True},
                    "set2_expanded_ood": {"candidate_pass": True},
                    "set3_operational_smoke": {"candidate_pass": True},
                },
                "task_rows": [
                    {
                        "set_id": "set1_core_blind",
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "baseline_pass": True,
                        "candidate_pass": True,
                        "delta_pr_auc": 0.0,
                        "delta_ef1": 0.0,
                        "delta_top20_hit_rate": 0.0,
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    decoy = runs / "biorxiv_run_comparison_2026-03-23_decoy_seed_shift1_vs_current" / "summary.json"
    decoy.parent.mkdir(parents=True)
    decoy.write_text(
        json.dumps(
            {
                "set_summary": {
                    "set1_core_blind": {"candidate_pass": True},
                    "set2_expanded_ood": {"candidate_pass": True},
                    "set3_operational_smoke": {"candidate_pass": True},
                },
                "task_rows": [
                    {
                        "set_id": "set1_core_blind",
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "baseline_pass": True,
                        "candidate_pass": True,
                        "delta_pr_auc": -0.15,
                        "delta_ef1": 0.0,
                        "delta_top20_hit_rate": -0.05,
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    out_json = runs / "summary_multi.json"
    out_md = runs / "summary_multi.md"
    out_para = runs / "paragraph_multi.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_robustness_comparison_summary.py"),
            "--comparison-json",
            str(embed),
            "--comparison-json",
            str(decoy),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(runs / "summary_multi.csv"),
            "--out-md",
            str(out_md),
            "--out-paragraph-md",
            str(out_para),
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["scenario_count"] == 2
    assert payload["all_sets_preserved"] is True
    assert payload["pass_to_fail_task_transitions"] == 0
    assert payload["largest_pr_regression_task"] == "gpcr_core_full"
    assert payload["largest_pr_regression_scenario_id"] == "decoy_seed_shift1"
    assert "Across `2` completed robustness scenarios" in out_para.read_text(encoding="utf-8")
    assert "Robustness Battery Comparison Summary" in out_md.read_text(encoding="utf-8")
