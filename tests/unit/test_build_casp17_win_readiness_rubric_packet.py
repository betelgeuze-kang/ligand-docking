from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_readiness_rubric_packet_keeps_win_tier_fail_closed(tmp_path: Path) -> None:
    competitive = tmp_path / "competitive.json"
    render = tmp_path / "render.json"
    image_quality = tmp_path / "image_quality.json"
    quality = tmp_path / "quality.json"
    sidechain_quality = tmp_path / "sidechain_quality.json"
    rotamer = tmp_path / "rotamer.json"
    polar = tmp_path / "polar.json"
    forcefield = tmp_path / "forcefield.json"
    statistical = tmp_path / "statistical.json"
    historical = tmp_path / "historical.json"
    ablation = tmp_path / "ablation.json"
    calibration = tmp_path / "calibration.json"

    _write_json(
        competitive,
        {
            "summary": {
                "target_count": 2,
                "submission_readiness_status": "pass",
                "competitive_gap_count": 4,
            },
            "rows": [
                {"dimension": "top5_ranked_model_depth", "status": "pass", "current_evidence": "ranked-depth pass=2/2"},
                {"dimension": "model_score_records", "status": "pass", "current_evidence": "SCORE=2/2"},
                {"dimension": "interface_qscore_records", "status": "pass", "current_evidence": "QSCORE=1/1"},
                {"dimension": "all_atom_and_sidechain_quality", "status": "partial", "current_evidence": "QC partial"},
            ],
        },
    )
    _write_json(
        render,
        {
            "summary": {
                "target_count": 2,
                "rendered_count": 2,
                "pymol_rendered_count": 2,
                "pymol_surface_rendered_count": 0,
                "pymol_qc_rendered_count": 2,
                "review_panel_count": 0,
                "molecular_plate_count": 0,
                "pymol_qc_hotspot_count": 12,
            }
        },
    )
    _write_json(
        image_quality,
        {
            "summary": {
                "image_quality_status": "blocked",
                "target_complete_count": 0,
                "pass_count": 0,
                "image_count": 0,
                "min_estimated_colorful_pixel_count": 0,
            }
        },
    )
    _write_json(
        quality,
        {
            "summary": {
                "all_atom_quality_status": "pass",
                "total_severe_clash_count": 0,
                "total_soft_clash_count": 12,
                "mean_soft_clashscore_per_1000_atoms": 6.1,
                "min_heavy_atom_completion_fraction": 0.99,
            }
        },
    )
    _write_json(
        sidechain_quality,
        {
            "summary": {
                "sidechain_quality_status": "pass",
                "min_complete_sidechain_residue_fraction": 1.0,
                "min_rotamer_proxy_pass_fraction": 1.0,
                "max_cb_radial_outlier_fraction": 0.0,
            }
        },
    )
    _write_json(
        rotamer,
        {
            "summary": {
                "rotamer_minimization_status": "pass",
                "mean_rotamer_prior_deviation_before_deg": 30.0,
                "mean_rotamer_prior_deviation_after_deg": 14.5,
                "total_hbond_like_contact_count_before": 12,
                "total_hbond_like_contact_count_after": 18,
                "total_salt_bridge_like_contact_count_before": 2,
                "total_salt_bridge_like_contact_count_after": 4,
            }
        },
    )
    _write_json(
        polar,
        {
            "summary": {
                "polar_refinement_status": "pass",
                "total_soft_clash_delta": 1,
                "total_hbond_like_contact_count_before": 18,
                "total_hbond_like_contact_count_after": 21,
                "total_salt_bridge_like_contact_count_before": 4,
                "total_salt_bridge_like_contact_count_after": 5,
            }
        },
    )
    _write_json(
        forcefield,
        {
            "summary": {
                "forcefield_minimization_status": "pass",
                "total_forcefield_energy_delta": 22.5,
                "total_soft_clash_delta": 0,
                "total_hbond_like_contact_count_before": 21,
                "total_hbond_like_contact_count_after": 23,
                "total_salt_bridge_like_contact_count_before": 5,
                "total_salt_bridge_like_contact_count_after": 6,
                "total_hydrophobic_contact_count_before": 30,
                "total_hydrophobic_contact_count_after": 34,
            }
        },
    )
    _write_json(
        statistical,
        {
            "summary": {
                "statistical_rotamer_status": "pass",
                "total_statistical_rotamer_candidate_count": 18,
                "total_packed_residue_count": 2,
                "mean_frequency_prior_penalty_before": 1.6,
                "mean_frequency_prior_penalty_after": 1.2,
                "total_forcefield_energy_delta": 3.5,
                "revert_guard_count": 0,
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
            }
        },
    )
    _write_json(
        ablation,
        {
            "summary": {
                "refinement_ablation_status": "blocked",
                "manifest_blockers": "manifest_missing",
                "benchmark_count": 0,
                "layer_count": 10,
                "usable_layer_count": 0,
                "ablation_group_count": 0,
                "ablation_group_pass_count": 0,
                "final_not_worse_count": 0,
                "final_improved_count": 0,
                "required_improved_count": 1,
            }
        },
    )
    _write_json(
        calibration,
        {
            "summary": {
                "calibration_status": "blocked",
                "score_record_coverage_status": "pass",
                "qscore_record_coverage_status": "pass",
                "ranked_candidate_depth_status": "pass",
                "historical_exactness_status": "blocked",
                "calibration_pass_count": 0,
                "calibration_row_count": 0,
                "mean_selection_loss": 0.0,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_readiness_rubric_packet.py"),
            "--competitive-readiness-json",
            str(competitive),
            "--structure-render-json",
            str(render),
            "--structure-image-quality-json",
            str(image_quality),
            "--all-atom-quality-json",
            str(quality),
            "--sidechain-quality-json",
            str(sidechain_quality),
            "--rotamer-minimization-json",
            str(rotamer),
            "--polar-refinement-json",
            str(polar),
            "--forcefield-minimization-json",
            str(forcefield),
            "--statistical-rotamer-json",
            str(statistical),
            "--historical-benchmark-json",
            str(historical),
            "--refinement-ablation-json",
            str(ablation),
            "--model-selection-calibration-json",
            str(calibration),
            "--out-json",
            str(tmp_path / "rubric.json"),
            "--out-csv",
            str(tmp_path / "rubric.csv"),
            "--out-md",
            str(tmp_path / "rubric.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "rubric.json").read_text(encoding="utf-8"))
    rows = {row["dimension"]: row for row in payload["rows"]}

    assert payload["summary"]["submission_level_status"] == "pass"
    assert payload["summary"]["competitive_floor_status"] == "partial"
    assert payload["summary"]["win_tier_level_status"] == "blocked"
    assert payload["summary"]["review_quality_status"] == "blocked"
    assert rows["official_format_and_gate"]["status"] == "pass"
    assert rows["monomer_native_accuracy"]["status"] == "blocked"
    assert "sidechain_status=pass" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "rotamer_minimization=pass" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "polar_refinement=pass" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "forcefield_minimization=pass" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "forcefield_energy_delta=22.5" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "statistical_rotamer=pass" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "frequency_prior=1.6->1.2" in rows["all_atom_steric_quality"]["current_evidence"]
    assert "mean TM around 0.90" in rows["monomer_native_accuracy"]["required_level"]
    assert rows["complex_interface_accuracy"]["status"] == "blocked"
    assert "DockQ" in rows["complex_interface_accuracy"]["required_level"]
    assert rows["refinement_ablation_native_evidence"]["status"] == "blocked"
    assert "manifest_blockers=manifest_missing" in rows["refinement_ablation_native_evidence"]["current_evidence"]
    assert "calibration=blocked" in rows["confidence_and_model_selection_calibration"]["current_evidence"]
    assert rows["publication_and_qc_visuals"]["status"] == "blocked"
    assert "CASP17 rules and format" in (tmp_path / "rubric.md").read_text(encoding="utf-8")


def test_build_casp17_win_readiness_rubric_packet_accepts_full_review_and_benchmarks(tmp_path: Path) -> None:
    competitive = tmp_path / "competitive.json"
    render = tmp_path / "render.json"
    image_quality = tmp_path / "image_quality.json"
    quality = tmp_path / "quality.json"
    sidechain_quality = tmp_path / "sidechain_quality.json"
    rotamer = tmp_path / "rotamer.json"
    polar = tmp_path / "polar.json"
    forcefield = tmp_path / "forcefield.json"
    historical = tmp_path / "historical.json"
    ablation = tmp_path / "ablation.json"
    calibration = tmp_path / "calibration.json"

    _write_json(
        competitive,
        {
            "summary": {"target_count": 1, "submission_readiness_status": "pass", "competitive_gap_count": 0},
            "rows": [
                {"dimension": "top5_ranked_model_depth", "status": "pass", "current_evidence": "ranked-depth pass=1/1"},
                {"dimension": "model_score_records", "status": "pass", "current_evidence": "SCORE=1/1"},
                {"dimension": "interface_qscore_records", "status": "pass", "current_evidence": "QSCORE=1/1"},
                {"dimension": "all_atom_and_sidechain_quality", "status": "pass", "current_evidence": "QC pass"},
            ],
        },
    )
    _write_json(
        render,
        {
            "summary": {
                "target_count": 1,
                "rendered_count": 1,
                "pymol_rendered_count": 1,
                "pymol_surface_rendered_count": 1,
                "pymol_qc_rendered_count": 1,
                "review_panel_count": 1,
                "molecular_plate_count": 1,
                "pymol_qc_hotspot_count": 3,
            }
        },
    )
    _write_json(
        image_quality,
        {
            "summary": {
                "image_quality_status": "pass",
                "target_complete_count": 1,
                "pass_count": 9,
                "image_count": 9,
                "min_estimated_colorful_pixel_count": 250000,
            }
        },
    )
    _write_json(
        quality,
        {
            "summary": {
                "all_atom_quality_status": "pass",
                "total_severe_clash_count": 0,
                "total_soft_clash_count": 0,
                "mean_soft_clashscore_per_1000_atoms": 0.0,
                "min_heavy_atom_completion_fraction": 1.0,
            }
        },
    )
    _write_json(
        sidechain_quality,
        {
            "summary": {
                "sidechain_quality_status": "pass",
                "min_complete_sidechain_residue_fraction": 1.0,
                "min_rotamer_proxy_pass_fraction": 1.0,
                "max_cb_radial_outlier_fraction": 0.0,
            }
        },
    )
    _write_json(
        rotamer,
        {
            "summary": {
                "rotamer_minimization_status": "pass",
                "mean_rotamer_prior_deviation_before_deg": 30.0,
                "mean_rotamer_prior_deviation_after_deg": 14.5,
                "total_hbond_like_contact_count_before": 12,
                "total_hbond_like_contact_count_after": 18,
                "total_salt_bridge_like_contact_count_before": 2,
                "total_salt_bridge_like_contact_count_after": 4,
            }
        },
    )
    _write_json(
        polar,
        {
            "summary": {
                "polar_refinement_status": "pass",
                "total_soft_clash_delta": 1,
                "total_hbond_like_contact_count_before": 18,
                "total_hbond_like_contact_count_after": 21,
                "total_salt_bridge_like_contact_count_before": 4,
                "total_salt_bridge_like_contact_count_after": 5,
            }
        },
    )
    _write_json(
        forcefield,
        {
            "summary": {
                "forcefield_minimization_status": "pass",
                "total_forcefield_energy_delta": 22.5,
                "total_soft_clash_delta": 0,
                "total_hbond_like_contact_count_before": 21,
                "total_hbond_like_contact_count_after": 23,
                "total_salt_bridge_like_contact_count_before": 5,
                "total_salt_bridge_like_contact_count_after": 6,
                "total_hydrophobic_contact_count_before": 30,
                "total_hydrophobic_contact_count_after": 34,
            }
        },
    )
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "pass",
                "monomer_win_tier_status": "pass",
                "complex_win_tier_status": "pass",
                "monomer_pass_count": 5,
                "monomer_benchmark_count": 5,
                "complex_pass_count": 4,
                "complex_benchmark_count": 4,
                "mean_tm_score_proxy": 0.91,
                "mean_gdt_ts_proxy": 0.84,
                "mean_ca_lddt_proxy": 0.88,
                "mean_complex_interface_f1_proxy": 0.62,
            }
        },
    )
    _write_json(
        ablation,
        {
            "summary": {
                "refinement_ablation_status": "pass",
                "benchmark_count": 2,
                "layer_count": 10,
                "usable_layer_count": 20,
                "ablation_group_count": 2,
                "ablation_group_pass_count": 2,
                "final_not_worse_count": 2,
                "final_improved_count": 2,
                "required_improved_count": 1,
                "mean_delta_tm_score_proxy": 0.03,
                "mean_delta_gdt_ts_proxy": 0.04,
                "mean_delta_ca_lddt_proxy": 0.05,
            }
        },
    )
    _write_json(
        calibration,
        {
            "summary": {
                "calibration_status": "pass",
                "score_record_coverage_status": "pass",
                "qscore_record_coverage_status": "pass",
                "ranked_candidate_depth_status": "pass",
                "historical_exactness_status": "pass",
                "calibration_pass_count": 2,
                "calibration_row_count": 2,
                "mean_selection_loss": 0.01,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_readiness_rubric_packet.py"),
            "--competitive-readiness-json",
            str(competitive),
            "--structure-render-json",
            str(render),
            "--structure-image-quality-json",
            str(image_quality),
            "--all-atom-quality-json",
            str(quality),
            "--sidechain-quality-json",
            str(sidechain_quality),
            "--rotamer-minimization-json",
            str(rotamer),
            "--polar-refinement-json",
            str(polar),
            "--forcefield-minimization-json",
            str(forcefield),
            "--historical-benchmark-json",
            str(historical),
            "--refinement-ablation-json",
            str(ablation),
            "--model-selection-calibration-json",
            str(calibration),
            "--out-json",
            str(tmp_path / "rubric.json"),
            "--out-csv",
            str(tmp_path / "rubric.csv"),
            "--out-md",
            str(tmp_path / "rubric.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "rubric.json").read_text(encoding="utf-8"))
    assert payload["summary"]["submission_level_status"] == "pass"
    assert payload["summary"]["competitive_floor_status"] == "pass"
    assert payload["summary"]["win_tier_level_status"] == "pass"
    assert payload["summary"]["review_quality_status"] == "pass"
    rows = {row["dimension"]: row for row in payload["rows"]}
    assert payload["summary"]["requirement_count"] == 9
    assert rows["refinement_ablation_native_evidence"]["status"] == "pass"
