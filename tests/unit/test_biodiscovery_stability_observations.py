"""Observation semantics, not experimental binding-stability validation."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
import torch

from betelgeuze_engine.biodiscovery import scoring
from betelgeuze_engine.biodiscovery.screening import TierBetaScreening
from tests.unit.test_biodiscovery_screening import MINI_PDB, VALID_SMILES


def _protein():
    return np.array([[0., 0., 0.], [3., 0., 0.], [0., 3., 0.], [0., 0., 3.]], dtype=np.float32)


def _ligand():
    return np.array([[1., 1., 1.], [2., 1., 1.]], dtype=np.float32)


def _field(monkeypatch, *, fail_at=None, nonfinite=None):
    calls = []

    def evaluate(state, pairs, **kwargs):
        step = len(calls)
        calls.append(step)
        if fail_at == step:
            raise RuntimeError("synthetic_failure")
        forces = torch.zeros_like(state.coords)
        energy = torch.zeros(1, dtype=state.coords.dtype, device=state.coords.device)
        if nonfinite == "forces":
            forces[0, 0, 0] = float("nan")
        if nonfinite == "energy":
            energy[0] = float("inf")
        return SimpleNamespace(forces=forces, energy=energy)

    monkeypatch.setattr(scoring.ProductForceField, "from_registry", lambda *a, **k: SimpleNamespace(energy_forces=evaluate))
    return calls


def test_zero_steps_is_not_run_and_does_not_evaluate_forcefield(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unrequested stability created a force field")

    monkeypatch.setattr(scoring.ProductForceField, "from_registry", forbidden)
    drift, result = scoring.run_stability_simulation(_protein(), _ligand(), steps=0)
    assert drift is None
    assert result["status"] == "not_run"
    assert result["stable"] is None
    assert result["steps_run"] == 0
    assert result["initial_energy"] is None and result["final_energy"] is None


def test_disabled_stability_is_not_a_successful_stability_measurement():
    result = TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
        protein_input=MINI_PDB, ligand_input=VALID_SMILES,
    )
    assert result.ok is True  # Optional work is not required for a score result.
    assert result.stability_ok is None
    assert result.stability_drift_A is None
    stage = next(row for row in result.stage_records if row["stage_id"] == "stability_simulation")
    assert stage["status"] == "not_run"
    assert stage["diagnostics"]["stable"] is None
    assert result.result_manifest["stability"]["ok"] is None
    assert result.result_manifest["stability"]["drift_A"] is None
    assert "stability_failed" not in result.claim_metadata["blocked_reason"]


def test_failure_reports_completed_steps_not_requested_steps(monkeypatch):
    _field(monkeypatch, fail_at=1)
    drift, result = scoring.run_stability_simulation(_protein(), _ligand(), steps=5, temp_k=0.)
    assert drift is None
    assert result["status"] == "failed"
    assert result["steps_requested"] == 5
    assert result["steps_run"] == 1
    assert result["stable"] is False
    assert result["error_step"] == 1
    assert result["elapsed_seconds"] >= 0.


@pytest.mark.parametrize("kind", ["forces", "energy"])
def test_nonfinite_physics_is_a_failure_not_repaired_into_stability(monkeypatch, kind):
    _field(monkeypatch, nonfinite=kind)
    drift, result = scoring.run_stability_simulation(_protein(), _ligand(), steps=2, temp_k=0.)
    assert drift is None
    assert result["status"] == "failed"
    assert result["steps_run"] == 0
    assert result["stable"] is False
    assert "nonfinite" in result["error"]


def test_success_is_an_observed_proxy_with_explicit_limits(monkeypatch):
    _field(monkeypatch)
    drift, result = scoring.run_stability_simulation(_protein(), _ligand(), steps=3, temp_k=0.)
    assert result["status"] == "observed"
    assert result["evidence_kind"] == "computed_proxy_dynamics"
    assert result["steps_run"] == result["steps_requested"] == 3
    assert result["scientific_claim_validated"] is False
    assert result["restart_reproducible"] is None
    assert result["pbc_enabled"] is False
    assert result["elapsed_seconds"] >= 0.
    assert drift == pytest.approx(0.)
    assert result["pose_observations"]["ligand_rmsd_receptor_frame_a"] == pytest.approx(0.)


def test_ligand_escape_is_not_diluted_by_large_receptor():
    protein = np.tile(_protein(), (1000, 1))
    ligand = np.tile(_ligand(), (5, 1))
    moved = ligand + [10., 0., 0.]
    result = scoring.measure_pose_retention(protein, ligand, protein, moved)
    assert result["ligand_rmsd_receptor_frame_a"] == pytest.approx(10.)
    assert result["ligand_rmsd_direct_a"] == pytest.approx(10.)
    assert result["ligand_centroid_displacement_a"] == pytest.approx(10.)
    assert result["contact_retention_fraction"] == 0.


def test_receptor_alignment_removes_only_shared_rigid_motion():
    protein, ligand = _protein(), _ligand()
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    translation = np.array([10., -3., 2.])
    result = scoring.measure_pose_retention(protein, ligand, protein @ rotation.T + translation, ligand @ rotation.T + translation)
    assert result["ligand_rmsd_receptor_frame_a"] == pytest.approx(0., abs=1e-12)
    assert result["ligand_rmsd_direct_a"] > 1.
    assert result["contact_retention_fraction"] == pytest.approx(1.)


def test_degenerate_receptor_alignment_is_unavailable_not_fabricated():
    protein = np.array([[0., 0., 0.], [1., 0., 0.]])
    result = scoring.measure_pose_retention(protein, _ligand(), protein, _ligand())
    assert result["ligand_rmsd_receptor_frame_a"] is None
    assert result["alignment_status"] == "unavailable_degenerate_receptor"


def test_no_initial_contacts_does_not_mean_perfect_retention():
    protein, ligand = _protein(), _ligand() + 100.
    result = scoring.measure_pose_retention(protein, ligand, protein, ligand)
    assert result["initial_contact_count"] == 0
    assert result["contact_retention_fraction"] is None


@pytest.mark.parametrize("params", [dict(steps=-1), dict(steps=True), dict(steps=1.2),
                                   dict(dt=0.), dict(dt=float("nan")), dict(temp_k=-1.)])
def test_invalid_protocol_is_rejected(params):
    with pytest.raises(ValueError):
        scoring.run_stability_simulation(_protein(), _ligand(), **params)


def test_terminal_energy_is_evaluated_at_final_coordinates(monkeypatch):
    calls = []

    def evaluate(state, pairs, **kwargs):
        calls.append(state.coords.detach().clone())
        # Deliberate diagnostic double: inspect energy-coordinate binding only.
        return SimpleNamespace(forces=torch.ones_like(state.coords) * .5,
                               energy=state.coords.sum().reshape(1))

    monkeypatch.setattr(scoring.ProductForceField, "from_registry", lambda *a, **k: SimpleNamespace(energy_forces=evaluate))
    _, result = scoring.run_stability_simulation(_protein(), _ligand(), steps=3, temp_k=0.)
    assert len(calls) == 4
    assert result["final_energy"] == pytest.approx(float(calls[-1].sum()))
    assert result["final_energy"] != result["initial_energy"]
    assert result["energy_trace_length"] == 3


def test_seed_replay_is_checked_separately_from_elapsed_time():
    service = TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=2, seed=7)
    a = service.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
    b = service.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
    assert a.result_manifest["stability"]["status"] == "observed"
    assert a.result_manifest["replay_hash"] == b.result_manifest["replay_hash"]
    assert a.result_manifest["stability"] == b.result_manifest["stability"]
    assert "elapsed_seconds" not in a.result_manifest["stability"]["diagnostics"]
    assert a.diagnostics["execution_observations"]["stability_elapsed_seconds"] >= 0.
    assert b.diagnostics["execution_observations"]["stability_elapsed_seconds"] >= 0.


@pytest.mark.parametrize("offset", [50., -50.])
def test_initial_clamp_box_violation_is_reported_without_repair(monkeypatch, offset):
    calls = _field(monkeypatch)
    drift, result = scoring.run_stability_simulation(_protein() + offset, _ligand(), steps=2)
    assert drift is None and result["status"] == "failed"
    assert result["steps_run"] == 0 and calls == []
    assert result["error"] == "initial_coordinates_outside_proxy_clamp_box"


@pytest.mark.parametrize("value", [np.zeros((0, 3)), np.zeros((2, 2)), np.full((2, 3), np.nan),
                                  np.full((2, 3), 1j), np.full((2, 3), "0"),
                                  np.ma.array(np.zeros((2, 3)), mask=True)])
def test_endpoint_measurements_reject_invalid_ligand_representations(value):
    with pytest.raises(ValueError):
        scoring.measure_pose_retention(_protein(), value, _protein(), _ligand())


def test_endpoint_measurements_require_equal_atom_counts():
    with pytest.raises(ValueError, match="shapes must match"):
        scoring.measure_pose_retention(_protein(), _ligand(), _protein(), _ligand()[:1])


@pytest.mark.parametrize("cutoff", [0., -1., np.nan, np.inf])
def test_contact_measurement_requires_finite_positive_cutoff(cutoff):
    with pytest.raises(ValueError):
        scoring.measure_pose_retention(_protein(), _ligand(), _protein(), _ligand(), contact_cutoff_a=cutoff)
