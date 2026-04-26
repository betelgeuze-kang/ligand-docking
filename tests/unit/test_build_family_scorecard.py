from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from tools import build_family_scorecard as bfs

ROOT = Path(__file__).resolve().parents[2]


def _write_predictions(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = ["family", "label", "score"]
    for row in rows:
        for name in row:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_balanced_family_metric_calculation(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L0",
            },
            {"family": "gpcr", "label": 0, "score": 0.80},
            {"family": "gpcr", "label": 1, "score": 0.70},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=2,
    )

    gpcr = payload["families"]["gpcr"]
    assert gpcr["row_count"] == 4
    assert gpcr["positive_count"] == 2
    assert gpcr["negative_count"] == 2
    assert gpcr["score_coverage"] == 1.0
    assert gpcr["auroc"] == 0.75
    assert math.isclose(gpcr["average_precision"], 5 / 6)
    assert gpcr["top_k_hit_rate"] == 0.5
    assert gpcr["enrichment_at_k"] == 1.0
    assert gpcr["score_min"] == 0.10
    assert gpcr["score_max"] == 0.90
    assert math.isclose(gpcr["score_mean"], 0.625)


def test_score_resolution_metrics_are_calculated_for_family_and_overall(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.10},
            {"family": "gpcr", "label": 0, "score": 0.10},
            {"family": "gpcr", "label": 1, "score": 0.20},
            {"family": "gpcr", "label": 0, "score": ""},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=2,
    )

    for metrics in [payload["families"]["gpcr"], payload["families"]["overall"]]:
        assert metrics["score_unique_count"] == 2
        assert metrics["score_unique_ratio"] == 0.5
        assert metrics["score_tie_ratio"] == 0.5
        assert metrics["score_mode_ratio"] == 0.5
    for metric_name in [
        "score_unique_count",
        "score_unique_ratio",
        "score_tie_ratio",
        "score_mode_ratio",
    ]:
        assert metric_name in payload["summary"]["metric_names"]


def test_missing_score_coverage_uses_available_scores(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "kinase", "label": 1, "score": 0.95},
            {"family": "kinase", "label": 0, "score": ""},
            {"family": "kinase", "label": 0, "score": 0.25},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=2,
    )

    kinase = payload["families"]["kinase"]
    assert kinase["row_count"] == 3
    assert kinase["negative_count"] == 2
    assert math.isclose(kinase["score_coverage"], 2 / 3)
    assert kinase["score_min"] == 0.25
    assert kinase["score_max"] == 0.95
    assert kinase["score_mean"] == 0.60
    assert kinase["top_k_hit_rate"] == 0.5
    assert {
        "family": "kinase",
        "metric": "score_coverage",
        "reason": "missing_or_non_finite_scores",
    } in payload["warnings"]


def test_single_class_family_records_warning_and_null_rank_metrics(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "ion_channel", "label": 1, "score": 0.90},
            {"family": "ion_channel", "label": 1, "score": 0.70},
            {"family": "gpcr", "label": 0, "score": 0.20},
            {"family": "gpcr", "label": 1, "score": 0.60},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
    )

    ion_channel = payload["families"]["ion_channel"]
    assert ion_channel["auroc"] is None
    assert ion_channel["average_precision"] is None
    assert payload["warnings"] == [
        {
            "family": "ion_channel",
            "metric": "auroc,average_precision",
            "reason": "single_class_labels",
        }
    ]


def test_top_k_hit_rate_and_enrichment_at_k(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "ion_channel", "label": 1, "score": 0.99},
            {"family": "ion_channel", "label": 1, "score": 0.98},
            {"family": "ion_channel", "label": 0, "score": 0.70},
            {"family": "ion_channel", "label": 0, "score": 0.20},
            {"family": "ion_channel", "label": 0, "score": 0.10},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=2,
    )

    ion_channel = payload["families"]["ion_channel"]
    assert ion_channel["top_k_hit_rate"] == 1.0
    assert ion_channel["enrichment_at_k"] == 2.5


def test_lower_better_orientation_changes_rank_metrics_and_top_k(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "kinase", "label": 1, "score": -10.0},
            {"family": "kinase", "label": 0, "score": -8.0},
            {"family": "kinase", "label": 1, "score": -7.0},
            {"family": "kinase", "label": 0, "score": -6.0},
        ],
    )

    payload = bfs.build_family_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=2,
        lower_better=True,
    )

    kinase = payload["families"]["kinase"]
    assert payload["summary"]["lower_better"] is True
    assert kinase["auroc"] == 0.75
    assert math.isclose(kinase["average_precision"], 5 / 6)
    assert kinase["top_k_hit_rate"] == 0.5


def test_baseline_deltas_are_calculated_for_matching_family_metrics(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    baseline = tmp_path / "baseline.json"
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L0",
            },
            {"family": "gpcr", "label": 0, "score": 0.10},
            {"family": "kinase", "label": 1, "score": 0.80},
            {"family": "kinase", "label": 0, "score": 0.30},
        ],
    )
    baseline.write_text(
        json.dumps(
            {
                "families": {
                    "gpcr": {
                        "auroc": 0.75,
                        "average_precision": 0.50,
                        "top_k_hit_rate": 0.25,
                        "enrichment_at_k": 1.50,
                        "score_coverage": 0.90,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard_json=baseline,
    )

    assert payload["families"]["gpcr"]["deltas"] == {
        "auroc": 0.25,
        "average_precision": 0.50,
        "top_k_hit_rate": 0.75,
        "enrichment_at_k": 0.50,
        "score_coverage": 0.10,
    }


def test_missing_baseline_family_or_metric_records_warning(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    baseline = {
        "families": {
            "gpcr": {
                "auroc": 0.50,
                "average_precision": 0.50,
                "top_k_hit_rate": 0.50,
                "score_coverage": 1.0,
            }
        }
    }
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L0",
            },
            {"family": "gpcr", "label": 0, "score": 0.10},
            {"family": "kinase", "label": 1, "score": 0.80},
            {"family": "kinase", "label": 0, "score": 0.30},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard=baseline,
    )

    assert {
        "family": "gpcr",
        "metric": "enrichment_at_k",
        "reason": "missing_baseline_metric",
    } in payload["warnings"]
    assert {
        "family": "kinase",
        "metric": "baseline",
        "reason": "missing_baseline_family",
    } in payload["warnings"]


def test_acceptance_profile_pass_blocked_and_family_override(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
            {"family": "kinase", "label": 1, "score": 0.80},
            {"family": "kinase", "label": 0, "score": 0.30},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        acceptance_profile={
            "default": {"min_score_coverage": 1.0, "min_auroc": 0.8, "min_average_precision": 0.5},
            "families": {"gpcr": {"min_average_precision": 1.1}},
        },
    )

    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["kinase"]["status"] == "pass"
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"
    assert "average_precision 1 < min_average_precision 1.1" in payload["family_acceptance"]["gpcr"]["reasons"]


def test_acceptance_blocks_null_metric(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "ion_channel", "label": 1, "score": 0.90},
            {"family": "ion_channel", "label": 1, "score": 0.70},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        acceptance_profile={"default": {"min_auroc": 0.8}},
    )

    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["ion_channel"]["status"] == "blocked"
    assert "auroc is null for min_auroc" in payload["family_acceptance"]["ion_channel"]["reasons"]


def test_required_family_missing_records_warning_and_blocks_acceptance(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        required_families=["gpcr", "kinase"],
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert payload["summary"]["required_families"] == ["gpcr", "kinase"]
    assert {
        "family": "kinase",
        "metric": "required_family",
        "reason": "missing_required_family",
    } in payload["warnings"]
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["kinase"]["status"] == "blocked"
    assert (
        "required_family blocked because missing_required_family"
        in payload["family_acceptance"]["kinase"]["reasons"]
    )


def test_required_family_missing_blocks_scorecard_without_acceptance_profile(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        required_families=["gpcr", "kinase"],
    )

    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert (
        "required_family blocked because missing_required_family"
        in payload["summary"]["scorecard_level_reasons"]
    )


def test_row_identity_sha256_ignores_scores_but_changes_with_ordered_family_labels(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.csv"
    changed_scores = tmp_path / "changed_scores.csv"
    changed_order = tmp_path / "changed_order.csv"
    base_rows = [
        {"family": "gpcr", "label": 1, "score": 0.90},
        {"family": "kinase", "label": 0, "score": 0.10},
    ]
    _write_predictions(first, base_rows)
    _write_predictions(
        changed_scores,
        [
            {"family": "gpcr", "label": 1, "score": 0.20},
            {"family": "kinase", "label": 0, "score": 0.80},
        ],
    )
    _write_predictions(changed_order, list(reversed(base_rows)))

    first_payload = bfs.build_scorecard(
        predictions_csv=first,
        family_col="family",
        label_col="label",
        score_col="score",
    )
    changed_scores_payload = bfs.build_scorecard(
        predictions_csv=changed_scores,
        family_col="family",
        label_col="label",
        score_col="score",
    )
    changed_order_payload = bfs.build_scorecard(
        predictions_csv=changed_order,
        family_col="family",
        label_col="label",
        score_col="score",
    )

    assert (
        first_payload["summary"]["row_identity_sha256"]
        == changed_scores_payload["summary"]["row_identity_sha256"]
    )
    assert (
        first_payload["summary"]["predictions_csv_sha256"]
        != changed_scores_payload["summary"]["predictions_csv_sha256"]
    )
    assert (
        first_payload["summary"]["row_identity_sha256"]
        != changed_order_payload["summary"]["row_identity_sha256"]
    )


def test_identity_cols_ignore_scores_but_change_with_target_ligand_identity(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.csv"
    changed_scores = tmp_path / "changed_scores.csv"
    changed_identity = tmp_path / "changed_identity.csv"
    _write_predictions(
        first,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L1",
            },
            {
                "family": "kinase",
                "label": 0,
                "score": 0.10,
                "target": "ABL1",
                "ligand_id": "L2",
            },
        ],
    )
    _write_predictions(
        changed_scores,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.20,
                "target": "ADRB2",
                "ligand_id": "L1",
            },
            {
                "family": "kinase",
                "label": 0,
                "score": 0.80,
                "target": "ABL1",
                "ligand_id": "L2",
            },
        ],
    )
    _write_predictions(
        changed_identity,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L9",
            },
            {
                "family": "kinase",
                "label": 0,
                "score": 0.10,
                "target": "ABL1",
                "ligand_id": "L2",
            },
        ],
    )

    first_payload = bfs.build_scorecard(
        predictions_csv=first,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["target", "ligand_id"],
    )
    changed_scores_payload = bfs.build_scorecard(
        predictions_csv=changed_scores,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["target", "ligand_id"],
    )
    changed_identity_payload = bfs.build_scorecard(
        predictions_csv=changed_identity,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["target", "ligand_id"],
    )

    assert first_payload["summary"]["identity_columns"] == [
        "family",
        "label",
        "target",
        "ligand_id",
    ]
    assert (
        first_payload["summary"]["row_identity_sha256"]
        == changed_scores_payload["summary"]["row_identity_sha256"]
    )
    assert (
        first_payload["summary"]["row_identity_sha256"]
        != changed_identity_payload["summary"]["row_identity_sha256"]
    )


def test_default_identity_columns_and_packet_id_are_recorded(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )

    default_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
    )
    packet_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        packet_id="frozen-packet-a",
    )

    assert default_payload["summary"]["identity_columns"] == ["family", "label"]
    assert default_payload["summary"]["packet_id"] is None
    assert packet_payload["summary"]["packet_id"] == "frozen-packet-a"
    assert (
        default_payload["summary"]["row_identity_sha256"]
        == packet_payload["summary"]["row_identity_sha256"]
    )
    assert (
        default_payload["summary"]["row_identity_schema_version"]
        == bfs.ROW_IDENTITY_SCHEMA_VERSION
    )


def test_baseline_row_identity_schema_version_mismatch_blocks_acceptance_and_scorecard(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90, "target": "ADRB2"},
            {"family": "gpcr", "label": 0, "score": 0.10, "target": "ADRB2"},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target"],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target"],
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "identity_columns": candidate_payload["summary"]["identity_columns"],
                "row_identity_schema_version": "family-scorecard-row-identity-v0",
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.row_identity_schema_version",
        "reason": "baseline_row_identity_schema_version_mismatch",
    } in payload["warnings"]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"
    assert (
        "baseline.row_identity_schema_version blocked because baseline_row_identity_schema_version_mismatch"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_missing_baseline_row_identity_schema_version_blocks_acceptance_and_scorecard(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90, "target": "ADRB2"},
            {"family": "gpcr", "label": 0, "score": 0.10, "target": "ADRB2"},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target"],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target"],
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "identity_columns": candidate_payload["summary"]["identity_columns"],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.row_identity_schema_version",
        "reason": "missing_baseline_row_identity_schema_version",
    } in payload["warnings"]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert (
        "baseline.row_identity_schema_version blocked because missing_baseline_row_identity_schema_version"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_blank_identity_value_in_explicit_identity_column_raises_value_error(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90, "target": "ADRB2"},
            {"family": "gpcr", "label": 0, "score": 0.10, "target": ""},
            {"family": "kinase", "label": 1, "score": 0.80, "target": "ABL1"},
            {"family": "kinase", "label": 0, "score": 0.20, "target": "ABL1"},
        ],
    )

    with pytest.raises(
        ValueError,
        match="blank identity value in row 3, column target",
    ):
        bfs.build_scorecard(
            predictions_csv=predictions,
            family_col="family",
            label_col="label",
            score_col="score",
            identity_cols=["target"],
            acceptance_profile={"default": {"min_score_coverage": 1.0}},
        )


def test_blank_family_value_raises_value_error(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "   ", "label": 1, "score": 0.90},
        ],
    )

    with pytest.raises(
        ValueError,
        match="blank family value in row 2, column family",
    ):
        bfs.build_scorecard(
            predictions_csv=predictions,
            family_col="family",
            label_col="label",
            score_col="score",
        )


def test_overall_family_value_is_reserved(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "overall", "label": 1, "score": 0.90},
        ],
    )

    with pytest.raises(
        ValueError,
        match="reserved family value in row 2, column family: overall",
    ):
        bfs.build_scorecard(
            predictions_csv=predictions,
            family_col="family",
            label_col="label",
            score_col="score",
        )


def test_default_identity_columns_do_not_warn_for_blank_non_identity_values(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90, "target": ""},
            {"family": "gpcr", "label": 0, "score": 0.10, "target": "ADRB2"},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
    )

    assert all(
        warning["reason"] != "blank_identity_value" for warning in payload["warnings"]
    )
    assert payload["summary"]["scorecard_level_status"] == "pass"


def test_missing_identity_column_raises_value_error(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(predictions, [{"family": "gpcr", "label": 1, "score": 0.90}])

    with pytest.raises(ValueError, match="missing identity CSV columns: ligand_id"):
        bfs.build_scorecard(
            predictions_csv=predictions,
            family_col="family",
            label_col="label",
            score_col="score",
            identity_cols=["ligand_id"],
        )


def test_score_col_as_identity_col_raises_value_error(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(predictions, [{"family": "gpcr", "label": 1, "score": 0.90}])

    with pytest.raises(ValueError, match="score column cannot be used as an identity column"):
        bfs.build_scorecard(
            predictions_csv=predictions,
            family_col="family",
            label_col="label",
            score_col="score",
            identity_cols=["score"],
        )


def test_duplicate_identity_cols_are_deduplicated_in_summary(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L1",
            }
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["target", "ligand_id", "target"],
    )

    assert payload["summary"]["identity_columns"] == [
        "family",
        "label",
        "target",
        "ligand_id",
    ]


def test_implicit_family_and_label_identity_cols_are_deduplicated(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
            }
        ],
    )

    implicit_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["target"],
    )
    duplicate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["family", "label", "target"],
    )

    assert duplicate_payload["summary"]["identity_columns"] == ["family", "label", "target"]
    assert (
        duplicate_payload["summary"]["row_identity_sha256"]
        == implicit_payload["summary"]["row_identity_sha256"]
    )


def test_baseline_identity_columns_mismatch_blocks_acceptance_and_scorecard(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L1",
            },
            {
                "family": "gpcr",
                "label": 0,
                "score": 0.10,
                "target": "ADRB2",
                "ligand_id": "L2",
            },
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target", "ligand_id"],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target", "ligand_id"],
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "identity_columns": ["family", "label"],
                "row_identity_schema_version": candidate_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.identity_columns",
        "reason": "baseline_identity_columns_mismatch",
    } in payload["warnings"]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"
    assert (
        "baseline.identity_columns blocked because baseline_identity_columns_mismatch"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_missing_baseline_identity_columns_blocks_acceptance_and_scorecard(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90, "target": "ADRB2"},
            {"family": "gpcr", "label": 0, "score": 0.10, "target": "ADRB2"},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target"],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target"],
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "row_identity_schema_version": candidate_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.identity_columns",
        "reason": "missing_baseline_identity_columns",
    } in payload["warnings"]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert (
        "baseline.identity_columns blocked because missing_baseline_identity_columns"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )
    assert (
        "- overall: baseline.identity_columns blocked because missing_baseline_identity_columns"
        in bfs.render_markdown(payload)
    )


def test_non_list_baseline_identity_columns_is_mismatch_without_string_splitting(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "identity_columns": "family,label",
                "row_identity_schema_version": candidate_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.identity_columns",
        "reason": "baseline_identity_columns_mismatch",
    } in payload["warnings"]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"


def test_duplicate_row_identity_with_explicit_identity_cols_blocks_once_per_family(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90, "target": "ADRB2"},
            {"family": "gpcr", "label": 1, "score": 0.80, "target": "ADRB2"},
            {"family": "gpcr", "label": 1, "score": 0.70, "target": "ADRB2"},
            {"family": "kinase", "label": 0, "score": 0.20, "target": "ABL1"},
            {"family": "kinase", "label": 0, "score": 0.10, "target": "ABL1"},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        identity_cols=["target"],
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    duplicate_warnings = [
        warning
        for warning in payload["warnings"]
        if warning["reason"] == "duplicate_row_identity"
    ]
    assert duplicate_warnings == [
        {"family": "gpcr", "metric": "row_identity", "reason": "duplicate_row_identity"},
        {
            "family": "kinase",
            "metric": "row_identity",
            "reason": "duplicate_row_identity",
        },
    ]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert (
        "row_identity blocked because duplicate_row_identity"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )
    assert (
        "- gpcr: row_identity blocked because duplicate_row_identity"
        in bfs.render_markdown(payload)
    )


def test_default_family_label_identity_mode_does_not_warn_for_duplicates(
    tmp_path: Path,
) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 1, "score": 0.80},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
    )

    assert all(
        warning["reason"] != "duplicate_row_identity" for warning in payload["warnings"]
    )
    assert payload["summary"]["scorecard_level_status"] == "pass"


def test_acceptance_supports_delta_thresholds(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "row_identity_schema_version": candidate_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": 0.9,
                    "average_precision": 0.95,
                    "top_k_hit_rate": 0.9,
                    "enrichment_at_k": 1.8,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 0.9,
                    "average_precision": 0.95,
                    "top_k_hit_rate": 0.9,
                    "enrichment_at_k": 1.8,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_delta_average_precision": 0.1}},
    )

    assert payload["families"]["gpcr"]["deltas"]["average_precision"] == 0.05
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"
    assert (
        "delta_average_precision 0.05 < min_delta_average_precision 0.1"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_missing_baseline_summary_blocks_scorecard_and_acceptance(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard={
            "families": {
                "gpcr": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            }
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline",
        "reason": "missing_baseline_summary",
    } in payload["warnings"]
    assert payload["summary"]["scorecard_level_status"] == "blocked"
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert (
        "baseline blocked because missing_baseline_summary"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_baseline_row_identity_mismatch_blocks_acceptance(tmp_path: Path) -> None:
    baseline_predictions = tmp_path / "baseline_predictions.csv"
    candidate_predictions = tmp_path / "candidate_predictions.csv"
    _write_predictions(
        baseline_predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "kinase", "label": 0, "score": 0.10},
        ],
    )
    _write_predictions(
        candidate_predictions,
        [
            {"family": "kinase", "label": 0, "score": 0.10},
            {"family": "gpcr", "label": 1, "score": 0.90},
        ],
    )
    baseline_payload = bfs.build_scorecard(
        predictions_csv=baseline_predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
    )

    payload = bfs.build_scorecard(
        predictions_csv=candidate_predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "row_identity_schema_version": baseline_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": baseline_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": None,
                    "average_precision": None,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "kinase": {
                    "auroc": None,
                    "average_precision": None,
                    "top_k_hit_rate": 0.0,
                    "enrichment_at_k": None,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_score_coverage": 1.0}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.row_identity_sha256",
        "reason": "baseline_row_identity_mismatch",
    } in payload["warnings"]
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert (
        "baseline.row_identity_sha256 blocked because baseline_row_identity_mismatch"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_acceptance_supports_min_and_max_score_resolution_thresholds(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.10},
            {"family": "gpcr", "label": 0, "score": 0.10},
            {"family": "gpcr", "label": 1, "score": 0.20},
            {"family": "gpcr", "label": 0, "score": 0.30},
        ],
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        acceptance_profile={
            "default": {
                "min_score_unique_ratio": 0.9,
                "max_score_tie_ratio": 0.1,
                "max_score_mode_ratio": 0.4,
            }
        },
    )

    assert payload["families"]["gpcr"]["score_unique_ratio"] == 0.75
    assert payload["families"]["gpcr"]["score_tie_ratio"] == 0.25
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"
    assert (
        "score_unique_ratio 0.75 < min_score_unique_ratio 0.9"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )
    assert (
        "score_tie_ratio 0.25 > max_score_tie_ratio 0.1"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )
    assert (
        "score_mode_ratio 0.5 > max_score_mode_ratio 0.4"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_baseline_orientation_mismatch_blocks_acceptance(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "kinase", "label": 1, "score": -10.0},
            {"family": "kinase", "label": 0, "score": -8.0},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        lower_better=True,
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        lower_better=True,
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "row_identity_schema_version": candidate_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "kinase": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_auroc": 0.8}},
    )

    assert {
        "family": "overall",
        "metric": "baseline.lower_better",
        "reason": "baseline_lower_better_mismatch",
    } in payload["warnings"]
    assert payload["summary"]["acceptance_overall_pass"] is False
    assert payload["family_acceptance"]["kinase"]["status"] == "blocked"
    assert (
        "baseline.lower_better blocked because baseline_lower_better_mismatch"
        in payload["family_acceptance"]["kinase"]["reasons"]
    )


def test_invalid_baseline_metric_blocks_acceptance(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    _write_predictions(
        predictions,
        [
            {"family": "gpcr", "label": 1, "score": 0.90},
            {"family": "gpcr", "label": 0, "score": 0.10},
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
    )

    payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        baseline_scorecard={
            "summary": {
                "top_k": 1,
                "lower_better": False,
                "row_identity_schema_version": candidate_payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
            },
            "families": {
                "gpcr": {
                    "auroc": "not-a-number",
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
                "overall": {
                    "auroc": 1.0,
                    "average_precision": 1.0,
                    "top_k_hit_rate": 1.0,
                    "enrichment_at_k": 2.0,
                    "score_coverage": 1.0,
                },
            },
        },
        acceptance_profile={"default": {"min_auroc": 0.8}},
    )

    assert {
        "family": "gpcr",
        "metric": "auroc",
        "reason": "invalid_baseline_comparison_metric",
    } in payload["warnings"]
    assert payload["family_acceptance"]["gpcr"]["status"] == "blocked"
    assert (
        "auroc blocked because invalid_baseline_comparison_metric"
        in payload["family_acceptance"]["gpcr"]["reasons"]
    )


def test_cli_writes_json_markdown_and_csv(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    out_json = tmp_path / "scorecard.json"
    out_md = tmp_path / "scorecard.md"
    out_csv = tmp_path / "scorecard.csv"
    baseline = tmp_path / "baseline.json"
    acceptance_profile = tmp_path / "acceptance.json"
    _write_predictions(
        predictions,
        [
            {
                "family": "gpcr",
                "label": 1,
                "score": 0.90,
                "target": "ADRB2",
                "ligand_id": "L0",
            },
            {
                "family": "gpcr",
                "label": 0,
                "score": 0.10,
                "target": "ADRB2",
                "ligand_id": "L1",
            },
            {
                "family": "kinase",
                "label": 0,
                "score": 0.30,
                "target": "ABL1",
                "ligand_id": "L2",
            },
            {
                "family": "kinase",
                "label": 1,
                "score": 0.80,
                "target": "ABL1",
                "ligand_id": "L3",
            },
        ],
    )
    candidate_payload = bfs.build_scorecard(
        predictions_csv=predictions,
        family_col="family",
        label_col="label",
        score_col="score",
        top_k=1,
        identity_cols=["target", "ligand_id"],
        packet_id="packet-a",
    )
    baseline.write_text(
        json.dumps(
            {
                "summary": {
                    "top_k": 1,
                    "lower_better": False,
                    "identity_columns": candidate_payload["summary"]["identity_columns"],
                    "row_identity_schema_version": candidate_payload["summary"][
                        "row_identity_schema_version"
                    ],
                    "row_identity_sha256": candidate_payload["summary"]["row_identity_sha256"],
                },
                "families": {
                    "gpcr": {
                        "auroc": 0.5,
                        "average_precision": 0.5,
                        "top_k_hit_rate": 0.5,
                        "enrichment_at_k": 1.0,
                        "score_coverage": 1.0,
                    },
                    "kinase": {
                        "auroc": 0.5,
                        "average_precision": 0.5,
                        "top_k_hit_rate": 0.5,
                        "enrichment_at_k": 1.0,
                        "score_coverage": 1.0,
                    },
                    "overall": {
                        "auroc": 0.5,
                        "average_precision": 0.5,
                        "top_k_hit_rate": 0.5,
                        "enrichment_at_k": 1.0,
                        "score_coverage": 1.0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    acceptance_profile.write_text(
        json.dumps({"default": {"min_score_coverage": 1.0, "min_auroc": 0.8}}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_family_scorecard.py"),
            "--predictions-csv",
            str(predictions),
            "--family-col",
            "family",
            "--label-col",
            "label",
            "--score-col",
            "score",
            "--identity-col",
            "target",
            "--identity-col",
            "ligand_id",
            "--packet-id",
            "packet-a",
            "--top-k",
            "1",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
            "--baseline-scorecard-json",
            str(baseline),
            "--acceptance-profile-json",
            str(acceptance_profile),
            "--required-family",
            "gpcr",
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["overall_row_count"] == 4
    assert payload["summary"]["lower_better"] is False
    assert payload["summary"]["supported_families"] == ["gpcr", "kinase"]
    assert payload["summary"]["required_families"] == ["gpcr"]
    assert payload["summary"]["identity_columns"] == [
        "family",
        "label",
        "target",
        "ligand_id",
    ]
    assert payload["summary"]["packet_id"] == "packet-a"
    assert payload["summary"]["row_identity_schema_version"] == bfs.ROW_IDENTITY_SCHEMA_VERSION
    assert len(payload["summary"]["predictions_csv_sha256"]) == 64
    assert len(payload["summary"]["row_identity_sha256"]) == 64
    assert payload["summary"]["scorecard_level_status"] == "pass"
    assert "overall" in payload["families"]
    assert "auroc" in payload["summary"]["metric_names"]
    assert "score_unique_ratio" in payload["summary"]["metric_names"]
    assert payload["summary"]["acceptance_overall_pass"] is True
    assert payload["families"]["gpcr"]["deltas"]["auroc"] == 0.5

    markdown = out_md.read_text(encoding="utf-8")
    assert "| family | row_count | positive_count | negative_count |" in markdown
    assert "score_unique_ratio" in markdown
    assert "- lower_better: False" in markdown
    assert "- identity_columns: family, label, target, ligand_id" in markdown
    assert (
        f"- row_identity_schema_version: {bfs.ROW_IDENTITY_SCHEMA_VERSION}"
        in markdown
    )
    assert "- packet_id: packet-a" in markdown
    assert "- required_families: gpcr" in markdown
    assert "- scorecard_level_status: pass" in markdown
    assert "| gpcr | 2 | 1 | 1 |" in markdown
    assert "| overall | 4 | 2 | 2 |" in markdown

    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))
    assert [row["family"] for row in csv_rows] == ["gpcr", "kinase", "overall"]
    assert csv_rows[0]["predictions_csv_sha256"] == payload["summary"]["predictions_csv_sha256"]
    assert csv_rows[0]["row_identity_schema_version"] == bfs.ROW_IDENTITY_SCHEMA_VERSION
    assert csv_rows[0]["row_identity_sha256"] == payload["summary"]["row_identity_sha256"]
    assert csv_rows[0]["identity_columns"] == "family,label,target,ligand_id"
    assert csv_rows[0]["packet_id"] == "packet-a"
    assert csv_rows[0]["required_families"] == "gpcr"
    assert "score_unique_ratio" in csv_rows[0]
    assert csv_rows[0]["delta_auroc"] == "0.5"
    assert csv_rows[0]["acceptance_status"] == "pass"


def test_cli_accepts_lower_better_flag(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.csv"
    out_json = tmp_path / "scorecard.json"
    out_md = tmp_path / "scorecard.md"
    _write_predictions(
        predictions,
        [
            {"family": "kinase", "label": 1, "score": -10.0},
            {"family": "kinase", "label": 0, "score": -8.0},
            {"family": "kinase", "label": 1, "score": -7.0},
            {"family": "kinase", "label": 0, "score": -6.0},
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_family_scorecard.py"),
            "--predictions-csv",
            str(predictions),
            "--family-col",
            "family",
            "--label-col",
            "label",
            "--score-col",
            "score",
            "--top-k",
            "2",
            "--lower-better",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    kinase = payload["families"]["kinase"]
    assert payload["summary"]["lower_better"] is True
    assert kinase["auroc"] == 0.75
    assert math.isclose(kinase["average_precision"], 5 / 6)
