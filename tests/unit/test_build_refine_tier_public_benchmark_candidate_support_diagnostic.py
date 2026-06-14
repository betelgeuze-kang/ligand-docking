from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_candidate_support_diagnostic as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_existing_csv(path: Path) -> None:
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
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "work_order_id": "seed_001",
                "target_id": "seed_a",
                "pose_id": "seed_a_1",
                "split": "fit",
                "deltaG_mm_gbsa_kcal_mol": "-9.0",
                "deltaG_experimental_kcal_mol": "-9.2",
            }
        )
        writer.writerow(
            {
                "work_order_id": "seed_002",
                "target_id": "seed_b",
                "pose_id": "seed_b_1",
                "split": "holdout",
                "deltaG_mm_gbsa_kcal_mol": "-4.0",
                "deltaG_experimental_kcal_mol": "-6.0",
            }
        )


def test_candidate_support_diagnostic_records_rank_sensitivity(tmp_path: Path) -> None:
    candidate_fill = {
        "summary": {"status": "refine_tier_public_benchmark_statistical_support_metric_candidates_ready"},
        "candidate_pairs": [
            {
                "work_order_id": "candidate_001",
                "target_id": "cand_a",
                "pose_id": "cand_a_1",
                "split": "fit",
                "deltaG_candidate_kcal_mol": "-8.0",
                "deltaG_experimental_kcal_mol": "-8.3",
                "candidate_status": "pass",
            },
            {
                "work_order_id": "candidate_002",
                "target_id": "cand_b",
                "pose_id": "cand_b_1",
                "split": "holdout",
                "deltaG_candidate_kcal_mol": "-2.0",
                "deltaG_experimental_kcal_mol": "-10.0",
                "candidate_status": "pass",
            },
        ],
    }
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    _write_json(candidate_path, candidate_fill)
    _write_existing_csv(existing_path)

    payload = mod.build_refine_tier_public_benchmark_candidate_support_diagnostic(
        candidate_fill_json=candidate_path,
        existing_materialization_csv=existing_path,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "refine_tier_public_benchmark_candidate_support_diagnostic_ready"
    assert summary["combined_pair_count"] == 4
    assert summary["existing_pair_count"] == 2
    assert summary["candidate_pair_count"] == 2
    assert summary["diagnostic_policy"] == (
        "leave_one_out_is_sensitivity_only_do_not_drop_pairs_without_independent_scientific_review"
    )
    assert summary["external_state_mutated"] is False
    assert payload["top_leave_one_out_rows"]
    assert payload["top_rank_residual_rows"][0]["rank_abs_error"] >= 1


def test_candidate_support_diagnostic_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    out_json = tmp_path / "diag.json"
    out_csv = tmp_path / "diag.csv"
    out_md = tmp_path / "diag.md"
    _write_json(
        candidate_path,
        {
            "candidate_pairs": [
                {
                    "work_order_id": "candidate_001",
                    "target_id": "cand_a",
                    "pose_id": "cand_a_1",
                    "split": "fit",
                    "deltaG_candidate_kcal_mol": "-8.0",
                    "deltaG_experimental_kcal_mol": "-8.3",
                    "candidate_status": "pass",
                }
            ]
        },
    )
    _write_existing_csv(existing_path)

    mod.main(
        [
            "--candidate-fill-json",
            str(candidate_path),
            "--existing-materialization-csv",
            str(existing_path),
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
    assert payload["summary"]["combined_pair_count"] == 3
    assert rows
    assert "R9 Candidate Support Diagnostic" in out_md.read_text(encoding="utf-8")
