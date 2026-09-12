"""Fresh independent controls for source-assigned pair LJ interactions."""
from dataclasses import replace
import math

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Chain, Residue, StructureProvenance, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter, PairScalingParameter, ReferenceForceFieldParameters,
)
from betelgeuze_engine_v2.physics.reference_forcefield import evaluate_reference_force_field
from betelgeuze_engine.product.reference_pair_lj import (
    PairLJOverride, ReferencePairLJParameters, evaluate_reference_force_field_with_pair_lj,
)


def fixture(distance=3.2):
    atoms = tuple(Atom(i, f"C{i}", "C", 6, 0) for i in range(2))
    system = AllAtomSystem(system_id="fresh-pair-lj-control", atoms=atoms, bonds=(),
        residues=(Residue(0, "PRJ", 0, 1, (0, 1), entity_type="non_polymer", hetero=True),),
        chains=(Chain(0, "A", (0,)),),
        coordinates=torch.tensor([[[0., 0., 0.], [distance, 0., 0.]]], dtype=torch.float64),
        provenance=StructureProvenance(source_format="synthetic", source_id="fresh-pair-control",
            parser_name="test", parser_version="1"))
    base = ReferenceForceFieldParameters(parameter_set_id="pair-control", parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=(AtomNonbondedParameter(0, 3.7 / 2 ** (1 / 6), .2, 0),
                         AtomNonbondedParameter(1, 3.4 / 2 ** (1 / 6), .12, 0)),
        cutoff_angstrom=10., switch_start_angstrom=8.)
    return system, base


def evaluate(system, parameters):
    neighbors = build_compact_radius_graph(system.coordinates,
        RadiusGraphConfig(10., max(2, system.atom_count-1), max(4, system.atom_count)))
    if isinstance(parameters, ReferencePairLJParameters):
        return evaluate_reference_force_field_with_pair_lj(system, neighbors, parameters)
    return evaluate_reference_force_field(system, neighbors, parameters)


def oracle(distance, epsilon=.154919, rmin=3.637):
    # Direct Rmin form and analytic derivative, independent of sigma correction.
    ratio = rmin / distance
    value = epsilon * (ratio ** 12 - 2 * ratio ** 6)
    derivative = 12 * epsilon * (ratio ** 6 - ratio ** 12) / distance
    if distance >= 10:
        return 0., 0.
    if distance <= 8:
        return value, derivative
    x = (distance - 8) / 2
    switching = 1 - 10*x**3 + 15*x**4 - 6*x**5
    switching_derivative = (-30*x**2 + 60*x**3 - 30*x**4) / 2
    return value * switching, derivative * switching + value * switching_derivative


@pytest.mark.parametrize("distance", [2.8, 3.637, 7.9, 8., 8.4, 9.999, 10., 11.])
def test_pair_override_matches_independent_energy_and_atomic_force(distance):
    system, base = fixture(distance)
    parameters = ReferencePairLJParameters(base, (PairLJOverride(0, 1, 3.637 / 2**(1/6), .154919),), "a"*64)
    result = evaluate(system, parameters)
    energy, derivative = oracle(distance)
    assert result.term.energy.item() == pytest.approx(energy, abs=1e-11)
    assert result.term.forces[0, 0, 0].item() == pytest.approx(derivative, abs=1e-10)
    assert result.term.forces[0, 1, 0].item() == pytest.approx(-derivative, abs=1e-10)
    assert not result.scientifically_validated and not result.term.validated_for_composition
    assert result.component_energies["lennard_jones"].item() == pytest.approx(energy, abs=1e-11)


def test_original_mixing_does_not_represent_the_explicit_pair_source():
    system, base = fixture()
    assert abs(evaluate(system, base).term.energy.item() - oracle(3.2)[0]) > .01


def test_zero_epsilon_is_preserved_and_coulomb_is_unchanged():
    system, base = fixture()
    base = replace(base, atom_parameters=tuple(replace(a, charge_e=q)
        for a, q in zip(base.atom_parameters, (.4, -.7))))
    baseline = evaluate(system, base)
    result = evaluate(system, ReferencePairLJParameters(base, (PairLJOverride(0, 1, 4., 0.),), "a"*64))
    assert result.component_energies["lennard_jones"].item() == pytest.approx(0., abs=1e-14)
    assert torch.equal(result.component_energies["screened_coulomb"], baseline.component_energies["screened_coulomb"])


def test_explicit_base_scaling_is_retained():
    system, base = fixture()
    base = replace(base, scaled_pairs=(PairScalingParameter(0, 1, .25, .5),))
    result = evaluate(system, ReferencePairLJParameters(base, (PairLJOverride(0, 1, 3.637 / 2**(1/6), .154919),), "a"*64))
    assert result.term.energy.item() == pytest.approx(oracle(3.2)[0] * .25, abs=1e-12)


def test_rotation_translation_permutation_batch_and_finite_difference():
    system, base = fixture(8.7)
    par = ReferencePairLJParameters(base, (PairLJOverride(0, 1, 3.637 / 2**(1/6), .154919),), "a"*64)
    original = evaluate(system, par)
    angle = .7
    rotation = torch.tensor([[math.cos(angle), -math.sin(angle), 0.],
                             [math.sin(angle), math.cos(angle), 0.], [0., 0., 1.]], dtype=torch.float64)
    moved = replace(system, coordinates=system.coordinates @ rotation.T + torch.tensor([2., -4., 1.]))
    actual = evaluate(moved, par)
    assert torch.allclose(actual.term.energy, original.term.energy, atol=1e-12, rtol=0)
    assert torch.allclose(actual.term.forces, original.term.forces @ rotation.T, atol=1e-12, rtol=0)
    batch = evaluate(replace(system, coordinates=torch.cat((system.coordinates, moved.coordinates))), par)
    assert torch.allclose(batch.term.energy, original.term.energy.repeat(2), atol=1e-12, rtol=0)
    reordered = replace(system, atoms=tuple(replace(a, index=i) for i, a in enumerate(reversed(system.atoms))),
                        coordinates=system.coordinates[:, [1, 0]])
    reordered_base = replace(base, topology_sha256=canonical_topology_sha256(reordered),
        atom_parameters=tuple(replace(a, atom_index=i) for i, a in enumerate(reversed(base.atom_parameters))))
    reordered_result = evaluate(reordered, replace(par, base_parameters=reordered_base))
    assert torch.allclose(reordered_result.term.forces, original.term.forces[:, [1, 0]], atol=1e-12, rtol=0)
    energies = []
    for displacement in [-1e-5, 1e-5]:
        coords = system.coordinates.clone()
        coords[0, 1, 0] += displacement
        energies.append(evaluate(replace(system, coordinates=coords), par).term.energy.item())
    assert original.term.forces[0, 1, 0].item() == pytest.approx(-(energies[1]-energies[0])/2e-5, abs=1e-10)


@pytest.mark.parametrize("args", [(0, 0, 3., .1), (-1, 1, 3., .1), (False, 1, 3., .1),
    (.1, 1, 3., .1), (0, 1, 0., .1), (0, 1, 3., -.1), (0, 1, float('nan'), .1),
    (0, 1, 3., float('inf')), (0, 1, True, .1)])
def test_invalid_pair_definition_is_refused(args):
    with pytest.raises(ValueError):
        PairLJOverride(*args)


def test_conflicts_unknown_atoms_exclusions_source_and_topology_are_refused():
    system, base = fixture()
    row = PairLJOverride(0, 1, 3., .1)
    for candidate, rows, source in [(base, (row, row), "a"*64),
        (base, (PairLJOverride(0, 2, 3., .1),), "a"*64),
        (replace(base, excluded_pairs=((0, 1),)), (row,), "a"*64), (base, (row,), "missing")]:
        with pytest.raises(ValueError):
            ReferencePairLJParameters(candidate, rows, source)
    par = ReferencePairLJParameters(base, (row,), "a"*64)
    assert par.fingerprint_sha256 != replace(par, source_sha256="b"*64).fingerprint_sha256
    assert par.fingerprint_sha256 != replace(par, overrides=(replace(row, epsilon_kcal_per_mol=.2),)).fingerprint_sha256
    with pytest.raises(RuntimeError, match="topology"):
        evaluate(system, replace(par, base_parameters=replace(base, topology_sha256="b"*64)))


def test_no_overrides_preserves_original_energy_and_forces_exactly():
    system, base = fixture()
    old = evaluate(system, base)
    new = evaluate(system, ReferencePairLJParameters(base, (), "a"*64))
    assert torch.equal(old.term.energy, new.term.energy)
    assert torch.equal(old.term.forces, new.term.forces)


def test_multiple_overrides_keep_unmodified_pairs_and_scatter_to_source_atoms():
    system, base = fixture()
    system = replace(system,
        atoms=tuple(Atom(i, f"C{i}", "C", 6, 0) for i in range(4)),
        residues=(replace(system.residues[0], atom_indices=(0, 1, 2, 3)),),
        coordinates=torch.tensor([[[0., 0., 0.], [3.1, .3, .4],
                                    [1.3, 3.4, .7], [4., 3., 1.]]], dtype=torch.float64))
    base = replace(base, topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(AtomNonbondedParameter(i, 2.5 + i/5, .1 + i/20, 0.) for i in range(4)),
        excluded_pairs=((0, 3),))
    overrides = (PairLJOverride(0, 2, 3.2, .4), PairLJOverride(1, 3, 2.8, .02))
    par = ReferencePairLJParameters(base, overrides, "a"*64)
    result = evaluate(system, par)
    expected_energy = 0.
    expected_force = torch.zeros_like(system.coordinates)
    for i in range(4):
        for j in range(i+1, 4):
            if (i, j) == (0, 3):
                continue
            a, b = base.atom_parameters[i], base.atom_parameters[j]
            sigma = (a.sigma_angstrom + b.sigma_angstrom)/2
            epsilon = math.sqrt(a.epsilon_kcal_per_mol * b.epsilon_kcal_per_mol)
            for row in overrides:
                if row.pair == (i, j):
                    sigma, epsilon = row.sigma_angstrom, row.epsilon_kcal_per_mol
            vector = system.coordinates[0, i] - system.coordinates[0, j]
            distance = torch.linalg.vector_norm(vector).item()
            value, derivative = oracle(distance, epsilon, sigma * 2**(1/6))
            expected_energy += value
            force = -derivative * vector / distance
            expected_force[0, i] += force
            expected_force[0, j] -= force
    assert result.term.energy.item() == pytest.approx(expected_energy, abs=1e-12)
    assert torch.allclose(result.term.forces, expected_force, atol=1e-12, rtol=0)
