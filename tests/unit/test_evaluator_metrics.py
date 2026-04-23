import torch
from torch.utils.data import DataLoader, TensorDataset

from train.evaluator import evaluate_model


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
