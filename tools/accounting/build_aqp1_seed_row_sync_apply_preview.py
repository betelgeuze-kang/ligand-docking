#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import argparse
from pathlib import Path


RUNS = Path("runs")

SEED_FILL_DRAFT_JSON = RUNS / "aqp1_seed_row_fill_draft_current.json"
WORKBOOK_JSON = RUNS / "aqp1_packet_replacement_workbook_current.json"
FIRST_SEED_PACKET_JSON = RUNS / "aqp1_first_seed_row_packet_current.json"

OUT_JSON = RUNS / "aqp1_seed_row_sync_apply_preview_current.json"
OUT_CSV = RUNS / "aqp1_seed_row_sync_apply_preview_current.csv"
OUT_MD = RUNS / "aqp1_seed_row_sync_apply_preview_current.md"

TARGET_STEP = "core_binder_01"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {str(row[key]): row for row in rows}


def build_row(seed_fill_draft: dict, workbook: dict, first_seed_packet: dict, packet_step: str) -> dict:
    workbook_row = index_by(workbook["workbook_rows"], "packet_step")[packet_step]
    field_rows = index_by(seed_fill_draft["rows"], "field_name")
    seed_summary = first_seed_packet["summary"]

    unresolved = [field_name for field_name, row in field_rows.items() if row["reviewer_safe_now"] != "yes"]

    return {
        "packet_step": packet_step,
        "target": workbook_row["target"],
        "candidate_name": seed_summary["candidate_name"],
        "current_ligand_id": workbook_row["current_ligand_id"],
        "staged_replacement_ligand_id": field_rows["replacement_ligand_id"]["staged_fill_value"],
        "staged_replacement_reference_binding_kcal_mol": field_rows["replacement_reference_binding_kcal_mol"]["staged_fill_value"],
        "staged_replacement_source": field_rows["replacement_source"]["staged_fill_value"],
        "staged_replacement_smiles": field_rows["replacement_smiles"]["staged_fill_value"],
        "staged_replacement_scaffold": field_rows["replacement_scaffold"]["staged_fill_value"],
        "replacement_is_binder": workbook_row["replacement_is_binder"],
        "replacement_role": workbook_row["replacement_role"],
        "apply_reference_row": workbook_row["apply_reference_row"],
        "apply_split_row": workbook_row["apply_split_row"],
        "apply_meta_row": workbook_row["apply_meta_row"],
        "sync_preview_status": "non_authoritative_partial_stage_only",
        "manual_verdict_status": seed_fill_draft["summary"]["manual_verdict_status"],
        "promotion_blocker": seed_summary["promotion_blocker"],
        "unresolved_fields": ",".join(sorted(unresolved)),
        "authoritative_apply_allowed": "no",
    }


def build_summary(seed_fill_draft: dict, row: dict) -> dict:
    unresolved = [x for x in row["unresolved_fields"].split(",") if x]
    safe_staged_field_count = sum(
        1
        for field in [
            "staged_replacement_ligand_id",
            "staged_replacement_reference_binding_kcal_mol",
            "staged_replacement_source",
            "staged_replacement_smiles",
            "staged_replacement_scaffold",
        ]
        if str(row.get(field, "")).strip()
    )
    return {
        "target_id": seed_fill_draft["summary"]["target_id"],
        "packet_step": row["packet_step"],
        "candidate_name": row["candidate_name"],
        "safe_staged_field_count": safe_staged_field_count,
        "unresolved_field_count": len(unresolved),
        "sync_preview_status": row["sync_preview_status"],
        "manual_verdict_status": row["manual_verdict_status"],
        "authoritative_apply_allowed": False,
        "next_required_step": (
            "This preview shows the exact non-authoritative synchronized row stage that is safe now. "
            f"Only keep `{','.join(unresolved)}` unresolved until curated."
            if unresolved
            else "This preview shows the exact non-authoritative synchronized row stage that is safe now. All row fields are staged, but the row must remain non-authoritative until binding/provenance review is complete."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the non-authoritative AQP1 seed-row sync/apply preview.")
    parser.add_argument("--seed-fill-draft-json", default=str(SEED_FILL_DRAFT_JSON))
    parser.add_argument("--workbook-json", default=str(WORKBOOK_JSON))
    parser.add_argument("--seed-packet-json", default=str(FIRST_SEED_PACKET_JSON))
    parser.add_argument("--packet-step", default=TARGET_STEP)
    parser.add_argument("--out-json", default=str(OUT_JSON))
    parser.add_argument("--out-csv", default=str(OUT_CSV))
    parser.add_argument("--out-md", default=str(OUT_MD))
    return parser.parse_args()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, row: dict) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def write_md(path: Path, summary: dict, row: dict) -> None:
    unresolved = [x for x in row["unresolved_fields"].split(",") if x]
    lines = [
        "# AQP1 Seed Row Sync Apply Preview",
        "",
        f"- target_id: `{summary['target_id']}`",
        f"- packet_step: `{summary['packet_step']}`",
        f"- candidate_name: `{summary['candidate_name']}`",
        f"- safe_staged_field_count: `{summary['safe_staged_field_count']}`",
        f"- unresolved_field_count: `{summary['unresolved_field_count']}`",
        f"- sync_preview_status: `{summary['sync_preview_status']}`",
        f"- manual_verdict_status: `{summary['manual_verdict_status']}`",
        f"- authoritative_apply_allowed: `{summary['authoritative_apply_allowed']}`",
        "",
        "## Draft Synchronized Row",
        "",
        "| field | staged value |",
        "| --- | --- |",
    ]
    ordered = [
        "current_ligand_id",
        "staged_replacement_ligand_id",
        "staged_replacement_reference_binding_kcal_mol",
        "staged_replacement_source",
        "staged_replacement_smiles",
        "staged_replacement_scaffold",
        "replacement_is_binder",
        "replacement_role",
        "apply_reference_row",
        "apply_split_row",
        "apply_meta_row",
    ]
    for field in ordered:
        lines.append(f"| `{field}` | `{row[field]}` |")
    lines.extend(
        [
            "",
            "## Blockers",
            "",
            f"- promotion_blocker: `{row['promotion_blocker']}`",
            f"- unresolved_fields: `{row['unresolved_fields']}`",
            "",
            "## Interpretation",
            "",
            "- This is only a draft synchronized-row stage preview.",
            "- It does not make the row authoritative or apply-ready.",
            "- Right now only the explicitly staged fields are safe to carry forward while the row remains non-authoritative.",
        ]
    )
    if unresolved:
        lines.append(f"- Remaining unresolved fields: `{','.join(unresolved)}`")
    else:
        lines.append("- No structural fields remain unresolved.")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    seed_fill_draft = load_json(Path(args.seed_fill_draft_json))
    workbook = load_json(Path(args.workbook_json))
    first_seed_packet = load_json(Path(args.seed_packet_json))

    row = build_row(seed_fill_draft, workbook, first_seed_packet, args.packet_step)
    summary = build_summary(seed_fill_draft, row)
    payload = {"summary": summary, "row": row}

    write_json(Path(args.out_json), payload)
    write_csv(Path(args.out_csv), row)
    write_md(Path(args.out_md), summary, row)


if __name__ == "__main__":
    main()
