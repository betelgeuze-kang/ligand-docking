"""Deterministic bounded torsion and rigid-body docking proposal generation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import torch

from betelgeuze_engine_v2.ai import torsion_tree_forward_kinematics
from .identity import (
    DockingProblemIdentity,
    coordinate_fingerprint,
    search_space_fingerprint,
)

if TYPE_CHECKING:
    from .problem import DockingProblemInput

MAX_DOCKING_TORSIONS = 64
MAX_DOCKING_CANDIDATES = 4096
MAX_DOCKING_TOP_K = 128
MAX_DOCKING_REFINEMENT_STEPS = 256
DOCKING_NUMERIC_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_numeric_policy/3.0.0"
)
DOCKING_CANDIDATE_ID_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_candidate_id/3.0.0"
)
DOCKING_PROPOSAL_SCHEMA_ID = "betelgeuze.engine_v2_docking_proposal/5.0.0"
DOCKING_TRANSLATION_PLACEMENT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_translation_placement_receipt/1.0.0"
)
DOCKING_SAMPLING_POLICY_ID = (
    "torch_cpu_uniform_torsion_shoemake_haar_so3_uniform_volume_ball/2.0.0"
)
DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID = (
    "torch_cpu_uniform_torsion_shoemake_haar_so3_steric_field_grid/1.0.0"
)
DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID = (
    "uniform_volume_ball_translation/1.0.0"
)
DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID = (
    "authenticated_receptor_steric_field_grid_translation/1.0.0"
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


def _canonical_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DockingProposalError(
            "docking proposal identity is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _generator_state_sha256(generator: torch.Generator) -> str:
    state = generator.get_state().detach().to(device="cpu", dtype=torch.uint8)
    return hashlib.sha256(bytes(state.tolist())).hexdigest()


@dataclass(frozen=True)
class DockingNumericPolicy:
    """Exact dtype, runtime, and RNG policy used by proposal generation."""

    coordinate_dtype: str
    torch_version: str = str(torch.__version__)
    rng_engine_id: str = "torch_cpu_default_generator_state/1.0.0"
    sampling_policy_id: str = DOCKING_SAMPLING_POLICY_ID
    translation_placement_policy_id: str = (
        DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID
    )
    translation_placement_plan_sha256: str = ""
    schema_id: str = DOCKING_NUMERIC_POLICY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != DOCKING_NUMERIC_POLICY_SCHEMA_ID:
            raise DockingProposalError("unsupported docking numeric policy")
        dtype = str(self.coordinate_dtype or "").strip()
        if dtype not in {"float32", "float64"}:
            raise DockingProposalError(
                "docking coordinate dtype must be float32 or float64"
            )
        for name in (
            "torch_version",
            "rng_engine_id",
            "sampling_policy_id",
            "translation_placement_policy_id",
        ):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise DockingProposalError(
                    f"{name} must be non-empty in the numeric policy"
                )
            object.__setattr__(self, name, value)
        placement_plan = _require_digest(
            self.translation_placement_plan_sha256,
            field_name="translation_placement_plan_sha256",
            allow_empty=True,
        )
        guided = bool(placement_plan)
        expected_sampling_policy = (
            DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID
            if guided
            else DOCKING_SAMPLING_POLICY_ID
        )
        expected_placement_policy = (
            DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
            if guided
            else DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID
        )
        if self.sampling_policy_id != expected_sampling_policy:
            raise DockingProposalError(
                "sampling policy and translation placement plan disagree"
            )
        if self.translation_placement_policy_id != expected_placement_policy:
            raise DockingProposalError(
                "translation placement policy and plan disagree"
            )
        object.__setattr__(self, "coordinate_dtype", dtype)
        object.__setattr__(
            self,
            "translation_placement_plan_sha256",
            placement_plan,
        )

    def to_dict(self) -> dict[str, object]:
        guided = bool(self.translation_placement_plan_sha256)
        return {
            "schema_id": self.schema_id,
            "coordinate_dtype": self.coordinate_dtype,
            "accumulation_policy": "coordinate_dtype_unless_component_declares_otherwise",
            "integer_index_dtype": "int64",
            "device": "cpu",
            "torch_version": self.torch_version,
            "rng_engine_id": self.rng_engine_id,
            "sampling_policy_id": self.sampling_policy_id,
            "translation_placement_policy_id": (
                self.translation_placement_policy_id
            ),
            "translation_placement_plan_sha256": (
                self.translation_placement_plan_sha256
            ),
            "candidate_zero_policy": "zero_torsion_identity_rotation_zero_translation",
            "torsion_sampling": "independent_uniform_closed_open_minus_pi_plus_pi",
            "rotation_sampling": (
                "shoemake_three_independent_uniforms_unit_quaternion_haar_so3"
            ),
            "quaternion_component_order": "x_y_z_w",
            "translation_direction_sampling": (
                None if guided else "normalized_three_normal_draws"
            ),
            "translation_radius_sampling": (
                None if guided else "cube_root_uniform_volume_ball"
            ),
            "translation_site_selection": (
                "deterministic_orientation_conditioned_steric_field_rank_cycle"
                if guided
                else None
            ),
            "per_candidate_draw_order": (
                "torsions_then_haar_u1_u2_u3_then_steric_field_site_selection"
                if guided
                else "torsions_then_haar_u1_u2_u3_then_translation_direction_then_radius"
            ),
            "deterministic_algorithms_enabled": (
                torch.are_deterministic_algorithms_enabled()
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class DockingTranslationPlacementReceipt:
    """Authenticated explanation of how one proposal translation was selected."""

    proposal_index: int
    placement_policy_id: str
    placement_plan_sha256: str
    problem_fingerprint_sha256: str
    search_space_fingerprint_sha256: str
    site_id: str
    site_index: int
    selected_rank: int
    evaluated_site_count: int
    translation_angstrom: tuple[float, float, float]
    blockers: tuple[str, ...]
    steric_overlap_penalty: float | None = None
    overlap_pair_count: int | None = None
    deep_overlap_pair_count: int | None = None
    pocket_outside_atom_count: int | None = None
    pocket_boundary_penalty: float | None = None
    minimum_surface_separation_angstrom: float | None = None
    schema_id: str = DOCKING_TRANSLATION_PLACEMENT_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != DOCKING_TRANSLATION_PLACEMENT_RECEIPT_SCHEMA_ID:
            raise DockingProposalError(
                "unsupported translation placement receipt schema"
            )
        proposal_index = int(self.proposal_index)
        if proposal_index < 0:
            raise DockingProposalError(
                "translation placement proposal_index must be non-negative"
            )
        policy_id = str(self.placement_policy_id or "").strip()
        if not policy_id:
            raise DockingProposalError(
                "translation placement policy ID must be non-empty"
            )
        plan_sha256 = _require_digest(
            self.placement_plan_sha256,
            field_name="placement_plan_sha256",
            allow_empty=True,
        )
        problem_sha256 = _require_digest(
            self.problem_fingerprint_sha256,
            field_name="problem_fingerprint_sha256",
        )
        search_sha256 = _require_digest(
            self.search_space_fingerprint_sha256,
            field_name="search_space_fingerprint_sha256",
        )
        site_id = str(self.site_id or "").strip()
        if not site_id:
            raise DockingProposalError(
                "translation placement site ID must be non-empty"
            )
        site_index = int(self.site_index)
        selected_rank = int(self.selected_rank)
        evaluated_site_count = int(self.evaluated_site_count)
        try:
            translation = tuple(float(value) for value in self.translation_angstrom)
        except (TypeError, ValueError) as exc:
            raise DockingProposalError(
                "translation placement must contain three finite values"
            ) from exc
        if len(translation) != 3 or any(
            not math.isfinite(value) for value in translation
        ):
            raise DockingProposalError(
                "translation placement must contain three finite values"
            )
        blockers = tuple(str(value or "").strip() for value in self.blockers)
        if (
            not blockers
            or any(not value for value in blockers)
            or len(blockers) != len(set(blockers))
        ):
            raise DockingProposalError(
                "translation placement blockers must be non-empty and unique"
            )
        guided = bool(plan_sha256)
        expected_policy = (
            DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
            if guided
            else DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID
        )
        if policy_id != expected_policy:
            raise DockingProposalError(
                "translation placement receipt policy and plan disagree"
            )
        metric_names = (
            "steric_overlap_penalty",
            "pocket_boundary_penalty",
            "minimum_surface_separation_angstrom",
        )
        metrics: dict[str, float | None] = {}
        for name in metric_names:
            value = getattr(self, name)
            if value is None:
                metrics[name] = None
                continue
            number = float(value)
            if not math.isfinite(number):
                raise DockingProposalError(f"{name} must be finite when present")
            if name != "minimum_surface_separation_angstrom" and number < 0.0:
                raise DockingProposalError(
                    f"{name} must be non-negative when present"
                )
            metrics[name] = number
        count_names = (
            "overlap_pair_count",
            "deep_overlap_pair_count",
            "pocket_outside_atom_count",
        )
        counts: dict[str, int | None] = {}
        for name in count_names:
            value = getattr(self, name)
            if value is None:
                counts[name] = None
                continue
            if isinstance(value, bool):
                raise DockingProposalError(f"{name} must be an integer when present")
            number = int(value)
            if number < 0 or number != value:
                raise DockingProposalError(
                    f"{name} must be a non-negative integer when present"
                )
            counts[name] = number
        if guided:
            if (
                site_index < 0
                or selected_rank < 0
                or evaluated_site_count < 1
                or selected_rank >= evaluated_site_count
                or any(value is None for value in metrics.values())
                or any(value is None for value in counts.values())
            ):
                raise DockingProposalError(
                    "steric-field placement receipt is incomplete"
                )
        elif (
            site_index != -1
            or selected_rank != -1
            or evaluated_site_count != 0
            or any(value is not None for value in metrics.values())
            or any(value is not None for value in counts.values())
        ):
            raise DockingProposalError(
                "uniform translation receipt must not claim field evaluation"
            )
        object.__setattr__(self, "proposal_index", proposal_index)
        object.__setattr__(self, "placement_policy_id", policy_id)
        object.__setattr__(self, "placement_plan_sha256", plan_sha256)
        object.__setattr__(self, "problem_fingerprint_sha256", problem_sha256)
        object.__setattr__(self, "search_space_fingerprint_sha256", search_sha256)
        object.__setattr__(self, "site_id", site_id)
        object.__setattr__(self, "site_index", site_index)
        object.__setattr__(self, "selected_rank", selected_rank)
        object.__setattr__(self, "evaluated_site_count", evaluated_site_count)
        object.__setattr__(self, "translation_angstrom", translation)
        object.__setattr__(self, "blockers", blockers)
        for name, value in metrics.items():
            object.__setattr__(self, name, value)
        for name, value in counts.items():
            object.__setattr__(self, name, value)

    def _payload(self) -> dict[str, object]:
        def optional_hex(value: float | None) -> str | None:
            return None if value is None else value.hex()

        return {
            "schema_id": self.schema_id,
            "proposal_index": self.proposal_index,
            "placement_policy_id": self.placement_policy_id,
            "placement_plan_sha256": self.placement_plan_sha256,
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "site_id": self.site_id,
            "site_index": self.site_index,
            "selected_rank": self.selected_rank,
            "evaluated_site_count": self.evaluated_site_count,
            "translation_angstrom_hex": [
                value.hex() for value in self.translation_angstrom
            ],
            "steric_overlap_penalty_hex": optional_hex(
                self.steric_overlap_penalty
            ),
            "overlap_pair_count": self.overlap_pair_count,
            "deep_overlap_pair_count": self.deep_overlap_pair_count,
            "pocket_outside_atom_count": self.pocket_outside_atom_count,
            "pocket_boundary_penalty_hex": optional_hex(
                self.pocket_boundary_penalty
            ),
            "minimum_surface_separation_angstrom_hex": optional_hex(
                self.minimum_surface_separation_angstrom
            ),
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def translation_tensor(self, *, dtype: torch.dtype) -> torch.Tensor:
        return torch.tensor(self.translation_angstrom, dtype=dtype)


@runtime_checkable
class DockingTranslationPlacementPlan(Protocol):
    """Protocol for a bounded, authenticated translation-placement plan."""

    @property
    def placement_policy_id(self) -> str:
        ...

    @property
    def problem_fingerprint_sha256(self) -> str:
        ...

    @property
    def search_space_fingerprint_sha256(self) -> str:
        ...

    @property
    def blockers(self) -> tuple[str, ...]:
        ...

    @property
    def fingerprint_sha256(self) -> str:
        ...

    def assert_integrity(self) -> None:
        ...

    def place(
        self,
        oriented_coordinates: torch.Tensor,
        *,
        proposal_index: int,
        translation_radius_angstrom: float,
    ) -> DockingTranslationPlacementReceipt:
        ...


def _candidate_id(
    *,
    proposal_index: int,
    seed: int,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
    numeric_policy_sha256: str,
    rng_state_before_sha256: str,
    translation_placement_plan_sha256: str,
) -> str:
    digest = _canonical_sha256(
        {
            "schema_id": DOCKING_CANDIDATE_ID_SCHEMA_ID,
            "proposal_index": int(proposal_index),
            "seed": int(seed),
            "problem_fingerprint_sha256": problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (
                search_space_fingerprint_sha256
            ),
            "numeric_policy_sha256": numeric_policy_sha256,
            "rng_state_before_sha256": rng_state_before_sha256,
            "translation_placement_plan_sha256": (
                translation_placement_plan_sha256
            ),
        }
    )
    return f"pose-{int(proposal_index):05d}-{digest[:16]}"


def _proposal_fingerprint(
    *,
    candidate_id: str,
    proposal_index: int,
    seed: int,
    torsion_angles: torch.Tensor,
    rotation: torch.Tensor,
    translation: torch.Tensor,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
    coordinate_fingerprint_sha256: str,
    numeric_policy_sha256: str,
    rng_state_before_sha256: str,
    rng_state_after_sha256: str,
    translation_placement_receipt_sha256: str,
    parent_proposal_fingerprint_sha256: str = "",
    refiner_id: str = "",
    refiner_version: str = "",
    refinement_receipt_sha256: str = "",
) -> str:
    payload = {
        "schema_id": DOCKING_PROPOSAL_SCHEMA_ID,
        "candidate_id": candidate_id,
        "proposal_index": int(proposal_index),
        "seed": int(seed),
        "problem_fingerprint_sha256": problem_fingerprint_sha256,
        "search_space_fingerprint_sha256": search_space_fingerprint_sha256,
        "coordinate_fingerprint_sha256": coordinate_fingerprint_sha256,
        "numeric_policy_sha256": numeric_policy_sha256,
        "rng_state_before_sha256": rng_state_before_sha256,
        "rng_state_after_sha256": rng_state_after_sha256,
        "translation_placement_receipt_sha256": (
            translation_placement_receipt_sha256
        ),
        "parent_proposal_fingerprint_sha256": parent_proposal_fingerprint_sha256,
        "refiner_id": refiner_id,
        "refiner_version": refiner_version,
        "refinement_receipt_sha256": refinement_receipt_sha256,
        "torsion_angles": _tensor_payload(torsion_angles),
        "rotation": _tensor_payload(rotation),
        "translation": _tensor_payload(translation),
    }
    return _canonical_sha256(payload)


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
    numeric_policy_sha256: str
    rng_state_before_sha256: str
    rng_state_after_sha256: str
    translation_placement_receipt: DockingTranslationPlacementReceipt
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
        numeric_policy_digest = _require_digest(
            self.numeric_policy_sha256,
            field_name="numeric_policy_sha256",
        )
        rng_state_before = _require_digest(
            self.rng_state_before_sha256,
            field_name="rng_state_before_sha256",
        )
        rng_state_after = _require_digest(
            self.rng_state_after_sha256,
            field_name="rng_state_after_sha256",
        )
        placement_receipt = self.translation_placement_receipt
        if not isinstance(
            placement_receipt,
            DockingTranslationPlacementReceipt,
        ):
            raise DockingProposalError(
                "translation_placement_receipt has the wrong type"
            )
        if (
            placement_receipt.proposal_index != proposal_index
            or placement_receipt.problem_fingerprint_sha256
            != problem_fingerprint
            or placement_receipt.search_space_fingerprint_sha256
            != search_fingerprint
        ):
            raise DockingProposalError(
                "translation placement receipt is cross-wired"
            )
        receipt_translation = placement_receipt.translation_tensor(
            dtype=translation.dtype
        )
        if not torch.equal(receipt_translation, translation):
            raise DockingProposalError(
                "translation placement receipt does not match proposal translation"
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
        expected_candidate_id = _candidate_id(
            proposal_index=proposal_index,
            seed=seed,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=search_fingerprint,
            numeric_policy_sha256=numeric_policy_digest,
            rng_state_before_sha256=rng_state_before,
            translation_placement_plan_sha256=(
                placement_receipt.placement_plan_sha256
            ),
        )
        if candidate_id != expected_candidate_id:
            raise DockingProposalError(
                "candidate_id does not match the canonical candidate identity"
            )
        expected_fingerprint = _proposal_fingerprint(
            candidate_id=candidate_id,
            proposal_index=proposal_index,
            seed=seed,
            torsion_angles=torsion_angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=search_fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            numeric_policy_sha256=numeric_policy_digest,
            rng_state_before_sha256=rng_state_before,
            rng_state_after_sha256=rng_state_after,
            translation_placement_receipt_sha256=(
                placement_receipt.fingerprint_sha256
            ),
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
            "numeric_policy_sha256",
            numeric_policy_digest,
        )
        object.__setattr__(
            self,
            "rng_state_before_sha256",
            rng_state_before,
        )
        object.__setattr__(
            self,
            "rng_state_after_sha256",
            rng_state_after,
        )
        object.__setattr__(
            self,
            "translation_placement_receipt",
            placement_receipt,
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

    def assert_integrity(self) -> None:
        coordinate_digest = coordinate_fingerprint(self.coordinates)
        if coordinate_digest != self.coordinate_fingerprint_sha256:
            raise DockingProposalError(
                "proposal coordinates changed after construction"
            )
        observed = _proposal_fingerprint(
            candidate_id=self.candidate_id,
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=self.torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
            numeric_policy_sha256=self.numeric_policy_sha256,
            rng_state_before_sha256=self.rng_state_before_sha256,
            rng_state_after_sha256=self.rng_state_after_sha256,
            translation_placement_receipt_sha256=(
                self.translation_placement_receipt.fingerprint_sha256
            ),
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
        receipt = _require_digest(
            refinement_receipt_sha256,
            field_name="refinement_receipt_sha256",
            allow_empty=True,
        )
        coordinate_digest = coordinate_fingerprint(frozen_coordinates)
        fingerprint = _proposal_fingerprint(
            candidate_id=self.candidate_id,
            proposal_index=self.proposal_index,
            seed=self.seed,
            torsion_angles=self.torsion_angles,
            rotation=self.rotation,
            translation=self.translation,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
            numeric_policy_sha256=self.numeric_policy_sha256,
            rng_state_before_sha256=self.rng_state_before_sha256,
            rng_state_after_sha256=self.rng_state_after_sha256,
            translation_placement_receipt_sha256=(
                self.translation_placement_receipt.fingerprint_sha256
            ),
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=normalized_refiner_id,
            refiner_version=normalized_refiner_version,
            refinement_receipt_sha256=receipt,
        )
        return replace(
            self,
            coordinates=frozen_coordinates,
            fingerprint_sha256=fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            parent_proposal_fingerprint_sha256=self.fingerprint_sha256,
            refiner_id=normalized_refiner_id,
            refiner_version=normalized_refiner_version,
            refinement_receipt_sha256=receipt,
        )


def _random_unit_axis(generator: torch.Generator, dtype: torch.dtype) -> torch.Tensor:
    axis = torch.randn(3, generator=generator, dtype=dtype)
    norm = torch.linalg.vector_norm(axis)
    if float(norm.item()) <= 1.0e-12:
        return torch.tensor([0.0, 0.0, 1.0], dtype=dtype)
    return axis / norm


def _haar_rotation_matrix(
    generator: torch.Generator,
    dtype: torch.dtype,
) -> torch.Tensor:
    """Sample one deterministic Shoemake unit quaternion and SO(3) matrix."""

    uniforms = torch.rand(3, generator=generator, dtype=dtype)
    u1, u2, u3 = uniforms.unbind()
    first_radius = torch.sqrt(1.0 - u1)
    second_radius = torch.sqrt(u1)
    first_angle = 2.0 * torch.pi * u2
    second_angle = 2.0 * torch.pi * u3
    x = first_radius * torch.sin(first_angle)
    y = first_radius * torch.cos(first_angle)
    z = second_radius * torch.sin(second_angle)
    w = second_radius * torch.cos(second_angle)
    two = torch.tensor(2.0, dtype=dtype)
    return torch.stack(
        (
            1.0 - two * (y * y + z * z),
            two * (x * y - z * w),
            two * (x * z + y * w),
            two * (x * y + z * w),
            1.0 - two * (x * x + z * z),
            two * (y * z - x * w),
            two * (x * z - y * w),
            two * (y * z + x * w),
            1.0 - two * (x * x + y * y),
        )
    ).reshape(3, 3)


def _uniform_translation_placement_receipt(
    *,
    proposal_index: int,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
    translation: torch.Tensor,
) -> DockingTranslationPlacementReceipt:
    translation_values = translation.tolist()
    return DockingTranslationPlacementReceipt(
        proposal_index=proposal_index,
        placement_policy_id=DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID,
        placement_plan_sha256="",
        problem_fingerprint_sha256=problem_fingerprint_sha256,
        search_space_fingerprint_sha256=search_space_fingerprint_sha256,
        site_id=(
            "baseline-zero-translation"
            if proposal_index == 0
            else "uniform-volume-ball-sample"
        ),
        site_index=-1,
        selected_rank=-1,
        evaluated_site_count=0,
        translation_angstrom=(
            float(translation_values[0]),
            float(translation_values[1]),
            float(translation_values[2]),
        ),
        blockers=("receptor_steric_field_not_used_for_translation_placement",),
    )


def generate_bounded_docking_proposals(
    search_space: TorsionSearchSpace,
    budget: DockingBudget,
    *,
    problem: DockingProblemIdentity | DockingProblemInput | None = None,
    translation_placement_plan: DockingTranslationPlacementPlan | None = None,
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
    from .problem import DockingProblemInput

    if isinstance(problem, DockingProblemInput):
        problem.assert_integrity()
        if (
            problem.search_space.fingerprint_sha256
            != search_space.fingerprint_sha256
        ):
            raise DockingProposalError(
                "authenticated docking input is cross-wired to another search space"
            )
        problem_identity = problem.identity
    else:
        problem_identity = problem or DockingProblemIdentity.unbound()
    if not isinstance(problem_identity, DockingProblemIdentity):
        raise TypeError("problem must be DockingProblemIdentity")
    problem_fingerprint = problem_identity.fingerprint_sha256
    search_fingerprint = search_space.fingerprint_sha256
    placement_plan_sha256 = ""
    if translation_placement_plan is not None:
        if not isinstance(
            translation_placement_plan,
            DockingTranslationPlacementPlan,
        ):
            raise TypeError(
                "translation_placement_plan must satisfy "
                "DockingTranslationPlacementPlan"
            )
        translation_placement_plan.assert_integrity()
        placement_plan_sha256 = translation_placement_plan.fingerprint_sha256
        if (
            translation_placement_plan.placement_policy_id
            != DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
            or translation_placement_plan.problem_fingerprint_sha256
            != problem_fingerprint
            or translation_placement_plan.search_space_fingerprint_sha256
            != search_fingerprint
        ):
            raise DockingProposalError(
                "translation placement plan is cross-wired to another problem or space"
            )
    dtype = search_space.local_offsets.dtype
    numeric_policy = DockingNumericPolicy(
        coordinate_dtype=str(dtype).removeprefix("torch."),
        sampling_policy_id=(
            DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID
            if placement_plan_sha256
            else DOCKING_SAMPLING_POLICY_ID
        ),
        translation_placement_policy_id=(
            DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
            if placement_plan_sha256
            else DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID
        ),
        translation_placement_plan_sha256=placement_plan_sha256,
    )
    numeric_policy_sha256 = numeric_policy.fingerprint_sha256
    generator = torch.Generator(device="cpu")
    generator.manual_seed(budget.seed)
    proposals: list[DockingProposal] = []
    for proposal_index in range(budget.candidate_count):
        search_space.assert_integrity()
        rng_state_before_sha256 = _generator_state_sha256(generator)
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
        else:
            rotation = _haar_rotation_matrix(generator, dtype)
        oriented_coordinates = kinematic.coordinates @ rotation.T
        if translation_placement_plan is not None:
            translation_placement_plan.assert_integrity()
            placement_receipt = translation_placement_plan.place(
                oriented_coordinates,
                proposal_index=proposal_index,
                translation_radius_angstrom=(
                    budget.translation_radius_angstrom
                ),
            )
            if not isinstance(
                placement_receipt,
                DockingTranslationPlacementReceipt,
            ):
                raise DockingProposalError(
                    "translation placement plan returned an invalid receipt"
                )
            translation = placement_receipt.translation_tensor(dtype=dtype)
        elif proposal_index == 0:
            translation = torch.zeros(3, dtype=dtype)
            placement_receipt = _uniform_translation_placement_receipt(
                proposal_index=proposal_index,
                problem_fingerprint_sha256=problem_fingerprint,
                search_space_fingerprint_sha256=search_fingerprint,
                translation=translation,
            )
        else:
            direction = _random_unit_axis(generator, dtype)
            radius = torch.rand((), generator=generator, dtype=dtype) ** (
                1.0 / 3.0
            )
            translation = (
                direction * radius * budget.translation_radius_angstrom
            )
            placement_receipt = _uniform_translation_placement_receipt(
                proposal_index=proposal_index,
                problem_fingerprint_sha256=problem_fingerprint,
                search_space_fingerprint_sha256=search_fingerprint,
                translation=translation,
            )
        coordinates = oriented_coordinates + translation
        rng_state_after_sha256 = _generator_state_sha256(generator)
        coordinate_digest = coordinate_fingerprint(coordinates)
        candidate_id = _candidate_id(
            proposal_index=proposal_index,
            seed=budget.seed,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=search_fingerprint,
            numeric_policy_sha256=numeric_policy_sha256,
            rng_state_before_sha256=rng_state_before_sha256,
            translation_placement_plan_sha256=placement_plan_sha256,
        )
        fingerprint = _proposal_fingerprint(
            candidate_id=candidate_id,
            proposal_index=proposal_index,
            seed=budget.seed,
            torsion_angles=angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=problem_fingerprint,
            search_space_fingerprint_sha256=search_fingerprint,
            coordinate_fingerprint_sha256=coordinate_digest,
            numeric_policy_sha256=numeric_policy_sha256,
            rng_state_before_sha256=rng_state_before_sha256,
            rng_state_after_sha256=rng_state_after_sha256,
            translation_placement_receipt_sha256=(
                placement_receipt.fingerprint_sha256
            ),
        )
        proposals.append(
            DockingProposal(
                candidate_id=candidate_id,
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
                numeric_policy_sha256=numeric_policy_sha256,
                rng_state_before_sha256=rng_state_before_sha256,
                rng_state_after_sha256=rng_state_after_sha256,
                translation_placement_receipt=placement_receipt,
            )
        )
    search_space.assert_integrity()
    return tuple(proposals)


__all__ = [
    "DOCKING_CANDIDATE_ID_SCHEMA_ID",
    "DOCKING_NUMERIC_POLICY_SCHEMA_ID",
    "DOCKING_PROPOSAL_SCHEMA_ID",
    "DOCKING_SAMPLING_POLICY_ID",
    "DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID",
    "DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID",
    "DOCKING_TRANSLATION_PLACEMENT_RECEIPT_SCHEMA_ID",
    "DOCKING_UNIFORM_TRANSLATION_PLACEMENT_POLICY_ID",
    "MAX_DOCKING_CANDIDATES",
    "MAX_DOCKING_REFINEMENT_STEPS",
    "MAX_DOCKING_TOP_K",
    "MAX_DOCKING_TORSIONS",
    "DockingBudget",
    "DockingNumericPolicy",
    "DockingProposal",
    "DockingProposalError",
    "DockingTranslationPlacementPlan",
    "DockingTranslationPlacementReceipt",
    "TorsionSearchSpace",
    "generate_bounded_docking_proposals",
]
