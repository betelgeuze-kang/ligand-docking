"""Explicit compiled GROMACS particle sources for the existing cross kernel.

Chemical bond orders and formal charges are unavailable in this input profile.
Canonical containers are source particle projections, not validated chemical
topologies. Complete source connectivity and omitted environments are retained.
No preprocessor, preparation program, external solver or learned model runs.
"""
from __future__ import annotations

import hashlib
import re

import torch

from betelgeuze_engine.product.prepared_gromacs_input import (
    _atomtypes, _bind_atom, _defaults, _gro, _integer, _keys, _molecule,
    _number, _read_source, _require, _text, _topology,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Chain, Residue, StructureProvenance,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.molecular.models import element_for_atomic_number

SCHEMA = "compiled_gromacs_cross_particles_v1"
_GLOBAL = {"defaults", "atomtypes", "system", "molecules"}
_MOLECULE = {"moleculetype", "atoms", "bonds", "pairs", "angles", "dihedrals"}


def _compiled(raw: bytes, selected: set[str]):
    """Partition source text; ignored environment conditionals are never run."""
    globals_, molecules = {}, {}
    owner, section, name, conditional, seen_else = globals_, None, None, False, False
    for line_no, original in enumerate(raw.decode("utf-8").splitlines(), 1):
        line = original.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            _require(name is not None and name not in selected, "conditional in selected molecule or global parameters")
            if line == "#ifndef FLEXIBLE" and not conditional:
                conditional, seen_else = True, False
            elif line == "#else" and conditional and not seen_else:
                seen_else = True
            elif line == "#endif" and conditional:
                conditional = False
            else:
                raise ValueError("unsupported compiled topology directive")
            continue
        match = re.fullmatch(r"\[\s*([a-z_0-9]+)\s*\]", line)
        if match:
            section = match[1]
            _require(not conditional or section not in _GLOBAL | {"moleculetype", "atoms"},
                     "conditional changes source particle inventory")
            if section in _GLOBAL:
                owner, name = globals_, None
            elif section == "moleculetype":
                _require(not conditional, "unterminated environment conditional")
                owner, name = None, None
            else:
                _require(owner is not globals_ and owner is not None, "section outside a molecule")
            continue
        tokens = line.split()
        row = {"line": line_no, "tokens": tokens, "raw": original}
        if section == "moleculetype":
            _require(owner is None and len(tokens) == 2, "one molecule header required")
            name = _text(tokens[0], "molecule name")
            _integer(tokens[1], "nrexcl", minimum=0)
            _require(name not in molecules, "duplicate molecule definition")
            owner = molecules[name] = {"moleculetype": [row]}
        else:
            _require(owner is not None and section is not None, "data outside a section")
            owner.setdefault(section, []).append(row)
    _require(not conditional, "unterminated environment conditional")
    _require(set(globals_) == _GLOBAL, "complete standalone global sections required")
    return globals_, molecules


def _projection(molecule, omitted, types):
    atoms = molecule.get("atoms", [])
    _require(bool(atoms), "missing molecule atoms")
    _require([_integer(r["tokens"][0], "atom index") for r in atoms] == list(range(1, len(atoms)+1)),
             "source atom indices must be contiguous")
    _require(type(omitted) is list and all(type(i) is int for i in omitted), "explicit integer omission list required")
    _require(omitted == list(range(len(atoms)-len(omitted)+1, len(atoms)+1)), "only explicit trailing inert sites supported")
    _require(len(omitted) < len(atoms), "empty physical particle selection")
    for index in omitted:
        t = atoms[index-1]["tokens"]
        _require(len(t) == 8 and t[1] in types, "invalid omitted site")
        typ = types[t[1]]["tokens"]
        _require(len(typ) == 7 and typ[4] == "D", "omitted site must be an explicit dummy particle")
        _require(all(_number(v, "inert site parameter") == 0 for v in [t[6], t[7], typ[2], typ[3], typ[6]]),
                 "omitted site must have zero mass, charge and epsilon")
        _require(_number(typ[5], "inert site sigma") >= 0, "invalid inert site sigma")
    virtual = molecule.get("virtual_sites2", [])
    _require(len(virtual) == len(omitted), "every omitted site needs one explicit virtual_sites2 definition")
    _require(sorted(_integer(r["tokens"][0], "virtual site") for r in virtual) == omitted, "virtual site inventory mismatch")
    for row in virtual:
        t = row["tokens"]
        _require(len(t) == 5 and t[3] == "1", "only declared two-parent virtual sites supported")
        _require(all(1 <= _integer(v, "virtual parent") <= len(atoms)-len(omitted) for v in t[1:3]), "invalid virtual parent")
        _number(t[4], "virtual coefficient")
    _require(set(molecule) <= _MOLECULE | {"virtual_sites2"}, "unsupported selected molecule section")
    physical = len(atoms)-len(omitted)
    parts = []
    for section, rows in molecule.items():
        if section == "virtual_sites2":
            continue
        selected_rows = rows[:physical] if section == "atoms" else rows
        parts.extend(["[ " + section + " ]", *(r["raw"] for r in selected_rows)])
    projected = _topology("\n".join(parts).encode(), "selected particle projection", role="molecule")
    rows, adjacency = _molecule(projected, "selected particle projection")
    return rows, adjacency


def _state(side, name, rows, adjacency, gro, offset, types, sources):
    atoms, parameters, residues, coordinates = [], [], [], []
    groups = {}
    for index, source in enumerate(rows):
        key = (source["residue_number"], source["residue_name"])
        if key not in groups:
            groups[key] = []
        _require(key == next(reversed(groups)), "noncontiguous residue identity")
        residue_index = len(groups)-1
        groups[key].append(index)
        typ = types[source["atomtype"]]
        atom = Atom(index, source["atom_name"], element_for_atomic_number(typ["atomic_number"]),
                    typ["atomic_number"], residue_index, serial=offset+index+1,
                    metadata={"source_global_atom_index_1based": offset+index+1,
                              "formal_charge_observation": None, "chemical_bond_order_available": False})
        bound, parameter = _bind_atom(atom, source, typ, label=side,
            formal_status="unavailable_canonical_default_not_an_observation")
        atoms.append(bound)
        parameters.append(parameter)
        coordinates.append(gro[offset+index]["coordinates_angstrom"])
    for index, ((number, residue_name), indices) in enumerate(groups.items()):
        residues.append(Residue(index, residue_name, 0, number, tuple(indices), entity_type="unknown"))
    state = AllAtomSystem(
        system_id="compiled-cross-particle-projection:" + side + ":" + name,
        atoms=tuple(atoms), bonds=(), residues=tuple(residues),
        chains=(Chain(0, name, tuple(range(len(residues)))),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64, device="cpu"),
        provenance=StructureProvenance(source_format="mathematical_projection", source_id=name,
            parser_name=SCHEMA, parser_version="1", parent_sha256=tuple(s["sha256"] for s in sources.values())),
        metadata={"is_prepared_molecular_state": False, "chemical_topology_verified": False,
                  "canonical_chain_is_source_molecule_group": True, "biopolymer_chain_identity_available": False,
                  "source_bond_adjacency": [list(pair) for pair in sorted(adjacency)]})
    require_valid_all_atom_system(state)
    return state, parameters


def load_compiled_gromacs_cross_particles(request):
    _keys(request, {"schema_version", "topology", "coordinates", "selected_molecules", "excluded_molecules",
                    "omitted_inert_sites", "source_declarations", "source_relationship"}, "compiled request")
    _require(request["schema_version"] == SCHEMA, "unsupported compiled cross profile")
    _keys(request["selected_molecules"], {"receptor", "ligand"}, "selected molecules")
    _keys(request["omitted_inert_sites"], {"receptor", "ligand"}, "omitted inert sites")
    names = [_text(request["selected_molecules"][s], s) for s in ("receptor", "ligand")]
    _require(len(set(names)) == 2, "receptor and ligand must be distinct molecules")
    _keys(request["source_declarations"], {"coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id"}, "source declarations")
    for key, value in request["source_declarations"].items():
        _text(value, key)
    _text(request["source_relationship"], "source relationship")
    sources = {}
    raw = {k: _read_source(request[k], k, sources) for k in ("topology", "coordinates")}
    globals_, molecules = _compiled(raw["topology"], set(names))
    gro, box = _gro(raw["coordinates"], "compiled coordinates")
    _require(len(gro) <= 99999, "wrapped GRO serials are outside this profile")
    defaults = _defaults({"sections": globals_}, "compiled defaults")
    types = {}
    for row in globals_["atomtypes"]:
        t = row["tokens"]
        _require(len(t) == 7 and t[0] not in types, "explicit atomic numbers and unique atomtypes required")
        _require(all(_number(t[i], "source atomtype parameter") >= 0 for i in (2, 5, 6)), "negative source atomtype parameter")
        _number(t[3], "source atomtype default charge")
        types[t[0]] = row
    _require(type(request["excluded_molecules"]) is dict, "explicit excluded molecule counts required")
    roster, offset, seen = [], 0, set()
    positions = {}
    excluded = {}
    for record in globals_["molecules"]:
        t = record["tokens"]
        _require(len(t) == 2 and t[0] in molecules and t[0] not in seen, "unique declared molecule roster required")
        name, count = t[0], _integer(t[1], "molecule count")
        seen.add(name)
        atoms = molecules[name].get("atoms", [])
        _require(bool(atoms), "missing source molecule atoms")
        _require([_integer(a["tokens"][0], "atom index") for a in atoms] == list(range(1, len(atoms)+1)), "invalid molecule atom ordering")
        _require(offset+count*len(atoms) <= len(gro), "topology exceeds coordinate count")
        positions[name] = offset
        for copy in range(count):
            forward_residues, reverse_residues = {}, {}
            for index, atom in enumerate(atoms):
                a = atom["tokens"]
                _require(len(a) == 8 and a[1] in types, "invalid source atom row or missing atomtype")
                _number(a[6], "source atom charge")
                _require(_number(a[7], "source atom mass") >= 0, "negative source atom mass")
                g = gro[offset+copy*len(atoms)+index]
                _require((g["atom_name"], g["residue_name"]) == (a[4], a[3]), "source coordinate/topology name or order mismatch")
                local_residue = _integer(a[2], "source residue")
                gro_residue = g["residue_number"]
                _require(forward_residues.get(local_residue, gro_residue) == gro_residue
                         and reverse_residues.get(gro_residue, local_residue) == local_residue,
                         "source coordinate/topology residue partition mismatch")
                forward_residues[local_residue] = gro_residue
                reverse_residues[gro_residue] = local_residue
        roster.append({"molecule": name, "copies": count, "sites_per_copy": len(atoms),
                       "global_start_1based": offset+1, "global_end_1based": offset+count*len(atoms),
                       "selected": name in names})
        if name in names:
            _require(count == 1, "selected molecule must have exactly one copy")
        else:
            excluded[name] = count
        offset += count*len(atoms)
    _require(offset == len(gro) and set(names) <= seen, "coordinate count or selected molecule coverage mismatch")
    _require(all(type(v) is int for v in request["excluded_molecules"].values()) and request["excluded_molecules"] == excluded,
             "excluded molecule inventory must exactly match declaration")
    states, parameters, adjacencies = {}, {}, {}
    for side, name in zip(("receptor", "ligand"), names):
        rows, adjacency = _projection(molecules[name], request["omitted_inert_sites"][side], types)
        _require(len(rows) <= (10000 if side == "receptor" else 256), "selected particle count exceeds cross profile capacity")
        used = {row["atomtype"] for row in rows}
        selected_types = _atomtypes({"sections": {"atomtypes": [types[k] for k in sorted(used)]}}, side)
        states[side], parameters[side] = _state(side, name, rows, adjacency, gro, positions[name], selected_types, sources)
        adjacencies[side] = [list(pair) for pair in sorted(adjacency)]
    for key in sources:
        _require(_read_source(request[key], key, {}) == raw[key], "compiled source changed during parsing")
    count = sum(s.atom_count for s in states.values())
    provenance = {
        "schema_version": SCHEMA, "sources": sources, "source_hashes_postflight_verified": True,
        "source_declarations": request["source_declarations"], "declarations_verified": False,
        "source_relationship": request["source_relationship"], "source_coevality_verified": False,
        "source_topology_text": raw["topology"].decode(), "molecule_roster": roster,
        "omitted_inert_sites": request["omitted_inert_sites"], "excluded_molecules": excluded,
        "site_accounting": {"requested_source_sites": len(gro), "selected_physical_sites": count, "omitted_source_sites": len(gro)-count},
        "receptor_source_bond_adjacency": adjacencies["receptor"], "ligand_source_bond_adjacency": adjacencies["ligand"],
        "defaults": defaults, "source_box_nm_ignored_for_nonperiodic_cross": box,
        "calculation_scope": "nonperiodic_source_particle_cross_nonbonded_only",
        "hydrogen_coordinate_origin": "supplied_computational_preparation_not_experimental",
        "partial_charge_origin": "supplied_force_field_assignment_not_experimental",
        "chemical_bond_orders_available": False, "formal_charge_observations_available": False,
        "chemical_state_identity_verified": False, "eligible_for_same_state_assay_join": False,
        "coordinates_generated": False, "external_solver_called": False,
        "source_full_simulation_hamiltonian_reproduced": False,
        "source_topology_sha256": hashlib.sha256(raw["topology"]).hexdigest()}
    return states["receptor"], states["ligand"], parameters["receptor"], parameters["ligand"], provenance
