#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_JSON = "runs/ligand_heavy_runs_cleanup_transition_dry_run_current.json"
DEFAULT_OUT_JSON = "runs/ligand_heavy_cleanup_approval_packet_current.json"
DEFAULT_OUT_CSV = "runs/ligand_heavy_cleanup_approval_packet_current.csv"
DEFAULT_OUT_MD = "runs/ligand_heavy_cleanup_approval_packet_current.md"
APPROVAL_TOKEN = "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS"
CLAIM_BOUNDARY = (
    "Ligand-heavy cleanup approval packet only; it summarizes dry-run deletion candidates. "
    "It does not delete, move, archive, upload, commit, push, or change scientific claims."
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


def _size_gb(size_bytes: Any) -> float:
    try:
        return round(float(size_bytes) / (1024**3), 3)
    except (TypeError, ValueError):
        return 0.0


def build_approval_packet(dry_run_payload: dict[str, Any], *, input_json: str = DEFAULT_INPUT_JSON) -> dict[str, Any]:
    summary = dry_run_payload.get("summary") if isinstance(dry_run_payload.get("summary"), dict) else {}
    rows = dry_run_payload.get("rows") if isinstance(dry_run_payload.get("rows"), list) else []
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "dry_run_delete":
            continue
        candidates.append(
            {
                "root": str(row.get("root", "")),
                "path": str(row.get("path", "")),
                "run_path": str(row.get("run_path", "")),
                "run_name": str(row.get("run_name", row.get("name", ""))),
                "payload_name": str(row.get("name", "")),
                "age_days": row.get("age_days", 0),
                "size_bytes": int(row.get("size_bytes", 0) or 0),
                "size_gb": _size_gb(row.get("size_bytes", 0)),
                "dry_run_status": str(row.get("status", "")),
                "dry_run_reason": str(row.get("reason", "")),
                "approval_token": APPROVAL_TOKEN,
                "deletion_scope": "payload_directory_only",
                "parent_run_preserved": True,
            }
        )
    total_bytes = sum(int(row["size_bytes"]) for row in candidates)
    dry_run_execute = bool(summary.get("execute", False))
    deleted_count = int(summary.get("deleted_count", 0) or 0)
    blockers: list[str] = []
    if dry_run_execute:
        blockers.append("source_report_was_not_dry_run")
    if deleted_count:
        blockers.append("source_report_already_deleted_payloads")
    if not candidates:
        blockers.append("no_dry_run_delete_candidates")
    status = "approval_packet_ready" if not blockers else "blocked_approval_packet"
    packet_summary = {
        "packet_type": "ligand_heavy_cleanup_approval_packet",
        "status": status,
        "source_dry_run_json": input_json,
        "source_status": str(summary.get("status", "")),
        "source_execute": dry_run_execute,
        "candidate_count": len(candidates),
        "planned_delete_count_from_source": int(summary.get("planned_delete_count", 0) or 0),
        "planned_delete_bytes_from_source": int(summary.get("planned_delete_bytes", 0) or 0),
        "candidate_bytes": total_bytes,
        "candidate_size_gb": _size_gb(total_bytes),
        "deleted_count_from_source": deleted_count,
        "approval_token_required": APPROVAL_TOKEN,
        "delete_executed": False,
        "external_state_mutated": False,
        "parent_runs_preserved": True,
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Review candidate rows and provide `{APPROVAL_TOKEN}` before running cleanup_ligand_heavy_runs.py with --execute."
            if status == "approval_packet_ready"
            else "Regenerate a clean dry-run report before requesting deletion approval."
        ),
    }
    return {"summary": packet_summary, "rows": candidates}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Ligand Heavy Cleanup Approval Packet",
        "",
        f"- status: `{s['status']}`",
        f"- source_dry_run_json: `{s['source_dry_run_json']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- candidate_size_gb: `{s['candidate_size_gb']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- parent_runs_preserved: `{s['parent_runs_preserved']}`",
        "",
        "## Candidates",
        "",
        "| run | payload | size_gb | age_days | path |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['run_name']}` | `{row['payload_name']}` | `{row['size_gb']}` | "
            f"`{row['age_days']}` | `{row['path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an approval packet from a ligand-heavy cleanup dry-run JSON.")
    parser.add_argument("--dry-run-json", default=DEFAULT_INPUT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_approval_packet(_read_json(args.dry_run_json), input_json=str(args.dry_run_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
