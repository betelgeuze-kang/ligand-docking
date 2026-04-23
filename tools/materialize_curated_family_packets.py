#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "ca2": {
        "target": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
        "workbook_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "core_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
        "core_eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
        "core_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_v1.csv",
        "ood_reference_csv": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
        "ood_eval_split_csv": "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
        "ood_ligand_meta_csv": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
        "out_json": "runs/ca2_curated_packet_materialization_current.json",
        "out_csv": "runs/ca2_curated_packet_materialization_current.csv",
        "out_md": "runs/ca2_curated_packet_materialization_current.md",
    },
    "pxr": {
        "target": "PXR_NR1I2_BLIND",
        "workbook_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "core_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
        "core_eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
        "core_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
        "ood_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
        "ood_eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
        "ood_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
        "out_json": "runs/pxr_curated_packet_materialization_current.json",
        "out_csv": "runs/pxr_curated_packet_materialization_current.csv",
        "out_md": "runs/pxr_curated_packet_materialization_current.md",
    },
}

REFERENCE_FIELDS = ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"]
SPLIT_FIELDS = ["target", "ligand_id", "role"]
META_FIELDS = ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"]


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


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_ready_row(row: dict[str, Any]) -> bool:
    return _text(row.get("row_ready_for_apply")).lower() == "yes"


def _missing_fields(row: dict[str, Any]) -> list[str]:
    missing = _text(row.get("required_missing_fields"))
    return [item for item in missing.split(",") if item]


def _reference_row(row: dict[str, Any], target: str) -> dict[str, Any]:
    return {
        "target": target,
        "ligand_id": _text(row.get("replacement_ligand_id")),
        "reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
        "is_binder": _text(row.get("replacement_is_binder")),
        "source": _text(row.get("replacement_source")),
    }


def _split_row(row: dict[str, Any], target: str) -> dict[str, Any]:
    return {
        "target": target,
        "ligand_id": _text(row.get("replacement_ligand_id")),
        "role": _text(row.get("replacement_role")),
    }


def _meta_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ligand_id": _text(row.get("replacement_ligand_id")),
        "smiles": _text(row.get("replacement_smiles")),
        "molecular_weight": _text(row.get("replacement_molecular_weight")),
        "logp": _text(row.get("replacement_logp")),
        "h_donors": _text(row.get("replacement_h_donors")),
        "h_acceptors": _text(row.get("replacement_h_acceptors")),
        "rot_bonds": _text(row.get("replacement_rot_bonds")),
        "scaffold": _text(row.get("replacement_scaffold")),
    }


def build_payload(*, family: str, workbook_rows: list[dict[str, str]], target: str) -> dict[str, Any]:
    materialized_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    packet_outputs: dict[str, dict[str, list[dict[str, Any]]]] = {
        "core": {"reference": [], "split": [], "meta": []},
        "ood": {"reference": [], "split": [], "meta": []},
    }
    role_counter: dict[str, dict[str, int]] = {"core": {}, "ood": {}}

    for row in workbook_rows:
        packet = _text(row.get("packet"))
        packet_step = _text(row.get("packet_step"))
        replacement_ligand_id = _text(row.get("replacement_ligand_id"))
        output_row = {
            "packet": packet,
            "packet_step": packet_step,
            "replacement_ligand_id": replacement_ligand_id,
            "replacement_is_binder": _text(row.get("replacement_is_binder")),
            "replacement_role": _text(row.get("replacement_role")),
            "row_ready_for_apply": _text(row.get("row_ready_for_apply")),
            "required_missing_fields": _text(row.get("required_missing_fields")),
        }
        if packet not in packet_outputs or not _is_ready_row(row):
            unresolved_rows.append(output_row)
            continue

        ref_row = _reference_row(row, target)
        split_row = _split_row(row, target)
        meta_row = _meta_row(row)
        packet_outputs[packet]["reference"].append(ref_row)
        packet_outputs[packet]["split"].append(split_row)
        packet_outputs[packet]["meta"].append(meta_row)
        role = split_row["role"]
        role_counter[packet][role] = int(role_counter[packet].get(role, 0)) + 1
        materialized_rows.append(
            {
                **output_row,
                "reference_binding_kcal_mol": ref_row["reference_binding_kcal_mol"],
                "source": ref_row["source"],
            }
        )

    packet_summaries: list[dict[str, Any]] = []
    for packet in ("core", "ood"):
        ref_rows = packet_outputs[packet]["reference"]
        packet_summaries.append(
            {
                "packet": packet,
                "materialized_reference_rows": len(ref_rows),
                "materialized_split_rows": len(packet_outputs[packet]["split"]),
                "materialized_meta_rows": len(packet_outputs[packet]["meta"]),
                "role_counts": role_counter[packet],
                "binder_rows": sum(1 for row in ref_rows if _text(row.get("is_binder")) == "1"),
                "non_binder_rows": sum(1 for row in ref_rows if _text(row.get("is_binder")) == "0"),
            }
        )

    summary = {
        "family": family,
        "target": target,
        "workbook_row_count": len(workbook_rows),
        "materialized_row_count": len(materialized_rows),
        "unresolved_row_count": len(unresolved_rows),
        "core_ready": bool(packet_outputs["core"]["reference"]),
        "ood_ready": bool(packet_outputs["ood"]["reference"]),
        "next_required_step": (
            "Curate quantitative binding for unresolved rows, then rerun materialization to complete synchronized reference/split/meta packets."
            if unresolved_rows
            else "All workbook rows are synchronized into reference/split/meta packet files."
        ),
    }
    return {
        "summary": summary,
        "packet_summaries": packet_summaries,
        "materialized_rows": materialized_rows,
        "unresolved_rows": unresolved_rows,
        "packet_outputs": packet_outputs,
    }


def _write_markdown(path: Path, payload: dict[str, Any], defaults: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# {summary['family'].upper()} Curated Packet Materialization",
        "",
        f"- target: `{summary['target']}`",
        f"- workbook_row_count: `{summary['workbook_row_count']}`",
        f"- materialized_row_count: `{summary['materialized_row_count']}`",
        f"- unresolved_row_count: `{summary['unresolved_row_count']}`",
        "",
        "## Outputs",
        "",
        f"- core_reference_csv: `{defaults['core_reference_csv']}`",
        f"- core_eval_split_csv: `{defaults['core_eval_split_csv']}`",
        f"- core_ligand_meta_csv: `{defaults['core_ligand_meta_csv']}`",
        f"- ood_reference_csv: `{defaults['ood_reference_csv']}`",
        f"- ood_eval_split_csv: `{defaults['ood_eval_split_csv']}`",
        f"- ood_ligand_meta_csv: `{defaults['ood_ligand_meta_csv']}`",
        "",
        "## Packet Summary",
        "",
        "| packet | ref_rows | split_rows | meta_rows | binders | non_binders | roles |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["packet_summaries"]:
        role_text = ", ".join(f"{key}:{value}" for key, value in sorted((row.get("role_counts") or {}).items()))
        lines.append(
            f"| {row['packet']} | {row['materialized_reference_rows']} | {row['materialized_split_rows']} | "
            f"{row['materialized_meta_rows']} | {row['binder_rows']} | {row['non_binder_rows']} | {role_text} |"
        )
    lines.extend(
        [
            "",
            "## Unresolved Rows",
            "",
            "| packet_step | ligand | binder | role | missing_fields |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["unresolved_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_is_binder']} | "
            f"{row['replacement_role']} | `{row['required_missing_fields']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize synchronized family reference/eval/meta packet CSVs from curated replacement workbooks."
    )
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--workbook-csv")
    parser.add_argument("--core-reference-csv")
    parser.add_argument("--core-eval-split-csv")
    parser.add_argument("--core-ligand-meta-csv")
    parser.add_argument("--ood-reference-csv")
    parser.add_argument("--ood-eval-split-csv")
    parser.add_argument("--ood-ligand-meta-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in (
        "workbook_csv",
        "core_reference_csv",
        "core_eval_split_csv",
        "core_ligand_meta_csv",
        "ood_reference_csv",
        "ood_eval_split_csv",
        "ood_ligand_meta_csv",
        "out_json",
        "out_csv",
        "out_md",
    ):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    workbook_rows = _read_csv(_resolve(args.workbook_csv))
    payload = build_payload(family=args.family, workbook_rows=workbook_rows, target=defaults["target"])

    packet_outputs = payload["packet_outputs"]
    _write_csv(_resolve(args.core_reference_csv), packet_outputs["core"]["reference"], REFERENCE_FIELDS)
    _write_csv(_resolve(args.core_eval_split_csv), packet_outputs["core"]["split"], SPLIT_FIELDS)
    _write_csv(_resolve(args.core_ligand_meta_csv), packet_outputs["core"]["meta"], META_FIELDS)
    _write_csv(_resolve(args.ood_reference_csv), packet_outputs["ood"]["reference"], REFERENCE_FIELDS)
    _write_csv(_resolve(args.ood_eval_split_csv), packet_outputs["ood"]["split"], SPLIT_FIELDS)
    _write_csv(_resolve(args.ood_ligand_meta_csv), packet_outputs["ood"]["meta"], META_FIELDS)

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(
        out_csv,
        payload["materialized_rows"],
        [
            "packet",
            "packet_step",
            "replacement_ligand_id",
            "replacement_is_binder",
            "replacement_role",
            "row_ready_for_apply",
            "required_missing_fields",
            "reference_binding_kcal_mol",
            "source",
        ],
    )
    _write_markdown(out_md, payload, defaults)


if __name__ == "__main__":
    main()
