#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_REPAIR_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_current.json"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board_current.csv"
)
DEFAULT_OUT_MD = (
    "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_REPAIR_FEASIBILITY_BOARD.md"
)

ROW_COLUMNS = [
    "action_id",
    "target_id",
    "repair_class",
    "blocker",
    "action_status",
    "feasibility_status",
    "feasibility_reason",
    "prediction_created_at",
    "native_release_date",
    "current_prediction_before_native",
    "next_route",
    "required_operator_input",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot repair feasibility board only. It classifies whether current local candidate repair "
    "actions can close strict-blind evidence with existing artifacts or require external pre-native prediction "
    "artifacts/candidate replacement. It does not create evidence, approve candidates, compute metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _date(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _prediction_before_native(candidate: dict[str, Any]) -> str:
    prediction_date = _date(candidate.get("prediction_created_at"))
    native_date = _date(candidate.get("native_release_date"))
    if not prediction_date or not native_date:
        return ""
    return str(prediction_date < native_date)


def _classify_action(repair: dict[str, Any], candidate: dict[str, Any]) -> dict[str, str]:
    prediction_created_at = _text(candidate.get("prediction_created_at"))
    native_release_date = _text(candidate.get("native_release_date"))
    prediction_date = _date(prediction_created_at)
    native_date = _date(native_release_date)
    current_before_native = _prediction_before_native(candidate)
    blocker = _text(repair.get("blocker"))
    repair_class = _text(repair.get("repair_class"))

    if blocker == "prediction_not_before_native":
        if prediction_date and native_date and prediction_date >= native_date:
            return {
                "feasibility_status": "not_repairable_with_current_prediction",
                "feasibility_reason": "current prediction artifact is dated on or after authoritative native release",
                "next_route": "source_external_pre_native_prediction_or_replace_candidate",
                "required_operator_input": "pre-native prediction artifact with independent timestamp and no-leak provenance",
            }
        if prediction_date and native_date and prediction_date < native_date:
            return {
                "feasibility_status": "repairable_current_prediction_pre_native",
                "feasibility_reason": "current prediction date is before authoritative native release",
                "next_route": "proceed_to_no_leak_ablation_calibration_repairs",
                "required_operator_input": "operator confirmation of chronology evidence",
            }
        return {
            "feasibility_status": "needs_chronology_date_evidence",
            "feasibility_reason": "prediction/native dates are missing or invalid",
            "next_route": "fill_prediction_created_at_and_native_release_date",
            "required_operator_input": "authoritative prediction timestamp and native release date",
        }

    if blocker == "strict_blind_not_eligible":
        if prediction_date and native_date and prediction_date >= native_date:
            return {
                "feasibility_status": "blocked_by_post_native_prediction",
                "feasibility_reason": "eligibility cannot clear while current prediction is post-native",
                "next_route": "source_external_pre_native_prediction_or_replace_candidate",
                "required_operator_input": "clear chronology with pre-native prediction evidence before promotion",
            }
        return {
            "feasibility_status": "blocked_by_primary_repairs",
            "feasibility_reason": "eligibility waits for chronology, no-leak, ablation, and calibration repairs",
            "next_route": "complete_primary_repair_actions",
            "required_operator_input": "primary repair evidence bundle",
        }

    if repair_class in {"prediction_file", "native_file", "native_authority"}:
        return {
            "feasibility_status": "repairable_operator_source_required",
            "feasibility_reason": "missing source material can be supplied by operator if authoritative",
            "next_route": "attach_authoritative_source_file_or_reference",
            "required_operator_input": _text(repair.get("next_action")) or "attach source material",
        }

    if repair_class in {"no_leak", "ablation", "calibration"}:
        return {
            "feasibility_status": "repairable_operator_evidence_required",
            "feasibility_reason": "operator evidence is required after chronology/source gates",
            "next_route": "complete_operator_evidence_after_chronology",
            "required_operator_input": _text(repair.get("next_action")) or "complete operator evidence",
        }

    return {
        "feasibility_status": "needs_manual_review",
        "feasibility_reason": "repair class is not covered by feasibility policy",
        "next_route": "inspect_repair_policy",
        "required_operator_input": "manual feasibility review",
    }


def _build_rows(repair_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    candidates = {_text(row.get("target_id")): row for row in candidate_rows}
    rows: list[dict[str, str]] = []
    for repair in repair_rows:
        candidate = candidates.get(_text(repair.get("target_id")), {})
        classification = _classify_action(repair, candidate)
        rows.append(
            {
                "action_id": _text(repair.get("action_id")),
                "target_id": _text(repair.get("target_id")),
                "repair_class": _text(repair.get("repair_class")),
                "blocker": _text(repair.get("blocker")),
                "action_status": _text(repair.get("action_status")),
                "prediction_created_at": _text(candidate.get("prediction_created_at")),
                "native_release_date": _text(candidate.get("native_release_date")),
                "current_prediction_before_native": _prediction_before_native(candidate),
                **classification,
            }
        )
    return rows


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, str]],
    candidate_payload: dict[str, Any],
    repair_payload: dict[str, Any],
    input_blockers: list[str],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["feasibility_status"]] = status_counts.get(row["feasibility_status"], 0) + 1
    external_targets = {
        row["target_id"]
        for row in rows
        if row["next_route"] == "source_external_pre_native_prediction_or_replace_candidate"
    }
    first_external = next(
        (
            row
            for row in rows
            if row["next_route"] == "source_external_pre_native_prediction_or_replace_candidate"
        ),
        {},
    )
    first_actionable = next(
        (
            row
            for row in rows
            if row["feasibility_status"]
            in {"repairable_operator_source_required", "repairable_operator_evidence_required", "needs_chronology_date_evidence"}
        ),
        {},
    )
    return {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_first_slot_repair_feasibility_board_status": _overall_status(rows, input_blockers),
        "candidate_board_json": _artifact(args.candidate_board_json),
        "repair_board_json": _artifact(args.repair_board_json),
        "candidate_board_status": _text(
            _summary(candidate_payload).get("strict_blind_replacement_first_slot_local_candidate_board_status")
        ),
        "repair_board_status": _text(
            _summary(repair_payload).get("strict_blind_replacement_first_slot_candidate_repair_board_status")
        ),
        "required_benchmark_id": _text(_summary(candidate_payload).get("required_benchmark_id")),
        "candidate_count": _summary(candidate_payload).get("candidate_count", 0),
        "action_count": len(rows),
        "not_repairable_with_current_prediction_count": status_counts.get("not_repairable_with_current_prediction", 0),
        "blocked_by_post_native_prediction_count": status_counts.get("blocked_by_post_native_prediction", 0),
        "external_pre_native_artifact_required_action_count": sum(
            1 for row in rows if row["next_route"] == "source_external_pre_native_prediction_or_replace_candidate"
        ),
        "external_pre_native_artifact_required_target_count": len(external_targets),
        "repairable_operator_source_required_count": status_counts.get("repairable_operator_source_required", 0),
        "repairable_operator_evidence_required_count": status_counts.get("repairable_operator_evidence_required", 0),
        "needs_chronology_date_evidence_count": status_counts.get("needs_chronology_date_evidence", 0),
        "blocked_by_primary_repairs_count": status_counts.get("blocked_by_primary_repairs", 0),
        "repairable_current_prediction_pre_native_count": status_counts.get("repairable_current_prediction_pre_native", 0),
        "first_external_action_id": _text(first_external.get("action_id")),
        "first_external_target_id": _text(first_external.get("target_id")),
        "first_external_blocker": _text(first_external.get("blocker")),
        "first_external_next_route": _text(first_external.get("next_route")),
        "first_actionable_action_id": _text(first_actionable.get("action_id")),
        "first_actionable_target_id": _text(first_actionable.get("target_id")),
        "first_actionable_status": _text(first_actionable.get("feasibility_status")),
        "first_actionable_required_input": _text(first_actionable.get("required_operator_input")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _overall_status(rows: list[dict[str, str]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if any(row["next_route"] == "source_external_pre_native_prediction_or_replace_candidate" for row in rows):
        return "first_slot_current_local_candidate_source_required"
    if any(row["feasibility_status"].startswith("repairable") for row in rows):
        return "first_slot_repair_inputs_required"
    return "first_slot_repair_feasibility_clear"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_payload = _read_json(args.candidate_board_json)
    repair_payload = _read_json(args.repair_board_json)
    input_blockers = []
    if not _resolve(args.candidate_board_json).exists():
        input_blockers.append("first_slot_local_candidate_board_json_missing")
    if not _resolve(args.repair_board_json).exists():
        input_blockers.append("first_slot_candidate_repair_board_json_missing")
    rows = _build_rows(_rows(repair_payload), _rows(candidate_payload))
    summary = _build_summary(args, rows, candidate_payload, repair_payload, input_blockers)
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement First Slot Repair Feasibility Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_first_slot_repair_feasibility_board_status']}`",
        f"- required benchmark: `{summary['required_benchmark_id'] or '-'}`",
        f"- actions total: `{summary['action_count']}`",
        f"- current-prediction post-native actions/eligibility: `{summary['not_repairable_with_current_prediction_count']}/{summary['blocked_by_post_native_prediction_count']}`",
        f"- external pre-native artifact required actions/targets: `{summary['external_pre_native_artifact_required_action_count']}/{summary['external_pre_native_artifact_required_target_count']}`",
        f"- repairable source/evidence/date actions: `{summary['repairable_operator_source_required_count']}/{summary['repairable_operator_evidence_required_count']}/{summary['needs_chronology_date_evidence_count']}`",
        f"- primary-repair blocked/current-pre-native actions: `{summary['blocked_by_primary_repairs_count']}/{summary['repairable_current_prediction_pre_native_count']}`",
        f"- first external-route action: `{summary['first_external_action_id'] or '-'}` `{summary['first_external_target_id'] or '-'}` `{summary['first_external_blocker'] or '-'}`",
        f"- first actionable input: `{summary['first_actionable_action_id'] or '-'}` `{summary['first_actionable_target_id'] or '-'}` `{summary['first_actionable_status'] or '-'}`",
        "",
        "## Feasibility Rows",
        "",
        "| action | target | blocker | status | prediction | native | route | required input |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:120]:
        lines.append(
            f"| `{row['action_id']}` | `{row['target_id']}` | `{row['blocker']}` | "
            f"`{row['feasibility_status']}` | `{row['prediction_created_at'] or '-'}` | "
            f"`{row['native_release_date'] or '-'}` | `{row['next_route']}` | {row['required_operator_input']} |"
        )
    if len(payload["rows"]) > 120:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | `{len(payload['rows']) - 120} more rows in CSV` |")
    if not payload["rows"]:
        lines.append("| - | - | - | `clear` | - | - | - | rerun repair board |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot repair feasibility board.")
    parser.add_argument("--candidate-board-json", default=DEFAULT_CANDIDATE_BOARD_JSON)
    parser.add_argument("--repair-board-json", default=DEFAULT_REPAIR_BOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
