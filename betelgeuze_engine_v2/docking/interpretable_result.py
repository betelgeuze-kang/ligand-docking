"""Failure-complete search receipts with retained interpretable score terms.

The generic docking search stores one scalar per candidate.  This module wraps
an authenticated pocket-placement search driven by :class:`InterpretablePoseScorerV0`
and retains the exact term decomposition for every successful row. Failed
candidates remain in the denominator with no fabricated terms.

The wrapper re-evaluates each successful immutable proposal, requires bit-exact
agreement with the scalar stored by the search, binds every row to the generic
search-row document, and preserves all existing claim blockers.  It does not
calibrate or validate the score.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math

import torch

from .authority import AuthenticatedDockingProblem, DockingAuthorityError
from .interpretable_scorer import (
    InterpretablePoseScoreTerms,
    InterpretablePoseScorerV0,
)
from .placement import (
    PocketPlacementPolicy,
    PocketPlacementReceipt,
    PocketPlacementSearchResult,
    run_authenticated_pocket_placement_search,
)
from .proposals import DockingBudget, DockingProposal
from .search import DockingSearchRow


INTERPRETABLE_SEARCH_TERM_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_search_term_row/1.0.0"
)
INTERPRETABLE_SCORED_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_scored_search_result/1.0.0"
)


class InterpretableSearchResultError(DockingAuthorityError):
    """The scalar search and retained term evidence disagree."""


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
        raise InterpretableSearchResultError(
            "interpretable search evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise InterpretableSearchResultError(f"{name} must be a SHA-256")
    return text


def _row_document_sha256(row: DockingSearchRow) -> str:
    return _sha256(row.to_dict())


@dataclass(frozen=True, slots=True)
class InterpretableSearchTermRow:
    candidate_id: str
    proposal_index: int
    search_status: str
    search_row_sha256: str
    score: float | None
    selection_eligible: bool
    terms: InterpretablePoseScoreTerms | None
    error_code: str = ""
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        candidate = str(self.candidate_id or "").strip()
        if not candidate:
            raise InterpretableSearchResultError(
                "term row candidate_id must be non-empty"
            )
        if type(self.proposal_index) is not int or self.proposal_index < 0:
            raise InterpretableSearchResultError(
                "term row proposal_index must be non-negative"
            )
        status = str(self.search_status or "").strip()
        if status not in {"success", "failure"}:
            raise InterpretableSearchResultError("term row search_status is invalid")
        search_row_sha = _require_sha256(
            self.search_row_sha256,
            name="search_row_sha256",
        )
        error_code = str(self.error_code or "").strip()
        if status == "success":
            if self.score is None or not math.isfinite(float(self.score)):
                raise InterpretableSearchResultError(
                    "successful term rows require one finite scalar score"
                )
            if not isinstance(self.terms, InterpretablePoseScoreTerms):
                raise InterpretableSearchResultError(
                    "successful term rows require score terms"
                )
            score = float(self.score)
            if score.hex() != float(self.terms.total_score).hex():
                raise InterpretableSearchResultError(
                    "retained terms do not reproduce the search scalar bit-exactly"
                )
            if error_code:
                raise InterpretableSearchResultError(
                    "successful term rows cannot contain an error code"
                )
        else:
            if self.score is not None or self.terms is not None:
                raise InterpretableSearchResultError(
                    "failed term rows cannot fabricate score terms"
                )
            if self.selection_eligible:
                raise InterpretableSearchResultError(
                    "failed term rows cannot be selection eligible"
                )
        object.__setattr__(self, "candidate_id", candidate)
        object.__setattr__(self, "search_status", status)
        object.__setattr__(self, "search_row_sha256", search_row_sha)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    @property
    def succeeded(self) -> bool:
        return self.search_status == "success"

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": INTERPRETABLE_SEARCH_TERM_ROW_SCHEMA_ID,
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "search_status": self.search_status,
            "search_row_sha256": self.search_row_sha256,
            "score_binary64_hex": (
                None if self.score is None else float(self.score).hex()
            ),
            "selection_eligible": bool(self.selection_eligible),
            "score_terms_receipt_sha256": (
                "" if self.terms is None else self.terms.receipt_sha256
            ),
            "error_code": self.error_code,
            "failure_row_retained": not self.succeeded,
            "calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise InterpretableSearchResultError(
                "interpretable term row changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "terms": None if self.terms is None else self.terms.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class InterpretableScoredSearchResult:
    placement_search_result: PocketPlacementSearchResult
    scorer_contract_fingerprint_sha256: str
    scorer_authority_input_receipt_sha256: str
    rows: tuple[InterpretableSearchTermRow, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.placement_search_result,
            PocketPlacementSearchResult,
        ):
            raise TypeError(
                "placement_search_result must be PocketPlacementSearchResult"
            )
        scorer_contract = _require_sha256(
            self.scorer_contract_fingerprint_sha256,
            name="scorer_contract_fingerprint_sha256",
        )
        scorer_authority = _require_sha256(
            self.scorer_authority_input_receipt_sha256,
            name="scorer_authority_input_receipt_sha256",
        )
        search = self.placement_search_result.authenticated_search_result
        if search.authenticated_input_receipt_sha256 != scorer_authority:
            raise InterpretableSearchResultError(
                "scorer authority and placement search are cross-wired"
            )
        if search.search_result.scorer_contract_fingerprint_sha256 != scorer_contract:
            raise InterpretableSearchResultError(
                "scorer contract and generic search are cross-wired"
            )
        rows = tuple(self.rows)
        search_rows = search.search_result.rows
        if len(rows) != len(search_rows):
            raise InterpretableSearchResultError(
                "term rows must preserve the complete search denominator"
            )
        for retained, source in zip(rows, search_rows, strict=True):
            if retained.candidate_id != source.candidate_id:
                raise InterpretableSearchResultError(
                    "term row candidate identity is cross-wired"
                )
            if retained.proposal_index != source.proposal_index:
                raise InterpretableSearchResultError(
                    "term row proposal index is cross-wired"
                )
            if retained.search_row_sha256 != _row_document_sha256(source):
                raise InterpretableSearchResultError(
                    "term row does not bind the generic search row"
                )
            if retained.search_status != source.status:
                raise InterpretableSearchResultError("term row status is cross-wired")
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "scorer_contract_fingerprint_sha256",
            scorer_contract,
        )
        object.__setattr__(
            self,
            "scorer_authority_input_receipt_sha256",
            scorer_authority,
        )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    @property
    def success_count(self) -> int:
        return sum(row.succeeded for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    def _projection(self) -> dict[str, object]:
        search = self.placement_search_result.authenticated_search_result
        return {
            "schema_id": INTERPRETABLE_SCORED_SEARCH_RESULT_SCHEMA_ID,
            "placement_search_receipt_sha256": (
                self.placement_search_result.receipt_sha256
            ),
            "authenticated_search_receipt_sha256": search.receipt_sha256,
            "authenticated_input_receipt_sha256": (
                search.authenticated_input_receipt_sha256
            ),
            "generic_search_fingerprint_sha256": (
                search.search_result.search_fingerprint_sha256
            ),
            "scorer_contract_fingerprint_sha256": (
                self.scorer_contract_fingerprint_sha256
            ),
            "scorer_authority_input_receipt_sha256": (
                self.scorer_authority_input_receipt_sha256
            ),
            "candidate_count": len(self.rows),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "failure_rows_retained": True,
            "row_receipt_sha256s": [row.receipt_sha256 for row in self.rows],
            "calibrated": False,
            "validated_for_docking_ranking": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise InterpretableSearchResultError(
                "interpretable scored search result changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "rows": [row.to_dict() for row in self.rows],
            "placement_search_result": self.placement_search_result.to_dict(),
        }


def run_authenticated_interpretable_pocket_search(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    scorer: InterpretablePoseScorerV0,
    *,
    refiner=None,
    policy: PocketPlacementPolicy | None = None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
    precomputed_proposals: Sequence[DockingProposal] | None = None,
    precomputed_placement_receipt: PocketPlacementReceipt | None = None,
) -> InterpretableScoredSearchResult:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(scorer, InterpretablePoseScorerV0):
        raise TypeError("scorer must be InterpretablePoseScorerV0")
    if scorer.authority_input_receipt_sha256 != (
        authenticated_problem.input_receipt_sha256
    ):
        raise InterpretableSearchResultError(
            "scorer is cross-wired to another authenticated input"
        )
    placement_result = run_authenticated_pocket_placement_search(
        authenticated_problem,
        budget,
        scorer,
        refiner=refiner,
        policy=policy,
        diversity_rmsd_angstrom=diversity_rmsd_angstrom,
        diversity_metric=diversity_metric,
        symmetry_permutations=symmetry_permutations,
        precomputed_proposals=precomputed_proposals,
        precomputed_placement_receipt=precomputed_placement_receipt,
    )
    return build_interpretable_scored_search_result(placement_result, scorer)


def build_interpretable_scored_search_result(
    placement_result: PocketPlacementSearchResult,
    scorer: InterpretablePoseScorerV0,
) -> InterpretableScoredSearchResult:
    """Attach exact score-term receipts after search ranking is complete."""

    if not isinstance(placement_result, PocketPlacementSearchResult):
        raise TypeError("placement_result must be PocketPlacementSearchResult")
    if not isinstance(scorer, InterpretablePoseScorerV0):
        raise TypeError("scorer must be InterpretablePoseScorerV0")
    if scorer.authority_input_receipt_sha256 != (
        placement_result.authenticated_search_result.authenticated_input_receipt_sha256
    ):
        raise InterpretableSearchResultError(
            "scorer and placement result authority are cross-wired"
        )
    search_rows = placement_result.authenticated_search_result.search_result.rows
    retained_rows: list[InterpretableSearchTermRow] = []
    for row in search_rows:
        if row.succeeded:
            if row.proposal is None or row.score is None:
                raise InterpretableSearchResultError(
                    "successful search row lacks proposal or score"
                )
            terms = scorer.score_terms(row.proposal)
            retained_rows.append(
                InterpretableSearchTermRow(
                    candidate_id=row.candidate_id,
                    proposal_index=row.proposal_index,
                    search_status=row.status,
                    search_row_sha256=_row_document_sha256(row),
                    score=float(row.score),
                    selection_eligible=row.selection_eligible,
                    terms=terms,
                )
            )
        else:
            retained_rows.append(
                InterpretableSearchTermRow(
                    candidate_id=row.candidate_id,
                    proposal_index=row.proposal_index,
                    search_status=row.status,
                    search_row_sha256=_row_document_sha256(row),
                    score=None,
                    selection_eligible=False,
                    terms=None,
                    error_code=row.error_code,
                )
            )
    return InterpretableScoredSearchResult(
        placement_search_result=placement_result,
        scorer_contract_fingerprint_sha256=(scorer.contract_fingerprint_sha256),
        scorer_authority_input_receipt_sha256=(scorer.authority_input_receipt_sha256),
        rows=tuple(retained_rows),
    )


__all__ = [
    "INTERPRETABLE_SCORED_SEARCH_RESULT_SCHEMA_ID",
    "INTERPRETABLE_SEARCH_TERM_ROW_SCHEMA_ID",
    "InterpretableScoredSearchResult",
    "InterpretableSearchResultError",
    "InterpretableSearchTermRow",
    "build_interpretable_scored_search_result",
    "run_authenticated_interpretable_pocket_search",
]
