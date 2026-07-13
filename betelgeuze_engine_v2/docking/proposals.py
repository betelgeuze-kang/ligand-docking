"""Deterministic bounded torsion and rigid-body docking proposal generation."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import re

import torch

from betelgeuze_engine_v2.ai import axis_angle_matrix, torsion_tree_forward_kinematics
from .identity import (
    DockingProblemIdentity,
    coordinate_fingerprint,
    search_space_fingerprint,
)

MAX_DOCKING_TORSIONS = 64
MAX_DOCKING_CANDIDATES = 4096
MAX_DOCKING_TOP_K = 128
MAX_DOCKING_REFINEMENT_STEPS = 256
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DockingProposalError(ValueError):
    """A docking proposal request exceeds the supported bounded scaffold."""


def _require_digest(value: str, *, field_name: str, allow_empty: bool = False) -> str:
    text = str(value or "").lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise DockingProposalError(f"{field_name} must be a lowercase SHA-256")
    return text


@dataclass(frozen=True)
class DockingBudget:
    candidate_count: int = 64
    top_k: int = 10
    max_torsions: int = 32
    max_refinement_steps: int = 0
    translation_radius_angstrom: float = 4.0
    seed: int = 7301

    def __post_init__(self) -> None:
        if int(self.candidate_count) < 1 or int(self.candidate_count) > MAX_DOCKING_CANDIDATES:
            raise DockingProposalError(
                f"candidate_count must be in [1, {MAX_DOCKING_CANDIDATES}]"
            )
        if int(self.top_k) < 1 or int(self.top_k) > min(int(self.candidate_count), MAX_DOCKING_TOP_K):
            raise DockingProposalError(
                f"top_k must be in [1, min(candidate_count, {MAX_DOCKING_TOP_K})]"
            )
        if int(self.max_torsions) < 0 or int(self.max_torsions) > MAX_DOCKING_TORSIONS:
            raise DockingProposalError(
                f"max_torsions must be in [0, {MAX_DOCKING_TORSIONS}]"
            )
        if (
            int(self.max_refinement_steps) < 0
            or int(self.max_refinement_steps) > MAX_DOCKING_REFINEMENT_STEPS
        ):
            raise DockingProposalError(
                f"max_refinement_steps must be in [0, {MAX_DOCKING_REFINEMENT_STEPS}]"
            )
        radius = float(self.translation_radius_angstrom)
        if not math.isfinite(radius) or radius < 0.0:
            raise DockingProposalError("translation_radius_angstrom must be finite and non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": int(self.candidate_count),
            "top_k": int(self.top_k),
            "max_torsions": int(self.max_torsions),
            "max_refinement_steps": int(self.max_refinement_steps),
            "translation_radius_angstrom": float(self.translation_radius_angstrom),
            "seed": int(self.seed),
        }


@dataclass(frozen=True)
class TorsionSearchSpace:
    local_offsets: torch.Tensor
    parent: torch.Tensor
    local_axes: torch.Tensor
    rotatable_mask: torch.Tensor
    root_positions: torch.Tensor | None = None

    def __post_init__(self) -> None:
        atom_count = int(self.local_offsets.shape[0]) if self.local_offsets.ndim == 2 else -1
        if atom_count < 1 or self.local_offsets.shape != (atom_count, 3):
            raise DockingProposalError("local_offsets must have shape [N,3]")
        if self.parent.shape != (atom_count,) or self.parent.dtype != torch.long:
            raise DockingProposalError("parent must be torch.long with shape [N]")
        if self.local_axes.shape != (atom_count, 3):
            raise DockingProposalError("local_axes must have shape [N,3]")
        if self.rotatable_mask.shape != (atom_count,) or self.rotatable_mask.dtype != torch.bool:
            raise DockingProposalError("rotatable_mask must be boolean with shape [N]")
        tensors = (self.local_offsets, self.local_axes)
        if not all(value.is_floating_point() for value in tensors):
            raise DockingProposalError("kinematic tensors must use floating dtypes")
        if self.local_offsets.dtype != self.local_axes.dtype:
            raise DockingProposalError("local_offsets and local_axes must share a dtype")
        if self.local_offsets.device.type != "cpu" or self.parent.device.type != "cpu":
            raise DockingProposalError("bounded docking proposal scaffold is CPU-only")
        if self.local_axes.device != self.local_offsets.device or self.rotatable_mask.device != self.parent.device:
            raise DockingProposalError("search-space tensors must share the CPU device")
        if not bool(torch.isfinite(self.local_offsets).all().item()):
            raise DockingProposalError("local_offsets must be finite")
        if not bool(torch.isfinite(self.local_axes).all().item()):
            raise DockingProposalError("local_axes must be finite")
        roots = self.parent == -1
        if bool((self.rotatable_mask & roots).any().item()):
            raise DockingProposalError("root atoms cannot be marked as torsion variables")
        torsion_tree_forward_kinematics(
            self.local_offsets,
            self.parent,
            torch.zeros(atom_count, dtype=self.local_offsets.dtype),
            local_axes=self.local_axes,
            root_positions=self.root_positions,
        )

    @property
    def atom_count(self) -> int:
        return int(self.local_offsets.shape[0])

    @property
    def torsion_count(self) -> int:
        return int(self.rotatable_mask.sum().item())

    @property
    def fingerprint_sha256(self) -> str:
        return search_space_fingerprint(
            local_offsets=self.local_offsets,
            parent=self.parent,
            local_axes=self.local_axes,
            rotatable_mask=self.rotatable_mask,
            root_positions=self.root_positions,
        )


@dataclass(frozen=True)
class DockingProposal:
    candidate_id: str
    coordinates: torch.Tensor
    torsion_angles: torch.Tensor
    rotation: torch.Tensor
    translation: torch.Tensor
    proposal_index: int
    seed: int
    fingerprint_sha256: str
    problem_fingerprint_sha256: str = ""
    search_space_fingerprint_sha256: str = ""
    coordinate_fingerprint_sha256: str = ""
    parent_proposal_fingerprint_sha256: str = ""
    refiner_id: str = ""
    refiner_version: str = ""
    refinement_receipt_sha256: str = ""

    def __post_init__(self) -> None:
        atom_count = int(self.coordinates.shape[0]) if self.coordinates.ndim == 2 else -1
        if atom_count < 1 or self.coordinates.shape != (atom_count, 3):
            raise DockingProposalError("proposal coordinates must have shape [N,3]")
        if self.torsion_angles.shape != (atom_count,):
            raise DockingProposalError("proposal torsion_angles must have shape [N]")
        if self.rotation.shape != (3, 3) or self.translation.shape != (3,):
            raise DockingProposalError("proposal rigid transform has invalid shape")
        if not all(
            bool(torch.isfinite(value).all().item())
            for value in (self.coordinates, self.torsion_angles, self.rotation, self.translation)
        ):
            raise DockingProposalError("proposal tensors must be finite")
        _require_digest(self.fingerprint_sha256, field_name="fingerprint_sha256")
        for field_name in (
            "problem_fingerprint_sha256",
            "search_space_fingerprint_sha256",
            "coordinate_fingerprint_sha256",
            "parent_proposal_fingerprint_sha256",
            "refinement_receipt_sha256",
        ):
            _require_digest(
                getattr(self, field_name),
                field_name=field_name,
                allow_empty=field_name in {"parent_proposal_fingerprint_sha256", "refinement_receipt_sha256"},
            )
        expected_coordinate_digest = coordinate_fingerprint(self.coordinates)
        if self.coordinate_fingerprint_sha256 and self.coordinate_fingerprint_sha256 != expected_coordinate_digest:
            raise DockingProposalError("coordinate_fingerprint_sha256 does not match proposal coordinates")
        if bool(self.parent_proposal_fingerprint_sha256) != bool(self.refiner_id and self.refiner_version):
            raise DockingProposalError("refined proposal lineage requires parent fingerprint and refiner identity")

    @property
    def refined(self) -> bool:
        return bool(self.parent_proposal_fingerprint_sha256)

    def with_refined_coordinates(
        self,
        coordinates: torch.Tensor,
        *,
        refiner_id: str,
        refiner_version: str,
        refinement_receipt_sha256: str = "",
    ) -> "DockingProposal":
        if not str(refiner_id or "").strip() or not str(refiner_version or "").strip():
            raise DockingProposalError("refined proposals require refiner ID and version")
        receipt = _require_digest(
            refinement_receipt_sha256,
            field_name="refinement_receipt_sha256",
            allow_empty=True,
        )
        coordinate_digest = coordinate_fingerprint(coordinates)
        fingerprint = _proposal_fingerprint(
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=self.torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=str(refiner_id),
            refiner_version=str(refiner_version),
            refinement_receipt_sha256=receipt,
        )
        return replace(
            self,
            coordinates=coordinates,
            fingerprint_sha256=fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=str(refiner_id),
            refiner_version=str(refiner_version),
            refinement_receipt_sha256=receipt,
        )


def _tensor_payload(tensor: torch.Tensor) -> list[float]:
    return [float(value) for value in tensor.detach().to(dtype=torch.float64, device="cpu").reshape(-1).tolist()]


def _proposal_fingerprint(
    *,
    proposal_index: int,
    seed: int,
    torsion_angles: torch.Tensor,
    rotation: torch.Tensor,
    translation: torch.Tensor,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
    coordinate_fingerprint_sha256: str,
    parent_proposal_fingerprint_sha256: str = "",
    refiner_id: str = "",
    refiner_version: str = "",
    refinement_receipt_sha256: str = "",
) -> str:
    payload = {
        "schema_id": "betelgeuze.engine_v2_docking_proposal/2.0.0",
        "proposal_index": int(proposal_index),
        "seed": int(seed),
        "problem_fingerprint_sha256": problem_fingerprint_sha256,
        "search_space_fingerprint_sha256": search_space_fingerprint_sha256,
        "coordinate_fingerprint_sha256": coordinate_fingerprint_sha256,
        "parent_proposal_fingerprint_sha256": parent_proposal_fingerprint_sha256,
        "refiner_id": refiner_id,
        "refiner_version": refiner_version,
        "refinement_receipt_sha256": refinement_receipt_sha256,
        "torsion_angles": _tensor_payload(torsion_angles),
        "rotation": _tensor_payload(rotation),
        "translation": _tensor_payload(translation),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _random_unit_axis(generator: torch.Generator, dtype: torch.dtype) -> torch.Tensor:
    axis = torch.randn(3, generator=generator, dtype=dtype)
    norm = torch.linalg.vector_norm(axis)
    if float(norm.item()) <= 1e-12:
        return torch.tensor([0.0, 0.0, 1.0], dtype=dtype)
    return axis / norm


def generate_bounded_docking_proposals(
    search_space: TorsionSearchSpace,
    budget: DockingBudget,
    *,
    problem: DockingProblemIdentity | None = None,
) -> tuple[DockingProposal, ...]:
    """Generate a deterministic baseline plus bounded random torsion/rigid proposals."""

    if search_space.torsion_count > int(budget.max_torsions):
        raise DockingProposalError(
            f"search space has {search_space.torsion_count} torsions, exceeding budget {budget.max_torsions}"
        )
    problem_identity = problem or DockingProblemIdentity.unbound()
    problem_fingerprint = problem_identity.fingerprint_sha256
    space_fingerprint = search_space.fingerprint_sha256
    dtype = search_space.local_offsets.dtype
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(budget.seed))
    proposals: list[DockingProposal] = []
    for proposal_index in range(int(budget.candidate_count)):
        angles = torch.zeros(search_space.atom_count, dtype=dtype)
        if proposal_index > 0 and search_space.torsion_count:
            sampled = (
                torch.rand(search_space.torsion_count, generator=generator, dtype=dtype) * (2.0 * torch.pi)
                - torch.pi
            )
            angles[search_space.rotatable_mask] = sampled
        kinematic = torsion_tree_forward_kinematics(
            search_space.local_offsets,
            search_space.parent,
            angles,
            local_axes=search_space.local_axes,
            root_positions=search_space.root_positions,
        )
        if proposal_index == 0:
            rotation = torch.eye(3, dtype=dtype)
            translation = torch.zeros(3, dtype=dtype)
        else:
            axis = _random_unit_axis(generator, dtype)
            rigid_angle = (torch.rand((), generator=generator, dtype=dtype) * 2.0 - 1.0) * torch.pi
            rotation = axis_angle_matrix(axis.unsqueeze(0), rigid_angle.unsqueeze(0))[0]
            direction = _random_unit_axis(generator, dtype)
            radius = torch.rand((), generator=generator, dtype=dtype) ** (1.0 / 3.0)
            translation = direction * radius * float(budget.translation_radius_angstrom)
        coordinates = kinematic.coordinates @ rotation.T + translation
        coordinate_digest = coordinate_fingerprint(coordinates)
        fingerprint = _proposal_fingerprint(
            proposal_index=proposal_index,
            seed=int(budget.seed),
            torsion_angles=angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=space_fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposals.append(
            DockingProposal(
                candidate_id=f"pose-{proposal_index:05d}-{fingerprint[:12]}",
                coordinates=coordinates,
                torsion_angles=angles,
                rotation=rotation,
                translation=translation,
                proposal_index=proposal_index,
                seed=int(budget.seed),
                fingerprint_sha256=fingerprint,
                problem_fingerprint_sha256=problem_fingerprint,
                search_space_fingerprint_sha256=space_fingerprint,
                coordinate_fingerprint_sha256=coordinate_digest,
            )
        )
    return tuple(proposals)


__all__ = [
    "MAX_DOCKING_CANDIDATES",
    "MAX_DOCKING_REFINEMENT_STEPS",
    "MAX_DOCKING_TOP_K",
    "MAX_DOCKING_TORSIONS",
    "DockingBudget",
    "DockingProposal",
    "DockingProposalError",
    "TorsionSearchSpace",
    "generate_bounded_docking_proposals",
]
