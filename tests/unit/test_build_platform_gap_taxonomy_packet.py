from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_platform_gap_taxonomy_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_platform_gap_taxonomy_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ligand_scaleup_claim_safe": False,
                "ligand_scaleup_claim_safe_status": "regression_guardrail_failed",
                "ligand_scaleup_commercialization_ready_suite_count": 0,
                "ligand_scaleup_suite_count": 3,
                "ligand_scaleup_next_required_step": "rerun 100k comparison",
            }
        },
        {
            "rows": [
                {"family": "ca2", "source_linked_count": 6, "ready_like_count": 5, "next_required_step": "keep CA2 review-only"},
                {"family": "pxr", "source_linked_count": 6, "ready_like_count": 8, "next_required_step": "defer PXR rows"},
                {"family": "aqp1", "ready_like_count": 0, "next_required_step": "keep AQP1 kcal blank"},
            ]
        },
        {
            "summary": {
                "placeholder_driven_rows": 6,
                "evidence_blocked_placeholder_rows": 6,
                "packet_artifact": "runs/transporter_placeholder_burndown_queue_current.md",
                "next_required_step": "keep transporter negative rows parked",
            }
        },
        {"summary": {"top_priority_status": "parked"}},
        {
            "summary": {
                "packet_artifact": "runs/keep_green_regression_trend_packet_current.md",
                "all_current_green": True,
                "repeated_history_ready_lane_count": 1,
                "lane_count": 4,
                "insufficient_history_lane_count": 3,
                "next_required_step": "rerun keep-green lanes",
            }
        },
    )

    summary = payload["summary"]
    rows = {row["gap_id"]: row for row in payload["rows"]}
    assert summary["packet_ready"] is True
    assert summary["platform_gap_count"] == 6
    assert summary["current_delivery_blocker_count"] == 0
    assert summary["transporter_specific_split_resolved"] is True
    assert summary["top_expansion_gap_id"] == "keep_green_repeated_history"
    assert summary["ligand_scaleup_claim_safe_status"] == "regression_guardrail_failed"
    assert rows["ligand_scaleup_regression_guardrail"]["primary_value"] == "0/3"
    assert rows["ligand_scaleup_suite_completion"]["expansion_blocker_count"] == 0
    assert rows["transporter_negative_placeholder_rows"]["expansion_blocker_count"] == 6
    assert rows["ca2_pxr_review_only_evidence_policy"]["expansion_blocker_count"] == 13


def test_build_platform_gap_taxonomy_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "platform_gap_taxonomy_packet.json"
    out_csv = tmp_path / "platform_gap_taxonomy_packet.csv"
    out_md = tmp_path / "platform_gap_taxonomy_packet.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_platform_gap_taxonomy_packet.py",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_artifact"] == "runs/platform_gap_taxonomy_packet_current.md"
    assert payload["summary"]["platform_gap_count"] == 6
    assert payload["summary"]["non_transporter_gap_count"] >= 4
    assert out_csv.exists()
    assert out_md.exists()
