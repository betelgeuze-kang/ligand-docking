//! Safe ownership and unit-aware views for the Betelgeuze native compute ABI.
//!
//! The raw handles and pointers remain private to this crate. All system input
//! is copied into native-owned structure-of-arrays storage.

mod development_water_box;
mod docking;
mod dynamics;
mod fixed64_lane_metrics;
mod forcefield;
mod qualification;
mod qualification_v6;
mod qualification_v7;

pub use betelgeuze_docking_search::Fixed64Lane;
pub use development_water_box::{
    development_ion_parameters_v1, development_water_box_constraints_v1_profile_sha256,
    development_water_box_nvt_ensemble_v1_profile_sha256, development_water_box_v1_profile_sha256,
    development_water_ion_v1_profile_sha256, evaluate_development_single_water_v1,
    evaluate_development_water_box_v1, evaluate_development_water_ion_v1,
    observe_development_water_box_nvt_ensemble_v1, DevelopmentIonIdentityV1,
    DevelopmentIonParameterErrorV1, DevelopmentIonParametersV1, DevelopmentIonSpeciesV1,
    DevelopmentWaterBoxNvtEnsembleReportV1, DevelopmentWaterBoxNvtObservationV1,
    DevelopmentWaterBoxV1, DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_ID,
    DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_SCHEMA_ID,
    DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_PROFILE_ID,
    DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_SCHEMA_ID, DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT,
    DEVELOPMENT_WATER_BOX_V1_PROFILE_ID, DEVELOPMENT_WATER_BOX_V1_SCHEMA_ID,
    DEVELOPMENT_WATER_ION_V1_ATOM_COUNT, DEVELOPMENT_WATER_ION_V1_PARAMETER_SOURCE_DOI,
    DEVELOPMENT_WATER_ION_V1_PROFILE_ID, DEVELOPMENT_WATER_ION_V1_SCHEMA_ID,
};
pub use docking::{
    Fixed64AtomicFeature, Fixed64AuthorityDisposition, Fixed64BatchReceipts,
    Fixed64ChiralityCenter, Fixed64ClusterEvidence, Fixed64ConformerCoordinateSource,
    Fixed64CoordinateSource, Fixed64Donor, Fixed64ExactSourceEvidence, Fixed64FeatureGeometry,
    Fixed64FeatureKind, Fixed64GeometricEvidence, Fixed64Identities,
    Fixed64IndexedCoordinateSource, Fixed64Ligand, Fixed64Pair, Fixed64Pipeline,
    Fixed64PipelineContext, Fixed64PipelineReceipt, Fixed64PipelineRow,
    Fixed64PreselectedBatchReceipts, Fixed64PreselectedPipeline, Fixed64PreselectedPipelineReceipt,
    Fixed64PreselectedPipelineRow, Fixed64PreselectedRunInput, Fixed64ProducerEvidence,
    Fixed64RankingEvidence, Fixed64Receptor, Fixed64RefinementEvidence, Fixed64RefinementMode,
    Fixed64RigidCoordinates, Fixed64RigidEvidence, Fixed64RigidProfileEvidence, Fixed64Rotor,
    Fixed64RunInput, Fixed64ScientificCandidateProjection, Fixed64ScientificProjection,
    Fixed64ScorerEvidence, Fixed64SourceEvidence, Fixed64TorsionCoordinates,
    Fixed64TorsionEvidence, Fixed64TorsionMoveEvidence, Fixed64ValidityEvidence,
    FIXED64_NATIVE_PIPELINE_PROFILE_ID, FIXED64_PRESELECTED_PIPELINE_PROFILE_ID,
};
pub use dynamics::{
    DistanceConstraint, DistanceConstraints, DynamicsReport, Integrator, MinimizationReport,
    MinimizerOptions, Simulation, SimulationOptions,
};
pub use fixed64_lane_metrics::{
    Fixed64ConformerOrientationInteraction, Fixed64CoordinateEntropy, Fixed64LaneMetricObservation,
    Fixed64LaneMetricSummary, Fixed64LaneMetricsReceipt, Fixed64LaneMetricsReference,
    Fixed64MetricRate, Fixed64OracleFailureClass, Fixed64OracleSelectionSummary,
    FIXED64_LANE_METRICS_OBSERVATION_SCHEMA_ID, FIXED64_LANE_METRICS_REFERENCE_SCHEMA_ID,
    FIXED64_LANE_METRICS_SCHEMA_ID, FIXED64_MAX_SYMMETRY_PERMUTATIONS,
    FIXED64_ORACLE_RMSD_THRESHOLD_ANGSTROM,
};
pub use forcefield::{
    native_periodic_neighbor_list_v1_profile_sha256,
    native_periodic_neighbor_list_v2_profile_sha256, AtomNonbonded, EnergyComponents, Evaluation,
    ForceField, ForceFieldInput, ForceSoaOwned, HarmonicAngle, HarmonicBond, NonbondedSettings,
    OrthorhombicCell, PairExclusion, PairScale, PeriodicTorsion,
    NATIVE_PERIODIC_NEIGHBOR_LIST_V1_PROFILE_ID, NATIVE_PERIODIC_NEIGHBOR_LIST_V1_SCHEMA_ID,
    NATIVE_PERIODIC_NEIGHBOR_LIST_V2_PROFILE_ID, NATIVE_PERIODIC_NEIGHBOR_LIST_V2_SCHEMA_ID,
};
pub use qualification::{
    compare_fixed64_scientific_numeric_parity, fixed64_cpu_v5_live_activation_admitted,
    run_native_fixed64_cpu_probe_v5, Fixed64CpuFixtureProbeV5, Fixed64CpuProbeConfigV5,
    Fixed64CpuProbeReportV5, Fixed64NumericParityV5, FIXED64_CPU_QUALIFICATION_V5_PROFILE_ID,
    FIXED64_CPU_QUALIFICATION_V5_SCHEMA_ID, FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED,
};
pub use qualification_v6::{
    preflight_native_fixed64_cpu_v6, run_native_fixed64_cpu_qualification_v6,
    verify_native_fixed64_cpu_v6_activation, Fixed64CpuActivationStatusV6,
    Fixed64CpuPersistedQualificationV6, Fixed64CpuPreflightV6,
    NativeFixed64CpuQualificationV6Error, FIXED64_CPU_QUALIFICATION_V6_PROFILE_ID,
    FIXED64_CPU_QUALIFICATION_V6_SCHEMA_ID,
};
pub use qualification_v7::{
    preflight_native_fixed64_cpu_v7, run_native_fixed64_cpu_qualification_v7,
    verify_native_fixed64_cpu_v7_activation, Fixed64CpuActivationStatusV7,
    Fixed64CpuPersistedQualificationV7, Fixed64CpuPreflightV7,
    NativeFixed64CpuQualificationV7Error, FIXED64_CPU_QUALIFICATION_V7_PROFILE_ID,
    FIXED64_CPU_QUALIFICATION_V7_SCHEMA_ID,
};

use std::ffi::CStr;
use std::fmt;
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_sys as sys;

/// The only unit system accepted by native ABI v1.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnitSystem {
    AngstromKcalMol,
}

impl UnitSystem {
    fn from_raw(raw: sys::bg_unit_system) -> Result<Self> {
        match raw {
            sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL => Ok(Self::AngstromKcalMol),
            other => Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native library returned unknown unit system {other}"),
            )),
        }
    }
}

/// Human-readable canonical-unit manifest mirrored from `engine.h`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CanonicalUnits {
    pub length: &'static str,
    pub energy: &'static str,
    pub force: &'static str,
    pub charge: &'static str,
    pub mass: &'static str,
    pub angle: &'static str,
    pub time: &'static str,
    pub velocity: &'static str,
    pub temperature: &'static str,
    pub coulomb_constant_kcal_angstrom_per_mol_e2: f64,
}

pub const CANONICAL_UNITS: CanonicalUnits = CanonicalUnits {
    length: "angstrom",
    energy: "kcal/mol",
    force: "kcal/(mol*angstrom)",
    charge: "elementary_charge",
    mass: "dalton",
    angle: "radian",
    time: "femtosecond",
    velocity: "angstrom/femtosecond",
    temperature: "kelvin",
    coulomb_constant_kcal_angstrom_per_mol_e2: sys::BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Backend {
    Auto,
    CppCpuReference,
    RustCpu,
    HipFast,
    HipSafe,
}

impl Backend {
    /// Frozen source-compatible alias for the qualification-only C++ lane.
    #[allow(non_upper_case_globals)]
    pub const Cpu: Self = Self::CppCpuReference;

    /// Frozen source-compatible alias for the historical parallel HIP lane.
    #[allow(non_upper_case_globals)]
    pub const Hip: Self = Self::HipFast;

    const fn as_raw(self) -> sys::bg_backend {
        match self {
            Self::Auto => sys::BG_BACKEND_AUTO,
            Self::CppCpuReference => sys::BG_BACKEND_CPP_CPU_REFERENCE,
            Self::RustCpu => sys::BG_BACKEND_RUST_CPU,
            Self::HipFast => sys::BG_BACKEND_HIP_FAST,
            Self::HipSafe => sys::BG_BACKEND_HIP_SAFE,
        }
    }

    fn from_raw(raw: sys::bg_backend) -> Result<Self> {
        match raw {
            sys::BG_BACKEND_AUTO => Ok(Self::Auto),
            sys::BG_BACKEND_CPP_CPU_REFERENCE => Ok(Self::CppCpuReference),
            sys::BG_BACKEND_RUST_CPU => Ok(Self::RustCpu),
            sys::BG_BACKEND_HIP_FAST => Ok(Self::HipFast),
            sys::BG_BACKEND_HIP_SAFE => Ok(Self::HipSafe),
            other => Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native library returned unknown backend {other}"),
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContextOptions {
    pub backend: Backend,
    pub device_ordinal: i32,
}

impl ContextOptions {
    /// Qualification-only C++ reference lane.
    pub const fn cpu_reference() -> Self {
        Self {
            backend: Backend::CppCpuReference,
            device_ordinal: 0,
        }
    }

    /// Product-default deterministic native Rust CPU lane.
    pub const fn rust_cpu() -> Self {
        Self {
            backend: Backend::RustCpu,
            device_ordinal: 0,
        }
    }

    /// Frozen compatibility constructor for `cpu_reference()`.
    pub const fn cpu() -> Self {
        Self::cpu_reference()
    }

    /// Frozen compatibility constructor for `hip_fast()`.
    pub const fn hip(device_ordinal: i32) -> Self {
        Self::hip_fast(device_ordinal)
    }

    pub const fn hip_fast(device_ordinal: i32) -> Self {
        Self {
            backend: Backend::HipFast,
            device_ordinal,
        }
    }

    pub const fn hip_safe(device_ordinal: i32) -> Self {
        Self {
            backend: Backend::HipSafe,
            device_ordinal,
        }
    }

    pub const fn auto(device_ordinal: i32) -> Self {
        Self {
            backend: Backend::Auto,
            device_ordinal,
        }
    }
}

impl Default for ContextOptions {
    fn default() -> Self {
        Self::rust_cpu()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    InvalidArgument,
    AbiMismatch,
    UnsupportedBackend,
    BackendUnavailable,
    OutOfMemory,
    CapacityOverflow,
    BufferTooSmall,
    BackendError,
    InternalError,
    NumericalError,
    Unknown(i32),
}

impl ErrorCode {
    pub const fn from_raw(raw: i32) -> Option<Self> {
        match raw {
            sys::BG_STATUS_OK => None,
            sys::BG_STATUS_INVALID_ARGUMENT => Some(Self::InvalidArgument),
            sys::BG_STATUS_ABI_MISMATCH => Some(Self::AbiMismatch),
            sys::BG_STATUS_UNSUPPORTED_BACKEND => Some(Self::UnsupportedBackend),
            sys::BG_STATUS_BACKEND_UNAVAILABLE => Some(Self::BackendUnavailable),
            sys::BG_STATUS_OUT_OF_MEMORY => Some(Self::OutOfMemory),
            sys::BG_STATUS_CAPACITY_OVERFLOW => Some(Self::CapacityOverflow),
            sys::BG_STATUS_BUFFER_TOO_SMALL => Some(Self::BufferTooSmall),
            sys::BG_STATUS_BACKEND_ERROR => Some(Self::BackendError),
            sys::BG_STATUS_INTERNAL_ERROR => Some(Self::InternalError),
            sys::BG_STATUS_NUMERICAL_ERROR => Some(Self::NumericalError),
            other => Some(Self::Unknown(other)),
        }
    }

    pub const fn as_raw(self) -> i32 {
        match self {
            Self::InvalidArgument => sys::BG_STATUS_INVALID_ARGUMENT,
            Self::AbiMismatch => sys::BG_STATUS_ABI_MISMATCH,
            Self::UnsupportedBackend => sys::BG_STATUS_UNSUPPORTED_BACKEND,
            Self::BackendUnavailable => sys::BG_STATUS_BACKEND_UNAVAILABLE,
            Self::OutOfMemory => sys::BG_STATUS_OUT_OF_MEMORY,
            Self::CapacityOverflow => sys::BG_STATUS_CAPACITY_OVERFLOW,
            Self::BufferTooSmall => sys::BG_STATUS_BUFFER_TOO_SMALL,
            Self::BackendError => sys::BG_STATUS_BACKEND_ERROR,
            Self::InternalError => sys::BG_STATUS_INTERNAL_ERROR,
            Self::NumericalError => sys::BG_STATUS_NUMERICAL_ERROR,
            Self::Unknown(raw) => raw,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Error {
    pub code: ErrorCode,
    pub message: String,
}

impl Error {
    fn local(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }

    fn native(status: sys::bg_status) -> Self {
        let code = ErrorCode::from_raw(status).unwrap_or(ErrorCode::InternalError);
        let message = native_last_error().unwrap_or_else(|| native_status_name(status));
        Self { code, message }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?}: {}", self.code, self.message)
    }
}

impl std::error::Error for Error {}

pub type Result<T> = std::result::Result<T, Error>;

fn status_result(status: sys::bg_status) -> Result<()> {
    if status == sys::BG_STATUS_OK {
        Ok(())
    } else {
        Err(Error::native(status))
    }
}

fn ensure_abi_compatibility() -> Result<()> {
    // SAFETY: Version queries take no pointers and are stable ABI entry points.
    let observed = unsafe { sys::bg_abi_version() };
    if observed == sys::BG_ABI_VERSION {
        Ok(())
    } else {
        Err(Error::local(
            ErrorCode::AbiMismatch,
            format!(
                "native ABI version {observed} does not match required version {}",
                sys::BG_ABI_VERSION
            ),
        ))
    }
}

fn native_status_name(status: sys::bg_status) -> String {
    // SAFETY: The native ABI returns a process-lifetime NUL-terminated string.
    unsafe {
        let pointer = sys::bg_status_string(status);
        if pointer.is_null() {
            return format!("native status {status}");
        }
        CStr::from_ptr(pointer).to_string_lossy().into_owned()
    }
}

fn native_last_error() -> Option<String> {
    // SAFETY: Both calls follow the documented size-query/copy protocol. The
    // copied bytes are native-owned diagnostics and contain a trailing NUL.
    unsafe {
        let mut required = 0_u64;
        if sys::bg_last_error_message_copy(ptr::null_mut(), 0, &mut required) != sys::BG_STATUS_OK
            || required <= 1
        {
            return None;
        }
        let length = usize::try_from(required).ok()?;
        let mut buffer = vec![0 as std::ffi::c_char; length];
        if sys::bg_last_error_message_copy(buffer.as_mut_ptr(), required, &mut required)
            != sys::BG_STATUS_OK
        {
            return None;
        }
        Some(
            CStr::from_ptr(buffer.as_ptr())
                .to_string_lossy()
                .into_owned(),
        )
    }
}

fn invalid(message: impl Into<String>) -> Error {
    Error::local(ErrorCode::InvalidArgument, message)
}

fn checked_count(length: usize) -> Result<u64> {
    u64::try_from(length).map_err(|_| {
        Error::local(
            ErrorCode::CapacityOverflow,
            "slice length does not fit the native uint64 count",
        )
    })
}

fn finite(values: &[f64]) -> bool {
    values.iter().all(|value| value.is_finite())
}

fn channel_pointer(values: &[f64]) -> *const f64 {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}

/// Shared private owner for the exact native context handle.
pub(crate) struct ContextInner {
    handle: NonNull<sys::bg_context>,
}

impl ContextInner {
    pub(crate) fn raw_handle(&self) -> *mut sys::bg_context {
        self.handle.as_ptr()
    }
}

impl Drop for ContextInner {
    fn drop(&mut self) {
        // SAFETY: the last context lease owns this non-null handle and destroys
        // it exactly once after every dependent native object has been dropped.
        unsafe { sys::bg_context_destroy(self.handle.as_ptr()) };
    }
}

/// Owned native execution context.
///
/// Context operations are intentionally confined to their creating thread
/// until the native ABI publishes a stronger synchronization contract.
/// Fixed64 pipelines retain a private lease on this context, so dropping this
/// public wrapper does not invalidate a pipeline that was created from it.
///
/// ```compile_fail
/// use betelgeuze_runtime::Context;
/// fn require_send_sync<T: Send + Sync>() {}
/// require_send_sync::<Context>();
/// ```
pub struct Context {
    inner: Rc<ContextInner>,
}

impl Context {
    pub fn new(options: ContextOptions) -> Result<Self> {
        ensure_abi_compatibility()?;
        if options.device_ordinal < 0 {
            return Err(invalid("device_ordinal must be non-negative"));
        }

        let mut raw_options = MaybeUninit::<sys::bg_context_options>::uninit();
        // SAFETY: raw_options points to correctly sized writable storage.
        status_result(unsafe {
            sys::bg_context_options_init(
                raw_options.as_mut_ptr(),
                std::mem::size_of::<sys::bg_context_options>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_options = unsafe { raw_options.assume_init() };
        raw_options.backend = options.backend.as_raw();
        raw_options.device_ordinal = options.device_ordinal;

        let mut handle = ptr::null_mut();
        // SAFETY: Both descriptors and the out pointer remain live for the call.
        status_result(unsafe { sys::bg_context_create(&raw_options, &mut handle) })?;
        let handle = NonNull::new(handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native context creation succeeded with a null handle",
            )
        })?;
        Ok(Self {
            inner: Rc::new(ContextInner { handle }),
        })
    }

    pub fn backend_available(backend: Backend, device_ordinal: i32) -> Result<bool> {
        ensure_abi_compatibility()?;
        if device_ordinal < 0 {
            return Err(invalid("device_ordinal must be non-negative"));
        }
        let mut available = 0_u8;
        // SAFETY: available is a valid writable byte for the duration of the call.
        status_result(unsafe {
            sys::bg_backend_is_available(backend.as_raw(), device_ordinal, &mut available)
        })?;
        match available {
            0 => Ok(false),
            1 => Ok(true),
            other => Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native availability query returned non-boolean value {other}"),
            )),
        }
    }

    pub fn backend(&self) -> Result<Backend> {
        let mut backend = sys::BG_BACKEND_AUTO;
        // SAFETY: The private handle is live and backend is writable.
        status_result(unsafe { sys::bg_context_get_backend(self.raw_handle(), &mut backend) })?;
        Backend::from_raw(backend)
    }

    pub fn device_ordinal(&self) -> Result<i32> {
        let mut device_ordinal = -1;
        // SAFETY: The private handle is live and device_ordinal is writable.
        status_result(unsafe {
            sys::bg_context_get_device_ordinal(self.raw_handle(), &mut device_ordinal)
        })?;
        Ok(device_ordinal)
    }

    pub fn unit_system(&self) -> Result<UnitSystem> {
        let mut unit_system = 0;
        // SAFETY: The private handle is live and unit_system is writable.
        status_result(unsafe {
            sys::bg_context_get_unit_system(self.raw_handle(), &mut unit_system)
        })?;
        UnitSystem::from_raw(unit_system)
    }

    pub(crate) fn raw_handle(&self) -> *mut sys::bg_context {
        self.inner.raw_handle()
    }

    pub(crate) fn lease(&self) -> Rc<ContextInner> {
        Rc::clone(&self.inner)
    }
}

#[derive(Debug, Clone, Copy)]
pub struct PositionSoa<'a> {
    pub x_angstrom: &'a [f64],
    pub y_angstrom: &'a [f64],
    pub z_angstrom: &'a [f64],
}

impl<'a> PositionSoa<'a> {
    pub const fn new(x_angstrom: &'a [f64], y_angstrom: &'a [f64], z_angstrom: &'a [f64]) -> Self {
        Self {
            x_angstrom,
            y_angstrom,
            z_angstrom,
        }
    }

    pub fn len(&self) -> usize {
        self.x_angstrom.len()
    }

    pub fn is_empty(&self) -> bool {
        self.x_angstrom.is_empty()
    }

    fn validate(&self) -> Result<usize> {
        let count = self.len();
        if self.y_angstrom.len() != count || self.z_angstrom.len() != count {
            return Err(invalid("position SoA channels must have equal lengths"));
        }
        if !finite(self.x_angstrom) || !finite(self.y_angstrom) || !finite(self.z_angstrom) {
            return Err(invalid(
                "position SoA channels must contain only finite values",
            ));
        }
        Ok(count)
    }
}

#[derive(Debug, Clone, Copy)]
pub struct VelocitySoa<'a> {
    pub x_angstrom_per_femtosecond: &'a [f64],
    pub y_angstrom_per_femtosecond: &'a [f64],
    pub z_angstrom_per_femtosecond: &'a [f64],
}

impl<'a> VelocitySoa<'a> {
    pub const fn new(
        x_angstrom_per_femtosecond: &'a [f64],
        y_angstrom_per_femtosecond: &'a [f64],
        z_angstrom_per_femtosecond: &'a [f64],
    ) -> Self {
        Self {
            x_angstrom_per_femtosecond,
            y_angstrom_per_femtosecond,
            z_angstrom_per_femtosecond,
        }
    }

    fn validate(&self, count: usize) -> Result<()> {
        if self.x_angstrom_per_femtosecond.len() != count
            || self.y_angstrom_per_femtosecond.len() != count
            || self.z_angstrom_per_femtosecond.len() != count
        {
            return Err(invalid(
                "velocity SoA channels must match the particle count",
            ));
        }
        if !finite(self.x_angstrom_per_femtosecond)
            || !finite(self.y_angstrom_per_femtosecond)
            || !finite(self.z_angstrom_per_femtosecond)
        {
            return Err(invalid(
                "velocity SoA channels must contain only finite values",
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ParticleSoa<'a> {
    pub positions: PositionSoa<'a>,
    pub velocities: Option<VelocitySoa<'a>>,
    pub mass_dalton: &'a [f64],
    pub charge_elementary: &'a [f64],
}

impl<'a> ParticleSoa<'a> {
    pub const fn new(
        positions: PositionSoa<'a>,
        mass_dalton: &'a [f64],
        charge_elementary: &'a [f64],
    ) -> Self {
        Self {
            positions,
            velocities: None,
            mass_dalton,
            charge_elementary,
        }
    }

    pub const fn with_velocities(mut self, velocities: VelocitySoa<'a>) -> Self {
        self.velocities = Some(velocities);
        self
    }

    fn validate(&self) -> Result<usize> {
        let count = self.positions.validate()?;
        if self.mass_dalton.len() != count || self.charge_elementary.len() != count {
            return Err(invalid(
                "mass and charge channels must match the particle count",
            ));
        }
        if self
            .mass_dalton
            .iter()
            .any(|mass| !mass.is_finite() || *mass <= 0.0)
        {
            return Err(invalid("masses must be finite and strictly positive"));
        }
        if !finite(self.charge_elementary) {
            return Err(invalid("charges must contain only finite values"));
        }
        if let Some(velocities) = self.velocities {
            velocities.validate(count)?;
        }
        checked_count(count)?;
        Ok(count)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct PositionSoaOwned {
    pub x_angstrom: Vec<f64>,
    pub y_angstrom: Vec<f64>,
    pub z_angstrom: Vec<f64>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct VelocitySoaOwned {
    pub x_angstrom_per_femtosecond: Vec<f64>,
    pub y_angstrom_per_femtosecond: Vec<f64>,
    pub z_angstrom_per_femtosecond: Vec<f64>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ParticleSnapshot {
    pub positions: PositionSoaOwned,
    pub velocities: VelocitySoaOwned,
    pub mass_dalton: Vec<f64>,
    pub charge_elementary: Vec<f64>,
}

impl ParticleSnapshot {
    pub fn len(&self) -> usize {
        self.mass_dalton.len()
    }

    pub fn is_empty(&self) -> bool {
        self.mass_dalton.is_empty()
    }
}

/// Owned native particle system.
///
/// The safe layer never exposes the native borrowed pointers: [`snapshot`](Self::snapshot)
/// copies every channel while `self` is immutably borrowed, and mutation
/// requires `&mut self`. The handle is also deliberately neither `Send` nor
/// `Sync`, enforcing the native external-synchronization rule.
///
/// ```compile_fail
/// use betelgeuze_runtime::System;
/// fn require_send_sync<T: Send + Sync>() {}
/// require_send_sync::<System>();
/// ```
pub struct System {
    handle: NonNull<sys::bg_system>,
    // The ABI requires external synchronization for calls on one system.
    _not_send_or_sync: PhantomData<Rc<()>>,
}

impl System {
    pub fn new(particles: ParticleSoa<'_>) -> Result<Self> {
        ensure_abi_compatibility()?;
        let count = particles.validate()?;
        let particle_count = checked_count(count)?;

        let mut raw = MaybeUninit::<sys::bg_particle_soa>::uninit();
        // SAFETY: raw points to correctly sized writable storage.
        status_result(unsafe {
            sys::bg_particle_soa_init(
                raw.as_mut_ptr(),
                std::mem::size_of::<sys::bg_particle_soa>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw = unsafe { raw.assume_init() };
        raw.particle_count = particle_count;
        raw.position_x_angstrom = channel_pointer(particles.positions.x_angstrom);
        raw.position_y_angstrom = channel_pointer(particles.positions.y_angstrom);
        raw.position_z_angstrom = channel_pointer(particles.positions.z_angstrom);
        raw.mass_dalton = channel_pointer(particles.mass_dalton);
        raw.charge_elementary = channel_pointer(particles.charge_elementary);
        if let Some(velocities) = particles.velocities {
            raw.velocity_x_angstrom_per_femtosecond =
                channel_pointer(velocities.x_angstrom_per_femtosecond);
            raw.velocity_y_angstrom_per_femtosecond =
                channel_pointer(velocities.y_angstrom_per_femtosecond);
            raw.velocity_z_angstrom_per_femtosecond =
                channel_pointer(velocities.z_angstrom_per_femtosecond);
        }

        let mut handle = ptr::null_mut();
        // SAFETY: All descriptor channels remain borrowed for the call and the
        // native contract deep-copies them before returning.
        status_result(unsafe { sys::bg_system_create(&raw, &mut handle) })?;
        let handle = NonNull::new(handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native system creation succeeded with a null handle",
            )
        })?;
        Ok(Self {
            handle,
            _not_send_or_sync: PhantomData,
        })
    }

    pub fn len(&self) -> Result<usize> {
        let mut count = 0_u64;
        // SAFETY: The private handle is live and count is writable.
        status_result(unsafe {
            sys::bg_system_get_particle_count(self.handle.as_ptr(), &mut count)
        })?;
        usize::try_from(count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "native particle count does not fit usize",
            )
        })
    }

    pub fn is_empty(&self) -> Result<bool> {
        self.len().map(|length| length == 0)
    }

    pub fn unit_system(&self) -> Result<UnitSystem> {
        let mut unit_system = 0;
        // SAFETY: The private handle is live and unit_system is writable.
        status_result(unsafe {
            sys::bg_system_get_unit_system(self.handle.as_ptr(), &mut unit_system)
        })?;
        UnitSystem::from_raw(unit_system)
    }

    pub fn snapshot(&self) -> Result<ParticleSnapshot> {
        let expected_count = self.len()?;
        let mut view = MaybeUninit::<sys::bg_particle_soa_view>::uninit();
        // SAFETY: view points to correctly sized writable storage.
        status_result(unsafe {
            sys::bg_particle_soa_view_init(
                view.as_mut_ptr(),
                std::mem::size_of::<sys::bg_particle_soa_view>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut view = unsafe { view.assume_init() };
        // SAFETY: The private system handle remains live for all copies below.
        status_result(unsafe { sys::bg_system_get_particles(self.handle.as_ptr(), &mut view) })?;
        if view.struct_size as usize != std::mem::size_of::<sys::bg_particle_soa_view>()
            || view.abi_version != sys::BG_ABI_VERSION
            || view.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
            || view.reserved0 != 0
            || view.reserved != [0; 4]
            || view.particle_count != checked_count(expected_count)?
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native system returned an invalid particle view descriptor",
            ));
        }
        UnitSystem::from_raw(view.unit_system)?;
        let count = expected_count;

        // SAFETY: Successful native views contain count readable doubles per
        // non-empty channel and remain valid while self is immutably borrowed.
        unsafe {
            Ok(ParticleSnapshot {
                positions: PositionSoaOwned {
                    x_angstrom: copy_native_channel(view.position_x_angstrom, count)?,
                    y_angstrom: copy_native_channel(view.position_y_angstrom, count)?,
                    z_angstrom: copy_native_channel(view.position_z_angstrom, count)?,
                },
                velocities: VelocitySoaOwned {
                    x_angstrom_per_femtosecond: copy_native_channel(
                        view.velocity_x_angstrom_per_femtosecond,
                        count,
                    )?,
                    y_angstrom_per_femtosecond: copy_native_channel(
                        view.velocity_y_angstrom_per_femtosecond,
                        count,
                    )?,
                    z_angstrom_per_femtosecond: copy_native_channel(
                        view.velocity_z_angstrom_per_femtosecond,
                        count,
                    )?,
                },
                mass_dalton: copy_native_channel(view.mass_dalton, count)?,
                charge_elementary: copy_native_channel(view.charge_elementary, count)?,
            })
        }
    }

    pub fn set_positions(&mut self, positions: PositionSoa<'_>) -> Result<()> {
        let count = positions.validate()?;
        if count != self.len()? {
            return Err(invalid("replacement position count must match the system"));
        }

        let mut raw = MaybeUninit::<sys::bg_position_soa>::uninit();
        // SAFETY: raw points to correctly sized writable storage.
        status_result(unsafe {
            sys::bg_position_soa_init(
                raw.as_mut_ptr(),
                std::mem::size_of::<sys::bg_position_soa>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw = unsafe { raw.assume_init() };
        raw.particle_count = checked_count(count)?;
        raw.x_angstrom = channel_pointer(positions.x_angstrom);
        raw.y_angstrom = channel_pointer(positions.y_angstrom);
        raw.z_angstrom = channel_pointer(positions.z_angstrom);
        // SAFETY: The borrowed input channels remain live for the call.
        status_result(unsafe { sys::bg_system_set_positions(self.handle.as_ptr(), &raw) })
    }
}

impl Drop for System {
    fn drop(&mut self) {
        // SAFETY: System owns this non-null handle and destroys it exactly once.
        unsafe { sys::bg_system_destroy(self.handle.as_ptr()) };
    }
}

unsafe fn copy_native_channel(pointer: *const f64, count: usize) -> Result<Vec<f64>> {
    if count == 0 {
        return Ok(Vec::new());
    }
    if pointer.is_null() || (pointer as usize) % std::mem::align_of::<f64>() != 0 {
        return Err(Error::local(
            ErrorCode::InternalError,
            "native system returned an invalid SoA channel pointer",
        ));
    }
    // SAFETY: The caller established that pointer addresses count live,
    // aligned doubles owned by the immutably borrowed native system.
    Ok(unsafe { std::slice::from_raw_parts(pointer, count) }.to_vec())
}
