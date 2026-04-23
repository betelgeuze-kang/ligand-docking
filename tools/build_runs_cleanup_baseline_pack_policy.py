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
DEFAULT_OUT_JSON = "runs/runs_cleanup_baseline_pack_policy_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_baseline_pack_policy_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_baseline_pack_policy_current.md"


def build_payload(holdout_review_json: str, audit_json: str) -> dict[str, Any]:
    holdout = json.loads(_resolve(holdout_review_json).read_text(encoding="utf-8"))
    audit = json.loads(_resolve(audit_json).read_text(encoding="utf-8"))
    holdout_summary = holdout["summary"]
    audit_summary = audit["summary"]

    rows = [
        {
            "retention_group": "current_artifacts",
            "scope": "_current.* artifacts across active domains",
            "retention_policy": "keep_in_active_root",
            "why_keep": "These are the live operator, decision, and outbound surfaces.",
        },
        {
            "retention_group": "idp_admitted_current_lane",
            "scope": "Protected IDP admitted/commercial-pretest/wider-lane prefixes",
            "retention_policy": "keep_in_active_root",
            "why_keep": "This is the current IDP claim surface and must remain directly accessible.",
        },
        {
            "retention_group": "idp_baseline_reference_pack",
            "scope": "IDP holdout prefixes still referenced by current artifacts",
            "retention_policy": "review_hold_until_reference_replaced",
            "why_keep": "These historical prefixes remain part of the minimal reproducibility chain until their references are collapsed into a thinner baseline pack.",
        },
        {
            "retention_group": "idp_stale_historical_holdouts",
            "scope": "Legacy IDP batch/sb_rust/vhbond/fastpair exploratory prefixes with zero current references",
            "retention_policy": "archive_first_then_compress",
            "why_keep": "They no longer support current decisions directly and are the largest safe space-recovery target.",
        },
        {
            "retention_group": "ligand_pipeline_heavy_stage_outputs",
            "scope": "Blind GPCR/TRPV1/stress historical stage2/3 heavy bundles",
            "retention_policy": "archive_then_compress",
            "why_keep": "They preserve historical pipeline provenance but do not need to stay in the active root.",
        },
        {
            "retention_group": "external_validation_archives",
            "scope": "Already archived external validation batches",
            "retention_policy": "keep_tarball_or_offload",
            "why_keep": "They are already cold-storage material and should move out of the active root or to external storage next.",
        },
    ]

    summary = {
        "status": "runs_cleanup_baseline_pack_policy_ready",
        "current_artifact_file_count": int(audit_summary.get("current_artifact_file_count", 0) or 0),
        "idp_protected_prefix_count": int(holdout_summary.get("protected_prefix_count", 0) or 0),
        "idp_reference_hold_prefix_count": int(holdout_summary.get("review_hold_reference_prefix_count", 0) or 0),
        "idp_stale_candidate_prefix_count": int(holdout_summary.get("stale_candidate_prefix_count", 0) or 0),
        "archive_only_cleanup_recommended": bool(audit_summary.get("archive_only_cleanup_recommended", False)),
        "baseline_pack_rule": "Keep current artifacts and the smallest still-referenced baseline lineage; archive and compress everything else historical.",
        "next_required_step": "Use the baseline-retention contract to build archive-first manifests, apply only stale historical prefixes, then compress those archives or move them off-machine for actual disk recovery.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Baseline Pack Policy",
        "",
        f"- status: `{s['status']}`",
        f"- current_artifact_file_count: `{s['current_artifact_file_count']}`",
        f"- idp_protected_prefix_count: `{s['idp_protected_prefix_count']}`",
        f"- idp_reference_hold_prefix_count: `{s['idp_reference_hold_prefix_count']}`",
        f"- idp_stale_candidate_prefix_count: `{s['idp_stale_candidate_prefix_count']}`",
        f"- archive_only_cleanup_recommended: `{s['archive_only_cleanup_recommended']}`",
        f"- baseline_pack_rule: {s['baseline_pack_rule']}",
        "",
        "| retention_group | scope | retention_policy | why_keep |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['retention_group']}` | {row['scope']} | `{row['retention_policy']}` | {row['why_keep']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a baseline-pack retention policy for runs/ cleanup.")
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
