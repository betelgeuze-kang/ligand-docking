from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_platform_packet_index_outputs_expected_navigation() -> None:
    subprocess.run(
        [sys.executable, "tools/build_family_packet_catalog.py"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/build_platform_packet_index.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((ROOT / "runs/platform_packet_index_current.json").read_text())
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["packet_count"] == 11
    assert summary["core_commercial_lane_score"] == 82.5
    assert summary["highest_gap_family"] == "none_tracked_commercialization_gap"
    assert summary["manual_review_count"] == 1
    assert summary["manual_review_target_count"] == 2
    assert summary["partial_commit_confirm_now_count"] == 3
    assert summary["transporter_manual_review_seed_row_count"] == 6
    assert summary["idp_commercial_pretest_target_count"] == 7
    assert summary["transporter_manual_review_binder_pending_count"] == 0
    assert summary["operator_evidence_closure_console_row_count"] == 20
    assert summary["family_packet_count"] == 27
    assert summary["family_quicklink_row_count"] == 8

    row_map = {row["packet_key"]: row for row in rows}
    assert row_map["platform_operator_quickstart"]["artifact_path"] == "runs/platform_operator_quickstart_packet_current.md"
    assert row_map["family_packet_catalog"]["artifact_path"] == "runs/family_packet_catalog_current.md"
    assert row_map["family_operator_quicklink_board"]["artifact_path"] == "runs/family_operator_quicklink_board_current.md"
    assert row_map["partial_authoritative_commit_launchboard"]["artifact_path"] == "runs/partial_authoritative_commit_launchboard_current.md"
    assert row_map["partial_authoritative_commit_launchboard"]["primary_signal"] == "confirm_now=3"
    assert row_map["transporter_manual_review_quickstart"]["artifact_path"] == "runs/transporter_manual_review_quickstart_packet_current.md"
    assert row_map["transporter_manual_review_quickstart"]["primary_signal"] == "seed_rows=6"
    assert row_map["idp_commercial_pretest"]["artifact_path"] == "runs/idp_commercial_pretest_decision_current.md"
    assert row_map["idp_commercial_pretest"]["packet_label"] == "IDP Commercial Pretest Decision"
    assert row_map["idp_commercial_pretest"]["primary_signal"] == "subset_safe_now=yes"
    assert row_map["idp_commercial_pretest"]["secondary_signal"] == "pretest_ready=core:4 watch:3"
    assert row_map["operator_evidence_closure_console"]["artifact_path"] == "runs/operator_evidence_closure_console_current.md"
    assert row_map["operator_evidence_closure_console"]["primary_signal"] == "console_rows=20"
    assert row_map["commercial_core_preservation"]["artifact_path"] == "runs/commercial_core_preservation_packet_current.md"
    assert row_map["execution_handoff_dashboard"]["primary_signal"] == "run_now=4"
    assert row_map["commercialization_gap_burndown"]["secondary_signal"].startswith("blocked=")
    assert row_map["family_readiness_heatmap"]["primary_signal"] == "run_now=4"
