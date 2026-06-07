#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.cleanup_ligand_heavy_runs import PAYLOAD_DIR_NAMES

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTECTED_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_OUT_JSON = "runs/protected_ligand_heavy_payload_deep_review_current.json"
DEFAULT_OUT_CSV = "runs/protected_ligand_heavy_payload_deep_review_current.csv"
DEFAULT_OUT_MD = "runs/protected_ligand_heavy_payload_deep_review_current.md"

CLAIM_BOUNDARY = (
    "Protected ligand-heavy payload deep review only; it splits protected parent run directories into known payload "
    "children and preservation siblings for operator policy review. It does not promote protected rows to deletion, "
    "delete, move, archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
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


def _size_gb(size_bytes: int) -> float:
    return round(size_bytes / (1024**3), 3)


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _safe_children(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir(), key=lambda item: item.name)
    except OSError:
        return []


def _direct_payload_children(path: Path) -> list[Path]:
    return [child for child in _safe_children(path) if child.is_dir() and child.name.lower() in PAYLOAD_DIR_NAMES]


def _row(
    *,
    protected_path: Path,
    child_path: Path,
    child_role: str,
    size_bytes: int,
    source_row: dict[str, Any],
    present: bool,
) -> dict[str, Any]:
    return {
        "protected_path": str(protected_path),
        "child_path": str(child_path),
        "child_name": child_path.name,
        "child_role": child_role,
        "present": present,
        "size_bytes": size_bytes,
        "size_gb": _size_gb(size_bytes),
        "source_dry_run_status": _text(source_row.get("source_dry_run_status")),
        "source_dry_run_reason": _text(source_row.get("source_dry_run_reason")),
        "current_policy_action": _text(source_row.get("current_policy_action")) or "keep_protected",
        "policy_change_required_for_deletion": child_role == "known_payload_child",
        "approval_promoted": False,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_protected_ligand_heavy_payload_deep_review(
    protected_review_packet: dict[str, Any],
    *,
    protected_review_json: str = DEFAULT_PROTECTED_REVIEW_JSON,
) -> dict[str, Any]:
    protected = _summary(protected_review_packet)
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []

    if protected.get("status") != "protected_cleanup_payload_review_ready":
        blockers.append(
            {
                "code": "protected_cleanup_payload_review_not_ready",
                "severity": "hard",
                "reason": "Protected cleanup payload review must be ready before deep review.",
            }
        )

    for protected_row in _rows(protected_review_packet):
        protected_path = _resolve(_text(protected_row.get("path")))
        if not protected_path.exists():
            rows.append(
                _row(
                    protected_path=protected_path,
                    child_path=protected_path,
                    child_role="missing_protected_path",
                    size_bytes=0,
                    source_row=protected_row,
                    present=False,
                )
            )
            blockers.append(
                {
                    "code": "protected_path_missing",
                    "severity": "hard",
                    "reason": f"Protected review path is missing: {protected_path}",
                }
            )
            continue
        if protected_path.name.lower() in PAYLOAD_DIR_NAMES:
            rows.append(
                _row(
                    protected_path=protected_path,
                    child_path=protected_path,
                    child_role="known_payload_child",
                    size_bytes=_dir_size(protected_path),
                    source_row=protected_row,
                    present=True,
                )
            )
            continue
        payload_children = set(_direct_payload_children(protected_path))
        for child in _safe_children(protected_path):
            if not child.is_dir():
                continue
            role = "known_payload_child" if child in payload_children else "preservation_sibling"
            rows.append(
                _row(
                    protected_path=protected_path,
                    child_path=child,
                    child_role=role,
                    size_bytes=_dir_size(child),
                    source_row=protected_row,
                    present=True,
                )
            )
        if not payload_children:
            blockers.append(
                {
                    "code": "known_payload_child_missing",
                    "severity": "hard",
                    "reason": f"No direct known payload child was found under protected path: {protected_path}",
                }
            )

    rows.sort(key=lambda row: (-float(row["size_gb"]), row["protected_path"], row["child_path"]))
    payload_rows = [row for row in rows if row["child_role"] == "known_payload_child"]
    sibling_rows = [row for row in rows if row["child_role"] == "preservation_sibling"]
    summary = {
        "packet_type": "protected_ligand_heavy_payload_deep_review",
        "status": "protected_ligand_heavy_payload_deep_review_ready" if not blockers else "blocked_protected_ligand_heavy_payload_deep_review",
        "source_protected_review_json": protected_review_json,
        "source_protected_review_status": _text(protected.get("status")),
        "protected_payload_row_count": int(protected.get("protected_payload_row_count") or 0),
        "deep_review_row_count": len(rows),
        "known_payload_child_count": len(payload_rows),
        "known_payload_child_size_gb": round(sum(float(row["size_gb"]) for row in payload_rows), 3),
        "preservation_sibling_count": len(sibling_rows),
        "preservation_sibling_size_gb": round(sum(float(row["size_gb"]) for row in sibling_rows), 3),
        "largest_known_payload_child_size_gb": max((float(row["size_gb"]) for row in payload_rows), default=0.0),
        "policy_change_required_for_deletion_count": len(payload_rows),
        "approval_promoted_count": 0,
        "blocker_count": len(blockers),
        "delete_enabled": False,
        "delete_executed": False,
        "action_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this split to decide whether protected known payload children should remain kept or receive an explicit policy-change request."
            if not blockers
            else "Repair missing protected paths or payload-child classification before any protected cleanup policy decision."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Protected Ligand Heavy Payload Deep Review",
        "",
        f"- status: `{s['status']}`",
        f"- known_payload_child_count: `{s['known_payload_child_count']}`",
        f"- known_payload_child_size_gb: `{s['known_payload_child_size_gb']}`",
        f"- preservation_sibling_count: `{s['preservation_sibling_count']}`",
        f"- preservation_sibling_size_gb: `{s['preservation_sibling_size_gb']}`",
        f"- largest_known_payload_child_size_gb: `{s['largest_known_payload_child_size_gb']}`",
        f"- policy_change_required_for_deletion_count: `{s['policy_change_required_for_deletion_count']}`",
        f"- approval_promoted_count: `{s['approval_promoted_count']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| role | size_gb | dry_run_status | policy_change_for_deletion | child_path |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['child_role']}` | `{row['size_gb']}` | `{row['source_dry_run_status']}` | "
            f"`{row['policy_change_required_for_deletion']}` | `{row['child_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deep-review protected ligand-heavy payload rows without cleanup execution.")
    parser.add_argument("--protected-review-json", default=DEFAULT_PROTECTED_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_protected_ligand_heavy_payload_deep_review(
        _read_json(args.protected_review_json),
        protected_review_json=str(args.protected_review_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
