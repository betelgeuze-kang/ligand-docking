from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template as mod
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


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


def _worksheet_row() -> dict[str, str]:
    return {
        "worksheet_id": "r9_bootstrap_driver_operator_review_001",
        "target_id": "3f3e",
        "pose_id": "3f3e_197",
        "work_order_id": "wo_3f3e",
        "split": "holdout",
        "metric_name": "dockq",
        "review_surface": "candidate_preview_payload_write_review",
        "operator_decision": "OPERATOR_FILL_ACCEPT_OR_REJECT",
        "metric_value_reviewed": "OPERATOR_CONFIRM_TRUE",
        "method_reviewed": "OPERATOR_CONFIRM_TRUE",
        "input_artifacts_reviewed": "OPERATOR_CONFIRM_TRUE",
        "input_artifact_sha256s_reviewed": "OPERATOR_CONFIRM_TRUE",
        "expected_metric_source_artifact_reviewed": "OPERATOR_CONFIRM_TRUE",
        "payload_schema_reviewed": "OPERATOR_CONFIRM_TRUE",
        "license_ok_reviewed": "OPERATOR_CONFIRM_TRUE",
        "operator_id": "OPERATOR_FILL_OPERATOR_ID",
        "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
        "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
        "approval_token_required": APPROVAL_TOKEN,
        "operator_manual_pending_field_count": "11",
        "operator_manual_pending_fields": (
            "operator_decision;metric_value_reviewed;method_reviewed;input_artifacts_reviewed;"
            "input_artifact_sha256s_reviewed;expected_metric_source_artifact_reviewed;"
            "payload_schema_reviewed;license_ok_reviewed;operator_id;reviewed_at_utc;approval_token"
        ),
    }


def _triage_payload(*, machine_gap: bool = False) -> dict:
    return {
        "summary": {
            "status": (
                "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage"
                if machine_gap
                else "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_ready"
            )
        },
        "rows": [
            {
                "worksheet_id": "r9_bootstrap_driver_operator_review_001",
                "machine_supported_pending_fields": (
                    "metric_value_reviewed;method_reviewed;input_artifacts_reviewed;"
                    "input_artifact_sha256s_reviewed;expected_metric_source_artifact_reviewed;"
                    "payload_schema_reviewed"
                ),
                "machine_gap_pending_fields": "payload_schema_reviewed" if machine_gap else "",
            }
        ],
    }


def test_bootstrap_driver_operator_machine_prefill_template_reduces_current_pending_fields() -> None:
    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template()
    summary = payload["summary"]

    assert summary["status"] == (
        "refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_ready"
    )
    assert summary["prefill_row_count"] == 6
    assert summary["machine_supported_prefilled_field_count"] == 36
    assert summary["remaining_pending_field_count"] == 30
    assert summary["operator_only_remaining_field_count"] == 30
    assert summary["machine_remaining_field_count"] == 0
    assert summary["unclassified_remaining_field_count"] == 0
    assert summary["remaining_placeholder_row_count"] == 6
    assert summary["canonical_worksheet_edited"] is False
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    first_prefilled = payload["prefilled_rows"][0]
    assert first_prefilled["metric_value_reviewed"] == "true"
    assert first_prefilled["payload_schema_reviewed"] == "true"
    assert first_prefilled["operator_decision"] == "OPERATOR_FILL_ACCEPT_OR_REJECT"
    assert first_prefilled["approval_token"] == "OPERATOR_FILL_APPROVAL_TOKEN"


def test_bootstrap_driver_operator_machine_prefill_template_blocks_machine_gap(tmp_path: Path) -> None:
    worksheet_csv = tmp_path / "worksheet.csv"
    triage_json = tmp_path / "triage.json"
    _write_csv(worksheet_csv, [_worksheet_row()])
    _write_json(triage_json, _triage_payload(machine_gap=True))

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template(
        worksheet_csv=worksheet_csv,
        field_triage_json=triage_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template"
    assert summary["prefill_row_count"] == 1
    assert summary["machine_supported_prefilled_field_count"] == 0
    assert summary["machine_remaining_field_count"] == 6
    assert "machine_supported_fields_not_prefilled" in summary["blockers"]


def test_bootstrap_driver_operator_machine_prefill_template_cli_writes_outputs(tmp_path: Path) -> None:
    worksheet_csv = tmp_path / "worksheet.csv"
    triage_json = tmp_path / "triage.json"
    prefill_csv = tmp_path / "prefill.csv"
    out_json = tmp_path / "prefill.json"
    out_md = tmp_path / "prefill.md"
    _write_csv(worksheet_csv, [_worksheet_row()])
    _write_json(triage_json, _triage_payload(machine_gap=False))

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--worksheet-csv",
            str(worksheet_csv),
            "--field-triage-json",
            str(triage_json),
            "--prefill-csv",
            str(prefill_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(prefill_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["prefill_row_count"] == len(rows)
    assert rows[0]["metric_value_reviewed"] == "true"
    assert rows[0]["license_ok_reviewed"] == "OPERATOR_CONFIRM_TRUE"
    assert "R9 Bootstrap Driver Operator Machine Prefill Template" in out_md.read_text(encoding="utf-8")
