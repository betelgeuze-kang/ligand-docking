from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_suite_current_input as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ranking_summary(unique_csv: str = "") -> dict[str, object]:
    return {
        "lower_better": True,
        "score_col": "score",
        "metrics_unique": {"pr_auc": 0.52},
        "metrics_ci_unique": {"pr_auc": {"low": 0.46}},
        "topk_unique": [{"k": 20, "hit_rate": 0.25}],
        "artifacts": {"unique_csv": unique_csv},
    }


def _hard_decoy_summary() -> dict[str, object]:
    return {
        "target_hard_decoy_stats": [
            {"target": "CHEMBL217_DRD2_HUMAN", "binders": 4},
            {"target": "CHEMBL224_HTR2A_HUMAN", "binders": 4},
            {"target": "CHEMBL233_OPRM1_HUMAN", "binders": 4},
        ]
    }


def _write_rows_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["target", "ligand_id", "score", "is_binder", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": "decoy-a",
                    "score": "1.0",
                    "is_binder": "0",
                    "mean_min_distance_A": "2.5",
                },
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": "positive-a",
                    "score": "2.0",
                    "is_binder": "1",
                    "mean_min_distance_A": "3.2",
                },
                {
                    "target": "CHEMBL224_HTR2A_HUMAN",
                    "ligand_id": "positive-b",
                    "score": "0.5",
                    "is_binder": "1",
                    "mean_min_distance_A": "3.0",
                },
                {
                    "target": "CHEMBL224_HTR2A_HUMAN",
                    "ligand_id": "decoy-b",
                    "score": "0.7",
                    "is_binder": "0",
                    "mean_min_distance_A": "3.8",
                },
                {
                    "target": "CHEMBL233_OPRM1_HUMAN",
                    "ligand_id": "positive-c",
                    "score": "0.4",
                    "is_binder": "1",
                    "mean_min_distance_A": "3.1",
                },
                {
                    "target": "CHEMBL233_OPRM1_HUMAN",
                    "ligand_id": "decoy-c",
                    "score": "0.9",
                    "is_binder": "0",
                    "mean_min_distance_A": "3.6",
                },
            ]
        )


def test_builds_current_input_from_actual_ranking_rows(tmp_path: Path) -> None:
    rows_csv = tmp_path / "ranking_unique.csv"
    _write_rows_csv(rows_csv)
    ranking_json = tmp_path / "ranking.json"
    hard_json = tmp_path / "hard.json"
    _write_json(ranking_json, _ranking_summary(str(rows_csv)))
    _write_json(hard_json, _hard_decoy_summary())

    rows, provenance = mod.build_current_input_artifact(ranking_json, hard_json)

    assert provenance["ranking_rows_available"] is True
    drd2 = next(row for row in rows if row["target_id"] == "DRD2")
    assert drd2["positive_count"] == 4
    assert drd2["ranking_pr_auc"] == 0.52
    assert drd2["ranking_pr_auc_ci_low"] == 0.46
    assert drd2["top20_hit_rate"] == 0.25
    assert drd2["decoys_above_positive_count"] == 1
    assert drd2["positive_target_rank"] == 2
    assert drd2["positive_anchor_distance_a"] == 3.2
    assert drd2["top_decoy_anchor_distance_a"] == 2.5
    assert drd2["retained_target_row_count"] == 2
    assert drd2["retained_positive_count"] == 1
    assert drd2["top_decoy_retained_count"] == 1


def test_retained_top_rank_rows_block_when_positive_missing(tmp_path: Path) -> None:
    missing_unique = tmp_path / "ranking_unique.csv"
    retained = tmp_path / "ranking_unique_top_rank_retained_top50_current.csv"
    with retained.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["target", "ligand_id", "score", "is_binder", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": "decoy-a",
                    "score": "1.0",
                    "is_binder": "0",
                    "mean_min_distance_A": "2.5",
                },
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": "decoy-b",
                    "score": "2.0",
                    "is_binder": "0",
                    "mean_min_distance_A": "2.7",
                },
            ]
        )
    ranking_json = tmp_path / "ranking.json"
    hard_json = tmp_path / "hard.json"
    _write_json(ranking_json, _ranking_summary(str(missing_unique)))
    _write_json(hard_json, _hard_decoy_summary())

    rows, provenance = mod.build_current_input_artifact(ranking_json, hard_json)

    assert provenance["ranking_rows_available"] is True
    assert provenance["ranking_rows_complete"] is False
    assert provenance["rank_evidence_mode"] == "unique_csv_retained_top_rank_top50"
    drd2 = next(row for row in rows if row["target_id"] == "DRD2")
    assert drd2["decoys_above_positive_count"] == 2
    assert drd2["positive_target_rank"] == ""
    assert drd2["positive_anchor_distance_a"] == ""
    assert drd2["top_decoy_anchor_distance_a"] == 2.5
    assert drd2["retained_target_row_count"] == 2
    assert drd2["retained_positive_count"] == 0
    assert drd2["top_decoy_retained_count"] == 2


def test_retained_top_rank_rows_discovered_for_current_suffix(tmp_path: Path) -> None:
    missing_unique = tmp_path / "ranking_unique_current.csv"
    retained = tmp_path / "ranking_unique_top_rank_retained_top50_current.csv"
    _write_rows_csv(retained)
    ranking_json = tmp_path / "ranking.json"
    hard_json = tmp_path / "hard.json"
    _write_json(ranking_json, _ranking_summary(str(missing_unique)))
    _write_json(hard_json, _hard_decoy_summary())

    rows, provenance = mod.build_current_input_artifact(ranking_json, hard_json)

    assert provenance["ranking_rows_available"] is True
    assert provenance["ranking_rows_complete"] is False
    assert provenance["rank_evidence_mode"] == "unique_csv_retained_top_rank_top50"
    assert provenance["ranking_rows_csv"] == str(retained)
    htr2a = next(row for row in rows if row["target_id"] == "HTR2A")
    assert htr2a["decoys_above_positive_count"] == 0
    assert htr2a["positive_target_rank"] == 1
    assert htr2a["positive_anchor_distance_a"] == 3.0
    assert htr2a["top_decoy_anchor_distance_a"] == 3.8
    assert htr2a["retained_target_row_count"] == 2
    assert htr2a["retained_positive_count"] == 1
    assert htr2a["top_decoy_retained_count"] == 1


def test_missing_ranking_rows_keep_separation_blank_for_fail_closed(tmp_path: Path) -> None:
    ranking_json = tmp_path / "ranking.json"
    hard_json = tmp_path / "hard.json"
    _write_json(ranking_json, _ranking_summary(str(tmp_path / "missing.csv")))
    _write_json(hard_json, _hard_decoy_summary())

    rows, provenance = mod.build_current_input_artifact(ranking_json, hard_json)

    assert provenance["ranking_rows_available"] is False
    assert provenance["ranking_rows_complete"] is False
    assert provenance["rank_evidence_mode"] == "missing"
    assert provenance["ranking_rows_source_missing_fail_closed"] is True
    for row in rows:
        assert row["positive_count"] == 4
        assert row["decoys_above_positive_count"] == ""
        assert row["positive_target_rank"] == ""
        assert row["positive_anchor_distance_a"] == ""
        assert row["top_decoy_anchor_distance_a"] == ""


def test_builds_current_input_from_preregistered_replay_json(tmp_path: Path) -> None:
    replay_json = tmp_path / "preregistered.json"
    _write_json(
        replay_json,
        {
            "status": "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked",
            "pre_registered_runner_replay_complete": True,
            "runner_replay_closure_gate_pass": True,
            "score_matches_probe": True,
            "claim_promotion_allowed": False,
            "claim_boundary": "claim locked replay",
            "runner_replay_target_heldout": {
                "ranking_pr_auc": 0.7074,
                "ranking_pr_auc_ci_low": 0.5597,
                "top20_hit_rate": 1.0,
                "target_rows": {
                    "DRD2": {
                        "decoys_above_positive_count": 0,
                        "positive_target_rank": 1,
                        "positive_anchor_distance_a": 4.56,
                        "top_decoy_anchor_distance_a": 4.99,
                    },
                    "HTR2A": {
                        "decoys_above_positive_count": 0,
                        "positive_target_rank": 1,
                        "positive_anchor_distance_a": 5.72,
                        "top_decoy_anchor_distance_a": 5.77,
                    },
                    "OPRM1": {
                        "decoys_above_positive_count": 0,
                        "positive_target_rank": 1,
                        "positive_anchor_distance_a": 4.80,
                        "top_decoy_anchor_distance_a": 4.82,
                    },
                },
            },
            "runner_replay_target_metric_rows": [
                {"target_id": "DRD2", "row_count": 10000, "positive_count": 4},
                {"target_id": "HTR2A", "row_count": 10000, "positive_count": 4},
                {"target_id": "OPRM1", "row_count": 10000, "positive_count": 4},
            ],
        },
    )

    rows, provenance = mod.build_current_input_artifact(
        tmp_path / "unused_ranking.json",
        tmp_path / "unused_hard.json",
        preregistered_replay_json=replay_json,
    )

    assert provenance["source_mode"] == "adora2a_preregistered_runner_replay"
    assert provenance["pre_registered_runner_replay_complete"] is True
    assert provenance["runner_replay_closure_gate_pass"] is True
    assert provenance["score_matches_probe"] is True
    assert provenance["claim_locked_source"] is True
    assert [row["target_id"] for row in rows] == ["DRD2", "HTR2A", "OPRM1"]
    for row in rows:
        assert row["positive_count"] == 4
        assert row["ranking_pr_auc"] == 0.7074
        assert row["ranking_pr_auc_ci_low"] == 0.5597
        assert row["top20_hit_rate"] == 1.0
        assert row["decoys_above_positive_count"] == 0
        assert row["positive_target_rank"] == 1
        assert row["retained_target_row_count"] == 10000
        assert row["retained_positive_count"] == 4
        assert row["top_decoy_retained_count"] == 9996


def test_main_writes_csv_and_provenance(tmp_path: Path) -> None:
    ranking_json = tmp_path / "ranking.json"
    hard_json = tmp_path / "hard.json"
    _write_json(ranking_json, _ranking_summary())
    _write_json(hard_json, _hard_decoy_summary())
    out_csv = tmp_path / "current.csv"
    out_provenance = tmp_path / "provenance.json"

    rc = mod.main(
        [
            "--ranking-summary-json",
            str(ranking_json),
            "--hard-decoy-summary-json",
            str(hard_json),
            "--out-csv",
            str(out_csv),
            "--out-provenance-json",
            str(out_provenance),
        ]
    )

    assert rc == 0
    csv_rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["target_id"] for row in csv_rows] == ["DRD2", "HTR2A", "OPRM1"]
    payload = json.loads(out_provenance.read_text(encoding="utf-8"))
    assert payload["read_only"]["execution_enabled"] is False
