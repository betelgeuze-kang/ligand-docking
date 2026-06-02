#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_PACKAGE_PREFLIGHT_JSON = "casp17/casp17_current_submission_package_preflight_current.json"
DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_current_submission_deadline_guard_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_submission_deadline_guard_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_SUBMISSION_DEADLINE_GUARD.md"


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


def _date(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _today(value: str) -> dt.date:
    parsed = _date(value)
    return parsed if parsed is not None else dt.datetime.now().astimezone().date()


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "protein_name",
        "lane",
        "deadline_guard_status",
        "package_preflight_status",
        "human_expiration",
        "qa_expiration",
        "days_to_human_expiration",
        "days_to_qa_expiration",
        "human_deadline_open",
        "qa_deadline_open",
        "candidate_pdb",
        "blockers",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Submission Deadline Guard",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- current_date: `{summary['current_date']}`",
        f"- deadline_guard_status: `{summary['deadline_guard_status']}`",
        f"- upload-window ready/blocked/total: `{summary['upload_window_ready_count']}/{summary['deadline_blocked_count']}/{summary['target_count']}`",
        f"- expired/expiring-today/future: `{summary['human_expired_count']}/{summary['human_expiring_today_count']}/{summary['human_future_count']}`",
        f"- QA open/expired/unknown: `{summary['qa_open_count']}/{summary['qa_expired_count']}/{summary['qa_unknown_count']}`",
        f"- package preflight: `{summary['package_preflight_status']}` ready/blocked/total `{summary['package_ready_count']}/{summary['package_blocked_count']}/{summary['package_target_count']}`",
        f"- watchlist stale: `{summary['watchlist_stale']}` watchlist_today `{summary['watchlist_today'] or '-'}` stale_days `{summary['watchlist_stale_days']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_reason'] or '-'}`",
        f"- nearest open human deadline: `{summary['nearest_open_target_id'] or '-'}` `{summary['nearest_open_human_expiration'] or '-'}` days `{summary['nearest_open_days_to_human_expiration']}`",
        "",
        "## Rows",
        "",
        "| target | protein | status | human | days | QA | package | candidate | blockers |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['protein_name']} | `{row['deadline_guard_status']}` | "
            f"`{row['human_expiration'] or '-'}` | {row['days_to_human_expiration']} | "
            f"`{row['qa_expiration'] or '-'}` | `{row['package_preflight_status']}` | "
            f"`{row['candidate_pdb'] or '-'}` | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `missing` | - | 0 | - | - | - | no target rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _package_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in _rows(payload)}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    today = _today(args.current_date)
    target_payload = _read_json(args.target_model_folders_json)
    package_payload = _read_json(args.package_preflight_json)
    watchlist_payload = _read_json(args.target_watchlist_json)
    package_summary = _summary(package_payload)
    watchlist_summary = _summary(watchlist_payload)
    package_rows = _package_by_target(package_payload)

    watchlist_today = _date(watchlist_summary.get("today"))
    watchlist_stale_days = (today - watchlist_today).days if watchlist_today is not None else 0
    watchlist_stale = watchlist_today is not None and watchlist_today < today

    rows: list[dict[str, Any]] = []
    for target_row in sorted(_rows(target_payload), key=lambda row: _text(row.get("target_id"))):
        target_id = _text(target_row.get("target_id")).upper()
        package_row = package_rows.get(target_id, {})
        human_expiration = _date(target_row.get("human_expiration"))
        qa_expiration = _date(target_row.get("qa_expiration"))
        days_to_human = (human_expiration - today).days if human_expiration is not None else 0
        days_to_qa = (qa_expiration - today).days if qa_expiration is not None else 0
        human_open = human_expiration is not None and days_to_human >= 0
        qa_open = qa_expiration is not None and days_to_qa >= 0
        package_status = _text(package_row.get("package_preflight_status")) or "missing"
        blockers: list[str] = []

        if not target_id:
            blockers.append("target_id_missing")
        if package_status != "ready":
            blockers.append("package_preflight_not_ready")
        if human_expiration is None:
            blockers.append("human_expiration_missing")
        elif not human_open:
            blockers.append("human_submission_deadline_expired")
        if qa_expiration is None:
            blockers.append("qa_expiration_missing")

        if blockers:
            if "human_submission_deadline_expired" in blockers:
                row_status = "blocked_human_deadline_expired"
            elif package_status != "ready":
                row_status = "blocked_package_preflight"
            else:
                row_status = "blocked_deadline_metadata"
        elif days_to_human == 0:
            row_status = "ready_expiring_today"
        elif days_to_human <= 2:
            row_status = "ready_expiring_soon"
        else:
            row_status = "ready_future_window"

        rows.append(
            {
                "target_id": target_id,
                "protein_name": _text(target_row.get("protein_name")),
                "lane": _text(target_row.get("lane")),
                "deadline_guard_status": row_status,
                "package_preflight_status": package_status,
                "human_expiration": human_expiration.isoformat() if human_expiration else "",
                "qa_expiration": qa_expiration.isoformat() if qa_expiration else "",
                "days_to_human_expiration": days_to_human,
                "days_to_qa_expiration": days_to_qa,
                "human_deadline_open": human_open,
                "qa_deadline_open": qa_open,
                "candidate_pdb": _text(package_row.get("candidate_pdb")),
                "blockers": ";".join(dict.fromkeys(blockers)),
            }
        )

    upload_ready_count = sum(1 for row in rows if row["deadline_guard_status"].startswith("ready_"))
    deadline_blocked_count = len(rows) - upload_ready_count
    expired_rows = [row for row in rows if "human_submission_deadline_expired" in row["blockers"]]
    open_rows = [row for row in rows if row["human_deadline_open"]]
    open_rows.sort(key=lambda row: (row["days_to_human_expiration"], row["target_id"]))
    first_blocked = expired_rows[0] if expired_rows else next((row for row in rows if row["blockers"]), {})
    nearest_open = open_rows[0] if open_rows else {}
    package_target_count = _int(package_summary.get("target_count"))
    package_ready_count = _int(package_summary.get("ready_count"))
    package_blocked_count = _int(package_summary.get("blocked_count"))

    if not rows:
        guard_status = "missing_targets"
    elif deadline_blocked_count == 0:
        guard_status = "current_upload_window_ready"
    elif upload_ready_count > 0:
        guard_status = "partial_current_upload_window_ready"
    else:
        guard_status = "blocked_no_current_upload_window"

    summary = {
        "packet_type": "casp17_current_submission_deadline_guard",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_date": today.isoformat(),
        "deadline_guard_status": guard_status,
        "target_count": len(rows),
        "upload_window_ready_count": upload_ready_count,
        "deadline_blocked_count": deadline_blocked_count,
        "human_expired_count": len(expired_rows),
        "human_expiring_today_count": sum(1 for row in rows if row["days_to_human_expiration"] == 0),
        "human_future_count": sum(1 for row in rows if row["days_to_human_expiration"] > 0),
        "qa_open_count": sum(1 for row in rows if row["qa_deadline_open"]),
        "qa_expired_count": sum(1 for row in rows if row["qa_expiration"] and not row["qa_deadline_open"]),
        "qa_unknown_count": sum(1 for row in rows if not row["qa_expiration"]),
        "package_preflight_status": _text(package_summary.get("package_preflight_status")),
        "package_ready_count": package_ready_count,
        "package_blocked_count": package_blocked_count,
        "package_target_count": package_target_count,
        "watchlist_today": watchlist_today.isoformat() if watchlist_today else "",
        "watchlist_stale": watchlist_stale,
        "watchlist_stale_days": max(0, watchlist_stale_days),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_reason": _text(first_blocked.get("blockers")).split(";")[0] if first_blocked else "",
        "nearest_open_target_id": _text(nearest_open.get("target_id")),
        "nearest_open_human_expiration": _text(nearest_open.get("human_expiration")),
        "nearest_open_days_to_human_expiration": _int(nearest_open.get("days_to_human_expiration")),
        "next_action": (
            "submit or archive only targets whose human deadline remains open; move expired target files into "
            "late-retrospective review rather than current upload readiness"
        ),
        "claim_boundary": (
            "CASP17 current submission deadline guard only. It recomputes open human/QA windows from local target "
            "dates and links them to package preflight state; it is not a portal submission, native-accuracy claim, "
            "or official CASP deadline authority."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build current-date deadline guard for CASP17 local TS package candidates.")
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--package-preflight-json", default=DEFAULT_PACKAGE_PREFLIGHT_JSON)
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--current-date", default="")
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
