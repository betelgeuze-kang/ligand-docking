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
        "prefill_csv": "runs/ca2_packet_replacement_prefill_current.csv",
        "out_json": "runs/ca2_packet_replacement_draft_apply_current.json",
        "out_csv": "runs/ca2_packet_replacement_draft_apply_current.csv",
        "out_md": "runs/ca2_packet_replacement_draft_apply_current.md",
        "title": "CA2 Packet Replacement Draft Apply",
    },
    "pxr": {
        "prefill_csv": "runs/pxr_packet_replacement_prefill_current.csv",
        "out_json": "runs/pxr_packet_replacement_draft_apply_current.json",
        "out_csv": "runs/pxr_packet_replacement_draft_apply_current.csv",
        "out_md": "runs/pxr_packet_replacement_draft_apply_current.md",
        "title": "PXR Packet Replacement Draft Apply",
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


def build_payload(prefill_rows: list[dict[str, str]], family: str) -> dict[str, Any]:
    draft_rows: list[dict[str, Any]] = []
    candidate_attached = 0
    for row in prefill_rows:
        candidate_name = str(row.get("candidate_ligand_name", "")).strip()
        seed_attached = str(row.get("prefill_status", "")).strip() == "seed_attached" and bool(candidate_name)
        if seed_attached:
            candidate_attached += 1
        draft = dict(row)
        draft.update(
            {
                "draft_replacement_ligand_id": candidate_name,
                "draft_replacement_reference_binding_kcal_mol": "",
                "draft_replacement_source": f"TODO_VERIFY::{row.get('candidate_source_kind', '')}".strip(),
                "draft_replacement_smiles": "",
                "draft_replacement_scaffold": "",
                "draft_replacement_anchor_pdb_id": str(row.get("candidate_anchor_pdb_id", "")).strip(),
                "draft_replacement_anchor_native_path": str(row.get("candidate_anchor_native_path", "")).strip(),
                "draft_manual_verification_required": "yes",
                "draft_can_promote_after_verification": "yes" if seed_attached else "no",
                "draft_apply_status": "seed_promoted_to_draft" if seed_attached else "seed_missing",
                "authoritative_replacement_fields_touched": "no",
            }
        )
        draft_rows.append(draft)

    summary = {
        "family": family,
        "replacement_row_count": len(prefill_rows),
        "candidate_attached_row_count": candidate_attached,
        "draft_promoted_row_count": candidate_attached,
        "seed_missing_row_count": len(prefill_rows) - candidate_attached,
        "authoritative_replacement_fields_touched": False,
        "next_required_step": "Review the draft_* columns, verify provenance/binding/smiles/scaffold, then manually copy approved values into the authoritative replacement workbook.",
    }
    return {"summary": summary, "draft_rows": draft_rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    summary = payload["summary"]
    lines = [
        f"# {title}",
        "",
        f"- replacement_row_count: `{summary['replacement_row_count']}`",
        f"- candidate_attached_row_count: `{summary['candidate_attached_row_count']}`",
        f"- draft_promoted_row_count: `{summary['draft_promoted_row_count']}`",
        f"- seed_missing_row_count: `{summary['seed_missing_row_count']}`",
        f"- authoritative_replacement_fields_touched: `{str(summary['authoritative_replacement_fields_touched']).lower()}`",
        "",
        "## Safety",
        "",
        "- This file does not modify authoritative `replacement_*` workbook fields.",
        "- It only exposes `draft_*` columns for manual review.",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Draft Rows",
        "",
        "| packet_step | current_ligand_id | draft_replacement_ligand_id | draft_replacement_source | draft_apply_status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["draft_rows"]:
        lines.append(
            f"| {row.get('packet_step','')} | `{row.get('current_ligand_id','')}` | `{row.get('draft_replacement_ligand_id','')}` | `{row.get('draft_replacement_source','')}` | {row.get('draft_apply_status','')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe draft-apply workbook from packet replacement prefill rows.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--prefill-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
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
    defaults = FAMILY_DEFAULTS[args.family]
    prefill_rows = _read_csv(_resolve(args.prefill_csv))
    payload = build_payload(prefill_rows, args.family)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["draft_rows"])
    _write_markdown(out_md, payload, defaults["title"])


if __name__ == "__main__":
    main()
