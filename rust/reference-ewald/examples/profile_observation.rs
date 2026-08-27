use betelgeuze_reference_ewald::{
    evaluate, EwaldInput, EwaldSettings, OrthorhombicCell, PairExclusion, PairScale, Position,
    EWALD_SCHEMA_ID,
};

fn fixture(maximum: i32) -> EwaldInput {
    let mut input = EwaldInput::new(
        vec![
            Position::new(1.25, 2.5, 3.75),
            Position::new(5.1, 3.2, 8.4),
            Position::new(10.2, 12.3, 7.7),
            Position::new(15.4, 17.1, 19.3),
        ],
        vec![0.7, -0.4, -0.6, 0.3],
        OrthorhombicCell {
            lengths_angstrom: [18.0, 20.0, 22.0],
        },
    );
    input.settings = EwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [maximum; 3],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
        neutrality_tolerance_elementary: 1.0e-12,
    };
    input.exclusions.push(PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    input.pair_scales.push(PairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    });
    input
}

fn main() {
    let input = fixture(5);
    let result = evaluate(&input).expect("frozen fixture must evaluate");
    println!("schema_id={EWALD_SCHEMA_ID}");
    println!(
        "real={:.17e},0x{:016x}",
        result.energy.real_space_kcal_per_mol,
        result.energy.real_space_kcal_per_mol.to_bits()
    );
    println!(
        "reciprocal={:.17e},0x{:016x}",
        result.energy.reciprocal_space_kcal_per_mol,
        result.energy.reciprocal_space_kcal_per_mol.to_bits()
    );
    println!(
        "self={:.17e},0x{:016x}",
        result.energy.self_kcal_per_mol,
        result.energy.self_kcal_per_mol.to_bits()
    );
    println!(
        "correction={:.17e},0x{:016x}",
        result.energy.pair_correction_kcal_per_mol,
        result.energy.pair_correction_kcal_per_mol.to_bits()
    );
    println!(
        "total={:.17e},0x{:016x}",
        result.energy.total_kcal_per_mol(),
        result.energy.total_kcal_per_mol().to_bits()
    );
    for (atom, force) in result.forces_kcal_per_mol_angstrom.iter().enumerate() {
        for (axis, value) in force.iter().enumerate() {
            println!(
                "force_{atom}_{axis}={value:.17e},0x{:016x}",
                value.to_bits()
            );
        }
    }

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
                .energy
                .total_kcal_per_mol();
            let plus_energy = evaluate(&plus)
                .expect("plus displacement must evaluate")
                .energy
                .total_kcal_per_mol();
            let finite_difference_force = -(plus_energy - minus_energy) / (2.0 * step);
            maximum_finite_difference_error = maximum_finite_difference_error.max(
                (finite_difference_force - result.forces_kcal_per_mol_angstrom[atom][axis]).abs(),
            );
        }
    }
    println!("maximum_finite_difference_force_error={maximum_finite_difference_error:.17e}");

    let reference = evaluate(&fixture(9))
        .expect("reference reciprocal bound must evaluate")
        .energy
        .total_kcal_per_mol();
    for maximum in [3, 5, 7] {
        let total = evaluate(&fixture(maximum))
            .expect("comparison reciprocal bound must evaluate")
            .energy
            .total_kcal_per_mol();
        println!(
            "reciprocal_bound_{maximum}_absolute_total_difference_from_9={:.17e}",
            (total - reference).abs()
        );
    }
}

fn coordinate_mut(position: &mut Position, axis: usize) -> &mut f64 {
    match axis {
        0 => &mut position.x_angstrom,
        1 => &mut position.y_angstrom,
        2 => &mut position.z_angstrom,
        _ => unreachable!(),
    }
}
