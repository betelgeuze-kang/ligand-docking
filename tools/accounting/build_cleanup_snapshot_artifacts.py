#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cleanup_snapshot_preflight import DEFAULT_OUT_JSON as DEFAULT_SNAPSHOT_PREFLIGHT_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/cleanup_snapshot_artifacts_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_snapshot_artifacts_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_snapshot_artifacts_current.md"

CLAIM_BOUNDARY = (
    "Cleanup snapshot artifact builder only; it writes local metadata/listing snapshots for approval-gated cleanup rows. "
    "It does not delete, move, archive, externalize, upload, commit, push, or mutate external state beyond writing local "
    "snapshot evidence files."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _snapshot_target(path_like: str) -> Path:
    return _resolve(path_like)


def _entry_digest_line(root: Path, path: Path, stat: Any, kind: str) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return f"{kind}|{rel.as_posix()}|{int(getattr(stat, 'st_size', 0))}|{int(getattr(stat, 'st_mtime_ns', 0))}"


def build_single_snapshot(*, source_row: dict[str, Any], max_listing_entries: int = 5000) -> dict[str, Any]:
    target_path = _snapshot_target(_text(source_row.get("path")))
    snapshot_artifact = _text(source_row.get("snapshot_artifact"))
    listing: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    entry_count = 0
    file_count = 0
    dir_count = 0
    symlink_count = 0
    total_size_bytes = 0
    blockers: list[str] = []

    if not target_path.exists():
        blockers.append("target_path_missing")
    else:
        paths = [target_path]
        if target_path.is_dir():
            paths.extend(sorted(target_path.rglob("*"), key=lambda item: item.as_posix()))
        for path in paths:
            try:
                stat = path.lstat()
            except OSError as exc:
                blockers.append(f"stat_failed:{path}:{exc.__class__.__name__}")
                continue
            if path.is_symlink():
                kind = "symlink"
                symlink_count += 1
            elif path.is_dir():
                kind = "dir"
                dir_count += 1
            else:
                kind = "file"
                file_count += 1
                total_size_bytes += int(stat.st_size)
            entry_count += 1
            line = _entry_digest_line(target_path, path, stat, kind)
            digest.update(line.encode("utf-8"))
            digest.update(b"\n")
            if len(listing) < max_listing_entries:
                listing.append(
                    {
                        "relative_path": "." if path == target_path else Path(line.split("|", 2)[1]).as_posix(),
                        "kind": kind,
                        "size_bytes": int(stat.st_size),
                        "mtime_ns": int(stat.st_mtime_ns),
                    }
                )

    snapshot_payload = {
        "summary": {
            "packet_type": "cleanup_snapshot_artifact",
            "status": "cleanup_snapshot_artifact_ready" if not blockers else "blocked_cleanup_snapshot_artifact",
            "lane": _text(source_row.get("lane")),
            "recommended_action": _text(source_row.get("recommended_action")),
            "approval_token": _text(source_row.get("approval_token")),
            "snapshot_target_path": _text(source_row.get("path")),
            "snapshot_artifact": snapshot_artifact,
            "target_exists": target_path.exists(),
            "entry_count": entry_count,
            "file_count": file_count,
            "dir_count": dir_count,
            "symlink_count": symlink_count,
            "total_size_bytes": total_size_bytes,
            "total_size_gb": round(total_size_bytes / (1024**3), 3),
            "listing_entry_count": len(listing),
            "listing_truncated": entry_count > len(listing),
            "metadata_fingerprint_sha256": digest.hexdigest() if entry_count else "",
            "blocker_count": len(blockers),
            "snapshot_created": True,
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "blockers": blockers,
        "listing": listing,
    }
    if snapshot_artifact:
        _write_json(snapshot_artifact, snapshot_payload)
    return {
        "lane": _text(source_row.get("lane")),
        "path": _text(source_row.get("path")),
        "recommended_action": _text(source_row.get("recommended_action")),
        "approval_token": _text(source_row.get("approval_token")),
        "snapshot_artifact": snapshot_artifact,
        "snapshot_status": snapshot_payload["summary"]["status"],
        "entry_count": entry_count,
        "file_count": file_count,
        "dir_count": dir_count,
        "listing_truncated": entry_count > len(listing),
        "metadata_fingerprint_sha256": snapshot_payload["summary"]["metadata_fingerprint_sha256"],
        "snapshot_created": True,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_cleanup_snapshot_artifacts(
    *,
    cleanup_snapshot_preflight_packet: dict[str, Any],
    preflight_path: str = DEFAULT_SNAPSHOT_PREFLIGHT_JSON,
    max_listing_entries: int = 5000,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source_row in _rows(cleanup_snapshot_preflight_packet):
        if source_row.get("snapshot_required") is not True:
            continue
        rows.append(build_single_snapshot(source_row=source_row, max_listing_entries=max_listing_entries))

    set_digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: (_text(item.get("lane")), _text(item.get("recommended_action")), _text(item.get("path")))):
        set_digest.update(
            "|".join(
                [
                    _text(row.get("lane")),
                    _text(row.get("recommended_action")),
                    _text(row.get("path")),
                    _text(row.get("snapshot_artifact")),
                    _text(row.get("snapshot_status")),
                    _text(row.get("metadata_fingerprint_sha256")),
                    str(_int(row.get("entry_count"))),
                    str(_int(row.get("file_count"))),
                    str(_int(row.get("dir_count"))),
                    str(bool(row.get("listing_truncated") is True)),
                ]
            ).encode("utf-8")
        )
        set_digest.update(b"\n")

    summary = {
        "packet_type": "cleanup_snapshot_artifacts",
        "status": "cleanup_snapshot_artifacts_ready" if rows and all(row["snapshot_status"] == "cleanup_snapshot_artifact_ready" for row in rows) else "blocked_cleanup_snapshot_artifacts",
        "source_preflight_json": preflight_path,
        "source_preflight_status": _text(_summary(cleanup_snapshot_preflight_packet).get("status")),
        "snapshot_artifact_count": len(rows),
        "snapshot_ready_count": sum(1 for row in rows if row["snapshot_status"] == "cleanup_snapshot_artifact_ready"),
        "snapshot_blocked_count": sum(1 for row in rows if row["snapshot_status"] != "cleanup_snapshot_artifact_ready"),
        "listing_truncated_count": sum(1 for row in rows if row["listing_truncated"]),
        "total_entry_count": sum(_int(row.get("entry_count")) for row in rows),
        "total_file_count": sum(_int(row.get("file_count")) for row in rows),
        "total_dir_count": sum(_int(row.get("dir_count")) for row in rows),
        "snapshot_set_fingerprint_sha256": set_digest.hexdigest() if rows else "",
        "snapshot_created": bool(rows),
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Refresh cleanup snapshot preflight and inspect snapshot metadata before any cleanup approval is executed.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Snapshot Artifacts",
        "",
        f"- status: `{s['status']}`",
        f"- source_preflight_status: `{s['source_preflight_status']}`",
        f"- snapshot_artifact_count: `{s['snapshot_artifact_count']}`",
        f"- snapshot_ready_count: `{s['snapshot_ready_count']}`",
        f"- snapshot_blocked_count: `{s['snapshot_blocked_count']}`",
        f"- listing_truncated_count: `{s['listing_truncated_count']}`",
        f"- total_entry_count: `{s['total_entry_count']}`",
        f"- total_file_count: `{s['total_file_count']}`",
        f"- total_dir_count: `{s['total_dir_count']}`",
        f"- snapshot_set_fingerprint_sha256: `{s['snapshot_set_fingerprint_sha256']}`",
        f"- snapshot_created: `{s['snapshot_created']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Snapshots",
        "",
        "| lane | action | status | entries | files | truncated | artifact |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane']}` | `{row['recommended_action']}` | `{row['snapshot_status']}` | "
            f"`{row['entry_count']}` | `{row['file_count']}` | `{row['listing_truncated']}` | `{row['snapshot_artifact']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local cleanup snapshot artifacts without cleanup execution.")
    parser.add_argument("--cleanup-snapshot-preflight-json", default=DEFAULT_SNAPSHOT_PREFLIGHT_JSON)
    parser.add_argument("--max-listing-entries", type=int, default=5000)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_snapshot_artifacts(
        cleanup_snapshot_preflight_packet=_read_json_if_present(args.cleanup_snapshot_preflight_json),
        preflight_path=args.cleanup_snapshot_preflight_json,
        max_listing_entries=args.max_listing_entries,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
