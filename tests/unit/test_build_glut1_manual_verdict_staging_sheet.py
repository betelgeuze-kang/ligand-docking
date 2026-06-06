from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_glut1_manual_verdict_staging_sheet() -> None:
    subprocess.run(
        [sys.executable, "tools/product/build_glut1_manual_verdict_staging_sheet.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/glut1_manual_verdict_staging_sheet_current.json").read_text())
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["target_id"] == "GLUT1"
    assert summary["row_count"] == 3
    assert summary["ready_for_manual_fill_count"] == 3
    assert summary["manual_fields_committed_count"] == 0

    first = rows[0]
    assert first["candidate_name"] == "cytochalasin B"
    assert first["staged_manual_verdict"] == "keep_review_only"
    assert first["staged_manual_confidence_update"] == "strong_structural"
    assert first["promotion_blocker"] == "no_local_glut1_binder_evidence_curated"
    assert first["manual_verdict_update"] == ""
    assert first["manual_confidence_update"] == ""
    assert first["manual_decision_note"] == ""
