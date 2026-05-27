from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_readiness_dashboard_summarizes_levels_and_gaps(tmp_path: Path) -> None:
    win = tmp_path / "win.json"
    competitive = tmp_path / "competitive.json"
    threshold = tmp_path / "threshold.json"
    closure = tmp_path / "closure.json"
    coordinate_frame = tmp_path / "coordinate_frame.json"
    shape_sanity = tmp_path / "shape_sanity.json"
    image_quality = tmp_path / "image_quality.json"
    publication = tmp_path / "publication.json"
    model_comparison = tmp_path / "model_comparison.json"
    viewer_smoke = tmp_path / "viewer_smoke.json"
    benchmark = tmp_path / "benchmark.json"
    fill_kit = tmp_path / "fill_kit.json"
    input_scaffold = tmp_path / "input_scaffold.json"
    input_inventory = tmp_path / "input_inventory.json"
    bundle = tmp_path / "bundle.json"

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
            "rows": [{"dimension": "top5_ranked_model_depth", "status": "pass"}],
        },
    )
    _write_json(
        threshold,
        {
            "summary": {
                "target_count": 2,
                "current_proven_level": "review_quality",
                "submission_floor_status": "pass",
                "review_quality_status": "pass",
                "competitive_floor_status": "partial",
                "win_tier_level_status": "blocked",
                "pass_count": 5,
                "partial_count": 1,
                "blocked_count": 6,
                "first_blocked_dimension": "sidechain_native_quality",
                "first_blocked_metric": "sidechain_native_lddt",
                "first_blocked_blocker": "sidechain_native_benchmark_missing_or_blocked",
            },
            "rows": [
                {
                    "level": "competitive_floor",
                    "dimension": "sidechain_native_quality",
                    "metric": "sidechain_native_lddt",
                    "threshold_status": "partial",
                    "blocker": "sidechain_native_benchmark_missing_or_blocked",
                    "next_action": "Populate historical native rows.",
                },
                {
                    "level": "win_tier",
                    "dimension": "monomer_native_accuracy",
                    "metric": "historical_monomer_rows",
                    "threshold_status": "blocked_input",
                    "blocker": "historical_monomer_rows_missing",
                },
            ],
        },
    )
    _write_json(
        closure,
        {
            "summary": {
                "closure_status": "blocked_input",
                "current_proven_level": "review_quality",
                "next_unclosed_level": "competitive_floor",
                "first_operator_input_blockers": "ready_total_below_threshold",
            }
        },
    )
    _write_json(
        coordinate_frame,
        {
            "summary": {
                "coordinate_frame_status": "pass",
                "pass_count": 2,
                "target_count": 2,
                "shifted_target_count": 1,
                "pre_fixed_width_parse_error_count": 3,
                "post_fixed_width_parse_error_count": 0,
                "normalized_prediction_dir": "runs/normalized",
            }
        },
    )
    _write_json(
        shape_sanity,
        {
            "summary": {
                "shape_sanity_status": "pass",
                "pass_count": 2,
                "target_count": 2,
                "blocked_count": 0,
                "blocked_targets": "",
                "max_observed_span_per_residue": 0.2,
                "max_observed_radius_gyration_per_residue": 0.08,
                "max_observed_chain_linearity": 0.12,
            }
        },
    )
    _write_json(
        image_quality,
        {
            "summary": {
                "image_quality_status": "pass",
                "image_count": 26,
                "pass_count": 26,
                "target_complete_count": 2,
                "stereo_depth_count": 2,
                "stereo_depth_pass_count": 2,
                "turntable_count": 2,
                "turntable_pass_count": 2,
                "publication_image_count": 6,
                "publication_image_pass_count": 6,
                "min_estimated_edge_pixel_count": 1234,
                "min_luminance_range": 91.5,
            }
        },
    )
    _write_json(
        publication,
        {
            "summary": {
                "inspection_poster_count": 2,
                "scene_poster_count": 2,
                "review_board_count": 2,
                "molecular_showcase_count": 2,
            }
        },
    )
    _write_json(
        model_comparison,
        {
            "summary": {
                "comparison_status": "pass",
                "promotion_status": "blocked_pending_no_leak_historical_calibration",
                "active_gate_pass_count": 2,
                "model_selected_gate_pass_count": 2,
                "review_both_count": 2,
                "model_selected_internal_candidate_count": 0,
                "contact_sheet_path": "runs/comparison.png",
            }
        },
    )
    _write_json(
        viewer_smoke,
        {
            "summary": {
                "viewer_smoke_status": "pass",
                "pass_count": 2,
                "target_count": 2,
                "viewer_html": "runs/viewer.html",
            }
        },
    )
    _write_json(
        benchmark,
        {"summary": {"row_count": 40, "ready_count": 0, "blocked_count": 40}},
    )
    _write_json(
        fill_kit,
        {
            "summary": {
                "evidence_item_count": 1160,
                "filled_evidence_item_count": 0,
                "missing_evidence_item_count": 1160,
                "sidechain_native_priority_status": "open",
                "sidechain_native_priority_action_count": 120,
                "sidechain_native_priority_open_action_count": 120,
                "sidechain_native_priority_first_open_action_id": "hist_REQUIRED_MONOMER_001:leakage_clearance",
                "sidechain_native_priority_first_open_next_action": "Replace placeholder leakage_clearance with operator-confirmed no_leak provenance.",
                "missing_by_class": {
                    "target_identity": 40,
                    "core_file": 80,
                    "ablation_layer_file": 400,
                    "provenance_field": 400,
                    "calibration_field": 240,
                },
            }
        },
    )
    _write_json(
        input_scaffold,
        {
            "summary": {
                "scaffold_status": "ready",
                "row_count": 40,
                "required_total_file_count": 480,
                "required_prediction_file_count": 40,
                "required_native_file_count": 40,
                "required_ablation_file_count": 400,
                "manifest_draft_csv": "runs/manifest_draft.csv",
                "calibration_draft_csv": "runs/calibration_draft.csv",
            }
        },
    )
    _write_json(
        input_inventory,
        {
            "summary": {
                "inventory_status": "blocked",
                "ready_row_count": 0,
                "blocked_row_count": 40,
                "present_file_count": 0,
                "missing_file_count": 480,
                "present_prediction_file_count": 0,
                "present_native_file_count": 0,
                "present_ablation_layer_file_count": 0,
                "provenance_ready_row_count": 0,
                "calibration_ready_row_count": 0,
                "required_file_count": 480,
            }
        },
    )
    _write_json(bundle, {"summary": {"bundle_status": "ready", "artifact_count": 480}})

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_readiness_dashboard.py"),
            "--win-rubric-json",
            str(win),
            "--competitive-readiness-json",
            str(competitive),
            "--threshold-json",
            str(threshold),
            "--closure-json",
            str(closure),
            "--coordinate-frame-json",
            str(coordinate_frame),
            "--shape-sanity-json",
            str(shape_sanity),
            "--image-quality-json",
            str(image_quality),
            "--publication-figure-json",
            str(publication),
            "--model-comparison-json",
            str(model_comparison),
            "--molecular-viewer-smoke-json",
            str(viewer_smoke),
            "--benchmark-dashboard-json",
            str(benchmark),
            "--evidence-fill-kit-json",
            str(fill_kit),
            "--input-scaffold-json",
            str(input_scaffold),
            "--input-inventory-json",
            str(input_inventory),
            "--data-bundle-json",
            str(bundle),
            "--out-json",
            str(tmp_path / "dashboard.json"),
            "--out-csv",
            str(tmp_path / "dashboard.csv"),
            "--out-md",
            str(tmp_path / "dashboard.md"),
            "--out-html",
            str(tmp_path / "dashboard.html"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    html = (tmp_path / "dashboard.html").read_text(encoding="utf-8")

    assert summary["dashboard_status"] == "ready"
    assert summary["current_proven_level"] == "review_quality"
    assert summary["next_unclosed_level"] == "competitive_floor"
    assert summary["coordinate_frame_status"] == "pass"
    assert summary["coordinate_frame_pass_count"] == 2
    assert summary["coordinate_frame_pre_fixed_width_parse_error_count"] == 3
    assert summary["coordinate_frame_post_fixed_width_parse_error_count"] == 0
    assert summary["shape_sanity_status"] == "pass"
    assert summary["shape_sanity_pass_count"] == 2
    assert summary["shape_sanity_target_count"] == 2
    assert summary["shape_sanity_max_observed_span_per_residue"] == 0.2
    assert summary["shape_sanity_max_observed_radius_gyration_per_residue"] == 0.08
    assert summary["shape_sanity_max_observed_chain_linearity"] == 0.12
    assert summary["image_pass_count"] == 26
    assert summary["stereo_depth_pass_count"] == 2
    assert summary["stereo_depth_count"] == 2
    assert summary["turntable_pass_count"] == 2
    assert summary["turntable_count"] == 2
    assert summary["publication_image_pass_count"] == 6
    assert summary["review_board_count"] == 2
    assert summary["molecular_showcase_count"] == 2
    assert summary["molecular_viewer_smoke_status"] == "pass"
    assert summary["molecular_viewer_pass_count"] == 2
    assert summary["model_selection_comparison_status"] == "pass"
    assert summary["model_selection_promotion_status"] == "blocked_pending_no_leak_historical_calibration"
    assert summary["model_selection_review_both_count"] == 2
    assert summary["model_selection_internal_candidate_count"] == 0
    assert summary["min_estimated_edge_pixel_count"] == 1234
    assert summary["min_luminance_range"] == 91.5
    assert summary["benchmark_row_count"] == 40
    assert summary["missing_evidence_item_count"] == 1160
    assert summary["sidechain_native_priority_status"] == "open"
    assert summary["sidechain_native_priority_open_action_count"] == 120
    assert summary["sidechain_native_priority_action_count"] == 120
    assert summary["sidechain_native_priority_first_open_action_id"] == "hist_REQUIRED_MONOMER_001:leakage_clearance"
    assert summary["sidechain_native_priority_first_open_next_action"].startswith("Replace placeholder")
    assert summary["input_scaffold_status"] == "ready"
    assert summary["input_scaffold_row_count"] == 40
    assert summary["input_scaffold_required_total_file_count"] == 480
    assert summary["input_scaffold_required_ablation_file_count"] == 400
    assert summary["input_inventory_status"] == "blocked"
    assert summary["input_inventory_blocked_row_count"] == 40
    assert summary["input_inventory_present_file_count"] == 0
    assert summary["input_inventory_missing_file_count"] == 480
    assert summary["first_not_pass_level"] == "model_selection_review"
    assert summary["first_not_pass_gap"] == "no_leak_historical_calibration_required_for_model_selected_promotion"
    assert [row["level"] for row in payload["rows"]] == [
        "submission_floor",
        "review_quality",
        "model_selection_review",
        "competitive_floor",
        "win_tier",
        "external_submission_boundary",
    ]
    assert "CASP17 Readiness Dashboard" in html
    assert "PDB frame" in html
    assert "shape sanity" in html
    assert "stereo depth" in html
    assert "turntable" in html
    assert "showcases" in html
    assert "sidechain-native" in html
    assert "model_selection_review" in html
    assert "no_leak_historical_calibration_required_for_model_selected_promotion" in html
    assert "historical_monomer_rows_missing" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "Local readiness dashboard only" in payload["summary"]["claim_boundary"]
