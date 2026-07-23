from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from betelgeuze_engine_v2.docking.pdbqt_uff_diagnostic_scoring import (
    PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID,
    PdbqtUffDiagnosticScoreConfig,
    PdbqtUffDiagnosticScoringError,
    PdbqtUffNonbondedAtomParameter,
    UncalibratedPdbqtUffDiagnosticScorer,
    coordinate_sha256,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _QuadraticStrain:
    evaluator_id = "fixture-quadratic-strain"
    evaluator_version = "1.0.0"
    source_atom_count = 1
    parameter_source_sha256 = _sha("strain-parameters")
    config_fingerprint_sha256 = _sha("strain-config")

    def energy_kcal_per_mol(self, coordinates: np.ndarray) -> float:
        assert coordinates.dtype == np.float64
        assert coordinates.shape == (1, 3)
        return float(np.sum(coordinates * coordinates, dtype=np.float64))


def _parameter(
    atom_id: str,
    *,
    charge: float,
    x1: float = 3.0,
    d1: float = 0.1,
    atomic_number: int = 6,
    atom_type: str = "C",
) -> PdbqtUffNonbondedAtomParameter:
    return PdbqtUffNonbondedAtomParameter(
        atom_id=atom_id,
        atomic_number=atomic_number,
        partial_charge_e=charge,
        uff_x1_angstrom=x1,
        uff_d1_kcal_per_mol=d1,
        autodock4_atom_type=atom_type,
        parameter_source_sha256=_sha(f"parameter:{atom_id}"),
    )


def _scorer(
    *,
    config: PdbqtUffDiagnosticScoreConfig | None = None,
) -> UncalibratedPdbqtUffDiagnosticScorer:
    return UncalibratedPdbqtUffDiagnosticScorer(
        np.asarray([[0.0, 0.0, 0.0]], dtype=np.float64),
        (_parameter("receptor:1", charge=1.0),),
        np.asarray([[3.0, 0.0, 0.0]], dtype=np.float64),
        (_parameter("ligand:1", charge=-1.0),),
        (0,),
        _QuadraticStrain(),
        config=config
        or PdbqtUffDiagnosticScoreConfig(
            cutoff_angstrom=10.0,
            switch_start_angstrom=9.0,
            softcore_distance_angstrom=1.0e-9,
        ),
    )


def test_exact_four_term_decomposition_and_diagnostics() -> None:
    scorer = _scorer()
    pose = np.asarray([[3.0, 0.0, 0.0]], dtype=np.float64)
    breakdown, diagnostics = scorer.score_coordinates("pose:1", pose)
    terms = {term.term_id: term for term in breakdown.terms}

    assert set(terms) == {
        "uff_receptor_ligand_vdw",
        "pdbqt_receptor_ligand_coulomb",
        "rdkit_uff_source_atom_strain_delta",
        "uff_vdw_overlap_penalty",
    }
    assert terms["uff_receptor_ligand_vdw"].raw_value == pytest.approx(
        -0.1,
        abs=1.0e-15,
    )
    assert terms["pdbqt_receptor_ligand_coulomb"].raw_value == pytest.approx(
        -COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / 4.0 / 3.0,
        rel=1.0e-15,
    )
    assert terms["rdkit_uff_source_atom_strain_delta"].raw_value == 0.0
    assert terms["uff_vdw_overlap_penalty"].raw_value == 0.0
    assert breakdown.total_score == pytest.approx(
        -0.1 - COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / 4.0 / 3.0,
        rel=1.0e-15,
    )
    assert breakdown.claim_safe is False
    assert "diagnostic_score_uncalibrated" in breakdown.blockers
    assert diagnostics.total_cross_pair_count == 1
    assert diagnostics.evaluated_cross_pair_count == 1
    assert diagnostics.clashing_cross_pair_count == 0
    assert diagnostics.minimum_cross_distance_angstrom == 3.0
    assert diagnostics.coordinate_sha256 == coordinate_sha256(pose)
    assert diagnostics.ligand_reference_energy_kcal_per_mol == 9.0
    assert diagnostics.ligand_pose_energy_kcal_per_mol == 9.0


def test_strain_and_overlap_are_bound_to_the_exact_candidate() -> None:
    scorer = _scorer()
    pose = np.asarray([[2.0, 0.0, 0.0]], dtype=np.float64)
    breakdown, diagnostics = scorer.score_coordinates("pose:2", pose)
    terms = {term.term_id: term for term in breakdown.terms}

    assert terms["rdkit_uff_source_atom_strain_delta"].raw_value == -5.0
    assert terms["uff_vdw_overlap_penalty"].raw_value == pytest.approx(0.625)
    assert diagnostics.clashing_cross_pair_count == 1
    assert diagnostics.maximum_cross_overlap_angstrom == pytest.approx(0.25)
    assert diagnostics.ligand_pose_energy_kcal_per_mol == 4.0
    assert math.isfinite(breakdown.total_score)


def test_no_cross_pairs_retains_exact_strain_observation() -> None:
    scorer = _scorer(
        config=PdbqtUffDiagnosticScoreConfig(
            cutoff_angstrom=4.0,
            switch_start_angstrom=3.0,
        )
    )
    pose = np.asarray([[20.0, 0.0, 0.0]], dtype=np.float64)
    breakdown, diagnostics = scorer.score_coordinates("pose:far", pose)
    terms = {term.term_id: term.raw_value for term in breakdown.terms}

    assert terms["uff_receptor_ligand_vdw"] == 0.0
    assert terms["pdbqt_receptor_ligand_coulomb"] == 0.0
    assert terms["uff_vdw_overlap_penalty"] == 0.0
    assert terms["rdkit_uff_source_atom_strain_delta"] == 391.0
    assert diagnostics.evaluated_cross_pair_count == 0
    assert diagnostics.minimum_cross_distance_angstrom is None


def test_rejects_invalid_parameter_coordinate_and_capacity_contracts() -> None:
    with pytest.raises(
        PdbqtUffDiagnosticScoringError,
        match="outside the diagnostic scope",
    ):
        _parameter(
            "metal",
            charge=0.0,
            atomic_number=26,
            atom_type="Fe",
        )

    with pytest.raises(
        PdbqtUffDiagnosticScoringError,
        match="cross-pair capacity exceeded",
    ):
        UncalibratedPdbqtUffDiagnosticScorer(
            np.asarray(
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                dtype=np.float64,
            ),
            (
                _parameter("receptor:1", charge=1.0),
                _parameter("receptor:2", charge=0.0),
            ),
            np.asarray([[3.0, 0.0, 0.0]], dtype=np.float64),
            (_parameter("ligand:1", charge=-1.0),),
            (0,),
            _QuadraticStrain(),
            config=PdbqtUffDiagnosticScoreConfig(max_cross_pairs=1),
        )

    scorer = _scorer()
    with pytest.raises(
        PdbqtUffDiagnosticScoringError,
        match="NumPy float64",
    ):
        scorer.score_coordinates(
            "pose",
            np.asarray([[3.0, 0.0, 0.0]], dtype=np.float32),
        )
    with pytest.raises(
        PdbqtUffDiagnosticScoringError,
        match="bounded single-line",
    ):
        scorer.score_coordinates(
            "bad\npose",
            np.asarray([[3.0, 0.0, 0.0]], dtype=np.float64),
        )


def test_config_and_coordinate_identities_are_deterministic() -> None:
    config = PdbqtUffDiagnosticScoreConfig()
    assert config.schema_id == PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID
    assert config.fingerprint_sha256 == PdbqtUffDiagnosticScoreConfig().fingerprint_sha256
    coordinates = np.asarray(
        [[1.0, -0.0, 3.5], [4.0, 5.0, 6.0]],
        dtype=np.float64,
    )
    assert coordinate_sha256(coordinates) == coordinate_sha256(coordinates.copy())
    changed = coordinates.copy()
    changed[0, 0] += 1.0e-12
    assert coordinate_sha256(changed) != coordinate_sha256(coordinates)
