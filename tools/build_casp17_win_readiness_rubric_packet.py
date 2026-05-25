#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMPETITIVE_READINESS_JSON = "runs/casp17_competitive_readiness_packet_current.json"
DEFAULT_STRUCTURE_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_STRUCTURE_IMAGE_QUALITY_JSON = "runs/casp17_structure_image_quality_packet_current.json"
DEFAULT_ALL_ATOM_QUALITY_JSON = "runs/casp17_all_atom_quality_packet_current.json"
DEFAULT_SIDECHAIN_QUALITY_JSON = "runs/casp17_sidechain_quality_packet_current.json"
DEFAULT_ROTAMER_MINIMIZATION_JSON = "runs/casp17_rotamer_minimization_packet_current.json"
DEFAULT_POLAR_REFINEMENT_JSON = "runs/casp17_polar_refinement_packet_current.json"
DEFAULT_FORCEFIELD_MINIMIZATION_JSON = "runs/casp17_forcefield_minimization_packet_current.json"
DEFAULT_STATISTICAL_ROTAMER_JSON = "runs/casp17_statistical_rotamer_packet_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_REFINEMENT_ABLATION_JSON = "runs/casp17_refinement_ablation_packet_current.json"
DEFAULT_MODEL_SELECTION_CALIBRATION_JSON = "runs/casp17_model_selection_calibration_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_readiness_rubric_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_readiness_rubric_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_readiness_rubric_packet_current.md"

OFFICIAL_SOURCES = [
    {
        "name": "CASP17 rules and format",
        "url": "https://predictioncenter.org/casp17/index.cgi?page=format",
        "use": "TS format, per-target files, up to five ranked models, B-factor confidence, SCORE/QSCORE fields.",
    },
    {
        "name": "CASP17 experiment overview",
        "url": "https://predictioncenter.org/casp17/",
        "use": "Independent assessment, current target process, and submission route.",
    },
    {
        "name": "CASP16 monomer assessment",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12157625/",
        "use": "Recent monomer assessment dimensions: GDT_HA, lDDT, MolProbity, QSE, CAD/GDC sidechain measures.",
    },
    {
        "name": "CASP16 complex assessment",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12750043/",
        "use": "Recent complex assessment dimensions: DockQ, ICS, IPS, QSbest, TM-score, lDDT.",
    },
    {
        "name": "CASP infrastructure score definitions",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12422709/",
        "use": "Interface score definitions including ICS, IPS, QS scores, iLDDT, and DockQ.",
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
        fieldnames = ["level", "dimension", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def _status(value: bool) -> str:
    return "pass" if value else "blocked"


def _dimension_status(rows: dict[str, dict[str, Any]], *names: str) -> str:
    for name in names:
        status = rows.get(name, {}).get("status")
        if status:
            return str(status)
    return ""


def _row(
    *,
    priority: int,
    level: str,
    dimension: str,
    status: str,
    required_level: str,
    current_evidence: str,
    next_action: str,
    evidence_artifacts: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "level": level,
        "dimension": dimension,
        "status": status,
        "required_level": required_level,
        "current_evidence": current_evidence,
        "next_action": next_action,
        "evidence_artifacts": evidence_artifacts,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    competitive_payload = _read_json(args.competitive_readiness_json)
    render_payload = _read_json(args.structure_render_json)
    image_quality_payload = _read_json(args.structure_image_quality_json)
    quality_payload = _read_json(args.all_atom_quality_json)
    sidechain_quality_payload = _read_json(args.sidechain_quality_json)
    rotamer_minimization_payload = _read_json(args.rotamer_minimization_json)
    polar_refinement_payload = _read_json(args.polar_refinement_json)
    forcefield_minimization_payload = _read_json(args.forcefield_minimization_json)
    statistical_rotamer_payload = _read_json(args.statistical_rotamer_json)
    sidechain_native_payload = _read_json(args.sidechain_native_benchmark_json)
    historical_payload = _read_json(args.historical_benchmark_json)
    refinement_ablation_payload = _read_json(args.refinement_ablation_json)
    model_selection_calibration_payload = _read_json(args.model_selection_calibration_json)

    competitive = _summary(competitive_payload)
    render = _summary(render_payload)
    image_quality = _summary(image_quality_payload)
    quality = _summary(quality_payload)
    sidechain_quality = _summary(sidechain_quality_payload)
    rotamer_minimization = _summary(rotamer_minimization_payload)
    polar_refinement = _summary(polar_refinement_payload)
    forcefield_minimization = _summary(forcefield_minimization_payload)
    statistical_rotamer = _summary(statistical_rotamer_payload)
    sidechain_native = _summary(sidechain_native_payload)
    historical = _summary(historical_payload)
    refinement_ablation = _summary(refinement_ablation_payload)
    model_selection_calibration = _summary(model_selection_calibration_payload)
    competitive_rows = _rows_by_dimension(competitive_payload)

    target_count = int(competitive.get("target_count", render.get("target_count", 0)) or 0)
    submission_pass = competitive.get("submission_readiness_status") == "pass" and target_count > 0
    top5_pass = competitive_rows.get("top5_ranked_model_depth", {}).get("status") == "pass"
    score_pass = _dimension_status(competitive_rows, "global_model_score_records", "model_score_records") == "pass"
    qscore_pass = _dimension_status(competitive_rows, "interface_score_records", "interface_qscore_records") == "pass"
    all_atom_partial_or_pass = competitive_rows.get("all_atom_and_sidechain_quality", {}).get("status") in {"partial", "pass"}
    all_atom_win_pass = competitive_rows.get("all_atom_and_sidechain_quality", {}).get("status") == "pass"

    rendered_count = int(render.get("rendered_count", 0) or 0)
    pymol_count = int(render.get("pymol_rendered_count", 0) or 0)
    pymol_qc_count = int(render.get("pymol_qc_rendered_count", 0) or 0)
    pymol_surface_count = int(render.get("pymol_surface_rendered_count", 0) or 0)
    review_panel_count = int(render.get("review_panel_count", 0) or 0)
    molecular_plate_count = int(render.get("molecular_plate_count", 0) or 0)
    image_quality_pass = (
        image_quality.get("image_quality_status") == "pass"
        and int(image_quality.get("target_complete_count", 0) or 0) == target_count
        and target_count > 0
    )
    visual_review_pass = bool(target_count and rendered_count == target_count and pymol_count == target_count)
    visual_review_plus_pass = (
        visual_review_pass
        and pymol_surface_count == target_count
        and pymol_qc_count == target_count
        and review_panel_count == target_count
        and molecular_plate_count == target_count
        and image_quality_pass
    )

    historical_pass = historical.get("historical_benchmark_status") == "pass"
    monomer_pass = historical.get("monomer_win_tier_status") == "pass"
    complex_pass = historical.get("complex_win_tier_status") == "pass"
    refinement_ablation_pass = refinement_ablation.get("refinement_ablation_status") == "pass"
    refinement_ablation_partial = (
        int(refinement_ablation.get("usable_layer_count", 0) or 0) > 0
        or int(refinement_ablation.get("ablation_group_count", 0) or 0) > 0
    )
    confidence_calibrated = model_selection_calibration.get("calibration_status") == "pass"
    win_pass = bool(
        monomer_pass
        and complex_pass
        and refinement_ablation_pass
        and confidence_calibrated
        and all_atom_win_pass
        and top5_pass
    )

    rows = [
        _row(
            priority=1,
            level="submission_floor",
            dimension="official_format_and_gate",
            status=_status(submission_pass),
            required_level="CASP17 TS file per target; mandatory PFRMAT/TARGET/AUTHOR/METHOD/MODEL/END, no target residue repetitions, pLDDT-like B-factor confidence, and local submission gate pass for all current targets.",
            current_evidence=f"submission_readiness_status={competitive.get('submission_readiness_status', 'missing')}; targets={target_count}; competitive_packet={_artifact(args.competitive_readiness_json)}",
            next_action="Keep author code runtime-only and perform portal upload only after explicit R4 confirmation." if submission_pass else "Regenerate raw/TS/import/validation/scorecard/submission gates until all current targets pass.",
            evidence_artifacts=_artifact(args.competitive_readiness_json),
        ),
        _row(
            priority=2,
            level="submission_floor",
            dimension="ranked_model_coverage",
            status=_status(top5_pass),
            required_level="Up to five genuinely ranked TS models per target, with MODEL 1 selected by the internal best-current model selector.",
            current_evidence=competitive_rows.get("top5_ranked_model_depth", {}).get("current_evidence", "missing top-5 evidence"),
            next_action="Keep the ranked top-5 lane current whenever the predictor changes." if top5_pass else "Run ranked top-5 generation and candidate gates for every current target.",
            evidence_artifacts=_artifact(args.competitive_readiness_json),
        ),
        _row(
            priority=3,
            level="submission_floor",
            dimension="visual_structure_review",
            status=_status(visual_review_pass),
            required_level="Every target has nonblank local static structure renders and a PyMOL molecular-view render for manual sanity review.",
            current_evidence=f"renders={rendered_count}/{target_count}; pymol={pymol_count}/{target_count}; surface={pymol_surface_count}/{target_count}; qc={pymol_qc_count}/{target_count}; review_panels={review_panel_count}/{target_count}; molecular_plates={molecular_plate_count}/{target_count}; image_quality={image_quality.get('image_quality_status', 'missing')}:{image_quality.get('target_complete_count', 0)}/{target_count}",
            next_action="Add or refresh QC/review-panel renders after each coordinate update." if visual_review_pass else "Regenerate structure render packet with PyMOL enabled and inspect pixel smoke.",
            evidence_artifacts=f"{_artifact(args.structure_render_json)};{_artifact(args.structure_image_quality_json)}",
        ),
        _row(
            priority=4,
            level="competitive_floor",
            dimension="all_atom_steric_quality",
            status="partial" if all_atom_partial_or_pass and not all_atom_win_pass else _status(all_atom_win_pass),
            required_level="Heavy-atom completion, zero severe clashes, low soft-clash burden, rotamer/sidechain plausibility, and local minimization evidence across all targets.",
            current_evidence=(
                f"all_atom_status={quality.get('all_atom_quality_status', 'missing')}; "
                f"severe={quality.get('total_severe_clash_count', 'missing')}; "
                f"soft={quality.get('total_soft_clash_count', 'missing')}; "
                f"mean_soft_clashscore={quality.get('mean_soft_clashscore_per_1000_atoms', 'missing')}; "
                f"min_completion={quality.get('min_heavy_atom_completion_fraction', 'missing')}; "
                f"sidechain_status={sidechain_quality.get('sidechain_quality_status', 'missing')}; "
                f"min_sidechain_completion={sidechain_quality.get('min_complete_sidechain_residue_fraction', 'missing')}; "
                f"min_rotamer_proxy={sidechain_quality.get('min_rotamer_proxy_pass_fraction', 'missing')}; "
                f"max_cb_outlier={sidechain_quality.get('max_cb_radial_outlier_fraction', 'missing')}; "
                f"rotamer_minimization={rotamer_minimization.get('rotamer_minimization_status', 'missing')}; "
                f"prior_dev={rotamer_minimization.get('mean_rotamer_prior_deviation_before_deg', 'missing')}->"
                f"{rotamer_minimization.get('mean_rotamer_prior_deviation_after_deg', 'missing')}; "
                f"hbond_like={rotamer_minimization.get('total_hbond_like_contact_count_before', 'missing')}->"
                f"{rotamer_minimization.get('total_hbond_like_contact_count_after', 'missing')}; "
                f"salt_like={rotamer_minimization.get('total_salt_bridge_like_contact_count_before', 'missing')}->"
                f"{rotamer_minimization.get('total_salt_bridge_like_contact_count_after', 'missing')}; "
                f"polar_refinement={polar_refinement.get('polar_refinement_status', 'missing')}; "
                f"polar_soft_delta={polar_refinement.get('total_soft_clash_delta', 'missing')}; "
                f"polar_hbond_like={polar_refinement.get('total_hbond_like_contact_count_before', 'missing')}->"
                f"{polar_refinement.get('total_hbond_like_contact_count_after', 'missing')}; "
                f"polar_salt_like={polar_refinement.get('total_salt_bridge_like_contact_count_before', 'missing')}->"
                f"{polar_refinement.get('total_salt_bridge_like_contact_count_after', 'missing')}; "
                f"forcefield_minimization={forcefield_minimization.get('forcefield_minimization_status', 'missing')}; "
                f"forcefield_energy_delta={forcefield_minimization.get('total_forcefield_energy_delta', 'missing')}; "
                f"forcefield_soft_delta={forcefield_minimization.get('total_soft_clash_delta', 'missing')}; "
                f"forcefield_hbond_like={forcefield_minimization.get('total_hbond_like_contact_count_before', 'missing')}->"
                f"{forcefield_minimization.get('total_hbond_like_contact_count_after', 'missing')}; "
                f"forcefield_salt_like={forcefield_minimization.get('total_salt_bridge_like_contact_count_before', 'missing')}->"
                f"{forcefield_minimization.get('total_salt_bridge_like_contact_count_after', 'missing')}; "
                f"forcefield_hydrophobic={forcefield_minimization.get('total_hydrophobic_contact_count_before', 'missing')}->"
                f"{forcefield_minimization.get('total_hydrophobic_contact_count_after', 'missing')}; "
                f"statistical_rotamer={statistical_rotamer.get('statistical_rotamer_status', 'missing')}; "
                f"statistical_candidates={statistical_rotamer.get('total_statistical_rotamer_candidate_count', 'missing')}; "
                f"statistical_packed={statistical_rotamer.get('total_packed_residue_count', 'missing')}; "
                f"frequency_prior={statistical_rotamer.get('mean_frequency_prior_penalty_before', 'missing')}->"
                f"{statistical_rotamer.get('mean_frequency_prior_penalty_after', 'missing')}; "
                f"statistical_energy_delta={statistical_rotamer.get('total_forcefield_energy_delta', 'missing')}; "
                f"statistical_guard={statistical_rotamer.get('revert_guard_count', 'missing')}; "
                f"sidechain_native_benchmark={sidechain_native.get('sidechain_native_benchmark_status', 'missing')}; "
                f"sidechain_native_rows={sidechain_native.get('pass_count', 0)}/"
                f"{sidechain_native.get('benchmark_count', 0)}; "
                f"mean_sidechain_RMSD={sidechain_native.get('mean_sidechain_rmsd_A', 'missing')}; "
                f"mean_sidechain_lDDT={sidechain_native.get('mean_sidechain_lddt_proxy', 'missing')}; "
                f"mean_native_sidechain_coverage={sidechain_native.get('mean_native_sidechain_atom_coverage', 'missing')}"
            ),
            next_action="Populate no-leak sidechain-native benchmark rows with chain/residue/atom exactness and pass RMSD/lDDT/coverage thresholds.",
            evidence_artifacts=f"{_artifact(args.all_atom_quality_json)};{_artifact(args.sidechain_quality_json)};{_artifact(args.rotamer_minimization_json)};{_artifact(args.polar_refinement_json)};{_artifact(args.forcefield_minimization_json)};{_artifact(args.statistical_rotamer_json)};{_artifact(args.sidechain_native_benchmark_json)}",
        ),
        _row(
            priority=5,
            level="win_tier",
            dimension="monomer_native_accuracy",
            status=_status(monomer_pass),
            required_level="No-leak historical CASP-like monomer benchmark in the high-accuracy regime: operational target mean TM around 0.90+, GDT_TS/GDT_HA around 0.80-0.85+, high lDDT, low MolProbity, correct-fold rate above 95%.",
            current_evidence=(
                f"monomer_status={historical.get('monomer_win_tier_status', 'missing')}; "
                f"benchmarks={historical.get('monomer_pass_count', 0)}/{historical.get('monomer_benchmark_count', 0)}; "
                f"sequence_exact={historical.get('sequence_exact_match_count', 0)}/"
                f"{historical.get('benchmark_count', 0)}; "
                f"chain_exact={historical.get('chain_exact_match_count', 0)}/"
                f"{historical.get('benchmark_count', 0)}; "
                f"mean_TM={historical.get('mean_tm_score_proxy', 0.0)}; "
                f"mean_GDT_TS={historical.get('mean_gdt_ts_proxy', 0.0)}; "
                f"mean_CA_lDDT={historical.get('mean_ca_lddt_proxy', 0.0)}"
            ),
            next_action="Populate the no-leak historical monomer manifest, run native-scored benchmark, then tune model generation/ranking against those metrics.",
            evidence_artifacts=_artifact(args.historical_benchmark_json),
        ),
        _row(
            priority=6,
            level="win_tier",
            dimension="complex_interface_accuracy",
            status=_status(complex_pass),
            required_level="No-leak historical complex benchmark with correct stoichiometry, strong interface contacts, DockQ/QS/ICS/IPS-quality evidence, and operational average TM around 0.75-0.80 plus DockQ/interface F1 around 0.55-0.60+.",
            current_evidence=(
                f"complex_status={historical.get('complex_win_tier_status', 'missing')}; "
                f"benchmarks={historical.get('complex_pass_count', 0)}/{historical.get('complex_benchmark_count', 0)}; "
                f"sequence_exact={historical.get('sequence_exact_match_count', 0)}/"
                f"{historical.get('benchmark_count', 0)}; "
                f"chain_exact={historical.get('chain_exact_match_count', 0)}/"
                f"{historical.get('benchmark_count', 0)}; "
                f"mean_TM={historical.get('mean_tm_score_proxy', 0.0)}; "
                f"mean_interface_F1={historical.get('mean_complex_interface_f1_proxy', 0.0)}; "
                f"mean_DockQ_proxy={historical.get('mean_complex_dockq_proxy', 0.0)}; "
                f"mean_QSbest_proxy={historical.get('mean_complex_qsbest_proxy', 0.0)}; "
                f"mean_IPS_proxy={historical.get('mean_complex_interface_patch_jaccard_proxy', 0.0)}"
            ),
            next_action="Populate the no-leak historical complex manifest, add interface-aware sampling/docking, and calibrate QSCORE against native interfaces.",
            evidence_artifacts=_artifact(args.historical_benchmark_json),
        ),
        _row(
            priority=7,
            level="win_tier",
            dimension="refinement_ablation_native_evidence",
            status="pass" if refinement_ablation_pass else ("partial" if refinement_ablation_partial else "blocked"),
            required_level="The final selected internal refinement layer must be no-worse than the recursive internal baseline on no-leak historical native proxy metrics, with configured improvement evidence before claiming the refinement stack helps accuracy.",
            current_evidence=(
                f"ablation={refinement_ablation.get('refinement_ablation_status', 'missing')}; "
                f"benchmarks={refinement_ablation.get('benchmark_count', 0)}; "
                f"layers={refinement_ablation.get('layer_count', 0)}; "
                f"usable_layers={refinement_ablation.get('usable_layer_count', 0)}; "
                f"groups={refinement_ablation.get('ablation_group_pass_count', 0)}/"
                f"{refinement_ablation.get('ablation_group_count', 0)}; "
                f"final_not_worse={refinement_ablation.get('final_not_worse_count', 0)}; "
                f"final_improved={refinement_ablation.get('final_improved_count', 0)}; "
                f"required_improved={refinement_ablation.get('required_improved_count', 0)}; "
                f"mean_delta_TM={refinement_ablation.get('mean_delta_tm_score_proxy', 0.0)}; "
                f"mean_delta_GDT_TS={refinement_ablation.get('mean_delta_gdt_ts_proxy', 0.0)}; "
                f"mean_delta_CA_lDDT={refinement_ablation.get('mean_delta_ca_lddt_proxy', 0.0)}; "
                f"manifest_blockers={refinement_ablation.get('manifest_blockers', '') or '-'}"
            ),
            next_action="Populate historical ablation layer directories or layer-specific manifest prediction columns, then run build_casp17_refinement_ablation_packet.py.",
            evidence_artifacts=_artifact(args.refinement_ablation_json),
        ),
        _row(
            priority=8,
            level="win_tier",
            dimension="confidence_and_model_selection_calibration",
            status=_status(confidence_calibrated),
            required_level="SCORE/QSCORE and per-atom confidence must be native-calibrated enough to select MODEL 1 reliably from top-5 candidates and to reflect lDDT/interface quality.",
            current_evidence=(
                f"calibration={model_selection_calibration.get('calibration_status', 'missing')}; "
                f"SCORE={model_selection_calibration.get('score_record_coverage_status', score_pass)}; "
                f"QSCORE={model_selection_calibration.get('qscore_record_coverage_status', qscore_pass)}; "
                f"ranked_depth={model_selection_calibration.get('ranked_candidate_depth_status', 'missing')}; "
                f"historical_exactness={model_selection_calibration.get('historical_exactness_status', historical.get('historical_benchmark_status', 'missing'))}; "
                f"calibration_rows={model_selection_calibration.get('calibration_pass_count', 0)}/"
                f"{model_selection_calibration.get('calibration_row_count', 0)}; "
                f"mean_selection_loss={model_selection_calibration.get('mean_selection_loss', 0.0)}; "
                f"competitive_gap_count={competitive.get('competitive_gap_count', 'missing')}"
            ),
            next_action="Train/calibrate the internal ranker on no-leak historical rows and record top-1 vs best-of-5 selection loss.",
            evidence_artifacts=f"{_artifact(args.competitive_readiness_json)};{_artifact(args.historical_benchmark_json)};{_artifact(args.model_selection_calibration_json)}",
        ),
        _row(
            priority=9,
            level="review_quality",
            dimension="publication_and_qc_visuals",
            status=_status(visual_review_plus_pass),
            required_level="Every current target has base PyMOL, transparent molecular-surface inspection, QC overlay, high-resolution molecular inspection plate, review-panel images, and nonblank/colorful image-quality smoke suitable for manual model triage and communication.",
            current_evidence=(
                f"pymol={pymol_count}/{target_count}; surface={pymol_surface_count}/{target_count}; qc={pymol_qc_count}/{target_count}; "
                f"review_panels={review_panel_count}/{target_count}; molecular_plates={molecular_plate_count}/{target_count}; "
                f"image_quality={image_quality.get('image_quality_status', 'missing')}; "
                f"image_pass={image_quality.get('pass_count', 0)}/{image_quality.get('image_count', 0)}; "
                f"target_complete={image_quality.get('target_complete_count', 0)}/{target_count}; "
                f"min_colorful={image_quality.get('min_estimated_colorful_pixel_count', 0)}; "
                f"qc_hotspots={render.get('pymol_qc_hotspot_count', 0)}"
            ),
            next_action="Regenerate surface/QC/review-panel images after render tool upgrades or coordinate changes." if visual_review_plus_pass else "Add surface inspection plus side-by-side review-panel renders and rebuild the render packet.",
            evidence_artifacts=f"{_artifact(args.structure_render_json)};{_artifact(args.structure_image_quality_json)}",
        ),
    ]

    pass_count = sum(1 for row in rows if row["status"] == "pass")
    partial_count = sum(1 for row in rows if row["status"] == "partial")
    blocked_count = len(rows) - pass_count - partial_count
    first_gap = next((row for row in rows if row["status"] != "pass"), None)
    summary = {
        "packet_type": "casp17_win_readiness_rubric_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "competitive_readiness_json": _artifact(args.competitive_readiness_json),
        "structure_render_json": _artifact(args.structure_render_json),
        "structure_image_quality_json": _artifact(args.structure_image_quality_json),
        "all_atom_quality_json": _artifact(args.all_atom_quality_json),
        "sidechain_quality_json": _artifact(args.sidechain_quality_json),
        "rotamer_minimization_json": _artifact(args.rotamer_minimization_json),
        "polar_refinement_json": _artifact(args.polar_refinement_json),
        "forcefield_minimization_json": _artifact(args.forcefield_minimization_json),
        "statistical_rotamer_json": _artifact(args.statistical_rotamer_json),
        "sidechain_native_benchmark_json": _artifact(args.sidechain_native_benchmark_json),
        "historical_benchmark_json": _artifact(args.historical_benchmark_json),
        "refinement_ablation_json": _artifact(args.refinement_ablation_json),
        "model_selection_calibration_json": _artifact(args.model_selection_calibration_json),
        "target_count": target_count,
        "submission_level_status": "pass" if submission_pass and top5_pass and visual_review_pass else "blocked",
        "competitive_floor_status": "pass" if all_atom_win_pass and top5_pass else ("partial" if all_atom_partial_or_pass and top5_pass else "blocked"),
        "win_tier_level_status": "pass" if win_pass else "blocked",
        "review_quality_status": "pass" if visual_review_plus_pass else "blocked",
        "requirement_count": len(rows),
        "pass_count": pass_count,
        "partial_count": partial_count,
        "blocked_count": blocked_count,
        "first_gap_dimension": first_gap["dimension"] if first_gap else "",
        "first_gap_next_action": first_gap["next_action"] if first_gap else "",
        "official_sources": OFFICIAL_SOURCES,
        "claim_boundary": "Internal CASP17 readiness rubric only. Threshold bands are operational targets based on recent CASP assessment practice, not official CASP17 results or proof of current-target native accuracy.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Readiness Rubric Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- submission_level_status: `{summary['submission_level_status']}`",
        f"- competitive_floor_status: `{summary['competitive_floor_status']}`",
        f"- win_tier_level_status: `{summary['win_tier_level_status']}`",
        f"- review_quality_status: `{summary['review_quality_status']}`",
        f"- pass/partial/blocked: `{summary['pass_count']}/{summary['partial_count']}/{summary['blocked_count']}`",
        f"- first_gap: `{summary['first_gap_dimension'] or '-'}`",
        "",
        "## Requirements",
        "",
        "| priority | level | dimension | status | required level | current evidence | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['level']}` | `{row['dimension']}` | `{row['status']}` | "
            f"{row['required_level']} | {row['current_evidence']} | {row['next_action']} |"
        )
    lines.extend(["", "## Sources", ""])
    for source in summary["official_sources"]:
        lines.append(f"- {source['name']}: {source['url']} ({source['use']})")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 submission-vs-win-tier readiness rubric packet.")
    parser.add_argument("--competitive-readiness-json", default=DEFAULT_COMPETITIVE_READINESS_JSON)
    parser.add_argument("--structure-render-json", default=DEFAULT_STRUCTURE_RENDER_JSON)
    parser.add_argument("--structure-image-quality-json", default=DEFAULT_STRUCTURE_IMAGE_QUALITY_JSON)
    parser.add_argument("--all-atom-quality-json", default=DEFAULT_ALL_ATOM_QUALITY_JSON)
    parser.add_argument("--sidechain-quality-json", default=DEFAULT_SIDECHAIN_QUALITY_JSON)
    parser.add_argument("--rotamer-minimization-json", default=DEFAULT_ROTAMER_MINIMIZATION_JSON)
    parser.add_argument("--polar-refinement-json", default=DEFAULT_POLAR_REFINEMENT_JSON)
    parser.add_argument("--forcefield-minimization-json", default=DEFAULT_FORCEFIELD_MINIMIZATION_JSON)
    parser.add_argument("--statistical-rotamer-json", default=DEFAULT_STATISTICAL_ROTAMER_JSON)
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
