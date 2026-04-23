from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_cross_family_locked_decoy_shadow_decision(tmp_path: Path) -> None:
    comparison_json = tmp_path / "comparison.json"
    out_json = tmp_path / "decision.json"
    out_csv = tmp_path / "decision.csv"
    out_md = tmp_path / "decision.md"
    comparison_json.write_text(
        json.dumps(
            {
                "comparison_ready": True,
                "candidate_fail_count": 0,
                "live_process_count": 0,
                "family_rows": [
                    {"family": "ion_channel", "task_count": 2, "candidate_fail_count": 0, "max_abs_delta_pr_auc": 0.0012},
                    {"family": "kinase", "task_count": 2, "candidate_fail_count": 0, "max_abs_delta_pr_auc": 0.0},
                ],
                "task_rows": [
                    {"task_id": "ion_trpv1_chembl20_full"},
                    {"task_id": "kinase_core_full"},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_cross_family_locked_decoy_shadow_decision.py"),
            "--comparison-json",
            str(comparison_json),
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
    assert payload["summary"]["decision"] == "keep_shadow_noop_contract_for_ion_kinase"
    assert payload["summary"]["max_abs_delta_pr_auc"] == 0.0012
