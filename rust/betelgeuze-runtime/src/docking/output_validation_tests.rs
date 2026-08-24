use super::*;

fn assign_independent_validity_measurements(
    row: &mut sys::bg_docking_pose_validity_row_v1,
    measurements: IndependentValidityMeasurements,
) {
    row.atom_count = measurements.atom_count() as u64;
    row.rotation_orthogonality_max_error = measurements.rotation_orthogonality_max_error();
    row.rotation_determinant = measurements.rotation_determinant();
    row.max_bond_length_delta_angstrom = measurements.max_bond_length_delta_angstrom();
    row.minimum_ligand_nonbonded_distance_angstrom =
        measurements.minimum_ligand_nonbonded_distance_angstrom();
    row.evaluated_ligand_nonbonded_pair_count =
        measurements.evaluated_ligand_nonbonded_pair_count() as u64;
    row.excluded_ligand_pair_count = measurements.excluded_ligand_pair_count() as u64;
    row.minimum_receptor_ligand_distance_angstrom =
        measurements.minimum_receptor_ligand_distance_angstrom();
    row.evaluated_receptor_ligand_pair_count =
        measurements.evaluated_receptor_ligand_pair_count() as u64;
    row.minimum_declared_chiral_volume = measurements.minimum_declared_chiral_volume();
    row.declared_chirality_center_count = measurements.declared_chirality_center_count() as u64;
    row.maximum_pocket_center_distance_angstrom =
        measurements.maximum_pocket_center_distance_angstrom();
    row.element_vdw_ligand_pair_count = measurements.element_vdw_ligand_pair_count() as u64;
    row.element_vdw_ligand_severe_overlap_count =
        measurements.element_vdw_ligand_severe_overlap_count() as u64;
    row.element_vdw_ligand_minimum_distance_angstrom =
        measurements.element_vdw_ligand_minimum_distance_angstrom();
    row.element_vdw_ligand_minimum_ratio = measurements.element_vdw_ligand_minimum_ratio();
    row.element_vdw_receptor_candidate_pair_count =
        measurements.element_vdw_receptor_candidate_pair_count() as u64;
    row.element_vdw_receptor_full_cartesian_pair_count =
        measurements.element_vdw_receptor_full_cartesian_pair_count() as u64;
    row.element_vdw_receptor_cell_count = measurements.element_vdw_receptor_cell_count() as u64;
    row.element_vdw_receptor_severe_overlap_count =
        measurements.element_vdw_receptor_severe_overlap_count() as u64;
    row.element_vdw_receptor_minimum_distance_angstrom =
        measurements.element_vdw_receptor_minimum_distance_angstrom();
    row.element_vdw_receptor_minimum_ratio = measurements.element_vdw_receptor_minimum_ratio();
}

struct IndexFixture {
    ranking: sys::bg_docking_stable_top_k_output_v1,
    cluster: sys::bg_docking_rmsd_cluster_output_v1,
    scorer_rows: Vec<sys::bg_docking_scorer_v1_row_v1>,
    validity_rows: Vec<sys::bg_docking_pose_validity_row_v1>,
    ranking_rows: Vec<sys::bg_docking_stable_top_k_row_v1>,
    refinement_rows: Vec<sys::bg_docking_fixed64_refinement_row_v1>,
    post_admission_rows: Vec<sys::bg_docking_geometric_admission_row_v1>,
    cluster_rows: Vec<sys::bg_docking_rmsd_cluster_row_v1>,
    primary_indices: Vec<u32>,
    valid_indices: Vec<u32>,
    representative_indices: Vec<u32>,
    top_k_indices: Vec<u32>,
    final_coordinates: [Vec<f64>; 3],
    final_quaternions: [Vec<f64>; 4],
    receptor_cells: HashMap<(i64, i64, i64), u64>,
    scorer_context: IndependentScorerContext,
    validity_context: IndependentValidityContext,
}

impl IndexFixture {
    fn valid() -> Self {
        let count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        let mut scorer_rows = vec![zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1); count];
        let mut validity_rows =
            vec![zeroed_abi_value!(sys::bg_docking_pose_validity_row_v1); count];
        let mut ranking_rows = vec![zeroed_abi_value!(sys::bg_docking_stable_top_k_row_v1); count];
        let mut refinement_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1); count];
        let mut post_admission_rows =
            vec![zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1); count];
        let mut cluster_rows = vec![zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1); count];
        let final_coordinates: [Vec<f64>; 3] = std::array::from_fn(|_| vec![0.0; count]);
        let mut final_quaternions: [Vec<f64>; 4] = std::array::from_fn(|_| vec![0.0; count]);
        final_quaternions[3].fill(1.0);
        final_quaternions[0][1] = 1.0;
        let scorer_atom = IndependentScorerAtom {
            charge_elementary: 0.0,
            vdw_radius_angstrom: 0.5,
            epsilon_kcal_per_mol: 0.1,
            hydrophobic: false,
            acceptor: false,
        };
        let scorer_context = IndependentScorerContext::new(
            [1; 32],
            [2; 32],
            [3; 32],
            IndependentScorerBackend::RustCpu,
            [5; 32],
            vec![Vec3::new(1.6, 0.0, 0.0)],
            vec![scorer_atom],
            vec![Vec3::new(0.0, 0.0, 0.0)],
            vec![scorer_atom],
            Vec::new(),
            Vec::new(),
            Vec::new(),
            Vec::new(),
            Vec3::new(0.0, 0.0, 0.0),
            10.0,
            IndependentScorerConfig::default(),
        )
        .expect("valid independent scorer fixture");
        let IndependentScorerOutcome::Scored(scorer_counts) = scorer_context
            .score_coordinates(&[Vec3::new(0.0, 0.0, 0.0)])
            .expect("fixture scorer evaluation")
        else {
            panic!("fixture scorer evaluation unexpectedly failed");
        };
        let validity_context = IndependentValidityContext::new(
            [1; 32],
            [2; 32],
            [3; 32],
            [4; 32],
            IndependentValidityBackend::RustCpu,
            [5; 32],
            [6; 32],
            vec![Vec3::new(0.0, 0.0, 0.0)],
            vec![Vec3::new(1.6, 0.0, 0.0)],
            vec![0.5],
            vec![0.5],
            Vec::new(),
            Vec::new(),
            Vec::new(),
            Vec3::new(0.0, 0.0, 0.0),
            10.0,
            IndependentValidityConfig::default(),
        )
        .expect("valid independent validity fixture");
        for slot in 0..count {
            scorer_rows[slot].slot_index = slot as u32;
            scorer_rows[slot].status = sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
            scorer_rows[slot].failure_code =
                sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
            validity_rows[slot].slot_index = slot as u32;
            validity_rows[slot].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE;
            validity_rows[slot].failure_code =
                sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER;
            validity_rows[slot].upstream_scorer_failure_code =
                sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
            ranking_rows[slot].slot_index = slot as u32;
            post_admission_rows[slot].slot_index = slot as u32;
            post_admission_rows[slot].status =
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE;
            post_admission_rows[slot].failure_code =
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
            post_admission_rows[slot].decision =
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED;
            cluster_rows[slot].slot_index = slot as u32;
            cluster_rows[slot].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID;
        }
        for slot in [0_usize, 1] {
            scorer_rows[slot].status = sys::BG_DOCKING_SCORER_V1_ROW_SCORED;
            scorer_rows[slot].failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            scorer_rows[slot].weighted_terms = scorer_counts.weighted_terms();
            scorer_rows[slot].total_score = scorer_counts.total_score();
            scorer_rows[slot].receptor_candidate_pair_count =
                scorer_counts.receptor_candidate_pair_count() as u64;
            scorer_rows[slot].ligand_pair_count = scorer_counts.ligand_pair_count() as u64;
            scorer_rows[slot].hbond_count = scorer_counts.hbond_count() as u64;
            scorer_rows[slot].hydrophobic_contact_count =
                scorer_counts.hydrophobic_contact_count() as u64;
            scorer_rows[slot].buried_polar_count = scorer_counts.buried_polar_count() as u64;
            ranking_rows[slot].rank_eligible = 1;
            ranking_rows[slot].stable_rank = slot as u32 + 1;
            ranking_rows[slot].total_score = scorer_counts.total_score();
            ranking_rows[slot].coordinate_sha256 = [slot as u8 + 1; 32];
            refinement_rows[slot].status = sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
            post_admission_rows[slot].status = sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
            post_admission_rows[slot].failure_code =
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE;
            post_admission_rows[slot].decision =
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED;
            post_admission_rows[slot].rank_eligible = 1;
        }
        validity_rows[0].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
        validity_rows[0].failure_code = sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
        validity_rows[0].upstream_scorer_failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
        validity_rows[1].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
        validity_rows[1].failure_code = sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
        validity_rows[1].upstream_scorer_failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
        for slot in 0..2 {
            let quaternion = Quaternion::new(
                final_quaternions[0][slot],
                final_quaternions[1][slot],
                final_quaternions[2][slot],
                final_quaternions[3][slot],
            );
            let IndependentValidityOutcome::Evaluated {
                checks,
                measurements,
            } = validity_context
                .evaluate_coordinates(&[Vec3::new(0.0, 0.0, 0.0)], quaternion)
                .expect("fixture validity evaluation")
            else {
                panic!("fixture validity evaluation unexpectedly failed");
            };
            validity_rows[slot].passed_check_mask = independent_validity_check_mask(checks);
            validity_rows[slot].blocker_mask =
                sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ validity_rows[slot].passed_check_mask;
            assign_independent_validity_measurements(&mut validity_rows[slot], measurements);
        }
        ranking_rows[0].valid_rank_eligible = 1;
        ranking_rows[0].stable_valid_rank = 1;
        cluster_rows[0].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
        cluster_rows[0].cluster_eligible = 1;
        cluster_rows[0].representative = 1;
        cluster_rows[0].top_k_representative = 1;
        cluster_rows[0].stable_valid_rank = 1;
        cluster_rows[0].cluster_id = 1;
        cluster_rows[0].representative_slot_index = 0;
        cluster_rows[0].cluster_rank = 1;
        cluster_rows[0].top_k_rank = 1;
        cluster_rows[0].cluster_size = 1;
        cluster_rows[0].coordinate_sha256 = ranking_rows[0].coordinate_sha256;
        let mut ranking = zeroed_abi_value!(sys::bg_docking_stable_top_k_output_v1);
        ranking.primary_index_count = 2;
        ranking.valid_index_count = 1;
        let mut cluster = zeroed_abi_value!(sys::bg_docking_rmsd_cluster_output_v1);
        cluster.representative_index_count = 1;
        cluster.top_k_index_count = 1;
        let mut primary_indices = vec![0; count];
        primary_indices[1] = 1;
        Self {
            ranking,
            cluster,
            scorer_rows,
            validity_rows,
            ranking_rows,
            refinement_rows,
            post_admission_rows,
            cluster_rows,
            primary_indices,
            valid_indices: vec![0; count],
            representative_indices: vec![0; count],
            top_k_indices: vec![0; sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize],
            final_coordinates,
            final_quaternions,
            receptor_cells: HashMap::from([((0, 0, 0), 1)]),
            scorer_context,
            validity_context,
        }
    }

    fn validate(&self) -> Result<()> {
        validate_scorer_and_validity_evidence(
            &self.scorer_rows,
            &self.validity_rows,
            &self.ranking_rows,
            &self.refinement_rows,
            &self.post_admission_rows,
            1,
            1,
            0,
            0,
            3.5,
            &self.receptor_cells,
            [
                self.final_coordinates[0].as_slice(),
                self.final_coordinates[1].as_slice(),
                self.final_coordinates[2].as_slice(),
            ],
            [
                self.final_quaternions[0].as_slice(),
                self.final_quaternions[1].as_slice(),
                self.final_quaternions[2].as_slice(),
                self.final_quaternions[3].as_slice(),
            ],
            &self.scorer_context,
            &self.validity_context,
            Backend::RustCpu,
        )?;
        validate_index_evidence(
            &self.ranking,
            &self.cluster,
            &self.scorer_rows,
            &self.validity_rows,
            &self.ranking_rows,
            &self.cluster_rows,
            &self.primary_indices,
            &self.valid_indices,
            &self.representative_indices,
            &self.top_k_indices,
            2.0,
            [
                self.final_coordinates[0].as_slice(),
                self.final_coordinates[1].as_slice(),
                self.final_coordinates[2].as_slice(),
            ],
            1,
        )
    }
}

#[test]
fn accepts_cross_bound_rank_and_cluster_indices() {
    assert!(IndexFixture::valid().validate().is_ok());
}

#[test]
fn rejects_truncated_top_k_prefix() {
    let mut truncated = IndexFixture::valid();
    truncated.cluster.top_k_index_count = 0;
    truncated.cluster_rows[0].top_k_representative = 0;
    truncated.cluster_rows[0].top_k_rank = 0;
    assert!(truncated.validate().is_err());
}

#[test]
fn rejects_duplicate_or_out_of_range_rank_indices() {
    let mut duplicate = IndexFixture::valid();
    duplicate.primary_indices[1] = 0;
    assert!(duplicate.validate().is_err());

    let mut out_of_range = IndexFixture::valid();
    out_of_range.primary_indices[1] = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT;
    assert!(out_of_range.validate().is_err());
}

#[test]
fn rejects_reordered_or_component_cross_wired_indices() {
    let mut reordered = IndexFixture::valid();
    reordered.primary_indices.swap(0, 1);
    assert!(reordered.validate().is_err());

    let mut cross_wired = IndexFixture::valid();
    cross_wired.cluster_rows[0].coordinate_sha256 = [9; 32];
    assert!(cross_wired.validate().is_err());
}

#[test]
fn rejects_corrupt_scorer_terms_and_failure_sentinels() {
    let mut nonfinite = IndexFixture::valid();
    nonfinite.scorer_rows[0].weighted_terms[0] = f64::NAN;
    assert!(nonfinite.validate().is_err());

    let mut inconsistent_total = IndexFixture::valid();
    inconsistent_total.scorer_rows[0].weighted_terms[0] = 0.5;
    assert!(inconsistent_total.validate().is_err());

    let mut retained_failure_score = IndexFixture::valid();
    retained_failure_score.scorer_rows[2].total_score = 7.0;
    assert!(retained_failure_score.validate().is_err());

    let mut fabricated_interaction_count = IndexFixture::valid();
    fabricated_interaction_count.scorer_rows[0].receptor_candidate_pair_count += 1;
    assert!(fabricated_interaction_count.validate().is_err());

    let mut fabricated_consistent_score = IndexFixture::valid();
    fabricated_consistent_score.scorer_rows[0].weighted_terms[0] += 0.5;
    fabricated_consistent_score.scorer_rows[0].total_score += 0.5;
    fabricated_consistent_score.ranking_rows[0].total_score += 0.5;
    assert!(fabricated_consistent_score.validate().is_err());

    let mut suppressed_success = IndexFixture::valid();
    suppressed_success.scorer_rows[0] = zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1);
    suppressed_success.scorer_rows[0].status = sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
    suppressed_success.scorer_rows[0].failure_code =
        sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
    assert!(suppressed_success.validate().is_err());
}

#[test]
fn rejects_valid_rank_reordered_independently_of_primary_rank() {
    let mut fixture = IndexFixture::valid();
    fixture.final_quaternions[0][1] = 0.0;
    let IndependentValidityOutcome::Evaluated {
        checks,
        measurements,
    } = fixture
        .validity_context
        .evaluate_coordinates(
            &[Vec3::new(0.0, 0.0, 0.0)],
            Quaternion::new(0.0, 0.0, 0.0, 1.0),
        )
        .expect("second valid-rank fixture evaluation")
    else {
        panic!("second valid-rank fixture unexpectedly failed");
    };
    assert!(checks.all());
    fixture.validity_rows[1].passed_check_mask = independent_validity_check_mask(checks);
    fixture.validity_rows[1].blocker_mask = 0;
    assign_independent_validity_measurements(&mut fixture.validity_rows[1], measurements);
    fixture.ranking.valid_index_count = 2;
    fixture.valid_indices[0] = 1;
    fixture.valid_indices[1] = 0;
    fixture.ranking_rows[0].stable_valid_rank = 2;
    fixture.ranking_rows[1].valid_rank_eligible = 1;
    fixture.ranking_rows[1].stable_valid_rank = 1;
    assert!(fixture.validate().is_err());
}

#[test]
fn rejects_valid_rank_with_inconsistent_blocker_mask() {
    let mut fixture = IndexFixture::valid();
    fixture.validity_rows[0].blocker_mask =
        sys::BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH;
    assert!(fixture.validate().is_err());
}

#[test]
fn rejects_self_consistent_but_unrederived_validity_bits_and_measurements() {
    let mut fabricated_bit = IndexFixture::valid();
    fabricated_bit.validity_rows[0].passed_check_mask ^=
        sys::BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS;
    fabricated_bit.validity_rows[0].blocker_mask =
        sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ fabricated_bit.validity_rows[0].passed_check_mask;
    fabricated_bit.ranking_rows[0].valid_rank_eligible = 0;
    fabricated_bit.ranking_rows[0].stable_valid_rank = 0;
    fabricated_bit.ranking.valid_index_count = 0;
    fabricated_bit.cluster.representative_index_count = 0;
    fabricated_bit.cluster.top_k_index_count = 0;
    fabricated_bit.cluster_rows[0] = zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1);
    fabricated_bit.cluster_rows[0].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID;
    assert!(fabricated_bit.validate().is_err());

    let mut fabricated_measurement = IndexFixture::valid();
    fabricated_measurement.validity_rows[0].max_bond_length_delta_angstrom = 0.01;
    assert!(fabricated_measurement.validate().is_err());
}

#[test]
fn rejects_invalid_cluster_rmsd_evidence() {
    let mut nonfinite = IndexFixture::valid();
    nonfinite.cluster_rows[0].direct_rmsd_to_representative_angstrom = f64::NAN;
    assert!(nonfinite.validate().is_err());

    let mut representative_distance = IndexFixture::valid();
    representative_distance.cluster_rows[0].direct_rmsd_to_representative_angstrom = 0.5;
    assert!(representative_distance.validate().is_err());
}

#[test]
fn rejects_wrong_validity_measurement_denominators() {
    let mut wrong_atom_count = IndexFixture::valid();
    wrong_atom_count.validity_rows[0].atom_count = 2;
    assert!(wrong_atom_count.validate().is_err());

    let mut wrong_receptor_pairs = IndexFixture::valid();
    wrong_receptor_pairs.validity_rows[0].evaluated_receptor_ligand_pair_count = 0;
    assert!(wrong_receptor_pairs.validate().is_err());

    let mut wrong_candidate_pairs = IndexFixture::valid();
    wrong_candidate_pairs.validity_rows[0].element_vdw_receptor_candidate_pair_count = 0;
    assert!(wrong_candidate_pairs.validate().is_err());

    let mut passed_despite_severe_overlap = IndexFixture::valid();
    passed_despite_severe_overlap.validity_rows[0].element_vdw_receptor_severe_overlap_count = 1;
    assert!(passed_despite_severe_overlap.validate().is_err());
}

#[test]
fn rejects_cluster_assignment_that_skips_an_earlier_matching_representative() {
    let mut fixture = IndexFixture::valid();
    fixture.ranking.valid_index_count = 2;
    fixture.valid_indices[1] = 1;
    fixture.validity_rows[1].passed_check_mask = sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
    fixture.validity_rows[1].blocker_mask = 0;
    fixture.ranking_rows[1].valid_rank_eligible = 1;
    fixture.ranking_rows[1].stable_valid_rank = 2;
    fixture.cluster.representative_index_count = 2;
    fixture.representative_indices[1] = 1;
    fixture.cluster_rows[1].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
    fixture.cluster_rows[1].cluster_eligible = 1;
    fixture.cluster_rows[1].representative = 1;
    fixture.cluster_rows[1].stable_valid_rank = 2;
    fixture.cluster_rows[1].cluster_id = 2;
    fixture.cluster_rows[1].representative_slot_index = 1;
    fixture.cluster_rows[1].cluster_rank = 2;
    fixture.cluster_rows[1].cluster_size = 1;
    fixture.cluster_rows[1].coordinate_sha256 = fixture.ranking_rows[1].coordinate_sha256;
    assert!(fixture.validate().is_err());
}

#[test]
fn rejects_representative_list_reversed_from_stable_valid_rank_order() {
    let mut fixture = IndexFixture::valid();
    fixture.final_coordinates[0][1] = 3.0;
    fixture.final_quaternions[0][1] = 0.0;
    let IndependentValidityOutcome::Evaluated {
        checks,
        measurements,
    } = fixture
        .validity_context
        .evaluate_coordinates(
            &[Vec3::new(3.0, 0.0, 0.0)],
            Quaternion::new(0.0, 0.0, 0.0, 1.0),
        )
        .expect("far representative validity evaluation")
    else {
        panic!("far representative unexpectedly produced a typed failure");
    };
    assert!(checks.all());
    fixture.validity_rows[1].passed_check_mask = independent_validity_check_mask(checks);
    fixture.validity_rows[1].blocker_mask = 0;
    assign_independent_validity_measurements(&mut fixture.validity_rows[1], measurements);
    fixture.ranking.valid_index_count = 2;
    fixture.valid_indices[1] = 1;
    fixture.ranking_rows[1].valid_rank_eligible = 1;
    fixture.ranking_rows[1].stable_valid_rank = 2;
    fixture.cluster.representative_index_count = 2;
    fixture.cluster.top_k_index_count = 1;
    fixture.representative_indices[0] = 1;
    fixture.representative_indices[1] = 0;
    fixture.top_k_indices[0] = 1;

    fixture.cluster_rows[0].top_k_representative = 0;
    fixture.cluster_rows[0].top_k_rank = 0;
    fixture.cluster_rows[0].cluster_id = 2;
    fixture.cluster_rows[0].cluster_rank = 2;
    fixture.cluster_rows[1].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
    fixture.cluster_rows[1].cluster_eligible = 1;
    fixture.cluster_rows[1].representative = 1;
    fixture.cluster_rows[1].top_k_representative = 1;
    fixture.cluster_rows[1].stable_valid_rank = 2;
    fixture.cluster_rows[1].cluster_id = 1;
    fixture.cluster_rows[1].representative_slot_index = 1;
    fixture.cluster_rows[1].cluster_rank = 1;
    fixture.cluster_rows[1].top_k_rank = 1;
    fixture.cluster_rows[1].cluster_size = 1;
    fixture.cluster_rows[1].coordinate_sha256 = fixture.ranking_rows[1].coordinate_sha256;
    assert!(fixture.validate().is_err());
}

#[test]
fn rejects_component_and_pipeline_receipt_substitution() {
    let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_pipeline_row_v2);
    let component_binding = [1; 32];
    let policy = [2; 32];
    let refinement = [3; 32];
    let scorer = [4; 32];
    let validity = [5; 32];
    let ranking = [6; 32];
    let cluster = [7; 32];
    let post_policy = [8; 32];
    row.post_admission_row_receipt_sha256 = [9; 32];
    row.refinement_evidence_sha256 = refinement;
    row.scorer_evidence_sha256 = scorer;
    row.validity_evidence_sha256 = validity;
    row.ranking_evidence_sha256 = ranking;
    row.cluster_evidence_sha256 = cluster;
    row.row_receipt_sha256 = canonical_pipeline_row_receipt(
        &row,
        component_binding,
        policy,
        post_policy,
        refinement,
        scorer,
        validity,
        ranking,
        cluster,
    );
    assert!(validate_pipeline_receipt_bindings(
        &row,
        component_binding,
        policy,
        post_policy,
        refinement,
        scorer,
        validity,
        ranking,
        cluster,
    )
    .is_ok());

    let mut substituted_component = row;
    substituted_component.scorer_evidence_sha256 = [10; 32];
    assert!(validate_pipeline_receipt_bindings(
        &substituted_component,
        component_binding,
        policy,
        post_policy,
        refinement,
        scorer,
        validity,
        ranking,
        cluster,
    )
    .is_err());

    let mut substituted_row = row;
    substituted_row.row_receipt_sha256 = [11; 32];
    assert!(validate_pipeline_receipt_bindings(
        &substituted_row,
        component_binding,
        policy,
        post_policy,
        refinement,
        scorer,
        validity,
        ranking,
        cluster,
    )
    .is_err());
}

fn generated_producer_row(
    source: Fixed64CoordinateSource<'_>,
) -> sys::bg_docking_fixed64_producer_row_v1 {
    let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
    row.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
    row.failure_code = sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE;
    row.lane = sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS;
    row.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
    row.ligand_atom_count = 1;
    row.allocation_slot_receipt_sha256 = [1; 32];
    row.source_payload_receipt_sha256 = canonical_source_payload_sha256(source, 1);
    row.source_proposal_sha256 = source.evidence.proposal_sha256;
    row.source_coordinate_sha256 = source.evidence.coordinate_sha256;
    row.placement_receipt_sha256 = [5; 32];
    row.output_proposal_sha256 = row.source_proposal_sha256;
    row.output_coordinate_sha256 = row.source_coordinate_sha256;
    row.coordinates_available = 1;
    row.source_identity_verified = 1;
    row.allocation_identity_verified = 1;
    row.geometric_identity_verified = 1;
    row.denominator_preserved = 1;
    row.placement_quaternion_w = 1.0;
    row
}

#[test]
fn rejects_producer_success_and_failure_sentinel_corruption() {
    let coordinates = [vec![0.0], vec![0.0], vec![0.0]];
    let views = [
        coordinates[0].as_slice(),
        coordinates[1].as_slice(),
        coordinates[2].as_slice(),
    ];
    let source_coordinates = PositionSoa::new(views[0], views[1], views[2]);
    let source = Fixed64CoordinateSource {
        evidence: Fixed64SourceEvidence {
            receipt_sha256: [2; 32],
            proposal_sha256: [3; 32],
            coordinate_sha256: canonical_coordinate_sha256(source_coordinates),
        },
        coordinates: source_coordinates,
    };
    let valid = generated_producer_row(source);
    assert!(validate_producer_row_semantics(&valid, views, 0, 1, Some(source)).is_ok());

    let mut nonunit = generated_producer_row(source);
    nonunit.placement_quaternion_w = 0.5;
    assert!(validate_producer_row_semantics(&nonunit, views, 0, 1, Some(source)).is_err());

    let mut wrong_lane = generated_producer_row(source);
    wrong_lane.lane = sys::BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS;
    assert!(validate_producer_row_semantics(&wrong_lane, views, 0, 1, Some(source)).is_err());

    let mut cross_wired_passthrough = generated_producer_row(source);
    cross_wired_passthrough.output_coordinate_sha256 = [9; 32];
    assert!(
        validate_producer_row_semantics(&cross_wired_passthrough, views, 0, 1, Some(source),)
            .is_err()
    );

    let mut cross_wired_source = generated_producer_row(source);
    cross_wired_source.source_proposal_sha256 = [9; 32];
    assert!(
        validate_producer_row_semantics(&cross_wired_source, views, 0, 1, Some(source),).is_err()
    );

    let different_coordinates = [vec![1.0], vec![0.0], vec![0.0]];
    let different_views = [
        different_coordinates[0].as_slice(),
        different_coordinates[1].as_slice(),
        different_coordinates[2].as_slice(),
    ];
    assert!(validate_producer_row_semantics(&valid, different_views, 0, 1, Some(source),).is_err());

    let mut failure = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
    failure.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
    failure.failure_code = sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE;
    failure.lane = sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS;
    failure.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
    failure.ligand_atom_count = 1;
    failure.allocation_slot_receipt_sha256 = [1; 32];
    failure.allocation_identity_verified = 1;
    failure.geometric_identity_verified = 1;
    failure.denominator_preserved = 1;
    assert!(validate_producer_row_semantics(&failure, views, 0, 1, None).is_ok());
    let mut spurious_placement = failure;
    spurious_placement.placement_receipt_sha256 = [8; 32];
    assert!(validate_producer_row_semantics(&spurious_placement, views, 0, 1, None).is_err());
    failure.coordinates_available = 1;
    assert!(validate_producer_row_semantics(&failure, views, 0, 1, None).is_err());

    let mut indexed_failure_on_passthrough = generated_producer_row(source);
    indexed_failure_on_passthrough.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
    indexed_failure_on_passthrough.failure_code =
        sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE;
    indexed_failure_on_passthrough.component_failure_code =
        sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY;
    indexed_failure_on_passthrough.coordinates_available = 0;
    indexed_failure_on_passthrough.output_proposal_sha256 = [0; 32];
    indexed_failure_on_passthrough.output_coordinate_sha256 = [0; 32];
    indexed_failure_on_passthrough.placement_quaternion_w = 0.0;
    assert!(validate_producer_row_semantics(
        &indexed_failure_on_passthrough,
        views,
        0,
        1,
        Some(source),
    )
    .is_err());

    let mut feature_failure_on_passthrough = indexed_failure_on_passthrough;
    feature_failure_on_passthrough.failure_code =
        sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE;
    feature_failure_on_passthrough.component_failure_code = 0;
    feature_failure_on_passthrough.placement_receipt_sha256 = [0; 32];
    assert!(validate_producer_row_semantics(
        &feature_failure_on_passthrough,
        views,
        0,
        1,
        Some(source),
    )
    .is_err());

    let mut transformed_coordinates: [Vec<f64>; 3] = std::array::from_fn(|_| vec![0.0; 64]);
    let transformed_views = [
        transformed_coordinates[0].as_slice(),
        transformed_coordinates[1].as_slice(),
        transformed_coordinates[2].as_slice(),
    ];
    let mut transformed = generated_producer_row(source);
    transformed.lane = sys::BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3;
    transformed.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3;
    assert!(
        validate_producer_row_semantics(&transformed, transformed_views, 24, 1, Some(source),)
            .is_ok()
    );
    transformed_coordinates[0][24] = 1.0;
    let substituted_views = [
        transformed_coordinates[0].as_slice(),
        transformed_coordinates[1].as_slice(),
        transformed_coordinates[2].as_slice(),
    ];
    assert!(
        validate_producer_row_semantics(&transformed, substituted_views, 24, 1, Some(source),)
            .is_err()
    );

    let mut contradicted_source_failure = generated_producer_row(source);
    contradicted_source_failure.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
    contradicted_source_failure.failure_code =
        sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE;
    contradicted_source_failure.coordinates_available = 0;
    contradicted_source_failure.placement_receipt_sha256 = [0; 32];
    contradicted_source_failure.output_proposal_sha256 = [0; 32];
    contradicted_source_failure.output_coordinate_sha256 = [0; 32];
    contradicted_source_failure.placement_quaternion_w = 0.0;
    assert!(validate_producer_row_semantics(
        &contradicted_source_failure,
        views,
        0,
        1,
        Some(source),
    )
    .is_err());

    contradicted_source_failure.failure_code =
        sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_LIGAND_DENOMINATOR_MISMATCH;
    assert!(validate_producer_row_semantics(
        &contradicted_source_failure,
        views,
        0,
        1,
        Some(source),
    )
    .is_err());
}

fn accepted_geometric_fixture() -> (
    sys::bg_docking_geometric_admission_row_v1,
    IndependentFixed64GeometricInput,
    [Vec<f64>; 3],
) {
    let coordinates = [vec![5.0, 6.0], vec![0.0, 0.0], vec![0.0, 0.0]];
    let input = IndependentFixed64GeometricInput::new(
        vec![1.0, 1.0],
        vec![true, false],
        vec![
            Vec3::new(0.0, 0.0, 0.0),
            Vec3::new(0.0, 5.0, 0.0),
            Vec3::new(0.0, -5.0, 0.0),
        ],
        vec![1.0; 3],
        Vec3::new(5.5, 0.0, 0.0),
        10.0,
    )
    .expect("valid geometric fixture");
    let metrics = evaluate_fixed64_geometric_metrics(
        &[Vec3::new(5.0, 0.0, 0.0), Vec3::new(6.0, 0.0, 0.0)],
        &input,
    )
    .expect("valid geometric metrics");
    let mut row = zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1);
    row.status = sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
    row.failure_code = sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE;
    row.decision = sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED;
    row.rank_eligible = 1;
    row.ligand_atom_count = 2;
    row.receptor_atom_count = 3;
    row.exact_pair_count = 6;
    row.raw_minimum_distance_angstrom = metrics.raw_minimum_distance_angstrom();
    row.minimum_vdw_surface_gap_angstrom = metrics.minimum_vdw_surface_gap_angstrom();
    row.minimum_vdw_ratio = metrics.minimum_vdw_ratio();
    row.penetration_pair_count = metrics.penetration_pair_count() as u64;
    row.unique_ligand_penetration_atom_count =
        metrics.unique_ligand_penetration_atom_count() as u64;
    row.unique_ligand_heavy_atom_penetration_count =
        metrics.unique_ligand_heavy_atom_penetration_count() as u64;
    row.sphere_overlap_proxy_angstrom3 = metrics.sphere_overlap_proxy_angstrom3();
    row.pocket_escape_angstrom = metrics.pocket_escape_angstrom();
    row.row_receipt_sha256 = [1; 32];
    (row, input, coordinates)
}

#[test]
fn rejects_malformed_geometric_admission_semantics() {
    let (valid, input, coordinates) = accepted_geometric_fixture();
    let views = [
        coordinates[0].as_slice(),
        coordinates[1].as_slice(),
        coordinates[2].as_slice(),
    ];
    assert!(validate_geometric_admission_row_semantics(
        &valid,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_ok());

    let mut wrong_failure = valid;
    wrong_failure.failure_code = sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
    assert!(validate_geometric_admission_row_semantics(
        &wrong_failure,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_err());

    let mut nonfinite = valid;
    nonfinite.sphere_overlap_proxy_angstrom3 = f64::NAN;
    assert!(validate_geometric_admission_row_semantics(
        &nonfinite,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_err());

    let mut inconsistent_penetration = valid;
    inconsistent_penetration.penetration_pair_count = 1;
    assert!(validate_geometric_admission_row_semantics(
        &inconsistent_penetration,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_err());

    let mut threshold_mismatch = valid;
    threshold_mismatch.minimum_vdw_ratio = 0.5;
    assert!(validate_geometric_admission_row_semantics(
        &threshold_mismatch,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_err());

    let mut fabricated_minimum = valid;
    fabricated_minimum.raw_minimum_distance_angstrom += 0.25;
    assert!(validate_geometric_admission_row_semantics(
        &fabricated_minimum,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_err());

    let mut upstream = zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1);
    upstream.status = sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE;
    upstream.failure_code = sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
    upstream.decision = sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED;
    upstream.row_receipt_sha256 = [1; 32];
    assert!(validate_geometric_admission_row_semantics(
        &upstream,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_ok());
    assert!(validate_geometric_admission_row_semantics(
        &upstream,
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
        3,
        2,
        1,
        6,
        0.55,
        Backend::RustCpu,
        &input,
        views,
        0,
    )
    .is_err());
}

fn valid_rigid_v2_row() -> sys::bg_docking_rigid_refinement_row_v1 {
    let mut row = zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1);
    row.status = sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
    row.failure_code = sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    row.candidate_mode = sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
    row.selected_profile = sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION;
    row.selected.profile = sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION;
    row.selected.available = 1;
    row
}

#[test]
fn rejects_malformed_rigid_refinement_semantics() {
    let coordinates: [Vec<f64>; 12] = std::array::from_fn(|_| vec![0.0]);
    let valid = valid_rigid_v2_row();
    assert!(validate_rigid_row_semantics(
        &valid,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        0,
        &coordinates,
        0,
        1,
    )
    .is_ok());

    let mut nonfinite = valid_rigid_v2_row();
    nonfinite.selected.final_penalty = f64::NAN;
    assert!(validate_rigid_row_semantics(
        &nonfinite,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        0,
        &coordinates,
        0,
        1,
    )
    .is_err());

    let mut mismatched_steps = valid_rigid_v2_row();
    mismatched_steps.selected.accepted_steps = 1;
    assert!(validate_rigid_row_semantics(
        &mismatched_steps,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        1,
        &coordinates,
        0,
        1,
    )
    .is_err());

    let mut over_budget = valid_rigid_v2_row();
    over_budget.selected.accepted_steps = 1;
    over_budget.selected.accepted_translation_steps = 1;
    assert!(validate_rigid_row_semantics(
        &over_budget,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        0,
        &coordinates,
        0,
        1,
    )
    .is_err());
}

#[test]
fn rejects_rigid_coordinates_not_replayed_from_the_owned_producer_pose() {
    let producer_coordinates = [vec![0.0], vec![0.0], vec![0.0]];
    let producer_views = [
        producer_coordinates[0].as_slice(),
        producer_coordinates[1].as_slice(),
        producer_coordinates[2].as_slice(),
    ];
    let mut rigid_coordinates: [Vec<f64>; 12] = std::array::from_fn(|_| vec![0.0]);
    let geometric_input = IndependentFixed64GeometricInput::new(
        vec![0.5],
        vec![true],
        vec![Vec3::new(5.0, 0.0, 0.0)],
        vec![0.5],
        Vec3::new(0.0, 0.0, 0.0),
        10.0,
    )
    .expect("valid independent rigid replay fixture");
    let row = valid_rigid_v2_row();
    assert!(validate_independent_rigid_replay(
        Backend::RustCpu,
        &row,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        1,
        producer_views,
        &rigid_coordinates,
        0,
        1,
        &geometric_input,
        IndependentRigidV2Config::default(),
        IndependentRigidV3Config::default(),
        IndependentRigidV3Config::clearance_v4(),
    )
    .is_ok());

    rigid_coordinates[0][0] = 1.0;
    assert!(validate_independent_rigid_replay(
        Backend::RustCpu,
        &row,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        1,
        producer_views,
        &rigid_coordinates,
        0,
        1,
        &geometric_input,
        IndependentRigidV2Config::default(),
        IndependentRigidV3Config::default(),
        IndependentRigidV3Config::clearance_v4(),
    )
    .is_err());

    let mut suppressed = zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1);
    suppressed.status = sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE;
    suppressed.failure_code = sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT;
    suppressed.candidate_mode = sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
    assert!(validate_independent_rigid_replay(
        Backend::RustCpu,
        &suppressed,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
        1,
        producer_views,
        &rigid_coordinates,
        0,
        1,
        &geometric_input,
        IndependentRigidV2Config::default(),
        IndependentRigidV3Config::default(),
        IndependentRigidV3Config::clearance_v4(),
    )
    .is_err());
}

fn refined_torsion_fixture() -> (
    Vec<sys::bg_docking_torsion_v7_row_v1>,
    Vec<sys::bg_docking_torsion_v7_move_v1>,
) {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
    let mut rows = vec![zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1); candidate_count];
    for (slot, candidate) in rows.iter_mut().enumerate() {
        candidate.slot_index = slot as u32;
        candidate.status = sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
        candidate.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE;
    }
    let mut row = zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1);
    row.status = sys::BG_DOCKING_TORSION_V7_ROW_REFINED;
    row.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_NONE;
    row.skip_reason = sys::BG_DOCKING_TORSION_V7_SKIP_NONE;
    row.selection_reason = sys::BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_OUTSIDE_WINDOW;
    row.selection_window_reachable = 1;
    row.torsion_evaluated = 1;
    row.torsion_variant_available = 1;
    row.torsion_step_budget = 1;
    row.fixed_objective_evaluation_count = 2;
    row.evaluated_torsion_steps = 1;
    row.evaluated_total_torsion_path_radians = 0.1;
    rows[0] = row;
    let mut moves = vec![
        zeroed_abi_value!(sys::bg_docking_torsion_v7_move_v1);
        candidate_count * moves_per_slot
    ];
    for (index, movement) in moves.iter_mut().enumerate() {
        movement.slot_index = (index / moves_per_slot) as u32;
        movement.move_index = (index % moves_per_slot) as u32;
    }
    moves[0].evaluated = 1;
    moves[0].rotatable_child_atom_index = 5;
    moves[0].delta_radians = 0.1;
    (rows, moves)
}

#[test]
fn rejects_torsion_moves_cross_wired_from_parent_rows() {
    let (rows, moves) = refined_torsion_fixture();
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    let mut rigid =
        vec![zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1); candidate_count];
    rigid[0].status = sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
    rigid[0].candidate_mode = sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE;
    let mut eligibility = vec![0_u8; candidate_count];
    eligibility[0] = 1;
    let mut max_steps = vec![0_u64; candidate_count];
    max_steps[0] = 1;
    let torsion_coordinates: [Vec<f64>; 8] = std::array::from_fn(|_| vec![0.0; candidate_count]);
    let rigid_coordinates: [Vec<f64>; 12] = std::array::from_fn(|_| vec![0.0; candidate_count]);
    let baseline_angles = vec![0.0; candidate_count];
    let validation = validate_torsion_evidence(
        &rows,
        &moves,
        &rigid,
        &eligibility,
        &max_steps,
        4,
        &[5],
        &torsion_coordinates,
        &rigid_coordinates,
        &baseline_angles,
        1,
    );
    assert!(validation.is_ok(), "{validation:?}");

    let mut wrong_final_coordinates = torsion_coordinates.clone();
    wrong_final_coordinates[4][0] = 1.0;
    assert!(validate_torsion_evidence(
        &rows,
        &moves,
        &rigid,
        &eligibility,
        &max_steps,
        4,
        &[5],
        &wrong_final_coordinates,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());

    let mut nonfinite_optimized = torsion_coordinates.clone();
    nonfinite_optimized[0][0] = f64::NAN;
    assert!(validate_torsion_evidence(
        &rows,
        &moves,
        &rigid,
        &eligibility,
        &max_steps,
        4,
        &[5],
        &nonfinite_optimized,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());

    let mut retained_typed_failure_coordinate = torsion_coordinates.clone();
    retained_typed_failure_coordinate[0][1] = 1.0;
    assert!(validate_torsion_evidence(
        &rows,
        &moves,
        &rigid,
        &eligibility,
        &max_steps,
        4,
        &[5],
        &retained_typed_failure_coordinate,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());

    let mut wrong_child = moves.clone();
    wrong_child[0].rotatable_child_atom_index = 6;
    assert!(validate_torsion_evidence(
        &rows,
        &wrong_child,
        &rigid,
        &eligibility,
        &max_steps,
        4,
        &[5],
        &torsion_coordinates,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());

    let mut outside_prefix = moves.clone();
    outside_prefix[1].evaluated = 1;
    outside_prefix[1].rotatable_child_atom_index = 5;
    outside_prefix[1].delta_radians = 0.1;
    assert!(validate_torsion_evidence(
        &rows,
        &outside_prefix,
        &rigid,
        &eligibility,
        &max_steps,
        4,
        &[5],
        &torsion_coordinates,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());

    let disabled = vec![0_u8; candidate_count];
    assert!(validate_torsion_evidence(
        &rows,
        &moves,
        &rigid,
        &disabled,
        &max_steps,
        4,
        &[5],
        &torsion_coordinates,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());

    let capped = vec![0_u64; candidate_count];
    assert!(validate_torsion_evidence(
        &rows,
        &moves,
        &rigid,
        &eligibility,
        &capped,
        4,
        &[5],
        &torsion_coordinates,
        &rigid_coordinates,
        &baseline_angles,
        1,
    )
    .is_err());
}

struct RefinementFixture {
    rows: Vec<sys::bg_docking_fixed64_refinement_row_v1>,
    producer: Vec<sys::bg_docking_fixed64_producer_row_v1>,
    rigid: Vec<sys::bg_docking_rigid_refinement_row_v1>,
    torsion: Vec<sys::bg_docking_torsion_v7_row_v1>,
    coordinates: [Vec<f64>; 3],
    quaternions: [Vec<f64>; 4],
}

fn valid_refinement_fixture() -> RefinementFixture {
    let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1);
    row.status = sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
    row.failure_stage = sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE;
    row.coordinate_origin = sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED;
    row.rigid_failure_code = sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    row.selected_rigid_profile = sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION;
    row.downstream_candidate_state = sys::BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
    row.coordinate_available = 1;
    let coordinates: [Vec<f64>; 3] = std::array::from_fn(|_| vec![0.0]);
    row.coordinate_sha256 = canonical_coordinate_sha256(PositionSoa::new(
        &coordinates[0],
        &coordinates[1],
        &coordinates[2],
    ));
    let rigid = valid_rigid_v2_row();
    let mut producer = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
    producer.placement_quaternion_w = 1.0;
    let mut torsion = zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1);
    torsion.status = sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
    torsion.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE;
    RefinementFixture {
        rows: vec![row],
        producer: vec![producer],
        rigid: vec![rigid],
        torsion: vec![torsion],
        coordinates,
        quaternions: [vec![0.0], vec![0.0], vec![0.0], vec![1.0]],
    }
}

#[test]
fn rejects_incomplete_coordinate_ready_refinement_evidence() {
    let mut fixture = valid_refinement_fixture();
    let coordinate_views = [
        fixture.coordinates[0].as_slice(),
        fixture.coordinates[1].as_slice(),
        fixture.coordinates[2].as_slice(),
    ];
    let quaternion_views = [
        fixture.quaternions[0].as_slice(),
        fixture.quaternions[1].as_slice(),
        fixture.quaternions[2].as_slice(),
        fixture.quaternions[3].as_slice(),
    ];
    assert!(validate_refinement_evidence(
        &fixture.rows,
        &fixture.producer,
        &fixture.rigid,
        &fixture.torsion,
        &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
        coordinate_views,
        coordinate_views,
        coordinate_views,
        quaternion_views,
        1,
        Backend::RustCpu,
    )
    .is_ok());

    let substituted_quaternion = [vec![1.0], vec![0.0], vec![0.0], vec![0.0]];
    assert!(validate_refinement_evidence(
        &fixture.rows,
        &fixture.producer,
        &fixture.rigid,
        &fixture.torsion,
        &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
        coordinate_views,
        coordinate_views,
        coordinate_views,
        [
            substituted_quaternion[0].as_slice(),
            substituted_quaternion[1].as_slice(),
            substituted_quaternion[2].as_slice(),
            substituted_quaternion[3].as_slice(),
        ],
        1,
        Backend::RustCpu,
    )
    .is_err());

    let mismatched_origin = [vec![1.0], vec![0.0], vec![0.0]];
    let mismatched_origin_views = [
        mismatched_origin[0].as_slice(),
        mismatched_origin[1].as_slice(),
        mismatched_origin[2].as_slice(),
    ];
    assert!(validate_refinement_evidence(
        &fixture.rows,
        &fixture.producer,
        &fixture.rigid,
        &fixture.torsion,
        &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
        mismatched_origin_views,
        coordinate_views,
        coordinate_views,
        quaternion_views,
        1,
        Backend::RustCpu,
    )
    .is_err());

    fixture.rows[0].coordinate_available = 0;
    assert!(validate_refinement_evidence(
        &fixture.rows,
        &fixture.producer,
        &fixture.rigid,
        &fixture.torsion,
        &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
        coordinate_views,
        coordinate_views,
        coordinate_views,
        quaternion_views,
        1,
        Backend::RustCpu,
    )
    .is_err());
}
