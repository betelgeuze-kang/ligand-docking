"""Hash-bound, explicit prepared-coordinate ingestion for cross interactions only.

This is not a GROMACS preprocessor or a force-field preparation tool. Bonded
tables are retained as source evidence; they are never converted to chemical
bond orders or evaluated. No hydrogen, charge, tautomer or coordinate is made.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import hashlib
import math
from pathlib import Path
import re

import torch

from betelgeuze_engine_v2.io import parse_pdb, parse_sdf_v2000
from betelgeuze_engine_v2.molecular.models import AllAtomSystem, element_for_atomic_number
from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256
from betelgeuze_engine_v2.molecular.validation import require_valid_all_atom_system


SCHEMA_VERSION = "prepared_gromacs_components_v1"
_MAX_BYTES = 16 * 1024 * 1024
_MOLECULE_SECTIONS = {"moleculetype", "atoms", "bonds", "pairs", "angles", "dihedrals"}
_DECLARATIONS = {"coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id"}


class PreparedGromacsInputError(ValueError):
    """The supplied sources cannot establish the bounded ingestion contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PreparedGromacsInputError(message)


def _keys(value: object, expected: set[str], label: str) -> None:
    _require(type(value) is dict and set(value) == expected, f"{label}: exact keys required: {sorted(expected)}")


def _text(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label}: nonblank string required")
    return value


def _number(token: str, label: str) -> float:
    try:
        value = float(token)
    except (ValueError, TypeError) as exc:
        raise PreparedGromacsInputError(f"{label}: numeric value required") from exc
    _require(math.isfinite(value), f"{label}: finite value required")
    return value


def _integer(token: str, label: str, *, minimum: int = 1) -> int:
    _require(bool(re.fullmatch(r"[0-9]+", token)), f"{label}: integer required")
    value = int(token)
    _require(value >= minimum, f"{label}: integer below minimum")
    return value


def _read_source(ref: dict, label: str, sources: dict) -> bytes:
    _keys(ref, {"path", "sha256", "source_id"}, label)
    path = Path(_text(ref["path"], f"{label}.path"))
    _text(ref["source_id"], f"{label}.source_id")
    _require(path.is_absolute() and path.is_file(), f"{label}: absolute regular file required")
    _require(isinstance(ref["sha256"], str) and bool(re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])), f"{label}: lowercase SHA-256 required")
    _require(path.stat().st_size <= _MAX_BYTES, f"{label}: source exceeds byte capacity")
    with path.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    _require(len(raw) <= _MAX_BYTES, f"{label}: source exceeds byte capacity")
    _require(hashlib.sha256(raw).hexdigest() == ref["sha256"], f"{label}: source SHA-256 mismatch")
    sources[label] = dict(ref)
    return raw


def _topology(raw: bytes, label: str, *, role: str) -> dict:
    """Retain complete source text and parse only a small, explicit projection."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreparedGromacsInputError(f"{label}: UTF-8 text required") from exc
    allowed = {"atomtypes"} if role == "atomtypes" else set(_MOLECULE_SECTIONS)
    if role == "defaults":
        allowed |= {"defaults", "atomtypes", "system", "molecules"}
    sections: dict[str, list[dict]] = {}
    directives = []
    current = None
    posres = False
    for line_number, original in enumerate(text.splitlines(), 1):
        line = original.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            if line == "#ifdef POSRES" and role == "molecule" and not posres:
                posres = True
            elif line == "#endif" and posres:
                posres = False
            elif posres and re.fullmatch(r'#include "posre_[A-Za-z0-9_.-]+\.itp"', line):
                pass
            elif role == "defaults" and not posres and line in {
                "#define _FF_AMBER", "#define _FF_AMBER99SBILDN",
                '#include "ffnonbonded.itp"', '#include "ffbonded.itp"', '#include "gbsa.itp"',
            }:
                pass
            else:
                raise PreparedGromacsInputError(f"{label}:{line_number}: unsupported preprocessor directive {line}")
            directives.append({"line": line_number, "text": original, "evaluated": False})
            continue
        _require(not posres, f"{label}:{line_number}: only an inactive POSRES include is supported")
        if line.startswith("*") and current is None and role == "defaults":
            continue  # Published Amber license banner; retained verbatim below.
        match = re.fullmatch(r"\[\s*([a-z_0-9]+)\s*\]", line)
        if match:
            current = match.group(1)
            _require(current in allowed, f"{label}: unsupported active section {current}")
            # Dihedral proper/improper sections may occur separately in GROMACS.
            _require(current not in sections or current == "dihedrals", f"{label}: duplicate section {current}")
            sections.setdefault(current, [])
        else:
            _require(current is not None, f"{label}:{line_number}: data outside a section")
            sections[current].append({"line": line_number, "tokens": line.split(), "raw": original})
    _require(not posres, f"{label}: unterminated POSRES conditional")
    return {"source_text": text, "sections": sections, "directives": directives}


def _defaults(top: dict, label: str) -> dict:
    rows = top["sections"].get("defaults", [])
    _require(len(rows) == 1 and len(rows[0]["tokens"]) == 5, f"{label}: one complete defaults row required")
    nbfunc, rule, gen, lj, qq = rows[0]["tokens"]
    _require(nbfunc == "1" and rule == "2" and gen in {"yes", "no"}, f"{label}: only Lennard-Jones combination rule 2 is supported")
    lj_value, qq_value = _number(lj, label), _number(qq, label)
    _require(lj_value >= 0 and qq_value >= 0, f"{label}: negative pair scaling")
    return {"nbfunc": 1, "combination_rule": 2, "gen_pairs": gen, "fudge_lj": lj_value, "fudge_qq": qq_value, "raw": rows[0]["raw"]}


def _atomtypes(top: dict, label: str) -> dict:
    types = {}
    rows = top["sections"].get("atomtypes", [])
    _require(bool(rows), f"{label}: missing atomtypes")
    for row in rows:
        tokens = row["tokens"]
        _require(len(tokens) in {6, 7}, f"{label}: unsupported atomtype row width")
        name = tokens[0]
        _require(name not in types, f"{label}: duplicate atomtype {name}")
        atomic_number = _integer(tokens[1], label, minimum=0) if len(tokens) == 7 else None
        mass, charge, particle, sigma, epsilon = tokens[-5:]
        mass_value, charge_value = _number(mass, label), _number(charge, label)
        sigma_value, epsilon_value = _number(sigma, label), _number(epsilon, label)
        _require(particle == "A", f"{label}: only ordinary atom particles are supported")
        _require(mass_value >= 0 and sigma_value >= 0 and epsilon_value >= 0, f"{label}: negative mass or Lennard-Jones parameter")
        types[name] = {"atomic_number": atomic_number, "mass_da": mass_value, "default_charge_e": charge_value,
                       "sigma_nm": sigma_value, "epsilon_kj_per_mol": epsilon_value, "sigma_token": sigma,
                       "epsilon_token": epsilon, "source_row": row}
    return types


def _molecule(top: dict, label: str) -> tuple[list[dict], set[tuple[int, int]]]:
    sections = top["sections"]
    molecule_rows = sections.get("moleculetype", [])
    _require(len(molecule_rows) == 1 and len(molecule_rows[0]["tokens"]) == 2, f"{label}: exactly one moleculetype required")
    _integer(molecule_rows[0]["tokens"][1], label, minimum=0)
    atoms = []
    residue_names = {}
    seen_names = set()
    for row in sections.get("atoms", []):
        tokens = row["tokens"]
        _require(len(tokens) == 8, f"{label}: complete non-alchemical atom row required")
        index, atomtype, resnr, residue, name, group, charge, mass = tokens
        index_value = _integer(index, label)
        _require(index_value == len(atoms) + 1, f"{label}: atom indices must be sequential, unique and one based")
        resnr_value = _integer(resnr, label)
        _integer(group, label)
        charge_value, mass_value = _number(charge, label), _number(mass, label)
        _require(mass_value > 0, f"{label}: atom mass must be positive")
        _require(resnr_value not in residue_names or residue_names[resnr_value] == residue, f"{label}: inconsistent residue name")
        _require((resnr_value, name) not in seen_names, f"{label}: duplicate atom name within residue")
        residue_names[resnr_value] = residue
        seen_names.add((resnr_value, name))
        atoms.append({"source_atom_index": index_value, "atomtype": atomtype, "residue_number": resnr_value,
                      "residue_name": residue, "atom_name": name, "charge_e": charge_value,
                      "mass_da": mass_value, "source_row": row})
    _require(bool(atoms), f"{label}: missing atoms")
    adjacency = set()
    for section, arity in (("bonds", 2), ("pairs", 2), ("angles", 3), ("dihedrals", 4)):
        for row in sections.get(section, []):
            tokens = row["tokens"]
            _require(len(tokens) >= arity + 1, f"{label}: malformed {section} row")
            indices = [_integer(token, label) - 1 for token in tokens[:arity]]
            _require(all(index < len(atoms) for index in indices) and len(set(indices)) == arity, f"{label}: invalid {section} atom indices")
            _integer(tokens[arity], label)
            if section == "bonds":
                _require(tokens[arity] == "1", f"{label}: only ordinary harmonic bond adjacency is supported")
                pair = tuple(sorted(indices))
                _require(pair not in adjacency, f"{label}: duplicate bond adjacency")
                adjacency.add(pair)
    return atoms, adjacency


def _gro(raw: bytes, label: str) -> tuple[list[dict], list[float]]:
    lines = raw.decode("utf-8").splitlines()
    _require(len(lines) >= 4, f"{label}: truncated GRO")
    count = _integer(lines[1].strip(), label)
    _require(len(lines) == count + 3, f"{label}: GRO count or trailing records mismatch")
    atoms = []
    for index, line in enumerate(lines[2:-1]):
        _require(len(line) >= 20, f"{label}: short GRO atom record")
        residue_number = _integer(line[:5].strip(), label)
        source_index = _integer(line[15:20].strip(), label)
        _require(source_index == index + 1, f"{label}: sequential GRO atom indices required")
        tokens = line[20:].split()
        _require(len(tokens) == 3, f"{label}: exactly three GRO coordinates, no velocities, required")
        atoms.append({"residue_number": residue_number, "residue_name": _text(line[5:10].strip(), label),
                      "atom_name": _text(line[10:15].strip(), label), "source_atom_index": source_index,
                      "coordinates_angstrom": [_number(value, label) * 10.0 for value in tokens]})
    box = [_number(value, label) for value in lines[-1].split()]
    _require(len(box) in {3, 9}, f"{label}: malformed GRO box")
    return atoms, box


def _sdf_projection(raw: bytes) -> tuple[bytes, dict]:
    """Separate inert SD data fields without changing the original mol block."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    ends = [index for index, line in enumerate(lines) if line.strip() == "M  END"]
    _require(len(ends) == 1, "ligand SDF must contain one mol block")
    end = ends[0]
    fields = {}
    current = None
    closed = False
    for line in lines[end + 1:]:
        value = line.rstrip("\r\n")
        if not value.strip():
            current = None
            continue
        _require(not closed, "ligand SDF content after record terminator")
        if value == "$$$$":
            closed = True
            current = None
        elif value.startswith(">"):
            match = re.fullmatch(r">\s*<([A-Za-z0-9_. -]+)>\s*(?:\(1\)\s*)?", value)
            _require(match is not None, "unsupported ligand SDF data header")
            name = match.group(1)
            _require(bool(name.strip()) and name == name.strip(), "unsupported ligand SDF data header name")
            _require(name not in fields, "duplicate ligand SDF data field")
            fields[name] = []
            current = name
        else:
            _require(current is not None and not value.startswith("M  "), "unbound ligand SDF metadata")
            fields[current].append(value)
    projected = "".join(lines[:end + 1]).encode("utf-8")
    return projected, {"original_sha256": hashlib.sha256(raw).hexdigest(),
                       "mol_block_sha256": hashlib.sha256(projected).hexdigest(),
                       "mol_block_bytes_unchanged": True, "data_fields": fields,
                       "source_data_tail": "".join(lines[end + 1:]),
                       "data_fields_interpreted_as_chemistry": False}


def _pdb_projection(raw: bytes, chains: list[dict], molecules: dict, types: dict, *, policy: str, naming: str) -> tuple[bytes, dict]:
    transfers = []
    lines = raw.decode("utf-8").splitlines(keepends=True)
    if policy == "pdb_blank_element_from_matching_topology_atomic_number":
        indices_by_chain = {}
        for index, line in enumerate(lines):
            if line[:6].strip() in {"ATOM", "HETATM"}:
                indices_by_chain.setdefault(line[21:22].strip(), []).append(index)
        _require(list(indices_by_chain) == [chain["chain_id"] for chain in chains], "PDB projection chain identity/coverage mismatch")
        for chain in chains:
            label = "protein_chain_" + chain["chain_id"]
            atom_rows, _ = molecules[label]
            indices = indices_by_chain[chain["chain_id"]]
            _require(len(indices) == len(atom_rows), f"{label}: PDB projection atom count mismatch")
            for local_index, (line_index, source) in enumerate(zip(indices, atom_rows)):
                line = lines[line_index]
                name = line[12:16].strip()
                _require(source["atomtype"] in types, f"{label}: missing atomtype parameters")
                number = types[source["atomtype"]]["atomic_number"]
                element = element_for_atomic_number(number) if number is not None else ""
                _require(bool(element) and number > 0, f"{label}: explicit ordinary atom number required for PDB projection")
                expected_name = name
                if naming == "pdb_leading_digit_to_gromacs_suffix" and name[:1].isdigit() and element == "H":
                    expected_name = name[1:] + name[0]
                _require(source["atom_name"] == expected_name, f"{label}: PDB projection atom name/order mismatch")
                _require(not line[26:27].strip() and source["residue_name"] == line[17:20].strip()
                         and source["residue_number"] == _integer(line[22:26].strip(), label), f"{label}: PDB projection residue identity mismatch")
                annotation = line[76:78].strip()
                if annotation:
                    _require(annotation == element, f"{label}: nonblank PDB element mismatch")
                else:
                    body = line.rstrip("\r\n")
                    _require(len(body) >= 78, f"{label}: PDB projection requires explicit blank element columns")
                    ending = line[len(body):]
                    lines[line_index] = body[:76] + f"{element:>2s}" + body[78:] + ending
                    transfers.append({"source_line": line_index + 1, "chain_id": chain["chain_id"],
                                      "chain_atom_index": local_index, "source_atom_index": source["source_atom_index"],
                                      "pdb_atom_name": name, "itp_atom_name": source["atom_name"],
                                      "original_element_annotation": annotation, "atomic_number": number,
                                      "transferred_element": element, "atomtype": source["atomtype"],
                                      "element_source": "protein_atomtypes", "molecule_source": label})
    projected = "".join(lines).encode("utf-8")
    return projected, {"policy": policy, "original_sha256": hashlib.sha256(raw).hexdigest(),
                       "projected_sha256": hashlib.sha256(projected).hexdigest(), "transfers": transfers,
                       "element_inferred": False, "transferred_from_explicit_source": bool(transfers),
                       "coordinate_bytes_unchanged": True}


def _bind_atom(atom, source: dict, atomtype: dict, *, label: str, formal_status: str) -> tuple[object, dict]:
    _require(atomtype["atomic_number"] == atom.atomic_number and atom.atomic_number > 0, f"{label}: atom element mismatch")
    _require(abs(source["mass_da"] - atomtype["mass_da"]) <= 0.01, f"{label}: atom mass mismatch (0.01 Da printed-table tolerance)")
    _require(atom.isotope_mass_number is None, f"{label}: isotope-specific masses are outside this input profile")
    evidence = {**source, "atomtype_source": atomtype, "canonical_atom_index": atom.index,
                "canonical_atom_name": atom.name, "formal_charge_annotation_status": formal_status}
    bound = replace(atom, partial_charge_e=source["charge_e"], mass_da=source["mass_da"],
                    metadata={**atom.metadata, "prepared_gromacs_source": evidence})
    parameters = {"atom_index": atom.index, "charge_e": source["charge_e"],
                  "sigma_angstrom": atomtype["sigma_nm"] * 10.0,
                  "epsilon_kcal_per_mol": atomtype["epsilon_kj_per_mol"] / 4.184}
    _require(all(math.isfinite(value) for value in parameters.values()), f"{label}: nonfinite converted parameter")
    return bound, parameters


def _bound_system(system: AllAtomSystem, atoms: list, source_hashes: list[str], declarations: dict) -> AllAtomSystem:
    parent = canonical_system_sha256(system)
    result = replace(system, atoms=tuple(atoms), cell=None,
                     provenance=replace(system.provenance,
                         operations=system.provenance.operations + ("explicit_prepared_gromacs_charge_mass_attachment",),
                         parent_sha256=system.provenance.parent_sha256 + (parent,),
                         chemistry_validated=False, scientifically_validated=False, product_qualified=False,
                         metadata={**system.provenance.metadata, "prepared_source_sha256": source_hashes,
                                   "state_declarations": declarations, "declarations_verified": False,
                                   "hydrogen_coordinate_origin": "published_computational_preparation_not_experimental"}))
    require_valid_all_atom_system(result)
    return result


def load_prepared_gromacs_components(request: dict) -> tuple[AllAtomSystem, AllAtomSystem, list[dict], list[dict], dict]:
    """Return canonical receptor/ligand, explicit per-atom parameters and evidence.

    ``path``/``sha256``/``source_id`` references bind every local source. Sources
    are checked again after parsing. The frame and chemical state are caller
    assertions; this function does no registration or chemical preparation.
    """
    _keys(request, {"schema_version", "protein_pdb", "protein_chains", "protein_atomtypes", "protein_defaults",
                    "ligand_sdf", "ligand_gro", "ligand_itp", "ligand_atomtypes", "ligand_defaults",
                    "ligand_atomtype_name_mapping", "ligand_residue_name_mapping", "naming_convention",
                    "pdb_element_policy", "source_declarations", "source_relationship"}, "request")
    _require(request["schema_version"] == SCHEMA_VERSION, "unsupported prepared GROMACS schema")
    _keys(request["source_declarations"], _DECLARATIONS, "source_declarations")
    for key, value in request["source_declarations"].items():
        _text(value, key)
    _text(request["source_relationship"], "source_relationship")
    _require(_text(request["naming_convention"], "naming_convention") in {"exact", "pdb_leading_digit_to_gromacs_suffix"}, "unsupported naming convention")
    _require(_text(request["pdb_element_policy"], "pdb_element_policy") in {"reject_missing", "pdb_blank_element_from_matching_topology_atomic_number"}, "unsupported PDB element policy")
    _keys(request["ligand_residue_name_mapping"], {"gro", "itp"}, "ligand_residue_name_mapping")
    for value in request["ligand_residue_name_mapping"].values():
        _text(value, "ligand residue name")
    sources = {}
    raw = {key: _read_source(request[key], key, sources) for key in (
        "protein_pdb", "protein_atomtypes", "protein_defaults", "ligand_sdf", "ligand_gro", "ligand_itp", "ligand_atomtypes", "ligand_defaults")}
    tops = {key: _topology(raw[key], key, role=role) for key, role in (
        ("protein_atomtypes", "atomtypes"), ("protein_defaults", "defaults"),
        ("ligand_atomtypes", "atomtypes"), ("ligand_defaults", "defaults"), ("ligand_itp", "molecule"))}
    defaults = {key: _defaults(tops[key], key) for key in ("protein_defaults", "ligand_defaults")}
    rtypes = _atomtypes(tops["protein_atomtypes"], "protein_atomtypes")
    ltypes = _atomtypes(tops["ligand_atomtypes"], "ligand_atomtypes")
    mapping = request["ligand_atomtype_name_mapping"]
    _require(type(mapping) is dict, "ligand atomtype name mapping must be a dictionary")
    missing_number = {name for name, value in ltypes.items() if value["atomic_number"] is None}
    _require(set(mapping) == missing_number, "explicit ligand atomtype mapping must cover exactly types without atomic numbers")
    if missing_number:
        source_types = _atomtypes(tops["ligand_defaults"], "ligand_defaults")
        for source_name in mapping.values():
            _text(source_name, "ligand atomtype mapping value")
        _require(len(set(mapping.values())) == len(mapping), "ligand atomtype mapping must be one to one")
        for name, source_name in mapping.items():
            _require(isinstance(source_name, str) and source_name in source_types, "ligand mapped atomtype absent from original table")
            value, original = ltypes[name], source_types[source_name]
            _require(original["atomic_number"] is not None, "mapped atomtype lacks atomic number")
            _require(abs(value["mass_da"] - original["mass_da"]) <= 0.01, "mapped atomtype mass mismatch")
            for parameter, token in (("sigma_nm", "sigma_token"), ("epsilon_kj_per_mol", "epsilon_token")):
                tolerance = float(Decimal(10) ** Decimal(value[token]).as_tuple().exponent) / 2
                _require(abs(value[parameter] - original[parameter]) <= tolerance + 1e-14, "mapped atomtype parameter exceeds source printing precision")
            value["atomic_number"] = original["atomic_number"]
            value["atomic_number_source"] = {"source": "ligand_defaults", "atomtype": source_name, "original": original}
    chains = request["protein_chains"]
    _require(isinstance(chains, list) and bool(chains), "explicit protein chain molecules required")
    declared_ids, molecules = [], {}
    for chain in chains:
        _keys(chain, {"chain_id", "molecule_itp"}, "protein chain")
        chain_id = _text(chain["chain_id"], "chain_id")
        _require(chain_id not in declared_ids, "duplicate protein chain declaration")
        declared_ids.append(chain_id)
        label = "protein_chain_" + chain_id
        tops[label] = _topology(_read_source(chain["molecule_itp"], label, sources), label, role="molecule")
        molecules[label] = _molecule(tops[label], label)
    pdb_block, pdb_projection = _pdb_projection(raw["protein_pdb"], chains, molecules, rtypes,
        policy=request["pdb_element_policy"], naming=request["naming_convention"])
    receptor = parse_pdb(pdb_block, source_id=request["protein_pdb"]["source_id"], dtype=torch.float64, device="cpu", unit_cell_policy="ignore")
    receptor = replace(receptor, provenance=replace(receptor.provenance,
                        operations=receptor.provenance.operations + ("explicit_pdb_element_source_projection",),
                        parent_sha256=receptor.provenance.parent_sha256 + (pdb_projection["original_sha256"],),
                        metadata={**receptor.provenance.metadata, "pdb_element_projection": pdb_projection}))
    sdf_block, sdf_projection = _sdf_projection(raw["ligand_sdf"])
    ligand = parse_sdf_v2000(sdf_block, source_id=request["ligand_sdf"]["source_id"], dtype=torch.float64, device="cpu")
    ligand = replace(ligand, provenance=replace(ligand.provenance,
                     operations=ligand.provenance.operations + ("unchanged_sdf_mol_block_projection",),
                     parent_sha256=ligand.provenance.parent_sha256 + (sdf_projection["original_sha256"],),
                     metadata={**ligand.provenance.metadata, "sdf_data_field_projection": sdf_projection}))
    _require(receptor.model_count == ligand.model_count == 1, "single prepared coordinate model required")
    _require(declared_ids == [chain.chain_id for chain in receptor.chains], "protein chains must exactly match PDB chain order and coverage")
    ratoms, rparams, receptor_adjacency, name_changes = [], [], [], []
    pdb_lines = raw["protein_pdb"].decode("utf-8").splitlines()
    for chain, canonical_chain in zip(chains, receptor.chains):
        label = "protein_chain_" + chain["chain_id"]
        atom_rows, adjacency = molecules[label]
        atom_indices = [index for residue in canonical_chain.residue_indices for index in receptor.residues[residue].atom_indices]
        _require(len(atom_indices) == len(atom_rows), f"{label}: PDB/topology atom count mismatch")
        for index, source in zip(atom_indices, atom_rows):
            atom = receptor.atoms[index]
            residue = receptor.residues[atom.residue_index]
            _require(not residue.insertion_code and source["residue_number"] == residue.sequence_number and source["residue_name"] == residue.name, f"{label}: residue identity mismatch")
            expected_name = atom.name
            if request["naming_convention"] == "pdb_leading_digit_to_gromacs_suffix" and atom.name[0].isdigit() and atom.element == "H":
                expected_name = atom.name[1:] + atom.name[0]
            _require(source["atom_name"] == expected_name, f"{label}: atom name/order mismatch")
            if expected_name != atom.name:
                name_changes.append({"atom_index": index, "pdb": atom.name, "itp": expected_name})
            _require(source["atomtype"] in rtypes, f"{label}: missing atomtype parameters")
            annotation = pdb_lines[atom.metadata["source_line"] - 1][78:80].strip()
            bound, parameters = _bind_atom(atom, source, rtypes[source["atomtype"]], label=label,
                formal_status="explicit_pdb_annotation" if annotation else "missing_pdb_annotation_canonical_default_zero_not_measurement")
            ratoms.append(bound)
            rparams.append(parameters)
        receptor_adjacency.extend([atom_indices[i], atom_indices[j]] for i, j in sorted(adjacency))
    _require([atom.index for atom in ratoms] == list(range(receptor.atom_count)), "PDB atoms must be contiguous in declared chain/residue order")
    pdb_adjacency = {(bond.atom_i, bond.atom_j) for bond in receptor.bonds}
    _require(not pdb_adjacency or pdb_adjacency == {tuple(pair) for pair in receptor_adjacency}, "PDB explicit bond adjacency differs from topology")
    ligand_rows, ligand_adjacency = _molecule(tops["ligand_itp"], "ligand_itp")
    gro, box = _gro(raw["ligand_gro"], "ligand_gro")
    _require(len(ligand_rows) == len(gro) == ligand.atom_count, "ligand source atom count mismatch")
    _require(ligand_adjacency == {(bond.atom_i, bond.atom_j) for bond in ligand.bonds}, "ligand complete SDF/ITP bond adjacency mismatch")
    latoms, lparams, max_coordinate_difference = [], [], 0.0
    for atom, source, coordinate in zip(ligand.atoms, ligand_rows, gro):
        _require(source["residue_number"] == coordinate["residue_number"] == 1, "ligand must contain exactly one residue numbered one")
        _require(source["residue_name"] == request["ligand_residue_name_mapping"]["itp"] and coordinate["residue_name"] == request["ligand_residue_name_mapping"]["gro"], "ligand residue alias declaration mismatch")
        _require(source["atom_name"] == coordinate["atom_name"], "ligand GRO/ITP atom name/order mismatch")
        _require(bool(re.fullmatch(re.escape(atom.element) + r"[0-9]+", coordinate["atom_name"])), "ligand GRO name element differs from SDF")
        _require(source["atomtype"] in ltypes, "ligand missing atomtype parameters")
        difference = max(abs(a - b) for a, b in zip(ligand.coordinates[0, atom.index].tolist(), coordinate["coordinates_angstrom"]))
        max_coordinate_difference = max(max_coordinate_difference, difference)
        _require(difference <= 0.01 + 1e-12, "ligand same-index GRO/SDF coordinates differ beyond 0.01 angstrom")
        bound, parameters = _bind_atom(atom, source, ltypes[source["atomtype"]], label="ligand", formal_status="sdf_v2000_encoded_formal_charge_not_measurement")
        latoms.append(bound)
        lparams.append(parameters)
    hashes = [source["sha256"] for source in sources.values()]
    receptor = _bound_system(receptor, ratoms, hashes, request["source_declarations"])
    ligand = _bound_system(ligand, latoms, hashes, request["source_declarations"])
    for label, source in sources.items():
        with Path(source["path"]).open("rb") as stream:
            postflight = stream.read(_MAX_BYTES + 1)
        _require(len(postflight) <= _MAX_BYTES and hashlib.sha256(postflight).hexdigest() == source["sha256"], f"{label}: source changed during parsing")
    provenance = {
        "schema_version": SCHEMA_VERSION, "sources": sources, "source_hashes_postflight_verified": True,
        "source_declarations": dict(request["source_declarations"]), "declarations_verified": False,
        "source_relationship": request["source_relationship"], "source_coevality_verified": False,
        "original_topologies": tops, "defaults_by_source": defaults,
        "sdf_data_field_projection": sdf_projection,
        "pdb_element_projection": pdb_projection,
        "calculation_scope": "nonperiodic_receptor_ligand_cross_nonbonded_only",
        "cross_combination_rule": 2, "cross_coulomb_scale": 1.0, "cross_lennard_jones_scale": 1.0,
        "within_molecule_gen_pairs_and_fudge_values_applied": False,
        "coordinate_source": {"receptor": "protein_pdb", "ligand": "ligand_sdf"},
        "coordinate_frame_id": request["source_declarations"]["coordinate_frame_id"],
        "coordinate_registration_performed": False, "source_gro_box_nm_ignored_for_nonperiodic_cross": box,
        "gro_sdf_max_same_index_coordinate_difference_angstrom": max_coordinate_difference,
        "gro_sdf_coordinate_tolerance_angstrom": 0.01, "atomtype_mass_tolerance_da": 0.01,
        "unit_conversion": {"sigma_nm_to_angstrom": 10.0, "epsilon_kj_to_kcal_divisor": 4.184, "source_zero_preserved": True},
        "protein_name_mapping": name_changes, "ligand_residue_name_mapping": dict(request["ligand_residue_name_mapping"]),
        "ligand_atomtype_name_mapping": dict(mapping),
        "receptor_source_bond_adjacency": receptor_adjacency,
        "ligand_source_bond_adjacency": [list(pair) for pair in sorted(ligand_adjacency)],
        "gromacs_bond_order_available": False, "chemical_bond_orders_inferred": False,
        "hydrogen_coordinate_origin": "published_computational_preparation_not_experimental",
        "partial_charge_origin": "published_force_field_parameter_assignment_not_experimental_atomic_charge",
        "prepared_tautomer_policy": "retain_supplied_sdf_state_without_normalization",
        "posres_enabled": False, "coordinates_generated": False,
        "receptor_system_sha256": canonical_system_sha256(receptor), "ligand_system_sha256": canonical_system_sha256(ligand),
        "claim_policy": {"scientifically_validated": False, "validated_for_composition": False,
                         "production_claim_allowed": False, "product_qualified": False},
    }
    return receptor, ligand, rparams, lparams, provenance


__all__ = ["PreparedGromacsInputError", "SCHEMA_VERSION", "load_prepared_gromacs_components"]
