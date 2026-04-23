import torch

from train.runtime_inputs import filter_runtime_conditioning_params, resolve_sim_params


def test_filter_runtime_conditioning_params_blocks_target_like_fields():
    raw = {
        "temp": torch.tensor([300.0, 310.0], dtype=torch.float32),
        "salt_conc": torch.tensor([0.1, 0.2], dtype=torch.float32),
        "is_llps": torch.tensor([1.0, 0.0], dtype=torch.float32),
        "is_folded": torch.tensor([0.0, 1.0], dtype=torch.float32),
        "rmsd": torch.tensor([1.2, 1.0], dtype=torch.float32),
        "energy": torch.tensor([-12.0, -11.5], dtype=torch.float32),
        "violations": torch.tensor([0.0, 1.0], dtype=torch.float32),
    }
    filtered = filter_runtime_conditioning_params(raw)
    assert "temp" in filtered
    assert "salt_conc" in filtered
    assert "is_llps" not in filtered
    assert "is_folded" not in filtered
    assert "rmsd" not in filtered
    assert "energy" not in filtered
    assert "violations" not in filtered


def test_resolve_sim_params_keeps_conditioning_fields_and_defaults():
    raw = {
        "temp": torch.tensor([299.0, 301.0], dtype=torch.float32),
        "salt_conc": torch.tensor([0.1, 0.2], dtype=torch.float32),
        "ionic_strength": torch.tensor([0.18, 0.22], dtype=torch.float32),
        "ptm_count": torch.tensor([2.0, 4.0], dtype=torch.float32),
        "cooling_rate": 0.03,
        "is_folded": 1.0,
    }
    out = resolve_sim_params(raw)
    assert abs(float(out["temp"]) - 300.0) < 1e-6
    assert abs(float(out["salt_conc"]) - 0.15) < 1e-6
    assert abs(float(out["ionic_strength"]) - 0.20) < 1e-6
    assert abs(float(out["ptm_count"]) - 3.0) < 1e-6
    assert abs(float(out["cooling_rate"]) - 0.03) < 1e-6
    assert "pH" in out  # core default retained
    assert "is_folded" not in out
