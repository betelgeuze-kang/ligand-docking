"""Bounded pose-comparison metrics for docking diversity and validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import torch

MAX_SYMMETRY_PERMUTATIONS = 1024


class PoseMetricError(ValueError):
    """Pose coordinates or symmetry mappings violate the metric contract."""


@dataclass(frozen=True)
class RMSDResult:
    rmsd_angstrom: float
    aligned: bool
    symmetry_permutation_index: int

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.rmsd_angstrom)) or float(self.rmsd_angstrom) < 0.0:
            raise PoseMetricError("RMSD must be finite and non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "rmsd_angstrom": float(self.rmsd_angstrom),
            "aligned": bool(self.aligned),
            "symmetry_permutation_index": int(self.symmetry_permutation_index),
        }


def _coordinates(value: torch.Tensor, *, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.ndim != 2 or value.shape[-1] != 3:
        raise PoseMetricError(f"{name} must have shape [N,3]")
    if value.shape[0] < 1 or not value.is_floating_point():
        raise PoseMetricError(f"{name} must contain at least one floating atom")
    if not bool(torch.isfinite(value).all().item()):
        raise PoseMetricError(f"{name} must be finite")
    return value


def direct_rmsd(reference: torch.Tensor, candidate: torch.Tensor) -> float:
    first = _coordinates(reference, name="reference")
    second = _coordinates(candidate, name="candidate")
    if first.shape != second.shape:
        raise PoseMetricError("pose coordinate shapes differ")
    return float(torch.sqrt((first - second).square().sum(dim=-1).mean()).item())


def kabsch_aligned_coordinates(reference: torch.Tensor, candidate: torch.Tensor) -> torch.Tensor:
    first = _coordinates(reference, name="reference")
    second = _coordinates(candidate, name="candidate")
    if first.shape != second.shape:
        raise PoseMetricError("pose coordinate shapes differ")
    work_dtype = torch.float64 if first.dtype == torch.float64 or second.dtype == torch.float64 else torch.float32
    first_work = first.to(dtype=work_dtype)
    second_work = second.to(dtype=work_dtype, device=first.device)
    first_center = first_work.mean(dim=0)
    second_center = second_work.mean(dim=0)
    x = second_work - second_center
    y = first_work - first_center
    covariance = x.T @ y
    u, _singular, vh = torch.linalg.svd(covariance)
    correction = torch.eye(3, dtype=work_dtype, device=first.device)
    if float(torch.linalg.det(u @ vh).item()) < 0.0:
        correction[-1, -1] = -1.0
    rotation = u @ correction @ vh
    aligned = x @ rotation + first_center
    return aligned.to(dtype=candidate.dtype, device=candidate.device)


def kabsch_aligned_rmsd(reference: torch.Tensor, candidate: torch.Tensor) -> float:
    aligned = kabsch_aligned_coordinates(reference, candidate)
    return direct_rmsd(reference, aligned)


def _permutation_tensor(
    permutation: Sequence[int] | torch.Tensor,
    *,
    atom_count: int,
    device: torch.device,
) -> torch.Tensor:
    values = _canonicalize_symmetry_permutations(
        (permutation,),
        atom_count=atom_count,
    )[0]
    return torch.tensor(values, dtype=torch.long, device=device)


def _canonicalize_symmetry_permutations(
    permutations: Sequence[Sequence[int] | torch.Tensor],
    *,
    atom_count: int,
) -> tuple[tuple[int, ...], ...]:
    if len(permutations) < 1 or len(permutations) > MAX_SYMMETRY_PERMUTATIONS:
        raise PoseMetricError(
            f"symmetry permutation count must be in [1,{MAX_SYMMETRY_PERMUTATIONS}]"
        )
    expected = list(range(int(atom_count)))
    canonical: list[tuple[int, ...]] = []
    for permutation in permutations:
        try:
            tensor = torch.as_tensor(permutation)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise PoseMetricError(
                "symmetry permutation must be a one-dimensional integer mapping"
            ) from exc
        if tensor.shape != (atom_count,):
            raise PoseMetricError("symmetry permutation must have shape [N]")
        if tensor.dtype == torch.bool or tensor.is_floating_point() or tensor.is_complex():
            raise PoseMetricError("symmetry permutation atom indices must be integers")
        values = tuple(int(value) for value in tensor.detach().cpu().tolist())
        if sorted(values) != expected:
            raise PoseMetricError("symmetry permutation must be a bijection over atom indices")
        canonical.append(values)
    return tuple(canonical)


def symmetry_aware_rmsd(
    reference: torch.Tensor,
    candidate: torch.Tensor,
    *,
    permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
    align: bool = True,
) -> RMSDResult:
    first = _coordinates(reference, name="reference")
    second = _coordinates(candidate, name="candidate")
    if first.shape != second.shape:
        raise PoseMetricError("pose coordinate shapes differ")
    candidates = _canonicalize_symmetry_permutations(
        (tuple(range(first.shape[0])),) if permutations is None else permutations,
        atom_count=int(first.shape[0]),
    )
    best_value = float("inf")
    best_index = -1
    for index, permutation in enumerate(candidates):
        mapping = _permutation_tensor(
            permutation,
            atom_count=int(first.shape[0]),
            device=second.device,
        )
        permuted = second[mapping]
        value = kabsch_aligned_rmsd(first, permuted) if align else direct_rmsd(first, permuted)
        if value < best_value:
            best_value = value
            best_index = index
    return RMSDResult(
        rmsd_angstrom=best_value,
        aligned=bool(align),
        symmetry_permutation_index=best_index,
    )


__all__ = [
    "MAX_SYMMETRY_PERMUTATIONS",
    "PoseMetricError",
    "RMSDResult",
    "direct_rmsd",
    "kabsch_aligned_coordinates",
    "kabsch_aligned_rmsd",
    "symmetry_aware_rmsd",
]
