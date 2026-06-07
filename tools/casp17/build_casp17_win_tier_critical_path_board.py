#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROTEIN_OBJECT_LIBRARY_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_protein_object_library_completion_audit_current.json"
)
DEFAULT_MASSIVEFOLD_RNA_MODEL_SELECTION_COVERAGE_JSON = (
    "casp17/casp17_massivefold_rna_model_selection_coverage_current.json"
)
DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_MODEL_SELECTION_COVERAGE_JSON = (
    "casp17/casp17_protein_complex_massivefold_model_selection_coverage_current.json"
)
DEFAULT_WIN_TIER_METRIC_SURFACE_CONTRACT_JSON = "casp17/casp17_win_tier_metric_surface_contract_current.json"
DEFAULT_STRICT_BLIND_BATCH_CLOSURE_RUNWAY_JSON = (
    "casp17/casp17_strict_blind_batch_closure_runway_current.json"
)
DEFAULT_STRICT_BLIND_REPLACEMENT_CYCLE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_cycle_current.json"
)
DEFAULT_STRICT_BLIND_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_COMPETITIVE_READINESS_GATE_JSON = "casp17/casp17_competitive_floor_readiness_gate_current.json"
DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_CYCLE_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_win_tier_critical_path_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_win_tier_critical_path_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_WIN_TIER_CRITICAL_PATH_BOARD.md"

ROW_COLUMNS = [
    "stage_id",
    "stage_order",
    "stage_status",
    "ready_count",
    "blocked_count",
    "total_count",
    "proof_boundary",
    "first_blocker",
    "next_action",
    "artifact",
]
CLAIM_BOUNDARY = (
    "Local CASP17 win-tier critical path board only. It summarizes already-generated 3D object assets, "
    "review-only MassiveFold model-selection coverage, strict-blind historical benchmark evidence gates, "
    "and competitive-floor identity gates. It does not create evidence, approve no-leak provenance, promote "
    "external models as internal predictions, compute official CASP metrics, mutate intake CSVs, push remotes, "
    "or submit to CASP."
)


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


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in [
        "protein_object_library_completion_audit_json",
        "massivefold_rna_model_selection_coverage_json",
        "protein_complex_massivefold_model_selection_coverage_json",
        "win_tier_metric_surface_contract_json",
        "strict_blind_batch_closure_runway_json",
        "strict_blind_replacement_cycle_json",
        "strict_blind_first_slot_kit_json",
        "competitive_readiness_gate_json",
        "competitive_target_identity_clearance_cycle_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _stage_row(
    stage_id: str,
    order: int,
    status: str,
    ready: int,
    blocked: int,
    total: int,
    boundary: str,
    first_blocker: str,
    next_action: str,
    artifact: str | Path,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_order": order,
        "stage_status": status or "missing",
        "ready_count": ready,
        "blocked_count": blocked,
        "total_count": total,
        "proof_boundary": boundary,
        "first_blocker": first_blocker,
        "next_action": next_action,
        "artifact": _artifact(artifact),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    protein_library = _summary(_read_json(args.protein_object_library_completion_audit_json))
    rna_coverage = _summary(_read_json(args.massivefold_rna_model_selection_coverage_json))
    protein_coverage = _summary(_read_json(args.protein_complex_massivefold_model_selection_coverage_json))
    metric_contract = _summary(_read_json(args.win_tier_metric_surface_contract_json))
    batch_runway = _summary(_read_json(args.strict_blind_batch_closure_runway_json))
    strict_cycle = _summary(_read_json(args.strict_blind_replacement_cycle_json))
    first_slot = _summary(_read_json(args.strict_blind_first_slot_kit_json))
    competitive_readiness = _summary(_read_json(args.competitive_readiness_gate_json))
    clearance_cycle = _summary(_read_json(args.competitive_target_identity_clearance_cycle_json))
    blockers = _input_blockers(args)

    object_total = _int(protein_library.get("object_folder_count"))
    object_ready = _int(protein_library.get("object_pass_count"))
    rna_total = _int(rna_coverage.get("target_count"))
    rna_ready = _int(rna_coverage.get("ready_target_count"))
    protein_total = _int(protein_coverage.get("target_count"))
    protein_ready = _int(protein_coverage.get("ready_target_count"))
    external_total = rna_total + protein_total
    external_ready = rna_ready + protein_ready
    strict_slot_total = (
        _int(batch_runway.get("slot_count"))
        if "slot_count" in batch_runway
        else _int(strict_cycle.get("slot_count"))
    )
    strict_slot_ready = (
        _int(batch_runway.get("ready_slot_count"))
        if "ready_slot_count" in batch_runway
        else _int(strict_cycle.get("promotion_ready_count"))
    )
    first_slot_total = _int(first_slot.get("evidence_action_count")) + _int(first_slot.get("operator_action_count"))
    first_slot_ready = _int(first_slot.get("evidence_ready_count")) + _int(first_slot.get("operator_ready_count"))
    metric_total = _int(metric_contract.get("metric_surface_row_count"))
    metric_ready = _int(metric_contract.get("ready_metric_row_count"))

    readiness_total = _int(competitive_readiness.get("gate_count"))
    readiness_ready = _int(competitive_readiness.get("pass_count"))
    clearance_total = _int(clearance_cycle.get("stage_count"))
    clearance_ready = _int(clearance_cycle.get("ready_stage_count"))

    rows = [
        _stage_row(
            "three_d_object_library",
            1,
            _text(protein_library.get("completion_audit_status")),
            object_ready,
            _int(protein_library.get("object_blocked_count")),
            object_total,
            "3D object organization is local review evidence only; it is not native accuracy proof.",
            _text(protein_library.get("first_blocked_blockers")),
            _text(protein_library.get("next_action"))
            or "keep protein-name folders, per-object manifests, model files, projections, and viewers green",
            args.protein_object_library_completion_audit_json,
        ),
        _stage_row(
            "massivefold_rna_review_model_selection",
            2,
            _text(rna_coverage.get("massivefold_rna_model_selection_coverage_status")),
            rna_ready,
            _int(rna_coverage.get("partial_target_count")),
            rna_total,
            "External MassiveFold RNA/hybrid pools are review-only model-selection inputs, not internal proof.",
            _text(rna_coverage.get("first_partial_target_id")),
            _text(rna_coverage.get("next_action")),
            args.massivefold_rna_model_selection_coverage_json,
        ),
        _stage_row(
            "massivefold_protein_complex_review_model_selection",
            3,
            _text(protein_coverage.get("protein_complex_massivefold_model_selection_coverage_status")),
            protein_ready,
            _int(protein_coverage.get("partial_target_count")),
            protein_total,
            "External MassiveFold protein/complex pools are conformation triage inputs, not internal proof.",
            _text(protein_coverage.get("first_partial_target_id")),
            _text(protein_coverage.get("next_action")),
            args.protein_complex_massivefold_model_selection_coverage_json,
        ),
        _stage_row(
            "strict_blind_batch_closure_runway",
            4,
            _text(batch_runway.get("batch_closure_runway_status")),
            _int(batch_runway.get("ready_slot_count")),
            _int(batch_runway.get("blocked_slot_count")),
            _int(batch_runway.get("slot_count")),
            "Competitive proof stays closed until batch slots have internal pre-native predictions, native authority, no-leak evidence, ablation, calibration, and operator clearance.",
            _text(batch_runway.get("first_blocking_stage"))
            or _text(batch_runway.get("first_blocked_benchmark_id")),
            _text(batch_runway.get("first_next_action")),
            args.strict_blind_batch_closure_runway_json,
        ),
        _stage_row(
            "strict_blind_replacement_cycle",
            5,
            _text(strict_cycle.get("strict_blind_replacement_cycle_status")),
            _int(strict_cycle.get("promotion_ready_count")),
            max(_int(strict_cycle.get("slot_count")) - _int(strict_cycle.get("promotion_ready_count")), 0),
            _int(strict_cycle.get("slot_count")),
            "Competitive proof requires pre-native internal predictions, native authority, no-leak evidence, ablation, and calibration.",
            _text(strict_cycle.get("first_blocking_stage")),
            _text(strict_cycle.get("first_next_action")),
            args.strict_blind_replacement_cycle_json,
        ),
        _stage_row(
            "first_strict_blind_slot_kit",
            6,
            _text(first_slot.get("strict_blind_replacement_first_slot_kit_status")),
            first_slot_ready,
            max(first_slot_total - first_slot_ready, 0),
            first_slot_total,
            "First-slot kit is an operator/evidence intake surface; no field is auto-approved.",
            _text(first_slot.get("first_open_field")),
            _text(first_slot.get("first_next_action")),
            _text(first_slot.get("kit_folder")) or args.strict_blind_first_slot_kit_json,
        ),
        _stage_row(
            "win_tier_metric_surface",
            7,
            _text(metric_contract.get("metric_surface_contract_status")),
            metric_ready,
            _int(metric_contract.get("blocked_metric_row_count")),
            metric_total,
            "Official-like metric surface is blocked until strict-blind slots are populated.",
            _text(metric_contract.get("first_blocked_benchmark_id"))
            or _text(metric_contract.get("first_blocked_metric")),
            _text(metric_contract.get("next_action")),
            args.win_tier_metric_surface_contract_json,
        ),
        _stage_row(
            "competitive_floor_identity_gate",
            8,
            _text(competitive_readiness.get("readiness_gate_status")),
            readiness_ready,
            _int(competitive_readiness.get("blocked_gate_count")),
            readiness_total,
            "Competitive-floor rows stay blocked until cleared historical benchmark/target identity is applied.",
            _text(competitive_readiness.get("first_blocked_gate_id")),
            _text(competitive_readiness.get("first_blocked_next_action")),
            args.competitive_readiness_gate_json,
        ),
        _stage_row(
            "competitive_target_identity_clearance_cycle",
            9,
            _text(clearance_cycle.get("clearance_cycle_status")),
            clearance_ready,
            _int(clearance_cycle.get("blocked_stage_count")),
            clearance_total,
            "Target identity clearance requires operator-cleared native files and provenance before promotion.",
            _text(clearance_cycle.get("operator_intake_status")),
            _text(clearance_cycle.get("first_next_action")),
            args.competitive_target_identity_clearance_cycle_json,
        ),
    ]

    stage_ready = sum(1 for row in rows if _int(row["total_count"]) and _int(row["blocked_count"]) == 0)
    stage_blocked = len(rows) - stage_ready
    if blockers:
        status = "blocked_missing_inputs"
    elif object_total and object_ready < object_total:
        status = "blocked_3d_object_library"
    elif external_total and external_ready < external_total:
        status = "review_only_model_selection_partial"
    elif strict_slot_total and strict_slot_ready == strict_slot_total and readiness_total and readiness_ready == readiness_total:
        status = "ready_for_competitive_floor_fill"
    else:
        status = "competitive_proof_blocked_on_strict_blind_evidence"

    first_blocked = next((row for row in rows if _int(row["blocked_count"]) > 0), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_win_tier_critical_path_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "critical_path_status": status,
        "stage_count": len(rows),
        "stage_ready_count": stage_ready,
        "stage_blocked_count": stage_blocked,
        "three_d_object_ready_count": object_ready,
        "three_d_object_count": object_total,
        "three_d_protein_folder_count": _int(protein_library.get("protein_folder_count")),
        "external_model_selection_ready_target_count": external_ready,
        "external_model_selection_target_count": external_total,
        "external_model_selection_model1_count": (
            _int(rna_coverage.get("model1_candidate_count"))
            + _int(protein_coverage.get("model1_candidate_count"))
        ),
        "external_model_selection_top5_count": (
            _int(rna_coverage.get("top5_candidate_count"))
            + _int(protein_coverage.get("top5_candidate_count"))
        ),
        "strict_blind_ready_slot_count": strict_slot_ready,
        "strict_blind_slot_count": strict_slot_total,
        "strict_blind_evidence_file_present_count": (
            _int(batch_runway.get("file_present_count"))
            if "file_present_count" in batch_runway
            else _int(strict_cycle.get("evidence_file_present_count"))
        ),
        "strict_blind_evidence_file_missing_count": (
            _int(batch_runway.get("file_missing_count"))
            if "file_missing_count" in batch_runway
            else _int(strict_cycle.get("evidence_file_missing_count"))
        ),
        "strict_blind_operator_action_count": (
            _int(batch_runway.get("operator_ready_count")) + _int(batch_runway.get("operator_open_count"))
            if "operator_open_count" in batch_runway
            else _int(strict_cycle.get("operator_action_board_action_count"))
        ),
        "strict_blind_operator_open_value_count": (
            _int(batch_runway.get("operator_open_count"))
            if "operator_open_count" in batch_runway
            else _int(strict_cycle.get("operator_action_board_open_value_count"))
        ),
        "strict_blind_batch_closure_runway_status": _text(batch_runway.get("batch_closure_runway_status")),
        "strict_blind_batch_source_gate_blocked_count": _int(batch_runway.get("source_gate_blocked_count")),
        "strict_blind_batch_evidence_file_blocked_count": _int(batch_runway.get("evidence_file_blocked_count")),
        "strict_blind_batch_operator_value_blocked_count": _int(batch_runway.get("operator_value_blocked_count")),
        "strict_blind_batch_intake_preflight_blocked_count": _int(
            batch_runway.get("intake_preflight_blocked_count")
        ),
        "metric_surface_ready_row_count": metric_ready,
        "metric_surface_row_count": metric_total,
        "competitive_readiness_status": _text(competitive_readiness.get("readiness_gate_status")),
        "competitive_readiness_pass_count": readiness_ready,
        "competitive_readiness_gate_count": readiness_total,
        "target_identity_clearance_status": _text(clearance_cycle.get("clearance_cycle_status")),
        "target_identity_clearance_ready_stage_count": clearance_ready,
        "target_identity_clearance_stage_count": clearance_total,
        "first_blocked_stage_id": _text(first_blocked.get("stage_id")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "first_artifact": _text(first_blocked.get("artifact")),
        "input_blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Critical Path Board",
        "",
        "This board separates completed local review surfaces from the fail-closed competitive-proof gates.",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['critical_path_status']}`",
        f"- stages ready/blocked/total: `{summary['stage_ready_count']}/{summary['stage_blocked_count']}/{summary['stage_count']}`",
        f"- 3D objects ready/total: `{summary['three_d_object_ready_count']}/{summary['three_d_object_count']}`",
        f"- external review-only model-selection targets ready/total: `{summary['external_model_selection_ready_target_count']}/{summary['external_model_selection_target_count']}`",
        f"- external review-only model1/top5 picks: `{summary['external_model_selection_model1_count']}/{summary['external_model_selection_top5_count']}`",
        f"- strict-blind slots ready/total: `{summary['strict_blind_ready_slot_count']}/{summary['strict_blind_slot_count']}`",
        f"- strict-blind evidence present/missing: `{summary['strict_blind_evidence_file_present_count']}/{summary['strict_blind_evidence_file_missing_count']}`",
        f"- strict-blind operator actions/open-values: `{summary['strict_blind_operator_action_count']}/{summary['strict_blind_operator_open_value_count']}`",
        f"- strict-blind batch closure runway: `{summary['strict_blind_batch_closure_runway_status'] or '-'}` blocked source/evidence/operator/intake `{summary['strict_blind_batch_source_gate_blocked_count']}/{summary['strict_blind_batch_evidence_file_blocked_count']}/{summary['strict_blind_batch_operator_value_blocked_count']}/{summary['strict_blind_batch_intake_preflight_blocked_count']}`",
        f"- metric surface rows ready/total: `{summary['metric_surface_ready_row_count']}/{summary['metric_surface_row_count']}`",
        f"- competitive readiness: `{summary['competitive_readiness_status'] or '-'}` pass/total `{summary['competitive_readiness_pass_count']}/{summary['competitive_readiness_gate_count']}`",
        f"- target identity clearance: `{summary['target_identity_clearance_status'] or '-'}` stages `{summary['target_identity_clearance_ready_stage_count']}/{summary['target_identity_clearance_stage_count']}`",
        f"- first blocked stage: `{summary['first_blocked_stage_id'] or '-'}` blocker `{summary['first_blocker'] or '-'}`",
        f"- first next action: {summary['first_next_action'] or '-'}",
        f"- first artifact: `{summary['first_artifact'] or '-'}`",
        "",
        "## Stage Rows",
        "",
        "| stage | status | ready | blocked | total | proof boundary | first blocker | next action | artifact |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{stage_id}` | `{stage_status}` | {ready_count} | {blocked_count} | {total_count} | {proof_boundary} | `{first_blocker}` | {next_action} | `{artifact}` |".format(
                **row
            )
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protein-object-library-completion-audit-json",
        default=DEFAULT_PROTEIN_OBJECT_LIBRARY_COMPLETION_AUDIT_JSON,
    )
    parser.add_argument(
        "--massivefold-rna-model-selection-coverage-json",
        default=DEFAULT_MASSIVEFOLD_RNA_MODEL_SELECTION_COVERAGE_JSON,
    )
    parser.add_argument(
        "--protein-complex-massivefold-model-selection-coverage-json",
        default=DEFAULT_PROTEIN_COMPLEX_MASSIVEFOLD_MODEL_SELECTION_COVERAGE_JSON,
    )
    parser.add_argument(
        "--win-tier-metric-surface-contract-json",
        default=DEFAULT_WIN_TIER_METRIC_SURFACE_CONTRACT_JSON,
    )
    parser.add_argument(
        "--strict-blind-batch-closure-runway-json",
        default=DEFAULT_STRICT_BLIND_BATCH_CLOSURE_RUNWAY_JSON,
    )
    parser.add_argument(
        "--strict-blind-replacement-cycle-json",
        default=DEFAULT_STRICT_BLIND_REPLACEMENT_CYCLE_JSON,
    )
    parser.add_argument(
        "--strict-blind-first-slot-kit-json",
        default=DEFAULT_STRICT_BLIND_FIRST_SLOT_KIT_JSON,
    )
    parser.add_argument("--competitive-readiness-gate-json", default=DEFAULT_COMPETITIVE_READINESS_GATE_JSON)
    parser.add_argument(
        "--competitive-target-identity-clearance-cycle-json",
        default=DEFAULT_COMPETITIVE_TARGET_IDENTITY_CLEARANCE_CYCLE_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
