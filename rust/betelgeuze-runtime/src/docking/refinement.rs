//! Native refinement aggregation evidence validation.

use betelgeuze_sys as sys;

use super::{
    bool_from_abi, canonical_coordinate_sha256, coordinate_segment, coordinate_segment_matches,
    coordinate_segments_equal, digest_present, numeric_matches, unit_quaternion, Backend, Error,
    ErrorCode, Result,
};

fn independently_composed_final_quaternion(
    producer: &sys::bg_docking_fixed64_producer_row_v1,
    rigid: &sys::bg_docking_rigid_refinement_row_v1,
) -> Result<[f64; 4]> {
    let source = [
        producer.placement_quaternion_x,
        producer.placement_quaternion_y,
        producer.placement_quaternion_z,
        producer.placement_quaternion_w,
    ];
    let rotation = rigid.selected.total_rotation_vector_radians;
    let angle =
        (rotation[0] * rotation[0] + rotation[1] * rotation[1] + rotation[2] * rotation[2]).sqrt();
    if !angle.is_finite() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid rotation cannot produce a finite final quaternion",
        ));
    }
    if angle == 0.0 {
        return Ok(source);
    }
    let scale = (0.5 * angle).sin() / angle;
    let delta = [
        rotation[0] * scale,
        rotation[1] * scale,
        rotation[2] * scale,
        (0.5 * angle).cos(),
    ];
    let mut result = [
        delta[3] * source[0] + delta[0] * source[3] + delta[1] * source[2] - delta[2] * source[1],
        delta[3] * source[1] - delta[0] * source[2] + delta[1] * source[3] + delta[2] * source[0],
        delta[3] * source[2] + delta[0] * source[1] - delta[1] * source[0] + delta[2] * source[3],
        delta[3] * source[3] - delta[0] * source[0] - delta[1] * source[1] - delta[2] * source[2],
    ];
    for component in &mut result {
        if *component == 0.0 {
            *component = 0.0;
        }
    }
    Ok(result)
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_refinement_evidence(
    rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    producer_rows: &[sys::bg_docking_fixed64_producer_row_v1],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    requested_modes: &[sys::bg_docking_rigid_refinement_candidate_mode],
    rigid_coordinates: [&[f64]; 3],
    torsion_final_coordinates: [&[f64]; 3],
    final_coordinates: [&[f64]; 3],
    quaternions: [&[f64]; 4],
    ligand_atom_count: u64,
    backend: Backend,
) -> Result<()> {
    if rows.len() != producer_rows.len()
        || rows.len() != rigid_rows.len()
        || rows.len() != torsion_rows.len()
        || rows.len() != requested_modes.len()
        || quaternions.iter().any(|values| values.len() != rows.len())
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement denominator is invalid",
        ));
    }
    for (slot, row) in rows.iter().enumerate() {
        let applicable = bool_from_abi(
            row.torsion_v7_applicable,
            "refinement torsion applicability",
        )?;
        let selected = bool_from_abi(row.torsion_v7_selected, "refinement torsion selection")?;
        let coordinate_available = bool_from_abi(
            row.coordinate_available,
            "refinement coordinate availability",
        )?;
        let rigid = &rigid_rows[slot];
        let torsion = &torsion_rows[slot];
        let v6_mode = matches!(
            rigid.candidate_mode,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
                | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE
        );
        let quaternion = [
            quaternions[0][slot],
            quaternions[1][slot],
            quaternions[2][slot],
            quaternions[3][slot],
        ];
        let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 refinement ligand denominator does not fit usize",
            )
        })?;
        if row.slot_index as usize != slot
            || row.reserved0 != 0
            || row.reserved.iter().any(|value| *value != 0)
            || row.rigid_failure_code != rigid.failure_code
            || row.selected_rigid_profile != rigid.selected_profile
            || selected && !applicable
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 refinement row identity is inconsistent",
            ));
        }
        match row.status {
            sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY => {
                let expected_origin = if v6_mode {
                    sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_TORSION_V7_FINAL
                } else {
                    sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED
                };
                let origin_coordinates = if v6_mode {
                    torsion_final_coordinates
                } else {
                    rigid_coordinates
                };
                let final_coordinate_digest =
                    coordinate_segment(final_coordinates, slot, ligand_count)
                        .map(canonical_coordinate_sha256);
                let expected_quaternion =
                    independently_composed_final_quaternion(&producer_rows[slot], rigid)?;
                let quaternion_matches = expected_quaternion
                    .into_iter()
                    .zip(quaternion)
                    .all(|(expected, observed)| numeric_matches(backend, expected, observed));
                if row.failure_stage != sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE
                    || row.coordinate_origin != expected_origin
                    || rigid.status != sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
                    || rigid.failure_code != sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE
                    || row.downstream_candidate_state != sys::BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE
                    || applicable != v6_mode
                    || (v6_mode
                        && (torsion.status != sys::BG_DOCKING_TORSION_V7_ROW_REFINED
                            || row.torsion_v7_failure_code
                                != sys::BG_DOCKING_TORSION_V7_FAILURE_NONE
                            || selected != (torsion.torsion_selected == 1)))
                    || (!v6_mode && (row.torsion_v7_failure_code != 0 || selected))
                    || !coordinate_available
                    || !digest_present(&row.coordinate_sha256)
                    || final_coordinate_digest != Some(row.coordinate_sha256)
                    || !coordinate_segments_equal(
                        final_coordinates,
                        origin_coordinates,
                        slot,
                        ligand_count,
                    )
                    || !coordinate_segment_matches(
                        &final_coordinates,
                        slot,
                        ligand_atom_count,
                        false,
                    )?
                    || !unit_quaternion(quaternion)
                    || !quaternion_matches
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 coordinate-ready refinement evidence is invalid",
                    ));
                }
            }
            sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE => {
                let rigid_failure = row.failure_stage
                    == sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_RIGID
                    && rigid.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE
                    && row.rigid_failure_code
                        >= sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE
                    && row.rigid_failure_code
                        <= sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE
                    && row.torsion_v7_failure_code == 0
                    && !applicable;
                let torsion_failure = row.failure_stage
                    == sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_TORSION_V7
                    && rigid.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
                    && v6_mode
                    && applicable
                    && torsion.status == sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE
                    && row.torsion_v7_failure_code == torsion.failure_code;
                if (!rigid_failure && !torsion_failure)
                    || row.coordinate_origin != sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_NONE
                    || row.downstream_candidate_state
                        != sys::BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE
                    || selected
                    || coordinate_available
                    || digest_present(&row.coordinate_sha256)
                    || !coordinate_segment_matches(
                        &final_coordinates,
                        slot,
                        ligand_atom_count,
                        true,
                    )?
                    || quaternion.iter().any(|value| *value != 0.0)
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 refinement typed failure retained coordinate evidence",
                    ));
                }
            }
            _ => {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 refinement row status is unknown",
                ));
            }
        }
    }
    Ok(())
}
