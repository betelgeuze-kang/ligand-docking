from __future__ import annotations

from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine.physics.neighbor import (  # noqa: E402
    CellListNeighborProvider,
    NeighborProviderConfig,
    RustHipNeighborProvider,
    full_neighbor_pairs,
    neighbor_displacements,
    neighbor_pairs_from_rust_hip_tensors,
    refresh_neighbor_geometry,
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


def test_square_compact_neighbors_are_not_dense_but_reference_pairs_remain_dense() -> None:
    coords = torch.zeros((1, 64, 3))
    coords[0, :, 0] = torch.arange(64) * 2.0
    config = NeighborProviderConfig(cutoff=2.1, skin=0.5, max_neighbor_count=64)
    provider = CellListNeighborProvider(config)
    compact = provider.build(coords)
    assert compact.idx.shape == (1, 64, 64)
    assert compact.storage == "compact"
    assert compact.is_dense is False
    assert provider.build(coords).is_dense is False

    adapted = neighbor_pairs_from_rust_hip_tensors(
        coords,
        nb_idx=compact.idx,
        nb_dist=compact.dist,
        nb_mask=compact.candidate_mask,
        config=config,
    )
    assert adapted.storage == "compact"
    assert adapted.is_dense is False

    reference = full_neighbor_pairs(coords, cutoff=2.1)
    assert reference.idx.shape == compact.idx.shape
    assert reference.storage == "dense_reference"
    assert reference.is_dense is True
    assert refresh_neighbor_geometry(coords, reference).is_dense is True
    assert replace(reference, source="provided", diagnostics={}).is_dense is True
    assert replace(compact, diagnostics={"nxn_allocation_observed": True}).is_dense is True


class _CpuNeighborBackendDouble:
    """Exercise Rust/HIP adapter control flow without importing or running HIP."""

    last_neighbor_build_stats: dict = {}

    @staticmethod
    def has_neighbor_builder() -> bool:
        return True

    @staticmethod
    def build_neighbor_list(
        coords, scalar_box, cutoff, max_neighbors, grid_dims, *, max_atoms_per_cell
    ):
        assert coords.device.type == "cpu"
        pairs = CellListNeighborProvider(
            NeighborProviderConfig(
                cutoff=cutoff,
                max_neighbor_count=max_neighbors,
                max_atoms_per_cell=max_atoms_per_cell,
            )
        ).build(coords, box=scalar_box)
        return pairs.idx, pairs.dist, pairs.mask


@pytest.fixture(params=["cell_list", "rust_hip_cpu_double"])
def cached_provider(request, monkeypatch):
    config = NeighborProviderConfig(cutoff=1.0, skin=1.0, max_neighbor_count=4, rebuild_stride=10)
    if request.param == "cell_list":
        return CellListNeighborProvider(config)
    # Only the dispatch predicate is mocked. Every tensor and backend operation
    # remains on CPU; this is not device parity or a qualification execution.
    monkeypatch.setattr(torch.Tensor, "is_cuda", property(lambda self: True))
    return RustHipNeighborProvider(config, backend=_CpuNeighborBackendDouble())


def _boundary_coords():
    return torch.tensor([[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0]]])


def test_box_value_changes_rebuild_candidate_membership(cached_provider) -> None:
    coords = _boundary_coords()
    first = cached_provider.build(coords, box=20.0)
    assert first.pair_count() == 0
    periodic = cached_provider.build(coords, box=10.0)
    assert periodic.diagnostics["rebuilt"] is True
    assert periodic.pair_count() == 2
    assert float(periodic.dist[0, 0, 0]) == pytest.approx(0.4, abs=1e-6)
    assert cached_provider.build(coords, box=torch.tensor([10.0] * 3)).diagnostics["rebuilt"] is False
    expanded = cached_provider.build(coords, box=20.0)
    assert expanded.diagnostics["rebuilt"] is True
    assert expanded.pair_count() == 0


def test_mutating_caller_box_tensor_cannot_reuse_old_cache(cached_provider) -> None:
    coords = _boundary_coords()
    box = torch.tensor(20.0)
    cached_provider.build(coords, box=box)
    box.fill_(10.0)
    rebuilt = cached_provider.build(coords, box=box)
    assert rebuilt.diagnostics["rebuilt"] is True
    assert rebuilt.pair_count() == 2


def test_pbc_enabled_and_disabled_changes_invalidate_cell_cache() -> None:
    provider = CellListNeighborProvider(NeighborProviderConfig(cutoff=1.0, skin=1.0))
    coords = _boundary_coords()
    assert provider.build(coords).pair_count() == 0
    periodic = provider.build(coords, box=10.0)
    assert periodic.diagnostics["rebuilt"] is True
    assert periodic.pair_count() == 2
    nonperiodic = provider.build(coords)
    assert nonperiodic.diagnostics["rebuilt"] is True
    assert nonperiodic.diagnostics["pbc_enabled"] is False
    assert nonperiodic.pair_count() == 0


def test_pbc_removed_does_not_reuse_rust_adapter_cache(monkeypatch) -> None:
    monkeypatch.setattr(torch.Tensor, "is_cuda", property(lambda self: True))
    provider = RustHipNeighborProvider(
        NeighborProviderConfig(cutoff=1.0, skin=1.0), backend=_CpuNeighborBackendDouble()
    )
    coords = _boundary_coords()
    provider.build(coords, box=10.0)
    assert provider.needs_rebuild(coords) is True
    blocked = provider.build(coords)
    assert blocked.diagnostics["status"] == "blocked_rust_hip_neighbor_provider_requires_box_size"
    assert blocked.diagnostics["overflow"] is True
    assert blocked.pair_count() == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("cutoff", 1.5),
        ("skin", 1.5),
        ("max_neighbor_count", 5),
        ("max_atoms_per_cell", 32),
        ("rebuild_stride", 11),
        ("box_size", 30.0),
    ],
)
def test_config_changes_invalidate_cache(cached_provider, field, value) -> None:
    coords = _boundary_coords()
    cached_provider.build(coords, box=10.0)
    assert cached_provider.needs_rebuild(coords, box=10.0) is False
    cached_provider.config = replace(cached_provider.config, **{field: value})
    assert cached_provider.needs_rebuild(coords, box=10.0) is True
    rebuilt = cached_provider.build(coords, box=10.0)
    assert rebuilt.diagnostics["rebuilt"] is True
    if field == "max_neighbor_count":
        assert rebuilt.idx.shape[-1] == value


def test_config_box_change_uses_new_periodic_membership(cached_provider) -> None:
    coords = _boundary_coords()
    cached_provider.config = replace(cached_provider.config, box_size=20.0)
    assert cached_provider.build(coords).pair_count() == 0
    cached_provider.config = replace(cached_provider.config, box_size=10.0)
    rebuilt = cached_provider.build(coords)
    assert rebuilt.diagnostics["rebuilt"] is True
    assert rebuilt.pair_count() == 2


def test_dtype_and_shape_changes_rebuild(cached_provider) -> None:
    coords = _boundary_coords()
    cached_provider.build(coords, box=10.0)
    converted = coords.to(dtype=torch.float64)
    rebuilt = cached_provider.build(converted, box=10.0)
    assert rebuilt.diagnostics["rebuilt"] is True
    assert rebuilt.dist.dtype == torch.float64
    assert rebuilt.delta.dtype == torch.float64
    resized = converted.expand(2, -1, -1).clone()
    rebuilt_batch = cached_provider.build(resized, box=10.0)
    assert rebuilt_batch.diagnostics["rebuilt"] is True
    assert rebuilt_batch.idx.shape[:2] == (2, 2)
    added_atom = torch.cat([resized, torch.tensor([[[5.0, 0.0, 0.0]]] * 2, dtype=torch.float64)], dim=1)
    rebuilt_atoms = cached_provider.build(added_atom, box=10.0)
    assert rebuilt_atoms.diagnostics["rebuilt"] is True
    assert rebuilt_atoms.idx.shape[:2] == (2, 3)


def test_device_change_invalidates_before_reading_tensor_values(cached_provider) -> None:
    coords = _boundary_coords()
    cached_provider.build(coords, box=10.0)
    # A CPU-only metadata double tests device identity without allocating CUDA
    # tensors. The signature must reject the cache before coordinate arithmetic.
    class OtherDeviceCoordinates:
        shape = coords.shape
        dtype = coords.dtype
        device = torch.device("cpu", 1)

    assert cached_provider.needs_rebuild(OtherDeviceCoordinates(), box=10.0) is True


def test_stride_motion_and_step_reset_still_invalidate(cached_provider) -> None:
    coords = _boundary_coords()
    cached_provider.build(coords, step=3, box=10.0)
    assert cached_provider.needs_rebuild(coords, step=4, box=10.0) is False
    assert cached_provider.needs_rebuild(coords, step=13, box=10.0) is True
    assert cached_provider.needs_rebuild(coords, step=2, box=10.0) is True
    moved = coords.clone()
    moved[0, 1, 0] += 0.6
    assert cached_provider.needs_rebuild(moved, step=4, box=10.0) is True


def test_rust_cpu_blocked_cache_stays_fail_closed_across_input_changes() -> None:
    provider = RustHipNeighborProvider(NeighborProviderConfig(cutoff=1.0, skin=1.0))
    coords = _boundary_coords()
    first = provider.build(coords, box=10.0)
    assert first.diagnostics["blocked_reason"] == "coords_not_cuda"
    reused = provider.build(coords, box=10.0)
    assert reused.diagnostics["rebuilt"] is False
    assert reused.diagnostics["claim_safe"] is False
    changed_box = provider.build(coords, box=20.0)
    assert changed_box.diagnostics["rebuilt"] is True
    assert changed_box.diagnostics["blocked_reason"] == "coords_not_cuda"
    changed_dtype = provider.build(coords.double(), box=20.0)
    assert changed_dtype.diagnostics["rebuilt"] is True
    assert changed_dtype.dist.dtype == torch.float64
    assert changed_dtype.diagnostics["claim_safe"] is False
