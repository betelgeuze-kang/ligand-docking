from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import json

import pytest


torch = pytest.importorskip("torch")

import betelgeuze_engine_v2.benchmark.public_redocking_benchmark as benchmark_contract  # noqa: E402
import betelgeuze_engine_v2.docking.torsion_contact_refinement as torsion_contact_refinement  # noqa: E402

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
    ClashReliefRefinementError,
    ElementAwarePoseValidityContext,
    ElementAwareValidityError,
    InteractionAwareRigidClearanceConfigV4,
    InteractionAwareRigidClearanceEnsembleRefinerV5,
    InteractionAwareRigidHybridClearanceEnsembleRefinerV6,
    InteractionAwareRigidConfigV2,
    InteractionAwareRigidConfigV3,
    InteractionAwareRigidEnsembleRefinerV4,
    InteractionAwareRigidRefinerV2,
    InteractionAwareRigidRefinerV3,
    InteractionAwareTorsionClearanceConfigV8,
    InteractionAwareTorsionClearanceEnsembleRefinerV8,
    InteractionAwareTorsionContactConfigV7,
    InteractionAwareTorsionContactEnsembleRefinerV7,
    SourcePairedTorsionRescueAllocation,
    SourcePairedTorsionRescuePolicy,
    TorsionContactRefinementError,
    UnsupportedVdwElementError,
    PocketDefinition,
    ReceptorClashReliefRefiner,
    VdwContactPolicy,
    build_element_aware_authenticated_known_pocket_docking_problem,
    element_aware_authority_document,
    generate_bounded_docking_proposals,
)
from betelgeuze_engine_v2.docking.identity import (  # noqa: E402
    coordinate_fingerprint,
)
from betelgeuze_engine_v2.docking.proposals import (  # noqa: E402
    DockingProposal,
    _proposal_fingerprint,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="contact-fixture",
        parser_version="1.0.0",
    )


def _ligand(*, element: str = "C") -> AllAtomSystem:
    elements = (element, "N", "C", "O")
    atomic_numbers = {"C": 6, "N": 7, "O": 8, "XE": 54, "ZN": 30}
    return AllAtomSystem(
        system_id="contact-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=value,
                atomic_number=atomic_numbers[value.upper()],
                residue_index=0,
            )
            for index, value in enumerate(elements)
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
        provenance=_provenance("contact-ligand-source", "a" * 64),
    )


def _receptor(
    *, overlapping: bool = False, many: bool = False, element: str = "C"
) -> AllAtomSystem:
    if overlapping:
        coordinates = [[0.0, 0.0, 0.0], [8.0, 8.0, 8.0]]
    elif many:
        coordinates = [
            [float(x), float(y), float(z)]
            for x in range(-8, 9, 4)
            for y in range(-8, 9, 4)
            for z in (-6, 0, 6)
        ]
    else:
        coordinates = [[8.0, 8.0, 8.0], [10.0, -7.0, 3.0]]
    atoms = tuple(
        Atom(
            index=index,
            name=f"R{index}",
            element=element,
            atomic_number={"C": 6, "ZN": 30}[element.upper()],
            residue_index=0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id="contact-receptor",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("contact-receptor-source", "b" * 64),
    )


def _pocket(radius: float = 20.0) -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="contact-test-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64),
        radius_angstrom=radius,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )


def _baseline(authority):
    return generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=97,
        ),
        problem=authority.problem,
    )[0]


def test_element_aware_context_adds_conjunctive_vdw_checks() -> None:
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        _pocket(),
    )
    assert isinstance(authority.validity_context, ElementAwarePoseValidityContext)
    result = authority.validity_context.evaluate(_baseline(authority))
    assert result.evaluated_checks["element_vdw_ligand_overlap_free"] is True
    assert result.evaluated_checks["element_vdw_receptor_overlap_free"] is True
    assert result.checks["element_vdw_ligand_overlap_free"] is True
    assert result.checks["element_vdw_receptor_overlap_free"] is True
    assert all(
        isinstance(value, (int, float)) for value in result.measurements.values()
    )
    assert len(authority.validity_context.contact_policy.fingerprint_sha256) == 64
    document = element_aware_authority_document(authority)
    assert document["element_inference_performed"] is False
    assert document["contact_policy_sha256"] == (
        authority.validity_context.contact_policy.fingerprint_sha256
    )
    assert document["claim_safe"] is False


def test_contact_policy_changes_authority_and_context_identity() -> None:
    first = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        _pocket(),
        contact_policy=VdwContactPolicy(severe_overlap_scale=0.50),
    )
    second = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        _pocket(),
        contact_policy=VdwContactPolicy(severe_overlap_scale=0.60),
    )
    assert first.validity_context.fingerprint_sha256 != (
        second.validity_context.fingerprint_sha256
    )
    assert first.input_receipt_sha256 != second.input_receipt_sha256


def test_element_aware_context_detects_severe_receptor_overlap() -> None:
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(overlapping=True),
        _ligand(),
        _pocket(),
    )
    result = authority.validity_context.evaluate(_baseline(authority))
    assert result.checks["element_vdw_receptor_overlap_free"] is False
    assert result.measurements["element_vdw_receptor_severe_overlap_count"] >= 1
    assert "element_vdw_receptor_severe_overlap_detected" in result.blockers
    assert result.valid is False


def test_sparse_receptor_candidates_are_less_than_full_cartesian_pairs() -> None:
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(many=True),
        _ligand(),
        _pocket(radius=25.0),
        receptor_margin_angstrom=0.0,
    )
    result = authority.validity_context.evaluate(_baseline(authority))
    candidates = result.measurements["element_vdw_receptor_candidate_pair_count"]
    cartesian = result.measurements["element_vdw_receptor_full_cartesian_pair_count"]
    assert 0 <= candidates < cartesian
    assert result.measurements["element_vdw_receptor_cell_count"] > 1


def test_unsupported_element_and_invalid_policy_fail_closed() -> None:
    with pytest.raises(UnsupportedVdwElementError, match="unsupported vdW element"):
        build_element_aware_authenticated_known_pocket_docking_problem(
            _receptor(),
            _ligand(element="XE"),
            _pocket(),
        )
    with pytest.raises(ElementAwareValidityError, match="cell_size_angstrom"):
        VdwContactPolicy(cell_size_angstrom=1.0)


def test_receptor_ion_proxy_is_narrow_and_ligand_metal_stays_unsupported() -> None:
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(element="Zn"),
        _ligand(),
        _pocket(),
    )
    document = element_aware_authority_document(authority)
    assert "ZN" in document["receptor_ion_proxy_elements"]
    assert document["receptor_ion_coordination_modeled"] is False
    assert document["ligand_metal_support"] is False

    with pytest.raises(UnsupportedVdwElementError, match="separate applicability"):
        build_element_aware_authenticated_known_pocket_docking_problem(
            _receptor(),
            _ligand(element="Zn"),
            _pocket(),
        )


def test_receptor_clash_relief_is_bounded_and_preserves_lineage() -> None:
    receptor = _receptor(overlapping=True)
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposal = _baseline(authority)
    refiner = ReceptorClashReliefRefiner(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
    )

    refined = refiner.refine(proposal, max_steps=10)
    receipt = refiner.receipts[proposal.fingerprint_sha256]

    assert refined.parent_proposal_fingerprint_sha256 == proposal.fingerprint_sha256
    assert refined.refiner_id == refiner.refiner_id
    assert float.fromhex(receipt["final_penalty_binary64_hex"]) < float.fromhex(
        receipt["initial_penalty_binary64_hex"]
    )
    assert torch.linalg.vector_norm(refined.translation - proposal.translation) <= 1.5


def test_interaction_aware_v2_refines_contact_penalty_even_if_v1_valid() -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [[[-2.4, 0.0, 0.0], [8.0, 8.0, 8.0]]],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposal = _baseline(authority)
    assert authority.validity_context.evaluate(proposal).valid is True

    baseline = ReceptorClashReliefRefiner(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
    )
    v2 = InteractionAwareRigidRefinerV2(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="f" * 64,
    )

    baseline_pose = baseline.refine(proposal, max_steps=10)
    refined = v2.refine(proposal, max_steps=10)
    baseline_receipt = baseline.receipts[proposal.fingerprint_sha256]
    receipt = v2.receipts[proposal.fingerprint_sha256]

    assert baseline_receipt["accepted_steps"] == 0
    assert torch.equal(baseline_pose.coordinates, proposal.coordinates)
    assert receipt["original_pose_valid"] is True
    assert receipt["accepted_steps"] >= 1
    assert float.fromhex(receipt["initial_penalty_binary64_hex"]) > 0.0
    assert float.fromhex(receipt["final_penalty_binary64_hex"]) == 0.0
    shift = torch.tensor(
        [float.fromhex(value) for value in receipt["total_translation_binary64_hex"]],
        dtype=torch.float64,
    )
    assert torch.linalg.vector_norm(shift) <= 2.25
    assert refined.parent_proposal_fingerprint_sha256 == proposal.fingerprint_sha256
    assert refined.refiner_id == v2.refiner_id


def test_interaction_aware_v3_records_rotation_and_enforces_pocket_guard() -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [[[4.1, 0.5, 0.2], [8.0, 8.0, 8.0]]],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposal = _baseline(authority)
    config = InteractionAwareRigidConfigV3(
        maximum_step_angstrom=0.009375,
        minimum_step_angstrom=0.009375,
        maximum_total_translation_angstrom=0.009375,
        maximum_total_rotation_radians=0.25,
    )
    refiner = InteractionAwareRigidRefinerV3(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="1" * 64,
        config=config,
    )

    refined = refiner.refine(proposal, max_steps=10)
    receipt = refiner.receipts[proposal.fingerprint_sha256]

    assert receipt["schema_id"].endswith("/3.0.0")
    assert receipt["accepted_rotation_steps"] >= 1
    rotation = torch.tensor(
        [
            float.fromhex(value)
            for value in receipt["total_rotation_vector_binary64_hex"]
        ],
        dtype=torch.float64,
    )
    assert torch.linalg.vector_norm(rotation) > 0.0
    assert (
        float.fromhex(receipt["total_rotation_path_radians_binary64_hex"])
        <= config.maximum_total_rotation_radians
    )
    assert (
        float.fromhex(receipt["final_centroid_offset_angstrom_binary64_hex"])
        <= config.maximum_centroid_offset_angstrom
    )
    assert refined.refiner_id == refiner.refiner_id
    assert refined.parent_proposal_fingerprint_sha256 == proposal.fingerprint_sha256


def test_interaction_aware_v4_routes_only_receipt_bound_variants_to_v3() -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [[[4.1, 0.5, 0.2], [8.0, 8.0, 8.0]]],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposals = generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=97,
        ),
        problem=authority.problem,
    )
    implementation_sha256 = "7" * 64
    expected_v2_refiner = InteractionAwareRigidRefinerV2(
        authority,
        receptor,
        ligand,
        implementation_source_sha256=implementation_sha256,
    )
    expected_v3_refiner = InteractionAwareRigidRefinerV3(
        authority,
        receptor,
        ligand,
        implementation_source_sha256=implementation_sha256,
    )
    expected_v2 = expected_v2_refiner.refine(proposals[0], max_steps=10)
    expected_v3 = expected_v3_refiner.refine(proposals[1], max_steps=10)
    ensemble = InteractionAwareRigidEnsembleRefinerV4(
        authority,
        receptor,
        ligand,
        implementation_source_sha256=implementation_sha256,
        v3_proposal_indices=(1,),
    )

    observed_v2 = ensemble.refine(proposals[0], max_steps=10)
    observed_v3 = ensemble.refine(proposals[1], max_steps=10)
    v2_receipt = ensemble.receipts[proposals[0].fingerprint_sha256]
    v3_receipt = ensemble.receipts[proposals[1].fingerprint_sha256]

    assert torch.equal(observed_v2.coordinates, expected_v2.coordinates)
    assert torch.equal(observed_v3.coordinates, expected_v3.coordinates)
    assert observed_v2.refiner_id == ensemble.refiner_id
    assert observed_v3.refiner_id == ensemble.refiner_id
    assert v2_receipt["lane"] == "translation_v2"
    assert v3_receipt["lane"] == "translation_rotation_v3"
    assert v2_receipt["nested_refiner_id"] == expected_v2_refiner.refiner_id
    assert v3_receipt["nested_refiner_id"] == expected_v3_refiner.refiner_id
    assert (
        v2_receipt["nested_receipt_sha256"]
        == expected_v2_refiner.receipts[proposals[0].fingerprint_sha256][
            "receipt_sha256"
        ]
    )
    assert (
        v3_receipt["nested_receipt_sha256"]
        == expected_v3_refiner.receipts[proposals[1].fingerprint_sha256][
            "receipt_sha256"
        ]
    )
    assert v2_receipt["accepted_rotation_steps"] == 0
    assert (
        v3_receipt["accepted_rotation_steps"]
        == expected_v3_refiner.receipts[proposals[1].fingerprint_sha256][
            "accepted_rotation_steps"
        ]
    )
    assert v2_receipt["source_lane_retained"] is True
    assert v3_receipt["source_lane_retained"] is True


def test_interaction_aware_v5_binds_expanded_clearance_to_variant_lane() -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [[[4.1, 0.5, 0.2], [8.0, 8.0, 8.0]]],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposals = generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=101,
        ),
        problem=authority.problem,
    )
    config = InteractionAwareRigidClearanceConfigV4()
    assert config.overlap_scale == 0.80
    assert config.maximum_total_translation_angstrom == 4.0
    assert config.maximum_total_rotation_radians == pytest.approx(torch.pi / 6.0)
    assert config.maximum_rotation_steps == 6
    assert config.to_dict()["policy_role"] == (
        "retained_source_variant_clearance_rescue"
    )
    refiner = InteractionAwareRigidClearanceEnsembleRefinerV5(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="9" * 64,
        v3_proposal_indices=(1,),
    )

    refiner.refine(proposals[0], max_steps=10)
    refiner.refine(proposals[1], max_steps=10)
    source_receipt = refiner.receipts[proposals[0].fingerprint_sha256]
    variant_receipt = refiner.receipts[proposals[1].fingerprint_sha256]

    assert source_receipt["lane"] == "translation_v2"
    assert variant_receipt["lane"] == "translation_rotation_v3"
    assert source_receipt["schema_id"].endswith("/5.0.0")
    assert variant_receipt["schema_id"].endswith("/5.0.0")
    assert source_receipt["source_lane_retained"] is True
    assert variant_receipt["source_lane_retained"] is True


def test_interaction_aware_v6_records_receipt_bound_hybrid_selection() -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [[[4.1, 0.5, 0.2], [8.0, 8.0, 8.0]]],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposals = generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=103,
        ),
        problem=authority.problem,
    )
    refiner = InteractionAwareRigidHybridClearanceEnsembleRefinerV6(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="a" * 64,
        v3_proposal_indices=(1,),
    )

    refiner.refine(proposals[0], max_steps=10)
    refiner.refine(proposals[1], max_steps=10)
    source_receipt = refiner.receipts[proposals[0].fingerprint_sha256]
    variant_receipt = refiner.receipts[proposals[1].fingerprint_sha256]

    assert source_receipt["lane"] == "translation_v2"
    assert source_receipt["schema_id"].endswith("/6.0.0")
    assert variant_receipt["schema_id"].endswith("/6.0.0")
    assert variant_receipt["selection_reason"] == "v2_duplicate_clearance_rescue"
    assert variant_receipt["lane"] == ("translation_rotation_v5_clearance_rescue")
    assert variant_receipt["baseline_duplicate_of_v2_refinement"] is True
    assert variant_receipt["clearance_evaluated"] is True
    assert variant_receipt["clearance_selected"] is True
    assert variant_receipt["clearance_initial_penalty_binary64_hex"]
    assert variant_receipt["clearance_final_penalty_binary64_hex"]
    assert len(variant_receipt["comparison_v2_receipt_sha256"]) == 64
    assert len(variant_receipt["baseline_v3_receipt_sha256"]) == 64
    assert len(variant_receipt["clearance_receipt_sha256"]) == 64
    assert float.fromhex(variant_receipt["near_clear_penalty_binary64_hex"]) == 2.0**-12
    assert variant_receipt["source_lane_retained"] is True


def test_interaction_aware_v7_uses_only_authority_rotor_and_retains_v6_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [
                [
                    [1.2307712254983234, 3.9434758050512015, 1.6523553225866865],
                    [8.0, 8.0, 8.0],
                ]
            ],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposals = generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=103,
        ),
        problem=authority.problem,
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
    expected_v6 = InteractionAwareRigidHybridClearanceEnsembleRefinerV6(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
    )
    expected_source = expected_v6.refine(proposals[0], max_steps=20)
    expected_variant = expected_v6.refine(proposals[1], max_steps=20)
    refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=InteractionAwareTorsionContactConfigV7(
            maximum_torsion_steps=3,
            minimum_selected_final_receptor_penalty=0.0,
            maximum_selected_final_receptor_penalty=100.0,
        ),
    )

    observed_source = refiner.refine(proposals[0], max_steps=20)
    observed_variant = refiner.refine(proposals[1], max_steps=20)
    source_receipt = refiner.receipts[proposals[0].fingerprint_sha256]
    variant_receipt = refiner.receipts[proposals[1].fingerprint_sha256]

    assert refiner.config_fingerprint_sha256 == (
        "96e542103a1967d18aef2290c8bf7ae4e69f193ed123069bbf0e660530860330"
    )
    assert source_receipt["schema_id"] == (
        "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
    )
    assert source_receipt["receipt_sha256"] == (
        "9b617518253c3c5949cabcc4897362a79c64bed9939451419da1a9fa2d9a8581"
    )
    assert variant_receipt["schema_id"] == source_receipt["schema_id"]
    for active_v7_receipt in (source_receipt, variant_receipt):
        assert "source_paired_torsion_rescue_profile" not in active_v7_receipt
        assert "source_paired_torsion_rescue_allocation_sha256" not in active_v7_receipt
        assert "proposal_torsion_eligibility_lane" not in active_v7_receipt

    assert torch.equal(observed_source.coordinates, expected_source.coordinates)
    assert source_receipt["torsion_evaluated"] is False
    assert source_receipt["torsion_variant_available"] is False
    assert source_receipt["torsion_selected"] is False
    assert source_receipt["torsion_evaluation_skip_reason"] == "not_v3_variant"
    assert source_receipt["selection_reason"] == (
        "v6_baseline_retained_no_torsion_objective_reduction"
    )
    assert (
        source_receipt["baseline_v6_receipt_sha256"]
        == (expected_v6.receipts[proposals[0].fingerprint_sha256]["receipt_sha256"])
    )
    assert (
        source_receipt["baseline_v6_receipt_payload"]["receipt_sha256"]
        == (source_receipt["baseline_v6_receipt_sha256"])
    )
    assert (
        source_receipt["initial_penalty_binary64_hex"]
        == (source_receipt["initial_combined_penalty_binary64_hex"])
    )
    assert (
        source_receipt["final_penalty_binary64_hex"]
        == (source_receipt["final_combined_penalty_binary64_hex"])
    )
    assert (
        source_receipt["accepted_rotation_steps"]
        == (source_receipt["accepted_rigid_rotation_steps"])
    )
    assert source_receipt["generic_penalty_scope"] == (
        "source_proposal_to_final_coordinates_v7_objective"
    )

    assert variant_receipt["torsion_evaluated"] is True
    assert variant_receipt["torsion_variant_available"] is True
    assert variant_receipt["torsion_selected"] is True
    assert variant_receipt["torsion_evaluation_skip_reason"] == "none"
    assert variant_receipt["selection_reason"] == (
        "final_receptor_penalty_window_selected"
    )
    assert variant_receipt["evaluated_torsion_steps"] == 3
    assert variant_receipt["accepted_torsion_steps"] == 3
    assert variant_receipt["accepted_steps"] <= 20
    assert variant_receipt["accepted_rotation_steps"] == (
        variant_receipt["accepted_rigid_rotation_steps"]
        + variant_receipt["accepted_torsion_steps"]
    )
    assert {
        row["rotatable_child_atom_index"]
        for row in variant_receipt["accepted_torsion_moves"]
    } == {2}
    assert float.fromhex(
        variant_receipt["final_receptor_penalty_binary64_hex"]
    ) <= float.fromhex(variant_receipt["baseline_v6_receptor_penalty_binary64_hex"])
    assert float.fromhex(
        variant_receipt["final_combined_penalty_binary64_hex"]
    ) < float.fromhex(variant_receipt["baseline_v6_combined_penalty_binary64_hex"])
    assert (
        variant_receipt["initial_penalty_binary64_hex"]
        == (variant_receipt["initial_combined_penalty_binary64_hex"])
    )
    assert (
        variant_receipt["final_penalty_binary64_hex"]
        == (variant_receipt["final_combined_penalty_binary64_hex"])
    )
    source_combined = refiner._objective(
        proposals[1].coordinates.to(dtype=torch.float64, device="cpu")
    )[2]
    baseline_combined = refiner._objective(
        expected_variant.coordinates.to(dtype=torch.float64, device="cpu")
    )[2]
    assert (
        float.fromhex(variant_receipt["initial_penalty_binary64_hex"])
        == source_combined
    )
    assert (
        float.fromhex(variant_receipt["baseline_v6_combined_penalty_binary64_hex"])
        == baseline_combined
    )
    assert variant_receipt["accepted_rotation_steps_include_torsion"] is True
    assert not torch.equal(
        observed_variant.coordinates,
        expected_variant.coordinates,
    )
    assert torch.equal(
        observed_variant.torsion_angles[[0, 1, 3]],
        expected_variant.torsion_angles[[0, 1, 3]],
    )
    assert observed_variant.torsion_angles[2] != expected_variant.torsion_angles[2]
    outer_payload = dict(variant_receipt)
    outer_sha256 = outer_payload.pop("receipt_sha256")
    assert (
        hashlib.sha256(
            json.dumps(
                outer_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        == outer_sha256
    )
    nested_payload = dict(variant_receipt["baseline_v6_receipt_payload"])
    nested_sha256 = nested_payload.pop("receipt_sha256")
    assert nested_sha256 == variant_receipt["baseline_v6_receipt_sha256"]
    assert (
        hashlib.sha256(
            json.dumps(
                nested_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        == nested_sha256
    )
    for bond in ligand.bonds:
        before = torch.linalg.vector_norm(
            expected_variant.coordinates[bond.atom_i]
            - expected_variant.coordinates[bond.atom_j]
        )
        after = torch.linalg.vector_norm(
            observed_variant.coordinates[bond.atom_i]
            - observed_variant.coordinates[bond.atom_j]
        )
        assert after == pytest.approx(before, abs=1.0e-12)

    rejecting_refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=InteractionAwareTorsionContactConfigV7(
            maximum_torsion_steps=3,
            minimum_selected_final_receptor_penalty=0.0,
            maximum_selected_final_receptor_penalty=1.0e-12,
        ),
    )
    rejected_variant = rejecting_refiner.refine(proposals[1], max_steps=20)
    rejected_receipt = rejecting_refiner.receipts[proposals[1].fingerprint_sha256]

    assert rejected_receipt["torsion_evaluated"] is True
    assert rejected_receipt["torsion_variant_available"] is True
    assert rejected_receipt["torsion_selected"] is False
    assert rejected_receipt["selection_reason"] == (
        "v6_retained_outside_final_receptor_penalty_window"
    )
    assert rejected_receipt["evaluated_torsion_steps"] == 3
    assert len(rejected_receipt["evaluated_torsion_moves"]) == 3
    assert rejected_receipt["accepted_torsion_steps"] == 0
    assert rejected_receipt["accepted_torsion_moves"] == []
    assert float.fromhex(
        rejected_receipt["optimized_combined_penalty_binary64_hex"]
    ) < float.fromhex(rejected_receipt["baseline_v6_combined_penalty_binary64_hex"])
    assert (
        rejected_receipt["final_combined_penalty_binary64_hex"]
        == (rejected_receipt["baseline_v6_combined_penalty_binary64_hex"])
    )
    assert (
        rejected_receipt["initial_penalty_binary64_hex"]
        == (rejected_receipt["initial_combined_penalty_binary64_hex"])
    )
    assert (
        rejected_receipt["final_penalty_binary64_hex"]
        == (rejected_receipt["final_combined_penalty_binary64_hex"])
    )
    assert (
        rejected_receipt["accepted_rotation_steps"]
        == (rejected_receipt["accepted_rigid_rotation_steps"])
    )
    assert torch.equal(rejected_variant.coordinates, expected_variant.coordinates)
    assert torch.equal(
        rejected_variant.torsion_angles,
        expected_variant.torsion_angles,
    )

    pruned_refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="b" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=InteractionAwareTorsionContactConfigV7(
            maximum_torsion_steps=3,
            minimum_selected_final_receptor_penalty=1_000_000.0,
            maximum_selected_final_receptor_penalty=1_000_001.0,
        ),
    )
    pruned_variant = pruned_refiner.refine(proposals[1], max_steps=20)
    pruned_receipt = pruned_refiner.receipts[proposals[1].fingerprint_sha256]

    assert pruned_receipt["torsion_evaluated"] is False
    assert pruned_receipt["torsion_variant_available"] is False
    assert pruned_receipt["torsion_selected"] is False
    assert (
        pruned_receipt["selection_window_reachable_from_baseline_v6_receptor_penalty"]
        is False
    )
    assert pruned_receipt["torsion_evaluation_skip_reason"] == (
        "selection_window_unreachable_under_receptor_nonincrease"
    )
    assert pruned_receipt["objective_evaluation_count"] == 2
    assert pruned_receipt["fixed_objective_evaluation_count"] == 2
    assert pruned_receipt["torsion_trial_objective_evaluation_count"] == 0
    assert pruned_receipt["evaluated_torsion_steps"] == 0
    assert torch.equal(pruned_variant.coordinates, expected_variant.coordinates)
    assert torch.equal(
        pruned_variant.torsion_angles,
        expected_variant.torsion_angles,
    )

    rescue_policy = SourcePairedTorsionRescuePolicy()
    rescue_allocation = SourcePairedTorsionRescueAllocation(
        authenticated_input_receipt_sha256=authority.input_receipt_sha256,
        guidance_context_sha256="8" * 64,
        budget_sha256="9" * 64,
        rescue_policy_sha256=rescue_policy.fingerprint_sha256,
        base_guided_policy_sha256=(rescue_policy.base_guided_policy.fingerprint_sha256),
        candidate_count=64,
        authority_rotor_count=int(
            torch.count_nonzero(authority.search_space.rotatable_mask).item()
        ),
        v3_target_parent_pairs=(),
        rescue_target_parent_pairs=((1, 0),),
    )
    rescue_refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="7" * 64,
        v3_proposal_indices=(),
        source_paired_torsion_rescue_profile=True,
        source_paired_torsion_rescue_allocation=rescue_allocation,
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=InteractionAwareTorsionContactConfigV7(
            maximum_torsion_steps=3,
            minimum_selected_final_receptor_penalty=0.0,
            maximum_selected_final_receptor_penalty=100.0,
        ),
    )
    rescue_parent = rescue_refiner.refine(proposals[0], max_steps=20)
    rescue_variant = rescue_refiner.refine(proposals[1], max_steps=20)
    parent_receipt = rescue_refiner.receipts[proposals[0].fingerprint_sha256]
    rescue_receipt = rescue_refiner.receipts[proposals[1].fingerprint_sha256]

    assert parent_receipt["torsion_evaluated"] is False
    assert parent_receipt["schema_id"].endswith("/1.1.0")
    assert parent_receipt["proposal_torsion_eligibility_lane"] == (
        "ineligible_source_or_other_lane"
    )
    assert parent_receipt["clearance_measurement_evaluated"] is False
    assert parent_receipt["clearance_measurement_unavailable_reason"] == (
        "not_source_paired_rescue_target"
    )
    assert parent_receipt["clearance_radii_policy_sha256"] == ""
    assert (
        parent_receipt["baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"]
        == ""
    )
    assert (
        parent_receipt["optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"] == ""
    )
    assert parent_receipt["optimized_coordinates_sha256"] == ""
    assert parent_receipt["post_coordinates_sha256"] == coordinate_fingerprint(
        rescue_parent.coordinates
    )
    assert rescue_receipt["torsion_evaluated"] is True
    assert rescue_receipt["proposal_torsion_eligibility_lane"] == (
        "source_paired_torsion_rescue_variant"
    )
    assert rescue_receipt["source_paired_parent_proposal_index"] == 0
    assert rescue_receipt["nested_v6_treated_proposal_as_v3_variant"] is False
    assert rescue_receipt["rescue_target_excluded_from_nested_v3_indices"] is True
    assert rescue_receipt["source_paired_torsion_rescue_pairs"] == [
        {"target_proposal_index": 1, "parent_proposal_index": 0}
    ]
    assert rescue_receipt["schema_id"].endswith("/1.1.0")
    assert rescue_receipt["clearance_measurement_evaluated"] is True
    assert rescue_receipt["clearance_measurement_unavailable_reason"] == "none"
    assert (
        rescue_receipt["clearance_radii_policy_sha256"]
        == VdwContactPolicy().fingerprint_sha256
    )
    assert rescue_receipt["clearance_radii_policy_sha256"] == (
        benchmark_contract._SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256
    )
    baseline_state = rescue_refiner._baseline_state_for_experimental_v8(
        proposals[1].fingerprint_sha256
    )
    optimized_state = rescue_refiner._optimized_state_for_experimental_v8(
        proposals[1].fingerprint_sha256
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

    def expected_minimum_gap(coordinates: torch.Tensor) -> float:
        distances = torch.cdist(
            coordinates.to(dtype=torch.float64),
            receptor_coordinates,
        )
        return float(
            torch.min(
                distances - ligand_radii[:, None] - receptor_radii[None, :]
            ).item()
        )

    assert float.fromhex(
        rescue_receipt["baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"]
    ) == pytest.approx(
        expected_minimum_gap(baseline_state.coordinates),
        abs=1.0e-15,
    )
    assert float.fromhex(
        rescue_receipt["optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"]
    ) == pytest.approx(
        expected_minimum_gap(optimized_state.coordinates),
        abs=1.0e-15,
    )
    assert rescue_receipt["optimized_coordinates_sha256"] == coordinate_fingerprint(
        optimized_state.coordinates
    )
    if rescue_receipt["torsion_selected"]:
        assert rescue_receipt["optimized_coordinates_sha256"] == (
            coordinate_fingerprint(rescue_variant.coordinates)
        )
    assert set(rescue_receipt) == (
        benchmark_contract._SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_FIELDS
    )
    assert (
        rescue_receipt["source_paired_torsion_rescue_allocation_sha256"]
        == rescue_allocation.allocation_sha256
    )
    with monkeypatch.context() as pair_bound:
        pair_bound.setattr(
            torsion_contact_refinement,
            "MAX_RECEPTOR_CLEARANCE_PAIR_COUNT",
            0,
        )
        unavailable_refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="7" * 64,
            v3_proposal_indices=(),
            source_paired_torsion_rescue_profile=True,
            source_paired_torsion_rescue_allocation=rescue_allocation,
            v2_config=v2_config,
            v3_config=v3_config,
            clearance_config=clearance_config,
            torsion_config=InteractionAwareTorsionContactConfigV7(
                maximum_torsion_steps=3,
                minimum_selected_final_receptor_penalty=0.0,
                maximum_selected_final_receptor_penalty=100.0,
            ),
        )
        unavailable_refiner.refine(proposals[0], max_steps=20)
        unavailable_variant = unavailable_refiner.refine(
            proposals[1],
            max_steps=20,
        )
        unavailable_receipt = unavailable_refiner.receipts[
            proposals[1].fingerprint_sha256
        ]
    assert torch.equal(unavailable_variant.coordinates, rescue_variant.coordinates)
    assert unavailable_receipt["torsion_selected"] is rescue_receipt["torsion_selected"]
    assert unavailable_receipt["selection_reason"] == rescue_receipt["selection_reason"]
    assert unavailable_receipt["clearance_measurement_evaluated"] is False
    assert unavailable_receipt["clearance_measurement_unavailable_reason"] == (
        "full_cartesian_pair_count_exceeds_fixed_bound"
    )
    assert unavailable_receipt["clearance_radii_policy_sha256"] == ""
    assert (
        unavailable_receipt["baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"]
        == ""
    )
    assert (
        unavailable_receipt["optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"]
        == ""
    )
    assert unavailable_receipt["optimized_coordinates_sha256"] == ""
    assert set(unavailable_receipt) == (
        benchmark_contract._SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_FIELDS
    )
    rescue_payload = dict(rescue_receipt)
    rescue_sha256 = rescue_payload.pop("receipt_sha256")
    assert (
        hashlib.sha256(
            json.dumps(
                rescue_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        == rescue_sha256
    )

    with pytest.raises(TorsionContactRefinementError, match="cross-wired"):
        InteractionAwareTorsionContactEnsembleRefinerV7(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="7" * 64,
            v3_proposal_indices=(1,),
            source_paired_torsion_rescue_profile=True,
            source_paired_torsion_rescue_allocation=rescue_allocation,
        )
    with pytest.raises(TorsionContactRefinementError, match="typed allocation"):
        InteractionAwareTorsionContactEnsembleRefinerV7(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="7" * 64,
            v3_proposal_indices=(),
            source_paired_torsion_rescue_profile=True,
        )


def test_interaction_aware_v8_selects_only_strict_clearance_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receptor = replace(
        _receptor(),
        coordinates=torch.tensor(
            [
                [
                    [1.2307712254983234, 3.9434758050512015, 1.6523553225866865],
                    [8.0, 8.0, 8.0],
                ]
            ],
            dtype=torch.float64,
        ),
    )
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )
    proposals = generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=103,
        ),
        problem=authority.problem,
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
    outside_window = InteractionAwareTorsionContactConfigV7(
        maximum_torsion_steps=3,
        minimum_selected_final_receptor_penalty=0.0,
        maximum_selected_final_receptor_penalty=1.0e-12,
    )
    expected_v7 = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="c" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=outside_window,
    )
    legacy_variant = expected_v7.refine(proposals[1], max_steps=20)
    refiner = InteractionAwareTorsionClearanceEnsembleRefinerV8(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="c" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=outside_window,
    )

    observed = refiner.refine(proposals[1], max_steps=20)
    receipt = refiner.receipts[proposals[1].fingerprint_sha256]

    assert receipt["legacy_v7_selected"] is False
    assert receipt["torsion_variant_available"] is True
    assert receipt["combined_strict_decrease_guard_passed"] is True
    assert receipt["receptor_nonincrease_guard_passed"] is True
    assert receipt["internal_nonincrease_guard_passed"] is True
    assert receipt["minimum_vdw_surface_gap_improvement_guard_passed"] is True
    assert receipt["raw_minimum_distance_nonregression_guard_passed"] is True
    assert receipt["v8_clearance_guard_passed"] is True
    assert receipt["v8_clearance_selected"] is True
    assert receipt["selection_reason"] == ("outside_v7_window_clearance_guard_selected")
    legacy_gap = float.fromhex(
        receipt["legacy_v7_clearance"]["minimum_vdw_surface_gap_angstrom_binary64_hex"]
    )
    optimized_gap = float.fromhex(
        receipt["optimized_clearance"]["minimum_vdw_surface_gap_angstrom_binary64_hex"]
    )
    legacy_distance = float.fromhex(
        receipt["legacy_v7_clearance"]["minimum_distance_angstrom_binary64_hex"]
    )
    final_distance = float.fromhex(
        receipt["final_clearance"]["minimum_distance_angstrom_binary64_hex"]
    )
    assert optimized_gap > legacy_gap
    assert final_distance >= legacy_distance - 1.0e-9
    assert not torch.equal(observed.coordinates, legacy_variant.coordinates)
    for bond in ligand.bonds:
        before = torch.linalg.vector_norm(
            legacy_variant.coordinates[bond.atom_i]
            - legacy_variant.coordinates[bond.atom_j]
        )
        after = torch.linalg.vector_norm(
            observed.coordinates[bond.atom_i] - observed.coordinates[bond.atom_j]
        )
        assert after == pytest.approx(before, abs=1.0e-12)
    outer = dict(receipt)
    outer_sha256 = outer.pop("receipt_sha256")
    assert (
        hashlib.sha256(
            json.dumps(
                outer,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        == outer_sha256
    )
    nested = dict(receipt["legacy_v7_receipt_payload"])
    nested_sha256 = nested.pop("receipt_sha256")
    assert nested_sha256 == receipt["legacy_v7_receipt_sha256"]
    assert (
        hashlib.sha256(
            json.dumps(
                nested,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        == nested_sha256
    )

    duplicate = InteractionAwareTorsionClearanceEnsembleRefinerV8(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="c" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=outside_window,
    )
    duplicate_observed = duplicate.refine(proposals[1], max_steps=20)
    assert torch.equal(duplicate_observed.coordinates, observed.coordinates)
    assert duplicate.receipts[proposals[1].fingerprint_sha256] == receipt

    exposed_receipt = refiner.receipts[proposals[1].fingerprint_sha256]
    exposed_receipt["legacy_v7_receipt_payload"]["schema_id"] = "tampered"
    protected_receipt = refiner.receipts[proposals[1].fingerprint_sha256]
    assert protected_receipt["legacy_v7_receipt_payload"]["schema_id"] != ("tampered")
    assert protected_receipt["receipt_sha256"] == receipt["receipt_sha256"]

    source = proposals[1]
    proposal_fields = {
        definition.name: getattr(source, definition.name)
        for definition in fields(DockingProposal)
        if definition.init
    }
    coordinates, torsion_angles, rotation, translation = (
        value.float()
        for value in (
            source.coordinates,
            source.torsion_angles,
            source.rotation,
            source.translation,
        )
    )
    coordinate_sha256 = coordinate_fingerprint(coordinates)
    proposal_fields.update(
        coordinates=coordinates,
        torsion_angles=torsion_angles,
        rotation=rotation,
        translation=translation,
        coordinate_fingerprint_sha256=coordinate_sha256,
        fingerprint_sha256=_proposal_fingerprint(
            proposal_index=source.proposal_index,
            seed=source.seed,
            torsion_angles=torsion_angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=source.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=(source.search_space_fingerprint_sha256),
            coordinate_fingerprint_sha256=coordinate_sha256,
        ),
    )
    float32_proposal = DockingProposal(**proposal_fields)
    float32_refiner = InteractionAwareTorsionClearanceEnsembleRefinerV8(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=outside_window,
    )
    float32_observed = float32_refiner.refine(float32_proposal, max_steps=20)
    float32_receipt = float32_refiner.receipts[float32_proposal.fingerprint_sha256]
    assert float32_observed.coordinates.dtype == torch.float32
    assert float32_receipt["v8_clearance_selected"] is True
    assert (
        float32_receipt["optimized_objective_recomputed_from_output_coordinates"]
        is True
    )

    retry_refiner = InteractionAwareTorsionClearanceEnsembleRefinerV8(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="f" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=outside_window,
    )
    original_clearance_statistics = retry_refiner._clearance_statistics
    failed_once = False

    def fail_once(coordinates: torch.Tensor):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise TorsionContactRefinementError("fixture post-V7 failure")
        return original_clearance_statistics(coordinates)

    monkeypatch.setattr(retry_refiner, "_clearance_statistics", fail_once)
    with pytest.raises(TorsionContactRefinementError, match="post-V7 failure"):
        retry_refiner.refine(proposals[1], max_steps=20)
    for invalid_max_steps in (True, 20.0):
        with pytest.raises(TorsionContactRefinementError, match="max_steps"):
            retry_refiner.refine(
                proposals[1],
                max_steps=invalid_max_steps,
            )
    with pytest.raises(TorsionContactRefinementError, match="original max_steps"):
        retry_refiner.refine(proposals[1], max_steps=0)
    retried = retry_refiner.refine(proposals[1], max_steps=20)
    assert retried.coordinate_fingerprint_sha256 == (
        observed.coordinate_fingerprint_sha256
    )

    legacy_window = InteractionAwareTorsionContactConfigV7(
        maximum_torsion_steps=3,
        minimum_selected_final_receptor_penalty=0.0,
        maximum_selected_final_receptor_penalty=100.0,
    )
    expected_selected_v7 = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="d" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=legacy_window,
    ).refine(proposals[1], max_steps=20)
    retaining_v8 = InteractionAwareTorsionClearanceEnsembleRefinerV8(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="d" * 64,
        v3_proposal_indices=(1,),
        v2_config=v2_config,
        v3_config=v3_config,
        clearance_config=clearance_config,
        torsion_config=legacy_window,
    )
    retained = retaining_v8.refine(proposals[1], max_steps=20)
    retained_receipt = retaining_v8.receipts[proposals[1].fingerprint_sha256]
    assert retained_receipt["legacy_v7_selected"] is True
    assert retained_receipt["v8_clearance_selected"] is False
    assert retained_receipt["selection_reason"] == (
        "legacy_v7_window_selection_retained"
    )
    assert torch.equal(retained.coordinates, expected_selected_v7.coordinates)
    assert torch.equal(retained.torsion_angles, expected_selected_v7.torsion_angles)


@pytest.mark.parametrize("tolerance", (0.0, -1.0e-9, 1.0e-5, float("inf")))
def test_interaction_aware_v8_rejects_invalid_clearance_tolerance(
    tolerance: float,
) -> None:
    with pytest.raises(TorsionContactRefinementError, match="tolerance"):
        InteractionAwareTorsionClearanceConfigV8(clearance_tolerance_angstrom=tolerance)


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    ((-1.0, 4.0), (4.0, 4.0), (5.0, 4.0), (0.0, float("inf"))),
)
def test_interaction_aware_v7_rejects_invalid_selection_window(
    minimum: float,
    maximum: float,
) -> None:
    with pytest.raises(TorsionContactRefinementError, match="selection window"):
        InteractionAwareTorsionContactConfigV7(
            minimum_selected_final_receptor_penalty=minimum,
            maximum_selected_final_receptor_penalty=maximum,
        )


@pytest.mark.parametrize(
    "indices",
    ((1, 1), (1, 0), (True,), (128,)),
)
def test_interaction_aware_v4_rejects_ambiguous_lane_indices(
    indices: tuple[int, ...],
) -> None:
    receptor = _receptor()
    ligand = _ligand()
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        _pocket(),
    )

    with pytest.raises(ClashReliefRefinementError, match="proposal indices"):
        InteractionAwareRigidEnsembleRefinerV4(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="8" * 64,
            v3_proposal_indices=indices,
        )


def test_element_aware_ligand_pair_capacity_is_enforced() -> None:
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        _pocket(),
        contact_policy=VdwContactPolicy(max_ligand_pair_checks=0),
    )
    with pytest.raises(ElementAwareValidityError, match="ligand pair capacity"):
        authority.validity_context.evaluate(_baseline(authority))
