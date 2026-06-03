#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cleanup_execution_approval_gate import DEFAULT_OUT_JSON as DEFAULT_APPROVAL_GATE_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIGAND_EXECUTE_JSON = "runs/ligand_heavy_cleanup_execute_after_approval.json"
DEFAULT_EXTERNALIZED_ROOT = "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/cleanup_externalized/2026-06-03_goal_cleanup"
DEFAULT_OUT_JSON = "runs/cleanup_execution_completion_evidence_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_execution_completion_evidence_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_execution_completion_evidence_current.md"

CLAIM_BOUNDARY = (
    "Cleanup execution completion evidence only; it verifies approved cleanup rows against current local/external "
    "filesystem state and the ligand-heavy execute receipt. It does not delete, move, archive, externalize, upload, "
    "commit, push, or mutate external state."
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
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


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


def _externalized_destination(source_path: str, externalized_root: str | Path) -> Path:
    source = Path(source_path)
    parts = source.parts
    if len(parts) >= 2 and parts[-2:] == ("runs", "archive"):
        name = "runs_archive"
    elif len(parts) >= 2 and parts[-2:] == ("casp17", "massivefold_external_pool_intake"):
        name = "casp17_massivefold_external_pool_intake"
    else:
        name = source.name
    return Path(externalized_root).expanduser().resolve() / name


def _row(
    *,
    lane: str,
    action: str,
    path: str,
    completion_status: str,
    observed: str,
    required: str,
    size_gb: float,
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "lane": lane,
        "recommended_action": action,
        "path": path,
        "completion_status": completion_status,
        "observed": observed,
        "required": required,
        "size_gb": round(size_gb, 3),
        "blockers": ",".join(blockers),
        "execution_enabled": False,
        "delete_executed": completion_status == "complete" and action in {"delete_candidate", "delete_stale_stage2_trajectory_payloads_after_approval"},
        "archive_executed": completion_status == "complete" and action == "archive",
        "externalize_executed": completion_status == "complete" and action == "externalize",
        "external_state_mutated": completion_status == "complete",
    }


def build_cleanup_execution_completion_evidence(
    *,
    approval_gate_packet: dict[str, Any],
    ligand_execute_packet: dict[str, Any],
    externalized_root: str | Path = DEFAULT_EXTERNALIZED_ROOT,
) -> dict[str, Any]:
    approval = _summary(approval_gate_packet)
    ligand_execute = _summary(ligand_execute_packet)
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []

    if _text(approval.get("status")) != "cleanup_execution_operator_approval_gate_ready":
        blockers.append("cleanup_execution_operator_approval_gate_not_ready")

    authorized_rows = [row for row in _rows(approval_gate_packet) if _text(row.get("approval_gate_status")) == "authorized_for_operator_execution"]
    if not authorized_rows:
        blockers.append("authorized_cleanup_rows_missing")

    ligand_receipt_complete = (
        _text(ligand_execute.get("status")) == "cleanup_executed"
        and _int(ligand_execute.get("planned_delete_count")) > 0
        and _int(ligand_execute.get("deleted_count")) == _int(ligand_execute.get("planned_delete_count"))
        and _int(ligand_execute.get("deleted_bytes")) == _int(ligand_execute.get("planned_delete_bytes"))
    )

    for source in authorized_rows:
        lane = _text(source.get("lane"))
        action = _text(source.get("recommended_action"))
        path_text = _text(source.get("path"))
        source_path = _resolve(path_text)
        row_blockers: list[str] = []
        observed_parts: list[str] = []
        required = ""

        if action in {"delete_candidate"}:
            exists_now = source_path.exists()
            observed_parts.append(f"source_exists={exists_now}")
            required = "source_exists=false"
            if exists_now:
                row_blockers.append("delete_candidate_source_still_exists")
        elif action in {"externalize", "archive"}:
            dest = _externalized_destination(path_text, externalized_root)
            source_exists = source_path.exists()
            dest_exists = dest.exists()
            observed_parts.append(f"source_exists={source_exists}")
            observed_parts.append(f"destination_exists={dest_exists}")
            observed_parts.append(f"destination={dest}")
            required = "source_exists=false;destination_exists=true"
            if source_exists:
                row_blockers.append("moved_source_still_exists")
            if not dest_exists:
                row_blockers.append("externalized_destination_missing")
        elif lane == "ligand_heavy_cleanup":
            observed_parts.append(f"execute_status={_text(ligand_execute.get('status')) or 'missing'}")
            observed_parts.append(f"deleted_count={_int(ligand_execute.get('deleted_count'))}")
            observed_parts.append(f"planned_delete_count={_int(ligand_execute.get('planned_delete_count'))}")
            observed_parts.append(f"deleted_bytes={_int(ligand_execute.get('deleted_bytes'))}")
            required = "cleanup_executed;deleted_count=planned_delete_count;deleted_bytes=planned_delete_bytes"
            if not ligand_receipt_complete:
                row_blockers.append("ligand_heavy_execute_receipt_incomplete")
        else:
            required = "approved cleanup row has row-specific completion evidence"
            row_blockers.append("unknown_completion_action")

        rows.append(
            _row(
                lane=lane,
                action=action,
                path=path_text,
                completion_status="blocked" if row_blockers else "complete",
                observed=";".join(observed_parts),
                required=required,
                size_gb=_float(source.get("size_gb")),
                blockers=row_blockers,
            )
        )
        blockers.extend(row_blockers)

    transition_rows = [row for row in rows if row["lane"] in {"casp17_external_pool", "legacy_runs_archive", "build_output", "local_environment"}]
    ligand_rows = [row for row in rows if row["lane"] == "ligand_heavy_cleanup"]
    transition_complete = bool(transition_rows) and all(row["completion_status"] == "complete" for row in transition_rows)
    ligand_complete = bool(ligand_rows) and all(row["completion_status"] == "complete" for row in ligand_rows)
    complete = bool(rows) and transition_complete and ligand_complete and not blockers
    summary = {
        "packet_type": "cleanup_execution_completion_evidence",
        "status": "cleanup_execution_completion_evidence_ready" if complete else "blocked_cleanup_execution_completion_evidence",
        "completion_evidence_ready": complete,
        "row_count": len(rows),
        "complete_row_count": sum(1 for row in rows if row["completion_status"] == "complete"),
        "blocked_row_count": sum(1 for row in rows if row["completion_status"] != "complete"),
        "transition_cleanup_complete": transition_complete,
        "ligand_heavy_cleanup_complete": ligand_complete,
        "ligand_execute_status": _text(ligand_execute.get("status")),
        "ligand_deleted_count": _int(ligand_execute.get("deleted_count")),
        "ligand_deleted_bytes": _int(ligand_execute.get("deleted_bytes")),
        "authorized_reclaim_size_gb": round(sum(_float(row.get("size_gb")) for row in authorized_rows), 3),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "delete_executed": complete,
        "archive_executed": transition_complete,
        "externalize_executed": transition_complete,
        "external_state_mutated": complete,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Cleanup execution completion evidence is ready; refresh cleanup completion and release gates."
            if complete
            else "Repair missing source/destination/execute-receipt evidence before claiming cleanup completion."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": [{"code": code, "severity": "hard", "reason": code} for code in sorted(set(blockers))]}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Execution Completion Evidence",
        "",
        f"- status: `{s['status']}`",
        f"- completion_evidence_ready: `{s['completion_evidence_ready']}`",
        f"- transition_cleanup_complete: `{s['transition_cleanup_complete']}`",
        f"- ligand_heavy_cleanup_complete: `{s['ligand_heavy_cleanup_complete']}`",
        f"- complete_row_count: `{s['complete_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- authorized_reclaim_size_gb: `{s['authorized_reclaim_size_gb']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- archive_executed: `{s['archive_executed']}`",
        f"- externalize_executed: `{s['externalize_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| status | lane | action | size_gb | observed | required | path | blockers |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['completion_status']}` | `{row['lane']}` | `{row['recommended_action']}` | "
            f"`{row['size_gb']}` | `{row['observed']}` | `{row['required']}` | `{row['path']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cleanup execution completion evidence from current state.")
    parser.add_argument("--approval-gate-json", default=DEFAULT_APPROVAL_GATE_JSON)
    parser.add_argument("--ligand-execute-json", default=DEFAULT_LIGAND_EXECUTE_JSON)
    parser.add_argument("--externalized-root", default=DEFAULT_EXTERNALIZED_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_execution_completion_evidence(
        approval_gate_packet=_read_json_if_present(args.approval_gate_json),
        ligand_execute_packet=_read_json_if_present(args.ligand_execute_json),
        externalized_root=args.externalized_root,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
