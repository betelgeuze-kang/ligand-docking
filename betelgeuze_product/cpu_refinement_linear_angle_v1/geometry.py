"""Stable composite harmonic energy at the removable antiparallel endpoint."""

import torch
from betelgeuze_engine_v2.physics.reference_forcefield import (
    ReferencePhysicsApplicabilityError,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import finite

SMALL_CHORD_SQUARED = 1.e-4


def harmonic_linear_angle_energy(first, second, force_constant):
    """Return 0.5*k*(theta-pi)^2, including its zero Cartesian gradient at pi.

    For normalized u,v, q=|u+v|^2 and E/k=2*asin(sqrt(q)/2)^2.
    Its regular power series is sum q^n/(n^2*binomial(2n,n)). The five-term
    small-q evaluation has < 4e-29 absolute remainder at q <= 1e-4, avoiding
    the artificial singularity of sqrt at zero. Outside this region atan2
    evaluates the same source harmonic energy without subtracting from pi.
    No coordinates or force components are projected, clipped or jittered.
    """
    k = finite(force_constant)
    if k <= 0:
        raise ReferencePhysicsApplicabilityError("positive linear angle force constant required")
    if (not isinstance(first, torch.Tensor) or not isinstance(second, torch.Tensor)
            or first.dtype != torch.float64 or second.dtype != torch.float64
            or first.device.type != "cpu" or second.device.type != "cpu"
            or first.shape != second.shape or first.ndim != 2 or first.shape[-1] != 3
            or not bool(torch.isfinite(first).all()) or not bool(torch.isfinite(second).all())):
        raise ReferencePhysicsApplicabilityError("finite batched CPU float64 linear angle vectors required")
    left_norm = torch.linalg.vector_norm(first, dim=-1, keepdim=True)
    right_norm = torch.linalg.vector_norm(second, dim=-1, keepdim=True)
    if (not bool(torch.isfinite(left_norm).all()) or not bool(torch.isfinite(right_norm).all())
            or bool((left_norm <= 1.e-12).any()) or bool((right_norm <= 1.e-12).any())):
        raise ReferencePhysicsApplicabilityError("linear angle contains a zero-length or nonfinite vector norm")
    left, right = first / left_norm, second / right_norm
    sine = torch.linalg.vector_norm(torch.linalg.cross(left, right, dim=-1), dim=-1)
    cosine = (left * right).sum(dim=-1)
    if bool(((cosine >= 0) & (sine <= 8 * torch.finfo(sine.dtype).eps)).any()):
        raise ReferencePhysicsApplicabilityError("linear-equilibrium angle has incompatible parallel vectors")
    q = (left + right).square().sum(dim=-1)
    # Horner form is analytic at q=0 and retains its nonzero curvature.
    series = q * (.5 + q * (1/24 + q * (1/180 + q * (1/1120 + q/6300))))
    regular = q > SMALL_CHORD_SQUARED
    result = series.clone()
    if bool(regular.any()):
        # Mask before the norm: a dormant singular derivative must not poison
        # higher-order autograd at an exactly antiparallel row in a mixed batch.
        a, b = left[regular], right[regular]
        selected_sine = torch.linalg.vector_norm(torch.linalg.cross(a, b, dim=-1), dim=-1)
        selected_cosine = (a * b).sum(dim=-1)
        delta = torch.atan2(selected_sine, -selected_cosine)
        result[regular] = .5 * delta.square()
    return k * result
