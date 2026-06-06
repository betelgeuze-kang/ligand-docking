#!/usr/bin/env python3
"""Dry-run report for P2 data lifecycle manifest (no mutations)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = "runs/p2_data_lifecycle_manifest_current.json"
DEFAULT_OUT_JSON = "runs/p2_data_lifecycle_dry_run_current.json"
DEFAULT_OUT_MD = "runs/p2_data_lifecycle_dry_run_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd = (Path.cwd() / path).resolve()
    return cwd if cwd.exists() else (ROOT / path).resolve()


def dry_run(manifest: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    would_externalize_gb = 0.0
    would_delete_gb = 0.0
    blocked_count = 0
    for row in manifest.get("rows", []) or []:
        action = str(row.get("action", "review"))
        protected = bool(row.get("protected"))
        exists = bool(row.get("exists"))
        size_gb = float(row.get("size_gb") or 0.0)
        if not exists or action in {"keep", "review"}:
            status = "skipped"
        elif protected:
            status = "blocked_protected"
            blocked_count += 1
        elif action in {"externalize", "archive"}:
            status = "would_externalize"
            would_externalize_gb += size_gb
        elif action == "delete":
            status = "would_delete"
            would_delete_gb += size_gb
        else:
            status = "review_required"
        rows.append({**row, "dry_run_status": status})
    return {
        "packet_type": "p2_data_lifecycle_dry_run_v1",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "status": "p2_data_lifecycle_dry_run_ready",
            "dry_run_only": True,
            "execution_allowed": False,
            "externalize_executed": False,
            "delete_executed": False,
            "would_externalize_gb": round(would_externalize_gb, 3),
            "would_delete_gb": round(would_delete_gb, 3),
            "blocked_protected_count": blocked_count,
            "claim_boundary": "Dry-run only; no filesystem mutations performed.",
        },
        "rows": rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# P2 Data Lifecycle Dry Run",
        "",
        f"- would_externalize_gb: `{s['would_externalize_gb']}`",
        f"- would_delete_gb: `{s['would_delete_gb']}`",
        f"- blocked_protected_count: `{s['blocked_protected_count']}`",
        "",
        "| path | action | dry_run_status | size_gb |",
        "| --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row.get('path', '')}` | `{row.get('action', '')}` | `{row.get('dry_run_status', '')}` | `{row.get('size_gb', 0)}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run P2 data lifecycle manifest.")
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    manifest = json.loads(_resolve(args.manifest_json).read_text(encoding="utf-8"))
    payload = dry_run(manifest)
    _resolve(args.out_json).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(_resolve(args.out_md), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
