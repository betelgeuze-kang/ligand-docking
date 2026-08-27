use std::collections::BTreeMap;

use betelgeuze_reference_ewald::{
    evaluate, EwaldInput, EwaldSettings, OrthorhombicCell, PairExclusion, PairScale, Position,
    EWALD_SCHEMA_ID,
};

const FROZEN: &str = include_str!("../fixtures/direct_ewald_v1.tsv");

fn fixture() -> EwaldInput {
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
        reciprocal_max_indices: [5, 5, 5],
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

#[test]
fn frozen_energy_and_force_bits_match() {
    let declared_schema = FROZEN
        .lines()
        .find_map(|line| line.strip_prefix("# schema_id="))
        .expect("fixture must declare a schema");
    assert_eq!(declared_schema, EWALD_SCHEMA_ID);
    let expected = parse_rows();
    let result = evaluate(&fixture()).expect("frozen fixture must evaluate");
    let actual = [
        (
            "real_space_kcal_per_mol",
            result.energy.real_space_kcal_per_mol,
        ),
        (
            "reciprocal_space_kcal_per_mol",
            result.energy.reciprocal_space_kcal_per_mol,
        ),
        ("self_kcal_per_mol", result.energy.self_kcal_per_mol),
        (
            "pair_correction_kcal_per_mol",
            result.energy.pair_correction_kcal_per_mol,
        ),
        ("total_kcal_per_mol", result.energy.total_kcal_per_mol()),
    ];
    for (value_id, value) in actual {
        assert_eq!(
            value.to_bits(),
            expected[value_id],
            "frozen mismatch for {value_id}"
        );
    }
    for (atom, force) in result.forces_kcal_per_mol_angstrom.iter().enumerate() {
        for (axis, value) in force.iter().copied().enumerate() {
            let axis_name = ["x", "y", "z"][axis];
            let key = format!("force_{atom}_{axis_name}");
            assert_eq!(
                value.to_bits(),
                expected[key.as_str()],
                "frozen mismatch for {key}"
            );
        }
    }
    assert_eq!(expected.len(), 17);
}

fn parse_rows() -> BTreeMap<&'static str, u64> {
    FROZEN
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#') && !line.starts_with("value_id"))
        .map(|line| {
            let (value_id, bits) = line.split_once('\t').expect("row must be tab-separated");
            let bits = u64::from_str_radix(bits, 16).expect("bits must be hexadecimal");
            (value_id, bits)
        })
        .collect()
}
