import inspect
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.geometry import NeighborOverflowError
from core.ai_correction import NeuralForceCorrection
from train import runtime_inputs
from train.runtime_inputs import (
    MAX_RUNTIME_NEIGHBOR_CAPACITY,
    RUNTIME_INPUT_SCHEMA_ID,
    RuntimeInputSchemaError,
    _build_sparse_radius_neighbor_data,
    build_runtime_inputs,
    filter_runtime_conditioning_params,
    resolve_sim_params,
    require_runtime_input_checkpoint_schema,
    runtime_input_schema_metadata,
)


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


def test_sparse_runtime_neighbors_preserve_coordinate_gradients_without_dense_pairs():
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0]]],
        dtype=torch.float64,
        requires_grad=True,
    )
    (indices, distances, mask), diagnostics = _build_sparse_radius_neighbor_data(
        coords,
        neighbor_k=2,
        cutoff_angstrom=1.6,
        max_neighbor_candidates=4,
        max_atoms_per_cell=4,
    )

    assert indices.shape == (1, 3, 2)
    assert distances.shape == mask.shape == indices.shape
    assert int(mask.sum().item()) == 4
    assert diagnostics["nxn_allocation_observed"] is False
    assert diagnostics["source"] == "v2_compact_radius_graph"

    distances.sum().backward()
    assert coords.grad is not None
    assert bool(torch.isfinite(coords.grad).all().item())


def test_runtime_potential_proxy_excludes_padded_neighbor_slots():
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float32)
    residues = torch.zeros((1, 2), dtype=torch.long)

    top, (_idx, _dist, mask), pe_proxy, _sim_params = build_runtime_inputs(
        coords,
        residues,
        neighbor_k=10,
        neighbor_cutoff_angstrom=5.0,
        max_neighbor_candidates=10,
        max_atoms_per_cell=10,
    )

    assert int(mask.sum().item()) == 2
    assert torch.allclose(pe_proxy, torch.tensor([[0.25]]))
    assert top.neighbor_diagnostics["truncated_row_count"] == 0


def test_runtime_neighbor_capacity_overflow_is_fail_closed():
    coords = torch.zeros((1, 5, 3), dtype=torch.float32)
    with pytest.raises(NeighborOverflowError):
        _build_sparse_radius_neighbor_data(
            coords,
            neighbor_k=2,
            cutoff_angstrom=2.0,
            max_neighbor_candidates=4,
            max_atoms_per_cell=2,
        )


def test_runtime_neighbor_width_cannot_expand_into_n_by_n_storage():
    coords = torch.zeros((1, 4, 3), dtype=torch.float32)
    with pytest.raises(ValueError, match="neighbor_k exceeds"):
        _build_sparse_radius_neighbor_data(
            coords,
            neighbor_k=5,
            max_neighbor_candidates=4,
        )
    with pytest.raises(ValueError, match="max_neighbor_candidates"):
        _build_sparse_radius_neighbor_data(
            coords,
            neighbor_k=1,
            max_neighbor_candidates=MAX_RUNTIME_NEIGHBOR_CAPACITY + 1,
        )


def test_runtime_input_builder_does_not_use_all_pairs_distance_matrix():
    assert "torch.cdist" not in inspect.getsource(runtime_inputs)


def test_runtime_checkpoint_schema_blocks_silent_legacy_semantic_reuse():
    expected = runtime_input_schema_metadata(
        neighbor_k=10,
        cutoff_angstrom=12.0,
        max_neighbor_candidates=64,
        max_atoms_per_cell=64,
    )
    assert expected["schema_id"] == RUNTIME_INPUT_SCHEMA_ID
    assert expected["legacy_global_knn_compatible"] is False
    with pytest.raises(RuntimeInputSchemaError, match="legacy/raw checkpoint"):
        require_runtime_input_checkpoint_schema({"state_dict": {}})
    with pytest.raises(RuntimeInputSchemaError, match="configuration mismatch"):
        require_runtime_input_checkpoint_schema(
            {"runtime_input_schema": dict(expected)},
            expected={**expected, "neighbor_k": 8},
        )
    observed = require_runtime_input_checkpoint_schema(
        {"runtime_input_schema": dict(expected)},
        expected=expected,
    )
    assert observed == expected

    for consumer in (
        "train/train_pipeline.py",
        "benchmark/performance_bench.py",
        "tools/export_ai_router_onnx.py",
    ):
        source = Path(consumer).read_text(encoding="utf-8")
        assert "require_runtime_input_checkpoint_schema(" in source


def test_sparse_runtime_adapter_feeds_batched_legacy_correction_without_shape_loss():
    torch.manual_seed(9)
    coords = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0]],
            [[0.0, 1.0, 0.0], [1.5, 1.0, 0.0], [3.0, 1.0, 0.0]],
        ],
        dtype=torch.float32,
    )
    residues = torch.tensor([[1, 2, 3], [3, 2, 1]], dtype=torch.long)
    top, neighbor_data, potential, sim_params = build_runtime_inputs(
        coords,
        residues,
        neighbor_k=2,
        neighbor_cutoff_angstrom=2.0,
        max_neighbor_candidates=4,
        max_atoms_per_cell=4,
    )
    model = NeuralForceCorrection(hidden_dim=64, num_layers=1).eval()
    forces, diagnostics = model(coords, top, neighbor_data, potential, sim_params)
    assert forces.shape == coords.shape
    assert bool(torch.isfinite(forces).all().item())
    assert diagnostics["se3_equivariant"] is False
