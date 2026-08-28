use betelgeuze_runtime as runtime;
use runtime::{
    AtomNonbonded, Backend, Context, ContextOptions, DirectEwaldErrorCode, DirectEwaldModel,
    DirectEwaldPairExclusion, DirectEwaldPairScale, DirectEwaldParameters, DirectEwaldSettings,
    ErrorCode, ForceField, ForceFieldInput, HarmonicAngle, HarmonicBond, NonbondedSettings,
    OrthorhombicCell, PairExclusion, PairScale, ParticleMeshEwaldCompositeEnergyComponents,
    ParticleMeshEwaldCompositeEvaluation, ParticleMeshReciprocalModel,
    ParticleMeshReciprocalParameters, ParticleMeshReciprocalSettings, ParticleSoa, PeriodicTorsion,
    PositionSoa, System,
};

const POSITIONS: [[f64; 3]; 4] = [
    [1.25, 2.50, 3.75],
    [3.10, 3.20, 4.40],
    [5.20, 5.30, 4.70],
    [7.40, 6.10, 6.30],
];
const MASSES: [f64; 4] = [12.0, 14.0, 16.0, 19.0];
const CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
const ZERO_CHARGES: [f64; 4] = [0.0; 4];
const CELL_LENGTHS: [f64; 3] = [18.0, 20.0, 22.0];
const RUST_CPU_TOTAL_BITS: u64 = 0x4012_dc31_29bc_e12e;

struct Fixture {
    system: System,
    zero_charge_system: System,
    forcefield: ForceField,
    direct_model: DirectEwaldModel,
    reciprocal_model: ParticleMeshReciprocalModel,
}

fn fixture() -> Fixture {
    Fixture {
        system: system(&POSITIONS, &MASSES, &CHARGES),
        zero_charge_system: system(&POSITIONS, &MASSES, &ZERO_CHARGES),
        forcefield: forcefield(),
        direct_model: direct_model(4),
        reciprocal_model: reciprocal_model(4),
    }
}

fn system(positions: &[[f64; 3]], masses: &[f64], charges: &[f64]) -> System {
    let x: Vec<_> = positions.iter().map(|position| position[0]).collect();
    let y: Vec<_> = positions.iter().map(|position| position[1]).collect();
    let z: Vec<_> = positions.iter().map(|position| position[2]).collect();
    System::new(ParticleSoa::new(
        PositionSoa::new(&x, &y, &z),
        masses,
        charges,
    ))
    .expect("test system must be accepted")
}

fn forcefield() -> ForceField {
    let atoms = [
        AtomNonbonded {
            sigma_angstrom: 1.10,
            epsilon_kcal_per_mol: 0.15,
        },
        AtomNonbonded {
            sigma_angstrom: 1.20,
            epsilon_kcal_per_mol: 0.20,
        },
        AtomNonbonded {
            sigma_angstrom: 1.30,
            epsilon_kcal_per_mol: 0.25,
        },
        AtomNonbonded {
            sigma_angstrom: 1.40,
            epsilon_kcal_per_mol: 0.30,
        },
    ];
    let bonds = [HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: 5.0,
        force_constant_kcal_per_mol_angstrom2: 3.0,
    }];
    let angles = [HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.4,
        force_constant_kcal_per_mol_radian2: 2.0,
    }];
    let torsions = [PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 3,
        phase_radians: 0.4,
        amplitude_kcal_per_mol: 0.7,
    }];
    let exclusions = [PairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [PairScale {
        atom_i: 2,
        atom_j: 3,
        lennard_jones_scale: 0.25,
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
        switch_start_angstrom: 7.0,
        dielectric: 1.0,
        screening_kappa_per_angstrom: 0.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    ForceField::new(input).expect("four-atom force field must be accepted")
}

fn direct_model(atom_count: usize) -> DirectEwaldModel {
    let exclusions = [DirectEwaldPairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [DirectEwaldPairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    }];
    let mut parameters = DirectEwaldParameters::new(atom_count, CELL_LENGTHS);
    parameters.settings = DirectEwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [5, 5, 5],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    if atom_count == 4 {
        parameters.exclusions = &exclusions;
        parameters.pair_scales = &pair_scales;
    }
    DirectEwaldModel::new(parameters).expect("direct parent model must be accepted")
}

fn reciprocal_model(atom_count: usize) -> ParticleMeshReciprocalModel {
    let mut parameters = ParticleMeshReciprocalParameters::new(atom_count, CELL_LENGTHS);
    parameters.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 0.31,
        mesh_dimensions: [16, 16, 16],
        dielectric: 1.0,
    };
    ParticleMeshReciprocalModel::new(parameters).expect("reciprocal parent model must be accepted")
}

fn context(backend: Backend) -> Context {
    let options = match backend {
        Backend::CppCpuReference => ContextOptions::cpu_reference(),
        Backend::RustCpu => ContextOptions::rust_cpu(),
        _ => panic!("test helper admits only explicit CPU lanes"),
    };
    Context::new(options).expect("CPU context must be available")
}

#[test]
fn both_cpu_lanes_equal_the_independent_short_plus_pme_parent_sum() {
    let fixture = fixture();
    let mut lane_results = Vec::new();

    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let composite = context
            .evaluate_particle_mesh_ewald_composite(
                &fixture.system,
                &fixture.forcefield,
                &fixture.direct_model,
                &fixture.reciprocal_model,
            )
            .expect("composite evaluation must succeed");
        let repeated = context
            .evaluate_particle_mesh_ewald_composite(
                &fixture.system,
                &fixture.forcefield,
                &fixture.direct_model,
                &fixture.reciprocal_model,
            )
            .expect("repeated composite evaluation must succeed");
        assert_composite_bits(&composite, &repeated);

        let energy_only = context
            .evaluate_particle_mesh_ewald_composite_energy(
                &fixture.system,
                &fixture.forcefield,
                &fixture.direct_model,
                &fixture.reciprocal_model,
            )
            .expect("composite energy-only evaluation must succeed");
        assert_eq!(
            energy_values(composite.energy).map(f64::to_bits),
            energy_values(energy_only).map(f64::to_bits)
        );

        let short = context
            .evaluate(&fixture.zero_charge_system, &fixture.forcefield)
            .expect("independent zero-charge short-range evaluation must succeed");
        let pme = context
            .evaluate_particle_mesh_ewald(
                &fixture.system,
                &fixture.direct_model,
                &fixture.reciprocal_model,
            )
            .expect("independent particle-mesh Ewald evaluation must succeed");

        assert_eq!(
            composite.energy.short_coulomb_kcal_per_mol.to_bits(),
            0.0_f64.to_bits(),
            "short Coulomb must be exact +0.0 on {backend:?}"
        );
        assert_parent_energy_bits(&composite.energy, &short.energy, &pme.energy);
        assert_parent_force_sum_bits(&composite, &short, &pme);
        if backend == Backend::RustCpu {
            assert_eq!(
                composite.energy.total_kcal_per_mol.to_bits(),
                RUST_CPU_TOTAL_BITS,
                "Rust CPU composite total must preserve the frozen fixture bits"
            );
        }
        lane_results.push(composite);
    }

    assert_composite_close(&lane_results[0], &lane_results[1]);
}

#[test]
fn typed_failure_length_mismatch_and_auto_request_fail_closed_then_recover() {
    let fixture = fixture();

    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let non_neutral = system(&POSITIONS, &MASSES, &[0.7, -0.4, -0.6, 0.4]);
        let error = context
            .evaluate_particle_mesh_ewald_composite(
                &non_neutral,
                &fixture.forcefield,
                &fixture.direct_model,
                &fixture.reciprocal_model,
            )
            .expect_err("non-neutral composite evaluation must fail");
        assert_eq!(error.status, ErrorCode::NumericalError);
        assert_eq!(error.code, Some(DirectEwaldErrorCode::NonNeutralSystem));

        let mismatch = context
            .evaluate_particle_mesh_ewald_composite_energy(
                &fixture.system,
                &fixture.forcefield,
                &fixture.direct_model,
                &reciprocal_model(3),
            )
            .expect_err("mismatched reciprocal parent length must fail locally");
        assert_eq!(mismatch.status, ErrorCode::InvalidArgument);
        assert_eq!(mismatch.code, None);

        context
            .evaluate_particle_mesh_ewald_composite(
                &fixture.system,
                &fixture.forcefield,
                &fixture.direct_model,
                &fixture.reciprocal_model,
            )
            .expect("prior failures must not poison borrowed handles");
    }

    let auto = Context::new(ContextOptions::auto(0)).expect("AUTO context creation is available");
    let error = auto
        .evaluate_particle_mesh_ewald_composite(
            &fixture.system,
            &fixture.forcefield,
            &fixture.direct_model,
            &fixture.reciprocal_model,
        )
        .expect_err("AUTO must not inherit its resolved CPU lane");
    assert_eq!(error.status, ErrorCode::UnsupportedBackend);
    assert_eq!(error.code, None);
    assert!(error.detail.contains("cannot fall back"));
}

#[test]
fn profile_identity_is_frozen() {
    assert_eq!(
        runtime::particle_mesh_ewald_composite_profile_id().unwrap(),
        "betelgeuze.native_particle_mesh_ewald_composite/1.0.0"
    );
}

fn assert_parent_energy_bits(
    composite: &ParticleMeshEwaldCompositeEnergyComponents,
    short: &runtime::EnergyComponents,
    pme: &runtime::ParticleMeshEwaldEnergyComponents,
) {
    for (name, observed, expected) in [
        (
            "short bond",
            composite.short_harmonic_bond_kcal_per_mol,
            short.harmonic_bond_kcal_per_mol,
        ),
        (
            "short angle",
            composite.short_harmonic_angle_kcal_per_mol,
            short.harmonic_angle_kcal_per_mol,
        ),
        (
            "short torsion",
            composite.short_periodic_torsion_kcal_per_mol,
            short.periodic_torsion_kcal_per_mol,
        ),
        (
            "short Lennard-Jones",
            composite.short_lennard_jones_kcal_per_mol,
            short.lennard_jones_kcal_per_mol,
        ),
        (
            "short Coulomb",
            composite.short_coulomb_kcal_per_mol,
            short.coulomb_kcal_per_mol,
        ),
        (
            "short total",
            composite.short_total_kcal_per_mol,
            short.total_kcal_per_mol,
        ),
        (
            "PME real",
            composite.pme_real_space_kcal_per_mol,
            pme.real_space_kcal_per_mol,
        ),
        (
            "PME reciprocal",
            composite.pme_reciprocal_space_kcal_per_mol,
            pme.reciprocal_space_kcal_per_mol,
        ),
        (
            "PME self",
            composite.pme_self_kcal_per_mol,
            pme.self_kcal_per_mol,
        ),
        (
            "PME pair correction",
            composite.pme_pair_correction_kcal_per_mol,
            pme.pair_correction_kcal_per_mol,
        ),
        (
            "PME total",
            composite.pme_total_kcal_per_mol,
            pme.total_kcal_per_mol,
        ),
        (
            "grand total",
            composite.total_kcal_per_mol,
            short.total_kcal_per_mol + pme.total_kcal_per_mol,
        ),
    ] {
        assert_eq!(
            observed.to_bits(),
            expected.to_bits(),
            "composite component differs from independent parent: {name}"
        );
    }
}

fn assert_parent_force_sum_bits(
    composite: &ParticleMeshEwaldCompositeEvaluation,
    short: &runtime::Evaluation,
    pme: &runtime::ParticleMeshEwaldEvaluation,
) {
    for (axis, composite, short, pme) in [
        (
            "x",
            composite.forces.x_kcal_per_mol_angstrom.as_slice(),
            short.forces.x_kcal_per_mol_angstrom.as_slice(),
            pme.forces.x_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "y",
            composite.forces.y_kcal_per_mol_angstrom.as_slice(),
            short.forces.y_kcal_per_mol_angstrom.as_slice(),
            pme.forces.y_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "z",
            composite.forces.z_kcal_per_mol_angstrom.as_slice(),
            short.forces.z_kcal_per_mol_angstrom.as_slice(),
            pme.forces.z_kcal_per_mol_angstrom.as_slice(),
        ),
    ] {
        for (atom, ((observed, short), pme)) in composite.iter().zip(short).zip(pme).enumerate() {
            assert_eq!(
                observed.to_bits(),
                (short + pme).to_bits(),
                "composite force differs from parent sum: atom {atom} axis {axis}"
            );
        }
    }
}

fn energy_values(energy: ParticleMeshEwaldCompositeEnergyComponents) -> [f64; 12] {
    [
        energy.short_harmonic_bond_kcal_per_mol,
        energy.short_harmonic_angle_kcal_per_mol,
        energy.short_periodic_torsion_kcal_per_mol,
        energy.short_lennard_jones_kcal_per_mol,
        energy.short_coulomb_kcal_per_mol,
        energy.short_total_kcal_per_mol,
        energy.pme_real_space_kcal_per_mol,
        energy.pme_reciprocal_space_kcal_per_mol,
        energy.pme_self_kcal_per_mol,
        energy.pme_pair_correction_kcal_per_mol,
        energy.pme_total_kcal_per_mol,
        energy.total_kcal_per_mol,
    ]
}

fn assert_composite_bits(
    left: &ParticleMeshEwaldCompositeEvaluation,
    right: &ParticleMeshEwaldCompositeEvaluation,
) {
    assert_eq!(
        energy_values(left.energy).map(f64::to_bits),
        energy_values(right.energy).map(f64::to_bits)
    );
    for (left, right) in [
        (
            &left.forces.x_kcal_per_mol_angstrom,
            &right.forces.x_kcal_per_mol_angstrom,
        ),
        (
            &left.forces.y_kcal_per_mol_angstrom,
            &right.forces.y_kcal_per_mol_angstrom,
        ),
        (
            &left.forces.z_kcal_per_mol_angstrom,
            &right.forces.z_kcal_per_mol_angstrom,
        ),
    ] {
        assert_eq!(left.len(), right.len());
        for (left, right) in left.iter().zip(right) {
            assert_eq!(left.to_bits(), right.to_bits());
        }
    }
}

fn assert_composite_close(
    left: &ParticleMeshEwaldCompositeEvaluation,
    right: &ParticleMeshEwaldCompositeEvaluation,
) {
    for (index, (left, right)) in energy_values(left.energy)
        .into_iter()
        .zip(energy_values(right.energy))
        .enumerate()
    {
        assert_close(left, right, &format!("energy {index}"));
    }
    for (axis, left, right) in [
        (
            "x",
            &left.forces.x_kcal_per_mol_angstrom,
            &right.forces.x_kcal_per_mol_angstrom,
        ),
        (
            "y",
            &left.forces.y_kcal_per_mol_angstrom,
            &right.forces.y_kcal_per_mol_angstrom,
        ),
        (
            "z",
            &left.forces.z_kcal_per_mol_angstrom,
            &right.forces.z_kcal_per_mol_angstrom,
        ),
    ] {
        for (atom, (left, right)) in left.iter().zip(right).enumerate() {
            assert_close(*left, *right, &format!("force atom {atom} axis {axis}"));
        }
    }
}

fn assert_close(observed: f64, expected: f64, label: &str) {
    let tolerance = 5.0e-12 * expected.abs().max(1.0);
    assert!(
        (observed - expected).abs() <= tolerance,
        "{label}: observed {observed:.17e}, expected {expected:.17e}, tolerance {tolerance:.3e}"
    );
}
