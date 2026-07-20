"""Deterministic bounded torsion and rigid-body docking proposal generation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise DockingProposalError(f"{field_name} must be a lowercase SHA-256")
    return text


def _frozen_tensor(value: torch.Tensor, *, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise DockingProposalError(f"{name} must be a torch.Tensor")
    return value.detach().clone().contiguous().requires_grad_(False)


@dataclass(frozen=True)
class DockingBudget:
    candidate_count: int = 64
    top_k: int = 10
    max_torsions: int = 32
    max_refinement_steps: int = 0
    translation_radius_angstrom: float = 4.0
    seed: int = 7301

    def __post_init__(self) -> None:
        candidate_count = int(self.candidate_count)
        top_k = int(self.top_k)
        max_torsions = int(self.max_torsions)
        max_refinement_steps = int(self.max_refinement_steps)
        seed = int(self.seed)
        if candidate_count < 1 or candidate_count > MAX_DOCKING_CANDIDATES:
            raise DockingProposalError(
                f"candidate_count must be in [1, {MAX_DOCKING_CANDIDATES}]"
            )
        if top_k < 1 or top_k > min(candidate_count, MAX_DOCKING_TOP_K):
            raise DockingProposalError(
                f"top_k must be in [1, min(candidate_count, {MAX_DOCKING_TOP_K})]"
            )
        if max_torsions < 0 or max_torsions > MAX_DOCKING_TORSIONS:
            raise DockingProposalError(
                f"max_torsions must be in [0, {MAX_DOCKING_TORSIONS}]"
            )
        if (
            max_refinement_steps < 0
            or max_refinement_steps > MAX_DOCKING_REFINEMENT_STEPS
        ):
            raise DockingProposalError(
                f"max_refinement_steps must be in [0, {MAX_DOCKING_REFINEMENT_STEPS}]"
            )
        radius = float(self.translation_radius_angstrom)
        if not math.isfinite(radius) or radius < 0.0:
            raise DockingProposalError(
                "translation_radius_angstrom must be finite and non-negative"
            )
        if seed < 0 or seed > 2**63 - 1:
            raise DockingProposalError("seed must be in [0,2**63-1]")
        object.__setattr__(self, "candidate_count", candidate_count)
        object.__setattr__(self, "top_k", top_k)
        object.__setattr__(self, "max_torsions", max_torsions)
        object.__setattr__(self, "max_refinement_steps", max_refinement_steps)
        object.__setattr__(self, "translation_radius_angstrom", radius)
        object.__setattr__(self, "seed", seed)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "max_torsions": self.max_torsions,
            "max_refinement_steps": self.max_refinement_steps,
            "translation_radius_angstrom": self.translation_radius_angstrom,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class TorsionSearchSpace:
    local_offsets: torch.Tensor
    parent: torch.Tensor
    local_axes: torch.Tensor
    rotatable_mask: torch.Tensor
    root_positions: torch.Tensor | None = None
    _frozen_fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        local_offsets = _frozen_tensor(self.local_offsets, name="local_offsets")
        parent = _frozen_tensor(self.parent, name="parent")
        local_axes = _frozen_tensor(self.local_axes, name="local_axes")
        rotatable_mask = _frozen_tensor(
            self.rotatable_mask, name="rotatable_mask"
        )
        root_positions = (
            None
            if self.root_positions is None
            else _frozen_tensor(self.root_positions, name="root_positions")
        )
        object.__setattr__(self, "local_offsets", local_offsets)
        object.__setattr__(self, "parent", parent)
        object.__setattr__(self, "local_axes", local_axes)
        object.__setattr__(self, "rotatable_mask", rotatable_mask)
        object.__setattr__(self, "root_positions", root_positions)

        atom_count = (
            int(local_offsets.shape[0]) if local_offsets.ndim == 2 else -1
        )
        if atom_count < 1 or local_offsets.shape != (atom_count, 3):
            raise DockingProposalError("local_offsets must have shape [N,3]")
        if parent.shape != (atom_count,) or parent.dtype != torch.long:
            raise DockingProposalError("parent must be torch.long with shape [N]")
        if local_axes.shape != (atom_count, 3):
            raise DockingProposalError("local_axes must have shape [N,3]")
        if rotatable_mask.shape != (atom_count,) or rotatable_mask.dtype != torch.bool:
            raise DockingProposalError(
                "rotatable_mask must be boolean with shape [N]"
            )
        if not local_offsets.is_floating_point() or not local_axes.is_floating_point():
            raise DockingProposalError("kinematic tensors must use floating dtypes")
        if local_offsets.dtype != local_axes.dtype:
            raise DockingProposalError(
                "local_offsets and local_axes must share a dtype"
            )
        if any(
            value.device.type != "cpu"
            for value in (local_offsets, parent, local_axes, rotatable_mask)
        ):
            raise DockingProposalError(
                "bounded docking proposal scaffold is CPU-only"
            )
        if root_positions is not None:
            if (
                root_positions.shape != (atom_count, 3)
                or root_positions.dtype != local_offsets.dtype
                or root_positions.device.type != "cpu"
                or not root_positions.is_floating_point()
            ):
                raise DockingProposalError(
                    "root_positions must be a CPU floating tensor with shape [N,3]"
                )
        for name, value in (
            ("local_offsets", local_offsets),
            ("local_axes", local_axes),
            ("root_positions", root_positions),
        ):
            if value is not None and not bool(torch.isfinite(value).all().item()):
                raise DockingProposalError(f"{name} must be finite")
        roots = parent == -1
        if bool((rotatable_mask & roots).any().item()):
            raise DockingProposalError(
                "root atoms cannot be marked as torsion variables"
            )
        torsion_tree_forward_kinematics(
            local_offsets,
            parent,
            torch.zeros(atom_count, dtype=local_offsets.dtype),
            local_axes=local_axes,
            root_positions=root_positions,
        )
        object.__setattr__(
            self,
            "_frozen_fingerprint_sha256",
            self._current_fingerprint_sha256(),
        )

    def _current_fingerprint_sha256(self) -> str:
        return search_space_fingerprint(
            local_offsets=self.local_offsets,
            parent=self.parent,
            local_axes=self.local_axes,
            rotatable_mask=self.rotatable_mask,
            root_positions=self.root_positions,
        )

    def assert_integrity(self) -> None:
        if self._current_fingerprint_sha256() != self._frozen_fingerprint_sha256:
            raise DockingProposalError(
                "torsion search-space tensors changed after construction"
            )

    @property
    def atom_count(self) -> int:
        return int(self.local_offsets.shape[0])

    @property
    def torsion_count(self) -> int:
        return int(self.rotatable_mask.sum().item())

    @property
    def fingerprint_sha256(self) -> str:
        self.assert_integrity()
        return self._frozen_fingerprint_sha256


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
    problem_fingerprint_sha256: str
    search_space_fingerprint_sha256: str
    coordinate_fingerprint_sha256: str
    parent_proposal_fingerprint_sha256: str = ""
    refiner_id: str = ""
    refiner_version: str = ""
    refinement_receipt_sha256: str = ""

    def __post_init__(self) -> None:
        coordinates = _frozen_tensor(self.coordinates, name="coordinates")
        torsion_angles = _frozen_tensor(
            self.torsion_angles, name="torsion_angles"
        )
        rotation = _frozen_tensor(self.rotation, name="rotation")
        translation = _frozen_tensor(self.translation, name="translation")
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "torsion_angles", torsion_angles)
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "translation", translation)

        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise DockingProposalError("candidate_id must be non-empty")
        object.__setattr__(self, "candidate_id", candidate_id)
        proposal_index = int(self.proposal_index)
        seed = int(self.seed)
        if proposal_index < 0:
            raise DockingProposalError("proposal_index must be non-negative")
        if seed < 0 or seed > 2**63 - 1:
            raise DockingProposalError("seed must be in [0,2**63-1]")
        object.__setattr__(self, "proposal_index", proposal_index)
        object.__setattr__(self, "seed", seed)

        atom_count = int(coordinates.shape[0]) if coordinates.ndim == 2 else -1
        if atom_count < 1 or coordinates.shape != (atom_count, 3):
            raise DockingProposalError(
                "proposal coordinates must have shape [N,3]"
            )
        if torsion_angles.shape != (atom_count,):
            raise DockingProposalError(
                "proposal torsion_angles must have shape [N]"
            )
        if rotation.shape != (3, 3) or translation.shape != (3,):
            raise DockingProposalError(
                "proposal rigid transform has invalid shape"
            )
        tensors = (coordinates, torsion_angles, rotation, translation)
        if not all(value.is_floating_point() for value in tensors):
            raise DockingProposalError("proposal tensors must be floating point")
        if len({value.dtype for value in tensors}) != 1:
            raise DockingProposalError("proposal tensors must share one dtype")
        if any(value.device.type != "cpu" for value in tensors):
            raise DockingProposalError("bounded docking proposals are CPU-only")
        if not all(bool(torch.isfinite(value).all().item()) for value in tensors):
            raise DockingProposalError("proposal tensors must be finite")

        fingerprint = _require_digest(
            self.fingerprint_sha256,
            field_name="fingerprint_sha256",
        )
        problem_fingerprint = _require_digest(
            self.problem_fingerprint_sha256,
            field_name="problem_fingerprint_sha256",
        )
        search_space_digest = _require_digest(
            self.search_space_fingerprint_sha256,
            field_name="search_space_fingerprint_sha256",
        )
        coordinate_digest = _require_digest(
            self.coordinate_fingerprint_sha256,
            field_name="coordinate_fingerprint_sha256",
        )
        parent_digest = _require_digest(
            self.parent_proposal_fingerprint_sha256,
            field_name="parent_proposal_fingerprint_sha256",
            allow_empty=True,
        )
        receipt = _require_digest(
            self.refinement_receipt_sha256,
            field_name="refinement_receipt_sha256",
            allow_empty=True,
        )
        refiner_id = str(self.refiner_id or "").strip()
        refiner_version = str(self.refiner_version or "").strip()
        if bool(parent_digest) != bool(refiner_id and refiner_version):
            raise DockingProposalError(
                "refined proposal lineage requires parent fingerprint and refiner identity"
            )
        observed_coordinate_digest = coordinate_fingerprint(coordinates)
        if coordinate_digest != observed_coordinate_digest:
            raise DockingProposalError(
                "coordinate_fingerprint_sha256 does not match proposal coordinates"
            )
        expected_fingerprint = _proposal_fingerprint(
            proposal_index=proposal_index,
            seed=seed,
            torsion_angles=torsion_angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=search_space_digest,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=parent_digest,
            refiner_id=refiner_id,
            refiner_version=refiner_version,
            refinement_receipt_sha256=receipt,
        )
        if fingerprint != expected_fingerprint:
            raise DockingProposalError(
                "fingerprint_sha256 does not match the complete proposal state"
            )
        object.__setattr__(self, "fingerprint_sha256", fingerprint)
        object.__setattr__(self, "problem_fingerprint_sha256", problem_fingerprint)
        object.__setattr__(
            self, "search_space_fingerprint_sha256", search_space_digest
        )
        object.__setattr__(
            self, "coordinate_fingerprint_sha256", coordinate_digest
        )
        object.__setattr__(
            self, "parent_proposal_fingerprint_sha256", parent_digest
        )
        object.__setattr__(self, "refiner_id", refiner_id)
        object.__setattr__(self, "refiner_version", refiner_version)
        object.__setattr__(self, "refinement_receipt_sha256", receipt)

    @property
    def refined(self) -> bool:
        return bool(self.parent_proposal_fingerprint_sha256)

    def assert_integrity(self) -> None:
        observed_coordinate_digest = coordinate_fingerprint(self.coordinates)
        if observed_coordinate_digest != self.coordinate_fingerprint_sha256:
            raise DockingProposalError(
                "proposal coordinates changed after construction"
            )
        observed_fingerprint = _proposal_fingerprint(
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=self.torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=observed_coordinate_digest,
            parent_proposal_fingerprint_sha256=(
                self.parent_proposal_fingerprint_sha256
            ),
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=self.refinement_receipt_sha256,
        )
        if observed_fingerprint != self.fingerprint_sha256:
            raise DockingProposalError(
                "proposal state changed after construction"
            )

    def with_refined_coordinates(
        self,
        coordinates: torch.Tensor,
        *,
        refiner_id: str,
        refiner_version: str,
        refinement_receipt_sha256: str = "",
    ) -> "DockingProposal":
        self.assert_integrity()
        if not str(refiner_id or "").strip() or not str(
            refiner_version or ""
        ).strip():
            raise DockingProposalError(
                "refined proposals require refiner ID and version"
            )
        frozen_coordinates = _frozen_tensor(coordinates, name="refined coordinates")
        receipt = _require_digest(
            refinement_receipt_sha256,
            field_name="refinement_receipt_sha256",
            allow_empty=True,
        )
        coordinate_digest = coordinate_fingerprint(frozen_coordinates)
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
            refiner_id=str(refiner_id).strip(),
            refiner_version=str(refiner_version).strip(),
            refinement_receipt_sha256=receipt,
        )
        return replace(
            self,
            coordinates=frozen_coordinates,
            fingerprint_sha256=fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=str(refiner_id).strip(),
            refiner_version=str(refiner_version).strip(),
            refinement_receipt_sha256=receipt,
        )


def _tensor_payload(tensor: torch.Tensor) -> list[float]:
    return [
        float(value)
        for value in tensor.detach()
        .to(dtype=torch.float64, device="cpu")
        .contiguous()
        .reshape(-1)
        .tolist()
    ]


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
        "schema_id": "betelgeuze.engine_v2_docking_proposal/2.1.0",
        "proposal_index": int(proposal_index),
        "seed": int(seed),
        "problem_fingerprint_sha256": problem_fingerprint_sha256,
        "search_space_fingerprint_sha256": search_space_fingerprint_sha256,
        "coordinate_fingerprint_sha256": coordinate_fingerprint_sha256,
        "parent_proposal_fingerprint_sha256": (
            parent_proposal_fingerprint_sha256
        ),
        "refiner_id": refiner_id,
        "refiner_version": refiner_version,
        "refinement_receipt_sha256": refinement_receipt_sha256,
        "torsion_angles": _tensor_payload(torsion_angles),
        "rotation": _tensor_payload(rotation),
        "translation": _tensor_payload(translation),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
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
    """Generate a deterministic baseline plus bounded torsion/rigid proposals."""

    if not isinstance(search_space, TorsionSearchSpace):
        raise TypeError("search_space must be TorsionSearchSpace")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    search_space.assert_integrity()
    if search_space.torsion_count > budget.max_torsions:
        raise DockingProposalError(
            f"search space has {search_space.torsion_count} torsions, exceeding budget {budget.max_torsions}"
        )
    problem_identity = problem or DockingProblemIdentity.unbound()
    if not isinstance(problem_identity, DockingProblemIdentity):
        raise TypeError("problem must be DockingProblemIdentity")
    problem_fingerprint = problem_identity.fingerprint_sha256
    space_fingerprint = search_space.fingerprint_sha256
    dtype = search_space.local_offsets.dtype
    generator = torch.Generator(device="cpu")
    generator.manual_seed(budget.seed)
    proposals: list[DockingProposal] = []
    for proposal_index in range(budget.candidate_count):
        search_space.assert_integrity()
        angles = torch.zeros(search_space.atom_count, dtype=dtype)
        if proposal_index > 0 and search_space.torsion_count:
            sampled = (
                torch.rand(
                    search_space.torsion_count,
                    generator=generator,
                    dtype=dtype,
                )
                * (2.0 * torch.pi)
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
            rigid_angle = (
                torch.rand((), generator=generator, dtype=dtype) * 2.0 - 1.0
            ) * torch.pi
            rotation = axis_angle_matrix(
                axis.unsqueeze(0), rigid_angle.unsqueeze(0)
            )[0]
            direction = _random_unit_axis(generator, dtype)
            radius = torch.rand((), generator=generator, dtype=dtype) ** (
                1.0 / 3.0
            )
            translation = (
                direction * radius * budget.translation_radius_angstrom
            )
        coordinates = kinematic.coordinates @ rotation.T + translation
        coordinate_digest = coordinate_fingerprint(coordinates)
        fingerprint = _proposal_fingerprint(
            proposal_index=proposal_index,
            seed=budget.seed,
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
                seed=budget.seed,
                fingerprint_sha256=fingerprint,
                problem_fingerprint_sha256=problem_fingerprint,
                search_space_fingerprint_sha256=space_fingerprint,
                coordinate_fingerprint_sha256=coordinate_digest,
            )
        )
    search_space.assert_integrity()
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
