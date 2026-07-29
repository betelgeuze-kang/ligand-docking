from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import guided_placement as guided_module  # noqa: E402

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
    MULTI_ANCHOR_MODE,
    UNIFORM_FALLBACK_MODE,
    DockingAuthorityError,
    DockingBudget,
    DockingScoreDescriptor,
    DockingScope,
    GuidedPlacementPolicy,
    GuidedPlacementSearchResult,
    PocketDefinition,
    ScoreDirection,
    build_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    generate_guided_docking_proposals,
    generate_pocket_centered_docking_proposals,
    run_authenticated_guided_placement_search,
)
from betelgeuze_engine_v2.docking.guided_placement import (  # noqa: E402
    _adjacency,
    _aromatic_systems,
    _feature_indices,
    _principal_axes,
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
        receptor_system=receptor,
        ligand_system=ligand,
    )
    second, second_receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
        receptor_system=receptor,
        ligand_system=ligand,
    )

    assert receipt.receipt_sha256 == second_receipt.receipt_sha256
    assert tuple(row.fingerprint_sha256 for row in first) == tuple(
        row.fingerprint_sha256 for row in second
    )
    assert set(GUIDED_MODES).issubset(receipt.proposal_modes)
    guided_count = sum(
        mode != UNIFORM_FALLBACK_MODE for mode in receipt.proposal_modes
    )
    assert guided_count == 5
    assert receipt.proposal_modes.count(UNIFORM_FALLBACK_MODE) == 3
    assert all(receipt.proposal_modes.count(mode) <= 8 for mode in GUIDED_MODES)
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


def test_repeated_interaction_cycles_add_bounded_multi_anchor_candidates() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(authority, receptor, ligand)
    budget = replace(_budget(), candidate_count=64, top_k=5)

    proposals, receipt = generate_guided_docking_proposals(
        authority,
        budget,
        context,
        receptor_system=receptor,
        ligand_system=ligand,
    )
    repeated, repeated_receipt = generate_guided_docking_proposals(
        authority,
        budget,
        context,
        receptor_system=receptor,
        ligand_system=ligand,
    )

    multi_indices = tuple(
        index
        for index, mode in enumerate(receipt.proposal_modes)
        if mode == MULTI_ANCHOR_MODE
    )
    assert len(multi_indices) == 8
    assert receipt.proposal_modes.count(UNIFORM_FALLBACK_MODE) == 24
    assert receipt.receipt_sha256 == repeated_receipt.receipt_sha256
    assert tuple(row.fingerprint_sha256 for row in proposals) == tuple(
        row.fingerprint_sha256 for row in repeated
    )
    for index in multi_indices:
        ligand_indices = receipt.ligand_anchor_atom_indices[index]
        receptor_indices = receipt.receptor_anchor_atom_indices[index]
        assert 2 <= len(ligand_indices) <= 3
        assert len(ligand_indices) == len(receptor_indices)
        assert receipt.requested_anchor_distance_angstroms[index] is not None
        assert receipt.observed_anchor_distance_angstroms[index] is not None
        guidance_row = receipt.to_dict()["proposal_guidance_rows"][index]
        assert guidance_row["anchor_pairing"] == "positionally_aligned"
        assert guidance_row["anchor_distance_aggregation"] == (
            "per_pair_arithmetic_mean"
        )
        assert guidance_row["anchor_pairs"] == [
            {
                "ligand_atom_index": ligand_index,
                "receptor_atom_index": receptor_index,
            }
            for ligand_index, receptor_index in zip(
                ligand_indices, receptor_indices
            )
        ]
        paired_observed = sum(
            float(
                torch.linalg.vector_norm(
                    proposals[index].coordinates[ligand_index]
                    - receptor.coordinates[0, receptor_index]
                ).item()
            )
            for ligand_index, receptor_index in zip(
                ligand_indices, receptor_indices
            )
        ) / len(ligand_indices)
        assert receipt.observed_anchor_distance_angstroms[index] == pytest.approx(
            paired_observed,
            abs=1.0e-12,
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
        receptor_system=receptor,
        ligand_system=ligand,
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
    aromatic_delta = ligand_center - receptor_center
    receptor_normal = torch.tensor(receptor_plane[2], dtype=torch.float64)
    assert float(
        torch.linalg.vector_norm(
            torch.cross(aromatic_delta, receptor_normal, dim=0)
        ).item()
    ) == pytest.approx(
        0.0,
        abs=1.0e-8,
    )
    assert abs(
        float(torch.dot(aromatic_delta, receptor_normal).item())
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
            receptor_system=receptor,
            ligand_system=ligand,
        )


def test_caller_forged_guidance_context_is_rejected() -> None:
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

    with pytest.raises(DockingAuthorityError, match="authenticated derivation"):
        generate_guided_docking_proposals(
            authority,
            _budget(),
            unavailable,
            receptor_system=receptor,
            ligand_system=ligand,
        )


def test_guided_receipt_detects_anchor_distance_mutation() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(authority, receptor, ligand)
    _, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
        receptor_system=receptor,
        ligand_system=ligand,
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


def test_feature_capacity_is_applied_to_the_authenticated_pocket_subset() -> None:
    base = _receptor()
    extra_count = 2_050
    extra_atoms = tuple(
        Atom(
            index=base.atom_count + offset,
            name=f"X{offset}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for offset in range(extra_count)
    )
    extra_coordinates = torch.tensor(
        [[50.0 + 0.01 * offset, 50.0, 50.0] for offset in range(extra_count)],
        dtype=torch.float64,
    )
    receptor = AllAtomSystem(
        system_id="large-guided-receptor",
        atoms=(*base.atoms, *extra_atoms),
        bonds=base.bonds,
        residues=(
            replace(
                base.residues[0],
                atom_indices=tuple(range(base.atom_count + extra_count)),
            ),
        ),
        chains=base.chains,
        coordinates=torch.cat(
            (base.coordinates, extra_coordinates.unsqueeze(0)),
            dim=1,
        ),
        provenance=_provenance("large-guided-receptor-source", "9" * 64),
    )
    ligand = _ligand()
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="guided-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    authority = build_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=4.0,
    )

    context = build_guided_placement_context(authority, receptor, ligand)
    assert len(context.receptor_feature_rows["hydrophobic"]) < 2_048
    assert max(authority.receptor_atom_indices) < base.atom_count
    local_adjacency = _adjacency(
        receptor,
        allowed_indices=set(authority.receptor_atom_indices),
    )
    assert max(local_adjacency) < base.atom_count


def test_receptor_bond_scan_work_is_hard_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand = _authority()
    monkeypatch.setattr(
        guided_module,
        "MAX_GUIDED_RECEPTOR_BONDS_SCANNED",
        1,
    )
    with pytest.raises(DockingAuthorityError, match="bond count"):
        build_guided_placement_context(authority, receptor, ligand)


def test_degenerate_ligand_shape_and_aromatic_frames_use_uniform_fallback() -> None:
    ligand = AllAtomSystem(
        system_id="linear-guided-ligand",
        atoms=_atoms(("C", "C", "C"), aromatic={0, 1, 2}),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.5, aromatic=True),
            Bond(index=1, atom_i=1, atom_j=2, order=1.5, aromatic=True),
            Bond(index=2, atom_i=0, atom_j=2, order=1.5, aromatic=True),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[-1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("linear-guided-ligand-source", "7" * 64),
    )
    receptor = AllAtomSystem(
        system_id="shape-only-receptor",
        atoms=_atoms(("H", "H", "H")),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 2.0, 0.0]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("shape-only-receptor-source", "8" * 64),
    )
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="guided-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    authority = build_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=4.0,
    )
    context = build_guided_placement_context(authority, receptor, ligand)
    guided, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
        receptor_system=receptor,
        ligand_system=ligand,
    )
    baseline, _ = generate_pocket_centered_docking_proposals(authority, _budget())

    assert context.ligand_shape_frame_available is False
    assert context.ligand_aromatic_systems == ()
    assert receipt.proposal_modes == (UNIFORM_FALLBACK_MODE,) * 8
    assert tuple(row.fingerprint_sha256 for row in guided) == tuple(
        row.fingerprint_sha256 for row in baseline
    )


def test_nonaromatic_biaryl_bridge_does_not_merge_aromatic_planes() -> None:
    atoms = _atoms(tuple("C" for _ in range(12)), aromatic=set(range(12)))
    bonds: list[Bond] = []
    for start in (0, 6):
        for offset in range(6):
            first = start + offset
            second = start + ((offset + 1) % 6)
            bonds.append(
                Bond(
                    index=len(bonds),
                    atom_i=min(first, second),
                    atom_j=max(first, second),
                    order=1.5,
                    aromatic=True,
                )
            )
    bonds.append(Bond(index=len(bonds), atom_i=5, atom_j=6, order=1.0))
    system = AllAtomSystem(
        system_id="biaryl-guided-fixture",
        atoms=atoms,
        bonds=tuple(bonds),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(12)),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.zeros((1, 12, 3), dtype=torch.float64),
        provenance=_provenance("biaryl-guided-source", "6" * 64),
    )

    assert _aromatic_systems(system) == (
        tuple(range(6)),
        tuple(range(6, 12)),
    )


def test_donor_and_acceptor_features_exclude_false_aromatic_and_charge_cases() -> None:
    atoms = _atoms(
        ("N", "H", "N", "C", "C", "C", "C"),
        charges={2: 1},
        aromatic={0},
    )
    system = AllAtomSystem(
        system_id="guided-feature-edge-cases",
        atoms=atoms,
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=2, atom_j=3),
            Bond(index=2, atom_i=2, atom_j=4),
            Bond(index=3, atom_i=2, atom_j=5),
            Bond(index=4, atom_i=2, atom_j=6),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(7)),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.zeros((1, 7, 3), dtype=torch.float64),
        provenance=_provenance("guided-feature-edge-source", "5" * 64),
    )

    features = _feature_indices(system)
    assert 0 in features["donor"]
    assert 0 not in features["acceptor"]
    assert 2 in features["positive"]
    assert 2 not in features["donor"]


def test_repeated_principal_values_disable_shape_guidance() -> None:
    root = 3.0**0.5 / 2.0
    symmetric_ring = torch.tensor(
        [
            [1.0, 0.0, 0.0],
            [0.5, root, 0.0],
            [-0.5, root, 0.0],
            [-1.0, 0.0, 0.0],
            [-0.5, -root, 0.0],
            [0.5, -root, 0.0],
        ],
        dtype=torch.float64,
    )
    assert _principal_axes(symmetric_ring) is None


def test_sampled_degenerate_shape_frame_falls_back_per_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(authority, receptor, ligand)
    baseline, _ = generate_pocket_centered_docking_proposals(authority, _budget())

    def unavailable_shape(*args, **kwargs):
        raise guided_module._GuidanceUnavailable("sampled shape frame is degenerate")

    monkeypatch.setattr(guided_module, "_principal_rotation", unavailable_shape)
    proposals, receipt = generate_guided_docking_proposals(
        authority,
        _budget(),
        context,
        receptor_system=receptor,
        ligand_system=ligand,
    )
    shape_index = GUIDED_MODES.index("shape_complementarity")
    assert receipt.proposal_modes[shape_index] == UNIFORM_FALLBACK_MODE
    assert proposals[shape_index].fingerprint_sha256 == (
        baseline[shape_index].fingerprint_sha256
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
        receptor_system=receptor,
        ligand_system=ligand,
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


def test_guided_search_result_rejects_a_different_top_k_budget() -> None:
    authority, receptor, ligand = _authority()
    context = build_guided_placement_context(authority, receptor, ligand)
    first = run_authenticated_guided_placement_search(
        authority,
        _budget(919),
        _Scorer(authority.problem.fingerprint_sha256),
        context,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )
    second = run_authenticated_guided_placement_search(
        authority,
        replace(_budget(919), top_k=2),
        _Scorer(authority.problem.fingerprint_sha256),
        context,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
    )
    assert first.guided_receipt.proposal_fingerprint_sha256s == (
        second.guided_receipt.proposal_fingerprint_sha256s
    )
    with pytest.raises(DockingAuthorityError, match="budget is cross-wired"):
        GuidedPlacementSearchResult(
            guided_receipt=first.guided_receipt,
            authenticated_search_result=second.authenticated_search_result,
        )
