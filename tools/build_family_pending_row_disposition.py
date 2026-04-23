#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULTS = {
    "ca2": {
        "sheet_csv": "runs/ca2_binding_verification_sheet_current.csv",
        "capture_sheet_json": "runs/ca2_negative_evidence_capture_sheet_current.json",
        "out_json": "runs/ca2_pending_row_disposition_current.json",
        "out_csv": "runs/ca2_pending_row_disposition_current.csv",
        "out_md": "runs/ca2_pending_row_disposition_current.md",
    },
    "pxr": {
        "sheet_csv": "runs/pxr_binding_verification_sheet_current.csv",
        "capture_sheet_json": "runs/pxr_unresolved_evidence_capture_sheet_current.json",
        "out_json": "runs/pxr_pending_row_disposition_current.json",
        "out_csv": "runs/pxr_pending_row_disposition_current.csv",
        "out_md": "runs/pxr_pending_row_disposition_current.md",
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _is_verified(status: str) -> bool:
    return str(status or "").strip().startswith("verified_")


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _capture_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _classify(family: str, row: dict[str, str], capture_row: dict[str, Any] | None = None) -> dict[str, str]:
    ligand = str(row.get("replacement_ligand_id", "")).strip()
    is_binder = str(row.get("replacement_is_binder", "")).strip() == "1"
    capture_row = capture_row or {}
    capture_supportive = str(capture_row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
    capture_blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
    capture_status = str(capture_row.get("capture_status", "")).strip()
    capture_policy_bucket = str(capture_row.get("policy_bucket", "")).strip()
    if family == "ca2":
        if not is_binder:
            return {
                "disposition": "review_only_negative_evidence",
                "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                "next_required_action": "manual_negative_evidence_review",
                "notes": "Keep CA2 negative-like rows review-only until direct CA2-specific negative evidence is manually curated; do not inject proxy values or defer them as pending binders.",
            }
    if family == "pxr":
        if capture_blocker == "inactive_only_human_pxr_qhts_review_only":
            return {
                "disposition": "review_only_negative_evidence",
                "promotion_blocker": "inactive_only_human_pxr_qhts_review_only",
                "next_required_action": str(capture_row.get("manual_next_required_action", "")).strip()
                or "manual_negative_evidence_review",
                "notes": (
                    str(capture_row.get("source_note", "")).strip()
                    or "Direct human PXR qHTS rows are currently inactive-only for this ligand; keep it review-only and do not turn it into a count-improving non-binder claim."
                ),
            }
        if (
            is_binder
            and capture_supportive
            and capture_blocker == "quantitative_binding_value_or_activity_proxy_missing"
        ):
            return {
                "disposition": "pending_binder_curation",
                "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                "next_required_action": str(capture_row.get("manual_next_required_action", "")).strip()
                or "curate_quantitative_binding_value",
                "notes": (
                    str(capture_row.get("source_note", "")).strip()
                    or "Target-specific human PXR binder evidence is confirmed for this row, but claim-safe quantitative provenance is still missing; keep deferred from authoritative apply."
                ),
            }
        if (
            is_binder
            and capture_supportive
            and capture_blocker == "activity_present_manual_confirmation_required"
        ):
            return {
                "disposition": "defer_pending_target_specific_evidence",
                "promotion_blocker": "activity_present_manual_confirmation_required",
                "next_required_action": str(capture_row.get("manual_next_required_action", "")).strip() or "manual_curated_search_or_defer",
                "notes": (
                    str(capture_row.get("source_note", "")).strip()
                    or "Supportive target-specific human PXR evidence is present for this binder candidate, but it still requires manual confirmation before any claim-safe binder fill; keep deferred."
                ),
            }
        if capture_status and capture_status != "pending_capture" and (
            str(capture_row.get("manual_assay_type_honesty", "")).strip()
            or capture_blocker
            or str(capture_row.get("manual_next_required_action", "")).strip()
        ):
            return {
                "disposition": (
                    "review_only_negative_evidence"
                    if capture_policy_bucket == "review_only"
                    else "defer_pending_target_specific_evidence"
                ),
                "promotion_blocker": capture_blocker
                or str(capture_row.get("manual_assay_type_honesty", "")).strip()
                or "manual_review_required",
                "next_required_action": str(capture_row.get("manual_next_required_action", "")).strip()
                or str(capture_row.get("next_required_action", "")).strip()
                or (
                    "manual_negative_evidence_review"
                    if capture_policy_bucket == "review_only"
                    else "manual_curated_search_or_defer"
                ),
                "notes": str(capture_row.get("source_note", "")).strip()
                or str(capture_row.get("manual_commit_class_override", "")).strip()
                or "Capture-sheet evidence exists for this row; preserve the current policy bucket unless stronger target-specific evidence changes it.",
            }
        if ligand == "ibuprofen" and not is_binder:
            return {
                "disposition": "review_only_negative_evidence",
                "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                "next_required_action": "manual_negative_evidence_review",
                "notes": "Human PXR activity is only available as a weak upper-bound proxy (>30000 nM); keep as review-only negative-like evidence and do not inject proxy binding values.",
            }
        if ligand == "acetaminophen" and not is_binder:
            return {
                "disposition": "defer_pending_target_specific_evidence",
                "promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                "next_required_action": "manual_curated_search_or_defer",
                "notes": "Human PXR activity proxy exists for this ligand, so it is unsafe to label as a non-binder; keep deferred.",
            }
        if ligand in {"caffeine", "nicotinamide", "aspirin"} and not is_binder:
            return {
                "disposition": "defer_pending_target_specific_evidence",
                "promotion_blocker": "no_local_target_activity_curated",
                "next_required_action": "manual_curated_search_or_defer",
                "notes": "No local human PXR target-specific activity is curated for this ligand; keep deferred rather than labeling it a non-binder.",
            }
    if not is_binder:
        return {
            "disposition": "review_only_negative_evidence",
            "promotion_blocker": "no_quantitative_nonbinder_value_curated",
            "next_required_action": "manual_negative_evidence_review",
            "notes": "Keep this row review-only until target-specific negative evidence is manually curated; do not inject proxy binding values.",
        }
    if family == "pxr" and ligand == "bexarotene":
        return {
            "disposition": "defer_pending_target_specific_evidence",
            "promotion_blocker": "activity_present_manual_confirmation_required",
            "next_required_action": "manual_curated_search_or_defer",
            "notes": "Supportive target-specific human PXR activity is present for bexarotene, but the row still needs manual confirmation before any claim-safe binder promotion; keep deferred.",
        }
    return {
        "disposition": "pending_binder_curation",
        "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
        "next_required_action": "curate_quantitative_binding_value",
        "notes": "Binder candidate still needs quantitative evidence before authoritative apply.",
    }


def build_payload(
    family: str,
    rows: list[dict[str, str]],
    capture_sheet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pending = [row for row in rows if not _is_verified(str(row.get("verification_status", "")))]
    pending.sort(key=lambda row: int(str(row.get("priority_rank", "999"))))
    capture_by_step = _capture_by_step(capture_sheet_payload)
    disposition_rows: list[dict[str, Any]] = []
    for row in pending:
        packet_step = str(row.get("packet_step", "")).strip()
        classified = _classify(family, row, capture_by_step.get(packet_step, {}))
        disposition_rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": packet_step,
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "verification_status": str(row.get("verification_status", "")).strip(),
                **classified,
            }
        )
    review_only_rows = sum(1 for row in disposition_rows if row["disposition"] == "review_only_negative_evidence")
    defer_rows = sum(1 for row in disposition_rows if row["disposition"] == "defer_pending_target_specific_evidence")
    pending_binder_rows = sum(1 for row in disposition_rows if row["disposition"] == "pending_binder_curation")
    verified_rows = sum(1 for row in rows if _is_verified(str(row.get("verification_status", ""))))
    if family == "ca2":
        next_step = "Keep the remaining CA2 negative-like rows review-only, keep them out of authoritative apply, and only promote them if direct CA2-specific negative evidence is manually curated."
    else:
        review_only_ligands = [
            str(row.get("replacement_ligand_id", "")).strip()
            for row in disposition_rows
            if str(row.get("disposition", "")).strip() == "review_only_negative_evidence"
        ]
        deferred_ligands = [
            str(row.get("replacement_ligand_id", "")).strip()
            for row in disposition_rows
            if str(row.get("disposition", "")).strip() == "defer_pending_target_specific_evidence"
        ]
        review_only_phrase = ", ".join(review_only_ligands) or "none"
        deferred_phrase = ", ".join(deferred_ligands) or "none"
        next_step = (
            f"Keep PXR review-only rows ({review_only_phrase}) locked to review-only negative-like documentation, "
            "keep bexarotene on the supportive-binder manual-confirmation lane when present, "
            f"and defer the remaining unresolved rows ({deferred_phrase}) until blocker-reducing human PXR evidence is curated."
        )
    return {
        "summary": {
            "family": family,
            "total_rows": len(rows),
            "verified_rows": verified_rows,
            "pending_rows": len(disposition_rows),
            "review_only_rows": review_only_rows,
            "defer_rows": defer_rows,
            "pending_binder_rows": pending_binder_rows,
            "next_required_step": next_step,
        },
        "rows": disposition_rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# {str(summary['family']).upper()} Pending Row Disposition",
        "",
        f"- total_rows: `{summary['total_rows']}`",
        f"- verified_rows: `{summary['verified_rows']}`",
        f"- pending_rows: `{summary['pending_rows']}`",
        f"- review_only_rows: `{summary['review_only_rows']}`",
        f"- defer_rows: `{summary['defer_rows']}`",
        f"- pending_binder_rows: `{summary['pending_binder_rows']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| priority_rank | packet_step | ligand | disposition | promotion_blocker | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | `{row['disposition']}` | `{row['promotion_blocker']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build review-only/defer disposition for remaining CA2/PXR rows.")
    p.add_argument("--family", choices=sorted(DEFAULTS.keys()), required=True)
    p.add_argument("--sheet-csv")
    p.add_argument("--capture-sheet-json")
    p.add_argument("--out-json")
    p.add_argument("--out-csv")
    p.add_argument("--out-md")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    defaults = DEFAULTS[args.family]
    rows = _read_csv(_resolve(args.sheet_csv or defaults["sheet_csv"]))
    capture_sheet_payload = _read_optional_json(_resolve(args.capture_sheet_json or defaults["capture_sheet_json"]))
    payload = build_payload(args.family, rows, capture_sheet_payload)
    out_json = _resolve(args.out_json or defaults["out_json"])
    out_csv = _resolve(args.out_csv or defaults["out_csv"])
    out_md = _resolve(args.out_md or defaults["out_md"])
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
