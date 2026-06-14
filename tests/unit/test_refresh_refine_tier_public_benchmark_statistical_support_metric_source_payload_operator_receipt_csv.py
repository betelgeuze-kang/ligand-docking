from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import (
    build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt as receipt_mod,
)
from tools.product import (
    refresh_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv as mod,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=receipt_mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _template_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, metric_name in enumerate(("dockq", "lddt_pli"), start=1):
        rows.append(
            {
                "template_id": f"r9_statistical_support_metric_source_template_{index:03d}",
                "candidate_queue_id": "stat_support_candidate_001",
                "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "target_id": "4ivc",
                "pose_id": "4ivc_20",
                "metric_name": metric_name,
                "metric_source_artifact": f"runs/refine_tier_public_benchmark_metric_sources/{metric_name}.json",
                "required_metric_input_artifacts": "ligand.sdf;receptor.pdb",
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
            }
        )
    return rows


def _templates_json(path: Path) -> list[dict[str, str]]:
    rows = _template_rows()
    _write_json(
        path,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready",
            },
            "rows": rows,
        },
    )
    return rows


def _receipt_row(template: dict[str, str], *, fingerprint: str, metric_value: str) -> dict[str, str]:
    return {
        "template_id": template["template_id"],
        "target_id": template["target_id"],
        "pose_id": template["pose_id"],
        "metric_name": template["metric_name"],
        "metric_source_template_row_sha256": fingerprint,
        "metric_value": metric_value,
        "method": "reviewed_local_metric",
        "input_artifacts_reviewed": "true",
        "input_artifact_sha256s_reviewed": "true",
        "metric_source_artifact_reviewed": "true",
        "payload_schema_reviewed": "true",
        "license_ok": "true",
        "external_engine_calls": "0",
        "operator_id": "operator@example.test",
        "reviewed_at_utc": "2026-06-14T00:00:00Z",
        "approval_token": receipt_mod.APPROVAL_TOKEN,
        "notes": "reviewed",
    }


def test_refresh_metric_source_payload_receipt_csv_preview_does_not_write(tmp_path: Path) -> None:
    templates_json = tmp_path / "templates.json"
    receipt_csv = tmp_path / "receipt.csv"
    out_csv = tmp_path / "out.csv"
    templates = _templates_json(templates_json)
    _write_csv(receipt_csv, [_receipt_row(templates[0], fingerprint="old", metric_value="0.5")])

    payload = mod.refresh_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv(
        metric_source_templates_json=templates_json,
        receipt_csv=receipt_csv,
        out_csv=out_csv,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["write_executed"] is False
    assert summary["refreshed_receipt_row_count"] == 2
    assert summary["reset_review_row_count"] == 2
    assert summary["numeric_metric_value_filled_count"] == 0
    assert summary["approval_token_filled_count"] == 0
    assert not out_csv.exists()


def test_refresh_metric_source_payload_receipt_csv_writes_current_fingerprints(
    tmp_path: Path,
) -> None:
    templates_json = tmp_path / "templates.json"
    receipt_csv = tmp_path / "receipt.csv"
    templates = _templates_json(templates_json)
    current_fingerprint = receipt_mod.template_row_fingerprint(templates[0])
    _write_csv(
        receipt_csv,
        [
            _receipt_row(templates[0], fingerprint=current_fingerprint, metric_value="0.5"),
            _receipt_row(templates[1], fingerprint="old", metric_value="0.9"),
        ],
    )

    payload = mod.refresh_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv(
        metric_source_templates_json=templates_json,
        receipt_csv=receipt_csv,
        write=True,
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = _read_csv(receipt_csv)
    assert summary["write_executed"] is True
    assert summary["preserved_existing_review_row_count"] == 1
    assert summary["reset_review_row_count"] == 1
    assert rows[0]["metric_source_template_row_sha256"] == current_fingerprint
    assert rows[0]["metric_value"] == "0.5"
    assert rows[0]["approval_token"] == receipt_mod.APPROVAL_TOKEN
    assert rows[1]["metric_source_template_row_sha256"] == receipt_mod.template_row_fingerprint(
        templates[1]
    )
    assert rows[1]["metric_value"] == "OPERATOR_FILL_NUMERIC_METRIC_VALUE"
    assert rows[1]["approval_token"] == "OPERATOR_FILL_APPROVAL_TOKEN"
