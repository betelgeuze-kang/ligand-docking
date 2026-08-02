"""Scorer v1 per-term contract tests (P1-5)."""

from __future__ import annotations

import numpy as np

from betelgeuze_engine.scoring.scorer_v1 import (
    DEFAULT_TERM_WEIGHTS,
    SCORER_V1_SCHEMA_VERSION,
    SCORER_V1_TERMS,
    STATUS_BLOCKED_EMPTY,
    STATUS_READY,
    TERM_DESOLVATION,
    TERM_ELECTROSTATICS,
    TERM_HBOND,
    TERM_HYDROPHOBIC,
    TERM_POCKET_PRIOR,
    TERM_STERIC_VDW,
    TERM_STRAIN,
    TERM_TORSION,
    score_pose_v1,
)

PROTEIN = np.asarray(
    [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0], [3.0, 3.0, 3.0]],
    dtype=np.float64,
)
LIGAND = np.asarray([[1.5, 1.0, 1.0], [2.0, 1.0, 1.0]], dtype=np.float64)


def _score(**overrides):
    kwargs = {
        "protein_elements": ["N", "C", "O", "C", "C"],
        "ligand_elements": ["O", "C"],
        "ligand_smiles": "CC(=O)NC",
        "pocket_center": [1.5, 1.0, 1.0],
        "pocket_radius_a": 6.0,
    }
    kwargs.update(overrides)
    protein = kwargs.pop("protein_xyz", PROTEIN)
    ligand = kwargs.pop("ligand_xyz", LIGAND)
    return score_pose_v1(protein, ligand, **kwargs)


def test_all_eight_required_terms_are_reported() -> None:
    result = _score()
    payload = result.to_dict()

    assert payload["status"] == STATUS_READY
    assert payload["schema_version"] == SCORER_V1_SCHEMA_VERSION
    assert payload["term_count"] == 8
    assert set(payload["terms"]) == set(SCORER_V1_TERMS)
    for term_id in (
        TERM_STERIC_VDW,
        TERM_ELECTROSTATICS,
        TERM_HBOND,
        TERM_HYDROPHOBIC,
        TERM_DESOLVATION,
        TERM_TORSION,
        TERM_STRAIN,
        TERM_POCKET_PRIOR,
    ):
        assert term_id in payload["terms"]


def test_total_is_reproducible_from_the_term_breakdown() -> None:
    result = _score()

    recomputed = sum(term.weighted_value for term in result.terms)
    assert abs(recomputed - result.total_score) < 1e-9


def test_each_term_records_raw_weight_and_weighted_value() -> None:
    result = _score()

    for term in result.terms:
        assert term.weight == DEFAULT_TERM_WEIGHTS[term.term_id]
        assert abs(term.raw_value * term.weight - term.weighted_value) < 1e-9


def test_steric_term_is_element_typed_and_counts_clashes() -> None:
    clashing = _score(ligand_xyz=np.asarray([[0.5, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64))
    relaxed = _score()

    clash_detail = clashing.term(TERM_STERIC_VDW).detail
    assert clash_detail["typed"] is True
    assert clash_detail["clash_pair_count"] >= 1
    # A clashing pose must score worse on the steric term than a relaxed one.
    assert clashing.term(TERM_STERIC_VDW).raw_value > relaxed.term(TERM_STERIC_VDW).raw_value


def test_opposite_charges_are_favourable_and_like_charges_are_not() -> None:
    attractive = _score(protein_charges=[-0.5, 0, 0, 0, 0], ligand_charges=[0.5, 0.0])
    repulsive = _score(protein_charges=[0.5, 0, 0, 0, 0], ligand_charges=[0.5, 0.0])

    assert attractive.term(TERM_ELECTROSTATICS).raw_value < 0.0
    assert repulsive.term(TERM_ELECTROSTATICS).raw_value > 0.0


def test_neutral_ligand_has_no_electrostatic_contribution() -> None:
    result = _score(protein_charges=None, ligand_charges=None)

    assert result.term(TERM_ELECTROSTATICS).raw_value == 0.0
    assert result.term(TERM_ELECTROSTATICS).detail["charged_pair_count"] == 0


def test_hbond_term_requires_direction_not_just_distance() -> None:
    # Acceptor at H-bond distance from a polar protein atom, pointing at the
    # reference direction: counted.
    aligned = score_pose_v1(
        np.asarray([[0.0, 0.0, 0.0]], dtype=np.float64),
        np.asarray([[3.0, 0.0, 0.0]], dtype=np.float64),
        protein_elements=["N"],
        ligand_elements=["O"],
        pocket_center=[0.0, 0.0, 0.0],
        pocket_radius_a=6.0,
    )
    # Same distance, but the reference direction is opposite: angle-gated out.
    misaligned = score_pose_v1(
        np.asarray([[0.0, 0.0, 0.0]], dtype=np.float64),
        np.asarray([[3.0, 0.0, 0.0]], dtype=np.float64),
        protein_elements=["N"],
        ligand_elements=["O"],
        pocket_center=[9.0, 0.0, 0.0],
        pocket_radius_a=6.0,
    )

    aligned_term = aligned.term(TERM_HBOND)
    misaligned_term = misaligned.term(TERM_HBOND)

    assert aligned_term.detail["directional"] is True
    assert aligned_term.detail["accepted_hbond_count"] == 1
    assert aligned_term.raw_value < 0.0
    assert misaligned_term.detail["distance_only_candidate_count"] == 1
    assert misaligned_term.detail["accepted_hbond_count"] == 0
    assert misaligned_term.detail["angle_rejected_count"] == 1
    assert misaligned_term.raw_value == 0.0


def test_apolar_contacts_are_rewarded_by_the_hydrophobic_term() -> None:
    apolar = _score(protein_elements=["C"] * 5, ligand_elements=["C", "C"])
    polar = _score(protein_elements=["O"] * 5, ligand_elements=["O", "O"])

    assert apolar.term(TERM_HYDROPHOBIC).raw_value < 0.0
    assert apolar.term(TERM_HYDROPHOBIC).detail["apolar_pair_count"] > 0
    assert polar.term(TERM_HYDROPHOBIC).raw_value == 0.0


def test_desolvation_penalizes_buried_polar_atom_without_polar_partner() -> None:
    buried_unpaired = _score(protein_elements=["C"] * 5, ligand_elements=["O", "C"])
    paired = _score(protein_elements=["O"] * 5, ligand_elements=["O", "C"])

    assert buried_unpaired.term(TERM_DESOLVATION).raw_value > 0.0
    assert buried_unpaired.term(TERM_DESOLVATION).detail["buried_unpaired_polar_atom_count"] >= 1
    assert paired.term(TERM_DESOLVATION).raw_value == 0.0


def test_torsion_term_uses_chemistry_aware_rotors() -> None:
    flexible = _score(ligand_smiles="CCCCCC")
    rigid = _score(ligand_smiles="c1ccccc1")

    flexible_term = flexible.term(TERM_TORSION)
    assert flexible_term.detail["rotor_perception_supported"] is True
    assert flexible_term.detail["rotor_count"] == 3
    assert flexible_term.raw_value > 0.0
    assert rigid.term(TERM_TORSION).raw_value == 0.0


def test_torsion_term_reports_unsupported_for_macrocycle() -> None:
    result = _score(ligand_smiles="C1CCCCCCCCCCCC1")

    assert result.term(TERM_TORSION).detail["rotor_perception_supported"] is False
    assert result.term(TERM_TORSION).raw_value == 0.0


def test_strain_term_penalizes_internal_clash() -> None:
    strained = _score(
        ligand_xyz=np.asarray(
            [[1.5, 1.0, 1.0], [2.5, 1.0, 1.0], [1.6, 1.0, 1.0]], dtype=np.float64
        ),
        ligand_elements=["C", "C", "C"],
    )
    clean = _score()

    assert strained.term(TERM_STRAIN).raw_value > 0.0
    assert strained.term(TERM_STRAIN).detail["internal_clash_count"] >= 1
    assert clean.term(TERM_STRAIN).raw_value == 0.0


def test_pocket_prior_is_weak_and_bounded() -> None:
    centred = _score()
    far = _score(pocket_center=[40.0, 40.0, 40.0])

    prior = far.term(TERM_POCKET_PRIOR)
    assert prior.detail["weak_prior"] is True
    assert prior.raw_value <= 2.0
    assert prior.raw_value > centred.term(TERM_POCKET_PRIOR).raw_value
    # The prior must be the smallest weight so it cannot drive ranking.
    assert prior.weight == min(DEFAULT_TERM_WEIGHTS.values())


def test_term_weights_can_be_overridden_without_changing_raw_values() -> None:
    default = _score()
    reweighted = _score(term_weights={TERM_HBOND: 0.0})

    assert reweighted.term(TERM_HBOND).weight == 0.0
    assert reweighted.term(TERM_HBOND).raw_value == default.term(TERM_HBOND).raw_value
    assert reweighted.term(TERM_HBOND).weighted_value == 0.0


def test_empty_coordinates_are_blocked() -> None:
    result = score_pose_v1(np.zeros((0, 3)), LIGAND)

    assert result.status == STATUS_BLOCKED_EMPTY
    assert result.ready is False
    assert result.terms == ()
    assert "scorer_v1_requires_protein_and_ligand_coordinates" in result.blockers


def test_scoring_is_deterministic() -> None:
    assert _score().total_score == _score().total_score


def test_payload_states_uncalibrated_ranking_boundary() -> None:
    payload = _score().to_dict()

    assert "not a binding free energy" in payload["claim_boundary"]
    assert "uncalibrated" in payload["claim_boundary"]
