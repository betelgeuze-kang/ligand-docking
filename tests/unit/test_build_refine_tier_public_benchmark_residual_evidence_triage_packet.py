from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_residual_evidence_triage_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _priority_payload() -> dict:
    rows = []
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=1):
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "work_order_id": "wo_3n86",
                "split": "fit",
                "metric_name": metric,
                "operator_gap_class": "operator_receipt_blocked_placeholders",
                "operator_manual_pending_field_count": "10",
                "locked_cv_rank_abs_error": "14",
                "cv_rank_error_vs_baseline": "worse",
            }
        )
    for rank, metric in enumerate(("dockq", "lddt_pli", "internal_deltaG"), start=4):
        rows.append(
            {
                "payload_priority_rank": rank,
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "work_order_id": "wo_2j7h",
                "split": "fit",
                "metric_name": metric,
                "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
                "operator_manual_pending_field_count": "0",
                "locked_cv_rank_abs_error": "13",
                "leave_one_out_leverage": "true",
                "leave_one_out_bootstrap_p05_delta": "0.08",
            }
        )
    return {
        "summary": {
            "locked_cv_model_id": "density_size_ridge_l0.1",
            "locked_cv_bootstrap_p05": 0.4,
            "locked_cv_bootstrap_p05_gap_to_claim_grade": 0.1,
        },
        "priority_rows": rows,
    }


def _feature_payload() -> dict:
    return {
        "summary": {"status": "ready"},
        "feature_extrapolation_rows": [
            {
                "target_id": "3n86",
                "pose_id": "3n86_99",
                "feature_extrapolation_residual_class": "high_error_in_distribution",
                "locked_cv_rank_abs_error": "14",
                "baseline_rank_abs_error": "13",
                "cv_rank_error_vs_baseline": "worse",
                "top_feature_shift_name": "contact_per_atom",
                "top_feature_shift_abs_z": "1.2",
            },
            {
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "feature_extrapolation_residual_class": "high_error_in_distribution",
                "locked_cv_rank_abs_error": "13",
                "baseline_rank_abs_error": "16",
            },
        ],
    }


def test_residual_evidence_triage_prioritizes_target_pose_review_lanes(tmp_path: Path) -> None:
    priority_json = tmp_path / "priority.json"
    feature_json = tmp_path / "feature.json"
    model_json = tmp_path / "model.json"
    backfill_json = tmp_path / "backfill.json"
    _write_json(priority_json, _priority_payload())
    _write_json(feature_json, _feature_payload())
    _write_json(model_json, {"summary": {"model_extension_generalization_ready": False, "best_extension_model_id": "m1"}})
    _write_json(
        backfill_json,
        {
            "backfill_template_rows": [
                {
                    "target_id": "2j7h",
                    "pose_id": "2j7h_48",
                    "metric_name": metric,
                    "payload_validation_status": "pass",
                    "input_artifact_count": 2,
                    "input_artifact_sha256_verified_count": 2,
                    "operator_manual_pending_field_count": 11,
                }
                for metric in ("dockq", "lddt_pli", "internal_deltaG")
            ]
        },
    )

    payload = mod.build_refine_tier_public_benchmark_residual_evidence_triage_packet(
        payload_priority_json=priority_json,
        feature_extrapolation_json=feature_json,
        model_extension_json=model_json,
        seeded_backfill_json=backfill_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = payload["triage_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_residual_evidence_triage_packet_ready"
    assert summary["triage_row_count"] == 2
    assert summary["in_distribution_high_error_triage_count"] == 1
    assert summary["seeded_payload_receipt_gap_triage_count"] == 1
    assert summary["seeded_backfill_template_ready_triage_count"] == 1
    assert summary["seeded_backfill_template_ready_payload_count"] == 3
    assert summary["seeded_backfill_operator_manual_pending_field_count"] == 33
    assert summary["operator_receipt_blocked_payload_count"] == 3
    assert summary["operator_receipt_missing_payload_count"] == 3
    by_target = {row["target_id"]: row for row in rows}
    assert by_target["3n86"]["next_review_lane"] == "metric_payload_pose_model_form_review"
    assert by_target["2j7h"]["next_review_lane"] == "seeded_payload_receipt_coverage_first"
    assert by_target["2j7h"]["seeded_backfill_template_ready"] is True
    assert by_target["2j7h"]["seeded_backfill_template_row_count"] == 3
    assert "generated seeded-payload backfill template" in by_target["2j7h"]["next_science_step"]
    assert by_target["3n86"]["claim_promotion_allowed"] is False


def test_residual_evidence_triage_cli_writes_outputs(tmp_path: Path) -> None:
    priority_json = tmp_path / "priority.json"
    feature_json = tmp_path / "feature.json"
    model_json = tmp_path / "model.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(priority_json, _priority_payload())
    _write_json(feature_json, _feature_payload())
    _write_json(model_json, {"summary": {}})

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--payload-priority-json",
            str(priority_json),
            "--feature-extrapolation-json",
            str(feature_json),
            "--model-extension-json",
            str(model_json),
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
    assert payload["summary"]["triage_row_count"] == len(rows)
    assert "R9 Residual Evidence Triage Packet" in out_md.read_text(encoding="utf-8")
