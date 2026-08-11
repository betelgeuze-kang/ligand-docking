use betelgeuze_reference_physics as oracle;
use betelgeuze_runtime as runtime;

const ENERGY_TOLERANCE: f64 = 1.0e-10;
const FORCE_DIFFERENCE_STEP_ANGSTROM: f64 = 1.0e-5;
const FORCE_TOLERANCE: f64 = 2.0e-4;
const CROSS_BACKEND_TOLERANCE: f64 = 2.0e-12;

fn safe_backends() -> Vec<runtime::Backend> {
    let mut backends = vec![runtime::Backend::CppCpuReference, runtime::Backend::RustCpu];
    if runtime::Context::backend_available(runtime::Backend::HipSafe, 0)
        .expect("hip_safe availability query succeeds")
    {
        backends.push(runtime::Backend::HipSafe);
    }
    backends
}

#[derive(Clone)]
struct Fixture {
    name: &'static str,
    input: oracle::OracleInput,
    exact: Option<ExactFixture>,
}

#[derive(Clone, Copy)]
enum ExactFixture {
    BondOnly,
    LennardJonesOnly,
}

struct NativeFixture {
    context: runtime::Context,
    system: runtime::System,
    forcefield: runtime::ForceField,
}

#[test]
fn cpu_energy_components_match_the_independent_rust_oracle() {
    for fixture in fixtures() {
        let expected = oracle::evaluate(&fixture.input)
            .unwrap_or_else(|error| panic!("{} oracle evaluation failed: {error}", fixture.name));
        for backend in safe_backends() {
            let native = native_fixture(&fixture, backend);
            let actual = native
                .context
                .evaluate(&native.system, &native.forcefield)
                .unwrap_or_else(|error| {
                    panic!(
                        "{} {} evaluation failed: {error}",
                        fixture.name,
                        backend_name(backend)
                    )
                });
            let energy_only = native
                .context
                .evaluate_energy(&native.system, &native.forcefield)
                .unwrap_or_else(|error| {
                    panic!(
                        "{} {} energy-only evaluation failed: {error}",
                        fixture.name,
                        backend_name(backend)
                    )
                });

            assert_energy_close(fixture.name, actual.energy, expected);
            assert_runtime_energy_bits_equal(
                fixture.name,
                "full and energy-only evaluation",
                actual.energy,
                energy_only,
            );
            if let Some(exact) = fixture.exact {
                assert_exact_algebraic_fixture(fixture.name, exact, actual.energy, expected);
            }
        }
    }
}

#[test]
fn every_analytic_force_component_matches_oracle_central_differences() {
    for fixture in fixtures() {
        for backend in safe_backends() {
            let native = native_fixture(&fixture, backend);
            let actual = native
                .context
                .evaluate(&native.system, &native.forcefield)
                .unwrap_or_else(|error| {
                    panic!(
                        "{} {} evaluation failed: {error}",
                        fixture.name,
                        backend_name(backend)
                    )
                });

            for atom in 0..fixture.input.positions.len() {
                for axis in 0..3 {
                    let expected = finite_difference_force(&fixture, atom, axis);
                    let observed = native_force_component(&actual.forces, atom, axis);
                    let difference = (observed - expected).abs();
                    assert!(
                        difference <= FORCE_TOLERANCE,
                        "{} {} force atom {atom} axis {axis}: observed={observed:.17e}, \
                         oracle finite difference={expected:.17e}, |delta|={difference:.3e} > \
                         {FORCE_TOLERANCE:.3e}",
                        fixture.name,
                        backend_name(backend)
                    );
                }
            }
        }
    }
}

#[test]
fn cpu_evaluation_is_bit_deterministic_and_conserves_net_force() {
    for fixture in fixtures() {
        for backend in safe_backends() {
            let native = native_fixture(&fixture, backend);
            let first = native
                .context
                .evaluate(&native.system, &native.forcefield)
                .unwrap_or_else(|error| {
                    panic!(
                        "{} first {} evaluation failed: {error}",
                        fixture.name,
                        backend_name(backend)
                    )
                });
            let second = native
                .context
                .evaluate(&native.system, &native.forcefield)
                .unwrap_or_else(|error| {
                    panic!(
                        "{} repeated {} evaluation failed: {error}",
                        fixture.name,
                        backend_name(backend)
                    )
                });

            assert_runtime_energy_bits_equal(
                fixture.name,
                "repeated full evaluation",
                first.energy,
                second.energy,
            );
            for axis in 0..3 {
                let first_channel = force_channel(&first.forces, axis);
                let second_channel = force_channel(&second.forces, axis);
                assert_eq!(first_channel.len(), second_channel.len());
                for (atom, (left, right)) in
                    first_channel.iter().zip(second_channel.iter()).enumerate()
                {
                    assert_eq!(
                        left.to_bits(),
                        right.to_bits(),
                        "{} repeated {} force changed bits at atom {atom}, axis {axis}",
                        fixture.name,
                        backend_name(backend)
                    );
                }

                let net: f64 = first_channel.iter().sum();
                let magnitude_sum: f64 = first_channel.iter().map(|value| value.abs()).sum();
                let tolerance = 1.0e-12 * (1.0 + magnitude_sum);
                assert!(
                    net.abs() <= tolerance,
                    "{} {} net force axis {axis} is {net:.17e}, tolerance {tolerance:.3e}",
                    fixture.name,
                    backend_name(backend)
                );
            }
        }
    }
}

#[test]
fn native_safe_backends_match_cpp_reference_within_the_frozen_tolerance() {
    for fixture in fixtures() {
        let cpp = native_fixture(&fixture, runtime::Backend::CppCpuReference);
        let cpp_result = cpp
            .context
            .evaluate(&cpp.system, &cpp.forcefield)
            .expect("C++ reference evaluation succeeds");
        for backend in safe_backends()
            .into_iter()
            .filter(|backend| *backend != runtime::Backend::CppCpuReference)
        {
            let candidate = native_fixture(&fixture, backend);
            let candidate_result = candidate
                .context
                .evaluate(&candidate.system, &candidate.forcefield)
                .unwrap_or_else(|error| {
                    panic!(
                        "{} {} evaluation failed: {error}",
                        fixture.name,
                        backend_name(backend)
                    )
                });
            for ((name, left), (_, right)) in runtime_energy_values(cpp_result.energy)
                .into_iter()
                .zip(runtime_energy_values(candidate_result.energy))
            {
                assert_close_cross_backend(fixture.name, backend, name, left, right);
            }
            for axis in 0..3 {
                for (atom, (left, right)) in force_channel(&cpp_result.forces, axis)
                    .iter()
                    .zip(force_channel(&candidate_result.forces, axis))
                    .enumerate()
                {
                    let field = format!("force[{atom}][{axis}]");
                    assert_close_cross_backend(fixture.name, backend, &field, *left, *right);
                }
            }
        }
    }
}

#[test]
fn signed_torsion_fixture_distinguishes_reflected_geometry() {
    let fixture = fixtures()
        .into_iter()
        .find(|fixture| fixture.name == "signed_torsion")
        .expect("signed torsion fixture exists");
    let original = oracle::evaluate(&fixture.input)
        .expect("original signed torsion evaluates")
        .periodic_torsion_kcal_per_mol;
    let mut reflected = fixture.input;
    reflected.positions[3].z_angstrom *= -1.0;
    let reflected = oracle::evaluate(&reflected)
        .expect("reflected signed torsion evaluates")
        .periodic_torsion_kcal_per_mol;
    assert!(
        (original - reflected).abs() > 1.0,
        "the signed fixture must detect a torsion-orientation reversal"
    );
}

#[test]
fn independent_oracle_remains_a_dev_only_dependency() {
    let manifest = include_str!("../Cargo.toml");
    let normal_dependencies = manifest
        .split_once("[dependencies]")
        .expect("runtime manifest has dependencies")
        .1
        .split_once('[')
        .expect("runtime manifest has a following section")
        .0;
    let dev_dependencies = manifest
        .split_once("[dev-dependencies]")
        .expect("runtime manifest has dev-dependencies")
        .1;
    assert!(!normal_dependencies.contains("betelgeuze-reference-physics"));
    assert!(dev_dependencies.contains("betelgeuze-reference-physics"));
}

#[test]
#[cfg(feature = "hip")]
fn hip_matches_the_cpu_and_independent_oracle_without_fallback() {
    if !runtime::Context::backend_available(runtime::Backend::Hip, 0)
        .expect("HIP availability query succeeds")
    {
        assert_ne!(
            std::env::var("BG_REQUIRE_HIP_DEVICE").as_deref(),
            Ok("1"),
            "BG_REQUIRE_HIP_DEVICE=1 but no HIP device is available at ordinal zero"
        );
        eprintln!("SKIP: HIP feature was compiled without a visible device zero");
        return;
    }
    for fixture in fixtures() {
        let expected = oracle::evaluate(&fixture.input)
            .unwrap_or_else(|error| panic!("{} oracle evaluation failed: {error}", fixture.name));
        let native = native_fixture(&fixture, runtime::Backend::CppCpuReference);
        let cpu = native
            .context
            .evaluate(&native.system, &native.forcefield)
            .unwrap_or_else(|error| panic!("{} CPU evaluation failed: {error}", fixture.name));
        let hip_context = runtime::Context::new(runtime::ContextOptions::hip(0))
            .unwrap_or_else(|error| panic!("{} HIP context failed: {error}", fixture.name));
        assert_eq!(
            hip_context.backend().expect("HIP backend query succeeds"),
            runtime::Backend::Hip
        );
        let hip = hip_context
            .evaluate(&native.system, &native.forcefield)
            .unwrap_or_else(|error| panic!("{} HIP evaluation failed: {error}", fixture.name));
        let repeated = hip_context
            .evaluate(&native.system, &native.forcefield)
            .unwrap_or_else(|error| {
                panic!("{} repeated HIP evaluation failed: {error}", fixture.name)
            });

        assert_energy_close(fixture.name, hip.energy, expected);
        assert_runtime_energy_bits_equal(
            fixture.name,
            "repeated HIP evaluation",
            hip.energy,
            repeated.energy,
        );
        for axis in 0..3 {
            let cpu_channel = force_channel(&cpu.forces, axis);
            let hip_channel = force_channel(&hip.forces, axis);
            let repeated_channel = force_channel(&repeated.forces, axis);
            for atom in 0..cpu_channel.len() {
                let tolerance = 1.0e-10 * (1.0 + cpu_channel[atom].abs());
                assert!(
                    (hip_channel[atom] - cpu_channel[atom]).abs() <= tolerance,
                    "{} CPU/HIP force mismatch at atom {atom}, axis {axis}: CPU={:.17e}, HIP={:.17e}",
                    fixture.name,
                    cpu_channel[atom],
                    hip_channel[atom]
                );
                assert_eq!(
                    hip_channel[atom].to_bits(),
                    repeated_channel[atom].to_bits(),
                    "{} repeated HIP force changed bits at atom {atom}, axis {axis}",
                    fixture.name
                );
            }
        }
    }
}

fn fixtures() -> Vec<Fixture> {
    vec![
        isolated_bond(),
        isolated_angle(),
        isolated_signed_torsion(),
        isolated_lennard_jones(),
        isolated_screened_coulomb(),
        explicit_scales_and_exclusion(),
        periodic_minimum_image(),
        switching_window(),
        combined_system(),
    ]
}

fn isolated_bond() -> Fixture {
    let mut input = inert_input(vec![p(0.0, 0.0, 0.0), p(2.0, 0.0, 0.0)]);
    input.bonds.push(oracle::HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: 1.5,
        force_constant_kcal_per_mol_angstrom2: 8.0,
    });
    Fixture {
        name: "isolated_bond",
        input,
        exact: Some(ExactFixture::BondOnly),
    }
}

fn isolated_angle() -> Fixture {
    let mut input = inert_input(vec![p(1.2, 0.1, 0.4), p(0.1, -0.2, 0.3), p(-0.1, 1.4, 0.7)]);
    input.angles.push(oracle::HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.1,
        force_constant_kcal_per_mol_radian2: 6.5,
    });
    Fixture {
        name: "isolated_angle",
        input,
        exact: None,
    }
}

fn isolated_signed_torsion() -> Fixture {
    let mut input = inert_input(vec![
        p(0.0, 1.0, 0.0),
        p(0.0, 0.0, 0.0),
        p(1.0, 0.0, 0.0),
        p(1.0, 0.0, 1.0),
    ]);
    input.torsions.push(oracle::PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 1,
        phase_radians: 0.37,
        amplitude_kcal_per_mol: 1.7,
    });
    Fixture {
        name: "signed_torsion",
        input,
        exact: None,
    }
}

fn isolated_lennard_jones() -> Fixture {
    let positions = vec![p(0.0, 0.0, 0.0), p(2.0, 0.0, 0.0)];
    let atoms = vec![atom(1.0, 1.0, 0.0), atom(1.0, 1.0, 0.0)];
    let mut input = oracle::OracleInput::new(positions, atoms);
    input.nonbonded = settings(4.0, 3.0, 1.0, 0.0);
    Fixture {
        name: "isolated_lennard_jones",
        input,
        exact: Some(ExactFixture::LennardJonesOnly),
    }
}

fn isolated_screened_coulomb() -> Fixture {
    let positions = vec![p(-0.2, 0.4, 0.1), p(1.1, -0.3, 0.6)];
    let atoms = vec![atom(1.0, 0.0, 0.8), atom(1.0, 0.0, -0.6)];
    let mut input = oracle::OracleInput::new(positions, atoms);
    input.nonbonded = settings(4.0, 3.0, 2.3, 0.17);
    Fixture {
        name: "isolated_screened_coulomb",
        input,
        exact: None,
    }
}

fn explicit_scales_and_exclusion() -> Fixture {
    let positions = vec![p(-0.6, 0.2, 0.1), p(0.7, -0.4, 0.3), p(1.4, 1.0, -0.5)];
    let atoms = vec![
        atom(1.1, 0.8, 0.5),
        atom(1.5, 1.25, -0.4),
        atom(1.3, 0.45, 0.7),
    ];
    let mut input = oracle::OracleInput::new(positions, atoms);
    input.nonbonded = settings(5.0, 4.0, 1.7, 0.08);
    input.exclusions.push(oracle::PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    input.pair_scales.push(oracle::PairScale {
        atom_i: 2,
        atom_j: 1,
        lennard_jones_scale: 0.25,
        coulomb_scale: 0.4,
    });
    Fixture {
        name: "explicit_scales_and_exclusion",
        input,
        exact: None,
    }
}

fn periodic_minimum_image() -> Fixture {
    let positions = vec![p(0.2, 0.3, -0.1), p(9.1, 0.8, 0.2)];
    let atoms = vec![atom(1.2, 0.7, 0.4), atom(1.4, 0.9, -0.6)];
    let mut input = oracle::OracleInput::new(positions, atoms);
    input.cell = Some(oracle::OrthorhombicCell {
        lengths_angstrom: [10.0, 12.0, 14.0],
        periodic_axes: [true, false, false],
    });
    input.nonbonded = settings(4.5, 3.5, 1.4, 0.11);
    Fixture {
        name: "periodic_minimum_image",
        input,
        exact: None,
    }
}

fn switching_window() -> Fixture {
    let positions = vec![p(0.0, 0.0, 0.0), p(3.0, 0.0, 0.0)];
    let atoms = vec![atom(1.4, 0.8, 0.5), atom(1.8, 1.25, -0.3)];
    let mut input = oracle::OracleInput::new(positions, atoms);
    input.nonbonded = settings(4.0, 2.0, 1.6, 0.0);
    Fixture {
        name: "switching_window",
        input,
        exact: None,
    }
}

fn combined_system() -> Fixture {
    let positions = vec![
        p(-0.8, 0.2, 0.3),
        p(0.3, -0.4, 0.1),
        p(1.4, 0.5, -0.2),
        p(2.0, 1.1, 0.9),
        p(-1.3, 1.4, -0.5),
    ];
    let atoms = vec![
        atom(1.1, 0.7, 0.35),
        atom(1.4, 0.9, -0.55),
        atom(1.3, 0.5, 0.25),
        atom(1.6, 1.1, -0.30),
        atom(1.2, 0.6, 0.25),
    ];
    let mut input = oracle::OracleInput::new(positions, atoms);
    input.nonbonded = settings(5.0, 4.0, 1.8, 0.06);
    input.bonds.extend([
        oracle::HarmonicBond {
            atom_i: 0,
            atom_j: 1,
            equilibrium_angstrom: 1.25,
            force_constant_kcal_per_mol_angstrom2: 7.5,
        },
        oracle::HarmonicBond {
            atom_i: 1,
            atom_j: 2,
            equilibrium_angstrom: 1.35,
            force_constant_kcal_per_mol_angstrom2: 5.0,
        },
    ]);
    input.angles.push(oracle::HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.8,
        force_constant_kcal_per_mol_radian2: 4.2,
    });
    input.torsions.push(oracle::PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 3,
        phase_radians: -0.4,
        amplitude_kcal_per_mol: 0.85,
    });
    input.exclusions.push(oracle::PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    input.pair_scales.push(oracle::PairScale {
        atom_i: 3,
        atom_j: 0,
        lennard_jones_scale: 0.35,
        coulomb_scale: 0.65,
    });
    Fixture {
        name: "combined_system",
        input,
        exact: None,
    }
}

fn inert_input(positions: Vec<oracle::Position>) -> oracle::OracleInput {
    let atoms = positions.iter().map(|_| atom(1.0, 0.0, 0.0)).collect();
    oracle::OracleInput::new(positions, atoms)
}

const fn p(x_angstrom: f64, y_angstrom: f64, z_angstrom: f64) -> oracle::Position {
    oracle::Position::new(x_angstrom, y_angstrom, z_angstrom)
}

const fn atom(
    sigma_angstrom: f64,
    epsilon_kcal_per_mol: f64,
    charge_elementary: f64,
) -> oracle::AtomNonbonded {
    oracle::AtomNonbonded {
        sigma_angstrom,
        epsilon_kcal_per_mol,
        charge_elementary,
    }
}

const fn settings(
    cutoff_angstrom: f64,
    switch_start_angstrom: f64,
    dielectric: f64,
    screening_kappa_per_angstrom: f64,
) -> oracle::NonbondedSettings {
    oracle::NonbondedSettings {
        cutoff_angstrom,
        switch_start_angstrom,
        dielectric,
        screening_kappa_per_angstrom,
        minimum_pair_distance_angstrom: 1.0e-6,
    }
}

fn native_fixture(fixture: &Fixture, backend: runtime::Backend) -> NativeFixture {
    let input = &fixture.input;
    let x: Vec<_> = input
        .positions
        .iter()
        .map(|position| position.x_angstrom)
        .collect();
    let y: Vec<_> = input
        .positions
        .iter()
        .map(|position| position.y_angstrom)
        .collect();
    let z: Vec<_> = input
        .positions
        .iter()
        .map(|position| position.z_angstrom)
        .collect();
    let masses = vec![12.0; input.positions.len()];
    let charges: Vec<_> = input
        .atom_nonbonded
        .iter()
        .map(|atom| atom.charge_elementary)
        .collect();
    let particles =
        runtime::ParticleSoa::new(runtime::PositionSoa::new(&x, &y, &z), &masses, &charges);
    let system = runtime::System::new(particles)
        .unwrap_or_else(|error| panic!("{} system conversion failed: {error}", fixture.name));

    let atoms: Vec<_> = input
        .atom_nonbonded
        .iter()
        .map(|row| runtime::AtomNonbonded {
            sigma_angstrom: row.sigma_angstrom,
            epsilon_kcal_per_mol: row.epsilon_kcal_per_mol,
        })
        .collect();
    let bonds: Vec<_> = input
        .bonds
        .iter()
        .map(|row| runtime::HarmonicBond {
            atom_i: row.atom_i,
            atom_j: row.atom_j,
            equilibrium_angstrom: row.equilibrium_angstrom,
            force_constant_kcal_per_mol_angstrom2: row.force_constant_kcal_per_mol_angstrom2,
        })
        .collect();
    let angles: Vec<_> = input
        .angles
        .iter()
        .map(|row| runtime::HarmonicAngle {
            atom_i: row.atom_i,
            atom_j: row.atom_j,
            atom_k: row.atom_k,
            equilibrium_radians: row.equilibrium_radians,
            force_constant_kcal_per_mol_radian2: row.force_constant_kcal_per_mol_radian2,
        })
        .collect();
    let torsions: Vec<_> = input
        .torsions
        .iter()
        .map(|row| runtime::PeriodicTorsion {
            atom_i: row.atom_i,
            atom_j: row.atom_j,
            atom_k: row.atom_k,
            atom_l: row.atom_l,
            periodicity: row.periodicity,
            phase_radians: row.phase_radians,
            amplitude_kcal_per_mol: row.amplitude_kcal_per_mol,
        })
        .collect();
    let exclusions: Vec<_> = input
        .exclusions
        .iter()
        .map(|row| runtime::PairExclusion {
            atom_i: row.atom_i,
            atom_j: row.atom_j,
        })
        .collect();
    let pair_scales: Vec<_> = input
        .pair_scales
        .iter()
        .map(|row| runtime::PairScale {
            atom_i: row.atom_i,
            atom_j: row.atom_j,
            lennard_jones_scale: row.lennard_jones_scale,
            coulomb_scale: row.coulomb_scale,
        })
        .collect();
    let cell = input.cell.map(|cell| runtime::OrthorhombicCell {
        lengths_angstrom: cell.lengths_angstrom,
        periodic_axes: cell.periodic_axes,
    });
    let nonbonded = runtime::NonbondedSettings {
        cutoff_angstrom: input.nonbonded.cutoff_angstrom,
        switch_start_angstrom: input.nonbonded.switch_start_angstrom,
        dielectric: input.nonbonded.dielectric,
        screening_kappa_per_angstrom: input.nonbonded.screening_kappa_per_angstrom,
        minimum_pair_distance_angstrom: input.nonbonded.minimum_pair_distance_angstrom,
    };
    let mut forcefield_input = runtime::ForceFieldInput::new(&atoms);
    forcefield_input.bonds = &bonds;
    forcefield_input.angles = &angles;
    forcefield_input.torsions = &torsions;
    forcefield_input.exclusions = &exclusions;
    forcefield_input.pair_scales = &pair_scales;
    forcefield_input.cell = cell;
    forcefield_input.nonbonded = nonbonded;
    let forcefield = runtime::ForceField::new(forcefield_input)
        .unwrap_or_else(|error| panic!("{} force-field conversion failed: {error}", fixture.name));
    let options = match backend {
        runtime::Backend::CppCpuReference => runtime::ContextOptions::cpu_reference(),
        runtime::Backend::RustCpu => runtime::ContextOptions::rust_cpu(),
        runtime::Backend::HipSafe => runtime::ContextOptions::hip_safe(0),
        _ => panic!("non-safe backend passed to native_fixture"),
    };
    let context = runtime::Context::new(options)
        .unwrap_or_else(|error| panic!("{} native context failed: {error}", fixture.name));

    NativeFixture {
        context,
        system,
        forcefield,
    }
}

const fn backend_name(backend: runtime::Backend) -> &'static str {
    match backend {
        runtime::Backend::CppCpuReference => "cpp_cpu_reference",
        runtime::Backend::RustCpu => "rust_cpu",
        runtime::Backend::Auto => "auto",
        runtime::Backend::HipSafe => "hip_safe",
        runtime::Backend::HipFast => "hip_fast",
    }
}

fn assert_close_cross_backend(
    fixture: &str,
    backend: runtime::Backend,
    field: &str,
    left: f64,
    right: f64,
) {
    let difference = (left - right).abs();
    let tolerance = CROSS_BACKEND_TOLERANCE * (1.0 + left.abs().max(right.abs()));
    assert!(
        difference <= tolerance,
        "{fixture} {field}: cpp_cpu_reference={left:.17e}, {}={right:.17e}, \
         |delta|={difference:.3e} > {tolerance:.3e}",
        backend_name(backend)
    );
}

fn assert_energy_close(
    fixture: &str,
    actual: runtime::EnergyComponents,
    expected: oracle::EnergyComponents,
) {
    let actual_components = runtime_energy_values(actual);
    let expected_components = oracle_energy_values(expected);
    for ((name, actual), (_, expected)) in actual_components
        .into_iter()
        .zip(expected_components.into_iter())
    {
        let difference = (actual - expected).abs();
        let tolerance = ENERGY_TOLERANCE * (1.0 + actual.abs().max(expected.abs()));
        assert!(
            difference <= tolerance,
            "{fixture} {name}: CPU={actual:.17e}, oracle={expected:.17e}, \
             |delta|={difference:.3e} > {tolerance:.3e}"
        );
    }
}

fn assert_runtime_energy_bits_equal(
    fixture: &str,
    comparison: &str,
    left: runtime::EnergyComponents,
    right: runtime::EnergyComponents,
) {
    for ((name, left), (_, right)) in runtime_energy_values(left)
        .into_iter()
        .zip(runtime_energy_values(right))
    {
        assert_eq!(
            left.to_bits(),
            right.to_bits(),
            "{fixture} {comparison} changed {name} bits"
        );
    }
}

fn assert_exact_algebraic_fixture(
    fixture: &str,
    exact: ExactFixture,
    actual: runtime::EnergyComponents,
    expected: oracle::EnergyComponents,
) {
    let frozen: [f64; 6] = match exact {
        ExactFixture::BondOnly => [1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ExactFixture::LennardJonesOnly => {
            let lennard_jones = -63.0 / 1024.0;
            [0.0, 0.0, 0.0, lennard_jones, 0.0, lennard_jones]
        }
    };
    let actual = runtime_energy_values(actual);
    let expected = oracle_energy_values(expected);
    for index in 0..frozen.len() {
        assert_eq!(
            expected[index].1.to_bits(),
            frozen[index].to_bits(),
            "{fixture} oracle algebraic fixture drifted for {}",
            expected[index].0
        );
        assert_eq!(
            actual[index].1.to_bits(),
            frozen[index].to_bits(),
            "{fixture} CPU algebraic fixture drifted for {}",
            actual[index].0
        );
    }
}

fn finite_difference_force(fixture: &Fixture, atom: usize, axis: usize) -> f64 {
    let mut plus = fixture.input.clone();
    let mut minus = fixture.input.clone();
    *position_component(&mut plus.positions[atom], axis) += FORCE_DIFFERENCE_STEP_ANGSTROM;
    *position_component(&mut minus.positions[atom], axis) -= FORCE_DIFFERENCE_STEP_ANGSTROM;
    let plus_energy = oracle::evaluate(&plus)
        .unwrap_or_else(|error| panic!("{} +h oracle evaluation failed: {error}", fixture.name))
        .total_kcal_per_mol();
    let minus_energy = oracle::evaluate(&minus)
        .unwrap_or_else(|error| panic!("{} -h oracle evaluation failed: {error}", fixture.name))
        .total_kcal_per_mol();
    -(plus_energy - minus_energy) / (2.0 * FORCE_DIFFERENCE_STEP_ANGSTROM)
}

fn position_component(position: &mut oracle::Position, axis: usize) -> &mut f64 {
    match axis {
        0 => &mut position.x_angstrom,
        1 => &mut position.y_angstrom,
        2 => &mut position.z_angstrom,
        _ => unreachable!("Cartesian axis lies in 0..3"),
    }
}

fn native_force_component(forces: &runtime::ForceSoaOwned, atom: usize, axis: usize) -> f64 {
    force_channel(forces, axis)[atom]
}

fn force_channel(forces: &runtime::ForceSoaOwned, axis: usize) -> &[f64] {
    match axis {
        0 => &forces.x_kcal_per_mol_angstrom,
        1 => &forces.y_kcal_per_mol_angstrom,
        2 => &forces.z_kcal_per_mol_angstrom,
        _ => unreachable!("Cartesian axis lies in 0..3"),
    }
}

fn runtime_energy_values(energy: runtime::EnergyComponents) -> [(&'static str, f64); 6] {
    [
        ("harmonic bond", energy.harmonic_bond_kcal_per_mol),
        ("harmonic angle", energy.harmonic_angle_kcal_per_mol),
        ("periodic torsion", energy.periodic_torsion_kcal_per_mol),
        ("Lennard-Jones", energy.lennard_jones_kcal_per_mol),
        ("Coulomb", energy.coulomb_kcal_per_mol),
        ("total", energy.total_kcal_per_mol),
    ]
}

fn oracle_energy_values(energy: oracle::EnergyComponents) -> [(&'static str, f64); 6] {
    [
        ("harmonic bond", energy.harmonic_bond_kcal_per_mol),
        ("harmonic angle", energy.harmonic_angle_kcal_per_mol),
        ("periodic torsion", energy.periodic_torsion_kcal_per_mol),
        ("Lennard-Jones", energy.lennard_jones_kcal_per_mol),
        ("Coulomb", energy.coulomb_kcal_per_mol),
        ("total", energy.total_kcal_per_mol()),
    ]
}
