from __future__ import annotations

import json
from pathlib import Path

from tools import build_protected_cleanup_payload_review as mod


def _drilldown() -> dict:
    return {
        "summary": {"status": "large_cleanup_surface_drilldown_ready"},
        "rows": [
            {
                "path": "/mnt/ligand_heavy_runs/recent_big",
                "surface_path": "/mnt/ligand_heavy_runs",
                "scope": "surface_child",
                "status": "known_payloads_protected_by_dry_run",
                "source_dry_run_status": "kept_recent_slot",
                "source_dry_run_reason": "protected by keep-recent",
                "known_payload_count": 1,
                "known_payload_size_gb": 396.794,
            },
            {
                "path": "/mnt/ligand_heavy_runs/old_small",
                "surface_path": "/mnt/ligand_heavy_runs",
                "scope": "surface_child",
                "status": "known_payloads_found",
                "source_dry_run_status": "dry_run_delete",
                "source_dry_run_reason": "would be removed",
                "known_payload_count": 1,
                "known_payload_size_gb": 6.012,
            },
        ],
    }


def test_protected_cleanup_payload_review_summarizes_protected_rows_only() -> None:
    payload = mod.build_protected_payload_review(_drilldown())
    summary = payload["summary"]

    assert summary["status"] == "protected_cleanup_payload_review_ready"
    assert summary["protected_payload_row_count"] == 1
    assert summary["protected_payload_size_gb"] == 396.794
    assert summary["large_protected_payload_row_count"] == 1
    assert summary["policy_change_required_count"] == 1
    assert summary["approval_promoted_count"] == 0
    assert summary["delete_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"][0]["approval_promoted"] is False
    assert payload["rows"][0]["policy_change_required_for_deletion"] is True


def test_protected_cleanup_payload_review_tool_writes_outputs(tmp_path: Path) -> None:
    drilldown_json = tmp_path / "drilldown.json"
    out_json = tmp_path / "protected.json"
    out_csv = tmp_path / "protected.csv"
    out_md = tmp_path / "protected.md"
    drilldown_json.write_text(json.dumps(_drilldown()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--drilldown-json",
            str(drilldown_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["protected_payload_row_count"] == 1
    assert out_csv.read_text(encoding="utf-8").startswith("path,surface_path,")
    assert "Protected Cleanup Payload Review" in out_md.read_text(encoding="utf-8")
