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
DEFAULT_HISTORICAL_SCAFFOLD_JSON = "runs/casp17_historical_benchmark_manifest_scaffold_current.json"
DEFAULT_HISTORICAL_PROMOTION_JSON = "runs/casp17_historical_benchmark_manifest_promotion_current.json"
DEFAULT_HISTORICAL_INPUT_PREFLIGHT_JSON = "runs/casp17_historical_input_preflight_packet_current.json"
DEFAULT_HISTORICAL_INPUT_WORKORDER_JSON = "runs/casp17_historical_input_workorder_packet_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_CALIBRATION_SCAFFOLD_JSON = "runs/casp17_model_selection_calibration_scaffold_current.json"
DEFAULT_CALIBRATION_JSON = "runs/casp17_model_selection_calibration_packet_current.json"
DEFAULT_RENDER_JSON = "runs/casp17_structure_render_packet_current.json"
DEFAULT_POLAR_REFINEMENT_JSON = "runs/casp17_polar_refinement_packet_current.json"
DEFAULT_FORCEFIELD_MINIMIZATION_JSON = "runs/casp17_forcefield_minimization_packet_current.json"
DEFAULT_STATISTICAL_ROTAMER_JSON = "runs/casp17_statistical_rotamer_packet_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_REFINEMENT_ABLATION_JSON = "runs/casp17_refinement_ablation_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_action_queue_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_action_queue_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_action_queue_packet_current.md"


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
        fieldnames = ["priority", "action_id", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _row(
    *,
    priority: int,
    action_id: str,
    lane: str,
    status: str,
    related_dimension: str,
    required_level: str,
    current_evidence: str,
    inputs_needed: str,
    command: str,
    done_when: str,
    blockers: str,
    evidence_artifacts: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "action_id": action_id,
        "lane": lane,
        "status": status,
        "related_dimension": related_dimension,
        "required_level": required_level,
        "current_evidence": current_evidence,
        "inputs_needed": inputs_needed,
        "command": command,
        "done_when": done_when,
        "blockers": blockers,
        "evidence_artifacts": evidence_artifacts,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    win_payload = _read_json(args.win_rubric_json)
    competitive = _summary(_read_json(args.competitive_readiness_json))
    historical_scaffold = _summary(_read_json(args.historical_scaffold_json))
    historical_promotion = _summary(_read_json(args.historical_promotion_json))
    historical_input_preflight = _summary(_read_json(args.historical_input_preflight_json))
    historical_input_workorder = _summary(_read_json(args.historical_input_workorder_json))
    historical_benchmark = _summary(_read_json(args.historical_benchmark_json))
    calibration_scaffold = _summary(_read_json(args.calibration_scaffold_json))
    calibration = _summary(_read_json(args.calibration_json))
    render = _summary(_read_json(args.render_json))
    polar_refinement = _summary(_read_json(args.polar_refinement_json))
    forcefield_minimization = _summary(_read_json(args.forcefield_minimization_json))
    statistical_rotamer = _summary(_read_json(args.statistical_rotamer_json))
    sidechain_native = _summary(_read_json(args.sidechain_native_benchmark_json))
    refinement_ablation = _summary(_read_json(args.refinement_ablation_json))
    win = _summary(win_payload)
    win_rows = _rows_by_dimension(win_payload)

    all_atom = win_rows.get("all_atom_steric_quality", {})
    monomer = win_rows.get("monomer_native_accuracy", {})
    complex_row = win_rows.get("complex_interface_accuracy", {})
    refinement_ablation_row = win_rows.get("refinement_ablation_native_evidence", {})
    calibration_row = win_rows.get("confidence_and_model_selection_calibration", {})
    visuals = win_rows.get("publication_and_qc_visuals", {})
    refinement_ablation_has_rows = (
        int(refinement_ablation.get("usable_layer_count", 0) or 0) > 0
        or int(refinement_ablation.get("ablation_group_count", 0) or 0) > 0
    )
    refinement_ablation_has_input_blocker = bool(
        refinement_ablation.get("manifest_blockers")
        or refinement_ablation.get("config_blockers")
        or historical_benchmark.get("historical_benchmark_status") != "pass"
        or not refinement_ablation_has_rows
    )

    rows = [
        _row(
            priority=1,
            action_id="all_atom_quality_upgrade",
            lane="internal_quality",
            status=(
                "pass"
                if all_atom.get("status") == "pass"
                else "blocked_input"
                if sidechain_native.get("sidechain_native_benchmark_status") != "pass"
                else "ready_internal_development"
            ),
            related_dimension="all_atom_steric_quality",
            required_level=str(all_atom.get("required_level", "Native-scored all-atom steric and sidechain quality evidence.")),
            current_evidence=str(all_atom.get("current_evidence", "missing")),
            inputs_needed="No external predictor input. Needs no-leak historical prediction/native PDB pairs with sidechain atoms, chain/residue/atom exactness, and leakage clearance.",
            command=(
                "python3 tools/build_casp17_statistical_rotamer_packet.py "
                "--source-dir runs/casp17_predictions_forcefield_minimized_current "
                "--out-dir runs/casp17_predictions_statistical_rotamer_current && "
                "python3 tools/build_casp17_sidechain_native_benchmark_packet.py "
                "--manifest-csv runs/casp17_historical_benchmark_manifest_current.csv && "
                "python3 tools/build_casp17_competitive_readiness_packet.py "
                "--prediction-dir runs/casp17_predictions_statistical_rotamer_current "
                "--polar-refinement-json runs/casp17_polar_refinement_packet_current.json "
                "--forcefield-minimization-json runs/casp17_forcefield_minimization_packet_current.json "
                "--statistical-rotamer-json runs/casp17_statistical_rotamer_packet_current.json "
                "--sidechain-native-benchmark-json runs/casp17_sidechain_native_benchmark_packet_current.json "
                "--refinement-ablation-json runs/casp17_refinement_ablation_packet_current.json"
            ),
            done_when="all_atom_and_sidechain_quality becomes pass in competitive readiness, and win rubric no longer lists all_atom_steric_quality as first gap.",
            blockers="sidechain_native_benchmark_missing_or_blocked"
            if all_atom.get("status") != "pass" and sidechain_native.get("sidechain_native_benchmark_status") != "pass"
            else ("" if all_atom.get("status") != "blocked" else "all_atom_quality_blocked"),
            evidence_artifacts=(
                f"{_artifact(args.competitive_readiness_json)};"
                "runs/casp17_all_atom_quality_packet_current.json;"
                "runs/casp17_sidechain_quality_packet_current.json;"
                "runs/casp17_rotamer_minimization_packet_current.json;"
                f"{_artifact(args.polar_refinement_json)};"
                f"{_artifact(args.forcefield_minimization_json)};"
                f"{_artifact(args.statistical_rotamer_json)};"
                f"{_artifact(args.sidechain_native_benchmark_json)}"
            ),
        ),
        _row(
            priority=2,
            action_id="historical_benchmark_inputs",
            lane="no_leak_native_benchmark",
            status="blocked_input" if int(historical_scaffold.get("ready_count", 0) or 0) == 0 else "ready_to_promote",
            related_dimension="monomer_native_accuracy;complex_interface_accuracy",
            required_level=(
                f"{monomer.get('required_level', 'No-leak monomer native benchmark')}; "
                f"{complex_row.get('required_level', 'No-leak complex/interface native benchmark')}"
            ),
            current_evidence=(
                f"manifest_scaffold={historical_scaffold.get('scaffold_status', 'missing')}; "
                f"ready={historical_scaffold.get('ready_count', 0)}/{historical_scaffold.get('candidate_count', 0)}; "
                f"promotion={historical_promotion.get('promotion_status', 'missing')}; "
                f"promoted={historical_promotion.get('promoted_count', 0)}; "
                f"preflight={historical_input_preflight.get('preflight_status', 'missing')}; "
                f"historical_ready={historical_input_preflight.get('historical_ready_count', 0)}; "
                f"ablation_ready={historical_input_preflight.get('ablation_ready_count', 0)}; "
                f"missing_layer_files={historical_input_preflight.get('missing_ablation_layer_file_count', 0)}; "
                f"workorder={historical_input_workorder.get('workorder_status', 'missing')}; "
                f"core_workorders={historical_input_workorder.get('core_input_workorder_count', 0)}; "
                f"template={historical_input_workorder.get('operator_template_csv', '')}"
            ),
            inputs_needed=(
                "Local historical prediction/native PDB pairs only; no current CASP17 targets, no template/public leakage, "
                "explicit leakage_clearance=no_leak, exact chain IDs, scope chain count, residue-key overlap, residue identity, "
                "and optional per-layer ablation prediction paths where final-vs-baseline evidence is needed."
            ),
            command=(
                "python3 tools/build_casp17_historical_benchmark_manifest_scaffold.py && "
                "python3 tools/build_casp17_historical_benchmark_manifest_promotion.py && "
                "python3 tools/build_casp17_historical_input_preflight_packet.py && "
                "python3 tools/build_casp17_historical_input_workorder_packet.py"
            ),
            done_when="promotion_status=ready with at least one monomer and one complex row, then ready manifest is copied into the active historical benchmark manifest by operator decision.",
            blockers=str(historical_promotion.get("threshold_blockers") or historical_scaffold.get("existing_manifest_blockers") or "historical_rows_missing"),
            evidence_artifacts=f"{_artifact(args.historical_scaffold_json)};{_artifact(args.historical_promotion_json)};{_artifact(args.historical_input_preflight_json)};{_artifact(args.historical_input_workorder_json)}",
        ),
        _row(
            priority=3,
            action_id="historical_native_scoring",
            lane="no_leak_native_benchmark",
            status="blocked_input" if historical_benchmark.get("historical_benchmark_status") != "pass" else "pass",
            related_dimension="monomer_native_accuracy;complex_interface_accuracy",
            required_level="Historical native benchmark rows must pass chain/residue exactness before TM/GDT/lDDT/interface proxy scores can count.",
            current_evidence=(
                f"historical_status={historical_benchmark.get('historical_benchmark_status', 'missing')}; "
                f"benchmarks={historical_benchmark.get('benchmark_count', 0)}; "
                f"sequence_exact={historical_benchmark.get('sequence_exact_match_count', 0)}/{historical_benchmark.get('benchmark_count', 0)}; "
                f"chain_exact={historical_benchmark.get('chain_exact_match_count', 0)}/{historical_benchmark.get('benchmark_count', 0)}; "
                f"mean_DockQ_proxy={historical_benchmark.get('mean_complex_dockq_proxy', 0.0)}; "
                f"mean_QSbest_proxy={historical_benchmark.get('mean_complex_qsbest_proxy', 0.0)}"
            ),
            inputs_needed="Active runs/casp17_historical_benchmark_manifest_current.csv promoted from ready no-leak rows.",
            command="python3 tools/build_casp17_historical_benchmark_packet.py --manifest-csv runs/casp17_historical_benchmark_manifest_current.csv",
            done_when="historical_benchmark_status=pass, monomer_win_tier_status=pass, complex_win_tier_status=pass.",
            blockers=str(historical_benchmark.get("manifest_blockers") or "historical_manifest_missing_or_not_ready"),
            evidence_artifacts=_artifact(args.historical_benchmark_json),
        ),
        _row(
            priority=4,
            action_id="refinement_ablation_native_evidence",
            lane="no_leak_native_benchmark",
            status=(
                "pass"
                if refinement_ablation.get("refinement_ablation_status") == "pass"
                else "blocked_input"
                if refinement_ablation_has_input_blocker
                else "ready_to_score"
            ),
            related_dimension="refinement_ablation_native_evidence",
            required_level=str(
                refinement_ablation_row.get(
                    "required_level",
                    "Final selected refinement layer must be no-worse than the recursive baseline on no-leak historical native proxy metrics.",
                )
            ),
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
                f"mean_delta_CA_lDDT={refinement_ablation.get('mean_delta_ca_lddt_proxy', 0.0)}"
            ),
            inputs_needed="Active no-leak historical manifest plus layer directories or layer-specific manifest columns for recursive baseline through final statistical-rotamer refinement.",
            command="python3 tools/build_casp17_refinement_ablation_packet.py --manifest-csv runs/casp17_historical_benchmark_manifest_current.csv",
            done_when="refinement_ablation_status=pass with final_not_worse and required final_improved evidence across no-leak historical groups.",
            blockers=str(
                refinement_ablation.get("manifest_blockers")
                or refinement_ablation.get("threshold_blockers")
                or "refinement_ablation_missing_or_blocked"
            )
            if refinement_ablation.get("refinement_ablation_status") != "pass"
            else "",
            evidence_artifacts=_artifact(args.refinement_ablation_json),
        ),
        _row(
            priority=5,
            action_id="model_selection_calibration_inputs",
            lane="model_selection",
            status="blocked_input" if int(calibration_scaffold.get("ready_count", 0) or 0) == 0 else "ready_to_score",
            related_dimension="confidence_and_model_selection_calibration",
            required_level=str(calibration_row.get("required_level", "Native-calibrated SCORE/QSCORE and top-5 model selection.")),
            current_evidence=(
                f"calibration_scaffold={calibration_scaffold.get('scaffold_status', 'missing')}; "
                f"ready={calibration_scaffold.get('ready_count', 0)}/{calibration_scaffold.get('candidate_count', 0)}; "
                f"historical_status={calibration_scaffold.get('historical_benchmark_status', 'missing')}"
            ),
            inputs_needed="No-leak historical top-5 rows with selected/best model ranks, native metrics, selected/best internal scores, and leakage clearance.",
            command="python3 tools/build_casp17_model_selection_calibration_scaffold.py",
            done_when="runs/casp17_model_selection_calibration_current.csv has ready monomer and complex rows from no-leak historical targets.",
            blockers=str(calibration_scaffold.get("existing_csv_blockers") or "calibration_rows_missing"),
            evidence_artifacts=_artifact(args.calibration_scaffold_json),
        ),
        _row(
            priority=6,
            action_id="model_selection_calibration_gate",
            lane="model_selection",
            status="blocked_input" if calibration.get("calibration_status") != "pass" else "pass",
            related_dimension="confidence_and_model_selection_calibration",
            required_level="Selected MODEL 1 must be close to oracle best-of-five on no-leak historical targets; SCORE/QSCORE coverage is not enough by itself.",
            current_evidence=(
                f"calibration={calibration.get('calibration_status', 'missing')}; "
                f"rows={calibration.get('calibration_pass_count', 0)}/{calibration.get('calibration_row_count', 0)}; "
                f"mean_loss={calibration.get('mean_selection_loss', 0)}; "
                f"ranked_depth={calibration.get('ranked_candidate_depth_status', 'missing')}"
            ),
            inputs_needed="runs/casp17_model_selection_calibration_current.csv from no-leak historical top-5 evidence.",
            command="python3 tools/build_casp17_model_selection_calibration_packet.py",
            done_when="calibration_status=pass and mean/max selected-vs-oracle loss are below configured thresholds.",
            blockers="calibration_csv_missing_or_blocked" if calibration.get("calibration_status") != "pass" else "",
            evidence_artifacts=_artifact(args.calibration_json),
        ),
        _row(
            priority=7,
            action_id="visual_review_current",
            lane="review_quality",
            status="pass" if visuals.get("status") == "pass" else "blocked",
            related_dimension="publication_and_qc_visuals",
            required_level=str(visuals.get("required_level", "Base/surface/QC/review images for every current target.")),
            current_evidence=str(visuals.get("current_evidence", "missing")),
            inputs_needed="Regenerate renders after every coordinate update.",
            command=(
                "python3 tools/build_casp17_structure_render_packet.py "
                "--prediction-dir runs/casp17_predictions_statistical_rotamer_current "
                "--pymol-render --pymol-qc-render --pymol-surface-render"
            ),
            done_when="rendered/base/surface/QC/review counts all equal target_count and pixel smoke is nonflat.",
            blockers="" if visuals.get("status") == "pass" else "render_review_missing",
            evidence_artifacts=_artifact(args.render_json),
        ),
        _row(
            priority=8,
            action_id="final_submission_confirmation",
            lane="external_state",
            status="blocked_r4_confirmation" if win.get("win_tier_level_status") != "pass" else "needs_r4_confirmation",
            related_dimension="official_format_and_gate",
            required_level="Only submit after local fail-closed gates pass and the operator explicitly confirms CASP portal upload.",
            current_evidence=(
                f"submission={win.get('submission_level_status', 'missing')}; "
                f"review={win.get('review_quality_status', 'missing')}; "
                f"competitive={win.get('competitive_floor_status', 'missing')}; "
                f"win_tier={win.get('win_tier_level_status', 'missing')}"
            ),
            inputs_needed="CASP author code at runtime and explicit R4 confirmation.",
            command="python3 tools/build_casp17_submission_gate_packet.py --intake-csv runs/casp17_target_intake_scored_statistical_rotamer_current.csv",
            done_when="CASP submission is explicitly confirmed and portal receipt/status matches intended target files.",
            blockers="win_tier_not_pass" if win.get("win_tier_level_status") != "pass" else "external_state_confirmation_required",
            evidence_artifacts=f"{_artifact(args.win_rubric_json)};runs/casp17_submission_gate_packet_statistical_rotamer_current.json;{_artifact(args.polar_refinement_json)};{_artifact(args.forcefield_minimization_json)};{_artifact(args.statistical_rotamer_json)}",
        ),
    ]

    pass_count = sum(1 for row in rows if row["status"] == "pass")
    ready_count = sum(1 for row in rows if row["status"].startswith("ready"))
    blocked_count = len(rows) - pass_count - ready_count
    first_not_pass = next((row for row in rows if row["status"] != "pass"), None)
    summary = {
        "packet_type": "casp17_win_tier_action_queue_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "win_rubric_json": _artifact(args.win_rubric_json),
        "competitive_readiness_json": _artifact(args.competitive_readiness_json),
        "historical_input_preflight_status": historical_input_preflight.get("preflight_status", "missing"),
        "historical_input_preflight_json": _artifact(args.historical_input_preflight_json),
        "historical_input_workorder_status": historical_input_workorder.get("workorder_status", "missing"),
        "historical_input_workorder_json": _artifact(args.historical_input_workorder_json),
        "historical_input_workorder_count": historical_input_workorder.get("workorder_count", 0),
        "target_count": int(win.get("target_count", competitive.get("target_count", render.get("target_count", 0))) or 0),
        "submission_level_status": win.get("submission_level_status", "missing"),
        "review_quality_status": win.get("review_quality_status", "missing"),
        "competitive_floor_status": win.get("competitive_floor_status", "missing"),
        "win_tier_level_status": win.get("win_tier_level_status", "missing"),
        "polar_refinement_status": polar_refinement.get("polar_refinement_status", "missing"),
        "polar_refinement_json": _artifact(args.polar_refinement_json),
        "forcefield_minimization_status": forcefield_minimization.get("forcefield_minimization_status", "missing"),
        "forcefield_minimization_json": _artifact(args.forcefield_minimization_json),
        "statistical_rotamer_status": statistical_rotamer.get("statistical_rotamer_status", "missing"),
        "statistical_rotamer_json": _artifact(args.statistical_rotamer_json),
        "sidechain_native_benchmark_status": sidechain_native.get("sidechain_native_benchmark_status", "missing"),
        "sidechain_native_benchmark_json": _artifact(args.sidechain_native_benchmark_json),
        "refinement_ablation_status": refinement_ablation.get("refinement_ablation_status", "missing"),
        "refinement_ablation_json": _artifact(args.refinement_ablation_json),
        "action_count": len(rows),
        "pass_count": pass_count,
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "first_not_pass_action_id": first_not_pass["action_id"] if first_not_pass else "",
        "first_not_pass_status": first_not_pass["status"] if first_not_pass else "",
        "first_not_pass_blockers": first_not_pass["blockers"] if first_not_pass else "",
        "action_queue_status": "pass" if blocked_count == 0 and ready_count == 0 else "blocked",
        "claim_boundary": "Internal CASP17 win-tier action queue only; it does not fetch native structures, prove current-target accuracy, submit to CASP, or replace official CASP assessment.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Action Queue Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- action_queue_status: `{summary['action_queue_status']}`",
        f"- submission/review/competitive/win: `{summary['submission_level_status']}/{summary['review_quality_status']}/{summary['competitive_floor_status']}/{summary['win_tier_level_status']}`",
        f"- historical_input_preflight: `{summary['historical_input_preflight_status']}`",
        f"- historical_input_workorder: `{summary.get('historical_input_workorder_status')}` ({summary.get('historical_input_workorder_count', 0)} rows)",
        f"- forcefield/statistical_rotamer/sidechain_native/ablation: `{summary['forcefield_minimization_status']}/{summary['statistical_rotamer_status']}/{summary['sidechain_native_benchmark_status']}/{summary['refinement_ablation_status']}`",
        f"- pass/ready/blocked: `{summary['pass_count']}/{summary['ready_count']}/{summary['blocked_count']}`",
        f"- first_not_pass: `{summary['first_not_pass_action_id'] or '-'}` (`{summary['first_not_pass_status'] or '-'}`)",
        "",
        "## Actions",
        "",
        "| priority | action | lane | status | dimension | current evidence | inputs needed | blockers | done when |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['action_id']}` | `{row['lane']}` | `{row['status']}` | "
            f"`{row['related_dimension']}` | {row['current_evidence']} | {row['inputs_needed']} | "
            f"{row['blockers'] or '-'} | {row['done_when']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CASP17 win-tier action queue packet.")
    parser.add_argument("--win-rubric-json", default=DEFAULT_WIN_RUBRIC_JSON)
    parser.add_argument("--competitive-readiness-json", default=DEFAULT_COMPETITIVE_READINESS_JSON)
    parser.add_argument("--historical-scaffold-json", default=DEFAULT_HISTORICAL_SCAFFOLD_JSON)
    parser.add_argument("--historical-promotion-json", default=DEFAULT_HISTORICAL_PROMOTION_JSON)
    parser.add_argument("--historical-input-preflight-json", default=DEFAULT_HISTORICAL_INPUT_PREFLIGHT_JSON)
    parser.add_argument("--historical-input-workorder-json", default=DEFAULT_HISTORICAL_INPUT_WORKORDER_JSON)
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--calibration-scaffold-json", default=DEFAULT_CALIBRATION_SCAFFOLD_JSON)
    parser.add_argument("--calibration-json", default=DEFAULT_CALIBRATION_JSON)
    parser.add_argument("--render-json", default=DEFAULT_RENDER_JSON)
    parser.add_argument("--polar-refinement-json", default=DEFAULT_POLAR_REFINEMENT_JSON)
    parser.add_argument("--forcefield-minimization-json", default=DEFAULT_FORCEFIELD_MINIMIZATION_JSON)
    parser.add_argument("--statistical-rotamer-json", default=DEFAULT_STATISTICAL_ROTAMER_JSON)
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
    parser.add_argument("--refinement-ablation-json", default=DEFAULT_REFINEMENT_ABLATION_JSON)
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
