//! Native torsion-refinement row, move, and coordinate-selection evidence validation.

use betelgeuze_sys as sys;

use super::{
    bool_from_abi, coordinate_segment_matches, coordinate_segments_equal, scalar_segments_equal,
    Error, ErrorCode, Result,
};

pub(super) fn torsion_row_values(row: &sys::bg_docking_torsion_v7_row_v1) -> [f64; 14] {
    [
        row.source_receptor_penalty,
        row.source_internal_penalty,
        row.source_combined_penalty,
        row.baseline_receptor_penalty,
        row.baseline_internal_penalty,
        row.baseline_combined_penalty,
        row.optimized_receptor_penalty,
        row.optimized_internal_penalty,
        row.optimized_combined_penalty,
        row.final_receptor_penalty,
        row.final_internal_penalty,
        row.final_combined_penalty,
        row.evaluated_total_torsion_path_radians,
        row.accepted_total_torsion_path_radians,
    ]
}

fn torsion_failure_evidence_is_zero(row: &sys::bg_docking_torsion_v7_row_v1) -> bool {
    row.skip_reason == 0
        && row.selection_reason == 0
        && row.selection_window_reachable == 0
        && row.evaluation_stopped_after_selection_window_became_unreachable == 0
        && row.torsion_evaluated == 0
        && row.torsion_variant_available == 0
        && row.torsion_selected == 0
        && row.torsion_step_budget == 0
        && row.fixed_objective_evaluation_count == 0
        && row.torsion_trial_objective_evaluation_count == 0
        && row.evaluated_torsion_steps == 0
        && row.accepted_torsion_steps == 0
        && row.baseline_v6_accepted_steps == 0
        && torsion_row_values(row).iter().all(|value| *value == 0.0)
}

fn torsion_move_is_zero(row: &sys::bg_docking_torsion_v7_move_v1) -> bool {
    row.evaluated == 0
        && row.selected == 0
        && row.rotatable_child_atom_index == 0
        && row.delta_radians == 0.0
        && row.receptor_penalty == 0.0
        && row.internal_penalty == 0.0
        && row.combined_penalty == 0.0
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_torsion_evidence(
    rows: &[sys::bg_docking_torsion_v7_row_v1],
    moves: &[sys::bg_docking_torsion_v7_move_v1],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    proposal_is_torsion_eligible: &[u8],
    torsion_max_steps: &[u64],
    maximum_torsion_steps: u64,
    rotatable_child_atom_indices: &[u64],
    torsion_coordinates: &[Vec<f64>; 8],
    rigid_coordinates: &[Vec<f64>; 12],
    baseline_torsion_angles_radians: &[f64],
    ligand_atom_count: u64,
) -> Result<()> {
    let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion ligand denominator does not fit usize",
        )
    })?;
    let coordinate_count = rows.len().checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion coordinate denominator overflowed",
        )
    })?;
    if rows.len() != sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize
        || moves.len() != rows.len() * moves_per_slot
        || rigid_rows.len() != rows.len()
        || proposal_is_torsion_eligible.len() != rows.len()
        || torsion_max_steps.len() != rows.len()
        || torsion_coordinates
            .iter()
            .any(|channel| channel.len() != coordinate_count)
        || rigid_coordinates
            .iter()
            .any(|channel| channel.len() != coordinate_count)
        || baseline_torsion_angles_radians.len() != coordinate_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion denominator is invalid",
        ));
    }
    for (slot, row) in rows.iter().enumerate() {
        let rigid = &rigid_rows[slot];
        let v6_ready = rigid.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
            && matches!(
                rigid.candidate_mode,
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
                    | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE
            );
        let window_reachable = bool_from_abi(
            row.selection_window_reachable,
            "torsion selection-window reachability",
        )?;
        let stopped = bool_from_abi(
            row.evaluation_stopped_after_selection_window_became_unreachable,
            "torsion evaluation stop",
        )?;
        let evaluated = bool_from_abi(row.torsion_evaluated, "torsion evaluation")?;
        let variant_available = bool_from_abi(
            row.torsion_variant_available,
            "torsion variant availability",
        )?;
        let selected = bool_from_abi(row.torsion_selected, "torsion selection")?;
        if row.slot_index as usize != slot
            || row.reserved0.iter().any(|value| *value != 0)
            || row.reserved.iter().any(|value| *value != 0)
            || torsion_row_values(row)
                .iter()
                .any(|value| !value.is_finite())
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 torsion row ABI shape or numeric evidence is invalid",
            ));
        }
        match row.status {
            sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE => {
                if row.failure_code < sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE
                    || row.failure_code > sys::BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE
                    || (!v6_ready
                        && row.failure_code
                            != sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE)
                    || !torsion_failure_evidence_is_zero(row)
                    || !coordinate_segment_matches(
                        &torsion_coordinates
                            .iter()
                            .map(Vec::as_slice)
                            .collect::<Vec<_>>(),
                        slot,
                        ligand_atom_count,
                        true,
                    )?
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion typed failure retained optimization evidence",
                    ));
                }
            }
            sys::BG_DOCKING_TORSION_V7_ROW_REFINED => {
                let expected_baseline_steps = rigid.selected.accepted_steps;
                let expected_step_budget = maximum_torsion_steps
                    .min(torsion_max_steps[slot].saturating_sub(expected_baseline_steps));
                let input_eligible = proposal_is_torsion_eligible[slot] == 1;
                if row.failure_code != sys::BG_DOCKING_TORSION_V7_FAILURE_NONE
                    || !v6_ready
                    || row.baseline_v6_accepted_steps != expected_baseline_steps
                    || row.torsion_step_budget != expected_step_budget
                    || row.skip_reason < sys::BG_DOCKING_TORSION_V7_SKIP_NONE
                    || row.skip_reason
                        > sys::BG_DOCKING_TORSION_V7_SKIP_SELECTION_WINDOW_UNREACHABLE
                    || row.selection_reason
                        < sys::BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW
                    || row.selection_reason
                        > sys::BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_NO_REDUCTION
                    || row.fixed_objective_evaluation_count != 2
                    || row.evaluated_torsion_steps > moves_per_slot as u64
                    || row.evaluated_torsion_steps > row.torsion_step_budget
                    || row.accepted_torsion_steps > row.evaluated_torsion_steps
                    || evaluated != (row.skip_reason == sys::BG_DOCKING_TORSION_V7_SKIP_NONE)
                    || variant_available != (row.evaluated_torsion_steps != 0)
                    || (!evaluated && row.evaluated_torsion_steps != 0)
                    || (selected && row.accepted_torsion_steps != row.evaluated_torsion_steps)
                    || (!selected && row.accepted_torsion_steps != 0)
                    || (selected
                        && row.selection_reason
                            != sys::BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW)
                    || (!selected
                        && row.selection_reason
                            == sys::BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW)
                    || (selected
                        && row.accepted_total_torsion_path_radians
                            != row.evaluated_total_torsion_path_radians)
                    || (!selected && row.accepted_total_torsion_path_radians != 0.0)
                    || row.evaluated_total_torsion_path_radians < 0.0
                    || (stopped
                        && (!window_reachable || !evaluated || row.evaluated_torsion_steps == 0))
                    || (!input_eligible
                        && (row.skip_reason != sys::BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE
                            || evaluated
                            || variant_available
                            || selected
                            || row.evaluated_torsion_steps != 0))
                    || (input_eligible
                        && row.skip_reason == sys::BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE)
                    || !coordinate_segment_matches(
                        &torsion_coordinates
                            .iter()
                            .map(Vec::as_slice)
                            .collect::<Vec<_>>(),
                        slot,
                        ligand_atom_count,
                        false,
                    )?
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion refinement evidence is inconsistent",
                    ));
                }
                let rigid_selected = [
                    rigid_coordinates[0].as_slice(),
                    rigid_coordinates[1].as_slice(),
                    rigid_coordinates[2].as_slice(),
                ];
                let optimized = [
                    torsion_coordinates[0].as_slice(),
                    torsion_coordinates[1].as_slice(),
                    torsion_coordinates[2].as_slice(),
                ];
                let final_coordinates = [
                    torsion_coordinates[4].as_slice(),
                    torsion_coordinates[5].as_slice(),
                    torsion_coordinates[6].as_slice(),
                ];
                let optimized_from_baseline = row.evaluated_torsion_steps != 0
                    || (coordinate_segments_equal(optimized, rigid_selected, slot, ligand_count)
                        && scalar_segments_equal(
                            &torsion_coordinates[3],
                            baseline_torsion_angles_radians,
                            slot,
                            ligand_count,
                        ));
                let final_matches_selection = if selected {
                    coordinate_segments_equal(final_coordinates, optimized, slot, ligand_count)
                        && scalar_segments_equal(
                            &torsion_coordinates[7],
                            &torsion_coordinates[3],
                            slot,
                            ligand_count,
                        )
                } else {
                    coordinate_segments_equal(final_coordinates, rigid_selected, slot, ligand_count)
                        && scalar_segments_equal(
                            &torsion_coordinates[7],
                            baseline_torsion_angles_radians,
                            slot,
                            ligand_count,
                        )
                };
                if !optimized_from_baseline || !final_matches_selection {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion coordinate or angle channel disagrees with selection semantics",
                    ));
                }
            }
            _ => {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 torsion row status is unknown",
                ));
            }
        }
        for move_index in 0..moves_per_slot {
            let movement = &moves[slot * moves_per_slot + move_index];
            let move_evaluated = bool_from_abi(movement.evaluated, "torsion move evaluation")?;
            let move_selected = bool_from_abi(movement.selected, "torsion move selection")?;
            let expected_evaluated = row.status == sys::BG_DOCKING_TORSION_V7_ROW_REFINED
                && move_index < row.evaluated_torsion_steps as usize;
            if movement.slot_index as usize != slot
                || movement.move_index as usize != move_index
                || movement.reserved0 != 0
                || movement.reserved.iter().any(|value| *value != 0)
                || [
                    movement.delta_radians,
                    movement.receptor_penalty,
                    movement.internal_penalty,
                    movement.combined_penalty,
                ]
                .iter()
                .any(|value| !value.is_finite())
                || move_evaluated != expected_evaluated
                || (expected_evaluated
                    && (!rotatable_child_atom_indices
                        .contains(&movement.rotatable_child_atom_index)
                        || movement.delta_radians == 0.0
                        || movement.receptor_penalty < 0.0
                        || movement.internal_penalty < 0.0
                        || movement.combined_penalty < 0.0
                        || move_selected != selected))
                || (!expected_evaluated && !torsion_move_is_zero(movement))
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 torsion move evidence disagrees with its parent row",
                ));
            }
        }
    }
    Ok(())
}
