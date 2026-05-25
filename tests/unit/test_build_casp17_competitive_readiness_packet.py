from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_prediction(path: Path, target_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                f"TARGET {target_id}",
                "AUTHOR REDACTED",
                "METHOD fixture",
                "MODEL 1",
                "PARENT N/A",
                "ATOM      1 CA   ALA A   1       0.000   0.000   0.000  1.00 70.00           C  ",
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_casp17_competitive_readiness_packet_separates_submission_and_win_tier(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    raw = tmp_path / "raw.json"
    ts = tmp_path / "ts.json"
    submission = tmp_path / "submission.json"
    accuracy = tmp_path / "accuracy.json"
    viewer = tmp_path / "viewer.json"
    prediction_dir = tmp_path / "predictions"
    _write_prediction(prediction_dir / "T9999TS.pdb", "T9999")

    _write_json(
        watchlist,
        {
            "rows": [
                {
                    "target_id": "T9999",
                    "human_open": True,
                    "lane_recommendation": "difficult_protein_complexes",
                }
            ]
        },
    )
    _write_json(raw, {"summary": {"raw_gate_status": "pass", "pass_count": 1}})
    _write_json(ts, {"summary": {"batch_status": "completed_to_submission_gate", "converted_count": 1}})
    _write_json(submission, {"summary": {"submission_go_count": 1, "submission_no_go_count": 0}})
    _write_json(accuracy, {"summary": {"accuracy_readiness_status": "pass", "pass_count": 1}})
    _write_json(viewer, {"summary": {"ready_count": 1, "blocked_count": 0}})

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_competitive_readiness_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--raw-gate-json",
            str(raw),
            "--ts-gate-json",
            str(ts),
            "--submission-gate-json",
            str(submission),
            "--accuracy-readiness-json",
            str(accuracy),
            "--viewer-json",
            str(viewer),
            "--ranked-depth-json",
            str(tmp_path / "missing_ranked_depth.json"),
            "--sidechain-scaffold-json",
            str(tmp_path / "missing_sidechain_scaffold.json"),
            "--sidechain-repack-json",
            str(tmp_path / "missing_sidechain_repack.json"),
            "--steric-relax-json",
            str(tmp_path / "missing_steric_relax.json"),
            "--all-atom-quality-json",
            str(tmp_path / "missing_all_atom_quality.json"),
            "--sidechain-quality-json",
            str(tmp_path / "missing_sidechain_quality.json"),
            "--rotamer-minimization-json",
            str(tmp_path / "missing_rotamer_minimization.json"),
            "--historical-benchmark-json",
            str(tmp_path / "missing_historical.json"),
            "--refinement-ablation-json",
            str(tmp_path / "missing_refinement_ablation.json"),
            "--model-selection-calibration-json",
            str(tmp_path / "missing_model_selection_calibration.json"),
            "--prediction-dir",
            str(prediction_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    by_dimension = {row["dimension"]: row for row in payload["rows"]}

    assert payload["summary"]["submission_readiness_status"] == "pass"
    assert payload["summary"]["competitive_readiness_status"] == "blocked"
    assert payload["summary"]["win_tier_readiness_status"] == "blocked"
    assert by_dimension["submission_floor"]["status"] == "pass"
    assert by_dimension["top5_ranked_model_depth"]["status"] == "partial"
    assert by_dimension["monomer_win_tier_accuracy"]["status"] == "unproven"
    assert by_dimension["all_atom_and_sidechain_quality"]["status"] == "blocked"
    assert by_dimension["refinement_ablation_native_evidence"]["status"] == "blocked"
    assert "CASP17 Competitive Readiness Packet" in (tmp_path / "packet.md").read_text(encoding="utf-8")


def test_competitive_readiness_reports_sidechain_scaffold_as_partial_not_win_tier(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    raw = tmp_path / "raw.json"
    ts = tmp_path / "ts.json"
    submission = tmp_path / "submission.json"
    accuracy = tmp_path / "accuracy.json"
    viewer = tmp_path / "viewer.json"
    ranked = tmp_path / "ranked.json"
    sidechain = tmp_path / "sidechain.json"
    repack = tmp_path / "repack.json"
    steric = tmp_path / "steric.json"
    all_atom = tmp_path / "all_atom.json"
    sidechain_quality = tmp_path / "sidechain_quality.json"
    rotamer = tmp_path / "rotamer.json"
    polar = tmp_path / "polar.json"
    forcefield = tmp_path / "forcefield.json"
    statistical = tmp_path / "statistical.json"
    prediction_dir = tmp_path / "predictions"
    _write_prediction(prediction_dir / "T9999TS.pdb", "T9999")

    _write_json(
        watchlist,
        {"rows": [{"target_id": "T9999", "human_open": True, "lane_recommendation": "difficult_protein_complexes"}]},
    )
    _write_json(raw, {"summary": {"raw_gate_status": "pass", "pass_count": 1}})
    _write_json(ts, {"summary": {"batch_status": "completed_to_submission_gate", "converted_count": 1}})
    _write_json(submission, {"summary": {"submission_go_count": 1, "submission_no_go_count": 0}})
    _write_json(accuracy, {"summary": {"accuracy_readiness_status": "pass", "pass_count": 1}})
    _write_json(viewer, {"summary": {"ready_count": 1, "blocked_count": 0}})
    _write_json(
        ranked,
        {"summary": {"ranked_depth_status": "pass", "pass_count": 1, "candidate_gate_pass_count": 5, "candidate_gate_total_count": 5}},
    )
    _write_json(
        sidechain,
        {
            "summary": {
                "sidechain_scaffold_status": "pass",
                "pass_count": 1,
                "validation_pass_count": 1,
                "min_heavy_atom_completion_fraction": 0.93,
                "total_emitted_heavy_atom_count": 42,
                "total_rotamer_candidate_count": 12,
                "total_rotamer_selected_residue_count": 2,
            }
        },
    )
    _write_json(
        all_atom,
        {
            "summary": {
                "all_atom_quality_status": "pass",
                "pass_count": 1,
                "max_soft_clashscore_per_1000_atoms": 0.0,
                "total_severe_clash_count": 0,
            }
        },
    )
    _write_json(
        sidechain_quality,
        {
            "summary": {
                "sidechain_quality_status": "pass",
                "pass_count": 1,
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
                "pass_count": 1,
                "mean_rotamer_prior_deviation_before_deg": 30.0,
                "mean_rotamer_prior_deviation_after_deg": 14.5,
                "total_hbond_like_contact_count_before": 12,
                "total_hbond_like_contact_count_after": 18,
                "total_salt_bridge_like_contact_count_before": 2,
                "total_salt_bridge_like_contact_count_after": 4,
                "revert_guard_count": 0,
            }
        },
    )
    _write_json(
        polar,
        {
            "summary": {
                "polar_refinement_status": "pass",
                "pass_count": 1,
                "total_soft_clash_delta": 1,
                "total_hbond_like_contact_count_before": 18,
                "total_hbond_like_contact_count_after": 21,
                "total_salt_bridge_like_contact_count_before": 4,
                "total_salt_bridge_like_contact_count_after": 5,
                "revert_guard_count": 0,
            }
        },
    )
    _write_json(
        forcefield,
        {
            "summary": {
                "forcefield_minimization_status": "pass",
                "pass_count": 1,
                "total_forcefield_energy_delta": 22.5,
                "total_soft_clash_delta": 0,
                "total_hbond_like_contact_count_before": 21,
                "total_hbond_like_contact_count_after": 23,
                "total_salt_bridge_like_contact_count_before": 5,
                "total_salt_bridge_like_contact_count_after": 6,
                "total_hydrophobic_contact_count_before": 30,
                "total_hydrophobic_contact_count_after": 34,
                "revert_guard_count": 0,
            }
        },
    )
    _write_json(
        statistical,
        {
            "summary": {
                "statistical_rotamer_status": "pass",
                "pass_count": 1,
                "total_statistical_rotamer_candidate_count": 18,
                "total_packed_residue_count": 2,
                "mean_frequency_prior_penalty_before": 1.6,
                "mean_frequency_prior_penalty_after": 1.2,
                "total_forcefield_energy_delta": 3.5,
                "total_soft_clash_delta": 0,
                "revert_guard_count": 0,
            }
        },
    )
    _write_json(
        repack,
        {
            "summary": {
                "sidechain_repack_status": "pass",
                "pass_count": 1,
                "total_soft_clash_delta": 7,
                "revert_guard_count": 0,
            }
        },
    )
    _write_json(
        steric,
        {
            "summary": {
                "steric_relax_status": "pass",
                "pass_count": 1,
                "total_soft_clash_delta": 11,
                "revert_guard_count": 0,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_competitive_readiness_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--raw-gate-json",
            str(raw),
            "--ts-gate-json",
            str(ts),
            "--submission-gate-json",
            str(submission),
            "--accuracy-readiness-json",
            str(accuracy),
            "--viewer-json",
            str(viewer),
            "--ranked-depth-json",
            str(ranked),
            "--sidechain-scaffold-json",
            str(sidechain),
            "--sidechain-repack-json",
            str(repack),
            "--steric-relax-json",
            str(steric),
            "--all-atom-quality-json",
            str(all_atom),
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
            "--prediction-dir",
            str(prediction_dir),
            "--refinement-ablation-json",
            str(tmp_path / "missing_refinement_ablation.json"),
            "--model-selection-calibration-json",
            str(tmp_path / "missing_model_selection_calibration.json"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = {item["dimension"]: item for item in payload["rows"]}["all_atom_and_sidechain_quality"]

    assert row["status"] == "partial"
    assert "sidechain scaffold=1/1" in row["current_evidence"]
    assert "local frame-rotamer selections=2/12" in row["current_evidence"]
    assert "sidechain repack=1/1" in row["current_evidence"]
    assert "repack soft delta=7" in row["current_evidence"]
    assert "steric relax=1/1" in row["current_evidence"]
    assert "relax soft delta=11" in row["current_evidence"]
    assert "all-atom QC=1/1" in row["current_evidence"]
    assert "severe clashes=0" in row["current_evidence"]
    assert "sidechain quality=1/1" in row["current_evidence"]
    assert "min complete sidechain=1.0" in row["current_evidence"]
    assert "min rotamer proxy=1.0" in row["current_evidence"]
    assert "rotamer minimization=1/1" in row["current_evidence"]
    assert "rotamer prior deviation=30.0->14.5" in row["current_evidence"]
    assert "hbond-like contacts=12->18" in row["current_evidence"]
    assert "polar refinement=1/1" in row["current_evidence"]
    assert "polar hbond-like=18->21" in row["current_evidence"]
    assert "forcefield minimization=1/1" in row["current_evidence"]
    assert "forcefield energy delta=22.5" in row["current_evidence"]
    assert "forcefield hydrophobic=30->34" in row["current_evidence"]
    assert "statistical rotamer=1/1" in row["current_evidence"]
    assert "frequency prior penalty=1.6->1.2" in row["current_evidence"]
    assert payload["summary"]["win_tier_readiness_status"] == "blocked"


def test_competitive_readiness_uses_historical_benchmark_evidence(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.json"
    raw = tmp_path / "raw.json"
    ts = tmp_path / "ts.json"
    submission = tmp_path / "submission.json"
    accuracy = tmp_path / "accuracy.json"
    viewer = tmp_path / "viewer.json"
    ranked = tmp_path / "ranked.json"
    historical = tmp_path / "historical.json"
    prediction_dir = tmp_path / "predictions"
    _write_prediction(prediction_dir / "T9999TS.pdb", "T9999")

    _write_json(
        watchlist,
        {"rows": [{"target_id": "T9999", "human_open": True, "lane_recommendation": "difficult_protein_complexes"}]},
    )
    _write_json(raw, {"summary": {"raw_gate_status": "pass", "pass_count": 1}})
    _write_json(ts, {"summary": {"batch_status": "completed_to_submission_gate", "converted_count": 1}})
    _write_json(submission, {"summary": {"submission_go_count": 1, "submission_no_go_count": 0}})
    _write_json(accuracy, {"summary": {"accuracy_readiness_status": "pass", "pass_count": 1}})
    _write_json(viewer, {"summary": {"ready_count": 1, "blocked_count": 0}})
    _write_json(
        ranked,
        {"summary": {"ranked_depth_status": "pass", "pass_count": 1, "candidate_gate_pass_count": 5, "candidate_gate_total_count": 5}},
    )
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "pass",
                "monomer_benchmark_count": 1,
                "monomer_pass_count": 1,
                "monomer_win_tier_status": "pass",
                "complex_benchmark_count": 0,
                "complex_pass_count": 0,
                "complex_win_tier_status": "blocked",
                "mean_tm_score_proxy": 0.91,
                "mean_gdt_ts_proxy": 0.82,
                "mean_ca_lddt_proxy": 0.78,
                "mean_complex_interface_f1_proxy": 0.0,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_competitive_readiness_packet.py"),
            "--target-watchlist-json",
            str(watchlist),
            "--raw-gate-json",
            str(raw),
            "--ts-gate-json",
            str(ts),
            "--submission-gate-json",
            str(submission),
            "--accuracy-readiness-json",
            str(accuracy),
            "--viewer-json",
            str(viewer),
            "--ranked-depth-json",
            str(ranked),
            "--sidechain-scaffold-json",
            str(tmp_path / "missing_sidechain_scaffold.json"),
            "--sidechain-repack-json",
            str(tmp_path / "missing_sidechain_repack.json"),
            "--steric-relax-json",
            str(tmp_path / "missing_steric_relax.json"),
            "--all-atom-quality-json",
            str(tmp_path / "missing_all_atom_quality.json"),
            "--sidechain-quality-json",
            str(tmp_path / "missing_sidechain_quality.json"),
            "--rotamer-minimization-json",
            str(tmp_path / "missing_rotamer_minimization.json"),
            "--historical-benchmark-json",
            str(historical),
            "--refinement-ablation-json",
            str(tmp_path / "missing_refinement_ablation.json"),
            "--model-selection-calibration-json",
            str(tmp_path / "missing_model_selection_calibration.json"),
            "--prediction-dir",
            str(prediction_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    by_dimension = {row["dimension"]: row for row in payload["rows"]}

    assert by_dimension["monomer_win_tier_accuracy"]["status"] == "pass"
    assert "historical monomer benchmarks=1/1" in by_dimension["monomer_win_tier_accuracy"]["current_evidence"]
    assert "mean TM=0.91" in by_dimension["monomer_win_tier_accuracy"]["current_evidence"]
    assert by_dimension["complex_win_tier_accuracy"]["status"] == "unproven"
    assert by_dimension["refinement_ablation_native_evidence"]["status"] == "blocked"
    assert payload["summary"]["win_tier_readiness_status"] == "blocked"
