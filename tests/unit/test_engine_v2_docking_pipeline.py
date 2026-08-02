from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.pipeline import (
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineStagePayload,
    VerifiedDockingPipelineExecution,
    VerifiedDockingPipelineStageOutput,
    build_docking_pipeline_candidate_evidence,
    build_docking_pipeline_recorded_evidence,
    build_docking_pipeline_source_binding,
    docking_pipeline_stage_payload,
    require_pipeline_stage,
    validate_verified_docking_pipeline_execution_document,
)


_CANDIDATES = ("fixture-candidate-0",)


def _sha256(value: object) -> str:
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
) -> DockingPipelineStagePayload:
    return docking_pipeline_stage_payload(
        value,
        evidence={"stage": stage},
        integrity={"stage": stage, "fixture_integrity": True},
        candidate_ids=_CANDIDATES if candidates else (),
        candidate_count=1 if candidates else None,
    )


def _value(value: object, stage: str) -> object:
    return require_pipeline_stage(value, stage_name=stage).value


@dataclass
class _Component:
    component_id: str
    calls: list[str]
    role: str
    value: int = 1

    def pipeline_configuration(self) -> dict[str, object]:
        return {"role": self.role, "value": self.value}

    def prepare(self, request: object) -> DockingPipelineStagePayload:
        self.calls.append("input_preparer.prepare")
        return _payload({"request": request}, stage="prepared")

    def provide(self, prepared: object) -> DockingPipelineStagePayload:
        self.calls.append("conformer_provider.provide")
        prepared = _value(prepared, "input_preparer.prepare")
        return _payload({"prepared": prepared}, stage="conformers")

    def generate(
        self, prepared: object, conformers: object
    ) -> DockingPipelineStagePayload:
        self.calls.append("proposal_generator.generate")
        prepared = _value(prepared, "input_preparer.prepare")
        conformers = _value(conformers, "conformer_provider.provide")
        return _payload(
            {"prepared": prepared, "conformers": conformers},
            stage="proposals",
            candidates=True,
        )

    def admit(self, prepared: object, proposals: object) -> DockingPipelineStagePayload:
        self.calls.append("geometric_admission.admit")
        prepared = _value(prepared, "input_preparer.prepare")
        proposals = _value(proposals, "proposal_generator.generate")
        return _payload(
            {"prepared": prepared, "proposals": proposals},
            stage="admission",
            candidates=True,
        )

    def bind(self, prepared: object, admission: object) -> DockingPipelineStagePayload:
        self.calls.append("scorer.bind")
        prepared = _value(prepared, "input_preparer.prepare")
        admission = _value(admission, "geometric_admission.admit")
        return _payload(
            {"role": self.role, "prepared": prepared, "admission": admission},
            stage=f"{self.role}-binding",
            candidates=True,
        )

    def refine(
        self,
        prepared: object,
        admission: object,
        scorer: object,
    ) -> DockingPipelineStagePayload:
        self.calls.append("refiner.refine")
        prepared = _value(prepared, "input_preparer.prepare")
        admission = _value(admission, "geometric_admission.admit")
        scorer = _value(scorer, "scorer.bind")
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
        self.calls.append("scorer.score")
        prepared = _value(prepared, "input_preparer.prepare")
        refined = _value(refined, "refiner.refine")
        scorer = _value(scorer, "scorer.bind")
        return _payload(
            {
                "prepared": prepared,
                "refined": refined,
                "scorer": scorer,
            },
            stage="scored",
            candidates=True,
        )

    def evaluate(self, prepared: object, scored: object) -> DockingPipelineStagePayload:
        self.calls.append("validity_evaluator.evaluate")
        prepared = _value(prepared, "input_preparer.prepare")
        scored = _value(scored, "scorer.score")
        return _payload(
            {"prepared": prepared, "scored": scored},
            stage="validity",
            candidates=True,
        )

    def rank(
        self, prepared: object, scored: object, validity: object
    ) -> DockingPipelineStagePayload:
        self.calls.append("ranker.rank")
        prepared = _value(prepared, "input_preparer.prepare")
        scored = _value(scored, "scorer.score")
        validity = _value(validity, "validity_evaluator.evaluate")
        return _payload(
            {"prepared": prepared, "scored": scored, "validity": validity},
            stage="ranking",
            candidates=True,
        )

    def record(self, execution: object) -> DockingPipelineStagePayload:
        self.calls.append("evidence_recorder.record")
        value = {
            "pipeline_profile_id": execution.pipeline_profile_id,
            "pipeline_profile_sha256": execution.pipeline_profile_sha256,
        }
        return _payload(value, stage="recorded", candidates=True)


def _fixture_public_candidate_evidence() -> dict[str, object]:
    from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
        PublicRedockingEngineV2CandidateDiagnostic,
    )
    from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
    from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
        INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
    )

    proposal_sha256 = "1" * 64
    coordinate_sha256 = "2" * 64
    terms = ScorerV1Terms(
        proposal_fingerprint_sha256=proposal_sha256,
        authority_input_receipt_sha256="3" * 64,
        context_fingerprint_sha256="4" * 64,
        config_fingerprint_sha256="5" * 64,
        backend_receipt_sha256="6" * 64,
        typed_vdw=1.25,
        electrostatics=-0.25,
        directional_hbond=0.0,
        hydrophobic_contact=0.0,
        desolvation_proxy=0.0,
        torsion_energy=0.0,
        ligand_strain=0.0,
        weak_pocket_prior=0.0,
        total_score=1.0,
        receptor_candidate_pair_count=12,
        ligand_pair_count=3,
        hbond_count=0,
        hydrophobic_contact_count=0,
        buried_polar_count=0,
    )
    refinement: dict[str, object] = {
        "schema_id": INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
        "source_proposal_sha256": proposal_sha256,
        "post_coordinates_sha256": coordinate_sha256,
        "initial_penalty_binary64_hex": (2.0).hex(),
        "final_penalty_binary64_hex": (1.0).hex(),
        "accepted_steps": 1,
        "accepted_rotation_steps": 0,
        "original_pose_valid": False,
        "total_translation_binary64_hex": [
            (0.1).hex(),
            (0.0).hex(),
            (0.0).hex(),
        ],
        "total_rotation_vector_binary64_hex": [
            (0.0).hex(),
            (0.0).hex(),
            (0.0).hex(),
        ],
    }
    refinement["receipt_sha256"] = _sha256(refinement)
    source = PublicRedockingEngineV2CandidateDiagnostic(
        proposal_index=0,
        status="success",
        proposal_mode="pocket_center_baseline",
        proposal_fingerprint_sha256=proposal_sha256,
        coordinate_fingerprint_sha256=coordinate_sha256,
        score=1.0,
        rmsd_angstrom=1.5,
        geometric_valid=True,
        chemical_valid=True,
        pose_artifact_sha256="7" * 64,
        score_terms_receipt_sha256=terms.receipt_sha256,
        hbond_count=0,
        selection_eligible=True,
        refinement_receipt_sha256=str(refinement["receipt_sha256"]),
        refinement_initial_penalty_binary64_hex=(2.0).hex(),
        refinement_final_penalty_binary64_hex=(1.0).hex(),
        refinement_accepted_steps=1,
        refinement_accepted_rotation_steps=0,
        refinement_original_pose_valid=False,
        refinement_total_translation_binary64_hex=(
            (0.1).hex(),
            (0.0).hex(),
            (0.0).hex(),
        ),
        refinement_total_rotation_vector_binary64_hex=(
            (0.0).hex(),
            (0.0).hex(),
            (0.0).hex(),
        ),
        refinement_receipt_payload=refinement,
        score_term_binary64_hex={
            name: float(getattr(terms, name)).hex()
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
    ).to_dict()
    return build_docking_pipeline_candidate_evidence(
        candidate_id=_CANDIDATES[0],
        source_candidate=source,
        scorer_v1_terms=terms.to_dict(),
        refinement_receipt=refinement,
        baseline_disagreement={
            "available": False,
            "reason": "baseline_not_evaluated",
        },
    )


class _ScientificEvidenceRecorder(_Component):
    def record(self, execution: object) -> DockingPipelineStagePayload:
        self.calls.append("evidence_recorder.record")
        proposal_stage = execution.stage_outputs[2]
        source_binding = build_docking_pipeline_source_binding(
            request_receipt_sha256="8" * 64,
            source_receipt_sha256="3" * 64,
            source_artifact_sha256s={"fixture": "a" * 64},
        )
        verified_execution_evidence = build_docking_pipeline_recorded_evidence(
            source_binding=source_binding,
            candidates=[_fixture_public_candidate_evidence()],
            candidate_ids=proposal_stage.candidate_ids,
            candidate_binding_sha256=proposal_stage.candidate_binding_sha256,
        )
        value = {
            "pipeline_profile_id": execution.pipeline_profile_id,
            "pipeline_profile_sha256": execution.pipeline_profile_sha256,
            "verified_execution_evidence": verified_execution_evidence,
        }
        return docking_pipeline_stage_payload(
            value,
            evidence={
                "stage": "recorded",
                "verified_execution_evidence": verified_execution_evidence,
            },
            integrity={"stage": "recorded", "fixture_integrity": True},
            candidate_ids=proposal_stage.candidate_ids,
            candidate_count=proposal_stage.candidate_count,
        )


GLOBAL_SCORER_BEHAVIOR = 1


class _GlobalComponent(_Component):
    def score(
        self,
        prepared: object,
        refined: object,
        scorer: object,
    ) -> DockingPipelineStagePayload:
        return _payload(
            {"behavior": GLOBAL_SCORER_BEHAVIOR},
            stage="scored",
            candidates=True,
        )


def _pipeline(
    calls: list[str],
    *,
    evidence_recorder: _Component | None = None,
) -> DockingPipeline:
    return DockingPipeline(
        _Component("input/1", calls, "input_preparer"),
        _Component("conformer/1", calls, "conformer_provider"),
        _Component("proposal/1", calls, "proposal_generator"),
        _Component("admission/1", calls, "geometric_admission"),
        _Component("scorer/1", calls, "scorer"),
        _Component("refiner/1", calls, "refiner"),
        _Component("validity/1", calls, "validity_evaluator"),
        _Component("ranker/1", calls, "ranker"),
        evidence_recorder or _Component("recorder/1", calls, "evidence_recorder"),
        profile_id="test.pipeline/1.0.0",
    )


def test_pipeline_runs_all_nine_collaborators_in_frozen_order() -> None:
    calls: list[str] = []
    pipeline = _pipeline(calls)

    result = pipeline.run({"job": "fixture"})

    assert calls == [
        "input_preparer.prepare",
        "conformer_provider.provide",
        "proposal_generator.generate",
        "geometric_admission.admit",
        "scorer.bind",
        "refiner.refine",
        "scorer.score",
        "validity_evaluator.evaluate",
        "ranker.rank",
        "evidence_recorder.record",
    ]
    assert result["pipeline_profile_id"] == "test.pipeline/1.0.0"
    assert result["pipeline_profile_sha256"] == pipeline.profile_sha256
    assert (
        pipeline.profile_document()["candidate_denominator_preservation_required"]
        is True
    )


def test_pipeline_fails_closed_when_a_stage_returns_no_evidence() -> None:
    calls: list[str] = []
    pipeline = _pipeline(calls)
    pipeline.proposal_generator.generate = lambda *args: None  # type: ignore[method-assign]

    with pytest.raises(DockingPipelineError, match="component changed"):
        pipeline.run({"job": "fixture"})


def test_pipeline_rejects_component_replacement_and_identity_drift() -> None:
    calls: list[str] = []
    pipeline = _pipeline(calls)
    frozen_profile = pipeline.profile_sha256

    with pytest.raises(AttributeError):
        pipeline.scorer = _Component("evil.scorer/9", calls, "scorer")

    pipeline.scorer.component_id = "evil.scorer/9"
    with pytest.raises(DockingPipelineError, match="scorer component changed"):
        pipeline.run({"job": "fixture"})
    assert frozen_profile == pipeline._profile_sha256


def test_declared_component_digest_cannot_hide_callable_mutation() -> None:
    calls: list[str] = []
    components = [
        _Component(f"component-{index}/1", calls, role)
        for index, role in enumerate(
            (
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
        )
    ]
    components[4].implementation_sha256 = "a" * 64  # type: ignore[attr-defined]
    pipeline = DockingPipeline(*components, profile_id="test.declared/1.0.0")
    pipeline.scorer.score = lambda *args: {"mutated": True}  # type: ignore[method-assign]

    with pytest.raises(DockingPipelineError, match="scorer component changed"):
        pipeline.run({"job": "fixture"})


def test_mutable_component_configuration_cannot_change_behavior_under_same_profile() -> (
    None
):
    calls: list[str] = []
    pipeline = _pipeline(calls)
    frozen_profile = pipeline.profile_sha256

    pipeline.scorer.value = 999
    with pytest.raises(DockingPipelineError, match="scorer component changed"):
        pipeline.run({"job": "fixture"})
    assert pipeline._profile_sha256 == frozen_profile


def test_referenced_module_global_cannot_change_behavior_under_same_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
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
    components = [
        (
            _GlobalComponent(f"component-{index}/1", calls, role)
            if role == "scorer"
            else _Component(f"component-{index}/1", calls, role)
        )
        for index, role in enumerate(roles)
    ]
    pipeline = DockingPipeline(*components, profile_id="test.globals/1.0.0")
    frozen_profile = pipeline.profile_sha256

    monkeypatch.setattr(sys.modules[__name__], "GLOBAL_SCORER_BEHAVIOR", 2)
    with pytest.raises(DockingPipelineError, match="scorer component changed"):
        pipeline.run({"job": "fixture"})
    assert pipeline._profile_sha256 == frozen_profile


def test_canonical_profile_sha256_is_stable_across_processes() -> None:
    command = (
        sys.executable,
        "-c",
        (
            "from betelgeuze_engine_v2.cli import "
            "build_canonical_docking_pipeline; "
            "print(build_canonical_docking_pipeline().profile_sha256)"
        ),
    )
    observed = {
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        for _ in range(3)
    }
    assert len(observed) == 1
    assert len(observed.pop()) == 64


def test_verified_execution_is_factory_only_and_exposes_typed_stage_outputs() -> None:
    with pytest.raises(DockingPipelineError, match="created only by DockingPipeline"):
        VerifiedDockingPipelineExecution(
            authority=object(),
            execution=None,  # type: ignore[arg-type]
            recorder_stage=None,  # type: ignore[arg-type]
        )
    with pytest.raises(DockingPipelineError, match="created only by DockingPipeline"):
        VerifiedDockingPipelineStageOutput(
            authority=object(),
            stage_name="input_preparer.prepare",
            owner_role="input_preparer",
            owner_component_id="forged/1",
            owner_component_receipt_sha256="b" * 64,
            upstream_receipt_sha256s=(),
            payload=_payload({}, stage="forged"),
        )

    verified = _pipeline([]).run_verified({"job": "fixture"})

    assert isinstance(verified, VerifiedDockingPipelineExecution)
    assert len(verified.stage_outputs) == 10
    assert all(
        isinstance(stage, VerifiedDockingPipelineStageOutput)
        for stage in verified.stage_outputs
    )


def test_public_candidate_wrapper_cross_binds_full_scoring_and_refinement() -> None:
    candidate = _fixture_public_candidate_evidence()
    source = deepcopy(candidate["source_candidate"])
    source["score_terms_receipt_sha256"] = "c" * 64

    with pytest.raises(DockingPipelineError, match="ScorerV1Terms.*cross-wired"):
        build_docking_pipeline_candidate_evidence(
            candidate_id=str(candidate["candidate_id"]),
            source_candidate=source,
            scorer_v1_terms=candidate["scorer_v1_terms"],
            refinement_receipt=candidate["refinement_receipt"],
            baseline_disagreement=candidate["baseline_disagreement"],
        )

    with pytest.raises(DockingPipelineError, match="fields are not exact"):
        build_docking_pipeline_candidate_evidence(
            candidate_id=str(candidate["candidate_id"]),
            source_candidate=candidate["source_candidate"],
            scorer_v1_terms=candidate["scorer_v1_terms"],
            refinement_receipt=candidate["refinement_receipt"],
            baseline_disagreement={
                **candidate["baseline_disagreement"],
                "result_dependent_note": "forbidden",
            },
        )


def test_recorded_evidence_cross_binds_stage_candidate_ids_and_source_authority() -> (
    None
):
    candidate = _fixture_public_candidate_evidence()
    exact_binding = _sha256({"candidate_count": 1, "candidate_ids": list(_CANDIDATES)})
    source = build_docking_pipeline_source_binding(
        request_receipt_sha256="8" * 64,
        source_receipt_sha256="3" * 64,
        source_artifact_sha256s={"fixture": "a" * 64},
    )

    with pytest.raises(DockingPipelineError, match="candidate evidence"):
        build_docking_pipeline_recorded_evidence(
            source_binding=source,
            candidates=[candidate],
            candidate_ids=("different-stage-candidate",),
            candidate_binding_sha256=_sha256(
                {
                    "candidate_count": 1,
                    "candidate_ids": ["different-stage-candidate"],
                }
            ),
        )

    wrong_source = build_docking_pipeline_source_binding(
        request_receipt_sha256="8" * 64,
        source_receipt_sha256="9" * 64,
        source_artifact_sha256s={"fixture": "a" * 64},
    )
    with pytest.raises(DockingPipelineError, match="scoring authority.*source"):
        build_docking_pipeline_recorded_evidence(
            source_binding=wrong_source,
            candidates=[candidate],
            candidate_ids=_CANDIDATES,
            candidate_binding_sha256=exact_binding,
        )


def test_serialized_verified_execution_round_trip_and_tamper_rejection() -> None:
    calls: list[str] = []
    verified = _pipeline(
        calls,
        evidence_recorder=_ScientificEvidenceRecorder(
            "scientific-recorder/1",
            calls,
            "evidence_recorder",
        ),
    ).run_verified({"job": "fixture"})
    document = verified.to_dict()
    profile = dict(verified.profile_document)
    recorded = dict(verified.recorded_evidence["verified_execution_evidence"])

    assert (
        validate_verified_docking_pipeline_execution_document(
            document,
            profile,
            recorded,
        )
        == document
    )
    assert len(verified.candidate_evidence) == 1
    assert verified.source_binding == recorded["source_binding"]
    assert (
        verified.result_binding["candidate_payload_sha256"]
        == recorded["candidate_payload_sha256"]
    )

    cross_wired_stage = deepcopy(document)
    cross_wired_stage["stage_receipts"][3]["upstream_receipt_sha256s"] = [
        cross_wired_stage["stage_receipts"][1]["receipt_sha256"]
    ]
    with pytest.raises(DockingPipelineError, match="upstream receipt chain"):
        validate_verified_docking_pipeline_execution_document(
            cross_wired_stage,
            profile,
            recorded,
        )

    changed_candidates = deepcopy(recorded)
    changed_candidates["candidates"][0]["baseline_disagreement"]["reason"] = (
        "tampered_after_recording"
    )
    with pytest.raises(DockingPipelineError, match="candidate evidence receipt"):
        validate_verified_docking_pipeline_execution_document(
            document,
            profile,
            changed_candidates,
        )

    cross_wired_source = deepcopy(document)
    cross_wired_source["source_binding"] = build_docking_pipeline_source_binding(
        request_receipt_sha256="e" * 64,
        source_receipt_sha256="9" * 64,
        source_artifact_sha256s={"fixture": "a" * 64},
    )
    with pytest.raises(DockingPipelineError, match="source binding is cross-wired"):
        validate_verified_docking_pipeline_execution_document(
            cross_wired_source,
            profile,
            recorded,
        )

    cross_wired_result = deepcopy(document)
    cross_wired_result["result_binding"]["candidate_payload_sha256"] = "f" * 64
    with pytest.raises(DockingPipelineError, match="result binding is cross-wired"):
        validate_verified_docking_pipeline_execution_document(
            cross_wired_result,
            profile,
            recorded,
        )

    changed_profile = deepcopy(profile)
    changed_profile["profile_id"] = "cross-wired.profile/9"
    with pytest.raises(DockingPipelineError, match="profile SHA-256"):
        validate_verified_docking_pipeline_execution_document(
            document,
            changed_profile,
            recorded,
        )

    changed_execution = deepcopy(document)
    changed_execution["receipt_sha256"] = "d" * 64
    with pytest.raises(DockingPipelineError, match="execution receipt changed"):
        validate_verified_docking_pipeline_execution_document(
            changed_execution,
            profile,
            recorded,
        )
