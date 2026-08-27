use std::ffi::CStr;
use std::fmt;
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_sys as sys;

use crate::{checked_count, ensure_abi_compatibility, Backend, Context, Error, ErrorCode, System};

/// An unordered pair whose local full Coulomb interaction is removed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DirectEwaldPairExclusion {
    pub atom_i: usize,
    pub atom_j: usize,
}

/// An unordered pair with a local full-Coulomb scale in `[0, 1]`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DirectEwaldPairScale {
    pub atom_i: usize,
    pub atom_j: usize,
    pub coulomb_scale: f64,
}

/// Frozen direct-Ewald numerical settings.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DirectEwaldSettings {
    pub alpha_per_angstrom: f64,
    pub real_space_cutoff_angstrom: f64,
    pub reciprocal_max_indices: [i32; 3],
    pub dielectric: f64,
    pub minimum_pair_distance_angstrom: f64,
}

impl Default for DirectEwaldSettings {
    fn default() -> Self {
        Self {
            alpha_per_angstrom: 0.3,
            real_space_cutoff_angstrom: 8.0,
            reciprocal_max_indices: [5, 5, 5],
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
        }
    }
}

/// Borrowed constructor input for an immutable native direct-Ewald model.
///
/// Native creation deep-copies every non-empty pair-rule channel, so none of
/// these borrows are retained by [`DirectEwaldModel`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DirectEwaldParameters<'a> {
    pub atom_count: usize,
    pub cell_lengths_angstrom: [f64; 3],
    pub exclusions: &'a [DirectEwaldPairExclusion],
    pub pair_scales: &'a [DirectEwaldPairScale],
    pub settings: DirectEwaldSettings,
}

impl<'a> DirectEwaldParameters<'a> {
    #[must_use]
    pub const fn new(atom_count: usize, cell_lengths_angstrom: [f64; 3]) -> Self {
        Self {
            atom_count,
            cell_lengths_angstrom,
            exclusions: &[],
            pair_scales: &[],
            settings: DirectEwaldSettings {
                alpha_per_angstrom: 0.3,
                real_space_cutoff_angstrom: 8.0,
                reciprocal_max_indices: [5, 5, 5],
                dielectric: 1.0,
                minimum_pair_distance_angstrom: 1.0e-8,
            },
        }
    }
}

/// Stable direct-Ewald validation and numerical error categories.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum DirectEwaldErrorCode {
    EmptySystem,
    CapacityExceeded,
    ChargeCountMismatch,
    NonFiniteCoordinate,
    NonFiniteCharge,
    NonNeutralSystem,
    InvalidCell,
    CutoffViolatesMinimumImage,
    InvalidParameter,
    AtomIndexOutOfRange,
    RepeatedAtomIndex,
    DuplicatePairRule,
    ConflictingPairRule,
    AmbiguousPairCorrectionImage,
    AmbiguousRealSpaceCutoff,
    AmbiguousMinimumPairDistance,
    PairBelowMinimumDistance,
    DampingUnderflow,
    PhaseUnderflow,
    NonFiniteResult,
}

impl DirectEwaldErrorCode {
    const fn from_raw(raw: sys::bg_direct_ewald_error_code) -> Option<Self> {
        match raw {
            sys::BG_DIRECT_EWALD_ERROR_NONE => None,
            sys::BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM => Some(Self::EmptySystem),
            sys::BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED => Some(Self::CapacityExceeded),
            sys::BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH => Some(Self::ChargeCountMismatch),
            sys::BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE => Some(Self::NonFiniteCoordinate),
            sys::BG_DIRECT_EWALD_ERROR_NONFINITE_CHARGE => Some(Self::NonFiniteCharge),
            sys::BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM => Some(Self::NonNeutralSystem),
            sys::BG_DIRECT_EWALD_ERROR_INVALID_CELL => Some(Self::InvalidCell),
            sys::BG_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE => {
                Some(Self::CutoffViolatesMinimumImage)
            }
            sys::BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER => Some(Self::InvalidParameter),
            sys::BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE => Some(Self::AtomIndexOutOfRange),
            sys::BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX => Some(Self::RepeatedAtomIndex),
            sys::BG_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE => Some(Self::DuplicatePairRule),
            sys::BG_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE => Some(Self::ConflictingPairRule),
            sys::BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE => {
                Some(Self::AmbiguousPairCorrectionImage)
            }
            sys::BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF => {
                Some(Self::AmbiguousRealSpaceCutoff)
            }
            sys::BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE => {
                Some(Self::AmbiguousMinimumPairDistance)
            }
            sys::BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE => {
                Some(Self::PairBelowMinimumDistance)
            }
            sys::BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW => Some(Self::DampingUnderflow),
            sys::BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW => Some(Self::PhaseUnderflow),
            sys::BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT => Some(Self::NonFiniteResult),
            _ => None,
        }
    }
}

/// Failure returned by the safe direct-Ewald layer.
///
/// `code` is present for a scientific-input or numerical failure emitted by
/// the direct-Ewald evaluator. Generic ABI, ownership, and backend failures
/// retain their ordinary native `status` and have no typed Ewald code.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DirectEwaldError {
    pub status: ErrorCode,
    pub code: Option<DirectEwaldErrorCode>,
    pub detail: String,
}

impl fmt::Display for DirectEwaldError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(code) = self.code {
            write!(formatter, "{code:?} ({:?}): {}", self.status, self.detail)
        } else {
            write!(formatter, "{:?}: {}", self.status, self.detail)
        }
    }
}

impl std::error::Error for DirectEwaldError {}

pub type DirectEwaldResult<T> = std::result::Result<T, DirectEwaldError>;

/// Owned immutable native direct-Ewald model.
///
/// The native ABI requires external synchronization, so this handle is
/// deliberately neither `Send` nor `Sync`.
///
/// ```compile_fail
/// use betelgeuze_runtime::DirectEwaldModel;
/// fn require_send_sync<T: Send + Sync>() {}
/// require_send_sync::<DirectEwaldModel>();
/// ```
pub struct DirectEwaldModel {
    handle: NonNull<sys::bg_direct_ewald_model_v1>,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

impl DirectEwaldModel {
    /// Create an immutable model and deep-copy all pair rules.
    pub fn new(parameters: DirectEwaldParameters<'_>) -> DirectEwaldResult<Self> {
        ensure_direct_ewald_abi_compatibility()?;

        let exclusion_i = index_channel(parameters.exclusions.iter().map(|row| row.atom_i))?;
        let exclusion_j = index_channel(parameters.exclusions.iter().map(|row| row.atom_j))?;
        let pair_scale_i = index_channel(parameters.pair_scales.iter().map(|row| row.atom_i))?;
        let pair_scale_j = index_channel(parameters.pair_scales.iter().map(|row| row.atom_j))?;
        let pair_scale_coulomb: Vec<_> = parameters
            .pair_scales
            .iter()
            .map(|row| row.coulomb_scale)
            .collect();

        let mut raw = initialized_parameters()?;
        raw.atom_count = checked_count(parameters.atom_count).map_err(DirectEwaldError::from)?;
        raw.cell_lengths_angstrom = parameters.cell_lengths_angstrom;
        raw.alpha_per_angstrom = parameters.settings.alpha_per_angstrom;
        raw.real_space_cutoff_angstrom = parameters.settings.real_space_cutoff_angstrom;
        raw.reciprocal_max_indices = parameters.settings.reciprocal_max_indices;
        raw.dielectric = parameters.settings.dielectric;
        raw.minimum_pair_distance_angstrom = parameters.settings.minimum_pair_distance_angstrom;
        raw.exclusion_count =
            checked_count(parameters.exclusions.len()).map_err(DirectEwaldError::from)?;
        raw.exclusion_atom_i = slice_pointer(&exclusion_i);
        raw.exclusion_atom_j = slice_pointer(&exclusion_j);
        raw.pair_scale_count =
            checked_count(parameters.pair_scales.len()).map_err(DirectEwaldError::from)?;
        raw.pair_scale_atom_i = slice_pointer(&pair_scale_i);
        raw.pair_scale_atom_j = slice_pointer(&pair_scale_j);
        raw.pair_scale_coulomb = slice_pointer(&pair_scale_coulomb);

        let mut raw_error = initialized_error()?;
        let mut handle = ptr::null_mut();
        // SAFETY: Every borrowed channel remains live for this call, the
        // native contract deep-copies them, and both outputs are writable.
        let status =
            unsafe { sys::bg_direct_ewald_model_v1_create(&raw, &mut handle, &mut raw_error) };
        let model = NonNull::new(handle).map(|handle| Self {
            handle,
            _not_send_or_sync: PhantomData,
        });
        if status != sys::BG_STATUS_OK {
            drop(model);
            return Err(error_from_call(status, &raw_error));
        }
        let model = model
            .ok_or_else(|| abi_error("direct-Ewald model creation succeeded with a null handle"))?;
        validate_cleared_error(&raw_error)?;
        if model.len()? != parameters.atom_count {
            return Err(abi_error(
                "native direct-Ewald model returned an inconsistent atom count",
            ));
        }
        Ok(model)
    }

    pub fn len(&self) -> DirectEwaldResult<usize> {
        let mut count = 0_u64;
        // SAFETY: The owned model handle is live and count is writable.
        plain_status(unsafe {
            sys::bg_direct_ewald_model_v1_get_atom_count(self.handle.as_ptr(), &mut count)
        })?;
        usize::try_from(count)
            .map_err(|_| abi_error("native direct-Ewald atom count exceeds usize"))
    }

    pub fn is_empty(&self) -> DirectEwaldResult<bool> {
        self.len().map(|length| length == 0)
    }
}

impl Drop for DirectEwaldModel {
    fn drop(&mut self) {
        // SAFETY: This owner holds one non-null model handle and destroys it
        // exactly once. The type is neither Clone nor Send/Sync.
        unsafe { sys::bg_direct_ewald_model_v1_destroy(self.handle.as_ptr()) };
    }
}

/// Energy components in the ABI's frozen real, reciprocal, self,
/// pair-correction, total order.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct DirectEwaldEnergyComponents {
    pub real_space_kcal_per_mol: f64,
    pub reciprocal_space_kcal_per_mol: f64,
    pub self_kcal_per_mol: f64,
    pub pair_correction_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct DirectEwaldForceSoaOwned {
    pub x_kcal_per_mol_angstrom: Vec<f64>,
    pub y_kcal_per_mol_angstrom: Vec<f64>,
    pub z_kcal_per_mol_angstrom: Vec<f64>,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct DirectEwaldEvaluation {
    pub energy: DirectEwaldEnergyComponents,
    pub forces: DirectEwaldForceSoaOwned,
}

impl Context {
    /// Evaluate direct Ewald with the context's explicitly resolved CPU lane.
    /// HIP contexts fail closed; this safe layer never selects a CPU fallback.
    pub fn evaluate_direct_ewald(
        &self,
        system: &System,
        model: &DirectEwaldModel,
    ) -> DirectEwaldResult<DirectEwaldEvaluation> {
        require_direct_ewald_backend(self.backend().map_err(DirectEwaldError::from)?)?;
        let count = model.len()?;
        let mut force_x = vec![f64::NAN; count];
        let mut force_y = vec![f64::NAN; count];
        let mut force_z = vec![f64::NAN; count];
        let mut raw_energy = initialized_energy()?;
        let mut raw_forces = initialized_forces()?;
        raw_forces.atom_capacity = checked_count(count).map_err(DirectEwaldError::from)?;
        raw_forces.x_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_x);
        raw_forces.y_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_y);
        raw_forces.z_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_z);
        let mut raw_error = initialized_error()?;

        // SAFETY: Every opaque handle is live and thread-confined; all output
        // descriptors and force spans remain writable and mutually disjoint.
        let status = unsafe {
            sys::bg_context_evaluate_direct_ewald_v1(
                self.raw_handle(),
                system.handle.as_ptr(),
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
        if raw_forces.atom_count != checked_count(count).map_err(DirectEwaldError::from)? {
            return Err(abi_error(
                "native direct-Ewald evaluator returned an inconsistent force count",
            ));
        }
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
                "native direct-Ewald evaluator returned a non-finite force",
            ));
        }
        Ok(DirectEwaldEvaluation {
            energy: energy_from_raw(raw_energy)?,
            forces: DirectEwaldForceSoaOwned {
                x_kcal_per_mol_angstrom: force_x,
                y_kcal_per_mol_angstrom: force_y,
                z_kcal_per_mol_angstrom: force_z,
            },
        })
    }

    /// Evaluate direct-Ewald energy without requesting force storage.
    pub fn evaluate_direct_ewald_energy(
        &self,
        system: &System,
        model: &DirectEwaldModel,
    ) -> DirectEwaldResult<DirectEwaldEnergyComponents> {
        require_direct_ewald_backend(self.backend().map_err(DirectEwaldError::from)?)?;
        let mut raw_energy = initialized_energy()?;
        let mut raw_error = initialized_error()?;
        // SAFETY: Every handle and descriptor is live. A null force descriptor
        // explicitly requests the ABI's energy-only path.
        let status = unsafe {
            sys::bg_context_evaluate_direct_ewald_v1(
                self.raw_handle(),
                system.handle.as_ptr(),
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
}

/// Query the immutable native model-profile identity.
pub fn direct_ewald_profile_id() -> DirectEwaldResult<String> {
    ensure_direct_ewald_abi_compatibility()?;
    // SAFETY: The ABI returns a process-lifetime NUL-terminated string.
    unsafe {
        let pointer = sys::bg_direct_ewald_model_v1_profile_id();
        if pointer.is_null() {
            return Err(abi_error("native direct-Ewald profile id is null"));
        }
        let value = CStr::from_ptr(pointer).to_string_lossy().into_owned();
        if value.is_empty() {
            return Err(abi_error("native direct-Ewald profile id is empty"));
        }
        Ok(value)
    }
}

fn ensure_direct_ewald_abi_compatibility() -> DirectEwaldResult<()> {
    ensure_abi_compatibility().map_err(DirectEwaldError::from)?;
    // SAFETY: The version query takes no pointers.
    let observed = unsafe { sys::bg_direct_ewald_abi_version() };
    if observed == sys::BG_DIRECT_EWALD_ABI_VERSION {
        Ok(())
    } else {
        Err(abi_error(format!(
            "native direct-Ewald ABI version {observed} does not match required version {}",
            sys::BG_DIRECT_EWALD_ABI_VERSION
        )))
    }
}

fn require_direct_ewald_backend(backend: Backend) -> DirectEwaldResult<()> {
    match backend {
        Backend::CppCpuReference | Backend::RustCpu => Ok(()),
        Backend::Auto | Backend::HipFast | Backend::HipSafe => Err(DirectEwaldError {
            status: ErrorCode::UnsupportedBackend,
            code: None,
            detail: format!(
                "direct-Ewald requires an explicitly resolved C++ or Rust CPU backend; {backend:?} cannot fall back"
            ),
        }),
    }
}

fn initialized_parameters() -> DirectEwaldResult<sys::bg_direct_ewald_parameters_v1> {
    let mut raw = MaybeUninit::<sys::bg_direct_ewald_parameters_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_direct_ewald_parameters_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_direct_ewald_parameters_v1>(),
            sys::BG_DIRECT_EWALD_ABI_VERSION,
        )
    })?;
    // SAFETY: The successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_energy() -> DirectEwaldResult<sys::bg_direct_ewald_energy_components_v1> {
    let mut raw = MaybeUninit::<sys::bg_direct_ewald_energy_components_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_direct_ewald_energy_components_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_direct_ewald_energy_components_v1>(),
            sys::BG_DIRECT_EWALD_ABI_VERSION,
        )
    })?;
    // SAFETY: The successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_forces() -> DirectEwaldResult<sys::bg_direct_ewald_force_soa_v1> {
    let mut raw = MaybeUninit::<sys::bg_direct_ewald_force_soa_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_direct_ewald_force_soa_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_direct_ewald_force_soa_v1>(),
            sys::BG_DIRECT_EWALD_ABI_VERSION,
        )
    })?;
    // SAFETY: The successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_error() -> DirectEwaldResult<sys::bg_direct_ewald_error_v1> {
    let mut raw = MaybeUninit::<sys::bg_direct_ewald_error_v1>::uninit();
    // SAFETY: raw is correctly sized writable storage.
    plain_status(unsafe {
        sys::bg_direct_ewald_error_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_direct_ewald_error_v1>(),
            sys::BG_DIRECT_EWALD_ABI_VERSION,
        )
    })?;
    // SAFETY: The successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn energy_from_raw(
    raw: sys::bg_direct_ewald_energy_components_v1,
) -> DirectEwaldResult<DirectEwaldEnergyComponents> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_direct_ewald_energy_components_v1>()
        || raw.abi_version != sys::BG_DIRECT_EWALD_ABI_VERSION
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        return Err(abi_error(
            "native direct-Ewald evaluator returned an invalid energy descriptor",
        ));
    }
    let values = [
        raw.real_space_kcal_per_mol,
        raw.reciprocal_space_kcal_per_mol,
        raw.self_kcal_per_mol,
        raw.pair_correction_kcal_per_mol,
        raw.total_kcal_per_mol,
    ];
    if values.iter().any(|value| !value.is_finite()) {
        return Err(abi_error(
            "native direct-Ewald evaluator returned a non-finite energy",
        ));
    }
    let summed = raw.real_space_kcal_per_mol
        + raw.reciprocal_space_kcal_per_mol
        + raw.self_kcal_per_mol
        + raw.pair_correction_kcal_per_mol;
    if summed.to_bits() != raw.total_kcal_per_mol.to_bits() {
        return Err(abi_error(
            "native direct-Ewald total violates the frozen component summation order",
        ));
    }
    Ok(DirectEwaldEnergyComponents {
        real_space_kcal_per_mol: raw.real_space_kcal_per_mol,
        reciprocal_space_kcal_per_mol: raw.reciprocal_space_kcal_per_mol,
        self_kcal_per_mol: raw.self_kcal_per_mol,
        pair_correction_kcal_per_mol: raw.pair_correction_kcal_per_mol,
        total_kcal_per_mol: raw.total_kcal_per_mol,
    })
}

fn validate_force_descriptor(
    raw: &sys::bg_direct_ewald_force_soa_v1,
    expected_count: usize,
    expected_x: *mut f64,
    expected_y: *mut f64,
    expected_z: *mut f64,
) -> DirectEwaldResult<()> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_direct_ewald_force_soa_v1>()
        || raw.abi_version != sys::BG_DIRECT_EWALD_ABI_VERSION
        || raw.atom_capacity != checked_count(expected_count).map_err(DirectEwaldError::from)?
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.x_kcal_per_mol_angstrom != expected_x
        || raw.y_kcal_per_mol_angstrom != expected_y
        || raw.z_kcal_per_mol_angstrom != expected_z
        || raw.reserved != [0; 4]
    {
        Err(abi_error(
            "native direct-Ewald evaluator returned an invalid force descriptor",
        ))
    } else {
        Ok(())
    }
}

fn validate_error_descriptor(raw: &sys::bg_direct_ewald_error_v1) -> DirectEwaldResult<()> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_direct_ewald_error_v1>()
        || raw.abi_version != sys::BG_DIRECT_EWALD_ABI_VERSION
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        Err(abi_error(
            "native direct-Ewald call returned an invalid typed-error descriptor",
        ))
    } else {
        Ok(())
    }
}

fn validate_cleared_error(raw: &sys::bg_direct_ewald_error_v1) -> DirectEwaldResult<()> {
    validate_error_descriptor(raw)?;
    if raw.code != sys::BG_DIRECT_EWALD_ERROR_NONE || raw.detail.iter().any(|value| *value != 0) {
        Err(abi_error(
            "successful direct-Ewald call left a non-empty typed error",
        ))
    } else {
        Ok(())
    }
}

fn error_from_call(
    status: sys::bg_status,
    raw: &sys::bg_direct_ewald_error_v1,
) -> DirectEwaldError {
    if let Err(error) = validate_error_descriptor(raw) {
        return error;
    }
    let status_code = ErrorCode::from_raw(status).unwrap_or(ErrorCode::InternalError);
    if raw.code == sys::BG_DIRECT_EWALD_ERROR_NONE {
        let native = Error::native(status);
        return DirectEwaldError {
            status: status_code,
            code: None,
            detail: native.message,
        };
    }
    let Some(code) = DirectEwaldErrorCode::from_raw(raw.code) else {
        return abi_error(format!(
            "native direct-Ewald call returned unknown typed error code {}",
            raw.code
        ));
    };
    let Some(nul) = raw.detail.iter().position(|value| *value == 0) else {
        return abi_error("native direct-Ewald typed error detail is not NUL-terminated");
    };
    let bytes: Vec<u8> = raw.detail[..nul].iter().map(|value| *value as u8).collect();
    DirectEwaldError {
        status: status_code,
        code: Some(code),
        detail: String::from_utf8_lossy(&bytes).into_owned(),
    }
}

fn plain_status(status: sys::bg_status) -> DirectEwaldResult<()> {
    if status == sys::BG_STATUS_OK {
        Ok(())
    } else {
        Err(DirectEwaldError::from(Error::native(status)))
    }
}

fn abi_error(detail: impl Into<String>) -> DirectEwaldError {
    DirectEwaldError {
        status: ErrorCode::AbiMismatch,
        code: None,
        detail: detail.into(),
    }
}

impl From<Error> for DirectEwaldError {
    fn from(error: Error) -> Self {
        Self {
            status: error.code,
            code: None,
            detail: error.message,
        }
    }
}

fn index_channel(indices: impl Iterator<Item = usize>) -> DirectEwaldResult<Vec<u64>> {
    indices
        .map(|index| {
            u64::try_from(index).map_err(|_| DirectEwaldError {
                status: ErrorCode::CapacityOverflow,
                code: None,
                detail: "atom index does not fit native uint64".to_owned(),
            })
        })
        .collect()
}

fn slice_pointer<T>(values: &[T]) -> *const T {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}

fn mutable_slice_pointer<T>(values: &mut [T]) -> *mut T {
    if values.is_empty() {
        ptr::null_mut()
    } else {
        values.as_mut_ptr()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn typed_error_mapping_covers_every_frozen_code() {
        let expected = [
            DirectEwaldErrorCode::EmptySystem,
            DirectEwaldErrorCode::CapacityExceeded,
            DirectEwaldErrorCode::ChargeCountMismatch,
            DirectEwaldErrorCode::NonFiniteCoordinate,
            DirectEwaldErrorCode::NonFiniteCharge,
            DirectEwaldErrorCode::NonNeutralSystem,
            DirectEwaldErrorCode::InvalidCell,
            DirectEwaldErrorCode::CutoffViolatesMinimumImage,
            DirectEwaldErrorCode::InvalidParameter,
            DirectEwaldErrorCode::AtomIndexOutOfRange,
            DirectEwaldErrorCode::RepeatedAtomIndex,
            DirectEwaldErrorCode::DuplicatePairRule,
            DirectEwaldErrorCode::ConflictingPairRule,
            DirectEwaldErrorCode::AmbiguousPairCorrectionImage,
            DirectEwaldErrorCode::AmbiguousRealSpaceCutoff,
            DirectEwaldErrorCode::AmbiguousMinimumPairDistance,
            DirectEwaldErrorCode::PairBelowMinimumDistance,
            DirectEwaldErrorCode::DampingUnderflow,
            DirectEwaldErrorCode::PhaseUnderflow,
            DirectEwaldErrorCode::NonFiniteResult,
        ];
        for (offset, expected) in expected.into_iter().enumerate() {
            assert_eq!(
                DirectEwaldErrorCode::from_raw((offset + 1) as i32),
                Some(expected)
            );
        }
        assert_eq!(DirectEwaldErrorCode::from_raw(0), None);
        assert_eq!(DirectEwaldErrorCode::from_raw(21), None);
    }

    #[test]
    fn unsupported_lanes_fail_closed_without_fallback() {
        for backend in [Backend::Auto, Backend::HipFast, Backend::HipSafe] {
            let error = require_direct_ewald_backend(backend).unwrap_err();
            assert_eq!(error.status, ErrorCode::UnsupportedBackend);
            assert_eq!(error.code, None);
            assert!(error.detail.contains("cannot fall back"));
        }
        require_direct_ewald_backend(Backend::CppCpuReference).unwrap();
        require_direct_ewald_backend(Backend::RustCpu).unwrap();
    }
}
