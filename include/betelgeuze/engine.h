#ifndef BETELGEUZE_ENGINE_H
#define BETELGEUZE_ENGINE_H

/*
 * Betelgeuze native compute ABI v1.
 *
 * This header is C11-compatible.  It deliberately exposes only fixed-width
 * scalars, versioned plain-old-data descriptors, and opaque handles.  C++
 * types and exceptions never cross this boundary.
 *
 * Canonical unit system (BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL):
 *   length       angstrom
 *   energy       kcal/mol
 *   force        kcal/(mol*angstrom)
 *   charge       elementary charge
 *   mass         dalton
 *   angle        radian
 *   time         femtosecond
 *   velocity     angstrom/femtosecond
 *   temperature  kelvin
 *
 * Callers must convert at adapters before entering this ABI.  Native entry
 * points reject any other unit-system identifier.
 *
 * ABI evolution rule: every descriptor layout and initializer write-size in
 * ABI/SOVERSION 1 is frozen.  ABI v1 additions must consume reserved fields or
 * introduce a new, version-suffixed descriptor and initializer; they must not
 * enlarge the structs below.  A new major layout requires a new ABI/SOVERSION.
 */

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#  if defined(BG_ENGINE_BUILD_SHARED)
#    define BG_API __declspec(dllexport)
#  elif defined(BG_ENGINE_USE_SHARED)
#    define BG_API __declspec(dllimport)
#  else
#    define BG_API
#  endif
#  define BG_CALL __cdecl
#elif defined(__GNUC__) || defined(__clang__)
#  define BG_API __attribute__((visibility("default")))
#  define BG_CALL
#else
#  define BG_API
#  define BG_CALL
#endif

#if defined(__cplusplus)
#  define BG_NOEXCEPT noexcept
extern "C" {
#else
#  define BG_NOEXCEPT
#endif

#define BG_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_ABI_VERSION_MINOR UINT32_C(6)
#define BG_ABI_VERSION UINT32_C(1)

#define BG_CANONICAL_LENGTH_UNIT "angstrom"
#define BG_CANONICAL_ENERGY_UNIT "kcal/mol"
#define BG_CANONICAL_FORCE_UNIT "kcal/(mol*angstrom)"
#define BG_CANONICAL_CHARGE_UNIT "elementary_charge"
#define BG_CANONICAL_MASS_UNIT "dalton"
#define BG_CANONICAL_ANGLE_UNIT "radian"
#define BG_CANONICAL_TIME_UNIT "femtosecond"
#define BG_CANONICAL_VELOCITY_UNIT "angstrom/femtosecond"
#define BG_CANONICAL_TEMPERATURE_UNIT "kelvin"

/* q1*q2/r electrostatic factor for the canonical unit system. */
#define BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2 (332.063713299)

typedef int32_t bg_status;
enum {
    BG_STATUS_OK = 0,
    BG_STATUS_INVALID_ARGUMENT = 1,
    BG_STATUS_ABI_MISMATCH = 2,
    BG_STATUS_UNSUPPORTED_BACKEND = 3,
    BG_STATUS_BACKEND_UNAVAILABLE = 4,
    BG_STATUS_OUT_OF_MEMORY = 5,
    BG_STATUS_CAPACITY_OVERFLOW = 6,
    BG_STATUS_BUFFER_TOO_SMALL = 7,
    BG_STATUS_BACKEND_ERROR = 8,
    BG_STATUS_INTERNAL_ERROR = 9,
    BG_STATUS_NUMERICAL_ERROR = 10
};

typedef int32_t bg_backend;
enum {
    BG_BACKEND_AUTO = 0,
    BG_BACKEND_CPP_CPU_REFERENCE = 1,
    /* ABI v1.0-v1.3 exposed backend value 2 as the parallel HIP lane. */
    BG_BACKEND_HIP_FAST = 2,
    BG_BACKEND_RUST_CPU = 3,
    BG_BACKEND_HIP_SAFE = 4,
    /* Frozen legacy aliases. New product code must use an explicit lane. */
    BG_BACKEND_CPU = BG_BACKEND_CPP_CPU_REFERENCE,
    BG_BACKEND_HIP = BG_BACKEND_HIP_FAST
};

/* python_reference remains outside the native ABI and is verifier-only. */

typedef int32_t bg_unit_system;
enum {
    BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL = 1
};

typedef int32_t bg_integrator;
enum {
    BG_INTEGRATOR_VELOCITY_VERLET = 1,
    BG_INTEGRATOR_LANGEVIN_BAOAB = 2
};

/* Frozen Engine V2 ScorerV1 batch dimensions and row semantics. */
#define BG_DOCKING_FIXED64_CANDIDATE_COUNT UINT32_C(64)
#define BG_DOCKING_SCORER_V1_TERM_COUNT UINT32_C(8)

typedef int32_t bg_docking_scorer_v1_candidate_state;
enum {
    BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE = 0,
    BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE = 1
};

typedef int32_t bg_docking_scorer_v1_row_status;
enum {
    BG_DOCKING_SCORER_V1_ROW_SCORED = 1,
    BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE = 2
};

typedef int32_t bg_docking_scorer_v1_failure;
enum {
    BG_DOCKING_SCORER_V1_FAILURE_NONE = 0,
    BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED = 1,
    BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES = 2,
    BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY = 3,
    BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY = 4,
    BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR = 5,
    BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE = 6
};

/* Frozen Engine V2 pose-validity candidate, row, and check semantics. */
#define BG_DOCKING_POSE_VALIDITY_CHECK_COUNT UINT32_C(8)

typedef int32_t bg_docking_pose_validity_candidate_state;
enum {
    BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE = 0,
    BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE = 1
};

typedef int32_t bg_docking_pose_validity_row_status;
enum {
    BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED = 1,
    BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE = 2,
    BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE = 3
};

typedef int32_t bg_docking_pose_validity_failure;
enum {
    BG_DOCKING_POSE_VALIDITY_FAILURE_NONE = 0,
    BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER = 1,
    BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES = 2,
    BG_DOCKING_POSE_VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY = 3,
    BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY = 4,
    BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY = 5,
    BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY = 6,
    BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT = 7
};

typedef uint32_t bg_docking_pose_validity_check_mask;
enum {
    BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION = UINT32_C(1) << 0,
    BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS = UINT32_C(1) << 1,
    BG_DOCKING_POSE_VALIDITY_CHECK_LIGAND_SELF_CLASH = UINT32_C(1) << 2,
    BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH = UINT32_C(1) << 3,
    BG_DOCKING_POSE_VALIDITY_CHECK_CHIRALITY = UINT32_C(1) << 4,
    BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET = UINT32_C(1) << 5,
    BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW = UINT32_C(1) << 6,
    BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW = UINT32_C(1) << 7,
    BG_DOCKING_POSE_VALIDITY_CHECK_ALL = UINT32_C(0xff)
};

/* Incomplete declarations are the only public handle representation. */
typedef struct bg_context bg_context;
typedef struct bg_system bg_system;
typedef struct bg_forcefield bg_forcefield;
typedef struct bg_simulation bg_simulation;
typedef struct bg_docking_scorer_v1 bg_docking_scorer_v1;
typedef struct bg_docking_pose_validity_v1 bg_docking_pose_validity_v1;

typedef struct bg_context_options {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_backend backend;
    bg_unit_system unit_system;
    int32_t device_ordinal;
    uint32_t reserved0;
    uint64_t flags;
    uint64_t reserved[4];
} bg_context_options;

/*
 * Input-only host SoA.  All non-null channels are deep-copied by
 * bg_system_create.  For particle_count > 0, positions, mass, and charge are
 * required.  Velocity channels must be either all null (native zero fill) or
 * all non-null.  Every supplied scalar must be finite, masses must be strictly
 * positive, and non-null channels must satisfy the platform alignment of
 * double.  For particle_count == 0 every data pointer may be null.
 */
typedef struct bg_particle_soa {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t particle_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    const double *position_x_angstrom;
    const double *position_y_angstrom;
    const double *position_z_angstrom;
    const double *velocity_x_angstrom_per_femtosecond;
    const double *velocity_y_angstrom_per_femtosecond;
    const double *velocity_z_angstrom_per_femtosecond;
    const double *mass_dalton;
    const double *charge_elementary;
    uint64_t reserved[4];
} bg_particle_soa;

/*
 * Read-only borrowed host view into a system-owned SoA.  Pointers remain valid
 * until the system is destroyed or a future ABI operation explicitly states
 * that it invalidates views.  Calls on one system must be externally
 * synchronized.  Access through borrowed pointers must also be synchronized
 * against mutating calls and destruction; the phrase "observe new values"
 * below never authorizes a concurrent read/write data race.  Empty views may
 * contain null data pointers.
 */
typedef struct bg_particle_soa_view {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t particle_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    const double *position_x_angstrom;
    const double *position_y_angstrom;
    const double *position_z_angstrom;
    const double *velocity_x_angstrom_per_femtosecond;
    const double *velocity_y_angstrom_per_femtosecond;
    const double *velocity_z_angstrom_per_femtosecond;
    const double *mass_dalton;
    const double *charge_elementary;
    uint64_t reserved[4];
} bg_particle_soa_view;

/*
 * Input-only host SoA used for transactional position replacement.  For a
 * non-empty system all channels are required, finite, and aligned for double.
 */
typedef struct bg_position_soa {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t particle_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    const double *x_angstrom;
    const double *y_angstrom;
    const double *z_angstrom;
    uint64_t reserved[4];
} bg_position_soa;

enum {
    BG_PERIODIC_AXIS_X = UINT32_C(1) << 0,
    BG_PERIODIC_AXIS_Y = UINT32_C(1) << 1,
    BG_PERIODIC_AXIS_Z = UINT32_C(1) << 2,
    BG_PERIODIC_AXES_ALL = BG_PERIODIC_AXIS_X | BG_PERIODIC_AXIS_Y |
                           BG_PERIODIC_AXIS_Z
};

/*
 * Input-only force-field SoA, frozen as ABI v1.  Every channel associated
 * with a non-zero count is required, naturally aligned, and deep-copied by
 * bg_forcefield_create.  Atom indices are zero-based uint64 values.
 *
 * Bond:     0.5*k*(r-r0)^2
 * Angle:    0.5*k*(theta-theta0)^2, with the normalized dot product clamped
 *           to [-1+1e-12,1-1e-12] before acos.
 * Torsion:  amplitude*(1+cos(periodicity*phi-phase)), where b0=ri-rj,
 *           b1=rk-rj, b2=rl-rk, axis=b1/|b1|, v and w are b0 and b2
 *           projected perpendicular to axis, and
 *           phi=atan2(dot(cross(axis,v),w),dot(v,w)) in [-pi,pi].
 * LJ mixing uses sigma=(sigma_i+sigma_j)/2 and
 * epsilon=sqrt(epsilon_i*epsilon_j), followed by
 * 4*epsilon*((sigma/r)^12-(sigma/r)^6).  Coulomb is
 * C*qi*qj*exp(-kappa*r)/(dielectric*r), where qi/qj come from the associated
 * bg_system charge_elementary channel.  Both components are multiplied by
 * S=1 below switch_start, S=0 at and above cutoff, and inside the switch
 * interval S=1-10*x^3+15*x^4-6*x^5 for
 * x=(r-switch_start)/(cutoff-switch_start).  Pairs at exactly cutoff are
 * evaluated and multiplied by zero; only r>cutoff is skipped.
 * Explicit exclusions suppress both nonbonded components; topology does not
 * imply exclusions.  Pair scales must lie in [0,1].
 *
 * Orthorhombic minimum images use d-L*floor(d/L+0.5) for every bonded and
 * nonbonded displacement on axes selected by periodic_axes_mask.  When any
 * axis is periodic all three cell lengths must
 * be finite and positive, and cutoff must be strictly below half every
 * periodic length.  With no periodic axes, cell lengths must be either all
 * zero (no cell) or all finite and positive (a nonperiodic cell).
 *
 * Exclusion lookup precedes the minimum-distance check, so a coincident
 * excluded pair has exactly zero nonbonded energy.  Every other pair below
 * minimum_pair_distance_angstrom is rejected before cutoff handling.
 */
typedef struct bg_forcefield_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t atom_count;
    bg_unit_system unit_system;
    uint32_t periodic_axes_mask;

    const double *sigma_angstrom;
    const double *epsilon_kcal_per_mol;

    uint64_t bond_count;
    const uint64_t *bond_atom_i;
    const uint64_t *bond_atom_j;
    const double *bond_equilibrium_angstrom;
    const double *bond_force_constant_kcal_per_mol_angstrom2;

    uint64_t angle_count;
    const uint64_t *angle_atom_i;
    const uint64_t *angle_atom_j;
    const uint64_t *angle_atom_k;
    const double *angle_equilibrium_radians;
    const double *angle_force_constant_kcal_per_mol_radian2;

    uint64_t torsion_count;
    const uint64_t *torsion_atom_i;
    const uint64_t *torsion_atom_j;
    const uint64_t *torsion_atom_k;
    const uint64_t *torsion_atom_l;
    const uint32_t *torsion_periodicity;
    const double *torsion_phase_radians;
    const double *torsion_amplitude_kcal_per_mol;

    uint64_t exclusion_count;
    const uint64_t *exclusion_atom_i;
    const uint64_t *exclusion_atom_j;

    uint64_t pair_scale_count;
    const uint64_t *pair_scale_atom_i;
    const uint64_t *pair_scale_atom_j;
    const double *pair_scale_lennard_jones;
    const double *pair_scale_coulomb;

    double cell_lengths_angstrom[3];
    double cutoff_angstrom;
    double switch_start_angstrom;
    double dielectric;
    double screening_kappa_per_angstrom;
    double minimum_pair_distance_angstrom;
    uint64_t reserved[4];
} bg_forcefield_soa_v1;

/* Caller-owned force output.  capacity and all channels are input fields;
 * particle_count is committed on success.  A null descriptor requests energy
 * only.  For the first particle_count elements, x/y/z channels must be
 * mutually non-overlapping and must not overlap either output descriptor. */
typedef struct bg_force_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t particle_capacity;
    uint64_t particle_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double *x_kcal_per_mol_angstrom;
    double *y_kcal_per_mol_angstrom;
    double *z_kcal_per_mol_angstrom;
    uint64_t reserved[4];
} bg_force_soa_v1;

/* Energy output in the frozen bond, angle, torsion, LJ, Coulomb order. */
typedef struct bg_energy_components_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double harmonic_bond_kcal_per_mol;
    double harmonic_angle_kcal_per_mol;
    double periodic_torsion_kcal_per_mol;
    double lennard_jones_kcal_per_mol;
    double coulomb_kcal_per_mol;
    double total_kcal_per_mol;
    uint64_t reserved[4];
} bg_energy_components_v1;

/*
 * Canonical distance constraints.  Rows are deep-copied and canonicalized by
 * bg_simulation_create.  Atom indices are zero based, each target distance is
 * finite and positive, tolerance_angstrom is finite and positive, and
 * max_iterations is non-zero.  Duplicate unordered atom pairs are rejected.
 * tolerance_angstrom controls SHAKE distance residuals and
 * velocity_tolerance_angstrom_per_femtosecond separately controls RATTLE.
 * Every target must be below half each periodic axis length.  Rows are
 * required to be independent; duplicates and detectable
 * singular/nonconvergent initial states are rejected.  SHAKE/RATTLE process
 * canonical pair order and use the force field's exact
 * d-L*floor(d/L+0.5) orthorhombic minimum-image rule while positions remain
 * unwrapped.
 */
typedef struct bg_distance_constraints_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t constraint_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    const uint64_t *atom_i;
    const uint64_t *atom_j;
    const double *distance_angstrom;
    double tolerance_angstrom;
    double velocity_tolerance_angstrom_per_femtosecond;
    uint32_t max_iterations;
    uint32_t reserved1;
    uint64_t reserved[4];
} bg_distance_constraints_v1;

/*
 * Dynamics configuration in canonical units.  The timestep must be finite
 * and positive, including a representable positive half-step.  Temperature
 * and friction are validated as finite and non-negative for both integrators;
 * Velocity Verlet canonicalizes its unused temperature, friction, and seed to
 * zero for semantic checkpoint fingerprints.  Langevin BAOAB's counter-based
 * Philox4x32-10 stream is keyed by random_seed and the absolute step, so
 * checkpoint continuation consumes exactly the same samples and keeps no
 * hidden spare-normal cache.
 */
typedef struct bg_simulation_options_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    bg_integrator integrator;
    double timestep_femtoseconds;
    double temperature_kelvin;
    double friction_per_femtosecond;
    uint64_t random_seed;
    uint64_t reserved[4];
} bg_simulation_options_v1;

/*
 * Deterministic steepest-descent and bounded Armijo line-search settings.
 * The step has units angstrom^2*mol/kcal because it multiplies force.  Energy
 * and maximum-force convergence thresholds use kcal/mol and
 * kcal/(mol*angstrom), respectively.  All tolerances are non-negative;
 * initial/minimum step and both iteration bounds are positive; 0<armijo<1 and
 * 0<backtrack<1.  An energy tolerance of zero disables energy convergence; a
 * force tolerance of zero requires an exactly zero projected force.
 */
typedef struct bg_minimizer_options_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    uint64_t max_iterations;
    uint32_t max_line_search_steps;
    uint32_t reserved1;
    double initial_step_angstrom2_mol_per_kcal;
    double minimum_step_angstrom2_mol_per_kcal;
    double energy_tolerance_kcal_per_mol;
    double force_tolerance_kcal_per_mol_angstrom;
    double armijo_coefficient;
    double backtrack_factor;
    uint64_t reserved[4];
} bg_minimizer_options_v1;

typedef struct bg_minimization_report_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    uint64_t iterations;
    uint32_t converged;
    uint32_t reserved1;
    double initial_potential_kcal_per_mol;
    double final_potential_kcal_per_mol;
    double maximum_force_kcal_per_mol_angstrom;
    uint64_t reserved[4];
} bg_minimization_report_v1;

/* maximum_force is the Euclidean tangential projection used by constrained
 * Cartesian steepest descent, rather than an unprojected constraint reaction. */

/*
 * Dynamics energies use deterministic float64 evaluation.  Kinetic energy is
 * 0.5/4.184e-4 * sum(mass_dalton*velocity_angstrom_per_fs^2).  Temperature is
 * 2*K/(DOF*R), R=0.0019872042586408316 kcal/(mol*K), with
 * DOF=3*particle_count-constraint_count and no implicit COM removal.
 */
typedef struct bg_dynamics_report_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    uint64_t steps_completed;
    uint64_t absolute_step;
    uint64_t degrees_of_freedom;
    double potential_kcal_per_mol;
    double kinetic_kcal_per_mol;
    double total_kcal_per_mol;
    double temperature_kelvin;
    uint64_t reserved[4];
} bg_dynamics_report_v1;

/*
 * Persistent Engine V2 ScorerV1 context input.  All channels and the four
 * identity digests are deep-copied by bg_docking_scorer_v1_create.  The
 * ligand reference geometry fixes internal-vdW and rotor strain baselines.
 * Donor rows are sorted lexicographically by donor/hydrogen, exclusion rows
 * are unique canonical first<second pairs, and rotor rows are unique.  Atom
 * boolean channels contain exactly 0 or 1.  This numerical ABI binds evidence
 * identities but does not grant molecular-execution or production authority.
 */
typedef struct bg_docking_scorer_v1_context_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;

    uint64_t receptor_atom_count;
    uint64_t ligand_atom_count;

    const double *receptor_x_angstrom;
    const double *receptor_y_angstrom;
    const double *receptor_z_angstrom;
    const double *receptor_charge_elementary;
    const double *receptor_vdw_radius_angstrom;
    const double *receptor_epsilon_kcal_per_mol;
    const uint8_t *receptor_hydrophobic;
    const uint8_t *receptor_acceptor;

    const double *ligand_reference_x_angstrom;
    const double *ligand_reference_y_angstrom;
    const double *ligand_reference_z_angstrom;
    const double *ligand_charge_elementary;
    const double *ligand_vdw_radius_angstrom;
    const double *ligand_epsilon_kcal_per_mol;
    const uint8_t *ligand_hydrophobic;
    const uint8_t *ligand_acceptor;

    uint64_t receptor_donor_count;
    const uint64_t *receptor_donor_atom_index;
    const uint64_t *receptor_hydrogen_atom_index;
    uint64_t ligand_donor_count;
    const uint64_t *ligand_donor_atom_index;
    const uint64_t *ligand_hydrogen_atom_index;

    uint64_t ligand_exclusion_count;
    const uint64_t *ligand_exclusion_atom_i;
    const uint64_t *ligand_exclusion_atom_j;

    uint64_t rotor_count;
    const uint64_t *rotor_atom_i;
    const uint64_t *rotor_atom_j;
    const uint64_t *rotor_atom_k;
    const uint64_t *rotor_atom_l;

    double pocket_center_angstrom[3];
    double pocket_radius_angstrom;
    double weights[BG_DOCKING_SCORER_V1_TERM_COUNT];
    double electrostatic_dielectric;
    double pair_cutoff_angstrom;
    double hbond_distance_max_angstrom;
    double polar_burial_distance_angstrom;
    uint64_t max_receptor_candidate_pairs;
    uint64_t max_ligand_pair_checks;

    uint8_t authority_input_receipt_sha256[32];
    uint8_t receptor_system_sha256[32];
    uint8_t ligand_system_sha256[32];
    uint8_t backend_receipt_sha256[32];
    uint64_t reserved[8];
} bg_docking_scorer_v1_context_soa_v1;

/* Candidate-major fixed64 coordinate SoA.  Every batch preserves 64 slots.
 * Inactive rows retain the denominator and produce the typed upstream failure
 * without interpreting their coordinate values. */
typedef struct bg_docking_scorer_v1_candidate_batch_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t candidate_count;
    uint64_t ligand_atom_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    const bg_docking_scorer_v1_candidate_state *candidate_state;
    const double *x_angstrom;
    const double *y_angstrom;
    const double *z_angstrom;
    uint64_t reserved[4];
} bg_docking_scorer_v1_candidate_batch_soa_v1;

/* Frozen ScorerV1 term order: typed-vdW, electrostatics,
 * directional-H-bond, hydrophobic-contact, desolvation-proxy,
 * torsion-energy, ligand-strain, weak-pocket-prior. */
typedef struct bg_docking_scorer_v1_row_v1 {
    uint32_t slot_index;
    bg_docking_scorer_v1_row_status status;
    bg_docking_scorer_v1_failure failure_code;
    uint32_t reserved0;
    double weighted_terms[BG_DOCKING_SCORER_V1_TERM_COUNT];
    double total_score;
    uint64_t receptor_candidate_pair_count;
    uint64_t ligand_pair_count;
    uint64_t hbond_count;
    uint64_t hydrophobic_contact_count;
    uint64_t buried_polar_count;
    uint64_t reserved[4];
} bg_docking_scorer_v1_row_v1;

/* Caller-owned fixed64 output.  capacity and rows are inputs; row_count is
 * committed only after the complete batch succeeds. */
typedef struct bg_docking_scorer_v1_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t row_capacity;
    uint64_t row_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    bg_docking_scorer_v1_row_v1 *rows;
    uint64_t reserved[4];
} bg_docking_scorer_v1_output_v1;

/*
 * Persistent Engine V2 pose-validity context. All channels and six identity
 * digests are deep-copied. Bond and exclusion rows are unique sorted
 * canonical i<j pairs; each chirality row contains four distinct in-range
 * ligand atom indices. This numerical ABI records no product, molecular-
 * execution, benchmark, or reservation authority.
 */
typedef struct bg_docking_pose_validity_context_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;

    uint64_t receptor_atom_count;
    uint64_t ligand_atom_count;
    const double *receptor_x_angstrom;
    const double *receptor_y_angstrom;
    const double *receptor_z_angstrom;
    const double *receptor_vdw_radius_angstrom;
    const double *ligand_reference_x_angstrom;
    const double *ligand_reference_y_angstrom;
    const double *ligand_reference_z_angstrom;
    const double *ligand_vdw_radius_angstrom;

    uint64_t bond_count;
    const uint64_t *bond_atom_i;
    const uint64_t *bond_atom_j;
    uint64_t ligand_exclusion_count;
    const uint64_t *ligand_exclusion_atom_i;
    const uint64_t *ligand_exclusion_atom_j;
    uint64_t chirality_center_count;
    const uint64_t *chirality_center_atom;
    const uint64_t *chirality_atom_i;
    const uint64_t *chirality_atom_j;
    const uint64_t *chirality_atom_k;

    double pocket_center_angstrom[3];
    double pocket_radius_angstrom;
    double bond_length_tolerance_angstrom;
    double ligand_self_clash_angstrom;
    double receptor_ligand_clash_angstrom;
    double rotation_tolerance;
    double chirality_volume_tolerance;
    double severe_overlap_scale;
    double contact_cell_size_angstrom;
    uint64_t max_pair_checks;
    uint64_t max_cross_checks;
    uint64_t max_element_ligand_pair_checks;
    uint64_t max_element_receptor_candidate_pairs;

    uint8_t authority_input_receipt_sha256[32];
    uint8_t receptor_system_sha256[32];
    uint8_t ligand_system_sha256[32];
    uint8_t scorer_context_receipt_sha256[32];
    uint8_t backend_receipt_sha256[32];
    uint8_t contact_policy_sha256[32];
    uint64_t reserved[8];
} bg_docking_pose_validity_context_soa_v1;

/* Candidate-major fixed64 coordinates and explicit (x,y,z,w) rotation
 * evidence. Upstream-failure rows retain the denominator and exact ScorerV1
 * failure code; their coordinate and quaternion values are not interpreted. */
typedef struct bg_docking_pose_validity_candidate_batch_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t candidate_count;
    uint64_t ligand_atom_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    const bg_docking_pose_validity_candidate_state *candidate_state;
    const bg_docking_scorer_v1_failure *upstream_scorer_failure_code;
    const double *quaternion_x;
    const double *quaternion_y;
    const double *quaternion_z;
    const double *quaternion_w;
    const double *x_angstrom;
    const double *y_angstrom;
    const double *z_angstrom;
    uint64_t reserved[4];
} bg_docking_pose_validity_candidate_batch_soa_v1;

typedef struct bg_docking_pose_validity_row_v1 {
    uint32_t slot_index;
    bg_docking_pose_validity_row_status status;
    bg_docking_pose_validity_failure failure_code;
    bg_docking_scorer_v1_failure upstream_scorer_failure_code;
    bg_docking_pose_validity_check_mask passed_check_mask;
    bg_docking_pose_validity_check_mask blocker_mask;
    uint64_t observed_count;

    uint64_t atom_count;
    double rotation_orthogonality_max_error;
    double rotation_determinant;
    double max_bond_length_delta_angstrom;
    double minimum_ligand_nonbonded_distance_angstrom;
    uint64_t evaluated_ligand_nonbonded_pair_count;
    uint64_t excluded_ligand_pair_count;
    double minimum_receptor_ligand_distance_angstrom;
    uint64_t evaluated_receptor_ligand_pair_count;
    double minimum_declared_chiral_volume;
    uint64_t declared_chirality_center_count;
    double maximum_pocket_center_distance_angstrom;
    uint64_t element_vdw_ligand_pair_count;
    uint64_t element_vdw_ligand_severe_overlap_count;
    double element_vdw_ligand_minimum_distance_angstrom;
    double element_vdw_ligand_minimum_ratio;
    uint64_t element_vdw_receptor_candidate_pair_count;
    uint64_t element_vdw_receptor_full_cartesian_pair_count;
    uint64_t element_vdw_receptor_cell_count;
    uint64_t element_vdw_receptor_severe_overlap_count;
    double element_vdw_receptor_minimum_distance_angstrom;
    double element_vdw_receptor_minimum_ratio;
    uint64_t reserved[4];
} bg_docking_pose_validity_row_v1;

typedef struct bg_docking_pose_validity_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t row_capacity;
    uint64_t row_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    bg_docking_pose_validity_row_v1 *rows;
    uint64_t reserved[4];
} bg_docking_pose_validity_output_v1;

/* ABI and diagnostics. */
BG_API uint32_t BG_CALL bg_abi_version(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_abi_version_major(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_abi_version_minor(void) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_abi_version_string(void) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_status_string(bg_status status) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_backend_string(bg_backend backend) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_unit_system_string(bg_unit_system units) BG_NOEXCEPT;

/*
 * Detailed errors are thread-local.  The direct pointer remains valid until
 * the next fallible ABI call on the same thread.  The copy form reports the
 * required byte count including the trailing NUL.  A null buffer with zero
 * capacity is a size query.
 */
BG_API const char *BG_CALL bg_last_error_message(void) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_last_error_message_copy(
    char *buffer,
    uint64_t buffer_capacity,
    uint64_t *required_size) BG_NOEXCEPT;

/*
 * Descriptor initializers set the current size/version and canonical units.
 * The exported functions require the descriptor size and ABI version compiled
 * into the caller.  A mismatch returns BG_STATUS_ABI_MISMATCH without reading
 * or writing descriptor storage, so an incompatible library cannot overwrite
 * an older caller's smaller object.  The convenience macros below supply the
 * exact current values for ordinary C and C++ calls.  Taking an initializer's
 * address still names its three-argument exported function.  Define
 * BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS before including this header
 * when direct three-argument call syntax is preferred.
 */
BG_API bg_status BG_CALL bg_context_options_init(
    bg_context_options *options,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_soa_init(
    bg_particle_soa *particles,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_soa_view_init(
    bg_particle_soa_view *view,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_position_soa_init(
    bg_position_soa *positions,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_forcefield_soa_v1_init(
    bg_forcefield_soa_v1 *forcefield,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_force_soa_v1_init(
    bg_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_energy_components_v1_init(
    bg_energy_components_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_distance_constraints_v1_init(
    bg_distance_constraints_v1 *constraints,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_simulation_options_v1_init(
    bg_simulation_options_v1 *options,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_minimizer_options_v1_init(
    bg_minimizer_options_v1 *options,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_minimization_report_v1_init(
    bg_minimization_report_v1 *report,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_dynamics_report_v1_init(
    bg_dynamics_report_v1 *report,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_scorer_v1_context_soa_v1_init(
    bg_docking_scorer_v1_context_soa_v1 *descriptor,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_scorer_v1_candidate_batch_soa_v1_init(
    bg_docking_scorer_v1_candidate_batch_soa_v1 *batch,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_scorer_v1_output_v1_init(
    bg_docking_scorer_v1_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_pose_validity_context_soa_v1_init(
    bg_docking_pose_validity_context_soa_v1 *descriptor,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_pose_validity_candidate_batch_soa_v1_init(
    bg_docking_pose_validity_candidate_batch_soa_v1 *batch,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_pose_validity_output_v1_init(
    bg_docking_pose_validity_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;

#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define bg_context_options_init(options) \
    bg_context_options_init( \
        (options), sizeof(bg_context_options), BG_ABI_VERSION)
#  define bg_particle_soa_init(particles) \
    bg_particle_soa_init( \
        (particles), sizeof(bg_particle_soa), BG_ABI_VERSION)
#  define bg_particle_soa_view_init(view) \
    bg_particle_soa_view_init( \
        (view), sizeof(bg_particle_soa_view), BG_ABI_VERSION)
#  define bg_position_soa_init(positions) \
    bg_position_soa_init( \
        (positions), sizeof(bg_position_soa), BG_ABI_VERSION)
#  define bg_forcefield_soa_v1_init(forcefield) \
    bg_forcefield_soa_v1_init( \
        (forcefield), sizeof(bg_forcefield_soa_v1), BG_ABI_VERSION)
#  define bg_force_soa_v1_init(forces) \
    bg_force_soa_v1_init( \
        (forces), sizeof(bg_force_soa_v1), BG_ABI_VERSION)
#  define bg_energy_components_v1_init(energy) \
    bg_energy_components_v1_init( \
        (energy), sizeof(bg_energy_components_v1), BG_ABI_VERSION)
#  define bg_distance_constraints_v1_init(constraints) \
    bg_distance_constraints_v1_init( \
        (constraints), \
        sizeof(bg_distance_constraints_v1), \
        BG_ABI_VERSION)
#  define bg_simulation_options_v1_init(options) \
    bg_simulation_options_v1_init( \
        (options), \
        sizeof(bg_simulation_options_v1), \
        BG_ABI_VERSION)
#  define bg_minimizer_options_v1_init(options) \
    bg_minimizer_options_v1_init( \
        (options), \
        sizeof(bg_minimizer_options_v1), \
        BG_ABI_VERSION)
#  define bg_minimization_report_v1_init(report) \
    bg_minimization_report_v1_init( \
        (report), \
        sizeof(bg_minimization_report_v1), \
        BG_ABI_VERSION)
#  define bg_dynamics_report_v1_init(report) \
    bg_dynamics_report_v1_init( \
        (report), sizeof(bg_dynamics_report_v1), BG_ABI_VERSION)
#  define bg_docking_scorer_v1_context_soa_v1_init(descriptor) \
    bg_docking_scorer_v1_context_soa_v1_init( \
        (descriptor), \
        sizeof(bg_docking_scorer_v1_context_soa_v1), \
        BG_ABI_VERSION)
#  define bg_docking_scorer_v1_candidate_batch_soa_v1_init(batch) \
    bg_docking_scorer_v1_candidate_batch_soa_v1_init( \
        (batch), \
        sizeof(bg_docking_scorer_v1_candidate_batch_soa_v1), \
        BG_ABI_VERSION)
#  define bg_docking_scorer_v1_output_v1_init(output) \
    bg_docking_scorer_v1_output_v1_init( \
        (output), sizeof(bg_docking_scorer_v1_output_v1), BG_ABI_VERSION)
#  define bg_docking_pose_validity_context_soa_v1_init(descriptor) \
    bg_docking_pose_validity_context_soa_v1_init( \
        (descriptor), \
        sizeof(bg_docking_pose_validity_context_soa_v1), \
        BG_ABI_VERSION)
#  define bg_docking_pose_validity_candidate_batch_soa_v1_init(batch) \
    bg_docking_pose_validity_candidate_batch_soa_v1_init( \
        (batch), \
        sizeof(bg_docking_pose_validity_candidate_batch_soa_v1), \
        BG_ABI_VERSION)
#  define bg_docking_pose_validity_output_v1_init(output) \
    bg_docking_pose_validity_output_v1_init( \
        (output), sizeof(bg_docking_pose_validity_output_v1), BG_ABI_VERSION)
#endif

/*
 * Backend selection is explicit.  AUTO remains the deterministic CPU backend
 * in ABI v1.3.  HIP is reported available only when the native library was
 * built with its HIP provider, the requested runtime device supports
 * binary64, and the library contains a compatible device code object.
 * An explicit unavailable HIP request never runs CPU.  The availability
 * output is initialized to zero; HIP runtime discovery failures are returned
 * as an error status instead of being reported as an unavailable device.
 */
BG_API bg_status BG_CALL bg_backend_is_available(
    bg_backend backend,
    int32_t device_ordinal,
    uint8_t *available) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_context_create(
    const bg_context_options *options,
    bg_context **out_context) BG_NOEXCEPT;
BG_API void BG_CALL bg_context_destroy(bg_context *context) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_context_get_backend(
    const bg_context *context,
    bg_backend *backend) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_context_get_device_ordinal(
    const bg_context *context,
    int32_t *device_ordinal) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_context_get_unit_system(
    const bg_context *context,
    bg_unit_system *unit_system) BG_NOEXCEPT;

/*
 * Create a persistent ScorerV1 context for the explicitly selected backend.
 * CPP_CPU_REFERENCE is qualification-only.  RUST_CPU is the product CPU
 * implementation.  HIP_SAFE and HIP_FAST never fall back; until their
 * ScorerV1 providers are compiled and qualified these calls fail closed with
 * BG_STATUS_BACKEND_UNAVAILABLE.  The scorer owns all copied context state and
 * has no parent-context lifetime dependency, while score calls still require a
 * context with the exact backend/device binding used at creation.
 */
BG_API bg_status BG_CALL bg_docking_scorer_v1_create(
    const bg_context *context,
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    bg_docking_scorer_v1 **out_scorer) BG_NOEXCEPT;
BG_API void BG_CALL bg_docking_scorer_v1_destroy(
    bg_docking_scorer_v1 *scorer) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_scorer_v1_get_backend(
    const bg_docking_scorer_v1 *scorer,
    bg_backend *backend) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_scorer_v1_score_fixed64(
    const bg_context *context,
    const bg_docking_scorer_v1 *scorer,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_output_v1 *out_rows) BG_NOEXCEPT;

/*
 * Pose validity uses the same explicit backend/device binding as ScorerV1.
 * CPP_CPU_REFERENCE is qualification-only, RUST_CPU is the product CPU path,
 * and HIP_SAFE/HIP_FAST never fall back. Candidate rows remain fixed at 64;
 * upstream scorer failures and candidate-local capacity failures are emitted
 * as typed rows rather than removed from the denominator.
 */
BG_API bg_status BG_CALL bg_docking_pose_validity_v1_create(
    const bg_context *context,
    const bg_docking_pose_validity_context_soa_v1 *descriptor,
    bg_docking_pose_validity_v1 **out_validity) BG_NOEXCEPT;
BG_API void BG_CALL bg_docking_pose_validity_v1_destroy(
    bg_docking_pose_validity_v1 *validity) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_pose_validity_v1_get_backend(
    const bg_docking_pose_validity_v1 *validity,
    bg_backend *backend) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_docking_pose_validity_v1_evaluate_fixed64(
    const bg_context *context,
    const bg_docking_pose_validity_v1 *validity,
    const bg_docking_pose_validity_candidate_batch_soa_v1 *candidates,
    bg_docking_pose_validity_output_v1 *out_rows) BG_NOEXCEPT;

/* A system owns its host SoA and has no parent-handle lifetime dependency. */
BG_API bg_status BG_CALL bg_system_create(
    const bg_particle_soa *particles,
    bg_system **out_system) BG_NOEXCEPT;
BG_API void BG_CALL bg_system_destroy(bg_system *system) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_system_get_particle_count(
    const bg_system *system,
    uint64_t *particle_count) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_system_get_unit_system(
    const bg_system *system,
    bg_unit_system *unit_system) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_system_get_particles(
    const bg_system *system,
    bg_particle_soa_view *out_view) BG_NOEXCEPT;
/*
 * On success this atomically replaces all three position channels without
 * changing the addresses held by existing bg_particle_soa_view values; those
 * views observe the new coordinates after the synchronized call returns.  On
 * failure the system and existing views are unchanged.
 */
BG_API bg_status BG_CALL bg_system_set_positions(
    bg_system *system,
    const bg_position_soa *positions) BG_NOEXCEPT;

/* A force-field handle owns validated parameter SoAs and has no parent handle. */
BG_API bg_status BG_CALL bg_forcefield_create(
    const bg_forcefield_soa_v1 *parameters,
    bg_forcefield **out_forcefield) BG_NOEXCEPT;
BG_API void BG_CALL bg_forcefield_destroy(
    bg_forcefield *forcefield) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_forcefield_get_atom_count(
    const bg_forcefield *forcefield,
    uint64_t *atom_count) BG_NOEXCEPT;

/*
 * Dispatch through the explicitly selected context backend. The C++ CPU
 * reference, independent Rust CPU backend, and hip_safe qualification backend
 * use binary64 with a fixed serial accumulation order and analytic forces
 * defined as -dU/d(position). hip_safe is available only when a compiled,
 * explicitly qualified GPU architecture matches the requested runtime device;
 * it never falls back to CPU. hip_fast is the separately selected parallel HIP
 * lane and likewise never falls back. Output buffers are transactional: no
 * output value changes unless the complete evaluation succeeds. Energy-only
 * evaluation does not require differentiability of a zero-length harmonic
 * bond; requesting forces for that geometry returns
 * BG_STATUS_NUMERICAL_ERROR.
 */
BG_API bg_status BG_CALL bg_context_evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    bg_energy_components_v1 *out_energy,
    bg_force_soa_v1 *out_forces) BG_NOEXCEPT;

/*
 * A simulation deep-owns independent copies of the system, force field,
 * canonicalized constraints, and integration configuration.  A null
 * constraints pointer means no constraints.  For a constrained simulation,
 * creation transactionally SHAKE-projects copied positions and RATTLE-projects
 * copied velocities before returning.  It has no
 * parent-handle lifetime dependency.  Particle views remain valid until the
 * simulation is destroyed and observe committed minimize/integrate/load
 * results after the synchronized call returns without changing the borrowed
 * channel addresses.  Mutating calls are whole-call
 * transactional: every failure leaves positions, velocities, and absolute
 * step unchanged.  The supplied context selects the force evaluator and an
 * unavailable/erroring HIP backend never falls back to CPU.
 */
BG_API bg_status BG_CALL bg_simulation_create(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_distance_constraints_v1 *constraints,
    const bg_simulation_options_v1 *options,
    bg_simulation **out_simulation) BG_NOEXCEPT;
BG_API void BG_CALL bg_simulation_destroy(
    bg_simulation *simulation) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_simulation_get_particles(
    const bg_simulation *simulation,
    bg_particle_soa_view *out_view) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_simulation_get_absolute_step(
    const bg_simulation *simulation,
    uint64_t *absolute_step) BG_NOEXCEPT;

/* Minimization preserves absolute step.  It preserves velocity bits when
 * unconstrained; constrained minimization performs a final mass-weighted
 * RATTLE projection against its new geometry. */
BG_API bg_status BG_CALL bg_context_minimize(
    const bg_context *context,
    bg_simulation *simulation,
    const bg_minimizer_options_v1 *options,
    bg_minimization_report_v1 *out_report) BG_NOEXCEPT;
/* Integrating zero steps evaluates and reports the current energy but is a
 * strict dynamic-state no-op; backend or numerical evaluation errors are
 * still returned transactionally. */
BG_API bg_status BG_CALL bg_context_integrate(
    const bg_context *context,
    bg_simulation *simulation,
    uint64_t step_count,
    bg_dynamics_report_v1 *out_report) BG_NOEXCEPT;

/*
 * Checkpoint wire format v1 is canonical little-endian and padding-free:
 * magic "BGDYN001" at bytes 0..7, uint32 format/version and header size at
 * 8/12, uint64 total size/particle count/absolute step at 16/24/32, semantic
 * fingerprint at 40..71, integrity digest at 72..103, then float64 SoA payload
 * in x,y,z,vx,vy,vz channel order.  The fixed header is 104 bytes.  SHA-256
 * covers every serialized byte with bytes 72..103 zeroed, and a
 * separate semantic SHA-256 fingerprint binds the complete force field,
 * masses, charges, constraints, and integration configuration.  Load
 * validates everything, including an exact static-fingerprint match with the
 * existing destination simulation, before transactionally committing dynamic
 * state.
 */
BG_API bg_status BG_CALL bg_simulation_checkpoint_size(
    const bg_simulation *simulation,
    uint64_t *required_size) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_simulation_checkpoint_write(
    const bg_simulation *simulation,
    void *buffer,
    uint64_t buffer_capacity,
    uint64_t *written_size) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_simulation_checkpoint_load(
    bg_simulation *simulation,
    const void *buffer,
    uint64_t buffer_size) BG_NOEXCEPT;

#if defined(__cplusplus)
} /* extern "C" */
#endif

#endif /* BETELGEUZE_ENGINE_H */
