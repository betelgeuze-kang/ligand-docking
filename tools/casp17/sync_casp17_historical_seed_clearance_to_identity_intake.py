#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CLEARED_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_cleared_current.csv"
DEFAULT_IDENTITY_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_clearance_to_identity_intake_sync_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_clearance_to_identity_intake_sync_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CLEARANCE_TO_IDENTITY_INTAKE_SYNC.md"

CLEAR_VALUES = {"no_leak", "cleared", "ready_for_row_fill", "internal_no_leak", "true", "yes", "approved"}
TRUE_VALUES = {"true", "yes", "1", "y"}
FALSE_VALUES = {"false", "no", "0", "n"}
PLACEHOLDER_PREFIXES = ("REQUIRED", "YYYY-MM-DD")
SYNC_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "sync_status",
    "seed_benchmark_id",
    "seed_target_id",
    "evidence_ref",
    "operator_clearance",
    "missing_or_blocked_reason",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local historical-seed-to-identity-intake sync only. It previews or, with --apply, copies already-cleared "
    "historical non-CASP17 seed identity values into the competitive-floor identity intake bundle. It does not "
    "choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, "
    "mutate row_fill.csv, import files, or submit to CASP."
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


def _norm(value: Any) -> str:
    return _text(value).lower()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    upper = text.upper()
    return any(upper.startswith(prefix) or prefix in upper for prefix in PLACEHOLDER_PREFIXES)


def _bool_is_true(value: Any) -> bool:
    return _norm(value) in TRUE_VALUES


def _bool_is_false(value: Any) -> bool:
    return _norm(value) in FALSE_VALUES


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{_artifact(path)}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{_artifact(path)}_header_missing")
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
        resolved = SYNC_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _path_exists(value: Any) -> bool:
    text = _text(value)
    return bool(text) and _resolve(text).is_file()


def _seed_blockers(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    scope = _norm(row.get("scope"))
    if _contains_placeholder(row.get("benchmark_id")):
        blockers.append("benchmark_id_required")
    if _contains_placeholder(row.get("target_id")):
        blockers.append("target_id_required")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_must_be_monomer_or_complex")
    if _norm(row.get("leakage_clearance")) not in CLEAR_VALUES:
        blockers.append("leakage_clearance_not_clear")
    if _norm(row.get("operator_clearance")) not in CLEAR_VALUES:
        blockers.append("operator_clearance_not_clear")
    if not _bool_is_true(row.get("prediction_generated_before_native_release")):
        blockers.append("prediction_chronology_not_confirmed")
    if not _bool_is_false(row.get("public_template_or_native_used_for_prediction")):
        blockers.append("public_template_or_native_used_not_false")
    if not _bool_is_false(row.get("other_team_model_used")):
        blockers.append("other_team_model_used_not_false")
    if not _bool_is_false(row.get("post_release_information_used")):
        blockers.append("post_release_information_used_not_false")
    if not _bool_is_false(row.get("current_casp17_target")):
        blockers.append("current_casp17_target_not_false")
    if not _path_exists(row.get("prediction_pdb")):
        blockers.append("prediction_pdb_missing")
    if not _path_exists(row.get("native_pdb")):
        blockers.append("native_pdb_missing")
    if _text(row.get("prediction_pdb")) and _text(row.get("prediction_pdb")) == _text(row.get("native_pdb")):
        blockers.append("prediction_native_paths_must_differ")
    return blockers


def _eligible_seed_rows(seed_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    eligible: list[dict[str, str]] = []
    rejected: list[dict[str, Any]] = []
    for row in seed_rows:
        blockers = _seed_blockers(row)
        if blockers:
            rejected.append(
                {
                    "benchmark_id": _text(row.get("benchmark_id")),
                    "target_id": _text(row.get("target_id")),
                    "scope": _text(row.get("scope")),
                    "blockers": ",".join(blockers),
                }
            )
        else:
            eligible.append(row)
    return eligible, rejected


def _intake_has_existing_identity(row: dict[str, str]) -> bool:
    return any(
        not _contains_placeholder(row.get(field))
        for field in ("proposed_benchmark_id", "proposed_target_id", "evidence_ref", "operator_clearance")
    )


def _sync_status_for_intake(
    intake: dict[str, str],
    seed: dict[str, str] | None,
    *,
    eligible_seed_count: int,
) -> tuple[str, str, str]:
    if _intake_has_existing_identity(intake):
        return (
            "protected_existing_identity",
            "protected_existing_value",
            "review the existing identity intake row before allowing automated seed sync",
        )
    if seed:
        return (
            "ready_to_sync",
            "",
            "review this seed identity mapping, then rerun with --apply to fill the identity intake bundle",
        )
    if eligible_seed_count == 0:
        return (
            "waiting_on_cleared_seed",
            "cleared_seed_manifest_empty_or_blocked",
            "clear historical seed rows before syncing competitive identity intake",
        )
    return (
        "waiting_on_matching_scope_seed",
        "no_remaining_cleared_seed_for_scope",
        "add more cleared historical seed rows for this scope",
    )


def _assign_seeds(
    intake_rows: list[dict[str, str]],
    eligible: list[dict[str, str]],
    evidence_ref: str,
) -> list[dict[str, Any]]:
    queues = {
        "monomer": [row for row in eligible if _norm(row.get("scope")) == "monomer"],
        "complex": [row for row in eligible if _norm(row.get("scope")) == "complex"],
    }
    output: list[dict[str, Any]] = []
    for intake in intake_rows:
        scope = _norm(intake.get("scope"))
        seed = queues.get(scope, []).pop(0) if queues.get(scope) else None
        status, reason, next_action = _sync_status_for_intake(intake, seed, eligible_seed_count=len(eligible))
        output.append(
            {
                "dropzone_id": _text(intake.get("dropzone_id")),
                "operator_priority": _int(intake.get("operator_priority")),
                "row_rank": _int(intake.get("row_rank")),
                "scope": _text(intake.get("scope")),
                "sync_status": status,
                "seed_benchmark_id": _text(seed.get("benchmark_id")) if seed else "",
                "seed_target_id": _text(seed.get("target_id")) if seed else "",
                "evidence_ref": evidence_ref if seed else "",
                "operator_clearance": _text(seed.get("operator_clearance")) if seed else "",
                "missing_or_blocked_reason": reason,
                "next_action": next_action,
            }
        )
    return output


def _apply_sync(args: argparse.Namespace, sync_rows: list[dict[str, Any]], intake_fieldnames: list[str]) -> int:
    intake_rows, _fields, blockers = _read_csv(args.identity_intake_csv)
    if blockers:
        return 0
    by_dropzone = {row["dropzone_id"]: row for row in sync_rows if row.get("sync_status") == "ready_to_sync"}
    applied = 0
    for row in intake_rows:
        sync = by_dropzone.get(_text(row.get("dropzone_id")))
        if not sync:
            continue
        row["proposed_benchmark_id"] = _text(sync.get("seed_benchmark_id"))
        row["proposed_target_id"] = _text(sync.get("seed_target_id"))
        row["evidence_ref"] = _text(sync.get("evidence_ref"))
        row["operator_clearance"] = _text(sync.get("operator_clearance"))
        applied += 1
    _write_csv(args.identity_intake_csv, intake_rows, fieldnames=intake_fieldnames)
    return applied


def _overall_status(
    rows: list[dict[str, Any]],
    *,
    intake_blockers: list[str],
    seed_blockers: list[str],
    eligible_count: int,
    rejected_count: int,
    applied_count: int,
) -> str:
    if intake_blockers or seed_blockers:
        return "blocked_missing_input"
    if applied_count:
        return "applied"
    ready = sum(1 for row in rows if row["sync_status"] == "ready_to_sync")
    protected = sum(1 for row in rows if row["sync_status"] == "protected_existing_identity")
    waiting = sum(1 for row in rows if str(row["sync_status"]).startswith("waiting_on"))
    if ready:
        return "ready_to_sync"
    if not eligible_count and rejected_count:
        return "blocked_seed_rows"
    if not eligible_count and waiting:
        return "waiting_on_cleared_seed_manifest"
    if protected and protected == len(rows):
        return "identity_intake_has_existing_values"
    if waiting:
        return "waiting_on_additional_cleared_seeds"
    return "synced_or_noop"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    seed_rows, _seed_fields, seed_blockers = _read_csv(args.cleared_seed_manifest_csv)
    intake_rows, intake_fieldnames, intake_blockers = _read_csv(args.identity_intake_csv)
    eligible, rejected = _eligible_seed_rows(seed_rows)
    evidence_ref = _artifact(args.cleared_seed_manifest_csv)
    rows = _assign_seeds(intake_rows, eligible, evidence_ref)
    applied_count = _apply_sync(args, rows, intake_fieldnames) if args.apply else 0
    ready_count = sum(1 for row in rows if row["sync_status"] == "ready_to_sync")
    waiting_count = sum(1 for row in rows if str(row["sync_status"]).startswith("waiting_on"))
    protected_count = sum(1 for row in rows if row["sync_status"] == "protected_existing_identity")
    blocked_count = len(rejected) + len(seed_blockers) + len(intake_blockers)
    first_open = next((row for row in rows if row["sync_status"] != "protected_existing_identity"), rows[0] if rows else {})
    status = _overall_status(
        rows,
        intake_blockers=intake_blockers,
        seed_blockers=seed_blockers,
        eligible_count=len(eligible),
        rejected_count=len(rejected),
        applied_count=applied_count,
    )
    summary = {
        "packet_type": "casp17_historical_seed_clearance_to_identity_intake_sync",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "seed_to_identity_sync_status": status,
        "apply_mode": "applied" if args.apply else "dry_run",
        "cleared_seed_manifest_csv": evidence_ref,
        "identity_intake_csv": _artifact(args.identity_intake_csv),
        "seed_manifest_row_count": len(seed_rows),
        "eligible_seed_row_count": len(eligible),
        "rejected_seed_row_count": len(rejected),
        "intake_row_count": len(intake_rows),
        "ready_to_sync_count": ready_count,
        "waiting_intake_count": waiting_count,
        "protected_intake_count": protected_count,
        "blocked_count": blocked_count,
        "applied_count": applied_count,
        "first_next_action": _text(first_open.get("next_action"))
        or "clear historical seed rows before syncing competitive identity intake",
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("sync_status")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "rejected_seed_rows": rejected}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Clearance To Identity Intake Sync",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- seed_to_identity_sync_status: `{summary['seed_to_identity_sync_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- seed rows eligible/rejected/total: `{summary['eligible_seed_row_count']}/{summary['rejected_seed_row_count']}/{summary['seed_manifest_row_count']}`",
        f"- intake rows ready/waiting/protected/total: `{summary['ready_to_sync_count']}/{summary['waiting_intake_count']}/{summary['protected_intake_count']}/{summary['intake_row_count']}`",
        f"- blocked/applied: `{summary['blocked_count']}/{summary['applied_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Sync Rows",
        "",
        "| priority | dropzone | scope | status | seed benchmark | seed target | reason | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['scope']}` | `{row['sync_status']}` | "
            f"`{row['seed_benchmark_id'] or '-'}` | `{row['seed_target_id'] or '-'}` | "
            f"`{row['missing_or_blocked_reason'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `waiting_on_cleared_seed_manifest` | - | - | - | no intake rows |")
    rejected = payload.get("rejected_seed_rows") or []
    if rejected:
        lines.extend(["", "## Rejected Seed Rows", "", "| benchmark | target | scope | blockers |", "| --- | --- | --- | --- |"])
        for row in rejected:
            lines.append(
                f"| `{row['benchmark_id'] or '-'}` | `{row['target_id'] or '-'}` | `{row['scope'] or '-'}` | `{row['blockers']}` |"
            )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=SYNC_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or apply cleared historical seed identity values into CASP17 identity intake."
    )
    parser.add_argument("--cleared-seed-manifest-csv", default=DEFAULT_CLEARED_SEED_MANIFEST_CSV)
    parser.add_argument("--identity-intake-csv", default=DEFAULT_IDENTITY_INTAKE_CSV)
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
