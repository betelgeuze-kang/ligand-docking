from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
from pathlib import Path

import pytest

import betelgeuze_engine_v2.docking.scorer_v1 as scorer_module
import betelgeuze_engine_v2.docking.synthetic_d0_mixed64_source_v3 as source_module
import betelgeuze_engine_v2.docking.torsion_contact_refinement as refinement_module
from betelgeuze_engine_v2.docking.mixed64_scientific_pipeline_v3 import (
    execute_synthetic_mixed64_scientific_pipeline,
)
from betelgeuze_engine_v2.docking.mixed64_v7_post_admission_policy_v3 import (
    V7_TORSION_ELIGIBLE_SLOT_INDICES,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
from betelgeuze_engine_v2.docking.synthetic_d0_mixed64_source_policy_v3 import (
    RETAINED_SOURCE_INDICES,
    SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
    V7_CONTROL_SOURCE_INDICES,
)
from betelgeuze_engine_v2.docking.synthetic_d0_mixed64_source_v3 import (
    SyntheticD0Mixed64SourceV3Error,
    build_repository_synthetic_d0_mixed64_source,
)
from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    InteractionAwareTorsionContactEnsembleRefinerV7,
)
from tests.unit.test_engine_v2_standalone_pipeline_core import _request


def _scientific_executors(source, request):
    refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        source.authority,
        request.receptor_system,
        request.ligand_system,
        implementation_source_sha256=hashlib.sha256(
            Path(refinement_module.__file__).read_bytes()
        ).hexdigest(),
        v3_proposal_indices=V7_TORSION_ELIGIBLE_SLOT_INDICES,
    )
    scorer = ChemistryPoseScorerV1(
        source.authority,
        request.receptor_system,
        request.ligand_system,
        implementation_source_sha256=hashlib.sha256(
            Path(scorer_module.__file__).read_bytes()
        ).hexdigest(),
    )
    return refiner, scorer


def test_exact_repository_fixture_derives_complete_source_bundle() -> None:
    request = _request()
    result = build_repository_synthetic_d0_mixed64_source(request)
    document = result.to_dict()
    bundle = result.source_bundle
    allocation = bundle.allocation

    assert document["policy_sha256"] == SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256
    assert document["candidate_denominator"] == 64
    assert document["v7_control_source_count"] == 24
    assert document["true_conformer_source_count"] == 0
    assert document["retained_source_count"] == 4
    assert document["atomic_feature_count"] == 13
    assert len(allocation.slots) == 64
    assert allocation.ready_count == 54
    assert allocation.typed_failure_count == 10
    assert len(bundle.v7_control_sources) == 24
    assert len(bundle.conformer_sources) == 0
    assert len(bundle.retained_sources) == 4
    assert bundle.receptor_source_receipt_sha256 == (
        allocation.features.exact_v11_source_receipt_sha256
    )
    assert document["source_bundle"]["receipt_sha256"] == bundle.receipt_sha256
    assert document["allocation_receipt_sha256"] == allocation.receipt_sha256


def test_control_and_retained_sources_bind_exact_guided_proposals() -> None:
    result = build_repository_synthetic_d0_mixed64_source(_request())
    bundle = result.source_bundle
    guided = result.guided_placement_receipt

    assert tuple(
        int(value.source_ordinal) for value in bundle.v7_control_sources
    ) == V7_CONTROL_SOURCE_INDICES
    assert tuple(
        int(value.source_ordinal) for value in bundle.retained_sources
    ) == RETAINED_SOURCE_INDICES
    for source in bundle.v7_control_sources:
        index = int(source.source_ordinal)
        assert source.proposal_sha256 == guided.proposal_fingerprint_sha256s[index]
        assert source.proposal_lineage_sha256 is not None
        lineage = source.to_dict()["proposal_lineage"]
        assert lineage["proposal_mode"] == guided.proposal_modes[index]
        assert lineage["result_fields_consumed"] is False
    for source in bundle.retained_sources:
        index = int(source.source_ordinal)
        assert source.proposal_sha256 == guided.proposal_fingerprint_sha256s[index]
        assert source.proposal_lineage_sha256 is None


def test_atomic_features_are_pre_result_and_geometry_bound() -> None:
    result = build_repository_synthetic_d0_mixed64_source(_request())
    features = result.source_bundle.allocation.features.atomic_features
    observed = {(value.kind, value.atom_indices) for value in features}

    assert ("ligand_donor", (1, 2)) in observed
    assert ("ligand_donor", (3, 4)) in observed
    assert ("receptor_donor", (1, 2)) in observed
    assert ("ligand_acceptor", (1,)) in observed
    assert ("receptor_acceptor", (0,)) in observed
    assert ("ligand_negative_site", (3,)) in observed
    assert ("ligand_positive_site", (4,)) in observed
    assert ("receptor_negative_site", (0,)) in observed
    assert ("receptor_positive_site", (4,)) in observed
    assert ("ligand_shape_axis", (0, 1, 3)) in observed
    assert ("pocket_shape_axis", (0, 1, 3)) in observed
    assert not any("aromatic" in kind for kind, _indices in observed)
    assert all(len(value.geometry_receipt_sha256) == 64 for value in features)
    assert all(
        value.to_dict()["result_fields_consumed"] is False for value in features
    )


def test_missing_conformer_and_aromatic_lanes_remain_typed_in_denominator() -> None:
    result = build_repository_synthetic_d0_mixed64_source(_request())
    failed = tuple(
        value
        for value in result.source_bundle.allocation.slots
        if not value.generation_eligible
    )

    assert len(failed) == 10
    assert tuple(value.slot_index for value in failed) == tuple(range(36, 44)) + (
        56,
        57,
    )
    assert all(value.missing_feature_codes for value in failed)


def test_adapter_is_deterministic_and_calls_guided_generator_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = source_module.generate_guided_docking_proposals
    calls = 0

    def generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        source_module,
        "generate_guided_docking_proposals",
        generate,
    )
    first = build_repository_synthetic_d0_mixed64_source(_request())
    assert calls == 1
    monkeypatch.setattr(
        source_module,
        "generate_guided_docking_proposals",
        original,
    )
    second = build_repository_synthetic_d0_mixed64_source(_request())
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.source_bundle.receipt_sha256 == second.source_bundle.receipt_sha256
    assert first.to_dict() == second.to_dict()


def test_guided_generation_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic source failure")

    monkeypatch.setattr(
        source_module,
        "generate_guided_docking_proposals",
        fail,
    )
    with pytest.raises(RuntimeError, match="synthetic source failure"):
        build_repository_synthetic_d0_mixed64_source(_request())
    assert calls == 1


def test_source_bundle_executes_exact_scientific_core() -> None:
    request = _request()
    source = build_repository_synthetic_d0_mixed64_source(request)
    refiner, scorer = _scientific_executors(source, request)
    result = execute_synthetic_mixed64_scientific_pipeline(
        source.source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    document = result.to_dict()

    assert document["candidate_denominator"] == 64
    assert document["stage_counts"]["generated"] == 54
    assert document["stage_counts"]["typed_generation_failure"] == 10
    assert document["stage_counts"]["score_evidence_complete"] == 32
    assert document["stage_counts"]["pose_valid"] == 32
    assert document["stage_counts"]["pose_invalid"] == 0
    assert len(document["top5_slot_indices"]) == 5
    assert document["top5_slot_indices"] == document["valid_top5_slot_indices"]
    assert document["invalid_top1"] is False
    assert document["molecular_cohort_execution_authorized"] is False
    assert document["reservation_allowed"] is False
    assert document["public_or_scientific_claim_authorized"] is False


def test_receipt_is_factory_sealed_and_tamper_evident() -> None:
    result = build_repository_synthetic_d0_mixed64_source(_request())
    with pytest.raises(SyntheticD0Mixed64SourceV3Error, match="bounded adapter"):
        replace(result)

    object.__setattr__(result, "request_sha256", "0" * 64)
    with pytest.raises(SyntheticD0Mixed64SourceV3Error, match="request"):
        _ = result.receipt_sha256


def test_adapter_source_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = source_module._stable_source_sha256
    calls = 0

    def changed(path):
        nonlocal calls
        calls += 1
        observed = original(path)
        return observed if calls == 1 else "0" * 64

    monkeypatch.setattr(source_module, "_stable_source_sha256", changed)
    with pytest.raises(SyntheticD0Mixed64SourceV3Error, match="changed"):
        build_repository_synthetic_d0_mixed64_source(_request())


def test_adapter_api_accepts_only_exact_repository_request() -> None:
    assert set(
        inspect.signature(
            build_repository_synthetic_d0_mixed64_source
        ).parameters
    ) == {"request"}
    with pytest.raises(TypeError, match="request must be exact"):
        build_repository_synthetic_d0_mixed64_source(object())  # type: ignore[arg-type]


def test_all_adapter_and_consumer_authority_remains_false() -> None:
    document = build_repository_synthetic_d0_mixed64_source(_request()).to_dict()
    for key in (
        "standalone_activation_authorized",
        "benchmark_activation_authorized",
        "api_activation_authorized",
        "product_shadow_activation_authorized",
        "activation_evidence_eligible",
        "reservation_allowed",
        "molecular_cohort_execution_authorized",
        "historical_or_fresh_execution_authorized",
        "product_or_stage0_authority",
        "hip_execution_authorized",
        "public_or_scientific_claim_authorized",
    ):
        assert document[key] is False
