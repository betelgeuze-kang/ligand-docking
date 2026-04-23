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
        "replacement_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "seed_csv": "runs/ca2_curated_candidate_source_seed_current.csv",
        "out_json": "runs/ca2_packet_replacement_prefill_current.json",
        "out_csv": "runs/ca2_packet_replacement_prefill_current.csv",
        "out_md": "runs/ca2_packet_replacement_prefill_current.md",
        "title": "CA2 Packet Replacement Prefill",
    },
    "pxr": {
        "replacement_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "seed_csv": "runs/pxr_curated_candidate_source_seed_current.csv",
        "out_json": "runs/pxr_packet_replacement_prefill_current.json",
        "out_csv": "runs/pxr_packet_replacement_prefill_current.csv",
        "out_md": "runs/pxr_packet_replacement_prefill_current.md",
        "title": "PXR Packet Replacement Prefill",
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


def build_payload(replacement_rows: list[dict[str, str]], seed_rows: list[dict[str, str]], family: str) -> dict[str, Any]:
    seed_by_step = {str(row.get("packet_step", "")).strip(): row for row in seed_rows}
    prefill_rows: list[dict[str, Any]] = []
    matched = 0
    for row in replacement_rows:
        packet_step = str(row.get("packet_step", "")).strip()
        seed = seed_by_step.get(packet_step, {})
        if seed:
            matched += 1
        merged = dict(row)
        merged.update(
            {
                "candidate_ligand_name": str(seed.get("candidate_ligand_name", "")).strip(),
                "candidate_source_kind": str(seed.get("candidate_source_kind", "")).strip(),
                "candidate_reference_hint": str(seed.get("candidate_reference_hint", "")).strip(),
                "candidate_anchor_pdb_id": str(seed.get("target_anchor_pdb_id", "")).strip(),
                "candidate_anchor_native_path": str(seed.get("target_anchor_native_path", "")).strip(),
                "candidate_status": str(seed.get("candidate_status", "")).strip(),
                "candidate_manual_verification_required": str(seed.get("manual_verification_required", "")).strip(),
                "candidate_next_action": str(seed.get("next_action", "")).strip(),
                "prefill_status": "seed_attached" if seed else "seed_missing",
            }
        )
        prefill_rows.append(merged)
    summary = {
        "family": family,
        "replacement_row_count": len(replacement_rows),
        "seed_row_count": len(seed_rows),
        "matched_prefill_row_count": matched,
        "missing_seed_row_count": len(replacement_rows) - matched,
        "next_required_step": "Review the attached candidate columns, then manually move verified values into the replacement_* workbook fields.",
    }
    return {"summary": summary, "prefill_rows": prefill_rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"- replacement_row_count: `{summary['replacement_row_count']}`",
        f"- matched_prefill_row_count: `{summary['matched_prefill_row_count']}`",
        f"- missing_seed_row_count: `{summary['missing_seed_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Prefill Rows",
        "",
        "| packet_step | current_ligand_id | candidate_ligand_name | candidate_source_kind | prefill_status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["prefill_rows"]:
        lines.append(
            f"| {row.get('packet_step','')} | `{row.get('current_ligand_id','')}` | `{row.get('candidate_ligand_name','')}` | {row.get('candidate_source_kind','')} | {row.get('prefill_status','')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach curated candidate-source seed columns to a packet replacement workbook.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--replacement-csv")
    parser.add_argument("--seed-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    if not args.replacement_csv:
        args.replacement_csv = defaults["replacement_csv"]
    if not args.seed_csv:
        args.seed_csv = defaults["seed_csv"]
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
    replacement_rows = _read_csv(_resolve(args.replacement_csv))
    seed_rows = _read_csv(_resolve(args.seed_csv))
    payload = build_payload(replacement_rows, seed_rows, args.family)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["prefill_rows"])
    _write_markdown(out_md, payload, defaults["title"])


if __name__ == "__main__":
    main()
