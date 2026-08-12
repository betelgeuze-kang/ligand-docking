use core::mem::align_of;
use core::ptr;
use std::panic::{catch_unwind, AssertUnwindSafe};

use betelgeuze_docking_search::{
    native_fixed64_single_anchor_kernel, Fixed64AnchorKind, Fixed64Lane, Fixed64PlacementErrorCode,
    NativeFixed64SingleAnchorKernelOutcome, Vec3,
};

use super::{
    clear_error, reserved_is_zero, validate_header, write_error, ErrorV1, ProviderError,
    STATUS_ABI_MISMATCH, STATUS_INTERNAL_ERROR, STATUS_INVALID_ARGUMENT, STATUS_OK,
};

const MAX_LIGAND_ATOMS: usize = 512;
const MAX_FEATURE_ATOMS: usize = 65_536;
const MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 100_000.0;

#[repr(C)]
pub struct Fixed64SingleAnchorKernelInputV1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub lane: i32,
    pub anchor_kind: i32,
    pub lane_offset: u32,
    pub reserved0: u32,
    pub ligand_atom_count: u64,
    pub source_x_angstrom: *const f64,
    pub source_y_angstrom: *const f64,
    pub source_z_angstrom: *const f64,
    pub ligand_feature_atom_count: u64,
    pub ligand_feature_x_angstrom: *const f64,
    pub ligand_feature_y_angstrom: *const f64,
    pub ligand_feature_z_angstrom: *const f64,
    pub receptor_feature_atom_count: u64,
    pub receptor_feature_x_angstrom: *const f64,
    pub receptor_feature_y_angstrom: *const f64,
    pub receptor_feature_z_angstrom: *const f64,
    pub pocket_center_angstrom: [f64; 3],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct Fixed64SingleAnchorKernelResultV1 {
    pub status: i32,
    pub failure_code: i32,
    pub ligand_anchor_point_angstrom: [f64; 3],
    pub receptor_anchor_point_angstrom: [f64; 3],
    pub target_anchor_point_angstrom: [f64; 3],
    pub local_surface_normal: [f64; 3],
    pub approach_vector: [f64; 3],
    pub ligand_direction: [f64; 3],
    pub alignment_target_direction: [f64; 3],
    pub target_distance_angstrom: f64,
    pub twist_angle_radians: f64,
    pub quaternion_x: f64,
    pub quaternion_y: f64,
    pub quaternion_z: f64,
    pub quaternion_w: f64,
    pub translation_angstrom: [f64; 3],
    pub coordinates_written: u8,
    pub reserved0: [u8; 7],
    pub reserved: [u64; 4],
}

struct Generated {
    result: Fixed64SingleAnchorKernelResultV1,
    x: Vec<f64>,
    y: Vec<f64>,
    z: Vec<f64>,
}

fn finite_coordinate(value: f64) -> bool {
    value.is_finite() && value.abs() <= MAX_ABSOLUTE_COORDINATE_ANGSTROM
}

unsafe fn checked_channel<'a>(
    pointer: *const f64,
    count: usize,
    message: &'static str,
) -> Result<&'a [f64], ProviderError> {
    if pointer.is_null() || (pointer as usize) % align_of::<f64>() != 0 {
        return Err(ProviderError::invalid(message));
    }
    Ok(unsafe { core::slice::from_raw_parts(pointer, count) })
}

fn checked_count(
    value: u64,
    maximum: usize,
    message: &'static str,
) -> Result<usize, ProviderError> {
    let count = usize::try_from(value).map_err(|_| ProviderError::capacity(message))?;
    if count == 0 || count > maximum {
        return Err(ProviderError::capacity(message));
    }
    Ok(count)
}

fn lane(value: i32) -> Result<Fixed64Lane, ProviderError> {
    match value {
        4 => Ok(Fixed64Lane::LigandDonorToReceptorAcceptor),
        5 => Ok(Fixed64Lane::LigandAcceptorToReceptorDonor),
        6 => Ok(Fixed64Lane::ComplementaryCharge),
        7 => Ok(Fixed64Lane::AromaticPlane),
        8 => Ok(Fixed64Lane::PrincipalAxisShape),
        _ => Err(ProviderError::invalid(
            "rust_cpu single-anchor lane is outside the frozen anchor set",
        )),
    }
}

fn anchor_kind(value: i32) -> Result<Fixed64AnchorKind, ProviderError> {
    match value {
        1 => Ok(Fixed64AnchorKind::LigandDonorToReceptorAcceptor),
        2 => Ok(Fixed64AnchorKind::LigandAcceptorToReceptorDonor),
        3 => Ok(Fixed64AnchorKind::ComplementaryCharge),
        4 => Ok(Fixed64AnchorKind::AromaticPlane),
        5 => Ok(Fixed64AnchorKind::PrincipalAxisShape),
        _ => Err(ProviderError::invalid(
            "rust_cpu single-anchor kind is outside the frozen anchor set",
        )),
    }
}

fn expected_pair(lane: Fixed64Lane, anchor: Fixed64AnchorKind) -> bool {
    matches!(
        (lane, anchor),
        (
            Fixed64Lane::LigandDonorToReceptorAcceptor,
            Fixed64AnchorKind::LigandDonorToReceptorAcceptor
        ) | (
            Fixed64Lane::LigandAcceptorToReceptorDonor,
            Fixed64AnchorKind::LigandAcceptorToReceptorDonor
        ) | (
            Fixed64Lane::ComplementaryCharge,
            Fixed64AnchorKind::ComplementaryCharge
        ) | (Fixed64Lane::AromaticPlane, Fixed64AnchorKind::AromaticPlane)
            | (
                Fixed64Lane::PrincipalAxisShape,
                Fixed64AnchorKind::PrincipalAxisShape
            )
    )
}

fn valid_feature_cardinality(
    lane: Fixed64Lane,
    ligand_count: usize,
    receptor_count: usize,
) -> bool {
    match lane {
        Fixed64Lane::LigandDonorToReceptorAcceptor => ligand_count == 2 && receptor_count == 1,
        Fixed64Lane::LigandAcceptorToReceptorDonor => ligand_count == 1 && receptor_count == 2,
        Fixed64Lane::ComplementaryCharge | Fixed64Lane::PrincipalAxisShape => {
            ligand_count >= 1 && receptor_count >= 1
        }
        Fixed64Lane::AromaticPlane => ligand_count >= 3 && receptor_count >= 3,
        _ => false,
    }
}

fn vec3_channels(x: &[f64], y: &[f64], z: &[f64]) -> Vec<Vec3> {
    (0..x.len())
        .map(|index| Vec3::new(x[index], y[index], z[index]))
        .collect()
}

fn typed_failure_code(code: Fixed64PlacementErrorCode) -> i32 {
    match code {
        Fixed64PlacementErrorCode::DegenerateLigandDirection => 1,
        Fixed64PlacementErrorCode::DegenerateReceptorDirection => 2,
        Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal => 3,
        Fixed64PlacementErrorCode::DegenerateAromaticPlane => 4,
        Fixed64PlacementErrorCode::DegeneratePrincipalAxis => 5,
        _ => 6,
    }
}

unsafe fn generate(input: &Fixed64SingleAnchorKernelInputV1) -> Result<Generated, ProviderError> {
    validate_header::<Fixed64SingleAnchorKernelInputV1>(
        input.struct_size,
        input.abi_version,
        "rust_cpu single-anchor input size mismatch",
    )?;
    if input.reserved0 != 0 || !reserved_is_zero(&input.reserved) {
        return Err(ProviderError::invalid(
            "rust_cpu single-anchor input reserved fields must be zero",
        ));
    }
    let ligand_count = checked_count(
        input.ligand_atom_count,
        MAX_LIGAND_ATOMS,
        "rust_cpu single-anchor ligand count is outside native bounds",
    )?;
    let ligand_feature_count = checked_count(
        input.ligand_feature_atom_count,
        MAX_FEATURE_ATOMS,
        "rust_cpu single-anchor ligand feature count is outside bounds",
    )?;
    let receptor_feature_count = checked_count(
        input.receptor_feature_atom_count,
        MAX_FEATURE_ATOMS,
        "rust_cpu single-anchor receptor feature count is outside bounds",
    )?;
    let lane = lane(input.lane)?;
    let anchor = anchor_kind(input.anchor_kind)?;
    if !expected_pair(lane, anchor) {
        return Err(ProviderError::invalid(
            "rust_cpu single-anchor lane and kind are cross-wired",
        ));
    }
    if !valid_feature_cardinality(lane, ligand_feature_count, receptor_feature_count) {
        return Err(ProviderError::invalid(
            "rust_cpu single-anchor feature cardinality is invalid for its lane",
        ));
    }
    let lane_width = if matches!(
        lane,
        Fixed64Lane::LigandDonorToReceptorAcceptor
            | Fixed64Lane::LigandAcceptorToReceptorDonor
            | Fixed64Lane::ComplementaryCharge
    ) {
        4
    } else {
        2
    };
    let lane_offset = usize::try_from(input.lane_offset)
        .map_err(|_| ProviderError::invalid("rust_cpu single-anchor offset is invalid"))?;
    if lane_offset >= lane_width {
        return Err(ProviderError::invalid(
            "rust_cpu single-anchor offset exceeds its frozen lane width",
        ));
    }
    let source_x = unsafe {
        checked_channel(
            input.source_x_angstrom,
            ligand_count,
            "rust_cpu single-anchor source x is null or misaligned",
        )?
    };
    let source_y = unsafe {
        checked_channel(
            input.source_y_angstrom,
            ligand_count,
            "rust_cpu single-anchor source y is null or misaligned",
        )?
    };
    let source_z = unsafe {
        checked_channel(
            input.source_z_angstrom,
            ligand_count,
            "rust_cpu single-anchor source z is null or misaligned",
        )?
    };
    let ligand_feature_x = unsafe {
        checked_channel(
            input.ligand_feature_x_angstrom,
            ligand_feature_count,
            "rust_cpu single-anchor ligand feature x is null or misaligned",
        )?
    };
    let ligand_feature_y = unsafe {
        checked_channel(
            input.ligand_feature_y_angstrom,
            ligand_feature_count,
            "rust_cpu single-anchor ligand feature y is null or misaligned",
        )?
    };
    let ligand_feature_z = unsafe {
        checked_channel(
            input.ligand_feature_z_angstrom,
            ligand_feature_count,
            "rust_cpu single-anchor ligand feature z is null or misaligned",
        )?
    };
    let receptor_feature_x = unsafe {
        checked_channel(
            input.receptor_feature_x_angstrom,
            receptor_feature_count,
            "rust_cpu single-anchor receptor feature x is null or misaligned",
        )?
    };
    let receptor_feature_y = unsafe {
        checked_channel(
            input.receptor_feature_y_angstrom,
            receptor_feature_count,
            "rust_cpu single-anchor receptor feature y is null or misaligned",
        )?
    };
    let receptor_feature_z = unsafe {
        checked_channel(
            input.receptor_feature_z_angstrom,
            receptor_feature_count,
            "rust_cpu single-anchor receptor feature z is null or misaligned",
        )?
    };
    if source_x
        .iter()
        .chain(source_y)
        .chain(source_z)
        .chain(ligand_feature_x)
        .chain(ligand_feature_y)
        .chain(ligand_feature_z)
        .chain(receptor_feature_x)
        .chain(receptor_feature_y)
        .chain(receptor_feature_z)
        .chain(input.pocket_center_angstrom.iter())
        .copied()
        .any(|value| !finite_coordinate(value))
    {
        return Err(ProviderError::invalid(
            "rust_cpu single-anchor coordinates are outside native bounds",
        ));
    }
    let source = vec3_channels(source_x, source_y, source_z);
    let ligand_feature = vec3_channels(ligand_feature_x, ligand_feature_y, ligand_feature_z);
    let receptor_feature =
        vec3_channels(receptor_feature_x, receptor_feature_y, receptor_feature_z);
    let pocket_center = Vec3::new(
        input.pocket_center_angstrom[0],
        input.pocket_center_angstrom[1],
        input.pocket_center_angstrom[2],
    );
    match native_fixed64_single_anchor_kernel(
        lane,
        anchor,
        lane_offset,
        &source,
        &ligand_feature,
        &receptor_feature,
        pocket_center,
    ) {
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(code) => Ok(Generated {
            result: Fixed64SingleAnchorKernelResultV1 {
                status: 2,
                failure_code: typed_failure_code(code),
                ..Fixed64SingleAnchorKernelResultV1::default()
            },
            x: Vec::new(),
            y: Vec::new(),
            z: Vec::new(),
        }),
        NativeFixed64SingleAnchorKernelOutcome::Placed(placement) => {
            let mut x = Vec::with_capacity(ligand_count);
            let mut y = Vec::with_capacity(ligand_count);
            let mut z = Vec::with_capacity(ligand_count);
            for coordinate in &placement.output_coordinates_angstrom {
                x.push(coordinate.x);
                y.push(coordinate.y);
                z.push(coordinate.z);
            }
            Ok(Generated {
                result: Fixed64SingleAnchorKernelResultV1 {
                    status: 1,
                    ligand_anchor_point_angstrom: [
                        placement.ligand_anchor_point_angstrom.x,
                        placement.ligand_anchor_point_angstrom.y,
                        placement.ligand_anchor_point_angstrom.z,
                    ],
                    receptor_anchor_point_angstrom: [
                        placement.receptor_anchor_point_angstrom.x,
                        placement.receptor_anchor_point_angstrom.y,
                        placement.receptor_anchor_point_angstrom.z,
                    ],
                    target_anchor_point_angstrom: [
                        placement.target_anchor_point_angstrom.x,
                        placement.target_anchor_point_angstrom.y,
                        placement.target_anchor_point_angstrom.z,
                    ],
                    local_surface_normal: [
                        placement.local_surface_normal.x,
                        placement.local_surface_normal.y,
                        placement.local_surface_normal.z,
                    ],
                    approach_vector: [
                        placement.approach_vector.x,
                        placement.approach_vector.y,
                        placement.approach_vector.z,
                    ],
                    ligand_direction: [
                        placement.ligand_direction.x,
                        placement.ligand_direction.y,
                        placement.ligand_direction.z,
                    ],
                    alignment_target_direction: [
                        placement.alignment_target_direction.x,
                        placement.alignment_target_direction.y,
                        placement.alignment_target_direction.z,
                    ],
                    target_distance_angstrom: placement.target_distance_angstrom,
                    twist_angle_radians: placement.twist_angle_radians,
                    quaternion_x: placement.quaternion.x,
                    quaternion_y: placement.quaternion.y,
                    quaternion_z: placement.quaternion.z,
                    quaternion_w: placement.quaternion.w,
                    translation_angstrom: [
                        placement.translation_angstrom.x,
                        placement.translation_angstrom.y,
                        placement.translation_angstrom.z,
                    ],
                    coordinates_written: 1,
                    ..Fixed64SingleAnchorKernelResultV1::default()
                },
                x,
                y,
                z,
            })
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_fixed64_single_anchor_v1_place(
    input: *const Fixed64SingleAnchorKernelInputV1,
    out_x: *mut f64,
    out_y: *mut f64,
    out_z: *mut f64,
    out_result: *mut Fixed64SingleAnchorKernelResultV1,
    out_error: *mut ErrorV1,
) -> i32 {
    if out_error.is_null() || (out_error as usize) % align_of::<ErrorV1>() != 0 {
        return STATUS_INVALID_ARGUMENT;
    }
    let error = unsafe { &mut *out_error };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu single-anchor error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if input.is_null()
        || out_x.is_null()
        || out_y.is_null()
        || out_z.is_null()
        || out_result.is_null()
        || (input as usize) % align_of::<Fixed64SingleAnchorKernelInputV1>() != 0
        || (out_x as usize) % align_of::<f64>() != 0
        || (out_y as usize) % align_of::<f64>() != 0
        || (out_z as usize) % align_of::<f64>() != 0
        || (out_result as usize) % align_of::<Fixed64SingleAnchorKernelResultV1>() != 0
    {
        write_error(
            error,
            "rust_cpu single-anchor arguments must be non-null and aligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    let input = unsafe { &*input };
    match catch_unwind(AssertUnwindSafe(|| unsafe { generate(input) })) {
        Ok(Ok(generated)) => {
            if generated.result.coordinates_written != 0 {
                unsafe {
                    ptr::copy_nonoverlapping(generated.x.as_ptr(), out_x, generated.x.len());
                    ptr::copy_nonoverlapping(generated.y.as_ptr(), out_y, generated.y.len());
                    ptr::copy_nonoverlapping(generated.z.as_ptr(), out_z, generated.z.len());
                }
            }
            unsafe { ptr::write(out_result, generated.result) };
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu single-anchor provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kernel_layouts_are_stable() {
        assert_eq!(
            core::mem::size_of::<Fixed64SingleAnchorKernelInputV1>(),
            208
        );
        assert_eq!(
            core::mem::size_of::<Fixed64SingleAnchorKernelResultV1>(),
            288
        );
    }
}
