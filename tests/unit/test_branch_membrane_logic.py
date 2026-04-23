import torch

from theory.branches.membrane_logic import MembraneLogic


def test_membrane_logic_outputs_finite_force():
    dev = torch.device("cpu")
    mod = MembraneLogic(dev).to(dev)
    c = torch.tensor(
        [
            [
                [0.0, 0.0, -8.0],
                [2.5, 0.0, -2.0],
                [5.0, 0.0, 2.0],
                [7.5, 0.0, 8.0],
            ]
        ],
        dtype=torch.float32,
        device=dev,
    )
    nb_idx = torch.tensor([[[1, 2], [0, 2], [1, 3], [1, 2]]], dtype=torch.long, device=dev)
    nb_dist = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    nb_mask = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    top = type("Top", (), {"residue_types": torch.tensor([[0, 4, 9, 2]], dtype=torch.long, device=dev)})()
    sim_params = {"membrane_normal": [0.0, 0.0, 1.0], "membrane_midplane": 0.0}
    f, info = mod(c, top=top, nb_data=(nb_idx, nb_dist, nb_mask), pe=None, sim_params=sim_params)
    assert f.shape == c.shape
    assert torch.isfinite(f).all()
    assert float(torch.linalg.norm(f, dim=-1).mean().item()) > 0.0
    assert "mean_hydrophobic_mismatch_A" in info
