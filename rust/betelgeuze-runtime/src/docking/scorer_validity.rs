use std::collections::HashMap;

use super::{
    bool_from_abi, coordinate_segment, digest_present, numeric_matches, sys,
    validity_cell_component, Backend, Error, ErrorCode, IndependentScorerContext,
    IndependentScorerFailureCode, IndependentScorerOutcome, IndependentValidityChecks,
    IndependentValidityContext, IndependentValidityFailureCode, IndependentValidityMeasurements,
    IndependentValidityOutcome, Quaternion, Result, Vec3,
};

fn scorer_failure_rank_evidence_is_zero(row: &sys::bg_docking_scorer_v1_row_v1) -> bool {
    row.weighted_terms.iter().all(|value| *value == 0.0)
        && row.total_score == 0.0
        && row.hbond_count == 0
        && row.hydrophobic_contact_count == 0
        && row.buried_polar_count == 0
}

fn scorer_failure_pair_evidence_is_valid(row: &sys::bg_docking_scorer_v1_row_v1) -> bool {
    match row.failure_code {
        sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
        | sys::BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES => {
            row.receptor_candidate_pair_count == 0 && row.ligand_pair_count == 0
        }
        sys::BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY => {
            row.receptor_candidate_pair_count > 0 && row.ligand_pair_count == 0
        }
        sys::BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY => row.ligand_pair_count > 0,
        sys::BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR
        | sys::BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE => true,
        _ => false,
    }
}

fn independent_scorer_failure_code(code: IndependentScorerFailureCode) -> i32 {
    match code {
        IndependentScorerFailureCode::ProposalGenerationFailure
        | IndependentScorerFailureCode::SeverePenetrationRejected => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
        }
        IndependentScorerFailureCode::InvalidCandidateCoordinates => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES
        }
        IndependentScorerFailureCode::ReceptorCandidatePairCapacityExceeded => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY
        }
        IndependentScorerFailureCode::LigandPairCapacityExceeded => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY
        }
        IndependentScorerFailureCode::DegenerateRotorGeometry => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR
        }
        IndependentScorerFailureCode::NonfiniteScore => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE
        }
    }
}

fn validity_measurements_are_finite(row: &sys::bg_docking_pose_validity_row_v1) -> bool {
    [
        row.rotation_orthogonality_max_error,
        row.rotation_determinant,
        row.max_bond_length_delta_angstrom,
        row.minimum_ligand_nonbonded_distance_angstrom,
        row.minimum_receptor_ligand_distance_angstrom,
        row.minimum_declared_chiral_volume,
        row.maximum_pocket_center_distance_angstrom,
        row.element_vdw_ligand_minimum_distance_angstrom,
        row.element_vdw_ligand_minimum_ratio,
        row.element_vdw_receptor_minimum_distance_angstrom,
        row.element_vdw_receptor_minimum_ratio,
    ]
    .iter()
    .all(|value| value.is_finite())
}

fn validity_failure_evidence_is_zero(row: &sys::bg_docking_pose_validity_row_v1) -> bool {
    row.passed_check_mask == 0
        && row.blocker_mask == 0
        && row.atom_count == 0
        && row.rotation_orthogonality_max_error == 0.0
        && row.rotation_determinant == 0.0
        && row.max_bond_length_delta_angstrom == 0.0
        && row.minimum_ligand_nonbonded_distance_angstrom == 0.0
        && row.evaluated_ligand_nonbonded_pair_count == 0
        && row.excluded_ligand_pair_count == 0
        && row.minimum_receptor_ligand_distance_angstrom == 0.0
        && row.evaluated_receptor_ligand_pair_count == 0
        && row.minimum_declared_chiral_volume == 0.0
        && row.declared_chirality_center_count == 0
        && row.maximum_pocket_center_distance_angstrom == 0.0
        && row.element_vdw_ligand_pair_count == 0
        && row.element_vdw_ligand_severe_overlap_count == 0
        && row.element_vdw_ligand_minimum_distance_angstrom == 0.0
        && row.element_vdw_ligand_minimum_ratio == 0.0
        && row.element_vdw_receptor_candidate_pair_count == 0
        && row.element_vdw_receptor_full_cartesian_pair_count == 0
        && row.element_vdw_receptor_cell_count == 0
        && row.element_vdw_receptor_severe_overlap_count == 0
        && row.element_vdw_receptor_minimum_distance_angstrom == 0.0
        && row.element_vdw_receptor_minimum_ratio == 0.0
}

pub(super) fn independent_validity_check_mask(checks: IndependentValidityChecks) -> u32 {
    let mut mask = 0_u32;
    for (passed, bit) in [
        (
            checks.proper_rotation(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION,
        ),
        (
            checks.bond_lengths_preserved(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS,
        ),
        (
            checks.ligand_self_clash_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_LIGAND_SELF_CLASH,
        ),
        (
            checks.receptor_ligand_clash_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH,
        ),
        (
            checks.declared_chirality_preserved(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_CHIRALITY,
        ),
        (
            checks.inside_declared_pocket(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET,
        ),
        (
            checks.element_vdw_ligand_overlap_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW,
        ),
        (
            checks.element_vdw_receptor_overlap_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW,
        ),
    ] {
        if passed {
            mask |= bit;
        }
    }
    mask
}

fn independent_validity_failure_code(
    value: IndependentValidityFailureCode,
) -> sys::bg_docking_pose_validity_failure {
    match value {
        IndependentValidityFailureCode::UpstreamScorerFailure => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER
        }
        IndependentValidityFailureCode::InvalidCandidateCoordinates => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES
        }
        IndependentValidityFailureCode::LigandPairCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY
        }
        IndependentValidityFailureCode::ReceptorCrossCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY
        }
        IndependentValidityFailureCode::ElementLigandPairCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY
        }
        IndependentValidityFailureCode::ElementReceptorCandidateCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY
        }
        IndependentValidityFailureCode::NonfiniteDerivedMeasurement => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT
        }
    }
}

fn independent_validity_measurements_match(
    backend: Backend,
    expected: IndependentValidityMeasurements,
    observed: &sys::bg_docking_pose_validity_row_v1,
) -> bool {
    observed.atom_count == expected.atom_count() as u64
        && observed.evaluated_ligand_nonbonded_pair_count
            == expected.evaluated_ligand_nonbonded_pair_count() as u64
        && observed.excluded_ligand_pair_count == expected.excluded_ligand_pair_count() as u64
        && observed.evaluated_receptor_ligand_pair_count
            == expected.evaluated_receptor_ligand_pair_count() as u64
        && observed.declared_chirality_center_count
            == expected.declared_chirality_center_count() as u64
        && observed.element_vdw_ligand_pair_count == expected.element_vdw_ligand_pair_count() as u64
        && observed.element_vdw_ligand_severe_overlap_count
            == expected.element_vdw_ligand_severe_overlap_count() as u64
        && observed.element_vdw_receptor_candidate_pair_count
            == expected.element_vdw_receptor_candidate_pair_count() as u64
        && observed.element_vdw_receptor_full_cartesian_pair_count
            == expected.element_vdw_receptor_full_cartesian_pair_count() as u64
        && observed.element_vdw_receptor_cell_count
            == expected.element_vdw_receptor_cell_count() as u64
        && observed.element_vdw_receptor_severe_overlap_count
            == expected.element_vdw_receptor_severe_overlap_count() as u64
        && [
            (
                expected.rotation_orthogonality_max_error(),
                observed.rotation_orthogonality_max_error,
            ),
            (
                expected.rotation_determinant(),
                observed.rotation_determinant,
            ),
            (
                expected.max_bond_length_delta_angstrom(),
                observed.max_bond_length_delta_angstrom,
            ),
            (
                expected.minimum_ligand_nonbonded_distance_angstrom(),
                observed.minimum_ligand_nonbonded_distance_angstrom,
            ),
            (
                expected.minimum_receptor_ligand_distance_angstrom(),
                observed.minimum_receptor_ligand_distance_angstrom,
            ),
            (
                expected.minimum_declared_chiral_volume(),
                observed.minimum_declared_chiral_volume,
            ),
            (
                expected.maximum_pocket_center_distance_angstrom(),
                observed.maximum_pocket_center_distance_angstrom,
            ),
            (
                expected.element_vdw_ligand_minimum_distance_angstrom(),
                observed.element_vdw_ligand_minimum_distance_angstrom,
            ),
            (
                expected.element_vdw_ligand_minimum_ratio(),
                observed.element_vdw_ligand_minimum_ratio,
            ),
            (
                expected.element_vdw_receptor_minimum_distance_angstrom(),
                observed.element_vdw_receptor_minimum_distance_angstrom,
            ),
            (
                expected.element_vdw_receptor_minimum_ratio(),
                observed.element_vdw_receptor_minimum_ratio,
            ),
        ]
        .iter()
        .all(|(expected, observed)| numeric_matches(backend, *expected, *observed))
}

fn validity_receptor_candidate_pair_count(
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
    cell_size: f64,
    receptor_cells: &HashMap<(i64, i64, i64), u64>,
) -> Result<u64> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity ligand count does not fit usize",
        )
    })?;
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity coordinate offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity coordinate end overflowed",
        )
    })?;
    if coordinates
        .iter()
        .any(|channel| channel.get(begin..end).is_none())
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity coordinate segment exceeds its buffer",
        ));
    }
    let mut count = 0_u64;
    for ((x, y), z) in coordinates[0][begin..end]
        .iter()
        .zip(&coordinates[1][begin..end])
        .zip(&coordinates[2][begin..end])
    {
        let key = (
            validity_cell_component(*x, cell_size).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity x coordinate has an invalid cell key",
                )
            })?,
            validity_cell_component(*y, cell_size).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity y coordinate has an invalid cell key",
                )
            })?,
            validity_cell_component(*z, cell_size).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity z coordinate has an invalid cell key",
                )
            })?,
        );
        for dx in -1_i64..=1 {
            for dy in -1_i64..=1 {
                for dz in -1_i64..=1 {
                    let neighbor = (
                        key.0.checked_add(dx).ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity x cell neighbor overflowed",
                            )
                        })?,
                        key.1.checked_add(dy).ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity y cell neighbor overflowed",
                            )
                        })?,
                        key.2.checked_add(dz).ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity z cell neighbor overflowed",
                            )
                        })?,
                    );
                    count = count
                        .checked_add(receptor_cells.get(&neighbor).copied().unwrap_or(0))
                        .ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity receptor candidate count overflowed",
                            )
                        })?;
                }
            }
        }
    }
    Ok(count)
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_scorer_and_validity_evidence(
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    refinement_rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    post_admission_rows: &[sys::bg_docking_geometric_admission_row_v1],
    ligand_atom_count: u64,
    receptor_atom_count: u64,
    exclusion_count: u64,
    chirality_count: u64,
    contact_cell_size_angstrom: f64,
    receptor_cells: &HashMap<(i64, i64, i64), u64>,
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
    independent_scorer_context: &IndependentScorerContext,
    independent_context: &IndependentValidityContext,
    backend: Backend,
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    if scorer_rows.len() != candidate_count
        || validity_rows.len() != candidate_count
        || ranking_rows.len() != candidate_count
        || refinement_rows.len() != candidate_count
        || post_admission_rows.len() != candidate_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 scorer, validity, or ranking denominator is invalid",
        ));
    }
    let total_ligand_pairs = ligand_atom_count
        .checked_mul(ligand_atom_count.checked_sub(1).ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 validity ligand denominator underflowed",
            )
        })?)
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 validity ligand-pair denominator overflowed",
            )
        })?;
    let evaluated_ligand_pairs =
        total_ligand_pairs
            .checked_sub(exclusion_count)
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity exclusions exceed the ligand-pair denominator",
                )
            })?;
    let receptor_pairs = ligand_atom_count
        .checked_mul(receptor_atom_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 validity receptor-pair denominator overflowed",
            )
        })?;
    let receptor_cell_count = u64::try_from(receptor_cells.len()).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity receptor-cell count does not fit u64",
        )
    })?;
    for slot in 0..candidate_count {
        let scorer = &scorer_rows[slot];
        let validity = &validity_rows[slot];
        let ranking = &ranking_rows[slot];
        if scorer.slot_index as usize != slot
            || scorer.reserved0 != 0
            || scorer.reserved.iter().any(|value| *value != 0)
            || validity.slot_index as usize != slot
            || validity.reserved.iter().any(|value| *value != 0)
            || ranking.slot_index as usize != slot
            || ranking.reserved0 != 0
            || ranking.reserved.iter().any(|value| *value != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 scorer, validity, or ranking row ABI shape is invalid",
            ));
        }
        let coordinate_ready =
            refinement_rows[slot].status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
        let post_admitted = coordinate_ready
            && post_admission_rows[slot].status
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
            && post_admission_rows[slot].decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && post_admission_rows[slot].rank_eligible == 1;
        if !post_admitted {
            if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
                || scorer.failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
                || !scorer_failure_rank_evidence_is_zero(scorer)
                || scorer.receptor_candidate_pair_count != 0
                || scorer.ligand_pair_count != 0
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 inactive scorer row disagrees with refinement eligibility",
                ));
            }
        } else {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 scorer ligand denominator does not fit usize",
                )
            })?;
            let owned =
                coordinate_segment(final_coordinates, slot, ligand_count).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 scorer coordinates exceed their owned buffer",
                    )
                })?;
            let coordinates = (0..ligand_count)
                .map(|atom| {
                    Vec3::new(
                        owned.x_angstrom[atom],
                        owned.y_angstrom[atom],
                        owned.z_angstrom[atom],
                    )
                })
                .collect::<Vec<_>>();
            let independent = independent_scorer_context
                .score_coordinates(&coordinates)
                .map_err(|error| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!("independent fixed64 scorer evaluation failed: {error}"),
                    )
                })?;
            match independent {
                IndependentScorerOutcome::Scored(expected) => {
                    let term_sum = scorer.weighted_terms.iter().copied().sum::<f64>();
                    let terms_match = expected
                        .weighted_terms()
                        .into_iter()
                        .zip(scorer.weighted_terms)
                        .all(|(expected, observed)| numeric_matches(backend, expected, observed));
                    let count_matches = [
                        (
                            expected.receptor_candidate_pair_count(),
                            scorer.receptor_candidate_pair_count,
                        ),
                        (expected.ligand_pair_count(), scorer.ligand_pair_count),
                        (expected.hbond_count(), scorer.hbond_count),
                        (
                            expected.hydrophobic_contact_count(),
                            scorer.hydrophobic_contact_count,
                        ),
                        (expected.buried_polar_count(), scorer.buried_polar_count),
                    ]
                    .into_iter()
                    .all(|(expected, observed)| u64::try_from(expected).ok() == Some(observed));
                    if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_SCORED
                        || scorer.failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_NONE
                        || !scorer.total_score.is_finite()
                        || scorer.weighted_terms.iter().any(|value| !value.is_finite())
                        || (term_sum - scorer.total_score).abs() > 1.0e-12
                        || !terms_match
                        || !numeric_matches(backend, expected.total_score(), scorer.total_score)
                        || !count_matches
                    {
                        return Err(Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 scored terms, score, or counts disagree with independent replay",
                        ));
                    }
                }
                IndependentScorerOutcome::TypedFailure(expected) => {
                    let receptor_count =
                        u64::try_from(expected.receptor_candidate_pair_count()).ok();
                    let ligand_count = u64::try_from(expected.ligand_pair_count()).ok();
                    if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
                        || scorer.failure_code
                            != independent_scorer_failure_code(expected.failure_code())
                        || !scorer_failure_rank_evidence_is_zero(scorer)
                        || !scorer_failure_pair_evidence_is_valid(scorer)
                        || receptor_count != Some(scorer.receptor_candidate_pair_count)
                        || ligand_count != Some(scorer.ligand_pair_count)
                    {
                        return Err(Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 scorer typed failure disagrees with independent replay",
                        ));
                    }
                }
            }
        }
        if validity.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity ligand denominator does not fit usize",
                )
            })?;
            let owned =
                coordinate_segment(final_coordinates, slot, ligand_count).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 validity coordinates exceed their owned buffer",
                    )
                })?;
            let coordinates = (0..ligand_count)
                .map(|atom| {
                    Vec3::new(
                        owned.x_angstrom[atom],
                        owned.y_angstrom[atom],
                        owned.z_angstrom[atom],
                    )
                })
                .collect::<Vec<_>>();
            let quaternion = Quaternion::new(
                final_quaternions[0][slot],
                final_quaternions[1][slot],
                final_quaternions[2][slot],
                final_quaternions[3][slot],
            );
            let independent = independent_context
                .evaluate_coordinates(&coordinates, quaternion)
                .map_err(|error| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!("independent fixed64 validity evaluation failed: {error}"),
                    )
                })?;
            let (expected_checks, expected_measurements) = match independent {
                IndependentValidityOutcome::Evaluated {
                    checks,
                    measurements,
                } => (checks, measurements),
                IndependentValidityOutcome::TypedFailure(_) => {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 validity reported evaluated evidence for an independently typed failure",
                    ));
                }
            };
            let expected_mask = independent_validity_check_mask(expected_checks);
            let unknown_checks =
                validity.passed_check_mask & !sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
            if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_SCORED
                || validity.failure_code != sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE
                || validity.upstream_scorer_failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_NONE
                || unknown_checks != 0
                || validity.blocker_mask
                    != (sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ validity.passed_check_mask)
                || validity.observed_count != 0
                || validity.atom_count != ligand_atom_count
                || !validity_measurements_are_finite(validity)
                || validity.passed_check_mask != expected_mask
                || validity.blocker_mask
                    != (sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ expected_mask)
                || !independent_validity_measurements_match(
                    backend,
                    expected_measurements,
                    validity,
                )
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 evaluated validity evidence is invalid",
                ));
            }
            let receptor_candidate_pairs = validity_receptor_candidate_pair_count(
                final_coordinates,
                slot,
                ligand_atom_count,
                contact_cell_size_angstrom,
                receptor_cells,
            )?;
            let ligand_vdw_passed = validity.passed_check_mask
                & sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW
                != 0;
            let receptor_vdw_passed = validity.passed_check_mask
                & sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW
                != 0;
            if validity.evaluated_ligand_nonbonded_pair_count != evaluated_ligand_pairs
                || validity.excluded_ligand_pair_count != exclusion_count
                || validity.element_vdw_ligand_pair_count != evaluated_ligand_pairs
                || validity.element_vdw_ligand_severe_overlap_count > evaluated_ligand_pairs
                || validity.evaluated_receptor_ligand_pair_count != receptor_pairs
                || validity.declared_chirality_center_count != chirality_count
                || validity.element_vdw_receptor_candidate_pair_count != receptor_candidate_pairs
                || validity.element_vdw_receptor_full_cartesian_pair_count != receptor_pairs
                || validity.element_vdw_receptor_cell_count != receptor_cell_count
                || validity.element_vdw_receptor_severe_overlap_count > receptor_candidate_pairs
                || ligand_vdw_passed != (validity.element_vdw_ligand_severe_overlap_count == 0)
                || receptor_vdw_passed != (validity.element_vdw_receptor_severe_overlap_count == 0)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity measurement denominators are inconsistent",
                ));
            }
        } else {
            if !validity_failure_evidence_is_zero(validity) {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 failed validity row retained measurements",
                ));
            }
            let valid_upstream_failure = validity.status
                == sys::BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE
                && scorer.status == sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
                && validity.failure_code == sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER
                && validity.upstream_scorer_failure_code == scorer.failure_code
                && validity.observed_count == 0;
            let valid_typed_failure = validity.status
                == sys::BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE
                && scorer.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED
                && validity.failure_code
                    >= sys::BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES
                && validity.failure_code
                    <= sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT
                && validity.upstream_scorer_failure_code == sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            if !valid_upstream_failure && !valid_typed_failure {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity failure is cross-wired",
                ));
            }
            if valid_typed_failure {
                let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 validity ligand denominator does not fit usize",
                    )
                })?;
                let owned =
                    coordinate_segment(final_coordinates, slot, ligand_count).ok_or_else(|| {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 validity coordinates exceed their owned buffer",
                        )
                    })?;
                let coordinates = (0..ligand_count)
                    .map(|atom| {
                        Vec3::new(
                            owned.x_angstrom[atom],
                            owned.y_angstrom[atom],
                            owned.z_angstrom[atom],
                        )
                    })
                    .collect::<Vec<_>>();
                let quaternion = Quaternion::new(
                    final_quaternions[0][slot],
                    final_quaternions[1][slot],
                    final_quaternions[2][slot],
                    final_quaternions[3][slot],
                );
                match independent_context
                    .evaluate_coordinates(&coordinates, quaternion)
                    .map_err(|error| {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            format!("independent fixed64 validity evaluation failed: {error}"),
                        )
                    })? {
                    IndependentValidityOutcome::TypedFailure(failure)
                        if validity.failure_code
                            == independent_validity_failure_code(failure.failure_code())
                            && validity.observed_count == failure.observed_count() as u64 => {}
                    _ => {
                        return Err(Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 validity typed failure disagrees with independent evaluation",
                        ));
                    }
                }
            }
        }
        let rank_eligible = bool_from_abi(ranking.rank_eligible, "rank eligibility")?;
        let valid_rank_eligible =
            bool_from_abi(ranking.valid_rank_eligible, "valid-rank eligibility")?;
        if !rank_eligible
            && (valid_rank_eligible
                || ranking.stable_rank != 0
                || ranking.stable_valid_rank != 0
                || ranking.total_score != 0.0
                || digest_present(&ranking.coordinate_sha256))
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 ineligible ranking row retained score or coordinate evidence",
            ));
        }
    }
    Ok(())
}
