from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_cv_feature_extrapolation_probe as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _candidate_pair(target: str, pose: str, *, contact_per_atom: float, pose_atoms: int, reference: float) -> dict:
    return {
        "candidate_status": "pass",
        "target_id": target,
        "pose_id": pose,
        "work_order_id": f"wo_{target}",
        "split": "fit",
        "candidate_refine_proxy_score": "-5.0",
        "deltaG_experimental_kcal_mol": str(reference),
        "details_json": json.dumps(
            {
                "contact_count": contact_per_atom * pose_atoms,
                "ligand_contact_atom_count": pose_atoms,
                "pose_atom_count": pose_atoms,
                "min_distance_a": 3.0,
            }
        ),
    }


def _candidate_payload() -> dict:
    return {
        "summary": {"status": "ready"},
        "candidate_pairs": [
            _candidate_pair("in", "in_1", contact_per_atom=1.0, pose_atoms=10, reference=-7.0),
            _candidate_pair("out", "out_1", contact_per_atom=10.0, pose_atoms=10, reference=-8.0),
            _candidate_pair("mid1", "mid1_1", contact_per_atom=1.1, pose_atoms=11, reference=-6.0),
            _candidate_pair("mid2", "mid2_1", contact_per_atom=0.9, pose_atoms=9, reference=-5.0),
        ],
        "rows": [],
    }


def _cv_payload() -> dict:
    return {
        "summary": {
            "locked_cv_model_id": "density_size_ridge_l0.1",
            "locked_cv_bootstrap_p05": 0.4,
        },
        "cv_model_rows": [
            {
                "model_id": "density_size_ridge_l0.1",
                "feature_names": "contact_per_atom;pose_atom_count",
            }
        ],
        "baseline_rank_residual_rows": [
            {"target_id": "in", "pose_id": "in_1", "rank_abs_error": 10},
            {"target_id": "out", "pose_id": "out_1", "rank_abs_error": 9},
            {"target_id": "mid1", "pose_id": "mid1_1", "rank_abs_error": 1},
            {"target_id": "mid2", "pose_id": "mid2_1", "rank_abs_error": 1},
        ],
        "locked_cv_rank_residual_rows": [
            {
                "target_id": "in",
                "pose_id": "in_1",
                "split": "fit",
                "source": "candidate_fill_preview",
                "baseline_proxy": "-5.0",
                "variant_proxy": "-6.0",
                "reference": "-7.0",
                "variant_rank": 1,
                "reference_rank": 13,
                "rank_abs_error": 12,
            },
            {
                "target_id": "out",
                "pose_id": "out_1",
                "split": "fit",
                "source": "candidate_fill_preview",
                "baseline_proxy": "-5.0",
                "variant_proxy": "-8.0",
                "reference": "-8.0",
                "variant_rank": 1,
                "reference_rank": 12,
                "rank_abs_error": 11,
            },
            {
                "target_id": "mid1",
                "pose_id": "mid1_1",
                "split": "fit",
                "source": "candidate_fill_preview",
                "baseline_proxy": "-5.0",
                "variant_proxy": "-5.5",
                "reference": "-6.0",
                "variant_rank": 2,
                "reference_rank": 3,
                "rank_abs_error": 1,
            },
        ],
    }


def _priority_payload() -> dict:
    return {
        "priority_rows": [
            {
                "target_id": "in",
                "pose_id": "in_1",
                "metric_name": "dockq",
                "operator_gap_class": "operator_receipt_blocked_placeholders",
            },
            {
                "target_id": "out",
                "pose_id": "out_1",
                "metric_name": "internal_deltaG",
                "operator_gap_class": "existing_metric_payload_present_without_operator_receipt",
            },
        ]
    }


def test_cv_feature_extrapolation_probe_splits_feature_and_in_distribution_failures(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    cv_json = tmp_path / "cv.json"
    priority_json = tmp_path / "priority.json"
    _write_json(candidate_json, _candidate_payload())
    _write_json(cv_json, _cv_payload())
    _write_json(priority_json, _priority_payload())

    payload = mod.build_refine_tier_public_benchmark_cv_feature_extrapolation_probe(
        cross_validation_json=cv_json,
        candidate_fill_json=candidate_json,
        existing_materialization_csv=tmp_path / "missing.csv",
        residual_priority_json=priority_json,
        score_decomposition_json=tmp_path / "missing_decomposition.json",
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = payload["feature_extrapolation_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_cv_feature_extrapolation_probe_ready"
    assert summary["high_error_row_count"] == 2
    assert summary["high_error_feature_extrapolation_count"] == 1
    assert summary["high_error_in_distribution_count"] == 1
    assert summary["operator_receipt_missing_payload_count"] == 1
    by_target = {row["target_id"]: row for row in rows}
    assert by_target["out"]["feature_extrapolation_residual_class"] == "high_error_feature_extrapolation"
    assert by_target["out"]["outside_train_range_features"] == "contact_per_atom"
    assert by_target["in"]["feature_extrapolation_residual_class"] == "high_error_in_distribution"
    assert "model-form review" in by_target["in"]["next_science_step"]
    assert by_target["out"]["claim_promotion_allowed"] is False


def test_cv_feature_extrapolation_probe_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    cv_json = tmp_path / "cv.json"
    priority_json = tmp_path / "priority.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(candidate_json, _candidate_payload())
    _write_json(cv_json, _cv_payload())
    _write_json(priority_json, _priority_payload())

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--cross-validation-json",
            str(cv_json),
            "--candidate-fill-json",
            str(candidate_json),
            "--existing-materialization-csv",
            str(tmp_path / "missing.csv"),
            "--residual-priority-json",
            str(priority_json),
            "--score-decomposition-json",
            str(tmp_path / "missing_decomposition.json"),
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
    assert payload["summary"]["feature_extrapolation_probe_row_count"] == len(rows)
    assert "R9 CV Feature-Extrapolation Probe" in out_md.read_text(encoding="utf-8")
