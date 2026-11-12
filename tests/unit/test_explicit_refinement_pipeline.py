"""Bounded synthetic geometry and explicit toy-model adapter checks, no benchmark."""

# ruff: noqa: E402
from dataclasses import fields, replace
import json
import math
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (
    DockingBudget,
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from betelgeuze_engine_v2.docking.authority import (
    run_authenticated_bounded_docking_search,
)
from betelgeuze_engine_v2.docking.interaction_refinement import (
    InteractionAwareRigidHybridClearanceEnsembleRefinerV6,
    ReceptorClashReliefRefiner,
)
from betelgeuze_engine_v2.docking.proposals import bind_docking_proposal_state
from betelgeuze_engine_v2.docking.refinement_work import (
    count_objective,
    refinement_work_records,
)
from betelgeuze_engine_v2.docking.search import DockingBatchScoreOutcome
from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    InteractionAwareTorsionContactEnsembleRefinerV7,
)
from betelgeuze_engine_v2.docking.torsion_refinement_v9 import (
    InteractionAwareTorsionContactEnsembleRefinerV9,
    TorsionRefinementBoundsV9,
)
from betelgeuze_product.explicit_refinement_pipeline import (
    ContactRefinementProviderV9,
    ExplicitRefinementDockingPipelineV1,
    ExplicitRefinementResultV1,
    FixedReceptorStructureDockingRefinerV1,
    FixedReceptorStructureProviderV1,
    implementation_source_sha256,
    implementation_sources,
)
from betelgeuze_product.fixed_receptor_structure_refinement import (
    FixedReceptorStructureCoordinator,
)
from betelgeuze_product.structure_preserving import SearchConfig
from betelgeuze_product.structure_preserving_refinement import StructureRefinementError
from tests.unit.test_engine_v2_element_contact_round8 import _ligand, _receptor, _pocket
from tests.unit.test_engine_v2_docking_authority_search import _Scorer, _authority
from tests.unit.test_fixed_receptor_structure_refinement import fixture


def _folded_source(*, overlapping=False):
    ligand = replace(
        _ligand(),
        coordinates=torch.tensor(
            [[[0.0, 1.0, 0.0], [0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [1.4, 1.0, 0.0]]],
            dtype=torch.float64,
        ),
    )
    receptor = _receptor(overlapping=overlapping)
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, _pocket()
    )
    source = bind_docking_proposal_state(
        coordinates=ligand.coordinates[0],
        torsion_angles=torch.zeros(ligand.atom_count, dtype=torch.float64),
        rotation=torch.eye(3, dtype=torch.float64),
        translation=torch.zeros(3, dtype=torch.float64),
        proposal_index=0,
        seed=7,
        problem_fingerprint_sha256=authority.problem.fingerprint_sha256,
        search_space_fingerprint_sha256=authority.search_space.fingerprint_sha256,
    )
    return authority, ligand, receptor, source


def test_v9_really_searches_internal_overlap_below_receptor_window_and_retains_both():
    authority, ligand, receptor, source = _folded_source()
    legacy = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(0,),
    )
    newer = InteractionAwareTorsionContactEnsembleRefinerV9(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(0,),
    )
    old = legacy.refine(source, max_steps=2)
    result = newer.refine(source, max_steps=2)
    old_receipt = legacy.receipts[source.fingerprint_sha256]
    receipt = newer.receipts[source.fingerprint_sha256]
    assert float.fromhex(receipt["baseline_v6_receptor_penalty_binary64_hex"]) == 0.0
    assert float.fromhex(receipt["baseline_v6_internal_penalty_binary64_hex"]) > 0.0
    assert old_receipt["torsion_evaluated"] is False
    assert receipt["torsion_evaluated"] is True
    assert receipt["accepted_torsion_steps"] > 0
    assert float.fromhex(
        receipt["final_internal_penalty_binary64_hex"]
    ) < float.fromhex(receipt["baseline_v6_internal_penalty_binary64_hex"])
    retained = newer.retained_candidates(source)
    assert len(retained) == 2
    assert torch.equal(retained[0].coordinates, old.coordinates)
    assert torch.equal(retained[1].coordinates, result.coordinates)
    assert all(
        value.parent_proposal_fingerprint_sha256 == source.fingerprint_sha256
        for value in retained
    )
    retained[0].coordinates.add_(10.0)
    assert torch.equal(
        newer.retained_candidates(source)[0].coordinates, old.coordinates
    )
    assert receipt["historical_receptor_penalty_window_enabled"] is False
    assert receipt["scientifically_validated"] is False


@pytest.mark.parametrize(
    "penalty", [0.0, math.nextafter(2.0, 0.0), 2.0, math.nextafter(4.0, 0.0), 4.0, 10.0]
)
def test_v9_has_no_discontinuous_selection_at_legacy_two_and_four(penalty):
    authority, ligand, receptor, _ = _folded_source()
    old = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(0,),
    )
    new = InteractionAwareTorsionContactEnsembleRefinerV9(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(0,),
    )
    assert old._select_torsion_variant(True, penalty) == (2.0 <= penalty < 4.0)
    assert new._select_torsion_variant(True, penalty)
    assert new._selection_window_reachable(penalty, 2)
    assert not new._stop_torsion_search(penalty, 2)
    assert not new._select_torsion_variant(False, penalty)


def test_all_rigid_arms_are_counted_even_when_their_endpoint_is_discarded(monkeypatch):
    authority, ligand, receptor, source = _folded_source(overlapping=True)
    refiner = InteractionAwareRigidHybridClearanceEnsembleRefinerV6(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(0,),
    )
    calls = []
    original = ReceptorClashReliefRefiner._penalty_and_direction

    def observed(self, coordinates):
        calls.append(self)
        return original(self, coordinates)

    monkeypatch.setattr(ReceptorClashReliefRefiner, "_penalty_and_direction", observed)
    refiner.refine(source, max_steps=2)
    work = refinement_work_records(refiner)[-1]
    assert len(work.children) >= 2
    assert work.total("objective_attempts") == len(calls)
    assert work.total("objective_completed") == len(calls)
    assert work.total("accepted_steps") > work.selected_path_steps
    assert work.to_dict()["discarded_path_steps"] > 0
    assert (
        work.selected_path_steps
        == refiner.receipts[source.fingerprint_sha256]["accepted_steps"]
    )


def test_failed_objective_and_previous_discarded_arm_work_are_retained(monkeypatch):
    authority, ligand, receptor, source = _folded_source(overlapping=True)
    refiner = InteractionAwareRigidHybridClearanceEnsembleRefinerV6(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(0,),
    )

    @count_objective
    def fail(coordinates):
        raise RuntimeError("synthetic second-arm failure")

    monkeypatch.setattr(refiner._v3, "_penalty_and_direction", fail)
    with pytest.raises(RuntimeError, match="second-arm"):
        refiner.refine(source, max_steps=2)
    work = refinement_work_records(refiner)[-1]
    assert work.status == "failure"
    assert len(work.children) == 2
    assert work.children[0].status == "success"
    assert work.children[1].status == "failure"
    assert work.total("objective_attempts") > work.children[0].total(
        "objective_attempts"
    )
    assert work.total("objective_failed") == 1
    assert work.total("objective_attempts") == work.total("objective_completed") + 1
    assert work.total("accepted_steps") > 0


def _budget():
    return DockingBudget(
        candidate_count=2,
        top_k=2,
        max_torsions=1,
        max_refinement_steps=2,
        translation_radius_angstrom=0.0,
        seed=31,
    )


@pytest.mark.parametrize("fourier", [False, True])
def test_explicit_physical_pipeline_runs_real_ef_scores_and_preserves_failure_denominator(
    fourier,
):
    authority, ligand, receptor, parameters, cross, _ = fixture()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, authority.pocket
    )
    if fourier:
        from betelgeuze_product.cpu_refinement_fourier_v1.parameters import (
            FourierParameters,
            NonbondedParameter,
            SignedPeriodicTorsionParameter,
        )
        from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
            FourierCrossParameters,
        )

        base = parameters.base_parameters
        parameters = FourierParameters(
            parameter_set_id="synthetic-pipeline-fourier",
            parameter_set_version="1",
            topology_sha256=base.topology_sha256,
            atom_parameters=tuple(
                NonbondedParameter(
                    row.atom_index,
                    row.sigma_angstrom,
                    row.epsilon_kcal_per_mol,
                    row.charge_e,
                )
                for row in base.atom_parameters
            ),
            bonds=base.bonds,
            angles=base.angles,
            excluded_pairs=base.excluded_pairs,
            torsions=(SignedPeriodicTorsionParameter(0, 1, 2, 3, 2, 0.3, -0.2),),
        )
        document = cross.to_dict()
        document.update(
            schema_id="cpu_prepared_fourier_cross/1.0.0",
            ligand_base_parameters_sha256=parameters.fingerprint_sha256,
        )
        cross = FourierCrossParameters.from_dict(document)
    provider = FixedReceptorStructureProviderV1(
        parameters,
        cross,
        SearchConfig(max_steps=2, max_evaluations=8, max_backtracks=2),
    )
    result = ExplicitRefinementDockingPipelineV1(provider).run(
        authority, ligand, receptor, _budget()
    )
    document = result.to_dict()
    assert len(document["source_outcomes"]) == 2
    assert all(row["status"] == "success" for row in document["source_outcomes"])
    assert len(document["candidates"]) == 4
    assert all(row["status"] == "success" for row in document["candidates"])
    assert all(
        row["physical_evaluation_attempts"] > 0 for row in document["work"].values()
    )
    for receipt in document["refinement_receipts"].values():
        assert receipt["model_fingerprint_sha256"]
        assert receipt["initial_observation"]["components"]
        assert receipt["optimizer_attempt"]["result"]["evaluation_attempts"] <= 8
        assert receipt["cartesian_converged"] is False
        assert receipt["scientifically_validated"] is False
    assert document["accuracy_claim"] is False
    assert len(result.receipt_sha256) == 64
    assert len(document["selected_candidates"]) <= 2


def test_rejected_physical_endpoint_is_preserved_but_never_ranked(monkeypatch):
    import betelgeuze_product.fixed_receptor_structure_refinement as module

    authority, ligand, receptor, parameters, cross, _ = fixture()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, authority.pocket
    )
    monkeypatch.setattr(
        module,
        "final_admission_reasons",
        lambda *args: ("synthetic_final_strain_rejection",),
    )
    provider = FixedReceptorStructureProviderV1(
        parameters,
        cross,
        SearchConfig(max_steps=2, max_evaluations=8, max_backtracks=2),
    )
    result = (
        ExplicitRefinementDockingPipelineV1(provider)
        .run(authority, ligand, receptor, _budget())
        .to_dict()
    )
    refined = [row for row in result["candidates"] if row["role"] == "refined"]
    assert len(refined) == 2
    assert all(row["status"] == "success" for row in refined)
    assert all(
        not row["policy_admissible"]
        and not row["selection_eligible"]
        and not row["selected"]
        for row in refined
    )
    assert all(row["coordinates_binary64_hex"] for row in refined)


def test_physical_failure_preserves_all_sources_and_work(monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
        FixedReceptorEvaluator,
    )

    authority, ligand, receptor, parameters, cross, _ = fixture()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, authority.pocket
    )

    def fail(self, state, neighbors):
        raise RuntimeError("synthetic physical kernel failure")

    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", fail)
    result = (
        ExplicitRefinementDockingPipelineV1(
            FixedReceptorStructureProviderV1(
                parameters,
                cross,
                SearchConfig(max_steps=2, max_evaluations=8, max_backtracks=2),
            )
        )
        .run(authority, ligand, receptor, _budget())
        .to_dict()
    )
    assert len(result["source_outcomes"]) == len(result["work"]) == 2
    assert all(row["status"] == "failure" for row in result["source_outcomes"])
    assert not result["selected_candidates"] and not result["candidates"]
    assert all(
        row["physical_evaluation_attempts"] == 1 for row in result["work"].values()
    )
    assert all(
        row["objective_callback_attempts"] == 1 for row in result["work"].values()
    )


def test_provider_replacement_is_not_a_generic_injection_escape():
    pipeline = ExplicitRefinementDockingPipelineV1(ContactRefinementProviderV9())
    pipeline.provider = object()
    with pytest.raises(StructureRefinementError, match="exact supported"):
        pipeline.run(None, None, None, None)


def test_physical_adapter_works_through_existing_authenticated_search_call():
    authority, ligand, receptor, parameters, cross, _ = fixture()
    provider = FixedReceptorStructureProviderV1(
        parameters,
        cross,
        SearchConfig(max_steps=2, max_evaluations=8, max_backtracks=2),
    )
    adapter = provider.build(
        authority, ligand, receptor, _budget(), implementation_source_sha256()
    )
    result = run_authenticated_bounded_docking_search(
        authority,
        _budget(),
        _Scorer(authority.problem.fingerprint_sha256),
        refiner=adapter,
        diversity_rmsd_angstrom=0.0,
    )
    assert len(result.search_result.rows) == 2
    assert all(row.succeeded for row in result.search_result.rows)
    assert len(adapter.receipts) == len(adapter.work) == 2
    assert all(
        value["physical_evaluation_attempts"] > 0 for value in adapter.work.values()
    )


def test_missing_model_and_cross_wired_provider_fail_before_execution():
    with pytest.raises(StructureRefinementError, match="explicit matching"):
        FixedReceptorStructureProviderV1(None, None)
    authority, ligand, _, _, _, provider = fixture()
    coordinator = FixedReceptorStructureCoordinator(
        authority, ligand, provider, implementation_source_sha256="d" * 64
    )
    other = fixture()[-1]
    with pytest.raises(StructureRefinementError, match="cross-wired"):
        FixedReceptorStructureDockingRefinerV1(coordinator, other)
    assert provider.evaluation_attempts == other.evaluation_attempts == 0
    with pytest.raises(StructureRefinementError, match="exact supported"):
        ExplicitRefinementDockingPipelineV1(object())


def test_explicit_model_frame_mismatch_is_not_automatically_repaired():
    authority, ligand, receptor, parameters, cross, physical = fixture()
    provider = FixedReceptorStructureProviderV1(
        parameters, replace(cross, coordinate_frame_id="wrong-frame")
    )
    with pytest.raises(StructureRefinementError, match="cross-wired"):
        ExplicitRefinementDockingPipelineV1(provider).run(
            authority, ligand, receptor, _budget()
        )
    assert physical.evaluation_attempts == 0


def test_v9_pipeline_retains_and_independently_validates_bounded_candidates():
    authority, ligand, receptor, _, _, _ = fixture()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, authority.pocket
    )
    pipeline = ExplicitRefinementDockingPipelineV1(
        ContactRefinementProviderV9(TorsionRefinementBoundsV9(maximum_torsion_steps=2))
    )
    result = pipeline.run(authority, ligand, receptor, _budget()).to_dict()
    assert len(result["source_outcomes"]) == 2
    assert 2 <= len(result["candidates"]) <= 4
    assert all(row["status"] == "success" for row in result["source_outcomes"])
    for row in result["candidates"]:
        assert row["coordinates_binary64_hex"]
        if row["selected"]:
            assert row["policy_admissible"] and row["pose_validity"]["valid"]
    assert result["claim_blockers"]
    for changed in ("coordinates", "claim", "denominator"):
        forged = json.loads(json.dumps(result))
        if changed == "coordinates":
            forged["candidates"][0]["coordinates_binary64_hex"][0][0] = (999.0).hex()
        elif changed == "claim":
            forged["accuracy_claim"] = True
        else:
            forged["source_outcomes"][0]["retained_count"] += 1
        with pytest.raises(StructureRefinementError):
            ExplicitRefinementResultV1(
                json.dumps(forged, sort_keys=True, separators=(",", ":"))
            )


@pytest.mark.parametrize(
    "relative",
    [
        "betelgeuze_product/cpu_refinement_fourier_v1/evaluation.py",
        "betelgeuze_product/cpu_refinement_v1_2/evaluation.py",
        "betelgeuze_product/cpu_refinement_v1_2/fixed_receptor.py",
        "betelgeuze_engine_v2/physics/reference_forcefield.py",
    ],
)
def test_actual_numerical_source_change_changes_pipeline_identity_without_execution(
    monkeypatch, relative
):
    root = Path(__file__).resolve().parents[2]
    target = root / relative
    inventory = implementation_sources()
    assert relative in inventory
    assert any(name.startswith("betelgeuze_engine_v2/geometry/") for name in inventory)
    before = implementation_source_sha256()
    read = Path.read_bytes

    def changed(path):
        value = read(path)
        return (
            value + b"\n# simulated source drift\n"
            if path.resolve() == target
            else value
        )

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert implementation_source_sha256() != before


@pytest.mark.parametrize("batch", [False, True])
def test_search_detects_coherently_rebound_scorer_mutation_before_scoring(batch):
    authority = _authority()

    class Mutator(_Scorer):
        def score(self, proposal):
            rebound = bind_docking_proposal_state(
                coordinates=proposal.coordinates + 0.01,
                torsion_angles=proposal.torsion_angles,
                rotation=proposal.rotation,
                translation=proposal.translation,
                proposal_index=proposal.proposal_index,
                seed=proposal.seed,
                problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
                search_space_fingerprint_sha256=proposal.search_space_fingerprint_sha256,
            )
            for item in fields(proposal):
                object.__setattr__(proposal, item.name, getattr(rebound, item.name))
            proposal.assert_integrity()
            return 0.0

    if batch:

        class BatchMutator(Mutator):
            def score_batch(self, proposals):
                return tuple(
                    DockingBatchScoreOutcome(score=self.score(proposal))
                    for proposal in proposals
                )

        scorer = BatchMutator(authority.problem.fingerprint_sha256)
    else:
        scorer = Mutator(authority.problem.fingerprint_sha256)
    result = run_authenticated_bounded_docking_search(
        authority, DockingBudget(candidate_count=1, top_k=1, max_torsions=1), scorer
    ).search_result
    assert len(result.rows) == 1
    assert result.rows[0].status == "failure"
    assert not result.rows[0].selection_eligible
    assert not result.top_rows
