#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_READY_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_ready_current.csv"
DEFAULT_CANDIDATE_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_candidate_current.csv"
DEFAULT_SEED_CLEARED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_cleared_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"
DEFAULT_OPERATOR_PREFLIGHT_JSON = "runs/casp17_win_tier_benchmark_operator_preflight_current.json"
DEFAULT_OPERATOR_IMPORT_JSON = "runs/casp17_win_tier_benchmark_operator_import_packet_current.json"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_candidate_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_candidate_packet_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_CANDIDATE_PACKET.md"

CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CANDIDATE_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "current_benchmark_id",
    "current_target_id",
    "candidate_status",
    "source_artifact",
    "source_rank",
    "source_row_status",
    "proposed_benchmark_id",
    "proposed_target_id",
    "evidence_ref",
    "operator_clearance",
    "source_blockers",
    "next_action",
]
INTAKE_IDENTITY_FIELDS = ["proposed_benchmark_id", "proposed_target_id", "evidence_ref", "operator_clearance"]
CLAIM_BOUNDARY = (
    "Local competitive-floor identity candidate packet only. It inspects local historical benchmark/operator "
    "manifests and proposes intake values only when a source row already has a non-placeholder historical target "
    "identity and no-leak/operator clearance. It does not choose targets, clear provenance, fetch native "
    "structures, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP. It writes intake "
    "CSV values only when --apply is explicitly provided."
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


def _write_csv(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    fieldnames: list[str] | None = None,
) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = CANDIDATE_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _current_targets(path_like: str | Path) -> set[str]:
    rows, _fieldnames, blockers = _read_csv(path_like)
    if blockers:
        return set()
    return {_text(row.get("target_id")).upper() for row in rows if _text(row.get("target_id"))}


def _source_definitions(args: argparse.Namespace) -> list[tuple[str, str]]:
    return [
        ("ready_manifest", args.ready_manifest_csv),
        ("candidate_manifest", args.candidate_manifest_csv),
        ("seed_cleared_manifest", args.seed_cleared_manifest_csv),
        ("seed_manifest", args.seed_manifest_csv),
        ("operator_template", args.operator_template_csv),
    ]


def _source_blockers(row: dict[str, str], current_targets: set[str]) -> list[str]:
    blockers: list[str] = []
    benchmark_id = _text(row.get("benchmark_id"))
    target_id = _text(row.get("target_id")).upper()
    scope = _text(row.get("scope")).lower()
    if _contains_placeholder(benchmark_id):
        blockers.append("benchmark_id_required")
    elif not benchmark_id.startswith("hist_"):
        blockers.append("benchmark_id_must_start_hist_")
    if _contains_placeholder(target_id):
        blockers.append("target_id_required")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if _text(row.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
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


def _candidate_pool(args: argparse.Namespace, current_targets: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for source_name, source_path in _source_definitions(args):
        source_rows, _fieldnames, blockers = _read_csv(source_path)
        if blockers:
            continue
        for index, row in enumerate(source_rows, start=1):
            target_id = _text(row.get("target_id")).upper()
            duplicate = target_id in seen_targets and not _contains_placeholder(target_id)
            source_blockers = _source_blockers(row, current_targets)
            if duplicate:
                source_blockers.append("duplicate_candidate_target_id")
            if not _contains_placeholder(target_id):
                seen_targets.add(target_id)
            source_status = "ready_for_intake" if not source_blockers else "blocked_candidate_source"
            candidates.append(
                {
                    "source_artifact": _artifact(source_path),
                    "source_name": source_name,
                    "source_rank": index,
                    "scope": _text(row.get("scope")).lower(),
                    "source_row_status": source_status,
                    "proposed_benchmark_id": _text(row.get("benchmark_id")),
                    "proposed_target_id": target_id,
                    "evidence_ref": _text(row.get("evidence_ref")) or f"{_artifact(source_path)}#{_text(row.get('benchmark_id'))}",
                    "operator_clearance": _text(row.get("operator_clearance")).lower(),
                    "source_blockers": ",".join(source_blockers),
                }
            )
    return candidates


def _candidate_for_scope(candidates: list[dict[str, Any]], scope: str, used_targets: set[str]) -> dict[str, Any] | None:
    for candidate in candidates:
        if _text(candidate.get("scope")) != scope:
            continue
        if _text(candidate.get("source_row_status")) != "ready_for_intake":
            continue
        target_id = _text(candidate.get("proposed_target_id")).upper()
        if target_id in used_targets:
            continue
        used_targets.add(target_id)
        return candidate
    return None


def _next_action(status: str, candidate_count: int) -> str:
    if status == "ready_for_intake":
        return "review this local candidate, then run with --apply or copy values into the identity intake bundle"
    if candidate_count:
        return "fix blocked local candidate rows until a cleared non-current historical target is ready"
    return "populate the historical/operator manifest with cleared non-current historical targets and rerun this packet"


def _apply_candidates(args: argparse.Namespace, rows: list[dict[str, Any]]) -> int:
    intake_rows, fieldnames, blockers = _read_csv(args.intake_csv)
    if blockers:
        return 0
    by_dropzone = {row["dropzone_id"]: row for row in rows if row["candidate_status"] == "ready_for_intake"}
    applied = 0
    for intake in intake_rows:
        candidate = by_dropzone.get(_text(intake.get("dropzone_id")))
        if not candidate:
            continue
        for field in INTAKE_IDENTITY_FIELDS:
            intake[field] = _text(candidate.get(field))
        applied += 1
    _write_csv(args.intake_csv, intake_rows, fieldnames=fieldnames)
    return applied


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    intake_rows, _intake_fields, intake_blockers = _read_csv(args.intake_csv)
    current_targets = _current_targets(args.current_target_csv)
    candidates = _candidate_pool(args, current_targets)
    used_targets: set[str] = set()
    rows: list[dict[str, Any]] = []
    for intake in intake_rows:
        scope = _text(intake.get("scope")).lower()
        candidate = _candidate_for_scope(candidates, scope, used_targets)
        status = "ready_for_intake" if candidate else "awaiting_candidate_source"
        source_blocked_count = sum(
            1
            for item in candidates
            if _text(item.get("scope")) == scope and _text(item.get("source_row_status")) != "ready_for_intake"
        )
        rows.append(
            {
                "dropzone_id": _text(intake.get("dropzone_id")),
                "operator_priority": _int(intake.get("operator_priority")),
                "row_rank": _int(intake.get("row_rank")),
                "scope": scope,
                "current_benchmark_id": _text(intake.get("current_benchmark_id")),
                "current_target_id": _text(intake.get("current_target_id")),
                "candidate_status": status,
                "source_artifact": _text(candidate.get("source_artifact")) if candidate else "",
                "source_rank": _int(candidate.get("source_rank")) if candidate else 0,
                "source_row_status": _text(candidate.get("source_row_status")) if candidate else "",
                "proposed_benchmark_id": _text(candidate.get("proposed_benchmark_id")) if candidate else "",
                "proposed_target_id": _text(candidate.get("proposed_target_id")) if candidate else "",
                "evidence_ref": _text(candidate.get("evidence_ref")) if candidate else "",
                "operator_clearance": _text(candidate.get("operator_clearance")) if candidate else "",
                "source_blockers": _text(candidate.get("source_blockers")) if candidate else f"blocked_source_candidates:{source_blocked_count}",
                "next_action": _next_action(status, len(candidates)),
            }
        )
    applied = _apply_candidates(args, rows) if args.apply else 0
    by_status = Counter(_text(row.get("candidate_status")) for row in rows)
    source_by_status = Counter(_text(row.get("source_row_status")) for row in candidates)
    first_open = next((row for row in rows if row["candidate_status"] != "ready_for_intake"), rows[0] if rows else {})
    operator_preflight_summary = _summary(_read_json(args.operator_preflight_json))
    operator_import_summary = _summary(_read_json(args.operator_import_json))
    if intake_blockers:
        candidate_status = "blocked"
    elif rows and by_status["ready_for_intake"] == len(rows):
        candidate_status = "ready_for_intake_sync"
    elif by_status["ready_for_intake"]:
        candidate_status = "partial_candidates_ready"
    else:
        candidate_status = "awaiting_candidate_sources"
    summary = {
        "packet_type": "casp17_competitive_floor_identity_candidate_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity_candidate_status": candidate_status,
        "apply_mode": "applied" if args.apply else "dry_run",
        "intake_csv": _artifact(args.intake_csv),
        "ready_manifest_csv": _artifact(args.ready_manifest_csv),
        "candidate_manifest_csv": _artifact(args.candidate_manifest_csv),
        "seed_cleared_manifest_csv": _artifact(args.seed_cleared_manifest_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "operator_template_csv": _artifact(args.operator_template_csv),
        "operator_preflight_status": _text(operator_preflight_summary.get("operator_preflight_status")),
        "operator_import_status": _text(operator_import_summary.get("import_status")),
        "row_count": len(rows),
        "ready_for_intake_count": by_status["ready_for_intake"],
        "awaiting_candidate_source_count": by_status["awaiting_candidate_source"],
        "source_candidate_count": len(candidates),
        "source_ready_candidate_count": source_by_status["ready_for_intake"],
        "source_blocked_candidate_count": source_by_status["blocked_candidate_source"],
        "applied_intake_count": applied,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("candidate_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "candidate_rows": candidates}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Candidate Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- identity_candidate_status: `{summary['identity_candidate_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- intake rows ready/awaiting: `{summary['ready_for_intake_count']}/{summary['awaiting_candidate_source_count']}`",
        f"- source candidates ready/blocked/total: `{summary['source_ready_candidate_count']}/{summary['source_blocked_candidate_count']}/{summary['source_candidate_count']}`",
        f"- operator preflight/import: `{summary['operator_preflight_status'] or '-'}`/`{summary['operator_import_status'] or '-'}`",
        f"- applied intake rows: `{summary['applied_intake_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Intake Candidate Rows",
        "",
        "| priority | dropzone | scope | status | proposed benchmark | proposed target | source | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['scope']}` | "
            f"`{row['candidate_status']}` | `{row['proposed_benchmark_id'] or '-'}` | "
            f"`{row['proposed_target_id'] or '-'}` | `{row['source_artifact'] or '-'}` | "
            f"`{row['source_blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `ready` | - | - | - | - | no intake rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=CANDIDATE_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 competitive-floor identity intake candidates.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--ready-manifest-csv", default=DEFAULT_READY_MANIFEST_CSV)
    parser.add_argument("--candidate-manifest-csv", default=DEFAULT_CANDIDATE_MANIFEST_CSV)
    parser.add_argument("--seed-cleared-manifest-csv", default=DEFAULT_SEED_CLEARED_MANIFEST_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--operator-preflight-json", default=DEFAULT_OPERATOR_PREFLIGHT_JSON)
    parser.add_argument("--operator-import-json", default=DEFAULT_OPERATOR_IMPORT_JSON)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
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
