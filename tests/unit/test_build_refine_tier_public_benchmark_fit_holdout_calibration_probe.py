from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_fit_holdout_calibration_probe as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_existing_csv(path: Path, root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source_a = root / "runs" / "sources" / "seed_a_internal_deltaG.json"
    source_b = root / "runs" / "sources" / "seed_b_internal_deltaG.json"
    _write_json(source_a, {"details": {"contact_count": 600, "pose_atom_count": 12}})
    _write_json(source_b, {"details": {"contact_count": 1200, "pose_atom_count": 20}})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "work_order_id",
                "target_id",
                "pose_id",
                "split",
                "internal_refine_proxy_score",
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
                "internal_refine_proxy_score": "-4.0",
                "deltaG_experimental_kcal_mol": "-7.0",
                "internal_deltaG_source_artifact": "runs/sources/seed_a_internal_deltaG.json",
            }
        )
        writer.writerow(
            {
                "work_order_id": "seed_002",
                "target_id": "seed_b",
                "pose_id": "seed_b_1",
                "split": "fit",
                "internal_refine_proxy_score": "-7.0",
                "deltaG_experimental_kcal_mol": "-9.0",
                "internal_deltaG_source_artifact": "runs/sources/seed_b_internal_deltaG.json",
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
                "candidate_refine_proxy_score": "-3.0",
                "deltaG_experimental_kcal_mol": "-6.0",
                "candidate_status": "pass",
            },
            {
                "work_order_id": "candidate_002",
                "target_id": "cand_b",
                "pose_id": "cand_b_1",
                "split": "holdout",
                "candidate_refine_proxy_score": "-8.0",
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
                "details_json": json.dumps({"contact_count": 500, "pose_atom_count": 10}),
            },
            {
                "target_id": "cand_b",
                "pose_id": "cand_b_1",
                "metric_name": "internal_deltaG",
                "candidate_status": "pass",
                "details_json": json.dumps({"contact_count": 1400, "pose_atom_count": 20}),
            },
        ],
    }


def test_fit_holdout_calibration_probe_records_guarded_selection(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    existing_path = tmp_path / "existing.csv"
    _write_json(candidate_path, _candidate_fill())
    _write_existing_csv(existing_path, tmp_path)

    payload = mod.build_refine_tier_public_benchmark_fit_holdout_calibration_probe(
        candidate_fill_json=candidate_path,
        existing_materialization_csv=existing_path,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "refine_tier_public_benchmark_fit_holdout_calibration_probe_ready"
    assert summary["combined_pair_count"] == 4
    assert summary["fit_pair_count"] == 2
    assert summary["holdout_pair_count"] == 2
    assert summary["feature_complete_pair_count"] == 4
    assert summary["candidate_detail_from_rows_pair_count"] == 2
    assert summary["payload_write_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["production_score_mutation_allowed"] is False
    assert summary["fit_selected_variant_id"]
    assert summary["holdout_guarded_variant_id"]
    assert payload["calibration_rows"]
    assert payload["holdout_guarded_rank_residual_rows"]


def test_fit_holdout_calibration_probe_cli_writes_outputs(tmp_path: Path) -> None:
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
    assert payload["summary"]["variant_count"] == len(rows)
    assert "R9 Fit/Holdout Calibration Probe" in out_md.read_text(encoding="utf-8")
