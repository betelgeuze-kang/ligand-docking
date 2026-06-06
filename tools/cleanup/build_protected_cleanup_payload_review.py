#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRILLDOWN_JSON = "runs/large_cleanup_surface_drilldown_current.json"
DEFAULT_OUT_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_OUT_CSV = "runs/protected_cleanup_payload_review_current.csv"
DEFAULT_OUT_MD = "runs/protected_cleanup_payload_review_current.md"

CLAIM_BOUNDARY = (
    "Protected cleanup payload review only; it summarizes known heavy payload rows protected by the current dry-run policy. "
    "It does not promote protected rows to deletion approval, delete, move, archive, externalize, upload, commit, push, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _is_protected(row: dict[str, Any]) -> bool:
    status = _text(row.get("source_dry_run_status"))
    return bool(status and ("kept_" in status or "protected" in status))


def build_protected_payload_review(
    drilldown_packet: dict[str, Any],
    *,
    drilldown_json: str = DEFAULT_DRILLDOWN_JSON,
    large_payload_threshold_gb: float = 100.0,
) -> dict[str, Any]:
    drilldown = _summary(drilldown_packet)
    source_rows = drilldown_packet.get("rows") if isinstance(drilldown_packet.get("rows"), list) else []
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        if not isinstance(row, dict) or not _is_protected(row):
            continue
        size_gb = _float(row.get("known_payload_size_gb") or row.get("size_gb"))
        rows.append(
            {
                "path": _text(row.get("path")),
                "surface_path": _text(row.get("surface_path")),
                "scope": _text(row.get("scope")),
                "status": _text(row.get("status")),
                "source_dry_run_status": _text(row.get("source_dry_run_status")),
                "source_dry_run_reason": _text(row.get("source_dry_run_reason")),
                "known_payload_count": int(_float(row.get("known_payload_count"))),
                "known_payload_size_gb": round(size_gb, 3),
                "large_payload": size_gb >= large_payload_threshold_gb,
                "current_policy_action": "keep_protected",
                "policy_change_required_for_deletion": True,
                "approval_promoted": False,
                "delete_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
                "recommended_next_action": "review protection reason and only create a new approval packet if operator changes cleanup policy",
            }
        )
    rows.sort(key=lambda row: (-float(row["known_payload_size_gb"]), row["path"]))
    large_rows = [row for row in rows if row["large_payload"]]
    summary = {
        "packet_type": "protected_cleanup_payload_review",
        "status": "protected_cleanup_payload_review_ready",
        "source_drilldown_json": drilldown_json,
        "source_drilldown_status": _text(drilldown.get("status")),
        "protected_payload_row_count": len(rows),
        "protected_payload_size_gb": round(sum(float(row["known_payload_size_gb"]) for row in rows), 3),
        "large_protected_payload_row_count": len(large_rows),
        "large_protected_payload_size_gb": round(sum(float(row["known_payload_size_gb"]) for row in large_rows), 3),
        "largest_protected_payload_size_gb": max((float(row["known_payload_size_gb"]) for row in rows), default=0.0),
        "large_payload_threshold_gb": float(large_payload_threshold_gb),
        "policy_change_required_count": len(rows),
        "approval_promoted_count": 0,
        "delete_enabled": False,
        "delete_executed": False,
        "action_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Keep protected payload rows out of approval-gated deletion unless the operator explicitly changes cleanup policy."
            if rows
            else "No protected payload rows were found in the large cleanup drilldown."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Protected Cleanup Payload Review",
        "",
        f"- status: `{s['status']}`",
        f"- protected_payload_row_count: `{s['protected_payload_row_count']}`",
        f"- protected_payload_size_gb: `{s['protected_payload_size_gb']}`",
        f"- large_protected_payload_row_count: `{s['large_protected_payload_row_count']}`",
        f"- large_protected_payload_size_gb: `{s['large_protected_payload_size_gb']}`",
        f"- largest_protected_payload_size_gb: `{s['largest_protected_payload_size_gb']}`",
        f"- policy_change_required_count: `{s['policy_change_required_count']}`",
        f"- approval_promoted_count: `{s['approval_promoted_count']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Protected Rows",
        "",
        "| size_gb | dry_run_status | dry_run_reason | large | path | next |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['known_payload_size_gb']}` | `{row['source_dry_run_status']}` | `{row['source_dry_run_reason']}` | "
            f"`{row['large_payload']}` | `{row['path']}` | {row['recommended_next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize protected large cleanup payloads without promoting deletion.")
    parser.add_argument("--drilldown-json", default=DEFAULT_DRILLDOWN_JSON)
    parser.add_argument("--large-payload-threshold-gb", type=float, default=100.0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_protected_payload_review(
        _read_json(args.drilldown_json),
        drilldown_json=str(args.drilldown_json),
        large_payload_threshold_gb=args.large_payload_threshold_gb,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
