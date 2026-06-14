from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import (
    build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt as mod,
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


def _r4_preflight(path: Path) -> None:
    rows = [
        {
            "r4_review_id": "r9_statistical_support_coordinate_fetch_001",
            "target_id": "4ivc",
            "pose_id": "4ivc_20",
            "source_url_primary": "https://files.rcsb.org/download/4IVC.pdb",
            "staging_destination_path": "data/public_benchmarks/pdbbind_casf_pose_affinity/4ivc/4ivc_complex.pdb",
            "r4_preflight_status": "ready_for_r4_operator_confirmation",
            "coordinate_validation_status": "blocked",
            "metric_materialization_status": "blocked_metric_source_materialization_inputs",
            "target": "R9 statistical-support public coordinate fetch for 4ivc/4ivc_20",
            "action": "download public coordinate",
            "impact": "adds one local coordinate artifact",
            "risk": "wrong assembly could contaminate evidence",
            "rollback": "remove staged coordinate",
            "verification": "rerun coordinate validation",
        },
        {
            "r4_review_id": "r9_statistical_support_coordinate_fetch_002",
            "target_id": "3g0w",
            "pose_id": "3g0w_281",
            "source_url_primary": "https://files.rcsb.org/download/3G0W.pdb",
            "staging_destination_path": "data/public_benchmarks/pdbbind_casf_pose_affinity/3g0w/3g0w_complex.pdb",
            "r4_preflight_status": "ready_for_r4_operator_confirmation",
            "coordinate_validation_status": "blocked",
            "metric_materialization_status": "blocked_metric_source_materialization_inputs",
            "target": "R9 statistical-support public coordinate fetch for 3g0w/3g0w_281",
            "action": "download public coordinate",
            "impact": "adds one local coordinate artifact",
            "risk": "wrong assembly could contaminate evidence",
            "rollback": "remove staged coordinate",
            "verification": "rerun coordinate validation",
        },
    ]
    _write_json(
        path,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready",
                "r4_preflight_ready": True,
            },
            "rows": rows,
        },
    )


def _receipt_rows(*, ready: bool) -> list[dict[str, object]]:
    base = [
        ("r9_statistical_support_coordinate_fetch_001", "4ivc", "4ivc_20"),
        ("r9_statistical_support_coordinate_fetch_002", "3g0w", "3g0w_281"),
    ]
    rows = []
    for review_id, target_id, pose_id in base:
        rows.append(
            {
                "r4_review_id": review_id,
                "target_id": target_id,
                "pose_id": pose_id,
                "operator_decision": "approve_coordinate_fetch" if ready else "OPERATOR_FILL_DECISION",
                "coordinate_fetch_approved": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "source_url_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "staging_destination_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "license_ok": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "biological_assembly_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "execute_command_reviewed": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "post_fetch_validation_required": "true" if ready else "OPERATOR_CONFIRM_TRUE",
                "canonical_intake_promotion_allowed": "false",
                "claim_promotion_allowed": "false",
                "external_state_mutated": "false",
                "reviewer": "operator@example.test" if ready else "OPERATOR_FILL_REVIEWER",
                "reviewed_at_utc": "2026-06-14T00:00:00Z" if ready else "OPERATOR_FILL_REVIEWED_AT_UTC",
                "approval_token": mod.APPROVAL_TOKEN if ready else "OPERATOR_FILL_APPROVAL_TOKEN",
                "notes": "reviewed",
            }
        )
    return rows


def test_coordinate_fetch_operator_receipt_blocks_current_placeholders() -> None:
    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt()
    summary = payload["summary"]

    assert summary["status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
    )
    assert summary["operator_receipt_ready"] is False
    assert summary["receipt_csv_present"] is True
    assert summary["r4_preflight_present"] is True
    assert summary["r4_preflight_ready"] is True
    assert summary["receipt_row_count"] == 17
    assert summary["required_r4_review_count"] == 17
    assert summary["missing_required_r4_review_count"] == 0
    assert summary["unexpected_r4_review_count"] == 0
    assert summary["duplicate_r4_review_id_count"] == 0
    assert summary["pass_row_count"] == 0
    assert summary["blocked_row_count"] == 17
    assert summary["approved_fetch_count"] == 0
    assert summary["authorized_for_external_download"] is False
    assert summary["download_executed"] is False
    assert summary["canonical_intake_promotion_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["first_blocked_review_id"] == "r9_statistical_support_coordinate_fetch_001"
    assert summary["first_blocked_target_id"] == "4ivc"
    assert summary["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert summary["blocker_count"] == 1
    assert "blocked_receipt_rows_present" in summary["blockers"]
    assert payload["rows"][0]["source_url_primary"] == "https://files.rcsb.org/download/4IVC.pdb"


def test_coordinate_fetch_operator_receipt_ready_with_verified_rows(tmp_path: Path) -> None:
    r4_json = tmp_path / "r4.json"
    receipt_csv = tmp_path / "receipt.csv"
    _r4_preflight(r4_json)
    _write_csv(receipt_csv, _receipt_rows(ready=True), mod.REQUIRED_COLUMNS)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt(
        receipt_csv=receipt_csv,
        r4_preflight_json=r4_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
    )
    assert summary["operator_receipt_ready"] is True
    assert summary["pass_row_count"] == 2
    assert summary["blocked_row_count"] == 0
    assert summary["approved_fetch_count"] == 2
    assert summary["source_url_reviewed_count"] == 2
    assert summary["license_ok_count"] == 2
    assert summary["authorized_for_external_download"] is True
    assert summary["download_executed"] is False
    assert summary["blocker_count"] == 0


def test_coordinate_fetch_operator_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    r4_json = tmp_path / "r4.json"
    receipt_csv = tmp_path / "receipt.csv"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.out.csv"
    out_md = tmp_path / "receipt.md"
    _r4_preflight(r4_json)
    _write_csv(receipt_csv, _receipt_rows(ready=False), mod.REQUIRED_COLUMNS)

    mod.main(
        [
            "--receipt-csv",
            str(receipt_csv),
            "--r4-preflight-json",
            str(r4_json),
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
    assert out_csv.is_file()
    assert out_md.is_file()
