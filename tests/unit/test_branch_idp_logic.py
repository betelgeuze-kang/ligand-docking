import torch

from theory.branches.idp_logic import IDPLogic


def _mock_nb(dev):
    nb_idx = torch.tensor(
        [[[1, 2], [0, 2], [1, 3], [1, 2]]],
        dtype=torch.long,
        device=dev,
    )
    nb_dist = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    nb_mask = torch.ones((1, 4, 2), dtype=torch.float32, device=dev)
    return nb_idx, nb_dist, nb_mask


def test_idp_logic_default_off_returns_zero_force():
    dev = torch.device("cpu")
    mod = IDPLogic(dev).to(dev)
    c = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.5, 0.4, 0.2], [3.0, 1.0, 0.5], [4.2, 1.9, 1.1]]],
        dtype=torch.float32,
        device=dev,
    )
    top = type("Top", (), {"residue_types": torch.tensor([[1, 5, 6, 11]], dtype=torch.long, device=dev)})()
    f, info = mod(c, top=top, nb_data=_mock_nb(dev), pe=None, sim_params={})
    assert f.shape == c.shape
    assert torch.allclose(f, torch.zeros_like(c))
    assert info["enabled"] is False


def test_idp_logic_enabled_outputs_finite_force():
    dev = torch.device("cpu")
    mod = IDPLogic(dev).to(dev)
    c = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.3, 0.7, 0.1], [2.7, 1.6, 0.6], [4.0, 2.4, 1.3]]],
        dtype=torch.float32,
        device=dev,
    )
    top = type("Top", (), {"residue_types": torch.tensor([[1, 5, 6, 11]], dtype=torch.long, device=dev)})()
    sim_params = {
        "idp_virtual_hbond_enabled": 1,
        "ionic_strength": 0.15,
        "pH": 7.4,
        "ptm_count": 1,
        "hydro_strength": 1.1,
    }
    f, info = mod(c, top=top, nb_data=_mock_nb(dev), pe=None, sim_params=sim_params)
    assert f.shape == c.shape
    assert torch.isfinite(f).all()
    assert float(torch.linalg.norm(f, dim=-1).mean().item()) > 0.0
    assert info["enabled"] is True
    assert "virtual_hbond_contacts" in info
    assert "anti_collapse_force_mean" in info
    assert float(info["anti_collapse_force_mean"]) >= 0.0
    assert "three_bead_cb_mean_distance_A" in info
    assert float(info["three_bead_cb_mean_distance_A"]) > 0.0


def test_idp_logic_component_force_diagnostics_default_off(monkeypatch):
    monkeypatch.delenv("IDP_COMPONENT_FORCE_DIAGNOSTICS", raising=False)
    monkeypatch.delenv("IDP_PAIRWISE_CONTACT_DIAGNOSTICS", raising=False)
    dev = torch.device("cpu")
    mod = IDPLogic(dev).to(dev)
    c = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.3, 0.7, 0.1], [2.7, 1.6, 0.6], [4.0, 2.4, 1.3]]],
        dtype=torch.float32,
        device=dev,
    )
    top = type("Top", (), {"residue_types": torch.tensor([[1, 5, 6, 11]], dtype=torch.long, device=dev)})()
    sim_params = {
        "idp_virtual_hbond_enabled": 1,
        "ionic_strength": 0.15,
        "pH": 7.4,
        "ptm_count": 1,
        "hydro_strength": 1.1,
    }
    _, info = mod(c, top=top, nb_data=_mock_nb(dev), pe=None, sim_params=sim_params)
    assert float(info["mean_fuzzy_force"].item()) > 0.0
    assert float(info["hbond_force_mean"].item()) == 0.0
    assert float(info["sticker_force_mean"].item()) == 0.0
    assert float(info["bridge_force_mean"].item()) == 0.0
    assert float(info["helix_force_mean"].item()) == 0.0
    assert float(info["sticker_contacts"].item()) == 0.0
    assert float(info["pi_pi_contacts"].item()) == 0.0
    assert float(info["cation_pi_contacts"].item()) == 0.0
    assert float(info["bridge_contacts"].item()) == 0.0
