from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_historical_winner_normalized_bands as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--historical-benchmark-json",
        str(tmp_path / "historical.json"),
        "--metric-surface-contract-json",
        str(tmp_path / "metric_surface.json"),
        "--official-archive-baseline-json",
        str(tmp_path / "official.json"),
        "--sidechain-native-benchmark-json",
        str(tmp_path / "sidechain.json"),
        "--out-json",
        str(tmp_path / "bands.json"),
        "--out-csv",
        str(tmp_path / "bands.csv"),
        "--out-md",
        str(tmp_path / "bands.md"),
    ]


def _write_blocked_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "historical.json",
        {
            "summary": {
                "historical_benchmark_status": "blocked",
                "benchmark_count": 0,
                "monomer_benchmark_count": 0,
                "complex_benchmark_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "metric_surface.json",
        {
            "summary": {
                "metric_surface_contract_status": "awaiting_strict_blind_evidence_files",
                "ready_slot_count": 0,
                "strict_blind_slot_count": 40,
                "ready_metric_row_count": 0,
                "metric_surface_row_count": 440,
            }
        },
    )
    _write_json(
        tmp_path / "official.json",
        {
            "summary": {
                "official_archive_baseline_lane_status": "official_archive_baseline_lane_ready",
                "baseline_candidate_count": 24,
                "competitive_proof_eligible_count": 0,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
            }
        },
    )
    _write_json(
        tmp_path / "sidechain.json",
        {
            "summary": {
                "sidechain_native_benchmark_status": "blocked",
                "pass_count": 0,
                "benchmark_count": 40,
            }
        },
    )


def test_historical_winner_normalized_bands_blocks_until_strict_blind_metrics_exist(tmp_path: Path) -> None:
    _write_blocked_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    rows = {row["band_id"]: row for row in payload["rows"]}
    summary = payload["summary"]
    assert summary["historical_winner_normalized_bands_status"] == "blocked_strict_blind_metrics_missing"
    assert summary["band_count"] == 5
    assert summary["blocked_band_count"] == 5
    assert summary["strict_blind_ready_slot_count"] == 0
    assert summary["strict_blind_slot_count"] == 40
    assert summary["official_archive_baseline_candidate_count"] == 24
    assert summary["official_archive_competitive_proof_eligible_count"] == 0
    assert summary["official_archive_policy"] == "do_not_import_as_internal_prediction"
    assert summary["first_blocked_band_id"] == "casp15_regular_domain"
    assert summary["first_blocker"] == "strict_blind_historical_metric_surface_missing"
    assert rows["casp15_regular_domain"]["reference_winner_value"] == 90.4273
    assert rows["casp15_regular_domain"]["top5_cutoff"] == 73.0
    assert rows["casp15_regular_domain"]["top3_cutoff"] == 85.0
    assert rows["casp16_regular_domain"]["reference_winner_value"] == 40.8978
    assert rows["casp16_regular_domain"]["top5_cutoff"] == 33.3
    assert rows["casp16_regular_domain"]["top3_cutoff"] == 36.3
    assert rows["casp16_ligand_pose_affinity"]["top5_cutoff"] == 0.69
    assert rows["accuracy_estimation_model_selection"]["top5_cutoff"] == 0.70
    assert (tmp_path / "bands.md").is_file()


def test_historical_winner_normalized_bands_ready_for_review_when_top5_bands_hold(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "historical.json",
        {
            "summary": {
                "historical_benchmark_status": "pass",
                "benchmark_count": 40,
                "monomer_benchmark_count": 25,
                "complex_benchmark_count": 15,
                "casp15_regular_domain_sum_zscore": 86.0,
                "casp16_regular_domain_sum_zscore": 37.0,
                "casp16_complex_sum_zscore": 14.5,
                "mean_lddt_pli": 0.81,
                "top1_selection_accuracy": 0.72,
                "dockq_acceptable_fraction": 0.93,
                "dockq_medium_fraction": 0.76,
                "dockq_high_fraction": 0.52,
                "bisyrmsd_2a_hit_fraction": 0.71,
                "affinity_kendall_tau": 0.56,
                "score_native_correlation": 0.73,
                "high_confidence_false_positive_rate": 0.04,
            }
        },
    )
    _write_json(
        tmp_path / "metric_surface.json",
        {
            "summary": {
                "metric_surface_contract_status": "metric_surface_ready",
                "ready_slot_count": 40,
                "strict_blind_slot_count": 40,
                "ready_metric_row_count": 440,
                "metric_surface_row_count": 440,
            }
        },
    )
    _write_json(
        tmp_path / "official.json",
        {
            "summary": {
                "baseline_candidate_count": 24,
                "competitive_proof_eligible_count": 0,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
            }
        },
    )
    _write_json(
        tmp_path / "sidechain.json",
        {"summary": {"sidechain_native_benchmark_status": "pass", "pass_count": 40, "benchmark_count": 40}},
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))
    rows = {row["band_id"]: row for row in payload["rows"]}

    assert payload["summary"]["historical_winner_normalized_bands_status"] == (
        "historical_winner_normalized_bands_ready_for_review"
    )
    assert payload["summary"]["top5_or_better_count"] == 5
    assert payload["summary"]["winner_proximity_count"] == 4
    assert rows["casp15_regular_domain"]["band_status"] == "top3_winner_proximity"
    assert rows["casp16_regular_domain"]["winner_ratio"] > 0.90
    assert rows["casp16_multimer_complex"]["band_status"] == "top3_winner_proximity"
    assert rows["casp16_ligand_pose_affinity"]["band_status"] == "top3_winner_proximity"
    assert rows["accuracy_estimation_model_selection"]["band_status"] == "top5_competitive"


def test_historical_winner_normalized_bands_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["historical_winner_normalized_bands_status"] == "blocked_missing_inputs"
    assert "historical_benchmark_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
