"""Development-only pair geometry in a source-verified receptor coordinate frame.

Reads original hash-bound coordinates, rederives the public anchor and verifies
the observed receptor atom mapping. It makes no placements, scorer/force calls,
role assignments or native candidate admission. A geometry pass never grants
comparison or assay-state readiness.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import time

import numpy as np

from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json

PROTOCOL = "registered_pair_geometry_development_protocol_v1"
RESULT = "registered_pair_geometry_development_result_v1"
MAX_BYTES = 20 * 1024 * 1024
POLICY = {"schema_version": "registered_pair_severe_geometry_screen_v1",
          "minimum_all_atom_distance_angstrom": 1.0,
          "minimum_heavy_atom_distance_angstrom": 2.0,
          "minimum_all_atom_radius_sum_ratio": 0.60,
          "minimum_heavy_atom_radius_sum_ratio": 0.72,
          "maximum_ligand_heavy_anchor_radius_angstrom": 10.0,
          "radius_table_angstrom": {"C": 1.7, "Cl": 1.75, "H": 1.2, "N": 1.55, "O": 1.52, "S": 1.8}}
ORIGINS = {"computational_registered", "isolated_ligand_no_receptor_pose"}
MAP_FIELDS = {"prepared_serial", "prepared_chain", "prepared_residue_number",
              "prepared_residue_name", "prepared_atom_name", "prepared_element",
              "origin", "source_atom_site_id"}


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _fields(value, fields):
    _require(type(value) is dict and set(value) == set(fields), "exact_geometry_fields_required")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read(ref):
    _fields(ref, {"path", "sha256"})
    _require(type(ref["path"]) is str and Path(ref["path"]).is_absolute()
             and str(Path(ref["path"]).resolve()) == ref["path"], "canonical_absolute_input_path_required")
    _require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64
             and set(ref["sha256"]) <= set("0123456789abcdef"), "input_sha256_required")
    fd = os.open(ref["path"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES, "bounded_regular_input_required")
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "input_changed_during_read")
    _require(len(raw) <= MAX_BYTES and hashlib.sha256(raw).hexdigest() == ref["sha256"], "input_hash_mismatch")
    return raw


def _system(raw, maximum):
    system = all_atom_system_from_canonical_json(raw)
    _require(system.model_count == 1 and 1 <= system.atom_count <= maximum
             and system.cell is None, "bounded_single_nonperiodic_system_required")
    xyz = system.coordinates[0].detach().cpu().numpy()
    _require(xyz.dtype == np.float64 and np.isfinite(xyz).all(), "finite_binary64_coordinates_required")
    return xyz, [a.element for a in system.atoms], [a.name for a in system.atoms], system


def _ligand(entry):
    _fields(entry, {"kind", "file"})
    raw = _read(entry["file"])
    if entry["kind"] == "canonical_all_atom_system":
        return (*_system(raw, 256)[:3], raw)
    _require(entry["kind"] == "sdf_v2000", "supported_coordinate_format_required")
    from rdkit import Chem
    text = raw.decode("ascii")
    _require(text.count("$$$$") == 1 and len(text.splitlines()) > 4
             and "V2000" in text.splitlines()[3], "single_V2000_record_required")
    molecule = Chem.MolFromMolBlock(text.split("$$$$")[0], sanitize=False,
                                   removeHs=False, strictParsing=True)
    _require(molecule is not None and 1 <= molecule.GetNumAtoms() <= 256
             and molecule.GetNumConformers() == 1, "bounded_sdf_coordinates_required")
    xyz = np.asarray(molecule.GetConformer().GetPositions(), dtype=np.float64)
    _require(np.isfinite(xyz).all(), "finite_sdf_coordinates_required")
    return xyz, [a.GetSymbol() for a in molecule.GetAtoms()], [f"atom-{i}" for i in range(len(xyz))], raw


def _source_rows(raw):
    result = {}
    block = parse_cif_block(raw.decode("ascii"))
    for loop in block.loops:
        if "_atom_site" not in loop.categories:
            continue
        for tokens in loop.rows:
            row = {key: token.value for key, token in zip(loop.tags, tokens)}
            key = row["_atom_site.id"]
            _require(key not in result, "duplicate_source_atom_site_id")
            result[key] = row
    _require(result, "source_atom_site_rows_required")
    return result


def _xyz(row):
    value = [float(row["_atom_site.cartn_" + axis]) for axis in "xyz"]
    _require(all(math.isfinite(v) for v in value), "finite_source_coordinates_required")
    return value


def _anchor(rows, selector):
    _fields(selector, {"model", "label_asym_id", "label_comp_id", "auth_seq_id", "heavy_atom_count"})
    _require(type(selector["model"]) is int and selector["model"] >= 1
             and type(selector["heavy_atom_count"]) is int and 1 <= selector["heavy_atom_count"] <= 256,
             "bounded_anchor_selection_required")
    selected = [row for row in rows.values() if all(row[key] == str(value) for key, value in (
        ("_atom_site.pdbx_pdb_model_num", selector["model"]),
        ("_atom_site.label_asym_id", selector["label_asym_id"]),
        ("_atom_site.label_comp_id", selector["label_comp_id"]),
        ("_atom_site.auth_seq_id", selector["auth_seq_id"])))]
    _require(len(selected) == selector["heavy_atom_count"]
             and all(row["_atom_site.type_symbol"] != "H" for row in selected), "complete_heavy_anchor_required")
    names = [row["_atom_site.label_atom_id"] for row in selected]
    _require(len(set(names)) == len(names), "unique_anchor_atom_names_required")
    points = np.array([_xyz(row) for row in selected], dtype=np.float64)
    return points.mean(axis=0), {name: {"coordinates": point, "element": row["_atom_site.type_symbol"]}
                                    for name, point, row in zip(names, points, selected)}, [row["_atom_site.id"] for row in selected]


def _receptor_mapping(system, xyz, raw, source_rows, selector):
    _fields(selector, {"model", "label_asym_id"})
    _require(type(selector["model"]) is int and selector["model"] >= 1
             and type(selector["label_asym_id"]) is str and selector["label_asym_id"].strip(),
             "source_receptor_selection_required")
    expected_source = {source_id for source_id, row in source_rows.items()
                       if row["_atom_site.pdbx_pdb_model_num"] == str(selector["model"])
                       and row["_atom_site.label_asym_id"] == selector["label_asym_id"]
                       and row["_atom_site.type_symbol"] != "H"}
    _require(expected_source, "observed_source_receptor_heavy_atoms_required")
    mapping = list(csv.DictReader(io.StringIO(raw.decode("ascii"))))
    _require(len(mapping) == system.atom_count and all(set(row) == MAP_FIELDS for row in mapping),
             "complete_receptor_atom_mapping_required")
    serials, observed, generated, modelled, seen_source = [], 0, 0, 0, set()
    for index, (row, atom) in enumerate(zip(mapping, system.atoms)):
        serials.append(int(row["prepared_serial"]))
        residue = system.residues[atom.residue_index]
        chain = system.chains[residue.chain_index]
        _require(row["prepared_atom_name"] == atom.name and row["prepared_element"] == atom.element
                 and row["prepared_residue_name"] == residue.name
                 and row["prepared_residue_number"] == str(residue.sequence_number)
                 and row["prepared_chain"] == chain.chain_id, "receptor_mapping_identity_or_order_mismatch")
        origin, source_id = row["origin"], row["source_atom_site_id"]
        if origin == "source_observed_heavy":
            _require(source_id in source_rows and source_id not in seen_source and atom.element != "H",
                     "one_to_one_observed_receptor_map_required")
            actual = source_rows[source_id]
            _require(actual["_atom_site.label_atom_id"] == atom.name
                     and actual["_atom_site.type_symbol"] == atom.element
                     and actual["_atom_site.pdbx_pdb_model_num"] == str(selector["model"])
                     and actual["_atom_site.label_asym_id"] == selector["label_asym_id"],
                     "receptor_source_identity_mismatch")
            _require(np.array_equal(xyz[index], _xyz(actual)), "observed_receptor_source_coordinates_changed")
            seen_source.add(source_id)
            observed += 1
        else:
            _require(source_id == "", "modelled_atom_has_source_observation_claim")
            if origin == "openmm_generated_hydrogen":
                _require(atom.element == "H", "generated_hydrogen_element_mismatch")
                generated += 1
            else:
                _require(origin == "explicitly_modelled_heavy" and atom.element != "H",
                         "unsupported_receptor_atom_origin")
                modelled += 1
    _require(seen_source == expected_source, "complete_observed_source_receptor_heavy_map_required")
    _require(serials == sorted(set(serials)), "ordered_unique_receptor_mapping_required")
    return {"observed_heavy_coordinate_matches": observed, "selected_source_heavy_atom_count": len(expected_source),
            "all_selected_source_heavy_atoms_mapped_once": True, "generated_hydrogens": generated,
            "explicitly_modelled_heavy_atoms": modelled, "prepared_atoms": len(mapping),
            "all_observed_receptor_coordinates_exactly_preserved": True,
            "modelled_coordinates_physical_accuracy_verified": False}


def _metrics(xyz, elements, receptor, receptor_elements, center):
    heavy_l = np.array([e != "H" for e in elements])
    heavy_r = np.array([e != "H" for e in receptor_elements])
    _require(heavy_l.any() and heavy_r.any(), "heavy_atoms_required")
    distances = np.linalg.norm(xyz[:, None, :] - receptor[None, :, :], axis=2)
    all_min = float(distances.min())
    heavy_min = float(distances[np.ix_(heavy_l, heavy_r)].min())
    radius = float(np.linalg.norm(xyz[heavy_l] - center, axis=1).max())
    radii = POLICY["radius_table_angstrom"]
    _require(all(element in radii for element in (*elements, *receptor_elements)), "fixed_geometry_radius_table_element_required")
    sums = np.array([radii[e] for e in elements])[:, None] + np.array([radii[e] for e in receptor_elements])[None, :]
    ratios = distances / sums
    all_ratio = float(ratios.min())
    heavy_ratio = float(ratios[np.ix_(heavy_l, heavy_r)].min())
    checks = {"all_atom_severe_overlap_screen": all_min >= POLICY["minimum_all_atom_distance_angstrom"],
              "heavy_atom_severe_overlap_screen": heavy_min >= POLICY["minimum_heavy_atom_distance_angstrom"],
              "all_atom_radius_sum_screen": all_ratio >= POLICY["minimum_all_atom_radius_sum_ratio"],
              "heavy_atom_radius_sum_screen": heavy_ratio >= POLICY["minimum_heavy_atom_radius_sum_ratio"],
              "all_heavy_atoms_inside_anchor_radius": radius <= POLICY["maximum_ligand_heavy_anchor_radius_angstrom"]}
    return {"atom_count": len(xyz), "heavy_atom_count": int(heavy_l.sum()),
            "minimum_all_atom_receptor_distance_angstrom": all_min,
            "minimum_heavy_atom_receptor_distance_angstrom": heavy_min,
            "minimum_all_atom_radius_sum_ratio": all_ratio,
            "minimum_heavy_atom_radius_sum_ratio": heavy_ratio,
            "maximum_heavy_atom_anchor_radius_angstrom": radius,
            "checks": checks, "geometry_screen_passed": all(checks.values())}


def _decode_coordinates(value, count):
    _require(type(value) is list and len(value) == count
             and all(type(row) is list and len(row) == 3 for row in value), "retained_coordinate_shape_mismatch")
    result = []
    for row in value:
        decoded = []
        for token in row:
            _require(type(token) is str and len(token) <= 32, "retained_binary64_hex_required")
            number = float.fromhex(token)
            _require(math.isfinite(number) and number.hex() == token, "canonical_finite_retained_coordinates_required")
            decoded.append(number)
        result.append(decoded)
    return np.asarray(result, dtype=np.float64)


def _seal(value, field):
    _require(type(value) is dict and value.get(field) == _sha({k: v for k, v in value.items() if k != field}),
             "retained_result_seal_mismatch")


def _control(control, protocol, receptor, receptor_elements, center, anchor):
    _fields(control, {"control_id", "input", "retained_request", "retained_result"})
    _require(control["control_id"] == "SRO_initial_source_heavy_geometry", "supported_positive_control_required")
    xyz, elements, names, _ = _ligand(control["input"])
    heavy = [i for i, element in enumerate(elements) if element != "H"]
    _require(len(heavy) == len(anchor) and set(names[i] for i in heavy) == set(anchor),
             "complete_control_source_heavy_atom_map_required")
    _require(all(elements[i] == anchor[names[i]]["element"]
                 and np.array_equal(xyz[i], anchor[names[i]]["coordinates"]) for i in heavy), "initial_control_source_coordinates_changed")
    request = json.loads(_read(control["retained_request"]))
    saved = json.loads(_read(control["retained_result"]))
    _seal(saved, "result_sha256")
    _seal(saved["binding"], "receipt_sha256")
    _require(request.get("schema_id") == "cpu_cartesian_registered_pose_request/1.3.0"
             and saved.get("schema_id") == "cpu_cartesian_registered_pose_result/1.3.0"
             and saved.get("execution_complete") is True
             and request["receptor"] == protocol["receptor"]
             and request["ligand"] == control["input"]["file"]
             and saved["binding"]["request_sha256"] == _sha(request), "control_request_or_receptor_binding_mismatch")
    numerical = saved["numerical_result"]
    _seal(numerical, "result_sha256")
    state = numerical["checkpoint"]["state"]
    original = _decode_coordinates(state["original_coordinates"], len(xyz))
    _require(np.array_equal(original, xyz), "control_original_coordinates_mismatch")
    final = _decode_coordinates(state["current"]["coordinates"], len(xyz))
    _require(saved["attempt"]["post_coordinates_binary64_hex"] == state["current"]["coordinates"],
             "control_attempt_numerical_geometry_mismatch")
    displacement = np.linalg.norm(final[heavy] - xyz[heavy], axis=1)
    return {"control_id": control["control_id"], "initial_geometry": _metrics(xyz, elements, receptor, receptor_elements, center),
            "initial_observed_heavy_coordinate_matches": len(heavy),
            "initial_direct_source_heavy_rmsd_angstrom": 0.0,
            "retained_final_direct_source_heavy_rmsd_angstrom": float(np.sqrt(np.mean(displacement**2))),
            "retained_final_maximum_source_heavy_displacement_angstrom": float(displacement.max()),
            "alignment_or_pose_generation_performed": False,
            "retained_snapshot_checked_not_numerical_trace_replayed": True,
            "independent_pose_recovery_admitted": False, "candidate_pair_membership": False,
            "assayed_microstate_equivalence_verified": False, "source_role_assigned": None,
            "physical_accuracy_or_pose_performance_verified": False}


def evaluate(protocol):
    started = time.perf_counter()
    _fields(protocol, {"schema_version", "source_cif", "receptor", "receptor_atom_mapping",
                       "receptor_source_selection", "anchor_selection", "coordinate_frame_id", "geometry_policy_reference", "candidates", "controls"})
    _require(protocol["schema_version"] == PROTOCOL, "explicit_development_geometry_protocol_required")
    _require(type(protocol["coordinate_frame_id"]) is str and protocol["coordinate_frame_id"].strip(), "coordinate_frame_required")
    _require(type(protocol["candidates"]) is list and len(protocol["candidates"]) == 2
             and type(protocol["controls"]) is list and len(protocol["controls"]) <= 1, "exact_two_candidate_development_pair_required")
    original_policy = json.loads(_read(protocol["geometry_policy_reference"]))
    for original_key, current_key in (
            ("all_atom_minimum_distance_angstrom", "minimum_all_atom_distance_angstrom"),
            ("heavy_atom_minimum_distance_angstrom", "minimum_heavy_atom_distance_angstrom"),
            ("all_atom_minimum_radius_sum_ratio", "minimum_all_atom_radius_sum_ratio"),
            ("heavy_atom_minimum_radius_sum_ratio", "minimum_heavy_atom_radius_sum_ratio"),
            ("pocket_all_heavy_maximum_radius_angstrom", "maximum_ligand_heavy_anchor_radius_angstrom"),
            ("radius_table_angstrom", "radius_table_angstrom")):
        _require(original_policy.get(original_key) == POLICY[current_key], "geometry_protocol_criteria_changed_or_weakened")
    source = _source_rows(_read(protocol["source_cif"]))
    center, anchor, anchor_ids = _anchor(source, protocol["anchor_selection"])
    receptor, receptor_elements, _, system = _system(_read(protocol["receptor"]), 8192)
    mapping = _receptor_mapping(system, receptor, _read(protocol["receptor_atom_mapping"]), source,
                                protocol["receptor_source_selection"])
    observations, ids = [], set()
    for candidate in protocol["candidates"]:
        _fields(candidate, {"candidate_id", "input", "declared_coordinate_frame_id", "coordinate_origin",
                            "source_role", "assay_microstate_verified", "observed_candidate_reference_pose"})
        cid = candidate["candidate_id"]
        _require(type(cid) is str and cid.strip() and cid not in ids, "unique_candidate_identity_required")
        ids.add(cid)
        _require(candidate["source_role"] is None and candidate["assay_microstate_verified"] is False
                 and candidate["observed_candidate_reference_pose"] is False
                 and candidate["coordinate_origin"] in ORIGINS, "development_authority_promotion_forbidden")
        xyz, elements, _, _ = _ligand(candidate["input"])
        metrics = _metrics(xyz, elements, receptor, receptor_elements, center)
        frame = candidate["declared_coordinate_frame_id"] == protocol["coordinate_frame_id"]
        blockers = []
        if not frame:
            blockers.append("declared_coordinate_frame_mismatch")
        if not metrics["geometry_screen_passed"]:
            blockers.append("initial_pose_geometry_not_registered_in_receptor_pocket")
        if candidate["coordinate_origin"] != "computational_registered":
            blockers.append("coordinate_origin_has_no_receptor_registration")
        observations.append({"candidate_id": cid, "input": candidate["input"], "coordinate_origin": candidate["coordinate_origin"],
                             "declared_frame_matches": frame, "metrics": metrics, "geometry_blockers": blockers,
                             "source_role": None, "assay_microstate_verified": False,
                             "observed_candidate_reference_pose": False, "geometry_ready_only": not blockers})
    controls = [_control(c, protocol, receptor, receptor_elements, center, anchor) for c in protocol["controls"]]
    result = {"schema_version": RESULT, "protocol_sha256": _sha(protocol),
              "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_inputs": {k: protocol[k] for k in ("source_cif", "receptor", "receptor_atom_mapping", "geometry_policy_reference")},
              "anchor_source_atom_site_ids": anchor_ids, "anchor_center_angstrom": center.tolist(),
              "coordinate_frame_id": protocol["coordinate_frame_id"], "receptor_mapping": mapping,
              "screen_policy": POLICY, "candidates": observations, "positive_geometry_controls": controls,
              "requested_candidate_count": 2, "geometry_ready_candidate_count": sum(o["geometry_ready_only"] for o in observations),
              "two_candidate_geometry_passed": all(o["geometry_ready_only"] for o in observations),
              "pair_readiness": False,
              "remaining_admission_requirements": ["native_source_method_and_prepared_origin_binding",
                  "sanctioned_fit_and_development_source_roles_and_fit_denominator",
                  "assay_microstate_and_receptor_state_equivalence_unresolved",
                  "complete_chemical_stereo_charge_and_unconstrained_model_admission"],
              "source_roles_changed": False, "new_source_labels_admitted": 0,
              "force_evaluations": 0, "score_evaluations": 0, "placements_or_coordinate_repairs": 0,
              "chemical_identity_or_stereochemistry_admission_checked": False,
              "v4_native_admission_invoked": False, "scientifically_validated": False,
              "product_ranking_enabled": False, "elapsed_wall_seconds": time.perf_counter() - started}
    # Reopen every bound input after the arithmetic. Source changes cannot
    # silently validate an earlier set of coordinates.
    refs = [protocol[k] for k in ("source_cif", "receptor", "receptor_atom_mapping", "geometry_policy_reference")]
    refs += [c["input"]["file"] for c in protocol["candidates"]]
    for control in protocol["controls"]:
        refs += [control["input"]["file"], control["retained_request"], control["retained_result"]]
    for ref in refs:
        _read(ref)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = evaluate(json.loads(args.protocol.read_bytes()))
    raw = _canonical(result) + b"\n"
    if args.output is not None:
        with args.output.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    print(raw.decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
