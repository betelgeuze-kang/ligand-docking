from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    PoseValidityConfig,
    PoseValidityContext,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.io import (  # noqa: E402
    PDBParseError,
    SDF_PARSER_VERSION,
    SDFParseError,
    parse_pdb,
    parse_sdf_v2000,
    pdb_string,
    sdf_v2000_string,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    CanonicalSerializationError,
    MolecularValidationError,
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
    validate_all_atom_system,
    write_canonical_system_json,
)


def _pdb_atom(serial: int, name: str, element: str, x: float) -> str:
    return (
        f"{'HETATM':<6}{serial:5d} {name:<4}{'':1}{'LIG':>3} {'L':1}{1:4d}{'':1}   "
        f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{10.0:6.2f}          {element:>2}{'':>2}"
    )


def _pdb_fixture(*, connectivity_record: str = "") -> str:
    rows = [
        _pdb_atom(1, "C1", "C", 0.0),
        _pdb_atom(2, "O1", "O", 1.25),
        "CONECT    1    2",
    ]
    if connectivity_record:
        rows.insert(0, connectivity_record)
    rows.append("END")
    return "\n".join(rows) + "\n"


def _sdf_fixture() -> str:
    return "\n".join(
        [
            "identity-ligand",
            "EngineV2",
            "strict fixture",
            f"{2:3d}{1:3d}  0  0  0  0            999 V2000",
            f"{0.0:10.4f}{0.0:10.4f}{0.0:10.4f} {'C':<3}{0:2d}{0:3d}  0  0  0  0  0  0  0  0  0  0  0  0",
            f"{1.25:10.4f}{0.0:10.4f}{0.0:10.4f} {'O':<3}{0:2d}{0:3d}  0  0  0  0  0  0  0  0  0  0  0  0",
            f"{1:3d}{2:3d}{1:3d}{0:3d}  0  0  0",
            "M  CHG  1   2  -1",
            "M  ISO  1   1  13",
            "M  END",
            "$$$$",
        ]
    ) + "\n"


def test_canonical_json_round_trip_is_self_verifying_and_atomic(tmp_path: Path) -> None:
    system = parse_sdf_v2000(_sdf_fixture(), source_id="canonical-fixture")
    encoded = canonical_system_json_bytes(system)
    restored = all_atom_system_from_canonical_json(encoded)

    assert canonical_system_sha256(restored) == canonical_system_sha256(system)
    assert canonical_topology_sha256(restored) == canonical_topology_sha256(system)
    assert canonical_coordinates_sha256(restored) == canonical_coordinates_sha256(system)
    assert torch.equal(restored.coordinates, system.coordinates)

    path = write_canonical_system_json(system, tmp_path / "system.json")
    assert path.exists()
    assert not list(tmp_path.glob(".system.json.tmp-*"))
    assert canonical_system_sha256(
        all_atom_system_from_canonical_json(path.read_bytes())
    ) == canonical_system_sha256(system)

    tampered = encoded.replace(b"identity-ligand", b"identity-ligand-tampered")
    with pytest.raises(CanonicalSerializationError, match="SHA-256 mismatch"):
        all_atom_system_from_canonical_json(tampered)


def test_strict_pdb_and_sdf_writers_round_trip_supported_fields() -> None:
    pdb_system = parse_pdb(_pdb_fixture(), source_id="pdb-source")
    pdb_text, pdb_receipt = pdb_string(pdb_system)
    pdb_round_trip = parse_pdb(pdb_text, source_id="pdb-round-trip")
    assert pdb_receipt.format == "pdb_strict_v1"
    assert [atom.element for atom in pdb_round_trip.atoms] == ["C", "O"]
    assert [(bond.atom_i, bond.atom_j) for bond in pdb_round_trip.bonds] == [(0, 1)]
    assert torch.allclose(
        pdb_round_trip.coordinates,
        pdb_system.coordinates,
        atol=5.0e-4,
        rtol=0.0,
    )

    sdf_system = parse_sdf_v2000(_sdf_fixture(), source_id="sdf-source")
    sdf_text, sdf_receipt = sdf_v2000_string(sdf_system)
    sdf_round_trip = parse_sdf_v2000(sdf_text, source_id="sdf-round-trip")
    assert sdf_receipt.format == "sdf_v2000_strict_v1"
    assert sdf_round_trip.atoms[0].isotope_mass_number == 13
    assert sdf_round_trip.atoms[1].formal_charge == -1
    assert [
        (bond.atom_i, bond.atom_j, bond.order) for bond in sdf_round_trip.bonds
    ] == [(0, 1, 1.0)]
    assert torch.allclose(
        sdf_round_trip.coordinates,
        sdf_system.coordinates,
        atol=5.0e-5,
        rtol=0.0,
    )


def test_sdf_wedge_anchor_survives_canonical_endpoints_and_writer() -> None:
    atoms = [
        ("C", (0.0, 0.0, 0.0)),
        ("F", (1.0, 1.0, 1.0)),
        ("Cl", (-1.0, -1.0, 1.0)),
        ("Br", (-1.0, 1.0, -1.0)),
        ("H", (1.0, -1.0, -1.0)),
    ]

    def source(first: int, second: int) -> str:
        lines = ["tetrahedral-wedge", "EngineV2", "orientation fixture",
                 f"{5:3d}{4:3d}  0  0  0  0            999 V2000"]
        for element, (x, y, z) in atoms:
            lines.append(
                f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3}{0:2d}{0:3d}"
                "  0  0  0  0  0  0  0  0  0  0  0  0"
            )
        lines.append(f"{first:3d}{second:3d}{1:3d}{1:3d}  0  0  0")
        lines.extend(f"{1:3d}{index:3d}{1:3d}{0:3d}  0  0  0"
                     for index in (3, 4, 5))
        return "\n".join([*lines, "M  END", "$$$$", ""])

    forward = parse_sdf_v2000(source(1, 2))
    reverse = parse_sdf_v2000(source(2, 1))
    assert [(bond.atom_i, bond.atom_j, bond.stereo) for bond in forward.bonds] == [
        (0, 1, "up"), (0, 2, "none"), (0, 3, "none"), (0, 4, "none")]
    assert [(bond.atom_i, bond.atom_j, bond.stereo) for bond in reverse.bonds] == [
        (0, 1, "up"), (0, 2, "none"), (0, 3, "none"), (0, 4, "none")]
    assert forward.bonds[0].metadata["sdf_v2000_stereo_first_atom_index"] == 0
    assert reverse.bonds[0].metadata["sdf_v2000_stereo_first_atom_index"] == 1
    assert forward.provenance.parser_version == reverse.provenance.parser_version == SDF_PARSER_VERSION
    assert canonical_topology_sha256(forward) != canonical_topology_sha256(reverse)
    for system, expected_anchor in ((forward, 0), (reverse, 1)):
        report = validate_all_atom_system(system)
        assert report.stereochemistry_declared is True
        assert report.stereochemistry_geometry_verified is False
        assert any(issue.code == "bond_stereo_geometry_unverified"
                   for issue in report.issues)
        written, _ = sdf_v2000_string(system)
        restored = parse_sdf_v2000(written)
        assert restored.bonds[0].metadata["sdf_v2000_stereo_first_atom_index"] == expected_anchor
        canonical = all_atom_system_from_canonical_json(canonical_system_json_bytes(system))
        assert canonical.bonds[0].metadata["sdf_v2000_stereo_first_atom_index"] == expected_anchor
    for metadata in (
        {},
        {"sdf_v2000_stereo_first_atom_index": True},
        {"sdf_v2000_stereo_first_atom_index": 4},
    ):
        invalid_bond = replace(reverse.bonds[0], metadata=metadata)
        invalid_system = replace(reverse, bonds=(invalid_bond, *reverse.bonds[1:]))
        invalid_report = validate_all_atom_system(invalid_system)
        assert invalid_report.topology_consistent is False
        assert any(issue.code == "bond_stereo_anchor_invalid" for issue in invalid_report.issues)
        with pytest.raises(MolecularValidationError, match="bond_stereo_anchor_invalid"):
            sdf_v2000_string(invalid_system)
    invalid_order = source(1, 2).replace(
        f"{1:3d}{2:3d}{1:3d}{1:3d}  0  0  0",
        f"{1:3d}{2:3d}{2:3d}{1:3d}  0  0  0",
    )
    with pytest.raises(SDFParseError, match="directed stereo requires a single bond"):
        parse_sdf_v2000(invalid_order)


def test_pdb_connectivity_records_are_rejected_or_explicitly_recorded() -> None:
    link = "LINK         C1  LIG L   1                 O1  LIG L   1     1555   1555  1.25"
    source = _pdb_fixture(connectivity_record=link)
    with pytest.raises(PDBParseError, match="cannot be represented"):
        parse_pdb(source)

    recorded = parse_pdb(source, connectivity_policy="record_unrepresented")
    counts = recorded.provenance.metadata[
        "unrepresented_connectivity_record_counts"
    ]
    assert counts == {"LINK": 1}
    assert (
        recorded.metadata["connectivity_claim_blocker"]
        == "pdb_link_or_ssbond_not_materialized"
    )
    assert recorded.provenance.chemistry_validated is False


def _search_space(offset: float = 1.0) -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [offset, 0.0, 0.0], [offset, 0.0, 0.0]],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, 1], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 3, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False, True]),
    )


def _problem(marker: str) -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256=("a" if marker == "a" else "c") * 64,
        ligand_system_sha256=("b" if marker == "a" else "d") * 64,
        pocket_definition_sha256="e" * 64,
        coordinate_frame_id="receptor-frame-v1",
    )


def _validity_context(problem: DockingProblemIdentity) -> PoseValidityContext:
    reference = generate_bounded_docking_proposals(
        _search_space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1),
        problem=problem,
    )[0].coordinates
    return PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=((0, 1), (1, 2)),
        excluded_nonbonded_pairs=((0, 1), (1, 2)),
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]], dtype=torch.float64
        ),
        pocket_center=reference.mean(dim=0),
        chirality_centers=(),
        config=PoseValidityConfig(pocket_radius_angstrom=20.0),
    )


def test_problem_and_search_space_identity_are_bound_into_every_proposal() -> None:
    budget = DockingBudget(candidate_count=3, top_k=1, max_torsions=1, seed=7)
    first = generate_bounded_docking_proposals(
        _search_space(), budget, problem=_problem("a")
    )
    changed_problem = generate_bounded_docking_proposals(
        _search_space(), budget, problem=_problem("b")
    )
    changed_space = generate_bounded_docking_proposals(
        _search_space(1.1), budget, problem=_problem("a")
    )

    assert first[0].problem_fingerprint_sha256 == _problem("a").fingerprint_sha256
    assert (
        first[0].search_space_fingerprint_sha256
        == _search_space().fingerprint_sha256
    )
    assert first[0].fingerprint_sha256 != changed_problem[0].fingerprint_sha256
    assert first[0].fingerprint_sha256 != changed_space[0].fingerprint_sha256
    assert first[0].coordinate_fingerprint_sha256


_PROBLEM_A_FINGERPRINT = _problem("a").fingerprint_sha256


class _Scorer:
    scorer_id = "identity-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    problem_fingerprint_sha256 = _PROBLEM_A_FINGERPRINT
    implementation_source_sha256 = "1" * 64
    config_fingerprint_sha256 = "2" * 64

    def score(self, proposal):
        return proposal.coordinates.square().sum()


class _LineageRefiner:
    refiner_id = "identity-test-refiner"
    refiner_version = "1.0.0"
    problem_fingerprint_sha256 = _PROBLEM_A_FINGERPRINT
    implementation_source_sha256 = "3" * 64
    config_fingerprint_sha256 = "4" * 64

    def refine(self, proposal, *, max_steps):
        assert max_steps == 2
        return proposal.with_refined_coordinates(
            proposal.coordinates + 0.01,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256="f" * 64,
        )


class _BadRefiner:
    refiner_id = "bad-refiner"
    refiner_version = "1.0.0"
    problem_fingerprint_sha256 = _PROBLEM_A_FINGERPRINT
    implementation_source_sha256 = "5" * 64
    config_fingerprint_sha256 = "6" * 64

    def refine(self, proposal, *, max_steps):
        del max_steps
        return replace(proposal, candidate_id="forged-candidate")


def test_refined_pose_requires_parent_lineage_and_preserves_problem_identity() -> None:
    problem = _problem("a")
    context = _validity_context(problem)
    budget = DockingBudget(
        candidate_count=2,
        top_k=1,
        max_torsions=1,
        max_refinement_steps=2,
        seed=11,
    )
    result = run_bounded_docking_search(
        _search_space(),
        budget,
        _Scorer(),
        refiner=_LineageRefiner(),
        validity_context=context,
        problem=problem,
    )
    assert result.failure_count == 0
    assert result.problem_fingerprint_sha256 == problem.fingerprint_sha256
    assert all(row.selection_eligible for row in result.rows)
    for row in result.rows:
        assert row.refined is True
        assert (
            row.proposal_fingerprint_sha256
            != row.result_proposal_fingerprint_sha256
        )
        assert row.proposal is not None
        assert (
            row.proposal.parent_proposal_fingerprint_sha256
            == row.proposal_fingerprint_sha256
        )

    rejected = run_bounded_docking_search(
        _search_space(),
        budget,
        _Scorer(),
        refiner=_BadRefiner(),
        validity_context=context,
        problem=problem,
    )
    assert rejected.failure_count == 2
    assert all(
        row.error_code in {"DockingProposalError", "DockingSearchError"}
        for row in rejected.rows
    )
