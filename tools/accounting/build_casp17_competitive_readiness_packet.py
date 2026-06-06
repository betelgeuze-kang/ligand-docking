#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_RAW_GATE_JSON = "runs/casp17_internal_physics_raw_gate_packet_recursive_current.json"
DEFAULT_TS_GATE_JSON = "runs/casp17_internal_physics_ts_gate_batch_recursive_current.json"
DEFAULT_SUBMISSION_GATE_JSON = "runs/casp17_submission_gate_packet_current.json"
DEFAULT_ACCURACY_READINESS_JSON = "runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.json"
DEFAULT_VIEWER_JSON = "runs/casp17_molecular_viewer_packet_current.json"
DEFAULT_RANKED_DEPTH_JSON = "runs/casp17_ranked_model_depth_packet_current.json"
DEFAULT_SIDECHAIN_SCAFFOLD_JSON = "runs/casp17_sidechain_scaffold_packet_current.json"
DEFAULT_SIDECHAIN_REPACK_JSON = "runs/casp17_sidechain_repack_packet_current.json"
DEFAULT_STERIC_RELAX_JSON = "runs/casp17_steric_relax_packet_current.json"
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
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_statistical_rotamer_current"
DEFAULT_OUT_JSON = "runs/casp17_competitive_readiness_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_competitive_readiness_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_competitive_readiness_packet_current.md"

CASP17_SOURCES = [
    {
        "name": "CASP17 format and submission rules",
        "url": "https://predictioncenter.org/casp17/index.cgi?page=format",
        "use": "TS records, SCORE/QSCORE semantics, PARENT/TER requirements, model index limits.",
    },
    {
        "name": "CASP17 main experiment page",
        "url": "https://predictioncenter.org/casp17/",
        "use": "Submission path, modeling season, independent assessment boundary.",
    },
    {
        "name": "CASP15 tertiary assessment / MULTICOM analysis",
        "url": "https://www.nature.com/articles/s42004-023-00991-6",
        "use": "Recent top-tier monomer ranking metrics and representative GDT-TS/TM-score bands.",
    },
    {
        "name": "CASP16 MULTICOM4 complex analysis",
        "url": "https://sciety.org/articles/activity/10.1002/prot.26850",
        "use": "Recent top-tier complex TM-score and DockQ bands.",
    },
    {
        "name": "CASP16 AlphaFold3 assessment summary",
        "url": "https://sciety-labs.elifesciences.org/articles/by?article_doi=10.1101%2F2025.04.10.648174",
        "use": "Current state-of-the-art context: AF3/top predictors, model selection, best-of-five gap.",
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


def _text(value: Any) -> str:
    return str(value or "").strip()


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
        fieldnames = ["dimension"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _current_open_targets(watchlist: dict[str, Any]) -> list[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return []
    targets: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lane = _text(row.get("lane_recommendation"))
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}:
            targets.append(target_id)
    return targets


def _prediction_stats(prediction_dir: str | Path, target_ids: list[str]) -> dict[str, Any]:
    root = _resolve(prediction_dir)
    model_counts: list[int] = []
    score_count = 0
    qscore_count = 0
    assembly_target_count = 0
    ts_count = 0
    for target_id in target_ids:
        path = root / f"{target_id}TS.pdb"
        if not path.exists():
            model_counts.append(0)
            continue
        ts_count += 1
        model_count = 0
        has_score = False
        has_qscore = False
        chain_ids: set[str] = set()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            record = line[:6].strip().upper()
            if record == "MODEL":
                model_count += 1
            elif record == "SCORE":
                has_score = True
            elif record == "QSCORE":
                has_qscore = True
            elif record == "ATOM":
                if len(line) > 21:
                    chain_ids.add(line[21].strip() or "_")
                else:
                    fields = line.split()
                    chain_ids.add(fields[4] if len(fields) > 4 else "_")
        model_counts.append(model_count)
        is_assembly = len(chain_ids) > 1
        assembly_target_count += int(is_assembly)
        score_count += int(has_score)
        qscore_count += int(has_qscore and is_assembly)
    return {
        "ts_file_count": ts_count,
        "model_count_min": min(model_counts) if model_counts else 0,
        "model_count_max": max(model_counts) if model_counts else 0,
        "targets_with_score": score_count,
        "targets_with_qscore": qscore_count,
        "assembly_target_count": assembly_target_count,
    }


def _status(pass_condition: bool, partial_condition: bool = False) -> str:
    if pass_condition:
        return "pass"
    if partial_condition:
        return "partial"
    return "blocked"


def _row(
    dimension: str,
    status: str,
    current_evidence: str,
    target_level: str,
    gap: str,
    next_action: str,
) -> dict[str, str]:
    return {
        "dimension": dimension,
        "status": status,
        "current_evidence": current_evidence,
        "target_level": target_level,
        "gap": gap,
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    watchlist = _read_json(args.target_watchlist_json)
    raw = _summary(_read_json(args.raw_gate_json))
    ts = _summary(_read_json(args.ts_gate_json))
    submission = _summary(_read_json(args.submission_gate_json))
    accuracy = _summary(_read_json(args.accuracy_readiness_json))
    viewer = _summary(_read_json(args.viewer_json))
    ranked_depth = _summary(_read_json(args.ranked_depth_json))
    sidechain_scaffold = _summary(_read_json(args.sidechain_scaffold_json))
    sidechain_repack = _summary(_read_json(args.sidechain_repack_json))
    steric_relax = _summary(_read_json(args.steric_relax_json))
    all_atom_quality = _summary(_read_json(args.all_atom_quality_json))
    sidechain_quality = _summary(_read_json(args.sidechain_quality_json))
    rotamer_minimization = _summary(_read_json(args.rotamer_minimization_json))
    polar_refinement = _summary(_read_json(args.polar_refinement_json))
    forcefield_minimization = _summary(_read_json(args.forcefield_minimization_json))
    statistical_rotamer = _summary(_read_json(args.statistical_rotamer_json))
    sidechain_native_benchmark = _summary(_read_json(args.sidechain_native_benchmark_json))
    historical_benchmark = _summary(_read_json(args.historical_benchmark_json))
    refinement_ablation = _summary(_read_json(args.refinement_ablation_json))
    model_selection_calibration = _summary(_read_json(args.model_selection_calibration_json))
    target_ids = _current_open_targets(watchlist)
    prediction_stats = _prediction_stats(args.prediction_dir, target_ids)

    target_count = len(target_ids)
    raw_pass = raw.get("raw_gate_status") == "pass" and int(raw.get("pass_count", -1)) == target_count
    ts_batch_status = _text(ts.get("batch_status"))
    ts_pass = (
        ts_batch_status in {"completed_to_submission_gate", "completed_to_conversion"}
        and int(ts.get("converted_count", -1)) == target_count
        and int(ts.get("blocked_count", 0) or 0) == 0
        and int(ts.get("failed_count", 0) or 0) == 0
    )
    submission_pass = int(submission.get("submission_go_count", -1)) == target_count and int(submission.get("submission_no_go_count", -1)) == 0
    accuracy_pass = accuracy.get("accuracy_readiness_status") == "pass" and int(accuracy.get("pass_count", -1)) == target_count
    viewer_pass = int(viewer.get("ready_count", -1)) == target_count and int(viewer.get("blocked_count", -1)) == 0
    submission_ready = bool(target_count and raw_pass and ts_pass and submission_pass and accuracy_pass and viewer_pass)

    one_model_only = prediction_stats["model_count_min"] == 1 and prediction_stats["model_count_max"] == 1
    ranked_depth_pass_count = int(ranked_depth.get("pass_count", 0) or 0)
    ranked_depth_candidate_gate_pass_count = int(ranked_depth.get("candidate_gate_pass_count", 0) or 0)
    ranked_depth_candidate_gate_total_count = int(ranked_depth.get("candidate_gate_total_count", 0) or 0)
    ranked_depth_status = _text(ranked_depth.get("ranked_depth_status"))
    ranked_depth_candidate_gates_complete = (
        ranked_depth_candidate_gate_total_count >= target_count * 5
        and ranked_depth_candidate_gate_pass_count >= target_count * 5
    )
    top5_pass = (
        ranked_depth_status == "pass"
        and ranked_depth_pass_count == target_count
        and ranked_depth_candidate_gates_complete
        and target_count > 0
    )
    top5_partial = ranked_depth_pass_count > 0 or ranked_depth_candidate_gate_pass_count > 0 or one_model_only
    score_partial = prediction_stats["targets_with_score"] == target_count and target_count > 0
    assembly_target_count = int(prediction_stats["assembly_target_count"])
    qscore_pass = assembly_target_count == 0 or prediction_stats["targets_with_qscore"] == assembly_target_count
    qscore_partial = prediction_stats["targets_with_qscore"] > 0
    sidechain_scaffold_pass = (
        sidechain_scaffold.get("sidechain_scaffold_status") == "pass"
        and int(sidechain_scaffold.get("pass_count", -1)) == target_count
        and int(sidechain_scaffold.get("validation_pass_count", -1)) == target_count
    )
    sidechain_scaffold_partial = int(sidechain_scaffold.get("pass_count", 0) or 0) > 0
    sidechain_repack_pass = (
        sidechain_repack.get("sidechain_repack_status") == "pass"
        and int(sidechain_repack.get("pass_count", -1)) == target_count
    )
    sidechain_repack_partial = int(sidechain_repack.get("pass_count", 0) or 0) > 0
    steric_relax_pass = (
        steric_relax.get("steric_relax_status") == "pass"
        and int(steric_relax.get("pass_count", -1)) == target_count
    )
    steric_relax_partial = int(steric_relax.get("pass_count", 0) or 0) > 0
    all_atom_quality_pass = (
        all_atom_quality.get("all_atom_quality_status") == "pass"
        and int(all_atom_quality.get("pass_count", -1)) == target_count
    )
    all_atom_quality_partial = int(all_atom_quality.get("pass_count", 0) or 0) > 0
    sidechain_quality_pass = (
        sidechain_quality.get("sidechain_quality_status") == "pass"
        and int(sidechain_quality.get("pass_count", -1)) == target_count
    )
    sidechain_quality_partial = int(sidechain_quality.get("pass_count", 0) or 0) > 0
    rotamer_minimization_pass = (
        rotamer_minimization.get("rotamer_minimization_status") == "pass"
        and int(rotamer_minimization.get("pass_count", -1)) == target_count
    )
    rotamer_minimization_partial = int(rotamer_minimization.get("pass_count", 0) or 0) > 0
    polar_refinement_pass = (
        polar_refinement.get("polar_refinement_status") == "pass"
        and int(polar_refinement.get("pass_count", -1)) == target_count
    )
    polar_refinement_partial = int(polar_refinement.get("pass_count", 0) or 0) > 0
    forcefield_minimization_pass = (
        forcefield_minimization.get("forcefield_minimization_status") == "pass"
        and int(forcefield_minimization.get("pass_count", -1)) == target_count
    )
    forcefield_minimization_partial = int(forcefield_minimization.get("pass_count", 0) or 0) > 0
    statistical_rotamer_pass = (
        statistical_rotamer.get("statistical_rotamer_status") == "pass"
        and int(statistical_rotamer.get("pass_count", -1)) == target_count
    )
    statistical_rotamer_partial = int(statistical_rotamer.get("pass_count", 0) or 0) > 0
    sidechain_native_pass = sidechain_native_benchmark.get("sidechain_native_benchmark_status") == "pass"
    sidechain_native_partial = int(sidechain_native_benchmark.get("pass_count", 0) or 0) > 0
    monomer_benchmark_count = int(historical_benchmark.get("monomer_benchmark_count", 0) or 0)
    monomer_benchmark_pass_count = int(historical_benchmark.get("monomer_pass_count", 0) or 0)
    complex_benchmark_count = int(historical_benchmark.get("complex_benchmark_count", 0) or 0)
    complex_benchmark_pass_count = int(historical_benchmark.get("complex_pass_count", 0) or 0)
    monomer_benchmark_pass = (
        monomer_benchmark_count > 0
        and historical_benchmark.get("monomer_win_tier_status") == "pass"
        and monomer_benchmark_pass_count == monomer_benchmark_count
    )
    complex_benchmark_pass = (
        complex_benchmark_count > 0
        and historical_benchmark.get("complex_win_tier_status") == "pass"
        and complex_benchmark_pass_count == complex_benchmark_count
    )
    refinement_ablation_pass = refinement_ablation.get("refinement_ablation_status") == "pass"
    refinement_ablation_partial = (
        int(refinement_ablation.get("usable_layer_count", 0) or 0) > 0
        or int(refinement_ablation.get("ablation_group_count", 0) or 0) > 0
    )

    rows = [
        _row(
            "submission_floor",
            _status(submission_ready),
            f"raw={raw.get('raw_gate_status', '-')}; ts={ts.get('batch_status', '-')}; submission_go={submission.get('submission_go_count', 0)}/{target_count}; accuracy={accuracy.get('accuracy_readiness_status', '-')}; viewer_ready={viewer.get('ready_count', 0)}/{target_count}",
            "All current targets pass format, sequence/chain coverage, geometry, confidence, scorecard, internal submission gate, and visual sanity checks.",
            "-" if submission_ready else "At least one local CASP gate is not green.",
            "Keep this as the non-negotiable gate before any external CASP upload.",
        ),
        _row(
            "top5_ranked_model_depth",
            _status(top5_pass, partial_condition=top5_partial),
            f"primary TS files={prediction_stats['ts_file_count']}/{target_count}; primary MODEL count range={prediction_stats['model_count_min']}..{prediction_stats['model_count_max']}; ranked-depth pass={ranked_depth_pass_count}/{target_count}; candidate gates={ranked_depth_candidate_gate_pass_count}/{ranked_depth_candidate_gate_total_count}",
            "Generate up to five genuinely diverse ranked models per target, with MODEL 1 selected by a calibrated internal ranker.",
            "-" if top5_pass else "Current primary lane emits one accepted TS model per target; ranked top-5 depth is not yet complete for all current targets.",
            "Add multi-start/top-5 TS export plus model-selection evidence from an offline benchmark.",
        ),
        _row(
            "global_model_score_records",
            _status(score_partial),
            f"SCORE records on {prediction_stats['targets_with_score']}/{target_count} current TS files.",
            "Emit explicit SCORE records in [0,1]; native calibration is tracked by the historical benchmark and model-selection rows.",
            "-" if score_partial else "Explicit global SCORE records are missing from at least one current TS file.",
            "Calibrate ensemble/energy features against historical targets before treating SCORE as native-accuracy evidence.",
        ),
        _row(
            "interface_score_records",
            _status(qscore_pass, partial_condition=qscore_partial),
            f"QSCORE records on {prediction_stats['targets_with_qscore']}/{assembly_target_count} multichain TS files.",
            "For assembly targets, emit explicit per-interface QSCORE records; native calibration is tracked by historical complex benchmarks.",
            "-" if qscore_pass else "At least one multichain TS file lacks an explicit QSCORE record.",
            "Calibrate interface-contact features on historical complex targets before treating QSCORE as DockQ/QS/ICS-quality evidence.",
        ),
        _row(
            "monomer_win_tier_accuracy",
            "pass" if monomer_benchmark_pass else "unproven",
            (
                f"historical monomer benchmarks={monomer_benchmark_pass_count}/{monomer_benchmark_count}; "
                f"sequence_exact={historical_benchmark.get('sequence_exact_match_count', 0)}/"
                f"{historical_benchmark.get('benchmark_count', 0)}; "
                f"chain_exact={historical_benchmark.get('chain_exact_match_count', 0)}/"
                f"{historical_benchmark.get('benchmark_count', 0)}; "
                f"mean TM={historical_benchmark.get('mean_tm_score_proxy', 0.0)}; "
                f"mean GDT_TS={historical_benchmark.get('mean_gdt_ts_proxy', 0.0)}; "
                f"mean CA-lDDT={historical_benchmark.get('mean_ca_lddt_proxy', 0.0)}"
            )
            if monomer_benchmark_count
            else f"No native-scored no-leak historical benchmark rows are available; manifest blockers={historical_benchmark.get('manifest_blockers', 'missing_packet') or '-'}",
            "Recent top monomer systems are in the high-accuracy regime: historical benchmark goal should be mean TM-score about 0.90, GDT_TS/GDT_HA roughly 0.80-0.85+, high lDDT, and correct-fold rate above 95%.",
            "-" if monomer_benchmark_pass else "Local gates prove format/geometry/readiness, not native accuracy or ranking competitiveness.",
            "Populate the no-leak historical benchmark manifest with CASP-like local prediction/native pairs, then optimize against TM/GDT/lDDT/MolProbity/sidechain metrics.",
        ),
        _row(
            "complex_win_tier_accuracy",
            "pass" if complex_benchmark_pass else "unproven",
            (
                f"historical complex benchmarks={complex_benchmark_pass_count}/{complex_benchmark_count}; "
                f"sequence_exact={historical_benchmark.get('sequence_exact_match_count', 0)}/"
                f"{historical_benchmark.get('benchmark_count', 0)}; "
                f"chain_exact={historical_benchmark.get('chain_exact_match_count', 0)}/"
                f"{historical_benchmark.get('benchmark_count', 0)}; "
                f"mean TM={historical_benchmark.get('mean_tm_score_proxy', 0.0)}; "
                f"mean interface F1={historical_benchmark.get('mean_complex_interface_f1_proxy', 0.0)}; "
                f"mean DockQ proxy={historical_benchmark.get('mean_complex_dockq_proxy', 0.0)}; "
                f"mean QSbest proxy={historical_benchmark.get('mean_complex_qsbest_proxy', 0.0)}; "
                f"mean IPS proxy={historical_benchmark.get('mean_complex_interface_patch_jaccard_proxy', 0.0)}"
            )
            if complex_benchmark_count
            else f"No native-scored no-leak historical complex benchmark rows are available; manifest blockers={historical_benchmark.get('manifest_blockers', 'missing_packet') or '-'}",
            "Recent top complex systems average around TM-score 0.75-0.80 and DockQ about 0.55-0.60 on CASP16-style complex sets, with antibody-antigen and difficult interfaces still hard.",
            "-" if complex_benchmark_pass else "Current local gate does not prove interface placement, stoichiometry selection, or DockQ-quality contacts.",
            "Populate the no-leak historical complex benchmark manifest, then add interface-aware sampling, stoichiometry search, and calibrated QSCORE.",
        ),
        _row(
            "all_atom_and_sidechain_quality",
            "pass"
            if (
                all_atom_quality_pass
                and sidechain_quality_pass
                and forcefield_minimization_pass
                and statistical_rotamer_pass
                and sidechain_native_pass
            )
            else "partial"
            if (
                sidechain_scaffold_pass
                or sidechain_repack_pass
                or steric_relax_pass
                or all_atom_quality_pass
                or sidechain_quality_pass
                or rotamer_minimization_pass
                or polar_refinement_pass
                or forcefield_minimization_pass
                or statistical_rotamer_pass
                or sidechain_native_pass
            )
            else "blocked",
            (
                f"sidechain scaffold={sidechain_scaffold.get('pass_count', 0)}/{target_count}; "
                f"validation={sidechain_scaffold.get('validation_pass_count', 0)}/{target_count}; "
                f"min heavy-atom completion={sidechain_scaffold.get('min_heavy_atom_completion_fraction', 0.0)}; "
                f"emitted heavy atoms={sidechain_scaffold.get('total_emitted_heavy_atom_count', 0)}; "
                f"local frame-rotamer selections={sidechain_scaffold.get('total_rotamer_selected_residue_count', 0)}/"
                f"{sidechain_scaffold.get('total_rotamer_candidate_count', 0)}; "
                f"sidechain repack={sidechain_repack.get('pass_count', 0)}/{target_count}; "
                f"repack soft delta={sidechain_repack.get('total_soft_clash_delta', 0)}; "
                f"repack guard={sidechain_repack.get('revert_guard_count', 0)}; "
                f"steric relax={steric_relax.get('pass_count', 0)}/{target_count}; "
                f"relax soft delta={steric_relax.get('total_soft_clash_delta', 0)}; "
                f"relax guard={steric_relax.get('revert_guard_count', 0)}; "
                f"all-atom QC={all_atom_quality.get('pass_count', 0)}/{target_count}; "
                f"max soft clashscore={all_atom_quality.get('max_soft_clashscore_per_1000_atoms', 0.0)}; "
                f"severe clashes={all_atom_quality.get('total_severe_clash_count', 0)}; "
                f"sidechain quality={sidechain_quality.get('pass_count', 0)}/{target_count}; "
                f"min complete sidechain={sidechain_quality.get('min_complete_sidechain_residue_fraction', 0.0)}; "
                f"min rotamer proxy={sidechain_quality.get('min_rotamer_proxy_pass_fraction', 0.0)}; "
                f"max CB radial outlier={sidechain_quality.get('max_cb_radial_outlier_fraction', 0.0)}; "
                f"rotamer minimization={rotamer_minimization.get('pass_count', 0)}/{target_count}; "
                f"rotamer prior deviation={rotamer_minimization.get('mean_rotamer_prior_deviation_before_deg', 0.0)}->"
                f"{rotamer_minimization.get('mean_rotamer_prior_deviation_after_deg', 0.0)}; "
                f"hbond-like contacts={rotamer_minimization.get('total_hbond_like_contact_count_before', 0)}->"
                f"{rotamer_minimization.get('total_hbond_like_contact_count_after', 0)}; "
                f"salt-like contacts={rotamer_minimization.get('total_salt_bridge_like_contact_count_before', 0)}->"
                f"{rotamer_minimization.get('total_salt_bridge_like_contact_count_after', 0)}; "
                f"rotamer guard={rotamer_minimization.get('revert_guard_count', 0)}; "
                f"polar refinement={polar_refinement.get('pass_count', 0)}/{target_count}; "
                f"polar soft delta={polar_refinement.get('total_soft_clash_delta', 0)}; "
                f"polar hbond-like={polar_refinement.get('total_hbond_like_contact_count_before', 0)}->"
                f"{polar_refinement.get('total_hbond_like_contact_count_after', 0)}; "
                f"polar salt-like={polar_refinement.get('total_salt_bridge_like_contact_count_before', 0)}->"
                f"{polar_refinement.get('total_salt_bridge_like_contact_count_after', 0)}; "
                f"polar guard={polar_refinement.get('revert_guard_count', 0)}; "
                f"forcefield minimization={forcefield_minimization.get('pass_count', 0)}/{target_count}; "
                f"forcefield energy delta={forcefield_minimization.get('total_forcefield_energy_delta', 0.0)}; "
                f"forcefield soft delta={forcefield_minimization.get('total_soft_clash_delta', 0)}; "
                f"forcefield hbond-like={forcefield_minimization.get('total_hbond_like_contact_count_before', 0)}->"
                f"{forcefield_minimization.get('total_hbond_like_contact_count_after', 0)}; "
                f"forcefield salt-like={forcefield_minimization.get('total_salt_bridge_like_contact_count_before', 0)}->"
                f"{forcefield_minimization.get('total_salt_bridge_like_contact_count_after', 0)}; "
                f"forcefield hydrophobic={forcefield_minimization.get('total_hydrophobic_contact_count_before', 0)}->"
                f"{forcefield_minimization.get('total_hydrophobic_contact_count_after', 0)}; "
                f"forcefield guard={forcefield_minimization.get('revert_guard_count', 0)}; "
                f"statistical rotamer={statistical_rotamer.get('pass_count', 0)}/{target_count}; "
                f"statistical candidates={statistical_rotamer.get('total_statistical_rotamer_candidate_count', 0)}; "
                f"statistical packed residues={statistical_rotamer.get('total_packed_residue_count', 0)}; "
                f"frequency prior penalty={statistical_rotamer.get('mean_frequency_prior_penalty_before', 0.0)}->"
                f"{statistical_rotamer.get('mean_frequency_prior_penalty_after', 0.0)}; "
                f"statistical energy delta={statistical_rotamer.get('total_forcefield_energy_delta', 0.0)}; "
                f"statistical soft delta={statistical_rotamer.get('total_soft_clash_delta', 0)}; "
                f"statistical guard={statistical_rotamer.get('revert_guard_count', 0)}; "
                f"sidechain native benchmark={sidechain_native_benchmark.get('sidechain_native_benchmark_status', 'missing')}; "
                f"sidechain native rows={sidechain_native_benchmark.get('pass_count', 0)}/"
                f"{sidechain_native_benchmark.get('benchmark_count', 0)}; "
                f"mean sidechain RMSD={sidechain_native_benchmark.get('mean_sidechain_rmsd_A', 0.0)}; "
                f"mean sidechain lDDT={sidechain_native_benchmark.get('mean_sidechain_lddt_proxy', 0.0)}; "
                f"mean native sidechain coverage={sidechain_native_benchmark.get('mean_native_sidechain_atom_coverage', 0.0)}"
            )
            if (
                sidechain_scaffold_pass
                or sidechain_scaffold_partial
                or sidechain_repack_pass
                or sidechain_repack_partial
                or steric_relax_pass
                or steric_relax_partial
                or all_atom_quality_pass
                or all_atom_quality_partial
                or sidechain_quality_pass
                or sidechain_quality_partial
                or rotamer_minimization_pass
                or rotamer_minimization_partial
                or polar_refinement_pass
                or polar_refinement_partial
                or forcefield_minimization_pass
                or forcefield_minimization_partial
                or statistical_rotamer_pass
                or statistical_rotamer_partial
                or sidechain_native_pass
                or sidechain_native_partial
            )
            else "Current emitted atoms are a CA-anchored compact pseudo-backbone with placeholder sidechain atoms sufficient for local gates.",
            "Competitive TS models need realistic all-atom geometry, sidechain packing, low clashscore, good MolProbity, and contact-area agreement.",
            "Residue-specific heavy-atom scaffold has local frame-rotamer candidate selection, not-worse sidechain repack/polish, sidechain-only steric relaxation, residue-class rotamer-prior steric/polar minimization, sidechain-only hydrogen-bond/salt/steric fine tuning, short sidechain-only forcefield-style minimization, internal residue-frequency statistical rotamer packing proxy, sidechain completeness/rotamer-frame proxy QC, and internal steric/completion QC, but it is not an external Dunbrack/Richardson validation, official MolProbity-calibrated all-atom refinement, or native-scored accuracy evidence.",
            "-"
            if sidechain_native_pass
            else "Populate no-leak historical prediction/native PDB pairs with sidechain atoms, then run sidechain-native benchmark metrics before treating this as win-tier all-atom evidence.",
        ),
        _row(
            "refinement_ablation_native_evidence",
            _status(refinement_ablation_pass, partial_condition=refinement_ablation_partial),
            (
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
            "Final selected internal refinement layer must be no-worse than the recursive baseline on no-leak historical native proxy metrics, with configured improvement evidence.",
            "-"
            if refinement_ablation_pass
            else "Layered internal refinement is not yet native-ablation-proven on no-leak historical prediction/native pairs.",
            "Populate historical ablation layer directories or layer-specific manifest prediction columns, then run casp17/build_casp17_refinement_ablation_packet.py.",
        ),
        _row(
            "confidence_and_model_selection",
            "pass" if model_selection_calibration.get("calibration_status") == "pass" else "blocked",
            (
                f"calibration={model_selection_calibration.get('calibration_status', 'missing')}; "
                f"SCORE={model_selection_calibration.get('score_record_coverage_status', 'missing')}; "
                f"QSCORE={model_selection_calibration.get('qscore_record_coverage_status', 'missing')}; "
                f"ranked_depth={model_selection_calibration.get('ranked_candidate_depth_status', 'missing')}; "
                f"historical_exactness={model_selection_calibration.get('historical_exactness_status', 'missing')}; "
                f"calibration_rows={model_selection_calibration.get('calibration_pass_count', 0)}/"
                f"{model_selection_calibration.get('calibration_row_count', 0)}; "
                f"mean_selection_loss={model_selection_calibration.get('mean_selection_loss', 0.0)}"
            ),
            "Winning-level methods need accurate per-residue/per-atom confidence, global ranking, interface confidence, and failure detection.",
            "-"
            if model_selection_calibration.get("calibration_status") == "pass"
            else "Current SCORE/QSCORE records exist, but selected-vs-oracle model ranking is not native-calibrated on no-leak historical rows.",
            "Populate the no-leak calibration CSV from historical top-5 predictions and keep selection loss under the configured threshold.",
        ),
    ]

    competitive_gap_count = sum(1 for row in rows if row["status"] != "pass")
    summary = {
        "packet_type": "casp17_competitive_readiness_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "prediction_dir": _artifact(args.prediction_dir),
        "ranked_depth_json": _artifact(args.ranked_depth_json),
        "sidechain_scaffold_json": _artifact(args.sidechain_scaffold_json),
        "sidechain_repack_json": _artifact(args.sidechain_repack_json),
        "steric_relax_json": _artifact(args.steric_relax_json),
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
        "submission_readiness_status": "pass" if submission_ready else "blocked",
        "competitive_readiness_status": "blocked" if competitive_gap_count else "pass",
        "win_tier_readiness_status": "blocked",
        "competitive_gap_count": competitive_gap_count,
        "claim_boundary": "This packet compares local internal readiness to recent CASP competitiveness targets. It is not official CASP scoring and cannot prove current-target native accuracy before assessment.",
    }
    return {
        "summary": summary,
        "sources": CASP17_SOURCES,
        "benchmarks": {
            "submission_floor": "CASP17 TS format, current-target coverage, internal gates, and explicit external-submission confirmation.",
            "monomer_win_tier_target": "Historical no-leak benchmark mean TM-score about 0.90, GDT_TS/GDT_HA roughly 0.80-0.85+, high lDDT, low MolProbity, correct-fold rate above 95%.",
            "complex_win_tier_target": "Historical no-leak benchmark average TM-score about 0.75-0.80 and DockQ about 0.55-0.60, plus strong interface contact and stoichiometry metrics.",
        },
        "rows": rows,
    }


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Readiness Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- submission_readiness_status: `{summary['submission_readiness_status']}`",
        f"- competitive_readiness_status: `{summary['competitive_readiness_status']}`",
        f"- win_tier_readiness_status: `{summary['win_tier_readiness_status']}`",
        f"- competitive_gap_count: `{summary['competitive_gap_count']}`",
        "",
        "## Benchmarks",
        "",
    ]
    for key, value in payload["benchmarks"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Gap Table",
            "",
            "| dimension | status | current evidence | target level | gap | next action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['dimension']}` | `{row['status']}` | {row['current_evidence']} | {row['target_level']} | {row['gap']} | {row['next_action']} |"
        )
    lines.extend(["", "## Sources", ""])
    for source in payload["sources"]:
        lines.append(f"- [{source['name']}]({source['url']}): {source['use']}")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 submission-vs-winning-level competitive readiness packet.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--raw-gate-json", default=DEFAULT_RAW_GATE_JSON)
    parser.add_argument("--ts-gate-json", default=DEFAULT_TS_GATE_JSON)
    parser.add_argument("--submission-gate-json", default=DEFAULT_SUBMISSION_GATE_JSON)
    parser.add_argument("--accuracy-readiness-json", default=DEFAULT_ACCURACY_READINESS_JSON)
    parser.add_argument("--viewer-json", default=DEFAULT_VIEWER_JSON)
    parser.add_argument("--ranked-depth-json", default=DEFAULT_RANKED_DEPTH_JSON)
    parser.add_argument("--sidechain-scaffold-json", default=DEFAULT_SIDECHAIN_SCAFFOLD_JSON)
    parser.add_argument("--sidechain-repack-json", default=DEFAULT_SIDECHAIN_REPACK_JSON)
    parser.add_argument("--steric-relax-json", default=DEFAULT_STERIC_RELAX_JSON)
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
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
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
