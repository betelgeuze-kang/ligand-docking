#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_CURRENT_TARGET_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_current_target_prefill_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_current_target_prefill_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CURRENT_TARGET_PREFILL.md"

FALSE_VALUES = {"false", "no", "0", "n"}
PLACEHOLDER_TOKENS = ("REQUIRED", "YYYY-MM-DD")
ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "prefill_status",
    "existing_value",
    "proposed_value",
    "seed_manifest_value",
    "current_target_collision",
    "hist_prefix_present",
    "action",
    "blockers",
]
CLAIM_BOUNDARY = (
    "Local CASP17 seed current-target prefill only. It can set current_casp17_target=false when the seed row "
    "already says false, the target_id uses the local HIST_ prefix, and no current CASP17 target-id collision is "
    "present. It does not clear no-leak provenance, certify chronology, mutate any other operator fields, fetch "
    "native structures, score native accuracy, or submit to CASP."
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


def _is_false(value: Any) -> bool:
    return _norm(value) in FALSE_VALUES


def _is_open(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    upper = text.upper()
    return any(token in upper for token in PLACEHOLDER_TOKENS)


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _collect_target_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        target_id = _text(value.get("target_id")).upper()
        if target_id:
            found.add(target_id)
        for child in value.values():
            found.update(_collect_target_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_target_ids(child))
    return found


def _row_status(
    row: dict[str, str],
    seed_row: dict[str, str],
    current_target_ids: set[str],
    *,
    mode: str,
) -> tuple[dict[str, Any], bool]:
    target_id = _text(row.get("target_id")).upper()
    existing_value = _text(row.get("current_casp17_target"))
    seed_value = _text(seed_row.get("current_casp17_target"))
    hist_prefix = target_id.startswith("HIST_")
    collision = target_id in current_target_ids
    blockers: list[str] = []
    should_apply = False
    if not target_id:
        blockers.append("target_id_required")
    if not seed_row:
        blockers.append("seed_manifest_row_missing")
    if not hist_prefix:
        blockers.append("hist_prefix_required")
    if collision:
        blockers.append("current_target_collision")
    if not _is_false(seed_value):
        blockers.append("seed_manifest_current_target_false_required")
    if _is_false(existing_value):
        status = "already_safe_false"
        action = "keep current_casp17_target=false"
    elif blockers:
        status = "blocked"
        action = "manual review required before current_casp17_target can be set"
    elif mode == "apply" and _is_open(existing_value):
        status = "applied"
        action = "set current_casp17_target=false"
        should_apply = True
    elif _is_open(existing_value):
        status = "ready_to_apply"
        action = "rerun this tool with --mode apply"
    else:
        status = "blocked"
        action = "manual review required for non-placeholder current_casp17_target value"
        blockers.append("non_placeholder_value_not_false")
    return (
        {
            "target_id": target_id,
            "benchmark_id": _text(row.get("benchmark_id")),
            "prefill_status": status,
            "existing_value": existing_value,
            "proposed_value": "false" if status in {"ready_to_apply", "applied"} else "",
            "seed_manifest_value": seed_value,
            "current_target_collision": collision,
            "hist_prefix_present": hist_prefix,
            "action": action,
            "blockers": ",".join(blockers),
        },
        should_apply,
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_fields = _read_csv(args.operator_clearance_csv)
    seed_rows, _seed_fields = _read_csv(args.seed_manifest_csv)
    seed_by_target = {_text(row.get("target_id")).upper(): row for row in seed_rows}
    current_target_ids = _collect_target_ids(_read_json(args.current_target_json))
    rows: list[dict[str, Any]] = []
    updated_operator_rows: list[dict[str, str]] = []
    for index, row in enumerate(operator_rows, start=1):
        updated = dict(row)
        result, should_apply = _row_status(
            row,
            seed_by_target.get(_text(row.get("target_id")).upper(), {}),
            current_target_ids,
            mode=args.mode,
        )
        if should_apply:
            updated["current_casp17_target"] = "false"
        result["row_rank"] = index
        rows.append(result)
        updated_operator_rows.append(updated)
    if args.mode == "apply" and operator_rows:
        fields = operator_fields[:]
        if "current_casp17_target" not in fields:
            fields.append("current_casp17_target")
        _write_csv(args.operator_clearance_csv, updated_operator_rows, fields)
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["prefill_status"]] = status_counts.get(row["prefill_status"], 0) + 1
    blocked_count = status_counts.get("blocked", 0)
    if not operator_rows:
        status = "missing_operator_rows"
    elif blocked_count:
        status = "blocked"
    elif status_counts.get("ready_to_apply", 0):
        status = "ready_to_apply"
    elif status_counts.get("applied", 0):
        status = "applied"
    else:
        status = "already_prefilled"
    summary = {
        "packet_type": "casp17_historical_seed_current_target_prefill",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "prefill_status": status,
        "apply_mode": args.mode,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "current_target_json": _artifact(args.current_target_json),
        "row_count": len(rows),
        "ready_to_apply_count": status_counts.get("ready_to_apply", 0),
        "applied_count": status_counts.get("applied", 0),
        "already_safe_false_count": status_counts.get("already_safe_false", 0),
        "blocked_count": blocked_count,
        "current_target_collision_count": sum(1 for row in rows if row["current_target_collision"]),
        "hist_prefix_pass_count": sum(1 for row in rows if row["hist_prefix_present"]),
        "remaining_open_current_target_count": sum(
            1 for row in updated_operator_rows if not _is_false(row.get("current_casp17_target"))
        ),
        "first_next_action": _text(next((row.get("action") for row in rows if row["prefill_status"] != "already_safe_false"), "")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Current-Target Prefill",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- prefill_status: `{summary['prefill_status']}`",
        f"- mode: `{summary['apply_mode']}`",
        f"- rows ready/applied/already/blocked/total: `{summary['ready_to_apply_count']}/{summary['applied_count']}/{summary['already_safe_false_count']}/{summary['blocked_count']}/{summary['row_count']}`",
        f"- current target collisions: `{summary['current_target_collision_count']}`",
        f"- HIST prefix pass: `{summary['hist_prefix_pass_count']}`",
        f"- remaining open current-target fields: `{summary['remaining_open_current_target_count']}`",
        f"- operator clearance csv: `{summary['operator_clearance_csv']}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| rank | target | status | existing | proposed | seed | collision | action | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['prefill_status']}` | "
            f"`{row['existing_value'] or '-'}` | `{row['proposed_value'] or '-'}` | "
            f"`{row['seed_manifest_value'] or '-'}` | `{row['current_target_collision']}` | "
            f"{row['action']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `missing_operator_rows` | - | - | - | - | provide operator CSV | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely prefill current_casp17_target=false for historical seed rows.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--current-target-json", default=DEFAULT_CURRENT_TARGET_JSON)
    parser.add_argument("--mode", choices=["dry_run", "apply"], default="dry_run")
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
