from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path: Path, target: str) -> tuple[str, str]:
    paths = []
    for name in ("pose.sdf", "receptor.pdb", "reference.sdf"):
        path = tmp_path / "inputs" / target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{target}:{name}\n", encoding="utf-8")
        paths.append(path)
    artifacts = ";".join(str(path.relative_to(tmp_path)) for path in paths)
    hashes = ";".join(_sha256(path) for path in paths)
    return artifacts, hashes


def _fixture_paths(tmp_path: Path) -> dict[str, Path]:
    candidate_artifacts, candidate_hashes = _inputs(tmp_path, "3f3e")
    existing_artifacts, existing_hashes = _inputs(tmp_path, "2j7h")
    paths = {
        "audit": tmp_path / "audit.json",
        "candidate": tmp_path / "candidate.json",
        "backfill": tmp_path / "backfill.json",
    }
    _write_json(
        paths["audit"],
        {
            "audit_rows": [
                {
                    "driver_audit_rank": 1,
                    "recovery_priority_rank": 1,
                    "target_id": "3f3e",
                    "pose_id": "3f3e_197",
                    "work_order_id": "wo_3f3e",
                    "split": "holdout",
                    "audit_class": "candidate_preview_payload_not_written",
                    "bootstrap_p05_delta_if_removed": "0.12",
                    "rank_abs_error": 18,
                },
                {
                    "driver_audit_rank": 2,
                    "recovery_priority_rank": 2,
                    "target_id": "2j7h",
                    "pose_id": "2j7h_48",
                    "work_order_id": "wo_2j7h",
                    "split": "fit",
                    "audit_class": "existing_payload_receipt_backfill_pending",
                    "bootstrap_p05_delta_if_removed": "0.08",
                    "rank_abs_error": 16,
                },
            ]
        },
    )
    _write_json(
        paths["candidate"],
        {
            "rows": [
                {
                    "target_id": "3f3e",
                    "pose_id": "3f3e_197",
                    "metric_name": metric,
                    "metric_value_candidate": value,
                    "method_candidate": f"candidate_{metric}",
                    "candidate_input_artifacts": candidate_artifacts,
                    "candidate_input_artifact_sha256s": candidate_hashes,
                    "expected_metric_source_artifact": f"runs/3f3e_{metric}.json",
                    "expected_metric_source_artifact_present": False,
                }
                for metric, value in (("dockq", "0.7"), ("lddt_pli", "1.0"), ("internal_deltaG", "-2.3"))
            ]
        },
    )
    _write_json(
        paths["backfill"],
        {
            "backfill_template_rows": [
                {
                    "payload_priority_rank": index,
                    "target_id": "2j7h",
                    "pose_id": "2j7h_48",
                    "work_order_id": "wo_2j7h",
                    "split": "fit",
                    "metric_name": metric,
                    "metric_source_artifact": f"runs/2j7h_{metric}.json",
                    "metric_source_artifact_present": True,
                    "metric_source_artifact_sha256": "a" * 64,
                    "payload_validation_status": "pass",
                    "existing_metric_value": value,
                    "existing_metric_method": f"method_{metric}",
                    "input_artifacts": existing_artifacts,
                    "input_artifact_sha256s": existing_hashes,
                    "input_artifact_count": 3,
                    "input_artifact_sha256_verified_count": 3,
                    "operator_decision": "OPERATOR_FILL_ACCEPT_OR_REJECT",
                    "metric_value_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "method_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "input_artifacts_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "input_artifact_sha256s_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "metric_source_artifact_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "payload_schema_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "license_ok_reviewed": "OPERATOR_CONFIRM_TRUE",
                    "operator_id": "OPERATOR_FILL_OPERATOR_ID",
                    "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
                    "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
                    "approval_token_required": "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS",
                    "operator_manual_pending_field_count": 11,
                    "operator_manual_pending_fields": "operator_decision;approval_token",
                }
                for index, (metric, value) in enumerate(
                    (("dockq", "0.71"), ("lddt_pli", "1.0"), ("internal_deltaG", "-2.1")),
                    start=4,
                )
            ]
        },
    )
    return paths


def test_bootstrap_driver_operator_review_worksheet_expands_candidate_and_backfill_rows(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet(
        driver_audit_json=paths["audit"],
        candidate_fill_json=paths["candidate"],
        backfill_json=paths["backfill"],
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = payload["worksheet_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_ready"
    assert summary["worksheet_row_count"] == 6
    assert summary["candidate_preview_review_row_count"] == 3
    assert summary["existing_payload_backfill_review_row_count"] == 3
    assert summary["candidate_preview_input_hash_verified_row_count"] == 3
    assert summary["existing_payload_validation_pass_row_count"] == 3
    assert summary["existing_payload_input_hash_verified_row_count"] == 3
    assert summary["operator_manual_pending_field_count"] == 66
    assert summary["payload_write_allowed"] is False
    assert rows[0]["review_surface"] == "candidate_preview_payload_write_review"
    assert rows[-1]["review_surface"] == "existing_payload_backfill_receipt_review"
    assert rows[-1]["claim_promotion_allowed"] is False


def test_bootstrap_driver_operator_review_worksheet_cli_writes_outputs(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--driver-audit-json",
            str(paths["audit"]),
            "--candidate-fill-json",
            str(paths["candidate"]),
            "--backfill-json",
            str(paths["backfill"]),
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
    assert "R9 Bootstrap Driver Operator Review Worksheet" in out_md.read_text(encoding="utf-8")
