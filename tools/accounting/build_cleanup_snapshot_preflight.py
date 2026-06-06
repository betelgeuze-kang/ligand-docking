#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON = "runs/transition_cleanup_work_order_current.json"
DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_SNAPSHOT_DIR = "runs/cleanup_snapshots"
DEFAULT_OUT_JSON = "runs/cleanup_snapshot_preflight_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_snapshot_preflight_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_snapshot_preflight_current.md"

CLAIM_BOUNDARY = (
    "Cleanup snapshot preflight only; it checks whether approval-gated cleanup rows have a reviewable snapshot/listing "
    "or frozen candidate manifest before execution. It does not create snapshots, delete, move, archive, externalize, upload, "
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


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().strip("/"))
    slug = re.sub(r"_+", "_", slug).strip("._")
    return slug[:120] or "root"


def _snapshot_path(snapshot_dir: str, *, lane: str, action: str, path: str) -> str:
    return str(Path(snapshot_dir) / f"{_slug(lane)}__{_slug(action)}__{_slug(path)}.snapshot.json")


def _row(
    *,
    source_artifact: str,
    lane: str,
    path: str,
    recommended_action: str,
    approval_token: str,
    size_gb: float,
    snapshot_artifact: str,
    snapshot_required: bool,
    snapshot_present: bool,
    frozen_manifest_present: bool,
    postcheck: str,
    status: str,
    blockers: str = "",
) -> dict[str, Any]:
    return {
        "source_artifact": source_artifact,
        "lane": lane,
        "path": path,
        "recommended_action": recommended_action,
        "approval_token": approval_token,
        "size_gb": round(size_gb, 3),
        "snapshot_artifact": snapshot_artifact,
        "snapshot_required": snapshot_required,
        "snapshot_present": snapshot_present,
        "frozen_manifest_present": frozen_manifest_present,
        "postcheck": postcheck,
        "preflight_status": status,
        "blockers": blockers,
        "snapshot_created": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_cleanup_snapshot_preflight(
    *,
    transition_cleanup_work_order_packet: dict[str, Any],
    ligand_cleanup_preflight_packet: dict[str, Any],
    ligand_cleanup_work_order_packet: dict[str, Any],
    transition_cleanup_work_order_path: str = DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON,
    ligand_cleanup_preflight_path: str = DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON,
    ligand_cleanup_work_order_path: str = DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON,
    snapshot_dir: str = DEFAULT_SNAPSHOT_DIR,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for source_row in _rows(transition_cleanup_work_order_packet):
        if _text(source_row.get("work_order_status")) != "approval_gated":
            continue
        lane = _text(source_row.get("lane"))
        action = _text(source_row.get("recommended_action"))
        path = _text(source_row.get("path"))
        snapshot_required = action in {"archive", "externalize"}
        snapshot_artifact = _snapshot_path(snapshot_dir, lane=lane, action=action, path=path)
        snapshot_present = _resolve(snapshot_artifact).exists()
        blockers: list[str] = []
        if snapshot_required and not snapshot_present:
            blockers.append("snapshot_artifact_missing")
        status = "pass" if not blockers else "blocked"
        rows.append(
            _row(
                source_artifact=transition_cleanup_work_order_path,
                lane=lane,
                path=path,
                recommended_action=action,
                approval_token=_text(source_row.get("approval_token")),
                size_gb=_float(source_row.get("size_gb")),
                snapshot_artifact=snapshot_artifact,
                snapshot_required=snapshot_required,
                snapshot_present=snapshot_present,
                frozen_manifest_present=bool(transition_cleanup_work_order_packet),
                postcheck=_text(source_row.get("postcheck")),
                status=status,
                blockers=",".join(blockers),
            )
        )

    ligand_summary = _summary(ligand_cleanup_preflight_packet)
    ligand_work_order = _summary(ligand_cleanup_work_order_packet)
    ligand_ready = ligand_summary.get("status") == "ligand_heavy_cleanup_execution_preflight_ready"
    ligand_candidate_count = _int(ligand_summary.get("existing_candidate_count") or ligand_summary.get("candidate_count"))
    if ligand_cleanup_preflight_packet or ligand_cleanup_work_order_packet:
        snapshot_artifact = str(Path(snapshot_dir) / "ligand_heavy_cleanup_candidates.snapshot.json")
        snapshot_present = _resolve(snapshot_artifact).exists()
        frozen_manifest_present = ligand_ready and ligand_candidate_count > 0 and bool(_rows(ligand_cleanup_preflight_packet))
        blockers = []
        if not frozen_manifest_present:
            blockers.append("ligand_cleanup_candidate_manifest_missing_or_empty")
        status = "pass" if not blockers else "blocked"
        rows.append(
            _row(
                source_artifact=f"{ligand_cleanup_preflight_path};{ligand_cleanup_work_order_path}",
                lane="ligand_heavy_cleanup",
                path=_text(ligand_work_order.get("source_approval_json")) or ligand_cleanup_preflight_path,
                recommended_action="delete_stale_stage2_trajectory_payloads_after_approval",
                approval_token=_text(ligand_summary.get("approval_token_required") or ligand_work_order.get("approval_token_required")),
                size_gb=_float(ligand_summary.get("candidate_size_gb")),
                snapshot_artifact=snapshot_artifact,
                snapshot_required=False,
                snapshot_present=snapshot_present,
                frozen_manifest_present=frozen_manifest_present,
                postcheck="rerun cleanup dry-run and focused release gates after approved deletion",
                status=status,
                blockers=",".join(blockers),
            )
        )

    blocked_count = sum(1 for row in rows if row["preflight_status"] == "blocked")
    snapshot_required_count = sum(1 for row in rows if row["snapshot_required"])
    snapshot_missing_count = sum(1 for row in rows if row["snapshot_required"] and not row["snapshot_present"])
    approval_token_count = len({_text(row.get("approval_token")) for row in rows if _text(row.get("approval_token"))})
    summary = {
        "packet_type": "cleanup_snapshot_preflight",
        "status": "cleanup_snapshot_preflight_ready" if blocked_count == 0 else "blocked_cleanup_snapshot_preflight",
        "source_transition_cleanup_work_order_status": _text(_summary(transition_cleanup_work_order_packet).get("status")),
        "source_ligand_cleanup_preflight_status": _text(ligand_summary.get("status")),
        "row_count": len(rows),
        "blocked_row_count": blocked_count,
        "snapshot_required_count": snapshot_required_count,
        "snapshot_missing_count": snapshot_missing_count,
        "frozen_manifest_ready_count": sum(1 for row in rows if row["frozen_manifest_present"]),
        "approval_token_count": approval_token_count,
        "approval_gated_size_gb": round(sum(_float(row.get("size_gb")) for row in rows), 3),
        "snapshot_created": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Create/review missing snapshot artifacts for archive/externalize rows before any cleanup execution approval."
            if blocked_count
            else "Snapshot/frozen-manifest preflight is clear; approval tokens are still required before cleanup execution."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Snapshot Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- snapshot_required_count: `{s['snapshot_required_count']}`",
        f"- snapshot_missing_count: `{s['snapshot_missing_count']}`",
        f"- frozen_manifest_ready_count: `{s['frozen_manifest_ready_count']}`",
        f"- approval_token_count: `{s['approval_token_count']}`",
        f"- approval_gated_size_gb: `{s['approval_gated_size_gb']}`",
        f"- snapshot_created: `{s['snapshot_created']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| lane | action | status | token | size_gb | snapshot | blockers |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane']}` | `{row['recommended_action']}` | `{row['preflight_status']}` | "
            f"`{row['approval_token']}` | `{row['size_gb']}` | `{row['snapshot_artifact']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check cleanup snapshot/frozen-manifest readiness without executing cleanup.")
    parser.add_argument("--transition-cleanup-work-order-json", default=DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--ligand-cleanup-work-order-json", default=DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_snapshot_preflight(
        transition_cleanup_work_order_packet=_read_json_if_present(args.transition_cleanup_work_order_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        ligand_cleanup_work_order_packet=_read_json_if_present(args.ligand_cleanup_work_order_json),
        transition_cleanup_work_order_path=args.transition_cleanup_work_order_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        ligand_cleanup_work_order_path=args.ligand_cleanup_work_order_json,
        snapshot_dir=args.snapshot_dir,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
