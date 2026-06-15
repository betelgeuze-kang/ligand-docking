from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply as mod
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in mod.REQUIRED_COLUMNS})


def _input_artifacts(root: Path, target: str) -> tuple[str, str]:
    paths = []
    for filename in ("pose.sdf", "receptor.pdb", "reference.sdf"):
        path = root / "data" / target / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{target}:{filename}\n", encoding="utf-8")
        paths.append(path)
    artifacts = ";".join(str(path.relative_to(root)) for path in paths)
    hashes = ";".join(_sha256(path) for path in paths)
    return artifacts, hashes


def _worksheet_row(
    *,
    root: Path,
    worksheet_id: str,
    target_id: str,
    pose_id: str,
    metric_name: str,
    review_surface: str,
    artifact: str,
    value: str,
    method: str,
    ready: bool,
) -> dict[str, str]:
    artifacts, hashes = _input_artifacts(root, target_id)
    return {
        "worksheet_id": worksheet_id,
        "target_id": target_id,
        "pose_id": pose_id,
        "work_order_id": f"wo_{target_id}",
        "split": "holdout",
        "metric_name": metric_name,
        "review_surface": review_surface,
        "metric_value_under_review": value,
        "method_under_review": method,
        "expected_metric_source_artifact": artifact,
        "expected_metric_source_artifact_present": str(review_surface.startswith("existing")).lower(),
        "metric_source_artifact_sha256": "",
        "payload_validation_status": "pass" if review_surface.startswith("existing") else "candidate_payload_not_written",
        "input_artifacts": artifacts,
        "input_artifact_sha256s": hashes,
        "input_artifact_sha256_verified": "true",
        "operator_decision": "accept" if ready else "OPERATOR_FILL_ACCEPT_OR_REJECT",
        "metric_value_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "method_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "input_artifacts_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "input_artifact_sha256s_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "expected_metric_source_artifact_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "payload_schema_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "license_ok_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
        "operator_id": "operator@example.test" if ready else "OPERATOR_FILL_OPERATOR_ID",
        "reviewed_at_utc": "2026-06-15T00:00:00Z" if ready else "OPERATOR_FILL_REVIEWED_AT_UTC",
        "approval_token": APPROVAL_TOKEN if ready else "OPERATOR_FILL_APPROVAL_TOKEN",
        "approval_token_required": APPROVAL_TOKEN,
    }


def _write_metric_source_payload(path: Path, row: dict[str, str], root: Path) -> str:
    payload = {
        "metric_name": row["metric_name"],
        "target_id": row["target_id"],
        "pose_id": row["pose_id"],
        "value": float(row["metric_value_under_review"]),
        "method": row["method_under_review"],
        "input_artifacts": row["input_artifacts"].split(";"),
        "input_artifact_sha256s": row["input_artifact_sha256s"].split(";"),
        "operator_id": "local_refine_tier_metric_materializer",
        "reviewed_at_utc": "2026-06-14T00:00:00Z",
        "license_ok": True,
        "external_engine_calls": 0,
    }
    _write_json(root / path, payload)
    return _sha256(root / path)


def test_bootstrap_driver_operator_staging_apply_blocks_current_placeholder_sheet() -> None:
    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply()
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply"
    assert summary["worksheet_csv_present"] is True
    assert summary["worksheet_json_present"] is True
    assert summary["worksheet_row_count"] == 6
    assert summary["pass_row_count"] == 0
    assert summary["blocked_row_count"] == 6
    assert summary["candidate_preview_row_count"] == 3
    assert summary["existing_payload_backfill_row_count"] == 3
    assert summary["input_artifact_sha256_verified_row_count"] == 6
    assert summary["existing_payload_schema_revalidated_row_count"] == 3
    assert summary["operator_manual_pending_field_count"] == 66
    assert summary["placeholder_row_count"] == 6
    assert summary["payload_write_allowed"] is False
    assert summary["canonical_receipt_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert "blocked_worksheet_rows_present" in summary["blockers"]


def test_bootstrap_driver_operator_staging_apply_ready_preview_keeps_writes_disabled(
    tmp_path: Path,
) -> None:
    candidate_artifact = "runs/refine_tier_public_benchmark_metric_sources/candidate_dockq.json"
    existing_artifact = "runs/refine_tier_public_benchmark_metric_sources/existing_dockq.json"
    candidate_row = _worksheet_row(
        root=tmp_path,
        worksheet_id="r9_bootstrap_driver_operator_review_001",
        target_id="3f3e",
        pose_id="3f3e_197",
        metric_name="dockq",
        review_surface="candidate_preview_payload_write_review",
        artifact=candidate_artifact,
        value="0.733726",
        method="candidate_internal_ligand_pose_reference_dockq_proxy_v1",
        ready=True,
    )
    existing_row = _worksheet_row(
        root=tmp_path,
        worksheet_id="r9_bootstrap_driver_operator_review_002",
        target_id="2j7h",
        pose_id="2j7h_48",
        metric_name="dockq",
        review_surface="existing_payload_backfill_receipt_review",
        artifact=existing_artifact,
        value="0.731168",
        method="internal_ligand_pose_reference_dockq_proxy_v1",
        ready=True,
    )
    existing_row["metric_source_artifact_sha256"] = _write_metric_source_payload(
        Path(existing_artifact),
        existing_row,
        tmp_path,
    )
    worksheet_csv = tmp_path / "worksheet.csv"
    worksheet_json = tmp_path / "worksheet.json"
    _write_csv(worksheet_csv, [candidate_row, existing_row])
    _write_json(
        worksheet_json,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_ready",
                "worksheet_row_count": 2,
            }
        },
    )

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply(
        worksheet_csv=worksheet_csv,
        worksheet_json=worksheet_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_staging_preview_ready"
    assert summary["pass_row_count"] == 2
    assert summary["blocked_row_count"] == 0
    assert summary["candidate_payload_write_preview_ready_count"] == 1
    assert summary["existing_payload_receipt_backfill_preview_ready_count"] == 1
    assert summary["operator_manual_pending_field_count"] == 0
    assert summary["placeholder_row_count"] == 0
    assert summary["payload_write_preview_ready"] is True
    assert summary["payload_write_allowed"] is False
    assert summary["canonical_receipt_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert payload["rows"][0]["payload_preview_json"]


def test_bootstrap_driver_operator_staging_apply_cli_writes_outputs(tmp_path: Path) -> None:
    worksheet_csv = tmp_path / "worksheet.csv"
    worksheet_json = tmp_path / "worksheet.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    row = _worksheet_row(
        root=tmp_path,
        worksheet_id="r9_bootstrap_driver_operator_review_001",
        target_id="3f3e",
        pose_id="3f3e_197",
        metric_name="dockq",
        review_surface="candidate_preview_payload_write_review",
        artifact="runs/missing_candidate.json",
        value="0.733726",
        method="candidate_internal_ligand_pose_reference_dockq_proxy_v1",
        ready=False,
    )
    _write_csv(worksheet_csv, [row])
    _write_json(
        worksheet_json,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_ready",
                "worksheet_row_count": 1,
            }
        },
    )

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--worksheet-csv",
            str(worksheet_csv),
            "--worksheet-json",
            str(worksheet_json),
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
    assert payload["summary"]["worksheet_row_count"] == len(rows)
    assert payload["summary"]["blocked_row_count"] == 1
    assert "R9 Bootstrap Driver Operator Staging Apply Preview" in out_md.read_text(encoding="utf-8")
