from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_gap_closure_packet_summarizes_open_win_tier_inputs(tmp_path: Path) -> None:
    win = tmp_path / "win.json"
    actions = tmp_path / "actions.json"
    workorder = tmp_path / "workorder.json"
    image_quality = tmp_path / "image_quality.json"
    bundle = tmp_path / "bundle.json"
    thresholds = tmp_path / "thresholds.json"
    benchmark_plan = tmp_path / "benchmark_plan.json"
    operator_preflight = tmp_path / "operator_preflight.json"
    operator_import = tmp_path / "operator_import.json"

    _write_json(
        win,
        {
            "summary": {
                "target_count": 16,
                "submission_level_status": "pass",
                "review_quality_status": "pass",
                "competitive_floor_status": "partial",
                "win_tier_level_status": "blocked",
            },
            "rows": [
                {
                    "priority": 1,
                    "level": "submission_floor",
                    "dimension": "official_format_and_gate",
                    "status": "pass",
                    "required_level": "TS format pass",
                    "current_evidence": "submission=pass",
                    "evidence_artifacts": "submission.json",
                },
                {
                    "priority": 3,
                    "level": "submission_floor",
                    "dimension": "visual_structure_review",
                    "status": "pass",
                    "required_level": "visual pass",
                    "current_evidence": "image_quality=pass",
                    "evidence_artifacts": "render.json",
                },
                {
                    "priority": 4,
                    "level": "competitive_floor",
                    "dimension": "all_atom_steric_quality",
                    "status": "partial",
                    "required_level": "sidechain native evidence",
                    "current_evidence": "sidechain_native_benchmark=blocked",
                    "evidence_artifacts": "sidechain_native.json",
                },
                {
                    "priority": 5,
                    "level": "win_tier",
                    "dimension": "monomer_native_accuracy",
                    "status": "blocked",
                    "required_level": "mean TM around 0.90+",
                    "current_evidence": "benchmarks=0/0",
                    "evidence_artifacts": "historical.json",
                },
                {
                    "priority": 8,
                    "level": "win_tier",
                    "dimension": "confidence_and_model_selection_calibration",
                    "status": "blocked",
                    "required_level": "selected-vs-oracle loss low",
                    "current_evidence": "rows=0/0",
                    "evidence_artifacts": "calibration.json",
                },
            ],
        },
    )
    _write_json(
        actions,
        {
            "summary": {"action_queue_status": "blocked", "target_count": 16},
            "rows": [
                {
                    "priority": 1,
                    "action_id": "all_atom_quality_upgrade",
                    "related_dimension": "all_atom_steric_quality",
                    "status": "blocked_input",
                    "blockers": "sidechain_native_benchmark_missing_or_blocked",
                    "inputs_needed": "no-leak historical sidechain native pairs",
                    "command": "python3 tools/build_casp17_sidechain_native_benchmark_packet.py",
                    "done_when": "all atom quality pass",
                    "evidence_artifacts": "sidechain_native.json",
                },
                {
                    "priority": 2,
                    "action_id": "historical_benchmark_inputs",
                    "related_dimension": "monomer_native_accuracy;complex_interface_accuracy",
                    "status": "blocked_input",
                    "blockers": "ready_total_below_threshold",
                    "inputs_needed": "no-leak historical prediction/native PDB pairs",
                    "command": "python3 tools/build_casp17_historical_benchmark_manifest_scaffold.py",
                    "done_when": "promotion_status=ready",
                    "evidence_artifacts": "historical_scaffold.json",
                },
                {
                    "priority": 6,
                    "action_id": "model_selection_calibration_gate",
                    "related_dimension": "confidence_and_model_selection_calibration",
                    "status": "blocked_input",
                    "blockers": "calibration_csv_missing_or_blocked",
                    "inputs_needed": "no-leak historical top-5 evidence",
                    "command": "python3 tools/build_casp17_model_selection_calibration_packet.py",
                    "done_when": "calibration_status=pass",
                    "evidence_artifacts": "calibration.json",
                },
            ],
        },
    )
    _write_json(
        workorder,
        {
            "summary": {
                "workorder_status": "ready",
                "workorder_count": 2,
                "core_input_workorder_count": 2,
                "missing_core_file_count": 4,
                "missing_ablation_layer_file_count": 20,
                "operator_template_csv": "runs/template.csv",
            }
        },
    )
    _write_json(
        image_quality,
        {
            "summary": {
                "image_quality_status": "pass",
                "pass_count": 160,
                "image_count": 160,
                "presentation_plate_pass_count": 16,
                "presentation_plate_count": 16,
            }
        },
    )
    _write_json(bundle, {"summary": {"bundle_status": "ready", "artifact_count": 442}})
    _write_json(
        thresholds,
        {
            "summary": {
                "threshold_packet_status": "blocked_input",
                "threshold_count": 12,
                "pass_count": 5,
                "partial_count": 1,
                "blocked_count": 6,
                "first_blocked_dimension": "sidechain_native_quality",
                "first_blocked_metric": "sidechain_native_lddt",
                "first_blocked_blocker": "sidechain_native_benchmark_missing_or_blocked",
            }
        },
    )
    _write_json(
        benchmark_plan,
        {
            "summary": {
                "closure_plan_status": "ready",
                "benchmark_evidence_status": "blocked_input",
                "win_required_total_rows": 40,
                "missing_win_total_rows": 40,
                "required_core_prediction_files_for_win": 40,
                "required_native_files_for_win": 40,
                "required_ablation_layer_prediction_files_for_win": 400,
                "required_calibration_rows_for_win": 40,
                "operator_template_csv": "runs/casp17_win_tier_benchmark_operator_template_current.csv",
            }
        },
    )
    _write_json(
        operator_preflight,
        {
            "summary": {
                "operator_preflight_status": "blocked",
                "ready_count": 0,
                "blocked_count": 40,
                "missing_prediction_count": 40,
                "missing_native_count": 40,
                "missing_ablation_layer_file_count": 400,
                "calibration_blocked_count": 40,
                "threshold_blockers": "ready_total_below_threshold",
            }
        },
    )
    _write_json(
        operator_import,
        {
            "summary": {
                "import_status": "blocked",
                "historical_manifest_candidate_csv": "runs/casp17_historical_benchmark_manifest_candidate_current.csv",
                "historical_manifest_candidate_row_count": 0,
                "model_selection_calibration_candidate_csv": "runs/casp17_model_selection_calibration_candidate_current.csv",
                "model_selection_calibration_candidate_row_count": 0,
                "blockers": "operator_preflight_not_pass,ready_count_below_import_threshold",
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_gap_closure_packet.py"),
            "--win-rubric-json",
            str(win),
            "--action-queue-json",
            str(actions),
            "--historical-input-workorder-json",
            str(workorder),
            "--structure-image-quality-json",
            str(image_quality),
            "--data-bundle-json",
            str(bundle),
            "--win-tier-threshold-json",
            str(thresholds),
            "--benchmark-closure-plan-json",
            str(benchmark_plan),
            "--benchmark-operator-preflight-json",
            str(operator_preflight),
            "--benchmark-operator-import-json",
            str(operator_import),
            "--out-json",
            str(tmp_path / "closure.json"),
            "--out-csv",
            str(tmp_path / "closure.csv"),
            "--out-md",
            str(tmp_path / "closure.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "closure.json").read_text(encoding="utf-8"))
    rows = {row["dimension"]: row for row in payload["rows"]}

    assert payload["summary"]["closure_status"] == "blocked_input"
    assert payload["summary"]["current_proven_level"] == "review_quality"
    assert payload["summary"]["next_unclosed_level"] == "competitive_floor"
    assert payload["summary"]["first_open_dimension"] == "all_atom_steric_quality"
    assert payload["summary"]["first_open_action_id"] == "all_atom_quality_upgrade"
    assert payload["summary"]["historical_input_workorder_count"] == 2
    assert payload["summary"]["presentation_plate_pass_count"] == 16
    assert payload["summary"]["threshold_packet_status"] == "blocked_input"
    assert payload["summary"]["threshold_pass_count"] == 5
    assert payload["summary"]["threshold_partial_count"] == 1
    assert payload["summary"]["threshold_blocked_count"] == 6
    assert payload["summary"]["threshold_first_blocked_dimension"] == "sidechain_native_quality"
    assert payload["summary"]["threshold_first_blocked_metric"] == "sidechain_native_lddt"
    assert payload["summary"]["benchmark_closure_plan_status"] == "ready"
    assert payload["summary"]["benchmark_missing_win_total_rows"] == 40
    assert payload["summary"]["benchmark_required_ablation_layer_prediction_files_for_win"] == 400
    assert payload["summary"]["benchmark_operator_preflight_status"] == "blocked"
    assert payload["summary"]["benchmark_operator_blocked_count"] == 40
    assert payload["summary"]["benchmark_operator_missing_ablation_layer_file_count"] == 400
    assert payload["summary"]["benchmark_operator_import_status"] == "blocked"
    assert payload["summary"]["benchmark_import_historical_manifest_candidate_row_count"] == 0
    assert payload["summary"]["benchmark_import_calibration_candidate_row_count"] == 0
    assert payload["summary"]["benchmark_operator_import_blockers"] == (
        "operator_preflight_not_pass,ready_count_below_import_threshold"
    )
    assert rows["official_format_and_gate"]["closure_status"] == "closed"
    assert rows["all_atom_steric_quality"]["closure_status"] == "blocked_input"
    assert rows["monomer_native_accuracy"]["action_id"] == "historical_benchmark_inputs"
    assert "mean TM around 0.90+" in rows["monomer_native_accuracy"]["required_level"]
    assert "Internal closure packet only" in payload["summary"]["claim_boundary"]
    md = (tmp_path / "closure.md").read_text(encoding="utf-8")
    assert "current_proven_level: `review_quality`" in md
    assert "first_threshold_gap: `sidechain_native_quality` / `sidechain_native_lddt`" in md
    assert "benchmark_missing_win_rows: `40/40`" in md
    assert "benchmark_operator_preflight: `blocked` ready/blocked `0/40`" in md
    assert "benchmark_operator_import: `blocked` historical/calibration rows `0/0`" in md
    assert "benchmark_operator_import_blockers: `operator_preflight_not_pass,ready_count_below_import_threshold`" in md
    assert "python3 tools/build_casp17_sidechain_native_benchmark_packet.py" in md
