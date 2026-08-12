use std::collections::BTreeMap;

use betelgeuze_docking_search::{
    Fixed64Allocation, Fixed64AllocationError, Fixed64AtomicFeatureEvidence,
    Fixed64ConformerSourceEvidence, Fixed64ExactV11SourceEvidence, Fixed64FeatureInventory,
    Fixed64FeatureKind, Fixed64GenerationParentRole, Fixed64IndexedSourceEvidence,
    Fixed64MissingFeature, Fixed64SourceEvidence, FIXED64_CANDIDATE_COUNT, FIXED64_LANE_RANGES,
    NATIVE_FIXED64_ALLOCATION_SCHEMA_ID, NATIVE_FIXED64_SLOT_SCHEMA_ID, RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_SLOT_RANKS,
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

fn source(marker: u8) -> Fixed64SourceEvidence {
    Fixed64SourceEvidence {
        receipt_sha256: digest(marker),
        proposal_sha256: digest(marker.wrapping_add(64)),
        coordinate_sha256: digest(marker.wrapping_add(128)),
    }
}

fn exact_source() -> Fixed64ExactV11SourceEvidence {
    Fixed64ExactV11SourceEvidence {
        source_receipt_sha256: digest(240),
        proposal_sha256: digest(241),
        ligand_coordinate_sha256: digest(242),
        receptor_coordinate_sha256: digest(243),
        prepared_ligand_topology_sha256: digest(244),
        prepared_receptor_topology_sha256: digest(245),
        ligand_vdw_radii_sha256: digest(246),
        ligand_heavy_atom_mask_sha256: digest(247),
        receptor_vdw_radii_sha256: digest(248),
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

fn v7_controls() -> Vec<Fixed64IndexedSourceEvidence> {
    (0_u32..24)
        .map(|source_index| Fixed64IndexedSourceEvidence {
            source_index,
            source: source(1 + u8::try_from(source_index).unwrap()),
        })
        .collect()
}

fn conformers() -> Vec<Fixed64ConformerSourceEvidence> {
    (2_u8..=8)
        .map(|rank| Fixed64ConformerSourceEvidence {
            rank,
            source: source(32 + rank),
        })
        .collect()
}

fn retained_sources() -> Vec<Fixed64IndexedSourceEvidence> {
    RETAINED_SOURCE_INDICES
        .into_iter()
        .enumerate()
        .map(|(offset, source_index)| Fixed64IndexedSourceEvidence {
            source_index,
            source: source(48 + u8::try_from(offset).unwrap()),
        })
        .collect()
}

fn inventory(complete: bool) -> Fixed64FeatureInventory {
    Fixed64FeatureInventory::new(
        exact_source(),
        if complete { atomic_features() } else { vec![] },
        if complete { v7_controls() } else { vec![] },
        if complete { conformers() } else { vec![] },
        if complete { retained_sources() } else { vec![] },
    )
    .unwrap()
}

#[test]
fn parent_bound_receipts_use_the_versioned_schema() {
    assert_eq!(
        NATIVE_FIXED64_SLOT_SCHEMA_ID,
        "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_slot/1.1.0"
    );
    assert_eq!(
        NATIVE_FIXED64_ALLOCATION_SCHEMA_ID,
        "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_allocation/1.1.0"
    );
}

#[test]
fn zero_identity_sentinels_fail_closed() {
    let mut exact = exact_source();
    exact.source_receipt_sha256 = [0; 32];
    assert!(Fixed64FeatureInventory::new(
        exact,
        atomic_features(),
        v7_controls(),
        conformers(),
        retained_sources(),
    )
    .is_err());

    let mut controls = v7_controls();
    controls[0].source.coordinate_sha256 = [0; 32];
    assert!(Fixed64FeatureInventory::new(
        exact_source(),
        atomic_features(),
        controls,
        conformers(),
        retained_sources(),
    )
    .is_err());

    let mut features = atomic_features();
    features[0].receipt_sha256 = [0; 32];
    assert!(Fixed64FeatureInventory::new(
        exact_source(),
        features,
        v7_controls(),
        conformers(),
        retained_sources(),
    )
    .is_err());
}

#[test]
fn complete_inventory_freezes_all_64_slots_and_lane_sources() {
    let allocation = Fixed64Allocation::build(inventory(true)).unwrap();

    assert_eq!(allocation.slots().len(), FIXED64_CANDIDATE_COUNT);
    assert_eq!(allocation.ready_count(), 64);
    assert_eq!(allocation.typed_failure_count(), 0);
    assert!(allocation.has_valid_receipt());
    assert!(!allocation.result_dependent_allocation());
    assert!(!allocation.molecular_execution_authorized());

    let mut lane_counts = BTreeMap::new();
    for (index, slot) in allocation.slots().iter().enumerate() {
        assert_eq!(slot.slot_index(), index);
        assert!(slot.generation_eligible());
        assert!(slot.missing_features().is_empty());
        assert!(!slot.fallback_allowed());
        assert!(!slot.multi_anchor_allowed());
        *lane_counts.entry(slot.lane()).or_insert(0_usize) += 1;
    }
    for (lane, start, end) in FIXED64_LANE_RANGES {
        assert_eq!(lane_counts[&lane], end - start + 1);
        for (offset, slot) in allocation.slots()[start..=end].iter().enumerate() {
            assert_eq!(slot.lane(), lane);
            assert_eq!(slot.lane_offset(), offset);
        }
    }

    assert_eq!(
        allocation.slots()[..24]
            .iter()
            .map(|slot| slot.v7_control_source_index().unwrap())
            .collect::<Vec<_>>(),
        (0_u32..24).collect::<Vec<_>>()
    );
    assert_eq!(
        allocation.slots()[24..36]
            .iter()
            .map(|slot| slot.so3_sequence_index().unwrap())
            .collect::<Vec<_>>(),
        (0_u8..12).collect::<Vec<_>>()
    );
    assert_eq!(
        allocation.slots()[36..44]
            .iter()
            .map(|slot| slot.so3_sequence_index().unwrap())
            .collect::<Vec<_>>(),
        (0_u8..8).collect::<Vec<_>>()
    );
    assert_eq!(
        allocation.slots()[36..44]
            .iter()
            .map(|slot| slot.true_conformer_rank().unwrap())
            .collect::<Vec<_>>(),
        TRUE_CONFORMER_SLOT_RANKS
    );
    assert_eq!(
        allocation.slots()[60..64]
            .iter()
            .map(|slot| slot.retained_source_index().unwrap())
            .collect::<Vec<_>>(),
        RETAINED_SOURCE_INDICES
    );

    assert!(allocation.slots()[..24].iter().all(|slot| {
        slot.generation_parent().unwrap().role
            == Fixed64GenerationParentRole::ExactPassthroughParent
            && slot.selected_source_receipt_sha256s().len() == 1
    }));
    assert!(allocation.slots()[24..36].iter().all(|slot| {
        slot.generation_parent().unwrap().role == Fixed64GenerationParentRole::GeneratorInputParent
            && slot.selected_source_receipt_sha256s().is_empty()
    }));
    assert!(allocation.slots()[36..44].iter().all(|slot| {
        slot.generation_parent().unwrap().role == Fixed64GenerationParentRole::GeneratorInputParent
            && slot.selected_source_receipt_sha256s().len() == 1
    }));
    assert!(allocation.slots()[44..60].iter().all(|slot| {
        slot.declared_anchor_count() == 1 && slot.selected_source_receipt_sha256s().len() == 2
    }));
    assert!(allocation.slots()[60..64].iter().all(|slot| {
        slot.generation_parent().unwrap().role
            == Fixed64GenerationParentRole::ExactPassthroughParent
            && slot.selected_source_receipt_sha256s().len() == 1
    }));
    assert!(allocation.slots()[..44]
        .iter()
        .chain(&allocation.slots()[60..])
        .all(|slot| slot.declared_anchor_count() == 0));

    assert_eq!(
        allocation.slots()[36].selected_source_receipt_sha256s(),
        allocation.slots()[43].selected_source_receipt_sha256s()
    );
}

#[test]
fn missing_feature_slots_remain_in_the_64_slot_denominator() {
    let allocation = Fixed64Allocation::build(inventory(false)).unwrap();

    assert_eq!(allocation.slots().len(), 64);
    assert_eq!(allocation.ready_count(), 12);
    assert_eq!(allocation.typed_failure_count(), 52);
    assert!(allocation.slots()[24..36]
        .iter()
        .all(|slot| slot.generation_eligible()));
    assert!(allocation.slots()[..24]
        .iter()
        .chain(&allocation.slots()[36..])
        .all(|slot| !slot.generation_eligible()));

    for (index, slot) in allocation.slots()[..24].iter().enumerate() {
        assert_eq!(
            slot.missing_features(),
            &[Fixed64MissingFeature::V7ControlSource(
                u8::try_from(index).unwrap()
            )]
        );
        assert!(slot.generation_parent().is_none());
    }
    assert_eq!(
        allocation.slots()[36].missing_features(),
        &[Fixed64MissingFeature::TrueConformer(2)]
    );
    assert_eq!(
        allocation.slots()[44].missing_features(),
        &[
            Fixed64MissingFeature::LigandDonor,
            Fixed64MissingFeature::ReceptorAcceptor,
        ]
    );
    assert_eq!(
        allocation.slots()[48].missing_features(),
        &[
            Fixed64MissingFeature::LigandAcceptor,
            Fixed64MissingFeature::ReceptorDonor,
        ]
    );
    assert_eq!(
        allocation.slots()[52].missing_features(),
        &[Fixed64MissingFeature::ComplementaryChargeAnchor]
    );
    assert_eq!(
        allocation.slots()[56].missing_features(),
        &[
            Fixed64MissingFeature::LigandAromaticPlane,
            Fixed64MissingFeature::ReceptorAromaticPlane,
        ]
    );
    assert_eq!(
        allocation.slots()[58].missing_features(),
        &[
            Fixed64MissingFeature::LigandShapeAxis,
            Fixed64MissingFeature::PocketShapeAxis,
        ]
    );
    assert_eq!(
        allocation.slots()[60..64]
            .iter()
            .map(|slot| slot.missing_features()[0])
            .collect::<Vec<_>>(),
        RETAINED_SOURCE_INDICES
            .map(Fixed64MissingFeature::RetainedSource)
            .to_vec()
    );
    assert!(allocation.slots()[44..60]
        .iter()
        .all(|slot| slot.generation_parent().is_some()));
    assert!(allocation.slots()[60..64]
        .iter()
        .all(|slot| slot.generation_parent().is_none()));
}

#[test]
fn one_missing_atomic_feature_only_fails_its_frozen_lane() {
    let receptor_acceptor_receipt = atomic_features()
        .into_iter()
        .find(|feature| feature.kind == Fixed64FeatureKind::ReceptorAcceptor)
        .unwrap()
        .receipt_sha256;
    let features = atomic_features()
        .into_iter()
        .filter(|feature| feature.kind != Fixed64FeatureKind::ReceptorAcceptor)
        .collect();
    let inventory = Fixed64FeatureInventory::new(
        exact_source(),
        features,
        v7_controls(),
        conformers(),
        retained_sources(),
    )
    .unwrap();
    let allocation = Fixed64Allocation::build(inventory).unwrap();

    assert_eq!(allocation.ready_count(), 60);
    assert_eq!(allocation.typed_failure_count(), 4);
    assert_eq!(
        allocation
            .slots()
            .iter()
            .filter(|slot| !slot.generation_eligible())
            .map(|slot| slot.slot_index())
            .collect::<Vec<_>>(),
        vec![44, 45, 46, 47]
    );
    assert!(allocation.slots()[44..48].iter().all(|slot| {
        slot.missing_features() == [Fixed64MissingFeature::ReceptorAcceptor]
            && slot.selected_source_receipt_sha256s().len() == 1
            && !slot
                .selected_source_receipt_sha256s()
                .contains(&receptor_acceptor_receipt)
            && slot.declared_anchor_count() == 1
            && !slot.fallback_allowed()
    }));
}

#[test]
fn allocation_and_slot_receipts_are_repeat_stable() {
    let frozen_inventory = inventory(true);
    let first = Fixed64Allocation::build(frozen_inventory.clone()).unwrap();
    let second = Fixed64Allocation::build(frozen_inventory).unwrap();

    assert_eq!(first, second);
    assert_eq!(first.inventory_sha256(), second.inventory_sha256());
    assert_eq!(first.receipt_sha256(), second.receipt_sha256());
    assert_eq!(
        first
            .slots()
            .iter()
            .map(|slot| slot.receipt_sha256())
            .collect::<Vec<_>>(),
        second
            .slots()
            .iter()
            .map(|slot| slot.receipt_sha256())
            .collect::<Vec<_>>()
    );
}

#[test]
fn noncanonical_duplicate_and_out_of_range_inventory_fails_closed() {
    let mut unsorted_features = atomic_features();
    unsorted_features.swap(0, 1);
    assert!(matches!(
        Fixed64FeatureInventory::new(
            exact_source(),
            unsorted_features,
            v7_controls(),
            conformers(),
            retained_sources(),
        ),
        Err(Fixed64AllocationError::InvalidInventory(_))
    ));

    let mut duplicate_controls = v7_controls();
    duplicate_controls[1].source.receipt_sha256 = duplicate_controls[0].source.receipt_sha256;
    assert!(matches!(
        Fixed64FeatureInventory::new(
            exact_source(),
            atomic_features(),
            duplicate_controls,
            conformers(),
            retained_sources(),
        ),
        Err(Fixed64AllocationError::InvalidInventory(_))
    ));

    let mut invalid_control = v7_controls();
    invalid_control[23].source_index = 24;
    assert!(matches!(
        Fixed64FeatureInventory::new(
            exact_source(),
            atomic_features(),
            invalid_control,
            conformers(),
            retained_sources(),
        ),
        Err(Fixed64AllocationError::InvalidInventory(_))
    ));

    let mut invalid_conformer = conformers();
    invalid_conformer[0].rank = 1;
    assert!(matches!(
        Fixed64FeatureInventory::new(
            exact_source(),
            atomic_features(),
            v7_controls(),
            invalid_conformer,
            retained_sources(),
        ),
        Err(Fixed64AllocationError::InvalidInventory(_))
    ));

    let mut invalid_retained = retained_sources();
    invalid_retained[0].source_index = 37;
    assert!(matches!(
        Fixed64FeatureInventory::new(
            exact_source(),
            atomic_features(),
            v7_controls(),
            conformers(),
            invalid_retained,
        ),
        Err(Fixed64AllocationError::InvalidInventory(_))
    ));
}
