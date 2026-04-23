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
        "draft_csv": "runs/ca2_packet_replacement_draft_current.csv",
        "out_json": "runs/ca2_packet_replacement_verification_queue_current.json",
        "out_csv": "runs/ca2_packet_replacement_verification_queue_current.csv",
        "out_md": "runs/ca2_packet_replacement_verification_queue_current.md",
        "title": "CA2 Packet Replacement Verification Queue",
    },
    "pxr": {
        "draft_csv": "runs/pxr_packet_replacement_draft_current.csv",
        "out_json": "runs/pxr_packet_replacement_verification_queue_current.json",
        "out_csv": "runs/pxr_packet_replacement_verification_queue_current.csv",
        "out_md": "runs/pxr_packet_replacement_verification_queue_current.md",
        "title": "PXR Packet Replacement Verification Queue",
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


def _is_binder(row: dict[str, str]) -> bool:
    repl = str(row.get("replacement_is_binder", "")).strip()
    if repl:
        return repl == "1"
    current = str(row.get("current_binder_label", "")).strip().lower()
    return current == "binder"


def _priority_tuple(row: dict[str, str]) -> tuple[int, int, str]:
    packet = str(row.get("packet", "")).strip()
    packet_rank = {"core": 0, "ood": 1}.get(packet, 9)
    binder_rank = 0 if _is_binder(row) else 1
    return (packet_rank, binder_rank, str(row.get("packet_step", "")).strip())


def build_payload(rows: list[dict[str, str]], family: str) -> dict[str, Any]:
    sorted_rows = sorted(rows, key=_priority_tuple)
    queue_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(sorted_rows, start=1):
        replacement_ligand_id = str(row.get("draft_replacement_ligand_id", "")).strip() or str(row.get("replacement_ligand_id", "")).strip()
        replacement_source = str(row.get("draft_replacement_source", "")).strip() or str(row.get("replacement_source", "")).strip()
        queue_rows.append(
            {
                "priority_rank": idx,
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "target": str(row.get("target", "")).strip(),
                "replacement_ligand_id": replacement_ligand_id,
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "replacement_source": replacement_source,
                "draft_candidate_reference_hint": str(row.get("draft_candidate_reference_hint", "")).strip(),
                "draft_candidate_anchor_pdb_id": str(row.get("draft_candidate_anchor_pdb_id", "")).strip(),
                "draft_missing_claim_fields": str(row.get("draft_missing_claim_fields", "")).strip(),
                "draft_verification_status": str(row.get("draft_verification_status", "")).strip(),
                "draft_apply_block_reason": str(row.get("draft_apply_block_reason", "")).strip(),
                "next_verification_action": (
                    "Verify binding/provenance first for binder row."
                    if _is_binder(row)
                    else "Verify non-binder provenance and keep binding/scaffold evidence conservative."
                ),
            }
        )
    summary = {
        "family": family,
        "row_count": len(queue_rows),
        "binder_row_count": sum(1 for row in queue_rows if row["replacement_is_binder"] == "1"),
        "non_binder_row_count": sum(1 for row in queue_rows if row["replacement_is_binder"] == "0"),
        "next_required_step": "Start with core binders, then core non-binders, then OOD rows.",
    }
    return {"summary": summary, "queue_rows": queue_rows}


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
        "## Verification Queue",
        "",
        "| priority_rank | packet_step | replacement_ligand_id | binder | source | missing_claim_fields |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["queue_rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | {row['replacement_source']} | {row['draft_missing_claim_fields']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prioritize CA2/PXR draft replacement rows into a manual verification queue.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--draft-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    if not args.draft_csv:
        args.draft_csv = defaults["draft_csv"]
    if not args.out_json:
        args.out_json = defaults["out_json"]
    if not args.out_csv:
        args.out_csv = defaults["out_csv"]
    if not args.out_md:
        args.out_md = defaults["out_md"]
    return args


def main() -> None:
    args = parse_args()
    rows = _read_csv(_resolve(args.draft_csv))
    payload = build_payload(rows, args.family)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["queue_rows"])
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()
