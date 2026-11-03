#!/usr/bin/env python3
"""Project one saved prepared-cross geometry; no engine imports or evaluation."""
import argparse
import hashlib
import json
import math
import re
import sys

SOURCE_SCHEMA = "betelgeuze.prepared_v2_cross_interaction/1.0.0"
LIMITS = {"source_bytes": 32 * 1024 * 1024, "json_depth": 64,
          "atoms_per_side": 50_000, "residues_per_side": 10_000,
          "projected_bytes": 2_000_000, "distance_ops": 5_000_000}
HEX = re.compile(r"-?0x[0-9a-f]+\.[0-9a-f]+p[+-][0-9]+\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class ProjectionError(ValueError):
    """Fixed diagnostics that never echo source values or private paths."""


def _fail(code):
    raise ProjectionError(code)


def _obj(value, required=(), exact=False):
    if not isinstance(value, dict) or not set(required) <= value.keys():
        _fail("missing_or_invalid_object")
    if exact and set(value) != set(required):
        _fail("unexpected_object_fields")
    return value


def _text(value, empty=False, maximum=128):
    if (not isinstance(value, str) or len(value) > maximum or (not value and not empty)
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        _fail("invalid_text")
    return value


def _int(value, minimum=0, maximum=50_000):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail("invalid_index_or_integer")
    return value


def _array(value, maximum, nonempty=True):
    if not isinstance(value, list) or len(value) > maximum or (nonempty and not value):
        _fail("invalid_array_or_count")
    return value


def _sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        _fail("invalid_sha256")
    return value


def serialize_json(value):
    """Exact deterministic ASCII JSON bytes, including one terminal LF."""
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("ascii")


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key")
        result[key] = value
    return result


def _constant(_):
    _fail("nonfinite_json_number")


def _float(token):
    value = float(token)
    if not math.isfinite(value):
        _fail("nonfinite_json_number")
    return value


def _parse(raw):
    # Bound depth before decoding into Python containers; ignore quoted brackets.
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > LIMITS["json_depth"]:
                _fail("json_depth_exceeded")
        elif byte in (93, 125):
            depth -= 1
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_float)
    except ProjectionError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        _fail("invalid_json")


def _side(source, role, declarations):
    _obj(source, ("system", "system_sha256", "coordinates_sha256"))
    wrapper = _obj(source["system"], ("schema_id", "system", "system_sha256"))
    if wrapper["schema_id"] != "betelgeuze.engine_v2_canonical_system/1.0.0":
        _fail("unsupported_system_schema")
    declared_hash = _sha(source["system_sha256"])
    if _sha(wrapper["system_sha256"]) != declared_hash:
        _fail("inconsistent_declared_system_hash")
    system = _obj(wrapper["system"], ("topology", "coordinates", "provenance"))
    provenance = _obj(system["provenance"], ("metadata",))
    meta = _obj(provenance["metadata"], ("state_declarations",))
    state = _obj(meta["state_declarations"], ("coordinate_frame_id", "prepared_state_id"))
    for key in ("coordinate_frame_id", "prepared_state_id"):
        if state[key] != declarations[key]:
            _fail("incompatible_frame_or_state")
    topology = _obj(system["topology"], ("schema_id", "coordinate_unit", "cell_periodic",
                     "atoms", "residues", "chains", "system_id", "source"))
    if topology["schema_id"] != "betelgeuze.all_atom_system/2.0.0":
        _fail("unsupported_topology_schema")
    coords = _obj(system["coordinates"], ("coordinate_unit", "cell_periodic", "cell_vectors", "coordinates"))
    if topology["coordinate_unit"] != "angstrom" or coords["coordinate_unit"] != "angstrom":
        _fail("unsupported_coordinate_unit")
    if (topology["cell_periodic"] is not None or topology.get("cell_vectors") is not None
            or coords["cell_periodic"] is not None or coords["cell_vectors"] is not None):
        _fail("periodic_geometry_not_supported")
    atoms = _array(topology["atoms"], LIMITS["atoms_per_side"])
    residues = _array(topology["residues"], LIMITS["residues_per_side"])
    chains = _array(topology["chains"], LIMITS["residues_per_side"])
    tensor = _obj(_obj(coords["coordinates"], ("$tensor",), True)["$tensor"], ("dtype", "shape", "values"), True)
    shape = _array(tensor["shape"], 3)
    if any(type(v) is not int for v in shape) or shape != [1, len(atoms), 3] or tensor["dtype"] != "float64":
        _fail("invalid_tensor_shape_or_dtype")
    values = _array(tensor["values"], 3 * LIMITS["atoms_per_side"])
    if len(values) != 3 * len(atoms):
        _fail("invalid_tensor_value_count")
    xyz = []
    for encoded in values:
        token = _obj(encoded, ("$float_hex",), True)["$float_hex"]
        if not isinstance(token, str) or len(token) > 64 or not HEX.fullmatch(token):
            _fail("invalid_float_hex")
        try:
            value = float.fromhex(token)
        except (ValueError, OverflowError):
            _fail("invalid_float_hex")
        if value.hex() != token:
            _fail("noncanonical_float_hex")
        if not math.isfinite(value) or abs(value) > 1e150:
            _fail("coordinate_out_of_range")
        xyz.append(value)
    atom_groups = [[] for _ in residues]
    output_atoms = []
    for i, atom in enumerate(atoms):
        _obj(atom, ("index", "residue_index", "name", "element"))
        if _int(atom["index"]) != i:
            _fail("unordered_atom_indices")
        ri = _int(atom["residue_index"], maximum=len(residues) - 1)
        _text(atom["name"])
        element = _text(atom["element"])
        atom_groups[ri].append(i)
        out = {"atom_id": f"{role}:atom:{i:05d}", "element": element, "xyz": xyz[3*i:3*i+3]}
        if role == "receptor":
            out["residue_id"] = f"receptor:residue:{ri:05d}"
        output_atoms.append(out)
    chain_groups = [[] for _ in chains]
    output_residues = []
    for i, residue in enumerate(residues):
        _obj(residue, ("index", "chain_index", "name", "sequence_number", "insertion_code", "atom_indices"))
        if _int(residue["index"]) != i:
            _fail("unordered_residue_indices")
        ci = _int(residue["chain_index"], maximum=len(chains) - 1)
        members = _array(residue["atom_indices"], len(atoms))
        if any(type(v) is not int for v in members) or members != atom_groups[i]:
            _fail("inexact_residue_partition")
        chain_groups[ci].append(i)
        chain = _obj(chains[ci], ("chain_id",))
        output_residues.append({"residue_id": f"{role}:residue:{i:05d}",
                                "chain": _text(chain["chain_id"], empty=True),
                                "name": _text(residue["name"]),
                                "resnum": str(_int(residue["sequence_number"], -1_000_000_000, 1_000_000_000)),
                                "icode": _text(residue["insertion_code"], empty=True)})
    for i, chain in enumerate(chains):
        _obj(chain, ("index", "chain_id", "residue_indices"))
        if _int(chain["index"]) != i:
            _fail("unordered_chain_indices")
        _text(chain["chain_id"], empty=True)
        members = _array(chain["residue_indices"], len(residues))
        if any(type(v) is not int for v in members) or members != chain_groups[i]:
            _fail("inexact_chain_partition")
    origin = _obj(topology["source"], ("id", "sha256"))
    # Opaque source identifiers can contain private paths: bind, never echo them.
    identity = {"system_id_sha256": _digest(_text(topology["system_id"], maximum=4096).encode("utf-8")),
                "source_id_sha256": _digest(_text(origin["id"], maximum=4096).encode("utf-8")),
                "declared_source_sha256": _sha(origin["sha256"]),
                "declared_system_sha256": declared_hash,
                "declared_coordinates_sha256": _sha(source["coordinates_sha256"]),
                "atoms": len(atoms), "residues": len(residues), "chains": len(chains)}
    return output_atoms, output_residues, identity


def project_prepared_cross(raw, *, expected_sha256):
    """Return contacts and receipt; byte binding is not authentication.

    Unrelated canonical fields are allowed, not validated as scientific evidence.
    No I/O, E/F, alignment, refinement, validity, selection or trajectory inference.
    """
    if not isinstance(raw, bytes):
        _fail("expected_bytes")
    if len(raw) > LIMITS["source_bytes"]:
        _fail("source_byte_budget_exceeded")
    if _digest(raw) != _sha(expected_sha256):
        _fail("source_sha256_mismatch")
    data = _obj(_parse(raw), ("schema_id", "status", "source_declarations", "sources"))
    if data["schema_id"] != SOURCE_SCHEMA:
        _fail("unsupported_source_schema")
    status = _text(data["status"])
    declarations = _obj(data["source_declarations"], ("coordinate_frame_id", "prepared_state_id"))
    frame = _text(declarations["coordinate_frame_id"])
    state = _text(declarations["prepared_state_id"])
    sources = _obj(data["sources"], ("receptor", "ligand"))
    ra, rr, ri = _side(sources["receptor"], "receptor", declarations)
    la, _, li = _side(sources["ligand"], "ligand", declarations)
    operations = len(ra) * len(la)
    if operations > LIMITS["distance_ops"]:
        _fail("distance_operation_budget_exceeded")
    contacts = {"schema_version": "residue_contacts_input.v1", "coordinate_frame": frame,
                "units": "angstrom", "receptor": {"atoms": ra, "residues": rr},
                "poses": [{"pose_id": state, "coordinate_frame": frame, "atoms": la}], "comparisons": []}
    projected = serialize_json(contacts)
    if len(projected) > LIMITS["projected_bytes"]:
        _fail("projected_byte_budget_exceeded")
    receipt = {"schema_version": "prepared_cross_contacts_receipt.v1",
               "source_sha256": _digest(raw), "source_bytes": len(raw), "source_schema": SOURCE_SCHEMA,
               "declared_status_sha256": _digest(status.encode("utf-8")),
               "declared_saved_state_id_sha256": _digest(state.encode("utf-8")),
               "coordinate_frame_sha256": _digest(frame.encode("utf-8")),
               "source_identity": {"receptor": ri, "ligand": li},
               "projected_sha256": _digest(projected), "projected_bytes": len(projected),
               "projected_schema": contacts["schema_version"], "distance_ops": operations,
               "limits": dict(LIMITS), "scope": "single_saved_geometry_only",
               "unrelated_source_fields_interpreted": False,
               "canonical_system_hashes_recomputed": False,
               "claims": {key: False for key in ("authenticated_evidence", "trajectory", "refinement",
                          "candidate_completeness", "selection", "validity", "scientific_validation",
                          "benchmark_promotion", "gpu_validation", "product_readiness",
                          "customer_readiness", "commercial_readiness")}}
    return contacts, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="saved source JSON; read only")
    parser.add_argument("--expected-sha256", required=True, help="expected exact source-byte digest, not authentication")
    parser.add_argument("--format", choices=("contacts", "receipt"), default="contacts")
    args = parser.parse_args(argv)
    try:
        with open(args.source, "rb") as handle:
            raw = handle.read(LIMITS["source_bytes"] + 1)
        contacts, receipt = project_prepared_cross(raw, expected_sha256=args.expected_sha256)
        sys.stdout.buffer.write(serialize_json(contacts if args.format == "contacts" else receipt))
    except ProjectionError as exc:
        print("projection_error: " + str(exc), file=sys.stderr)
        return 2
    except OSError:
        print("projection_error: io_error", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
