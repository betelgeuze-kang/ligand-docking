from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
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
    VdwContactPolicy,
    build_element_aware_authenticated_known_pocket_docking_problem,
    generate_bounded_docking_proposals,
)
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint  # noqa: E402


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="activation-snapshot-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="activation-snapshot-ligand",
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


def _receptor() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="activation-snapshot-receptor",
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
        coordinates=torch.tensor(
            [
                [
                    [1.2307712254983234, 3.9434758050512015, 1.6523553225866865],
                    [8.0, 8.0, 8.0],
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=_provenance("activation-receptor", "b" * 64),
    )


def _pocket() -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="activation-snapshot-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=20.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )


def _fixture():
    receptor = _receptor()
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
        rescue_target_parent_pairs=((1, 0),),
    )
    proposal_fingerprints = tuple(proposal.fingerprint_sha256 for proposal in proposals)
    baseline_modes = ["uniform_fallback"] * 64
    baseline_modes[1] = "uniform_v3_rigid_ensemble"
    baseline_sources: list[int | None] = [None] * 64
    baseline_sources[1] = 0
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
    guided_modes[1] = "uniform_torsion_rescue_variant"
    guided_sources = list(baseline_sources)
    guided_sources[1] = None
    rescue_parents: list[int | None] = [None] * 64
    rescue_parents[1] = 0
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
        torsion_config=InteractionAwareTorsionContactConfigV7(
            maximum_torsion_steps=3,
            minimum_selected_final_receptor_penalty=0.0,
            maximum_selected_final_receptor_penalty=100.0,
        ),
    )
    return receptor, ligand, authority, proposals, allocation, refiner, proposal_receipt


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


def _tensor_from_payload(payload: dict[str, object]) -> torch.Tensor:
    assert payload["dtype"] == "float64"
    shape = tuple(int(value) for value in payload["shape"])
    values = [float.fromhex(value) for value in payload["values_binary64_hex"]]
    return torch.tensor(values, dtype=torch.float64).reshape(shape)


def test_builder_seals_exact_v11_source_states_and_full_clearance() -> None:
    receptor, ligand, authority, proposals, allocation, refiner, proposal_receipt = (
        _fixture()
    )
    source = proposals[1]

    with pytest.raises(TypeError, match="builder-produced"):
        refinement_module.SourcePairedTorsionRescueActivationSnapshotV1()
    with pytest.raises(TorsionContactRefinementError, match="exact proposal"):
        refiner.activation_snapshot(
            source.fingerprint_sha256,
            proposal_receipt=proposal_receipt,
        )

    refined_parent = refiner.refine(proposals[0], max_steps=20)
    with pytest.raises(TorsionContactRefinementError, match="not a fixed"):
        refiner.activation_snapshot(
            proposals[0].fingerprint_sha256,
            proposal_receipt=proposal_receipt,
        )
    refined = refiner.refine(source, max_steps=20)
    crosswired_coordinates = list(
        proposal_receipt.proposal_coordinate_fingerprint_sha256s
    )
    crosswired_coordinates[source.proposal_index] = "0" * 64
    crosswired_receipt = replace(
        proposal_receipt,
        proposal_coordinate_fingerprint_sha256s=tuple(crosswired_coordinates),
    )
    with pytest.raises(TorsionContactRefinementError, match="cross-wired"):
        refiner.activation_snapshot(
            source.fingerprint_sha256,
            proposal_receipt=crosswired_receipt,
        )
    snapshot = refiner.activation_snapshot(
        source.fingerprint_sha256,
        proposal_receipt=proposal_receipt,
    )
    cloned_snapshot = refiner.activation_snapshot(
        source.fingerprint_sha256,
        proposal_receipt=proposal_receipt,
    )
    document = snapshot.to_dict()

    assert snapshot is not cloned_snapshot
    assert document["schema_id"] == (
        refinement_module.SOURCE_PAIRED_TORSION_RESCUE_ACTIVATION_SNAPSHOT_SCHEMA_ID
    )
    snapshot_sha256 = document.pop("snapshot_sha256")
    assert snapshot_sha256 == snapshot.snapshot_sha256
    assert snapshot_sha256 == _canonical_sha256(document)
    assert document["source_v11_receipt_payload"] == dict(
        refiner.receipts[source.fingerprint_sha256]
    )
    assert (
        document["source_v11_receipt_sha256"]
        == (document["source_v11_receipt_payload"]["receipt_sha256"])
    )
    source_receipt_projection = dict(document["source_v11_receipt_payload"])
    assert (
        source_receipt_projection.pop("receipt_sha256")
        == (document["source_v11_receipt_sha256"])
    )
    assert (
        _canonical_sha256(source_receipt_projection)
        == (document["source_v11_receipt_sha256"])
    )
    assert document["allocation_receipt_payload"] == allocation.to_dict()
    assert document["allocation_receipt_sha256"] == allocation.allocation_sha256
    assert document["source_proposal_receipt_payload"] == proposal_receipt.to_dict()
    assert document["source_proposal_receipt_sha256"] == (
        proposal_receipt.receipt_sha256
    )
    assert document["authenticated_input_receipt_sha256"] == (
        authority.input_receipt_sha256
    )
    assert document["authenticated_input_receipt_payload"] == authority.to_dict()
    assert document["validity_context_payload"] == authority.validity_context.to_dict()
    receptor_coordinate_payload = document["receptor_coordinates"]
    assert _tensor_from_payload(receptor_coordinate_payload).shape == (
        len(authority.receptor_atom_indices),
        3,
    )
    assert receptor_coordinate_payload["validity_coordinate_sha256"] == (
        authority.validity_context.receptor_coordinates_sha256
    )
    assert document["candidate_id"] == refined.candidate_id == source.candidate_id
    assert document["proposal_index"] == source.proposal_index
    assert document["candidate_proposal_fingerprint_sha256"] == (
        refined.fingerprint_sha256
    )
    assert document["source_proposal_fingerprint_sha256"] == (source.fingerprint_sha256)
    assert (
        document["candidate_proposal_fingerprint_sha256"]
        != (document["source_proposal_fingerprint_sha256"])
    )
    assert document["source_paired_parent_proposal_index"] == 0
    assert refined_parent.fingerprint_sha256 != refined.fingerprint_sha256
    assert document["generic_v7_config_sha256"] == (refiner._config.fingerprint_sha256)
    assert document["vdw_contact_policy_sha256"] == (
        VdwContactPolicy().fingerprint_sha256
    )
    assert document["v6_baseline_torsion_metadata_sha256"] == (
        guided_module._torsion_metadata_sha256(
            _tensor_from_payload(document["v6_baseline_torsion_angles"])
        )
    )
    assert document["optimized_torsion_metadata_sha256"] == (
        guided_module._torsion_metadata_sha256(
            _tensor_from_payload(document["optimized_torsion_angles"])
        )
    )

    baseline_state = refiner._baseline_state_for_experimental_v8(
        source.fingerprint_sha256
    )
    optimized_state = refiner._optimized_state_for_experimental_v8(
        source.fingerprint_sha256
    )
    for name, expected_state in (
        ("v6_baseline_state", baseline_state),
        ("optimized_state", optimized_state),
    ):
        state = document[name]
        coordinates = _tensor_from_payload(state["coordinates"])
        torsion_angles = _tensor_from_payload(state["torsion_angles"])
        assert torch.equal(coordinates, expected_state.coordinates.to(torch.float64))
        assert torch.equal(
            torsion_angles,
            expected_state.torsion_angles.to(torch.float64),
        )
        assert state["coordinates"]["shape"] == [ligand.atom_count, 3]
        assert state["torsion_angles"]["shape"] == [ligand.atom_count]
        assert (
            coordinate_fingerprint(coordinates)
            == (state["coordinates"]["coordinate_sha256"])
        )

    clearance = document["clearance"]
    assert clearance["evaluated"] is True
    assert clearance["unavailable_reason"] == "none"
    assert clearance["ligand_atom_count"] == ligand.atom_count
    assert clearance["receptor_atom_count"] == len(authority.receptor_atom_indices)
    assert clearance["exact_pair_count"] == (
        ligand.atom_count * len(authority.receptor_atom_indices)
    )
    receptor_coordinates = receptor.coordinates[
        authority.receptor_model_index,
        list(authority.receptor_atom_indices),
    ].to(dtype=torch.float64)
    ligand_radii = torch.tensor(
        [VdwContactPolicy().radius(atom.element) for atom in ligand.atoms],
        dtype=torch.float64,
    )
    receptor_radii = torch.tensor(
        [
            VdwContactPolicy().radius(receptor.atoms[index].element)
            for index in authority.receptor_atom_indices
        ],
        dtype=torch.float64,
    )
    for name, coordinate_field in (
        ("baseline", "v6_baseline_coordinates"),
        ("optimized", "optimized_coordinates"),
    ):
        coordinates = _tensor_from_payload(document[coordinate_field])
        delta = coordinates[:, None, :] - receptor_coordinates[None, :, :]
        distances = torch.linalg.vector_norm(delta, dim=-1)
        radii_sum = ligand_radii[:, None] + receptor_radii[None, :]
        gaps = distances - radii_sum
        ratios = distances / radii_sum
        statistics = clearance[name]
        for metric_name, metric in (
            ("minimum_distance", distances),
            ("minimum_vdw_surface_gap", gaps),
            ("minimum_vdw_ratio", ratios),
        ):
            flat_index = int(torch.argmin(metric).item())
            ligand_index = flat_index // len(receptor_coordinates)
            receptor_index = authority.receptor_atom_indices[
                flat_index % len(receptor_coordinates)
            ]
            assert float.fromhex(
                statistics[f"{metric_name}_angstrom_binary64_hex"]
                if metric_name != "minimum_vdw_ratio"
                else statistics["minimum_vdw_ratio_binary64_hex"]
            ) == float(metric.reshape(-1)[flat_index].item())
            assert statistics[f"{metric_name}_ligand_atom_index"] == ligand_index
            assert statistics[f"{metric_name}_receptor_atom_index"] == receptor_index

    receipt = document["source_v11_receipt_payload"]
    objectives = document["objectives"]
    assert objectives["baseline"] == {
        "receptor_binary64_hex": receipt["baseline_v6_receptor_penalty_binary64_hex"],
        "internal_binary64_hex": receipt["baseline_v6_internal_penalty_binary64_hex"],
        "combined_binary64_hex": receipt["baseline_v6_combined_penalty_binary64_hex"],
    }
    assert objectives["optimized"] == {
        "receptor_binary64_hex": receipt["optimized_receptor_penalty_binary64_hex"],
        "internal_binary64_hex": receipt["optimized_internal_penalty_binary64_hex"],
        "combined_binary64_hex": receipt["optimized_combined_penalty_binary64_hex"],
    }
    assert document["torsion_state"] == {
        "evaluated": receipt["torsion_evaluated"],
        "variant_available": receipt["torsion_variant_available"],
        "selected": receipt["torsion_selected"],
        "evaluated_steps": receipt["evaluated_torsion_steps"],
        "evaluated_moves": receipt["evaluated_torsion_moves"],
    }

    document["source_v11_receipt_payload"]["schema_id"] = "tampered"
    document["optimized_state"]["coordinates"]["values_binary64_hex"][0] = (0.0).hex()
    assert cloned_snapshot.to_dict()["source_v11_receipt_payload"]["schema_id"] == (
        refinement_module.INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID
    )
    assert (
        cloned_snapshot.to_dict()["optimized_state"]["coordinates"]
        != (document["optimized_state"]["coordinates"])
    )
    with pytest.raises(FrozenInstanceError):
        snapshot._snapshot_sha256 = "0" * 64


def test_snapshot_fails_closed_for_nonprofile_and_unavailable_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        receptor,
        ligand,
        authority,
        proposals,
        allocation,
        source_refiner,
        proposal_receipt,
    ) = _fixture()
    ordinary_refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="7" * 64,
        v3_proposal_indices=(1,),
    )
    ordinary_refiner.refine(proposals[1], max_steps=20)
    with pytest.raises(TorsionContactRefinementError, match="V1.1 profile"):
        ordinary_refiner.activation_snapshot(
            proposals[1].fingerprint_sha256,
            proposal_receipt=proposal_receipt,
        )

    monkeypatch.setattr(refinement_module, "MAX_RECEPTOR_CLEARANCE_PAIR_COUNT", 0)
    unavailable_refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="7" * 64,
        v3_proposal_indices=(),
        source_paired_torsion_rescue_profile=True,
        source_paired_torsion_rescue_allocation=allocation,
        torsion_config=source_refiner._config,
    )
    unavailable_refiner.refine(proposals[1], max_steps=20)
    with pytest.raises(TorsionContactRefinementError, match="evidence is unavailable"):
        unavailable_refiner.activation_snapshot(
            proposals[1].fingerprint_sha256,
            proposal_receipt=proposal_receipt,
        )
