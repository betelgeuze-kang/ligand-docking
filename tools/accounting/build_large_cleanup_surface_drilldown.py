#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_ligand_heavy_cleanup_approval_packet import DEFAULT_INPUT_JSON as DEFAULT_LIGAND_HEAVY_DRY_RUN_JSON
from tools.cleanup_ligand_heavy_runs import PAYLOAD_DIR_NAMES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTION_BOARD_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_OUT_JSON = "runs/large_cleanup_surface_drilldown_current.json"
DEFAULT_OUT_CSV = "runs/large_cleanup_surface_drilldown_current.csv"
DEFAULT_OUT_MD = "runs/large_cleanup_surface_drilldown_current.md"

CLAIM_BOUNDARY = (
    "Large cleanup surface drilldown only; it inspects review-only cleanup surfaces and known local payload directories. "
    "It does not delete, move, archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _size_gb(size_bytes: Any) -> float:
    try:
        return round(float(size_bytes or 0) / (1024**3), 3)
    except (TypeError, ValueError):
        return 0.0


def _dir_size(path: Path) -> int:
    try:
        output = subprocess.check_output(["du", "-sb", str(path)], text=True)
        return int(output.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                continue
        return total


def _safe_iterdir(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir(), key=lambda item: item.name)
    except OSError:
        return []


def _payload_children(path: Path) -> list[Path]:
    return [child for child in _safe_iterdir(path) if child.is_dir() and child.name.lower() in PAYLOAD_DIR_NAMES]


def _surface_rows(action_board: dict[str, Any]) -> list[dict[str, Any]]:
    rows = action_board.get("rows") if isinstance(action_board.get("rows"), list) else []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("action_type") == "review_large_cleanup_surface"
        and row.get("status") == "review_required"
    ]


def _dry_run_lookup(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    return {str(row.get("path", "")).strip(): row for row in rows if isinstance(row, dict) and str(row.get("path", "")).strip()}


def _row(
    *,
    surface_path: str,
    surface_size_gb: float,
    path: Path,
    scope: str,
    size_bytes: int,
    status: str,
    recommended_next_action: str,
    reason: str,
    payload_count: int = 0,
    payload_size_bytes: int = 0,
    source_dry_run_status: str = "",
    source_dry_run_reason: str = "",
) -> dict[str, Any]:
    return {
        "surface_path": surface_path,
        "surface_size_gb": round(surface_size_gb, 3),
        "path": str(path),
        "name": path.name,
        "scope": scope,
        "status": status,
        "size_bytes": size_bytes,
        "size_gb": _size_gb(size_bytes),
        "known_payload_count": payload_count,
        "known_payload_size_bytes": payload_size_bytes,
        "known_payload_size_gb": _size_gb(payload_size_bytes),
        "recommended_next_action": recommended_next_action,
        "reason": reason,
        "source_dry_run_status": source_dry_run_status,
        "source_dry_run_reason": source_dry_run_reason,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_drilldown(
    action_board: dict[str, Any],
    *,
    ligand_heavy_dry_run_packet: dict[str, Any] | None = None,
    action_board_json: str = DEFAULT_ACTION_BOARD_JSON,
    ligand_heavy_dry_run_json: str = DEFAULT_LIGAND_HEAVY_DRY_RUN_JSON,
    max_children_per_surface: int = 500,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    surfaces = _surface_rows(action_board)
    dry_run_rows_by_path = _dry_run_lookup(ligand_heavy_dry_run_packet or {})
    if not surfaces:
        blockers.append({"code": "large_review_surfaces_missing", "severity": "soft", "reason": "No review_large_cleanup_surface rows were present."})

    for surface in surfaces:
        surface_path_text = _text(surface.get("artifact_path"))
        surface_size_gb = _float(surface.get("size_gb"))
        surface_path = _resolve(surface_path_text)
        if not surface_path.exists():
            rows.append(
                _row(
                    surface_path=surface_path_text,
                    surface_size_gb=surface_size_gb,
                    path=surface_path,
                    scope="surface",
                    size_bytes=0,
                    status="missing_refresh_required",
                    recommended_next_action="refresh_transition_cleanup_preflight",
                    reason="Review surface no longer exists on disk.",
                )
            )
            continue
        if surface_path.name.lower() in PAYLOAD_DIR_NAMES:
            size_bytes = _dir_size(surface_path)
            source_row = dry_run_rows_by_path.get(str(surface_path), {})
            rows.append(
                _row(
                    surface_path=surface_path_text,
                    surface_size_gb=surface_size_gb,
                    path=surface_path,
                    scope="known_payload_surface",
                    size_bytes=size_bytes,
                    status="narrow_payload_candidate",
                    recommended_next_action="convert_to_payload-only approval candidate after operator review",
                    reason="The review surface itself is a known heavy payload directory.",
                    payload_count=1,
                    payload_size_bytes=size_bytes,
                    source_dry_run_status=_text(source_row.get("status")),
                    source_dry_run_reason=_text(source_row.get("reason")),
                )
            )
            continue
        children = [child for child in _safe_iterdir(surface_path) if child.is_dir()]
        if len(children) > max_children_per_surface:
            blockers.append(
                {
                    "code": "surface_child_count_truncated",
                    "severity": "soft",
                    "reason": f"{surface_path} has {len(children)} children; only {max_children_per_surface} were inspected.",
                }
            )
        for child in children[:max_children_per_surface]:
            payloads = _payload_children(child)
            payload_sizes = [_dir_size(payload) for payload in payloads]
            source_rows = [dry_run_rows_by_path.get(str(payload), {}) for payload in payloads]
            source_statuses = sorted({_text(row.get("status")) for row in source_rows if _text(row.get("status"))})
            source_reasons = sorted({_text(row.get("reason")) for row in source_rows if _text(row.get("reason"))})
            child_size = _dir_size(child)
            if payloads:
                if "dry_run_delete" in source_statuses:
                    status = "known_payloads_found"
                    recommended = "route payload rows through approval-gated cleanup packet"
                    reason = "Child run contains dry-run delete payload rows while preserving the parent run directory."
                elif source_statuses:
                    status = "known_payloads_protected_by_dry_run"
                    recommended = "review dry-run protection reason before changing cleanup policy"
                    reason = "Child run contains known heavy payload directories, but the current dry-run protects them."
                else:
                    status = "known_payloads_found"
                    recommended = "route child root through cleanup_ligand_heavy_runs.py dry-run before approval"
                    reason = "Child run contains known heavy payload directories while preserving the parent run directory."
            else:
                status = "review_no_known_payload"
                recommended = "manual review or narrower classifier required"
                reason = "No direct known heavy payload directory was found under this child."
            rows.append(
                _row(
                    surface_path=surface_path_text,
                    surface_size_gb=surface_size_gb,
                    path=child,
                    scope="surface_child",
                    size_bytes=child_size,
                    status=status,
                    recommended_next_action=recommended,
                    reason=reason,
                    payload_count=len(payloads),
                    payload_size_bytes=sum(payload_sizes),
                    source_dry_run_status=";".join(source_statuses),
                    source_dry_run_reason=";".join(source_reasons),
                )
            )

    rows.sort(key=lambda row: (-float(row["known_payload_size_gb"]), -float(row["size_gb"]), row["surface_path"], row["path"]))
    known_payload_rows = [row for row in rows if int(row["known_payload_count"]) > 0]
    protected_rows = [row for row in rows if "kept_" in str(row.get("source_dry_run_status", ""))]
    dry_run_delete_rows = [row for row in rows if "dry_run_delete" in str(row.get("source_dry_run_status", ""))]
    summary = {
        "packet_type": "large_cleanup_surface_drilldown",
        "status": "large_cleanup_surface_drilldown_ready",
        "source_action_board_json": action_board_json,
        "source_ligand_heavy_dry_run_json": ligand_heavy_dry_run_json,
        "surface_count": len(surfaces),
        "row_count": len(rows),
        "known_payload_row_count": len(known_payload_rows),
        "known_payload_total_size_gb": round(sum(float(row["known_payload_size_gb"]) for row in rows), 3),
        "dry_run_delete_payload_row_count": len(dry_run_delete_rows),
        "dry_run_delete_payload_size_gb": round(sum(float(row["known_payload_size_gb"]) for row in dry_run_delete_rows), 3),
        "dry_run_protected_payload_row_count": len(protected_rows),
        "dry_run_protected_payload_size_gb": round(sum(float(row["known_payload_size_gb"]) for row in protected_rows), 3),
        "largest_row_size_gb": max((float(row["size_gb"]) for row in rows), default=0.0),
        "largest_known_payload_size_gb": max((float(row["known_payload_size_gb"]) for row in rows), default=0.0),
        "blocker_count": len(blockers),
        "delete_enabled": False,
        "delete_executed": False,
        "action_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review dry-run protected payload rows separately before changing cleanup policy; feed only dry_run_delete payload rows into approval-gated cleanup packets."
            if protected_rows or dry_run_delete_rows
            else "Add a narrower classifier or manual review for these large cleanup surfaces."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Large Cleanup Surface Drilldown",
        "",
        f"- status: `{s['status']}`",
        f"- surface_count: `{s['surface_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- known_payload_row_count: `{s['known_payload_row_count']}`",
        f"- known_payload_total_size_gb: `{s['known_payload_total_size_gb']}`",
        f"- dry_run_delete_payload_size_gb: `{s['dry_run_delete_payload_size_gb']}`",
        f"- dry_run_protected_payload_size_gb: `{s['dry_run_protected_payload_size_gb']}`",
        f"- largest_row_size_gb: `{s['largest_row_size_gb']}`",
        f"- largest_known_payload_size_gb: `{s['largest_known_payload_size_gb']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Top Rows",
        "",
        "| status | dry-run | scope | size_gb | known_payload_size_gb | payloads | path | next |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"][:40]:
        lines.append(
            f"| `{row['status']}` | `{row['source_dry_run_status']}` | `{row['scope']}` | `{row['size_gb']}` | `{row['known_payload_size_gb']}` | "
            f"`{row['known_payload_count']}` | `{row['path']}` | {row['recommended_next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drill into large review-only cleanup surfaces without deleting anything.")
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--ligand-heavy-dry-run-json", default=DEFAULT_LIGAND_HEAVY_DRY_RUN_JSON)
    parser.add_argument("--max-children-per-surface", type=int, default=500)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_drilldown(
        _read_json(args.action_board_json),
        ligand_heavy_dry_run_packet=_read_json_if_present(args.ligand_heavy_dry_run_json),
        action_board_json=str(args.action_board_json),
        ligand_heavy_dry_run_json=str(args.ligand_heavy_dry_run_json),
        max_children_per_surface=args.max_children_per_surface,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
