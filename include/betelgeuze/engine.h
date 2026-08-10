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
 *
 * Callers must convert at adapters before entering this ABI.  Native entry
 * points reject any other unit-system identifier.
 *
 * ABI evolution rule: every descriptor layout and initializer write-size in
 * ABI/SOVERSION 1 is frozen.  ABI v1 additions must consume reserved fields or
 * introduce a new, version-suffixed descriptor and initializer; they must not
 * enlarge the structs below.  A new major layout requires a new ABI/SOVERSION.
 */

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
#define BG_ABI_VERSION_MINOR UINT32_C(1)
#define BG_ABI_VERSION UINT32_C(1)

#define BG_CANONICAL_LENGTH_UNIT "angstrom"
#define BG_CANONICAL_ENERGY_UNIT "kcal/mol"
#define BG_CANONICAL_FORCE_UNIT "kcal/(mol*angstrom)"
#define BG_CANONICAL_CHARGE_UNIT "elementary_charge"
#define BG_CANONICAL_MASS_UNIT "dalton"
#define BG_CANONICAL_ANGLE_UNIT "radian"
#define BG_CANONICAL_TIME_UNIT "femtosecond"
#define BG_CANONICAL_VELOCITY_UNIT "angstrom/femtosecond"

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
    BG_BACKEND_CPU = 1,
    BG_BACKEND_HIP = 2
};

typedef int32_t bg_unit_system;
enum {
    BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL = 1
};

/* Incomplete declarations are the only public handle representation. */
typedef struct bg_context bg_context;
typedef struct bg_system bg_system;
typedef struct bg_forcefield bg_forcefield;

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

/* Descriptor initializers set the current size/version and canonical units. */
BG_API bg_status BG_CALL bg_context_options_init(
    bg_context_options *options) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_soa_init(
    bg_particle_soa *particles) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_soa_view_init(
    bg_particle_soa_view *view) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_position_soa_init(
    bg_position_soa *positions) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_forcefield_soa_v1_init(
    bg_forcefield_soa_v1 *forcefield) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_force_soa_v1_init(
    bg_force_soa_v1 *forces) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_energy_components_v1_init(
    bg_energy_components_v1 *energy) BG_NOEXCEPT;

/* Backend selection is explicit.  An unavailable HIP request never runs CPU. */
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
 * Dispatch through the explicitly selected context backend.  CPU evaluation
 * is scalar binary64 with a fixed serial accumulation order and analytic
 * forces defined as -dU/d(position).  Output buffers are transactional: no output value changes unless
 * the complete evaluation succeeds.  Energy-only evaluation does not require
 * differentiability of a zero-length harmonic bond; requesting forces for
 * that geometry returns BG_STATUS_NUMERICAL_ERROR.
 */
BG_API bg_status BG_CALL bg_context_evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    bg_energy_components_v1 *out_energy,
    bg_force_soa_v1 *out_forces) BG_NOEXCEPT;

#if defined(__cplusplus)
} /* extern "C" */
#endif

#endif /* BETELGEUZE_ENGINE_H */
