use super::*;

use betelgeuze_docking_search::{
    refine_interaction_aware_rigid_v2, refine_interaction_aware_rigid_v3,
    refine_interaction_aware_rigid_v6, NativeRigidRefinementContext,
    NativeRigidRefinementErrorCode, NativeRigidRefinementOutcome, NativeRigidRefinementProfile,
    NativeRigidV2Config, NativeRigidV3Config, NATIVE_RIGID_REFINEMENT_MAX_LIGAND_ATOMS,
    NATIVE_RIGID_REFINEMENT_MAX_PAIR_EVALUATIONS, NATIVE_RIGID_REFINEMENT_MAX_RECEPTOR_ATOMS,
    NATIVE_RIGID_REFINEMENT_MAX_STEPS,
};

const CANDIDATE_COUNT: usize = FIXED64_CANDIDATE_COUNT;
const CANDIDATE_INACTIVE: i32 = 0;
const CANDIDATE_V2: i32 = 1;
const CANDIDATE_V3: i32 = 2;
const CANDIDATE_V6_BASELINE_V2: i32 = 3;
const CANDIDATE_V6_BASELINE_V3: i32 = 4;
const ROW_REFINED: i32 = 1;
const ROW_TYPED_FAILURE: i32 = 2;
const FAILURE_NONE: i32 = 0;
const FAILURE_UPSTREAM_NOT_ELIGIBLE: i32 = 1;
const FAILURE_INVALID_INPUT: i32 = 2;
const FAILURE_NONFINITE_INPUT: i32 = 3;
const FAILURE_PAIR_BUDGET: i32 = 4;
const FAILURE_NONFINITE_DERIVED_VALUE: i32 = 5;
const PROFILE_NONE: i32 = 0;
const PROFILE_V2_TRANSLATION: i32 = 1;
const PROFILE_V3_TRANSLATION_ROTATION: i32 = 2;
const PROFILE_V6_BASELINE_V2: i32 = 3;
const PROFILE_V6_BASELINE_V3: i32 = 4;
const PROFILE_V6_CLEARANCE_V4: i32 = 5;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct RigidV2ConfigV1 {
    overlap_scale: f64,
    maximum_step_angstrom: f64,
    minimum_step_angstrom: f64,
    maximum_total_translation_angstrom: f64,
    maximum_backtracking_evaluations: usize,
    penalty_tolerance: f64,
    epsilon_angstrom: f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct RigidV3ConfigV1 {
    v2: RigidV2ConfigV1,
    maximum_rotation_step_radians: f64,
    minimum_rotation_step_radians: f64,
    maximum_total_rotation_radians: f64,
    maximum_rotation_steps: usize,
    minimum_rotation_relative_penalty_reduction: f64,
    maximum_centroid_offset_angstrom: f64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct RigidContextV1 {
    struct_size: u32,
    abi_version: u32,
    receptor_atom_count: usize,
    ligand_atom_count: usize,
    receptor_x_angstrom: *const f64,
    receptor_y_angstrom: *const f64,
    receptor_z_angstrom: *const f64,
    receptor_vdw_radius_angstrom: *const f64,
    ligand_vdw_radius_angstrom: *const f64,
    pocket_center_angstrom: [f64; 3],
    pocket_radius_angstrom: f64,
    v2: RigidV2ConfigV1,
    v3: RigidV3ConfigV1,
    clearance_v4: RigidV3ConfigV1,
    reserved: [u64; 8],
}

#[repr(C)]
pub struct RigidBatchV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: usize,
    ligand_atom_count: usize,
    candidate_mode: *const i32,
    max_steps: *const usize,
    x_angstrom: *const f64,
    y_angstrom: *const f64,
    z_angstrom: *const f64,
    reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct RigidEvidenceV1 {
    profile: i32,
    available: u8,
    reserved0: [u8; 3],
    accepted_steps: usize,
    accepted_translation_steps: usize,
    accepted_rotation_steps: usize,
    line_search_evaluation_count: usize,
    fallback_direction_step_count: usize,
    initial_penalty: f64,
    final_penalty: f64,
    total_translation_angstrom: [f64; 3],
    total_rotation_vector_radians: [f64; 3],
    total_rotation_path_radians: f64,
    initial_centroid_offset_angstrom: f64,
    final_centroid_offset_angstrom: f64,
    maximum_centroid_offset_angstrom: f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct RigidRowV1 {
    slot_index: u32,
    status: i32,
    failure_code: i32,
    candidate_mode: i32,
    selected_profile: i32,
    baseline_duplicate_of_v2: u8,
    clearance_evaluated: u8,
    clearance_selected: u8,
    reserved0: u8,
    selected: RigidEvidenceV1,
    comparison_v2: RigidEvidenceV1,
    baseline_v3: RigidEvidenceV1,
    clearance_v4: RigidEvidenceV1,
    reserved: [u64; 8],
}

struct RigidState {
    receptor_coordinates: Vec<Vec3>,
    receptor_radii: Vec<f64>,
    ligand_radii: Vec<f64>,
    pocket_center: Vec3,
    pocket_radius: f64,
    v2: NativeRigidV2Config,
    v3: NativeRigidV3Config,
    clearance_v4: NativeRigidV3Config,
}

struct RigidOutput {
    rows: [RigidRowV1; CANDIDATE_COUNT],
    selected_x: Vec<f64>,
    selected_y: Vec<f64>,
    selected_z: Vec<f64>,
    comparison_v2_x: Vec<f64>,
    comparison_v2_y: Vec<f64>,
    comparison_v2_z: Vec<f64>,
    baseline_v3_x: Vec<f64>,
    baseline_v3_y: Vec<f64>,
    baseline_v3_z: Vec<f64>,
    clearance_v4_x: Vec<f64>,
    clearance_v4_y: Vec<f64>,
    clearance_v4_z: Vec<f64>,
}

fn empty_row(slot: usize, mode: i32, failure_code: i32) -> RigidRowV1 {
    RigidRowV1 {
        slot_index: slot as u32,
        status: ROW_TYPED_FAILURE,
        failure_code,
        candidate_mode: mode,
        selected_profile: PROFILE_NONE,
        baseline_duplicate_of_v2: 0,
        clearance_evaluated: 0,
        clearance_selected: 0,
        reserved0: 0,
        selected: RigidEvidenceV1::default(),
        comparison_v2: RigidEvidenceV1::default(),
        baseline_v3: RigidEvidenceV1::default(),
        clearance_v4: RigidEvidenceV1::default(),
        reserved: [0; 8],
    }
}

fn profile_code(profile: NativeRigidRefinementProfile) -> i32 {
    match profile {
        NativeRigidRefinementProfile::V2Translation => PROFILE_V2_TRANSLATION,
        NativeRigidRefinementProfile::V3TranslationRotation => PROFILE_V3_TRANSLATION_ROTATION,
        NativeRigidRefinementProfile::V6BaselineV2 => PROFILE_V6_BASELINE_V2,
        NativeRigidRefinementProfile::V6BaselineV3 => PROFILE_V6_BASELINE_V3,
        NativeRigidRefinementProfile::V6ClearanceV4 => PROFILE_V6_CLEARANCE_V4,
    }
}

fn evidence(outcome: &NativeRigidRefinementOutcome) -> RigidEvidenceV1 {
    let translation = outcome.total_translation_angstrom();
    let rotation = outcome.total_rotation_vector_radians();
    RigidEvidenceV1 {
        profile: profile_code(outcome.profile()),
        available: 1,
        reserved0: [0; 3],
        accepted_steps: outcome.accepted_steps(),
        accepted_translation_steps: outcome.accepted_translation_steps(),
        accepted_rotation_steps: outcome.accepted_rotation_steps(),
        line_search_evaluation_count: outcome.line_search_evaluation_count(),
        fallback_direction_step_count: outcome.fallback_direction_step_count(),
        initial_penalty: outcome.initial_penalty(),
        final_penalty: outcome.final_penalty(),
        total_translation_angstrom: [translation.x, translation.y, translation.z],
        total_rotation_vector_radians: [rotation.x, rotation.y, rotation.z],
        total_rotation_path_radians: outcome.total_rotation_path_radians(),
        initial_centroid_offset_angstrom: outcome.initial_centroid_offset_angstrom(),
        final_centroid_offset_angstrom: outcome.final_centroid_offset_angstrom(),
        maximum_centroid_offset_angstrom: outcome.maximum_centroid_offset_angstrom(),
        reserved: [0; 4],
    }
}

fn copy_coordinates(
    outcome: &NativeRigidRefinementOutcome,
    slot: usize,
    ligand_count: usize,
    x: &mut [f64],
    y: &mut [f64],
    z: &mut [f64],
) {
    let offset = slot * ligand_count;
    for (atom, coordinate) in outcome.coordinates_angstrom().iter().enumerate() {
        x[offset + atom] = coordinate.x;
        y[offset + atom] = coordinate.y;
        z[offset + atom] = coordinate.z;
    }
}

fn validate_v2(config: RigidV2ConfigV1) -> Result<NativeRigidV2Config, ProviderError> {
    if !reserved_is_zero(&config.reserved) {
        return Err(ProviderError::abi(
            "rust_cpu rigid V2 reserved fields must be zero",
        ));
    }
    let values = [
        config.overlap_scale,
        config.maximum_step_angstrom,
        config.minimum_step_angstrom,
        config.maximum_total_translation_angstrom,
        config.penalty_tolerance,
        config.epsilon_angstrom,
    ];
    if values
        .iter()
        .any(|value| !value.is_finite() || *value <= 0.0)
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid V2 configuration is non-finite",
        ));
    }
    if !(0.55..=1.0).contains(&config.overlap_scale)
        || config.minimum_step_angstrom > config.maximum_step_angstrom
        || config.maximum_step_angstrom > config.maximum_total_translation_angstrom
        || !(1..=16).contains(&config.maximum_backtracking_evaluations)
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid V2 configuration bounds are invalid",
        ));
    }
    Ok(NativeRigidV2Config {
        overlap_scale: config.overlap_scale,
        maximum_step_angstrom: config.maximum_step_angstrom,
        minimum_step_angstrom: config.minimum_step_angstrom,
        maximum_total_translation_angstrom: config.maximum_total_translation_angstrom,
        maximum_backtracking_evaluations: config.maximum_backtracking_evaluations,
        penalty_tolerance: config.penalty_tolerance,
        epsilon_angstrom: config.epsilon_angstrom,
    })
}

fn validate_v3(config: RigidV3ConfigV1) -> Result<NativeRigidV3Config, ProviderError> {
    if !reserved_is_zero(&config.reserved) {
        return Err(ProviderError::abi(
            "rust_cpu rigid V3 reserved fields must be zero",
        ));
    }
    let v2 = validate_v2(config.v2)?;
    let values = [
        config.maximum_rotation_step_radians,
        config.minimum_rotation_step_radians,
        config.maximum_total_rotation_radians,
        config.minimum_rotation_relative_penalty_reduction,
        config.maximum_centroid_offset_angstrom,
    ];
    if values
        .iter()
        .any(|value| !value.is_finite() || *value <= 0.0)
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid V3 configuration is non-finite",
        ));
    }
    if config.minimum_rotation_step_radians > config.maximum_rotation_step_radians
        || config.maximum_rotation_step_radians > config.maximum_total_rotation_radians
        || !(1..=8).contains(&config.maximum_rotation_steps)
        || config.minimum_rotation_relative_penalty_reduction > 0.25
        || !(0.5..=8.0).contains(&config.maximum_centroid_offset_angstrom)
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid V3 configuration bounds are invalid",
        ));
    }
    Ok(NativeRigidV3Config {
        v2,
        maximum_rotation_step_radians: config.maximum_rotation_step_radians,
        minimum_rotation_step_radians: config.minimum_rotation_step_radians,
        maximum_total_rotation_radians: config.maximum_total_rotation_radians,
        maximum_rotation_steps: config.maximum_rotation_steps,
        minimum_rotation_relative_penalty_reduction: config
            .minimum_rotation_relative_penalty_reduction,
        maximum_centroid_offset_angstrom: config.maximum_centroid_offset_angstrom,
    })
}

unsafe fn build_state(descriptor: &RigidContextV1) -> Result<RigidState, ProviderError> {
    validate_header::<RigidContextV1>(
        descriptor.struct_size,
        descriptor.abi_version,
        "rust_cpu rigid context size mismatch",
    )?;
    if !reserved_is_zero(&descriptor.reserved) {
        return Err(ProviderError::abi(
            "rust_cpu rigid context reserved fields must be zero",
        ));
    }
    let receptor_count = descriptor.receptor_atom_count;
    let ligand_count = descriptor.ligand_atom_count;
    if receptor_count == 0
        || receptor_count > NATIVE_RIGID_REFINEMENT_MAX_RECEPTOR_ATOMS
        || ligand_count == 0
        || ligand_count > NATIVE_RIGID_REFINEMENT_MAX_LIGAND_ATOMS
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid context dimensions are invalid",
        ));
    }
    let pair_count = receptor_count
        .checked_mul(ligand_count)
        .ok_or_else(|| ProviderError::capacity("rust_cpu rigid pair count overflowed"))?;
    if pair_count > NATIVE_RIGID_REFINEMENT_MAX_PAIR_EVALUATIONS {
        return Err(ProviderError::capacity(
            "rust_cpu rigid pair budget exceeded",
        ));
    }
    let receptor_x = unsafe {
        checked_slice(
            descriptor.receptor_x_angstrom,
            receptor_count,
            "rust_cpu rigid receptor x is null",
        )?
    };
    let receptor_y = unsafe {
        checked_slice(
            descriptor.receptor_y_angstrom,
            receptor_count,
            "rust_cpu rigid receptor y is null",
        )?
    };
    let receptor_z = unsafe {
        checked_slice(
            descriptor.receptor_z_angstrom,
            receptor_count,
            "rust_cpu rigid receptor z is null",
        )?
    };
    let receptor_radii = unsafe {
        checked_slice(
            descriptor.receptor_vdw_radius_angstrom,
            receptor_count,
            "rust_cpu rigid receptor radius is null",
        )?
    };
    let ligand_radii = unsafe {
        checked_slice(
            descriptor.ligand_vdw_radius_angstrom,
            ligand_count,
            "rust_cpu rigid ligand radius is null",
        )?
    };
    let receptor_coordinates: Vec<_> = (0..receptor_count)
        .map(|index| Vec3::new(receptor_x[index], receptor_y[index], receptor_z[index]))
        .collect();
    let pocket_center = Vec3::new(
        descriptor.pocket_center_angstrom[0],
        descriptor.pocket_center_angstrom[1],
        descriptor.pocket_center_angstrom[2],
    );
    if receptor_coordinates
        .iter()
        .any(|coordinate| !coordinate.is_finite())
        || receptor_radii
            .iter()
            .chain(ligand_radii)
            .any(|radius| !radius.is_finite() || *radius <= 0.0)
        || !pocket_center.is_finite()
        || !descriptor.pocket_radius_angstrom.is_finite()
        || descriptor.pocket_radius_angstrom <= 0.0
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid context contains non-finite values",
        ));
    }
    Ok(RigidState {
        receptor_coordinates,
        receptor_radii: receptor_radii.to_vec(),
        ligand_radii: ligand_radii.to_vec(),
        pocket_center,
        pocket_radius: descriptor.pocket_radius_angstrom,
        v2: validate_v2(descriptor.v2)?,
        v3: validate_v3(descriptor.v3)?,
        clearance_v4: validate_v3(descriptor.clearance_v4)?,
    })
}

fn map_failure(code: NativeRigidRefinementErrorCode) -> i32 {
    match code {
        NativeRigidRefinementErrorCode::InvalidInput => FAILURE_INVALID_INPUT,
        NativeRigidRefinementErrorCode::NonFiniteInput => FAILURE_NONFINITE_INPUT,
        NativeRigidRefinementErrorCode::PairBudgetExceeded => FAILURE_PAIR_BUDGET,
        NativeRigidRefinementErrorCode::NonFiniteDerivedValue => FAILURE_NONFINITE_DERIVED_VALUE,
    }
}

unsafe fn refine_batch(
    state: &RigidState,
    batch: &RigidBatchV1,
) -> Result<RigidOutput, ProviderError> {
    validate_header::<RigidBatchV1>(
        batch.struct_size,
        batch.abi_version,
        "rust_cpu rigid batch size mismatch",
    )?;
    if !reserved_is_zero(&batch.reserved)
        || batch.candidate_count != CANDIDATE_COUNT
        || batch.ligand_atom_count != state.ligand_radii.len()
    {
        return Err(ProviderError::invalid(
            "rust_cpu rigid fixed64 batch is cross-wired",
        ));
    }
    let coordinate_count = CANDIDATE_COUNT
        .checked_mul(state.ligand_radii.len())
        .ok_or_else(|| ProviderError::capacity("rust_cpu rigid coordinate count overflowed"))?;
    let modes = unsafe {
        checked_slice(
            batch.candidate_mode,
            CANDIDATE_COUNT,
            "rust_cpu rigid mode channel is null",
        )?
    };
    let max_steps = unsafe {
        checked_slice(
            batch.max_steps,
            CANDIDATE_COUNT,
            "rust_cpu rigid step channel is null",
        )?
    };
    let x = unsafe {
        checked_slice(
            batch.x_angstrom,
            coordinate_count,
            "rust_cpu rigid x channel is null",
        )?
    };
    let y = unsafe {
        checked_slice(
            batch.y_angstrom,
            coordinate_count,
            "rust_cpu rigid y channel is null",
        )?
    };
    let z = unsafe {
        checked_slice(
            batch.z_angstrom,
            coordinate_count,
            "rust_cpu rigid z channel is null",
        )?
    };

    let mut output = RigidOutput {
        rows: std::array::from_fn(|slot| {
            empty_row(slot, modes[slot], FAILURE_UPSTREAM_NOT_ELIGIBLE)
        }),
        selected_x: vec![0.0; coordinate_count],
        selected_y: vec![0.0; coordinate_count],
        selected_z: vec![0.0; coordinate_count],
        comparison_v2_x: vec![0.0; coordinate_count],
        comparison_v2_y: vec![0.0; coordinate_count],
        comparison_v2_z: vec![0.0; coordinate_count],
        baseline_v3_x: vec![0.0; coordinate_count],
        baseline_v3_y: vec![0.0; coordinate_count],
        baseline_v3_z: vec![0.0; coordinate_count],
        clearance_v4_x: vec![0.0; coordinate_count],
        clearance_v4_y: vec![0.0; coordinate_count],
        clearance_v4_z: vec![0.0; coordinate_count],
    };
    let context = NativeRigidRefinementContext {
        receptor_coordinates_angstrom: &state.receptor_coordinates,
        receptor_vdw_radii_angstrom: &state.receptor_radii,
        ligand_vdw_radii_angstrom: &state.ligand_radii,
        pocket_center_angstrom: state.pocket_center,
        pocket_radius_angstrom: state.pocket_radius,
    };
    for slot in 0..CANDIDATE_COUNT {
        let mode = modes[slot];
        if mode == CANDIDATE_INACTIVE {
            continue;
        }
        if !matches!(
            mode,
            CANDIDATE_V2 | CANDIDATE_V3 | CANDIDATE_V6_BASELINE_V2 | CANDIDATE_V6_BASELINE_V3
        ) || !(1..=NATIVE_RIGID_REFINEMENT_MAX_STEPS).contains(&max_steps[slot])
        {
            output.rows[slot] = empty_row(slot, mode, FAILURE_INVALID_INPUT);
            continue;
        }
        let offset = slot * state.ligand_radii.len();
        let coordinates: Vec<_> = (0..state.ligand_radii.len())
            .map(|atom| Vec3::new(x[offset + atom], y[offset + atom], z[offset + atom]))
            .collect();
        if coordinates.iter().any(|coordinate| !coordinate.is_finite()) {
            output.rows[slot] = empty_row(slot, mode, FAILURE_NONFINITE_INPUT);
            continue;
        }
        let mut row = empty_row(slot, mode, FAILURE_NONE);
        let result = match mode {
            CANDIDATE_V2 => {
                refine_interaction_aware_rigid_v2(context, &coordinates, max_steps[slot], state.v2)
                    .map(|selected| (selected, None))
            }
            CANDIDATE_V3 => {
                refine_interaction_aware_rigid_v3(context, &coordinates, max_steps[slot], state.v3)
                    .map(|selected| (selected, None))
            }
            CANDIDATE_V6_BASELINE_V2 | CANDIDATE_V6_BASELINE_V3 => {
                refine_interaction_aware_rigid_v6(
                    context,
                    &coordinates,
                    max_steps[slot],
                    mode == CANDIDATE_V6_BASELINE_V3,
                    state.v2,
                    state.v3,
                    state.clearance_v4,
                )
                .map(|outcome| (outcome.selected().clone(), Some(outcome)))
            }
            _ => unreachable!(),
        };
        match result {
            Ok((selected, v6)) => {
                row.status = ROW_REFINED;
                row.failure_code = FAILURE_NONE;
                row.selected_profile = profile_code(selected.profile());
                row.selected = evidence(&selected);
                copy_coordinates(
                    &selected,
                    slot,
                    state.ligand_radii.len(),
                    &mut output.selected_x,
                    &mut output.selected_y,
                    &mut output.selected_z,
                );
                if let Some(v6) = v6 {
                    row.baseline_duplicate_of_v2 = u8::from(v6.baseline_duplicate_of_v2());
                    row.clearance_evaluated = u8::from(v6.clearance_evaluated());
                    row.clearance_selected = u8::from(v6.clearance_selected());
                    if let Some(value) = v6.comparison_v2() {
                        row.comparison_v2 = evidence(value);
                        copy_coordinates(
                            value,
                            slot,
                            state.ligand_radii.len(),
                            &mut output.comparison_v2_x,
                            &mut output.comparison_v2_y,
                            &mut output.comparison_v2_z,
                        );
                    }
                    if let Some(value) = v6.baseline_v3() {
                        row.baseline_v3 = evidence(value);
                        copy_coordinates(
                            value,
                            slot,
                            state.ligand_radii.len(),
                            &mut output.baseline_v3_x,
                            &mut output.baseline_v3_y,
                            &mut output.baseline_v3_z,
                        );
                    }
                    if let Some(value) = v6.clearance_v4() {
                        row.clearance_v4 = evidence(value);
                        copy_coordinates(
                            value,
                            slot,
                            state.ligand_radii.len(),
                            &mut output.clearance_v4_x,
                            &mut output.clearance_v4_y,
                            &mut output.clearance_v4_z,
                        );
                    }
                }
                output.rows[slot] = row;
            }
            Err(error) => {
                output.rows[slot] = empty_row(slot, mode, map_failure(error.code()));
            }
        }
    }
    Ok(output)
}

fn aligned<T>(pointer: *mut T) -> bool {
    !pointer.is_null() && (pointer as usize) % align_of::<T>() == 0
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_rigid_refinement_create(
    descriptor: *const RigidContextV1,
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
        write_error(error, "rust_cpu rigid create pointer is null or misaligned");
        return STATUS_INVALID_ARGUMENT;
    }
    unsafe { ptr::write(out_state, ptr::null_mut()) };
    let descriptor = unsafe { &*descriptor };
    match catch_unwind(AssertUnwindSafe(|| unsafe { build_state(descriptor) })) {
        Ok(Ok(state)) => {
            unsafe { ptr::write(out_state, Box::into_raw(Box::new(state)).cast::<c_void>()) };
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu rigid context creation panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_rigid_refinement_destroy(state: *mut c_void) {
    if !state.is_null() {
        drop(unsafe { Box::from_raw(state.cast::<RigidState>()) });
    }
}

#[allow(clippy::too_many_arguments)]
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_rigid_refinement_fixed64(
    state: *const c_void,
    batch: *const RigidBatchV1,
    out_rows: *mut RigidRowV1,
    out_selected_x: *mut f64,
    out_selected_y: *mut f64,
    out_selected_z: *mut f64,
    out_comparison_v2_x: *mut f64,
    out_comparison_v2_y: *mut f64,
    out_comparison_v2_z: *mut f64,
    out_baseline_v3_x: *mut f64,
    out_baseline_v3_y: *mut f64,
    out_baseline_v3_z: *mut f64,
    out_clearance_v4_x: *mut f64,
    out_clearance_v4_y: *mut f64,
    out_clearance_v4_z: *mut f64,
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
    let pointers_valid = aligned(out_rows)
        && aligned(out_selected_x)
        && aligned(out_selected_y)
        && aligned(out_selected_z)
        && aligned(out_comparison_v2_x)
        && aligned(out_comparison_v2_y)
        && aligned(out_comparison_v2_z)
        && aligned(out_baseline_v3_x)
        && aligned(out_baseline_v3_y)
        && aligned(out_baseline_v3_z)
        && aligned(out_clearance_v4_x)
        && aligned(out_clearance_v4_y)
        && aligned(out_clearance_v4_z);
    if state.is_null() || batch.is_null() || !pointers_valid {
        write_error(error, "rust_cpu rigid refine pointer is null or misaligned");
        return STATUS_INVALID_ARGUMENT;
    }
    let state = unsafe { &*state.cast::<RigidState>() };
    let batch = unsafe { &*batch };
    match catch_unwind(AssertUnwindSafe(|| unsafe { refine_batch(state, batch) })) {
        Ok(Ok(output)) => {
            let coordinate_count = CANDIDATE_COUNT * state.ligand_radii.len();
            unsafe {
                ptr::copy_nonoverlapping(output.rows.as_ptr(), out_rows, CANDIDATE_COUNT);
                ptr::copy_nonoverlapping(
                    output.selected_x.as_ptr(),
                    out_selected_x,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.selected_y.as_ptr(),
                    out_selected_y,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.selected_z.as_ptr(),
                    out_selected_z,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.comparison_v2_x.as_ptr(),
                    out_comparison_v2_x,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.comparison_v2_y.as_ptr(),
                    out_comparison_v2_y,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.comparison_v2_z.as_ptr(),
                    out_comparison_v2_z,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.baseline_v3_x.as_ptr(),
                    out_baseline_v3_x,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.baseline_v3_y.as_ptr(),
                    out_baseline_v3_y,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.baseline_v3_z.as_ptr(),
                    out_baseline_v3_z,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.clearance_v4_x.as_ptr(),
                    out_clearance_v4_x,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.clearance_v4_y.as_ptr(),
                    out_clearance_v4_y,
                    coordinate_count,
                );
                ptr::copy_nonoverlapping(
                    output.clearance_v4_z.as_ptr(),
                    out_clearance_v4_z,
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
            write_error(error, "rust_cpu rigid fixed64 refinement panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v2_config() -> RigidV2ConfigV1 {
        RigidV2ConfigV1 {
            overlap_scale: 0.75,
            maximum_step_angstrom: 0.30,
            minimum_step_angstrom: 0.009_375,
            maximum_total_translation_angstrom: 2.25,
            maximum_backtracking_evaluations: 6,
            penalty_tolerance: 1.0e-18,
            epsilon_angstrom: 1.0e-9,
            reserved: [0; 4],
        }
    }

    fn v3_config(clearance: bool) -> RigidV3ConfigV1 {
        let mut v2 = v2_config();
        if clearance {
            v2.overlap_scale = 0.80;
            v2.maximum_total_translation_angstrom = 4.0;
        }
        RigidV3ConfigV1 {
            v2,
            maximum_rotation_step_radians: std::f64::consts::PI / 36.0,
            minimum_rotation_step_radians: std::f64::consts::PI / 1_152.0,
            maximum_total_rotation_radians: if clearance {
                std::f64::consts::PI / 6.0
            } else {
                std::f64::consts::PI / 18.0
            },
            maximum_rotation_steps: if clearance { 6 } else { 2 },
            minimum_rotation_relative_penalty_reduction: 0.01,
            maximum_centroid_offset_angstrom: 4.0,
            reserved: [0; 4],
        }
    }

    #[test]
    fn provider_preserves_fixed64_modes_failures_and_v6_evidence() {
        let receptor_x = [6.0];
        let receptor_y = [0.0];
        let receptor_z = [0.0];
        let receptor_radii = [1.5];
        let ligand_radii = [1.5, 1.5];
        let descriptor = RigidContextV1 {
            struct_size: size_of::<RigidContextV1>() as u32,
            abi_version: PROVIDER_ABI_VERSION,
            receptor_atom_count: 1,
            ligand_atom_count: 2,
            receptor_x_angstrom: receptor_x.as_ptr(),
            receptor_y_angstrom: receptor_y.as_ptr(),
            receptor_z_angstrom: receptor_z.as_ptr(),
            receptor_vdw_radius_angstrom: receptor_radii.as_ptr(),
            ligand_vdw_radius_angstrom: ligand_radii.as_ptr(),
            pocket_center_angstrom: [0.0; 3],
            pocket_radius_angstrom: 8.0,
            v2: v2_config(),
            v3: v3_config(false),
            clearance_v4: v3_config(true),
            reserved: [0; 8],
        };
        let state = unsafe { build_state(&descriptor) }
            .unwrap_or_else(|error| panic!("state build failed: {}", error.message));
        let mut modes = [CANDIDATE_INACTIVE; CANDIDATE_COUNT];
        modes[0] = CANDIDATE_V2;
        modes[1] = CANDIDATE_V3;
        modes[2] = CANDIDATE_V6_BASELINE_V2;
        modes[3] = CANDIDATE_V6_BASELINE_V3;
        modes[4] = 99;
        let steps = [8usize; CANDIDATE_COUNT];
        let mut x = vec![0.0; CANDIDATE_COUNT * 2];
        let mut y = vec![0.0; CANDIDATE_COUNT * 2];
        let z = vec![0.0; CANDIDATE_COUNT * 2];
        for slot in 0..CANDIDATE_COUNT {
            x[slot * 2] = 0.0;
            x[slot * 2 + 1] = 0.0;
            y[slot * 2] = -0.5;
            y[slot * 2 + 1] = 0.5;
        }
        let batch = RigidBatchV1 {
            struct_size: size_of::<RigidBatchV1>() as u32,
            abi_version: PROVIDER_ABI_VERSION,
            candidate_count: CANDIDATE_COUNT,
            ligand_atom_count: 2,
            candidate_mode: modes.as_ptr(),
            max_steps: steps.as_ptr(),
            x_angstrom: x.as_ptr(),
            y_angstrom: y.as_ptr(),
            z_angstrom: z.as_ptr(),
            reserved: [0; 8],
        };
        let output = unsafe { refine_batch(&state, &batch) }
            .unwrap_or_else(|error| panic!("batch refine failed: {}", error.message));
        assert_eq!(output.rows.len(), CANDIDATE_COUNT);
        assert_eq!(output.rows[0].status, ROW_REFINED);
        assert_eq!(
            output.rows[1].selected_profile,
            PROFILE_V3_TRANSLATION_ROTATION
        );
        assert_eq!(output.rows[2].selected_profile, PROFILE_V6_BASELINE_V2);
        assert_eq!(output.rows[3].selected_profile, PROFILE_V6_CLEARANCE_V4);
        assert_eq!(output.rows[3].comparison_v2.available, 1);
        assert_eq!(output.rows[3].baseline_v3.available, 1);
        assert_eq!(output.rows[3].clearance_v4.available, 1);
        assert_eq!(output.rows[4].failure_code, FAILURE_INVALID_INPUT);
        assert_eq!(output.rows[5].failure_code, FAILURE_UPSTREAM_NOT_ELIGIBLE);
    }
}
