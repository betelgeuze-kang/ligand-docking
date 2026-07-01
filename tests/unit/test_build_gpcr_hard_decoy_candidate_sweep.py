from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_candidate_sweep as mod


def _write_summary(path: Path, *, ci_low: float = 0.76, top20: float = 1.0) -> None:
    path.write_text(
        json.dumps(
            {
                "lower_better": True,
                "metrics_ci_unique": {"pr_auc": {"low": ci_low}},
                "topk_unique": [{"k": 20, "hit_rate": top20}],
            }
        ),
        encoding="utf-8",
    )


def _write_candidate(path: Path, *, drd2_green: bool) -> None:
    rows = [
        {
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": "DRD2_POS",
            "is_binder": "1",
            "score_value": "-10",
            "mean_min_distance_A": "5.0",
        },
        {
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": "DRD2_DECOY",
            "is_binder": "0",
            "score_value": "-9",
            "mean_min_distance_A": "5.2" if drd2_green else "4.8",
        },
        {
            "target": "CHEMBL224_HTR2A_HUMAN",
            "ligand_id": "HTR2A_POS",
            "is_binder": "1",
            "score_value": "-10",
            "mean_min_distance_A": "4.0",
        },
        {
            "target": "CHEMBL224_HTR2A_HUMAN",
            "ligand_id": "HTR2A_DECOY",
            "is_binder": "0",
            "score_value": "-9",
            "mean_min_distance_A": "4.5",
        },
        {
            "target": "CHEMBL233_OPRM1_HUMAN",
            "ligand_id": "OPRM1_POS",
            "is_binder": "1",
            "score_value": "-10",
            "mean_min_distance_A": "4.0",
        },
        {
            "target": "CHEMBL233_OPRM1_HUMAN",
            "ligand_id": "OPRM1_DECOY",
            "is_binder": "0",
            "score_value": "-9",
            "mean_min_distance_A": "4.1",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["target", "ligand_id", "is_binder", "score_value", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_candidate_sweep_finds_actual_closure_candidate(tmp_path: Path) -> None:
    candidate = tmp_path / "gpcr_demo_ranking_unique_top_rank_retained_top50_current.csv"
    summary = tmp_path / "gpcr_demo_ranking_summary_current.json"
    _write_candidate(candidate, drd2_green=True)
    _write_summary(summary)

    payload = mod.build_gpcr_hard_decoy_candidate_sweep(candidate_glob=str(tmp_path / "*top_rank_retained_top50_current.csv"))

    assert payload["summary"]["status"] == "gpcr_hard_decoy_candidate_sweep_closure_candidate_ready"
    assert payload["summary"]["gpcr_actual_closure_ready"] is True
    assert payload["summary"]["closure_candidate_count"] == 1
    candidate_payload = payload["candidates"][0]
    assert candidate_payload["metric_gate_ready"] is True
    assert candidate_payload["target_green_count"] == 3


def test_candidate_sweep_blocks_when_best_candidate_still_out_anchors(tmp_path: Path) -> None:
    candidate = tmp_path / "gpcr_demo_ranking_unique_top_rank_retained_top50_current.csv"
    summary = tmp_path / "gpcr_demo_ranking_summary_current.json"
    _write_candidate(candidate, drd2_green=False)
    _write_summary(summary)

    payload = mod.build_gpcr_hard_decoy_candidate_sweep(candidate_glob=str(tmp_path / "*top_rank_retained_top50_current.csv"))

    assert payload["summary"]["status"] == "blocked_gpcr_hard_decoy_candidate_sweep_no_closure_candidate"
    assert payload["summary"]["gpcr_actual_closure_ready"] is False
    assert payload["summary"]["best_candidate_target_green_count"] == 2
    drd2 = next(row for row in payload["candidates"][0]["targets"] if row["target_id"] == "DRD2")
    assert "decoy_over_anchored_vs_positive" in drd2["blockers"]


def test_main_writes_candidate_sweep_artifacts(tmp_path: Path) -> None:
    candidate = tmp_path / "gpcr_demo_ranking_unique_top_rank_retained_top50_current.csv"
    summary = tmp_path / "gpcr_demo_ranking_summary_current.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_candidate(candidate, drd2_green=False)
    _write_summary(summary)

    rc = mod.main(
        [
            "--candidate-glob",
            str(tmp_path / "*top_rank_retained_top50_current.csv"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["closure_candidate_count"] == 0
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Candidate Sweep")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["target_id"] for row in rows] == ["DRD2", "HTR2A", "OPRM1"]
