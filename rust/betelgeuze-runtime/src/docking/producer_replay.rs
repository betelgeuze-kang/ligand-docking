//! Native producer placement replay and independent scientific comparison.

use std::mem::MaybeUninit;
use std::ptr::NonNull;

use betelgeuze_docking_search::{
    generate_native_fixed64_single_anchor, orientations,
    Fixed64Allocation as IndependentFixed64Allocation,
    Fixed64FeatureGeometryInventory as IndependentFixed64FeatureGeometryInventory,
    Fixed64GeometricInput as IndependentFixed64GeometricInput,
    Fixed64PlacementErrorCode as IndependentFixed64PlacementErrorCode,
    Fixed64PlacementSource as IndependentFixed64PlacementSource, Quaternion, Vec3,
    FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM, NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID,
    NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID,
};

use super::{
    canonical_coordinate_sha256, coordinate_segment, digest_present,
    fixed64_lane_and_placement_for_slot, independent_placement_source, init, raw_coordinate_source,
    status_result, sys, Backend, CanonicalHasher, ContextInner, Error, ErrorCode,
    Fixed64CoordinateSource, Fixed64SourceEvidence, PositionSoa, Result, Sha256,
};

const NATIVE_FIXED64_SINGLE_ANCHOR_ABI_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_single_anchor_placement/1.0.0";

#[derive(Debug, Clone, PartialEq)]
pub(super) struct NativePlacementReplay {
    status: i32,
    failure_code: i32,
    coordinates: Vec<Vec3>,
    quaternion: Quaternion,
    output_coordinate_sha256: Sha256,
    placement_receipt_sha256: Sha256,
}

fn canonical_single_anchor_shared_receipt(
    output: &sys::bg_docking_fixed64_single_anchor_output_v1,
    source: Fixed64SourceEvidence,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_single_anchor_abi/native-v1");
    hash.string(NATIVE_FIXED64_SINGLE_ANCHOR_ABI_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID);
    hash.digest(output.allocation_inventory_sha256);
    hash.digest(output.allocation_receipt_sha256);
    hash.digest(output.allocation_slot_receipt_sha256);
    hash.u32(output.slot_index);
    hash.u32(output.lane as u32);
    hash.u32(output.lane_offset);
    hash.u32(output.anchor_kind as u32);
    hash.u32(output.backend as u32);
    hash.digest(source.receipt_sha256);
    hash.digest(source.proposal_sha256);
    hash.digest(source.coordinate_sha256);
    hash.digest(output.feature_geometry_inventory_sha256);
    hash.digest(output.selected_ligand_feature_geometry_sha256);
    hash.digest(output.selected_receptor_feature_geometry_sha256);
    hash.u32(output.status as u32);
    hash.u32(output.failure_code as u32);
    for value in [
        output.ligand_anchor_point_angstrom,
        output.receptor_anchor_point_angstrom,
        output.target_anchor_point_angstrom,
        output.local_surface_normal,
        output.approach_vector,
        output.ligand_direction,
        output.alignment_target_direction,
    ] {
        hash.vec3(Vec3::new(value[0], value[1], value[2]));
    }
    hash.f64(output.target_distance_angstrom);
    hash.f64(output.twist_angle_radians);
    hash.f64(output.quaternion_x);
    hash.f64(output.quaternion_y);
    hash.f64(output.quaternion_z);
    hash.f64(output.quaternion_w);
    hash.vec3(Vec3::new(
        output.translation_angstrom[0],
        output.translation_angstrom[1],
        output.translation_angstrom[2],
    ));
    hash.digest(output.output_coordinate_sha256);
    hash.digest([0; 32]);
    hash.digest([0; 32]);
    for value in [output.coordinates_written, 0, 1, 1, 1, 0, 0, 0, 0, 1] {
        hash.byte(value);
    }
    for _ in 0..7 {
        hash.byte(0);
    }
    hash.finish()
}

fn replay_coordinates(written: u8, x: &[f64], y: &[f64], z: &[f64]) -> Result<Vec<Vec3>> {
    match written {
        0 => Ok(Vec::new()),
        1 => Ok(x
            .iter()
            .zip(y)
            .zip(z)
            .map(|((x, y), z)| Vec3::new(*x, *y, *z))
            .collect()),
        _ => Err(Error::local(
            ErrorCode::AbiMismatch,
            "native placement replay returned a non-boolean coordinate flag",
        )),
    }
}

#[allow(clippy::too_many_arguments)]
pub(super) fn replay_native_placements(
    context: &ContextInner,
    admission: NonNull<sys::bg_docking_geometric_admission_v1>,
    allocation_input: &sys::bg_docking_fixed64_allocation_input_v1,
    producer_input: &sys::bg_docking_fixed64_producer_input_v1,
    expected_allocation: &IndependentFixed64Allocation,
    expected_feature_geometry_inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
    expected_sources: &[Option<Fixed64CoordinateSource<'_>>],
    ligand_atom_count: usize,
    pocket_center_angstrom: [f64; 3],
    pocket_normal: [f64; 3],
    backend: Backend,
) -> Result<[Option<NativePlacementReplay>; 64]> {
    const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    // SAFETY: this ABI row is a repr(C) aggregate containing only numeric
    // fields, raw pointers, and recursively zero-valid aggregates.
    let empty_allocation_row =
        unsafe { MaybeUninit::<sys::bg_docking_fixed64_allocation_row_v1>::zeroed().assume_init() };
    let mut allocation_rows = vec![empty_allocation_row; CANDIDATE_COUNT];
    let mut allocation_output = init(sys::bg_docking_fixed64_allocation_output_v1_init)?;
    allocation_output.row_capacity = CANDIDATE_COUNT as u64;
    allocation_output.rows = allocation_rows.as_mut_ptr();
    // SAFETY: the input descriptor and exact-capacity output remain live for the call.
    status_result(unsafe {
        sys::bg_docking_fixed64_allocation_v1_build(allocation_input, &mut allocation_output)
    })?;
    if allocation_output.row_count != CANDIDATE_COUNT as u64
        || allocation_output.inventory_sha256 != expected_allocation.inventory_sha256()
        || allocation_output.allocation_receipt_sha256 != expected_allocation.receipt_sha256()
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native placement replay allocation disagrees with independent allocation",
        ));
    }
    let ligand_atom_count_u64 = u64::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::CapacityOverflow,
            "native placement replay ligand denominator does not fit u64",
        )
    })?;
    let mut replays: [Option<NativePlacementReplay>; CANDIDATE_COUNT] =
        std::array::from_fn(|_| None);
    for slot_index in 0..CANDIDATE_COUNT {
        let Some((_, placement_kind)) = fixed64_lane_and_placement_for_slot(slot_index) else {
            continue;
        };
        if !matches!(
            placement_kind,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
                | sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
        ) || !expected_allocation.slots()[slot_index].generation_eligible()
        {
            continue;
        }
        let Some(source) = expected_sources[slot_index] else {
            continue;
        };
        if placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
            && !selected_feature_geometry_available(
                &expected_allocation.slots()[slot_index],
                expected_feature_geometry_inventory,
            )
        {
            continue;
        }
        let source_input = raw_coordinate_source(source, ligand_atom_count_u64);
        let mut x = vec![0.0; ligand_atom_count];
        let mut y = vec![0.0; ligand_atom_count];
        let mut z = vec![0.0; ligand_atom_count];
        if placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3 {
            let mut input = init(sys::bg_docking_fixed64_indexed_so3_input_v1_init)?;
            input.allocation_inventory_sha256 = allocation_output.inventory_sha256;
            input.allocation_receipt_sha256 = allocation_output.allocation_receipt_sha256;
            input.allocation_row_count = allocation_output.row_count;
            input.allocation_rows = allocation_rows.as_ptr();
            input.slot_index = slot_index as u32;
            input.source = source_input.source;
            input.ligand_atom_count = ligand_atom_count_u64;
            input.source_x_angstrom = source_input.x_angstrom;
            input.source_y_angstrom = source_input.y_angstrom;
            input.source_z_angstrom = source_input.z_angstrom;
            input.pocket_center_angstrom = pocket_center_angstrom;
            input.pocket_normal = pocket_normal;
            let mut output = init(sys::bg_docking_fixed64_indexed_so3_output_v1_init)?;
            output.coordinate_capacity = ligand_atom_count_u64;
            output.x_angstrom = x.as_mut_ptr();
            output.y_angstrom = y.as_mut_ptr();
            output.z_angstrom = z.as_mut_ptr();
            // SAFETY: every descriptor and exact-capacity channel remains live.
            status_result(unsafe {
                sys::bg_docking_fixed64_indexed_so3_v1_place(
                    context.raw_handle(),
                    &input,
                    &mut output,
                )
            })?;
            if output.slot_index as usize != slot_index
                || output.backend != backend.as_raw()
                || output.ligand_atom_count != ligand_atom_count_u64
                || output.source_identity_verified != 1
                || output.allocation_identity_verified != 1
                || output.denominator_preserved != 1
                || output.result_dependent_input_consumed != 0
                || output.molecular_execution_authorized != 0
                || output.reservation_authorized != 0
                || output.benchmark_execution_authorized != 0
                || output.production_claim_authorized != 0
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native indexed-SO3 replay violated its identity or authority boundary",
                ));
            }
            replays[slot_index] = Some(NativePlacementReplay {
                status: output.status,
                failure_code: output.failure_code,
                coordinates: replay_coordinates(output.coordinates_written, &x, &y, &z)?,
                quaternion: Quaternion::new(
                    output.quaternion_x,
                    output.quaternion_y,
                    output.quaternion_z,
                    output.quaternion_w,
                ),
                output_coordinate_sha256: output.output_coordinate_sha256,
                placement_receipt_sha256: output.placement_receipt_sha256,
            });
            continue;
        }
        let mut input = init(sys::bg_docking_fixed64_single_anchor_input_v1_init)?;
        input.allocation_input = allocation_input;
        input.slot_index = slot_index as u32;
        input.source = source_input.source;
        input.ligand_atom_count = ligand_atom_count_u64;
        input.source_x_angstrom = source_input.x_angstrom;
        input.source_y_angstrom = source_input.y_angstrom;
        input.source_z_angstrom = source_input.z_angstrom;
        input.feature_geometry_count = producer_input.feature_geometry_count;
        input.feature_geometry_rows = producer_input.feature_geometry_rows;
        input.feature_atom_index_count = producer_input.feature_atom_index_count;
        input.feature_atom_indices = producer_input.feature_atom_indices;
        input.feature_geometry_inventory_sha256 = producer_input.feature_geometry_inventory_sha256;
        let mut output = init(sys::bg_docking_fixed64_single_anchor_output_v1_init)?;
        output.coordinate_capacity = ligand_atom_count_u64;
        output.x_angstrom = x.as_mut_ptr();
        output.y_angstrom = y.as_mut_ptr();
        output.z_angstrom = z.as_mut_ptr();
        // SAFETY: every descriptor, persistent admission, and output remains live.
        status_result(unsafe {
            sys::bg_docking_fixed64_single_anchor_v1_place(
                context.raw_handle(),
                admission.as_ptr(),
                &input,
                &mut output,
            )
        })?;
        if output.slot_index as usize != slot_index
            || output.backend != backend.as_raw()
            || output.ligand_atom_count != ligand_atom_count_u64
            || output.source_identity_verified != 1
            || output.allocation_identity_verified != 1
            || output.feature_identity_verified != 1
            || output.geometric_identity_verified != 1
            || output.denominator_preserved != 1
            || output.result_dependent_input_consumed != 0
            || output.fallback_allowed != 0
            || output.multi_anchor_consumed != 0
            || output.molecular_execution_authorized != 0
            || output.reservation_authorized != 0
            || output.benchmark_execution_authorized != 0
            || output.existing_rank_auto_change_authorized != 0
            || output.customer_pose_emission_authorized != 0
            || output.production_claim_authorized != 0
            || output.scientific_claim_authorized != 0
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native single-anchor replay violated its identity or authority boundary",
            ));
        }
        replays[slot_index] = Some(NativePlacementReplay {
            status: output.status,
            failure_code: output.failure_code,
            coordinates: replay_coordinates(output.coordinates_written, &x, &y, &z)?,
            quaternion: Quaternion::new(
                output.quaternion_x,
                output.quaternion_y,
                output.quaternion_z,
                output.quaternion_w,
            ),
            output_coordinate_sha256: output.output_coordinate_sha256,
            placement_receipt_sha256: canonical_single_anchor_shared_receipt(
                &output,
                source.evidence,
            ),
        });
    }
    Ok(replays)
}

fn placement_tolerance(backend: Backend) -> f64 {
    match backend {
        Backend::HipFast => 2.0e-9,
        Backend::HipSafe => 2.0e-10,
        Backend::Auto | Backend::CppCpuReference | Backend::RustCpu => 2.0e-12,
    }
}

fn placement_scalar_close(backend: Backend, observed: f64, expected: f64) -> bool {
    let scale = 1.0_f64.max(observed.abs()).max(expected.abs());
    observed.is_finite()
        && expected.is_finite()
        && (observed - expected).abs() <= placement_tolerance(backend) * scale
}

fn placement_coordinates_close(
    backend: Backend,
    observed: PositionSoa<'_>,
    expected: &[Vec3],
) -> bool {
    observed.x_angstrom.len() == expected.len()
        && observed.y_angstrom.len() == expected.len()
        && observed.z_angstrom.len() == expected.len()
        && expected.iter().enumerate().all(|(atom, expected)| {
            placement_scalar_close(backend, observed.x_angstrom[atom], expected.x)
                && placement_scalar_close(backend, observed.y_angstrom[atom], expected.y)
                && placement_scalar_close(backend, observed.z_angstrom[atom], expected.z)
        })
}

fn placement_quaternion_close(
    backend: Backend,
    row: &sys::bg_docking_fixed64_producer_row_v1,
    expected: Quaternion,
) -> bool {
    [
        (row.placement_quaternion_x, expected.x),
        (row.placement_quaternion_y, expected.y),
        (row.placement_quaternion_z, expected.z),
        (row.placement_quaternion_w, expected.w),
    ]
    .into_iter()
    .all(|(observed, expected)| placement_scalar_close(backend, observed, expected))
}

fn native_replay_coordinates_match(
    observed: PositionSoa<'_>,
    replay: &NativePlacementReplay,
) -> bool {
    observed.x_angstrom.len() == replay.coordinates.len()
        && replay
            .coordinates
            .iter()
            .enumerate()
            .all(|(atom, expected)| {
                observed.x_angstrom[atom].to_bits() == expected.x.to_bits()
                    && observed.y_angstrom[atom].to_bits() == expected.y.to_bits()
                    && observed.z_angstrom[atom].to_bits() == expected.z.to_bits()
            })
}

fn native_replay_quaternion_matches(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    replay: &NativePlacementReplay,
) -> bool {
    [
        (row.placement_quaternion_x, replay.quaternion.x),
        (row.placement_quaternion_y, replay.quaternion.y),
        (row.placement_quaternion_z, replay.quaternion.z),
        (row.placement_quaternion_w, replay.quaternion.w),
    ]
    .into_iter()
    .all(|(observed, expected)| observed.to_bits() == expected.to_bits())
}

#[derive(Debug, Clone, PartialEq)]
struct IndependentIndexedSo3Replay {
    coordinates: Vec<Vec3>,
    quaternion: Quaternion,
}

fn independent_indexed_so3_replay(
    allocation: &IndependentFixed64Allocation,
    slot_index: usize,
    source: &IndependentFixed64PlacementSource,
    pocket_center: Vec3,
    canonical_pocket_normal: Vec3,
) -> Result<std::result::Result<IndependentIndexedSo3Replay, i32>> {
    let slot = allocation.slots().get(slot_index).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 slot is outside fixed64",
        )
    })?;
    let sequence_index = slot.so3_sequence_index().ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 slot lacks its frozen sequence index",
        )
    })?;
    let parent = slot.generation_parent().ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 slot lacks its generation parent",
        )
    })?;
    let evidence = source.evidence();
    if parent.receipt_sha256 != evidence.receipt_sha256
        || parent.proposal_sha256 != evidence.proposal_sha256
        || parent.coordinate_sha256 != evidence.coordinate_sha256
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 source is cross-wired to its allocation slot",
        ));
    }
    let coordinates = source.coordinates_angstrom();
    let first = coordinates[0];
    if !coordinates[1..]
        .iter()
        .any(|coordinate| coordinate.minus(first).norm_squared() > 1.0e-12)
    {
        return Ok(Err(
            sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY,
        ));
    }
    if !canonical_pocket_normal.is_finite()
        || (canonical_pocket_normal.norm() - 1.0).abs() > 1.0e-15
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 pocket normal is not canonical",
        ));
    }
    let mut seed = CanonicalHasher::new("betelgeuze.fixed64_indexed_so3_seed/native-v1");
    seed.digest(evidence.receipt_sha256);
    seed.digest(evidence.proposal_sha256);
    seed.digest(evidence.coordinate_sha256);
    seed.vec3(pocket_center);
    seed.vec3(canonical_pocket_normal);
    seed.string(NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID);
    let sequence = match orientations(seed.finish(), usize::from(sequence_index) + 1) {
        Ok(sequence) => sequence,
        Err(_) => {
            return Ok(Err(
                sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT,
            ));
        }
    };
    let selected = sequence.get(usize::from(sequence_index)).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 sequence selection is absent",
        )
    })?;
    if selected.orientation_index != u32::from(sequence_index) {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 accepted sequence index changed",
        ));
    }
    let mut source_center = Vec3::new(0.0, 0.0, 0.0);
    for coordinate in coordinates {
        source_center = source_center.plus(*coordinate);
    }
    source_center = source_center.scale(1.0 / coordinates.len() as f64);
    let translation = pocket_center.minus(selected.quaternion.rotate(source_center));
    let output: Vec<Vec3> = coordinates
        .iter()
        .map(|coordinate| selected.quaternion.rotate(*coordinate).plus(translation))
        .collect();
    if output.iter().any(|coordinate| {
        !coordinate.is_finite()
            || coordinate.x.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
            || coordinate.y.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
            || coordinate.z.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
    }) {
        return Ok(Err(
            sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT,
        ));
    }
    Ok(Ok(IndependentIndexedSo3Replay {
        coordinates: output,
        quaternion: selected.quaternion,
    }))
}

fn require_preplacement_failure(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    failure_code: sys::bg_docking_fixed64_producer_failure,
) -> Result<()> {
    if row.status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
        || row.failure_code != failure_code
        || row.component_failure_code != 0
        || digest_present(&row.placement_receipt_sha256)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 pre-placement failure disagrees with independent replay",
        ));
    }
    Ok(())
}

fn require_placement_failure(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    producer_failure: sys::bg_docking_fixed64_producer_failure,
    component_failure: i32,
) -> Result<()> {
    if row.status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
        || row.failure_code != producer_failure
        || row.component_failure_code != component_failure
        || !digest_present(&row.placement_receipt_sha256)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 placement failure disagrees with independent replay",
        ));
    }
    Ok(())
}

fn single_anchor_component_failure(code: IndependentFixed64PlacementErrorCode) -> Option<i32> {
    match code {
        IndependentFixed64PlacementErrorCode::DegenerateLigandDirection => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION)
        }
        IndependentFixed64PlacementErrorCode::DegenerateReceptorDirection => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_RECEPTOR_DIRECTION)
        }
        IndependentFixed64PlacementErrorCode::DegenerateLocalSurfaceNormal => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL)
        }
        IndependentFixed64PlacementErrorCode::DegenerateAromaticPlane => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE)
        }
        IndependentFixed64PlacementErrorCode::DegeneratePrincipalAxis => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_PRINCIPAL_AXIS)
        }
        IndependentFixed64PlacementErrorCode::InternalInvariant => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT)
        }
        _ => None,
    }
}

fn selected_feature_geometry_available(
    slot: &betelgeuze_docking_search::Fixed64Slot,
    inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
) -> bool {
    let Some(inventory) = inventory else {
        return false;
    };
    slot.selected_source_receipt_sha256s().len() == 2
        && slot
            .selected_source_receipt_sha256s()
            .iter()
            .all(|receipt| inventory.feature_for_allocation_receipt(*receipt).is_some())
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_independent_producer_placement(
    backend: Backend,
    allocation: &IndependentFixed64Allocation,
    feature_inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
    geometric_input: &IndependentFixed64GeometricInput,
    canonical_pocket_normal: [f64; 3],
    row: &sys::bg_docking_fixed64_producer_row_v1,
    producer_coordinates: [&[f64]; 3],
    slot_index: usize,
    ligand_atom_count: usize,
    expected_source: Option<Fixed64CoordinateSource<'_>>,
    native_replay: Option<&NativePlacementReplay>,
) -> Result<()> {
    if !matches!(
        row.placement_kind,
        sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
            | sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
    ) {
        return Ok(());
    }
    let slot = allocation.slots().get(slot_index).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 placement slot is outside independent allocation",
        )
    })?;
    if !slot.generation_eligible() {
        if native_replay.is_some() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native placement replay ran for an allocation-ineligible slot",
            ));
        }
        return require_preplacement_failure(
            row,
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE,
        );
    }
    let Some(source) = expected_source else {
        if native_replay.is_some() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native placement replay ran without a frozen source",
            ));
        }
        return require_preplacement_failure(
            row,
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE,
        );
    };
    if row.placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
        && !selected_feature_geometry_available(slot, feature_inventory)
    {
        if native_replay.is_some() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native placement replay ran without selected feature geometry",
            ));
        }
        return require_preplacement_failure(
            row,
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE,
        );
    }
    let native_replay = native_replay.ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native placement replay is absent for an executed placement",
        )
    })?;
    let source = independent_placement_source(source)?;
    let observed = coordinate_segment(producer_coordinates, slot_index, ligand_atom_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 placement coordinate segment is absent",
            )
        })?;
    if row.placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3 {
        match independent_indexed_so3_replay(
            allocation,
            slot_index,
            &source,
            Vec3::new(
                geometric_input.pocket_center_angstrom().x,
                geometric_input.pocket_center_angstrom().y,
                geometric_input.pocket_center_angstrom().z,
            ),
            Vec3::new(
                canonical_pocket_normal[0],
                canonical_pocket_normal[1],
                canonical_pocket_normal[2],
            ),
        ) {
            Ok(Ok(placement)) => {
                let status_matches = row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
                let coordinates_match =
                    placement_coordinates_close(backend, observed, &placement.coordinates);
                let quaternion_matches =
                    placement_quaternion_close(backend, row, placement.quaternion);
                let coordinate_receipt_matches =
                    row.output_coordinate_sha256 == canonical_coordinate_sha256(observed);
                let native_replay_matches = native_replay.status
                    == sys::BG_DOCKING_FIXED64_INDEXED_SO3_PLACED
                    && native_replay.failure_code
                        == sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE
                    && native_replay.output_coordinate_sha256 == row.output_coordinate_sha256
                    && native_replay_coordinates_match(observed, native_replay)
                    && native_replay_quaternion_matches(row, native_replay);
                let placement_receipt_matches =
                    row.placement_receipt_sha256 == native_replay.placement_receipt_sha256;
                if !status_matches
                    || !coordinates_match
                    || !quaternion_matches
                    || !coordinate_receipt_matches
                    || !native_replay_matches
                    || !placement_receipt_matches
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        format!(
                            "native fixed64 indexed-SO3 placement disagrees with independent replay: status={status_matches}, coordinates={coordinates_match}, quaternion={quaternion_matches}, coordinate_receipt={coordinate_receipt_matches}, native_replay={native_replay_matches}, placement_receipt={placement_receipt_matches}"
                        ),
                    ));
                }
            }
            Ok(Err(component_failure)) => {
                if native_replay.status != sys::BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE
                    || native_replay.failure_code != component_failure
                    || !native_replay.coordinates.is_empty()
                    || native_replay.output_coordinate_sha256 != [0; 32]
                    || row.placement_receipt_sha256 != native_replay.placement_receipt_sha256
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 indexed-SO3 failure disagrees with native replay",
                    ));
                }
                require_placement_failure(
                    row,
                    sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE,
                    component_failure,
                )?;
            }
            Err(error) => return Err(error),
        }
        return Ok(());
    }
    let feature_inventory = feature_inventory.expect("feature availability was checked");
    match generate_native_fixed64_single_anchor(
        allocation,
        slot_index,
        source,
        feature_inventory,
        geometric_input,
    ) {
        Ok(placement) => {
            let status_matches = row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
            let coordinates_match = placement_coordinates_close(
                backend,
                observed,
                placement.output_coordinates_angstrom(),
            );
            let quaternion_matches =
                placement_quaternion_close(backend, row, placement.quaternion());
            let coordinate_receipt_matches =
                row.output_coordinate_sha256 == canonical_coordinate_sha256(observed);
            let native_replay_matches = native_replay.status
                == sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED
                && native_replay.failure_code == sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONE
                && native_replay.output_coordinate_sha256 == row.output_coordinate_sha256
                && native_replay_coordinates_match(observed, native_replay)
                && native_replay_quaternion_matches(row, native_replay);
            let placement_receipt_matches =
                row.placement_receipt_sha256 == native_replay.placement_receipt_sha256;
            if !status_matches
                || !coordinates_match
                || !quaternion_matches
                || !coordinate_receipt_matches
                || !native_replay_matches
                || !placement_receipt_matches
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    format!(
                        "native fixed64 single-anchor placement disagrees with independent replay: status={status_matches}, coordinates={coordinates_match}, quaternion={quaternion_matches}, coordinate_receipt={coordinate_receipt_matches}, native_replay={native_replay_matches}, placement_receipt={placement_receipt_matches}"
                    ),
                ));
            }
        }
        Err(error) => {
            let component_failure =
                single_anchor_component_failure(error.code()).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!(
                            "independent single-anchor replay produced an impossible error: {error}"
                        ),
                    )
                })?;
            if native_replay.status != sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE
                || native_replay.failure_code != component_failure
                || !native_replay.coordinates.is_empty()
                || native_replay.output_coordinate_sha256 != [0; 32]
                || row.placement_receipt_sha256 != native_replay.placement_receipt_sha256
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 single-anchor failure disagrees with native replay",
                ));
            }
            require_placement_failure(
                row,
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE,
                component_failure,
            )?;
        }
    }
    Ok(())
}
