"""Export supplied coordinates with original chemical bytes and explicit rounding."""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path

from betelgeuze_engine.product.prepared_coordinate_derivation import (
    RECORD_SCHEMA, SCHEMA as DERIVED_SCHEMA, _canonical_sha256,
)
from betelgeuze_engine.product.prepared_gromacs_input import (
    INSERTION_CODE_SCHEMA_VERSION, MOLECULE_LIST_SCHEMA_VERSION, SCHEMA_VERSION,
    _DECLARATIONS, _MAX_BYTES, _keys, _read_source, _require, _text, load_prepared_gromacs_components,
)

SCHEMA = "prepared_coordinate_export_request_v1"
FORMATS = {"protein_pdb": (8, 3), "ligand_sdf": (10, 4), "ligand_gro": (15, 10)}


def _coordinates(value, count, label):
    _require(type(value) is list and len(value) == count, f"{label}: exact atom count required")
    result = []
    for row in value:
        _require(type(row) is list and len(row) == 3, f"{label}: XYZ triples required")
        _require(all(type(v) in (int, float) for v in row), f"{label}: numbers, not booleans, required")
        try:
            xyz = [float(v) for v in row]
        except OverflowError as exc:
            raise ValueError(f"{label}: coordinate overflow") from exc
        _require(all(math.isfinite(v) for v in xyz), f"{label}: finite coordinates required")
        result.append(xyz)
    return result


def _field(value, width, precision):
    text = f"{value:{width}.{precision}f}"
    _require(not width or len(text) == width, "coordinate exceeds source field width")
    with localcontext() as context:
        context.prec = 80
        error = abs(Decimal.from_float(value) - Decimal(text))
        _require(error <= Decimal(5).scaleb(-precision-1), "coordinate rounding exceeds printed half-unit")
    return text.encode("ascii"), float(text)


def _render(raw, key, system, coordinates):
    lines = raw.splitlines(keepends=True)
    rendered = []
    for index, xyz in enumerate(coordinates):
        values = [v / 10.0 for v in xyz] if key == "ligand_gro" else xyz
        width, precision = FORMATS[key]
        fields = [_field(v, width, precision) for v in values]
        if key == "protein_pdb":
            line_index = system.atoms[index].metadata["source_line"] - 1
            line = lines[line_index]
            lines[line_index] = line[:30] + b"".join(v[0] for v in fields) + line[54:]
        elif key == "ligand_sdf":
            line_index = index + 4
            lines[line_index] = b"".join(v[0] for v in fields) + lines[line_index][30:]
        else:
            line_index = index + 2
            line = lines[line_index]
            ending = line[len(line.rstrip(b"\r\n")):]
            lines[line_index] = line[:20] + b"".join(v[0] for v in fields) + ending
        rendered.append([v[1] * (10.0 if key == "ligand_gro" else 1.0) for v in fields])
    error = max((abs(a-b) for p, q in zip(coordinates, rendered) for a, b in zip(p, q)), default=0.)
    return b"".join(lines), rendered, error


def _write(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _validated_request(request):
    """Validate shared coordinate-array input before either output format writes."""
    _keys(request, {"schema_version", "parent_input", "source_declarations", "coordinates_angstrom",
                    "upstream_method"}, "coordinate export request")
    _require(request["schema_version"] == SCHEMA, "unsupported coordinate export schema")
    input_hash = _canonical_sha256(request)
    request = copy.deepcopy(request)
    parent_request = request["parent_input"]
    _require(type(parent_request) is dict and parent_request.get("schema_version") in (
        SCHEMA_VERSION, MOLECULE_LIST_SCHEMA_VERSION, INSERTION_CODE_SCHEMA_VERSION),
        "coordinate export requires a legacy parent")
    parent = load_prepared_gromacs_components(parent_request)
    _keys(request["source_declarations"], _DECLARATIONS, "source_declarations")
    for key, value in request["source_declarations"].items():
        _text(value, key)
        same = value == parent_request["source_declarations"][key]
        _require(not same if key == "prepared_state_id" else same,
                 "export requires a new state and unchanged frame/parameter/charge declarations")
    _keys(request["coordinates_angstrom"], {"receptor", "ligand"}, "coordinates_angstrom")
    coordinates = {side: _coordinates(request["coordinates_angstrom"][side], system.atom_count, side)
                   for side, system in zip(("receptor", "ligand"), parent[:2])}
    method = request["upstream_method"]
    _keys(method, {"tool", "operation", "settings", "evidence", "external_solver_called"}, "upstream_method")
    _keys(method["tool"], {"name", "version"}, "upstream tool")
    for key, value in method["tool"].items():
        _text(value, key)
    _text(method["operation"], "upstream operation")
    _require(type(method["settings"]) is dict and bool(method["settings"]), "nonempty upstream settings required")
    _require(type(method["external_solver_called"]) is bool, "upstream solver boolean required")
    _keys(method["evidence"], {"method", "execution", "model"}, "upstream evidence")
    for label, ref in method["evidence"].items():
        _require(bool(_read_source(ref, label, {})), "nonempty upstream evidence required")
    return input_hash, request, parent, coordinates, method


def export_prepared_coordinates(request, output_dir):
    """Write a new output directory and emit its request only after roundtrip checks.

    Coordinates are explicit Angstrom arrays in parent atom order. No rotation,
    fitting, interpolation, normalization, missing-atom generation or solver is
    performed. Existing directories are never overwritten; a failed late check
    can leave diagnostic files without a completed prepared-input manifest.
    """
    input_hash, request, parent, coordinates, method = _validated_request(request)
    parent_request = request["parent_input"]
    rendered, rounded, rounding = {}, {}, {}
    for key, side, system in [("protein_pdb", "receptor", parent[0]),
                               ("ligand_sdf", "ligand", parent[1]),
                               ("ligand_gro", "ligand", parent[1])]:
        raw = _read_source(parent_request[key], key, {})
        rendered[key], rounded[key], rounding[key] = _render(raw, key, system, coordinates[side])
    changed = {
        side: [i for i, (old, new) in enumerate(zip(system.coordinates[0].tolist(), rounded[key])) if old != new]
        for key, side, system in [("protein_pdb", "receptor", parent[0]), ("ligand_sdf", "ligand", parent[1])]
    }
    _require(changed["receptor"] or changed["ligand"], "all requested changes vanished at output precision")
    dest = Path(output_dir).resolve()
    dest.mkdir(mode=0o700)  # Exclusive ownership; never replace an existing export.
    sources = {}
    for key, suffix in [("protein_pdb", "pdb"), ("ligand_sdf", "sdf"), ("ligand_gro", "gro")]:
        path = dest / ("derived." + suffix)
        _write(path, rendered[key])
        sources[key] = {"path": str(path), "sha256": hashlib.sha256(rendered[key]).hexdigest(),
                        "source_id": "coordinate-export:" + input_hash + ":" + key}
    export_identity = {
        "schema_version": "coordinate_source_text_export_v1", "export_request_sha256": input_hash,
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pdb_xyz_decimal_places_angstrom": 3, "sdf_xyz_decimal_places_angstrom": 4,
        "gro_xyz_decimal_places_nm": 10, "maximum_roundtrip_component_error_angstrom": rounding,
        "comparison_indices_use_written_coordinates": True,
    }
    record = {
        "schema_version": RECORD_SCHEMA,
        "parent_input_sha256": _canonical_sha256(parent_request),
        "derived_coordinate_sha256": {key: value["sha256"] for key, value in sources.items()},
        "prepared_state_id": request["source_declarations"]["prepared_state_id"],
        **{key: method[key] for key in ("tool", "operation", "evidence", "external_solver_called")},
        "settings": {"upstream": method["settings"], "coordinate_export": export_identity},
        "changed_atom_indices": changed,
    }
    prepared = {"schema_version": DERIVED_SCHEMA, "parent_input": parent_request,
                "derived_coordinates": sources, "source_declarations": request["source_declarations"],
                "coordinate_derivation": record}
    # The legacy reader retains insertion-ordered source metadata. Validate
    # exactly the sorted JSON representation that will be emitted below.
    prepared = json.loads(_json_bytes(prepared), object_pairs_hook=_object)
    receptor, ligand, _, _, provenance = load_prepared_gromacs_components(prepared)
    _require(receptor.coordinates[0].tolist() == rounded["protein_pdb"], "receptor coordinate roundtrip mismatch")
    _require(ligand.coordinates[0].tolist() == rounded["ligand_sdf"], "ligand coordinate roundtrip mismatch")
    report = {
        "schema_version": "prepared_coordinate_export_report_v1", "status": "completed",
        "export_request_sha256": input_hash, "prepared_input": prepared,
        "coordinate_export": export_identity,
        "receptor_system_sha256": provenance["receptor_system_sha256"],
        "ligand_system_sha256": provenance["ligand_system_sha256"],
        "noncoordinate_source_bytes_unchanged": True, "external_solver_called_by_exporter": False,
        "source_files_overwritten": False, "scientifically_validated": False,
        "claim_policy": provenance["claim_policy"],
    }
    _write(dest / "export-request.json", _json_bytes(request))
    _write(dest / "export-report.json", _json_bytes(report))
    _write(dest / "prepared-input.json", _json_bytes(prepared))
    return report


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate export JSON key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.request.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
        _require(len(raw) <= _MAX_BYTES, "export request exceeds byte capacity")
        request = json.loads(raw, object_pairs_hook=_object)
        result = export_prepared_coordinates(request, args.output_dir)
        print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir.resolve()),
                          "scientifically_validated": False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
