#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCAN_ROOTS = "data/internal_structures,data/internal_structures_refined"
DEFAULT_SOURCE_REQUEST_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_UNKNOWN_TRIAGE_JSON = "casp17/casp17_strict_blind_unknown_candidate_triage_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_internal_like_source_review_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_internal_like_source_review_current.csv"
DEFAULT_TARGET_CSV = "casp17/casp17_strict_blind_internal_like_source_review_targets_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_INTERNAL_LIKE_SOURCE_REVIEW.md"

STRUCTURE_EXTENSIONS = {".pdb", ".cif", ".mmcif"}
ROW_COLUMNS = [
    "review_id",
    "review_status",
    "candidate_path",
    "source_root",
    "target_label",
    "mapped_target_id",
    "request_id",
    "candidate_scope",
    "prediction_date_from_path",
    "native_release_date",
    "prediction_before_native",
    "chronology_days",
    "atom_count",
    "source_request_current_prediction_pdb",
    "current_native_pdb",
    "native_authority_ref",
    "blockers",
    "next_action",
]
TARGET_COLUMNS = [
    "target_label",
    "mapped_target_id",
    "request_id",
    "candidate_scope",
    "native_release_date",
    "candidate_count",
    "pre_native_count",
    "post_native_count",
    "same_day_count",
    "prediction_date_missing_count",
    "unmapped_count",
    "earliest_prediction_date",
    "latest_prediction_date",
    "first_candidate_path",
    "target_review_status",
    "next_action",
]


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
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")


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
    resolved = list(fieldnames)
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _parse_date(value: str) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date_text(value: dt.date | None) -> str:
    return value.isoformat() if value else ""


def _prediction_label(path: Path) -> str:
    stem = path.stem
    if stem.startswith("visual_post_"):
        stem = stem[len("visual_post_") :]
    if not stem.startswith("internal_post_") or "_sample" not in stem:
        return ""
    return _slug(stem[len("internal_post_") : stem.index("_sample")])


def _prediction_date_from_path(path: Path) -> str:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", str(path).replace("\\", "/"))
    if not match:
        return ""
    return match.group(1) if _parse_date(match.group(1)) else ""


def _atom_count(path_like: Path) -> int:
    path = _resolve(path_like)
    count = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    count += 1
    except OSError:
        return 0
    return count


def _scan_roots(value: str) -> list[Path]:
    roots: list[Path] = []
    for item in value.split(","):
        text = item.strip()
        if text:
            roots.append(_resolve(text))
    return roots


def _structure_files(roots: list[Path]) -> list[tuple[Path, Path]]:
    files: list[tuple[Path, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in STRUCTURE_EXTENSIONS:
                files.append((root, path))
    return sorted(files, key=lambda item: _artifact(item[1]))


def _target_lookup(source_request_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in _rows(source_request_payload):
        if _text(row.get("candidate_scope")) != "monomer":
            continue
        labels = set()
        current_prediction = _text(row.get("current_prediction_pdb"))
        if current_prediction:
            labels.add(_prediction_label(Path(current_prediction)))
        candidate_target_id = _text(row.get("candidate_target_id"))
        if candidate_target_id.startswith("HIST_") and not candidate_target_id.startswith("HIST_COMPLEX_"):
            labels.add(_slug(candidate_target_id[len("HIST_") :]))
        for label in labels:
            if label:
                lookup[label] = row
    return lookup


def _review_status(
    *,
    label: str,
    target: dict[str, Any] | None,
    prediction_date: dt.date | None,
    native_date: dt.date | None,
) -> tuple[str, str, str, str, int | str]:
    blockers: list[str] = []
    if not label:
        blockers.append("target_label_unparsed")
        return (
            "blocked_target_label_unparsed",
            "parse candidate filename into an internal_post target label before source-gate review",
            ",".join(blockers),
            "false",
            "",
        )
    if target is None:
        blockers.append("source_request_target_mapping_missing")
        return (
            "blocked_source_request_target_mapping_missing",
            "map this internal-like file to a historical source request row before chronology review",
            ",".join(blockers),
            "false",
            "",
        )
    if prediction_date is None:
        blockers.append("prediction_date_from_path_missing")
    if native_date is None:
        blockers.append("native_release_date_missing")
    if blockers:
        return (
            "blocked_chronology_date_missing",
            "attach a prediction date and authoritative native release date before source-gate review",
            ",".join(blockers),
            "false",
            "",
        )
    chronology_days = (native_date - prediction_date).days
    if prediction_date < native_date:
        blockers.extend(["no_leak_evidence_required", "operator_clearance_required"])
        return (
            "pre_native_candidate_operator_review_required",
            "attach no-leak evidence and operator clearance before any source-gate promotion",
            ",".join(blockers),
            "true",
            chronology_days,
        )
    if prediction_date == native_date:
        blockers.append("same_day_timestamp_required")
        return (
            "blocked_same_day_timestamp_required",
            "attach a timestamp proving prediction creation before native release time",
            ",".join(blockers),
            "false",
            chronology_days,
        )
    blockers.append("prediction_not_before_native")
    return (
        "blocked_post_native_internal_candidate",
        "do not use this internal-like file for strict-blind proof; attach a pre-native replacement source",
        ",".join(blockers),
        "false",
        chronology_days,
    )


def _build_rows(roots: list[Path], target_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (root, path) in enumerate(_structure_files(roots), start=1):
        label = _prediction_label(path)
        target = target_lookup.get(label)
        prediction_date = _parse_date(_prediction_date_from_path(path))
        native_date = _parse_date(_text(target.get("native_release_date")) if target else "")
        status, next_action, blockers, before_native, chronology_days = _review_status(
            label=label,
            target=target,
            prediction_date=prediction_date,
            native_date=native_date,
        )
        rows.append(
            {
                "review_id": f"internal_like_source_review_{index:03d}",
                "review_status": status,
                "candidate_path": _artifact(path),
                "source_root": _artifact(root),
                "target_label": label,
                "mapped_target_id": _text(target.get("candidate_target_id")) if target else "",
                "request_id": _text(target.get("request_id")) if target else "",
                "candidate_scope": _text(target.get("candidate_scope")) if target else "",
                "prediction_date_from_path": _date_text(prediction_date),
                "native_release_date": _date_text(native_date),
                "prediction_before_native": before_native,
                "chronology_days": chronology_days,
                "atom_count": _atom_count(path),
                "source_request_current_prediction_pdb": _text(target.get("current_prediction_pdb")) if target else "",
                "current_native_pdb": _text(target.get("current_native_pdb")) if target else "",
                "native_authority_ref": _text(target.get("native_authority_ref")) if target else "",
                "blockers": blockers,
                "next_action": next_action,
            }
        )
    return rows


def _target_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = _text(row.get("mapped_target_id")) or f"unmapped:{_text(row.get('target_label')) or row['review_id']}"
        grouped.setdefault(key, []).append(row)
    target_rows: list[dict[str, Any]] = []
    for key in sorted(grouped):
        items = grouped[key]
        dates = sorted(_text(row.get("prediction_date_from_path")) for row in items if _text(row.get("prediction_date_from_path")))
        pre_native = sum(1 for row in items if row["review_status"] == "pre_native_candidate_operator_review_required")
        post_native = sum(1 for row in items if row["review_status"] == "blocked_post_native_internal_candidate")
        same_day = sum(1 for row in items if row["review_status"] == "blocked_same_day_timestamp_required")
        missing_date = sum(1 for row in items if row["review_status"] == "blocked_chronology_date_missing")
        unmapped = sum(1 for row in items if not _text(row.get("mapped_target_id")))
        if pre_native:
            status = "target_has_pre_native_candidates_requiring_no_leak_review"
            next_action = "review earliest pre-native candidate evidence and no-leak provenance"
        elif post_native == len(items):
            status = "target_all_internal_like_candidates_post_native"
            next_action = "replace with a different pre-native internal prediction source"
        elif unmapped:
            status = "target_mapping_required"
            next_action = "map candidate target labels to historical source request rows"
        else:
            status = "target_chronology_review_required"
            next_action = "complete missing date or timestamp evidence"
        first = items[0]
        target_rows.append(
            {
                "target_label": _text(first.get("target_label")),
                "mapped_target_id": _text(first.get("mapped_target_id")),
                "request_id": _text(first.get("request_id")),
                "candidate_scope": _text(first.get("candidate_scope")),
                "native_release_date": _text(first.get("native_release_date")),
                "candidate_count": len(items),
                "pre_native_count": pre_native,
                "post_native_count": post_native,
                "same_day_count": same_day,
                "prediction_date_missing_count": missing_date,
                "unmapped_count": unmapped,
                "earliest_prediction_date": dates[0] if dates else "",
                "latest_prediction_date": dates[-1] if dates else "",
                "first_candidate_path": _text(first.get("candidate_path")),
                "target_review_status": status,
                "next_action": next_action,
            }
        )
    return target_rows


def _status(rows: list[dict[str, Any]], target_rows: list[dict[str, Any]], count_match: bool) -> str:
    if not rows:
        return "strict_blind_internal_like_source_review_no_candidates"
    if not count_match:
        return "strict_blind_internal_like_source_review_count_mismatch"
    if any(row["review_status"] == "pre_native_candidate_operator_review_required" for row in rows):
        return "strict_blind_internal_like_source_review_pre_native_candidates_need_no_leak_review"
    if target_rows and all(row["target_review_status"] == "target_all_internal_like_candidates_post_native" for row in target_rows):
        return "strict_blind_internal_like_source_review_all_post_native"
    return "strict_blind_internal_like_source_review_operator_review_required"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_request_payload = _read_json(args.source_request_packet_json)
    source_request_summary = _summary(source_request_payload)
    unknown_triage_summary = _summary(_read_json(args.unknown_triage_json))
    roots = _scan_roots(args.scan_roots)
    rows = _build_rows(roots, _target_lookup(source_request_payload))
    target_rows = _target_rows(rows)
    triage_internal_like_count = _int(unknown_triage_summary.get("internal_like_review_count"))
    count_match = triage_internal_like_count == len(rows)
    pre_native = sum(1 for row in rows if row["review_status"] == "pre_native_candidate_operator_review_required")
    post_native = sum(1 for row in rows if row["review_status"] == "blocked_post_native_internal_candidate")
    same_day = sum(1 for row in rows if row["review_status"] == "blocked_same_day_timestamp_required")
    missing_date = sum(1 for row in rows if row["review_status"] == "blocked_chronology_date_missing")
    unmapped = sum(1 for row in rows if row["review_status"] == "blocked_source_request_target_mapping_missing")
    mapped = sum(1 for row in rows if _text(row.get("mapped_target_id")))
    dates = sorted(_text(row.get("prediction_date_from_path")) for row in rows if _text(row.get("prediction_date_from_path")))
    first_blocked = next((row for row in rows if row["review_status"] != "pre_native_candidate_operator_review_required"), rows[0] if rows else {})
    claim_boundary = (
        "CASP17 strict-blind internal-like source review only. It uses durable path dates and existing "
        "source-request native release dates to reject post-native local artifacts before source-gate use. "
        "It does not use filesystem mtime, does not approve no-leak provenance, and does not promote any "
        "candidate into strict-blind proof."
    )
    summary = {
        "packet_type": "casp17_strict_blind_internal_like_source_review",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "internal_like_source_review_status": _status(rows, target_rows, count_match),
        "scan_roots": ",".join(_artifact(root) for root in roots),
        "source_request_packet_status": _text(source_request_summary.get("source_request_packet_status")),
        "triage_internal_like_count": triage_internal_like_count,
        "triage_count_match": str(count_match),
        "internal_like_candidate_count": len(rows),
        "mapped_candidate_count": mapped,
        "unmapped_candidate_count": unmapped,
        "pre_native_candidate_count": pre_native,
        "same_day_timestamp_required_count": same_day,
        "post_native_blocked_count": post_native,
        "prediction_date_missing_count": missing_date,
        "promotion_ready_count": 0,
        "target_count": len(target_rows),
        "target_all_post_native_count": sum(
            1 for row in target_rows if row["target_review_status"] == "target_all_internal_like_candidates_post_native"
        ),
        "target_pre_native_candidate_count": sum(
            1 for row in target_rows if row["target_review_status"] == "target_has_pre_native_candidates_requiring_no_leak_review"
        ),
        "earliest_prediction_date": dates[0] if dates else "",
        "latest_prediction_date": dates[-1] if dates else "",
        "first_blocked_candidate_path": _text(first_blocked.get("candidate_path")),
        "first_blocked_target_id": _text(first_blocked.get("mapped_target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "target_rollup_csv": _artifact(args.target_csv),
        "next_action": (
            "treat these internal-like files as post-native blockers; source requests still need a different "
            "pre-native internal prediction artifact with no-leak evidence"
            if rows and pre_native == 0 and post_native == len(rows)
            else "review pre-native-looking rows only after no-leak evidence and operator clearance are attached"
        ),
        "claim_boundary": claim_boundary,
    }
    return {"summary": summary, "rows": rows, "target_rows": target_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Internal-Like Source Review",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['internal_like_source_review_status']}`",
        f"- candidates/triage-match: `{summary['internal_like_candidate_count']}/{summary['triage_internal_like_count']}` `{summary['triage_count_match']}`",
        f"- mapped/pre-native/post-native/same-day/missing/unmapped: `{summary['mapped_candidate_count']}/{summary['pre_native_candidate_count']}/{summary['post_native_blocked_count']}/{summary['same_day_timestamp_required_count']}/{summary['prediction_date_missing_count']}/{summary['unmapped_candidate_count']}`",
        f"- targets/all-post-native/pre-native-targets: `{summary['target_count']}/{summary['target_all_post_native_count']}/{summary['target_pre_native_candidate_count']}`",
        f"- prediction date range: `{summary['earliest_prediction_date'] or '-'}` to `{summary['latest_prediction_date'] or '-'}`",
        f"- first blocker: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}` `{summary['first_blocked_candidate_path'] or '-'}`",
        "",
        "## Target Rollup",
        "",
        "| target | candidates | pre-native | post-native | date range | status | first candidate |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row['mapped_target_id'] or row['target_label'] or '-'}` | {row['candidate_count']} | "
            f"{row['pre_native_count']} | {row['post_native_count']} | "
            f"`{row['earliest_prediction_date'] or '-'}`-`{row['latest_prediction_date'] or '-'}` | "
            f"`{row['target_review_status']}` | `{row['first_candidate_path'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_csv(args.target_csv, payload["target_rows"], TARGET_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review internal-like strict-blind source candidates by chronology.")
    parser.add_argument("--scan-roots", default=DEFAULT_SCAN_ROOTS)
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--unknown-triage-json", default=DEFAULT_UNKNOWN_TRIAGE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--target-csv", default=DEFAULT_TARGET_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
