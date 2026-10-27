"""Real engine types + synthetic analytic provider; not molecular qualification."""
# ruff: noqa: E402
from __future__ import annotations

from dataclasses import replace
import math

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import DockingBudget, run_authenticated_bounded_docking_search
from betelgeuze_engine_v2.docking.proposals import generate_bounded_docking_proposals
from betelgeuze_engine_v2.docking.search import DockingPoseRefiner, _require_refined_lineage
from betelgeuze_engine_v2.docking.structure_preserving import SearchConfig
from betelgeuze_engine_v2.docking.structure_preserving_refinement import (
    BoundEnergyForceResult, StructurePreservingPoseRefiner, StructureRefinementError,
    structure_coordinate_sha256,
)
from betelgeuze_engine_v2.molecular import canonical_topology_sha256
from tests.unit.test_engine_v2_docking_authority_search import _authority, _system, _Scorer


class AnalyticProvider:
    """Index-dependent harmonic test target, not a physical docking model."""
    implementation_source_sha256 = "9" * 64
    model_fingerprint_sha256 = "8" * 64

    def __init__(self, authority, ligand):
        self.problem_fingerprint_sha256 = authority.problem.fingerprint_sha256
        self.ligand_topology_sha256 = canonical_topology_sha256(ligand)
        self.targets = tuple(tuple(float(v) + (0.3 if k == 0 else 0.0)
                                   for k, v in enumerate(row))
                             for row in ligand.coordinates[0].tolist())
        self.calls = 0
        self.outputs = []
        self.mode = "normal"

    def evaluate(self, points):
        self.calls += 1
        if self.mode == "raise":
            raise RuntimeError("private backend path")
        forces = tuple(tuple((i + 1) * (target[k] - row[k]) for k in range(3))
                       for i, (row, target) in enumerate(zip(points, self.targets)))
        energy = sum(.5 * (i + 1) * sum((x-y)**2 for x, y in zip(row, target))
                     for i, (row, target) in enumerate(zip(points, self.targets)))
        result = BoundEnergyForceResult(structure_coordinate_sha256(points),
                                        self.model_fingerprint_sha256, energy, forces)
        if self.mode == "wrong_coordinates":
            result = replace(result, coordinate_sha256="7" * 64)
        elif self.mode == "wrong_model":
            result = replace(result, model_fingerprint_sha256="7" * 64)
        elif self.mode == "wrong_units":
            result = replace(result, force_unit="kJ/mol/nm")
        elif self.mode == "wrong_sign":
            result = replace(result, force_semantics="positive_gradient")
        elif self.mode == "nonfinite":
            result = replace(result, energy=math.nan)
        elif self.mode == "short_force":
            result = replace(result, forces=forces[:-1])
        elif self.mode == "mutate_model":
            self.model_fingerprint_sha256 = "6" * 64
        self.outputs.append(result)
        return result


def fixture(**config):
    authority, ligand = _authority(), _system(receptor=False)
    provider = AnalyticProvider(authority, ligand)
    refiner = StructurePreservingPoseRefiner(authority, ligand, provider,
        implementation_source_sha256="5" * 64, config=SearchConfig(**config))
    proposal = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)[0]
    return authority, ligand, provider, refiner, proposal


def test_real_proposal_refinement_preserves_lineage_and_bonds():
    authority, ligand, provider, refiner, proposal = fixture(max_steps=4)
    original = proposal.coordinates.clone()
    refined = refiner.refine(proposal, max_steps=4)
    assert isinstance(refiner, DockingPoseRefiner)
    _require_refined_lineage(proposal, refined, refiner)
    assert torch.equal(proposal.coordinates, original)
    assert refined.refinement_receipt_sha256 == refiner.attempts[proposal.fingerprint_sha256].receipt_sha256
    for bond in ligand.bonds:
        a, b = bond.atom_i, bond.atom_j
        assert torch.linalg.vector_norm(refined.coordinates[a] - refined.coordinates[b]).item() == pytest.approx(
            torch.linalg.vector_norm(original[a] - original[b]).item(), abs=1e-10)
    attempt = refiner.attempts[proposal.fingerprint_sha256]
    assert attempt.status == "success"
    assert attempt.result.energy <= attempt.result.initial_energy
    assert attempt.result.evaluation_attempts == provider.calls
    assert attempt.result.accepted_steps <= 4
    assert len(attempt.receipt_sha256) == 64


def test_existing_authenticated_search_accepts_opt_in_refiner():
    authority, _, _, refiner, _ = fixture(max_steps=2)
    result = run_authenticated_bounded_docking_search(authority,
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1,
                      max_refinement_steps=2, translation_radius_angstrom=0.),
        _Scorer(authority.problem.fingerprint_sha256), refiner=refiner,
        diversity_rmsd_angstrom=0.)
    assert len(result.search_result.rows) == 2
    assert len(refiner.attempts) == 2
    assert all(row.refined for row in result.search_result.rows)
    assert result.authenticated_input_receipt_sha256 == authority.input_receipt_sha256
    assert result.to_dict()["claim_safe"] is False


@pytest.mark.parametrize("mode", ["raise", "wrong_coordinates", "wrong_model", "wrong_units",
                                  "wrong_sign", "nonfinite", "short_force", "mutate_model"])
def test_invalid_provider_result_is_charged_failed_attempt(mode):
    _, _, provider, refiner, proposal = fixture()
    provider.mode = mode
    with pytest.raises(StructureRefinementError, match="refinement failed") as caught:
        refiner.refine(proposal, max_steps=2)
    assert "private backend path" not in str(caught.value)
    attempt = refiner.attempts[proposal.fingerprint_sha256]
    assert attempt.status == "failure"
    assert attempt.result.evaluation_attempts == attempt.result.failed_evaluations == provider.calls == 1
    assert attempt.result.energy is None


def test_duplicate_attempt_and_step_bound_do_not_dispatch():
    _, _, provider, refiner, proposal = fixture(max_steps=2)
    with pytest.raises(StructureRefinementError, match="max_steps"):
        refiner.refine(proposal, max_steps=3)
    assert provider.calls == 0
    refiner.refine(proposal, max_steps=2)
    count = provider.calls
    with pytest.raises(StructureRefinementError, match="duplicate"):
        refiner.refine(proposal, max_steps=2)
    assert provider.calls == count


def test_provider_identity_change_before_call_rejected_without_work():
    _, _, provider, refiner, proposal = fixture()
    provider.model_fingerprint_sha256 = "4" * 64
    with pytest.raises(StructureRefinementError, match="changed"):
        refiner.refine(proposal, max_steps=1)
    assert provider.calls == 0 and not refiner.attempts


def test_wrong_provider_problem_is_not_admitted():
    authority, ligand, provider, _, _ = fixture()
    provider.problem_fingerprint_sha256 = "4" * 64
    with pytest.raises(StructureRefinementError, match="cross-wired"):
        StructurePreservingPoseRefiner(authority, ligand, provider,
                                      implementation_source_sha256="5" * 64)
    assert provider.calls == 0


def test_source_coordinate_mutation_is_not_admitted():
    _, ligand, provider, refiner, proposal = fixture()
    ligand.coordinates[0, 0, 0] += .01
    with pytest.raises(StructureRefinementError):
        refiner.refine(proposal, max_steps=1)
    assert provider.calls == 0


def test_failed_candidates_remain_in_existing_search_denominator():
    authority, _, provider, refiner, _ = fixture()
    provider.mode = "raise"
    result = run_authenticated_bounded_docking_search(authority,
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1,
                      max_refinement_steps=1, translation_radius_angstrom=0.),
        _Scorer(authority.problem.fingerprint_sha256), refiner=refiner)
    assert len(result.search_result.rows) == len(refiner.attempts) == provider.calls == 2
    assert all(row.status == "failure" for row in result.search_result.rows)


def test_evaluation_limit_keeps_last_accepted_state_without_hidden_call():
    _, _, provider, refiner, proposal = fixture(max_evaluations=1)
    refined = refiner.refine(proposal, max_steps=1)
    assert torch.equal(refined.coordinates, proposal.coordinates)
    attempt = refiner.attempts[proposal.fingerprint_sha256]
    assert attempt.result.status == "evaluation_limit"
    assert not attempt.result.projected_stationary
    assert provider.calls == 1


def test_configuration_mutation_before_call_rejected():
    _, _, provider, refiner, proposal = fixture()
    object.__setattr__(refiner._config, "max_evaluations", 999)
    with pytest.raises(StructureRefinementError, match="changed"):
        refiner.refine(proposal, max_steps=1)
    assert provider.calls == 0


def test_reentrant_same_proposal_does_not_dispatch_recursively():
    _, _, provider, refiner, proposal = fixture()
    def reentrant(points):
        provider.calls += 1
        return refiner.refine(proposal, max_steps=1)
    provider.evaluate = reentrant
    with pytest.raises(StructureRefinementError, match="refinement failed"):
        refiner.refine(proposal, max_steps=1)
    assert provider.calls == 1
    assert refiner.attempts[proposal.fingerprint_sha256].result.failed_evaluations == 1
    assert not refiner._inflight


def test_nonzero_torsion_move_updates_source_relative_metadata():
    from betelgeuze_engine_v2.docking.structure_preserving import StructureTopology, torsion_move
    authority, ligand = _authority(), _system(receptor=False)
    proposal = generate_bounded_docking_proposals(authority.search_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1, translation_radius_angstrom=0.),
        problem=authority.problem)[0]
    provider = AnalyticProvider(authority, ligand)
    points = tuple(tuple(float(v) for v in row) for row in proposal.coordinates.tolist())
    topology = StructureTopology(4, ((0, 1, "single"), (1, 2, "single"), (2, 3, "single")), ((1, 2),))
    # Fix the analytic model before constructing its bound adapter.
    provider.targets = torsion_move(points, topology, 0, .6)
    refiner = StructurePreservingPoseRefiner(authority, ligand, provider,
        implementation_source_sha256="5" * 64,
        config=SearchConfig(max_steps=1, translation_step_angstrom=1.e-8,
                            rotation_step_radians=1.e-8, torsion_step_radians=.1))
    refined = refiner.refine(proposal, max_steps=1)
    attempt = refiner.attempts[proposal.fingerprint_sha256]
    assert any(row.move == "torsion:0" and row.status == "accepted" for row in attempt.result.history)
    assert float(refined.torsion_angles[2]) == pytest.approx(.1, abs=1.e-10)
    assert torch.equal(refined.torsion_angles[[0, 1, 3]], torch.zeros(3, dtype=torch.float64))
    expected = torch.tensor(torsion_move(points, topology, 0, .1), dtype=torch.float64)
    torch.testing.assert_close(refined.coordinates, expected, rtol=0., atol=1.e-11)


@pytest.mark.parametrize("mutation", ["source", "config"])
def test_mutation_inside_provider_retains_failed_call(mutation):
    _, ligand, provider, refiner, proposal = fixture()
    original = provider.evaluate
    def mutate(points):
        result = original(points)
        if mutation == "source":
            ligand.coordinates[0, 0, 0] += .01
        else:
            object.__setattr__(refiner._config, "max_evaluations", 999)
        return result
    provider.evaluate = mutate
    with pytest.raises(StructureRefinementError, match="refinement failed"):
        refiner.refine(proposal, max_steps=1)
    attempt = refiner.attempts[proposal.fingerprint_sha256]
    assert attempt.status == "failure"
    assert attempt.result.failed_evaluations == attempt.result.evaluation_attempts == provider.calls == 1


def test_mutated_authority_rotor_mask_rejected_before_evaluation():
    authority, _, provider, refiner, proposal = fixture()
    authority.search_space.rotatable_mask[2] = False
    with pytest.raises((StructureRefinementError, ValueError)):
        refiner.refine(proposal, max_steps=1)
    assert provider.calls == 0


def test_declared_adapter_source_binds_configuration_and_attempt_receipt():
    authority, ligand, _, first, proposal = fixture(max_evaluations=1)
    second = StructurePreservingPoseRefiner(authority, ligand, AnalyticProvider(authority, ligand),
        implementation_source_sha256="4" * 64, config=SearchConfig(max_evaluations=1))
    one = first.refine(proposal, max_steps=1)
    two = second.refine(proposal, max_steps=1)
    torch.testing.assert_close(one.coordinates, two.coordinates, rtol=0., atol=0.)
    assert first.config_fingerprint_sha256 != second.config_fingerprint_sha256
    a, b = first.attempts[proposal.fingerprint_sha256], second.attempts[proposal.fingerprint_sha256]
    assert a.result == b.result
    assert a.config_sha256 != b.config_sha256
    assert a.receipt_sha256 != b.receipt_sha256


@pytest.mark.parametrize("field", ["refiner_id", "refiner_version", "core_algorithm_id"])
def test_implementation_identity_mutation_fails_before_dispatch(field, monkeypatch):
    from betelgeuze_engine_v2.docking import structure_preserving as core
    _, _, provider, refiner, proposal = fixture()
    if field == "core_algorithm_id":
        monkeypatch.setattr(core, "ALGORITHM_ID", "changed/0")
    else:
        monkeypatch.setattr(refiner, field, "changed/0")
    with pytest.raises(StructureRefinementError, match="changed"):
        refiner.refine(proposal, max_steps=1)
    assert provider.calls == 0
