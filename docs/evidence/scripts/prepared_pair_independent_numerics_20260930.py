"""Independent source support, unconstrained derivation and paired point audits.

Reuses the retained source-driven OpenMM oracle without changing its equations or
1e-8 tolerances. Source XML builtin observations and D3 same-math observations
remain separate. Exclusive publication; no preparer, scorer or optimizer call.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from xml.etree import ElementTree as ET

import numpy as np
import torch


def ref(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def checked(item):
    raw = Path(item["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item["sha256"] or ("bytes" in item and len(raw) != item["bytes"]):
        raise ValueError("immutable_input_binding_mismatch:" + item["path"])
    return raw


def publish(path, document):
    with Path(path).open("x") as stream:
        json.dump(document, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def node_value(node):
    return [node.tag, dict(sorted(node.attrib.items())), [node_value(child) for child in node]]


def pair_rows(node, path):
    result = {}
    for row in node.findall(path):
        pair = tuple(sorted((int(row.attrib["p1"]), int(row.attrib["p2"]))))
        if pair in result:
            raise ValueError("duplicate_source_pair")
        result[pair] = dict(row.attrib)
    return result


def derivation_check(original_xml, derived_xml, ligand):
    """Recompute term correspondence independently of preparer declarations."""
    old, new = ET.fromstring(original_xml), ET.fromstring(derived_xml)
    constraints = pair_rows(old, "Constraints/Constraint")
    before = {force.attrib["type"]: force for force in old.find("Forces")}
    after = {force.attrib["type"]: force for force in new.find("Forces")}
    old_bonds = pair_rows(before["HarmonicBondForce"], "Bonds/Bond")
    new_bonds = pair_rows(after["HarmonicBondForce"], "Bonds/Bond")
    added = set(new_bonds) - set(old_bonds)
    graph = {tuple(sorted((bond.atom_i, bond.atom_j))) for bond in ligand.bonds}
    unchanged = {kind: node_value(before[kind]) == node_value(after[kind])
                 for kind in before if kind != "HarmonicBondForce"}
    result = {
        "original_constraint_count": len(constraints),
        "derived_constraint_count": len(new.find("Constraints")),
        "original_harmonic_bond_count": len(old_bonds),
        "derived_harmonic_bond_count": len(new_bonds),
        "restored_harmonic_pair_count": len(added),
        "restored_pairs_equal_original_constraint_pairs": added == set(constraints),
        "source_harmonic_bond_rows_preserved": all(new_bonds.get(pair) == row for pair, row in old_bonds.items()),
        "derived_harmonic_pairs_equal_canonical_graph": set(new_bonds) == graph,
        "restored_equilibrium_lengths_equal_original_constraint_lengths": all(new_bonds.get(pair, {}).get("d") == row["d"] for pair, row in constraints.items()),
        "particle_records_unchanged": node_value(old.find("Particles")) == node_value(new.find("Particles")),
        "unchanged_other_force_classes": unchanged,
        "constrained_dynamics_equivalence_claimed": False,
        "scope": "independent_serialized_term_and_graph_correspondence_not_parameter_assignment_reinference",
    }
    result["passed"] = (not result["derived_constraint_count"] and result["restored_pairs_equal_original_constraint_pairs"]
        and result["source_harmonic_bond_rows_preserved"] and result["derived_harmonic_pairs_equal_canonical_graph"]
        and result["restored_equilibrium_lengths_equal_original_constraint_lengths"]
        and result["particle_records_unchanged"] and all(unchanged.values()))
    if not result["passed"]:
        raise ValueError("unconstrained_derivation_term_correspondence_failed")
    return result


def audit_source_support(model, request, ligand, oracle, translator):
    from betelgeuze_product.reference_minimization_workflow import _parameters
    from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import OpenMMPeriodicParameters
    base = _parameters(json.loads(checked(request["parameters"])))
    extension = OpenMMPeriodicParameters.from_dict(json.loads(checked(request["extensions"])), base)
    settings = translator.TranslationSettings(base.parameter_set_id, base.cutoff_angstrom,
        base.switch_start_angstrom, base.applicability_domain.minimum_pair_distance_angstrom)
    raw = checked(model["ligand_xml"])
    conversion = translator.convert_openmm_system(raw, ligand, settings)
    energetic_fields = ("atom_parameters", "bonds", "angles", "torsions", "excluded_pairs", "scaled_pairs",
                        "cutoff_angstrom", "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom")
    matches = {name: getattr(base, name) == getattr(conversion.base_parameters, name) for name in energetic_fields}
    matches.update(periodic_impropers=extension.periodic_impropers == conversion.parameters.periodic_impropers,
        constant_energy_offset=extension.constant_energy_offset_kcal_per_mol == conversion.parameters.constant_energy_offset_kcal_per_mol)
    if not all(matches.values()):
        raise ValueError("complete_source_translation_parameter_correspondence_failed:" + str(matches))
    original = checked(model["original_constrained_xml"])
    try:
        translator.convert_openmm_system(original, ligand, settings)
    except translator.OpenMMD3TranslationError as exc:
        rejection = {"status": "rejected", "code": exc.code, "reason": str(exc)}
    else:
        raise ValueError("original_constrained_xml_unexpectedly_accepted")
    if rejection["code"] not in {"constrained_bond_terms_missing", "constrained_system_unsupported"}:
        raise ValueError("original_constraint_rejection_not_established:" + rejection["code"])
    return {"declared_unconstrained_source_terms_supported": True,
        "complete_energetic_parameter_correspondence": matches,
        "translation_inventory": conversion.inventory,
        "original_constrained_source_not_supported": rejection,
        "unconstrained_derivation": derivation_check(original, raw, ligand),
        "source_xml_builtin_arithmetic_equivalence_claimed": False,
        "projection_scope": "complete_supported_source_terms_with_declared_D3_Coulomb_constant_and_runtime_NoCutoff_distance_guard"}


def direct_source_components(audit, ligand_xml, oracle):
    import openmm
    original = oracle._grouped_source(ligand_xml, openmm)
    same_math = oracle.same_math_internal_system(ligand_xml, openmm)
    original_context, original_integrator = oracle._reference_context(original, openmm)
    math_context, math_integrator = oracle._reference_context(same_math, openmm)
    row = audit["snapshots"][0]
    coordinates = np.asarray(row["coordinates_angstrom"], dtype=np.float64)
    components = {}
    for group, name in oracle.GROUP_NAMES.items():
        source_energy, source_force = oracle._observe(original_context, coordinates, openmm, [group])
        math_energy, math_force = oracle._observe(math_context, coordinates, openmm, [group])
        components[name] = {
            "source_xml_builtin_energy_kcal_per_mol": source_energy,
            "same_math_reference_energy_kcal_per_mol": math_energy,
            "native_component_energy_kcal_per_mol": row["native"]["source_aligned_internal_components"][name],
            "source_minus_same_math_energy_kcal_per_mol": source_energy - math_energy,
            "native_minus_source_energy_kcal_per_mol": row["native"]["source_aligned_internal_components"][name] - source_energy,
            "source_vs_same_math": oracle._metrics(source_energy, math_energy, source_force, math_force),
            "source_xml_builtin_forces_kcal_per_mol_angstrom": source_force.tolist(),
            "same_math_forces_kcal_per_mol_angstrom": math_force.tolist(),
        }
    direct = oracle._metrics(row["native"]["internal_energy"], row["original_XML"]["internal_energy"],
        row["native"]["internal_forces"], row["original_XML"]["internal_forces"])
    del original_context, original_integrator, math_context, math_integrator
    return {"components": components, "native_internal_vs_source_xml_builtin": direct,
        "source_xml_builtin_point_agreement_passed_at_unchanged_1e_minus_8": direct["passed"],
        "fixed_coordinates_and_units_identical": True,
        "only_force_group_annotation_changed_for_component_observations": True,
        "source_xml_bytes_changed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.checkout))
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
    from tools.analysis import openmm_d3_numerical_audit as oracle
    from tools.product import openmm_d3_translation as translator
    protocol = json.loads(args.protocol.read_bytes())
    if (protocol["schema_id"] != "prepared_pair_independent_single_point_protocol/1"
            or protocol["planned_candidates"] != ["PR49", "PR59"]
            or protocol["snapshots_per_candidate"] != ["initial"] or protocol["perturbations"] != 0
            or protocol["energy_absolute_tolerance_kcal_per_mol"] != 1e-8
            or protocol["force_component_absolute_tolerance_kcal_per_mol_angstrom"] != 1e-8):
        raise ValueError("predeclared_pair_protocol_mismatch")
    checked(protocol["wrapper_source"])
    checked(protocol["oracle_source"])
    checked(protocol["translator_source"])
    torch.set_num_threads(1)
    results = {}
    start = time.perf_counter()
    for candidate in protocol["planned_candidates"]:
        model = protocol["models"][candidate]
        for item in model.values():
            checked(item)
        request = json.loads(checked(model["request"]))
        for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
            checked(request[key])
        ligand = all_atom_system_from_canonical_json(checked(request["ligand"]).decode("ascii"))
        source_support = audit_source_support(model, request, ligand, oracle, translator)
        publish(args.output_directory / (candidate + "-source-support.json"), source_support)
        observation = oracle.audit(model["request"]["path"], model["ligand_xml"]["path"], model["receptor_xml"]["path"],
            perturbations=0, seed=20260930, perturbation_angstrom=.001)
        if observation["denominator"] != {"requested": 1, "evaluated": 1, "passed": 1, "rejected": 0}:
            publish(args.output_directory / (candidate + "-same-math.json"), observation)
            raise ValueError("predeclared_single_point_denominator_not_passed")
        direct = direct_source_components(observation, checked(model["ligand_xml"]), oracle)
        publish(args.output_directory / (candidate + "-same-math.json"), observation)
        publish(args.output_directory / (candidate + "-direct-source.json"), direct)
        results[candidate] = {
            "source_support": ref(args.output_directory / (candidate + "-source-support.json")),
            "same_math": ref(args.output_directory / (candidate + "-same-math.json")),
            "direct_source": ref(args.output_directory / (candidate + "-direct-source.json")),
            "same_math_checks_passed": observation["all_same_math_checks_passed"],
            "native_internal_vs_source_xml_builtin": direct["native_internal_vs_source_xml_builtin"],
            "coulomb_constants": observation["coulomb_constants_kcal_angstrom_per_mol_e2"],
            "coordinates_sha256": observation["snapshots"][0]["coordinates_sha256"],
            "native_internal_energy_kcal_per_mol": observation["snapshots"][0]["native"]["internal_energy"],
            "native_cross_energy_kcal_per_mol": sum(observation["snapshots"][0]["native"]["cross_components"].values()),
        }
        for item in model.values():
            checked(item)
        for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
            checked(request[key])
    elapsed = time.perf_counter() - start
    checked(protocol["wrapper_source"])
    checked(protocol["oracle_source"])
    checked(protocol["translator_source"])
    result = {"schema_id": "prepared_pair_independent_single_point_results/1", "protocol": ref(args.protocol),
        "models": results, "denominator": {"requested": 2, "evaluated": 2, "same_math_passed": 2, "rejected": 0},
        "native_source_xml_builtin_equivalence_claimed": False,
        "scientific_qualification": False, "training_or_role_admission": False,
        "affinity_pose_recovery_HIP_service_validated": False,
        "elapsed_review_and_single_point_seconds": elapsed,
        "timing_excludes": ["preparation", "training", "optimization", "wheel_install", "outer_startup", "final_result_publication"],
        "nested_snapshot_timings_do_not_sum": True}
    publish(args.output_directory / "results.json", result)
    print(json.dumps({"denominator": result["denominator"], "models": results, "elapsed_seconds": elapsed}, sort_keys=True))


if __name__ == "__main__":
    main()
