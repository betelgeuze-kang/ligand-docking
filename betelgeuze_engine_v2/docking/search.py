"""Bounded docking search scaffold with explicit failure-row preservation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Protocol, runtime_checkable

import torch

from .proposals import (
    DockingBudget,
    DockingProposal,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
)


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
    status: str
    score: float | None
    proposal: DockingProposal | None
    error_code: str = ""
    error_message: str = ""
    refined: bool = False

    @property
    def succeeded(self) -> bool:
        return self.status == "success" and self.score is not None and self.proposal is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "proposal_index": int(self.proposal_index),
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "status": self.status,
            "succeeded": self.succeeded,
            "score": self.score,
            "refined": bool(self.refined),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class DockingSearchResult:
    rows: tuple[DockingSearchRow, ...]
    top_rows: tuple[DockingSearchRow, ...]
    budget: DockingBudget
    scorer_id: str
    scorer_version: str
    refiner_id: str
    search_fingerprint_sha256: str
    blockers: tuple[str, ...]

    @property
    def success_count(self) -> int:
        return sum(row.succeeded for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": len(self.rows),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "top_count": len(self.top_rows),
            "budget": self.budget.to_dict(),
            "scorer_id": self.scorer_id,
            "scorer_version": self.scorer_version,
            "refiner_id": self.refiner_id,
            "search_fingerprint_sha256": self.search_fingerprint_sha256,
            "claim_safe": False,
            "blockers": list(self.blockers),
            "rows": [row.to_dict() for row in self.rows],
            "top_candidate_ids": [row.candidate_id for row in self.top_rows],
        }


def _score_value(value: float | torch.Tensor) -> float:
    if isinstance(value, torch.Tensor):
        if value.numel() != 1:
            raise DockingSearchError("docking scorer must return one scalar per proposal")
        score = float(value.detach().cpu().item())
    else:
        score = float(value)
    if not math.isfinite(score):
        raise DockingSearchError("docking scorer returned a non-finite value")
    return score


def _direct_rmsd(first: DockingProposal, second: DockingProposal) -> float:
    if first.coordinates.shape != second.coordinates.shape:
        raise DockingSearchError("proposal coordinate shapes differ")
    delta = first.coordinates - second.coordinates
    return float(torch.sqrt(delta.square().sum(dim=-1).mean()).item())


def _search_fingerprint(
    proposals: tuple[DockingProposal, ...],
    budget: DockingBudget,
    scorer: DockingPoseScorer,
    refiner: DockingPoseRefiner | None,
) -> str:
    payload = {
        "budget": budget.to_dict(),
        "scorer_id": str(scorer.scorer_id),
        "scorer_version": str(scorer.scorer_version),
        "refiner_id": "" if refiner is None else str(refiner.refiner_id),
        "refiner_version": "" if refiner is None else str(refiner.refiner_version),
        "proposal_fingerprints": [proposal.fingerprint_sha256 for proposal in proposals],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_bounded_docking_search(
    search_space: TorsionSearchSpace,
    budget: DockingBudget,
    scorer: DockingPoseScorer,
    *,
    refiner: DockingPoseRefiner | None = None,
    diversity_rmsd_angstrom: float = 0.5,
) -> DockingSearchResult:
    """Generate, optionally refine, score, and diversity-filter a fixed budget."""

    if not isinstance(scorer, DockingPoseScorer):
        raise TypeError("scorer must satisfy DockingPoseScorer")
    if refiner is not None and not isinstance(refiner, DockingPoseRefiner):
        raise TypeError("refiner must satisfy DockingPoseRefiner")
    threshold = float(diversity_rmsd_angstrom)
    if not math.isfinite(threshold) or threshold < 0.0:
        raise ValueError("diversity_rmsd_angstrom must be finite and non-negative")

    proposals = generate_bounded_docking_proposals(search_space, budget)
    rows: list[DockingSearchRow] = []
    for proposal in proposals:
        current = proposal
        refined = False
        try:
            if int(budget.max_refinement_steps) > 0:
                if refiner is None:
                    raise DockingSearchError("refinement requested but no refiner was provided")
                current = refiner.refine(
                    proposal,
                    max_steps=int(budget.max_refinement_steps),
                )
                if not isinstance(current, DockingProposal):
                    raise TypeError("refiner did not return DockingProposal")
                if current.coordinates.shape != proposal.coordinates.shape:
                    raise DockingSearchError("refiner changed the ligand atom count")
                refined = True
            score = _score_value(scorer.score(current))
            rows.append(
                DockingSearchRow(
                    candidate_id=current.candidate_id,
                    proposal_index=proposal.proposal_index,
                    proposal_fingerprint_sha256=proposal.fingerprint_sha256,
                    status="success",
                    score=score,
                    proposal=current,
                    refined=refined,
                )
            )
        except Exception as exc:  # every failed candidate remains in the ledger
            rows.append(
                DockingSearchRow(
                    candidate_id=proposal.candidate_id,
                    proposal_index=proposal.proposal_index,
                    proposal_fingerprint_sha256=proposal.fingerprint_sha256,
                    status="failure",
                    score=None,
                    proposal=None,
                    error_code=exc.__class__.__name__,
                    error_message=str(exc)[:500],
                    refined=refined,
                )
            )

    successful = sorted(
        (row for row in rows if row.succeeded),
        key=lambda row: (float(row.score), row.proposal_index, row.candidate_id),
    )
    selected: list[DockingSearchRow] = []
    for row in successful:
        assert row.proposal is not None
        if all(
            _direct_rmsd(row.proposal, other.proposal) >= threshold
            for other in selected
            if other.proposal is not None
        ):
            selected.append(row)
        if len(selected) >= int(budget.top_k):
            break

    blockers = [
        "docking_proposal_scaffold_not_scientifically_validated",
        "public_pose_validity_and_ranking_evidence_missing",
    ]
    if not bool(scorer.validated_for_docking_ranking):
        blockers.append("scorer_not_validated_for_docking_ranking")
    if not successful:
        blockers.append("no_successful_candidates")
    if len(selected) < min(int(budget.top_k), len(successful)):
        blockers.append("insufficient_diverse_top_k")
    if int(budget.max_refinement_steps) > 0 and refiner is None:
        blockers.append("refinement_requested_but_refiner_missing")

    return DockingSearchResult(
        rows=tuple(rows),
        top_rows=tuple(selected),
        budget=budget,
        scorer_id=str(scorer.scorer_id),
        scorer_version=str(scorer.scorer_version),
        refiner_id="" if refiner is None else str(refiner.refiner_id),
        search_fingerprint_sha256=_search_fingerprint(proposals, budget, scorer, refiner),
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
