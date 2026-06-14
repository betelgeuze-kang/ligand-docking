from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_cv_failure_analysis_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _cv_payload() -> dict:
    return {
        "summary": {
            "locked_cv_model_id": "density_size_ridge_l0.1",
            "fit_trained_best_model_bootstrap_p05": 0.4944,
            "locked_cv_bootstrap_p05": 0.4035,
            "baseline_holdout_spearman": 0.64,
            "locked_cv_holdout_spearman": 0.59,
            "cross_validation_generalization_ready": False,
        },
        "locked_cv_rank_residual_rows": [
            {
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "split": "fit",
                "source": "candidate_fill_preview",
                "reference": "-7.0",
                "baseline_proxy": "-8.0",
                "variant_proxy": "-12.0",
                "reference_rank": 16,
                "variant_rank": 2,
                "rank_abs_error": 14,
                "contact_per_atom": "98",
                "pose_atom_count": "23",
            },
            {
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "split": "fit",
                "source": "existing_materialized",
                "reference": "-9.8",
                "baseline_proxy": "-2.1",
                "variant_proxy": "-6.6",
                "reference_rank": 9,
                "variant_rank": 22,
                "rank_abs_error": 13,
                "contact_per_atom": "94",
                "pose_atom_count": "10",
            },
            {
                "target_id": "3f3e",
                "pose_id": "3f3e_197",
                "split": "holdout",
                "source": "candidate_fill_preview",
                "reference": "-10.5",
                "baseline_proxy": "-2.3",
                "variant_proxy": "-7.8",
                "reference_rank": 6,
                "variant_rank": 17,
                "rank_abs_error": 11,
                "contact_per_atom": "109",
                "pose_atom_count": "9",
            },
        ],
        "baseline_rank_residual_rows": [
            {
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "split": "fit",
                "variant_rank": 3,
                "rank_abs_error": 13,
            },
            {
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "split": "fit",
                "variant_rank": 25,
                "rank_abs_error": 16,
            },
            {
                "target_id": "3f3e",
                "pose_id": "3f3e_197",
                "split": "holdout",
                "variant_rank": 24,
                "rank_abs_error": 18,
            },
        ],
        "locked_cv_fold_rows": [
            {"target_id": "3n86", "pose_id": "3n86_99", "split": "fit", "cv_proxy": "-12.0"},
            {"target_id": "2j7h", "pose_id": "2j7h_48", "split": "fit", "cv_proxy": "-6.6"},
            {"target_id": "3f3e", "pose_id": "3f3e_197", "split": "holdout", "cv_proxy": "-7.8"},
        ],
    }


def _priority_payload() -> dict:
    rows = []
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=1):
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "metric_name": metric,
                "operator_gap_class": "operator_receipt_blocked_placeholders",
            }
        )
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=4):
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "metric_name": metric,
                "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
            }
        )
    return {
        "summary": {"metric_payload_priority_row_count": len(rows)},
        "priority_rows": rows,
    }


def test_cv_failure_analysis_packet_joins_residuals_to_payload_gaps(tmp_path: Path) -> None:
    cv_json = tmp_path / "cv.json"
    priority_json = tmp_path / "priority.json"
    _write_json(cv_json, _cv_payload())
    _write_json(priority_json, _priority_payload())

    payload = mod.build_refine_tier_public_benchmark_cv_failure_analysis_packet(
        cv_json=cv_json,
        residual_priority_json=priority_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = payload["failure_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_cv_failure_analysis_packet_ready"
    assert summary["failure_row_count"] == 3
    assert summary["high_error_failure_row_count"] == 3
    assert summary["cv_regression_row_count"] == 1
    assert summary["payload_priority_matched_failure_row_count"] == 2
    assert summary["operator_receipt_blocked_payload_count"] == 3
    assert summary["operator_receipt_missing_payload_count"] == 3
    assert summary["existing_metric_source_artifact_present_without_receipt_count"] == 3
    assert summary["top_failure_target_id"] == "3n86"
    assert rows[0]["failure_class"] == "high_error_cv_regression_with_payload_review"
    assert rows[0]["operator_receipt_blocked_payload_count"] == 3
    two_j7h = next(row for row in rows if row["target_id"] == "2j7h")
    assert two_j7h["existing_metric_source_artifact_present_without_receipt_count"] == 3
    assert "operator receipt coverage" in two_j7h["next_science_step"]
    assert rows[0]["claim_promotion_allowed"] is False


def test_cv_failure_analysis_packet_cli_writes_outputs(tmp_path: Path) -> None:
    cv_json = tmp_path / "cv.json"
    priority_json = tmp_path / "priority.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(cv_json, _cv_payload())
    _write_json(priority_json, _priority_payload())

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--cv-json",
            str(cv_json),
            "--residual-priority-json",
            str(priority_json),
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
    assert payload["summary"]["failure_row_count"] == len(rows)
    assert "R9 CV Failure Analysis Packet" in out_md.read_text(encoding="utf-8")
