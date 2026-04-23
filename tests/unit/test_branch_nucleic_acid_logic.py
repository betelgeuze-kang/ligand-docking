import torch

from theory.branches.nucleic_acid_logic import NucleicAcidLogic


def test_nucleic_acid_logic_outputs_finite_force():
    dev = torch.device("cpu")
    mod = NucleicAcidLogic(dev).to(dev)
    c = torch.tensor(
        [
            [
                [0.0, 0.0, 0.0],
                [3.8, 0.0, 0.0],
                [7.6, 0.2, 0.0],
                [11.4, 0.1, 0.1],
            ]
        ],
        dtype=torch.float32,
        device=dev,
    )
    nb_idx = torch.tensor([[[1, 2], [0, 2], [1, 3], [1, 2]]], dtype=torch.long, device=dev)
    nb_dist = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    nb_mask = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    f, info = mod(c, top=None, nb_data=(nb_idx, nb_dist, nb_mask), pe=None, sim_params={})
    assert f.shape == c.shape
    assert torch.isfinite(f).all()
    assert float(torch.linalg.norm(f, dim=-1).mean().item()) > 0.0
    assert "mean_stacking_force" in info
