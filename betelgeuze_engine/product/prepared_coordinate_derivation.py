"""Verify supplied coordinate-only derivations without preparing molecules.

The inline parent and method record expose every source reference to existing
resume/cost binding. Hashes verify consistency, not the truth of a tool claim.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import math

from betelgeuze_engine.product.prepared_gromacs_input import (
    INSERTION_CODE_SCHEMA_VERSION, MOLECULE_LIST_SCHEMA_VERSION, SCHEMA_VERSION,
    PreparedGromacsInputError, _DECLARATIONS, _keys, _read_source, _require, _text,
    load_prepared_gromacs_components,
)
from betelgeuze_engine.product.prepared_validation import require_valid_prepared_system
from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256

SCHEMA = "prepared_gromacs_coordinate_derivation_v1"
RECORD_SCHEMA = "prepared_coordinate_derivation_record_v1"
ORIGIN = "locally_derived_computational_coordinates_not_experimental"
COORDINATE_KEYS = {"protein_pdb", "ligand_sdf", "ligand_gro"}


def _canonical_sha256(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise PreparedGromacsInputError("derivation requires finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _coordinate_projection(raw, key):
    """Mask only supported coordinate fields, retaining all other source bytes."""
    lines = raw.splitlines(keepends=True)
    if key == "protein_pdb":
        return b"".join(line[:30] + b"<xyz>" + line[54:]
                        if line.startswith((b"ATOM  ", b"HETATM")) else line for line in lines)
    if key == "ligand_sdf":
        count = int(lines[3][:3])
        return b"".join(b"<xyz>" + line[30:] if 4 <= index < 4 + count else line
                        for index, line in enumerate(lines))
    count = int(lines[1])
    return b"".join(line[:20] + b"<xyz>" + line[len(line.rstrip(b"\r\n")):]
                    if 2 <= index < 2 + count else line for index, line in enumerate(lines))


def _component_derivation(system, parent, side, record, sources, declarations):
    changed = (system.coordinates != parent.coordinates).any(dim=2)[0].nonzero().flatten().tolist()
    indices = record["changed_atom_indices"][side]
    _require(type(indices) is list and all(type(i) is int for i in indices)
             and indices == sorted(set(indices)) and indices == changed,
             f"{side}: declared changed atom indices must exactly match observed coordinates")
    hydrogens = {atom.index for atom in system.atoms if atom.atomic_number == 1}
    changed_hydrogens = sorted(set(changed) & hydrogens)
    if not hydrogens:
        hydrogen_origin = "no_hydrogen_atoms"
    elif not changed_hydrogens:
        hydrogen_origin = parent.provenance.metadata["hydrogen_coordinate_origin"]
    elif len(changed_hydrogens) == len(hydrogens):
        hydrogen_origin = ORIGIN
    else:
        hydrogen_origin = "mixed_parent_and_locally_derived_coordinates_not_experimental"
    maximum = max((math.dist(system.coordinates[0, i].tolist(), parent.coordinates[0, i].tolist())
                   for i in changed), default=0.0)
    _require(math.isfinite(maximum), "nonfinite derived coordinate displacement")
    parent_hash = canonical_system_sha256(parent)
    detail = {
        "coordinate_origin": ORIGIN, "parent_system_sha256": parent_hash,
        "parent_input_sha256": record["parent_input_sha256"],
        "derivation_record_sha256": _canonical_sha256(record),
        "changed_atom_indices": changed, "changed_hydrogen_atom_indices": changed_hydrogens,
        "changed_heavy_atom_indices": sorted(set(changed) - hydrogens),
        "maximum_displacement_angstrom": maximum,
        "hydrogen_coordinate_origin": hydrogen_origin,
        "noncoordinate_source_bytes_unchanged": True,
        "upstream_tool_execution_verified": False,
    }
    result = replace(system, provenance=replace(
        system.provenance,
        operations=system.provenance.operations + ("verified_supplied_coordinate_only_derivation",),
        parent_sha256=system.provenance.parent_sha256 + (parent_hash,),
        chemistry_validated=False, scientifically_validated=False, product_qualified=False,
        metadata={**system.provenance.metadata,
                  "prepared_source_sha256": [ref["sha256"] for ref in sources.values()],
                  "state_declarations": copy.deepcopy(declarations),
                  "coordinate_origin": ORIGIN, "hydrogen_coordinate_origin": hydrogen_origin,
                  "coordinate_derivation": detail,
                  "coordinate_derivation_record": copy.deepcopy(record)},
    ))
    require_valid_prepared_system(result)
    return result, detail


def load_derived_prepared_gromacs_components(request):
    """Bind a legacy parent, coordinate-only child and declared method evidence.

    Parent v1/v2/v3 semantics stay unchanged. Derivation chains, topology edits,
    registration, new atoms and altered charge/chemical-state assignments are
    unsupported. No command from the method record is ever executed.
    """
    _keys(request, {"schema_version", "parent_input", "derived_coordinates",
                    "source_declarations", "coordinate_derivation"}, "derived request")
    _require(request["schema_version"] == SCHEMA, "unsupported coordinate derivation schema")
    _canonical_sha256(request)
    request = copy.deepcopy(request)
    parent_request = request["parent_input"]
    _require(type(parent_request) is dict and parent_request.get("schema_version") in (
        SCHEMA_VERSION, MOLECULE_LIST_SCHEMA_VERSION, INSERTION_CODE_SCHEMA_VERSION),
        "coordinate derivation requires a legacy v1/v2/v3 parent; nested derivations unsupported")
    _keys(request["derived_coordinates"], COORDINATE_KEYS, "derived_coordinates")
    _keys(request["source_declarations"], _DECLARATIONS, "source_declarations")
    _keys(parent_request.get("source_declarations"), _DECLARATIONS, "parent source_declarations")
    for key, value in request["source_declarations"].items():
        _text(value, key)
        same = value == parent_request["source_declarations"][key]
        _require(not same if key == "prepared_state_id" else same,
                 "derived state needs a new prepared_state_id and unchanged frame/parameter/charge declarations")
    record = request["coordinate_derivation"]
    _keys(record, {"schema_version", "parent_input_sha256", "derived_coordinate_sha256",
                   "prepared_state_id", "tool", "operation", "settings", "evidence",
                   "changed_atom_indices", "external_solver_called"}, "coordinate_derivation")
    _require(record["schema_version"] == RECORD_SCHEMA, "unsupported derivation record schema")
    _require(record["parent_input_sha256"] == _canonical_sha256(parent_request),
             "derivation parent input SHA-256 mismatch")
    _keys(record["derived_coordinate_sha256"], COORDINATE_KEYS, "derived_coordinate_sha256")
    _require(record["prepared_state_id"] == request["source_declarations"]["prepared_state_id"],
             "derivation prepared state mismatch")
    _keys(record["tool"], {"name", "version"}, "derivation tool")
    for key, value in record["tool"].items():
        _text(value, "derivation tool " + key)
    _text(record["operation"], "derivation operation")
    _require(type(record["settings"]) is dict and bool(record["settings"]),
             "explicit nonempty derivation settings required")
    _require(type(record["external_solver_called"]) is bool, "explicit upstream solver boolean required")
    _keys(record["evidence"], {"method", "execution", "model"}, "derivation evidence")
    _keys(record["changed_atom_indices"], {"receptor", "ligand"}, "changed_atom_indices")
    sources = {}
    for key, ref in record["evidence"].items():
        raw = _read_source(ref, "derivation_" + key, sources)
        _require(bool(raw), "empty derivation evidence")
    original_raw, derived_raw = {}, {}
    for key in sorted(COORDINATE_KEYS):
        original_raw[key] = _read_source(parent_request[key], "parent_" + key, sources)
        derived_raw[key] = _read_source(request["derived_coordinates"][key], key, sources)
        _require(record["derived_coordinate_sha256"][key] == sources[key]["sha256"],
                 f"{key}: derivation output SHA-256 mismatch")

    parent = load_prepared_gromacs_components(parent_request)
    child_request = {**parent_request, **request["derived_coordinates"],
                     "source_declarations": request["source_declarations"]}
    child = load_prepared_gromacs_components(child_request)
    for key in COORDINATE_KEYS:
        _require(_coordinate_projection(original_raw[key], key) == _coordinate_projection(derived_raw[key], key),
                 f"{key}: coordinate derivation changed noncoordinate source bytes")
    _require(parent[2:4] == child[2:4], "coordinate derivation changed atom parameters")
    for label, ref in parent[4]["sources"].items():
        sources["parent_" + label] = ref
    sources.update(child[4]["sources"])
    receptor, rdetail = _component_derivation(child[0], parent[0], "receptor", record,
                                             sources, request["source_declarations"])
    ligand, ldetail = _component_derivation(child[1], parent[1], "ligand", record,
                                           sources, request["source_declarations"])
    _require(rdetail["changed_atom_indices"] or ldetail["changed_atom_indices"],
             "coordinate derivation must contain an observed coordinate change")
    # Includes parent topologies and opaque method/model evidence. Reused poses
    # check this same complete source map; journals also see all inline refs.
    for label, ref in sources.items():
        _read_source(ref, label, {})
    provenance = {
        **child[4], "schema_version": SCHEMA,
        "parent_schema_version": parent_request["schema_version"],
        "parent_source_relationship": parent[4]["source_relationship"],
        "source_relationship": "coordinate-only child of the hash-bound parent; upstream method is declared, not execution-verified",
        "sources": sources, "source_hashes_postflight_verified": True,
        "coordinate_origin": ORIGIN,
        "hydrogen_coordinate_origin": "see_component_coordinate_derivation",
        "coordinate_derivation": {"receptor": rdetail, "ligand": ldetail},
        "coordinate_derivation_record": copy.deepcopy(record),
        "coordinate_derivation_record_sha256": _canonical_sha256(record),
        "coordinates_generated": False, "coordinate_generation_scope": "this_ingestion_only",
        "coordinates_generated_upstream": True, "external_solver_called": False,
        "upstream_external_solver_called_declared": record["external_solver_called"],
        "upstream_tool_execution_verified": False,
        "noncoordinate_source_bytes_unchanged": True,
        "receptor_system_sha256": canonical_system_sha256(receptor),
        "ligand_system_sha256": canonical_system_sha256(ligand),
    }
    return receptor, ligand, child[2], child[3], provenance


__all__ = ["SCHEMA", "RECORD_SCHEMA", "load_derived_prepared_gromacs_components"]
