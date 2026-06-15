from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_cv_model_extension_probe as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _candidate_pair(index: int, contact: float, atoms: int, reference: float) -> dict:
    return {
        "candidate_status": "pass",
        "target_id": f"t{index}",
        "pose_id": f"t{index}_pose",
        "work_order_id": f"wo_{index}",
        "split": "holdout" if index in {1, 2} else "fit",
        "deltaG_candidate_kcal_mol": str(-contact),
        "deltaG_experimental_kcal_mol": str(reference),
        "details_json": json.dumps(
            {
                "contact_count": contact * atoms,
                "ligand_contact_atom_count": atoms,
                "pose_atom_count": atoms,
                "min_distance_a": 3.0,
            }
        ),
    }


def _candidate_payload() -> dict:
    return {
        "candidate_pairs": [
            _candidate_pair(1, 1.0, 8, -4.0),
            _candidate_pair(2, 1.5, 9, -5.0),
            _candidate_pair(3, 2.0, 10, -7.0),
            _candidate_pair(4, 2.5, 11, -9.0),
            _candidate_pair(5, 3.0, 12, -12.0),
        ],
        "rows": [],
    }


def _cv_payload() -> dict:
    return {
        "summary": {
            "locked_cv_model_id": "density_size_ridge_l0.1",
            "locked_cv_bootstrap_p05": 0.1,
            "locked_cv_holdout_spearman": 0.2,
            "locked_cv_combined_spearman": 0.3,
        }
    }


def test_cv_model_extension_probe_evaluates_predeclared_extensions(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    cv_json = tmp_path / "cv.json"
    feature_json = tmp_path / "feature.json"
    _write_json(candidate_json, _candidate_payload())
    _write_json(cv_json, _cv_payload())
    _write_json(feature_json, {"summary": {"high_error_feature_extrapolation_count": 1, "high_error_in_distribution_count": 2}})

    payload = mod.build_refine_tier_public_benchmark_cv_model_extension_probe(
        candidate_fill_json=candidate_json,
        existing_materialization_csv=tmp_path / "missing.csv",
        cross_validation_json=cv_json,
        feature_extrapolation_json=feature_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "refine_tier_public_benchmark_cv_model_extension_probe_ready"
    assert summary["extension_model_candidate_count"] == len(mod.MODEL_EXTENSION_SPECS) * 5
    assert summary["best_extension_model_id"]
    assert summary["feature_extrapolation_high_error_count"] == 1
    assert summary["in_distribution_high_error_count"] == 2
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert payload["best_extension_rank_residual_rows"]


def test_cv_model_extension_probe_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    cv_json = tmp_path / "cv.json"
    feature_json = tmp_path / "feature.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(candidate_json, _candidate_payload())
    _write_json(cv_json, _cv_payload())
    _write_json(feature_json, {"summary": {}})

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--candidate-fill-json",
            str(candidate_json),
            "--existing-materialization-csv",
            str(tmp_path / "missing.csv"),
            "--cross-validation-json",
            str(cv_json),
            "--feature-extrapolation-json",
            str(feature_json),
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
    assert payload["summary"]["extension_model_candidate_count"] == len(rows)
    assert "R9 CV Model-Extension Probe" in out_md.read_text(encoding="utf-8")
