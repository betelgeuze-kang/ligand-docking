from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

import betelgeuze_engine_v2.docking.mixed64_scientific_pipeline_v3 as pipeline_module
from betelgeuze_engine_v2.docking.geometric_admission_v3 import (
    GeometricAdmissionV3,
)
from betelgeuze_engine_v2.docking.mixed64_scientific_pipeline_policy_v3 import (
    MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256,
)
from betelgeuze_engine_v2.docking.mixed64_scientific_pipeline_v3 import (
    Mixed64ScientificPipelineV3Error,
    execute_synthetic_mixed64_scientific_pipeline,
)
from tests.unit.test_engine_v2_mixed64_scorer_validity_ranking_v3 import (
    _scorer,
)
from tests.unit.test_engine_v2_mixed64_v7_post_admission_v3 import (
    _fixture,
    _refiner,
)


def _inputs():
    authority, receptor, ligand, operational = _fixture(scoring_ready=True)
    source_bundle = operational.admission_batch.producer_batch.source_bundle
    return (
        authority,
        receptor,
        ligand,
        source_bundle,
        _refiner(authority, receptor, ligand),
        _scorer(authority, receptor, ligand),
    )


def test_exact_source_bundle_executes_one_failure_complete_scientific_core() -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    result = execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    document = result.to_dict()

    assert document["policy_sha256"] == MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256
    assert document["candidate_denominator"] == 64
    assert document["source_bundle_receipt_sha256"] == source_bundle.receipt_sha256
    assert document["allocation_receipt_sha256"] == (
        source_bundle.allocation.receipt_sha256
    )
    assert document["stage_receipt_sha256s"] == result.stage_receipt_sha256s
    assert document["final_scoring_batch"]["receipt_sha256"] == (
        result.scoring_batch.receipt_sha256
    )
    assert document["final_scoring_batch"]["candidate_denominator"] == 64
    assert len(document["final_scoring_batch"]["records"]) == 64
    assert document["top5_slot_indices"] == list(result.scoring_batch.top5_slot_indices)
    assert document["valid_top5_slot_indices"] == list(
        result.scoring_batch.valid_top5_slot_indices
    )
    assert document["complete_scorer_v1_terms_preserved"] is True
    assert document["canonical_scientific_core_receipt"] is True
    for key in (
        "activation_evidence_eligible",
        "reservation_allowed",
        "molecular_cohort_execution_authorized",
        "historical_or_fresh_execution_authorized",
        "standalone_consumer_activation_authorized",
        "benchmark_consumer_activation_authorized",
        "api_consumer_activation_authorized",
        "product_shadow_consumer_activation_authorized",
        "product_or_stage0_authority",
        "hip_execution_authorized",
        "public_or_scientific_claim_authorized",
    ):
        assert document[key] is False


def test_every_stage_preserves_exact_64_slot_denominator_and_order() -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    result = execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    )

    for stage in (
        result.producer_batch,
        result.admission_batch,
        result.operational_batch,
        result.post_admission_batch,
        result.scoring_batch,
    ):
        records = stage.records if hasattr(stage, "records") else stage.decisions
        assert len(records) == 64
        assert tuple(value.slot_index for value in records) == tuple(range(64))
    counts = result.to_dict()["stage_counts"]
    assert counts["generated"] + counts["typed_generation_failure"] == 64
    assert (
        counts["pre_refinement_accepted"]
        + counts["pre_refinement_rejected"]
        + counts["typed_allocation_failure"]
        + counts["typed_proposal_generation_failure"]
        == 64
    )
    assert (
        counts["materialized"]
        + counts["typed_materialization_failure"]
        + counts["upstream_not_materialized"]
        == 64
    )
    assert (
        counts["post_refinement_accepted"]
        + counts["post_refinement_rejected"]
        + counts["typed_refinement_failure"]
        + counts["upstream_not_refined"]
        == 64
    )
    assert (
        counts["score_evidence_complete"]
        + counts["typed_scorer_failure"]
        + counts["upstream_not_scored"]
        == 64
    )


def test_fresh_exact_executors_are_receipt_deterministic() -> None:
    authority, receptor, ligand, source_bundle, refiner, scorer = _inputs()
    first = execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    second = execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=_refiner(authority, receptor, ligand),
        scorer=_scorer(authority, receptor, ligand),
    )

    assert first.stage_receipt_sha256s == second.stage_receipt_sha256s
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.to_dict() == second.to_dict()


def test_executor_calls_each_stage_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    calls = {
        "producer": 0,
        "admission": 0,
        "materialization": 0,
        "v7": 0,
        "scoring": 0,
    }
    original_producer = pipeline_module.produce_fixed_mixed64_proposals
    original_admission = GeometricAdmissionV3.admit_producer_batch
    original_materialization = (
        pipeline_module.materialize_mixed64_operational_proposals
    )
    original_v7 = pipeline_module.execute_synthetic_mixed64_v7_post_admission
    original_scoring = (
        pipeline_module.execute_synthetic_mixed64_scorer_validity_ranking
    )

    def producer(*args, **kwargs):
        calls["producer"] += 1
        return original_producer(*args, **kwargs)

    def admission(self, producer_batch):
        calls["admission"] += 1
        return original_admission(self, producer_batch)

    def materialization(admission_batch):
        calls["materialization"] += 1
        return original_materialization(admission_batch)

    def v7(operational_batch, *, refiner):
        calls["v7"] += 1
        return original_v7(operational_batch, refiner=refiner)

    def scoring(post_admission_batch, *, scorer):
        calls["scoring"] += 1
        return original_scoring(post_admission_batch, scorer=scorer)

    monkeypatch.setattr(
        pipeline_module, "produce_fixed_mixed64_proposals", producer
    )
    monkeypatch.setattr(GeometricAdmissionV3, "admit_producer_batch", admission)
    monkeypatch.setattr(
        pipeline_module,
        "materialize_mixed64_operational_proposals",
        materialization,
    )
    monkeypatch.setattr(
        pipeline_module,
        "execute_synthetic_mixed64_v7_post_admission",
        v7,
    )
    monkeypatch.setattr(
        pipeline_module,
        "execute_synthetic_mixed64_scorer_validity_ranking",
        scoring,
    )

    execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    assert calls == {
        "producer": 1,
        "admission": 1,
        "materialization": 1,
        "v7": 1,
        "scoring": 1,
    }


def test_executor_rejects_reuse_and_cross_wired_scorer() -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    with pytest.raises(Exception, match="preexisting receipts"):
        execute_synthetic_mixed64_scientific_pipeline(
            source_bundle,
            refiner=refiner,
            scorer=scorer,
        )

    authority, receptor, ligand, source_bundle, _used, _scorer_one = _inputs()
    wrong_source_scorer = _scorer(
        authority,
        receptor,
        ligand,
        source_sha256="0" * 64,
    )
    with pytest.raises(Exception, match="exact|identity"):
        execute_synthetic_mixed64_scientific_pipeline(
            source_bundle,
            refiner=_refiner(authority, receptor, ligand),
            scorer=wrong_source_scorer,
        )


def test_receipt_is_factory_sealed_and_detects_field_tamper() -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    result = execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    with pytest.raises(Mixed64ScientificPipelineV3Error, match="bounded executor"):
        replace(result, profile_id="cross-wired")

    object.__setattr__(
        result,
        "pipeline_implementation_source_sha256",
        "0" * 64,
    )
    with pytest.raises(Mixed64ScientificPipelineV3Error, match="source"):
        _ = result.receipt_sha256


def test_pipeline_source_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    original = pipeline_module._stable_source_sha256
    calls = 0

    def changed(path):
        nonlocal calls
        calls += 1
        observed = original(path)
        return observed if calls == 1 else "0" * 64

    monkeypatch.setattr(pipeline_module, "_stable_source_sha256", changed)
    with pytest.raises(Mixed64ScientificPipelineV3Error, match="changed"):
        execute_synthetic_mixed64_scientific_pipeline(
            source_bundle,
            refiner=refiner,
            scorer=scorer,
        )


def test_public_api_has_no_allocation_result_tuning_or_authority_inputs() -> None:
    assert set(
        inspect.signature(
            execute_synthetic_mixed64_scientific_pipeline
        ).parameters
    ) == {"source_bundle", "refiner", "scorer"}


def test_receipt_avoids_recursive_prior_stage_duplication() -> None:
    _authority, _receptor, _ligand, source_bundle, refiner, scorer = _inputs()
    document = execute_synthetic_mixed64_scientific_pipeline(
        source_bundle,
        refiner=refiner,
        scorer=scorer,
    ).to_dict()

    assert "producer_batch" not in document
    assert "admission_batch" not in document
    assert "operational_batch" not in document
    assert "post_admission_batch" not in document
    assert "stage_receipt_sha256s" in document
    assert "final_scoring_batch" in document
