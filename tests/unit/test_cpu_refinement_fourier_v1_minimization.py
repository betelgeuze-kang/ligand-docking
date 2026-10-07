from dataclasses import replace
import pytest
import torch
from tests.unit.test_cpu_fixed_receptor import system, base_parameters, environment
from betelgeuze_engine_v2.molecular import (
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    ReferenceForceFieldV2Parameters,
)
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import (
    ReferenceMinimizationConfig,
)
from betelgeuze_product.cpu_refinement_v1_2.minimization import (
    SolverConfig,
    minimize_extended,
    require_checkpoint as require_old,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_fourier_v1 import (
    FourierParameters,
    NonbondedParameter,
    FourierCrossParameters,
    FourierEnvironment,
)
from betelgeuze_product.cpu_refinement_fourier_v1.minimization import (
    minimize_fourier,
    require_checkpoint,
)

torch.set_num_threads(1)


def fixture():
    ligand = system([[2.0, 0.0, 0.0]], name="synthetic-ligand")
    receptor = system([[0.0, 0.0, 0.0]], name="synthetic-receptor")
    model = FourierParameters(
        "synthetic-control",
        "1",
        canonical_topology_sha256(ligand),
        (NonbondedParameter(0, 1.0, 0.5, 0.0),),
    )
    cross = FourierCrossParameters(
        "synthetic-cross",
        "b" * 64,
        canonical_system_sha256(receptor),
        canonical_topology_sha256(ligand),
        model.fingerprint_sha256,
        "test-frame",
        (NonbondedParameter(0, 1.0, 0.5, 0.0),),
        6.0,
        4.0,
        0.2,
        4.0,
        0.15,
        2,
        2.0,
    )
    fixed = FourierEnvironment(receptor, cross)
    config = SolverConfig(
        ReferenceMinimizationConfig(
            max_iterations=4,
            max_backtracks=3,
            initial_step_size_angstrom2_mol_per_kcal=0.03,
        )
    )
    return ligand, model, config, fixed


def test_new_checkpoint_and_restart_work():
    ligand, model, config, fixed = fixture()
    before = ligand.coordinates.clone()
    paused = minimize_fourier(
        ligand,
        model,
        config,
        fixed_environment=fixed,
        pause_after_accepted_iterations=1,
    )
    assert paused.status == "checkpointed"
    assert paused.execution["force_evaluation_calls"] == 2
    restored = require_checkpoint(paused.checkpoint.to_dict())
    with pytest.raises(ResearchError):
        require_old(restored)
    resumed = minimize_fourier(
        ligand, model, config, fixed_environment=fixed, checkpoint=restored
    )
    direct = minimize_fourier(ligand, model, config, fixed_environment=fixed)
    assert resumed.status == "max_iterations_reached"
    assert resumed.execution["restart_verification_calls"] == 1
    assert resumed.execution["force_evaluation_calls"] == 4
    assert resumed.checkpoint.to_dict() == direct.checkpoint.to_dict()
    assert torch.equal(ligand.coordinates, before)
    assert (
        resumed.to_dict()["schema_id"]
        == "cpu_prepared_fourier_minimization_result/1.0.0"
    )


def test_old_checkpoint_rejected_by_new_profile():
    ligand, model, config, fixed = fixture()
    old_base = base_parameters(ligand)
    old = minimize_extended(
        ligand,
        ReferenceForceFieldV2Parameters(old_base),
        config,
        fixed_environment=environment(fixed.receptor, ligand, old_base),
        pause_after_accepted_iterations=1,
    )
    assert (
        require_old(old.checkpoint).to_dict()["schema_id"]
        == "cpu_corrected_projected_checkpoint/1.2.0"
    )
    with pytest.raises(ResearchError):
        require_checkpoint(old.checkpoint)
    with pytest.raises(ResearchError):
        minimize_fourier(
            ligand, model, config, fixed_environment=fixed, checkpoint=old.checkpoint
        )


def test_parameter_drift_cannot_resume():
    ligand, model, config, fixed = fixture()
    paused = minimize_fourier(
        ligand,
        model,
        config,
        fixed_environment=fixed,
        pause_after_accepted_iterations=1,
    )
    changed = replace(model, parameter_set_version="2")
    changed_fixed = replace(
        fixed,
        cross=replace(
            fixed.cross, ligand_base_parameters_sha256=changed.fingerprint_sha256
        ),
    )
    with pytest.raises(ResearchError):
        minimize_fourier(
            ligand,
            changed,
            config,
            fixed_environment=changed_fixed,
            checkpoint=paused.checkpoint,
        )


def test_checkpoint_cannot_drop_fixed_profile_identity():
    ligand, model, config, fixed = fixture()
    paused = minimize_fourier(
        ligand,
        model,
        config,
        fixed_environment=fixed,
        pause_after_accepted_iterations=1,
    )
    changed = paused.checkpoint.to_dict()
    changed["evaluator"] = {"evaluator_id": "different_nonfixed_profile"}
    changed.pop("initial_components")
    changed.pop("current_components")
    changed["checkpoint_sha256"] = digest(
        {k: v for k, v in changed.items() if k != "checkpoint_sha256"}
    )
    with pytest.raises(ResearchError):
        require_checkpoint(changed)
    with pytest.raises(ResearchError):
        minimize_fourier(
            ligand, model, config, fixed_environment=fixed, checkpoint=changed
        )


def test_composed_finite_components_overflow_rejected(monkeypatch):
    from betelgeuze_engine_v2.geometry import (
        RadiusGraphConfig,
        build_compact_radius_graph,
    )
    from betelgeuze_product.cpu_refinement_fourier_v1 import (
        FourierInternalEvaluator,
        FourierFixedEvaluator,
    )

    ligand, model, config, fixed = fixture()
    neighbors = build_compact_radius_graph(
        ligand.coordinates, RadiusGraphConfig(cutoff_angstrom=model.cutoff_angstrom)
    )
    base = FourierInternalEvaluator(model).evaluate(ligand, neighbors)
    huge = replace(
        base,
        term=replace(
            base.term,
            energy=torch.tensor([1e308], dtype=torch.float64),
            forces=torch.full_like(base.term.forces, 1e308),
        ),
    )
    monkeypatch.setattr(FourierInternalEvaluator, "evaluate", lambda *args: huge)
    monkeypatch.setattr(
        FourierEnvironment,
        "evaluate_cross",
        lambda *args: (
            {
                "cross_lennard_jones": torch.tensor([1e308], dtype=torch.float64),
                "cross_screened_coulomb": torch.tensor([1e308], dtype=torch.float64),
            },
            torch.full_like(base.term.forces, 1e308),
            1,
        ),
    )
    with pytest.raises(ValueError, match="finite"):
        FourierFixedEvaluator(model, fixed).evaluate(ligand, neighbors)
