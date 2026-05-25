#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_unlock_kit_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_UNLOCK_KIT.md"

CLEAR_VALUES = {"ready_for_row_fill", "cleared", "no_leak", "internal_no_leak"}
IDENTITY_COLUMNS = [
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
    "blockers",
    "file_actions_unlocked",
    "canonical_prediction_pdb",
    "canonical_native_pdb",
    "canonical_ablation_dir",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor identity unlock kit only. It compresses benchmark_id/target_id entry into one row "
    "per competitive-floor benchmark and can optionally write cleared values back into the evidence import CSV. "
    "It does not choose historical targets, clear no-leak provenance, fetch native structures, score native "
    "accuracy, run predictors, mutate row_fill.csv, or submit to CASP."
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
        resolved = IDENTITY_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _current_targets(path_like: str | Path) -> set[str]:
    rows, _fieldnames, blockers = _read_csv(path_like)
    if blockers:
        return set()
    return {_text(row.get("target_id")).upper() for row in rows if _text(row.get("target_id"))}


def _identity_input_rows(path_like: str | Path) -> dict[str, dict[str, str]]:
    rows, _fieldnames, blockers = _read_csv(path_like)
    if blockers:
        return {}
    return {_text(row.get("dropzone_id")): row for row in rows if _text(row.get("dropzone_id"))}


def _identity_import_groups(import_rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    grouped: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in import_rows:
        if _text(row.get("evidence_class")) != "target_identity":
            continue
        column = _text(row.get("template_column"))
        if column in {"benchmark_id", "target_id"}:
            grouped[_text(row.get("dropzone_id"))][column] = row
    return grouped


def _file_action_counts(import_rows: list[dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in import_rows:
        if _text(row.get("import_kind")) == "file":
            counts[_text(row.get("dropzone_id"))] += 1
    return counts


def _canonical_prediction(target_id: str) -> str:
    return f"runs/casp17_historical_benchmark_predictions_current/{target_id}_prediction.pdb" if target_id else ""


def _canonical_native(target_id: str) -> str:
    return f"runs/casp17_historical_benchmark_natives_current/{target_id}_native.pdb" if target_id else ""


def _canonical_ablation_dir(target_id: str) -> str:
    return "runs/casp17_historical_ablation_predictions_current/<layer>/" + f"{target_id}TS.pdb" if target_id else ""


def _status_for(row: dict[str, Any], current_targets: set[str], duplicate_targets: set[str]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    benchmark_id = _text(row.get("proposed_benchmark_id"))
    target_id = _text(row.get("proposed_target_id")).upper()
    clearance = _text(row.get("operator_clearance")).lower()
    evidence_ref = _text(row.get("evidence_ref"))
    if _contains_placeholder(benchmark_id):
        blockers.append("proposed_benchmark_id_required")
    elif not benchmark_id.startswith("hist_"):
        blockers.append("proposed_benchmark_id_must_start_hist_")
    if _contains_placeholder(target_id):
        blockers.append("proposed_target_id_required")
    if target_id in current_targets:
        blockers.append("proposed_target_id_is_current_casp17_target")
    if target_id in duplicate_targets:
        blockers.append("proposed_target_id_duplicate")
    if not evidence_ref:
        blockers.append("evidence_ref_required")
    if clearance not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    if blockers:
        awaiting = {
            "proposed_benchmark_id_required",
            "proposed_target_id_required",
            "evidence_ref_required",
            "operator_clearance_required",
        }
        return ("awaiting_identity" if set(blockers) <= awaiting else "blocked_identity", blockers)
    return "ready_for_import", []


def _next_action(status: str) -> str:
    if status == "ready_for_import":
        return "run this tool with --apply to write benchmark_id/target_id import rows, then run the evidence round"
    if status == "blocked_identity":
        return "fix blockers before applying identity values"
    return "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance"


def _kit_row(
    dropzone_id: str,
    grouped: dict[str, dict[str, str]],
    existing: dict[str, str],
    file_action_count: int,
) -> dict[str, Any]:
    benchmark_row = grouped.get("benchmark_id", {})
    target_row = grouped.get("target_id", {})
    proposed_target = _text(existing.get("proposed_target_id") or target_row.get("proposed_value")).upper()
    return {
        "dropzone_id": dropzone_id,
        "operator_priority": _int(benchmark_row.get("operator_priority") or target_row.get("operator_priority")),
        "row_rank": _int(benchmark_row.get("row_rank") or target_row.get("row_rank")),
        "scope": _text(benchmark_row.get("scope") or target_row.get("scope")),
        "current_benchmark_id": _text(benchmark_row.get("benchmark_id")),
        "current_target_id": _text(target_row.get("target_id")),
        "proposed_benchmark_id": _text(existing.get("proposed_benchmark_id") or benchmark_row.get("proposed_value")),
        "proposed_target_id": proposed_target,
        "evidence_ref": _text(existing.get("evidence_ref") or benchmark_row.get("evidence_ref") or target_row.get("evidence_ref")),
        "operator_clearance": _text(
            existing.get("operator_clearance")
            or benchmark_row.get("operator_clearance")
            or target_row.get("operator_clearance")
        ),
        "identity_status": "",
        "blockers": "",
        "file_actions_unlocked": file_action_count if proposed_target else 0,
        "canonical_prediction_pdb": _canonical_prediction(proposed_target),
        "canonical_native_pdb": _canonical_native(proposed_target),
        "canonical_ablation_dir": _canonical_ablation_dir(proposed_target),
        "next_action": "",
    }


def _apply_ready_rows(args: argparse.Namespace, rows: list[dict[str, Any]]) -> int:
    import_rows, fieldnames, blockers = _read_csv(args.import_csv)
    if blockers:
        return 0
    ready = {row["dropzone_id"]: row for row in rows if row["identity_status"] == "ready_for_import"}
    applied_count = 0
    for import_row in import_rows:
        kit = ready.get(_text(import_row.get("dropzone_id")))
        if not kit:
            continue
        column = _text(import_row.get("template_column"))
        if _text(import_row.get("evidence_class")) != "target_identity" or column not in {"benchmark_id", "target_id"}:
            continue
        import_row["proposed_value"] = _text(kit["proposed_benchmark_id" if column == "benchmark_id" else "proposed_target_id"])
        import_row["evidence_ref"] = _text(kit["evidence_ref"])
        import_row["operator_clearance"] = _text(kit["operator_clearance"])
        applied_count += 1
    _write_csv(args.import_csv, import_rows, fieldnames=fieldnames)
    return applied_count


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    import_rows, _fieldnames, _blockers = _read_csv(args.import_csv)
    grouped = _identity_import_groups(import_rows)
    existing = _identity_input_rows(args.out_csv)
    file_counts = _file_action_counts(import_rows)
    current_targets = _current_targets(args.current_target_csv)
    raw_rows = [
        _kit_row(dropzone_id, columns, existing.get(dropzone_id, {}), file_counts[dropzone_id])
        for dropzone_id, columns in sorted(grouped.items())
    ]
    target_counts = Counter(_text(row.get("proposed_target_id")).upper() for row in raw_rows if _text(row.get("proposed_target_id")))
    duplicates = {target for target, count in target_counts.items() if count > 1}
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        status, blockers = _status_for(row, current_targets, duplicates)
        row["identity_status"] = status
        row["blockers"] = ",".join(blockers)
        row["next_action"] = _next_action(status)
        rows.append(row)
    applied_count = _apply_ready_rows(args, rows) if args.apply else 0
    by_status = Counter(str(row["identity_status"]) for row in rows)
    first_open = next((row for row in rows if row["identity_status"] != "ready_for_import"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_identity_unlock_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity_unlock_status": "ready_for_import" if rows and by_status["ready_for_import"] == len(rows) else "awaiting_identity",
        "apply_mode": "applied" if args.apply else "dry_run",
        "import_csv": _artifact(args.import_csv),
        "current_target_csv": _artifact(args.current_target_csv),
        "row_count": len(rows),
        "ready_for_import_count": by_status["ready_for_import"],
        "awaiting_identity_count": by_status["awaiting_identity"],
        "blocked_identity_count": by_status["blocked_identity"],
        "applied_identity_import_count": applied_count,
        "file_actions_unlocked_count": sum(_int(row.get("file_actions_unlocked")) for row in rows if row["identity_status"] == "ready_for_import"),
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("identity_status")),
        "first_open_blockers": _text(first_open.get("blockers")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Unlock Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- identity_unlock_status: `{summary['identity_unlock_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- rows: `{summary['row_count']}`",
        f"- ready/awaiting/blocked: `{summary['ready_for_import_count']}/{summary['awaiting_identity_count']}/{summary['blocked_identity_count']}`",
        f"- applied identity import cells: `{summary['applied_identity_import_count']}`",
        f"- file actions unlocked by ready identities: `{summary['file_actions_unlocked_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}` `{summary['first_open_blockers'] or '-'}`",
        "",
        "## Identity Rows",
        "",
        "| priority | dropzone | status | current benchmark | current target | proposed benchmark | proposed target | files unlocked | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['identity_status']}` | "
            f"`{row['current_benchmark_id']}` | `{row['current_target_id']}` | "
            f"`{row['proposed_benchmark_id'] or '-'}` | `{row['proposed_target_id'] or '-'}` | "
            f"{row['file_actions_unlocked']} | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | - | - | - | - | 0 | - | no identity rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=IDENTITY_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or apply a compact identity unlock kit for CASP17 evidence imports.")
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
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
