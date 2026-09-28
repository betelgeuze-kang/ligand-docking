"""Recompute the source-only 3MXF/JQ1 atom-lineage and geometry receipt.

No receptor/ligand preparation, assay microstate, or physical validity is
inferred. This standalone script imports only the repository CIF syntax parser.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
RECEIPT_NAME = "source_geometry.v1.json"
SOURCES = {
    "coordinates": (
        "official_sources/coordinates-3mxf.cif",
        287430,
        "fb123201edb59709d14b64c5cb4296a90b6d35c45505baba48600d04e4cdd401",
    ),
    "ccd_jq1": (
        "official_sources/chemcomp-jq1.cif",
        10889,
        "9652a88ed9dd1f78e4dbfd2fcd127e40a9643fc5b111d84d8e615adc399213e5",
    ),
}
JQ1_SELECTION = {
    "group_pdb": "HETATM",
    "label_comp_id": "JQ1",
    "label_asym_id": "B",
    "label_entity_id": "2",
    "auth_comp_id": "JQ1",
    "auth_asym_id": "A",
    "auth_seq_id": "1",
    "pdbx_pdb_model_num": "1",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _load_parser():
    path = REPOSITORY / "betelgeuze_engine_v2/molecular/mmcif_syntax.py"
    spec = importlib.util.spec_from_file_location("_brd4_source_cif_syntax", path)
    require(spec is not None and spec.loader is not None, "cif_parser_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # Required by dataclasses during import.
    spec.loader.exec_module(module)
    return module.parse_cif_block


def _read_sources(root: Path):
    raw, receipts = {}, {}
    for key, (relative, size, digest) in SOURCES.items():
        path = root / relative
        require(
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve()),
            "archive_missing_or_outside_packet",
        )
        value = path.read_bytes()
        require(
            len(value) == size and hashlib.sha256(value).hexdigest() == digest,
            "archive_bytes_changed",
        )
        raw[key] = value
        receipts[key] = {
            "relative_path": relative,
            "size_bytes": size,
            "sha256": digest,
        }
    return raw, receipts


def _rows(block, category: str):
    prefix = category + "."
    loops = [loop for loop in block.loops if category in loop.categories]
    scalars = {
        key: value
        for key, value in block.scalar_values.items()
        if key.startswith(prefix)
    }
    require(not (loops and scalars) and len(loops) <= 1, "ambiguous_cif_category")
    if loops:
        loop = loops[0]
        require(loop.categories == (category,), "mixed_cif_category")
        values = [dict(zip(loop.tags, row)) for row in loop.rows]
    else:
        require(bool(scalars), "missing_cif_category")
        values = [scalars]
    return [
        {
            "source_line": min(token.line_number for token in row.values()),
            "values": {key[len(prefix) :]: token.value for key, token in row.items()},
        }
        for row in values
    ]


def _select(rows, selection: dict[str, str]):
    return [
        row
        for row in rows
        if all(row["values"].get(key) == value for key, value in selection.items())
    ]


def _point(row):
    point = tuple(Decimal(row["values"]["cartn_" + axis]) for axis in "xyz")
    require(all(value.is_finite() for value in point), "nonfinite_source_coordinate")
    return point


def _distance_squared(first, second):
    return sum(
        (left - right) ** 2 for left, right in zip(_point(first), _point(second))
    )


def _distance(first, second):
    with localcontext() as context:
        context.prec = 50
        return format(
            _distance_squared(first, second)
            .sqrt()
            .quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN),
            "f",
        )


def _atom(row):
    fields = (
        "id",
        "group_pdb",
        "type_symbol",
        "label_atom_id",
        "label_alt_id",
        "label_comp_id",
        "label_asym_id",
        "label_entity_id",
        "label_seq_id",
        "auth_atom_id",
        "auth_comp_id",
        "auth_asym_id",
        "auth_seq_id",
        "pdbx_pdb_model_num",
        "occupancy",
        "pdbx_formal_charge",
    )
    return {
        "source_line": row["source_line"],
        "source_identity_and_annotations": {key: row["values"][key] for key in fields},
        "coordinate_angstrom_source_tokens": [
            row["values"]["cartn_" + axis] for axis in "xyz"
        ],
    }


def _nearest(first, second):
    require(bool(first) and bool(second), "empty_distance_selection")
    left, right = min(
        ((left, right) for left in first for right in second),
        key=lambda pair: (
            _distance_squared(*pair),
            int(pair[0]["values"]["id"]),
            int(pair[1]["values"]["id"]),
        ),
    )
    return {
        "atoms": [_atom(left), _atom(right)],
        "distance_angstrom": _distance(left, right),
    }


def build_observation(root: Path = ROOT):
    raw, sources = _read_sources(root)
    parse = _load_parser()
    coordinate_block = parse(raw["coordinates"].decode("ascii"))
    ccd_block = parse(raw["ccd_jq1"].decode("ascii"))
    require(
        _rows(coordinate_block, "_entry")[0]["values"]["id"] == "3MXF",
        "entry_identity_changed",
    )
    sites = _rows(coordinate_block, "_atom_site")
    require(
        {row["values"]["pdbx_pdb_model_num"] for row in sites} == {"1"}
        and len({row["values"]["id"] for row in sites}) == len(sites),
        "source_model_or_atom_site_id_changed",
    )
    jq1 = _select(sites, JQ1_SELECTION)
    require(len(jq1) == 31, "jq1_instance_selection_changed")
    require(
        all(row["values"]["label_alt_id"] == "." for row in jq1),
        "jq1_altloc_unresolved",
    )
    ccd = _rows(ccd_block, "_chem_comp")[0]["values"]
    require(
        ccd["id"] == "JQ1"
        and ccd["pdbx_model_coordinates_db_code"] == "3MXF"
        and ccd["pdbx_formal_charge"] == "1",
        "ccd_identity_or_charge_changed",
    )
    declared = _select(_rows(ccd_block, "_chem_comp_atom"), {"comp_id": "JQ1"})
    dictionary = {row["values"]["atom_id"]: row for row in declared}
    observed = {row["values"]["label_atom_id"]: row for row in jq1}
    require(
        len(dictionary) == len(declared) == 57 and len(observed) == len(jq1),
        "duplicate_or_changed_jq1_atom_dictionary",
    )
    missing = {name: row for name, row in dictionary.items() if name not in observed}
    require(
        len(missing) == 26
        and all(row["values"]["type_symbol"] == "H" for row in missing.values()),
        "jq1_heavy_atom_coverage_changed",
    )
    for name, row in observed.items():
        component = dictionary[name]["values"]
        require(
            row["values"]["type_symbol"] == component["type_symbol"]
            and all(
                row["values"]["cartn_" + axis] == component["model_cartn_" + axis]
                for axis in "xyz"
            ),
            "jq1_ccd_model_coordinate_or_element_mismatch",
        )
    stereo = {
        name: row["values"]["pdbx_stereo_config"]
        for name, row in dictionary.items()
        if row["values"]["pdbx_stereo_config"] in {"R", "S"}
    }
    charged = {
        name: row["values"]["charge"]
        for name, row in dictionary.items()
        if row["values"]["charge"] != "0"
    }
    require(
        stereo == {"CBC": "S"} and charged == {"NBD": "1"},
        "ccd_stereo_or_atom_charge_changed",
    )
    bonds = _select(_rows(ccd_block, "_chem_comp_bond"), {"comp_id": "JQ1"})
    heavy_bonds = [
        bond
        for bond in bonds
        if bond["values"]["atom_id_1"] in observed
        and bond["values"]["atom_id_2"] in observed
    ]
    require(len(heavy_bonds) == 34, "ccd_heavy_bond_inventory_changed")
    bond_distances = [
        {
            "ccd_source_line": bond["source_line"],
            "ccd_atom_names": [
                bond["values"]["atom_id_1"],
                bond["values"]["atom_id_2"],
            ],
            "ccd_value_order": bond["values"]["value_order"],
            "distance_angstrom": _distance(
                observed[bond["values"]["atom_id_1"]],
                observed[bond["values"]["atom_id_2"]],
            ),
        }
        for bond in heavy_bonds
    ]

    protein = _select(
        sites, {"group_pdb": "ATOM", "label_asym_id": "A", "label_entity_id": "1"}
    )
    sequence = _select(
        _rows(coordinate_block, "_pdbx_poly_seq_scheme"), {"asym_id": "A"}
    )
    require(
        len(sequence) == 127
        and sequence[0]["values"]["auth_seq_num"] == "42"
        and sequence[-1]["values"]["auth_seq_num"] == "168"
        and sequence[1]["values"]["mon_id"] == "MET",
        "protein_sequence_selection_changed",
    )
    altloc = [row for row in protein if row["values"]["label_alt_id"] not in {".", "?"}]
    nonpoly = [row for row in sites if row["values"]["group_pdb"] == "HETATM"]
    by_component = {}
    for component in sorted({row["values"]["label_comp_id"] for row in nonpoly}):
        selected = _select(nonpoly, {"label_comp_id": component})
        by_component[component] = [row["values"]["id"] for row in selected]
    require(
        {name: len(ids) for name, ids in by_component.items()}
        == {"DMS": 4, "EDO": 12, "HOH": 208, "IOD": 1, "JQ1": 31},
        "nonpoly_inventory_changed",
    )
    ion = _select(
        sites, {"label_comp_id": "IOD", "label_asym_id": "C", "auth_seq_id": "169"}
    )
    waters = _select(
        sites, {"label_comp_id": "HOH", "label_asym_id": "H", "type_symbol": "O"}
    )
    solvents = [
        row for row in nonpoly if row["values"]["label_comp_id"] in {"DMS", "EDO"}
    ]
    require(
        len(ion) == 1 and len(waters) == 208 and len(solvents) == 16,
        "environment_selection_changed",
    )
    close_waters = []
    for water in waters:
        near = min(
            jq1,
            key=lambda row: (_distance_squared(row, water), int(row["values"]["id"])),
        )
        if _distance_squared(near, water) <= Decimal(16):
            close_waters.append(
                {
                    "water_atom_site_id": water["values"]["id"],
                    "water_auth_seq_id": water["values"]["auth_seq_id"],
                    "nearest_jq1_atom_site_id": near["values"]["id"],
                    "distance_angstrom": _distance(near, water),
                }
            )

    observation = {
        "schema_version": "brd4_3mxf_source_geometry_observation_v1",
        "status": "SOURCE_GEOMETRY_OBSERVED_PREPARATION_AND_ADMISSION_BLOCKED",
        "qualification": "NOT_QUALIFIED",
        "evidence_class": "unprepared_archive_coordinate_and_ccd_observation",
        "sources": sources,
        "method": {
            "cif_syntax_parser": "betelgeuze_engine_v2/molecular/mmcif_syntax.py",
            "coordinate_frame": "deposited_model_1_asymmetric_unit",
            "distance_definition": "Euclidean_distance_from_printed_Cartesian_coordinates",
            "distance_encoding": "angstrom_decimal_string_12_places_round_half_even",
            "symmetry_or_assembly_transform_applied": False,
            "periodic_minimum_image_applied": False,
            "alternate_locations_resolved": False,
            "protein_altloc_policy": "retain_all_source_A_and_B_rows_in_distance_observation",
            "water_radius_angstrom": "4.0",
            "water_radius_boundary": "inclusive",
            "interpretation": "source_distances_only_not_calibrated_clashes_contacts_or_preparation",
        },
        "jq1_source_and_ccd_lineage": {
            "selection": {"entry_id": "3MXF", **JQ1_SELECTION},
            "observed_atom_site_rows": [_atom(row) for row in jq1],
            "observed_heavy_atom_count": len(observed),
            "observed_hydrogen_atom_count": 0,
            "ccd_declared_atom_count": len(dictionary),
            "ccd_missing_hydrogen_names": sorted(missing),
            "ccd_heavy_atom_names_elements_and_model_coordinates_match": True,
            "ccd_formula": ccd["formula"],
            "ccd_formal_charge": ccd["pdbx_formal_charge"],
            "ccd_nonzero_atom_charges": charged,
            "ccd_stereocenters": stereo,
            "ccd_heavy_bond_distances": bond_distances,
            "coordinate_atom_site_unknown_formal_charge_count": sum(
                row["values"]["pdbx_formal_charge"] == "?" for row in jq1
            ),
            "assay_microstate_equivalence_inferred": False,
            "r_enantiomer_bound_pose_observed": False,
        },
        "protein_source_scope": {
            "chain_label_asym_id": "A",
            "poly_seq_scheme_residue_count": len(sequence),
            "source_residues_42_43": [row["values"] for row in sequence[:2]],
            "source_core_residues_44_168_count": len(sequence[2:]),
            "protein_atom_site_count": len(protein),
            "protein_altloc_rows": [_atom(row) for row in altloc],
            "assay_construct_equivalence_inferred": False,
        },
        "jq1_source_environment": {
            "nonpoly_component_atom_site_ids": by_component,
            "nearest_protein_heavy_atom_pair": _nearest(
                jq1,
                [
                    row
                    for row in protein
                    if row["values"]["type_symbol"] not in {"H", "D"}
                ],
            ),
            "nearest_iodide_pair": _nearest(jq1, ion),
            "nearest_dms_or_edo_pair": _nearest(jq1, solvents),
            "water_oxygen_rows": len(waters),
            "water_oxygens_within_radius": len(close_waters),
            "within_radius_water_nearest_pairs": close_waters,
            "ion_solvent_water_retain_or_exclude_decision_made": False,
        },
        "eligibility": {
            "receptor_prepared": False,
            "s_ligand_prepared": False,
            "r_ligand_prepared": False,
            "common_assay_microstate_selected": False,
            "charges_or_parameters_assigned": False,
            "prepared_input_executable": False,
            "physical_evaluations": 0,
            "source_roles_assigned": False,
            "training_admitted": False,
            "independent_evaluation_admitted": False,
            "scientifically_validated": False,
        },
    }
    require(_read_sources(root)[0] == raw, "source_changed_during_observation")
    return observation


def json_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("ascii")


def verify(root: Path = ROOT):
    expected = json_bytes(build_observation(root))
    path = root / RECEIPT_NAME
    require(
        path.is_file() and not path.is_symlink(),
        "source_geometry_receipt_missing_or_symlink",
    )
    require(path.read_bytes() == expected, "source_geometry_receipt_mismatch")
    return {
        "status": "PASS_SOURCE_GEOMETRY_ONLY",
        "prepared_pairs": 0,
        "physical_evaluations": 0,
        "scientifically_validated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="create the receipt; never overwrite"
    )
    args = parser.parse_args()
    if args.write:
        with (ROOT / RECEIPT_NAME).open("xb") as stream:
            stream.write(json_bytes(build_observation()))
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
