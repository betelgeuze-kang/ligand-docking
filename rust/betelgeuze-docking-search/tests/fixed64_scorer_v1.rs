use betelgeuze_docking_search::{
    evaluate_native_fixed64_pose_validity, native_fixed64_coordinate_sha256,
    native_fixed64_heavy_atom_mask_sha256, native_fixed64_radii_sha256,
    produce_native_fixed64_proposals, rank_native_fixed64_top_k, score_native_fixed64_scorer_v1,
    Fixed64Allocation, Fixed64CoordinateSourceKind, Fixed64CoordinateSourcePayload,
    Fixed64ExactV11SourceEvidence, Fixed64FeatureGeometryInventory, Fixed64FeatureInventory,
    Fixed64GeometricBatch, Fixed64GeometricInput, Fixed64ProposalFailureCode,
    Fixed64ProposalSourceBundle, NativeFixed64ValidityBackend, NativeFixed64ValidityConfig,
    NativeFixed64ValidityContext, NativeFixed64ValidityErrorCode, NativeFixed64ValidityFailureCode,
    NativeFixed64ValidityRowStatus, NativeScorerV1Atom, NativeScorerV1Backend,
    NativeScorerV1Config, NativeScorerV1Context, NativeScorerV1Donor, NativeScorerV1ErrorCode,
    NativeScorerV1FailureCode, NativeScorerV1KernelOutcome, NativeScorerV1RowStatus, Vec3,
};

fn digest(marker: u8) -> [u8; 32] {
    [marker; 32]
}

fn ligand() -> Vec<Vec3> {
    vec![
        Vec3::new(0.0, 1.0, 0.0),
        Vec3::new(0.0, 0.0, 0.0),
        Vec3::new(1.0, 0.0, 0.0),
        Vec3::new(1.0, 1.0, 1.0),
    ]
}

fn receptor() -> Vec<Vec3> {
    vec![Vec3::new(5.0, 0.0, 0.0), Vec3::new(6.0, 0.0, 0.0)]
}

fn exact_evidence() -> Fixed64ExactV11SourceEvidence {
    let ligand = ligand();
    let receptor = receptor();
    Fixed64ExactV11SourceEvidence {
        source_receipt_sha256: digest(1),
        proposal_sha256: digest(2),
        ligand_coordinate_sha256: native_fixed64_coordinate_sha256(&ligand).unwrap(),
        receptor_coordinate_sha256: native_fixed64_coordinate_sha256(&receptor).unwrap(),
        prepared_ligand_topology_sha256: digest(3),
        prepared_receptor_topology_sha256: digest(4),
        ligand_vdw_radii_sha256: native_fixed64_radii_sha256(&[1.0; 4]).unwrap(),
        ligand_heavy_atom_mask_sha256: native_fixed64_heavy_atom_mask_sha256(&[true; 4]).unwrap(),
        receptor_vdw_radii_sha256: native_fixed64_radii_sha256(&[1.0; 2]).unwrap(),
    }
}

fn admission() -> Fixed64GeometricBatch {
    let ligand = ligand();
    let exact = exact_evidence();
    let allocation = Fixed64Allocation::build(
        Fixed64FeatureInventory::new(exact, vec![], vec![], vec![], vec![]).unwrap(),
    )
    .unwrap();
    let exact_source = Fixed64CoordinateSourcePayload::new(
        Fixed64CoordinateSourceKind::ExactV11Base,
        None,
        exact.ligand_source(),
        ligand,
    )
    .unwrap();
    let geometric_input = Fixed64GeometricInput::new(
        vec![1.0; 4],
        vec![true; 4],
        receptor(),
        vec![1.0; 2],
        Vec3::new(0.0, 0.0, 0.0),
        20.0,
    )
    .unwrap();
    let source_bundle = Fixed64ProposalSourceBundle::new(
        &allocation,
        Some(exact_source),
        vec![],
        vec![],
        vec![],
        Fixed64FeatureGeometryInventory::new(vec![]).unwrap(),
        geometric_input,
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap();
    let proposals = produce_native_fixed64_proposals(&allocation, source_bundle).unwrap();
    assert_eq!(proposals.generated_count(), 12);
    let admission = Fixed64GeometricBatch::evaluate_proposals(proposals).unwrap();
    assert_eq!(admission.accepted_count(), 12);
    admission
}

fn scorer_atoms() -> (Vec<NativeScorerV1Atom>, Vec<NativeScorerV1Atom>) {
    let receptor_atoms = vec![
        NativeScorerV1Atom {
            charge_elementary: -0.25,
            vdw_radius_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.2,
            hydrophobic: true,
            acceptor: true,
        },
        NativeScorerV1Atom {
            charge_elementary: 0.15,
            vdw_radius_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.17,
            hydrophobic: false,
            acceptor: false,
        },
    ];
    let ligand_atoms = vec![
        NativeScorerV1Atom {
            charge_elementary: 0.2,
            vdw_radius_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.17,
            hydrophobic: false,
            acceptor: false,
        },
        NativeScorerV1Atom {
            charge_elementary: 0.1,
            vdw_radius_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.02,
            hydrophobic: false,
            acceptor: false,
        },
        NativeScorerV1Atom {
            charge_elementary: -0.1,
            vdw_radius_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.12,
            hydrophobic: true,
            acceptor: false,
        },
        NativeScorerV1Atom {
            charge_elementary: -0.2,
            vdw_radius_angstrom: 1.0,
            epsilon_kcal_per_mol: 0.2,
            hydrophobic: false,
            acceptor: true,
        },
    ];
    (receptor_atoms, ligand_atoms)
}

fn context(authority_receipt: [u8; 32], config: NativeScorerV1Config) -> NativeScorerV1Context {
    context_with_backend(authority_receipt, config, NativeScorerV1Backend::RustCpu)
}

fn context_with_backend(
    authority_receipt: [u8; 32],
    config: NativeScorerV1Config,
    backend: NativeScorerV1Backend,
) -> NativeScorerV1Context {
    let (receptor_atoms, ligand_atoms) = scorer_atoms();
    NativeScorerV1Context::new(
        authority_receipt,
        digest(10),
        digest(11),
        backend,
        digest(12),
        receptor(),
        receptor_atoms,
        ligand(),
        ligand_atoms,
        vec![],
        vec![NativeScorerV1Donor {
            donor_atom_index: 0,
            hydrogen_atom_index: 1,
        }],
        vec![[0, 1], [1, 2], [2, 3]],
        vec![[0, 1, 2, 3]],
        Vec3::new(0.0, 0.0, 0.0),
        20.0,
        config,
    )
    .unwrap()
}

#[test]
fn native_scorer_preserves_64_rows_and_complete_repeat_stable_terms() {
    let admission = admission();
    let context = context(digest(1), NativeScorerV1Config::default());
    assert!(context.has_valid_receipt());
    assert!(context.backend().product_eligible());

    let first = score_native_fixed64_scorer_v1(admission.clone(), context.clone()).unwrap();
    let second = score_native_fixed64_scorer_v1(admission, context).unwrap();

    assert_eq!(first, second);
    assert_eq!(first.rows().len(), 64);
    assert_eq!(first.scored_count(), 12);
    assert_eq!(first.typed_failure_count(), 52);
    assert_eq!(first.receipt_sha256(), second.receipt_sha256());
    assert!(first.has_valid_receipt());
    assert!(!first.molecular_execution_authorized());
    assert!(!first.production_claim_authorized());

    for row in &first.rows()[24..36] {
        assert_eq!(row.status(), NativeScorerV1RowStatus::Scored);
        let terms = row.terms().unwrap();
        assert!(terms.has_valid_receipt());
        assert_eq!(terms.backend(), NativeScorerV1Backend::RustCpu);
        assert_eq!(terms.weighted_terms().len(), 8);
        assert!(terms.total_score().is_finite());
        assert_eq!(terms.ligand_pair_count(), 3);
        assert_eq!(terms.receptor_candidate_pair_count(), 8);
        assert_eq!(
            terms.coordinate_sha256(),
            first.admission().decisions()[row.slot_index()]
                .candidate_coordinate_sha256()
                .unwrap()
        );
    }
    for row in first.rows()[..24].iter().chain(&first.rows()[36..]) {
        assert_eq!(row.status(), NativeScorerV1RowStatus::TypedFailure);
        assert_eq!(
            row.failure().unwrap().failure_code(),
            NativeScorerV1FailureCode::ProposalGenerationFailure
        );
        assert_eq!(
            row.failure().unwrap().upstream_proposal_failure_code(),
            Some(Fixed64ProposalFailureCode::AllocationMissingFeature)
        );
    }
}

#[test]
fn reusable_rust_kernel_reports_terms_and_candidate_local_rotor_failure() {
    let context = context(digest(1), NativeScorerV1Config::default());
    let scored = context.score_coordinates(&ligand()).unwrap();
    let NativeScorerV1KernelOutcome::Scored(terms) = scored else {
        panic!("reference ligand must score")
    };
    assert_eq!(terms.weighted_terms().len(), 8);
    assert!(terms.total_score().is_finite());
    assert_eq!(terms.ligand_pair_count(), 3);

    let mut collapsed = ligand();
    collapsed[0] = collapsed[1];
    let failed = context.score_coordinates(&collapsed).unwrap();
    let NativeScorerV1KernelOutcome::TypedFailure(failure) = failed else {
        panic!("collapsed rotor must fail locally")
    };
    assert_eq!(
        failure.failure_code(),
        NativeScorerV1FailureCode::DegenerateRotorGeometry
    );
    assert_eq!(failure.ligand_pair_count(), 3);
}

#[test]
fn receptor_pair_capacity_is_typed_per_candidate_without_batch_loss() {
    let default = NativeScorerV1Config::default();
    let limited = NativeScorerV1Config::new(
        default.weights(),
        default.electrostatic_dielectric(),
        default.pair_cutoff_angstrom(),
        default.hbond_distance_max_angstrom(),
        default.polar_burial_distance_angstrom(),
        1,
        default.max_ligand_pair_checks(),
    )
    .unwrap();
    let batch = score_native_fixed64_scorer_v1(admission(), context(digest(1), limited)).unwrap();

    assert_eq!(batch.rows().len(), 64);
    assert_eq!(batch.scored_count(), 0);
    assert_eq!(batch.typed_failure_count(), 64);
    for row in &batch.rows()[24..36] {
        let failure = row.failure().unwrap();
        assert_eq!(
            failure.failure_code(),
            NativeScorerV1FailureCode::ReceptorCandidatePairCapacityExceeded
        );
        assert_eq!(failure.receptor_candidate_pair_count(), 2);
        assert_eq!(failure.ligand_pair_count(), 0);
    }
    assert!(batch.has_valid_receipt());
}

#[test]
fn exact_authority_cross_wiring_fails_before_scoring() {
    let error = score_native_fixed64_scorer_v1(
        admission(),
        context(digest(99), NativeScorerV1Config::default()),
    )
    .unwrap_err();
    assert_eq!(error.code(), NativeScorerV1ErrorCode::UpstreamCrossWired);
}

#[test]
fn rust_entry_point_rejects_hip_backend_mislabeling() {
    let error = score_native_fixed64_scorer_v1(
        admission(),
        context_with_backend(
            digest(1),
            NativeScorerV1Config::default(),
            NativeScorerV1Backend::HipSafe,
        ),
    )
    .unwrap_err();
    assert_eq!(error.code(), NativeScorerV1ErrorCode::UpstreamCrossWired);
}

#[test]
fn invalid_context_rows_and_config_fail_closed() {
    let error = NativeScorerV1Config::new([1.0; 8], 4.0, 3.0, 3.1, 4.5, 1, 1).unwrap_err();
    assert_eq!(error.code(), NativeScorerV1ErrorCode::InvalidConfig);

    let (receptor_atoms, ligand_atoms) = scorer_atoms();
    let error = NativeScorerV1Context::new(
        digest(1),
        digest(10),
        digest(11),
        NativeScorerV1Backend::RustCpu,
        digest(12),
        receptor(),
        receptor_atoms,
        ligand(),
        ligand_atoms,
        vec![],
        vec![
            NativeScorerV1Donor {
                donor_atom_index: 0,
                hydrogen_atom_index: 1,
            },
            NativeScorerV1Donor {
                donor_atom_index: 2,
                hydrogen_atom_index: 1,
            },
        ],
        vec![],
        vec![],
        Vec3::new(0.0, 0.0, 0.0),
        20.0,
        NativeScorerV1Config::default(),
    )
    .unwrap_err();
    assert_eq!(error.code(), NativeScorerV1ErrorCode::InvalidContext);
}

fn validity_context(
    scorer: &NativeScorerV1Context,
    backend: NativeFixed64ValidityBackend,
    config: NativeFixed64ValidityConfig,
) -> NativeFixed64ValidityContext {
    NativeFixed64ValidityContext::from_scorer_context(
        scorer,
        backend,
        digest(13),
        digest(14),
        vec![[0, 1], [1, 2], [2, 3]],
        vec![[0, 1, 2, 3]],
        config,
    )
    .unwrap()
}

#[test]
fn native_validity_preserves_64_rows_and_complete_element_aware_evidence() {
    let scorer_context = context(digest(1), NativeScorerV1Config::default());
    let scorer_batch = score_native_fixed64_scorer_v1(admission(), scorer_context.clone()).unwrap();
    let validity_context = validity_context(
        &scorer_context,
        NativeFixed64ValidityBackend::RustCpu,
        NativeFixed64ValidityConfig::default(),
    );
    assert!(validity_context.has_valid_receipt());
    assert!(validity_context.backend().product_eligible());

    let first =
        evaluate_native_fixed64_pose_validity(scorer_batch.clone(), validity_context.clone())
            .unwrap();
    let second = evaluate_native_fixed64_pose_validity(scorer_batch, validity_context).unwrap();

    assert_eq!(first, second);
    assert_eq!(first.rows().len(), 64);
    assert_eq!(first.evaluated_count(), 12);
    assert_eq!(first.valid_count(), 12);
    assert!(first.has_valid_receipt());
    assert!(!first.molecular_execution_authorized());
    assert!(!first.production_claim_authorized());
    for row in &first.rows()[24..36] {
        assert_eq!(row.status(), NativeFixed64ValidityRowStatus::Evaluated);
        let result = row.result().unwrap();
        assert!(result.complete());
        assert!(result.valid());
        assert!(result.checks().all());
        assert!(result.blockers().is_empty());
        assert!(
            result
                .measurements()
                .element_vdw_receptor_candidate_pair_count()
                <= 8
        );
        assert_eq!(
            result
                .measurements()
                .element_vdw_receptor_severe_overlap_count(),
            0
        );
        assert!(result.has_valid_receipt());
    }
    for row in first.rows()[..24].iter().chain(&first.rows()[36..]) {
        assert_eq!(
            row.status(),
            NativeFixed64ValidityRowStatus::UpstreamScorerFailure
        );
        let failure = row.failure().unwrap();
        assert_eq!(
            failure.failure_code(),
            NativeFixed64ValidityFailureCode::UpstreamScorerFailure
        );
        assert_eq!(
            failure.upstream_scorer_failure_code(),
            Some(NativeScorerV1FailureCode::ProposalGenerationFailure)
        );
        assert!(failure.has_valid_receipt());
    }
}

#[test]
fn native_validity_capacity_is_candidate_local_and_hip_mislabel_fails_closed() {
    let scorer_context = context(digest(1), NativeScorerV1Config::default());
    let scorer_batch = score_native_fixed64_scorer_v1(admission(), scorer_context.clone()).unwrap();
    let default = NativeFixed64ValidityConfig::default();
    let limited = NativeFixed64ValidityConfig::new(
        0.15, 0.75, 0.8, 1.0e-6, 1.0e-8, 0.55, 3.5, 250_000, 1, 250_000, 1_000_000,
    )
    .unwrap();
    assert_ne!(limited.receipt_sha256(), default.receipt_sha256());
    let batch = evaluate_native_fixed64_pose_validity(
        scorer_batch.clone(),
        validity_context(
            &scorer_context,
            NativeFixed64ValidityBackend::RustCpu,
            limited,
        ),
    )
    .unwrap();
    assert_eq!(batch.evaluated_count(), 0);
    for row in &batch.rows()[24..36] {
        assert_eq!(row.status(), NativeFixed64ValidityRowStatus::TypedFailure);
        let failure = row.failure().unwrap();
        assert_eq!(
            failure.failure_code(),
            NativeFixed64ValidityFailureCode::ReceptorCrossCapacityExceeded
        );
        assert_eq!(failure.observed_count(), 8);
    }
    assert!(batch.has_valid_receipt());

    let error = evaluate_native_fixed64_pose_validity(
        scorer_batch,
        validity_context(
            &scorer_context,
            NativeFixed64ValidityBackend::HipSafe,
            default,
        ),
    )
    .unwrap_err();
    assert_eq!(
        error.code(),
        NativeFixed64ValidityErrorCode::UpstreamCrossWired
    );
}

#[test]
fn native_validity_rejects_scorer_context_cross_wiring() {
    let scorer_context = context(digest(1), NativeScorerV1Config::default());
    let scorer_batch = score_native_fixed64_scorer_v1(admission(), scorer_context.clone()).unwrap();
    let other = context(digest(99), NativeScorerV1Config::default());
    let error = evaluate_native_fixed64_pose_validity(
        scorer_batch,
        validity_context(
            &other,
            NativeFixed64ValidityBackend::RustCpu,
            NativeFixed64ValidityConfig::default(),
        ),
    )
    .unwrap_err();
    assert_eq!(
        error.code(),
        NativeFixed64ValidityErrorCode::UpstreamCrossWired
    );
}

#[test]
fn native_stable_top_k_rederives_primary_and_valid_only_rankings() {
    let scorer_context = context(digest(1), NativeScorerV1Config::default());
    let scorer_batch = score_native_fixed64_scorer_v1(admission(), scorer_context.clone()).unwrap();
    let validity = evaluate_native_fixed64_pose_validity(
        scorer_batch,
        validity_context(
            &scorer_context,
            NativeFixed64ValidityBackend::RustCpu,
            NativeFixed64ValidityConfig::default(),
        ),
    )
    .unwrap();

    let first = rank_native_fixed64_top_k(validity.clone()).unwrap();
    let second = rank_native_fixed64_top_k(validity).unwrap();

    assert_eq!(first, second);
    assert_eq!(first.primary_ranking_slot_indices().len(), 12);
    assert_eq!(
        first.primary_ranking_slot_indices(),
        first.valid_ranking_slot_indices()
    );
    assert_eq!(first.top5_slot_indices().len(), 5);
    assert_eq!(first.valid_top5_slot_indices(), first.top5_slot_indices());
    assert_eq!(first.top1_slot_index(), first.valid_top1_slot_index());
    assert!(first.has_valid_receipt());
    assert!(!first.existing_rank_auto_change_authorized());
    assert!(!first.customer_pose_emission_authorized());
    assert!(!first.production_claim_authorized());

    for (offset, slot_index) in first
        .primary_ranking_slot_indices()
        .iter()
        .copied()
        .enumerate()
    {
        let record = &first.records()[slot_index];
        assert!(record.rank_eligible());
        assert!(record.valid_rank_eligible());
        assert_eq!(record.stable_rank(), Some(offset + 1));
        assert_eq!(record.stable_valid_rank(), Some(offset + 1));
        assert!(record.total_score().unwrap().is_finite());
        assert!(record.coordinate_sha256().is_some());
        assert!(record.has_valid_receipt());
    }
    for record in first.records().iter().filter(|row| !row.rank_eligible()) {
        assert_eq!(record.stable_rank(), None);
        assert_eq!(record.stable_valid_rank(), None);
        assert_eq!(record.total_score(), None);
        assert_eq!(record.coordinate_sha256(), None);
    }
}

#[test]
fn native_primary_rank_survives_typed_validity_unavailability_without_valid_rank() {
    let scorer_context = context(digest(1), NativeScorerV1Config::default());
    let scorer_batch = score_native_fixed64_scorer_v1(admission(), scorer_context.clone()).unwrap();
    let limited = NativeFixed64ValidityConfig::new(
        0.15, 0.75, 0.8, 1.0e-6, 1.0e-8, 0.55, 3.5, 250_000, 1, 250_000, 1_000_000,
    )
    .unwrap();
    let validity = evaluate_native_fixed64_pose_validity(
        scorer_batch,
        validity_context(
            &scorer_context,
            NativeFixed64ValidityBackend::RustCpu,
            limited,
        ),
    )
    .unwrap();
    let ranking = rank_native_fixed64_top_k(validity).unwrap();

    assert_eq!(ranking.primary_ranking_slot_indices().len(), 12);
    assert!(ranking.valid_ranking_slot_indices().is_empty());
    assert_eq!(ranking.top5_slot_indices().len(), 5);
    assert!(ranking.valid_top5_slot_indices().is_empty());
    assert!(ranking.valid_top1_slot_index().is_none());
    for slot_index in ranking.primary_ranking_slot_indices() {
        let record = &ranking.records()[*slot_index];
        assert!(record.rank_eligible());
        assert!(!record.valid_rank_eligible());
        assert!(record.stable_rank().is_some());
        assert!(record.stable_valid_rank().is_none());
    }
    assert!(ranking.has_valid_receipt());
}
