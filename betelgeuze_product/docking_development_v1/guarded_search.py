"""Product-owned scorer isolation over the unchanged authenticated engine search.

Scorers receive bounded, independent copies with identical proposal identities.
Every copy and the wrapped component contract are checked against snapshots
taken before any call. Coherent rebinding and cross-row mutation become explicit
failed outcomes; mutable scorer inputs never replace the engine's source rows.
"""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import betelgeuze_engine_v2
from betelgeuze_engine_v2.docking.authority import (
    AuthenticatedDockingProblem,
    run_authenticated_bounded_docking_search,
)
from betelgeuze_engine_v2.docking.proposals import DockingBudget, DockingProposal
from betelgeuze_engine_v2.docking.scoring import (
    component_contract_fingerprint,
    scorer_descriptor,
)
from betelgeuze_engine_v2.docking.search import (
    DockingBatchScoreOutcome,
    DockingPoseBatchScorer,
    DockingPoseScorer,
    DockingSearchError,
    _score_value,
)

MAX_GUARDED_CANDIDATES = 128


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _implementation_identity():
    sources = {}
    for package in (
        Path(betelgeuze_engine_v2.__file__).resolve().parent,
        Path(__file__).resolve().parent,
    ):
        root = (
            package.parent
            if package.name == "betelgeuze_engine_v2"
            else package.parents[1]
        )
        for path in sorted(package.rglob("*.py")):
            sources[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return _digest(sources)


class IdentityGuardedScorerV1:
    scorer_id = "betelgeuze.product_identity_guarded_scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(self, scorer, problem_fingerprint_sha256):
        if not isinstance(scorer, DockingPoseScorer):
            raise TypeError("typed DockingPoseScorer contract required")
        self._scorer = scorer
        self.problem_fingerprint_sha256 = problem_fingerprint_sha256
        self._wrapped_contract = self._observed_contract()
        self.score_descriptor = scorer_descriptor(scorer)
        self.implementation_source_sha256 = _implementation_identity()
        self.config_fingerprint_sha256 = _digest(
            {
                "policy": "independent_identity_copies_and_pre_call_snapshot/1.0.0",
                "wrapped_component_contract_sha256": self._wrapped_contract,
                "maximum_candidates": MAX_GUARDED_CANDIDATES,
            }
        )

    def _observed_contract(self):
        return component_contract_fingerprint(
            self._scorer,
            kind="scorer",
            expected_problem_fingerprint_sha256=self.problem_fingerprint_sha256,
        )

    def _require_unchanged_contract(self):
        if self._observed_contract() != self._wrapped_contract:
            raise DockingSearchError("guarded scorer component contract changed")
        if _implementation_identity() != self.implementation_source_sha256:
            raise DockingSearchError("guarded search implementation source changed")

    def score(self, proposal):
        outcome = self.score_batch((proposal,))[0]
        if outcome.error is not None:
            raise outcome.error
        return outcome.score

    def score_batch(self, proposals):
        rows = tuple(proposals)
        if len(rows) > MAX_GUARDED_CANDIDATES or any(
            type(row) is not DockingProposal for row in rows
        ):
            raise DockingSearchError("guarded scorer proposal type or bound violated")
        self._require_unchanged_contract()
        for row in rows:
            row.assert_integrity()
        # DockingProposal.__post_init__ clones all four tensors. The originals
        # remain owned by the engine even if the scorer mutates its copies.
        copies = tuple(replace(row) for row in rows)
        before = tuple((row.candidate_id, row.fingerprint_sha256) for row in copies)
        try:
            if isinstance(self._scorer, DockingPoseBatchScorer):
                outcomes = tuple(self._scorer.score_batch(copies))
                if len(outcomes) != len(copies) or any(
                    type(row) is not DockingBatchScoreOutcome for row in outcomes
                ):
                    raise DockingSearchError(
                        "guarded batch scorer outcome denominator or type changed"
                    )
            else:
                generated = []
                for row in copies:
                    try:
                        generated.append(
                            DockingBatchScoreOutcome(score=self._scorer.score(row))
                        )
                    except Exception as exc:
                        generated.append(
                            DockingBatchScoreOutcome(score=None, error=exc)
                        )
                outcomes = tuple(generated)
            # Float/Tensor conversion may execute scorer-owned code. Finish all
            # conversions before checking any identity: a later conversion can
            # mutate an earlier copy or the wrapped component contract.
            materialized = []
            for outcome in outcomes:
                if outcome.error is not None:
                    materialized.append(outcome)
                    continue
                try:
                    materialized.append(
                        DockingBatchScoreOutcome(
                            score=_score_value(outcome.score),
                            evidence=outcome.evidence,
                        )
                    )
                except Exception as exc:
                    materialized.append(DockingBatchScoreOutcome(score=None, error=exc))
            outcomes = tuple(materialized)
            self._require_unchanged_contract()
        except Exception as exc:
            return tuple(DockingBatchScoreOutcome(score=None, error=exc) for _ in rows)
        guarded = []
        for original, copy, identity, outcome in zip(
            rows, copies, before, outcomes, strict=True
        ):
            try:
                original.assert_integrity()
                copy.assert_integrity()
                if (original.candidate_id, original.fingerprint_sha256) != identity or (
                    copy.candidate_id,
                    copy.fingerprint_sha256,
                ) != identity:
                    raise DockingSearchError("scorer mutated the proposal identity")
                guarded.append(outcome)
            except Exception as exc:
                guarded.append(DockingBatchScoreOutcome(score=None, error=exc))
        return tuple(guarded)


def run_authenticated_guarded_docking_search(authority, budget, scorer, **options):
    """Use the original authority/search checks plus explicit scorer isolation."""
    if (
        type(authority) is not AuthenticatedDockingProblem
        or type(budget) is not DockingBudget
    ):
        raise TypeError("exact authenticated docking authority and budget required")
    if not 1 <= budget.candidate_count <= MAX_GUARDED_CANDIDATES:
        raise DockingSearchError("product guarded search candidate bound exceeded")
    guard = IdentityGuardedScorerV1(scorer, authority.problem.fingerprint_sha256)
    return run_authenticated_bounded_docking_search(authority, budget, guard, **options)
