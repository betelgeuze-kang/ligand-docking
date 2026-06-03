from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_protected_cleanup_policy_decision_gate as mod


def _review() -> dict:
    return {
        "summary": {
            "status": "protected_cleanup_payload_review_ready",
            "protected_payload_row_count": 2,
            "protected_payload_size_gb": 396.794,
        },
        "rows": [
            {
                "path": "/mnt/ligand_heavy_runs/recent_big",
                "surface_path": "/mnt/ligand_heavy_runs",
                "source_dry_run_status": "kept_recent_slot",
                "source_dry_run_reason": "protected by keep-recent",
                "known_payload_size_gb": 396.794,
                "current_policy_action": "keep_protected",
            },
            {
                "path": "/mnt/ligand_heavy_runs/recent_small",
                "surface_path": "/mnt/ligand_heavy_runs",
                "source_dry_run_status": "kept_recent_slot",
                "source_dry_run_reason": "protected by keep-recent",
                "known_payload_size_gb": 0,
                "current_policy_action": "keep_protected",
            },
        ],
    }


def _decision(path: str, decision: str, token: str = "") -> dict[str, str]:
    return {
        "path": path,
        "operator_policy_decision": decision,
        "operator_approval_token": token,
    }


def _deep_review() -> dict:
    return {
        "summary": {
            "status": "protected_ligand_heavy_payload_deep_review_ready",
            "known_payload_child_count": 2,
            "known_payload_child_size_gb": 396.794,
            "preservation_sibling_count": 2,
            "policy_change_required_for_deletion_count": 2,
        },
        "rows": [
            {
                "protected_path": "/mnt/ligand_heavy_runs/recent_big",
                "child_path": "/mnt/ligand_heavy_runs/recent_big/stage2_trajectory_frames",
                "child_role": "known_payload_child",
                "size_gb": 396.794,
            },
            {
                "protected_path": "/mnt/ligand_heavy_runs/recent_big",
                "child_path": "/mnt/ligand_heavy_runs/recent_big/stage3_delivery",
                "child_role": "preservation_sibling",
                "size_gb": 0,
            },
            {
                "protected_path": "/mnt/ligand_heavy_runs/recent_small",
                "child_path": "/mnt/ligand_heavy_runs/recent_small/stage2_trajectory_frames",
                "child_role": "known_payload_child",
                "size_gb": 0,
            },
            {
                "protected_path": "/mnt/ligand_heavy_runs/recent_small",
                "child_path": "/mnt/ligand_heavy_runs/recent_small/stage3_delivery",
                "child_role": "preservation_sibling",
                "size_gb": 0,
            },
        ],
    }


def test_protected_cleanup_policy_decision_gate_blocks_missing_policy_csv() -> None:
    payload = mod.build_protected_cleanup_policy_decision_gate(
        protected_review_packet=_review(),
        operator_policy_rows=[],
        operator_policy_csv_present=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_protected_cleanup_policy_decision_gate"
    assert summary["operator_policy_csv_present"] is False
    assert summary["awaiting_policy_decision_row_count"] == 2
    assert summary["policy_resolved"] is False
    assert "operator_policy_csv_missing" in summary["blockers"]
    assert "operator_policy_decision_missing" in summary["blockers"]
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_protected_cleanup_policy_decision_gate_resolves_explicit_keep_policy() -> None:
    payload = mod.build_protected_cleanup_policy_decision_gate(
        protected_review_packet=_review(),
        operator_policy_rows=[
            _decision("/mnt/ligand_heavy_runs/recent_big", "keep_protected"),
            _decision("/mnt/ligand_heavy_runs/recent_small", "keep_protected"),
        ],
        operator_policy_csv_present=True,
    )

    assert payload["summary"]["status"] == "protected_cleanup_policy_decision_gate_ready"
    assert payload["summary"]["policy_resolved"] is True
    assert payload["summary"]["resolved_keep_protected_row_count"] == 2
    assert payload["summary"]["blocker_count"] == 0
    assert all(row["policy_gate_status"] == "resolved_keep_protected" for row in payload["rows"])
    assert all(row["approval_promoted"] is False for row in payload["rows"])


def test_protected_cleanup_policy_decision_gate_resolves_empty_refreshed_review() -> None:
    payload = mod.build_protected_cleanup_policy_decision_gate(
        protected_review_packet={
            "summary": {
                "status": "protected_cleanup_payload_review_ready",
                "protected_payload_row_count": 0,
                "protected_payload_size_gb": 0,
            },
            "rows": [],
        },
        operator_policy_rows=[],
        operator_policy_csv_present=True,
    )

    assert payload["summary"]["status"] == "protected_cleanup_policy_decision_gate_ready"
    assert payload["summary"]["policy_resolved"] is True
    assert payload["summary"]["protected_payload_row_count"] == 0
    assert payload["summary"]["blocker_count"] == 0
    assert payload["rows"] == []


def test_protected_cleanup_policy_decision_gate_adds_ligand_heavy_child_context() -> None:
    payload = mod.build_protected_cleanup_policy_decision_gate(
        protected_review_packet=_review(),
        protected_ligand_heavy_deep_review_packet=_deep_review(),
        operator_policy_rows=[],
        operator_policy_csv_present=False,
    )
    summary = payload["summary"]
    big = next(row for row in payload["rows"] if row["path"] == "/mnt/ligand_heavy_runs/recent_big")

    assert summary["protected_ligand_heavy_deep_review_status"] == "protected_ligand_heavy_payload_deep_review_ready"
    assert summary["known_payload_child_count"] == 2
    assert summary["known_payload_child_size_gb"] == 396.794
    assert summary["preservation_sibling_count"] == 2
    assert summary["policy_change_required_for_deletion_count"] == 2
    assert big["known_payload_child_count"] == 1
    assert big["known_payload_child_size_gb"] == 396.794
    assert big["preservation_sibling_count"] == 1
    assert big["approval_promoted"] is False
    assert big["delete_executed"] is False


def test_protected_cleanup_policy_decision_gate_keeps_policy_change_request_blocked() -> None:
    payload = mod.build_protected_cleanup_policy_decision_gate(
        protected_review_packet=_review(),
        operator_policy_rows=[
            _decision("/mnt/ligand_heavy_runs/recent_big", "request_policy_change"),
            _decision("/mnt/ligand_heavy_runs/recent_small", "keep_protected"),
        ],
        operator_policy_csv_present=True,
    )

    assert payload["summary"]["status"] == "blocked_protected_cleanup_policy_decision_gate"
    assert payload["summary"]["policy_change_requested_row_count"] == 1
    assert payload["summary"]["policy_resolved"] is False
    assert any(row["policy_gate_status"] == "policy_change_requested" for row in payload["rows"])


def test_protected_cleanup_policy_decision_gate_blocks_approval_token_attempt() -> None:
    payload = mod.build_protected_cleanup_policy_decision_gate(
        protected_review_packet=_review(),
        operator_policy_rows=[_decision("/mnt/ligand_heavy_runs/recent_big", "keep_protected", "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS")],
        operator_policy_csv_present=True,
    )

    assert payload["summary"]["status"] == "blocked_protected_cleanup_policy_decision_gate"
    assert "approval_token_not_allowed_for_policy_decision" in payload["summary"]["blockers"]
    row = next(row for row in payload["rows"] if row["path"] == "/mnt/ligand_heavy_runs/recent_big")
    assert row["policy_gate_status"] == "blocked_approval_token_attempted"
    assert row["delete_executed"] is False


def test_protected_cleanup_policy_decision_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    review_json = tmp_path / "review.json"
    deep_review_json = tmp_path / "deep_review.json"
    policy_csv = tmp_path / "policy.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    review_json.write_text(json.dumps(_review()) + "\n", encoding="utf-8")
    deep_review_json.write_text(json.dumps(_deep_review()) + "\n", encoding="utf-8")
    with policy_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "operator_policy_decision"], lineterminator="\n")
        writer.writeheader()
        writer.writerow({"path": "/mnt/ligand_heavy_runs/recent_big", "operator_policy_decision": "keep_protected"})
        writer.writerow({"path": "/mnt/ligand_heavy_runs/recent_small", "operator_policy_decision": "keep_protected"})

    mod.main(
        [
            "--protected-review-json",
            str(review_json),
            "--protected-ligand-heavy-deep-review-json",
            str(deep_review_json),
            "--operator-policy-csv",
            str(policy_csv),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "protected_cleanup_policy_decision_gate_ready"
    assert template_csv.read_text(encoding="utf-8").startswith("path,known_payload_size_gb,")
    assert "known_payload_child_size_gb" in template_csv.read_text(encoding="utf-8")
    assert "operator_approval_token" not in template_csv.read_text(encoding="utf-8").splitlines()[0]
    assert out_csv.read_text(encoding="utf-8").startswith("path,surface_path,")
    assert "Protected Cleanup Policy Decision Gate" in out_md.read_text(encoding="utf-8")
