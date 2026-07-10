"""Sparse parity-aware local energy model for the independent-engine prototype.

The model is a CPU/GPU-portable PyTorch reference, not a calibrated molecular
potential.  It uses bounded-degree message passing and scalar/vector geometric
features.  It does not use a Transformer or pairwise attention.  Forces are
computed only as the exact reverse-mode derivative of the predicted scalar
energy.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import torch
from torch import nn

from betelgeuze_engine_v2.geometry.neighbors import MAX_COMPACT_NEIGHBORS

from betelgeuze_engine_v2.ai.sparse_graph import (
    ComplexityMetadata,
    SparseNeighborGraph,
    coerce_sparse_graph,
    segment_sum,
)


MAX_LOCAL_INPUT_FEATURES = 1024
MAX_LOCAL_HIDDEN_FEATURES = 512
MAX_LOCAL_RADIAL_FEATURES = 256
MAX_LOCAL_ENERGY_LAYERS = 16
MIN_LOCAL_EDGE_DISTANCE_ANGSTROM = 1.0e-8


LOCAL_ENERGY_COMPLEXITY = ComplexityMetadata(
    forward="O(L*(N*C^2 + E*C^2))",
    backward="O(L*(N*C^2 + E*C^2))",
    assumptions=(
        "E <= K*N and K is fixed independently of N",
        "layer count L, channel width C, and radial basis width are fixed",
        "neighbor construction itself obeys a sparse bounded-degree contract",
    ),
    prohibited_dense_operations=(
        "N-by-N distance matrix",
        "N-by-N learned weights",
        "full Hessian or Jacobian materialization",
    ),
    claim_scope="one local energy/force evaluation; not docking-search candidate count",
)


@dataclass(frozen=True)
class LocalEnergyConfig:
    input_features: int
    hidden_features: int = 48
    radial_features: int = 16
    layers: int = 3
    cutoff: float = 6.0
    max_neighbors: int = 64

    def __post_init__(self) -> None:
        if int(self.input_features) < 1 or int(self.input_features) > MAX_LOCAL_INPUT_FEATURES:
            raise ValueError(f"input_features must be in [1, {MAX_LOCAL_INPUT_FEATURES}]")
        if int(self.hidden_features) < 4 or int(self.hidden_features) > MAX_LOCAL_HIDDEN_FEATURES:
            raise ValueError(f"hidden_features must be in [4, {MAX_LOCAL_HIDDEN_FEATURES}]")
        if int(self.radial_features) < 2 or int(self.radial_features) > MAX_LOCAL_RADIAL_FEATURES:
            raise ValueError(f"radial_features must be in [2, {MAX_LOCAL_RADIAL_FEATURES}]")
        if int(self.layers) < 1 or int(self.layers) > MAX_LOCAL_ENERGY_LAYERS:
            raise ValueError(f"layers must be in [1, {MAX_LOCAL_ENERGY_LAYERS}]")
        if not math.isfinite(float(self.cutoff)) or float(self.cutoff) <= 0.0:
            raise ValueError("cutoff must be finite and positive")
        if int(self.max_neighbors) < 1 or int(self.max_neighbors) > MAX_COMPACT_NEIGHBORS:
            raise ValueError(
                f"max_neighbors must be between 1 and hard cap {MAX_COMPACT_NEIGHBORS}"
            )


@dataclass
class EnergyForcePrediction:
    energy: torch.Tensor
    forces: torch.Tensor
    parity_odd: torch.Tensor
    coordinates_used: torch.Tensor
    diagnostics: dict[str, object]


@dataclass
class LocalEnergyTerms:
    total: torch.Tensor
    per_atom: torch.Tensor
    parity_odd: torch.Tensor
    diagnostics: dict[str, object]


class _RadialBasis(nn.Module):
    def __init__(self, count: int, cutoff: float):
        super().__init__()
        self.cutoff = float(cutoff)
        centers = torch.linspace(0.0, self.cutoff, int(count))
        spacing = self.cutoff / max(int(count) - 1, 1)
        self.register_buffer("centers", centers)
        self.gamma = float(1.0 / max(spacing * spacing, 1.0e-12))

    def forward(self, distances: torch.Tensor) -> torch.Tensor:
        scaled = distances.unsqueeze(-1) - self.centers.to(
            device=distances.device, dtype=distances.dtype
        )
        basis = torch.exp(-self.gamma * scaled.square())
        inside = distances < self.cutoff
        envelope = 0.5 * (torch.cos(torch.pi * distances.clamp(max=self.cutoff) / self.cutoff) + 1.0)
        envelope = torch.where(inside, envelope, torch.zeros_like(envelope))
        return basis * envelope.unsqueeze(-1)


class _LocalScalarLayer(nn.Module):
    def __init__(self, hidden: int, radial: int):
        super().__init__()
        self.message = nn.Sequential(
            nn.Linear(2 * hidden + radial, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
        )
        self.update = nn.Sequential(
            nn.Linear(2 * hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
        )
        self.norm = nn.LayerNorm(hidden)

    def forward(
        self,
        node_state: torch.Tensor,
        src: torch.Tensor,
        dst: torch.Tensor,
        radial: torch.Tensor,
        envelope: torch.Tensor,
    ) -> torch.Tensor:
        if src.numel():
            edge_input = torch.cat((node_state[src], node_state[dst], radial), dim=-1)
            # Gate the entire learned message, including MLP biases and node
            # terms.  Gating only the radial channels would leave a finite
            # edge contribution that jumps when the neighbor list drops the
            # edge at the cutoff.
            messages = self.message(edge_input) * envelope.unsqueeze(-1)
            aggregate = segment_sum(messages, dst, node_state.shape[0])
            degree = segment_sum(
                envelope.unsqueeze(-1), dst, node_state.shape[0]
            )
            # A raw active-edge count jumps when an edge crosses the cutoff and
            # rescales every other message at that node.  A smooth weighted
            # normalization keeps both the aggregate and denominator
            # continuous as an envelope decays to zero.
            aggregate = aggregate / (1.0 + degree).sqrt()
        else:
            aggregate = torch.zeros_like(node_state)
        delta = self.update(torch.cat((node_state, aggregate), dim=-1))
        return self.norm(node_state + delta)


class ParityAwareLocalEnergyModel(nn.Module):
    """Local scalar-energy network with an explicit parity-odd descriptor.

    Three independently weighted equivariant local vectors are accumulated at
    every atom.  Their scalar triple product is invariant under proper E(3)
    motions and changes sign under reflection.  This lets the scalar-energy
    head distinguish mirror configurations while preserving translation and
    rotation invariance.  It is a parity-aware SE(3) construction rather than
    a claim of a complete irreducible-representation implementation.
    """

    scientific_status = "unvalidated_reference_architecture"
    uses_dense_pair_matrix = False
    uses_pairwise_attention = False
    force_definition = "negative_exact_autograd_gradient_of_scalar_energy"

    def __init__(self, config: LocalEnergyConfig):
        super().__init__()
        self.config = config
        hidden = int(config.hidden_features)
        radial = int(config.radial_features)
        self.radial_basis = _RadialBasis(radial, config.cutoff)
        self.node_embedding = nn.Sequential(
            nn.Linear(int(config.input_features), hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
        )
        self.layers = nn.ModuleList(
            [_LocalScalarLayer(hidden, radial) for _ in range(int(config.layers))]
        )
        self.vector_weights = nn.Sequential(
            nn.Linear(2 * hidden + radial, hidden),
            nn.SiLU(),
            nn.Linear(hidden, 3),
        )
        self.energy_head = nn.Sequential(
            nn.Linear(hidden + 2, hidden),
            nn.SiLU(),
            nn.Linear(hidden, max(hidden // 2, 4)),
            nn.SiLU(),
            nn.Linear(max(hidden // 2, 4), 1),
        )

    @property
    def complexity(self) -> dict[str, object]:
        payload = LOCAL_ENERGY_COMPLEXITY.to_dict()
        payload.update(
            {
                "layers": int(self.config.layers),
                "hidden_features": int(self.config.hidden_features),
                "radial_features": int(self.config.radial_features),
                "max_neighbors": int(self.config.max_neighbors),
                "hard_max_neighbors": MAX_COMPACT_NEIGHBORS,
                "hard_capacity_contract_enforced": True,
                "hard_hidden_features": MAX_LOCAL_HIDDEN_FEATURES,
                "hard_radial_features": MAX_LOCAL_RADIAL_FEATURES,
                "hard_layers": MAX_LOCAL_ENERGY_LAYERS,
                "constructs_nxn": False,
                "scientific_status": self.scientific_status,
            }
        )
        return payload

    def _validate_inputs(
        self,
        coordinates: torch.Tensor,
        atom_features: torch.Tensor,
    ) -> tuple[int, int]:
        if coordinates.ndim != 3 or coordinates.shape[-1] != 3:
            raise ValueError("coordinates must have shape [B, N, 3]")
        if atom_features.ndim != 3 or atom_features.shape[:2] != coordinates.shape[:2]:
            raise ValueError("atom_features must have shape [B, N, F]")
        if atom_features.shape[-1] != int(self.config.input_features):
            raise ValueError("atom feature width does not match the model configuration")
        if not coordinates.is_floating_point() or not atom_features.is_floating_point():
            raise TypeError("coordinates and atom_features must be floating point")
        if coordinates.dtype not in (torch.float32, torch.float64):
            raise TypeError("local energy supports float32 or float64 geometry only")
        if int(coordinates.shape[0]) < 1 or int(coordinates.shape[1]) < 1:
            raise ValueError("coordinates must contain at least one batch and one atom")
        if coordinates.device != atom_features.device:
            raise ValueError("coordinates and atom_features must be on the same device")
        if coordinates.dtype != atom_features.dtype:
            raise ValueError("coordinates and atom_features must use the same floating dtype")
        if not bool(torch.isfinite(coordinates).all().item()):
            raise ValueError("coordinates must be finite")
        if not bool(torch.isfinite(atom_features).all().item()):
            raise ValueError("atom_features must be finite")
        return int(coordinates.shape[0]), int(coordinates.shape[1])

    def energy_terms(
        self,
        coordinates: torch.Tensor,
        atom_features: torch.Tensor,
        neighbors: SparseNeighborGraph | tuple[torch.Tensor, torch.Tensor] | Mapping[str, Any] | Any,
    ) -> LocalEnergyTerms:
        batch_size, atom_count = self._validate_inputs(coordinates, atom_features)
        diagnostics_object = getattr(neighbors, "diagnostics", None)
        if isinstance(diagnostics_object, Mapping):
            neighbor_diagnostics = diagnostics_object
        elif callable(getattr(diagnostics_object, "to_dict", None)):
            neighbor_diagnostics = diagnostics_object.to_dict()
        else:
            neighbor_diagnostics = {}
        periodic = neighbor_diagnostics.get("periodic")
        pbc_enabled = bool(neighbor_diagnostics.get("pbc_enabled", False))
        if periodic is not None:
            pbc_enabled = pbc_enabled or any(bool(value) for value in periodic)
        if pbc_enabled:
            raise ValueError(
                "periodic sparse energy is blocked until minimum-image displacement "
                "recomputation is part of the exact coordinate-gradient path"
            )
        graph = coerce_sparse_graph(
            neighbors,
            batch_size=batch_size,
            atom_count=atom_count,
            max_neighbors=int(self.config.max_neighbors),
            device=coordinates.device,
        )
        if graph.pbc_enabled:
            raise ValueError(
                "periodic sparse energy is blocked until minimum-image displacement "
                "recomputation is part of the exact coordinate-gradient path"
            )
        flat_coordinates = coordinates.reshape(batch_size * atom_count, 3)
        flat_features = atom_features.reshape(batch_size * atom_count, atom_features.shape[-1])
        displacement = flat_coordinates[graph.src] - flat_coordinates[graph.dst]
        distance = torch.linalg.vector_norm(displacement, dim=-1)
        minimum_edge_distance = max(
            MIN_LOCAL_EDGE_DISTANCE_ANGSTROM,
            32.0 * float(torch.finfo(coordinates.dtype).eps),
        )
        if distance.numel() and bool((distance <= minimum_edge_distance).any().item()):
            raise ValueError(
                "sparse graph contains a coincident or numerically singular edge; "
                f"all edge distances must exceed {minimum_edge_distance:.3e} angstrom"
            )
        active = distance < float(self.config.cutoff)
        src = graph.src[active]
        dst = graph.dst[active]
        displacement = displacement[active]
        distance = distance[active]
        radial = self.radial_basis(distance)
        envelope = 0.5 * (
            torch.cos(torch.pi * distance / float(self.config.cutoff)) + 1.0
        )

        node_state = self.node_embedding(flat_features)
        for layer in self.layers:
            node_state = layer(node_state, src, dst, radial, envelope)

        if src.numel():
            edge_scalar = torch.cat(
                (node_state[src], node_state[dst], radial), dim=-1
            )
            branch_weights = self.vector_weights(edge_scalar) * envelope.unsqueeze(-1)
            unit = displacement / distance.clamp_min(1.0e-9).unsqueeze(-1)
            edge_vectors = unit.unsqueeze(-1) * branch_weights.unsqueeze(-2)
            local_vectors = segment_sum(edge_vectors, dst, graph.node_count)
            parity_odd = (
                torch.cross(local_vectors[:, :, 0], local_vectors[:, :, 1], dim=-1)
                * local_vectors[:, :, 2]
            ).sum(dim=-1)
        else:
            parity_odd = coordinates.new_zeros((graph.node_count,))

        head_input = torch.cat(
            (node_state, parity_odd.unsqueeze(-1), parity_odd.square().unsqueeze(-1)), dim=-1
        )
        per_atom = self.energy_head(head_input).squeeze(-1)
        node_batch = torch.arange(batch_size, device=coordinates.device).repeat_interleave(atom_count)
        total = segment_sum(per_atom.unsqueeze(-1), node_batch, batch_size).squeeze(-1)
        # Preserve an explicit zero-valued coordinate dependency.  With frozen
        # parameters and no active edges, the learned per-atom baseline is
        # otherwise constant and autograd has no output graph from which to
        # return the physically correct zero force.
        total = total + 0.0 * coordinates[:, 0, 0]
        if not bool(torch.isfinite(total).all().item()):
            raise FloatingPointError("local energy produced a non-finite scalar result")
        diagnostics = self.complexity
        diagnostics.update(
            {
                "sparse_graph": graph.complexity,
                "node_count": graph.node_count,
                "provided_edge_count": graph.edge_count,
                "active_edge_count": int(src.numel()),
                "neighbor_source": graph.source,
                "force_is_energy_gradient": True,
                "parity_odd_descriptor": "local_scalar_triple_product",
                "parity_even_descriptor": "local_scalar_triple_product_squared",
                "calibrated_potential": False,
            }
        )
        return LocalEnergyTerms(
            total=total,
            per_atom=per_atom.reshape(batch_size, atom_count),
            parity_odd=parity_odd.reshape(batch_size, atom_count),
            diagnostics=diagnostics,
        )

    def forward(
        self,
        coordinates: torch.Tensor,
        atom_features: torch.Tensor,
        neighbors: SparseNeighborGraph | tuple[torch.Tensor, torch.Tensor] | Mapping[str, Any] | Any,
    ) -> torch.Tensor:
        return self.energy_terms(coordinates, atom_features, neighbors).total

    def energy_and_forces(
        self,
        coordinates: torch.Tensor,
        atom_features: torch.Tensor,
        neighbors: SparseNeighborGraph | tuple[torch.Tensor, torch.Tensor] | Mapping[str, Any] | Any,
        *,
        create_graph: bool = False,
    ) -> EnergyForcePrediction:
        """Return scalar energy and its exact negative coordinate gradient."""

        coordinates_used = coordinates
        if not coordinates_used.requires_grad:
            coordinates_used = coordinates.detach().clone().requires_grad_(True)
        terms = self.energy_terms(coordinates_used, atom_features, neighbors)
        gradient = torch.autograd.grad(
            terms.total.sum(),
            coordinates_used,
            create_graph=bool(create_graph),
            retain_graph=bool(create_graph),
            allow_unused=True,
        )[0]
        if gradient is None:
            gradient = torch.zeros_like(coordinates_used)
        if not bool(torch.isfinite(gradient).all().item()):
            raise FloatingPointError("local energy produced a non-finite exact force gradient")
        diagnostics = dict(terms.diagnostics)
        diagnostics["autograd_create_graph"] = bool(create_graph)
        diagnostics["full_hessian_materialized"] = False
        return EnergyForcePrediction(
            energy=terms.total,
            forces=-gradient,
            parity_odd=terms.parity_odd,
            coordinates_used=coordinates_used,
            diagnostics=diagnostics,
        )
