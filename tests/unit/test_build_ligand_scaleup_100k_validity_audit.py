from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_ligand_scaleup_100k_validity_audit(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run_root = runs / "external_validation_blind_runs" / "external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v2r2"
    run_root.mkdir(parents=True)
    pilot_json = runs / "ligand_scaleup_100k_pilot_current.json"
    summary_json = run_root / "summary.json"
    state_json = run_root / "state.json"

    task_summary = runs / "task_summary.json"
    pipeline_summary = runs / "pipeline_summary.json"
    task_summary.write_text(json.dumps({"ok": True}), encoding="utf-8")
    pipeline_summary.write_text(json.dumps({"max_ligands": 100000}), encoding="utf-8")

    pilot_payload = {
        "scope_summary": {"ligand_stress_task_count": 1, "full_task_count_100k": 1, "smoke_task_count_unchanged": 0, "domains_touched": ["gpcr"]},
        "task_rows": [
            {
                "set_id": "set1_core_blind",
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "pilot_shape_class": "full_100k",
                "ligand_sizes_after": "100000",
            }
        ],
    }
    summary_payload = {
        "tag": "2026-03-23_scaleup_100k_pilot_v2r2",
        "status": "completed",
        "sets": [
            {
                "set_id": "set1_core_blind",
                "pass": True,
                "tasks": [
                    {
                        "task_id": "gpcr_core_full",
                        "pass": True,
                        "summary_json": str(task_summary),
                        "pipeline_summary_json": str(pipeline_summary),
                        "ligand_sizes": [100000],
                        "metrics": {"ranking_pr_auc": 0.9, "ranking_ef1": 95.0},
                    }
                ],
            }
        ],
    }
    pilot_json.write_text(json.dumps(pilot_payload), encoding="utf-8")
    summary_json.write_text(json.dumps(summary_payload), encoding="utf-8")
    state_json.write_text(json.dumps({"status": "completed"}), encoding="utf-8")

    out_json = runs / "audit.json"
    out_csv = runs / "audit.csv"
    out_md = runs / "audit.md"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_ligand_scaleup_100k_validity_audit.py"),
            "--run-root",
            str(run_root),
            "--pilot-json",
            str(pilot_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["valid_completed_test_run"] is True
    assert payload["summary"]["interpretation"] == "valid_completed_test_run"
    assert payload["summary"]["live_process_count"] == 0
    assert payload["task_rows"][0]["contract_ok"] == "yes"
    assert "valid_completed_test_run" in out_md.read_text(encoding="utf-8")
