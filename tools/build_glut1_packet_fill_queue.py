#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_TARGET = "GLUT1_TRANSPORT_BLIND"
PACKET_FILES = {
    "reference_csv": "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
    "eval_split_csv": "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
    "ligand_meta_csv": "config/ligand_meta_blind_glut1_4pyp_v1.csv",
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


def _placeholder(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and ("placeholder" in text or "template_" in text or "todo" in text)


def _index_by_ligand_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        ligand_id = row.get("ligand_id", "").strip()
        if ligand_id:
            out[ligand_id] = row
    return out


def _queue_row(ligand_id: str, ref: dict[str, str], split: dict[str, str], meta: dict[str, str]) -> dict[str, Any]:
    binder_flag = str(ref.get("is_binder", "")).strip()
    binder_label = "binder" if binder_flag == "1" else "non_binder"
    slot_index = ligand_id.rsplit("_", 1)[-1] if "_" in ligand_id else ""
    placeholder_sources = []
    if any(_placeholder(v) for v in ref.values()):
        placeholder_sources.append("reference")
    if any(_placeholder(v) for v in split.values()):
        placeholder_sources.append("split")
    if any(_placeholder(v) for v in meta.values()):
        placeholder_sources.append("meta")
    return {
        "packet": "core",
        "packet_step": f"core_{binder_label}_{slot_index}".strip("_"),
        "current_ligand_id": ligand_id,
        "binder_label": binder_label,
        "current_role": str(split.get("role", "")).strip(),
        "current_reference_binding_kcal_mol": ref.get("reference_binding_kcal_mol", ""),
        "current_source": ref.get("source", ""),
        "current_smiles": meta.get("smiles", ""),
        "current_scaffold": meta.get("scaffold", ""),
        "placeholder_sources": ",".join(placeholder_sources),
        "replacement_ligand_id": "",
        "replacement_reference_binding_kcal_mol": "",
        "replacement_source": "",
        "replacement_smiles": "",
        "replacement_scaffold": "",
        "replacement_role": str(split.get("role", "")).strip(),
        "curation_status": "pending_replacement",
        "notes": f"Replace placeholder GLUT1 {binder_label} slot {slot_index} with a curated transporter ligand row before runnable promotion.",
    }


def _needs_queue_row(ligand_id: str, ref: dict[str, str], split: dict[str, str], meta: dict[str, str]) -> bool:
    if _placeholder(ligand_id):
        return True
    if any(_placeholder(v) for v in ref.values()):
        return True
    if any(_placeholder(v) for v in split.values()):
        return True
    if any(_placeholder(v) for v in meta.values()):
        return True
    return False


def build_payload() -> dict[str, Any]:
    ref_rows = [row for row in _read_csv(_resolve(PACKET_FILES["reference_csv"])) if row.get("target", "").strip() == PRIMARY_TARGET]
    split_rows = [row for row in _read_csv(_resolve(PACKET_FILES["eval_split_csv"])) if row.get("target", "").strip() == PRIMARY_TARGET]
    meta_rows = _read_csv(_resolve(PACKET_FILES["ligand_meta_csv"]))
    ref_by_id = _index_by_ligand_id(ref_rows)
    split_by_id = _index_by_ligand_id(split_rows)
    meta_by_id = _index_by_ligand_id(meta_rows)

    queue_rows: list[dict[str, Any]] = []
    for ligand_id, ref_row in sorted(ref_by_id.items()):
        split_row = split_by_id.get(ligand_id, {})
        meta_row = meta_by_id.get(ligand_id, {})
        if not _needs_queue_row(ligand_id, ref_row, split_row, meta_row):
            continue
        queue_rows.append(_queue_row(ligand_id, ref_row, split_row, meta_row))

    role_counter = Counter(row["current_role"] for row in queue_rows)
    return {
        "target": PRIMARY_TARGET,
        "summary": {
            "queue_count": len(queue_rows),
            "binder_slots": sum(1 for row in queue_rows if row["binder_label"] == "binder"),
            "non_binder_slots": sum(1 for row in queue_rows if row["binder_label"] == "non_binder"),
            "next_required_step": "Replace every placeholder GLUT1 slot with a curated transporter ligand_id/provenance/meta row before any runnable core or smoke packet attempt.",
        },
        "packet_summaries": [
            {
                "packet": "core",
                "queue_count": len(queue_rows),
                "binder_slots": sum(1 for row in queue_rows if row["binder_label"] == "binder"),
                "non_binder_slots": sum(1 for row in queue_rows if row["binder_label"] == "non_binder"),
                "role_counter": dict(role_counter),
            }
        ],
        "queue_rows": queue_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GLUT1 Packet Fill Queue",
        "",
        f"- target: `{payload['target']}`",
        f"- queue_count: `{payload['summary']['queue_count']}`",
        f"- binder_slots: `{payload['summary']['binder_slots']}`",
        f"- non_binder_slots: `{payload['summary']['non_binder_slots']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Packet Summary",
        "",
        "| packet | queue_count | binder_slots | non_binder_slots | roles |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["packet_summaries"]:
        roles = ", ".join(f"{k}:{v}" for k, v in sorted(row["role_counter"].items()))
        lines.append(f"| {row['packet']} | {row['queue_count']} | {row['binder_slots']} | {row['non_binder_slots']} | {roles} |")
    lines.extend(
        [
            "",
            "## Fill Queue",
            "",
            "| packet_step | current_ligand_id | binder_label | current_role | placeholder_sources | replacement_ligand_id | replacement_role | curation_status |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["queue_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['current_ligand_id']}` | {row['binder_label']} | {row['current_role']} | {row['placeholder_sources']} | {row['replacement_ligand_id']} | {row['replacement_role']} | {row['curation_status']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1 placeholder packet fill queue.")
    parser.add_argument("--out-json", default="runs/glut1_packet_fill_queue_current.json")
    parser.add_argument("--out-csv", default="runs/glut1_packet_fill_queue_current.csv")
    parser.add_argument("--out-md", default="runs/glut1_packet_fill_queue_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["queue_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
