#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


RUNS = Path("runs")

DEFAULT_SEED_PACKET_JSON = RUNS / "glut1_second_wave_seed_row_packet_current.json"
DEFAULT_WORKBOOK_JSON = RUNS / "glut1_packet_replacement_workbook_current.json"
DEFAULT_MANUAL_APPLY_DRAFT_JSON = RUNS / "glut1_manual_verdict_apply_draft_current.json"
DEFAULT_PACKET_STEP = "core_binder_01"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {str(row[key]): row for row in rows}


def _default_output(stem: str, packet_step: str, suffix: str) -> Path:
    if packet_step == "core_binder_01":
        return RUNS / f"{stem}_current.{suffix}"
    return RUNS / f"{stem}_{packet_step}_current.{suffix}"


def build_rows(seed_packet: dict, workbook: dict, manual_apply: dict, packet_step: str) -> list[dict]:
    workbook_row = index_by(workbook["workbook_rows"], "packet_step")[packet_step]
    apply_row = index_by(manual_apply["draft_rows"], "packet_step")[packet_step]
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
        staged_fill_value = seed["suggested_value"] if seed["status"] == "ready_to_copy" else ""
        field_status = seed["status"]
        reviewer_safe_now = "yes" if seed["status"] == "ready_to_copy" else "no"
        if field_name in {"replacement_ligand_id", "replacement_source", "replacement_smiles", "replacement_scaffold"} and str(current_value).strip():
            staged_fill_value = str(current_value).strip()
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
                "draft_manual_verdict_update": apply_row["draft_manual_verdict_update"],
                "draft_manual_confidence_update": apply_row["draft_manual_confidence_update"],
                "promotion_blocker": apply_row["promotion_blocker"],
                "note": seed["note"],
            }
        )
    return rows


def build_summary(seed_packet: dict, rows: list[dict], packet_step: str) -> dict:
    unresolved_fields = [row["field_name"] for row in rows if row["reviewer_safe_now"] == "no"]
    return {
        "target_id": seed_packet["summary"]["target_id"],
        "wave": seed_packet["summary"]["wave"],
        "packet_step": packet_step,
        "candidate_name": seed_packet["summary"]["candidate_name"],
        "required_seed_field_count": seed_packet["summary"]["required_seed_field_count"],
        "safe_prefill_field_count": sum(1 for row in rows if row["reviewer_safe_now"] == "yes"),
        "blocked_field_count": sum(1 for row in rows if row["reviewer_safe_now"] == "no"),
        "manual_verdict_status": "completed_manual_verdict",
        "authoritative_apply_allowed": False,
        "next_required_step": (
            f"Use this draft only to prefill reviewer-safe GLUT1 second-wave seed-row fields for {packet_step}. "
            f"Only keep `{','.join(unresolved_fields)}` unresolved until manually curated."
            if unresolved_fields
            else f"All second-wave seed-row fields for {packet_step} are reviewer-safe staged values, but the row must remain non-authoritative and kcal-blank."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the non-authoritative GLUT1 second-wave seed-row fill draft.")
    parser.add_argument("--seed-packet-json", default=str(DEFAULT_SEED_PACKET_JSON))
    parser.add_argument("--workbook-json", default=str(DEFAULT_WORKBOOK_JSON))
    parser.add_argument("--manual-apply-draft-json", default=str(DEFAULT_MANUAL_APPLY_DRAFT_JSON))
    parser.add_argument("--packet-step", default=DEFAULT_PACKET_STEP)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="")
    parser.add_argument("--out-md", default="")
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
        "# GLUT1 Second-Wave Seed Row Fill Draft",
        "",
        f"- target_id: `{summary['target_id']}`",
        f"- wave: `{summary['wave']}`",
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
        "- This is a second-wave non-authoritative seed-row draft. Only reviewer-safe fields may be staged now. Blocked fields must remain unresolved.",
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
    packet_step = args.packet_step
    seed_packet = load_json(Path(args.seed_packet_json))
    workbook = load_json(Path(args.workbook_json))
    manual_apply = load_json(Path(args.manual_apply_draft_json))

    rows = build_rows(seed_packet, workbook, manual_apply, packet_step)
    summary = build_summary(seed_packet, rows, packet_step)
    payload = {"summary": summary, "rows": rows}

    out_json = Path(args.out_json) if args.out_json else _default_output("glut1_second_wave_seed_row_fill_draft", packet_step, "json")
    out_csv = Path(args.out_csv) if args.out_csv else _default_output("glut1_second_wave_seed_row_fill_draft", packet_step, "csv")
    out_md = Path(args.out_md) if args.out_md else _default_output("glut1_second_wave_seed_row_fill_draft", packet_step, "md")
    write_json(out_json, payload)
    write_csv(out_csv, rows)
    write_md(out_md, summary, rows)


if __name__ == "__main__":
    main()
