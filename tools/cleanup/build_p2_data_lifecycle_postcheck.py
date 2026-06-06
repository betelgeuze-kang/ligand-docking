#!/usr/bin/env python3
"""Postcheck for P2 data lifecycle dry-run (before/after size snapshot, no mutations)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd = (Path.cwd() / path).resolve()
    return cwd if cwd.exists() else (ROOT / path).resolve()


def build_postcheck(
    *,
    inventory: dict[str, Any],
    manifest: dict[str, Any],
    dry_run: dict[str, Any],
) -> dict[str, Any]:
    inv_total = float((inventory.get("summary") or {}).get("total_measured_gb") or 0.0)
    would_ext = float((dry_run.get("summary") or {}).get("would_externalize_gb") or 0.0)
    would_del = float((dry_run.get("summary") or {}).get("would_delete_gb") or 0.0)
    projected = round(max(inv_total - would_ext - would_del, 0.0), 3)
    keep_protected = [
        row for row in manifest.get("rows", []) or [] if row.get("action") == "keep" and row.get("protected")
    ]
    return {
        "packet_type": "p2_data_lifecycle_postcheck_v1",
        "summary": {
            "status": "p2_data_lifecycle_postcheck_ready",
            "inventory_total_gb": inv_total,
            "would_externalize_gb": would_ext,
            "would_delete_gb": would_del,
            "projected_total_gb_after_approval": projected,
            "keep_protected_row_count": len(keep_protected),
            "execution_allowed": False,
            "externalize_executed": False,
            "delete_executed": False,
            "checksum_verification_required": True,
            "claim_boundary": "Postcheck only; no filesystem mutations performed.",
        },
        "keep_protected_rows": keep_protected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P2 data lifecycle postcheck (readonly).")
    parser.add_argument("--inventory-json", default="runs/p2_data_lifecycle_inventory_current.json")
    parser.add_argument("--manifest-json", default="runs/p2_data_lifecycle_manifest_current.json")
    parser.add_argument("--dry-run-json", default="runs/p2_data_lifecycle_dry_run_current.json")
    parser.add_argument("--out-json", default="runs/p2_data_lifecycle_postcheck_current.json")
    args = parser.parse_args(argv)
    inventory = json.loads(_resolve(args.inventory_json).read_text(encoding="utf-8"))
    manifest = json.loads(_resolve(args.manifest_json).read_text(encoding="utf-8"))
    dry_run = json.loads(_resolve(args.dry_run_json).read_text(encoding="utf-8"))
    payload = build_postcheck(inventory=inventory, manifest=manifest, dry_run=dry_run)
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
