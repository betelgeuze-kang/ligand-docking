use betelgeuze_docking_search::{
    materialize_native_sampling_funnel_preselected_batch, native_fixed64_coordinate_sha256,
    run_native_sampling_funnel, Fixed64FeatureGeometry as IndependentFeatureGeometry,
    Fixed64FeatureGeometryInventory as IndependentFeatureGeometryInventory,
    Fixed64FeatureKind as IndependentFeatureKind, NativeSamplingFunnelCandidate,
    NativeSamplingFunnelLane, NativeSamplingFunnelPayloadBatch, NativeSamplingFunnelPayloadRow,
    Quaternion, Vec3,
};
use betelgeuze_runtime::{
    Backend, Context, ContextOptions, ErrorCode, Fixed64AtomicFeature,
    Fixed64ConformerCoordinateSource, Fixed64CoordinateSource, Fixed64ExactSourceEvidence,
    Fixed64FeatureGeometry, Fixed64FeatureKind, Fixed64Identities, Fixed64IndexedCoordinateSource,
    Fixed64LaneMetricsReceipt, Fixed64LaneMetricsReference, Fixed64Ligand, Fixed64Pipeline,
    Fixed64PipelineContext, Fixed64PreselectedRunInput, Fixed64Receptor, Fixed64RefinementMode,
    Fixed64RunInput, Fixed64ScientificProjection, Fixed64SourceEvidence, PositionSoa,
};
use betelgeuze_sys as sys;
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
        self.scientific_context_at([0.0, 0.0, 0.0])
    }

    fn scientific_context_at(
        &self,
        pocket_center_angstrom: [f64; 3],
    ) -> Fixed64PipelineContext<'_> {
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
            pocket_center_angstrom,
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

fn funnel_digest(value: u64) -> [u8; 32] {
    let mut digest = [0; 32];
    digest[24..].copy_from_slice(&value.to_be_bytes());
    digest
}

fn funnel_lane(index: usize) -> NativeSamplingFunnelLane {
    match index % 4 {
        0 => NativeSamplingFunnelLane::UniformSo3,
        1 => NativeSamplingFunnelLane::PocketSurface,
        2 => NativeSamplingFunnelLane::SingleAnchor,
        3 => NativeSamplingFunnelLane::MultiAnchor,
        _ => unreachable!(),
    }
}

fn funnel_coordinates(index: usize) -> Vec<Vec3> {
    let base = index as f64 * 0.01;
    vec![
        Vec3::new(base - 0.5, 0.0, 0.0),
        Vec3::new(base + 0.5, 0.0, 0.0),
    ]
}

fn preselected_funnel_fixture() -> betelgeuze_docking_search::NativeSamplingFunnelPreselectedBatch {
    let candidates = (0..512)
        .map(|index| {
            if funnel_lane(index) == NativeSamplingFunnelLane::MultiAnchor {
                NativeSamplingFunnelCandidate::typed_failure(
                    index,
                    NativeSamplingFunnelLane::MultiAnchor,
                    "synthetic_feature_missing",
                )
                .unwrap()
            } else {
                let coordinates = funnel_coordinates(index);
                NativeSamplingFunnelCandidate::generated(
                    index,
                    funnel_lane(index),
                    funnel_digest(index as u64 + 1),
                    funnel_digest(index as u64 + 513),
                    native_fixed64_coordinate_sha256(&coordinates).unwrap(),
                    0.8,
                    1.0,
                    (index % 17) as f64,
                    (index % 11) as f64,
                    std::array::from_fn(|dimension| ((index * (dimension + 3)) % 19) as f64),
                )
                .unwrap()
            }
        })
        .collect();
    let payloads = (0..512)
        .map(|index| {
            if funnel_lane(index) == NativeSamplingFunnelLane::MultiAnchor {
                NativeSamplingFunnelPayloadRow::typed_failure(index).unwrap()
            } else {
                NativeSamplingFunnelPayloadRow::generated(
                    index,
                    funnel_digest(index as u64 + 1),
                    funnel_digest(index as u64 + 513),
                    funnel_coordinates(index),
                    Quaternion::new(0.0, 0.0, 0.0, 1.0),
                )
                .unwrap()
            }
        })
        .collect();
    let funnel = run_native_sampling_funnel(candidates).unwrap();
    let payloads = NativeSamplingFunnelPayloadBatch::new(2, payloads).unwrap();
    materialize_native_sampling_funnel_preselected_batch(&funnel, &payloads).unwrap()
}

fn assert_numeric_parity(left: f64, right: f64) {
    let scale = left.abs().max(right.abs()).max(1.0);
    assert!(
        (left - right).abs() <= 1.0e-10 * scale,
        "numeric parity mismatch: left={left:?}, right={right:?}"
    );
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
        "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0"
    );
}

#[test]
fn multiple_pipelines_keep_the_shared_context_alive_after_wrapper_drop() {
    let fixture = SingleAtomFixture::new();
    for options in [ContextOptions::cpu_reference(), ContextOptions::rust_cpu()] {
        let (first, second) = {
            let context = Context::new(options).unwrap();
            (
                Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap(),
                Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap(),
            )
        };
        assert_eq!(first.backend(), second.backend());
        drop(first);
        assert_eq!(second.receptor_atom_count(), 4);
        assert_eq!(second.ligand_atom_count(), 1);
        drop(second);
    }
}

fn assert_safe_run_returns_complete_receipt(
    fixture: &SingleAtomFixture,
    options: ContextOptions,
) -> (Fixed64ScientificProjection, Fixed64LaneMetricsReceipt) {
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
        predeclared_post_refinement_admission_policy_sha256: [0x77; 32],
    };
    let (pipeline, sibling_pipeline) = {
        let context = Context::new(options).unwrap();
        (
            Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap(),
            Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap(),
        )
    };
    // The public Context wrapper is already gone. Both private Rc leases must
    // keep the exact native context alive through every run below.
    let receipt = pipeline.run(run).unwrap();
    let sibling_receipt = sibling_pipeline.run(run).unwrap();
    assert_eq!(receipt, sibling_receipt);
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
    let nonbinary_scaled_oblique_normal = Fixed64RunInput {
        pocket_normal: [3.0, 3.0, 15.0],
        ..run
    };
    assert_eq!(
        oblique_receipt,
        pipeline.run(nonbinary_scaled_oblique_normal).unwrap()
    );
    let rounded_scaled_oblique_normal = Fixed64RunInput {
        pocket_normal: [0.3, 0.3, 1.5],
        ..run
    };
    assert_eq!(
        oblique_receipt,
        pipeline.run(rounded_scaled_oblique_normal).unwrap()
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
    let mut absent_post_admission_policy = run;
    absent_post_admission_policy.predeclared_post_refinement_admission_policy_sha256 = [0; 32];
    let error = pipeline.run(absent_post_admission_policy).unwrap_err();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert!(error.message.contains("post-refinement admission policy"));
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
    assert_eq!(receipt.post_admission_rows.len(), 64);
    assert_eq!(receipt.rows.len(), 64);
    assert_eq!(receipt.scorer_rows.len(), 64);
    assert_eq!(receipt.validity_rows.len(), 64);
    assert_eq!(receipt.generated_count, 28);
    assert_eq!(receipt.typed_failure_count, 36);
    assert_eq!(
        receipt.post_admitted_count + receipt.post_rejected_count,
        receipt.refined_count
    );
    assert!(receipt.scored_count <= receipt.post_admitted_count);
    assert!(receipt.valid_count <= receipt.scored_count);
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
    for slot in 0..64 {
        let post = receipt.post_admission_rows[slot];
        assert_eq!(post.slot_index, slot as u32);
        assert_ne!(post.row_receipt_sha256, [0; 32]);
        if post.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED {
            assert_eq!(
                post.failure_code,
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE
            );
            assert_eq!(post.ligand_atom_count, 1);
            assert_eq!(post.receptor_atom_count, 4);
            assert_eq!(post.exact_pair_count, 4);
            assert!(post.penetration_pair_count <= post.exact_pair_count);
            assert!(post.raw_minimum_distance_angstrom.is_finite());
            assert!(post.minimum_vdw_surface_gap_angstrom.is_finite());
            assert!(post.minimum_vdw_ratio.is_finite());
            assert!(post.sphere_overlap_proxy_angstrom3.is_finite());
            assert!(post.pocket_escape_angstrom.is_finite());
        }
        let coordinate_ready = receipt.refinement_rows[slot].status
            == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
        let admitted = post.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
            && post.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && post.rank_eligible;
        if coordinate_ready && !admitted {
            assert_eq!(
                receipt.scorer_rows[slot].status,
                sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
            );
            assert_eq!(
                receipt.scorer_rows[slot].failure_code,
                sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
            );
            assert!(!receipt.ranking_rows[slot].rank_eligible);
        }
    }
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
        receipt.receipts.post_admission_policy_receipt_sha256,
        receipt.receipts.post_admission_batch_receipt_sha256,
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
    let mut malformed = receipt.clone();
    malformed.scorer_rows.pop();
    let error = malformed.scientific_projection().unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error.message.contains("scorer=63"));
    let mut swapped = receipt.clone();
    swapped.scorer_rows.swap(0, 1);
    let error = swapped.scientific_projection().unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error.message.contains("not aligned at slot 0"));
    let mut cross_wired = receipt.clone();
    cross_wired.scorer_rows[0].status ^= 1;
    let error = cross_wired.scientific_projection().unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error
        .message
        .contains("mirrored evidence changed at slot 0"));
    let mut swapped_moves = receipt.clone();
    swapped_moves.torsion_moves.swap(0, 1);
    let error = swapped_moves.scientific_projection().unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error
        .message
        .contains("torsion moves are not index-aligned"));
    let mut changed_scorer_terms = receipt.clone();
    changed_scorer_terms.scorer_rows[0].weighted_terms[0] += 0.25;
    let error = changed_scorer_terms.scientific_projection().unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error
        .message
        .contains("component evidence changed at slot 0"));
    let mut changed_producer_coordinate = receipt.clone();
    changed_producer_coordinate.producer_coordinates.x_angstrom[0] += 0.25;
    let error = changed_producer_coordinate
        .scientific_projection()
        .unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error
        .message
        .contains("coordinate identity changed at slot 0"));
    let mut changed_geometric_measurement = receipt.clone();
    changed_geometric_measurement.producer_rows[0]
        .geometric
        .raw_minimum_distance_angstrom += 0.25;
    let error = changed_geometric_measurement
        .scientific_projection()
        .unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error.message.contains("changed after receipt issuance"));
    let mut changed_post_admission_measurement = receipt.clone();
    changed_post_admission_measurement.post_admission_rows[0].raw_minimum_distance_angstrom += 0.25;
    let error = changed_post_admission_measurement
        .scientific_projection()
        .unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error.message.contains("changed after receipt issuance"));
    let mut changed_projection_seal = receipt.clone();
    changed_projection_seal.scientific_projection_sha256[0] ^= 1;
    let error = changed_projection_seal.scientific_projection().unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error.message.contains("changed after receipt issuance"));
    let projection = receipt.scientific_projection().unwrap();
    assert_eq!(projection, repeated.scientific_projection().unwrap());
    assert_eq!(projection.candidate_denominator, 64);
    assert_eq!(projection.receptor_atom_count, 4);
    assert_eq!(projection.ligand_atom_count, 1);
    assert_eq!(projection.candidate_rows.len(), 64);
    assert_eq!(projection.post_admitted_count, receipt.post_admitted_count);
    assert_eq!(projection.post_rejected_count, receipt.post_rejected_count);
    assert_eq!(projection.torsion_moves.len(), 512);
    assert_ne!(projection.decision_sha256, [0; 32]);
    assert_ne!(projection.sha256, [0; 32]);
    assert!(projection.candidate_rows.iter().all(|row| {
        if row.coordinates_available {
            row.placement_receipt_sha256 != [0; 32]
                && row.output_proposal_sha256 != [0; 32]
                && row.output_coordinate_sha256 != [0; 32]
        } else {
            row.output_proposal_sha256 == [0; 32] && row.output_coordinate_sha256 == [0; 32]
        }
    }));
    let reference = Fixed64LaneMetricsReference::new(
        "synthetic-single-atom",
        [0x88; 32],
        run.exact_source_evidence.prepared_ligand_topology_sha256,
        PositionSoa::new(&fixture.ligand_x, &fixture.ligand_y, &fixture.ligand_z),
        &fixture.heavy_mask,
        &[vec![0]],
    )
    .unwrap();
    let metrics = Fixed64LaneMetricsReceipt::build(&receipt, reference).unwrap();
    metrics.verify_against(&receipt).unwrap();
    assert_eq!(metrics.candidate_denominator, 64);
    assert_eq!(metrics.observations.len(), 64);
    assert_eq!(metrics.lane_summaries.len(), 10);
    assert_eq!(
        metrics
            .lane_summaries
            .iter()
            .map(|lane| lane.slot_count)
            .sum::<u64>(),
        64
    );
    assert_eq!(
        metrics
            .lane_summaries
            .iter()
            .map(|lane| lane.generated_count + lane.typed_failure_count)
            .sum::<u64>(),
        64
    );
    assert_eq!(
        metrics
            .lane_summaries
            .iter()
            .map(|lane| lane.generated_count)
            .sum::<u64>(),
        receipt.generated_count
    );
    assert_eq!(metrics.rmsd_threshold_angstrom, 2.0);
    assert!(!metrics.result_dependent_allocation_consumed);
    assert!(!metrics.metrics_used_to_change_rank);
    assert!(!metrics.product_execution_authorized);
    assert!(!metrics.public_or_scientific_claim_authorized);
    assert_ne!(metrics.reference.receipt_sha256, [0; 32]);
    assert_ne!(metrics.decision_sha256, [0; 32]);
    assert_ne!(metrics.receipt_sha256, [0; 32]);
    let mut mutated = metrics.clone();
    mutated.observations[0].oracle_2a ^= true;
    let error = mutated.verify_against(&receipt).unwrap_err();
    assert_eq!(error.code, ErrorCode::AbiMismatch);
    assert!(error.message.contains("full pipeline rederivation"));
    drop(pipeline);
    assert_eq!(sibling_receipt, sibling_pipeline.run(run).unwrap());
    (projection, metrics)
}

#[test]
fn safe_run_returns_complete_fixed64_receipt_and_preserves_typed_failures() {
    let fixture = SingleAtomFixture::new();
    let (cpp, cpp_metrics) =
        assert_safe_run_returns_complete_receipt(&fixture, ContextOptions::cpu_reference());
    let (rust, rust_metrics) =
        assert_safe_run_returns_complete_receipt(&fixture, ContextOptions::rust_cpu());
    assert_eq!(cpp.decision_sha256, rust.decision_sha256);
    assert_eq!(cpp.candidate_denominator, rust.candidate_denominator);
    assert_eq!(cpp.primary_slot_indices, rust.primary_slot_indices);
    assert_eq!(cpp.valid_slot_indices, rust.valid_slot_indices);
    assert_eq!(cpp.top_k_slot_indices, rust.top_k_slot_indices);
    assert_eq!(cpp.post_admitted_count, rust.post_admitted_count);
    assert_eq!(cpp.post_rejected_count, rust.post_rejected_count);
    assert_eq!(cpp.scored_count, rust.scored_count);
    assert_eq!(cpp.valid_count, rust.valid_count);
    assert_eq!(
        cpp_metrics.candidate_denominator,
        rust_metrics.candidate_denominator
    );
    assert_eq!(cpp_metrics.decision_sha256, rust_metrics.decision_sha256);
    assert_eq!(cpp_metrics.lane_summaries, rust_metrics.lane_summaries);
    assert_eq!(
        cpp_metrics.oracle_selection.failure_class,
        rust_metrics.oracle_selection.failure_class
    );
    assert_eq!(
        cpp_metrics.oracle_selection.proposal_oracle_success,
        rust_metrics.oracle_selection.proposal_oracle_success
    );
    assert_eq!(
        cpp_metrics.oracle_selection.valid_proposal_oracle_success,
        rust_metrics.oracle_selection.valid_proposal_oracle_success
    );
    assert_eq!(
        cpp_metrics.conformer_orientation_interaction,
        rust_metrics.conformer_orientation_interaction
    );
    for (cpp_row, rust_row) in cpp_metrics
        .observations
        .iter()
        .zip(&rust_metrics.observations)
    {
        assert_eq!(cpp_row.slot_index, rust_row.slot_index);
        assert_eq!(cpp_row.lane, rust_row.lane);
        assert_eq!(cpp_row.coordinate_ready, rust_row.coordinate_ready);
        assert_eq!(cpp_row.exact_valid, rust_row.exact_valid);
        assert_eq!(cpp_row.oracle_2a, rust_row.oracle_2a);
        assert_eq!(cpp_row.valid_oracle_2a, rust_row.valid_oracle_2a);
        if cpp_row.rmsd_evaluated {
            assert_numeric_parity(
                cpp_row.symmetry_aware_direct_heavy_atom_rmsd_angstrom,
                rust_row.symmetry_aware_direct_heavy_atom_rmsd_angstrom,
            );
        }
    }
    for (cpp_row, rust_row) in cpp.candidate_rows.iter().zip(&rust.candidate_rows) {
        assert_eq!(cpp_row.slot_index, rust_row.slot_index);
        assert_eq!(
            cpp_row.post_admission.status,
            rust_row.post_admission.status
        );
        assert_eq!(
            cpp_row.post_admission.failure_code,
            rust_row.post_admission.failure_code
        );
        assert_eq!(
            cpp_row.post_admission.decision,
            rust_row.post_admission.decision
        );
        assert_eq!(
            cpp_row.post_admission.rank_eligible,
            rust_row.post_admission.rank_eligible
        );
        assert_eq!(
            cpp_row.post_admission.exact_pair_count,
            rust_row.post_admission.exact_pair_count
        );
        assert_eq!(
            cpp_row.post_admission.penetration_pair_count,
            rust_row.post_admission.penetration_pair_count
        );
        assert_numeric_parity(
            cpp_row.post_admission.raw_minimum_distance_angstrom,
            rust_row.post_admission.raw_minimum_distance_angstrom,
        );
        assert_numeric_parity(
            cpp_row.post_admission.minimum_vdw_surface_gap_angstrom,
            rust_row.post_admission.minimum_vdw_surface_gap_angstrom,
        );
        assert_numeric_parity(
            cpp_row.post_admission.minimum_vdw_ratio,
            rust_row.post_admission.minimum_vdw_ratio,
        );
        for (cpp_term, rust_term) in cpp_row
            .scorer
            .weighted_terms
            .iter()
            .zip(rust_row.scorer.weighted_terms)
        {
            assert_numeric_parity(*cpp_term, rust_term);
        }
        assert_numeric_parity(cpp_row.scorer.total_score, rust_row.scorer.total_score);
        assert_eq!(cpp_row.validity.status, rust_row.validity.status);
        assert_eq!(
            cpp_row.validity.failure_code,
            rust_row.validity.failure_code
        );
        assert_eq!(
            cpp_row.validity.passed_check_mask,
            rust_row.validity.passed_check_mask
        );
        assert_eq!(
            cpp_row.validity.blocker_mask,
            rust_row.validity.blocker_mask
        );
        assert_eq!(cpp_row.ranking.stable_rank, rust_row.ranking.stable_rank);
        assert_eq!(
            cpp_row.ranking.stable_valid_rank,
            rust_row.ranking.stable_valid_rank
        );
    }
}

#[test]
fn preselected_fixed64_composition_preserves_payloads_and_rederives_receipts() {
    let fixture = TwoAtomFixture::new();
    let preselected = preselected_funnel_fixture();
    let candidate_modes: [Fixed64RefinementMode; 64] = std::array::from_fn(|slot| {
        if slot % 2 == 0 {
            Fixed64RefinementMode::V2Translation
        } else {
            Fixed64RefinementMode::V6BaselineV2Lane
        }
    });
    let rigid_steps = [4_u64; 64];
    let torsion_eligible = [0_u8; 64];
    let torsion_steps = [0_u64; 64];
    let baseline_angles = [0.0_f64; 128];
    let input = Fixed64PreselectedRunInput {
        preselected: &preselected,
        rmsd_threshold_angstrom: 1.5,
        candidate_modes: &candidate_modes,
        rigid_max_steps: &rigid_steps,
        proposal_is_torsion_eligible: &torsion_eligible,
        torsion_max_steps: &torsion_steps,
        baseline_torsion_angles_radians: &baseline_angles,
        predeclared_refinement_policy_sha256: [0x76; 32],
        predeclared_post_refinement_admission_policy_sha256: [0x77; 32],
    };

    let mut receipts = Vec::new();
    for options in [ContextOptions::cpu_reference(), ContextOptions::rust_cpu()] {
        let context = Context::new(options).unwrap();
        let pipeline = Fixed64Pipeline::new(&context, fixture.scientific_context()).unwrap();
        let receipt = pipeline.run_preselected(input).unwrap();
        assert_eq!(receipt, pipeline.run_preselected(input).unwrap());
        assert!(receipt.has_valid_receipt());
        assert_eq!(receipt.backend, options.backend);
        assert_eq!(receipt.ligand_atom_count, 2);
        assert_eq!(receipt.selected_count, 56);
        assert_eq!(receipt.lane_shortfall_count, 8);
        assert!(receipt.refined_count > 0);
        assert!(receipt.rows.iter().any(|row| {
            row.requested_refinement_mode
                == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
                && row.refinement.coordinate_available
        }));
        assert_eq!(receipt.rows.len(), 64);
        assert_eq!(receipt.torsion_moves.len(), 512);
        assert_eq!(
            receipt.source_coordinates.x_angstrom,
            preselected.x_angstrom()
        );
        assert_eq!(
            receipt.source_coordinates.y_angstrom,
            preselected.y_angstrom()
        );
        assert_eq!(
            receipt.source_coordinates.z_angstrom,
            preselected.z_angstrom()
        );
        assert_eq!(
            receipt.source_quaternions[0],
            preselected.source_quaternion_x()
        );
        assert_eq!(
            receipt.source_quaternions[1],
            preselected.source_quaternion_y()
        );
        assert_eq!(
            receipt.source_quaternions[2],
            preselected.source_quaternion_z()
        );
        assert_eq!(
            receipt.source_quaternions[3],
            preselected.source_quaternion_w()
        );
        assert_eq!(
            receipt.post_admitted_count + receipt.post_rejected_count,
            receipt.refined_count
        );
        assert!(receipt.scored_count <= receipt.post_admitted_count);
        assert!(receipt.valid_count <= receipt.scored_count);
        assert!(receipt.authority.denominator_preserved);
        assert!(!receipt.authority.molecular_execution_authorized);
        assert!(!receipt.authority.reservation_authorized);
        assert!(!receipt.authority.benchmark_execution_authorized);
        assert!(!receipt.authority.production_claim_authorized);
        assert!(!receipt.molecular_execution_authorized());
        assert!(!receipt.benchmark_claim_authorized());
        assert!(!receipt.product_authorized());
        assert!(!receipt.scientific_claim_authorized());
        assert!(receipt
            .rows
            .iter()
            .all(|row| row.row_receipt_sha256 != [0; 32]));
        for slot in 56..64 {
            assert_eq!(receipt.rows[slot].effective_refinement_mode, 0);
            assert_eq!(receipt.source_quaternions[3][slot], 0.0);
            assert!(!receipt.initial_admission_rows[slot].rank_eligible);
        }
        let mut changed_coordinate = receipt.clone();
        changed_coordinate.source_coordinates.x_angstrom[0] += 0.25;
        assert!(!changed_coordinate.has_valid_receipt());
        let mut changed_evidence = receipt.clone();
        changed_evidence.scorer_rows[0].total_score += 0.25;
        assert!(!changed_evidence.has_valid_receipt());
        let mut changed_torsion_move = receipt.clone();
        changed_torsion_move.torsion_moves[0].delta_radians += 0.25;
        assert!(!changed_torsion_move.has_valid_receipt());
        let mut absent_policy = input;
        absent_policy.predeclared_refinement_policy_sha256 = [0; 32];
        let error = pipeline.run_preselected(absent_policy).unwrap_err();
        assert_eq!(error.code, ErrorCode::InvalidArgument);
        receipts.push(receipt);
    }

    assert_eq!(
        receipts[0].primary_slot_indices,
        receipts[1].primary_slot_indices
    );
    assert_eq!(
        receipts[0].valid_slot_indices,
        receipts[1].valid_slot_indices
    );
    assert_eq!(
        receipts[0].representative_slot_indices,
        receipts[1].representative_slot_indices
    );
    assert_eq!(
        receipts[0].top_k_slot_indices,
        receipts[1].top_k_slot_indices
    );
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
        predeclared_post_refinement_admission_policy_sha256: [0x77; 32],
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
            pocket_normal: [3.0, 3.0, 15.0],
            ..run
        })
        .unwrap();
    let rounded_oblique = pipeline
        .run(Fixed64RunInput {
            pocket_normal: [0.3, 0.3, 1.5],
            ..run
        })
        .unwrap();
    assert_eq!(oblique, scaled_oblique);
    assert_eq!(oblique, rounded_oblique);
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

#[test]
fn indexed_so3_out_of_envelope_output_remains_a_typed_failure() {
    let mut fixture = TwoAtomFixture::new();
    fixture.ligand_x = [-100_000.0, 100_000.0];
    let exact_source = fixture.source(0x10);
    let candidate_modes = [Fixed64RefinementMode::V2Translation; 64];
    let rigid_steps = [0_u64; 64];
    let torsion_eligible = [0_u8; 64];
    let torsion_steps = [0_u64; 64];
    let baseline_angles = [0.0_f64; 128];
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
        atomic_features: &[],
        v7_control_sources: &[],
        conformer_sources: &[],
        retained_sources: &[],
        feature_geometries: &[],
        feature_geometry_inventory_sha256: [0; 32],
        pocket_normal: [1.0, 1.0, 5.0],
        rmsd_threshold_angstrom: 1.5,
        candidate_modes: &candidate_modes,
        rigid_max_steps: &rigid_steps,
        proposal_is_torsion_eligible: &torsion_eligible,
        torsion_max_steps: &torsion_steps,
        baseline_torsion_angles_radians: &baseline_angles,
        predeclared_refinement_policy_sha256: [0x76; 32],
        predeclared_post_refinement_admission_policy_sha256: [0x77; 32],
    };
    #[cfg(not(feature = "hip"))]
    let backends = vec![ContextOptions::cpu_reference(), ContextOptions::rust_cpu()];
    #[cfg(feature = "hip")]
    let backends = {
        let mut values = vec![ContextOptions::cpu_reference(), ContextOptions::rust_cpu()];
        for options in [ContextOptions::hip_safe(0), ContextOptions::hip_fast(0)] {
            if Context::backend_available(options.backend, options.device_ordinal).unwrap() {
                values.push(options);
            }
        }
        values
    };
    for options in backends {
        let context = Context::new(options).unwrap();
        let pipeline =
            Fixed64Pipeline::new(&context, fixture.scientific_context_at([100_000.0; 3])).unwrap();
        let receipt = pipeline.run(run).unwrap();
        assert!(receipt.producer_rows[24..36].iter().all(|row| {
            row.status != 0
                && row.failure_code == 5
                && row.component_failure_code == 2
                && !row.coordinates_available
                && row.placement_receipt_sha256 != [0; 32]
                && row.output_coordinate_sha256 == [0; 32]
        }));
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
        let _ = assert_safe_run_returns_complete_receipt(&fixture, options);
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
