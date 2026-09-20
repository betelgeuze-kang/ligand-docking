"""Globally incompatible cross inputs must fail before candidate work or publication."""

from dataclasses import replace
import hashlib
import json
import pytest
from betelgeuze_product.cpu_refinement_v1_2 import comparison, comparison_resume
from betelgeuze_product.cpu_refinement_v1_2 import workflow, resumable_workflow
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    FixedReceptorEnvironment,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement.refinement_comparison import (
    RefinementComparisonConfig,
)
from tests.unit.test_cpu_fixed_receptor_pipeline import fixture, request_fixture


@pytest.mark.parametrize("resumable", [False, True])
@pytest.mark.parametrize("equal", [False, True])
@pytest.mark.parametrize("mismatch", ["topology", "charge"])
def test_global_mismatch_rejected_before_force_calls(
    tmp_path, monkeypatch, resumable, equal, mismatch
):
    a, r, ligand, params, fixed, solver, budget = fixture()
    if mismatch == "topology":
        fixed = FixedReceptorEnvironment(
            r, replace(fixed.cross, ligand_topology_sha256=digest("wrong"))
        )
    else:
        atoms = list(params.base_parameters.atom_parameters)
        atoms[0] = replace(atoms[0], charge_e=atoms[0].charge_e + 0.125)
        base = replace(params.base_parameters, atom_parameters=tuple(atoms))
        params = replace(params, base_parameters=base)
        fixed = FixedReceptorEnvironment(
            r,
            replace(fixed.cross, ligand_base_parameters_sha256=base.fingerprint_sha256),
        )
    mode = RefinementComparisonConfig()
    if equal:
        solver = replace(
            solver, minimization=replace(solver.minimization, max_backtracks=0)
        )
        budget = replace(budget, candidate_count=12, max_refinement_steps=2)
        mode = RefinementComparisonConfig(
            mode="equal_work_budget", work_units_per_arm=8
        )
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("globally invalid input reached force evaluation")

    monkeypatch.setattr(FixedReceptorEnvironment, "evaluate_cross", forbidden)
    args = dict(
        receptor_system=r,
        ligand_system=ligand,
        parameters=params,
        solver=solver,
        fixed_environment=fixed,
        comparison=mode,
    )
    run = comparison.run_comparison
    if resumable:
        run = comparison_resume.run_candidate_comparison
        args["output"] = tmp_path / "candidates"
    with pytest.raises(ResearchError, match="ligand"):
        run(a, budget, **args)
    assert calls == []
    assert not (tmp_path / "candidates").exists()


@pytest.mark.parametrize("resumable", [False, True])
def test_request_rejects_global_mismatch_before_output(
    tmp_path, monkeypatch, resumable
):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    request = request_fixture(inputs)
    path = inputs / "cross_parameters-fixed.json"
    cross = json.loads(path.read_text())
    cross["ligand_topology_sha256"] = digest("wrong")
    raw = json.dumps(cross).encode()
    path.write_bytes(raw)
    request["cross_parameters"]["sha256"] = hashlib.sha256(raw).hexdigest()
    module = resumable_workflow if resumable else workflow

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid request reached comparison execution")

    monkeypatch.setattr(
        module, "run_candidate_comparison" if resumable else "run_comparison", forbidden
    )
    run = module.run_resumable_request if resumable else module.run_request
    with pytest.raises(ResearchError, match="ligand"):
        run(request, tmp_path / "out")
    assert not (tmp_path / "out").exists()
