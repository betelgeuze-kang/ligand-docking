use core::mem::{align_of, size_of};
use core::ptr;
use std::panic::{catch_unwind, AssertUnwindSafe};

use betelgeuze_docking_search::{
    Fixed64Allocation, Fixed64AnchorKind, Fixed64AtomicFeatureEvidence,
    Fixed64ConformerSourceEvidence, Fixed64ExactV11SourceEvidence, Fixed64FeatureInventory,
    Fixed64FeatureKind, Fixed64GenerationParentRole, Fixed64IndexedSourceEvidence, Fixed64Lane,
    Fixed64MissingFeature, Fixed64Requirement, Fixed64Slot, Fixed64SourceEvidence,
    FIXED64_CANDIDATE_COUNT,
};

use super::{
    checked_slice, clear_error, reserved_is_zero, validate_header, write_error, ErrorV1,
    ProviderError, STATUS_ABI_MISMATCH, STATUS_INTERNAL_ERROR, STATUS_INVALID_ARGUMENT, STATUS_OK,
};

const FEATURE_KIND_COUNT: usize = 12;
const MAX_FEATURES_PER_KIND: usize = 256;
const MAX_ATOMIC_FEATURES: usize = FEATURE_KIND_COUNT * MAX_FEATURES_PER_KIND;
const MAX_REQUIREMENTS: usize = 2;
const MAX_MISSING_FEATURES: usize = 2;
const MAX_SELECTED_RECEIPTS: usize = 2;

const ROW_READY: i32 = 1;
const ROW_TYPED_FAILURE: i32 = 2;
const PARENT_NONE: i32 = 0;
const PARENT_EXACT_PASSTHROUGH: i32 = 1;
const PARENT_GENERATOR_INPUT: i32 = 2;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Fixed64SourceEvidenceV1 {
    receipt_sha256: [u8; 32],
    proposal_sha256: [u8; 32],
    coordinate_sha256: [u8; 32],
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Fixed64ExactSourceEvidenceV1 {
    source_receipt_sha256: [u8; 32],
    proposal_sha256: [u8; 32],
    ligand_coordinate_sha256: [u8; 32],
    receptor_coordinate_sha256: [u8; 32],
    prepared_ligand_topology_sha256: [u8; 32],
    prepared_receptor_topology_sha256: [u8; 32],
    ligand_vdw_radii_sha256: [u8; 32],
    ligand_heavy_atom_mask_sha256: [u8; 32],
    receptor_vdw_radii_sha256: [u8; 32],
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Fixed64AtomicFeatureEvidenceV1 {
    kind: i32,
    reserved0: u32,
    receipt_sha256: [u8; 32],
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Fixed64IndexedSourceEvidenceV1 {
    source_index: u32,
    reserved0: u32,
    source: Fixed64SourceEvidenceV1,
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Fixed64ConformerSourceEvidenceV1 {
    rank: u8,
    reserved0: [u8; 7],
    source: Fixed64SourceEvidenceV1,
    reserved: [u64; 2],
}

#[repr(C)]
pub struct Fixed64AllocationInputV1 {
    struct_size: u32,
    abi_version: u32,
    exact_v11_source: Fixed64ExactSourceEvidenceV1,
    atomic_feature_count: u64,
    atomic_features: *const Fixed64AtomicFeatureEvidenceV1,
    v7_control_source_count: u64,
    v7_control_sources: *const Fixed64IndexedSourceEvidenceV1,
    conformer_source_count: u64,
    conformer_sources: *const Fixed64ConformerSourceEvidenceV1,
    retained_source_count: u64,
    retained_sources: *const Fixed64IndexedSourceEvidenceV1,
    reserved: [u64; 8],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct Fixed64RequirementV1 {
    kind: i32,
    value: u32,
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct Fixed64MissingFeatureV1 {
    kind: i32,
    value: u32,
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct Fixed64AllocationRowV1 {
    slot_index: u32,
    lane: i32,
    lane_offset: u32,
    status: i32,
    declared_anchor_kind: i32,
    generation_parent_role: i32,
    requirement_count: u32,
    missing_feature_count: u32,
    v7_control_source_index: i32,
    so3_sequence_index: i32,
    true_conformer_rank: i32,
    retained_source_index: i32,
    requirements: [Fixed64RequirementV1; MAX_REQUIREMENTS],
    missing_features: [Fixed64MissingFeatureV1; MAX_MISSING_FEATURES],
    selected_source_receipt_count: u32,
    reserved0: u32,
    selected_source_receipt_sha256: [[u8; 32]; MAX_SELECTED_RECEIPTS],
    generation_parent_receipt_sha256: [u8; 32],
    generation_parent_proposal_sha256: [u8; 32],
    generation_parent_coordinate_sha256: [u8; 32],
    slot_receipt_sha256: [u8; 32],
    generation_eligible: u8,
    fallback_allowed: u8,
    multi_anchor_allowed: u8,
    result_dependent_allocation: u8,
    denominator_preserved: u8,
    molecular_execution_authorized: u8,
    reservation_authorized: u8,
    benchmark_execution_authorized: u8,
    reserved: [u64; 4],
}

struct ProviderAllocation {
    rows: [Fixed64AllocationRowV1; FIXED64_CANDIDATE_COUNT],
    inventory_sha256: [u8; 32],
    allocation_sha256: [u8; 32],
    ready_count: u64,
    typed_failure_count: u64,
}

fn internal(message: &'static str) -> ProviderError {
    ProviderError {
        status: STATUS_INTERNAL_ERROR,
        message,
    }
}

fn checked_count(value: u64, maximum: usize) -> Result<usize, ProviderError> {
    let count = usize::try_from(value).map_err(|_| {
        ProviderError::capacity("rust_cpu fixed64 allocation count exceeds host address space")
    })?;
    if count > maximum {
        return Err(ProviderError::capacity(
            "rust_cpu fixed64 allocation inventory exceeds frozen capacity",
        ));
    }
    Ok(count)
}

fn feature_kind(value: i32) -> Result<Fixed64FeatureKind, ProviderError> {
    match value {
        0 => Ok(Fixed64FeatureKind::LigandDonor),
        1 => Ok(Fixed64FeatureKind::LigandAcceptor),
        2 => Ok(Fixed64FeatureKind::ReceptorDonor),
        3 => Ok(Fixed64FeatureKind::ReceptorAcceptor),
        4 => Ok(Fixed64FeatureKind::LigandPositiveSite),
        5 => Ok(Fixed64FeatureKind::LigandNegativeSite),
        6 => Ok(Fixed64FeatureKind::ReceptorPositiveSite),
        7 => Ok(Fixed64FeatureKind::ReceptorNegativeSite),
        8 => Ok(Fixed64FeatureKind::LigandAromaticPlane),
        9 => Ok(Fixed64FeatureKind::ReceptorAromaticPlane),
        10 => Ok(Fixed64FeatureKind::LigandShapeAxis),
        11 => Ok(Fixed64FeatureKind::PocketShapeAxis),
        _ => Err(ProviderError::invalid(
            "rust_cpu fixed64 allocation feature kind is invalid",
        )),
    }
}

fn source_evidence(value: Fixed64SourceEvidenceV1) -> Result<Fixed64SourceEvidence, ProviderError> {
    if !reserved_is_zero(&value.reserved) {
        return Err(ProviderError::invalid(
            "rust_cpu fixed64 allocation source reserved fields must be zero",
        ));
    }
    Ok(Fixed64SourceEvidence {
        receipt_sha256: value.receipt_sha256,
        proposal_sha256: value.proposal_sha256,
        coordinate_sha256: value.coordinate_sha256,
    })
}

unsafe fn build_inventory(
    input: &Fixed64AllocationInputV1,
) -> Result<Fixed64FeatureInventory, ProviderError> {
    validate_header::<Fixed64AllocationInputV1>(
        input.struct_size,
        input.abi_version,
        "rust_cpu fixed64 allocation input size mismatch",
    )?;
    if !reserved_is_zero(&input.reserved) || !reserved_is_zero(&input.exact_v11_source.reserved) {
        return Err(ProviderError::invalid(
            "rust_cpu fixed64 allocation reserved fields must be zero",
        ));
    }
    let atomic_count = checked_count(input.atomic_feature_count, MAX_ATOMIC_FEATURES)?;
    let v7_count = checked_count(input.v7_control_source_count, 24)?;
    let conformer_count = checked_count(input.conformer_source_count, 7)?;
    let retained_count = checked_count(input.retained_source_count, 4)?;

    // SAFETY: Counts are bounded above and checked_slice validates every raw
    // channel before any domain object is built.
    let atomic_rows = unsafe {
        checked_slice(
            input.atomic_features,
            atomic_count,
            "rust_cpu fixed64 allocation atomic-feature channel is null",
        )?
    };
    // SAFETY: Same bounded raw-channel contract as above.
    let v7_rows = unsafe {
        checked_slice(
            input.v7_control_sources,
            v7_count,
            "rust_cpu fixed64 allocation V7 source channel is null",
        )?
    };
    // SAFETY: Same bounded raw-channel contract as above.
    let conformer_rows = unsafe {
        checked_slice(
            input.conformer_sources,
            conformer_count,
            "rust_cpu fixed64 allocation conformer channel is null",
        )?
    };
    // SAFETY: Same bounded raw-channel contract as above.
    let retained_rows = unsafe {
        checked_slice(
            input.retained_sources,
            retained_count,
            "rust_cpu fixed64 allocation retained-source channel is null",
        )?
    };

    let mut atomic_features = Vec::with_capacity(atomic_count);
    for row in atomic_rows {
        if row.reserved0 != 0 || !reserved_is_zero(&row.reserved) {
            return Err(ProviderError::invalid(
                "rust_cpu fixed64 allocation atomic-feature reserved fields must be zero",
            ));
        }
        atomic_features.push(Fixed64AtomicFeatureEvidence {
            kind: feature_kind(row.kind)?,
            receipt_sha256: row.receipt_sha256,
        });
    }

    let mut v7_sources = Vec::with_capacity(v7_count);
    for row in v7_rows {
        if row.reserved0 != 0 || !reserved_is_zero(&row.reserved) {
            return Err(ProviderError::invalid(
                "rust_cpu fixed64 allocation V7 source reserved fields must be zero",
            ));
        }
        v7_sources.push(Fixed64IndexedSourceEvidence {
            source_index: row.source_index,
            source: source_evidence(row.source)?,
        });
    }

    let mut conformer_sources = Vec::with_capacity(conformer_count);
    for row in conformer_rows {
        if row.reserved0 != [0; 7] || !reserved_is_zero(&row.reserved) {
            return Err(ProviderError::invalid(
                "rust_cpu fixed64 allocation conformer reserved fields must be zero",
            ));
        }
        conformer_sources.push(Fixed64ConformerSourceEvidence {
            rank: row.rank,
            source: source_evidence(row.source)?,
        });
    }

    let mut retained_sources = Vec::with_capacity(retained_count);
    for row in retained_rows {
        if row.reserved0 != 0 || !reserved_is_zero(&row.reserved) {
            return Err(ProviderError::invalid(
                "rust_cpu fixed64 allocation retained source reserved fields must be zero",
            ));
        }
        retained_sources.push(Fixed64IndexedSourceEvidence {
            source_index: row.source_index,
            source: source_evidence(row.source)?,
        });
    }

    let exact = input.exact_v11_source;
    Fixed64FeatureInventory::new(
        Fixed64ExactV11SourceEvidence {
            source_receipt_sha256: exact.source_receipt_sha256,
            proposal_sha256: exact.proposal_sha256,
            ligand_coordinate_sha256: exact.ligand_coordinate_sha256,
            receptor_coordinate_sha256: exact.receptor_coordinate_sha256,
            prepared_ligand_topology_sha256: exact.prepared_ligand_topology_sha256,
            prepared_receptor_topology_sha256: exact.prepared_receptor_topology_sha256,
            ligand_vdw_radii_sha256: exact.ligand_vdw_radii_sha256,
            ligand_heavy_atom_mask_sha256: exact.ligand_heavy_atom_mask_sha256,
            receptor_vdw_radii_sha256: exact.receptor_vdw_radii_sha256,
        },
        atomic_features,
        v7_sources,
        conformer_sources,
        retained_sources,
    )
    .map_err(|_| ProviderError::invalid("rust_cpu fixed64 allocation inventory is invalid"))
}

fn lane_tag(value: Fixed64Lane) -> i32 {
    match value {
        Fixed64Lane::PocketCenteredControls => 0,
        Fixed64Lane::UniformSourceControls => 1,
        Fixed64Lane::DeterministicIndependentSo3 => 2,
        Fixed64Lane::TrueConformerIndependentSo3 => 3,
        Fixed64Lane::LigandDonorToReceptorAcceptor => 4,
        Fixed64Lane::LigandAcceptorToReceptorDonor => 5,
        Fixed64Lane::ComplementaryCharge => 6,
        Fixed64Lane::AromaticPlane => 7,
        Fixed64Lane::PrincipalAxisShape => 8,
        Fixed64Lane::PairedRetainedControls => 9,
    }
}

fn anchor_tag(value: Option<Fixed64AnchorKind>) -> i32 {
    match value {
        None => 0,
        Some(Fixed64AnchorKind::LigandDonorToReceptorAcceptor) => 1,
        Some(Fixed64AnchorKind::LigandAcceptorToReceptorDonor) => 2,
        Some(Fixed64AnchorKind::ComplementaryCharge) => 3,
        Some(Fixed64AnchorKind::AromaticPlane) => 4,
        Some(Fixed64AnchorKind::PrincipalAxisShape) => 5,
    }
}

fn feature_tag(value: Fixed64FeatureKind) -> u32 {
    match value {
        Fixed64FeatureKind::LigandDonor => 0,
        Fixed64FeatureKind::LigandAcceptor => 1,
        Fixed64FeatureKind::ReceptorDonor => 2,
        Fixed64FeatureKind::ReceptorAcceptor => 3,
        Fixed64FeatureKind::LigandPositiveSite => 4,
        Fixed64FeatureKind::LigandNegativeSite => 5,
        Fixed64FeatureKind::ReceptorPositiveSite => 6,
        Fixed64FeatureKind::ReceptorNegativeSite => 7,
        Fixed64FeatureKind::LigandAromaticPlane => 8,
        Fixed64FeatureKind::ReceptorAromaticPlane => 9,
        Fixed64FeatureKind::LigandShapeAxis => 10,
        Fixed64FeatureKind::PocketShapeAxis => 11,
    }
}

fn requirement(value: Fixed64Requirement) -> Fixed64RequirementV1 {
    let (kind, value) = match value {
        Fixed64Requirement::V7ControlSource(index) => (0, u32::from(index)),
        Fixed64Requirement::TrueConformerRank(rank) => (1, u32::from(rank)),
        Fixed64Requirement::Feature(feature) => (2, feature_tag(feature)),
        Fixed64Requirement::ComplementaryChargeAnchor => (3, 0),
        Fixed64Requirement::RetainedSource(index) => (4, index),
    };
    Fixed64RequirementV1 {
        kind,
        value,
        reserved: [0; 2],
    }
}

fn missing_feature(value: Fixed64MissingFeature) -> Fixed64MissingFeatureV1 {
    let (kind, value) = match value {
        Fixed64MissingFeature::V7ControlSource(index) => (0, u32::from(index)),
        Fixed64MissingFeature::TrueConformer(rank) => (1, u32::from(rank)),
        Fixed64MissingFeature::LigandDonor => (2, 0),
        Fixed64MissingFeature::ReceptorAcceptor => (3, 0),
        Fixed64MissingFeature::LigandAcceptor => (4, 0),
        Fixed64MissingFeature::ReceptorDonor => (5, 0),
        Fixed64MissingFeature::ComplementaryChargeAnchor => (6, 0),
        Fixed64MissingFeature::LigandAromaticPlane => (7, 0),
        Fixed64MissingFeature::ReceptorAromaticPlane => (8, 0),
        Fixed64MissingFeature::LigandShapeAxis => (9, 0),
        Fixed64MissingFeature::PocketShapeAxis => (10, 0),
        Fixed64MissingFeature::RetainedSource(index) => (11, index),
    };
    Fixed64MissingFeatureV1 {
        kind,
        value,
        reserved: [0; 2],
    }
}

fn row_from_slot(slot: &Fixed64Slot) -> Result<Fixed64AllocationRowV1, ProviderError> {
    if slot.required_features().len() > MAX_REQUIREMENTS
        || slot.missing_features().len() > MAX_MISSING_FEATURES
        || slot.selected_source_receipt_sha256s().len() > MAX_SELECTED_RECEIPTS
    {
        return Err(internal(
            "rust_cpu fixed64 allocation row exceeded the frozen ABI capacity",
        ));
    }
    let mut row = Fixed64AllocationRowV1 {
        slot_index: u32::try_from(slot.slot_index())
            .map_err(|_| internal("rust_cpu fixed64 allocation slot index exceeded u32"))?,
        lane: lane_tag(slot.lane()),
        lane_offset: u32::try_from(slot.lane_offset())
            .map_err(|_| internal("rust_cpu fixed64 allocation lane offset exceeded u32"))?,
        status: if slot.generation_eligible() {
            ROW_READY
        } else {
            ROW_TYPED_FAILURE
        },
        declared_anchor_kind: anchor_tag(slot.declared_anchor_kind()),
        generation_parent_role: PARENT_NONE,
        requirement_count: u32::try_from(slot.required_features().len())
            .map_err(|_| internal("rust_cpu fixed64 allocation requirement count exceeded u32"))?,
        missing_feature_count: u32::try_from(slot.missing_features().len())
            .map_err(|_| internal("rust_cpu fixed64 allocation missing count exceeded u32"))?,
        v7_control_source_index: slot
            .v7_control_source_index()
            .map_or(-1, |value| i32::try_from(value).unwrap_or(-1)),
        so3_sequence_index: slot.so3_sequence_index().map_or(-1, i32::from),
        true_conformer_rank: slot.true_conformer_rank().map_or(-1, i32::from),
        retained_source_index: slot
            .retained_source_index()
            .map_or(-1, |value| i32::try_from(value).unwrap_or(-1)),
        requirements: [Fixed64RequirementV1::default(); MAX_REQUIREMENTS],
        missing_features: [Fixed64MissingFeatureV1::default(); MAX_MISSING_FEATURES],
        selected_source_receipt_count: u32::try_from(slot.selected_source_receipt_sha256s().len())
            .map_err(|_| {
                internal("rust_cpu fixed64 allocation selected receipt count exceeded u32")
            })?,
        reserved0: 0,
        selected_source_receipt_sha256: [[0; 32]; MAX_SELECTED_RECEIPTS],
        generation_parent_receipt_sha256: [0; 32],
        generation_parent_proposal_sha256: [0; 32],
        generation_parent_coordinate_sha256: [0; 32],
        slot_receipt_sha256: slot.receipt_sha256(),
        generation_eligible: u8::from(slot.generation_eligible()),
        fallback_allowed: u8::from(slot.fallback_allowed()),
        multi_anchor_allowed: u8::from(slot.multi_anchor_allowed()),
        result_dependent_allocation: 0,
        denominator_preserved: 1,
        molecular_execution_authorized: 0,
        reservation_authorized: 0,
        benchmark_execution_authorized: 0,
        reserved: [0; 4],
    };
    for (index, value) in slot.required_features().iter().copied().enumerate() {
        row.requirements[index] = requirement(value);
    }
    for (index, value) in slot.missing_features().iter().copied().enumerate() {
        row.missing_features[index] = missing_feature(value);
    }
    for (index, value) in slot
        .selected_source_receipt_sha256s()
        .iter()
        .copied()
        .enumerate()
    {
        row.selected_source_receipt_sha256[index] = value;
    }
    if let Some(parent) = slot.generation_parent() {
        row.generation_parent_role = match parent.role {
            Fixed64GenerationParentRole::ExactPassthroughParent => PARENT_EXACT_PASSTHROUGH,
            Fixed64GenerationParentRole::GeneratorInputParent => PARENT_GENERATOR_INPUT,
        };
        row.generation_parent_receipt_sha256 = parent.receipt_sha256;
        row.generation_parent_proposal_sha256 = parent.proposal_sha256;
        row.generation_parent_coordinate_sha256 = parent.coordinate_sha256;
    }
    Ok(row)
}

unsafe fn build_provider_allocation(
    input: *const Fixed64AllocationInputV1,
) -> Result<ProviderAllocation, ProviderError> {
    if input.is_null() || (input as usize) % align_of::<Fixed64AllocationInputV1>() != 0 {
        return Err(ProviderError::invalid(
            "rust_cpu fixed64 allocation input is null or misaligned",
        ));
    }
    // SAFETY: Pointer identity and alignment were checked above; the private
    // caller holds the descriptor live for the complete call.
    let input = unsafe { &*input };
    // SAFETY: build_inventory checks all bounded raw channels before use.
    let inventory = unsafe { build_inventory(input)? };
    let allocation = Fixed64Allocation::build(inventory).map_err(|_| {
        internal("rust_cpu fixed64 allocation failed an internal receipt invariant")
    })?;
    let mut rows = [Fixed64AllocationRowV1::default(); FIXED64_CANDIDATE_COUNT];
    for (index, slot) in allocation.slots().iter().enumerate() {
        rows[index] = row_from_slot(slot)?;
    }
    Ok(ProviderAllocation {
        rows,
        inventory_sha256: allocation.inventory_sha256(),
        allocation_sha256: allocation.receipt_sha256(),
        ready_count: u64::try_from(allocation.ready_count())
            .map_err(|_| internal("rust_cpu fixed64 allocation ready count exceeded u64"))?,
        typed_failure_count: u64::try_from(allocation.typed_failure_count())
            .map_err(|_| internal("rust_cpu fixed64 allocation failure count exceeded u64"))?,
    })
}

fn outputs_valid(
    out_rows: *mut Fixed64AllocationRowV1,
    out_inventory_sha256: *mut u8,
    out_allocation_sha256: *mut u8,
    out_ready_count: *mut u64,
    out_typed_failure_count: *mut u64,
) -> bool {
    !out_rows.is_null()
        && (out_rows as usize) % align_of::<Fixed64AllocationRowV1>() == 0
        && !out_inventory_sha256.is_null()
        && !out_allocation_sha256.is_null()
        && !out_ready_count.is_null()
        && (out_ready_count as usize) % align_of::<u64>() == 0
        && !out_typed_failure_count.is_null()
        && (out_typed_failure_count as usize) % align_of::<u64>() == 0
}

/// Build fixed64 allocation evidence through the independent Rust domain model.
///
/// # Safety
/// The input descriptor and its declared channels must remain readable for the
/// call. Every output pointer must address its complete, naturally aligned,
/// caller-owned denominator and must be disjoint from inputs and other outputs.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_fixed64_allocation_v1_build(
    input: *const Fixed64AllocationInputV1,
    out_rows: *mut Fixed64AllocationRowV1,
    out_inventory_sha256: *mut u8,
    out_allocation_sha256: *mut u8,
    out_ready_count: *mut u64,
    out_typed_failure_count: *mut u64,
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
    if !outputs_valid(
        out_rows,
        out_inventory_sha256,
        out_allocation_sha256,
        out_ready_count,
        out_typed_failure_count,
    ) {
        write_error(
            error,
            "rust_cpu fixed64 allocation output is null or misaligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        build_provider_allocation(input)
    }));
    match result {
        Ok(Ok(value)) => {
            // SAFETY: The private C++ caller supplies disjoint output ranges;
            // all computation completed in local storage before this commit.
            unsafe {
                ptr::copy_nonoverlapping(value.rows.as_ptr(), out_rows, FIXED64_CANDIDATE_COUNT);
                ptr::copy_nonoverlapping(
                    value.inventory_sha256.as_ptr(),
                    out_inventory_sha256,
                    value.inventory_sha256.len(),
                );
                ptr::copy_nonoverlapping(
                    value.allocation_sha256.as_ptr(),
                    out_allocation_sha256,
                    value.allocation_sha256.len(),
                );
                ptr::write(out_ready_count, value.ready_count);
                ptr::write(out_typed_failure_count, value.typed_failure_count);
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu fixed64 allocation provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

const _: () = {
    assert!(size_of::<Fixed64AllocationRowV1>() == 384);
};
