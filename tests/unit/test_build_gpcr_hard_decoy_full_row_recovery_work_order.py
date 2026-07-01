from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_full_row_recovery_work_order as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ranking_summary(detail_csv: Path, unique_csv: Path) -> dict[str, object]:
    return {
        "artifacts": {
            "detail_csv": str(detail_csv),
            "unique_csv": str(unique_csv),
            "topk_csv": str(detail_csv.with_name("ranking_topk_current.csv")),
        },
        "expected_keys_csv": str(detail_csv.with_name("stage1_queue.csv")),
        "split_csv": str(detail_csv.with_name("hard_decoy_split.csv")),
        "score_col": "score",
        "lower_better": True,
    }


def _suite_payload() -> dict[str, object]:
    return {
        "summary": {
            "status": "broad_family_locked",
            "family_claim_safe": False,
            "blocked_target_ids": ["DRD2", "OPRM1"],
        },
        "targets": [
            {
                "target_id": "DRD2",
                "gate_status": "blocked",
                "claim_safe": False,
                "blockers": ["decoy_over_anchored_vs_positive"],
                "root_cause_tags": ["anchor_separation_insufficient"],
                "ranking_pr_auc_ci_low": 0.7611678630724843,
                "top20_hit_rate": 1.0,
                "decoys_above_positive_count": 0,
                "positive_target_rank": 1,
                "positive_anchor_distance_a": 5.36299774646759,
                "top_decoy_anchor_distance_a": 4.959856432676316,
                "anchor_margin_a": -0.4031413137912736,
                "retained_target_row_count": 10,
                "retained_positive_count": 1,
                "top_decoy_retained_count": 9,
            },
            {
                "target_id": "HTR2A",
                "gate_status": "green",
                "claim_safe": True,
                "blockers": [],
                "root_cause_tags": [],
            },
            {
                "target_id": "OPRM1",
                "gate_status": "blocked",
                "claim_safe": False,
                "blockers": ["top_decoy_anchor_not_observed_in_retained_rows"],
                "root_cause_tags": [],
                "ranking_pr_auc_ci_low": 0.7611678630724843,
                "top20_hit_rate": 1.0,
                "decoys_above_positive_count": 0,
                "positive_target_rank": 1,
                "positive_anchor_distance_a": 5.49461901585261,
                "top_decoy_anchor_distance_a": None,
                "anchor_margin_a": None,
                "retained_target_row_count": 3,
                "retained_positive_count": 3,
                "top_decoy_retained_count": 0,
            },
        ],
    }


def test_work_order_records_missing_full_rows_and_current_blockers(tmp_path: Path) -> None:
    detail_csv = tmp_path / "ranking_rows_current.csv"
    unique_csv = tmp_path / "ranking_unique_current.csv"
    retained_csv = tmp_path / "ranking_unique_top_rank_retained_top50_current.csv"
    retained_csv.write_text("target,score\n", encoding="utf-8")
    ranking_json = tmp_path / "ranking.json"
    provenance_json = tmp_path / "provenance.json"
    suite_json = tmp_path / "suite.json"
    _write_json(ranking_json, _ranking_summary(detail_csv, unique_csv))
    _write_json(
        provenance_json,
        {
            "ranking_summary_json": str(ranking_json),
            "ranking_rows_csv": str(retained_csv),
            "rank_evidence_mode": "unique_csv_retained_top_rank_top50",
            "ranking_rows_complete": False,
        },
    )
    _write_json(suite_json, _suite_payload())

    payload = mod.build_gpcr_hard_decoy_full_row_recovery_work_order(
        provenance_json=provenance_json,
        suite_json=suite_json,
        ranking_summary_json=ranking_json,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_hard_decoy_full_row_recovery_required"
    assert summary["missing_full_row_artifact_count"] == 2
    assert summary["missing_ranking_input_artifact_count"] == 2
    assert summary["retained_evidence_available"] is True
    assert summary["ranking_rows_complete"] is False
    assert summary["blocked_target_ids"] == ["DRD2", "OPRM1"]
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert {row["artifact_key"] for row in payload["missing_full_rows"]} == {"detail_csv", "unique_csv"}
    assert {row["path"] for row in payload["missing_full_rows"]} == {str(detail_csv), str(unique_csv)}
    assert {row["artifact_key"] for row in payload["missing_ranking_inputs"]} == {"expected_keys_csv", "split_csv"}
    assert payload["retained_evidence"]["path"] == str(retained_csv)
    drd2 = next(row for row in payload["target_blockers"] if row["target_id"] == "DRD2")
    assert drd2["anchor_margin_a"] == -0.4031413137912736
    oprm1 = next(row for row in payload["target_blockers"] if row["target_id"] == "OPRM1")
    assert oprm1["top_decoy_retained_count"] == 0


def test_main_writes_work_order_artifacts(tmp_path: Path) -> None:
    detail_csv = tmp_path / "ranking_rows_current.csv"
    unique_csv = tmp_path / "ranking_unique_current.csv"
    retained_csv = tmp_path / "ranking_unique_top_rank_retained_top50_current.csv"
    retained_csv.write_text("target,score\n", encoding="utf-8")
    ranking_json = tmp_path / "ranking.json"
    provenance_json = tmp_path / "provenance.json"
    suite_json = tmp_path / "suite.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_json(ranking_json, _ranking_summary(detail_csv, unique_csv))
    _write_json(
        provenance_json,
        {
            "ranking_summary_json": str(ranking_json),
            "ranking_rows_csv": str(retained_csv),
            "rank_evidence_mode": "unique_csv_retained_top_rank_top50",
            "ranking_rows_complete": False,
        },
    )
    _write_json(suite_json, _suite_payload())

    rc = mod.main(
        [
            "--provenance-json",
            str(provenance_json),
            "--suite-json",
            str(suite_json),
            "--ranking-summary-json",
            str(ranking_json),
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
    assert payload["summary"]["status"] == "blocked_gpcr_hard_decoy_full_row_recovery_required"
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Full-Row Recovery Work Order")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["row_type"] for row in rows].count("full_row_artifact") == 2
    assert [row["row_type"] for row in rows].count("ranking_input_artifact") == 2
    assert [row["target_id"] for row in rows if row["row_type"] == "target_blocker"] == ["DRD2", "OPRM1"]
