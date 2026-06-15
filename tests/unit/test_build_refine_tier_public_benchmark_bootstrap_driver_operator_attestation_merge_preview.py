from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview as mod
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


def _prefill_row() -> dict[str, str]:
    return {
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
        "approval_token_required": APPROVAL_TOKEN,
        "operator_manual_pending_field_count": "5",
        "operator_manual_pending_fields": "operator_decision;license_ok_reviewed;operator_id;reviewed_at_utc;approval_token",
        "payload_write_allowed": "False",
        "canonical_receipt_write_allowed": "False",
        "canonical_intake_promotion_allowed": "False",
        "claim_promotion_allowed": "False",
        "production_score_mutation_allowed": "False",
        "external_state_mutated": "False",
    }


def _attestation_row(prefill: dict[str, str], *, filled: bool, stale: bool = False) -> dict[str, str]:
    row = {
        "attestation_id": "r9_bootstrap_driver_operator_attestation_001",
        "worksheet_id": prefill["worksheet_id"],
        "target_id": prefill["target_id"],
        "pose_id": prefill["pose_id"],
        "work_order_id": prefill["work_order_id"],
        "split": prefill["split"],
        "metric_name": prefill["metric_name"],
        "review_surface": prefill["review_surface"],
        "prefill_row_sha256": "0" * 64 if stale else mod.prefill_row_fingerprint(prefill),
        "operator_decision": "accept" if filled else "OPERATOR_FILL_ACCEPT_OR_REJECT",
        "license_ok_reviewed": "true" if filled else "OPERATOR_CONFIRM_TRUE",
        "operator_id": "operator@example.test" if filled else "OPERATOR_FILL_OPERATOR_ID",
        "reviewed_at_utc": "2026-06-15T00:00:00Z" if filled else "OPERATOR_FILL_REVIEWED_AT_UTC",
        "approval_token": APPROVAL_TOKEN if filled else "OPERATOR_FILL_APPROVAL_TOKEN",
        "approval_token_required": APPROVAL_TOKEN,
    }
    return row


def test_bootstrap_driver_operator_attestation_merge_preview_blocks_current_placeholders() -> None:
    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview()
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview"
    assert summary["prefill_row_count"] == 6
    assert summary["attestation_row_count"] == 6
    assert summary["merge_preview_pass_row_count"] == 0
    assert summary["merge_preview_blocked_row_count"] == 6
    assert summary["prefill_row_fingerprint_verified_count"] == 6
    assert summary["prefill_row_fingerprint_mismatch_count"] == 0
    assert summary["merged_candidate_row_count"] == 0
    assert summary["attestation_merge_ready"] is False
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["most_common_row_blocker"] == "operator_only_placeholders_unfilled"
    assert "blocked_attestation_rows_present" in summary["blockers"]


def test_bootstrap_driver_operator_attestation_merge_preview_emits_merged_candidate_when_filled(
    tmp_path: Path,
) -> None:
    prefill = _prefill_row()
    prefill_csv = tmp_path / "prefill.csv"
    attestation_csv = tmp_path / "attestation.csv"
    _write_csv(prefill_csv, [prefill])
    _write_csv(attestation_csv, [_attestation_row(prefill, filled=True)])

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview(
        prefill_csv=prefill_csv,
        attestation_csv=attestation_csv,
        root=tmp_path,
    )
    summary = payload["summary"]
    merged = payload["merged_candidate_rows"][0]

    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview_ready"
    assert summary["attestation_merge_ready"] is True
    assert summary["merge_preview_pass_row_count"] == 1
    assert summary["merge_preview_blocked_row_count"] == 0
    assert summary["merged_candidate_row_count"] == 1
    assert merged["operator_decision"] == "accept"
    assert merged["license_ok_reviewed"] == "true"
    assert merged["operator_manual_pending_field_count"] == "0"
    assert merged["operator_manual_pending_fields"] == ""
    assert merged["payload_write_allowed"] == "False"


def test_bootstrap_driver_operator_attestation_merge_preview_blocks_stale_prefill_fingerprint(
    tmp_path: Path,
) -> None:
    prefill = _prefill_row()
    prefill_csv = tmp_path / "prefill.csv"
    attestation_csv = tmp_path / "attestation.csv"
    _write_csv(prefill_csv, [prefill])
    _write_csv(attestation_csv, [_attestation_row(prefill, filled=True, stale=True)])

    payload = mod.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview(
        prefill_csv=prefill_csv,
        attestation_csv=attestation_csv,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview"
    assert summary["prefill_row_fingerprint_verified_count"] == 0
    assert summary["prefill_row_fingerprint_mismatch_count"] == 1
    assert summary["merged_candidate_row_count"] == 0
    assert summary["attestation_merge_ready"] is False
    assert "blocked_attestation_rows_present" in summary["blockers"]


def test_bootstrap_driver_operator_attestation_merge_preview_cli_writes_outputs(tmp_path: Path) -> None:
    prefill = _prefill_row()
    prefill_csv = tmp_path / "prefill.csv"
    attestation_csv = tmp_path / "attestation.csv"
    merged_csv = tmp_path / "merged.csv"
    out_json = tmp_path / "merge.json"
    out_csv = tmp_path / "merge.csv"
    out_md = tmp_path / "merge.md"
    _write_csv(prefill_csv, [prefill])
    _write_csv(attestation_csv, [_attestation_row(prefill, filled=True)])

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--prefill-csv",
            str(prefill_csv),
            "--attestation-csv",
            str(attestation_csv),
            "--merged-candidate-csv",
            str(merged_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    report_rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    merged_rows = list(csv.DictReader(merged_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["merge_preview_row_count"] == len(report_rows)
    assert payload["summary"]["merged_candidate_row_count"] == len(merged_rows)
    assert "R9 Bootstrap Driver Operator Attestation Merge Preview" in out_md.read_text(encoding="utf-8")
