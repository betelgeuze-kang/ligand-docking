"""Verify the tracked source-only packet; optionally rederive it from 7XTB CIF.

Default verification needs only this tracked directory and the standard library.
The optional --source path must contain the unchanged, hash-pinned original CIF.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SOURCE_HASH = "e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7"
SOURCE_SIZE = 900097
PDB_NAME = "receptor-E-observed.pdb"
MAP_NAME = "source-atom-map.csv"
PINNED = {
    PDB_NAME: (172210, "8b5d0a754fd7d511331c63da4880b0464620a27ca2147602d0431a5f41e15d46"),
    MAP_NAME: (211885, "9c6a697cd43439e8e4f5434c1e05d8bafdef4d20882a0c9fc7f86fe2c99526b5"),
}
MAP_FIELDS = (
    "source_atom_site_id", "source_label_asym_id", "source_auth_asym_id",
    "source_label_entity_id", "source_model", "source_label_seq_id",
    "source_auth_seq_id", "source_label_comp_id", "source_label_atom_id",
    "source_type_symbol", "source_x", "source_y", "source_z",
    "source_formal_charge", "output_line_number", "output_atom_serial",
    "output_chain_id", "output_residue_number", "output_residue_name",
    "output_atom_name", "output_element", "output_x", "output_y", "output_z",
)


class PacketError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PacketError(message)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _segments(numbers: list[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for number in sorted(set(numbers)):
        if not result or number != result[-1][1] + 1:
            result.append([number, number])
        else:
            result[-1][1] = number
    return result


def _source_categories(source: Path) -> dict[str, list[dict[str, str]]]:
    raw = source.read_bytes()
    require(len(raw) == SOURCE_SIZE and _hash(raw) == SOURCE_HASH, "pinned source size or hash mismatch")
    parser_path = HERE.parents[2] / "betelgeuze_engine_v2/molecular/mmcif_syntax.py"
    spec = importlib.util.spec_from_file_location("_7xtb_receptor_packet_cif", parser_path)
    require(spec is not None and spec.loader is not None, "repository CIF parser unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    block = module.parse_cif_block(raw.decode("ascii"))
    categories: dict[str, list[dict[str, str]]] = {}
    for loop in block.loops:
        for category in loop.categories:
            categories[category] = [
                {tag: token.value for tag, token in zip(loop.tags, row)} for row in loop.rows
            ]
    for tag, token in block.scalar_values.items():
        categories.setdefault(tag.split(".")[0], [{}])[0][tag] = token.value
    return categories


def _check_source(source: Path, map_rows: list[dict[str, str]], pdb_lines: list[str]) -> None:
    categories = _source_categories(source)
    selected = [row for row in categories["_atom_site"] if row["_atom_site.label_asym_id"] == "E"]
    require(len(selected) == len(map_rows) == 2124, "source selection count mismatch")
    for source_row, mapped in zip(selected, map_rows):
        expected = {
            "source_atom_site_id": source_row["_atom_site.id"],
            "source_label_asym_id": source_row["_atom_site.label_asym_id"],
            "source_auth_asym_id": source_row["_atom_site.auth_asym_id"],
            "source_label_entity_id": source_row["_atom_site.label_entity_id"],
            "source_model": source_row["_atom_site.pdbx_pdb_model_num"],
            "source_label_seq_id": source_row["_atom_site.label_seq_id"],
            "source_auth_seq_id": source_row["_atom_site.auth_seq_id"],
            "source_label_comp_id": source_row["_atom_site.label_comp_id"],
            "source_label_atom_id": source_row["_atom_site.label_atom_id"],
            "source_type_symbol": source_row["_atom_site.type_symbol"],
            "source_x": source_row["_atom_site.cartn_x"],
            "source_y": source_row["_atom_site.cartn_y"],
            "source_z": source_row["_atom_site.cartn_z"],
            "source_formal_charge": source_row["_atom_site.pdbx_formal_charge"],
        }
        for key, value in expected.items():
            require(mapped[key] == value, f"source-to-map mismatch: {key}")
        require(source_row["_atom_site.group_pdb"] == "ATOM"
                and source_row["_atom_site.label_alt_id"] == ".",
                "source selected row changed group or alternate location")
        line = pdb_lines[int(mapped["output_line_number"]) - 1]
        for axis, start in zip("xyz", (30, 38, 46)):
            require(line[start:start + 8].strip() == source_row[f"_atom_site.cartn_{axis}"],
                    f"source-to-PDB coordinate mismatch: {axis}")

    unobserved = [int(row["_pdbx_unobs_or_zero_occ_residues.auth_seq_id"])
                  for row in categories["_pdbx_unobs_or_zero_occ_residues"]
                  if row["_pdbx_unobs_or_zero_occ_residues.label_asym_id"] == "E"]
    require(len(unobserved) == 306 and _segments(unobserved) == [[-143, 25], [228, 262], [339, 440]],
            "source unobserved-residue declaration mismatch")
    missing_atoms = [row for row in categories["_pdbx_unobs_or_zero_occ_atoms"]
                     if row["_pdbx_unobs_or_zero_occ_atoms.label_asym_id"] == "E"]
    require(len(missing_atoms) == 1 and
            (missing_atoms[0]["_pdbx_unobs_or_zero_occ_atoms.auth_seq_id"],
             missing_atoms[0]["_pdbx_unobs_or_zero_occ_atoms.auth_comp_id"],
             missing_atoms[0]["_pdbx_unobs_or_zero_occ_atoms.auth_atom_id"]) == ("26", "SER", "OG"),
            "source unobserved-atom declaration mismatch")
    disulfides = [row for row in categories["_struct_conn"]
                  if row["_struct_conn.conn_type_id"] == "disulf"
                  and row["_struct_conn.ptnr1_label_asym_id"] == "E"
                  and row["_struct_conn.ptnr2_label_asym_id"] == "E"]
    require(len(disulfides) == 1 and
            (disulfides[0]["_struct_conn.ptnr1_auth_seq_id"],
             disulfides[0]["_struct_conn.ptnr2_auth_seq_id"],
             disulfides[0]["_struct_conn.ptnr1_label_atom_id"],
             disulfides[0]["_struct_conn.ptnr2_label_atom_id"],
             disulfides[0]["_struct_conn.pdbx_dist_value"]) == ("99", "180", "SG", "SG", "2.028"),
            "source disulfide declaration mismatch")


def verify_packet(packet_root: Path = HERE, source: Path | None = None) -> dict[str, object]:
    manifest = json.loads((packet_root / "manifest.v1.json").read_text(encoding="ascii"))
    require(set(manifest) == {"schema_version", "status", "source", "selection", "output",
                             "observed", "derivation", "authority"}, "manifest keys changed")
    require(manifest["schema_version"] == "human_5ht6_7xtb_receptor_source_extraction_v1"
            and manifest["status"] == "SOURCE_ONLY_UNPREPARED_BLOCKED", "manifest status changed")
    require(manifest["source"] == {
        "entry_id": "7XTB", "url": "https://files.rcsb.org/download/7XTB.cif",
        "bytes": SOURCE_SIZE, "sha256": SOURCE_HASH,
    }, "manifest source identity changed")
    require(manifest["selection"] == {
        "label_entity_id": "5", "label_asym_id": "E", "auth_asym_id": "R",
        "pdb_model_num": "1", "group_pdb": "ATOM", "altloc": ".",
    }, "manifest selection changed")
    require(manifest["observed"] == {
        "atom_site_rows": 2124, "residues": 278,
        "auth_residue_segments": [[26, 227], [263, 338]],
        "output_chain_segments": [
            {"chain_id": "A", "source_label_asym_id": "E", "auth_residue_range": [26, 227]},
            {"chain_id": "B", "source_label_asym_id": "E", "auth_residue_range": [263, 338]},
        ],
        "unobserved_auth_residue_segments": [[-143, 25], [228, 262], [339, 440]],
        "unobserved_atom": {"auth_seq_id": "26", "residue": "SER", "atom": "OG"},
        "declared_disulfide": {"auth_residues": [99, 180], "atoms": ["SG", "SG"],
                               "printed_distance_angstrom": "2.028"},
    }, "manifest observed source state changed")
    require(manifest["derivation"] == {
        "coordinates_copied_from_atom_site": True, "source_atom_order_preserved": True,
        "gap_227_263_split_by_TER_and_distinct_output_chain_ids": True,
        "atoms_or_residues_generated": False, "hydrogens_added": False,
        "termini_capped": False, "parameters_or_charges_assigned": False,
        "ligand_included": False,
    }, "manifest derivation claim changed")
    require(manifest["authority"] == {
        "prepared_receptor": False, "prepared_gromacs_input": False,
        "assay_state_equivalence_verified": False, "physical_evaluations": 0,
        "scientifically_validated": False, "roles_assigned": False,
        "protected_inputs_read": False,
    }, "manifest authority claim changed")

    contents = {name: (packet_root / name).read_bytes() for name in PINNED}
    require(manifest["output"] == {
        "pdb": {"name": PDB_NAME, "bytes": PINNED[PDB_NAME][0], "sha256": PINNED[PDB_NAME][1]},
        "source_atom_map": {"name": MAP_NAME, "bytes": PINNED[MAP_NAME][0], "sha256": PINNED[MAP_NAME][1]},
    }, "manifest output receipt changed")
    for name, raw in contents.items():
        require((len(raw), _hash(raw)) == PINNED[name], f"tracked artifact changed: {name}")

    pdb_lines = contents[PDB_NAME].decode("ascii").splitlines()
    mapping = csv.DictReader(io.StringIO(contents[MAP_NAME].decode("ascii")))
    require(tuple(mapping.fieldnames or ()) == MAP_FIELDS, "atom map columns changed")
    map_rows = list(mapping)
    require(len(map_rows) == 2124 and len(pdb_lines) == 2127, "PDB/map row count mismatch")
    require(len({row["source_atom_site_id"] for row in map_rows}) == 2124,
            "duplicate source atom-site ID")
    require(_segments([int(row["source_auth_seq_id"]) for row in map_rows])
            == [[26, 227], [263, 338]], "mapped residue segments changed")
    require(len({(row["source_auth_seq_id"], row["source_label_comp_id"])
                 for row in map_rows}) == 278, "mapped residue count changed")
    next_serial, current_chain, last_row = 1, None, None
    for row in map_rows:
        require(set(row) == set(MAP_FIELDS) and None not in row, "malformed map row")
        residue_number = int(row["source_auth_seq_id"])
        expected_chain = "A" if 26 <= residue_number <= 227 else "B"
        require((expected_chain == "A" or 263 <= residue_number <= 338),
                "unexpected mapped residue")
        if current_chain is not None and expected_chain != current_chain:
            ter = pdb_lines[int(row["output_line_number"]) - 2]
            require(ter[:6].strip() == "TER" and int(ter[6:11]) == next_serial
                    and ter[21] == current_chain and int(ter[22:26]) == 227,
                    "missing explicit TER at 227/263 gap")
            next_serial += 1
        require(row["output_atom_serial"] == str(next_serial), "mapped atom serial mismatch")
        line_number = int(row["output_line_number"])
        line = pdb_lines[line_number - 1]
        require(len(line) == 80 and line[:6] == "ATOM  " and int(line[6:11]) == next_serial,
                "PDB ATOM row or serial changed")
        require((line[12:16].strip(), line[16], line[17:20].strip(), line[21],
                 int(line[22:26]), line[26], line[76:78].strip(), line[78:80]) ==
                (row["output_atom_name"], " ", row["output_residue_name"], expected_chain,
                 residue_number, " ", row["output_element"], "  "),
                "PDB atom identity changed")
        require(row["source_label_asym_id"] == "E" and row["source_auth_asym_id"] == "R"
                and row["source_label_entity_id"] == "5" and row["source_model"] == "1"
                and row["output_chain_id"] == expected_chain
                and row["output_residue_number"] == row["source_auth_seq_id"]
                and row["output_residue_name"] == row["source_label_comp_id"]
                and row["output_atom_name"] == row["source_label_atom_id"]
                and row["output_element"] == row["source_type_symbol"],
                "source/output identity map changed")
        for axis, start in zip("xyz", (30, 38, 46)):
            require(row[f"output_{axis}"] == row[f"source_{axis}"]
                    == line[start:start + 8].strip(), f"source/output coordinate map changed: {axis}")
        next_serial += 1
        current_chain, last_row = expected_chain, row
    require(last_row is not None and current_chain == "B", "missing terminal receptor segment")
    require(pdb_lines[-2][:6].strip() == "TER"
            and int(pdb_lines[-2][6:11]) == next_serial
            and pdb_lines[-2][21] == "B" and int(pdb_lines[-2][22:26]) == 338
            and pdb_lines[-1] == "END", "unexpected PDB ending")
    require(sum(line[:6].strip() == "TER" for line in pdb_lines) == 2,
            "unexpected PDB chain break count")
    if source is not None:
        _check_source(source, map_rows, pdb_lines)
    return {"status": "PASS_SOURCE_ONLY_PACKET", "atom_site_rows": 2124,
            "source_rederived": source is not None, "prepared": False,
            "physical_evaluations": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-root", type=Path, default=HERE)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_packet(args.packet_root, args.source), sort_keys=True))


if __name__ == "__main__":
    main()
