#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from tools.accounting.build_ligand_heavy_run_cleanup_manifest import DEFAULT_OUT_JSON as DEFAULT_MANIFEST_JSON
from tools.accounting.build_storage_retention_manifest import _display, _human_size, _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/ligand_heavy_run_cleanup_execution_current.json"
DEFAULT_OUT_CSV = "runs/ligand_heavy_run_cleanup_execution_current.csv"
DEFAULT_OUT_MD = "runs/ligand_heavy_run_cleanup_execution_current.md"
APPROVAL_TOKEN = "APPROVE_LIGAND_HEAVY_RUN_CLEANUP"

CLAIM_BOUNDARY = (
    "Ligand-heavy run cleanup execution only deletes rows marked delete_recommended=true in the generated "
    "cleanup manifest, and only when --execute and the approval token are supplied. It does not delete "
    "top-ranking/summary keep rows, referenced keep rows, review-required rows, git history, source code, "
    "models, CASP17 evidence roots, or any path outside the repository root."
)


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _safe_candidate_path(rel_path: str, *, root: Path) -> Path | None:
    if not rel_path or Path(rel_path).is_absolute():
        return None
    path = (root / rel_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    protected_prefixes = (".git", "tools", "scripts", "tests", "docs", "api", "core", "models", "casp17", "data")
    parts = Path(rel_path).parts
    if parts and parts[0] in protected_prefixes:
        return None
    return path


def apply_ligand_heavy_run_cleanup_manifest(
    *,
    root: str | Path = ROOT,
    manifest_json: str | Path = DEFAULT_MANIFEST_JSON,
    execute: bool = False,
    approval_token: str = "",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    manifest, manifest_present = _read_json(manifest_json, root=root_path)
    manifest_rows = [row for row in manifest.get("rows", []) if isinstance(row, dict)]
    delete_rows = [row for row in manifest_rows if row.get("delete_recommended") is True]
    approval_token_valid = approval_token == APPROVAL_TOKEN
    delete_authorized = bool(execute and approval_token_valid)
    rows: list[dict[str, Any]] = []

    for row in delete_rows:
        rel_path = str(row.get("path") or "")
        size = int(row.get("size_bytes") or 0)
        candidate = _safe_candidate_path(rel_path, root=root_path)
        status = "dry_run_pending"
        error = ""
        observed_type = ""
        if candidate is None:
            status = "blocked_unsafe_path"
        elif not candidate.exists():
            status = "missing_before_delete"
        elif candidate.is_symlink():
            status = "blocked_symlink"
            observed_type = "symlink"
        elif candidate.is_file():
            observed_type = "file"
            if delete_authorized:
                try:
                    candidate.unlink()
                    status = "deleted"
                except OSError as exc:
                    status = "delete_failed"
                    error = str(exc)
        elif candidate.is_dir():
            observed_type = "directory"
            if delete_authorized:
                try:
                    shutil.rmtree(candidate)
                    status = "deleted"
                except OSError as exc:
                    status = "delete_failed"
                    error = str(exc)
        else:
            status = "blocked_unknown_path_type"
            observed_type = "other"
        rows.append(
            {
                "path": rel_path,
                "path_type": row.get("path_type", ""),
                "observed_path_type": observed_type,
                "size_bytes": size,
                "size_human": _human_size(size),
                "manifest_disposition": row.get("disposition", ""),
                "cleanup_class": row.get("cleanup_class", ""),
                "execute_requested": execute,
                "approval_token_valid": approval_token_valid,
                "delete_authorized": delete_authorized,
                "status": status,
                "error": error,
            }
        )

    deleted_rows = [row for row in rows if row["status"] == "deleted"]
    failed_rows = [
        row
        for row in rows
        if row["status"]
        in {"delete_failed", "blocked_unsafe_path", "blocked_symlink", "blocked_unknown_path_type"}
    ]
    missing_rows = [row for row in rows if row["status"] == "missing_before_delete"]
    pending_rows = [row for row in rows if row["status"] == "dry_run_pending"]
    summary = {
        "packet_type": "ligand_heavy_run_cleanup_execution",
        "status": (
            "ligand_heavy_run_cleanup_execution_complete"
            if delete_authorized and not failed_rows
            else "ligand_heavy_run_cleanup_execution_ready"
        ),
        "manifest_json": _display(_resolve(manifest_json, root=root_path), root=root_path),
        "manifest_present": manifest_present,
        "manifest_delete_recommended_count": len(delete_rows),
        "execute_requested": execute,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_valid": approval_token_valid,
        "delete_authorized": delete_authorized,
        "delete_executed": bool(deleted_rows),
        "deleted_count": len(deleted_rows),
        "deleted_size_bytes": sum(int(row["size_bytes"]) for row in deleted_rows),
        "deleted_size_human": _human_size(sum(int(row["size_bytes"]) for row in deleted_rows)),
        "pending_count": len(pending_rows),
        "missing_count": len(missing_rows),
        "failed_count": len(failed_rows),
        "local_filesystem_mutated": bool(deleted_rows),
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rerun the cleanup manifest, storage retention manifest, and independent readiness check after deletion."
            if deleted_rows
            else "Provide --execute with the approval token to delete manifest rows marked delete_recommended=true."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Ligand Heavy Run Cleanup Execution",
        "",
        f"- status: `{s['status']}`",
        f"- manifest_delete_recommended_count: `{s['manifest_delete_recommended_count']}`",
        f"- execute_requested: `{s['execute_requested']}`",
        f"- approval_token_valid: `{s['approval_token_valid']}`",
        f"- delete_authorized: `{s['delete_authorized']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- deleted_count: `{s['deleted_count']}`",
        f"- deleted_size_human: `{s['deleted_size_human']}`",
        f"- pending_count: `{s['pending_count']}`",
        f"- missing_count: `{s['missing_count']}`",
        f"- failed_count: `{s['failed_count']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply an approval-gated ligand-heavy run cleanup manifest.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = apply_ligand_heavy_run_cleanup_manifest(
        root=root,
        manifest_json=args.manifest_json,
        execute=args.execute,
        approval_token=args.approval_token,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
