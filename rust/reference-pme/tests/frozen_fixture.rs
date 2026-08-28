use std::collections::BTreeMap;

use betelgeuze_reference_pme_reciprocal::{
    evaluate, OrthorhombicCell, ParticleMeshReciprocalInput, ParticleMeshReciprocalSettings,
    Position, PARTICLE_MESH_RECIPROCAL_SCHEMA_ID,
};

const FROZEN: &str = include_str!("../fixtures/pme_reciprocal_v1.tsv");

fn fixture() -> ParticleMeshReciprocalInput {
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
        mesh_dimensions: [16, 16, 16],
        dielectric: 1.0,
    };
    input
}

#[test]
fn frozen_reciprocal_energy_and_force_bits_match() {
    let declared_schema = FROZEN
        .lines()
        .find_map(|line| line.strip_prefix("# schema_id="))
        .expect("fixture must declare a schema");
    assert_eq!(declared_schema, PARTICLE_MESH_RECIPROCAL_SCHEMA_ID);
    let expected = parse_rows();
    let result = evaluate(&fixture()).expect("frozen fixture must evaluate");
    assert_eq!(
        result.reciprocal_space_kcal_per_mol.to_bits(),
        expected["reciprocal_space_kcal_per_mol"]
    );
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
    assert_eq!(expected.len(), 13);
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
