"""Independent BFGS algebra, bounded work, and frozen evidence contracts."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from docs.research.human_5ht6_d3_complex import lbfgs_development_experiment as experiment


def settings(**changes):
    return {**experiment.PROTOCOL, **changes}


def quadratic(matrix):
    def objective(xyz):
        flat = xyz.flatten()
        gradient = (matrix @ flat).reshape_as(xyz)
        energy = float(0.5 * flat @ matrix @ flat)
        return energy, gradient, {"ligand_internal": energy, "total": energy}
    return objective


def test_two_loop_matches_independently_formed_dense_inverse_bfgs_updates():
    matrix = torch.tensor([[9., 2., 1.], [2., 4., .5], [1., .5, 2.]], dtype=torch.float64)
    history = []
    for vector in ([.4, -.2, .6], [-.3, .5, .2], [.1, .2, -.3]):
        s = torch.tensor([vector], dtype=torch.float64)
        history.append((s, (matrix @ s.flatten()).reshape_as(s)))
    last_s, last_y = history[-1]
    gamma = float((last_s * last_y).sum() / last_y.square().sum())
    identity = torch.eye(3, dtype=torch.float64)
    dense = gamma * identity
    for s, y in history:
        s, y = s.flatten(), y.flatten()
        rho = 1. / float(s @ y)
        left = identity - rho * torch.outer(s, y)
        dense = left @ dense @ left.T + rho * torch.outer(s, s)
    gradient = torch.tensor([[2., -4., 7.]], dtype=torch.float64)
    observed = experiment.inverse_hessian_product(gradient, history, .001)
    torch.testing.assert_close(observed.flatten(), dense @ gradient.flatten(), rtol=0, atol=1e-14)
    assert float(gradient.flatten() @ observed.flatten()) > 0.


def test_no_history_uses_frozen_initial_inverse_hessian_scale():
    gradient = torch.tensor([[3., -2., 1.]], dtype=torch.float64)
    torch.testing.assert_close(experiment.inverse_hessian_product(gradient, [], .001), .001 * gradient,
                               rtol=0, atol=0)


def test_spd_quadratic_converges_with_actual_armijo_and_per_atom_displacement_cap():
    torch.manual_seed(212)
    basis = torch.randn(6, 6, dtype=torch.float64)
    matrix = basis.T @ basis + 0.5 * torch.eye(6, dtype=torch.float64)
    original = torch.tensor([[.3, -.2, .1], [-.1, .2, -.4]], dtype=torch.float64)
    preserved = original.clone()
    rows = []
    xyz, report, first = experiment.bounded_lbfgs(original, quadratic(matrix), rows.append)
    assert report["converged"]
    assert report["final"]["maximum_atom_force"] <= .001
    assert report["force_evaluation_attempts"] <= 192 and report["accepted_steps"] <= 128
    assert report["retained_history_pairs"] <= 10
    assert report["final"]["energy_kcal_mol"] < report["initial"]["energy_kcal_mol"]
    assert first is not None
    assert torch.equal(original, preserved)
    assert not torch.equal(xyz, original)
    accepted = [row for row in rows if row["outcome"] == "accepted"]
    assert len(accepted) == report["accepted_steps"]
    assert all(row["energy_kcal_mol"] <= row["armijo_energy_limit_kcal_mol"] for row in accepted)
    assert all(row["maximum_atom_displacement_angstrom"] <= .05 + 1e-12 for row in rows[1:])
    assert all(row["armijo_slope_kcal_mol"] < 0 for row in rows[1:])


def test_full_192_call_budget_includes_failed_trials_and_never_evaluates_193rd():
    rows, seen = [], []
    def objective(xyz):
        seen.append(xyz.clone())
        # A rejected first trial at each iteration costs exactly one call.
        if len(seen) > 1 and len(seen) % 2 == 0:
            raise FloatingPointError("synthetic numerical failure")
        energy = -float(xyz.sum())
        return energy, -torch.ones_like(xyz), {"ligand_internal": 0., "total": energy}
    xyz, report, first = experiment.bounded_lbfgs(torch.zeros(1, 3, dtype=torch.float64), objective, rows.append)
    assert report["status"] == "force_budget_exhausted_last_accepted_retained"
    assert len(seen) == report["force_evaluation_attempts"] == 192
    assert report["accepted_steps"] == 95
    assert report["failed_force_evaluation_attempts"] == 96
    assert report["trial_count"] == 191
    assert report["skipped_curvature_updates"] == 95
    assert report["outcomes"]["rejected_force_evaluation"] == 96
    assert rows[-1]["outcome"] == "rejected_force_evaluation"
    assert torch.equal(xyz, seen[-2]) and not torch.equal(xyz, seen[-1])
    assert first is not None


def test_maximum_accepted_steps_is_separate_from_call_budget():
    def objective(xyz):
        energy = -float(xyz.sum())
        return energy, -torch.ones_like(xyz), {"total": energy}
    _, report, _ = experiment.bounded_lbfgs(torch.zeros(1, 3, dtype=torch.float64), objective, lambda _: None)
    assert report["accepted_steps"] == 128
    assert report["force_evaluation_attempts"] == 129
    assert report["status"] == "max_accepted_steps_reached"


def test_thirteen_armijo_trials_retained_and_no_rejected_candidate_selected():
    original = torch.zeros(1, 3, dtype=torch.float64)
    calls, rows = [], []
    def objective(xyz):
        calls.append(xyz.clone())
        return (0. if len(calls) == 1 else 1.), torch.ones_like(xyz), {"total": 0.}
    xyz, report, first = experiment.bounded_lbfgs(original, objective, rows.append)
    assert report["status"] == "line_search_failed_last_accepted_retained"
    assert report["accepted_steps"] == 0 and report["trial_count"] == 13
    assert len(calls) == report["force_evaluation_attempts"] == 14
    assert all(row["outcome"] == "rejected_armijo" for row in rows[1:])
    assert first is None and torch.equal(xyz, original)


def test_initial_evaluation_is_in_budget_and_its_failure_is_durable():
    rows = []
    def objective(_):
        raise FloatingPointError("initial invalid")
    with pytest.raises(FloatingPointError, match="initial invalid"):
        experiment.bounded_lbfgs(torch.zeros(1, 3, dtype=torch.float64), objective, rows.append)
    assert len(rows) == 1 and rows[0]["outcome"] == "fatal_initial_evaluation"
    assert rows[0]["force_evaluation_attempt"] == 1 and rows[0]["objective_wall_seconds"] >= 0.


def test_global_integrity_failure_during_objective_is_fatal_without_backtracking():
    rows, calls = [], []
    intact_flag = [True]
    def intact():
        if not intact_flag[0]:
            raise ValueError("source changed")
    def objective(xyz):
        calls.append(xyz.clone())
        if len(calls) == 2:
            intact_flag[0] = False
        return -float(xyz.sum()), -torch.ones_like(xyz), {}
    with pytest.raises(ValueError, match="source changed"):
        experiment.bounded_lbfgs(torch.zeros(1, 3, dtype=torch.float64), objective, rows.append, intact=intact)
    assert len(calls) == len(rows) == 2
    assert rows[-1]["outcome"] == "fatal_evaluation_or_integrity"


def test_integrity_failure_cannot_hide_behind_retryable_numerical_exception():
    rows, calls = [], []
    flag = [True]
    def intact():
        if not flag[0]:
            raise ValueError("mutated during failed call")
    def objective(xyz):
        calls.append(xyz.clone())
        if len(calls) == 2:
            flag[0] = False
            raise FloatingPointError("otherwise retryable")
        return -float(xyz.sum()), -torch.ones_like(xyz), {}
    with pytest.raises(ValueError, match="mutated during failed call"):
        experiment.bounded_lbfgs(torch.zeros(1, 3, dtype=torch.float64), objective, rows.append, intact=intact)
    assert len(calls) == len(rows) == 2
    assert rows[-1]["outcome"] == "fatal_evaluation_or_integrity"


def test_maximum_atom_norm_is_not_rms_or_maximum_component():
    gradient = torch.tensor([[.0007, .0007, .0007], [0., 0., 0.]], dtype=torch.float64)
    assert gradient.abs().max() < .001
    assert experiment.maximum_atom_norm(gradient) > .001
    def objective(xyz):
        return float((xyz * gradient).sum()), gradient, {}
    _, report, _ = experiment.bounded_lbfgs(torch.zeros_like(gradient), objective, lambda _: None,
        protocol=settings(max_force_evaluation_attempts=1))
    assert not report["converged"] and report["status"] == "force_budget_exhausted_last_accepted_retained"


@pytest.mark.parametrize("pair", [([1., 0., 0.], [-1., 0., 0.]), ([0., 0., 0.], [1., 0., 0.]),
                                  ([1., 0., 0.], [0., 1., 0.]), ([float('nan'), 0., 0.], [1., 0., 0.])])
def test_nonpositive_zero_or_nonfinite_curvature_is_explicitly_skipped(pair):
    history = []
    s, y = (torch.tensor([row], dtype=torch.float64) for row in pair)
    row = experiment.curvature_update(history, s, y, experiment.PROTOCOL)
    assert not row["accepted"] and not history
    json.dumps(row, allow_nan=False)


def test_history_discards_only_oldest_and_retains_ten_pairs():
    history = []
    for i in range(12):
        s = torch.full((1, 3), float(i + 1), dtype=torch.float64)
        row = experiment.curvature_update(history, s, 2. * s, experiment.PROTOCOL)
        assert row["accepted"] and row["discarded_oldest_pair"] == (i >= 10)
    assert len(history) == 10
    assert float(history[0][0][0, 0]) == 3.


@pytest.mark.parametrize("invalid", [float("nan"), -1.])
def test_bad_direction_restarts_with_frozen_steepest_direction_and_clears_history(monkeypatch, invalid):
    gradient = torch.tensor([[100., -200., 300.]], dtype=torch.float64)
    history = [(torch.ones_like(gradient), torch.ones_like(gradient))]
    monkeypatch.setattr(experiment, "inverse_hessian_product", lambda *args: gradient * invalid)
    direction, reason, scale = experiment.search_direction(gradient, history, experiment.PROTOCOL)
    assert not history and reason is not None
    assert experiment.maximum_atom_norm(direction) == pytest.approx(.05, abs=1e-15)
    torch.testing.assert_close(direction, -.001 * gradient * scale, rtol=0, atol=0)
    assert float((direction * gradient).sum()) < 0


@pytest.mark.parametrize("change", ["native", "runtime", "script", "oracle", "input", "helpers", "protocol"])
def test_every_source_runtime_protocol_and_input_freeze_is_enforced(tmp_path, monkeypatch, change):
    sources, runtime = {"native": "a"}, {"runtime": "b"}
    monkeypatch.setattr(experiment, "source_manifest", lambda: sources.copy())
    monkeypatch.setattr(experiment, "runtime_identity", lambda: runtime.copy())
    refs = {}
    for name in ("script", "oracle", "input", "helpers"):
        path = tmp_path / name
        path.write_text("original")
        refs[name] = experiment.common.reference(path)
    saved_sources, saved_runtime = sources.copy(), runtime.copy()
    protocol = dict(experiment.PROTOCOL)
    experiment.verify_freeze(saved_sources, saved_runtime, refs, protocol)
    if change == "native":
        sources["native"] = "changed"
    elif change == "runtime":
        runtime["runtime"] = "changed"
    elif change == "protocol":
        protocol["force_tolerance_kcal_mol_angstrom"] = 1.
    else:
        Path(refs[change]["path"]).write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        experiment.verify_freeze(saved_sources, saved_runtime, refs, protocol)


@pytest.mark.parametrize("changed", ["absolute_energy_tolerance_kcal_per_mol",
                                    "absolute_force_component_tolerance_kcal_per_mol_angstrom"])
def test_oracle_tolerance_cannot_be_replaced_by_passing_boolean(changed):
    report = {"protocol": {"absolute_energy_tolerance_kcal_per_mol": 1e-8,
                           "absolute_force_component_tolerance_kcal_per_mol_angstrom": 1e-8},
              "audit_source_sha256": "a", "native_source_manifest_sha256": "b",
              "all_same_math_checks_passed": True}
    report["protocol"][changed] = 1e-7
    with pytest.raises(ValueError, match="tolerance_changed"):
        experiment.common.verify_numerical_receipt(report, "a", "b")


def test_native_source_mismatch_prevents_output_and_physics(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "source_manifest", lambda: {"native": "a"})
    with pytest.raises(ValueError, match="frozen_expected_hash"):
        experiment.run(tmp_path / "request", tmp_path / "geometry", tmp_path / "l.xml",
                       tmp_path / "r.xml", tmp_path / "output", "b" * 64)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("fail", [False, True])
def test_oracle_measurement_counts_every_observation_and_restores_original_callables(fail):
    module = SimpleNamespace()
    def native(x):
        return 2 * x
    def observe(x):
        if x == "fail":
            raise RuntimeError("oracle failed")
        return x + 3
    module._native_components, module._observe = native, observe
    def audit():
        value = module._native_components(4)
        assert module._observe(value) == 11
        module._observe("fail" if fail else 2)
        return {"unchanged_result": value}
    module.audit = audit
    cost = {}
    if fail:
        with pytest.raises(RuntimeError, match="oracle failed"):
            experiment.measured_audit(module, cost)
    else:
        assert experiment.measured_audit(module, cost) == {"unchanged_result": 8}
    assert module._native_components is native and module._observe is observe
    assert cost["native_combined_snapshots"]["calls"] == 1
    assert cost["openmm_energy_force_observations"]["calls"] == 2
    assert cost["openmm_energy_force_observations"]["failed_calls"] == int(fail)
    assert cost["whole_audit_wall_seconds"] >= 0.


@pytest.mark.parametrize("change", [None, "denominator", "coordinates", "coordinate_hash", "input", "final_binding"])
def test_oracle_must_cover_exact_original_and_supplied_states(change):
    original = torch.tensor([[1., 2., 3.]], dtype=torch.float64)
    supplied = original + .1
    refs = {name: {"sha256": name} for name in ("request", "ligand_xml", "receptor_xml")}
    bound = {"sha256": "coordinates"}
    report = {"denominator": {"requested": 2, "evaluated": 2, "rejected": 0, "passed": 2},
        "snapshots": [{"coordinates_angstrom": xyz.tolist(), "coordinates_sha256": experiment.digest(xyz.tolist()),
                       "passed": True} for xyz in (original, supplied)],
        "inputs": {"request": refs["request"], "ligand_XML": refs["ligand_xml"], "receptor_XML": refs["receptor_xml"]},
        "final_coordinates": bound.copy()}
    if change == "denominator":
        report["denominator"]["requested"] = 1
    elif change == "coordinates":
        report["snapshots"][1]["coordinates_angstrom"] = original.tolist()
    elif change == "coordinate_hash":
        report["snapshots"][1]["coordinates_sha256"] = "changed"
    elif change == "input":
        report["inputs"]["request"] = {"sha256": "changed"}
    elif change == "final_binding":
        report["final_coordinates"]["sha256"] = "changed"
    if change:
        with pytest.raises(ValueError, match="coverage|mismatch"):
            experiment.verify_audit_coverage(report, original, supplied, refs, bound)
    else:
        experiment.verify_audit_coverage(report, original, supplied, refs, bound)


@pytest.mark.parametrize("schema", sorted(experiment.FIXED_REQUEST_SCHEMAS))
def test_supported_request_schemas_reach_same_native_loader_before_physics(tmp_path, monkeypatch, schema):
    sources = {"native": "a"}
    monkeypatch.setattr(experiment, "source_manifest", lambda: sources)
    request = {"schema_id": schema, "solvation": None}
    for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        path = tmp_path / (key + ".json")
        path.write_text("{}")
        ref = experiment.common.reference(path)
        request[key] = {k: v for k, v in ref.items() if k != "bytes"}
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    geometry, ligand_xml, receptor_xml = (tmp_path / name for name in ("geometry", "l.xml", "r.xml"))
    for path in (geometry, ligand_xml, receptor_xml):
        path.write_text("{}")
    monkeypatch.setattr(experiment.common, "GEOMETRY_PROTOCOL_SHA256", experiment.common.reference(geometry)["sha256"])
    monkeypatch.setattr(experiment, "ORIGINAL_LIGAND_FILE_SHA256", request["ligand"]["sha256"])
    def loader(value, identity):
        assert value["schema_id"] == experiment.REQUEST_SCHEMA
        assert value["ligand"] == request["ligand"]
        assert identity == experiment.digest(sources)
        raise RuntimeError("reached unchanged native loader")
    monkeypatch.setattr(experiment, "load_request", loader)
    with pytest.raises(RuntimeError, match="unchanged native loader"):
        experiment.run(request_path, geometry, ligand_xml, receptor_xml, tmp_path / "out", experiment.digest(sources))
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("mutate_plan", [False, True])
def test_published_plan_precedes_original_pose_physics_and_failure_cost_survives(tmp_path, monkeypatch, mutate_plan):
    from tests.unit.test_cpu_fixed_receptor import system
    from tools.analysis import openmm_d3_numerical_audit
    ligand = system([[2., 3., 4.]], [.1], "ligand")
    receptor = system([[0., 0., 0.]], [-.1], "receptor")
    sources = {"native": "a"}
    monkeypatch.setattr(experiment, "source_manifest", lambda: sources)
    monkeypatch.setattr(experiment, "runtime_identity", lambda: {"runtime": "frozen"})
    request = {"schema_id": sorted(experiment.FIXED_REQUEST_SCHEMAS)[0], "solvation": None,
               "pocket": {"center_angstrom": [0., 0., 0.], "radius_angstrom": 10.}}
    for key in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        path = tmp_path / (key + ".json")
        path.write_text("{}")
        ref = experiment.common.reference(path)
        request[key] = {k: v for k, v in ref.items() if k != "bytes"}
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    geometry, ligand_xml, receptor_xml = (tmp_path / name for name in ("geometry", "l.xml", "r.xml"))
    geometry.write_text(json.dumps({"pocket_all_heavy_maximum_radius_angstrom": 10.}))
    ligand_xml.write_text("ligand xml source")
    receptor_xml.write_text("receptor xml source")
    monkeypatch.setattr(experiment.common, "GEOMETRY_PROTOCOL_SHA256", experiment.common.reference(geometry)["sha256"])
    monkeypatch.setattr(experiment, "ORIGINAL_LIGAND_FILE_SHA256", request["ligand"]["sha256"])
    monkeypatch.setattr(experiment.common, "geometry_observation", lambda *args: {"passed": True})
    params = SimpleNamespace(constraints=(), base_parameters=SimpleNamespace(cutoff_angstrom=10.),
        metadata={"source_xml_sha256": experiment.common.reference(ligand_xml)["sha256"]})
    solver = SimpleNamespace(minimization=SimpleNamespace(force_tolerance_kcal_per_mol_angstrom=.001,
        maximum_atom_displacement_angstrom=.05, max_neighbors=256, max_atoms_per_cell=256), to_dict=lambda: {})
    monkeypatch.setattr(experiment, "load_request", lambda *args: (None, receptor, ligand, params, None, solver, None, None, None))
    fixed = SimpleNamespace(cross=SimpleNamespace(max_internal_increase_kcal_per_mol=5.,
        parameter_source_sha256=experiment.common.reference(receptor_xml)["sha256"]),
        assert_intact=lambda: None, validate_ligand=lambda *args: None)
    monkeypatch.setattr(experiment.CrossParameters, "from_dict", lambda _: None)
    monkeypatch.setattr(experiment, "FixedReceptorEnvironment", lambda *args: fixed)
    monkeypatch.setattr(experiment, "ExtendedEvaluator", lambda *args: None)
    monkeypatch.setattr(experiment, "build_compact_radius_graph", lambda *args: None)
    output = tmp_path / "out"
    observations = []
    def evaluate(state, graph):
        plan = json.loads((output / "plan.json").read_text())
        observations.append(state.coordinates.clone())
        assert plan["protocol"] == experiment.PROTOCOL
        assert plan["original_coordinates_sha256"] == experiment.digest(ligand.coordinates[0].tolist())
        assert not plan["input_placement_applied"] and not plan["rigid_prestep_applied"]
        assert torch.equal(state.coordinates, ligand.coordinates)
        if mutate_plan:
            (output / "plan.json").write_text("{}")
        raise FloatingPointError("controlled initial failure")
    monkeypatch.setattr(experiment, "FixedReceptorEvaluator", lambda *args: SimpleNamespace(evaluate=evaluate))
    monkeypatch.setattr(openmm_d3_numerical_audit, "audit", lambda *args, **kwargs: pytest.fail("failed optimizer reached oracle"))
    expected = ValueError if mutate_plan else FloatingPointError
    message = "published_plan_changed" if mutate_plan else "controlled initial failure"
    with pytest.raises(expected, match=message):
        experiment.run(request_path, geometry, ligand_xml, receptor_xml, output, experiment.digest(sources))
    failure = json.loads((output / "failure.json").read_text())
    assert len(observations) == 1
    assert failure["native_optimizer_cost"]["force_calls"] == 1
    assert failure["native_optimizer_cost"]["failed_force_calls"] == 1
    assert failure["recorded_trial_outcomes"] == {"fatal_initial_evaluation": 1}
    assert not (output / "report.json").exists()
