from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _state_payload(
    summary_json: Path,
    pipeline_summary_json: Path,
    *,
    task_id: str,
    set_id: str,
    pr_auc: float,
    ef1: float,
    unique_auc: float,
    passed: bool,
) -> dict:
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


def test_build_gpcr_residual_mode_comparison_partial(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline"
    shadow_root = tmp_path / "shadow"
    apply_root = tmp_path / "apply"
    baseline_root.mkdir()
    shadow_root.mkdir()
    apply_root.mkdir()

    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    baseline_summary = tmp_path / "baseline_core_summary.json"
    shadow_summary = tmp_path / "shadow_core_summary.json"
    apply_summary = tmp_path / "apply_core_summary.json"
    baseline_pipeline = tmp_path / "baseline_core_pipeline.json"
    shadow_pipeline = tmp_path / "shadow_core_pipeline.json"
    apply_pipeline = tmp_path / "apply_core_pipeline.json"

    for path in (baseline_summary, shadow_summary, apply_summary):
        path.write_text("{}", encoding="utf-8")
    baseline_pipeline.write_text(json.dumps({"summary": {}}), encoding="utf-8")
    shadow_pipeline.write_text(
        json.dumps(
            {
                "summary": {
                    "residual_prototype": {
                        "enabled": True,
                        "mode": "shadow_only",
                        "status": "shadow_ready",
                        "positive_delta_count": 123,
                        "mean_delta": 0.4,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    apply_pipeline.write_text(
        json.dumps(
            {
                "summary": {
                    "residual_prototype": {
                        "enabled": True,
                        "mode": "apply",
                        "status": "apply_ready",
                        "positive_delta_count": 456,
                        "mean_delta": 0.5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    (baseline_root / "state.json").write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                **_state_payload(
                                    baseline_summary,
                                    baseline_pipeline,
                                    task_id="gpcr_core_full",
                                    set_id="set1_core_blind",
                                    pr_auc=0.50,
                                    ef1=90.0,
                                    unique_auc=0.99,
                                    passed=True,
                                )["sets"][0]["tasks"][0]
                            }
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "tasks": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (shadow_root / "state.json").write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                **_state_payload(
                                    shadow_summary,
                                    shadow_pipeline,
                                    task_id="gpcr_core_full",
                                    set_id="set1_core_blind",
                                    pr_auc=0.50,
                                    ef1=90.0,
                                    unique_auc=0.99,
                                    passed=True,
                                )["sets"][0]["tasks"][0]
                            }
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "tasks": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (apply_root / "state.json").write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                **_state_payload(
                                    apply_summary,
                                    apply_pipeline,
                                    task_id="gpcr_core_full",
                                    set_id="set1_core_blind",
                                    pr_auc=0.52,
                                    ef1=95.0,
                                    unique_auc=0.995,
                                    passed=True,
                                )["sets"][0]["tasks"][0]
                            }
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "tasks": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_mode_comparison.py"),
            "--baseline-run-root",
            str(baseline_root),
            "--shadow-run-root",
            str(shadow_root),
            "--apply-run-root",
            str(apply_root),
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
    assert payload["completed_apply_tasks"] == 1
    rows = {row["task_id"]: row for row in payload["rows"]}
    assert rows["gpcr_core_full"]["delta_pr_auc_apply_vs_baseline"] == 0.020000000000000018
    assert rows["gpcr_core_full"]["delta_ef1_apply_vs_shadow"] == 5.0
    assert rows["gpcr_core_full"]["apply_residual_positive_delta_count"] == 456
    assert rows["gpcr_chembl50_full"]["apply_complete"] is False
