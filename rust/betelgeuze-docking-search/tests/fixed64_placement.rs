use betelgeuze_docking_search::{
    generate_native_fixed64_indexed_so3, generate_native_fixed64_single_anchor,
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, native_fixed64_single_anchor_kernel, Fixed64Allocation,
    Fixed64AnchorKind, Fixed64AtomicFeatureEvidence, Fixed64ConformerSourceEvidence,
    Fixed64ExactV11SourceEvidence, Fixed64FeatureGeometry, Fixed64FeatureGeometryInventory,
    Fixed64FeatureInventory, Fixed64FeatureKind, Fixed64GeometricInput, Fixed64Lane,
    Fixed64PlacementErrorCode, Fixed64PlacementSource, Fixed64SourceEvidence,
    NativeFixed64SingleAnchorKernelOutcome, Vec3, NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID,
};

const FEATURE_KINDS: [Fixed64FeatureKind; 12] = [
    Fixed64FeatureKind::LigandDonor,
    Fixed64FeatureKind::LigandAcceptor,
    Fixed64FeatureKind::ReceptorDonor,
    Fixed64FeatureKind::ReceptorAcceptor,
    Fixed64FeatureKind::LigandPositiveSite,
    Fixed64FeatureKind::LigandNegativeSite,
    Fixed64FeatureKind::ReceptorPositiveSite,
    Fixed64FeatureKind::ReceptorNegativeSite,
    Fixed64FeatureKind::LigandAromaticPlane,
    Fixed64FeatureKind::ReceptorAromaticPlane,
    Fixed64FeatureKind::LigandShapeAxis,
    Fixed64FeatureKind::PocketShapeAxis,
];

fn digest(marker: u8) -> [u8; 32] {
    [marker; 32]
}

fn ligand() -> Vec<Vec3> {
    let dominant = 1.0 / 2.0_f64.sqrt();
    let dominant_scale = (1.1_f64 / 2.0).sqrt();
    let secondary_scale = (1.0_f64 / 2.0).sqrt();
    vec![
        Vec3::new(0.0, 0.0, 0.0),
        Vec3::new(1.0, 0.0, 0.0),
        Vec3::new(2.0, 0.0, 0.0),
        Vec3::new(0.0, 1.0, 0.0),
        Vec3::new(0.0, -1.0, 0.5),
        Vec3::new(-1.0, -1.0, 0.0),
        Vec3::new(1.0, -1.0, 0.0),
        Vec3::new(0.0, 1.0, 0.0),
        Vec3::new(dominant_scale * dominant, dominant_scale * dominant, 0.0),
        Vec3::new(-dominant_scale * dominant, -dominant_scale * dominant, 0.0),
        Vec3::new(0.0, 0.0, secondary_scale),
        Vec3::new(0.0, 0.0, -secondary_scale),
    ]
}

fn receptor() -> Vec<Vec3> {
    let dominant = 1.0 / 2.0_f64.sqrt();
    let dominant_scale = (1.2_f64 / 2.0).sqrt();
    let secondary_scale = (1.0_f64 / 2.0).sqrt();
    vec![
        Vec3::new(0.0, 0.0, 0.0),
        Vec3::new(0.0, 0.0, 1.0),
        Vec3::new(0.2, 0.1, 0.0),
        Vec3::new(-0.2, 0.0, 0.0),
        Vec3::new(0.2, 0.0, 0.0),
        Vec3::new(-1.0, -1.0, 0.0),
        Vec3::new(1.0, -1.0, 0.0),
        Vec3::new(0.0, 1.0, 0.0),
        Vec3::new(dominant_scale * dominant, dominant_scale * dominant, 0.0),
        Vec3::new(-dominant_scale * dominant, -dominant_scale * dominant, 0.0),
        Vec3::new(0.0, 0.0, secondary_scale),
        Vec3::new(0.0, 0.0, -secondary_scale),
    ]
}

fn exact_evidence(ligand: &[Vec3]) -> Fixed64ExactV11SourceEvidence {
    let receptor = receptor();
    exact_evidence_for(
        ligand,
        &vec![1.2; ligand.len()],
        &vec![true; ligand.len()],
        &receptor,
        &vec![1.2; receptor.len()],
    )
}

fn exact_evidence_for(
    ligand: &[Vec3],
    ligand_radii: &[f64],
    heavy_mask: &[bool],
    receptor: &[Vec3],
    receptor_radii: &[f64],
) -> Fixed64ExactV11SourceEvidence {
    Fixed64ExactV11SourceEvidence {
        source_receipt_sha256: digest(1),
        proposal_sha256: digest(2),
        ligand_coordinate_sha256: native_fixed64_coordinate_sha256(ligand).unwrap(),
        receptor_coordinate_sha256: native_fixed64_coordinate_sha256(receptor).unwrap(),
        prepared_ligand_topology_sha256: digest(3),
        prepared_receptor_topology_sha256: digest(4),
        ligand_vdw_radii_sha256: native_fixed64_radii_sha256(ligand_radii).unwrap(),
        ligand_heavy_atom_mask_sha256: native_fixed64_heavy_atom_mask_sha256(heavy_mask).unwrap(),
        receptor_vdw_radii_sha256: native_fixed64_radii_sha256(receptor_radii).unwrap(),
    }
}

fn allocation(
    ligand: &[Vec3],
    conformers: Vec<Fixed64ConformerSourceEvidence>,
) -> Fixed64Allocation {
    let inventory =
        Fixed64FeatureInventory::new(exact_evidence(ligand), vec![], vec![], conformers, vec![])
            .unwrap();
    Fixed64Allocation::build(inventory).unwrap()
}

fn exact_source(ligand: &[Vec3]) -> Fixed64PlacementSource {
    Fixed64PlacementSource::new(exact_evidence(ligand).ligand_source(), ligand.to_vec()).unwrap()
}

fn feature_atom_indices(kind: Fixed64FeatureKind) -> Vec<usize> {
    match kind {
        Fixed64FeatureKind::LigandDonor => vec![0, 1],
        Fixed64FeatureKind::LigandAcceptor => vec![2],
        Fixed64FeatureKind::ReceptorDonor => vec![0, 1],
        Fixed64FeatureKind::ReceptorAcceptor => vec![2],
        Fixed64FeatureKind::LigandPositiveSite => vec![3],
        Fixed64FeatureKind::LigandNegativeSite => vec![4],
        Fixed64FeatureKind::ReceptorPositiveSite => vec![4],
        Fixed64FeatureKind::ReceptorNegativeSite => vec![3],
        Fixed64FeatureKind::LigandAromaticPlane | Fixed64FeatureKind::ReceptorAromaticPlane => {
            vec![5, 6, 7]
        }
        Fixed64FeatureKind::LigandShapeAxis | Fixed64FeatureKind::PocketShapeAxis => {
            vec![8, 9, 10, 11]
        }
    }
}

fn atomic_features() -> Vec<Fixed64AtomicFeatureEvidence> {
    FEATURE_KINDS
        .into_iter()
        .enumerate()
        .map(|(index, kind)| Fixed64AtomicFeatureEvidence {
            kind,
            receipt_sha256: digest(80 + u8::try_from(index).unwrap()),
        })
        .collect()
}

fn feature_inventory() -> Fixed64FeatureGeometryInventory {
    feature_inventory_with(feature_atom_indices)
}

fn feature_inventory_with(
    indices: impl Fn(Fixed64FeatureKind) -> Vec<usize>,
) -> Fixed64FeatureGeometryInventory {
    let features = FEATURE_KINDS
        .into_iter()
        .enumerate()
        .map(|(index, kind)| {
            Fixed64FeatureGeometry::new(
                kind,
                digest(80 + u8::try_from(index).unwrap()),
                indices(kind),
            )
            .unwrap()
        })
        .collect();
    Fixed64FeatureGeometryInventory::new(features).unwrap()
}

fn anchor_fixture(
    ligand: &[Vec3],
    ligand_radii: Vec<f64>,
    heavy_mask: Vec<bool>,
    receptor: Vec<Vec3>,
    receptor_radii: Vec<f64>,
    pocket_center: Vec3,
) -> (
    Fixed64Allocation,
    Fixed64PlacementSource,
    Fixed64GeometricInput,
) {
    let exact = exact_evidence_for(
        ligand,
        &ligand_radii,
        &heavy_mask,
        &receptor,
        &receptor_radii,
    );
    let allocation = Fixed64Allocation::build(
        Fixed64FeatureInventory::new(exact, atomic_features(), vec![], vec![], vec![]).unwrap(),
    )
    .unwrap();
    let source = Fixed64PlacementSource::new(exact.ligand_source(), ligand.to_vec()).unwrap();
    let geometry = Fixed64GeometricInput::new(
        ligand_radii,
        heavy_mask,
        receptor,
        receptor_radii,
        pocket_center,
        20.0,
    )
    .unwrap();
    (allocation, source, geometry)
}

#[test]
fn indexed_so3_is_source_bound_prefix_stable_and_centered_on_the_pocket() {
    let ligand = ligand();
    let allocation = allocation(&ligand, vec![]);
    let pocket_center = Vec3::new(4.0, -3.0, 8.0);
    let pocket_normal = Vec3::new(0.0, 0.0, 2.0);

    let first = generate_native_fixed64_indexed_so3(
        &allocation,
        24,
        exact_source(&ligand),
        pocket_center,
        pocket_normal,
    )
    .unwrap();
    let repeated = generate_native_fixed64_indexed_so3(
        &allocation,
        24,
        exact_source(&ligand),
        pocket_center,
        pocket_normal,
    )
    .unwrap();
    let next = generate_native_fixed64_indexed_so3(
        &allocation,
        25,
        exact_source(&ligand),
        pocket_center,
        pocket_normal,
    )
    .unwrap();

    assert_eq!(first, repeated);
    assert_eq!(first.receipt_sha256(), repeated.receipt_sha256());
    assert_eq!(first.accepted_sequence_index(), 0);
    assert_eq!(next.accepted_sequence_index(), 1);
    assert_eq!(first.raw_sequence_index(), 0);
    assert!(next.raw_sequence_index() > first.raw_sequence_index());
    assert_eq!(first.source_seed_sha256(), next.source_seed_sha256());
    assert_ne!(first.quaternion(), next.quaternion());
    assert_ne!(
        first.output_coordinate_sha256(),
        next.output_coordinate_sha256()
    );
    assert!(first.has_valid_receipt());
    assert!(!first.result_dependent_input_consumed());
    assert!(!first.molecular_execution_authorized());

    let inverse = 1.0 / first.output_coordinates_angstrom().len() as f64;
    let observed_center = first
        .output_coordinates_angstrom()
        .iter()
        .copied()
        .fold(Vec3::new(0.0, 0.0, 0.0), Vec3::plus)
        .scale(inverse);
    assert!(observed_center.minus(pocket_center).norm() < 2.0e-15);
    assert_eq!(first.pocket_normal(), Vec3::new(0.0, 0.0, 1.0));
}

#[test]
fn seed_and_output_change_when_the_exact_source_changes() {
    let baseline_ligand = ligand();
    let mut changed_ligand = baseline_ligand.clone();
    changed_ligand[2].z += 0.25;
    let baseline = generate_native_fixed64_indexed_so3(
        &allocation(&baseline_ligand, vec![]),
        24,
        exact_source(&baseline_ligand),
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();
    let changed = generate_native_fixed64_indexed_so3(
        &allocation(&changed_ligand, vec![]),
        24,
        exact_source(&changed_ligand),
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();

    assert_ne!(baseline.source_seed_sha256(), changed.source_seed_sha256());
    assert_ne!(
        baseline.output_coordinate_sha256(),
        changed.output_coordinate_sha256()
    );
}

#[test]
fn indexed_so3_profile_versions_proposal_bound_seed_semantics() {
    assert_eq!(
        NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID,
        "betelgeuze.engine_v2_mixed64_indexed_source_bound_so3_native/1.1.0"
    );
    let ligand = ligand();
    let baseline_exact = exact_evidence(&ligand);
    let changed_exact = Fixed64ExactV11SourceEvidence {
        proposal_sha256: digest(42),
        ..baseline_exact
    };
    let baseline_allocation = Fixed64Allocation::build(
        Fixed64FeatureInventory::new(baseline_exact, vec![], vec![], vec![], vec![]).unwrap(),
    )
    .unwrap();
    let changed_allocation = Fixed64Allocation::build(
        Fixed64FeatureInventory::new(changed_exact, vec![], vec![], vec![], vec![]).unwrap(),
    )
    .unwrap();
    let baseline = generate_native_fixed64_indexed_so3(
        &baseline_allocation,
        24,
        Fixed64PlacementSource::new(baseline_exact.ligand_source(), ligand.clone()).unwrap(),
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();
    let changed = generate_native_fixed64_indexed_so3(
        &changed_allocation,
        24,
        Fixed64PlacementSource::new(changed_exact.ligand_source(), ligand).unwrap(),
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();
    assert_ne!(baseline.source_seed_sha256(), changed.source_seed_sha256());
    assert_ne!(
        baseline.output_coordinate_sha256(),
        changed.output_coordinate_sha256()
    );
}

#[test]
fn true_conformer_slots_require_their_exact_allocation_parent() {
    let ligand = ligand();
    let conformer_evidence = Fixed64SourceEvidence {
        receipt_sha256: digest(20),
        proposal_sha256: digest(21),
        coordinate_sha256: native_fixed64_coordinate_sha256(&ligand).unwrap(),
    };
    let allocation = allocation(
        &ligand,
        vec![Fixed64ConformerSourceEvidence {
            rank: 2,
            source: conformer_evidence,
        }],
    );
    let conformer = Fixed64PlacementSource::new(conformer_evidence, ligand.clone()).unwrap();

    let slot36 = generate_native_fixed64_indexed_so3(
        &allocation,
        36,
        conformer.clone(),
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();
    let slot43 = generate_native_fixed64_indexed_so3(
        &allocation,
        43,
        conformer,
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();
    assert_eq!(slot36.accepted_sequence_index(), 0);
    assert_eq!(slot43.accepted_sequence_index(), 7);
    assert_eq!(slot36.source_seed_sha256(), slot43.source_seed_sha256());

    let error = generate_native_fixed64_indexed_so3(
        &allocation,
        36,
        exact_source(&ligand),
        Vec3::new(0.0, 0.0, 5.0),
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap_err();
    assert_eq!(
        error.code(),
        Fixed64PlacementErrorCode::SourceIdentityMismatch
    );
    assert_eq!(
        generate_native_fixed64_indexed_so3(
            &allocation,
            37,
            exact_source(&ligand),
            Vec3::new(0.0, 0.0, 5.0),
            Vec3::new(0.0, 0.0, 1.0),
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::AllocationSlotNotEligible
    );
}

#[test]
fn unsupported_cross_wired_and_degenerate_inputs_fail_closed() {
    let ligand = ligand();
    let fixed_allocation = allocation(&ligand, vec![]);
    assert_eq!(
        generate_native_fixed64_indexed_so3(
            &fixed_allocation,
            0,
            exact_source(&ligand),
            Vec3::new(0.0, 0.0, 5.0),
            Vec3::new(0.0, 0.0, 1.0),
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::UnsupportedLane
    );

    let exact = exact_evidence(&ligand);
    let wrong_source = Fixed64PlacementSource::new(
        Fixed64SourceEvidence {
            proposal_sha256: digest(99),
            ..exact.ligand_source()
        },
        ligand.clone(),
    )
    .unwrap();
    assert_eq!(
        generate_native_fixed64_indexed_so3(
            &fixed_allocation,
            24,
            wrong_source,
            Vec3::new(0.0, 0.0, 5.0),
            Vec3::new(0.0, 0.0, 1.0),
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::SourceIdentityMismatch
    );
    assert_eq!(
        generate_native_fixed64_indexed_so3(
            &fixed_allocation,
            24,
            exact_source(&ligand),
            Vec3::new(0.0, 0.0, 5.0),
            Vec3::new(0.0, 0.0, 0.0),
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal
    );

    let degenerate = vec![Vec3::new(1.0, 1.0, 1.0); 3];
    let degenerate_allocation = allocation(&degenerate, vec![]);
    assert_eq!(
        generate_native_fixed64_indexed_so3(
            &degenerate_allocation,
            24,
            exact_source(&degenerate),
            Vec3::new(0.0, 0.0, 5.0),
            Vec3::new(0.0, 0.0, 1.0),
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::DegenerateSo3SourceGeometry
    );
}

fn standard_anchor_fixture() -> (
    Vec<Vec3>,
    Vec<Vec3>,
    Fixed64Allocation,
    Fixed64PlacementSource,
    Fixed64GeometricInput,
) {
    let ligand = ligand();
    let receptor = receptor();
    let (allocation, source, geometry) = anchor_fixture(
        &ligand,
        vec![1.2; ligand.len()],
        vec![true; ligand.len()],
        receptor.clone(),
        vec![1.2; receptor.len()],
        Vec3::new(0.0, 0.0, 10.0),
    );
    (ligand, receptor, allocation, source, geometry)
}

#[test]
fn public_single_anchor_kernel_rejects_cross_wiring_and_short_features() {
    let source = [
        Vec3::new(0.0, 0.0, 0.0),
        Vec3::new(1.0, 0.0, 0.0),
        Vec3::new(0.0, 1.0, 0.0),
    ];
    let ligand_donor = [source[0], source[1]];
    let receptor_acceptor = [Vec3::new(0.0, 0.0, 4.0)];
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::LigandDonorToReceptorAcceptor,
            Fixed64AnchorKind::AromaticPlane,
            0,
            &source,
            &ligand_donor,
            &receptor_acceptor,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::FeatureCrossWired
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::LigandDonorToReceptorAcceptor,
            Fixed64AnchorKind::LigandDonorToReceptorAcceptor,
            0,
            &source,
            &ligand_donor[..1],
            &receptor_acceptor,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::LigandAcceptorToReceptorDonor,
            Fixed64AnchorKind::LigandAcceptorToReceptorDonor,
            0,
            &source,
            &ligand_donor[..1],
            &receptor_acceptor,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::LigandDonorToReceptorAcceptor,
            Fixed64AnchorKind::LigandDonorToReceptorAcceptor,
            0,
            &[],
            &ligand_donor,
            &receptor_acceptor,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::ComplementaryCharge,
            Fixed64AnchorKind::ComplementaryCharge,
            0,
            &source,
            &[],
            &receptor_acceptor,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::AromaticPlane,
            Fixed64AnchorKind::AromaticPlane,
            0,
            &source,
            &ligand_donor,
            &source,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::PrincipalAxisShape,
            Fixed64AnchorKind::PrincipalAxisShape,
            0,
            &source,
            &ligand_donor,
            &[],
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput
        )
    );
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::PocketCenteredControls,
            Fixed64AnchorKind::LigandDonorToReceptorAcceptor,
            0,
            &source,
            &ligand_donor,
            &receptor_acceptor,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::UnsupportedLane
        )
    );
}

#[test]
fn aromatic_degeneracy_scan_is_linear_at_feature_limit_scale() {
    let source = [
        Vec3::new(0.0, 0.0, 0.0),
        Vec3::new(1.0, 0.0, 0.0),
        Vec3::new(0.0, 1.0, 0.0),
    ];
    let collinear = (0_u32..4_096)
        .map(|index| Vec3::new(f64::from(index), 0.0, 0.0))
        .collect::<Vec<_>>();
    let receptor_plane = [
        Vec3::new(0.0, 0.0, 4.0),
        Vec3::new(1.0, 0.0, 4.0),
        Vec3::new(0.0, 1.0, 4.0),
    ];
    assert_eq!(
        native_fixed64_single_anchor_kernel(
            Fixed64Lane::AromaticPlane,
            Fixed64AnchorKind::AromaticPlane,
            0,
            &source,
            &collinear,
            &receptor_plane,
            Vec3::new(0.0, 0.0, 0.0),
        ),
        NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::DegenerateAromaticPlane
        )
    );
}

#[test]
fn every_single_anchor_lane_hits_its_frozen_distance_and_full_precheck() {
    let (ligand, receptor, allocation, source, geometry) = standard_anchor_fixture();
    let features = feature_inventory();
    for (slot_index, target_distance) in [(44, 2.9), (48, 2.9), (52, 3.5), (56, 3.8), (58, 3.0)] {
        let placement = generate_native_fixed64_single_anchor(
            &allocation,
            slot_index,
            source.clone(),
            &features,
            &geometry,
        )
        .unwrap();
        assert_eq!(placement.target_distance_angstrom(), target_distance);
        assert!(
            (placement
                .target_anchor_point_angstrom()
                .minus(placement.receptor_anchor_point_angstrom())
                .norm()
                - target_distance)
                .abs()
                < 2.0e-14
        );
        assert!((placement.local_surface_normal().norm() - 1.0).abs() < 2.0e-15);
        assert!(
            placement
                .approach_vector()
                .plus(placement.local_surface_normal())
                .norm()
                < 2.0e-15
        );
        assert_eq!(
            placement.geometric_metrics().exact_pair_count(),
            ligand.len() * receptor.len()
        );
        assert_eq!(
            placement.geometric_metrics().ligand_atom_count(),
            ligand.len()
        );
        assert_eq!(
            placement.geometric_metrics().receptor_atom_count(),
            receptor.len()
        );
        assert!(placement.has_valid_receipt());
        assert!(!placement.fallback_allowed());
        assert!(!placement.multi_anchor_consumed());
        assert!(!placement.result_dependent_input_consumed());
        assert!(!placement.molecular_execution_authorized());
    }

    let donor = generate_native_fixed64_single_anchor(
        &allocation,
        44,
        source.clone(),
        &features,
        &geometry,
    )
    .unwrap();
    let transformed_direction =
        donor.output_coordinates_angstrom()[1].minus(donor.output_coordinates_angstrom()[0]);
    let transformed_direction = transformed_direction.scale(1.0 / transformed_direction.norm());
    assert!(transformed_direction.minus(donor.approach_vector()).norm() < 2.0e-15);
    assert!(
        (donor.output_coordinates_angstrom()[0]
            .minus(donor.receptor_anchor_point_angstrom())
            .norm()
            - 2.9)
            .abs()
            < 2.0e-14
    );

    let shape =
        generate_native_fixed64_single_anchor(&allocation, 58, source, &features, &geometry)
            .unwrap();
    let expected_axis = Vec3::new(1.0, 1.0, 0.0).scale(1.0 / 2.0_f64.sqrt());
    assert!((shape.ligand_direction().dot(expected_axis).abs() - 1.0).abs() < 2.0e-14);
}

#[test]
fn anchor_lane_twists_are_predeclared_and_index_stable() {
    let (_, _, allocation, source, geometry) = standard_anchor_fixture();
    let features = feature_inventory();
    for (start, width) in [(44, 4_usize), (48, 4), (52, 4), (56, 2), (58, 2)] {
        let placements = (0..width)
            .map(|offset| {
                generate_native_fixed64_single_anchor(
                    &allocation,
                    start + offset,
                    source.clone(),
                    &features,
                    &geometry,
                )
                .unwrap()
            })
            .collect::<Vec<_>>();
        for (offset, placement) in placements.iter().enumerate() {
            let expected = 2.0 * core::f64::consts::PI * offset as f64 / width as f64;
            assert!((placement.twist_angle_radians() - expected).abs() < 2.0e-15);
            assert_eq!(placement.lane_offset(), offset);
        }
        assert_eq!(
            placements
                .iter()
                .map(|placement| placement.output_coordinate_sha256())
                .collect::<std::collections::BTreeSet<_>>()
                .len(),
            width
        );
    }
}

#[test]
fn severe_penetration_is_preserved_as_single_anchor_precheck_evidence() {
    let ligand = ligand();
    let receptor = receptor();
    let (allocation, source, geometry) = anchor_fixture(
        &ligand,
        vec![10.0; ligand.len()],
        vec![true; ligand.len()],
        receptor.clone(),
        vec![10.0; receptor.len()],
        Vec3::new(0.0, 0.0, 10.0),
    );
    let placement = generate_native_fixed64_single_anchor(
        &allocation,
        44,
        source,
        &feature_inventory(),
        &geometry,
    )
    .unwrap();

    assert!(!placement.steric_precheck_passed());
    assert!(!placement.output_coordinates_angstrom().is_empty());
    assert!(placement.geometric_metrics().penetration_pair_count() > 0);
    assert!(
        placement
            .geometric_metrics()
            .sphere_overlap_proxy_angstrom3()
            > 0.0
    );
    assert!(placement.has_valid_receipt());
}

#[test]
fn anchor_degeneracy_and_feature_cross_wiring_fail_with_typed_codes() {
    let (_, _, allocation, source, geometry) = standard_anchor_fixture();
    let mut donor_degenerate = ligand();
    donor_degenerate[1] = donor_degenerate[0];
    let receptor = receptor();
    let (donor_allocation, donor_source, donor_geometry) = anchor_fixture(
        &donor_degenerate,
        vec![1.2; donor_degenerate.len()],
        vec![true; donor_degenerate.len()],
        receptor.clone(),
        vec![1.2; receptor.len()],
        Vec3::new(0.0, 0.0, 10.0),
    );
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &donor_allocation,
            44,
            donor_source,
            &feature_inventory(),
            &donor_geometry,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::DegenerateLigandDirection
    );

    let mut aromatic_degenerate = ligand();
    aromatic_degenerate[5] = Vec3::new(0.0, 0.0, 0.0);
    aromatic_degenerate[6] = Vec3::new(1.0, 0.0, 0.0);
    aromatic_degenerate[7] = Vec3::new(2.0, 0.0, 0.0);
    let (aromatic_allocation, aromatic_source, aromatic_geometry) = anchor_fixture(
        &aromatic_degenerate,
        vec![1.2; aromatic_degenerate.len()],
        vec![true; aromatic_degenerate.len()],
        receptor.clone(),
        vec![1.2; receptor.len()],
        Vec3::new(0.0, 0.0, 10.0),
    );
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &aromatic_allocation,
            56,
            aromatic_source,
            &feature_inventory(),
            &aromatic_geometry,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::DegenerateAromaticPlane
    );

    let degenerate_shape_features = feature_inventory_with(|kind| {
        if kind == Fixed64FeatureKind::LigandShapeAxis {
            vec![9]
        } else {
            feature_atom_indices(kind)
        }
    });
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &allocation,
            58,
            source.clone(),
            &degenerate_shape_features,
            &geometry,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::DegeneratePrincipalAxis
    );

    let out_of_range = feature_inventory_with(|kind| {
        if kind == Fixed64FeatureKind::ReceptorAcceptor {
            vec![999]
        } else {
            feature_atom_indices(kind)
        }
    });
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &allocation,
            44,
            source.clone(),
            &out_of_range,
            &geometry,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::FeatureAtomIndexOutOfRange
    );

    let missing_receptor_acceptor = Fixed64FeatureGeometryInventory::new(
        FEATURE_KINDS
            .into_iter()
            .enumerate()
            .filter(|(_, kind)| *kind != Fixed64FeatureKind::ReceptorAcceptor)
            .map(|(index, kind)| {
                Fixed64FeatureGeometry::new(
                    kind,
                    digest(80 + u8::try_from(index).unwrap()),
                    feature_atom_indices(kind),
                )
                .unwrap()
            })
            .collect(),
    )
    .unwrap();
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &allocation,
            44,
            source,
            &missing_receptor_acceptor,
            &geometry,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::FeatureCrossWired
    );
}

#[test]
fn aromatic_tangent_and_exact_receptor_cross_wiring_fail_closed() {
    let ligand = ligand();
    let receptor = receptor();
    let (tangent_allocation, tangent_source, tangent_geometry) = anchor_fixture(
        &ligand,
        vec![1.2; ligand.len()],
        vec![true; ligand.len()],
        receptor.clone(),
        vec![1.2; receptor.len()],
        Vec3::new(10.0, 0.0, 0.0),
    );
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &tangent_allocation,
            56,
            tangent_source,
            &feature_inventory(),
            &tangent_geometry,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal
    );

    let (_, _, allocation, source, geometry) = standard_anchor_fixture();
    let mut changed_receptor = geometry.receptor_coordinates_angstrom().to_vec();
    changed_receptor[0].x += 0.01;
    let cross_wired = Fixed64GeometricInput::new(
        geometry.ligand_vdw_radii_angstrom().to_vec(),
        geometry.ligand_heavy_atom_mask().to_vec(),
        changed_receptor,
        geometry.receptor_vdw_radii_angstrom().to_vec(),
        geometry.pocket_center_angstrom(),
        geometry.pocket_radius_angstrom(),
    )
    .unwrap();
    assert_eq!(
        generate_native_fixed64_single_anchor(
            &allocation,
            44,
            source,
            &feature_inventory(),
            &cross_wired,
        )
        .unwrap_err()
        .code(),
        Fixed64PlacementErrorCode::SourceIdentityMismatch
    );
}
