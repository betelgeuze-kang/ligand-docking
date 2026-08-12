use betelgeuze_docking_search::{
    Fixed64FeatureGeometry as IndependentFeatureGeometry,
    Fixed64FeatureGeometryInventory as IndependentFeatureGeometryInventory,
    Fixed64FeatureKind as IndependentFeatureKind,
};
use betelgeuze_runtime::{
    Backend, Context, ContextOptions, ErrorCode, Fixed64AtomicFeature,
    Fixed64ConformerCoordinateSource, Fixed64CoordinateSource, Fixed64ExactSourceEvidence,
    Fixed64FeatureGeometry, Fixed64FeatureKind, Fixed64Identities, Fixed64IndexedCoordinateSource,
    Fixed64Ligand, Fixed64Pipeline, Fixed64PipelineContext, Fixed64Receptor, Fixed64RefinementMode,
    Fixed64RunInput, Fixed64SourceEvidence, PositionSoa,
};
use sha2::{Digest, Sha256};

struct SingleAtomFixture {
    receptor_x: [f64; 4],
    receptor_y: [f64; 4],
    receptor_z: [f64; 4],
    ligand_x: [f64; 1],
    ligand_y: [f64; 1],
    ligand_z: [f64; 1],
    receptor_radii: [f64; 4],
    ligand_radii: [f64; 1],
    receptor_charges: [f64; 4],
    ligand_charges: [f64; 1],
    receptor_epsilon: [f64; 4],
    ligand_epsilon: [f64; 1],
    receptor_zero_mask: [u8; 4],
    ligand_zero_mask: [u8; 1],
    heavy_mask: [u8; 1],
    parent: [i32; 1],
}

impl SingleAtomFixture {
    fn new() -> Self {
        Self {
            receptor_x: [4.0, 3.5, 4.0, 4.0],
            receptor_y: [0.0, 0.0, 1.0, 0.0],
            receptor_z: [0.0, 0.0, 0.0, 1.0002],
            ligand_x: [0.0],
            ligand_y: [0.0],
            ligand_z: [0.0],
            receptor_radii: [1.5; 4],
            ligand_radii: [1.5],
            receptor_charges: [-0.5, 0.2, 0.3, 0.0],
            ligand_charges: [0.2],
            receptor_epsilon: [0.2, 0.18, 0.05, 0.25],
            ligand_epsilon: [0.18],
            receptor_zero_mask: [0; 4],
            ligand_zero_mask: [0],
            heavy_mask: [1],
            parent: [-1],
        }
    }

    fn scientific_context(&self) -> Fixed64PipelineContext<'_> {
        Fixed64PipelineContext {
            receptor: Fixed64Receptor {
                coordinates: PositionSoa::new(&self.receptor_x, &self.receptor_y, &self.receptor_z),
                vdw_radius_angstrom: &self.receptor_radii,
                charge_elementary: &self.receptor_charges,
                epsilon_kcal_per_mol: &self.receptor_epsilon,
                hydrophobic_mask: &self.receptor_zero_mask,
                acceptor_mask: &self.receptor_zero_mask,
                donors: &[],
            },
            ligand: Fixed64Ligand {
                reference_coordinates: PositionSoa::new(
                    &self.ligand_x,
                    &self.ligand_y,
                    &self.ligand_z,
                ),
                vdw_radius_angstrom: &self.ligand_radii,
                heavy_atom_mask: &self.heavy_mask,
                charge_elementary: &self.ligand_charges,
                epsilon_kcal_per_mol: &self.ligand_epsilon,
                hydrophobic_mask: &self.ligand_zero_mask,
                acceptor_mask: &self.ligand_zero_mask,
                donors: &[],
                exclusions: &[],
                rotors: &[],
                bonds: &[],
                chirality_centers: &[],
                parent_atom_index: &self.parent,
                rotatable_child_atom_index: &[],
                internal_pairs: &[],
            },
            pocket_center_angstrom: [0.0, 0.0, 0.0],
            pocket_radius_angstrom: 10.0,
            identities: Fixed64Identities {
                authority_input_receipt_sha256: [0x11; 32],
                receptor_system_sha256: [0x22; 32],
                ligand_system_sha256: [0x33; 32],
                backend_receipt_sha256: [0x44; 32],
                validity_scorer_context_receipt_sha256: [0x55; 32],
                contact_policy_sha256: [0x66; 32],
            },
        }
    }

    fn exact_source(&self) -> Fixed64CoordinateSource<'_> {
        Fixed64CoordinateSource {
            evidence: Fixed64SourceEvidence {
                receipt_sha256: [0x10; 32],
                proposal_sha256: [0x11; 32],
                coordinate_sha256: digest(
                    "70c6f2b5446c0652d7bbc81537a0ac8a93553e961ecb3c2c40fee2620de1545b",
                ),
            },
            coordinates: PositionSoa::new(&self.ligand_x, &self.ligand_y, &self.ligand_z),
        }
    }

    fn source(&self, marker: u8) -> Fixed64CoordinateSource<'_> {
        Fixed64CoordinateSource {
            evidence: Fixed64SourceEvidence {
                receipt_sha256: [marker; 32],
                proposal_sha256: [marker.wrapping_add(64); 32],
                coordinate_sha256: digest(
                    "70c6f2b5446c0652d7bbc81537a0ac8a93553e961ecb3c2c40fee2620de1545b",
                ),
            },
            coordinates: PositionSoa::new(&self.ligand_x, &self.ligand_y, &self.ligand_z),
        }
    }
}

struct TwoAtomFixture {
    base: SingleAtomFixture,
    ligand_x: [f64; 2],
    ligand_y: [f64; 2],
    ligand_z: [f64; 2],
    ligand_radii: [f64; 2],
    ligand_charges: [f64; 2],
    ligand_epsilon: [f64; 2],
    ligand_zero_mask: [u8; 2],
    heavy_mask: [u8; 2],
    parent: [i32; 2],
}

impl TwoAtomFixture {
    fn new() -> Self {
        Self {
            base: SingleAtomFixture::new(),
            ligand_x: [-0.5, 0.5],
            ligand_y: [0.0, 0.0],
            ligand_z: [0.0, 0.0],
            ligand_radii: [1.5; 2],
            ligand_charges: [0.2, -0.2],
            ligand_epsilon: [0.18; 2],
            ligand_zero_mask: [0; 2],
            heavy_mask: [1; 2],
            parent: [-1, 0],
        }
    }

    fn scientific_context(&self) -> Fixed64PipelineContext<'_> {
        Fixed64PipelineContext {
            receptor: Fixed64Receptor {
                coordinates: PositionSoa::new(
                    &self.base.receptor_x,
                    &self.base.receptor_y,
                    &self.base.receptor_z,
                ),
                vdw_radius_angstrom: &self.base.receptor_radii,
                charge_elementary: &self.base.receptor_charges,
                epsilon_kcal_per_mol: &self.base.receptor_epsilon,
                hydrophobic_mask: &self.base.receptor_zero_mask,
                acceptor_mask: &self.base.receptor_zero_mask,
                donors: &[],
            },
            ligand: Fixed64Ligand {
                reference_coordinates: PositionSoa::new(
                    &self.ligand_x,
                    &self.ligand_y,
                    &self.ligand_z,
                ),
                vdw_radius_angstrom: &self.ligand_radii,
                heavy_atom_mask: &self.heavy_mask,
                charge_elementary: &self.ligand_charges,
                epsilon_kcal_per_mol: &self.ligand_epsilon,
                hydrophobic_mask: &self.ligand_zero_mask,
                acceptor_mask: &self.ligand_zero_mask,
                donors: &[],
                exclusions: &[],
                rotors: &[],
                bonds: &[],
                chirality_centers: &[],
                parent_atom_index: &self.parent,
                rotatable_child_atom_index: &[],
                internal_pairs: &[],
            },
            pocket_center_angstrom: [0.0, 0.0, 0.0],
            pocket_radius_angstrom: 10.0,
            identities: Fixed64Identities {
                authority_input_receipt_sha256: [0x11; 32],
                receptor_system_sha256: [0x22; 32],
                ligand_system_sha256: [0x33; 32],
                backend_receipt_sha256: [0x44; 32],
                validity_scorer_context_receipt_sha256: [0x55; 32],
                contact_policy_sha256: [0x66; 32],
            },
        }
    }

    fn source(&self, marker: u8) -> Fixed64CoordinateSource<'_> {
        Fixed64CoordinateSource {
            evidence: Fixed64SourceEvidence {
                receipt_sha256: [marker; 32],
                proposal_sha256: [marker.wrapping_add(64); 32],
                coordinate_sha256: coordinate_digest(
                    &self.ligand_x,
                    &self.ligand_y,
                    &self.ligand_z,
                ),
            },
            coordinates: PositionSoa::new(&self.ligand_x, &self.ligand_y, &self.ligand_z),
        }
    }
}

fn canonical_hasher(domain: &str) -> Sha256 {
    let mut hash = Sha256::new();
    hash.update((domain.len() as u64).to_be_bytes());
    hash.update(domain.as_bytes());
    hash
}

fn canonical_f64(hash: &mut Sha256, value: f64) {
    hash.update(
        (if value == 0.0 { 0.0 } else { value })
            .to_bits()
            .to_be_bytes(),
    );
}

fn coordinate_digest(x: &[f64], y: &[f64], z: &[f64]) -> [u8; 32] {
    let mut hash = canonical_hasher("betelgeuze.fixed64_coordinates/native-v1");
    hash.update((x.len() as u64).to_be_bytes());
    for atom in 0..x.len() {
        canonical_f64(&mut hash, x[atom]);
        canonical_f64(&mut hash, y[atom]);
        canonical_f64(&mut hash, z[atom]);
    }
    hash.finalize().into()
}

fn radii_digest(values: &[f64]) -> [u8; 32] {
    let mut hash = canonical_hasher("betelgeuze.fixed64_vdw_radii/native-v1");
    hash.update((values.len() as u64).to_be_bytes());
    for value in values {
        canonical_f64(&mut hash, *value);
    }
    hash.finalize().into()
}

fn mask_digest(values: &[u8]) -> [u8; 32] {
    let mut hash = canonical_hasher("betelgeuze.fixed64_heavy_atom_mask/native-v1");
    hash.update((values.len() as u64).to_be_bytes());
    hash.update(values);
    hash.finalize().into()
}

fn digest(value: &str) -> [u8; 32] {
    assert_eq!(value.len(), 64);
    let mut result = [0_u8; 32];
    for (index, output) in result.iter_mut().enumerate() {
        *output = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16).unwrap();
    }
    result
}

#[test]
fn complete_pipeline_is_raii_bound_to_the_exact_native_context() {
    let fixture = SingleAtomFixture::new();
    for (options, expected) in [
        (ContextOptions::cpu_reference(), Backend::CppCpuReference),
        (ContextOptions::rust_cpu(), Backend::RustCpu),
    ] {
        assert!(Context::backend_available(options.backend, options.device_ordinal).unwrap());
        let context = Context::new(options).unwrap();
        let pipeline = Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap();
        assert_eq!(pipeline.backend(), expected);
        assert_eq!(pipeline.receptor_atom_count(), 4);
        assert_eq!(pipeline.ligand_atom_count(), 1);
    }
    assert_eq!(
        Fixed64Pipeline::profile_id().unwrap(),
        "betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0"
    );
}

fn assert_safe_run_returns_complete_receipt(fixture: &SingleAtomFixture, options: ContextOptions) {
    let v7 = (0_u8..24)
        .map(|index| Fixed64IndexedCoordinateSource {
            source_index: u32::from(index),
            source: fixture.source(index + 1),
        })
        .collect::<Vec<_>>();
    let conformers = (0_u8..7)
        .map(|index| Fixed64ConformerCoordinateSource {
            rank: index + 2,
            source: fixture.source(34 + index),
        })
        .collect::<Vec<_>>();
    let retained_indices = [36_u32, 45, 54, 63];
    let retained = retained_indices
        .iter()
        .enumerate()
        .map(|(index, source_index)| Fixed64IndexedCoordinateSource {
            source_index: *source_index,
            source: fixture.source(48 + index as u8),
        })
        .collect::<Vec<_>>();
    let candidate_modes = [Fixed64RefinementMode::V2Translation; 64];
    let rigid_steps = [4_u64; 64];
    let torsion_eligible = [0_u8; 64];
    let torsion_steps = [0_u64; 64];
    let baseline_angles = [0.0_f64; 64];
    let run = Fixed64RunInput {
        exact_source_evidence: Fixed64ExactSourceEvidence {
            source_receipt_sha256: [0x10; 32],
            proposal_sha256: [0x11; 32],
            ligand_coordinate_sha256: digest(
                "70c6f2b5446c0652d7bbc81537a0ac8a93553e961ecb3c2c40fee2620de1545b",
            ),
            receptor_coordinate_sha256: digest(
                "fc1a4a36a926d55049f0d6d06d3f61328f59ed6860899712dec2df39c6832ef5",
            ),
            prepared_ligand_topology_sha256: [0x33; 32],
            prepared_receptor_topology_sha256: [0x22; 32],
            ligand_vdw_radii_sha256: digest(
                "d4379c8a5c7b2291893bd45b047e8736168136002dd646b705a735875a947919",
            ),
            ligand_heavy_atom_mask_sha256: digest(
                "49e14fc025f4768dc72e02fe53803e4cd9906d5dc7c89c1f7b08c6fb39b9223a",
            ),
            receptor_vdw_radii_sha256: digest(
                "142a64fce99277370fc239fbbb59e85aee8c8c9472a6eb394231b8bff31981f6",
            ),
        },
        exact_source: fixture.exact_source(),
        atomic_features: &[],
        v7_control_sources: &v7,
        conformer_sources: &conformers,
        retained_sources: &retained,
        feature_geometries: &[],
        feature_geometry_inventory_sha256: [0; 32],
        pocket_normal: [0.0, 0.0, 1.0],
        rmsd_threshold_angstrom: 1.5,
        candidate_modes: &candidate_modes,
        rigid_max_steps: &rigid_steps,
        proposal_is_torsion_eligible: &torsion_eligible,
        torsion_max_steps: &torsion_steps,
        baseline_torsion_angles_radians: &baseline_angles,
        predeclared_refinement_policy_sha256: [0x76; 32],
    };
    let context = Context::new(options).unwrap();
    let pipeline = Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap();
    let receipt = pipeline.run(run).unwrap();
    let repeated = pipeline.run(run).unwrap();
    assert_eq!(receipt, repeated);
    let scaled_normal = Fixed64RunInput {
        pocket_normal: [0.0, 0.0, 2.0],
        ..run
    };
    assert_eq!(receipt, pipeline.run(scaled_normal).unwrap());
    let oblique_normal = Fixed64RunInput {
        pocket_normal: [1.0, 1.0, 5.0],
        ..run
    };
    let oblique_receipt = pipeline.run(oblique_normal).unwrap();
    let scaled_oblique_normal = Fixed64RunInput {
        pocket_normal: [2.0, 2.0, 10.0],
        ..run
    };
    assert_eq!(
        oblique_receipt,
        pipeline.run(scaled_oblique_normal).unwrap()
    );
    let mut crosswired_source_evidence = run;
    crosswired_source_evidence
        .exact_source_evidence
        .source_receipt_sha256[0] ^= 1;
    let error = pipeline.run(crosswired_source_evidence).unwrap_err();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert!(error.message.contains("cross-wired"));

    let mismatched_source_x = [1.0_f64];
    let mut mismatched_source_coordinates = run;
    mismatched_source_coordinates.exact_source.coordinates =
        PositionSoa::new(&mismatched_source_x, &fixture.ligand_y, &fixture.ligand_z);
    let error = pipeline.run(mismatched_source_coordinates).unwrap_err();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert!(error.message.contains("supplied coordinates"));
    for crosswire_ligand in [true, false] {
        let mut crosswired = run;
        if crosswire_ligand {
            crosswired
                .exact_source_evidence
                .prepared_ligand_topology_sha256[0] ^= 1;
        } else {
            crosswired
                .exact_source_evidence
                .prepared_receptor_topology_sha256[0] ^= 1;
        }
        let error = pipeline.run(crosswired).unwrap_err();
        assert_eq!(error.code, ErrorCode::InvalidArgument);
        assert!(error.message.contains("topology identity"));
    }
    assert_eq!(receipt.backend, options.backend);
    assert_eq!(
        receipt.unit_system,
        betelgeuze_runtime::UnitSystem::AngstromKcalMol
    );
    assert_eq!(receipt.receptor_atom_count, 4);
    assert_eq!(receipt.ligand_atom_count, 1);
    assert_eq!(receipt.producer_rows.len(), 64);
    assert_eq!(receipt.rigid_rows.len(), 64);
    assert_eq!(receipt.torsion_rows.len(), 64);
    assert_eq!(receipt.torsion_moves.len(), 512);
    assert_eq!(receipt.refinement_rows.len(), 64);
    assert_eq!(receipt.rows.len(), 64);
    assert_eq!(receipt.scorer_rows.len(), 64);
    assert_eq!(receipt.validity_rows.len(), 64);
    assert_eq!(receipt.generated_count, 28);
    assert_eq!(receipt.typed_failure_count, 36);
    for coordinates in [
        &receipt.producer_coordinates,
        &receipt.rigid_coordinates.selected,
        &receipt.rigid_coordinates.comparison_v2,
        &receipt.rigid_coordinates.baseline_v3,
        &receipt.rigid_coordinates.clearance_v4,
        &receipt.torsion_coordinates.optimized,
        &receipt.torsion_coordinates.final_state,
        &receipt.final_coordinates,
    ] {
        assert_eq!(coordinates.x_angstrom.len(), 64);
        assert_eq!(coordinates.y_angstrom.len(), 64);
        assert_eq!(coordinates.z_angstrom.len(), 64);
    }
    assert_eq!(
        receipt
            .torsion_coordinates
            .optimized_torsion_angles_radians
            .len(),
        64
    );
    assert_eq!(
        receipt
            .torsion_coordinates
            .final_torsion_angles_radians
            .len(),
        64
    );
    assert_eq!(
        receipt
            .producer_rows
            .iter()
            .filter(|row| row.coordinates_available)
            .count(),
        28
    );
    assert!(receipt
        .producer_rows
        .iter()
        .all(|row| row.denominator_preserved));
    assert!(receipt.producer_rows.iter().all(|row| {
        row.backend == options.backend
            && row.ligand_atom_count == 1
            && (row.geometric.ligand_atom_count == 0
                || (row.geometric.ligand_atom_count == 1 && row.geometric.receptor_atom_count == 4))
    }));
    assert!(receipt
        .scorer_rows
        .iter()
        .all(|row| row.weighted_terms.iter().all(|term| term.is_finite())));
    assert!(receipt
        .torsion_moves
        .iter()
        .enumerate()
        .all(|(index, move_evidence)| {
            move_evidence.slot_index as usize == index / 8
                && move_evidence.move_index as usize == index % 8
        }));
    assert!(receipt.authority.denominator_preserved);
    assert!(!receipt.authority.multi_anchor_consumed);
    assert!(!receipt.authority.molecular_execution_authorized);
    assert!(!receipt.authority.reservation_authorized);
    assert!(!receipt.authority.benchmark_execution_authorized);
    assert!(!receipt.authority.production_claim_authorized);
    for digest in [
        receipt.receipts.allocation_inventory_sha256,
        receipt.receipts.allocation_receipt_sha256,
        receipt.receipts.source_bundle_receipt_sha256,
        receipt.receipts.geometric_admission_batch_receipt_sha256,
        receipt.receipts.admission_context_receipt_sha256,
        receipt.receipts.refinement_context_receipt_sha256,
        receipt.receipts.scorer_context_receipt_sha256,
        receipt.receipts.validity_context_receipt_sha256,
        receipt.receipts.component_binding_receipt_sha256,
        receipt.receipts.producer_batch_receipt_sha256,
        receipt.receipts.refinement_policy_receipt_sha256,
        receipt.receipts.refinement_batch_receipt_sha256,
        receipt.receipts.scorer_batch_receipt_sha256,
        receipt.receipts.validity_batch_receipt_sha256,
        receipt.receipts.ranking_batch_receipt_sha256,
        receipt.receipts.cluster_batch_receipt_sha256,
        receipt.receipts.pipeline_batch_receipt_sha256,
    ] {
        assert_ne!(digest, [0; 32]);
    }
    assert!(receipt
        .rows
        .iter()
        .all(|row| row.row_receipt_sha256 != [0; 32]));
}

#[test]
fn safe_run_returns_complete_fixed64_receipt_and_preserves_typed_failures() {
    let fixture = SingleAtomFixture::new();
    for options in [ContextOptions::cpu_reference(), ContextOptions::rust_cpu()] {
        assert_safe_run_returns_complete_receipt(&fixture, options);
    }
}

fn assert_transformed_placements_are_independently_replayed(
    options: ContextOptions,
    include_single_anchor: bool,
) {
    let fixture = TwoAtomFixture::new();
    let v7 = (0_u8..24)
        .map(|index| Fixed64IndexedCoordinateSource {
            source_index: u32::from(index),
            source: fixture.source(index + 1),
        })
        .collect::<Vec<_>>();
    let conformers = (0_u8..7)
        .map(|index| Fixed64ConformerCoordinateSource {
            rank: index + 2,
            source: fixture.source(34 + index),
        })
        .collect::<Vec<_>>();
    let retained = [36_u32, 45, 54, 63]
        .iter()
        .enumerate()
        .map(|(index, source_index)| Fixed64IndexedCoordinateSource {
            source_index: *source_index,
            source: fixture.source(48 + index as u8),
        })
        .collect::<Vec<_>>();
    let candidate_modes = [Fixed64RefinementMode::V2Translation; 64];
    let rigid_steps = [0_u64; 64];
    let torsion_eligible = [0_u8; 64];
    let torsion_steps = [0_u64; 64];
    let baseline_angles = [0.0_f64; 128];
    let exact_source = fixture.source(0x10);
    let ligand_donor_indices = [0_u64, 1];
    let receptor_acceptor_indices = [0_u64];
    let ligand_donor_receipt = [0x81; 32];
    let receptor_acceptor_receipt = [0x82; 32];
    let independent_ligand_donor = IndependentFeatureGeometry::new(
        IndependentFeatureKind::LigandDonor,
        ligand_donor_receipt,
        vec![0, 1],
    )
    .unwrap();
    let independent_receptor_acceptor = IndependentFeatureGeometry::new(
        IndependentFeatureKind::ReceptorAcceptor,
        receptor_acceptor_receipt,
        vec![0],
    )
    .unwrap();
    let feature_geometry_inventory = IndependentFeatureGeometryInventory::new(vec![
        independent_ligand_donor.clone(),
        independent_receptor_acceptor.clone(),
    ])
    .unwrap();
    let atomic_features = if include_single_anchor {
        vec![
            Fixed64AtomicFeature {
                kind: Fixed64FeatureKind::LigandDonor,
                receipt_sha256: ligand_donor_receipt,
            },
            Fixed64AtomicFeature {
                kind: Fixed64FeatureKind::ReceptorAcceptor,
                receipt_sha256: receptor_acceptor_receipt,
            },
        ]
    } else {
        Vec::new()
    };
    let feature_geometries = if include_single_anchor {
        vec![
            Fixed64FeatureGeometry {
                kind: Fixed64FeatureKind::LigandDonor,
                allocation_feature_receipt_sha256: ligand_donor_receipt,
                atom_indices: &ligand_donor_indices,
                feature_geometry_receipt_sha256: independent_ligand_donor.receipt_sha256(),
            },
            Fixed64FeatureGeometry {
                kind: Fixed64FeatureKind::ReceptorAcceptor,
                allocation_feature_receipt_sha256: receptor_acceptor_receipt,
                atom_indices: &receptor_acceptor_indices,
                feature_geometry_receipt_sha256: independent_receptor_acceptor.receipt_sha256(),
            },
        ]
    } else {
        Vec::new()
    };
    let run = Fixed64RunInput {
        exact_source_evidence: Fixed64ExactSourceEvidence {
            source_receipt_sha256: exact_source.evidence.receipt_sha256,
            proposal_sha256: exact_source.evidence.proposal_sha256,
            ligand_coordinate_sha256: exact_source.evidence.coordinate_sha256,
            receptor_coordinate_sha256: coordinate_digest(
                &fixture.base.receptor_x,
                &fixture.base.receptor_y,
                &fixture.base.receptor_z,
            ),
            prepared_ligand_topology_sha256: [0x33; 32],
            prepared_receptor_topology_sha256: [0x22; 32],
            ligand_vdw_radii_sha256: radii_digest(&fixture.ligand_radii),
            ligand_heavy_atom_mask_sha256: mask_digest(&fixture.heavy_mask),
            receptor_vdw_radii_sha256: radii_digest(&fixture.base.receptor_radii),
        },
        exact_source,
        atomic_features: &atomic_features,
        v7_control_sources: &v7,
        conformer_sources: &conformers,
        retained_sources: &retained,
        feature_geometries: &feature_geometries,
        feature_geometry_inventory_sha256: if include_single_anchor {
            feature_geometry_inventory.receipt_sha256()
        } else {
            [0; 32]
        },
        pocket_normal: [0.0, 0.0, 1.0],
        rmsd_threshold_angstrom: 1.5,
        candidate_modes: &candidate_modes,
        rigid_max_steps: &rigid_steps,
        proposal_is_torsion_eligible: &torsion_eligible,
        torsion_max_steps: &torsion_steps,
        baseline_torsion_angles_radians: &baseline_angles,
        predeclared_refinement_policy_sha256: [0x76; 32],
    };
    let context = Context::new(options).unwrap();
    let pipeline = Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap();
    let receipt = pipeline.run(run).unwrap();
    let oblique = pipeline
        .run(Fixed64RunInput {
            pocket_normal: [1.0, 1.0, 5.0],
            ..run
        })
        .unwrap();
    let scaled_oblique = pipeline
        .run(Fixed64RunInput {
            pocket_normal: [2.0, 2.0, 10.0],
            ..run
        })
        .unwrap();
    assert_eq!(oblique, scaled_oblique);
    assert_eq!(
        receipt.generated_count,
        if include_single_anchor { 52 } else { 48 }
    );
    assert!(receipt.producer_rows[24..44].iter().all(|row| {
        row.coordinates_available
            && row.component_failure_code == 0
            && row.placement_receipt_sha256 != [0; 32]
    }));
    if include_single_anchor {
        assert!(receipt.producer_rows[44..48].iter().all(|row| {
            row.coordinates_available
                && row.component_failure_code == 0
                && row.placement_receipt_sha256 != [0; 32]
        }));
    }
}

#[test]
fn transformed_indexed_so3_is_replayed_from_owned_sources() {
    for options in [ContextOptions::cpu_reference(), ContextOptions::rust_cpu()] {
        assert_transformed_placements_are_independently_replayed(options, false);
    }
}

#[test]
fn transformed_single_anchor_is_replayed_from_owned_features() {
    for options in [ContextOptions::cpu_reference(), ContextOptions::rust_cpu()] {
        assert_transformed_placements_are_independently_replayed(options, true);
    }
}

#[cfg(feature = "hip")]
#[test]
fn transformed_placements_are_replayed_on_available_qualified_hip_lanes() {
    let mut tested = 0;
    for options in [ContextOptions::hip_safe(0), ContextOptions::hip_fast(0)] {
        if Context::backend_available(options.backend, options.device_ordinal).unwrap() {
            assert_transformed_placements_are_independently_replayed(options, false);
            assert_transformed_placements_are_independently_replayed(options, true);
            tested += 1;
        }
    }
    if std::env::var("BG_REQUIRE_HIP_DEVICE").as_deref() == Ok("1") {
        assert_eq!(tested, 2, "both qualified HIP lanes must be available");
    }
}

#[cfg(feature = "hip")]
#[test]
fn complete_pipeline_constructs_on_both_qualified_hip_lanes() {
    let fixture = SingleAtomFixture::new();
    for (options, expected) in [
        (ContextOptions::hip_safe(0), Backend::HipSafe),
        (ContextOptions::hip_fast(0), Backend::HipFast),
    ] {
        if !Context::backend_available(options.backend, options.device_ordinal).unwrap() {
            continue;
        }
        let context = Context::new(options).unwrap();
        let pipeline = Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap();
        assert_eq!(pipeline.backend(), expected);
        assert_eq!(pipeline.receptor_atom_count(), 4);
        assert_eq!(pipeline.ligand_atom_count(), 1);
        drop(pipeline);
        drop(context);
        assert_safe_run_returns_complete_receipt(&fixture, options);
    }
}

#[test]
fn safe_constructor_rejects_mismatched_channels_before_native_creation() {
    let fixture = SingleAtomFixture::new();
    let context = Context::new(ContextOptions::rust_cpu()).unwrap();
    let mut scientific = fixture.scientific_context();
    scientific.ligand.heavy_atom_mask = &[];
    let error = match Fixed64Pipeline::new(&context, scientific) {
        Ok(_) => panic!("mismatched ligand channel unexpectedly created a pipeline"),
        Err(error) => error,
    };
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert!(error.message.contains("heavy-atom mask"));
}

#[test]
fn safe_constructor_rejects_absent_receipt_identity() {
    let fixture = SingleAtomFixture::new();
    let context = Context::new(ContextOptions::rust_cpu()).unwrap();
    let mut scientific = fixture.scientific_context();
    scientific.identities.contact_policy_sha256 = [0; 32];
    let error = match Fixed64Pipeline::new(&context, scientific) {
        Ok(_) => panic!("absent contact-policy receipt unexpectedly created a pipeline"),
        Err(error) => error,
    };
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert!(error.message.contains("contact policy"));
}
