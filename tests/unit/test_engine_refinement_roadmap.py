from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from betelgeuze_product.engine_dispatch import build_dispatch_manifest, engine_roadmap_ready
from core.ai_correction import NeuralForceCorrection, SE3EquivariantCorrection
from core.interaction_forces import analytic_hbond_forces
from core.onsps_backmap import backmap_4bead_onsps, needs_onsps_4bead, onsps_hbond_sites_from_smiles
from core.score_residual import apply_score_residual
from core.sequence_topology import hbond_role_for_residue_index, residue_indices_from_sequence
from core.topology import TopologyFactory
from core.topo_corrector import summarize_topo_correction
from core.definitions import StrategyType
from theory.branches.hbond_logic import HbondLogic
from theory.force_residual_shortlist import refine_forces_shortlist, should_apply_force_residual
from theory.specialists import HBSpecialist, HydrophobicSpecialist
from tools.run_ligand_backmapping_scoring import (
    _frame_mmpbsa_proxy,
    _resolve_ligand_model_for_row,
)


def test_ai_correction_forward_runs():
    model = NeuralForceCorrection(hidden_dim=64, num_layers=1)
    b, n, k = 1, 8, 4
    c = torch.randn(b, n, 3)
    nb_idx = torch.randint(0, n, (b, n, k))
    nb_dist = torch.rand(b, n, k)
    nb_mask = torch.ones(b, n, k)
    nb_data = (nb_idx, nb_dist, nb_mask)
    top = type("Top", (), {"residue_features": torch.randn(n, 64)})()
    f_corr, aux = model.forward(c, top, nb_data, torch.zeros(b, 1), {"temp": 300.0})
    assert f_corr.shape == (b, n, 3)
    assert "mean_force_magnitude" in aux
    assert aux["correction_model_class"] == "NeuralForceCorrection"
    assert aux["se3_equivariant"] is False
    assert aux["claim_grade"] == "frame_dependent_neural_force_correction"
    assert model.claim_metadata()["claim_safe"] is False
    assert model.claim_metadata()["blocked_reason"] == "neural_force_correction_not_product_claim_promoted"


def test_legacy_se3_name_is_compatibility_alias_not_product_claim():
    model = SE3EquivariantCorrection(hidden_dim=64, num_layers=1)

    assert isinstance(model, NeuralForceCorrection)
    assert model.claim_metadata()["correction_model_class"] == "NeuralForceCorrection"
    assert model.claim_metadata()["se3_equivariant"] is False


def test_neural_force_correction_rotation_audit_blocks_se3_claim():
    torch.manual_seed(7)
    model = NeuralForceCorrection(hidden_dim=64, num_layers=1)
    model.eval()
    b, n, k = 1, 5, 3
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.0, 0.2, 0.0], [2.0, -0.3, 0.4], [3.0, 0.1, -0.2], [4.0, 0.0, 0.3]]],
        dtype=torch.float32,
    )
    nb_idx = torch.tensor([[[1, 2, 3], [0, 2, 4], [0, 1, 3], [0, 2, 4], [1, 2, 3]]], dtype=torch.long)
    nb_dist = torch.ones(b, n, k, dtype=torch.float32)
    nb_mask = torch.ones(b, n, k, dtype=torch.float32)
    top = type("Top", (), {"residue_features": torch.zeros(n, 64)})()
    sim_params = {"temp": 300.0, "salt_conc": 0.1, "pH": 7.0, "ionic_strength": 0.15}
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
    )

    forces, aux = model(coords, top, (nb_idx, nb_dist, nb_mask), torch.zeros(b, 1), sim_params)
    rotated_forces, _ = model(
        torch.matmul(coords, rotation.transpose(-1, -2)),
        top,
        (nb_idx, nb_dist, nb_mask),
        torch.zeros(b, 1),
        sim_params,
    )
    expected_rotated_forces = torch.matmul(forces, rotation.transpose(-1, -2))
    rotation_error = float((rotated_forces - expected_rotated_forces).abs().max().item())

    assert aux["se3_equivariant"] is False
    assert model.claim_metadata()["claim_safe"] is False
    assert rotation_error > 1e-5


def test_topology_sequence_aware_and_adress_gate(capsys):
    top = TopologyFactory(
        n_res=5,
        t_type=0,
        box_size=[100.0, 100.0, 100.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )
    top.set_residue_types_from_sequence_string("ACDEF")
    assert top.topology_fidelity() == "sequence_mapped"
    assert "donor" in top.hbond_roles() or "acceptor" in top.hbond_roles()
    top_adress = TopologyFactory(
        n_res=5,
        t_type=0,
        box_size=[100.0, 100.0, 100.0],
        device="cpu",
        strategy_type=StrategyType.ADRESS,
    )
    captured = capsys.readouterr().out
    assert "BLOCKED (AdResS research path" in captured
    assert "ACTIVE (AdResS" not in captured
    with pytest.raises(RuntimeError):
        top_adress.get_adress_neighbor_data(torch.zeros(1, 10, 3))


def test_specialists_emit_nonzero_forces():
    dev = torch.device("cpu")
    hb = HbondLogic(dev)
    assert getattr(HBSpecialist, "always_zero_output", True) is False
    c = torch.tensor([[[0.0, 0.0, 0.0], [2.8, 0.0, 0.0]]], dtype=torch.float32)
    nb_idx = torch.tensor([[[1, 0], [0, 1]]], dtype=torch.long)
    nb_dist = torch.tensor([[[2.8, 5.0], [2.8, 5.0]]], dtype=torch.float32)
    nb_mask = torch.ones(1, 2, 2)
    f, info = hb.forward(c, None, (nb_idx, nb_dist, nb_mask), None, {})
    assert float(f.abs().sum().item()) > 0.0
    assert float(info["mean_force"]) >= 0.0
    assert getattr(HydrophobicSpecialist, "always_zero_output", True) is False


def test_onsps_backmap_and_scoring_models():
    two_bead = np.asarray([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
    mapped, meta = backmap_4bead_onsps(two_bead, "CCO")
    assert mapped.ndim == 2 and mapped.shape[1] == 3
    assert meta["site_count"] >= 1
    sites = onsps_hbond_sites_from_smiles("CCO")
    assert len(sites) >= 1
    assert needs_onsps_4bead(smiles="CCO", family="gpcr") is True
    row = {"ligand_smiles": "CCO", "family": "gpcr"}
    assert _resolve_ligand_model_for_row(row, "2bead") == "4bead_onsps_hbond"
    props = {"affinity_hint": 0.5, "polar_norm": 0.4, "logp_norm": 0.3, "onsps_norm": 0.2}
    score_4 = _frame_mmpbsa_proxy(
        protein_xyz=np.asarray([[0.0, 0.0, 0.0], [2.5, 0.0, 0.0]], dtype=np.float32),
        ligand_xyz=two_bead,
        props=props,
        contact_cutoff_A=6.0,
        ligand_model="4bead_onsps_hbond",
        smiles="CCO",
    )
    assert score_4["ligand_model"] == "4bead_onsps_hbond"
    assert score_4["onsps_site_count"] >= 1


def test_score_residual_and_topo_corrector():
    residual = apply_score_residual(
        1.0,
        family="kinase",
        prior_pressure=0.2,
        structural_weakness=0.3,
        structural_support=0.1,
        topo_delta=-0.05,
        mode="assist",
    )
    assert residual["status"] == "residual_ready"
    topo = summarize_topo_correction({"site_count": 2, "roles": ["donor", "acceptor"]}, 1.0, 0.8)
    assert "topo_correction_delta" in topo
    assert topo["topology_correction_contract"] == "topology_score_correction_bounded_v1"
    assert topo["topology_correction_scope"] == "score_ranking_heuristic"
    assert topo["topology_correction_physical_force_claim"] is False
    assert topo["topology_correction_bounded"] is True
    assert topo["topology_correction_policy_caps"]["max_abs_delta_score"] == pytest.approx(1.0)


def test_force_residual_shortlist_hook():
    assert should_apply_force_residual(rank_index=0, total_count=100, top_k_fraction=0.05) is True
    assert should_apply_force_residual(rank_index=90, total_count=100, top_k_fraction=0.05) is False
    c = torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]]], dtype=torch.float32)
    f_core = torch.zeros_like(c)
    nb_idx = torch.tensor([[[1, 0], [0, 1]]], dtype=torch.long)
    nb_dist = torch.tensor([[[3.0, 8.0], [3.0, 8.0]]], dtype=torch.float32)
    nb_mask = torch.ones(1, 2, 2)
    f_total, meta = refine_forces_shortlist(c, (nb_idx, nb_dist, nb_mask), f_core)
    assert meta["force_residual_applied"] is True
    assert float(f_total.abs().sum().item()) > 0.0


def test_engine_dispatch_manifest(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True)
    (runs / "independent_engine_roadmap_status_current.json").write_text(
        json.dumps({"summary": {"status": "independent_engine_roadmap_closed"}}),
        encoding="utf-8",
    )
    import betelgeuze_product.engine_dispatch as dispatch

    dispatch.ENGINE_ROADMAP_ARTIFACT = runs / "independent_engine_roadmap_status_current.json"
    assert engine_roadmap_ready() is True
    manifest = build_dispatch_manifest(job_id="j1", target_id="ADRB2", family="gpcr")
    assert manifest["dispatch_ready"] is True
    assert manifest["runner_profile_id"]


def test_sequence_topology_helpers():
    idx = residue_indices_from_sequence("AC", device="cpu")
    assert int(idx.numel()) == 2
    assert hbond_role_for_residue_index(16) in {"donor", "both"}
