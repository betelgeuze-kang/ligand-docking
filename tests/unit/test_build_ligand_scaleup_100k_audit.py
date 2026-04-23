from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_ligand_scaleup_100k_audit_marks_valid_completed_run(tmp_path: Path) -> None:
    pilot_json = tmp_path / "runs" / "ligand_scaleup_100k_pilot_current.json"
    run_root = tmp_path / "runs" / "external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v2r2"
    _write_json(
        pilot_json,
        {
            "scope_summary": {
                "ligand_stress_task_count": 2,
                "full_task_count_100k": 1,
                "smoke_task_count_unchanged": 1,
            },
            "drift_audit": {"ok": True},
            "launch_readiness": {"ready": True},
        },
    )
    _write_json(
        run_root / "summary.json",
        {
            "status": "completed",
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "pass": False,
                    "tasks": [
                        {
                            "task_id": "gpcr_core_full",
                            "domain": "gpcr",
                            "kind": "ligand_stress",
                            "pass": False,
                            "summary_json": str(tmp_path / "runs" / "gpcr_summary.json"),
                            "pipeline_summary_json": str(tmp_path / "runs" / "gpcr_pipeline_summary.json"),
                            "ligand_sizes": [100000],
                            "metrics": {"ranking_pr_auc": 0.39, "ranking_ef1": 66.67, "strict_gate_pass": True, "operational_gate_pass": False},
                        }
                    ],
                },
                {
                    "set_id": "set3_operational_smoke",
                    "pass": True,
                    "tasks": [
                        {
                            "task_id": "gpcr_smoke",
                            "domain": "gpcr",
                            "kind": "ligand_stress",
                            "pass": True,
                            "summary_json": str(tmp_path / "runs" / "gpcr_smoke_summary.json"),
                            "pipeline_summary_json": str(tmp_path / "runs" / "gpcr_smoke_pipeline_summary.json"),
                            "ligand_sizes": [64],
                            "metrics": {"ranking_pr_auc": 1.0, "ranking_ef1": 5.33, "strict_gate_pass": True, "operational_gate_pass": False},
                        }
                    ],
                },
            ],
        },
    )
    _write_json(
        run_root / "state.json",
        {
            "status": "completed",
            "sets": [],
        },
    )
    _write_json(tmp_path / "runs" / "gpcr_summary.json", {"pass": False})
    _write_json(tmp_path / "runs" / "gpcr_pipeline_summary.json", {"ok": True})
    _write_json(tmp_path / "runs" / "gpcr_smoke_summary.json", {"pass": True})
    _write_json(tmp_path / "runs" / "gpcr_smoke_pipeline_summary.json", {"ok": True})
    out_json = tmp_path / "runs" / "ligand_scaleup_100k_audit_current.json"
    out_csv = tmp_path / "runs" / "ligand_scaleup_100k_audit_current.csv"
    out_md = tmp_path / "runs" / "ligand_scaleup_100k_audit_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools" / "build_ligand_scaleup_100k_audit.py"),
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
        cwd=tmp_path,
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["valid_completed_test_run"] is True
    assert payload["summary"]["result_interpretation"] == "valid_completed_run_mixed_outcome"
    assert payload["summary"]["task_fail_count"] == 1
    assert "gpcr_core_full" in payload["summary"]["failed_task_ids"]
