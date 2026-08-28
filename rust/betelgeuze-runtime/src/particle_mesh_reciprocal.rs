//! Safe binding for the reciprocal-only native particle-mesh ABI.

use std::borrow::Cow;
use std::ffi::CStr;
use std::fmt;
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_sys as sys;

use crate::{checked_count, ensure_abi_compatibility, Backend, Context, Error, ErrorCode, System};

/// Frozen order-4 reciprocal-mesh settings.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ParticleMeshReciprocalSettings {
    pub alpha_per_angstrom: f64,
    pub mesh_dimensions: [u32; 3],
    pub dielectric: f64,
}

impl Default for ParticleMeshReciprocalSettings {
    fn default() -> Self {
        Self {
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [16, 16, 16],
            dielectric: 1.0,
        }
    }
}

/// Immutable model input in the canonical Engine unit system.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ParticleMeshReciprocalParameters {
    pub atom_count: usize,
    pub cell_lengths_angstrom: [f64; 3],
    pub settings: ParticleMeshReciprocalSettings,
}

impl ParticleMeshReciprocalParameters {
    #[must_use]
    pub const fn new(atom_count: usize, cell_lengths_angstrom: [f64; 3]) -> Self {
        Self {
            atom_count,
            cell_lengths_angstrom,
            settings: ParticleMeshReciprocalSettings {
                alpha_per_angstrom: 0.3,
                mesh_dimensions: [16, 16, 16],
                dielectric: 1.0,
            },
        }
    }
}

/// Stable reciprocal-mesh validation and numerical error categories.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ParticleMeshReciprocalErrorCode {
    EmptySystem,
    CapacityExceeded,
    ChargeCountMismatch,
    NonFiniteCoordinate,
    NonFiniteCharge,
    NonNeutralSystem,
    InvalidCell,
    InvalidParameter,
    InvalidMesh,
    NonFiniteResult,
}

impl ParticleMeshReciprocalErrorCode {
    const fn from_raw(raw: sys::bg_particle_mesh_reciprocal_error_code) -> Option<Self> {
        match raw {
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE => None,
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM => Some(Self::EmptySystem),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED => {
                Some(Self::CapacityExceeded)
            }
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH => {
                Some(Self::ChargeCountMismatch)
            }
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE => {
                Some(Self::NonFiniteCoordinate)
            }
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE => Some(Self::NonFiniteCharge),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM => {
                Some(Self::NonNeutralSystem)
            }
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL => Some(Self::InvalidCell),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER => {
                Some(Self::InvalidParameter)
            }
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH => Some(Self::InvalidMesh),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT => Some(Self::NonFiniteResult),
            _ => None,
        }
    }
}

/// Failure from the reciprocal-only particle-mesh boundary.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ParticleMeshReciprocalError {
    pub status: ErrorCode,
    pub code: Option<ParticleMeshReciprocalErrorCode>,
    pub detail: Cow<'static, str>,
}

impl fmt::Display for ParticleMeshReciprocalError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(code) = self.code {
            write!(formatter, "{code:?} ({:?}): {}", self.status, self.detail)
        } else {
            write!(formatter, "{:?}: {}", self.status, self.detail)
        }
    }
}

impl std::error::Error for ParticleMeshReciprocalError {}

pub type ParticleMeshReciprocalResult<T> = std::result::Result<T, ParticleMeshReciprocalError>;

struct ModelHandleGuard {
    handle: NonNull<sys::bg_particle_mesh_reciprocal_model_v1>,
    destroy: unsafe extern "C" fn(*mut sys::bg_particle_mesh_reciprocal_model_v1),
}

impl ModelHandleGuard {
    fn new(handle: NonNull<sys::bg_particle_mesh_reciprocal_model_v1>) -> Self {
        Self {
            handle,
            destroy: sys::bg_particle_mesh_reciprocal_model_v1_destroy,
        }
    }

    fn into_inner(self) -> NonNull<sys::bg_particle_mesh_reciprocal_model_v1> {
        let handle = self.handle;
        std::mem::forget(self);
        handle
    }
}

impl Drop for ModelHandleGuard {
    fn drop(&mut self) {
        // SAFETY: The guard uniquely owns this non-null handle until transfer.
        unsafe { (self.destroy)(self.handle.as_ptr()) };
    }
}

/// Owned immutable native reciprocal-mesh model.
///
/// Native calls require external synchronization, so the handle is neither
/// `Send` nor `Sync`.
///
/// ```compile_fail
/// use betelgeuze_runtime::ParticleMeshReciprocalModel;
/// fn require_send_sync<T: Send + Sync>() {}
/// require_send_sync::<ParticleMeshReciprocalModel>();
/// ```
pub struct ParticleMeshReciprocalModel {
    handle: NonNull<sys::bg_particle_mesh_reciprocal_model_v1>,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

impl ParticleMeshReciprocalModel {
    pub fn new(parameters: ParticleMeshReciprocalParameters) -> ParticleMeshReciprocalResult<Self> {
        ensure_particle_mesh_reciprocal_abi_compatibility()?;
        let mut raw = initialized_parameters()?;
        raw.atom_count =
            checked_count(parameters.atom_count).map_err(ParticleMeshReciprocalError::from)?;
        raw.cell_lengths_angstrom = parameters.cell_lengths_angstrom;
        raw.alpha_per_angstrom = parameters.settings.alpha_per_angstrom;
        raw.mesh_dimensions = parameters.settings.mesh_dimensions;
        raw.dielectric = parameters.settings.dielectric;

        let mut raw_error = initialized_error()?;
        let mut handle = ptr::null_mut();
        // SAFETY: The immutable descriptor and both writable outputs live for
        // the call. Native creation deep-copies every parameter.
        let status = unsafe {
            sys::bg_particle_mesh_reciprocal_model_v1_create(&raw, &mut handle, &mut raw_error)
        };
        // Guard any non-null handle immediately, including an abnormal handle
        // returned alongside failure, so every native allocation is released.
        let guard = NonNull::new(handle).map(ModelHandleGuard::new);
        if status != sys::BG_STATUS_OK {
            drop(guard);
            return Err(error_from_call(status, &raw_error));
        }
        let guard = guard.ok_or_else(|| {
            abi_error("particle-mesh reciprocal model creation succeeded with a null handle")
        })?;
        validate_cleared_error(&raw_error)?;
        let model = Self {
            handle: guard.into_inner(),
            _not_send_or_sync: PhantomData,
        };
        if model.len()? != parameters.atom_count {
            return Err(abi_error(
                "native particle-mesh reciprocal model returned an inconsistent atom count",
            ));
        }
        Ok(model)
    }

    pub fn len(&self) -> ParticleMeshReciprocalResult<usize> {
        let mut count = 0_u64;
        // SAFETY: The owned model handle is live and count is writable.
        plain_status(unsafe {
            sys::bg_particle_mesh_reciprocal_model_v1_get_atom_count(
                self.handle.as_ptr(),
                &mut count,
            )
        })?;
        usize::try_from(count)
            .map_err(|_| abi_error("native particle-mesh reciprocal atom count exceeds usize"))
    }

    pub fn is_empty(&self) -> ParticleMeshReciprocalResult<bool> {
        self.len().map(|length| length == 0)
    }

    pub(crate) fn raw_handle(&self) -> *mut sys::bg_particle_mesh_reciprocal_model_v1 {
        self.handle.as_ptr()
    }
}

impl Drop for ParticleMeshReciprocalModel {
    fn drop(&mut self) {
        // SAFETY: This non-clone owner destroys its unique non-null handle once.
        unsafe { sys::bg_particle_mesh_reciprocal_model_v1_destroy(self.handle.as_ptr()) };
    }
}

/// Reciprocal-space mesh energy only; this is not a total energy.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct ParticleMeshReciprocalEnergy {
    pub reciprocal_space_kcal_per_mol: f64,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct ParticleMeshReciprocalForceSoaOwned {
    pub x_kcal_per_mol_angstrom: Vec<f64>,
    pub y_kcal_per_mol_angstrom: Vec<f64>,
    pub z_kcal_per_mol_angstrom: Vec<f64>,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct ParticleMeshReciprocalEvaluation {
    pub energy: ParticleMeshReciprocalEnergy,
    pub forces: ParticleMeshReciprocalForceSoaOwned,
}

impl Context {
    /// Evaluate reciprocal-mesh energy and forces on an explicit CPU lane.
    pub fn evaluate_particle_mesh_reciprocal(
        &self,
        system: &System,
        model: &ParticleMeshReciprocalModel,
    ) -> ParticleMeshReciprocalResult<ParticleMeshReciprocalEvaluation> {
        self.require_particle_mesh_reciprocal_backend()?;
        let count = model.len()?;
        let mut force_x = allocate_force_channel(count)?;
        let mut force_y = allocate_force_channel(count)?;
        let mut force_z = allocate_force_channel(count)?;
        let mut raw_energy = initialized_energy()?;
        let mut raw_forces = initialized_forces()?;
        raw_forces.atom_capacity =
            checked_count(count).map_err(ParticleMeshReciprocalError::from)?;
        raw_forces.x_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_x);
        raw_forces.y_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_y);
        raw_forces.z_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_z);
        let mut raw_error = initialized_error()?;

        // SAFETY: All handles are live and thread-confined. Output descriptors
        // and force channels are writable and mutually disjoint.
        let status = unsafe {
            sys::bg_context_evaluate_particle_mesh_reciprocal_v1(
                self.raw_handle(),
                system.raw_handle(),
                model.handle.as_ptr(),
                &mut raw_energy,
                &mut raw_forces,
                &mut raw_error,
            )
        };
        if status != sys::BG_STATUS_OK {
            return Err(error_from_call(status, &raw_error));
        }
        validate_cleared_error(&raw_error)?;
        validate_force_descriptor(
            &raw_forces,
            count,
            force_x.as_mut_ptr(),
            force_y.as_mut_ptr(),
            force_z.as_mut_ptr(),
        )?;
        if force_x
            .iter()
            .chain(&force_y)
            .chain(&force_z)
            .any(|value| !value.is_finite())
        {
            return Err(abi_error(
                "native particle-mesh reciprocal evaluator returned a non-finite force",
            ));
        }
        Ok(ParticleMeshReciprocalEvaluation {
            energy: energy_from_raw(raw_energy)?,
            forces: ParticleMeshReciprocalForceSoaOwned {
                x_kcal_per_mol_angstrom: force_x,
                y_kcal_per_mol_angstrom: force_y,
                z_kcal_per_mol_angstrom: force_z,
            },
        })
    }

    /// Evaluate reciprocal-mesh energy without allocating force output.
    pub fn evaluate_particle_mesh_reciprocal_energy(
        &self,
        system: &System,
        model: &ParticleMeshReciprocalModel,
    ) -> ParticleMeshReciprocalResult<ParticleMeshReciprocalEnergy> {
        self.require_particle_mesh_reciprocal_backend()?;
        let mut raw_energy = initialized_energy()?;
        let mut raw_error = initialized_error()?;
        // SAFETY: Every handle and descriptor is live. Null forces explicitly
        // select the reciprocal-energy-only native path.
        let status = unsafe {
            sys::bg_context_evaluate_particle_mesh_reciprocal_v1(
                self.raw_handle(),
                system.raw_handle(),
                model.handle.as_ptr(),
                &mut raw_energy,
                ptr::null_mut(),
                &mut raw_error,
            )
        };
        if status != sys::BG_STATUS_OK {
            return Err(error_from_call(status, &raw_error));
        }
        validate_cleared_error(&raw_error)?;
        energy_from_raw(raw_energy)
    }

    fn require_particle_mesh_reciprocal_backend(&self) -> ParticleMeshReciprocalResult<()> {
        // Reject AUTO and HIP from the original safe request before model
        // queries or output allocation; native AUTO resolution cannot grant
        // authority to this explicit-lane API.
        require_particle_mesh_reciprocal_backend(self.requested_backend())?;
        let resolved = self.backend().map_err(ParticleMeshReciprocalError::from)?;
        require_particle_mesh_reciprocal_backend(resolved)?;
        if resolved != self.requested_backend() {
            return Err(abi_error(format!(
                "native context resolved {:?} after explicit {:?} request",
                resolved,
                self.requested_backend()
            )));
        }
        Ok(())
    }
}

/// Query the immutable reciprocal-only native model profile identity.
pub fn particle_mesh_reciprocal_profile_id() -> ParticleMeshReciprocalResult<String> {
    ensure_particle_mesh_reciprocal_abi_compatibility()?;
    // SAFETY: The ABI returns a process-lifetime NUL-terminated string.
    unsafe {
        let pointer = sys::bg_particle_mesh_reciprocal_model_v1_profile_id();
        if pointer.is_null() {
            return Err(abi_error(
                "native particle-mesh reciprocal profile id is null",
            ));
        }
        let value = CStr::from_ptr(pointer).to_string_lossy().into_owned();
        if value.is_empty() {
            return Err(abi_error(
                "native particle-mesh reciprocal profile id is empty",
            ));
        }
        Ok(value)
    }
}

pub(crate) fn ensure_particle_mesh_reciprocal_abi_compatibility() -> ParticleMeshReciprocalResult<()>
{
    ensure_abi_compatibility().map_err(ParticleMeshReciprocalError::from)?;
    // SAFETY: Version query takes no pointers.
    let observed = unsafe { sys::bg_particle_mesh_reciprocal_abi_version() };
    if observed == sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION {
        Ok(())
    } else {
        Err(abi_error(format!(
            "native particle-mesh reciprocal ABI version {observed} does not match required version {}",
            sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION
        )))
    }
}

fn require_particle_mesh_reciprocal_backend(backend: Backend) -> ParticleMeshReciprocalResult<()> {
    match backend {
        Backend::CppCpuReference | Backend::RustCpu => Ok(()),
        Backend::Auto | Backend::HipFast | Backend::HipSafe => Err(ParticleMeshReciprocalError {
            status: ErrorCode::UnsupportedBackend,
            code: None,
            detail: Cow::Owned(format!(
                "particle-mesh reciprocal evaluation requires an explicitly requested C++ or Rust CPU backend; {backend:?} cannot fall back"
            )),
        }),
    }
}

fn initialized_parameters(
) -> ParticleMeshReciprocalResult<sys::bg_particle_mesh_reciprocal_parameters_v1> {
    let mut raw = MaybeUninit::<sys::bg_particle_mesh_reciprocal_parameters_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_particle_mesh_reciprocal_parameters_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_particle_mesh_reciprocal_parameters_v1>(),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        )
    })?;
    // SAFETY: Successful initialization wrote every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_energy() -> ParticleMeshReciprocalResult<sys::bg_particle_mesh_reciprocal_energy_v1>
{
    let mut raw = MaybeUninit::<sys::bg_particle_mesh_reciprocal_energy_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_particle_mesh_reciprocal_energy_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_particle_mesh_reciprocal_energy_v1>(),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        )
    })?;
    // SAFETY: Successful initialization wrote every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_forces(
) -> ParticleMeshReciprocalResult<sys::bg_particle_mesh_reciprocal_force_soa_v1> {
    let mut raw = MaybeUninit::<sys::bg_particle_mesh_reciprocal_force_soa_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_particle_mesh_reciprocal_force_soa_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_particle_mesh_reciprocal_force_soa_v1>(),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        )
    })?;
    // SAFETY: Successful initialization wrote every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_error() -> ParticleMeshReciprocalResult<sys::bg_particle_mesh_reciprocal_error_v1> {
    let mut raw = MaybeUninit::<sys::bg_particle_mesh_reciprocal_error_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_particle_mesh_reciprocal_error_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_particle_mesh_reciprocal_error_v1>(),
            sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        )
    })?;
    // SAFETY: Successful initialization wrote every field.
    Ok(unsafe { raw.assume_init() })
}

fn energy_from_raw(
    raw: sys::bg_particle_mesh_reciprocal_energy_v1,
) -> ParticleMeshReciprocalResult<ParticleMeshReciprocalEnergy> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_particle_mesh_reciprocal_energy_v1>()
        || raw.abi_version != sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        return Err(abi_error(
            "native particle-mesh reciprocal evaluator returned an invalid energy descriptor",
        ));
    }
    if !raw.reciprocal_space_kcal_per_mol.is_finite() {
        return Err(abi_error(
            "native particle-mesh reciprocal evaluator returned a non-finite energy",
        ));
    }
    Ok(ParticleMeshReciprocalEnergy {
        reciprocal_space_kcal_per_mol: raw.reciprocal_space_kcal_per_mol,
    })
}

fn validate_force_descriptor(
    raw: &sys::bg_particle_mesh_reciprocal_force_soa_v1,
    expected_count: usize,
    expected_x: *mut f64,
    expected_y: *mut f64,
    expected_z: *mut f64,
) -> ParticleMeshReciprocalResult<()> {
    let expected_count =
        checked_count(expected_count).map_err(ParticleMeshReciprocalError::from)?;
    if raw.struct_size as usize
        != std::mem::size_of::<sys::bg_particle_mesh_reciprocal_force_soa_v1>()
        || raw.abi_version != sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION
        || raw.atom_capacity != expected_count
        || raw.atom_count != expected_count
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.x_kcal_per_mol_angstrom != expected_x
        || raw.y_kcal_per_mol_angstrom != expected_y
        || raw.z_kcal_per_mol_angstrom != expected_z
        || raw.reserved != [0; 4]
    {
        Err(abi_error(
            "native particle-mesh reciprocal evaluator returned an invalid force descriptor",
        ))
    } else {
        Ok(())
    }
}

fn validate_error_descriptor(
    raw: &sys::bg_particle_mesh_reciprocal_error_v1,
) -> ParticleMeshReciprocalResult<()> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_particle_mesh_reciprocal_error_v1>()
        || raw.abi_version != sys::BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        Err(abi_error(
            "native particle-mesh reciprocal call returned an invalid typed-error descriptor",
        ))
    } else {
        Ok(())
    }
}

fn validate_cleared_error(
    raw: &sys::bg_particle_mesh_reciprocal_error_v1,
) -> ParticleMeshReciprocalResult<()> {
    validate_error_descriptor(raw)?;
    if raw.code != sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE
        || raw.detail.iter().any(|value| *value != 0)
    {
        Err(abi_error(
            "successful particle-mesh reciprocal call left a non-empty typed error",
        ))
    } else {
        Ok(())
    }
}

fn error_from_call(
    status: sys::bg_status,
    raw: &sys::bg_particle_mesh_reciprocal_error_v1,
) -> ParticleMeshReciprocalError {
    if let Err(error) = validate_error_descriptor(raw) {
        return error;
    }
    let status_code = ErrorCode::from_raw(status).unwrap_or(ErrorCode::InternalError);
    if status_code == ErrorCode::OutOfMemory {
        if raw.code != sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE {
            return abi_error("native particle-mesh reciprocal OOM returned a typed error code");
        }
        return allocation_free_out_of_memory_error();
    }
    if raw.code == sys::BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE {
        let native = Error::native(status);
        return ParticleMeshReciprocalError {
            status: status_code,
            code: None,
            detail: Cow::Owned(native.message),
        };
    }
    let Some(code) = ParticleMeshReciprocalErrorCode::from_raw(raw.code) else {
        return abi_error(format!(
            "native particle-mesh reciprocal call returned unknown typed error code {}",
            raw.code
        ));
    };
    let Some(nul) = raw.detail.iter().position(|value| *value == 0) else {
        return abi_error(
            "native particle-mesh reciprocal typed error detail is not NUL-terminated",
        );
    };
    let bytes: Vec<u8> = raw.detail[..nul].iter().map(|value| *value as u8).collect();
    ParticleMeshReciprocalError {
        status: status_code,
        code: Some(code),
        detail: Cow::Owned(String::from_utf8_lossy(&bytes).into_owned()),
    }
}

fn plain_status(status: sys::bg_status) -> ParticleMeshReciprocalResult<()> {
    if status == sys::BG_STATUS_OK {
        Ok(())
    } else if status == sys::BG_STATUS_OUT_OF_MEMORY {
        Err(allocation_free_out_of_memory_error())
    } else {
        Err(ParticleMeshReciprocalError::from(Error::native(status)))
    }
}

fn allocation_free_out_of_memory_error() -> ParticleMeshReciprocalError {
    ParticleMeshReciprocalError {
        status: ErrorCode::OutOfMemory,
        code: None,
        // Borrowed static storage ensures that an allocator failure is never
        // followed by a second infallible diagnostic allocation.
        detail: Cow::Borrowed("particle-mesh reciprocal allocation failed"),
    }
}

fn abi_error(detail: impl Into<Cow<'static, str>>) -> ParticleMeshReciprocalError {
    ParticleMeshReciprocalError {
        status: ErrorCode::AbiMismatch,
        code: None,
        detail: detail.into(),
    }
}

impl From<Error> for ParticleMeshReciprocalError {
    fn from(error: Error) -> Self {
        if error.code == ErrorCode::OutOfMemory {
            return allocation_free_out_of_memory_error();
        }
        Self {
            status: error.code,
            code: None,
            detail: Cow::Owned(error.message),
        }
    }
}

fn mutable_slice_pointer<T>(values: &mut [T]) -> *mut T {
    if values.is_empty() {
        ptr::null_mut()
    } else {
        values.as_mut_ptr()
    }
}

fn allocate_force_channel(count: usize) -> ParticleMeshReciprocalResult<Vec<f64>> {
    let mut values = Vec::new();
    values
        .try_reserve_exact(count)
        .map_err(|_| allocation_free_out_of_memory_error())?;
    values.resize(count, f64::NAN);
    Ok(values)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static TEST_DESTROY_COUNT: AtomicUsize = AtomicUsize::new(0);

    unsafe extern "C" fn count_test_destroy(
        _handle: *mut sys::bg_particle_mesh_reciprocal_model_v1,
    ) {
        TEST_DESTROY_COUNT.fetch_add(1, Ordering::SeqCst);
    }

    #[test]
    fn typed_error_mapping_covers_every_frozen_code() {
        let expected = [
            ParticleMeshReciprocalErrorCode::EmptySystem,
            ParticleMeshReciprocalErrorCode::CapacityExceeded,
            ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
            ParticleMeshReciprocalErrorCode::NonFiniteCoordinate,
            ParticleMeshReciprocalErrorCode::NonFiniteCharge,
            ParticleMeshReciprocalErrorCode::NonNeutralSystem,
            ParticleMeshReciprocalErrorCode::InvalidCell,
            ParticleMeshReciprocalErrorCode::InvalidParameter,
            ParticleMeshReciprocalErrorCode::InvalidMesh,
            ParticleMeshReciprocalErrorCode::NonFiniteResult,
        ];
        for (offset, expected) in expected.into_iter().enumerate() {
            assert_eq!(
                ParticleMeshReciprocalErrorCode::from_raw((offset + 1) as i32),
                Some(expected)
            );
        }
        assert_eq!(ParticleMeshReciprocalErrorCode::from_raw(0), None);
        assert_eq!(ParticleMeshReciprocalErrorCode::from_raw(11), None);
    }

    #[test]
    fn out_of_memory_error_materialization_is_allocation_free() {
        let error = allocation_free_out_of_memory_error();
        assert_eq!(error.status, ErrorCode::OutOfMemory);
        assert_eq!(error.code, None);
        assert_eq!(error.detail, "particle-mesh reciprocal allocation failed");
        assert!(matches!(error.detail, Cow::Borrowed(_)));
    }

    #[test]
    fn auto_and_hip_lanes_fail_closed() {
        for backend in [Backend::Auto, Backend::HipFast, Backend::HipSafe] {
            let error = require_particle_mesh_reciprocal_backend(backend).unwrap_err();
            assert_eq!(error.status, ErrorCode::UnsupportedBackend);
            assert_eq!(error.code, None);
            assert!(error.detail.contains("cannot fall back"));
        }
        require_particle_mesh_reciprocal_backend(Backend::CppCpuReference).unwrap();
        require_particle_mesh_reciprocal_backend(Backend::RustCpu).unwrap();
    }

    #[test]
    fn abnormal_non_null_creation_handle_guard_destroys_exactly_once() {
        TEST_DESTROY_COUNT.store(0, Ordering::SeqCst);
        let guard = ModelHandleGuard {
            handle: NonNull::dangling(),
            destroy: count_test_destroy,
        };
        drop(guard);
        assert_eq!(TEST_DESTROY_COUNT.load(Ordering::SeqCst), 1);
    }
}
