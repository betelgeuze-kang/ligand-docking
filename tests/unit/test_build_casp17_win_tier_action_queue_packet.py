from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_tier_action_queue_packet_orders_blocked_gaps(tmp_path: Path) -> None:
    win = tmp_path / "win.json"
    competitive = tmp_path / "competitive.json"
    historical_scaffold = tmp_path / "historical_scaffold.json"
    historical_promotion = tmp_path / "historical_promotion.json"
    historical_input_preflight = tmp_path / "historical_input_preflight.json"
    historical = tmp_path / "historical.json"
    calibration_scaffold = tmp_path / "calibration_scaffold.json"
    calibration = tmp_path / "calibration.json"
    render = tmp_path / "render.json"
    polar = tmp_path / "polar.json"
    forcefield = tmp_path / "forcefield.json"
    statistical = tmp_path / "statistical.json"
    sidechain_native = tmp_path / "sidechain_native.json"
    ablation = tmp_path / "ablation.json"

    _write_json(
        win,
        {
            "summary": {
                "target_count": 14,
                "submission_level_status": "pass",
                "review_quality_status": "pass",
                "competitive_floor_status": "partial",
                "win_tier_level_status": "blocked",
            },
            "rows": [
                {
                    "dimension": "all_atom_steric_quality",
                    "status": "partial",
                    "required_level": "all atom target",
                    "current_evidence": "soft=30",
                },
                {
                    "dimension": "monomer_native_accuracy",
                    "status": "blocked",
                    "required_level": "monomer target",
                    "current_evidence": "benchmarks=0/0",
                },
                {
                    "dimension": "complex_interface_accuracy",
                    "status": "blocked",
                    "required_level": "complex target",
                    "current_evidence": "benchmarks=0/0",
                },
                {
                    "dimension": "refinement_ablation_native_evidence",
                    "status": "blocked",
                    "required_level": "ablation target",
                    "current_evidence": "ablation=blocked",
                },
                {
                    "dimension": "confidence_and_model_selection_calibration",
                    "status": "blocked",
                    "required_level": "calibration target",
                    "current_evidence": "rows=0/0",
                },
                {
                    "dimension": "publication_and_qc_visuals",
                    "status": "pass",
                    "required_level": "visual target",
                    "current_evidence": "surface=14/14",
                },
            ],
        },
    )
    _write_json(competitive, {"summary": {"target_count": 14}})
    _write_json(historical_scaffold, {"summary": {"scaffold_status": "blocked", "ready_count": 0, "candidate_count": 2}})
    _write_json(
        historical_promotion,
        {"summary": {"promotion_status": "blocked", "promoted_count": 0, "threshold_blockers": "ready_total_below_threshold"}},
    )
    _write_json(
        historical_input_preflight,
        {
            "summary": {
                "preflight_status": "blocked",
                "historical_input_preflight_status": "blocked",
                "ablation_input_preflight_status": "blocked",
                "historical_ready_count": 0,
                "ablation_ready_count": 0,
                "missing_ablation_layer_file_count": 20,
            }
        },
    )
    _write_json(
        historical,
        {"summary": {"historical_benchmark_status": "blocked", "manifest_blockers": "manifest_missing", "benchmark_count": 0}},
    )
    _write_json(
        calibration_scaffold,
        {
            "summary": {
                "scaffold_status": "blocked",
                "ready_count": 0,
                "candidate_count": 2,
                "existing_csv_blockers": "existing_calibration_csv_missing",
            }
        },
    )
    _write_json(calibration, {"summary": {"calibration_status": "blocked", "calibration_row_count": 0}})
    _write_json(render, {"summary": {"target_count": 14}})
    _write_json(polar, {"summary": {"polar_refinement_status": "pass", "pass_count": 14}})
    _write_json(forcefield, {"summary": {"forcefield_minimization_status": "pass", "pass_count": 14}})
    _write_json(statistical, {"summary": {"statistical_rotamer_status": "pass", "pass_count": 14}})
    _write_json(sidechain_native, {"summary": {"sidechain_native_benchmark_status": "blocked", "pass_count": 0, "benchmark_count": 0}})
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
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_win_tier_action_queue_packet.py"),
            "--win-rubric-json",
            str(win),
            "--competitive-readiness-json",
            str(competitive),
            "--historical-scaffold-json",
            str(historical_scaffold),
            "--historical-promotion-json",
            str(historical_promotion),
            "--historical-input-preflight-json",
            str(historical_input_preflight),
            "--historical-benchmark-json",
            str(historical),
            "--calibration-scaffold-json",
            str(calibration_scaffold),
            "--calibration-json",
            str(calibration),
            "--render-json",
            str(render),
            "--polar-refinement-json",
            str(polar),
            "--forcefield-minimization-json",
            str(forcefield),
            "--statistical-rotamer-json",
            str(statistical),
            "--sidechain-native-benchmark-json",
            str(sidechain_native),
            "--refinement-ablation-json",
            str(ablation),
            "--out-json",
            str(tmp_path / "queue.json"),
            "--out-csv",
            str(tmp_path / "queue.csv"),
            "--out-md",
            str(tmp_path / "queue.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "queue.json").read_text(encoding="utf-8"))
    rows = {row["action_id"]: row for row in payload["rows"]}

    assert payload["summary"]["action_queue_status"] == "blocked"
    assert payload["summary"]["first_not_pass_action_id"] == "all_atom_quality_upgrade"
    assert payload["summary"]["polar_refinement_status"] == "pass"
    assert payload["summary"]["forcefield_minimization_status"] == "pass"
    assert payload["summary"]["statistical_rotamer_status"] == "pass"
    assert payload["summary"]["sidechain_native_benchmark_status"] == "blocked"
    assert payload["summary"]["refinement_ablation_status"] == "blocked"
    assert payload["summary"]["historical_input_preflight_status"] == "blocked"
    assert rows["all_atom_quality_upgrade"]["status"] == "blocked_input"
    assert rows["all_atom_quality_upgrade"]["blockers"] == "sidechain_native_benchmark_missing_or_blocked"
    assert "runs/casp17_predictions_forcefield_minimized_current" in rows["all_atom_quality_upgrade"]["command"]
    assert "runs/casp17_predictions_statistical_rotamer_current" in rows["all_atom_quality_upgrade"]["command"]
    assert "build_casp17_sidechain_native_benchmark_packet.py" in rows["all_atom_quality_upgrade"]["command"]
    assert rows["historical_benchmark_inputs"]["status"] == "blocked_input"
    assert "ready_total_below_threshold" in rows["historical_benchmark_inputs"]["blockers"]
    assert "preflight=blocked" in rows["historical_benchmark_inputs"]["current_evidence"]
    assert "build_casp17_historical_input_preflight_packet.py" in rows["historical_benchmark_inputs"]["command"]
    assert rows["refinement_ablation_native_evidence"]["status"] == "blocked_input"
    assert rows["refinement_ablation_native_evidence"]["blockers"] == "manifest_missing"
    assert "build_casp17_refinement_ablation_packet.py" in rows["refinement_ablation_native_evidence"]["command"]
    assert rows["model_selection_calibration_inputs"]["status"] == "blocked_input"
    assert rows["visual_review_current"]["status"] == "pass"
    assert rows["final_submission_confirmation"]["status"] == "blocked_r4_confirmation"
    assert "Internal CASP17 win-tier action queue" in (tmp_path / "queue.md").read_text(encoding="utf-8")
