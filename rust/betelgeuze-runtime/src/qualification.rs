//! Claim-blocked synthetic qualification probes for the complete fixed64 graph.
//!
//! The probes in this module never read molecular corpora, reserve an external
//! run, or grant qualification/product authority.  A separately sealed runner
//! may consume one predeclared profile around this native measurement core.

use std::hint::black_box;
use std::time::Instant;

use betelgeuze_docking_search::{
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, Fixed64FeatureGeometry as IndependentFeatureGeometry,
    Fixed64FeatureGeometryInventory as IndependentFeatureGeometryInventory,
    Fixed64FeatureKind as IndependentFeatureKind, Vec3,
};

use crate::{
    Backend, Context, ContextOptions, Error, ErrorCode, Fixed64AtomicFeature,
    Fixed64ConformerCoordinateSource, Fixed64CoordinateSource, Fixed64Donor,
    Fixed64ExactSourceEvidence, Fixed64FeatureGeometry, Fixed64FeatureKind, Fixed64Identities,
    Fixed64IndexedCoordinateSource, Fixed64Ligand, Fixed64Pair, Fixed64Pipeline,
    Fixed64PipelineContext, Fixed64Receptor, Fixed64RefinementMode, Fixed64RigidProfileEvidence,
    Fixed64Rotor, Fixed64RunInput, Fixed64ScientificProjection, Fixed64SourceEvidence, PositionSoa,
    Result,
};

pub const FIXED64_CPU_QUALIFICATION_V4_PROFILE_ID: &str =
    "engine_v2_native_fixed64_cpu_synthetic_v4";
pub const FIXED64_CPU_QUALIFICATION_V4_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_cpu_probe/4.0.0";

const SLOT_COUNT: usize = 64;
const LIGAND_ATOM_COUNT: usize = 12;
const FEATURE_COUNT: usize = 12;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64CpuProbeConfigV4 {
    pub warmup_rounds: u32,
    pub sample_rounds: u32,
    pub absolute_tolerance: f64,
    pub relative_tolerance: f64,
    pub maximum_rust_to_cpp_median_ratio: f64,
}

impl Fixed64CpuProbeConfigV4 {
    #[must_use]
    pub const fn qualification_profile() -> Self {
        Self {
            warmup_rounds: 5,
            sample_rounds: 25,
            absolute_tolerance: 1.0e-11,
            relative_tolerance: 4.0e-12,
            maximum_rust_to_cpp_median_ratio: 1.25,
        }
    }

    #[must_use]
    pub const fn unit_test() -> Self {
        Self {
            warmup_rounds: 0,
            sample_rounds: 2,
            absolute_tolerance: 1.0e-11,
            relative_tolerance: 4.0e-12,
            maximum_rust_to_cpp_median_ratio: f64::MAX,
        }
    }

    fn validate(self) -> Result<Self> {
        if self.sample_rounds < 2
            || self.sample_rounds > 10_000
            || self.warmup_rounds > 10_000
            || !self.absolute_tolerance.is_finite()
            || self.absolute_tolerance < 0.0
            || !self.relative_tolerance.is_finite()
            || self.relative_tolerance < 0.0
            || !self.maximum_rust_to_cpp_median_ratio.is_finite()
            || self.maximum_rust_to_cpp_median_ratio <= 0.0
        {
            return Err(Error::local(
                ErrorCode::InvalidArgument,
                "fixed64 CPU probe configuration is outside its frozen safety envelope",
            ));
        }
        Ok(self)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64NumericParityV4 {
    pub compared_f64_count: usize,
    pub maximum_absolute_difference: f64,
    pub maximum_scaled_difference: f64,
    pub tolerance_violation_count: usize,
    pub first_violation_index: Option<usize>,
}

impl Fixed64NumericParityV4 {
    #[must_use]
    pub const fn passed(&self) -> bool {
        self.tolerance_violation_count == 0 && self.compared_f64_count != 0
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64CpuFixtureProbeV4 {
    pub fixture_id: &'static str,
    pub candidate_denominator: usize,
    pub receptor_atom_count: usize,
    pub ligand_atom_count: usize,
    pub generated_count: u64,
    pub typed_failure_count: u64,
    pub cpp_decision_sha256: [u8; 32],
    pub rust_decision_sha256: [u8; 32],
    pub cpp_projection_sha256: [u8; 32],
    pub rust_projection_sha256: [u8; 32],
    pub cpp_repeat_stable: bool,
    pub rust_repeat_stable: bool,
    pub decision_parity: bool,
    pub numeric_parity: Fixed64NumericParityV4,
    pub cpp_sample_nanoseconds: Vec<u64>,
    pub rust_sample_nanoseconds: Vec<u64>,
    pub cpp_median_nanoseconds: u64,
    pub rust_median_nanoseconds: u64,
    pub rust_to_cpp_median_ratio: f64,
    pub persistent_cpp_context_count: u32,
    pub persistent_rust_context_count: u32,
    pub authority_false: bool,
    pub gate_passed: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64CpuProbeReportV4 {
    pub schema_id: &'static str,
    pub profile_id: &'static str,
    pub qualification_authority: bool,
    pub molecular_execution_authorized: bool,
    pub reservation_authorized: bool,
    pub public_benchmark_authorized: bool,
    pub product_performance_claim_authorized: bool,
    pub fixtures: Vec<Fixed64CpuFixtureProbeV4>,
    pub gate_passed: bool,
}

#[derive(Clone, Copy)]
enum FixtureVariant {
    Complete,
    FeatureSparse,
}

impl FixtureVariant {
    const fn id(self) -> &'static str {
        match self {
            Self::Complete => "synthetic_complete_64",
            Self::FeatureSparse => "synthetic_feature_sparse_48_plus_16",
        }
    }

    const fn includes_features(self) -> bool {
        matches!(self, Self::Complete)
    }

    const fn expected_counts(self) -> (u64, u64) {
        match self {
            Self::Complete => (64, 0),
            Self::FeatureSparse => (48, 16),
        }
    }
}

struct SyntheticFixture {
    ligand_x: [f64; LIGAND_ATOM_COUNT],
    ligand_y: [f64; LIGAND_ATOM_COUNT],
    ligand_z: [f64; LIGAND_ATOM_COUNT],
    receptor_x: [f64; LIGAND_ATOM_COUNT],
    receptor_y: [f64; LIGAND_ATOM_COUNT],
    receptor_z: [f64; LIGAND_ATOM_COUNT],
    ligand_radii: [f64; LIGAND_ATOM_COUNT],
    receptor_radii: [f64; LIGAND_ATOM_COUNT],
    heavy_mask: [u8; LIGAND_ATOM_COUNT],
    receptor_charge: [f64; LIGAND_ATOM_COUNT],
    receptor_epsilon: [f64; LIGAND_ATOM_COUNT],
    receptor_hydrophobic: [u8; LIGAND_ATOM_COUNT],
    receptor_acceptor: [u8; LIGAND_ATOM_COUNT],
    ligand_charge: [f64; LIGAND_ATOM_COUNT],
    ligand_epsilon: [f64; LIGAND_ATOM_COUNT],
    ligand_hydrophobic: [u8; LIGAND_ATOM_COUNT],
    ligand_acceptor: [u8; LIGAND_ATOM_COUNT],
    receptor_donors: [Fixed64Donor; 1],
    ligand_donors: [Fixed64Donor; 1],
    bonds: [Fixed64Pair; 3],
    exclusions: [Fixed64Pair; 3],
    rotors: [Fixed64Rotor; 1],
    parent: [i32; LIGAND_ATOM_COUNT],
    rotatable_children: [u64; 1],
    internal_pairs: [Fixed64Pair; 3],
}

impl SyntheticFixture {
    fn new() -> Self {
        let dominant = 1.0 / 2.0_f64.sqrt();
        let ligand_scale = (1.1_f64 / 2.0).sqrt();
        let receptor_scale = (1.2_f64 / 2.0).sqrt();
        let secondary_scale = (1.0_f64 / 2.0).sqrt();
        Self {
            ligand_x: [
                0.0,
                1.0,
                2.0,
                0.0,
                0.0,
                -1.0,
                1.0,
                0.0,
                ligand_scale * dominant,
                -ligand_scale * dominant,
                0.0,
                0.0,
            ],
            ligand_y: [
                0.0,
                0.0,
                0.0,
                1.0,
                -1.0,
                -1.0,
                -1.0,
                1.0,
                ligand_scale * dominant,
                -ligand_scale * dominant,
                0.0,
                0.0,
            ],
            ligand_z: [
                0.0,
                0.0,
                0.0,
                0.0,
                0.5,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                secondary_scale,
                -secondary_scale,
            ],
            receptor_x: [
                0.0,
                0.0,
                0.2,
                -0.2,
                0.2,
                -1.0,
                1.0,
                0.0,
                receptor_scale * dominant,
                -receptor_scale * dominant,
                0.0,
                0.0,
            ],
            receptor_y: [
                0.0,
                0.0,
                0.1,
                0.0,
                0.0,
                -1.0,
                -1.0,
                1.0,
                receptor_scale * dominant,
                -receptor_scale * dominant,
                0.0,
                0.0,
            ],
            receptor_z: [
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                secondary_scale,
                -secondary_scale,
            ],
            ligand_radii: [1.2; LIGAND_ATOM_COUNT],
            receptor_radii: [1.2; LIGAND_ATOM_COUNT],
            heavy_mask: [1; LIGAND_ATOM_COUNT],
            receptor_charge: [
                -0.5, 0.2, 0.3, 0.0, 0.1, -0.1, 0.0, 0.0, 0.2, -0.2, 0.1, -0.1,
            ],
            receptor_epsilon: [0.2; LIGAND_ATOM_COUNT],
            receptor_hydrophobic: [0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0],
            receptor_acceptor: [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ligand_charge: [
                0.2, 0.25, -0.45, 0.0, 0.1, -0.1, 0.0, 0.0, 0.2, -0.2, 0.1, -0.1,
            ],
            ligand_epsilon: [0.2; LIGAND_ATOM_COUNT],
            ligand_hydrophobic: [0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0],
            ligand_acceptor: [0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
            receptor_donors: [Fixed64Donor {
                donor_atom_index: 0,
                hydrogen_atom_index: 1,
            }],
            ligand_donors: [Fixed64Donor {
                donor_atom_index: 0,
                hydrogen_atom_index: 1,
            }],
            bonds: [
                Fixed64Pair {
                    atom_i: 0,
                    atom_j: 1,
                },
                Fixed64Pair {
                    atom_i: 1,
                    atom_j: 2,
                },
                Fixed64Pair {
                    atom_i: 2,
                    atom_j: 3,
                },
            ],
            exclusions: [
                Fixed64Pair {
                    atom_i: 0,
                    atom_j: 1,
                },
                Fixed64Pair {
                    atom_i: 1,
                    atom_j: 2,
                },
                Fixed64Pair {
                    atom_i: 2,
                    atom_j: 3,
                },
            ],
            rotors: [Fixed64Rotor {
                atom_i: 0,
                atom_j: 1,
                atom_k: 3,
                atom_l: 4,
            }],
            parent: [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            rotatable_children: [2],
            internal_pairs: [
                Fixed64Pair {
                    atom_i: 0,
                    atom_j: 2,
                },
                Fixed64Pair {
                    atom_i: 0,
                    atom_j: 3,
                },
                Fixed64Pair {
                    atom_i: 1,
                    atom_j: 3,
                },
            ],
        }
    }

    fn ligand_coordinates(&self) -> PositionSoa<'_> {
        PositionSoa::new(&self.ligand_x, &self.ligand_y, &self.ligand_z)
    }

    fn receptor_coordinates(&self) -> PositionSoa<'_> {
        PositionSoa::new(&self.receptor_x, &self.receptor_y, &self.receptor_z)
    }

    fn scientific_context(&self) -> Fixed64PipelineContext<'_> {
        Fixed64PipelineContext {
            receptor: Fixed64Receptor {
                coordinates: self.receptor_coordinates(),
                vdw_radius_angstrom: &self.receptor_radii,
                charge_elementary: &self.receptor_charge,
                epsilon_kcal_per_mol: &self.receptor_epsilon,
                hydrophobic_mask: &self.receptor_hydrophobic,
                acceptor_mask: &self.receptor_acceptor,
                donors: &self.receptor_donors,
            },
            ligand: Fixed64Ligand {
                reference_coordinates: self.ligand_coordinates(),
                vdw_radius_angstrom: &self.ligand_radii,
                heavy_atom_mask: &self.heavy_mask,
                charge_elementary: &self.ligand_charge,
                epsilon_kcal_per_mol: &self.ligand_epsilon,
                hydrophobic_mask: &self.ligand_hydrophobic,
                acceptor_mask: &self.ligand_acceptor,
                donors: &self.ligand_donors,
                exclusions: &self.exclusions,
                rotors: &self.rotors,
                bonds: &self.bonds,
                chirality_centers: &[],
                parent_atom_index: &self.parent,
                rotatable_child_atom_index: &self.rotatable_children,
                internal_pairs: &self.internal_pairs,
            },
            pocket_center_angstrom: [0.0, 0.0, 5.0],
            pocket_radius_angstrom: 20.0,
            identities: Fixed64Identities {
                authority_input_receipt_sha256: [0x70; 32],
                receptor_system_sha256: [0x71; 32],
                ligand_system_sha256: [0x72; 32],
                backend_receipt_sha256: [0x73; 32],
                validity_scorer_context_receipt_sha256: [0x74; 32],
                contact_policy_sha256: [0x75; 32],
            },
        }
    }

    fn source(&self, marker: u8) -> Result<Fixed64CoordinateSource<'_>> {
        Ok(Fixed64CoordinateSource {
            evidence: Fixed64SourceEvidence {
                receipt_sha256: [marker; 32],
                proposal_sha256: [marker.wrapping_add(64); 32],
                coordinate_sha256: self.ligand_coordinate_sha256()?,
            },
            coordinates: self.ligand_coordinates(),
        })
    }

    fn ligand_coordinate_sha256(&self) -> Result<[u8; 32]> {
        search_result(native_fixed64_coordinate_sha256(
            &self
                .ligand_x
                .iter()
                .zip(self.ligand_y)
                .zip(self.ligand_z)
                .map(|((x, y), z)| Vec3::new(*x, y, z))
                .collect::<Vec<_>>(),
        ))
    }

    fn receptor_coordinate_sha256(&self) -> Result<[u8; 32]> {
        search_result(native_fixed64_coordinate_sha256(
            &self
                .receptor_x
                .iter()
                .zip(self.receptor_y)
                .zip(self.receptor_z)
                .map(|((x, y), z)| Vec3::new(*x, y, z))
                .collect::<Vec<_>>(),
        ))
    }
}

fn search_result<T, E: std::fmt::Display>(value: std::result::Result<T, E>) -> Result<T> {
    value.map_err(|error| Error::local(ErrorCode::InvalidArgument, error.to_string()))
}

const FEATURE_KINDS: [Fixed64FeatureKind; FEATURE_COUNT] = [
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

fn independent_kind(value: Fixed64FeatureKind) -> IndependentFeatureKind {
    match value {
        Fixed64FeatureKind::LigandDonor => IndependentFeatureKind::LigandDonor,
        Fixed64FeatureKind::LigandAcceptor => IndependentFeatureKind::LigandAcceptor,
        Fixed64FeatureKind::ReceptorDonor => IndependentFeatureKind::ReceptorDonor,
        Fixed64FeatureKind::ReceptorAcceptor => IndependentFeatureKind::ReceptorAcceptor,
        Fixed64FeatureKind::LigandPositiveSite => IndependentFeatureKind::LigandPositiveSite,
        Fixed64FeatureKind::LigandNegativeSite => IndependentFeatureKind::LigandNegativeSite,
        Fixed64FeatureKind::ReceptorPositiveSite => IndependentFeatureKind::ReceptorPositiveSite,
        Fixed64FeatureKind::ReceptorNegativeSite => IndependentFeatureKind::ReceptorNegativeSite,
        Fixed64FeatureKind::LigandAromaticPlane => IndependentFeatureKind::LigandAromaticPlane,
        Fixed64FeatureKind::ReceptorAromaticPlane => IndependentFeatureKind::ReceptorAromaticPlane,
        Fixed64FeatureKind::LigandShapeAxis => IndependentFeatureKind::LigandShapeAxis,
        Fixed64FeatureKind::PocketShapeAxis => IndependentFeatureKind::PocketShapeAxis,
    }
}

fn feature_indices() -> [Vec<u64>; FEATURE_COUNT] {
    [
        vec![0, 1],
        vec![2],
        vec![0, 1],
        vec![2],
        vec![3],
        vec![4],
        vec![4],
        vec![3],
        vec![5, 6, 7],
        vec![5, 6, 7],
        vec![8, 9, 10, 11],
        vec![8, 9, 10, 11],
    ]
}

fn authority_is_false(value: &Fixed64ScientificProjection) -> bool {
    let authority = value.authority;
    !authority.result_dependent_input_consumed
        && !authority.fallback_allowed
        && !authority.multi_anchor_consumed
        && authority.denominator_preserved
        && !authority.molecular_execution_authorized
        && !authority.reservation_authorized
        && !authority.benchmark_execution_authorized
        && !authority.existing_rank_auto_change_authorized
        && !authority.customer_pose_emission_authorized
        && !authority.production_claim_authorized
        && !authority.scientific_claim_authorized
}

fn median(values: &[u64]) -> u64 {
    let mut sorted = values.to_vec();
    sorted.sort_unstable();
    let middle = sorted.len() / 2;
    if sorted.len() % 2 == 0 {
        sorted[middle - 1] / 2
            + sorted[middle] / 2
            + (sorted[middle - 1] % 2 + sorted[middle] % 2) / 2
    } else {
        sorted[middle]
    }
}

fn append_rigid_profile(values: &mut Vec<f64>, profile: Fixed64RigidProfileEvidence) {
    values.extend([profile.initial_penalty, profile.final_penalty]);
    values.extend(profile.total_translation_angstrom);
    values.extend(profile.total_rotation_vector_radians);
    values.extend([
        profile.total_rotation_path_radians,
        profile.initial_centroid_offset_angstrom,
        profile.final_centroid_offset_angstrom,
        profile.maximum_centroid_offset_angstrom,
    ]);
}

fn append_positions(values: &mut Vec<f64>, positions: &crate::PositionSoaOwned) {
    values.extend(&positions.x_angstrom);
    values.extend(&positions.y_angstrom);
    values.extend(&positions.z_angstrom);
}

fn numeric_projection(value: &Fixed64ScientificProjection) -> Vec<f64> {
    let mut numbers = Vec::new();
    for row in &value.candidate_rows {
        numbers.extend(row.placement_quaternion);
        numbers.extend([
            row.raw_minimum_distance_angstrom,
            row.minimum_vdw_surface_gap_angstrom,
            row.minimum_vdw_ratio,
            row.sphere_overlap_proxy_angstrom3,
            row.pocket_escape_angstrom,
        ]);
        for profile in [
            row.rigid.selected,
            row.rigid.comparison_v2,
            row.rigid.baseline_v3,
            row.rigid.clearance_v4,
        ] {
            append_rigid_profile(&mut numbers, profile);
        }
        numbers.extend([
            row.torsion.source_receptor_penalty,
            row.torsion.source_internal_penalty,
            row.torsion.source_combined_penalty,
            row.torsion.baseline_receptor_penalty,
            row.torsion.baseline_internal_penalty,
            row.torsion.baseline_combined_penalty,
            row.torsion.optimized_receptor_penalty,
            row.torsion.optimized_internal_penalty,
            row.torsion.optimized_combined_penalty,
            row.torsion.final_receptor_penalty,
            row.torsion.final_internal_penalty,
            row.torsion.final_combined_penalty,
            row.torsion.evaluated_total_torsion_path_radians,
            row.torsion.accepted_total_torsion_path_radians,
        ]);
        numbers.extend(row.scorer.weighted_terms);
        numbers.push(row.scorer.total_score);
        numbers.extend([
            row.validity.rotation_orthogonality_max_error,
            row.validity.rotation_determinant,
            row.validity.max_bond_length_delta_angstrom,
            row.validity.minimum_ligand_nonbonded_distance_angstrom,
            row.validity.minimum_receptor_ligand_distance_angstrom,
            row.validity.minimum_declared_chiral_volume,
            row.validity.maximum_pocket_center_distance_angstrom,
            row.validity.element_vdw_ligand_minimum_distance_angstrom,
            row.validity.element_vdw_ligand_minimum_ratio,
            row.validity.element_vdw_receptor_minimum_distance_angstrom,
            row.validity.element_vdw_receptor_minimum_ratio,
            row.ranking.total_score,
            row.cluster.direct_rmsd_to_representative_angstrom,
        ]);
    }
    for movement in &value.torsion_moves {
        numbers.extend([
            movement.delta_radians,
            movement.receptor_penalty,
            movement.internal_penalty,
            movement.combined_penalty,
        ]);
    }
    append_positions(&mut numbers, &value.producer_coordinates);
    for positions in [
        &value.rigid_coordinates.selected,
        &value.rigid_coordinates.comparison_v2,
        &value.rigid_coordinates.baseline_v3,
        &value.rigid_coordinates.clearance_v4,
        &value.torsion_coordinates.optimized,
        &value.torsion_coordinates.final_state,
        &value.final_coordinates,
    ] {
        append_positions(&mut numbers, positions);
    }
    numbers.extend(&value.torsion_coordinates.optimized_torsion_angles_radians);
    numbers.extend(&value.torsion_coordinates.final_torsion_angles_radians);
    for channel in &value.final_quaternions {
        numbers.extend(channel);
    }
    numbers
}

fn numeric_parity(
    reference: &Fixed64ScientificProjection,
    observed: &Fixed64ScientificProjection,
    absolute_tolerance: f64,
    relative_tolerance: f64,
) -> Fixed64NumericParityV4 {
    let reference = numeric_projection(reference);
    let observed = numeric_projection(observed);
    let mut result = Fixed64NumericParityV4 {
        compared_f64_count: reference.len().min(observed.len()),
        maximum_absolute_difference: 0.0,
        maximum_scaled_difference: 0.0,
        tolerance_violation_count: reference.len().abs_diff(observed.len()),
        first_violation_index: (reference.len() != observed.len()).then_some(0),
    };
    for (index, (left, right)) in reference.iter().zip(&observed).enumerate() {
        let difference = (*left - *right).abs();
        let scale = left.abs().max(right.abs());
        let allowed = absolute_tolerance + relative_tolerance * scale;
        let scaled = if scale == 0.0 {
            difference
        } else {
            difference / scale
        };
        if difference.is_finite() {
            result.maximum_absolute_difference = result.maximum_absolute_difference.max(difference);
            result.maximum_scaled_difference = result.maximum_scaled_difference.max(scaled);
        }
        if !left.is_finite() || !right.is_finite() || difference > allowed {
            result.tolerance_violation_count += 1;
            if result.first_violation_index.is_none() {
                result.first_violation_index = Some(index);
            }
        }
    }
    result
}

fn timed_run(
    pipeline: &Fixed64Pipeline<'_>,
    input: Fixed64RunInput<'_>,
) -> Result<(u64, Fixed64ScientificProjection)> {
    let started = Instant::now();
    let receipt = pipeline.run(input)?;
    let elapsed = u64::try_from(started.elapsed().as_nanos()).map_err(|_| {
        Error::local(
            ErrorCode::CapacityOverflow,
            "fixed64 CPU probe duration exceeded uint64 nanoseconds",
        )
    })?;
    let projection = receipt.scientific_projection()?;
    black_box(projection.sha256);
    Ok((elapsed, projection))
}

fn run_fixture(
    fixture: &SyntheticFixture,
    variant: FixtureVariant,
    config: Fixed64CpuProbeConfigV4,
) -> Result<Fixed64CpuFixtureProbeV4> {
    let exact = fixture.source(0x10)?;
    let v7 = (0_u8..24)
        .map(|index| {
            Ok(Fixed64IndexedCoordinateSource {
                source_index: u32::from(index),
                source: fixture.source(index + 1)?,
            })
        })
        .collect::<Result<Vec<_>>>()?;
    let conformers = (0_u8..7)
        .map(|index| {
            Ok(Fixed64ConformerCoordinateSource {
                rank: index + 2,
                source: fixture.source(34 + index)?,
            })
        })
        .collect::<Result<Vec<_>>>()?;
    let retained = [36_u32, 45, 54, 63]
        .iter()
        .enumerate()
        .map(|(offset, source_index)| {
            Ok(Fixed64IndexedCoordinateSource {
                source_index: *source_index,
                source: fixture.source(48 + u8::try_from(offset).unwrap())?,
            })
        })
        .collect::<Result<Vec<_>>>()?;
    let indices = feature_indices();
    let independent_features = FEATURE_KINDS
        .iter()
        .enumerate()
        .map(|(index, kind)| {
            search_result(IndependentFeatureGeometry::new(
                independent_kind(*kind),
                [0x40 + u8::try_from(index).unwrap(); 32],
                indices[index]
                    .iter()
                    .map(|value| usize::try_from(*value).unwrap())
                    .collect(),
            ))
        })
        .collect::<Result<Vec<_>>>()?;
    let independent_inventory = search_result(IndependentFeatureGeometryInventory::new(
        independent_features.clone(),
    ))?;
    let atomic_features = if variant.includes_features() {
        FEATURE_KINDS
            .iter()
            .enumerate()
            .map(|(index, kind)| Fixed64AtomicFeature {
                kind: *kind,
                receipt_sha256: [0x40 + u8::try_from(index).unwrap(); 32],
            })
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };
    let feature_geometries = if variant.includes_features() {
        FEATURE_KINDS
            .iter()
            .enumerate()
            .map(|(index, kind)| Fixed64FeatureGeometry {
                kind: *kind,
                allocation_feature_receipt_sha256: [0x40 + u8::try_from(index).unwrap(); 32],
                atom_indices: &indices[index],
                feature_geometry_receipt_sha256: independent_features[index].receipt_sha256(),
            })
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };
    let feature_inventory_sha256 = if variant.includes_features() {
        independent_inventory.receipt_sha256()
    } else {
        [0; 32]
    };
    let ligand_radii_sha256 = search_result(native_fixed64_radii_sha256(&fixture.ligand_radii))?;
    let receptor_radii_sha256 =
        search_result(native_fixed64_radii_sha256(&fixture.receptor_radii))?;
    let heavy = fixture
        .heavy_mask
        .iter()
        .map(|value| *value != 0)
        .collect::<Vec<_>>();
    let heavy_sha256 = search_result(native_fixed64_heavy_atom_mask_sha256(&heavy))?;
    let exact_evidence = Fixed64ExactSourceEvidence {
        source_receipt_sha256: exact.evidence.receipt_sha256,
        proposal_sha256: exact.evidence.proposal_sha256,
        ligand_coordinate_sha256: fixture.ligand_coordinate_sha256()?,
        receptor_coordinate_sha256: fixture.receptor_coordinate_sha256()?,
        prepared_ligand_topology_sha256: [0x72; 32],
        prepared_receptor_topology_sha256: [0x71; 32],
        ligand_vdw_radii_sha256: ligand_radii_sha256,
        ligand_heavy_atom_mask_sha256: heavy_sha256,
        receptor_vdw_radii_sha256: receptor_radii_sha256,
    };
    let candidate_modes: [Fixed64RefinementMode; SLOT_COUNT] =
        std::array::from_fn(|slot| match slot % 4 {
            0 => Fixed64RefinementMode::V2Translation,
            1 => Fixed64RefinementMode::V3TranslationRotation,
            2 => Fixed64RefinementMode::V6BaselineV2Lane,
            _ => Fixed64RefinementMode::V6BaselineV3Lane,
        });
    let rigid_steps = [4_u64; SLOT_COUNT];
    let torsion_eligible: [u8; SLOT_COUNT] = std::array::from_fn(|slot| u8::from(slot % 4 >= 2));
    let torsion_steps: [u64; SLOT_COUNT] =
        std::array::from_fn(|slot| if slot % 4 >= 2 { 4 } else { 0 });
    let baseline_angles = [0.0_f64; SLOT_COUNT * LIGAND_ATOM_COUNT];
    let input = Fixed64RunInput {
        exact_source_evidence: exact_evidence,
        exact_source: exact,
        atomic_features: &atomic_features,
        v7_control_sources: &v7,
        conformer_sources: &conformers,
        retained_sources: &retained,
        feature_geometries: &feature_geometries,
        feature_geometry_inventory_sha256: feature_inventory_sha256,
        pocket_normal: [0.0, 0.0, 1.0],
        rmsd_threshold_angstrom: 1.5,
        candidate_modes: &candidate_modes,
        rigid_max_steps: &rigid_steps,
        proposal_is_torsion_eligible: &torsion_eligible,
        torsion_max_steps: &torsion_steps,
        baseline_torsion_angles_radians: &baseline_angles,
        predeclared_refinement_policy_sha256: [0x76; 32],
    };

    let cpp_context = Context::new(ContextOptions::cpu_reference())?;
    let rust_context = Context::new(ContextOptions::rust_cpu())?;
    let cpp_pipeline = Fixed64Pipeline::new(&cpp_context, fixture.scientific_context())?;
    let rust_pipeline = Fixed64Pipeline::new(&rust_context, fixture.scientific_context())?;
    if cpp_pipeline.backend() != Backend::CppCpuReference
        || rust_pipeline.backend() != Backend::RustCpu
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "fixed64 CPU probe backend identity changed",
        ));
    }
    for round in 0..config.warmup_rounds {
        if round % 2 == 0 {
            black_box(cpp_pipeline.run(input)?);
            black_box(rust_pipeline.run(input)?);
        } else {
            black_box(rust_pipeline.run(input)?);
            black_box(cpp_pipeline.run(input)?);
        }
    }

    let mut cpp_samples = Vec::with_capacity(config.sample_rounds as usize);
    let mut rust_samples = Vec::with_capacity(config.sample_rounds as usize);
    let mut cpp_first: Option<Fixed64ScientificProjection> = None;
    let mut rust_first: Option<Fixed64ScientificProjection> = None;
    let mut cpp_repeat_stable = true;
    let mut rust_repeat_stable = true;
    for round in 0..config.sample_rounds {
        let mut execute = |pipeline: &Fixed64Pipeline<'_>, cpp: bool| -> Result<()> {
            let (duration, projection) = timed_run(pipeline, input)?;
            let (samples, first, repeat_stable) = if cpp {
                (&mut cpp_samples, &mut cpp_first, &mut cpp_repeat_stable)
            } else {
                (&mut rust_samples, &mut rust_first, &mut rust_repeat_stable)
            };
            samples.push(duration);
            if let Some(reference) = first.as_ref() {
                *repeat_stable &= reference.sha256 == projection.sha256;
            } else {
                *first = Some(projection);
            }
            Ok(())
        };
        if round % 2 == 0 {
            execute(&cpp_pipeline, true)?;
            execute(&rust_pipeline, false)?;
        } else {
            execute(&rust_pipeline, false)?;
            execute(&cpp_pipeline, true)?;
        }
    }
    let cpp = cpp_first.ok_or_else(|| {
        Error::local(
            ErrorCode::InternalError,
            "fixed64 CPU probe produced no C++ sample",
        )
    })?;
    let rust = rust_first.ok_or_else(|| {
        Error::local(
            ErrorCode::InternalError,
            "fixed64 CPU probe produced no Rust sample",
        )
    })?;
    let numeric = numeric_parity(
        &cpp,
        &rust,
        config.absolute_tolerance,
        config.relative_tolerance,
    );
    let cpp_median = median(&cpp_samples);
    let rust_median = median(&rust_samples);
    if cpp_median == 0 || rust_median == 0 {
        return Err(Error::local(
            ErrorCode::InternalError,
            "fixed64 CPU probe backend median duration was zero",
        ));
    }
    let ratio = rust_median as f64 / cpp_median as f64;
    if !ratio.is_finite() {
        return Err(Error::local(
            ErrorCode::NumericalError,
            "fixed64 CPU probe produced a non-finite performance ratio",
        ));
    }
    let (expected_generated, expected_failures) = variant.expected_counts();
    let authority_false = authority_is_false(&cpp) && authority_is_false(&rust);
    let decision_parity = cpp.decision_sha256 == rust.decision_sha256;
    let gate_passed = cpp.candidate_denominator == SLOT_COUNT
        && rust.candidate_denominator == SLOT_COUNT
        && cpp.receptor_atom_count == LIGAND_ATOM_COUNT
        && rust.receptor_atom_count == LIGAND_ATOM_COUNT
        && cpp.ligand_atom_count == LIGAND_ATOM_COUNT
        && rust.ligand_atom_count == LIGAND_ATOM_COUNT
        && cpp.generated_count == expected_generated
        && rust.generated_count == expected_generated
        && cpp.typed_failure_count == expected_failures
        && rust.typed_failure_count == expected_failures
        && cpp_repeat_stable
        && rust_repeat_stable
        && decision_parity
        && numeric.passed()
        && authority_false
        && ratio <= config.maximum_rust_to_cpp_median_ratio;
    Ok(Fixed64CpuFixtureProbeV4 {
        fixture_id: variant.id(),
        candidate_denominator: cpp.candidate_denominator,
        receptor_atom_count: cpp.receptor_atom_count,
        ligand_atom_count: cpp.ligand_atom_count,
        generated_count: cpp.generated_count,
        typed_failure_count: cpp.typed_failure_count,
        cpp_decision_sha256: cpp.decision_sha256,
        rust_decision_sha256: rust.decision_sha256,
        cpp_projection_sha256: cpp.sha256,
        rust_projection_sha256: rust.sha256,
        cpp_repeat_stable,
        rust_repeat_stable,
        decision_parity,
        numeric_parity: numeric,
        cpp_sample_nanoseconds: cpp_samples,
        rust_sample_nanoseconds: rust_samples,
        cpp_median_nanoseconds: cpp_median,
        rust_median_nanoseconds: rust_median,
        rust_to_cpp_median_ratio: ratio,
        persistent_cpp_context_count: 1,
        persistent_rust_context_count: 1,
        authority_false,
        gate_passed,
    })
}

/// Run a repeatable, non-consuming, synthetic native CPU probe.
///
/// This function deliberately returns all execution and claim authorities as
/// false.  Calling it does not consume or qualify the sealed v4 profile.
pub fn run_native_fixed64_cpu_probe_v4(
    config: Fixed64CpuProbeConfigV4,
) -> Result<Fixed64CpuProbeReportV4> {
    let config = config.validate()?;
    let fixture = SyntheticFixture::new();
    let fixtures = [FixtureVariant::Complete, FixtureVariant::FeatureSparse]
        .into_iter()
        .map(|variant| run_fixture(&fixture, variant, config))
        .collect::<Result<Vec<_>>>()?;
    let gate_passed = fixtures.iter().all(|fixture| fixture.gate_passed);
    Ok(Fixed64CpuProbeReportV4 {
        schema_id: FIXED64_CPU_QUALIFICATION_V4_SCHEMA_ID,
        profile_id: FIXED64_CPU_QUALIFICATION_V4_PROFILE_ID,
        qualification_authority: false,
        molecular_execution_authorized: false,
        reservation_authorized: false,
        public_benchmark_authorized: false,
        product_performance_claim_authorized: false,
        fixtures,
        gate_passed,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_unbounded_or_single_sample_probe_configuration() {
        let mut config = Fixed64CpuProbeConfigV4::unit_test();
        config.sample_rounds = 1;
        assert!(run_native_fixed64_cpu_probe_v4(config).is_err());
        config.sample_rounds = 2;
        config.maximum_rust_to_cpp_median_ratio = f64::NAN;
        assert!(run_native_fixed64_cpu_probe_v4(config).is_err());
    }

    #[test]
    fn complete_and_sparse_probes_preserve_fixed64_cpu_parity() {
        let report = run_native_fixed64_cpu_probe_v4(Fixed64CpuProbeConfigV4::unit_test())
            .expect("synthetic native fixed64 CPU probe");
        assert_eq!(report.fixtures.len(), 2);
        assert!(report.gate_passed);
        assert!(!report.qualification_authority);
        assert!(!report.molecular_execution_authorized);
        assert!(!report.reservation_authorized);
        assert!(!report.public_benchmark_authorized);
        assert!(!report.product_performance_claim_authorized);
        assert_eq!(report.fixtures[0].generated_count, 64);
        assert_eq!(report.fixtures[0].typed_failure_count, 0);
        assert_eq!(report.fixtures[1].generated_count, 48);
        assert_eq!(report.fixtures[1].typed_failure_count, 16);
        assert!(report.fixtures.iter().all(|fixture| {
            fixture.candidate_denominator == 64
                && fixture.receptor_atom_count == 12
                && fixture.ligand_atom_count == 12
                && fixture.cpp_repeat_stable
                && fixture.rust_repeat_stable
                && fixture.decision_parity
                && fixture.numeric_parity.passed()
                && fixture.authority_false
                && fixture.persistent_cpp_context_count == 1
                && fixture.persistent_rust_context_count == 1
        }));
    }
}
