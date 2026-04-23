import torch

from theory.branches.metal_coordination_logic import MetalCoordinationLogic


def test_metal_coordination_logic_outputs_finite_force():
    dev = torch.device("cpu")
    mod = MetalCoordinationLogic(dev).to(dev)
    c = torch.tensor(
        [
            [
                [0.0, 0.0, 0.0],
                [1.8, 0.0, 0.0],
                [0.0, 1.8, 0.0],
                [1.8, 1.8, 0.0],
            ]
        ],
        dtype=torch.float32,
        device=dev,
    )
    nb_idx = torch.tensor([[[1, 2], [0, 3], [0, 3], [1, 2]]], dtype=torch.long, device=dev)
    nb_dist = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    nb_mask = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    f, info = mod(c, top=None, nb_data=(nb_idx, nb_dist, nb_mask), pe=None, sim_params={})
    assert f.shape == c.shape
    assert torch.isfinite(f).all()
    assert float(torch.linalg.norm(f, dim=-1).mean().item()) > 0.0
    assert int(info.get("active_centers", 0)) >= 1
