from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

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
    ElementAwarePoseValidityContext,
    ElementAwareValidityError,
    InteractionAwareRigidConfigV3,
    InteractionAwareRigidRefinerV2,
    InteractionAwareRigidRefinerV3,
    UnsupportedVdwElementError,
    PocketDefinition,
    ReceptorClashReliefRefiner,
    VdwContactPolicy,
    build_element_aware_authenticated_known_pocket_docking_problem,
    element_aware_authority_document,
    generate_bounded_docking_proposals,
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
        isinstance(value, (int, float))
        for value in result.measurements.values()
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
    assert result.measurements[
        "element_vdw_receptor_severe_overlap_count"
    ] >= 1
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
    candidates = result.measurements[
        "element_vdw_receptor_candidate_pair_count"
    ]
    cartesian = result.measurements[
        "element_vdw_receptor_full_cartesian_pair_count"
    ]
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
    assert float.fromhex(
        receipt["total_rotation_path_radians_binary64_hex"]
    ) <= config.maximum_total_rotation_radians
    assert float.fromhex(
        receipt["final_centroid_offset_angstrom_binary64_hex"]
    ) <= config.maximum_centroid_offset_angstrom
    assert refined.refiner_id == refiner.refiner_id
    assert refined.parent_proposal_fingerprint_sha256 == proposal.fingerprint_sha256


def test_element_aware_ligand_pair_capacity_is_enforced() -> None:
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        _pocket(),
        contact_policy=VdwContactPolicy(max_ligand_pair_checks=0),
    )
    with pytest.raises(ElementAwareValidityError, match="ligand pair capacity"):
        authority.validity_context.evaluate(_baseline(authority))
