"""Share one evaluation identity without caching across integrity boundaries."""
from dataclasses import replace

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    ReferenceForceFieldV2ApplicabilityError, ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.stack_round3_molecular import MolecularIntegrityError
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    FixedReceptorEnvironment, FixedReceptorEvaluator,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from tests.unit.test_cpu_fixed_receptor import base_parameters, environment, system


def fixture():
    receptor = system([[0, 0, 0], [0, 3, 0]], [0.1, -0.1], "rec")
    ligand = system([[2, 1, 1], [3, 1, 1]], [0.2, -0.2], "lig")
    base = base_parameters(ligand)
    fixed = environment(receptor, ligand, base)
    evaluator = FixedReceptorEvaluator(
        ExtendedEvaluator(ReferenceForceFieldV2Parameters(base)), fixed
    )
    neighbors = build_compact_radius_graph(
        ligand.coordinates, RadiusGraphConfig(cutoff_angstrom=base.cutoff_angstrom)
    )
    return receptor, ligand, base, evaluator, neighbors


def mutate_receptor(receptor, kind):
    if kind == "coordinates":
        receptor.coordinates[0, 0, 0] += 0.01
    elif kind == "metadata":
        object.__setattr__(receptor, "metadata", {"changed": True})
    elif kind == "partial_charge":
        atoms = (replace(receptor.atoms[0], partial_charge_e=0.125), *receptor.atoms[1:])
        object.__setattr__(receptor, "atoms", atoms)
    else:
        atoms = (replace(receptor.atoms[0], formal_charge=1), *receptor.atoms[1:])
        object.__setattr__(receptor, "atoms", atoms)


def test_identity_shared_with_exact_composition_and_three_receptor_checks(monkeypatch):
    _, ligand, base, evaluator, neighbors = fixture()
    internal = evaluator.internal.evaluate(ligand, neighbors)
    cross, cross_force, _ = evaluator.fixed.evaluate_cross(ligand, base)
    identity = evaluator.identity()
    expected_energy = sum(
        (internal.term.energy, *cross.values()), torch.zeros_like(internal.term.energy)
    )
    expected_force = internal.term.forces + cross_force
    original = FixedReceptorEnvironment.assert_intact
    checks = []

    def checked(fixed):
        checks.append(fixed)
        return original(fixed)

    monkeypatch.setattr(FixedReceptorEnvironment, "assert_intact", checked)
    result = evaluator.evaluate(ligand, neighbors)
    assert len(checks) == 3  # Cross entry, cross exit, final identity.
    assert torch.equal(result.term.energy, expected_energy)
    assert torch.equal(result.term.forces, expected_force)
    assert result.evaluator_fingerprint_sha256 == digest(identity)
    assert result.component_energies.keys() == {
        "ligand_internal", "cross_lennard_jones", "cross_screened_coulomb"
    }
    assert "fixed_receptor_model_not_scientifically_validated" in result.scientific_blockers


@pytest.mark.parametrize("kind", ["coordinates", "metadata", "partial_charge", "topology"])
@pytest.mark.parametrize("boundary", ["validate_ligand", "evaluate_cross", "identity", "evaluate"])
def test_each_public_boundary_rejects_receptor_mutation_between_calls(kind, boundary):
    receptor, ligand, base, evaluator, neighbors = fixture()
    evaluator.evaluate(ligand, neighbors)
    mutate_receptor(receptor, kind)
    with pytest.raises(ResearchError, match="changed"):
        if boundary == "validate_ligand":
            evaluator.fixed.validate_ligand(ligand, base)
        elif boundary == "evaluate_cross":
            evaluator.fixed.evaluate_cross(ligand, base)
        elif boundary == "identity":
            evaluator.identity()
        else:
            evaluator.evaluate(ligand, neighbors)


@pytest.mark.parametrize("kind", ["coordinates", "metadata", "partial_charge", "topology"])
@pytest.mark.parametrize("when", ["during_cross", "after_cross"])
def test_receptor_mutation_during_evaluation_is_still_rejected(monkeypatch, kind, when):
    receptor, ligand, _, evaluator, neighbors = fixture()
    name = "validate_ligand" if when == "during_cross" else "evaluate_cross"
    original = getattr(FixedReceptorEnvironment, name)

    def mutate_after_boundary(fixed, *args):
        result = original(fixed, *args)
        mutate_receptor(receptor, kind)
        return result

    monkeypatch.setattr(FixedReceptorEnvironment, name, mutate_after_boundary)
    with pytest.raises(ResearchError, match="changed"):
        evaluator.evaluate(ligand, neighbors)


@pytest.mark.parametrize("kind", ["base_parameter", "ligand_topology"])
@pytest.mark.parametrize("boundary", ["validate_ligand", "evaluate_cross", "evaluate"])
def test_ligand_binding_changes_are_not_hidden_by_identity_reuse(kind, boundary):
    _, ligand, base, evaluator, neighbors = fixture()
    evaluator.evaluate(ligand, neighbors)
    if kind == "base_parameter":
        rows = (replace(base.atom_parameters[0], sigma_angstrom=1.25), *base.atom_parameters[1:])
        base = replace(base, atom_parameters=rows)
        # A new immutable parameter object cannot inherit a previous admission.
        object.__setattr__(evaluator.internal, "parameters", ReferenceForceFieldV2Parameters(base))
    else:
        atoms = (replace(ligand.atoms[0], formal_charge=1), *ligand.atoms[1:])
        ligand = replace(ligand, atoms=atoms)
    with pytest.raises((ResearchError, ReferenceForceFieldV2ApplicabilityError), match="topology|parameter"):
        if boundary == "validate_ligand":
            evaluator.fixed.validate_ligand(ligand, base)
        elif boundary == "evaluate_cross":
            evaluator.fixed.evaluate_cross(ligand, base)
        else:
            evaluator.evaluate(ligand, neighbors)


@pytest.mark.parametrize("kind", ["base_parameter", "ligand_topology"])
def test_binding_change_during_internal_evaluation_is_rejected(monkeypatch, kind):
    _, ligand, base, evaluator, neighbors = fixture()
    original = ExtendedEvaluator.evaluate

    def mutate_after_internal(internal, state, graph):
        result = original(internal, state, graph)
        if kind == "base_parameter":
            rows = (replace(base.atom_parameters[0], sigma_angstrom=1.25), *base.atom_parameters[1:])
            changed = ReferenceForceFieldV2Parameters(replace(base, atom_parameters=rows))
            object.__setattr__(internal, "parameters", changed)
        else:
            atoms = (replace(state.atoms[0], formal_charge=1), *state.atoms[1:])
            object.__setattr__(state, "atoms", atoms)
        return result

    monkeypatch.setattr(ExtendedEvaluator, "evaluate", mutate_after_internal)
    expected = ResearchError if kind == "base_parameter" else MolecularIntegrityError
    with pytest.raises(expected, match="parameter|changed"):
        evaluator.evaluate(ligand, neighbors)
