use betelgeuze_reference_dynamics as oracle;
use betelgeuze_runtime as runtime;

const EQUILIBRIUM_ANGSTROM: f64 = 1.0;
const FORCE_CONSTANT: f64 = 20.0;
const TIMESTEP_FS: f64 = 0.25;

#[test]
fn independent_dynamics_oracle_is_dev_only() {
    let manifest = include_str!("../Cargo.toml");
    let mut section = "";
    let mut found_dev_dependency = false;
    for line in manifest.lines() {
        let line = line.trim();
        if line.starts_with('[') && line.ends_with(']') {
            section = line;
            continue;
        }
        if line.starts_with("betelgeuze-reference-dynamics") {
            assert!(
                section == "[dev-dependencies]" || section.ends_with(".dev-dependencies]"),
                "independent dynamics oracle leaked into product section {section}"
            );
            found_dev_dependency = true;
        }
    }
    assert!(found_dev_dependency);
}

#[test]
fn velocity_verlet_matches_the_independent_scalar_oracle() {
    let context = runtime::Context::new(runtime::ContextOptions::cpu()).unwrap();
    let mut simulation = native_simulation(runtime::SimulationOptions {
        integrator: runtime::Integrator::VelocityVerlet,
        timestep_femtoseconds: TIMESTEP_FS,
        ..runtime::SimulationOptions::default()
    });
    let mut state = oracle_state();
    let system = oracle_system();
    let mut provider = harmonic_provider;

    let expected = oracle::integrate_velocity_verlet(
        &system,
        &mut state,
        &mut provider,
        oracle::VerletConfig {
            timestep_fs: TIMESTEP_FS,
            steps: 32,
            constraints: oracle::ConstraintConfig::default(),
        },
    )
    .unwrap();
    let actual = context.integrate(&mut simulation, 32).unwrap();
    let snapshot = simulation.snapshot().unwrap();

    assert_eq!(actual.steps_completed, 32);
    assert_eq!(actual.absolute_step, expected.absolute_step);
    assert_eq!(actual.degrees_of_freedom, 6);
    assert_close(
        actual.potential_kcal_per_mol,
        expected.final_potential_kcal_per_mol,
        2.0e-13,
    );
    assert_close(
        actual.kinetic_kcal_per_mol,
        expected.final_kinetic_kcal_per_mol,
        2.0e-13,
    );
    assert_snapshot_matches_oracle(&snapshot, &state, 2.0e-14);
}

#[test]
fn fixed_seed_baoab_matches_oracle_and_checkpoint_continuation_is_exact() {
    let options = runtime::SimulationOptions {
        integrator: runtime::Integrator::LangevinBaoab,
        timestep_femtoseconds: TIMESTEP_FS,
        temperature_kelvin: 285.0,
        friction_per_femtosecond: 0.015,
        random_seed: 0x0123_4567_89ab_cdef,
    };
    let context = runtime::Context::new(runtime::ContextOptions::cpu()).unwrap();
    let mut uninterrupted = native_simulation(options);
    let mut restarted = native_simulation(options);

    context.integrate(&mut uninterrupted, 7).unwrap();
    let checkpoint = uninterrupted.checkpoint().unwrap();
    let checkpoint_again = uninterrupted.checkpoint().unwrap();
    assert_eq!(checkpoint, checkpoint_again);
    restarted.load_checkpoint(&checkpoint).unwrap();
    assert_snapshot_bits_equal(
        &uninterrupted.snapshot().unwrap(),
        &restarted.snapshot().unwrap(),
    );

    let first_report = context.integrate(&mut uninterrupted, 9).unwrap();
    let second_report = context.integrate(&mut restarted, 9).unwrap();
    assert_eq!(first_report, second_report);
    assert_snapshot_bits_equal(
        &uninterrupted.snapshot().unwrap(),
        &restarted.snapshot().unwrap(),
    );

    let mut oracle_state = oracle_state();
    let oracle_system = oracle_system();
    let mut provider = harmonic_provider;
    let expected = oracle::integrate_baoab(
        &oracle_system,
        &mut oracle_state,
        &mut provider,
        oracle::LangevinConfig {
            timestep_fs: TIMESTEP_FS,
            steps: 16,
            temperature_kelvin: options.temperature_kelvin,
            friction_per_fs: options.friction_per_femtosecond,
            seed: options.random_seed,
            constraints: oracle::ConstraintConfig::default(),
        },
    )
    .unwrap();
    assert_eq!(first_report.absolute_step, expected.absolute_step);
    assert_close(
        first_report.potential_kcal_per_mol,
        expected.final_potential_kcal_per_mol,
        5.0e-12,
    );
    assert_close(
        first_report.kinetic_kcal_per_mol,
        expected.final_kinetic_kcal_per_mol,
        5.0e-12,
    );
    assert_snapshot_matches_oracle(&uninterrupted.snapshot().unwrap(), &oracle_state, 5.0e-13);

    let before_corruption = restarted.snapshot().unwrap();
    let mut wrong_static = native_simulation(runtime::SimulationOptions {
        random_seed: options.random_seed ^ 1,
        ..options
    });
    let wrong_static_before = wrong_static.snapshot().unwrap();
    assert!(wrong_static.load_checkpoint(&checkpoint).is_err());
    assert_snapshot_bits_equal(&wrong_static_before, &wrong_static.snapshot().unwrap());

    let mut corrupt = checkpoint;
    let middle = corrupt.len() / 2;
    corrupt[middle] ^= 0x80;
    assert!(restarted.load_checkpoint(&corrupt).is_err());
    assert_snapshot_bits_equal(&before_corruption, &restarted.snapshot().unwrap());
}

#[test]
fn minimization_constraints_and_zero_step_are_transactional() {
    let context = runtime::Context::new(runtime::ContextOptions::cpu()).unwrap();
    let mut minimization = native_simulation(runtime::SimulationOptions::default());
    let initial = minimization.snapshot().unwrap();
    let minimizer = runtime::MinimizerOptions {
        max_iterations: 1_000,
        max_line_search_steps: 64,
        initial_step_angstrom2_mol_per_kcal: 0.01,
        minimum_step_angstrom2_mol_per_kcal: 1.0e-16,
        energy_tolerance_kcal_per_mol: 0.0,
        force_tolerance_kcal_per_mol_angstrom: 1.0e-9,
        armijo_coefficient: 1.0e-4,
        backtrack_factor: 0.5,
    };
    let report = context.minimize(&mut minimization, minimizer).unwrap();
    assert!(report.converged);
    assert!(report.final_potential_kcal_per_mol < report.initial_potential_kcal_per_mol);
    let minimized = minimization.snapshot().unwrap();
    let separation = minimized.positions.x_angstrom[1] - minimized.positions.x_angstrom[0];
    assert_close(separation, EQUILIBRIUM_ANGSTROM, 1.0e-10);
    assert_ne!(initial.positions, minimized.positions);

    let mut expected_state = oracle_state();
    let mut provider = harmonic_provider;
    let expected_report = oracle::minimize(
        &oracle_system(),
        &mut expected_state,
        &mut provider,
        oracle::MinimizationConfig {
            max_iterations: minimizer.max_iterations,
            force_tolerance_kcal_per_mol_angstrom: minimizer.force_tolerance_kcal_per_mol_angstrom,
            energy_tolerance_kcal_per_mol: minimizer.energy_tolerance_kcal_per_mol,
            initial_step_angstrom2_mol_per_kcal: minimizer.initial_step_angstrom2_mol_per_kcal,
            minimum_step_angstrom2_mol_per_kcal: minimizer.minimum_step_angstrom2_mol_per_kcal,
            armijo_c1: minimizer.armijo_coefficient,
            backtrack_factor: minimizer.backtrack_factor,
            max_backtracks: minimizer.max_line_search_steps,
            constraints: oracle::ConstraintConfig::default(),
        },
    )
    .unwrap();
    assert_eq!(report.iterations, expected_report.iterations);
    assert_eq!(report.converged, expected_report.converged);
    assert_close(
        report.initial_potential_kcal_per_mol,
        expected_report.initial_potential_kcal_per_mol,
        2.0e-13,
    );
    assert_close(
        report.final_potential_kcal_per_mol,
        expected_report.final_potential_kcal_per_mol,
        2.0e-13,
    );
    assert_close(
        report.maximum_force_kcal_per_mol_angstrom,
        expected_report.final_max_force_kcal_per_mol_angstrom,
        2.0e-13,
    );
    assert_snapshot_matches_oracle(&minimized, &expected_state, 2.0e-13);

    let constraints = runtime::DistanceConstraints {
        rows: vec![runtime::DistanceConstraint {
            atom_i: 1,
            atom_j: 0,
            distance_angstrom: EQUILIBRIUM_ANGSTROM,
        }],
        tolerance_angstrom: 1.0e-12,
        velocity_tolerance_angstrom_per_femtosecond: 1.0e-12,
        max_iterations: 64,
    };
    let mut constrained = native_simulation_with_constraints(
        runtime::SimulationOptions {
            integrator: runtime::Integrator::VelocityVerlet,
            timestep_femtoseconds: TIMESTEP_FS,
            ..runtime::SimulationOptions::default()
        },
        &constraints,
    );
    let projected = constrained.snapshot().unwrap();
    assert_close(
        snapshot_distance(&projected, 0, 1),
        EQUILIBRIUM_ANGSTROM,
        constraints.tolerance_angstrom,
    );
    let before_zero = constrained.snapshot().unwrap();
    let zero = context.integrate(&mut constrained, 0).unwrap();
    assert_eq!(zero.steps_completed, 0);
    assert_snapshot_bits_equal(&before_zero, &constrained.snapshot().unwrap());

    let constrained_report = context.integrate(&mut constrained, 128).unwrap();
    assert_eq!(constrained_report.degrees_of_freedom, 5);
    let final_state = constrained.snapshot().unwrap();
    assert_close(
        snapshot_distance(&final_state, 0, 1),
        EQUILIBRIUM_ANGSTROM,
        2.0e-12,
    );

    let constraint_config = oracle::ConstraintConfig {
        position_tolerance_angstrom: constraints.tolerance_angstrom,
        velocity_tolerance_angstrom_per_fs: constraints.velocity_tolerance_angstrom_per_femtosecond,
        max_iterations: constraints.max_iterations,
    };
    let oracle_system = oracle::System::new(
        vec![12.0, 16.0],
        vec![oracle::DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: EQUILIBRIUM_ANGSTROM,
        }],
        None,
    )
    .unwrap();
    let mut oracle_state = oracle_state();
    oracle::project_positions(
        &oracle_system,
        &mut oracle_state.positions_angstrom,
        constraint_config,
    )
    .unwrap();
    oracle::project_velocities(
        &oracle_system,
        &oracle_state.positions_angstrom,
        &mut oracle_state.velocities_angstrom_per_fs,
        constraint_config,
    )
    .unwrap();
    oracle::integrate_velocity_verlet(
        &oracle_system,
        &mut oracle_state,
        &mut harmonic_provider,
        oracle::VerletConfig {
            timestep_fs: TIMESTEP_FS,
            steps: 128,
            constraints: constraint_config,
        },
    )
    .unwrap();
    assert_snapshot_matches_oracle(&final_state, &oracle_state, 2.0e-12);
}

#[test]
fn periodic_constraint_uses_the_same_unwrapped_half_open_image_as_oracle() {
    let context = runtime::Context::new(runtime::ContextOptions::cpu()).unwrap();
    let config = runtime::DistanceConstraints {
        rows: vec![runtime::DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: 0.8,
        }],
        tolerance_angstrom: 1.0e-12,
        velocity_tolerance_angstrom_per_femtosecond: 1.0e-12,
        max_iterations: 64,
    };
    let mut native = native_periodic_simulation(&config);
    let report = context.integrate(&mut native, 64).unwrap();
    assert_eq!(report.degrees_of_freedom, 5);

    let oracle_config = oracle::ConstraintConfig {
        position_tolerance_angstrom: config.tolerance_angstrom,
        velocity_tolerance_angstrom_per_fs: config.velocity_tolerance_angstrom_per_femtosecond,
        max_iterations: config.max_iterations,
    };
    let oracle_system = oracle::System::new(
        vec![12.0, 16.0],
        vec![oracle::DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: 0.8,
        }],
        Some(oracle::OrthorhombicCell {
            lengths_angstrom: [10.0, 10.0, 10.0],
            periodic_axes: [true, false, false],
        }),
    )
    .unwrap();
    let mut oracle_state = oracle::State::new(
        vec![[0.1, 0.0, 0.0], [9.3, 0.0, 0.0]],
        vec![[0.001, 0.0005, 0.0], [-0.001, -0.00025, 0.00075]],
    );
    oracle::project_positions(
        &oracle_system,
        &mut oracle_state.positions_angstrom,
        oracle_config,
    )
    .unwrap();
    oracle::project_velocities(
        &oracle_system,
        &oracle_state.positions_angstrom,
        &mut oracle_state.velocities_angstrom_per_fs,
        oracle_config,
    )
    .unwrap();
    let mut provider = |positions: &[[f64; 3]], forces: &mut [[f64; 3]]| {
        periodic_harmonic_provider(positions, forces)
    };
    oracle::integrate_velocity_verlet(
        &oracle_system,
        &mut oracle_state,
        &mut provider,
        oracle::VerletConfig {
            timestep_fs: TIMESTEP_FS,
            steps: 64,
            constraints: oracle_config,
        },
    )
    .unwrap();
    let actual = native.snapshot().unwrap();
    assert_snapshot_matches_oracle(&actual, &oracle_state, 2.0e-12);
    assert!(actual.positions.x_angstrom[1] > 9.0);
}

#[cfg(feature = "hip")]
#[test]
fn hip_short_dynamics_matches_cpu_without_backend_fallback() {
    if !runtime::Context::backend_available(runtime::Backend::Hip, 0).unwrap() {
        assert_ne!(
            std::env::var("BG_REQUIRE_HIP_DEVICE").as_deref(),
            Ok("1"),
            "BG_REQUIRE_HIP_DEVICE=1 but HIP device zero is unavailable"
        );
        eprintln!("SKIP: no compatible HIP device zero is visible");
        return;
    }
    let cpu = runtime::Context::new(runtime::ContextOptions::cpu()).unwrap();
    let hip = runtime::Context::new(runtime::ContextOptions::hip(0)).unwrap();
    assert_eq!(hip.backend().unwrap(), runtime::Backend::Hip);

    for integrator in [
        runtime::Integrator::VelocityVerlet,
        runtime::Integrator::LangevinBaoab,
    ] {
        let options = runtime::SimulationOptions {
            integrator,
            timestep_femtoseconds: TIMESTEP_FS,
            temperature_kelvin: 300.0,
            friction_per_femtosecond: 0.01,
            random_seed: 0xa5a5_0123_dead_beef,
        };
        let mut cpu_simulation = native_simulation(options);
        let mut hip_simulation = native_simulation(options);
        let cpu_report = cpu.integrate(&mut cpu_simulation, 24).unwrap();
        let hip_report = hip.integrate(&mut hip_simulation, 24).unwrap();
        assert_eq!(cpu_report.steps_completed, hip_report.steps_completed);
        assert_eq!(cpu_report.absolute_step, hip_report.absolute_step);
        assert_eq!(cpu_report.degrees_of_freedom, hip_report.degrees_of_freedom);
        assert_close(
            hip_report.potential_kcal_per_mol,
            cpu_report.potential_kcal_per_mol,
            2.0e-9,
        );
        assert_close(
            hip_report.kinetic_kcal_per_mol,
            cpu_report.kinetic_kcal_per_mol,
            2.0e-9,
        );
        let cpu_snapshot = cpu_simulation.snapshot().unwrap();
        let hip_snapshot = hip_simulation.snapshot().unwrap();
        for atom in 0..cpu_snapshot.len() {
            for (cpu_value, hip_value) in [
                (
                    cpu_snapshot.positions.x_angstrom[atom],
                    hip_snapshot.positions.x_angstrom[atom],
                ),
                (
                    cpu_snapshot.positions.y_angstrom[atom],
                    hip_snapshot.positions.y_angstrom[atom],
                ),
                (
                    cpu_snapshot.positions.z_angstrom[atom],
                    hip_snapshot.positions.z_angstrom[atom],
                ),
                (
                    cpu_snapshot.velocities.x_angstrom_per_femtosecond[atom],
                    hip_snapshot.velocities.x_angstrom_per_femtosecond[atom],
                ),
                (
                    cpu_snapshot.velocities.y_angstrom_per_femtosecond[atom],
                    hip_snapshot.velocities.y_angstrom_per_femtosecond[atom],
                ),
                (
                    cpu_snapshot.velocities.z_angstrom_per_femtosecond[atom],
                    hip_snapshot.velocities.z_angstrom_per_femtosecond[atom],
                ),
            ] {
                assert_close(hip_value, cpu_value, 2.0e-9);
            }
        }
    }
}

fn native_simulation(options: runtime::SimulationOptions) -> runtime::Simulation {
    native_simulation_with_constraints(options, &runtime::DistanceConstraints::default())
}

fn native_simulation_with_constraints(
    options: runtime::SimulationOptions,
    constraints: &runtime::DistanceConstraints,
) -> runtime::Simulation {
    let position_x = [0.0, 1.2];
    let position_y = [0.0, 0.0];
    let position_z = [0.0, 0.0];
    let velocity_x = [0.002, -0.001];
    let velocity_y = [0.0005, -0.00025];
    let velocity_z = [0.0, 0.00075];
    let masses = [12.0, 16.0];
    let charges = [0.0, 0.0];
    let particles = runtime::ParticleSoa::new(
        runtime::PositionSoa::new(&position_x, &position_y, &position_z),
        &masses,
        &charges,
    )
    .with_velocities(runtime::VelocitySoa::new(
        &velocity_x,
        &velocity_y,
        &velocity_z,
    ));
    let system = runtime::System::new(particles).unwrap();

    let atoms = [
        runtime::AtomNonbonded {
            sigma_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.0,
        },
        runtime::AtomNonbonded {
            sigma_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.0,
        },
    ];
    let bonds = [runtime::HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: EQUILIBRIUM_ANGSTROM,
        force_constant_kcal_per_mol_angstrom2: FORCE_CONSTANT,
    }];
    let mut input = runtime::ForceFieldInput::new(&atoms);
    input.bonds = &bonds;
    let forcefield = runtime::ForceField::new(input).unwrap();
    runtime::Simulation::new(&system, &forcefield, constraints, options).unwrap()
}

fn native_periodic_simulation(constraints: &runtime::DistanceConstraints) -> runtime::Simulation {
    let position_x = [0.1, 9.3];
    let zeros = [0.0, 0.0];
    let velocity_x = [0.001, -0.001];
    let velocity_y = [0.0005, -0.00025];
    let velocity_z = [0.0, 0.00075];
    let masses = [12.0, 16.0];
    let particles = runtime::ParticleSoa::new(
        runtime::PositionSoa::new(&position_x, &zeros, &zeros),
        &masses,
        &zeros,
    )
    .with_velocities(runtime::VelocitySoa::new(
        &velocity_x,
        &velocity_y,
        &velocity_z,
    ));
    let system = runtime::System::new(particles).unwrap();
    let atoms = [
        runtime::AtomNonbonded {
            sigma_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.0,
        },
        runtime::AtomNonbonded {
            sigma_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.0,
        },
    ];
    let bonds = [runtime::HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: 0.8,
        force_constant_kcal_per_mol_angstrom2: FORCE_CONSTANT,
    }];
    let mut input = runtime::ForceFieldInput::new(&atoms);
    input.bonds = &bonds;
    input.cell = Some(runtime::OrthorhombicCell {
        lengths_angstrom: [10.0, 10.0, 10.0],
        periodic_axes: [true, false, false],
    });
    input.nonbonded.cutoff_angstrom = 4.0;
    input.nonbonded.switch_start_angstrom = 3.0;
    let forcefield = runtime::ForceField::new(input).unwrap();
    runtime::Simulation::new(
        &system,
        &forcefield,
        constraints,
        runtime::SimulationOptions {
            integrator: runtime::Integrator::VelocityVerlet,
            timestep_femtoseconds: TIMESTEP_FS,
            ..runtime::SimulationOptions::default()
        },
    )
    .unwrap()
}

fn oracle_system() -> oracle::System {
    oracle::System::new(vec![12.0, 16.0], Vec::new(), None).unwrap()
}

fn oracle_state() -> oracle::State {
    oracle::State::new(
        vec![[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
        vec![[0.002, 0.0005, 0.0], [-0.001, -0.00025, 0.00075]],
    )
}

fn harmonic_provider(
    positions: &[[f64; 3]],
    forces: &mut [[f64; 3]],
) -> Result<f64, oracle::DynamicsError> {
    let displacement = [
        positions[0][0] - positions[1][0],
        positions[0][1] - positions[1][1],
        positions[0][2] - positions[1][2],
    ];
    let distance = (displacement[0] * displacement[0]
        + displacement[1] * displacement[1]
        + displacement[2] * displacement[2])
        .sqrt();
    if distance == 0.0 || !distance.is_finite() {
        return Err(oracle::DynamicsError::force_provider(
            "harmonic distance is degenerate",
        ));
    }
    let extension = distance - EQUILIBRIUM_ANGSTROM;
    let scale = -FORCE_CONSTANT * extension / distance;
    forces[0] = [
        scale * displacement[0],
        scale * displacement[1],
        scale * displacement[2],
    ];
    forces[1] = [-forces[0][0], -forces[0][1], -forces[0][2]];
    Ok(0.5 * FORCE_CONSTANT * extension * extension)
}

fn periodic_harmonic_provider(
    positions: &[[f64; 3]],
    forces: &mut [[f64; 3]],
) -> Result<f64, oracle::DynamicsError> {
    let mut displacement = [
        positions[0][0] - positions[1][0],
        positions[0][1] - positions[1][1],
        positions[0][2] - positions[1][2],
    ];
    displacement[0] -= 10.0 * (displacement[0] / 10.0 + 0.5).floor();
    let distance = (displacement[0] * displacement[0]
        + displacement[1] * displacement[1]
        + displacement[2] * displacement[2])
        .sqrt();
    if distance == 0.0 || !distance.is_finite() {
        return Err(oracle::DynamicsError::force_provider(
            "periodic harmonic distance is degenerate",
        ));
    }
    let extension = distance - 0.8;
    let scale = -FORCE_CONSTANT * extension / distance;
    forces[0] = [
        scale * displacement[0],
        scale * displacement[1],
        scale * displacement[2],
    ];
    forces[1] = [-forces[0][0], -forces[0][1], -forces[0][2]];
    Ok(0.5 * FORCE_CONSTANT * extension * extension)
}

fn assert_snapshot_matches_oracle(
    actual: &runtime::ParticleSnapshot,
    expected: &oracle::State,
    tolerance: f64,
) {
    for atom in 0..actual.len() {
        let actual_position = [
            actual.positions.x_angstrom[atom],
            actual.positions.y_angstrom[atom],
            actual.positions.z_angstrom[atom],
        ];
        let actual_velocity = [
            actual.velocities.x_angstrom_per_femtosecond[atom],
            actual.velocities.y_angstrom_per_femtosecond[atom],
            actual.velocities.z_angstrom_per_femtosecond[atom],
        ];
        for axis in 0..3 {
            assert_close(
                actual_position[axis],
                expected.positions_angstrom[atom][axis],
                tolerance,
            );
            assert_close(
                actual_velocity[axis],
                expected.velocities_angstrom_per_fs[atom][axis],
                tolerance,
            );
        }
    }
}

fn assert_snapshot_bits_equal(left: &runtime::ParticleSnapshot, right: &runtime::ParticleSnapshot) {
    assert_eq!(left.mass_dalton, right.mass_dalton);
    assert_eq!(left.charge_elementary, right.charge_elementary);
    for (left, right) in [
        (&left.positions.x_angstrom, &right.positions.x_angstrom),
        (&left.positions.y_angstrom, &right.positions.y_angstrom),
        (&left.positions.z_angstrom, &right.positions.z_angstrom),
        (
            &left.velocities.x_angstrom_per_femtosecond,
            &right.velocities.x_angstrom_per_femtosecond,
        ),
        (
            &left.velocities.y_angstrom_per_femtosecond,
            &right.velocities.y_angstrom_per_femtosecond,
        ),
        (
            &left.velocities.z_angstrom_per_femtosecond,
            &right.velocities.z_angstrom_per_femtosecond,
        ),
    ] {
        assert_eq!(left.len(), right.len());
        for (left, right) in left.iter().zip(right) {
            assert_eq!(left.to_bits(), right.to_bits());
        }
    }
}

fn snapshot_distance(snapshot: &runtime::ParticleSnapshot, atom_i: usize, atom_j: usize) -> f64 {
    let dx = snapshot.positions.x_angstrom[atom_i] - snapshot.positions.x_angstrom[atom_j];
    let dy = snapshot.positions.y_angstrom[atom_i] - snapshot.positions.y_angstrom[atom_j];
    let dz = snapshot.positions.z_angstrom[atom_i] - snapshot.positions.z_angstrom[atom_j];
    (dx * dx + dy * dy + dz * dz).sqrt()
}

fn assert_close(actual: f64, expected: f64, tolerance: f64) {
    let error = (actual - expected).abs();
    assert!(
        error <= tolerance * (1.0 + expected.abs()),
        "actual={actual:.17e}, expected={expected:.17e}, error={error:.3e}, tolerance={tolerance:.3e}"
    );
}
