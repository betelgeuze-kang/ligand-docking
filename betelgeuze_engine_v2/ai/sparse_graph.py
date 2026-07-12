"""Bounded-degree graph contracts for the independent AI reference path.

This module operates only on compact edge lists. It never materializes an
``N x N`` distance, adjacency, attention, or projection matrix. Linear-work
claims apply only when maximum degree is bounded independently of atom count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.geometry.neighbors import MAX_COMPACT_NEIGHBORS
from betelgeuze_engine_v2.molecular.models import UnitCell


@dataclass(frozen=True)
class ComplexityMetadata:
    forward: str
    backward: str
    assumptions: tuple[str, ...]
    prohibited_dense_operations: tuple[str, ...]
    claim_scope: str

    def to_dict(self) -> dict[str, object]:
        return {
            "forward": self.forward,
            "backward": self.backward,
            "assumptions": list(self.assumptions),
            "prohibited_dense_operations": list(self.prohibited_dense_operations),
            "claim_scope": self.claim_scope,
        }


SPARSE_GRAPH_COMPLEXITY = ComplexityMetadata(
    forward="O(N + E)",
    backward="O(N + E)",
    assumptions=(
        "E <= K*N with K bounded independently of N",
        "feature width and layer count are fixed",
        "the caller supplies or builds a sparse neighbor list",
    ),
    prohibited_dense_operations=(
        "all-pairs distance matrix",
        "dense N-by-N adjacency",
        "full attention",
    ),
    claim_scope="graph adaptation and local message passing only",
)


def _coerce_cell_vectors(
    value: torch.Tensor | UnitCell | None,
    *,
    dtype: torch.dtype | None = None,
    device: torch.device | str | None = None,
) -> torch.Tensor | None:
    if value is None:
        return None
    vectors = value.vectors if isinstance(value, UnitCell) else value
    if not isinstance(vectors, torch.Tensor):
        raise TypeError("cell_vectors must be a torch.Tensor or UnitCell")
    if vectors.shape != (3, 3):
        raise ValueError("cell_vectors must have shape [3, 3]")
    if not vectors.is_floating_point():
        raise TypeError("cell_vectors must use a floating dtype")
    if not bool(torch.isfinite(vectors).all().item()):
        raise ValueError("cell_vectors must be finite")
    if dtype is not None or device is not None:
        vectors = vectors.to(dtype=dtype or vectors.dtype, device=device or vectors.device)
    return vectors


@dataclass(frozen=True)
class SparseNeighborGraph:
    """Directed sparse edges over a flattened ``[B, N]`` atom array.

    ``src`` is the neighbor sending a message and ``dst`` is the center atom.
    For periodic graphs, ``image_shifts`` contains integer lattice multiples
    added to ``r_src - r_dst``. ``cell_vectors`` stores three row lattice
    vectors, making minimum-image reconstruction differentiable in coordinates.
    """

    src: torch.Tensor
    dst: torch.Tensor
    batch: torch.Tensor
    batch_size: int
    atom_count: int
    max_neighbors: int
    source: str = "sparse_edges"
    pbc_enabled: bool = False
    periodic: tuple[bool, bool, bool] = (False, False, False)
    image_shifts: torch.Tensor | None = None
    cell_vectors: torch.Tensor | None = None

    def __post_init__(self) -> None:
        for name, value in (("src", self.src), ("dst", self.dst), ("batch", self.batch)):
            if value.ndim != 1:
                raise ValueError(f"{name} must be rank one")
            if value.dtype != torch.long:
                raise TypeError(f"{name} must use torch.long indices")
        if self.src.shape != self.dst.shape or self.src.shape != self.batch.shape:
            raise ValueError("src, dst, and batch must have equal shapes")
        if int(self.batch_size) < 1 or int(self.atom_count) < 1:
            raise ValueError("batch_size and atom_count must be positive")
        if int(self.max_neighbors) < 1 or int(self.max_neighbors) > MAX_COMPACT_NEIGHBORS:
            raise ValueError(
                f"max_neighbors must be in [1, {MAX_COMPACT_NEIGHBORS}]"
            )
        if len(self.periodic) != 3:
            raise ValueError("periodic must contain three axis flags")
        periodic = tuple(bool(value) for value in self.periodic)
        object.__setattr__(self, "periodic", periodic)
        pbc_enabled = bool(self.pbc_enabled or any(periodic))
        object.__setattr__(self, "pbc_enabled", pbc_enabled)

        if self.image_shifts is not None:
            if self.image_shifts.shape != (self.src.numel(), 3):
                raise ValueError("image_shifts must have shape [E, 3]")
            if self.image_shifts.dtype != torch.long:
                raise TypeError("image_shifts must use torch.long")
            if self.image_shifts.device != self.src.device:
                raise ValueError("image_shifts must share the edge-index device")
        if self.cell_vectors is not None:
            _coerce_cell_vectors(self.cell_vectors)
        if pbc_enabled and self.image_shifts is None:
            # The graph may still be retained for diagnostics, but an energy
            # consumer must fail closed until image geometry is supplied.
            pass
        if not pbc_enabled and self.image_shifts is not None:
            if bool((self.image_shifts != 0).any().item()):
                raise ValueError("non-periodic graphs cannot carry nonzero image shifts")

        total = int(self.batch_size) * int(self.atom_count)
        if self.src.numel():
            if bool((self.src < 0).any().item()) or bool((self.src >= total).any().item()):
                raise ValueError("src contains an out-of-range flattened atom index")
            if bool((self.dst < 0).any().item()) or bool((self.dst >= total).any().item()):
                raise ValueError("dst contains an out-of-range flattened atom index")
            if bool((self.batch < 0).any().item()) or bool((self.batch >= self.batch_size).any().item()):
                raise ValueError("batch contains an out-of-range sample index")
            expected = torch.div(self.dst, int(self.atom_count), rounding_mode="floor")
            if not bool(torch.equal(expected, self.batch)):
                raise ValueError("edge batch must agree with the destination index")
            src_batch = torch.div(self.src, int(self.atom_count), rounding_mode="floor")
            if not bool(torch.equal(src_batch, self.batch)):
                raise ValueError("cross-sample edges are not allowed")
            if bool((self.src == self.dst).any().item()):
                raise ValueError("self edges are not allowed in a molecular neighbor graph")
            directed_pairs = zip(
                self.src.detach().cpu().tolist(),
                self.dst.detach().cpu().tolist(),
            )
            if len(set(directed_pairs)) != int(self.src.numel()):
                raise ValueError("duplicate directed neighbor edges are not allowed")
            degree = torch.bincount(self.dst, minlength=total)
            if bool((degree > int(self.max_neighbors)).any().item()):
                raise ValueError("actual destination degree exceeds max_neighbors")

    @property
    def edge_count(self) -> int:
        return int(self.src.numel())

    @property
    def node_count(self) -> int:
        return int(self.batch_size) * int(self.atom_count)

    @property
    def periodic_geometry_ready(self) -> bool:
        return bool(
            not self.pbc_enabled
            or (self.image_shifts is not None and self.cell_vectors is not None)
        )

    @property
    def complexity(self) -> dict[str, object]:
        payload = SPARSE_GRAPH_COMPLEXITY.to_dict()
        payload.update(
            {
                "node_count": self.node_count,
                "edge_count": self.edge_count,
                "max_neighbors": int(self.max_neighbors),
                "source": self.source,
                "pbc_enabled": bool(self.pbc_enabled),
                "periodic": list(self.periodic),
                "periodic_geometry_ready": self.periodic_geometry_ready,
                "constructs_nxn": False,
            }
        )
        return payload

    def to(
        self,
        device: torch.device | str,
        *,
        dtype: torch.dtype | None = None,
    ) -> "SparseNeighborGraph":
        return SparseNeighborGraph(
            src=self.src.to(device=device),
            dst=self.dst.to(device=device),
            batch=self.batch.to(device=device),
            batch_size=self.batch_size,
            atom_count=self.atom_count,
            max_neighbors=self.max_neighbors,
            source=self.source,
            pbc_enabled=self.pbc_enabled,
            periodic=self.periodic,
            image_shifts=None if self.image_shifts is None else self.image_shifts.to(device=device),
            cell_vectors=None
            if self.cell_vectors is None
            else self.cell_vectors.to(device=device, dtype=dtype or self.cell_vectors.dtype),
        )

    @classmethod
    def from_edges(
        cls,
        src: torch.Tensor,
        dst: torch.Tensor,
        *,
        atom_count: int,
        batch_size: int = 1,
        batch: torch.Tensor | None = None,
        max_neighbors: int = 64,
        source: str = "provided_sparse_edges",
        pbc_enabled: bool = False,
        periodic: tuple[bool, bool, bool] = (False, False, False),
        image_shifts: torch.Tensor | None = None,
        cell_vectors: torch.Tensor | UnitCell | None = None,
    ) -> "SparseNeighborGraph":
        src = torch.as_tensor(src, dtype=torch.long)
        dst = torch.as_tensor(dst, dtype=torch.long, device=src.device)
        if batch is None:
            if int(batch_size) != 1:
                raise ValueError("batch indices are required when batch_size is greater than one")
            batch = torch.zeros_like(src)
        else:
            batch = torch.as_tensor(batch, dtype=torch.long, device=src.device)
        if image_shifts is not None:
            image_shifts = torch.as_tensor(
                image_shifts,
                dtype=torch.long,
                device=src.device,
            )
        return cls(
            src=src,
            dst=dst,
            batch=batch,
            batch_size=int(batch_size),
            atom_count=int(atom_count),
            max_neighbors=int(max_neighbors),
            source=source,
            pbc_enabled=bool(pbc_enabled),
            periodic=periodic,
            image_shifts=image_shifts,
            cell_vectors=_coerce_cell_vectors(cell_vectors),
        )

    @classmethod
    def from_neighbor_pairs(
        cls,
        pairs: Any,
        *,
        max_neighbors: int = 64,
        reject_dense_reference: bool = True,
        cell: UnitCell | torch.Tensor | None = None,
    ) -> "SparseNeighborGraph":
        """Adapt compact ``[B,N,K]`` neighbor rows without legacy imports."""

        idx = getattr(pairs, "idx", None)
        if idx is None:
            idx = getattr(pairs, "indices", None)
        mask = getattr(pairs, "mask", None)
        if not isinstance(idx, torch.Tensor) or not isinstance(mask, torch.Tensor):
            raise TypeError("neighbor pairs must expose tensor idx/indices and mask fields")
        if idx.ndim != 3 or mask.shape != idx.shape:
            raise ValueError("neighbor idx and mask must have matching [B, N, K] shapes")
        if idx.dtype != torch.long:
            idx = idx.to(dtype=torch.long)
        batch_size, atom_count, width = (int(value) for value in idx.shape)
        if width > int(max_neighbors):
            raise ValueError(
                f"neighbor width {width} exceeds bounded degree {int(max_neighbors)}"
            )
        diagnostics_object = getattr(pairs, "diagnostics", {})
        if isinstance(diagnostics_object, Mapping):
            diagnostics = diagnostics_object
        elif callable(getattr(diagnostics_object, "to_dict", None)):
            diagnostics = diagnostics_object.to_dict()
        else:
            diagnostics = {}
        if reject_dense_reference and bool(diagnostics.get("nxn_allocation_observed", False)):
            raise ValueError("dense reference neighbor pairs are not allowed in the v2 path")
        status = str(diagnostics.get("status", ""))
        if bool(diagnostics.get("overflow", False)) or status.startswith("blocked"):
            raise ValueError("overflowed or blocked neighbor pairs are not allowed in the v2 path")
        periodic_raw = diagnostics.get("periodic", (False, False, False))
        if not isinstance(periodic_raw, (tuple, list)) or len(periodic_raw) != 3:
            raise ValueError("neighbor diagnostics periodic field must contain three axis flags")
        periodic = tuple(bool(value) for value in periodic_raw)
        pbc_enabled = bool(diagnostics.get("pbc_enabled", False) or any(periodic))

        device = idx.device
        centers = torch.arange(atom_count, device=device, dtype=torch.long).view(1, atom_count, 1)
        centers = centers.expand(batch_size, atom_count, width)
        sample = torch.arange(batch_size, device=device, dtype=torch.long).view(batch_size, 1, 1)
        sample = sample.expand_as(centers)
        valid = mask.to(device=device, dtype=torch.bool)
        invalid_requested = valid & ((idx < 0) | (idx >= atom_count) | (idx == centers))
        if bool(invalid_requested.any().item()):
            raise ValueError("active neighbor slots contain an invalid or self atom index")
        offsets = sample * atom_count
        src = (idx + offsets)[valid]
        dst = (centers + offsets)[valid]
        edge_batch = sample[valid]

        compact_shifts = getattr(pairs, "image_shifts", None)
        edge_shifts = None
        if compact_shifts is not None:
            if not isinstance(compact_shifts, torch.Tensor) or compact_shifts.shape != (*idx.shape, 3):
                raise ValueError("compact image_shifts must have shape [B,N,K,3]")
            edge_shifts = compact_shifts.to(device=device, dtype=torch.long)[valid]

        return cls(
            src=src,
            dst=dst,
            batch=edge_batch,
            batch_size=batch_size,
            atom_count=atom_count,
            max_neighbors=int(max_neighbors),
            source=str(
                getattr(
                    pairs,
                    "source",
                    diagnostics.get("schema_version", pairs.__class__.__name__),
                )
            ),
            pbc_enabled=pbc_enabled,
            periodic=periodic,
            image_shifts=edge_shifts,
            cell_vectors=_coerce_cell_vectors(cell),
        )

    @classmethod
    def from_compact_neighbor_list(
        cls,
        neighbors: Any,
        *,
        max_neighbors: int = 64,
        cell: UnitCell | torch.Tensor | None = None,
    ) -> "SparseNeighborGraph":
        if not hasattr(neighbors, "indices"):
            raise TypeError("compact neighbor lists must expose indices")
        return cls.from_neighbor_pairs(
            neighbors,
            max_neighbors=max_neighbors,
            cell=cell,
        )


def coerce_sparse_graph(
    neighbors: SparseNeighborGraph | tuple[torch.Tensor, torch.Tensor] | Mapping[str, Any] | Any,
    *,
    batch_size: int,
    atom_count: int,
    max_neighbors: int,
    device: torch.device,
    dtype: torch.dtype,
) -> SparseNeighborGraph:
    """Normalize sparse edges, mappings, or compact neighbor rows."""

    if isinstance(neighbors, SparseNeighborGraph):
        graph = neighbors
    elif isinstance(neighbors, tuple) and len(neighbors) == 2:
        graph = SparseNeighborGraph.from_edges(
            neighbors[0],
            neighbors[1],
            atom_count=atom_count,
            batch_size=batch_size,
            max_neighbors=max_neighbors,
        )
    elif isinstance(neighbors, Mapping) and "src" in neighbors and "dst" in neighbors:
        graph = SparseNeighborGraph.from_edges(
            neighbors["src"],
            neighbors["dst"],
            atom_count=atom_count,
            batch_size=batch_size,
            batch=neighbors.get("batch"),
            max_neighbors=int(neighbors.get("max_neighbors", max_neighbors)),
            pbc_enabled=bool(neighbors.get("pbc_enabled", False)),
            periodic=tuple(neighbors.get("periodic", (False, False, False))),
            image_shifts=neighbors.get("image_shifts"),
            cell_vectors=neighbors.get("cell_vectors"),
        )
    else:
        graph = SparseNeighborGraph.from_neighbor_pairs(
            neighbors,
            max_neighbors=max_neighbors,
        )
    if graph.batch_size != int(batch_size) or graph.atom_count != int(atom_count):
        raise ValueError("neighbor graph shape does not match the coordinate batch")
    if graph.max_neighbors > int(max_neighbors):
        raise ValueError("neighbor graph exceeds the model bounded-degree contract")
    return graph.to(device, dtype=dtype)


def segment_sum(values: torch.Tensor, indices: torch.Tensor, size: int) -> torch.Tensor:
    """Sparse sum reduction implemented with ``index_add``."""

    if values.shape[0] != indices.shape[0]:
        raise ValueError("values and indices must agree on the edge dimension")
    output = values.new_zeros((int(size),) + tuple(values.shape[1:]))
    if indices.numel():
        output = output.index_add(0, indices, values)
    return output
