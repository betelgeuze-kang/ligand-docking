use core::fmt;

/// Stable error categories for callers and parity tests.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum DynamicsErrorCode {
    EmptySystem,
    ParticleCountMismatch,
    InvalidMass,
    NonFiniteState,
    InvalidConstraint,
    DuplicateConstraint,
    InvalidCell,
    InvalidConfiguration,
    ForceProvider,
    NonFiniteEnergy,
    NonFiniteForce,
    ConstraintDegenerate,
    ConstraintNotConverged,
    LineSearchFailed,
    StepOverflow,
    CheckpointMalformed,
    CheckpointVersion,
    CheckpointChecksum,
    CheckpointSystemMismatch,
}

/// A validation or evaluation error with a machine-readable category.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DynamicsError {
    code: DynamicsErrorCode,
    detail: String,
}

impl DynamicsError {
    #[must_use]
    pub fn new(code: DynamicsErrorCode, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    /// Construct an error returned by a user-supplied force provider.
    #[must_use]
    pub fn force_provider(detail: impl Into<String>) -> Self {
        Self::new(DynamicsErrorCode::ForceProvider, detail)
    }

    #[must_use]
    pub const fn code(&self) -> DynamicsErrorCode {
        self.code
    }

    #[must_use]
    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl fmt::Display for DynamicsError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?}: {}", self.code, self.detail)
    }
}

impl std::error::Error for DynamicsError {}

/// Scalar potential-energy and force callback.
///
/// `positions_angstrom` and `forces_kcal_per_mol_angstrom` have identical
/// lengths. Implementations must overwrite every force component and return
/// potential energy in kcal/mol. The oracle clears the output before the call
/// and rejects any non-finite result.
pub trait ForceProvider {
    fn energy_and_forces(
        &mut self,
        positions_angstrom: &[[f64; 3]],
        forces_kcal_per_mol_angstrom: &mut [[f64; 3]],
    ) -> Result<f64, DynamicsError>;
}

impl<F> ForceProvider for F
where
    F: FnMut(&[[f64; 3]], &mut [[f64; 3]]) -> Result<f64, DynamicsError>,
{
    fn energy_and_forces(
        &mut self,
        positions_angstrom: &[[f64; 3]],
        forces_kcal_per_mol_angstrom: &mut [[f64; 3]],
    ) -> Result<f64, DynamicsError> {
        self(positions_angstrom, forces_kcal_per_mol_angstrom)
    }
}

/// A mass-weighted holonomic distance constraint.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DistanceConstraint {
    pub atom_i: usize,
    pub atom_j: usize,
    pub distance_angstrom: f64,
}

/// Orthorhombic box used only for minimum-image constraint displacement.
///
/// Positions remain unwrapped. Periodic axes use the half-open interval
/// `[-L/2, L/2)` via `d - L * floor(d/L + 0.5)`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OrthorhombicCell {
    pub lengths_angstrom: [f64; 3],
    pub periodic_axes: [bool; 3],
}

/// Immutable particle masses, canonicalized constraints, and optional cell.
#[derive(Clone, Debug, PartialEq)]
pub struct System {
    masses_dalton: Vec<f64>,
    constraints: Vec<DistanceConstraint>,
    cell: Option<OrthorhombicCell>,
}

impl System {
    pub fn new(
        masses_dalton: Vec<f64>,
        mut constraints: Vec<DistanceConstraint>,
        cell: Option<OrthorhombicCell>,
    ) -> Result<Self, DynamicsError> {
        if masses_dalton.is_empty() {
            return Err(DynamicsError::new(
                DynamicsErrorCode::EmptySystem,
                "a dynamics system must contain at least one particle",
            ));
        }
        for (atom, mass) in masses_dalton.iter().copied().enumerate() {
            if !mass.is_finite() || mass <= 0.0 {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::InvalidMass,
                    format!("mass[{atom}] must be finite and positive"),
                ));
            }
        }
        if let Some(value) = cell {
            for (axis, length) in value.lengths_angstrom.iter().copied().enumerate() {
                if !length.is_finite() || length <= 0.0 {
                    return Err(DynamicsError::new(
                        DynamicsErrorCode::InvalidCell,
                        format!("cell length[{axis}] must be finite and positive"),
                    ));
                }
            }
        }

        for constraint in &mut constraints {
            if constraint.atom_i >= masses_dalton.len()
                || constraint.atom_j >= masses_dalton.len()
                || constraint.atom_i == constraint.atom_j
                || !constraint.distance_angstrom.is_finite()
                || constraint.distance_angstrom <= 0.0
            {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::InvalidConstraint,
                    "constraint indices must be distinct and in range, and distance must be finite and positive",
                ));
            }
            if constraint.atom_j < constraint.atom_i {
                core::mem::swap(&mut constraint.atom_i, &mut constraint.atom_j);
            }
            if let Some(box_) = cell {
                for axis in 0..3 {
                    if box_.periodic_axes[axis]
                        && constraint.distance_angstrom >= 0.5 * box_.lengths_angstrom[axis]
                    {
                        return Err(DynamicsError::new(
                            DynamicsErrorCode::InvalidConstraint,
                            format!(
                                "constraint distance must be smaller than half periodic cell length[{axis}]"
                            ),
                        ));
                    }
                }
            }
        }
        constraints.sort_by_key(|constraint| (constraint.atom_i, constraint.atom_j));
        for pair in constraints.windows(2) {
            if pair[0].atom_i == pair[1].atom_i && pair[0].atom_j == pair[1].atom_j {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::DuplicateConstraint,
                    format!(
                        "constraint pair ({}, {}) is duplicated",
                        pair[0].atom_i, pair[0].atom_j
                    ),
                ));
            }
        }
        let cartesian_dof = masses_dalton.len().checked_mul(3).ok_or_else(|| {
            DynamicsError::new(
                DynamicsErrorCode::InvalidConstraint,
                "Cartesian degree-of-freedom count overflowed",
            )
        })?;
        if constraints.len() >= cartesian_dof {
            return Err(DynamicsError::new(
                DynamicsErrorCode::InvalidConstraint,
                "constraints leave no positive degree-of-freedom count",
            ));
        }

        Ok(Self {
            masses_dalton,
            constraints,
            cell,
        })
    }

    #[must_use]
    pub fn particle_count(&self) -> usize {
        self.masses_dalton.len()
    }

    #[must_use]
    pub fn masses_dalton(&self) -> &[f64] {
        &self.masses_dalton
    }

    /// Constraints sorted lexicographically after normalizing every pair to
    /// `atom_i < atom_j`.
    #[must_use]
    pub fn constraints(&self) -> &[DistanceConstraint] {
        &self.constraints
    }

    #[must_use]
    pub const fn cell(&self) -> Option<OrthorhombicCell> {
        self.cell
    }

    pub(crate) fn validate_state(&self, state: &State) -> Result<(), DynamicsError> {
        if state.positions_angstrom.len() != self.particle_count()
            || state.velocities_angstrom_per_fs.len() != self.particle_count()
        {
            return Err(DynamicsError::new(
                DynamicsErrorCode::ParticleCountMismatch,
                format!(
                    "system has {} particles but state has {} positions and {} velocities",
                    self.particle_count(),
                    state.positions_angstrom.len(),
                    state.velocities_angstrom_per_fs.len()
                ),
            ));
        }
        validate_vectors(&state.positions_angstrom, "position")?;
        validate_vectors(&state.velocities_angstrom_per_fs, "velocity")?;
        crate::constraints::validate_constraint_independence(self, &state.positions_angstrom)
    }
}

pub(crate) fn validate_vectors(values: &[[f64; 3]], label: &str) -> Result<(), DynamicsError> {
    for (atom, vector) in values.iter().enumerate() {
        for (axis, component) in vector.iter().copied().enumerate() {
            if !component.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteState,
                    format!("{label}[{atom}][{axis}] must be finite"),
                ));
            }
        }
    }
    Ok(())
}

/// Owned positions, velocities, and trajectory step.
#[derive(Clone, Debug, PartialEq)]
pub struct State {
    pub positions_angstrom: Vec<[f64; 3]>,
    pub velocities_angstrom_per_fs: Vec<[f64; 3]>,
    /// Absolute completed integration step, used directly by counter RNG.
    pub absolute_step: u64,
}

impl State {
    #[must_use]
    pub fn new(
        positions_angstrom: Vec<[f64; 3]>,
        velocities_angstrom_per_fs: Vec<[f64; 3]>,
    ) -> Self {
        Self {
            positions_angstrom,
            velocities_angstrom_per_fs,
            absolute_step: 0,
        }
    }
}

/// Deterministic SHAKE/RATTLE stopping bounds.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ConstraintConfig {
    pub position_tolerance_angstrom: f64,
    pub velocity_tolerance_angstrom_per_fs: f64,
    pub max_iterations: u32,
}

impl Default for ConstraintConfig {
    fn default() -> Self {
        Self {
            position_tolerance_angstrom: 1.0e-12,
            velocity_tolerance_angstrom_per_fs: 1.0e-12,
            max_iterations: 100,
        }
    }
}

impl ConstraintConfig {
    pub(crate) fn validate(self) -> Result<(), DynamicsError> {
        if !self.position_tolerance_angstrom.is_finite()
            || self.position_tolerance_angstrom <= 0.0
            || !self.velocity_tolerance_angstrom_per_fs.is_finite()
            || self.velocity_tolerance_angstrom_per_fs <= 0.0
            || self.max_iterations == 0
        {
            return Err(DynamicsError::new(
                DynamicsErrorCode::InvalidConfiguration,
                "constraint tolerances must be finite and positive and max_iterations must be nonzero",
            ));
        }
        Ok(())
    }
}

/// Bounded steepest-descent and Armijo parameters.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MinimizationConfig {
    pub max_iterations: u64,
    pub force_tolerance_kcal_per_mol_angstrom: f64,
    /// A value of zero disables the accepted-step energy-change criterion.
    pub energy_tolerance_kcal_per_mol: f64,
    pub initial_step_angstrom2_mol_per_kcal: f64,
    pub minimum_step_angstrom2_mol_per_kcal: f64,
    pub armijo_c1: f64,
    pub backtrack_factor: f64,
    pub max_backtracks: u32,
    pub constraints: ConstraintConfig,
}

impl Default for MinimizationConfig {
    fn default() -> Self {
        Self {
            max_iterations: 1_000,
            force_tolerance_kcal_per_mol_angstrom: 1.0e-6,
            energy_tolerance_kcal_per_mol: 1.0e-12,
            initial_step_angstrom2_mol_per_kcal: 1.0e-3,
            minimum_step_angstrom2_mol_per_kcal: 1.0e-12,
            armijo_c1: 1.0e-4,
            backtrack_factor: 0.5,
            max_backtracks: 32,
            constraints: ConstraintConfig::default(),
        }
    }
}

impl MinimizationConfig {
    pub(crate) fn validate(self) -> Result<(), DynamicsError> {
        self.constraints.validate()?;
        if self.max_iterations == 0
            || !self.force_tolerance_kcal_per_mol_angstrom.is_finite()
            || self.force_tolerance_kcal_per_mol_angstrom < 0.0
            || !self.energy_tolerance_kcal_per_mol.is_finite()
            || self.energy_tolerance_kcal_per_mol < 0.0
            || !self.initial_step_angstrom2_mol_per_kcal.is_finite()
            || self.initial_step_angstrom2_mol_per_kcal <= 0.0
            || !self.minimum_step_angstrom2_mol_per_kcal.is_finite()
            || self.minimum_step_angstrom2_mol_per_kcal <= 0.0
            || self.minimum_step_angstrom2_mol_per_kcal > self.initial_step_angstrom2_mol_per_kcal
            || !self.armijo_c1.is_finite()
            || self.armijo_c1 <= 0.0
            || self.armijo_c1 >= 1.0
            || !self.backtrack_factor.is_finite()
            || self.backtrack_factor <= 0.0
            || self.backtrack_factor >= 1.0
            || self.max_backtracks == 0
        {
            return Err(DynamicsError::new(
                DynamicsErrorCode::InvalidConfiguration,
                "invalid steepest-descent or Armijo configuration",
            ));
        }
        Ok(())
    }
}

/// Velocity-Verlet integration parameters.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct VerletConfig {
    pub timestep_fs: f64,
    pub steps: u64,
    pub constraints: ConstraintConfig,
}

impl VerletConfig {
    pub(crate) fn validate(self) -> Result<(), DynamicsError> {
        self.constraints.validate()?;
        if !self.timestep_fs.is_finite() || self.timestep_fs <= 0.0 || 0.5 * self.timestep_fs == 0.0
        {
            return Err(DynamicsError::new(
                DynamicsErrorCode::InvalidConfiguration,
                "Verlet timestep must be finite and positive",
            ));
        }
        Ok(())
    }
}

/// BAOAB Langevin integration parameters.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LangevinConfig {
    pub timestep_fs: f64,
    pub steps: u64,
    pub temperature_kelvin: f64,
    pub friction_per_fs: f64,
    pub seed: u64,
    pub constraints: ConstraintConfig,
}

impl LangevinConfig {
    pub(crate) fn validate(self) -> Result<(), DynamicsError> {
        self.constraints.validate()?;
        if !self.timestep_fs.is_finite()
            || self.timestep_fs <= 0.0
            || 0.5 * self.timestep_fs == 0.0
            || !self.temperature_kelvin.is_finite()
            || self.temperature_kelvin < 0.0
            || !self.friction_per_fs.is_finite()
            || self.friction_per_fs < 0.0
        {
            return Err(DynamicsError::new(
                DynamicsErrorCode::InvalidConfiguration,
                "BAOAB timestep must be positive and temperature/friction must be finite and nonnegative",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MinimizationReport {
    pub iterations: u64,
    pub converged: bool,
    pub initial_potential_kcal_per_mol: f64,
    pub final_potential_kcal_per_mol: f64,
    pub final_max_force_kcal_per_mol_angstrom: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct IntegrationReport {
    pub steps: u64,
    pub absolute_step: u64,
    pub initial_potential_kcal_per_mol: f64,
    pub final_potential_kcal_per_mol: f64,
    pub initial_kinetic_kcal_per_mol: f64,
    pub final_kinetic_kcal_per_mol: f64,
}
