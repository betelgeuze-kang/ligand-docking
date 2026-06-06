#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PDB = "data/public_structures/2026-02-19-measured20-strict-r1/carbonic_anhydrase_2_zn_pdb_1CA2.pdb"
DEFAULT_TARGET_CSV = "config/real_drug_targets_blind_ca2_zn_v1.csv"
DEFAULT_TARGET_META_CSV = "config/ligand_target_metadata_blind_ca2_zn_v1.csv"
DEFAULT_OUT_JSON = "runs/ca2_target_packet_freeze_current.json"
DEFAULT_OUT_MD = "runs/ca2_target_packet_freeze_current.md"
DEFAULT_TARGET_ID = "CARBONIC_ANHYDRASE_2_ZN_BLIND"
DEFAULT_CHAIN_ID = "A"


AA3_TO_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "SEC": "U",
    "PYL": "O",
}


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _extract_chain_seqres(pdb_path: Path, chain_id: str) -> tuple[str, int]:
    residues: list[str] = []
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("SEQRES"):
                continue
            if line[11].strip() != chain_id:
                continue
            residues.extend(part.strip().upper() for part in line[19:].split() if part.strip())
    if not residues:
        raise ValueError(f"no SEQRES records found for chain {chain_id} in {pdb_path}")
    unknown = [res for res in residues if res not in AA3_TO_1]
    if unknown:
        raise ValueError(f"unsupported residues in SEQRES: {sorted(set(unknown))}")
    return "".join(AA3_TO_1[res] for res in residues), len(residues)


def _extract_zn_center(pdb_path: Path, chain_id: str) -> tuple[float, float, float, str]:
    hits: list[tuple[str, float, float, float]] = []
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("HETATM"):
                continue
            if line[17:20].strip().upper() != "ZN":
                continue
            if chain_id and line[21].strip() != chain_id:
                continue
            atom_name = line[12:16].strip()
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            hits.append((atom_name, x, y, z))
    if not hits:
        raise ValueError(f"no HETATM ZN found for chain {chain_id} in {pdb_path}")
    atom_name, x, y, z = hits[0]
    return x, y, z, atom_name


def _update_target_csv(target_csv: Path, *, target_id: str, pocket_xyz: tuple[float, float, float]) -> dict[str, Any]:
    fields, rows = _read_csv_rows(target_csv)
    updated = False
    for row in rows:
        if str(row.get("target", "")).strip() != target_id:
            continue
        row["pocket_x"] = f"{pocket_xyz[0]:.3f}"
        row["pocket_y"] = f"{pocket_xyz[1]:.3f}"
        row["pocket_z"] = f"{pocket_xyz[2]:.3f}"
        row["notes"] = "CA2 Zn blind target with catalytic ZN center from 1CA2 chain A."
        updated = True
        break
    if not updated:
        raise ValueError(f"target row {target_id} not found in {target_csv}")
    _write_csv_rows(target_csv, fields, rows)
    return {"updated": True, "row_count": len(rows)}


def _update_target_meta_csv(target_meta_csv: Path, *, target_id: str, sequence: str) -> dict[str, Any]:
    fields, rows = _read_csv_rows(target_meta_csv)
    updated = False
    for row in rows:
        if str(row.get("target", "")).strip() != target_id:
            continue
        row["sequence"] = sequence
        row["target_family"] = "METALLOENZYME"
        if not str(row.get("pocket_fingerprint", "")).strip():
            row["pocket_fingerprint"] = "zn_active_site|metal|hydrophilic_pocket"
        updated = True
        break
    if not updated:
        raise ValueError(f"target row {target_id} not found in {target_meta_csv}")
    _write_csv_rows(target_meta_csv, fields, rows)
    return {"updated": True, "row_count": len(rows)}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    pdb_path = _resolve(args.pdb_path)
    target_csv = _resolve(args.target_csv)
    target_meta_csv = _resolve(args.target_meta_csv)

    sequence, residue_count = _extract_chain_seqres(pdb_path, args.chain_id)
    x, y, z, atom_name = _extract_zn_center(pdb_path, args.chain_id)

    target_update = _update_target_csv(target_csv, target_id=args.target_id, pocket_xyz=(x, y, z))
    target_meta_update = _update_target_meta_csv(target_meta_csv, target_id=args.target_id, sequence=sequence)

    return {
        "target_id": args.target_id,
        "pdb_path": str(pdb_path),
        "chain_id": args.chain_id,
        "derived": {
            "seqres_residue_count": residue_count,
            "sequence_length": len(sequence),
            "sequence": sequence,
            "zn_atom_name": atom_name,
            "pocket_center_xyz": [round(x, 3), round(y, 3), round(z, 3)],
        },
        "updated_files": {
            "target_csv": str(target_csv),
            "target_metadata_csv": str(target_meta_csv),
        },
        "update_summary": {
            "target_csv": target_update,
            "target_metadata_csv": target_meta_update,
        },
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    derived = payload["derived"]
    lines = [
        "# CA2 Target Packet Freeze",
        "",
        f"- target: `{payload['target_id']}`",
        f"- pdb_path: `{payload['pdb_path']}`",
        f"- chain_id: `{payload['chain_id']}`",
        f"- sequence_length: `{derived['sequence_length']}`",
        f"- seqres_residue_count: `{derived['seqres_residue_count']}`",
        f"- catalytic_zn_atom: `{derived['zn_atom_name']}`",
        f"- pocket_center_xyz: `{tuple(derived['pocket_center_xyz'])}`",
        "",
        "## Updated Files",
        "",
        f"- `target_csv`: `{payload['updated_files']['target_csv']}`",
        f"- `target_metadata_csv`: `{payload['updated_files']['target_metadata_csv']}`",
        "",
        "## Notes",
        "",
        "- pocket center was seeded from the catalytic `ZN` atom in `1CA2` chain `A`",
        "- sequence was seeded from `SEQRES` chain `A` and converted to one-letter code",
        "- this reduces target-packet placeholders but does not make the CA2 packet claim-ready by itself",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Freeze CA2 target packet values from local 1CA2 structure.")
    ap.add_argument("--pdb-path", default=DEFAULT_PDB)
    ap.add_argument("--target-csv", default=DEFAULT_TARGET_CSV)
    ap.add_argument("--target-meta-csv", default=DEFAULT_TARGET_META_CSV)
    ap.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    ap.add_argument("--chain-id", default=DEFAULT_CHAIN_ID)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
