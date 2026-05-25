#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_INTAKE_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_report_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_OPERATOR_INTAKE.md"

INTAKE_COLUMNS = [
    "target_id",
    "native_source_pdb",
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "notes",
]
REPORT_COLUMNS = [
    "target_id",
    "intake_status",
    "apply_mode",
    "native_source_pdb",
    "native_dropzone_pdb",
    "native_action_status",
    "provenance_template_csv",
    "provenance_action_status",
    "no_leak_evidence_ref",
    "evidence_ref_sha256",
    "blockers",
    "next_action",
]
PROVENANCE_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
    "operator",
    "evidence_ref",
    "notes",
]
CLEAR_VALUES = {"cleared", "no_leak", "ready_for_row_fill", "internal_no_leak", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
URL_PREFIXES = ("http://", "https://")
EVIDENCE_REF_BLOCKED_MARKERS = (
    "clearance_evidence_status: request_template",
    "evidence request template",
    "not a completed no-leak clearance",
)
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor target identity clearance operator intake only. It validates operator-supplied "
    "native PDB paths, no-leak evidence refs, provenance dates, and true/false provenance controls before optional "
    "local workorder patching. It does not fetch native structures, clear no-leak provenance, trust external URLs, "
    "score native accuracy, mutate identity intake files, or submit to CASP."
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


def _read_csv_rows(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _sha256(path_like: str | Path) -> str:
    return hashlib.sha256(_resolve(path_like).read_bytes()).hexdigest()


def _ensure_intake_csv(path_like: str | Path, workorder_rows: list[dict[str, Any]]) -> str:
    path = _resolve(path_like)
    if path.exists():
        return "preserved"
    rows = [
        {
            "target_id": _text(row.get("target_id")).upper(),
            "native_source_pdb": "",
            "no_leak_evidence_ref": "",
            "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
            "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
            "operator": "REQUIRED_OPERATOR_ID",
            "prediction_created_at": "YYYY-MM-DD",
            "native_release_date": "YYYY-MM-DD",
            "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
            "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
            "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
            "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
            "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
            "notes": "Do not mark cleared until native and no-leak provenance are operator-reviewed.",
        }
        for row in workorder_rows
    ]
    _write_csv(path, rows, INTAKE_COLUMNS)
    return "created"


def _pdb_blockers(path_like: str | Path, *, role: str) -> list[str]:
    path_text = _text(path_like)
    if _contains_placeholder(path_text):
        return [f"{role}_pdb_required"]
    path = _resolve(path_text)
    if not path.exists():
        return [f"{role}_pdb_missing"]
    if not path.is_file():
        return [f"{role}_pdb_not_file"]
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [f"{role}_pdb_unreadable"]
    atom_lines = [line for line in lines if line.startswith(("ATOM", "HETATM"))]
    protein_atom_lines = [line for line in lines if line.startswith("ATOM")]
    if not atom_lines:
        return [f"{role}_pdb_has_no_atom_records"]
    if not protein_atom_lines:
        return [f"{role}_pdb_has_no_protein_atom_records"]
    for line in atom_lines:
        try:
            float(line[30:38])
            float(line[38:46])
            float(line[46:54])
        except ValueError:
            return [f"{role}_pdb_coordinates_invalid"]
    return []


def _native_prediction_identity_blockers(native_path_like: str | Path, prediction_path_like: str | Path) -> list[str]:
    native = _resolve(native_path_like)
    prediction_text = _text(prediction_path_like)
    if not prediction_text:
        return ["prediction_pdb_required_for_identity_check"]
    prediction = _resolve(prediction_text)
    if not prediction.exists():
        return ["prediction_pdb_missing_for_identity_check"]
    try:
        if native.samefile(prediction):
            return ["native_pdb_same_path_as_prediction_pdb"]
        if _sha256(native) == _sha256(prediction):
            return ["native_pdb_identical_to_prediction_pdb"]
    except OSError:
        return ["native_prediction_identity_unreadable"]
    return []


def _evidence_blockers(path_like: str | Path, *, target_id: str) -> tuple[list[str], str]:
    ref = _text(path_like)
    if _contains_placeholder(ref):
        return ["no_leak_evidence_ref_required"], ""
    if ref.lower().startswith(URL_PREFIXES):
        return ["no_leak_evidence_ref_must_be_local_file"], ""
    path = _resolve(ref)
    if not path.exists():
        return ["no_leak_evidence_ref_missing"], ""
    if not path.is_file():
        return ["no_leak_evidence_ref_not_file"], ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["no_leak_evidence_ref_unreadable"], ""
    blockers: list[str] = []
    if not content.strip():
        blockers.append("no_leak_evidence_ref_empty")
    lowered = content.lower()
    if target_id.lower() not in lowered:
        blockers.append("no_leak_evidence_target_id_missing")
    if not any(marker in lowered for marker in ["no-leak", "no_leak", "no leak"]):
        blockers.append("no_leak_evidence_marker_missing")
    if any(marker in lowered for marker in EVIDENCE_REF_BLOCKED_MARKERS):
        blockers.append("no_leak_evidence_is_request_template")
    return blockers, _sha256(path) if not blockers else ""


def _provenance_value_blockers(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    for column in ["operator"]:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"{column}_required")
    if _text(row.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    prediction_date = _date_or_none(row.get("prediction_created_at"))
    native_date = _date_or_none(row.get("native_release_date"))
    if prediction_date is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_date is not None and native_date is not None and prediction_date >= native_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    return blockers


def _read_provenance_template(path_like: str | Path) -> tuple[dict[str, str], list[str]]:
    rows, fieldnames = _read_csv_rows(path_like)
    if not rows:
        return {}, fieldnames
    return rows[0], fieldnames


def _write_provenance_template(path_like: str | Path, row: dict[str, str], fieldnames: list[str]) -> None:
    fields = fieldnames or PROVENANCE_COLUMNS
    _write_csv(path_like, [row], fields)


def _intake_by_target(path_like: str | Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    rows, fieldnames = _read_csv_rows(path_like)
    by_target: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        target_id = _text(row.get("target_id")).upper()
        if not target_id:
            continue
        if target_id in by_target:
            duplicates.append(target_id)
        by_target[target_id] = row
    missing = [column for column in INTAKE_COLUMNS if column not in fieldnames]
    blockers = []
    if missing:
        blockers.append("intake_required_columns_missing:" + ",".join(missing))
    if duplicates:
        blockers.append("intake_duplicate_targets:" + ",".join(sorted(set(duplicates))))
    return by_target, blockers


def _apply_row(workorder_row: dict[str, Any], intake_row: dict[str, str], *, apply: bool) -> dict[str, Any]:
    target_id = _text(workorder_row.get("target_id")).upper()
    native_source = _text(intake_row.get("native_source_pdb"))
    native_dropzone = _text(workorder_row.get("native_dropzone_pdb"))
    evidence_ref = _text(intake_row.get("no_leak_evidence_ref"))
    provenance_template = _text(workorder_row.get("provenance_template_csv"))
    prediction_pdb = _text(workorder_row.get("prediction_pdb")) or _text(workorder_row.get("ts_prediction_pdb"))
    blockers: list[str] = []
    blockers.extend(_pdb_blockers(native_source, role="native_source"))
    if not blockers:
        blockers.extend(_native_prediction_identity_blockers(native_source, prediction_pdb))
    evidence_blockers, evidence_sha = _evidence_blockers(evidence_ref, target_id=target_id)
    blockers.extend(evidence_blockers)
    blockers.extend(_provenance_value_blockers(intake_row))

    native_status = "ready_to_copy"
    provenance_status = "ready_to_patch"
    if blockers:
        missing_input = any(
            blocker.endswith("_required")
            or blocker.endswith("_required_iso_date")
            or "REQUIRED" in _text(intake_row.get("notes"))
            for blocker in blockers
        )
        intake_status = "awaiting_input" if missing_input else "blocked"
        native_status = "waiting_on_input" if missing_input else "blocked"
        provenance_status = "waiting_on_input" if missing_input else "blocked"
    else:
        intake_status = "ready_to_apply"

    applied_native = False
    applied_provenance = False
    if apply and intake_status == "ready_to_apply":
        native_dest = _resolve(native_dropzone)
        native_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_resolve(native_source), native_dest)
        applied_native = True

        template_row, template_fields = _read_provenance_template(provenance_template)
        patched = dict(template_row)
        patched.update(
            {
                "benchmark_id": template_row.get("benchmark_id") or f"hist_{target_id}_clearance_candidate",
                "target_id": target_id,
                "scope": template_row.get("scope") or _text(workorder_row.get("scope")) or "complex",
                "split": template_row.get("split") or "historical_candidate",
                "leakage_clearance": _text(intake_row.get("leakage_clearance")),
                "prediction_method": template_row.get("prediction_method")
                or "internal_prediction_from_clearance_queue",
                "prediction_created_at": _text(intake_row.get("prediction_created_at")),
                "native_release_date": _text(intake_row.get("native_release_date")),
                "prediction_generated_before_native_release": _text(
                    intake_row.get("prediction_generated_before_native_release")
                ),
                "public_template_or_native_used_for_prediction": _text(
                    intake_row.get("public_template_or_native_used_for_prediction")
                ),
                "other_team_model_used": _text(intake_row.get("other_team_model_used")),
                "post_release_information_used": _text(intake_row.get("post_release_information_used")),
                "current_casp17_target": _text(intake_row.get("current_casp17_target")),
                "operator_clearance": _text(intake_row.get("operator_clearance")),
                "operator": _text(intake_row.get("operator")),
                "evidence_ref": evidence_ref,
                "notes": _text(intake_row.get("notes")),
            }
        )
        _write_provenance_template(provenance_template, patched, template_fields or PROVENANCE_COLUMNS)
        applied_provenance = True
        intake_status = "applied"
        native_status = "copied"
        provenance_status = "patched"

    return {
        "target_id": target_id,
        "intake_status": intake_status,
        "apply_mode": "applied" if apply and intake_status == "applied" else "dry_run",
        "native_source_pdb": native_source,
        "native_dropzone_pdb": native_dropzone,
        "native_action_status": native_status,
        "provenance_template_csv": provenance_template,
        "provenance_action_status": provenance_status,
        "no_leak_evidence_ref": evidence_ref,
        "evidence_ref_sha256": evidence_sha,
        "applied_native": "true" if applied_native else "false",
        "applied_provenance": "true" if applied_provenance else "false",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": _next_action(intake_status),
    }


def _next_action(status: str) -> str:
    if status == "ready_to_apply":
        return "review intake report, then rerun with --apply to copy native PDB and patch provenance template"
    if status == "applied":
        return "rerun the target identity clearance cycle to audit and sync manifest stubs"
    if status == "awaiting_input":
        return "fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls"
    return "resolve blocked native/evidence/provenance validation before apply"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    workorder_summary = _summary(workorder_payload)
    workorder_rows = _rows(workorder_payload)
    template_status = _ensure_intake_csv(args.intake_csv, workorder_rows)
    intake_rows, intake_file_blockers = _intake_by_target(args.intake_csv)
    rows: list[dict[str, Any]] = []
    for workorder_row in workorder_rows:
        target_id = _text(workorder_row.get("target_id")).upper()
        intake_row = intake_rows.get(target_id, {"target_id": target_id})
        row = _apply_row(workorder_row, intake_row, apply=bool(args.apply))
        if intake_file_blockers:
            blockers = [*(row["blockers"].split(",") if row["blockers"] else []), *intake_file_blockers]
            row["blockers"] = ",".join(dict.fromkeys(blocker for blocker in blockers if blocker))
            row["intake_status"] = "blocked"
            row["native_action_status"] = "blocked"
            row["provenance_action_status"] = "blocked"
            row["next_action"] = _next_action("blocked")
        rows.append(row)
    statuses = [_text(row.get("intake_status")) for row in rows]
    if not rows:
        intake_status = "missing_workorders"
    elif "blocked" in statuses:
        intake_status = "blocked"
    elif "ready_to_apply" in statuses:
        intake_status = "ready_to_apply"
    elif "awaiting_input" in statuses:
        intake_status = "awaiting_input"
    elif all(status == "applied" for status in statuses):
        intake_status = "applied"
    else:
        intake_status = "blocked"
    first_open = next((row for row in rows if row["intake_status"] != "applied"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_operator_intake",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "operator_intake_status": intake_status,
        "apply_mode": "apply" if args.apply else "dry_run",
        "template_status": template_status,
        "workorder_json": _artifact(args.workorder_json),
        "intake_csv": _artifact(args.intake_csv),
        "clearance_workorder_status": _text(workorder_summary.get("clearance_workorder_status")),
        "row_count": len(rows),
        "ready_to_apply_count": statuses.count("ready_to_apply"),
        "awaiting_input_count": statuses.count("awaiting_input"),
        "blocked_count": statuses.count("blocked"),
        "applied_count": statuses.count("applied"),
        "native_copy_ready_count": sum(1 for row in rows if row["native_action_status"] == "ready_to_copy"),
        "provenance_patch_ready_count": sum(
            1 for row in rows if row["provenance_action_status"] == "ready_to_patch"
        ),
        "native_copied_count": sum(1 for row in rows if row["native_action_status"] == "copied"),
        "provenance_patched_count": sum(1 for row in rows if row["provenance_action_status"] == "patched"),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("intake_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Operator Intake",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- operator_intake_status: `{summary['operator_intake_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- intake_csv: `{summary['intake_csv']}`",
        f"- rows ready/awaiting/blocked/applied: `{summary['ready_to_apply_count']}/{summary['awaiting_input_count']}/{summary['blocked_count']}/{summary['applied_count']}`",
        f"- native ready/copied: `{summary['native_copy_ready_count']}/{summary['native_copied_count']}`",
        f"- provenance ready/patched: `{summary['provenance_patch_ready_count']}/{summary['provenance_patched_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Intake Rows",
        "",
        "| target | status | native | provenance | evidence | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['intake_status']}` | `{row['native_action_status']}` | "
            f"`{row['provenance_action_status']}` | `{row['no_leak_evidence_ref'] or '-'}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing_workorders` | - | - | - | - | rebuild clearance workorders |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], REPORT_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and optionally apply CASP17 clearance operator intake.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    if payload["summary"]["operator_intake_status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
