from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_scope_breadth_evidence_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _scope_checklist(path: Path) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "product_scope_breadth_closure_checklist_ready",
                "blocker_class_counts": {blocker: 1 for blocker in mod.REQUIRED_SCOPE_BLOCKERS},
                "scope_breadth_ready": False,
            }
        },
    )


def test_product_scope_breadth_evidence_receipt_blocks_default_template() -> None:
    payload = mod.build_product_scope_breadth_evidence_receipt()
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_scope_breadth_evidence_receipt"
    assert summary["full_scope_evidence_receipt_ready"] is False
    assert summary["receipt_row_count"] == 6
    assert summary["required_scope_blocker_count"] == 6
    assert summary["missing_required_scope_blocker_count"] == 0
    assert summary["blocked_row_count"] == 6
    assert summary["external_state_mutated"] is False
    assert "blocked_receipt_rows_present" in summary["blockers"]
    assert all(row["row_status"] == "blocked" for row in payload["rows"])
    assert all("operator_placeholders_unfilled" in row["blockers"] for row in payload["rows"])


def test_product_scope_breadth_evidence_receipt_passes_verified_local_evidence(tmp_path: Path) -> None:
    receipt_csv = tmp_path / "config" / "receipt.csv"
    scope_checklist_json = tmp_path / "runs" / "scope_checklist.json"
    _scope_checklist(scope_checklist_json)
    rows: list[dict[str, object]] = []
    for scope_blocker_id in mod.REQUIRED_SCOPE_BLOCKERS:
        expected = mod.EXPECTED_EVIDENCE[scope_blocker_id]
        evidence_path = tmp_path / "runs" / f"{scope_blocker_id}.json"
        evidence_payload = {
            "summary": {
                "status": expected["status"],
                **{field: True for field in expected["true_fields"]},
            }
        }
        _write_json(evidence_path, evidence_payload)
        rows.append(
            {
                "scope_blocker_id": scope_blocker_id,
                "evidence_artifact": evidence_path.relative_to(tmp_path).as_posix(),
                "evidence_status": expected["status"],
                "claim_ready": "true",
                "reviewer": "operator-a",
                "reviewed_at_utc": "2026-06-12T00:00:00+00:00",
                "provenance_kind": "operator_curated_public",
                "license_ok": "true",
                "external_state_mutated": "false",
                "approval_token": mod.APPROVAL_TOKEN,
                "operator_attestation": "reviewed_for_scope_promotion",
                "notes": "unit-test evidence",
            }
        )
    _write_csv(receipt_csv, rows)

    payload = mod.build_product_scope_breadth_evidence_receipt(
        receipt_csv=receipt_csv.relative_to(tmp_path),
        scope_checklist_json=scope_checklist_json.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_scope_breadth_evidence_receipt_ready"
    assert summary["full_scope_evidence_receipt_ready"] is True
    assert summary["pass_row_count"] == 6
    assert summary["blocked_row_count"] == 0
    assert summary["evidence_status_verified_count"] == 6
    assert summary["blockers"] == []


def test_product_scope_breadth_evidence_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert out_json.is_file()
    assert out_csv.is_file()
    assert out_md.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_product_scope_breadth_evidence_receipt"
