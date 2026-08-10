use core::fmt;

/// One Cartesian position in canonical angstrom units.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Position {
    pub x_angstrom: f64,
    pub y_angstrom: f64,
    pub z_angstrom: f64,
}

impl Position {
    #[must_use]
    pub const fn new(x_angstrom: f64, y_angstrom: f64, z_angstrom: f64) -> Self {
        Self {
            x_angstrom,
            y_angstrom,
            z_angstrom,
        }
    }
}

/// Per-atom Lennard-Jones and electrostatic parameters.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct AtomNonbonded {
    pub sigma_angstrom: f64,
    pub epsilon_kcal_per_mol: f64,
    pub charge_elementary: f64,
}

/// Harmonic bond term: `0.5 * k * (r - r0)^2`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HarmonicBond {
    pub atom_i: usize,
    pub atom_j: usize,
    pub equilibrium_angstrom: f64,
    pub force_constant_kcal_per_mol_angstrom2: f64,
}

/// Harmonic angle term: `0.5 * k * (theta - theta0)^2`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HarmonicAngle {
    pub atom_i: usize,
    pub atom_j: usize,
    pub atom_k: usize,
    pub equilibrium_radians: f64,
    pub force_constant_kcal_per_mol_radian2: f64,
}

/// Periodic torsion term: `amplitude * (1 + cos(n * phi - phase))`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PeriodicTorsion {
    pub atom_i: usize,
    pub atom_j: usize,
    pub atom_k: usize,
    pub atom_l: usize,
    pub periodicity: u32,
    pub phase_radians: f64,
    pub amplitude_kcal_per_mol: f64,
}

/// An unordered pair whose Lennard-Jones and Coulomb interactions are both zero.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PairExclusion {
    pub atom_i: usize,
    pub atom_j: usize,
}

/// An unordered pair with independent Lennard-Jones and Coulomb scale factors.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PairScale {
    pub atom_i: usize,
    pub atom_j: usize,
    pub lennard_jones_scale: f64,
    pub coulomb_scale: f64,
}

/// Orthorhombic periodic cell in canonical angstrom units.
///
/// Periodic displacement components use the half-open minimum-image interval
/// `[-L/2, L/2)`, implemented as `d - L * floor(d / L + 0.5)`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OrthorhombicCell {
    pub lengths_angstrom: [f64; 3],
    pub periodic_axes: [bool; 3],
}

/// Global nonbonded equation settings.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NonbondedSettings {
    pub cutoff_angstrom: f64,
    pub switch_start_angstrom: f64,
    pub dielectric: f64,
    pub screening_kappa_per_angstrom: f64,
    pub minimum_pair_distance_angstrom: f64,
}

impl Default for NonbondedSettings {
    fn default() -> Self {
        Self {
            cutoff_angstrom: 10.0,
            switch_start_angstrom: 8.0,
            dielectric: 1.0,
            screening_kappa_per_angstrom: 0.0,
            minimum_pair_distance_angstrom: 1.0e-6,
        }
    }
}

/// Complete, owned input to the independent scalar oracle.
#[derive(Clone, Debug, PartialEq)]
pub struct OracleInput {
    pub positions: Vec<Position>,
    /// Indexed exactly like `positions`; every atom has one row.
    pub atom_nonbonded: Vec<AtomNonbonded>,
    pub bonds: Vec<HarmonicBond>,
    pub angles: Vec<HarmonicAngle>,
    pub torsions: Vec<PeriodicTorsion>,
    pub exclusions: Vec<PairExclusion>,
    pub pair_scales: Vec<PairScale>,
    pub cell: Option<OrthorhombicCell>,
    pub nonbonded: NonbondedSettings,
}

impl OracleInput {
    #[must_use]
    pub fn new(positions: Vec<Position>, atom_nonbonded: Vec<AtomNonbonded>) -> Self {
        Self {
            positions,
            atom_nonbonded,
            bonds: Vec::new(),
            angles: Vec::new(),
            torsions: Vec::new(),
            exclusions: Vec::new(),
            pair_scales: Vec::new(),
            cell: None,
            nonbonded: NonbondedSettings::default(),
        }
    }
}

/// Energy components in the frozen accumulation order.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct EnergyComponents {
    pub harmonic_bond_kcal_per_mol: f64,
    pub harmonic_angle_kcal_per_mol: f64,
    pub periodic_torsion_kcal_per_mol: f64,
    pub lennard_jones_kcal_per_mol: f64,
    /// Plain Coulomb when kappa is zero; screened Coulomb otherwise.
    pub coulomb_kcal_per_mol: f64,
}

impl EnergyComponents {
    /// Sum components in the schema-frozen bond, angle, torsion, LJ, Coulomb order.
    #[must_use]
    pub fn total_kcal_per_mol(self) -> f64 {
        self.harmonic_bond_kcal_per_mol
            + self.harmonic_angle_kcal_per_mol
            + self.periodic_torsion_kcal_per_mol
            + self.lennard_jones_kcal_per_mol
            + self.coulomb_kcal_per_mol
    }
}

/// Stable categories used by callers and parity tests without parsing messages.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum OracleErrorCode {
    EmptySystem,
    AtomParameterCountMismatch,
    NonFiniteCoordinate,
    AtomIndexOutOfRange,
    RepeatedAtomIndex,
    InvalidParameter,
    DuplicateTerm,
    DuplicatePairRule,
    ConflictingPairRule,
    InvalidCell,
    CutoffViolatesMinimumImage,
    DegenerateAngle,
    DegenerateTorsion,
    PairBelowMinimumDistance,
    NonFiniteEnergy,
}

/// A validation or evaluation failure with a machine-readable category.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OracleError {
    code: OracleErrorCode,
    detail: String,
}

impl OracleError {
    pub(crate) fn new(code: OracleErrorCode, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    #[must_use]
    pub const fn code(&self) -> OracleErrorCode {
        self.code
    }

    #[must_use]
    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl fmt::Display for OracleError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?}: {}", self.code, self.detail)
    }
}

impl std::error::Error for OracleError {}
