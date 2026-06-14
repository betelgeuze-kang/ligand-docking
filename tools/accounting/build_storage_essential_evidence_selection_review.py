#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.accounting.build_storage_essential_evidence_register import (
    DEFAULT_OUT_JSON as DEFAULT_REGISTER_JSON,
)
from tools.accounting.build_storage_retention_manifest import _display, _human_size, _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/storage_essential_evidence_selection_review_current.json"
DEFAULT_OUT_CSV = "runs/storage_essential_evidence_selection_review_current.csv"
DEFAULT_OUT_MD = "runs/storage_essential_evidence_selection_review_current.md"
DEFAULT_TOP_DOMAIN_LIMIT = 12

CLAIM_BOUNDARY = (
    "Essential evidence selection review only; it summarizes protected-domain review priorities from "
    "the read-only essential evidence register. It does not select a model for production, delete, move, "
    "archive, externalize, rewrite git history, upload, commit, push, run docking, or mutate external state."
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


def _top_role(rows: list[dict[str, Any]]) -> str:
    counts = Counter(str(row.get("evidence_role") or "") for row in rows)
    if not counts:
        return ""
    return counts.most_common(1)[0][0]


def _review_action(domain: str, dominant_role: str) -> tuple[str, str, str]:
    if domain.startswith("models/"):
        return (
            "model_checkpoint_selection_review",
            "Mark selected/promoted checkpoints, required provenance, and sha256 targets before any stale checkpoint cleanup.",
            "Model domains are large and checkpoint-heavy; cleanup needs an explicit selected-checkpoint register.",
        )
    if domain == "casp17/targets_current":
        return (
            "casp17_final_target_register_review",
            "Confirm final target folders, final coordinate/object/viewer links, validation reports, and sha256 manifests.",
            "Targets current is the strongest CASP17 keep-surface and should be registered before historical cleanup.",
        )
    if "viewer" in domain or dominant_role == "casp17_viewer_or_object_artifact":
        return (
            "casp17_viewer_object_register_review",
            "Confirm current viewer/object artifacts and identify stale galleries only after final target evidence is mapped.",
            "Viewer/object bundles are inspection evidence and should not be bulk-cleaned.",
        )
    if domain == "casp17/runs":
        return (
            "casp17_run_artifact_register_review",
            "Map current run artifacts to final CASP17 evidence, then separate historical/intermediate run payloads.",
            "CASP17 run outputs mix current reports with generated history.",
        )
    if dominant_role == "casp17_structure_coordinate":
        return (
            "casp17_coordinate_register_review",
            "Confirm final/representative/native/candidate coordinate role before cleanup.",
            "Coordinate payloads can be scientific evidence even when not source-of-truth referenced at top level.",
        )
    if dominant_role == "casp17_manifest_validation_or_receipt":
        return (
            "casp17_manifest_receipt_register_review",
            "Keep current manifests, ledgers, gates, receipts, decisions, and validation reports until superseded.",
            "Manifest and receipt payloads carry product evidence.",
        )
    return (
        "protected_domain_register_review",
        "Classify final evidence versus historical/support payload before any cleanup request.",
        "Protected domains require a compact register before deletion.",
    )


def build_storage_essential_evidence_selection_review(
    *,
    root: str | Path = ROOT,
    register_json: str | Path = DEFAULT_REGISTER_JSON,
    top_domain_limit: int = DEFAULT_TOP_DOMAIN_LIMIT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    register, register_present = _read_json(register_json, root=root_path)
    register_rows = [row for row in register.get("rows", []) if isinstance(row, dict)]
    summary_in = register.get("summary", {}) if isinstance(register.get("summary"), dict) else {}
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in register_rows:
        domain = str(row.get("domain") or "").strip()
        if domain:
            by_domain[domain].append(row)

    domain_items: list[tuple[str, list[dict[str, Any]], int]] = []
    for domain, rows in by_domain.items():
        size = sum(int(row.get("size_bytes") or 0) for row in rows)
        domain_items.append((domain, rows, size))
    domain_items.sort(key=lambda item: (-item[2], item[0]))

    rows_out: list[dict[str, Any]] = []
    for rank, (domain, rows, size) in enumerate(domain_items[: max(top_domain_limit, 0)], start=1):
        dominant_role = _top_role(rows)
        action_id, required_review, reason = _review_action(domain, dominant_role)
        high_count = sum(1 for row in rows if row.get("evidence_priority") == "high")
        referenced_count = sum(1 for row in rows if int(row.get("source_of_truth_reference_count") or 0) > 0)
        sha_recorded_count = sum(1 for row in rows if row.get("sha256_status") == "recorded")
        sha_deferred_count = len(rows) - sha_recorded_count
        rows_out.append(
            {
                "rank": rank,
                "domain": domain,
                "file_count": len(rows),
                "size_bytes": size,
                "size_human": _human_size(size),
                "dominant_role": dominant_role,
                "high_priority_file_count": high_count,
                "referenced_file_count": referenced_count,
                "sha256_recorded_count": sha_recorded_count,
                "sha256_deferred_count": sha_deferred_count,
                "review_action_id": action_id,
                "required_review": required_review,
                "keep_before_cleanup": True,
                "cleanup_allowed_by_this_tool": False,
                "operator_approval_required_before_cleanup": True,
                "delete_executed": False,
                "archive_executed": False,
                "externalize_executed": False,
                "external_state_mutated": False,
                "reason": reason,
            }
        )

    total_review_size = sum(int(row["size_bytes"]) for row in rows_out)
    summary = {
        "packet_type": "storage_essential_evidence_selection_review",
        "status": "storage_essential_evidence_selection_review_ready",
        "source_register_json": _display(_resolve(register_json, root=root_path), root=root_path),
        "source_register_present": register_present,
        "source_register_status": str(summary_in.get("status") or ""),
        "source_register_file_count": int(summary_in.get("file_count") or len(register_rows)),
        "source_register_total_size_human": str(summary_in.get("total_size_human") or ""),
        "top_domain_limit": top_domain_limit,
        "review_domain_count": len(rows_out),
        "review_domain_size_bytes": total_review_size,
        "review_domain_size_human": _human_size(total_review_size),
        "review_domain_file_count": sum(int(row["file_count"]) for row in rows_out),
        "review_action_count": len(set(row["review_action_id"] for row in rows_out)),
        "operator_approval_required_count": sum(1 for row in rows_out if row["operator_approval_required_before_cleanup"]),
        "cleanup_allowed_count": 0,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use these top-domain review rows to mark selected checkpoints and final CASP17 target/viewer/validation evidence; cleanup stays blocked until that review is complete."
        ),
    }
    return {"summary": summary, "rows": rows_out}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Storage Essential Evidence Selection Review",
        "",
        f"- status: `{s['status']}`",
        f"- source_register_json: `{s['source_register_json']}`",
        f"- source_register_present: `{s['source_register_present']}`",
        f"- source_register_file_count: `{s['source_register_file_count']}`",
        f"- source_register_total_size_human: `{s['source_register_total_size_human']}`",
        f"- review_domain_count: `{s['review_domain_count']}`",
        f"- review_domain_file_count: `{s['review_domain_file_count']}`",
        f"- review_domain_size_human: `{s['review_domain_size_human']}`",
        f"- cleanup_allowed_count: `{s['cleanup_allowed_count']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- archive_executed: `{s['archive_executed']}`",
        f"- externalize_executed: `{s['externalize_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Review Domains",
        "",
        "| rank | domain | files | size | action |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['rank']}` | `{row['domain']}` | `{row['file_count']}` | "
            f"`{row['size_human']}` | `{row['review_action_id']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only selection review board from the protected storage evidence register.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--register-json", default=DEFAULT_REGISTER_JSON)
    parser.add_argument("--top-domain-limit", type=int, default=DEFAULT_TOP_DOMAIN_LIMIT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_storage_essential_evidence_selection_review(
        root=root,
        register_json=args.register_json,
        top_domain_limit=args.top_domain_limit,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
