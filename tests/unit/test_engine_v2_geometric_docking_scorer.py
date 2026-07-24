from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    GEOMETRY_DIAGNOSTIC_BLOCKERS,
    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
    DockingBudget,
    DockingProblemIdentity,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
    ElementGeometryDiagnosticScoringError,
    PoseValidityConfig,
    PoseValidityContext,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
        coordinate_frame_id="pocket_centered_receptor_frame",
    )


def _space() -> TorsionSearchSpace:
    coordinates = torch.tensor(
        [[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]],
        dtype=torch.float64,
    )
    return TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((2,), -1, dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 2, dtype=torch.float64),
        rotatable_mask=torch.zeros(2, dtype=torch.bool),
        root_positions=coordinates,
    )


def _scorer() -> ElementGeometryDiagnosticScorer:
    receptor = torch.tensor(
        [[0.0, 3.4, 0.0], [20.0, 20.0, 20.0]],
        dtype=torch.float64,
    )
    return ElementGeometryDiagnosticScorer(
        receptor,
        (6, 8),
        (6, 8),
        _problem(),
        config=ElementGeometryDiagnosticScoreConfig(
            receptor_shell_radius_angstrom=10.1,
            pocket_radius_angstrom=10.0,
        ),
    )


def _validity_context() -> PoseValidityContext:
    problem = _problem()
    reference = _space().root_positions
    return PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=((0, 1),),
        excluded_nonbonded_pairs=((0, 1),),
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]],
            dtype=torch.float64,
        ),
        pocket_center=reference.mean(dim=0),
        chirality_centers=(),
        config=PoseValidityConfig(pocket_radius_angstrom=20.0),
    )


def test_element_geometry_scorer_emits_atomic_five_term_diagnostic() -> None:
    scorer = _scorer()
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0),
        problem=_problem(),
    )[0]

    breakdown = scorer.score(proposal)

    assert breakdown.complete
    assert {term.term_id for term in breakdown.terms} == {
        "element_radius_contact_reward",
        "element_radius_overlap_penalty",
        "element_radius_deep_penetration_penalty",
        "pocket_centroid_restraint",
        "rigid_ligand_internal_strain",
    }
    assert breakdown.blockers == GEOMETRY_DIAGNOSTIC_BLOCKERS
    assert all(
        term.unit == "dimensionless" for term in breakdown.terms
    )
    assert scorer.parameter_source_sha256 == (
        GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
    )
    assert scorer.receptor_shell_atom_count == 1
    assert scorer.score_descriptor.calibrated is False
    assert scorer.validated_for_docking_ranking is False
    assert scorer.chemistry_scope["partial_charge_used"] is False


def test_deep_clash_and_far_escape_score_worse_than_surface_contact() -> None:
    scorer = _scorer()
    surface = torch.tensor([[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]], dtype=torch.float64)
    clash = surface + torch.tensor([0.0, 3.3, 0.0], dtype=torch.float64)
    far = surface + torch.tensor([9.0, 0.0, 0.0], dtype=torch.float64)

    surface_score = scorer.score_coordinates(surface).total_score
    clash_score = scorer.score_coordinates(clash).total_score
    far_score = scorer.score_coordinates(far).total_score

    assert surface_score < clash_score
    assert surface_score < far_score


def test_search_retains_uncalibrated_geometry_term_breakdowns() -> None:
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(
            candidate_count=8,
            top_k=3,
            max_torsions=0,
            translation_radius_angstrom=2.0,
            seed=19,
        ),
        _scorer(),
        validity_context=_validity_context(),
        problem=_problem(),
        diversity_rmsd_angstrom=0.0,
    )

    assert result.success_count == 8
    assert result.failure_count == 0
    assert len(result.top_rows) == 3
    assert all(row.score_breakdown is not None for row in result.rows)
    assert "docking_score_uncalibrated" in result.blockers
    assert "scorer_not_validated_for_docking_ranking" in result.blockers
    assert "score_term_decomposition_missing" not in result.blockers


def test_scope_problem_and_capacity_fail_closed() -> None:
    with pytest.raises(
        ElementGeometryDiagnosticScoringError,
        match="unsupported elements",
    ):
        ElementGeometryDiagnosticScorer(
            torch.zeros((1, 3), dtype=torch.float64),
            (26,),
            (6,),
            _problem(),
        )
    with pytest.raises(
        ElementGeometryDiagnosticScoringError,
        match="pair capacity",
    ):
        ElementGeometryDiagnosticScorer(
            torch.zeros((2, 3), dtype=torch.float64),
            (6, 6),
            (6, 6),
            _problem(),
            config=ElementGeometryDiagnosticScoreConfig(max_cross_pairs=3),
        )

    scorer = _scorer()
    other_problem = DockingProblemIdentity(
        receptor_system_sha256="d" * 64,
        ligand_system_sha256="e" * 64,
    )
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0),
        problem=other_problem,
    )[0]
    with pytest.raises(
        ElementGeometryDiagnosticScoringError,
        match="does not match",
    ):
        scorer.score(proposal)


def test_geometric_scorer_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.geometric_scoring import (
        __all__ as geometric_exports,
    )

    assert set(geometric_exports) <= set(docking.__all__)
