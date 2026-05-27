#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WIN_RUBRIC_JSON = "runs/casp17_win_readiness_rubric_packet_current.json"
DEFAULT_COMPETITIVE_READINESS_JSON = "runs/casp17_competitive_readiness_packet_current.json"
DEFAULT_THRESHOLD_JSON = "runs/casp17_win_tier_threshold_packet_current.json"
DEFAULT_CLOSURE_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_COORDINATE_FRAME_JSON = "runs/casp17_pdb_coordinate_frame_packet_model_selected_current.json"
DEFAULT_SHAPE_SANITY_JSON = "runs/casp17_structure_shape_sanity_packet_current.json"
DEFAULT_IMAGE_QUALITY_JSON = "runs/casp17_structure_image_quality_packet_current.json"
DEFAULT_PUBLICATION_FIGURE_JSON = "runs/casp17_publication_figure_packet_current.json"
DEFAULT_MODEL_COMPARISON_JSON = "runs/casp17_model_selected_refinement_comparison_packet_current.json"
DEFAULT_MOLECULAR_VIEWER_SMOKE_JSON = "runs/casp17_molecular_viewer_smoke_packet_current.json"
DEFAULT_BENCHMARK_DASHBOARD_JSON = "runs/casp17_win_tier_benchmark_operator_dashboard_current.json"
DEFAULT_EVIDENCE_FILL_KIT_JSON = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.json"
DEFAULT_INPUT_SCAFFOLD_JSON = "runs/casp17_win_tier_benchmark_input_scaffold_current.json"
DEFAULT_INPUT_INVENTORY_JSON = "runs/casp17_win_tier_benchmark_input_inventory_current.json"
DEFAULT_DATA_BUNDLE_JSON = "casp17/casp17_data_bundle_manifest_current.json"
DEFAULT_OUT_JSON = "runs/casp17_readiness_dashboard_current.json"
DEFAULT_OUT_CSV = "runs/casp17_readiness_dashboard_current.csv"
DEFAULT_OUT_MD = "runs/casp17_readiness_dashboard_current.md"
DEFAULT_OUT_HTML = "runs/casp17_readiness_dashboard_current.html"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status_rank(status: str) -> int:
    order = {"pass": 0, "ready": 1, "partial": 2, "blocked_input": 3, "blocked": 4, "missing": 5}
    return order.get(status, 5)


def _row(
    *,
    priority: int,
    level: str,
    status: str,
    target_bar: str,
    current_evidence: str,
    gap: str,
    next_action: str,
    artifact: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "level": level,
        "status": status or "missing",
        "target_bar": target_bar,
        "current_evidence": current_evidence,
        "gap": gap,
        "next_action": next_action,
        "artifact": artifact,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    win = _summary(_read_json(args.win_rubric_json))
    competitive = _summary(_read_json(args.competitive_readiness_json))
    threshold_payload = _read_json(args.threshold_json)
    threshold = _summary(threshold_payload)
    threshold_rows = _rows(threshold_payload)
    closure = _summary(_read_json(args.closure_json))
    coordinate_frame = _summary(_read_json(args.coordinate_frame_json))
    shape_sanity = _summary(_read_json(args.shape_sanity_json))
    image_quality = _summary(_read_json(args.image_quality_json))
    publication = _summary(_read_json(args.publication_figure_json))
    model_comparison = _summary(_read_json(args.model_comparison_json))
    viewer_smoke = _summary(_read_json(args.molecular_viewer_smoke_json))
    benchmark = _summary(_read_json(args.benchmark_dashboard_json))
    fill_kit = _summary(_read_json(args.evidence_fill_kit_json))
    input_scaffold = _summary(_read_json(args.input_scaffold_json))
    input_inventory = _summary(_read_json(args.input_inventory_json))
    bundle = _summary(_read_json(args.data_bundle_json))

    target_count = _int(
        threshold.get("target_count")
        or closure.get("target_count")
        or win.get("target_count")
        or competitive.get("target_count")
    )
    threshold_by_level: dict[str, list[dict[str, Any]]] = {}
    for item in threshold_rows:
        threshold_by_level.setdefault(_text(item.get("level")), []).append(item)
    competitive_threshold_rows = threshold_by_level.get("competitive_floor", [])
    win_threshold_rows = threshold_by_level.get("win_tier", [])
    first_competitive_gap = next((row for row in competitive_threshold_rows if row.get("threshold_status") != "pass"), {})
    first_win_gap = next((row for row in win_threshold_rows if row.get("threshold_status") != "pass"), {})

    image_count = _int(image_quality.get("image_count"))
    image_pass_count = _int(image_quality.get("pass_count"))
    publication_image_count = _int(image_quality.get("publication_image_count"))
    publication_image_pass_count = _int(image_quality.get("publication_image_pass_count"))
    stereo_depth_count = _int(image_quality.get("stereo_depth_count"))
    stereo_depth_pass_count = _int(image_quality.get("stereo_depth_pass_count"))
    turntable_count = _int(image_quality.get("turntable_count"))
    turntable_pass_count = _int(image_quality.get("turntable_pass_count"))
    min_edge_pixels = _int(image_quality.get("min_estimated_edge_pixel_count"))
    min_luminance_range = image_quality.get("min_luminance_range", 0.0)
    inspection_count = _int(publication.get("inspection_poster_count"))
    scene_count = _int(publication.get("scene_poster_count"))
    review_board_count = _int(publication.get("review_board_count"))
    showcase_count = _int(publication.get("molecular_showcase_count"))
    model_comparison_status = _text(model_comparison.get("comparison_status") or "missing")
    model_promotion_status = _text(model_comparison.get("promotion_status") or "missing")
    model_review_both_count = _int(model_comparison.get("review_both_count"))
    model_active_gate_pass_count = _int(model_comparison.get("active_gate_pass_count"))
    model_selected_gate_pass_count = _int(model_comparison.get("model_selected_gate_pass_count"))
    model_selected_candidate_count = _int(model_comparison.get("model_selected_internal_candidate_count"))
    viewer_smoke_status = _text(viewer_smoke.get("viewer_smoke_status") or "missing")
    viewer_ready_count = _int(viewer_smoke.get("pass_count"))
    viewer_target_count = _int(viewer_smoke.get("target_count"))
    viewer_html_path = _text(viewer_smoke.get("viewer_html"))
    shape_status = _text(shape_sanity.get("shape_sanity_status") or "missing")
    shape_blocks_submission = shape_status == "blocked"

    evidence_item_count = _int(fill_kit.get("evidence_item_count"))
    missing_evidence_count = _int(fill_kit.get("missing_evidence_item_count"))
    missing_by_class = fill_kit.get("missing_by_class")
    if not isinstance(missing_by_class, dict):
        missing_by_class = {}
    missing_by_class_text = ",".join(f"{key}:{missing_by_class[key]}" for key in sorted(missing_by_class))
    sidechain_priority_status = _text(fill_kit.get("sidechain_native_priority_status") or "missing")
    sidechain_priority_open_count = _int(fill_kit.get("sidechain_native_priority_open_action_count"))
    sidechain_priority_action_count = _int(fill_kit.get("sidechain_native_priority_action_count"))
    sidechain_priority_first_action = _text(fill_kit.get("sidechain_native_priority_first_open_action_id"))
    sidechain_priority_first_next_action = _text(fill_kit.get("sidechain_native_priority_first_open_next_action"))

    rows = [
        _row(
            priority=1,
            level="submission_floor",
            status=(
                "blocked_input"
                if coordinate_frame.get("coordinate_frame_status") == "blocked" or shape_blocks_submission
                else _text(win.get("submission_level_status") or threshold.get("submission_floor_status"))
            ),
            target_bar="All current CASP17 protein targets pass local TS format, geometry, confidence, scorecard, author-code runtime boundary, and submission gate.",
            current_evidence=(
                f"targets={target_count}; submission={competitive.get('submission_readiness_status', 'missing')}; "
                f"threshold={threshold.get('submission_floor_status', 'missing')}; "
                f"coordinate_frame={coordinate_frame.get('coordinate_frame_status', 'missing')} "
                f"{coordinate_frame.get('pass_count', 0)}/{coordinate_frame.get('target_count', 0)} "
                f"fixed_width_errors={coordinate_frame.get('pre_fixed_width_parse_error_count', 0)}->"
                f"{coordinate_frame.get('post_fixed_width_parse_error_count', 0)}; "
                f"shape_sanity={shape_status} {shape_sanity.get('pass_count', 0)}/{shape_sanity.get('target_count', 0)} "
                f"max_span_per_res={shape_sanity.get('max_observed_span_per_residue', 'missing')} "
                f"max_rg_per_res={shape_sanity.get('max_observed_radius_gyration_per_residue', 'missing')} "
                f"max_linearity={shape_sanity.get('max_observed_chain_linearity', 'missing')}"
            ),
            gap=(
                "pdb_coordinate_frame_not_fixed_width_parseable"
                if coordinate_frame.get("coordinate_frame_status") == "blocked"
                else "structure_shape_sanity_blocked"
                if shape_blocks_submission
                else ("" if win.get("submission_level_status") == "pass" else "submission_floor_not_fully_green")
            ),
            next_action="Keep final TS artifacts coordinate-normalized/current and perform CASP portal upload only after explicit external-state confirmation.",
            artifact=f"{_artifact(args.competitive_readiness_json)};{_artifact(args.coordinate_frame_json)};{_artifact(args.shape_sanity_json)}",
        ),
        _row(
            priority=2,
            level="review_quality",
            status=_text(win.get("review_quality_status") or threshold.get("review_quality_status")),
            target_bar="Every target has internal viewer, static render panels, stereo-depth renders, turntable review strips, publication figures, inspection posters, scene posters, review boards, molecular showcases, and image smoke coverage.",
            current_evidence=(
                f"image_quality={image_quality.get('image_quality_status', 'missing')}; images={image_pass_count}/{image_count}; "
                f"stereo_depth={stereo_depth_pass_count}/{stereo_depth_count}; "
                f"turntable={turntable_pass_count}/{turntable_count}; "
                f"publication_images={publication_image_pass_count}/{publication_image_count}; "
                f"inspection={inspection_count}/{target_count}; scene={scene_count}/{target_count}; "
                f"review_boards={review_board_count}/{target_count}; showcases={showcase_count}/{target_count}; "
                f"viewer_smoke={viewer_smoke_status} {viewer_ready_count}/{viewer_target_count}; "
                f"min_edge_pixels={min_edge_pixels}; min_luminance_range={min_luminance_range}"
            ),
            gap=(
                ""
                if image_quality.get("image_quality_status") == "pass" and viewer_smoke_status in {"pass", "missing"}
                else "visual_review_image_or_viewer_smoke_not_pass"
            ),
            next_action="Regenerate render, publication, scene, review-board, showcase, viewer, viewer-smoke, and image-quality packets after every coordinate or viewer change.",
            artifact=f"{_artifact(args.image_quality_json)};{_artifact(args.publication_figure_json)};{_artifact(args.molecular_viewer_smoke_json)}",
        ),
        _row(
            priority=3,
            level="model_selection_review",
            status=(
                "partial"
                if model_comparison_status == "pass"
                and model_promotion_status == "blocked_pending_no_leak_historical_calibration"
                else model_comparison_status
            ),
            target_bar="Active and model-selected refined heavy-atom lanes are compared target-by-target before any promotion to CASP submission artifacts.",
            current_evidence=(
                f"comparison={model_comparison_status}; promotion={model_promotion_status}; "
                f"active_gate={model_active_gate_pass_count}/{target_count}; "
                f"model_selected_gate={model_selected_gate_pass_count}/{target_count}; "
                f"review_both={model_review_both_count}/{target_count}; "
                f"internal_promotions={model_selected_candidate_count}/{target_count}"
            ),
            gap=(
                "no_leak_historical_calibration_required_for_model_selected_promotion"
                if model_promotion_status == "blocked_pending_no_leak_historical_calibration"
                else ("" if model_promotion_status in {"pass", "missing"} else model_promotion_status)
            ),
            next_action="Use the comparison boards for human review, but promote model-selected candidates only after no-leak historical calibration proves the selector is safer than the active lane.",
            artifact=_artifact(args.model_comparison_json),
        ),
        _row(
            priority=4,
            level="competitive_floor",
            status=_text(threshold.get("competitive_floor_status") or win.get("competitive_floor_status")),
            target_bar="Review-quality plus top-5 depth, SCORE/QSCORE coverage, low local all-atom clash burden, and no-leak sidechain/native evidence.",
            current_evidence=(
                f"threshold_pass/partial/blocked={threshold.get('pass_count', 0)}/{threshold.get('partial_count', 0)}/{threshold.get('blocked_count', 0)}; "
                f"first_gap={first_competitive_gap.get('dimension', threshold.get('first_blocked_dimension', 'missing'))}/"
                f"{first_competitive_gap.get('metric', threshold.get('first_blocked_metric', 'missing'))}"
            ),
            gap=_text(first_competitive_gap.get("blocker") or threshold.get("first_blocked_blocker")),
            next_action=_text(first_competitive_gap.get("next_action") or "Populate no-leak sidechain/native benchmark evidence."),
            artifact=_artifact(args.threshold_json),
        ),
        _row(
            priority=5,
            level="win_tier",
            status=_text(threshold.get("win_tier_level_status") or win.get("win_tier_level_status")),
            target_bar="25 monomer + 15 complex no-leak historical rows in win bands, refinement ablation pass, sidechain-native quality pass, and calibrated MODEL 1 selection.",
            current_evidence=(
                f"benchmark_rows_ready={benchmark.get('ready_count', 0)}/{benchmark.get('row_count', 0)}; "
                f"evidence_filled={fill_kit.get('filled_evidence_item_count', 0)}/{evidence_item_count}; "
                f"missing={missing_evidence_count}; missing_by_class={missing_by_class_text or '-'}; "
                f"sidechain_native_priority={sidechain_priority_status} "
                f"{sidechain_priority_open_count}/{sidechain_priority_action_count} "
                f"first={sidechain_priority_first_action or '-'}; "
                f"input_scaffold={input_scaffold.get('scaffold_status', 'missing')} "
                f"files={input_scaffold.get('required_total_file_count', 0)}; "
                f"inventory={input_inventory.get('inventory_status', 'missing')} "
                f"present={input_inventory.get('present_file_count', 0)}/"
                f"{input_inventory.get('required_file_count', 0)}"
            ),
            gap=_text(first_win_gap.get("blocker") or closure.get("first_operator_input_blockers") or "historical_benchmark_inputs_missing"),
            next_action=(
                sidechain_priority_first_next_action
                or "Fill the 40-row no-leak historical benchmark template with local prediction/native files, ablation layers, provenance, and calibration fields."
            ),
            artifact=f"{_artifact(args.benchmark_dashboard_json)};{_artifact(args.evidence_fill_kit_json)};{_artifact(args.input_scaffold_json)};{_artifact(args.input_inventory_json)}",
        ),
        _row(
            priority=6,
            level="external_submission_boundary",
            status="blocked_input",
            target_bar="CASP portal upload is an external-state action and remains blocked until the operator explicitly confirms target set and author code use.",
            current_evidence=f"closure={closure.get('closure_status', 'missing')}; bundle={bundle.get('bundle_status', 'missing')}; artifacts={bundle.get('artifact_count', 0)}",
            gap="explicit_operator_confirmation_required",
            next_action="Prepare exact upload target/action/risk/rollback packet before any CASP portal interaction.",
            artifact=f"{_artifact(args.closure_json)};{_artifact(args.data_bundle_json)}",
        ),
    ]
    rows = sorted(rows, key=lambda row: (row["priority"], _status_rank(str(row["status"]))))

    blocked_levels = [row for row in rows if row["status"] not in {"pass", "ready"}]
    summary = {
        "packet_type": "casp17_readiness_dashboard",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dashboard_status": "ready" if rows else "blocked",
        "current_proven_level": _text(threshold.get("current_proven_level") or closure.get("current_proven_level")),
        "next_unclosed_level": _text(closure.get("next_unclosed_level") or "competitive_floor"),
        "target_count": target_count,
        "level_count": len(rows),
        "pass_or_ready_level_count": sum(1 for row in rows if row["status"] in {"pass", "ready"}),
        "blocked_or_partial_level_count": len(blocked_levels),
        "submission_floor_status": rows[0]["status"],
        "review_quality_status": rows[1]["status"],
        "model_selection_review_status": rows[2]["status"],
        "competitive_floor_status": rows[3]["status"],
        "win_tier_status": rows[4]["status"],
        "first_not_pass_level": _text(blocked_levels[0]["level"] if blocked_levels else ""),
        "first_not_pass_gap": _text(blocked_levels[0]["gap"] if blocked_levels else ""),
        "image_quality_status": image_quality.get("image_quality_status", "missing"),
        "image_pass_count": image_pass_count,
        "image_count": image_count,
        "stereo_depth_pass_count": stereo_depth_pass_count,
        "stereo_depth_count": stereo_depth_count,
        "turntable_pass_count": turntable_pass_count,
        "turntable_count": turntable_count,
        "publication_image_pass_count": publication_image_pass_count,
        "publication_image_count": publication_image_count,
        "coordinate_frame_status": coordinate_frame.get("coordinate_frame_status", "missing"),
        "coordinate_frame_pass_count": _int(coordinate_frame.get("pass_count")),
        "coordinate_frame_target_count": _int(coordinate_frame.get("target_count")),
        "coordinate_frame_shifted_target_count": _int(coordinate_frame.get("shifted_target_count")),
        "coordinate_frame_pre_fixed_width_parse_error_count": _int(coordinate_frame.get("pre_fixed_width_parse_error_count")),
        "coordinate_frame_post_fixed_width_parse_error_count": _int(coordinate_frame.get("post_fixed_width_parse_error_count")),
        "coordinate_frame_normalized_prediction_dir": _text(coordinate_frame.get("normalized_prediction_dir")),
        "shape_sanity_status": shape_status,
        "shape_sanity_pass_count": _int(shape_sanity.get("pass_count")),
        "shape_sanity_target_count": _int(shape_sanity.get("target_count")),
        "shape_sanity_blocked_count": _int(shape_sanity.get("blocked_count")),
        "shape_sanity_blocked_targets": _text(shape_sanity.get("blocked_targets")),
        "shape_sanity_max_observed_span_per_residue": shape_sanity.get("max_observed_span_per_residue", 0.0),
        "shape_sanity_max_observed_radius_gyration_per_residue": shape_sanity.get(
            "max_observed_radius_gyration_per_residue", 0.0
        ),
        "shape_sanity_max_observed_chain_linearity": shape_sanity.get("max_observed_chain_linearity", 0.0),
        "min_estimated_edge_pixel_count": min_edge_pixels,
        "min_luminance_range": min_luminance_range,
        "scene_poster_count": scene_count,
        "inspection_poster_count": inspection_count,
        "review_board_count": review_board_count,
        "molecular_showcase_count": showcase_count,
        "molecular_viewer_smoke_status": viewer_smoke_status,
        "molecular_viewer_pass_count": viewer_ready_count,
        "molecular_viewer_target_count": viewer_target_count,
        "molecular_viewer_html_path": viewer_html_path,
        "model_selection_comparison_status": model_comparison_status,
        "model_selection_promotion_status": model_promotion_status,
        "model_selection_active_gate_pass_count": model_active_gate_pass_count,
        "model_selection_model_selected_gate_pass_count": model_selected_gate_pass_count,
        "model_selection_review_both_count": model_review_both_count,
        "sidechain_native_priority_status": sidechain_priority_status,
        "sidechain_native_priority_open_action_count": sidechain_priority_open_count,
        "sidechain_native_priority_action_count": sidechain_priority_action_count,
        "sidechain_native_priority_first_open_action_id": sidechain_priority_first_action,
        "sidechain_native_priority_first_open_next_action": sidechain_priority_first_next_action,
        "model_selection_internal_candidate_count": model_selected_candidate_count,
        "model_selection_comparison_contact_sheet_path": _text(model_comparison.get("contact_sheet_path")),
        "benchmark_row_count": _int(benchmark.get("row_count")),
        "benchmark_ready_count": _int(benchmark.get("ready_count")),
        "benchmark_blocked_count": _int(benchmark.get("blocked_count")),
        "evidence_item_count": evidence_item_count,
        "missing_evidence_item_count": missing_evidence_count,
        "missing_evidence_by_class": missing_by_class,
        "input_scaffold_status": input_scaffold.get("scaffold_status", "missing"),
        "input_scaffold_row_count": _int(input_scaffold.get("row_count")),
        "input_scaffold_required_total_file_count": _int(input_scaffold.get("required_total_file_count")),
        "input_scaffold_required_prediction_file_count": _int(input_scaffold.get("required_prediction_file_count")),
        "input_scaffold_required_native_file_count": _int(input_scaffold.get("required_native_file_count")),
        "input_scaffold_required_ablation_file_count": _int(input_scaffold.get("required_ablation_file_count")),
        "input_scaffold_manifest_draft_csv": _text(input_scaffold.get("manifest_draft_csv")),
        "input_scaffold_calibration_draft_csv": _text(input_scaffold.get("calibration_draft_csv")),
        "input_inventory_status": input_inventory.get("inventory_status", "missing"),
        "input_inventory_ready_row_count": _int(input_inventory.get("ready_row_count")),
        "input_inventory_blocked_row_count": _int(input_inventory.get("blocked_row_count")),
        "input_inventory_present_file_count": _int(input_inventory.get("present_file_count")),
        "input_inventory_missing_file_count": _int(input_inventory.get("missing_file_count")),
        "input_inventory_present_prediction_file_count": _int(input_inventory.get("present_prediction_file_count")),
        "input_inventory_present_native_file_count": _int(input_inventory.get("present_native_file_count")),
        "input_inventory_present_ablation_layer_file_count": _int(input_inventory.get("present_ablation_layer_file_count")),
        "input_inventory_provenance_ready_row_count": _int(input_inventory.get("provenance_ready_row_count")),
        "input_inventory_calibration_ready_row_count": _int(input_inventory.get("calibration_ready_row_count")),
        "data_bundle_status": bundle.get("bundle_status", "missing"),
        "data_bundle_artifact_count": _int(bundle.get("artifact_count")),
        "dashboard_html_path": _artifact(args.out_html),
        "claim_boundary": (
            "Local readiness dashboard only. It consolidates internal gates, visual QC, and no-leak benchmark work; "
            "it does not prove current-target native accuracy, fetch structures, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["priority", "level", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Readiness Dashboard",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- dashboard_status: `{summary['dashboard_status']}`",
        f"- current_proven_level: `{summary['current_proven_level']}`",
        f"- next_unclosed_level: `{summary['next_unclosed_level']}`",
        f"- levels pass_or_ready/blocked_or_partial: `{summary['pass_or_ready_level_count']}/{summary['blocked_or_partial_level_count']}`",
        f"- PDB coordinate frame: `{summary['coordinate_frame_status']}` `{summary['coordinate_frame_pass_count']}/{summary['coordinate_frame_target_count']}` fixed-width errors `{summary['coordinate_frame_pre_fixed_width_parse_error_count']}->{summary['coordinate_frame_post_fixed_width_parse_error_count']}`",
        f"- structure shape sanity: `{summary['shape_sanity_status']}` `{summary['shape_sanity_pass_count']}/{summary['shape_sanity_target_count']}` max span/Rg/linearity `{summary['shape_sanity_max_observed_span_per_residue']}` / `{summary['shape_sanity_max_observed_radius_gyration_per_residue']}` / `{summary['shape_sanity_max_observed_chain_linearity']}`",
        f"- visual images pass/total: `{summary['image_pass_count']}/{summary['image_count']}`",
        f"- stereo-depth renders pass/total: `{summary['stereo_depth_pass_count']}/{summary['stereo_depth_count']}`",
        f"- turntable renders pass/total: `{summary['turntable_pass_count']}/{summary['turntable_count']}`",
        f"- publication/review images pass/total: `{summary['publication_image_pass_count']}/{summary['publication_image_count']}`",
        f"- molecular showcases: `{summary['molecular_showcase_count']}/{summary['target_count']}`",
        f"- molecular viewer smoke: `{summary['molecular_viewer_smoke_status']}` `{summary['molecular_viewer_pass_count']}/{summary['molecular_viewer_target_count']}`",
        f"- model-selection review: `{summary['model_selection_comparison_status']}` promotion `{summary['model_selection_promotion_status']}` review-both `{summary['model_selection_review_both_count']}/{summary['target_count']}`",
        f"- minimum edge pixels / luminance range: `{summary['min_estimated_edge_pixel_count']}` / `{summary['min_luminance_range']}`",
        f"- benchmark rows ready/blocked: `{summary['benchmark_ready_count']}/{summary['benchmark_blocked_count']}`",
        f"- evidence items missing/total: `{summary['missing_evidence_item_count']}/{summary['evidence_item_count']}`",
        f"- sidechain-native priority open/action: `{summary['sidechain_native_priority_open_action_count']}/{summary['sidechain_native_priority_action_count']}` first `{summary['sidechain_native_priority_first_open_action_id'] or '-'}`",
        f"- input scaffold: `{summary['input_scaffold_status']}` rows/files `{summary['input_scaffold_row_count']}/{summary['input_scaffold_required_total_file_count']}`",
        f"- input scaffold prediction/native/ablation files: `{summary['input_scaffold_required_prediction_file_count']}/{summary['input_scaffold_required_native_file_count']}/{summary['input_scaffold_required_ablation_file_count']}`",
        f"- input inventory: `{summary['input_inventory_status']}` ready/blocked rows `{summary['input_inventory_ready_row_count']}/{summary['input_inventory_blocked_row_count']}`",
        f"- input inventory present/missing files: `{summary['input_inventory_present_file_count']}/{summary['input_inventory_missing_file_count']}`",
        f"- html: `{summary['dashboard_html_path']}`",
        "",
        "## Levels",
        "",
        "| priority | level | status | target bar | current evidence | gap | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['level']}` | `{row['status']}` | {row['target_bar']} | "
            f"{row['current_evidence']} | `{row['gap'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = payload["rows"]
    cards: list[str] = []
    for row in rows:
        css_status = "ok" if row["status"] in {"pass", "ready"} else "warn"
        cards.append(
            "\n".join(
                [
                    f'<article class="card {css_status}">',
                    f'  <div class="kicker">{html.escape(str(row["level"]))}</div>',
                    f'  <h2>{html.escape(str(row["status"]))}</h2>',
                    f'  <p>{html.escape(str(row["target_bar"]))}</p>',
                    f'  <dl><dt>Evidence</dt><dd>{html.escape(str(row["current_evidence"]))}</dd></dl>',
                    f'  <dl><dt>Gap</dt><dd>{html.escape(str(row["gap"] or "-"))}</dd></dl>',
                    f'  <dl><dt>Next</dt><dd>{html.escape(str(row["next_action"]))}</dd></dl>',
                    f'  <code>{html.escape(str(row["artifact"]))}</code>',
                    "</article>",
                ]
            )
        )
    missing_by_class = summary.get("missing_evidence_by_class") or {}
    missing_items = "".join(
        f"<li><span>{html.escape(str(key))}</span><strong>{html.escape(str(value))}</strong></li>"
        for key, value in sorted(missing_by_class.items())
    )
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>CASP17 Readiness Dashboard</title>",
        "  <style>",
        "    :root{color-scheme:dark;--bg:#020617;--panel:#07111f;--line:#1e293b;--text:#f8fafc;--muted:#94a3b8;--ok:#86efac;--warn:#fbbf24}",
        "    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}",
        "    header{padding:24px;border-bottom:1px solid var(--line);background:#07111f} h1{margin:0 0 10px;font-size:28px;letter-spacing:0}",
        "    .summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.stat{border:1px solid var(--line);border-radius:8px;padding:12px;background:#0b1220}.stat span{display:block;color:var(--muted)}.stat strong{font-size:20px}",
        "    main{padding:22px;display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}.card{border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:16px;min-width:0}.card.ok{border-color:#14532d}.card.warn{border-color:#854d0e}.kicker{color:var(--muted);text-transform:uppercase;font-size:12px}.card h2{margin:4px 0 10px;font-size:22px}.card.ok h2{color:var(--ok)}.card.warn h2{color:var(--warn)} dl{margin:10px 0}dt{color:var(--muted)}dd{margin:2px 0 0;overflow-wrap:anywhere}code{display:block;margin-top:12px;color:#bae6fd;white-space:pre-wrap;overflow-wrap:anywhere}",
        "    section{padding:0 22px 22px}.missing{border:1px solid var(--line);border-radius:8px;background:#07111f;padding:16px}.missing ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;list-style:none;padding:0;margin:10px 0 0}.missing li{display:flex;justify-content:space-between;gap:12px;border:1px solid var(--line);border-radius:6px;padding:8px;background:#0b1220}",
        "  </style>",
        "</head>",
        "<body>",
        "  <header>",
        "    <h1>CASP17 Readiness Dashboard</h1>",
        '    <div class="summary">',
        f'      <div class="stat"><span>current proven</span><strong>{html.escape(str(summary["current_proven_level"]))}</strong></div>',
        f'      <div class="stat"><span>next level</span><strong>{html.escape(str(summary["next_unclosed_level"]))}</strong></div>',
        f'      <div class="stat"><span>PDB frame</span><strong>{html.escape(str(summary["coordinate_frame_status"]))}</strong></div>',
        f'      <div class="stat"><span>shape sanity</span><strong>{html.escape(str(summary["shape_sanity_status"]))}</strong></div>',
        f'      <div class="stat"><span>visual QC</span><strong>{summary["image_pass_count"]}/{summary["image_count"]}</strong></div>',
        f'      <div class="stat"><span>stereo depth</span><strong>{summary["stereo_depth_pass_count"]}/{summary["stereo_depth_count"]}</strong></div>',
        f'      <div class="stat"><span>turntable</span><strong>{summary["turntable_pass_count"]}/{summary["turntable_count"]}</strong></div>',
        f'      <div class="stat"><span>review images</span><strong>{summary["publication_image_pass_count"]}/{summary["publication_image_count"]}</strong></div>',
        f'      <div class="stat"><span>showcases</span><strong>{summary["molecular_showcase_count"]}/{summary["target_count"]}</strong></div>',
        f'      <div class="stat"><span>viewer smoke</span><strong>{html.escape(str(summary["molecular_viewer_smoke_status"]))}</strong></div>',
        f'      <div class="stat"><span>model review</span><strong>{html.escape(str(summary["model_selection_review_both_count"]))}/{html.escape(str(summary["target_count"]))}</strong></div>',
        f'      <div class="stat"><span>min edge</span><strong>{summary["min_estimated_edge_pixel_count"]}</strong></div>',
        f'      <div class="stat"><span>benchmark rows</span><strong>{summary["benchmark_ready_count"]}/{summary["benchmark_row_count"]}</strong></div>',
        f'      <div class="stat"><span>evidence missing</span><strong>{summary["missing_evidence_item_count"]}</strong></div>',
        f'      <div class="stat"><span>sidechain-native</span><strong>{summary["sidechain_native_priority_open_action_count"]}/{summary["sidechain_native_priority_action_count"]}</strong></div>',
        "    </div>",
        "  </header>",
        "  <main>",
        *cards,
        "  </main>",
        "  <section>",
        '    <div class="missing">',
        "      <h2>Missing Win-Tier Evidence</h2>",
        f"      <p>{summary['missing_evidence_item_count']} of {summary['evidence_item_count']} required evidence items are still missing.</p>",
        f"      <ul>{missing_items}</ul>",
        "    </div>",
        "  </section>",
        "  <section>",
        '    <p style="color:#94a3b8">Local dashboard only. No external data fetch, no predictor handoff, no native/current-target accuracy claim, no CASP submission.</p>',
        "  </section>",
        "</body>",
        "</html>",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _artifact(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a consolidated local CASP17 readiness dashboard.")
    parser.add_argument("--win-rubric-json", default=DEFAULT_WIN_RUBRIC_JSON)
    parser.add_argument("--competitive-readiness-json", default=DEFAULT_COMPETITIVE_READINESS_JSON)
    parser.add_argument("--threshold-json", default=DEFAULT_THRESHOLD_JSON)
    parser.add_argument("--closure-json", default=DEFAULT_CLOSURE_JSON)
    parser.add_argument("--coordinate-frame-json", default=DEFAULT_COORDINATE_FRAME_JSON)
    parser.add_argument("--shape-sanity-json", default=DEFAULT_SHAPE_SANITY_JSON)
    parser.add_argument("--image-quality-json", default=DEFAULT_IMAGE_QUALITY_JSON)
    parser.add_argument("--publication-figure-json", default=DEFAULT_PUBLICATION_FIGURE_JSON)
    parser.add_argument("--model-comparison-json", default=DEFAULT_MODEL_COMPARISON_JSON)
    parser.add_argument("--molecular-viewer-smoke-json", default=DEFAULT_MOLECULAR_VIEWER_SMOKE_JSON)
    parser.add_argument("--benchmark-dashboard-json", default=DEFAULT_BENCHMARK_DASHBOARD_JSON)
    parser.add_argument("--evidence-fill-kit-json", default=DEFAULT_EVIDENCE_FILL_KIT_JSON)
    parser.add_argument("--input-scaffold-json", default=DEFAULT_INPUT_SCAFFOLD_JSON)
    parser.add_argument("--input-inventory-json", default=DEFAULT_INPUT_INVENTORY_JSON)
    parser.add_argument("--data-bundle-json", default=DEFAULT_DATA_BUNDLE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    payload["summary"]["dashboard_html_path"] = _write_html(args.out_html, payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
