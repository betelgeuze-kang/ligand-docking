#!/usr/bin/env python3

import torch

from core.definitions import Config, ResearchConstants
from core.forcefield import ForceField
from core.integrator import LangevinIntegrator
from core.spatial import GridSpatialHash
from core.topology import TopologyFactory
from monitor.physics_guard import PhysicsGuard
from runtime.governance import AIControlModel, RuntimeGovernanceLayer
from theory.strategy import AIRouter, StrategicOrchestrator


def run():
    # 1) ForceField smoke
    n_res = 5
    box = [10.0, 10.0, 10.0]
    top = TopologyFactory(n_res, "protein", box, Config.DEVICE, target_name="test")
    ff = ForceField(top, params={"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2})
    c = torch.linspace(0, 4, n_res, device=Config.DEVICE).view(1, n_res, 1).repeat(1, 1, 3)
    sh = GridSpatialHash(box, 12.0, Config.DEVICE)
    nb = sh.get_neighbor_data(c)
    f, pe = ff.compute(c, nb)
    assert f.shape == c.shape and pe.shape == (1, 1)

    # 2) RuntimeGovernance smoke (3-tuple router_info compatibility)
    ctrl = AIControlModel(input_dim=11, output_dim=3)
    gov = RuntimeGovernanceLayer(ctrl)
    sim = {"RMSD": 2.0, "energy": -100.0, "temp": 300.0, "ionic_strength": 0.1, "Rg": 1.5, "SASA": 100.0}
    router_info = (torch.tensor([[0.1, 0.9]]), ["m1", "m2"], torch.tensor([False]))
    guard = {"violation_count": 0, "last_energy_drift": 0.0, "last_momentum_drift": 0.0}
    gov.update(sim, router_info, guard)
    reward = gov.calculate_reward(
        {"RMSD": 1.8, "energy": -101.0, "temp": 300.0, "ionic_strength": 0.1, "Rg": 1.4, "SASA": 105.0},
        (torch.tensor([[0.1, 0.9]]), ["m1", "m2"], torch.tensor([True])),
        guard,
    )
    assert reward > 0.0

    # 3) AIRouter smoke
    router = AIRouter(num_modules=5, explore_prob=0.0).to(Config.DEVICE)
    bsz, n = 1, 10
    c_router = torch.randn(bsz, n, 3, device=Config.DEVICE)
    top_router = type("MockTop", (), {"residue_features": torch.randn(n, 64, device=Config.DEVICE)})()
    aux = {f"module_{i}": torch.randn(bsz, n, 4, device=Config.DEVICE) for i in range(5)}
    weights, is_explored, names, active_mask = router(c_router, top_router, aux, {"temp": 300.0, "salt_conc": 0.1})
    assert weights.shape == (bsz, 5)
    assert is_explored.shape == (bsz,)
    assert len(names) == 5
    assert active_mask.shape == (bsz, 5)
    assert torch.allclose(weights.sum(dim=-1), torch.ones(bsz, device=Config.DEVICE), atol=1e-5)

    # 4) StrategicOrchestrator smoke
    orch = StrategicOrchestrator(Config.DEVICE).to(Config.DEVICE)
    top_orch = type("MockTop", (), {"residue_types": torch.randint(0, 20, (bsz, n), device=Config.DEVICE)})()
    nb_orch = (
        torch.randint(0, n, (bsz, n, 10), device=Config.DEVICE),
        torch.randn(bsz, n, 10, device=Config.DEVICE),
        torch.ones(bsz, n, 10, device=Config.DEVICE),
    )
    pe_orch = torch.randn(bsz, 1, device=Config.DEVICE)
    f_orch, aux_out = orch(c_router, top_orch, nb_orch, pe_orch, {"temp": 300.0, "salt_conc": 0.1})
    assert f_orch.shape == c_router.shape
    for key in ("router_was_explored", "router_used_weights", "router_action_log_probs", "router_active_mask"):
        assert key in aux_out

    # 5) Mini integration smoke
    target = "Chignolin"
    t_conf = ResearchConstants.CHALLENGES[target]
    top_int = TopologyFactory(t_conf["n_res"], t_conf["type"], t_conf["box"], Config.DEVICE, target_name=target)
    ff_int = ForceField(top_int, params={"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2})
    sh_int = GridSpatialHash(t_conf["box"], 12.0, Config.DEVICE)
    integrator = LangevinIntegrator(dt=0.002, friction=1.0, kT=0.001987 * 300.0)
    physics_guard = PhysicsGuard(max_energy_drift=0.02, max_momentum_drift=0.015)
    physics_guard.set_system_size(t_conf["n_res"])
    c_int = torch.linspace(0, t_conf["n_res"] - 1, t_conf["n_res"], device=Config.DEVICE).view(1, t_conf["n_res"], 1).repeat(1, 1, 3)
    v_int = torch.zeros_like(c_int)
    for step in range(2):
        nb_int = sh_int.get_neighbor_data(c_int)
        f_int, pe_int = ff_int.compute(c_int, nb_int)
        v_int, c_int = integrator.step(c_int, v_int, f_int)
        physics_guard.check_conservation(c_int, v_int, pe_int, f_int, torch.zeros_like(f_int), step)

    print("SMOKE_OK")


if __name__ == "__main__":
    run()
