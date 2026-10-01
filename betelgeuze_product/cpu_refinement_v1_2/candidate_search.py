"""Candidate-only adapter of the frozen search algorithm; differential tests required.

The engine source remains immutable. Keep failure, lineage, scoring and validity
semantics aligned with docking.search; orchestration and journaling live here.
"""
from betelgeuze_engine_v2.docking.search import (
    DockingSearchRow, DockingSearchError, DockingProposal, DockingPoseBatchScorer,
    DockingBatchScoreOutcome, _require_refined_lineage, _score_value, failure_receipt,
)

def _evaluate_candidate_rows(proposals, *, search_space, budget, scorer, refiner,
                             problem_fingerprint, context, validity_fingerprint,
                             unbound_validity_compatibility):
    """Shared candidate execution; selection and persistence belong to callers."""
    row_by_index: dict[int, DockingSearchRow] = {}
    prepared: list[tuple[DockingProposal, DockingProposal, bool]] = []

    def failure_row(
        proposal: DockingProposal,
        *,
        refined: bool,
        error: Exception,
    ) -> DockingSearchRow:
        receipt = failure_receipt(
            error,
            public_message="docking candidate execution failed",
        )
        public_error_code = str(
            getattr(error, "public_error_code", receipt.public_error_code)
        )
        return DockingSearchRow(
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
            error_code=public_error_code,
            error_message=receipt.public_message,
            private_error_sha256=receipt.private_error_sha256,
            private_error_byte_length=receipt.private_error_byte_length,
            refined=refined,
        )

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
            prepared.append((proposal, current, refined))
        except Exception as exc:
            row_by_index[proposal.proposal_index] = failure_row(
                proposal,
                refined=refined,
                error=exc,
            )

    if isinstance(scorer, DockingPoseBatchScorer):
        try:
            outcomes = tuple(scorer.score_batch(tuple(row[1] for row in prepared)))
            if len(outcomes) != len(prepared):
                raise DockingSearchError("batch scorer denominator mismatch")
            if any(not isinstance(row, DockingBatchScoreOutcome) for row in outcomes):
                raise DockingSearchError("batch scorer returned an invalid outcome")
        except Exception as exc:
            outcomes = tuple(
                DockingBatchScoreOutcome(score=None, error=exc) for _ in prepared
            )
    else:
        generated: list[DockingBatchScoreOutcome] = []
        for _, current, _ in prepared:
            try:
                generated.append(DockingBatchScoreOutcome(score=scorer.score(current)))
            except Exception as exc:
                generated.append(DockingBatchScoreOutcome(score=None, error=exc))
        outcomes = tuple(generated)

    for (proposal, current, refined), outcome in zip(
        prepared,
        outcomes,
        strict=True,
    ):
        try:
            if outcome.error is not None:
                raise outcome.error
            before_score_fingerprint = current.fingerprint_sha256
            score = _score_value(outcome.score)
            current.assert_integrity()
            proposal.assert_integrity()
            search_space.assert_integrity()
            if current.fingerprint_sha256 != before_score_fingerprint:
                raise DockingSearchError("scorer mutated the proposal identity")
            validity = None if context is None else context.evaluate(current)
            selection_eligible = (
                unbound_validity_compatibility
                if validity is None
                else validity.valid
            )
            row_by_index[proposal.proposal_index] = DockingSearchRow(
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
                score_evidence=outcome.evidence,
            )
        except Exception as exc:
            row_by_index[proposal.proposal_index] = failure_row(
                proposal,
                refined=refined,
                error=exc,
            )

    return [row_by_index[proposal.proposal_index] for proposal in proposals]
