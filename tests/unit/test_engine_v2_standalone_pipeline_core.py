from __future__ import annotations

from dataclasses import fields, replace
import hashlib
from importlib import resources
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    CandidateEvidenceV1,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
    DockingPipelineResultV1,
    Residue,
    StructureProvenance,
    SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
    SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER,
    SYNTHETIC_D0_FIXTURE_REQUEST_SHA256,
    SYNTHETIC_ONLY_ACKNOWLEDGMENT,
    UNVERIFIED_COMPONENT_BINDING,
    UNVERIFIED_COMPONENT_BLOCKER,
    UNVERIFIED_SIDE_EFFECT_BLOCKER,
    repository_synthetic_d0_fixture_admission,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    CURRENT_V7_FIXED64_PROFILE_ID,
    EXTERNAL_AUTHORITY_BLOCKERS,
    PIPELINE_CLAIM_BLOCKERS,
    SEALED_CANONICAL_COMPONENT_BINDING,
    DockingScope,
    PocketDefinition,
)
from betelgeuze_engine_v2.docking.pipeline import (  # noqa: E402
    CanonicalPreparedInputPreparer,
)
from betelgeuze_engine_v2.docking import pipeline as pipeline_module  # noqa: E402
from betelgeuze_engine_v2.docking.scorer_v1 import (  # noqa: E402
    ChemistryPoseScorerV1,
    ScorerV1Error,
)
from betelgeuze_engine_v2.docking.search import (  # noqa: E402
    DockingBatchScoreOutcome,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-consumer-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "H", "O", "H")
    charges = (0.0, -0.2, 0.2, -0.4, 0.4)
    coordinates = (
        [-2.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [-2.0, 0.0, 0.0],
        [-3.0, 0.0, 0.0],
    )
    return AllAtomSystem(
        system_id="standalone-consumer-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=1, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
            Bond(index=3, atom_i=3, atom_j=4),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("ligand", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    elements = ("O", "N", "H", "C", "H")
    charges = (-0.4, -0.2, 0.2, 0.0, 0.4)
    coordinates = (
        [2.0, 0.0, 0.0],
        [3.0, 3.0, 0.0],
        [2.5, 2.5, 0.0],
        [-2.0, 3.0, 0.0],
        [6.0, 6.0, 0.0],
    )
    return AllAtomSystem(
        system_id="standalone-consumer-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(Bond(index=0, atom_i=1, atom_j=2),),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("receptor", "b" * 64),
    )


def _pocket() -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="consumer-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )


def _request(
    *,
    ligand: AllAtomSystem | None = None,
) -> DockingPipelineRequestV1:
    return DockingPipelineRequestV1(
        receptor_system=_receptor(),
        ligand_system=ligand or _ligand(),
        pocket=_pocket(),
        seed=4301,
        synthetic_only_acknowledgment=SYNTHETIC_ONLY_ACKNOWLEDGMENT,
        fixture_admission=repository_synthetic_d0_fixture_admission(),
        profile=DockingPipelineProfileV1(),
    )


def test_current_v7_profile_is_exact_fixed64() -> None:
    profile = DockingPipelineProfileV1()

    assert profile.profile_id == CURRENT_V7_FIXED64_PROFILE_ID
    assert profile.candidate_count == 64
    assert profile.top_k == 5
    assert profile.max_refinement_steps == 24
    assert profile.to_dict()["clearance_shadow_selection_enabled"] is False
    assert profile.to_dict()["failure_denominator_required"] == 64
    assert profile.to_dict()["full_budget_receipt_required"] is True
    assert profile.to_dict()["full_proposal_plan_receipt_required"] is True

    with pytest.raises(DockingPipelineError, match="fixed64 profile was changed"):
        DockingPipelineProfileV1(candidate_count=63)

    admission = repository_synthetic_d0_fixture_admission()
    assert admission.candidate_count == 64
    assert admission.top_k == 5
    assert admission.manifest_sha256 == SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
    assert admission.request_sha256 == SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
    with pytest.raises(DockingPipelineError, match="repository manifest"):
        replace(admission)


def test_structural_receipt_is_repeatable_across_processes() -> None:
    test_path = Path(__file__).resolve()
    command = (
        "import runpy; "
        f"ns=runpy.run_path({str(test_path)!r}); "
        "print(ns['DockingPipeline']().run(ns['_request']()).receipt_sha256)"
    )
    observed = tuple(
        subprocess.check_output(
            [sys.executable, "-c", command],
            cwd=test_path.parents[2],
            text=True,
        ).strip()
        for _ in range(2)
    )

    assert len(set(observed)) == 1
    assert len(observed[0]) == 64


def test_pipeline_is_deterministic_failure_complete_and_claim_blocked() -> None:
    pipeline = DockingPipeline()
    first = pipeline.run(_request())
    second = pipeline.run(_request())

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(first.candidates) == 64
    assert first.success_count + first.failure_count == 64
    assert tuple(row.proposal_index for row in first.candidates) == tuple(range(64))
    assert all(
        row.geometric_admission_status
        == "not_enabled_in_current_v7_baseline"
        for row in first.candidates
    )
    assert all(code in first.blockers for code in EXTERNAL_AUTHORITY_BLOCKERS)
    assert all(code in first.blockers for code in PIPELINE_CLAIM_BLOCKERS)
    document = first.to_dict()
    assert document["scorer_source_sha256"] == hashlib.sha256(
        resources.files("betelgeuze_engine_v2.docking").joinpath("scorer_v1.py").read_bytes()
    ).hexdigest()
    assert document["refiner_source_sha256"] == hashlib.sha256(
        resources.files("betelgeuze_engine_v2.docking")
        .joinpath("torsion_contact_refinement.py")
        .read_bytes()
    ).hexdigest()
    for receipt_field in (
        "prepared_input_receipt_sha256",
        "conformer_receipt_sha256",
        "authority_input_receipt_sha256",
        "proposal_plan_receipt_sha256",
    ):
        assert len(document[receipt_field]) == 64
    assert document["failure_denominator_preserved"] is True
    assert document["caller_acknowledged_synthetic_fixture_only"] is True
    assert document["synthetic_fixture_identity_independently_verified"] is True
    assert SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER in first.blockers
    assert document["synthetic_d0_fixture_manifest_sha256"] == (
        SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
    )
    assert document["request_sha256"] == SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
    assert (
        document["synthetic_only_acknowledgment"]
        == SYNTHETIC_ONLY_ACKNOWLEDGMENT
    )
    assert document["component_binding_mode"] == SEALED_CANONICAL_COMPONENT_BINDING
    assert document["canonical_components_sealed"] is True
    assert document["arbitrary_dependency_injection_used"] is False
    assert document["external_reservation_requested"] is False
    assert document["historical_execution_authorized"] is False
    assert document["fresh_holdout_execution_authorized"] is False
    assert document["product_execution_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False
    assert document["claim_safe"] is False
    for row in first.candidates:
        assert len(row.receipt_sha256) == 64
        assert row.to_dict()["construction_proof_scope"] == (
            "process_local_not_serialized_not_cryptographic_attestation"
        )
        assert not any("proof_sha256" in key for key in row.to_dict())
        if row.status == "success":
            assert row.scorer_terms is not None
            assert row.refinement_receipt is not None
            assert row.pose_validity is not None
        else:
            assert row.error_code


def test_candidate_and_result_receipts_are_deep_canonical_and_fail_closed() -> None:
    result = DockingPipeline().run(_request())
    successful = next(row for row in result.candidates if row.status == "success")
    refinement = successful.to_dict()["refinement_receipt"]
    assert isinstance(refinement, dict)
    cloned = replace(successful, refinement_receipt=refinement)
    receipt_sha256 = cloned.receipt_sha256

    nested = refinement["baseline_v6_receipt_payload"]
    assert isinstance(nested, dict)
    nested["claim_safe"] = True
    assert cloned.receipt_sha256 == receipt_sha256
    assert cloned.refinement_receipt is not None
    assert cloned.refinement_receipt["baseline_v6_receipt_payload"] != nested
    with pytest.raises(TypeError):
        cloned.refinement_receipt["claim_safe"] = True  # type: ignore[index]

    forged_refinement = successful.to_dict()["refinement_receipt"]
    assert isinstance(forged_refinement, dict)
    forged_refinement["forged_lineage_note"] = "format-valid-but-not-recorded"
    forged_refinement.pop("receipt_sha256")
    forged_refinement["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            forged_refinement,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    with pytest.raises(DockingPipelineError, match="construction proof mismatch"):
        replace(successful, refinement_receipt=forged_refinement)
    with pytest.raises(DockingPipelineError, match="construction proof mismatch"):
        replace(successful, search_row_sha256="e" * 64)
    candidate_constructor_fields = {
        item.name: getattr(successful, item.name)
        for item in fields(successful)
        if item.init and item.name != "_construction_proof_sha256"
    }
    with pytest.raises(DockingPipelineError, match="construction proof"):
        CandidateEvidenceV1(**candidate_constructor_fields)

    with pytest.raises(DockingPipelineError, match="lacks complete evidence"):
        replace(successful, scorer_terms=None)
    incomplete_terms = successful.to_dict()["scorer_terms"]
    assert isinstance(incomplete_terms, dict)
    incomplete_terms.pop("typed_vdw_binary64_hex")
    with pytest.raises(DockingPipelineError, match="ScorerV1Terms receipt is incomplete"):
        replace(successful, scorer_terms=incomplete_terms)
    contradictory_validity = successful.to_dict()["pose_validity"]
    assert isinstance(contradictory_validity, dict)
    contradictory_validity["valid"] = not contradictory_validity["valid"]
    with pytest.raises(DockingPipelineError, match="pose validity is contradictory"):
        replace(successful, pose_validity=contradictory_validity)
    with pytest.raises(DockingPipelineError, match="exact lowercase SHA-256"):
        replace(successful, search_row_sha256=successful.search_row_sha256.upper())
    with pytest.raises(DockingPipelineError, match="cannot fabricate success evidence"):
        replace(
            successful,
            status="failure",
            result_proposal_fingerprint_sha256="",
            error_code="synthetic_failure",
        )

    top = result.top_proposal_indices
    assert top
    with pytest.raises(DockingPipelineError, match="Top-K evidence is invalid"):
        replace(result, top_proposal_indices=(top[0], top[0]))
    with pytest.raises(DockingPipelineError, match="Top-K evidence is invalid"):
        replace(result, top_proposal_indices=(len(result.candidates),))
    with pytest.raises(DockingPipelineError, match="exact stable eligible ranking"):
        replace(result, top_proposal_indices=top[:-1])
    with pytest.raises(DockingPipelineError, match="exact stable eligible ranking"):
        replace(result, top_proposal_indices=tuple(reversed(top)))
    with pytest.raises(DockingPipelineError, match="required claim blocker"):
        replace(result, blockers=EXTERNAL_AUTHORITY_BLOCKERS)
    with pytest.raises(DockingPipelineError, match="construction proof mismatch"):
        replace(result, pipeline_source_sha256="e" * 64)
    unverified_plan = result.to_dict()["proposal_plan"]
    assert isinstance(unverified_plan, dict)
    unverified_plan.pop("receipt_sha256")
    unverified_plan["component_id"] = "UNVERIFIED"
    unverified_plan_receipt = hashlib.sha256(
        json.dumps(
            unverified_plan,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    unverified_plan["receipt_sha256"] = unverified_plan_receipt
    with pytest.raises(DockingPipelineError, match="construction proof mismatch"):
        replace(
            result,
            component_binding_mode=UNVERIFIED_COMPONENT_BINDING,
            scorer_source_sha256=None,
            refiner_source_sha256=None,
            component_ids={role: "UNVERIFIED" for role in result.component_ids},
            proposal_plan=unverified_plan,
            proposal_plan_receipt_sha256=unverified_plan_receipt,
            blockers=(
                *result.blockers,
                UNVERIFIED_COMPONENT_BLOCKER,
                UNVERIFIED_SIDE_EFFECT_BLOCKER,
            ),
        )
    result_constructor_fields = {
        item.name: getattr(result, item.name)
        for item in fields(result)
        if item.init and item.name != "_construction_proof_sha256"
    }
    with pytest.raises(DockingPipelineError, match="construction proof"):
        DockingPipelineResultV1(**result_constructor_fields)

    result_receipt_sha256 = result.receipt_sha256
    document = result.to_dict()
    assert document["construction_proof_scope"] == (
        "process_local_not_serialized_not_cryptographic_attestation"
    )
    assert not any("proof_sha256" in key for key in document)
    document["candidate_evidence"][0]["candidate_id"] = "tampered-copy"
    assert result.receipt_sha256 == result_receipt_sha256
    with pytest.raises(TypeError):
        result.component_ids["scorer"] = "tampered"  # type: ignore[index]


def test_dependency_injection_is_unverified_and_recorder_is_sealed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(DockingPipelineError, match="internal test-only latch"):
        DockingPipeline(input_preparer=CanonicalPreparedInputPreparer())

    injected = DockingPipeline._internal_test_only_with_unverified_components(
        input_preparer=CanonicalPreparedInputPreparer(),
    ).run(_request())
    document = injected.to_dict()

    assert injected.component_binding_mode == UNVERIFIED_COMPONENT_BINDING
    assert UNVERIFIED_COMPONENT_BLOCKER in injected.blockers
    assert UNVERIFIED_SIDE_EFFECT_BLOCKER in injected.blockers
    assert document["canonical_components_sealed"] is False
    assert document["arbitrary_dependency_injection_used"] is True
    assert document["network_fetch_performed"] is None
    assert document["external_reservation_requested"] is None
    assert document["side_effect_evidence_status"] == (
        "unknown_for_unverified_internal_components"
    )
    assert document["scorer_source_sha256"] is None
    assert document["refiner_source_sha256"] is None
    assert set(document["component_ids"].values()) == {"UNVERIFIED"}
    assert document["proposal_plan"]["component_id"] == "UNVERIFIED"
    assert document["product_execution_authorized"] is False

    assert "CanonicalPipelineEvidenceRecorder" not in pipeline_module.__all__
    assert "EvidenceRecorder" not in pipeline_module.__all__
    import betelgeuze_engine_v2 as engine_module
    import betelgeuze_engine_v2.docking as docking_module

    assert not hasattr(engine_module, "CanonicalPipelineEvidenceRecorder")
    assert not hasattr(engine_module, "EvidenceRecorder")
    assert not hasattr(docking_module, "CanonicalPipelineEvidenceRecorder")
    assert not hasattr(docking_module, "EvidenceRecorder")
    with pytest.raises(TypeError, match="unexpected keyword"):
        DockingPipeline(evidence_recorder=object())  # type: ignore[call-arg]

    def invalid_record_result(
        self: object,
        **kwargs: object,
    ) -> object:
        return object()

    monkeypatch.setattr(
        pipeline_module._CanonicalPipelineEvidenceRecorder,
        "_record",
        invalid_record_result,
    )
    with pytest.raises(TypeError, match="return exact DockingPipelineResultV1"):
        DockingPipeline().run(_request())


def test_internal_recorder_capability_blocks_direct_replay_and_crosswire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder_type = pipeline_module._CanonicalPipelineEvidenceRecorder
    original_record = recorder_type._record
    parameters = inspect.signature(original_record).parameters
    for caller_supplied_name in (
        "pipeline_source_sha256",
        "scorer_source_sha256",
        "refiner_source_sha256",
        "component_ids",
        "component_binding_mode",
    ):
        assert caller_supplied_name not in parameters

    captured: list[tuple[object, dict[str, object]]] = []

    def capture_record(self: object, **kwargs: object) -> object:
        captured.append((self, dict(kwargs)))
        return original_record(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(recorder_type, "_record", capture_record)
    first = DockingPipeline().run(_request())
    assert len(captured) == 1
    recorder, issued_kwargs = captured[0]
    document = first.to_dict()
    assert document["evidence_record_capability_consumed"] is True
    assert document["evidence_record_capability_scope"] == (
        "one_run_process_local_not_serialized_not_cryptographic_attestation"
    )
    assert all("nonce" not in key for key in document)

    with pytest.raises(DockingPipelineError, match="was consumed"):
        original_record(recorder, **issued_kwargs)  # type: ignore[arg-type]

    fake_kwargs = dict(issued_kwargs)
    fake_kwargs["capability"] = object()
    with pytest.raises(DockingPipelineError, match="exact one-shot"):
        original_record(recorder_type(), **fake_kwargs)

    with pytest.raises(TypeError, match="unexpected keyword"):
        original_record(
            recorder_type(),
            **fake_kwargs,
            pipeline_source_sha256="e" * 64,
        )

    foreign_raw_result = issued_kwargs["result"]
    crosswire_capture: dict[str, object] = {}

    def crosswire_record(self: object, **kwargs: object) -> object:
        correct = dict(kwargs)
        crosswired = dict(kwargs)
        crosswired["result"] = foreign_raw_result
        crosswire_capture["recorder"] = self
        crosswire_capture["correct"] = correct
        return original_record(self, **crosswired)  # type: ignore[arg-type]

    monkeypatch.setattr(recorder_type, "_record", crosswire_record)
    with pytest.raises(DockingPipelineError, match="object identity is cross-wired"):
        DockingPipeline().run(_request())

    consumed_recorder = crosswire_capture["recorder"]
    consumed_kwargs = crosswire_capture["correct"]
    assert isinstance(consumed_kwargs, dict)
    with pytest.raises(DockingPipelineError, match="was consumed"):
        original_record(
            consumed_recorder,
            **consumed_kwargs,
        )  # type: ignore[arg-type]


def test_actual_fixed64_preserves_failures_and_is_repeatable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_score_batch = ChemistryPoseScorerV1.score_batch
    original_record = pipeline_module._CanonicalPipelineEvidenceRecorder._record
    captured_core_results: list[object] = []

    def deterministic_failure_batch(
        self: ChemistryPoseScorerV1,
        proposals: object,
    ) -> tuple[DockingBatchScoreOutcome, ...]:
        rows = tuple(proposals)  # type: ignore[arg-type]
        outcomes = list(original_score_batch(self, rows))
        for index, proposal in enumerate(rows):
            if proposal.proposal_index % 11 == 0:
                outcomes[index] = DockingBatchScoreOutcome(
                    score=None,
                    error=ScorerV1Error("synthetic fixed64 failure fixture"),
                )
        return tuple(outcomes)

    monkeypatch.setattr(
        ChemistryPoseScorerV1,
        "score_batch",
        deterministic_failure_batch,
    )

    def capture_core_result(
        self: object,
        **kwargs: object,
    ) -> object:
        captured_core_results.append(kwargs["result"])
        return original_record(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        pipeline_module._CanonicalPipelineEvidenceRecorder,
        "_record",
        capture_core_result,
    )
    pipeline = DockingPipeline()
    first = pipeline.run(_request())
    second = pipeline.run(_request())

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(captured_core_results) == 2
    for pipeline_result, core_result in zip(
        (first, second),
        captured_core_results,
        strict=True,
    ):
        assert pipeline_result.scorer_v1_result_receipt_sha256 == (
            core_result.receipt_sha256  # type: ignore[attr-defined]
        )
        core_search = (
            core_result.guided_search_result.authenticated_search_result.search_result  # type: ignore[attr-defined]
        )
        assert pipeline_result.top_proposal_indices == tuple(
            row.proposal_index for row in core_search.top_rows
        )
        for retained, source, terms in zip(
            pipeline_result.candidates,
            core_search.rows,
            core_result.rows,  # type: ignore[attr-defined]
            strict=True,
        ):
            assert retained.candidate_id == source.candidate_id
            assert retained.status == source.status
            assert retained.selection_eligible is source.selection_eligible
            assert retained.scorer_terms == (
                None if terms.terms is None else terms.terms.to_dict()
            )
    assert len(first.candidates) == 64
    assert first.success_count + first.failure_count == 64
    assert first.failure_count == 6
    assert tuple(row.proposal_index for row in first.candidates) == tuple(range(64))
    assert len({row.candidate_id for row in first.candidates}) == 64
    assert len({row.receipt_sha256 for row in first.candidates}) == 64
    assert first.to_dict()["budget"]["candidate_count"] == 64
    assert first.to_dict()["proposal_plan"]["budget"] == first.to_dict()["budget"]
    assert first.to_dict()["proposal_plan"]["budget_sha256"] == first.to_dict()[
        "budget_sha256"
    ]
    assert all(code in first.blockers for code in PIPELINE_CLAIM_BLOCKERS)
    assert first.to_dict()["historical_execution_authorized"] is False
    assert first.to_dict()["fresh_holdout_execution_authorized"] is False
    assert first.to_dict()["stage0_admission_authority"] is False
    assert first.to_dict()["product_execution_authorized"] is False
    assert first.to_dict()["customer_pose_emission_authorized"] is False
    assert first.to_dict()["public_or_scientific_claim_authorized"] is False

    failed_index = next(
        row.proposal_index for row in first.candidates if row.status == "failure"
    )
    with pytest.raises(DockingPipelineError, match="successful eligible"):
        replace(first, top_proposal_indices=(failed_index,))

    for row in first.candidates:
        if row.status == "failure":
            assert row.score_binary64_hex is None
            assert row.scorer_terms is None
            assert row.pose_validity is None
            assert row.refinement_receipt is not None
            assert row.selection_eligible is False
            assert row.error_code
        else:
            assert row.scorer_terms is not None
            assert row.refinement_receipt is not None
            assert row.score_binary64_hex == row.scorer_terms[
                "total_score_binary64_hex"
            ]
            assert row.result_proposal_fingerprint_sha256 == row.scorer_terms[
                "proposal_fingerprint_sha256"
            ]
            assert row.source_proposal_fingerprint_sha256 == row.refinement_receipt[
                "source_proposal_sha256"
            ]

    expected_top = tuple(
        row.proposal_index
        for row in sorted(
            (
                row
                for row in first.candidates
                if row.status == "success" and row.selection_eligible
            ),
            key=lambda row: (
                float.fromhex(str(row.score_binary64_hex)),
                row.proposal_index,
                row.candidate_id,
            ),
        )[:5]
    )
    assert first.top_proposal_indices == expected_top


def test_pipeline_rejects_arbitrary_input_before_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ligand = _ligand()
    atoms = list(ligand.atoms)
    atoms[0] = replace(atoms[0], partial_charge_e=None)
    incomplete = replace(ligand, atoms=tuple(atoms))

    def forbidden_score(*args: object, **kwargs: object) -> object:
        raise AssertionError("scoring must not run for an unadmitted input")

    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", forbidden_score)
    base: dict[str, object] = {
        "receptor_system": _receptor(),
        "ligand_system": _ligand(),
        "pocket": _pocket(),
        "seed": 4301,
        "synthetic_only_acknowledgment": SYNTHETIC_ONLY_ACKNOWLEDGMENT,
        "fixture_admission": repository_synthetic_d0_fixture_admission(),
        "profile": DockingPipelineProfileV1(),
    }
    mutations = (
        {"receptor_system": replace(_receptor(), system_id="unadmitted-receptor")},
        {"ligand_system": incomplete},
        {"pocket": replace(_pocket(), radius_angstrom=9.0)},
        {"seed": 4302},
        {
            "profile": DockingPipelineProfileV1.synthetic_test(
                candidate_count=2,
                top_k=1,
                max_torsions=1,
                max_refinement_steps=1,
            )
        },
    )
    for mutation in mutations:
        with pytest.raises(DockingPipelineError, match="exact repository-owned"):
            DockingPipelineRequestV1(**{**base, **mutation})

    request = _request()
    object.__setattr__(request, "seed", 4302)
    with pytest.raises(DockingPipelineError, match="exact repository-owned"):
        DockingPipeline().run(request)


def test_pipeline_cannot_be_used_as_production_authority() -> None:
    admission = repository_synthetic_d0_fixture_admission()

    with pytest.raises(TypeError, match="fixture_admission"):
        DockingPipelineRequestV1(
            receptor_system=_receptor(),
            ligand_system=_ligand(),
            pocket=_pocket(),
            seed=4301,
            synthetic_only_acknowledgment=SYNTHETIC_ONLY_ACKNOWLEDGMENT,
        )

    with pytest.raises(DockingPipelineError, match="remains test-only"):
        DockingPipelineRequestV1(
            receptor_system=_receptor(),
            ligand_system=_ligand(),
            pocket=_pocket(),
            seed=4301,
            synthetic_only_acknowledgment=SYNTHETIC_ONLY_ACKNOWLEDGMENT,
            fixture_admission=admission,
            test_only=False,
        )

    with pytest.raises(DockingPipelineError, match="synthetic-only acknowledgment"):
        DockingPipelineRequestV1(
            receptor_system=_receptor(),
            ligand_system=_ligand(),
            pocket=_pocket(),
            seed=4301,
            synthetic_only_acknowledgment="",
            fixture_admission=admission,
        )
