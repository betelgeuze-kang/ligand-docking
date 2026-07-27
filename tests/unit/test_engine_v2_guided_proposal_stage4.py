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
    GUIDED_MODES,
    UNIFORM_FALLBACK_MODE,
    DockingAuthorityError,
    DockingBudget,
    DockingScoreDescriptor,
    DockingScope,
    GuidedPlacementPolicy,
    PocketDefinition,
    ScoreDirection,
    build_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    generate_guided_docking_proposals,
    generate_pocket_centered_docking_proposals,
    run_authenticated_guided_placement_search,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="guided-stage4-fixture",
        parser_version="1.0.0",
    )


def _atoms(
    elements: tuple[str, ...],
    *,
    charges: dict[int, int] | None = None,
    aromatic: set[int] | None = None,
) -> tuple[Atom, ...]:
    atomic_numbers = {
        "H": 1,
        "C": 6,
        "N": 7,
        "O": 8,
    }
    charges = charges or {}
    aromatic = aromatic or set()
    return tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_numbers[element],
            residue_index=0,
            formal_charge=charges.get(index, 0),
            aromatic=index in aromatic,
        )
        for index, element in enumerate(elements)
    )


def _ligand() -> AllAtomSystem:
    root = 3.0**0.5 / 2.0
    coordinates = torch.tensor(
        [
            [1.4, 0.0, 0.0],
            [0.7, 1.4 * root, 0.0],
            [-0.7, 1.4 * root, 0.0],
            [-1.4, 0.0, 0.0],
            [-0.7, -1.4 * root, 0.0],
            [0.7, -1.4 * root, 0.0],
            [2.7, 0.0, 0.0],
            [3.5, 0.5, 0.0],
            [-2.7, 0.0, 0.0],
        ],
        dtype=torch.float64,
    )
    ring_bonds = tuple(
        Bond(
            index=index,
            atom_i=min(index, (index + 1) % 6),
            atom_j=max(index, (index + 1) % 6),
            order=1.5,
            aromatic=True,
        )
        for index in range(6)
    )
    return AllAtomSystem(
        system_id="guided-stage4-ligand",
        atoms=_atoms(
            ("C", "C", "C", "C", "C", "C", "N", "H", "O"),
            charges={6: 1, 8: -1},
            aromatic=set(range(6)),
        ),
        bonds=(
            *ring_bonds,
            Bond(index=6, atom_i=0, atom_j=6, order=1.0),
            Bond(index=7, atom_i=6, atom_j=7, order=1.0),
            Bond(index=8, atom_i=3, atom_j=8, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(9)),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=coordinates.unsqueeze(0),
        provenance=_provenance("guided-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    root = 3.0**0.5 / 2.0
    ring = [
        [6.4, 0.0, 0.0],
        [5.7, 1.4 * root, 0.0],
        [4.3, 1.4 * root, 0.0],
        [3.6, 0.0, 0.0],
        [4.3, -1.4 * root, 0.0],
        [5.7, -1.4 * root, 0.0],
    ]
    coordinates = torch.tensor(
        [
            *ring,
            [-4.0, 0.0, 0.0],
            [4.0, 3.0, 0.5],
            [4.8, 3.4, 0.5],
            [0.0, 4.0, -0.5],
            [0.0, -4.0, 0.5],
            [0.0, -4.8, 0.5],
            [2.5, 2.5, 2.0],
        ],
        dtype=torch.float64,
    )
    ring_bonds = tuple(
        Bond(
            index=index,
            atom_i=min(index, (index + 1) % 6),
            atom_j=max(index, (index + 1) % 6),
            order=1.5,
            aromatic=True,
        )
        for index in range(6)
    )
    return AllAtomSystem(
        system_id="guided-stage4-receptor",
        atoms=_atoms(
            (
                "C",
                "C",
                "C",
                "C",
                "C",
                "C",
                "O",
                "N",
                "H",
                "O",
                "O",
                "H",
                "C",
            ),
            charges={6: -1, 7: 1},
            aromatic=set(range(6)),
        ),
        bonds=(
            *ring_bonds,
            Bond(index=6, atom_i=7, atom_j=8, order=1.0),
            Bond(index=7, atom_i=10, atom_j=11, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(13)),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=coordinates.unsqueeze(0),
        provenance=_provenance("guided-receptor-source", "b" * 64),
    )


def _authority():
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="guided-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    receptor = _receptor()
    ligand = _ligand()
    authority = build_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=4.0,
    )
    return authority, receptor, ligand


def _budget(seed: int = 901) -> DockingBudget:
    return DockingBudget(
        candidate_count=8,
        top_k=3,
        max_torsions=0,
        translation_radius_angstrom=9.0,
        seed=seed,
    )


class _Scorer:
    scorer_id = "guided-stage4-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "e" * 64
    config_fingerprint_sha256 = "f" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="guided-stage4-test-score",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_only",
        calibrated=False,
    )

    def __init__(self, problem_fingerprint: str) -> None:
        self.problem_fingerprint_sha256 = problem_fingerprint

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def _mode_proposal(proposals, receipt, mode: str):
    index = receipt.proposal_modes.index(mode)
    return proposals[index]


def test_guided_modes_are_deterministic_and_uniform_fallback_is_exact() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    first, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
    )
    second, second_receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
    )

    assert receipt.receipt_sha256 == second_receipt.receipt_sha256
    assert tuple(row.fingerprint_sha256 for row in first) == tuple(
        row.fingerprint_sha256 for row in second
    )
    assert set(GUIDED_MODES).issubset(receipt.proposal_modes)
    assert receipt.proposal_modes.count(UNIFORM_FALLBACK_MODE) >= 1
    assert receipt.to_dict()["uniform_random_placement_retained_as_fallback"]
    assert receipt.to_dict()["scientifically_validated"] is False
    assert context.ligand_hydrophobic_patches
    assert context.receptor_hydrophobic_patches

    baseline, _ = generate_pocket_centered_docking_proposals(
        authority,
        _budget(),
    )
    for index, mode in enumerate(receipt.proposal_modes):
        observed_offset = float(
            torch.linalg.vector_norm(
                first[index].coordinates.mean(dim=0) - authority.pocket.center
            ).item()
        )
        assert observed_offset <= _budget().translation_radius_angstrom + 1.0e-10
        identity = torch.eye(3, dtype=first[index].rotation.dtype)
        assert torch.allclose(
            first[index].rotation.T @ first[index].rotation,
            identity,
            atol=1.0e-10,
            rtol=0.0,
        )
        assert float(torch.linalg.det(first[index].rotation).item()) == pytest.approx(
            1.0,
            abs=1.0e-10,
        )
        if mode == UNIFORM_FALLBACK_MODE:
            assert first[index].fingerprint_sha256 == (
                baseline[index].fingerprint_sha256
            )
            assert torch.equal(
                first[index].coordinates,
                baseline[index].coordinates,
            )
        else:
            assert first[index].fingerprint_sha256 != (
                baseline[index].fingerprint_sha256
            )


def test_each_guidance_mode_changes_geometry_by_its_feature_contract() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    policy = GuidedPlacementPolicy()
    proposals, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
        policy=policy,
    )
    receptor_coordinates = receptor.coordinates[0]

    expected_distances = {
        "donor_acceptor_hotspot": policy.donor_acceptor_distance_angstrom,
        "charge_anchor": policy.charge_anchor_distance_angstrom,
        "hydrophobic_patch": policy.hydrophobic_distance_angstrom,
    }
    for mode, expected_distance in expected_distances.items():
        index = receipt.proposal_modes.index(mode)
        proposal = proposals[index]
        ligand_anchor = proposal.coordinates[
            list(receipt.ligand_anchor_atom_indices[index])
        ].mean(dim=0)
        receptor_anchor = receptor_coordinates[
            list(receipt.receptor_anchor_atom_indices[index])
        ].mean(dim=0)
        observed = float(
            torch.linalg.vector_norm(ligand_anchor - receptor_anchor).item()
        )
        assert receipt.requested_anchor_distance_angstroms[index] == pytest.approx(
            expected_distance,
            abs=1.0e-12,
        )
        assert receipt.observed_anchor_distance_angstroms[index] == pytest.approx(
            observed,
            abs=1.0e-12,
        )
        assert observed == pytest.approx(expected_distance, abs=1.0e-8)

    hydrophobic_index = receipt.proposal_modes.index("hydrophobic_patch")
    assert len(receipt.ligand_anchor_atom_indices[hydrophobic_index]) > 1
    guidance_row = receipt.to_dict()["proposal_guidance_rows"][hydrophobic_index]
    assert guidance_row["ligand_anchor_atom_indices"] == list(
        receipt.ligand_anchor_atom_indices[hydrophobic_index]
    )

    aromatic = _mode_proposal(proposals, receipt, "aromatic_plane")
    ligand_system = context.ligand_aromatic_systems[0]
    receptor_plane = context.receptor_aromatic_planes[0]
    ligand_center = aromatic.coordinates[list(ligand_system)].mean(dim=0)
    receptor_center = torch.tensor(
        receptor_plane[1],
        dtype=torch.float64,
    )
    assert float(
        torch.linalg.vector_norm(ligand_center - receptor_center).item()
    ) == pytest.approx(
        policy.aromatic_plane_distance_angstrom,
        abs=1.0e-8,
    )

    shape = _mode_proposal(
        proposals,
        receipt,
        "shape_complementarity",
    )
    assert torch.allclose(
        shape.coordinates.mean(dim=0),
        authority.pocket.center,
        atol=1.0e-10,
        rtol=0.0,
    )


def test_guided_context_rejects_crosswired_systems_and_is_immutable() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    assert len(context.fingerprint_sha256) == 64
    with pytest.raises(TypeError):
        context.ligand_features["donor"] = ()

    moved = receptor.with_coordinates(
        receptor.coordinates + 0.1,
        operation="crosswire-test",
    )
    with pytest.raises(
        DockingAuthorityError,
        match="receptor system is cross-wired",
    ):
        build_guided_placement_context(authority, moved, ligand)

    crosswired = replace(
        context,
        authority_input_receipt_sha256="0" * 64,
    )
    with pytest.raises(
        DockingAuthorityError,
        match="another authority",
    ):
        generate_guided_docking_proposals(
            authority,
            _budget(),
            crosswired,
        )


def test_unavailable_guidance_is_the_exact_uniform_batch() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(authority, receptor, ligand)
    empty_features = {name: () for name in context.ligand_features}
    unavailable = replace(
        context,
        ligand_features=empty_features,
        receptor_feature_rows={name: () for name in empty_features},
        ligand_hydrophobic_patches=(),
        receptor_hydrophobic_patches=(),
        ligand_aromatic_systems=(),
        receptor_aromatic_planes=(),
        receptor_shape_axes=(),
    )

    guided, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        unavailable,
    )
    baseline, _ = generate_pocket_centered_docking_proposals(
        authority,
        _budget(),
    )
    assert (
        receipt.proposal_modes == (UNIFORM_FALLBACK_MODE,) * _budget().candidate_count
    )
    assert tuple(row.fingerprint_sha256 for row in guided) == tuple(
        row.fingerprint_sha256 for row in baseline
    )
    assert all(
        torch.equal(guided_row.coordinates, baseline_row.coordinates)
        for guided_row, baseline_row in zip(guided, baseline)
    )


def test_guided_receipt_detects_anchor_distance_mutation() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(authority, receptor, ligand)
    _, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
    )
    observed = list(receipt.observed_anchor_distance_angstroms)
    guided_index = next(
        index for index, value in enumerate(observed) if value is not None
    )
    observed[guided_index] = float(observed[guided_index]) + 0.25
    object.__setattr__(
        receipt,
        "observed_anchor_distance_angstroms",
        tuple(observed),
    )
    with pytest.raises(DockingAuthorityError, match="receipt changed"):
        _ = receipt.receipt_sha256


def test_unavailable_guidance_reproduces_the_entire_uniform_batch() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    empty_features = {name: () for name in context.ligand_features}
    no_guidance = replace(
        context,
        ligand_features=empty_features,
        receptor_feature_rows=empty_features,
        ligand_hydrophobic_patches=(),
        receptor_hydrophobic_patches=(),
        ligand_aromatic_systems=(),
        receptor_aromatic_planes=(),
        receptor_shape_axes=(),
    )

    proposals, receipt = generate_guided_docking_proposals(
        authority,
        _budget(911),
        no_guidance,
    )
    baseline, _ = generate_pocket_centered_docking_proposals(
        authority,
        _budget(911),
    )

    assert set(receipt.proposal_modes) == {UNIFORM_FALLBACK_MODE}
    assert receipt.proposal_fingerprint_sha256s == tuple(
        row.fingerprint_sha256 for row in baseline
    )
    assert all(
        torch.equal(guided.coordinates, uniform.coordinates)
        for guided, uniform in zip(proposals, baseline)
    )


def test_guided_search_reuses_failure_complete_search_and_resets_override() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    result = run_authenticated_guided_placement_search(
        authority,
        _budget(907),
        _Scorer(authority.problem.fingerprint_sha256),
        context,
        diversity_rmsd_angstrom=0.0,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=(tuple(range(ligand.atom_count)),),
    )

    assert result.guided_receipt.authenticated_input_receipt_sha256 == (
        authority.input_receipt_sha256
    )
    assert len(result.authenticated_search_result.search_result.rows) == (
        _budget().candidate_count
    )
    assert result.to_dict()["claim_safe"] is False

    baseline, _ = generate_pocket_centered_docking_proposals(
        authority,
        _budget(907),
    )
    assert tuple(row.fingerprint_sha256 for row in baseline) != (
        result.guided_receipt.proposal_fingerprint_sha256s
    )
