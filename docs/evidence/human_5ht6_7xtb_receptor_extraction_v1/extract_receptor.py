"""Export only observed 7XTB entity-5 receptor atom sites with a gap break.

No missing atom, residue, hydrogen, cap, charge, or force-field parameter is made.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict


HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = "e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7"
SOURCE_BYTES = 900097
PDB_NAME = "receptor-E-observed.pdb"
MAP_NAME = "source-atom-map.csv"
MANIFEST_NAME = "manifest.v1.json"
MAP_FIELDS = (
    "source_atom_site_id", "source_label_asym_id", "source_auth_asym_id",
    "source_label_entity_id", "source_model", "source_label_seq_id",
    "source_auth_seq_id", "source_label_comp_id", "source_label_atom_id",
    "source_type_symbol", "source_x", "source_y", "source_z",
    "source_formal_charge", "output_line_number", "output_atom_serial",
    "output_chain_id", "output_residue_number", "output_residue_name",
    "output_atom_name", "output_element", "output_x", "output_y", "output_z",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sites(raw: bytes) -> list[dict[str, str]]:
    data = MMCIF2Dict(io.StringIO(raw.decode("ascii")))
    keys = (
        "id", "group_PDB", "label_asym_id", "auth_asym_id", "label_entity_id",
        "pdbx_PDB_model_num", "label_seq_id", "auth_seq_id", "label_comp_id",
        "auth_comp_id", "label_atom_id", "auth_atom_id", "type_symbol",
        "label_alt_id", "pdbx_PDB_ins_code", "Cartn_x", "Cartn_y", "Cartn_z",
        "occupancy", "B_iso_or_equiv", "pdbx_formal_charge",
    )
    columns = {key: data[f"_atom_site.{key}"] for key in keys}
    lengths = {len(column) for column in columns.values()}
    if len(lengths) != 1:
        raise ValueError("source atom_site columns have different lengths")
    rows = [{key: columns[key][i] for key in keys} for i in range(lengths.pop())]
    selected = [row for row in rows if row["label_asym_id"] == "E"]
    if len(selected) != 2124 or len({row["id"] for row in selected}) != 2124:
        raise ValueError("unexpected receptor atom-site count or duplicate ID")
    for row in selected:
        if (row["group_PDB"], row["label_entity_id"], row["auth_asym_id"],
            row["pdbx_PDB_model_num"], row["label_alt_id"]) != ("ATOM", "5", "R", "1", "."):
            raise ValueError("unexpected selected receptor identity")
        if (row["label_comp_id"] != row["auth_comp_id"]
                or row["label_atom_id"] != row["auth_atom_id"]
                or row["pdbx_PDB_ins_code"] not in ("?", ".")):
            raise ValueError("unhandled residue, atom, or insertion identity")
    return selected


def _chain(number: int) -> str:
    if 26 <= number <= 227:
        return "A"
    if 263 <= number <= 338:
        return "B"
    raise ValueError(f"unexpected observed receptor residue {number}")


def _pdb_atom(row: dict[str, str], serial: int, chain: str, residue_number: int) -> str:
    name, residue, element = row["label_atom_id"], row["label_comp_id"], row["type_symbol"]
    if len(name) > 3 or len(residue) != 3 or element not in {"C", "N", "O", "S"}:
        raise ValueError("atom cannot be represented by this fixed PDB profile")
    xyz = [float(row[f"Cartn_{axis}"]) for axis in "xyz"]
    occupancy, b_factor = float(row["occupancy"]), float(row["B_iso_or_equiv"])
    line = (
        f"ATOM  {serial:5d}  {name:<3s} {residue:>3s} {chain}{residue_number:4d}    "
        f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}"
        f"{occupancy:6.2f}{b_factor:6.2f}          {element:>2s}  "
    )
    if len(line) != 80:
        raise ValueError("PDB ATOM record must be exactly 80 columns")
    if any(f"{value:.3f}" != row[f"Cartn_{axis}"] for value, axis in zip(xyz, "xyz")):
        raise ValueError("PDB coordinate would round source coordinate")
    return line + "\n"


def _ter(serial: int, row: dict[str, str], chain: str) -> str:
    return (
        f"TER   {serial:5d}      {row['label_comp_id']:>3s} {chain}"
        f"{int(row['auth_seq_id']):4d}"
    ).ljust(80) + "\n"


def _render(sites: list[dict[str, str]]) -> tuple[bytes, bytes]:
    lines, mapping = [], []
    previous_chain = None
    previous_row = None
    serial = 1
    seen_residues = set()
    for row in sites:
        number = int(row["auth_seq_id"])
        chain = _chain(number)
        if chain != previous_chain and previous_row is not None:
            lines.append(_ter(serial, previous_row, previous_chain))
            serial += 1
        lines.append(_pdb_atom(row, serial, chain, number))
        mapping.append({
            "source_atom_site_id": row["id"],
            "source_label_asym_id": row["label_asym_id"],
            "source_auth_asym_id": row["auth_asym_id"],
            "source_label_entity_id": row["label_entity_id"],
            "source_model": row["pdbx_PDB_model_num"],
            "source_label_seq_id": row["label_seq_id"],
            "source_auth_seq_id": row["auth_seq_id"],
            "source_label_comp_id": row["label_comp_id"],
            "source_label_atom_id": row["label_atom_id"],
            "source_type_symbol": row["type_symbol"],
            "source_x": row["Cartn_x"],
            "source_y": row["Cartn_y"],
            "source_z": row["Cartn_z"],
            "source_formal_charge": row["pdbx_formal_charge"],
            "output_line_number": str(len(lines)),
            "output_atom_serial": str(serial),
            "output_chain_id": chain,
            "output_residue_number": str(number),
            "output_residue_name": row["label_comp_id"],
            "output_atom_name": row["label_atom_id"],
            "output_element": row["type_symbol"],
            "output_x": row["Cartn_x"],
            "output_y": row["Cartn_y"],
            "output_z": row["Cartn_z"],
        })
        serial += 1
        previous_chain, previous_row = chain, row
        seen_residues.add((number, row["label_comp_id"]))
    if previous_row is None or len(seen_residues) != 278:
        raise ValueError("unexpected receptor residue inventory")
    lines.extend((_ter(serial, previous_row, previous_chain), "END\n"))
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=MAP_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(mapping)
    return "".join(lines).encode("ascii"), table.getvalue().encode("ascii")


def _manifest(pdb: bytes, atom_map: bytes) -> bytes:
    document = {
        "schema_version": "human_5ht6_7xtb_receptor_source_extraction_v1",
        "status": "SOURCE_ONLY_UNPREPARED_BLOCKED",
        "source": {
            "entry_id": "7XTB", "url": "https://files.rcsb.org/download/7XTB.cif",
            "bytes": SOURCE_BYTES, "sha256": SOURCE_SHA256,
        },
        "selection": {
            "label_entity_id": "5", "label_asym_id": "E", "auth_asym_id": "R",
            "pdb_model_num": "1", "group_pdb": "ATOM", "altloc": ".",
        },
        "output": {
            "pdb": {"name": PDB_NAME, "bytes": len(pdb), "sha256": _sha(pdb)},
            "source_atom_map": {"name": MAP_NAME, "bytes": len(atom_map), "sha256": _sha(atom_map)},
        },
        "observed": {
            "atom_site_rows": 2124, "residues": 278,
            "auth_residue_segments": [[26, 227], [263, 338]],
            "output_chain_segments": [
                {"chain_id": "A", "source_label_asym_id": "E", "auth_residue_range": [26, 227]},
                {"chain_id": "B", "source_label_asym_id": "E", "auth_residue_range": [263, 338]},
            ],
            "unobserved_auth_residue_segments": [[-143, 25], [228, 262], [339, 440]],
            "unobserved_atom": {"auth_seq_id": "26", "residue": "SER", "atom": "OG"},
            "declared_disulfide": {"auth_residues": [99, 180], "atoms": ["SG", "SG"], "printed_distance_angstrom": "2.028"},
        },
        "derivation": {
            "coordinates_copied_from_atom_site": True,
            "source_atom_order_preserved": True,
            "gap_227_263_split_by_TER_and_distinct_output_chain_ids": True,
            "atoms_or_residues_generated": False,
            "hydrogens_added": False, "termini_capped": False,
            "parameters_or_charges_assigned": False,
            "ligand_included": False,
        },
        "authority": {
            "prepared_receptor": False, "prepared_gromacs_input": False,
            "assay_state_equivalence_verified": False, "physical_evaluations": 0,
            "scientifically_validated": False, "roles_assigned": False,
            "protected_inputs_read": False,
        },
    }
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def _write_same_or_new(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"refusing to replace changed artifact: {path}")
    else:
        path.write_bytes(content)


def extract(source: Path, output_dir: Path) -> None:
    raw = source.read_bytes()
    if len(raw) != SOURCE_BYTES or _sha(raw) != SOURCE_SHA256:
        raise ValueError("7XTB source size or SHA-256 mismatch")
    pdb, atom_map = _render(_sites(raw))
    if source.read_bytes() != raw:
        raise ValueError("7XTB source changed during extraction")
    manifest = _manifest(pdb, atom_map)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in ((PDB_NAME, pdb), (MAP_NAME, atom_map), (MANIFEST_NAME, manifest)):
        _write_same_or_new(output_dir / name, content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    extract(args.source, args.output_dir)
    print(json.dumps({"status": "SOURCE_ONLY_UNPREPARED_BLOCKED", "atom_site_rows": 2124,
                      "output_dir": str(args.output_dir.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
