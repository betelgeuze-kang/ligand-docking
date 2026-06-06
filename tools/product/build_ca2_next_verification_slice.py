#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHEET_CSV = "runs/ca2_binding_verification_sheet_current.csv"
DEFAULT_OUT_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_OUT_CSV = "runs/ca2_next_verification_slice_current.csv"
DEFAULT_OUT_MD = "runs/ca2_next_verification_slice_current.md"


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


def build_payload(rows: list[dict[str, str]], limit: int) -> dict[str, Any]:
    remaining = [
        row
        for row in rows
        if not str(row.get("verification_status", "")).strip().startswith("verified_")
    ]
    remaining.sort(key=lambda row: int(str(row.get("priority_rank", "999"))))
    selected = remaining[:limit]
    slice_rows: list[dict[str, Any]] = []
    for row in selected:
        packet = str(row.get("packet", "")).strip()
        ligand = str(row.get("replacement_ligand_id", "")).strip()
        is_binder = str(row.get("replacement_is_binder", "")).strip() == "1"
        if not is_binder and ligand == "acetaminophen":
            review_reason = "core negative-like row stays review-only because weak target-specific CA2 activity conflicts with forcing a hard non-binder label"
            honesty = "review_only_negative_conflict_with_weak_activity"
            next_action = "manual_negative_evidence_review"
        elif not is_binder and ligand in {"metformin", "caffeine", "ibuprofen", "aspirin"}:
            review_reason = "negative-like CA2 row lacks direct target-specific quantitative negative evidence and stays review-only"
            honesty = "no_quantitative_nonbinder_value_curated"
            next_action = "manual_negative_evidence_review"
        elif not is_binder and packet == "core":
            review_reason = "highest-value remaining core row after verified binder tranche"
            honesty = "no_quantitative_nonbinder_value_curated"
            next_action = "manual_negative_evidence_review"
        elif is_binder:
            review_reason = "next direct binder candidate once core negative review is staged"
            honesty = "direct_binding_value_expected"
            next_action = "curate_quantitative_binding_value"
        else:
            review_reason = "remaining lower-priority row after core tranche"
            honesty = "manual_nonbinder_review_or_defer"
            next_action = "manual_review"
        slice_rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet": packet,
                "packet_step": str(row.get("packet_step", "")).strip(),
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "verification_status": str(row.get("verification_status", "")).strip(),
                "review_reason": review_reason,
                "quantitative_value_available": "no",
                "assay_type_honesty": honesty,
                "ready_for_authoritative_apply": "no",
                "next_required_action": next_action,
                "notes": "Core non-binders remain review-only until negative evidence is manually curated; no proxy ΔG should be injected automatically."
                if not is_binder and next_action == "manual_negative_evidence_review"
                else (
                    "This row should stay review-only until target-specific CA2 negative evidence is curated; do not force a non-binder label or auto-defer it."
                    if not is_binder
                    else "Binder row still needs quantitative value/provenance curation before any apply step."
                )
            }
        )
    payload = {
        "summary": {
            "row_count": len(slice_rows),
            "selected_after_verified_top3": True,
            "contains_only_core_rows": all(row["packet"] == "core" for row in slice_rows),
            "next_required_step": "Review these rows manually before any OOD binder promotion beyond the already-verified tranche.",
        },
        "rows": slice_rows,
    }
    return payload


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CA2 Next Verification Slice",
        "",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- selected_after_verified_top3: `{str(payload['summary']['selected_after_verified_top3']).lower()}`",
        f"- contains_only_core_rows: `{str(payload['summary']['contains_only_core_rows']).lower()}`",
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
    p = argparse.ArgumentParser(description="Build the next CA2 verification slice after the already-verified top binder tranche.")
    p.add_argument("--sheet-csv", default=DEFAULT_SHEET_CSV)
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rows = _read_csv(_resolve(args.sheet_csv))
    payload = build_payload(rows, args.limit)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
