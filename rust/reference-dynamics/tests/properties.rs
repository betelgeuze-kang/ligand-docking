use betelgeuze_reference_dynamics::{
    decode_checkpoint, encode_checkpoint, integrate_baoab, integrate_velocity_verlet,
    kinetic_energy_kcal_per_mol, minimize, project_positions, project_velocities,
    temperature_kelvin, ConstraintConfig, DistanceConstraint, DynamicsError, DynamicsErrorCode,
    ForceProvider, LangevinConfig, MinimizationConfig, OrthorhombicCell, State, System,
    VerletConfig,
};

struct ZeroForce;

impl ForceProvider for ZeroForce {
    fn energy_and_forces(
        &mut self,
        _positions: &[[f64; 3]],
        _forces: &mut [[f64; 3]],
    ) -> Result<f64, DynamicsError> {
        Ok(0.0)
    }
}

struct HarmonicBond {
    force_constant: f64,
    equilibrium: f64,
}

impl ForceProvider for HarmonicBond {
    fn energy_and_forces(
        &mut self,
        positions: &[[f64; 3]],
        forces: &mut [[f64; 3]],
    ) -> Result<f64, DynamicsError> {
        let displacement = positions[1][0] - positions[0][0];
        let distance = displacement.abs();
        let extension = distance - self.equilibrium;
        let force = self.force_constant * extension * displacement.signum();
        forces[0][0] = force;
        forces[1][0] = -force;
        Ok(0.5 * self.force_constant * extension * extension)
    }
}

struct HarmonicTargets {
    targets: Vec<[f64; 3]>,
}

impl ForceProvider for HarmonicTargets {
    fn energy_and_forces(
        &mut self,
        positions: &[[f64; 3]],
        forces: &mut [[f64; 3]],
    ) -> Result<f64, DynamicsError> {
        let mut energy = 0.0;
        for atom in 0..positions.len() {
            for axis in 0..3 {
                let delta = positions[atom][axis] - self.targets[atom][axis];
                energy += 0.5 * delta * delta;
                forces[atom][axis] = -delta;
            }
        }
        Ok(energy)
    }
}

fn assert_close(actual: f64, expected: f64, tolerance: f64) {
    assert!(
        (actual - expected).abs() <= tolerance,
        "actual={actual:.17e}, expected={expected:.17e}, tolerance={tolerance:.3e}"
    );
}

fn fixture_bit(case: &str, field: &str) -> u64 {
    include_str!("../fixtures/dynamics_v1.tsv")
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .find_map(|line| {
            let mut fields = line.split('\t');
            let row_case = fields.next()?;
            let row_field = fields.next()?;
            let bits = fields.next()?;
            assert!(fields.next().is_none(), "fixture row has extra columns");
            (row_case == case && row_field == field)
                .then(|| u64::from_str_radix(bits, 16).expect("valid fixture bits"))
        })
        .expect("fixture row exists")
}

fn default_verlet(steps: u64) -> VerletConfig {
    VerletConfig {
        timestep_fs: 0.25,
        steps,
        constraints: ConstraintConfig::default(),
    }
}

fn default_langevin(steps: u64) -> LangevinConfig {
    LangevinConfig {
        timestep_fs: 0.5,
        steps,
        temperature_kelvin: 300.0,
        friction_per_fs: 0.01,
        seed: 0x0123_4567_89AB_CDEF,
        constraints: ConstraintConfig::default(),
    }
}

#[test]
fn pbc_shake_and_rattle_are_mass_weighted_and_keep_positions_unwrapped() {
    let system = System::new(
        vec![1.0, 3.0],
        vec![DistanceConstraint {
            atom_i: 1,
            atom_j: 0,
            distance_angstrom: 1.0,
        }],
        Some(OrthorhombicCell {
            lengths_angstrom: [10.0, 10.0, 10.0],
            periodic_axes: [true, false, false],
        }),
    )
    .expect("valid periodic constrained system");
    assert_eq!(system.constraints()[0].atom_i, 0);
    assert_eq!(system.constraints()[0].atom_j, 1);

    let mut positions = vec![[9.8, 0.0, 0.0], [0.2, 0.0, 0.0]];
    project_positions(&system, &mut positions, ConstraintConfig::default())
        .expect("SHAKE projection succeeds");
    assert_close(positions[0][0], 9.35, 2.0e-15);
    assert_close(positions[1][0], 0.35, 2.0e-15);
    assert!(positions[0][0] > 9.0, "coordinates must not be wrapped");
    assert_close(
        1.0 * (positions[0][0] - 9.8) + 3.0 * (positions[1][0] - 0.2),
        0.0,
        2.0e-15,
    );

    let mut velocities = vec![[2.0, 0.0, 0.0], [-1.0, 0.0, 0.0]];
    project_velocities(
        &system,
        &positions,
        &mut velocities,
        ConstraintConfig::default(),
    )
    .expect("RATTLE projection succeeds");
    assert_close(velocities[0][0], -0.25, 2.0e-15);
    assert_close(velocities[1][0], -0.25, 2.0e-15);
    assert_close(velocities[0][0] + 3.0 * velocities[1][0], -1.0, 2.0e-15);
}

#[test]
fn constrained_drift_reconstructs_velocity_and_preserves_invariants() {
    let system = System::new(
        vec![1.0, 3.0],
        vec![DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: 1.0,
        }],
        None,
    )
    .expect("valid constrained system");
    let mut state = State::new(
        vec![[-0.75, 0.0, 0.0], [0.25, 0.0, 0.0]],
        vec![[0.0, 0.3, 0.0], [0.0, -0.1, 0.0]],
    );
    let initial_center = [
        (state.positions_angstrom[0][0] + 3.0 * state.positions_angstrom[1][0]) / 4.0,
        (state.positions_angstrom[0][1] + 3.0 * state.positions_angstrom[1][1]) / 4.0,
    ];
    let initial_momentum = [
        state.velocities_angstrom_per_fs[0][0] + 3.0 * state.velocities_angstrom_per_fs[1][0],
        state.velocities_angstrom_per_fs[0][1] + 3.0 * state.velocities_angstrom_per_fs[1][1],
    ];
    integrate_velocity_verlet(&system, &mut state, &mut ZeroForce, default_verlet(1))
        .expect("constrained drift succeeds");
    let delta = [
        state.positions_angstrom[0][0] - state.positions_angstrom[1][0],
        state.positions_angstrom[0][1] - state.positions_angstrom[1][1],
    ];
    let relative_velocity = [
        state.velocities_angstrom_per_fs[0][0] - state.velocities_angstrom_per_fs[1][0],
        state.velocities_angstrom_per_fs[0][1] - state.velocities_angstrom_per_fs[1][1],
    ];
    assert_close(
        (delta[0] * delta[0] + delta[1] * delta[1]).sqrt(),
        1.0,
        1.0e-12,
    );
    assert_close(
        delta[0] * relative_velocity[0] + delta[1] * relative_velocity[1],
        0.0,
        1.0e-12,
    );
    assert_close(
        (state.positions_angstrom[0][0] + 3.0 * state.positions_angstrom[1][0]) / 4.0,
        initial_center[0] + 0.25 * initial_momentum[0] / 4.0,
        2.0e-15,
    );
    assert_close(
        (state.positions_angstrom[0][1] + 3.0 * state.positions_angstrom[1][1]) / 4.0,
        initial_center[1] + 0.25 * initial_momentum[1] / 4.0,
        2.0e-15,
    );
}

#[test]
fn unequal_masses_do_not_move_the_cartesian_constrained_minimum() {
    let system = System::new(
        vec![1.0, 100.0],
        vec![DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: 1.0,
        }],
        None,
    )
    .expect("valid unequal-mass system");
    let mut state = State::new(
        vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        vec![[2.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
    );
    let mut provider = HarmonicTargets {
        targets: vec![[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]],
    };
    let report = minimize(
        &system,
        &mut state,
        &mut provider,
        MinimizationConfig {
            max_iterations: 4,
            force_tolerance_kcal_per_mol_angstrom: 0.0,
            energy_tolerance_kcal_per_mol: 0.0,
            initial_step_angstrom2_mol_per_kcal: 1.0,
            minimum_step_angstrom2_mol_per_kcal: 1.0e-12,
            armijo_c1: 1.0e-4,
            backtrack_factor: 0.5,
            max_backtracks: 4,
            constraints: ConstraintConfig::default(),
        },
    )
    .expect("constrained minimization succeeds");
    assert!(report.converged);
    assert_eq!(report.iterations, 1);
    assert_close(state.positions_angstrom[0][0], 1.0, 2.0e-14);
    assert_close(state.positions_angstrom[1][0], 2.0, 2.0e-14);
    assert_close(report.final_potential_kcal_per_mol, 1.0, 2.0e-14);
    assert_close(
        state.velocities_angstrom_per_fs[0][0] - state.velocities_angstrom_per_fs[1][0],
        0.0,
        2.0e-14,
    );
}

#[test]
fn rotating_constrained_minimization_rattles_velocity_at_final_geometry() {
    let system = System::new(
        vec![1.0, 1.0],
        vec![DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: 1.0,
        }],
        None,
    )
    .expect("valid constrained system");
    let mut state = State {
        positions_angstrom: vec![[-0.5, 0.0, 0.0], [0.5, 0.0, 0.0]],
        velocities_angstrom_per_fs: vec![[0.0, 1.0, 0.0], [0.0, -1.0, 0.0]],
        absolute_step: 77,
    };
    let mut provider = HarmonicTargets {
        targets: vec![[0.0, -0.5, 0.0], [0.0, 0.5, 0.0]],
    };
    let report = minimize(
        &system,
        &mut state,
        &mut provider,
        MinimizationConfig {
            max_iterations: 1_000,
            force_tolerance_kcal_per_mol_angstrom: 1.0e-8,
            energy_tolerance_kcal_per_mol: 1.0e-14,
            initial_step_angstrom2_mol_per_kcal: 0.2,
            minimum_step_angstrom2_mol_per_kcal: 1.0e-14,
            armijo_c1: 1.0e-4,
            backtrack_factor: 0.5,
            max_backtracks: 64,
            constraints: ConstraintConfig::default(),
        },
    )
    .expect("rotating constrained minimum converges");
    assert!(report.converged);
    assert_eq!(state.absolute_step, 77);
    let delta = [
        state.positions_angstrom[0][0] - state.positions_angstrom[1][0],
        state.positions_angstrom[0][1] - state.positions_angstrom[1][1],
        state.positions_angstrom[0][2] - state.positions_angstrom[1][2],
    ];
    let relative_velocity = [
        state.velocities_angstrom_per_fs[0][0] - state.velocities_angstrom_per_fs[1][0],
        state.velocities_angstrom_per_fs[0][1] - state.velocities_angstrom_per_fs[1][1],
        state.velocities_angstrom_per_fs[0][2] - state.velocities_angstrom_per_fs[1][2],
    ];
    assert_close(
        delta[0] * relative_velocity[0]
            + delta[1] * relative_velocity[1]
            + delta[2] * relative_velocity[2],
        0.0,
        1.0e-12,
    );
}

#[test]
fn checkpoint_round_trip_corruption_mismatch_and_signed_zero_are_checked() {
    let system = System::new(vec![12.0, 16.0], vec![], None).expect("valid system");
    let state = State {
        positions_angstrom: vec![[-0.0, 1.25, -2.5], [3.75, -4.0, 0.0]],
        velocities_angstrom_per_fs: vec![[0.0, -0.0, 0.125], [-0.25, 0.5, -0.75]],
        absolute_step: 42,
    };
    let bytes = encode_checkpoint(&system, &state).expect("checkpoint encoding succeeds");
    assert_eq!(bytes.len(), 96 + 48 * 2);
    let decoded = decode_checkpoint(&system, &bytes).expect("checkpoint round trip succeeds");
    assert_eq!(decoded, state);
    assert_eq!(
        decoded.positions_angstrom[0][0].to_bits(),
        (-0.0_f64).to_bits()
    );
    assert_eq!(
        decoded.velocities_angstrom_per_fs[0][1].to_bits(),
        (-0.0_f64).to_bits()
    );

    let mut corrupted = bytes.clone();
    corrupted[80] ^= 0x40;
    assert_eq!(
        decode_checkpoint(&system, &corrupted)
            .expect_err("corruption must fail")
            .code(),
        DynamicsErrorCode::CheckpointChecksum
    );
    let other = System::new(vec![12.0, 17.0], vec![], None).expect("valid other system");
    assert_eq!(
        decode_checkpoint(&other, &bytes)
            .expect_err("topology mismatch must fail")
            .code(),
        DynamicsErrorCode::CheckpointSystemMismatch
    );
}

#[test]
fn checkpoint_restart_reproduces_the_exact_baoab_stream() {
    let system = System::new(vec![12.0], vec![], None).expect("valid system");
    let initial = State::new(vec![[0.7, -0.2, 0.1]], vec![[0.001, -0.002, 0.003]]);
    let mut uninterrupted = initial.clone();
    let mut split = initial;
    let mut provider = HarmonicTargets {
        targets: vec![[0.0; 3]],
    };
    integrate_baoab(
        &system,
        &mut uninterrupted,
        &mut provider,
        default_langevin(20),
    )
    .expect("uninterrupted run succeeds");
    let mut first_provider = HarmonicTargets {
        targets: vec![[0.0; 3]],
    };
    integrate_baoab(
        &system,
        &mut split,
        &mut first_provider,
        default_langevin(7),
    )
    .expect("first split run succeeds");
    let bytes = encode_checkpoint(&system, &split).expect("checkpoint succeeds");
    let mut restarted = decode_checkpoint(&system, &bytes).expect("restart succeeds");
    let mut second_provider = HarmonicTargets {
        targets: vec![[0.0; 3]],
    };
    integrate_baoab(
        &system,
        &mut restarted,
        &mut second_provider,
        default_langevin(13),
    )
    .expect("second split run succeeds");
    assert_eq!(restarted, uninterrupted);
}

#[test]
fn nve_energy_stays_inside_the_frozen_verlet_envelope() {
    let system = System::new(vec![1.0, 1.0], vec![], None).expect("valid system");
    let mut state = State::new(
        vec![[-0.55, 0.0, 0.0], [0.55, 0.0, 0.0]],
        vec![[0.0; 3], [0.0; 3]],
    );
    let mut provider = HarmonicBond {
        force_constant: 100.0,
        equilibrium: 1.0,
    };
    let initial_energy = 0.5;
    let mut maximum_drift = 0.0_f64;
    for _ in 0..2_000 {
        let report =
            integrate_velocity_verlet(&system, &mut state, &mut provider, default_verlet(1))
                .expect("NVE trajectory step succeeds");
        let total = report.final_potential_kcal_per_mol + report.final_kinetic_kcal_per_mol;
        maximum_drift = maximum_drift.max((total - initial_energy).abs());
    }
    assert_eq!(
        maximum_drift.to_bits(),
        fixture_bit(
            "nve_2000_step_envelope",
            "max_abs_energy_drift_kcal_per_mol"
        )
    );
    assert!(maximum_drift < 7.0e-4, "drift={maximum_drift:.17e}");
}

#[test]
fn long_run_free_particle_baoab_reaches_the_target_temperature() {
    let system = System::new(vec![12.0], vec![], None).expect("valid system");
    let mut state = State::new(vec![[0.0; 3]], vec![[0.0; 3]]);
    let config = LangevinConfig {
        timestep_fs: 1.0,
        steps: 5_000,
        temperature_kelvin: 300.0,
        friction_per_fs: 0.05,
        seed: 0xA5A5_0123_FEDC_9876,
        constraints: ConstraintConfig::default(),
    };
    integrate_baoab(&system, &mut state, &mut ZeroForce, config)
        .expect("burn-in trajectory succeeds");

    let mut temperature_sum = 0.0;
    for _ in 0..50_000 {
        integrate_baoab(
            &system,
            &mut state,
            &mut ZeroForce,
            LangevinConfig { steps: 1, ..config },
        )
        .expect("sample trajectory step succeeds");
        temperature_sum += temperature_kelvin(&system, &state).expect("finite temperature");
    }
    let mean_temperature = temperature_sum / 50_000.0;
    assert_eq!(
        mean_temperature.to_bits(),
        fixture_bit("nvt_50000_sample", "mean_temperature_kelvin")
    );
    assert!(
        (mean_temperature - 300.0).abs() < 24.0,
        "mean temperature={mean_temperature:.17e} K"
    );
}

#[test]
fn calls_are_transactional_and_zero_steps_are_a_strict_no_op() {
    let system = System::new(vec![1.0], vec![], None).expect("valid system");
    let original = State::new(vec![[1.0, 2.0, 3.0]], vec![[0.1, 0.2, 0.3]]);
    let mut state = original.clone();
    let mut calls = 0_u32;
    let mut failing =
        |_positions: &[[f64; 3]], _forces: &mut [[f64; 3]]| -> Result<f64, DynamicsError> {
            calls += 1;
            if calls == 2 {
                Err(DynamicsError::force_provider("injected failure"))
            } else {
                Ok(0.0)
            }
        };
    assert_eq!(
        integrate_velocity_verlet(&system, &mut state, &mut failing, default_verlet(2))
            .expect_err("injected failure must propagate")
            .code(),
        DynamicsErrorCode::ForceProvider
    );
    assert_eq!(state, original);

    let constrained = System::new(
        vec![1.0, 1.0],
        vec![DistanceConstraint {
            atom_i: 0,
            atom_j: 1,
            distance_angstrom: 1.0,
        }],
        None,
    )
    .expect("valid constrained system");
    let mut unsatisfied = State::new(
        vec![[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        vec![[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
    );
    let before = unsatisfied.clone();
    let report = integrate_velocity_verlet(
        &constrained,
        &mut unsatisfied,
        &mut ZeroForce,
        VerletConfig {
            steps: 0,
            ..default_verlet(0)
        },
    )
    .expect("zero-step report succeeds");
    assert_eq!(report.steps, 0);
    assert_eq!(unsatisfied, before);

    let mut overflowing_velocity = State::new(
        vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        vec![[f64::MAX, 0.0, 0.0], [-f64::MAX, 0.0, 0.0]],
    );
    let overflowing_before = overflowing_velocity.clone();
    assert_eq!(
        minimize(
            &constrained,
            &mut overflowing_velocity,
            &mut ZeroForce,
            MinimizationConfig {
                force_tolerance_kcal_per_mol_angstrom: 0.0,
                energy_tolerance_kcal_per_mol: 0.0,
                ..MinimizationConfig::default()
            },
        )
        .expect_err("final RATTLE overflow must fail transactionally")
        .code(),
        DynamicsErrorCode::NonFiniteState
    );
    assert_eq!(overflowing_velocity, overflowing_before);
}

#[test]
fn invalid_rows_parameters_and_outputs_fail_closed() {
    let redundant = System::new(
        vec![1.0, 1.0, 1.0],
        vec![
            DistanceConstraint {
                atom_i: 0,
                atom_j: 1,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 1,
                atom_j: 2,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 0,
                atom_j: 2,
                distance_angstrom: 2.0,
            },
        ],
        None,
    )
    .expect("topology alone cannot determine instantaneous rank");
    let collinear = State::new(
        vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        vec![[0.0; 3]; 3],
    );
    assert_eq!(
        kinetic_energy_kcal_per_mol(&redundant, &collinear)
            .expect_err("singular constraint rows must fail")
            .code(),
        DynamicsErrorCode::InvalidConstraint
    );

    assert_eq!(
        System::new(
            vec![1.0, 1.0],
            vec![DistanceConstraint {
                atom_i: 0,
                atom_j: 1,
                distance_angstrom: 5.0,
            }],
            Some(OrthorhombicCell {
                lengths_angstrom: [10.0; 3],
                periodic_axes: [true, true, true],
            }),
        )
        .expect_err("half-box target is ambiguous")
        .code(),
        DynamicsErrorCode::InvalidConstraint
    );

    let system = System::new(vec![1.0], vec![], None).expect("valid system");
    let original = State::new(vec![[0.0; 3]], vec![[0.0; 3]]);
    let mut state = original.clone();
    let mut nonfinite = |_positions: &[[f64; 3]], forces: &mut [[f64; 3]]| {
        forces[0][0] = f64::NAN;
        Ok(0.0)
    };
    assert_eq!(
        integrate_baoab(&system, &mut state, &mut nonfinite, default_langevin(1))
            .expect_err("non-finite provider output must fail")
            .code(),
        DynamicsErrorCode::NonFiniteForce
    );
    assert_eq!(state, original);

    let mut overflow = State {
        absolute_step: u64::MAX,
        ..original.clone()
    };
    assert_eq!(
        integrate_velocity_verlet(&system, &mut overflow, &mut ZeroForce, default_verlet(1))
            .expect_err("step overflow must fail")
            .code(),
        DynamicsErrorCode::StepOverflow
    );
    assert_eq!(overflow.absolute_step, u64::MAX);
}

#[test]
fn geometrically_singular_cycle_is_rejected_even_when_distances_match() {
    let system = System::new(
        vec![1.0; 4],
        vec![
            DistanceConstraint {
                atom_i: 0,
                atom_j: 1,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 1,
                atom_j: 2,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 2,
                atom_j: 3,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 0,
                atom_j: 3,
                distance_angstrom: 1.0,
            },
        ],
        None,
    )
    .expect("cycle topology is valid before geometry is supplied");
    let state = State::new(
        vec![
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ],
        vec![[0.0; 3]; 4],
    );
    assert_eq!(
        temperature_kelvin(&system, &state)
            .expect_err("collapsed cycle has a rank-deficient Jacobian")
            .code(),
        DynamicsErrorCode::InvalidConstraint
    );
}
