"""Source-coordinate observations using V2 syntax, bonds and geometry.

This versioned adapter accepts a deposited entry's component tables without
requiring a parameterized chemical state. Unknown charges stay None. It does
not construct an AllAtomSystem, infer missing atoms, or admit physical scoring.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import re

import torch

from betelgeuze_engine_v2.geometry.neighbors import (
    NeighborOverflowError, RadiusGraphConfig, build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_canonical_topology import (
    MMCIF_COMPONENT_BOND_ORDERS,
)
from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
from betelgeuze_engine_v2.molecular.models import Bond, canonical_element_symbol

SCHEMA = "mmcif_ligand_source_observation_v1"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_SELECTED_ATOMS = 256


def _value(token):
    return None if token.value in {".", "?"} and not token.quoted else token.value


def _table(block, category, required):
    loops = [loop for loop in block.loops if category in loop.categories]
    scalars = {key: value for key, value in block.scalar_values.items() if key.startswith(category + ".")}
    if loops and scalars or len(loops) > 1:
        raise ValueError("ambiguous_category:" + category)
    if loops:
        loop = loops[0]
        if loop.categories != (category,) or not set(required).issubset(loop.tags):
            raise ValueError("missing_or_mixed_headers:" + category)
        return [(index, dict(zip(loop.tags, row))) for index, row in enumerate(loop.rows)]
    if scalars:
        if not set(required).issubset(scalars):
            raise ValueError("missing_headers:" + category)
        return [(0, scalars)]
    raise ValueError("missing_category:" + category)


def _text(row, key):
    value = _value(row[key])
    if value is None or not value or any(c.isspace() for c in value):
        raise ValueError("missing_or_invalid_identity:" + key)
    return value


def _number(row, key, *, optional=False):
    value = _value(row[key]) if key in row else None
    if value is None and optional:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("missing_or_invalid_number:" + key) from exc
    if not math.isfinite(value):
        raise ValueError("nonfinite_number:" + key)
    return value


def _charge(row, key):
    value = _value(row[key]) if key in row else None
    if value is None:
        return None
    if not re.fullmatch(r"[+-]?[0-9]+", value):
        raise ValueError("invalid_formal_charge")
    return int(value)


def observe_mmcif_ligand(*, source: dict, selection: dict) -> dict:
    """Observe one explicit source instance, retaining source order and absence."""
    if (not isinstance(source, dict) or set(source) != {"path", "sha256"}
            or not isinstance(source["path"], str) or not Path(source["path"]).is_absolute()
            or not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])):
        raise ValueError("invalid_source_binding")
    keys = {"entry_id", "label_asym_id", "component_id", "auth_seq_id", "model_number"}
    if (not isinstance(selection, dict) or set(selection) != keys
            or any(not isinstance(v, str) or not v or any(c.isspace() for c in v) for v in selection.values())
            or not re.fullmatch(r"[1-9][0-9]*", selection["model_number"])):
        raise ValueError("explicit_instance_selection_required")
    path = Path(source["path"])
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("source_size_limit")
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("source_hash_or_size_mismatch")
    block = parse_cif_block(raw.decode("ascii"))
    entry = _table(block, "_entry", ["_entry.id"])
    if len(entry) != 1 or _text(entry[0][1], "_entry.id").upper() != selection["entry_id"].upper():
        raise ValueError("entry_identity_mismatch")
    sites = _table(block, "_atom_site", ["_atom_site." + name for name in (
        "id", "type_symbol", "label_atom_id", "label_comp_id", "label_asym_id",
        "label_entity_id", "auth_seq_id", "auth_asym_id", "label_alt_id",
        "pdbx_pdb_model_num", "cartn_x", "cartn_y", "cartn_z")])
    selected = [(n, r) for n, r in sites if all(_value(r[key]) == selection[name] for key, name in (
        ("_atom_site.label_asym_id", "label_asym_id"), ("_atom_site.label_comp_id", "component_id"),
        ("_atom_site.auth_seq_id", "auth_seq_id"), ("_atom_site.pdbx_pdb_model_num", "model_number")))]
    if not 1 <= len(selected) <= MAX_SELECTED_ATOMS:
        raise ValueError("selected_atom_count_outside_scope")
    if any(_value(row["_atom_site.label_alt_id"]) is not None for _, row in selected):
        raise ValueError("alternate_locations_require_explicit_resolution")
    # Identity joins use the source's entity/asym/instance declarations, not names.
    entity_ids = {_text(row, "_atom_site.label_entity_id") for _, row in selected}
    auth_chains = {_text(row, "_atom_site.auth_asym_id") for _, row in selected}
    if len(entity_ids) != 1 or len(auth_chains) != 1:
        raise ValueError("ambiguous_selected_instance")
    entity = next(iter(entity_ids))
    entities = _table(block, "_entity", ["_entity.id", "_entity.type"])
    declarations = [r for _, r in entities if _value(r["_entity.id"]) == entity]
    if len(declarations) != 1 or _text(declarations[0], "_entity.type").lower() != "non-polymer":
        raise ValueError("selected_entity_not_nonpolymer")
    asym = _table(block, "_struct_asym", ["_struct_asym.id", "_struct_asym.entity_id"])
    declarations = [r for _, r in asym if _value(r["_struct_asym.id"]) == selection["label_asym_id"]]
    if len(declarations) != 1 or _text(declarations[0], "_struct_asym.entity_id") != entity:
        raise ValueError("asym_entity_mismatch")
    nonpoly = _table(block, "_pdbx_entity_nonpoly", ["_pdbx_entity_nonpoly.entity_id", "_pdbx_entity_nonpoly.comp_id"])
    declarations = [r for _, r in nonpoly if _value(r["_pdbx_entity_nonpoly.entity_id"]) == entity]
    if len(declarations) != 1 or _text(declarations[0], "_pdbx_entity_nonpoly.comp_id") != selection["component_id"]:
        raise ValueError("nonpolymer_component_mismatch")
    comp = selection["component_id"]
    atom_table = _table(block, "_chem_comp_atom", ["_chem_comp_atom." + k for k in ("comp_id", "atom_id", "type_symbol")])
    dictionary = {}
    for ordinal, row in atom_table:
        if _value(row["_chem_comp_atom.comp_id"]) != comp:
            continue
        name = _text(row, "_chem_comp_atom.atom_id")
        if name in dictionary:
            raise ValueError("duplicate_component_atom")
        dictionary[name] = {"element": canonical_element_symbol(_text(row, "_chem_comp_atom.type_symbol")),
                            "formal_charge": _charge(row, "_chem_comp_atom.charge"), "source_row": ordinal}
    if not dictionary:
        raise ValueError("missing_component_atoms")
    atoms, by_name, serials = [], {}, set()
    for ordinal, row in selected:
        name = _text(row, "_atom_site.label_atom_id")
        serial = _text(row, "_atom_site.id")
        if name in by_name or serial in serials:
            raise ValueError("duplicate_source_atom")
        serials.add(serial)
        element = canonical_element_symbol(_text(row, "_atom_site.type_symbol"))
        if name not in dictionary or dictionary[name]["element"] != element:
            raise ValueError("source_component_atom_mismatch")
        charge = _charge(row, "_atom_site.pdbx_formal_charge")
        if charge is not None and dictionary[name]["formal_charge"] is not None and charge != dictionary[name]["formal_charge"]:
            raise ValueError("source_component_charge_conflict")
        occupancy = _number(row, "_atom_site.occupancy", optional=True)
        if occupancy is not None and not 0 <= occupancy <= 1:
            raise ValueError("occupancy_outside_unit_interval")
        by_name[name] = len(atoms)
        atoms.append({"index": len(atoms), "source_row": ordinal, "source_atom_id": serial,
                      "name": name, "element": element, "coordinate_angstrom": [_number(row, "_atom_site.cartn_" + axis) for axis in "xyz"],
                      "formal_charge": charge, "component_formal_charge": dictionary[name]["formal_charge"],
                      "occupancy": occupancy, "auth_asym_id": next(iter(auth_chains)),
                      "insertion_code": _value(row["_atom_site.pdbx_pdb_ins_code"]) if "_atom_site.pdbx_pdb_ins_code" in row else None})
    if len({atom["insertion_code"] for atom in atoms}) != 1:
        raise ValueError("ambiguous_insertion_code")
    scheme = _table(block, "_pdbx_nonpoly_scheme", ["_pdbx_nonpoly_scheme." + key for key in (
        "asym_id", "entity_id", "mon_id", "pdb_seq_num", "pdb_strand_id", "pdb_ins_code")])
    declared = [r for _, r in scheme if _value(r["_pdbx_nonpoly_scheme.asym_id"]) == selection["label_asym_id"]
                and _value(r["_pdbx_nonpoly_scheme.pdb_seq_num"]) == selection["auth_seq_id"]]
    if len(declared) != 1 or any(_value(declared[0]["_pdbx_nonpoly_scheme." + key]) != value for key, value in (
            ("entity_id", entity), ("mon_id", comp), ("pdb_strand_id", next(iter(auth_chains))),
            ("pdb_ins_code", atoms[0]["insertion_code"]))):
        raise ValueError("nonpolymer_instance_scheme_mismatch")
    missing = [{"name": name, **value} for name, value in dictionary.items() if name not in by_name]
    bonds, absent_bonds, seen = [], [], set()
    bond_table = _table(block, "_chem_comp_bond", ["_chem_comp_bond." + k for k in (
        "comp_id", "atom_id_1", "atom_id_2", "value_order", "pdbx_aromatic_flag", "pdbx_stereo_config")])
    for ordinal, row in bond_table:
        if _value(row["_chem_comp_bond.comp_id"]) != comp:
            continue
        a, b = [_text(row, "_chem_comp_bond.atom_id_" + end) for end in ("1", "2")]
        pair = tuple(sorted((a, b)))
        if a == b or a not in dictionary or b not in dictionary or pair in seen:
            raise ValueError("invalid_or_duplicate_component_bond")
        seen.add(pair)
        code = _text(row, "_chem_comp_bond.value_order").upper()
        flag = _text(row, "_chem_comp_bond.pdbx_aromatic_flag").upper()
        stereo = _text(row, "_chem_comp_bond.pdbx_stereo_config").upper()
        if code not in MMCIF_COMPONENT_BOND_ORDERS or flag not in {"Y", "N"} or stereo not in {"N", "E", "Z"}:
            raise ValueError("unsupported_component_bond_semantics")
        order, aromatic = MMCIF_COMPONENT_BOND_ORDERS[code]
        if (aromatic and flag != "Y") or (stereo != "N" and order != 2.0):
            raise ValueError("conflicting_component_bond_semantics")
        if a not in by_name or b not in by_name:
            absent_bonds.append({"names": [a, b], "source_row": ordinal, "reason": "source_atom_coordinates_absent"})
            continue
        i, j = sorted((by_name[a], by_name[b]))
        bond = Bond(index=len(bonds), atom_i=i, atom_j=j, order=order,
                    aromatic=flag == "Y", stereo="none" if stereo == "N" else stereo.lower(),
                    source="mmcif_chem_comp_bond", metadata={"source_row": ordinal, "source_sha256": source["sha256"]})
        bonds.append(asdict(bond))
    coordinates = torch.tensor([atom["coordinate_angstrom"] for atom in atoms], dtype=torch.float64).unsqueeze(0)
    for bond in bonds:
        bond["distance_angstrom"] = torch.linalg.vector_norm(coordinates[0, bond["atom_i"]] - coordinates[0, bond["atom_j"]]).item()
    try:
        graph = build_compact_radius_graph(coordinates, RadiusGraphConfig(1.0, max_neighbors=64, max_atoms_per_cell=64))
        batch, first, slot = torch.nonzero(graph.upper_mask(), as_tuple=True)
        second = graph.indices[batch, first, slot]
        pairs = [{"atom_i": i, "atom_j": j, "distance_angstrom": d} for i, j, d in zip(
            first.tolist(), second.tolist(), graph.distances[batch, first, slot].tolist())]
        geometry = {"status": "observed", "radius_angstrom": 1.0, "pairs": pairs, "pair_count": len(pairs),
                    "interpretation": "source_distances_only_not_calibrated_clash_test"}
    except NeighborOverflowError as exc:
        geometry = {"status": "unavailable", "radius_angstrom": 1.0, "pairs": None, "pair_count": None,
                    "reason": str(exc), "error_type": type(exc).__name__}
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("source_changed_during_observation")
    missing_h = sum(a["element"] in {"H", "D"} for a in missing)
    return {"schema_version": SCHEMA, "source": dict(source), "selection": dict(selection),
            "source_atom_site_count": len(sites), "selected_atom_site_count": len(atoms),
            "atoms": atoms, "bonds": bonds, "component_atoms_without_source_coordinates": missing,
            "component_bonds_without_source_coordinates": absent_bonds,
            "counts": {"observed_elements": dict(Counter(a["element"] for a in atoms)),
                       "missing_hydrogen_coordinates": missing_h, "missing_heavy_atom_coordinates": len(missing) - missing_h,
                       "missing_atom_site_formal_charges": sum(a["formal_charge"] is None for a in atoms),
                       "missing_component_formal_charges": sum(a["component_formal_charge"] is None for a in atoms),
                       "zero_occupancy_atoms": sum(a["occupancy"] == 0 for a in atoms),
                       "unknown_occupancy_atoms": sum(a["occupancy"] is None for a in atoms)},
            "geometry": geometry, "coordinate_scope": "selected_asymmetric_unit_instance_no_assembly_or_symmetry_transform",
            "partial_charges_e": None, "potential_energy": None, "forces": None,
            "intercomponent_connections_assessed": False, "complete_chemical_topology_claimed": False,
            "physics_blockers": ["partial_charges_and_forcefield_parameters_not_supplied", "chemical_state_not_prepared"],
            "all_atom_prepared": False, "receptor_prepared": False, "assay_state_equivalence_verified": False,
            "training_admitted": False, "scientifically_validated": False, "customer_execution": False}
