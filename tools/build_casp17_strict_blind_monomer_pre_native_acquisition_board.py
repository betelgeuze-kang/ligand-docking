#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REQUEST_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_INTERNAL_LIKE_SOURCE_REVIEW_JSON = "casp17/casp17_strict_blind_internal_like_source_review_current.json"
DEFAULT_INTERNAL_SOURCE_AUDIT_JSON = "casp17/casp17_strict_blind_internal_prediction_source_audit_current.json"
DEFAULT_BOARD_DIR = "casp17/strict_blind_monomer_pre_native_acquisition_board"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_monomer_pre_native_acquisition_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_monomer_pre_native_acquisition_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_MONOMER_PRE_NATIVE_ACQUISITION_BOARD.md"

ROW_COLUMNS = [
    "acquisition_rank",
    "request_id",
    "target_id",
    "acquisition_status",
    "request_status",
    "route_status",
    "current_prediction_created_at",
    "native_release_date",
    "local_pre_native_candidate_count",
    "local_post_native_candidate_count",
    "operator_field_filled_count",
    "operator_field_missing_count",
    "operator_template_csv",
    "source_request_folder",
    "acquisition_folder",
    "acquisition_template_csv",
    "required_artifacts_csv",
    "first_slot_prediction_dropzone",
    "first_blocker",
    "next_action",
]

ACQUISITION_FIELDS = [
    ("source_id", "stable internal source id for the acquired pre-native prediction"),
    ("prediction_pdb", "path to acquired pre-native prediction PDB"),
    ("prediction_pdb_dropzone", "first-slot dropzone path after operator acquisition"),
    ("prediction_created_at", "YYYY-MM-DD; must be earlier than native_release_date"),
    ("native_release_date", "authoritative native release date used for chronology comparison"),
    ("native_authority_ref", "authority reference for the native release date"),
    ("creation_evidence_ref", "timestamp/job/archive evidence for prediction creation"),
    ("no_leak_evidence_ref", "independent no-leak evidence for the prediction source"),
    ("method_summary", "short internal method/source summary"),
    ("operator_clearance", "operator_cleared only after evidence review"),
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind monomer pre-native acquisition board only. It consolidates monomer "
    "source requests and internal-like source review evidence into operator acquisition folders for "
    "pre-native prediction artifacts. It does not fetch files, copy coordinates, approve provenance, "
    "mutate source-gate templates, compute CASP metrics, serialize an author code, or submit to CASP."
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


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug.lower() or "unknown"


def _target_folder(board_dir: str | Path, rank: int, request_id: str, target_id: str) -> Path:
    return _resolve(board_dir) / f"{rank:02d}_{_slug(request_id)}_{_slug(target_id)}"


def _dropzone_from_audit(source_audit_rows: list[dict[str, Any]], source_audit_summary: dict[str, Any]) -> str:
    for row in source_audit_rows:
        if _text(row.get("source_id")) == "required_prediction_dropzone":
            evidence_ref = _text(row.get("evidence_ref"))
            match = re.search(r"\bat\s+(\S+)", evidence_ref)
            return match.group(1) if match else evidence_ref
    match = re.search(r"\bat\s+(\S+)", _text(source_audit_summary.get("first_next_action")))
    return match.group(1) if match else ""


def _target_review_by_request(internal_review_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_request: dict[str, dict[str, Any]] = {}
    for row in _rows(internal_review_payload, "target_rows"):
        request_id = _text(row.get("request_id"))
        if request_id:
            by_request[request_id] = row
    return by_request


def _acquisition_status(request_row: dict[str, Any], target_review: dict[str, Any]) -> str:
    if _text(request_row.get("candidate_scope")) != "monomer":
        return "blocked_not_monomer_request"
    if _int(target_review.get("pre_native_count")) > 0:
        return "operator_review_pre_native_local_candidate_available"
    return "awaiting_pre_native_artifact_operator_acquisition"


def _build_rows(
    source_request_rows: list[dict[str, Any]],
    target_review_rows_by_request: dict[str, dict[str, Any]],
    source_audit_summary: dict[str, Any],
    source_audit_rows: list[dict[str, Any]],
    board_dir: str | Path,
) -> list[dict[str, Any]]:
    first_slot_dropzone = _dropzone_from_audit(source_audit_rows, source_audit_summary)
    monomer_requests = [
        row
        for row in source_request_rows
        if _text(row.get("candidate_scope")) == "monomer"
        and _text(row.get("request_kind")) == "pre_native_prediction_source_required"
    ]
    rows: list[dict[str, Any]] = []
    for rank, request in enumerate(monomer_requests, start=1):
        request_id = _text(request.get("request_id"))
        target_id = _text(request.get("candidate_target_id"))
        review = target_review_rows_by_request.get(request_id, {})
        folder = _target_folder(board_dir, rank, request_id, target_id)
        rows.append(
            {
                "acquisition_rank": rank,
                "request_id": request_id,
                "target_id": target_id,
                "acquisition_status": _acquisition_status(request, review),
                "request_status": _text(request.get("request_status")),
                "route_status": _text(request.get("route_status")),
                "current_prediction_created_at": _text(request.get("prediction_created_at")),
                "native_release_date": _text(request.get("native_release_date")),
                "local_pre_native_candidate_count": _int(review.get("pre_native_count")),
                "local_post_native_candidate_count": _int(review.get("post_native_count")),
                "operator_field_filled_count": _int(request.get("operator_field_filled_count")),
                "operator_field_missing_count": _int(request.get("operator_field_missing_count")),
                "operator_template_csv": _text(request.get("operator_template_csv")),
                "source_request_folder": _text(request.get("request_folder")),
                "acquisition_folder": _artifact(folder),
                "acquisition_template_csv": _artifact(folder / "operator_acquisition_template.csv"),
                "required_artifacts_csv": _artifact(folder / "required_artifacts.csv"),
                "first_slot_prediction_dropzone": first_slot_dropzone,
                "first_blocker": _text(request.get("first_blocker")) or "pre_native_artifact_missing",
                "next_action": "acquire a pre-native internal prediction artifact with timestamp and no-leak evidence",
            }
        )
    return rows


def _write_target_folder(row: dict[str, Any]) -> None:
    folder = _resolve(row["acquisition_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    target_id = row["target_id"]
    request_id = row["request_id"]
    readme_lines = [
        f"# {request_id} {target_id} Pre-Native Acquisition",
        "",
        f"- status: `{row['acquisition_status']}`",
        f"- route: `{row['route_status']}`",
        f"- local pre/post-native candidates: `{row['local_pre_native_candidate_count']}/{row['local_post_native_candidate_count']}`",
        f"- current prediction/native dates: `{row['current_prediction_created_at'] or '-'}` / `{row['native_release_date'] or '-'}`",
        f"- source request folder: `{row['source_request_folder']}`",
        f"- source request template: `{row['operator_template_csv']}`",
        f"- first-slot prediction dropzone: `{row['first_slot_prediction_dropzone'] or '-'}`",
        f"- next action: {row['next_action']}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "ACQUISITION.md").write_text("\n".join(readme_lines), encoding="utf-8")
    template_rows = [
        {
            "field_key": field_key,
            "operator_value": "",
            "operator_evidence_ref": "",
            "required_format": required_format,
            "request_id": request_id,
            "target_id": target_id,
            "source_request_template": row["operator_template_csv"],
            "claim_boundary": "operator_fill_only_not_proof",
        }
        for field_key, required_format in ACQUISITION_FIELDS
    ]
    _write_csv(
        folder / "operator_acquisition_template.csv",
        template_rows,
        [
            "field_key",
            "operator_value",
            "operator_evidence_ref",
            "required_format",
            "request_id",
            "target_id",
            "source_request_template",
            "claim_boundary",
        ],
    )
    artifact_rows = [
        {
            "artifact_key": "prediction_pdb",
            "required": "true",
            "operator_path_or_uri": "",
            "expected_dropzone": row["first_slot_prediction_dropzone"],
            "notes": "pre-native internal prediction PDB; do not use current post-native local candidate",
        },
        {
            "artifact_key": "creation_evidence_ref",
            "required": "true",
            "operator_path_or_uri": "",
            "expected_dropzone": "",
            "notes": "timestamp, immutable job record, archive manifest, or signed lab notebook evidence",
        },
        {
            "artifact_key": "no_leak_evidence_ref",
            "required": "true",
            "operator_path_or_uri": "",
            "expected_dropzone": "",
            "notes": "independent no-leak provenance and negative-control evidence",
        },
    ]
    _write_csv(
        folder / "required_artifacts.csv",
        artifact_rows,
        ["artifact_key", "required", "operator_path_or_uri", "expected_dropzone", "notes"],
    )


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Monomer Pre-Native Acquisition Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['monomer_pre_native_acquisition_board_status']}`",
        f"- monomer requests ready/acquire/total: `{summary['ready_pre_native_local_candidate_count']}/{summary['acquisition_required_count']}/{summary['monomer_request_count']}`",
        f"- local internal-like pre/post candidates: `{summary['internal_like_pre_native_candidate_count']}/{summary['internal_like_post_native_candidate_count']}`",
        f"- operator fields filled/missing/total: `{summary['operator_field_filled_count']}/{summary['operator_field_missing_count']}/{summary['operator_field_count']}`",
        f"- first request/blocker: `{summary['first_request_id'] or '-'}` `{summary['first_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- first-slot prediction dropzone: `{summary['first_slot_prediction_dropzone'] or '-'}`",
        f"- board dir: `{summary['board_dir']}`",
        f"- next action: {summary['next_action'] or '-'}",
        "",
        "## Requests",
        "",
        "| rank | request | target | status | local pre/post | current/native dates | template | next action |",
        "| ---: | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['acquisition_rank']} | `{row['request_id']}` | `{row['target_id']}` | "
            f"`{row['acquisition_status']}` | `{row['local_pre_native_candidate_count']}/{row['local_post_native_candidate_count']}` | "
            f"`{row['current_prediction_created_at'] or '-'}` / `{row['native_release_date'] or '-'}` | "
            f"`{row['acquisition_template_csv']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | missing input or no monomer requests |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_packet = _read_json(args.source_request_packet_json)
    internal_review = _read_json(args.internal_like_source_review_json)
    source_audit = _read_json(args.internal_source_audit_json)
    input_blockers = [
        f"{name}_json_missing"
        for name, path in [
            ("source_request_packet", args.source_request_packet_json),
            ("internal_like_source_review", args.internal_like_source_review_json),
            ("internal_source_audit", args.internal_source_audit_json),
        ]
        if not _resolve(path).exists()
    ]
    source_packet_summary = _summary(source_packet)
    internal_review_summary = _summary(internal_review)
    source_audit_summary = _summary(source_audit)
    rows = []
    if not input_blockers:
        rows = _build_rows(
            _rows(source_packet),
            _target_review_by_request(internal_review),
            source_audit_summary,
            _rows(source_audit),
            args.board_dir,
        )
    ready_rows = [
        row
        for row in rows
        if row["acquisition_status"] == "operator_review_pre_native_local_candidate_available"
    ]
    acquisition_rows = [
        row
        for row in rows
        if row["acquisition_status"] == "awaiting_pre_native_artifact_operator_acquisition"
    ]
    first_row = rows[0] if rows else {}
    status = "strict_blind_monomer_pre_native_acquisition_required"
    if input_blockers:
        status = "blocked_missing_input"
    elif ready_rows and not acquisition_rows:
        status = "strict_blind_monomer_pre_native_candidates_available_for_operator_review"
    elif not rows:
        status = "blocked_no_monomer_source_requests"
    summary = {
        "packet_type": "casp17_strict_blind_monomer_pre_native_acquisition_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "monomer_pre_native_acquisition_board_status": status,
        "source_request_packet_status": _text(source_packet_summary.get("source_request_packet_status")),
        "internal_like_source_review_status": _text(internal_review_summary.get("internal_like_source_review_status")),
        "internal_source_audit_status": _text(source_audit_summary.get("internal_prediction_source_audit_status")),
        "monomer_request_count": len(rows),
        "ready_pre_native_local_candidate_count": len(ready_rows),
        "acquisition_required_count": len(acquisition_rows),
        "internal_like_pre_native_candidate_count": _int(internal_review_summary.get("pre_native_candidate_count")),
        "internal_like_post_native_candidate_count": _int(internal_review_summary.get("post_native_blocked_count")),
        "target_pre_native_candidate_count": _int(internal_review_summary.get("target_pre_native_candidate_count")),
        "target_all_post_native_count": _int(internal_review_summary.get("target_all_post_native_count")),
        "operator_field_count": sum(_int(row.get("operator_field_filled_count")) + _int(row.get("operator_field_missing_count")) for row in rows),
        "operator_field_filled_count": sum(_int(row.get("operator_field_filled_count")) for row in rows),
        "operator_field_missing_count": sum(_int(row.get("operator_field_missing_count")) for row in rows),
        "first_request_id": _text(first_row.get("request_id")),
        "first_target_id": _text(first_row.get("target_id")),
        "first_blocker": _text(first_row.get("first_blocker")),
        "first_slot_prediction_dropzone": _text(first_row.get("first_slot_prediction_dropzone"))
        or _dropzone_from_audit(_rows(source_audit), source_audit_summary),
        "board_dir": _artifact(args.board_dir),
        "input_blockers": ",".join(input_blockers),
        "next_action": (
            "fill acquisition templates with a verified pre-native internal prediction source, timestamp, no-leak evidence, method summary, and operator clearance"
            if not input_blockers
            else "restore missing input JSON artifacts and rerun the board"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_target_folder(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind monomer pre-native acquisition board.")
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--internal-like-source-review-json", default=DEFAULT_INTERNAL_LIKE_SOURCE_REVIEW_JSON)
    parser.add_argument("--internal-source-audit-json", default=DEFAULT_INTERNAL_SOURCE_AUDIT_JSON)
    parser.add_argument("--board-dir", default=DEFAULT_BOARD_DIR)
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
