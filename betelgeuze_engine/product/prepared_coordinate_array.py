"""Preserve binary64 calculation coordinates in a hash-bound JSON array source."""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import torch

from betelgeuze_engine.product import prepared_coordinate_export as text_export
from betelgeuze_engine.product.prepared_coordinate_derivation import (
    ORIGIN, _canonical_sha256, _component_derivation,
)
from betelgeuze_engine.product.prepared_gromacs_input import (
    _MAX_BYTES, _keys, _read_source, _require, load_prepared_gromacs_components,
)
from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256

SCHEMA = "prepared_gromacs_coordinate_array_v1"
ARRAY_SCHEMA = "prepared_calculation_coordinate_array_v1"
RECORD_SCHEMA = "prepared_coordinate_array_record_v1"
SIDES = ("receptor", "ligand")
METHOD_KEYS = {"tool", "operation", "settings", "evidence", "external_solver_called"}


def load_coordinate_array_components(request):
    """Read explicit calculation coordinates while retaining a legacy parent.

    The array file, not the parent's coordinate text, supplies the new XYZs.
    The parent still supplies identity, atom order, chemistry and parameters.
    This reader neither prepares molecules nor verifies a declared tool run.
    """
    _keys(request, {"schema_version", "parent_input", "coordinate_array",
                    "source_declarations", "coordinate_derivation"}, "coordinate array request")
    _require(request["schema_version"] == SCHEMA, "unsupported coordinate array schema")
    _canonical_sha256(request)
    request = copy.deepcopy(request)
    sources = {}
    raw = _read_source(request["coordinate_array"], "coordinate_array", sources)
    array = json.loads(raw, object_pairs_hook=text_export._object)
    _keys(array, {"schema_version", "coordinate_unit", "numeric_representation", "atom_order",
                  "parent_input_sha256", "parent_system_sha256", "coordinates_angstrom"}, "coordinate array")
    _require(array["schema_version"] == ARRAY_SCHEMA, "unsupported coordinate array payload schema")
    _require(array["coordinate_unit"] == "angstrom", "explicit Angstrom coordinates required")
    _require(array["numeric_representation"] == "binary64", "binary64 coordinate representation required")
    _require(array["atom_order"] == "parent_canonical_atom_index", "parent canonical atom order required")
    _keys(array["parent_system_sha256"], set(SIDES), "parent_system_sha256")
    parent_hash = _canonical_sha256(request["parent_input"])
    _require(array["parent_input_sha256"] == parent_hash, "array parent input SHA-256 mismatch")
    record = request["coordinate_derivation"]
    _keys(record, {"schema_version", "parent_input_sha256", "coordinate_array_sha256",
                   "prepared_state_id", "changed_atom_indices"} | METHOD_KEYS, "coordinate_derivation")
    _require(record["schema_version"] == RECORD_SCHEMA, "unsupported coordinate array record schema")
    _require(record["parent_input_sha256"] == parent_hash, "record parent input SHA-256 mismatch")
    _require(record["coordinate_array_sha256"] == sources["coordinate_array"]["sha256"],
             "coordinate array record SHA-256 mismatch")
    _keys(record["changed_atom_indices"], set(SIDES), "changed_atom_indices")
    _, validated, parent, coordinates, _ = text_export._validated_request({
        "schema_version": text_export.SCHEMA, "parent_input": request["parent_input"],
        "source_declarations": request["source_declarations"], "coordinates_angstrom": array["coordinates_angstrom"],
        "upstream_method": {key: record[key] for key in METHOD_KEYS},
    })
    declarations = validated["source_declarations"]
    _require(record["prepared_state_id"] == declarations["prepared_state_id"], "array prepared state mismatch")
    for side, system in zip(SIDES, parent[:2]):
        _require(array["parent_system_sha256"][side] == canonical_system_sha256(system),
                 f"{side}: array parent system SHA-256 mismatch")
    sources.update({"parent_" + label: ref for label, ref in parent[4]["sources"].items()})
    # Component provenance includes a source-hash list: keep its order stable
    # when a manifest is encoded with sorted JSON keys and read back.
    for label in sorted(record["evidence"]):
        _read_source(record["evidence"][label], "derivation_" + label, sources)
    systems, details = [], {}
    for side, original in zip(SIDES, parent[:2]):
        child = replace(original,
            coordinates=torch.tensor([coordinates[side]], dtype=torch.float64, device="cpu"),
            provenance=replace(original.provenance, metadata={**original.provenance.metadata,
                "calculation_coordinate_source": "coordinate_array",
                "calculation_coordinate_array_sha256": sources["coordinate_array"]["sha256"],
                "calculation_coordinate_representation": "binary64_angstrom_parent_canonical_atom_index"}))
        system, details[side] = _component_derivation(child, original, side, record, sources, declarations)
        systems.append(system)
    _require(any(detail["changed_atom_indices"] for detail in details.values()),
             "coordinate array must contain an observed coordinate change")
    for label, ref in sources.items():
        _read_source(ref, label, {})
    # These observations describe the immutable parent's legacy text files.
    # Do not present the parent's GRO/SDF agreement as a check of the new XYZs.
    parent_observation_keys = {"gro_sdf_max_same_index_coordinate_difference_angstrom",
                              "gro_sdf_coordinate_tolerance_angstrom", "source_gro_box_nm_ignored_for_nonperiodic_cross"}
    provenance = {
        **{key: value for key, value in parent[4].items() if key not in parent_observation_keys},
        "schema_version": SCHEMA, "parent_schema_version": request["parent_input"]["schema_version"],
        "parent_source_relationship": parent[4]["source_relationship"],
        "parent_coordinate_observations": {key: parent[4][key] for key in sorted(parent_observation_keys)},
        "source_relationship": "explicit binary64 coordinate-array child of hash-bound legacy parent; method declared, not execution-verified",
        "source_declarations": copy.deepcopy(declarations), "sources": sources,
        "source_hashes_postflight_verified": True,
        "coordinate_source": {side: "coordinate_array" for side in SIDES},
        "coordinate_representation": "binary64_angstrom_parent_canonical_atom_index",
        "coordinate_origin": ORIGIN, "hydrogen_coordinate_origin": "see_component_coordinate_derivation",
        "coordinate_derivation": details, "coordinate_derivation_record": copy.deepcopy(record),
        "coordinate_derivation_record_sha256": _canonical_sha256(record),
        "coordinates_generated": False, "coordinate_generation_scope": "this_ingestion_only",
        "coordinates_generated_upstream": True, "external_solver_called": False,
        "upstream_external_solver_called_declared": record["external_solver_called"],
        "upstream_tool_execution_verified": False, "noncoordinate_source_bytes_unchanged": True,
        "receptor_system_sha256": canonical_system_sha256(systems[0]),
        "ligand_system_sha256": canonical_system_sha256(systems[1]),
    }
    return systems[0], systems[1], parent[2], parent[3], provenance


def export_prepared_coordinate_array(request, output_dir):
    """Export supplied binary64 Angstrom values without fixed-decimal rounding.

    This alternative writer accepts the same request as the text exporter.
    Inputs are converted to finite Python binary64 numbers before serialization.
    No unit conversion, fitting, solver execution or text-file override occurs.
    """
    input_hash, request, parent, coordinates, method = text_export._validated_request(request)
    changed = {side: [i for i, (old, new) in enumerate(zip(system.coordinates[0].tolist(), coordinates[side]))
                      if old != new] for side, system in zip(SIDES, parent[:2])}
    _require(any(changed.values()), "coordinate array must contain an observed coordinate change")
    parent_hash = _canonical_sha256(request["parent_input"])
    array = {"schema_version": ARRAY_SCHEMA, "coordinate_unit": "angstrom", "numeric_representation": "binary64",
             "atom_order": "parent_canonical_atom_index", "parent_input_sha256": parent_hash,
             "parent_system_sha256": {side: canonical_system_sha256(system) for side, system in zip(SIDES, parent[:2])},
             "coordinates_angstrom": coordinates}
    raw = text_export._json_bytes(array)
    _require(len(raw) <= _MAX_BYTES, "coordinate array exceeds source byte capacity")
    dest = Path(output_dir).resolve()
    dest.mkdir(mode=0o700)
    path = dest / "coordinates.json"
    text_export._write(path, raw)
    source = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
              "source_id": "coordinate-array-export:" + input_hash}
    identity = {"schema_version": "calculation_coordinate_array_export_v1",
                "export_request_sha256": input_hash,
                "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "shared_validation_implementation_sha256": hashlib.sha256(Path(text_export.__file__).read_bytes()).hexdigest(),
                "representation": "binary64_angstrom_parent_canonical_atom_index",
                "unit_conversion_performed": False, "fixed_decimal_rounding_performed": False}
    record = {"schema_version": RECORD_SCHEMA, "parent_input_sha256": parent_hash,
              "coordinate_array_sha256": source["sha256"],
              "prepared_state_id": request["source_declarations"]["prepared_state_id"],
              **{key: method[key] for key in METHOD_KEYS - {"settings"}},
              "settings": {"upstream": method["settings"], "coordinate_array_export": identity},
              "changed_atom_indices": changed}
    prepared = {"schema_version": SCHEMA, "parent_input": request["parent_input"], "coordinate_array": source,
                "source_declarations": request["source_declarations"], "coordinate_derivation": record}
    loaded = load_prepared_gromacs_components(prepared)
    for side, system in zip(SIDES, loaded[:2]):
        expected = torch.tensor([coordinates[side]], dtype=torch.float64)
        _require(torch.equal(system.coordinates.view(torch.int64), expected.view(torch.int64)),
                 f"{side}: binary64 coordinate roundtrip mismatch")
    report = {"schema_version": "prepared_coordinate_array_export_report_v1", "status": "completed",
              "prepared_input": prepared, "coordinate_export": identity,
              "binary64_coordinate_bits_preserved": True, "maximum_roundtrip_component_error_angstrom": 0.0,
              "receptor_system_sha256": loaded[4]["receptor_system_sha256"],
              "ligand_system_sha256": loaded[4]["ligand_system_sha256"],
              "noncoordinate_source_bytes_unchanged": True, "external_solver_called_by_exporter": False,
              "source_files_overwritten": False, "scientifically_validated": False,
              "claim_policy": loaded[4]["claim_policy"]}
    text_export._write(dest / "export-request.json", text_export._json_bytes(request))
    text_export._write(dest / "export-report.json", text_export._json_bytes(report))
    text_export._write(dest / "prepared-input.json", text_export._json_bytes(prepared))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.request.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
        _require(len(raw) <= _MAX_BYTES, "export request exceeds byte capacity")
        result = export_prepared_coordinate_array(json.loads(raw, object_pairs_hook=text_export._object), args.output_dir)
        print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir.resolve()),
                          "scientifically_validated": False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
