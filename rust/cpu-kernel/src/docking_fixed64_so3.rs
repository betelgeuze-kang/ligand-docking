use core::mem::{align_of, size_of};
use core::ptr;
use std::panic::{catch_unwind, AssertUnwindSafe};

use betelgeuze_docking_search::{orientations, FIXED64_CANDIDATE_COUNT};

use super::{
    clear_error, reserved_is_zero, validate_header, write_error, ErrorV1, ProviderError,
    STATUS_INTERNAL_ERROR, STATUS_INVALID_ARGUMENT, STATUS_OK,
};

const ROW_GENERATED: i32 = 1;
const FAILURE_NONE: i32 = 0;

#[repr(C)]
pub struct Fixed64So3InputV1 {
    struct_size: u32,
    abi_version: u32,
    source_seed_sha256: [u8; 32],
    reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct Fixed64So3RowV1 {
    orientation_index: u32,
    status: i32,
    failure_code: i32,
    reserved0: u32,
    raw_sequence_index: u64,
    quaternion_x: f64,
    quaternion_y: f64,
    quaternion_z: f64,
    quaternion_w: f64,
    norm_error: f64,
    row_receipt_sha256: [u8; 32],
    result_dependent_input_consumed: u8,
    duplicate_orientation_emitted: u8,
    denominator_preserved: u8,
    molecular_execution_authorized: u8,
    reservation_authorized: u8,
    benchmark_execution_authorized: u8,
    production_claim_authorized: u8,
    reserved1: u8,
    reserved: [u64; 4],
}

fn generate(
    input: &Fixed64So3InputV1,
) -> Result<[Fixed64So3RowV1; FIXED64_CANDIDATE_COUNT], ProviderError> {
    validate_header::<Fixed64So3InputV1>(
        input.struct_size,
        input.abi_version,
        "rust_cpu fixed64 SO3 input size mismatch",
    )?;
    if !reserved_is_zero(&input.reserved) || input.source_seed_sha256.iter().all(|byte| *byte == 0)
    {
        return Err(ProviderError::invalid(
            "rust_cpu fixed64 SO3 seed must be present and reserved fields zero",
        ));
    }
    let sequence =
        orientations(input.source_seed_sha256, FIXED64_CANDIDATE_COUNT).map_err(|_| {
            ProviderError {
                status: STATUS_INTERNAL_ERROR,
                message: "rust_cpu fixed64 SO3 sequence generation failed",
            }
        })?;
    let mut rows = [Fixed64So3RowV1::default(); FIXED64_CANDIDATE_COUNT];
    for (index, orientation) in sequence.into_iter().enumerate() {
        let q = orientation.quaternion;
        let norm = (q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w).sqrt();
        rows[index] = Fixed64So3RowV1 {
            orientation_index: orientation.orientation_index,
            status: ROW_GENERATED,
            failure_code: FAILURE_NONE,
            raw_sequence_index: orientation.raw_sequence_index,
            quaternion_x: q.x,
            quaternion_y: q.y,
            quaternion_z: q.z,
            quaternion_w: q.w,
            norm_error: (norm - 1.0).abs(),
            denominator_preserved: 1,
            ..Fixed64So3RowV1::default()
        };
    }
    Ok(rows)
}

#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_fixed64_so3_v1_generate(
    input: *const Fixed64So3InputV1,
    out_rows: *mut Fixed64So3RowV1,
    out_error: *mut ErrorV1,
) -> i32 {
    if out_error.is_null() || (out_error as usize) % align_of::<ErrorV1>() != 0 {
        return STATUS_INVALID_ARGUMENT;
    }
    let error = unsafe { &mut *out_error };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu fixed64 SO3 error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return super::STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if input.is_null()
        || out_rows.is_null()
        || (input as usize) % align_of::<Fixed64So3InputV1>() != 0
        || (out_rows as usize) % align_of::<Fixed64So3RowV1>() != 0
    {
        write_error(
            error,
            "rust_cpu fixed64 SO3 input and output must be non-null and aligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    let input = unsafe { &*input };
    let outcome = catch_unwind(AssertUnwindSafe(|| generate(input)));
    match outcome {
        Ok(Ok(rows)) => {
            unsafe {
                ptr::copy_nonoverlapping(rows.as_ptr(), out_rows, rows.len());
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu fixed64 SO3 provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

const _: () = {
    assert!(size_of::<Fixed64So3InputV1>() == 104);
    assert!(size_of::<Fixed64So3RowV1>() == 136);
};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn provider_layouts_are_frozen() {
        assert_eq!(size_of::<Fixed64So3InputV1>(), 104);
        assert_eq!(size_of::<Fixed64So3RowV1>(), 136);
    }
}
