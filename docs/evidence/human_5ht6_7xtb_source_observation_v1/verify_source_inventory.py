"""Read-only 7XTB source inventory; no chemical preparation or physical score."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
SOURCE_SHA256 = "e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7"


def derive(source):
    raw = source.read_bytes()
    if len(raw) != 900097 or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("7xtb_source_hash_or_size_mismatch")
    spec = importlib.util.spec_from_file_location(
        "_7xtb_source_cif", REPO / "betelgeuze_engine_v2/molecular/mmcif_syntax.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    block = module.parse_cif_block(raw.decode("ascii"))
    categories = {}
    for loop in block.loops:
        for category in loop.categories:
            categories[category] = [
                {key: token.value for key, token in zip(loop.tags, row)}
                for row in loop.rows]
    for key, token in block.scalar_values.items():
        category = key.split(".")[0]
        categories.setdefault(category, [{}])[0][key] = token.value
    sites = categories["_atom_site"]
    receptor = [r for r in sites if r["_atom_site.label_asym_id"] == "E"]
    ligand = [r for r in sites if r["_atom_site.label_asym_id"] == "F"]
    if not ligand or any(r["_atom_site.label_comp_id"] != "SRO"
                         or r["_atom_site.auth_seq_id"] != "501"
                         or r["_atom_site.pdbx_pdb_model_num"] != "1" for r in ligand):
        raise ValueError("7xtb_ligand_instance_mismatch")
    residues = sorted({(int(r["_atom_site.label_seq_id"]),
                        r["_atom_site.auth_seq_id"], r["_atom_site.label_comp_id"])
                       for r in receptor})
    numbers = sorted(int(r[1]) for r in residues)
    segments = []
    for number in numbers:
        if not segments or number != segments[-1][1] + 1:
            segments.append([number, number])
        else:
            segments[-1][1] = number
    def xyz(row):
        return [float(row["_atom_site.cartn_" + axis]) for axis in "xyz"]
    contacts = {}
    closest = None
    for r in receptor:
        for ligand_row in ligand:
            distance = math.dist(xyz(r), xyz(ligand_row))
            pair = {"distance_angstrom": distance,
                    "receptor_atom_site_id": r["_atom_site.id"],
                    "ligand_atom_site_id": ligand_row["_atom_site.id"]}
            if closest is None or distance < closest["distance_angstrom"]:
                closest = pair
            key = (r["_atom_site.auth_seq_id"], r["_atom_site.label_comp_id"])
            if distance <= 4.0 and (key not in contacts or distance < contacts[key]):
                contacts[key] = distance
    summary = {
        "entry_atom_site_rows": len(sites),
        "receptor_atom_rows": len(receptor),
        "receptor_modeled_residue_count": len(residues),
        "receptor_observed_auth_number_segments": segments,
        "receptor_hydrogen_atom_rows": sum(r["_atom_site.type_symbol"] == "H" for r in receptor),
        "receptor_altloc_atom_rows": sum(r["_atom_site.label_alt_id"] not in {".", "?"} for r in receptor),
        "entry_water_atom_rows": sum(r["_atom_site.label_comp_id"] in {"HOH", "WAT", "DOD"} for r in sites),
        "entry_nonpolymer_components": dict(Counter(r["_atom_site.label_comp_id"] for r in sites
                                                      if r["_atom_site.group_pdb"] == "HETATM")),
        "ligand_atom_rows": len(ligand),
        "ligand_hydrogen_atom_rows": sum(r["_atom_site.type_symbol"] == "H" for r in ligand),
    }
    return {
        "schema_version": "7xtb_source_preparation_inventory_v1",
        "source_sha256": SOURCE_SHA256,
        "summary": summary,
        "receptor_modeled_residue_source_rows": [list(row) for row in residues],
        "source_categories": {c: categories.get(c) for c in (
            "_entity", "_entity_poly", "_struct_ref", "_struct_ref_seq",
            "_struct_ref_seq_dif", "_pdbx_unobs_or_zero_occ_residues",
            "_pdbx_unobs_or_zero_occ_atoms", "_struct_conn")},
        "source_distance_observations": {
            "closest_receptor_ligand_atom_pair": closest,
            "receptor_residues_with_atom_within_4_angstrom": [
                {"auth_seq_id": key[0], "residue_name": key[1],
                 "minimum_distance_angstrom": value}
                for key, value in sorted(contacts.items(), key=lambda item: int(item[0][0]))],
            "scope": "printed_asymmetric_unit_coordinates_no_transform",
            "interpretation": "4_angstrom_inventory_only_not_an_admitted_pocket_or_contact_quality_test",
        },
        "prepared": False, "physical_evaluations": 0,
        "assay_state_equivalence_verified": False,
        "roles_assigned": False, "protected_inputs_read": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    derived = derive(args.source)
    if args.check:
        if json.loads(args.check.read_text()) != derived:
            raise ValueError("source_inventory_mismatch")
        print(json.dumps({"status": "PASS_SOURCE_INVENTORY_REDERIVATION",
                          "physical_evaluations": 0, "prepared": False}))
    else:
        print(json.dumps(derived, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
