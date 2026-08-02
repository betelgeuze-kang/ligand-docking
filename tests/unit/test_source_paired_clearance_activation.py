from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import inspect
import json

import pytest


torch = pytest.importorskip("torch")

import betelgeuze_engine_v2.docking.torsion_contact_refinement as refinement_module  # noqa: E402
import betelgeuze_engine_v2.docking.guided_placement as guided_module  # noqa: E402

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingScope,
    GuidedPlacementReceipt,
    InteractionAwareRigidClearanceConfigV4,
    InteractionAwareRigidConfigV2,
    InteractionAwareRigidConfigV3,
    InteractionAwareTorsionContactConfigV7,
    InteractionAwareTorsionContactEnsembleRefinerV7,
    PocketDefinition,
    SourcePairedTorsionRescueAllocation,
    SourcePairedTorsionRescuePolicy,
    SourcePairedTorsionRescueProposalReceipt,
    TorsionContactRefinementError,
    build_element_aware_authenticated_known_pocket_docking_problem,
    generate_bounded_docking_proposals,
)
from betelgeuze_engine_v2.docking.source_paired_clearance_activation import (  # noqa: E402
    SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
    SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_ID,
    SourcePairedClearanceActivatedStateV1,
    SourcePairedClearanceActivationError,
    build_source_paired_clearance_activated_state_v1,
)


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="clearance-activation-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="clearance-activation-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "O": 8}[element],
                residue_index=0,
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.4, 0.0, 0.0],
                    [2.8, 0.3, 0.0],
                    [4.1, 1.0, 0.2],
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=_provenance("activation-ligand", "a" * 64),
    )


def _receptor(*, separated: bool = False) -> AllAtomSystem:
    receptor_coordinates = (
        [[10.0, 10.0, 10.0], [12.0, 12.0, 12.0]]
        if separated
        else [
            [1.2307712254983234, 3.9434758050512015, 1.6523553225866865],
            [8.0, 8.0, 8.0],
        ]
    )
    return AllAtomSystem(
        system_id="clearance-activation-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(2)
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([receptor_coordinates], dtype=torch.float64),
        provenance=_provenance("activation-receptor", "b" * 64),
    )


def _pocket() -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="clearance-activation-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=20.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )


def _fixture(
    *,
    permissive_selection_window: bool,
    rescue_pairs: tuple[tuple[int, int], ...] = ((1, 0),),
    return_all: bool = False,
):
    receptor = _receptor(separated=permissive_selection_window)
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    budget = DockingBudget(
        candidate_count=64,
        top_k=1,
        max_torsions=1,
        translation_radius_angstrom=0.0,
        seed=103,
    )
    proposals = generate_bounded_docking_proposals(
        authority.search_space,
        budget,
        problem=authority.problem,
    )
    policy = SourcePairedTorsionRescuePolicy()
    allocation = SourcePairedTorsionRescueAllocation(
        authenticated_input_receipt_sha256=authority.input_receipt_sha256,
        guidance_context_sha256="8" * 64,
        budget_sha256="9" * 64,
        rescue_policy_sha256=policy.fingerprint_sha256,
        base_guided_policy_sha256=policy.base_guided_policy.fingerprint_sha256,
        candidate_count=64,
        authority_rotor_count=int(
            torch.count_nonzero(authority.search_space.rotatable_mask).item()
        ),
        v3_target_parent_pairs=(),
        rescue_target_parent_pairs=rescue_pairs,
    )
    proposal_fingerprints = tuple(proposal.fingerprint_sha256 for proposal in proposals)
    baseline_modes = ["uniform_fallback"] * 64
    baseline_sources: list[int | None] = [None] * 64
    for target, parent in rescue_pairs:
        baseline_modes[target] = "uniform_v3_rigid_ensemble"
        baseline_sources[target] = parent
    baseline_receipt = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=authority.input_receipt_sha256,
        guidance_context_sha256="8" * 64,
        guided_policy_sha256=policy.base_guided_policy.fingerprint_sha256,
        budget_sha256="9" * 64,
        proposal_fingerprint_sha256s=proposal_fingerprints,
        proposal_modes=tuple(baseline_modes),
        ligand_anchor_atom_indices=((),) * 64,
        receptor_anchor_atom_indices=((),) * 64,
        requested_anchor_distance_angstroms=(None,) * 64,
        observed_anchor_distance_angstroms=(None,) * 64,
        feature_counts={},
        ensemble_source_proposal_indices=tuple(baseline_sources),
    )
    guided_modes = list(baseline_modes)
    guided_sources = list(baseline_sources)
    rescue_parents: list[int | None] = [None] * 64
    for target, parent in rescue_pairs:
        guided_modes[target] = "uniform_torsion_rescue_variant"
        guided_sources[target] = None
        rescue_parents[target] = parent
    guided_receipt = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=authority.input_receipt_sha256,
        guidance_context_sha256="8" * 64,
        guided_policy_sha256=policy.fingerprint_sha256,
        budget_sha256="9" * 64,
        proposal_fingerprint_sha256s=proposal_fingerprints,
        proposal_modes=tuple(guided_modes),
        ligand_anchor_atom_indices=((),) * 64,
        receptor_anchor_atom_indices=((),) * 64,
        requested_anchor_distance_angstroms=(None,) * 64,
        observed_anchor_distance_angstroms=(None,) * 64,
        feature_counts={},
        ensemble_source_proposal_indices=tuple(guided_sources),
        torsion_rescue_parent_proposal_indices=tuple(rescue_parents),
        source_paired_torsion_rescue_profile=True,
        baseline_guided_receipt_sha256=baseline_receipt.receipt_sha256,
        torsion_rescue_allocation_sha256=allocation.allocation_sha256,
    )
    proposal_receipt = SourcePairedTorsionRescueProposalReceipt(
        authenticated_input_receipt_sha256=authority.input_receipt_sha256,
        budget_sha256="9" * 64,
        source_ligand_system_sha256="a" * 64,
        source_ligand_topology_sha256="b" * 64,
        rescue_policy_sha256=policy.fingerprint_sha256,
        allocation=allocation,
        baseline_guided_receipt=baseline_receipt,
        guided_receipt=guided_receipt,
        candidate_ids=tuple(proposal.candidate_id for proposal in proposals),
        proposal_fingerprint_sha256s=proposal_fingerprints,
        proposal_coordinate_fingerprint_sha256s=tuple(
            proposal.coordinate_fingerprint_sha256 for proposal in proposals
        ),
        proposal_torsion_metadata_sha256s=tuple(
            guided_module._torsion_metadata_sha256(proposal.torsion_angles)
            for proposal in proposals
        ),
    )
    v2_config = InteractionAwareRigidConfigV2(
        maximum_step_angstrom=0.001,
        minimum_step_angstrom=0.000125,
        maximum_total_translation_angstrom=0.001,
    )
    v3_config = InteractionAwareRigidConfigV3(
        maximum_step_angstrom=0.001,
        minimum_step_angstrom=0.000125,
        maximum_total_translation_angstrom=0.001,
        maximum_rotation_step_radians=1.0e-4,
        minimum_rotation_step_radians=1.0e-5,
        maximum_total_rotation_radians=1.0e-4,
        maximum_rotation_steps=1,
    )
    clearance_config = InteractionAwareRigidClearanceConfigV4(
        overlap_scale=0.85,
        maximum_step_angstrom=0.001,
        minimum_step_angstrom=0.000125,
        maximum_total_translation_angstrom=0.001,
        maximum_rotation_step_radians=1.0e-4,
        minimum_rotation_step_radians=1.0e-5,
        maximum_total_rotation_radians=1.0e-4,
        maximum_rotation_steps=1,
    )
    torsion_config = InteractionAwareTorsionContactConfigV7()
    refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="7" * 64,
        v3_proposal_indices=(),
        source_paired_torsion_rescue_profile=True,
        source_paired_torsion_rescue_allocation=allocation,
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=torsion_config,
    )
    for parent in sorted({parent for _, parent in rescue_pairs}):
        refiner.refine(proposals[parent], max_steps=20)
    currents = tuple(
        refiner.refine(proposals[target], max_steps=20) for target, _ in rescue_pairs
    )
    snapshots = tuple(
        refiner.activation_snapshot(
            proposals[target].fingerprint_sha256,
            proposal_receipt=proposal_receipt,
        )
        for target, _ in rescue_pairs
    )
    if return_all:
        return proposals, currents, snapshots, proposal_receipt
    return proposals, currents[0], snapshots[0], proposal_receipt


def test_ineligible_snapshot_retains_exact_current_v7_before_scoring() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=True
    )
    current_fingerprint = current_v7.fingerprint_sha256
    current_coordinates = current_v7.coordinates.clone()

    with pytest.raises(TypeError, match="builder-produced"):
        SourcePairedClearanceActivatedStateV1()
    state = build_source_paired_clearance_activated_state_v1(snapshot, current_v7)
    selected = state.selected_or_retained_proposal
    document = state.to_dict()

    assert state.selection_applied is False
    assert state.shadow_selection_eligible is False
    assert state.selected_action == "retain_exact_current_v7_state"
    assert selected.fingerprint_sha256 == current_fingerprint
    assert torch.equal(selected.coordinates, current_coordinates)
    assert current_v7.fingerprint_sha256 == current_fingerprint
    assert torch.equal(current_v7.coordinates, current_coordinates)
    assert document["schema_id"] == SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID
    assert document["source_snapshot_sha256"] == snapshot.snapshot_sha256
    assert document["decision_sealed_before_scoring"] is True
    assert document["score_rank_rmsd_posebusters_native_or_case_identity_used"] is False
    for name in (
        "historical_ab_execution_authorized",
        "historical_result_materialization_authorized",
        "generic_runner_cli_wired",
        "product_path_wired",
        "fresh_execution_authorized",
        "customer_pose_emission_authorized",
        "stage0_eligible",
        "public_or_scientific_claim_authorized",
        "claim_safe",
    ):
        assert document[name] is False
    state_projection = dict(document)
    assert state_projection.pop("state_sha256") == state.state_sha256
    assert _canonical_sha256(state_projection) == state.state_sha256


def test_shadow_eligible_snapshot_selects_only_optimized_state() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )
    optimized_coordinate_sha256 = snapshot.to_dict()["optimized_coordinates"][
        "coordinate_sha256"
    ]
    current_fingerprint = current_v7.fingerprint_sha256
    current_coordinates = current_v7.coordinates.clone()

    state = build_source_paired_clearance_activated_state_v1(snapshot, current_v7)
    selected = state.selected_or_retained_proposal
    document = state.to_dict()

    assert state.shadow_selection_eligible is True
    assert state.selection_applied is True
    assert state.selected_action == "select_shadow_eligible_optimized_state"
    assert selected.coordinate_fingerprint_sha256 == (optimized_coordinate_sha256)
    assert selected.fingerprint_sha256 != current_fingerprint
    assert selected.parent_proposal_fingerprint_sha256 == current_fingerprint
    assert selected.refiner_id == SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_ID
    assert selected.refinement_receipt_sha256 == document["decision_sha256"]
    assert document["selected_or_retained_candidate_proposal_fingerprint_sha256"] == (
        selected.fingerprint_sha256
    )
    assert current_v7.fingerprint_sha256 == current_fingerprint
    assert torch.equal(current_v7.coordinates, current_coordinates)


def test_snapshot_and_current_v7_tampering_fail_closed() -> None:
    proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )
    projection = snapshot.to_dict()
    projection.pop("snapshot_sha256")
    projection["source_v11_receipt_payload"]["lane"] = "tampered"
    with pytest.raises(TorsionContactRefinementError, match="refiner builder"):
        refinement_module._build_source_paired_activation_snapshot(
            projection,
            _builder_token=object(),
        )
    with pytest.raises(SourcePairedClearanceActivationError, match="cross-wired"):
        build_source_paired_clearance_activated_state_v1(snapshot, proposals[0])


def _snapshot_from_correct_builder_token(
    projection: dict[str, object],
):
    projection.pop("snapshot_sha256", None)
    return refinement_module._build_source_paired_activation_snapshot(
        projection,
        _builder_token=refinement_module._ACTIVATION_SNAPSHOT_BUILDER_TOKEN,
    )


def test_correct_token_cannot_forge_raw_clearance_statistics() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )
    projection = snapshot.to_dict()
    forged_value = (
        float.fromhex(
            projection["baseline_clearance_statistics"][
                "minimum_distance_angstrom_binary64_hex"
            ]
        )
        + 1.0
    )
    for statistics in (
        projection["baseline_clearance_statistics"],
        projection["clearance"]["baseline"],
    ):
        statistics["minimum_distance_angstrom_binary64_hex"] = forged_value.hex()
    forged = _snapshot_from_correct_builder_token(projection)

    with pytest.raises(
        SourcePairedClearanceActivationError,
        match="authenticated geometry",
    ):
        build_source_paired_clearance_activated_state_v1(forged, current_v7)


def test_correct_token_cannot_forge_optimized_torsion_state() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )
    projection = snapshot.to_dict()
    optimized = projection["optimized_torsion_angles"]
    values = optimized["values_binary64_hex"]
    rotor = projection["source_v11_receipt_payload"]["rotatable_child_atom_indices"][0]
    values[rotor] = (float.fromhex(values[rotor]) + 0.125).hex()
    projection["optimized_state"]["torsion_angles"] = optimized
    optimized_tensor = torch.tensor(
        [float.fromhex(value) for value in values],
        dtype=torch.float64,
    )
    projection["optimized_torsion_metadata_sha256"] = (
        guided_module._torsion_metadata_sha256(optimized_tensor)
    )
    forged = _snapshot_from_correct_builder_token(projection)

    with pytest.raises(SourcePairedClearanceActivationError, match="does not replay"):
        build_source_paired_clearance_activated_state_v1(forged, current_v7)


def test_correct_token_cannot_flip_optimized_torsion_signed_zero() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )
    projection = snapshot.to_dict()
    optimized = projection["optimized_torsion_angles"]
    values = optimized["values_binary64_hex"]
    untouched_index = next(
        index
        for index, value in enumerate(values)
        if value == (0.0).hex()
        and index
        not in {
            move["rotatable_child_atom_index"]
            for move in projection["evaluated_torsion_moves"]
        }
    )
    values[untouched_index] = (-0.0).hex()
    projection["optimized_state"]["torsion_angles"] = optimized
    optimized_tensor = torch.tensor(
        [float.fromhex(value) for value in values],
        dtype=torch.float64,
    )
    projection["optimized_torsion_metadata_sha256"] = (
        guided_module._torsion_metadata_sha256(optimized_tensor)
    )
    forged = _snapshot_from_correct_builder_token(projection)

    with pytest.raises(SourcePairedClearanceActivationError, match="does not replay"):
        build_source_paired_clearance_activated_state_v1(forged, current_v7)


def test_correct_token_cannot_forge_candidate_torsion_identity() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )
    projection = snapshot.to_dict()
    projection["candidate_torsion_metadata_sha256"] = "0" * 64
    forged = _snapshot_from_correct_builder_token(projection)

    with pytest.raises(SourcePairedClearanceActivationError, match="cross-wired"):
        build_source_paired_clearance_activated_state_v1(forged, current_v7)


def test_snapshot_subclass_is_rejected_before_projection_dispatch() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=False
    )

    class SnapshotSubclass(
        refinement_module.SourcePairedTorsionRescueActivationSnapshotV1
    ):
        def __init__(self) -> None:
            pass

        @property
        def snapshot_sha256(self) -> str:
            return snapshot.snapshot_sha256

        def to_dict(self) -> dict[str, object]:
            return snapshot.to_dict()

    with pytest.raises(TypeError, match="snapshot must be"):
        build_source_paired_clearance_activated_state_v1(
            SnapshotSubclass(),
            current_v7,
        )


def test_state_returns_integrity_checked_clones() -> None:
    _proposals, current_v7, snapshot, _proposal_receipt = _fixture(
        permissive_selection_window=True
    )
    state = build_source_paired_clearance_activated_state_v1(snapshot, current_v7)
    returned = state.selected_or_retained_proposal
    returned.coordinates[0, 0] += 1.0

    pristine = state.selected_or_retained_proposal
    pristine.assert_integrity()
    assert pristine.fingerprint_sha256 == current_v7.fingerprint_sha256
    with pytest.raises(FrozenInstanceError):
        state._state_sha256 = "0" * 64


def test_activation_api_cannot_accept_outcome_evidence() -> None:
    signature = inspect.signature(build_source_paired_clearance_activated_state_v1)
    assert tuple(signature.parameters) == (
        "snapshot",
        "current_v7_proposal",
        "policy",
    )
    forbidden = {
        "score",
        "rank",
        "rmsd",
        "posebusters",
        "native",
        "case_id",
        "validity",
    }
    assert forbidden.isdisjoint(signature.parameters)
