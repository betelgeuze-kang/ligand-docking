#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GOAL_ADDENDUM_MD = "casp17/CASP17_WIN_TIER_GOAL.md"
DEFAULT_WIN_GAP_CLOSURE_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_BENCHMARK_INPUT_INVENTORY_JSON = "runs/casp17_win_tier_benchmark_input_inventory_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_MODEL_SELECTION_CALIBRATION_JSON = "runs/casp17_model_selection_calibration_packet_current.json"
DEFAULT_REPLACEMENT_WORKORDER_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_audit_current.json"
)
DEFAULT_OUT_JSON = "runs/casp17_win_tier_goal_scorecard_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_goal_scorecard_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_goal_scorecard_current.md"

REQUIRED_METRIC_SURFACE = [
    "GDT_TS",
    "lDDT",
    "TM-score",
    "RMSD",
    "GDT_HA",
    "MolProbity",
    "DockQ",
    "ICS",
    "IPS",
    "LDDT-PLI",
    "BiSyRMSD",
]

PRIORITY_CATEGORIES = [
    "immune_protein_complexes",
    "organic_ligand_protein_complexes",
    "accuracy_estimation_model_selection",
    "difficult_monomer_domain",
]

HISTORICAL_BANDS = {
    "casp15_regular_domain": {
        "winner_group": "Yang-Server",
        "winner_sum_zscore": 90.4273,
        "top5_cutoff": 73.0,
        "top3_cutoff": 85.0,
        "winner_proximity_ratio": 0.90,
    },
    "casp16_regular_domain": {
        "winner_group": "Yang-Server",
        "winner_sum_zscore": 40.8978,
        "top5_cutoff": 33.3,
        "top3_cutoff": 36.3,
        "winner_proximity_ratio": 0.90,
    },
    "casp16_multimer_complex": {
        "dockq_acceptable": 0.23,
        "dockq_medium": 0.49,
        "dockq_high": 0.80,
        "win_target_acceptable_fraction": 0.90,
        "win_target_medium_fraction": 0.70,
        "win_target_general_high_fraction": 0.50,
        "win_target_immune_high_fraction": 0.40,
    },
    "casp16_ligand": {
        "participant_mean_lddt_pli": 0.70,
        "af3_baseline_mean_lddt_pli": 0.80,
        "bisyrmsd_2a_hit_fraction": 0.60,
        "best_observed_affinity_kendall_tau": 0.42,
        "win_candidate_affinity_kendall_tau": 0.55,
    },
}


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


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _status(pass_condition: bool, *, partial_condition: bool = False) -> str:
    if pass_condition:
        return "pass"
    return "partial" if partial_condition else "blocked_input"


def _row(
    *,
    priority: int,
    gate: str,
    category: str,
    status: str,
    target: str,
    current: str,
    evidence_source: str,
    blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "gate": gate,
        "category": category,
        "status": status,
        "target": target,
        "current": current,
        "evidence_source": evidence_source,
        "blocker": blocker,
        "next_action": next_action,
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
        fieldnames = ["priority", "gate", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _metric_surface_pass(historical: dict[str, Any]) -> tuple[bool, str]:
    if _text(historical.get("metric_surface_status")) == "pass":
        return True, "metric_surface_status=pass"
    present = []
    for metric in REQUIRED_METRIC_SURFACE:
        normalized = metric.lower().replace("-", "_").replace(" ", "_")
        if historical.get(f"has_{normalized}") or historical.get(f"mean_{normalized}") is not None:
            present.append(metric)
    return len(present) == len(REQUIRED_METRIC_SURFACE), ",".join(present) or "none"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    goal_path = _resolve(args.goal_addendum_md)
    closure = _summary(_read_json(args.win_gap_closure_json))
    inventory = _summary(_read_json(args.benchmark_input_inventory_json))
    sidechain = _summary(_read_json(args.sidechain_native_benchmark_json))
    historical = _summary(_read_json(args.historical_benchmark_json))
    calibration = _summary(_read_json(args.model_selection_calibration_json))
    replacement_audit = _summary(_read_json(args.replacement_workorder_audit_json))

    goal_text = goal_path.read_text(encoding="utf-8", errors="replace") if goal_path.exists() else ""
    goal_documented = (
        goal_path.exists()
        and "CASP17 scaffold score" in goal_text
        and "competitive proof score" in goal_text
        and "top-5" in goal_text
    )

    closure_pass = _text(closure.get("closure_status")) == "pass"
    identity_blocked = _text(closure.get("first_operator_input_action_id")) == "historical_benchmark_inputs"
    identity_cleared = closure_pass and not identity_blocked
    replacement_audit_next_action = _text(replacement_audit.get("first_blocked_next_action"))
    identity_next_action = (
        replacement_audit_next_action
        if replacement_audit_next_action
        else "Replace placeholder benchmark/target IDs with operator-cleared historical non-CASP17 targets."
    )

    required_files = _int(inventory.get("required_file_count"))
    present_files = _int(inventory.get("present_file_count"))
    missing_files = _int(inventory.get("missing_file_count"))
    required_files_pass = required_files > 0 and present_files == required_files and missing_files == 0

    sidechain_pass_count = _int(sidechain.get("pass_count"))
    sidechain_total = _int(sidechain.get("benchmark_count"))
    sidechain_pass = (
        _text(sidechain.get("sidechain_native_benchmark_status")) == "pass"
        and sidechain_pass_count >= 40
        and sidechain_total >= 40
    )

    metric_surface_pass, metric_surface_current = _metric_surface_pass(historical)

    casp15_ratio = _float(historical.get("casp15_regular_domain_winner_ratio"))
    casp16_ratio = _float(historical.get("casp16_regular_domain_winner_ratio"))
    normalized_ratio_pass = casp15_ratio >= 0.90 and casp16_ratio >= 0.90

    monomer_ratio = _float(historical.get("casp16_domain_winner_ratio"), casp16_ratio)
    monomer_gap = _float(historical.get("model1_best_of5_gap_fraction"), 1.0)
    monomer_catastrophic = _int(historical.get("catastrophic_fail_count"), 999)
    monomer_pass = (
        _text(historical.get("monomer_win_tier_status")) == "pass"
        and monomer_ratio >= 0.90
        and monomer_gap <= 0.10
        and monomer_catastrophic == 0
    )

    dockq_acceptable = _float(historical.get("dockq_acceptable_fraction"))
    dockq_medium = _float(historical.get("dockq_medium_fraction"))
    dockq_high = _float(historical.get("dockq_high_fraction"))
    immune_high = _float(historical.get("immune_hard_target_high_fraction"), dockq_high)
    complex_pass = (
        dockq_acceptable >= 0.90
        and dockq_medium >= 0.70
        and dockq_high >= 0.50
        and immune_high >= 0.40
    )

    mean_lddt_pli = _float(historical.get("mean_lddt_pli"))
    bisyrmsd_hit = _float(historical.get("bisyrmsd_2a_hit_fraction"))
    affinity_tau = _float(historical.get("affinity_kendall_tau"))
    ligand_pass = mean_lddt_pli >= 0.80 and bisyrmsd_hit >= 0.70 and affinity_tau >= 0.55
    ligand_partial = mean_lddt_pli >= 0.70 and bisyrmsd_hit >= 0.60 and affinity_tau >= 0.42

    top1_selection = _float(calibration.get("top1_selection_accuracy"))
    score_correlation = _float(
        calibration.get("score_native_correlation"),
        _float(calibration.get("score_native_correlation_proxy")),
    )
    high_conf_fp = _float(calibration.get("high_confidence_false_positive_rate"), 1.0)
    selection_pass = (
        _text(calibration.get("calibration_status")) == "pass"
        and top1_selection >= 0.70
        and score_correlation >= 0.70
        and high_conf_fp <= 0.05
    )

    rows = [
        _row(
            priority=1,
            gate="goal_contract_documented",
            category="scaffold_and_proof",
            status=_status(goal_documented),
            target="scaffold 65 -> 90; competitive proof 15-25 -> 85-90",
            current="documented" if goal_documented else "missing or incomplete",
            evidence_source=_artifact(args.goal_addendum_md),
            blocker="" if goal_documented else "goal_addendum_missing_or_incomplete",
            next_action="Keep this addendum linked from the workbench and scorecard before claiming win-tier progress.",
        ),
        _row(
            priority=2,
            gate="historical_identity_clearance",
            category="competitive_floor_unlock",
            status=_status(identity_cleared, partial_condition=not identity_blocked and bool(closure)),
            target="cleared non-CASP17 historical identities with no-leak provenance",
            current=(
                f"closure={closure.get('closure_status', 'missing')}; "
                f"first_operator={closure.get('first_operator_input_action_id', 'missing')}; "
                f"replacement_audit={replacement_audit.get('clearance_workorder_audit_status', 'missing')}"
            ),
            evidence_source=f"{_artifact(args.win_gap_closure_json)};{_artifact(args.replacement_workorder_audit_json)}",
            blocker="" if identity_cleared else "historical_benchmark_inputs_still_required",
            next_action=identity_next_action,
        ),
        _row(
            priority=3,
            gate="required_files_present",
            category="competitive_floor_unlock",
            status=_status(required_files_pass, partial_condition=present_files > 0),
            target="required files 480/480 present",
            current=f"{present_files}/{required_files}; missing={missing_files}",
            evidence_source=_artifact(args.benchmark_input_inventory_json),
            blocker="" if required_files_pass else "required_benchmark_files_missing",
            next_action="Fill prediction/native/core/ablation/provenance/calibration paths for every benchmark row.",
        ),
        _row(
            priority=4,
            gate="sidechain_native_40",
            category="competitive_floor_unlock",
            status=_status(sidechain_pass, partial_condition=sidechain_pass_count > 0),
            target="sidechain-native benchmark 40/40 pass",
            current=(
                f"status={sidechain.get('sidechain_native_benchmark_status', 'missing')}; "
                f"pass={sidechain_pass_count}/{sidechain_total}"
            ),
            evidence_source=_artifact(args.sidechain_native_benchmark_json),
            blocker="" if sidechain_pass else "sidechain_native_40_pass_not_proven",
            next_action="Place cleared native/prediction PDBs and no-leak provenance, then rerun the sidechain-native packet.",
        ),
        _row(
            priority=5,
            gate="metric_surface",
            category="competitive_floor_unlock",
            status=_status(metric_surface_pass),
            target=", ".join(REQUIRED_METRIC_SURFACE),
            current=metric_surface_current,
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if metric_surface_pass else "official_like_metric_surface_missing",
            next_action="Generate the complete native metric surface before comparing against historical winner bands.",
        ),
        _row(
            priority=6,
            gate="winner_normalized_replay",
            category="historical_benchmark",
            status=_status(normalized_ratio_pass, partial_condition=max(casp15_ratio, casp16_ratio) > 0.0),
            target="CASP15 and CASP16 regular-domain winner-normalized ratio >= 0.90",
            current=f"CASP15={casp15_ratio:.3f}; CASP16={casp16_ratio:.3f}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if normalized_ratio_pass else "winner_normalized_ratios_missing_or_below_0_90",
            next_action="Score no-leak historical replay rows and compare against official CASP15/16 top bands.",
        ),
        _row(
            priority=7,
            gate="difficult_monomer_domain",
            category="difficult_monomer_domain",
            status=_status(monomer_pass, partial_condition=monomer_ratio > 0.0),
            target="CASP16 winner ratio >=0.90, model1 within 5-10% best-of-5, catastrophic fails 0",
            current=f"ratio={monomer_ratio:.3f}; model1_gap={monomer_gap:.3f}; catastrophic={monomer_catastrophic}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if monomer_pass else "monomer_win_tier_replay_not_proven",
            next_action="Use no-leak historical replay to tune hard-target generation and model1 selection.",
        ),
        _row(
            priority=8,
            gate="immune_protein_complex",
            category="immune_protein_complexes",
            status=_status(complex_pass, partial_condition=max(dockq_acceptable, dockq_medium, dockq_high) > 0.0),
            target="DockQ acceptable >=90%, medium >=70%, high >=50% general and >=40% hard immune",
            current=(
                f"acceptable={dockq_acceptable:.3f}; medium={dockq_medium:.3f}; "
                f"high={dockq_high:.3f}; immune_high={immune_high:.3f}"
            ),
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if complex_pass else "dockq_fraction_win_band_not_proven",
            next_action="Add complex no-leak rows with DockQ/ICS/IPS and close the model1-vs-best-of-5 interface gap.",
        ),
        _row(
            priority=9,
            gate="organic_ligand_protein_complex",
            category="organic_ligand_protein_complexes",
            status=_status(ligand_pass, partial_condition=ligand_partial),
            target="mean LDDT-PLI >=0.80, BiSyRMSD<=2A hit >=70%, affinity tau >=0.55",
            current=f"LDDT-PLI={mean_lddt_pli:.3f}; BiSyRMSD_hit={bisyrmsd_hit:.3f}; tau={affinity_tau:.3f}",
            evidence_source=_artifact(args.historical_benchmark_json),
            blocker="" if ligand_pass else "ligand_pose_or_affinity_win_band_not_proven",
            next_action="Add ligand historical rows with LDDT-PLI, BiSyRMSD, pocket stability, and affinity ranking fields.",
        ),
        _row(
            priority=10,
            gate="accuracy_estimation_model_selection",
            category="accuracy_estimation_model_selection",
            status=_status(selection_pass, partial_condition=top1_selection > 0.0),
            target="top1 selection >=70%, score/native correlation >=0.70, high-confidence false positives <=5%",
            current=f"top1={top1_selection:.3f}; corr={score_correlation:.3f}; high_conf_fp={high_conf_fp:.3f}",
            evidence_source=_artifact(args.model_selection_calibration_json),
            blocker="" if selection_pass else "model_selection_calibration_win_band_not_proven",
            next_action="Calibrate top-5 ranking against no-leak native metrics and record model1 versus best-of-5 loss.",
        ),
    ]

    pass_count = sum(1 for row in rows if row["status"] == "pass")
    partial_count = sum(1 for row in rows if row["status"] == "partial")
    blocked_count = len(rows) - pass_count - partial_count
    first_blocked = next((row for row in rows if row["status"] != "pass"), {})
    scorecard_status = "pass" if blocked_count == 0 and partial_count == 0 else "partial" if blocked_count == 0 else "blocked_input"
    summary = {
        "packet_type": "casp17_win_tier_goal_scorecard",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scorecard_status": scorecard_status,
        "row_count": len(rows),
        "pass_count": pass_count,
        "partial_count": partial_count,
        "blocked_count": blocked_count,
        "first_blocked_gate": first_blocked.get("gate", ""),
        "first_blocked_category": first_blocked.get("category", ""),
        "first_blocked_next_action": first_blocked.get("next_action", ""),
        "scaffold_score_current": 65,
        "scaffold_score_target": 90,
        "competitive_proof_score_current_band": "15-25",
        "competitive_proof_score_target_band": "85-90",
        "priority_categories": PRIORITY_CATEGORIES,
        "historical_bands": HISTORICAL_BANDS,
        "required_metric_surface": REQUIRED_METRIC_SURFACE,
        "replacement_workorder_audit_json": _artifact(args.replacement_workorder_audit_json),
        "claim_boundary": (
            "Goal scorecard only. It tracks whether the CASP17 win-tier evidence contract is closed; "
            "it does not claim current-target native accuracy, CASP17 submission success, or official ranking."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Goal Scorecard",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- scorecard_status: `{summary['scorecard_status']}`",
        f"- pass/partial/blocked: `{summary['pass_count']}/{summary['partial_count']}/{summary['blocked_count']}`",
        f"- scaffold score: `{summary['scaffold_score_current']} -> {summary['scaffold_score_target']}`",
        f"- competitive proof score: `{summary['competitive_proof_score_current_band']} -> {summary['competitive_proof_score_target_band']}`",
        f"- first blocked gate: `{summary['first_blocked_gate'] or '-'}`",
        "",
        "## Gates",
        "",
        "| priority | gate | category | status | target | current | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['gate']}` | `{row['category']}` | `{row['status']}` | "
            f"{row['target']} | {row['current']} | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CASP17 win-tier goal scorecard.")
    parser.add_argument("--goal-addendum-md", default=DEFAULT_GOAL_ADDENDUM_MD)
    parser.add_argument("--win-gap-closure-json", default=DEFAULT_WIN_GAP_CLOSURE_JSON)
    parser.add_argument("--benchmark-input-inventory-json", default=DEFAULT_BENCHMARK_INPUT_INVENTORY_JSON)
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--model-selection-calibration-json", default=DEFAULT_MODEL_SELECTION_CALIBRATION_JSON)
    parser.add_argument("--replacement-workorder-audit-json", default=DEFAULT_REPLACEMENT_WORKORDER_AUDIT_JSON)
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
