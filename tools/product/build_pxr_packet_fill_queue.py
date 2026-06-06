#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PRIMARY_TARGET = "PXR_NR1I2_BLIND"
PACKETS = {
    "core": {
        "reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        "ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
    },
    "ood": {
        "reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        "ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
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


def _placeholder(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and ("placeholder" in text or "template_" in text or "todo" in text)


def _packet_rows(packet_name: str) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    ref_rows = [
        row for row in _read_csv(_resolve(PACKETS[packet_name]["reference_csv"]))
        if row.get("target", "").strip() == PRIMARY_TARGET
    ]
    split_rows = [
        row for row in _read_csv(_resolve(PACKETS[packet_name]["eval_split_csv"]))
        if row.get("target", "").strip() == PRIMARY_TARGET
    ]
    meta_rows = _read_csv(_resolve(PACKETS[packet_name]["ligand_meta_csv"]))
    return ref_rows, split_rows, meta_rows


def _index_by_ligand_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        ligand_id = row.get("ligand_id", "").strip()
        if ligand_id:
            out[ligand_id] = row
    return out


def _queue_row(packet_name: str, ligand_id: str, ref: dict[str, str], split: dict[str, str], meta: dict[str, str]) -> dict[str, Any]:
    binder_flag = str(ref.get("is_binder", "")).strip()
    binder_label = "binder" if binder_flag == "1" else "non_binder"
    role = str(split.get("role", "")).strip()
    placeholder_sources = []
    if any(_placeholder(v) for v in ref.values()):
        placeholder_sources.append("reference")
    if any(_placeholder(v) for v in split.values()):
        placeholder_sources.append("split")
    if any(_placeholder(v) for v in meta.values()):
        placeholder_sources.append("meta")
    slot_index = ligand_id.rsplit("_", 1)[-1] if "_" in ligand_id else ""
    role_token_map = {
        "fit": "fit",
        "id_eval": "id",
        "near_ood_eval": "near",
        "far_ood_eval": "eval",
        "ood_eval": "ood",
    }
    role_token = role_token_map.get(role, role or "role")
    packet_step = f"{packet_name}_{role_token}_{binder_label}_{slot_index}".strip("_")
    return {
        "packet": packet_name,
        "packet_step": packet_step,
        "current_ligand_id": ligand_id,
        "binder_label": binder_label,
        "current_role": role,
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
        "replacement_role": role,
        "curation_status": "pending_replacement",
        "notes": f"Replace placeholder {packet_name} {binder_label} slot {slot_index} with a curated PXR ligand row.",
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
    queue_rows: list[dict[str, Any]] = []
    packet_summaries: list[dict[str, Any]] = []
    for packet_name in ("core", "ood"):
        ref_rows, split_rows, meta_rows = _packet_rows(packet_name)
        ref_by_id = _index_by_ligand_id(ref_rows)
        split_by_id = _index_by_ligand_id(split_rows)
        meta_by_id = _index_by_ligand_id(meta_rows)
        packet_queue = []
        for ligand_id, ref_row in sorted(ref_by_id.items()):
            split_row = split_by_id.get(ligand_id, {})
            meta_row = meta_by_id.get(ligand_id, {})
            if not _needs_queue_row(ligand_id, ref_row, split_row, meta_row):
                continue
            row = _queue_row(packet_name, ligand_id, ref_row, split_row, meta_row)
            queue_rows.append(row)
            packet_queue.append(row)
        packet_summaries.append(
            {
                "packet": packet_name,
                "queue_count": len(packet_queue),
                "binder_slots": sum(1 for row in packet_queue if row["binder_label"] == "binder"),
                "non_binder_slots": sum(1 for row in packet_queue if row["binder_label"] == "non_binder"),
                "role_counter": dict(Counter(row["current_role"] for row in packet_queue)),
            }
        )
    return {
        "target": PRIMARY_TARGET,
        "summary": {
            "queue_count": len(queue_rows),
            "packet_count": len(packet_summaries),
            "packets_with_queue": sum(1 for row in packet_summaries if row["queue_count"] > 0),
            "next_required_step": "Replace every placeholder slot in the queue with a curated PXR ligand_id/provenance/meta row before attempting a runnable packet.",
        },
        "packet_summaries": packet_summaries,
        "queue_rows": queue_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PXR Packet Fill Queue",
        "",
        f"- target: `{payload['target']}`",
        f"- queue_count: `{payload['summary']['queue_count']}`",
        f"- packets_with_queue: `{payload['summary']['packets_with_queue']}`",
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
        lines.append(
            f"| {row['packet']} | {row['queue_count']} | {row['binder_slots']} | {row['non_binder_slots']} | {roles} |"
        )
    lines.extend(
        [
            "",
            "## Fill Queue",
            "",
            "| packet | packet_step | current_ligand_id | binder_label | current_role | placeholder_sources | replacement_ligand_id | replacement_role | curation_status |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["queue_rows"]:
        lines.append(
            f"| {row['packet']} | {row['packet_step']} | `{row['current_ligand_id']}` | {row['binder_label']} | {row['current_role']} | {row['placeholder_sources']} | {row['replacement_ligand_id']} | {row['replacement_role']} | {row['curation_status']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a PXR placeholder packet fill queue.")
    parser.add_argument("--out-json", default="runs/pxr_packet_fill_queue_current.json")
    parser.add_argument("--out-csv", default="runs/pxr_packet_fill_queue_current.csv")
    parser.add_argument("--out-md", default="runs/pxr_packet_fill_queue_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["queue_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
