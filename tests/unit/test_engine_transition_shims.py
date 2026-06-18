from __future__ import annotations

import importlib

import numpy as np
import torch


def test_core_onsps_backmap_is_compatibility_shim_to_engine() -> None:
    import core.onsps_backmap as legacy
    import betelgeuze_engine.backmapping.onsps as engine

    assert legacy.backmap_4bead_onsps is engine.backmap_4bead_onsps
    assert legacy.onsps_hbond_sites_from_smiles is engine.onsps_hbond_sites_from_smiles
    mapped, meta = legacy.backmap_4bead_onsps(
        np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32),
        "CCO",
    )
    assert mapped.shape[1] == 3
    assert meta["site_count"] >= 1


def test_core_topology_uses_product_engine_protein_topology_bridge() -> None:
    from betelgeuze_engine.topology.protein import ProteinTopology
    from core.definitions import Config
    from core.topology import TopologyFactory

    top = TopologyFactory(2, "protein", [20.0, 20.0, 20.0], Config.DEVICE, target_name="bridge")
    top.set_residue_types_from_sequence_string("DK")

    assert isinstance(top.protein_topology, ProteinTopology)
    assert top.topology_fidelity() == "sequence_mapped"
    assert top.protein_topology.fidelity == "sequence_mapped"
    assert top.residue_types.shape == (2,)
    assert len(top.hbond_roles()) == 2


def test_allowlisted_runner_path_routes_through_product_engine_adapter() -> None:
    import tools.run_ligand_backmapping_scoring as legacy_runner
    import tools.run_ligand_htvs_pipeline as htvs_runner
    import tools.run_ligand_topk_delivery as topk_runner
    from betelgeuze_engine.product.runners import backmapping_scoring, htvs_pipeline, topk_delivery

    assert legacy_runner.main is backmapping_scoring.main
    assert legacy_runner._frame_mmpbsa_proxy is backmapping_scoring._frame_mmpbsa_proxy
    assert importlib.import_module("tools.run_ligand_backmapping_scoring").main is backmapping_scoring.main
    assert htvs_runner.main is htvs_pipeline.main
    assert htvs_runner.build_parser is htvs_pipeline.build_parser
    assert importlib.import_module("tools.run_ligand_htvs_pipeline").main is htvs_pipeline.main
    assert topk_runner.main is topk_delivery.main
    assert topk_runner.build_delivery is topk_delivery.build_delivery
    assert importlib.import_module("tools.run_ligand_topk_delivery").main is topk_delivery.main


def test_core_forcefield_exposes_product_engine_bridge_with_claim_metadata() -> None:
    from betelgeuze_engine.contracts import EnergyForces
    from betelgeuze_engine.physics import ProductForceField
    from core.definitions import Config
    from core.forcefield import ForceField, default_product_forcefield
    from core.topology import TopologyFactory

    top = TopologyFactory(2, "protein", [20.0, 20.0, 20.0], Config.DEVICE, target_name="bridge")
    top.set_residue_types_from_sequence_string("DK")
    legacy_forcefield = ForceField(top, force_backend="pytorch")
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float32, device=Config.DEVICE)

    bridge_state = legacy_forcefield.engine_state(
        coords,
        metadata={
            "hbond_roles": ["donor", "acceptor"],
            "hydrophobic_mask": torch.tensor([True, True], device=Config.DEVICE),
        },
    )
    result = legacy_forcefield.product_energy_forces(
        coords,
        term_names=["legacy_lj"],
        metadata={
            "hbond_roles": ["donor", "acceptor"],
            "hydrophobic_mask": torch.tensor([True, True], device=Config.DEVICE),
        },
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert isinstance(default_product_forcefield(term_names=["legacy_lj"]), ProductForceField)
    assert bridge_state.metadata["topology_fidelity"] == "sequence_mapped"
    assert bridge_state.atom_types.shape == (2,)
    assert isinstance(result, EnergyForces)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert result.claim_metadata["force_term_plugins"] == ["legacy_lj"]
    assert result.diagnostics["term_diagnostics"]["legacy_lj"]["claim_metadata"]["force_term_name"] == "legacy_lj"
