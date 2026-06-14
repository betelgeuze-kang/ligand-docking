from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_score_variant_probe as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_existing_csv(path: Path, root: Path) -> None:
    source = root / "runs" / "sources" / "seed_internal_deltaG.json"
    _write_json(
        source,
        {
            "details": {
                "contact_count": 900,
                "ligand_contact_atom_count": 10,
                "pose_atom_count": 10,
                "min_distance_a": 2.5,
            }
        },
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
                "target_id": "seed_a",
                "pose_id": "seed_a_1",
                "split": "fit",
                "deltaG_mm_gbsa_kcal_mol": "-4.0",
                "deltaG_experimental_kcal_mol": "-8.0",
                "internal_deltaG_source_artifact": "runs/sources/seed_internal_deltaG.json",
            }
        )


def test_score_variant_probe_records_diagnostic_variants(tmp_path: Path) -> None:
    candidate_fill = {
        "candidate_pairs": [
            {
                "work_order_id": "candidate_001",
                "target_id": "small_dense",
                "pose_id": "small_dense_1",
                "split": "holdout",
                "deltaG_candidate_kcal_mol": "-2.0",
                "deltaG_experimental_kcal_mol": "-10.0",
                "candidate_status": "pass",
            },
            {
                "work_order_id": "candidate_002",
                "target_id": "large_weaker",
                "pose_id": "large_weaker_1",
                "split": "fit",
                "deltaG_candidate_kcal_mol": "-8.0",
                "deltaG_experimental_kcal_mol": "-6.0",
                "candidate_status": "pass",
            },
        ],
        "rows": [
            {
                "target_id": "small_dense",
                "pose_id": "small_dense_1",
                "metric_name": "internal_deltaG",
                "candidate_status": "pass",
                "details_json": json.dumps(
                    {
                        "contact_count": 1000,
                        "ligand_contact_atom_count": 9,
                        "pose_atom_count": 9,
                        "min_distance_a": 2.7,
                    }
                ),
            },
            {
                "target_id": "large_weaker",
                "pose_id": "large_weaker_1",
                "metric_name": "internal_deltaG",
                "candidate_status": "pass",
                "details_json": json.dumps(
                    {
                        "contact_count": 1400,
                        "ligand_contact_atom_count": 24,
                        "pose_atom_count": 24,
                        "min_distance_a": 2.8,
                    }
                ),
            },
        ],
    }
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    _write_json(candidate_path, candidate_fill)
    _write_existing_csv(existing_path, tmp_path)

    payload = mod.build_refine_tier_public_benchmark_score_variant_probe(
        candidate_fill_json=candidate_path,
        existing_materialization_csv=existing_path,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "refine_tier_public_benchmark_score_variant_probe_ready"
    assert summary["combined_pair_count"] == 3
    assert summary["candidate_detail_pair_count"] == 2
    assert summary["candidate_detail_from_rows_pair_count"] == 2
    assert summary["candidate_detail_missing_pair_count"] == 0
    assert summary["feature_complete_pair_count"] == 3
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["best_variant_selection_policy"] == (
        "diagnostic_grid_requires_combined_spearman_not_below_baseline_and_independent_validation_before_score_use"
    )
    assert "top_p05_variant_id" in summary
    assert any(row["variant_id"] == "baseline_proxy" for row in payload["variant_rows"])
    assert payload["best_variant_rank_residual_rows"]


def test_science_admissible_selection_rejects_spearman_regression() -> None:
    assert not mod._science_admissible_for_best_selection(
        {"combined_spearman": -0.2, "free_energy_spearman_bootstrap_p05": 0.9}, 0.4
    )
    assert mod._science_admissible_for_best_selection(
        {"combined_spearman": 0.4, "free_energy_spearman_bootstrap_p05": 0.2}, 0.4
    )


def test_score_variant_probe_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    out_json = tmp_path / "probe.json"
    out_csv = tmp_path / "probe.csv"
    out_md = tmp_path / "probe.md"
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
                    "details_json": json.dumps({"contact_count": 800, "pose_atom_count": 16}),
                }
            ]
        },
    )
    _write_existing_csv(existing_path, tmp_path)

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
    assert payload["summary"]["variant_count"] == len(rows)
    assert "R9 Score Variant Probe" in out_md.read_text(encoding="utf-8")
