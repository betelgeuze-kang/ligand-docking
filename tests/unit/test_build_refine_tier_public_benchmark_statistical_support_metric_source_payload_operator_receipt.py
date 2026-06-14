from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import (
    build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt as mod,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _template_rows(*, ready: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, metric_name in enumerate(["dockq", "lddt_pli"], start=1):
        rows.append(
            {
                "template_id": f"r9_statistical_support_metric_source_template_{index:03d}",
                "candidate_queue_id": "stat_support_candidate_001",
                "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "target_id": "4ivc",
                "pose_id": "4ivc_20",
                "metric_name": metric_name,
                "metric_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/"
                    f"refine_tier_public_benchmark_stat_support_expansion_001_{metric_name}.json"
                ),
                "required_metric_input_artifacts": (
                    "data/public_benchmarks/pdbbind_casf_pose_affinity/data_5_sdf/4ivc_20;"
                    "data/public_benchmarks/pdbbind_casf_pose_affinity/4ivc/4ivc_receptor.pdb"
                ),
                "required_metric_input_artifact_sha256s": "abc;def",
                "required_metric_source_payload_fields": (
                    "metric_name;target_id;pose_id;value;method;input_artifacts;"
                    "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls"
                ),
                "template_payload_json": json.dumps(
                    {
                        "metric_name": metric_name,
                        "target_id": "4ivc",
                        "pose_id": "4ivc_20",
                        "value": "OPERATOR_FILL_NUMERIC_METRIC_VALUE",
                    },
                    sort_keys=True,
                ),
                "coordinate_validation_status": "pass" if ready else "blocked",
                "metric_materialization_status": (
                    "ready_for_metric_source_materialization"
                    if ready
                    else "blocked_metric_source_materialization_inputs"
                ),
                "metric_source_payload_fill_ready": ready,
                "missing_required_metric_input_artifact_count": 0 if ready else 1,
                "template_status": (
                    "ready_for_operator_metric_source_payload_fill"
                    if ready
                    else "blocked_until_coordinate_validation_passes"
                ),
                "template_blockers": "" if ready else "coordinate_validation_not_pass",
            }
        )
    return rows


def _templates_json(path: Path, *, ready: bool) -> list[dict[str, object]]:
    rows = _template_rows(ready=ready)
    _write_json(
        path,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready",
                "metric_source_templates_ready": True,
            },
            "rows": rows,
        },
    )
    return rows


def _receipt_rows(template_rows: list[dict[str, object]], *, ready: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for template in template_rows:
        rows.append(
            {
                "template_id": template["template_id"],
                "target_id": template["target_id"],
                "pose_id": template["pose_id"],
                "metric_name": template["metric_name"],
                "metric_source_template_row_sha256": (
                    mod.template_row_fingerprint(template)
                    if ready
                    else "OPERATOR_FILL_METRIC_SOURCE_TEMPLATE_ROW_SHA256"
                ),
                "metric_value": "0.75" if ready else "OPERATOR_FILL_NUMERIC_METRIC_VALUE",
                "method": "reviewed_local_metric" if ready else "OPERATOR_FILL_METHOD_OR_TOOL",
                "input_artifacts_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "input_artifact_sha256s_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "metric_source_artifact_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "payload_schema_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "license_ok": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "external_engine_calls": "0",
                "operator_id": "operator@example.test" if ready else "OPERATOR_FILL_OPERATOR_ID",
                "reviewed_at_utc": "2026-06-14T00:00:00Z" if ready else "OPERATOR_FILL_REVIEWED_AT_UTC",
                "approval_token": mod.APPROVAL_TOKEN if ready else "OPERATOR_FILL_APPROVAL_TOKEN",
                "notes": "reviewed",
            }
        )
    return rows


def test_metric_source_payload_operator_receipt_blocks_current_placeholders() -> None:
    payload = mod.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt()
    summary = payload["summary"]

    assert summary["status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
    )
    assert summary["operator_receipt_ready"] is False
    assert summary["receipt_csv_present"] is True
    assert summary["metric_source_templates_present"] is True
    assert summary["metric_source_templates_ready"] is True
    assert summary["receipt_row_count"] == 51
    assert summary["required_template_count"] == 51
    assert summary["metric_source_template_row_fingerprint_required"] is True
    assert summary["metric_source_template_row_fingerprint_verified_count"] == 51
    assert summary["metric_source_template_row_fingerprint_mismatch_count"] == 0
    assert summary["pass_row_count"] == 0
    assert summary["blocked_row_count"] == 51
    assert summary["approved_payload_count"] == 0
    assert summary["coordinate_validation_pass_payload_row_count"] == 0
    assert summary["coordinate_validation_blocked_payload_row_count"] == 51
    assert summary["payload_write_allowed"] is False
    assert summary["canonical_intake_promotion_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["first_blocked_template_id"] == "r9_statistical_support_metric_source_template_001"
    assert summary["first_blocked_metric_name"] == "dockq"
    assert summary["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert summary["blocker_count"] == 1
    assert "blocked_receipt_rows_present" in summary["blockers"]


def test_metric_source_payload_operator_receipt_ready_with_verified_rows(tmp_path: Path) -> None:
    templates_json = tmp_path / "templates.json"
    receipt_csv = tmp_path / "receipt.csv"
    template_rows = _templates_json(templates_json, ready=True)
    _write_csv(receipt_csv, _receipt_rows(template_rows, ready=True), mod.REQUIRED_COLUMNS)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt(
        receipt_csv=receipt_csv,
        metric_source_templates_json=templates_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
    )
    assert summary["operator_receipt_ready"] is True
    assert summary["pass_row_count"] == 2
    assert summary["blocked_row_count"] == 0
    assert summary["metric_source_template_row_fingerprint_verified_count"] == 2
    assert summary["approved_payload_count"] == 2
    assert summary["coordinate_validation_pass_payload_row_count"] == 2
    assert summary["blocker_count"] == 0


def test_metric_source_payload_operator_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    templates_json = tmp_path / "templates.json"
    receipt_csv = tmp_path / "receipt.csv"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.out.csv"
    out_md = tmp_path / "receipt.md"
    template_rows = _templates_json(templates_json, ready=False)
    _write_csv(receipt_csv, _receipt_rows(template_rows, ready=False), mod.REQUIRED_COLUMNS)

    mod.main(
        [
            "--receipt-csv",
            str(receipt_csv),
            "--metric-source-templates-json",
            str(templates_json),
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["receipt_row_count"] == 2
    assert payload["summary"]["blocked_row_count"] == 2
    assert payload["summary"]["metric_source_template_row_fingerprint_mismatch_count"] == 2
    assert out_csv.is_file()
    assert out_md.is_file()
