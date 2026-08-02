from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path

import pytest

import api.engine_v2_shadow as api_shadow
from api.request_identity import ProductRequestIdentity
from api.validated_runner_execution_evidence import (
    ENGINE_V2_SHADOW_RUNNER_PROFILE_ID,
    build_validated_runner_execution_evidence,
    engine_v2_shadow_execution_evidence,
    is_engine_v2_shadow_execution_evidence,
    require_engine_v2_shadow_execution_evidence,
)
from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    VerifiedStage0Admission,
    _VERIFIED_STAGE0_ADMISSION_AUTHORITY,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.fresh_run_verifier import (
    VerifiedFreshRun,
    _VERIFIED_FRESH_RUN_AUTHORITY,
)
from betelgeuze_engine_v2.pipeline import (
    DockingPipeline,
    DockingPipelineStagePayload,
    VerifiedDockingPipelineExecution,
    build_docking_pipeline_candidate_evidence,
    build_docking_pipeline_recorded_evidence,
    build_docking_pipeline_source_binding,
    docking_pipeline_stage_payload,
)
from betelgeuze_product.engine_v2_shadow import (
    EngineV2ProductShadowAccessError,
    project_operator_engine_v2_shadow,
)


_CANDIDATE_IDS = ("fixture-candidate-0",)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _payload(
    value: object,
    *,
    stage: str,
    candidates: bool = False,
    evidence: dict[str, object] | None = None,
) -> DockingPipelineStagePayload:
    return docking_pipeline_stage_payload(
        value,
        evidence=evidence or {"fixture_stage": stage},
        integrity={"fixture_stage": stage, "immutable": True},
        candidate_ids=_CANDIDATE_IDS if candidates else (),
        candidate_count=1 if candidates else None,
    )


def _failure_candidate() -> dict[str, object]:
    return build_docking_pipeline_candidate_evidence(
        candidate_id=_CANDIDATE_IDS[0],
        source_candidate={
            "schema_id": PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
            "proposal_index": 0,
            "status": "failure",
            "proposal_mode": "uniform_fallback",
            "error_code": "candidate_execution_failed",
        },
        scorer_v1_terms=None,
        refinement_receipt=None,
        baseline_disagreement={
            "available": False,
            "reason": "baseline_not_evaluated",
        },
    )


@dataclass
class _Component:
    component_id: str
    role: str

    def pipeline_configuration(self) -> dict[str, object]:
        return {"role": self.role, "fixture": True}

    def prepare(self, request: object) -> DockingPipelineStagePayload:
        return _payload({"request": request}, stage="prepared")

    def provide(self, prepared: object) -> DockingPipelineStagePayload:
        return _payload({"prepared": prepared}, stage="conformers")

    def generate(
        self, prepared: object, conformers: object
    ) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "conformers": conformers},
            stage="proposals",
            candidates=True,
        )

    def admit(self, prepared: object, proposals: object) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "proposals": proposals},
            stage="admission",
            candidates=True,
        )

    def bind(self, prepared: object, admission: object) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "admission": admission},
            stage="scorer-binding",
            candidates=True,
        )

    def refine(
        self,
        prepared: object,
        admission: object,
        scorer: object,
    ) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "admission": admission, "scorer": scorer},
            stage="refined",
            candidates=True,
        )

    def score(
        self,
        prepared: object,
        refined: object,
        scorer: object,
    ) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "refined": refined, "scorer": scorer},
            stage="scored",
            candidates=True,
        )

    def evaluate(self, prepared: object, scored: object) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "scored": scored},
            stage="validity",
            candidates=True,
        )

    def rank(
        self,
        prepared: object,
        scored: object,
        validity: object,
    ) -> DockingPipelineStagePayload:
        return _payload(
            {"prepared": prepared, "scored": scored, "validity": validity},
            stage="ranking",
            candidates=True,
        )

    def record(self, execution: object) -> DockingPipelineStagePayload:
        proposal = execution.stage_outputs[2]
        recorded = build_docking_pipeline_recorded_evidence(
            source_binding=build_docking_pipeline_source_binding(
                request_receipt_sha256="1" * 64,
                source_receipt_sha256="2" * 64,
                source_artifact_sha256s={"fixture": "3" * 64},
            ),
            candidates=[_failure_candidate()],
            candidate_ids=proposal.candidate_ids,
            candidate_binding_sha256=proposal.candidate_binding_sha256,
        )
        value = {"verified_execution_evidence": recorded}
        return _payload(
            value,
            stage="recorded",
            candidates=True,
            evidence={
                "fixture_stage": "recorded",
                "verified_execution_evidence": recorded,
            },
        )


def _verified_execution() -> VerifiedDockingPipelineExecution:
    roles = (
        "input_preparer",
        "conformer_provider",
        "proposal_generator",
        "geometric_admission",
        "scorer",
        "refiner",
        "validity_evaluator",
        "ranker",
        "evidence_recorder",
    )
    pipeline = DockingPipeline(
        *(_Component(f"fixture.{role}/1", role) for role in roles),
        profile_id="fixture.engine_v2_shadow_pipeline/1.0.0",
    )
    return pipeline.run_verified({"fixture": "shadow"})


def _stage0_admission(
    verified_execution: VerifiedDockingPipelineExecution,
) -> VerifiedStage0Admission:
    profile = verified_execution.profile_document
    return VerifiedStage0Admission._from_verified_policy(
        policy_sha256="4" * 64,
        source_freeze_sha256="5" * 64,
        execution_profile_sha256="6" * 64,
        reviewer_id="independent-reviewer",
        operator_id="independent-operator",
        governance_mode="independent_three_role",
        independent_review_complete=True,
        trusted_review_time_authority_id="fixture-time-authority",
        trusted_review_time_evidence_sha256="7" * 64,
        external_run_once_authority_id="fixture-run-once-authority",
        external_run_once_reservation_sha256="8" * 64,
        fresh_run_identity_sha256="9" * 64,
        docking_pipeline_profile_id=str(profile["profile_id"]),
        docking_pipeline_profile_sha256=str(profile["profile_sha256"]),
        verification_authority=_VERIFIED_STAGE0_ADMISSION_AUTHORITY,
    )


def _identity(
    *, authenticated: bool = True, is_admin: bool = True
) -> ProductRequestIdentity:
    return ProductRequestIdentity(
        tenant_id="internal-ops",
        principal="operator:reviewer-1",
        authenticated=authenticated,
        is_admin=is_admin,
    )


def _runner_evidence() -> dict[str, object]:
    return engine_v2_shadow_execution_evidence("shadow-job-1")


def _fresh_activation(
    admission: VerifiedStage0Admission,
    *,
    exactly_once_verified: bool = True,
) -> VerifiedFreshRun:
    return VerifiedFreshRun._from_verified_root(
        reservation_sha256="a" * 64,
        report_fingerprint_sha256="b" * 64,
        report_file_sha256="c" * 64,
        artifact_manifest_sha256="d" * 64,
        artifact_manifest_file_sha256="e" * 64,
        completion_sha256="f" * 64,
        stage0_admission_receipt_sha256=admission.receipt_sha256,
        external_run_once_reservation_sha256=(
            admission.external_run_once_reservation_sha256
        ),
        fresh_run_identity_sha256=admission.fresh_run_identity_sha256,
        docking_pipeline_profile_id=admission.docking_pipeline_profile_id,
        docking_pipeline_profile_sha256=(admission.docking_pipeline_profile_sha256),
        stage0_binding_authority="verified_stage0_policy",
        stage0_policy_verified=True,
        external_worm_reservation_cryptographically_verified=True,
        exactly_once_verified=exactly_once_verified,
        verification_authority=_VERIFIED_FRESH_RUN_AUTHORITY,
    )


def test_shadow_runner_evidence_uses_only_server_owned_job_and_purpose() -> None:
    generic_contract = {
        "execution_mode": "restricted-production",
        "customer_submission_allowed": True,
        "synthetic_input_allowed": False,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
    }
    injected_request = {
        "execution_evidence_purpose": "engine_v2_operator_shadow_v1",
        "execution_evidence_source_actor": "engine_v2_docking_pipeline",
        "runner_profile_params": {"docking_job_id": "caller-controlled-job"},
    }

    generic = build_validated_runner_execution_evidence(
        job_id="server-owned-job",
        profile_id="generic_profile",
        execution_contract=generic_contract,
        request_data=injected_request,
    )

    assert generic["evidence_purpose"] == ""
    assert generic["source_actor"] == ""
    assert generic["docking_job_id"] == "server-owned-job"

    shadow_contract = {
        **generic_contract,
        "customer_submission_allowed": False,
    }
    shadow = build_validated_runner_execution_evidence(
        job_id="server-owned-shadow-job",
        profile_id=ENGINE_V2_SHADOW_RUNNER_PROFILE_ID,
        execution_contract=shadow_contract,
        request_data=injected_request,
    )
    assert require_engine_v2_shadow_execution_evidence(shadow) == shadow
    assert is_engine_v2_shadow_execution_evidence(shadow) is True
    assert shadow["docking_job_id"] == "server-owned-shadow-job"
    assert shadow["runner_profile_id"] == ENGINE_V2_SHADOW_RUNNER_PROFILE_ID

    foreign_profile = dict(shadow)
    foreign_profile["runner_profile_id"] = "caller-selected-shadow-profile"
    with pytest.raises(ValueError, match="not an Engine V2 shadow execution"):
        require_engine_v2_shadow_execution_evidence(foreign_profile)
    assert is_engine_v2_shadow_execution_evidence(foreign_profile) is False
    assert is_engine_v2_shadow_execution_evidence(generic) is False


def test_generic_result_route_rejects_signed_shadow_artifact_and_closes_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main
    from fastapi import HTTPException

    class _VerifiedResult:
        artifact_type = "json"
        media_type = "application/json"
        validated_runner_execution_evidence = _runner_evidence()

        def __init__(self) -> None:
            self.result_snapshot = io.BytesIO(b"{}\n")
            self.closed = False

        def close(self) -> None:
            self.closed = True
            self.result_snapshot.close()

    verified = _VerifiedResult()
    monkeypatch.setattr(api_main, "request_identity", lambda request: _identity())
    monkeypatch.setattr(api_main, "get_job_store", object)
    monkeypatch.setattr(
        api_main,
        "get_simulation_job_for_identity",
        lambda *args, **kwargs: {"published_status_path": "status.json"},
    )
    monkeypatch.setattr(
        api_main,
        "read_confined_json_object",
        lambda *args, **kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        api_main,
        "job_results_dir",
        lambda job_id: tmp_path,
    )
    monkeypatch.setattr(
        api_main,
        "verify_completed_result_artifacts",
        lambda **kwargs: verified,
    )

    with pytest.raises(HTTPException) as exc_info:
        api_main.get_simulation_results("shadow-job-1", request=object())

    assert exc_info.value.status_code == 403
    assert verified.closed is True
    assert verified.result_snapshot.closed is True


def test_authenticated_operator_adapter_accepts_only_typed_verified_execution() -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)

    result = project_operator_engine_v2_shadow(
        identity=_identity(),
        stage0_admission=admission,
        verified_fresh_run=_fresh_activation(admission),
        verified_execution=verified,
    )

    assert result["access_scope"] == "authenticated_operator_read_only"
    assert result["shared_docking_pipeline_profile_verified"] is True
    assert result["execution_performed"] is False
    assert result["primary_rank_mutation_performed"] is False
    assert result["customer_pose_emitted"] is False
    assert result["production_claim_granted"] is False
    evidence = result["engine_v2_shadow_evidence"]
    assert evidence["candidate_count"] == verified.candidate_count
    assert evidence["profile_sha256"] == verified.profile_document["profile_sha256"]

    with pytest.raises(
        EngineV2ProductShadowAccessError,
        match="factory-created VerifiedDockingPipelineExecution",
    ):
        project_operator_engine_v2_shadow(
            identity=_identity(),
            stage0_admission=admission,
            verified_fresh_run=_fresh_activation(admission),
            verified_execution=verified.to_dict(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "identity",
    (_identity(authenticated=False), _identity(is_admin=False)),
)
def test_operator_adapter_rejects_unauthenticated_or_non_admin_identity(
    identity: object,
) -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)
    with pytest.raises(
        EngineV2ProductShadowAccessError,
        match="authenticated administrator",
    ):
        project_operator_engine_v2_shadow(
            identity=identity,
            stage0_admission=admission,
            verified_fresh_run=_fresh_activation(admission),
            verified_execution=verified,
        )


def test_api_direct_adapter_delegates_only_the_verified_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)
    fresh = _fresh_activation(admission)
    identity = _identity()
    authorized: list[object] = []
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"execution_performed": False}

    monkeypatch.setattr(
        api_shadow,
        "_identity_authorizers",
        lambda: (lambda request: identity, authorized.append),
    )
    monkeypatch.setattr(api_shadow, "_product_projector", lambda: _capture)

    result = api_shadow.get_engine_v2_operator_shadow(
        object(),  # type: ignore[arg-type]
        stage0_admission=admission,
        verified_fresh_run=fresh,
        verified_execution=verified,
    )

    assert result == {"execution_performed": False}
    assert authorized == [identity]
    assert captured == {
        "identity": identity,
        "stage0_admission": admission,
        "verified_fresh_run": fresh,
        "verified_execution": verified,
    }


def test_shadow_artifact_requires_exactly_once_fresh_activation_authority() -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)
    offline_verification = _fresh_activation(
        admission,
        exactly_once_verified=False,
    )

    with pytest.raises(ValueError, match="activation authority is incomplete"):
        api_shadow.build_engine_v2_shadow_server_artifact(
            job_id="shadow-job-1",
            verified_execution=verified,
            stage0_admission=admission,
            verified_fresh_run=offline_verification,
        )
    with pytest.raises(
        EngineV2ProductShadowAccessError,
        match="Fresh-128 activation authority",
    ):
        project_operator_engine_v2_shadow(
            identity=_identity(),
            stage0_admission=admission,
            verified_fresh_run=offline_verification,
            verified_execution=verified,
        )
    with pytest.raises(TypeError, match="factory-created VerifiedFreshRun"):
        api_shadow.build_engine_v2_shadow_server_artifact(
            job_id="shadow-job-1",
            verified_execution=verified,
            stage0_admission=admission,
            verified_fresh_run=_fresh_activation(admission).to_dict(),
        )


def test_server_artifact_round_trip_revalidates_serialized_execution() -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)
    fresh = _fresh_activation(admission)
    runner_evidence = _runner_evidence()
    artifact = api_shadow.build_engine_v2_shadow_server_artifact(
        job_id="shadow-job-1",
        verified_execution=verified,
        stage0_admission=admission,
        verified_fresh_run=fresh,
    )

    assert artifact["scientific_inputs_derived_from_verified_execution"] is True
    assert artifact["outer_result_manifest_signature_required"] is True
    assert "candidates" not in artifact
    assert "source_evidence_document" not in artifact
    assert "upstream_evidence_document" not in artifact
    result = api_shadow._validate_and_project_engine_v2_shadow_server_artifact(
        artifact=artifact,
        receipt_sha256=str(artifact["receipt_sha256"]),
        job_id="shadow-job-1",
        identity=_identity(),
        stage0_admission=admission,
        verified_fresh_run=fresh,
        signed_runner_execution_evidence=runner_evidence,
    )
    assert result["access_scope"] == "authenticated_operator_read_only"
    assert result["execution_performed"] is False


def test_server_artifact_rejects_execution_and_signed_purpose_tampering() -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)
    fresh = _fresh_activation(admission)
    runner_evidence = _runner_evidence()
    artifact = api_shadow.build_engine_v2_shadow_server_artifact(
        job_id="shadow-job-1",
        verified_execution=verified,
        stage0_admission=admission,
        verified_fresh_run=fresh,
    )
    tampered = deepcopy(artifact)
    tampered_execution = tampered["verified_docking_pipeline_execution"]
    tampered_execution["stage_receipts"][3]["upstream_receipt_sha256s"] = ["a" * 64]
    tampered["receipt_sha256"] = _sha(
        {key: value for key, value in tampered.items() if key != "receipt_sha256"}
    )
    with pytest.raises(RuntimeError, match="upstream receipt chain"):
        api_shadow._validate_and_project_engine_v2_shadow_server_artifact(
            artifact=tampered,
            receipt_sha256=str(tampered["receipt_sha256"]),
            job_id="shadow-job-1",
            identity=_identity(),
            stage0_admission=admission,
            verified_fresh_run=fresh,
            signed_runner_execution_evidence=runner_evidence,
        )

    tampered_profile = deepcopy(artifact)
    tampered_profile["profile_document"]["components"]["scorer"]["component_id"] = (
        "tampered.scorer/9"
    )
    tampered_profile["receipt_sha256"] = _sha(
        {
            key: value
            for key, value in tampered_profile.items()
            if key != "receipt_sha256"
        }
    )
    with pytest.raises(RuntimeError):
        api_shadow._validate_and_project_engine_v2_shadow_server_artifact(
            artifact=tampered_profile,
            receipt_sha256=str(tampered_profile["receipt_sha256"]),
            job_id="shadow-job-1",
            identity=_identity(),
            stage0_admission=admission,
            verified_fresh_run=fresh,
            signed_runner_execution_evidence=runner_evidence,
        )

    tampered_candidates = deepcopy(artifact)
    tampered_candidates["recorded_evidence_document"]["candidates"][0]["failure"][
        "error_code"
    ] = "scoring_failed"
    tampered_candidates["receipt_sha256"] = _sha(
        {
            key: value
            for key, value in tampered_candidates.items()
            if key != "receipt_sha256"
        }
    )
    with pytest.raises(RuntimeError):
        api_shadow._validate_and_project_engine_v2_shadow_server_artifact(
            artifact=tampered_candidates,
            receipt_sha256=str(tampered_candidates["receipt_sha256"]),
            job_id="shadow-job-1",
            identity=_identity(),
            stage0_admission=admission,
            verified_fresh_run=fresh,
            signed_runner_execution_evidence=runner_evidence,
        )

    cross_wired_runner = dict(runner_evidence)
    cross_wired_runner["docking_job_id"] = "other-job"
    with pytest.raises(ValueError, match="cross-wired to the signed job"):
        api_shadow._validate_and_project_engine_v2_shadow_server_artifact(
            artifact=artifact,
            receipt_sha256=str(artifact["receipt_sha256"]),
            job_id="shadow-job-1",
            identity=_identity(),
            stage0_admission=admission,
            verified_fresh_run=fresh,
            signed_runner_execution_evidence=cross_wired_runner,
        )


def test_server_artifact_builder_rejects_serialized_or_crosswired_input() -> None:
    verified = _verified_execution()
    admission = _stage0_admission(verified)
    fresh = _fresh_activation(admission)
    with pytest.raises(
        TypeError, match="factory-created VerifiedDockingPipelineExecution"
    ):
        api_shadow.build_engine_v2_shadow_server_artifact(
            job_id="shadow-job-1",
            verified_execution=verified.to_dict(),
            stage0_admission=admission,
            verified_fresh_run=fresh,
        )

    other_verified = _verified_execution()
    other_admission = VerifiedStage0Admission._from_verified_policy(
        policy_sha256="4" * 64,
        source_freeze_sha256="5" * 64,
        execution_profile_sha256="6" * 64,
        reviewer_id="independent-reviewer",
        operator_id="independent-operator",
        governance_mode="independent_three_role",
        independent_review_complete=True,
        trusted_review_time_authority_id="fixture-time-authority",
        trusted_review_time_evidence_sha256="7" * 64,
        external_run_once_authority_id="fixture-run-once-authority",
        external_run_once_reservation_sha256="8" * 64,
        fresh_run_identity_sha256="9" * 64,
        docking_pipeline_profile_id="crosswired.profile/1",
        docking_pipeline_profile_sha256="a" * 64,
        verification_authority=_VERIFIED_STAGE0_ADMISSION_AUTHORITY,
    )
    with pytest.raises(ValueError, match="profile are cross-wired"):
        api_shadow.build_engine_v2_shadow_server_artifact(
            job_id="shadow-job-1",
            verified_execution=other_verified,
            stage0_admission=other_admission,
            verified_fresh_run=_fresh_activation(other_admission),
        )
