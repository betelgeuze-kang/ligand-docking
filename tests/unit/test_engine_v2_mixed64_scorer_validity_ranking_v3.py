from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

import betelgeuze_engine_v2.docking.scorer_v1 as scorer_module
from betelgeuze_engine_v2.docking.contact_validity import (
    ElementAwarePoseValidityContext,
)
from betelgeuze_engine_v2.docking.mixed64_scorer_validity_ranking_policy_v3 import (
    MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
    SCORED_POSE_INVALID_STATUS,
    SCORED_POSE_VALID_STATUS,
    SCORED_VALIDITY_INCOMPLETE_STATUS,
    TYPED_SCORER_FAILURE_STATUS,
    TYPED_VALIDITY_FAILURE_STATUS,
    UPSTREAM_NOT_SCORED_STATUS,
    frozen_mixed64_scorer_validity_ranking_policy,
)
from betelgeuze_engine_v2.docking.mixed64_scorer_validity_ranking_v3 import (
    Mixed64ScorerValidityRankingRecordV1,
    Mixed64ScorerValidityRankingV3Error,
    execute_synthetic_mixed64_scorer_validity_ranking,
)
from betelgeuze_engine_v2.docking.mixed64_v7_post_admission_v3 import (
    execute_synthetic_mixed64_v7_post_admission,
)
from betelgeuze_engine_v2.docking.scorer_v1 import (
    ChemistryPoseScorerV1,
    ScorerV1Config,
)
from betelgeuze_engine_v2.docking.search import DockingBatchScoreOutcome
from betelgeuze_engine_v2.docking.validity import PoseValidityResult
from tests.unit.test_engine_v2_mixed64_v7_post_admission_v3 import (
    _fixture,
    _refiner,
)


def _post_batch():
    authority, receptor, ligand, operational = _fixture(scoring_ready=True)
    post = execute_synthetic_mixed64_v7_post_admission(
        operational,
        refiner=_refiner(authority, receptor, ligand),
    )
    return authority, receptor, ligand, post


def _scorer(authority, receptor, ligand, *, config=None, source_sha256=None):
    observed_source = hashlib.sha256(Path(scorer_module.__file__).read_bytes()).hexdigest()
    return ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256=(
            observed_source if source_sha256 is None else source_sha256
        ),
        config=config,
    )


def test_exact_post_batch_preserves_full_terms_validity_and_stable_ranks() -> None:
    authority, receptor, ligand, post = _post_batch()
    result = execute_synthetic_mixed64_scorer_validity_ranking(
        post,
        scorer=_scorer(authority, receptor, ligand),
    )

    assert len(result.records) == 64
    assert result.to_dict()["candidate_denominator"] == 64
    assert len(result.stable_ranking_slot_indices) == (
        post.post_refinement_accepted_count
    )
    assert result.top5_slot_indices == result.stable_ranking_slot_indices[:5]
    assert result.valid_top5_slot_indices == (
        result.stable_valid_ranking_slot_indices[:5]
    )
    assert tuple(
        record.stable_rank
        for record in sorted(
            (value for value in result.records if value.rank_eligible),
            key=lambda value: value.stable_rank,
        )
    ) == tuple(range(1, len(result.stable_ranking_slot_indices) + 1))
    for record in result.records:
        if record.rank_eligible:
            assert record.scorer_terms is not None
            terms = record.scorer_terms.to_dict()
            assert terms["receipt_sha256"] == record.scorer_terms.receipt_sha256
            assert all(
                f"{name}_binary64_hex" in terms
                for name in (
                    "typed_vdw",
                    "electrostatics",
                    "directional_hbond",
                    "hydrophobic_contact",
                    "desolvation_proxy",
                    "torsion_energy",
                    "ligand_strain",
                    "weak_pocket_prior",
                    "total_score",
                )
            )
            assert record.status in {
                SCORED_POSE_VALID_STATUS,
                SCORED_POSE_INVALID_STATUS,
                SCORED_VALIDITY_INCOMPLETE_STATUS,
                TYPED_VALIDITY_FAILURE_STATUS,
            }
        else:
            assert record.status in {
                UPSTREAM_NOT_SCORED_STATUS,
                TYPED_SCORER_FAILURE_STATUS,
            }
    document = result.to_dict()
    assert document["scorer_v1_terms_fully_preserved"] is True
    assert document["primary_ranking_includes_pose_invalid"] is True
    assert document["activation_evidence_eligible"] is False
    assert document["molecular_cohort_execution_authorized"] is False
    assert document["reservation_allowed"] is False


def test_only_post_admission_accepted_slots_reach_scorer_and_validity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, post = _post_batch()
    scorer = _scorer(authority, receptor, ligand)
    original_score = ChemistryPoseScorerV1.score_batch
    original_validity = ElementAwarePoseValidityContext.evaluate
    score_batches: list[tuple[str, ...]] = []
    validity_calls: list[str] = []

    def score_batch(self, proposals):
        rows = tuple(proposals)
        score_batches.append(tuple(value.fingerprint_sha256 for value in rows))
        return original_score(self, rows)

    def evaluate(self, proposal):
        validity_calls.append(proposal.fingerprint_sha256)
        return original_validity(self, proposal)

    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", score_batch)
    monkeypatch.setattr(ElementAwarePoseValidityContext, "evaluate", evaluate)
    result = execute_synthetic_mixed64_scorer_validity_ranking(
        post,
        scorer=scorer,
    )

    assert len(score_batches) == 1
    assert len(score_batches[0]) == post.post_refinement_accepted_count
    assert len(validity_calls) == result.to_dict()["score_evidence_complete_count"]
    assert all(
        value.status == UPSTREAM_NOT_SCORED_STATUS
        for value in result.records
        if not value.post_admission_record.rank_eligible
    )


def test_one_scorer_failure_is_preserved_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, post = _post_batch()
    scorer = _scorer(authority, receptor, ligand)
    original = ChemistryPoseScorerV1.score_batch
    calls = 0

    def score_batch(self, proposals):
        nonlocal calls
        calls += 1
        rows = list(original(self, proposals))
        rows[0] = DockingBatchScoreOutcome(
            score=None,
            error=RuntimeError("synthetic scoring failure"),
        )
        return tuple(rows)

    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", score_batch)
    result = execute_synthetic_mixed64_scorer_validity_ranking(
        post,
        scorer=scorer,
    )

    failed = tuple(
        value
        for value in result.records
        if value.status == TYPED_SCORER_FAILURE_STATUS
    )
    assert calls == 1
    assert len(failed) == 1
    assert failed[0].scorer_terms is None
    assert failed[0].pose_validity_result is None
    assert failed[0].stable_rank is None


def test_validity_failure_preserves_score_and_primary_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, post = _post_batch()
    scorer = _scorer(authority, receptor, ligand)
    original = ElementAwarePoseValidityContext.evaluate
    first = next(
        value.result_proposal.fingerprint_sha256
        for value in post.records
        if value.rank_eligible
    )
    attempts: list[str] = []

    def evaluate(self, proposal):
        attempts.append(proposal.fingerprint_sha256)
        if proposal.fingerprint_sha256 == first:
            raise RuntimeError("synthetic validity failure")
        return original(self, proposal)

    monkeypatch.setattr(ElementAwarePoseValidityContext, "evaluate", evaluate)
    result = execute_synthetic_mixed64_scorer_validity_ranking(
        post,
        scorer=scorer,
    )
    failed = next(
        value
        for value in result.records
        if value.status == TYPED_VALIDITY_FAILURE_STATUS
    )
    assert attempts.count(first) == 1
    assert failed.scorer_terms is not None
    assert failed.stable_rank is not None
    assert failed.pose_validity_result is None
    assert failed.stable_valid_rank is None


def test_incomplete_validity_result_is_preserved_and_not_valid_ranked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, post = _post_batch()
    scorer = _scorer(authority, receptor, ligand)
    original = ElementAwarePoseValidityContext.evaluate
    first = next(
        value.result_proposal.fingerprint_sha256
        for value in post.records
        if value.rank_eligible
    )

    def evaluate(self, proposal):
        result = original(self, proposal)
        if proposal.fingerprint_sha256 != first:
            return result
        evaluated = dict(result.evaluated_checks)
        evaluated["inside_declared_pocket"] = False
        return PoseValidityResult(
            checks=result.checks,
            evaluated_checks=evaluated,
            complete=False,
            valid_within_evaluated_scope=result.valid_within_evaluated_scope,
            measurements=result.measurements,
            blockers=result.blockers,
            not_evaluated_reasons={
                "inside_declared_pocket": "synthetic_not_evaluated"
            },
        )

    monkeypatch.setattr(ElementAwarePoseValidityContext, "evaluate", evaluate)
    result = execute_synthetic_mixed64_scorer_validity_ranking(
        post,
        scorer=scorer,
    )
    incomplete = next(
        value
        for value in result.records
        if value.status == SCORED_VALIDITY_INCOMPLETE_STATUS
    )
    assert incomplete.pose_validity_result is not None
    assert incomplete.pose_validity_result.complete is False
    assert incomplete.stable_rank is not None
    assert incomplete.stable_valid_rank is None


def test_nondefault_config_and_wrong_source_fail_before_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand, post = _post_batch()
    attempts = 0

    def score_batch(self, proposals):
        nonlocal attempts
        attempts += 1
        raise AssertionError("must not score")

    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", score_batch)
    with pytest.raises(Mixed64ScorerValidityRankingV3Error, match="profile"):
        execute_synthetic_mixed64_scorer_validity_ranking(
            post,
            scorer=_scorer(
                authority,
                receptor,
                ligand,
                config=ScorerV1Config(weak_pocket_prior_weight=0.10),
            ),
        )
    with pytest.raises(Mixed64ScorerValidityRankingV3Error, match="source identity"):
        execute_synthetic_mixed64_scorer_validity_ranking(
            post,
            scorer=_scorer(
                authority,
                receptor,
                ligand,
                source_sha256="a" * 64,
            ),
        )
    assert attempts == 0


def test_record_factory_policy_signature_and_authority_are_frozen() -> None:
    policy = frozen_mixed64_scorer_validity_ranking_policy()
    assert len(MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256) == 64
    assert policy["candidate_denominator"] == 64
    assert policy["scoring"]["maximum_batch_size"] == 64
    assert len(policy["scoring"]["term_names"]) == 8
    assert all(value is False for value in policy["authority"].values())
    parameters = set(
        inspect.signature(
            execute_synthetic_mixed64_scorer_validity_ranking
        ).parameters
    )
    assert parameters == {"post_admission_batch", "scorer"}
    with pytest.raises(Mixed64ScorerValidityRankingV3Error, match="factory"):
        Mixed64ScorerValidityRankingRecordV1(
            post_admission_record=None,
            scorer_terms=None,
            pose_validity_result=None,
            status=UPSTREAM_NOT_SCORED_STATUS,
            failure_code=None,
            stable_rank=None,
            stable_valid_rank=None,
            scorer_implementation_source_sha256="a" * 64,
            validity_implementation_source_sha256="b" * 64,
            base_validity_implementation_source_sha256="c" * 64,
            scorer_authority_input_receipt_sha256="d" * 64,
            scorer_context_fingerprint_sha256="e" * 64,
            scorer_config_fingerprint_sha256="f" * 64,
            scorer_backend_receipt_sha256="0" * 64,
            validity_context_fingerprint_sha256="1" * 64,
            validity_config_fingerprint_sha256="2" * 64,
            contact_policy_fingerprint_sha256="3" * 64,
        )
