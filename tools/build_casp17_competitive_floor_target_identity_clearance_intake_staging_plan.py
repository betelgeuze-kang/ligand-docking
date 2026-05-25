#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROMOTED_MANIFEST_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_promoted_manifest_candidate_current.csv"
)
DEFAULT_PROMOTION_PLAN_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json"
)
DEFAULT_IDENTITY_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_CANDIDATE_INTAKE_CSV = (
    "casp17/casp17_competitive_floor_identity_intake_bundle_candidate_from_clearance_current.csv"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.csv"
)
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_INTAKE_STAGING_PLAN.md"

MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
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
]
INTAKE_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "current_benchmark_id",
    "current_target_id",
    "proposed_benchmark_id",
    "proposed_target_id",
    "evidence_ref",
    "operator_clearance",
    "identity_status",
    "missing_field_count",
    "blockers",
    "file_actions_unlocked",
    "readiness_gate_status",
    "apply_identity_command",
    "verify_command",
    "next_action",
]
PLAN_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "staging_status",
    "benchmark_id",
    "target_id",
    "evidence_ref",
    "operator_clearance",
    "manifest_source_csv",
    "prediction_pdb",
    "native_pdb",
    "blockers",
    "next_action",
]
CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak", "true", "yes"}
CLAIM_BOUNDARY = (
    "Local competitive-floor clearance-to-intake staging plan only. It maps already promoted target identity "
    "manifest candidate rows onto empty competitive-floor identity intake slots and writes a separate candidate "
    "intake CSV for operator review. It does not mutate the live identity intake bundle, mutate the identity "
    "unlock kit, fetch native structures, clear provenance, score native accuracy, run predictors, or submit to CASP."
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


def _current_targets(path_like: str | Path) -> set[str]:
    rows, _fields, blockers = _read_csv(path_like)
    if blockers:
        return set()
    return {_text(row.get("target_id")).upper() for row in rows if _text(row.get("target_id"))}


def _open_intake_slots(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    slots: list[dict[str, str]] = []
    for row in rows:
        if _contains_placeholder(row.get("proposed_benchmark_id")) and _contains_placeholder(row.get("proposed_target_id")):
            slots.append(row)
    return sorted(slots, key=lambda row: (_int(row.get("operator_priority")) or _int(row.get("row_rank")), _text(row.get("dropzone_id"))))


def _manifest_blockers(row: dict[str, str], current_targets: set[str], duplicate_targets: set[str]) -> list[str]:
    blockers: list[str] = []
    missing_columns = [column for column in MANIFEST_COLUMNS if column not in row]
    if missing_columns:
        blockers.append("manifest_required_columns_missing:" + ",".join(missing_columns))
    benchmark_id = _text(row.get("benchmark_id"))
    target_id = _text(row.get("target_id")).upper()
    scope = _text(row.get("scope"))
    for column in ["benchmark_id", "target_id", "scope", "prediction_pdb", "native_pdb", "operator_clearance"]:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"{column}_required")
    if benchmark_id and not benchmark_id.startswith("hist_"):
        blockers.append("benchmark_id_must_start_hist")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_must_be_monomer_or_complex")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed")
    if target_id in duplicate_targets:
        blockers.append("duplicate_promoted_target_id")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    return blockers


def _candidate_intake_row(source: dict[str, str], assignment: dict[str, Any] | None) -> dict[str, Any]:
    row = {column: _text(source.get(column)) for column in INTAKE_COLUMNS}
    if assignment is None:
        return row
    row["proposed_benchmark_id"] = _text(assignment.get("benchmark_id"))
    row["proposed_target_id"] = _text(assignment.get("target_id"))
    row["evidence_ref"] = _text(assignment.get("evidence_ref"))
    row["operator_clearance"] = _text(assignment.get("operator_clearance"))
    row["identity_status"] = "staged_for_operator_review"
    row["missing_field_count"] = "0"
    row["blockers"] = ""
    row["next_action"] = "review this candidate row, then copy it into the live intake bundle before sync"
    return row


def _next_action(status: str) -> str:
    if status == "staged_for_operator_review":
        return "review candidate intake values before copying them into the live identity intake bundle"
    if status == "blocked_no_open_scope_slot":
        return "add or free a matching-scope identity intake slot before staging this promoted target"
    if status == "blocked_manifest_row":
        return "fix promoted manifest blockers and rerun the clearance promotion plan"
    return "wait for promoted clearance manifest rows"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    promotion_summary = _summary(_read_json(args.promotion_plan_json))
    manifest_rows, manifest_fields, manifest_blockers = _read_csv(args.promoted_manifest_csv)
    intake_rows, intake_fields, intake_blockers = _read_csv(args.identity_intake_csv)
    current_targets = _current_targets(args.current_target_csv)
    promoted_targets = [_text(row.get("target_id")).upper() for row in manifest_rows if _text(row.get("target_id"))]
    target_counts = Counter(promoted_targets)
    duplicate_targets = {target for target, count in target_counts.items() if count > 1}
    slots_by_scope: dict[str, list[dict[str, str]]] = {"monomer": [], "complex": []}
    for slot in _open_intake_slots(intake_rows):
        scope = _text(slot.get("scope"))
        if scope in slots_by_scope:
            slots_by_scope[scope].append(slot)
    initial_open_slot_count = sum(len(slots) for slots in slots_by_scope.values())

    rows: list[dict[str, Any]] = []
    assignments_by_dropzone: dict[str, dict[str, Any]] = {}
    manifest_field_blocker = ""
    if manifest_fields:
        missing_columns = [column for column in MANIFEST_COLUMNS if column not in manifest_fields]
        if missing_columns:
            manifest_field_blocker = "manifest_required_columns_missing:" + ",".join(missing_columns)
    for manifest in manifest_rows:
        target_id = _text(manifest.get("target_id")).upper()
        scope = _text(manifest.get("scope"))
        blockers = list(manifest_blockers)
        if manifest_field_blocker:
            blockers.append(manifest_field_blocker)
        blockers.extend(_manifest_blockers(manifest, current_targets, duplicate_targets))
        slot = None
        if not blockers:
            candidates = slots_by_scope.get(scope, [])
            slot = candidates.pop(0) if candidates else None
            if slot is None:
                blockers.append("no_open_identity_intake_slot_for_scope")
        status = "staged_for_operator_review" if not blockers and slot else (
            "blocked_no_open_scope_slot" if "no_open_identity_intake_slot_for_scope" in blockers else "blocked_manifest_row"
        )
        evidence_ref = _artifact(args.promotion_plan_json) + "#" + target_id if target_id else _artifact(args.promotion_plan_json)
        row = {
            "dropzone_id": _text(slot.get("dropzone_id")) if slot else "",
            "operator_priority": _int(slot.get("operator_priority")) if slot else 0,
            "row_rank": _int(slot.get("row_rank")) if slot else 0,
            "scope": scope,
            "staging_status": status,
            "benchmark_id": _text(manifest.get("benchmark_id")),
            "target_id": target_id,
            "evidence_ref": evidence_ref,
            "operator_clearance": _text(manifest.get("operator_clearance")),
            "manifest_source_csv": _artifact(args.promoted_manifest_csv),
            "prediction_pdb": _text(manifest.get("prediction_pdb")),
            "native_pdb": _text(manifest.get("native_pdb")),
            "blockers": ",".join(dict.fromkeys(blockers)),
            "next_action": _next_action(status),
        }
        rows.append(row)
        if status == "staged_for_operator_review" and slot:
            assignments_by_dropzone[row["dropzone_id"]] = row

    candidate_intake_rows = [
        _candidate_intake_row(row, assignments_by_dropzone.get(_text(row.get("dropzone_id"))))
        for row in intake_rows
    ]
    _write_csv(args.out_candidate_intake_csv, candidate_intake_rows, intake_fields or INTAKE_COLUMNS)
    staged_count = sum(1 for row in rows if row["staging_status"] == "staged_for_operator_review")
    blocked_count = len(rows) - staged_count
    if manifest_blockers or intake_blockers:
        staging_status = "missing_inputs"
    elif not manifest_rows:
        staging_status = "waiting_on_promoted_manifest"
    elif staged_count == len(rows):
        staging_status = "ready_for_operator_intake_review"
    elif staged_count:
        staging_status = "partial_ready_for_operator_intake_review"
    else:
        staging_status = "blocked_assignments"
    first_open = next((row for row in rows if row["staging_status"] != "staged_for_operator_review"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_intake_staging_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_intake_staging_status": staging_status,
        "promotion_plan_json": _artifact(args.promotion_plan_json),
        "promotion_status": _text(promotion_summary.get("clearance_promotion_status")),
        "promoted_manifest_csv": _artifact(args.promoted_manifest_csv),
        "identity_intake_csv": _artifact(args.identity_intake_csv),
        "candidate_intake_csv": _artifact(args.out_candidate_intake_csv),
        "current_target_csv": _artifact(args.current_target_csv),
        "promoted_manifest_row_count": len(manifest_rows),
        "identity_intake_row_count": len(intake_rows),
        "open_identity_intake_slot_count": initial_open_slot_count,
        "open_monomer_slot_count": len(slots_by_scope["monomer"]),
        "open_complex_slot_count": len(slots_by_scope["complex"]),
        "staged_identity_count": staged_count,
        "blocked_assignment_count": blocked_count,
        "candidate_intake_row_count": len(candidate_intake_rows),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_status": _text(first_open.get("staging_status")),
        "first_open_next_action": _text(first_open.get("next_action")) or _next_action("waiting_on_promoted_manifest"),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "candidate_intake_rows": candidate_intake_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Intake Staging Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_intake_staging_status: `{summary['clearance_intake_staging_status']}`",
        f"- promotion_status: `{summary['promotion_status'] or '-'}`",
        f"- promoted/staged/blocked: `{summary['promoted_manifest_row_count']}/{summary['staged_identity_count']}/{summary['blocked_assignment_count']}`",
        f"- identity intake rows/open slots: `{summary['identity_intake_row_count']}/{summary['open_identity_intake_slot_count']}`",
        f"- open monomer/complex slots after staging: `{summary['open_monomer_slot_count']}/{summary['open_complex_slot_count']}`",
        f"- candidate_intake_csv: `{summary['candidate_intake_csv']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Staging Rows",
        "",
        "| dropzone | scope | status | benchmark | target | clearance | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['dropzone_id'] or '-'}` | `{row['scope'] or '-'}` | `{row['staging_status']}` | "
            f"`{row['benchmark_id'] or '-'}` | `{row['target_id'] or '-'}` | "
            f"`{row['operator_clearance'] or '-'}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `waiting_on_promoted_manifest` | - | - | - | `promoted_manifest_empty` | wait for promoted clearance manifest rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], PLAN_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage promoted CASP17 clearance manifest rows for identity intake.")
    parser.add_argument("--promoted-manifest-csv", default=DEFAULT_PROMOTED_MANIFEST_CSV)
    parser.add_argument("--promotion-plan-json", default=DEFAULT_PROMOTION_PLAN_JSON)
    parser.add_argument("--identity-intake-csv", default=DEFAULT_IDENTITY_INTAKE_CSV)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--out-candidate-intake-csv", default=DEFAULT_OUT_CANDIDATE_INTAKE_CSV)
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
