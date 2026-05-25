#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_IDENTITY_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_IDENTITY_KIT_CSV = "casp17/casp17_competitive_floor_identity_unlock_kit_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_value_entry_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_value_entry_plan_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_VALUE_ENTRY_PLAN.md"

FILE_CLASSES = {"core_file", "ablation_file"}
CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
PLAN_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "value_rank",
    "evidence_class",
    "template_column",
    "identity_status",
    "proposed_target_id",
    "proposed_value",
    "recommended_value",
    "expected_value_rule",
    "evidence_ref",
    "operator_clearance",
    "value_entry_status",
    "blocker",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor value entry plan only. It organizes target identity, no-leak provenance, and "
    "calibration value actions so operators can fill cleared historical benchmark evidence consistently. It does "
    "not choose historical targets, clear no-leak provenance, fetch native structures, score native accuracy, run "
    "predictors, mutate row_fill.csv, update ledgers, or submit to CASP."
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
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_ok(value: Any) -> bool:
    text = _text(value)
    if _contains_placeholder(text):
        return False
    try:
        dt.date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


def _numeric_ok(value: Any) -> bool:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed)


def _rank_ok(value: Any) -> bool:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return False
    return 1 <= parsed <= 5


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = PLAN_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _identity_rows(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    payload = _read_json(args.identity_kit_json)
    rows = payload.get("rows")
    if isinstance(rows, list):
        return {_text(row.get("dropzone_id")): row for row in rows if isinstance(row, dict) and _text(row.get("dropzone_id"))}
    csv_rows, _fieldnames, blockers = _read_csv(args.identity_kit_csv)
    if blockers:
        return {}
    return {_text(row.get("dropzone_id")): row for row in csv_rows if _text(row.get("dropzone_id"))}


def _value_rows(path_like: str | Path) -> list[dict[str, str]]:
    rows, _fieldnames, blockers = _read_csv(path_like)
    if blockers:
        return []
    return [
        row
        for row in rows
        if _text(row.get("import_kind")) == "value" and _text(row.get("evidence_class")) not in FILE_CLASSES
    ]


def _identity_status(identity: dict[str, Any]) -> tuple[str, str, str]:
    declared = _text(identity.get("identity_status"))
    target_id = _text(identity.get("proposed_target_id")).upper()
    benchmark_id = _text(identity.get("proposed_benchmark_id"))
    if declared:
        return declared, benchmark_id, target_id
    clearance = _text(identity.get("operator_clearance")).lower()
    evidence_ref = _text(identity.get("evidence_ref"))
    if _contains_placeholder(target_id) or _contains_placeholder(benchmark_id) or not evidence_ref or clearance not in CLEAR_VALUES:
        return "awaiting_identity", benchmark_id, target_id
    return "ready_for_import", benchmark_id, target_id


def _recommended_value(row: dict[str, str], identity: dict[str, Any]) -> str:
    column = _text(row.get("template_column"))
    evidence_class = _text(row.get("evidence_class"))
    if evidence_class == "target_identity" and column == "benchmark_id":
        return _text(identity.get("proposed_benchmark_id"))
    if evidence_class == "target_identity" and column == "target_id":
        return _text(identity.get("proposed_target_id")).upper()
    if column in {"leakage_clearance", "operator_clearance"}:
        return "no_leak"
    if column == "prediction_generated_before_native_release":
        return "true"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "false"
    return ""


def _value_blocker(column: str, proposed: str) -> str:
    lower = proposed.lower()
    if column in {"benchmark_id", "target_id", "prediction_method"}:
        return "" if not _contains_placeholder(proposed) else f"{column}_required"
    if column in {"leakage_clearance", "operator_clearance"}:
        return "" if lower in CLEAR_VALUES else f"{column}_requires_no_leak_clearance"
    if column in {"prediction_created_at", "native_release_date"}:
        return "" if _date_ok(proposed) else f"{column}_requires_iso_date"
    if column == "prediction_generated_before_native_release":
        return "" if lower in TRUE_VALUES else "prediction_generated_before_native_release_must_be_true"
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return "" if lower in FALSE_VALUES else f"{column}_must_be_false"
    if column in {"selected_model_rank", "best_model_rank"}:
        return "" if _rank_ok(proposed) else f"{column}_requires_rank_1_to_5"
    if column in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return "" if _numeric_ok(proposed) else f"{column}_requires_numeric_value"
    return "" if not _contains_placeholder(proposed) else f"{column}_required"


def _status_for_value(row: dict[str, str], identity_status: str, recommended: str) -> tuple[str, str]:
    proposed = _text(row.get("proposed_value"))
    evidence_class = _text(row.get("evidence_class"))
    column = _text(row.get("template_column"))
    if identity_status == "blocked_identity":
        return "blocked_identity", "identity_row_blocked"
    if identity_status != "ready_for_import":
        return "waiting_on_identity", "target_identity_required"
    if evidence_class == "target_identity" and _contains_placeholder(proposed) and recommended:
        return "ready_from_identity_kit", ""
    if _contains_placeholder(proposed):
        return "awaiting_value", "proposed_value_required"
    value_blocker = _value_blocker(column, proposed)
    if value_blocker:
        return "blocked_invalid_value", value_blocker
    clearance = _text(row.get("operator_clearance")).lower()
    if clearance not in CLEAR_VALUES:
        return "awaiting_clearance", "operator_clearance_required"
    if not _text(row.get("evidence_ref")):
        return "awaiting_evidence_ref", "evidence_ref_required"
    return "ready_for_import", ""


def _next_action(status: str) -> str:
    if status == "waiting_on_identity":
        return "fill and apply the compact identity unlock kit first"
    if status == "blocked_identity":
        return "fix the identity row blockers before filling downstream values"
    if status == "ready_from_identity_kit":
        return "run the identity unlock round with --apply-identity to stage benchmark_id and target_id values"
    if status == "awaiting_value":
        return "enter proposed_value from cleared local historical evidence"
    if status == "awaiting_clearance":
        return "set operator_clearance to no_leak, cleared, internal_no_leak, or ready_for_row_fill"
    if status == "awaiting_evidence_ref":
        return "add the local evidence_ref that supports this value"
    if status == "blocked_invalid_value":
        return "correct proposed_value to match the expected field rule"
    if status == "ready_for_import":
        return "review this value, then run the evidence round with --apply-import"
    return "review this value action"


def _plan_status(by_status: Counter[str], row_count: int) -> str:
    if not row_count:
        return "ready"
    if by_status["blocked_identity"] or by_status["blocked_invalid_value"]:
        return "blocked"
    if by_status["waiting_on_identity"]:
        return "waiting_on_identity"
    if by_status["ready_from_identity_kit"]:
        return "ready_for_identity_apply"
    if by_status["awaiting_value"] or by_status["awaiting_clearance"] or by_status["awaiting_evidence_ref"]:
        return "awaiting_values"
    if by_status["ready_for_import"] == row_count:
        return "ready_for_import"
    return "awaiting_values"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    identities = _identity_rows(args)
    rows: list[dict[str, Any]] = []
    for value_rank, row in enumerate(_value_rows(args.import_csv), start=1):
        dropzone_id = _text(row.get("dropzone_id"))
        identity = identities.get(dropzone_id, {})
        identity_status, _benchmark_id, target_id = _identity_status(identity)
        recommended = _recommended_value(row, identity)
        status, blocker = _status_for_value(row, identity_status, recommended)
        rows.append(
            {
                "dropzone_id": dropzone_id,
                "operator_priority": _int(row.get("operator_priority")),
                "row_rank": _int(row.get("row_rank")),
                "scope": _text(row.get("scope")),
                "value_rank": value_rank,
                "evidence_class": _text(row.get("evidence_class")),
                "template_column": _text(row.get("template_column")),
                "identity_status": identity_status,
                "proposed_target_id": target_id,
                "proposed_value": _text(row.get("proposed_value")),
                "recommended_value": recommended,
                "expected_value_rule": _text(row.get("expected_value_rule")),
                "evidence_ref": _text(row.get("evidence_ref")),
                "operator_clearance": _text(row.get("operator_clearance")),
                "value_entry_status": status,
                "blocker": blocker,
                "next_action": _next_action(status),
            }
        )
    by_status = Counter(str(row["value_entry_status"]) for row in rows)
    by_class = Counter(str(row["evidence_class"]) for row in rows)
    row_ids = {row["dropzone_id"] for row in rows if row["dropzone_id"]}
    first_open = next((row for row in rows if row["value_entry_status"] != "ready_for_import"), rows[0] if rows else {})
    blocked_count = by_status["blocked_identity"] + by_status["blocked_invalid_value"]
    summary = {
        "packet_type": "casp17_competitive_floor_value_entry_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "value_entry_status": _plan_status(by_status, len(rows)),
        "import_csv": _artifact(args.import_csv),
        "identity_kit_json": _artifact(args.identity_kit_json),
        "identity_kit_csv": _artifact(args.identity_kit_csv),
        "row_count": len(row_ids),
        "value_action_count": len(rows),
        "target_identity_action_count": by_class["target_identity"],
        "provenance_action_count": by_class["provenance"],
        "calibration_action_count": by_class["calibration"],
        "waiting_on_identity_count": by_status["waiting_on_identity"],
        "ready_from_identity_kit_count": by_status["ready_from_identity_kit"],
        "awaiting_value_count": by_status["awaiting_value"],
        "awaiting_clearance_count": by_status["awaiting_clearance"],
        "awaiting_evidence_ref_count": by_status["awaiting_evidence_ref"],
        "ready_for_import_count": by_status["ready_for_import"],
        "blocked_value_count": blocked_count,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_column": _text(first_open.get("template_column")),
        "first_open_status": _text(first_open.get("value_entry_status")),
        "first_open_blocker": _text(first_open.get("blocker")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Value Entry Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- value_entry_status: `{summary['value_entry_status']}`",
        f"- rows/value actions: `{summary['row_count']}/{summary['value_action_count']}`",
        f"- target/provenance/calibration actions: `{summary['target_identity_action_count']}/{summary['provenance_action_count']}/{summary['calibration_action_count']}`",
        f"- waiting on identity: `{summary['waiting_on_identity_count']}`",
        f"- ready from identity kit: `{summary['ready_from_identity_kit_count']}`",
        f"- awaiting value/clearance/ref: `{summary['awaiting_value_count']}/{summary['awaiting_clearance_count']}/{summary['awaiting_evidence_ref_count']}`",
        f"- ready/blocked: `{summary['ready_for_import_count']}/{summary['blocked_value_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_column'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Value Actions",
        "",
        "| rank | dropzone | class | column | identity | target | status | proposed | recommended | blocker | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['value_rank']} | `{row['dropzone_id']}` | `{row['evidence_class']}` | "
            f"`{row['template_column']}` | `{row['identity_status']}` | `{row['proposed_target_id'] or '-'}` | "
            f"`{row['value_entry_status']}` | `{row['proposed_value'] or '-'}` | "
            f"`{row['recommended_value'] or '-'}` | `{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | `ready` | - | - | - | no value actions |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=PLAN_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 competitive-floor value entry plan.")
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--identity-kit-json", default=DEFAULT_IDENTITY_KIT_JSON)
    parser.add_argument("--identity-kit-csv", default=DEFAULT_IDENTITY_KIT_CSV)
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
