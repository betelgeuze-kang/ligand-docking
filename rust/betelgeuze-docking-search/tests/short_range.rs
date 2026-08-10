use betelgeuze_docking_search::{
    AnchorId, AnchorKind, EnergyForceEvaluator, LigandAnchor, LigandAtom, ReceptorAtom,
    SearchErrorCode, SearchInput, ShortRangeConfig, ShortRangeEvaluator, SurfaceId, SurfaceSample,
    Vec3,
};

fn fixture() -> SearchInput {
    SearchInput {
        source_seed: [9; 32],
        ligand_atoms: vec![
            LigandAtom {
                position_angstrom: Vec3::new(-0.7, 0.1, 0.0),
                vdw_radius_angstrom: 1.5,
                epsilon_kcal_per_mol: 0.18,
                charge_elementary: 0.35,
            },
            LigandAtom {
                position_angstrom: Vec3::new(0.8, -0.2, 0.3),
                vdw_radius_angstrom: 1.7,
                epsilon_kcal_per_mol: 0.24,
                charge_elementary: -0.25,
            },
            LigandAtom {
                position_angstrom: Vec3::new(0.0, 0.9, -0.4),
                vdw_radius_angstrom: 1.6,
                epsilon_kcal_per_mol: 0.21,
                charge_elementary: -0.10,
            },
        ],
        ligand_anchors: vec![LigandAnchor {
            id: AnchorId(1),
            atom_index: 0,
            direction: Vec3::new(1.0, 0.0, 0.0),
            kind: AnchorKind::Hydrophobe,
        }],
        receptor_atoms: vec![
            ReceptorAtom {
                position_angstrom: Vec3::new(4.0, 2.0, 1.0),
                vdw_radius_angstrom: 1.8,
                epsilon_kcal_per_mol: 0.16,
                charge_elementary: -0.30,
            },
            ReceptorAtom {
                position_angstrom: Vec3::new(-3.5, 4.0, -2.0),
                vdw_radius_angstrom: 1.6,
                epsilon_kcal_per_mol: 0.12,
                charge_elementary: 0.20,
            },
        ],
        surface_samples: vec![SurfaceSample {
            id: SurfaceId(1),
            position_angstrom: Vec3::new(2.0, 0.0, 0.0),
            outward_normal: Vec3::new(1.0, 0.0, 0.0),
            anchor_kind: AnchorKind::Hydrophobe,
        }],
    }
}

fn evaluate(evaluator: &mut ShortRangeEvaluator, positions: &[Vec3]) -> (f64, Vec<Vec3>) {
    let mut forces = vec![Vec3::default(); positions.len()];
    let energy = evaluator.energy_and_forces(positions, &mut forces).unwrap();
    (energy, forces)
}

#[test]
fn analytic_force_matches_central_finite_difference_for_every_component() {
    let input = fixture();
    let mut positions: Vec<_> = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect();
    positions[0].x += 0.12;
    positions[1].y -= 0.08;
    positions[2].z += 0.05;
    let mut evaluator =
        ShortRangeEvaluator::from_input(&input, ShortRangeConfig::default()).unwrap();
    let (_, analytic) = evaluate(&mut evaluator, &positions);
    let step = 1.0e-6;
    for atom_index in 0..positions.len() {
        for axis in 0..3 {
            let mut plus = positions.clone();
            let mut minus = positions.clone();
            match axis {
                0 => {
                    plus[atom_index].x += step;
                    minus[atom_index].x -= step;
                }
                1 => {
                    plus[atom_index].y += step;
                    minus[atom_index].y -= step;
                }
                2 => {
                    plus[atom_index].z += step;
                    minus[atom_index].z -= step;
                }
                _ => unreachable!(),
            }
            let plus_energy = evaluate(&mut evaluator, &plus).0;
            let minus_energy = evaluate(&mut evaluator, &minus).0;
            let numerical_force = -(plus_energy - minus_energy) / (2.0 * step);
            let analytic_force = match axis {
                0 => analytic[atom_index].x,
                1 => analytic[atom_index].y,
                2 => analytic[atom_index].z,
                _ => unreachable!(),
            };
            let tolerance = 2.0e-6 * analytic_force.abs().max(1.0);
            assert!(
                (analytic_force - numerical_force).abs() <= tolerance,
                "atom {atom_index} axis {axis}: analytic={analytic_force} numerical={numerical_force}"
            );
        }
    }
}

#[test]
fn receptor_input_permutation_has_bit_exact_energy_and_forces() {
    let input = fixture();
    let mut reversed = input.clone();
    reversed.receptor_atoms.reverse();
    let positions: Vec<_> = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect();
    let mut left = ShortRangeEvaluator::from_input(&input, ShortRangeConfig::default()).unwrap();
    let mut right =
        ShortRangeEvaluator::from_input(&reversed, ShortRangeConfig::default()).unwrap();
    assert_eq!(
        evaluate(&mut left, &positions),
        evaluate(&mut right, &positions)
    );
}

#[test]
fn source_shape_is_zero_without_receptor_and_restores_a_displacement() {
    let mut input = fixture();
    input.receptor_atoms.clear();
    let source: Vec<_> = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect();
    let mut evaluator =
        ShortRangeEvaluator::from_input(&input, ShortRangeConfig::default()).unwrap();
    let (source_energy, source_forces) = evaluate(&mut evaluator, &source);
    assert_eq!(source_energy, 0.0);
    assert_eq!(source_forces, vec![Vec3::default(); source.len()]);
    let mut displaced = source;
    displaced[0].x -= 0.2;
    let (energy, forces) = evaluate(&mut evaluator, &displaced);
    assert!(energy > 0.0);
    assert!(forces[0].x > 0.0);
    let total = forces.iter().copied().fold(Vec3::default(), Vec3::plus);
    assert!(total.norm() < 1.0e-12);
}

#[test]
fn switch_reaches_exact_zero_at_cutoff() {
    let mut input = fixture();
    input.receptor_atoms = vec![ReceptorAtom {
        position_angstrom: Vec3::new(100.0, 0.0, 0.0),
        vdw_radius_angstrom: 1.5,
        epsilon_kcal_per_mol: 0.2,
        charge_elementary: 1.0,
    }];
    let positions: Vec<_> = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect();
    let mut evaluator =
        ShortRangeEvaluator::from_input(&input, ShortRangeConfig::default()).unwrap();
    assert_eq!(
        evaluate(&mut evaluator, &positions),
        (0.0, vec![Vec3::default(); positions.len()])
    );
}

#[test]
fn softcore_overlap_remains_finite() {
    let mut input = fixture();
    input.receptor_atoms[0].position_angstrom = input.ligand_atoms[0].position_angstrom;
    input.receptor_atoms.truncate(1);
    let positions: Vec<_> = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect();
    let mut evaluator =
        ShortRangeEvaluator::from_input(&input, ShortRangeConfig::default()).unwrap();
    let (energy, forces) = evaluate(&mut evaluator, &positions);
    assert!(energy.is_finite());
    assert!(forces.iter().all(|force| force.is_finite()));
}

#[test]
fn config_atom_and_buffer_bounds_fail_closed() {
    let input = fixture();
    let invalid_configs = [
        ShortRangeConfig {
            cutoff_angstrom: f64::NAN,
            ..ShortRangeConfig::default()
        },
        ShortRangeConfig {
            switch_start_angstrom: 12.0,
            ..ShortRangeConfig::default()
        },
        ShortRangeConfig {
            softcore_angstrom: 0.0,
            ..ShortRangeConfig::default()
        },
        ShortRangeConfig {
            dielectric: 0.5,
            ..ShortRangeConfig::default()
        },
    ];
    for config in invalid_configs {
        assert_eq!(
            ShortRangeEvaluator::from_input(&input, config)
                .unwrap_err()
                .code(),
            SearchErrorCode::InvalidConfiguration
        );
    }
    let mut invalid_atom = input.clone();
    invalid_atom.receptor_atoms[0].epsilon_kcal_per_mol = -0.1;
    assert_eq!(
        ShortRangeEvaluator::from_input(&invalid_atom, ShortRangeConfig::default())
            .unwrap_err()
            .code(),
        SearchErrorCode::InvalidAtomParameter
    );
    let mut evaluator =
        ShortRangeEvaluator::from_input(&input, ShortRangeConfig::default()).unwrap();
    let positions: Vec<_> = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect();
    assert!(evaluator
        .energy_and_forces(&positions, &mut [Vec3::default(); 1])
        .is_err());
}
