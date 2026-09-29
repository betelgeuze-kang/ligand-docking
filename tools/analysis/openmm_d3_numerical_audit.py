"""Independent OpenMM Reference checks for one prepared D3 development case.

Original XML is evaluated unchanged. A second reference replaces only its
NoCutoff nonbonded arithmetic with explicitly declared D3 Coulomb arithmetic;
all particles, exceptions and bonded terms still come directly from XML. The
cross reference uses ligand--receptor interaction groups, never receptor
internal energies. This is a bounded numerical audit, not affinity validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import time

import numpy as np
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.physics.reference_parameters import COULOMB_KCAL_ANGSTROM_PER_MOL_E2
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment, FIXED_REQUEST_SCHEMA,
)
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import OpenMMPeriodicParameters
from betelgeuze_product.cpu_refinement_v1_2.provenance import canonical, digest, source_manifest
from betelgeuze_product.cpu_refinement_v1_2.workflow import REQUEST_SCHEMA, load_request
from betelgeuze_product.local_research_workflow import _decode
from betelgeuze_product.reference_minimization_workflow import _bound, _read

SCHEMA = "openmm_d3_numerical_audit/1.0.0"
ENERGY_ABSOLUTE_TOLERANCE = 1e-8
FORCE_ABSOLUTE_TOLERANCE = 1e-8
DEFAULT_SEED = 20260929
DEFAULT_PERTURBATIONS = 3
DEFAULT_PERTURBATION_ANGSTROM = 1e-4
KJ_PER_KCAL = 4.184
ANGSTROM_PER_NM = 10.0
GROUP_NAMES = {0: "harmonic_bond", 1: "harmonic_angle", 2: "periodic_torsion_with_improper", 3: "nonbonded"}


class NumericalAuditError(ValueError):
    """Missing source correspondence or unsupported reference configuration."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _nonbonded(system, openmm):
    rows = [force for force in system.getForces() if isinstance(force, openmm.NonbondedForce)]
    if len(rows) != 1:
        raise NumericalAuditError("exactly_one_source_NonbondedForce_required")
    nb = rows[0]
    if nb.getNumParticles() != system.getNumParticles():
        raise NumericalAuditError("source_nonbonded_particle_count_mismatch")
    if nb.getNumParticleParameterOffsets() or nb.getNumExceptionParameterOffsets() or nb.getNumGlobalParameters():
        raise NumericalAuditError("parameter_offsets_and_global_nonbonded_parameters_unsupported")
    return nb


def _particle_values(nb, unit):
    values = []
    for i in range(nb.getNumParticles()):
        q, sig, eps = nb.getParticleParameters(i)
        values.append((q.value_in_unit(unit.elementary_charge),
                       sig.value_in_unit(unit.nanometer),
                       eps.value_in_unit(unit.kilojoules_per_mole)))
    return values


def _reference_context(system, openmm):
    integrator = openmm.VerletIntegrator(.001)
    context = openmm.Context(system, integrator, openmm.Platform.getPlatformByName("Reference"))
    return context, integrator


def _grouped_source(xml_bytes, openmm):
    system = openmm.XmlSerializer.deserialize(xml_bytes.decode("utf-8"))
    if not 1 <= system.getNumParticles() <= 256 or system.getNumConstraints():
        raise NumericalAuditError("unconstrained_ligand_source_of_1_to_256_particles_required")
    mapping = {"HarmonicBondForce": 0, "HarmonicAngleForce": 1,
               "PeriodicTorsionForce": 2, "NonbondedForce": 3, "CMMotionRemover": 4}
    seen = set()
    for force in system.getForces():
        name = force.__class__.__name__
        if name not in mapping or name in seen:
            raise NumericalAuditError("unsupported_or_duplicate_source_force:" + name)
        seen.add(name)
        force.setForceGroup(mapping[name])
    if not set(mapping)-{"CMMotionRemover"} <= seen:
        raise NumericalAuditError("required_source_force_missing")
    nb = _nonbonded(system, openmm)
    if nb.getNonbondedMethod() != openmm.NonbondedForce.NoCutoff:
        raise NumericalAuditError("source_internal_nonbonded_must_be_NoCutoff")
    if any(system.isVirtualSite(i) for i in range(system.getNumParticles())):
        raise NumericalAuditError("virtual_sites_unsupported")
    return system


def same_math_internal_system(xml_bytes, openmm):
    """Independent source-driven reference; no D3 parameter rows are copied."""
    system = _grouped_source(xml_bytes, openmm)
    nb = _nonbonded(system, openmm)
    unit = openmm.unit
    # Expressions use OpenMM nm/kJ. D3 kcal/A Coulomb constant is explicit.
    coefficient = COULOMB_KCAL_ANGSTROM_PER_MOL_E2*KJ_PER_KCAL/ANGSTROM_PER_NM
    force = openmm.CustomNonbondedForce(
        "4*sqrt(eps1*eps2)*(sr6*sr6-sr6)+C*q1*q2/r;"
        "sr6=(0.5*(sig1+sig2)/r)^6")
    for name in ("q", "sig", "eps"):
        force.addPerParticleParameter(name)
    force.addGlobalParameter("C", coefficient)
    force.setNonbondedMethod(openmm.CustomNonbondedForce.NoCutoff)
    force.setUseLongRangeCorrection(False)
    force.setForceGroup(3)
    for values in _particle_values(nb, unit):
        force.addParticle(values)
    exceptions = openmm.CustomBondForce("4*eps*(sr6*sr6-sr6)+C*q/r;sr6=(sig/r)^6")
    for name in ("q", "sig", "eps"):
        exceptions.addPerBondParameter(name)
    exceptions.addGlobalParameter("C", coefficient)
    exceptions.setForceGroup(3)
    for i in range(nb.getNumExceptions()):
        a, b, charge, sigma, epsilon = nb.getExceptionParameters(i)
        force.addExclusion(a, b)
        q = charge.value_in_unit(unit.elementary_charge**2)
        eps = epsilon.value_in_unit(unit.kilojoules_per_mole)
        # Zero exceptions contribute exactly zero and are still excluded above.
        if q != 0.0 or eps != 0.0:
            exceptions.addBond(a, b, [q, sigma.value_in_unit(unit.nanometer), eps])
    for i in reversed(range(system.getNumForces())):
        if isinstance(system.getForce(i), openmm.NonbondedForce):
            system.removeForce(i)
    system.addForce(force)
    system.addForce(exceptions)
    return system


def cross_reference_system(ligand_source, receptor_source, cross, openmm):
    """Cross-only pair arithmetic from source XML, with no R--R work or energy."""
    unit = openmm.unit
    lnb, rnb = _nonbonded(ligand_source, openmm), _nonbonded(receptor_source, openmm)
    nl, nr = ligand_source.getNumParticles(), receptor_source.getNumParticles()
    system = openmm.System()
    for source in (ligand_source, receptor_source):
        for i in range(source.getNumParticles()):
            system.addParticle(source.getParticleMass(i))
    switch = "s=1-10*t^3+15*t^4-6*t^5;t=min(1,max(0,(r-rs)/(rc-rs)))"
    expressions = (
        "s*4*sqrt(eps1*eps2)*(sr6*sr6-sr6);sr6=(0.5*(sig1+sig2)/r)^6;" + switch,
        "s*C*q1*q2*exp(-kappa*r)/(dielectric*r);" + switch,
    )
    values = _particle_values(lnb, unit)+_particle_values(rnb, unit)
    for group, expression in enumerate(expressions):
        force = openmm.CustomNonbondedForce(expression)
        for name in ("q", "sig", "eps"):
            force.addPerParticleParameter(name)
        for name, value in {
            "C": COULOMB_KCAL_ANGSTROM_PER_MOL_E2*KJ_PER_KCAL/ANGSTROM_PER_NM,
            "rs": cross.switch_start_angstrom/ANGSTROM_PER_NM,
            "rc": cross.cutoff_angstrom/ANGSTROM_PER_NM,
            "dielectric": cross.dielectric,
            "kappa": cross.screening_kappa_per_angstrom*ANGSTROM_PER_NM,
        }.items():
            force.addGlobalParameter(name, value)
        for row in values:
            force.addParticle(row)
        force.addInteractionGroup(set(range(nl)), set(range(nl, nl+nr)))
        force.setNonbondedMethod(openmm.CustomNonbondedForce.CutoffNonPeriodic)
        force.setCutoffDistance(cross.cutoff_angstrom/ANGSTROM_PER_NM)
        force.setUseSwitchingFunction(False)
        force.setUseLongRangeCorrection(False)
        force.setForceGroup(group)
        system.addForce(force)
    return system


def _observe(context, xyz_angstrom, openmm, groups=None):
    context.setPositions(np.asarray(xyz_angstrom, dtype=np.float64)/ANGSTROM_PER_NM)
    kwargs = {} if groups is None else {"groups": set(groups)}
    state = context.getState(getEnergy=True, getForces=True, **kwargs)
    unit = openmm.unit
    energy = state.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)/KJ_PER_KCAL
    forces = np.asarray(state.getForces(asNumpy=True).value_in_unit(
        unit.kilojoules_per_mole/unit.nanometer), dtype=np.float64)/(KJ_PER_KCAL*ANGSTROM_PER_NM)
    if not math.isfinite(energy) or not np.isfinite(forces).all():
        raise NumericalAuditError("nonfinite_OpenMM_reference_observation")
    return float(energy), forces


def _measure_builtin_coulomb_constant(openmm):
    system = openmm.System()
    force = openmm.NonbondedForce()
    force.setNonbondedMethod(openmm.NonbondedForce.NoCutoff)
    for _ in range(2):
        system.addParticle(1.)
        force.addParticle(1., .1, 0.)
    system.addForce(force)
    context, integrator = _reference_context(system, openmm)
    energy, _ = _observe(context, [[0., 0., 0.], [10., 0., 0.]], openmm)
    del context, integrator
    return energy*10.0


def _source_parameter_correspondence(source, params, openmm, name):
    values = _particle_values(_nonbonded(source, openmm), openmm.unit)
    if len(values) != len(params):
        raise NumericalAuditError(name+"_source_parameter_count_mismatch")
    maxima = {"charge_e": 0., "sigma_angstrom": 0., "epsilon_kcal_per_mol": 0.}
    for i, ((q, sig, eps), row) in enumerate(zip(values, params, strict=True)):
        if row.atom_index != i:
            raise NumericalAuditError(name+"_source_parameter_order_mismatch")
        observed = (q, sig*10., eps/4.184)
        admitted = (row.charge_e, row.sigma_angstrom, row.epsilon_kcal_per_mol)
        for key, a, b in zip(maxima, observed, admitted, strict=True):
            maxima[key] = max(maxima[key], abs(a-b))
            if not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
                raise NumericalAuditError(name+"_source_particle_parameter_mismatch:"+str(i)+":"+key)
    return maxima


def _metrics(energy, expected_energy, force, expected_force):
    error = np.asarray(force)-np.asarray(expected_force)
    energy_error = abs(float(energy)-float(expected_energy))
    max_force = float(np.abs(error).max(initial=0.))
    return {"absolute_energy_error_kcal_per_mol": energy_error,
        "maximum_absolute_force_component_error_kcal_per_mol_angstrom": max_force,
        "rms_force_component_error_kcal_per_mol_angstrom": float(np.sqrt(np.mean(error*error))),
        "passed": energy_error <= ENERGY_ABSOLUTE_TOLERANCE and max_force <= FORCE_ABSOLUTE_TOLERANCE}


def _native_components(state, params, fixed, solver):
    graph = build_compact_radius_graph(state.coordinates,
        RadiusGraphConfig(cutoff_angstrom=params.base_parameters.cutoff_angstrom,
            max_neighbors=solver.minimization.max_neighbors,
            max_atoms_per_cell=solver.minimization.max_atoms_per_cell))
    internal = ExtendedEvaluator(params).evaluate(state, graph)
    cross, force, pair_count = fixed.evaluate_cross(state, params.base_parameters)
    components = {name: float(value[0]) for name, value in internal.component_energies.items()}
    aligned = {"harmonic_bond": components["harmonic_bond"],
        "harmonic_angle": components["harmonic_angle"],
        "periodic_torsion_with_improper": components["periodic_torsion"]+components["periodic_star_improper"]+components["constant_energy_offset"],
        "nonbonded": components["lennard_jones"]+components["screened_coulomb"]}
    if components["harmonic_out_of_plane_improper"] != 0.:
        raise NumericalAuditError("source_XML_has_no_harmonic_out_of_plane_improper_correspondence")
    return {"internal_components": components, "source_aligned_internal_components": aligned,
        "internal_energy": float(internal.term.energy[0]), "internal_forces": internal.term.forces[0].numpy(),
        "cross_components": {name: float(value[0]) for name, value in cross.items()},
        "cross_forces": force[0].numpy(), "cross_pair_count": pair_count}


def audit(request_path, ligand_xml_path, receptor_xml_path, *, final_coordinates_path=None,
          perturbations=DEFAULT_PERTURBATIONS, seed=DEFAULT_SEED,
          perturbation_angstrom=DEFAULT_PERTURBATION_ANGSTROM):
    import openmm

    if type(perturbations) is not int or not 0 <= perturbations <= 16:
        raise NumericalAuditError("perturbation_count_must_be_0_to_16")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise NumericalAuditError("bounded_integer_seed_required")
    if type(perturbation_angstrom) not in (int, float) or not 0 < perturbation_angstrom <= .01:
        raise NumericalAuditError("perturbation_magnitude_must_be_positive_and_at_most_0.01_A")
    paths = [Path(path).absolute() for path in (request_path, ligand_xml_path, receptor_xml_path)]
    raw_request, ligand_xml, receptor_xml = map(_read, paths)
    request = _decode(raw_request)
    if request.get("schema_id") != FIXED_REQUEST_SCHEMA or request.get("solvation") is not None:
        raise NumericalAuditError("explicit_fixed_receptor_request_required")
    sources = source_manifest()
    prepared = {key: value for key, value in request.items() if key != "cross_parameters"}
    prepared["schema_id"] = REQUEST_SCHEMA
    _, receptor, ligand, params, _, solver, _, _, _ = load_request(prepared, digest(sources))
    if type(params) is not OpenMMPeriodicParameters:
        raise NumericalAuditError("explicit_OpenMM_periodic_extension_required")
    if params.metadata.get("source_xml_sha256") != _sha(ligand_xml):
        raise NumericalAuditError("ligand_source_XML_not_bound_to_extension")
    if params.metadata.get("openmm_xml_sha256", _sha(ligand_xml)) != _sha(ligand_xml):
        raise NumericalAuditError("conflicting_ligand_XML_binding")
    cross = CrossParameters.from_dict(_bound(request["cross_parameters"]))
    if cross.parameter_source_sha256 != _sha(receptor_xml):
        raise NumericalAuditError("receptor_XML_not_bound_to_cross_parameters")
    fixed = FixedReceptorEnvironment(receptor, cross)
    fixed.validate_ligand(ligand, params.base_parameters)
    original = _grouped_source(ligand_xml, openmm)
    receptor_source = openmm.XmlSerializer.deserialize(receptor_xml.decode("utf-8"))
    if original.getNumParticles() != ligand.atom_count or receptor_source.getNumParticles() != receptor.atom_count:
        raise NumericalAuditError("XML_and_canonical_atom_count_mismatch")
    correspondence = {
        "ligand": _source_parameter_correspondence(original, params.base_parameters.atom_parameters, openmm, "ligand"),
        "receptor": _source_parameter_correspondence(receptor_source, cross.receptor_atoms, openmm, "receptor")}
    snapshots = [("initial", ligand.coordinates[0].numpy().copy())]
    rng = random.Random(seed)
    for index in range(perturbations):
        delta = np.array([[rng.uniform(-perturbation_angstrom, perturbation_angstrom)
                           for _ in range(3)] for _ in range(ligand.atom_count)])
        snapshots.append(("perturbation_"+str(index+1), snapshots[0][1]+delta))
    final_binding = None
    if final_coordinates_path is not None:
        final_path = Path(final_coordinates_path).absolute()
        raw = _read(final_path)
        document = _decode(raw)
        if type(document) is not dict or set(document) != {"coordinates_angstrom"}:
            raise NumericalAuditError("final_coordinates_require_exact_coordinates_angstrom_document")
        xyz = np.asarray(document["coordinates_angstrom"], dtype=np.float64)
        if xyz.shape != (ligand.atom_count, 3) or not np.isfinite(xyz).all():
            raise NumericalAuditError("invalid_final_coordinate_array")
        snapshots.append(("supplied_final", xyz))
        final_binding = {"path": str(final_path), "sha256": _sha(raw)}
    original_context, original_integrator = _reference_context(original, openmm)
    math_context, math_integrator = _reference_context(same_math_internal_system(ligand_xml, openmm), openmm)
    cross_context, cross_integrator = _reference_context(cross_reference_system(original, receptor_source, cross, openmm), openmm)
    rows = []
    start = time.perf_counter()
    for name, xyz in snapshots:
        row = {"snapshot": name, "coordinates_angstrom": xyz.tolist(), "coordinates_sha256": digest(xyz.tolist())}
        try:
            state = ligand.with_coordinates(torch.tensor(xyz[None, :, :], dtype=torch.float64), operation="openmm_numerical_audit_"+name)
            native = _native_components(state, params, fixed, solver)
            source_energy, source_force = _observe(original_context, xyz, openmm)
            math_energy, math_force = _observe(math_context, xyz, openmm)
            component_reference = {label: _observe(math_context, xyz, openmm, [group])[0] for group, label in GROUP_NAMES.items()}
            combined = np.concatenate((xyz, receptor.coordinates[0].numpy()), axis=0)
            cross_energy, all_cross_force = _observe(cross_context, combined, openmm)
            cross_force = all_cross_force[:ligand.atom_count]
            cross_components = {label: _observe(cross_context, combined, openmm, [group])[0]
                for group, label in enumerate(("cross_lennard_jones", "cross_screened_coulomb"))}
            native_cross_energy = sum(native["cross_components"].values())
            checks = {
                "internal": _metrics(native["internal_energy"], math_energy, native["internal_forces"], math_force),
                "cross": _metrics(native_cross_energy, cross_energy, native["cross_forces"], cross_force),
                "total": _metrics(native["internal_energy"]+native_cross_energy, math_energy+cross_energy,
                                  native["internal_forces"]+native["cross_forces"], math_force+cross_force)}
            component_errors = {key: abs(native["source_aligned_internal_components"][key]-value) for key, value in component_reference.items()}
            component_errors.update({key: abs(native["cross_components"][key]-value) for key, value in cross_components.items()})
            row.update(status="evaluated", same_math_checks=checks, component_absolute_energy_errors=component_errors,
                passed=all(check["passed"] for check in checks.values()) and all(value <= ENERGY_ABSOLUTE_TOLERANCE for value in component_errors.values()),
                native={**native, "internal_forces": native["internal_forces"].tolist(), "cross_forces": native["cross_forces"].tolist()},
                reference_same_math={"internal_energy": math_energy, "internal_forces": math_force.tolist(),
                    "internal_components": component_reference, "cross_energy": cross_energy,
                    "cross_forces": cross_force.tolist(), "cross_components": cross_components},
                original_XML={"internal_energy": source_energy, "internal_forces": source_force.tolist(),
                    "original_minus_same_math_energy_kcal_per_mol": source_energy-math_energy,
                    "maximum_absolute_original_minus_same_math_force_component": float(np.abs(source_force-math_force).max())})
        except (ValueError, RuntimeError, FloatingPointError) as exc:
            row.update(status="rejected", passed=False, error_type=type(exc).__name__, reason=str(exc))
        rows.append(row)
    elapsed = time.perf_counter()-start
    del original_context, original_integrator, math_context, math_integrator, cross_context, cross_integrator
    measured_constant = _measure_builtin_coulomb_constant(openmm)
    for path, original_bytes in zip(paths, (raw_request, ligand_xml, receptor_xml), strict=True):
        if _read(path) != original_bytes:
            raise NumericalAuditError("audit_input_changed_during_execution")
    for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        _bound(request[key])
    if source_manifest() != sources:
        raise NumericalAuditError("native_implementation_changed_during_audit")
    report = {"schema_id": SCHEMA,
        "inputs": {key: {"path": str(path), "sha256": _sha(raw)} for key, path, raw in zip(
            ("request", "ligand_XML", "receptor_XML"), paths, (raw_request, ligand_xml, receptor_xml), strict=True)},
        "final_coordinates": final_binding,
        "canonical_state_sha256": {"ligand": canonical_system_sha256(ligand), "receptor": canonical_system_sha256(receptor)},
        "native_source_manifest_sha256": digest(sources), "native_source_manifest": sources,
        "audit_source_sha256": _sha(Path(__file__).read_bytes()),
        "openmm_version": openmm.version.version, "reference_platform": "Reference",
        "source_particle_parameter_correspondence_max_errors": correspondence,
        "ligand_atom_count": ligand.atom_count, "receptor_atom_count": receptor.atom_count,
        "cross_interaction_group_pair_capacity": ligand.atom_count*receptor.atom_count,
        "intrareceptor_energy_evaluated": False,
        "protocol": {"seed": seed, "perturbations": perturbations,
            "perturbation_coordinate_distribution": "independent_uniform_symmetric",
            "perturbation_angstrom": perturbation_angstrom,
            "absolute_energy_tolerance_kcal_per_mol": ENERGY_ABSOLUTE_TOLERANCE,
            "absolute_force_component_tolerance_kcal_per_mol_angstrom": FORCE_ABSOLUTE_TOLERANCE},
        "coulomb_constants_kcal_angstrom_per_mol_e2": {
            "native_and_same_math_reference": COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
            "OpenMM_builtin_measured_at_unit_charges_one_nm": measured_constant,
            "native_minus_builtin": COULOMB_KCAL_ANGSTROM_PER_MOL_E2-measured_constant},
        "denominator": {"requested": len(snapshots), "evaluated": sum(r["status"] == "evaluated" for r in rows),
            "rejected": sum(r["status"] == "rejected" for r in rows), "passed": sum(r["passed"] for r in rows)},
        "snapshots": rows, "all_same_math_checks_passed": all(row["passed"] for row in rows),
        "elapsed_snapshot_evaluation_seconds": elapsed,
        "source_XML_equivalence_claimed": False, "scientifically_validated": False,
        "affinity_or_pose_recovery_validated": False, "product_qualified": False,
        "scope": "fixed_coordinate_source_term_and_D3_arithmetic_comparison_only"}
    report["report_sha256"] = digest(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--ligand-xml", required=True)
    parser.add_argument("--receptor-xml", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--final-coordinates")
    parser.add_argument("--perturbations", type=int, default=DEFAULT_PERTURBATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--perturbation-angstrom", type=float, default=DEFAULT_PERTURBATION_ANGSTROM)
    args = parser.parse_args(argv)
    report = audit(args.request, args.ligand_xml, args.receptor_xml,
        final_coordinates_path=args.final_coordinates, perturbations=args.perturbations,
        seed=args.seed, perturbation_angstrom=args.perturbation_angstrom)
    output = Path(args.output).absolute()
    with output.open("xb") as stream:
        stream.write((canonical(report)+"\n").encode("ascii"))
    print(json.dumps({"output": str(output), "denominator": report["denominator"],
        "all_same_math_checks_passed": report["all_same_math_checks_passed"]}, sort_keys=True))
    return 0 if report["all_same_math_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
