"""Recompute a candidate-only observation from the two unchanged archive files.

This standalone verifier needs only the Python standard library. It loads the
repository's CIF syntax module directly, without importing the molecular engine.
It selects source rows, compares atom names/elements, and measures distances;
it does not resolve alternate locations or assign chemistry or parameters.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
        "official_sources/coordinates-5arg.cif",
        744344,
        "ba33c3dc604445e1d49cf549b9738abcfd7f5727ef900e4f3d1f946a8d26ff74",
    ),
    "ccd_h41": (
        "official_sources/chemcomp-h41.cif",
        10621,
        "41f1ec80e2fd231ad561c370ec01cf7290bea32f1cb69cdca15b7a185ab9e651",
    ),
}
H41_SELECTION = {
    "group_pdb": "HETATM",
    "label_comp_id": "H41",
    "label_asym_id": "E",
    "label_entity_id": "3",
    "auth_comp_id": "H41",
    "auth_asym_id": "A",
    "auth_seq_id": "1432",
    "pdbx_pdb_model_num": "1",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _load_cif_syntax():
    path = REPOSITORY / "betelgeuze_engine_v2/molecular/mmcif_syntax.py"
    name = "_smyd2_source_geometry_cif_syntax"
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "cif_parser_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses requires this during module execution.
    spec.loader.exec_module(module)
    return module.parse_cif_block


def _read_sources(root):
    raw, receipts = {}, {}
    for key, (relative, size, digest) in SOURCES.items():
        path = root / relative
        require(
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve()),
            "archive_missing_or_outside_packet",
        )
        require(path.stat().st_size == size, "archive_bytes_changed")
        with path.open("rb") as stream:
            value = stream.read(size + 1)
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


def _rows(block, category):
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
    # Source markers such as '?' and '.' remain literal tokens in this receipt.
    return [
        {
            "source_line": min(token.line_number for token in row.values()),
            "values": {key[len(prefix) :]: token.value for key, token in row.items()},
        }
        for row in values
    ]


def _select(rows, selection):
    return [
        row
        for row in rows
        if all(row["values"].get(k) == v for k, v in selection.items())
    ]


def _point(row):
    point = tuple(Decimal(row["values"]["cartn_" + axis]) for axis in "xyz")
    require(all(value.is_finite() for value in point), "nonfinite_source_coordinate")
    return point


def _squared_distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(_point(first), _point(second)))


def _distance(first, second):
    with localcontext() as context:
        context.prec = 50
        value = _squared_distance(first, second).sqrt()
        return format(
            value.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN), "f"
        )


def _atom(row):
    keys = (
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
        "pdbx_pdb_ins_code",
        "pdbx_pdb_model_num",
        "occupancy",
        "pdbx_formal_charge",
    )
    return {
        "source_line": row["source_line"],
        "source_identity_and_annotations": {key: row["values"][key] for key in keys},
        "coordinate_angstrom_source_tokens": [
            row["values"]["cartn_" + axis] for axis in "xyz"
        ],
    }


def _pair(first, second):
    return {
        "atoms": [_atom(first), _atom(second)],
        "distance_angstrom": _distance(first, second),
    }


def _nearest(first, second):
    require(bool(first) and bool(second), "empty_distance_selection")
    a, b = min(
        ((a, b) for a in first for b in second),
        key=lambda pair: (
            _squared_distance(*pair),
            int(pair[0]["values"]["id"]),
            int(pair[1]["values"]["id"]),
        ),
    )
    return _pair(a, b)


def build_observation(root=ROOT):
    raw, sources = _read_sources(root)
    parse = _load_cif_syntax()
    coordinate_block = parse(raw["coordinates"].decode("ascii"))
    ccd_block = parse(raw["ccd_h41"].decode("ascii"))
    require(
        _rows(coordinate_block, "_entry")[0]["values"]["id"] == "5ARG",
        "entry_identity_changed",
    )
    sites = _rows(coordinate_block, "_atom_site")
    require(
        {row["values"]["pdbx_pdb_model_num"] for row in sites} == {"1"},
        "source_model_inventory_changed",
    )
    require(
        len({row["values"]["id"] for row in sites}) == len(sites),
        "duplicate_atom_site_id",
    )
    h41 = _select(sites, H41_SELECTION)
    require(len(h41) == 35, "h41_selection_changed")
    require(
        all(row["values"]["label_alt_id"] == "." for row in h41),
        "h41_altloc_unresolved",
    )
    declared = _select(_rows(ccd_block, "_chem_comp_atom"), {"comp_id": "H41"})
    dictionary = {
        row["values"]["atom_id"]: row["values"]["type_symbol"] for row in declared
    }
    require(len(dictionary) == len(declared) == 55, "ccd_atom_dictionary_changed")
    observed = {
        row["values"]["label_atom_id"]: row["values"]["type_symbol"] for row in h41
    }
    require(len(observed) == len(h41), "duplicate_h41_atom_name")
    require(
        all(dictionary.get(name) == element for name, element in observed.items()),
        "h41_ccd_atom_mismatch",
    )
    missing = {
        name: element for name, element in dictionary.items() if name not in observed
    }

    selected = {}
    for atom_id, label_asym, component, residue, atom_name in (
        ("1653", "A", "CYS", "209", "SG"),
        ("2087", "A", "CYS", "262", "SG"),
        ("2102", "A", "CYS", "264", "SG"),
        ("2126", "A", "CYS", "267", "SG"),
        ("3473", "B", "ZN", "1003", "ZN"),
    ):
        matches = _select(
            sites,
            {
                "id": atom_id,
                "label_asym_id": label_asym,
                "label_comp_id": component,
                "auth_asym_id": "A",
                "auth_seq_id": residue,
                "auth_atom_id": atom_name,
                "label_atom_id": atom_name,
                "label_alt_id": ".",
                "pdbx_pdb_model_num": "1",
            },
        )
        require(len(matches) == 1, "explicit_geometry_selection_changed")
        selected[atom_id] = matches[0]
    annotations = _rows(coordinate_block, "_struct_conn")
    require(len(annotations) == 1, "struct_conn_inventory_changed")
    annotation = annotations[0]
    expected_annotation = {
        "id": "disulf1",
        "conn_type_id": "disulf",
        "pdbx_dist_value": "2.333",
        "ptnr1_label_asym_id": "A",
        "ptnr1_label_comp_id": "CYS",
        "ptnr1_label_seq_id": "209",
        "ptnr1_label_atom_id": "SG",
        "ptnr1_symmetry": "1_555",
        "ptnr2_label_asym_id": "A",
        "ptnr2_label_comp_id": "CYS",
        "ptnr2_label_seq_id": "267",
        "ptnr2_label_atom_id": "SG",
        "ptnr2_symmetry": "1_555",
    }
    require(
        all(annotation["values"].get(k) == v for k, v in expected_annotation.items()),
        "disulfide_annotation_changed",
    )

    protein_selection = {
        "group_pdb": "ATOM",
        "label_asym_id": "A",
        "label_entity_id": "1",
        "pdbx_pdb_model_num": "1",
    }
    sam_selection = {
        "label_comp_id": "SAM",
        "label_asym_id": "G",
        "auth_asym_id": "A",
        "auth_seq_id": "1434",
        "pdbx_pdb_model_num": "1",
    }
    water_selection = {
        "label_comp_id": "HOH",
        "label_asym_id": "H",
        "type_symbol": "O",
        "pdbx_pdb_model_num": "1",
    }
    protein = [
        row
        for row in _select(sites, protein_selection)
        if row["values"]["type_symbol"] not in {"H", "D"}
    ]
    sam = [
        row
        for row in _select(sites, sam_selection)
        if row["values"]["type_symbol"] not in {"H", "D"}
    ]
    waters = _select(sites, water_selection)
    close_waters = []
    for water in waters:
        nearest = min(
            h41,
            key=lambda atom: (
                _squared_distance(atom, water),
                int(atom["values"]["id"]),
            ),
        )
        if _squared_distance(nearest, water) <= Decimal(16):
            close_waters.append(
                {
                    "water_atom_site_id": water["values"]["id"],
                    "water_auth_asym_id": water["values"]["auth_asym_id"],
                    "water_auth_seq_id": water["values"]["auth_seq_id"],
                    "nearest_h41_atom_site_id": nearest["values"]["id"],
                    "distance_angstrom": _distance(nearest, water),
                }
            )
    observation = {
        "schema_version": "smyd2_5arg_source_geometry_observation_v1",
        "status": "SOURCE_GEOMETRY_OBSERVED_PREPARATION_AND_ADMISSION_BLOCKED",
        "qualification": "NOT_QUALIFIED",
        "evidence_class": "unprepared_archive_coordinate_observation",
        "sources": sources,
        "method": {
            "cif_syntax_parser": "betelgeuze_engine_v2/molecular/mmcif_syntax.py",
            "coordinate_frame": "deposited_model_1_asymmetric_unit",
            "distance_definition": "Euclidean_distance_from_printed_Cartesian_coordinates",
            "distance_encoding": "angstrom_decimal_string_12_places_round_half_even",
            "symmetry_or_assembly_transform_applied": False,
            "periodic_minimum_image_applied": False,
            "alternate_locations_resolved": False,
            "protein_altloc_policy": "retain_all_source_rows_including_A_and_B_for_nearest_pair_observation",
            "water_radius_angstrom": "4.0",
            "water_radius_boundary": "inclusive",
            "interpretation": "distances_and_source_annotations_only_not_a_calibrated_clash_or_coordination_test",
        },
        "h41_completeness": {
            "selection": {"entry_id": "5ARG", **H41_SELECTION},
            "observed_atom_site_ids": [row["values"]["id"] for row in h41],
            "observed_heavy_atom_names": sorted(
                name for name, element in observed.items() if element not in {"H", "D"}
            ),
            "observed_heavy_atom_count": sum(
                element not in {"H", "D"} for element in observed.values()
            ),
            "observed_hydrogen_atom_count": sum(
                element in {"H", "D"} for element in observed.values()
            ),
            "ccd_declared_atom_count": len(dictionary),
            "missing_heavy_atom_names": sorted(
                name for name, element in missing.items() if element not in {"H", "D"}
            ),
            "missing_hydrogen_atom_names": sorted(
                name for name, element in missing.items() if element in {"H", "D"}
            ),
            "source_atom_site_unknown_formal_charge_count": sum(
                row["values"]["pdbx_formal_charge"] == "?" for row in h41
            ),
            "interpretation": "atom_name_and_element_coverage_against_CCD_only_not_complete_preparation_or_assay_microstate_equivalence",
        },
        "disulfide_annotation_and_nearby_zinc": {
            "source_struct_conn_annotation": annotation,
            "source_annotated_partner_distance": _pair(
                selected["1653"], selected["2126"]
            ),
            "zinc_to_sulfur_distances": [
                _pair(selected["3473"], selected[key])
                for key in ("1653", "2087", "2102", "2126")
            ],
            "annotation_adjudicated": False,
            "coordination_or_covalence_inferred": False,
            "interpretation": "the_deposited_disulf_annotation_and_Zn_S_proximity_are_preserved_separately_without_selecting_chemical_state",
        },
        "h41_environment": {
            "protein_selection": protein_selection,
            "protein_heavy_atom_rows": len(protein),
            "protein_altloc_rows_retained": sum(
                row["values"]["label_alt_id"] not in {".", "?"} for row in protein
            ),
            "nearest_protein_heavy_atom_pair": _nearest(h41, protein),
            "sam_selection": sam_selection,
            "sam_heavy_atom_rows": len(sam),
            "nearest_sam_heavy_atom_pair": _nearest(h41, sam),
            "water_oxygen_selection": water_selection,
            "water_oxygen_rows": len(waters),
            "water_oxygens_within_radius": len(close_waters),
            "within_radius_water_nearest_pairs": close_waters,
            "all_nonpoly_component_atom_site_counts": dict(
                sorted(
                    Counter(
                        row["values"]["label_comp_id"]
                        for row in sites
                        if row["values"]["group_pdb"] == "HETATM"
                    ).items()
                )
            ),
        },
        "eligibility": {
            "receptor_prepared": False,
            "ligands_prepared": False,
            "chemical_state_selected": False,
            "parameters_assigned": False,
            "prepared_input_executable": False,
            "physical_evaluations": 0,
            "source_roles_assigned": False,
            "training_admitted": False,
            "calibration_admitted": False,
            "independent_evaluation_admitted": False,
            "customer_execution": False,
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


def verify(root=ROOT):
    expected = json_bytes(build_observation(root))
    # Exact canonical bytes reject extra fields, duplicate JSON keys, changed
    # selections/distances, promoted flags and nonfinite spellings alike.
    require(
        (root / RECEIPT_NAME).read_bytes() == expected,
        "source_geometry_receipt_mismatch",
    )
    return {
        "status": "PASS_SOURCE_GEOMETRY_ONLY",
        "prepared_pairs": 0,
        "physical_evaluations": 0,
        "scientifically_validated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="create the receipt exclusively; never overwrite an existing file",
    )
    args = parser.parse_args()
    if args.write:
        value = json_bytes(build_observation())
        with (ROOT / RECEIPT_NAME).open("xb") as stream:
            stream.write(value)
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
