"""Independent saved-endpoint arithmetic audit; benchmark only, no product imports.

``audit_case`` accepts exactly two stored observations, initial and last accepted.
The OpenMM boundary is injectable for tests; importing this module does no work.
No native evaluator, scorer, optimizer, original ligand or evaluation reference is
used. Numerical agreement is not pose recovery, source admission or qualification.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import stat
import sys
import time
import xml.etree.ElementTree as ET

SCHEMA = "sro_recovery_endpoint_numerics/1"
ENDPOINT_SCHEMA = "sro_saved_numerical_endpoints/1"
OLD_WHEEL_SHA256 = "00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8"
PROTOCOL_SHA256 = "5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23"
MANIFEST_SHA256 = "4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3"
XML_SHA256 = {"ligand": "6446b0f2babfab9748fc445653d8cd2453e5d98ad1483320da197e55192734ea",
              "receptor": "7c5aeeeafed880dfee5f294fc34b6a0e2ec5a31d9482245b5cab93c10d4d1cc6"}
ORIGINAL_SHA256 = {
    "parameters": "16d3b25e6492ae8500771d60d6fe5b5db12089b8c7fa64d3f25a6f1230fad217",
    "extensions": "871c1a252c87c0b4f134c8b572f009f99658fea88f1076c9ee3fe1461a0871f6",
    "cross_parameters": "226cb9f4be87b40d312e4b3bdb0dbc785bd6d6e87daa68e2f6abec76dde22d52",
}
TOLERANCE = 1e-8
COULOMB = 332.063713299
KJ_PER_KCAL = 4.184
ANGSTROM_PER_NM = 10.0
LABELS = ("initial", "last_accepted")
COMPONENTS = {"ligand_internal", "cross_lennard_jones", "cross_screened_coulomb", "total"}
IDENTITIES = {
    "parameters": {"topology_sha256"},
    "extensions": {"topology_sha256", "base_parameter_fingerprint_sha256"},
    "cross_parameters": {"ligand_topology_sha256", "ligand_base_parameters_sha256"},
}


class EndpointAuditError(ValueError):
    """Unsupported input, source mismatch or incomplete endpoint evidence."""


def require(condition, reason):
    if not condition:
        raise EndpointAuditError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def value_hash(value):
    return sha(canonical(value))


def exact(value):
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_number")
        return ["float", value.hex()]
    if type(value) is list:
        return ["list", [exact(item) for item in value]]
    if type(value) is dict:
        return ["dict", [[key, exact(value[key])] for key in sorted(value)]]
    require(value is None or type(value) in (str, int, bool), "unsupported_json_value")
    return [type(value).__name__, value]


def _object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "duplicate_json_key")
        out[key] = value
    return out


def loads(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(EndpointAuditError("nonfinite_json")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EndpointAuditError("invalid_json") from exc
    exact(value)
    return value


def read_bound(ref):
    require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "exact_file_pin_required")
    require(type(ref["path"]) is str and Path(ref["path"]).is_absolute(), "absolute_file_path_required")
    require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in ref["sha256"]), "invalid_source_digest")
    require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= 32 * 1024 * 1024, "bounded_file_required")
    path = Path(ref["path"])
    require(not path.is_symlink() and str(path.resolve(strict=True)) == ref["path"], "source_path_alias")
    require("evaluation_only" not in path.parts and "stability_control" not in path.parts
            and not (path.name == "ligand-canonical.json" and "engine-v2-sro-numerical-preparation-20260929-v1" in path.parts),
            "reference_body_forbidden")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == ref["bytes"], "source_size_changed")
        raw = stream.read(ref["bytes"] + 1)
        after = os.fstat(stream.fileno())
        current = path.stat()
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(identity(before) == identity(after) == identity(current), "source_changed_during_read")
    require(len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "source_hash_mismatch")
    return raw


def number(token):
    require(type(token) is str, "binary64_hex_required")
    try:
        value = float.fromhex(token)
    except ValueError as exc:
        raise EndpointAuditError("invalid_binary64_hex") from exc
    require(math.isfinite(value) and value.hex() == token, "noncanonical_or_nonfinite_binary64")
    return value


def matrix(tokens, count):
    require(type(tokens) is list and len(tokens) == count, "coordinate_or_force_count")
    require(all(type(row) is list and len(row) == 3 for row in tokens), "three_components_required")
    return [[number(item) for item in row] for row in tokens]


def decode_canonical(value):
    if type(value) is dict:
        if set(value) == {"$float_hex"}:
            return number(value["$float_hex"])
        return {key: decode_canonical(item) for key, item in value.items()}
    if type(value) is list:
        return [decode_canonical(item) for item in value]
    return value


def canonical_coordinates(document, count):
    require(set(document) == {"schema_id", "system", "system_sha256"}
            and document["schema_id"] == "betelgeuze.engine_v2_canonical_system/1.0.0", "canonical_system_required")
    require(value_hash(document["system"]) == document["system_sha256"], "canonical_system_seal")
    block = document["system"]["coordinates"]
    require(block["coordinate_unit"] == "angstrom" and block["cell_vectors"] is None
            and block["cell_periodic"] is None, "nonperiodic_angstrom_required")
    tensor = block["coordinates"]["$tensor"]
    require(tensor["dtype"] == "float64" and tensor["shape"] == [1, count, 3]
            and len(tensor["values"]) == count * 3, "canonical_coordinate_shape")
    flat = [number(item["$float_hex"]) for item in tensor["values"]]
    return [flat[i:i + 3] for i in range(0, len(flat), 3)]


class Accounting:
    """Leaf call durations never overlap; the audit elapsed scope encloses them."""
    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.calls = []

    def call(self, kind, label, function, *args):
        start = self.clock()
        row = {"kind": kind, "label": label, "attempted": True, "completed": False,
               "failed": False, "wall_seconds": None, "start_monotonic_seconds": start,
               "end_monotonic_seconds": None}
        self.calls.append(row)
        try:
            result = function(*args)
        except BaseException:
            row["failed"] = True
            raise
        else:
            row["completed"] = True
            return result
        finally:
            end = self.clock()
            row["end_monotonic_seconds"] = end
            row["wall_seconds"] = end - start

    def receipt(self):
        counts = {}
        for row in self.calls:
            target = counts.setdefault(row["kind"], {"attempted": 0, "completed": 0, "failed": 0})
            for key in target:
                target[key] += int(row[key])
        return {"calls": self.calls, "counts": counts, "leaf_durations_nonoverlapping": True,
                "enclosing_elapsed_must_not_be_added_to_leaf_durations": True,
                "failed_call_work_quantities_unknown": [
                    {"kind": row["kind"], "label": row["label"]}
                    for row in self.calls if row["failed"]
                    and row["kind"] in {"context_create", "get_state"}]}


def compare_observation(stored, internal, cross, lj, electrostatic, cross_count):
    for observation, count in ((internal, 26), (cross, cross_count),
                               (lj, cross_count), (electrostatic, cross_count)):
        require(type(observation) in (list, tuple) and len(observation) == 2,
                "oracle_observation_shape")
        require(type(observation[0]) in (int, float) and math.isfinite(observation[0]),
                "nonfinite_oracle_energy")
        require(type(observation[1]) is list and len(observation[1]) == count
                and all(type(row) is list and len(row) == 3 for row in observation[1]),
                "oracle_force_shape")
        require(all(type(v) in (int, float) and math.isfinite(v)
                    for row in observation[1] for v in row), "nonfinite_oracle_output")
    energy = internal[0] + cross[0]
    forces = [[a + b for a, b in zip(x, y, strict=True)]
              for x, y in zip(internal[1], cross[1][:26], strict=True)]
    require(len(forces) == 26 and all(len(row) == 3 for row in forces), "oracle_force_shape")
    require(all(math.isfinite(v) for row in forces for v in row) and math.isfinite(energy), "nonfinite_oracle_output")
    energy_error = abs(number(stored["energy"]) - energy)
    saved_forces = matrix(stored["forces"], 26)
    force_error = max(abs(a - b) for x, y in zip(saved_forces, forces, strict=True)
                      for a, b in zip(x, y, strict=True))
    expected = {"ligand_internal": internal[0], "cross_lennard_jones": lj[0],
                "cross_screened_coulomb": electrostatic[0], "total": energy}
    component_errors = {key: abs(number(stored["components"][key]) - value) for key, value in expected.items()}
    require(all(math.isfinite(v) for v in expected.values()), "nonfinite_oracle_component")
    return {"energy_absolute_error_kcal_per_mol": energy_error,
            "force_component_absolute_error_kcal_per_mol_angstrom": force_error,
            "component_absolute_errors_kcal_per_mol": component_errors,
            "force_components_checked": 78, "reference_energy_kcal_per_mol": energy,
            "passed": energy_error <= TOLERANCE and force_error <= TOLERANCE
                      and all(v <= TOLERANCE for v in component_errors.values())}


def validate_endpoint_domain(coordinates, receptor_coordinates, base, cross):
    """NoCutoff equivalence requires every internal pair inside the native switch."""
    for i, first in enumerate(coordinates):
        for second in coordinates[i + 1:]:
            distance = math.dist(first, second)
            require(distance < base["switch_start_angstrom"], "internal_pair_outside_nocutoff_equivalence")
    for first in coordinates:
        for second in receptor_coordinates:
            require(math.dist(first, second) >= cross["minimum_distance_angstrom"],
                    "cross_pair_below_native_domain")


def _validate_inputs(case_id, request_ref, binding_ref, endpoint_states_ref,
                     ligand_xml_ref, receptor_xml_ref, original_parameter_refs, wheel_ref):
    request = loads(read_bound(request_ref))
    binding_outer = loads(read_bound(binding_ref))
    binding = binding_outer["input_binding"]
    require(wheel_ref["sha256"] == OLD_WHEEL_SHA256 and binding_outer["executed_wheel"] == wheel_ref,
            "specified_old_wheel_required")
    read_bound(wheel_ref)
    require(value_hash({k: v for k, v in binding.items() if k != "receipt_sha256"}) == binding["receipt_sha256"], "binding_seal")
    require(binding["request_sha256"] == value_hash(request), "request_binding_mismatch")
    require(binding["input_files"] == {name: request[name] for name in ("receptor", "ligand", *IDENTITIES)}, "bound_input_mismatch")
    require(set(original_parameter_refs) == set(IDENTITIES), "original_parameter_refs_required")
    require({k: v["sha256"] for k, v in original_parameter_refs.items()} == ORIGINAL_SHA256,
            "frozen_original_parameter_hash_mismatch")
    require(ligand_xml_ref["sha256"] == XML_SHA256["ligand"]
            and receptor_xml_ref["sha256"] == XML_SHA256["receptor"], "frozen_source_xml_hash_mismatch")
    derived = {}
    all_refs = [request_ref, binding_ref, endpoint_states_ref, ligand_xml_ref, receptor_xml_ref, wheel_ref]
    for name, fields in IDENTITIES.items():
        original = loads(read_bound(original_parameter_refs[name]))
        ref = {**request[name], "bytes": Path(request[name]["path"]).stat().st_size}
        value = loads(read_bound(ref))
        require(set(original) == set(value), "parameter_fields_changed")
        require(exact({k: v for k, v in original.items() if k not in fields})
                == exact({k: v for k, v in value.items() if k not in fields}), "numeric_parameter_mutation")
        derived[name] = value
        all_refs.extend([original_parameter_refs[name], ref])
    base, extensions, cross = (derived[name] for name in IDENTITIES)
    require(extensions["metadata"]["source_xml_sha256"] == ligand_xml_ref["sha256"]
            and extensions["metadata"].get("openmm_xml_sha256", ligand_xml_ref["sha256"]) == ligand_xml_ref["sha256"]
            and cross["parameter_source_sha256"] == receptor_xml_ref["sha256"], "source_xml_binding_mismatch")
    require(extensions["topology_sha256"] == cross["ligand_topology_sha256"] == base["topology_sha256"]
            and extensions["base_parameter_fingerprint_sha256"] == cross["ligand_base_parameters_sha256"] == value_hash(base),
            "parameter_reseal_mismatch")
    require(not extensions["constraints"] and not extensions["impropers"]
            and extensions["nonbonded_domain"] == "nocutoff_equivalent_inside_switch"
            and cross["mixing_rule"] == "lorentz_berthelot"
            and cross["pair_policy"] == "all_non_covalent_cross_pairs_no_exclusions", "unsupported_numeric_terms")
    require(base["dielectric"] == 1.0 and base["screening_kappa_per_angstrom"] == 0.0
            and 0 < base["switch_start_angstrom"] < base["cutoff_angstrom"]
            and 0 < cross["switch_start_angstrom"] < cross["cutoff_angstrom"]
            and cross["dielectric"] > 0 and cross["screening_kappa_per_angstrom"] >= 0,
            "unsupported_internal_or_cross_domain")
    systems = {}
    for name, count in (("ligand", 26), ("receptor", len(cross["receptor_atoms"]))):
        ref = {**request[name], "bytes": Path(request[name]["path"]).stat().st_size}
        systems[name] = canonical_coordinates(loads(read_bound(ref)), count)
        all_refs.append(ref)
    endpoints = loads(read_bound(endpoint_states_ref))
    require(set(endpoints) == {"schema_id", "case_id", "request_sha256", "binding_receipt_sha256",
                              "native_artifact_refs", "states"}, "endpoint_document_fields")
    require(endpoints["schema_id"] == ENDPOINT_SCHEMA and endpoints["case_id"] == case_id
            and endpoints["request_sha256"] == binding["request_sha256"]
            and endpoints["binding_receipt_sha256"] == binding["receipt_sha256"], "endpoint_semantic_binding_mismatch")
    require(type(endpoints["native_artifact_refs"]) is list and endpoints["native_artifact_refs"], "native_artifact_pins_required")
    for ref in endpoints["native_artifact_refs"]:
        read_bound(ref)
        all_refs.append(ref)
    require(type(endpoints["states"]) is list and len(endpoints["states"]) == 2
            and [s["label"] for s in endpoints["states"]] == list(LABELS), "exactly_two_endpoint_states_required")
    for state in endpoints["states"]:
        require(set(state) == {"label", "coordinates", "energy", "forces", "components"}
                and set(state["components"]) == COMPONENTS, "endpoint_state_fields")
        matrix(state["coordinates"], 26)
        matrix(state["forces"], 26)
        number(state["energy"])
        for value in state["components"].values():
            number(value)
    require(exact(matrix(endpoints["states"][0]["coordinates"], 26)) == exact(systems["ligand"]), "initial_coordinates_mismatch")
    for state in endpoints["states"]:
        validate_endpoint_domain(matrix(state["coordinates"], 26), systems["receptor"], base, cross)
    ligand_xml, receptor_xml = read_bound(ligand_xml_ref), read_bound(receptor_xml_ref)
    source_xml_inventory(ligand_xml, True)
    source_xml_inventory(receptor_xml, False)
    return endpoints, derived, systems, ligand_xml, receptor_xml, all_refs


def source_xml_inventory(raw, ligand):
    """Reject unsupported evaluated terms before creating any OpenMM context."""
    require(b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw, "xml_entities_unsupported")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise EndpointAuditError("invalid_source_xml") from exc
    require(root.tag == "System" and root.find("Particles") is not None
            and root.find("Forces") is not None, "source_system_required")
    forces = list(root.find("Forces"))
    nonbonded = [f for f in forces if f.get("type") == "NonbondedForce"]
    require(len(nonbonded) == 1, "exactly_one_source_nonbonded_required")
    nb = nonbonded[0]
    require(all(not list(nb.find(name)) if nb.find(name) is not None else True
                for name in ("GlobalParameters", "ParticleOffsets", "ExceptionOffsets")),
            "nonbonded_offsets_or_global_parameters_unsupported")
    require(len(nb.find("Particles")) == len(root.find("Particles")), "source_particle_count_mismatch")
    if ligand:
        allowed = {"HarmonicBondForce", "HarmonicAngleForce", "PeriodicTorsionForce", "NonbondedForce", "CMMotionRemover"}
        kinds = [f.get("type") for f in forces]
        require(set(kinds) <= allowed and len(kinds) == len(set(kinds))
                and allowed - {"CMMotionRemover"} <= set(kinds), "unsupported_or_duplicate_source_force")
        require(not list(root.find("Constraints")) and nb.get("method") == "0", "unconstrained_nocutoff_source_required")
        require(all(not list(p) for p in root.find("Particles"))
                and root.find("VirtualSites") is None, "virtual_sites_unsupported")
        require(all(f.get("usesPeriodic", "0") == "0" for f in forces), "periodic_bonded_terms_unsupported")
    return {"particles": len(root.find("Particles")), "forces": [f.get("type") for f in forces],
            "source_nonbonded_settings": dict(nb.attrib),
            "source_term_counts": {f.get("type"): {child.tag: len(child) for child in f}
                                   for f in forces},
            "nocutoff_source_switch_cutoff_dispersion_settings_inactive": ligand and nb.get("method") == "0",
            "evaluated_intrareceptor": False}


def audit_case(*, case_id, request_ref, binding_ref, endpoint_states_ref, ligand_xml_ref,
               receptor_xml_ref, original_parameter_refs, wheel_ref, protocol_sha256,
               manifest_sha256, backend=None, clock=time.perf_counter):
    """Audit two supplied stored states; injected boundaries are test evidence only.

    Endpoint fields are strict canonical binary64 hex arrays, with native result,
    journal/work/invocation file pins carried in ``native_artifact_refs``. The
    execution exporter owns proof that labels select checkpoint initial/current.
    This oracle binds the supplied observations and compares their arithmetic.
    """
    enclosing_start = clock()
    meter = Accounting(clock)
    contexts = []
    rows = []
    failure = None
    current_label = None
    refs = []
    source_ref = None
    source_digest = None
    try:
        source_path = Path(__file__).resolve(strict=True)
        source_raw = source_path.read_bytes()
        source_ref = {"path": str(source_path), "bytes": len(source_raw), "sha256": sha(source_raw)}
        read_bound(source_ref)
        source_digest = source_ref["sha256"]
        require(protocol_sha256 == PROTOCOL_SHA256 and manifest_sha256 == MANIFEST_SHA256,
                "frozen_protocol_or_manifest_mismatch")
        endpoints, derived, systems, ligand_xml, receptor_xml, refs = _validate_inputs(
            case_id, request_ref, binding_ref, endpoint_states_ref, ligand_xml_ref,
            receptor_xml_ref, original_parameter_refs, wheel_ref)
        if backend is None:
            backend = meter.call("backend_initialize", "openmm_and_numpy_imports", OpenMMBoundary)
        internal_system, cross_system = meter.call("system_build", "source_math_systems", backend.build,
                                                 ligand_xml, receptor_xml, derived)
        contexts.append(meter.call("context_create", "internal", backend.context, internal_system))
        contexts.append(meter.call("context_create", "cross", backend.context, cross_system))
        for state in endpoints["states"]:
            current_label = state["label"]
            xyz = matrix(state["coordinates"], 26)
            combined = xyz + systems["receptor"]
            meter.call("set_positions", state["label"] + ".internal", backend.positions, contexts[0], xyz)
            meter.call("set_positions", state["label"] + ".cross", backend.positions, contexts[1], combined)
            observations = []
            for label, context, groups in (("internal", contexts[0], None), ("cross", contexts[1], None),
                                            ("cross_lj", contexts[1], {0}), ("cross_q", contexts[1], {1})):
                raw_state = meter.call("get_state", state["label"] + "." + label,
                                       backend.get_state, context, groups)
                observations.append(meter.call("state_values", state["label"] + "." + label,
                                               backend.decode_state, raw_state))
            result = meter.call("comparison", state["label"], compare_observation, state,
                                *observations, len(combined))
            rows.append({"label": state["label"], "coordinates_binary64_hex": state["coordinates"],
                         "stored_observation_sha256": value_hash(state), "status": "evaluated", **result})
            current_label = None
    except Exception as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
        if current_label is not None:
            rows.append({"label": current_label, "status": "failed", "passed": False,
                         "error": failure, "comparison_completed": False})
    finally:
        for context in reversed(contexts):
            try:
                meter.call("context_release", "release", backend.release, context)
            except Exception as exc:
                failure = {"type": type(exc).__name__, "reason": str(exc)}
    try:
        for ref in refs:
            read_bound(ref)
        if source_ref is not None:
            read_bound(source_ref)
    except Exception as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    environment = {}
    if backend is not None and meter.calls:
        try:
            environment = meter.call("environment_inventory", "environment", backend.environment)
        except Exception as exc:
            failure = {"type": type(exc).__name__, "reason": str(exc)}
    passed = sum(row["passed"] for row in rows)
    enclosing_end = clock()
    receipt = {"schema_id": SCHEMA, "case_id": case_id, "status": "passed" if passed == 2 and failure is None else "failed",
               "request_ref": request_ref, "binding_ref": binding_ref, "endpoint_states_ref": endpoint_states_ref,
               "native_artifact_refs": endpoints["native_artifact_refs"] if "endpoints" in locals() else [], "wheel_ref": wheel_ref,
               "source_xml_refs": {"ligand": ligand_xml_ref, "receptor": receptor_xml_ref},
               "source_xml_inventory": {"ligand": source_xml_inventory(ligand_xml, True),
                                        "receptor": source_xml_inventory(receptor_xml, False)}
                                       if "ligand_xml" in locals() else {},
               "original_parameter_refs": original_parameter_refs,
               "protocol_sha256": protocol_sha256, "manifest_sha256": manifest_sha256,
               "source_sha256": source_digest, "executing_source_ref": source_ref, "environment": environment,
               "states": rows, "denominator": {"requested": 2, "evaluated": sum(r["status"] == "evaluated" for r in rows), "passed": passed,
                                                   "failed": len(rows) - passed, "unknown": 2 - len(rows)},
               "all_same_math_checks_passed": passed == 2 and failure is None, "failure": failure,
               "energy_absolute_tolerance_kcal_per_mol": TOLERANCE,
               "force_component_absolute_tolerance_kcal_per_mol_angstrom": TOLERANCE,
               "openmm_accounting": meter.receipt(), "enclosing_wall_seconds": enclosing_end - enclosing_start,
               "enclosing_start_monotonic_seconds": enclosing_start,
               "enclosing_end_monotonic_seconds": enclosing_end,
               "enclosing_scope": "entry_through_validation_openmm_cleanup_environment_before_receipt_seal",
               "endpoint_states_are_not_openmm_call_count": True, "new_native_force_calls": 0,
               "new_native_score_calls": 0, "intrareceptor_energy_evaluated": False,
               "source_XML_equivalence_claimed": False, "scientifically_validated": False,
               "actual_execution_authorized": False,
               "native_endpoint_selection_proof": "external_exporter_semantic_verification_required",
               "openmm_observations_performed": backend is not None and getattr(backend, "is_real_openmm", False)
                                             and any(r["kind"] == "get_state" and r["completed"] for r in meter.calls)}
    receipt["receipt_sha256"] = value_hash(receipt)
    return receipt


class OpenMMBoundary:
    """Reference platform, source-driven internal math and cross-only interactions."""
    is_real_openmm = True

    def __init__(self):
        import openmm
        import numpy
        self.mm = openmm
        self.np = numpy

    def environment(self):
        package_modules = {}
        for name, module in tuple(sys.modules.items()):
            if name == "openmm" or name.startswith("openmm.") or name == "numpy" or name.startswith("numpy."):
                origin = getattr(module, "__file__", None)
                if origin and Path(origin).is_file():
                    path = Path(origin).resolve(strict=True)
                    package_modules[name] = {"path": str(path), "sha256": sha(path.read_bytes()),
                                             "bytes": path.stat().st_size}
        return {"python": platform.python_version(), "executable": sys.executable,
                "isolated": sys.flags.isolated, "openmm": self.mm.version.version,
                "openmm_module_sha256": sha(Path(self.mm.__file__).read_bytes()),
                "openmm_module_path": str(Path(self.mm.__file__).resolve()),
                "numpy": self.np.__version__, "numpy_module_path": str(Path(self.np.__file__).resolve()),
                "numpy_module_sha256": sha(Path(self.np.__file__).read_bytes()), "platform": "Reference",
                "loaded_dependency_modules": package_modules,
                "loaded_dependency_manifest_sha256": value_hash(package_modules)}

    def _nonbonded(self, system):
        rows = [f for f in system.getForces() if isinstance(f, self.mm.NonbondedForce)]
        require(len(rows) == 1, "exactly_one_source_nonbonded_required")
        f = rows[0]
        require(not f.getNumGlobalParameters() and not f.getNumParticleParameterOffsets()
                and not f.getNumExceptionParameterOffsets(), "unsupported_source_parameter_offsets")
        return f

    def _particles(self, system):
        nb, u = self._nonbonded(system), self.mm.unit
        return [(q.value_in_unit(u.elementary_charge), s.value_in_unit(u.nanometer), e.value_in_unit(u.kilojoules_per_mole))
                for q, s, e in (nb.getParticleParameters(i) for i in range(nb.getNumParticles()))]

    def build(self, ligand_xml, receptor_xml, derived):
        mm, u = self.mm, self.mm.unit
        ligand = mm.XmlSerializer.deserialize(ligand_xml.decode())
        receptor = mm.XmlSerializer.deserialize(receptor_xml.decode())
        cross, base = derived["cross_parameters"], derived["parameters"]
        for source, rows in ((ligand, base["atom_parameters"]), (receptor, cross["receptor_atoms"])):
            values = self._particles(source)
            require(len(values) == len(rows), "source_parameter_count_mismatch")
            for i, ((q, sig, eps), row) in enumerate(zip(values, rows, strict=True)):
                require(row["atom_index"] == i and all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
                        for a, b in zip((q, sig * 10, eps / 4.184),
                                        (row["charge_e"], row["sigma_angstrom"], row["epsilon_kcal_per_mol"]), strict=True)),
                        "source_particle_parameter_mismatch")
        require(ligand.getNumParticles() == 26 and not ligand.getNumConstraints(), "source_ligand_scope")
        nb = self._nonbonded(ligand)
        require(nb.getNonbondedMethod() == mm.NonbondedForce.NoCutoff, "source_nocutoff_required")
        values = self._particles(ligand)
        internal = mm.XmlSerializer.deserialize(ligand_xml.decode())
        for f in internal.getForces():
            f.setForceGroup(0)
        force = mm.CustomNonbondedForce("4*sqrt(eps1*eps2)*(sr6*sr6-sr6)+C*q1*q2/r;sr6=(0.5*(sig1+sig2)/r)^6")
        for name in ("q", "sig", "eps"):
            force.addPerParticleParameter(name)
        force.addGlobalParameter("C", COULOMB * KJ_PER_KCAL / ANGSTROM_PER_NM)
        force.setNonbondedMethod(mm.CustomNonbondedForce.NoCutoff)
        force.setUseLongRangeCorrection(False)
        for row in values:
            force.addParticle(row)
        exceptions = mm.CustomBondForce("4*eps*(sr6*sr6-sr6)+C*q/r;sr6=(sig/r)^6")
        for name in ("q", "sig", "eps"):
            exceptions.addPerBondParameter(name)
        exceptions.addGlobalParameter("C", COULOMB * KJ_PER_KCAL / ANGSTROM_PER_NM)
        for i in range(nb.getNumExceptions()):
            a, b, q, sig, eps = nb.getExceptionParameters(i)
            force.addExclusion(a, b)
            q, sig, eps = q.value_in_unit(u.elementary_charge ** 2), sig.value_in_unit(u.nanometer), eps.value_in_unit(u.kilojoules_per_mole)
            if q != 0 or eps != 0:
                exceptions.addBond(a, b, [q, sig, eps])
        for i in reversed(range(internal.getNumForces())):
            if isinstance(internal.getForce(i), mm.NonbondedForce):
                internal.removeForce(i)
        internal.addForce(force)
        internal.addForce(exceptions)
        combined = mm.System()
        for source in (ligand, receptor):
            for i in range(source.getNumParticles()):
                combined.addParticle(source.getParticleMass(i))
        switch = "s=1-10*t^3+15*t^4-6*t^5;t=min(1,max(0,(r-rs)/(rc-rs)))"
        expressions = ("s*4*sqrt(eps1*eps2)*(sr6*sr6-sr6);sr6=(0.5*(sig1+sig2)/r)^6;" + switch,
                       "s*C*q1*q2*exp(-kappa*r)/(dielectric*r);" + switch)
        for group, expression in enumerate(expressions):
            f = mm.CustomNonbondedForce(expression)
            for name in ("q", "sig", "eps"):
                f.addPerParticleParameter(name)
            for name, value in {"C": COULOMB * KJ_PER_KCAL / ANGSTROM_PER_NM,
                                "rs": cross["switch_start_angstrom"] / 10, "rc": cross["cutoff_angstrom"] / 10,
                                "dielectric": cross["dielectric"], "kappa": cross["screening_kappa_per_angstrom"] * 10}.items():
                f.addGlobalParameter(name, value)
            for row in values + self._particles(receptor):
                f.addParticle(row)
            f.addInteractionGroup(set(range(26)), set(range(26, combined.getNumParticles())))
            f.setNonbondedMethod(mm.CustomNonbondedForce.CutoffNonPeriodic)
            f.setCutoffDistance(cross["cutoff_angstrom"] / 10)
            f.setUseSwitchingFunction(False)
            f.setUseLongRangeCorrection(False)
            f.setForceGroup(group)
            combined.addForce(f)
        return internal, combined

    def context(self, system):
        integrator = self.mm.VerletIntegrator(.001)
        return [self.mm.Context(system, integrator, self.mm.Platform.getPlatformByName("Reference")), integrator]

    def positions(self, holder, coordinates):
        holder[0].setPositions(self.np.asarray(coordinates, dtype=self.np.float64) / 10)

    def get_state(self, holder, groups):
        kwargs = {} if groups is None else {"groups": groups}
        return holder[0].getState(getEnergy=True, getForces=True, **kwargs)

    def decode_state(self, state):
        u = self.mm.unit
        energy = float(state.getPotentialEnergy().value_in_unit(u.kilojoules_per_mole) / 4.184)
        force = self.np.asarray(state.getForces(asNumpy=True).value_in_unit(u.kilojoules_per_mole / u.nanometer),
                                dtype=self.np.float64) / 41.84
        return energy, force.tolist()

    def release(self, holder):
        # Audit keeps the holder for accounting; clearing it drops its sole owned
        # Context and Integrator references inside this measured release scope.
        holder.clear()
