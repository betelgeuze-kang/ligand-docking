"""Bounded geometric validity checks for internal docking poses."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import torch

from .proposals import DockingProposal


class PoseValidityError(ValueError):
    """Pose validity input exceeds the supported bounded contract."""


@dataclass(frozen=True)
class PoseValidityConfig:
    bond_length_tolerance_angstrom: float = 0.15
    ligand_self_clash_angstrom: float = 0.75
    receptor_ligand_clash_angstrom: float = 0.8
    rotation_tolerance: float = 1.0e-6
    chirality_volume_tolerance: float = 1.0e-8
    pocket_radius_angstrom: float | None = None
    max_pair_checks: int = 250_000
    max_cross_checks: int = 1_000_000

    def __post_init__(self) -> None:
        for name in (
            "bond_length_tolerance_angstrom",
            "ligand_self_clash_angstrom",
            "receptor_ligand_clash_angstrom",
            "rotation_tolerance",
            "chirality_volume_tolerance",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise PoseValidityError(f"{name} must be finite and non-negative")
        if self.pocket_radius_angstrom is not None and (
            not math.isfinite(float(self.pocket_radius_angstrom))
            or float(self.pocket_radius_angstrom) <= 0.0
        ):
            raise PoseValidityError("pocket_radius_angstrom must be positive and finite")
        if int(self.max_pair_checks) < 0 or int(self.max_cross_checks) < 0:
            raise PoseValidityError("pair-check capacities must be non-negative")


@dataclass(frozen=True)
class PoseValidityResult:
    checks: dict[str, bool]
    evaluated_checks: dict[str, bool]
    complete: bool
    valid_within_evaluated_scope: bool
    measurements: dict[str, float | int]
    blockers: tuple[str, ...]
    not_evaluated_reasons: dict[str, str]

    @property
    def valid(self) -> bool:
        return bool(self.complete and self.valid_within_evaluated_scope)

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "checks": dict(self.checks),
            "evaluated_checks": dict(self.evaluated_checks),
            "complete": bool(self.complete),
            "valid_within_evaluated_scope": bool(self.valid_within_evaluated_scope),
            "measurements": dict(self.measurements),
            "blockers": list(self.blockers),
            "not_evaluated_reasons": dict(self.not_evaluated_reasons),
            "claim_safe": False,
        }


def _coords(value: torch.Tensor, *, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.ndim != 2 or value.shape[-1] != 3:
        raise PoseValidityError(f"{name} must have shape [N,3]")
    if not value.is_floating_point() or not bool(torch.isfinite(value).all().item()):
        raise PoseValidityError(f"{name} must contain finite floating coordinates")
    return value.detach().to(dtype=torch.float64, device="cpu")


def _signed_volume(coords: torch.Tensor, center: int, a: int, b: int, c: int) -> float:
    origin = coords[center]
    return float(torch.dot(torch.cross(coords[a] - origin, coords[b] - origin, dim=0), coords[c] - origin).item())


def evaluate_pose_validity(
    proposal: DockingProposal,
    reference_coordinates: torch.Tensor,
    *,
    bond_pairs: Sequence[tuple[int, int]] | None = None,
    receptor_coordinates: torch.Tensor | None = None,
    pocket_center: torch.Tensor | None = None,
    chirality_centers: Sequence[tuple[int, int, int, int]] | None = None,
    config: PoseValidityConfig | None = None,
) -> PoseValidityResult:
    """Evaluate explicit geometric checks without inferring chemistry."""

    cfg = config or PoseValidityConfig()
    reference = _coords(reference_coordinates, name="reference_coordinates")
    pose = _coords(proposal.coordinates, name="proposal.coordinates")
    if reference.shape != pose.shape:
        raise PoseValidityError("reference and proposal coordinate shapes differ")
    atom_count = int(pose.shape[0])
    bond_set: set[tuple[int, int]] = set()
    for first, second in bond_pairs or ():
        i, j = sorted((int(first), int(second)))
        if i < 0 or j >= atom_count or i == j:
            raise PoseValidityError("bond pair references invalid atom indices")
        bond_set.add((i, j))

    checks: dict[str, bool] = {}
    evaluated_checks: dict[str, bool] = {}
    measurements: dict[str, float | int] = {"atom_count": atom_count}
    blockers: list[str] = []
    not_evaluated_reasons: dict[str, str] = {}

    identity = torch.eye(3, dtype=torch.float64)
    rotation = proposal.rotation.detach().to(dtype=torch.float64, device="cpu")
    orthogonality_error = float(torch.max(torch.abs(rotation.T @ rotation - identity)).item())
    determinant = float(torch.linalg.det(rotation).item())
    checks["proper_rotation"] = bool(
        orthogonality_error <= cfg.rotation_tolerance
        and abs(determinant - 1.0) <= cfg.rotation_tolerance
    )
    evaluated_checks["proper_rotation"] = True
    measurements["rotation_orthogonality_max_error"] = orthogonality_error
    measurements["rotation_determinant"] = determinant
    if not checks["proper_rotation"]:
        blockers.append("rigid_rotation_not_proper_orthogonal")

    if bond_pairs is None:
        checks["bond_lengths_preserved"] = False
        evaluated_checks["bond_lengths_preserved"] = False
        not_evaluated_reasons["bond_lengths_preserved"] = "bond_pairs_not_supplied"
        checks["ligand_self_clash_free"] = False
        evaluated_checks["ligand_self_clash_free"] = False
        not_evaluated_reasons["ligand_self_clash_free"] = "bond_pairs_not_supplied"
    else:
        max_bond_delta = 0.0
        for first, second in sorted(bond_set):
            reference_length = float(
                torch.linalg.vector_norm(reference[first] - reference[second]).item()
            )
            pose_length = float(torch.linalg.vector_norm(pose[first] - pose[second]).item())
            max_bond_delta = max(max_bond_delta, abs(reference_length - pose_length))
        checks["bond_lengths_preserved"] = (
            max_bond_delta <= cfg.bond_length_tolerance_angstrom
        )
        evaluated_checks["bond_lengths_preserved"] = True
        measurements["max_bond_length_delta_angstrom"] = max_bond_delta
        if not checks["bond_lengths_preserved"]:
            blockers.append("bond_length_preservation_failed")

        pair_count = atom_count * (atom_count - 1) // 2
        if pair_count > cfg.max_pair_checks:
            raise PoseValidityError("ligand pair-check capacity exceeded")
        minimum_nonbonded = float("inf")
        for first in range(atom_count):
            for second in range(first + 1, atom_count):
                if (first, second) in bond_set:
                    continue
                distance = float(torch.linalg.vector_norm(pose[first] - pose[second]).item())
                minimum_nonbonded = min(minimum_nonbonded, distance)
        if not math.isfinite(minimum_nonbonded):
            minimum_nonbonded = 999.0
        checks["ligand_self_clash_free"] = (
            minimum_nonbonded >= cfg.ligand_self_clash_angstrom
        )
        evaluated_checks["ligand_self_clash_free"] = True
        measurements["minimum_ligand_nonbonded_distance_angstrom"] = minimum_nonbonded
        if not checks["ligand_self_clash_free"]:
            blockers.append("ligand_self_clash_detected")

    if receptor_coordinates is not None:
        receptor = _coords(receptor_coordinates, name="receptor_coordinates")
        if int(receptor.shape[0]) * atom_count > cfg.max_cross_checks:
            raise PoseValidityError("receptor-ligand cross-check capacity exceeded")
        minimum_receptor_distance = float("inf")
        for ligand_index in range(atom_count):
            for receptor_index in range(int(receptor.shape[0])):
                distance = float(
                    torch.linalg.vector_norm(pose[ligand_index] - receptor[receptor_index]).item()
                )
                minimum_receptor_distance = min(minimum_receptor_distance, distance)
        checks["receptor_ligand_clash_free"] = (
            minimum_receptor_distance >= cfg.receptor_ligand_clash_angstrom
        )
        evaluated_checks["receptor_ligand_clash_free"] = True
        measurements["minimum_receptor_ligand_distance_angstrom"] = minimum_receptor_distance
        if not checks["receptor_ligand_clash_free"]:
            blockers.append("receptor_ligand_clash_detected")
    else:
        checks["receptor_ligand_clash_free"] = False
        evaluated_checks["receptor_ligand_clash_free"] = False
        not_evaluated_reasons["receptor_ligand_clash_free"] = (
            "receptor_coordinates_not_supplied"
        )

    if chirality_centers is None:
        checks["declared_chirality_preserved"] = False
        evaluated_checks["declared_chirality_preserved"] = False
        not_evaluated_reasons["declared_chirality_preserved"] = (
            "chirality_centers_not_supplied"
        )
    else:
        chirality_preserved = True
        minimum_chiral_volume = float("inf")
        for center, a, b, c in chirality_centers:
            indices = (int(center), int(a), int(b), int(c))
            if len(set(indices)) != 4 or min(indices) < 0 or max(indices) >= atom_count:
                raise PoseValidityError("chirality center references invalid atom indices")
            reference_volume = _signed_volume(reference, *indices)
            pose_volume = _signed_volume(pose, *indices)
            minimum_chiral_volume = min(
                minimum_chiral_volume,
                abs(reference_volume),
                abs(pose_volume),
            )
            if (
                abs(reference_volume) <= cfg.chirality_volume_tolerance
                or abs(pose_volume) <= cfg.chirality_volume_tolerance
                or reference_volume * pose_volume < 0.0
            ):
                chirality_preserved = False
        if not math.isfinite(minimum_chiral_volume):
            minimum_chiral_volume = 0.0
        checks["declared_chirality_preserved"] = chirality_preserved
        evaluated_checks["declared_chirality_preserved"] = True
        measurements["minimum_declared_chiral_volume"] = minimum_chiral_volume
        if not chirality_preserved:
            blockers.append("declared_chirality_not_preserved")

    if pocket_center is not None:
        center = torch.as_tensor(pocket_center, dtype=torch.float64).reshape(-1)
        if center.shape != (3,) or not bool(torch.isfinite(center).all().item()):
            raise PoseValidityError("pocket_center must contain three finite coordinates")
        radius = cfg.pocket_radius_angstrom
        if radius is None:
            raise PoseValidityError("pocket_center requires pocket_radius_angstrom")
        max_distance = max(
            float(torch.linalg.vector_norm(pose[index] - center).item())
            for index in range(atom_count)
        )
        checks["inside_declared_pocket"] = max_distance <= float(radius)
        evaluated_checks["inside_declared_pocket"] = True
        measurements["maximum_pocket_center_distance_angstrom"] = max_distance
        if not checks["inside_declared_pocket"]:
            blockers.append("pose_outside_declared_pocket")
    else:
        checks["inside_declared_pocket"] = False
        evaluated_checks["inside_declared_pocket"] = False
        not_evaluated_reasons["inside_declared_pocket"] = "pocket_center_not_supplied"

    complete = all(evaluated_checks.values())
    valid_within_evaluated_scope = all(
        checks[name]
        for name, evaluated in evaluated_checks.items()
        if evaluated
    )

    return PoseValidityResult(
        checks=checks,
        evaluated_checks=evaluated_checks,
        complete=complete,
        valid_within_evaluated_scope=valid_within_evaluated_scope,
        measurements=measurements,
        blockers=tuple(blockers),
        not_evaluated_reasons=not_evaluated_reasons,
    )


__all__ = [
    "PoseValidityConfig",
    "PoseValidityError",
    "PoseValidityResult",
    "evaluate_pose_validity",
]
