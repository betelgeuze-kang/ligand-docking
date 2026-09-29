"""Rigid development mechanics, frozen geometry and complete bounded trials."""
import importlib.util
import json
from pathlib import Path

import pytest
import torch

PATH = Path(__file__).resolve().parents[2] / "docs/research/human_5ht6_d3_complex/d3_development_experiment.py"
SPEC = importlib.util.spec_from_file_location("d3_development_rigid_math", PATH)
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def points():
    return torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 2., 0.], [0., 0., 3.]], dtype=torch.float64)


@pytest.mark.parametrize("vector", [[0., 0., 0.], [1e-12, -2e-12, 3e-12], [.4, -.7, .8], [3.141592653589793, 0., 0.]])
def test_exponential_rotation_preserves_distances_and_chirality(vector):
    original = points()
    rotation = experiment.proper_rotation(vector)
    moved, drift = experiment.transform_from_original(original, rotation, torch.tensor([84., 110., 82.]))
    assert drift <= 1e-10
    torch.testing.assert_close(rotation.T @ rotation, torch.eye(3, dtype=torch.float64), atol=1e-12, rtol=0)
    assert float(torch.linalg.det(rotation)) == pytest.approx(1., abs=1e-12)
    assert float(torch.linalg.det(moved[1:] - moved[0])) == pytest.approx(float(torch.linalg.det(original[1:] - original[0])), abs=1e-10)


@pytest.mark.parametrize("rotation", [torch.diag(torch.tensor([-1., 1., 1.])), torch.eye(3) * 1.001, torch.eye(3) * float("nan")])
def test_reflections_scaling_and_nonfinite_transforms_rejected(rotation):
    with pytest.raises(ValueError, match="proper_rigid"):
        experiment.transform_from_original(points(), rotation.double(), torch.zeros(3, dtype=torch.float64))


def test_rigid_projection_has_zero_residual_net_force_and_torque():
    xyz = points()
    force = torch.tensor([[.4, 2., -1.], [3., 1., .2], [1., -4., 2.], [-3., 2., 4.]], dtype=torch.float64)
    translation, omega, tangent = experiment.rigid_tangent(xyz, force)
    residual = force - tangent
    relative = xyz - xyz.mean(dim=0)
    torch.testing.assert_close(translation, force.mean(dim=0), atol=1e-12, rtol=0)
    torch.testing.assert_close(residual.sum(dim=0), torch.zeros(3, dtype=torch.float64), atol=1e-12, rtol=0)
    torch.testing.assert_close(torch.linalg.cross(relative, residual, dim=-1).sum(dim=0), torch.zeros(3, dtype=torch.float64), atol=1e-12, rtol=0)
    assert float((force * tangent).sum()) == pytest.approx(float(tangent.square().sum()), abs=1e-12)
    recovered_t, recovered_o, recovered = experiment.rigid_tangent(xyz, tangent)
    torch.testing.assert_close(recovered_t, translation, atol=1e-12, rtol=0)
    torch.testing.assert_close(recovered_o, omega, atol=1e-12, rtol=0)
    torch.testing.assert_close(recovered, tangent, atol=1e-12, rtol=0)


def test_projected_direction_matches_independent_energy_derivative():
    xyz = points()
    target = xyz + torch.tensor([.3, -.7, .2], dtype=torch.float64)
    target[2] += torch.tensor([.1, .2, -.5], dtype=torch.float64)
    force = target - xyz
    translation, omega, tangent = experiment.rigid_tangent(xyz, force)
    h = 1e-5
    plus, _ = experiment.transform_from_original(xyz, experiment.proper_rotation(h * omega), h * translation)
    minus, _ = experiment.transform_from_original(xyz, experiment.proper_rotation(-h * omega), -h * translation)
    derivative = float(((plus - target).square().sum() - (minus - target).square().sum()) / (4. * h))
    assert derivative == pytest.approx(-float((force * tangent).sum()), abs=1e-9)


def test_thirty_two_composed_steps_keep_original_pair_distances_and_displacement_cap():
    original = points() + 100.
    xyz = original.clone()
    rotation = torch.eye(3, dtype=torch.float64)
    shift = torch.zeros(3, dtype=torch.float64)
    for _ in range(32):
        translation = torch.tensor([900., -500., 250.], dtype=torch.float64)
        omega = torch.tensor([600., 800., -300.], dtype=torch.float64)
        translation, omega = experiment.bounded_direction(xyz, translation, omega)
        rotation = experiment.proper_rotation(.001 * omega) @ rotation
        shift = shift + .001 * translation
        trial, drift = experiment.transform_from_original(original, rotation, shift)
        assert drift <= 1e-10
        assert float(torch.linalg.vector_norm(trial - xyz, dim=-1).max()) <= .05 + 1e-12
        xyz = trial


def test_singular_rotation_metric_fails_explicitly():
    xyz = torch.tensor([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]], dtype=torch.float64)
    with pytest.raises(ValueError, match="singular"):
        experiment.rigid_tangent(xyz, torch.ones_like(xyz))


def test_bounded_rigid_descent_reduces_objective_without_internal_deformation():
    original = points()
    target = original + torch.tensor([1., .2, -.3], dtype=torch.float64)
    rows = []
    def objective(xyz):
        energy = float(.5 * (xyz - target).square().sum())
        return {"synthetic_quadratic_cross": energy}, target - xyz, len(xyz)
    result, report = experiment.rigid_descent(original, objective, lambda _: {"passed": True}, rows.append)
    assert report["accepted_steps"] == 32
    assert report["cross_force_calls"] == 33
    assert report["trial_count"] == 32
    assert report["final_cross_energy_kcal_mol"] < report["initial_cross_energy_kcal_mol"]
    assert report["maximum_internal_distance_drift_angstrom"] <= 1e-10
    torch.testing.assert_close(torch.pdist(result), torch.pdist(original), atol=1e-10, rtol=0)
    assert len(rows) == 33 and rows[0]["outcome"] == "initial"
    assert all(row["outcome"] == "accepted" for row in rows[1:])
    assert not report["full_coordinate_convergence_claimed"]


def test_every_ineligible_geometry_trial_retained_without_force_evaluation():
    original = points()
    rows = []
    def objective(xyz):
        return {"synthetic_linear_cross": -float(xyz[:, 0].sum())}, torch.tensor([[1., 0., 0.]], dtype=torch.float64).expand_as(xyz), len(xyz)
    result, report = experiment.rigid_descent(original, objective, lambda xyz: {"passed": torch.equal(xyz, original)}, rows.append)
    assert report["accepted_steps"] == 0 and report["cross_force_calls"] == 1
    assert report["trial_count"] == 13
    assert len(rows) == 14
    assert all(row["outcome"] == "rejected_geometry" for row in rows[1:])
    assert all(row["cross_force_wall_seconds"] == 0 for row in rows[1:])
    assert report["status"] == "rigid_line_search_failed_last_accepted_retained"
    assert torch.equal(result, original)


def test_failed_force_trials_retained_and_counted():
    original = points()
    rows = []
    def objective(xyz):
        if not torch.equal(xyz, original):
            raise FloatingPointError("synthetic rejected force")
        return {"synthetic_linear_cross": -float(xyz[:, 0].sum())}, torch.tensor([[1., 0., 0.]], dtype=torch.float64).expand_as(xyz), len(xyz)
    _, report = experiment.rigid_descent(original, objective, lambda _: {"passed": True}, rows.append)
    assert report["cross_force_calls"] == 14 and report["failed_cross_force_calls"] == 13
    assert len(rows) == 14
    assert all(row["outcome"] == "rejected_force_evaluation" for row in rows[1:])


def test_global_integrity_failure_is_recorded_once_and_not_backtracked():
    original = points()
    rows = []
    def objective(xyz):
        if not torch.equal(xyz, original):
            raise ValueError("global binding changed")
        return {"synthetic_linear_cross": -float(xyz[:, 0].sum())}, torch.tensor([[1., 0., 0.]], dtype=torch.float64).expand_as(xyz), len(xyz)
    with pytest.raises(ValueError, match="global binding"):
        experiment.rigid_descent(original, objective, lambda _: {"passed": True}, rows.append)
    assert len(rows) == 2 and rows[-1]["outcome"] == "fatal_force_evaluation"
    assert rows[-1]["cross_force_wall_seconds"] >= 0.


def test_ineligible_initial_geometry_prevents_all_force_work():
    def forbidden(_):
        pytest.fail("geometry rejection reached force evaluation")
    with pytest.raises(ValueError, match="initial_geometry_ineligible"):
        experiment.rigid_descent(points(), forbidden, lambda _: {"passed": False}, lambda _: None)


def test_geometry_keeps_all_distance_ratio_pocket_and_centroid_limits():
    protocol = {"radius_table_angstrom": {"C": 1.7, "H": 1.2},
        "all_atom_minimum_distance_angstrom": 1., "heavy_atom_minimum_distance_angstrom": 2.,
        "all_atom_minimum_radius_sum_ratio": .6, "heavy_atom_minimum_radius_sum_ratio": .72,
        "pocket_all_heavy_maximum_radius_angstrom": 10., "offset_maximum_norm_angstrom": 5.}
    receptor = torch.tensor([[0., 0., 0.]], dtype=torch.float64)
    center = torch.zeros(3, dtype=torch.float64)
    def check(x):
        return experiment.geometry_observation(torch.tensor([[x, 0., 0.]], dtype=torch.float64), ["C"], receptor, ["C"], center, protocol)
    assert check(3.)["passed"]
    assert not check(2.)["checks"]["heavy_ratio"]
    assert not check(.5)["checks"]["all_distance"]
    assert not check(6.)["checks"]["centroid_offset"]
    assert not check(11.)["checks"]["pocket"]


def test_native_source_freeze_is_checked_before_request_or_output(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "source_manifest", lambda: {"file": "a" * 64})
    with pytest.raises(ValueError, match="frozen_expected_hash"):
        experiment.run(tmp_path / "absent.json", tmp_path / "geometry.json", tmp_path / "l.xml",
                       tmp_path / "r.xml", tmp_path / "out", "0" * 64)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("schema", sorted(experiment.FIXED_REQUEST_SCHEMAS))
def test_legacy_and_explicit_chemistry_schemas_reach_unchanged_native_loader(tmp_path, monkeypatch, schema):
    sources = {"file": "a" * 64}
    monkeypatch.setattr(experiment, "source_manifest", lambda: sources)
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"schema_id": schema, "solvation": None}))
    geometry = tmp_path / "geometry.json"
    geometry.write_text("{}")
    ligand_xml, receptor_xml = tmp_path / "l.xml", tmp_path / "r.xml"
    ligand_xml.write_text("source-ligand")
    receptor_xml.write_text("source-receptor")
    monkeypatch.setattr(experiment, "GEOMETRY_PROTOCOL_SHA256", experiment.sha(geometry.read_bytes()))
    def loader(document, identity):
        assert document["schema_id"] == experiment.REQUEST_SCHEMA
        assert identity == experiment.digest(sources)
        raise RuntimeError("reached_unchanged_native_loader")
    monkeypatch.setattr(experiment, "load_request", loader)
    with pytest.raises(RuntimeError, match="unchanged_native_loader"):
        experiment.run(request, geometry, ligand_xml, receptor_xml, tmp_path / "out", experiment.digest(sources))
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("change", ["energy_tolerance", "force_tolerance", "oracle_source", "native_source"])
def test_oracle_receipt_cannot_weaken_frozen_tolerances_or_source(change):
    report = {"protocol": {"absolute_energy_tolerance_kcal_per_mol": 1e-8,
        "absolute_force_component_tolerance_kcal_per_mol_angstrom": 1e-8},
        "audit_source_sha256": "a" * 64, "native_source_manifest_sha256": "b" * 64,
        "all_same_math_checks_passed": True}
    experiment.verify_numerical_receipt(report, "a" * 64, "b" * 64)
    if change == "energy_tolerance":
        report["protocol"]["absolute_energy_tolerance_kcal_per_mol"] = 1e-7
    elif change == "force_tolerance":
        report["protocol"]["absolute_force_component_tolerance_kcal_per_mol_angstrom"] = 1e-7
    elif change == "oracle_source":
        report["audit_source_sha256"] = "c" * 64
    else:
        report["native_source_manifest_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="changed"):
        experiment.verify_numerical_receipt(report, "a" * 64, "b" * 64)


def test_changed_oracle_file_fails_frozen_input_check(tmp_path):
    oracle = tmp_path / "numerical_oracle.py"
    oracle.write_text("ENERGY_ABSOLUTE_TOLERANCE = 1e-8\n")
    bound = {"numerical_oracle": experiment.reference(oracle)}
    experiment.verify_file_references(bound)
    oracle.write_text("ENERGY_ABSOLUTE_TOLERANCE = 1e-7\n")
    with pytest.raises(ValueError, match="source_file_changed"):
        experiment.verify_file_references(bound)
