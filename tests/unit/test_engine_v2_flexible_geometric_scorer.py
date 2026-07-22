from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    ElementFlexibleGeometryDiagnosticScorer,
    FlexibleGeometryDiagnosticScoreConfig,
    FlexibleGeometryDiagnosticScoringError,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
)


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )


def _proposal():
    coordinates = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [1.5, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [4.5, 0.0, 0.0],
        ],
        dtype=torch.float64,
    )
    space = TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((4,), -1, dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 4, dtype=torch.float64),
        rotatable_mask=torch.zeros(4, dtype=torch.bool),
        root_positions=coordinates,
    )
    return generate_bounded_docking_proposals(
        space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
        ),
        problem=_problem(),
    )[0]


def _scorer(
    *,
    config: FlexibleGeometryDiagnosticScoreConfig | None = None,
) -> ElementFlexibleGeometryDiagnosticScorer:
    return ElementFlexibleGeometryDiagnosticScorer(
        torch.tensor([[0.0, 5.0, 0.0]], dtype=torch.float64),
        (6,),
        (6, 6, 6, 6),
        ((0, 1), (1, 2), (2, 3)),
        _problem(),
        config=config,
    )


def _term_map(breakdown):
    return {term.term_id: term for term in breakdown.terms}


def test_flexible_scorer_excludes_1_2_and_1_3_pairs_and_penalizes_1_4_clash() -> None:
    scorer = _scorer()
    proposal = _proposal()
    baseline = _term_map(scorer.score(proposal))
    clashing_coordinates = proposal.coordinates.clone()
    clashing_coordinates[3] = proposal.coordinates[0]
    clashing = proposal.with_refined_coordinates(
        clashing_coordinates,
        refiner_id="unit-clash",
        refiner_version="1.0.0",
    )
    collided = _term_map(scorer.score(clashing))

    assert scorer.ligand_nonbonded_pairs == ((0, 3),)
    assert baseline["ligand_nonbonded_self_overlap_penalty"].raw_value == 0.0
    assert collided["ligand_nonbonded_self_overlap_penalty"].raw_value > 0.0
    assert "rigid_ligand_internal_strain" not in baseline
    assert baseline["ligand_torsion_internal_energy"].raw_value == 0.0
    assert baseline["ligand_torsion_internal_energy"].weight == 0.0


def test_flexible_score_is_complete_parameter_bound_and_explicitly_uncalibrated() -> None:
    scorer = _scorer()
    result = scorer.score(_proposal())

    assert result.complete
    assert result.total_score == pytest.approx(
        sum(term.contribution for term in result.terms)
    )
    assert scorer.score_descriptor.calibrated is False
    assert scorer.validated_for_docking_ranking is False
    assert scorer.chemistry_scope["ligand_self_overlap_evaluated"] is True
    assert scorer.chemistry_scope["torsion_energy_evaluated"] is False
    assert len(scorer.config_fingerprint_sha256) == 64
    assert _scorer().config_fingerprint_sha256 == scorer.config_fingerprint_sha256


def test_flexible_scorer_rejects_duplicate_bonds_and_pair_capacity_overflow() -> None:
    with pytest.raises(FlexibleGeometryDiagnosticScoringError, match="unique"):
        ElementFlexibleGeometryDiagnosticScorer(
            torch.tensor([[0.0, 5.0, 0.0]], dtype=torch.float64),
            (6,),
            (6, 6, 6, 6),
            ((0, 1), (1, 0)),
            _problem(),
        )

    with pytest.raises(FlexibleGeometryDiagnosticScoringError, match="pair count"):
        ElementFlexibleGeometryDiagnosticScorer(
            torch.tensor([[0.0, 5.0, 0.0]], dtype=torch.float64),
            (6,),
            (6, 6, 6, 6),
            (),
            _problem(),
            config=FlexibleGeometryDiagnosticScoreConfig(
                max_ligand_nonbonded_pairs=1
            ),
        )


def test_flexible_geometry_scorer_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.flexible_geometric_scoring import (
        __all__ as scorer_exports,
    )

    assert set(scorer_exports) <= set(docking.__all__)
