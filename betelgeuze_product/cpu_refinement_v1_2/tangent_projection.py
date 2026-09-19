"""Call-local fixed geometry for the unchanged equal-weight Jacobi projection.

Directions are rebuilt for EVERY invocation. Coordinates do not change during
one projection, so only redundant vector/normalization work is removed. Update
order, relaxation, stopping tolerance and sweep budget are unchanged. There is
no cross-coordinate cache, hidden extra iteration, direct-solver fallback or
modification of the historical engine. Finite CPU binary64 inputs are required.
"""
from __future__ import annotations

import math

import torch

from betelgeuze_engine_v2.physics.reference_constrained_minimization import (
    ReferenceConstrainedMinimizationError, _constraint_vector,
)
from .provenance import ResearchError, finite, integer

IMPLEMENTATION_ID = "call_local_constraint_geometry_jacobi/1.0.0"


def project_tangent_forces(system, coordinates, forces, parameters, config):
    """Return (forces, max force, constraint residual, sweeps, converged)."""
    for value in (coordinates, forces):
        if (not isinstance(value, torch.Tensor) or value.device.type != "cpu"
                or value.dtype != torch.float64 or tuple(value.shape) != (1, system.atom_count, 3)
                or not bool(torch.isfinite(value).all())):
            raise ResearchError("finite single-model CPU binary64 projection inputs required")
    maximum_sweeps = integer(config.force_projection_max_sweeps, 1, 1000)
    tolerance = finite(config.force_projection_tolerance_kcal_per_mol_angstrom)
    if tolerance <= 0:
        raise ResearchError("positive tangent projection tolerance required")
    projected = forces.detach().clone()
    if not parameters.constraints:
        return projected, float(torch.linalg.vector_norm(projected[0], dim=-1).max()), 0., 0, True
    degrees = [0] * system.atom_count
    geometry = []
    for constraint in parameters.constraints:
        i, j = constraint.atom_i, constraint.atom_j
        integer(i, 0, system.atom_count - 1)
        integer(j, 0, system.atom_count - 1)
        degrees[i] += 1
        degrees[j] += 1
        vector = _constraint_vector(coordinates, system, i, j)
        distance = float(torch.linalg.vector_norm(vector).item())
        if distance <= 1.e-12:
            raise ReferenceConstrainedMinimizationError(
                "constraint tangent is undefined at zero pair distance")
        if not math.isfinite(distance):
            raise FloatingPointError("nonfinite constraint vector length")
        geometry.append((i, j, vector / distance))
    relaxation = float(max(degrees, default=1))
    for sweep in range(1, maximum_sweeps + 1):
        updates = torch.zeros_like(projected)
        for i, j, direction in geometry:
            relative = torch.dot(projected[0, i] - projected[0, j], direction)
            correction = .5 * relative * direction
            updates[0, i] -= correction
            updates[0, j] += correction
        projected += updates / relaxation
        residual = max(abs(float(torch.dot(projected[0, i] - projected[0, j], direction).item()))
                       for i, j, direction in geometry)
        if residual <= tolerance:
            return projected, float(torch.linalg.vector_norm(projected[0], dim=-1).max()), residual, sweep, True
    return projected, float(torch.linalg.vector_norm(projected[0], dim=-1).max()), residual, maximum_sweeps, False
