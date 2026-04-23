#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = "CARBONIC_ANHYDRASE_2_ZN_BLIND"


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
    return bool(text) and "placeholder" in text


def _classify_packet_row(ref_row: dict[str, str] | None, split_row: dict[str, str] | None, meta_row: dict[str, str] | None) -> dict[str, Any]:
    ligand_id = ""
    if ref_row:
        ligand_id = ref_row.get("ligand_id", "")
    elif split_row:
        ligand_id = split_row.get("ligand_id", "")
    elif meta_row:
        ligand_id = meta_row.get("ligand_id", "")

    ligand_id_placeholder = _placeholder(ligand_id)
    provenance_ready = bool(ref_row) and not _placeholder((ref_row or {}).get("source", ""))
    split_ready = bool(split_row) and not _placeholder((split_row or {}).get("role", "")) and bool((split_row or {}).get("role", "").strip())
    meta_ready = bool(meta_row) and not any(
        _placeholder((meta_row or {}).get(key, ""))
        for key in ("smiles", "scaffold")
    )
    binder_label = ""
    if ref_row:
        binder_label = "binder" if str(ref_row.get("is_binder", "")).strip() == "1" else "non_binder"

    blockers: list[str] = []
    if ligand_id_placeholder:
        blockers.append("ligand_id_placeholder")
    if not provenance_ready:
        blockers.append("provenance_pending")
    if not split_ready:
        blockers.append("split_pending")
    if not meta_ready:
        blockers.append("meta_pending")

    ready = not blockers
    return {
        "ligand_id": ligand_id,
        "binder_label": binder_label,
        "reference_binding_kcal_mol": (ref_row or {}).get("reference_binding_kcal_mol", ""),
        "role": (split_row or {}).get("role", ""),
        "smiles": (meta_row or {}).get("smiles", ""),
        "scaffold": (meta_row or {}).get("scaffold", ""),
        "ligand_id_placeholder": ligand_id_placeholder,
        "provenance_ready": provenance_ready,
        "split_ready": split_ready,
        "meta_ready": meta_ready,
        "ready_for_packet": ready,
        "blockers": ", ".join(blockers) if blockers else "ready",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    reference_rows = [row for row in _read_csv(_resolve(args.reference_csv)) if row.get("target", "").strip() == TARGET]
    split_rows = [row for row in _read_csv(_resolve(args.eval_split_csv)) if row.get("target", "").strip() == TARGET]
    meta_rows = _read_csv(_resolve(args.ligand_meta_csv))

    ref_by_id = {row.get("ligand_id", "").strip(): row for row in reference_rows}
    split_by_id = {row.get("ligand_id", "").strip(): row for row in split_rows}
    meta_by_id = {row.get("ligand_id", "").strip(): row for row in meta_rows}

    ligand_ids = sorted({lig for lig in [*ref_by_id.keys(), *split_by_id.keys()] if lig})
    ledger_rows: list[dict[str, Any]] = []
    for ligand_id in ligand_ids:
        ledger_rows.append(_classify_packet_row(ref_by_id.get(ligand_id), split_by_id.get(ligand_id), meta_by_id.get(ligand_id)))

    ready_count = sum(1 for row in ledger_rows if row["ready_for_packet"])
    placeholder_count = sum(1 for row in ledger_rows if row["ligand_id_placeholder"])
    binder_count = sum(1 for row in ledger_rows if row["binder_label"] == "binder")
    non_binder_count = sum(1 for row in ledger_rows if row["binder_label"] == "non_binder")
    return {
        "target": TARGET,
        "reference_csv": args.reference_csv,
        "eval_split_csv": args.eval_split_csv,
        "ligand_meta_csv": args.ligand_meta_csv,
        "summary": {
            "ligand_count": len(ledger_rows),
            "binder_count": binder_count,
            "non_binder_count": non_binder_count,
            "ready_for_packet_count": ready_count,
            "blocked_count": len(ledger_rows) - ready_count,
            "placeholder_ligand_id_count": placeholder_count,
            "next_required_step": "Freeze a non-placeholder CA2 core ligand_id ledger, then fill provenance/meta/split fields consistently across the three packet tables.",
        },
        "ledger_rows": ledger_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CA2 Core Ligand Ledger",
        "",
        f"- target: `{payload['target']}`",
        f"- ligand_count: `{payload['summary']['ligand_count']}`",
        f"- ready_for_packet_count: `{payload['summary']['ready_for_packet_count']}`",
        f"- blocked_count: `{payload['summary']['blocked_count']}`",
        f"- placeholder_ligand_id_count: `{payload['summary']['placeholder_ligand_id_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Ledger",
        "",
        "| ligand_id | binder_label | role | provenance_ready | split_ready | meta_ready | ready_for_packet | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["ledger_rows"]:
        lines.append(
            "| {ligand_id} | {binder_label} | {role} | {provenance_ready} | {split_ready} | {meta_ready} | {ready_for_packet} | {blockers} |".format(**row)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 core ligand ledger from reference/split/meta packets.")
    parser.add_argument("--reference-csv", default="config/ligand_binding_reference_blind_ca2_zn_v1.csv")
    parser.add_argument("--eval-split-csv", default="config/ligand_eval_splits_blind_ca2_zn_v1.csv")
    parser.add_argument("--ligand-meta-csv", default="config/ligand_meta_blind_ca2_zn_v1.csv")
    parser.add_argument("--out-json", default="runs/ca2_core_ligand_ledger_current.json")
    parser.add_argument("--out-csv", default="runs/ca2_core_ligand_ledger_current.csv")
    parser.add_argument("--out-md", default="runs/ca2_core_ligand_ledger_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["ledger_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
