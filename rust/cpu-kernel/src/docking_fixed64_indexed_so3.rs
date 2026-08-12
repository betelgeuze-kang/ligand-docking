use core::mem::align_of;
use core::ptr;
use std::panic::{catch_unwind, AssertUnwindSafe};

use betelgeuze_docking_search::{orientations, Quaternion, Vec3, FIXED64_CANDIDATE_COUNT};

use super::{
    clear_error, reserved_is_zero, validate_header, write_error, ErrorV1, ProviderError,
    STATUS_INTERNAL_ERROR, STATUS_INVALID_ARGUMENT, STATUS_OK,
};

const MAX_LIGAND_ATOMS: usize = 512;
const MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 100_000.0;
const GEOMETRY_EPSILON: f64 = 1.0e-12;

#[repr(C)]
pub struct Fixed64IndexedSo3KernelInputV1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub ligand_atom_count: u64,
    pub source_x_angstrom: *const f64,
    pub source_y_angstrom: *const f64,
    pub source_z_angstrom: *const f64,
    pub pocket_center_angstrom: [f64; 3],
    pub source_seed_sha256: [u8; 32],
    pub sequence_index: u32,
    pub reserved0: u32,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct Fixed64IndexedSo3KernelResultV1 {
    pub status: i32,
    pub failure_code: i32,
    pub accepted_sequence_index: u32,
    pub reserved0: u32,
    pub raw_sequence_index: u64,
    pub quaternion_x: f64,
    pub quaternion_y: f64,
    pub quaternion_z: f64,
    pub quaternion_w: f64,
    pub translation_angstrom: [f64; 3],
    pub source_centroid_angstrom: [f64; 3],
    pub coordinates_written: u8,
    pub reserved1: [u8; 7],
    pub reserved: [u64; 4],
}

struct Generated {
    result: Fixed64IndexedSo3KernelResultV1,
    x: Vec<f64>,
    y: Vec<f64>,
    z: Vec<f64>,
}

fn checked_count(value: u64) -> Result<usize, ProviderError> {
    let count = usize::try_from(value)
        .map_err(|_| ProviderError::capacity("rust_cpu indexed SO3 count exceeds host size"))?;
    if !(1..=MAX_LIGAND_ATOMS).contains(&count) {
        return Err(ProviderError::capacity(
            "rust_cpu indexed SO3 ligand count is outside native bounds",
        ));
    }
    Ok(count)
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
    // SAFETY: The public C++ dispatcher validates range arithmetic, disjoint
    // channels, and count bounds before calling this private provider.
    Ok(unsafe { core::slice::from_raw_parts(pointer, count) })
}

unsafe fn generate(input: &Fixed64IndexedSo3KernelInputV1) -> Result<Generated, ProviderError> {
    validate_header::<Fixed64IndexedSo3KernelInputV1>(
        input.struct_size,
        input.abi_version,
        "rust_cpu indexed SO3 input size mismatch",
    )?;
    if input.reserved0 != 0 || !reserved_is_zero(&input.reserved) {
        return Err(ProviderError::invalid(
            "rust_cpu indexed SO3 input reserved fields must be zero",
        ));
    }
    let count = checked_count(input.ligand_atom_count)?;
    if usize::try_from(input.sequence_index).map_or(true, |index| index >= FIXED64_CANDIDATE_COUNT)
    {
        return Err(ProviderError::invalid(
            "rust_cpu indexed SO3 sequence index is outside fixed64",
        ));
    }
    // SAFETY: This function's private FFI contract is described above.
    let source_x = unsafe {
        checked_channel(
            input.source_x_angstrom,
            count,
            "rust_cpu indexed SO3 source x channel is null or misaligned",
        )?
    };
    // SAFETY: Same validated private FFI contract.
    let source_y = unsafe {
        checked_channel(
            input.source_y_angstrom,
            count,
            "rust_cpu indexed SO3 source y channel is null or misaligned",
        )?
    };
    // SAFETY: Same validated private FFI contract.
    let source_z = unsafe {
        checked_channel(
            input.source_z_angstrom,
            count,
            "rust_cpu indexed SO3 source z channel is null or misaligned",
        )?
    };
    if !input
        .pocket_center_angstrom
        .iter()
        .copied()
        .all(finite_coordinate)
        || source_x
            .iter()
            .chain(source_y)
            .chain(source_z)
            .copied()
            .any(|value| !finite_coordinate(value))
    {
        return Err(ProviderError::invalid(
            "rust_cpu indexed SO3 coordinates are non-finite or outside bounds",
        ));
    }

    let inverse = 1.0 / count as f64;
    let centroid = Vec3::new(
        source_x.iter().copied().sum::<f64>() * inverse,
        source_y.iter().copied().sum::<f64>() * inverse,
        source_z.iter().copied().sum::<f64>() * inverse,
    );
    let first = Vec3::new(source_x[0], source_y[0], source_z[0]);
    let distinct = (1..count).any(|index| {
        Vec3::new(source_x[index], source_y[index], source_z[index])
            .minus(first)
            .norm_squared()
            > GEOMETRY_EPSILON
    });
    if !distinct {
        return Ok(Generated {
            result: Fixed64IndexedSo3KernelResultV1 {
                status: 2,
                failure_code: 1,
                accepted_sequence_index: input.sequence_index,
                source_centroid_angstrom: [centroid.x, centroid.y, centroid.z],
                ..Fixed64IndexedSo3KernelResultV1::default()
            },
            x: Vec::new(),
            y: Vec::new(),
            z: Vec::new(),
        });
    }
    let sequence_count = usize::try_from(input.sequence_index)
        .map_err(|_| ProviderError::invalid("rust_cpu indexed SO3 sequence index is invalid"))?
        + 1;
    let sequence =
        orientations(input.source_seed_sha256, sequence_count).map_err(|_| ProviderError {
            status: STATUS_INTERNAL_ERROR,
            message: "rust_cpu indexed SO3 orientation generation failed",
        })?;
    let selected = sequence.last().ok_or(ProviderError {
        status: STATUS_INTERNAL_ERROR,
        message: "rust_cpu indexed SO3 orientation selection failed",
    })?;
    let quaternion = Quaternion::new(
        selected.quaternion.x,
        selected.quaternion.y,
        selected.quaternion.z,
        selected.quaternion.w,
    );
    let center = Vec3::new(
        input.pocket_center_angstrom[0],
        input.pocket_center_angstrom[1],
        input.pocket_center_angstrom[2],
    );
    let translation = center.minus(quaternion.rotate(centroid));
    let mut x = Vec::with_capacity(count);
    let mut y = Vec::with_capacity(count);
    let mut z = Vec::with_capacity(count);
    for index in 0..count {
        let placed = quaternion
            .rotate(Vec3::new(source_x[index], source_y[index], source_z[index]))
            .plus(translation);
        if !finite_coordinate(placed.x)
            || !finite_coordinate(placed.y)
            || !finite_coordinate(placed.z)
        {
            return Ok(Generated {
                result: Fixed64IndexedSo3KernelResultV1 {
                    status: 2,
                    failure_code: 2,
                    accepted_sequence_index: selected.orientation_index,
                    raw_sequence_index: selected.raw_sequence_index,
                    quaternion_x: quaternion.x,
                    quaternion_y: quaternion.y,
                    quaternion_z: quaternion.z,
                    quaternion_w: quaternion.w,
                    translation_angstrom: [translation.x, translation.y, translation.z],
                    source_centroid_angstrom: [centroid.x, centroid.y, centroid.z],
                    ..Fixed64IndexedSo3KernelResultV1::default()
                },
                x: Vec::new(),
                y: Vec::new(),
                z: Vec::new(),
            });
        }
        x.push(placed.x);
        y.push(placed.y);
        z.push(placed.z);
    }
    Ok(Generated {
        result: Fixed64IndexedSo3KernelResultV1 {
            status: 1,
            accepted_sequence_index: selected.orientation_index,
            raw_sequence_index: selected.raw_sequence_index,
            quaternion_x: quaternion.x,
            quaternion_y: quaternion.y,
            quaternion_z: quaternion.z,
            quaternion_w: quaternion.w,
            translation_angstrom: [translation.x, translation.y, translation.z],
            source_centroid_angstrom: [centroid.x, centroid.y, centroid.z],
            coordinates_written: 1,
            ..Fixed64IndexedSo3KernelResultV1::default()
        },
        x,
        y,
        z,
    })
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_fixed64_indexed_so3_v1_place(
    input: *const Fixed64IndexedSo3KernelInputV1,
    out_x: *mut f64,
    out_y: *mut f64,
    out_z: *mut f64,
    out_result: *mut Fixed64IndexedSo3KernelResultV1,
    out_error: *mut ErrorV1,
) -> i32 {
    if out_error.is_null() || (out_error as usize) % align_of::<ErrorV1>() != 0 {
        return STATUS_INVALID_ARGUMENT;
    }
    let error = unsafe { &mut *out_error };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu indexed SO3 error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return super::STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if input.is_null()
        || out_x.is_null()
        || out_y.is_null()
        || out_z.is_null()
        || out_result.is_null()
        || (input as usize) % align_of::<Fixed64IndexedSo3KernelInputV1>() != 0
        || (out_x as usize) % align_of::<f64>() != 0
        || (out_y as usize) % align_of::<f64>() != 0
        || (out_z as usize) % align_of::<f64>() != 0
        || (out_result as usize) % align_of::<Fixed64IndexedSo3KernelResultV1>() != 0
    {
        write_error(
            error,
            "rust_cpu indexed SO3 arguments must be non-null and aligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    let input = unsafe { &*input };
    let outcome = catch_unwind(AssertUnwindSafe(|| unsafe { generate(input) }));
    match outcome {
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
            write_error(error, "rust_cpu indexed SO3 provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kernel_layouts_are_stable() {
        assert_eq!(core::mem::size_of::<Fixed64IndexedSo3KernelInputV1>(), 168);
        assert_eq!(core::mem::size_of::<Fixed64IndexedSo3KernelResultV1>(), 144);
    }
}
