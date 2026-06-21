from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from betelgeuze_engine.contracts import (
    EnergyForces,
    EngineState,
    PRODUCT_CORRECTION_POLICY_CAP_KEYS,
    TermResult,
    validate_energy_forces_contract,
    validate_term_result_contract,
)
from betelgeuze_engine.benchmark import (
    build_capped_neighbor_pairs,
    run_runtime_scaling_benchmark,
    write_runtime_scaling_svg,
)
from betelgeuze_engine.benchmark.runtime_scaling import _LinearProbeTerm
from betelgeuze_engine.interactions.hbond_evidence import evaluate_hbond_evidence
from betelgeuze_engine.backmapping.onsps import (
    ONSPS_BACKMAP_SCHEMA_VERSION,
    backmap_4bead_onsps,
    evaluate_onsps_backmap_evidence,
)
from betelgeuze_engine.physics.terms import (
    DirectionalHBondTerm,
    HydrophobicContactTerm,
    LegacyLJTerm,
    PocketWallTerm,
    ScreenedElectrostaticsTerm,
    TopologyPenaltyTerm,
    TorsionPriorTerm,
    WaterDisplacementProxyTerm,
)
from betelgeuze_engine.physics import ProductForceField, default_force_term_registry, guarded_force_term_registry
from betelgeuze_engine.physics.neighbor import (
    CellListNeighborProvider,
    NeighborPairs,
    NeighborProviderConfig,
    full_neighbor_pairs,
)
from betelgeuze_engine.topology import (
    ComplexTopology,
    ProteinTopology,
    TopologyFactoryFacade,
    ligand_topology_from_smiles,
    protein_topology_from_sequence,
    topology_claim_metadata,
)
from betelgeuze_engine.validation import (
    build_confidence_calibration_report,
    energy_drift_smoke_pct,
    finite_difference_force_error,
    neighbor_list_parity_error,
    rotation_equivariance_error,
    translation_invariance_error,
)


def test_engine_terms_return_energy_forces_and_diagnostics() -> None:
    coords = torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [5.0, 0.0, 0.0]]])
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    for term in (LegacyLJTerm(sigma=1.0), DirectionalHBondTerm(), HydrophobicContactTerm()):
        result = term.energy_forces(state)
        assert isinstance(result, TermResult)
        assert result.energy.shape == (1,)
        assert result.forces.shape == coords.shape
        assert result.diagnostics["term"] == term.name
        assert result.diagnostics["status"] == "pass"
        assert result.claim_metadata["claim_safe"] is True
        assert result.claim_metadata["blocked_reason"] == ""
        assert result.claim_metadata["force_term_name"] == term.name
        assert result.claim_metadata["force_term_status"] == "pass"
        assert result.claim_metadata["topology_fidelity"] == "sequence_mapped"
        assert result.claim_metadata["ligand_topology_valid"] is True
        assert result.claim_metadata["hbond_evidence_status"] == "pass"
        if term.name == "directional_hbond":
            assert result.claim_metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
            assert result.claim_metadata["hbond_evidence_schema_ready"] is True
        assert result.claim_metadata["force_residual_applied"] is False
        assert torch.isfinite(result.energy).all()
        assert torch.isfinite(result.forces).all()


def test_runtime_scaling_benchmark_tracks_capped_neighbor_path() -> None:
    result = run_runtime_scaling_benchmark(atom_counts=(8, 16, 32), repeats=1)
    payload = result.to_dict()

    assert payload["ready"] is True
    assert payload["status"] == "runtime_neighbor_cap_scaling_ready"
    assert payload["forcefield_contract_ready"] is True
    assert payload["neighbor_cap_scaling_ready"] is True
    assert 0.85 <= payload["neighbor_pair_count_slope"] <= 1.15
    assert payload["neighbor_pair_count_r2"] > 0.99
    assert len(payload["rows"]) == 3
    assert all(row["neighbor_pairs_provided"] is True for row in payload["rows"])
    assert all(row["neighbor_source"] == "provided" for row in payload["rows"])
    assert all(row["row_ready"] is True for row in payload["rows"])
    assert all(row["duration_per_repeat_sec"] > 0.0 for row in payload["rows"])


def test_runtime_scaling_benchmark_handles_single_neighbor_cap() -> None:
    result = run_runtime_scaling_benchmark(
        atom_counts=(8, 16, 32),
        max_neighbor_count=1,
        repeats=1,
    )
    payload = result.to_dict()

    assert payload["ready"] is False
    assert payload["status"] == "blocked_runtime_neighbor_cap_scaling"
    assert payload["max_neighbor_count"] == 1
    assert payload["forcefield_contract_ready"] is False
    assert payload["neighbor_cap_scaling_ready"] is False
    assert all(row["neighbor_pairs_provided"] is True for row in payload["rows"])
    assert all(row["neighbor_source"] == "provided" for row in payload["rows"])
    assert all(row["neighbor_pair_count"] > row["max_neighbor_count"] * row["atom_count"] for row in payload["rows"])
    assert all(row["claim_safe"] is True for row in payload["rows"])
    assert all(row["row_ready"] is False for row in payload["rows"])


def test_runtime_scaling_svg_plot_writes_claim_bounded_artifact(tmp_path: Path) -> None:
    result = run_runtime_scaling_benchmark(atom_counts=(8, 16, 32), repeats=1)
    out = tmp_path / "runtime_scaling.svg"

    metadata = write_runtime_scaling_svg(result, out)
    text = out.read_text(encoding="utf-8")

    assert metadata["plot_ready"] is True
    assert metadata["plot_format"] == "svg"
    assert metadata["plot_role"] == "runtime_neighbor_cap_scaling_plot"
    assert "<svg" in text
    assert "Capped neighbor pairs" in text
    assert "Duration per repeat" in text
    assert "Pair-count scaling" in text
    assert "advisory" in text


def test_runtime_scaling_benchmark_fails_closed_for_invalid_neighbor_inputs() -> None:
    with pytest.raises(ValueError, match="coords must have shape"):
        build_capped_neighbor_pairs(torch.zeros(4, 3))
    with pytest.raises(ValueError, match="max_neighbor_count must be positive"):
        build_capped_neighbor_pairs(torch.zeros(1, 4, 3), max_neighbor_count=0)

    state = EngineState(
        coords=torch.zeros(1, 4, 3),
        atom_types=torch.arange(4),
        metadata={"claim_safe": True, "blocked_reason": ""},
    )
    with pytest.raises(ValueError, match="requires provided neighbor pairs"):
        _LinearProbeTerm().energy_forces(state)

    blocked = run_runtime_scaling_benchmark(atom_counts=(4, 5, 6), max_neighbor_count=2, repeats=1)
    assert blocked.ready is False
    assert blocked.status == "blocked_runtime_neighbor_cap_scaling"
    assert blocked.forcefield_contract_ready is True
    assert blocked.neighbor_cap_scaling_ready is False
    assert blocked.neighbor_pair_count_slope > 1.15


def test_confidence_calibration_report_bins_pose_confidence_fail_closed() -> None:
    rows = [
        {"pose_id": "active", "benchmark_role": "hbond_recovery_pose", "hbond_confidence": 1.0, "expected_claim_safe": True},
        {"pose_id": "far", "benchmark_role": "far_decoy_pose", "hbond_confidence": 0.0, "expected_claim_safe": False},
        {"pose_id": "yellow", "benchmark_role": "delta_backmap_yellow_band_pose", "hbond_confidence": 0.4, "expected_claim_safe": False},
        {"pose_id": "invalid", "benchmark_role": "invalid_ligand_pose", "hbond_confidence": 0.0, "expected_claim_safe": False},
    ]

    report = build_confidence_calibration_report(rows)

    assert report["schema_version"] == "confidence_calibration_v1"
    assert report["ready"] is True
    assert report["status"] == "confidence_calibration_report_ready"
    assert report["row_count"] == 4
    assert report["positive_count"] == 1
    assert report["negative_count"] == 3
    assert report["expected_calibration_error"] <= report["max_expected_calibration_error"]
    assert report["brier_score"] <= report["max_brier_score"]
    assert len(report["bins"]) == report["bin_count"]
    assert any(row["row_count"] > 0 and row["calibration_gap"] >= 0.0 for row in report["bins"])

    blocked = build_confidence_calibration_report(rows[:1])
    assert blocked["ready"] is False
    assert blocked["status"] == "blocked_confidence_calibration_report"
    assert "confidence_calibration_negative_rows_missing" in blocked["blocked_reasons"]

    bad_brier = build_confidence_calibration_report(
        [
            {"pose_id": "active", "hbond_confidence": 0.0, "expected_claim_safe": True},
            {"pose_id": "decoy_a", "hbond_confidence": 1.0, "expected_claim_safe": False},
            {"pose_id": "decoy_b", "hbond_confidence": 1.0, "expected_claim_safe": False},
            {"pose_id": "decoy_c", "hbond_confidence": 1.0, "expected_claim_safe": False},
        ],
        max_expected_calibration_error=1.0,
        max_brier_score=0.2,
    )
    assert bad_brier["ready"] is False
    assert "confidence_calibration_brier_exceeded" in bad_brier["blocked_reasons"]


def test_force_terms_fail_closed_with_scoped_claim_metadata_for_missing_inputs() -> None:
    state = EngineState(
        coords=torch.zeros(1, 2, 3),
        atom_types=torch.tensor([0, 1]),
        metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "water_displacement_model_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    hbond = DirectionalHBondTerm().energy_forces(state)
    hydrophobic = HydrophobicContactTerm().energy_forces(state)

    assert hbond.claim_metadata["claim_safe"] is False
    assert hbond.claim_metadata["force_term_name"] == "directional_hbond"
    assert hbond.claim_metadata["force_term_status"] == "roles_missing"
    assert hbond.claim_metadata["blocked_reason"] == "hbond_roles_missing"
    assert hbond.claim_metadata["hbond_evidence_status"] == "roles_missing"
    assert hydrophobic.claim_metadata["claim_safe"] is False
    assert hydrophobic.claim_metadata["force_term_name"] == "hydrophobic_contact"
    assert hydrophobic.claim_metadata["force_term_status"] == "mask_missing"
    assert hydrophobic.claim_metadata["blocked_reason"] == "hydrophobic_mask_missing"


def test_legacy_lj_force_matches_finite_difference() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    base = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float64)
    state = EngineState(coords=base, atom_types=torch.tensor([0, 0]))
    observed = term.energy_forces(state).forces[0, 0, 0].item()
    eps = 1e-4
    plus = base.clone()
    minus = base.clone()
    plus[0, 0, 0] += eps
    minus[0, 0, 0] -= eps
    e_plus = term.energy_forces(EngineState(coords=plus, atom_types=torch.tensor([0, 0]))).energy.item()
    e_minus = term.energy_forces(EngineState(coords=minus, atom_types=torch.tensor([0, 0]))).energy.item()
    finite_difference_force = -((e_plus - e_minus) / (2.0 * eps))

    assert observed == pytest.approx(finite_difference_force, rel=1e-3, abs=1e-6)


def test_legacy_lj_translation_invariance() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]])
    shift = torch.tensor([[[10.0, -3.0, 2.0]]])
    atom_types = torch.tensor([0, 0, 0])

    a = term.energy_forces(EngineState(coords=coords, atom_types=atom_types))
    b = term.energy_forces(EngineState(coords=coords + shift, atom_types=atom_types))

    assert a.energy == pytest.approx(b.energy)
    assert torch.allclose(a.forces, b.forces, atol=1e-6)


def test_legacy_lj_rotation_equivariance() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    state = EngineState(
        coords=torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]], dtype=torch.float64),
        atom_types=torch.tensor([0, 0, 0]),
    )
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )

    assert rotation_equivariance_error(term, state, rotation) < 1e-9


def test_default_force_terms_pass_physics_validation_surface() -> None:
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [8.2, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )
    shift = torch.tensor([[[4.0, -2.0, 1.0]]], dtype=torch.float64)

    for term in default_force_term_registry().create():
        result = term.energy_forces(state)
        assert result.claim_metadata["claim_safe"] is True
        assert result.claim_metadata["blocked_reason"] == ""
        assert result.diagnostics["status"] == "pass"
        assert finite_difference_force_error(term, state, atom_index=1, coord_index=0) < 1e-4
        assert translation_invariance_error(term, state, shift) < 1e-9
        assert rotation_equivariance_error(term, state, rotation) < 1e-9
        assert energy_drift_smoke_pct(term, state, step_size=1e-4) < 5e-2


def test_neighbor_list_parity_checks_mask_distance_and_index() -> None:
    coords = torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [9.0, 0.0, 0.0]]])
    pairs = full_neighbor_pairs(coords, cutoff=5.0)

    assert neighbor_list_parity_error(coords, cutoff=5.0, candidate_pairs=pairs) == 0.0

    bad_dist = NeighborPairs(
        idx=pairs.idx,
        dist=pairs.dist + pairs.mask.to(dtype=pairs.dist.dtype) * 0.25,
        mask=pairs.mask,
    )
    assert neighbor_list_parity_error(coords, cutoff=5.0, candidate_pairs=bad_dist) > 0.0

    bad_idx_tensor = pairs.idx.clone()
    bad_idx_tensor[0, 0, 1] = 2
    bad_idx = NeighborPairs(idx=bad_idx_tensor, dist=pairs.dist, mask=pairs.mask)
    assert neighbor_list_parity_error(coords, cutoff=5.0, candidate_pairs=bad_idx) > 0.0

    nonfinite_dist_tensor = pairs.dist.clone()
    nonfinite_dist_tensor[0, 0, 1] = torch.nan
    nonfinite_dist = NeighborPairs(idx=pairs.idx, dist=nonfinite_dist_tensor, mask=pairs.mask)
    assert neighbor_list_parity_error(coords, cutoff=5.0, candidate_pairs=nonfinite_dist) == 1.0

    wrong_shape = NeighborPairs(
        idx=pairs.idx[:, :2, :2],
        dist=pairs.dist[:, :2, :2],
        mask=pairs.mask[:, :2, :2],
    )
    assert neighbor_list_parity_error(coords, cutoff=5.0, candidate_pairs=wrong_shape) == 1.0

    no_pair_pairs = full_neighbor_pairs(torch.zeros(1, 1, 3), cutoff=5.0)
    assert neighbor_list_parity_error(
        torch.zeros(1, 1, 3),
        cutoff=5.0,
        candidate_pairs=no_pair_pairs,
    ) == 0.0


def _pair_set_from_neighbors(pairs: NeighborPairs) -> set[tuple[int, int]]:
    found: set[tuple[int, int]] = set()
    mask = pairs.mask.detach().cpu()
    idx = pairs.idx.detach().cpu()
    for i in range(mask.shape[1]):
        for slot in range(mask.shape[2]):
            if bool(mask[0, i, slot].item()):
                found.add((i, int(idx[0, i, slot].item())))
    return found


def test_cell_list_neighbor_provider_matches_small_dense_reference() -> None:
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [4.9, 0.0, 0.0], [8.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    provider = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=3.1, max_neighbor_count=4, max_atoms_per_cell=8)
    )

    sparse = provider.build(coords)
    dense = full_neighbor_pairs(coords, cutoff=3.1)

    assert sparse.source == "provided_cell_list"
    assert sparse.diagnostics["status"] == "neighbor_provider_ready"
    assert sparse.diagnostics["overflow"] is False
    assert sparse.diagnostics["nxn_allocation_observed"] is False
    assert _pair_set_from_neighbors(sparse) == _pair_set_from_neighbors(dense)
    for i, j in _pair_set_from_neighbors(sparse):
        slot = (sparse.idx[0, i] == j).nonzero(as_tuple=False)[0, 0]
        assert sparse.dist[0, i, slot].item() == pytest.approx(dense.dist[0, i, j].item())


def test_cell_list_neighbor_provider_uses_periodic_minimum_image() -> None:
    coords = torch.tensor([[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0], [5.0, 0.0, 0.0]]], dtype=torch.float64)
    provider = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=1.0, max_neighbor_count=2, max_atoms_per_cell=4, box_size=10.0)
    )

    sparse = provider.build(coords)

    assert (0, 1) in _pair_set_from_neighbors(sparse)
    assert (1, 0) in _pair_set_from_neighbors(sparse)
    slot = (sparse.idx[0, 0] == 1).nonzero(as_tuple=False)[0, 0]
    assert sparse.dist[0, 0, slot].item() == pytest.approx(0.4)
    assert sparse.diagnostics["pbc_enabled"] is True


def test_product_forcefield_rejects_overflowing_product_neighbors() -> None:
    coords = torch.tensor([[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.9, 0.0, 0.0]]], dtype=torch.float64)
    provider = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=2.0, max_neighbor_count=1, max_atoms_per_cell=8)
    )
    pairs = provider.build(coords)
    forcefield = ProductForceField(terms=[LegacyLJTerm(sigma=1.0, epsilon=0.1)])

    assert pairs.diagnostics["overflow"] is True
    with pytest.raises(ValueError, match="overflow"):
        forcefield.energy_forces(
            EngineState(coords=coords, atom_types=torch.tensor([0, 0, 0])),
            pairs=pairs,
            product_neighbor_required=True,
        )


def test_legacy_lj_compact_neighbor_path_matches_dense_reference() -> None:
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [2.2, 0.0, 0.0], [0.0, 2.5, 0.0], [6.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    state = EngineState(coords=coords, atom_types=torch.tensor([0, 0, 0, 0]))
    term = LegacyLJTerm(sigma=1.0, epsilon=0.2, cutoff=3.0)
    dense = full_neighbor_pairs(coords, cutoff=3.0)
    sparse = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=3.0, max_neighbor_count=4, max_atoms_per_cell=8)
    ).build(coords)

    dense_result = term.energy_forces(state, dense)
    sparse_result = term.energy_forces(state, sparse)

    assert sparse.diagnostics["nxn_allocation_observed"] is False
    assert torch.allclose(sparse_result.energy, dense_result.energy, atol=1e-10, rtol=1e-10)
    assert torch.allclose(sparse_result.forces, dense_result.forces, atol=1e-10, rtol=1e-10)


def test_product_forcefield_plugin_registry_aggregates_terms_and_claim_metadata() -> None:
    registry = default_force_term_registry()
    assert registry.names() == ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
    forcefield = ProductForceField.from_registry(
        registry,
        names=["legacy_lj", "directional_hbond", "hydrophobic_contact"],
    )
    coords = torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [5.0, 0.0, 0.0]]])
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
        },
    )

    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert set(result.terms) == {"legacy_lj", "directional_hbond", "hydrophobic_contact"}
    assert result.diagnostics["term_count"] == 3
    assert result.diagnostics["neighbor_pair_count"] == 6
    assert result.diagnostics["neighbor_pairs_provided"] is False
    assert result.diagnostics["neighbor_source"] == "full_neighbor_pairs"
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["topology_fidelity"] == "sequence_mapped"
    assert result.claim_metadata["ligand_topology_valid"] is True
    assert result.claim_metadata["hbond_evidence_status"] == "pass"
    assert result.claim_metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert result.claim_metadata["hbond_evidence_schema_ready"] is True
    assert result.claim_metadata["force_term_plugin_count"] == 3
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert result.claim_metadata["force_term_claim_metadata_schema_version"] == "force_term_claim_metadata_v1"
    assert result.claim_metadata["force_term_claim_safe_count"] == 3
    assert result.claim_metadata["force_term_blocked_count"] == 0
    assert {
        row["force_term_name"]
        for row in result.claim_metadata["force_term_claim_rows"]
    } == {"legacy_lj", "directional_hbond", "hydrophobic_contact"}
    assert all(row["claim_safe"] is True for row in result.claim_metadata["force_term_claim_rows"])
    assert all(row["blocked_reason"] == "" for row in result.claim_metadata["force_term_claim_rows"])
    assert any(
        row["force_term_name"] == "directional_hbond"
        and row["hbond_evidence_schema_version"] == "hbond_evidence_v1"
        and row["hbond_evidence_schema_ready"] is True
        for row in result.claim_metadata["force_term_claim_rows"]
    )
    for term_name, diagnostics in result.diagnostics["term_diagnostics"].items():
        term_metadata = diagnostics["claim_metadata"]
        assert term_metadata["claim_safe"] is True
        assert term_metadata["blocked_reason"] == ""
        assert term_metadata["force_term_name"] == term_name
        assert term_metadata["force_term_status"] == "pass"
        assert term_metadata["topology_fidelity"] == "sequence_mapped"
        assert term_metadata["ligand_topology_valid"] is True


def test_energy_forces_contract_validates_aggregate_metadata_and_diagnostics() -> None:
    coords = torch.zeros(1, 2, 3)
    result = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics={
            "forcefield": "product_forcefield",
            "term_count": 1,
            "neighbor_pair_count": 2,
            "neighbor_pairs_provided": False,
            "neighbor_source": "full_neighbor_pairs",
            "term_diagnostics": {"legacy_lj": {"status": "pass"}},
        },
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "force_residual_applied": False,
            "claim_safe": True,
            "blocked_reason": "",
            "force_term_claim_metadata_ready": True,
            "force_term_claim_rows": [
                {
                    "force_term_name": "legacy_lj",
                    "force_term_status": "pass",
                    "claim_safe": True,
                    "blocked_reason": "",
                }
            ],
        },
    )

    validate_energy_forces_contract(result=result, coords=coords)

    bad_terms = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": float("nan")},
        diagnostics=dict(result.diagnostics),
        claim_metadata=dict(result.claim_metadata),
    )
    with pytest.raises(ValueError, match="nonfinite term value"):
        validate_energy_forces_contract(result=bad_terms, coords=coords)

    missing_diagnostics = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics={**result.diagnostics, "term_diagnostics": {}},
        claim_metadata=dict(result.claim_metadata),
    )
    with pytest.raises(ValueError, match="term diagnostics mismatch"):
        validate_energy_forces_contract(result=missing_diagnostics, coords=coords)

    missing_claim_rows = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={**result.claim_metadata, "force_term_claim_rows": []},
    )
    with pytest.raises(ValueError, match="force term claim row count mismatch"):
        validate_energy_forces_contract(result=missing_claim_rows, coords=coords)

    wrong_energy_shape = EnergyForces(
        energy=torch.zeros(1, 1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata=dict(result.claim_metadata),
    )
    with pytest.raises(ValueError, match="energy with wrong shape"):
        validate_energy_forces_contract(result=wrong_energy_shape, coords=coords)

    bad_neighbor_source = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics={**result.diagnostics, "neighbor_source": "unknown"},
        claim_metadata=dict(result.claim_metadata),
    )
    with pytest.raises(ValueError, match="invalid diagnostic neighbor_source"):
        validate_energy_forces_contract(result=bad_neighbor_source, coords=coords)

    unsafe_blocked = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={**result.claim_metadata, "blocked_reason": "should_not_be_set"},
    )
    with pytest.raises(ValueError, match="claim_safe with blocked_reason"):
        validate_energy_forces_contract(result=unsafe_blocked, coords=coords)

    metadata_not_ready = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={**result.claim_metadata, "force_term_claim_metadata_ready": False},
    )
    with pytest.raises(ValueError, match="force term claim metadata not ready"):
        validate_energy_forces_contract(result=metadata_not_ready, coords=coords)

    row_name_mismatch = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={
            **result.claim_metadata,
            "force_term_claim_rows": [
                {
                    "force_term_name": "other_term",
                    "force_term_status": "pass",
                    "claim_safe": True,
                    "blocked_reason": "",
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="force term claim row names mismatch"):
        validate_energy_forces_contract(result=row_name_mismatch, coords=coords)

    non_dict_row = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={**result.claim_metadata, "force_term_claim_rows": ["legacy_lj"]},
    )
    with pytest.raises(ValueError, match="non-dict force term claim row"):
        validate_energy_forces_contract(result=non_dict_row, coords=coords)

    claim_safe_row_with_blocker = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={
            **result.claim_metadata,
            "force_term_claim_rows": [
                {
                    "force_term_name": "legacy_lj",
                    "force_term_status": "pass",
                    "claim_safe": True,
                    "blocked_reason": "should_not_be_set",
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="claim-safe force term row with blocker"):
        validate_energy_forces_contract(result=claim_safe_row_with_blocker, coords=coords)

    empty_row_name = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={
            **result.claim_metadata,
            "force_term_claim_rows": [
                {
                    "force_term_name": "",
                    "force_term_status": "pass",
                    "claim_safe": True,
                    "blocked_reason": "",
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="claim row without name"):
        validate_energy_forces_contract(result=empty_row_name, coords=coords)

    missing_row_claim_safe = EnergyForces(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        terms={"legacy_lj": 0.0},
        diagnostics=dict(result.diagnostics),
        claim_metadata={
            **result.claim_metadata,
            "force_term_claim_rows": [
                {
                    "force_term_name": "legacy_lj",
                    "force_term_status": "pass",
                    "blocked_reason": "",
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="non-boolean force term claim safety"):
        validate_energy_forces_contract(result=missing_row_claim_safe, coords=coords)


def test_guarded_force_term_registry_exposes_screened_electrostatics_opt_in() -> None:
    default_registry = default_force_term_registry()
    guarded_registry = guarded_force_term_registry()

    assert default_registry.names() == ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
    assert guarded_registry.names() == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
        "pocket_wall",
        "screened_electrostatics",
        "topology_penalty",
        "torsion_prior",
        "water_displacement_proxy",
    ]
    assert isinstance(guarded_registry.create(["pocket_wall"])[0], PocketWallTerm)
    assert isinstance(guarded_registry.create(["screened_electrostatics"])[0], ScreenedElectrostaticsTerm)
    assert isinstance(guarded_registry.create(["topology_penalty"])[0], TopologyPenaltyTerm)
    assert isinstance(guarded_registry.create(["torsion_prior"])[0], TorsionPriorTerm)
    assert isinstance(guarded_registry.create(["water_displacement_proxy"])[0], WaterDisplacementProxyTerm)


def test_pocket_wall_term_is_guarded_bounded_and_claim_scoped() -> None:
    term = PocketWallTerm(k_wall=0.2, max_abs_energy=10.0, max_force_norm=10.0)
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [4.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "pocket_atom_indices": [0],
            "ligand_atom_indices": [1, 2],
            "pocket_radius": 1.0,
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    result = term.energy_forces(state)

    validate_term_result_contract(name="pocket_wall", result=result, coords=coords)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert result.diagnostics["term"] == "pocket_wall"
    assert result.diagnostics["status"] == "pass"
    assert result.diagnostics["pocket_escape"] is True
    assert result.diagnostics["pocket_center_source"] == "pocket_atom_indices"
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""
    assert result.claim_metadata["force_term_name"] == "pocket_wall"
    assert result.claim_metadata["force_term_status"] == "pass"
    assert result.claim_metadata["force_term_policy_caps_ready"] is True
    assert set(PRODUCT_CORRECTION_POLICY_CAP_KEYS).issubset(
        result.claim_metadata["force_term_policy_caps"]
    )
    assert result.claim_metadata["force_term_policy_caps"]["max_abs_delta_score"] == 10.0
    assert result.claim_metadata["force_term_policy_caps"]["max_displacement"] == 0.0
    assert result.claim_metadata["force_term_policy_caps"]["abstain_threshold"] == 1.0
    assert result.claim_metadata["force_term_observed_caps_ready"] is True
    assert result.claim_metadata["force_term_bounded_correction_ready"] is True
    assert result.claim_metadata["force_term_abs_energy_within_cap"] is True
    assert result.claim_metadata["force_term_force_norm_within_cap"] is True
    assert result.claim_metadata["force_term_active_pair_count_within_cap"] is True
    assert result.claim_metadata["force_term_pocket_anchor_count"] == 1
    assert result.claim_metadata["force_term_ligand_atom_count"] == 2
    assert finite_difference_force_error(term, state, atom_index=1, coord_index=0) < 1e-5
    assert translation_invariance_error(
        term,
        state,
        torch.tensor([[[11.0, -3.0, 2.0]]], dtype=torch.float64),
    ) < 1e-9
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    assert rotation_equivariance_error(term, state, rotation) < 1e-9

    missing = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    assert missing.claim_metadata["claim_safe"] is False
    assert missing.claim_metadata["force_term_status"] == "ligand_indices_missing"
    assert missing.claim_metadata["blocked_reason"] == "pocket_wall_ligand_indices_missing"
    assert torch.allclose(missing.energy, torch.zeros_like(missing.energy))
    assert torch.allclose(missing.forces, torch.zeros_like(missing.forces))

    missing_radius = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "ligand_atom_indices": [1, 2],
                "pocket_atom_indices": [0],
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert missing_radius.claim_metadata["claim_safe"] is False
    assert missing_radius.claim_metadata["force_term_status"] == "pocket_radius_missing"
    assert missing_radius.claim_metadata["blocked_reason"] == "pocket_wall_radius_missing"

    missing_center = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "ligand_atom_indices": [1, 2],
                "pocket_radius": 1.0,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert missing_center.claim_metadata["claim_safe"] is False
    assert missing_center.claim_metadata["force_term_status"] == "pocket_center_missing"
    assert missing_center.claim_metadata["blocked_reason"] == "pocket_wall_center_missing"

    invalid_center = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "ligand_atom_indices": [1, 2],
                "pocket_center": [float("nan"), 0.0, 0.0],
                "pocket_radius": 1.0,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert invalid_center.claim_metadata["claim_safe"] is False
    assert invalid_center.claim_metadata["force_term_status"] == "pocket_center_invalid"
    assert invalid_center.claim_metadata["blocked_reason"] == "pocket_wall_center_invalid"

    capped = PocketWallTerm(k_wall=0.2, max_force_norm=1e-12)
    capped_result = capped.energy_forces(state)
    assert capped_result.claim_metadata["claim_safe"] is False
    assert capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert capped_result.claim_metadata["blocked_reason"] == "pocket_wall_policy_cap_exceeded"
    assert capped_result.claim_metadata["force_term_policy_caps_ready"] is True
    assert capped_result.claim_metadata["force_term_observed_caps_ready"] is False
    assert capped_result.claim_metadata["force_term_bounded_correction_ready"] is False
    assert capped_result.claim_metadata["force_term_force_norm_within_cap"] is False
    assert torch.count_nonzero(capped_result.forces).item() == 0
    assert torch.count_nonzero(capped_result.energy).item() == 0


def test_screened_electrostatics_term_is_guarded_and_claim_scoped() -> None:
    term = ScreenedElectrostaticsTerm(scale=2.0, debye_kappa=0.15)
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 5.0, 0.0]]], dtype=torch.float64)
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
            "charge_source": "unit_test_validated_proxy",
            "charge_model_valid": True,
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    result = term.energy_forces(state)

    assert isinstance(result, TermResult)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert torch.isfinite(result.energy).all()
    assert torch.isfinite(result.forces).all()
    assert result.diagnostics["term"] == "screened_electrostatics"
    assert result.diagnostics["status"] == "pass"
    assert result.diagnostics["active_pair_count"] == 3
    assert result.diagnostics["force_term_policy_caps_ready"] is True
    assert result.diagnostics["force_term_observed_caps_ready"] is True
    assert result.diagnostics["force_term_bounded_correction_ready"] is True
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""
    assert result.claim_metadata["force_term_name"] == "screened_electrostatics"
    assert result.claim_metadata["force_term_status"] == "pass"
    assert result.claim_metadata["force_term_charge_model_valid"] is True
    assert result.claim_metadata["force_term_policy_caps_ready"] is True
    assert result.claim_metadata["force_term_observed_caps_ready"] is True
    assert result.claim_metadata["force_term_bounded_correction_ready"] is True
    assert result.claim_metadata["force_term_abs_energy_within_cap"] is True
    assert result.claim_metadata["force_term_force_norm_within_cap"] is True
    assert result.claim_metadata["force_term_active_pair_count_within_cap"] is True
    assert finite_difference_force_error(term, state, atom_index=0, coord_index=0) < 1e-5

    missing = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    assert missing.claim_metadata["claim_safe"] is False
    assert missing.claim_metadata["force_term_status"] == "charges_missing"
    assert missing.claim_metadata["blocked_reason"] == "screened_electrostatics_charges_missing"
    assert torch.allclose(missing.energy, torch.zeros_like(missing.energy))
    assert torch.allclose(missing.forces, torch.zeros_like(missing.forces))

    unvalidated = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert unvalidated.claim_metadata["claim_safe"] is False
    assert unvalidated.claim_metadata["force_term_status"] == "charge_model_unvalidated"
    assert unvalidated.claim_metadata["blocked_reason"] == "screened_electrostatics_charge_model_unvalidated"

    capped = ScreenedElectrostaticsTerm(scale=2.0, debye_kappa=0.15, max_force_norm=1e-12)
    capped_result = capped.energy_forces(state)
    assert capped_result.claim_metadata["claim_safe"] is False
    assert capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert capped_result.claim_metadata["blocked_reason"] == "screened_electrostatics_policy_cap_exceeded"
    assert capped_result.claim_metadata["force_term_charge_model_valid"] is True
    assert capped_result.claim_metadata["force_term_policy_caps_ready"] is True
    assert capped_result.claim_metadata["force_term_observed_caps_ready"] is False
    assert capped_result.claim_metadata["force_term_bounded_correction_ready"] is False
    assert capped_result.claim_metadata["force_term_force_norm_within_cap"] is False
    assert torch.count_nonzero(capped_result.forces).item() == 0
    assert torch.count_nonzero(capped_result.energy).item() == 0


def test_topology_penalty_term_is_guarded_bounded_and_claim_scoped() -> None:
    term = TopologyPenaltyTerm(k_topology=0.25)
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [2.4, 0.1, 0.0]]],
        dtype=torch.float64,
    )
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "topology_edge_indices": [[0, 1], [1, 2]],
            "topology_edge_target_distances": [1.0, 1.0],
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "ligand_topology_claim_safe": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    result = term.energy_forces(state)

    assert isinstance(result, TermResult)
    validate_term_result_contract(name="topology_penalty", result=result, coords=coords)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert torch.isfinite(result.energy).all()
    assert torch.isfinite(result.forces).all()
    assert result.diagnostics["term"] == "topology_penalty"
    assert result.diagnostics["status"] == "pass"
    assert result.diagnostics["active_pair_count"] == 2
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""
    assert result.claim_metadata["force_term_name"] == "topology_penalty"
    assert result.claim_metadata["force_term_status"] == "pass"
    assert result.claim_metadata["force_term_topology_edge_count"] == 2
    assert result.claim_metadata["force_term_policy_caps_ready"] is True
    assert result.claim_metadata["force_term_observed_caps_ready"] is True
    assert result.claim_metadata["force_term_bounded_correction_ready"] is True
    assert result.claim_metadata["force_term_abs_energy_within_cap"] is True
    assert result.claim_metadata["force_term_force_norm_within_cap"] is True
    assert result.claim_metadata["force_term_active_pair_count_within_cap"] is True
    assert finite_difference_force_error(term, state, atom_index=1, coord_index=0) < 1e-5
    shift = torch.tensor([[[4.0, -2.0, 1.0]]], dtype=torch.float64)
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )
    assert translation_invariance_error(term, state, shift) < 1e-9
    assert rotation_equivariance_error(term, state, rotation) < 1e-9

    placeholder = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "topology_edge_indices": [[0, 1]],
                "topology_edge_target_distances": [1.0],
                "topology_fidelity": "placeholder_alanine",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert placeholder.claim_metadata["claim_safe"] is False
    assert placeholder.claim_metadata["force_term_status"] == "topology_not_sequence_mapped"
    assert placeholder.claim_metadata["blocked_reason"] == "topology_penalty_topology_not_sequence_mapped"
    assert torch.count_nonzero(placeholder.forces).item() == 0
    assert placeholder.forces.requires_grad is False

    invalid_ligand = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "topology_edge_indices": [[0, 1]],
                "topology_edge_target_distances": [1.0],
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": False,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert invalid_ligand.claim_metadata["claim_safe"] is False
    assert invalid_ligand.claim_metadata["force_term_status"] == "ligand_topology_invalid"
    assert invalid_ligand.claim_metadata["blocked_reason"] == "topology_penalty_ligand_topology_invalid"

    missing_edges = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert missing_edges.claim_metadata["claim_safe"] is False
    assert missing_edges.claim_metadata["force_term_status"] == "topology_edges_missing"
    assert missing_edges.claim_metadata["blocked_reason"] == "topology_penalty_edges_missing"

    invalid_targets = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "topology_edge_indices": [[0, 1]],
                "topology_edge_target_distances": [float("nan")],
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert invalid_targets.claim_metadata["claim_safe"] is False
    assert invalid_targets.claim_metadata["force_term_status"] == "topology_targets_invalid"
    assert invalid_targets.claim_metadata["blocked_reason"] == "topology_penalty_targets_invalid"

    capped = TopologyPenaltyTerm(k_topology=0.25, max_force_norm=1e-12)
    capped_result = capped.energy_forces(state)
    assert capped_result.claim_metadata["claim_safe"] is False
    assert capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert capped_result.claim_metadata["blocked_reason"] == "topology_penalty_policy_cap_exceeded"
    assert capped_result.claim_metadata["force_term_force_norm_within_cap"] is False
    assert torch.count_nonzero(capped_result.forces).item() == 0
    assert capped_result.forces.requires_grad is False

    pair_capped = TopologyPenaltyTerm(k_topology=0.25, max_active_pair_count=1)
    pair_capped_result = pair_capped.energy_forces(state)
    assert pair_capped_result.claim_metadata["claim_safe"] is False
    assert pair_capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert pair_capped_result.claim_metadata["blocked_reason"] == "topology_penalty_policy_cap_exceeded"
    assert pair_capped_result.claim_metadata["force_term_active_pair_count_within_cap"] is False
    assert torch.count_nonzero(pair_capped_result.forces).item() == 0
    assert pair_capped_result.forces.requires_grad is False


def test_torsion_prior_term_is_guarded_bounded_and_claim_scoped() -> None:
    term = TorsionPriorTerm(k_torsion=0.2)
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.1, 0.0], [2.1, 1.0, 0.2], [3.0, 1.2, 1.1]]],
        dtype=torch.float64,
    )
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2, 3]),
        metadata={
            "torsion_atom_quartets": [[0, 1, 2, 3]],
            "torsion_target_angles_rad": [0.0],
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    result = term.energy_forces(state)

    assert isinstance(result, TermResult)
    validate_term_result_contract(name="torsion_prior", result=result, coords=coords)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert torch.isfinite(result.energy).all()
    assert torch.isfinite(result.forces).all()
    assert result.diagnostics["term"] == "torsion_prior"
    assert result.diagnostics["status"] == "pass"
    assert result.diagnostics["active_pair_count"] == 1
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""
    assert result.claim_metadata["force_term_name"] == "torsion_prior"
    assert result.claim_metadata["force_term_status"] == "pass"
    assert result.claim_metadata["force_term_torsion_quartet_count"] == 1
    assert result.claim_metadata["force_term_policy_caps_ready"] is True
    assert result.claim_metadata["force_term_observed_caps_ready"] is True
    assert result.claim_metadata["force_term_bounded_correction_ready"] is True
    assert result.claim_metadata["force_term_abs_energy_within_cap"] is True
    assert result.claim_metadata["force_term_force_norm_within_cap"] is True
    assert result.claim_metadata["force_term_active_pair_count_within_cap"] is True
    assert finite_difference_force_error(term, state, atom_index=3, coord_index=2) < 1e-5
    shift = torch.tensor([[[4.0, -2.0, 1.0]]], dtype=torch.float64)
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )
    assert translation_invariance_error(term, state, shift) < 1e-9
    assert rotation_equivariance_error(term, state, rotation) < 1e-9

    missing = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3]),
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    assert missing.claim_metadata["claim_safe"] is False
    assert missing.claim_metadata["force_term_status"] == "torsion_quartets_missing"
    assert missing.claim_metadata["blocked_reason"] == "torsion_prior_quartets_missing"
    assert torch.count_nonzero(missing.forces).item() == 0
    assert torch.count_nonzero(missing.energy).item() == 0

    invalid_targets = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3]),
            metadata={
                "torsion_atom_quartets": [[0, 1, 2, 3]],
                "torsion_target_angles_rad": [float("nan")],
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert invalid_targets.claim_metadata["claim_safe"] is False
    assert invalid_targets.claim_metadata["force_term_status"] == "torsion_targets_invalid"
    assert invalid_targets.claim_metadata["blocked_reason"] == "torsion_prior_targets_invalid"

    capped = TorsionPriorTerm(k_torsion=0.2, max_force_norm=1e-12)
    capped_result = capped.energy_forces(state)
    assert capped_result.claim_metadata["claim_safe"] is False
    assert capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert capped_result.claim_metadata["blocked_reason"] == "torsion_prior_policy_cap_exceeded"
    assert capped_result.claim_metadata["force_term_policy_caps_ready"] is True
    assert capped_result.claim_metadata["force_term_observed_caps_ready"] is False
    assert capped_result.claim_metadata["force_term_bounded_correction_ready"] is False
    assert capped_result.claim_metadata["force_term_force_norm_within_cap"] is False
    assert torch.count_nonzero(capped_result.forces).item() == 0
    assert torch.count_nonzero(capped_result.energy).item() == 0
    assert capped_result.forces.requires_grad is False

    energy_capped = TorsionPriorTerm(k_torsion=0.2, max_abs_energy=1e-12)
    energy_capped_result = energy_capped.energy_forces(state)
    assert energy_capped_result.claim_metadata["claim_safe"] is False
    assert energy_capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert energy_capped_result.claim_metadata["blocked_reason"] == "torsion_prior_policy_cap_exceeded"
    assert energy_capped_result.claim_metadata["force_term_abs_energy_within_cap"] is False
    assert torch.count_nonzero(energy_capped_result.forces).item() == 0
    assert energy_capped_result.forces.requires_grad is False

    pair_capped = TorsionPriorTerm(k_torsion=0.2, max_active_pair_count=0)
    pair_capped_result = pair_capped.energy_forces(state)
    assert pair_capped_result.claim_metadata["claim_safe"] is False
    assert pair_capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert pair_capped_result.claim_metadata["blocked_reason"] == "torsion_prior_policy_cap_exceeded"
    assert pair_capped_result.claim_metadata["force_term_active_pair_count_within_cap"] is False
    assert torch.count_nonzero(pair_capped_result.forces).item() == 0
    assert pair_capped_result.forces.requires_grad is False


def test_water_displacement_proxy_term_is_guarded_bounded_and_claim_scoped() -> None:
    term = WaterDisplacementProxyTerm(k_water=0.05, sigma=1.0)
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.5, 0.0], [5.0, 0.0, 0.0], [7.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2, 3, 4]),
        metadata={
            "ligand_atom_indices": [0, 1],
            "water_displacement_site_indices": [2, 3, 4],
            "water_displacement_site_weights": [1.0, 1.0, 1.0],
            "water_displacement_model_valid": True,
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "ligand_topology_claim_safe": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    result = term.energy_forces(state)

    assert isinstance(result, TermResult)
    validate_term_result_contract(name="water_displacement_proxy", result=result, coords=coords)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert torch.isfinite(result.energy).all()
    assert torch.isfinite(result.forces).all()
    assert result.diagnostics["term"] == "water_displacement_proxy"
    assert result.diagnostics["status"] == "pass"
    assert result.diagnostics["active_pair_count"] == 6
    assert result.diagnostics["ligand_atom_count"] == 2
    assert result.diagnostics["water_site_count"] == 3
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""
    assert result.claim_metadata["force_term_name"] == "water_displacement_proxy"
    assert result.claim_metadata["force_term_status"] == "pass"
    assert result.claim_metadata["force_term_ligand_atom_count"] == 2
    assert result.claim_metadata["force_term_water_site_count"] == 3
    assert result.claim_metadata["force_term_policy_caps_ready"] is True
    assert result.claim_metadata["force_term_observed_caps_ready"] is True
    assert result.claim_metadata["force_term_bounded_correction_ready"] is True
    assert result.claim_metadata["force_term_abs_energy_within_cap"] is True
    assert result.claim_metadata["force_term_force_norm_within_cap"] is True
    assert result.claim_metadata["force_term_active_pair_count_within_cap"] is True
    assert finite_difference_force_error(term, state, atom_index=0, coord_index=0) < 1e-5
    shift = torch.tensor([[[4.0, -2.0, 1.0]]], dtype=torch.float64)
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )
    assert translation_invariance_error(term, state, shift) < 1e-9
    assert rotation_equivariance_error(term, state, rotation) < 1e-9

    missing = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3, 4]),
            metadata={
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "water_displacement_model_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert missing.claim_metadata["claim_safe"] is False
    assert missing.claim_metadata["force_term_status"] == "ligand_indices_missing"
    assert missing.claim_metadata["blocked_reason"] == "water_displacement_proxy_ligand_indices_missing"
    assert torch.count_nonzero(missing.forces).item() == 0
    assert torch.count_nonzero(missing.energy).item() == 0

    invalid_topology = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3, 4]),
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [2, 3, 4],
                "water_displacement_model_valid": True,
                "topology_fidelity": "placeholder_alanine",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert invalid_topology.claim_metadata["claim_safe"] is False
    assert invalid_topology.claim_metadata["force_term_status"] == "topology_not_sequence_mapped"
    assert invalid_topology.claim_metadata["blocked_reason"] == "water_displacement_proxy_topology_not_sequence_mapped"
    assert torch.count_nonzero(invalid_topology.forces).item() == 0

    unvalidated = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3, 4]),
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [2, 3, 4],
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert unvalidated.claim_metadata["claim_safe"] is False
    assert unvalidated.claim_metadata["force_term_status"] == "water_displacement_model_unvalidated"
    assert unvalidated.claim_metadata["blocked_reason"] == "water_displacement_proxy_model_unvalidated"

    weights_invalid = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3, 4]),
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [2, 3, 4],
                "water_displacement_site_weights": [1.0, -1.0, float("nan")],
                "water_displacement_model_valid": True,
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert weights_invalid.claim_metadata["claim_safe"] is False
    assert weights_invalid.claim_metadata["force_term_status"] == "water_site_weights_invalid"
    assert weights_invalid.claim_metadata["blocked_reason"] == "water_displacement_proxy_weights_invalid"

    overlapping_indices = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2, 3, 4]),
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [1, 2],
                "water_displacement_model_valid": True,
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert overlapping_indices.claim_metadata["claim_safe"] is False
    assert overlapping_indices.claim_metadata["force_term_status"] == "water_site_indices_invalid"
    assert (
        overlapping_indices.claim_metadata["blocked_reason"]
        == "water_displacement_proxy_site_indices_overlap_ligand"
    )

    capped = WaterDisplacementProxyTerm(k_water=0.05, sigma=1.0, max_force_norm=1e-12)
    capped_result = capped.energy_forces(state)
    assert capped_result.claim_metadata["claim_safe"] is False
    assert capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert capped_result.claim_metadata["blocked_reason"] == "water_displacement_proxy_policy_cap_exceeded"
    assert capped_result.claim_metadata["force_term_observed_caps_ready"] is False
    assert capped_result.claim_metadata["force_term_bounded_correction_ready"] is False
    assert capped_result.claim_metadata["force_term_force_norm_within_cap"] is False
    assert torch.count_nonzero(capped_result.forces).item() == 0
    assert torch.count_nonzero(capped_result.energy).item() == 0

    pair_capped = WaterDisplacementProxyTerm(k_water=0.05, sigma=1.0, max_active_pair_count=1)
    pair_capped_result = pair_capped.energy_forces(state)
    assert pair_capped_result.claim_metadata["claim_safe"] is False
    assert pair_capped_result.claim_metadata["force_term_status"] == "policy_cap_exceeded"
    assert pair_capped_result.claim_metadata["blocked_reason"] == "water_displacement_proxy_policy_cap_exceeded"
    assert pair_capped_result.claim_metadata["force_term_active_pair_count_within_cap"] is False
    assert torch.count_nonzero(pair_capped_result.forces).item() == 0


def test_product_forcefield_can_execute_guarded_screened_electrostatics_plugin() -> None:
    forcefield = ProductForceField.from_registry(
        guarded_force_term_registry(),
        names=["screened_electrostatics"],
    )
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float64)
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1]),
        metadata={
            "partial_charges": torch.tensor([1.0, -1.0], dtype=torch.float64),
            "charge_source": "unit_test_validated_proxy",
            "charge_model_valid": True,
        },
    )

    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["force_term_plugins"] == ["screened_electrostatics"]
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert result.claim_metadata["force_term_claim_rows"] == [
        {
            "force_term_name": "screened_electrostatics",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
            "hbond_evidence_status": "pass",
            "hbond_evidence_schema_version": "",
            "hbond_evidence_schema_ready": False,
            "ligand_topology_valid": True,
            "policy_caps_ready": True,
            "observed_caps_ready": True,
            "bounded_correction_ready": True,
            "policy_caps": {
                "max_abs_energy": 50.0,
                "max_force_norm": 25.0,
                "max_active_pair_count": 4096.0,
                "max_abs_delta_score": 50.0,
                "max_displacement": 0.0,
                "max_energy_drift": 50.0,
                "abstain_threshold": 1.0,
            },
            "abs_energy_within_cap": True,
            "force_norm_within_cap": True,
            "active_pair_count_within_cap": True,
        }
    ]
    assert result.diagnostics["term_diagnostics"]["screened_electrostatics"]["status"] == "pass"


def test_product_forcefield_plugin_registry_blocks_missing_metadata_or_bad_term_status() -> None:
    forcefield = ProductForceField.from_registry(names=["directional_hbond"])
    state = EngineState(
        coords=torch.zeros(1, 2, 3),
        atom_types=torch.tensor([0, 1]),
        metadata={},
    )

    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert result.claim_metadata["claim_safe"] is False
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert "directional_hbond:roles_missing" in result.claim_metadata["blocked_reason"]
    assert "hbond_roles_missing" in result.claim_metadata["blocked_reason"]
    term_metadata = result.diagnostics["term_diagnostics"]["directional_hbond"]["claim_metadata"]
    assert term_metadata["force_term_status"] == "roles_missing"
    assert term_metadata["blocked_reason"] == "hbond_roles_missing"
    assert term_metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert term_metadata["hbond_evidence_schema_ready"] is False


def test_product_forcefield_enforces_term_result_contract_before_claim_merge() -> None:
    class BadEnergyShapeTerm:
        name = "bad_energy_shape"

        def energy_forces(self, state: EngineState, pairs=None) -> TermResult:
            return TermResult(
                energy=torch.zeros(1, 1),
                forces=torch.zeros_like(state.coords),
                diagnostics={"term": self.name, "status": "pass"},
                claim_metadata={
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "hbond_evidence_status": "pass",
                    "force_residual_applied": False,
                    "claim_safe": True,
                    "blocked_reason": "",
                    "force_term_name": self.name,
                    "force_term_status": "pass",
                },
            )

    class NonfiniteForceTerm:
        name = "nonfinite_force"

        def energy_forces(self, state: EngineState, pairs=None) -> TermResult:
            forces = torch.zeros_like(state.coords)
            forces[0, 0, 0] = torch.nan
            return TermResult(
                energy=torch.zeros(state.coords.shape[0]),
                forces=forces,
                diagnostics={"term": self.name, "status": "pass"},
                claim_metadata={
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "hbond_evidence_status": "pass",
                    "force_residual_applied": False,
                    "claim_safe": True,
                    "blocked_reason": "",
                    "force_term_name": self.name,
                    "force_term_status": "pass",
                },
            )

    class MismatchedMetadataTerm:
        name = "mismatched_metadata"

        def energy_forces(self, state: EngineState, pairs=None) -> TermResult:
            return TermResult(
                energy=torch.zeros(state.coords.shape[0]),
                forces=torch.zeros_like(state.coords),
                diagnostics={"term": self.name, "status": "pass"},
                claim_metadata={
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "hbond_evidence_status": "pass",
                    "force_residual_applied": False,
                    "claim_safe": True,
                    "blocked_reason": "",
                    "force_term_name": "other_term",
                    "force_term_status": "pass",
                },
            )

    class MissingBaseClaimKeyTerm:
        name = "missing_base_claim_key"

        def energy_forces(self, state: EngineState, pairs=None) -> TermResult:
            return TermResult(
                energy=torch.zeros(state.coords.shape[0]),
                forces=torch.zeros_like(state.coords),
                diagnostics={"term": self.name, "status": "pass"},
                claim_metadata={
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "hbond_evidence_status": "pass",
                    "force_residual_applied": False,
                    "claim_safe": True,
                    "force_term_name": self.name,
                    "force_term_status": "pass",
                },
            )

    class UnboundedCorrectionTerm:
        name = "unbounded_correction"

        def energy_forces(self, state: EngineState, pairs=None) -> TermResult:
            return TermResult(
                energy=torch.zeros(state.coords.shape[0]),
                forces=torch.zeros_like(state.coords),
                diagnostics={"term": self.name, "status": "pass"},
                claim_metadata={
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "hbond_evidence_status": "pass",
                    "force_residual_applied": False,
                    "claim_safe": True,
                    "blocked_reason": "",
                    "force_term_name": self.name,
                    "force_term_status": "pass",
                    "force_term_bounded_correction_required": True,
                },
            )

    state = EngineState(coords=torch.zeros(1, 2, 3), atom_types=torch.tensor([0, 1]))
    claim_metadata = {
        "topology_fidelity": "sequence_mapped",
        "ligand_topology_valid": True,
        "hbond_evidence_status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
    }

    with pytest.raises(ValueError, match="energy with wrong shape"):
        ProductForceField([BadEnergyShapeTerm()]).energy_forces(state, claim_metadata=claim_metadata)
    with pytest.raises(ValueError, match="nonfinite forces"):
        ProductForceField([NonfiniteForceTerm()]).energy_forces(state, claim_metadata=claim_metadata)
    with pytest.raises(ValueError, match="mismatched claim metadata term"):
        ProductForceField([MismatchedMetadataTerm()]).energy_forces(state, claim_metadata=claim_metadata)
    with pytest.raises(ValueError, match="missing claim metadata keys: blocked_reason"):
        ProductForceField([MissingBaseClaimKeyTerm()]).energy_forces(state, claim_metadata=claim_metadata)
    with pytest.raises(ValueError, match="missing bounded correction keys"):
        ProductForceField([UnboundedCorrectionTerm()]).energy_forces(state, claim_metadata=claim_metadata)


def test_term_result_contract_exposes_bounded_correction_validator() -> None:
    coords = torch.zeros(1, 2, 3)
    result = TermResult(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        diagnostics={"term": "bounded_proxy", "status": "pass"},
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "force_residual_applied": False,
            "claim_safe": True,
            "blocked_reason": "",
            "force_term_name": "bounded_proxy",
            "force_term_status": "pass",
            "force_term_policy_caps": {
                "max_abs_energy": 1.0,
                "max_force_norm": 1.0,
                "max_active_pair_count": 16.0,
                "max_abs_delta_score": 1.0,
                "max_displacement": 0.0,
                "max_energy_drift": 1.0,
                "abstain_threshold": 1.0,
            },
            "force_term_policy_caps_ready": True,
            "force_term_observed_caps_ready": True,
            "force_term_bounded_correction_ready": True,
            "force_term_abs_energy_within_cap": True,
            "force_term_force_norm_within_cap": True,
            "force_term_active_pair_count_within_cap": True,
        },
    )

    validate_term_result_contract(name="bounded_proxy", result=result, coords=coords)

    missing_active_pair_cap = TermResult(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        diagnostics={"term": "bounded_proxy", "status": "pass"},
        claim_metadata={
            **result.claim_metadata,
            "force_term_active_pair_count_within_cap": None,
        },
    )
    with pytest.raises(ValueError, match="non-boolean bounded correction key"):
        validate_term_result_contract(
            name="bounded_proxy",
            result=missing_active_pair_cap,
            coords=coords,
        )

    nonfinite_policy_cap = TermResult(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        diagnostics={"term": "bounded_proxy", "status": "pass"},
        claim_metadata={
            **result.claim_metadata,
            "force_term_policy_caps": {
                "max_abs_energy": 1.0,
                "max_force_norm": float("inf"),
                "max_active_pair_count": 16.0,
                "max_abs_delta_score": 1.0,
                "max_displacement": 0.0,
                "max_energy_drift": 1.0,
                "abstain_threshold": 1.0,
            },
        },
    )
    with pytest.raises(ValueError, match="invalid bounded correction policy cap"):
        validate_term_result_contract(
            name="bounded_proxy",
            result=nonfinite_policy_cap,
            coords=coords,
        )

    missing_pair_policy_cap = TermResult(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        diagnostics={"term": "bounded_proxy", "status": "pass"},
        claim_metadata={
            **result.claim_metadata,
            "force_term_policy_caps": {
                "max_abs_energy": 1.0,
                "max_force_norm": 1.0,
                "max_abs_delta_score": 1.0,
                "max_displacement": 0.0,
                "max_energy_drift": 1.0,
                "abstain_threshold": 1.0,
            },
        },
    )
    with pytest.raises(ValueError, match="missing bounded correction policy caps"):
        validate_term_result_contract(
            name="bounded_proxy",
            result=missing_pair_policy_cap,
            coords=coords,
        )

    negative_policy_cap = TermResult(
        energy=torch.zeros(1),
        forces=torch.zeros_like(coords),
        diagnostics={"term": "bounded_proxy", "status": "pass"},
        claim_metadata={
            **result.claim_metadata,
            "force_term_policy_caps": {
                "max_abs_energy": 1.0,
                "max_force_norm": 1.0,
                "max_active_pair_count": -1.0,
                "max_abs_delta_score": 1.0,
                "max_displacement": 0.0,
                "max_energy_drift": 1.0,
                "abstain_threshold": 1.0,
            },
        },
    )
    with pytest.raises(ValueError, match="invalid bounded correction policy cap"):
        validate_term_result_contract(
            name="bounded_proxy",
            result=negative_policy_cap,
            coords=coords,
        )


def test_hbond_evidence_uses_onsps_roles_distance_and_angle() -> None:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    mapped, meta = backmap_4bead_onsps(two_bead, "CCO")
    if meta.get("mapping_source") != "rdkit_etkdg":
        pytest.skip("RDKit ONSPS evidence is required for claim-safe 2-bead H-bond geometry")
    protein = mapped + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
    pocket_center = mapped.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)

    evidence = evaluate_hbond_evidence(
        smiles="CCO",
        protein_xyz=protein,
        ligand_xyz=two_bead,
        pocket_center=pocket_center,
    )

    assert evidence.site_count >= 1
    assert evidence.donor_site_count + evidence.acceptor_site_count == evidence.site_count
    assert evidence.distance_pass_count >= 1
    assert evidence.angle_pass_count >= 1
    assert evidence.distance_pass_fraction > 0.0
    assert evidence.angle_pass_fraction > 0.0
    assert evidence.geometry_evaluated is True
    assert evidence.geometry_complete is True
    assert evidence.donor_acceptor_pairs[0]["role"] in {"donor", "acceptor"}
    assert evidence.hbond_confidence > 0.0
    assert evidence.schema_version == "hbond_evidence_v1"
    assert evidence.claim_safe is True
    assert evidence.abstention_reason == ""
    assert evidence.blocked_reason == ""
    assert evidence.thresholds["claim_safe_confidence_min"] == 0.5
    assert evidence.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert evidence.onsps_backmap_metadata["backmap_status"] == "ok"
    assert evidence.onsps_backmap_metadata["mapping_source"] == "rdkit_etkdg"
    assert evidence.onsps_backmap_metadata["claim_safe"] is True
    assert (
        evidence.onsps_backmap_metadata["role_counts"]["donor"]
        + evidence.onsps_backmap_metadata["role_counts"]["acceptor"]
    ) >= 1
    assert evidence.schema_ready() is True
    assert evidence.threshold_schema_ready() is True
    assert evidence.pair_schema_ready() is True
    assert evidence.geometry_flags_ready() is True
    metadata = evidence.to_claim_metadata(
        topology_fidelity="sequence_mapped",
        ligand_topology_valid=True,
        product_claim_promoted=True,
    )
    assert metadata["hbond_claim_metadata_schema_version"] == "hbond_claim_metadata_v1"
    assert metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert metadata["hbond_evidence_schema_ready"] is True
    assert metadata["hbond_threshold_schema_ready"] is True
    assert metadata["hbond_pair_schema_ready"] is True
    assert metadata["hbond_geometry_flags_ready"] is True
    assert metadata["hbond_status"] == "pass"
    assert metadata["hbond_abstention_reason"] == ""
    assert metadata["hbond_claim_safe"] is True
    assert metadata["hbond_distance_pass_count"] >= 1
    assert metadata["hbond_angle_pass_count"] >= 1
    assert metadata["onsps_backmap_schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert metadata["onsps_backmap_metadata_schema_ready"] is True
    assert metadata["onsps_backmap_claim_safe"] is True
    assert metadata["topology_fidelity"] == "sequence_mapped"
    assert metadata["ligand_topology_valid"] is True
    assert metadata["claim_safe"] is True
    assert metadata["blocked_reason"] == ""


def test_hbond_evidence_abstains_on_delta_backmap_yellow_band() -> None:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    mapped, meta = backmap_4bead_onsps(two_bead, "CCO")
    if meta.get("mapping_source") != "rdkit_etkdg":
        pytest.skip("RDKit ONSPS evidence is required for claim-safe 2-bead H-bond geometry")
    protein = mapped + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
    pocket_center = mapped.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)

    baseline = evaluate_hbond_evidence(
        smiles="CCO",
        protein_xyz=protein,
        ligand_xyz=two_bead,
        pocket_center=pocket_center,
        delta_backmap=0.25,
        delta_backmap_max=2.5,
    )
    yellow_band = evaluate_hbond_evidence(
        smiles="CCO",
        protein_xyz=protein,
        ligand_xyz=two_bead,
        pocket_center=pocket_center,
        delta_backmap=3.0,
        delta_backmap_max=2.5,
    )

    assert baseline.claim_safe is True
    assert baseline.delta_backmap_evaluated is True
    assert baseline.delta_backmap_yellow_band is False
    assert baseline.thresholds["delta_backmap_max"] == 2.5
    assert baseline.schema_ready() is True
    assert yellow_band.claim_safe is False
    assert yellow_band.status == "review"
    assert yellow_band.delta_backmap == 3.0
    assert yellow_band.delta_backmap_max == 2.5
    assert yellow_band.delta_backmap_evaluated is True
    assert yellow_band.delta_backmap_yellow_band is True
    assert yellow_band.blocked_reason == "delta_backmap_yellow_band"
    assert yellow_band.abstention_reason == "delta_backmap_yellow_band"
    assert yellow_band.hbond_confidence < baseline.hbond_confidence
    assert yellow_band.schema_ready() is True

    metadata = yellow_band.to_claim_metadata(
        topology_fidelity="sequence_mapped",
        ligand_topology_valid=True,
        product_claim_promoted=True,
    )
    assert metadata["hbond_delta_backmap"] == 3.0
    assert metadata["hbond_delta_backmap_max"] == 2.5
    assert metadata["hbond_delta_backmap_evaluated"] is True
    assert metadata["hbond_delta_backmap_yellow_band"] is True
    assert metadata["hbond_abstention_reason"] == "delta_backmap_yellow_band"
    assert metadata["hbond_claim_safe"] is False
    assert metadata["claim_safe"] is False
    assert "delta_backmap_yellow_band" in metadata["blocked_reason"]


def test_onsps_backmap_evidence_schema_and_fail_closed_geometry() -> None:
    from betelgeuze_engine.backmapping import ONSPS_BACKMAP_SCHEMA_VERSION as exported_schema

    assert exported_schema == ONSPS_BACKMAP_SCHEMA_VERSION
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    evidence = evaluate_onsps_backmap_evidence(two_bead, "CCO")

    assert evidence.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
    assert evidence.backmap_status == "ok"
    assert evidence.site_count >= 1
    assert evidence.mapped_site_count == evidence.site_count
    assert evidence.input_bead_count == 2
    assert evidence.output_shape[1] == 3
    assert evidence.role_counts["donor"] + evidence.role_counts["acceptor"] >= 1
    if evidence.mapping_source == "rdkit_etkdg":
        assert evidence.claim_safe is True
        assert evidence.blocked_reason == ""
    else:
        assert evidence.claim_safe is False
        assert evidence.blocked_reason == "onsps_fallback_not_claim_safe"

    invalid = evaluate_onsps_backmap_evidence(np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32), "CCO")
    assert invalid.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
    assert invalid.claim_safe is False
    assert invalid.backmap_status == "empty_input"
    assert invalid.blocked_reason == "invalid_two_bead_geometry"
    assert invalid.abstention_reason == "invalid_two_bead_geometry"

    no_sites = evaluate_onsps_backmap_evidence(two_bead, "CCCC")
    assert no_sites.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
    assert no_sites.claim_safe is False
    assert no_sites.backmap_status == "no_onsps_sites"
    assert no_sites.blocked_reason == "no_onsps_sites"
    assert no_sites.site_count == 0


def test_hbond_evidence_fail_closed_schema_for_invalid_or_missing_anchor() -> None:
    invalid = evaluate_hbond_evidence(smiles="C1(")
    assert invalid.claim_safe is False
    assert invalid.status == "invalid_smiles"
    assert invalid.abstention_reason == "invalid_smiles"
    assert invalid.blocked_reason == "invalid_smiles"
    assert invalid.schema_version == "hbond_evidence_v1"
    assert invalid.donor_site_count == 0
    assert invalid.acceptor_site_count == 0
    assert invalid.distance_pass_count == 0
    assert invalid.angle_pass_count == 0
    assert invalid.geometry_evaluated is False
    assert invalid.geometry_complete is False
    assert invalid.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert invalid.onsps_backmap_metadata["backmap_status"] == "invalid_smiles"
    assert invalid.onsps_backmap_metadata["claim_safe"] is False
    assert invalid.onsps_backmap_metadata["blocked_reason"] == "invalid_smiles"
    invalid_metadata = invalid.to_claim_metadata(
        topology_fidelity="sequence_mapped",
        ligand_topology_valid=False,
        product_claim_promoted=True,
    )
    assert invalid.schema_ready() is True
    assert invalid.threshold_schema_ready() is True
    assert invalid.pair_schema_ready() is True
    assert invalid.geometry_flags_ready() is True
    assert invalid_metadata["hbond_evidence_schema_ready"] is True
    assert invalid_metadata["hbond_threshold_schema_ready"] is True
    assert invalid_metadata["hbond_pair_schema_ready"] is True
    assert invalid_metadata["hbond_geometry_flags_ready"] is True
    assert invalid_metadata["hbond_status"] == "invalid_smiles"
    assert invalid_metadata["hbond_abstention_reason"] == "invalid_smiles"
    assert invalid_metadata["hbond_claim_safe"] is False
    assert invalid_metadata["claim_safe"] is False
    assert "ligand_topology_invalid" in invalid_metadata["blocked_reason"]
    assert "invalid_smiles" in invalid_metadata["blocked_reason"]

    missing = evaluate_hbond_evidence(
        smiles="CCO",
        protein_xyz=np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32),
        ligand_xyz=np.asarray([[8.0, 0.0, 0.0], [9.0, 0.0, 0.0]], dtype=np.float32),
    )
    assert missing.claim_safe is False
    assert missing.abstention_reason == "missing_expected_anchor"
    assert missing.geometry_evaluated is True
    assert missing.geometry_complete is True
    assert missing.distance_pass_count == 0

    no_pose_geometry = evaluate_hbond_evidence(smiles="CCO")
    assert no_pose_geometry.claim_safe is False
    assert no_pose_geometry.abstention_reason == "pose_geometry_missing"
    assert no_pose_geometry.geometry_evaluated is False
    assert no_pose_geometry.geometry_complete is False
    assert no_pose_geometry.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert no_pose_geometry.onsps_backmap_metadata["backmap_status"] == "not_evaluated"
    assert no_pose_geometry.onsps_backmap_metadata["claim_safe"] is False
    assert no_pose_geometry.onsps_backmap_metadata["blocked_reason"] == "ligand_geometry_missing"
    no_pose_metadata = no_pose_geometry.to_claim_metadata(
        topology_fidelity="sequence_mapped",
        ligand_topology_valid=True,
        product_claim_promoted=False,
    )
    assert no_pose_metadata["claim_safe"] is False
    assert "pose_geometry_missing" in no_pose_metadata["blocked_reason"]
    assert "hbond_evidence_not_product_claim_promoted" in no_pose_metadata["blocked_reason"]

    broken_thresholds = evaluate_hbond_evidence(smiles="CCO")
    broken_thresholds.thresholds = {"min_distance": 2.4}
    assert broken_thresholds.threshold_schema_ready() is False
    assert broken_thresholds.schema_ready() is False

    broken_pair = evaluate_hbond_evidence(smiles="CCO")
    if broken_pair.donor_acceptor_pairs:
        broken_pair.donor_acceptor_pairs[0].pop("role", None)
        assert broken_pair.pair_schema_ready() is False
        assert broken_pair.schema_ready() is False


def test_hbond_evidence_rejects_overanchored_decoy_contact() -> None:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    mapped, meta = backmap_4bead_onsps(two_bead, "CC(=O)N")
    if meta.get("mapping_source") != "rdkit_etkdg":
        pytest.skip("RDKit ONSPS evidence is required for overanchored decoy fixture")

    evidence = evaluate_hbond_evidence(
        smiles="CC(=O)N",
        protein_xyz=mapped,
        ligand_xyz=two_bead,
    )

    assert evidence.claim_safe is False
    assert evidence.overanchoring_flag is True
    assert evidence.blocked_reason == "overanchored_decoy"
    assert evidence.abstention_reason == "overanchored_decoy"
    assert evidence.geometry_evaluated is True
    assert evidence.geometry_complete is True
    assert evidence.thresholds["overanchor_distance"] == 2.1
    assert evidence.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert evidence.onsps_backmap_metadata["claim_safe"] is True


def test_topology_claim_metadata_blocks_placeholder_and_invalid_ligand() -> None:
    protein = protein_topology_from_sequence("", n_res=3)
    ligand = ligand_topology_from_smiles("")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    assert metadata["topology_fidelity"] == "placeholder_alanine"
    assert metadata["ligand_topology_valid"] is False
    assert metadata["claim_safe"] is False
    assert metadata["blocked_reason"] in {"empty_smiles", "ligand_topology_invalid"}


def test_topology_claim_metadata_carries_ligand_product_validity_status() -> None:
    protein = protein_topology_from_sequence("ACD", n_res=3)
    ligand = ligand_topology_from_smiles("C[C@H](O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[1, 2],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for claim-safe ligand metadata")
    assert metadata["claim_safe"] is True
    assert metadata["blocked_reason"] == ""
    assert metadata["topology_fidelity"] == "sequence_mapped"
    assert metadata["protein_residue_count"] == 3
    assert metadata["protein_topology_valid"] is True
    assert metadata["protein_topology_blocker"] == ""
    assert metadata["pocket_residue_count"] == 2
    assert metadata["pocket_residue_indices"] == [1, 2]
    assert metadata["pocket_residue_indices_valid"] is True
    assert metadata["pocket_topology_blocker"] == ""
    assert metadata["ligand_topology_valid"] is True
    assert metadata["ligand_topology_claim_safe"] is True
    assert metadata["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert metadata["ligand_topology_source"] == "rdkit"
    assert metadata["ligand_atom_count"] == 6
    assert metadata["ligand_hbond_site_count"] >= 1
    assert metadata["ligand_chiral_center_count"] == 1
    assert metadata["ligand_specified_chiral_center_count"] == 1
    assert metadata["ligand_unassigned_chiral_center_count"] == 0
    assert metadata["ligand_chirality_status"] == "specified"
    assert metadata["ligand_chirality_valid"] is True
    assert metadata["ligand_ring_status"] == "not_applicable"
    assert metadata["ligand_ring_valid"] is True
    assert metadata["ligand_protonation_status"] == "neutral_state_parsed"
    assert metadata["ligand_protonation_valid"] is True
    assert metadata["ligand_tautomer_status"] == "connectivity_parsed_tautomer_not_canonicalized"
    assert metadata["ligand_tautomer_valid"] is True
    assert metadata["ligand_validity_blockers"] == []


def test_topology_claim_metadata_blocks_empty_protein_topology() -> None:
    protein = protein_topology_from_sequence("", n_res=0)
    ligand = ligand_topology_from_smiles("C[C@H](O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for empty protein blocker metadata")
    assert metadata["topology_fidelity"] == "placeholder_alanine"
    assert metadata["protein_residue_count"] == 0
    assert metadata["protein_topology_valid"] is False
    assert metadata["protein_topology_blocker"] == "empty_protein_topology"
    assert metadata["ligand_topology_valid"] is True
    assert metadata["ligand_topology_claim_safe"] is True
    assert metadata["claim_safe"] is False
    assert metadata["blocked_reason"] == "empty_protein_topology"


def test_topology_claim_metadata_blocks_invalid_pocket_indices() -> None:
    protein = protein_topology_from_sequence("ACD", n_res=3)
    ligand = ligand_topology_from_smiles("C[C@H](O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[0, 3],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for pocket blocker metadata")
    assert metadata["topology_fidelity"] == "sequence_mapped"
    assert metadata["protein_residue_count"] == 3
    assert metadata["protein_topology_valid"] is True
    assert metadata["ligand_topology_valid"] is True
    assert metadata["ligand_topology_claim_safe"] is True
    assert metadata["pocket_residue_count"] == 2
    assert metadata["pocket_residue_indices"] == [0, 3]
    assert metadata["pocket_residue_indices_valid"] is False
    assert metadata["pocket_topology_blocker"] == "invalid_pocket_residue_indices"
    assert metadata["claim_safe"] is False
    assert metadata["blocked_reason"] == "invalid_pocket_residue_indices"

    negative_pocket = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[-1],
        claim_scope="unit-test",
    )
    negative_metadata = topology_claim_metadata(negative_pocket)
    assert negative_metadata["pocket_residue_indices"] == [-1]
    assert negative_metadata["pocket_residue_indices_valid"] is False
    assert negative_metadata["pocket_topology_blocker"] == "invalid_pocket_residue_indices"
    assert negative_metadata["claim_safe"] is False
    assert negative_metadata["blocked_reason"] == "invalid_pocket_residue_indices"


def test_topology_claim_metadata_allows_empty_pocket_for_valid_topology() -> None:
    protein = protein_topology_from_sequence("ACD", n_res=3)
    ligand = ligand_topology_from_smiles("C[C@H](O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for empty pocket claim-safe metadata")
    assert metadata["pocket_residue_count"] == 0
    assert metadata["pocket_residue_indices"] == []
    assert metadata["pocket_residue_indices_valid"] is True
    assert metadata["pocket_topology_blocker"] == ""
    assert metadata["claim_safe"] is True
    assert metadata["blocked_reason"] == ""


def test_topology_claim_metadata_blocks_unassigned_ligand_chirality() -> None:
    protein = protein_topology_from_sequence("ACD", n_res=3)
    ligand = ligand_topology_from_smiles("CC(O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[1, 2],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for chirality blocker metadata")
    assert ligand.validity["valid"] is True
    assert ligand.validity["claim_safe"] is False
    assert metadata["claim_safe"] is False
    assert metadata["ligand_topology_valid"] is True
    assert metadata["ligand_topology_claim_safe"] is False
    assert metadata["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert metadata["ligand_unassigned_chiral_center_count"] == 1
    assert metadata["ligand_chirality_status"] == "unassigned_chiral_centers"
    assert metadata["ligand_chirality_valid"] is False
    assert "unassigned_ligand_chirality" in metadata["blocked_reason"]
    assert "unassigned_ligand_chirality" in metadata["ligand_validity_blockers"]


def test_engine_topology_factory_facade_builds_claim_metadata() -> None:
    factory = TopologyFactoryFacade(device="cpu", default_claim_scope="unit_test")
    result = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C[C@H](O)C(=O)O",
        pocket_residue_indices=[1, 2],
    )

    assert isinstance(result.complex_topology, ComplexTopology)
    assert result.complex_topology.protein.fidelity == "sequence_mapped"
    assert result.complex_topology.claim_scope == "unit_test"
    assert result.complex_topology.pocket_residue_indices == [1, 2]
    if result.claim_metadata.get("ligand_topology_source") != "rdkit":
        pytest.skip("RDKit topology validity is required for claim-safe ligand metadata")
    assert result.claim_metadata["topology_fidelity"] == "sequence_mapped"
    assert result.claim_metadata["protein_residue_count"] == 3
    assert result.claim_metadata["protein_topology_valid"] is True
    assert result.claim_metadata["pocket_residue_count"] == 2
    assert result.claim_metadata["pocket_residue_indices_valid"] is True
    assert result.claim_metadata["ligand_topology_valid"] is True
    assert result.claim_metadata["ligand_topology_claim_safe"] is True
    assert result.claim_metadata["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""


def test_engine_topology_factory_facade_blocks_placeholder_or_ligand_invalidity() -> None:
    factory = TopologyFactoryFacade(device="cpu")
    placeholder = factory.from_sequence_and_smiles(
        sequence="",
        smiles="C[C@H](O)C(=O)O",
        n_res=3,
    )
    if placeholder.claim_metadata.get("ligand_topology_source") != "rdkit":
        pytest.skip("RDKit topology validity is required for topology factory blocker metadata")
    assert placeholder.claim_metadata["topology_fidelity"] == "placeholder_alanine"
    assert placeholder.claim_metadata["protein_residue_count"] == 3
    assert placeholder.claim_metadata["protein_topology_valid"] is True
    assert placeholder.claim_metadata["ligand_topology_valid"] is True
    assert placeholder.claim_metadata["claim_safe"] is False
    assert placeholder.claim_metadata["blocked_reason"] == "placeholder_alanine_topology"

    invalid_ligand = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C1(",
    )
    assert invalid_ligand.claim_metadata["topology_fidelity"] == "sequence_mapped"
    assert invalid_ligand.claim_metadata["ligand_topology_valid"] is False
    assert invalid_ligand.claim_metadata["claim_safe"] is False
    assert invalid_ligand.claim_metadata["blocked_reason"] == "invalid_smiles"


def test_core_topology_factory_facades_engine_protein_topology() -> None:
    from core.definitions import StrategyType
    from core.topology import TopologyFactory

    topo = TopologyFactory(
        n_res=3,
        t_type=1,
        box_size=[10.0, 10.0, 10.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )

    assert isinstance(topo.protein_topology, ProteinTopology)
    assert topo.protein_topology.fidelity == "placeholder_alanine"
    topo.set_residue_types_from_sequence(torch.tensor([9, 3, 5], dtype=torch.long))
    assert topo.protein_topology.fidelity == "sequence_mapped"
    assert topo.hbond_roles() == topo.protein_topology.hbond_roles
    coords = torch.zeros(1, 3, 3)
    assert torch.allclose(topo.compute_virtual_hbond_bead_coords(coords), topo.protein_topology.virtual_site_offsets.unsqueeze(0))
