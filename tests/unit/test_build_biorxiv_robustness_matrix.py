from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_robustness_matrix(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    run_summary = runs / "summary.json"
    run_summary.write_text(
        json.dumps(
            {
                "sets": {
                    "set1_core_blind": {"pass": True},
                    "set2_expanded_ood": {"pass": True},
                    "set3_operational_smoke": {"pass": True},
                }
            }
        ),
        encoding="utf-8",
    )
    baseline = runs / "baseline.json"
    baseline.write_text(
        json.dumps({"profile_changed_task_count": 4, "tasks_with_pr_improvement": 3, "tasks_with_pr_regression": 0}),
        encoding="utf-8",
    )
    seed_shift = runs / "seed_shift.json"
    seed_shift.write_text(
        json.dumps(
            {
                "candidate_status": "completed",
                "tasks_with_pr_improvement": 1,
                "tasks_with_pr_regression": 3,
                "set_summary": {
                    "set1_core_blind": {"candidate_pass": True},
                    "set2_expanded_ood": {"candidate_pass": True},
                    "set3_operational_smoke": {"candidate_pass": True},
                },
            }
        ),
        encoding="utf-8",
    )
    temporal = runs / "temporal.json"
    temporal.write_text(
        json.dumps({"overall_item_ready_count": 202, "overall_dataset_ready_count": 4}),
        encoding="utf-8",
    )
    audit = runs / "audit.json"
    audit.write_text(json.dumps({"pass": True, "failure_count": 0}), encoding="utf-8")
    ablation = runs / "ablation.json"
    ablation.write_text(json.dumps({"rows": [{"x": 1}, {"x": 2}, {"x": 3}]}), encoding="utf-8")

    out_json = runs / "robustness.json"
    out_csv = runs / "robustness.csv"
    out_md = runs / "robustness.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_robustness_matrix.py"),
            "--run-summary-json",
            str(run_summary),
            "--baseline-gauntlet-json",
            str(baseline),
            "--seed-shift-comparison-json",
            str(seed_shift),
            "--temporal-baseline-json",
            str(temporal),
            "--audit-json",
            str(audit),
            "--ablation-json",
            str(ablation),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(data["rows"]) >= 6
    assert out_csv.exists()
    assert out_md.exists()
