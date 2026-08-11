use betelgeuze_docking_search::{
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, produce_native_fixed64_proposals, Fixed64Allocation,
    Fixed64AtomicFeatureEvidence, Fixed64ConformerSourceEvidence, Fixed64CoordinateSourceKind,
    Fixed64CoordinateSourcePayload, Fixed64ExactV11SourceEvidence, Fixed64FeatureGeometry,
    Fixed64FeatureGeometryInventory, Fixed64FeatureInventory, Fixed64FeatureKind,
    Fixed64GeometricBatch, Fixed64GeometricInput, Fixed64GeometricStatus,
    Fixed64IndexedSourceEvidence, Fixed64PlacementErrorCode, Fixed64ProposalFailureCode,
    Fixed64ProposalPlacement, Fixed64ProposalSourceBundle, Fixed64ProposalStatus,
    Fixed64SourceEvidence, Vec3, RETAINED_SOURCE_INDICES,
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

fn feature_atom_indices(kind: Fixed64FeatureKind, degenerate_donor: bool) -> Vec<usize> {
    match kind {
        Fixed64FeatureKind::LigandDonor if degenerate_donor => vec![3, 7],
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

struct Fixture {
    allocation: Fixed64Allocation,
    exact: Fixed64CoordinateSourcePayload,
    v7: Vec<Fixed64CoordinateSourcePayload>,
    conformers: Vec<Fixed64CoordinateSourcePayload>,
    retained: Vec<Fixed64CoordinateSourcePayload>,
    features: Fixed64FeatureGeometryInventory,
    geometry: Fixed64GeometricInput,
}

impl Fixture {
    fn new() -> Self {
        Self::with_first_v7_coordinates(ligand())
    }

    fn with_first_v7_coordinates(first_v7_coordinates: Vec<Vec3>) -> Self {
        let ligand = ligand();
        let receptor = receptor();
        let ligand_radii = vec![1.2; ligand.len()];
        let heavy_mask = vec![true; ligand.len()];
        let receptor_radii = vec![1.2; receptor.len()];
        let exact = Fixed64ExactV11SourceEvidence {
            source_receipt_sha256: digest(1),
            proposal_sha256: digest(2),
            ligand_coordinate_sha256: native_fixed64_coordinate_sha256(&ligand).unwrap(),
            receptor_coordinate_sha256: native_fixed64_coordinate_sha256(&receptor).unwrap(),
            prepared_ligand_topology_sha256: digest(3),
            prepared_receptor_topology_sha256: digest(4),
            ligand_vdw_radii_sha256: native_fixed64_radii_sha256(&ligand_radii).unwrap(),
            ligand_heavy_atom_mask_sha256: native_fixed64_heavy_atom_mask_sha256(&heavy_mask)
                .unwrap(),
            receptor_vdw_radii_sha256: native_fixed64_radii_sha256(&receptor_radii).unwrap(),
        };
        let v7_evidence = (0_u32..24)
            .map(|source_index| {
                let coordinates = if source_index == 0 {
                    &first_v7_coordinates
                } else {
                    &ligand
                };
                Fixed64IndexedSourceEvidence {
                    source_index,
                    source: Fixed64SourceEvidence {
                        receipt_sha256: digest(20 + u8::try_from(source_index).unwrap()),
                        proposal_sha256: digest(60 + u8::try_from(source_index).unwrap()),
                        coordinate_sha256: native_fixed64_coordinate_sha256(coordinates).unwrap(),
                    },
                }
            })
            .collect::<Vec<_>>();
        let conformer_evidence = (2_u8..=8)
            .map(|rank| Fixed64ConformerSourceEvidence {
                rank,
                source: Fixed64SourceEvidence {
                    receipt_sha256: digest(100 + rank),
                    proposal_sha256: digest(110 + rank),
                    coordinate_sha256: native_fixed64_coordinate_sha256(&ligand).unwrap(),
                },
            })
            .collect::<Vec<_>>();
        let retained_evidence = RETAINED_SOURCE_INDICES
            .into_iter()
            .enumerate()
            .map(|(offset, source_index)| Fixed64IndexedSourceEvidence {
                source_index,
                source: Fixed64SourceEvidence {
                    receipt_sha256: digest(120 + u8::try_from(offset).unwrap()),
                    proposal_sha256: digest(130 + u8::try_from(offset).unwrap()),
                    coordinate_sha256: native_fixed64_coordinate_sha256(&ligand).unwrap(),
                },
            })
            .collect::<Vec<_>>();
        let atomic_features = FEATURE_KINDS
            .into_iter()
            .enumerate()
            .map(|(index, kind)| Fixed64AtomicFeatureEvidence {
                kind,
                receipt_sha256: digest(140 + u8::try_from(index).unwrap()),
            })
            .collect::<Vec<_>>();
        let inventory = Fixed64FeatureInventory::new(
            exact,
            atomic_features,
            v7_evidence.clone(),
            conformer_evidence.clone(),
            retained_evidence.clone(),
        )
        .unwrap();
        let allocation = Fixed64Allocation::build(inventory).unwrap();
        let exact = Fixed64CoordinateSourcePayload::new(
            Fixed64CoordinateSourceKind::ExactV11Base,
            None,
            exact.ligand_source(),
            ligand.clone(),
        )
        .unwrap();
        let v7 = v7_evidence
            .into_iter()
            .map(|row| {
                let coordinates = if row.source_index == 0 {
                    first_v7_coordinates.clone()
                } else {
                    ligand.clone()
                };
                Fixed64CoordinateSourcePayload::new(
                    Fixed64CoordinateSourceKind::V7Control,
                    Some(row.source_index),
                    row.source,
                    coordinates,
                )
                .unwrap()
            })
            .collect();
        let conformers = conformer_evidence
            .into_iter()
            .map(|row| {
                Fixed64CoordinateSourcePayload::new(
                    Fixed64CoordinateSourceKind::TrueConformer,
                    Some(u32::from(row.rank)),
                    row.source,
                    ligand.clone(),
                )
                .unwrap()
            })
            .collect();
        let retained = retained_evidence
            .into_iter()
            .map(|row| {
                Fixed64CoordinateSourcePayload::new(
                    Fixed64CoordinateSourceKind::RetainedControl,
                    Some(row.source_index),
                    row.source,
                    ligand.clone(),
                )
                .unwrap()
            })
            .collect();
        let features = feature_inventory(false);
        let geometry = Fixed64GeometricInput::new(
            ligand_radii,
            heavy_mask,
            receptor,
            receptor_radii,
            Vec3::new(0.0, 0.0, 5.0),
            20.0,
        )
        .unwrap();
        Self {
            allocation,
            exact,
            v7,
            conformers,
            retained,
            features,
            geometry,
        }
    }

    fn bundle(
        &self,
        exact: Option<Fixed64CoordinateSourcePayload>,
        v7: Vec<Fixed64CoordinateSourcePayload>,
        features: Fixed64FeatureGeometryInventory,
    ) -> Fixed64ProposalSourceBundle {
        Fixed64ProposalSourceBundle::new(
            &self.allocation,
            exact,
            v7,
            self.conformers.clone(),
            self.retained.clone(),
            features,
            self.geometry.clone(),
            Vec3::new(0.0, 0.0, 2.0),
        )
        .unwrap()
    }

    fn complete_bundle(&self) -> Fixed64ProposalSourceBundle {
        self.bundle(
            Some(self.exact.clone()),
            self.v7.clone(),
            self.features.clone(),
        )
    }
}

fn feature_inventory(degenerate_donor: bool) -> Fixed64FeatureGeometryInventory {
    Fixed64FeatureGeometryInventory::new(
        FEATURE_KINDS
            .into_iter()
            .enumerate()
            .map(|(index, kind)| {
                Fixed64FeatureGeometry::new(
                    kind,
                    digest(140 + u8::try_from(index).unwrap()),
                    feature_atom_indices(kind, degenerate_donor),
                )
                .unwrap()
            })
            .collect(),
    )
    .unwrap()
}

#[test]
fn complete_bundle_generates_exactly_64_repeat_stable_records() {
    let fixture = Fixture::new();
    let first =
        produce_native_fixed64_proposals(&fixture.allocation, fixture.complete_bundle()).unwrap();
    let second =
        produce_native_fixed64_proposals(&fixture.allocation, fixture.complete_bundle()).unwrap();

    assert_eq!(first, second);
    assert_eq!(first.records().len(), 64);
    assert_eq!(first.generated_count(), 64);
    assert_eq!(first.typed_failure_count(), 0);
    assert_eq!(first.receipt_sha256(), second.receipt_sha256());
    assert!(first.has_valid_receipt());
    assert!(!first.result_dependent_input_consumed());
    assert!(!first.molecular_execution_authorized());
    assert!(!first.product_mutation_authorized());
    assert!(first.records().iter().all(|record| {
        record.status() == Fixed64ProposalStatus::Generated && record.has_valid_receipt()
    }));

    let first_control = &first.records()[0];
    assert!(matches!(
        first_control.placement(),
        Some(Fixed64ProposalPlacement::ExactPassthrough(_))
    ));
    assert_eq!(
        first_control.output_coordinates_angstrom().unwrap(),
        fixture.v7[0].coordinates_angstrom()
    );
    assert_eq!(
        first_control.source_coordinate_sha256(),
        Some(fixture.v7[0].evidence().coordinate_sha256)
    );
    assert_eq!(
        first_control.source_proposal_sha256(),
        Some(fixture.v7[0].evidence().proposal_sha256)
    );
}

#[test]
fn missing_payloads_fail_only_their_frozen_slots_without_fallback() {
    let fixture = Fixture::new();
    let without_exact = fixture.bundle(None, fixture.v7.clone(), fixture.features.clone());
    let batch = produce_native_fixed64_proposals(&fixture.allocation, without_exact).unwrap();

    assert_eq!(batch.generated_count(), 36);
    assert_eq!(batch.typed_failure_count(), 28);
    for index in (24..36).chain(44..60) {
        assert_eq!(
            batch.records()[index].failure_code(),
            Some(Fixed64ProposalFailureCode::MissingExactV11Source)
        );
        assert!(batch.records()[index]
            .output_coordinates_angstrom()
            .is_none());
    }
    assert!(batch.records()[..24]
        .iter()
        .chain(&batch.records()[36..44])
        .chain(&batch.records()[60..])
        .all(|record| record.status() == Fixed64ProposalStatus::Generated));

    let missing_first_v7 = fixture.bundle(
        Some(fixture.exact.clone()),
        fixture.v7[1..].to_vec(),
        fixture.features.clone(),
    );
    let batch = produce_native_fixed64_proposals(&fixture.allocation, missing_first_v7).unwrap();
    assert_eq!(batch.generated_count(), 63);
    assert_eq!(
        batch.records()[0].failure_code(),
        Some(Fixed64ProposalFailureCode::MissingV7ControlSource)
    );
    assert!(batch.records()[1..]
        .iter()
        .all(|record| record.status() == Fixed64ProposalStatus::Generated));
}

#[test]
fn geometry_degeneracy_is_a_typed_lane_local_failure() {
    let fixture = Fixture::new();
    let bundle = fixture.bundle(
        Some(fixture.exact.clone()),
        fixture.v7.clone(),
        feature_inventory(true),
    );
    let batch = produce_native_fixed64_proposals(&fixture.allocation, bundle).unwrap();

    assert_eq!(batch.generated_count(), 60);
    assert_eq!(batch.typed_failure_count(), 4);
    for record in &batch.records()[44..48] {
        assert_eq!(
            record.failure_code(),
            Some(Fixed64ProposalFailureCode::Placement(
                Fixed64PlacementErrorCode::DegenerateLigandDirection
            ))
        );
        assert!(record
            .failure()
            .unwrap()
            .attempted_source_payload_receipt_sha256()
            .is_some());
    }
    assert!(batch.records()[..44]
        .iter()
        .chain(&batch.records()[48..])
        .all(|record| record.status() == Fixed64ProposalStatus::Generated));
}

#[test]
fn ligand_atom_denominator_mismatch_is_one_typed_slot_failure() {
    let shortened = ligand()[..11].to_vec();
    let fixture = Fixture::with_first_v7_coordinates(shortened);
    let proposals =
        produce_native_fixed64_proposals(&fixture.allocation, fixture.complete_bundle()).unwrap();

    assert_eq!(proposals.generated_count(), 63);
    assert_eq!(proposals.typed_failure_count(), 1);
    assert_eq!(
        proposals.records()[0].failure_code(),
        Some(Fixed64ProposalFailureCode::LigandAtomDenominatorMismatch)
    );
    assert!(proposals.records()[0]
        .failure()
        .unwrap()
        .attempted_source_payload_receipt_sha256()
        .is_some());
    assert!(proposals.records()[1..]
        .iter()
        .all(|record| record.status() == Fixed64ProposalStatus::Generated));

    let admission = Fixed64GeometricBatch::evaluate_proposals(proposals).unwrap();
    assert_eq!(admission.decisions().len(), 64);
    assert_eq!(admission.typed_generation_failure_count(), 1);
    assert_eq!(
        admission.decisions()[0].proposal_failure_code(),
        Some(Fixed64ProposalFailureCode::LigandAtomDenominatorMismatch)
    );
    assert!(admission.has_valid_receipt());
}

#[test]
fn proposal_aware_admission_preserves_producer_failures_in_64_rows() {
    let fixture = Fixture::new();
    let bundle = fixture.bundle(
        Some(fixture.exact.clone()),
        fixture.v7[1..].to_vec(),
        fixture.features.clone(),
    );
    let proposals = produce_native_fixed64_proposals(&fixture.allocation, bundle).unwrap();
    let proposal_receipt = proposals.receipt_sha256();
    let admission = Fixed64GeometricBatch::evaluate_proposals(proposals).unwrap();

    assert_eq!(admission.decisions().len(), 64);
    assert_eq!(admission.typed_generation_failure_count(), 1);
    assert_eq!(
        admission.decisions()[0].status(),
        Fixed64GeometricStatus::TypedGenerationFailure
    );
    assert_eq!(
        admission.decisions()[0].proposal_failure_code(),
        Some(Fixed64ProposalFailureCode::MissingV7ControlSource)
    );
    assert!(admission.decisions()[0]
        .proposal_record_receipt_sha256()
        .is_some());
    assert!(admission.decisions()[0].metrics().is_none());
    assert!(!admission.decisions()[0].rank_eligible());
    assert_eq!(
        admission.proposal_batch().unwrap().receipt_sha256(),
        proposal_receipt
    );
    assert!(admission.has_valid_receipt());
}

#[test]
fn exact_system_cross_wiring_fails_before_production() {
    let fixture = Fixture::new();
    let mut changed_receptor = receptor();
    changed_receptor[0].x += 0.125;
    let changed_geometry = Fixed64GeometricInput::new(
        vec![1.2; ligand().len()],
        vec![true; ligand().len()],
        changed_receptor.clone(),
        vec![1.2; changed_receptor.len()],
        Vec3::new(0.0, 0.0, 5.0),
        20.0,
    )
    .unwrap();
    let error = Fixed64ProposalSourceBundle::new(
        &fixture.allocation,
        Some(fixture.exact),
        fixture.v7,
        fixture.conformers,
        fixture.retained,
        fixture.features,
        changed_geometry,
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap_err();
    assert_eq!(
        error.code(),
        betelgeuze_docking_search::Fixed64ProducerErrorCode::ExactSystemCrossWired
    );
}

#[test]
fn malformed_source_groups_fail_closed_without_panicking() {
    let fixture = Fixture::new();
    let error = Fixed64ProposalSourceBundle::new(
        &fixture.allocation,
        Some(fixture.exact.clone()),
        vec![fixture.exact.clone(), fixture.exact],
        fixture.conformers,
        fixture.retained,
        fixture.features,
        fixture.geometry,
        Vec3::new(0.0, 0.0, 1.0),
    )
    .unwrap_err();
    assert_eq!(
        error.code(),
        betelgeuze_docking_search::Fixed64ProducerErrorCode::SourcePayloadCrossWired
    );
}
