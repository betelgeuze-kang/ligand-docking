//! Native rigid-refinement evidence validation and independent source-pose replay.

use betelgeuze_docking_search::{
    refine_interaction_aware_rigid_v2, refine_interaction_aware_rigid_v3,
    refine_interaction_aware_rigid_v6, Fixed64GeometricInput as IndependentFixed64GeometricInput,
    NativeRigidRefinementContext as IndependentRigidContext,
    NativeRigidRefinementError as IndependentRigidError,
    NativeRigidRefinementErrorCode as IndependentRigidErrorCode,
    NativeRigidRefinementOutcome as IndependentRigidOutcome,
    NativeRigidRefinementProfile as IndependentRigidProfile,
    NativeRigidV2Config as IndependentRigidV2Config,
    NativeRigidV3Config as IndependentRigidV3Config, Vec3,
};
use betelgeuze_sys as sys;

use super::{
    bool_from_abi, coordinate_segment, coordinate_segment_matches, numeric_matches, Backend, Error,
    ErrorCode, Result,
};

pub(super) fn independent_rigid_v2_config(
    value: &sys::bg_docking_rigid_v2_config_v1,
) -> Result<IndependentRigidV2Config> {
    Ok(IndependentRigidV2Config {
        overlap_scale: value.overlap_scale,
        maximum_step_angstrom: value.maximum_step_angstrom,
        minimum_step_angstrom: value.minimum_step_angstrom,
        maximum_total_translation_angstrom: value.maximum_total_translation_angstrom,
        maximum_backtracking_evaluations: usize::try_from(value.maximum_backtracking_evaluations)
            .map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 rigid backtracking budget does not fit usize",
            )
        })?,
        penalty_tolerance: value.penalty_tolerance,
        epsilon_angstrom: value.epsilon_angstrom,
    })
}

pub(super) fn independent_rigid_v3_config(
    value: &sys::bg_docking_rigid_v3_config_v1,
) -> Result<IndependentRigidV3Config> {
    Ok(IndependentRigidV3Config {
        v2: independent_rigid_v2_config(&value.v2)?,
        maximum_rotation_step_radians: value.maximum_rotation_step_radians,
        minimum_rotation_step_radians: value.minimum_rotation_step_radians,
        maximum_total_rotation_radians: value.maximum_total_rotation_radians,
        maximum_rotation_steps: usize::try_from(value.maximum_rotation_steps).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 rigid rotation budget does not fit usize",
            )
        })?,
        minimum_rotation_relative_penalty_reduction: value
            .minimum_rotation_relative_penalty_reduction,
        maximum_centroid_offset_angstrom: value.maximum_centroid_offset_angstrom,
    })
}

fn rigid_evidence_values(value: &sys::bg_docking_rigid_refinement_evidence_v1) -> [f64; 13] {
    [
        value.initial_penalty,
        value.final_penalty,
        value.total_translation_angstrom[0],
        value.total_translation_angstrom[1],
        value.total_translation_angstrom[2],
        value.total_rotation_vector_radians[0],
        value.total_rotation_vector_radians[1],
        value.total_rotation_vector_radians[2],
        value.total_rotation_path_radians,
        value.initial_centroid_offset_angstrom,
        value.final_centroid_offset_angstrom,
        value.maximum_centroid_offset_angstrom,
        value.accepted_steps as f64,
    ]
}

fn rigid_evidence_is_zero(value: &sys::bg_docking_rigid_refinement_evidence_v1) -> bool {
    value.profile == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE
        && value.available == 0
        && value.reserved0.iter().all(|item| *item == 0)
        && value.accepted_steps == 0
        && value.accepted_translation_steps == 0
        && value.accepted_rotation_steps == 0
        && value.line_search_evaluation_count == 0
        && value.fallback_direction_step_count == 0
        && rigid_evidence_values(value)
            .iter()
            .take(12)
            .all(|item| *item == 0.0)
        && value.reserved.iter().all(|item| *item == 0)
}

fn rigid_evidence_is_consistent(
    value: &sys::bg_docking_rigid_refinement_evidence_v1,
) -> Result<bool> {
    let available = bool_from_abi(value.available, "rigid evidence availability")?;
    if !available {
        return Ok(rigid_evidence_is_zero(value));
    }
    let values = rigid_evidence_values(value);
    let rotation_norm = values[5].hypot(values[6]).hypot(values[7]);
    Ok(value.reserved0.iter().all(|item| *item == 0)
        && value.reserved.iter().all(|item| *item == 0)
        && value.profile >= sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
        && value.profile <= sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4
        && value.accepted_translation_steps <= value.accepted_steps
        && value.accepted_rotation_steps == value.accepted_steps - value.accepted_translation_steps
        && value.fallback_direction_step_count <= value.accepted_steps
        && values.iter().all(|item| item.is_finite())
        && value.initial_penalty >= 0.0
        && value.final_penalty >= 0.0
        && value.total_rotation_path_radians >= 0.0
        && rotation_norm.is_finite()
        && rotation_norm <= value.total_rotation_path_radians + 2.0e-12
        && (value.accepted_rotation_steps != 0
            || (rotation_norm == 0.0 && value.total_rotation_path_radians == 0.0)))
}

fn rigid_evidence_equal(
    left: &sys::bg_docking_rigid_refinement_evidence_v1,
    right: &sys::bg_docking_rigid_refinement_evidence_v1,
) -> bool {
    left.profile == right.profile
        && left.available == right.available
        && left.accepted_steps == right.accepted_steps
        && left.accepted_translation_steps == right.accepted_translation_steps
        && left.accepted_rotation_steps == right.accepted_rotation_steps
        && left.line_search_evaluation_count == right.line_search_evaluation_count
        && left.fallback_direction_step_count == right.fallback_direction_step_count
        && rigid_evidence_values(left)[..12] == rigid_evidence_values(right)[..12]
}

fn validate_rigid_coordinate_channel(
    evidence: &sys::bg_docking_rigid_refinement_evidence_v1,
    coordinates: &[Vec<f64>; 12],
    first_channel: usize,
    slot: usize,
    ligand_atom_count: u64,
) -> Result<bool> {
    let channels = [
        coordinates[first_channel].as_slice(),
        coordinates[first_channel + 1].as_slice(),
        coordinates[first_channel + 2].as_slice(),
    ];
    coordinate_segment_matches(&channels, slot, ligand_atom_count, evidence.available == 0)
}

pub(super) fn validate_rigid_row_semantics(
    row: &sys::bg_docking_rigid_refinement_row_v1,
    requested_mode: sys::bg_docking_rigid_refinement_candidate_mode,
    requested_max_steps: u64,
    coordinates: &[Vec<f64>; 12],
    slot: usize,
    ligand_atom_count: u64,
) -> Result<()> {
    let baseline_duplicate =
        bool_from_abi(row.baseline_duplicate_of_v2, "rigid baseline duplicate")?;
    let clearance_evaluated = bool_from_abi(row.clearance_evaluated, "rigid clearance evaluation")?;
    let clearance_selected = bool_from_abi(row.clearance_selected, "rigid clearance selection")?;
    if row.slot_index as usize != slot
        || row.candidate_mode != requested_mode
        || row.reserved0 != 0
        || row.reserved.iter().any(|item| *item != 0)
        || !rigid_evidence_is_consistent(&row.selected)?
        || !rigid_evidence_is_consistent(&row.comparison_v2)?
        || !rigid_evidence_is_consistent(&row.baseline_v3)?
        || !rigid_evidence_is_consistent(&row.clearance_v4)?
        || [
            &row.selected,
            &row.comparison_v2,
            &row.baseline_v3,
            &row.clearance_v4,
        ]
        .iter()
        .any(|evidence| evidence.available == 1 && evidence.accepted_steps > requested_max_steps)
        || !validate_rigid_coordinate_channel(
            &row.selected,
            coordinates,
            0,
            slot,
            ligand_atom_count,
        )?
        || !validate_rigid_coordinate_channel(
            &row.comparison_v2,
            coordinates,
            3,
            slot,
            ligand_atom_count,
        )?
        || !validate_rigid_coordinate_channel(
            &row.baseline_v3,
            coordinates,
            6,
            slot,
            ligand_atom_count,
        )?
        || !validate_rigid_coordinate_channel(
            &row.clearance_v4,
            coordinates,
            9,
            slot,
            ligand_atom_count,
        )?
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid row evidence is malformed",
        ));
    }
    match row.status {
        sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE => {
            let active_mode = row.candidate_mode
                >= sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION
                && row.candidate_mode
                    <= sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
            if row.failure_code < sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE
                || row.failure_code
                    > sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE
                || row.selected_profile != sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE
                || baseline_duplicate
                || clearance_evaluated
                || clearance_selected
                || !rigid_evidence_is_zero(&row.selected)
                || !rigid_evidence_is_zero(&row.comparison_v2)
                || !rigid_evidence_is_zero(&row.baseline_v3)
                || !rigid_evidence_is_zero(&row.clearance_v4)
                || (row.candidate_mode == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
                    && row.failure_code
                        != sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE)
                || (active_mode
                    && row.failure_code
                        == sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 rigid typed failure retained refinement evidence",
                ));
            }
        }
        sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED => {
            if row.failure_code != sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE
                || row.candidate_mode != requested_mode
                || row.selected.available != 1
                || row.selected.profile != row.selected_profile
                || clearance_selected && !clearance_evaluated
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 rigid success evidence is inconsistent",
                ));
            }
            let channels_match_mode = match row.candidate_mode {
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION => {
                    row.selected_profile == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
                        && !baseline_duplicate
                        && !clearance_evaluated
                        && !clearance_selected
                        && rigid_evidence_is_zero(&row.comparison_v2)
                        && rigid_evidence_is_zero(&row.baseline_v3)
                        && rigid_evidence_is_zero(&row.clearance_v4)
                }
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION => {
                    row.selected_profile
                        == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION
                        && !baseline_duplicate
                        && !clearance_evaluated
                        && !clearance_selected
                        && rigid_evidence_is_zero(&row.comparison_v2)
                        && rigid_evidence_is_zero(&row.baseline_v3)
                        && rigid_evidence_is_zero(&row.clearance_v4)
                }
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE => {
                    row.selected_profile == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2
                        && !baseline_duplicate
                        && !clearance_evaluated
                        && !clearance_selected
                        && rigid_evidence_is_zero(&row.comparison_v2)
                        && rigid_evidence_is_zero(&row.baseline_v3)
                        && rigid_evidence_is_zero(&row.clearance_v4)
                }
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE => {
                    row.comparison_v2.available == 1
                        && row.comparison_v2.profile
                            == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
                        && row.baseline_v3.available == 1
                        && row.baseline_v3.profile
                            == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3
                        && (clearance_evaluated == (row.clearance_v4.available == 1))
                        && (!clearance_evaluated
                            || row.clearance_v4.profile
                                == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4)
                        && rigid_evidence_equal(
                            &row.selected,
                            if clearance_selected {
                                &row.clearance_v4
                            } else {
                                &row.baseline_v3
                            },
                        )
                }
                _ => false,
            };
            if !channels_match_mode {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 rigid evidence disagrees with its candidate mode",
                ));
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 rigid row status is unknown",
            ));
        }
    }
    Ok(())
}

fn independent_rigid_profile_raw(
    profile: IndependentRigidProfile,
) -> sys::bg_docking_rigid_refinement_profile {
    match profile {
        IndependentRigidProfile::V2Translation => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
        }
        IndependentRigidProfile::V3TranslationRotation => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION
        }
        IndependentRigidProfile::V6BaselineV2 => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2
        }
        IndependentRigidProfile::V6BaselineV3 => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3
        }
        IndependentRigidProfile::V6ClearanceV4 => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4
        }
    }
}

fn validate_independent_rigid_evidence(
    backend: Backend,
    observed: &sys::bg_docking_rigid_refinement_evidence_v1,
    expected: &IndependentRigidOutcome,
    coordinates: &[Vec<f64>; 12],
    first_channel: usize,
    slot: usize,
    ligand_atom_count: usize,
) -> Result<()> {
    let expected_counts = [
        expected.accepted_steps(),
        expected.accepted_translation_steps(),
        expected.accepted_rotation_steps(),
        expected.line_search_evaluation_count(),
        expected.fallback_direction_step_count(),
    ];
    let observed_counts = [
        observed.accepted_steps,
        observed.accepted_translation_steps,
        observed.accepted_rotation_steps,
        observed.line_search_evaluation_count,
        observed.fallback_direction_step_count,
    ];
    let counts_match = expected_counts
        .into_iter()
        .zip(observed_counts)
        .all(|(expected, observed)| u64::try_from(expected).ok() == Some(observed));
    let expected_translation = expected.total_translation_angstrom();
    let expected_rotation = expected.total_rotation_vector_radians();
    let expected_values = [
        expected.initial_penalty(),
        expected.final_penalty(),
        expected_translation.x,
        expected_translation.y,
        expected_translation.z,
        expected_rotation.x,
        expected_rotation.y,
        expected_rotation.z,
        expected.total_rotation_path_radians(),
        expected.initial_centroid_offset_angstrom(),
        expected.final_centroid_offset_angstrom(),
        expected.maximum_centroid_offset_angstrom(),
    ];
    let observed_values = [
        observed.initial_penalty,
        observed.final_penalty,
        observed.total_translation_angstrom[0],
        observed.total_translation_angstrom[1],
        observed.total_translation_angstrom[2],
        observed.total_rotation_vector_radians[0],
        observed.total_rotation_vector_radians[1],
        observed.total_rotation_vector_radians[2],
        observed.total_rotation_path_radians,
        observed.initial_centroid_offset_angstrom,
        observed.final_centroid_offset_angstrom,
        observed.maximum_centroid_offset_angstrom,
    ];
    let values_match = expected_values
        .into_iter()
        .zip(observed_values)
        .all(|(expected, observed)| numeric_matches(backend, expected, observed));
    let begin = slot.checked_mul(ligand_atom_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid coordinate offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_atom_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid coordinate range overflowed",
        )
    })?;
    let coordinate_channels = coordinates
        .get(first_channel..first_channel + 3)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 independent rigid coordinate channel is absent",
            )
        })?;
    let coordinates_match = expected.coordinates_angstrom().len() == ligand_atom_count
        && coordinate_channels
            .iter()
            .all(|channel| channel.len() >= end)
        && expected
            .coordinates_angstrom()
            .iter()
            .enumerate()
            .all(|(atom, expected)| {
                numeric_matches(backend, expected.x, coordinate_channels[0][begin + atom])
                    && numeric_matches(backend, expected.y, coordinate_channels[1][begin + atom])
                    && numeric_matches(backend, expected.z, coordinate_channels[2][begin + atom])
            });
    if observed.available != 1
        || observed.profile != independent_rigid_profile_raw(expected.profile())
        || !counts_match
        || !values_match
        || !coordinates_match
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid evidence disagrees with independent source-pose replay",
        ));
    }
    Ok(())
}

fn independent_rigid_failure_code(code: IndependentRigidErrorCode) -> i32 {
    match code {
        IndependentRigidErrorCode::InvalidInput => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT
        }
        IndependentRigidErrorCode::NonFiniteInput => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_INPUT
        }
        IndependentRigidErrorCode::PairBudgetExceeded => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_PAIR_BUDGET
        }
        IndependentRigidErrorCode::NonFiniteDerivedValue => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE
        }
    }
}

fn bind_independent_rigid_outcome<T>(
    row: &sys::bg_docking_rigid_refinement_row_v1,
    replay: std::result::Result<T, IndependentRigidError>,
) -> Result<Option<T>> {
    match replay {
        Ok(expected) if row.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED => {
            Ok(Some(expected))
        }
        Ok(_) => Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid failure suppressed an independently successful refinement",
        )),
        Err(error)
            if row.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE
                && row.failure_code == independent_rigid_failure_code(error.code()) =>
        {
            Ok(None)
        }
        Err(error) => Err(Error::local(
            ErrorCode::AbiMismatch,
            format!(
                "native fixed64 rigid outcome disagrees with independent typed failure: {error}"
            ),
        )),
    }
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_independent_rigid_replay(
    backend: Backend,
    row: &sys::bg_docking_rigid_refinement_row_v1,
    requested_mode: sys::bg_docking_rigid_refinement_candidate_mode,
    requested_max_steps: u64,
    producer_coordinates: [&[f64]; 3],
    rigid_coordinates: &[Vec<f64>; 12],
    slot: usize,
    ligand_atom_count: u64,
    geometric_input: &IndependentFixed64GeometricInput,
    v2_config: IndependentRigidV2Config,
    v3_config: IndependentRigidV3Config,
    clearance_config: IndependentRigidV3Config,
) -> Result<()> {
    if requested_mode == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE {
        return Ok(());
    }
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid ligand denominator does not fit usize",
        )
    })?;
    let source = coordinate_segment(producer_coordinates, slot, ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid replay exceeds its producer coordinate buffer",
        )
    })?;
    let source = (0..ligand_count)
        .map(|atom| {
            Vec3::new(
                source.x_angstrom[atom],
                source.y_angstrom[atom],
                source.z_angstrom[atom],
            )
        })
        .collect::<Vec<_>>();
    let max_steps = usize::try_from(requested_max_steps).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid step budget does not fit usize",
        )
    })?;
    let context = IndependentRigidContext {
        receptor_coordinates_angstrom: geometric_input.receptor_coordinates_angstrom(),
        receptor_vdw_radii_angstrom: geometric_input.receptor_vdw_radii_angstrom(),
        ligand_vdw_radii_angstrom: geometric_input.ligand_vdw_radii_angstrom(),
        pocket_center_angstrom: geometric_input.pocket_center_angstrom(),
        pocket_radius_angstrom: geometric_input.pocket_radius_angstrom(),
    };
    match requested_mode {
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION => {
            let Some(expected) = bind_independent_rigid_outcome(
                row,
                refine_interaction_aware_rigid_v2(context, &source, max_steps, v2_config),
            )?
            else {
                return Ok(());
            };
            validate_independent_rigid_evidence(
                backend,
                &row.selected,
                &expected,
                rigid_coordinates,
                0,
                slot,
                ligand_count,
            )?;
        }
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION => {
            let Some(expected) = bind_independent_rigid_outcome(
                row,
                refine_interaction_aware_rigid_v3(context, &source, max_steps, v3_config),
            )?
            else {
                return Ok(());
            };
            validate_independent_rigid_evidence(
                backend,
                &row.selected,
                &expected,
                rigid_coordinates,
                0,
                slot,
                ligand_count,
            )?;
        }
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
        | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE => {
            let v3_lane =
                requested_mode == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
            let Some(expected) = bind_independent_rigid_outcome(
                row,
                refine_interaction_aware_rigid_v6(
                    context,
                    &source,
                    max_steps,
                    v3_lane,
                    v2_config,
                    v3_config,
                    clearance_config,
                ),
            )?
            else {
                return Ok(());
            };
            if bool_from_abi(
                row.baseline_duplicate_of_v2,
                "rigid replay baseline duplicate",
            )? != expected.baseline_duplicate_of_v2()
                || bool_from_abi(row.clearance_evaluated, "rigid replay clearance evaluation")?
                    != expected.clearance_evaluated()
                || bool_from_abi(row.clearance_selected, "rigid replay clearance selection")?
                    != expected.clearance_selected()
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 V6 decision flags disagree with independent source-pose replay",
                ));
            }
            validate_independent_rigid_evidence(
                backend,
                &row.selected,
                expected.selected(),
                rigid_coordinates,
                0,
                slot,
                ligand_count,
            )?;
            for (observed, expected, first_channel) in [
                (&row.comparison_v2, expected.comparison_v2(), 3_usize),
                (&row.baseline_v3, expected.baseline_v3(), 6_usize),
                (&row.clearance_v4, expected.clearance_v4(), 9_usize),
            ] {
                if let Some(expected) = expected {
                    validate_independent_rigid_evidence(
                        backend,
                        observed,
                        expected,
                        rigid_coordinates,
                        first_channel,
                        slot,
                        ligand_count,
                    )?;
                } else if !rigid_evidence_is_zero(observed) {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 V6 retained evidence absent from independent replay",
                    ));
                }
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 rigid replay used an unknown candidate mode",
            ));
        }
    }
    Ok(())
}
