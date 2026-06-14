from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_residual_metric_payload_priority_packet as mod


METRICS = ("dockq", "lddt_pli", "internal_deltaG")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _residual_rows() -> list[dict[str, str]]:
    return [
        {
            "priority_rank": "1",
            "target_id": "3n86",
            "pose_id": "3n86_99",
            "work_order_id": "exp_009",
            "source": "candidate_fill_preview",
            "split": "fit",
            "locked_cv_rank_abs_error": "14",
            "baseline_rank_abs_error": "13",
            "cv_rank_error_vs_baseline": "worse",
            "rank_direction": "overranked_stronger_than_reference",
            "leave_one_out_bootstrap_p05_delta": "-0.03",
            "leave_one_out_leverage": "False",
            "contact_per_atom": "98.1",
            "pose_atom_count": "23",
            "primary_action": "target_heldout_generalization_regression_review",
            "required_reviewed_metric_payloads": ";".join(
                f"runs/refine_tier_public_benchmark_metric_sources/exp_009_{metric}.json"
                for metric in METRICS
            ),
        },
        {
            "priority_rank": "2",
            "target_id": "2j7h",
            "pose_id": "2j7h_48",
            "work_order_id": "seed_005",
            "source": "existing_materialized",
            "split": "fit",
            "locked_cv_rank_abs_error": "13",
            "baseline_rank_abs_error": "16",
            "cv_rank_error_vs_baseline": "better",
            "rank_direction": "underranked_weaker_than_reference",
            "leave_one_out_bootstrap_p05_delta": "0.08",
            "leave_one_out_leverage": "True",
            "contact_per_atom": "94.7",
            "pose_atom_count": "10",
            "primary_action": "underbinding_pose_contact_coverage_review",
            "required_reviewed_metric_payloads": ";".join(
                f"runs/refine_tier_public_benchmark_metric_sources/seed_005_{metric}.json"
                for metric in METRICS
            ),
        },
    ]


def _candidate_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, metric in enumerate(METRICS, start=1):
        rows.append(
            {
                "template_id": f"template_{idx:03d}",
                "candidate_queue_id": "candidate_009",
                "suggested_work_order_id": "exp_009",
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "split": "fit",
                "metric_name": metric,
                "metric_value_candidate": str(idx / 10),
                "method_candidate": f"candidate_method_{metric}",
                "expected_metric_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/exp_009_{metric}.json"
                ),
                "expected_metric_source_artifact_present": "False",
                "required_metric_input_artifacts": "pose;receptor",
                "candidate_input_artifact_sha256s": "a;b",
                "candidate_input_artifact_sha256s_complete": "True",
            }
        )
    return rows


def _receipt_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, metric in enumerate(METRICS, start=1):
        rows.append(
            {
                "template_id": f"template_{idx:03d}",
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "metric_name": metric,
                "candidate_queue_id": "candidate_009",
                "suggested_work_order_id": "exp_009",
                "metric_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/exp_009_{metric}.json"
                ),
                "required_metric_input_artifacts": "pose;receptor",
                "required_metric_input_artifact_sha256s": "a;b",
                "row_status": "blocked",
                "blockers": "operator_placeholders_unfilled",
                "operator_review_surface_ready": "True",
                "operator_manual_pending_fields": "metric_value;method;approval_token",
                "operator_manual_pending_field_count": "10",
                "metric_source_template_row_fingerprint_verified": "True",
            }
        )
    return rows


def test_residual_metric_payload_priority_packet_surfaces_receipt_gaps(tmp_path: Path) -> None:
    board_json = tmp_path / "board.json"
    board_csv = tmp_path / "board.csv"
    candidate_csv = tmp_path / "candidate.csv"
    receipt_csv = tmp_path / "receipt.csv"
    _write_json(
        board_json,
        {
            "summary": {
                "locked_cv_model_id": "density_size_ridge_l0.1",
                "locked_cv_bootstrap_p05": 0.403,
                "locked_cv_bootstrap_p05_gap_to_claim_grade": 0.097,
            }
        },
    )
    _write_csv(board_csv, _residual_rows())
    _write_csv(candidate_csv, _candidate_rows())
    _write_csv(receipt_csv, _receipt_rows())
    for metric in METRICS:
        _write_json(
            tmp_path / f"runs/refine_tier_public_benchmark_metric_sources/seed_005_{metric}.json",
            {
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "metric_name": metric,
                "value": 0.5,
                "method": f"existing_method_{metric}",
                "input_artifacts": ["pose", "receptor"],
                "input_artifact_sha256s": ["a", "b"],
            },
        )

    payload = mod.build_refine_tier_public_benchmark_residual_metric_payload_priority_packet(
        root=tmp_path,
        residual_board_json=board_json,
        residual_board_csv=board_csv,
        candidate_fill_csv=candidate_csv,
        operator_receipt_csv=receipt_csv,
    )

    summary = payload["summary"]
    rows = payload["priority_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_residual_metric_payload_priority_packet_ready"
    assert summary["metric_payload_priority_row_count"] == 6
    assert summary["candidate_fill_matched_payload_count"] == 3
    assert summary["operator_receipt_matched_payload_count"] == 3
    assert summary["operator_receipt_missing_payload_count"] == 3
    assert summary["operator_receipt_blocked_payload_count"] == 3
    assert summary["existing_metric_source_artifact_present_without_receipt_count"] == 3
    assert summary["operator_manual_pending_field_count"] == 30
    assert rows[0]["target_id"] == "3n86"
    assert rows[0]["operator_gap_class"] == "operator_receipt_blocked_placeholders"
    assert rows[3]["target_id"] == "2j7h"
    assert rows[3]["review_priority_class"] == "residual_leverage_metric_payload_first"
    assert rows[3]["operator_gap_class"] == "existing_metric_payload_present_without_operator_receipt"
    assert rows[3]["existing_metric_method"] == "existing_method_dockq"
    assert rows[3]["claim_promotion_allowed"] is False


def test_residual_metric_payload_priority_packet_cli_writes_outputs(tmp_path: Path) -> None:
    board_json = tmp_path / "board.json"
    board_csv = tmp_path / "board.csv"
    candidate_csv = tmp_path / "candidate.csv"
    receipt_csv = tmp_path / "receipt.csv"
    out_json = tmp_path / "priority.json"
    out_csv = tmp_path / "priority.csv"
    out_md = tmp_path / "priority.md"
    _write_json(board_json, {"summary": {"locked_cv_model_id": "model"}})
    _write_csv(board_csv, _residual_rows()[:1])
    _write_csv(candidate_csv, _candidate_rows())
    _write_csv(receipt_csv, _receipt_rows())

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--residual-board-json",
            str(board_json),
            "--residual-board-csv",
            str(board_csv),
            "--candidate-fill-csv",
            str(candidate_csv),
            "--operator-receipt-csv",
            str(receipt_csv),
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
    assert payload["summary"]["metric_payload_priority_row_count"] == len(rows)
    assert "R9 Residual Metric Payload Priority Packet" in out_md.read_text(encoding="utf-8")
