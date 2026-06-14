#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.accounting.apply_ligand_heavy_run_cleanup_manifest import (
    DEFAULT_OUT_JSON as DEFAULT_EXECUTION_JSON,
)
from tools.accounting.build_ligand_heavy_run_cleanup_manifest import (
    DEFAULT_OUT_JSON as DEFAULT_MANIFEST_JSON,
)
from tools.accounting.build_storage_retention_manifest import _display, _human_size, _resolve

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/ligand_heavy_run_retention_receipt_current.json"
DEFAULT_OUT_MD = "docs/ligand_heavy_run_retention_receipt_current.md"

CLAIM_BOUNDARY = (
    "Ligand-heavy retention receipt only records compact top-ranking evidence, "
    "delete-candidate metadata, and optional cleanup execution receipt fields. It "
    "does not run docking, change scientific claims, approve commercial promotion, "
    "or mutate external state."
)


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _split_evidence(value: Any) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [part for part in value.split(";") if part]


def _delete_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("delete_recommended") is True]


def _execution_rows(execution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = execution.get("rows", [])
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("path"):
            result[str(row["path"])] = row
    return result


def _retained_evidence(delete_rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    evidence: list[str] = []
    for row in delete_rows:
        for path in _split_evidence(row.get("preserved_evidence")):
            if path in seen:
                continue
            seen.add(path)
            evidence.append(path)
    return evidence


def build_ligand_heavy_run_retention_receipt(
    *,
    root: str | Path = ROOT,
    manifest_json: str | Path = DEFAULT_MANIFEST_JSON,
    execution_json: str | Path = DEFAULT_EXECUTION_JSON,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    manifest, manifest_present = _read_json(manifest_json, root=root_path)
    execution, execution_present = _read_json(execution_json, root=root_path)
    manifest_summary = manifest.get("summary", {}) if isinstance(manifest.get("summary"), dict) else {}
    execution_summary = execution.get("summary", {}) if isinstance(execution.get("summary"), dict) else {}
    rows = _delete_rows(manifest)
    execution_by_path = _execution_rows(execution)
    retained = _retained_evidence(rows)

    delete_records: list[dict[str, Any]] = []
    for row in rows:
        path = str(row.get("path") or "")
        execution_row = execution_by_path.get(path, {})
        delete_records.append(
            {
                "path": path,
                "cleanup_class": row.get("cleanup_class", ""),
                "path_type": row.get("path_type", ""),
                "size_bytes": int(row.get("size_bytes") or 0),
                "size_human": row.get("size_human", ""),
                "disposition": row.get("disposition", ""),
                "reason": row.get("reason", ""),
                "preserved_evidence_count": int(row.get("preserved_evidence_count") or 0),
                "preserved_evidence": _split_evidence(row.get("preserved_evidence")),
                "execution_status": execution_row.get("status", "not_executed_or_not_recorded"),
            }
        )

    deleted_count = int(execution_summary.get("deleted_count") or 0)
    deleted_size = int(execution_summary.get("deleted_size_bytes") or 0)
    delete_count = len(delete_records)
    delete_size = sum(int(row["size_bytes"]) for row in delete_records)
    status = (
        "ligand_heavy_run_retention_receipt_execution_recorded"
        if execution_present and deleted_count
        else "ligand_heavy_run_retention_receipt_ready"
    )
    summary = {
        "packet_type": "ligand_heavy_run_retention_receipt",
        "status": status,
        "manifest_json": _display(_resolve(manifest_json, root=root_path), root=root_path),
        "manifest_present": manifest_present,
        "execution_json": _display(_resolve(execution_json, root=root_path), root=root_path),
        "execution_present": execution_present,
        "manifest_candidate_count": int(manifest_summary.get("candidate_count") or 0),
        "manifest_candidate_size_human": manifest_summary.get("candidate_size_human", ""),
        "manifest_delete_recommended_count": int(manifest_summary.get("delete_recommended_count") or delete_count),
        "manifest_delete_recommended_size_bytes": int(
            manifest_summary.get("delete_recommended_size_bytes") or delete_size
        ),
        "manifest_delete_recommended_size_human": manifest_summary.get(
            "delete_recommended_size_human", _human_size(delete_size)
        ),
        "manifest_top_rank_keep_count": int(manifest_summary.get("top_rank_keep_count") or 0),
        "manifest_top_rank_keep_size_human": manifest_summary.get("top_rank_keep_size_human", ""),
        "manifest_review_required_count": int(manifest_summary.get("review_required_count") or 0),
        "manifest_review_required_size_human": manifest_summary.get("review_required_size_human", ""),
        "retained_top_rank_or_compact_evidence_count": len(retained),
        "delete_record_count": delete_count,
        "delete_record_size_bytes": delete_size,
        "delete_record_size_human": _human_size(delete_size),
        "execution_status": execution_summary.get("status", ""),
        "execution_deleted_count": deleted_count,
        "execution_deleted_size_bytes": deleted_size,
        "execution_deleted_size_human": execution_summary.get("deleted_size_human", _human_size(deleted_size)),
        "execution_failed_count": int(execution_summary.get("failed_count") or 0),
        "execution_missing_count": int(execution_summary.get("missing_count") or 0),
        "local_filesystem_mutated": bool(execution_summary.get("local_filesystem_mutated", False)),
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rerun ligand-heavy cleanup manifest and product readiness checks after cleanup."
            if deleted_count
            else "Run the approval-gated ligand-heavy cleanup execution only after reviewing delete_records."
        ),
    }
    return {
        "summary": summary,
        "retained_top_rank_or_compact_evidence": retained,
        "delete_records": delete_records,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Ligand Heavy Run Retention Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- manifest_delete_recommended_count: `{s['manifest_delete_recommended_count']}`",
        f"- manifest_delete_recommended_size_human: `{s['manifest_delete_recommended_size_human']}`",
        f"- manifest_top_rank_keep_count: `{s['manifest_top_rank_keep_count']}`",
        f"- manifest_top_rank_keep_size_human: `{s['manifest_top_rank_keep_size_human']}`",
        f"- retained_top_rank_or_compact_evidence_count: `{s['retained_top_rank_or_compact_evidence_count']}`",
        f"- execution_deleted_count: `{s['execution_deleted_count']}`",
        f"- execution_deleted_size_human: `{s['execution_deleted_size_human']}`",
        f"- execution_failed_count: `{s['execution_failed_count']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Delete Records",
        "",
        "| path | class | size | execution |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["delete_records"][:40]:
        lines.append(
            f"| `{row['path']}` | `{row['cleanup_class']}` | `{row['size_human']}` | "
            f"`{row['execution_status']}` |"
        )
    lines.extend(["", "## Retained Evidence", ""])
    for path_value in payload["retained_top_rank_or_compact_evidence"][:80]:
        lines.append(f"- `{path_value}`")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact retention receipt for ligand-heavy cleanup.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_ligand_heavy_run_retention_receipt(
        root=root,
        manifest_json=args.manifest_json,
        execution_json=args.execution_json,
    )
    _write_json(args.out_json, payload, root=root)
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
