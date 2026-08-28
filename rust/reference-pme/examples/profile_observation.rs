use betelgeuze_reference_ewald::{
    evaluate as evaluate_direct_ewald, EwaldInput, EwaldSettings,
    OrthorhombicCell as DirectOrthorhombicCell, Position as DirectPosition,
};
use betelgeuze_reference_pme_reciprocal::{
    evaluate, OrthorhombicCell, ParticleMeshReciprocalInput, ParticleMeshReciprocalSettings,
    Position, CARDINAL_B_SPLINE_ORDER, PARTICLE_MESH_RECIPROCAL_SCHEMA_ID,
};

fn fixture(mesh_dimension: u32) -> ParticleMeshReciprocalInput {
    let mut input = ParticleMeshReciprocalInput::new(
        vec![
            Position::new(1.25, 2.5, 3.75),
            Position::new(5.1, 3.2, 8.4),
            Position::new(10.2, 12.3, 7.7),
            Position::new(15.4, 17.1, 19.3),
        ],
        vec![0.7, -0.4, -0.6, 0.300_000_000_000_000_04],
        OrthorhombicCell {
            lengths_angstrom: [18.0, 20.0, 22.0],
        },
    );
    input.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 0.31,
        mesh_dimensions: [mesh_dimension; 3],
        dielectric: 1.0,
    };
    input
}

fn main() {
    let input = fixture(16);
    let result = evaluate(&input).expect("frozen fixture must evaluate");
    print_frozen_values(&result);
    print_internal_observations(&input, &result);
    print_direct_ewald_observations();
    println!("full_pme_implemented=false");
}

fn print_frozen_values(
    result: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
) {
    println!("schema_id={PARTICLE_MESH_RECIPROCAL_SCHEMA_ID}");
    println!("cardinal_b_spline_order={CARDINAL_B_SPLINE_ORDER}");
    println!("mesh_dimensions=16,16,16");
    println!(
        "reciprocal_space_kcal_per_mol={:.17e},0x{:016x}",
        result.reciprocal_space_kcal_per_mol,
        result.reciprocal_space_kcal_per_mol.to_bits()
    );
    for (atom, force) in result.forces_kcal_per_mol_angstrom.iter().enumerate() {
        for (axis, value) in force.iter().copied().enumerate() {
            let axis_name = ["x", "y", "z"][axis];
            println!(
                "force_{atom}_{axis_name}={value:.17e},0x{:016x}",
                value.to_bits()
            );
        }
    }
    println!("maximum_fft_dft_checked_in_tests=true");
}

fn print_internal_observations(
    input: &ParticleMeshReciprocalInput,
    result: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
) {
    let step = 1.0e-5;
    let mut maximum_finite_difference_error = 0.0_f64;
    for atom in 0..input.positions.len() {
        for axis in 0..3 {
            let mut minus = input.clone();
            let mut plus = input.clone();
            *coordinate_mut(&mut minus.positions[atom], axis) -= step;
            *coordinate_mut(&mut plus.positions[atom], axis) += step;
            let minus_energy = evaluate(&minus)
                .expect("minus displacement must evaluate")
                .reciprocal_space_kcal_per_mol;
            let plus_energy = evaluate(&plus)
                .expect("plus displacement must evaluate")
                .reciprocal_space_kcal_per_mol;
            let finite_difference_force = -(plus_energy - minus_energy) / (2.0 * step);
            maximum_finite_difference_error = maximum_finite_difference_error.max(
                (finite_difference_force - result.forces_kcal_per_mol_angstrom[atom][axis]).abs(),
            );
        }
    }
    println!(
        "maximum_central_finite_difference_force_error={maximum_finite_difference_error:.17e}"
    );

    let mut integer_grid_translated = input.clone();
    for position in &mut integer_grid_translated.positions {
        position.x_angstrom += input.cell.lengths_angstrom[0] / 16.0;
        position.y_angstrom += input.cell.lengths_angstrom[1] / 16.0;
        position.z_angstrom += input.cell.lengths_angstrom[2] / 16.0;
    }
    let integer_grid_translated =
        evaluate(&integer_grid_translated).expect("integer-grid translation must evaluate");
    println!(
        "integer_grid_translation_absolute_energy_difference={:.17e}",
        (integer_grid_translated.reciprocal_space_kcal_per_mol
            - result.reciprocal_space_kcal_per_mol)
            .abs()
    );
    println!(
        "maximum_integer_grid_translation_force_difference={:.17e}",
        maximum_force_difference(&integer_grid_translated, result)
    );

    let mut arbitrarily_translated = input.clone();
    for position in &mut arbitrarily_translated.positions {
        position.x_angstrom += 0.317;
        position.y_angstrom -= 0.229;
        position.z_angstrom += 0.141;
    }
    let arbitrarily_translated =
        evaluate(&arbitrarily_translated).expect("arbitrary translation must evaluate");
    println!(
        "arbitrary_translation_absolute_energy_difference={:.17e}",
        (arbitrarily_translated.reciprocal_space_kcal_per_mol
            - result.reciprocal_space_kcal_per_mol)
            .abs()
    );
    println!(
        "maximum_arbitrary_translation_force_difference={:.17e}",
        maximum_force_difference(&arbitrarily_translated, result)
    );
    let mut net_force = [0.0_f64; 3];
    for force in &result.forces_kcal_per_mol_angstrom {
        for axis in 0..3 {
            net_force[axis] += force[axis];
        }
    }
    println!(
        "maximum_absolute_net_force_component={:.17e}",
        net_force.into_iter().map(f64::abs).fold(0.0, f64::max)
    );
}

fn print_direct_ewald_observations() {
    let step = 1.0e-5;
    let direct_input = direct_reciprocal_fixture();
    let direct = evaluate_direct_ewald(&direct_input)
        .expect("direct reciprocal observation must evaluate")
        .energy
        .reciprocal_space_kcal_per_mol;
    let direct_forces = direct_reciprocal_finite_difference_forces(&direct_input, step);
    println!("direct_ewald_reciprocal_space_kcal_per_mol={direct:.17e}");
    for mesh_dimension in [8, 16, 32] {
        let particle_mesh =
            evaluate(&fixture(mesh_dimension)).expect("mesh observation must evaluate");
        println!(
            "mesh_{mesh_dimension}_absolute_difference_from_direct_ewald={:.17e}",
            (particle_mesh.reciprocal_space_kcal_per_mol - direct).abs()
        );
        println!(
            "mesh_{mesh_dimension}_maximum_force_difference_from_direct_ewald_reciprocal_finite_difference={:.17e}",
            particle_mesh
                .forces_kcal_per_mol_angstrom
                .iter()
                .flatten()
                .zip(direct_forces.iter().flatten())
                .map(|(particle_mesh, direct)| (particle_mesh - direct).abs())
            .fold(0.0, f64::max)
        );
    }
}

fn direct_reciprocal_fixture() -> EwaldInput {
    let mut input = EwaldInput::new(
        vec![
            DirectPosition::new(1.25, 2.5, 3.75),
            DirectPosition::new(5.1, 3.2, 8.4),
            DirectPosition::new(10.2, 12.3, 7.7),
            DirectPosition::new(15.4, 17.1, 19.3),
        ],
        vec![0.7, -0.4, -0.6, 0.300_000_000_000_000_04],
        DirectOrthorhombicCell {
            lengths_angstrom: [18.0, 20.0, 22.0],
        },
    );
    input.settings = EwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 1.0e-7,
        reciprocal_max_indices: [9; 3],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    input
}

fn direct_reciprocal_finite_difference_forces(input: &EwaldInput, step: f64) -> Vec<[f64; 3]> {
    (0..input.positions.len())
        .map(|atom| {
            core::array::from_fn(|axis| {
                let mut minus = input.clone();
                let mut plus = input.clone();
                *direct_coordinate_mut(&mut minus.positions[atom], axis) -= step;
                *direct_coordinate_mut(&mut plus.positions[atom], axis) += step;
                let minus_energy = evaluate_direct_ewald(&minus)
                    .expect("direct minus displacement must evaluate")
                    .energy
                    .reciprocal_space_kcal_per_mol;
                let plus_energy = evaluate_direct_ewald(&plus)
                    .expect("direct plus displacement must evaluate")
                    .energy
                    .reciprocal_space_kcal_per_mol;
                -(plus_energy - minus_energy) / (2.0 * step)
            })
        })
        .collect()
}

fn direct_coordinate_mut(position: &mut DirectPosition, axis: usize) -> &mut f64 {
    match axis {
        0 => &mut position.x_angstrom,
        1 => &mut position.y_angstrom,
        2 => &mut position.z_angstrom,
        _ => unreachable!(),
    }
}

fn maximum_force_difference(
    left: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
    right: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
) -> f64 {
    left.forces_kcal_per_mol_angstrom
        .iter()
        .flatten()
        .zip(right.forces_kcal_per_mol_angstrom.iter().flatten())
        .map(|(left, right)| (left - right).abs())
        .fold(0.0, f64::max)
}

fn coordinate_mut(position: &mut Position, axis: usize) -> &mut f64 {
    match axis {
        0 => &mut position.x_angstrom,
        1 => &mut position.y_angstrom,
        2 => &mut position.z_angstrom,
        _ => unreachable!(),
    }
}
