#!/usr/bin/env python3
"""Build P2 data lifecycle manifest (keep/archive/externalize/delete/review)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = "runs/p2_data_lifecycle_inventory_current.json"
DEFAULT_PROTECTED = "runs/protected_cleanup_policy_decision_gate_current.json"
DEFAULT_OUT_JSON = "runs/p2_data_lifecycle_manifest_current.json"
DEFAULT_OUT_MD = "runs/p2_data_lifecycle_manifest_current.md"

PROTECTED_GLOBS = (
    "*_current.json",
    "*_current.csv",
    "*_current.md",
    "*_packet_current.*",
    "wetlab_*",
    "local_delivery_*",
    "product_commercial_readiness_*",
    "nightly_*",
    "keep_green_*",
)

ROW_SPECS: list[dict[str, Any]] = [
    {"path": "data", "action": "keep", "protected": True, "reason": "Local datasets; never git-tracked."},
    {"path": "models", "action": "keep", "protected": True, "reason": "Local model checkpoints; never git-tracked."},
    {"path": "runs", "action": "review", "protected": False, "reason": "Mixed; sub-rows classify archive/externalize candidates."},
    {"path": "runs/archive", "action": "externalize", "protected": False, "reason": "Historical archive subtree."},
    {"path": "runs/archive_*", "action": "externalize", "glob": True, "protected": False, "reason": "Dated archive prefixes."},
    {"path": "runs/*stage2_traj_frames*", "action": "externalize", "glob": True, "protected": False, "reason": "Repeat trajectory frames; keep final PDB/manifest only."},
    {"path": "runs/external_validation_2026-03-*", "action": "archive", "glob": True, "protected": False, "reason": "Superseded external-validation intermediates."},
    {"path": "casp17", "action": "review", "protected": False, "reason": "Scan subdirs; externalize heavy pools only after review."},
    {"path": "casp17/massivefold_external_pool_intake", "action": "externalize", "protected": False, "reason": "Primary CASP17 heavy pool candidate."},
    {"path": "casp17/massivefold_*", "action": "review", "glob": True, "protected": False, "reason": "Massivefold subtrees require operator review."},
    {"path": "archives", "action": "externalize", "protected": False, "reason": "Cold storage candidate."},
    {"path": "rust_engine/target", "action": "delete", "local_only": True, "protected": False, "reason": "Rust build cache; reproducible from source."},
    {"path": ".venv", "action": "delete", "local_only": True, "protected": False, "reason": "Local virtualenv only."},
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd = (Path.cwd() / path).resolve()
    return cwd if cwd.exists() else (ROOT / path).resolve()


def _du_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        out = subprocess.check_output(["du", "-sb", str(path)], text=True).split()[0]
        return int(out)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0


def _glob_size(root: Path, pattern: str) -> tuple[int, int]:
    if not root.parent.exists() and not root.exists():
        return 0, 0
    base = root.parent if "*" in pattern else root
    if not base.exists():
        return 0, 0
    matches = list(base.glob(pattern if "*" in pattern else root.name))
    total = sum(_du_bytes(p) for p in matches if p.exists())
    return len(matches), total


def _path_row(spec: dict[str, Any]) -> dict[str, Any]:
    rel = str(spec["path"])
    path = _resolve(rel)
    if spec.get("glob"):
        count, size_bytes = _glob_size(path, Path(rel).name if "/" in rel else rel)
    else:
        count = 1 if path.exists() else 0
        size_bytes = _du_bytes(path) if path.exists() else 0
    return {
        "path": rel,
        "action": spec["action"],
        "protected": bool(spec.get("protected")),
        "local_only": bool(spec.get("local_only")),
        "exists": count > 0,
        "match_count": count,
        "size_gb": round(size_bytes / 1e9, 3) if size_bytes else 0.0,
        "reason": spec.get("reason", ""),
        "execution_allowed": False,
    }


def build_manifest(
    *,
    inventory: dict[str, Any] | None = None,
    protected_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [_path_row(spec) for spec in ROW_SPECS]
    protected_patterns = list(PROTECTED_GLOBS)
    if protected_policy:
        extra = protected_policy.get("summary", {}).get("protected_glob_patterns", [])
        if isinstance(extra, list):
            protected_patterns.extend(str(p) for p in extra)

    externalize_gb = sum(r["size_gb"] for r in rows if r["action"] in {"externalize", "archive"} and r["exists"])
    delete_gb = sum(r["size_gb"] for r in rows if r["action"] == "delete" and r["exists"])

    return {
        "packet_type": "p2_data_lifecycle_manifest_v1",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "status": "p2_data_lifecycle_manifest_ready",
            "inventory_source": DEFAULT_INVENTORY,
            "protected_policy_loaded": bool(protected_policy),
            "protected_glob_patterns": protected_patterns,
            "row_count": len(rows),
            "externalize_candidate_gb": round(externalize_gb, 3),
            "delete_candidate_gb": round(delete_gb, 3),
            "execution_allowed": False,
            "externalize_executed": False,
            "delete_executed": False,
            "archive_executed": False,
            "claim_boundary": (
                "Manifest only. No archive/externalize/delete until operator approval dossier and payload lock are green."
            ),
            "next_required_step": (
                "Run tools/cleanup/dry_run_p2_data_lifecycle.py, review protected rows, then obtain operator approval."
            ),
        },
        "rows": rows,
        "inventory_summary": (inventory or {}).get("summary", {}),
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# P2 Data Lifecycle Manifest v1",
        "",
        f"- status: `{s['status']}`",
        f"- externalize_candidate_gb: `{s['externalize_candidate_gb']}`",
        f"- delete_candidate_gb: `{s['delete_candidate_gb']}`",
        f"- execution_allowed: `{s['execution_allowed']}`",
        "",
        "| path | action | exists | size_gb | protected | reason |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['action']}` | `{row['exists']}` | `{row['size_gb']}` | "
            f"`{row['protected']}` | {row['reason']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P2 data lifecycle manifest v1.")
    parser.add_argument("--inventory-json", default=DEFAULT_INVENTORY)
    parser.add_argument("--protected-policy-json", default=DEFAULT_PROTECTED)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = _resolve(args.inventory_json)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else {}
    protected_path = _resolve(args.protected_policy_json)
    protected = json.loads(protected_path.read_text(encoding="utf-8")) if protected_path.exists() else {}
    payload = build_manifest(inventory=inventory, protected_policy=protected)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_md(out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
