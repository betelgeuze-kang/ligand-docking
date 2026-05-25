#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_TARGET_WATCHLIST_CSV = "runs/casp17_target_watchlist_current.csv"
DEFAULT_DISCOVERY_JSON = "casp17/casp17_competitive_floor_target_identity_discovery_packet_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_native_candidate_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_native_candidate_packet_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_NATIVE_CANDIDATES.md"

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
ENTRY_URL_TEMPLATE = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
PDB_DOWNLOAD_URL_TEMPLATE = "https://files.rcsb.org/download/{pdb_id}.pdb"
QUERY_LABELS = ("exact", "relaxed")
PACKET_COLUMNS = [
    "target_id",
    "target_name",
    "candidate_status",
    "query_label",
    "query_text",
    "pdb_id",
    "rcsb_score",
    "struct_title",
    "initial_release_date",
    "experimental_method",
    "resolution_combined",
    "current_target_collision_ids",
    "current_target_collision_names",
    "target_entry_date",
    "target_qa_expiration",
    "download_url",
    "native_source_pdb_suggestion",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor native candidate packet only. It prepares and optionally executes compact RCSB "
    "candidate searches for operator review. It does not assert a native structure, clear no-leak provenance, copy "
    "native files into workorders, score native accuracy, mutate operator intake, or submit to CASP. Any RCSB hit "
    "must still pass operator no-leak/current-target review before use."
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


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PACKET_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _normalize_name(value: str) -> str:
    text = value.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bcomplex\b|\bchains?\b|\bprotein\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _relaxed_query(target_name: str) -> str:
    text = re.sub(r"\s*-\s*antibody\s+\S+.*$", "", target_name, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*complex.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\([^)]*\)", "", text)
    return re.sub(r"\s+", " ", text).strip() or target_name


def _target_name(row: dict[str, Any]) -> str:
    return _text(row.get("target_name") or row.get("description") or row.get("protein_name"))


def _current_targets(path_like: str | Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(path_like):
        target_id = _text(row.get("target_id")).upper()
        name = _target_name(row)
        if target_id and name:
            out[target_id] = dict(row)
    return out


def _watchlist(path_like: str | Path) -> dict[str, dict[str, str]]:
    return {
        _text(row.get("target_id")).upper(): row
        for row in _read_csv_rows(path_like)
        if _text(row.get("target_id"))
    }


def _find_current_collisions(
    target_id: str,
    target_name: str,
    current_rows: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    normalized = _normalize_name(target_name)
    collisions: list[dict[str, str]] = []
    if not normalized:
        return collisions
    for current_id, row in current_rows.items():
        if current_id == target_id:
            continue
        current_name = _target_name(row)
        if normalized and normalized == _normalize_name(current_name):
            collisions.append({"target_id": current_id, "target_name": current_name})
    return collisions


def _post_json(url: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 204:
            return {}
        raise
    if not raw.strip():
        return {}
    return json.loads(raw)


def _get_json(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def _rcsb_search(query_text: str, *, rows: int, timeout_seconds: int) -> list[dict[str, Any]]:
    payload = {
        "query": {"type": "terminal", "service": "full_text", "parameters": {"value": query_text}},
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": rows}},
    }
    data = _post_json(SEARCH_URL, payload, timeout_seconds=timeout_seconds)
    result_set = data.get("result_set") if isinstance(data, dict) else []
    return [row for row in result_set if isinstance(row, dict)] if isinstance(result_set, list) else []


def _rcsb_entry(pdb_id: str, *, timeout_seconds: int) -> dict[str, Any]:
    return _get_json(ENTRY_URL_TEMPLATE.format(pdb_id=pdb_id.upper()), timeout_seconds=timeout_seconds)


def _entry_title(entry: dict[str, Any]) -> str:
    struct = entry.get("struct")
    return _text(struct.get("title") if isinstance(struct, dict) else "")


def _entry_release_date(entry: dict[str, Any]) -> str:
    accession = entry.get("rcsb_accession_info")
    return _text(accession.get("initial_release_date") if isinstance(accession, dict) else "")[:10]


def _entry_methods(entry: dict[str, Any]) -> str:
    info = entry.get("exptl")
    if not isinstance(info, list):
        return ""
    methods = [_text(row.get("method")) for row in info if isinstance(row, dict)]
    return ";".join(method for method in methods if method)


def _entry_resolution(entry: dict[str, Any]) -> str:
    info = entry.get("rcsb_entry_info")
    values = info.get("resolution_combined") if isinstance(info, dict) else []
    if not isinstance(values, list):
        return ""
    return ";".join(str(value) for value in values if value is not None)


def _candidate_status(
    *,
    collisions: list[dict[str, str]],
    query_label: str,
    release_date: str,
    target_entry_date: str,
) -> tuple[str, list[str], str]:
    blockers: list[str] = []
    if collisions:
        blockers.append("current_target_name_collision")
    if query_label != "exact":
        blockers.append("relaxed_query_match_requires_operator_review")
    release = _date_or_none(release_date)
    entry = _date_or_none(target_entry_date)
    if release and entry and release <= entry:
        blockers.append("candidate_public_before_target_entry")
    if collisions:
        return (
            "blocked_current_target_collision",
            blockers,
            "do not use until operator proves this is not leakage from a current/open CASP17 target",
        )
    if release and entry and release <= entry:
        return (
            "blocked_public_before_target_entry",
            blockers,
            "reject as native unless operator provides an independent no-leak rationale",
        )
    if query_label != "exact":
        return (
            "review_only_relaxed_match",
            blockers,
            "inspect title/entities manually before considering as a native candidate",
        )
    return (
        "operator_review_required",
        blockers,
        "download candidate PDB, verify entities/native identity, then create no-leak evidence before intake",
    )


def _candidate_row(
    workorder_row: dict[str, Any],
    *,
    query_label: str,
    query_text: str,
    result: dict[str, Any],
    entry: dict[str, Any],
    collisions: list[dict[str, str]],
    watch_row: dict[str, str],
) -> dict[str, Any]:
    target_id = _text(workorder_row.get("target_id")).upper()
    target_name = _target_name(workorder_row)
    pdb_id = _text(result.get("identifier")).upper()
    release_date = _entry_release_date(entry)
    target_entry_date = _text(watch_row.get("entry_date"))
    status, blockers, next_action = _candidate_status(
        collisions=collisions,
        query_label=query_label,
        release_date=release_date,
        target_entry_date=target_entry_date,
    )
    return {
        "target_id": target_id,
        "target_name": target_name,
        "candidate_status": status,
        "query_label": query_label,
        "query_text": query_text,
        "pdb_id": pdb_id,
        "rcsb_score": result.get("score", ""),
        "struct_title": _entry_title(entry),
        "initial_release_date": release_date,
        "experimental_method": _entry_methods(entry),
        "resolution_combined": _entry_resolution(entry),
        "current_target_collision_ids": ";".join(row["target_id"] for row in collisions),
        "current_target_collision_names": ";".join(row["target_name"] for row in collisions),
        "target_entry_date": target_entry_date,
        "target_qa_expiration": _text(watch_row.get("qa_expiration")),
        "download_url": PDB_DOWNLOAD_URL_TEMPLATE.format(pdb_id=pdb_id),
        "native_source_pdb_suggestion": f"casp17/native_candidate_downloads/{target_id}/{pdb_id}.pdb" if pdb_id else "",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": next_action,
    }


def _no_candidate_row(
    workorder_row: dict[str, Any],
    *,
    query_text: str,
    collisions: list[dict[str, str]],
    watch_row: dict[str, str],
    fetch_enabled: bool,
) -> dict[str, Any]:
    target_id = _text(workorder_row.get("target_id")).upper()
    status = "no_rcsb_candidate_found" if fetch_enabled else "search_prepared"
    blockers = ["rcsb_candidate_missing"] if fetch_enabled else ["rcsb_fetch_not_enabled"]
    if collisions:
        blockers.append("current_target_name_collision")
    next_action = (
        "broaden RCSB/manual native search and document no-leak evidence"
        if fetch_enabled
        else "rerun with --fetch-rcsb to retrieve current RCSB candidate metadata"
    )
    return {
        "target_id": target_id,
        "target_name": _target_name(workorder_row),
        "candidate_status": status,
        "query_label": "prepared",
        "query_text": query_text,
        "pdb_id": "",
        "rcsb_score": "",
        "struct_title": "",
        "initial_release_date": "",
        "experimental_method": "",
        "resolution_combined": "",
        "current_target_collision_ids": ";".join(row["target_id"] for row in collisions),
        "current_target_collision_names": ";".join(row["target_name"] for row in collisions),
        "target_entry_date": _text(watch_row.get("entry_date")),
        "target_qa_expiration": _text(watch_row.get("qa_expiration")),
        "download_url": "",
        "native_source_pdb_suggestion": "",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": next_action,
    }


def _search_queries(target_name: str) -> list[tuple[str, str]]:
    exact = target_name.strip()
    relaxed = _relaxed_query(target_name)
    queries = [("exact", exact)]
    if relaxed and relaxed != exact:
        queries.append(("relaxed", relaxed))
    return [(label, query) for label, query in queries if query]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    workorder_rows = _rows(workorder_payload)
    current_rows = _current_targets(args.current_target_csv)
    watch = _watchlist(args.target_watchlist_csv)
    discovery_summary = _summary(_read_json(args.discovery_json))
    entry_cache: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    fetch_errors: list[str] = []
    for workorder_row in workorder_rows:
        target_id = _text(workorder_row.get("target_id")).upper()
        target_name = _target_name(workorder_row)
        collisions = _find_current_collisions(target_id, target_name, current_rows)
        watch_row = watch.get(target_id, {})
        target_rows: list[dict[str, Any]] = []
        for query_label, query_text in _search_queries(target_name):
            if not args.fetch_rcsb:
                continue
            try:
                results = _rcsb_search(query_text, rows=max(1, args.max_rcsb_results), timeout_seconds=args.timeout_seconds)
            except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                fetch_errors.append(f"{target_id}:{query_label}:{type(exc).__name__}")
                continue
            for result in results[: args.max_rcsb_results]:
                pdb_id = _text(result.get("identifier")).upper()
                if not pdb_id:
                    continue
                if pdb_id not in entry_cache:
                    try:
                        entry_cache[pdb_id] = _rcsb_entry(pdb_id, timeout_seconds=args.timeout_seconds)
                    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                        fetch_errors.append(f"{target_id}:{pdb_id}:{type(exc).__name__}")
                        entry_cache[pdb_id] = {}
                target_rows.append(
                    _candidate_row(
                        workorder_row,
                        query_label=query_label,
                        query_text=query_text,
                        result=result,
                        entry=entry_cache[pdb_id],
                        collisions=collisions,
                        watch_row=watch_row,
                    )
                )
        if not target_rows:
            prepared_query = "; ".join(query for _, query in _search_queries(target_name))
            target_rows.append(
                _no_candidate_row(
                    workorder_row,
                    query_text=prepared_query,
                    collisions=collisions,
                    watch_row=watch_row,
                    fetch_enabled=bool(args.fetch_rcsb),
                )
            )
        rows.extend(target_rows)
    statuses = [_text(row.get("candidate_status")) for row in rows]
    blocked_count = sum(1 for status in statuses if status.startswith("blocked_"))
    review_count = statuses.count("operator_review_required") + statuses.count("review_only_relaxed_match")
    no_candidate_count = statuses.count("no_rcsb_candidate_found")
    prepared_count = statuses.count("search_prepared")
    if not workorder_rows:
        packet_status = "missing_workorders"
    elif fetch_errors:
        packet_status = "fetch_errors"
    elif blocked_count or no_candidate_count or review_count:
        packet_status = "review_required"
    elif prepared_count:
        packet_status = "search_prepared"
    else:
        packet_status = "ready"
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_native_candidate_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "native_candidate_packet_status": packet_status,
        "fetch_rcsb": bool(args.fetch_rcsb),
        "workorder_json": _artifact(args.workorder_json),
        "current_target_csv": _artifact(args.current_target_csv),
        "target_watchlist_csv": _artifact(args.target_watchlist_csv),
        "discovery_json": _artifact(args.discovery_json),
        "discovery_status": _text(discovery_summary.get("target_identity_discovery_status")),
        "target_count": len({_text(row.get("target_id")).upper() for row in workorder_rows if _text(row.get("target_id"))}),
        "candidate_row_count": len(rows),
        "operator_review_required_count": statuses.count("operator_review_required"),
        "relaxed_review_count": statuses.count("review_only_relaxed_match"),
        "blocked_candidate_count": blocked_count,
        "current_target_collision_count": sum(1 for row in rows if _text(row.get("current_target_collision_ids"))),
        "no_candidate_target_count": no_candidate_count,
        "search_prepared_count": prepared_count,
        "fetch_error_count": len(fetch_errors),
        "fetch_errors": ";".join(fetch_errors),
        "first_open_target_id": _text(next((row.get("target_id") for row in rows if row.get("candidate_status") != "ready"), "")),
        "first_open_next_action": _text(next((row.get("next_action") for row in rows if row.get("candidate_status") != "ready"), "")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Native Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- native_candidate_packet_status: `{summary['native_candidate_packet_status']}`",
        f"- fetch_rcsb: `{summary['fetch_rcsb']}`",
        f"- targets/candidate rows: `{summary['target_count']}/{summary['candidate_row_count']}`",
        f"- operator/relaxed/blocked/no-candidate/prepared: `{summary['operator_review_required_count']}/{summary['relaxed_review_count']}/{summary['blocked_candidate_count']}/{summary['no_candidate_target_count']}/{summary['search_prepared_count']}`",
        f"- current-target collisions: `{summary['current_target_collision_count']}`",
        f"- fetch errors: `{summary['fetch_error_count']}` `{summary['fetch_errors'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Candidates",
        "",
        "| target | status | query | pdb | title | release | blockers | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['candidate_status']}` | `{row['query_label']}` "
            f"`{row['query_text']}` | `{row['pdb_id'] or '-'}` | {row['struct_title'] or '-'} | "
            f"`{row['initial_release_date'] or '-'}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing_workorders` | - | - | - | - | - | rebuild clearance workorders |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 clearance native candidate packet.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--target-watchlist-csv", default=DEFAULT_TARGET_WATCHLIST_CSV)
    parser.add_argument("--discovery-json", default=DEFAULT_DISCOVERY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--fetch-rcsb", action="store_true")
    parser.add_argument("--max-rcsb-results", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
