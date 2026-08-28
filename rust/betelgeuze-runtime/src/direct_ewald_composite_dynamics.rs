//! Safe ownership for deterministic short-range + direct-Ewald dynamics.

use std::ffi::CStr;
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_sys as sys;

use crate::direct_ewald::{
    abi_error, ensure_direct_ewald_abi_compatibility, error_from_call, initialized_error,
    plain_status, require_direct_ewald_backend, validate_cleared_error, DirectEwaldError,
    DirectEwaldModel, DirectEwaldResult,
};
use crate::{
    checked_count, copy_native_channel, invalid, Context, DistanceConstraints, DynamicsReport,
    ErrorCode, ForceField, Integrator, ParticleSnapshot, PositionSoaOwned, SimulationOptions,
    System, VelocitySoaOwned,
};

const PROFILE_ID: &str = "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0";
const CHECKPOINT_MAGIC: &[u8; 8] = b"BGDEC001";
const CHECKPOINT_HEADER_SIZE: usize = 104;
const BOLTZMANN_KCAL_PER_MOL_KELVIN: f64 = 0.001_987_204_258_640_831_6;

/// A deep-owned composite simulation using the frozen Velocity-Verlet path.
///
/// Creation copies the system, force field, direct-Ewald model, constraints,
/// and options. The borrowed constructor inputs therefore need not outlive the
/// returned owner. The owner destroys its native handle exactly once.
///
/// Native calls require external synchronization, so this type is deliberately
/// neither `Send` nor `Sync`.
///
/// ```compile_fail
/// use betelgeuze_runtime::DirectEwaldCompositeSimulation;
/// fn require_send<T: Send>() {}
/// require_send::<DirectEwaldCompositeSimulation>();
/// ```
///
/// ```compile_fail
/// use betelgeuze_runtime::DirectEwaldCompositeSimulation;
/// fn require_sync<T: Sync>() {}
/// require_sync::<DirectEwaldCompositeSimulation>();
/// ```
///
/// ```compile_fail
/// use betelgeuze_runtime::DirectEwaldCompositeSimulation;
/// fn require_clone<T: Clone>() {}
/// require_clone::<DirectEwaldCompositeSimulation>();
/// ```
pub struct DirectEwaldCompositeSimulation {
    handle: NonNull<sys::bg_direct_ewald_composite_simulation_v1>,
    particle_count: usize,
    constraint_count: usize,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

impl DirectEwaldCompositeSimulation {
    /// Deep-copy all immutable inputs into a new Velocity-Verlet simulation.
    pub fn new(
        system: &System,
        forcefield: &ForceField,
        model: &DirectEwaldModel,
        constraints: &DistanceConstraints,
        options: SimulationOptions,
    ) -> DirectEwaldResult<Self> {
        ensure_composite_dynamics_abi_compatibility()?;
        validate_integrator(options.integrator)?;

        let particle_count = system.len().map_err(DirectEwaldError::from)?;
        if forcefield.len().map_err(DirectEwaldError::from)? != particle_count {
            return Err(local_invalid(
                "force-field atom count must match the system",
            ));
        }
        if model.len()? != particle_count {
            return Err(local_invalid(
                "direct-Ewald model atom count must match the system",
            ));
        }
        validate_options(options)?;

        let (atom_i, atom_j, distances) = validate_constraints(constraints, particle_count)?;

        let mut raw_options = MaybeUninit::<sys::bg_simulation_options_v1>::uninit();
        // SAFETY: raw_options is correctly sized writable storage.
        plain_status(unsafe {
            sys::bg_simulation_options_v1_init(
                raw_options.as_mut_ptr(),
                std::mem::size_of::<sys::bg_simulation_options_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_options = unsafe { raw_options.assume_init() };
        raw_options.integrator = sys::BG_INTEGRATOR_VELOCITY_VERLET;
        raw_options.timestep_femtoseconds = options.timestep_femtoseconds;
        raw_options.temperature_kelvin = options.temperature_kelvin;
        raw_options.friction_per_femtosecond = options.friction_per_femtosecond;
        raw_options.random_seed = options.random_seed;

        let mut raw_constraints = MaybeUninit::<sys::bg_distance_constraints_v1>::uninit();
        // SAFETY: raw_constraints is correctly sized writable storage.
        plain_status(unsafe {
            sys::bg_distance_constraints_v1_init(
                raw_constraints.as_mut_ptr(),
                std::mem::size_of::<sys::bg_distance_constraints_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_constraints = unsafe { raw_constraints.assume_init() };
        raw_constraints.constraint_count =
            checked_count(constraints.rows.len()).map_err(DirectEwaldError::from)?;
        raw_constraints.atom_i = slice_pointer(&atom_i);
        raw_constraints.atom_j = slice_pointer(&atom_j);
        raw_constraints.distance_angstrom = slice_pointer(&distances);
        raw_constraints.tolerance_angstrom = constraints.tolerance_angstrom;
        raw_constraints.velocity_tolerance_angstrom_per_femtosecond =
            constraints.velocity_tolerance_angstrom_per_femtosecond;
        raw_constraints.max_iterations = constraints.max_iterations;
        let constraints_pointer = if constraints.rows.is_empty() {
            ptr::null()
        } else {
            &raw_constraints
        };

        let mut raw_error = initialized_error()?;
        let mut raw_handle = ptr::null_mut();
        // SAFETY: All handles, descriptors, and channels remain live through
        // the call. The native owner deep-copies their semantic contents.
        let status = unsafe {
            sys::bg_direct_ewald_composite_simulation_v1_create(
                system.raw_handle(),
                forcefield.raw_handle(),
                model.raw_handle(),
                constraints_pointer,
                &raw_options,
                &mut raw_handle,
                &mut raw_error,
            )
        };
        let simulation = NonNull::new(raw_handle).map(|handle| Self {
            handle,
            particle_count,
            constraint_count: constraints.rows.len(),
            _not_send_or_sync: PhantomData,
        });
        if status != sys::BG_STATUS_OK {
            // A native contract violation that exposes a handle on failure is
            // still reclaimed exactly once before the error is propagated.
            drop(simulation);
            return Err(error_from_call(status, &raw_error));
        }
        let simulation = simulation.ok_or_else(|| {
            abi_error("composite simulation creation succeeded with a null handle")
        })?;
        validate_cleared_error(&raw_error)?;
        simulation.particle_view()?;
        Ok(simulation)
    }

    #[must_use]
    pub const fn len(&self) -> usize {
        self.particle_count
    }

    #[must_use]
    pub const fn is_empty(&self) -> bool {
        self.particle_count == 0
    }

    /// Copy every native state channel into Rust-owned storage.
    pub fn snapshot(&self) -> DirectEwaldResult<ParticleSnapshot> {
        let view = self.particle_view()?;
        let count = self.particle_count;
        // SAFETY: A successful native view contains count readable, aligned
        // doubles per channel and self remains borrowed through every copy.
        unsafe {
            Ok(ParticleSnapshot {
                positions: PositionSoaOwned {
                    x_angstrom: copy_native_channel(view.position_x_angstrom, count)
                        .map_err(DirectEwaldError::from)?,
                    y_angstrom: copy_native_channel(view.position_y_angstrom, count)
                        .map_err(DirectEwaldError::from)?,
                    z_angstrom: copy_native_channel(view.position_z_angstrom, count)
                        .map_err(DirectEwaldError::from)?,
                },
                velocities: VelocitySoaOwned {
                    x_angstrom_per_femtosecond: copy_native_channel(
                        view.velocity_x_angstrom_per_femtosecond,
                        count,
                    )
                    .map_err(DirectEwaldError::from)?,
                    y_angstrom_per_femtosecond: copy_native_channel(
                        view.velocity_y_angstrom_per_femtosecond,
                        count,
                    )
                    .map_err(DirectEwaldError::from)?,
                    z_angstrom_per_femtosecond: copy_native_channel(
                        view.velocity_z_angstrom_per_femtosecond,
                        count,
                    )
                    .map_err(DirectEwaldError::from)?,
                },
                mass_dalton: copy_native_channel(view.mass_dalton, count)
                    .map_err(DirectEwaldError::from)?,
                charge_elementary: copy_native_channel(view.charge_elementary, count)
                    .map_err(DirectEwaldError::from)?,
            })
        }
    }

    fn particle_view(&self) -> DirectEwaldResult<sys::bg_particle_soa_view> {
        let mut view = MaybeUninit::<sys::bg_particle_soa_view>::uninit();
        // SAFETY: view is correctly sized writable storage.
        plain_status(unsafe {
            sys::bg_particle_soa_view_init(
                view.as_mut_ptr(),
                std::mem::size_of::<sys::bg_particle_soa_view>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut view = unsafe { view.assume_init() };
        // SAFETY: The owned handle remains live and immutably borrowed while
        // the returned channels are copied below.
        plain_status(unsafe {
            sys::bg_direct_ewald_composite_simulation_v1_get_particles(
                self.handle.as_ptr(),
                &mut view,
            )
        })?;
        if view.struct_size as usize != std::mem::size_of::<sys::bg_particle_soa_view>()
            || view.abi_version != sys::BG_ABI_VERSION
            || view.particle_count
                != checked_count(self.particle_count).map_err(DirectEwaldError::from)?
            || view.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
            || view.reserved0 != 0
            || view.reserved != [0; 4]
        {
            return Err(abi_error(
                "native composite simulation returned an invalid particle view descriptor",
            ));
        }
        Ok(view)
    }

    pub fn absolute_step(&self) -> DirectEwaldResult<u64> {
        let mut step = 0_u64;
        // SAFETY: The owned handle is live and step is writable.
        plain_status(unsafe {
            sys::bg_direct_ewald_composite_simulation_v1_get_absolute_step(
                self.handle.as_ptr(),
                &mut step,
            )
        })?;
        Ok(step)
    }

    /// Serialize the canonical, integrity-protected `BGDEC001` restart image.
    pub fn checkpoint(&self) -> DirectEwaldResult<Vec<u8>> {
        let mut required = 0_u64;
        // SAFETY: The owned handle is live and required is writable.
        plain_status(unsafe {
            sys::bg_direct_ewald_composite_simulation_v1_checkpoint_size(
                self.handle.as_ptr(),
                &mut required,
            )
        })?;
        let length = usize::try_from(required).map_err(|_| DirectEwaldError {
            status: ErrorCode::CapacityOverflow,
            code: None,
            detail: "native composite checkpoint size exceeds usize".to_owned(),
        })?;
        if length < CHECKPOINT_HEADER_SIZE {
            return Err(abi_error(
                "native composite checkpoint size is smaller than its frozen header",
            ));
        }
        if length > isize::MAX as usize {
            return Err(DirectEwaldError {
                status: ErrorCode::CapacityOverflow,
                code: None,
                detail: "native composite checkpoint exceeds addressable Rust capacity".to_owned(),
            });
        }
        let mut bytes = Vec::new();
        bytes
            .try_reserve_exact(length)
            .map_err(|error| DirectEwaldError {
                status: ErrorCode::OutOfMemory,
                code: None,
                detail: format!("cannot allocate composite checkpoint: {error}"),
            })?;
        bytes.resize(length, 0);
        let mut written = 0_u64;
        // SAFETY: bytes exposes exactly required writable bytes.
        plain_status(unsafe {
            sys::bg_direct_ewald_composite_simulation_v1_checkpoint_write(
                self.handle.as_ptr(),
                bytes.as_mut_ptr().cast(),
                required,
                &mut written,
            )
        })?;
        if written != required {
            return Err(abi_error(
                "native composite checkpoint writer returned an inconsistent byte count",
            ));
        }
        if bytes[..CHECKPOINT_MAGIC.len()] != CHECKPOINT_MAGIC[..] {
            return Err(abi_error(
                "native composite checkpoint writer returned an invalid magic",
            ));
        }
        Ok(bytes)
    }

    /// Transactionally restore state from a canonical `BGDEC001` restart image.
    pub fn load_checkpoint(&mut self, checkpoint: &[u8]) -> DirectEwaldResult<()> {
        if checkpoint.len() < CHECKPOINT_HEADER_SIZE || !checkpoint.starts_with(CHECKPOINT_MAGIC) {
            return Err(local_invalid(
                "composite checkpoint must contain a complete BGDEC001 header",
            ));
        }
        let length = checked_count(checkpoint.len()).map_err(DirectEwaldError::from)?;
        // SAFETY: checkpoint exposes length readable bytes. The native loader
        // commits mutable state only after complete validation.
        plain_status(unsafe {
            sys::bg_direct_ewald_composite_simulation_v1_checkpoint_load(
                self.handle.as_ptr(),
                checkpoint.as_ptr().cast(),
                length,
            )
        })
    }
}

impl Drop for DirectEwaldCompositeSimulation {
    fn drop(&mut self) {
        // SAFETY: This non-clone owner holds one non-null handle and destroys
        // it exactly once. Failed constructors wrap any returned handle too.
        unsafe { sys::bg_direct_ewald_composite_simulation_v1_destroy(self.handle.as_ptr()) };
    }
}

impl Context {
    /// Integrate the composite owner on this explicitly selected CPU lane.
    pub fn integrate_direct_ewald_composite(
        &self,
        simulation: &mut DirectEwaldCompositeSimulation,
        step_count: u64,
    ) -> DirectEwaldResult<DynamicsReport> {
        self.require_direct_ewald_composite_dynamics_backend()?;
        ensure_composite_dynamics_abi_compatibility()?;

        let initial_step = simulation.absolute_step()?;
        let expected_absolute_step =
            initial_step
                .checked_add(step_count)
                .ok_or_else(|| DirectEwaldError {
                    status: ErrorCode::CapacityOverflow,
                    code: None,
                    detail: "absolute composite dynamics step would overflow uint64".to_owned(),
                })?;
        let expected_degrees_of_freedom = simulation
            .particle_count
            .checked_mul(3)
            .and_then(|value| value.checked_sub(simulation.constraint_count))
            .and_then(|value| u64::try_from(value).ok())
            .ok_or_else(|| {
                abi_error("safe composite simulation contains an invalid degree-of-freedom count")
            })?;

        let mut raw_report = MaybeUninit::<sys::bg_dynamics_report_v1>::uninit();
        // SAFETY: raw_report is correctly sized writable storage.
        plain_status(unsafe {
            sys::bg_dynamics_report_v1_init(
                raw_report.as_mut_ptr(),
                std::mem::size_of::<sys::bg_dynamics_report_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_report = unsafe { raw_report.assume_init() };
        let mut raw_error = initialized_error()?;
        // SAFETY: Both private handles remain live; the mutable borrow prevents
        // safe concurrent access, and both output descriptors are writable.
        let status = unsafe {
            sys::bg_context_integrate_direct_ewald_composite_v1(
                self.raw_handle(),
                simulation.handle.as_ptr(),
                step_count,
                &mut raw_report,
                &mut raw_error,
            )
        };
        if status != sys::BG_STATUS_OK {
            return Err(error_from_call(status, &raw_error));
        }
        validate_cleared_error(&raw_error)?;
        dynamics_report_from_raw(
            raw_report,
            step_count,
            expected_absolute_step,
            expected_degrees_of_freedom,
        )
    }

    fn require_direct_ewald_composite_dynamics_backend(&self) -> DirectEwaldResult<()> {
        // Reject AUTO/HIP from the immutable request before any native ABI or
        // simulation call. A resolved CPU lane cannot authorize fallback for
        // this explicitly selected CPU-only dynamics boundary.
        let requested = self.requested_backend();
        require_direct_ewald_backend(requested)?;
        let resolved = self.backend().map_err(DirectEwaldError::from)?;
        if resolved != requested {
            return Err(abi_error(format!(
                "native context resolved {resolved:?} after explicit {requested:?} request"
            )));
        }
        require_direct_ewald_backend(resolved)?;
        Ok(())
    }
}

/// Query and validate the frozen native composite-dynamics profile identity.
pub fn direct_ewald_composite_dynamics_profile_id() -> DirectEwaldResult<String> {
    ensure_composite_dynamics_abi_compatibility()?;
    // SAFETY: The ABI returns a process-lifetime NUL-terminated string.
    unsafe {
        let pointer = sys::bg_direct_ewald_composite_dynamics_v1_profile_id();
        if pointer.is_null() {
            return Err(abi_error("native composite-dynamics profile id is null"));
        }
        let value = CStr::from_ptr(pointer)
            .to_str()
            .map_err(|_| abi_error("native composite-dynamics profile id is not UTF-8"))?;
        if value != PROFILE_ID {
            return Err(abi_error(format!(
                "native composite-dynamics profile id {value:?} does not match {PROFILE_ID:?}"
            )));
        }
        Ok(value.to_owned())
    }
}

fn ensure_composite_dynamics_abi_compatibility() -> DirectEwaldResult<()> {
    ensure_direct_ewald_abi_compatibility()?;
    // SAFETY: Version queries take no pointers and return scalar constants.
    let observed_composite = unsafe { sys::bg_direct_ewald_composite_abi_version() };
    if observed_composite != sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION {
        return Err(abi_error(format!(
            "native composite ABI version {observed_composite} does not match required version {}",
            sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION
        )));
    }
    // SAFETY: This version query also takes no pointers.
    let observed_dynamics = unsafe { sys::bg_direct_ewald_composite_dynamics_abi_version() };
    if observed_dynamics != sys::BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION {
        return Err(abi_error(format!(
            "native composite-dynamics ABI version {observed_dynamics} does not match required version {}",
            sys::BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION
        )));
    }
    Ok(())
}

fn validate_options(options: SimulationOptions) -> DirectEwaldResult<()> {
    if !options.timestep_femtoseconds.is_finite()
        || options.timestep_femtoseconds <= 0.0
        || 0.5 * options.timestep_femtoseconds == 0.0
        || !options.temperature_kelvin.is_finite()
        || options.temperature_kelvin < 0.0
        || !options.friction_per_femtosecond.is_finite()
        || options.friction_per_femtosecond < 0.0
    {
        Err(local_invalid(
            "timestep must be positive and temperature/friction finite and non-negative",
        ))
    } else {
        Ok(())
    }
}

fn validate_integrator(integrator: Integrator) -> DirectEwaldResult<()> {
    if integrator == Integrator::VelocityVerlet {
        Ok(())
    } else {
        Err(local_invalid(
            "direct-Ewald composite dynamics supports only Velocity-Verlet",
        ))
    }
}

fn validate_constraints(
    constraints: &DistanceConstraints,
    particle_count: usize,
) -> DirectEwaldResult<(Vec<u64>, Vec<u64>, Vec<f64>)> {
    if !constraints.tolerance_angstrom.is_finite()
        || constraints.tolerance_angstrom <= 0.0
        || !constraints
            .velocity_tolerance_angstrom_per_femtosecond
            .is_finite()
        || constraints.velocity_tolerance_angstrom_per_femtosecond <= 0.0
        || constraints.max_iterations == 0
    {
        return Err(local_invalid(
            "constraint tolerances must be finite and positive and max_iterations nonzero",
        ));
    }

    let mut atom_i = Vec::with_capacity(constraints.rows.len());
    let mut atom_j = Vec::with_capacity(constraints.rows.len());
    let mut distances = Vec::with_capacity(constraints.rows.len());
    for row in &constraints.rows {
        if row.atom_i >= particle_count
            || row.atom_j >= particle_count
            || row.atom_i == row.atom_j
            || !row.distance_angstrom.is_finite()
            || row.distance_angstrom <= 0.0
        {
            return Err(local_invalid(
                "constraint atoms must be distinct and in range and distances positive",
            ));
        }
        atom_i.push(u64::try_from(row.atom_i).map_err(|_| DirectEwaldError {
            status: ErrorCode::CapacityOverflow,
            code: None,
            detail: "constraint atom index exceeds uint64".to_owned(),
        })?);
        atom_j.push(u64::try_from(row.atom_j).map_err(|_| DirectEwaldError {
            status: ErrorCode::CapacityOverflow,
            code: None,
            detail: "constraint atom index exceeds uint64".to_owned(),
        })?);
        distances.push(row.distance_angstrom);
    }
    Ok((atom_i, atom_j, distances))
}

fn dynamics_report_from_raw(
    raw: sys::bg_dynamics_report_v1,
    requested_steps: u64,
    expected_absolute_step: u64,
    expected_degrees_of_freedom: u64,
) -> DirectEwaldResult<DynamicsReport> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_dynamics_report_v1>()
        || raw.abi_version != sys::BG_ABI_VERSION
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        return Err(abi_error(
            "native composite integrator returned an invalid report descriptor",
        ));
    }
    let recomputed_total = raw.potential_kcal_per_mol + raw.kinetic_kcal_per_mol;
    let recomputed_temperature = 2.0 * raw.kinetic_kcal_per_mol
        / ((raw.degrees_of_freedom as f64) * BOLTZMANN_KCAL_PER_MOL_KELVIN);
    if raw.steps_completed != requested_steps
        || raw.absolute_step != expected_absolute_step
        || raw.degrees_of_freedom != expected_degrees_of_freedom
        || raw.degrees_of_freedom == 0
        || !raw.potential_kcal_per_mol.is_finite()
        || !raw.kinetic_kcal_per_mol.is_finite()
        || raw.kinetic_kcal_per_mol < 0.0
        || !raw.total_kcal_per_mol.is_finite()
        || raw.total_kcal_per_mol.to_bits() != recomputed_total.to_bits()
        || !raw.temperature_kelvin.is_finite()
        || raw.temperature_kelvin < 0.0
        || raw.temperature_kelvin.to_bits() != recomputed_temperature.to_bits()
    {
        return Err(abi_error(
            "native composite integrator returned a semantically invalid report",
        ));
    }
    Ok(DynamicsReport {
        steps_completed: raw.steps_completed,
        absolute_step: raw.absolute_step,
        degrees_of_freedom: raw.degrees_of_freedom,
        potential_kcal_per_mol: raw.potential_kcal_per_mol,
        kinetic_kcal_per_mol: raw.kinetic_kcal_per_mol,
        total_kcal_per_mol: raw.total_kcal_per_mol,
        temperature_kelvin: raw.temperature_kelvin,
    })
}

fn local_invalid(detail: impl Into<String>) -> DirectEwaldError {
    DirectEwaldError::from(invalid(detail))
}

fn slice_pointer<T>(values: &[T]) -> *const T {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::DistanceConstraint;

    #[test]
    fn validation_is_velocity_verlet_only_and_checks_constraints() {
        let error = validate_integrator(Integrator::LangevinBaoab).unwrap_err();
        assert_eq!(error.status, ErrorCode::InvalidArgument);

        let constraints = DistanceConstraints {
            rows: vec![DistanceConstraint {
                atom_i: 0,
                atom_j: 0,
                distance_angstrom: 1.0,
            }],
            ..DistanceConstraints::default()
        };
        let error = validate_constraints(&constraints, 1).unwrap_err();
        assert_eq!(error.status, ErrorCode::InvalidArgument);
    }

    #[test]
    fn wrapper_has_drop_glue_for_its_single_native_owner() {
        assert!(std::mem::needs_drop::<DirectEwaldCompositeSimulation>());
    }
}
