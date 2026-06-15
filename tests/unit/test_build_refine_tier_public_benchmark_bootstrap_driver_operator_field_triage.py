from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _staging_row(*, ready_support: bool = True, review_surface: str = "candidate_preview_payload_write_review") -> dict:
    return {
        "worksheet_id": "r9_bootstrap_driver_operator_review_001",
        "target_id": "3f3e",
        "pose_id": "3f3e_197",
        "work_order_id": "wo_3f3e",
        "split": "holdout",
        "metric_name": "dockq",
        "review_surface": review_surface,
        "row_status": "blocked",
        "blockers": "operator_placeholders_unfilled;operator_manual_fields_pending",
        "operator_manual_pending_fields": (
            "operator_decision;metric_value_reviewed;method_reviewed;input_artifacts_reviewed;"
            "input_artifact_sha256s_reviewed;expected_metric_source_artifact_reviewed;"
            "payload_schema_reviewed;license_ok_reviewed;operator_id;reviewed_at_utc;approval_token"
        ),
        "metric_value_under_review": "0.733726" if ready_support else "not-a-number",
        "method_under_review": "candidate_internal_ligand_pose_reference_dockq_proxy_v1" if ready_support else "",
        "input_artifact_sha256_verified": ready_support,
        "expected_metric_source_artifact_present": False if review_surface.startswith("candidate") else ready_support,
        "existing_payload_schema_revalidated": ready_support if review_surface.startswith("existing") else False,
    }


def test_bootstrap_driver_operator_field_triage_splits_current_pending_fields() -> None:
    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage()
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_field_triage_ready"
    assert summary["row_count"] == 6
    assert summary["manual_pending_field_count"] == 66
    assert summary["machine_supported_pending_field_count"] == 36
    assert summary["operator_only_pending_field_count"] == 30
    assert summary["machine_gap_pending_field_count"] == 0
    assert summary["unclassified_pending_field_count"] == 0
    assert summary["input_artifact_sha256_verified_row_count"] == 6
    assert summary["metric_source_artifact_state_consistent_row_count"] == 6
    assert summary["payload_schema_support_ready_row_count"] == 6
    assert summary["license_requires_operator_review_row_count"] == 6
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False


def test_bootstrap_driver_operator_field_triage_blocks_machine_support_gaps(tmp_path: Path) -> None:
    staging_json = tmp_path / "staging.json"
    _write_json(
        staging_json,
        {
            "summary": {
                "status": "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply",
                "pass_row_count": 0,
                "blocked_row_count": 1,
            },
            "rows": [_staging_row(ready_support=False)],
        },
    )

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage(
        staging_apply_json=staging_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage"
    assert summary["row_count"] == 1
    assert summary["manual_pending_field_count"] == 11
    assert summary["machine_supported_pending_field_count"] == 1
    assert summary["machine_gap_pending_field_count"] == 5
    assert "machine_supported_review_field_evidence_gaps_present" in summary["blockers"]


def test_bootstrap_driver_operator_field_triage_cli_writes_outputs(tmp_path: Path) -> None:
    staging_json = tmp_path / "staging.json"
    out_json = tmp_path / "triage.json"
    out_csv = tmp_path / "triage.csv"
    out_md = tmp_path / "triage.md"
    _write_json(
        staging_json,
        {
            "summary": {
                "status": "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply",
                "pass_row_count": 0,
                "blocked_row_count": 1,
            },
            "rows": [_staging_row(ready_support=True)],
        },
    )

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--staging-apply-json",
            str(staging_json),
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
    assert payload["summary"]["row_count"] == len(rows)
    assert payload["summary"]["machine_supported_pending_field_count"] == 6
    assert "R9 Bootstrap Driver Operator Field Triage" in out_md.read_text(encoding="utf-8")
