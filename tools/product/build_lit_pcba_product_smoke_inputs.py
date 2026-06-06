#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): _text(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_smi(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            smiles, ligand_id = parts[0], parts[1]
            out.setdefault(_text(ligand_id), _text(smiles))
    return out


def _native_row(source_native_csv: Path, source_target: str, out_target: str) -> dict[str, Any]:
    rows = _read_csv(source_native_csv) if source_native_csv.exists() else []
    source = next((row for row in rows if _text(row.get("target")) == source_target), {})
    native = _text(source.get("native_pdb_path")) or "data/native/adrb2_gpcr_blind.pdb"
    return {
        "target": out_target,
        "native_pdb_path": native,
        "pdb_id": _text(source.get("pdb_id")) or "2RH1",
        "pocket_x": _text(source.get("pocket_x")) or "-29.51954545454545",
        "pocket_y": _text(source.get("pocket_y")) or "9.234363636363637",
        "pocket_z": _text(source.get("pocket_z")) or "6.944045454545452",
        "notes": f"LIT-PCBA {out_target} smoke mapped to local product native structure {source_target}",
    }


def build_inputs(args: argparse.Namespace) -> dict[str, Any]:
    target = _text(args.target)
    labels_path = _resolve(args.labels_csv)
    lit_dir = _resolve(args.lit_pcba_dir)
    smi_paths = [
        lit_dir / "Gold" / target / "ligands_T_std.smi",
        lit_dir / "Gold" / target / "ligands_V_std.smi",
    ]
    smiles_by_id: dict[str, str] = {}
    for path in smi_paths:
        smiles_by_id.update(_read_smi(path))

    labels = [row for row in _read_csv(labels_path) if _text(row.get("target")) == target]
    merged: list[dict[str, Any]] = []
    missing_smiles = 0
    for row in labels:
        ligand_id = _text(row.get("ligand_id"))
        smiles = smiles_by_id.get(ligand_id, "")
        if not ligand_id or not smiles:
            missing_smiles += 1
            continue
        is_binder = "1" if _text(row.get("is_binder")).lower() in {"1", "true", "yes"} else "0"
        merged.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "smiles": smiles,
                "is_binder": is_binder,
                "reference_binding_kcal_mol": "-10.0" if is_binder == "1" else "-1.0",
                "role": _text(args.role),
                "source": "lit_pcba_public_smoke",
            }
        )

    merged.sort(key=lambda row: (0 if row["is_binder"] == "1" else 1, row["ligand_id"]))
    max_ligands = int(max(1, int(args.max_ligands)))
    selected = merged[:max_ligands]
    if int(args.min_binders) > 0:
        binder_count = sum(1 for row in selected if row["is_binder"] == "1")
        if binder_count < int(args.min_binders):
            raise ValueError(f"selected binder count {binder_count} below required {args.min_binders}")

    out_ligands = _resolve(args.out_ligand_csv)
    out_labels = _resolve(args.out_labels_csv)
    out_split = _resolve(args.out_split_csv)
    out_native = _resolve(args.out_target_native_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)

    ligand_fields = ["target", "ligand_id", "smiles", "is_binder", "reference_binding_kcal_mol", "source"]
    label_fields = ["target", "ligand_id", "is_binder", "reference_binding_kcal_mol"]
    split_fields = ["target", "ligand_id", "role"]
    native_fields = ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"]
    _write_csv(out_ligands, selected, ligand_fields)
    _write_csv(out_labels, selected, label_fields)
    _write_csv(out_split, selected, split_fields)
    native_rows = [_native_row(_resolve(args.source_target_native_csv), _text(args.source_native_target), target)]
    _write_csv(out_native, native_rows, native_fields)

    summary = {
        "packet_type": "lit_pcba_product_smoke_inputs",
        "status": "lit_pcba_product_smoke_inputs_ready",
        "target": target,
        "selected_rows": len(selected),
        "selected_binders": sum(1 for row in selected if row["is_binder"] == "1"),
        "source_label_rows": len(labels),
        "smiles_rows": len(smiles_by_id),
        "missing_smiles_rows": missing_smiles,
        "out_ligand_csv": str(out_ligands),
        "out_labels_csv": str(out_labels),
        "out_split_csv": str(out_split),
        "out_target_native_csv": str(out_native),
        "source_engine": "betelgeuze_ligand_htvs",
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "next_required_step": "Run run_ligand_htvs_pipeline.py with these inputs, then export stage scores to LIT-PCBA scorecard format.",
    }
    payload = {"summary": summary, "rows": selected[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# LIT-PCBA Product Smoke Inputs",
                "",
                f"- status: `{summary['status']}`",
                f"- target: `{target}`",
                f"- selected_rows: `{summary['selected_rows']}`",
                f"- selected_binders: `{summary['selected_binders']}`",
                f"- out_ligand_csv: `{out_ligands}`",
                f"- out_labels_csv: `{out_labels}`",
                f"- out_split_csv: `{out_split}`",
                f"- out_target_native_csv: `{out_native}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LIT-PCBA product-engine smoke inputs from staged public data.")
    parser.add_argument("--target", default="ADRB2")
    parser.add_argument("--role", default="eval")
    parser.add_argument("--max-ligands", type=int, default=240)
    parser.add_argument("--min-binders", type=int, default=1)
    parser.add_argument("--lit-pcba-dir", default="data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released")
    parser.add_argument("--labels-csv", default="data/public_benchmarks/lit_pcba/lit_pcba_source_labels.csv")
    parser.add_argument("--source-target-native-csv", default="config/real_drug_targets_blind_gpcr_adrb2_v1.csv")
    parser.add_argument("--source-native-target", default="ADRB2_GPCR_BLIND")
    parser.add_argument("--out-ligand-csv", default="runs/lit_pcba_adrb2_product_ligands_current.csv")
    parser.add_argument("--out-labels-csv", default="runs/lit_pcba_labels_current.csv")
    parser.add_argument("--out-split-csv", default="runs/lit_pcba_adrb2_product_split_current.csv")
    parser.add_argument("--out-target-native-csv", default="runs/lit_pcba_adrb2_product_target_native_current.csv")
    parser.add_argument("--out-json", default="runs/lit_pcba_product_smoke_inputs_current.json")
    parser.add_argument("--out-md", default="runs/lit_pcba_product_smoke_inputs_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_inputs(parse_args(argv))


if __name__ == "__main__":
    main()
