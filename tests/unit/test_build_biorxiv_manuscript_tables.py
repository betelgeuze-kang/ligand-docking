from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_manuscript_tables(tmp_path: Path) -> None:
    run_root = tmp_path / "external_validation_blind_runs_2026-03-22_demo"
    set_dir = run_root / "set1_core_blind"
    set_dir.mkdir(parents=True)
    (run_root / "summary.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    manifest = {
        "set_id": "set1_core_blind",
        "claim_role": "primary",
        "pass": True,
        "tasks": [
            {
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "pass": True,
                "raw_pass": True,
                "profile_json": "/tmp/profile.json",
                "metrics": {
                    "ranking_unique_auc": 1.0,
                    "ranking_pr_auc": 0.9,
                    "ranking_ef1": 10.0,
                    "ranking_bedroc": 1.0,
                    "operational_gate_pass": True,
                    "strict_gate_pass": True,
                    "ranking_pass": True,
                    "integrity_pass": True,
                },
                "acceptance_note": "",
            }
        ],
    }
    (set_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out_root = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_biorxiv_manuscript_tables.py"),
            "--run-root",
            str(run_root),
            "--out-root",
            str(out_root),
            "--label",
            "test",
        ],
        check=True,
    )
    set_csv = out_root / "biorxiv_external_validation_set_table_test.csv"
    task_csv = out_root / "biorxiv_external_validation_task_table_test.csv"
    main_csv = out_root / "biorxiv_external_validation_main_table_test.csv"
    supp_csv = out_root / "biorxiv_external_validation_supplementary_task_table_test.csv"
    summary_json = out_root / "biorxiv_external_validation_manuscript_tables_test.json"
    assert set_csv.exists()
    assert task_csv.exists()
    assert main_csv.exists()
    assert supp_csv.exists()
    assert summary_json.exists()
    assert "set1_core_blind" in set_csv.read_text(encoding="utf-8")
    assert "gpcr_core_full" in task_csv.read_text(encoding="utf-8")
    assert "gpcr" in main_csv.read_text(encoding="utf-8")
