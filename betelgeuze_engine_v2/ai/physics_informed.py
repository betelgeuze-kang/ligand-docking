"""Physics-informed training terms and fail-closed evaluation gates.

These losses constrain an energy model; they are not a PDE solver and do not
turn an uncalibrated model into a validated force field.  Force supervision of
an energy-gradient model may require reverse-over-reverse products during
training, but this module never materializes a full Hessian.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch
import torch.nn.functional as functional


@dataclass(frozen=True)
class PhysicsLossWeights:
    energy: float = 1.0
    force: float = 1.0
    net_force: float = 0.05
    net_torque: float = 0.05
    equivariance: float = 0.1
    rollout: float = 0.0

    def __post_init__(self) -> None:
        if any(
            not math.isfinite(float(value)) or float(value) < 0.0
            for value in self.__dict__.values()
        ):
            raise ValueError("physics loss weights must be finite and non-negative")


@dataclass
class PhysicsObjectiveResult:
    total: torch.Tensor
    terms: dict[str, torch.Tensor]
    diagnostics: dict[str, object]


def _centered_torque(coordinates: torch.Tensor, forces: torch.Tensor) -> torch.Tensor:
    if coordinates.shape != forces.shape or coordinates.ndim != 3 or coordinates.shape[-1] != 3:
        raise ValueError("coordinates and forces must have matching [B, N, 3] shapes")
    relative = coordinates - coordinates.mean(dim=1, keepdim=True)
    return torch.cross(relative, forces, dim=-1).sum(dim=1)


def _validate_energy_force_shapes(
    energy: torch.Tensor,
    forces: torch.Tensor,
    coordinates: torch.Tensor,
) -> None:
    if coordinates.ndim != 3 or coordinates.shape[-1] != 3:
        raise ValueError("coordinates must have shape [B, N, 3]")
    if int(coordinates.shape[0]) < 1 or int(coordinates.shape[1]) < 1:
        raise ValueError("physics objectives and gates require a nonempty batch and atom set")
    if energy.ndim != 1 or energy.shape[0] != coordinates.shape[0]:
        raise ValueError("energy must have shape [B]")
    if forces.shape != coordinates.shape:
        raise ValueError("forces must match coordinates")
    if not energy.is_floating_point() or not forces.is_floating_point() or not coordinates.is_floating_point():
        raise TypeError("energy, forces, and coordinates must be floating point")
    if energy.device != coordinates.device or forces.device != coordinates.device:
        raise ValueError("energy, forces, and coordinates must share a device")


def physics_informed_objective(
    predicted_energy: torch.Tensor,
    predicted_forces: torch.Tensor,
    *,
    coordinates: torch.Tensor,
    reference_energy: torch.Tensor | None = None,
    reference_forces: torch.Tensor | None = None,
    equivariance_residual: torch.Tensor | None = None,
    rollout_residual: torch.Tensor | None = None,
    weights: PhysicsLossWeights | None = None,
) -> PhysicsObjectiveResult:
    """Combine supervised and symmetry/conservation residuals.

    ``predicted_forces`` should normally come from ``-grad(E)`` with
    ``create_graph=True``.  The caller can then backpropagate this scalar loss
    without asking for a dense Hessian; autograd computes only the required
    vector-Jacobian products.
    """

    weights = weights or PhysicsLossWeights()
    _validate_energy_force_shapes(predicted_energy, predicted_forces, coordinates)
    terms: dict[str, torch.Tensor] = {}
    zero = predicted_energy.sum() * 0.0
    if reference_energy is not None:
        if reference_energy.shape != predicted_energy.shape:
            raise ValueError("reference_energy must match predicted_energy")
        terms["energy"] = functional.mse_loss(predicted_energy, reference_energy)
    else:
        terms["energy"] = zero
    if reference_forces is not None:
        if reference_forces.shape != predicted_forces.shape:
            raise ValueError("reference_forces must match predicted_forces")
        terms["force"] = functional.mse_loss(predicted_forces, reference_forces)
    else:
        terms["force"] = zero

    net_force = predicted_forces.sum(dim=1)
    net_torque = _centered_torque(coordinates, predicted_forces)
    terms["net_force"] = net_force.square().mean()
    terms["net_torque"] = net_torque.square().mean()
    terms["equivariance"] = (
        equivariance_residual.square().mean() if equivariance_residual is not None else zero
    )
    terms["rollout"] = rollout_residual.square().mean() if rollout_residual is not None else zero
    total = (
        float(weights.energy) * terms["energy"]
        + float(weights.force) * terms["force"]
        + float(weights.net_force) * terms["net_force"]
        + float(weights.net_torque) * terms["net_torque"]
        + float(weights.equivariance) * terms["equivariance"]
        + float(weights.rollout) * terms["rollout"]
    )
    return PhysicsObjectiveResult(
        total=total,
        terms=terms,
        diagnostics={
            "scientific_status": "training_constraint_only",
            "full_hessian_materialized": False,
            "force_training_derivative": "autograd_vector_jacobian_products_only",
            "claim": "loss construction does not establish force-field accuracy",
        },
    )


@dataclass(frozen=True)
class PhysicsGateThresholds:
    max_net_force: float = 1.0e-5
    max_net_torque: float = 1.0e-5
    max_finite_difference_error: float = 1.0e-4
    max_equivariance_error: float = 1.0e-5

    def __post_init__(self) -> None:
        if any(
            not math.isfinite(float(value)) or float(value) < 0.0
            for value in self.__dict__.values()
        ):
            raise ValueError("physics gate thresholds must be finite and non-negative")


@dataclass(frozen=True)
class PhysicsGateResult:
    passed: bool
    status: str
    metrics: dict[str, float | bool | None]
    blockers: tuple[str, ...]
    claim_scope: str = "architecture-level physics consistency only"


def evaluate_physics_gates(
    energy: torch.Tensor,
    forces: torch.Tensor,
    coordinates: torch.Tensor,
    *,
    finite_difference_error: float | torch.Tensor | None = None,
    equivariance_error: float | torch.Tensor | None = None,
    applicability_in_domain: bool = False,
    thresholds: PhysicsGateThresholds | None = None,
) -> PhysicsGateResult:
    """Fail closed when required consistency evidence is missing or invalid."""

    thresholds = thresholds or PhysicsGateThresholds()
    _validate_energy_force_shapes(energy, forces, coordinates)
    finite = bool(
        torch.isfinite(energy).all().item()
        and torch.isfinite(forces).all().item()
        and torch.isfinite(coordinates).all().item()
    )
    if finite:
        net_force = float(torch.linalg.vector_norm(forces.sum(dim=1), dim=-1).amax().detach().cpu().item())
        torque = _centered_torque(coordinates, forces)
        net_torque = float(torch.linalg.vector_norm(torque, dim=-1).amax().detach().cpu().item())
    else:
        net_force = float("inf")
        net_torque = float("inf")

    def optional_float(value: float | torch.Tensor | None) -> float | None:
        if value is None:
            return None
        tensor = torch.as_tensor(value)
        return float(tensor.detach().abs().amax().cpu().item())

    fd_error = optional_float(finite_difference_error)
    equiv_error = optional_float(equivariance_error)
    blockers: list[str] = []
    if not finite:
        blockers.append("nonfinite_energy_or_force")
    if net_force > float(thresholds.max_net_force):
        blockers.append("net_force_threshold_exceeded")
    if net_torque > float(thresholds.max_net_torque):
        blockers.append("net_torque_threshold_exceeded")
    if fd_error is None:
        blockers.append("finite_difference_evidence_missing")
    elif not math.isfinite(fd_error):
        blockers.append("finite_difference_evidence_nonfinite")
    elif fd_error > float(thresholds.max_finite_difference_error):
        blockers.append("finite_difference_threshold_exceeded")
    if equiv_error is None:
        blockers.append("equivariance_evidence_missing")
    elif not math.isfinite(equiv_error):
        blockers.append("equivariance_evidence_nonfinite")
    elif equiv_error > float(thresholds.max_equivariance_error):
        blockers.append("equivariance_threshold_exceeded")
    if not bool(applicability_in_domain):
        blockers.append("applicability_domain_unproven")
    passed = not blockers
    return PhysicsGateResult(
        passed=passed,
        status="architecture_consistency_passed" if passed else "blocked",
        metrics={
            "finite": finite,
            "max_net_force": net_force,
            "max_net_torque": net_torque,
            "finite_difference_error": fd_error,
            "equivariance_error": equiv_error,
            "applicability_in_domain": bool(applicability_in_domain),
        },
        blockers=tuple(blockers),
    )
