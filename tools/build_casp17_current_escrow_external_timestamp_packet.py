#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ESCROW_JSON = "casp17/casp17_current_prospective_strict_blind_escrow_current.json"
DEFAULT_OUT_DIR = "casp17/current_escrow_external_timestamp_packet"
DEFAULT_OUT_JSON = "casp17/casp17_current_escrow_external_timestamp_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_escrow_external_timestamp_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_ESCROW_EXTERNAL_TIMESTAMP_PACKET.md"

ROW_COLUMNS = [
    "target_id",
    "official_target_id",
    "protein_name",
    "queue_rank",
    "urgency",
    "upload_queue_status",
    "escrow_status",
    "timestamp_packet_status",
    "timestamp_action",
    "candidate_pdb",
    "candidate_sha256",
    "candidate_size_bytes",
    "sha256_match",
    "escrow_md",
    "review_md",
    "native_status",
    "external_timestamp_status",
    "competitive_proof_eligible",
    "author_serialized",
    "manifest_inclusion",
    "blockers",
    "next_action",
]

RERUN_COMMANDS = [
    "python3 tools/build_casp17_current_prospective_strict_blind_escrow.py",
    "python3 tools/build_casp17_current_escrow_external_timestamp_packet.py",
    "python3 tools/build_casp17_workbench_index.py",
]

CLAIM_BOUNDARY = (
    "CASP17 current escrow external timestamp packet only. It converts the prospective strict-blind "
    "escrow into a commit/push-ready timestamp manifest with candidate paths, SHA256 hashes, review links, "
    "and native-pending state. It does not commit, push, submit to CASP, copy coordinates, serialize a CASP "
    "author code, compute native accuracy, or mark strict-blind competitive proof."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_true(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _is_upload_ready(status: str) -> bool:
    return status.startswith("upload_ready")


def _timestamp_action(row: dict[str, Any]) -> str:
    urgency = _text(row.get("urgency"))
    upload_status = _text(row.get("upload_queue_status"))
    if _is_upload_ready(upload_status) and urgency == "today":
        return "timestamp_now_expiring_today"
    if _is_upload_ready(upload_status) and urgency == "soon":
        return "timestamp_now_expiring_soon"
    if _is_upload_ready(upload_status):
        return "timestamp_now_future_window"
    return "timestamp_for_retrospective_proof_only"


def _timestamp_row(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    target_id = _text(row.get("target_id")).upper()
    escrow_md = _text(row.get("escrow_md"))
    escrow_md_path = _resolve(escrow_md) if escrow_md else Path()
    if not target_id:
        blockers.append("target_id_missing")
    if _text(row.get("escrow_status")) != "prospective_escrow_ready_native_pending":
        blockers.append("escrow_not_ready")
    if not _is_true(row.get("sha256_match")):
        blockers.append("sha256_not_verified")
    if not _text(row.get("candidate_pdb")):
        blockers.append("candidate_pdb_missing")
    if not _text(row.get("candidate_sha256")):
        blockers.append("candidate_sha256_missing")
    if not escrow_md or not escrow_md_path.is_file():
        blockers.append("escrow_md_missing")
    if _text(row.get("native_status")) != "official_native_release_pending":
        blockers.append("native_status_not_pending")
    if _text(row.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_violation")
    timestamp_status = "ready_for_external_timestamp" if not blockers else "blocked_external_timestamp_packet"
    return {
        "target_id": target_id,
        "official_target_id": _text(row.get("official_target_id")),
        "protein_name": _text(row.get("protein_name")),
        "queue_rank": _int(row.get("queue_rank")),
        "urgency": _text(row.get("urgency")),
        "upload_queue_status": _text(row.get("upload_queue_status")),
        "escrow_status": _text(row.get("escrow_status")),
        "timestamp_packet_status": timestamp_status,
        "timestamp_action": _timestamp_action(row),
        "candidate_pdb": _text(row.get("candidate_pdb")),
        "candidate_sha256": _text(row.get("candidate_sha256")),
        "candidate_size_bytes": _int(row.get("candidate_size_bytes")),
        "sha256_match": str(_is_true(row.get("sha256_match"))),
        "escrow_md": escrow_md,
        "review_md": _text(row.get("review_md")),
        "native_status": _text(row.get("native_status")),
        "external_timestamp_status": "external_timestamp_required",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "manifest_inclusion": "include" if not blockers else "blocked",
        "blockers": ",".join(blockers),
        "next_action": (
            "commit/push this timestamp packet and escrow manifests, then preserve the resulting external "
            "timestamp for post-native strict-blind evaluation"
            if not blockers
            else "repair escrow row before external timestamp"
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    escrow_payload = _read_json(args.escrow_json)
    escrow_summary = _summary(escrow_payload)
    escrow_rows = _rows(escrow_payload)
    rows = [_timestamp_row(row) for row in escrow_rows]
    rows.sort(key=lambda row: (_int(row.get("queue_rank")) or 9999, _text(row.get("target_id"))))
    ready = sum(1 for row in rows if row["timestamp_packet_status"] == "ready_for_external_timestamp")
    blocked = len(rows) - ready
    upload_ready = sum(1 for row in rows if _is_upload_ready(_text(row.get("upload_queue_status"))))
    upload_blocked = len(rows) - upload_ready
    today = sum(1 for row in rows if row["urgency"] == "today")
    soon = sum(1 for row in rows if row["urgency"] == "soon")
    future = sum(1 for row in rows if row["urgency"] == "future")
    escrow_md_present = sum(1 for row in rows if _text(row.get("escrow_md")) and _resolve(row["escrow_md"]).is_file())
    sha_ready = sum(1 for row in rows if _is_true(row.get("sha256_match")))
    first_ready = next((row for row in rows if row["timestamp_packet_status"] == "ready_for_external_timestamp"), {})
    first_blocked = next((row for row in rows if row["timestamp_packet_status"] != "ready_for_external_timestamp"), {})
    status = (
        "blocked_current_prospective_strict_blind_escrow_missing"
        if not escrow_rows
        else (
            "current_escrow_external_timestamp_packet_ready_for_external_timestamp"
            if ready == len(rows)
            else (
                "current_escrow_external_timestamp_packet_partial"
                if ready
                else "blocked_current_escrow_external_timestamp_packet"
            )
        )
    )
    timestamp_manifest_csv = _artifact(Path(args.out_dir) / "TIMESTAMP_MANIFEST.csv")
    rerun_commands_md = _artifact(Path(args.out_dir) / "RERUN_COMMANDS.md")
    summary = {
        "packet_type": "casp17_current_escrow_external_timestamp_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_escrow_external_timestamp_packet_status": status,
        "prospective_escrow_status": _text(escrow_summary.get("prospective_escrow_status")),
        "manifest_signature_sha256": _text(escrow_summary.get("manifest_signature_sha256")),
        "target_count": len(rows),
        "timestamp_ready_count": ready,
        "timestamp_blocked_count": blocked,
        "upload_ready_count": upload_ready,
        "upload_blocked_count": upload_blocked,
        "urgency_today_count": today,
        "urgency_soon_count": soon,
        "urgency_future_count": future,
        "sha256_match_count": sha_ready,
        "escrow_md_present_count": escrow_md_present,
        "timestamp_manifest_row_count": len(rows),
        "native_pending_count": len(rows),
        "external_timestamp_required_count": len(rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "coordinate_copy_count": 0,
        "proof_marker_count": 0,
        "portal_submit_marker_count": 0,
        "first_ready_target_id": _text(first_ready.get("target_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "timestamp_manifest_csv": timestamp_manifest_csv,
        "rerun_commands_md": rerun_commands_md,
        "next_action": (
            "commit/push the timestamp packet and escrow manifests when operator requests external timestamp; "
            "do not claim proof until official native release and post-native scoring"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "rerun_commands": RERUN_COMMANDS}


def _write_rerun_commands(path_like: str | Path) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CASP17 Current Escrow External Timestamp Packet Rerun Commands", ""]
    lines.extend(f"- `{command}`" for command in RERUN_COMMANDS)
    lines.append("")
    lines.append(CLAIM_BOUNDARY)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Escrow External Timestamp Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['current_escrow_external_timestamp_packet_status']}`",
        f"- prospective escrow: `{summary['prospective_escrow_status'] or '-'}`",
        f"- timestamp ready/blocked/total: `{summary['timestamp_ready_count']}/{summary['timestamp_blocked_count']}/{summary['target_count']}`",
        f"- upload ready/blocked: `{summary['upload_ready_count']}/{summary['upload_blocked_count']}`",
        f"- urgency today/soon/future: `{summary['urgency_today_count']}/{summary['urgency_soon_count']}/{summary['urgency_future_count']}`",
        f"- sha256/escrow-md/manifest rows: `{summary['sha256_match_count']}/{summary['escrow_md_present_count']}/{summary['timestamp_manifest_row_count']}`",
        f"- native pending/external timestamp required: `{summary['native_pending_count']}/{summary['external_timestamp_required_count']}`",
        f"- proof/author/hygiene: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}/{summary['coordinate_copy_count']}/{summary['proof_marker_count']}/{summary['portal_submit_marker_count']}`",
        f"- manifest signature: `{summary['manifest_signature_sha256'] or '-'}`",
        f"- timestamp manifest: `{summary['timestamp_manifest_csv']}`",
        f"- first ready/blocked: `{summary['first_ready_target_id'] or '-'}`/`{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Timestamp Manifest Rows",
        "",
        "| target | status | action | upload | urgency | sha256 | escrow md | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['timestamp_packet_status']}` | `{row['timestamp_action']}` | "
            f"`{row['upload_queue_status'] or '-'}` | `{row['urgency'] or '-'}` | "
            f"`{row['candidate_sha256'][:16] if row['candidate_sha256'] else '-'}` | "
            f"`{row['escrow_md'] or '-'}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_csv(out_dir / "TIMESTAMP_MANIFEST.csv", payload["rows"])
    _write_rerun_commands(out_dir / "RERUN_COMMANDS.md")
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 current escrow external timestamp packet.")
    parser.add_argument("--escrow-json", default=DEFAULT_ESCROW_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
