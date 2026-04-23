#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_JSON = "runs/glut1_packet_fill_queue_current.json"
PRIMARY_TARGET = "GLUT1_TRANSPORT_BLIND"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _required_missing_fields(row: dict[str, Any]) -> str:
    required = [
        ("replacement_ligand_id", row["replacement_ligand_id"]),
        ("replacement_reference_binding_kcal_mol", row["replacement_reference_binding_kcal_mol"]),
        ("replacement_source", row["replacement_source"]),
        ("replacement_smiles", row["replacement_smiles"]),
        ("replacement_scaffold", row["replacement_scaffold"]),
        ("replacement_role", row["replacement_role"]),
    ]
    missing = [name for name, value in required if not str(value or "").strip()]
    return ",".join(missing)


def _seed_row(queue_row: dict[str, Any]) -> dict[str, Any]:
    binder_flag = "1" if queue_row.get("binder_label") == "binder" else "0"
    row = {
        "packet": queue_row["packet"],
        "packet_step": queue_row["packet_step"],
        "target": PRIMARY_TARGET,
        "current_ligand_id": queue_row["current_ligand_id"],
        "current_binder_label": queue_row.get("binder_label", ""),
        "current_role": queue_row.get("current_role", ""),
        "current_reference_binding_kcal_mol": queue_row.get("current_reference_binding_kcal_mol", ""),
        "current_source": queue_row.get("current_source", ""),
        "current_smiles": queue_row.get("current_smiles", ""),
        "current_scaffold": queue_row.get("current_scaffold", ""),
        "placeholder_sources": queue_row.get("placeholder_sources", ""),
        "replacement_ligand_id": "",
        "replacement_reference_binding_kcal_mol": "",
        "replacement_is_binder": binder_flag,
        "replacement_source": "",
        "replacement_role": queue_row.get("replacement_role") or queue_row.get("current_role", ""),
        "replacement_smiles": "",
        "replacement_molecular_weight": "",
        "replacement_logp": "",
        "replacement_h_donors": "",
        "replacement_h_acceptors": "",
        "replacement_rot_bonds": "",
        "replacement_scaffold": "",
        "apply_reference_row": "yes",
        "apply_split_row": "yes",
        "apply_meta_row": "yes",
        "row_ready_for_apply": "no",
        "notes": queue_row.get(
            "notes",
            "Replace placeholder GLUT1 packet slot with a synchronized reference/split/meta edit.",
        ),
    }
    row["required_missing_fields"] = _required_missing_fields(row)
    return row


def build_payload(queue_payload: dict[str, Any]) -> dict[str, Any]:
    queue_rows = list(queue_payload.get("queue_rows", []))
    workbook_rows = [_seed_row(row) for row in queue_rows]
    return {
        "target": PRIMARY_TARGET,
        "summary": {
            "queue_row_count": len(queue_rows),
            "workbook_row_count": len(workbook_rows),
            "ready_seed_row_count": 0,
            "packets_with_workbook_rows": 1 if workbook_rows else 0,
            "next_required_step": "Fill replacement columns one GLUT1 packet_step at a time, then promote accepted rows as a synchronized reference/split/meta triple edit.",
        },
        "packet_summaries": [
            {
                "packet": "core",
                "row_count": len(workbook_rows),
                "ready_seed_rows": 0,
            }
        ],
        "workbook_rows": workbook_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GLUT1 Packet Replacement Workbook",
        "",
        f"- target: `{payload['target']}`",
        f"- workbook_row_count: `{payload['summary']['workbook_row_count']}`",
        f"- ready_seed_row_count: `{payload['summary']['ready_seed_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Workbook",
        "",
        "| packet_step | current_ligand_id | replacement_ligand_id | replacement_is_binder | replacement_role | required_missing_fields |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["workbook_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['current_ligand_id']}` | {row['replacement_ligand_id']} | {row['replacement_is_binder']} | {row['replacement_role']} | {row['required_missing_fields']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1 packet replacement workbook from the current fill queue.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--out-json", default="runs/glut1_packet_replacement_workbook_current.json")
    parser.add_argument("--out-csv", default="runs/glut1_packet_replacement_workbook_current.csv")
    parser.add_argument("--out-md", default="runs/glut1_packet_replacement_workbook_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue_payload = _load_json(_resolve(args.queue_json))
    payload = build_payload(queue_payload)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["workbook_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
