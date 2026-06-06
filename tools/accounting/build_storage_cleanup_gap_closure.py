#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESIDUAL_JSON = "runs/storage_residual_cleanup_status_current.json"
DEFAULT_COMPLETION_JSON = "runs/cleanup_completion_gate_current.json"
DEFAULT_OUT_JSON = "runs/storage_cleanup_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/storage_cleanup_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/storage_cleanup_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Storage cleanup gap closure status only; it audits residual storage status and cleanup completion gate "
    "readiness without executing delete/archive/externalize. delete_executed remains false unless separate "
    "operator-approved cleanup evidence exists."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _row(gap_id: str, gap: str, status: str, evidence: str, observed: str, next_action: str) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "gap": gap,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_storage_cleanup_gap_closure(
    *,
    residual_packet: dict[str, Any] | None = None,
    completion_gate_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    residual = _summary(residual_packet or _read_json_if_present(DEFAULT_RESIDUAL_JSON))
    completion = _summary(completion_gate_packet or _read_json_if_present(DEFAULT_COMPLETION_JSON))
    residual_ready = _resolve("tools/product/build_storage_residual_cleanup_status.py").exists() and bool(residual)
    operator_action_candidates = _int(residual.get("operator_action_candidate_count"))
    completion_ready = completion.get("status") == "cleanup_completion_gate_ready" or completion.get("cleanup_complete") is True
    postcheck_ready = completion.get("postcheck_contract_ready") is True or _resolve("tools/accounting/build_cleanup_postcheck_contract.py").exists()
    execution_scaffold_ready = _resolve("tools/accounting/build_cleanup_execution_approval_gate.py").exists()
    storage_status_closed = residual_ready and operator_action_candidates == 0
    cleanup_execution_closed = completion_ready or (postcheck_ready and execution_scaffold_ready and operator_action_candidates == 0)

    rows = [
        _row(
            "STOR-RESIDUAL",
            "Storage residual status tracking",
            "closed" if storage_status_closed else "open",
            DEFAULT_RESIDUAL_JSON,
            f"residual_ready={residual_ready}; operator_action_candidate_count={operator_action_candidates}",
            "Maintain residual status builder and keep heavy operator-action candidates at zero unless approved.",
        ),
        _row(
            "STOR-EXEC",
            "Cleanup execution approval/completion scaffold",
            "closed" if cleanup_execution_closed else "open",
            DEFAULT_COMPLETION_JSON,
            f"completion_status={completion.get('status')}; delete_executed=false",
            "Run operator-approved cleanup execution in a separate step; keep delete_executed=false here.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "storage_cleanup_gap_closure",
        "status": "storage_cleanup_gap_closure_complete" if not open_rows else "blocked_storage_cleanup_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "closed_gap_ids": [row["gap_id"] for row in closed_rows],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap_id": first_open["gap_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All storage cleanup boundary gaps are closed.",
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Storage Cleanup Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build storage cleanup gap closure status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_storage_cleanup_gap_closure()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
