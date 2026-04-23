#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "ca2": {
        "sheet_csv": "runs/ca2_binding_verification_sheet_current.csv",
        "pending_disposition_json": "runs/ca2_pending_row_disposition_current.json",
        "out_json": "runs/ca2_manual_review_queue_current.json",
        "out_csv": "runs/ca2_manual_review_queue_current.csv",
        "out_md": "runs/ca2_manual_review_queue_current.md",
        "title": "CA2 Manual Review Queue",
    },
    "pxr": {
        "sheet_csv": "runs/pxr_binding_verification_sheet_current.csv",
        "pending_disposition_json": "runs/pxr_pending_row_disposition_current.json",
        "out_json": "runs/pxr_manual_review_queue_current.json",
        "out_csv": "runs/pxr_manual_review_queue_current.csv",
        "out_md": "runs/pxr_manual_review_queue_current.md",
        "title": "PXR Manual Review Queue",
    },
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _normalize_disposition_row(row: dict[str, Any]) -> dict[str, str]:
    disposition = str(row.get("disposition", "")).strip()
    if disposition == "review_only_negative_evidence":
        review_bucket = "review_only_negative"
        recommended_resolution = "keep_review_only_until_negative_evidence_is_curated"
    elif disposition == "defer_pending_target_specific_evidence":
        review_bucket = "defer_pending_target_specific_evidence"
        recommended_resolution = "defer_until_target_specific_human_activity_is_curated"
    else:
        review_bucket = "pending_binder_review"
        recommended_resolution = "curate_quantitative_value_before_apply"
    return {
        "review_bucket": review_bucket,
        "assay_type_honesty": str(row.get("promotion_blocker", "")).strip(),
        "next_required_action": str(row.get("next_required_action", "")).strip(),
        "recommended_resolution": recommended_resolution,
        "notes": str(row.get("notes", "")).strip(),
    }


def build_payload(
    family: str,
    rows: list[dict[str, str]],
    pending_disposition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pending_rows = [
        row for row in rows if not str(row.get("verification_status", "")).strip().startswith("verified_")
    ]
    pending_rows.sort(key=lambda row: int(str(row.get("priority_rank", "999"))))
    disposition_rows = {
        (
            str(row.get("priority_rank", "")).strip(),
            str(row.get("packet_step", "")).strip(),
            str(row.get("replacement_ligand_id", "")).strip(),
        ): _normalize_disposition_row(dict(row))
        for row in (pending_disposition or {}).get("rows", [])
        if isinstance(row, dict)
    }

    queue_rows: list[dict[str, Any]] = []
    review_only_negative_count = 0
    defer_count = 0
    pending_binder_review_count = 0
    for row in pending_rows:
        key = (
            str(row.get("priority_rank", "")).strip(),
            str(row.get("packet_step", "")).strip(),
            str(row.get("replacement_ligand_id", "")).strip(),
        )
        classification = dict(disposition_rows.get(key, {}))
        if not classification:
            classification = {
                "review_bucket": "pending_binder_review" if str(row.get("replacement_is_binder", "")).strip() == "1" else "review_only_negative",
                "assay_type_honesty": "fallback_classification_only",
                "next_required_action": "manual_review",
                "recommended_resolution": "manual_review",
                "notes": "No normalized pending disposition was found for this row.",
            }
        bucket = classification["review_bucket"]
        if bucket == "review_only_negative":
            review_only_negative_count += 1
        elif bucket == "defer_pending_target_specific_evidence":
            defer_count += 1
        else:
            pending_binder_review_count += 1
        queue_rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "verification_status": str(row.get("verification_status", "")).strip(),
                **classification,
            }
        )
    return {
        "summary": {
            "family": family,
            "row_count": len(queue_rows),
            "review_only_negative_count": review_only_negative_count,
            "defer_binder_count": defer_count,
            "pending_binder_review_count": pending_binder_review_count,
            "policy_fixed_pending_count": review_only_negative_count + defer_count,
            "uses_pending_disposition": pending_disposition is not None,
            "next_required_step": "Keep policy-fixed review-only/defer rows out of authoritative apply, and only revisit them when target-specific evidence changes.",
        },
        "rows": queue_rows,
    }


def _write_md(path: Path, title: str, payload: dict[str, Any]) -> None:
    lines = [
        f"# {title}",
        "",
        f"- family: `{payload['summary']['family']}`",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- review_only_negative_count: `{payload['summary']['review_only_negative_count']}`",
        f"- defer_binder_count: `{payload['summary']['defer_binder_count']}`",
        f"- pending_binder_review_count: `{payload['summary']['pending_binder_review_count']}`",
        f"- policy_fixed_pending_count: `{payload['summary']['policy_fixed_pending_count']}`",
        f"- uses_pending_disposition: `{payload['summary']['uses_pending_disposition']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Queue",
        "",
        "| priority_rank | packet_step | ligand | binder | review_bucket | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | `{row['review_bucket']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manual review queue for remaining CA2/PXR rows using the policy-fixed pending disposition.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS), required=True)
    parser.add_argument("--sheet-csv")
    parser.add_argument("--pending-disposition-json")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    sheet_csv = args.sheet_csv or defaults["sheet_csv"]
    pending_disposition_json = args.pending_disposition_json or defaults["pending_disposition_json"]
    out_json = args.out_json or defaults["out_json"]
    out_csv = args.out_csv or defaults["out_csv"]
    out_md = args.out_md or defaults["out_md"]
    rows = _read_csv(_resolve(sheet_csv))
    payload = build_payload(args.family, rows, _read_json(_resolve(pending_disposition_json)))
    out_json_path = _resolve(out_json)
    out_csv_path = _resolve(out_csv)
    out_md_path = _resolve(out_md)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv_path, payload["rows"])
    _write_md(out_md_path, defaults["title"], payload)


if __name__ == "__main__":
    main()
