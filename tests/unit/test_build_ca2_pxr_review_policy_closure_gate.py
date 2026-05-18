from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_ca2_pxr_review_policy_closure_gate as mod

ROOT = Path(__file__).resolve().parents[2]


def test_build_payload_closes_confirmed_review_only_policy_without_promotion() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "validation_error_count": 0,
                "pending_capture_count": 0,
                "confirmed_commit_count": 5,
                "review_only_conflict_or_gap_only": True,
                "authoritative_negative_closure_allowed": False,
            }
        },
        {
            "summary": {
                "commit_row_count": 5,
                "confirmed_manual_commit_count": 5,
                "pending_manual_commit_count": 0,
                "confirm_now_row_count": 5,
                "binder_gap_count": 0,
                "closure_mode": "review_only_conflict_closure",
            }
        },
        {
            "summary": {
                "validation_error_count": 0,
                "pending_capture_count": 0,
                "manual_commit_override_count": 6,
            }
        },
        {
            "summary": {
                "commit_row_count": 6,
                "confirmed_manual_commit_count": 6,
                "pending_manual_commit_count": 0,
                "review_only_row_count": 3,
                "defer_row_count": 3,
                "binder_gap_count": 0,
                "ready_for_apply_row_count": 8,
            }
        },
    )

    summary = payload["summary"]
    rows = {row["family"]: row for row in payload["rows"]}
    assert summary["review_only_policy_closure_allowed"] is True
    assert summary["families_closed_count"] == 2
    assert summary["review_only_policy_locked_row_count"] == 13
    assert summary["promotion_allowed_count"] == 0
    assert rows["ca2"]["promotion_allowed"] is False
    assert rows["pxr"]["policy_gate_status"] == "review_only_policy_closed"


def test_build_payload_keeps_gate_open_when_manual_commit_is_pending() -> None:
    payload = mod.build_payload(
        {"summary": {"validation_error_count": 0, "pending_capture_count": 0, "review_only_conflict_or_gap_only": True}},
        {"summary": {"commit_row_count": 5, "confirmed_manual_commit_count": 4, "pending_manual_commit_count": 1}},
        {"summary": {"validation_error_count": 0, "pending_capture_count": 0}},
        {"summary": {"commit_row_count": 6, "confirmed_manual_commit_count": 6, "review_only_row_count": 3, "defer_row_count": 3}},
    )

    assert payload["summary"]["review_only_policy_closure_allowed"] is False
    assert payload["summary"]["unresolved_policy_family_count"] == 1


def test_cli_writes_gate(tmp_path: Path) -> None:
    ca2_capture = tmp_path / "ca2_capture.json"
    ca2_commit = tmp_path / "ca2_commit.json"
    pxr_capture = tmp_path / "pxr_capture.json"
    pxr_commit = tmp_path / "pxr_commit.json"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    ca2_capture.write_text(json.dumps({"summary": {"validation_error_count": 0, "pending_capture_count": 0, "review_only_conflict_or_gap_only": True}}), encoding="utf-8")
    ca2_commit.write_text(json.dumps({"summary": {"commit_row_count": 1, "confirmed_manual_commit_count": 1}}), encoding="utf-8")
    pxr_capture.write_text(json.dumps({"summary": {"validation_error_count": 0, "pending_capture_count": 0}}), encoding="utf-8")
    pxr_commit.write_text(json.dumps({"summary": {"commit_row_count": 1, "confirmed_manual_commit_count": 1, "review_only_row_count": 1}}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_ca2_pxr_review_policy_closure_gate.py",
            "--ca2-capture-json",
            str(ca2_capture),
            "--ca2-commit-json",
            str(ca2_commit),
            "--pxr-capture-json",
            str(pxr_capture),
            "--pxr-commit-json",
            str(pxr_commit),
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
    assert payload["summary"]["packet_artifact"] == "runs/ca2_pxr_review_policy_closure_gate_current.md"
    assert out_csv.exists()
    assert out_md.exists()
