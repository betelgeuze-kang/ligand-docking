use super::*;

use betelgeuze_docking_search::{
    refine_interaction_aware_torsion_contact_v7,
    validate_interaction_aware_torsion_contact_v7_context, NativeTorsionV7Config,
    NativeTorsionV7Context, NativeTorsionV7ErrorCode, NativeTorsionV7Request,
    NativeTorsionV7SelectionReason, NativeTorsionV7SkipReason, NATIVE_TORSION_V7_MAX_LIGAND_ATOMS,
    NATIVE_TORSION_V7_MAX_RECEPTOR_ATOMS,
};

const CANDIDATE_COUNT: usize = FIXED64_CANDIDATE_COUNT;
const MAX_MOVES: usize = 8;
const CANDIDATE_INACTIVE: i32 = 0;
const CANDIDATE_REFINE: i32 = 1;
const ROW_REFINED: i32 = 1;
const ROW_TYPED_FAILURE: i32 = 2;
const FAILURE_NONE: i32 = 0;
const FAILURE_UPSTREAM_NOT_ELIGIBLE: i32 = 1;
const FAILURE_INVALID_INPUT: i32 = 2;
const FAILURE_PAIR_BUDGET: i32 = 3;
const FAILURE_DEGENERATE_ROTOR: i32 = 4;
const FAILURE_NONFINITE_DERIVED_VALUE: i32 = 5;

#[repr(C)]
pub struct TorsionV7ContextV1 {
    struct_size: u32,
    abi_version: u32,
    receptor_atom_count: usize,
    ligand_atom_count: usize,
    rotor_count: usize,
    internal_pair_count: usize,
    receptor_x_angstrom: *const f64,
    receptor_y_angstrom: *const f64,
    receptor_z_angstrom: *const f64,
    receptor_vdw_radius_angstrom: *const f64,
    ligand_vdw_radius_angstrom: *const f64,
    pocket_center_angstrom: [f64; 3],
    parent_atom_index: *const i32,
    rotatable_child_atom_index: *const usize,
    internal_pair_atom_i: *const usize,
    internal_pair_atom_j: *const usize,
    receptor_overlap_scale: f64,
    internal_overlap_scale: f64,
    internal_overlap_weight: f64,
    maximum_baseline_v6_steps: usize,
    maximum_torsions_evaluated: usize,
    maximum_torsion_steps: usize,
    maximum_backtracking_evaluations: usize,
    maximum_torsion_step_radians: f64,
    minimum_torsion_step_radians: f64,
    maximum_total_torsion_path_radians: f64,
    maximum_centroid_offset_angstrom: f64,
    minimum_selected_final_receptor_penalty: f64,
    maximum_selected_final_receptor_penalty: f64,
    penalty_tolerance: f64,
    epsilon_angstrom: f64,
    reserved: [u64; 8],
}

#[repr(C)]
pub struct TorsionV7BatchV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: usize,
    ligand_atom_count: usize,
    candidate_state: *const i32,
    proposal_is_torsion_eligible: *const u8,
    max_steps: *const usize,
    baseline_v6_accepted_steps: *const usize,
    source_x_angstrom: *const f64,
    source_y_angstrom: *const f64,
    source_z_angstrom: *const f64,
    baseline_v6_x_angstrom: *const f64,
    baseline_v6_y_angstrom: *const f64,
    baseline_v6_z_angstrom: *const f64,
    baseline_v6_torsion_angles_radians: *const f64,
    reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct TorsionV7RowV1 {
    slot_index: u32,
    status: i32,
    failure_code: i32,
    skip_reason: i32,
    selection_reason: i32,
    selection_window_reachable: u8,
    evaluation_stopped_after_selection_window_became_unreachable: u8,
    torsion_evaluated: u8,
    torsion_variant_available: u8,
    torsion_selected: u8,
    reserved0: [u8; 3],
    torsion_step_budget: usize,
    fixed_objective_evaluation_count: usize,
    torsion_trial_objective_evaluation_count: usize,
    evaluated_torsion_steps: usize,
    accepted_torsion_steps: usize,
    baseline_v6_accepted_steps: usize,
    source_receptor_penalty: f64,
    source_internal_penalty: f64,
    source_combined_penalty: f64,
    baseline_receptor_penalty: f64,
    baseline_internal_penalty: f64,
    baseline_combined_penalty: f64,
    optimized_receptor_penalty: f64,
    optimized_internal_penalty: f64,
    optimized_combined_penalty: f64,
    final_receptor_penalty: f64,
    final_internal_penalty: f64,
    final_combined_penalty: f64,
    evaluated_total_torsion_path_radians: f64,
    accepted_total_torsion_path_radians: f64,
    reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct TorsionV7MoveV1 {
    slot_index: u32,
    move_index: u32,
    evaluated: u8,
    selected: u8,
    reserved0: u16,
    rotatable_child_atom_index: usize,
    delta_radians: f64,
    receptor_penalty: f64,
    internal_penalty: f64,
    combined_penalty: f64,
    reserved: [u64; 4],
}

struct TorsionV7State {
    receptor_coordinates: Vec<Vec3>,
    receptor_radii: Vec<f64>,
    ligand_radii: Vec<f64>,
    pocket_center: Vec3,
    parents: Vec<i32>,
    rotors: Vec<usize>,
    internal_pairs: Vec<(usize, usize)>,
    config: NativeTorsionV7Config,
}

struct TorsionV7ProviderOutput {
    rows: [TorsionV7RowV1; CANDIDATE_COUNT],
    moves: Vec<TorsionV7MoveV1>,
    optimized_x: Vec<f64>,
    optimized_y: Vec<f64>,
    optimized_z: Vec<f64>,
    optimized_angles: Vec<f64>,
    final_x: Vec<f64>,
    final_y: Vec<f64>,
    final_z: Vec<f64>,
    final_angles: Vec<f64>,
}

fn empty_row(slot_index: usize, failure_code: i32) -> TorsionV7RowV1 {
    TorsionV7RowV1 {
        slot_index: slot_index as u32,
        status: ROW_TYPED_FAILURE,
        failure_code,
        skip_reason: 0,
        selection_reason: 0,
        selection_window_reachable: 0,
        evaluation_stopped_after_selection_window_became_unreachable: 0,
        torsion_evaluated: 0,
        torsion_variant_available: 0,
        torsion_selected: 0,
        reserved0: [0; 3],
        torsion_step_budget: 0,
        fixed_objective_evaluation_count: 0,
        torsion_trial_objective_evaluation_count: 0,
        evaluated_torsion_steps: 0,
        accepted_torsion_steps: 0,
        baseline_v6_accepted_steps: 0,
        source_receptor_penalty: 0.0,
        source_internal_penalty: 0.0,
        source_combined_penalty: 0.0,
        baseline_receptor_penalty: 0.0,
        baseline_internal_penalty: 0.0,
        baseline_combined_penalty: 0.0,
        optimized_receptor_penalty: 0.0,
        optimized_internal_penalty: 0.0,
        optimized_combined_penalty: 0.0,
        final_receptor_penalty: 0.0,
        final_internal_penalty: 0.0,
        final_combined_penalty: 0.0,
        evaluated_total_torsion_path_radians: 0.0,
        accepted_total_torsion_path_radians: 0.0,
        reserved: [0; 8],
    }
}

fn empty_move(slot_index: usize, move_index: usize) -> TorsionV7MoveV1 {
    TorsionV7MoveV1 {
        slot_index: slot_index as u32,
        move_index: move_index as u32,
        evaluated: 0,
        selected: 0,
        reserved0: 0,
        rotatable_child_atom_index: 0,
        delta_radians: 0.0,
        receptor_penalty: 0.0,
        internal_penalty: 0.0,
        combined_penalty: 0.0,
        reserved: [0; 4],
    }
}

fn context<'a>(state: &'a TorsionV7State) -> NativeTorsionV7Context<'a> {
    NativeTorsionV7Context {
        receptor_coordinates_angstrom: &state.receptor_coordinates,
        receptor_vdw_radii_angstrom: &state.receptor_radii,
        ligand_vdw_radii_angstrom: &state.ligand_radii,
        pocket_center_angstrom: state.pocket_center,
        parent_atom_indices: &state.parents,
        rotatable_child_atom_indices: &state.rotors,
        evaluated_internal_pairs: &state.internal_pairs,
    }
}

fn core_error(error: NativeTorsionV7ErrorCode) -> i32 {
    match error {
        NativeTorsionV7ErrorCode::InvalidInput | NativeTorsionV7ErrorCode::NonFiniteInput => {
            FAILURE_INVALID_INPUT
        }
        NativeTorsionV7ErrorCode::PairBudgetExceeded => FAILURE_PAIR_BUDGET,
        NativeTorsionV7ErrorCode::DegenerateRotor => FAILURE_DEGENERATE_ROTOR,
        NativeTorsionV7ErrorCode::NonFiniteDerivedValue => FAILURE_NONFINITE_DERIVED_VALUE,
    }
}

fn skip_reason(reason: NativeTorsionV7SkipReason) -> i32 {
    match reason {
        NativeTorsionV7SkipReason::NoSkip => 0,
        NativeTorsionV7SkipReason::NotEligible => 1,
        NativeTorsionV7SkipReason::NoAuthorityRotor => 2,
        NativeTorsionV7SkipReason::NoRemainingTorsionStepBudget => 3,
        NativeTorsionV7SkipReason::ObjectiveAtOrBelowTolerance => 4,
        NativeTorsionV7SkipReason::SelectionWindowUnreachable => 5,
    }
}

fn selection_reason(reason: NativeTorsionV7SelectionReason) -> i32 {
    match reason {
        NativeTorsionV7SelectionReason::FinalReceptorPenaltyWindowSelected => 1,
        NativeTorsionV7SelectionReason::V6RetainedOutsideFinalReceptorPenaltyWindow => 2,
        NativeTorsionV7SelectionReason::V6BaselineRetainedNoTorsionObjectiveReduction => 3,
    }
}

unsafe fn build_state(descriptor: &TorsionV7ContextV1) -> Result<TorsionV7State, ProviderError> {
    validate_header::<TorsionV7ContextV1>(
        descriptor.struct_size,
        descriptor.abi_version,
        "rust_cpu torsion V7 context size mismatch",
    )?;
    if !reserved_is_zero(&descriptor.reserved)
        || descriptor.receptor_atom_count == 0
        || descriptor.receptor_atom_count > NATIVE_TORSION_V7_MAX_RECEPTOR_ATOMS
        || descriptor.ligand_atom_count == 0
        || descriptor.ligand_atom_count > NATIVE_TORSION_V7_MAX_LIGAND_ATOMS
        || descriptor.rotor_count > descriptor.ligand_atom_count
    {
        return Err(ProviderError::capacity(
            "rust_cpu torsion V7 context denominator is invalid",
        ));
    }
    let maximum_internal_pairs = descriptor
        .ligand_atom_count
        .checked_mul(descriptor.ligand_atom_count - 1)
        .map(|value| value / 2)
        .ok_or_else(|| ProviderError::capacity("rust_cpu torsion V7 pair bound overflowed"))?;
    if descriptor.internal_pair_count > maximum_internal_pairs {
        return Err(ProviderError::capacity(
            "rust_cpu torsion V7 pair denominator exceeds the canonical maximum",
        ));
    }
    let receptor_x = unsafe {
        checked_slice(
            descriptor.receptor_x_angstrom,
            descriptor.receptor_atom_count,
            "rust_cpu torsion V7 receptor x is null",
        )?
    };
    let receptor_y = unsafe {
        checked_slice(
            descriptor.receptor_y_angstrom,
            descriptor.receptor_atom_count,
            "rust_cpu torsion V7 receptor y is null",
        )?
    };
    let receptor_z = unsafe {
        checked_slice(
            descriptor.receptor_z_angstrom,
            descriptor.receptor_atom_count,
            "rust_cpu torsion V7 receptor z is null",
        )?
    };
    let receptor_radii = unsafe {
        checked_slice(
            descriptor.receptor_vdw_radius_angstrom,
            descriptor.receptor_atom_count,
            "rust_cpu torsion V7 receptor radii are null",
        )?
    };
    let ligand_radii = unsafe {
        checked_slice(
            descriptor.ligand_vdw_radius_angstrom,
            descriptor.ligand_atom_count,
            "rust_cpu torsion V7 ligand radii are null",
        )?
    };
    let parents = unsafe {
        checked_slice(
            descriptor.parent_atom_index,
            descriptor.ligand_atom_count,
            "rust_cpu torsion V7 parent tree is null",
        )?
    };
    let rotors = unsafe {
        checked_slice(
            descriptor.rotatable_child_atom_index,
            descriptor.rotor_count,
            "rust_cpu torsion V7 rotor channel is null",
        )?
    };
    let internal_i = unsafe {
        checked_slice(
            descriptor.internal_pair_atom_i,
            descriptor.internal_pair_count,
            "rust_cpu torsion V7 internal pair i is null",
        )?
    };
    let internal_j = unsafe {
        checked_slice(
            descriptor.internal_pair_atom_j,
            descriptor.internal_pair_count,
            "rust_cpu torsion V7 internal pair j is null",
        )?
    };
    let state = TorsionV7State {
        receptor_coordinates: (0..descriptor.receptor_atom_count)
            .map(|index| Vec3::new(receptor_x[index], receptor_y[index], receptor_z[index]))
            .collect(),
        receptor_radii: receptor_radii.to_vec(),
        ligand_radii: ligand_radii.to_vec(),
        pocket_center: Vec3::new(
            descriptor.pocket_center_angstrom[0],
            descriptor.pocket_center_angstrom[1],
            descriptor.pocket_center_angstrom[2],
        ),
        parents: parents.to_vec(),
        rotors: rotors.to_vec(),
        internal_pairs: internal_i
            .iter()
            .copied()
            .zip(internal_j.iter().copied())
            .collect(),
        config: NativeTorsionV7Config {
            receptor_overlap_scale: descriptor.receptor_overlap_scale,
            internal_overlap_scale: descriptor.internal_overlap_scale,
            internal_overlap_weight: descriptor.internal_overlap_weight,
            maximum_baseline_v6_steps: descriptor.maximum_baseline_v6_steps,
            maximum_torsions_evaluated: descriptor.maximum_torsions_evaluated,
            maximum_torsion_steps: descriptor.maximum_torsion_steps,
            maximum_backtracking_evaluations: descriptor.maximum_backtracking_evaluations,
            maximum_torsion_step_radians: descriptor.maximum_torsion_step_radians,
            minimum_torsion_step_radians: descriptor.minimum_torsion_step_radians,
            maximum_total_torsion_path_radians: descriptor.maximum_total_torsion_path_radians,
            maximum_centroid_offset_angstrom: descriptor.maximum_centroid_offset_angstrom,
            minimum_selected_final_receptor_penalty: descriptor
                .minimum_selected_final_receptor_penalty,
            maximum_selected_final_receptor_penalty: descriptor
                .maximum_selected_final_receptor_penalty,
            penalty_tolerance: descriptor.penalty_tolerance,
            epsilon_angstrom: descriptor.epsilon_angstrom,
        },
    };

    validate_interaction_aware_torsion_contact_v7_context(context(&state), state.config).map_err(
        |error| match error.code() {
            NativeTorsionV7ErrorCode::PairBudgetExceeded => {
                ProviderError::capacity(error.message())
            }
            NativeTorsionV7ErrorCode::NonFiniteDerivedValue => ProviderError {
                status: STATUS_NUMERICAL_ERROR,
                message: error.message(),
            },
            _ => ProviderError::invalid(error.message()),
        },
    )?;
    Ok(state)
}

fn coordinates_from_soa(
    x: &[f64],
    y: &[f64],
    z: &[f64],
    start: usize,
    atom_count: usize,
) -> Vec<Vec3> {
    (start..start + atom_count)
        .map(|index| Vec3::new(x[index], y[index], z[index]))
        .collect()
}

unsafe fn refine_batch(
    state: &TorsionV7State,
    batch: &TorsionV7BatchV1,
) -> Result<TorsionV7ProviderOutput, ProviderError> {
    validate_header::<TorsionV7BatchV1>(
        batch.struct_size,
        batch.abi_version,
        "rust_cpu torsion V7 batch size mismatch",
    )?;
    if !reserved_is_zero(&batch.reserved)
        || batch.candidate_count != CANDIDATE_COUNT
        || batch.ligand_atom_count != state.ligand_radii.len()
    {
        return Err(ProviderError::invalid(
            "rust_cpu torsion V7 batch denominator is invalid",
        ));
    }
    let coordinate_count = CANDIDATE_COUNT
        .checked_mul(batch.ligand_atom_count)
        .ok_or_else(|| {
            ProviderError::capacity("rust_cpu torsion V7 coordinate count overflowed")
        })?;
    let candidate_state = unsafe {
        checked_slice(
            batch.candidate_state,
            CANDIDATE_COUNT,
            "rust_cpu torsion V7 candidate state is null",
        )?
    };
    let eligible = unsafe {
        checked_slice(
            batch.proposal_is_torsion_eligible,
            CANDIDATE_COUNT,
            "rust_cpu torsion V7 eligibility channel is null",
        )?
    };
    let max_steps = unsafe {
        checked_slice(
            batch.max_steps,
            CANDIDATE_COUNT,
            "rust_cpu torsion V7 max-step channel is null",
        )?
    };
    let baseline_steps = unsafe {
        checked_slice(
            batch.baseline_v6_accepted_steps,
            CANDIDATE_COUNT,
            "rust_cpu torsion V7 baseline-step channel is null",
        )?
    };
    let source_x = unsafe {
        checked_slice(
            batch.source_x_angstrom,
            coordinate_count,
            "rust_cpu torsion V7 source x is null",
        )?
    };
    let source_y = unsafe {
        checked_slice(
            batch.source_y_angstrom,
            coordinate_count,
            "rust_cpu torsion V7 source y is null",
        )?
    };
    let source_z = unsafe {
        checked_slice(
            batch.source_z_angstrom,
            coordinate_count,
            "rust_cpu torsion V7 source z is null",
        )?
    };
    let baseline_x = unsafe {
        checked_slice(
            batch.baseline_v6_x_angstrom,
            coordinate_count,
            "rust_cpu torsion V7 baseline x is null",
        )?
    };
    let baseline_y = unsafe {
        checked_slice(
            batch.baseline_v6_y_angstrom,
            coordinate_count,
            "rust_cpu torsion V7 baseline y is null",
        )?
    };
    let baseline_z = unsafe {
        checked_slice(
            batch.baseline_v6_z_angstrom,
            coordinate_count,
            "rust_cpu torsion V7 baseline z is null",
        )?
    };
    let baseline_angles = unsafe {
        checked_slice(
            batch.baseline_v6_torsion_angles_radians,
            coordinate_count,
            "rust_cpu torsion V7 baseline angles are null",
        )?
    };
    if candidate_state
        .iter()
        .any(|value| !matches!(*value, CANDIDATE_INACTIVE | CANDIDATE_REFINE))
    {
        return Err(ProviderError::invalid(
            "rust_cpu torsion V7 candidate state is unknown",
        ));
    }

    let mut rows = core::array::from_fn(|slot| empty_row(slot, FAILURE_UPSTREAM_NOT_ELIGIBLE));
    let mut moves = (0..CANDIDATE_COUNT)
        .flat_map(|slot| (0..MAX_MOVES).map(move |index| empty_move(slot, index)))
        .collect::<Vec<_>>();
    let mut optimized_x = vec![0.0; coordinate_count];
    let mut optimized_y = vec![0.0; coordinate_count];
    let mut optimized_z = vec![0.0; coordinate_count];
    let mut optimized_angles = vec![0.0; coordinate_count];
    let mut final_x = vec![0.0; coordinate_count];
    let mut final_y = vec![0.0; coordinate_count];
    let mut final_z = vec![0.0; coordinate_count];
    let mut final_angles = vec![0.0; coordinate_count];

    for slot in 0..CANDIDATE_COUNT {
        if candidate_state[slot] == CANDIDATE_INACTIVE {
            continue;
        }
        if eligible[slot] > 1 {
            rows[slot] = empty_row(slot, FAILURE_INVALID_INPUT);
            continue;
        }
        let start = slot * batch.ligand_atom_count;
        let source =
            coordinates_from_soa(source_x, source_y, source_z, start, batch.ligand_atom_count);
        let baseline = coordinates_from_soa(
            baseline_x,
            baseline_y,
            baseline_z,
            start,
            batch.ligand_atom_count,
        );
        let angles = &baseline_angles[start..start + batch.ligand_atom_count];
        let outcome = match refine_interaction_aware_torsion_contact_v7(
            NativeTorsionV7Request {
                context: context(state),
                source_coordinates_angstrom: &source,
                baseline_v6_coordinates_angstrom: &baseline,
                baseline_v6_torsion_angles_radians: angles,
                proposal_is_torsion_eligible: eligible[slot] == 1,
                max_steps: max_steps[slot],
                baseline_v6_accepted_steps: baseline_steps[slot],
            },
            state.config,
        ) {
            Ok(outcome) => outcome,
            Err(error) => {
                rows[slot] = empty_row(slot, core_error(error.code()));
                continue;
            }
        };
        let source_objective = outcome.source_objective();
        let baseline_objective = outcome.baseline_objective();
        let optimized_objective = outcome.optimized_objective();
        let final_objective = outcome.final_objective();
        rows[slot] = TorsionV7RowV1 {
            slot_index: slot as u32,
            status: ROW_REFINED,
            failure_code: FAILURE_NONE,
            skip_reason: skip_reason(outcome.skip_reason()),
            selection_reason: selection_reason(outcome.selection_reason()),
            selection_window_reachable: u8::from(outcome.selection_window_reachable()),
            evaluation_stopped_after_selection_window_became_unreachable: u8::from(
                outcome.evaluation_stopped_after_selection_window_became_unreachable(),
            ),
            torsion_evaluated: u8::from(outcome.torsion_evaluated()),
            torsion_variant_available: u8::from(outcome.torsion_variant_available()),
            torsion_selected: u8::from(outcome.torsion_selected()),
            reserved0: [0; 3],
            torsion_step_budget: outcome.torsion_step_budget(),
            fixed_objective_evaluation_count: outcome.fixed_objective_evaluation_count(),
            torsion_trial_objective_evaluation_count: outcome
                .torsion_trial_objective_evaluation_count(),
            evaluated_torsion_steps: outcome.evaluated_torsion_steps(),
            accepted_torsion_steps: outcome.accepted_torsion_steps(),
            baseline_v6_accepted_steps: baseline_steps[slot],
            source_receptor_penalty: source_objective.receptor(),
            source_internal_penalty: source_objective.internal(),
            source_combined_penalty: source_objective.combined(),
            baseline_receptor_penalty: baseline_objective.receptor(),
            baseline_internal_penalty: baseline_objective.internal(),
            baseline_combined_penalty: baseline_objective.combined(),
            optimized_receptor_penalty: optimized_objective.receptor(),
            optimized_internal_penalty: optimized_objective.internal(),
            optimized_combined_penalty: optimized_objective.combined(),
            final_receptor_penalty: final_objective.receptor(),
            final_internal_penalty: final_objective.internal(),
            final_combined_penalty: final_objective.combined(),
            evaluated_total_torsion_path_radians: outcome.evaluated_total_torsion_path_radians(),
            accepted_total_torsion_path_radians: outcome.accepted_total_torsion_path_radians(),
            reserved: [0; 8],
        };
        for (index, movement) in outcome.evaluated_moves().iter().copied().enumerate() {
            let objective = movement.objective();
            moves[slot * MAX_MOVES + index] = TorsionV7MoveV1 {
                slot_index: slot as u32,
                move_index: index as u32,
                evaluated: 1,
                selected: u8::from(outcome.torsion_selected()),
                reserved0: 0,
                rotatable_child_atom_index: movement.rotatable_child_atom_index(),
                delta_radians: movement.delta_radians(),
                receptor_penalty: objective.receptor(),
                internal_penalty: objective.internal(),
                combined_penalty: objective.combined(),
                reserved: [0; 4],
            };
        }
        for atom in 0..batch.ligand_atom_count {
            let destination = start + atom;
            let optimized = outcome.optimized_coordinates_angstrom()[atom];
            let final_coordinate = outcome.final_coordinates_angstrom()[atom];
            optimized_x[destination] = optimized.x;
            optimized_y[destination] = optimized.y;
            optimized_z[destination] = optimized.z;
            optimized_angles[destination] = outcome.optimized_torsion_angles_radians()[atom];
            final_x[destination] = final_coordinate.x;
            final_y[destination] = final_coordinate.y;
            final_z[destination] = final_coordinate.z;
            final_angles[destination] = outcome.final_torsion_angles_radians()[atom];
        }
    }
    Ok(TorsionV7ProviderOutput {
        rows,
        moves,
        optimized_x,
        optimized_y,
        optimized_z,
        optimized_angles,
        final_x,
        final_y,
        final_z,
        final_angles,
    })
}

fn aligned<T>(pointer: *mut T) -> bool {
    !pointer.is_null() && (pointer as usize) % align_of::<T>() == 0
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_torsion_v7_create(
    descriptor: *const TorsionV7ContextV1,
    out_state: *mut *mut c_void,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if descriptor.is_null() || out_state.is_null() || !aligned(out_state) {
        write_error(
            error,
            "rust_cpu torsion V7 create pointer is null or misaligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    unsafe { ptr::write(out_state, ptr::null_mut()) };
    let descriptor = unsafe { &*descriptor };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe { build_state(descriptor) }));
    match result {
        Ok(Ok(state)) => {
            unsafe { ptr::write(out_state, Box::into_raw(Box::new(state)).cast::<c_void>()) };
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu torsion V7 context creation panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_torsion_v7_destroy(state: *mut c_void) {
    if !state.is_null() {
        drop(unsafe { Box::from_raw(state.cast::<TorsionV7State>()) });
    }
}

#[allow(clippy::too_many_arguments)]
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_torsion_v7_refine_fixed64(
    state: *const c_void,
    batch: *const TorsionV7BatchV1,
    out_rows: *mut TorsionV7RowV1,
    out_moves: *mut TorsionV7MoveV1,
    out_optimized_x_angstrom: *mut f64,
    out_optimized_y_angstrom: *mut f64,
    out_optimized_z_angstrom: *mut f64,
    out_optimized_torsion_angles_radians: *mut f64,
    out_final_x_angstrom: *mut f64,
    out_final_y_angstrom: *mut f64,
    out_final_z_angstrom: *mut f64,
    out_final_torsion_angles_radians: *mut f64,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let output_pointers_valid = aligned(out_rows)
        && aligned(out_moves)
        && aligned(out_optimized_x_angstrom)
        && aligned(out_optimized_y_angstrom)
        && aligned(out_optimized_z_angstrom)
        && aligned(out_optimized_torsion_angles_radians)
        && aligned(out_final_x_angstrom)
        && aligned(out_final_y_angstrom)
        && aligned(out_final_z_angstrom)
        && aligned(out_final_torsion_angles_radians);
    if state.is_null() || batch.is_null() || !output_pointers_valid {
        write_error(
            error,
            "rust_cpu torsion V7 refine pointer is null or misaligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    let state = unsafe { &*state.cast::<TorsionV7State>() };
    let batch = unsafe { &*batch };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe { refine_batch(state, batch) }));
    match result {
        Ok(Ok(output)) => {
            let coordinate_count = CANDIDATE_COUNT * state.ligand_radii.len();
            unsafe {
                ptr::copy_nonoverlapping(output.rows.as_ptr(), out_rows, CANDIDATE_COUNT);
                ptr::copy_nonoverlapping(
                    output.moves.as_ptr(),
                    out_moves,
                    CANDIDATE_COUNT * MAX_MOVES,
                );
                ptr::copy_nonoverlapping(
                    output.optimized_x.as_ptr(),
                    out_optimized_x_angstrom,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.optimized_y.as_ptr(),
                    out_optimized_y_angstrom,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.optimized_z.as_ptr(),
                    out_optimized_z_angstrom,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.optimized_angles.as_ptr(),
                    out_optimized_torsion_angles_radians,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.final_x.as_ptr(),
                    out_final_x_angstrom,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.final_y.as_ptr(),
                    out_final_y_angstrom,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.final_z.as_ptr(),
                    out_final_z_angstrom,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.final_angles.as_ptr(),
                    out_final_torsion_angles_radians,
                    coordinate_count,
                );
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu torsion V7 refinement panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct ContextStorage {
        receptor_x: [f64; 2],
        receptor_y: [f64; 2],
        receptor_z: [f64; 2],
        receptor_radii: [f64; 2],
        ligand_radii: [f64; 4],
        parents: [i32; 4],
        rotors: [usize; 1],
        internal_i: [usize; 3],
        internal_j: [usize; 3],
    }

    impl ContextStorage {
        fn fixture() -> Self {
            Self {
                receptor_x: [2.0, 20.0],
                receptor_y: [1.0, 20.0],
                receptor_z: [0.0, 20.0],
                receptor_radii: [1.0; 2],
                ligand_radii: [1.0; 4],
                parents: [-1, 0, 1, 2],
                rotors: [2],
                internal_i: [0, 0, 1],
                internal_j: [2, 3, 3],
            }
        }

        fn descriptor(&self) -> TorsionV7ContextV1 {
            let config = NativeTorsionV7Config {
                minimum_selected_final_receptor_penalty: 0.0,
                maximum_selected_final_receptor_penalty: 1_000_000.0,
                ..NativeTorsionV7Config::default()
            };
            TorsionV7ContextV1 {
                struct_size: u32::try_from(size_of::<TorsionV7ContextV1>()).unwrap(),
                abi_version: PROVIDER_ABI_VERSION,
                receptor_atom_count: self.receptor_x.len(),
                ligand_atom_count: self.ligand_radii.len(),
                rotor_count: self.rotors.len(),
                internal_pair_count: self.internal_i.len(),
                receptor_x_angstrom: self.receptor_x.as_ptr(),
                receptor_y_angstrom: self.receptor_y.as_ptr(),
                receptor_z_angstrom: self.receptor_z.as_ptr(),
                receptor_vdw_radius_angstrom: self.receptor_radii.as_ptr(),
                ligand_vdw_radius_angstrom: self.ligand_radii.as_ptr(),
                pocket_center_angstrom: [1.5, 0.0, 0.0],
                parent_atom_index: self.parents.as_ptr(),
                rotatable_child_atom_index: self.rotors.as_ptr(),
                internal_pair_atom_i: self.internal_i.as_ptr(),
                internal_pair_atom_j: self.internal_j.as_ptr(),
                receptor_overlap_scale: config.receptor_overlap_scale,
                internal_overlap_scale: config.internal_overlap_scale,
                internal_overlap_weight: config.internal_overlap_weight,
                maximum_baseline_v6_steps: config.maximum_baseline_v6_steps,
                maximum_torsions_evaluated: config.maximum_torsions_evaluated,
                maximum_torsion_steps: config.maximum_torsion_steps,
                maximum_backtracking_evaluations: config.maximum_backtracking_evaluations,
                maximum_torsion_step_radians: config.maximum_torsion_step_radians,
                minimum_torsion_step_radians: config.minimum_torsion_step_radians,
                maximum_total_torsion_path_radians: config.maximum_total_torsion_path_radians,
                maximum_centroid_offset_angstrom: config.maximum_centroid_offset_angstrom,
                minimum_selected_final_receptor_penalty: config
                    .minimum_selected_final_receptor_penalty,
                maximum_selected_final_receptor_penalty: config
                    .maximum_selected_final_receptor_penalty,
                penalty_tolerance: config.penalty_tolerance,
                epsilon_angstrom: config.epsilon_angstrom,
                reserved: [0; 8],
            }
        }
    }

    struct BatchStorage {
        candidate_state: [i32; CANDIDATE_COUNT],
        eligible: [u8; CANDIDATE_COUNT],
        max_steps: [usize; CANDIDATE_COUNT],
        baseline_steps: [usize; CANDIDATE_COUNT],
        source_x: Vec<f64>,
        source_y: Vec<f64>,
        source_z: Vec<f64>,
        baseline_x: Vec<f64>,
        baseline_y: Vec<f64>,
        baseline_z: Vec<f64>,
        baseline_angles: Vec<f64>,
    }

    impl BatchStorage {
        fn fixture() -> Self {
            let atom_count = 4;
            let coordinate_count = CANDIDATE_COUNT * atom_count;
            let mut source_x = vec![0.0; coordinate_count];
            let mut source_y = vec![0.0; coordinate_count];
            let source_z = vec![0.0; coordinate_count];
            for slot in 0..CANDIDATE_COUNT {
                let start = slot * atom_count;
                source_x[start..start + atom_count].copy_from_slice(&[0.0, 1.0, 2.0, 2.0]);
                source_y[start..start + atom_count].copy_from_slice(&[0.0, 0.0, 0.0, 1.0]);
            }
            let mut candidate_state = [CANDIDATE_INACTIVE; CANDIDATE_COUNT];
            let mut eligible = [0; CANDIDATE_COUNT];
            let mut max_steps = [0; CANDIDATE_COUNT];
            candidate_state[0] = CANDIDATE_REFINE;
            eligible[0] = 1;
            max_steps[0] = 4;
            Self {
                candidate_state,
                eligible,
                max_steps,
                baseline_steps: [0; CANDIDATE_COUNT],
                baseline_x: source_x.clone(),
                baseline_y: source_y.clone(),
                baseline_z: source_z.clone(),
                source_x,
                source_y,
                source_z,
                baseline_angles: vec![0.0; coordinate_count],
            }
        }

        fn descriptor(&self) -> TorsionV7BatchV1 {
            TorsionV7BatchV1 {
                struct_size: u32::try_from(size_of::<TorsionV7BatchV1>()).unwrap(),
                abi_version: PROVIDER_ABI_VERSION,
                candidate_count: CANDIDATE_COUNT,
                ligand_atom_count: 4,
                candidate_state: self.candidate_state.as_ptr(),
                proposal_is_torsion_eligible: self.eligible.as_ptr(),
                max_steps: self.max_steps.as_ptr(),
                baseline_v6_accepted_steps: self.baseline_steps.as_ptr(),
                source_x_angstrom: self.source_x.as_ptr(),
                source_y_angstrom: self.source_y.as_ptr(),
                source_z_angstrom: self.source_z.as_ptr(),
                baseline_v6_x_angstrom: self.baseline_x.as_ptr(),
                baseline_v6_y_angstrom: self.baseline_y.as_ptr(),
                baseline_v6_z_angstrom: self.baseline_z.as_ptr(),
                baseline_v6_torsion_angles_radians: self.baseline_angles.as_ptr(),
                reserved: [0; 8],
            }
        }
    }

    struct OutputStorage {
        rows: Vec<TorsionV7RowV1>,
        moves: Vec<TorsionV7MoveV1>,
        optimized_x: Vec<f64>,
        optimized_y: Vec<f64>,
        optimized_z: Vec<f64>,
        optimized_angles: Vec<f64>,
        final_x: Vec<f64>,
        final_y: Vec<f64>,
        final_z: Vec<f64>,
        final_angles: Vec<f64>,
    }

    impl OutputStorage {
        fn with_sentinel(atom_count: usize, sentinel: f64) -> Self {
            let mut row = empty_row(0, 91);
            row.slot_index = u32::MAX;
            row.status = 93;
            let mut movement = empty_move(0, 0);
            movement.slot_index = u32::MAX;
            movement.evaluated = 95;
            let coordinate_count = CANDIDATE_COUNT * atom_count;
            Self {
                rows: vec![row; CANDIDATE_COUNT],
                moves: vec![movement; CANDIDATE_COUNT * MAX_MOVES],
                optimized_x: vec![sentinel; coordinate_count],
                optimized_y: vec![sentinel; coordinate_count],
                optimized_z: vec![sentinel; coordinate_count],
                optimized_angles: vec![sentinel; coordinate_count],
                final_x: vec![sentinel; coordinate_count],
                final_y: vec![sentinel; coordinate_count],
                final_z: vec![sentinel; coordinate_count],
                final_angles: vec![sentinel; coordinate_count],
            }
        }
    }

    fn error_output() -> ErrorV1 {
        ErrorV1 {
            struct_size: u32::try_from(size_of::<ErrorV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            message: [0; ERROR_CAPACITY],
            reserved: [0; 4],
        }
    }

    fn error_message(error: &ErrorV1) -> &str {
        let length = error
            .message
            .iter()
            .position(|value| *value == 0)
            .unwrap_or(error.message.len());
        core::str::from_utf8(&error.message[..length]).unwrap()
    }

    unsafe fn refine(
        state: *const c_void,
        batch: &TorsionV7BatchV1,
        output: &mut OutputStorage,
        error: &mut ErrorV1,
    ) -> i32 {
        unsafe {
            bg_rust_cpu_docking_torsion_v7_refine_fixed64(
                state,
                batch,
                output.rows.as_mut_ptr(),
                output.moves.as_mut_ptr(),
                output.optimized_x.as_mut_ptr(),
                output.optimized_y.as_mut_ptr(),
                output.optimized_z.as_mut_ptr(),
                output.optimized_angles.as_mut_ptr(),
                output.final_x.as_mut_ptr(),
                output.final_y.as_mut_ptr(),
                output.final_z.as_mut_ptr(),
                output.final_angles.as_mut_ptr(),
                error,
            )
        }
    }

    #[test]
    fn provider_deep_copies_context_and_preserves_fixed64_failures() {
        let mut context_storage = ContextStorage::fixture();
        let descriptor = context_storage.descriptor();
        let mut state = ptr::null_mut();
        let mut error = error_output();
        let status =
            unsafe { bg_rust_cpu_docking_torsion_v7_create(&descriptor, &mut state, &mut error) };
        assert_eq!(status, STATUS_OK, "{}", error_message(&error));
        assert!(!state.is_null());

        // Mutating every borrowed authority channel after creation proves the
        // persistent provider owns a deep copy rather than caller storage.
        context_storage.parents[0] = 0;
        context_storage.receptor_x[0] = f64::NAN;
        context_storage.ligand_radii[0] = f64::NAN;
        assert_eq!(context_storage.parents[0], 0);
        assert!(context_storage.receptor_x[0].is_nan());
        assert!(context_storage.ligand_radii[0].is_nan());

        let batch_storage = BatchStorage::fixture();
        let batch = batch_storage.descriptor();
        let mut output = OutputStorage::with_sentinel(4, 97.0);
        let status = unsafe { refine(state, &batch, &mut output, &mut error) };
        unsafe { bg_rust_cpu_docking_torsion_v7_destroy(state) };

        assert_eq!(status, STATUS_OK, "{}", error_message(&error));
        assert_eq!(error_message(&error), "");
        assert_eq!(output.rows.len(), CANDIDATE_COUNT);
        for (slot, row) in output.rows.iter().enumerate() {
            assert_eq!(row.slot_index, slot as u32);
        }
        assert_eq!(output.rows[0].status, ROW_REFINED);
        assert_eq!(output.rows[0].failure_code, FAILURE_NONE);
        assert_eq!(output.rows[0].torsion_evaluated, 1);
        assert_eq!(output.rows[0].torsion_variant_available, 1);
        assert_eq!(output.rows[0].torsion_selected, 1);
        assert_eq!(output.rows[0].evaluated_torsion_steps, 4);
        assert_eq!(output.rows[0].accepted_torsion_steps, 4);
        assert!(
            output.rows[0].optimized_combined_penalty < output.rows[0].baseline_combined_penalty
        );
        assert_eq!(output.rows[1].status, ROW_TYPED_FAILURE);
        assert_eq!(output.rows[1].failure_code, FAILURE_UPSTREAM_NOT_ELIGIBLE);
        assert_eq!(
            output
                .moves
                .iter()
                .filter(|movement| movement.evaluated == 1)
                .count(),
            4
        );
        assert_eq!(&output.optimized_x[..4], &output.final_x[..4]);
        assert_eq!(&output.optimized_y[..4], &output.final_y[..4]);
        assert_ne!(&output.final_y[..4], &batch_storage.baseline_y[..4]);
    }

    #[test]
    fn malformed_batch_is_transactional_for_all_scientific_outputs() {
        let context_storage = ContextStorage::fixture();
        let descriptor = context_storage.descriptor();
        let mut state = ptr::null_mut();
        let mut error = error_output();
        let status =
            unsafe { bg_rust_cpu_docking_torsion_v7_create(&descriptor, &mut state, &mut error) };
        assert_eq!(status, STATUS_OK, "{}", error_message(&error));

        let batch_storage = BatchStorage::fixture();
        let mut batch = batch_storage.descriptor();
        batch.candidate_count -= 1;
        let mut output = OutputStorage::with_sentinel(4, 101.0);
        let status = unsafe { refine(state, &batch, &mut output, &mut error) };
        unsafe { bg_rust_cpu_docking_torsion_v7_destroy(state) };

        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert!(error_message(&error).contains("denominator"));
        assert_eq!(output.rows[0].slot_index, u32::MAX);
        assert_eq!(output.rows[0].status, 93);
        assert_eq!(output.moves[0].evaluated, 95);
        assert!(output.optimized_x.iter().all(|value| *value == 101.0));
        assert!(output.final_angles.iter().all(|value| *value == 101.0));
    }

    #[test]
    fn candidate_local_invalid_input_is_a_typed_fixed64_row() {
        let context_storage = ContextStorage::fixture();
        let descriptor = context_storage.descriptor();
        let mut state = ptr::null_mut();
        let mut error = error_output();
        let status =
            unsafe { bg_rust_cpu_docking_torsion_v7_create(&descriptor, &mut state, &mut error) };
        assert_eq!(status, STATUS_OK, "{}", error_message(&error));

        let mut batch_storage = BatchStorage::fixture();
        batch_storage.eligible[0] = 2;
        let batch = batch_storage.descriptor();
        let mut output = OutputStorage::with_sentinel(4, 103.0);
        let status = unsafe { refine(state, &batch, &mut output, &mut error) };
        unsafe { bg_rust_cpu_docking_torsion_v7_destroy(state) };

        assert_eq!(status, STATUS_OK, "{}", error_message(&error));
        assert_eq!(output.rows[0].status, ROW_TYPED_FAILURE);
        assert_eq!(output.rows[0].failure_code, FAILURE_INVALID_INPUT);
        assert_eq!(output.rows[1].status, ROW_TYPED_FAILURE);
        assert_eq!(output.rows[1].failure_code, FAILURE_UPSTREAM_NOT_ELIGIBLE);
        assert_eq!(
            output
                .rows
                .iter()
                .filter(|row| row.status == ROW_TYPED_FAILURE)
                .count(),
            CANDIDATE_COUNT
        );
    }

    #[test]
    fn create_rejects_impossible_pair_count_before_reading_pair_channels() {
        let context_storage = ContextStorage::fixture();
        let mut descriptor = context_storage.descriptor();
        descriptor.internal_pair_count = 7;
        let mut state = ptr::null_mut();
        let mut error = error_output();
        let status =
            unsafe { bg_rust_cpu_docking_torsion_v7_create(&descriptor, &mut state, &mut error) };

        assert_eq!(status, STATUS_CAPACITY_OVERFLOW);
        assert!(state.is_null());
        assert!(error_message(&error).contains("canonical maximum"));
    }

    #[test]
    fn create_validates_context_without_synthetic_objective_evaluation() {
        let context_storage = ContextStorage::fixture();
        let mut descriptor = context_storage.descriptor();
        descriptor.internal_overlap_weight = f64::MAX;
        let mut state = ptr::null_mut();
        let mut error = error_output();
        let status =
            unsafe { bg_rust_cpu_docking_torsion_v7_create(&descriptor, &mut state, &mut error) };

        assert_eq!(status, STATUS_OK, "{}", error_message(&error));
        assert!(!state.is_null());
        unsafe { bg_rust_cpu_docking_torsion_v7_destroy(state) };
    }
}
