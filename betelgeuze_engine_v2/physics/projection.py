"""Matrix-free orthogonal projections for force and gradient constraints.

Only fixed-rank global bases and three-dimensional rigid-body systems are
solved.  No ``N x N`` projector, full molecular Jacobian, Hessian, or dense
constraint pseudoinverse is constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch


MAX_FIXED_PROJECTION_RANK = 16


@dataclass(frozen=True)
class ProjectionDiagnostics:
    projection: str
    atom_count: int
    rank: int
    constructs_nxn: bool
    forward_complexity: str
    backward_complexity: str
    assumptions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "projection": self.projection,
            "atom_count": int(self.atom_count),
            "rank": int(self.rank),
            "constructs_nxn": bool(self.constructs_nxn),
            "forward_complexity": self.forward_complexity,
            "backward_complexity": self.backward_complexity,
            "assumptions": list(self.assumptions),
        }


class ProjectionRankError(ValueError):
    """An exact differentiable projector cannot be formed from this basis."""


def _validate_rcond(rcond: float) -> float:
    value = float(rcond)
    if not math.isfinite(value) or value <= 0.0 or value >= 1.0:
        raise ValueError("rcond must be finite and strictly between zero and one")
    return value


def _full_rank_symmetric_solve(
    matrix: torch.Tensor,
    right_hand_side: torch.Tensor,
    *,
    rcond: float,
    context: str,
) -> torch.Tensor:
    """Solve a small positive-definite system behind a detached rank gate.

    The differentiable path deliberately avoids eigenvectors and singular
    vectors: their derivatives are undefined at repeated eigenvalues even for
    a valid identity Gram matrix.  Rank-deficient bases sit on a projector
    rank-change boundary, so the exact-gradient API rejects them.
    """

    threshold = max(
        _validate_rcond(rcond),
        32.0 * torch.finfo(matrix.dtype).eps,
    )
    symmetric = 0.5 * (matrix + matrix.transpose(-1, -2))
    eigenvalues = torch.linalg.eigvalsh(symmetric.detach())
    largest = eigenvalues.amax(dim=-1)
    smallest = eigenvalues.amin(dim=-1)
    finite = torch.isfinite(eigenvalues).all(dim=-1)
    full_rank = finite & (largest > 0.0) & (smallest > threshold * largest)
    if not bool(full_rank.all().detach().cpu().item()):
        bad_rows = torch.nonzero(~full_rank, as_tuple=True)[0].detach().cpu().tolist()
        raise ProjectionRankError(
            f"{context} requires a finite full-rank basis/system; invalid batch rows {bad_rows}"
        )
    return torch.linalg.solve(symmetric, right_hand_side)


def _as_batched_projection_inputs(
    values: torch.Tensor,
    basis: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, bool]:
    if values.ndim == 2:
        if values.shape[-1] != 3 or basis.ndim != 3 or tuple(basis.shape[:-1]) != tuple(values.shape):
            raise ValueError("unbatched projection requires values [N, 3] and basis [N, 3, r]")
        values = values.unsqueeze(0)
        basis = basis.unsqueeze(0)
        return values, basis, True
    if values.ndim == 3:
        if values.shape[-1] != 3 or basis.ndim != 4 or tuple(basis.shape[:-1]) != tuple(values.shape):
            raise ValueError("batched projection requires values [B, N, 3] and basis [B, N, 3, r]")
        return values, basis, False
    raise ValueError("projection values must have shape [N, 3] or [B, N, 3]")


def fixed_rank_orthogonal_complement(
    values: torch.Tensor,
    basis: torch.Tensor,
    *,
    rcond: float = 1.0e-10,
    max_rank: int = 16,
    return_diagnostics: bool = False,
) -> torch.Tensor | tuple[torch.Tensor, ProjectionDiagnostics]:
    """Remove the span of a small, full-column-rank non-orthonormal basis.

    If ``B`` is the flattened basis, this computes
    ``x - B (B.T B)^-1 B.T x`` by associative products.  The dense projector
    ``B B.T`` is never formed.  Rank is explicitly capped so the operation is
    O(N) when rank is independent of atom count.
    """

    if not values.is_floating_point() or not basis.is_floating_point():
        raise TypeError("projection inputs must be floating point tensors")
    if values.dtype not in (torch.float32, torch.float64) or basis.dtype not in (
        torch.float32,
        torch.float64,
    ):
        raise TypeError("exact projection supports torch.float32 or torch.float64")
    if values.device != basis.device or values.dtype != basis.dtype:
        raise ValueError("values and basis must share a device and floating dtype")
    values_b, basis_b, squeeze = _as_batched_projection_inputs(values, basis)
    rank = int(basis_b.shape[-1])
    if int(max_rank) < 1 or int(max_rank) > MAX_FIXED_PROJECTION_RANK:
        raise ValueError(
            f"max_rank must be between 1 and the hard cap {MAX_FIXED_PROJECTION_RANK}"
        )
    if rank < 1 or rank > int(max_rank):
        raise ValueError(f"projection rank must be between 1 and {int(max_rank)}")
    if values_b.shape[0] != basis_b.shape[0]:
        raise ValueError("values and basis batch sizes must match")
    flat_values = values_b.reshape(values_b.shape[0], -1, 1)
    flat_basis = basis_b.reshape(basis_b.shape[0], -1, rank)
    gram = flat_basis.transpose(-1, -2) @ flat_basis
    coefficients = _full_rank_symmetric_solve(
        gram,
        flat_basis.transpose(-1, -2) @ flat_values,
        rcond=float(rcond),
        context="fixed-rank orthogonal projection",
    )
    projected = (flat_values - flat_basis @ coefficients).reshape_as(values_b)
    if squeeze:
        projected = projected.squeeze(0)
    if not return_diagnostics:
        return projected
    atom_count = int(values.shape[-2]) if values.ndim >= 2 else int(values.numel())
    diagnostics = ProjectionDiagnostics(
        projection="fixed_rank_orthogonal_complement",
        atom_count=atom_count,
        rank=rank,
        constructs_nxn=False,
        forward_complexity="O(N*r^2 + r^3)",
        backward_complexity="O(N*r^2 + r^3)",
        assumptions=("rank r is fixed independently of N", "basis is supplied without an N-by-N expansion"),
    )
    return projected, diagnostics


def fixed_rank_projection_adjoint(
    cotangent: torch.Tensor,
    basis: torch.Tensor,
    *,
    rcond: float = 1.0e-10,
    max_rank: int = 16,
) -> torch.Tensor:
    """Adjoint with respect to values for a fixed basis.

    An orthogonal projector is symmetric, so its VJP for ``values`` is the
    same matrix-free operation.  If ``basis`` itself depends on coordinates,
    callers must retain the normal autograd graph to include ``dB/dx``; this
    helper intentionally describes only the fixed-basis adjoint.
    """

    result = fixed_rank_orthogonal_complement(
        cotangent,
        basis,
        rcond=rcond,
        max_rank=max_rank,
    )
    assert isinstance(result, torch.Tensor)
    return result


def local_normal_projection(
    vectors: torch.Tensor,
    normals: torch.Tensor,
    *,
    keep_tangent: bool = True,
    epsilon: float = 1.0e-12,
) -> torch.Tensor:
    """Apply independent rank-one projections to local three-vectors."""

    if vectors.shape != normals.shape or vectors.shape[-1] != 3:
        raise ValueError("vectors and normals must have matching [..., 3] shapes")
    if not math.isfinite(float(epsilon)) or float(epsilon) <= 0.0:
        raise ValueError("epsilon must be finite and positive")
    norm_squared = (normals * normals).sum(dim=-1, keepdim=True).clamp_min(float(epsilon))
    normal_component = normals * ((vectors * normals).sum(dim=-1, keepdim=True) / norm_squared)
    return vectors - normal_component if keep_tangent else normal_component


def project_rigid_body_forces(
    coordinates: torch.Tensor,
    forces: torch.Tensor,
    *,
    atom_mask: torch.Tensor | None = None,
    rcond: float = 1.0e-10,
    return_diagnostics: bool = False,
) -> torch.Tensor | tuple[torch.Tensor, ProjectionDiagnostics]:
    """Remove net translation and rotation from batched Cartesian forces.

    The rotational least-squares system is only ``3 x 3`` per sample.  This is
    a geometric force projection, not a claim that the projected field remains
    conservative.  Energy-derived forces should normally be kept unprojected;
    use this at an explicit constraint boundary.
    """

    squeeze = False
    if coordinates.ndim == 2 and forces.ndim == 2:
        coordinates = coordinates.unsqueeze(0)
        forces = forces.unsqueeze(0)
        if atom_mask is not None and atom_mask.ndim == 1:
            atom_mask = atom_mask.unsqueeze(0)
        squeeze = True
    if coordinates.shape != forces.shape or coordinates.ndim != 3 or coordinates.shape[-1] != 3:
        raise ValueError("coordinates and forces must have matching [B, N, 3] shapes")
    if not coordinates.is_floating_point() or not forces.is_floating_point():
        raise TypeError("coordinates and forces must use floating dtypes")
    if coordinates.dtype not in (torch.float32, torch.float64) or forces.dtype not in (
        torch.float32,
        torch.float64,
    ):
        raise TypeError("rigid projection supports torch.float32 or torch.float64")
    if coordinates.device != forces.device or coordinates.dtype != forces.dtype:
        raise ValueError("coordinates and forces must share a device and floating dtype")
    if atom_mask is None:
        weights = torch.ones_like(coordinates[..., :1])
    else:
        if atom_mask.shape != coordinates.shape[:2]:
            raise ValueError("atom_mask must have shape [B, N]")
        if atom_mask.dtype != torch.bool:
            raise TypeError("atom_mask must be boolean")
        weights = atom_mask.to(device=coordinates.device, dtype=coordinates.dtype).unsqueeze(-1)
    count = weights.sum(dim=1, keepdim=True)
    if bool((count <= 0).any().item()):
        raise ValueError("each sample must contain at least one active atom")

    centroid = (coordinates * weights).sum(dim=1, keepdim=True) / count
    relative = (coordinates - centroid) * weights
    mean_force = (forces * weights).sum(dim=1, keepdim=True) / count
    translated = (forces - mean_force) * weights

    torque = torch.cross(relative, translated, dim=-1).sum(dim=1)
    radius_squared = (relative * relative).sum(dim=-1)
    identity = torch.eye(3, dtype=coordinates.dtype, device=coordinates.device).expand(
        coordinates.shape[0], 3, 3
    )
    inertia = radius_squared.sum(dim=1).view(-1, 1, 1) * identity
    inertia = inertia - torch.einsum("bni,bnj->bij", relative, relative)
    angular_coefficient = _full_rank_symmetric_solve(
        inertia,
        torque.unsqueeze(-1),
        rcond=float(rcond),
        context="rigid-body rotational projection",
    ).squeeze(-1)
    rotational_component = torch.cross(
        angular_coefficient.unsqueeze(1).expand_as(relative),
        relative,
        dim=-1,
    )
    projected = (translated - rotational_component) * weights
    if squeeze:
        projected = projected.squeeze(0)
    if not return_diagnostics:
        return projected
    diagnostics = ProjectionDiagnostics(
        projection="rigid_translation_rotation",
        atom_count=int(coordinates.shape[1]),
        rank=6,
        constructs_nxn=False,
        forward_complexity="O(N) plus one 3-by-3 solve",
        backward_complexity="O(N) plus the adjoint of one 3-by-3 solve",
        assumptions=("Cartesian dimension is fixed at three", "active coordinates span three rotational modes"),
    )
    return projected, diagnostics
