from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_statistical_support_work_order as mod


def _write_json(path: Path, summary: dict) -> None:
    path.write_text(json.dumps({"summary": summary}) + "\n", encoding="utf-8")


def _write_work_order(path: Path, row_count: int = 8) -> None:
    fieldnames = ["work_order_id", "split"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(1, row_count + 1):
            writer.writerow(
                {
                    "work_order_id": f"refine_tier_public_benchmark_seeded_{index:03d}",
                    "split": "holdout" if index > 5 else "fit",
                }
            )


def test_statistical_support_work_order_emits_minimum_expansion_slots(tmp_path: Path) -> None:
    materialization = tmp_path / "materialization.json"
    materialized_apply = tmp_path / "apply.json"
    work_order = tmp_path / "work_order.csv"
    _write_json(
        materialization,
        {
            "status": "refine_tier_public_benchmark_metric_sources_materialized",
            "free_energy_pair_count": 8,
            "free_energy_fit_pair_count": 5,
            "free_energy_holdout_pair_count": 3,
            "free_energy_spearman_bootstrap_p05": -0.14285714285714285,
            "claim_grade_public_benchmark_statistical_support_ready": False,
        },
    )
    _write_json(
        materialized_apply,
        {
            "status": "refine_tier_public_benchmark_work_order_apply_ready",
            "apply_ready": True,
        },
    )
    _write_work_order(work_order)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_work_order(
        materialization_json=materialization,
        materialized_apply_json=materialized_apply,
        work_order_csv=work_order,
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_statistical_support_work_order_ready"
    assert summary["work_order_ready"] is True
    assert summary["claim_grade_public_benchmark_statistical_support_ready"] is False
    assert summary["canonical_intake_promotion_allowed"] is False
    assert summary["observed_public_benchmark_pair_count"] == 8
    assert summary["observed_holdout_pair_count"] == 3
    assert summary["minimum_new_pair_count"] == 17
    assert summary["minimum_new_holdout_pair_count"] == 5
    assert summary["minimum_new_fit_or_holdout_pair_count"] == 12
    assert summary["expansion_slot_count"] == 17
    assert summary["holdout_expansion_slot_count"] == 5
    assert summary["fit_or_holdout_expansion_slot_count"] == 12
    assert summary["bootstrap_retest_required"] is True
    assert summary["blockers"] == [
        "claim_grade_public_benchmark_pair_count_below_minimum",
        "claim_grade_public_benchmark_holdout_pair_count_below_minimum",
        "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
    ]
    assert len(payload["rows"]) == 17
    assert [row["required_split"] for row in payload["rows"][:5]] == ["holdout"] * 5
    assert all(row["canonical_intake_promotion_allowed"] is False for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_statistical_support_work_order_allows_review_when_gap_is_closed(tmp_path: Path) -> None:
    materialization = tmp_path / "materialization.json"
    materialized_apply = tmp_path / "apply.json"
    work_order = tmp_path / "work_order.csv"
    _write_json(
        materialization,
        {
            "status": "refine_tier_public_benchmark_metric_sources_materialized",
            "free_energy_pair_count": 25,
            "free_energy_fit_pair_count": 17,
            "free_energy_holdout_pair_count": 8,
            "free_energy_spearman_bootstrap_p05": 0.61,
            "claim_grade_public_benchmark_statistical_support_ready": True,
        },
    )
    _write_json(
        materialized_apply,
        {
            "status": "refine_tier_public_benchmark_work_order_apply_ready",
            "apply_ready": True,
        },
    )
    _write_work_order(work_order, row_count=25)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_work_order(
        materialization_json=materialization,
        materialized_apply_json=materialized_apply,
        work_order_csv=work_order,
    )
    summary = payload["summary"]

    assert summary["work_order_ready"] is True
    assert summary["claim_grade_public_benchmark_statistical_support_ready"] is True
    assert summary["canonical_intake_promotion_allowed"] is True
    assert summary["minimum_new_pair_count"] == 0
    assert summary["minimum_new_holdout_pair_count"] == 0
    assert summary["expansion_slot_count"] == 0
    assert summary["blocker_count"] == 0
    assert payload["rows"] == []


def test_statistical_support_work_order_cli_writes_outputs(tmp_path: Path) -> None:
    materialization = tmp_path / "materialization.json"
    materialized_apply = tmp_path / "apply.json"
    work_order = tmp_path / "work_order.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(
        materialization,
        {
            "free_energy_pair_count": 8,
            "free_energy_fit_pair_count": 5,
            "free_energy_holdout_pair_count": 3,
            "free_energy_spearman_bootstrap_p05": -0.14285714285714285,
            "claim_grade_public_benchmark_statistical_support_ready": False,
        },
    )
    _write_json(
        materialized_apply,
        {
            "status": "refine_tier_public_benchmark_work_order_apply_ready",
            "apply_ready": True,
        },
    )
    _write_work_order(work_order)

    mod.main(
        [
            "--materialization-json",
            str(materialization),
            "--materialized-apply-json",
            str(materialized_apply),
            "--work-order-csv",
            str(work_order),
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
    assert payload["summary"]["expansion_slot_count"] == 17
    assert len(rows) == 17
    assert "Statistical Support Work Order" in out_md.read_text(encoding="utf-8")
