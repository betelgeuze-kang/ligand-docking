from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_ligand_scaleup_100k_test_audit() -> None:
    out_json = ROOT / "runs" / "ligand_scaleup_100k_test_audit_current.json"
    out_csv = ROOT / "runs" / "ligand_scaleup_100k_test_audit_current.csv"
    out_md = ROOT / "runs" / "ligand_scaleup_100k_test_audit_current.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/build_ligand_scaleup_100k_test_audit.py"),
            "--out-json", str(out_json),
            "--out-csv", str(out_csv),
            "--out-md", str(out_md),
        ],
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["run_completed"] is True
    assert payload["summary"]["contract_task_count"] == 9
    assert payload["summary"]["full_task_count_100k"] == 6
    assert payload["summary"]["smoke_task_count_64"] == 3
    assert payload["summary"]["full_task_hard_decoy_100k_count"] == 6
    assert payload["summary"]["valid_completed_test_run"] is True
    assert payload["summary"]["contract_fail_count"] == 1
