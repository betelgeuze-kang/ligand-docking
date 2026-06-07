from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_performance_threshold_policy as mod


def test_build_cameo_performance_threshold_policy_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "policy.json"
    out_csv = tmp_path / "policy.csv"
    out_md = tmp_path / "policy.md"

    mod.main(
        [
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "cameo_performance_threshold_policy_ready"
    assert payload["summary"]["threshold_policy_ready"] is True
    assert payload["thresholds"]["min_model1_lddt"] == 0.70
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "CAMEO Performance Threshold Policy" in out_md.read_text(encoding="utf-8")
