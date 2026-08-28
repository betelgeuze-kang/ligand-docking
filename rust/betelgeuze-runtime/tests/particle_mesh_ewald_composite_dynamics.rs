use betelgeuze_runtime as runtime;
use runtime::{
    AtomNonbonded, Backend, Context, ContextOptions, DirectEwaldErrorCode, DirectEwaldModel,
    DirectEwaldPairExclusion, DirectEwaldPairScale, DirectEwaldParameters, DirectEwaldSettings,
    DistanceConstraints, ErrorCode, ForceField, ForceFieldInput, HarmonicAngle, HarmonicBond,
    Integrator, NonbondedSettings, OrthorhombicCell, PairExclusion, PairScale,
    ParticleMeshEwaldCompositeSimulation, ParticleMeshReciprocalModel,
    ParticleMeshReciprocalParameters, ParticleMeshReciprocalSettings, ParticleSnapshot,
    ParticleSoa, PeriodicTorsion, PositionSoa, SimulationOptions, System, VelocitySoa,
};

const POSITIONS: [[f64; 3]; 4] = [
    [1.25, 2.50, 3.75],
    [5.10, 3.20, 8.40],
    [7.20, 8.30, 5.70],
    [12.40, 9.10, 8.30],
];
const VELOCITIES: [[f64; 3]; 4] = [
    [0.001, -0.002, 0.003],
    [-0.004, 0.005, -0.006],
    [0.007, -0.008, 0.009],
    [-0.010, 0.011, -0.012],
];
const MASSES: [f64; 4] = [12.0, 14.0, 16.0, 18.0];
const NEUTRAL_CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
const NONNEUTRAL_CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.4];
const CELL_LENGTHS: [f64; 3] = [18.0, 20.0, 22.0];

#[test]
fn profile_deep_ownership_and_velocity_verlet_boundary_are_explicit() {
    assert_eq!(
        runtime::particle_mesh_ewald_composite_dynamics_profile_id().unwrap(),
        "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0"
    );
    assert!(std::mem::needs_drop::<ParticleMeshEwaldCompositeSimulation>());

    // The returned owner outlives the system, force field, and both models.
    let simulation = neutral_simulation(options(0.1), [16, 16, 16]).unwrap();
    assert_eq!(simulation.len(), 4);
    assert!(!simulation.is_empty());
    assert_eq!(simulation.snapshot().unwrap().len(), 4);
    drop(simulation);

    let error = match neutral_simulation(
        SimulationOptions {
            integrator: Integrator::LangevinBaoab,
            ..options(0.1)
        },
        [16, 16, 16],
    ) {
        Ok(_) => panic!("non-Verlet options must fail before native creation"),
        Err(error) => error,
    };
    assert_eq!(error.status, ErrorCode::InvalidArgument);
    assert_eq!(error.code, None);
}

#[test]
fn exact_neutral_cpu_lanes_match_stateless_zero_step_and_restart_bit_exactly() {
    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let system = system(&NEUTRAL_CHARGES);
        let forcefield = forcefield();
        let direct_model = direct_model();
        let reciprocal_model = reciprocal_model([16, 16, 16]);
        let expected_potential = context
            .evaluate_particle_mesh_ewald_composite_energy(
                &system,
                &forcefield,
                &direct_model,
                &reciprocal_model,
            )
            .unwrap()
            .total_kcal_per_mol;
        let mut uninterrupted = ParticleMeshEwaldCompositeSimulation::new(
            &system,
            &forcefield,
            &direct_model,
            &reciprocal_model,
            &DistanceConstraints::default(),
            options(0.1),
        )
        .unwrap();
        let mut restarted = neutral_simulation(options(0.1), [16, 16, 16]).unwrap();

        let initial_snapshot = uninterrupted.snapshot().unwrap();
        let initial_checkpoint = uninterrupted.checkpoint().unwrap();
        assert!(initial_checkpoint.starts_with(b"BGPME001"));
        let zero = context
            .integrate_particle_mesh_ewald_composite(&mut uninterrupted, 0)
            .unwrap();
        assert_eq!(zero.steps_completed, 0);
        assert_eq!(zero.absolute_step, 0);
        assert_eq!(zero.degrees_of_freedom, 12);
        assert_eq!(
            zero.potential_kcal_per_mol.to_bits(),
            expected_potential.to_bits()
        );
        assert_snapshot_bits(&initial_snapshot, &uninterrupted.snapshot().unwrap());
        assert_eq!(initial_checkpoint, uninterrupted.checkpoint().unwrap());

        context
            .integrate_particle_mesh_ewald_composite(&mut uninterrupted, 3)
            .unwrap();
        let checkpoint = uninterrupted.checkpoint().unwrap();
        assert_eq!(checkpoint, uninterrupted.checkpoint().unwrap());
        restarted.load_checkpoint(&checkpoint).unwrap();
        assert_eq!(restarted.absolute_step().unwrap(), 3);
        assert_snapshot_bits(
            &uninterrupted.snapshot().unwrap(),
            &restarted.snapshot().unwrap(),
        );

        let uninterrupted_report = context
            .integrate_particle_mesh_ewald_composite(&mut uninterrupted, 5)
            .unwrap();
        let restarted_report = context
            .integrate_particle_mesh_ewald_composite(&mut restarted, 5)
            .unwrap();
        assert_report_bits(&uninterrupted_report, &restarted_report);
        assert_snapshot_bits(
            &uninterrupted.snapshot().unwrap(),
            &restarted.snapshot().unwrap(),
        );
        assert_eq!(
            uninterrupted.checkpoint().unwrap(),
            restarted.checkpoint().unwrap()
        );
    }
}

#[test]
fn mismatched_and_corrupt_checkpoints_preserve_every_dynamic_byte() {
    let context = context(Backend::RustCpu);
    let mut source = neutral_simulation(options(0.1), [16, 16, 16]).unwrap();
    context
        .integrate_particle_mesh_ewald_composite(&mut source, 4)
        .unwrap();
    let checkpoint = source.checkpoint().unwrap();

    for mut target in [
        neutral_simulation(options(0.2), [16, 16, 16]).unwrap(),
        neutral_simulation(options(0.1), [32, 16, 16]).unwrap(),
    ] {
        let target_snapshot = target.snapshot().unwrap();
        let target_step = target.absolute_step().unwrap();
        let target_checkpoint = target.checkpoint().unwrap();
        assert!(target.load_checkpoint(&checkpoint).is_err());
        assert_eq!(target.absolute_step().unwrap(), target_step);
        assert_snapshot_bits(&target_snapshot, &target.snapshot().unwrap());
        assert_eq!(target.checkpoint().unwrap(), target_checkpoint);

        let mut corrupt = target_checkpoint.clone();
        let corrupt_index = corrupt.len() / 2;
        corrupt[corrupt_index] ^= 0x80;
        assert!(target.load_checkpoint(&corrupt).is_err());
        assert_eq!(target.absolute_step().unwrap(), target_step);
        assert_snapshot_bits(&target_snapshot, &target.snapshot().unwrap());
        assert_eq!(target.checkpoint().unwrap(), target_checkpoint);
    }
}

#[test]
fn nonneutral_creation_preserves_the_typed_direct_ewald_error() {
    let error = match simulation(&NONNEUTRAL_CHARGES, options(0.1), [16, 16, 16]) {
        Ok(_) => panic!("nonneutral creation must fail"),
        Err(error) => error,
    };
    assert_eq!(error.code, Some(DirectEwaldErrorCode::NonNeutralSystem));
}

#[test]
fn auto_request_fails_closed_and_preserves_every_dynamic_byte() {
    let context =
        Context::new(ContextOptions::auto(0)).expect("AUTO context creation is available");
    let mut simulation = neutral_simulation(options(0.1), [16, 16, 16]).unwrap();
    let initial_snapshot = simulation.snapshot().unwrap();
    let initial_step = simulation.absolute_step().unwrap();
    let initial_checkpoint = simulation.checkpoint().unwrap();

    let error = context
        .integrate_particle_mesh_ewald_composite(&mut simulation, 1)
        .expect_err("AUTO must not inherit its resolved CPU lane");
    assert_eq!(error.status, ErrorCode::UnsupportedBackend);
    assert_eq!(error.code, None);
    assert!(error.detail.contains("cannot fall back"));
    assert_eq!(simulation.absolute_step().unwrap(), initial_step);
    assert_snapshot_bits(&initial_snapshot, &simulation.snapshot().unwrap());
    assert_eq!(simulation.checkpoint().unwrap(), initial_checkpoint);
}

fn neutral_simulation(
    options: SimulationOptions,
    mesh_dimensions: [u32; 3],
) -> runtime::DirectEwaldResult<ParticleMeshEwaldCompositeSimulation> {
    simulation(&NEUTRAL_CHARGES, options, mesh_dimensions)
}

fn simulation(
    charges: &[f64],
    options: SimulationOptions,
    mesh_dimensions: [u32; 3],
) -> runtime::DirectEwaldResult<ParticleMeshEwaldCompositeSimulation> {
    let system = system(charges);
    let forcefield = forcefield();
    let direct_model = direct_model();
    let reciprocal_model = reciprocal_model(mesh_dimensions);
    ParticleMeshEwaldCompositeSimulation::new(
        &system,
        &forcefield,
        &direct_model,
        &reciprocal_model,
        &DistanceConstraints::default(),
        options,
    )
}

fn system(charges: &[f64]) -> System {
    let x: Vec<_> = POSITIONS.iter().map(|position| position[0]).collect();
    let y: Vec<_> = POSITIONS.iter().map(|position| position[1]).collect();
    let z: Vec<_> = POSITIONS.iter().map(|position| position[2]).collect();
    let vx: Vec<_> = VELOCITIES.iter().map(|velocity| velocity[0]).collect();
    let vy: Vec<_> = VELOCITIES.iter().map(|velocity| velocity[1]).collect();
    let vz: Vec<_> = VELOCITIES.iter().map(|velocity| velocity[2]).collect();
    System::new(
        ParticleSoa::new(PositionSoa::new(&x, &y, &z), &MASSES, charges)
            .with_velocities(VelocitySoa::new(&vx, &vy, &vz)),
    )
    .unwrap()
}

fn forcefield() -> ForceField {
    let atoms = [
        AtomNonbonded {
            sigma_angstrom: 3.10,
            epsilon_kcal_per_mol: 0.14,
        },
        AtomNonbonded {
            sigma_angstrom: 3.35,
            epsilon_kcal_per_mol: 0.18,
        },
        AtomNonbonded {
            sigma_angstrom: 3.00,
            epsilon_kcal_per_mol: 0.11,
        },
        AtomNonbonded {
            sigma_angstrom: 3.45,
            epsilon_kcal_per_mol: 0.16,
        },
    ];
    let bonds = [
        HarmonicBond {
            atom_i: 0,
            atom_j: 1,
            equilibrium_angstrom: 5.70,
            force_constant_kcal_per_mol_angstrom2: 2.5,
        },
        HarmonicBond {
            atom_i: 1,
            atom_j: 2,
            equilibrium_angstrom: 5.80,
            force_constant_kcal_per_mol_angstrom2: 1.75,
        },
    ];
    let angles = [HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.7,
        force_constant_kcal_per_mol_radian2: 1.25,
    }];
    let torsions = [PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 3,
        phase_radians: -0.4,
        amplitude_kcal_per_mol: 0.35,
    }];
    let exclusions = [PairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [PairScale {
        atom_i: 2,
        atom_j: 3,
        lennard_jones_scale: 0.4,
        coulomb_scale: 0.5,
    }];
    let mut input = ForceFieldInput::new(&atoms);
    input.bonds = &bonds;
    input.angles = &angles;
    input.torsions = &torsions;
    input.exclusions = &exclusions;
    input.pair_scales = &pair_scales;
    input.cell = Some(OrthorhombicCell {
        lengths_angstrom: CELL_LENGTHS,
        periodic_axes: [true; 3],
    });
    input.nonbonded = NonbondedSettings {
        cutoff_angstrom: 8.9,
        switch_start_angstrom: 7.5,
        dielectric: 1.0,
        screening_kappa_per_angstrom: 0.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    ForceField::new(input).unwrap()
}

fn direct_model() -> DirectEwaldModel {
    let exclusions = [DirectEwaldPairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [DirectEwaldPairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    }];
    let mut parameters = DirectEwaldParameters::new(4, CELL_LENGTHS);
    parameters.exclusions = &exclusions;
    parameters.pair_scales = &pair_scales;
    parameters.settings = DirectEwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [5, 5, 5],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    DirectEwaldModel::new(parameters).unwrap()
}

fn reciprocal_model(mesh_dimensions: [u32; 3]) -> ParticleMeshReciprocalModel {
    let mut parameters = ParticleMeshReciprocalParameters::new(4, CELL_LENGTHS);
    parameters.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 0.31,
        mesh_dimensions,
        dielectric: 1.0,
    };
    ParticleMeshReciprocalModel::new(parameters).unwrap()
}

fn options(timestep_femtoseconds: f64) -> SimulationOptions {
    SimulationOptions {
        integrator: Integrator::VelocityVerlet,
        timestep_femtoseconds,
        temperature_kelvin: 0.0,
        friction_per_femtosecond: 0.0,
        random_seed: 0,
    }
}

fn context(backend: Backend) -> Context {
    let options = match backend {
        Backend::CppCpuReference => ContextOptions::cpu_reference(),
        Backend::RustCpu => ContextOptions::rust_cpu(),
        _ => panic!("only explicit CPU lanes are admitted"),
    };
    Context::new(options).unwrap()
}

fn assert_snapshot_bits(left: &ParticleSnapshot, right: &ParticleSnapshot) {
    assert_channel_bits(&left.positions.x_angstrom, &right.positions.x_angstrom);
    assert_channel_bits(&left.positions.y_angstrom, &right.positions.y_angstrom);
    assert_channel_bits(&left.positions.z_angstrom, &right.positions.z_angstrom);
    assert_channel_bits(
        &left.velocities.x_angstrom_per_femtosecond,
        &right.velocities.x_angstrom_per_femtosecond,
    );
    assert_channel_bits(
        &left.velocities.y_angstrom_per_femtosecond,
        &right.velocities.y_angstrom_per_femtosecond,
    );
    assert_channel_bits(
        &left.velocities.z_angstrom_per_femtosecond,
        &right.velocities.z_angstrom_per_femtosecond,
    );
    assert_channel_bits(&left.mass_dalton, &right.mass_dalton);
    assert_channel_bits(&left.charge_elementary, &right.charge_elementary);
}

fn assert_channel_bits(left: &[f64], right: &[f64]) {
    assert_eq!(left.len(), right.len());
    for (left, right) in left.iter().zip(right) {
        assert_eq!(left.to_bits(), right.to_bits());
    }
}

fn assert_report_bits(left: &runtime::DynamicsReport, right: &runtime::DynamicsReport) {
    assert_eq!(left.steps_completed, right.steps_completed);
    assert_eq!(left.absolute_step, right.absolute_step);
    assert_eq!(left.degrees_of_freedom, right.degrees_of_freedom);
    assert_eq!(
        left.potential_kcal_per_mol.to_bits(),
        right.potential_kcal_per_mol.to_bits()
    );
    assert_eq!(
        left.kinetic_kcal_per_mol.to_bits(),
        right.kinetic_kcal_per_mol.to_bits()
    );
    assert_eq!(
        left.total_kcal_per_mol.to_bits(),
        right.total_kcal_per_mol.to_bits()
    );
    assert_eq!(
        left.temperature_kelvin.to_bits(),
        right.temperature_kelvin.to_bits()
    );
}
