//! Safe ownership wrappers for deterministic minimization and short dynamics.

use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_sys as sys;

use crate::{
    checked_count, copy_native_channel, ensure_abi_compatibility, invalid, status_result, Context,
    Error, ErrorCode, ForceField, ParticleSnapshot, PositionSoaOwned, Result, System, UnitSystem,
    VelocitySoaOwned,
};

/// Production integrator selected when a simulation is created.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Integrator {
    VelocityVerlet,
    LangevinBaoab,
}

impl Integrator {
    const fn as_raw(self) -> sys::bg_integrator {
        match self {
            Self::VelocityVerlet => sys::BG_INTEGRATOR_VELOCITY_VERLET,
            Self::LangevinBaoab => sys::BG_INTEGRATOR_LANGEVIN_BAOAB,
        }
    }
}

/// One mass-weighted holonomic distance constraint in canonical units.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DistanceConstraint {
    pub atom_i: usize,
    pub atom_j: usize,
    pub distance_angstrom: f64,
}

/// Canonical SHAKE/RATTLE rows and deterministic stopping bounds.
#[derive(Clone, Debug, PartialEq)]
pub struct DistanceConstraints {
    pub rows: Vec<DistanceConstraint>,
    pub tolerance_angstrom: f64,
    pub velocity_tolerance_angstrom_per_femtosecond: f64,
    pub max_iterations: u32,
}

impl Default for DistanceConstraints {
    fn default() -> Self {
        Self {
            rows: Vec::new(),
            tolerance_angstrom: 1.0e-10,
            velocity_tolerance_angstrom_per_femtosecond: 1.0e-10,
            max_iterations: 100,
        }
    }
}

/// Immutable integration configuration copied into a native simulation.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SimulationOptions {
    pub integrator: Integrator,
    pub timestep_femtoseconds: f64,
    pub temperature_kelvin: f64,
    pub friction_per_femtosecond: f64,
    pub random_seed: u64,
}

impl Default for SimulationOptions {
    fn default() -> Self {
        Self {
            integrator: Integrator::VelocityVerlet,
            timestep_femtoseconds: 1.0,
            temperature_kelvin: 300.0,
            friction_per_femtosecond: 0.001,
            random_seed: 0,
        }
    }
}

/// Bounded steepest-descent and Armijo line-search controls.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MinimizerOptions {
    pub max_iterations: u64,
    pub max_line_search_steps: u32,
    pub initial_step_angstrom2_mol_per_kcal: f64,
    pub minimum_step_angstrom2_mol_per_kcal: f64,
    pub energy_tolerance_kcal_per_mol: f64,
    pub force_tolerance_kcal_per_mol_angstrom: f64,
    pub armijo_coefficient: f64,
    pub backtrack_factor: f64,
}

impl Default for MinimizerOptions {
    fn default() -> Self {
        Self {
            max_iterations: 1_000,
            max_line_search_steps: 32,
            initial_step_angstrom2_mol_per_kcal: 1.0e-3,
            minimum_step_angstrom2_mol_per_kcal: 1.0e-12,
            energy_tolerance_kcal_per_mol: 1.0e-12,
            force_tolerance_kcal_per_mol_angstrom: 1.0e-6,
            armijo_coefficient: 1.0e-4,
            backtrack_factor: 0.5,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MinimizationReport {
    pub iterations: u64,
    pub converged: bool,
    pub initial_potential_kcal_per_mol: f64,
    pub final_potential_kcal_per_mol: f64,
    pub maximum_force_kcal_per_mol_angstrom: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DynamicsReport {
    pub steps_completed: u64,
    pub absolute_step: u64,
    pub degrees_of_freedom: u64,
    pub potential_kcal_per_mol: f64,
    pub kinetic_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub temperature_kelvin: f64,
}

/// A native-owned state, force field, constraints, integrator, and RNG counter.
///
/// Creation deep-copies both input handles, so they may be dropped immediately.
/// Calls require external synchronization, matching the C ABI contract.
pub struct Simulation {
    handle: NonNull<sys::bg_simulation>,
    particle_count: usize,
    constraint_count: usize,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

impl Simulation {
    pub fn new(
        system: &System,
        forcefield: &ForceField,
        constraints: &DistanceConstraints,
        options: SimulationOptions,
    ) -> Result<Self> {
        ensure_abi_compatibility()?;
        let particle_count = system.len()?;
        if forcefield.len()? != particle_count {
            return Err(invalid("force-field atom count must match the system"));
        }
        if !constraints.tolerance_angstrom.is_finite()
            || constraints.tolerance_angstrom <= 0.0
            || !constraints
                .velocity_tolerance_angstrom_per_femtosecond
                .is_finite()
            || constraints.velocity_tolerance_angstrom_per_femtosecond <= 0.0
            || constraints.max_iterations == 0
        {
            return Err(invalid(
                "constraint tolerances must be finite and positive and max_iterations nonzero",
            ));
        }
        if !options.timestep_femtoseconds.is_finite()
            || options.timestep_femtoseconds <= 0.0
            || 0.5 * options.timestep_femtoseconds == 0.0
            || !options.temperature_kelvin.is_finite()
            || options.temperature_kelvin < 0.0
            || !options.friction_per_femtosecond.is_finite()
            || options.friction_per_femtosecond < 0.0
        {
            return Err(invalid(
                "timestep must be positive and temperature/friction finite and non-negative",
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
                return Err(invalid(
                    "constraint atoms must be distinct and in range and distances positive",
                ));
            }
            atom_i.push(u64::try_from(row.atom_i).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "constraint atom index exceeds uint64",
                )
            })?);
            atom_j.push(u64::try_from(row.atom_j).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "constraint atom index exceeds uint64",
                )
            })?);
            distances.push(row.distance_angstrom);
        }

        let mut raw_options = MaybeUninit::<sys::bg_simulation_options_v1>::uninit();
        // SAFETY: raw_options is correctly sized writable storage.
        status_result(unsafe {
            sys::bg_simulation_options_v1_init(
                raw_options.as_mut_ptr(),
                std::mem::size_of::<sys::bg_simulation_options_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_options = unsafe { raw_options.assume_init() };
        raw_options.integrator = options.integrator.as_raw();
        raw_options.timestep_femtoseconds = options.timestep_femtoseconds;
        raw_options.temperature_kelvin = options.temperature_kelvin;
        raw_options.friction_per_femtosecond = options.friction_per_femtosecond;
        raw_options.random_seed = options.random_seed;

        let mut raw_constraints = MaybeUninit::<sys::bg_distance_constraints_v1>::uninit();
        // SAFETY: raw_constraints is correctly sized writable storage.
        status_result(unsafe {
            sys::bg_distance_constraints_v1_init(
                raw_constraints.as_mut_ptr(),
                std::mem::size_of::<sys::bg_distance_constraints_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_constraints = unsafe { raw_constraints.assume_init() };
        raw_constraints.constraint_count = checked_count(constraints.rows.len())?;
        raw_constraints.atom_i = const_slice_pointer(&atom_i);
        raw_constraints.atom_j = const_slice_pointer(&atom_j);
        raw_constraints.distance_angstrom = const_slice_pointer(&distances);
        raw_constraints.tolerance_angstrom = constraints.tolerance_angstrom;
        raw_constraints.velocity_tolerance_angstrom_per_femtosecond =
            constraints.velocity_tolerance_angstrom_per_femtosecond;
        raw_constraints.max_iterations = constraints.max_iterations;

        let constraints_pointer = if constraints.rows.is_empty() {
            ptr::null()
        } else {
            &raw_constraints
        };
        let mut handle = ptr::null_mut();
        // SAFETY: All handles/descriptors/channels remain live through the call;
        // the native simulation deep-copies their semantic contents.
        status_result(unsafe {
            sys::bg_simulation_create(
                system.handle.as_ptr(),
                forcefield.raw_handle(),
                constraints_pointer,
                &raw_options,
                &mut handle,
            )
        })?;
        let handle = NonNull::new(handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native simulation creation succeeded with a null handle",
            )
        })?;
        Ok(Self {
            handle,
            particle_count,
            constraint_count: constraints.rows.len(),
            _not_send_or_sync: PhantomData,
        })
    }

    pub fn snapshot(&self) -> Result<ParticleSnapshot> {
        let mut view = MaybeUninit::<sys::bg_particle_soa_view>::uninit();
        // SAFETY: view is correctly sized writable storage.
        status_result(unsafe {
            sys::bg_particle_soa_view_init(
                view.as_mut_ptr(),
                std::mem::size_of::<sys::bg_particle_soa_view>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut view = unsafe { view.assume_init() };
        // SAFETY: The simulation remains live and immutably borrowed while copied.
        status_result(unsafe {
            sys::bg_simulation_get_particles(self.handle.as_ptr(), &mut view)
        })?;
        if view.struct_size as usize != std::mem::size_of::<sys::bg_particle_soa_view>()
            || view.abi_version != sys::BG_ABI_VERSION
            || view.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
            || view.reserved0 != 0
            || view.reserved != [0; 4]
            || view.particle_count != checked_count(self.particle_count)?
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native simulation returned an invalid particle view descriptor",
            ));
        }
        UnitSystem::from_raw(view.unit_system)?;
        let count = self.particle_count;
        // SAFETY: A successful view contains count readable, aligned doubles
        // per channel and self remains immutably borrowed for all copies.
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

    pub fn absolute_step(&self) -> Result<u64> {
        let mut step = 0;
        // SAFETY: The private handle is live and step is writable.
        status_result(unsafe {
            sys::bg_simulation_get_absolute_step(self.handle.as_ptr(), &mut step)
        })?;
        Ok(step)
    }

    /// Serialize a canonical SHA-256 integrity-protected restart image.
    pub fn checkpoint(&self) -> Result<Vec<u8>> {
        let mut required = 0_u64;
        // SAFETY: The private handle is live and required is writable.
        status_result(unsafe {
            sys::bg_simulation_checkpoint_size(self.handle.as_ptr(), &mut required)
        })?;
        let length = usize::try_from(required).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "checkpoint size does not fit the Rust address space",
            )
        })?;
        let mut bytes = vec![0_u8; length];
        let mut written = 0_u64;
        // SAFETY: bytes exposes required writable bytes for the call.
        status_result(unsafe {
            sys::bg_simulation_checkpoint_write(
                self.handle.as_ptr(),
                bytes.as_mut_ptr().cast(),
                required,
                &mut written,
            )
        })?;
        if written != required {
            return Err(Error::local(
                ErrorCode::InternalError,
                "native checkpoint writer returned an inconsistent byte count",
            ));
        }
        Ok(bytes)
    }

    /// Transactionally restore dynamic state after digest and fingerprint checks.
    pub fn load_checkpoint(&mut self, checkpoint: &[u8]) -> Result<()> {
        if checkpoint.is_empty() {
            return Err(invalid("checkpoint must not be empty"));
        }
        let length = checked_count(checkpoint.len())?;
        // SAFETY: checkpoint exposes length readable bytes; the native load is
        // documented to commit state only after complete validation.
        status_result(unsafe {
            sys::bg_simulation_checkpoint_load(
                self.handle.as_ptr(),
                checkpoint.as_ptr().cast(),
                length,
            )
        })
    }
}

impl Drop for Simulation {
    fn drop(&mut self) {
        // SAFETY: Simulation owns this non-null handle and destroys it once.
        unsafe { sys::bg_simulation_destroy(self.handle.as_ptr()) };
    }
}

impl Context {
    pub fn minimize(
        &self,
        simulation: &mut Simulation,
        options: MinimizerOptions,
    ) -> Result<MinimizationReport> {
        let mut raw_options = MaybeUninit::<sys::bg_minimizer_options_v1>::uninit();
        // SAFETY: raw_options is correctly sized writable storage.
        status_result(unsafe {
            sys::bg_minimizer_options_v1_init(
                raw_options.as_mut_ptr(),
                std::mem::size_of::<sys::bg_minimizer_options_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_options = unsafe { raw_options.assume_init() };
        raw_options.max_iterations = options.max_iterations;
        raw_options.max_line_search_steps = options.max_line_search_steps;
        raw_options.initial_step_angstrom2_mol_per_kcal =
            options.initial_step_angstrom2_mol_per_kcal;
        raw_options.minimum_step_angstrom2_mol_per_kcal =
            options.minimum_step_angstrom2_mol_per_kcal;
        raw_options.energy_tolerance_kcal_per_mol = options.energy_tolerance_kcal_per_mol;
        raw_options.force_tolerance_kcal_per_mol_angstrom =
            options.force_tolerance_kcal_per_mol_angstrom;
        raw_options.armijo_coefficient = options.armijo_coefficient;
        raw_options.backtrack_factor = options.backtrack_factor;

        let mut raw_report = MaybeUninit::<sys::bg_minimization_report_v1>::uninit();
        // SAFETY: raw_report is correctly sized writable storage.
        status_result(unsafe {
            sys::bg_minimization_report_v1_init(
                raw_report.as_mut_ptr(),
                std::mem::size_of::<sys::bg_minimization_report_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_report = unsafe { raw_report.assume_init() };
        // SAFETY: Both private handles remain live and exclusively borrowing
        // simulation prevents safe concurrent access to its mutable state.
        status_result(unsafe {
            sys::bg_context_minimize(
                self.handle.as_ptr(),
                simulation.handle.as_ptr(),
                &raw_options,
                &mut raw_report,
            )
        })?;
        minimization_report_from_raw(raw_report, options.max_iterations)
    }

    pub fn integrate(
        &self,
        simulation: &mut Simulation,
        step_count: u64,
    ) -> Result<DynamicsReport> {
        let initial_step = simulation.absolute_step()?;
        let expected_absolute_step = initial_step.checked_add(step_count).ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "absolute dynamics step would overflow uint64",
            )
        })?;
        let expected_degrees_of_freedom = simulation
            .particle_count
            .checked_mul(3)
            .and_then(|value| value.checked_sub(simulation.constraint_count))
            .and_then(|value| u64::try_from(value).ok())
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::InternalError,
                    "safe simulation contains an invalid degree-of-freedom count",
                )
            })?;
        let mut raw_report = MaybeUninit::<sys::bg_dynamics_report_v1>::uninit();
        // SAFETY: raw_report is correctly sized writable storage.
        status_result(unsafe {
            sys::bg_dynamics_report_v1_init(
                raw_report.as_mut_ptr(),
                std::mem::size_of::<sys::bg_dynamics_report_v1>(),
                sys::BG_ABI_VERSION,
            )
        })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_report = unsafe { raw_report.assume_init() };
        // SAFETY: Both private handles remain live and simulation is exclusively borrowed.
        status_result(unsafe {
            sys::bg_context_integrate(
                self.handle.as_ptr(),
                simulation.handle.as_ptr(),
                step_count,
                &mut raw_report,
            )
        })?;
        dynamics_report_from_raw(
            raw_report,
            step_count,
            expected_absolute_step,
            expected_degrees_of_freedom,
        )
    }
}

fn minimization_report_from_raw(
    raw: sys::bg_minimization_report_v1,
    maximum_iterations: u64,
) -> Result<MinimizationReport> {
    validate_report_header(
        raw.struct_size,
        std::mem::size_of::<sys::bg_minimization_report_v1>(),
        raw.abi_version,
        raw.unit_system,
        raw.reserved0,
        &raw.reserved,
    )?;
    let converged = match raw.converged {
        0 => false,
        1 => true,
        value => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native minimizer returned non-boolean converged value {value}"),
            ));
        }
    };
    if raw.reserved1 != 0 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native minimizer report returned nonzero reserved data",
        ));
    }
    if raw.iterations > maximum_iterations
        || (!converged && raw.iterations != maximum_iterations)
        || !raw.initial_potential_kcal_per_mol.is_finite()
        || !raw.final_potential_kcal_per_mol.is_finite()
        || !raw.maximum_force_kcal_per_mol_angstrom.is_finite()
        || raw.maximum_force_kcal_per_mol_angstrom < 0.0
        || raw.final_potential_kcal_per_mol > raw.initial_potential_kcal_per_mol
    {
        return Err(Error::local(
            ErrorCode::InternalError,
            "native minimizer returned a semantically invalid report",
        ));
    }
    Ok(MinimizationReport {
        iterations: raw.iterations,
        converged,
        initial_potential_kcal_per_mol: raw.initial_potential_kcal_per_mol,
        final_potential_kcal_per_mol: raw.final_potential_kcal_per_mol,
        maximum_force_kcal_per_mol_angstrom: raw.maximum_force_kcal_per_mol_angstrom,
    })
}

fn dynamics_report_from_raw(
    raw: sys::bg_dynamics_report_v1,
    requested_steps: u64,
    expected_absolute_step: u64,
    expected_degrees_of_freedom: u64,
) -> Result<DynamicsReport> {
    validate_report_header(
        raw.struct_size,
        std::mem::size_of::<sys::bg_dynamics_report_v1>(),
        raw.abi_version,
        raw.unit_system,
        raw.reserved0,
        &raw.reserved,
    )?;
    let recomputed_total = raw.potential_kcal_per_mol + raw.kinetic_kcal_per_mol;
    let recomputed_temperature = 2.0 * raw.kinetic_kcal_per_mol
        / ((raw.degrees_of_freedom as f64) * 0.001_987_204_258_640_831_6);
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
        return Err(Error::local(
            ErrorCode::InternalError,
            "native integrator returned a semantically invalid report",
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

fn validate_report_header(
    observed_size: u32,
    expected_size: usize,
    version: u32,
    units: sys::bg_unit_system,
    reserved0: u32,
    reserved: &[u64; 4],
) -> Result<()> {
    if observed_size as usize != expected_size
        || version != sys::BG_ABI_VERSION
        || units != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || reserved0 != 0
        || *reserved != [0; 4]
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native dynamics returned an invalid report descriptor",
        ));
    }
    Ok(())
}

fn const_slice_pointer<T>(values: &[T]) -> *const T {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}
