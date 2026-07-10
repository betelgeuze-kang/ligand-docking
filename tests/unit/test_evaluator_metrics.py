import inspect

import torch
from torch.utils.data import DataLoader, TensorDataset

from train import evaluator
from train.evaluator import _pairwise_lj_energy, _sparse_overlap_flags, evaluate_model


class _ZeroModel(torch.nn.Module):
    def forward(self, c, top, nb_data, pe, sim_params, ai_influence=1.0):
        return torch.zeros_like(c), {}


class _HugeForceModel(torch.nn.Module):
    def forward(self, c, top, nb_data, pe, sim_params, ai_influence=1.0):
        return torch.ones_like(c) * 1000.0, {}


def test_evaluator_energy_drift_and_violation_rate_stable_case():
    coords = torch.zeros((4, 8, 3), dtype=torch.float32)
    coords[:, :, 0] = torch.arange(8, dtype=torch.float32).unsqueeze(0).repeat(4, 1) * 2.0
    target = torch.zeros((4, 8, 3), dtype=torch.float32)
    residue_types = torch.zeros((4, 8), dtype=torch.long)
    loader = DataLoader(TensorDataset(coords, target, residue_types), batch_size=2, shuffle=False)

    model = _ZeroModel()
    res = evaluate_model(model, loader, device=torch.device("cpu"), metrics=["rmse", "mae", "energy_drift", "violation_rate"])
    assert abs(float(res["rmse"])) < 1e-8
    assert abs(float(res["mae"])) < 1e-8
    assert abs(float(res["energy_drift"])) < 1e-8
    assert abs(float(res["violation_rate"])) < 1e-8


def test_evaluator_violation_rate_detects_unstable_forces():
    coords = torch.zeros((2, 6, 3), dtype=torch.float32)
    target = torch.zeros((2, 6, 3), dtype=torch.float32)
    residue_types = torch.zeros((2, 6), dtype=torch.long)
    loader = DataLoader(TensorDataset(coords, target, residue_types), batch_size=2, shuffle=False)

    model = _HugeForceModel()
    res = evaluate_model(model, loader, device=torch.device("cpu"), metrics=["violation_rate"])
    assert float(res["violation_rate"]) > 0.0


def test_sparse_lj_metric_counts_each_local_pair_once():
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float64)
    observed = _pairwise_lj_energy(coords, sigma=4.0, eps=2.0, cutoff=5.0)
    assert torch.allclose(observed, torch.zeros_like(observed), atol=1.0e-12)


def test_sparse_overlap_flags_are_per_sample_and_fail_closed():
    coords = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        ],
        dtype=torch.float32,
    )
    assert _sparse_overlap_flags(coords, threshold=1.2).tolist() == [False, True]

    overcrowded = torch.zeros((1, 66, 3), dtype=torch.float32)
    assert _sparse_overlap_flags(overcrowded, threshold=1.2).tolist() == [True]


def test_sparse_metrics_fail_closed_instead_of_crashing_on_nonfinite_coordinates():
    coords = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [float("nan"), 0.0, 0.0]],
        ],
        dtype=torch.float32,
    )
    assert _sparse_overlap_flags(coords, threshold=1.2).tolist() == [False, True]
    energies = _pairwise_lj_energy(coords, cutoff=3.0)
    assert torch.isfinite(energies[0])
    assert torch.isinf(energies[1])

    overcrowded = torch.zeros((1, 129, 3), dtype=torch.float32)
    assert torch.isinf(_pairwise_lj_energy(overcrowded)[0])


def test_evaluator_uses_current_checkpoint_runtime_schema(monkeypatch):
    captured = {}

    def _capture_runtime_inputs(coords_batch, residue_types_batch, **kwargs):
        captured.update(kwargs)
        batch, atoms, _ = coords_batch.shape
        k = int(kwargs["neighbor_k"])
        top = object()
        neighbors = (
            torch.full((batch, atoms, k), -1, dtype=torch.long),
            torch.zeros((batch, atoms, k), dtype=coords_batch.dtype),
            torch.zeros((batch, atoms, k), dtype=coords_batch.dtype),
        )
        return top, neighbors, torch.zeros((batch, 1)), {}

    schema = {
        "neighbor_k": 3,
        "cutoff_angstrom": 7.5,
        "max_neighbor_candidates": 9,
        "max_atoms_per_cell": 11,
    }
    monkeypatch.setattr(evaluator, "current_runtime_input_schema_metadata", lambda: schema)
    monkeypatch.setattr(evaluator, "build_runtime_inputs", _capture_runtime_inputs)
    coords = torch.zeros((1, 2, 3), dtype=torch.float32)
    target = torch.zeros_like(coords)
    residues = torch.zeros((1, 2), dtype=torch.long)
    loader = DataLoader(TensorDataset(coords, target, residues), batch_size=1)
    evaluate_model(_ZeroModel(), loader, torch.device("cpu"), metrics=["rmse"])
    assert captured["neighbor_k"] == 3
    assert captured["neighbor_cutoff_angstrom"] == 7.5
    assert captured["max_neighbor_candidates"] == 9
    assert captured["max_atoms_per_cell"] == 11


def test_evaluator_does_not_use_all_pairs_distance_matrix():
    assert "torch.cdist" not in inspect.getsource(evaluator)
