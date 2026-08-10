from __future__ import annotations

from dataclasses import fields, replace
import inspect

import pytest

import betelgeuze_engine_v2.docking.standalone_scientific_core_v3 as core_module
from betelgeuze_engine_v2.docking.mixed64_scorer_validity_ranking_v3 import (
    SCORED_POSE_VALID_STATUS,
    UPSTREAM_NOT_SCORED_STATUS,
)
from betelgeuze_engine_v2.docking.standalone_scientific_core_policy_v3 import (
    STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256,
)
from betelgeuze_engine_v2.docking.standalone_scientific_core_v3 import (
    STANDALONE_SCIENTIFIC_CORE_BLOCKERS,
    StandaloneScientificCoreReceiptV1,
    StandaloneScientificCoreV3Error,
    execute_repository_synthetic_d0_standalone_scientific_core,
)
from tests.unit.test_engine_v2_standalone_pipeline_core import _request


def test_exact_repository_request_emits_failure_complete_scientific_receipt() -> None:
    result = execute_repository_synthetic_d0_standalone_scientific_core(_request())
    document = result.to_dict()

    assert document["policy_sha256"] == STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256
    assert document["candidate_denominator"] == 64
    assert len(result.candidates) == 64
    assert tuple(row.slot_index for row in result.candidates) == tuple(range(64))
    assert result.success_count == 32
    assert result.failure_count == 32
    assert result.top_proposal_indices == (45, 47, 23, 63, 9)
    assert result.top_valid_proposal_indices == (45, 47, 23, 63, 9)
    assert document["source_adapter_receipt_sha256"] == (
        result.source_adapter.receipt_sha256
    )
    assert document["scientific_pipeline_receipt_sha256"] == (
        result.scientific_pipeline.receipt_sha256
    )
    assert document["stage_receipt_sha256s"] == (
        result.scientific_pipeline.stage_receipt_sha256s
    )
    final_batch = document["scientific_pipeline_receipt"]["final_scoring_batch"]
    assert len(final_batch["records"]) == 64
    assert final_batch["score_evidence_complete_count"] == 32
    assert final_batch["pose_valid_count"] == 32
    assert sum(
        row["status"] == UPSTREAM_NOT_SCORED_STATUS
        for row in final_batch["records"]
    ) == 32
    assert sum(
        row["status"] == SCORED_POSE_VALID_STATUS
        for row in final_batch["records"]
    ) == 32
    assert document["blockers"] == list(STANDALONE_SCIENTIFIC_CORE_BLOCKERS)
    assert document["complete_scorer_v1_terms_preserved"] is True
    assert document["complete_pose_validity_preserved"] is True
    assert document["primary_and_valid_only_rank_preserved"] is True
    assert document["failure_denominator_preserved"] is True
    for key in (
        "producer_attested",
        "activation_evidence_eligible",
        "canonical_docking_pipeline_activation_authorized",
        "cli_activation_authorized",
        "api_activation_authorized",
        "benchmark_activation_authorized",
        "product_shadow_activation_authorized",
        "reservation_allowed",
        "molecular_cohort_execution_authorized",
        "historical_or_fresh_execution_authorized",
        "stage0_admission_authority",
        "product_execution_authorized",
        "product_mutation_authorized",
        "existing_rank_auto_change_authorized",
        "customer_pose_emission_authorized",
        "public_benchmark_execution_authorized",
        "hip_execution_authorized",
        "public_or_scientific_claim_authorized",
        "claim_safe",
    ):
        assert document[key] is False


def test_fresh_executions_are_receipt_deterministic() -> None:
    first = execute_repository_synthetic_d0_standalone_scientific_core(_request())
    second = execute_repository_synthetic_d0_standalone_scientific_core(_request())

    assert first.receipt_sha256 == second.receipt_sha256
    assert first.to_dict() == second.to_dict()
    assert first.source_adapter.receipt_sha256 == second.source_adapter.receipt_sha256
    assert (
        first.scientific_pipeline.receipt_sha256
        == second.scientific_pipeline.receipt_sha256
    )


def test_executor_owns_exact_source_components_and_scientific_call_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"source": 0, "refiner": 0, "scorer": 0, "scientific": 0}
    original_source = core_module.build_repository_synthetic_d0_mixed64_source
    original_refiner = core_module.InteractionAwareTorsionContactEnsembleRefinerV7
    original_scorer = core_module.ChemistryPoseScorerV1
    original_scientific = core_module.execute_synthetic_mixed64_scientific_pipeline

    def source(request):
        calls["source"] += 1
        return original_source(request)

    def refiner(*args, **kwargs):
        calls["refiner"] += 1
        return original_refiner(*args, **kwargs)

    def scorer(*args, **kwargs):
        calls["scorer"] += 1
        return original_scorer(*args, **kwargs)

    def scientific(source_bundle, *, refiner, scorer):
        calls["scientific"] += 1
        return original_scientific(
            source_bundle,
            refiner=refiner,
            scorer=scorer,
        )

    monkeypatch.setattr(
        core_module,
        "build_repository_synthetic_d0_mixed64_source",
        source,
    )
    monkeypatch.setattr(
        core_module,
        "InteractionAwareTorsionContactEnsembleRefinerV7",
        refiner,
    )
    monkeypatch.setattr(core_module, "ChemistryPoseScorerV1", scorer)
    monkeypatch.setattr(
        core_module,
        "execute_synthetic_mixed64_scientific_pipeline",
        scientific,
    )

    execute_repository_synthetic_d0_standalone_scientific_core(_request())

    assert calls == {"source": 1, "refiner": 1, "scorer": 1, "scientific": 1}


def test_executor_api_accepts_no_caller_source_tuning_or_authority() -> None:
    parameters = inspect.signature(
        execute_repository_synthetic_d0_standalone_scientific_core
    ).parameters
    assert tuple(parameters) == ("request",)
    with pytest.raises(TypeError, match="exact DockingPipelineRequestV1"):
        execute_repository_synthetic_d0_standalone_scientific_core(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unexpected keyword"):
        execute_repository_synthetic_d0_standalone_scientific_core(
            _request(),
            allocation=object(),  # type: ignore[call-arg]
        )


def test_receipt_factory_and_embedded_chain_fail_closed() -> None:
    result = execute_repository_synthetic_d0_standalone_scientific_core(_request())
    constructor_fields = {
        item.name: getattr(result, item.name)
        for item in fields(result)
        if item.init
    }
    with pytest.raises(StandaloneScientificCoreV3Error, match="bounded executor"):
        StandaloneScientificCoreReceiptV1(**constructor_fields)
    with pytest.raises(StandaloneScientificCoreV3Error, match="bounded executor"):
        replace(result)
    with pytest.raises(StandaloneScientificCoreV3Error, match="bounded executor"):
        replace(result, recorder_implementation_source_sha256="e" * 64)


def test_source_identity_change_during_execution_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = core_module._stable_source_sha256
    calls = 0

    def changing(path):
        nonlocal calls
        calls += 1
        observed = original(path)
        return "f" * 64 if calls > 3 and path == core_module.Path(core_module.__file__) else observed

    monkeypatch.setattr(core_module, "_stable_source_sha256", changing)
    with pytest.raises(StandaloneScientificCoreV3Error, match="changed during execution"):
        execute_repository_synthetic_d0_standalone_scientific_core(_request())


def test_serialized_receipt_is_deep_copy_and_object_remains_immutable() -> None:
    result = execute_repository_synthetic_d0_standalone_scientific_core(_request())
    receipt_sha256 = result.receipt_sha256
    document = result.to_dict()
    document["scientific_pipeline_receipt"]["final_scoring_batch"]["records"][0][
        "status"
    ] = "forged"

    assert result.receipt_sha256 == receipt_sha256
    assert result.to_dict()["scientific_pipeline_receipt"]["final_scoring_batch"][
        "records"
    ][0]["status"] != "forged"
