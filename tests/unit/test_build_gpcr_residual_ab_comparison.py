from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _state_payload(summary_json: Path, pipeline_summary_json: Path, *, task_id: str, set_id: str, pr_auc: float, ef1: float, unique_auc: float, passed: bool) -> dict:
    return {
        "sets": [
            {
                "set_id": set_id,
                "tasks": [
                    {
                        "task_id": task_id,
                        "pass": passed,
                        "run_ok": passed,
                        "summary_json": str(summary_json),
                        "pipeline_summary_json": str(pipeline_summary_json),
                        "metrics": {
                            "ranking_pr_auc": pr_auc,
                            "ranking_ef1": ef1,
                            "ranking_unique_auc": unique_auc,
                            "operational_gate_pass": passed,
                            "strict_gate_pass": True,
                        },
                    }
                ],
            }
        ]
    }


def test_build_gpcr_residual_ab_comparison_partial(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline"
    candidate_root = tmp_path / "candidate"
    baseline_root.mkdir()
    candidate_root.mkdir()
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    baseline_summary = tmp_path / "baseline_gpcr_core_summary.json"
    baseline_pipeline = tmp_path / "baseline_gpcr_core_pipeline.json"
    candidate_summary = tmp_path / "candidate_gpcr_core_summary.json"
    candidate_pipeline = tmp_path / "candidate_gpcr_core_pipeline.json"

    baseline_summary.write_text("{}", encoding="utf-8")
    candidate_summary.write_text("{}", encoding="utf-8")
    baseline_pipeline.write_text(json.dumps({"summary": {}}), encoding="utf-8")
    candidate_pipeline.write_text(
        json.dumps(
            {
                "summary": {
                    "residual_prototype": {
                        "enabled": True,
                        "mode": "shadow_only",
                        "status": "shadow_ready",
                        "positive_delta_count": 123,
                        "yellow_band_count": 45,
                        "mean_delta": 0.4,
                        "max_delta": 1.5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    (baseline_root / "state.json").write_text(
        json.dumps(
            _state_payload(
                baseline_summary,
                baseline_pipeline,
                task_id="gpcr_core_full",
                set_id="set1_core_blind",
                pr_auc=0.50,
                ef1=90.0,
                unique_auc=0.99,
                passed=True,
            )
        ),
        encoding="utf-8",
    )
    (candidate_root / "state.json").write_text(
        json.dumps(
            _state_payload(
                candidate_summary,
                candidate_pipeline,
                task_id="gpcr_core_full",
                set_id="set1_core_blind",
                pr_auc=0.48,
                ef1=88.0,
                unique_auc=0.98,
                passed=False,
            )
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_ab_comparison.py"),
            "--baseline-run-root",
            str(baseline_root),
            "--candidate-run-root",
            str(candidate_root),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["completed_candidate_tasks"] == 1
    rows = {row["task_id"]: row for row in payload["rows"]}
    assert rows["gpcr_core_full"]["delta_pr_auc"] == -0.020000000000000018
    assert rows["gpcr_core_full"]["residual_positive_delta_count"] == 123
    assert rows["gpcr_chembl50_full"]["candidate_complete"] is False
