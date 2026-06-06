from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_tier_threshold_packet_names_required_win_bands(tmp_path: Path) -> None:
    win = tmp_path / "win.json"
    competitive = tmp_path / "competitive.json"
    viewer = tmp_path / "viewer.json"
    viewer_smoke = tmp_path / "viewer_smoke.json"
    image_quality = tmp_path / "image_quality.json"
    publication_figure = tmp_path / "publication_figure.json"
    all_atom = tmp_path / "all_atom.json"
    sidechain_quality = tmp_path / "sidechain_quality.json"
    sidechain_native = tmp_path / "sidechain_native.json"
    historical = tmp_path / "historical.json"
    ablation = tmp_path / "ablation.json"
    calibration = tmp_path / "calibration.json"

    _write_json(
        win,
        {
            "summary": {
                "target_count": 2,
                "submission_level_status": "pass",
                "review_quality_status": "pass",
                "competitive_floor_status": "partial",
                "win_tier_level_status": "blocked",
            }
        },
    )
    _write_json(
        competitive,
        {
            "summary": {"target_count": 2, "submission_readiness_status": "pass"},
            "rows": [
                {"dimension": "top5_ranked_model_depth", "status": "pass"},
                {"dimension": "all_atom_and_sidechain_quality", "status": "partial"},
            ],
        },
    )
    _write_json(
        viewer,
        {
            "summary": {
                "target_count": 2,
                "ready_count": 2,
                "webgl_runtime": "internal_canvas_runtime",
                "external_network_default": "disabled",
            }
        },
    )
    _write_json(
        viewer_smoke,
        {
            "summary": {
                "viewer_smoke_status": "pass",
                "target_count": 2,
                "pass_count": 2,
                "blocked_count": 0,
            }
        },
    )
    _write_json(
        image_quality,
        {
            "summary": {
                "image_quality_status": "pass",
                "target_complete_count": 2,
                "stereo_depth_count": 2,
                "stereo_depth_pass_count": 2,
                "turntable_count": 2,
                "turntable_pass_count": 2,
            }
        },
    )
    _write_json(
        publication_figure,
        {
            "summary": {
                "publication_figure_status": "pass",
                "target_complete_count": 2,
                "inspection_poster_count": 2,
                "scene_poster_count": 2,
                "review_board_count": 2,
                "molecular_showcase_count": 2,
            }
        },
    )
    _write_json(
        all_atom,
        {
            "summary": {
                "all_atom_quality_status": "pass",
                "total_severe_clash_count": 0,
                "max_soft_clashscore_per_1000_atoms": 0.42,
            }
        },
    )
    _write_json(
        sidechain_quality,
        {
            "summary": {
                "sidechain_quality_status": "pass",
            }
        },
    )
    _write_json(
        sidechain_native,
        {
            "summary": {
                "sidechain_native_benchmark_status": "blocked",
                "pass_count": 0,
                "benchmark_count": 0,
                "mean_sidechain_lddt_proxy": 0.0,
            }
        },
    )
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "blocked",
                "monomer_win_tier_status": "blocked",
                "complex_win_tier_status": "blocked",
                "manifest_blockers": "manifest_missing",
                "monomer_benchmark_count": 0,
                "complex_benchmark_count": 0,
                "mean_tm_score_proxy": 0.0,
                "mean_gdt_ts_proxy": 0.0,
                "mean_ca_lddt_proxy": 0.0,
                "mean_complex_interface_f1_proxy": 0.0,
                "mean_complex_qsbest_proxy": 0.0,
                "mean_complex_interface_patch_jaccard_proxy": 0.0,
                "mean_complex_dockq_proxy": 0.0,
            }
        },
    )
    _write_json(
        ablation,
        {
            "summary": {
                "refinement_ablation_status": "blocked",
                "manifest_blockers": "manifest_missing",
                "final_not_worse_count": 0,
                "ablation_group_count": 0,
            }
        },
    )
    _write_json(
        calibration,
        {
            "summary": {
                "calibration_status": "blocked",
                "calibration_pass_count": 0,
                "calibration_row_count": 0,
                "mean_selection_loss": 0.0,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_threshold_packet.py"),
            "--win-rubric-json",
            str(win),
            "--competitive-readiness-json",
            str(competitive),
            "--molecular-viewer-json",
            str(viewer),
            "--molecular-viewer-smoke-json",
            str(viewer_smoke),
            "--structure-image-quality-json",
            str(image_quality),
            "--publication-figure-json",
            str(publication_figure),
            "--all-atom-quality-json",
            str(all_atom),
            "--sidechain-quality-json",
            str(sidechain_quality),
            "--sidechain-native-benchmark-json",
            str(sidechain_native),
            "--historical-benchmark-json",
            str(historical),
            "--refinement-ablation-json",
            str(ablation),
            "--model-selection-calibration-json",
            str(calibration),
            "--out-json",
            str(tmp_path / "threshold.json"),
            "--out-csv",
            str(tmp_path / "threshold.csv"),
            "--out-md",
            str(tmp_path / "threshold.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "threshold.json").read_text(encoding="utf-8"))
    rows = {(row["dimension"], row["metric"]): row for row in payload["rows"]}

    assert payload["summary"]["threshold_packet_status"] == "blocked_input"
    assert payload["summary"]["current_proven_level"] == "review_quality"
    assert payload["summary"]["next_unclosed_level"] == "competitive_floor"
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["first_gap_level"] == "competitive_floor"
    assert payload["summary"]["first_blocked_dimension"] == "sidechain_native_quality"
    assert payload["summary"]["first_blocked_metric"] == "sidechain_native_lddt"
    assert payload["summary"]["first_gap_status"] == "partial"
    assert rows[("official_submission_gate", "submission_go_fraction")]["threshold_status"] == "pass"
    assert rows[("visual_molecular_review", "visual_review_fraction")]["threshold_status"] == "pass"
    assert "stereo_depth=2/2" in rows[("visual_molecular_review", "visual_review_fraction")]["current_status"]
    assert "turntable=2/2" in rows[("visual_molecular_review", "visual_review_fraction")]["current_status"]
    assert rows[("local_all_atom_qc", "severe_clash_count")]["threshold_status"] == "pass"
    assert rows[("local_all_atom_qc", "min_heavy_atom_completion_fraction")]["threshold_status"] == "pass"
    assert rows[("local_sidechain_qc", "min_sidechain_completion_fraction")]["threshold_status"] == "pass"
    assert rows[("local_sidechain_qc", "min_rotamer_proxy_pass_fraction")]["threshold_status"] == "pass"
    assert rows[("sidechain_native_quality", "sidechain_native_lddt")]["threshold_status"] == "partial"
    assert rows[("sidechain_native_quality", "sidechain_native_rmsd_a")]["threshold_status"] == "partial"
    assert rows[("sidechain_native_quality", "sidechain_native_lddt")]["blocker"] == "sidechain_native_benchmark_missing_or_blocked"
    assert rows[("monomer_native_accuracy", "historical_monomer_rows")]["win_tier_threshold"] == 25.0
    assert rows[("monomer_native_accuracy", "monomer_mean_tm")]["win_tier_threshold"] == 0.9
    assert rows[("monomer_native_accuracy", "monomer_mean_gdt_ts")]["win_tier_threshold"] == 0.8
    assert rows[("monomer_native_accuracy", "monomer_mean_ca_lddt")]["win_tier_threshold"] == 0.85
    assert rows[("monomer_native_accuracy", "monomer_correct_fold_rate")]["win_tier_threshold"] == 0.95
    assert rows[("complex_interface_accuracy", "complex_mean_tm")]["win_tier_threshold"] == 0.78
    assert rows[("complex_interface_accuracy", "complex_interface_f1")]["win_tier_threshold"] == 0.58
    assert rows[("complex_interface_accuracy", "complex_dockq")]["win_tier_threshold"] == 0.58
    assert rows[("complex_interface_accuracy", "complex_dockq")]["blocker"] == "complex_dockq_or_interface_patch_quality_missing_or_below_threshold"
    assert rows[("refinement_ablation_native_evidence", "final_improved_rate")]["win_tier_threshold"] == 0.6
    assert rows[("refinement_ablation_native_evidence", "mean_delta_tm")]["win_tier_threshold"] == 0.01
    assert rows[("refinement_ablation_native_evidence", "mean_delta_lddt")]["win_tier_threshold"] == 0.015
    assert rows[("model_selection_calibration", "selection_loss")]["direction"] == "max"
    assert rows[("model_selection_calibration", "score_native_correlation")]["win_tier_threshold"] == 0.7
    assert rows[("model_selection_calibration", "qscore_interface_correlation")]["win_tier_threshold"] == 0.65
    assert rows[("model_selection_calibration", "confidence_ece")]["win_tier_threshold"] == 0.08
    assert payload["summary"]["standard_levels"][0]["level"] == "submission_floor"
    assert "Operational internal threshold packet only" in payload["summary"]["claim_boundary"]

    md = (tmp_path / "threshold.md").read_text(encoding="utf-8")
    assert "CASP17 Win Tier Threshold Packet" in md
    assert "next_unclosed_level: `competitive_floor`" in md
    assert "sidechain_native_benchmark_missing_or_blocked" in md
