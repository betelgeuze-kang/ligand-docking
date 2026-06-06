from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_third_party_license_review_gate as mod


def _audit() -> dict:
    return {
        "summary": {
            "status": "self_hosted_license_distribution_audit_recorded",
            "hard_blocker_count": 0,
            "operator_review_item_count": 1,
            "third_party_dual_license_assets": ["jszip"],
            "external_state_mutated": False,
        }
    }


def _review_row(**overrides: str) -> dict[str, str]:
    row = {
        "package": "jszip",
        "operator_decision": "approve",
        "approval_token": "APPROVE_THIRD_PARTY_LICENSE_REVIEW",
        "chosen_license_path": "MIT",
        "reviewer_name": "Legal Reviewer",
        "reviewed_at_utc": "2026-06-06T00:00:00Z",
        "operator_note": "approved MIT path",
    }
    row.update(overrides)
    return row


def test_third_party_license_review_gate_blocks_missing_operator_intake() -> None:
    payload = mod.build_third_party_license_review_gate(
        audit_packet=_audit(),
        review_rows=[],
        review_csv_present=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_third_party_license_review_gate"
    assert summary["expected_review_asset_count"] == 1
    assert summary["missing_review_asset_count"] == 1
    assert "operator_review_csv_missing" in summary["blockers"]
    assert "missing_review_row:jszip" in summary["blockers"]
    assert summary["legal_advice_provided"] is False
    assert summary["asset_modified"] is False
    assert summary["external_state_mutated"] is False


def test_third_party_license_review_gate_ready_with_complete_operator_record() -> None:
    payload = mod.build_third_party_license_review_gate(
        audit_packet=_audit(),
        review_rows=[_review_row()],
        review_csv_present=True,
    )

    assert payload["summary"]["status"] == "third_party_license_review_gate_ready"
    assert payload["summary"]["approved_review_asset_count"] == 1
    assert payload["summary"]["blocker_count"] == 0
    assert payload["summary"]["legal_advice_provided"] is False
    assert payload["rows"][0]["review_status"] == "approved_for_operator_record"


def test_third_party_license_review_gate_blocks_bad_token_and_path() -> None:
    payload = mod.build_third_party_license_review_gate(
        audit_packet=_audit(),
        review_rows=[_review_row(approval_token="WRONG", chosen_license_path="unknown", reviewer_name="")],
        review_csv_present=True,
    )

    blockers = set(payload["summary"]["blockers"])
    assert payload["summary"]["status"] == "blocked_third_party_license_review_gate"
    assert "approval_token_mismatch" in blockers
    assert "chosen_license_path_invalid" in blockers
    assert "reviewer_name_missing" in blockers


def test_third_party_license_review_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    audit_json = tmp_path / "audit.json"
    review_csv = tmp_path / "review.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    audit_json.write_text(json.dumps(_audit()) + "\n", encoding="utf-8")
    with review_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_review_row().keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(_review_row())

    mod.main(
        [
            "--license-audit-json",
            str(audit_json),
            "--review-csv",
            str(review_csv),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "third_party_license_review_gate_ready"
    assert template_csv.read_text(encoding="utf-8").startswith("package,operator_decision,")
    assert out_csv.read_text(encoding="utf-8").startswith("row_number,package,")
    assert "Third-Party License Review Gate" in out_md.read_text(encoding="utf-8")
