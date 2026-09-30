"""Prospective saved-state particle conversion diagnostic; never a campaign resume.

``prepare`` reads metadata and stored observations only. ``execute`` requires an
explicit numerical-phase flag and an exact plan hash. Importing this file neither
imports OpenMM nor reads any molecular input. Tests inject a synthetic boundary.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import stat
import sys
import time
import types

SCHEMA = "sro_particle_roundtrip_diagnostic/1"
PLAN_SCHEMA = "sro_particle_roundtrip_diagnostic_plan/1"
ARMS = ("original_xml_particles", "native_unit_roundtrip_particles")
LABELS = ("initial", "last_accepted")
TERMS = ("internal", "cross", "cross_lj", "cross_coulomb")
CASE = "perturbed_02"
TOLERANCE = 1e-8
FROZEN_ORACLE_SHA256 = "9a1598e8f94e98ff691a435e8f6a43835a9408c58e9da07051fdd7a56e90f1e1"
NUMERICAL_ROLES = {"ligand_xml", "receptor_xml", "receptor_coordinates", "parameters", "extensions", "cross_parameters"}
FROZEN_R2 = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-guard-repair-four-case-20260930-p76d71f6")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def validate_path(path):
    path = Path(path)
    forbidden = {"evaluation_only", "stability_control", "Fresh-128", "fresh-128"}
    require(not any(part in forbidden for part in path.parts) and path.name != "ligand-canonical.json",
            "protected_or_original_ligand_body_forbidden")
    require(path.is_absolute() and not path.is_symlink() and str(path.resolve(strict=True)) == str(path),
            "canonical_regular_file_required")
    require(stat.S_ISREG(path.stat().st_mode), "regular_file_required")
    return path


def pin(path, *, allowed_paths, max_bytes=32 * 1024 * 1024):
    # All callers name owned source/output or fixed metadata paths BEFORE opening.
    path = Path(path)
    require(str(path) in {str(Path(item)) for item in allowed_paths}, "pin_role_path_not_authorized")
    validate_path(path)
    size = path.stat().st_size
    require(0 < size <= max_bytes, "bounded_input_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "regular_file_required")
        raw = stream.read(size + 1)
        after = os.fstat(stream.fileno())
    require(file_identity(before) == file_identity(after) == file_identity(path.stat()), "source_changed_during_read")
    require(len(raw) == size, "source_size_changed")
    return {"path": str(path), "bytes": size, "sha256": digest(raw)}


def read_ref(ref, *, max_bytes=32 * 1024 * 1024):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "exact_file_pin_required")
    path = validate_path(ref["path"])
    require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= max_bytes, "bounded_input_required")
    require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64, "sha256_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "regular_file_required")
        raw = stream.read(ref["bytes"] + 1)
        after = os.fstat(stream.fileno())
    now = path.stat()
    require(file_identity(before) == file_identity(after) == file_identity(now), "source_changed_during_read")
    require(len(raw) == ref["bytes"] and digest(raw) == ref["sha256"], "source_pin_mismatch")
    return raw


def load_oracle(ref):
    require(ref["sha256"] == FROZEN_ORACLE_SHA256, "frozen_oracle_hash_required")
    raw = read_ref(ref)
    module = types.ModuleType("sro_particle_roundtrip_frozen_oracle")
    module.__file__ = ref["path"]
    exec(compile(raw, ref["path"], "exec"), module.__dict__)
    return module


def write_json(path, value):
    raw = canonical(value) + b"\n"
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def binary64(value):
    require(type(value) in (int, float) and math.isfinite(value), "finite_binary64_required")
    value = float(value)
    return {"hex": value.hex(), "ulp_size_hex": math.ulp(value).hex()}


def ulp_distance(first, second):
    def ordered(value):
        bits = struct.unpack(">Q", struct.pack(">d", float(value)))[0]
        return (~bits & ((1 << 64) - 1)) if bits >> 63 else bits | (1 << 63)
    binary64(first)
    binary64(second)
    return abs(ordered(first) - ordered(second))


def exact_delta(first, second):
    difference = Fraction.from_float(float(second)) - Fraction.from_float(float(first))
    return {"float_subtraction_hex": (float(second) - float(first)).hex(),
            "exact_numerator": str(difference.numerator), "exact_denominator": str(difference.denominator)}


def particle_table(source_rows, native_rows, scope):
    require(len(source_rows) == len(native_rows), "particle_count_changed")
    rows = []
    for index, (source, native) in enumerate(zip(source_rows, native_rows, strict=True)):
        require(native["atom_index"] == index, "particle_order_changed")
        native_values = (native["charge_e"], native["sigma_angstrom"], native["epsilon_kcal_per_mol"])
        roundtrip = (float(native_values[0]), float(native_values[1]) / 10, float(native_values[2]) * 4.184)
        converted_source = (source[0], source[1] * 10, source[2] / 4.184)
        fields = {}
        for field, old, n, converted, new, native_unit, mm_unit in zip(
                ("q", "sigma", "epsilon"), source, native_values, converted_source, roundtrip,
                ("elementary_charge", "angstrom", "kcal_per_mol"),
                ("elementary_charge", "nanometer", "kilojoules_per_mol"), strict=True):
            require(math.isclose(converted, n, rel_tol=1e-12, abs_tol=1e-12), "source_particle_mismatch")
            fields[field] = {"original_openmm": binary64(old), "native": binary64(n),
                             "source_converted_to_native": binary64(converted), "roundtrip_openmm": binary64(new),
                             "native_unit": native_unit, "openmm_unit": mm_unit,
                             "source_vs_native_ulp_distance_in_native_unit": ulp_distance(converted, n),
                             "original_vs_roundtrip_ulp_distance": ulp_distance(old, new),
                             "changed": float(old).hex() != float(new).hex(),
                             "roundtrip_minus_original": exact_delta(old, new)}
        rows.append({"scope": scope, "atom_index": index, "fields": fields})
    return rows, [tuple(float.fromhex(row["fields"][key]["roundtrip_openmm"]["hex"])
                        for key in ("q", "sigma", "epsilon")) for row in rows]


class RealBoundary:
    """Reuse the frozen builder; mutate only custom nonbonded particle scalars."""
    is_real_openmm = True

    def __init__(self, oracle):
        self.oracle = oracle
        self.base = oracle.OpenMMBoundary()

    def _customs(self, system):
        mm = self.base.mm
        rows = [force for force in system.getForces() if isinstance(force, mm.CustomNonbondedForce)]
        require(all([force.getPerParticleParameterName(i) for i in range(force.getNumPerParticleParameters())]
                    == ["q", "sig", "eps"] for force in rows), "custom_particle_schema_changed")
        return rows

    def _signature(self, system):
        mm = self.base.mm
        raw = mm.XmlSerializer.serialize(system).encode()
        normalized = mm.XmlSerializer.deserialize(raw.decode())
        for force in self._customs(normalized):
            for index in range(force.getNumParticles()):
                force.setParticleParameters(index, [0.0, 0.0, 0.0])
        return {"full_system_xml_sha256": digest(raw),
                "all_except_custom_particle_q_sigma_epsilon_sha256":
                    digest(mm.XmlSerializer.serialize(normalized).encode())}

    def build_arms(self, ligand_xml, receptor_xml, parameters):
        mm = self.base.mm
        original = self.base.build(ligand_xml, receptor_xml, parameters)
        roundtrip = self.base.build(ligand_xml, receptor_xml, parameters)
        ligand = mm.XmlSerializer.deserialize(ligand_xml.decode())
        receptor = mm.XmlSerializer.deserialize(receptor_xml.decode())
        ligand_table, ligand_values = particle_table(self.base._particles(ligand),
                                                   parameters["parameters"]["atom_parameters"], "ligand")
        receptor_table, receptor_values = particle_table(self.base._particles(receptor),
                                                       parameters["cross_parameters"]["receptor_atoms"], "receptor")
        for system, values, expected_forces in ((roundtrip[0], ligand_values, 1),
                                                (roundtrip[1], ligand_values + receptor_values, 2)):
            forces = self._customs(system)
            require(len(forces) == expected_forces, "custom_force_count_changed")
            for force in forces:
                require(force.getNumParticles() == len(values), "custom_particle_count_changed")
                for index, row in enumerate(values):
                    force.setParticleParameters(index, row)
        invariants = {}
        for label, old, new in zip(("internal", "cross"), original, roundtrip, strict=True):
            old_pin, new_pin = self._signature(old), self._signature(new)
            require(old_pin["all_except_custom_particle_q_sigma_epsilon_sha256"]
                    == new_pin["all_except_custom_particle_q_sigma_epsilon_sha256"], "nonparticle_intervention_detected")
            invariants[label] = {"original": old_pin, "roundtrip": new_pin,
                                 "all_nonintervened_system_fields_identical": True}
        return dict(zip(ARMS, (original, roundtrip), strict=True)), ligand_table + receptor_table, invariants

    def context(self, system):
        return self.base.context(system)

    def positions(self, holder, coordinates):
        return self.base.positions(holder, coordinates)

    def get_state(self, holder, groups):
        return self.base.get_state(holder, groups)

    def decode_state(self, state):
        return self.base.decode_state(state)

    def release(self, holder):
        return self.base.release(holder)

    def environment(self):
        return self.base.environment()


class CallLedger:
    """Reserve the complete protocol before dispatch; durable starts mean unknown."""
    def __init__(self, event_sink=None, wall=time.perf_counter, cpu=time.process_time):
        self.rows = []
        self.event_sink = event_sink or (lambda event: None)
        self.wall, self.cpu = wall, cpu
        for arm in ARMS:
            for scope in ("internal", "cross"):
                self.reserve("context_create", f"{arm}.{scope}")
            for state in LABELS:
                for scope in ("internal", "cross"):
                    self.reserve("set_positions", f"{arm}.{state}.{scope}")
                for term in TERMS:
                    self.reserve("get_state", f"{arm}.{state}.{term}")

    def reserve(self, kind, label):
        row = {"kind": kind, "label": label, "status": "reserved", "wall_seconds": None,
               "process_cpu_seconds": None, "work_quantity": "not_dispatched"}
        self.rows.append(row)
        self.event_sink({"event": "reserved", **row})

    def call(self, kind, label, function, *args):
        rows = [row for row in self.rows if row["kind"] == kind and row["label"] == label]
        require(len(rows) == 1 and rows[0]["status"] == "reserved", "duplicate_or_unreserved_call")
        row = rows[0]
        start, cpu_start = self.wall(), self.cpu()
        row.update(status="unknown", work_quantity="unknown", start_monotonic_seconds=start,
                   start_process_cpu_seconds=cpu_start)
        self.event_sink({"event": "started", **row})
        try:
            result = function(*args)
        except BaseException as exc:
            row.update(status="error", error={"type": type(exc).__name__, "reason": str(exc)})
            raise
        else:
            row.update(status="completed", work_quantity="one_boundary_call_completed")
            return result
        finally:
            end, cpu_end = self.wall(), self.cpu()
            row.update(end_monotonic_seconds=end, end_process_cpu_seconds=cpu_end,
                       wall_seconds=end - start, process_cpu_seconds=cpu_end - cpu_start)
            self.event_sink({"event": "finished", **row})

    def receipt(self):
        counts = {}
        for row in self.rows:
            count = counts.setdefault(row["kind"], {key: 0 for key in ("reserved_total", "completed", "error", "unknown", "not_dispatched")})
            count["reserved_total"] += 1
            count["not_dispatched" if row["status"] == "reserved" else row["status"]] += 1
        return {"calls": self.rows, "counts": counts,
                "boundary_leaf_durations_nonoverlapping": True,
                "enclosing_wall_and_cpu_scopes_must_not_be_added_to_leaf_costs": True,
                "failed_or_interrupted_internal_work_unknown": True}


def hex_matrix(rows):
    return [[float(value).hex() for value in row] for row in rows]


def difference(first, second):
    return [[a - b for a, b in zip(x, y, strict=True)] for x, y in zip(first, second, strict=True)]


def force_summary(rows):
    require(len(rows) == 26 and all(len(row) == 3 for row in rows), "ligand_force_shape")
    require(all(math.isfinite(value) for row in rows for value in row), "nonfinite_force")
    index, axis = max(((i, j) for i in range(26) for j in range(3)), key=lambda ij: abs(rows[ij[0]][ij[1]]))
    value = rows[index][axis]
    return {"vectors_binary64_hex": hex_matrix(rows), "components": 78,
            "max_absolute_component": abs(value), "argmax_atom_index": index,
            "argmax_axis": "xyz"[axis], "argmax_signed_component_hex": value.hex()}


def observations_record(observations, stored, oracle, cross_count):
    # The frozen comparator validates ALL receptor force outputs as well.
    comparison = oracle.compare_observation(stored, *observations, cross_count)
    records = {}
    for label, (energy, forces) in zip(TERMS, observations, strict=True):
        records[label] = {"energy_kcal_per_mol_hex": float(energy).hex(),
                          "ligand_force": force_summary(forces[:26])}
    total = [[a + b for a, b in zip(x, y, strict=True)]
             for x, y in zip(observations[0][1], observations[1][1][:26], strict=True)]
    energy = observations[0][0] + observations[1][0]
    native = oracle.matrix(stored["forces"], 26)
    return {"terms": records, "total_energy_kcal_per_mol_hex": float(energy).hex(),
            "total_ligand_force": force_summary(total),
            "native_total_minus_arm_force": force_summary(difference(native, total)),
            "native_total_minus_arm_energy_kcal_per_mol_hex": (oracle.number(stored["energy"]) - energy).hex(),
            "fixed_1e_minus_8_comparison": comparison,
            "vector_role": "new_prospective_openmm_observation"}


def arm_comparison(original, roundtrip, oracle):
    old = oracle.matrix(original["total_ligand_force"]["vectors_binary64_hex"], 26)
    new = oracle.matrix(roundtrip["total_ligand_force"]["vectors_binary64_hex"], 26)
    native_residual_old = oracle.matrix(original["native_total_minus_arm_force"]["vectors_binary64_hex"], 26)
    native_residual_new = oracle.matrix(roundtrip["native_total_minus_arm_force"]["vectors_binary64_hex"], 26)
    delta = difference(new, old)
    closure = difference(native_residual_new, difference(native_residual_old, delta))
    terms = {}
    for label in TERMS:
        a, b = original["terms"][label], roundtrip["terms"][label]
        terms[label] = {"roundtrip_minus_original_energy_kcal_per_mol_hex":
                           (float.fromhex(b["energy_kcal_per_mol_hex"]) - float.fromhex(a["energy_kcal_per_mol_hex"])).hex(),
                       "roundtrip_minus_original_ligand_force": force_summary(difference(
                           oracle.matrix(b["ligand_force"]["vectors_binary64_hex"], 26),
                           oracle.matrix(a["ligand_force"]["vectors_binary64_hex"], 26)))}
    return {"roundtrip_minus_original_total_force": force_summary(delta),
            "roundtrip_minus_original_total_energy_kcal_per_mol_hex":
                (float.fromhex(roundtrip["total_energy_kcal_per_mol_hex"]) - float.fromhex(original["total_energy_kcal_per_mol_hex"])).hex(),
            "term_arm_deltas_are_openmm_arm_differences_only": terms,
            "residual_identity_roundoff": force_summary(closure),
            "identity": "native-roundtrip = (native-original) - (roundtrip-original)",
            "native_term_force_vectors_available": False, "cause_established": False}


def run_diagnostic(*, oracle, endpoints, receptor_coordinates, parameters, ligand_xml,
                   receptor_xml, backend, ledger=None):
    ledger = ledger or CallLedger()
    start, cpu_start = time.perf_counter(), time.process_time()
    contexts, results, cleanup, failure = [], {}, [], None
    particle_rows, invariants = [], {}
    try:
        require([state["label"] for state in endpoints["states"]] == list(LABELS), "two_ordered_saved_states_required")
        for state in endpoints["states"]:
            oracle.matrix(state["forces"], 26)
            oracle.number(state["energy"])
            oracle.validate_endpoint_domain(oracle.matrix(state["coordinates"], 26), receptor_coordinates,
                                            parameters["parameters"], parameters["cross_parameters"])
        systems, particle_rows, invariants = backend.build_arms(ligand_xml, receptor_xml, parameters)
        for arm in ARMS:
            holders = []
            for scope, system in zip(("internal", "cross"), systems[arm], strict=True):
                holder = ledger.call("context_create", f"{arm}.{scope}", backend.context, system)
                contexts.append((arm, scope, holder))
                holders.append(holder)
            for state in endpoints["states"]:
                label = state["label"]
                coordinates = oracle.matrix(state["coordinates"], 26)
                for scope, holder, positions in (("internal", holders[0], coordinates),
                                                 ("cross", holders[1], coordinates + receptor_coordinates)):
                    ledger.call("set_positions", f"{arm}.{label}.{scope}", backend.positions, holder, positions)
                observations = []
                for term, holder, groups in (("internal", holders[0], None), ("cross", holders[1], None),
                                               ("cross_lj", holders[1], {0}), ("cross_coulomb", holders[1], {1})):
                    raw = ledger.call("get_state", f"{arm}.{label}.{term}", backend.get_state, holder, groups)
                    observations.append(backend.decode_state(raw))
                results.setdefault(label, {})[arm] = observations_record(observations, state, oracle, 26 + len(receptor_coordinates))
    except Exception as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    finally:
        for arm, scope, holder in reversed(contexts):
            released_start, cpu_release = time.perf_counter(), time.process_time()
            row = {"arm": arm, "scope": scope, "status": "unknown"}
            try:
                backend.release(holder)
                row["status"] = "completed"
            except Exception as exc:
                row.update(status="error", error={"type": type(exc).__name__, "reason": str(exc)})
                failure = row["error"]
            row.update(wall_seconds=time.perf_counter() - released_start,
                       process_cpu_seconds=time.process_time() - cpu_release)
            cleanup.append(row)
    try:
        for state in results.values():
            if set(state) == set(ARMS):
                state["arm_comparison"] = arm_comparison(state[ARMS[0]], state[ARMS[1]], oracle)
    except Exception as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    complete = failure is None and all(set(results.get(label, {})) == {*ARMS, "arm_comparison"} for label in LABELS)
    return {"schema_id": SCHEMA, "case_id": CASE, "status": "completed" if complete else "failed",
            "failure": failure, "states": results, "particle_fields": particle_rows, "system_invariants": invariants,
            "call_accounting": ledger.receipt(), "context_cleanup": cleanup,
            "numerical_execution_enclosing_wall_seconds": time.perf_counter() - start,
            "numerical_execution_enclosing_process_cpu_seconds": time.process_time() - cpu_start,
            "enclosing_costs_must_not_be_added_to_leaf_costs": True,
            "native_force_calls": 0, "native_score_calls": 0, "native_optimizer_calls": 0,
            "intrareceptor_energy_evaluated": False, "frozen_gate": TOLERANCE,
            "frozen_campaign_modified_or_resumed": False, "native_term_force_vectors_available": False,
            "scientifically_validated": False, "cause_established": False,
            "actual_openmm_observations": bool(getattr(backend, "is_real_openmm", False))
                and any(row["kind"] == "get_state" and row["status"] == "completed" for row in ledger.rows)}


def prepare_plan(r2, output, test_source, document_source):
    require(Path(r2) == FROZEN_R2, "fixed_terminal_metadata_root_required")
    r2, output = Path(r2), Path(output)
    require(output.is_absolute() and not output.exists() and output.parent.resolve() == output.parent,
            "new_canonical_output_directory_required")
    require(not output.is_relative_to(r2), "output_inside_frozen_campaign_forbidden")
    source_path = Path(__file__)
    require(source_path.name == "sro_particle_roundtrip_diagnostic_v1.py"
            and Path(test_source).name == "test_sro_particle_roundtrip_diagnostic_v1.py"
            and Path(document_source).name == "sro_particle_roundtrip_diagnostic_plan_20260930.md", "owned_source_names_required")
    source = pin(source_path, allowed_paths=[source_path])
    metadata_paths = [r2 / "plan.json", r2 / "oracle-input-spec.json",
                      r2 / "campaign" / CASE / "native/endpoint-states.json",
                      r2 / "campaign" / CASE / "oracle/numerical-receipt.json"]
    plan_ref, spec_ref = (pin(path, allowed_paths=metadata_paths) for path in metadata_paths[:2])
    old_plan = json.loads(read_ref(plan_ref))
    spec = json.loads(read_ref(spec_ref))
    require(set(spec) == {"schema_id", "dependency_site", "ligand_xml_ref", "receptor_xml_ref", "oracle_source_ref", "original_parameter_refs"}
            and spec["schema_id"] == "sro_endpoint_oracle_input_spec/1"
            and set(spec["original_parameter_refs"]) == {"parameters", "extensions", "cross_parameters"}, "exact_spec_roles_required")
    require(spec["oracle_source_ref"]["path"] == str(r2 / "source/sro_recovery_endpoint_numerics_v1.py"), "fixed_oracle_source_path_required")
    oracle = load_oracle(spec["oracle_source_ref"])
    endpoint_ref, receipt_ref = (pin(path, allowed_paths=metadata_paths) for path in metadata_paths[2:])
    endpoints, receipt = oracle.loads(read_ref(endpoint_ref)), oracle.loads(read_ref(receipt_ref))
    require(endpoints["schema_id"] == oracle.ENDPOINT_SCHEMA and endpoints["case_id"] == receipt["case_id"] == CASE,
            "case02_saved_observations_required")
    require(set(endpoints) == {"schema_id", "case_id", "request_sha256", "binding_receipt_sha256", "native_artifact_refs", "states"}
            and type(endpoints["states"]) is list and len(endpoints["states"]) == 2
            and [state["label"] for state in endpoints["states"]] == list(LABELS), "two_ordered_saved_states_required")
    for state in endpoints["states"]:
        require(set(state) == {"label", "coordinates", "energy", "forces", "components"}
                and set(state["components"]) == oracle.COMPONENTS, "saved_observation_fields")
        oracle.matrix(state["coordinates"], 26)
        oracle.matrix(state["forces"], 26)
        oracle.number(state["energy"])
        for value in state["components"].values():
            oracle.number(value)
    require(receipt["endpoint_states_ref"] == endpoint_ref and receipt["source_sha256"] == FROZEN_ORACLE_SHA256,
            "stored_oracle_binding_mismatch")
    require(receipt["receipt_sha256"] == oracle.value_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"}),
            "stored_oracle_receipt_seal")
    require(receipt["status"] == "failed" and receipt["energy_absolute_tolerance_kcal_per_mol"] == TOLERANCE
            and receipt["force_component_absolute_tolerance_kcal_per_mol_angstrom"] == TOLERANCE,
            "frozen_failure_and_gate_required")
    case = next(case for case in old_plan["cases"] if case["case_id"] == CASE)
    numeric_refs = {"ligand_xml": spec["ligand_xml_ref"], "receptor_xml": spec["receptor_xml_ref"],
                    "receptor_coordinates": case["derived_input_refs"]["receptor"], **spec["original_parameter_refs"]}
    validate_numerical_roles(numeric_refs, oracle)
    require(case["request_file_ref"] == receipt["request_ref"], "request_metadata_binding_mismatch")
    require(receipt["protocol_sha256"] == old_plan["protocol_sha256"] == oracle.PROTOCOL_SHA256
            and receipt["manifest_sha256"] == old_plan["manifest_sha256"] == oracle.MANIFEST_SHA256,
            "frozen_protocol_manifest_required")
    output.mkdir(mode=0o700)
    snapshots = output / "source"
    snapshots.mkdir()
    refs = {}
    for name, ref in (("diagnostic", source), ("frozen_oracle", spec["oracle_source_ref"]),
                      ("tests", pin(test_source, allowed_paths=[test_source])),
                      ("plan_document", pin(document_source, allowed_paths=[document_source]))):
        path = snapshots / {"diagnostic": "sro_particle_roundtrip_diagnostic_v1.py",
                            "frozen_oracle": "sro_recovery_endpoint_numerics_v1.py",
                            "tests": "test_sro_particle_roundtrip_diagnostic_v1.py",
                            "plan_document": "sro_particle_roundtrip_diagnostic_plan_20260930.md"}[name]
        path.write_bytes(read_ref(ref))
        refs[name] = pin(path, allowed_paths=[path])
    plan = {"schema_id": PLAN_SCHEMA, "case_id": CASE, "frozen_terminal_campaign_root": str(r2),
            "actual_execution_performed": False, "numerical_phase_requires_explicit_authorization": True,
            "campaign_resume_allowed": False, "arms": list(ARMS), "states": list(LABELS),
            "protocol_counts": {"context_create": 4, "set_positions": 8, "get_state": 16},
            "frozen_gate": TOLERANCE, "protocol_sha256": old_plan["protocol_sha256"],
            "manifest_sha256": old_plan["manifest_sha256"], "source_refs": refs,
            "metadata_refs": {"terminal_plan": plan_ref, "oracle_input_spec": spec_ref,
                              "saved_endpoint_states": endpoint_ref, "saved_oracle_receipt": receipt_ref},
            "numerical_input_refs": numeric_refs,
            "saved_state_pins": [{"label": state["label"], "stored_observation_sha256": oracle.value_hash(state),
                                  "coordinates_sha256": oracle.value_hash(state["coordinates"]),
                                  "native_total_forces_sha256": oracle.value_hash(state["forces"])}
                                 for state in endpoints["states"]],
            "source_system_pins": {"derived_system_sha256": case["derived_system_sha256"],
                                   "derived_topology_sha256": case["derived_topology_sha256"],
                                   "request_sha256": endpoints["request_sha256"],
                                   "binding_receipt_sha256": endpoints["binding_receipt_sha256"]},
            "dependency_site": spec["dependency_site"], "python_binary_ref": old_plan["oracle_phase"]["python_binary_ref"],
            "read_phases": {"prepare": "metadata, frozen source code, saved numerical observations only",
                            "execute_authorized": "source XML, original parameters/extensions/cross, receptor coordinates"},
            "limits": ["New original arm vectors are new observations; the prior oracle saved no force vectors.",
                       "Native term forces are absent; term arm deltas are OpenMM-only differences.",
                       "Residual reduction cannot establish a root cause or change the frozen gate/failure.",
                       "No source admission, pose recovery, qualification or speed claim."]}
    write_json(output / "plan.json", plan)
    return pin(output / "plan.json", allowed_paths=[output / "plan.json"])


def validate_numerical_roles(refs, oracle):
    # Stat/path metadata is allowed here; no molecular bytes are opened.
    require(type(refs) is dict and set(refs) == NUMERICAL_ROLES, "exact_numerical_role_set_required")
    expected_hashes = {**oracle.ORIGINAL_SHA256, "ligand_xml": oracle.XML_SHA256["ligand"],
                       "receptor_xml": oracle.XML_SHA256["receptor"]}
    expected_names = {"ligand_xml": "ligand-unconstrained-openmm-system.xml", "receptor_xml": "openmm-system.xml",
                      "receptor_coordinates": "receptor-canonical.json", "parameters": "parameters.json",
                      "extensions": "extensions.json", "cross_parameters": "cross-parameters.json"}
    for role, ref in refs.items():
        require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "exact_file_pin_required")
        require(Path(ref["path"]).name == expected_names[role], "numerical_role_filename_mismatch")
        validate_path(ref["path"])
        require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= 32 * 1024 * 1024,
                "bounded_input_required")
        require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64, "sha256_required")
        if role in expected_hashes:
            require(ref["sha256"] == expected_hashes[role], "fixed_numerical_source_hash_required")


def validate_plan_input_bindings(plan, oracle):
    require(Path(plan["frozen_terminal_campaign_root"]) == FROZEN_R2, "fixed_terminal_metadata_root_required")
    expected_paths = {"terminal_plan": FROZEN_R2 / "plan.json", "oracle_input_spec": FROZEN_R2 / "oracle-input-spec.json",
                      "saved_endpoint_states": FROZEN_R2 / "campaign" / CASE / "native/endpoint-states.json",
                      "saved_oracle_receipt": FROZEN_R2 / "campaign" / CASE / "oracle/numerical-receipt.json"}
    require(set(plan["metadata_refs"]) == set(expected_paths), "exact_metadata_roles_required")
    require(all(plan["metadata_refs"][role]["path"] == str(path) for role, path in expected_paths.items()),
            "fixed_metadata_paths_required")
    old_plan = oracle.loads(read_ref(plan["metadata_refs"]["terminal_plan"]))
    spec = oracle.loads(read_ref(plan["metadata_refs"]["oracle_input_spec"]))
    require(set(spec["original_parameter_refs"]) == set(oracle.IDENTITIES), "exact_spec_roles_required")
    case = next(case for case in old_plan["cases"] if case["case_id"] == CASE)
    expected = {"ligand_xml": spec["ligand_xml_ref"], "receptor_xml": spec["receptor_xml_ref"],
                "receptor_coordinates": case["derived_input_refs"]["receptor"], **spec["original_parameter_refs"]}
    require(plan["numerical_input_refs"] == expected, "exact_terminal_numerical_refs_required")
    validate_numerical_roles(plan["numerical_input_refs"], oracle)


def numerical_inputs(plan, oracle, events):
    validate_plan_input_bindings(plan, oracle)
    values = {}
    for name, ref in plan["numerical_input_refs"].items():
        start = time.perf_counter()
        raw = read_ref(ref)
        events.append({"role": name, "phase": "authorized_numerical", "ref": ref,
                       "wall_seconds": time.perf_counter() - start, "status": "completed"})
        values[name] = raw
    require({name: plan["numerical_input_refs"][name]["sha256"] for name in oracle.IDENTITIES}
            == oracle.ORIGINAL_SHA256, "original_parameter_hashes_changed")
    require({name: plan["numerical_input_refs"][name + "_xml"]["sha256"] for name in ("ligand", "receptor")}
            == oracle.XML_SHA256, "source_xml_hashes_changed")
    parameters = {name: oracle.loads(values[name]) for name in oracle.IDENTITIES}
    base, ext, cross = (parameters[name] for name in oracle.IDENTITIES)
    require(base["topology_sha256"] == ext["topology_sha256"] == cross["ligand_topology_sha256"]
            and oracle.value_hash(base) == ext["base_parameter_fingerprint_sha256"] == cross["ligand_base_parameters_sha256"],
            "original_parameter_identity_mismatch")
    require(ext["metadata"]["source_xml_sha256"] == oracle.XML_SHA256["ligand"]
            and cross["parameter_source_sha256"] == oracle.XML_SHA256["receptor"], "source_parameter_binding_mismatch")
    require(not ext["constraints"] and not ext["impropers"]
            and ext["nonbonded_domain"] == "nocutoff_equivalent_inside_switch"
            and cross["mixing_rule"] == "lorentz_berthelot"
            and cross["pair_policy"] == "all_non_covalent_cross_pairs_no_exclusions", "unsupported_numeric_terms")
    require(base["dielectric"] == 1.0 and base["screening_kappa_per_angstrom"] == 0.0
            and 0 < base["switch_start_angstrom"] < base["cutoff_angstrom"]
            and 0 < cross["switch_start_angstrom"] < cross["cutoff_angstrom"]
            and cross["dielectric"] > 0 and cross["screening_kappa_per_angstrom"] >= 0, "unsupported_domain")
    inventories = {name: oracle.source_xml_inventory(values[name + "_xml"], name == "ligand")
                   for name in ("ligand", "receptor")}
    receptor = oracle.canonical_coordinates(oracle.loads(values["receptor_coordinates"]), len(cross["receptor_atoms"]))
    endpoints = oracle.loads(read_ref(plan["metadata_refs"]["saved_endpoint_states"]))
    require(endpoints["case_id"] == CASE and endpoints["schema_id"] == oracle.ENDPOINT_SCHEMA, "saved_state_identity")
    require([{ "label": state["label"], "stored_observation_sha256": oracle.value_hash(state),
               "coordinates_sha256": oracle.value_hash(state["coordinates"]),
               "native_total_forces_sha256": oracle.value_hash(state["forces"])} for state in endpoints["states"]]
            == plan["saved_state_pins"], "saved_states_changed")
    return endpoints, receptor, parameters, values["ligand_xml"], values["receptor_xml"], inventories


def execute_plan(plan_path, plan_sha256, output, *, numerical_phase_authorized=False):
    require(numerical_phase_authorized, "explicit_numerical_phase_authorization_required")
    plan_ref = pin(plan_path, allowed_paths=[plan_path])
    require(plan_ref["sha256"] == plan_sha256, "exact_plan_hash_required")
    plan = json.loads(read_ref(plan_ref))
    require(plan["schema_id"] == PLAN_SCHEMA and plan["case_id"] == CASE and not plan["campaign_resume_allowed"], "prospective_plan_required")
    require(pin(__file__, allowed_paths=[__file__]) == plan["source_refs"]["diagnostic"], "executing_snapshot_pin_mismatch")
    require(plan["protocol_counts"] == {"context_create": 4, "set_positions": 8, "get_state": 16}
            and plan["frozen_gate"] == TOLERANCE and plan["arms"] == list(ARMS)
            and plan["states"] == list(LABELS), "fixed_protocol_required")
    executable = Path(sys.executable).resolve()
    require(pin(executable, allowed_paths=[executable]) == plan["python_binary_ref"], "python_binary_changed")
    output = Path(output)
    require(output.is_absolute() and not output.exists() and output.parent.resolve() == output.parent
            and not output.is_relative_to(Path(plan["frozen_terminal_campaign_root"])), "new_noncampaign_output_required")
    require(set(plan["source_refs"]) == {"diagnostic", "frozen_oracle", "tests", "plan_document"}, "exact_source_roles_required")
    oracle = load_oracle(plan["source_refs"]["frozen_oracle"])
    validate_plan_input_bindings(plan, oracle)
    for ref in plan["source_refs"].values():
        read_ref(ref)
    for ref in plan["metadata_refs"].values():
        read_ref(ref)
    output.mkdir(mode=0o700)
    input_events = []
    ledger_stream = (output / "call-events.jsonl").open("x")
    def sink(event):
        ledger_stream.write(canonical(event).decode() + "\n")
        ledger_stream.flush()
        os.fsync(ledger_stream.fileno())
    ledger = CallLedger(sink)
    receipt = None
    enclosing_start, cpu_start = time.perf_counter(), time.process_time()
    try:
        inputs = numerical_inputs(plan, oracle, input_events)
        sys.path.insert(0, plan["dependency_site"])
        boundary = RealBoundary(oracle)
        receipt = run_diagnostic(oracle=oracle, endpoints=inputs[0], receptor_coordinates=inputs[1], parameters=inputs[2],
                                 ligand_xml=inputs[3], receptor_xml=inputs[4], backend=boundary, ledger=ledger)
        receipt["source_xml_inventory"] = inputs[5]
        receipt["environment"] = boundary.environment()
        for ref in [*plan["source_refs"].values(), *plan["metadata_refs"].values(), *plan["numerical_input_refs"].values()]:
            read_ref(ref)
    except Exception as exc:
        if receipt is None:
            receipt = {"schema_id": SCHEMA, "case_id": CASE, "status": "failed", "call_accounting": ledger.receipt(),
                       "actual_openmm_observations": any(row["kind"] == "get_state" and row["status"] == "completed"
                                                          for row in ledger.rows)}
        receipt.update(status="failed", failure={"type": type(exc).__name__, "reason": str(exc)})
    finally:
        ledger_stream.close()
    receipt.update(plan_ref=plan_ref, input_reads=input_events, input_refs=plan["numerical_input_refs"],
                   source_refs=plan["source_refs"], stored_state_pins=plan["saved_state_pins"],
                   actual_execution_performed=True, entry_enclosing_wall_seconds=time.perf_counter() - enclosing_start,
                   entry_enclosing_process_cpu_seconds=time.process_time() - cpu_start,
                   entry_enclosing_costs_must_not_be_added_to_nested_execution_or_leaf_costs=True,
                   frozen_campaign_modified_or_resumed=False, frozen_gate=TOLERANCE,
                   cause_established=False, scientifically_validated=False,
                   native_term_force_vectors_available=False)
    receipt["receipt_sha256"] = digest(canonical(receipt))
    write_json(output / "receipt.json", receipt)
    return pin(output / "receipt.json", allowed_paths=[output / "receipt.json"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare")
    for name in ("r2", "output", "test-source", "document-source"):
        prepare.add_argument("--" + name, required=True)
    execute = sub.add_parser("execute")
    for name in ("plan", "plan-sha256", "output"):
        execute.add_argument("--" + name, required=True)
    execute.add_argument("--numerical-phase-authorized", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "prepare":
        ref = prepare_plan(args.r2, args.output, args.test_source, args.document_source)
    else:
        ref = execute_plan(args.plan, args.plan_sha256, args.output,
                           numerical_phase_authorized=args.numerical_phase_authorized)
    print(json.dumps(ref, sort_keys=True))
    if args.action == "execute" and json.loads(read_ref(ref))["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
