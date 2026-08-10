from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.docking.geometric_admission_v2 import GeometricAdmissionV2
from betelgeuze_engine_v2.docking.mixed64_allocation import (
    RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_RANKS,
    Mixed64AtomicFeatureEvidence,
    Mixed64ConformerSourceEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    V7_CONTROL_SOURCE_INDICES,
    build_fixed_mixed64_allocation,
)
from betelgeuze_engine_v2.docking.pipeline_candidate_evidence_v2 import (
    PipelineCandidateRecordV2,
    bind_pose_validity_receipt_v2,
    bind_proposal_execution_receipt_v2,
    bind_refinement_receipt_v2,
    bind_scorer_v1_evidence_v2,
    build_pipeline_candidate_evidence_v2,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
from betelgeuze_engine_v2.docking.validity import PoseValidityResult


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tools" / "verify_engine_v2_mixed64_candidate_evidence_artifact.py"


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _receipt(document: dict[str, object]) -> dict[str, object]:
    result = dict(document)
    result["receipt_sha256"] = hashlib.sha256(_canonical(document)[:-1]).hexdigest()
    return result


def _coordinate_digest(x: float) -> str:
    return hashlib.sha256(
        json.dumps(
            [[float(x).hex(), 0.0.hex(), 0.0.hex()]],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _features(*, slot_zero_coordinate: float = 5.0) -> Mixed64FeatureEvidence:
    rows = tuple(
        sorted(
            (
                ("ligand_acceptor", (2,)),
                ("ligand_aromatic_plane", (5, 6, 7)),
                ("ligand_donor", (0, 1)),
                ("ligand_positive_site", (3,)),
                ("ligand_shape_axis", (0, 2, 3)),
                ("pocket_shape_axis", (20, 21, 22)),
                ("receptor_acceptor", (12,)),
                ("receptor_aromatic_plane", (15, 16, 17)),
                ("receptor_donor", (10, 11)),
                ("receptor_negative_site", (13,)),
            )
        )
    )
    return Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=_digest("v11-source"),
        prepared_ligand_topology_sha256=_digest("ligand-topology"),
        prepared_receptor_topology_sha256=_digest("receptor-topology"),
        feature_extractor_policy_sha256=_digest("feature-policy"),
        atomic_features=tuple(
            Mixed64AtomicFeatureEvidence(
                kind=kind,
                atom_indices=indices,
                source_receipt_sha256=_digest(f"feature-source-{kind}"),
                geometry_receipt_sha256=_digest(f"feature-geometry-{kind}"),
            )
            for kind, indices in rows
        ),
        v7_control_sources=tuple(
            Mixed64V7ControlSourceEvidence(
                source_index=index,
                proposal_mode=(
                    "pocket_centered_control"
                    if index < 8
                    else "uniform_source_control"
                ),
                proposal_sha256=_digest(f"v7-control-proposal-{index}"),
                coordinate_sha256=_coordinate_digest(
                    slot_zero_coordinate if index == 0 else 5.0 + index / 10.0
                ),
                proposal_lineage_sha256=_digest(f"v7-control-lineage-{index}"),
                source_receipt_sha256=_digest(f"v7-control-source-{index}"),
            )
            for index in V7_CONTROL_SOURCE_INDICES
        ),
        conformer_sources=tuple(
            Mixed64ConformerSourceEvidence(
                rank=rank,
                proposal_sha256=_digest(f"conformer-proposal-{rank}"),
                coordinate_sha256=_digest(f"conformer-coordinate-{rank}"),
                source_receipt_sha256=_digest(f"conformer-source-{rank}"),
            )
            for rank in TRUE_CONFORMER_RANKS
        ),
        retained_sources=tuple(
            Mixed64RetainedSourceEvidence(
                source_index=index,
                proposal_sha256=_digest(f"retained-proposal-{index}"),
                coordinate_sha256=_coordinate_digest(11.0 + position / 10.0),
                source_receipt_sha256=_digest(f"retained-source-{index}"),
            )
            for position, index in enumerate(RETAINED_SOURCE_INDICES)
        ),
    )


def _validity(result_sha: str, coordinate_sha: str, *, valid: bool):
    checks = {
        "proper_rotation": valid,
        "bond_lengths_preserved": True,
        "ligand_self_clash_free": True,
        "receptor_ligand_clash_free": True,
        "declared_chirality_preserved": True,
        "inside_declared_pocket": True,
        "element_vdw_ligand_overlap_free": True,
        "element_vdw_receptor_overlap_free": True,
    }
    return bind_pose_validity_receipt_v2(
        result_proposal_sha256=result_sha,
        coordinate_sha256=coordinate_sha,
        validity_context_fingerprint_sha256=_digest("validity-context"),
        validity_config_fingerprint_sha256=_digest("validity-config"),
        evaluator_implementation_source_sha256=_digest("validity-source"),
        result=PoseValidityResult(
            checks=checks,
            evaluated_checks={name: True for name in checks},
            complete=True,
            valid_within_evaluated_scope=valid,
            measurements={"synthetic_measurement": 1.0},
            blockers=() if valid else ("synthetic_pose_invalid",),
            not_evaluated_reasons={},
        ),
    )


def _record(slot_index: int, slot, source_coordinate_sha: str) -> PipelineCandidateRecordV2:
    source_sha = (
        slot.selected_generation_parent_proposal_sha256
        if slot.generation_parent_role == "exact_passthrough_parent"
        else _digest(f"source-{slot_index}")
    )
    result_sha = _digest(f"result-{slot_index}")
    result_coordinate_sha = _digest(f"result-coordinate-{slot_index}")
    score = float(slot_index)
    terms = ScorerV1Terms(
        proposal_fingerprint_sha256=result_sha,
        authority_input_receipt_sha256=_digest("authority"),
        context_fingerprint_sha256=_digest("context"),
        config_fingerprint_sha256=_digest("config"),
        backend_receipt_sha256=_digest("backend"),
        typed_vdw=score,
        electrostatics=0.0,
        directional_hbond=0.0,
        hydrophobic_contact=0.0,
        desolvation_proxy=0.0,
        torsion_energy=0.0,
        ligand_strain=0.0,
        weak_pocket_prior=0.0,
        total_score=score,
        receptor_candidate_pair_count=1,
        ligand_pair_count=0,
        hbond_count=0,
        hydrophobic_contact_count=0,
        buried_polar_count=0,
    )
    config_sha = _digest("refiner-config")
    return PipelineCandidateRecordV2(
        slot_index=slot_index,
        source_proposal_sha256=source_sha,
        result_proposal_sha256=result_sha,
        proposal_execution_receipt=bind_proposal_execution_receipt_v2(
            slot_index=slot_index,
            allocation_slot_receipt_sha256=slot.receipt_sha256,
            allocation_source_receipt_sha256s=slot.selected_source_receipt_sha256s,
            generation_parent_proposal_sha256=(
                slot.selected_generation_parent_proposal_sha256
            ),
            generation_parent_coordinate_sha256=(
                slot.selected_generation_parent_coordinate_sha256
            ),
            source_proposal_sha256=source_sha,
            source_coordinate_sha256=source_coordinate_sha,
            generation_input_receipt_sha256=_digest("v11-source"),
            generator_config_sha256=_digest("generator-config"),
            generator_implementation_source_sha256=_digest("generator-source"),
            generator_component_id="betelgeuze.engine_v2_fixed64_generator/1.0.0",
        ),
        refinement_receipt=bind_refinement_receipt_v2(
            source_proposal_sha256=source_sha,
            result_proposal_sha256=result_sha,
            source_coordinate_sha256=source_coordinate_sha,
            result_coordinate_sha256=result_coordinate_sha,
            refiner_config_sha256=config_sha,
            refiner_implementation_source_sha256=_digest("refiner-source"),
            source_receipt=_receipt(
                {
                    "schema_id": "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0",
                    "source_proposal_sha256": source_sha,
                    "config_sha256": config_sha,
                    "pre_coordinates_sha256": source_coordinate_sha,
                    "post_coordinates_sha256": result_coordinate_sha,
                    "accepted_steps": 0,
                    "scientifically_validated": False,
                }
            ),
        ),
        scorer_evidence=bind_scorer_v1_evidence_v2(
            terms=terms,
            search_row_sha256=_digest(f"search-row-{slot_index}"),
            search_term_row_receipt_sha256=_digest(f"term-row-{slot_index}"),
            source_search_result_receipt_sha256=_digest("search-result"),
            scorer_implementation_source_sha256=_digest("scorer-source"),
        ),
        pose_validity_receipt=_validity(
            result_sha,
            result_coordinate_sha,
            valid=slot_index != 0,
        ),
    )


def _proposal_only_record(
    slot_index: int,
    slot,
    source_coordinate_sha: str,
    *,
    refinement_failure: bool,
) -> PipelineCandidateRecordV2:
    source_sha = (
        slot.selected_generation_parent_proposal_sha256
        if slot.generation_parent_role == "exact_passthrough_parent"
        else _digest(f"source-{slot_index}")
    )
    return PipelineCandidateRecordV2(
        slot_index=slot_index,
        source_proposal_sha256=source_sha,
        proposal_execution_receipt=bind_proposal_execution_receipt_v2(
            slot_index=slot_index,
            allocation_slot_receipt_sha256=slot.receipt_sha256,
            allocation_source_receipt_sha256s=slot.selected_source_receipt_sha256s,
            generation_parent_proposal_sha256=(
                slot.selected_generation_parent_proposal_sha256
            ),
            generation_parent_coordinate_sha256=(
                slot.selected_generation_parent_coordinate_sha256
            ),
            source_proposal_sha256=source_sha,
            source_coordinate_sha256=source_coordinate_sha,
            generation_input_receipt_sha256=_digest("v11-source"),
            generator_config_sha256=_digest("generator-config"),
            generator_implementation_source_sha256=_digest("generator-source"),
            generator_component_id="betelgeuze.engine_v2_fixed64_generator/1.0.0",
        ),
        execution_failure_stage="refinement" if refinement_failure else None,
        execution_failure_code=(
            "typed_refinement_synthetic_failure" if refinement_failure else None
        ),
    )


@pytest.fixture(scope="module")
def artifact_document() -> dict[str, object]:
    allocation = build_fixed_mixed64_allocation(_features())
    geometric = GeometricAdmissionV2().admit_fixed64(
        tuple((((5.0 + slot.slot_index / 10.0), 0.0, 0.0),) for slot in allocation.slots),
        allocation=allocation,
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=100.0,
    )
    records = tuple(
        _record(
            slot_index,
            allocation.slots[slot_index],
            str(geometric.decisions[slot_index].candidate_coordinate_sha256),
        )
        for slot_index in range(64)
    )
    return build_pipeline_candidate_evidence_v2(
        allocation,
        geometric,
        records,
    ).to_dict()


@pytest.fixture(scope="module")
def partial_failure_artifact_document() -> dict[str, object]:
    allocation = build_fixed_mixed64_allocation(_features(slot_zero_coordinate=0.0))
    geometric = GeometricAdmissionV2().admit_fixed64(
        tuple(
            (
                ((0.0, 0.0, 0.0),)
                if slot.slot_index == 0
                else (((5.0 + slot.slot_index / 10.0), 0.0, 0.0),)
            )
            for slot in allocation.slots
        ),
        allocation=allocation,
        ligand_vdw_radii=(1.0,),
        ligand_heavy_atom_mask=(True,),
        receptor_coordinates=((0.0, 0.0, 0.0),),
        receptor_vdw_radii=(1.0,),
        pocket_center=(0.0, 0.0, 0.0),
        pocket_radius=100.0,
    )
    complete = tuple(
        _record(
            slot_index,
            allocation.slots[slot_index],
            str(geometric.decisions[slot_index].candidate_coordinate_sha256),
        )
        for slot_index in range(1, 64)
    )
    records = (
        _proposal_only_record(
            0,
            allocation.slots[0],
            str(geometric.decisions[0].candidate_coordinate_sha256),
            refinement_failure=False,
        ),
        _proposal_only_record(
            1,
            allocation.slots[1],
            str(geometric.decisions[1].candidate_coordinate_sha256),
            refinement_failure=True,
        ),
        replace(
            complete[1],
            scorer_evidence=None,
            pose_validity_receipt=None,
            execution_failure_stage="scoring",
            execution_failure_code="typed_scorer_synthetic_failure",
        ),
        replace(
            complete[2],
            pose_validity_receipt=None,
            execution_failure_stage="validity",
            execution_failure_code="typed_validity_synthetic_failure",
        ),
        *complete[3:],
    )
    return build_pipeline_candidate_evidence_v2(
        allocation,
        geometric,
        records,
    ).to_dict()


def _invoke(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _reseal(document: dict[str, object]) -> None:
    document.pop("receipt_sha256", None)
    document["receipt_sha256"] = hashlib.sha256(_canonical(document)[:-1]).hexdigest()


def _reseal_candidate_and_root(document: dict[str, object], slot_index: int) -> None:
    candidate = document["candidates"][slot_index]
    _reseal(candidate)
    document["candidate_receipt_sha256s"][slot_index] = candidate["receipt_sha256"]
    _reseal(document)


def _tamper_resealed_rank(document: dict[str, object]) -> None:
    document["candidates"][0]["stable_rank"] = 2
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_term(document: dict[str, object]) -> None:
    candidate = document["candidates"][0]
    scorer = candidate["scorer_v1_evidence"]
    terms = scorer["scorer_v1_terms"]
    terms["typed_vdw_binary64_hex"] = (1.0).hex()
    _reseal(terms)
    scorer["scorer_v1_terms_receipt_sha256"] = terms["receipt_sha256"]
    _reseal(scorer)
    candidate["scorer_v1_evidence_binding_sha256"] = scorer["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_exact_input(document: dict[str, object]) -> None:
    geometric = document["geometric_admission_batch"]
    exact_inputs = geometric["exact_inputs"]
    exact_inputs["candidate_coordinates_binary64_hex"][0][0][0] = (6.0).hex()
    _reseal(exact_inputs)
    geometric["exact_input_binding_sha256"] = exact_inputs["receipt_sha256"]
    _reseal(geometric)
    document["geometric_admission_batch_receipt_sha256"] = geometric["receipt_sha256"]
    for slot_index, candidate in enumerate(document["candidates"]):
        candidate["geometric_admission_batch_receipt_sha256"] = geometric[
            "receipt_sha256"
        ]
        _reseal(candidate)
        document["candidate_receipt_sha256s"][slot_index] = candidate["receipt_sha256"]
    _reseal(document)


def _tamper_resealed_generator_component(document: dict[str, object]) -> None:
    candidate = document["candidates"][0]
    proposal = candidate["proposal_execution_receipt"]
    proposal["generator_component_id"] = "betelgeuze.synthetic_other_generator/1.0.0"
    _reseal(proposal)
    candidate["proposal_execution_receipt_sha256"] = proposal["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_generation_parent(document: dict[str, object]) -> None:
    candidate = document["candidates"][0]
    proposal = candidate["proposal_execution_receipt"]
    proposal["generation_parent_proposal_sha256"] = _digest(
        "wrong-generation-parent-proposal"
    )
    proposal["generation_parent_coordinate_sha256"] = _digest(
        "wrong-generation-parent-coordinate"
    )
    _reseal(proposal)
    candidate["proposal_execution_receipt_sha256"] = proposal["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_activation_blocker(document: dict[str, object]) -> None:
    document["activation_evidence_blockers"][0] = "fabricated_activation_ready"
    _reseal(document)


def _tamper_resealed_denominator_scope(document: dict[str, object]) -> None:
    document["denominator_failure_completeness_scope"] = "end_to_end_all_stages"
    _reseal(document)


def _tamper_resealed_nested_profile_authority(document: dict[str, object]) -> None:
    candidate = document["candidates"][0]
    refinement = candidate["refinement_receipt"]
    source_receipt = refinement["source_receipt"]
    source_receipt["profile_promotion_authority"] = True
    _reseal(source_receipt)
    _reseal(refinement)
    candidate["refinement_receipt_binding_sha256"] = refinement["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_nested_authority_granted(document: dict[str, object]) -> None:
    candidate = document["candidates"][0]
    refinement = candidate["refinement_receipt"]
    source_receipt = refinement["source_receipt"]
    source_receipt["authority_granted"] = True
    _reseal(source_receipt)
    _reseal(refinement)
    candidate["refinement_receipt_binding_sha256"] = refinement["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _reseal_refinement_identity(
    document: dict[str, object],
    *,
    refiner_config_sha256: str | None = None,
    refiner_implementation_source_sha256: str | None = None,
    refinement_source_schema_id: str | None = None,
) -> None:
    candidate = document["candidates"][0]
    refinement = candidate["refinement_receipt"]
    source_receipt = refinement["source_receipt"]
    if refiner_config_sha256 is not None:
        refinement["refiner_config_sha256"] = refiner_config_sha256
        source_receipt["config_sha256"] = refiner_config_sha256
    if refiner_implementation_source_sha256 is not None:
        refinement["refiner_implementation_source_sha256"] = (
            refiner_implementation_source_sha256
        )
    if refinement_source_schema_id is not None:
        source_receipt["source_receipt_schema_id"] = refinement_source_schema_id
    if refiner_config_sha256 is not None or refinement_source_schema_id is not None:
        _reseal(source_receipt)
    _reseal(refinement)
    candidate["refinement_receipt_binding_sha256"] = refinement["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_refiner_config(document: dict[str, object]) -> None:
    _reseal_refinement_identity(
        document,
        refiner_config_sha256=_digest("other-refiner-config"),
    )


def _tamper_resealed_refiner_implementation(document: dict[str, object]) -> None:
    _reseal_refinement_identity(
        document,
        refiner_implementation_source_sha256=_digest("other-refiner-source"),
    )


def _tamper_resealed_refinement_schema(document: dict[str, object]) -> None:
    _reseal_refinement_identity(
        document,
        refinement_source_schema_id=(
            "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
        ),
    )


def _tamper_resealed_invalid_pose_without_blocker(
    document: dict[str, object],
) -> None:
    candidate = document["candidates"][0]
    validity = candidate["pose_validity_receipt"]
    validity["pose_validity"]["blockers"] = []
    _reseal(validity)
    candidate["pose_validity_receipt_sha256"] = validity["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_valid_pose_with_blocker(document: dict[str, object]) -> None:
    candidate = document["candidates"][1]
    validity = candidate["pose_validity_receipt"]
    validity["pose_validity"]["blockers"] = ["fabricated_blocker"]
    _reseal(validity)
    candidate["pose_validity_receipt_sha256"] = validity["receipt_sha256"]
    _reseal_candidate_and_root(document, 1)


def _tamper_resealed_nonstring_validity_blocker(
    document: dict[str, object],
) -> None:
    candidate = document["candidates"][0]
    validity = candidate["pose_validity_receipt"]
    validity["pose_validity"]["blockers"] = [{}]
    _reseal(validity)
    candidate["pose_validity_receipt_sha256"] = validity["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_oversized_validity_measurement(
    document: dict[str, object],
) -> None:
    candidate = document["candidates"][0]
    validity = candidate["pose_validity_receipt"]
    validity["pose_validity"]["measurements"]["too_large"] = 2.0e15
    _reseal(validity)
    candidate["pose_validity_receipt_sha256"] = validity["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_oversized_scorer_count(document: dict[str, object]) -> None:
    candidate = document["candidates"][0]
    scorer = candidate["scorer_v1_evidence"]
    terms = scorer["scorer_v1_terms"]
    terms["receptor_candidate_pair_count"] = 16_777_217
    _reseal(terms)
    scorer["scorer_v1_terms_receipt_sha256"] = terms["receipt_sha256"]
    _reseal(scorer)
    candidate["scorer_v1_evidence_binding_sha256"] = scorer["receipt_sha256"]
    _reseal_candidate_and_root(document, 0)


def _tamper_resealed_noncanonical_failure_code(document: dict[str, object]) -> None:
    candidate = document["candidates"][1]
    candidate["execution_failure_code"] = "typed_refinement_BAD"
    candidate["typed_failure_codes"] = ["typed_refinement_BAD"]
    _reseal_candidate_and_root(document, 1)


def test_fresh_process_replays_complete_persisted_artifact(
    tmp_path: Path,
    artifact_document: dict[str, object],
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_bytes(_canonical(artifact_document))

    completed = _invoke(artifact)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["verified"] is True
    assert result["candidate_denominator"] == 64
    assert result["full_cartesian_geometric_replay"] is True
    assert result["primary_and_valid_rankings_rederived"] is True
    assert result["authority_granted"] is False
    assert result["verification_blockers"] == []
    assert result["activation_evidence_eligible"] is False
    assert result["activation_evidence_blockers"] == [
        "uniform_source_control_lineage_not_rederived",
        "independent_so3_base_source_not_bound",
        "independent_so3_orientation_receipt_not_implemented",
        "single_anchor_placement_receipt_not_implemented",
        "proposal_generation_failure_receipt_not_implemented",
        "post_refinement_geometric_admission_not_implemented",
        "source_parent_payload_rederivation_not_implemented",
        "producer_attestation_not_implemented",
        "score_term_reexecution_not_implemented",
        "pose_validity_reexecution_not_implemented",
    ]
    assert artifact_document["denominator_failure_completeness_scope"] == (
        "allocation_and_supported_post_proposal_structural_stages_only"
    )
    assert artifact_document["activation_evidence_eligible"] is False
    assert artifact_document["activation_evidence_blockers"] == [
        "uniform_source_control_lineage_not_rederived",
        "independent_so3_base_source_not_bound",
        "independent_so3_orientation_receipt_not_implemented",
        "single_anchor_placement_receipt_not_implemented",
        "proposal_generation_failure_receipt_not_implemented",
        "post_refinement_geometric_admission_not_implemented",
        "source_parent_payload_rederivation_not_implemented",
        "producer_attestation_not_implemented",
        "score_term_reexecution_not_implemented",
        "pose_validity_reexecution_not_implemented",
    ]


def test_fresh_process_replays_stage_specific_partial_failures(
    tmp_path: Path,
    partial_failure_artifact_document: dict[str, object],
) -> None:
    artifact = tmp_path / "partial-failures.json"
    artifact.write_bytes(_canonical(partial_failure_artifact_document))

    completed = _invoke(artifact)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["verified"] is True
    assert result["candidate_denominator"] == 64
    assert result["authority_granted"] is False
    assert result["verification_blockers"] == []
    assert result["activation_evidence_eligible"] is False


@pytest.mark.parametrize(
    ("name", "tamper"),
    (
        ("allocation", lambda value: value["allocation"]["slots"][0].__setitem__("lane", "tampered_lane")),
        (
            "exact_input",
            lambda value: value["geometric_admission_batch"]["exact_inputs"]["candidate_coordinates_binary64_hex"][0][0].__setitem__(0, (6.0).hex()),
        ),
        (
            "score_term",
            lambda value: value["candidates"][0]["scorer_v1_evidence"]["scorer_v1_terms"].__setitem__("typed_vdw_binary64_hex", (1.0).hex()),
        ),
        ("rank", lambda value: value["candidates"][0].__setitem__("stable_rank", 2)),
        ("authority", lambda value: value.__setitem__("molecular_execution_authorized", True)),
    ),
)
def test_adversarial_artifact_tampering_fails_closed(
    tmp_path: Path,
    artifact_document: dict[str, object],
    name: str,
    tamper,
) -> None:
    document = deepcopy(artifact_document)
    tamper(document)
    artifact = tmp_path / f"{name}.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert result["authority_granted"] is False
    assert result["verification_blockers"]
    assert result["activation_evidence_eligible"] is False


@pytest.mark.parametrize(
    "tamper",
    (_tamper_resealed_rank, _tamper_resealed_term, _tamper_resealed_exact_input),
)
def test_resealed_tampering_still_fails_independent_replay(
    tmp_path: Path,
    artifact_document: dict[str, object],
    tamper,
) -> None:
    document = deepcopy(artifact_document)
    tamper(document)
    artifact = tmp_path / f"resealed-{tamper.__name__}.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert result["authority_granted"] is False
    assert result["verification_blockers"]


@pytest.mark.parametrize(
    "tamper",
    (
        _tamper_resealed_generator_component,
        _tamper_resealed_refiner_config,
        _tamper_resealed_refiner_implementation,
        _tamper_resealed_refinement_schema,
    ),
)
def test_resealed_mixed_generator_and_refiner_identities_fail_replay(
    tmp_path: Path,
    artifact_document: dict[str, object],
    tamper,
) -> None:
    document = deepcopy(artifact_document)
    tamper(document)
    artifact = tmp_path / f"mixed-identity-{tamper.__name__}.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert result["authority_granted"] is False
    assert result["verification_blockers"] == [
        "$: batch producer/config/context identity is cross-wired"
    ]


@pytest.mark.parametrize(
    ("tamper", "expected_blocker"),
    (
        (
            _tamper_resealed_generation_parent,
            "proposal generation parent identity is cross-wired",
        ),
        (_tamper_resealed_activation_blocker, "activation blockers changed"),
        (
            _tamper_resealed_denominator_scope,
            "denominator_failure_completeness_scope",
        ),
        (
            _tamper_resealed_nested_profile_authority,
            "profile_promotion_authority",
        ),
        (
            _tamper_resealed_nested_authority_granted,
            "authority_granted",
        ),
    ),
)
def test_resealed_parent_and_activation_contract_tampering_fails_replay(
    tmp_path: Path,
    artifact_document: dict[str, object],
    tamper,
    expected_blocker: str,
) -> None:
    document = deepcopy(artifact_document)
    tamper(document)
    artifact = tmp_path / f"contract-{tamper.__name__}.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert expected_blocker in result["verification_blockers"][0]


@pytest.mark.parametrize(
    "tamper",
    (
        _tamper_resealed_invalid_pose_without_blocker,
        _tamper_resealed_valid_pose_with_blocker,
    ),
)
def test_resealed_validity_blocker_inconsistency_fails_replay(
    tmp_path: Path,
    artifact_document: dict[str, object],
    tamper,
) -> None:
    document = deepcopy(artifact_document)
    tamper(document)
    artifact = tmp_path / f"validity-blockers-{tamper.__name__}.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert "validity blockers disagree" in result["verification_blockers"][0]


def test_resealed_nonstring_validity_blocker_returns_fail_closed_json(
    tmp_path: Path,
    artifact_document: dict[str, object],
) -> None:
    document = deepcopy(artifact_document)
    _tamper_resealed_nonstring_validity_blocker(document)
    artifact = tmp_path / "nonstring-validity-blocker.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert "must be an exact non-empty string" in result["verification_blockers"][0]


@pytest.mark.parametrize(
    ("tamper", "expected_blocker"),
    (
        (
            _tamper_resealed_oversized_validity_measurement,
            "validity measurement is not a bounded finite number",
        ),
        (
            _tamper_resealed_oversized_scorer_count,
            "must be an integer in [0, 16777216]",
        ),
    ),
)
def test_resealed_verifier_envelope_violations_fail_replay(
    tmp_path: Path,
    artifact_document: dict[str, object],
    tamper,
    expected_blocker: str,
) -> None:
    document = deepcopy(artifact_document)
    tamper(document)
    artifact = tmp_path / f"bounded-{tamper.__name__}.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert expected_blocker in result["verification_blockers"][0]


def test_resealed_noncanonical_execution_failure_code_fails_replay(
    tmp_path: Path,
    partial_failure_artifact_document: dict[str, object],
) -> None:
    document = deepcopy(partial_failure_artifact_document)
    _tamper_resealed_noncanonical_failure_code(document)
    artifact = tmp_path / "noncanonical-failure-code.json"
    artifact.write_bytes(_canonical(document))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert (
        "failure code is not a canonical identifier"
        in result["verification_blockers"][0]
    )


def test_duplicate_json_keys_and_noncanonical_bytes_fail_closed(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"schema_id":"x","schema_id":"y"}\n')
    no_lf = tmp_path / "no-lf.json"
    no_lf.write_bytes(b'{"schema_id":"x"}')

    duplicate_result = _invoke(duplicate)
    no_lf_result = _invoke(no_lf)

    assert duplicate_result.returncode == 1
    assert "duplicate JSON key" in duplicate_result.stdout
    assert no_lf_result.returncode == 1
    assert "canonical one-line JSON plus LF" in no_lf_result.stdout


def test_oversized_artifact_fails_before_json_loading(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized-evidence.json"
    with oversized.open("wb") as handle:
        handle.truncate(64 * 1024 * 1024 + 1)

    completed = _invoke(oversized)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verification_blockers"] == [
        "artifact byte size is outside the fixed bound"
    ]


def test_json_integer_outside_exact_envelope_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "oversized-integer.json"
    artifact.write_bytes(b'{"value":9007199254740992}\n')

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verification_blockers"] == [
        "JSON integer exceeds bounded precision"
    ]


def test_very_long_json_integer_returns_fail_closed_json(tmp_path: Path) -> None:
    artifact = tmp_path / "very-long-integer.json"
    artifact.write_bytes(b'{"value":' + b"1" * 5_000 + b"}\n")

    completed = _invoke(artifact)

    assert completed.returncode == 1
    assert completed.stderr == ""
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert result["authority_granted"] is False
    assert result["verification_blockers"] == [
        "JSON integer exceeds bounded precision"
    ]


def test_nonregular_artifact_fails_without_unbounded_read(tmp_path: Path) -> None:
    completed = _invoke(tmp_path)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verification_blockers"] == [
        "artifact must be a regular file"
    ]


def test_oversized_mapping_key_fails_before_path_amplification(tmp_path: Path) -> None:
    artifact = tmp_path / "oversized-key.json"
    artifact.write_bytes(_canonical({"x" * 257: {"child": 1}}))

    completed = _invoke(artifact)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["verification_blockers"] == ["$: oversized JSON mapping key"]


@pytest.mark.parametrize(
    "raw",
    (b'{"\\ud800":0}\n', b'{"x":"\\ud800"}\n'),
)
def test_lone_surrogate_returns_fail_closed_json(
    tmp_path: Path,
    raw: bytes,
) -> None:
    artifact = tmp_path / "lone-surrogate.json"
    artifact.write_bytes(raw)

    completed = _invoke(artifact)

    assert completed.returncode == 1
    assert completed.stderr == ""
    result = json.loads(completed.stdout)
    assert result["verified"] is False
    assert result["authority_granted"] is False
    assert "non-Unicode-scalar string" in result["verification_blockers"][0]
