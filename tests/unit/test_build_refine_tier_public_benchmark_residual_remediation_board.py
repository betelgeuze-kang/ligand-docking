from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_residual_remediation_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_existing_csv(path: Path, root: Path) -> None:
    source_path = root / "runs" / "sources" / "seed_001_internal_deltaG.json"
    _write_json(
        source_path,
        {"details": {"contact_count": 600, "pose_atom_count": 12, "min_distance_a": 2.5}},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "work_order_id",
                "target_id",
                "pose_id",
                "split",
                "deltaG_mm_gbsa_kcal_mol",
                "deltaG_experimental_kcal_mol",
                "internal_deltaG_source_artifact",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "work_order_id": "seed_001",
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "split": "fit",
                "deltaG_mm_gbsa_kcal_mol": "-2.0",
                "deltaG_experimental_kcal_mol": "-9.0",
                "internal_deltaG_source_artifact": "runs/sources/seed_001_internal_deltaG.json",
            }
        )


def _write_leave_one_out_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "removed_source",
                "removed_work_order_id",
                "removed_target_id",
                "removed_pose_id",
                "removed_split",
                "removed_proxy",
                "removed_reference",
                "spearman_without_pair",
                "bootstrap_p05_without_pair",
                "bootstrap_p05_delta",
                "claim_grade_p05_without_pair",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "removed_source": "existing_materialized",
                "removed_work_order_id": "seed_001",
                "removed_target_id": "2j7h",
                "removed_pose_id": "2j7h_48",
                "removed_split": "fit",
                "removed_proxy": "-2.0",
                "removed_reference": "-9.0",
                "spearman_without_pair": "0.70",
                "bootstrap_p05_without_pair": "0.35",
                "bootstrap_p05_delta": "0.12",
                "claim_grade_p05_without_pair": "False",
            }
        )


def _cross_validation_payload() -> dict:
    return {
        "summary": {
            "locked_cv_model_id": "density_size_ridge_l0.1",
            "locked_cv_bootstrap_p05": 0.403,
            "locked_cv_holdout_spearman": 0.59,
            "baseline_holdout_spearman": 0.64,
        },
        "locked_cv_rank_residual_rows": [
            {
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "source": "existing_materialized",
                "split": "fit",
                "baseline_proxy": "-2.0",
                "variant_proxy": "-5.0",
                "reference": "-9.0",
                "variant_rank": 20,
                "reference_rank": 2,
                "rank_abs_error": 18,
                "contact_per_atom": "50",
                "pose_atom_count": "12",
            },
            {
                "target_id": "3f3e",
                "pose_id": "3f3e_197",
                "source": "candidate_fill_preview",
                "split": "holdout",
                "baseline_proxy": "-2.5",
                "variant_proxy": "-3.0",
                "reference": "-10.0",
                "variant_rank": 12,
                "reference_rank": 4,
                "rank_abs_error": 8,
                "contact_per_atom": "35",
                "pose_atom_count": "20",
            },
        ],
        "baseline_rank_residual_rows": [
            {
                "target_id": "2j7h",
                "pose_id": "2j7h_48",
                "source": "existing_materialized",
                "split": "fit",
                "variant_rank": 15,
                "reference_rank": 2,
                "rank_abs_error": 13,
            },
            {
                "target_id": "3f3e",
                "pose_id": "3f3e_197",
                "source": "candidate_fill_preview",
                "split": "holdout",
                "variant_rank": 14,
                "reference_rank": 4,
                "rank_abs_error": 10,
            },
        ],
    }


def test_residual_remediation_board_prioritizes_leveraged_residual(tmp_path: Path) -> None:
    cv_json = tmp_path / "cv.json"
    loo_csv = tmp_path / "leave_one_out.csv"
    existing_csv = tmp_path / "existing.csv"
    candidate_json = tmp_path / "candidate.json"
    _write_json(cv_json, _cross_validation_payload())
    _write_leave_one_out_csv(loo_csv)
    _write_existing_csv(existing_csv, tmp_path)
    _write_json(candidate_json, {"candidate_pairs": [], "rows": []})

    payload = mod.build_refine_tier_public_benchmark_residual_remediation_board(
        cross_validation_json=cv_json,
        leave_one_out_csv=loo_csv,
        candidate_fill_json=candidate_json,
        existing_materialization_csv=existing_csv,
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = payload["remediation_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_residual_remediation_board_ready"
    assert summary["locked_cv_model_id"] == "density_size_ridge_l0.1"
    assert summary["claim_promotion_allowed"] is False
    assert summary["production_score_mutation_allowed"] is False
    assert rows[0]["target_id"] == "2j7h"
    assert rows[0]["leave_one_out_leverage"] is True
    assert rows[0]["cv_rank_error_vs_baseline"] == "worse"
    assert rows[0]["primary_action"] == "priority_metric_payload_and_pose_assignment_review"
    assert "seed_001_dockq.json" in rows[0]["required_reviewed_metric_payloads"]


def test_residual_remediation_board_cli_writes_outputs(tmp_path: Path) -> None:
    cv_json = tmp_path / "cv.json"
    loo_csv = tmp_path / "leave_one_out.csv"
    existing_csv = tmp_path / "existing.csv"
    candidate_json = tmp_path / "candidate.json"
    out_json = tmp_path / "board.json"
    out_csv = tmp_path / "board.csv"
    out_md = tmp_path / "board.md"
    _write_json(cv_json, _cross_validation_payload())
    _write_leave_one_out_csv(loo_csv)
    _write_existing_csv(existing_csv, tmp_path)
    _write_json(candidate_json, {"candidate_pairs": [], "rows": []})

    mod.main(
        [
            "--cross-validation-json",
            str(cv_json),
            "--leave-one-out-csv",
            str(loo_csv),
            "--candidate-fill-json",
            str(candidate_json),
            "--existing-materialization-csv",
            str(existing_csv),
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
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["remediation_action_row_count"] == len(rows)
    assert "R9 Residual Remediation Board" in out_md.read_text(encoding="utf-8")
