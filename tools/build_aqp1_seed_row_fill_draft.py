#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import argparse
from pathlib import Path


RUNS = Path("runs")

SEED_PACKET_JSON = RUNS / "aqp1_first_seed_row_packet_current.json"
WORKBOOK_JSON = RUNS / "aqp1_packet_replacement_workbook_current.json"
MANUAL_APPLY_DRAFT_JSON = RUNS / "aqp1_manual_verdict_apply_draft_current.json"

OUT_JSON = RUNS / "aqp1_seed_row_fill_draft_current.json"
OUT_CSV = RUNS / "aqp1_seed_row_fill_draft_current.csv"
OUT_MD = RUNS / "aqp1_seed_row_fill_draft_current.md"

TARGET_STEP = "core_binder_01"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {str(row[key]): row for row in rows}


def build_rows(seed_packet: dict, workbook: dict, manual_apply: dict, packet_step: str) -> list[dict]:
    workbook_row = index_by(workbook["workbook_rows"], "packet_step")[packet_step]
    apply_row = index_by(manual_apply["rows"], "packet_step")[packet_step]
    seed_fields = index_by(seed_packet["rows"], "field_name")

    ordered_fields = [
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "replacement_smiles",
        "replacement_scaffold",
    ]

    rows: list[dict] = []
    for field_name in ordered_fields:
        seed = seed_fields[field_name]
        current_value = workbook_row.get(field_name, "")
        seed_status = str(seed["status"])
        seed_safe = seed_status == "ready_to_copy" or seed_status.startswith("staged_review_")
        staged_fill_value = seed["suggested_value"] if seed_safe else ""
        field_status = seed["status"]
        reviewer_safe_now = "yes" if seed_safe else "no"
        current_text = str(current_value).strip()
        current_is_source_placeholder = (
            field_name == "replacement_source"
            and current_text.startswith("pubchem_name_resolve_pending::")
            and str(staged_fill_value).strip()
        )
        if (
            field_name in {"replacement_ligand_id", "replacement_source", "replacement_smiles", "replacement_scaffold"}
            and current_text
            and not current_is_source_placeholder
        ):
            staged_fill_value = current_text
            field_status = (
                "staged_review_identifier"
                if field_name == "replacement_ligand_id"
                else "staged_review_source"
                if field_name == "replacement_source"
                else "staged_review_structure"
            )
            reviewer_safe_now = "yes"
        rows.append(
            {
                "packet_step": packet_step,
                "candidate_name": apply_row["candidate_name"],
                "field_name": field_name,
                "current_workbook_value": current_value,
                "suggested_value": seed["suggested_value"],
                "staged_fill_value": staged_fill_value,
                "field_status": field_status,
                "reviewer_safe_now": reviewer_safe_now,
                "manual_verdict_update": apply_row["manual_verdict_update"],
                "manual_confidence_update": apply_row["manual_confidence_update"],
                "promotion_blocker": apply_row["promotion_blocker"],
                "note": seed["note"],
            }
        )
    return rows


def build_summary(seed_packet: dict, rows: list[dict], packet_step: str) -> dict:
    unresolved_fields = [row["field_name"] for row in rows if row["reviewer_safe_now"] == "no"]
    return {
        "target_id": seed_packet["summary"]["target_id"],
        "packet_step": packet_step,
        "candidate_name": seed_packet["summary"]["candidate_name"],
        "required_seed_field_count": seed_packet["summary"]["required_seed_field_count"],
        "safe_prefill_field_count": sum(1 for row in rows if row["reviewer_safe_now"] == "yes"),
        "blocked_field_count": sum(1 for row in rows if row["reviewer_safe_now"] == "no"),
        "manual_verdict_status": "completed_manual_verdict",
        "authoritative_apply_allowed": False,
        "next_required_step": (
            f"Use this draft only to prefill reviewer-safe seed-row fields for {packet_step}. "
            f"Only keep `{','.join(unresolved_fields)}` unresolved until manually curated."
            if unresolved_fields
            else f"All seed-row fields for {packet_step} are reviewer-safe staged values; keep the row non-authoritative until binding/provenance review is complete."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the non-authoritative AQP1 seed-row fill draft.")
    parser.add_argument("--seed-packet-json", default=str(SEED_PACKET_JSON))
    parser.add_argument("--workbook-json", default=str(WORKBOOK_JSON))
    parser.add_argument("--manual-apply-draft-json", default=str(MANUAL_APPLY_DRAFT_JSON))
    parser.add_argument("--packet-step", default=TARGET_STEP)
    parser.add_argument("--out-json", default=str(OUT_JSON))
    parser.add_argument("--out-csv", default=str(OUT_CSV))
    parser.add_argument("--out-md", default=str(OUT_MD))
    return parser.parse_args()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, summary: dict, rows: list[dict]) -> None:
    safe_fields = [row["field_name"] for row in rows if row["reviewer_safe_now"] == "yes"]
    unresolved_fields = [row["field_name"] for row in rows if row["reviewer_safe_now"] == "no"]
    lines = [
        "# AQP1 Seed Row Fill Draft",
        "",
        f"- target_id: `{summary['target_id']}`",
        f"- packet_step: `{summary['packet_step']}`",
        f"- candidate_name: `{summary['candidate_name']}`",
        f"- required_seed_field_count: `{summary['required_seed_field_count']}`",
        f"- safe_prefill_field_count: `{summary['safe_prefill_field_count']}`",
        f"- blocked_field_count: `{summary['blocked_field_count']}`",
        f"- manual_verdict_status: `{summary['manual_verdict_status']}`",
        f"- authoritative_apply_allowed: `{summary['authoritative_apply_allowed']}`",
        "",
        "## Rule",
        "",
        "- This is a non-authoritative seed-row draft. Only reviewer-safe fields may be staged now. Blocked fields must remain unresolved.",
        "",
        "## Field Draft",
        "",
        "| field | suggested value | staged fill value | reviewer-safe now | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{field_name}` | `{suggested_value}` | `{staged_fill_value}` | `{reviewer_safe_now}` | `{field_status}` |".format(
                **row
            )
        )
        lines.append(f"- Note: {row['note']}")
    lines.extend(
        [
            "",
            "## Apply If Proceeding Now",
            "",
        ]
    )
    for field_name in safe_fields:
        lines.append(f"- `{field_name}`")
    lines.extend(
        [
            "",
            "## Leave Unresolved",
            "",
        ]
    )
    if unresolved_fields:
        for field_name in unresolved_fields:
            lines.append(f"- `{field_name}`")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    seed_packet = load_json(Path(args.seed_packet_json))
    workbook = load_json(Path(args.workbook_json))
    manual_apply = load_json(Path(args.manual_apply_draft_json))

    rows = build_rows(seed_packet, workbook, manual_apply, args.packet_step)
    summary = build_summary(seed_packet, rows, args.packet_step)
    payload = {"summary": summary, "rows": rows}

    write_json(Path(args.out_json), payload)
    write_csv(Path(args.out_csv), rows)
    write_md(Path(args.out_md), summary, rows)


if __name__ == "__main__":
    main()
