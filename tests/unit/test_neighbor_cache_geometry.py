from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine.physics.neighbor import (  # noqa: E402
    CellListNeighborProvider,
    NeighborProviderConfig,
    neighbor_displacements,
)


def test_zero_skin_rebuilds_when_no_step_is_supplied() -> None:
    provider = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=3.0, skin=0.0, max_neighbor_count=4)
    )
    first_coords = torch.tensor([[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]])
    first = provider.build(first_coords)
    moved = first_coords.clone()
    moved[0, 1, 0] = 2.5
    second = provider.build(moved)
    assert first.diagnostics["rebuilt"] is True
    assert second.diagnostics["rebuilt"] is True
    assert float(second.dist[0, 0, 0]) == pytest.approx(2.5)


def test_skin_cache_reuses_indices_but_refreshes_distances_and_deltas() -> None:
    provider = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=3.0, skin=1.0, max_neighbor_count=4)
    )
    coords = torch.tensor([[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]])
    first = provider.build(coords)
    moved = coords.clone()
    moved[0, 1, 0] = 2.2
    second = provider.build(moved)
    assert second.diagnostics["rebuilt"] is False
    assert torch.equal(first.idx, second.idx)
    assert float(second.dist[0, 0, 0]) == pytest.approx(2.2)
    displacement = neighbor_displacements(moved, first)
    assert abs(float(displacement[0, 0, 0, 0])) == pytest.approx(2.2)


def test_skin_pairs_are_candidates_but_only_activate_inside_force_cutoff() -> None:
    provider = CellListNeighborProvider(
        NeighborProviderConfig(cutoff=3.0, skin=1.0, max_neighbor_count=4)
    )
    coords = torch.tensor([[[0.0, 0.0, 0.0], [3.4, 0.0, 0.0]]])
    first = provider.build(coords)
    assert first.pair_count() == 0
    assert first.candidate_mask is not None
    assert int(first.candidate_mask.sum().item()) == 2

    moved = coords.clone()
    moved[0, 1, 0] = 2.95
    second = provider.build(moved)
    assert second.diagnostics["rebuilt"] is False
    assert second.pair_count() == 2
    assert float(second.dist[0, 0, 0]) == pytest.approx(2.95)
