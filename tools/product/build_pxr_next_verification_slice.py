#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHEET_CSV = "runs/pxr_binding_verification_sheet_current.csv"
DEFAULT_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_OUT_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_OUT_CSV = "runs/pxr_next_verification_slice_current.csv"
DEFAULT_OUT_MD = "runs/pxr_next_verification_slice_current.md"


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


def _load_optional_json(path: Path) -> dict[str, Any]:
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


def build_payload(
    rows: list[dict[str, str]],
    limit: int,
    capture_sheet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    remaining = [
        row
        for row in rows
        if not str(row.get("verification_status", "")).strip().startswith("verified_")
    ]
    capture_rows = _capture_by_step(capture_sheet_payload)
    slice_rows: list[dict[str, Any]] = []
    for row in remaining:
        ligand = str(row.get("replacement_ligand_id", "")).strip()
        packet_step = str(row.get("packet_step", "")).strip()
        is_binder = str(row.get("replacement_is_binder", "")).strip() == "1"
        capture_row = capture_rows.get(packet_step, {})
        capture_status = str(capture_row.get("capture_status", "")).strip()
        capture_policy_bucket = str(capture_row.get("policy_bucket", "")).strip()
        if capture_status and capture_status != "pending_capture" and (
            str(capture_row.get("manual_assay_type_honesty", "")).strip()
            or str(capture_row.get("manual_promotion_blocker", "")).strip()
            or str(capture_row.get("manual_next_required_action", "")).strip()
        ):
            review_reason = (
                str(capture_row.get("source_note", "")).strip()
                or str(capture_row.get("manual_commit_class_override", "")).strip()
                or (
                    "supportive target-specific human PXR evidence exists, but manual confirmation is still required before binder promotion"
                    if is_binder
                    and str(capture_row.get("manual_promotion_blocker", "")).strip() == "activity_present_manual_confirmation_required"
                    else "target-specific human PXR binder evidence is confirmed, but quantitative provenance is still missing before binder promotion"
                    if is_binder
                    and str(capture_row.get("manual_promotion_blocker", "")).strip() == "quantitative_binding_value_or_activity_proxy_missing"
                    else "capture-sheet evidence exists for this row; preserve the current policy bucket until a stronger target-specific source changes it"
                )
            )
            honesty = (
                str(capture_row.get("manual_assay_type_honesty", "")).strip()
                or str(capture_row.get("assay_type_honesty", "")).strip()
                or str(capture_row.get("manual_promotion_blocker", "")).strip()
                or "manual_review_required"
            )
            next_action = (
                str(capture_row.get("manual_next_required_action", "")).strip()
                or str(capture_row.get("next_required_action", "")).strip()
                or ("manual_negative_evidence_review" if capture_policy_bucket == "review_only" else "manual_curated_search_or_defer")
            )
        elif (
            is_binder
            and str(capture_row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
            and str(capture_row.get("manual_promotion_blocker", "")).strip() == "activity_present_manual_confirmation_required"
        ):
            review_reason = "supportive target-specific human PXR evidence exists, but manual confirmation is still required before binder promotion"
            honesty = str(capture_row.get("manual_assay_type_honesty", "")).strip() or "activity_present_manual_confirmation_required"
            next_action = str(capture_row.get("manual_next_required_action", "")).strip() or "manual_curated_search_or_defer"
        elif (
            is_binder
            and str(capture_row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
            and str(capture_row.get("manual_promotion_blocker", "")).strip() == "quantitative_binding_value_or_activity_proxy_missing"
        ):
            review_reason = "target-specific human PXR binder evidence is confirmed, but quantitative provenance is still missing before binder promotion"
            honesty = (
                str(capture_row.get("manual_assay_type_honesty", "")).strip()
                or "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing"
            )
            next_action = str(capture_row.get("manual_next_required_action", "")).strip() or "curate_quantitative_binding_value"
        elif is_binder and ligand == "bexarotene":
            review_reason = "remaining OOD binder without confirmed local human PXR activity in the current curated set"
            honesty = "no_local_target_activity_curated"
            next_action = "manual_curated_search_or_defer"
        elif ligand == "acetaminophen" and not is_binder:
            review_reason = "remaining non-binder row conflicts with a weak human PXR activity proxy in the current curated set"
            honesty = "activity_proxy_conflicts_with_non_binder"
            next_action = "manual_curated_search_or_defer"
        elif ligand in {"caffeine", "nicotinamide", "aspirin"} and not is_binder:
            review_reason = "remaining row has no local human PXR target-specific activity in the current curated set"
            honesty = "no_local_target_activity_curated"
            next_action = "manual_curated_search_or_defer"
        elif ligand == "ibuprofen" and not is_binder:
            review_reason = "remaining negative-like row backed only by a weak human PXR activity upper bound"
            honesty = "activity_upper_bound_only_not_quantitative_nonbinder"
            next_action = "manual_negative_evidence_review"
        elif is_binder:
            review_reason = "remaining binder candidate after verified core/OOD tranche"
            honesty = "activity_proxy_or_binding_value_needed"
            next_action = "curate_quantitative_binding_value"
        else:
            review_reason = "remaining negative-control style row after verified binder tranche"
            honesty = "no_quantitative_nonbinder_value_curated"
            next_action = "manual_negative_evidence_review"
        slice_rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "replacement_ligand_id": ligand,
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "verification_status": str(row.get("verification_status", "")).strip(),
                "review_reason": review_reason,
                "assay_type_honesty": honesty,
                "ready_for_authoritative_apply": "no",
                "next_required_action": next_action,
            }
        )
    action_priority = {
        "manual_negative_evidence_review": 0,
        "curate_quantitative_binding_value": 1,
        "manual_curated_search_or_defer": 2,
    }
    slice_rows.sort(
        key=lambda row: (
            action_priority.get(str(row.get("next_required_action", "")), 9),
            int(str(row.get("priority_rank", "999"))),
        )
    )
    selected_rows = slice_rows[:limit]
    return {
        "summary": {
            "row_count": len(selected_rows),
            "selected_after_verified_tranche": True,
            "contains_binder_gap": any(
                row["replacement_is_binder"] == "1"
                and row["assay_type_honesty"] in {
                    "no_local_target_activity_curated",
                    "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                }
                for row in selected_rows
            ),
            "supportive_binder_review_count": sum(
                1
                for row in selected_rows
                if row["replacement_is_binder"] == "1"
                and "manual_confirmation_required" in str(row.get("assay_type_honesty", ""))
            ),
            "confirmed_binder_quantitative_gap_count": sum(
                1
                for row in selected_rows
                if row["replacement_is_binder"] == "1"
                and str(row.get("assay_type_honesty", "")).strip()
                == "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing"
            ),
            "next_required_step": "Defer unresolved PXR rows unless target-specific human activity supports a safer classification; keep only clearly weak upper-bound negatives as review-only.",
        },
        "rows": selected_rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# PXR Next Verification Slice",
        "",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- selected_after_verified_tranche: `{str(payload['summary']['selected_after_verified_tranche']).lower()}`",
        f"- contains_binder_gap: `{str(payload['summary']['contains_binder_gap']).lower()}`",
        f"- supportive_binder_review_count: `{payload['summary']['supportive_binder_review_count']}`",
        f"- confirmed_binder_quantitative_gap_count: `{payload['summary']['confirmed_binder_quantitative_gap_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Rows",
        "",
        "| priority_rank | packet_step | ligand | binder | assay_type_honesty | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | `{row['assay_type_honesty']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the next PXR verification slice after the current verified binder tranche.")
    p.add_argument("--sheet-csv", default=DEFAULT_SHEET_CSV)
    p.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    p.add_argument("--limit", type=int, default=4)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rows = _read_csv(_resolve(args.sheet_csv))
    payload = build_payload(rows, args.limit, _load_optional_json(_resolve(args.capture_sheet_json)))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
