#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_UPLOAD_REVIEW_PACKET_JSON = "casp17/casp17_current_upload_review_packet_current.json"
DEFAULT_UPLOAD_OPERATOR_DECISION_KIT_JSON = "casp17/casp17_current_upload_operator_decision_kit_current.json"
DEFAULT_POST_NATIVE_SCORING_SCAFFOLD_JSON = "casp17/casp17_current_post_native_scoring_scaffold_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_current_queue_rollover_hygiene_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_queue_rollover_hygiene_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_QUEUE_ROLLOVER_HYGIENE_AUDIT.md"

ROW_COLUMNS = [
    "surface_id",
    "surface_status",
    "managed_root",
    "active_folder_count",
    "actual_folder_count",
    "missing_active_folder_count",
    "stale_extra_folder_count",
    "first_missing_active_folder",
    "first_stale_extra_folder",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "CASP17 current queue rollover hygiene audit only. It compares active manifest folder references "
    "against generated direct-child folders for current upload review, operator decision, and post-native "
    "scoring surfaces. It does not delete, move, archive, or clean folders, submit to CASP, serialize an "
    "author code, compute native accuracy, or mark strict-blind competitive proof."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Queue Rollover Hygiene Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['status']}`",
        f"- surfaces pass/stale/blocked/total: `{summary['surface_pass_count']}/{summary['surface_stale_count']}/{summary['surface_blocked_count']}/{summary['surface_count']}`",
        f"- active/actual folders: `{summary['active_folder_count']}/{summary['actual_folder_count']}`",
        f"- missing/stale folders: `{summary['missing_active_folder_count']}/{summary['stale_extra_folder_count']}`",
        f"- first stale: `{summary['first_stale_surface_id'] or '-'}` `{summary['first_stale_extra_folder'] or '-'}`",
        "",
        "## Surfaces",
        "",
        "| surface | status | active | actual | missing | stale | first stale | next action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['surface_id']}` | `{row['surface_status']}` | "
            f"{row['active_folder_count']} | {row['actual_folder_count']} | "
            f"{row['missing_active_folder_count']} | {row['stale_extra_folder_count']} | "
            f"`{row['first_stale_extra_folder'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `blocked_no_surfaces` | 0 | 0 | 0 | 0 | - | provide manifest inputs |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _direct_child_dirs(root: str | Path) -> set[str]:
    path = _resolve(root)
    if not path.is_dir():
        return set()
    return {_artifact(child) for child in path.iterdir() if child.is_dir()}


def _parent_folder(path_like: Any) -> str:
    text = _text(path_like)
    if not text:
        return ""
    return _artifact(Path(text).parent)


def _common_parent_from_rows(rows: list[dict[str, Any]], field_name: str, fallback: str) -> str:
    folders = [_resolve(row.get(field_name)) for row in rows if _text(row.get(field_name))]
    if not folders:
        return fallback
    first_parent = folders[0].parent
    if all(folder.parent == first_parent for folder in folders):
        return _artifact(first_parent)
    return fallback


def _surface_row(
    surface_id: str,
    managed_root: str,
    active_folders: set[str],
    actual_folders: set[str],
) -> dict[str, Any]:
    missing = sorted(active_folders - actual_folders)
    stale = sorted(actual_folders - active_folders)
    blockers: list[str] = []
    if missing:
        blockers.append("active_folder_missing")
    if stale:
        blockers.append("stale_generated_folder_retained")
    if missing:
        status = "blocked_missing_active_folder"
        next_action = "regenerate or restore missing active folder before operator use"
    elif stale:
        status = "stale_generated_folders_retained"
        next_action = "operator-approved cleanup may remove stale generated folders after confirming no decisions were entered"
    else:
        status = "pass"
        next_action = "keep regenerating this audit after each date or queue rollover"
    return {
        "surface_id": surface_id,
        "surface_status": status,
        "managed_root": managed_root,
        "active_folder_count": len(active_folders),
        "actual_folder_count": len(actual_folders),
        "missing_active_folder_count": len(missing),
        "stale_extra_folder_count": len(stale),
        "first_missing_active_folder": missing[0] if missing else "",
        "first_stale_extra_folder": stale[0] if stale else "",
        "active_folders": sorted(active_folders),
        "actual_folders": sorted(actual_folders),
        "missing_active_folders": missing,
        "stale_extra_folders": stale,
        "blockers": ",".join(blockers),
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_payload = _read_json(args.upload_review_packet_json)
    decision_payload = _read_json(args.upload_operator_decision_kit_json)
    post_native_payload = _read_json(args.post_native_scoring_scaffold_json)
    review_summary = _summary(review_payload)
    decision_summary = _summary(decision_payload)
    post_native_summary = _summary(post_native_payload)

    review_root = _text(review_summary.get("review_dir")) or "casp17/current_upload_review_packet"
    decision_root = _text(decision_summary.get("decision_dir")) or _common_parent_from_rows(
        _rows(decision_payload),
        "decision_packet_folder",
        "casp17/current_upload_operator_decision_kit",
    )
    post_native_root = _text(post_native_summary.get("scaffold_dir")) or "casp17/current_post_native_scoring_scaffold"

    rows = [
        _surface_row(
            "current_upload_review_packet",
            review_root,
            {_artifact(row.get("packet_folder")) for row in _rows(review_payload) if _text(row.get("packet_folder"))},
            _direct_child_dirs(review_root),
        ),
        _surface_row(
            "current_upload_operator_decision_kit",
            decision_root,
            {
                _artifact(row.get("decision_packet_folder"))
                for row in _rows(decision_payload)
                if _text(row.get("decision_packet_folder"))
            },
            _direct_child_dirs(decision_root),
        ),
        _surface_row(
            "current_post_native_scoring_scaffold",
            post_native_root,
            {
                _parent_folder(row.get("post_native_scoring_md"))
                for row in _rows(post_native_payload, "target_rows")
                if _text(row.get("post_native_scoring_md"))
            },
            _direct_child_dirs(post_native_root),
        ),
    ]
    rows = [row for row in rows if row["active_folder_count"] or row["actual_folder_count"]]
    blocked_rows = [row for row in rows if row["missing_active_folder_count"]]
    stale_rows = [row for row in rows if row["stale_extra_folder_count"] and not row["missing_active_folder_count"]]
    pass_rows = [row for row in rows if row["surface_status"] == "pass"]
    first_stale = stale_rows[0] if stale_rows else next((row for row in rows if row["stale_extra_folder_count"]), {})

    if not rows:
        status = "blocked_no_current_queue_surfaces"
    elif blocked_rows:
        status = "blocked_missing_active_generated_folder"
    elif stale_rows:
        status = "current_queue_rollover_hygiene_stale_generated_folders_retained"
    else:
        status = "current_queue_rollover_hygiene_pass"

    summary = {
        "packet_type": "casp17_current_queue_rollover_hygiene_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "surface_count": len(rows),
        "surface_pass_count": len(pass_rows),
        "surface_stale_count": len(stale_rows),
        "surface_blocked_count": len(blocked_rows),
        "active_folder_count": sum(int(row["active_folder_count"]) for row in rows),
        "actual_folder_count": sum(int(row["actual_folder_count"]) for row in rows),
        "missing_active_folder_count": sum(int(row["missing_active_folder_count"]) for row in rows),
        "stale_extra_folder_count": sum(int(row["stale_extra_folder_count"]) for row in rows),
        "first_stale_surface_id": _text(first_stale.get("surface_id")),
        "first_stale_extra_folder": _text(first_stale.get("first_stale_extra_folder")),
        "next_action": (
            "cleanup stale generated folders only after operator approval, or keep them retained but use active manifests "
            "as source of truth for upload/scoring work"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 current queue rollover generated folder hygiene.")
    parser.add_argument("--upload-review-packet-json", default=DEFAULT_UPLOAD_REVIEW_PACKET_JSON)
    parser.add_argument("--upload-operator-decision-kit-json", default=DEFAULT_UPLOAD_OPERATOR_DECISION_KIT_JSON)
    parser.add_argument("--post-native-scoring-scaffold-json", default=DEFAULT_POST_NATIVE_SCORING_SCAFFOLD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
