//! Native descriptor initialization and exactly-once handle ownership.

use std::mem::{size_of, MaybeUninit};
use std::ptr::{self, NonNull};

use super::{
    status_result, sys, Backend, Error, ErrorCode, Fixed64CoordinateSource, Fixed64Pipeline,
    Fixed64SourceEvidence, Result,
};

pub(super) fn slice_pointer<T>(values: &[T]) -> *const T {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}

pub(super) fn init<T>(
    initializer: unsafe extern "C" fn(*mut T, usize, u32) -> sys::bg_status,
) -> Result<T> {
    let mut value = MaybeUninit::<T>::uninit();
    // SAFETY: value is correctly sized writable storage and the ABI initializer
    // writes every field on success.
    status_result(unsafe { initializer(value.as_mut_ptr(), size_of::<T>(), sys::BG_ABI_VERSION) })?;
    // SAFETY: successful ABI initialization wrote the complete descriptor.
    Ok(unsafe { value.assume_init() })
}

pub(super) fn bool_from_abi(value: u8, label: &str) -> Result<bool> {
    match value {
        0 => Ok(false),
        1 => Ok(true),
        other => Err(Error::local(
            ErrorCode::AbiMismatch,
            format!("native fixed64 {label} returned non-boolean value {other}"),
        )),
    }
}

pub(super) fn raw_source_evidence(
    value: Fixed64SourceEvidence,
) -> sys::bg_docking_fixed64_source_evidence_v1 {
    sys::bg_docking_fixed64_source_evidence_v1 {
        receipt_sha256: value.receipt_sha256,
        proposal_sha256: value.proposal_sha256,
        coordinate_sha256: value.coordinate_sha256,
        reserved: [0; 2],
    }
}

pub(super) fn raw_coordinate_source(
    value: Fixed64CoordinateSource<'_>,
    ligand_atom_count: u64,
) -> sys::bg_docking_fixed64_coordinate_source_v1 {
    sys::bg_docking_fixed64_coordinate_source_v1 {
        source: raw_source_evidence(value.evidence),
        ligand_atom_count,
        x_angstrom: value.coordinates.x_angstrom.as_ptr(),
        y_angstrom: value.coordinates.y_angstrom.as_ptr(),
        z_angstrom: value.coordinates.z_angstrom.as_ptr(),
        reserved: [0; 4],
    }
}

pub(super) struct PipelineHandleGuard(pub(super) NonNull<sys::bg_docking_fixed64_pipeline_v2>);

impl PipelineHandleGuard {
    pub(super) fn into_inner(self) -> NonNull<sys::bg_docking_fixed64_pipeline_v2> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for PipelineHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_fixed64_pipeline_v2_destroy(self.0.as_ptr()) };
    }
}

pub(super) struct GeometricAdmissionHandleGuard(
    pub(super) NonNull<sys::bg_docking_geometric_admission_v1>,
);

impl GeometricAdmissionHandleGuard {
    pub(super) fn into_inner(self) -> NonNull<sys::bg_docking_geometric_admission_v1> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for GeometricAdmissionHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_geometric_admission_v1_destroy(self.0.as_ptr()) };
    }
}

pub(super) struct RigidHandleGuard(pub(super) NonNull<sys::bg_docking_rigid_refinement>);

impl RigidHandleGuard {
    pub(super) fn into_inner(self) -> NonNull<sys::bg_docking_rigid_refinement> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for RigidHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_rigid_refinement_destroy(self.0.as_ptr()) };
    }
}

pub(super) struct TorsionHandleGuard(pub(super) NonNull<sys::bg_docking_torsion_v7>);

impl TorsionHandleGuard {
    pub(super) fn into_inner(self) -> NonNull<sys::bg_docking_torsion_v7> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for TorsionHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_torsion_v7_destroy(self.0.as_ptr()) };
    }
}

pub(super) struct DownstreamHandleGuard(pub(super) NonNull<sys::bg_docking_fixed64_downstream_v1>);

impl DownstreamHandleGuard {
    pub(super) fn into_inner(self) -> NonNull<sys::bg_docking_fixed64_downstream_v1> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for DownstreamHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_fixed64_downstream_v1_destroy(self.0.as_ptr()) };
    }
}

pub(super) struct RankerHandleGuard(pub(super) NonNull<sys::bg_docking_stable_top_k_v1>);

impl RankerHandleGuard {
    pub(super) fn into_inner(self) -> NonNull<sys::bg_docking_stable_top_k_v1> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

pub(crate) struct PreselectedHandles {
    pub(crate) rigid: NonNull<sys::bg_docking_rigid_refinement>,
    pub(crate) torsion: NonNull<sys::bg_docking_torsion_v7>,
    pub(crate) downstream: NonNull<sys::bg_docking_fixed64_downstream_v1>,
    pub(crate) ranker: NonNull<sys::bg_docking_stable_top_k_v1>,
}

impl Drop for PreselectedHandles {
    fn drop(&mut self) {
        // SAFETY: this value exclusively owns all four non-null handles.
        unsafe {
            sys::bg_docking_rigid_refinement_destroy(self.rigid.as_ptr());
            sys::bg_docking_torsion_v7_destroy(self.torsion.as_ptr());
            sys::bg_docking_fixed64_downstream_v1_destroy(self.downstream.as_ptr());
            sys::bg_docking_stable_top_k_v1_destroy(self.ranker.as_ptr());
        }
    }
}

impl Drop for RankerHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_stable_top_k_v1_destroy(self.0.as_ptr()) };
    }
}

pub(super) fn preselected_component_backend(
    query: impl FnOnce(*mut sys::bg_backend) -> sys::bg_status,
) -> Result<Backend> {
    let mut raw = sys::BG_BACKEND_AUTO;
    status_result(query(&mut raw))?;
    Backend::from_raw(raw)
}

impl Drop for Fixed64Pipeline {
    fn drop(&mut self) {
        // SAFETY: this object owns both non-null handles and destroys each once,
        // before this object's context lease can release the native Context.
        unsafe {
            sys::bg_docking_fixed64_pipeline_v2_destroy(self.handle.as_ptr());
            sys::bg_docking_geometric_admission_v1_destroy(self.replay_admission_handle.as_ptr());
        }
    }
}
