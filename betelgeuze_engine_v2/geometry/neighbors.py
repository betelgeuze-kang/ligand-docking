"""Compact bounded-degree radius graphs without dense atom-pair tensors."""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Any

import torch

from betelgeuze_engine_v2.molecular.models import UnitCell


NEIGHBOR_SCHEMA_VERSION = "compact_radius_graph/2.0.0"
MAX_COMPACT_NEIGHBORS = 256
MAX_COMPACT_ATOMS_PER_CELL = 256


@dataclass(frozen=True)
class RadiusGraphConfig:
    """Immutable scientific and capacity limits for one radius graph."""

    cutoff_angstrom: float
    max_neighbors: int = 64
    max_atoms_per_cell: int = 64

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.cutoff_angstrom)) or float(self.cutoff_angstrom) <= 0.0:
            raise ValueError("cutoff_angstrom must be finite and positive")
        if int(self.max_neighbors) < 1:
            raise ValueError("max_neighbors must be positive")
        if int(self.max_neighbors) > MAX_COMPACT_NEIGHBORS:
            raise ValueError(f"max_neighbors exceeds hard cap {MAX_COMPACT_NEIGHBORS}")
        if int(self.max_atoms_per_cell) < 1:
            raise ValueError("max_atoms_per_cell must be positive")
        if int(self.max_atoms_per_cell) > MAX_COMPACT_ATOMS_PER_CELL:
            raise ValueError(
                f"max_atoms_per_cell exceeds hard cap {MAX_COMPACT_ATOMS_PER_CELL}"
            )


@dataclass(frozen=True)
class NeighborBuildDiagnostics:
    schema_version: str
    status: str
    batch_size: int
    atom_count: int
    directed_pair_count: int
    cutoff_angstrom: float
    max_neighbors: int
    max_atoms_per_cell: int
    max_observed_neighbors: int
    max_observed_atoms_per_cell: int
    periodic: tuple[bool, bool, bool]
    overflow: bool
    overflow_kind: str = ""
    nxn_allocation_observed: bool = False
    expected_complexity: str = "O(B*N) at fixed cutoff and bounded cell occupancy"

    @property
    def claim_safe(self) -> bool:
        return bool(not self.overflow and not self.nxn_allocation_observed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "batch_size": self.batch_size,
            "atom_count": self.atom_count,
            "directed_pair_count": self.directed_pair_count,
            "cutoff_angstrom": self.cutoff_angstrom,
            "max_neighbors": self.max_neighbors,
            "max_atoms_per_cell": self.max_atoms_per_cell,
            "max_observed_neighbors": self.max_observed_neighbors,
            "max_observed_atoms_per_cell": self.max_observed_atoms_per_cell,
            "periodic": list(self.periodic),
            "overflow": self.overflow,
            "overflow_kind": self.overflow_kind,
            "nxn_allocation_observed": self.nxn_allocation_observed,
            "expected_complexity": self.expected_complexity,
            "hard_max_neighbors": MAX_COMPACT_NEIGHBORS,
            "hard_max_atoms_per_cell": MAX_COMPACT_ATOMS_PER_CELL,
            "hard_capacity_contract_enforced": bool(
                self.max_neighbors <= MAX_COMPACT_NEIGHBORS
                and self.max_atoms_per_cell <= MAX_COMPACT_ATOMS_PER_CELL
            ),
            "claim_safe": self.claim_safe,
        }


class NeighborOverflowError(RuntimeError):
    """Capacity violation; no truncated graph is returned to the caller."""

    def __init__(self, diagnostics: NeighborBuildDiagnostics):
        self.diagnostics = diagnostics
        super().__init__(
            f"compact radius graph blocked: {diagnostics.overflow_kind} exceeded fixed capacity "
            f"(max_neighbors={diagnostics.max_neighbors}, "
            f"max_atoms_per_cell={diagnostics.max_atoms_per_cell})"
        )


@dataclass(frozen=True)
class CompactNeighborList:
    """Directed neighbor rows with shape ``[B, N, K]``.

    Invalid slots contain index ``-1`` and zero geometry.  ``displacements`` are
    ``r_i - r_j`` and remain differentiable with respect to input coordinates.
    """

    indices: torch.Tensor
    mask: torch.Tensor
    distances: torch.Tensor
    displacements: torch.Tensor
    diagnostics: NeighborBuildDiagnostics

    def __post_init__(self) -> None:
        if self.indices.ndim != 3:
            raise ValueError("indices must have shape [B, N, K]")
        if self.mask.shape != self.indices.shape or self.distances.shape != self.indices.shape:
            raise ValueError("indices, mask, and distances must have matching [B, N, K] shapes")
        if self.displacements.shape != (*self.indices.shape, 3):
            raise ValueError("displacements must have shape [B, N, K, 3]")
        if self.indices.dtype != torch.long:
            raise TypeError("neighbor indices must use torch.long")
        if self.mask.dtype != torch.bool:
            raise TypeError("neighbor mask must use torch.bool")

    @property
    def pair_count(self) -> int:
        return int(self.diagnostics.directed_pair_count)

    @property
    def width(self) -> int:
        return int(self.indices.shape[-1])

    def upper_mask(self) -> torch.Tensor:
        source = torch.arange(self.indices.shape[1], device=self.indices.device).view(1, -1, 1)
        return self.mask & (self.indices > source)

    def edge_triplets(self, *, upper_only: bool = False) -> torch.Tensor:
        """Return compact ``[3, E]`` rows of batch, source, target indices."""

        selected = self.upper_mask() if upper_only else self.mask
        batch_index, source_index, slot = torch.nonzero(selected, as_tuple=True)
        target_index = self.indices[batch_index, source_index, slot]
        return torch.stack((batch_index, source_index, target_index), dim=0)


def _cell_parameters(
    cell: UnitCell | None,
    *,
    cutoff: float,
) -> tuple[list[float] | None, tuple[bool, bool, bool], tuple[int, int, int] | None, tuple[float, float, float]]:
    if cell is None:
        return None, (False, False, False), None, (cutoff, cutoff, cutoff)
    try:
        lengths_t = cell.orthorhombic_lengths()
    except ValueError as exc:
        raise ValueError("compact cell-list v2 currently requires an orthorhombic unit cell") from exc
    lengths = [float(value) for value in lengths_t.detach().to(dtype=torch.float64, device="cpu").tolist()]
    if any(not math.isfinite(value) or value <= 0.0 for value in lengths):
        raise ValueError("unit-cell lengths must be finite and positive")
    periodic = tuple(bool(value) for value in cell.periodic)
    grid_dims = tuple(
        max(1, int(math.floor(length / cutoff))) if periodic[axis] else 0
        for axis, length in enumerate(lengths)
    )
    cell_widths = tuple(
        lengths[axis] / grid_dims[axis] if periodic[axis] else cutoff
        for axis in range(3)
    )
    return lengths, periodic, grid_dims, cell_widths


def _wrapped_position(
    position: list[float],
    *,
    lengths: list[float] | None,
    periodic: tuple[bool, bool, bool],
) -> tuple[float, float, float]:
    values = [float(position[axis]) for axis in range(3)]
    if lengths is not None:
        for axis in range(3):
            if periodic[axis]:
                values[axis] -= lengths[axis] * math.floor(values[axis] / lengths[axis])
    return values[0], values[1], values[2]


def _cell_key(
    position: tuple[float, float, float],
    *,
    periodic: tuple[bool, bool, bool],
    grid_dims: tuple[int, int, int] | None,
    cell_widths: tuple[float, float, float],
) -> tuple[int, int, int]:
    raw = [int(math.floor(position[axis] / cell_widths[axis])) for axis in range(3)]
    if grid_dims is not None:
        for axis in range(3):
            if periodic[axis]:
                raw[axis] %= grid_dims[axis]
    return raw[0], raw[1], raw[2]


def _neighbor_cell_keys(
    center: tuple[int, int, int],
    *,
    periodic: tuple[bool, bool, bool],
    grid_dims: tuple[int, int, int] | None,
) -> tuple[tuple[int, int, int], ...]:
    keys: set[tuple[int, int, int]] = set()
    for offset in itertools.product((-1, 0, 1), repeat=3):
        value = [center[axis] + offset[axis] for axis in range(3)]
        if grid_dims is not None:
            for axis in range(3):
                if periodic[axis]:
                    value[axis] %= grid_dims[axis]
        keys.add((value[0], value[1], value[2]))
    return tuple(sorted(keys))


def _minimum_image_squared_distance(
    first: list[float],
    second: list[float],
    *,
    lengths: list[float] | None,
    periodic: tuple[bool, bool, bool],
) -> float:
    squared = 0.0
    for axis in range(3):
        delta = float(first[axis]) - float(second[axis])
        if lengths is not None and periodic[axis]:
            delta -= lengths[axis] * round(delta / lengths[axis])
        squared += delta * delta
    return squared


def _overflow_diagnostics(
    config: RadiusGraphConfig,
    *,
    batch_size: int,
    atom_count: int,
    periodic: tuple[bool, bool, bool],
    overflow_kind: str,
    max_observed_neighbors: int,
    max_observed_atoms_per_cell: int,
) -> NeighborBuildDiagnostics:
    return NeighborBuildDiagnostics(
        schema_version=NEIGHBOR_SCHEMA_VERSION,
        status="blocked_capacity_overflow",
        batch_size=batch_size,
        atom_count=atom_count,
        directed_pair_count=0,
        cutoff_angstrom=float(config.cutoff_angstrom),
        max_neighbors=int(config.max_neighbors),
        max_atoms_per_cell=int(config.max_atoms_per_cell),
        max_observed_neighbors=max_observed_neighbors,
        max_observed_atoms_per_cell=max_observed_atoms_per_cell,
        periodic=periodic,
        overflow=True,
        overflow_kind=overflow_kind,
    )


def build_compact_radius_graph(
    coordinates: torch.Tensor,
    config: RadiusGraphConfig,
    *,
    cell: UnitCell | None = None,
) -> CompactNeighborList:
    """Build a compact radius graph with expected O(B*N) work.

    A Python/CPU cell map selects discrete neighbors.  Geometry is then gathered
    from the original tensor in O(B*N*K), preserving autograd for distances and
    displacements.  Cell and row capacities are hard gates: overflow raises and
    never returns a silently truncated graph.
    """

    if not isinstance(coordinates, torch.Tensor):
        raise TypeError("coordinates must be a torch.Tensor")
    if coordinates.ndim != 3 or coordinates.shape[-1] != 3:
        raise ValueError("coordinates must have shape [B, N, 3]")
    if not coordinates.is_floating_point():
        raise TypeError("coordinates must use a floating dtype")
    if not bool(torch.isfinite(coordinates).all().detach().cpu().item()):
        raise ValueError("coordinates must be finite")

    batch_size, atom_count, _ = coordinates.shape
    if batch_size < 1 or atom_count < 1:
        raise ValueError("coordinates must contain at least one batch and one atom")
    cutoff = float(config.cutoff_angstrom)
    cutoff_squared = cutoff * cutoff
    lengths, periodic, grid_dims, cell_widths = _cell_parameters(cell, cutoff=cutoff)
    coords_cpu = coordinates.detach().to(dtype=torch.float64, device="cpu")
    index_rows = torch.full(
        (batch_size, atom_count, int(config.max_neighbors)),
        -1,
        dtype=torch.long,
        device="cpu",
    )
    max_observed_atoms_per_cell = 0
    max_observed_neighbors = 0

    for batch_index in range(batch_size):
        positions = coords_cpu[batch_index].tolist()
        wrapped = [
            _wrapped_position(position, lengths=lengths, periodic=periodic)
            for position in positions
        ]
        keys = [
            _cell_key(
                position,
                periodic=periodic,
                grid_dims=grid_dims,
                cell_widths=cell_widths,
            )
            for position in wrapped
        ]
        buckets: dict[tuple[int, int, int], list[int]] = {}
        for atom_index, key in enumerate(keys):
            bucket = buckets.setdefault(key, [])
            bucket.append(atom_index)
            max_observed_atoms_per_cell = max(max_observed_atoms_per_cell, len(bucket))

        if max_observed_atoms_per_cell > int(config.max_atoms_per_cell):
            raise NeighborOverflowError(
                _overflow_diagnostics(
                    config,
                    batch_size=batch_size,
                    atom_count=atom_count,
                    periodic=periodic,
                    overflow_kind="cell_capacity",
                    max_observed_neighbors=max_observed_neighbors,
                    max_observed_atoms_per_cell=max_observed_atoms_per_cell,
                )
            )

        for source_index in range(atom_count):
            candidates: list[tuple[float, int]] = []
            for key in _neighbor_cell_keys(keys[source_index], periodic=periodic, grid_dims=grid_dims):
                for target_index in buckets.get(key, ()):
                    if source_index == target_index:
                        continue
                    squared_distance = _minimum_image_squared_distance(
                        positions[source_index],
                        positions[target_index],
                        lengths=lengths,
                        periodic=periodic,
                    )
                    if squared_distance <= cutoff_squared:
                        candidates.append((squared_distance, target_index))
            candidates.sort(key=lambda value: (value[0], value[1]))
            max_observed_neighbors = max(max_observed_neighbors, len(candidates))
            if len(candidates) > int(config.max_neighbors):
                raise NeighborOverflowError(
                    _overflow_diagnostics(
                        config,
                        batch_size=batch_size,
                        atom_count=atom_count,
                        periodic=periodic,
                        overflow_kind="neighbor_capacity",
                        max_observed_neighbors=max_observed_neighbors,
                        max_observed_atoms_per_cell=max_observed_atoms_per_cell,
                    )
                )
            for slot, (_, target_index) in enumerate(candidates):
                index_rows[batch_index, source_index, slot] = target_index

    indices = index_rows.to(device=coordinates.device)
    mask = indices >= 0
    safe_indices = indices.clamp_min(0)
    batch_offsets = (
        torch.arange(batch_size, device=coordinates.device, dtype=torch.long).view(batch_size, 1, 1)
        * atom_count
    )
    flat_target_indices = (safe_indices + batch_offsets).reshape(-1)
    target_coordinates = coordinates.reshape(batch_size * atom_count, 3)[flat_target_indices]
    target_coordinates = target_coordinates.reshape(batch_size, atom_count, int(config.max_neighbors), 3)
    displacements = coordinates.unsqueeze(2) - target_coordinates

    if lengths is not None and any(periodic):
        box = torch.tensor(lengths, dtype=coordinates.dtype, device=coordinates.device).view(1, 1, 1, 3)
        periodic_mask = torch.tensor(periodic, dtype=torch.bool, device=coordinates.device).view(1, 1, 1, 3)
        correction = torch.where(
            periodic_mask,
            box * torch.round(displacements / box),
            torch.zeros_like(displacements),
        )
        displacements = displacements - correction
    displacements = torch.where(mask.unsqueeze(-1), displacements, torch.zeros_like(displacements))
    distances = torch.where(
        mask,
        torch.linalg.vector_norm(displacements, dim=-1),
        torch.zeros_like(mask, dtype=coordinates.dtype),
    )
    directed_pair_count = int(mask.sum().detach().cpu().item())
    diagnostics = NeighborBuildDiagnostics(
        schema_version=NEIGHBOR_SCHEMA_VERSION,
        status="ready",
        batch_size=batch_size,
        atom_count=atom_count,
        directed_pair_count=directed_pair_count,
        cutoff_angstrom=cutoff,
        max_neighbors=int(config.max_neighbors),
        max_atoms_per_cell=int(config.max_atoms_per_cell),
        max_observed_neighbors=max_observed_neighbors,
        max_observed_atoms_per_cell=max_observed_atoms_per_cell,
        periodic=periodic,
        overflow=False,
    )
    return CompactNeighborList(
        indices=indices,
        mask=mask,
        distances=distances,
        displacements=displacements,
        diagnostics=diagnostics,
    )


build_radius_neighbors = build_compact_radius_graph
