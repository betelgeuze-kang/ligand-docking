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
    ChemistryPoseScorerV1,
    DockingBudget,
    DockingScope,
    PocketDefinition,
    ScorerV1Config,
    ScorerBackend,
    ScorerBackendOptions,
    ScorerV1Error,
    build_guided_placement_context,
    build_element_aware_authenticated_known_pocket_docking_problem,
    generate_pocket_centered_docking_proposals,
    run_authenticated_pocket_placement_search,
    run_authenticated_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint  # noqa: E402
from betelgeuze_engine_v2.docking.proposals import (  # noqa: E402
    DockingProposal,
    _proposal_fingerprint,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="scorer-v1-fixture",
        parser_version="1.0.0",
    )


def _ligand(*, complete_charges: bool = True) -> AllAtomSystem:
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
        system_id="scorer-v1-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=(
                    charges[index] if complete_charges or index != 0 else None
                ),
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
        provenance=_provenance("scorer-v1-ligand-source", "a" * 64),
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
        system_id="scorer-v1-receptor",
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
        provenance=_provenance("scorer-v1-receptor-source", "b" * 64),
    )


def _authority(ligand: AllAtomSystem | None = None):
    receptor = _receptor()
    ligand = ligand or _ligand()
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="scorer-v1-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=4.0,
    )
    return authority, receptor, ligand


def _budget(seed: int = 1201) -> DockingBudget:
    return DockingBudget(
        candidate_count=6,
        top_k=3,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=seed,
    )


def _scorer(authority, receptor, ligand, config=None):
    return ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
        config=config,
    )


class _OneFailureScorer(ChemistryPoseScorerV1):
    def _score_terms_python(self, proposal):
        if proposal.proposal_index == 0:
            raise ScorerV1Error("intentional bounded scorer failure")
        return super()._score_terms_python(proposal)


def _isolated_config(**selected_weights) -> ScorerV1Config:
    values = {
        "typed_vdw_weight": 0.0,
        "electrostatics_weight": 0.0,
        "directional_hbond_weight": 0.0,
        "hydrophobic_contact_weight": 0.0,
        "desolvation_weight": 0.0,
        "torsion_energy_weight": 0.0,
        "ligand_strain_weight": 0.0,
        "weak_pocket_prior_weight": 0.0,
    }
    values.update(selected_weights)
    return ScorerV1Config(**values)


def _rotor_ligand() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="scorer-v1-rotor-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
                partial_charge_e=0.0,
            )
            for index in range(4)
        ),
        bonds=tuple(
            Bond(index=index, atom_i=index, atom_j=index + 1) for index in range(3)
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
            [[[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [2.8, 0.8, 0.0], [4.0, 1.0, 0.9]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("scorer-v1-rotor-source", "9" * 64),
    )


def _interaction_proposal(authority, ligand):
    proposal = generate_pocket_centered_docking_proposals(
        authority,
        _budget(),
    )[0][0]
    return proposal.with_refined_coordinates(
        ligand.coordinates[0],
        refiner_id="scorer-v1-interaction-fixture",
        refiner_version="1.0.0",
    )


def test_all_eight_terms_are_deterministic_exact_and_auditable() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    proposal = _interaction_proposal(authority, ligand)
    first = scorer.score_terms(proposal)
    second = scorer.score_terms(proposal)

    assert first.receipt_sha256 == second.receipt_sha256
    term_names = (
        "typed_vdw",
        "electrostatics",
        "directional_hbond",
        "hydrophobic_contact",
        "desolvation_proxy",
        "torsion_energy",
        "ligand_strain",
        "weak_pocket_prior",
    )
    assert first.total_score == pytest.approx(
        sum(float(getattr(first, name)) for name in term_names),
        abs=1.0e-12,
    )
    assert first.hbond_count >= 1
    assert first.directional_hbond < 0.0
    assert first.hydrophobic_contact_count >= 1
    assert first.hydrophobic_contact < 0.0
    assert scorer.score(proposal) == pytest.approx(first.total_score, abs=1.0e-12)
    document = scorer.qualification_document()
    assert document["affinity_estimate"] is False
    assert document["free_energy_estimate"] is False
    assert document["claim_safe"] is False
    assert len(scorer.context.fingerprint_sha256) == 64


def test_python_reference_batch_matches_single_and_binds_backend_receipt() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    first = _interaction_proposal(authority, ligand)
    second = first.with_refined_coordinates(
        first.coordinates + torch.tensor([0.25, 0.0, 0.0], dtype=torch.float64),
        refiner_id="scorer-v1-batch-fixture",
        refiner_version="1.0.0",
    )

    batch = scorer.score_terms_batch((first, second))

    assert scorer.backend is ScorerBackend.PYTHON_REFERENCE
    assert len(batch) == 2
    assert batch[0].receipt_sha256 == scorer.score_terms(first).receipt_sha256
    assert batch[1].receipt_sha256 == scorer.score_terms(second).receipt_sha256
    assert all(
        row.backend_receipt_sha256 == scorer.backend_receipt_sha256
        for row in batch
    )
    assert scorer.qualification_document()["backend_receipt"]["backend"] == (
        "python_reference"
    )


def test_batch_capacity_and_missing_required_native_receipt_fail_closed() -> None:
    authority, receptor, ligand = _authority()
    scorer = ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
        backend_options=ScorerBackendOptions(max_batch_size=1),
    )
    proposal = _interaction_proposal(authority, ligand)
    with pytest.raises(ScorerV1Error, match="batch capacity"):
        scorer.score_terms_batch((proposal, proposal))

    with pytest.raises(ScorerV1Error, match=r"C\+\+/HIP scorer backend"):
        ChemistryPoseScorerV1(
            authority,
            receptor,
            ligand,
            implementation_source_sha256="e" * 64,
            backend=ScorerBackend.CPP_HIP_REQUIRED,
        )


def test_rust_cpu_batch_matches_python_reference_when_installed() -> None:
    pytest.importorskip("betelgeuze_engine_v2_native")
    authority, receptor, ligand = _authority()
    python_scorer = _scorer(authority, receptor, ligand)
    rust_scorer = ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
        backend=ScorerBackend.RUST_CPU_REQUIRED,
        backend_options=ScorerBackendOptions(thread_count=2),
    )
    first = _interaction_proposal(authority, ligand)
    second = first.with_refined_coordinates(
        first.coordinates + torch.tensor([0.25, 0.0, 0.0], dtype=torch.float64),
        refiner_id="scorer-v1-native-batch-fixture",
        refiner_version="1.0.0",
    )

    reference = python_scorer.score_terms_batch((first, second))
    observed = rust_scorer.score_terms_batch((first, second))

    assert rust_scorer.backend_receipt.extension_sha256
    assert rust_scorer.backend_receipt.cargo_lock_sha256
    for expected, actual in zip(reference, observed, strict=True):
        assert actual.receptor_candidate_pair_count == (
            expected.receptor_candidate_pair_count
        )
        assert actual.ligand_pair_count == expected.ligand_pair_count
        assert actual.hbond_count == expected.hbond_count
        assert actual.hydrophobic_contact_count == (
            expected.hydrophobic_contact_count
        )
        assert actual.buried_polar_count == expected.buried_polar_count
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
        ):
            assert float(getattr(actual, name)) == pytest.approx(
                float(getattr(expected, name)), rel=1.0e-12, abs=1.0e-12
            )


def test_rust_cpu_preserves_candidate_local_typed_failure() -> None:
    pytest.importorskip("betelgeuze_engine_v2_native")
    authority, receptor, ligand = _authority(_rotor_ligand())
    scorer = ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
        backend=ScorerBackend.RUST_CPU_REQUIRED,
        backend_options=ScorerBackendOptions(thread_count=2),
    )
    valid = _interaction_proposal(authority, ligand)
    assert scorer._rotor_quads
    degenerate_coordinates = valid.coordinates.clone()
    for offset, atom_index in enumerate(scorer._rotor_quads[0]):
        degenerate_coordinates[atom_index] = torch.tensor(
            [float(offset), 0.0, 0.0], dtype=torch.float64
        )
    degenerate = valid.with_refined_coordinates(
        degenerate_coordinates,
        refiner_id="scorer-v1-degenerate-native-fixture",
        refiner_version="1.0.0",
    )

    outcomes = scorer.score_batch((valid, degenerate))

    assert outcomes[0].error is None
    assert outcomes[0].evidence is not None
    assert outcomes[1].score is None
    assert outcomes[1].error is not None
    assert getattr(outcomes[1].error, "public_error_code") == (
        "scorer_v1_native_degenerate_rotor_geometry"
    )


def test_rust_cpu_64_candidate_rank_and_top5_match_reference() -> None:
    pytest.importorskip("betelgeuze_engine_v2_native")
    authority, receptor, ligand = _authority()
    python_scorer = _scorer(authority, receptor, ligand)
    rust_scorer = ChemistryPoseScorerV1(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="e" * 64,
        backend=ScorerBackend.RUST_CPU_REQUIRED,
        backend_options=ScorerBackendOptions(thread_count=2),
    )
    budget = DockingBudget(
        candidate_count=64,
        top_k=5,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=1241,
    )
    guided_context = build_guided_placement_context(authority, receptor, ligand)

    reference = run_authenticated_scorer_v1_guided_search(
        authority,
        budget,
        python_scorer,
        guided_context,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )
    observed = run_authenticated_scorer_v1_guided_search(
        authority,
        budget,
        rust_scorer,
        guided_context,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )

    assert len(reference.rows) == len(observed.rows) == 64
    reference_top = (
        reference.guided_search_result.authenticated_search_result.search_result.top_rows
    )
    observed_top = (
        observed.guided_search_result.authenticated_search_result.search_result.top_rows
    )
    assert [row.candidate_id for row in reference_top] == [
        row.candidate_id for row in observed_top
    ]
    for expected, actual in zip(reference.rows, observed.rows, strict=True):
        assert expected.search_status == actual.search_status
        assert expected.error_code == actual.error_code
        if expected.score is None:
            assert actual.score is None
        else:
            assert actual.score == pytest.approx(
                expected.score,
                rel=1.0e-12,
                abs=1.0e-12,
            )


def test_electrostatics_responds_to_opposite_charge_distance() -> None:
    authority, receptor, ligand = _authority()
    config = _isolated_config(electrostatics_weight=0.35)
    scorer = _scorer(authority, receptor, ligand, config)
    near = _interaction_proposal(authority, ligand)
    far = near.with_refined_coordinates(
        near.coordinates + torch.tensor([4.0, 0.0, 0.0], dtype=torch.float64),
        refiner_id="scorer-v1-far-charge-fixture",
        refiner_version="1.0.0",
    )
    assert scorer.score_terms(near).electrostatics != pytest.approx(
        scorer.score_terms(far).electrostatics,
        abs=1.0e-12,
    )


def test_directional_hbond_requires_linear_donor_hydrogen_acceptor_geometry() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(
        authority,
        receptor,
        ligand,
        _isolated_config(directional_hbond_weight=1.0),
    )
    linear = _interaction_proposal(authority, ligand)
    bent_coordinates = linear.coordinates.clone()
    bent_coordinates[2] = torch.tensor([0.0, 1.0, 0.0], dtype=torch.float64)
    bent = linear.with_refined_coordinates(
        bent_coordinates,
        refiner_id="scorer-v1-bent-hbond-fixture",
        refiner_version="1.0.0",
    )
    assert scorer.score_terms(linear).directional_hbond < (
        scorer.score_terms(bent).directional_hbond
    )


def test_vdw_strain_and_weak_pocket_terms_respond_to_geometry() -> None:
    authority, receptor, ligand = _authority()
    proposal = _interaction_proposal(authority, ligand)

    vdw_scorer = _scorer(
        authority,
        receptor,
        ligand,
        _isolated_config(typed_vdw_weight=1.0),
    )
    overlap_coordinates = proposal.coordinates.clone()
    overlap_coordinates[0] = authority.validity_context.receptor_coordinates[3]
    overlap = proposal.with_refined_coordinates(
        overlap_coordinates,
        refiner_id="scorer-v1-vdw-overlap-fixture",
        refiner_version="1.0.0",
    )
    clear = proposal.with_refined_coordinates(
        proposal.coordinates + torch.tensor([20.0, 0.0, 0.0], dtype=torch.float64),
        refiner_id="scorer-v1-vdw-clear-fixture",
        refiner_version="1.0.0",
    )
    assert vdw_scorer.score_terms(overlap).typed_vdw > (
        vdw_scorer.score_terms(clear).typed_vdw
    )

    strain_scorer = _scorer(
        authority,
        receptor,
        ligand,
        _isolated_config(ligand_strain_weight=1.0),
    )
    strained_coordinates = proposal.coordinates.clone()
    strained_coordinates[2] = strained_coordinates[3] + torch.tensor(
        [0.05, 0.0, 0.0], dtype=torch.float64
    )
    strained = proposal.with_refined_coordinates(
        strained_coordinates,
        refiner_id="scorer-v1-strain-fixture",
        refiner_version="1.0.0",
    )
    assert strain_scorer.score_terms(strained).ligand_strain > (
        strain_scorer.score_terms(proposal).ligand_strain
    )

    pocket_scorer = _scorer(
        authority,
        receptor,
        ligand,
        _isolated_config(weak_pocket_prior_weight=1.0),
    )
    assert pocket_scorer.score_terms(clear).weak_pocket_prior > (
        pocket_scorer.score_terms(proposal).weak_pocket_prior
    )


def test_periodic_torsion_energy_responds_to_sampled_rotor_angle() -> None:
    ligand = _rotor_ligand()
    authority, receptor, ligand = _authority(ligand)
    assert authority.search_space.torsion_count == 1
    scorer = _scorer(
        authority,
        receptor,
        ligand,
        _isolated_config(torsion_energy_weight=1.0),
    )
    proposals = generate_pocket_centered_docking_proposals(
        authority,
        _budget(1223),
    )[0]
    assert scorer.score_terms(proposals[0]).torsion_energy == pytest.approx(0.0)
    assert scorer.score_terms(proposals[1]).torsion_energy > 0.0

    first_refined = proposals[0].with_refined_coordinates(
        ligand.coordinates[0],
        refiner_id="scorer-v1-coordinate-torsion-fixture",
        refiner_version="1.0.0",
    )
    second_refined = proposals[1].with_refined_coordinates(
        ligand.coordinates[0],
        refiner_id="scorer-v1-coordinate-torsion-fixture",
        refiner_version="1.0.0",
    )
    assert scorer.score_terms(first_refined).torsion_energy == pytest.approx(
        scorer.score_terms(second_refined).torsion_energy,
        abs=1.0e-12,
    )


def test_config_rejects_interaction_ranges_beyond_pair_cutoff() -> None:
    with pytest.raises(ScorerV1Error, match="must cover"):
        ScorerV1Config(
            pair_cutoff_angstrom=3.0,
            polar_burial_distance_angstrom=4.5,
        )


def test_missing_or_nonconserving_partial_charge_fails_closed() -> None:
    ligand = _ligand(complete_charges=False)
    authority, receptor, ligand = _authority(ligand)
    with pytest.raises(ScorerV1Error, match="complete finite partial charges"):
        _scorer(authority, receptor, ligand)

    nonconserving = _ligand().with_coordinates(
        _ligand().coordinates,
        operation="scorer-v1-nonconserving-fixture",
    )
    atoms = list(nonconserving.atoms)
    atoms[0] = replace(atoms[0], partial_charge_e=0.25)
    nonconserving = replace(nonconserving, atoms=tuple(atoms))
    authority, receptor, nonconserving = _authority(nonconserving)
    with pytest.raises(ScorerV1Error, match="do not conserve"):
        _scorer(authority, receptor, nonconserving)


def test_pair_work_bounds_fail_closed() -> None:
    authority, receptor, ligand = _authority()
    proposal = _interaction_proposal(authority, ligand)
    receptor_bounded = _scorer(
        authority,
        receptor,
        ligand,
        ScorerV1Config(max_receptor_candidate_pairs=1),
    )
    with pytest.raises(ScorerV1Error, match="candidate-pair capacity"):
        receptor_bounded.score_terms(proposal)

    with pytest.raises(ScorerV1Error, match="ligand pair capacity"):
        _scorer(
            authority,
            receptor,
            ligand,
            ScorerV1Config(max_ligand_pair_checks=1),
        )


def test_terms_receipt_and_source_crosswires_fail_closed() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    terms = scorer.score_terms(_interaction_proposal(authority, ligand))
    object.__setattr__(terms, "desolvation_proxy", terms.desolvation_proxy + 1.0)
    with pytest.raises(ScorerV1Error, match="terms changed"):
        _ = terms.receipt_sha256

    moved = ligand.with_coordinates(
        ligand.coordinates + 0.1,
        operation="scorer-v1-crosswire-test",
    )
    with pytest.raises(ScorerV1Error, match="systems are cross-wired"):
        _scorer(authority, receptor, moved)


def test_config_changes_component_and_term_identity() -> None:
    authority, receptor, ligand = _authority()
    first = _scorer(
        authority,
        receptor,
        ligand,
        ScorerV1Config(weak_pocket_prior_weight=0.01),
    )
    second = _scorer(
        authority,
        receptor,
        ligand,
        ScorerV1Config(weak_pocket_prior_weight=0.2),
    )
    proposal = generate_pocket_centered_docking_proposals(
        authority,
        _budget(1207),
    )[0][1]
    assert first.config.fingerprint_sha256 != second.config.fingerprint_sha256
    assert first.contract_fingerprint_sha256 != second.contract_fingerprint_sha256
    assert first.score_terms(proposal).weak_pocket_prior != (
        second.score_terms(proposal).weak_pocket_prior
    )
    with pytest.raises(AttributeError):
        first.config_fingerprint_sha256 = "0" * 64


def test_truncated_but_internally_consistent_proposal_fails_closed() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    source = _interaction_proposal(authority, ligand)
    coordinates = source.coordinates[:-1]
    torsion_angles = source.torsion_angles[:-1]
    coordinate_sha256 = coordinate_fingerprint(coordinates)
    forged = DockingProposal(
        candidate_id=source.candidate_id,
        coordinates=coordinates,
        torsion_angles=torsion_angles,
        rotation=source.rotation,
        translation=source.translation,
        proposal_index=source.proposal_index,
        seed=source.seed,
        fingerprint_sha256=_proposal_fingerprint(
            proposal_index=source.proposal_index,
            seed=source.seed,
            torsion_angles=torsion_angles,
            rotation=source.rotation,
            translation=source.translation,
            problem_fingerprint_sha256=source.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=source.search_space_fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_sha256,
            parent_proposal_fingerprint_sha256=(
                source.parent_proposal_fingerprint_sha256
            ),
            refiner_id=source.refiner_id,
            refiner_version=source.refiner_version,
            refinement_receipt_sha256=source.refinement_receipt_sha256,
        ),
        problem_fingerprint_sha256=source.problem_fingerprint_sha256,
        search_space_fingerprint_sha256=source.search_space_fingerprint_sha256,
        coordinate_fingerprint_sha256=coordinate_sha256,
        parent_proposal_fingerprint_sha256=(source.parent_proposal_fingerprint_sha256),
        refiner_id=source.refiner_id,
        refiner_version=source.refiner_version,
        refinement_receipt_sha256=source.refinement_receipt_sha256,
    )
    forged.assert_integrity()
    with pytest.raises(ScorerV1Error, match="atom count is cross-wired"):
        scorer.score_terms(forged)


def test_failure_complete_search_accepts_scorer_v1_contract() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    result = run_authenticated_pocket_placement_search(
        authority,
        _budget(1213),
        scorer,
        diversity_rmsd_angstrom=0.0,
    )
    search = result.authenticated_search_result.search_result
    assert len(search.rows) == _budget().candidate_count
    assert search.scorer_id == scorer.scorer_id
    assert search.score_descriptor.calibrated is False
    assert "scorer_not_validated_for_docking_ranking" in search.blockers


def test_ligand_strain_detects_internal_nonbonded_distortion() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    reference = _interaction_proposal(authority, ligand)
    distorted_coordinates = reference.coordinates.clone()
    distorted_coordinates[3] += torch.tensor(
        [1.0, 0.3, 0.0],
        dtype=torch.float64,
    )
    distorted = reference.with_refined_coordinates(
        distorted_coordinates,
        refiner_id="scorer-v1-strain-fixture",
        refiner_version="1.0.0",
    )

    assert scorer.score_terms(reference).ligand_strain == pytest.approx(
        0.0,
        abs=1.0e-12,
    )
    assert scorer.score_terms(distorted).ligand_strain > 0.0


def test_guided_search_retains_exact_terms_for_every_success_row() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    guided_context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    result = run_authenticated_scorer_v1_guided_search(
        authority,
        _budget(1217),
        scorer,
        guided_context,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )

    assert len(result.rows) == _budget().candidate_count
    assert result.success_count + result.failure_count == len(result.rows)
    assert result.to_dict()["term_decomposition_retained"] is True
    assert result.to_dict()["failure_rows_retained"] is True
    for row in result.rows:
        assert len(row.receipt_sha256) == 64
        if row.search_status == "success":
            assert row.terms is not None
            assert row.score == pytest.approx(row.terms.total_score, abs=0.0)
        else:
            assert row.terms is None


def test_guided_search_result_rejects_forged_term_configuration() -> None:
    authority, receptor, ligand = _authority()
    scorer = _scorer(authority, receptor, ligand)
    result = run_authenticated_scorer_v1_guided_search(
        authority,
        _budget(1223),
        scorer,
        build_guided_placement_context(authority, receptor, ligand),
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )
    row_index = next(
        index for index, row in enumerate(result.rows) if row.terms is not None
    )
    source_row = result.rows[row_index]
    assert source_row.terms is not None
    forged_terms = replace(
        source_row.terms,
        config_fingerprint_sha256="0" * 64,
    )
    forged_rows = list(result.rows)
    forged_rows[row_index] = replace(
        source_row,
        terms=forged_terms,
    )

    with pytest.raises(ScorerV1Error, match="terms are cross-wired"):
        replace(result, rows=tuple(forged_rows))

    offset_terms = replace(
        source_row.terms,
        typed_vdw=source_row.terms.typed_vdw + 1.0,
        electrostatics=source_row.terms.electrostatics - 1.0,
    )
    offset_rows = list(result.rows)
    offset_rows[row_index] = replace(source_row, terms=offset_terms)
    with pytest.raises(ScorerV1Error, match="not the scorer output"):
        replace(result, rows=tuple(offset_rows))


def test_guided_search_retains_scorer_failures_and_rejects_result_crosswire() -> None:
    authority, receptor, ligand = _authority()
    scorer = _OneFailureScorer(
        authority,
        receptor,
        ligand,
        implementation_source_sha256="f" * 64,
    )
    result = run_authenticated_scorer_v1_guided_search(
        authority,
        _budget(1229),
        scorer,
        build_guided_placement_context(authority, receptor, ligand),
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )

    failures = [row for row in result.rows if row.search_status == "failure"]
    assert failures
    assert result.success_count + result.failure_count == _budget().candidate_count
    assert all(row.score is None and row.terms is None for row in failures)
    assert all(row.error_code for row in failures)

    with pytest.raises(ScorerV1Error, match="lowercase SHA-256"):
        replace(result, scorer_config_fingerprint_sha256="0" * 63)
