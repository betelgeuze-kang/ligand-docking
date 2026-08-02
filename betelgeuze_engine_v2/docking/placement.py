"""Deterministic pocket-centered proposal placement for authenticated docking.

The baseline proposal generator intentionally remains a generic bounded scaffold.
This module adds a known-pocket placement policy without copying the search,
validity, scoring, failure-row, or diversity-selection implementation.

A context-local proposal override feeds a precomputed immutable proposal batch
into the active :func:`run_bounded_docking_search` implementation.  The search
therefore retains all existing component binding, mutation protection, validity,
failure-complete accounting, score ordering, and top-k diversity semantics.

Rigid rotations use Shoemake's three-uniform construction for the Haar measure
on SO(3). A bounded center ensemble preserves multiple rotations/conformers at
the authenticated pocket center; remaining centroids are sampled uniformly by
volume inside the pocket sphere. The zero-index baseline retains zero torsions
and identity rotation.

The policy is a deterministic software contract, not a scientifically validated
pose generator or pocket model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any

import torch

from betelgeuze_engine_v2.ai import torsion_tree_forward_kinematics

from .authority import (
    AuthenticatedDockingProblem,
    AuthenticatedDockingSearchResult,
    DockingAuthorityError,
)
from .identity import coordinate_fingerprint
from .proposals import (
    DockingBudget,
    DockingProposal,
    TorsionSearchSpace,
)


POCKET_PLACEMENT_POLICY_SCHEMA_ID = "betelgeuze.engine_v2_pocket_placement_policy/1.1.0"
POCKET_PLACEMENT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_pocket_placement_receipt/1.1.0"
)
POCKET_PLACEMENT_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_pocket_placement_search_result/1.0.0"
)
POCKET_PLACEMENT_POLICY_ID = "betelgeuze.engine_v2_authenticated_pocket_placement/1.1.0"
HAAR_ROTATION_SAMPLER_ID = "shoemake_three_uniform_unit_quaternion/1.0.0"
SPHERICAL_TRANSLATION_SAMPLER_ID = "uniform_spherical_volume_centroid_offset/1.0.0"
CENTROID_POLICY_ID = "all_atom_arithmetic_centroid/1.0.0"
COUNTER_PRNG_ID = "sha256_counter_uniform_binary64/1.0.0"
MAX_POCKET_PLACEMENT_PROPOSALS = 4_096
MAX_POCKET_TRANSLATION_RADIUS_ANGSTROM = 100.0
_ROTATION_TOLERANCE = 1.0e-10
_CENTROID_TOLERANCE_ANGSTROM = 1.0e-10
CENTERED_CANDIDATE_FRACTION = 0.125


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingAuthorityError(
            "pocket-placement state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DockingAuthorityError("placement metadata floats must be finite")
        return float(value)
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item) for item in value)
    raise DockingAuthorityError("placement metadata must be canonical JSON-compatible")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _counter_uniform(
    *,
    seed: int,
    proposal_index: int,
    domain: str,
    counter: int,
) -> float:
    digest = hashlib.sha256(
        _canonical_bytes(
            {
                "prng_id": COUNTER_PRNG_ID,
                "seed": int(seed),
                "proposal_index": int(proposal_index),
                "domain": str(domain),
                "counter": int(counter),
            }
        )
    ).digest()
    integer = int.from_bytes(digest[:8], "big", signed=False)
    return (integer + 0.5) / float(1 << 64)


def _stable_candidate_id(
    *,
    proposal_index: int,
    seed: int,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
) -> str:
    identity = _sha256(
        {
            "schema_id": ("betelgeuze.engine_v2_docking_candidate_identity/1.0.0"),
            "proposal_index": int(proposal_index),
            "seed": int(seed),
            "problem_fingerprint_sha256": problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (search_space_fingerprint_sha256),
        }
    )
    return f"pose-{int(proposal_index):05d}-{identity[:12]}"


def _haar_rotation(
    *,
    seed: int,
    proposal_index: int,
    dtype: torch.dtype,
) -> torch.Tensor:
    if proposal_index == 0:
        return torch.eye(3, dtype=dtype)
    first = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain="haar-rotation",
        counter=0,
    )
    second = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain="haar-rotation",
        counter=1,
    )
    third = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain="haar-rotation",
        counter=2,
    )
    root_one_minus = math.sqrt(1.0 - first)
    root_first = math.sqrt(first)
    x = root_one_minus * math.sin(2.0 * math.pi * second)
    y = root_one_minus * math.cos(2.0 * math.pi * second)
    z = root_first * math.sin(2.0 * math.pi * third)
    w = root_first * math.cos(2.0 * math.pi * third)
    rotation = torch.tensor(
        [
            [
                1.0 - 2.0 * (y * y + z * z),
                2.0 * (x * y - z * w),
                2.0 * (x * z + y * w),
            ],
            [
                2.0 * (x * y + z * w),
                1.0 - 2.0 * (x * x + z * z),
                2.0 * (y * z - x * w),
            ],
            [
                2.0 * (x * z - y * w),
                2.0 * (y * z + x * w),
                1.0 - 2.0 * (x * x + y * y),
            ],
        ],
        dtype=dtype,
    )
    identity = torch.eye(3, dtype=dtype)
    orthogonality_error = float((rotation.T @ rotation - identity).abs().max().item())
    determinant = float(torch.linalg.det(rotation).item())
    if (
        orthogonality_error > _ROTATION_TOLERANCE
        or abs(determinant - 1.0) > _ROTATION_TOLERANCE
    ):
        raise DockingAuthorityError(
            "Haar rotation sampler produced an invalid proper rotation"
        )
    return rotation.contiguous()


def _uniform_spherical_offset(
    *,
    seed: int,
    proposal_index: int,
    radius_angstrom: float,
    dtype: torch.dtype,
) -> torch.Tensor:
    if proposal_index == 0 or radius_angstrom == 0.0:
        return torch.zeros(3, dtype=dtype)
    azimuth_uniform = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain="pocket-translation",
        counter=0,
    )
    z_uniform = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain="pocket-translation",
        counter=1,
    )
    radial_uniform = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain="pocket-translation",
        counter=2,
    )
    azimuth = 2.0 * math.pi * azimuth_uniform
    z_component = 2.0 * z_uniform - 1.0
    planar = math.sqrt(max(0.0, 1.0 - z_component * z_component))
    radius = radius_angstrom * radial_uniform ** (1.0 / 3.0)
    return torch.tensor(
        [
            radius * planar * math.cos(azimuth),
            radius * planar * math.sin(azimuth),
            radius * z_component,
        ],
        dtype=dtype,
    )


def _centered_candidate_count(
    candidate_count: int,
    configured_maximum: int,
) -> int:
    return min(
        configured_maximum,
        max(1, int(math.ceil(candidate_count * CENTERED_CANDIDATE_FRACTION))),
    )


def _torsion_angles(
    search_space: TorsionSearchSpace,
    *,
    seed: int,
    proposal_index: int,
) -> torch.Tensor:
    angles = torch.zeros(
        search_space.atom_count,
        dtype=search_space.local_offsets.dtype,
    )
    if proposal_index == 0:
        return angles
    rotatable_indices = (
        torch.nonzero(
            search_space.rotatable_mask,
            as_tuple=False,
        )
        .reshape(-1)
        .tolist()
    )
    for counter, atom_index in enumerate(rotatable_indices):
        uniform = _counter_uniform(
            seed=seed,
            proposal_index=proposal_index,
            domain="torsion-angle",
            counter=counter,
        )
        angles[int(atom_index)] = (2.0 * math.pi * uniform) - math.pi
    return angles


@dataclass(frozen=True, slots=True)
class PocketPlacementPolicy:
    policy_id: str = POCKET_PLACEMENT_POLICY_ID
    rotation_sampler_id: str = HAAR_ROTATION_SAMPLER_ID
    translation_sampler_id: str = SPHERICAL_TRANSLATION_SAMPLER_ID
    centroid_policy_id: str = CENTROID_POLICY_ID
    prng_id: str = COUNTER_PRNG_ID
    baseline_at_pocket_center: bool = True
    centered_candidate_count: int = 1
    metadata: Mapping[str, object] = field(default_factory=dict)
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        expected = {
            "policy_id": POCKET_PLACEMENT_POLICY_ID,
            "rotation_sampler_id": HAAR_ROTATION_SAMPLER_ID,
            "translation_sampler_id": SPHERICAL_TRANSLATION_SAMPLER_ID,
            "centroid_policy_id": CENTROID_POLICY_ID,
            "prng_id": COUNTER_PRNG_ID,
        }
        for field_name, expected_value in expected.items():
            if str(getattr(self, field_name)) != expected_value:
                raise DockingAuthorityError(
                    f"unsupported pocket placement {field_name}"
                )
        if self.baseline_at_pocket_center is not True:
            raise DockingAuthorityError(
                "the frozen placement baseline must be pocket-centered"
            )
        if (
            type(self.centered_candidate_count) is not int
            or not 1 <= self.centered_candidate_count <= 64
        ):
            raise DockingAuthorityError("centered_candidate_count must be in [1,64]")
        metadata = _freeze_json(dict(self.metadata))
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(
            self,
            "_fingerprint_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": POCKET_PLACEMENT_POLICY_SCHEMA_ID,
            "policy_id": self.policy_id,
            "rotation_sampler_id": self.rotation_sampler_id,
            "translation_sampler_id": self.translation_sampler_id,
            "centroid_policy_id": self.centroid_policy_id,
            "prng_id": self.prng_id,
            "baseline_at_pocket_center": self.baseline_at_pocket_center,
            "centered_candidate_count": self.centered_candidate_count,
            "centered_candidate_allocation": (
                "lowest_indices_min_configured_and_ceil_one_eighth_budget"
            ),
            "metadata": _thaw_json(self.metadata),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise DockingAuthorityError(
                "pocket placement policy changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "fingerprint_sha256": self.fingerprint_sha256,
        }


@dataclass(frozen=True, slots=True)
class PocketPlacementReceipt:
    authenticated_input_receipt_sha256: str
    placement_policy_sha256: str
    budget_sha256: str
    proposal_fingerprint_sha256s: tuple[str, ...]
    centroid_offset_angstroms: tuple[float, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for field_name in (
            "authenticated_input_receipt_sha256",
            "placement_policy_sha256",
            "budget_sha256",
        ):
            value = str(getattr(self, field_name) or "").lower()
            if len(value) != 64 or any(
                char not in "0123456789abcdef" for char in value
            ):
                raise DockingAuthorityError(f"{field_name} must be a SHA-256")
            object.__setattr__(self, field_name, value)
        fingerprints = tuple(str(value) for value in self.proposal_fingerprint_sha256s)
        if not fingerprints or any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in fingerprints
        ):
            raise DockingAuthorityError("proposal fingerprints are invalid")
        offsets = tuple(float(value) for value in self.centroid_offset_angstroms)
        if len(offsets) != len(fingerprints) or any(
            not math.isfinite(value) or value < 0.0 for value in offsets
        ):
            raise DockingAuthorityError("placement centroid offsets are invalid")
        object.__setattr__(self, "proposal_fingerprint_sha256s", fingerprints)
        object.__setattr__(self, "centroid_offset_angstroms", offsets)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": POCKET_PLACEMENT_RECEIPT_SCHEMA_ID,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "placement_policy_sha256": self.placement_policy_sha256,
            "budget_sha256": self.budget_sha256,
            "proposal_count": len(self.proposal_fingerprint_sha256s),
            "proposal_fingerprint_sha256s": list(self.proposal_fingerprint_sha256s),
            "centroid_offset_angstrom_binary64_hex": [
                value.hex() for value in self.centroid_offset_angstroms
            ],
            "failure_rows_retained_by_search": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError(
                "pocket placement receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class PocketPlacementSearchResult:
    placement_receipt: PocketPlacementReceipt
    authenticated_search_result: AuthenticatedDockingSearchResult
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.placement_receipt, PocketPlacementReceipt):
            raise TypeError("placement_receipt must be PocketPlacementReceipt")
        if not isinstance(
            self.authenticated_search_result,
            AuthenticatedDockingSearchResult,
        ):
            raise TypeError(
                "authenticated_search_result must be AuthenticatedDockingSearchResult"
            )
        if (
            self.placement_receipt.authenticated_input_receipt_sha256
            != self.authenticated_search_result.authenticated_input_receipt_sha256
        ):
            raise DockingAuthorityError(
                "placement and search authority receipts are cross-wired"
            )
        observed_proposals = tuple(
            row.proposal_fingerprint_sha256
            for row in self.authenticated_search_result.search_result.rows
        )
        if observed_proposals != self.placement_receipt.proposal_fingerprint_sha256s:
            raise DockingAuthorityError(
                "placement proposal batch and search rows are cross-wired"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": POCKET_PLACEMENT_SEARCH_RESULT_SCHEMA_ID,
            "placement_receipt_sha256": self.placement_receipt.receipt_sha256,
            "authenticated_search_receipt_sha256": (
                self.authenticated_search_result.receipt_sha256
            ),
            "authenticated_input_receipt_sha256": (
                self.placement_receipt.authenticated_input_receipt_sha256
            ),
            "search_fingerprint_sha256": (
                self.authenticated_search_result.search_result.search_fingerprint_sha256
            ),
            "scientifically_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError(
                "pocket placement search result changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "placement": self.placement_receipt.to_dict(),
            "search": self.authenticated_search_result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class _ProposalOverride:
    search_space_fingerprint_sha256: str
    budget_sha256: str
    problem_fingerprint_sha256: str
    proposals: tuple[DockingProposal, ...]


_PROPOSAL_OVERRIDE: ContextVar[_ProposalOverride | None] = ContextVar(
    "betelgeuze_pocket_proposal_override",
    default=None,
)


def _budget_sha256(budget: DockingBudget) -> str:
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_docking_budget_identity/1.0.0",
            "budget": budget.to_dict(),
        }
    )


def install_pocket_proposal_override() -> str:
    """Install one context-local dispatch around the active proposal generator."""

    from . import search as search_module

    marker = "_betelgeuze_pocket_proposal_override_sha256"
    existing = getattr(search_module, marker, None)
    if isinstance(existing, str):
        return existing
    original = search_module.generate_bounded_docking_proposals

    def dispatch(
        search_space: TorsionSearchSpace,
        budget: DockingBudget,
        *,
        problem=None,
        placement_center: torch.Tensor | None = None,
    ) -> tuple[DockingProposal, ...]:
        override = _PROPOSAL_OVERRIDE.get()
        if override is None:
            return original(
                search_space,
                budget,
                problem=problem,
                placement_center=placement_center,
            )
        problem_fingerprint = "" if problem is None else problem.fingerprint_sha256
        if (
            search_space.fingerprint_sha256 != override.search_space_fingerprint_sha256
            or _budget_sha256(budget) != override.budget_sha256
            or problem_fingerprint != override.problem_fingerprint_sha256
        ):
            raise DockingAuthorityError(
                "pocket proposal override is cross-wired to another search"
            )
        for proposal in override.proposals:
            proposal.assert_integrity()
        return override.proposals

    search_module.generate_bounded_docking_proposals = dispatch
    receipt = _sha256(
        {
            "schema_id": ("betelgeuze.engine_v2_pocket_proposal_dispatch/1.0.0"),
            "context_local": True,
            "generic_search_implementation_reused": True,
            "generic_generation_unchanged_without_override": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(search_module, marker, receipt)
    return receipt


def generate_pocket_centered_docking_proposals(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    *,
    policy: PocketPlacementPolicy | None = None,
) -> tuple[tuple[DockingProposal, ...], PocketPlacementReceipt]:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    authenticated_problem.input_receipt_sha256
    placement_policy = policy or PocketPlacementPolicy()
    if not isinstance(placement_policy, PocketPlacementPolicy):
        raise TypeError("policy must be PocketPlacementPolicy")
    search_space = authenticated_problem.search_space
    search_space.assert_integrity()
    if search_space.torsion_count > budget.max_torsions:
        raise DockingAuthorityError(
            "authenticated search space exceeds the torsion budget"
        )
    if not 1 <= budget.candidate_count <= MAX_POCKET_PLACEMENT_PROPOSALS:
        raise DockingAuthorityError("candidate count exceeds the placement hard bound")
    if (
        budget.translation_radius_angstrom
        > authenticated_problem.pocket.radius_angstrom
        or budget.translation_radius_angstrom > MAX_POCKET_TRANSLATION_RADIUS_ANGSTROM
    ):
        raise DockingAuthorityError(
            "placement translation radius exceeds the pocket authority bound"
        )
    from . import proposals as proposal_module

    proposals: list[DockingProposal] = []
    centroid_offsets: list[float] = []
    centered_count = _centered_candidate_count(
        budget.candidate_count,
        placement_policy.centered_candidate_count,
    )
    for proposal_index in range(budget.candidate_count):
        angles = _torsion_angles(
            search_space,
            seed=budget.seed,
            proposal_index=proposal_index,
        )
        conformer = torsion_tree_forward_kinematics(
            search_space.local_offsets,
            search_space.parent,
            angles,
            local_axes=search_space.local_axes,
            root_positions=search_space.root_positions,
        ).coordinates
        conformer_centroid = conformer.mean(dim=0)
        centered = conformer - conformer_centroid
        rotation = _haar_rotation(
            seed=budget.seed,
            proposal_index=proposal_index,
            dtype=conformer.dtype,
        )
        offset = (
            torch.zeros(3, dtype=conformer.dtype)
            if proposal_index < centered_count
            else _uniform_spherical_offset(
                seed=budget.seed,
                proposal_index=proposal_index,
                radius_angstrom=budget.translation_radius_angstrom,
                dtype=conformer.dtype,
            )
        )
        target_centroid = (
            authenticated_problem.pocket.center.to(dtype=conformer.dtype) + offset
        )
        coordinates = centered @ rotation.T + target_centroid
        observed_centroid = coordinates.mean(dim=0)
        centroid_error = float(
            torch.linalg.vector_norm(observed_centroid - target_centroid).item()
        )
        if centroid_error > _CENTROID_TOLERANCE_ANGSTROM:
            raise DockingAuthorityError(
                "pocket-centered placement centroid is numerically inconsistent"
            )
        centroid_offset = float(
            torch.linalg.vector_norm(
                observed_centroid
                - authenticated_problem.pocket.center.to(dtype=conformer.dtype)
            ).item()
        )
        if (
            centroid_offset
            > budget.translation_radius_angstrom + _CENTROID_TOLERANCE_ANGSTROM
        ):
            raise DockingAuthorityError(
                "pocket-centered proposal exceeds the translation bound"
            )
        translation = target_centroid - conformer_centroid @ rotation.T
        coordinate_digest = coordinate_fingerprint(coordinates)
        fingerprint = proposal_module._proposal_fingerprint(
            proposal_index=proposal_index,
            seed=budget.seed,
            torsion_angles=angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=(
                authenticated_problem.problem.fingerprint_sha256
            ),
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposal = DockingProposal(
            candidate_id=_stable_candidate_id(
                proposal_index=proposal_index,
                seed=budget.seed,
                problem_fingerprint_sha256=(
                    authenticated_problem.problem.fingerprint_sha256
                ),
                search_space_fingerprint_sha256=(search_space.fingerprint_sha256),
            ),
            coordinates=coordinates,
            torsion_angles=angles,
            rotation=rotation,
            translation=translation,
            proposal_index=proposal_index,
            seed=budget.seed,
            fingerprint_sha256=fingerprint,
            problem_fingerprint_sha256=(
                authenticated_problem.problem.fingerprint_sha256
            ),
            search_space_fingerprint_sha256=(search_space.fingerprint_sha256),
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposal.assert_integrity()
        proposals.append(proposal)
        centroid_offsets.append(centroid_offset)
    result = tuple(proposals)
    receipt = PocketPlacementReceipt(
        authenticated_input_receipt_sha256=(authenticated_problem.input_receipt_sha256),
        placement_policy_sha256=placement_policy.fingerprint_sha256,
        budget_sha256=_budget_sha256(budget),
        proposal_fingerprint_sha256s=tuple(
            proposal.fingerprint_sha256 for proposal in result
        ),
        centroid_offset_angstroms=tuple(centroid_offsets),
    )
    return result, receipt


def run_authenticated_pocket_placement_search(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    scorer,
    *,
    refiner=None,
    policy: PocketPlacementPolicy | None = None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
    precomputed_proposals: Sequence[DockingProposal] | None = None,
    precomputed_placement_receipt: PocketPlacementReceipt | None = None,
) -> PocketPlacementSearchResult:
    if (precomputed_proposals is None) is not (precomputed_placement_receipt is None):
        raise DockingAuthorityError(
            "precomputed pocket proposals and receipt must be supplied together"
        )
    if precomputed_proposals is None:
        proposals, placement_receipt = generate_pocket_centered_docking_proposals(
            authenticated_problem,
            budget,
            policy=policy,
        )
    else:
        proposals = tuple(precomputed_proposals)
        placement_receipt = precomputed_placement_receipt
        assert placement_receipt is not None
        if (
            len(proposals) != budget.candidate_count
            or placement_receipt.authenticated_input_receipt_sha256
            != authenticated_problem.input_receipt_sha256
            or placement_receipt.budget_sha256 != _budget_sha256(budget)
            or placement_receipt.proposal_fingerprint_sha256s
            != tuple(proposal.fingerprint_sha256 for proposal in proposals)
        ):
            raise DockingAuthorityError(
                "precomputed pocket proposal authority is cross-wired"
            )
        placement_receipt.receipt_sha256
        for proposal in proposals:
            proposal.assert_integrity()
    override = _ProposalOverride(
        search_space_fingerprint_sha256=(
            authenticated_problem.search_space.fingerprint_sha256
        ),
        budget_sha256=_budget_sha256(budget),
        problem_fingerprint_sha256=(authenticated_problem.problem.fingerprint_sha256),
        proposals=proposals,
    )
    token = _PROPOSAL_OVERRIDE.set(override)
    try:
        from . import authority as authority_module

        search_result = authority_module.run_authenticated_bounded_docking_search(
            authenticated_problem,
            budget,
            scorer,
            refiner=refiner,
            diversity_rmsd_angstrom=diversity_rmsd_angstrom,
            diversity_metric=diversity_metric,
            symmetry_permutations=symmetry_permutations,
        )
    finally:
        _PROPOSAL_OVERRIDE.reset(token)
    return PocketPlacementSearchResult(
        placement_receipt=placement_receipt,
        authenticated_search_result=search_result,
    )


__all__ = [
    "CENTROID_POLICY_ID",
    "COUNTER_PRNG_ID",
    "HAAR_ROTATION_SAMPLER_ID",
    "MAX_POCKET_PLACEMENT_PROPOSALS",
    "MAX_POCKET_TRANSLATION_RADIUS_ANGSTROM",
    "POCKET_PLACEMENT_POLICY_ID",
    "POCKET_PLACEMENT_POLICY_SCHEMA_ID",
    "POCKET_PLACEMENT_RECEIPT_SCHEMA_ID",
    "POCKET_PLACEMENT_SEARCH_RESULT_SCHEMA_ID",
    "SPHERICAL_TRANSLATION_SAMPLER_ID",
    "PocketPlacementPolicy",
    "PocketPlacementReceipt",
    "PocketPlacementSearchResult",
    "generate_pocket_centered_docking_proposals",
    "install_pocket_proposal_override",
    "run_authenticated_pocket_placement_search",
]
