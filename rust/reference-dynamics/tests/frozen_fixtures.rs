use betelgeuze_reference_dynamics::{
    integrate_baoab, integrate_velocity_verlet, kinetic_energy_kcal_per_mol, minimize,
    normal_triplet, temperature_kelvin, ConstraintConfig, DynamicsError, ForceProvider,
    LangevinConfig, MinimizationConfig, State, System, VerletConfig,
};

struct HarmonicWell {
    force_constant: f64,
}

impl ForceProvider for HarmonicWell {
    fn energy_and_forces(
        &mut self,
        positions: &[[f64; 3]],
        forces: &mut [[f64; 3]],
    ) -> Result<f64, DynamicsError> {
        let mut energy = 0.0;
        for atom in 0..positions.len() {
            for axis in 0..3 {
                let coordinate = positions[atom][axis];
                energy += 0.5 * self.force_constant * coordinate * coordinate;
                forces[atom][axis] = -self.force_constant * coordinate;
            }
        }
        Ok(energy)
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

fn assert_close(actual: f64, expected: f64, tolerance: f64) {
    assert!(
        (actual - expected).abs() <= tolerance,
        "actual={actual:.17e}, expected={expected:.17e}, tolerance={tolerance:.3e}"
    );
}

fn fixture_case_bits(case: &str) -> Vec<u64> {
    include_str!("../fixtures/dynamics_v1.tsv")
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .filter_map(|line| {
            let mut fields = line.split('\t');
            let row_case = fields.next()?;
            let _field = fields.next()?;
            let bits = fields.next()?;
            assert!(fields.next().is_none(), "fixture row has extra columns");
            (row_case == case).then(|| u64::from_str_radix(bits, 16).expect("valid fixture bits"))
        })
        .collect()
}

#[test]
fn canonical_units_and_philox_normal_are_frozen() {
    let system = System::new(vec![12.0], vec![], None).expect("valid one-particle system");
    let state = State::new(vec![[0.0; 3]], vec![[0.001, -0.002, 0.003]]);
    assert_close(
        kinetic_energy_kcal_per_mol(&system, &state).expect("finite kinetic energy"),
        0.200_764_818_355_640_53,
        1.0e-16,
    );
    assert_close(
        temperature_kelvin(&system, &state).expect("finite temperature"),
        67.352_518_823_926_59,
        1.0e-13,
    );

    let normal = normal_triplet(0, 0, 0);
    assert_close(normal[0], 0.991_137_679_930_385_7, 2.0e-15);
    assert_close(normal[1], -0.924_662_587_665_535_3, 2.0e-15);
    assert_close(normal[2], -0.617_608_959_459_190_7, 2.0e-15);
}

#[test]
fn armijo_attempt_order_and_sign_are_frozen() {
    let system = System::new(vec![1.0], vec![], None).expect("valid system");
    let velocity = [-0.0, 1.25, -2.5];
    let mut state = State::new(vec![[2.0, 0.0, 0.0]], vec![velocity]);
    let mut provider = HarmonicWell {
        force_constant: 4.0,
    };
    let report = minimize(
        &system,
        &mut state,
        &mut provider,
        MinimizationConfig {
            max_iterations: 2,
            force_tolerance_kcal_per_mol_angstrom: 0.0,
            energy_tolerance_kcal_per_mol: 0.0,
            initial_step_angstrom2_mol_per_kcal: 1.0,
            minimum_step_angstrom2_mol_per_kcal: 0.01,
            armijo_c1: 0.25,
            backtrack_factor: 0.5,
            max_backtracks: 3,
            constraints: ConstraintConfig::default(),
        },
    )
    .expect("third bounded Armijo attempt reaches the minimum");
    assert_eq!(report.iterations, 1);
    assert!(report.converged);
    assert_eq!(
        report.initial_potential_kcal_per_mol.to_bits(),
        8.0_f64.to_bits()
    );
    assert_eq!(
        report.final_potential_kcal_per_mol.to_bits(),
        0.0_f64.to_bits()
    );
    assert_eq!(report.final_max_force_kcal_per_mol_angstrom, 0.0);
    assert_eq!(state.positions_angstrom, vec![[0.0; 3]]);
    assert_eq!(
        state.velocities_angstrom_per_fs[0].map(f64::to_bits),
        velocity.map(f64::to_bits)
    );
}

#[test]
fn nve_velocity_verlet_one_step_is_frozen() {
    let system = System::new(vec![1.0, 1.0], vec![], None).expect("valid system");
    let mut state = State::new(
        vec![[-0.55, 0.0, 0.0], [0.55, 0.0, 0.0]],
        vec![[0.0; 3], [0.0; 3]],
    );
    let mut provider = HarmonicBond {
        force_constant: 100.0,
        equilibrium: 1.0,
    };
    let report = integrate_velocity_verlet(
        &system,
        &mut state,
        &mut provider,
        VerletConfig {
            timestep_fs: 0.25,
            steps: 1,
            constraints: ConstraintConfig::default(),
        },
    )
    .expect("one NVE step succeeds");

    assert_eq!(
        state.positions_angstrom[0][0].to_bits(),
        0xBFE1_9887_65BA_6EFD
    );
    assert_eq!(
        state.positions_angstrom[1][0].to_bits(),
        0x3FE1_9887_65BA_6EFD
    );
    assert_eq!(
        state.velocities_angstrom_per_fs[0][0].to_bits(),
        0x3F51_1D81_7344_B4AE
    );
    assert_eq!(
        state.velocities_angstrom_per_fs[1][0].to_bits(),
        0xBF51_1D81_7344_B4AE
    );
    assert_close(
        report.final_potential_kcal_per_mol + report.final_kinetic_kcal_per_mol,
        0.499_996_585_357_991_35,
        2.0e-15,
    );
    assert_eq!(state.absolute_step, 1);
}

#[test]
fn fixed_seed_baoab_one_step_is_frozen() {
    let system = System::new(vec![12.0], vec![], None).expect("valid system");
    let mut state = State::new(vec![[0.7, -0.2, 0.1]], vec![[0.001, -0.002, 0.003]]);
    let mut provider = HarmonicWell {
        force_constant: 2.3,
    };
    let report = integrate_baoab(
        &system,
        &mut state,
        &mut provider,
        LangevinConfig {
            timestep_fs: 0.5,
            steps: 1,
            temperature_kelvin: 300.0,
            friction_per_fs: 0.01,
            seed: 0,
            constraints: ConstraintConfig::default(),
        },
    )
    .expect("one fixed-seed BAOAB step succeeds");

    let actual = [
        state.positions_angstrom[0][0],
        state.positions_angstrom[0][1],
        state.positions_angstrom[0][2],
        state.velocities_angstrom_per_fs[0][0],
        state.velocities_angstrom_per_fs[0][1],
        state.velocities_angstrom_per_fs[0][2],
        report.final_potential_kcal_per_mol,
        report.final_kinetic_kcal_per_mol,
    ];
    assert_eq!(
        actual.map(f64::to_bits).as_slice(),
        fixture_case_bits("baoab_one_step")
    );
    assert_eq!(state.absolute_step, 1);
}
