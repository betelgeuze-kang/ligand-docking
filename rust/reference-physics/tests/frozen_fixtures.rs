use std::collections::BTreeMap;

use betelgeuze_reference_physics::{
    evaluate, AtomNonbonded, EnergyComponents, HarmonicAngle, HarmonicBond, NonbondedSettings,
    OracleInput, OrthorhombicCell, PairExclusion, PairScale, PeriodicTorsion, Position,
    ORACLE_SCHEMA_ID,
};

const FIXTURE_TABLE: &str = include_str!("../fixtures/exact_energy_v1.tsv");

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct ExpectedBits {
    bond: u64,
    angle: u64,
    torsion: u64,
    lennard_jones: u64,
    coulomb: u64,
    total: u64,
}

fn neutral() -> AtomNonbonded {
    AtomNonbonded {
        sigma_angstrom: 1.0,
        epsilon_kcal_per_mol: 0.0,
        charge_elementary: 0.0,
    }
}

fn input_with_neutral_atoms(positions: Vec<Position>) -> OracleInput {
    OracleInput::new(positions.clone(), vec![neutral(); positions.len()])
}

fn build_case(case_id: &str) -> OracleInput {
    match case_id {
        "bond" => {
            let mut input = input_with_neutral_atoms(vec![
                Position::new(0.0, 0.0, 0.0),
                Position::new(2.0, 0.0, 0.0),
            ]);
            input.bonds.push(HarmonicBond {
                atom_i: 0,
                atom_j: 1,
                equilibrium_angstrom: 1.0,
                force_constant_kcal_per_mol_angstrom2: 4.0,
            });
            input
        }
        "angle" => {
            let mut input = input_with_neutral_atoms(vec![
                Position::new(1.0, 0.0, 0.0),
                Position::new(0.0, 0.0, 0.0),
                Position::new(0.0, 1.0, 0.0),
            ]);
            input.angles.push(HarmonicAngle {
                atom_i: 0,
                atom_j: 1,
                atom_k: 2,
                equilibrium_radians: core::f64::consts::PI / 3.0,
                force_constant_kcal_per_mol_radian2: 36.0,
            });
            input
        }
        "signed_torsion" => {
            let mut input = input_with_neutral_atoms(vec![
                Position::new(0.0, 1.0, 0.0),
                Position::new(0.0, 0.0, 0.0),
                Position::new(1.0, 0.0, 0.0),
                Position::new(1.0, 0.0, -1.0),
            ]);
            input.torsions.push(PeriodicTorsion {
                atom_i: 0,
                atom_j: 1,
                atom_k: 2,
                atom_l: 3,
                periodicity: 1,
                phase_radians: core::f64::consts::PI / 6.0,
                amplitude_kcal_per_mol: 3.0,
            });
            input
        }
        "lennard_jones" => OracleInput::new(
            vec![Position::new(0.0, 0.0, 0.0), Position::new(2.0, 0.0, 0.0)],
            vec![
                AtomNonbonded {
                    sigma_angstrom: 1.0,
                    epsilon_kcal_per_mol: 1.0,
                    charge_elementary: 0.0,
                },
                AtomNonbonded {
                    sigma_angstrom: 1.0,
                    epsilon_kcal_per_mol: 1.0,
                    charge_elementary: 0.0,
                },
            ],
        ),
        "coulomb" => {
            let mut input = OracleInput::new(
                vec![Position::new(0.0, 0.0, 0.0), Position::new(2.0, 0.0, 0.0)],
                vec![
                    AtomNonbonded {
                        sigma_angstrom: 1.0,
                        epsilon_kcal_per_mol: 0.0,
                        charge_elementary: 1.0,
                    },
                    AtomNonbonded {
                        sigma_angstrom: 1.0,
                        epsilon_kcal_per_mol: 0.0,
                        charge_elementary: -1.0,
                    },
                ],
            );
            input.nonbonded.dielectric = 2.0;
            input
        }
        "exclusion" => {
            let mut input = OracleInput::new(
                vec![Position::default(), Position::default()],
                vec![
                    AtomNonbonded {
                        sigma_angstrom: 1.0,
                        epsilon_kcal_per_mol: 1.0,
                        charge_elementary: 1.0,
                    },
                    AtomNonbonded {
                        sigma_angstrom: 1.0,
                        epsilon_kcal_per_mol: 1.0,
                        charge_elementary: -1.0,
                    },
                ],
            );
            input.exclusions.push(PairExclusion {
                atom_i: 1,
                atom_j: 0,
            });
            input
        }
        "pbc" => {
            let mut input = OracleInput::new(
                vec![Position::new(0.0, 0.0, 0.0), Position::new(9.0, 0.0, 0.0)],
                vec![
                    AtomNonbonded {
                        sigma_angstrom: 0.5,
                        epsilon_kcal_per_mol: 1.0,
                        charge_elementary: 1.0,
                    },
                    AtomNonbonded {
                        sigma_angstrom: 0.5,
                        epsilon_kcal_per_mol: 1.0,
                        charge_elementary: 1.0,
                    },
                ],
            );
            input.cell = Some(OrthorhombicCell {
                lengths_angstrom: [10.0, 12.0, 14.0],
                periodic_axes: [true, false, false],
            });
            input.nonbonded = NonbondedSettings {
                cutoff_angstrom: 4.0,
                switch_start_angstrom: 3.0,
                ..NonbondedSettings::default()
            };
            input
        }
        "combined" => combined_case(),
        _ => panic!("unknown frozen fixture case: {case_id}"),
    }
}

fn combined_case() -> OracleInput {
    let mut input = OracleInput::new(
        vec![
            Position::new(0.0, 1.0, 0.0),
            Position::new(0.0, 0.0, 0.0),
            Position::new(1.0, 0.0, 0.0),
            Position::new(1.0, 0.0, -1.0),
        ],
        vec![
            AtomNonbonded {
                sigma_angstrom: 1.0,
                epsilon_kcal_per_mol: 0.25,
                charge_elementary: 1.0,
            },
            AtomNonbonded {
                sigma_angstrom: 1.2,
                epsilon_kcal_per_mol: 0.36,
                charge_elementary: -0.5,
            },
            AtomNonbonded {
                sigma_angstrom: 0.8,
                epsilon_kcal_per_mol: 0.49,
                charge_elementary: 0.25,
            },
            AtomNonbonded {
                sigma_angstrom: 1.4,
                epsilon_kcal_per_mol: 0.64,
                charge_elementary: -1.0,
            },
        ],
    );
    input.bonds.push(HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: 0.75,
        force_constant_kcal_per_mol_angstrom2: 8.0,
    });
    input.angles.push(HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: core::f64::consts::PI / 3.0,
        force_constant_kcal_per_mol_radian2: 18.0,
    });
    input.torsions.push(PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 1,
        phase_radians: core::f64::consts::PI / 6.0,
        amplitude_kcal_per_mol: 3.0,
    });
    input.exclusions = vec![
        PairExclusion {
            atom_i: 0,
            atom_j: 1,
        },
        PairExclusion {
            atom_i: 1,
            atom_j: 2,
        },
        PairExclusion {
            atom_i: 2,
            atom_j: 3,
        },
    ];
    input.pair_scales.push(PairScale {
        atom_i: 0,
        atom_j: 3,
        lennard_jones_scale: 0.5,
        coulomb_scale: 0.25,
    });
    input.nonbonded = NonbondedSettings {
        cutoff_angstrom: 5.0,
        switch_start_angstrom: 4.0,
        dielectric: 2.0,
        ..NonbondedSettings::default()
    };
    input
}

fn parse_fixture_table() -> BTreeMap<&'static str, ExpectedBits> {
    let fixture_schema = FIXTURE_TABLE
        .lines()
        .find_map(|line| line.strip_prefix("# oracle_schema_id="))
        .expect("fixture must declare its oracle schema");
    assert_eq!(fixture_schema, ORACLE_SCHEMA_ID);

    let mut rows = BTreeMap::new();
    for line in FIXTURE_TABLE
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .skip(1)
    {
        let fields: Vec<_> = line.split('\t').collect();
        assert_eq!(fields.len(), 7, "invalid fixture row: {line}");
        let expected = ExpectedBits {
            bond: parse_bits(fields[1]),
            angle: parse_bits(fields[2]),
            torsion: parse_bits(fields[3]),
            lennard_jones: parse_bits(fields[4]),
            coulomb: parse_bits(fields[5]),
            total: parse_bits(fields[6]),
        };
        assert!(
            rows.insert(fields[0], expected).is_none(),
            "duplicate fixture case: {}",
            fields[0]
        );
    }
    rows
}

fn parse_bits(value: &str) -> u64 {
    u64::from_str_radix(
        value
            .strip_prefix("0x")
            .expect("fixture bits must have a 0x prefix"),
        16,
    )
    .expect("fixture bits must be hexadecimal binary64 words")
}

fn actual_bits(energy: EnergyComponents) -> ExpectedBits {
    ExpectedBits {
        bond: energy.harmonic_bond_kcal_per_mol.to_bits(),
        angle: energy.harmonic_angle_kcal_per_mol.to_bits(),
        torsion: energy.periodic_torsion_kcal_per_mol.to_bits(),
        lennard_jones: energy.lennard_jones_kcal_per_mol.to_bits(),
        coulomb: energy.coulomb_kcal_per_mol.to_bits(),
        total: energy.total_kcal_per_mol().to_bits(),
    }
}

fn assert_component_bits(case_id: &str, component: &str, actual: u64, expected: u64) {
    assert_eq!(
        actual,
        expected,
        "{case_id} {component}: actual={} expected={}",
        f64::from_bits(actual),
        f64::from_bits(expected)
    );
}

#[test]
fn energies_match_frozen_binary64_fixtures_exactly() {
    const CASE_IDS: [&str; 8] = [
        "bond",
        "angle",
        "signed_torsion",
        "lennard_jones",
        "coulomb",
        "exclusion",
        "pbc",
        "combined",
    ];
    let fixtures = parse_fixture_table();
    assert_eq!(fixtures.len(), CASE_IDS.len());

    for case_id in CASE_IDS {
        let expected = fixtures
            .get(case_id)
            .unwrap_or_else(|| panic!("missing frozen fixture case: {case_id}"));
        let actual = actual_bits(
            evaluate(&build_case(case_id))
                .unwrap_or_else(|error| panic!("fixture {case_id} failed: {error}")),
        );
        assert_component_bits(case_id, "bond", actual.bond, expected.bond);
        assert_component_bits(case_id, "angle", actual.angle, expected.angle);
        assert_component_bits(case_id, "torsion", actual.torsion, expected.torsion);
        assert_component_bits(
            case_id,
            "Lennard-Jones",
            actual.lennard_jones,
            expected.lennard_jones,
        );
        assert_component_bits(case_id, "Coulomb", actual.coulomb, expected.coulomb);
        assert_component_bits(case_id, "total", actual.total, expected.total);
    }
}
