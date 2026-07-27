"""Bounded docking search with failure and pose-validity row preservation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Protocol, Sequence, runtime_checkable

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from .identity import DockingProblemIdentity
from .metrics import (
    _canonicalize_symmetry_permutations,
    direct_rmsd,
    kabsch_aligned_rmsd,
    symmetry_aware_rmsd,
)
from .proposals import (
    DockingBudget,
    DockingProposal,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
)
from .scoring import (
    DockingScoreDescriptor,
    component_contract_fingerprint,
    score_sort_key,
    scorer_descriptor,
)
from .validity import PoseValidityContext, PoseValidityResult


class DockingSearchError(RuntimeError):
    """The bounded docking search contract cannot be satisfied."""


@runtime_checkable
class DockingPoseScorer(Protocol):
    scorer_id: str
    scorer_version: str
    validated_for_docking_ranking: bool

    def score(self, proposal: DockingProposal) -> float | torch.Tensor:
        ...


@runtime_checkable
class DockingPoseRefiner(Protocol):
    refiner_id: str
    refiner_version: str

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        ...


@dataclass(frozen=True)
class DockingSearchRow:
    candidate_id: str
    proposal_index: int
    proposal_fingerprint_sha256: str
    result_proposal_fingerprint_sha256: str
    problem_fingerprint_sha256: str
    search_space_fingerprint_sha256: str
    status: str
    score: float | None
    proposal: DockingProposal | None
    pose_validity: PoseValidityResult | None = None
    validity_context_fingerprint_sha256: str = ""
    selection_eligible: bool = False
    error_code: str = ""
    error_message: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0
    refined: bool = False

    @property
    def succeeded(self) -> bool:
        return (
            self.status == "success"
            and self.score is not None
            and self.proposal is not None
        )

    @property
    def validity_complete(self) -> bool:
        return bool(
            self.pose_validity is not None and self.pose_validity.complete
        )

    @property
    def pose_valid(self) -> bool:
        return bool(
            self.pose_validity is not None and self.pose_validity.valid
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "proposal_index": int(self.proposal_index),
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "result_proposal_fingerprint_sha256": (
                self.result_proposal_fingerprint_sha256
            ),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "status": self.status,
            "succeeded": self.succeeded,
            "score": self.score,
            "refined": bool(self.refined),
            "validity_context_fingerprint_sha256": (
                self.validity_context_fingerprint_sha256
            ),
            "validity_complete": self.validity_complete,
            "pose_valid": self.pose_valid,
            "selection_eligible": bool(self.selection_eligible),
            "pose_validity": (
                None if self.pose_validity is None else self.pose_validity.to_dict()
            ),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": int(self.private_error_byte_length),
        }


@dataclass(frozen=True)
class DockingSearchResult:
    rows: tuple[DockingSearchRow, ...]
    top_rows: tuple[DockingSearchRow, ...]
    budget: DockingBudget
    scorer_id: str
    scorer_version: str
    scorer_contract_fingerprint_sha256: str
    refiner_id: str
    refiner_contract_fingerprint_sha256: str
    score_descriptor: DockingScoreDescriptor
    problem_fingerprint_sha256: str
    search_space_fingerprint_sha256: str
    validity_context_fingerprint_sha256: str
    search_fingerprint_sha256: str
    diversity_metric: str
    blockers: tuple[str, ...]

    @property
    def success_count(self) -> int:
        return sum(row.succeeded for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    @property
    def selection_eligible_count(self) -> int:
        return sum(
            row.succeeded and row.selection_eligible for row in self.rows
        )

    @property
    def valid_pose_count(self) -> int:
        return sum(row.succeeded and row.pose_valid for row in self.rows)

    @property
    def invalid_or_incomplete_count(self) -> int:
        return sum(
            row.succeeded
            and row.pose_validity is not None
            and not row.pose_valid
            for row in self.rows
        )

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": len(self.rows),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "selection_eligible_count": self.selection_eligible_count,
            "valid_pose_count": self.valid_pose_count,
            "invalid_or_incomplete_count": self.invalid_or_incomplete_count,
            "top_count": len(self.top_rows),
            "budget": self.budget.to_dict(),
            "scorer_id": self.scorer_id,
            "scorer_version": self.scorer_version,
            "scorer_contract_fingerprint_sha256": (
                self.scorer_contract_fingerprint_sha256
            ),
            "refiner_id": self.refiner_id,
            "refiner_contract_fingerprint_sha256": (
                self.refiner_contract_fingerprint_sha256
            ),
            "score_descriptor": self.score_descriptor.to_dict(),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "validity_context_fingerprint_sha256": (
                self.validity_context_fingerprint_sha256
            ),
            "search_fingerprint_sha256": self.search_fingerprint_sha256,
            "diversity_metric": self.diversity_metric,
            "claim_safe": False,
            "blockers": list(self.blockers),
            "rows": [row.to_dict() for row in self.rows],
            "top_candidate_ids": [row.candidate_id for row in self.top_rows],
        }


def _score_value(value: float | torch.Tensor) -> float:
    if isinstance(value, torch.Tensor):
        if value.numel() != 1:
            raise DockingSearchError(
                "docking scorer must return one scalar per proposal"
            )
        score = float(value.detach().cpu().item())
    else:
        score = float(value)
    if not math.isfinite(score):
        raise DockingSearchError("docking scorer returned a non-finite value")
    return score


def _search_fingerprint(
    proposals: tuple[DockingProposal, ...],
    budget: DockingBudget,
    *,
    scorer_fingerprint: str,
    refiner_fingerprint: str,
    score_descriptor: DockingScoreDescriptor,
    validity_context_fingerprint: str,
    unbound_validity_compatibility: bool,
    diversity_metric: str,
    symmetry_permutations: tuple[tuple[int, ...], ...],
) -> str:
    payload = {
        "schema_id": "betelgeuze.engine_v2_docking_search/5.0.0",
        "budget": budget.to_dict(),
        "scorer_contract_fingerprint_sha256": scorer_fingerprint,
        "refiner_contract_fingerprint_sha256": refiner_fingerprint,
        "score_descriptor": score_descriptor.to_dict(),
        "validity_context_fingerprint_sha256": validity_context_fingerprint,
        "unbound_validity_compatibility": unbound_validity_compatibility,
        "diversity_metric": diversity_metric,
        "symmetry_permutation_count": len(symmetry_permutations),
        "symmetry_permutations": {
            "atom_count": int(proposals[0].coordinates.shape[0]),
            "mappings": [list(permutation) for permutation in symmetry_permutations],
        },
        "problem_fingerprint_sha256": proposals[0].problem_fingerprint_sha256,
        "search_space_fingerprint_sha256": (
            proposals[0].search_space_fingerprint_sha256
        ),
        "proposal_fingerprints": [
            proposal.fingerprint_sha256 for proposal in proposals
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_refined_lineage(
    original: DockingProposal,
    refined: DockingProposal,
    refiner: DockingPoseRefiner,
) -> None:
    original.assert_integrity()
    refined.assert_integrity()
    for field_name in (
        "candidate_id",
        "proposal_index",
        "seed",
        "problem_fingerprint_sha256",
        "search_space_fingerprint_sha256",
    ):
        if getattr(refined, field_name) != getattr(original, field_name):
            raise DockingSearchError(
                f"refiner changed immutable proposal identity field {field_name}"
            )
    if refined.parent_proposal_fingerprint_sha256 != original.fingerprint_sha256:
        raise DockingSearchError(
            "refined proposal does not reference the original proposal fingerprint"
        )
    if (
        refined.refiner_id != str(refiner.refiner_id)
        or refined.refiner_version != str(refiner.refiner_version)
    ):
        raise DockingSearchError(
            "refined proposal refiner identity does not match the active refiner"
        )


def _pose_distance(
    first: DockingProposal,
    second: DockingProposal,
    *,
    metric: str,
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None,
) -> float:
    first.assert_integrity()
    second.assert_integrity()
    if metric == "direct_rmsd":
        return direct_rmsd(first.coordinates, second.coordinates)
    if metric == "kabsch_rmsd":
        return kabsch_aligned_rmsd(first.coordinates, second.coordinates)
    if metric == "symmetry_aware_kabsch_rmsd":
        return symmetry_aware_rmsd(
            first.coordinates,
            second.coordinates,
            permutations=symmetry_permutations,
            align=True,
        ).rmsd_angstrom
    raise ValueError("unsupported diversity metric")


def _require_component_contracts(
    scorer: DockingPoseScorer,
    refiner: DockingPoseRefiner | None,
    problem: DockingProblemIdentity,
) -> tuple[DockingScoreDescriptor, str, str]:
    if not isinstance(scorer, DockingPoseScorer):
        raise TypeError("scorer must declare ID, version, validation, and score")
    if refiner is not None and not isinstance(refiner, DockingPoseRefiner):
        raise TypeError("refiner must declare ID, version, and refine")
    descriptor = scorer_descriptor(scorer)
    scorer_fingerprint = component_contract_fingerprint(
        scorer,
        kind="scorer",
        expected_problem_fingerprint_sha256=problem.fingerprint_sha256,
        allow_unbound_internal=not problem.bound,
    )
    refiner_fingerprint = (
        ""
        if refiner is None
        else component_contract_fingerprint(
            refiner,
            kind="refiner",
            expected_problem_fingerprint_sha256=problem.fingerprint_sha256,
            allow_unbound_internal=not problem.bound,
        )
    )
    return descriptor, scorer_fingerprint, refiner_fingerprint


def _require_validity_context(
    problem: DockingProblemIdentity,
    context: PoseValidityContext | None,
) -> tuple[PoseValidityContext | None, bool, str]:
    if context is None:
        if problem.bound:
            raise DockingSearchError(
                "bound docking problems require a complete pose validity context"
            )
        return None, True, ""
    if not isinstance(context, PoseValidityContext):
        raise TypeError("validity_context must be PoseValidityContext")
    context.assert_integrity()
    if context.problem_fingerprint_sha256 != problem.fingerprint_sha256:
        raise DockingSearchError(
            "pose validity context does not match the active docking problem"
        )
    return context, False, context.fingerprint_sha256


def run_bounded_docking_search(
    search_space: TorsionSearchSpace,
    budget: DockingBudget,
    scorer: DockingPoseScorer,
    *,
    refiner: DockingPoseRefiner | None = None,
    validity_context: PoseValidityContext | None = None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
    problem: DockingProblemIdentity | None = None,
    placement_center: torch.Tensor | None = None,
) -> DockingSearchResult:
    """Generate, validate, score, and diversity-filter one fixed candidate budget."""

    if not isinstance(search_space, TorsionSearchSpace):
        raise TypeError("search_space must be TorsionSearchSpace")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    search_space.assert_integrity()
    problem_identity = problem or DockingProblemIdentity.unbound()
    if not isinstance(problem_identity, DockingProblemIdentity):
        raise TypeError("problem must be DockingProblemIdentity")
    problem_fingerprint = problem_identity.fingerprint_sha256
    descriptor, scorer_fingerprint, refiner_fingerprint = (
        _require_component_contracts(scorer, refiner, problem_identity)
    )
    context, unbound_validity_compatibility, validity_fingerprint = (
        _require_validity_context(problem_identity, validity_context)
    )

    threshold = float(diversity_rmsd_angstrom)
    if not math.isfinite(threshold) or threshold < 0.0:
        raise ValueError(
            "diversity_rmsd_angstrom must be finite and non-negative"
        )
    if diversity_metric not in {
        "direct_rmsd",
        "kabsch_rmsd",
        "symmetry_aware_kabsch_rmsd",
    }:
        raise ValueError("unsupported diversity_metric")
    if (
        diversity_metric == "symmetry_aware_kabsch_rmsd"
        and symmetry_permutations is None
    ):
        raise ValueError(
            "symmetry-aware diversity requires explicit permutations"
        )
    canonical_symmetry_permutations = (
        ()
        if symmetry_permutations is None
        else _canonicalize_symmetry_permutations(
            symmetry_permutations,
            atom_count=search_space.atom_count,
        )
    )

    proposals = generate_bounded_docking_proposals(
        search_space,
        budget,
        problem=problem_identity,
        placement_center=placement_center,
    )
    rows: list[DockingSearchRow] = []
    for proposal in proposals:
        current = proposal
        refined = False
        try:
            search_space.assert_integrity()
            proposal.assert_integrity()
            if proposal.problem_fingerprint_sha256 != problem_fingerprint:
                raise DockingSearchError(
                    "proposal is cross-wired to a different docking problem"
                )
            if proposal.search_space_fingerprint_sha256 != (
                search_space.fingerprint_sha256
            ):
                raise DockingSearchError(
                    "proposal is cross-wired to a different search space"
                )
            if budget.max_refinement_steps > 0:
                if refiner is None:
                    raise DockingSearchError(
                        "refinement requested but no refiner was provided"
                    )
                original_fingerprint = proposal.fingerprint_sha256
                current = refiner.refine(
                    proposal,
                    max_steps=budget.max_refinement_steps,
                )
                proposal.assert_integrity()
                if proposal.fingerprint_sha256 != original_fingerprint:
                    raise DockingSearchError(
                        "refiner mutated the original proposal identity"
                    )
                if not isinstance(current, DockingProposal):
                    raise TypeError("refiner did not return DockingProposal")
                _require_refined_lineage(proposal, current, refiner)
                refined = True
            current.assert_integrity()
            before_score_fingerprint = current.fingerprint_sha256
            score = _score_value(scorer.score(current))
            current.assert_integrity()
            proposal.assert_integrity()
            search_space.assert_integrity()
            if current.fingerprint_sha256 != before_score_fingerprint:
                raise DockingSearchError(
                    "scorer mutated the proposal identity"
                )
            validity = None if context is None else context.evaluate(current)
            selection_eligible = (
                unbound_validity_compatibility
                if validity is None
                else validity.valid
            )
            rows.append(
                DockingSearchRow(
                    candidate_id=current.candidate_id,
                    proposal_index=proposal.proposal_index,
                    proposal_fingerprint_sha256=proposal.fingerprint_sha256,
                    result_proposal_fingerprint_sha256=current.fingerprint_sha256,
                    problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
                    search_space_fingerprint_sha256=(
                        proposal.search_space_fingerprint_sha256
                    ),
                    status="success",
                    score=score,
                    proposal=current,
                    pose_validity=validity,
                    validity_context_fingerprint_sha256=validity_fingerprint,
                    selection_eligible=selection_eligible,
                    refined=refined,
                )
            )
        except Exception as exc:
            receipt = failure_receipt(
                exc,
                public_message="docking candidate execution failed",
            )
            rows.append(
                DockingSearchRow(
                    candidate_id=proposal.candidate_id,
                    proposal_index=proposal.proposal_index,
                    proposal_fingerprint_sha256=proposal.fingerprint_sha256,
                    result_proposal_fingerprint_sha256="",
                    problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
                    search_space_fingerprint_sha256=(
                        proposal.search_space_fingerprint_sha256
                    ),
                    status="failure",
                    score=None,
                    proposal=None,
                    validity_context_fingerprint_sha256=validity_fingerprint,
                    selection_eligible=False,
                    error_code=receipt.public_error_code,
                    error_message=receipt.public_message,
                    private_error_sha256=receipt.private_error_sha256,
                    private_error_byte_length=receipt.private_error_byte_length,
                    refined=refined,
                )
            )

    successful = sorted(
        (
            row
            for row in rows
            if row.succeeded and row.selection_eligible
        ),
        key=lambda row: (
            score_sort_key(float(row.score), descriptor),
            row.proposal_index,
            row.candidate_id,
        ),
    )
    selected: list[DockingSearchRow] = []
    for row in successful:
        assert row.proposal is not None
        row.proposal.assert_integrity()
        if all(
            _pose_distance(
                row.proposal,
                other.proposal,
                metric=diversity_metric,
                symmetry_permutations=canonical_symmetry_permutations,
            )
            >= threshold
            for other in selected
            if other.proposal is not None
        ):
            selected.append(row)
        if len(selected) >= budget.top_k:
            break

    blockers = [
        "docking_proposal_scaffold_not_scientifically_validated",
        "public_pose_validity_and_ranking_evidence_missing",
        "component_source_identity_not_independently_attested",
    ]
    if not problem_identity.bound:
        blockers.extend(
            (
                "docking_problem_identity_unbound",
                "unbound_internal_component_compatibility",
            )
        )
    if unbound_validity_compatibility:
        blockers.append("unbound_internal_pose_validity_compatibility")
    if getattr(scorer, "score_descriptor", None) is None:
        blockers.append("score_descriptor_not_explicit")
    if not descriptor.calibrated:
        blockers.append("docking_score_uncalibrated")
    if not bool(scorer.validated_for_docking_ranking):
        blockers.append("scorer_not_validated_for_docking_ranking")
    scored_rows = tuple(row for row in rows if row.succeeded)
    if not scored_rows:
        blockers.append("no_successful_candidates")
    invalid_rows = tuple(
        row
        for row in scored_rows
        if row.pose_validity is not None and not row.pose_validity.valid
    )
    if any(
        row.pose_validity is not None and not row.pose_validity.complete
        for row in invalid_rows
    ):
        blockers.append("pose_validity_incomplete_candidates_present")
    if any(
        row.pose_validity is not None
        and row.pose_validity.complete
        and not row.pose_validity.valid
        for row in invalid_rows
    ):
        blockers.append("invalid_pose_candidates_present")
    eligible_count = sum(row.selection_eligible for row in scored_rows)
    if not eligible_count:
        blockers.append("no_selection_eligible_candidates")
    if len(selected) < min(budget.top_k, eligible_count):
        blockers.append("insufficient_valid_diverse_top_k")
    if budget.max_refinement_steps > 0 and refiner is None:
        blockers.append("refinement_requested_but_refiner_missing")

    search_space.assert_integrity()
    if context is not None:
        context.assert_integrity()
    for row in selected:
        assert row.proposal is not None
        row.proposal.assert_integrity()
        if not row.selection_eligible:
            raise DockingSearchError(
                "top-k selection contains an ineligible docking pose"
            )
    return DockingSearchResult(
        rows=tuple(rows),
        top_rows=tuple(selected),
        budget=budget,
        scorer_id=str(scorer.scorer_id),
        scorer_version=str(scorer.scorer_version),
        scorer_contract_fingerprint_sha256=scorer_fingerprint,
        refiner_id="" if refiner is None else str(refiner.refiner_id),
        refiner_contract_fingerprint_sha256=refiner_fingerprint,
        score_descriptor=descriptor,
        problem_fingerprint_sha256=problem_fingerprint,
        search_space_fingerprint_sha256=search_space.fingerprint_sha256,
        validity_context_fingerprint_sha256=validity_fingerprint,
        search_fingerprint_sha256=_search_fingerprint(
            proposals,
            budget,
            scorer_fingerprint=scorer_fingerprint,
            refiner_fingerprint=refiner_fingerprint,
            score_descriptor=descriptor,
            validity_context_fingerprint=validity_fingerprint,
            unbound_validity_compatibility=unbound_validity_compatibility,
            diversity_metric=diversity_metric,
            symmetry_permutations=canonical_symmetry_permutations,
        ),
        diversity_metric=diversity_metric,
        blockers=tuple(dict.fromkeys(blockers)),
    )


__all__ = [
    "DockingPoseRefiner",
    "DockingPoseScorer",
    "DockingSearchError",
    "DockingSearchResult",
    "DockingSearchRow",
    "run_bounded_docking_search",
]
