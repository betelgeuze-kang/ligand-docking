from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_idp_kalman_feature_state_smoothing_plan(tmp_path: Path) -> None:
    out_json = tmp_path / "plan.json"
    out_md = tmp_path / "plan.md"
    doc_md = tmp_path / "doc.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_idp_kalman_feature_state_smoothing_plan.py"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--doc-md",
            str(doc_md),
        ],
        cwd=ROOT,
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["scope"] == "feature_state_smoothing_only"
    assert payload["summary"]["coordinate_correction"] is False
    assert payload["summary"]["ranking_override"] is False
    assert payload["summary"]["default_feature_mask"] == "rg_sasa_only"
    assert any(row["file"] == "tools/run_idp_3bead_evaluator.py" for row in payload["insertion_points"])
