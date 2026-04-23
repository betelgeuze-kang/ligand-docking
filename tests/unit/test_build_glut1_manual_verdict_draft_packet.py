from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_glut1_manual_verdict_draft_packet_keeps_manual_fields_empty() -> None:
    subprocess.run(
        [sys.executable, "tools/build_glut1_manual_verdict_draft_packet.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/glut1_manual_verdict_draft_packet_current.json").read_text())
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "glut1"
    assert summary["binder_slot_count"] == 3
    assert summary["suggested_prefill_count"] == 3
    assert summary["manual_fields_committed_count"] == 0

    first = rows[0]
    assert first["candidate_name"] == "cytochalasin B"
    assert first["suggested_manual_verdict"] == "keep_review_only"
    assert first["manual_verdict_update"] == ""
    assert first["manual_confidence_update"] == ""
    assert first["manual_decision_note"] == ""
