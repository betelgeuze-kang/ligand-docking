#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WIN_RUBRIC_JSON = "runs/casp17_win_readiness_rubric_packet_current.json"
DEFAULT_COMPETITIVE_READINESS_JSON = "runs/casp17_competitive_readiness_packet_current.json"
DEFAULT_MOLECULAR_VIEWER_JSON = "runs/casp17_molecular_viewer_packet_current.json"
DEFAULT_MOLECULAR_VIEWER_SMOKE_JSON = "runs/casp17_molecular_viewer_smoke_packet_current.json"
DEFAULT_STRUCTURE_IMAGE_QUALITY_JSON = "runs/casp17_structure_image_quality_packet_current.json"
DEFAULT_PUBLICATION_FIGURE_JSON = "runs/casp17_publication_figure_packet_current.json"
DEFAULT_ALL_ATOM_QUALITY_JSON = "runs/casp17_all_atom_quality_packet_current.json"
DEFAULT_SIDECHAIN_QUALITY_JSON = "runs/casp17_sidechain_quality_packet_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_REFINEMENT_ABLATION_JSON = "runs/casp17_refinement_ablation_packet_current.json"
DEFAULT_MODEL_SELECTION_CALIBRATION_JSON = "runs/casp17_model_selection_calibration_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_threshold_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_threshold_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_threshold_packet_current.md"

OFFICIAL_SOURCES = [
    {
        "name": "CASP17 format and submission rules",
        "url": "https://predictioncenter.org/casp17/index.cgi?page=format",
        "use": "TS format, one target per file, up to five ranked models, model 1 focus, B-factor confidence, SCORE/QSCORE.",
    },
    {
        "name": "CASP17 target list",
        "url": "https://predictioncenter.org/casp17/targetlist.cgi",
        "use": "Current target classes, target naming, deadlines, and stoichiometry context.",
    },
    {
        "name": "CASP16 monomer assessment",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12157625/",
        "use": "Recent monomer assessment dimensions including GDT_HA, lDDT, MolProbity, QSE, CAD/GDC sidechain measures.",
    },
    {
        "name": "CASP16 complex/interface assessment",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12750043/",
        "use": "Recent complex/interface dimensions including DockQ, ICS, IPS, QSbest, TM-score, lDDT.",
    },
]

THRESHOLDS = {
    "submission_go_fraction": {"competitive": 1.0, "win": 1.0},
    "ranked_top5_fraction": {"competitive": 1.0, "win": 1.0},
    "visual_review_fraction": {"competitive": 1.0, "win": 1.0},
    "severe_clash_count": {"competitive": 0.0, "win": 0.0},
    "max_soft_clashscore_per_1000_atoms": {"competitive": 5.0, "win": 1.0},
    "min_heavy_atom_completion_fraction": {"competitive": 0.99, "win": 0.995},
    "min_sidechain_completion_fraction": {"competitive": 0.98, "win": 0.995},
    "min_rotamer_proxy_pass_fraction": {"competitive": 0.95, "win": 0.98},
    "sidechain_native_lddt": {"competitive": 0.75, "win": 0.82},
    "sidechain_native_rmsd_a": {"competitive": 2.5, "win": 1.8},
    "historical_monomer_rows": {"competitive": 10.0, "win": 25.0},
    "historical_complex_rows": {"competitive": 5.0, "win": 15.0},
    "monomer_mean_tm": {"competitive": 0.82, "win": 0.90},
    "monomer_mean_gdt_ts": {"competitive": 0.72, "win": 0.80},
    "monomer_mean_ca_lddt": {"competitive": 0.78, "win": 0.85},
    "monomer_correct_fold_rate": {"competitive": 0.90, "win": 0.95},
    "complex_mean_tm": {"competitive": 0.68, "win": 0.78},
    "complex_interface_f1": {"competitive": 0.45, "win": 0.58},
    "complex_dockq": {"competitive": 0.45, "win": 0.58},
    "final_not_worse_rate": {"competitive": 0.95, "win": 1.0},
    "final_improved_rate": {"competitive": 0.35, "win": 0.60},
    "mean_delta_tm": {"competitive": 0.0, "win": 0.01},
    "mean_delta_lddt": {"competitive": 0.0, "win": 0.015},
    "selection_loss": {"competitive": 0.08, "win": 0.04},
    "score_native_correlation": {"competitive": 0.55, "win": 0.70},
    "qscore_interface_correlation": {"competitive": 0.45, "win": 0.65},
    "confidence_ece": {"competitive": 0.15, "win": 0.08},
}

STANDARD_LEVELS = [
    {
        "level": "submission_floor",
        "meaning": "CASP portal에 올릴 수 있는 로컬 형식/게이트 최소선",
        "must_hold": "16/16 current protein targets pass TS format, sequence/chain coverage, confidence, scorecard, shape sanity, and submission gate.",
        "not_enough_for": "competitive or win-tier native accuracy claims",
    },
    {
        "level": "review_quality",
        "meaning": "사람이 구조를 실제 분자구조 이미지처럼 검토할 수 있는 수준",
        "must_hold": "16/16 local internal viewer, PyMOL/studio/surface/confidence/QC renders, stereo-depth, turntable, publication/review/showcase figures, and image-quality smoke pass.",
        "not_enough_for": "native correctness, sidechain correctness, or interface correctness",
    },
    {
        "level": "competitive_floor",
        "meaning": "CASP에서 의미 있는 비교가 가능한 내부 baseline 수준",
        "must_hold": "zero severe clashes, very low soft-clash burden, near-complete heavy atoms and sidechains, plus no-leak sidechain/native benchmark evidence.",
        "not_enough_for": "top group or winner claim",
    },
    {
        "level": "win_tier",
        "meaning": "우승권을 주장하기 전에 내부 no-leak 벤치마크에서 넘어야 하는 기준",
        "must_hold": ">=25 monomer and >=15 complex no-leak historical rows, monomer mean TM>=0.90/GDT_TS>=0.80/CA_lDDT>=0.85, complex interface F1 and DockQ-like >=0.58, no-worse final refinement, low model-selection loss, and calibrated confidence.",
        "not_enough_for": "official CASP ranking before external assessment",
    },
]


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


def _rows_by_dimension(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("dimension"):
            result[str(row["dimension"])] = row
    return result


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _ratio(numerator: Any, denominator: Any) -> float:
    den = _float(denominator)
    return round(_float(numerator) / den, 6) if den else 0.0


def _status_from_bool(value: bool) -> str:
    return "pass" if value else "blocked"


def _threshold_status(
    *,
    value: float,
    threshold: float,
    direction: str,
    evidence_ready: bool,
    partial_ready: bool = False,
) -> str:
    if not evidence_ready:
        return "partial" if partial_ready else "blocked_input"
    if direction == "max":
        return "pass" if value <= threshold else "blocked"
    return "pass" if value >= threshold else "blocked"


def _row(
    *,
    priority: int,
    level: str,
    dimension: str,
    metric: str,
    current_value: float,
    direction: str,
    evidence_ready: bool,
    evidence_kind: str,
    current_status: str,
    evidence_source: str,
    blocker: str,
    next_action: str,
    partial_ready: bool = False,
    note: str = "",
) -> dict[str, Any]:
    thresholds = THRESHOLDS[metric]
    competitive = float(thresholds["competitive"])
    win = float(thresholds["win"])
    target = win if level == "win_tier" else competitive
    status = _threshold_status(
        value=current_value,
        threshold=target,
        direction=direction,
        evidence_ready=evidence_ready,
        partial_ready=partial_ready,
    )
    return {
        "priority": priority,
        "level": level,
        "dimension": dimension,
        "metric": metric,
        "direction": direction,
        "competitive_floor_threshold": competitive,
        "win_tier_threshold": win,
        "active_threshold": target,
        "current_value": round(current_value, 6),
        "threshold_status": status,
        "current_status": current_status,
        "evidence_ready": bool(evidence_ready),
        "partial_ready": bool(partial_ready),
        "evidence_kind": evidence_kind,
        "evidence_source": evidence_source,
        "blocker": blocker,
        "next_action": next_action,
        "note": note,
    }


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
        fieldnames = ["level", "dimension", "metric", "threshold_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    win = _summary(_read_json(args.win_rubric_json))
    competitive_payload = _read_json(args.competitive_readiness_json)
    competitive = _summary(competitive_payload)
    competitive_rows = _rows_by_dimension(competitive_payload)
    viewer = _summary(_read_json(args.molecular_viewer_json))
    viewer_smoke = _summary(_read_json(args.molecular_viewer_smoke_json))
    image_quality = _summary(_read_json(args.structure_image_quality_json))
    publication_figure = _summary(_read_json(args.publication_figure_json))
    all_atom = _summary(_read_json(args.all_atom_quality_json))
    sidechain_quality = _summary(_read_json(args.sidechain_quality_json))
    sidechain_native = _summary(_read_json(args.sidechain_native_benchmark_json))
    historical = _summary(_read_json(args.historical_benchmark_json))
    ablation = _summary(_read_json(args.refinement_ablation_json))
    calibration = _summary(_read_json(args.model_selection_calibration_json))

    target_count = _int(win.get("target_count") or competitive.get("target_count") or viewer.get("target_count"))
    submission_ready = competitive.get("submission_readiness_status") == "pass" and target_count > 0
    top5_ready = competitive_rows.get("top5_ranked_model_depth", {}).get("status") == "pass"
    viewer_ready = viewer.get("ready_count") == target_count and viewer.get("external_network_default") == "disabled"
    stereo_depth_ready = (
        _int(image_quality.get("stereo_depth_count")) == target_count
        and _int(image_quality.get("stereo_depth_pass_count")) == target_count
    )
    turntable_ready = (
        _int(image_quality.get("turntable_count")) == target_count
        and _int(image_quality.get("turntable_pass_count")) == target_count
    )
    image_ready = (
        image_quality.get("image_quality_status") == "pass"
        and _int(image_quality.get("target_complete_count")) == target_count
        and stereo_depth_ready
        and turntable_ready
    )
    viewer_smoke_ready = viewer_smoke.get("viewer_smoke_status") == "pass"
    publication_figure_ready = (
        publication_figure.get("publication_figure_status") == "pass"
        and _int(publication_figure.get("target_complete_count")) == target_count
        and _int(publication_figure.get("inspection_poster_count")) == target_count
        and _int(publication_figure.get("scene_poster_count")) == target_count
        and _int(publication_figure.get("review_board_count")) == target_count
        and _int(publication_figure.get("molecular_showcase_count")) == target_count
    )
    visual_ready = bool(
        target_count
        and viewer_ready
        and viewer_smoke_ready
        and image_ready
        and publication_figure_ready
        and viewer.get("webgl_runtime") in {"internal_canvas_runtime", "local_3dmol_bundle"}
    )

    all_atom_ready = all_atom.get("all_atom_quality_status") == "pass"
    sidechain_ready = sidechain_quality.get("sidechain_quality_status") == "pass"
    local_steric_ready = all_atom_ready and sidechain_ready
    sidechain_native_ready = sidechain_native.get("sidechain_native_benchmark_status") == "pass"
    historical_ready = historical.get("historical_benchmark_status") == "pass"
    monomer_ready = historical.get("monomer_win_tier_status") == "pass"
    complex_ready = historical.get("complex_win_tier_status") == "pass"
    ablation_ready = ablation.get("refinement_ablation_status") == "pass"
    calibration_ready = calibration.get("calibration_status") == "pass"

    rows = [
        _row(
            priority=1,
            level="submission_floor",
            dimension="official_submission_gate",
            metric="submission_go_fraction",
            current_value=1.0 if submission_ready else 0.0,
            direction="min",
            evidence_ready=submission_ready,
            evidence_kind="current_target_internal_gate",
            current_status=str(competitive.get("submission_readiness_status", "missing")),
            evidence_source=_artifact(args.competitive_readiness_json),
            blocker="" if submission_ready else "submission_readiness_not_pass",
            next_action="Keep runtime-only author code handling; upload only after explicit external-state confirmation.",
        ),
        _row(
            priority=2,
            level="submission_floor",
            dimension="ranked_top5_depth",
            metric="ranked_top5_fraction",
            current_value=1.0 if top5_ready else 0.0,
            direction="min",
            evidence_ready=top5_ready,
            evidence_kind="current_target_internal_gate",
            current_status=str(competitive_rows.get("top5_ranked_model_depth", {}).get("status", "missing")),
            evidence_source=_artifact(args.competitive_readiness_json),
            blocker="" if top5_ready else "ranked_top5_depth_not_pass",
            next_action="Regenerate top-5 candidates and gate all current targets after each predictor/ranker change.",
        ),
        _row(
            priority=3,
            level="review_quality",
            dimension="visual_molecular_review",
            metric="visual_review_fraction",
            current_value=1.0 if visual_ready else 0.0,
            direction="min",
            evidence_ready=visual_ready,
            evidence_kind="current_target_visual_gate",
            current_status=(
                f"viewer={viewer.get('ready_count', 0)}/{target_count}; "
                f"viewer_smoke={viewer_smoke.get('viewer_smoke_status', 'missing')}; "
                f"image={image_quality.get('image_quality_status', 'missing')}; "
                f"stereo_depth={image_quality.get('stereo_depth_pass_count', 0)}/{target_count}; "
                f"turntable={image_quality.get('turntable_pass_count', 0)}/{target_count}; "
                f"publication_figure={publication_figure.get('publication_figure_status', 'missing')}; "
                f"scene_posters={publication_figure.get('scene_poster_count', 0)}/{target_count}; "
                f"inspection_posters={publication_figure.get('inspection_poster_count', 0)}/{target_count}; "
                f"review_boards={publication_figure.get('review_board_count', 0)}/{target_count}; "
                f"showcases={publication_figure.get('molecular_showcase_count', 0)}/{target_count}; "
                f"runtime={viewer.get('webgl_runtime', 'missing')}"
            ),
            evidence_source=f"{_artifact(args.molecular_viewer_json)};{_artifact(args.molecular_viewer_smoke_json)};{_artifact(args.structure_image_quality_json)};{_artifact(args.publication_figure_json)}",
            blocker="" if visual_ready else "viewer_smoke_image_quality_stereo_depth_turntable_publication_scene_inspection_review_board_or_showcase_not_pass",
            next_action="Keep internal canvas viewer, high-resolution presentation plates, stereo-depth renders, turntable review strips, 4K publication figures, molecular scene posters, inspection posters, review boards, and showcases current after coordinate changes.",
        ),
        _row(
            priority=4,
            level="competitive_floor",
            dimension="local_all_atom_qc",
            metric="severe_clash_count",
            current_value=_float(all_atom.get("total_severe_clash_count")),
            direction="max",
            evidence_ready=local_steric_ready,
            evidence_kind="current_target_internal_proxy",
            current_status=f"all_atom={all_atom.get('all_atom_quality_status', 'missing')}; sidechain={sidechain_quality.get('sidechain_quality_status', 'missing')}",
            evidence_source=f"{_artifact(args.all_atom_quality_json)};{_artifact(args.sidechain_quality_json)}",
            blocker="" if local_steric_ready else "local_all_atom_qc_not_pass",
            next_action="Keep zero severe clashes and low soft-clash burden across every selected TS model.",
            note="Local proxy only; does not prove native accuracy.",
        ),
        _row(
            priority=5,
            level="competitive_floor",
            dimension="local_all_atom_qc",
            metric="max_soft_clashscore_per_1000_atoms",
            current_value=_float(all_atom.get("max_soft_clashscore_per_1000_atoms")),
            direction="max",
            evidence_ready=local_steric_ready,
            evidence_kind="current_target_internal_proxy",
            current_status=f"soft={all_atom.get('total_soft_clash_count', 'missing')}; max_soft_clashscore={all_atom.get('max_soft_clashscore_per_1000_atoms', 'missing')}",
            evidence_source=_artifact(args.all_atom_quality_json),
            blocker="" if local_steric_ready else "local_all_atom_qc_not_pass",
            next_action="Reduce current-target soft contacts while preserving backbone continuity and sequence exactness.",
            note="Win threshold is stricter than current competitive floor.",
        ),
        _row(
            priority=6,
            level="competitive_floor",
            dimension="local_all_atom_qc",
            metric="min_heavy_atom_completion_fraction",
            current_value=_float(
                all_atom.get("min_heavy_atom_completion_fraction"),
                1.0 if all_atom_ready else 0.0,
            ),
            direction="min",
            evidence_ready=local_steric_ready,
            evidence_kind="current_target_internal_proxy",
            current_status=f"min_heavy_atom_completion={all_atom.get('min_heavy_atom_completion_fraction', 'missing')}",
            evidence_source=_artifact(args.all_atom_quality_json),
            blocker="" if local_steric_ready else "local_heavy_atom_completion_not_pass",
            next_action="Keep heavy-atom completion at or above win-tier threshold for every selected current-target model.",
            note="Local completion proxy only; does not prove all-atom native placement.",
        ),
        _row(
            priority=7,
            level="competitive_floor",
            dimension="local_sidechain_qc",
            metric="min_sidechain_completion_fraction",
            current_value=_float(
                sidechain_quality.get("min_complete_sidechain_residue_fraction"),
                1.0 if sidechain_ready else 0.0,
            ),
            direction="min",
            evidence_ready=local_steric_ready,
            evidence_kind="current_target_internal_proxy",
            current_status=(
                f"min_complete_sidechain_fraction="
                f"{sidechain_quality.get('min_complete_sidechain_residue_fraction', 'missing')}"
            ),
            evidence_source=_artifact(args.sidechain_quality_json),
            blocker="" if local_steric_ready else "local_sidechain_completion_not_pass",
            next_action="Keep every current-target sidechain complete after each refinement/ranking change.",
            note="Local completion proxy only; native sidechain accuracy is covered by the no-leak benchmark rows.",
        ),
        _row(
            priority=8,
            level="competitive_floor",
            dimension="local_sidechain_qc",
            metric="min_rotamer_proxy_pass_fraction",
            current_value=_float(
                sidechain_quality.get("min_rotamer_proxy_pass_fraction"),
                1.0 if sidechain_ready else 0.0,
            ),
            direction="min",
            evidence_ready=local_steric_ready,
            evidence_kind="current_target_internal_proxy",
            current_status=f"min_rotamer_proxy_pass={sidechain_quality.get('min_rotamer_proxy_pass_fraction', 'missing')}",
            evidence_source=_artifact(args.sidechain_quality_json),
            blocker="" if local_steric_ready else "local_rotamer_proxy_not_pass",
            next_action="Keep rotamer proxy pass fraction above the win-tier band before promoting MODEL 1.",
            note="Internal rotamer-frame proxy only; not official MolProbity.",
        ),
        _row(
            priority=9,
            level="competitive_floor",
            dimension="sidechain_native_quality",
            metric="sidechain_native_lddt",
            current_value=_float(sidechain_native.get("mean_sidechain_lddt_proxy")),
            direction="min",
            evidence_ready=sidechain_native_ready,
            partial_ready=local_steric_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"sidechain_native={sidechain_native.get('sidechain_native_benchmark_status', 'missing')}; rows={sidechain_native.get('pass_count', 0)}/{sidechain_native.get('benchmark_count', 0)}",
            evidence_source=_artifact(args.sidechain_native_benchmark_json),
            blocker="" if sidechain_native_ready else "sidechain_native_benchmark_missing_or_blocked",
            next_action="Populate cleared historical native sidechain benchmark rows and pass atom/residue exactness plus lDDT/RMSD thresholds.",
        ),
        _row(
            priority=10,
            level="competitive_floor",
            dimension="sidechain_native_quality",
            metric="sidechain_native_rmsd_a",
            current_value=_float(sidechain_native.get("mean_sidechain_rmsd_A")),
            direction="max",
            evidence_ready=sidechain_native_ready,
            partial_ready=local_steric_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=(
                f"sidechain_native={sidechain_native.get('sidechain_native_benchmark_status', 'missing')}; "
                f"mean_RMSD_A={sidechain_native.get('mean_sidechain_rmsd_A', 0.0)}"
            ),
            evidence_source=_artifact(args.sidechain_native_benchmark_json),
            blocker="" if sidechain_native_ready else "sidechain_native_benchmark_missing_or_blocked",
            next_action="Populate cleared historical sidechain-native rows and tune rotamer/repack layers against RMSD and lDDT together.",
        ),
        _row(
            priority=11,
            level="win_tier",
            dimension="monomer_native_accuracy",
            metric="historical_monomer_rows",
            current_value=_float(historical.get("monomer_benchmark_count")),
            direction="min",
            evidence_ready=historical_ready and monomer_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"historical={historical.get('historical_benchmark_status', 'missing')}; monomer={historical.get('monomer_win_tier_status', 'missing')}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if monomer_ready else (str(historical.get("manifest_blockers") or "historical_monomer_rows_missing")),
            next_action="Add no-leak CASP-like historical monomer prediction/native pairs until the ready row count and accuracy bands are stable.",
        ),
        _row(
            priority=12,
            level="win_tier",
            dimension="monomer_native_accuracy",
            metric="monomer_mean_tm",
            current_value=_float(historical.get("mean_tm_score_proxy")),
            direction="min",
            evidence_ready=historical_ready and monomer_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"mean_TM={historical.get('mean_tm_score_proxy', 0.0)}; mean_GDT_TS={historical.get('mean_gdt_ts_proxy', 0.0)}; mean_CA_lDDT={historical.get('mean_ca_lddt_proxy', 0.0)}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if monomer_ready else "monomer_native_accuracy_missing_or_below_threshold",
            next_action="Tune internal generation/ranking against no-leak historical monomer TM/GDT/lDDT before claiming win-tier monomer accuracy.",
        ),
        _row(
            priority=13,
            level="win_tier",
            dimension="monomer_native_accuracy",
            metric="monomer_mean_gdt_ts",
            current_value=_float(historical.get("mean_gdt_ts_proxy")),
            direction="min",
            evidence_ready=historical_ready and monomer_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"mean_GDT_TS={historical.get('mean_gdt_ts_proxy', 0.0)}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if monomer_ready else "monomer_gdt_ts_missing_or_below_threshold",
            next_action="Tune backbone generation and ranking until no-leak monomer GDT_TS clears the win-tier band.",
        ),
        _row(
            priority=14,
            level="win_tier",
            dimension="monomer_native_accuracy",
            metric="monomer_mean_ca_lddt",
            current_value=_float(historical.get("mean_ca_lddt_proxy")),
            direction="min",
            evidence_ready=historical_ready and monomer_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"mean_CA_lDDT={historical.get('mean_ca_lddt_proxy', 0.0)}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if monomer_ready else "monomer_ca_lddt_missing_or_below_threshold",
            next_action="Tune local geometry/refinement so no-leak historical CA-lDDT clears the win-tier band.",
        ),
        _row(
            priority=15,
            level="win_tier",
            dimension="monomer_native_accuracy",
            metric="monomer_correct_fold_rate",
            current_value=_ratio(historical.get("monomer_pass_count"), historical.get("monomer_benchmark_count")),
            direction="min",
            evidence_ready=historical_ready and monomer_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=(
                f"monomer_pass={historical.get('monomer_pass_count', 0)}/"
                f"{historical.get('monomer_benchmark_count', 0)}"
            ),
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if monomer_ready else "monomer_correct_fold_rate_missing_or_below_threshold",
            next_action="Increase no-leak monomer benchmark coverage and keep almost every historical monomer above fold-quality thresholds.",
        ),
        _row(
            priority=16,
            level="win_tier",
            dimension="complex_interface_accuracy",
            metric="historical_complex_rows",
            current_value=_float(historical.get("complex_benchmark_count")),
            direction="min",
            evidence_ready=historical_ready and complex_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"historical={historical.get('historical_benchmark_status', 'missing')}; complex={historical.get('complex_win_tier_status', 'missing')}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if complex_ready else (str(historical.get("manifest_blockers") or "historical_complex_rows_missing")),
            next_action="Add no-leak CASP-like complex/interface prediction/native pairs with stoichiometry and chain exactness.",
        ),
        _row(
            priority=17,
            level="win_tier",
            dimension="complex_interface_accuracy",
            metric="complex_mean_tm",
            current_value=_float(historical.get("mean_tm_score_proxy")),
            direction="min",
            evidence_ready=historical_ready and complex_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"mean_complex_TM_proxy={historical.get('mean_tm_score_proxy', 0.0)}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if complex_ready else "complex_tm_missing_or_below_threshold",
            next_action="Tune multimer chain placement so no-leak complex global fold quality clears the win-tier band.",
        ),
        _row(
            priority=18,
            level="win_tier",
            dimension="complex_interface_accuracy",
            metric="complex_interface_f1",
            current_value=_float(historical.get("mean_complex_interface_f1_proxy")),
            direction="min",
            evidence_ready=historical_ready and complex_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=f"mean_TM={historical.get('mean_tm_score_proxy', 0.0)}; mean_interface_F1={historical.get('mean_complex_interface_f1_proxy', 0.0)}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if complex_ready else "complex_interface_accuracy_missing_or_below_threshold",
            next_action="Tune rigid-body/interface sampling and QSCORE calibration against no-leak historical complex interfaces.",
        ),
        _row(
            priority=19,
            level="win_tier",
            dimension="complex_interface_accuracy",
            metric="complex_dockq",
            current_value=_float(historical.get("mean_complex_dockq_proxy")),
            direction="min",
            evidence_ready=historical_ready and complex_ready,
            evidence_kind="no_leak_historical_native_benchmark",
            current_status=(
                f"mean_DockQ_proxy={historical.get('mean_complex_dockq_proxy', 0.0)}; "
                f"mean_QSbest_proxy={historical.get('mean_complex_qsbest_proxy', 0.0)}; "
                f"mean_IPS_proxy={historical.get('mean_complex_interface_patch_jaccard_proxy', 0.0)}"
            ),
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if complex_ready else "complex_dockq_or_interface_patch_quality_missing_or_below_threshold",
            next_action="Tune interface sampling, chain placement, and QSCORE calibration against DockQ/QSbest/IPS-style no-leak complex metrics.",
        ),
        _row(
            priority=20,
            level="win_tier",
            dimension="refinement_ablation_native_evidence",
            metric="final_not_worse_rate",
            current_value=_ratio(ablation.get("final_not_worse_count"), ablation.get("ablation_group_count")),
            direction="min",
            evidence_ready=ablation_ready,
            evidence_kind="no_leak_historical_native_ablation",
            current_status=f"ablation={ablation.get('refinement_ablation_status', 'missing')}; groups={ablation.get('ablation_group_pass_count', 0)}/{ablation.get('ablation_group_count', 0)}",
            evidence_source=_artifact(args.refinement_ablation_json),
            blocker="" if ablation_ready else (str(ablation.get("manifest_blockers") or "refinement_ablation_missing_or_blocked")),
            next_action="Populate layer-specific historical predictions and prove the final layer is no-worse than baseline.",
        ),
        _row(
            priority=21,
            level="win_tier",
            dimension="refinement_ablation_native_evidence",
            metric="final_improved_rate",
            current_value=_ratio(ablation.get("final_improved_count"), ablation.get("ablation_group_count")),
            direction="min",
            evidence_ready=ablation_ready,
            evidence_kind="no_leak_historical_native_ablation",
            current_status=(
                f"final_improved={ablation.get('final_improved_count', 0)}/"
                f"{ablation.get('ablation_group_count', 0)}"
            ),
            evidence_source=_artifact(args.refinement_ablation_json),
            blocker="" if ablation_ready else (str(ablation.get("manifest_blockers") or "refinement_ablation_missing_or_blocked")),
            next_action="Tune refinement layers until the final layer improves a majority of no-leak benchmark groups.",
        ),
        _row(
            priority=22,
            level="win_tier",
            dimension="refinement_ablation_native_evidence",
            metric="mean_delta_tm",
            current_value=_float(ablation.get("mean_delta_tm_score_proxy")),
            direction="min",
            evidence_ready=ablation_ready,
            evidence_kind="no_leak_historical_native_ablation",
            current_status=f"mean_delta_TM={ablation.get('mean_delta_tm_score_proxy', 0.0)}",
            evidence_source=_artifact(args.refinement_ablation_json),
            blocker="" if ablation_ready else (str(ablation.get("manifest_blockers") or "refinement_ablation_missing_or_blocked")),
            next_action="Measure each refinement layer against historical natives and require positive final TM delta.",
        ),
        _row(
            priority=23,
            level="win_tier",
            dimension="refinement_ablation_native_evidence",
            metric="mean_delta_lddt",
            current_value=_float(ablation.get("mean_delta_ca_lddt_proxy")),
            direction="min",
            evidence_ready=ablation_ready,
            evidence_kind="no_leak_historical_native_ablation",
            current_status=f"mean_delta_CA_lDDT={ablation.get('mean_delta_ca_lddt_proxy', 0.0)}",
            evidence_source=_artifact(args.refinement_ablation_json),
            blocker="" if ablation_ready else (str(ablation.get("manifest_blockers") or "refinement_ablation_missing_or_blocked")),
            next_action="Measure each refinement layer against historical natives and require positive final CA-lDDT delta.",
        ),
        _row(
            priority=24,
            level="win_tier",
            dimension="model_selection_calibration",
            metric="selection_loss",
            current_value=_float(calibration.get("mean_selection_loss")),
            direction="max",
            evidence_ready=calibration_ready,
            evidence_kind="no_leak_historical_model_selection",
            current_status=f"calibration={calibration.get('calibration_status', 'missing')}; rows={calibration.get('calibration_pass_count', 0)}/{calibration.get('calibration_row_count', 0)}",
            evidence_source=_artifact(args.model_selection_calibration_json),
            blocker="" if calibration_ready else "model_selection_calibration_missing_or_blocked",
            next_action="Populate no-leak selected-vs-oracle top-5 calibration rows and minimize MODEL 1 selection loss.",
        ),
        _row(
            priority=25,
            level="win_tier",
            dimension="model_selection_calibration",
            metric="score_native_correlation",
            current_value=_float(calibration.get("score_native_correlation")),
            direction="min",
            evidence_ready=calibration_ready,
            evidence_kind="no_leak_historical_model_selection",
            current_status=f"score_native_correlation={calibration.get('score_native_correlation', 0.0)}",
            evidence_source=_artifact(args.model_selection_calibration_json),
            blocker="" if calibration_ready else "model_selection_calibration_missing_or_blocked",
            next_action="Calibrate SCORE against no-leak native monomer/global metrics until correlation clears the win-tier band.",
        ),
        _row(
            priority=26,
            level="win_tier",
            dimension="model_selection_calibration",
            metric="qscore_interface_correlation",
            current_value=_float(calibration.get("qscore_interface_correlation")),
            direction="min",
            evidence_ready=calibration_ready,
            evidence_kind="no_leak_historical_model_selection",
            current_status=f"qscore_interface_correlation={calibration.get('qscore_interface_correlation', 0.0)}",
            evidence_source=_artifact(args.model_selection_calibration_json),
            blocker="" if calibration_ready else "model_selection_calibration_missing_or_blocked",
            next_action="Calibrate QSCORE against no-leak complex interface metrics before using it for MODEL 1 promotion.",
        ),
        _row(
            priority=27,
            level="win_tier",
            dimension="model_selection_calibration",
            metric="confidence_ece",
            current_value=_float(calibration.get("confidence_ece")),
            direction="max",
            evidence_ready=calibration_ready,
            evidence_kind="no_leak_historical_model_selection",
            current_status=f"confidence_ece={calibration.get('confidence_ece', 0.0)}",
            evidence_source=_artifact(args.model_selection_calibration_json),
            blocker="" if calibration_ready else "model_selection_calibration_missing_or_blocked",
            next_action="Calibrate B-factor/pLDDT-style confidence against no-leak historical residue accuracy and keep ECE low.",
        ),
    ]

    pass_count = sum(1 for row in rows if row["threshold_status"] == "pass")
    partial_count = sum(1 for row in rows if row["threshold_status"] == "partial")
    gap_rows = [row for row in rows if row["threshold_status"] != "pass"]
    blocked_rows = [row for row in rows if row["threshold_status"] not in {"pass", "partial"}]
    first_blocked = gap_rows[0] if gap_rows else {}
    summary = {
        "packet_type": "casp17_win_tier_threshold_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "threshold_schema_version": "casp17_internal_win_thresholds_v1",
        "threshold_packet_status": "pass" if not gap_rows else "blocked_input",
        "current_proven_level": (
            "win_tier"
            if win.get("win_tier_level_status") == "pass"
            else "competitive_floor"
            if win.get("competitive_floor_status") == "pass"
            else "review_quality"
            if win.get("review_quality_status") == "pass"
            else "submission_floor"
            if win.get("submission_level_status") == "pass"
            else "none"
        ),
        "target_count": target_count,
        "threshold_count": len(rows),
        "pass_count": pass_count,
        "partial_count": partial_count,
        "blocked_count": len(blocked_rows),
        "first_blocked_dimension": str(first_blocked.get("dimension", "")),
        "first_blocked_metric": str(first_blocked.get("metric", "")),
        "first_blocked_blocker": str(first_blocked.get("blocker", "")),
        "submission_floor_status": win.get("submission_level_status", "missing"),
        "review_quality_status": win.get("review_quality_status", "missing"),
        "competitive_floor_status": win.get("competitive_floor_status", "missing"),
        "win_tier_level_status": win.get("win_tier_level_status", "missing"),
        "official_sources": OFFICIAL_SOURCES,
        "thresholds": THRESHOLDS,
        "standard_levels": STANDARD_LEVELS,
        "claim_boundary": (
            "Operational internal threshold packet only. It defines submission, competitive, and win-tier target bands "
            "for local/no-leak evidence; it does not prove current-target native accuracy, fetch native structures, use external predictors, or submit to CASP."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Tier Threshold Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- threshold_packet_status: `{summary['threshold_packet_status']}`",
        f"- current_proven_level: `{summary['current_proven_level']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- pass/partial/blocked: `{summary['pass_count']}/{summary['partial_count']}/{summary['blocked_count']}`",
        f"- first_blocked: `{summary['first_blocked_dimension'] or '-'}` / `{summary['first_blocked_metric'] or '-'}`",
        f"- first_blocker: `{summary['first_blocked_blocker'] or '-'}`",
        "",
        "## Interpretation",
        "",
        "- `submission_floor` and `review_quality` are current-target internal gates.",
        "- `competitive_floor` still needs no-leak sidechain/native evidence before all-atom quality can be considered competitive.",
        "- `win_tier` requires no-leak historical native benchmarks, refinement ablation, and model-selection calibration.",
        "",
        "## Target Levels",
        "",
        "| level | meaning | must hold | not enough for |",
        "| --- | --- | --- | --- |",
    ]
    for level in STANDARD_LEVELS:
        lines.append(
            f"| `{level['level']}` | {level['meaning']} | {level['must_hold']} | {level['not_enough_for']} |"
        )
    lines.extend(
        [
            "",
        "## Threshold Rows",
        "",
        "| priority | level | dimension | metric | status | current | competitive | win | evidence | blocker |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['level']}` | `{row['dimension']}` | `{row['metric']}` | "
            f"`{row['threshold_status']}` | {row['current_value']} | {row['competitive_floor_threshold']} | "
            f"{row['win_tier_threshold']} | `{row['evidence_kind']}` | `{row['blocker'] or '-'}` |"
        )
    lines.extend(
        [
            "",
            "## Official Sources",
            "",
        ]
    )
    for source in OFFICIAL_SOURCES:
        lines.append(f"- {source['name']}: {source['url']} ({source['use']})")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build operational CASP17 submission/competitive/win-tier threshold packet.")
    parser.add_argument("--win-rubric-json", default=DEFAULT_WIN_RUBRIC_JSON)
    parser.add_argument("--competitive-readiness-json", default=DEFAULT_COMPETITIVE_READINESS_JSON)
    parser.add_argument("--molecular-viewer-json", default=DEFAULT_MOLECULAR_VIEWER_JSON)
    parser.add_argument("--molecular-viewer-smoke-json", default=DEFAULT_MOLECULAR_VIEWER_SMOKE_JSON)
    parser.add_argument("--structure-image-quality-json", default=DEFAULT_STRUCTURE_IMAGE_QUALITY_JSON)
    parser.add_argument("--publication-figure-json", default=DEFAULT_PUBLICATION_FIGURE_JSON)
    parser.add_argument("--all-atom-quality-json", default=DEFAULT_ALL_ATOM_QUALITY_JSON)
    parser.add_argument("--sidechain-quality-json", default=DEFAULT_SIDECHAIN_QUALITY_JSON)
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--refinement-ablation-json", default=DEFAULT_REFINEMENT_ABLATION_JSON)
    parser.add_argument("--model-selection-calibration-json", default=DEFAULT_MODEL_SELECTION_CALIBRATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
