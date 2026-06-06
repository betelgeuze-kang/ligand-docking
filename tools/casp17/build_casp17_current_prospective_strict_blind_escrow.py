#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PACKAGE_PREFLIGHT_JSON = "casp17/casp17_current_submission_package_preflight_current.json"
DEFAULT_UPLOAD_QUEUE_JSON = "casp17/casp17_current_upload_queue_current.json"
DEFAULT_UPLOAD_REVIEW_PACKET_JSON = "casp17/casp17_current_upload_review_packet_current.json"
DEFAULT_ESCROW_DIR = "casp17/current_prospective_strict_blind_escrow"
DEFAULT_OUT_JSON = "casp17/casp17_current_prospective_strict_blind_escrow_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_prospective_strict_blind_escrow_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_PROSPECTIVE_STRICT_BLIND_ESCROW.md"

ROW_COLUMNS = [
    "target_id",
    "official_target_id",
    "protein_name",
    "escrow_status",
    "candidate_pdb",
    "candidate_sha256",
    "sha256_match",
    "candidate_size_bytes",
    "package_preflight_status",
    "upload_queue_status",
    "queue_rank",
    "urgency",
    "official_human_expiration",
    "review_md",
    "first_viewer_html_path",
    "escrow_folder",
    "escrow_md",
    "native_status",
    "external_timestamp_status",
    "competitive_proof_eligible",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "CASP17 current prospective strict-blind escrow only. It freezes local candidate paths, SHA256 hashes, "
    "upload-review links, and native-pending status for future evaluation after official native release. It is "
    "not a CASP portal submission, not native-accuracy evidence, not external timestamp proof, and not current "
    "strict-blind competitive proof."
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


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _review_by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _is_upload_ready(status: str) -> bool:
    return status.startswith("upload_ready")


def _is_upload_blocked(status: str) -> bool:
    return status.startswith("upload_blocked") or status.startswith("blocked_")


def _escrow_row(
    preflight_row: dict[str, Any],
    queue_row: dict[str, Any],
    review_row: dict[str, Any],
    escrow_root: Path,
) -> dict[str, Any]:
    target_id = _text(preflight_row.get("target_id")).upper()
    candidate_pdb = _text(preflight_row.get("candidate_pdb"))
    expected_sha = _text(preflight_row.get("candidate_sha256"))
    candidate_path = _resolve(candidate_pdb) if candidate_pdb else Path()
    blockers: list[str] = []
    hard_blockers: list[str] = []
    actual_sha = ""
    size_bytes = 0
    if not target_id:
        blockers.append("target_id_missing")
        hard_blockers.append("target_id_missing")
    if _text(preflight_row.get("package_preflight_status")) != "ready":
        blockers.append("package_preflight_not_ready")
        hard_blockers.append("package_preflight_not_ready")
    if not candidate_pdb or not candidate_path.is_file():
        blockers.append("candidate_pdb_missing")
        hard_blockers.append("candidate_pdb_missing")
    else:
        actual_sha = _sha256(candidate_path)
        size_bytes = candidate_path.stat().st_size
        if expected_sha and actual_sha != expected_sha:
            blockers.append("candidate_sha256_mismatch")
            hard_blockers.append("candidate_sha256_mismatch")
    if not expected_sha:
        blockers.append("candidate_sha256_missing")
        hard_blockers.append("candidate_sha256_missing")
    if not _text(queue_row.get("upload_queue_status")):
        blockers.append("upload_queue_row_missing")
    if _is_upload_blocked(_text(queue_row.get("upload_queue_status"))):
        blockers.append("upload_queue_blocked:" + (_text(queue_row.get("blockers")) or "no_current_upload_window"))
    if not _text(review_row.get("review_md")):
        blockers.append("upload_review_packet_missing")
    blockers.extend(["official_native_release_pending", "external_timestamp_required"])
    escrow_folder = escrow_root / _safe_name(target_id)
    escrow_md = escrow_folder / "ESCROW.md"
    escrow_status = (
        "prospective_escrow_ready_native_pending"
        if not hard_blockers
        else "prospective_escrow_blocked"
    )
    return {
        "target_id": target_id,
        "official_target_id": _text(queue_row.get("official_target_id")),
        "protein_name": _text(preflight_row.get("protein_name")) or _text(queue_row.get("protein_name")),
        "escrow_status": escrow_status,
        "candidate_pdb": candidate_pdb,
        "candidate_sha256": actual_sha or expected_sha,
        "sha256_match": str(bool(expected_sha and actual_sha and expected_sha == actual_sha)),
        "candidate_size_bytes": size_bytes,
        "package_preflight_status": _text(preflight_row.get("package_preflight_status")),
        "upload_queue_status": _text(queue_row.get("upload_queue_status")),
        "queue_rank": _int(queue_row.get("queue_rank")),
        "urgency": _text(review_row.get("urgency")),
        "official_human_expiration": _text(queue_row.get("official_human_expiration")) or _text(review_row.get("official_human_expiration")),
        "review_md": _text(review_row.get("review_md")),
        "first_viewer_html_path": _text(review_row.get("first_viewer_html_path")),
        "escrow_folder": _artifact(escrow_folder),
        "escrow_md": _artifact(escrow_md),
        "native_status": "official_native_release_pending",
        "external_timestamp_status": "external_timestamp_required",
        "competitive_proof_eligible": "false",
        "blockers": ",".join(blockers),
        "next_action": "commit/push or otherwise externally timestamp this escrow, then attach official native after release for strict-blind evaluation",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    preflight_payload = _read_json(args.package_preflight_json)
    queue_payload = _read_json(args.upload_queue_json)
    review_payload = _read_json(args.upload_review_packet_json)
    preflight_summary = _summary(preflight_payload)
    queue_summary = _summary(queue_payload)
    review_summary = _summary(review_payload)
    queue_by_target = _by_target(_rows(queue_payload))
    review_by_target = _review_by_target(_rows(review_payload))
    escrow_root = _resolve(args.escrow_dir)
    rows = [
        _escrow_row(row, queue_by_target.get(_text(row.get("target_id")).upper(), {}), review_by_target.get(_text(row.get("target_id")).upper(), {}), escrow_root)
        for row in _rows(preflight_payload)
    ]
    rows.sort(key=lambda row: (_int(row.get("queue_rank")) or 9999, _text(row.get("target_id"))))
    ready = sum(1 for row in rows if row["escrow_status"] == "prospective_escrow_ready_native_pending")
    blocked = len(rows) - ready
    upload_ready = sum(1 for row in rows if _is_upload_ready(_text(row.get("upload_queue_status"))))
    upload_blocked = sum(1 for row in rows if _is_upload_blocked(_text(row.get("upload_queue_status"))))
    sha_ready = sum(1 for row in rows if row["sha256_match"] == "True")
    review_ready = sum(1 for row in rows if _text(row.get("review_md")))
    today = sum(1 for row in rows if row["urgency"] == "today")
    soon = sum(1 for row in rows if row["urgency"] == "soon")
    future = sum(1 for row in rows if row["urgency"] == "future")
    status = (
        "current_prospective_strict_blind_escrow_ready_native_pending_partial_upload_window"
        if ready == len(rows) and upload_blocked
        else (
            "current_prospective_strict_blind_escrow_ready_native_pending"
            if ready and not blocked
            else (
                "current_prospective_strict_blind_escrow_partial"
                if ready
                else "current_prospective_strict_blind_escrow_blocked"
            )
        )
    )
    manifest_basis = {
        "rows": [
            {
                "target_id": row["target_id"],
                "candidate_pdb": row["candidate_pdb"],
                "candidate_sha256": row["candidate_sha256"],
                "candidate_size_bytes": row["candidate_size_bytes"],
                "native_status": row["native_status"],
            }
            for row in rows
        ]
    }
    manifest_signature_sha256 = hashlib.sha256(
        json.dumps(manifest_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    first_blocked = next((row for row in rows if row["escrow_status"] != "prospective_escrow_ready_native_pending"), {})
    first_upload_ready = next((row for row in rows if _is_upload_ready(_text(row.get("upload_queue_status")))), {})
    first_upload_blocked = next((row for row in rows if _is_upload_blocked(_text(row.get("upload_queue_status")))), {})
    summary = {
        "packet_type": "casp17_current_prospective_strict_blind_escrow",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "prospective_escrow_status": status,
        "package_preflight_status": _text(preflight_summary.get("package_preflight_status")),
        "upload_queue_status": _text(queue_summary.get("upload_queue_status")),
        "upload_review_packet_status": _text(review_summary.get("review_packet_status")),
        "escrow_dir": _artifact(escrow_root),
        "target_count": len(rows),
        "escrow_ready_count": ready,
        "escrow_blocked_count": blocked,
        "upload_ready_count": upload_ready,
        "upload_blocked_count": upload_blocked,
        "sha256_match_count": sha_ready,
        "review_link_count": review_ready,
        "urgency_today_count": today,
        "urgency_soon_count": soon,
        "urgency_future_count": future,
        "native_pending_count": len(rows),
        "external_timestamp_required_count": len(rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "manifest_signature_sha256": manifest_signature_sha256,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "first_upload_ready_target_id": _text(first_upload_ready.get("target_id")),
        "first_upload_blocked_target_id": _text(first_upload_blocked.get("target_id")),
        "next_action": "externally timestamp the escrow manifest and attach official native structures after release; keep current proof eligibility false until then",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_escrow_target_md(row: dict[str, Any]) -> None:
    path = _resolve(row["escrow_md"])
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {row['target_id']} Prospective Strict-Blind Escrow",
        "",
        f"- escrow_status: `{row['escrow_status']}`",
        f"- candidate_pdb: `{row['candidate_pdb']}`",
        f"- candidate_sha256: `{row['candidate_sha256']}`",
        f"- sha256_match: `{row['sha256_match']}`",
        f"- upload_queue_status: `{row['upload_queue_status'] or '-'}`",
        f"- review_md: `{row['review_md'] or '-'}`",
        f"- native_status: `{row['native_status']}`",
        f"- external_timestamp_status: `{row['external_timestamp_status']}`",
        f"- competitive_proof_eligible: `{row['competitive_proof_eligible']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Prospective Strict-Blind Escrow",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['prospective_escrow_status']}`",
        f"- escrow ready/blocked/total: `{summary['escrow_ready_count']}/{summary['escrow_blocked_count']}/{summary['target_count']}`",
        f"- upload ready/blocked: `{summary['upload_ready_count']}/{summary['upload_blocked_count']}`",
        f"- sha256/review/native-pending/external-timestamp-required: `{summary['sha256_match_count']}/{summary['review_link_count']}/{summary['native_pending_count']}/{summary['external_timestamp_required_count']}`",
        f"- urgency today/soon/future: `{summary['urgency_today_count']}/{summary['urgency_soon_count']}/{summary['urgency_future_count']}`",
        f"- competitive proof eligible: `{summary['competitive_proof_eligible_count']}`",
        f"- author serialized count: `{summary['author_serialized_count']}`",
        f"- first upload ready/blocked: `{summary['first_upload_ready_target_id'] or '-'}`/`{summary['first_upload_blocked_target_id'] or '-'}`",
        f"- manifest_signature_sha256: `{summary['manifest_signature_sha256']}`",
        "",
        "## Escrow Rows",
        "",
        "| target | escrow | upload | urgency | sha256 | native | escrow md | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['escrow_status']}` | `{row['upload_queue_status'] or '-'}` | "
            f"`{row['urgency'] or '-'}` | `{row['candidate_sha256'][:16] if row['candidate_sha256'] else '-'}` | "
            f"`{row['native_status']}` | `{row['escrow_md']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    for row in payload["rows"]:
        _write_escrow_target_md(row)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build current CASP17 prospective strict-blind escrow.")
    parser.add_argument("--package-preflight-json", default=DEFAULT_PACKAGE_PREFLIGHT_JSON)
    parser.add_argument("--upload-queue-json", default=DEFAULT_UPLOAD_QUEUE_JSON)
    parser.add_argument("--upload-review-packet-json", default=DEFAULT_UPLOAD_REVIEW_PACKET_JSON)
    parser.add_argument("--escrow-dir", default=DEFAULT_ESCROW_DIR)
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
