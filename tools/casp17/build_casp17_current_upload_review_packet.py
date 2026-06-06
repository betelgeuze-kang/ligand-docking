#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_UPLOAD_QUEUE_JSON = "casp17/casp17_current_upload_queue_current.json"
DEFAULT_PACKAGE_PREFLIGHT_JSON = "casp17/casp17_current_submission_package_preflight_current.json"
DEFAULT_PROTEIN_OBJECT_NAVIGATION_JSON = (
    "casp17/casp17_protein_object_library_navigation_catalog_current.json"
)
DEFAULT_TARGET_OBJECT_REVIEW_JSON = "casp17/casp17_target_object_model_review_current.json"
DEFAULT_REVIEW_DIR = "casp17/current_upload_review_packet"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_review_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_review_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_REVIEW_PACKET.md"


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


def _safe_folder_name(*parts: Any) -> str:
    text = "_".join(_text(part) for part in parts if _text(part))
    keep = []
    for char in text:
        if char.isalnum() or char in {"-", "_", "."}:
            keep.append(char)
        elif char.isspace() or char in {"/", "\\", ":", ";", ","}:
            keep.append("_")
    cleaned = "".join(keep).strip("._")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.lower() or "target"


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _object_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            counts[target_id] = counts.get(target_id, 0) + 1
    return counts


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
        "review_status",
        "urgency",
        "protein_name",
        "official_human_expiration",
        "days_to_official_human_expiration",
        "candidate_pdb",
        "candidate_sha256",
        "object_count",
        "chain_ids",
        "library_protein_folder",
        "protein_readme",
        "protein_manifest",
        "first_viewer_html_path",
        "review_md",
        "packet_folder",
        "blockers",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_target_review(row: dict[str, Any]) -> None:
    path = _resolve(row["review_md"])
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {row['target_id']} Upload Review",
        "",
        f"- review_status: `{row['review_status']}`",
        f"- urgency: `{row['urgency']}`",
        f"- official_target_id: `{row['official_target_id'] or '-'}`",
        f"- protein_name: `{row['protein_name'] or '-'}`",
        f"- official_human_expiration: `{row['official_human_expiration'] or '-'}`",
        f"- days_to_official_human_expiration: `{row['days_to_official_human_expiration']}`",
        f"- candidate_pdb: `{row['candidate_pdb'] or '-'}`",
        f"- candidate_sha256: `{row['candidate_sha256'] or '-'}`",
        f"- object_count: `{row['object_count']}`",
        f"- chain_ids: `{row['chain_ids'] or '-'}`",
        f"- library_protein_folder: `{row['library_protein_folder'] or '-'}`",
        f"- protein_readme: `{row['protein_readme'] or '-'}`",
        f"- protein_manifest: `{row['protein_manifest'] or '-'}`",
        f"- first_viewer_html_path: `{row['first_viewer_html_path'] or '-'}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        row["claim_boundary"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Upload Review Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- review_packet_status: `{summary['review_packet_status']}`",
        f"- upload queue: `{summary['upload_queue_status']}` ready/blocked/total `{summary['upload_ready_count']}/{summary['upload_blocked_count']}/{summary['upload_target_count']}`",
        f"- reviews ready/blocked/total: `{summary['review_ready_count']}/{summary['review_blocked_count']}/{summary['review_target_count']}`",
        f"- urgency today/soon/future: `{summary['urgency_today_count']}/{summary['urgency_soon_count']}/{summary['urgency_future_count']}`",
        f"- candidate/object/viewer complete: `{summary['candidate_present_count']}/{summary['object_catalog_pass_count']}/{summary['viewer_link_count']}`",
        f"- first review: `{summary['first_review_target_id'] or '-'}` `{summary['first_review_md'] or '-'}`",
        "",
        "## Review Targets",
        "",
        "| rank | target | status | urgency | human | candidate | objects | viewer | review |",
        "| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['target_id']}` | `{row['review_status']}` | "
            f"`{row['urgency']}` | `{row['official_human_expiration'] or '-'}` | "
            f"`{row['candidate_pdb'] or '-'}` | {row['object_count']} | "
            f"`{row['first_viewer_html_path'] or '-'}` | `{row['review_md']}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | `blocked` | - | - | - | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _urgency(days: int) -> str:
    if days <= 0:
        return "today"
    if days <= 2:
        return "soon"
    return "future"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    upload_payload = _read_json(args.upload_queue_json)
    package_payload = _read_json(args.package_preflight_json)
    navigation_payload = _read_json(args.protein_object_navigation_json)
    object_review_payload = _read_json(args.target_object_review_json)

    upload_summary = _summary(upload_payload)
    package_by_target = _by_target(_rows(package_payload))
    navigation_by_target = _by_target(_rows(navigation_payload))
    object_counts = _object_counts(_rows(object_review_payload))
    review_dir = _artifact(args.review_dir)
    claim_boundary = (
        "CASP17 current upload review packet only. It links official-targetlist upload-ready rows to local "
        "manifest-only TS candidates and per-protein 3D object folders/viewers. It is not a CASP portal "
        "submission, does not serialize an author code, and is not native-accuracy or strict-blind proof."
    )

    rows: list[dict[str, Any]] = []
    for queue_row in _rows(upload_payload):
        if not _text(queue_row.get("upload_queue_status")).startswith("upload_ready_"):
            continue
        target_id = _text(queue_row.get("target_id")).upper()
        package_row = package_by_target.get(target_id, {})
        navigation_row = navigation_by_target.get(target_id, {})
        candidate_pdb = _text(queue_row.get("candidate_pdb")) or _text(package_row.get("candidate_pdb"))
        candidate_sha256 = _text(queue_row.get("candidate_sha256")) or _text(package_row.get("candidate_sha256"))
        object_count = _int(navigation_row.get("object_count")) or object_counts.get(target_id, 0)
        first_viewer = _text(navigation_row.get("first_viewer_html_path"))
        blockers: list[str] = []
        if not candidate_pdb:
            blockers.append("candidate_pdb_missing")
        if not candidate_sha256:
            blockers.append("candidate_sha256_missing")
        if object_count <= 0:
            blockers.append("protein_object_catalog_missing")
        if not first_viewer:
            blockers.append("first_viewer_missing")
        if _text(package_row.get("package_preflight_status")) not in {"", "ready"}:
            blockers.append("package_preflight_not_ready")

        rank = _int(queue_row.get("queue_rank"))
        folder = f"{review_dir}/{rank:02d}_{_safe_folder_name(target_id, queue_row.get('protein_name'))}"
        review_md = f"{folder}/UPLOAD_REVIEW.md"
        days = _int(queue_row.get("days_to_official_human_expiration"))
        row = {
            "queue_rank": rank,
            "target_id": target_id,
            "official_target_id": _text(queue_row.get("official_target_id")),
            "review_status": "ready" if not blockers else "blocked",
            "urgency": _urgency(days),
            "protein_name": _text(queue_row.get("protein_name")),
            "official_human_expiration": _text(queue_row.get("official_human_expiration")),
            "days_to_official_human_expiration": days,
            "candidate_pdb": candidate_pdb,
            "candidate_sha256": candidate_sha256,
            "object_count": object_count,
            "chain_ids": _text(navigation_row.get("chain_ids")),
            "library_protein_folder": _text(navigation_row.get("library_protein_folder")),
            "protein_readme": _text(navigation_row.get("protein_readme")),
            "protein_manifest": _text(navigation_row.get("protein_manifest")),
            "first_viewer_html_path": first_viewer,
            "review_md": review_md,
            "packet_folder": folder,
            "blockers": ";".join(blockers),
            "claim_boundary": claim_boundary,
        }
        rows.append(row)

    rows.sort(key=lambda row: (row["queue_rank"], row["target_id"]))
    ready_rows = [row for row in rows if row["review_status"] == "ready"]
    blocked_rows = [row for row in rows if row["review_status"] != "ready"]
    first_review = rows[0] if rows else {}
    status = (
        "current_upload_review_packet_ready"
        if rows and not blocked_rows
        else (
            "current_upload_review_packet_partial"
            if rows and ready_rows
            else "blocked_no_current_upload_reviews_ready"
        )
    )
    summary = {
        "packet_type": "casp17_current_upload_review_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "review_packet_status": status,
        "review_dir": review_dir,
        "review_target_count": len(rows),
        "review_ready_count": len(ready_rows),
        "review_blocked_count": len(blocked_rows),
        "urgency_today_count": sum(1 for row in ready_rows if row["urgency"] == "today"),
        "urgency_soon_count": sum(1 for row in ready_rows if row["urgency"] == "soon"),
        "urgency_future_count": sum(1 for row in ready_rows if row["urgency"] == "future"),
        "candidate_present_count": sum(1 for row in rows if row["candidate_pdb"]),
        "sha256_present_count": sum(1 for row in rows if row["candidate_sha256"]),
        "object_catalog_pass_count": sum(1 for row in rows if row["object_count"] > 0),
        "viewer_link_count": sum(1 for row in rows if row["first_viewer_html_path"]),
        "upload_queue_status": _text(upload_summary.get("upload_queue_status")),
        "upload_ready_count": _int(upload_summary.get("upload_ready_count")),
        "upload_blocked_count": _int(upload_summary.get("blocked_count")),
        "upload_target_count": _int(upload_summary.get("target_count")),
        "first_review_target_id": _text(first_review.get("target_id")),
        "first_review_md": _text(first_review.get("review_md")),
        "first_blocked_target_id": _text(blocked_rows[0].get("target_id")) if blocked_rows else "",
        "first_blocker": _text(blocked_rows[0].get("blockers")).split(";")[0] if blocked_rows else "",
        "next_action": (
            "open each UPLOAD_REVIEW.md in queue_rank order; upload only with operator-approved runtime CASP "
            "author code and only while the official human deadline remains open"
        ),
        "claim_boundary": claim_boundary,
    }
    return {"summary": summary, "rows": rows}


def write_packet(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    for row in payload["rows"]:
        _write_target_review(row)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local review packet for official-upload-ready CASP17 targets."
    )
    parser.add_argument("--upload-queue-json", default=DEFAULT_UPLOAD_QUEUE_JSON)
    parser.add_argument("--package-preflight-json", default=DEFAULT_PACKAGE_PREFLIGHT_JSON)
    parser.add_argument("--protein-object-navigation-json", default=DEFAULT_PROTEIN_OBJECT_NAVIGATION_JSON)
    parser.add_argument("--target-object-review-json", default=DEFAULT_TARGET_OBJECT_REVIEW_JSON)
    parser.add_argument("--review-dir", default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_packet(args, payload)


if __name__ == "__main__":
    main()
