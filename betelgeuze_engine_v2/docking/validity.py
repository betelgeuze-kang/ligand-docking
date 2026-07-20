"""Bounded geometric validity checks and immutable selection contexts."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Mapping, Sequence

import torch

from .proposals import DockingProposal

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PoseValidityError(ValueError):
    """Pose validity input exceeds the supported bounded contract."""


def _canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PoseValidityError(
            "pose validity identity is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise PoseValidityError(f"{name} must be a lowercase SHA-256")
    return text


def _coords(
    value: object,
    *,
    name: str,
    require_nonempty: bool = False,
) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or value.ndim != 2
        or value.shape[-1] != 3
    ):
        raise PoseValidityError(f"{name} must have shape [N,3]")
    if require_nonempty and int(value.shape[0]) < 1:
        raise PoseValidityError(f"{name} must contain at least one coordinate")
    if not value.is_floating_point() or not bool(torch.isfinite(value).all().item()):
        raise PoseValidityError(
            f"{name} must contain finite floating coordinates"
        )
    return (
        value.detach()
        .to(dtype=torch.float64, device="cpu")
        .clone()
        .contiguous()
        .requires_grad_(False)
    )


def _vector3(value: object, *, name: str) -> torch.Tensor:
    tensor = torch.as_tensor(value, dtype=torch.float64, device="cpu").reshape(-1)
    if tensor.shape != (3,) or not bool(torch.isfinite(tensor).all().item()):
        raise PoseValidityError(f"{name} must contain three finite coordinates")
    return tensor.clone().contiguous().requires_grad_(False)


def _coordinate_identity(value: torch.Tensor, *, schema_id: str) -> str:
    tensor = value.detach().to(dtype=torch.float64, device="cpu").contiguous()
    return _canonical_sha256(
        {
            "schema_id": schema_id,
            "shape": [int(size) for size in tensor.shape],
            "values_hex": [
                float(item).hex() for item in tensor.reshape(-1).tolist()
            ],
        }
    )


def _normalize_pairs(
    values: Sequence[tuple[int, int]],
    *,
    atom_count: int,
    name: str,
) -> tuple[tuple[int, int], ...]:
    normalized: set[tuple[int, int]] = set()
    for first, second in values:
        i, j = sorted((int(first), int(second)))
        if i < 0 or j >= atom_count or i == j:
            raise PoseValidityError(f"{name} references invalid atom indices")
        normalized.add((i, j))
    return tuple(sorted(normalized))


def _normalize_chirality(
    values: Sequence[tuple[int, int, int, int]],
    *,
    atom_count: int,
) -> tuple[tuple[int, int, int, int], ...]:
    normalized: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for row in values:
        indices = tuple(int(value) for value in row)
        if (
            len(indices) != 4
            or len(set(indices)) != 4
            or min(indices) < 0
            or max(indices) >= atom_count
        ):
            raise PoseValidityError(
                "chirality center references invalid atom indices"
            )
        if indices in seen:
            raise PoseValidityError("chirality centers must be unique")
        seen.add(indices)
        normalized.append(indices)
    return tuple(normalized)


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
                raise PoseValidityError(
                    f"{name} must be finite and non-negative"
                )
            object.__setattr__(self, name, value)
        if self.pocket_radius_angstrom is not None:
            radius = float(self.pocket_radius_angstrom)
            if not math.isfinite(radius) or radius <= 0.0:
                raise PoseValidityError(
                    "pocket_radius_angstrom must be positive and finite"
                )
            object.__setattr__(self, "pocket_radius_angstrom", radius)
        pair_checks = int(self.max_pair_checks)
        cross_checks = int(self.max_cross_checks)
        if pair_checks < 0 or cross_checks < 0:
            raise PoseValidityError(
                "pair-check capacities must be non-negative"
            )
        object.__setattr__(self, "max_pair_checks", pair_checks)
        object.__setattr__(self, "max_cross_checks", cross_checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "bond_length_tolerance_angstrom": self.bond_length_tolerance_angstrom,
            "ligand_self_clash_angstrom": self.ligand_self_clash_angstrom,
            "receptor_ligand_clash_angstrom": self.receptor_ligand_clash_angstrom,
            "rotation_tolerance": self.rotation_tolerance,
            "chirality_volume_tolerance": self.chirality_volume_tolerance,
            "pocket_radius_angstrom": self.pocket_radius_angstrom,
            "max_pair_checks": self.max_pair_checks,
            "max_cross_checks": self.max_cross_checks,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(
            {
                "schema_id": "betelgeuze.engine_v2_pose_validity_config/2.0.0",
                **self.to_dict(),
            }
        )


@dataclass(frozen=True)
class PoseValidityResult:
    checks: Mapping[str, bool]
    evaluated_checks: Mapping[str, bool]
    complete: bool
    valid_within_evaluated_scope: bool
    measurements: Mapping[str, float | int]
    blockers: tuple[str, ...]
    not_evaluated_reasons: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", MappingProxyType(dict(self.checks)))
        object.__setattr__(
            self,
            "evaluated_checks",
            MappingProxyType(dict(self.evaluated_checks)),
        )
        object.__setattr__(
            self,
            "measurements",
            MappingProxyType(dict(self.measurements)),
        )
        object.__setattr__(self, "blockers", tuple(self.blockers))
        object.__setattr__(
            self,
            "not_evaluated_reasons",
            MappingProxyType(dict(self.not_evaluated_reasons)),
        )

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
            "valid_within_evaluated_scope": bool(
                self.valid_within_evaluated_scope
            ),
            "measurements": dict(self.measurements),
            "blockers": list(self.blockers),
            "not_evaluated_reasons": dict(self.not_evaluated_reasons),
            "claim_safe": False,
        }


@dataclass(frozen=True)
class PoseValidityContext:
    """Immutable receptor, topology, pocket, and validity selection contract."""

    problem_fingerprint_sha256: str
    reference_coordinates: torch.Tensor
    bond_pairs: tuple[tuple[int, int], ...]
    excluded_nonbonded_pairs: tuple[tuple[int, int], ...]
    receptor_coordinates: torch.Tensor
    pocket_center: torch.Tensor
    chirality_centers: tuple[tuple[int, int, int, int], ...]
    config: PoseValidityConfig
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        problem = _require_digest(
            self.problem_fingerprint_sha256,
            name="validity problem fingerprint",
        )
        reference = _coords(
            self.reference_coordinates,
            name="reference_coordinates",
            require_nonempty=True,
        )
        receptor = _coords(
            self.receptor_coordinates,
            name="receptor_coordinates",
            require_nonempty=True,
        )
        center = _vector3(self.pocket_center, name="pocket_center")
        if not isinstance(self.config, PoseValidityConfig):
            raise PoseValidityError("config must be PoseValidityConfig")
        if self.config.pocket_radius_angstrom is None:
            raise PoseValidityError(
                "selection validity context requires pocket_radius_angstrom"
            )
        atom_count = int(reference.shape[0])
        bonds = _normalize_pairs(
            self.bond_pairs,
            atom_count=atom_count,
            name="bond_pairs",
        )
        exclusions = _normalize_pairs(
            self.excluded_nonbonded_pairs,
            atom_count=atom_count,
            name="excluded_nonbonded_pairs",
        )
        if not set(bonds).issubset(exclusions):
            raise PoseValidityError(
                "excluded_nonbonded_pairs must include every declared bond"
            )
        chirality = _normalize_chirality(
            self.chirality_centers,
            atom_count=atom_count,
        )
        object.__setattr__(self, "problem_fingerprint_sha256", problem)
        object.__setattr__(self, "reference_coordinates", reference)
        object.__setattr__(self, "bond_pairs", bonds)
        object.__setattr__(self, "excluded_nonbonded_pairs", exclusions)
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "chirality_centers", chirality)
        object.__setattr__(
            self,
            "_fingerprint_sha256",
            self._current_fingerprint_sha256(),
        )

    @property
    def reference_coordinates_sha256(self) -> str:
        return _coordinate_identity(
            self.reference_coordinates,
            schema_id="betelgeuze.engine_v2_pose_validity_reference_coordinates/1.0.0",
        )

    @property
    def receptor_coordinates_sha256(self) -> str:
        return _coordinate_identity(
            self.receptor_coordinates,
            schema_id="betelgeuze.engine_v2_pose_validity_receptor_coordinates/1.0.0",
        )

    @property
    def pocket_center_sha256(self) -> str:
        return _coordinate_identity(
            self.pocket_center.reshape(1, 3),
            schema_id="betelgeuze.engine_v2_pose_validity_pocket_center/1.0.0",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": "betelgeuze.engine_v2_pose_validity_context/1.0.0",
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "reference_coordinates_sha256": self.reference_coordinates_sha256,
            "receptor_coordinates_sha256": self.receptor_coordinates_sha256,
            "pocket_center_sha256": self.pocket_center_sha256,
            "ligand_atom_count": int(self.reference_coordinates.shape[0]),
            "receptor_atom_count": int(self.receptor_coordinates.shape[0]),
            "bond_pairs": [list(pair) for pair in self.bond_pairs],
            "excluded_nonbonded_pairs": [
                list(pair) for pair in self.excluded_nonbonded_pairs
            ],
            "chirality_centers": [
                list(row) for row in self.chirality_centers
            ],
            "config": self.config.to_dict(),
            "config_fingerprint_sha256": self.config.fingerprint_sha256,
            "all_required_inputs_explicit": True,
            "chemistry_inference_performed": False,
            "claim_safe": False,
        }

    def _current_fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @property
    def fingerprint_sha256(self) -> str:
        self.assert_integrity()
        return self._fingerprint_sha256

    def assert_integrity(self) -> None:
        if self._current_fingerprint_sha256() != self._fingerprint_sha256:
            raise PoseValidityError(
                "pose validity context changed after construction"
            )

    def evaluate(self, proposal: DockingProposal) -> PoseValidityResult:
        self.assert_integrity()
        proposal.assert_integrity()
        if proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256:
            raise PoseValidityError(
                "pose validity context is cross-wired to another docking problem"
            )
        result = evaluate_pose_validity(
            proposal,
            self.reference_coordinates,
            bond_pairs=self.bond_pairs,
            excluded_nonbonded_pairs=self.excluded_nonbonded_pairs,
            receptor_coordinates=self.receptor_coordinates,
            pocket_center=self.pocket_center,
            chirality_centers=self.chirality_centers,
            config=self.config,
        )
        self.assert_integrity()
        proposal.assert_integrity()
        return result


def _signed_volume(
    coords: torch.Tensor,
    center: int,
    a: int,
    b: int,
    c: int,
) -> float:
    origin = coords[center]
    return float(
        torch.dot(
            torch.cross(coords[a] - origin, coords[b] - origin, dim=0),
            coords[c] - origin,
        ).item()
    )


def evaluate_pose_validity(
    proposal: DockingProposal,
    reference_coordinates: torch.Tensor,
    *,
    bond_pairs: Sequence[tuple[int, int]] | None = None,
    excluded_nonbonded_pairs: Sequence[tuple[int, int]] | None = None,
    receptor_coordinates: torch.Tensor | None = None,
    pocket_center: torch.Tensor | None = None,
    chirality_centers: Sequence[tuple[int, int, int, int]] | None = None,
    config: PoseValidityConfig | None = None,
) -> PoseValidityResult:
    """Evaluate explicit geometric checks without inferring chemistry."""

    if not isinstance(proposal, DockingProposal):
        raise TypeError("proposal must be DockingProposal")
    proposal.assert_integrity()
    cfg = config or PoseValidityConfig()
    reference = _coords(
        reference_coordinates,
        name="reference_coordinates",
        require_nonempty=True,
    )
    pose = _coords(
        proposal.coordinates,
        name="proposal.coordinates",
        require_nonempty=True,
    )
    if reference.shape != pose.shape:
        raise PoseValidityError(
            "reference and proposal coordinate shapes differ"
        )
    atom_count = int(pose.shape[0])
    bond_set = (
        set()
        if bond_pairs is None
        else set(
            _normalize_pairs(
                bond_pairs,
                atom_count=atom_count,
                name="bond_pairs",
            )
        )
    )
    exclusion_set = set(bond_set)
    if excluded_nonbonded_pairs is not None:
        exclusion_set.update(
            _normalize_pairs(
                excluded_nonbonded_pairs,
                atom_count=atom_count,
                name="excluded_nonbonded_pairs",
            )
        )

    checks: dict[str, bool] = {}
    evaluated_checks: dict[str, bool] = {}
    measurements: dict[str, float | int] = {"atom_count": atom_count}
    blockers: list[str] = []
    not_evaluated_reasons: dict[str, str] = {}

    identity = torch.eye(3, dtype=torch.float64)
    rotation = proposal.rotation.detach().to(dtype=torch.float64, device="cpu")
    orthogonality_error = float(
        torch.max(torch.abs(rotation.T @ rotation - identity)).item()
    )
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
        not_evaluated_reasons["bond_lengths_preserved"] = (
            "bond_pairs_not_supplied"
        )
        checks["ligand_self_clash_free"] = False
        evaluated_checks["ligand_self_clash_free"] = False
        not_evaluated_reasons["ligand_self_clash_free"] = (
            "bond_pairs_not_supplied"
        )
    else:
        max_bond_delta = 0.0
        for first, second in sorted(bond_set):
            reference_length = float(
                torch.linalg.vector_norm(
                    reference[first] - reference[second]
                ).item()
            )
            pose_length = float(
                torch.linalg.vector_norm(pose[first] - pose[second]).item()
            )
            max_bond_delta = max(
                max_bond_delta,
                abs(reference_length - pose_length),
            )
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
        evaluated_pair_count = 0
        for first in range(atom_count):
            for second in range(first + 1, atom_count):
                if (first, second) in exclusion_set:
                    continue
                evaluated_pair_count += 1
                distance = float(
                    torch.linalg.vector_norm(
                        pose[first] - pose[second]
                    ).item()
                )
                minimum_nonbonded = min(minimum_nonbonded, distance)
        if not math.isfinite(minimum_nonbonded):
            minimum_nonbonded = 999.0
        checks["ligand_self_clash_free"] = (
            minimum_nonbonded >= cfg.ligand_self_clash_angstrom
        )
        evaluated_checks["ligand_self_clash_free"] = True
        measurements["minimum_ligand_nonbonded_distance_angstrom"] = (
            minimum_nonbonded
        )
        measurements["evaluated_ligand_nonbonded_pair_count"] = (
            evaluated_pair_count
        )
        measurements["excluded_ligand_pair_count"] = len(exclusion_set)
        if not checks["ligand_self_clash_free"]:
            blockers.append("ligand_self_clash_detected")

    if receptor_coordinates is None:
        checks["receptor_ligand_clash_free"] = False
        evaluated_checks["receptor_ligand_clash_free"] = False
        not_evaluated_reasons["receptor_ligand_clash_free"] = (
            "receptor_coordinates_not_supplied"
        )
    else:
        receptor = _coords(
            receptor_coordinates,
            name="receptor_coordinates",
            require_nonempty=True,
        )
        if int(receptor.shape[0]) * atom_count > cfg.max_cross_checks:
            raise PoseValidityError(
                "receptor-ligand cross-check capacity exceeded"
            )
        distances = torch.cdist(pose, receptor)
        minimum_receptor_distance = float(distances.min().item())
        checks["receptor_ligand_clash_free"] = (
            minimum_receptor_distance >= cfg.receptor_ligand_clash_angstrom
        )
        evaluated_checks["receptor_ligand_clash_free"] = True
        measurements["minimum_receptor_ligand_distance_angstrom"] = (
            minimum_receptor_distance
        )
        if not checks["receptor_ligand_clash_free"]:
            blockers.append("receptor_ligand_clash_detected")

    if chirality_centers is None:
        checks["declared_chirality_preserved"] = False
        evaluated_checks["declared_chirality_preserved"] = False
        not_evaluated_reasons["declared_chirality_preserved"] = (
            "chirality_centers_not_supplied"
        )
    else:
        centers = _normalize_chirality(
            chirality_centers,
            atom_count=atom_count,
        )
        chirality_preserved = True
        minimum_chiral_volume = float("inf")
        for indices in centers:
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
        measurements["declared_chirality_center_count"] = len(centers)
        if not chirality_preserved:
            blockers.append("declared_chirality_not_preserved")

    if pocket_center is None:
        checks["inside_declared_pocket"] = False
        evaluated_checks["inside_declared_pocket"] = False
        not_evaluated_reasons["inside_declared_pocket"] = (
            "pocket_center_not_supplied"
        )
    else:
        center = _vector3(pocket_center, name="pocket_center")
        radius = cfg.pocket_radius_angstrom
        if radius is None:
            raise PoseValidityError(
                "pocket_center requires pocket_radius_angstrom"
            )
        max_distance = float(
            torch.linalg.vector_norm(pose - center, dim=-1).max().item()
        )
        checks["inside_declared_pocket"] = max_distance <= radius
        evaluated_checks["inside_declared_pocket"] = True
        measurements["maximum_pocket_center_distance_angstrom"] = max_distance
        if not checks["inside_declared_pocket"]:
            blockers.append("pose_outside_declared_pocket")

    complete = all(evaluated_checks.values())
    valid_within_evaluated_scope = all(
        checks[name]
        for name, evaluated in evaluated_checks.items()
        if evaluated
    )
    proposal.assert_integrity()
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
    "PoseValidityContext",
    "PoseValidityError",
    "PoseValidityResult",
    "evaluate_pose_validity",
]
