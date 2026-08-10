use std::collections::BTreeSet;

use betelgeuze_docking_search::{
    search, search_default, AnchorId, AnchorKind, CandidateReason, CandidateStatus,
    EvaluationError, LigandAnchor, LigandAtom, PlacementMode, ReceptorAtom, SearchConfig,
    SearchErrorCode, SearchInput, SurfaceId, SurfaceSample, Vec3, MAX_GENERATED_CANDIDATES,
    MAX_LIGAND_ATOMS, MAX_ORIENTATIONS, MAX_REFINEMENT_STEPS,
};

fn fixture_input() -> SearchInput {
    SearchInput {
        source_seed: [0x42; 32],
        ligand_atoms: vec![
            LigandAtom {
                position_angstrom: Vec3::new(-0.5, 0.0, 0.0),
                vdw_radius_angstrom: 0.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.1,
            },
            LigandAtom {
                position_angstrom: Vec3::new(0.5, 0.0, 0.0),
                vdw_radius_angstrom: 0.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: -0.1,
            },
            LigandAtom {
                position_angstrom: Vec3::new(0.0, 0.6, 0.0),
                vdw_radius_angstrom: 0.5,
                epsilon_kcal_per_mol: 0.15,
                charge_elementary: 0.0,
            },
        ],
        ligand_anchors: vec![
            LigandAnchor {
                id: AnchorId(7),
                atom_index: 0,
                direction: Vec3::new(0.0, -1.0, 0.0),
                kind: AnchorKind::HydrogenBondDonor,
            },
            LigandAnchor {
                id: AnchorId(3),
                atom_index: 1,
                direction: Vec3::new(0.0, -1.0, 0.0),
                kind: AnchorKind::HydrogenBondDonor,
            },
        ],
        receptor_atoms: vec![
            ReceptorAtom {
                position_angstrom: Vec3::new(0.0, 8.0, 0.0),
                vdw_radius_angstrom: 0.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.2,
            },
            ReceptorAtom {
                position_angstrom: Vec3::new(0.0, -8.0, 0.0),
                vdw_radius_angstrom: 0.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: -0.2,
            },
        ],
        surface_samples: vec![
            SurfaceSample {
                id: SurfaceId(11),
                position_angstrom: Vec3::new(0.5, 0.0, 0.0),
                outward_normal: Vec3::new(0.0, 2.0, 0.0),
                anchor_kind: AnchorKind::HydrogenBondAcceptor,
            },
            SurfaceSample {
                id: SurfaceId(2),
                position_angstrom: Vec3::new(-0.5, 0.0, 0.0),
                outward_normal: Vec3::new(0.0, 2.0, 0.0),
                anchor_kind: AnchorKind::HydrogenBondAcceptor,
            },
        ],
    }
}

fn small_config() -> SearchConfig {
    SearchConfig {
        orientation_count: 4,
        generated_candidate_limit: 8,
        coarse_keep: 7,
        refinement_keep: 5,
        top_k: 3,
        refinement_steps: 0,
        cluster_rmsd_angstrom: 1.0e-6,
        ..SearchConfig::default()
    }
}

fn harmonic_evaluator(positions: &[Vec3], forces: &mut [Vec3]) -> Result<f64, EvaluationError> {
    let mut energy = 0.0;
    for (position, force) in positions.iter().zip(forces) {
        energy += 0.5 * position.norm_squared();
        *force = position.scale(-1.0);
    }
    Ok(energy)
}

#[test]
fn complete_pipeline_preserves_every_allocated_row_and_denominator() {
    let result = search(&fixture_input(), &small_config(), &mut harmonic_evaluator).unwrap();
    let receipt = &result.receipt;
    assert!(result.has_valid_sha256());
    assert!(receipt.result_independent_allocation);
    assert_eq!(receipt.placement_mode, PlacementMode::DualAnchor);
    assert_eq!(receipt.compatible_single_anchor_pair_count, 4);
    assert_eq!(receipt.compatible_dual_anchor_combination_count, 2);
    assert_eq!(receipt.used_anchor_combination_count, 2);
    assert_eq!(receipt.requested_orientation_count, 4);
    assert_eq!(receipt.accepted_orientation_count, 4);
    assert_eq!(receipt.possible_candidate_slot_count, 8);
    assert_eq!(receipt.allocated_candidate_slot_count, 8);
    assert_eq!(receipt.coarse_kept_count, 7);
    assert_eq!(receipt.refinement_selected_count, 5);
    assert_eq!(receipt.refinement_succeeded_count, 5);
    assert_eq!(receipt.evaluator_call_count, 5);
    assert_eq!(result.candidate_rows.len(), 8);
    assert_eq!(
        result
            .candidate_rows
            .iter()
            .map(|row| row.slot_index)
            .collect::<Vec<_>>(),
        (0..8).collect::<Vec<_>>()
    );
    assert_eq!(
        result
            .candidate_rows
            .iter()
            .filter(|row| row.status == CandidateStatus::CoarsePruned)
            .count(),
        1
    );
    assert_eq!(
        result
            .candidate_rows
            .iter()
            .filter(|row| row.status == CandidateStatus::DetailedPruned)
            .count(),
        2
    );
    assert!(result
        .candidate_rows
        .iter()
        .all(|row| row.key.secondary_surface_id.is_some()
            && row.key.secondary_ligand_anchor_id.is_some()
            && row.anchor_fit_rmsd_angstrom <= 1.0e-12));
    assert_eq!(result.poses.len(), receipt.returned_pose_count);
}

#[test]
fn dual_anchor_falls_back_to_single_only_when_no_consistent_pair_exists() {
    let mut input = fixture_input();
    input.surface_samples[1].position_angstrom.x = 20.0;
    let result = search(&input, &small_config(), &mut harmonic_evaluator).unwrap();
    assert_eq!(
        result.receipt.placement_mode,
        PlacementMode::SingleAnchorFallback
    );
    assert_eq!(result.receipt.compatible_dual_anchor_combination_count, 0);
    assert_eq!(result.receipt.used_anchor_combination_count, 4);
    assert!(result.candidate_rows.iter().all(|row| {
        row.key.secondary_surface_id.is_none()
            && row.key.secondary_ligand_anchor_id.is_none()
            && row.placement_mode == PlacementMode::SingleAnchorFallback
    }));
}

#[test]
fn surface_anchor_and_receptor_permutations_are_exactly_invariant() {
    let input = fixture_input();
    let mut permuted = input.clone();
    permuted.ligand_anchors.reverse();
    permuted.surface_samples.reverse();
    permuted.receptor_atoms.reverse();
    let left = search(&input, &small_config(), &mut harmonic_evaluator).unwrap();
    let right = search(&permuted, &small_config(), &mut harmonic_evaluator).unwrap();
    assert_eq!(left, right);
    assert_eq!(input.canonical_sha256(), permuted.canonical_sha256());
    let mut changed = input;
    changed.receptor_atoms[0].charge_elementary += 0.01;
    assert_ne!(changed.canonical_sha256(), permuted.canonical_sha256());
}

#[test]
fn canonical_input_and_config_identities_normalize_directions_and_signed_zero() {
    let input = fixture_input();
    let mut equivalent = input.clone();
    for anchor in &mut equivalent.ligand_anchors {
        anchor.direction = anchor.direction.scale(7.0);
    }
    for surface in &mut equivalent.surface_samples {
        surface.outward_normal = surface.outward_normal.scale(0.25);
    }
    equivalent.ligand_atoms[0].position_angstrom.y = -0.0;
    equivalent.ligand_atoms[2].charge_elementary = -0.0;
    equivalent.receptor_atoms[0].position_angstrom.x = -0.0;
    equivalent.surface_samples[0].position_angstrom.z = -0.0;
    assert_eq!(input.canonical_sha256(), equivalent.canonical_sha256());

    let config = SearchConfig {
        placement_clearance_angstrom: 0.0,
        coarse_clash_weight: 0.0,
        translation_step_angstrom2_per_kcal: 0.0,
        rotation_step_per_torque: 0.0,
        ..small_config()
    };
    let equivalent_config = SearchConfig {
        placement_clearance_angstrom: -0.0,
        coarse_clash_weight: -0.0,
        translation_step_angstrom2_per_kcal: -0.0,
        rotation_step_per_torque: -0.0,
        ..config.clone()
    };
    assert_eq!(
        config.canonical_sha256(),
        equivalent_config.canonical_sha256()
    );
}

#[test]
fn public_5sd5_direction_rows_have_frozen_cross_language_identity() {
    // These are the first anchor/surface rows from the real 5SD5_HWI request
    // whose CPython `math.hypot` normalization differed from Rust/libc by ULPs.
    let input = SearchInput {
        source_seed: [
            0xf8, 0xa7, 0x39, 0x36, 0x16, 0x54, 0xdd, 0x79, 0x2b, 0x28, 0xee, 0xa7, 0x23, 0x80,
            0x2c, 0xcb, 0xfb, 0x97, 0x3e, 0xfe, 0xbd, 0x4c, 0x17, 0x1e, 0x52, 0x9a, 0x47, 0xc2,
            0xdd, 0x30, 0x87, 0xd8,
        ],
        ligand_atoms: vec![LigandAtom {
            position_angstrom: Vec3::new(-3.2869, -3.5712, 2.4783),
            vdw_radius_angstrom: 1.55,
            epsilon_kcal_per_mol: 0.17,
            charge_elementary: -0.367_719_209_024_196_7,
        }],
        ligand_anchors: vec![LigandAnchor {
            id: AnchorId(22),
            atom_index: 0,
            direction: Vec3::new(
                -0.640_973_443_630_728_7,
                -0.596_089_401_035_719_2,
                0.483_560_203_628_299_5,
            ),
            kind: AnchorKind::HydrogenBondDonor,
        }],
        receptor_atoms: vec![ReceptorAtom {
            position_angstrom: Vec3::new(15.522, 10.752, 8.664),
            vdw_radius_angstrom: 1.7,
            epsilon_kcal_per_mol: 0.12,
            charge_elementary: 0.0,
        }],
        surface_samples: vec![SurfaceSample {
            id: SurfaceId(8),
            position_angstrom: Vec3::new(
                3.856_288_487_549_871,
                6.613_194_919_700_477,
                12.322_604_421_462_243,
            ),
            outward_normal: Vec3::new(
                0.411_799_024_225_723,
                -0.843_745_213_096_466_7,
                0.344_260_917_072_415_3,
            ),
            anchor_kind: AnchorKind::HydrogenBondAcceptor,
        }],
    };
    let observed: String = input
        .canonical_sha256()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    assert_eq!(
        observed,
        "8c6d123661e7b1bd404f6ebb92d20f5a07ff58afbbac421e010545b9cde5ea4d"
    );
}

#[test]
fn allocation_is_unchanged_by_evaluator_values() {
    let input = fixture_input();
    let config = small_config();
    let mut positive = |positions: &[Vec3], forces: &mut [Vec3]| {
        forces.fill(Vec3::default());
        Ok(positions
            .iter()
            .map(|position| position.norm_squared())
            .sum())
    };
    let mut negative = |positions: &[Vec3], forces: &mut [Vec3]| {
        forces.fill(Vec3::default());
        Ok(-positions
            .iter()
            .map(|position| position.norm_squared())
            .sum::<f64>())
    };
    let left = search(&input, &config, &mut positive).unwrap();
    let right = search(&input, &config, &mut negative).unwrap();
    assert_eq!(
        left.receipt.allocation_sha256,
        right.receipt.allocation_sha256
    );
    assert_eq!(
        left.receipt.orientation_sha256,
        right.receipt.orientation_sha256
    );
    assert_eq!(
        left.candidate_rows
            .iter()
            .map(|row| row.key)
            .collect::<Vec<_>>(),
        right
            .candidate_rows
            .iter()
            .map(|row| row.key)
            .collect::<Vec<_>>()
    );
}

#[test]
fn stratified_prefix_covers_both_grid_axes_without_result_feedback() {
    let mut input = fixture_input();
    input.ligand_atoms.truncate(1);
    input.ligand_anchors.truncate(1);
    input.ligand_anchors[0].atom_index = 0;
    input.surface_samples = (0..128)
        .map(|index| SurfaceSample {
            id: SurfaceId(index),
            position_angstrom: Vec3::new(index as f64 * 0.1, 0.0, 0.0),
            outward_normal: Vec3::new(0.0, 1.0, 0.0),
            anchor_kind: AnchorKind::HydrogenBondAcceptor,
        })
        .collect();
    let full_config = SearchConfig {
        orientation_count: 64,
        generated_candidate_limit: 64,
        coarse_keep: 64,
        refinement_keep: 1,
        top_k: 1,
        refinement_steps: 0,
        ..SearchConfig::default()
    };
    let mut zero = |_: &[Vec3], forces: &mut [Vec3]| {
        forces.fill(Vec3::default());
        Ok(0.0)
    };
    let full = search(&input, &full_config, &mut zero).unwrap();
    assert_eq!(
        full.candidate_rows
            .iter()
            .map(|row| row.key.orientation_index)
            .collect::<BTreeSet<_>>()
            .len(),
        64
    );
    assert!(
        full.candidate_rows
            .iter()
            .map(|row| row.key.primary_surface_id)
            .collect::<BTreeSet<_>>()
            .len()
            > 1
    );
    assert_eq!(full.receipt.compatible_single_anchor_pair_count, 128);
    assert_eq!(full.receipt.used_anchor_combination_count, 64);
    let prefix_config = SearchConfig {
        generated_candidate_limit: 32,
        coarse_keep: 32,
        ..full_config
    };
    let prefix = search(&input, &prefix_config, &mut zero).unwrap();
    assert_eq!(
        prefix
            .candidate_rows
            .iter()
            .map(|row| row.key)
            .collect::<Vec<_>>(),
        full.candidate_rows[..32]
            .iter()
            .map(|row| row.key)
            .collect::<Vec<_>>()
    );
}

#[test]
fn per_candidate_evaluator_failures_remain_in_ledger_without_aborting_batch() {
    let mut calls = 0usize;
    let mut alternating = |positions: &[Vec3], forces: &mut [Vec3]| {
        calls += 1;
        if calls % 2 == 0 {
            return Err(EvaluationError::new("row-local backend failure"));
        }
        harmonic_evaluator(positions, forces)
    };
    let result = search(&fixture_input(), &small_config(), &mut alternating).unwrap();
    assert_eq!(result.receipt.evaluator_call_count, 5);
    assert_eq!(result.receipt.refinement_evaluator_failed_count, 2);
    assert_eq!(result.receipt.refinement_succeeded_count, 3);
    let failed: Vec<_> = result
        .candidate_rows
        .iter()
        .filter(|row| row.status == CandidateStatus::RefinementFailed)
        .collect();
    assert_eq!(failed.len(), 2);
    assert!(failed.iter().all(|row| {
        row.reason == Some(CandidateReason::EvaluatorFailure)
            && row.detail.as_deref() == Some("row-local backend failure")
            && row.energy_kcal_per_mol.is_none()
    }));
    assert!(result.has_valid_sha256());
}

#[test]
fn evaluator_call_budget_is_fixed_when_all_refinements_succeed() {
    let config = SearchConfig {
        refinement_steps: 3,
        refinement_keep: 2,
        coarse_keep: 2,
        top_k: 1,
        ..small_config()
    };
    let mut calls = 0usize;
    let mut evaluator = |positions: &[Vec3], forces: &mut [Vec3]| {
        calls += 1;
        harmonic_evaluator(positions, forces)
    };
    let result = search(&fixture_input(), &config, &mut evaluator).unwrap();
    assert_eq!(calls, 2 * (3 + 1));
    assert_eq!(result.receipt.evaluator_call_count, calls);
    assert_eq!(result.receipt.maximum_evaluator_call_count, calls);
}

#[test]
fn sha256_identities_detect_config_receipt_and_row_changes() {
    let config = small_config();
    let mut changed = config.clone();
    changed.cluster_rmsd_angstrom += 0.25;
    assert_ne!(config.canonical_sha256(), changed.canonical_sha256());
    let result = search(&fixture_input(), &config, &mut harmonic_evaluator).unwrap();
    assert_eq!(
        result.receipt.input_sha256,
        fixture_input().canonical_sha256()
    );
    assert!(result.receipt.has_valid_sha256());
    assert!(result.has_valid_sha256());
    let mut tampered_receipt = result.clone();
    tampered_receipt.receipt.coarse_keep_budget += 1;
    assert!(!tampered_receipt.has_valid_sha256());
    let mut tampered_row = result;
    tampered_row.candidate_rows[0].coordinates_angstrom[0].x += 0.01;
    assert!(!tampered_row.has_valid_sha256());
    let mut tampered_pose = search(&fixture_input(), &config, &mut harmonic_evaluator).unwrap();
    if let Some(pose) = tampered_pose.poses.first_mut() {
        pose.energy_kcal_per_mol += 0.5;
        assert!(!tampered_pose.has_valid_sha256());
    }
}

#[test]
fn built_in_short_range_is_the_sealed_default_product_path() {
    let result = search_default(&fixture_input(), &small_config()).unwrap();
    assert_eq!(
        result.receipt.evaluator_id,
        "betelgeuze_short_range_analytic/1.0.0"
    );
    assert_ne!(result.receipt.evaluator_config_sha256, [0; 32]);
    assert!(result.has_valid_sha256());
    assert_eq!(result.candidate_rows.len(), 8);
}

#[test]
fn incompatible_anchor_chemistry_fails_closed() {
    let mut input = fixture_input();
    for surface in &mut input.surface_samples {
        surface.anchor_kind = AnchorKind::Positive;
    }
    assert_eq!(
        search(&input, &small_config(), &mut harmonic_evaluator)
            .unwrap_err()
            .code(),
        SearchErrorCode::NoCompatibleAnchors
    );
}

#[test]
fn invalid_input_rows_have_stable_error_codes() {
    let mut cases = Vec::new();
    let mut empty_ligand = fixture_input();
    empty_ligand.ligand_atoms.clear();
    cases.push((empty_ligand, SearchErrorCode::EmptyLigand));
    let mut no_anchor = fixture_input();
    no_anchor.ligand_anchors.clear();
    cases.push((no_anchor, SearchErrorCode::MissingLigandAnchor));
    let mut no_surface = fixture_input();
    no_surface.surface_samples.clear();
    cases.push((no_surface, SearchErrorCode::EmptySurface));
    let mut bad_radius = fixture_input();
    bad_radius.ligand_atoms[0].vdw_radius_angstrom = f64::NAN;
    cases.push((bad_radius, SearchErrorCode::InvalidRadius));
    let mut bad_parameter = fixture_input();
    bad_parameter.ligand_atoms[0].charge_elementary = 17.0;
    cases.push((bad_parameter, SearchErrorCode::InvalidAtomParameter));
    let mut bad_coordinate = fixture_input();
    bad_coordinate.receptor_atoms[0].position_angstrom.x = f64::INFINITY;
    cases.push((bad_coordinate, SearchErrorCode::NonFiniteInput));
    let mut out_of_bounds = fixture_input();
    out_of_bounds.surface_samples[0].position_angstrom.x =
        small_config().maximum_absolute_coordinate_angstrom + 1.0;
    cases.push((out_of_bounds, SearchErrorCode::NonFiniteInput));
    let mut bad_direction = fixture_input();
    bad_direction.ligand_anchors[0].direction = Vec3::default();
    cases.push((bad_direction, SearchErrorCode::InvalidDirection));
    let mut bad_index = fixture_input();
    bad_index.ligand_anchors[0].atom_index = 99;
    cases.push((bad_index, SearchErrorCode::AtomIndexOutOfRange));
    let mut duplicate_anchor = fixture_input();
    duplicate_anchor.ligand_anchors[1].id = duplicate_anchor.ligand_anchors[0].id;
    cases.push((duplicate_anchor, SearchErrorCode::DuplicateIdentifier));
    let mut duplicate_surface = fixture_input();
    duplicate_surface.surface_samples[1].id = duplicate_surface.surface_samples[0].id;
    cases.push((duplicate_surface, SearchErrorCode::DuplicateIdentifier));
    for (input, expected) in cases {
        assert_eq!(
            search(&input, &small_config(), &mut harmonic_evaluator)
                .unwrap_err()
                .code(),
            expected
        );
    }
}

#[test]
fn hard_item_and_configuration_count_caps_fail_closed() {
    let mut input = fixture_input();
    input.ligand_atoms = vec![input.ligand_atoms[0]; MAX_LIGAND_ATOMS + 1];
    assert_eq!(
        search(&input, &small_config(), &mut harmonic_evaluator)
            .unwrap_err()
            .code(),
        SearchErrorCode::TooManyItems
    );
    let base = small_config();
    let mut cases = Vec::new();
    let mut value = base.clone();
    value.orientation_count = 0;
    cases.push(value);
    let mut value = base.clone();
    value.orientation_count = MAX_ORIENTATIONS + 1;
    cases.push(value);
    let mut value = base.clone();
    value.generated_candidate_limit = MAX_GENERATED_CANDIDATES + 1;
    cases.push(value);
    let mut value = base.clone();
    value.coarse_keep = value.generated_candidate_limit + 1;
    cases.push(value);
    let mut value = base.clone();
    value.refinement_keep = value.coarse_keep + 1;
    cases.push(value);
    let mut value = base.clone();
    value.top_k = value.refinement_keep + 1;
    cases.push(value);
    let mut value = base;
    value.refinement_steps = MAX_REFINEMENT_STEPS + 1;
    cases.push(value);
    for config in cases {
        assert_eq!(
            search(&fixture_input(), &config, &mut harmonic_evaluator)
                .unwrap_err()
                .code(),
            SearchErrorCode::InvalidConfiguration
        );
    }
}

#[test]
fn invalid_numeric_configuration_rows_fail_closed() {
    let mut cases = Vec::new();
    let mut value = small_config();
    value.placement_clearance_angstrom = f64::NAN;
    cases.push(value);
    let mut value = small_config();
    value.dual_anchor_distance_tolerance_angstrom = 0.0;
    cases.push(value);
    let mut value = small_config();
    value.coarse_clash_weight = -1.0;
    cases.push(value);
    let mut value = small_config();
    value.translation_step_angstrom2_per_kcal = f64::INFINITY;
    cases.push(value);
    let mut value = small_config();
    value.maximum_rotation_step_radians = core::f64::consts::PI + 0.01;
    cases.push(value);
    let mut value = small_config();
    value.maximum_absolute_coordinate_angstrom = 1.0e9 + 1.0;
    cases.push(value);
    let mut value = small_config();
    value.minimum_receptor_clearance_scale = 1.01;
    cases.push(value);
    let mut value = small_config();
    value.cluster_rmsd_angstrom = 0.0;
    cases.push(value);
    for config in cases {
        assert_eq!(
            search(&fixture_input(), &config, &mut harmonic_evaluator)
                .unwrap_err()
                .code(),
            SearchErrorCode::InvalidConfiguration
        );
    }
}

#[test]
fn nonfinite_evaluator_rows_are_recorded_and_excluded() {
    let mut nonfinite = |_: &[Vec3], forces: &mut [Vec3]| {
        forces.fill(Vec3::default());
        Ok(f64::NEG_INFINITY)
    };
    let result = search(&fixture_input(), &small_config(), &mut nonfinite).unwrap();
    assert_eq!(result.receipt.refinement_non_finite_failed_count, 5);
    assert_eq!(result.receipt.refinement_succeeded_count, 0);
    assert!(result.poses.is_empty());
    assert_eq!(
        result
            .candidate_rows
            .iter()
            .filter(|row| row.reason == Some(CandidateReason::NonFiniteEvaluation))
            .count(),
        5
    );
}

#[test]
fn evaluator_detail_is_utf8_safely_bounded_in_every_failed_row() {
    let huge_detail = "é".repeat(10_000);
    let mut failure = |_: &[Vec3], _: &mut [Vec3]| Err(EvaluationError::new(huge_detail.clone()));
    let result = search(&fixture_input(), &small_config(), &mut failure).unwrap();
    let failed: Vec<_> = result
        .candidate_rows
        .iter()
        .filter(|row| row.status == CandidateStatus::RefinementFailed)
        .collect();
    assert_eq!(failed.len(), 5);
    assert!(failed.iter().all(|row| {
        row.detail
            .as_ref()
            .is_some_and(|detail| detail.len() <= 4_096 && detail.is_char_boundary(detail.len()))
    }));
}

#[test]
fn composite_coordinate_and_pair_work_budgets_fail_before_allocation() {
    let mut anchor_heavy = fixture_input();
    anchor_heavy.surface_samples = (0..2_049)
        .map(|index| SurfaceSample {
            id: SurfaceId(index),
            position_angstrom: Vec3::new(index as f64, 0.0, 0.0),
            outward_normal: Vec3::new(0.0, 1.0, 0.0),
            anchor_kind: AnchorKind::HydrogenBondAcceptor,
        })
        .collect();
    assert_eq!(
        search(&anchor_heavy, &small_config(), &mut harmonic_evaluator)
            .unwrap_err()
            .code(),
        SearchErrorCode::TooManyItems
    );

    let mut coordinate_heavy = fixture_input();
    coordinate_heavy.ligand_atoms = vec![coordinate_heavy.ligand_atoms[0]; 512];
    coordinate_heavy.ligand_anchors.truncate(1);
    coordinate_heavy.ligand_anchors[0].atom_index = 0;
    coordinate_heavy.surface_samples = (0..64)
        .map(|index| SurfaceSample {
            id: SurfaceId(index),
            position_angstrom: Vec3::new(index as f64, 0.0, 0.0),
            outward_normal: Vec3::new(0.0, 1.0, 0.0),
            anchor_kind: AnchorKind::HydrogenBondAcceptor,
        })
        .collect();
    let coordinate_config = SearchConfig {
        orientation_count: 128,
        generated_candidate_limit: 8_192,
        coarse_keep: 1,
        refinement_keep: 1,
        top_k: 1,
        ..SearchConfig::default()
    };
    assert_eq!(
        search(
            &coordinate_heavy,
            &coordinate_config,
            &mut harmonic_evaluator
        )
        .unwrap_err()
        .code(),
        SearchErrorCode::CompositeWorkLimit
    );

    let mut work_heavy = fixture_input();
    work_heavy.ligand_atoms = vec![work_heavy.ligand_atoms[0]; 50];
    work_heavy.ligand_anchors.truncate(1);
    work_heavy.ligand_anchors[0].atom_index = 0;
    work_heavy.surface_samples.truncate(1);
    work_heavy.receptor_atoms = vec![work_heavy.receptor_atoms[0]; 1_000];
    let work_config = SearchConfig {
        orientation_count: 64,
        generated_candidate_limit: 64,
        coarse_keep: 64,
        refinement_keep: 64,
        top_k: 1,
        refinement_steps: 128,
        ..SearchConfig::default()
    };
    assert_eq!(
        search(&work_heavy, &work_config, &mut harmonic_evaluator)
            .unwrap_err()
            .code(),
        SearchErrorCode::CompositeWorkLimit
    );
}

#[test]
fn physical_filter_can_return_empty_top_k_with_complete_rows() {
    let mut input = fixture_input();
    input.receptor_atoms = input
        .surface_samples
        .iter()
        .map(|surface| ReceptorAtom {
            position_angstrom: surface.position_angstrom,
            vdw_radius_angstrom: 100.0,
            epsilon_kcal_per_mol: 0.2,
            charge_elementary: 0.0,
        })
        .collect();
    let result = search(&input, &small_config(), &mut harmonic_evaluator).unwrap();
    assert!(result.poses.is_empty());
    assert_eq!(result.receipt.physical_valid_count, 0);
    assert_eq!(
        result.receipt.rejected_receptor_clash_count,
        result.receipt.refinement_succeeded_count
    );
    assert_eq!(result.candidate_rows.len(), 8);
    assert_eq!(result.receipt.cluster_count, 0);
}
