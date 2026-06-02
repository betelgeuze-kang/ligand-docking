#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import re
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PACKAGE_PREFLIGHT_JSON = "casp17/casp17_current_submission_package_preflight_current.json"
DEFAULT_DEADLINE_GUARD_JSON = "casp17/casp17_current_submission_deadline_guard_current.json"
DEFAULT_OFFICIAL_TARGETLIST_URL = "https://predictioncenter.org/casp17/targetlist.cgi?type=csv"
DEFAULT_OFFICIAL_TARGETLIST_SNAPSHOT_CSV = "casp17/casp17_official_targetlist_snapshot_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_queue_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_QUEUE.md"


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
    if not text or text == "-":
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _today(value: str) -> dt.date:
    parsed = _date(value)
    return parsed if parsed is not None else dt.datetime.now().astimezone().date()


def _clean_description(value: Any) -> str:
    text = html.unescape(_text(value))
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def _normalize_official_csv_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def _fetch_official_csv(args: argparse.Namespace) -> tuple[str, str]:
    source_path = _text(args.official_targetlist_csv)
    if source_path:
        path = _resolve(source_path)
        return _normalize_official_csv_text(path.read_text(encoding="utf-8")), f"file:{_artifact(path)}"
    with urllib.request.urlopen(args.official_targetlist_url, timeout=int(args.fetch_timeout_seconds)) as response:
        text = _normalize_official_csv_text(response.read().decode("utf-8", errors="replace"))
    snapshot = _resolve(args.official_targetlist_snapshot_csv)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(text, encoding="utf-8")
    return text, args.official_targetlist_url


def _official_rows(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []
    return [dict(row) for row in csv.DictReader(io.StringIO(text), delimiter=";")]


def _official_by_target(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_text(row.get("Target")).upper(): row for row in rows if _text(row.get("Target"))}


def _phase_fallback_target_id(target_id: str) -> str:
    if len(target_id) > 2 and target_id[0] in {"H", "T", "R", "D", "M", "L"} and target_id[1] in {"2", "3"}:
        return target_id[0] + "1" + target_id[2:]
    return ""


def _match_official(target_id: str, by_target: dict[str, dict[str, str]]) -> tuple[str, dict[str, str]]:
    if target_id in by_target:
        return "direct", by_target[target_id]
    fallback = _phase_fallback_target_id(target_id)
    if fallback and fallback in by_target:
        return "phase_mapped_to_primary_target", by_target[fallback]
    return "missing", {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "queue_rank",
        "target_id",
        "official_target_id",
        "official_match_status",
        "upload_queue_status",
        "action_class",
        "protein_name",
        "official_description",
        "human_expiration",
        "official_human_expiration",
        "days_to_official_human_expiration",
        "qa_expiration",
        "official_qa_expiration",
        "official_cancellation_date",
        "package_preflight_status",
        "deadline_guard_status",
        "candidate_pdb",
        "candidate_sha256",
        "blockers",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Upload Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- current_date: `{summary['current_date']}`",
        f"- upload_queue_status: `{summary['upload_queue_status']}`",
        f"- upload ready/blocked/total: `{summary['upload_ready_count']}/{summary['blocked_count']}/{summary['target_count']}`",
        f"- ready today/soon/future: `{summary['ready_today_count']}/{summary['ready_soon_count']}/{summary['ready_future_count']}`",
        f"- official matches direct/mapped/missing: `{summary['official_direct_match_count']}/{summary['official_phase_mapped_count']}/{summary['official_missing_count']}`",
        f"- official cancelled/expired/local-date-mismatch: `{summary['official_cancelled_count']}/{summary['official_expired_count']}/{summary['official_local_deadline_mismatch_count']}`",
        f"- package ready/blocked/total: `{summary['package_ready_count']}/{summary['package_blocked_count']}/{summary['package_target_count']}`",
        f"- deadline guard ready/blocked/total: `{summary['deadline_guard_ready_count']}/{summary['deadline_guard_blocked_count']}/{summary['deadline_guard_target_count']}`",
        f"- official source: `{summary['official_source']}`",
        f"- official snapshot: `{summary['official_snapshot_csv']}`",
        f"- first upload: `{summary['first_upload_target_id'] or '-'}` `{summary['first_upload_human_expiration'] or '-'}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_reason'] or '-'}`",
        "",
        "## Upload Queue",
        "",
        "| rank | target | official | status | action | human | days | candidate | blockers |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['target_id']}` | `{row['official_target_id'] or '-'}` | "
            f"`{row['upload_queue_status']}` | `{row['action_class']}` | "
            f"`{row['official_human_expiration'] or row['human_expiration'] or '-'}` | "
            f"{row['days_to_official_human_expiration']} | `{row['candidate_pdb'] or '-'}` | "
            f"{row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | `missing` | - | - | 0 | - | no rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    today = _today(args.current_date)
    package_payload = _read_json(args.package_preflight_json)
    deadline_payload = _read_json(args.deadline_guard_json)
    package_summary = _summary(package_payload)
    deadline_summary = _summary(deadline_payload)
    official_text, official_source = _fetch_official_csv(args)
    official_rows = _official_rows(official_text)
    official_by_target = _official_by_target(official_rows)
    package_by_target = {_text(row.get("target_id")).upper(): row for row in _rows(package_payload)}

    rows: list[dict[str, Any]] = []
    for deadline_row in _rows(deadline_payload):
        target_id = _text(deadline_row.get("target_id")).upper()
        package_row = package_by_target.get(target_id, {})
        official_match_status, official = _match_official(target_id, official_by_target)
        official_target_id = _text(official.get("Target")).upper()
        official_human_expiration = _date(official.get("Human Exp."))
        official_qa_expiration = _date(official.get("QA Exp."))
        official_cancellation = _text(official.get("Cancellation Date"))
        official_description = _clean_description(official.get("Description"))
        official_cancelled = official_cancellation not in {"", "-"} or bool(
            re.search(r"\bcancell?ed\b", official_description, flags=re.IGNORECASE)
        )
        official_days = (
            (official_human_expiration - today).days
            if official_human_expiration is not None
            else _int(deadline_row.get("days_to_human_expiration"))
        )
        package_status = _text(package_row.get("package_preflight_status")) or "missing"
        deadline_status = _text(deadline_row.get("deadline_guard_status"))
        local_human = _text(deadline_row.get("human_expiration"))
        official_human_text = official_human_expiration.isoformat() if official_human_expiration else ""
        blockers: list[str] = []

        if package_status != "ready":
            blockers.append("package_preflight_not_ready")
        if not deadline_status.startswith("ready_"):
            blockers.append(_text(deadline_row.get("blockers")).split(";")[0] or "deadline_guard_not_ready")
        if official_match_status == "missing":
            blockers.append("official_target_missing")
        if official_cancelled:
            blockers.append("official_target_cancelled")
        if official_human_expiration is None:
            blockers.append("official_human_expiration_missing")
        elif official_days < 0:
            blockers.append("official_human_deadline_expired")
        if local_human and official_human_text and local_human != official_human_text:
            blockers.append("local_official_human_deadline_mismatch")

        if blockers:
            if "official_target_cancelled" in blockers:
                queue_status = "blocked_official_cancelled"
                action_class = "do_not_upload_cancelled_target"
            elif "official_human_deadline_expired" in blockers:
                queue_status = "blocked_official_deadline_expired"
                action_class = "move_to_late_retrospective_review"
            elif "package_preflight_not_ready" in blockers:
                queue_status = "blocked_package_preflight"
                action_class = "repair_package_preflight"
            else:
                queue_status = "blocked_official_or_deadline_review"
                action_class = "manual_deadline_review"
        elif official_days == 0:
            queue_status = "upload_ready_expiring_today"
            action_class = "upload_today_if_operator_approved"
        elif official_days <= 2:
            queue_status = "upload_ready_expiring_soon"
            action_class = "upload_next_if_operator_approved"
        else:
            queue_status = "upload_ready_future_window"
            action_class = "stage_for_future_upload"

        rows.append(
            {
                "queue_rank": 0,
                "target_id": target_id,
                "official_target_id": official_target_id,
                "official_match_status": official_match_status,
                "upload_queue_status": queue_status,
                "action_class": action_class,
                "protein_name": _text(deadline_row.get("protein_name")),
                "official_description": official_description,
                "human_expiration": local_human,
                "official_human_expiration": official_human_text,
                "days_to_official_human_expiration": official_days,
                "qa_expiration": _text(deadline_row.get("qa_expiration")),
                "official_qa_expiration": official_qa_expiration.isoformat() if official_qa_expiration else "",
                "official_cancellation_date": official_cancellation,
                "package_preflight_status": package_status,
                "deadline_guard_status": deadline_status,
                "candidate_pdb": _text(package_row.get("candidate_pdb")),
                "candidate_sha256": _text(package_row.get("candidate_sha256")),
                "blockers": ";".join(dict.fromkeys(blockers)),
            }
        )

    ready_rows = [row for row in rows if row["upload_queue_status"].startswith("upload_ready_")]
    ready_rows.sort(key=lambda row: (row["days_to_official_human_expiration"], row["target_id"]))
    rank_by_target = {row["target_id"]: index for index, row in enumerate(ready_rows, start=1)}
    for row in rows:
        row["queue_rank"] = rank_by_target.get(row["target_id"], 0)
    rows.sort(key=lambda row: (row["queue_rank"] == 0, row["queue_rank"] or 9999, row["target_id"]))

    blocked_rows = [row for row in rows if not row["upload_queue_status"].startswith("upload_ready_")]
    first_upload = ready_rows[0] if ready_rows else {}
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_current_upload_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_date": today.isoformat(),
        "upload_queue_status": (
            "official_verified_current_upload_queue_partial"
            if ready_rows and blocked_rows
            else (
                "official_verified_current_upload_queue_ready"
                if ready_rows
                else "blocked_no_official_verified_upload_ready_targets"
            )
        ),
        "target_count": len(rows),
        "upload_ready_count": len(ready_rows),
        "blocked_count": len(blocked_rows),
        "ready_today_count": sum(1 for row in ready_rows if row["days_to_official_human_expiration"] == 0),
        "ready_soon_count": sum(1 for row in ready_rows if 0 < row["days_to_official_human_expiration"] <= 2),
        "ready_future_count": sum(1 for row in ready_rows if row["days_to_official_human_expiration"] > 2),
        "official_target_count": len(official_rows),
        "official_direct_match_count": sum(1 for row in rows if row["official_match_status"] == "direct"),
        "official_phase_mapped_count": sum(1 for row in rows if row["official_match_status"] == "phase_mapped_to_primary_target"),
        "official_missing_count": sum(1 for row in rows if row["official_match_status"] == "missing"),
        "official_cancelled_count": sum(1 for row in rows if "official_target_cancelled" in row["blockers"]),
        "official_expired_count": sum(1 for row in rows if "official_human_deadline_expired" in row["blockers"]),
        "official_local_deadline_mismatch_count": sum(1 for row in rows if "local_official_human_deadline_mismatch" in row["blockers"]),
        "package_preflight_status": _text(package_summary.get("package_preflight_status")),
        "package_ready_count": _int(package_summary.get("ready_count")),
        "package_blocked_count": _int(package_summary.get("blocked_count")),
        "package_target_count": _int(package_summary.get("target_count")),
        "deadline_guard_status": _text(deadline_summary.get("deadline_guard_status")),
        "deadline_guard_ready_count": _int(deadline_summary.get("upload_window_ready_count")),
        "deadline_guard_blocked_count": _int(deadline_summary.get("deadline_blocked_count")),
        "deadline_guard_target_count": _int(deadline_summary.get("target_count")),
        "official_source": official_source,
        "official_snapshot_csv": _artifact(args.official_targetlist_snapshot_csv),
        "first_upload_target_id": _text(first_upload.get("target_id")),
        "first_upload_human_expiration": _text(first_upload.get("official_human_expiration")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_reason": _text(first_blocked.get("blockers")).split(";")[0] if first_blocked else "",
        "next_action": (
            "work queue_rank > 0 only, starting with expiring-today targets; do not upload cancelled, expired, "
            "or official/local deadline-mismatched rows without operator review"
        ),
        "claim_boundary": (
            "CASP17 current upload queue only. It combines local package/deadline guards with the official CASP17 "
            "targetlist CSV for upload triage; it is not a CASP portal submission, not native-accuracy evidence, "
            "and not strict-blind competitive proof."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an official-targetlist-aware current CASP17 upload queue.")
    parser.add_argument("--package-preflight-json", default=DEFAULT_PACKAGE_PREFLIGHT_JSON)
    parser.add_argument("--deadline-guard-json", default=DEFAULT_DEADLINE_GUARD_JSON)
    parser.add_argument("--official-targetlist-url", default=DEFAULT_OFFICIAL_TARGETLIST_URL)
    parser.add_argument("--official-targetlist-csv", default="")
    parser.add_argument("--official-targetlist-snapshot-csv", default=DEFAULT_OFFICIAL_TARGETLIST_SNAPSHOT_CSV)
    parser.add_argument("--fetch-timeout-seconds", default="30")
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
