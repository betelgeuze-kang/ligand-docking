#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DROPZONES_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_OPERATOR_VALUE_GATE.md"

TRUE_FIELDS = {"target_identity_non_current_historical", "prediction_generated_before_native_release"}
FALSE_FIELDS = {
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
}
DATE_FIELDS = {"prediction_created_at", "native_release_date"}
CLEAR_VALUES = {"clear", "cleared", "approved", "operator_cleared", "ready", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y", "confirmed", "clear", "cleared"}
FALSE_VALUES = {"0", "false", "no", "n", "none", "not_used", "confirmed_false"}

OPERATOR_VALUE_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "field_name",
    "required_policy",
    "operator_value",
    "evidence_ref",
    "operator_clearance",
    "operator_id",
    "notes",
]
ROW_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "field_name",
    "required_policy",
    "operator_value",
    "evidence_ref",
    "operator_clearance",
    "destination_intake_csv",
    "operator_values_csv",
    "gate_status",
    "apply_mode",
    "applied",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement operator-value gate only. It creates per-slot operator value templates "
    "and can optionally copy cleared operator values into replacement_candidate_intake.csv. It does not create "
    "evidence, approve no-leak provenance, choose replacement targets, fetch structures, compute CASP metrics, "
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    if not _text(path_like):
        return [], [], ["csv_path_missing"]
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    if not path.is_file():
        return [], [], [f"{path.name}_not_file"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if _is_placeholder(text):
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _required_policy(field_name: str) -> str:
    if field_name in TRUE_FIELDS:
        return "operator_confirmed_true"
    if field_name in FALSE_FIELDS:
        return "operator_confirmed_false"
    if field_name in DATE_FIELDS:
        return "authoritative_iso_date"
    if field_name == "operator_clearance":
        return "operator_cleared"
    return "operator_supplied_non_placeholder"


def _patch_rows(dropzone_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dropzone in dropzone_rows:
        patch_csv = _text(dropzone.get("patch_preview_csv"))
        patch_rows, _, blockers = _read_csv(patch_csv)
        if blockers:
            rows.append(
                {
                    "queue_rank": _text(dropzone.get("queue_rank")),
                    "required_benchmark_id": _text(dropzone.get("required_benchmark_id")),
                    "field_name": "",
                    "field_kind": "",
                    "destination_intake_csv": "",
                    "patch_blockers": ",".join(blockers),
                }
            )
            continue
        rows.extend([row for row in patch_rows if _text(row.get("field_kind")) == "operator_value"])
    return rows


def _template_path(patch_row: dict[str, str]) -> Path:
    intake_csv = _text(patch_row.get("destination_intake_csv"))
    if intake_csv:
        return _resolve(intake_csv).parent / "replacement_operator_values.csv"
    return ROOT / "casp17" / "historical_seed_strict_blind_replacement_operator_value_gate" / "missing.csv"


def _template_rows_for_patch_group(patch_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for patch in patch_rows:
        field_name = _text(patch.get("field_name"))
        rows.append(
            {
                "queue_rank": _int(patch.get("queue_rank")),
                "required_benchmark_id": _text(patch.get("required_benchmark_id")),
                "field_name": field_name,
                "required_policy": _required_policy(field_name),
                "operator_value": _placeholder_for(field_name),
                "evidence_ref": "REQUIRED_OPERATOR_EVIDENCE_REF",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator_id": "REQUIRED_OPERATOR_ID",
                "notes": "Fill only after strict-blind evidence review; placeholders block import.",
            }
        )
    return rows


def _placeholder_for(field_name: str) -> str:
    if field_name in TRUE_FIELDS:
        return "REQUIRED_TRUE_CONFIRMATION"
    if field_name in FALSE_FIELDS:
        return "REQUIRED_FALSE_CONFIRMATION"
    if field_name in DATE_FIELDS:
        return "YYYY-MM-DD"
    if field_name == "operator_clearance":
        return "REQUIRED_OPERATOR_CLEARANCE"
    return f"REQUIRED_{field_name.upper()}"


def _ensure_operator_template(path: Path, patch_rows: list[dict[str, str]]) -> str:
    if path.exists():
        return "preserved"
    _write_csv(path, _template_rows_for_patch_group(patch_rows), OPERATOR_VALUE_COLUMNS)
    return "created"


def _group_patch_rows(patch_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in patch_rows:
        key = _text(row.get("destination_intake_csv")) or f"missing:{_text(row.get('required_benchmark_id'))}"
        grouped.setdefault(key, []).append(row)
    return grouped


def _operator_rows_by_field(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    rows, _, blockers = _read_csv(path)
    return {row.get("field_name", ""): row for row in rows}, blockers


def _value_blockers(field_name: str, operator_row: dict[str, str]) -> list[str]:
    value = _text(operator_row.get("operator_value"))
    evidence_ref = _text(operator_row.get("evidence_ref"))
    clearance = _text(operator_row.get("operator_clearance")).lower()
    blockers: list[str] = []
    if _is_placeholder(value):
        blockers.append("operator_value_required")
    if _is_placeholder(evidence_ref):
        blockers.append("evidence_ref_required")
    elif evidence_ref.lower().startswith(("http://", "https://")):
        blockers.append("evidence_ref_must_be_local_or_repository_ref")
    if clearance not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    lower = value.lower()
    if field_name in TRUE_FIELDS and not _is_placeholder(value) and lower not in TRUE_VALUES:
        blockers.append(f"{field_name}_must_be_true")
    if field_name in FALSE_FIELDS and not _is_placeholder(value) and lower not in FALSE_VALUES:
        blockers.append(f"{field_name}_must_be_false")
    if field_name in DATE_FIELDS and not _is_placeholder(value) and _date_or_none(value) is None:
        blockers.append(f"{field_name}_requires_iso_date")
    if field_name == "operator_clearance" and not _is_placeholder(value) and lower not in CLEAR_VALUES:
        blockers.append("operator_clearance_value_not_clear")
    return blockers


def _chronology_blockers(rows_by_field: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    prediction_date = _date_or_none(rows_by_field.get("prediction_created_at", {}).get("operator_value"))
    native_date = _date_or_none(rows_by_field.get("native_release_date", {}).get("operator_value"))
    if not prediction_date or not native_date or prediction_date < native_date:
        return {}
    return {
        "prediction_created_at": ["prediction_created_at_not_before_native_release_date"],
        "native_release_date": ["native_release_date_not_after_prediction_created_at"],
    }


def _intake_current_value(intake_csv: str, field_name: str) -> tuple[str, list[str]]:
    rows, _, blockers = _read_csv(intake_csv)
    if blockers:
        return "", blockers
    return _text(rows[0].get(field_name)) if rows else "", []


def _apply_operator_value(intake_csv: str, field_name: str, operator_value: str) -> bool:
    rows, fieldnames, blockers = _read_csv(intake_csv)
    if blockers or not rows:
        return False
    if field_name not in fieldnames:
        fieldnames.append(field_name)
    rows[0][field_name] = operator_value
    _write_csv(intake_csv, rows, fieldnames)
    return True


def _gate_row(
    patch_row: dict[str, str],
    operator_row: dict[str, str],
    operator_values_csv: Path,
    extra_blockers: list[str],
    *,
    apply: bool,
) -> dict[str, Any]:
    field_name = _text(patch_row.get("field_name"))
    intake_csv = _text(patch_row.get("destination_intake_csv"))
    current_value, intake_blockers = _intake_current_value(intake_csv, field_name)
    blockers = []
    if not operator_row:
        blockers.append("operator_value_row_missing")
    blockers.extend(_value_blockers(field_name, operator_row))
    blockers.extend(extra_blockers)
    blockers.extend(intake_blockers)
    operator_value = _text(operator_row.get("operator_value"))
    applied = False
    if not blockers:
        if current_value == operator_value:
            status = "already_applied"
        elif _is_placeholder(current_value):
            status = "ready_to_apply"
            if apply:
                applied = _apply_operator_value(intake_csv, field_name, operator_value)
                status = "applied" if applied else "blocked_apply_failed"
        else:
            status = "blocked_conflict"
            blockers.append("intake_field_has_non_placeholder_value")
    else:
        status = _blocked_status(blockers)
    return {
        "queue_rank": _int(patch_row.get("queue_rank")),
        "required_benchmark_id": _text(patch_row.get("required_benchmark_id")),
        "field_name": field_name,
        "required_policy": _required_policy(field_name),
        "operator_value": operator_value,
        "evidence_ref": _text(operator_row.get("evidence_ref")),
        "operator_clearance": _text(operator_row.get("operator_clearance")),
        "destination_intake_csv": intake_csv,
        "operator_values_csv": _artifact(operator_values_csv),
        "gate_status": status,
        "apply_mode": "apply" if apply else "dry_run",
        "applied": "true" if applied else "false",
        "blockers": ",".join(blockers),
        "next_action": _next_action(status, field_name),
    }


def _blocked_status(blockers: list[str]) -> str:
    if any("requires_iso_date" in blocker or "not_before" in blocker for blocker in blockers):
        return "blocked_invalid_operator_value"
    if "operator_value_required" in blockers:
        return "awaiting_operator_value"
    if "evidence_ref_required" in blockers:
        return "awaiting_evidence_ref"
    if "operator_clearance_required" in blockers:
        return "awaiting_operator_clearance"
    return "blocked_operator_value_review"


def _next_action(status: str, field_name: str) -> str:
    if status == "ready_to_apply":
        return f"run this gate with --apply to copy {field_name} into replacement_candidate_intake.csv"
    if status == "applied":
        return "rerun strict-blind replacement intake preflight"
    if status == "already_applied":
        return "rerun strict-blind replacement intake preflight"
    if status == "awaiting_operator_value":
        return f"fill operator_value for {field_name} in replacement_operator_values.csv"
    if status == "awaiting_evidence_ref":
        return f"attach evidence_ref for {field_name} in replacement_operator_values.csv"
    if status == "awaiting_operator_clearance":
        return f"set operator_clearance for {field_name} after review"
    if status == "blocked_conflict":
        return f"review existing intake value for {field_name} before applying"
    return "repair operator value row and rerun this gate"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzones_payload = _read_json(args.dropzones_json)
    dropzones_summary = _summary(dropzones_payload)
    dropzone_rows = _rows(dropzones_payload)
    input_blockers: list[str] = []
    if not _resolve(args.dropzones_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_dropzones_json_missing")
    patch_rows = _patch_rows(dropzone_rows)
    rows: list[dict[str, Any]] = []
    template_statuses: list[str] = []
    for _, group in _group_patch_rows(patch_rows).items():
        if not group or _text(group[0].get("patch_blockers")):
            continue
        operator_values_csv = _template_path(group[0])
        template_statuses.append(_ensure_operator_template(operator_values_csv, group))
        operator_by_field, template_blockers = _operator_rows_by_field(operator_values_csv)
        chronology_blockers = _chronology_blockers(operator_by_field)
        for patch_row in group:
            field_name = _text(patch_row.get("field_name"))
            rows.append(
                _gate_row(
                    patch_row,
                    operator_by_field.get(field_name, {}),
                    operator_values_csv,
                    template_blockers + chronology_blockers.get(field_name, []),
                    apply=args.apply,
                )
            )
    summary = _build_summary(args, rows, template_statuses, input_blockers, dropzones_summary)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    template_statuses: list[str],
    input_blockers: list[str],
    dropzones_summary: dict[str, Any],
) -> dict[str, Any]:
    first_open = next((row for row in rows if row["gate_status"] not in {"already_applied", "applied"}), {})
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_operator_value_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_operator_value_gate_status": _status(rows, input_blockers, apply=args.apply),
        "apply_mode": "apply" if args.apply else "dry_run",
        "dropzones_json": _artifact(args.dropzones_json),
        "dropzone_status": _text(
            dropzones_summary.get("strict_blind_replacement_evidence_dropzone_status")
        ),
        "template_count": len(template_statuses),
        "created_template_count": template_statuses.count("created"),
        "preserved_template_count": template_statuses.count("preserved"),
        "action_count": len(rows),
        "ready_for_apply_count": sum(1 for row in rows if row["gate_status"] == "ready_to_apply"),
        "applied_count": sum(1 for row in rows if row["gate_status"] == "applied"),
        "already_applied_count": sum(1 for row in rows if row["gate_status"] == "already_applied"),
        "awaiting_operator_value_count": sum(1 for row in rows if row["gate_status"] == "awaiting_operator_value"),
        "awaiting_evidence_ref_count": sum(1 for row in rows if row["gate_status"] == "awaiting_evidence_ref"),
        "awaiting_operator_clearance_count": sum(
            1 for row in rows if row["gate_status"] == "awaiting_operator_clearance"
        ),
        "blocked_count": sum(1 for row in rows if str(row["gate_status"]).startswith("blocked")),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_open_field": _text(first_open.get("field_name")),
        "first_open_status": _text(first_open.get("gate_status")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind operator values",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _status(rows: list[dict[str, Any]], input_blockers: list[str], *, apply: bool) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_missing_operator_value_rows"
    if apply and any(row["gate_status"] == "applied" for row in rows):
        return "applied_operator_values_pending_intake_preflight"
    if any(str(row["gate_status"]).startswith("blocked") for row in rows):
        return "blocked_operator_value_review"
    if any(row["gate_status"] == "ready_to_apply" for row in rows):
        return "ready_for_operator_value_apply"
    if any(str(row["gate_status"]).startswith("awaiting") for row in rows):
        return "awaiting_operator_values"
    return "operator_values_import_gate_clear"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Operator Value Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_operator_value_gate_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- templates created/preserved/total: `{summary['created_template_count']}/{summary['preserved_template_count']}/{summary['template_count']}`",
        f"- actions ready/applied/already/total: `{summary['ready_for_apply_count']}/{summary['applied_count']}/{summary['already_applied_count']}/{summary['action_count']}`",
        f"- awaiting value/evidence/clearance: `{summary['awaiting_operator_value_count']}/{summary['awaiting_evidence_ref_count']}/{summary['awaiting_operator_clearance_count']}`",
        f"- blocked: `{summary['blocked_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_field'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Operator Value Rows",
        "",
        "| rank | benchmark | field | status | apply | next action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['field_name']}` | "
            f"`{row['gate_status']}` | `{row['applied']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_operator_value_rows` | false | provide dropzone patch previews |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind replacement operator value gate.")
    parser.add_argument("--dropzones-json", default=DEFAULT_DROPZONES_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
