from __future__ import annotations

import torch

from betelgeuze_engine.physics.neighbor import NeighborPairs
from tools.product.run_rust_hip_neighbor_provider_parity import (
    build_payload,
    compare_pair_distance_maps,
    pair_distance_map,
)


def test_pair_distance_map_extracts_directed_compact_pairs() -> None:
    pairs = NeighborPairs(
        idx=torch.tensor([[[1, 2, 0], [0, 2, 0], [1, 0, 0]]], dtype=torch.long),
        dist=torch.tensor([[[1.0, 2.0, 0.0], [1.0, 3.0, 0.0], [3.0, 0.0, 0.0]]]),
        mask=torch.tensor([[[True, True, False], [True, True, False], [True, False, False]]]),
        source="test",
    )

    assert pair_distance_map(pairs) == {
        (0, 0, 1): 1.0,
        (0, 0, 2): 2.0,
        (0, 1, 0): 1.0,
        (0, 1, 2): 3.0,
        (0, 2, 1): 3.0,
    }


def test_compare_pair_distance_maps_reports_mismatch_samples() -> None:
    reference = {(0, 0, 1): 1.0, (0, 1, 2): 2.0}
    candidate = {(0, 0, 1): 1.0002, (0, 2, 1): 3.0}

    result = compare_pair_distance_maps(reference, candidate, distance_abs_tol=1e-4)

    assert result["ready"] is False
    assert result["missing_pair_count"] == 1
    assert result["extra_pair_count"] == 1
    assert result["max_distance_abs_delta"] > 1e-4
    assert result["missing_pair_sample"] == [[0, 1, 2]]
    assert result["extra_pair_sample"] == [[0, 2, 1]]


def test_build_payload_fails_closed_when_cuda_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    payload = build_payload(
        atom_counts=[216],
        cutoff=3.1,
        skin=0.0,
        max_neighbor_count=16,
        max_atoms_per_cell=16,
        target_number_density=1.0 / 27.0,
        distance_abs_tol=1e-4,
        energy_abs_tol=1e-4,
        energy_rel_tol=1e-5,
        force_abs_tol=1e-3,
    )

    assert payload["summary"]["status"] == "blocked_rust_hip_neighbor_provider_parity"
    assert payload["summary"]["ready"] is False
    assert payload["blockers"] == ["cuda_unavailable"]
    assert payload["rows"] == []
