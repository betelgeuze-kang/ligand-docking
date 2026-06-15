from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_bootstrap_recovery_queue as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_existing_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "work_order_id": "seed_001",
            "target_id": "a",
            "pose_id": "a_1",
            "split": "fit",
            "metric_materialization_status": "pass",
            "deltaG_mm_gbsa_kcal_mol": "-1",
            "deltaG_experimental_kcal_mol": "-1",
            "dockq": "0.7",
            "lddt_pli": "1.0",
        },
        {
            "work_order_id": "seed_002",
            "target_id": "b",
            "pose_id": "b_1",
            "split": "holdout",
            "metric_materialization_status": "pass",
            "deltaG_mm_gbsa_kcal_mol": "-2",
            "deltaG_experimental_kcal_mol": "-2",
            "dockq": "0.7",
            "lddt_pli": "1.0",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _candidate_payload() -> dict:
    return {
        "summary": {
            "bootstrap_iteration_count": 30,
            "bootstrap_seed": 7,
        },
        "candidate_pairs": [
            {
                "work_order_id": "cand_001",
                "target_id": "c",
                "pose_id": "c_1",
                "split": "fit",
                "candidate_status": "pass",
                "deltaG_candidate_kcal_mol": "-3",
                "deltaG_experimental_kcal_mol": "-3",
                "dockq": "0.7",
                "lddt_pli": "1.0",
            },
            {
                "work_order_id": "cand_002",
                "target_id": "outlier",
                "pose_id": "outlier_1",
                "split": "holdout",
                "candidate_status": "pass",
                "deltaG_candidate_kcal_mol": "-4",
                "deltaG_experimental_kcal_mol": "1",
                "dockq": "0.7",
                "lddt_pli": "1.0",
            },
        ],
    }


def test_bootstrap_recovery_queue_prioritizes_leave_one_out_p05_driver(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    existing_csv = tmp_path / "existing.csv"
    gap_json = tmp_path / "gap.json"
    _write_json(candidate_json, _candidate_payload())
    _write_existing_csv(existing_csv)
    _write_json(gap_json, {"summary": {"top_statistical_gap_id": "claim_grade_public_benchmark_bootstrap_spearman_p05"}})

    payload = mod.build_refine_tier_public_benchmark_bootstrap_recovery_queue(
        candidate_fill_json=candidate_json,
        existing_materialization_csv=existing_csv,
        gap_audit_json=gap_json,
        root=tmp_path,
        iterations=30,
        seed=7,
    )

    summary = payload["summary"]
    rows = payload["recovery_rows"]
    assert summary["status"] == "refine_tier_public_benchmark_bootstrap_recovery_queue_ready"
    assert summary["queue_row_count"] == 4
    assert summary["existing_materialized_pair_count"] == 2
    assert summary["candidate_fill_pair_count"] == 2
    assert summary["leave_one_out_improves_p05_count"] >= 1
    assert rows[0]["target_id"] == "outlier"
    assert float(rows[0]["bootstrap_p05_delta_if_removed"]) > 0
    assert rows[0]["claim_promotion_allowed"] is False


def test_bootstrap_recovery_queue_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    existing_csv = tmp_path / "existing.csv"
    gap_json = tmp_path / "gap.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(candidate_json, _candidate_payload())
    _write_existing_csv(existing_csv)
    _write_json(gap_json, {"summary": {}})

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--candidate-fill-json",
            str(candidate_json),
            "--existing-materialization-csv",
            str(existing_csv),
            "--gap-audit-json",
            str(gap_json),
            "--iterations",
            "30",
            "--seed",
            "7",
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
    assert payload["summary"]["queue_row_count"] == len(rows)
    assert "R9 Bootstrap Recovery Queue" in out_md.read_text(encoding="utf-8")
