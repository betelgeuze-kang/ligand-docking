"""Independent, preparation-only checks for a source-bound SRO packet.

No preparation builder, product molecular loader, energy evaluator or optimizer
is imported. Stored structures and parameter records are inspected; passing is
not force-model accuracy, source-role admission or a physical validation claim.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


class PreparationVerificationError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise PreparationVerificationError(reason)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key:" + str(key))
        value[key] = item
    return value


def _json(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(PreparationVerificationError("nonfinite_json")))


def _finite(value, label):
    require(not isinstance(value, bool), label + ":boolean_not_numeric")
    number = float(value)
    require(math.isfinite(number), label + ":nonfinite")
    return number


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _reference(path, raw):
    return {"path": str(Path(path).resolve()), "bytes": len(raw), "sha256": _sha(raw)}


def _rows(cif, category):
    fields = {key.split(".", 1)[1].lower(): value if isinstance(value, list) else [value]
              for key, value in cif.items() if key.lower().startswith(category.lower() + ".")}
    require(bool(fields), "missing_cif_category:" + category)
    require(len({len(value) for value in fields.values()}) == 1, "unequal_cif_columns:" + category)
    return [dict(zip(fields, values, strict=True)) for values in zip(*fields.values(), strict=True)]


def parse_source(raw):
    """Read actual CIF rows independently of any generated source-graph document."""
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict

    cif = MMCIF2Dict(io.StringIO(raw.decode("utf-8")))
    atom_sites = _rows(cif, "_atom_site")
    observed = [row for row in atom_sites if row["label_comp_id"] == "SRO"
                and row["label_asym_id"] == "F" and row["pdbx_pdb_model_num"] == "1"]
    require(len(observed) == 13 and all(row["type_symbol"] != "H" for row in observed), "source_sro_heavy_count")
    require(len({row["label_atom_id"] for row in observed}) == 13, "duplicate_source_atom_name")
    require(all(row["auth_asym_id"] == "R" and row["auth_seq_id"] == "501"
                and row["label_entity_id"] == "6" for row in observed), "source_instance_mismatch")
    require(all(row["label_alt_id"] == "." and Decimal(row["occupancy"]) == 1 for row in observed), "source_altloc_or_occupancy")
    require(all(row["pdbx_formal_charge"] == "?" for row in observed), "unexpected_source_formal_charge")
    component_atoms = [row for row in _rows(cif, "_chem_comp_atom") if row["comp_id"] == "SRO"]
    component_bonds = [row for row in _rows(cif, "_chem_comp_bond") if row["comp_id"] == "SRO"]
    require(len(component_atoms) == 25 and len(component_bonds) == 26, "source_component_size")
    atoms = {row["atom_id"]: row for row in component_atoms}
    require(len(atoms) == 25 and all("charge" not in row for row in component_atoms), "source_component_charge_or_duplicate")
    heavy_names = {name for name, row in atoms.items() if row["type_symbol"] != "H"}
    require(heavy_names == {row["label_atom_id"] for row in observed}, "source_template_heavy_mismatch")
    heavy_bonds, hydrogen_parents = {}, {}
    for row in component_bonds:
        first, second = row["atom_id_1"], row["atom_id_2"]
        require(first in atoms and second in atoms and first != second, "invalid_source_bond")
        require(row["value_order"].lower() in {"sing", "doub"}, "unsupported_source_bond_order")
        bond = {"order": 1.0 if row["value_order"].lower() == "sing" else 2.0,
                "aromatic": row["pdbx_aromatic_flag"] == "Y"}
        if first in heavy_names and second in heavy_names:
            key = tuple(sorted((first, second)))
            require(key not in heavy_bonds, "duplicate_source_heavy_bond")
            heavy_bonds[key] = bond
        else:
            hydrogen, parent = (second, first) if first in heavy_names else (first, second)
            require(atoms[hydrogen]["type_symbol"] == "H" and parent in heavy_names
                    and hydrogen not in hydrogen_parents and bond == {"order": 1.0, "aromatic": False},
                    "invalid_source_hydrogen_parent")
            hydrogen_parents[hydrogen] = parent
    require(len(heavy_bonds) == 14 and len(hydrogen_parents) == 12, "source_bond_partition")
    require("HNZ3" not in atoms, "new_hydrogen_already_in_source")
    hydrogen_parents["HNZ3"] = "NZ"
    buffers = _rows(cif, "_em_buffer")
    buffer_ph = [row["ph"] for row in buffers]
    require(buffer_ph == ["7.4"], "deposited_buffer_ph_mismatch")
    return {"observed": observed, "component_atoms": atoms, "component_bonds": component_bonds, "heavy_bonds": heavy_bonds,
            "hydrogen_parents": hydrogen_parents, "atom_sites": atom_sites, "buffer_ph": buffer_ph}


def _decode(value):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$float_hex"}:
        return _finite(float.fromhex(value["$float_hex"]), "canonical_float")
    if set(value) == {"$tensor"}:
        item = value["$tensor"]
        require(item["dtype"] == "float64" and all(type(n) is int and n >= 0 for n in item["shape"]), "canonical_tensor_type")
        array = np.asarray([_decode(x) for x in item["values"]], dtype=np.float64)
        require(array.size == math.prod(item["shape"]) and np.isfinite(array).all(), "canonical_tensor_values")
        return array.reshape(item["shape"])
    return {key: _decode(item) for key, item in value.items()}


def parse_canonical(raw):
    document = _json(raw)
    require(document["schema_id"] == "betelgeuze.engine_v2_canonical_system/1.0.0", "canonical_schema")
    encoded = json.dumps(document["system"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    require(_sha(encoded) == document["system_sha256"], "canonical_system_digest")
    return _decode(document["system"]), document["system_sha256"]


def verify_structure(system, provenance, source):
    """Check the graph, names, source frame and explicit generated-H parents."""
    topology = system["topology"]
    atoms, bonds = topology["atoms"], topology["bonds"]
    coordinates = system["coordinates"]["coordinates"]
    require(topology["coordinate_unit"] == system["coordinates"]["coordinate_unit"] == "angstrom", "coordinate_units")
    require(np.asarray(coordinates).shape == (1, 26, 3) and np.isfinite(coordinates).all(), "canonical_coordinate_shape")
    xyz = np.asarray(coordinates)[0]
    require(len(atoms) == 26 and len(bonds) == 27, "prepared_atom_or_bond_count")
    require([row["index"] for row in atoms] == list(range(26)), "canonical_atom_order")
    names = [row["name"] for row in atoms]
    require(len(set(names)) == 26, "duplicate_prepared_atom_name")
    require(Counter(row["element"] for row in atoms) == {"C": 10, "H": 13, "N": 2, "O": 1}, "prepared_formula")
    expected_atomic = {"C": 6, "H": 1, "N": 7, "O": 8}
    require(all(row["atomic_number"] == expected_atomic[row["element"]] for row in atoms), "atomic_number_mismatch")
    require(all(type(row["formal_charge"]) is int and row["formal_charge"] == (1 if row["name"] == "NZ" else 0)
                for row in atoms), "formal_charge_not_NZ_only_plus_one")
    require(all(_finite(row["mass_da"], "atom.mass") > 0 for row in atoms), "invalid_mass")
    charges = [_finite(row["partial_charge_e"], "atom.partial_charge") for row in atoms]
    require(abs(math.fsum(charges) - 1.0) <= 1e-6, "partial_charge_total_not_plus_one")
    heavy_order = [row["label_atom_id"] for row in source["observed"]]
    require(names[:13] == heavy_order and all(row["element"] != "H" for row in atoms[:13])
            and all(row["element"] == "H" for row in atoms[13:]), "source_heavy_order_mismatch")
    for index, row in enumerate(source["observed"]):
        require(atoms[index]["element"] == row["type_symbol"], "source_heavy_element_mismatch")
        require(all(Decimal(str(xyz[index, axis])) == Decimal(row["cartn_" + dimension])
                    for axis, dimension in enumerate("xyz")), "source_heavy_coordinates_changed")
    by_name = {name: index for index, name in enumerate(names)}
    actual_bonds, adjacency = {}, {index: [] for index in range(26)}
    for index, row in enumerate(bonds):
        i, j = row["atom_i"], row["atom_j"]
        require(row["index"] == index and type(i) is int and type(j) is int and 0 <= i < j < 26,
                "invalid_canonical_bond_index")
        require((i, j) not in actual_bonds and type(row["aromatic"]) is bool, "duplicate_bond_or_untyped_aromaticity")
        actual_bonds[i, j] = {"order": _finite(row["order"], "bond.order"), "aromatic": row["aromatic"]}
        adjacency[i].append(j)
        adjacency[j].append(i)
    expected = {tuple(sorted((by_name[a], by_name[b]))): value for (a, b), value in source["heavy_bonds"].items()}
    for hydrogen, parent in source["hydrogen_parents"].items():
        require(hydrogen in by_name and parent in by_name, "missing_hydrogen_name_or_parent")
        expected[tuple(sorted((by_name[hydrogen], by_name[parent])))] = {"order": 1.0, "aromatic": False}
    require(actual_bonds == expected, "source_graph_or_hydrogen_parent_changed")
    for row in atoms:
        expected_aromatic = source["component_atoms"].get(row["name"], {}).get("pdbx_aromatic_flag") == "Y"
        require(type(row["aromatic"]) is bool and row["aromatic"] == expected_aromatic, "atom_aromaticity_mismatch")
    rows = provenance["atoms"]
    require(len(rows) == 26 and [row["index_zero_based"] for row in rows] == list(range(26)), "provenance_atom_order")
    for index, row in enumerate(rows):
        require(row["name"] == names[index] and row["element"] == atoms[index]["element"]
                and row["formal_charge"] == atoms[index]["formal_charge"]
                and row["aromatic"] is atoms[index]["aromatic"], "provenance_identity_mismatch")
        require(np.array_equal(np.asarray(row["coordinates_angstrom"]), xyz[index]), "provenance_coordinate_mismatch")
        if index < 13:
            original = source["observed"][index]
            require(row["source_atom_site_id"] == original["id"]
                    and row["source_component_atom_name"] == names[index]
                    and row["parent_index_zero_based"] is None and row["parent_name"] is None,
                    "source_atom_provenance_mismatch")
            require(row["origin"] == "observed_source_heavy" and row["hydrogen_method_protocol_key"] is None,
                    "observed_atom_generation_claim")
            require([Decimal(x) for x in row["source_coordinates_decimal"]]
                    == [Decimal(original["cartn_" + dim]) for dim in "xyz"], "source_decimal_provenance_mismatch")
        else:
            parent = source["hydrogen_parents"][names[index]]
            require(row["parent_name"] == parent and row["parent_index_zero_based"] == by_name[parent]
                    and row["source_atom_site_id"] is None and row["source_coordinates_decimal"] is None,
                    "generated_hydrogen_provenance_mismatch")
            expected_name = None if names[index] == "HNZ3" else names[index]
            require(row["source_component_atom_name"] == expected_name, "new_hydrogen_source_claim")
            require(row["origin"] == "generated_hydrogen"
                    and row["hydrogen_method_protocol_key"] == "generated_hydrogens_method", "hydrogen_method_provenance")
            require(all(Decimal(str(value)) % Decimal("0.0001") == 0 for value in xyz[index]), "hydrogen_quantization")
    source_bonds = {tuple(sorted((row["atom_id_1"], row["atom_id_2"]))): row for row in source["component_bonds"]}
    require(len(provenance["bonds"]) == 27, "provenance_bond_count")
    provenance_pairs = set()
    for row in provenance["bonds"]:
        pair = (row["atom_i"], row["atom_j"])
        require(pair in actual_bonds and pair not in provenance_pairs, "provenance_bond_identity")
        provenance_pairs.add(pair)
        require({"order": row["order"], "aromatic": row["aromatic"]} == actual_bonds[pair], "provenance_bond_properties")
        expected_source = source_bonds.get(tuple(sorted((names[pair[0]], names[pair[1]]))))
        recorded = row["source_component_bond"]
        require((None if recorded is None else {key.lower(): value for key, value in recorded.items()}) == expected_source,
                "provenance_source_bond_binding")
    require(sum(atoms[j]["element"] == "H" for j in adjacency[by_name["NZ"]]) == 3
            and sum(atoms[j]["element"] == "H" for j in adjacency[by_name["NE1"]]) == 1
            and sum(atoms[j]["element"] == "H" for j in adjacency[by_name["OH"]]) == 1,
            "functional_group_hydrogen_counts")
    for flag in ("scientifically_validated", "product_qualified"):
        require(system["provenance"][flag] is False, "unsupported_qualification:" + flag)
    return {"atoms": 26, "heavy_atoms_exact": 13, "generated_hydrogens": 13, "heavy_bonds_exact": 14,
            "formal_charge": 1, "partial_charge_sum": math.fsum(charges), "source_heavy_maximum_coordinate_change_angstrom": 0.0}


def verify_receptor(source, csv_raw, pdb_raw):
    rows = list(csv.DictReader(io.StringIO(csv_raw.decode())))
    require(len(rows) == 4376 and len({row["prepared_serial"] for row in rows}) == 4376, "receptor_map_atom_count")
    pdb = {}
    for line in pdb_raw.decode().splitlines():
        if line[:6].strip() in {"ATOM", "HETATM"}:
            serial = line[6:11].strip()
            require(serial not in pdb, "duplicate_receptor_serial")
            pdb[serial] = {"name": line[12:16].strip(), "element": line[76:78].strip(),
                           "xyz": [Decimal(line[begin:end]) for begin, end in ((30, 38), (38, 46), (46, 54))]}
    require(set(pdb) == {row["prepared_serial"] for row in rows}, "receptor_pdb_map_coverage")
    original = {row["id"]: row for row in source["atom_sites"] if row["label_asym_id"] == "E"
                and row["label_entity_id"] == "5" and row["pdbx_pdb_model_num"] == "1" and row["type_symbol"] != "H"}
    observed = [row for row in rows if row["origin"] == "source_observed_heavy"]
    require(len(original) == len(observed) == 2124
            and {row["source_atom_site_id"] for row in observed} == set(original), "receptor_source_coverage")
    for row in rows:
        prepared = pdb[row["prepared_serial"]]
        require(prepared["name"] == row["prepared_atom_name"] and prepared["element"] == row["prepared_element"],
                "receptor_map_pdb_identity")
    for row in observed:
        atom, prepared = original[row["source_atom_site_id"]], pdb[row["prepared_serial"]]
        require(prepared["name"] == atom["label_atom_id"] and prepared["element"] == atom["type_symbol"],
                "receptor_source_identity")
        require(prepared["xyz"] == [Decimal(atom["cartn_" + dim]) for dim in "xyz"], "receptor_source_coordinates_changed")
    return {"prepared_atoms": 4376, "source_heavy_atoms_exact": 2124, "maximum_printed_coordinate_change_angstrom": 0.0}


def verify_coordinate_formats(system, provenance, sdf_raw, gro_raw):
    """Read written atom/bond records directly, without toolkit aromaticity rewriting."""
    atoms, bonds = system["topology"]["atoms"], system["topology"]["bonds"]
    xyz = np.asarray(system["coordinates"]["coordinates"])[0]
    sdf = sdf_raw.decode().splitlines()
    require(len(sdf) > 4 and "V2000" in sdf[3], "sdf_v2000_required")
    n_atoms, n_bonds = int(sdf[3][:3]), int(sdf[3][3:6])
    require((n_atoms, n_bonds) == (26, 27) and sdf.count("$$$$") == 1, "sdf_record_or_graph_count")
    sdf_coordinates, charges = [], [0] * 26
    charge_codes = {0: 0, 1: 3, 2: 2, 3: 1, 5: -1, 6: -2, 7: -3}
    for index, line in enumerate(sdf[4:30]):
        require(line[31:34].strip() == atoms[index]["element"], "sdf_element_order")
        sdf_coordinates.append([Decimal(line[start:end]) for start, end in ((0, 10), (10, 20), (20, 30))])
        code = int(line[36:39])
        require(code in charge_codes, "sdf_radical_or_unknown_charge")
        charges[index] = charge_codes[code]
    written_bonds = {}
    for line in sdf[30:57]:
        i, j, order = int(line[:3]) - 1, int(line[3:6]) - 1, int(line[6:9])
        key = tuple(sorted((i, j)))
        require(0 <= i < 26 and 0 <= j < 26 and i != j and key not in written_bonds and order in (1, 2),
                "sdf_bond_record")
        written_bonds[key] = float(order)
    charge_overrides = set()
    for line in sdf[57:]:
        if line.startswith("M  CHG"):
            values = line.split()
            require(len(values) == 3 + 2 * int(values[2]), "sdf_charge_line")
            for position in range(3, len(values), 2):
                index = int(values[position]) - 1
                require(0 <= index < 26 and index not in charge_overrides, "sdf_duplicate_charge_override")
                charges[index] = int(values[position + 1])
                charge_overrides.add(index)
        elif line.startswith(("M  RAD", "M  ISO")):
            raise PreparationVerificationError("unexpected_sdf_radical_or_isotope")
    require(written_bonds == {(row["atom_i"], row["atom_j"]): row["order"] for row in bonds}, "sdf_bond_order_roundtrip")
    require(charges == [row["formal_charge"] for row in atoms], "sdf_formal_charge_roundtrip")
    require(all(sdf_coordinates[i][axis] == Decimal(str(xyz[i, axis]))
                for i in range(26) for axis in range(3)), "sdf_coordinate_roundtrip")
    gro = gro_raw.decode().splitlines()
    require(int(gro[1].strip()) == 26 and len(gro) == 29, "gro_atom_count")
    names = [row["reader_atom_name"] for row in provenance["atoms"]]
    require(len(set(names)) == 26, "duplicate_reader_atom_name")
    for index, line in enumerate(gro[2:28]):
        require(int(line[:5]) == 1 and line[5:10].strip() == "SRO" and line[10:15].strip() == names[index]
                and int(line[15:20]) == index + 1, "gro_atom_mapping")
        values = line[20:].split()
        require(len(values) == 3, "gro_velocity_or_missing_coordinate")
        require(all(Decimal(value) * 10 == Decimal(str(xyz[index, axis])) for axis, value in enumerate(values)),
                "gro_coordinate_roundtrip")
    require(all(math.isfinite(float(x)) for x in gro[-1].split()), "invalid_gro_box")
    return {"sdf_atoms": 26, "sdf_bonds": 27, "gro_atoms": 26,
            "coordinate_comparison": "exact_decimal_angstrom_after_declared_nm_conversion",
            "sdf_comparison": "written_source_Kekule_orders_and_formal_charges; no_toolkit_resonance_rewrite",
            "gro_scope": "coordinates_and_explicit_index_name_map_only; no_chemical_graph_in_GRO"}


def _itp(raw):
    sections, name = {}, None
    for original in raw.decode().splitlines():
        line = original.split(";", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip().lower()
            require(name not in sections, "duplicate_itp_section:" + name)
            sections[name] = []
        else:
            require(name is not None, "itp_data_without_section")
            sections[name].append(line.split())
    return sections


def verify_parameters(system, provenance, xml_raw, ligand_itp_raw, atomtypes_raw, reader_parameters, particle_parameters=None):
    """Check supported XML records and the explicitly limited reader projection."""
    topology = system["topology"]
    atoms = topology["atoms"]
    root = ET.fromstring(xml_raw)
    require(root.tag == "System", "openmm_xml_system_required")
    particles = root.findall("./Particles/Particle")
    require(len(particles) == 26 and not root.findall("./Constraints/Constraint")
            and not root.findall("./VirtualSites/*"), "unconstrained_26_particle_system_required")
    forces = root.findall("./Forces/Force")
    force_types = [force.attrib.get("type") for force in forces]
    supported = {"HarmonicBondForce", "HarmonicAngleForce", "PeriodicTorsionForce", "NonbondedForce", "CMMotionRemover"}
    require(set(force_types) <= supported and len(force_types) == len(set(force_types))
            and {"HarmonicBondForce", "HarmonicAngleForce", "PeriodicTorsionForce", "NonbondedForce"} <= set(force_types),
            "unsupported_or_missing_force_term")
    by_type = dict(zip(force_types, forces, strict=True))
    nb = by_type["NonbondedForce"]
    require(not nb.findall("./ParticleOffsets/*") and not nb.findall("./ExceptionOffsets/*")
            and not nb.findall("./GlobalParameters/*"), "unsupported_parameter_offsets")
    nb_atoms = nb.findall("./Particles/Particle")
    require(len(nb_atoms) == 26, "nonbonded_particle_count")
    require(abs(math.fsum(_finite(row.attrib["q"], "xml.charge") for row in nb_atoms) - 1.0) <= 1e-6,
            "xml_partial_charge_total")
    for index, (particle, nonbonded) in enumerate(zip(particles, nb_atoms, strict=True)):
        require(abs(_finite(particle.attrib["mass"], "xml.mass") - atoms[index]["mass_da"]) <= 1e-6, "xml_mass_projection")
        require(abs(_finite(nonbonded.attrib["q"], "xml.charge") - atoms[index]["partial_charge_e"]) <= 1e-7,
                "xml_charge_projection")
        require(_finite(nonbonded.attrib["sig"], "xml.sigma") > 0
                and _finite(nonbonded.attrib["eps"], "xml.epsilon") >= 0, "xml_nonbonded_domain")
    chemical_bonds = {(row["atom_i"], row["atom_j"]) for row in topology["bonds"]}
    neighbors = {index: set() for index in range(26)}
    for i, j in chemical_bonds:
        neighbors[i].add(j)
        neighbors[j].add(i)
    xml_bonds = []
    for row in by_type["HarmonicBondForce"].findall("./Bonds/Bond"):
        pair = tuple(sorted((int(row.attrib["p1"]), int(row.attrib["p2"]))))
        require(pair in chemical_bonds and _finite(row.attrib["d"], "xml.bond.length") > 0
                and _finite(row.attrib["k"], "xml.bond.k") >= 0, "xml_bond_graph_or_domain")
        xml_bonds.append(pair)
    require(len(xml_bonds) == len(chemical_bonds) and set(xml_bonds) == chemical_bonds, "xml_bond_coverage")
    angles = by_type["HarmonicAngleForce"].findall("./Angles/Angle")
    angle_ids = []
    for row in angles:
        indices = [int(row.attrib[key]) for key in ("p1", "p2", "p3")]
        require(len(set(indices)) == 3 and all(0 <= i < 26 for i in indices)
                and all(tuple(sorted(pair)) in chemical_bonds for pair in zip(indices, indices[1:])), "xml_angle_graph")
        require(0 < _finite(row.attrib["a"], "xml.angle") <= math.pi and _finite(row.attrib["k"], "xml.angle.k") >= 0,
                "xml_angle_domain")
        angle_ids.append((min(indices[0], indices[2]), indices[1], max(indices[0], indices[2])))
    expected_angles = {(i, center, j) for center, adjacent in neighbors.items() for i, j in itertools.combinations(sorted(adjacent), 2)}
    require(len(angle_ids) == len(expected_angles) and set(angle_ids) == expected_angles, "xml_angle_coverage")
    torsions = by_type["PeriodicTorsionForce"].findall("./Torsions/Torsion")
    for row in torsions:
        indices = [int(row.attrib[key]) for key in ("p1", "p2", "p3", "p4")]
        require(len(set(indices)) == 4 and all(0 <= i < 26 for i in indices), "xml_torsion_indices")
        proper = all(tuple(sorted(pair)) in chemical_bonds for pair in zip(indices, indices[1:]))
        improper = any(set(indices) - {center} <= neighbors[center] for center in indices)
        require(proper or improper, "xml_torsion_graph")
        require(1 <= int(row.attrib["periodicity"]) <= 12, "xml_torsion_periodicity")
        _finite(row.attrib["k"], "xml.signed_torsion.k")
        _finite(row.attrib["phase"], "xml.torsion.phase")
    exception_pairs = set()
    for row in nb.findall("./Exceptions/Exception"):
        pair = tuple(sorted((int(row.attrib["p1"]), int(row.attrib["p2"]))))
        require(0 <= pair[0] < pair[1] < 26 and pair not in exception_pairs, "xml_exception_pair")
        exception_pairs.add(pair)
        _finite(row.attrib["q"], "xml.exception.charge_product")
        require(_finite(row.attrib["sig"], "xml.exception.sigma") >= 0
                and _finite(row.attrib["eps"], "xml.exception.epsilon") >= 0, "xml_exception_domain")
    itp, types = _itp(ligand_itp_raw), _itp(atomtypes_raw)
    require(len(itp.get("atoms", [])) == 26, "itp_atom_count")
    type_rows = {}
    for row in types.get("atomtypes", []):
        require(row[0] not in type_rows, "duplicate_itp_atom_type")
        type_rows[row[0]] = row
    for index, row in enumerate(itp["atoms"]):
        require(len(row) >= 8 and int(row[0]) == index + 1 and row[4] == provenance["atoms"][index]["reader_atom_name"],
                "itp_atom_order_or_name")
        require(abs(_finite(row[6], "itp.charge") - atoms[index]["partial_charge_e"]) <= 1e-7
                and abs(_finite(row[7], "itp.mass") - atoms[index]["mass_da"]) <= 1e-6, "itp_atom_projection")
        require(row[1] in type_rows, "missing_itp_atom_type")
        atom_type = type_rows[row[1]]
        require(abs(_finite(atom_type[-2], "itp.sigma") - float(nb_atoms[index].attrib["sig"])) <= 1e-8
                and abs(_finite(atom_type[-1], "itp.epsilon") - float(nb_atoms[index].attrib["eps"])) <= 1e-8,
                "itp_nonbonded_projection")
    adjacency = [tuple(sorted((int(row[0]) - 1, int(row[1]) - 1))) for row in itp.get("bonds", [])]
    require(len(adjacency) == len(chemical_bonds) and set(adjacency) == chemical_bonds, "itp_bond_adjacency_projection")
    require(isinstance(reader_parameters, dict) and isinstance(reader_parameters.get("ligand"), list)
            and len(reader_parameters["ligand"]) == 26, "reader_parameter_count")
    for index, row in enumerate(reader_parameters["ligand"]):
        require(type(row["atom_index"]) is int and row["atom_index"] == index, "reader_parameter_atom_order")
        require(abs(_finite(row["charge_e"], "reader.charge") - float(nb_atoms[index].attrib["q"])) <= 1e-7,
                "reader_charge_projection")
        require(abs(_finite(row["sigma_angstrom"], "reader.sigma") - 10 * float(nb_atoms[index].attrib["sig"])) <= 1e-9
                and abs(_finite(row["epsilon_kcal_per_mol"], "reader.epsilon") - float(nb_atoms[index].attrib["eps"]) / 4.184) <= 1e-10,
                "reader_nonbonded_unit_projection")
    if particle_parameters is not None:
        require(len(particle_parameters["particles"]) == 26, "particle_parameter_count")
        for index, row in enumerate(particle_parameters["particles"]):
            require(row["atom_index"] == index, "particle_parameter_order")
            for key, expected in (("charge_e", float(nb_atoms[index].attrib["q"])),
                                  ("sigma_nm", float(nb_atoms[index].attrib["sig"])),
                                  ("epsilon_kj_mol", float(nb_atoms[index].attrib["eps"])),
                                  ("mass_da", float(particles[index].attrib["mass"]))):
                require(_finite(row[key], "particle." + key) == expected, "particle_xml_binding:" + key)
    return {"particles": 26, "supported_force_types": force_types, "bonds": len(xml_bonds), "angles": len(angles),
            "periodic_torsions": len(torsions), "exceptions": len(exception_pairs),
            "signed_negative_torsion_terms": sum(float(row.attrib["k"]) < 0 for row in torsions),
            "signed_proper_translation_requires_phase_shift_and_energy_offset": True,
            "partial_charge_absolute_tolerance": 1e-7, "mass_absolute_tolerance_da": 1e-6,
            "itp_scope": "atom_nonbonded_charge_mass_and_bond_adjacency; not_full_bonded_simulation_topology",
            "xml_scope": "source_bound_supported_records_indices_and_domains; no_force_or_energy_agreement_test"}


def verify_forcefield_derivation(original_raw, prepared_raw):
    """Ignore whitespace and commutative unit-factor order, not parameter values."""
    original, prepared = ET.fromstring(original_raw), ET.fromstring(prepared_raw)
    require(len(original.findall("Constraints")) == 1 and prepared.find("Constraints") is None,
            "forcefield_constraint_handler_scope")

    def signature(node, skip_constraints=False):
        attributes = {key: tuple(sorted(value.split(" * "))) if " * " in value else value
                      for key, value in node.attrib.items()}
        return (node.tag, attributes, (node.text or "").strip(),
                [signature(child) for child in node if not (skip_constraints and child.tag == "Constraints")])

    require(signature(original, True) == signature(prepared), "forcefield_changed_beyond_constraints")
    return {"only_constraints_handler_removed": True, "parameter_values_and_smirks_preserved": True,
            "unit_factor_order_normalization": "commutative multiplication only; no numerical tolerance"}


def verify_protocol(protocol, manifest):
    state = protocol["computational_microstate"]
    expected = {"formal_charge_site": "NZ", "formal_charge_e": 1, "formula": "C10H13N2O+",
                "atom_count": 26, "heavy_atom_count": 13, "hydrogen_count": 13,
                "terminal_amine_hydrogen_count": 3, "indole_NH_retained": True, "phenol_OH_retained": True,
                "selection": "single_predeclared_computational_assumption",
                "experimentally_measured_bound_protonation": None, "assay_chemical_state": None}
    require(state == expected and manifest["computational_microstate"] == expected, "computational_microstate_changed")
    source = protocol["source"]
    require(source["deposited_em_buffer_pH"] == "7.4" and source["atom_site_formal_charge_token"] == "?"
            and source["component_atom_charge_column_present"] is False
            and source["pH_determines_observed_microstate"] is False, "source_unknowns_conflated_with_assumption")
    require(manifest["source_deposited_em_buffer_pH"] == "7.4" and manifest["source_bound_protonation_known"] is False
            and manifest["source_assay_chemical_state_known"] is False, "manifest_source_state_claim")
    require(protocol["generated_hydrogens_method"] ==
            "RDKit Chem.AddHs(addCoords=True); no embedding or optimization; quantize H only to 0.0001 angstrom",
            "hydrogen_generation_protocol_changed")
    require(protocol["state_or_pose_selected_using_energy_force_or_score"] is False
            and type(protocol["preparation_force_energy_minimization_evaluations"]) is int
            and protocol["preparation_force_energy_minimization_evaluations"] == manifest["force_energy_minimization_evaluations"] == 0,
            "unexpected_preparation_evaluation_claim")
    require(protocol["coordinate_frame_id"] == manifest["coordinate_frame_id"] == "7XTB_original_cartesian_angstrom_development",
            "source_coordinate_frame_changed")
    authority = protocol["authority"]
    require(set(authority) == {"numerical_development_only", "reserved_source_role_unchanged", "training_admitted",
            "calibration_admitted", "independent_evaluation_admitted", "pose_recovery_admitted", "scientifically_validated",
            "product_qualified", "protected_context_read", "experimental_Ki_used", "independent_pose_recovery_claimed"},
            "authority_fields_missing_or_extra")
    require(authority == manifest["scientific_authority"], "authority_binding_mismatch")
    require(authority["numerical_development_only"] is True and authority["reserved_source_role_unchanged"] is True,
            "development_role_changed")
    for name, value in authority.items():
        if name not in {"numerical_development_only", "reserved_source_role_unchanged"}:
            require(value is False, "unsupported_authority:" + name)
    return {"deposited_em_buffer_pH": "7.4", "bound_ligand_protonation_known": False,
            "computational_microstate": "NZ_plus_one; indole_NH_and_phenol_OH",
            "execution_history_scope": "preparer declarations are bound; this verifier makes no force or model calls"}


def verify_reader_binding(system, reader, provenance):
    require(np.array_equal(system["coordinates"]["coordinates"], reader["coordinates"]["coordinates"]),
            "reader_canonical_coordinate_drift")
    original_atoms, final_atoms = reader["topology"]["atoms"], system["topology"]["atoms"]
    require(len(original_atoms) == len(final_atoms) == 26, "reader_canonical_atom_count")
    for index, (before, after) in enumerate(zip(original_atoms, final_atoms, strict=True)):
        binding = before["metadata"]["prepared_gromacs_source"]
        require(binding["atom_name"] == provenance["atoms"][index]["reader_atom_name"]
                and binding["canonical_atom_name"] == before["name"]
                and binding["canonical_atom_index"] == index and binding["source_atom_index"] == index + 1,
                "reader_alias_binding")
        require(before["name"] == before["element"] + str(index + 1), "sdf_generated_canonical_name")
        for key in ("index", "element", "atomic_number", "formal_charge", "partial_charge_e", "mass_da"):
            require(before[key] == after[key], "reader_canonical_property_drift:" + key)
    before_bonds = {(row["atom_i"], row["atom_j"]): row["order"] for row in reader["topology"]["bonds"]}
    after_bonds = {(row["atom_i"], row["atom_j"]): row["order"] for row in system["topology"]["bonds"]}
    require(before_bonds == after_bonds, "reader_canonical_bond_drift")
    return {"coordinates_and_parameters_unchanged": True, "explicit_atom_aliases_checked": 26,
            "source_names_and_aromatic_flags_checked_separately": True,
            "name_domains": "source names; GRO_ITP element-local counts; SDF-reader element-global indices"}


def verify_packet(prepared: Path, *, repository_root: Path | None = None,
                  readiness_path: Path | None = None):
    """Return a bounded verification receipt without modifying the packet.

    All files actually inspected are hashed before and after checking. Model
    weights are not opened: their named digest remains a preparer declaration.
    """
    prepared = Path(prepared).resolve()
    repository = Path(repository_root).resolve() if repository_root is not None else Path(__file__).resolve().parents[3]
    readiness = Path(readiness_path) if readiness_path is not None else repository / "docs/evidence/7xtb_observed_pose_readiness_v1.json"
    read_files, outputs, inputs, checks = {}, {}, {}, {}
    report = {"schema_id": "independent_sro_preparation_verification/1.0.0", "passed": False, "errors": [],
              "manifest": None, "source_ref": None, "validated_outputs": outputs,
              "validated_input_refs": inputs, "checks": checks,
              "force_evaluations": 0, "energy_evaluations": 0, "optimizer_calls": 0, "model_calls": 0,
              "model_weights_opened": False, "scientifically_validated": False, "source_roles_admitted": False,
              "product_qualified": False, "protected_context_opened": False,
              "verification_scope": "source_graph_coordinate_formats_parameter_records_and_provenance; not_force_agreement_or_physical_accuracy"}

    def read(path, expected=None):
        path = Path(path).resolve(strict=True)
        raw = path.read_bytes()
        ref = _reference(path, raw)
        if expected is not None:
            require(ref["sha256"] == expected["sha256"]
                    and ref["bytes"] == expected.get("bytes", expected.get("byte_count")), "input_or_output_hash_mismatch:" + path.name)
        require(str(path) not in read_files or read_files[str(path)] == ref, "file_changed_during_verification:" + path.name)
        read_files[str(path)] = ref
        return raw, ref

    try:
        _, verifier_ref = read(Path(__file__))
        report["verifier_source"] = verifier_ref
        manifest_raw, report["manifest"] = read(prepared / "manifest.v1.json")
        manifest = _json(manifest_raw)
        require(manifest["schema_id"] == "human_5ht6_sro_numerical_preparation/1.0.0", "manifest_schema")
        require(manifest["status"] == "PREPARED_NUMERICAL_DEVELOPMENT_NOT_SCIENTIFICALLY_QUALIFIED", "manifest_status")
        readiness_raw, inputs["readiness"] = read(readiness)
        pins = _json(readiness_raw)["inputs"]
        require(len(pins) == 9, "readiness_input_pin_count")
        retained = {}
        for name, pin in pins.items():
            path = Path(pin["path"])
            raw, inputs[name] = read(path if path.is_absolute() else repository / path, pin)
            retained[name] = raw
        report["source_ref"] = inputs["source_cif"]
        require(manifest["source"] == inputs["source_cif"], "manifest_source_binding")
        file_bytes = {}
        for name, pin in manifest["files"].items():
            require(Path(name).name == name and name not in (".", ".."), "nonlocal_packet_file")
            path = prepared / name
            require(path.resolve().parent == prepared, "packet_symlink_escape")
            file_bytes[name], outputs[name] = read(path, pin)
        required_files = {"protocol.json", "source-graph.json", "atom-provenance.json", "ligand-canonical.json",
            "ligand-reader-canonical.json", "ligand.sdf", "ligand.gro", "ligand.itp", "atomtypes.itp", "defaults.itp",
            "ligand-unconstrained-openmm-system.xml", "unconstrained-forcefield.offxml", "reader-parameters.json",
            "particle-parameters.json", "runtime-and-parameter-sources.json", "prepared-input.json", "reader-evidence.json"}
        require(required_files <= set(file_bytes), "required_preparation_outputs_missing")
        require(manifest["protocol"] == outputs["protocol.json"], "manifest_protocol_binding")
        protocol = _json(file_bytes["protocol.json"])
        checks["protocol"] = verify_protocol(protocol, manifest)
        source = parse_source(retained["source_cif"])
        copied_source = _json(file_bytes["source-graph.json"])
        require(copied_source["source"] == inputs["source_cif"]
                and copied_source["deposited_em_buffer_pH"] == source["buffer_ph"], "source_graph_pin_or_ph")
        def lower(rows):
            return [{key.lower(): value for key, value in row.items()} for row in rows]

        require(lower(copied_source["observed_atoms"]) == source["observed"]
                and lower(copied_source["component_atoms"]) == list(source["component_atoms"].values())
                and lower(copied_source["component_bonds"]) == source["component_bonds"], "copied_source_graph_mismatch")
        system, system_hash = parse_canonical(file_bytes["ligand-canonical.json"])
        require(system_hash == manifest["ligand_system_sha256"], "manifest_ligand_system_hash")
        provenance = _json(file_bytes["atom-provenance.json"])
        checks["structure"] = verify_structure(system, provenance, source)
        checks["coordinate_formats"] = verify_coordinate_formats(system, provenance, file_bytes["ligand.sdf"], file_bytes["ligand.gro"])
        reader, _ = parse_canonical(file_bytes["ligand-reader-canonical.json"])
        checks["reader_binding"] = verify_reader_binding(system, reader, provenance)
        checks["parameters"] = verify_parameters(system, provenance, file_bytes["ligand-unconstrained-openmm-system.xml"],
            file_bytes["ligand.itp"], file_bytes["atomtypes.itp"], _json(file_bytes["reader-parameters.json"]),
            _json(file_bytes["particle-parameters.json"]))
        checks["receptor_source_frame"] = verify_receptor(source, retained["receptor_projection_atom_map"],
                                                         retained["receptor_projection_coordinates"])
        receptor_refs = manifest["receptor_refs"]
        require(receptor_refs["prepared_manifest"] == inputs["receptor_projection_manifest"]
                and receptor_refs["atom_provenance"] == inputs["receptor_projection_atom_map"], "receptor_existing_pin_mismatch")
        receptor_canonical_raw, inputs["receptor_canonical"] = read(receptor_refs["canonical"]["path"], receptor_refs["canonical"])
        require(inputs["receptor_canonical"]["sha256"] == "2c0970bcaf9e994f382e0f0c0fdacbfd1359bef60a10b879f757b31628658c4c",
                "corrected_receptor_reference_changed")
        receptor, receptor_hash = parse_canonical(receptor_canonical_raw)
        require(receptor_hash == manifest["receptor_system_sha256"] and len(receptor["topology"]["atoms"]) == 4376,
                "receptor_system_binding")
        pdb_xyz = [[float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54))]
                   for line in retained["receptor_projection_coordinates"].decode().splitlines()
                   if line[:6].strip() in {"ATOM", "HETATM"}]
        require(np.array_equal(receptor["coordinates"]["coordinates"][0], np.asarray(pdb_xyz)), "receptor_canonical_frame_changed")
        runtime = _json(file_bytes["runtime-and-parameter-sources.json"])
        parameterization = protocol["parameterization"]
        require(runtime["charge_model"]["sha256"] == parameterization["charge_model_sha256"]
                == "7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee", "declared_charge_model_pin")
        ff_raw, inputs["forcefield"] = read(runtime["forcefield"]["path"], runtime["forcefield"])
        require(inputs["forcefield"]["sha256"] == parameterization["forcefield_sha256"]
                == "1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a", "forcefield_source_pin")
        checks["forcefield_derivation"] = verify_forcefield_derivation(ff_raw, file_bytes["unconstrained-forcefield.offxml"])
        require(runtime["source_experimental_charge_inferred"] is False and runtime["training_or_retraining"] is False
                and runtime["charge_inference_role"] == parameterization["charge_role"], "charge_prediction_role_mismatch")
        report["declared_charge_model_reference_not_reopened"] = runtime["charge_model"]
        checks["parameter_source"] = {"forcefield_bytes_verified": True, "unconstrained_forcefield_bound": True,
            "charge_model_reference_matches_frozen_declaration": True, "charge_model_weights_independently_rehashed": False,
            "charge_inference_reproduced": False, "charges_are_experimental": False}
        for path, expected in tuple(read_files.items()):
            read(path, expected)
        report["all_inspected_file_refs"] = list(read_files.values())
        report["passed"] = True
    except (OSError, ValueError, TypeError, KeyError, IndexError, ArithmeticError, ET.ParseError) as exc:
        report["errors"].append(type(exc).__name__ + ": " + str(exc))
        report["all_inspected_file_refs"] = list(read_files.values())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    result = verify_packet(arguments.prepared)
    if arguments.report is not None:
        with arguments.report.open("x") as stream:
            json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if result["passed"] else 1)
