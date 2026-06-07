#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PDB = "data/public_structures/nightly/2026-02-19-postfix-smoke-r6_ood_measured40/glut1_4pyp_pdb_4PYP.pdb"
DEFAULT_TARGET_CSV = "config/real_drug_targets_blind_glut1_4pyp_v1.csv"
DEFAULT_TARGET_META_CSV = "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv"
DEFAULT_OUT_JSON = "runs/glut1_target_packet_freeze_current.json"
DEFAULT_OUT_MD = "runs/glut1_target_packet_freeze_current.md"
DEFAULT_TARGET_ID = "GLUT1_TRANSPORT_BLIND"
DEFAULT_CHAIN_ID = "A"
DEFAULT_CENTROID_RESIDUES = "161,282,288,388,411"

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


def _parse_residue_list(value: str) -> list[int]:
    residues = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not residues:
        raise ValueError("centroid residue list is empty")
    return residues


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


def _extract_ca_centroid(
    pdb_path: Path,
    *,
    chain_id: str,
    residues: list[int],
) -> tuple[tuple[float, float, float], list[dict[str, Any]]]:
    wanted = set(residues)
    hits: dict[int, tuple[str, float, float, float]] = {}
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("ATOM"):
                continue
            if line[21].strip() != chain_id:
                continue
            if line[12:16].strip() != "CA":
                continue
            try:
                resid = int(line[22:26])
            except ValueError:
                continue
            if resid not in wanted:
                continue
            residue_name = line[17:20].strip().upper()
            hits[resid] = (
                residue_name,
                float(line[30:38]),
                float(line[38:46]),
                float(line[46:54]),
            )
    missing = [resid for resid in residues if resid not in hits]
    if missing:
        raise ValueError(f"missing CA coordinates for residues: {missing}")
    points = [(hits[resid][1], hits[resid][2], hits[resid][3]) for resid in residues]
    centroid = tuple(sum(point[i] for point in points) / len(points) for i in range(3))
    used_rows = [
        {
            "residue_number": resid,
            "residue_name": hits[resid][0],
            "ca_xyz": [round(hits[resid][1], 3), round(hits[resid][2], 3), round(hits[resid][3], 3)],
        }
        for resid in residues
    ]
    return (centroid[0], centroid[1], centroid[2]), used_rows


def _update_target_csv(target_csv: Path, *, target_id: str, pocket_xyz: tuple[float, float, float], residue_label: str) -> dict[str, Any]:
    fields, rows = _read_csv_rows(target_csv)
    updated = False
    for row in rows:
        if str(row.get("target", "")).strip() != target_id:
            continue
        row["pocket_x"] = f"{pocket_xyz[0]:.3f}"
        row["pocket_y"] = f"{pocket_xyz[1]:.3f}"
        row["pocket_z"] = f"{pocket_xyz[2]:.3f}"
        row["notes"] = (
            "GLUT1 4PYP blind target with central-cavity pocket centroid from "
            f"chain A CA residues {residue_label}; ligand packet remains gated separately."
        )
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
        row["target_family"] = "MEMBRANE_TRANSPORT_GLUCOSE"
        fingerprint = str(row.get("pocket_fingerprint", "")).strip()
        tokens = [token for token in fingerprint.split("|") if token]
        for token in ("glut_transporter", "central_cavity", "state_sensitive", "4pyp_seqres_chain_a", "residue_ca_centroid"):
            if token not in tokens:
                tokens.append(token)
        row["pocket_fingerprint"] = "|".join(tokens)
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
    residues = _parse_residue_list(args.centroid_residues)
    sequence, residue_count = _extract_chain_seqres(pdb_path, args.chain_id)
    pocket_xyz, used_residues = _extract_ca_centroid(pdb_path, chain_id=args.chain_id, residues=residues)
    residue_label = ",".join(str(residue) for residue in residues)
    target_update = _update_target_csv(target_csv, target_id=args.target_id, pocket_xyz=pocket_xyz, residue_label=residue_label)
    target_meta_update = _update_target_meta_csv(target_meta_csv, target_id=args.target_id, sequence=sequence)

    return {
        "target_id": args.target_id,
        "pdb_path": str(pdb_path),
        "chain_id": args.chain_id,
        "derived": {
            "seqres_residue_count": residue_count,
            "sequence_length": len(sequence),
            "sequence": sequence,
            "centroid_residue_numbers": residues,
            "centroid_residues_source": "GLUT1 central substrate/cavity residue set from local 4PYP numbering",
            "pocket_center_xyz": [round(pocket_xyz[0], 3), round(pocket_xyz[1], 3), round(pocket_xyz[2], 3)],
            "used_residue_ca_rows": used_residues,
        },
        "updated_files": {
            "target_csv": str(target_csv),
            "target_metadata_csv": str(target_meta_csv),
        },
        "update_summary": {
            "target_csv": target_update,
            "target_metadata_csv": target_meta_update,
        },
        "claim_boundary": (
            "This freezes a GLUT1 target-native pocket anchor from local 4PYP structure residues only. "
            "It does not make GLUT1 ligand rows, docking, affinity, or transporter scope claim-ready."
        ),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    derived = payload["derived"]
    lines = [
        "# GLUT1 Target Packet Freeze",
        "",
        f"- target: `{payload['target_id']}`",
        f"- pdb_path: `{payload['pdb_path']}`",
        f"- chain_id: `{payload['chain_id']}`",
        f"- sequence_length: `{derived['sequence_length']}`",
        f"- seqres_residue_count: `{derived['seqres_residue_count']}`",
        f"- centroid_residue_numbers: `{','.join(str(item) for item in derived['centroid_residue_numbers'])}`",
        f"- pocket_center_xyz: `{tuple(derived['pocket_center_xyz'])}`",
        "",
        "## Updated Files",
        "",
        f"- `target_csv`: `{payload['updated_files']['target_csv']}`",
        f"- `target_metadata_csv`: `{payload['updated_files']['target_metadata_csv']}`",
        "",
        "## Residue CA Inputs",
        "",
        "| residue | name | ca_xyz |",
        "| ---: | --- | --- |",
    ]
    for row in derived["used_residue_ca_rows"]:
        lines.append(f"| {row['residue_number']} | `{row['residue_name']}` | `{tuple(row['ca_xyz'])}` |")
    lines.extend(["", "## Claim Boundary", "", payload["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Freeze GLUT1 target packet values from local 4PYP structure.")
    ap.add_argument("--pdb-path", default=DEFAULT_PDB)
    ap.add_argument("--target-csv", default=DEFAULT_TARGET_CSV)
    ap.add_argument("--target-meta-csv", default=DEFAULT_TARGET_META_CSV)
    ap.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    ap.add_argument("--chain-id", default=DEFAULT_CHAIN_ID)
    ap.add_argument("--centroid-residues", default=DEFAULT_CENTROID_RESIDUES)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
