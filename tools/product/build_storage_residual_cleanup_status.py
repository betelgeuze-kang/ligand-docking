#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/storage_residual_cleanup_status_current.json"
DEFAULT_OUT_CSV = "runs/storage_residual_cleanup_status_current.csv"
DEFAULT_OUT_MD = "runs/storage_residual_cleanup_status_current.md"

DEFAULT_TARGETS = (
    ("runs", "keep_inventory", "large generated run history; do not delete wholesale"),
    ("casp17", "keep_curated_outputs", "CASP17 curated target/object/viewer state"),
    ("models", "keep_model_assets", "model assets require registry/provenance review"),
    ("data", "keep_data_assets", "input/reference data require provenance review"),
    ("casp17/massivefold_external_pool_intake", "externalize_or_archive", "transient MassiveFold external pool"),
    ("runs/archive", "inventory_then_archive_or_delete", "legacy archived run payloads"),
    ("rust_engine/target", "delete_regenerable_build_artifact", "regenerable Rust build artifact"),
    (".venv", "delete_regenerable_local_environment", "regenerable local virtualenv"),
    ("runs/local_heavy_runs", "review_then_archive_or_delete", "local heavy-run staging area"),
)

CLAIM_BOUNDARY = (
    "Storage residual cleanup status only; it measures selected local paths and records cleanup recommendations. "
    "It does not delete, move, archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        result = subprocess.run(["du", "-sb", str(path)], check=True, capture_output=True, text=True)
        return int(result.stdout.split()[0])
    except (OSError, subprocess.CalledProcessError, IndexError, ValueError):
        if path.is_file():
            return path.stat().st_size
        total = 0
        for child in path.rglob("*"):
            try:
                if child.is_file() or child.is_symlink():
                    total += child.lstat().st_size
            except OSError:
                continue
        return total


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def _status_for(path_exists: bool, size_bytes: int, action: str, heavy_threshold_bytes: int) -> str:
    if not path_exists:
        return "resolved_missing"
    if action.startswith("keep_"):
        return "tracked_keep"
    if size_bytes >= heavy_threshold_bytes:
        return "operator_action_candidate"
    return "small_residual_review"


def build_storage_residual_cleanup_status(
    *,
    root: str | Path = ROOT,
    heavy_threshold_bytes: int = 100 * 1024 * 1024,
    targets: tuple[tuple[str, str, str], ...] = DEFAULT_TARGETS,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    disk = shutil.disk_usage(root_path)
    rows: list[dict[str, Any]] = []
    for rel_path, recommended_action, reason in targets:
        path = root_path / rel_path
        exists = path.exists()
        size = _size_bytes(path)
        status = _status_for(exists, size, recommended_action, heavy_threshold_bytes)
        rows.append(
            {
                "path": rel_path,
                "exists": exists,
                "size_bytes": size,
                "size_human": _human_size(size),
                "status": status,
                "recommended_action": recommended_action,
                "operator_approval_required": bool(exists and not recommended_action.startswith("keep_")),
                "reason": reason,
                "delete_executed": False,
                "archive_executed": False,
                "externalize_executed": False,
                "external_state_mutated": False,
            }
        )
    action_candidates = [row for row in rows if row["status"] == "operator_action_candidate"]
    resolved_missing = [row for row in rows if row["status"] == "resolved_missing"]
    existing_bytes = sum(int(row["size_bytes"]) for row in rows if row["exists"])
    candidate_bytes = sum(int(row["size_bytes"]) for row in action_candidates)
    summary = {
        "packet_type": "storage_residual_cleanup_status",
        "status": "storage_residual_cleanup_status_ready",
        "target_path_count": len(rows),
        "existing_path_count": sum(1 for row in rows if row["exists"]),
        "resolved_missing_path_count": len(resolved_missing),
        "operator_action_candidate_count": len(action_candidates),
        "operator_approval_required_count": sum(1 for row in rows if row["operator_approval_required"]),
        "existing_target_bytes": existing_bytes,
        "existing_target_human": _human_size(existing_bytes),
        "operator_action_candidate_bytes": candidate_bytes,
        "operator_action_candidate_human": _human_size(candidate_bytes),
        "heavy_threshold_bytes": heavy_threshold_bytes,
        "filesystem_total_bytes": disk.total,
        "filesystem_used_bytes": disk.used,
        "filesystem_free_bytes": disk.free,
        "filesystem_used_percent": round((disk.used / disk.total) * 100, 2) if disk.total else 0.0,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review operator_action_candidate rows, then run a separately approved cleanup/externalize plan if needed."
            if action_candidates
            else "No heavy cleanup target in this tracked set currently requires operator action."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Storage Residual Cleanup Status",
        "",
        f"- status: `{s['status']}`",
        f"- target_path_count: `{s['target_path_count']}`",
        f"- existing_path_count: `{s['existing_path_count']}`",
        f"- resolved_missing_path_count: `{s['resolved_missing_path_count']}`",
        f"- operator_action_candidate_count: `{s['operator_action_candidate_count']}`",
        f"- operator_action_candidate_human: `{s['operator_action_candidate_human']}`",
        f"- filesystem_used_percent: `{s['filesystem_used_percent']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- archive_executed: `{s['archive_executed']}`",
        f"- externalize_executed: `{s['externalize_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Paths",
        "",
        "| path | exists | size | status | action | approval |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['exists']}` | `{row['size_human']}` | `{row['status']}` | "
            f"`{row['recommended_action']}` | `{row['operator_approval_required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only residual storage cleanup status for selected heavy paths.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--heavy-threshold-bytes", type=int, default=100 * 1024 * 1024)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_storage_residual_cleanup_status(root=args.root, heavy_threshold_bytes=args.heavy_threshold_bytes)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
