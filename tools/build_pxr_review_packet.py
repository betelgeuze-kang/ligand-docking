#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PENDING_POLICY_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_QUEUE_JSON = "runs/pxr_manual_review_queue_current.json"
DEFAULT_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_OUT_JSON = "runs/pxr_review_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_review_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_review_packet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _checklist_for_row(row: dict[str, Any]) -> tuple[str, str]:
    ligand = str(row.get("replacement_ligand_id", "")).strip()
    bucket = str(row.get("review_bucket", "")).strip()
    honesty = str(row.get("assay_type_honesty", "")).strip()
    binder = str(row.get("replacement_is_binder", "")).strip() == "1"
    if bucket == "review_only_negative":
        return (
            "Confirm review-only negative status; do not inject quantitative binding value.",
            f"Reviewer note: keep `{ligand}` as review-only negative-like evidence only. Weak upper-bound proxy is insufficient for authoritative non-binder labeling.",
        )
    if binder:
        if honesty == "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing":
            return (
                "Keep deferred until claim-safe quantitative human PXR binder provenance is curated.",
                f"Reviewer note: keep `{ligand}` deferred. Human PXR binder support is confirmed, but qualitative literature alone is still insufficient for binder-field fill.",
            )
        if honesty == "activity_present_manual_confirmation_required":
            return (
                "Keep deferred until the supportive human PXR binder source is manually confirmed.",
                f"Reviewer note: keep `{ligand}` deferred. Supportive target-specific human PXR evidence exists, but it still requires manual confirmation before any claim-safe binder promotion.",
            )
        return (
            "Keep deferred unless local target-specific human PXR evidence is curated.",
            f"Reviewer note: keep `{ligand}` deferred. Do not promote to a PXR binder packet row until local target-specific human PXR evidence is added.",
        )
    return (
        "Keep deferred unless local target-specific human PXR evidence resolves the non-binder conflict.",
        f"Reviewer note: keep `{ligand}` deferred. Current local evidence does not safely support authoritative non-binder labeling.",
    )


def build_payload(
    pending_policy_payload: dict[str, Any],
    queue_payload: dict[str, Any],
    readiness_payload: dict[str, Any],
) -> dict[str, Any]:
    queue_rows = list(queue_payload.get("rows", []) or [])
    readiness_summary = dict(readiness_payload.get("summary", {}) or {})
    rows: list[dict[str, Any]] = []
    for row in queue_rows:
        checklist_action, reviewer_note = _checklist_for_row(row)
        rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("replacement_ligand_id", "")).strip(),
                "binder": str(row.get("replacement_is_binder", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "checklist_action": checklist_action,
                "reviewer_note_template": reviewer_note,
            }
        )

    pending_summary = dict(pending_policy_payload.get("summary", {}) or {})
    summary = {
        "row_count": len(rows),
        "review_only_row_count": len(pending_summary.get("review_only_rows", []) or []),
        "defer_row_count": len(pending_summary.get("defer_rows", []) or []),
        "ready_for_apply_row_count": readiness_summary.get("ready_for_apply_row_count", 0),
        "blocked_row_count": readiness_summary.get("blocked_row_count", 0),
        "policy_line": pending_summary.get("policy_line", ""),
        "next_required_step": "Use this packet as the operator-facing checklist. Keep classifications unchanged and only revisit rows when local target-specific human PXR evidence is added.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Review Packet",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- defer_row_count: `{s['defer_row_count']}`",
        f"- ready_for_apply_row_count: `{s['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        "",
        s["policy_line"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Checklist",
        "",
        "| priority_rank | packet_step | ligand | binder | review_bucket | checklist_action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['ligand']}` | {row['binder']} | `{row['review_bucket']}` | {row['checklist_action']} |"
        )
        lines.append("")
        lines.append(f"- Reviewer note template for `{row['ligand']}`: {row['reviewer_note_template']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact operator-facing PXR review packet/checklist without changing classifications.")
    parser.add_argument("--pending-policy-json", default=DEFAULT_PENDING_POLICY_JSON)
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pending_policy_json),
        _load_json(args.queue_json),
        _load_json(args.readiness_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
