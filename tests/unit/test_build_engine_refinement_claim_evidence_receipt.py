from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_engine_refinement_claim_evidence_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _action_board(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["blocker_id"])
        writer.writeheader()
        for blocker_id in mod.REQUIRED_BLOCKERS:
            writer.writerow({"blocker_id": blocker_id})


def test_engine_refinement_claim_evidence_receipt_blocks_default_template() -> None:
    payload = mod.build_engine_refinement_claim_evidence_receipt()
    summary = payload["summary"]

    assert summary["status"] == "blocked_engine_refinement_claim_evidence_receipt"
    assert summary["claim_promotion_evidence_receipt_ready"] is False
    assert summary["receipt_row_count"] == 6
    assert summary["required_blocker_count"] == 6
    assert summary["missing_required_blocker_count"] == 0
    assert summary["blocked_row_count"] == 6
    assert summary["first_blocked_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["first_blocked_evidence_artifact"] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary["first_blocked_expected_evidence_status"] == "refine_tier_public_benchmark_ready"
    assert summary["first_blocked_observed_evidence_status"] == "missing"
    assert summary["first_blocked_missing_true_fields"] == ["claim_grade_public_benchmark_ready"]
    assert "operator_placeholders_unfilled" in summary["first_blocked_row_blockers"]
    assert summary["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["external_state_mutated"] is False
    assert "blocked_receipt_rows_present" in summary["blockers"]
    assert all(row["row_status"] == "blocked" for row in payload["rows"])
    assert all("operator_placeholders_unfilled" in row["blockers"] for row in payload["rows"])


def test_engine_refinement_claim_evidence_receipt_passes_verified_local_evidence(tmp_path: Path) -> None:
    receipt_csv = tmp_path / "config" / "receipt.csv"
    action_board_csv = tmp_path / "runs" / "action_board.csv"
    _action_board(action_board_csv)
    rows: list[dict[str, object]] = []
    for blocker_id in mod.REQUIRED_BLOCKERS:
        expected = mod.EXPECTED_EVIDENCE[blocker_id]
        evidence_path = tmp_path / "runs" / f"{blocker_id}.json"
        evidence_payload = {
            "summary": {
                "status": expected["status"],
                **{field: True for field in expected["true_fields"]},
            }
        }
        _write_json(evidence_path, evidence_payload)
        rows.append(
            {
                "blocker_id": blocker_id,
                "evidence_artifact": evidence_path.relative_to(tmp_path).as_posix(),
                "evidence_status": expected["status"],
                "claim_ready": "true",
                "reviewer": "operator-a",
                "reviewed_at_utc": "2026-06-12T00:00:00+00:00",
                "provenance_kind": "internal_calibration_report",
                "license_ok": "true",
                "external_engine_calls": 0,
                "approval_token": mod.APPROVAL_TOKEN,
                "operator_attestation": "reviewed_for_claim_promotion",
                "notes": "unit-test evidence",
            }
        )
    _write_csv(receipt_csv, rows)

    payload = mod.build_engine_refinement_claim_evidence_receipt(
        receipt_csv=receipt_csv.relative_to(tmp_path),
        action_board_csv=action_board_csv.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "engine_refinement_claim_evidence_receipt_ready"
    assert summary["claim_promotion_evidence_receipt_ready"] is True
    assert summary["pass_row_count"] == 6
    assert summary["blocked_row_count"] == 0
    assert summary["first_blocked_blocker_id"] == ""
    assert summary["first_blocked_row_blockers"] == []
    assert summary["most_common_row_blocker"] == ""
    assert summary["evidence_status_verified_count"] == 6
    assert summary["blockers"] == []


def test_engine_refinement_claim_evidence_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert out_json.is_file()
    assert out_csv.is_file()
    assert out_md.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_engine_refinement_claim_evidence_receipt"
