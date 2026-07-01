from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_replay_materialization_readiness as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_candidate(path: Path) -> None:
    rows = [
        {
            "rank": "1",
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": "DRD2_DECOY_A",
            "is_binder": "0",
            "score_value": "-11",
            "mean_min_distance_A": "4.7",
        },
        {
            "rank": "2",
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": "DRD2_DECOY_B",
            "is_binder": "0",
            "score_value": "-10",
            "mean_min_distance_A": "5.1",
        },
        {
            "rank": "3",
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": "DRD2_POS",
            "is_binder": "1",
            "score_value": "-9",
            "mean_min_distance_A": "5.0",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["rank", "target", "ligand_id", "is_binder", "score_value", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(path: Path, *, detail_csv: Path, unique_csv: Path, expected_keys_csv: Path, split_csv: Path) -> None:
    _write_json(
        path,
        {
            "lower_better": True,
            "artifacts": {"detail_csv": str(detail_csv), "unique_csv": str(unique_csv)},
            "expected_keys_csv": str(expected_keys_csv),
            "split_csv": str(split_csv),
        },
    )


def _write_feature_cache(path: Path, ligand_ids: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target",
                "ligand_id",
                "feature_cache_status",
                "label_free_penalty_pressure",
                "label_free_support_pressure",
                "valid_anchor_support",
                "pose_distortion_pressure",
            ],
        )
        writer.writeheader()
        for ligand_id in ligand_ids:
            writer.writerow(
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": ligand_id,
                    "feature_cache_status": "ok",
                    "label_free_penalty_pressure": "0.2",
                    "label_free_support_pressure": "0.4",
                    "valid_anchor_support": "0.4",
                    "pose_distortion_pressure": "0.0",
                }
            )


def _write_spec(path: Path, candidate: Path) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "gpcr_hard_decoy_closure_replay_spec_ready",
                "best_candidate_path": str(candidate),
            },
            "rows": [
                {"target_id": "DRD2", "target_green": False},
                {"target_id": "HTR2A", "target_green": True},
                {"target_id": "OPRM1", "target_green": True},
            ],
        },
    )


def test_readiness_blocks_on_missing_full_artifacts_before_feature_gap(tmp_path: Path) -> None:
    candidate = tmp_path / "demo_ranking_rows_top_rank_retained_top50_current.csv"
    summary = tmp_path / "demo_ranking_summary_current.json"
    closure = tmp_path / "closure.json"
    sweep = tmp_path / "sweep.json"
    feature_cache = tmp_path / "features.csv"
    _write_candidate(candidate)
    _write_summary(
        summary,
        detail_csv=tmp_path / "missing_detail.csv",
        unique_csv=tmp_path / "missing_unique.csv",
        expected_keys_csv=tmp_path / "missing_queue.csv",
        split_csv=tmp_path / "missing_split.csv",
    )
    _write_spec(closure, candidate)
    _write_json(sweep, {"summary": {}})
    _write_feature_cache(feature_cache, ["DRD2_POS"])

    payload = mod.build_gpcr_hard_decoy_replay_materialization_readiness(
        closure_spec_json=closure,
        candidate_sweep_json=sweep,
        feature_cache_globs=[str(feature_cache)],
    )

    summary_payload = payload["summary"]
    assert summary_payload["status"] == "blocked_gpcr_hard_decoy_replay_materialization_missing_full_rows"
    assert summary_payload["missing_full_artifact_count"] == 4
    assert summary_payload["missing_scoring_feature_ligand_ids"] == ["DRD2_DECOY_A", "DRD2_DECOY_B"]
    rows = payload["rows"]
    assert [row["materialization_role"] for row in rows] == [
        "positive",
        "decoy_above_positive",
        "decoy_above_positive",
    ]


def test_readiness_ready_when_full_artifacts_and_features_exist(tmp_path: Path) -> None:
    candidate = tmp_path / "demo_ranking_rows_top_rank_retained_top50_current.csv"
    summary = tmp_path / "demo_ranking_summary_current.json"
    closure = tmp_path / "closure.json"
    sweep = tmp_path / "sweep.json"
    feature_cache = tmp_path / "features.csv"
    detail = tmp_path / "detail.csv"
    unique = tmp_path / "unique.csv"
    expected = tmp_path / "queue.csv"
    split = tmp_path / "split.csv"
    for path in (detail, unique, expected, split):
        path.write_text("target,ligand_id\n", encoding="utf-8")
    _write_candidate(candidate)
    _write_summary(summary, detail_csv=detail, unique_csv=unique, expected_keys_csv=expected, split_csv=split)
    _write_spec(closure, candidate)
    _write_json(sweep, {"summary": {}})
    _write_feature_cache(feature_cache, ["DRD2_POS", "DRD2_DECOY_A", "DRD2_DECOY_B"])

    payload = mod.build_gpcr_hard_decoy_replay_materialization_readiness(
        closure_spec_json=closure,
        candidate_sweep_json=sweep,
        feature_cache_globs=[str(feature_cache)],
    )

    assert payload["summary"]["status"] == "gpcr_hard_decoy_replay_materialization_ready"
    assert payload["summary"]["materialization_ready"] is True
    assert payload["summary"]["missing_full_artifact_count"] == 0
    assert payload["summary"]["missing_scoring_feature_row_count"] == 0


def test_main_writes_readiness_artifacts(tmp_path: Path) -> None:
    candidate = tmp_path / "demo_ranking_rows_top_rank_retained_top50_current.csv"
    summary = tmp_path / "demo_ranking_summary_current.json"
    closure = tmp_path / "closure.json"
    sweep = tmp_path / "sweep.json"
    feature_cache = tmp_path / "features.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_candidate(candidate)
    _write_summary(
        summary,
        detail_csv=tmp_path / "missing_detail.csv",
        unique_csv=tmp_path / "missing_unique.csv",
        expected_keys_csv=tmp_path / "missing_queue.csv",
        split_csv=tmp_path / "missing_split.csv",
    )
    _write_spec(closure, candidate)
    _write_json(sweep, {"summary": {}})
    _write_feature_cache(feature_cache, ["DRD2_POS"])

    rc = mod.main(
        [
            "--closure-spec-json",
            str(closure),
            "--candidate-sweep-json",
            str(sweep),
            "--feature-cache-glob",
            str(feature_cache),
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
    assert payload["summary"]["materialization_ready"] is False
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Replay Materialization Readiness")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["ligand_id"] for row in rows] == ["DRD2_POS", "DRD2_DECOY_A", "DRD2_DECOY_B"]
