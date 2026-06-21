from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch


@dataclass
class NeighborPairs:
    idx: torch.Tensor
    dist: torch.Tensor
    mask: torch.Tensor
    delta: torch.Tensor | None = None
    source: str = "provided"
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_dense(self) -> bool:
        return bool(self.idx.ndim == 3 and self.idx.shape[1] == self.idx.shape[2])

    def pair_count(self) -> int:
        return int(self.mask.sum().detach().cpu().item())


@dataclass(frozen=True)
class NeighborProviderConfig:
    cutoff: float
    skin: float = 0.0
    max_neighbor_count: int = 64
    max_atoms_per_cell: int = 64
    rebuild_stride: int = 1
    box_size: float | None = None

    def __post_init__(self) -> None:
        if float(self.cutoff) <= 0.0:
            raise ValueError("cutoff must be positive")
        if float(self.skin) < 0.0:
            raise ValueError("skin must be non-negative")
        if int(self.max_neighbor_count) < 1:
            raise ValueError("max_neighbor_count must be positive")
        if int(self.max_atoms_per_cell) < 1:
            raise ValueError("max_atoms_per_cell must be positive")
        if int(self.rebuild_stride) < 1:
            raise ValueError("rebuild_stride must be positive")
        if self.box_size is not None and float(self.box_size) <= 0.0:
            raise ValueError("box_size must be positive when provided")


@dataclass(frozen=True)
class NeighborBuildDiagnostics:
    status: str
    source: str
    cutoff: float
    skin: float
    max_neighbor_count: int
    max_atoms_per_cell: int
    pair_count: int
    atom_count: int
    batch_size: int
    overflow: bool
    neighbor_overflow_count: int
    cell_overflow_count: int
    max_observed_neighbors: int
    max_observed_atoms_per_cell: int
    rebuilt: bool
    rebuild_reason: str
    pbc_enabled: bool
    nxn_allocation_observed: bool = False

    @property
    def claim_safe(self) -> bool:
        return bool(not self.overflow and not self.nxn_allocation_observed)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "source": self.source,
            "cutoff": float(self.cutoff),
            "skin": float(self.skin),
            "max_neighbor_count": int(self.max_neighbor_count),
            "max_atoms_per_cell": int(self.max_atoms_per_cell),
            "pair_count": int(self.pair_count),
            "atom_count": int(self.atom_count),
            "batch_size": int(self.batch_size),
            "overflow": bool(self.overflow),
            "neighbor_overflow_count": int(self.neighbor_overflow_count),
            "cell_overflow_count": int(self.cell_overflow_count),
            "max_observed_neighbors": int(self.max_observed_neighbors),
            "max_observed_atoms_per_cell": int(self.max_observed_atoms_per_cell),
            "rebuilt": bool(self.rebuilt),
            "rebuild_reason": self.rebuild_reason,
            "pbc_enabled": bool(self.pbc_enabled),
            "nxn_allocation_observed": bool(self.nxn_allocation_observed),
            "claim_safe": self.claim_safe,
        }
        return payload


def _box_tensor(box: torch.Tensor | float | None, *, coords: torch.Tensor) -> torch.Tensor | None:
    if box is None:
        return None
    value = torch.as_tensor(box, dtype=coords.dtype, device=coords.device)
    if value.ndim == 0:
        value = value.repeat(3)
    if value.numel() == 1:
        value = value.reshape(1).repeat(3)
    if value.numel() != 3:
        raise ValueError("box must be scalar or length-3")
    if not bool(torch.isfinite(value).all().item()) or bool((value <= 0.0).any().item()):
        raise ValueError("box values must be finite and positive")
    return value.reshape(3)


def _minimum_image(delta: torch.Tensor, box: torch.Tensor | None) -> torch.Tensor:
    if box is None:
        return delta
    return delta - box.view(*((1,) * (delta.ndim - 1)), 3) * torch.round(
        delta / box.view(*((1,) * (delta.ndim - 1)), 3)
    )


def full_neighbor_pairs(coords: torch.Tensor, *, cutoff: float | None = None) -> NeighborPairs:
    if coords.ndim != 3 or coords.shape[-1] != 3:
        raise ValueError("coords must have shape [B, N, 3]")
    b, n, _ = coords.shape
    device = coords.device
    idx = torch.arange(n, device=device).view(1, 1, n).expand(b, n, n)
    diff = coords.unsqueeze(2) - coords.unsqueeze(1)
    dist = diff.norm(dim=-1)
    mask = ~torch.eye(n, dtype=torch.bool, device=device).view(1, n, n).expand(b, n, n)
    if cutoff is not None:
        mask = mask & (dist <= float(cutoff))
    return NeighborPairs(
        idx=idx,
        dist=dist,
        mask=mask,
        delta=diff,
        source="full_neighbor_pairs",
        diagnostics={
            "status": "reference_full_pairs_ready",
            "source": "full_neighbor_pairs",
            "reference_only": True,
            "nxn_allocation_observed": True,
            "pair_count": int(mask.sum().detach().cpu().item()),
        },
    )


def neighbor_source_indices(pairs: NeighborPairs) -> torch.Tensor:
    if pairs.idx.ndim != 3:
        raise ValueError("neighbor idx must have shape [B, N, K]")
    _, atom_count, width = pairs.idx.shape
    return torch.arange(atom_count, device=pairs.idx.device).view(1, atom_count, 1).expand(-1, -1, width)


def neighbor_displacements(coords: torch.Tensor, pairs: NeighborPairs) -> torch.Tensor:
    if pairs.idx.ndim != 3 or pairs.mask.shape != pairs.idx.shape or pairs.dist.shape != pairs.idx.shape:
        raise ValueError("neighbor pairs must have matching [B, N, K] idx/dist/mask shapes")
    if coords.ndim != 3 or coords.shape[-1] != 3:
        raise ValueError("coords must have shape [B, N, 3]")
    if pairs.idx.shape[0] != coords.shape[0] or pairs.idx.shape[1] != coords.shape[1]:
        raise ValueError("neighbor pairs must match coords batch and atom dimensions")
    if pairs.delta is not None and not coords.requires_grad:
        if pairs.delta.shape != (*pairs.idx.shape, 3):
            raise ValueError("neighbor delta must have shape [B, N, K, 3]")
        return pairs.delta.to(dtype=coords.dtype, device=coords.device)
    gather_idx = pairs.idx.clamp(min=0, max=max(int(coords.shape[1]) - 1, 0)).to(device=coords.device)
    expanded = gather_idx.unsqueeze(-1).expand(-1, -1, -1, 3)
    coords_j = torch.gather(coords.unsqueeze(1).expand(-1, coords.shape[1], -1, -1), 2, expanded)
    delta = coords.unsqueeze(2) - coords_j
    if bool(pairs.diagnostics.get("pbc_enabled") is True) and pairs.diagnostics.get("box_size") is not None:
        return _minimum_image(delta, _box_tensor(pairs.diagnostics.get("box_size"), coords=coords))
    return delta


def neighbor_upper_mask(pairs: NeighborPairs) -> torch.Tensor:
    source = neighbor_source_indices(pairs).expand_as(pairs.idx)
    return pairs.mask & (pairs.idx.to(device=source.device) > source)


class CellListNeighborProvider:
    """CPU reference cell-list provider for bounded-density product neighbor paths."""

    source = "provided_cell_list"

    def __init__(self, config: NeighborProviderConfig):
        self.config = config
        self._cached_pairs: NeighborPairs | None = None
        self._cached_coords: torch.Tensor | None = None
        self._cached_step: int | None = None

    def needs_rebuild(self, coords: torch.Tensor, *, step: int | None = None) -> bool:
        if self._cached_pairs is None or self._cached_coords is None:
            return True
        if step is not None and self._cached_step is not None:
            if int(step) - int(self._cached_step) >= int(self.config.rebuild_stride):
                return True
        if float(self.config.skin) <= 0.0:
            return False
        if coords.shape != self._cached_coords.shape:
            return True
        displacement = (coords.detach() - self._cached_coords.to(device=coords.device, dtype=coords.dtype)).norm(dim=-1)
        return bool(displacement.amax().item() > (0.5 * float(self.config.skin)))

    def build(
        self,
        coords: torch.Tensor,
        *,
        step: int | None = None,
        box: torch.Tensor | float | None = None,
    ) -> NeighborPairs:
        if coords.ndim != 3 or coords.shape[-1] != 3:
            raise ValueError("coords must have shape [B, N, 3]")
        if not self.needs_rebuild(coords, step=step):
            assert self._cached_pairs is not None
            diagnostics = dict(self._cached_pairs.diagnostics)
            diagnostics["rebuilt"] = False
            diagnostics["rebuild_reason"] = "cached"
            return NeighborPairs(
                idx=self._cached_pairs.idx,
                dist=self._cached_pairs.dist,
                mask=self._cached_pairs.mask,
                delta=self._cached_pairs.delta,
                source=self._cached_pairs.source,
                diagnostics=diagnostics,
            )
        pairs = self._build(coords, box=box)
        self._cached_pairs = pairs
        self._cached_coords = coords.detach().clone()
        self._cached_step = int(step) if step is not None else None
        return pairs

    def _build(self, coords: torch.Tensor, *, box: torch.Tensor | float | None = None) -> NeighborPairs:
        cfg = self.config
        batch, atom_count, _ = coords.shape
        device = coords.device
        dtype = coords.dtype
        max_neighbors = int(cfg.max_neighbor_count)
        effective_cutoff = float(cfg.cutoff) + float(cfg.skin)
        box_value = _box_tensor(box if box is not None else cfg.box_size, coords=coords)
        pbc_enabled = box_value is not None
        idx = torch.zeros((batch, atom_count, max_neighbors), dtype=torch.long, device=device)
        dist = torch.zeros((batch, atom_count, max_neighbors), dtype=dtype, device=device)
        delta_out = torch.zeros((batch, atom_count, max_neighbors, 3), dtype=dtype, device=device)
        mask = torch.zeros((batch, atom_count, max_neighbors), dtype=torch.bool, device=device)
        neighbor_overflow_count = 0
        cell_overflow_count = 0
        max_observed_neighbors = 0
        max_observed_atoms_per_cell = 0
        pair_count = 0

        coords_cpu = coords.detach().cpu()
        box_cpu = box_value.detach().cpu() if box_value is not None else None
        for b_idx in range(batch):
            buckets: dict[tuple[int, int, int], list[int]] = {}
            wrapped_positions: list[torch.Tensor] = []
            if box_cpu is not None:
                grid_dims = tuple(
                    max(1, int(torch.floor(v.to(dtype=torch.float64) / effective_cutoff).item()))
                    for v in box_cpu
                )
            else:
                grid_dims = None

            def _cell_from_pos(pos: torch.Tensor) -> tuple[int, int, int]:
                raw = [int(torch.floor(v / effective_cutoff).item()) for v in pos]
                if grid_dims is None:
                    return (raw[0], raw[1], raw[2])
                return tuple(raw[axis] % grid_dims[axis] for axis in range(3))

            for atom_idx in range(atom_count):
                pos = coords_cpu[b_idx, atom_idx].to(dtype=torch.float64)
                if box_cpu is not None:
                    pos = pos - box_cpu.to(dtype=torch.float64) * torch.floor(pos / box_cpu.to(dtype=torch.float64))
                wrapped_positions.append(pos)
                cell = _cell_from_pos(pos)
                bucket = buckets.setdefault(cell, [])
                bucket.append(atom_idx)
                max_observed_atoms_per_cell = max(max_observed_atoms_per_cell, len(bucket))
                if len(bucket) > int(cfg.max_atoms_per_cell):
                    cell_overflow_count += 1
            for i in range(atom_count):
                pos_i = wrapped_positions[i]
                cell_i = _cell_from_pos(pos_i)
                candidates: list[tuple[float, int, torch.Tensor]] = []
                ranges = [range(cell_i[axis] - 1, cell_i[axis] + 2) for axis in range(3)]
                seen_cells: set[tuple[int, int, int]] = set()
                for cx in ranges[0]:
                    for cy in ranges[1]:
                        for cz in ranges[2]:
                            if grid_dims is None:
                                ncell = (cx, cy, cz)
                            else:
                                ncell = (cx % grid_dims[0], cy % grid_dims[1], cz % grid_dims[2])
                            if ncell in seen_cells:
                                continue
                            seen_cells.add(ncell)
                            for j in buckets.get(ncell, []):
                                if i == j:
                                    continue
                                raw_delta = coords_cpu[b_idx, i].to(dtype=torch.float64) - coords_cpu[b_idx, j].to(dtype=torch.float64)
                                if box_cpu is not None:
                                    raw_delta = raw_delta - box_cpu.to(dtype=torch.float64) * torch.round(raw_delta / box_cpu.to(dtype=torch.float64))
                                r = float(raw_delta.norm().item())
                                if r <= effective_cutoff:
                                    candidates.append((r, j, raw_delta.to(dtype=coords_cpu.dtype)))
                candidates.sort(key=lambda row: (row[0], row[1]))
                max_observed_neighbors = max(max_observed_neighbors, len(candidates))
                if len(candidates) > max_neighbors:
                    neighbor_overflow_count += len(candidates) - max_neighbors
                for slot, (r, j, delta_value) in enumerate(candidates[:max_neighbors]):
                    idx[b_idx, i, slot] = int(j)
                    dist[b_idx, i, slot] = torch.as_tensor(r, dtype=dtype, device=device)
                    delta_out[b_idx, i, slot] = delta_value.to(dtype=dtype, device=device)
                    mask[b_idx, i, slot] = True
                    pair_count += 1

        overflow = bool(neighbor_overflow_count or cell_overflow_count)
        diagnostics = NeighborBuildDiagnostics(
            status="blocked_neighbor_provider_overflow" if overflow else "neighbor_provider_ready",
            source=self.source,
            cutoff=float(cfg.cutoff),
            skin=float(cfg.skin),
            max_neighbor_count=max_neighbors,
            max_atoms_per_cell=int(cfg.max_atoms_per_cell),
            pair_count=pair_count,
            atom_count=atom_count,
            batch_size=batch,
            overflow=overflow,
            neighbor_overflow_count=neighbor_overflow_count,
            cell_overflow_count=cell_overflow_count,
            max_observed_neighbors=max_observed_neighbors,
            max_observed_atoms_per_cell=max_observed_atoms_per_cell,
            rebuilt=True,
            rebuild_reason="initial_or_due",
            pbc_enabled=pbc_enabled,
            nxn_allocation_observed=False,
        ).to_dict()
        diagnostics["box_size"] = _diagnostic_box_value(box_value)
        return NeighborPairs(
            idx=idx,
            dist=dist,
            mask=mask,
            delta=delta_out,
            source=self.source,
            diagnostics=diagnostics,
        )


def _diagnostic_box_value(box: torch.Tensor | None) -> float | list[float] | None:
    if box is None:
        return None
    values = [float(v) for v in box.detach().cpu().reshape(3)]
    if values[0] == values[1] == values[2]:
        return values[0]
    return values


def neighbor_pairs_from_rust_hip_tensors(
    coords: torch.Tensor,
    *,
    nb_idx: torch.Tensor,
    nb_dist: torch.Tensor,
    nb_mask: torch.Tensor,
    config: NeighborProviderConfig,
    box: torch.Tensor | float | None = None,
    backend_stats: dict[str, Any] | None = None,
) -> NeighborPairs:
    """Adapt Rust/HIP compact neighbor tensors to the product NeighborPairs contract."""

    if coords.ndim != 3 or coords.shape[-1] != 3:
        raise ValueError("coords must have shape [B, N, 3]")
    if nb_idx.ndim != 3 or nb_dist.shape != nb_idx.shape or nb_mask.shape != nb_idx.shape:
        raise ValueError("Rust/HIP neighbor tensors must have matching [B, N, K] shapes")
    if nb_idx.shape[0] != coords.shape[0] or nb_idx.shape[1] != coords.shape[1]:
        raise ValueError("Rust/HIP neighbor tensors must match coords batch and atom dimensions")

    device = coords.device
    dtype = coords.dtype
    idx = nb_idx.to(device=device, dtype=torch.long).contiguous()
    mask = nb_mask.to(device=device).bool().contiguous()
    box_value = _box_tensor(box if box is not None else config.box_size, coords=coords)
    gather_idx = idx.clamp(min=0, max=max(int(coords.shape[1]) - 1, 0))
    expanded = gather_idx.unsqueeze(-1).expand(-1, -1, -1, 3)
    coords_j = torch.gather(coords.unsqueeze(1).expand(-1, coords.shape[1], -1, -1), 2, expanded)
    delta = coords.unsqueeze(2) - coords_j
    delta = _minimum_image(delta, box_value).to(dtype=dtype, device=device)
    dist = torch.where(mask, delta.norm(dim=-1), torch.zeros_like(mask, dtype=dtype))

    stats = dict(backend_stats or {})
    max_neighbors = int(idx.shape[-1])
    pair_count = int(mask.sum().detach().cpu().item())
    cap_expanded = max_neighbors > int(config.max_neighbor_count)
    neighbor_saturated = bool(stats.get("neighbor_saturated") is True)
    cell_overflow = bool(stats.get("cell_overflow") is True)
    overflow = bool(cap_expanded or neighbor_saturated or cell_overflow)
    diagnostics = NeighborBuildDiagnostics(
        status="blocked_rust_hip_neighbor_provider_overflow" if overflow else "neighbor_provider_ready",
        source="rust_hip_cell_list",
        cutoff=float(config.cutoff),
        skin=float(config.skin),
        max_neighbor_count=max_neighbors,
        max_atoms_per_cell=int(stats.get("max_atoms_per_cell") or config.max_atoms_per_cell),
        pair_count=pair_count,
        atom_count=int(coords.shape[1]),
        batch_size=int(coords.shape[0]),
        overflow=overflow,
        neighbor_overflow_count=int(neighbor_saturated),
        cell_overflow_count=int(cell_overflow),
        max_observed_neighbors=int(stats.get("max_row_count") or 0),
        max_observed_atoms_per_cell=int(stats.get("max_cell_count") or 0),
        rebuilt=True,
        rebuild_reason="rust_hip_backend",
        pbc_enabled=box_value is not None,
        nxn_allocation_observed=False,
    ).to_dict()
    diagnostics.update(
        {
            "backend_stats": stats,
            "cap_expanded": bool(cap_expanded),
            "box_size": _diagnostic_box_value(box_value),
        }
    )
    return NeighborPairs(
        idx=idx,
        dist=dist,
        mask=mask,
        delta=delta,
        source="rust_hip_cell_list",
        diagnostics=diagnostics,
    )


class RustHipNeighborProvider:
    """Fail-closed adapter for the Rust/HIP compact cell-list neighbor builder."""

    source = "rust_hip_cell_list"

    def __init__(self, config: NeighborProviderConfig, *, backend: Any | None = None):
        self.config = config
        self._backend = backend
        self._cached_pairs: NeighborPairs | None = None
        self._cached_coords: torch.Tensor | None = None
        self._cached_step: int | None = None

    def needs_rebuild(self, coords: torch.Tensor, *, step: int | None = None) -> bool:
        if self._cached_pairs is None or self._cached_coords is None:
            return True
        if step is not None and self._cached_step is not None:
            if int(step) - int(self._cached_step) >= int(self.config.rebuild_stride):
                return True
        if float(self.config.skin) <= 0.0:
            return False
        if coords.shape != self._cached_coords.shape:
            return True
        displacement = (coords.detach() - self._cached_coords.to(device=coords.device, dtype=coords.dtype)).norm(dim=-1)
        return bool(displacement.amax().item() > (0.5 * float(self.config.skin)))

    def _blocked_pairs(self, coords: torch.Tensor, *, status: str, reason: str) -> NeighborPairs:
        batch = int(coords.shape[0]) if coords.ndim == 3 else 1
        atom_count = int(coords.shape[1]) if coords.ndim == 3 else 0
        width = int(self.config.max_neighbor_count)
        device = coords.device
        dtype = coords.dtype if coords.is_floating_point() else torch.float32
        diagnostics = NeighborBuildDiagnostics(
            status=status,
            source=self.source,
            cutoff=float(self.config.cutoff),
            skin=float(self.config.skin),
            max_neighbor_count=width,
            max_atoms_per_cell=int(self.config.max_atoms_per_cell),
            pair_count=0,
            atom_count=atom_count,
            batch_size=batch,
            overflow=True,
            neighbor_overflow_count=0,
            cell_overflow_count=0,
            max_observed_neighbors=0,
            max_observed_atoms_per_cell=0,
            rebuilt=True,
            rebuild_reason=reason,
            pbc_enabled=self.config.box_size is not None,
            nxn_allocation_observed=False,
        ).to_dict()
        diagnostics["blocked_reason"] = reason
        return NeighborPairs(
            idx=torch.zeros((batch, atom_count, width), dtype=torch.long, device=device),
            dist=torch.zeros((batch, atom_count, width), dtype=dtype, device=device),
            mask=torch.zeros((batch, atom_count, width), dtype=torch.bool, device=device),
            delta=torch.zeros((batch, atom_count, width, 3), dtype=dtype, device=device),
            source=self.source,
            diagnostics=diagnostics,
        )

    def _backend_or_none(self) -> Any | None:
        if self._backend is not None:
            return self._backend
        try:
            from core.rust_hip_backend import RustHipBackend
        except Exception:
            return None
        self._backend = RustHipBackend(device=torch.device("cuda"))
        return self._backend

    def build(
        self,
        coords: torch.Tensor,
        *,
        step: int | None = None,
        box: torch.Tensor | float | None = None,
    ) -> NeighborPairs:
        if coords.ndim != 3 or coords.shape[-1] != 3:
            raise ValueError("coords must have shape [B, N, 3]")
        if not self.needs_rebuild(coords, step=step):
            assert self._cached_pairs is not None
            diagnostics = dict(self._cached_pairs.diagnostics)
            diagnostics["rebuilt"] = False
            diagnostics["rebuild_reason"] = "cached"
            return NeighborPairs(
                idx=self._cached_pairs.idx,
                dist=self._cached_pairs.dist,
                mask=self._cached_pairs.mask,
                delta=self._cached_pairs.delta,
                source=self._cached_pairs.source,
                diagnostics=diagnostics,
            )
        if not coords.is_cuda:
            pairs = self._blocked_pairs(
                coords,
                status="blocked_rust_hip_neighbor_provider_unavailable",
                reason="coords_not_cuda",
            )
            self._cached_pairs = pairs
            self._cached_coords = coords.detach().clone()
            self._cached_step = int(step) if step is not None else None
            return pairs
        box_value = _box_tensor(box if box is not None else self.config.box_size, coords=coords)
        if box_value is None:
            return self._blocked_pairs(
                coords,
                status="blocked_rust_hip_neighbor_provider_requires_box_size",
                reason="box_size_required",
            )
        backend = self._backend_or_none()
        if backend is None or not bool(getattr(backend, "has_neighbor_builder", lambda: False)()):
            return self._blocked_pairs(
                coords,
                status="blocked_rust_hip_neighbor_provider_unavailable",
                reason="backend_neighbor_builder_unavailable",
            )
        scalar_box = float(box_value.max().detach().cpu().item())
        effective_cutoff = float(self.config.cutoff) + float(self.config.skin)
        grid_dims = tuple(max(1, int(torch.floor(v.detach().cpu().to(torch.float64) / effective_cutoff).item())) for v in box_value)
        nb_idx, nb_dist, nb_mask = backend.build_neighbor_list(
            coords,
            scalar_box,
            effective_cutoff,
            int(self.config.max_neighbor_count),
            grid_dims,
            max_atoms_per_cell=int(self.config.max_atoms_per_cell),
        )
        pairs = neighbor_pairs_from_rust_hip_tensors(
            coords,
            nb_idx=nb_idx,
            nb_dist=nb_dist,
            nb_mask=nb_mask,
            config=self.config,
            box=box_value,
            backend_stats=getattr(backend, "last_neighbor_build_stats", {}),
        )
        self._cached_pairs = pairs
        self._cached_coords = coords.detach().clone()
        self._cached_step = int(step) if step is not None else None
        return pairs
