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
        "queue_csv": "runs/ca2_packet_replacement_verification_queue_current.csv",
        "workbook_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "out_json": "runs/ca2_binding_verification_sheet_current.json",
        "out_csv": "runs/ca2_binding_verification_sheet_current.csv",
        "out_md": "runs/ca2_binding_verification_sheet_current.md",
        "title": "CA2 Binding Verification Sheet",
    },
    "pxr": {
        "queue_csv": "runs/pxr_packet_replacement_verification_queue_current.csv",
        "workbook_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "out_json": "runs/pxr_binding_verification_sheet_current.json",
        "out_csv": "runs/pxr_binding_verification_sheet_current.csv",
        "out_md": "runs/pxr_binding_verification_sheet_current.md",
        "title": "PXR Binding Verification Sheet",
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


def _existing_verification_by_step(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows = _read_csv(path)
    return {str(row.get("packet_step", "")).strip(): row for row in rows}


def build_payload(
    queue_rows: list[dict[str, str]],
    workbook_rows: list[dict[str, str]],
    family: str,
    existing_verification: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_verification = existing_verification or {}
    workbook_by_step = {str(row.get("packet_step", "")).strip(): row for row in workbook_rows}
    sheet_rows: list[dict[str, Any]] = []
    binder_count = 0
    for queue_row in queue_rows:
        packet_step = str(queue_row.get("packet_step", "")).strip()
        workbook_row = workbook_by_step.get(packet_step, {})
        existing_row = existing_verification.get(packet_step, {})
        is_binder = str(queue_row.get("replacement_is_binder", "")).strip() == "1"
        if is_binder:
            binder_count += 1
        sheet_rows.append(
            {
                "priority_rank": str(queue_row.get("priority_rank", "")).strip(),
                "packet": str(queue_row.get("packet", "")).strip(),
                "packet_step": packet_step,
                "replacement_ligand_id": str(queue_row.get("replacement_ligand_id", "")).strip(),
                "replacement_is_binder": "1" if is_binder else "0",
                "replacement_source": str(queue_row.get("replacement_source", "")).strip(),
                "replacement_smiles": str(workbook_row.get("replacement_smiles", "")).strip(),
                "replacement_scaffold": str(workbook_row.get("replacement_scaffold", "")).strip(),
                "replacement_pubchem_cid": str(workbook_row.get("replacement_pubchem_cid", "")).strip(),
                "replacement_structure_resolution_url": str(workbook_row.get("replacement_structure_resolution_url", "")).strip(),
                "verify_reference_binding_kcal_mol": str(existing_row.get("verify_reference_binding_kcal_mol", "")).strip(),
                "verify_provenance_source": str(existing_row.get("verify_provenance_source", "")).strip(),
                "verify_source_url": str(existing_row.get("verify_source_url", "")).strip(),
                "verification_status": str(existing_row.get("verification_status", "")).strip() or "pending_binding_provenance_review",
                "notes": str(existing_row.get("notes", "")).strip() or (
                    "Start with binder evidence and quantitative affinity."
                    if is_binder
                    else "Use conservative non-binder evidence and keep provenance explicit."
                ),
            }
        )
    summary = {
        "family": family,
        "row_count": len(sheet_rows),
        "binder_row_count": binder_count,
        "non_binder_row_count": len(sheet_rows) - binder_count,
        "next_required_step": "Fill verify_reference_binding_kcal_mol, verify_provenance_source, and verify_source_url for the highest-priority rows first.",
    }
    return {"summary": summary, "sheet_rows": sheet_rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- binder_row_count: `{payload['summary']['binder_row_count']}`",
        f"- non_binder_row_count: `{payload['summary']['non_binder_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Verification Rows",
        "",
        "| priority_rank | packet_step | replacement_ligand_id | binder | replacement_source | verify_reference_binding_kcal_mol |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["sheet_rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | `{row['replacement_source']}` | {row['verify_reference_binding_kcal_mol']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a binding/provenance verification sheet from packet replacement queues.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--queue-csv")
    parser.add_argument("--workbook-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("queue_csv", "workbook_csv", "out_json", "out_csv", "out_md"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    queue_rows = _read_csv(_resolve(args.queue_csv))
    workbook_rows = _read_csv(_resolve(args.workbook_csv))
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        queue_rows,
        workbook_rows,
        args.family,
        existing_verification=_existing_verification_by_step(out_csv),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["sheet_rows"])
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()
