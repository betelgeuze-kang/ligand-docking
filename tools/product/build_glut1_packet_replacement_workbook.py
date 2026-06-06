#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE_JSON = "runs/glut1_packet_fill_queue_current.json"
DEFAULT_CLAIM_SAFE_KCAL_JSON = "runs/glut1_claim_safe_binding_kcal_packet_current.json"
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


def _load_json_if_present(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    return _load_json(path)


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


def _claim_safe_rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
        and str(row.get("row_ready_for_apply", "")).strip().lower() == "yes"
    }


def _seed_row(queue_row: dict[str, Any], claim_safe_by_step: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    claim_safe = (claim_safe_by_step or {}).get(str(queue_row.get("packet_step", "")).strip(), {})
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
        "replacement_ligand_id": claim_safe.get("replacement_ligand_id", ""),
        "replacement_reference_binding_kcal_mol": claim_safe.get("replacement_reference_binding_kcal_mol", ""),
        "replacement_is_binder": claim_safe.get("replacement_is_binder", binder_flag),
        "replacement_source": claim_safe.get("replacement_source", ""),
        "replacement_role": claim_safe.get("replacement_role") or queue_row.get("replacement_role") or queue_row.get("current_role", ""),
        "replacement_smiles": claim_safe.get("replacement_smiles", ""),
        "replacement_molecular_weight": claim_safe.get("replacement_molecular_weight", ""),
        "replacement_logp": claim_safe.get("replacement_logp", ""),
        "replacement_h_donors": claim_safe.get("replacement_h_donors", ""),
        "replacement_h_acceptors": claim_safe.get("replacement_h_acceptors", ""),
        "replacement_rot_bonds": claim_safe.get("replacement_rot_bonds", ""),
        "replacement_scaffold": claim_safe.get("replacement_scaffold", ""),
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
    if not row["required_missing_fields"]:
        row["row_ready_for_apply"] = "yes"
        row["notes"] = (
            f"{row['notes']} Claim-safe binding/kcal row filled from "
            "runs/glut1_claim_safe_binding_kcal_packet_current.json."
        ).strip()
    return row


def build_payload(queue_payload: dict[str, Any], claim_safe_kcal_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    queue_rows = list(queue_payload.get("queue_rows", []))
    claim_safe_by_step = _claim_safe_rows_by_step(claim_safe_kcal_payload or {})
    workbook_rows = [_seed_row(row, claim_safe_by_step) for row in queue_rows]
    ready_seed_row_count = sum(1 for row in workbook_rows if row["row_ready_for_apply"] == "yes")
    return {
        "target": PRIMARY_TARGET,
        "summary": {
            "queue_row_count": len(queue_rows),
            "workbook_row_count": len(workbook_rows),
            "ready_seed_row_count": ready_seed_row_count,
            "claim_safe_prefill_row_count": len(claim_safe_by_step),
            "packets_with_workbook_rows": 1 if workbook_rows else 0,
            "next_required_step": (
                "Promote the ready claim-safe GLUT1 binder row through transporter gates, then fill remaining GLUT1 packet steps."
                if ready_seed_row_count
                else "Fill replacement columns one GLUT1 packet_step at a time, then promote accepted rows as a synchronized reference/split/meta triple edit."
            ),
        },
        "packet_summaries": [
            {
                "packet": "core",
                "row_count": len(workbook_rows),
                "ready_seed_rows": ready_seed_row_count,
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
    parser.add_argument("--claim-safe-kcal-json", default=DEFAULT_CLAIM_SAFE_KCAL_JSON)
    parser.add_argument("--out-json", default="runs/glut1_packet_replacement_workbook_current.json")
    parser.add_argument("--out-csv", default="runs/glut1_packet_replacement_workbook_current.csv")
    parser.add_argument("--out-md", default="runs/glut1_packet_replacement_workbook_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue_payload = _load_json(_resolve(args.queue_json))
    payload = build_payload(queue_payload, _load_json_if_present(args.claim_safe_kcal_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["workbook_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
