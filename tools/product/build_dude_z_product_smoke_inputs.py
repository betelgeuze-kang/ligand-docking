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


def _read_smi(path: Path, *, is_binder: int, max_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if 0 < int(max_rows) <= len(rows):
                break
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            rows.append(
                {
                    "ligand_id": _text(parts[1]),
                    "smiles": _text(parts[0]),
                    "is_binder": int(is_binder),
                    "reference_binding_kcal_mol": "-10.0" if int(is_binder) == 1 else "-1.0",
                    "source": "dude_z_ligand" if int(is_binder) == 1 else "dude_z_decoy",
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build_inputs(args: argparse.Namespace) -> dict[str, Any]:
    target = _text(args.target)
    dataset_dir = _resolve(args.dataset_dir)
    target_dir = dataset_dir / target
    ligand_rows = _read_smi(target_dir / "ligands.smi", is_binder=1, max_rows=int(args.max_actives))
    decoy_rows = _read_smi(target_dir / "decoys.smi", is_binder=0, max_rows=int(args.max_decoys))
    selected = [{**row, "target": target, "role": _text(args.role)} for row in [*ligand_rows, *decoy_rows]]

    native_path = _resolve(args.native_pdb_path)
    blockers: list[str] = []
    if not target_dir.exists():
        blockers.append("target_dataset_dir_missing")
    if not ligand_rows:
        blockers.append("ligands_smi_missing_or_empty")
    if not decoy_rows:
        blockers.append("decoys_smi_missing_or_empty")
    if not native_path.exists():
        blockers.append("native_pdb_path_missing")
    if len(selected) < int(args.min_ligands):
        blockers.append("selected_ligands_below_minimum")

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
    _write_csv(
        out_native,
        [
            {
                "target": target,
                "native_pdb_path": str(native_path),
                "pdb_id": _text(args.pdb_id),
                "pocket_x": _text(args.pocket_x),
                "pocket_y": _text(args.pocket_y),
                "pocket_z": _text(args.pocket_z),
                "notes": "DUD-E-Z AA2AR native structure path required for product-engine execution.",
            }
        ],
        native_fields,
    )

    status = "dude_z_product_smoke_inputs_ready" if not blockers else "blocked_dude_z_product_smoke_inputs"
    run_command = (
        "python3 tools/run_ligand_htvs_pipeline.py --run-scope smoke "
        f"--targets {target} --out-prefix runs/dude_z_decoy_smoke_product "
        f"--ligand-csv {out_ligands} --target-native-csv {out_native} "
        f"--eval-split-csv {out_split} --ranking-labels-csv {out_labels}"
    )
    summary = {
        "packet_type": "dude_z_product_smoke_inputs",
        "suite_id": "dude_z_decoy_smoke",
        "status": status,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "target": target,
        "dataset_dir": str(dataset_dir),
        "target_dataset_dir_present": target_dir.exists(),
        "native_pdb_path": str(native_path),
        "native_pdb_path_present": native_path.exists(),
        "selected_rows": len(selected),
        "selected_actives": len(ligand_rows),
        "selected_decoys": len(decoy_rows),
        "out_ligand_csv": str(out_ligands),
        "out_labels_csv": str(out_labels),
        "out_split_csv": str(out_split),
        "out_target_native_csv": str(out_native),
        "run_command": run_command,
        "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD" if "native_pdb_path_missing" in blockers else "",
        "external_state_mutated": False,
        "download_executed": False,
        "docking_results_emitted": False,
        "next_required_step": (
            "Run the product HTVS command, export benchmark results, then build provenance and scorecard."
            if not blockers
            else "Provide a local AA2AR native PDB path without downloading unless explicitly approved, then rebuild this preflight."
        ),
    }
    payload = {"summary": summary, "rows": selected[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# DUD-E-Z Product Smoke Inputs",
                "",
                f"- status: `{status}`",
                f"- target: `{target}`",
                f"- native_pdb_path_present: `{summary['native_pdb_path_present']}`",
                f"- selected_actives: `{summary['selected_actives']}`",
                f"- selected_decoys: `{summary['selected_decoys']}`",
                f"- blocker_count: `{summary['blocker_count']}`",
                "",
                "## Blockers",
                "",
                *(f"- `{blocker}`" for blocker in blockers),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DUD-E-Z product-engine smoke inputs from staged local data.")
    parser.add_argument("--target", default="AA2AR")
    parser.add_argument("--dataset-dir", default="data/public_benchmarks/dude_z_decoy_smoke")
    parser.add_argument("--native-pdb-path", default="data/native/aa2ar.pdb")
    parser.add_argument("--pdb-id", default="OPERATOR_FILL_AA2AR_PDB_ID")
    parser.add_argument("--pocket-x", default="0.0")
    parser.add_argument("--pocket-y", default="0.0")
    parser.add_argument("--pocket-z", default="0.0")
    parser.add_argument("--role", default="eval")
    parser.add_argument("--max-actives", type=int, default=32)
    parser.add_argument("--max-decoys", type=int, default=96)
    parser.add_argument("--min-ligands", type=int, default=2)
    parser.add_argument("--out-ligand-csv", default="runs/dude_z_decoy_smoke_product_ligands_current.csv")
    parser.add_argument("--out-labels-csv", default="runs/dude_z_decoy_smoke_product_labels_current.csv")
    parser.add_argument("--out-split-csv", default="runs/dude_z_decoy_smoke_product_split_current.csv")
    parser.add_argument("--out-target-native-csv", default="runs/dude_z_decoy_smoke_product_target_native_current.csv")
    parser.add_argument("--out-json", default="runs/dude_z_decoy_smoke_product_inputs_current.json")
    parser.add_argument("--out-md", default="runs/dude_z_decoy_smoke_product_inputs_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_inputs(parse_args(argv))


if __name__ == "__main__":
    main()
