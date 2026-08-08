from __future__ import annotations

from dataclasses import replace
import hashlib
from importlib import resources

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    CURRENT_V7_FIXED64_PROFILE_ID,
    EXTERNAL_AUTHORITY_BLOCKERS,
    DockingScope,
    PocketDefinition,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-pipeline-fixture",
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
        system_id="standalone-pipeline-ligand",
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
        provenance=_provenance("standalone-ligand-source", "a" * 64),
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
        system_id="standalone-pipeline-receptor",
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
        provenance=_provenance("standalone-receptor-source", "b" * 64),
    )


def _pocket() -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="standalone-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )


def _request(*, ligand: AllAtomSystem | None = None) -> DockingPipelineRequestV1:
    return DockingPipelineRequestV1(
        receptor_system=_receptor(),
        ligand_system=ligand or _ligand(),
        pocket=_pocket(),
        seed=4301,
        profile=DockingPipelineProfileV1.synthetic_test(
            candidate_count=4,
            top_k=2,
            max_torsions=1,
            max_refinement_steps=1,
        ),
    )


def test_current_v7_profile_is_exact_fixed64() -> None:
    profile = DockingPipelineProfileV1()

    assert profile.profile_id == CURRENT_V7_FIXED64_PROFILE_ID
    assert profile.candidate_count == 64
    assert profile.top_k == 5
    assert profile.max_refinement_steps == 24
    assert profile.to_dict()["clearance_shadow_selection_enabled"] is False

    with pytest.raises(DockingPipelineError, match="fixed64 profile was changed"):
        DockingPipelineProfileV1(candidate_count=63)


def test_pipeline_is_deterministic_failure_complete_and_claim_blocked() -> None:
    pipeline = DockingPipeline()
    first = pipeline.run(_request())
    second = pipeline.run(_request())

    assert first.receipt_sha256 == second.receipt_sha256
    assert len(first.candidates) == 4
    assert first.success_count + first.failure_count == 4
    assert tuple(row.proposal_index for row in first.candidates) == tuple(range(4))
    assert all(
        row.geometric_admission_status
        == "not_enabled_in_current_v7_baseline"
        for row in first.candidates
    )
    assert all(code in first.blockers for code in EXTERNAL_AUTHORITY_BLOCKERS)
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
    assert document["external_reservation_requested"] is False
    assert document["historical_execution_authorized"] is False
    assert document["fresh_holdout_execution_authorized"] is False
    assert document["product_execution_authorized"] is False
    assert document["public_or_scientific_claim_authorized"] is False
    assert document["claim_safe"] is False
    for row in first.candidates:
        if row.status == "success":
            assert row.scorer_terms is not None
            assert row.refinement_receipt is not None
            assert row.pose_validity is not None
        else:
            assert row.error_code


def test_pipeline_rejects_missing_prepared_partial_charge() -> None:
    ligand = _ligand()
    atoms = list(ligand.atoms)
    atoms[0] = replace(atoms[0], partial_charge_e=None)
    incomplete = replace(ligand, atoms=tuple(atoms))

    with pytest.raises(DockingPipelineError, match="lacks explicit partial charges"):
        DockingPipeline().run(_request(ligand=incomplete))


def test_pipeline_cannot_be_used_as_production_authority() -> None:
    with pytest.raises(DockingPipelineError, match="remains test-only"):
        DockingPipelineRequestV1(
            receptor_system=_receptor(),
            ligand_system=_ligand(),
            pocket=_pocket(),
            seed=4301,
            test_only=False,
        )
