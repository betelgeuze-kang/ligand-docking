"""Linear-work tree propagation and differentiable torsion kinematics.

Topology is treated as static metadata.  Every tree edge is visited a bounded
number of times, so forward and reverse-mode work are O(N) for a molecular
forest.  This module does not enumerate every torsion's full descendant set.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn

from betelgeuze_engine_v2.ai.sparse_graph import ComplexityMetadata


MAX_TORSION_FEATURES = 1024
MAX_TORSION_HIDDEN_FEATURES = 512


TORSION_TREE_COMPLEXITY = ComplexityMetadata(
    forward="O(N*C^2) for a forest with N-#roots edges",
    backward="O(N*C^2) reverse-mode adjoint through the same tree",
    assumptions=(
        "the topology is an acyclic rooted forest",
        "hidden width C is fixed independently of atom count",
        "each parent edge is traversed a constant number of times",
    ),
    prohibited_dense_operations=(
        "per-torsion scan over every atom",
        "dense transitive-closure matrix",
        "full kinematic Jacobian materialization",
    ),
    claim_scope="tree message propagation and one forward-kinematic evaluation",
)


@dataclass
class KinematicResult:
    coordinates: torch.Tensor
    rotations: torch.Tensor
    topological_order: tuple[int, ...]
    diagnostics: dict[str, object]


def _forest_metadata(
    parent: torch.Tensor,
) -> tuple[
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
    tuple[tuple[int, ...], ...],
    tuple[int, ...],
]:
    if parent.ndim != 1 or parent.dtype != torch.long:
        raise ValueError("parent must be a rank-one torch.long tensor")
    values = [int(value) for value in parent.detach().cpu().tolist()]
    atom_count = len(values)
    if atom_count < 1:
        raise ValueError("parent cannot be empty")
    children: list[list[int]] = [[] for _ in range(atom_count)]
    roots: list[int] = []
    indegree = [0] * atom_count
    for child, ancestor in enumerate(values):
        if ancestor == -1:
            roots.append(child)
            continue
        if ancestor < 0 or ancestor >= atom_count or ancestor == child:
            raise ValueError("each parent must be -1 or a distinct valid atom index")
        children[ancestor].append(child)
        indegree[child] += 1
    if not roots:
        raise ValueError("the parent forest must contain at least one root")
    queue = list(roots)
    order: list[int] = []
    depth = [0] * atom_count
    cursor = 0
    while cursor < len(queue):
        node = queue[cursor]
        cursor += 1
        order.append(node)
        for child in children[node]:
            depth[child] = depth[node] + 1
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != atom_count:
        raise ValueError("parent contains a cycle")
    depth_buckets: list[list[int]] = [[] for _ in range(max(depth) + 1)]
    for node in order:
        depth_buckets[depth[node]].append(node)
    return (
        tuple(order),
        tuple(depth),
        tuple(roots),
        tuple(tuple(bucket) for bucket in depth_buckets),
        tuple(values),
    )


def axis_angle_matrix(axis: torch.Tensor, angle: torch.Tensor, *, epsilon: float = 1.0e-12) -> torch.Tensor:
    """Differentiable Rodrigues rotation for matching ``[..., 3]`` axes."""

    if axis.shape[-1] != 3 or angle.shape != axis.shape[:-1]:
        raise ValueError("axis must have shape [..., 3] and angle must have shape [...]")
    if not math.isfinite(float(epsilon)) or float(epsilon) <= 0.0:
        raise ValueError("epsilon must be finite and positive")
    if not axis.is_floating_point() or not angle.is_floating_point():
        raise TypeError("axis and angle must use floating dtypes")
    if axis.device != angle.device or axis.dtype != angle.dtype:
        raise ValueError("axis and angle must share a device and floating dtype")
    if not bool(torch.isfinite(axis).all().item() and torch.isfinite(angle).all().item()):
        raise ValueError("axis and angle must be finite")
    axis_norm = torch.linalg.vector_norm(axis, dim=-1, keepdim=True)
    zero_axis = axis_norm <= float(epsilon)
    if bool((zero_axis.squeeze(-1) & (angle.abs() > float(epsilon))).any().item()):
        raise ValueError("a nonzero rotation angle requires a nonzero axis")
    fallback = torch.zeros_like(axis)
    fallback[..., 2] = 1.0
    unit = torch.where(zero_axis, fallback, axis / axis_norm.clamp_min(float(epsilon)))
    x, y, z = unit.unbind(dim=-1)
    zero = torch.zeros_like(x)
    skew = torch.stack(
        (zero, -z, y, z, zero, -x, -y, x, zero), dim=-1
    ).reshape(axis.shape[:-1] + (3, 3))
    outer = unit.unsqueeze(-1) * unit.unsqueeze(-2)
    identity = torch.eye(3, dtype=axis.dtype, device=axis.device).expand_as(skew)
    cosine = torch.cos(angle).unsqueeze(-1).unsqueeze(-1)
    sine = torch.sin(angle).unsqueeze(-1).unsqueeze(-1)
    return cosine * identity + (1.0 - cosine) * outer + sine * skew


def torsion_tree_forward_kinematics(
    local_offsets: torch.Tensor,
    parent: torch.Tensor,
    torsion_angles: torch.Tensor,
    *,
    local_axes: torch.Tensor | None = None,
    root_positions: torch.Tensor | None = None,
) -> KinematicResult:
    """Build Cartesian coordinates with one recursive operation per tree edge.

    The torsion assigned to a child rotates that child's local frame and hence
    all of its descendants.  The child bond offset itself is expressed in the
    parent frame.  This is a generic differentiable tree primitive, not a full
    ring-closure or molecular internal-coordinate solver.
    """

    if local_offsets.ndim != 2 or local_offsets.shape[-1] != 3:
        raise ValueError("local_offsets must have shape [N, 3]")
    if torsion_angles.shape != local_offsets.shape[:1]:
        raise ValueError("torsion_angles must have shape [N]")
    if parent.shape != torsion_angles.shape:
        raise ValueError("parent must have shape [N]")
    if local_axes is None:
        local_axes = torch.zeros_like(local_offsets)
        local_axes[:, 2] = 1.0
    if local_axes.shape != local_offsets.shape:
        raise ValueError("local_axes must have shape [N, 3]")
    if local_axes.device != local_offsets.device or torsion_angles.device != local_offsets.device:
        raise ValueError("kinematic tensors must share a device")
    if (
        not local_offsets.is_floating_point()
        or not local_axes.is_floating_point()
        or not torsion_angles.is_floating_point()
    ):
        raise TypeError("kinematic coordinate, axis, and angle tensors must be floating point")
    if local_offsets.dtype != local_axes.dtype or local_offsets.dtype != torsion_angles.dtype:
        raise ValueError("kinematic coordinate, axis, and angle tensors must share a dtype")
    if not bool(
        torch.isfinite(local_offsets).all().item()
        and torch.isfinite(local_axes).all().item()
        and torch.isfinite(torsion_angles).all().item()
    ):
        raise ValueError("kinematic coordinate, axis, and angle tensors must be finite")

    order, _, roots, _, parent_values = _forest_metadata(parent)
    root_index = {node: index for index, node in enumerate(roots)}
    if root_positions is None:
        root_positions = local_offsets.new_zeros((len(roots), 3))
    elif root_positions.ndim == 1 and len(roots) == 1 and root_positions.shape[0] == 3:
        root_positions = root_positions.unsqueeze(0)
    if root_positions.shape != (len(roots), 3):
        raise ValueError("root_positions must have shape [number_of_roots, 3]")
    if root_positions.device != local_offsets.device or root_positions.dtype != local_offsets.dtype:
        raise ValueError("root_positions must share the coordinate device and dtype")
    if not bool(torch.isfinite(root_positions).all().item()):
        raise ValueError("root_positions must be finite")

    relative_rotations = axis_angle_matrix(local_axes, torsion_angles)
    positions: list[torch.Tensor | None] = [None] * int(local_offsets.shape[0])
    rotations: list[torch.Tensor | None] = [None] * int(local_offsets.shape[0])
    identity = torch.eye(3, dtype=local_offsets.dtype, device=local_offsets.device)
    for node in order:
        ancestor = parent_values[node]
        if ancestor == -1:
            positions[node] = root_positions[root_index[node]]
            rotations[node] = relative_rotations[node]
        else:
            parent_position = positions[ancestor]
            parent_rotation = rotations[ancestor]
            assert parent_position is not None and parent_rotation is not None
            positions[node] = parent_position + parent_rotation @ local_offsets[node]
            rotations[node] = parent_rotation @ relative_rotations[node]
    coordinates = torch.stack([value for value in positions if value is not None], dim=0)
    global_rotations = torch.stack(
        [value if value is not None else identity for value in rotations], dim=0
    )
    diagnostics = TORSION_TREE_COMPLEXITY.to_dict()
    diagnostics.update(
        {
            "atom_count": int(local_offsets.shape[0]),
            "root_count": len(roots),
            "constructs_full_jacobian": False,
            "supports_ring_closure": False,
        }
    )
    return KinematicResult(
        coordinates=coordinates,
        rotations=global_rotations,
        topological_order=order,
        diagnostics=diagnostics,
    )


class TorsionTopologyGNN(nn.Module):
    """Bidirectional tree message passing over a static molecular forest."""

    uses_pairwise_attention = False
    uses_transformer = False

    def __init__(self, input_features: int, hidden_features: int = 48, output_features: int = 48):
        super().__init__()
        if min(int(input_features), int(hidden_features), int(output_features)) < 1:
            raise ValueError("feature widths must be positive")
        if int(input_features) > MAX_TORSION_FEATURES or int(output_features) > MAX_TORSION_FEATURES:
            raise ValueError(f"input/output features exceed hard cap {MAX_TORSION_FEATURES}")
        if int(hidden_features) > MAX_TORSION_HIDDEN_FEATURES:
            raise ValueError(f"hidden_features exceeds hard cap {MAX_TORSION_HIDDEN_FEATURES}")
        self.input_features = int(input_features)
        self.hidden_features = int(hidden_features)
        self.output_features = int(output_features)
        self.embedding = nn.Sequential(
            nn.Linear(self.input_features, self.hidden_features),
            nn.SiLU(),
        )
        self.up_message = nn.Sequential(
            nn.Linear(self.hidden_features, self.hidden_features),
            nn.SiLU(),
            nn.Linear(self.hidden_features, self.hidden_features),
        )
        self.down_message = nn.Sequential(
            nn.Linear(2 * self.hidden_features, self.hidden_features),
            nn.SiLU(),
            nn.Linear(self.hidden_features, self.hidden_features),
        )
        self.output = nn.Sequential(
            nn.LayerNorm(self.hidden_features),
            nn.Linear(self.hidden_features, self.output_features),
        )

    @property
    def complexity(self) -> dict[str, object]:
        payload = TORSION_TREE_COMPLEXITY.to_dict()
        payload.update(
            {
                "hidden_features": self.hidden_features,
                "constructs_transitive_closure": False,
                "uses_pairwise_attention": False,
            }
        )
        return payload

    def forward(self, node_features: torch.Tensor, parent: torch.Tensor) -> torch.Tensor:
        squeeze = False
        if node_features.ndim == 2:
            node_features = node_features.unsqueeze(0)
            squeeze = True
        if node_features.ndim != 3 or node_features.shape[-1] != self.input_features:
            raise ValueError("node_features must have shape [B, N, input_features]")
        if parent.shape != node_features.shape[1:2]:
            raise ValueError("parent must have shape [N]")
        order, depth, roots, depth_buckets, parent_values = _forest_metadata(parent)
        del depth, roots, depth_buckets
        embedded = self.embedding(node_features)

        # Lists avoid allocating or copying a full [B, N, C] tensor once per
        # tree depth.  Each edge creates only fixed-width [B, C] tensors.
        upward = [embedded[:, node, :] for node in range(int(node_features.shape[1]))]
        for node in reversed(order):
            ancestor = parent_values[node]
            if ancestor >= 0:
                upward[ancestor] = upward[ancestor] + self.up_message(upward[node])

        context = list(upward)
        for node in order:
            ancestor = parent_values[node]
            if ancestor >= 0:
                message_input = torch.cat((context[ancestor], upward[node]), dim=-1)
                context[node] = context[node] + self.down_message(message_input)
        result = self.output(torch.stack(context, dim=1))
        return result.squeeze(0) if squeeze else result
