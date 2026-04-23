from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_ablation_table(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    def write_summary(name: str, set_summary: dict, improved: int, regressed: int, changed: int) -> Path:
        path = runs / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "baseline_run_root": f"/tmp/{name}_baseline",
                    "candidate_run_root": f"/tmp/{name}_candidate",
                    "task_count": 12,
                    "tasks_with_pr_improvement": improved,
                    "tasks_with_pr_regression": regressed,
                    "profile_changed_task_count": changed,
                    "set_summary": set_summary,
                }
            ),
            encoding="utf-8",
        )
        return path

    s1 = write_summary(
        "v3v4",
        {
            "set1_core_blind": {"baseline_pass": False, "candidate_pass": False},
            "set2_expanded_ood": {"baseline_pass": False, "candidate_pass": True},
            "set3_operational_smoke": {"baseline_pass": False, "candidate_pass": True},
        },
        2,
        2,
        3,
    )
    s2 = write_summary(
        "v4v6",
        {
            "set1_core_blind": {"baseline_pass": False, "candidate_pass": True},
            "set2_expanded_ood": {"baseline_pass": True, "candidate_pass": True},
            "set3_operational_smoke": {"baseline_pass": True, "candidate_pass": True},
        },
        3,
        1,
        2,
    )
    s3 = write_summary(
        "v6v7",
        {
            "set1_core_blind": {"baseline_pass": True, "candidate_pass": True},
            "set2_expanded_ood": {"baseline_pass": True, "candidate_pass": True},
            "set3_operational_smoke": {"baseline_pass": True, "candidate_pass": True},
        },
        3,
        0,
        4,
    )

    out_json = runs / "ablation.json"
    out_csv = runs / "ablation.csv"
    out_md = runs / "ablation.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_ablation_table.py"),
            "--v3-v4-summary-json",
            str(s1),
            "--v4-v6-summary-json",
            str(s2),
            "--v6-v7-summary-json",
            str(s3),
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
    assert len(data["rows"]) == 3
    assert out_csv.exists()
    assert out_md.exists()
