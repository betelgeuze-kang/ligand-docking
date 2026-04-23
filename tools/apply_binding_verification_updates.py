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
        "sheet_json": "runs/ca2_binding_verification_sheet_current.json",
        "sheet_md": "runs/ca2_binding_verification_sheet_current.md",
        "updates_json": "runs/ca2_binding_verification_updates_current.json",
        "title": "CA2 Binding Verification Sheet",
    },
    "pxr": {
        "sheet_csv": "runs/pxr_binding_verification_sheet_current.csv",
        "sheet_json": "runs/pxr_binding_verification_sheet_current.json",
        "sheet_md": "runs/pxr_binding_verification_sheet_current.md",
        "updates_json": "runs/pxr_binding_verification_updates_current.json",
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


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- binder_row_count: `{payload['summary']['binder_row_count']}`",
        f"- non_binder_row_count: `{payload['summary']['non_binder_row_count']}`",
        f"- verified_row_count: `{payload['summary']['verified_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Verification Rows",
        "",
        "| priority_rank | packet_step | replacement_ligand_id | binder | verification_status | verify_reference_binding_kcal_mol |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["sheet_rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | `{row['verification_status']}` | {row['verify_reference_binding_kcal_mol']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(sheet_rows: list[dict[str, str]], updates_payload: dict[str, Any]) -> dict[str, Any]:
    updates_by_step = {str(row.get("packet_step", "")).strip(): row for row in updates_payload.get("rows", [])}
    updated_rows: list[dict[str, Any]] = []
    binder_count = 0
    verified_count = 0
    for row in sheet_rows:
        out = dict(row)
        packet_step = str(out.get("packet_step", "")).strip()
        if str(out.get("replacement_is_binder", "")).strip() == "1":
            binder_count += 1
        update = updates_by_step.get(packet_step)
        if update:
            out["verify_reference_binding_kcal_mol"] = str(update.get("verify_reference_binding_kcal_mol", "")).strip()
            out["verify_provenance_source"] = str(update.get("verify_provenance_source", "")).strip()
            out["verify_source_url"] = str(update.get("verify_source_url", "")).strip()
            out["verification_status"] = str(update.get("verification_status", "")).strip() or out.get("verification_status", "")
            note = str(out.get("notes", "")).strip()
            evidence_note = str(update.get("evidence_note", "")).strip()
            if evidence_note and evidence_note not in note:
                out["notes"] = f"{note} {evidence_note}".strip()
        if str(out.get("verification_status", "")).strip().startswith("verified_"):
            verified_count += 1
        updated_rows.append(out)
    summary = {
        "family": str(updates_payload.get("summary", {}).get("family", "")).strip(),
        "row_count": len(updated_rows),
        "binder_row_count": binder_count,
        "non_binder_row_count": len(updated_rows) - binder_count,
        "verified_row_count": verified_count,
        "next_required_step": "Manually review the verified rows, then copy accepted values into the authoritative replacement workbook.",
    }
    return {"summary": summary, "sheet_rows": updated_rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply curated verification updates onto the live CA2/PXR binding verification sheets.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--sheet-csv")
    parser.add_argument("--sheet-json")
    parser.add_argument("--sheet-md")
    parser.add_argument("--updates-json")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("sheet_csv", "sheet_json", "sheet_md", "updates_json"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    sheet_rows = _read_csv(_resolve(args.sheet_csv))
    updates_payload = json.loads(_resolve(args.updates_json).read_text(encoding="utf-8"))
    payload = build_payload(sheet_rows, updates_payload)
    sheet_csv = _resolve(args.sheet_csv)
    sheet_json = _resolve(args.sheet_json)
    sheet_md = _resolve(args.sheet_md)
    _write_csv(sheet_csv, payload["sheet_rows"])
    sheet_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(sheet_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()
