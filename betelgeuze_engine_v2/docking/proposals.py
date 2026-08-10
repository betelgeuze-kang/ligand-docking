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
PROPOSAL_NUMERIC_POLICY_ID = (
    "betelgeuze.engine_v2_proposal_numeric_identity/1.0.0"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DockingProposalError(ValueError):
    """A docking proposal request exceeds the supported bounded scaffold."""


def _require_digest(value: object, *, field_name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise DockingProposalError(f"{field_name} must be a lowercase SHA-256")
    return text


def _frozen_tensor(value: object, *, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor):
        raise DockingProposalError(f"{name} must be a torch.Tensor")
    return value.detach().clone().contiguous().requires_grad_(False)


def _finite_cpu_floating(value: torch.Tensor, *, name: str) -> None:
    if not value.is_floating_point() or value.device.type != "cpu":
        raise DockingProposalError(f"{name} must be a CPU floating tensor")
    if not bool(torch.isfinite(value).all().item()):
        raise DockingProposalError(f"{name} must be finite")


def _tensor_payload(tensor: torch.Tensor) -> list[float]:
    return [
        float(value)
        for value in tensor.detach()
        .to(dtype=torch.float64, device="cpu")
        .contiguous()
        .reshape(-1)
        .tolist()
    ]


def _proposal_tensor_identity_payload(tensor: torch.Tensor) -> dict[str, object]:
    value = tensor.detach().to(device="cpu").contiguous()
    return {
        "dtype": str(value.dtype).removeprefix("torch."),
        "shape": [int(size) for size in value.shape],
        "values_binary64_hex": [
            float(item).hex() for item in value.reshape(-1).tolist()
        ],
    }


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
    payload = _proposal_identity_payload(
        proposal_index=proposal_index,
        seed=seed,
        torsion_angles=torsion_angles,
        rotation=rotation,
        translation=translation,
        problem_fingerprint_sha256=problem_fingerprint_sha256,
        search_space_fingerprint_sha256=search_space_fingerprint_sha256,
        coordinate_fingerprint_sha256=coordinate_fingerprint_sha256,
        parent_proposal_fingerprint_sha256=parent_proposal_fingerprint_sha256,
        refiner_id=refiner_id,
        refiner_version=refiner_version,
        refinement_receipt_sha256=refinement_receipt_sha256,
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _proposal_identity_payload(
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
) -> dict[str, object]:
    return {
        "schema_id": "betelgeuze.engine_v2_docking_proposal/3.0.0",
        "numeric_policy_id": PROPOSAL_NUMERIC_POLICY_ID,
        "proposal_index": int(proposal_index),
        "seed": int(seed),
        "problem_fingerprint_sha256": problem_fingerprint_sha256,
        "search_space_fingerprint_sha256": search_space_fingerprint_sha256,
        "coordinate_fingerprint_sha256": coordinate_fingerprint_sha256,
        "parent_proposal_fingerprint_sha256": parent_proposal_fingerprint_sha256,
        "refiner_id": refiner_id,
        "refiner_version": refiner_version,
        "refinement_receipt_sha256": refinement_receipt_sha256,
        "torsion_angles": _proposal_tensor_identity_payload(torsion_angles),
        "rotation": _proposal_tensor_identity_payload(rotation),
        "translation": _proposal_tensor_identity_payload(translation),
    }


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
        if not 1 <= candidate_count <= MAX_DOCKING_CANDIDATES:
            raise DockingProposalError(
                f"candidate_count must be in [1, {MAX_DOCKING_CANDIDATES}]"
            )
        if not 1 <= top_k <= min(candidate_count, MAX_DOCKING_TOP_K):
            raise DockingProposalError(
                f"top_k must be in [1, min(candidate_count, {MAX_DOCKING_TOP_K})]"
            )
        if not 0 <= max_torsions <= MAX_DOCKING_TORSIONS:
            raise DockingProposalError(
                f"max_torsions must be in [0, {MAX_DOCKING_TORSIONS}]"
            )
        if not 0 <= max_refinement_steps <= MAX_DOCKING_REFINEMENT_STEPS:
            raise DockingProposalError(
                f"max_refinement_steps must be in [0, {MAX_DOCKING_REFINEMENT_STEPS}]"
            )
        radius = float(self.translation_radius_angstrom)
        if not math.isfinite(radius) or radius < 0.0:
            raise DockingProposalError(
                "translation_radius_angstrom must be finite and non-negative"
            )
        if not 0 <= seed <= 2**63 - 1:
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
            self.rotatable_mask,
            name="rotatable_mask",
        )
        atom_count = int(local_offsets.shape[0]) if local_offsets.ndim == 2 else -1
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
        _finite_cpu_floating(local_offsets, name="local_offsets")
        _finite_cpu_floating(local_axes, name="local_axes")
        if local_offsets.dtype != local_axes.dtype:
            raise DockingProposalError(
                "local_offsets and local_axes must share a dtype"
            )
        if parent.device.type != "cpu" or rotatable_mask.device.type != "cpu":
            raise DockingProposalError(
                "bounded docking proposal scaffold is CPU-only"
            )

        roots = parent == -1
        root_count = int(roots.sum().item())
        if root_count < 1:
            raise DockingProposalError(
                "the parent forest must contain at least one root"
            )
        if bool((rotatable_mask & roots).any().item()):
            raise DockingProposalError(
                "root atoms cannot be marked as torsion variables"
            )
        root_positions = (
            None
            if self.root_positions is None
            else _frozen_tensor(self.root_positions, name="root_positions")
        )
        if root_positions is not None:
            if root_positions.ndim == 1 and root_count == 1 and root_positions.shape == (3,):
                root_positions = root_positions.unsqueeze(0).contiguous()
            if root_positions.shape != (root_count, 3):
                raise DockingProposalError(
                    "root_positions must have shape [number_of_roots,3]"
                )
            _finite_cpu_floating(root_positions, name="root_positions")
            if root_positions.dtype != local_offsets.dtype:
                raise DockingProposalError(
                    "root_positions must share the coordinate dtype"
                )

        object.__setattr__(self, "local_offsets", local_offsets)
        object.__setattr__(self, "parent", parent)
        object.__setattr__(self, "local_axes", local_axes)
        object.__setattr__(self, "rotatable_mask", rotatable_mask)
        object.__setattr__(self, "root_positions", root_positions)
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
            self.torsion_angles,
            name="torsion_angles",
        )
        rotation = _frozen_tensor(self.rotation, name="rotation")
        translation = _frozen_tensor(self.translation, name="translation")
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
        for name, value in zip(
            ("coordinates", "torsion_angles", "rotation", "translation"),
            tensors,
            strict=True,
        ):
            _finite_cpu_floating(value, name=name)
        if len({value.dtype for value in tensors}) != 1:
            raise DockingProposalError("proposal tensors must share one dtype")

        candidate_id = str(self.candidate_id or "").strip()
        proposal_index = int(self.proposal_index)
        seed = int(self.seed)
        if not candidate_id:
            raise DockingProposalError("candidate_id must be non-empty")
        if proposal_index < 0:
            raise DockingProposalError("proposal_index must be non-negative")
        if not 0 <= seed <= 2**63 - 1:
            raise DockingProposalError("seed must be in [0,2**63-1]")
        fingerprint = _require_digest(
            self.fingerprint_sha256,
            field_name="fingerprint_sha256",
        )
        problem_fingerprint = _require_digest(
            self.problem_fingerprint_sha256,
            field_name="problem_fingerprint_sha256",
        )
        search_fingerprint = _require_digest(
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
        refinement_receipt = _require_digest(
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
        if coordinate_digest != coordinate_fingerprint(coordinates):
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
            search_space_fingerprint_sha256=search_fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=parent_digest,
            refiner_id=refiner_id,
            refiner_version=refiner_version,
            refinement_receipt_sha256=refinement_receipt,
        )
        if fingerprint != expected_fingerprint:
            raise DockingProposalError(
                "fingerprint_sha256 does not match the complete proposal state"
            )
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "torsion_angles", torsion_angles)
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "translation", translation)
        object.__setattr__(self, "proposal_index", proposal_index)
        object.__setattr__(self, "seed", seed)
        object.__setattr__(self, "fingerprint_sha256", fingerprint)
        object.__setattr__(self, "problem_fingerprint_sha256", problem_fingerprint)
        object.__setattr__(
            self,
            "search_space_fingerprint_sha256",
            search_fingerprint,
        )
        object.__setattr__(
            self,
            "coordinate_fingerprint_sha256",
            coordinate_digest,
        )
        object.__setattr__(
            self,
            "parent_proposal_fingerprint_sha256",
            parent_digest,
        )
        object.__setattr__(self, "refiner_id", refiner_id)
        object.__setattr__(self, "refiner_version", refiner_version)
        object.__setattr__(
            self,
            "refinement_receipt_sha256",
            refinement_receipt,
        )

    @property
    def refined(self) -> bool:
        return bool(self.parent_proposal_fingerprint_sha256)

    def identity_payload(self) -> dict[str, object]:
        """Return the complete canonical payload whose SHA is the fingerprint."""

        self.assert_integrity()
        return _proposal_identity_payload(
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=self.torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=self.coordinate_fingerprint_sha256,
            parent_proposal_fingerprint_sha256=(
                self.parent_proposal_fingerprint_sha256
            ),
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=self.refinement_receipt_sha256,
        )

    def assert_integrity(self) -> None:
        coordinate_digest = coordinate_fingerprint(self.coordinates)
        if coordinate_digest != self.coordinate_fingerprint_sha256:
            raise DockingProposalError(
                "proposal coordinates changed after construction"
            )
        observed = _proposal_fingerprint(
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=self.torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=(
                self.parent_proposal_fingerprint_sha256
            ),
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=self.refinement_receipt_sha256,
        )
        if observed != self.fingerprint_sha256:
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
        torsion_angles: torch.Tensor | None = None,
    ) -> "DockingProposal":
        self.assert_integrity()
        normalized_refiner_id = str(refiner_id or "").strip()
        normalized_refiner_version = str(refiner_version or "").strip()
        if not normalized_refiner_id or not normalized_refiner_version:
            raise DockingProposalError(
                "refined proposals require refiner ID and version"
            )
        frozen_coordinates = _frozen_tensor(
            coordinates,
            name="refined coordinates",
        )
        if frozen_coordinates.shape != self.coordinates.shape:
            raise DockingProposalError(
                "refined coordinates must preserve the ligand atom count"
            )
        _finite_cpu_floating(frozen_coordinates, name="refined coordinates")
        if frozen_coordinates.dtype != self.coordinates.dtype:
            raise DockingProposalError(
                "refined coordinates must preserve the proposal dtype"
            )
        frozen_torsion_angles = (
            self.torsion_angles
            if torsion_angles is None
            else _frozen_tensor(torsion_angles, name="refined torsion angles")
        )
        if frozen_torsion_angles.shape != self.torsion_angles.shape:
            raise DockingProposalError(
                "refined torsion angles must preserve the ligand atom count"
            )
        _finite_cpu_floating(
            frozen_torsion_angles,
            name="refined torsion angles",
        )
        if frozen_torsion_angles.dtype != self.torsion_angles.dtype:
            raise DockingProposalError(
                "refined torsion angles must preserve the proposal dtype"
            )
        receipt = _require_digest(
            refinement_receipt_sha256,
            field_name="refinement_receipt_sha256",
            allow_empty=True,
        )
        coordinate_digest = coordinate_fingerprint(frozen_coordinates)
        fingerprint = _proposal_fingerprint(
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=frozen_torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=normalized_refiner_id,
            refiner_version=normalized_refiner_version,
            refinement_receipt_sha256=receipt,
        )
        return replace(
            self,
            coordinates=frozen_coordinates,
            torsion_angles=frozen_torsion_angles,
            fingerprint_sha256=fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=normalized_refiner_id,
            refiner_version=normalized_refiner_version,
            refinement_receipt_sha256=receipt,
        )


def bind_docking_proposal_state(
    *,
    coordinates: torch.Tensor,
    torsion_angles: torch.Tensor,
    rotation: torch.Tensor,
    translation: torch.Tensor,
    proposal_index: int,
    seed: int,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
    parent_proposal_fingerprint_sha256: str = "",
    refiner_id: str = "",
    refiner_version: str = "",
    refinement_receipt_sha256: str = "",
) -> DockingProposal:
    """Bind a complete proposal state without accepting caller fingerprint claims."""

    if not isinstance(coordinates, torch.Tensor):
        raise DockingProposalError("coordinates must be a torch.Tensor")
    coordinate_digest = coordinate_fingerprint(coordinates)
    fingerprint = _proposal_fingerprint(
        proposal_index=proposal_index,
        seed=seed,
        torsion_angles=torsion_angles,
        rotation=rotation,
        translation=translation,
        problem_fingerprint_sha256=problem_fingerprint_sha256,
        search_space_fingerprint_sha256=search_space_fingerprint_sha256,
        coordinate_fingerprint_sha256=coordinate_digest,
        parent_proposal_fingerprint_sha256=parent_proposal_fingerprint_sha256,
        refiner_id=refiner_id,
        refiner_version=refiner_version,
        refinement_receipt_sha256=refinement_receipt_sha256,
    )
    return DockingProposal(
        candidate_id=f"pose-{proposal_index:05d}-{fingerprint[:12]}",
        coordinates=coordinates,
        torsion_angles=torsion_angles,
        rotation=rotation,
        translation=translation,
        proposal_index=proposal_index,
        seed=seed,
        fingerprint_sha256=fingerprint,
        problem_fingerprint_sha256=problem_fingerprint_sha256,
        search_space_fingerprint_sha256=search_space_fingerprint_sha256,
        coordinate_fingerprint_sha256=coordinate_digest,
        parent_proposal_fingerprint_sha256=parent_proposal_fingerprint_sha256,
        refiner_id=refiner_id,
        refiner_version=refiner_version,
        refinement_receipt_sha256=refinement_receipt_sha256,
    )


def _random_unit_axis(generator: torch.Generator, dtype: torch.dtype) -> torch.Tensor:
    axis = torch.randn(3, generator=generator, dtype=dtype)
    norm = torch.linalg.vector_norm(axis)
    if float(norm.item()) <= 1.0e-12:
        return torch.tensor([0.0, 0.0, 1.0], dtype=dtype)
    return axis / norm


def generate_bounded_docking_proposals(
    search_space: TorsionSearchSpace,
    budget: DockingBudget,
    *,
    problem: DockingProblemIdentity | None = None,
    placement_center: torch.Tensor | None = None,
) -> tuple[DockingProposal, ...]:
    """Generate a deterministic baseline plus bounded torsion/rigid proposals."""

    if not isinstance(search_space, TorsionSearchSpace):
        raise TypeError("search_space must be TorsionSearchSpace")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    search_space.assert_integrity()
    if search_space.torsion_count > budget.max_torsions:
        raise DockingProposalError(
            f"search space has {search_space.torsion_count} torsions, "
            f"exceeding budget {budget.max_torsions}"
        )
    problem_identity = problem or DockingProblemIdentity.unbound()
    if not isinstance(problem_identity, DockingProblemIdentity):
        raise TypeError("problem must be DockingProblemIdentity")
    problem_fingerprint = problem_identity.fingerprint_sha256
    search_fingerprint = search_space.fingerprint_sha256
    dtype = search_space.local_offsets.dtype
    center = None
    if placement_center is not None:
        center = _frozen_tensor(placement_center, name="placement_center")
        if center.shape != (3,):
            raise DockingProposalError("placement_center must have shape [3]")
        _finite_cpu_floating(center, name="placement_center")
        if center.dtype != dtype:
            raise DockingProposalError(
                "placement_center must share the search-space dtype"
            )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(budget.seed)
    proposals: list[DockingProposal] = []
    for proposal_index in range(budget.candidate_count):
        search_space.assert_integrity()
        angles = torch.zeros(search_space.atom_count, dtype=dtype)
        if proposal_index > 0 and search_space.torsion_count:
            angles[search_space.rotatable_mask] = (
                torch.rand(
                    search_space.torsion_count,
                    generator=generator,
                    dtype=dtype,
                )
                * (2.0 * torch.pi)
                - torch.pi
            )
        kinematic = torsion_tree_forward_kinematics(
            search_space.local_offsets,
            search_space.parent,
            angles,
            local_axes=search_space.local_axes,
            root_positions=search_space.root_positions,
        )
        if proposal_index == 0:
            rotation = torch.eye(3, dtype=dtype)
            offset = torch.zeros(3, dtype=dtype)
        else:
            axis = _random_unit_axis(generator, dtype)
            rigid_angle = (
                torch.rand((), generator=generator, dtype=dtype) * 2.0 - 1.0
            ) * torch.pi
            rotation = axis_angle_matrix(
                axis.unsqueeze(0),
                rigid_angle.unsqueeze(0),
            )[0]
            direction = _random_unit_axis(generator, dtype)
            radius = torch.rand((), generator=generator, dtype=dtype) ** (
                1.0 / 3.0
            )
            offset = (
                direction * radius * budget.translation_radius_angstrom
            )
        if center is None:
            translation = offset
            coordinates = kinematic.coordinates @ rotation.T + translation
        else:
            ligand_centroid = kinematic.coordinates.mean(dim=0)
            translation = center + offset - ligand_centroid @ rotation.T
            coordinates = kinematic.coordinates @ rotation.T + translation
        coordinate_digest = coordinate_fingerprint(coordinates)
        fingerprint = _proposal_fingerprint(
            proposal_index=proposal_index,
            seed=budget.seed,
            torsion_angles=angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=search_fingerprint,
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
                search_space_fingerprint_sha256=search_fingerprint,
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
    "PROPOSAL_NUMERIC_POLICY_ID",
    "DockingBudget",
    "DockingProposal",
    "DockingProposalError",
    "TorsionSearchSpace",
    "bind_docking_proposal_state",
    "generate_bounded_docking_proposals",
]
