"""Independent scalar checks for the explicit bounded periodic extension."""
from copy import deepcopy
from dataclasses import replace
import math

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    DistanceConstraintParameter, ReferenceForceFieldV2Parameters,
)
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import (
    OPENMM_PERIODIC_EVALUATOR_ID,
    OPENMM_PERIODIC_PARAMETER_SCHEMA,
    OpenMMPeriodicApplicabilityError,
    OpenMMPeriodicParameters,
    PeriodicImproperParameter,
    evaluate_extension,
    normalize_signed_proper,
    validate_periodic_domain,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_engine_v2_reference_forcefield_v2 import _star_system, _star_base_parameters


def fixture(amplitude=1.7, phase=.47):
    state = _star_system()
    params = OpenMMPeriodicParameters(_star_base_parameters(state),
        periodic_impropers=(PeriodicImproperParameter(1, 0, 2, 3, 0, 3, phase, amplitude),),
        constant_energy_offset_kcal_per_mol=-2.3)
    return state, params


def evaluate(state, params):
    graph = build_compact_radius_graph(state.coordinates,
        RadiusGraphConfig(cutoff_angstrom=params.base_parameters.cutoff_angstrom,
                          max_neighbors=8, max_atoms_per_cell=8))
    return evaluate_extension(state, graph, params)


def minus(a, b):
    return [x-y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def norm(a):
    return math.sqrt(dot(a, a))


def scalar_angle(xyz, row):
    # Independent plane-normal expression, not the runtime projected-vector helper.
    b1 = minus(xyz[row.atom_j], xyz[row.atom_i])
    b2 = minus(xyz[row.atom_k], xyz[row.atom_j])
    b3 = minus(xyz[row.atom_l], xyz[row.atom_k])
    n1, n2 = cross(b1, b2), cross(b2, b3)
    return math.atan2(dot(cross(n1, n2), b2)/norm(b2), dot(n1, n2))


def scalar_energy(xyz, params):
    value = params.constant_energy_offset_kcal_per_mol
    for row in params.base_parameters.bonds:
        value += .5*row.force_constant_kcal_per_mol_angstrom2*(norm(minus(xyz[row.atom_i], xyz[row.atom_j]))-row.equilibrium_angstrom)**2
    for row in params.base_parameters.angles:
        a, b = minus(xyz[row.atom_i], xyz[row.atom_j]), minus(xyz[row.atom_k], xyz[row.atom_j])
        angle = math.acos(dot(a, b)/norm(a)/norm(b))
        value += .5*row.force_constant_kcal_per_mol_radian2*(angle-row.equilibrium_radians)**2
    for row in params.periodic_impropers:
        value += row.amplitude_kcal_per_mol*(1+math.cos(row.periodicity*scalar_angle(xyz, row)-row.phase_radians))
    return value


@pytest.mark.parametrize("amplitude", [1.7, -1.7, 0.0])
@pytest.mark.parametrize("phase", [.47, -.83, math.pi])
def test_signed_ordered_improper_energy_and_independent_finite_difference(amplitude, phase):
    state, params = fixture(amplitude, phase)
    result = evaluate(state, params)
    xyz = state.coordinates[0].tolist()
    assert float(result.term.energy[0]) == pytest.approx(scalar_energy(xyz, params), abs=2e-13)
    h = 1e-6
    expected = torch.empty_like(result.term.forces)
    for atom in range(4):
        for axis in range(3):
            plus, minus_xyz = deepcopy(xyz), deepcopy(xyz)
            plus[atom][axis] += h
            minus_xyz[atom][axis] -= h
            expected[0, atom, axis] = -(scalar_energy(plus, params)-scalar_energy(minus_xyz, params))/(2*h)
    torch.testing.assert_close(result.term.forces, expected, rtol=2e-7, atol=2e-8)
    assert float(result.component_energies["constant_energy_offset"][0]) == -2.3
    assert not result.term.validated_for_composition


def test_order_is_not_rewritten_to_center_and_permutations_remain_distinct():
    state, params = fixture()
    alternate = PeriodicImproperParameter(2, 0, 3, 1, 0, 2, -.2, -.8)
    params = replace(params, periodic_impropers=(*params.periodic_impropers, alternate))
    result = evaluate(state, params)
    assert float(result.term.energy[0]) == pytest.approx(scalar_energy(state.coordinates[0].tolist(), params), abs=2e-13)


@pytest.mark.parametrize("amplitude", [1.7, -1.7])
def test_actual_openmm_reference_ordered_periodic_energy_and_force(amplitude):
    openmm = pytest.importorskip("openmm")
    unit = openmm.unit
    state, params = fixture(amplitude=amplitude, phase=.47)
    system = openmm.System()
    for _ in range(4):
        system.addParticle(12.)
    torsions = openmm.PeriodicTorsionForce()
    row = params.periodic_impropers[0]
    torsions.addTorsion(row.atom_i, row.atom_j, row.atom_k, row.atom_l,
                       row.periodicity, row.phase_radians, row.amplitude_kcal_per_mol*4.184)
    system.addForce(torsions)
    constant = openmm.CustomExternalForce(str(params.constant_energy_offset_kcal_per_mol*4.184))
    constant.addParticle(0, [])
    system.addForce(constant)
    integrator = openmm.VerletIntegrator(.001)
    context = openmm.Context(system, integrator, openmm.Platform.getPlatformByName("Reference"))
    context.setPositions(state.coordinates[0].numpy()/10)
    observed = context.getState(getEnergy=True, getForces=True)
    expected_energy = observed.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)/4.184
    expected_force = torch.as_tensor(observed.getForces(asNumpy=True).value_in_unit(
        unit.kilojoules_per_mole/unit.nanometer)/41.84, dtype=torch.float64).unsqueeze(0)
    actual = evaluate(state, params)
    # Base bonds/angles are at their declared equilibrium in this fixture.
    assert float(actual.term.energy[0]) == pytest.approx(expected_energy, abs=2e-12)
    torch.testing.assert_close(actual.term.forces, expected_force, rtol=1e-12, atol=1e-10)
    del context, integrator


@pytest.mark.parametrize("amplitude", [-3.4, 3.4, 0.0])
def test_signed_proper_normalization_preserves_energy_including_constant(amplitude):
    phase = .31
    term, offset = normalize_signed_proper(atom_i=0, atom_j=1, atom_k=2, atom_l=3,
        periodicity=3, phase_radians=phase, amplitude_kcal_per_mol=amplitude)
    assert term.amplitude_kcal_per_mol >= 0
    assert offset == (2*amplitude if amplitude < 0 else 0)
    for angle in [-2.1, -.2, .4, 2.8]:
        expected = amplitude*(1+math.cos(3*angle-phase))
        actual = term.amplitude_kcal_per_mol*(1+math.cos(3*angle-term.phase_radians))+offset
        assert actual == pytest.approx(expected, abs=4e-15)


def test_legacy_identity_and_new_schema_remain_distinct_and_roundtrip():
    _, params = fixture()
    legacy = ReferenceForceFieldV2Parameters(params.base_parameters)
    assert params.schema_id == OPENMM_PERIODIC_PARAMETER_SCHEMA
    assert legacy.schema_id != params.schema_id
    assert params.fingerprint_sha256 != legacy.fingerprint_sha256
    assert isinstance(params, ReferenceForceFieldV2Parameters)
    assert OpenMMPeriodicParameters.from_dict(params.to_dict(), params.base_parameters) == params


@pytest.mark.parametrize("change", ["unknown", "phase", "base", "schema", "promote", "domain"])
def test_canonical_input_refuses_changed_semantics(change):
    _, params = fixture()
    doc = params.to_dict()
    if change == "unknown":
        doc["discard_me"] = 1
    elif change == "phase":
        doc["periodic_impropers"][0]["discard_me"] = 1
    elif change == "base":
        doc["base_parameter_fingerprint_sha256"] = "0"*64
    elif change == "schema":
        doc["schema_id"] = "old"
    elif change == "promote":
        doc["scientifically_validated"] = True
    else:
        doc["nonbonded_domain"] = "ignore_far_pairs"
    with pytest.raises(ValueError):
        OpenMMPeriodicParameters.from_dict(doc, params.base_parameters)


def test_rejects_unbonded_center_and_out_of_topology():
    state, params = fixture()
    wrong = replace(params.periodic_impropers[0], center_atom=1)
    with pytest.raises(ResearchError, match="star"):
        evaluate(state, replace(params, periodic_impropers=(wrong,)))
    wrong = replace(params.periodic_impropers[0], atom_l=9)
    with pytest.raises(ResearchError, match="outside topology"):
        evaluate(state, replace(params, periodic_impropers=(wrong,)))


def test_nocutoff_domain_is_rechecked_on_every_coordinate_evaluation():
    state, params = fixture()
    validate_periodic_domain(state, params)
    # An excluded pair exactly at switch start is still out of this strict domain.
    xyz = state.coordinates.clone()
    xyz[0, 1] = torch.tensor([params.base_parameters.switch_start_angstrom, 0., 0.])
    moved = state.with_coordinates(xyz, operation="test_domain_boundary")
    with pytest.raises(OpenMMPeriodicApplicabilityError, match="at or beyond"):
        evaluate(moved, params)
    evaluate(state, params)


def test_domain_failure_is_a_minimizer_applicability_rejection():
    from betelgeuze_product.cpu_refinement_v1_2.minimization import APPLICABILITY_ERRORS
    assert issubclass(OpenMMPeriodicApplicabilityError, APPLICABILITY_ERRORS)


def test_actual_minimizer_trials_keep_domain_failures_and_original_state():
    from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
    from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig, minimize_extended
    state, params = fixture(amplitude=-1.7)
    params = replace(params, base_parameters=replace(params.base_parameters,
        switch_start_angstrom=float(torch.pdist(state.coordinates[0]).max())+1e-6))
    solver = SolverConfig(ReferenceMinimizationConfig(max_iterations=1, max_backtracks=4,
        initial_step_size_angstrom2_mol_per_kcal=.001,
        max_neighbors=8, max_atoms_per_cell=8))
    result = minimize_extended(state, params, solver)
    checkpoint = result.checkpoint.to_dict()
    assert checkpoint["status"] == "line_search_failed"
    trials = checkpoint["observations"][1:]
    assert len(trials) == 5
    assert all(row["outcome"] == "rejected_applicability" for row in trials)
    assert checkpoint["accepted_iterations"] == 0
    torch.testing.assert_close(result.system.coordinates, state.coordinates, rtol=0, atol=0)


@pytest.mark.parametrize("field,value", [("dielectric", 2.0), ("screening_kappa_per_angstrom", .01)])
def test_no_silent_reinterpretation_of_nocutoff_electrostatics(field, value):
    _, params = fixture()
    with pytest.raises(ResearchError, match="vacuum dielectric"):
        replace(params, base_parameters=replace(params.base_parameters, **{field: value}))


def test_constraints_keep_legacy_observations_and_not_an_energy_term():
    state, params = fixture()
    constrained = replace(params, constraints=(DistanceConstraintParameter(0, 1, 1.0),))
    a, b = evaluate(state, params), evaluate(state, constrained)
    torch.testing.assert_close(a.term.energy, b.term.energy, rtol=0, atol=0)
    torch.testing.assert_close(a.term.forces, b.term.forces, rtol=0, atol=0)
    assert len(b.constraint_observations) == 1 and b.constraints_satisfied


def test_extended_evaluator_dispatch_uses_new_identity():
    from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
    state, params = fixture()
    evaluator = ExtendedEvaluator(params)
    assert evaluator.identity()["evaluator_id"] == OPENMM_PERIODIC_EVALUATOR_ID
    graph = build_compact_radius_graph(state.coordinates,
        RadiusGraphConfig(cutoff_angstrom=4., max_neighbors=8, max_atoms_per_cell=8))
    expected, actual = evaluate(state, params), evaluator.evaluate(state, graph)
    assert expected.evaluator_fingerprint_sha256 == evaluator.fingerprint_sha256
    torch.testing.assert_close(expected.term.energy, actual.term.energy, rtol=0, atol=0)
    torch.testing.assert_close(expected.term.forces, actual.term.forces, rtol=0, atol=0)
