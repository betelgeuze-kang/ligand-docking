from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_platform_operator_quickstart_packet_outputs_expected_lanes() -> None:
    subprocess.run(
        [sys.executable, "tools/build_platform_operator_quickstart_packet.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/platform_operator_quickstart_packet_current.json").read_text())
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["run_now_count"] == 4
    assert summary["prepare_next_count"] == 2
    assert summary["manual_review_only_count"] == 1
    assert summary["highest_gap_family"] == "transporter"

    row_map = {row["family"]: row for row in rows}
    assert row_map["gpcr"]["lane"] == "run_now"
    assert row_map["idp"]["scope_now"] == "one_wider_shadow_safe_lane_only"
    assert row_map["non_kinase_enzyme_ca2"]["lane"] == "prepare_next"
    assert row_map["transporter"]["lane"] == "manual_review_only"
