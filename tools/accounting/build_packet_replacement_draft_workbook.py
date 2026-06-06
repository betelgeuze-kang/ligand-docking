#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "ca2": {
        "workbook_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "prefill_csv": "runs/ca2_packet_replacement_prefill_current.csv",
        "out_json": "runs/ca2_packet_replacement_draft_current.json",
        "out_csv": "runs/ca2_packet_replacement_draft_current.csv",
        "out_md": "runs/ca2_packet_replacement_draft_current.md",
        "title": "CA2 Packet Replacement Draft Workbook",
    },
    "pxr": {
        "workbook_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "prefill_csv": "runs/pxr_packet_replacement_prefill_current.csv",
        "out_json": "runs/pxr_packet_replacement_draft_current.json",
        "out_csv": "runs/pxr_packet_replacement_draft_current.csv",
        "out_md": "runs/pxr_packet_replacement_draft_current.md",
        "title": "PXR Packet Replacement Draft Workbook",
    },
}

BASE_REQUIRED = [
    "replacement_ligand_id",
    "replacement_reference_binding_kcal_mol",
    "replacement_source",
    "replacement_smiles",
    "replacement_scaffold",
]


def _overlay_required_missing_fields(row: dict[str, Any], family: str) -> list[str]:
    overlay = dict(row)
    if str(row.get("draft_replacement_ligand_id", "")).strip():
        overlay["replacement_ligand_id"] = str(row.get("draft_replacement_ligand_id", "")).strip()
    if str(row.get("draft_replacement_reference_binding_kcal_mol", "")).strip():
        overlay["replacement_reference_binding_kcal_mol"] = str(row.get("draft_replacement_reference_binding_kcal_mol", "")).strip()
    if str(row.get("draft_replacement_source", "")).strip():
        overlay["replacement_source"] = str(row.get("draft_replacement_source", "")).strip()
    if str(row.get("draft_replacement_smiles", "")).strip():
        overlay["replacement_smiles"] = str(row.get("draft_replacement_smiles", "")).strip()
    if str(row.get("draft_replacement_scaffold", "")).strip():
        overlay["replacement_scaffold"] = str(row.get("draft_replacement_scaffold", "")).strip()
    return _required_missing_fields(overlay, family)


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


def _required_missing_fields(row: dict[str, Any], family: str) -> list[str]:
    required = list(BASE_REQUIRED)
    if family == "pxr" and str(row.get("apply_split_row", "")).strip().lower() == "yes":
        required.append("replacement_role")
    return [field for field in required if not str(row.get(field, "")).strip()]


def build_payload(workbook_rows: list[dict[str, str]], prefill_rows: list[dict[str, str]], family: str) -> dict[str, Any]:
    prefill_by_step = {str(row.get("packet_step", "")).strip(): row for row in prefill_rows}
    draft_rows: list[dict[str, Any]] = []
    applied_count = 0
    manual_required_count = 0
    missing_counter: Counter[str] = Counter()

    for workbook_row in workbook_rows:
        packet_step = str(workbook_row.get("packet_step", "")).strip()
        prefill = prefill_by_step.get(packet_step, {})
        row = dict(workbook_row)
        candidate_name = str(prefill.get("candidate_ligand_name", "")).strip()
        candidate_kind = str(prefill.get("candidate_source_kind", "")).strip()
        candidate_hint = str(prefill.get("candidate_reference_hint", "")).strip()
        manual_required = str(prefill.get("candidate_manual_verification_required", "yes")).strip() or "yes"

        row["draft_replacement_ligand_id"] = str(row.get("draft_replacement_ligand_id", "")).strip()
        row["draft_replacement_reference_binding_kcal_mol"] = str(row.get("draft_replacement_reference_binding_kcal_mol", "")).strip()
        row["draft_replacement_source"] = str(row.get("draft_replacement_source", "")).strip()
        row["draft_replacement_smiles"] = str(row.get("draft_replacement_smiles", "")).strip()
        row["draft_replacement_scaffold"] = str(row.get("draft_replacement_scaffold", "")).strip()

        applied = False
        if candidate_name and not row["draft_replacement_ligand_id"]:
            row["draft_replacement_ligand_id"] = candidate_name
            applied = True
        if candidate_kind and not row["draft_replacement_source"]:
            row["draft_replacement_source"] = f"draft_seed::{candidate_kind}"
            applied = True

        missing = _overlay_required_missing_fields(row, family)
        for field in missing:
            missing_counter[field] += 1
        row["row_ready_for_apply"] = "no"

        row["draft_prefill_applied"] = "yes" if applied else "no"
        row["draft_claim_ready"] = "no"
        row["draft_manual_verification_required"] = manual_required
        row["draft_verification_status"] = "manual_review_pending"
        row["draft_manual_binding_review_status"] = "pending"
        row["draft_manual_provenance_review_status"] = "pending"
        row["draft_manual_structure_review_status"] = "pending"
        row["draft_authoritative_apply_approved"] = "no"
        row["draft_candidate_ligand_name"] = candidate_name
        row["draft_candidate_source_kind"] = candidate_kind
        row["draft_candidate_reference_hint"] = candidate_hint
        row["draft_candidate_anchor_pdb_id"] = str(prefill.get("candidate_anchor_pdb_id", "")).strip()
        row["draft_candidate_anchor_native_path"] = str(prefill.get("candidate_anchor_native_path", "")).strip()
        row["draft_assay_type"] = "unknown"
        row["draft_quantitation_kind"] = "negative_placeholder" if str(row.get("replacement_is_binder", "")).strip() == "0" else "manual_assignment_required"
        row["draft_claim_scope"] = "nonbinder_needs_manual_call" if str(row.get("replacement_is_binder", "")).strip() == "0" else "manual_review_required"
        row["draft_assay_type_honesty"] = "explicit"
        row["draft_missing_claim_fields"] = ",".join(missing)
        row["draft_missing_manual_checks"] = "binding,provenance,structure"
        row["draft_ready_for_authoritative_apply"] = "yes" if not missing else "no"
        row["draft_apply_block_reason"] = "manual verification pending" if missing else "manual verification pending despite structurally complete row"

        notes = str(row.get("notes", "")).strip()
        draft_note = "Draft prefill copied from candidate seed into draft_* fields only; authoritative replacement_* values remain unchanged until verified promotion."
        row["notes"] = f"{notes} {draft_note}".strip()

        draft_rows.append(row)
        if applied:
            applied_count += 1
        if manual_required.lower() == "yes":
            manual_required_count += 1

    summary = {
        "family": family,
        "draft_row_count": len(draft_rows),
        "draft_prefill_applied_count": applied_count,
        "manual_verification_required_count": manual_required_count,
        "ready_for_apply_row_count": sum(1 for row in draft_rows if str(row.get("row_ready_for_apply", "")).strip().lower() == "yes"),
        "blocked_row_count": sum(1 for row in draft_rows if str(row.get("row_ready_for_apply", "")).strip().lower() != "yes"),
        "most_common_missing_field": missing_counter.most_common(1)[0][0] if missing_counter else "",
        "missing_field_counts": dict(missing_counter),
        "next_required_step": "Use this draft workbook for review only. Verify binding value, provenance, SMILES, and scaffold before copying any row into the authoritative replacement workbook.",
    }
    return {"summary": summary, "draft_rows": draft_rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"- family: `{summary['family']}`",
        f"- draft_row_count: `{summary['draft_row_count']}`",
        f"- draft_prefill_applied_count: `{summary['draft_prefill_applied_count']}`",
        f"- ready_for_apply_row_count: `{summary['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{summary['blocked_row_count']}`",
        f"- most_common_missing_field: `{summary['most_common_missing_field']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Missing Field Counts",
        "",
        "| field | count |",
        "| --- | ---: |",
    ]
    for field, count in sorted(summary["missing_field_counts"].items()):
        lines.append(f"| {field} | {count} |")
    lines.extend([
        "",
        "## Draft Rows",
        "",
        "| packet_step | draft_replacement_ligand_id | draft_replacement_source | draft_prefill_applied | row_ready_for_apply | draft_missing_claim_fields |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for row in payload["draft_rows"]:
        lines.append(
            f"| {row.get('packet_step','')} | `{row.get('draft_replacement_ligand_id','')}` | `{row.get('draft_replacement_source','')}` | {row.get('draft_prefill_applied','')} | {row.get('row_ready_for_apply','')} | {row.get('draft_missing_claim_fields','')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe draft workbook by copying low-risk candidate seed fields into a separate replacement workbook copy.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--workbook-csv")
    parser.add_argument("--prefill-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    if not args.workbook_csv:
        args.workbook_csv = defaults["workbook_csv"]
    if not args.prefill_csv:
        args.prefill_csv = defaults["prefill_csv"]
    if not args.out_json:
        args.out_json = defaults["out_json"]
    if not args.out_csv:
        args.out_csv = defaults["out_csv"]
    if not args.out_md:
        args.out_md = defaults["out_md"]
    return args


def main() -> None:
    args = parse_args()
    workbook_rows = _read_csv(_resolve(args.workbook_csv))
    prefill_rows = _read_csv(_resolve(args.prefill_csv))
    payload = build_payload(workbook_rows, prefill_rows, args.family)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["draft_rows"])
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()
