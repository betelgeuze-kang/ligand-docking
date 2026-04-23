from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_gpcr_residual_apply_decision_no_go(tmp_path: Path) -> None:
    comparison_json = tmp_path / "comparison.json"
    out_json = tmp_path / "decision.json"
    out_md = tmp_path / "decision.md"
    comparison_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "task_id": "gpcr_core_full",
                        "baseline_pass": True,
                        "apply_pass": True,
                        "delta_pr_auc_apply_vs_baseline": -0.05,
                        "delta_ef1_apply_vs_baseline": 0.0,
                        "apply_residual_mean_delta": 0.47,
                    },
                    {
                        "task_id": "gpcr_chembl50_full",
                        "baseline_pass": True,
                        "apply_pass": True,
                        "delta_pr_auc_apply_vs_baseline": -0.01,
                        "delta_ef1_apply_vs_baseline": 0.0,
                        "apply_residual_mean_delta": 0.43,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_apply_decision.py"),
            "--comparison-json",
            str(comparison_json),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "no_go_for_100k_router"
    assert payload["pr_regressions"] == 2
    assert payload["ef1_improvements"] == 0
