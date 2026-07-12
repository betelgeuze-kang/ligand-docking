"""Recurrent sparse temporal graph state without sequence self-attention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import torch
from torch import nn

from betelgeuze_engine_v2.geometry.neighbors import MAX_COMPACT_NEIGHBORS

from betelgeuze_engine_v2.ai.sparse_graph import (
    ComplexityMetadata,
    SparseNeighborGraph,
    coerce_sparse_graph,
    segment_sum,
)


MAX_TEMPORAL_INPUT_FEATURES = 1024
MAX_TEMPORAL_HIDDEN_FEATURES = 512


TEMPORAL_COMPLEXITY = ComplexityMetadata(
    forward="O(T*(N*C^2 + E*C^2))",
    backward="O(W*(N*C^2 + E*C^2)) with truncated window W; O(T*...) otherwise",
    assumptions=(
        "E <= K*N with fixed maximum degree K",
        "hidden width C is fixed independently of N",
        "the recurrent history is represented by one fixed-width state per node",
    ),
    prohibited_dense_operations=(
        "T-by-T sequence mixing",
        "N-by-N spatial mixing",
        "full trajectory Jacobian materialization",
    ),
    claim_scope="temporal sparse-state propagation; trajectory length T remains explicit",
)


@dataclass
class TemporalRollout:
    states: torch.Tensor | None
    final_state: torch.Tensor
    diagnostics: dict[str, object]


class TemporalStateGNN(nn.Module):
    """One recurrent state per atom plus bounded-degree neighbor messages."""

    uses_pairwise_attention = False
    uses_transformer = False

    def __init__(self, input_features: int, hidden_features: int = 48, max_neighbors: int = 64):
        super().__init__()
        if min(int(input_features), int(hidden_features), int(max_neighbors)) < 1:
            raise ValueError("feature widths and max_neighbors must be positive")
        if int(input_features) > MAX_TEMPORAL_INPUT_FEATURES:
            raise ValueError(f"input_features exceeds hard cap {MAX_TEMPORAL_INPUT_FEATURES}")
        if int(hidden_features) > MAX_TEMPORAL_HIDDEN_FEATURES:
            raise ValueError(f"hidden_features exceeds hard cap {MAX_TEMPORAL_HIDDEN_FEATURES}")
        if int(max_neighbors) > MAX_COMPACT_NEIGHBORS:
            raise ValueError(f"max_neighbors exceeds hard cap {MAX_COMPACT_NEIGHBORS}")
        self.input_features = int(input_features)
        self.hidden_features = int(hidden_features)
        self.max_neighbors = int(max_neighbors)
        self.input_embedding = nn.Sequential(
            nn.Linear(self.input_features, self.hidden_features),
            nn.SiLU(),
        )
        self.message = nn.Sequential(
            nn.Linear(3 * self.hidden_features, self.hidden_features),
            nn.SiLU(),
            nn.Linear(self.hidden_features, self.hidden_features),
        )
        self.recurrent = nn.GRUCell(2 * self.hidden_features, self.hidden_features)
        self.output_norm = nn.LayerNorm(self.hidden_features)

    @property
    def complexity(self) -> dict[str, object]:
        payload = TEMPORAL_COMPLEXITY.to_dict()
        payload.update(
            {
                "hidden_features": self.hidden_features,
                "max_neighbors": self.max_neighbors,
                "uses_pairwise_attention": False,
                "uses_transformer": False,
            }
        )
        return payload

    def initial_state(self, node_features: torch.Tensor) -> torch.Tensor:
        if node_features.ndim != 3 or node_features.shape[-1] != self.input_features:
            raise ValueError("node_features must have shape [B, N, input_features]")
        return node_features.new_zeros(
            (node_features.shape[0], node_features.shape[1], self.hidden_features)
        )

    def forward(
        self,
        node_features: torch.Tensor,
        previous_state: torch.Tensor | None,
        neighbors: SparseNeighborGraph | tuple[torch.Tensor, torch.Tensor] | Mapping[str, Any] | Any,
    ) -> torch.Tensor:
        if node_features.ndim != 3 or node_features.shape[-1] != self.input_features:
            raise ValueError("node_features must have shape [B, N, input_features]")
        batch_size, atom_count = int(node_features.shape[0]), int(node_features.shape[1])
        if previous_state is None:
            previous_state = self.initial_state(node_features)
        if previous_state.shape != (batch_size, atom_count, self.hidden_features):
            raise ValueError("previous_state has the wrong shape")
        if previous_state.device != node_features.device:
            raise ValueError("previous_state and node_features must share a device")
        graph = coerce_sparse_graph(
            neighbors,
            batch_size=batch_size,
            atom_count=atom_count,
            max_neighbors=self.max_neighbors,
            device=node_features.device,
        )
        embedded = self.input_embedding(node_features).reshape(graph.node_count, self.hidden_features)
        flat_previous = previous_state.reshape(graph.node_count, self.hidden_features)
        if graph.edge_count:
            edge_input = torch.cat(
                (
                    flat_previous[graph.src],
                    flat_previous[graph.dst],
                    embedded[graph.src],
                ),
                dim=-1,
            )
            messages = self.message(edge_input)
            aggregate = segment_sum(messages, graph.dst, graph.node_count)
            degree = segment_sum(
                messages.new_ones((graph.edge_count, 1)), graph.dst, graph.node_count
            )
            aggregate = aggregate / degree.clamp_min(1.0).sqrt()
        else:
            aggregate = torch.zeros_like(flat_previous)
        recurrent_input = torch.cat((embedded, aggregate), dim=-1)
        next_state = self.recurrent(recurrent_input, flat_previous)
        next_state = self.output_norm(next_state)
        return next_state.reshape(batch_size, atom_count, self.hidden_features)

    def rollout(
        self,
        sequence: torch.Tensor,
        neighbors: (
            SparseNeighborGraph
            | tuple[torch.Tensor, torch.Tensor]
            | Mapping[str, Any]
            | Any
            | Sequence[SparseNeighborGraph | tuple[torch.Tensor, torch.Tensor] | Mapping[str, Any] | Any]
        ),
        *,
        initial_state: torch.Tensor | None = None,
        detach_interval: int | None = None,
        return_history: bool = True,
    ) -> TemporalRollout:
        if sequence.ndim != 4 or sequence.shape[-1] != self.input_features:
            raise ValueError("sequence must have shape [T, B, N, input_features]")
        if int(sequence.shape[0]) < 1:
            raise ValueError("sequence must contain at least one step")
        if detach_interval is not None and int(detach_interval) < 1:
            raise ValueError("detach_interval must be positive when provided")
        state = initial_state
        outputs: list[torch.Tensor] | None = [] if return_history else None
        graph_sequence: Sequence[Any] | None
        if isinstance(neighbors, Sequence) and not isinstance(neighbors, (tuple, SparseNeighborGraph)):
            graph_sequence = neighbors
            if len(graph_sequence) != int(sequence.shape[0]):
                raise ValueError("a dynamic neighbor sequence must have one graph per time step")
        else:
            graph_sequence = None
        for step in range(int(sequence.shape[0])):
            if detach_interval is not None and step > 0 and step % int(detach_interval) == 0:
                assert state is not None
                state = state.detach()
            graph = graph_sequence[step] if graph_sequence is not None else neighbors
            state = self.forward(sequence[step], state, graph)
            if outputs is not None:
                outputs.append(state)
        assert state is not None
        diagnostics = self.complexity
        diagnostics.update(
            {
                "time_steps": int(sequence.shape[0]),
                "truncated_bptt_window": int(detach_interval) if detach_interval is not None else None,
                "full_sequence_pair_matrix": False,
                "history_returned": bool(return_history),
                "retained_state_memory": (
                    "O(T*N*C) because every state is returned"
                    if return_history
                    else (
                        "O(W*N*C) autograd state with truncated window W"
                        if detach_interval is not None
                        else "O(T*N*C) autograd state without truncation"
                    )
                ),
                "backward_scope": (
                    "O(T*(N+E)) if a loss consumes all returned states"
                    if return_history
                    else (
                        "O(W*(N+E)) for final-state loss"
                        if detach_interval is not None
                        else "O(T*(N+E)) for final-state loss"
                    )
                ),
            }
        )
        history = torch.stack(outputs, dim=0) if outputs is not None else None
        return TemporalRollout(states=history, final_state=state, diagnostics=diagnostics)
