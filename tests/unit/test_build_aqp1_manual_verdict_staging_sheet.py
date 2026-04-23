from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_manual_verdict_staging_sheet() -> None:
    subprocess.run(
        [sys.executable, "tools/build_aqp1_manual_verdict_staging_sheet.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/aqp1_manual_verdict_staging_sheet_current.json").read_text())
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["target_id"] == "AQP1"
    assert summary["row_count"] == 3
    assert summary["ready_for_manual_fill_count"] == 3
    assert summary["manual_fields_committed_count"] == 0

    first = rows[0]
    assert first["candidate_name"] == "bacopaside II"
    assert first["staged_manual_verdict"] == "keep_review_only"
    assert first["staged_manual_confidence_update"] == "medium"
    assert first["promotion_blocker"] == "no_local_aqp1_binder_evidence_curated"
    assert first["manual_verdict_update"] == ""
    assert first["manual_confidence_update"] == ""
    assert first["manual_decision_note"] == ""
