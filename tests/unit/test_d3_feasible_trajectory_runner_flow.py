"""Synthetic runner failures retain evidence and never run molecular evaluators."""
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import torch

from docs.research.human_5ht6_d3_complex import feasible_trajectory_development_experiment as runner


class SyntheticLigand:
    def __init__(self, coordinates=None):
        self.coordinates = (torch.zeros((1, 1, 3), dtype=torch.float64)
                            if coordinates is None else coordinates.clone())
        self.atoms = [SimpleNamespace(element="C")]
        self.bonds = ()

    def with_coordinates(self, coordinates, *, operation):
        return SyntheticLigand(coordinates)


@pytest.fixture
def synthetic_run(tmp_path, monkeypatch):
    """Keep real core, publication and source guards; replace molecular setup."""
    state = SimpleNamespace(output=tmp_path / "result", product_geometry_calls=0,
                            placement_calls=0, ledger_calls=0, oracle_calls=0,
                            combined_calls=0, internal_calls=0,
                            final_passed=True, final_complete=True, malformed=None)
    ligand = SyntheticLigand()
    receptor = SyntheticLigand(torch.full((1, 1, 3), 10., dtype=torch.float64))

    def source_file(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return path

    ligand_xml = source_file("ligand.xml", {})
    receptor_xml = source_file("receptor.xml", {})
    geometry_path = source_file("geometry.json", {"pocket_all_heavy_maximum_radius_angstrom": 5.})
    request = {"schema_id": runner.REGISTERED_REQUEST_SCHEMA, "solvation": None,
               "pocket": {"center_angstrom": [0., 0., 0.], "radius_angstrom": 5.}}
    for name in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        request[name] = runner.common.reference(source_file(name + ".json", {}))
    request_path = source_file("request.json", request)
    monkeypatch.setattr(runner.common, "GEOMETRY_PROTOCOL_SHA256",
                        runner.common.reference(geometry_path)["sha256"])
    monkeypatch.setattr(runner.previous, "ORIGINAL_LIGAND_FILE_SHA256", request["ligand"]["sha256"])
    sources = {"synthetic": "no-native-force-code"}
    monkeypatch.setattr(runner, "source_manifest", lambda: sources.copy())
    monkeypatch.setattr(runner, "runtime_identity", lambda: {"synthetic": True})
    monkeypatch.setattr(runner, "_bound", lambda ref: json.loads(Path(ref["path"]).read_text()))
    monkeypatch.setattr(runner, "canonical_system_sha256", lambda item: runner.digest(item.coordinates.tolist()))
    monkeypatch.setattr(runner, "canonical_topology_sha256", lambda item: "one-carbon-topology")
    monkeypatch.setattr(runner, "canonical_system_json_bytes",
                        lambda item: json.dumps(item.coordinates.tolist(), allow_nan=False).encode())
    parameters = SimpleNamespace(constraints=(), metadata={
        "source_xml_sha256": runner.common.reference(ligand_xml)["sha256"]},
        base_parameters=SimpleNamespace(cutoff_angstrom=6.))
    solver = SimpleNamespace(minimization=SimpleNamespace(
        force_tolerance_kcal_per_mol_angstrom=.001, max_neighbors=16, max_atoms_per_cell=16),
        to_dict=lambda: {"synthetic": True})
    monkeypatch.setattr(runner, "load_request", lambda *args: (
        None, receptor, ligand, parameters, None, solver, None, None, None))
    fixed = SimpleNamespace(cross=SimpleNamespace(max_internal_increase_kcal_per_mol=5.,
        parameter_source_sha256=runner.common.reference(receptor_xml)["sha256"]),
        validate_ligand=lambda *args: None, assert_intact=lambda: None)
    monkeypatch.setattr(runner, "CrossParameters", SimpleNamespace(from_dict=lambda value: value))
    monkeypatch.setattr(runner, "FixedReceptorEnvironment", lambda *args: fixed)
    monkeypatch.setattr(runner, "ExtendedEvaluator", lambda *args: None)
    monkeypatch.setattr(runner, "build_compact_radius_graph", lambda *args: None)

    def evaluation(internal=False):
        state.internal_calls += int(internal)
        state.combined_calls += int(not internal)
        energy = float("inf") if state.malformed == "infinite_energy" and not internal else 0.
        forces = torch.zeros((1, 1, 3), dtype=torch.float64)
        if state.malformed == "nan_gradient" and not internal:
            forces[0, 0, 0] = float("nan")
        return SimpleNamespace(term=SimpleNamespace(
            energy=torch.tensor([energy], dtype=torch.float64), forces=forces),
            component_energies={"ligand_internal": torch.zeros(1, dtype=torch.float64)})

    evaluator = SimpleNamespace(evaluate=lambda *args: evaluation(),
        internal=SimpleNamespace(evaluate=lambda *args: evaluation(internal=True)))
    monkeypatch.setattr(runner, "FixedReceptorEvaluator", lambda *args: evaluator)
    monkeypatch.setattr(runner, "components_document", lambda value: {
        "total": float(value.term.energy[0]), "ligand_internal": 0.})

    def product_geometry(*args, **kwargs):
        state.product_geometry_calls += 1
        final = state.product_geometry_calls > 1
        return {"passed": state.final_passed if final else True,
                "complete": state.final_complete if final else True,
                "checks": {str(i): True for i in range(8)}}

    adapter = SimpleNamespace(criteria=lambda: {"pose_validity_config": {
        "bond_length_tolerance_angstrom": .15}}, baseline_report=lambda: {"passed": True},
        evaluate_coordinates=product_geometry)
    monkeypatch.setattr(runner.product_geometry, "ProductGeometryAudit", lambda *args: adapter)

    def placement(*args):
        state.placement_calls += 1
        return {"passed": True, "checks": {str(i): True for i in range(6)}}

    monkeypatch.setattr(runner.common, "geometry_observation", placement)

    def ledger(*args, **kwargs):
        state.ledger_calls += 1
        return {"passed": True, "synthetic": True}

    monkeypatch.setattr(runner.ledger_auditor, "audit_trajectory", ledger)
    # Even importing the real oracle is unnecessary in these flow tests.
    import tools.analysis
    oracle = ModuleType("tools.analysis.openmm_d3_numerical_audit")
    oracle.__file__ = __file__
    oracle.ENERGY_ABSOLUTE_TOLERANCE = oracle.FORCE_ABSOLUTE_TOLERANCE = 1e-8
    monkeypatch.setitem(sys.modules, oracle.__name__, oracle)
    monkeypatch.setattr(tools.analysis, "openmm_d3_numerical_audit", oracle, raising=False)

    def numerical_audit(module, cost, *args, **kwargs):
        assert module is oracle
        assert kwargs["perturbations"] == 0
        state.oracle_calls += 1
        cost["whole_audit_wall_seconds"] = 0.
        return {"all_same_math_checks_passed": True,
                "denominator": {"requested": 2, "evaluated": 2, "rejected": 0, "passed": 2},
                "snapshots": [{"coordinates_sha256": "synthetic-original"}]}

    monkeypatch.setattr(runner.previous, "measured_audit", numerical_audit)
    monkeypatch.setattr(runner.previous, "verify_audit_coverage", lambda *args: None)
    monkeypatch.setattr(runner.common, "verify_numerical_receipt", lambda *args: None)
    monkeypatch.setattr(runner.derivative_helper, "verify_optimizer_derivatives", lambda *args: [])
    state.run = lambda: runner.run(request_path, geometry_path, ligand_xml, receptor_xml,
                                   state.output, runner.digest(sources))
    state.read = lambda name: json.loads((state.output / name).read_text())
    return state


@pytest.mark.parametrize("verdict", ["final_passed", "final_complete"])
def test_final_geometry_must_pass_and_be_complete(synthetic_run, verdict):
    setattr(synthetic_run, verdict, False)
    with pytest.raises(ValueError):
        synthetic_run.run()
    assert synthetic_run.product_geometry_calls == 2
    assert synthetic_run.placement_calls == 3  # Setup, native point, retained point.
    assert synthetic_run.ledger_calls == synthetic_run.oracle_calls == 1
    failure = synthetic_run.read("failure.json")
    assert failure["phase"] == "final_retained_geometry"
    assert failure["product_qualified"] is False
    assert not (synthetic_run.output / "report.json").exists()


@pytest.mark.parametrize("malformed", ["nan_gradient", "infinite_energy"])
def test_invalid_native_result_preserves_json_and_full_geometry(synthetic_run, malformed):
    synthetic_run.malformed = malformed
    with pytest.raises(ValueError):
        synthetic_run.run()
    observations = synthetic_run.read("objective-observations.json")
    assert len(observations) == 1
    assert observations[0]["objective_point_attempt"] == 1
    assert observations[0]["status"] == "invalid_result"
    assert observations[0]["raw_result"]
    # Reading strict JSON and reserializing must preserve diagnostics without NaN tokens.
    json.dumps(observations, allow_nan=False)
    trajectory = synthetic_run.read("trajectory.json")
    counters = trajectory["counters"]
    assert counters["completed_objective_calls"] == 1
    assert counters["failed_objective_calls"] == 0
    assert counters["invalid_objective_results"] == counters["validity_calls"] == 1
    assert synthetic_run.product_geometry_calls == 1
    assert synthetic_run.placement_calls == 2
    assert synthetic_run.combined_calls == synthetic_run.internal_calls == 1
    assert synthetic_run.oracle_calls == 0
    assert trajectory["raw_force_converged"] is False
    assert synthetic_run.read("failure.json")["product_qualified"] is False
    assert not (synthetic_run.output / "report.json").exists()


def test_published_file_mutation_stops_before_dependent_audit(synthetic_run, monkeypatch):
    publish = runner.published_json

    def mutate_prior_publication(path, value, refs):
        result = publish(path, value, refs)
        if Path(path).name == "objective-observations.json":
            prior = synthetic_run.output / "trajectory.json"
            assert "trajectory.json" in refs  # Already bound before observations publish.
            prior.write_text(prior.read_text() + "\n")
        return result

    monkeypatch.setattr(runner, "published_json", mutate_prior_publication)
    with pytest.raises(ValueError, match="source_file_changed_during_experiment"):
        synthetic_run.run()
    assert synthetic_run.product_geometry_calls == 1
    assert synthetic_run.ledger_calls == synthetic_run.oracle_calls == 0
    assert synthetic_run.read("failure.json")["product_qualified"] is False
    assert not (synthetic_run.output / "trajectory-audit.json").exists()
    assert not (synthetic_run.output / "report.json").exists()
