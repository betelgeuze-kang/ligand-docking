from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_fit_trained_calibration_probe as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_existing_csv(path: Path, root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("seed_001", "seed_a", "seed_a_1", "fit", -4.0, -7.0, 600, 12),
        ("seed_002", "seed_b", "seed_b_1", "fit", -6.5, -9.0, 1000, 20),
        ("seed_003", "seed_c", "seed_c_1", "fit", -5.0, -8.0, 800, 16),
    ]
    for work_order_id, _target, _pose, _split, _proxy, _reference, contact, atoms in rows:
        _write_json(
            root / "runs" / "sources" / f"{work_order_id}_internal_deltaG.json",
            {"details": {"contact_count": contact, "pose_atom_count": atoms, "min_distance_a": 2.6}},
        )
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
        for work_order_id, target, pose, split, proxy, reference, _contact, _atoms in rows:
            writer.writerow(
                {
                    "work_order_id": work_order_id,
                    "target_id": target,
                    "pose_id": pose,
                    "split": split,
                    "deltaG_mm_gbsa_kcal_mol": str(proxy),
                    "deltaG_experimental_kcal_mol": str(reference),
                    "internal_deltaG_source_artifact": f"runs/sources/{work_order_id}_internal_deltaG.json",
                }
            )


def _candidate_fill() -> dict:
    return {
        "candidate_pairs": [
            {
                "work_order_id": "candidate_001",
                "target_id": "cand_a",
                "pose_id": "cand_a_1",
                "split": "holdout",
                "deltaG_candidate_kcal_mol": "-3.0",
                "deltaG_experimental_kcal_mol": "-6.0",
                "candidate_status": "pass",
            },
            {
                "work_order_id": "candidate_002",
                "target_id": "cand_b",
                "pose_id": "cand_b_1",
                "split": "holdout",
                "deltaG_candidate_kcal_mol": "-8.0",
                "deltaG_experimental_kcal_mol": "-10.0",
                "candidate_status": "pass",
            },
        ],
        "rows": [
            {
                "target_id": "cand_a",
                "pose_id": "cand_a_1",
                "metric_name": "internal_deltaG",
                "candidate_status": "pass",
                "details_json": json.dumps({"contact_count": 500, "pose_atom_count": 10, "min_distance_a": 2.8}),
            },
            {
                "target_id": "cand_b",
                "pose_id": "cand_b_1",
                "metric_name": "internal_deltaG",
                "candidate_status": "pass",
                "details_json": json.dumps({"contact_count": 1300, "pose_atom_count": 20, "min_distance_a": 2.5}),
            },
        ],
    }


def test_fit_trained_calibration_probe_records_read_only_models(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    _write_json(candidate_path, _candidate_fill())
    _write_existing_csv(existing_path, tmp_path)

    payload = mod.build_refine_tier_public_benchmark_fit_trained_calibration_probe(
        candidate_fill_json=candidate_path,
        existing_materialization_csv=existing_path,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "refine_tier_public_benchmark_fit_trained_calibration_probe_ready"
    assert summary["combined_pair_count"] == 5
    assert summary["fit_pair_count"] == 3
    assert summary["holdout_pair_count"] == 2
    assert summary["feature_complete_pair_count"] == 5
    assert summary["model_candidate_count"] == len(payload["model_rows"])
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["production_score_mutation_allowed"] is False
    assert summary["best_model_id"]
    assert payload["best_model_rank_residual_rows"]
    assert all(row["diagnostic_only"] is True for row in payload["model_rows"])


def test_fit_trained_calibration_probe_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    out_json = tmp_path / "probe.json"
    out_csv = tmp_path / "probe.csv"
    out_md = tmp_path / "probe.md"
    _write_json(candidate_path, _candidate_fill())
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
    assert payload["summary"]["model_candidate_count"] == len(rows)
    assert "R9 Fit-Trained Calibration Probe" in out_md.read_text(encoding="utf-8")
