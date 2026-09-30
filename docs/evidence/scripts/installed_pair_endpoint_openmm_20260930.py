"""Fresh source-driven OpenMM arithmetic at retained installed pair endpoints.

Uses the saved installed energy/components/forces as the native observation.
No native evaluator, scorer or optimizer is called. Direct source XML internal
plus declared cross arithmetic and D3 same-math arithmetic remain separate.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def ref(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def checked(item):
    raw = Path(item["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item["sha256"] or ("bytes" in item and len(raw) != item["bytes"]):
        raise ValueError("immutable_endpoint_input_changed:" + item["path"])
    return raw


def sealed(value, field):
    if value.get(field) != digest({k: v for k, v in value.items() if k != field}):
        raise ValueError("invalid_endpoint_" + field)


def numbers(values):
    result = []
    for row in values:
        if type(row) is not list or len(row) != 3:
            raise ValueError("endpoint_array_requires_three_components")
        atoms = []
        for item in row:
            if type(item) is not str:
                raise ValueError("endpoint_requires_canonical_binary64_hex")
            number = float.fromhex(item)
            if not math.isfinite(number) or number.hex() != item:
                raise ValueError("endpoint_nonfinite_or_noncanonical_scalar")
            atoms.append(number)
        result.append(atoms)
    return np.asarray(result, dtype=np.float64)


def publish(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def scalar(item):
    if type(item) is not str:
        raise ValueError("endpoint_requires_canonical_binary64_hex_scalar")
    number = float.fromhex(item)
    if not math.isfinite(number) or number.hex() != item:
        raise ValueError("endpoint_nonfinite_or_noncanonical_scalar")
    return number


def executing_sources(protocol, oracle):
    for key, executed in (("oracle_source", Path(oracle.__file__)), ("wrapper_source", Path(__file__))):
        checked(protocol[key])
        if Path(protocol[key]["path"]).resolve() != executed.resolve() or ref(executed)["sha256"] != protocol[key]["sha256"]:
            raise ValueError("executing_source_not_protocol_pinned:" + key)
    checked(protocol["trace_source"])
    if oracle.ENERGY_ABSOLUTE_TOLERANCE != 1e-8 or oracle.FORCE_ABSOLUTE_TOLERANCE != 1e-8:
        raise ValueError("executing_oracle_tolerance_not_unchanged")


@contextmanager
def counted_reference_contexts(oracle, work):
    original = oracle._reference_context
    class CountedContext:
        def __init__(self, context):
            self.context = context
        def __getattr__(self, name):
            return getattr(self.context, name)
        def getState(self, *args, **kwargs):
            work["attempted_getState_energy_force_observations"] += 1
            try:
                state = self.context.getState(*args, **kwargs)
            except BaseException as exc:
                work["failed_getState_energy_force_observations"] += 1
                if not isinstance(exc, Exception):
                    work["interrupted_getState_completion_unknown"] += 1
                raise
            work["completed_getState_energy_force_observations"] += 1
            return state
    def context(system, openmm):
        value, integrator = original(system, openmm)
        return CountedContext(value), integrator
    oracle._reference_context = context
    try:
        yield
    finally:
        oracle._reference_context = original


def endpoint(model, oracle, trace_source_sha256):
    import openmm
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
    from betelgeuze_product.reference_minimization_workflow import _parameters
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters
    from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import OpenMMPeriodicParameters

    request = json.loads(checked(model["source_request"]))
    for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        checked(request[key])
    native = json.loads(checked(model["installed_result"]))
    sealed(native, "result_sha256")
    sealed(native["binding"], "receipt_sha256")
    if native["binding"]["input_files"] != {key: request[key] for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters")}:
        raise ValueError("installed_endpoint_does_not_use_immutable_source_model")
    numerical = native["numerical_result"]
    sealed(numerical, "result_sha256")
    sealed(numerical["checkpoint"], "checkpoint_sha256")
    current = numerical["checkpoint"]["state"]["current"]
    if current is None:
        raise ValueError("installed_endpoint_has_no_observed_current_state")
    xyz, force = numbers(current["coordinates"]), numbers(current["forces"])
    energy = scalar(current["energy"])
    components = {key: scalar(value) for key, value in current["components"].items()}
    if set(components) != {"ligand_internal", "cross_lennard_jones", "cross_screened_coulomb", "total"}:
        raise ValueError("installed_component_contract_not_declared_reference")
    exported = json.loads(checked(model["final_coordinates"]))
    if set(exported) != {"coordinates_angstrom"}:
        raise ValueError("exclusive_final_coordinate_document_required")
    expected = np.asarray(exported["coordinates_angstrom"], dtype=np.float64)
    if xyz.shape != expected.shape or not np.array_equal(xyz.view(np.uint64), expected.view(np.uint64)):
        raise ValueError("endpoint_coordinates_not_binary64_exact_to_retained_export")
    if force.shape != xyz.shape:
        raise ValueError("endpoint_force_atom_count_mismatch")
    maximum_pair = max((math.dist(a, b) for i, a in enumerate(xyz) for b in xyz[:i]), default=0.)
    if not math.isfinite(maximum_pair) or maximum_pair >= 90.:
        raise ValueError("final_coordinate_NoCutoff_90_angstrom_domain_exceeded")
    ligand = all_atom_system_from_canonical_json(checked(request["ligand"]).decode("ascii"))
    receptor = all_atom_system_from_canonical_json(checked(request["receptor"]).decode("ascii"))
    base = _parameters(json.loads(checked(request["parameters"])))
    extension = OpenMMPeriodicParameters.from_dict(json.loads(checked(request["extensions"])), base)
    cross = CrossParameters.from_dict(json.loads(checked(request["cross_parameters"])))
    ligand_xml, receptor_xml = checked(model["ligand_xml"]), checked(model["receptor_xml"])
    if extension.metadata["source_xml_sha256"] != hashlib.sha256(ligand_xml).hexdigest():
        raise ValueError("source_ligand_XML_not_bound_to_endpoint_model")
    if cross.parameter_source_sha256 != hashlib.sha256(receptor_xml).hexdigest():
        raise ValueError("source_receptor_XML_not_bound_to_endpoint_model")
    if base.switch_start_angstrom != 90. or extension.nonbonded_domain != "nocutoff_equivalent_inside_switch":
        raise ValueError("unchanged_NoCutoff_domain_contract_required")
    domain = json.loads(checked(model["trace_domain"]))
    domain_bound = domain.get("trace_files", {}).get("result.json") == model["installed_result"]["sha256"]
    full_trace_passed = (domain.get("schema_id") == "retained_cartesian_nocutoff_domain/1"
        and domain.get("status") == "passed"
        and domain.get("source_sha256") == trace_source_sha256
        and domain.get("no_new_force_score_graph_or_optimization_calls") is True
        and domain.get("work", {}).get("actual_force_calls") is not None
        and domain.get("work", {}).get("unknown_pending_attempts") == 0
        and domain.get("full_retained_trace_source_domain_claim_passed") is True and domain_bound)
    original = oracle._grouped_source(ligand_xml, openmm)
    receptor_source = openmm.XmlSerializer.deserialize(receptor_xml.decode("ascii"))
    correspondence = {
        "ligand": oracle._source_parameter_correspondence(original, base.atom_parameters, openmm, "ligand"),
        "receptor": oracle._source_parameter_correspondence(receptor_source, cross.receptor_atoms, openmm, "receptor")}
    if xyz.shape != (ligand.atom_count, 3):
        raise ValueError("source_and_endpoint_atom_count_mismatch")
    source_context, source_integrator = oracle._reference_context(original, openmm)
    math_context, math_integrator = oracle._reference_context(oracle.same_math_internal_system(ligand_xml, openmm), openmm)
    cross_context, cross_integrator = oracle._reference_context(
        oracle.cross_reference_system(original, receptor_source, cross, openmm), openmm)
    source_energy, source_force = oracle._observe(source_context, xyz, openmm)
    math_energy, math_force = oracle._observe(math_context, xyz, openmm)
    combined = np.concatenate((xyz, receptor.coordinates[0].numpy()), axis=0)
    cross_energy, all_cross_force = oracle._observe(cross_context, combined, openmm)
    cross_force = all_cross_force[:ligand.atom_count]
    cross_components = {name: oracle._observe(cross_context, combined, openmm, [group])[0]
        for group, name in enumerate(("cross_lennard_jones", "cross_screened_coulomb"))}
    expected_components = {"ligand_internal": math_energy, **cross_components, "total": math_energy + cross_energy}
    if set(components) != set(expected_components):
        raise ValueError("installed_component_contract_not_declared_reference")
    same_metrics = oracle._metrics(energy, math_energy + cross_energy, force, math_force + cross_force)
    component_errors = {key: abs(components[key] - value) for key, value in expected_components.items()}
    direct_metrics = oracle._metrics(energy, source_energy + cross_energy, force, source_force + cross_force)
    direct_internal_energy_error = abs(components["ligand_internal"] - source_energy)
    force_classes = {}
    for group, name in oracle.GROUP_NAMES.items():
        se, sf = oracle._observe(source_context, xyz, openmm, [group])
        me, mf = oracle._observe(math_context, xyz, openmm, [group])
        force_classes[name] = {"source_energy_kcal_per_mol": se, "same_math_energy_kcal_per_mol": me,
            "source_minus_same_math_energy_kcal_per_mol": se - me, "source_vs_same_math": oracle._metrics(se, me, sf, mf)}
    del source_context, source_integrator, math_context, math_integrator, cross_context, cross_integrator
    builtin = oracle._measure_builtin_coulomb_constant(openmm)
    same_passed = same_metrics["passed"] and all(v <= 1e-8 for v in component_errors.values())
    direct_passed = direct_metrics["passed"] and direct_internal_energy_error <= 1e-8
    for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        checked(request[key])
    for item in model.values():
        checked(item)
    return {"schema_id": "installed_pair_final_source_openmm_point/1", "same_math_point_passed": same_passed,
        "source_XML_internal_plus_declared_cross_point_passed": direct_passed,
        "full_retained_trace_source_domain_claim_passed": full_trace_passed,
        "full_trace_domain_report_bound_to_this_installed_result": domain_bound,
        "coordinates_binary64_exact": True, "coordinates_sha256": digest(current["coordinates"]),
        "maximum_final_intraligand_pair_distance_angstrom": maximum_pair,
        "same_math_total": same_metrics, "same_math_component_energy_errors_kcal_per_mol": component_errors,
        "direct_source_internal_energy_error_kcal_per_mol": direct_internal_energy_error,
        "direct_source_internal_plus_declared_cross_total": direct_metrics, "source_force_class_deltas": force_classes,
        "reference": {"source_XML_internal_energy": source_energy, "same_math_internal_energy": math_energy,
            "cross_energy": cross_energy, "cross_components": cross_components,
            "source_XML_internal_forces": source_force.tolist(), "same_math_internal_forces": math_force.tolist(),
            "declared_cross_forces": cross_force.tolist()},
        "installed_native_energy": energy, "installed_native_components": components, "installed_native_forces": force.tolist(),
        "source_particle_parameter_correspondence_max_errors": correspondence,
        "source_XML_exact_mathematical_equivalence_claimed": False,
        "combined_source_complex_XML_exists": False, "intrareceptor_energy_evaluated": False,
        "coulomb_constants": {"native_and_same_math": oracle.COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
            "OpenMM_builtin_measured": builtin, "native_minus_builtin": oracle.COULOMB_KCAL_ANGSTROM_PER_MOL_E2 - builtin},
        "new_native_force_calls": 0, "new_score_or_optimization_calls": 0,
        "retained_installed_numerical_work": numerical["work"], "full_trace_work": domain.get("work"),
        "energy_absolute_tolerance_kcal_per_mol": 1e-8,
        "force_component_absolute_tolerance_kcal_per_mol_angstrom": 1e-8,
        "openmm_version": openmm.version.version, "reference_platform": "Reference",
        "qualification_affinity_pose_recovery_HIP_training_or_service": False}


def validate_protocol(protocol, oracle):
    if (protocol.get("schema_id") != "installed_pair_final_source_openmm_protocol/1"
            or protocol.get("planned_candidates") != ["PR49", "PR59"]
            or protocol.get("energy_absolute_tolerance_kcal_per_mol") != 1e-8
            or protocol.get("force_component_absolute_tolerance_kcal_per_mol_angstrom") != 1e-8
            or set(protocol.get("models", {})) != {"PR49", "PR59"}):
        raise ValueError("unchanged_predeclared_final_endpoint_protocol_required")
    executing_sources(protocol, oracle)


def recover_retained_evidence(model):
    evidence = {"retained_installed_numerical_work": None, "full_trace_work": None,
        "retained_installed_result_sha256": None}
    try:
        saved = json.loads(checked(model["installed_result"]))
        sealed(saved, "result_sha256")
        numerical = saved["numerical_result"]
        sealed(numerical, "result_sha256")
        evidence["retained_installed_numerical_work"] = numerical["work"]
        evidence["retained_installed_result_sha256"] = saved["result_sha256"]
    except (ValueError, KeyError, TypeError, OSError):
        pass
    try:
        evidence["full_trace_work"] = json.loads(checked(model["trace_domain"])).get("work")
    except (ValueError, KeyError, TypeError, OSError):
        pass
    return evidence


def run_protocol(protocol, oracle, output_directory, evaluate=endpoint):
    start = time.perf_counter()
    results, failures = {}, []
    interruption = None
    protocol_error = None
    try:
        validate_protocol(protocol, oracle)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        protocol_error = {"error_type": type(exc).__name__, "reason": str(exc)}
    for candidate in ["PR49", "PR59"]:
        work = {"attempted_getState_energy_force_observations": 0,
            "completed_getState_energy_force_observations": 0, "failed_getState_energy_force_observations": 0,
            "interrupted_getState_completion_unknown": 0}
        try:
            if interruption is not None:
                raise ValueError("reference_execution_skipped_after_interruption:" + interruption)
            if protocol_error is not None:
                raise ValueError("protocol_validation_blocked:" + protocol_error["reason"])
            executing_sources(protocol, oracle)
            with counted_reference_contexts(oracle, work):
                report = evaluate(protocol["models"][candidate], oracle, protocol["trace_source"]["sha256"])
            executing_sources(protocol, oracle)
            report.update(status="evaluated", reference_work=work,
                new_OpenMM_getState_energy_force_observations=work["attempted_getState_energy_force_observations"])
        except BaseException as exc:
            if not isinstance(exc, Exception):
                interruption = type(exc).__name__
            report = {"schema_id": "installed_pair_final_source_openmm_point/1", "status": "blocked",
                "error_type": type(exc).__name__, "reason": str(exc), "reference_work": work,
                "reference_run_interrupted": not isinstance(exc, Exception),
                "reference_execution_skipped_after_interruption": interruption is not None and isinstance(exc, Exception),
                "same_math_point_passed": False, "source_XML_internal_plus_declared_cross_point_passed": False,
                "full_retained_trace_source_domain_claim_passed": False,
                "new_native_force_calls": 0, "new_score_or_optimization_calls": 0,
                "new_OpenMM_getState_energy_force_observations": work["attempted_getState_energy_force_observations"],
                **recover_retained_evidence(protocol.get("models", {}).get(candidate, {})),
                "scientific_qualification": False}
            failures.append(candidate)
        output = Path(output_directory) / (candidate + "-final-openmm.json")
        publish(output, report)
        results[candidate] = {"report": ref(output), "status": report["status"],
            "same_math_point_passed": report["same_math_point_passed"],
            "direct_source_point_passed": report["source_XML_internal_plus_declared_cross_point_passed"],
            "full_trace_domain_passed": report["full_retained_trace_source_domain_claim_passed"],
            "reference_work": work, "same_math_total": report.get("same_math_total")}
    summary = {"schema_id": "installed_pair_final_source_openmm_results/1", "models": results,
        "point_denominator": {"requested": 2, "evaluated": sum(r["status"] == "evaluated" for r in results.values()),
            "blocked": len(failures), "same_math_passed": sum(r["same_math_point_passed"] for r in results.values()),
            "direct_source_passed": sum(r["direct_source_point_passed"] for r in results.values())},
        "full_trace_domain_denominator": {"requested": 2, "passed": sum(r["full_trace_domain_passed"] for r in results.values())},
        "reference_work": {key: sum(r["reference_work"][key] for r in results.values())
            for key in ("attempted_getState_energy_force_observations", "completed_getState_energy_force_observations", "failed_getState_energy_force_observations", "interrupted_getState_completion_unknown")},
        "protocol_error": protocol_error, "interruption": interruption, "new_native_force_calls": 0, "new_score_or_optimization_calls": 0,
        "elapsed_fresh_endpoint_reference_seconds": time.perf_counter() - start, "scientific_qualification": False}
    summary["point_audit_status"] = ("passed" if summary["point_denominator"]["same_math_passed"] == 2
        and summary["point_denominator"]["direct_source_passed"] == 2 else "failed")
    summary["full_trace_domain_status"] = "passed" if summary["full_trace_domain_denominator"]["passed"] == 2 else "blocked"
    summary["status"] = "passed" if summary["point_audit_status"] == summary["full_trace_domain_status"] == "passed" else "blocked"
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.checkout))
    from tools.analysis import openmm_d3_numerical_audit as oracle
    protocol = json.loads(args.protocol.read_bytes())
    summary = run_protocol(protocol, oracle, args.output_directory)
    summary["protocol"] = ref(args.protocol)
    publish(args.output_directory / "results.json", summary)
    print(json.dumps(summary, sort_keys=True))
    if summary["status"] != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
