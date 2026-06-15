from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_residual_review_dossier as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _priority_rows(tmp_path: Path) -> list[dict]:
    ligand = tmp_path / "inputs" / "ligand.sdf"
    receptor = tmp_path / "inputs" / "receptor.pdb"
    ligand.parent.mkdir(parents=True, exist_ok=True)
    ligand.write_text("ligand\n", encoding="utf-8")
    receptor.write_text("ATOM receptor\n", encoding="utf-8")
    artifacts = "inputs/ligand.sdf;inputs/receptor.pdb"
    hashes = "a" * 64 + ";" + "b" * 64
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
                "metric_source_artifact": f"runs/{metric}.json",
                "metric_source_artifact_present": False,
                "metric_value_candidate": "1.0",
                "existing_metric_value": "",
                "operator_gap_class": "operator_receipt_blocked_placeholders",
                "operator_review_surface_ready": True,
                "required_metric_input_artifacts": artifacts,
                "required_metric_input_artifact_sha256s": hashes,
                "rank_direction": "overranked_stronger_than_reference",
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
                "metric_source_artifact": f"runs/seeded_{metric}.json",
                "metric_source_artifact_present": True,
                "metric_value_candidate": "",
                "existing_metric_value": "0.5",
                "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
                "operator_review_surface_ready": False,
                "required_metric_input_artifacts": artifacts,
                "required_metric_input_artifact_sha256s": hashes,
                "rank_direction": "underranked_weaker_than_reference",
            }
        )
    return rows


def _triage_rows() -> list[dict]:
    return [
        {
            "triage_priority_rank": 1,
            "target_id": "3n86",
            "pose_id": "3n86_99",
            "work_order_id": "wo_3n86",
            "split": "fit",
            "next_review_lane": "metric_payload_pose_model_form_review",
            "next_science_step": "review metrics",
            "feature_extrapolation_residual_class": "high_error_in_distribution",
            "feature_extrapolation": False,
            "locked_cv_rank_abs_error": "14",
            "baseline_rank_abs_error": "13",
            "cv_rank_error_vs_baseline": "worse",
            "required_metric_names": "dockq;lddt_pli;internal_deltaG",
            "operator_receipt_blocked_payload_count": 3,
            "operator_receipt_missing_payload_count": 0,
            "operator_manual_pending_field_count": 30,
        },
        {
            "triage_priority_rank": 2,
            "target_id": "2j7h",
            "pose_id": "2j7h_48",
            "work_order_id": "wo_2j7h",
            "split": "fit",
            "next_review_lane": "seeded_payload_receipt_coverage_first",
            "next_science_step": "review backfill",
            "feature_extrapolation_residual_class": "high_error_in_distribution",
            "feature_extrapolation": False,
            "locked_cv_rank_abs_error": "13",
            "baseline_rank_abs_error": "16",
            "cv_rank_error_vs_baseline": "better",
            "required_metric_names": "dockq;lddt_pli;internal_deltaG",
            "operator_receipt_blocked_payload_count": 0,
            "operator_receipt_missing_payload_count": 3,
            "operator_manual_pending_field_count": 0,
        },
    ]


def test_residual_review_dossier_groups_triage_priority_and_backfill(tmp_path: Path) -> None:
    triage_json = tmp_path / "triage.json"
    priority_json = tmp_path / "priority.json"
    feature_json = tmp_path / "feature.json"
    backfill_json = tmp_path / "backfill.json"
    _write_json(triage_json, {"triage_rows": _triage_rows()})
    _write_json(priority_json, {"priority_rows": _priority_rows(tmp_path)})
    _write_json(
        feature_json,
        {
            "feature_extrapolation_rows": [
                {
                    "target_id": "3n86",
                    "pose_id": "3n86_99",
                    "rank_direction": "overranked_stronger_than_reference",
                    "feature_diagnostics_json": json.dumps(
                        [{"feature": "contact_per_atom", "z_score": "1.2", "outside_train_range": False}]
                    ),
                },
            ]
        },
    )
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

    payload = mod.build_refine_tier_public_benchmark_residual_review_dossier(
        triage_json=triage_json,
        payload_priority_json=priority_json,
        feature_extrapolation_json=feature_json,
        seeded_backfill_json=backfill_json,
        root=tmp_path,
        top_n=2,
    )

    summary = payload["summary"]
    rows = payload["dossier_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_residual_review_dossier_ready"
    assert summary["dossier_row_count"] == 2
    assert summary["review_package_ready_count"] == 2
    assert summary["metric_payload_pose_model_review_count"] == 1
    assert summary["seeded_backfill_template_ready_review_count"] == 1
    assert summary["operator_receipt_blocked_payload_count"] == 3
    assert summary["operator_receipt_missing_payload_count"] == 3
    by_target = {row["target_id"]: row for row in rows}
    assert by_target["3n86"]["operator_review_surface_ready_payload_count"] == 3
    assert by_target["3n86"]["required_input_artifact_present_count"] == 2
    assert "contact_per_atom" in by_target["3n86"]["feature_diagnostics_brief"]
    assert by_target["2j7h"]["seeded_backfill_template_ready"] is True
    assert by_target["2j7h"]["seeded_backfill_operator_manual_pending_field_count"] == 33
    assert "generated seeded-payload backfill" in by_target["2j7h"]["next_reviewer_action"]
    assert by_target["2j7h"]["claim_promotion_allowed"] is False


def test_residual_review_dossier_cli_writes_outputs(tmp_path: Path) -> None:
    triage_json = tmp_path / "triage.json"
    priority_json = tmp_path / "priority.json"
    feature_json = tmp_path / "feature.json"
    backfill_json = tmp_path / "backfill.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(triage_json, {"triage_rows": _triage_rows()})
    _write_json(priority_json, {"priority_rows": _priority_rows(tmp_path)})
    _write_json(feature_json, {"feature_extrapolation_rows": []})
    _write_json(backfill_json, {"backfill_template_rows": []})

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--triage-json",
            str(triage_json),
            "--payload-priority-json",
            str(priority_json),
            "--feature-extrapolation-json",
            str(feature_json),
            "--seeded-backfill-json",
            str(backfill_json),
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
    assert payload["summary"]["dossier_row_count"] == len(rows)
    assert "R9 Residual Review Dossier" in out_md.read_text(encoding="utf-8")
