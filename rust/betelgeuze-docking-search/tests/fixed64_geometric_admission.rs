use betelgeuze_docking_search::{
    evaluate_fixed64_geometric_metrics, native_fixed64_coordinate_sha256, Fixed64Allocation,
    Fixed64ExactV11SourceEvidence, Fixed64FeatureInventory, Fixed64GeometricBatch,
    Fixed64GeometricErrorCode, Fixed64GeometricInput, Fixed64GeometricStatus,
    Fixed64MissingFeature, Vec3, FIXED64_CANDIDATE_COUNT, FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    HARD_REJECTION_MINIMUM_VDW_RATIO,
};

fn digest(marker: u8) -> [u8; 32] {
    [marker; 32]
}

fn exact_source() -> Fixed64ExactV11SourceEvidence {
    Fixed64ExactV11SourceEvidence {
        source_receipt_sha256: digest(1),
        proposal_sha256: digest(2),
        ligand_coordinate_sha256: digest(3),
        receptor_coordinate_sha256: digest(4),
        prepared_ligand_topology_sha256: digest(5),
        prepared_receptor_topology_sha256: digest(6),
        ligand_vdw_radii_sha256: digest(7),
        ligand_heavy_atom_mask_sha256: digest(8),
        receptor_vdw_radii_sha256: digest(9),
    }
}

fn exact_only_allocation() -> Fixed64Allocation {
    let inventory =
        Fixed64FeatureInventory::new(exact_source(), vec![], vec![], vec![], vec![]).unwrap();
    Fixed64Allocation::build(inventory).unwrap()
}

fn input(
    ligand_radii: Vec<f64>,
    heavy_mask: Vec<bool>,
    receptor_coordinates: Vec<Vec3>,
    receptor_radii: Vec<f64>,
    pocket_radius: f64,
) -> Fixed64GeometricInput {
    Fixed64GeometricInput::new(
        ligand_radii,
        heavy_mask,
        receptor_coordinates,
        receptor_radii,
        Vec3::new(0.0, 0.0, 0.0),
        pocket_radius,
    )
    .unwrap()
}

fn candidates_for_ready_slots(
    allocation: &Fixed64Allocation,
    coordinates: &[Vec3],
) -> [Option<Vec<Vec3>>; FIXED64_CANDIDATE_COUNT] {
    std::array::from_fn(|index| {
        allocation.slots()[index]
            .generation_eligible()
            .then(|| coordinates.to_vec())
    })
}

#[test]
fn batch_keeps_typed_generation_failures_and_full_pair_denominators() {
    let allocation = exact_only_allocation();
    let geometry = input(
        vec![1.0, 1.2],
        vec![true, false],
        vec![Vec3::new(0.0, 0.0, 0.0), Vec3::new(-1.0, 0.0, 0.0)],
        vec![1.0, 1.1],
        20.0,
    );
    let candidates = candidates_for_ready_slots(
        &allocation,
        &[Vec3::new(10.0, 0.0, 0.0), Vec3::new(12.0, 0.0, 0.0)],
    );

    let batch = Fixed64GeometricBatch::evaluate(&allocation, geometry, candidates).unwrap();

    assert_eq!(batch.decisions().len(), 64);
    assert_eq!(batch.accepted_count(), 12);
    assert_eq!(batch.geometric_rejected_count(), 0);
    assert_eq!(batch.typed_generation_failure_count(), 52);
    assert!(batch.has_valid_receipt());
    assert!(!batch.molecular_execution_authorized());
    assert!(!batch.production_claim_authorized());

    for decision in &batch.decisions()[..24] {
        assert_eq!(
            decision.status(),
            Fixed64GeometricStatus::TypedGenerationFailure
        );
        assert!(!decision.rank_eligible());
        assert!(decision.candidate_coordinate_sha256().is_none());
        assert!(decision.metrics().is_none());
        assert_eq!(decision.allocation_missing_features().len(), 1);
    }
    for decision in &batch.decisions()[24..36] {
        assert_eq!(decision.status(), Fixed64GeometricStatus::Accepted);
        assert!(decision.rank_eligible());
        let metrics = decision.metrics().unwrap();
        assert_eq!(metrics.ligand_atom_count(), 2);
        assert_eq!(metrics.receptor_atom_count(), 2);
        assert_eq!(metrics.exact_pair_count(), 4);
        assert_eq!(metrics.penetration_pair_count(), 0);
        assert_eq!(metrics.sphere_overlap_proxy_angstrom3(), 0.0);
        assert!(metrics.minimum_vdw_ratio() >= HARD_REJECTION_MINIMUM_VDW_RATIO);
        assert!(metrics.has_valid_receipt());
    }
    assert_eq!(
        batch.decisions()[0].allocation_missing_features(),
        &[Fixed64MissingFeature::V7ControlSource(0)]
    );
}

#[test]
fn severe_penetration_is_rank_ineligible_but_never_deleted() {
    let allocation = exact_only_allocation();
    let geometry = input(
        vec![1.0],
        vec![true],
        vec![Vec3::new(0.0, 0.0, 0.0)],
        vec![1.0],
        20.0,
    );
    let mut candidates = candidates_for_ready_slots(&allocation, &[Vec3::new(10.0, 0.0, 0.0)]);
    candidates[24] = Some(vec![Vec3::new(0.2, 0.0, 0.0)]);

    let batch = Fixed64GeometricBatch::evaluate(&allocation, geometry, candidates).unwrap();

    assert_eq!(batch.accepted_count(), 11);
    assert_eq!(batch.geometric_rejected_count(), 1);
    assert_eq!(batch.typed_generation_failure_count(), 52);
    assert_eq!(batch.decisions().len(), 64);
    let rejected = &batch.decisions()[24];
    assert_eq!(
        rejected.status(),
        Fixed64GeometricStatus::SeverePenetrationRejected
    );
    assert!(!rejected.rank_eligible());
    assert!(batch.candidate_coordinates_angstrom(24).is_some());
    let metrics = rejected.metrics().unwrap();
    assert!((metrics.raw_minimum_distance_angstrom() - 0.2).abs() < 1.0e-15);
    assert!((metrics.minimum_vdw_surface_gap_angstrom() + 1.8).abs() < 1.0e-15);
    assert!((metrics.minimum_vdw_ratio() - 0.1).abs() < 1.0e-15);
    assert_eq!(metrics.penetration_pair_count(), 1);
    assert_eq!(metrics.unique_ligand_penetration_atom_count(), 1);
    assert_eq!(metrics.unique_ligand_heavy_atom_penetration_count(), 1);
    assert!(metrics.sphere_overlap_proxy_angstrom3() > 0.0);
}

#[test]
fn overlap_and_pocket_escape_metrics_have_frozen_physical_meanings() {
    let geometry = input(
        vec![1.0, 1.0],
        vec![true, false],
        vec![Vec3::new(0.0, 0.0, 0.0)],
        vec![1.0],
        5.0,
    );
    let metrics = evaluate_fixed64_geometric_metrics(
        &[Vec3::new(0.0, 0.0, 0.0), Vec3::new(10.0, 0.0, 0.0)],
        &geometry,
    )
    .unwrap();

    assert_eq!(metrics.exact_pair_count(), 2);
    assert_eq!(metrics.raw_minimum_distance_angstrom(), 0.0);
    assert_eq!(metrics.minimum_vdw_surface_gap_angstrom(), -2.0);
    assert_eq!(metrics.minimum_vdw_ratio(), 0.0);
    assert_eq!(metrics.penetration_pair_count(), 1);
    assert_eq!(metrics.unique_ligand_penetration_atom_count(), 1);
    assert_eq!(metrics.unique_ligand_heavy_atom_penetration_count(), 1);
    assert!(
        (metrics.sphere_overlap_proxy_angstrom3() - (4.0 / 3.0) * core::f64::consts::PI).abs()
            < 1.0e-14
    );
    assert_eq!(metrics.pocket_escape_angstrom(), 6.0);
}

#[test]
fn receipts_are_repeat_stable_and_normalize_signed_zero() {
    let positive = [Vec3::new(0.0, 1.0, 2.0)];
    let negative = [Vec3::new(-0.0, 1.0, 2.0)];
    assert_eq!(
        native_fixed64_coordinate_sha256(&positive).unwrap(),
        native_fixed64_coordinate_sha256(&negative).unwrap()
    );

    let allocation = exact_only_allocation();
    let geometry = input(
        vec![1.0],
        vec![true],
        vec![Vec3::new(0.0, 0.0, 0.0)],
        vec![1.0],
        20.0,
    );
    let candidates = candidates_for_ready_slots(&allocation, &[Vec3::new(10.0, 0.0, 0.0)]);
    let first =
        Fixed64GeometricBatch::evaluate(&allocation, geometry.clone(), candidates.clone()).unwrap();
    let second = Fixed64GeometricBatch::evaluate(&allocation, geometry, candidates).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.receipt_sha256(), second.receipt_sha256());
    assert_eq!(first.exact_input_sha256(), second.exact_input_sha256());
}

#[test]
fn invalid_cross_wired_and_over_budget_inputs_fail_closed() {
    assert_eq!(
        Fixed64GeometricInput::new(
            vec![1.0],
            vec![],
            vec![Vec3::new(0.0, 0.0, 0.0)],
            vec![1.0],
            Vec3::new(0.0, 0.0, 0.0),
            10.0,
        )
        .unwrap_err()
        .code(),
        Fixed64GeometricErrorCode::InvalidInput
    );
    assert_eq!(
        Fixed64GeometricInput::new(
            vec![f64::NAN],
            vec![true],
            vec![Vec3::new(0.0, 0.0, 0.0)],
            vec![1.0],
            Vec3::new(0.0, 0.0, 0.0),
            10.0,
        )
        .unwrap_err()
        .code(),
        Fixed64GeometricErrorCode::InvalidInput
    );

    let allocation = exact_only_allocation();
    let geometry = input(
        vec![1.0],
        vec![true],
        vec![Vec3::new(0.0, 0.0, 0.0)],
        vec![1.0],
        10.0,
    );
    let mut fabricated = candidates_for_ready_slots(&allocation, &[Vec3::new(10.0, 0.0, 0.0)]);
    fabricated[0] = Some(vec![Vec3::new(10.0, 0.0, 0.0)]);
    assert_eq!(
        Fixed64GeometricBatch::evaluate(&allocation, geometry.clone(), fabricated)
            .unwrap_err()
            .code(),
        Fixed64GeometricErrorCode::AllocationCrossWired
    );
    let missing_ready: [Option<Vec<Vec3>>; FIXED64_CANDIDATE_COUNT] = std::array::from_fn(|_| None);
    assert_eq!(
        Fixed64GeometricBatch::evaluate(&allocation, geometry, missing_ready)
            .unwrap_err()
            .code(),
        Fixed64GeometricErrorCode::AllocationCrossWired
    );

    let large_geometry = input(
        vec![1.0; 512],
        vec![true; 512],
        vec![Vec3::new(50.0, 0.0, 0.0); 4_096],
        vec![1.0; 4_096],
        100.0,
    );
    let large_candidates =
        candidates_for_ready_slots(&allocation, &vec![Vec3::new(0.0, 0.0, 0.0); 512]);
    let fixture_pair_work = allocation.ready_count()
        * large_geometry.ligand_vdw_radii_angstrom().len()
        * large_geometry.receptor_coordinates_angstrom().len();
    assert!(
        fixture_pair_work > FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS,
        "fixture must exercise the frozen batch cap"
    );
    assert_eq!(
        Fixed64GeometricBatch::evaluate(&allocation, large_geometry, large_candidates)
            .unwrap_err()
            .code(),
        Fixed64GeometricErrorCode::PairBudgetExceeded
    );
}
