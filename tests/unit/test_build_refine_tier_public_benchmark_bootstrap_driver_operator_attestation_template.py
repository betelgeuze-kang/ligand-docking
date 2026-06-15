from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template as mod
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _prefill_row(*, filled: bool = False) -> dict[str, str]:
    row = {
        "worksheet_id": "r9_bootstrap_driver_operator_review_001",
        "target_id": "3f3e",
        "pose_id": "3f3e_197",
        "work_order_id": "wo_3f3e",
        "split": "holdout",
        "metric_name": "dockq",
        "review_surface": "candidate_preview_payload_write_review",
        "metric_value_under_review": "0.733726",
        "method_under_review": "candidate_internal_ligand_pose_reference_dockq_proxy_v1",
        "expected_metric_source_artifact": "runs/candidate_dockq.json",
        "expected_metric_source_artifact_present": "False",
        "input_artifact_sha256_verified": "True",
        "operator_decision": "OPERATOR_FILL_ACCEPT_OR_REJECT",
        "metric_value_reviewed": "true",
        "method_reviewed": "true",
        "input_artifacts_reviewed": "true",
        "input_artifact_sha256s_reviewed": "true",
        "expected_metric_source_artifact_reviewed": "true",
        "payload_schema_reviewed": "true",
        "license_ok_reviewed": "OPERATOR_CONFIRM_TRUE",
        "operator_id": "OPERATOR_FILL_OPERATOR_ID",
        "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
        "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
        "operator_manual_pending_fields": "operator_decision;license_ok_reviewed;operator_id;reviewed_at_utc;approval_token",
    }
    if filled:
        row.update(
            {
                "operator_decision": "accept",
                "license_ok_reviewed": "true",
                "operator_id": "operator@example.test",
                "reviewed_at_utc": "2026-06-15T00:00:00Z",
                "approval_token": APPROVAL_TOKEN,
                "operator_manual_pending_fields": "",
            }
        )
    return row


def test_bootstrap_driver_operator_attestation_template_extracts_current_operator_only_fields() -> None:
    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template()
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_ready"
    assert summary["attestation_row_count"] == 6
    assert summary["attestation_pass_row_count"] == 0
    assert summary["attestation_blocked_row_count"] == 6
    assert summary["operator_only_total_field_count"] == 30
    assert summary["operator_only_pending_field_count"] == 30
    assert summary["machine_prefilled_field_count"] == 36
    assert summary["prefill_row_fingerprint_count"] == 6
    assert summary["approval_ready"] is False
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["first_blocked_worksheet_id"] == "r9_bootstrap_driver_operator_review_001"
    assert summary["most_common_row_blocker"] == "operator_only_fields_pending"
    assert payload["rows"][0]["prefill_row_sha256"]


def test_bootstrap_driver_operator_attestation_template_allows_filled_preview_without_writes(
    tmp_path: Path,
) -> None:
    prefill_csv = tmp_path / "prefill.csv"
    _write_csv(prefill_csv, [_prefill_row(filled=True)])

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template(
        prefill_csv=prefill_csv,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_ready"
    assert summary["attestation_row_count"] == 1
    assert summary["attestation_pass_row_count"] == 1
    assert summary["attestation_blocked_row_count"] == 0
    assert summary["operator_only_pending_field_count"] == 0
    assert summary["approval_ready"] is True
    assert summary["payload_write_allowed"] is False
    assert summary["canonical_receipt_write_allowed"] is False


def test_bootstrap_driver_operator_attestation_template_cli_writes_outputs(tmp_path: Path) -> None:
    prefill_csv = tmp_path / "prefill.csv"
    out_json = tmp_path / "attestation.json"
    out_csv = tmp_path / "attestation.csv"
    out_md = tmp_path / "attestation.md"
    _write_csv(prefill_csv, [_prefill_row(filled=False)])

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--prefill-csv",
            str(prefill_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["attestation_row_count"] == len(rows)
    assert rows[0]["attestation_id"] == "r9_bootstrap_driver_operator_attestation_001"
    assert "R9 Bootstrap Driver Operator Attestation Template" in out_md.read_text(encoding="utf-8")
