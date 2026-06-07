#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

DEFAULT_HOLDOUT_REVIEW_JSON = "runs/idp_3bead_holdout_cleanup_review_manifest_current.json"
DEFAULT_AUDIT_JSON = "runs/runs_cleanup_audit_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_domain_retention_table_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_domain_retention_table_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_domain_retention_table_current.md"


def build_payload(holdout_review_json: str, audit_json: str) -> dict[str, Any]:
    holdout = json.loads(_resolve(holdout_review_json).read_text(encoding="utf-8"))
    audit = json.loads(_resolve(audit_json).read_text(encoding="utf-8"))
    rows = [
        {
            "domain_id": "wetlab_partnering",
            "active_surface": "current briefs, outreach packets, and rail indexes",
            "keep_policy": "keep_current_only",
            "archive_policy": "archive historical drafts when a rail packet is superseded",
            "notes": "Outbound-facing artifacts stay active; drafts can move once the sent-ready export exists.",
        },
        {
            "domain_id": "idp_holdout",
            "active_surface": "commercial-pretest, processcheck, broader-shadow, onewider repeatability",
            "keep_policy": "keep_current_plus_minimal_baseline_reference_pack",
            "archive_policy": "archive and compress stale historical prefixes with zero current references",
            "notes": f"Current manifest shows {holdout['summary']['protected_prefix_count']} protected prefixes and {holdout['summary']['review_hold_reference_prefix_count']} reference-hold prefixes.",
        },
        {
            "domain_id": "ligand_blind_gpcr",
            "active_surface": "small residual historical review bundle only",
            "keep_policy": "keep review-only residue plus current artifacts",
            "archive_policy": "batch3/4/5 stage outputs already archived; keep remaining family traces until retirement signoff",
            "notes": "Heavy stage outputs are already out of the active root.",
        },
        {
            "domain_id": "ligand_blind_trpv1",
            "active_surface": "small residual historical review bundle only",
            "keep_policy": "keep review-only residue plus current artifacts",
            "archive_policy": "batch3/4/5 stage outputs already archived; keep remaining family traces until retirement signoff",
            "notes": "Heavy stage outputs are already out of the active root.",
        },
        {
            "domain_id": "ligand_stress_commercial",
            "active_surface": "small residual historical review bundle only",
            "keep_policy": "keep review-only residue plus current artifacts",
            "archive_policy": "batch3/4/5 stage outputs already archived; keep remaining family traces until retirement signoff",
            "notes": "Heavy stage outputs are already out of the active root.",
        },
        {
            "domain_id": "external_validation",
            "active_surface": "compressed archive tarballs only",
            "keep_policy": "keep tarball or move to external storage",
            "archive_policy": "do not expand back into active root",
            "notes": "Already moved to cold storage form; next savings comes from offloading the tarball.",
        },
    ]
    summary = {
        "status": "runs_cleanup_domain_retention_table_ready",
        "top_size_prefix": audit["summary"]["top_size_prefix"],
        "top_size_prefix_size_mb": audit["summary"]["top_size_prefix_size_mb"],
        "domain_row_count": len(rows),
        "next_required_step": "Use this table to limit active-root data to current artifacts plus the thinnest reproducibility pack per domain, then archive or offload the rest.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Domain Retention Table",
        "",
        f"- status: `{s['status']}`",
        f"- top_size_prefix: `{s['top_size_prefix']}`",
        f"- top_size_prefix_size_mb: `{s['top_size_prefix_size_mb']}`",
        f"- domain_row_count: `{s['domain_row_count']}`",
        "",
        "| domain_id | active_surface | keep_policy | archive_policy | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['domain_id']}` | {row['active_surface']} | `{row['keep_policy']}` | {row['archive_policy']} | {row['notes']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a domain-level retention table for runs/ cleanup.")
    parser.add_argument("--holdout-review-json", default=DEFAULT_HOLDOUT_REVIEW_JSON)
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.holdout_review_json, args.audit_json)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
