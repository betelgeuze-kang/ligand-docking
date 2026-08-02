from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    VerifiedStage0Admission,
    _VERIFIED_STAGE0_ADMISSION_AUTHORITY,
    stage0_engine_implementation_sha256,
)
from betelgeuze_engine_v2.benchmark.public_redocking_pipeline import (
    PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID,
    build_public_redocking_pipeline,
)
from betelgeuze_engine_v2.product_shadow import (
    ENGINE_V2_PRODUCT_SHADOW_PERMISSIONS,
    ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID,
    EngineV2ProductShadowError,
    project_engine_v2_product_shadow_evidence,
    validate_engine_v2_product_shadow_evidence,
)
from betelgeuze_engine_v2.pipeline import (
    DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID,
    build_docking_pipeline_candidate_evidence,
)


PROFILE_ID = PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID
PROPOSAL_SHA256 = "a" * 64
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _stage0_admission() -> VerifiedStage0Admission:
    profile = _profile_document()
    return VerifiedStage0Admission._from_verified_policy(
        policy_sha256="1" * 64,
        source_freeze_sha256="2" * 64,
        execution_profile_sha256="3" * 64,
        reviewer_id="independent-reviewer",
        operator_id="independent-operator",
        governance_mode="independent_three_role",
        independent_review_complete=True,
        trusted_review_time_authority_id="test-review-time-authority",
        trusted_review_time_evidence_sha256="4" * 64,
        external_run_once_authority_id="test-run-once-authority",
        external_run_once_reservation_sha256="5" * 64,
        fresh_run_identity_sha256="6" * 64,
        docking_pipeline_profile_id=PROFILE_ID,
        docking_pipeline_profile_sha256=str(profile["profile_sha256"]),
        verification_authority=_VERIFIED_STAGE0_ADMISSION_AUTHORITY,
    )


def _scoring_terms() -> dict[str, object]:
    return ScorerV1Terms(
        proposal_fingerprint_sha256=PROPOSAL_SHA256,
        authority_input_receipt_sha256="b" * 64,
        context_fingerprint_sha256="c" * 64,
        config_fingerprint_sha256="d" * 64,
        backend_receipt_sha256="e" * 64,
        typed_vdw=1.0,
        electrostatics=2.0,
        directional_hbond=3.0,
        hydrophobic_contact=4.0,
        desolvation_proxy=5.0,
        torsion_energy=6.0,
        ligand_strain=7.0,
        weak_pocket_prior=8.0,
        total_score=36.0,
        receptor_candidate_pair_count=120,
        ligand_pair_count=15,
        hbond_count=2,
        hydrophobic_contact_count=7,
        buried_polar_count=1,
    ).to_dict()


def _refinement_receipt() -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_id": (
            "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
        ),
        "source_proposal_sha256": PROPOSAL_SHA256,
        "config_sha256": "f" * 64,
        "initial_penalty_binary64_hex": (4.0).hex(),
        "final_penalty_binary64_hex": (1.0).hex(),
        "accepted_steps": 3,
        "accepted_rotation_steps": 0,
        "original_pose_valid": False,
        "total_translation_binary64_hex": [
            (0.1).hex(),
            (0.0).hex(),
            (-0.1).hex(),
        ],
        "total_rotation_vector_binary64_hex": [
            (0.0).hex(),
            (0.0).hex(),
            (0.0).hex(),
        ],
        "pre_coordinates_sha256": "1" * 64,
        "post_coordinates_sha256": "2" * 64,
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt


def _pose_validity(*, valid: bool = True) -> dict[str, object]:
    checks = {
        "all_atoms_finite": valid,
        "chemical_valid": valid,
        "geometric_valid": valid,
        "posebusters_valid": valid,
    }
    return {
        "valid": valid,
        "checks": checks,
        "evaluated_checks": {name: True for name in checks},
        "complete": True,
        "valid_within_evaluated_scope": valid,
        "measurements": {
            "minimum_vdw_gap_angstrom": -0.2,
            # This historical diagnostic is deliberately excluded from shadow.
            "rmsd_angstrom": 4.5,
        },
        "blockers": [] if valid else ["posebusters_invalid"],
        "not_evaluated_reasons": {},
        "claim_safe": False,
    }


def _candidate() -> dict[str, object]:
    terms = _scoring_terms()
    refinement = _refinement_receipt()
    source_candidate = {
        "schema_id": (
            "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0"
        ),
        "proposal_index": 7,
        "status": "success",
        "proposal_mode": "uniform_v3_rigid_ensemble",
        "ensemble_source_proposal_index": 3,
        "proposal_fingerprint_sha256": PROPOSAL_SHA256,
        "coordinate_fingerprint_sha256": "2" * 64,
        "score_terms_receipt_sha256": terms["receipt_sha256"],
        "score": 36.0,
        "geometric_valid": True,
        "chemical_valid": True,
        "selection_eligible": True,
        "posebusters_failed_check_ids": [],
        "pose_artifact_sha256": "4" * 64,
        "refinement_receipt_sha256": refinement["receipt_sha256"],
        "refinement_receipt_payload": refinement,
        "refinement_initial_penalty_binary64_hex": refinement[
            "initial_penalty_binary64_hex"
        ],
        "refinement_final_penalty_binary64_hex": refinement[
            "final_penalty_binary64_hex"
        ],
        "refinement_accepted_steps": refinement["accepted_steps"],
        "refinement_accepted_rotation_steps": refinement["accepted_rotation_steps"],
        "refinement_original_pose_valid": refinement["original_pose_valid"],
        "refinement_total_translation_binary64_hex": refinement[
            "total_translation_binary64_hex"
        ],
        "refinement_total_rotation_vector_binary64_hex": refinement[
            "total_rotation_vector_binary64_hex"
        ],
        "score_term_binary64_hex": {
            name: terms[f"{name}_binary64_hex"]
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
        },
        "hbond_count": terms["hbond_count"],
        "error_code": "",
    }
    return build_docking_pipeline_candidate_evidence(
        candidate_id="fixture-candidate-7",
        source_candidate=source_candidate,
        scorer_v1_terms=terms,
        refinement_receipt=refinement,
        baseline_disagreement={
            "available": True,
            "disagrees": True,
            "reason_codes": ["raw_top1_candidate_changed"],
        },
    )


def _resign_candidate(candidate: dict[str, object]) -> None:
    unsigned = dict(candidate)
    unsigned.pop("receipt_sha256", None)
    candidate["receipt_sha256"] = _canonical_sha256(unsigned)


def _resign_source_candidate(candidate: dict[str, object]) -> None:
    candidate["source_candidate_sha256"] = _canonical_sha256(
        candidate["source_candidate"]
    )
    _resign_candidate(candidate)


def _failure_candidate() -> dict[str, object]:
    return build_docking_pipeline_candidate_evidence(
        candidate_id="fixture-candidate-7",
        source_candidate={
            "schema_id": (
                "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0"
            ),
            "proposal_index": 7,
            "status": "failure",
            "proposal_mode": "uniform_v3_rigid_ensemble",
            "ensemble_source_proposal_index": 3,
            "torsion_rescue_parent_proposal_index": None,
            "error_code": "scorer_backend_unavailable",
        },
        scorer_v1_terms=None,
        refinement_receipt=None,
        baseline_disagreement={
            "available": False,
            "reason": "baseline_not_evaluated",
        },
    )


def _profile_document() -> dict[str, object]:
    return build_public_redocking_pipeline(
        engine_implementation_sha256=stage0_engine_implementation_sha256(_REPO_ROOT),
        variant_kind="",
    ).profile_document()


def _upstream_evidence_document(
    candidates: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    source_candidates = candidates or [_candidate()]
    profile = _profile_document()
    document: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID,
        "pipeline_profile_id": PROFILE_ID,
        "pipeline_profile_sha256": profile["profile_sha256"],
        "stage0_admission_receipt_sha256": _stage0_admission().receipt_sha256,
        "candidate_count": len(source_candidates),
        "candidate_source_sha256s": [
            _canonical_sha256(candidate) for candidate in source_candidates
        ],
        "execution_completed": True,
        "projection_only": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    document["receipt_sha256"] = _canonical_sha256(document)
    return document


def _source_evidence_document(
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    profile = _profile_document()
    upstream = _upstream_evidence_document(candidates)
    document: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_shadow_source_binding/1.0.0",
        "profile_id": PROFILE_ID,
        "profile_sha256": profile["profile_sha256"],
        "stage0_admission_receipt_sha256": _stage0_admission().receipt_sha256,
        "candidate_count": len(candidates),
        "candidate_source_sha256s": [
            _canonical_sha256(candidate) for candidate in candidates
        ],
        "upstream_evidence_schema_id": upstream["schema_id"],
        "upstream_evidence_receipt_sha256": upstream["receipt_sha256"],
        "execution_already_completed": True,
        "projection_only": True,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    document["receipt_sha256"] = _canonical_sha256(document)
    return document


def _project(candidate: dict[str, object] | None = None) -> dict[str, object]:
    source_candidates = [candidate or _candidate()]
    return project_engine_v2_product_shadow_evidence(
        stage0_admission=_stage0_admission(),
        profile_document=_profile_document(),
        upstream_evidence_document=_upstream_evidence_document(source_candidates),
        source_evidence_document=_source_evidence_document(source_candidates),
        candidates=source_candidates,
    )


def test_projection_is_operator_only_execution_free_and_receipt_complete() -> None:
    source = _candidate()
    original = deepcopy(source)

    projected = _project(source)

    assert source == original
    assert projected["consumer_scope"] == "operator_only"
    assert projected["projection_only"] is True
    assert projected["execution_performed"] is False
    assert projected["policy"]["permissions"] == dict(
        ENGINE_V2_PRODUCT_SHADOW_PERMISSIONS
    )
    assert projected["policy"]["permissions"] == {
        "evidence_display_allowed": True,
        "operator_second_opinion_allowed": True,
        "automatic_rank_mutation_allowed": False,
        "customer_pose_emission_allowed": False,
        "production_claim_allowed": False,
        "customer_execution_allowed": False,
    }

    row = projected["candidates"][0]
    assert row["profile_id"] == PROFILE_ID
    assert row["proposal_lineage"]["proposal_index"] == 7
    assert source["schema_id"] == DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID
    assert row["scoring_terms"] == source["scorer_v1_terms"]
    assert (
        row["scoring_terms"]["receipt_sha256"]
        == source["source_candidate"]["score_terms_receipt_sha256"]
    )
    assert row["pose_validity"]["valid"] is True
    assert "rmsd_angstrom" not in row["pose_validity"]["measurements"]
    assert row["refinement_receipt"] == {
        "source_receipt_sha256": source["refinement_receipt"]["receipt_sha256"],
        "source_receipt_self_hash_verified_before_projection": True,
    }
    assert row["failure_reason"] == ""
    assert row["baseline_disagreement"]["disagrees"] is True
    assert row["abstention"]["abstained"] is False
    assert row["redacted_sensitive_field_count"] >= 7

    serialized = json.dumps(projected, sort_keys=True)
    assert "/srv/private" not in serialized
    assert "pre_coordinates_sha256" not in serialized
    assert "post_coordinates_sha256" not in serialized
    assert "pose_artifact_sha256" not in serialized
    assert (
        validate_engine_v2_product_shadow_evidence(
            projected,
            stage0_admission=_stage0_admission(),
        )
        == projected
    )


def test_projection_rejects_term_tamper_and_summary_only_score_evidence() -> None:
    tampered = _candidate()
    tampered["scorer_v1_terms"]["typed_vdw_binary64_hex"] = (1.5).hex()
    _resign_candidate(tampered)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|ScorerV1Terms|exact",
    ):
        _project(tampered)

    summary_only = _candidate()
    summary_only["scorer_v1_terms"] = None
    _resign_candidate(summary_only)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|ScorerV1Terms|mapping",
    ):
        _project(summary_only)


def test_projection_requires_bound_profile_upstream_and_candidate_receipts() -> None:
    candidate = _candidate()
    profile = _profile_document()
    upstream = _upstream_evidence_document()
    source = _source_evidence_document([candidate])

    candidate["abstention"] = True
    with pytest.raises(
        EngineV2ProductShadowError,
        match="candidate bindings are cross-wired",
    ):
        project_engine_v2_product_shadow_evidence(
            stage0_admission=_stage0_admission(),
            profile_document=profile,
            upstream_evidence_document=upstream,
            source_evidence_document=source,
            candidates=[candidate],
        )

    candidate = _candidate()
    source = _source_evidence_document([candidate])
    upstream["execution_completed"] = False
    with pytest.raises(
        EngineV2ProductShadowError,
        match="upstream_evidence_document self-hash is invalid",
    ):
        project_engine_v2_product_shadow_evidence(
            stage0_admission=_stage0_admission(),
            profile_document=profile,
            upstream_evidence_document=upstream,
            source_evidence_document=source,
            candidates=[candidate],
        )

    upstream = _upstream_evidence_document()
    profile["candidate_denominator"] = 32
    with pytest.raises(
        EngineV2ProductShadowError,
        match="not an exact DockingPipeline profile",
    ):
        project_engine_v2_product_shadow_evidence(
            stage0_admission=_stage0_admission(),
            profile_document=profile,
            upstream_evidence_document=upstream,
            source_evidence_document=source,
            candidates=[candidate],
        )


def test_allowed_profile_id_cannot_front_for_foreign_components() -> None:
    profile = _profile_document()
    components = profile["components"]
    assert isinstance(components, dict)
    for role, component in components.items():
        assert isinstance(component, dict)
        component["component_id"] = f"evil.{role}/1.0.0"
        unsigned_component = dict(component)
        unsigned_component.pop("receipt_sha256")
        component["receipt_sha256"] = _canonical_sha256(unsigned_component)
    unsigned_profile = dict(profile)
    unsigned_profile.pop("profile_sha256")
    profile["profile_sha256"] = _canonical_sha256(unsigned_profile)
    candidate = _candidate()

    with pytest.raises(
        EngineV2ProductShadowError,
        match="outside the exact shadow registry",
    ):
        project_engine_v2_product_shadow_evidence(
            stage0_admission=_stage0_admission(),
            profile_document=profile,
            upstream_evidence_document=_upstream_evidence_document([candidate]),
            source_evidence_document=_source_evidence_document([candidate]),
            candidates=[candidate],
        )


def test_projection_rejects_refinement_receipt_tamper() -> None:
    candidate = _candidate()
    candidate["refinement_receipt"]["accepted_steps"] = 99
    _resign_candidate(candidate)

    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|refinement",
    ):
        _project(candidate)


def test_invalid_success_candidate_must_abstain() -> None:
    candidate = _candidate()
    candidate["source_candidate"]["geometric_valid"] = False
    candidate["source_candidate"]["selection_eligible"] = False
    candidate["validity"]["geometric_valid"] = False
    candidate["validity"]["selection_eligible"] = False
    candidate["abstention"] = False
    _resign_source_candidate(candidate)

    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|abstention",
    ):
        _project(candidate)

    candidate["abstention"] = True
    _resign_candidate(candidate)
    projected = _project(candidate)
    assert projected["candidates"][0]["abstention"]["abstained"] is True


def test_failure_candidate_is_retained_without_fabricated_scientific_receipts() -> None:
    candidate = _failure_candidate()

    projected = _project(candidate)
    row = projected["candidates"][0]
    assert row["status"] == "failure"
    assert row["scoring_terms"] is None
    assert row["refinement_receipt"] is None
    assert row["failure_reason"] == "scorer_backend_unavailable"
    assert row["abstention"]["abstained"] is True
    assert row["baseline_disagreement"] == {
        "available": False,
        "disagrees": None,
        "reason_codes": [],
        "unavailable_reason": "baseline_not_evaluated",
    }
    assert "baseline_evidence_incomplete" in row["abstention"]["reason_codes"]


def test_early_failure_can_report_unavailable_lineage_without_fabrication() -> None:
    candidate = build_docking_pipeline_candidate_evidence(
        candidate_id="fixture-candidate-early-failure",
        source_candidate={
            "schema_id": (
                "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0"
            ),
            "proposal_index": 7,
            "status": "failure",
            "error_code": "candidate_execution_failed",
        },
        scorer_v1_terms=None,
        refinement_receipt=None,
        baseline_disagreement={
            "available": False,
            "reason": "baseline_not_evaluated",
        },
    )

    row = _project(candidate)["candidates"][0]

    assert row["proposal_lineage"]["proposal_mode"] is None
    assert row["proposal_lineage"]["proposal_fingerprint_sha256"] is None
    assert row["abstention"]["abstained"] is True


def test_unavailable_baseline_is_not_conflated_with_agreement() -> None:
    candidate = _candidate()
    candidate["baseline_disagreement"] = {
        "available": False,
        "reason": "baseline_not_evaluated",
    }
    _resign_candidate(candidate)

    row = _project(candidate)["candidates"][0]

    assert row["baseline_disagreement"]["available"] is False
    assert row["baseline_disagreement"]["disagrees"] is None
    assert row["abstention"] == {
        "abstained": True,
        "reason_codes": ["baseline_evidence_incomplete"],
    }


def test_validator_rejects_sensitive_reinjection_and_permission_drift() -> None:
    projected = _project()
    projected["candidates"][0]["baseline_disagreement"]["reference_pose_path"] = (
        "/srv/private/reference.sdf"
    )
    with pytest.raises(
        EngineV2ProductShadowError,
        match="forbidden reference field",
    ):
        validate_engine_v2_product_shadow_evidence(
            projected,
            stage0_admission=_stage0_admission(),
        )


@pytest.mark.parametrize(
    "measurement_key",
    (
        "atom_0_x",
        "atom_0_y",
        "atom_0_z",
        "ligand_xyz",
        "rotation_matrix_00",
        "sdf_base64_chunk",
    ),
)
def test_projection_rejects_coordinate_encoding_measurement_keys(
    measurement_key: str,
) -> None:
    candidate = _candidate()
    candidate["validity"][measurement_key] = 1.125
    _resign_candidate(candidate)

    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|validity",
    ):
        _project(candidate)


def test_projection_rejects_incomplete_or_contradictory_validity_evidence() -> None:
    empty = _candidate()
    empty["validity"] = {}
    _resign_candidate(empty)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|validity",
    ):
        _project(empty)

    missing_reason = _candidate()
    missing_reason["validity"].pop("selection_eligible")
    _resign_candidate(missing_reason)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|validity",
    ):
        _project(missing_reason)

    reason_for_evaluated = _candidate()
    reason_for_evaluated["validity"]["geometric_valid"] = "unknown"
    _resign_candidate(reason_for_evaluated)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|validity",
    ):
        _project(reason_for_evaluated)

    negative_count = _candidate()
    negative_count["validity"]["exact_pair_count"] = -1
    _resign_candidate(negative_count)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|validity",
    ):
        _project(negative_count)

    valid_with_blocker = _candidate()
    valid_with_blocker["validity"]["unexpected_blocker"] = "posebusters_invalid"
    _resign_candidate(valid_with_blocker)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="wrapper|validity",
    ):
        _project(valid_with_blocker)


def test_projection_rejects_free_form_reason_and_failure_channels() -> None:
    encoded = _candidate()
    encoded["baseline_disagreement"] = {
        "available": True,
        "disagrees": True,
        "reason_codes": ["atom0=1.125,-2.25,3.5;atom1=4,5,6"],
    }
    _resign_candidate(encoded)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="outside the shadow vocabulary",
    ):
        _project(encoded)

    failure = _failure_candidate()
    failure["source_candidate"]["error_code"] = "x=1.0;y=2.0;z=3.0"
    failure["failure"]["error_code"] = "x=1.0;y=2.0;z=3.0"
    _resign_source_candidate(failure)
    with pytest.raises(
        EngineV2ProductShadowError,
        match="failure.error_code must be a neutral identifier",
    ):
        _project(failure)

    projected = _project()
    projected["candidates"][0]["baseline_disagreement"]["reason_codes"] = [
        "/srv/private/reference.sdf"
    ]
    with pytest.raises(
        EngineV2ProductShadowError,
        match="forbidden path value",
    ):
        validate_engine_v2_product_shadow_evidence(
            projected,
            stage0_admission=_stage0_admission(),
        )

    projected = _project()
    projected["policy"]["permissions"]["automatic_rank_mutation_allowed"] = True
    with pytest.raises(
        EngineV2ProductShadowError,
        match="permissions or policy were changed",
    ):
        validate_engine_v2_product_shadow_evidence(
            projected,
            stage0_admission=_stage0_admission(),
        )


def test_validator_rejects_candidate_and_document_receipt_tamper() -> None:
    candidate_tamper = _project()
    candidate_tamper["candidates"][0]["failure_reason"] = "changed"
    with pytest.raises(
        EngineV2ProductShadowError,
        match="failure.reason|self-hash",
    ):
        validate_engine_v2_product_shadow_evidence(
            candidate_tamper,
            stage0_admission=_stage0_admission(),
        )

    document_tamper = _project()
    document_tamper["profile_sha256"] = "7" * 64
    with pytest.raises(
        EngineV2ProductShadowError,
        match="profile is outside|evidence receipt self-hash is invalid",
    ):
        validate_engine_v2_product_shadow_evidence(
            document_tamper,
            stage0_admission=_stage0_admission(),
        )
