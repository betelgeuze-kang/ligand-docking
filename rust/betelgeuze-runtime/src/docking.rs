//! Safe ownership for the native fixed64 docking pipeline.
//!
//! The complete native pipeline deep-copies every molecular descriptor during
//! construction. This module builds all component descriptors from one shared
//! scientific context, so safe callers cannot cross-wire admission, refinement,
//! scoring, and validity inputs or reuse the handle with another native context.

use std::collections::HashMap;
use std::ffi::CStr;
use std::marker::PhantomData;
use std::mem::{size_of, MaybeUninit};
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_docking_search::{
    evaluate_fixed64_geometric_metrics, generate_native_fixed64_single_anchor, orientations,
    refine_interaction_aware_rigid_v2, refine_interaction_aware_rigid_v3,
    refine_interaction_aware_rigid_v6, Fixed64Allocation as IndependentFixed64Allocation,
    Fixed64AtomicFeatureEvidence as IndependentFixed64AtomicFeature,
    Fixed64ConformerSourceEvidence as IndependentFixed64ConformerSource,
    Fixed64ExactV11SourceEvidence as IndependentFixed64ExactSource,
    Fixed64FeatureGeometry as IndependentFixed64FeatureGeometry,
    Fixed64FeatureGeometryInventory as IndependentFixed64FeatureGeometryInventory,
    Fixed64FeatureInventory as IndependentFixed64FeatureInventory,
    Fixed64FeatureKind as IndependentFixed64FeatureKind,
    Fixed64GeometricInput as IndependentFixed64GeometricInput,
    Fixed64IndexedSourceEvidence as IndependentFixed64IndexedSource,
    Fixed64PlacementErrorCode as IndependentFixed64PlacementErrorCode,
    Fixed64PlacementSource as IndependentFixed64PlacementSource,
    Fixed64SourceEvidence as IndependentFixed64SourceEvidence,
    NativeFixed64ValidityBackend as IndependentValidityBackend,
    NativeFixed64ValidityChecks as IndependentValidityChecks,
    NativeFixed64ValidityConfig as IndependentValidityConfig,
    NativeFixed64ValidityContext as IndependentValidityContext,
    NativeFixed64ValidityFailureCode as IndependentValidityFailureCode,
    NativeFixed64ValidityKernelOutcome as IndependentValidityOutcome,
    NativeFixed64ValidityMeasurements as IndependentValidityMeasurements,
    NativeRigidRefinementContext as IndependentRigidContext,
    NativeRigidRefinementError as IndependentRigidError,
    NativeRigidRefinementErrorCode as IndependentRigidErrorCode,
    NativeRigidRefinementOutcome as IndependentRigidOutcome,
    NativeRigidRefinementProfile as IndependentRigidProfile,
    NativeRigidV2Config as IndependentRigidV2Config,
    NativeRigidV3Config as IndependentRigidV3Config, NativeScorerV1Atom as IndependentScorerAtom,
    NativeScorerV1Backend as IndependentScorerBackend,
    NativeScorerV1Config as IndependentScorerConfig,
    NativeScorerV1Context as IndependentScorerContext,
    NativeScorerV1Donor as IndependentScorerDonor,
    NativeScorerV1FailureCode as IndependentScorerFailureCode,
    NativeScorerV1KernelOutcome as IndependentScorerOutcome, Quaternion, Vec3,
    FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM, NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID,
    NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID,
};
use betelgeuze_sys as sys;
use sha2::{Digest, Sha256 as Sha256Hasher};

use super::{
    checked_count, finite, invalid, status_result, Backend, Context, Error, ErrorCode, PositionSoa,
    Result, UnitSystem,
};

pub type Sha256 = [u8; 32];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64Donor {
    pub donor_atom_index: u64,
    pub hydrogen_atom_index: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64Pair {
    pub atom_i: u64,
    pub atom_j: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64Rotor {
    pub atom_i: u64,
    pub atom_j: u64,
    pub atom_k: u64,
    pub atom_l: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64ChiralityCenter {
    pub center_atom: u64,
    pub atom_i: u64,
    pub atom_j: u64,
    pub atom_k: u64,
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64Receptor<'a> {
    pub coordinates: PositionSoa<'a>,
    pub vdw_radius_angstrom: &'a [f64],
    pub charge_elementary: &'a [f64],
    pub epsilon_kcal_per_mol: &'a [f64],
    pub hydrophobic_mask: &'a [u8],
    pub acceptor_mask: &'a [u8],
    pub donors: &'a [Fixed64Donor],
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64Ligand<'a> {
    pub reference_coordinates: PositionSoa<'a>,
    pub vdw_radius_angstrom: &'a [f64],
    pub heavy_atom_mask: &'a [u8],
    pub charge_elementary: &'a [f64],
    pub epsilon_kcal_per_mol: &'a [f64],
    pub hydrophobic_mask: &'a [u8],
    pub acceptor_mask: &'a [u8],
    pub donors: &'a [Fixed64Donor],
    pub exclusions: &'a [Fixed64Pair],
    pub rotors: &'a [Fixed64Rotor],
    pub bonds: &'a [Fixed64Pair],
    pub chirality_centers: &'a [Fixed64ChiralityCenter],
    pub parent_atom_index: &'a [i32],
    pub rotatable_child_atom_index: &'a [u64],
    pub internal_pairs: &'a [Fixed64Pair],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64Identities {
    pub authority_input_receipt_sha256: Sha256,
    pub receptor_system_sha256: Sha256,
    pub ligand_system_sha256: Sha256,
    pub backend_receipt_sha256: Sha256,
    /// Receipt asserted by the upstream validity contract.
    ///
    /// The complete native pipeline independently derives and returns its own
    /// ScorerV1 context receipt. This supplied identity remains distinct until
    /// the ABI exposes a public pre-construction derivation operation.
    pub validity_scorer_context_receipt_sha256: Sha256,
    pub contact_policy_sha256: Sha256,
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64PipelineContext<'a> {
    pub receptor: Fixed64Receptor<'a>,
    pub ligand: Fixed64Ligand<'a>,
    pub pocket_center_angstrom: [f64; 3],
    pub pocket_radius_angstrom: f64,
    pub identities: Fixed64Identities,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fixed64FeatureKind {
    LigandDonor,
    LigandAcceptor,
    ReceptorDonor,
    ReceptorAcceptor,
    LigandPositiveSite,
    LigandNegativeSite,
    ReceptorPositiveSite,
    ReceptorNegativeSite,
    LigandAromaticPlane,
    ReceptorAromaticPlane,
    LigandShapeAxis,
    PocketShapeAxis,
}

impl Fixed64FeatureKind {
    const fn as_raw(self) -> sys::bg_docking_fixed64_feature_kind {
        match self {
            Self::LigandDonor => sys::BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR,
            Self::LigandAcceptor => sys::BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR,
            Self::ReceptorDonor => sys::BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR,
            Self::ReceptorAcceptor => sys::BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR,
            Self::LigandPositiveSite => sys::BG_DOCKING_FIXED64_FEATURE_LIGAND_POSITIVE_SITE,
            Self::LigandNegativeSite => sys::BG_DOCKING_FIXED64_FEATURE_LIGAND_NEGATIVE_SITE,
            Self::ReceptorPositiveSite => sys::BG_DOCKING_FIXED64_FEATURE_RECEPTOR_POSITIVE_SITE,
            Self::ReceptorNegativeSite => sys::BG_DOCKING_FIXED64_FEATURE_RECEPTOR_NEGATIVE_SITE,
            Self::LigandAromaticPlane => sys::BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE,
            Self::ReceptorAromaticPlane => sys::BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE,
            Self::LigandShapeAxis => sys::BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS,
            Self::PocketShapeAxis => sys::BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS,
        }
    }

    const fn as_independent(self) -> IndependentFixed64FeatureKind {
        match self {
            Self::LigandDonor => IndependentFixed64FeatureKind::LigandDonor,
            Self::LigandAcceptor => IndependentFixed64FeatureKind::LigandAcceptor,
            Self::ReceptorDonor => IndependentFixed64FeatureKind::ReceptorDonor,
            Self::ReceptorAcceptor => IndependentFixed64FeatureKind::ReceptorAcceptor,
            Self::LigandPositiveSite => IndependentFixed64FeatureKind::LigandPositiveSite,
            Self::LigandNegativeSite => IndependentFixed64FeatureKind::LigandNegativeSite,
            Self::ReceptorPositiveSite => IndependentFixed64FeatureKind::ReceptorPositiveSite,
            Self::ReceptorNegativeSite => IndependentFixed64FeatureKind::ReceptorNegativeSite,
            Self::LigandAromaticPlane => IndependentFixed64FeatureKind::LigandAromaticPlane,
            Self::ReceptorAromaticPlane => IndependentFixed64FeatureKind::ReceptorAromaticPlane,
            Self::LigandShapeAxis => IndependentFixed64FeatureKind::LigandShapeAxis,
            Self::PocketShapeAxis => IndependentFixed64FeatureKind::PocketShapeAxis,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64SourceEvidence {
    pub receipt_sha256: Sha256,
    pub proposal_sha256: Sha256,
    pub coordinate_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64ExactSourceEvidence {
    pub source_receipt_sha256: Sha256,
    pub proposal_sha256: Sha256,
    pub ligand_coordinate_sha256: Sha256,
    pub receptor_coordinate_sha256: Sha256,
    pub prepared_ligand_topology_sha256: Sha256,
    pub prepared_receptor_topology_sha256: Sha256,
    pub ligand_vdw_radii_sha256: Sha256,
    pub ligand_heavy_atom_mask_sha256: Sha256,
    pub receptor_vdw_radii_sha256: Sha256,
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64CoordinateSource<'a> {
    pub evidence: Fixed64SourceEvidence,
    pub coordinates: PositionSoa<'a>,
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64IndexedCoordinateSource<'a> {
    pub source_index: u32,
    pub source: Fixed64CoordinateSource<'a>,
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64ConformerCoordinateSource<'a> {
    pub rank: u8,
    pub source: Fixed64CoordinateSource<'a>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64AtomicFeature {
    pub kind: Fixed64FeatureKind,
    pub receipt_sha256: Sha256,
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64FeatureGeometry<'a> {
    pub kind: Fixed64FeatureKind,
    pub allocation_feature_receipt_sha256: Sha256,
    pub atom_indices: &'a [u64],
    pub feature_geometry_receipt_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fixed64RefinementMode {
    V2Translation,
    V3TranslationRotation,
    V6BaselineV2Lane,
    V6BaselineV3Lane,
}

impl Fixed64RefinementMode {
    const fn as_raw(self) -> sys::bg_docking_rigid_refinement_candidate_mode {
        match self {
            Self::V2Translation => sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            Self::V3TranslationRotation => {
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION
            }
            Self::V6BaselineV2Lane => {
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
            }
            Self::V6BaselineV3Lane => {
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE
            }
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct Fixed64RunInput<'a> {
    pub exact_source_evidence: Fixed64ExactSourceEvidence,
    pub exact_source: Fixed64CoordinateSource<'a>,
    pub atomic_features: &'a [Fixed64AtomicFeature],
    pub v7_control_sources: &'a [Fixed64IndexedCoordinateSource<'a>],
    pub conformer_sources: &'a [Fixed64ConformerCoordinateSource<'a>],
    pub retained_sources: &'a [Fixed64IndexedCoordinateSource<'a>],
    pub feature_geometries: &'a [Fixed64FeatureGeometry<'a>],
    pub feature_geometry_inventory_sha256: Sha256,
    pub pocket_normal: [f64; 3],
    pub rmsd_threshold_angstrom: f64,
    pub candidate_modes: &'a [Fixed64RefinementMode],
    pub rigid_max_steps: &'a [u64],
    pub proposal_is_torsion_eligible: &'a [u8],
    pub torsion_max_steps: &'a [u64],
    pub baseline_torsion_angles_radians: &'a [f64],
    pub predeclared_refinement_policy_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64GeometricEvidence {
    pub status: i32,
    pub failure_code: i32,
    pub decision: i32,
    pub rank_eligible: bool,
    pub ligand_atom_count: u64,
    pub receptor_atom_count: u64,
    pub exact_pair_count: u64,
    pub penetration_pair_count: u64,
    pub unique_ligand_penetration_atom_count: u64,
    pub unique_ligand_heavy_atom_penetration_count: u64,
    pub raw_minimum_distance_angstrom: f64,
    pub minimum_vdw_surface_gap_angstrom: f64,
    pub minimum_vdw_ratio: f64,
    pub sphere_overlap_proxy_angstrom3: f64,
    pub pocket_escape_angstrom: f64,
    pub row_receipt_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64ProducerEvidence {
    pub slot_index: u32,
    pub lane: i32,
    pub status: i32,
    pub failure_code: i32,
    pub placement_kind: i32,
    pub component_failure_code: i32,
    pub backend: Backend,
    pub ligand_atom_count: u64,
    pub coordinate_offset: u64,
    pub coordinates_available: bool,
    pub steric_precheck_passed: bool,
    pub source_identity_verified: bool,
    pub allocation_identity_verified: bool,
    pub geometric_identity_verified: bool,
    pub denominator_preserved: bool,
    pub placement_quaternion: [f64; 4],
    pub allocation_slot_receipt_sha256: Sha256,
    pub source_payload_receipt_sha256: Sha256,
    pub source_proposal_sha256: Sha256,
    pub source_coordinate_sha256: Sha256,
    pub placement_receipt_sha256: Sha256,
    pub output_proposal_sha256: Sha256,
    pub output_coordinate_sha256: Sha256,
    pub row_receipt_sha256: Sha256,
    pub geometric: Fixed64GeometricEvidence,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64RigidProfileEvidence {
    pub profile: i32,
    pub available: bool,
    pub accepted_steps: u64,
    pub accepted_translation_steps: u64,
    pub accepted_rotation_steps: u64,
    pub line_search_evaluation_count: u64,
    pub fallback_direction_step_count: u64,
    pub initial_penalty: f64,
    pub final_penalty: f64,
    pub total_translation_angstrom: [f64; 3],
    pub total_rotation_vector_radians: [f64; 3],
    pub total_rotation_path_radians: f64,
    pub initial_centroid_offset_angstrom: f64,
    pub final_centroid_offset_angstrom: f64,
    pub maximum_centroid_offset_angstrom: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64RigidEvidence {
    pub slot_index: u32,
    pub status: i32,
    pub failure_code: i32,
    pub candidate_mode: i32,
    pub selected_profile: i32,
    pub baseline_duplicate_of_v2: bool,
    pub clearance_evaluated: bool,
    pub clearance_selected: bool,
    pub selected: Fixed64RigidProfileEvidence,
    pub comparison_v2: Fixed64RigidProfileEvidence,
    pub baseline_v3: Fixed64RigidProfileEvidence,
    pub clearance_v4: Fixed64RigidProfileEvidence,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64RigidCoordinates {
    pub selected: super::PositionSoaOwned,
    pub comparison_v2: super::PositionSoaOwned,
    pub baseline_v3: super::PositionSoaOwned,
    pub clearance_v4: super::PositionSoaOwned,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64ScorerEvidence {
    pub slot_index: u32,
    pub status: i32,
    pub failure_code: i32,
    pub weighted_terms: [f64; sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize],
    pub total_score: f64,
    pub receptor_candidate_pair_count: u64,
    pub ligand_pair_count: u64,
    pub hbond_count: u64,
    pub hydrophobic_contact_count: u64,
    pub buried_polar_count: u64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64ValidityEvidence {
    pub slot_index: u32,
    pub status: i32,
    pub failure_code: i32,
    pub upstream_scorer_failure_code: i32,
    pub passed_check_mask: u32,
    pub blocker_mask: u32,
    pub observed_count: u64,
    pub atom_count: u64,
    pub rotation_orthogonality_max_error: f64,
    pub rotation_determinant: f64,
    pub max_bond_length_delta_angstrom: f64,
    pub minimum_ligand_nonbonded_distance_angstrom: f64,
    pub evaluated_ligand_nonbonded_pair_count: u64,
    pub excluded_ligand_pair_count: u64,
    pub minimum_receptor_ligand_distance_angstrom: f64,
    pub evaluated_receptor_ligand_pair_count: u64,
    pub minimum_declared_chiral_volume: f64,
    pub declared_chirality_center_count: u64,
    pub maximum_pocket_center_distance_angstrom: f64,
    pub element_vdw_ligand_pair_count: u64,
    pub element_vdw_ligand_severe_overlap_count: u64,
    pub element_vdw_ligand_minimum_distance_angstrom: f64,
    pub element_vdw_ligand_minimum_ratio: f64,
    pub element_vdw_receptor_candidate_pair_count: u64,
    pub element_vdw_receptor_full_cartesian_pair_count: u64,
    pub element_vdw_receptor_cell_count: u64,
    pub element_vdw_receptor_severe_overlap_count: u64,
    pub element_vdw_receptor_minimum_distance_angstrom: f64,
    pub element_vdw_receptor_minimum_ratio: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64RankingEvidence {
    pub slot_index: u32,
    pub rank_eligible: bool,
    pub valid_rank_eligible: bool,
    pub stable_rank: u32,
    pub stable_valid_rank: u32,
    pub total_score: f64,
    pub coordinate_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64ClusterEvidence {
    pub slot_index: u32,
    pub status: i32,
    pub cluster_eligible: bool,
    pub representative: bool,
    pub top_k_representative: bool,
    pub stable_valid_rank: u32,
    pub cluster_id: u32,
    pub representative_slot_index: u32,
    pub cluster_rank: u32,
    pub top_k_rank: u32,
    pub cluster_size: u32,
    pub direct_rmsd_to_representative_angstrom: f64,
    pub coordinate_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64TorsionEvidence {
    pub slot_index: u32,
    pub status: i32,
    pub failure_code: i32,
    pub skip_reason: i32,
    pub selection_reason: i32,
    pub selection_window_reachable: bool,
    pub evaluation_stopped_after_selection_window_became_unreachable: bool,
    pub torsion_evaluated: bool,
    pub torsion_variant_available: bool,
    pub torsion_selected: bool,
    pub torsion_step_budget: u64,
    pub fixed_objective_evaluation_count: u64,
    pub torsion_trial_objective_evaluation_count: u64,
    pub evaluated_torsion_steps: u64,
    pub accepted_torsion_steps: u64,
    pub baseline_v6_accepted_steps: u64,
    pub source_receptor_penalty: f64,
    pub source_internal_penalty: f64,
    pub source_combined_penalty: f64,
    pub baseline_receptor_penalty: f64,
    pub baseline_internal_penalty: f64,
    pub baseline_combined_penalty: f64,
    pub optimized_receptor_penalty: f64,
    pub optimized_internal_penalty: f64,
    pub optimized_combined_penalty: f64,
    pub final_receptor_penalty: f64,
    pub final_internal_penalty: f64,
    pub final_combined_penalty: f64,
    pub evaluated_total_torsion_path_radians: f64,
    pub accepted_total_torsion_path_radians: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64TorsionMoveEvidence {
    pub slot_index: u32,
    pub move_index: u32,
    pub evaluated: bool,
    pub selected: bool,
    pub rotatable_child_atom_index: u64,
    pub delta_radians: f64,
    pub receptor_penalty: f64,
    pub internal_penalty: f64,
    pub combined_penalty: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64TorsionCoordinates {
    pub optimized: super::PositionSoaOwned,
    pub optimized_torsion_angles_radians: Vec<f64>,
    pub final_state: super::PositionSoaOwned,
    pub final_torsion_angles_radians: Vec<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64RefinementEvidence {
    pub slot_index: u32,
    pub status: i32,
    pub failure_stage: i32,
    pub coordinate_origin: i32,
    pub rigid_failure_code: i32,
    pub torsion_v7_failure_code: i32,
    pub selected_rigid_profile: i32,
    pub downstream_candidate_state: i32,
    pub torsion_v7_applicable: bool,
    pub torsion_v7_selected: bool,
    pub coordinate_available: bool,
    pub coordinate_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64PipelineRow {
    pub slot_index: u32,
    pub producer_status: i32,
    pub producer_failure_code: i32,
    pub initial_admission_decision: i32,
    pub requested_refinement_mode: i32,
    pub effective_refinement_mode: i32,
    pub refinement_status: i32,
    pub refinement_failure_stage: i32,
    pub scorer_status: i32,
    pub scorer_failure_code: i32,
    pub validity_status: i32,
    pub validity_failure_code: i32,
    pub stable_rank: u32,
    pub stable_valid_rank: u32,
    pub cluster_status: i32,
    pub cluster_id: u32,
    pub cluster_rank: u32,
    pub top_k_rank: u32,
    pub producer_row_receipt_sha256: Sha256,
    pub final_coordinate_sha256: Sha256,
    pub refinement_evidence_sha256: Sha256,
    pub scorer_evidence_sha256: Sha256,
    pub validity_evidence_sha256: Sha256,
    pub ranking_evidence_sha256: Sha256,
    pub cluster_evidence_sha256: Sha256,
    pub row_receipt_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64AuthorityDisposition {
    pub result_dependent_input_consumed: bool,
    pub fallback_allowed: bool,
    pub multi_anchor_consumed: bool,
    pub denominator_preserved: bool,
    pub molecular_execution_authorized: bool,
    pub reservation_authorized: bool,
    pub benchmark_execution_authorized: bool,
    pub existing_rank_auto_change_authorized: bool,
    pub customer_pose_emission_authorized: bool,
    pub production_claim_authorized: bool,
    pub scientific_claim_authorized: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64BatchReceipts {
    pub allocation_inventory_sha256: Sha256,
    pub allocation_receipt_sha256: Sha256,
    pub source_bundle_receipt_sha256: Sha256,
    pub geometric_admission_batch_receipt_sha256: Sha256,
    pub admission_context_receipt_sha256: Sha256,
    pub refinement_context_receipt_sha256: Sha256,
    pub scorer_context_receipt_sha256: Sha256,
    pub validity_context_receipt_sha256: Sha256,
    pub component_binding_receipt_sha256: Sha256,
    pub producer_batch_receipt_sha256: Sha256,
    pub refinement_policy_receipt_sha256: Sha256,
    pub refinement_batch_receipt_sha256: Sha256,
    pub scorer_batch_receipt_sha256: Sha256,
    pub validity_batch_receipt_sha256: Sha256,
    pub ranking_batch_receipt_sha256: Sha256,
    pub cluster_batch_receipt_sha256: Sha256,
    pub pipeline_batch_receipt_sha256: Sha256,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64PipelineReceipt {
    pub backend: Backend,
    pub unit_system: UnitSystem,
    pub receptor_atom_count: usize,
    pub ligand_atom_count: usize,
    pub generated_count: u64,
    pub typed_failure_count: u64,
    pub initial_admitted_count: u64,
    pub refined_count: u64,
    pub scored_count: u64,
    pub valid_count: u64,
    pub cluster_count: u64,
    pub producer_coordinates: super::PositionSoaOwned,
    pub rigid_coordinates: Fixed64RigidCoordinates,
    pub torsion_coordinates: Fixed64TorsionCoordinates,
    pub final_coordinates: super::PositionSoaOwned,
    pub final_quaternions: [Vec<f64>; 4],
    pub producer_rows: Vec<Fixed64ProducerEvidence>,
    pub rigid_rows: Vec<Fixed64RigidEvidence>,
    pub torsion_rows: Vec<Fixed64TorsionEvidence>,
    pub torsion_moves: Vec<Fixed64TorsionMoveEvidence>,
    pub refinement_rows: Vec<Fixed64RefinementEvidence>,
    pub scorer_rows: Vec<Fixed64ScorerEvidence>,
    pub validity_rows: Vec<Fixed64ValidityEvidence>,
    pub ranking_rows: Vec<Fixed64RankingEvidence>,
    pub cluster_rows: Vec<Fixed64ClusterEvidence>,
    pub rows: Vec<Fixed64PipelineRow>,
    pub primary_slot_indices: Vec<u32>,
    pub valid_slot_indices: Vec<u32>,
    pub representative_slot_indices: Vec<u32>,
    pub top_k_slot_indices: Vec<u32>,
    pub receipts: Fixed64BatchReceipts,
    pub authority: Fixed64AuthorityDisposition,
}

struct ValidatedContext {
    receptor_atom_count: u64,
    ligand_atom_count: u64,
}

impl Fixed64PipelineContext<'_> {
    fn validate(&self) -> Result<ValidatedContext> {
        let receptor_count = self.receptor.coordinates.validate()?;
        let ligand_count = self.ligand.reference_coordinates.validate()?;
        if receptor_count == 0 || ligand_count == 0 {
            return Err(invalid(
                "fixed64 receptor and ligand atom counts must be non-zero",
            ));
        }
        validate_f64_channels(
            receptor_count,
            &[
                (self.receptor.vdw_radius_angstrom, "receptor vdw radii"),
                (self.receptor.charge_elementary, "receptor charges"),
                (
                    self.receptor.epsilon_kcal_per_mol,
                    "receptor epsilon values",
                ),
            ],
        )?;
        validate_masks(
            receptor_count,
            &[
                (self.receptor.hydrophobic_mask, "receptor hydrophobic mask"),
                (self.receptor.acceptor_mask, "receptor acceptor mask"),
            ],
        )?;
        validate_f64_channels(
            ligand_count,
            &[
                (self.ligand.vdw_radius_angstrom, "ligand vdw radii"),
                (self.ligand.charge_elementary, "ligand charges"),
                (self.ligand.epsilon_kcal_per_mol, "ligand epsilon values"),
            ],
        )?;
        validate_masks(
            ligand_count,
            &[
                (self.ligand.heavy_atom_mask, "ligand heavy-atom mask"),
                (self.ligand.hydrophobic_mask, "ligand hydrophobic mask"),
                (self.ligand.acceptor_mask, "ligand acceptor mask"),
            ],
        )?;
        if self.ligand.parent_atom_index.len() != ligand_count {
            return Err(invalid(
                "ligand parent-atom channel must match the ligand atom count",
            ));
        }
        if !finite(&self.pocket_center_angstrom)
            || !self.pocket_radius_angstrom.is_finite()
            || self.pocket_radius_angstrom <= 0.0
        {
            return Err(invalid(
                "fixed64 pocket center and radius must be finite and the radius positive",
            ));
        }
        for radius in self
            .receptor
            .vdw_radius_angstrom
            .iter()
            .chain(self.ligand.vdw_radius_angstrom.iter())
        {
            if *radius <= 0.0 {
                return Err(invalid("fixed64 vdw radii must be strictly positive"));
            }
        }
        for epsilon in self
            .receptor
            .epsilon_kcal_per_mol
            .iter()
            .chain(self.ligand.epsilon_kcal_per_mol.iter())
        {
            if *epsilon < 0.0 {
                return Err(invalid("fixed64 epsilon values must be non-negative"));
            }
        }
        validate_digests(self.identities)?;
        validate_topology(self, receptor_count, ligand_count)?;
        Ok(ValidatedContext {
            receptor_atom_count: checked_count(receptor_count)?,
            ligand_atom_count: checked_count(ligand_count)?,
        })
    }
}

fn validate_f64_channels(expected: usize, channels: &[(&[f64], &str)]) -> Result<()> {
    for (values, label) in channels {
        if values.len() != expected {
            return Err(invalid(format!(
                "{label} must match its molecular atom count"
            )));
        }
        if !finite(values) {
            return Err(invalid(format!("{label} must contain only finite values")));
        }
    }
    Ok(())
}

fn validate_masks(expected: usize, channels: &[(&[u8], &str)]) -> Result<()> {
    for (values, label) in channels {
        if values.len() != expected {
            return Err(invalid(format!(
                "{label} must match its molecular atom count"
            )));
        }
        if values.iter().any(|value| *value > 1) {
            return Err(invalid(format!("{label} must contain only 0 or 1")));
        }
    }
    Ok(())
}

fn digest_present(value: &Sha256) -> bool {
    value.iter().any(|byte| *byte != 0)
}

struct CanonicalHasher(Sha256Hasher);

impl CanonicalHasher {
    fn new(domain: &str) -> Self {
        let mut hasher = Self(Sha256Hasher::new());
        hasher.string(domain);
        hasher
    }

    fn byte(&mut self, value: u8) {
        self.0.update([value]);
    }

    fn u32(&mut self, value: u32) {
        self.0.update(value.to_be_bytes());
    }

    fn i32(&mut self, value: i32) {
        self.u32(value as u32);
    }

    fn u64(&mut self, value: u64) {
        self.0.update(value.to_be_bytes());
    }

    fn usize(&mut self, value: usize) {
        self.u64(u64::try_from(value).expect("bounded native receipt length fits u64"));
    }

    fn f64(&mut self, value: f64) {
        let canonical = if value == 0.0 { 0.0 } else { value };
        self.u64(canonical.to_bits());
    }

    fn vec3(&mut self, value: Vec3) {
        self.f64(value.x);
        self.f64(value.y);
        self.f64(value.z);
    }

    fn bytes(&mut self, value: &[u8]) {
        self.usize(value.len());
        self.0.update(value);
    }

    fn string(&mut self, value: &str) {
        self.bytes(value.as_bytes());
    }

    fn digest(&mut self, value: Sha256) {
        self.0.update(value);
    }

    fn finish(self) -> Sha256 {
        self.0.finalize().into()
    }
}

fn hash_f64_channel(hash: &mut CanonicalHasher, values: &[f64]) {
    hash.usize(values.len());
    for value in values {
        hash.f64(*value);
    }
}

fn hash_u8_channel(hash: &mut CanonicalHasher, values: &[u8]) {
    hash.usize(values.len());
    for value in values {
        hash.byte(*value);
    }
}

fn hash_u64_channel(hash: &mut CanonicalHasher, values: &[u64]) {
    hash.usize(values.len());
    for value in values {
        hash.u64(*value);
    }
}

fn hash_i32_channel(hash: &mut CanonicalHasher, values: &[i32]) {
    hash.usize(values.len());
    for value in values {
        hash.i32(*value);
    }
}

fn hash_rigid_v2_config(hash: &mut CanonicalHasher, config: &sys::bg_docking_rigid_v2_config_v1) {
    hash.f64(config.overlap_scale);
    hash.f64(config.maximum_step_angstrom);
    hash.f64(config.minimum_step_angstrom);
    hash.f64(config.maximum_total_translation_angstrom);
    hash.u64(config.maximum_backtracking_evaluations);
    hash.f64(config.penalty_tolerance);
    hash.f64(config.epsilon_angstrom);
}

fn hash_rigid_v3_config(hash: &mut CanonicalHasher, config: &sys::bg_docking_rigid_v3_config_v1) {
    hash_rigid_v2_config(hash, &config.v2);
    hash.f64(config.maximum_rotation_step_radians);
    hash.f64(config.minimum_rotation_step_radians);
    hash.f64(config.maximum_total_rotation_radians);
    hash.u64(config.maximum_rotation_steps);
    hash.f64(config.minimum_rotation_relative_penalty_reduction);
    hash.f64(config.maximum_centroid_offset_angstrom);
}

fn canonical_admission_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    descriptor: &sys::bg_docking_geometric_admission_context_soa_v1,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_admission_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.x_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.y_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.z_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, scientific.ligand.vdw_radius_angstrom);
    hash_u8_channel(&mut hash, scientific.ligand.heavy_atom_mask);
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash.f64(descriptor.hard_rejection_minimum_vdw_ratio);
    hash.u64(descriptor.max_batch_exact_pair_evaluations);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.finish()
}

fn canonical_refinement_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    rigid: &sys::bg_docking_rigid_refinement_context_soa_v1,
    torsion: &sys::bg_docking_torsion_v7_context_soa_v1,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(rigid.unit_system);
    hash.u64(rigid.receptor_atom_count);
    hash.u64(rigid.ligand_atom_count);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.x_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.y_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.z_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, scientific.ligand.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(rigid.pocket_radius_angstrom);
    hash_rigid_v2_config(&mut hash, &rigid.v2);
    hash_rigid_v3_config(&mut hash, &rigid.v3);
    hash_rigid_v3_config(&mut hash, &rigid.clearance_v4);
    hash.i32(torsion.unit_system);
    hash.u64(torsion.receptor_atom_count);
    hash.u64(torsion.ligand_atom_count);
    hash.u64(torsion.rotor_count);
    hash.u64(torsion.internal_pair_count);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.x_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.y_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.z_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, scientific.ligand.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash_i32_channel(&mut hash, scientific.ligand.parent_atom_index);
    hash_u64_channel(&mut hash, scientific.ligand.rotatable_child_atom_index);
    let internal_i = scientific
        .ligand
        .internal_pairs
        .iter()
        .map(|pair| pair.atom_i)
        .collect::<Vec<_>>();
    let internal_j = scientific
        .ligand
        .internal_pairs
        .iter()
        .map(|pair| pair.atom_j)
        .collect::<Vec<_>>();
    hash_u64_channel(&mut hash, &internal_i);
    hash_u64_channel(&mut hash, &internal_j);
    hash.f64(torsion.receptor_overlap_scale);
    hash.f64(torsion.internal_overlap_scale);
    hash.f64(torsion.internal_overlap_weight);
    hash.u64(torsion.maximum_baseline_v6_steps);
    hash.u64(torsion.maximum_torsions_evaluated);
    hash.u64(torsion.maximum_torsion_steps);
    hash.u64(torsion.maximum_backtracking_evaluations);
    hash.f64(torsion.maximum_torsion_step_radians);
    hash.f64(torsion.minimum_torsion_step_radians);
    hash.f64(torsion.maximum_total_torsion_path_radians);
    hash.f64(torsion.maximum_centroid_offset_angstrom);
    hash.f64(torsion.minimum_selected_final_receptor_penalty);
    hash.f64(torsion.maximum_selected_final_receptor_penalty);
    hash.f64(torsion.penalty_tolerance);
    hash.f64(torsion.epsilon_angstrom);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
fn canonical_scorer_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    descriptor: &sys::bg_docking_scorer_v1_context_soa_v1,
    receptor_donor_atom: &[u64],
    receptor_hydrogen_atom: &[u64],
    ligand_donor_atom: &[u64],
    ligand_hydrogen_atom: &[u64],
    exclusion_i: &[u64],
    exclusion_j: &[u64],
    rotor_i: &[u64],
    rotor_j: &[u64],
    rotor_k: &[u64],
    rotor_l: &[u64],
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scorer_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    for values in [
        scientific.receptor.coordinates.x_angstrom,
        scientific.receptor.coordinates.y_angstrom,
        scientific.receptor.coordinates.z_angstrom,
        scientific.receptor.charge_elementary,
        scientific.receptor.vdw_radius_angstrom,
        scientific.receptor.epsilon_kcal_per_mol,
    ] {
        hash_f64_channel(&mut hash, values);
    }
    hash_u8_channel(&mut hash, scientific.receptor.hydrophobic_mask);
    hash_u8_channel(&mut hash, scientific.receptor.acceptor_mask);
    for values in [
        scientific.ligand.reference_coordinates.x_angstrom,
        scientific.ligand.reference_coordinates.y_angstrom,
        scientific.ligand.reference_coordinates.z_angstrom,
        scientific.ligand.charge_elementary,
        scientific.ligand.vdw_radius_angstrom,
        scientific.ligand.epsilon_kcal_per_mol,
    ] {
        hash_f64_channel(&mut hash, values);
    }
    hash_u8_channel(&mut hash, scientific.ligand.hydrophobic_mask);
    hash_u8_channel(&mut hash, scientific.ligand.acceptor_mask);
    for values in [
        receptor_donor_atom,
        receptor_hydrogen_atom,
        ligand_donor_atom,
        ligand_hydrogen_atom,
        exclusion_i,
        exclusion_j,
        rotor_i,
        rotor_j,
        rotor_k,
        rotor_l,
    ] {
        hash_u64_channel(&mut hash, values);
    }
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash_f64_channel(&mut hash, &descriptor.weights);
    hash.f64(descriptor.electrostatic_dielectric);
    hash.f64(descriptor.pair_cutoff_angstrom);
    hash.f64(descriptor.hbond_distance_max_angstrom);
    hash.f64(descriptor.polar_burial_distance_angstrom);
    hash.u64(descriptor.max_receptor_candidate_pairs);
    hash.u64(descriptor.max_ligand_pair_checks);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
fn canonical_validity_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    descriptor: &sys::bg_docking_pose_validity_context_soa_v1,
    bond_i: &[u64],
    bond_j: &[u64],
    exclusion_i: &[u64],
    exclusion_j: &[u64],
    chirality_center: &[u64],
    chirality_i: &[u64],
    chirality_j: &[u64],
    chirality_k: &[u64],
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_validity_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    for values in [
        scientific.receptor.coordinates.x_angstrom,
        scientific.receptor.coordinates.y_angstrom,
        scientific.receptor.coordinates.z_angstrom,
        scientific.receptor.vdw_radius_angstrom,
        scientific.ligand.reference_coordinates.x_angstrom,
        scientific.ligand.reference_coordinates.y_angstrom,
        scientific.ligand.reference_coordinates.z_angstrom,
        scientific.ligand.vdw_radius_angstrom,
    ] {
        hash_f64_channel(&mut hash, values);
    }
    for values in [
        bond_i,
        bond_j,
        exclusion_i,
        exclusion_j,
        chirality_center,
        chirality_i,
        chirality_j,
        chirality_k,
    ] {
        hash_u64_channel(&mut hash, values);
    }
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash.f64(descriptor.bond_length_tolerance_angstrom);
    hash.f64(descriptor.ligand_self_clash_angstrom);
    hash.f64(descriptor.receptor_ligand_clash_angstrom);
    hash.f64(descriptor.rotation_tolerance);
    hash.f64(descriptor.chirality_volume_tolerance);
    hash.f64(descriptor.severe_overlap_scale);
    hash.f64(descriptor.contact_cell_size_angstrom);
    hash.u64(descriptor.max_pair_checks);
    hash.u64(descriptor.max_cross_checks);
    hash.u64(descriptor.max_element_ligand_pair_checks);
    hash.u64(descriptor.max_element_receptor_candidate_pairs);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.scorer_context_receipt_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.digest(descriptor.contact_policy_sha256);
    hash.finish()
}

fn canonical_component_binding_receipt(
    backend: Backend,
    device_ordinal: i32,
    admission: Sha256,
    refinement: Sha256,
    scorer: Sha256,
    validity: Sha256,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_component_binding/1.0.0");
    hash.string("betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.digest(admission);
    hash.digest(refinement);
    hash.digest(scorer);
    hash.digest(validity);
    hash.finish()
}

fn canonical_coordinate_sha256(coordinates: PositionSoa<'_>) -> Sha256 {
    let mut hasher = CanonicalHasher::new("betelgeuze.fixed64_coordinates/native-v1");
    hasher.usize(coordinates.x_angstrom.len());
    for atom in 0..coordinates.x_angstrom.len() {
        for value in [
            coordinates.x_angstrom[atom],
            coordinates.y_angstrom[atom],
            coordinates.z_angstrom[atom],
        ] {
            hasher.f64(value);
        }
    }
    hasher.finish()
}

fn canonical_source_payload_sha256(
    source: Fixed64CoordinateSource<'_>,
    ligand_atom_count: u64,
) -> Sha256 {
    let mut hasher = CanonicalHasher::new("betelgeuze.fixed64_coordinate_source_abi/native-v1");
    hasher.digest(source.evidence.receipt_sha256);
    hasher.digest(source.evidence.proposal_sha256);
    hasher.digest(source.evidence.coordinate_sha256);
    hasher.u64(ligand_atom_count);
    hasher.byte(1);
    hasher.byte(0);
    hasher.finish()
}

#[derive(Debug, Clone, Copy)]
struct ExpectedPipelineReceiptGraph {
    allocation_inventory_sha256: Sha256,
    allocation_receipt_sha256: Sha256,
    source_bundle_receipt_sha256: Sha256,
    admission_context_receipt_sha256: Sha256,
    refinement_context_receipt_sha256: Sha256,
    scorer_context_receipt_sha256: Sha256,
    validity_context_receipt_sha256: Sha256,
    component_binding_receipt_sha256: Sha256,
    refinement_policy_receipt_sha256: Sha256,
    authority_input_receipt_sha256: Sha256,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    backend_receipt_sha256: Sha256,
    backend: Backend,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    ligand_heavy_atom_count: u64,
    geometric_max_batch_exact_pair_evaluations: u64,
    pocket_center_angstrom: [f64; 3],
    pocket_radius_angstrom: f64,
    geometric_hard_rejection_minimum_vdw_ratio: f64,
}

#[allow(clippy::too_many_arguments)]
fn canonical_source_bundle_receipt(
    input: Fixed64RunInput<'_>,
    allocation_receipt_sha256: Sha256,
    ligand_atom_count: u64,
    pocket_center_angstrom: [f64; 3],
    authority_input_receipt_sha256: Sha256,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    backend_receipt_sha256: Sha256,
) -> Result<Sha256> {
    let feature_atom_index_count = input
        .feature_geometries
        .iter()
        .try_fold(0_usize, |total, geometry| {
            total.checked_add(geometry.atom_indices.len())
        })
        .ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 feature atom denominator overflowed while deriving source bundle",
            )
        })?;
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_source_bundle_abi/native-v1");
    hash.digest(allocation_receipt_sha256);
    hash.byte(1);
    hash.digest(canonical_source_payload_sha256(
        input.exact_source,
        ligand_atom_count,
    ));
    hash.usize(input.v7_control_sources.len());
    for source in input.v7_control_sources {
        hash.u32(source.source_index);
        hash.digest(canonical_source_payload_sha256(
            source.source,
            ligand_atom_count,
        ));
    }
    hash.usize(input.conformer_sources.len());
    for source in input.conformer_sources {
        hash.byte(source.rank);
        hash.digest(canonical_source_payload_sha256(
            source.source,
            ligand_atom_count,
        ));
    }
    hash.usize(input.retained_sources.len());
    for source in input.retained_sources {
        hash.u32(source.source_index);
        hash.digest(canonical_source_payload_sha256(
            source.source,
            ligand_atom_count,
        ));
    }
    hash.usize(input.feature_geometries.len());
    hash.usize(feature_atom_index_count);
    hash.digest(input.feature_geometry_inventory_sha256);
    for value in pocket_center_angstrom {
        hash.f64(value);
    }
    for value in input.pocket_normal {
        hash.f64(value);
    }
    hash.digest(authority_input_receipt_sha256);
    hash.digest(receptor_system_sha256);
    hash.digest(ligand_system_sha256);
    hash.digest(backend_receipt_sha256);
    hash.byte(1);
    hash.byte(0);
    Ok(hash.finish())
}

fn canonical_refinement_policy_receipt(
    refinement_context_receipt_sha256: Sha256,
    component_binding_receipt_sha256: Sha256,
    allocation_receipt_sha256: Sha256,
    input: Fixed64RunInput<'_>,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_policy_receipt/1.0.0");
    hash.string("betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0");
    hash.digest(refinement_context_receipt_sha256);
    hash.digest(component_binding_receipt_sha256);
    hash.digest(input.predeclared_refinement_policy_sha256);
    hash.digest(allocation_receipt_sha256);
    hash.f64(input.rmsd_threshold_angstrom);
    hash.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    for slot in 0..sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize {
        hash.i32(input.candidate_modes[slot].as_raw());
        hash.u64(input.rigid_max_steps[slot]);
        hash.byte(input.proposal_is_torsion_eligible[slot]);
        hash.u64(input.torsion_max_steps[slot]);
    }
    hash.usize(input.baseline_torsion_angles_radians.len());
    for value in input.baseline_torsion_angles_radians {
        hash.f64(*value);
    }
    hash.byte(0);
    hash.finish()
}

fn validate_digests(identities: Fixed64Identities) -> Result<()> {
    let values = [
        (
            identities.authority_input_receipt_sha256,
            "authority input receipt",
        ),
        (identities.receptor_system_sha256, "receptor system"),
        (identities.ligand_system_sha256, "ligand system"),
        (identities.backend_receipt_sha256, "backend receipt"),
        (
            identities.validity_scorer_context_receipt_sha256,
            "validity scorer-context receipt",
        ),
        (identities.contact_policy_sha256, "contact policy"),
    ];
    for (digest, label) in values {
        if !digest_present(&digest) {
            return Err(invalid(format!("fixed64 {label} SHA-256 is absent")));
        }
    }
    Ok(())
}

fn validate_topology(
    context: &Fixed64PipelineContext<'_>,
    receptor_count: usize,
    ligand_count: usize,
) -> Result<()> {
    for donor in context.receptor.donors {
        validate_index(donor.donor_atom_index, receptor_count, "receptor donor")?;
        validate_index(
            donor.hydrogen_atom_index,
            receptor_count,
            "receptor donor hydrogen",
        )?;
    }
    for donor in context.ligand.donors {
        validate_index(donor.donor_atom_index, ligand_count, "ligand donor")?;
        validate_index(
            donor.hydrogen_atom_index,
            ligand_count,
            "ligand donor hydrogen",
        )?;
    }
    for (pairs, label) in [
        (context.ligand.exclusions, "ligand exclusion"),
        (context.ligand.bonds, "ligand bond"),
        (context.ligand.internal_pairs, "ligand internal pair"),
    ] {
        for pair in pairs {
            validate_index(pair.atom_i, ligand_count, label)?;
            validate_index(pair.atom_j, ligand_count, label)?;
        }
    }
    for rotor in context.ligand.rotors {
        for atom in [rotor.atom_i, rotor.atom_j, rotor.atom_k, rotor.atom_l] {
            validate_index(atom, ligand_count, "ligand rotor")?;
        }
    }
    for center in context.ligand.chirality_centers {
        for atom in [
            center.center_atom,
            center.atom_i,
            center.atom_j,
            center.atom_k,
        ] {
            validate_index(atom, ligand_count, "ligand chirality center")?;
        }
    }
    for child in context.ligand.rotatable_child_atom_index {
        validate_index(*child, ligand_count, "rotatable child atom")?;
    }
    for parent in context.ligand.parent_atom_index {
        if *parent < -1 || (*parent >= 0 && *parent as usize >= ligand_count) {
            return Err(invalid("ligand parent atom index is out of range"));
        }
    }
    Ok(())
}

fn validate_index(index: u64, count: usize, label: &str) -> Result<()> {
    let index =
        usize::try_from(index).map_err(|_| invalid(format!("{label} index does not fit usize")))?;
    if index >= count {
        return Err(invalid(format!("{label} index is out of range")));
    }
    Ok(())
}

fn slice_pointer<T>(values: &[T]) -> *const T {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}

fn init<T>(initializer: unsafe extern "C" fn(*mut T, usize, u32) -> sys::bg_status) -> Result<T> {
    let mut value = MaybeUninit::<T>::uninit();
    // SAFETY: value is correctly sized writable storage and the ABI initializer
    // writes every field on success.
    status_result(unsafe { initializer(value.as_mut_ptr(), size_of::<T>(), sys::BG_ABI_VERSION) })?;
    // SAFETY: successful ABI initialization wrote the complete descriptor.
    Ok(unsafe { value.assume_init() })
}

macro_rules! zeroed_abi_value {
    ($type:ty) => {{
        // SAFETY: Every listed ABI type is a repr(C) aggregate containing only
        // numeric fields, raw pointers, and recursively zero-valid aggregates.
        unsafe { MaybeUninit::<$type>::zeroed().assume_init() }
    }};
}

fn bool_from_abi(value: u8, label: &str) -> Result<bool> {
    match value {
        0 => Ok(false),
        1 => Ok(true),
        other => Err(Error::local(
            ErrorCode::AbiMismatch,
            format!("native fixed64 {label} returned non-boolean value {other}"),
        )),
    }
}

fn raw_source_evidence(value: Fixed64SourceEvidence) -> sys::bg_docking_fixed64_source_evidence_v1 {
    sys::bg_docking_fixed64_source_evidence_v1 {
        receipt_sha256: value.receipt_sha256,
        proposal_sha256: value.proposal_sha256,
        coordinate_sha256: value.coordinate_sha256,
        reserved: [0; 2],
    }
}

fn raw_coordinate_source(
    value: Fixed64CoordinateSource<'_>,
    ligand_atom_count: u64,
) -> sys::bg_docking_fixed64_coordinate_source_v1 {
    sys::bg_docking_fixed64_coordinate_source_v1 {
        source: raw_source_evidence(value.evidence),
        ligand_atom_count,
        x_angstrom: value.coordinates.x_angstrom.as_ptr(),
        y_angstrom: value.coordinates.y_angstrom.as_ptr(),
        z_angstrom: value.coordinates.z_angstrom.as_ptr(),
        reserved: [0; 4],
    }
}

fn validate_source(
    value: Fixed64CoordinateSource<'_>,
    ligand_atom_count: usize,
    label: &str,
) -> Result<()> {
    if value.coordinates.validate()? != ligand_atom_count {
        return Err(invalid(format!(
            "{label} coordinate count must match the fixed64 ligand atom count"
        )));
    }
    for (digest, name) in [
        (value.evidence.receipt_sha256, "receipt"),
        (value.evidence.proposal_sha256, "proposal"),
        (value.evidence.coordinate_sha256, "coordinate"),
    ] {
        if !digest_present(&digest) {
            return Err(invalid(format!("{label} {name} SHA-256 is absent")));
        }
    }
    if canonical_coordinate_sha256(value.coordinates) != value.evidence.coordinate_sha256 {
        return Err(invalid(format!(
            "{label} coordinate SHA-256 does not match its supplied coordinates"
        )));
    }
    Ok(())
}

fn validate_run_input(
    input: Fixed64RunInput<'_>,
    ligand_atom_count: usize,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
) -> Result<()> {
    const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    validate_source(input.exact_source, ligand_atom_count, "exact V1.1 source")?;
    if input.exact_source.evidence.receipt_sha256
        != input.exact_source_evidence.source_receipt_sha256
        || input.exact_source.evidence.proposal_sha256
            != input.exact_source_evidence.proposal_sha256
        || input.exact_source.evidence.coordinate_sha256
            != input.exact_source_evidence.ligand_coordinate_sha256
    {
        return Err(invalid(
            "fixed64 exact source evidence and coordinate payload are cross-wired",
        ));
    }
    for (digest, label) in [
        (
            input.exact_source_evidence.source_receipt_sha256,
            "exact source receipt",
        ),
        (
            input.exact_source_evidence.proposal_sha256,
            "exact proposal",
        ),
        (
            input.exact_source_evidence.ligand_coordinate_sha256,
            "exact ligand coordinate",
        ),
        (
            input.exact_source_evidence.receptor_coordinate_sha256,
            "exact receptor coordinate",
        ),
        (
            input.exact_source_evidence.prepared_ligand_topology_sha256,
            "prepared ligand topology",
        ),
        (
            input
                .exact_source_evidence
                .prepared_receptor_topology_sha256,
            "prepared receptor topology",
        ),
        (
            input.exact_source_evidence.ligand_vdw_radii_sha256,
            "ligand vdw radii",
        ),
        (
            input.exact_source_evidence.ligand_heavy_atom_mask_sha256,
            "ligand heavy-atom mask",
        ),
        (
            input.exact_source_evidence.receptor_vdw_radii_sha256,
            "receptor vdw radii",
        ),
        (
            input.predeclared_refinement_policy_sha256,
            "predeclared refinement policy",
        ),
    ] {
        if !digest_present(&digest) {
            return Err(invalid(format!("fixed64 {label} SHA-256 is absent")));
        }
    }
    if input
        .exact_source_evidence
        .prepared_receptor_topology_sha256
        != receptor_system_sha256
        || input.exact_source_evidence.prepared_ligand_topology_sha256 != ligand_system_sha256
    {
        return Err(invalid(
            "fixed64 producer prepared topology identity is cross-wired",
        ));
    }
    for (source, label) in input
        .v7_control_sources
        .iter()
        .map(|source| (source.source, "V7 control source"))
        .chain(
            input
                .conformer_sources
                .iter()
                .map(|source| (source.source, "conformer source")),
        )
        .chain(
            input
                .retained_sources
                .iter()
                .map(|source| (source.source, "retained source")),
        )
    {
        validate_source(source, ligand_atom_count, label)?;
    }
    for feature in input.atomic_features {
        if !digest_present(&feature.receipt_sha256) {
            return Err(invalid("fixed64 atomic-feature receipt SHA-256 is absent"));
        }
    }
    for geometry in input.feature_geometries {
        if !digest_present(&geometry.allocation_feature_receipt_sha256)
            || !digest_present(&geometry.feature_geometry_receipt_sha256)
        {
            return Err(invalid(
                "fixed64 feature geometry receipt SHA-256 is absent",
            ));
        }
    }
    if input.feature_geometries.is_empty() {
        if digest_present(&input.feature_geometry_inventory_sha256) {
            return Err(invalid(
                "empty fixed64 feature geometry inventory must use a zero SHA-256",
            ));
        }
    } else if !digest_present(&input.feature_geometry_inventory_sha256) {
        return Err(invalid(
            "non-empty fixed64 feature geometry inventory SHA-256 is absent",
        ));
    }
    if !finite(&input.pocket_normal)
        || input
            .pocket_normal
            .iter()
            .all(|component| *component == 0.0)
        || !input.rmsd_threshold_angstrom.is_finite()
        || input.rmsd_threshold_angstrom <= 0.0
    {
        return Err(invalid(
            "fixed64 pocket normal and RMSD threshold must be finite and non-zero",
        ));
    }
    for (length, label) in [
        (input.candidate_modes.len(), "candidate modes"),
        (input.rigid_max_steps.len(), "rigid step budgets"),
        (
            input.proposal_is_torsion_eligible.len(),
            "torsion eligibility",
        ),
        (input.torsion_max_steps.len(), "torsion step budgets"),
    ] {
        if length != CANDIDATE_COUNT {
            return Err(invalid(format!(
                "fixed64 {label} must contain exactly {CANDIDATE_COUNT} values"
            )));
        }
    }
    if input
        .proposal_is_torsion_eligible
        .iter()
        .any(|value| *value > 1)
    {
        return Err(invalid(
            "fixed64 torsion eligibility must contain only 0 or 1",
        ));
    }
    let coordinate_count = ligand_atom_count
        .checked_mul(CANDIDATE_COUNT)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 baseline torsion coordinate denominator overflows usize",
            )
        })?;
    if input.baseline_torsion_angles_radians.len() != coordinate_count
        || !finite(input.baseline_torsion_angles_radians)
    {
        return Err(invalid(
            "fixed64 baseline torsion angles must be finite and match 64 × ligand atoms",
        ));
    }
    Ok(())
}

const fn independent_source_evidence(
    value: Fixed64SourceEvidence,
) -> IndependentFixed64SourceEvidence {
    IndependentFixed64SourceEvidence {
        receipt_sha256: value.receipt_sha256,
        proposal_sha256: value.proposal_sha256,
        coordinate_sha256: value.coordinate_sha256,
    }
}

fn independent_allocation(input: Fixed64RunInput<'_>) -> Result<IndependentFixed64Allocation> {
    let exact = input.exact_source_evidence;
    let inventory = IndependentFixed64FeatureInventory::new(
        IndependentFixed64ExactSource {
            source_receipt_sha256: exact.source_receipt_sha256,
            proposal_sha256: exact.proposal_sha256,
            ligand_coordinate_sha256: exact.ligand_coordinate_sha256,
            receptor_coordinate_sha256: exact.receptor_coordinate_sha256,
            prepared_ligand_topology_sha256: exact.prepared_ligand_topology_sha256,
            prepared_receptor_topology_sha256: exact.prepared_receptor_topology_sha256,
            ligand_vdw_radii_sha256: exact.ligand_vdw_radii_sha256,
            ligand_heavy_atom_mask_sha256: exact.ligand_heavy_atom_mask_sha256,
            receptor_vdw_radii_sha256: exact.receptor_vdw_radii_sha256,
        },
        input
            .atomic_features
            .iter()
            .map(|feature| IndependentFixed64AtomicFeature {
                kind: feature.kind.as_independent(),
                receipt_sha256: feature.receipt_sha256,
            })
            .collect(),
        input
            .v7_control_sources
            .iter()
            .map(|source| IndependentFixed64IndexedSource {
                source_index: source.source_index,
                source: independent_source_evidence(source.source.evidence),
            })
            .collect(),
        input
            .conformer_sources
            .iter()
            .map(|source| IndependentFixed64ConformerSource {
                rank: source.rank,
                source: independent_source_evidence(source.source.evidence),
            })
            .collect(),
        input
            .retained_sources
            .iter()
            .map(|source| IndependentFixed64IndexedSource {
                source_index: source.source_index,
                source: independent_source_evidence(source.source.evidence),
            })
            .collect(),
    )
    .map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 allocation rejected safe input: {error}"),
        )
    })?;
    IndependentFixed64Allocation::build(inventory).map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 allocation derivation failed: {error}"),
        )
    })
}

fn independent_feature_geometry_inventory(
    input: Fixed64RunInput<'_>,
) -> Result<Option<IndependentFixed64FeatureGeometryInventory>> {
    if input.feature_geometries.is_empty() {
        return Ok(None);
    }
    let mut features = Vec::with_capacity(input.feature_geometries.len());
    for geometry in input.feature_geometries {
        let atom_indices = geometry
            .atom_indices
            .iter()
            .copied()
            .map(|index| {
                usize::try_from(index).map_err(|_| {
                    Error::local(
                        ErrorCode::CapacityOverflow,
                        "fixed64 feature-geometry atom index does not fit usize",
                    )
                })
            })
            .collect::<Result<Vec<_>>>()?;
        let feature = IndependentFixed64FeatureGeometry::new(
            geometry.kind.as_independent(),
            geometry.allocation_feature_receipt_sha256,
            atom_indices,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 feature geometry rejected safe input: {error}"),
            )
        })?;
        if feature.receipt_sha256() != geometry.feature_geometry_receipt_sha256 {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "fixed64 feature-geometry receipt was not independently rederived",
            ));
        }
        features.push(feature);
    }
    let inventory = IndependentFixed64FeatureGeometryInventory::new(features).map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 feature inventory rejected safe input: {error}"),
        )
    })?;
    if inventory.receipt_sha256() != input.feature_geometry_inventory_sha256 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "fixed64 feature-geometry inventory receipt was not independently rederived",
        ));
    }
    Ok(Some(inventory))
}

fn independent_placement_source(
    source: Fixed64CoordinateSource<'_>,
) -> Result<IndependentFixed64PlacementSource> {
    IndependentFixed64PlacementSource::new(
        independent_source_evidence(source.evidence),
        position_soa_to_vec3(source.coordinates),
    )
    .map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 placement source rejected safe input: {error}"),
        )
    })
}

/// Owned complete fixed64 native pipeline tied to its creating context.
///
/// The handle is deliberately neither `Send` nor `Sync`; the native ABI
/// requires external synchronization and exact context identity.
///
/// ```compile_fail
/// use betelgeuze_runtime::Fixed64Pipeline;
/// fn require_send_sync<T: Send + Sync>() {}
/// require_send_sync::<Fixed64Pipeline<'static>>();
/// ```
pub struct Fixed64Pipeline<'context> {
    handle: NonNull<sys::bg_docking_fixed64_pipeline_v1>,
    replay_admission_handle: NonNull<sys::bg_docking_geometric_admission_v1>,
    _context: &'context Context,
    backend: Backend,
    receptor_atom_count: usize,
    ligand_atom_count: usize,
    ligand_heavy_atom_count: u64,
    geometric_hard_rejection_minimum_vdw_ratio: f64,
    geometric_max_batch_exact_pair_evaluations: u64,
    geometric_input: IndependentFixed64GeometricInput,
    rigid_v2_config: IndependentRigidV2Config,
    rigid_v3_config: IndependentRigidV3Config,
    rigid_clearance_config: IndependentRigidV3Config,
    scorer_context: IndependentScorerContext,
    maximum_torsion_steps: u64,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    authority_input_receipt_sha256: Sha256,
    backend_receipt_sha256: Sha256,
    pocket_center_angstrom: [f64; 3],
    expected_admission_context_receipt_sha256: Sha256,
    expected_refinement_context_receipt_sha256: Sha256,
    expected_scorer_context_receipt_sha256: Sha256,
    expected_validity_context_receipt_sha256: Sha256,
    expected_component_binding_receipt_sha256: Sha256,
    rotatable_child_atom_indices: Vec<u64>,
    validity_exclusion_count: u64,
    validity_chirality_count: u64,
    validity_contact_cell_size_angstrom: f64,
    validity_receptor_cells: HashMap<(i64, i64, i64), u64>,
    validity_context: IndependentValidityContext,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

struct PipelineHandleGuard(NonNull<sys::bg_docking_fixed64_pipeline_v1>);

impl PipelineHandleGuard {
    fn into_inner(self) -> NonNull<sys::bg_docking_fixed64_pipeline_v1> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for PipelineHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_fixed64_pipeline_v1_destroy(self.0.as_ptr()) };
    }
}

struct GeometricAdmissionHandleGuard(NonNull<sys::bg_docking_geometric_admission_v1>);

impl GeometricAdmissionHandleGuard {
    fn into_inner(self) -> NonNull<sys::bg_docking_geometric_admission_v1> {
        let handle = self.0;
        std::mem::forget(self);
        handle
    }
}

impl Drop for GeometricAdmissionHandleGuard {
    fn drop(&mut self) {
        // SAFETY: the guard owns this non-null handle until into_inner transfers it.
        unsafe { sys::bg_docking_geometric_admission_v1_destroy(self.0.as_ptr()) };
    }
}

fn validity_cell_component(value: f64, cell_size: f64) -> Result<i64> {
    let component = (value / cell_size).floor();
    const I64_MIN_INCLUSIVE: f64 = -9_223_372_036_854_775_808.0;
    const I64_MAX_EXCLUSIVE: f64 = 9_223_372_036_854_775_808.0;
    if !component.is_finite() || !(I64_MIN_INCLUSIVE..I64_MAX_EXCLUSIVE).contains(&component) {
        return Err(invalid(
            "fixed64 receptor coordinate is outside the validity cell-key range",
        ));
    }
    Ok(component as i64)
}

fn validity_receptor_cells(
    coordinates: PositionSoa<'_>,
    cell_size: f64,
) -> Result<HashMap<(i64, i64, i64), u64>> {
    if !cell_size.is_finite() || cell_size <= 0.0 {
        return Err(invalid(
            "fixed64 validity contact-cell size must be finite and positive",
        ));
    }
    let mut cells = HashMap::new();
    for atom in 0..coordinates.x_angstrom.len() {
        let key = (
            validity_cell_component(coordinates.x_angstrom[atom], cell_size)?,
            validity_cell_component(coordinates.y_angstrom[atom], cell_size)?,
            validity_cell_component(coordinates.z_angstrom[atom], cell_size)?,
        );
        let count = cells.entry(key).or_insert(0_u64);
        *count = count.checked_add(1).ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 validity receptor-cell occupancy overflowed",
            )
        })?;
    }
    Ok(cells)
}

fn position_soa_to_vec3(coordinates: PositionSoa<'_>) -> Vec<Vec3> {
    coordinates
        .x_angstrom
        .iter()
        .zip(coordinates.y_angstrom)
        .zip(coordinates.z_angstrom)
        .map(|((x, y), z)| Vec3::new(*x, *y, *z))
        .collect()
}

fn u64_pair_to_usize(pair: Fixed64Pair, label: &str) -> Result<[usize; 2]> {
    Ok([
        usize::try_from(pair.atom_i).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} atom i does not fit usize"),
            )
        })?,
        usize::try_from(pair.atom_j).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} atom j does not fit usize"),
            )
        })?,
    ])
}

fn u64_donor_to_usize(donor: Fixed64Donor, label: &str) -> Result<IndependentScorerDonor> {
    Ok(IndependentScorerDonor {
        donor_atom_index: usize::try_from(donor.donor_atom_index).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} donor atom does not fit usize"),
            )
        })?,
        hydrogen_atom_index: usize::try_from(donor.hydrogen_atom_index).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} hydrogen atom does not fit usize"),
            )
        })?,
    })
}

fn u64_rotor_to_usize(rotor: Fixed64Rotor) -> Result<[usize; 4]> {
    let convert = |value| {
        usize::try_from(value).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 scorer rotor atom does not fit usize",
            )
        })
    };
    Ok([
        convert(rotor.atom_i)?,
        convert(rotor.atom_j)?,
        convert(rotor.atom_k)?,
        convert(rotor.atom_l)?,
    ])
}

fn independent_rigid_v2_config(
    value: &sys::bg_docking_rigid_v2_config_v1,
) -> Result<IndependentRigidV2Config> {
    Ok(IndependentRigidV2Config {
        overlap_scale: value.overlap_scale,
        maximum_step_angstrom: value.maximum_step_angstrom,
        minimum_step_angstrom: value.minimum_step_angstrom,
        maximum_total_translation_angstrom: value.maximum_total_translation_angstrom,
        maximum_backtracking_evaluations: usize::try_from(value.maximum_backtracking_evaluations)
            .map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 rigid backtracking budget does not fit usize",
            )
        })?,
        penalty_tolerance: value.penalty_tolerance,
        epsilon_angstrom: value.epsilon_angstrom,
    })
}

fn independent_rigid_v3_config(
    value: &sys::bg_docking_rigid_v3_config_v1,
) -> Result<IndependentRigidV3Config> {
    Ok(IndependentRigidV3Config {
        v2: independent_rigid_v2_config(&value.v2)?,
        maximum_rotation_step_radians: value.maximum_rotation_step_radians,
        minimum_rotation_step_radians: value.minimum_rotation_step_radians,
        maximum_total_rotation_radians: value.maximum_total_rotation_radians,
        maximum_rotation_steps: usize::try_from(value.maximum_rotation_steps).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 rigid rotation budget does not fit usize",
            )
        })?,
        minimum_rotation_relative_penalty_reduction: value
            .minimum_rotation_relative_penalty_reduction,
        maximum_centroid_offset_angstrom: value.maximum_centroid_offset_angstrom,
    })
}

fn canonical_pocket_normal(value: [f64; 3]) -> Result<[f64; 3]> {
    if value.iter().any(|component| {
        !component.is_finite() || component.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
    }) {
        return Err(invalid(
            "fixed64 pocket normal is outside its finite safety envelope",
        ));
    }
    let maximum = value[0].abs().max(value[1].abs()).max(value[2].abs());
    if maximum <= 1.0e-12 {
        return Err(invalid("fixed64 pocket normal is degenerate"));
    }
    let scaled = Vec3::new(value[0] / maximum, value[1] / maximum, value[2] / maximum);
    // This receipt boundary mirrors the native C++ `std::hypot` sequence.
    // The dev-only search oracle deliberately uses `libm`, which can differ by
    // a few ULPs and therefore must not define the ABI digest here.
    let scaled_norm = scaled.x.hypot(scaled.y).hypot(scaled.z);
    if !scaled_norm.is_finite() || scaled_norm <= 0.0 {
        return Err(invalid("fixed64 pocket normal could not be normalized"));
    }
    let inverse = (1.0 / maximum) / scaled_norm;
    let mut result = [value[0] * inverse, value[1] * inverse, value[2] * inverse];
    for component in &mut result {
        if *component == 0.0 {
            *component = 0.0;
        }
    }
    Ok(result)
}

impl<'context> Fixed64Pipeline<'context> {
    pub fn new(context: &'context Context, scientific: Fixed64PipelineContext<'_>) -> Result<Self> {
        let counts = scientific.validate()?;
        let expected_backend = context.backend()?;
        let device_ordinal = context.device_ordinal()?;
        let receptor_count = usize::try_from(counts.receptor_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 receptor atom count does not fit usize",
            )
        })?;
        let ligand_count = usize::try_from(counts.ligand_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 ligand atom count does not fit usize",
            )
        })?;

        let receptor_donor_atom = scientific
            .receptor
            .donors
            .iter()
            .map(|donor| donor.donor_atom_index)
            .collect::<Vec<_>>();
        let receptor_hydrogen_atom = scientific
            .receptor
            .donors
            .iter()
            .map(|donor| donor.hydrogen_atom_index)
            .collect::<Vec<_>>();
        let ligand_donor_atom = scientific
            .ligand
            .donors
            .iter()
            .map(|donor| donor.donor_atom_index)
            .collect::<Vec<_>>();
        let ligand_hydrogen_atom = scientific
            .ligand
            .donors
            .iter()
            .map(|donor| donor.hydrogen_atom_index)
            .collect::<Vec<_>>();
        let exclusion_i = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| pair.atom_i)
            .collect::<Vec<_>>();
        let exclusion_j = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| pair.atom_j)
            .collect::<Vec<_>>();
        let bond_i = scientific
            .ligand
            .bonds
            .iter()
            .map(|pair| pair.atom_i)
            .collect::<Vec<_>>();
        let bond_j = scientific
            .ligand
            .bonds
            .iter()
            .map(|pair| pair.atom_j)
            .collect::<Vec<_>>();
        let internal_i = scientific
            .ligand
            .internal_pairs
            .iter()
            .map(|pair| pair.atom_i)
            .collect::<Vec<_>>();
        let internal_j = scientific
            .ligand
            .internal_pairs
            .iter()
            .map(|pair| pair.atom_j)
            .collect::<Vec<_>>();
        let rotor_i = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_i)
            .collect::<Vec<_>>();
        let rotor_j = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_j)
            .collect::<Vec<_>>();
        let rotor_k = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_k)
            .collect::<Vec<_>>();
        let rotor_l = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_l)
            .collect::<Vec<_>>();
        let chirality_center = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.center_atom)
            .collect::<Vec<_>>();
        let chirality_i = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.atom_i)
            .collect::<Vec<_>>();
        let chirality_j = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.atom_j)
            .collect::<Vec<_>>();
        let chirality_k = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.atom_k)
            .collect::<Vec<_>>();

        let mut admission = init(sys::bg_docking_geometric_admission_context_soa_v1_init)?;
        admission.receptor_atom_count = counts.receptor_atom_count;
        admission.ligand_atom_count = counts.ligand_atom_count;
        admission.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        admission.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        admission.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        admission.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        admission.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        admission.ligand_heavy_atom_mask = scientific.ligand.heavy_atom_mask.as_ptr();
        admission.pocket_center_angstrom = scientific.pocket_center_angstrom;
        admission.pocket_radius_angstrom = scientific.pocket_radius_angstrom;
        assign_shared_identities(&mut admission, scientific.identities);

        let mut rigid = init(sys::bg_docking_rigid_refinement_context_soa_v1_init)?;
        rigid.receptor_atom_count = counts.receptor_atom_count;
        rigid.ligand_atom_count = counts.ligand_atom_count;
        rigid.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        rigid.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        rigid.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        rigid.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        rigid.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        rigid.pocket_center_angstrom = scientific.pocket_center_angstrom;
        rigid.pocket_radius_angstrom = scientific.pocket_radius_angstrom;

        let mut torsion = init(sys::bg_docking_torsion_v7_context_soa_v1_init)?;
        torsion.receptor_atom_count = counts.receptor_atom_count;
        torsion.ligand_atom_count = counts.ligand_atom_count;
        torsion.rotor_count = checked_count(scientific.ligand.rotatable_child_atom_index.len())?;
        torsion.internal_pair_count = checked_count(scientific.ligand.internal_pairs.len())?;
        torsion.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        torsion.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        torsion.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        torsion.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        torsion.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        torsion.pocket_center_angstrom = scientific.pocket_center_angstrom;
        torsion.parent_atom_index = scientific.ligand.parent_atom_index.as_ptr();
        torsion.rotatable_child_atom_index =
            slice_pointer(scientific.ligand.rotatable_child_atom_index);
        torsion.internal_pair_atom_i = slice_pointer(&internal_i);
        torsion.internal_pair_atom_j = slice_pointer(&internal_j);

        let mut scorer = init(sys::bg_docking_scorer_v1_context_soa_v1_init)?;
        scorer.receptor_atom_count = counts.receptor_atom_count;
        scorer.ligand_atom_count = counts.ligand_atom_count;
        scorer.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        scorer.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        scorer.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        scorer.receptor_charge_elementary = scientific.receptor.charge_elementary.as_ptr();
        scorer.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        scorer.receptor_epsilon_kcal_per_mol = scientific.receptor.epsilon_kcal_per_mol.as_ptr();
        scorer.receptor_hydrophobic = scientific.receptor.hydrophobic_mask.as_ptr();
        scorer.receptor_acceptor = scientific.receptor.acceptor_mask.as_ptr();
        scorer.ligand_reference_x_angstrom =
            scientific.ligand.reference_coordinates.x_angstrom.as_ptr();
        scorer.ligand_reference_y_angstrom =
            scientific.ligand.reference_coordinates.y_angstrom.as_ptr();
        scorer.ligand_reference_z_angstrom =
            scientific.ligand.reference_coordinates.z_angstrom.as_ptr();
        scorer.ligand_charge_elementary = scientific.ligand.charge_elementary.as_ptr();
        scorer.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        scorer.ligand_epsilon_kcal_per_mol = scientific.ligand.epsilon_kcal_per_mol.as_ptr();
        scorer.ligand_hydrophobic = scientific.ligand.hydrophobic_mask.as_ptr();
        scorer.ligand_acceptor = scientific.ligand.acceptor_mask.as_ptr();
        scorer.receptor_donor_count = checked_count(receptor_donor_atom.len())?;
        scorer.receptor_donor_atom_index = slice_pointer(&receptor_donor_atom);
        scorer.receptor_hydrogen_atom_index = slice_pointer(&receptor_hydrogen_atom);
        scorer.ligand_donor_count = checked_count(ligand_donor_atom.len())?;
        scorer.ligand_donor_atom_index = slice_pointer(&ligand_donor_atom);
        scorer.ligand_hydrogen_atom_index = slice_pointer(&ligand_hydrogen_atom);
        scorer.ligand_exclusion_count = checked_count(exclusion_i.len())?;
        scorer.ligand_exclusion_atom_i = slice_pointer(&exclusion_i);
        scorer.ligand_exclusion_atom_j = slice_pointer(&exclusion_j);
        scorer.rotor_count = checked_count(rotor_i.len())?;
        scorer.rotor_atom_i = slice_pointer(&rotor_i);
        scorer.rotor_atom_j = slice_pointer(&rotor_j);
        scorer.rotor_atom_k = slice_pointer(&rotor_k);
        scorer.rotor_atom_l = slice_pointer(&rotor_l);
        scorer.pocket_center_angstrom = scientific.pocket_center_angstrom;
        scorer.pocket_radius_angstrom = scientific.pocket_radius_angstrom;
        scorer.authority_input_receipt_sha256 =
            scientific.identities.authority_input_receipt_sha256;
        scorer.receptor_system_sha256 = scientific.identities.receptor_system_sha256;
        scorer.ligand_system_sha256 = scientific.identities.ligand_system_sha256;
        scorer.backend_receipt_sha256 = scientific.identities.backend_receipt_sha256;

        let mut validity = init(sys::bg_docking_pose_validity_context_soa_v1_init)?;
        validity.receptor_atom_count = counts.receptor_atom_count;
        validity.ligand_atom_count = counts.ligand_atom_count;
        validity.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        validity.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        validity.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        validity.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        validity.ligand_reference_x_angstrom =
            scientific.ligand.reference_coordinates.x_angstrom.as_ptr();
        validity.ligand_reference_y_angstrom =
            scientific.ligand.reference_coordinates.y_angstrom.as_ptr();
        validity.ligand_reference_z_angstrom =
            scientific.ligand.reference_coordinates.z_angstrom.as_ptr();
        validity.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        validity.bond_count = checked_count(bond_i.len())?;
        validity.bond_atom_i = slice_pointer(&bond_i);
        validity.bond_atom_j = slice_pointer(&bond_j);
        validity.ligand_exclusion_count = checked_count(exclusion_i.len())?;
        validity.ligand_exclusion_atom_i = slice_pointer(&exclusion_i);
        validity.ligand_exclusion_atom_j = slice_pointer(&exclusion_j);
        validity.chirality_center_count = checked_count(chirality_center.len())?;
        validity.chirality_center_atom = slice_pointer(&chirality_center);
        validity.chirality_atom_i = slice_pointer(&chirality_i);
        validity.chirality_atom_j = slice_pointer(&chirality_j);
        validity.chirality_atom_k = slice_pointer(&chirality_k);
        validity.pocket_center_angstrom = scientific.pocket_center_angstrom;
        validity.pocket_radius_angstrom = scientific.pocket_radius_angstrom;
        validity.authority_input_receipt_sha256 =
            scientific.identities.authority_input_receipt_sha256;
        validity.receptor_system_sha256 = scientific.identities.receptor_system_sha256;
        validity.ligand_system_sha256 = scientific.identities.ligand_system_sha256;
        validity.scorer_context_receipt_sha256 =
            scientific.identities.validity_scorer_context_receipt_sha256;
        validity.backend_receipt_sha256 = scientific.identities.backend_receipt_sha256;
        validity.contact_policy_sha256 = scientific.identities.contact_policy_sha256;
        let validity_exclusion_count = checked_count(scientific.ligand.exclusions.len())?;
        let validity_chirality_count = checked_count(scientific.ligand.chirality_centers.len())?;
        let ligand_heavy_atom_count = checked_count(
            scientific
                .ligand
                .heavy_atom_mask
                .iter()
                .filter(|value| **value != 0)
                .count(),
        )?;
        let geometric_hard_rejection_minimum_vdw_ratio = admission.hard_rejection_minimum_vdw_ratio;
        let geometric_max_batch_exact_pair_evaluations = admission.max_batch_exact_pair_evaluations;
        let maximum_torsion_steps = torsion.maximum_torsion_steps;
        let validity_contact_cell_size_angstrom = validity.contact_cell_size_angstrom;
        let validity_receptor_cells = validity_receptor_cells(
            scientific.receptor.coordinates,
            validity_contact_cell_size_angstrom,
        )?;
        let rotatable_child_atom_indices = scientific.ligand.rotatable_child_atom_index.to_vec();

        let receptor_coordinates = position_soa_to_vec3(scientific.receptor.coordinates);
        let ligand_reference_coordinates =
            position_soa_to_vec3(scientific.ligand.reference_coordinates);
        let geometric_input = IndependentFixed64GeometricInput::new(
            scientific.ligand.vdw_radius_angstrom.to_vec(),
            scientific
                .ligand
                .heavy_atom_mask
                .iter()
                .map(|value| *value != 0)
                .collect(),
            receptor_coordinates.clone(),
            scientific.receptor.vdw_radius_angstrom.to_vec(),
            Vec3::new(
                scientific.pocket_center_angstrom[0],
                scientific.pocket_center_angstrom[1],
                scientific.pocket_center_angstrom[2],
            ),
            scientific.pocket_radius_angstrom,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 geometric context rejected safe input: {error}"),
            )
        })?;
        let rigid_v2_config = independent_rigid_v2_config(&rigid.v2)?;
        let rigid_v3_config = independent_rigid_v3_config(&rigid.v3)?;
        let rigid_clearance_config = independent_rigid_v3_config(&rigid.clearance_v4)?;
        let scorer_config = IndependentScorerConfig::new(
            scorer.weights,
            scorer.electrostatic_dielectric,
            scorer.pair_cutoff_angstrom,
            scorer.hbond_distance_max_angstrom,
            scorer.polar_burial_distance_angstrom,
            usize::try_from(scorer.max_receptor_candidate_pairs).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 scorer receptor-pair capacity does not fit usize",
                )
            })?,
            usize::try_from(scorer.max_ligand_pair_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 scorer ligand-pair capacity does not fit usize",
                )
            })?,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 scorer config rejected safe input: {error}"),
            )
        })?;
        let receptor_atoms = (0..receptor_count)
            .map(|atom| IndependentScorerAtom {
                charge_elementary: scientific.receptor.charge_elementary[atom],
                vdw_radius_angstrom: scientific.receptor.vdw_radius_angstrom[atom],
                epsilon_kcal_per_mol: scientific.receptor.epsilon_kcal_per_mol[atom],
                hydrophobic: scientific.receptor.hydrophobic_mask[atom] != 0,
                acceptor: scientific.receptor.acceptor_mask[atom] != 0,
            })
            .collect::<Vec<_>>();
        let ligand_atoms = (0..ligand_count)
            .map(|atom| IndependentScorerAtom {
                charge_elementary: scientific.ligand.charge_elementary[atom],
                vdw_radius_angstrom: scientific.ligand.vdw_radius_angstrom[atom],
                epsilon_kcal_per_mol: scientific.ligand.epsilon_kcal_per_mol[atom],
                hydrophobic: scientific.ligand.hydrophobic_mask[atom] != 0,
                acceptor: scientific.ligand.acceptor_mask[atom] != 0,
            })
            .collect::<Vec<_>>();
        let receptor_donors = scientific
            .receptor
            .donors
            .iter()
            .map(|donor| u64_donor_to_usize(*donor, "receptor"))
            .collect::<Result<Vec<_>>>()?;
        let ligand_donors = scientific
            .ligand
            .donors
            .iter()
            .map(|donor| u64_donor_to_usize(*donor, "ligand"))
            .collect::<Result<Vec<_>>>()?;
        let scorer_exclusions = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| u64_pair_to_usize(*pair, "scorer exclusion"))
            .collect::<Result<Vec<_>>>()?;
        let scorer_rotors = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| u64_rotor_to_usize(*rotor))
            .collect::<Result<Vec<_>>>()?;
        let scorer_context = IndependentScorerContext::new(
            scientific.identities.authority_input_receipt_sha256,
            scientific.identities.receptor_system_sha256,
            scientific.identities.ligand_system_sha256,
            IndependentScorerBackend::RustCpu,
            scientific.identities.backend_receipt_sha256,
            receptor_coordinates.clone(),
            receptor_atoms,
            ligand_reference_coordinates.clone(),
            ligand_atoms,
            receptor_donors,
            ligand_donors,
            scorer_exclusions,
            scorer_rotors,
            Vec3::new(
                scientific.pocket_center_angstrom[0],
                scientific.pocket_center_angstrom[1],
                scientific.pocket_center_angstrom[2],
            ),
            scientific.pocket_radius_angstrom,
            scorer_config,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 scorer context rejected safe input: {error}"),
            )
        })?;
        let validity_config = IndependentValidityConfig::new(
            validity.bond_length_tolerance_angstrom,
            validity.ligand_self_clash_angstrom,
            validity.receptor_ligand_clash_angstrom,
            validity.rotation_tolerance,
            validity.chirality_volume_tolerance,
            validity.severe_overlap_scale,
            validity.contact_cell_size_angstrom,
            usize::try_from(validity.max_pair_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity pair capacity does not fit usize",
                )
            })?,
            usize::try_from(validity.max_cross_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity cross capacity does not fit usize",
                )
            })?,
            usize::try_from(validity.max_element_ligand_pair_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity element ligand capacity does not fit usize",
                )
            })?,
            usize::try_from(validity.max_element_receptor_candidate_pairs).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity element receptor capacity does not fit usize",
                )
            })?,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 validity config rejected safe input: {error}"),
            )
        })?;
        let bond_pairs = scientific
            .ligand
            .bonds
            .iter()
            .map(|pair| u64_pair_to_usize(*pair, "bond"))
            .collect::<Result<Vec<_>>>()?;
        let excluded_pairs = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| u64_pair_to_usize(*pair, "exclusion"))
            .collect::<Result<Vec<_>>>()?;
        let chirality_centers = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| {
                Ok([
                    usize::try_from(center.center_atom).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality center does not fit usize",
                        )
                    })?,
                    usize::try_from(center.atom_i).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality atom i does not fit usize",
                        )
                    })?,
                    usize::try_from(center.atom_j).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality atom j does not fit usize",
                        )
                    })?,
                    usize::try_from(center.atom_k).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality atom k does not fit usize",
                        )
                    })?,
                ])
            })
            .collect::<Result<Vec<_>>>()?;
        let validity_context = IndependentValidityContext::new(
            scientific.identities.authority_input_receipt_sha256,
            scientific.identities.receptor_system_sha256,
            scientific.identities.ligand_system_sha256,
            scientific.identities.validity_scorer_context_receipt_sha256,
            IndependentValidityBackend::RustCpu,
            scientific.identities.backend_receipt_sha256,
            scientific.identities.contact_policy_sha256,
            ligand_reference_coordinates,
            receptor_coordinates,
            scientific.ligand.vdw_radius_angstrom.to_vec(),
            scientific.receptor.vdw_radius_angstrom.to_vec(),
            bond_pairs,
            excluded_pairs,
            chirality_centers,
            Vec3::new(
                scientific.pocket_center_angstrom[0],
                scientific.pocket_center_angstrom[1],
                scientific.pocket_center_angstrom[2],
            ),
            scientific.pocket_radius_angstrom,
            validity_config,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 validity context rejected safe input: {error}"),
            )
        })?;
        let expected_admission_context_receipt_sha256 = canonical_admission_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &admission,
        );
        let expected_refinement_context_receipt_sha256 = canonical_refinement_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &rigid,
            &torsion,
        );
        let expected_scorer_context_receipt_sha256 = canonical_scorer_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &scorer,
            &receptor_donor_atom,
            &receptor_hydrogen_atom,
            &ligand_donor_atom,
            &ligand_hydrogen_atom,
            &exclusion_i,
            &exclusion_j,
            &rotor_i,
            &rotor_j,
            &rotor_k,
            &rotor_l,
        );
        let expected_validity_context_receipt_sha256 = canonical_validity_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &validity,
            &bond_i,
            &bond_j,
            &exclusion_i,
            &exclusion_j,
            &chirality_center,
            &chirality_i,
            &chirality_j,
            &chirality_k,
        );
        let expected_component_binding_receipt_sha256 = canonical_component_binding_receipt(
            expected_backend,
            device_ordinal,
            expected_admission_context_receipt_sha256,
            expected_refinement_context_receipt_sha256,
            expected_scorer_context_receipt_sha256,
            expected_validity_context_receipt_sha256,
        );

        let mut handle = ptr::null_mut();
        // SAFETY: every descriptor points to validated slices that remain live
        // for this call; the native constructor deep-copies all channels.
        status_result(unsafe {
            sys::bg_docking_fixed64_pipeline_v1_create(
                context.handle.as_ptr(),
                &admission,
                &rigid,
                &torsion,
                &scorer,
                &validity,
                &mut handle,
            )
        })?;
        let handle = NonNull::new(handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native fixed64 pipeline creation succeeded with a null handle",
            )
        })?;
        let handle = PipelineHandleGuard(handle);
        let mut raw_backend = sys::BG_BACKEND_AUTO;
        // SAFETY: handle is live and raw_backend is valid writable storage.
        status_result(unsafe {
            sys::bg_docking_fixed64_pipeline_v1_get_backend(handle.0.as_ptr(), &mut raw_backend)
        })?;
        let backend = Backend::from_raw(raw_backend)?;
        if backend != expected_backend {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline backend changed during construction",
            ));
        }
        let mut replay_admission_handle = ptr::null_mut();
        // SAFETY: the validated descriptor remains live for this call and the
        // native constructor deep-copies every molecular channel.
        status_result(unsafe {
            sys::bg_docking_geometric_admission_v1_create(
                context.handle.as_ptr(),
                &admission,
                &mut replay_admission_handle,
            )
        })?;
        let replay_admission_handle = NonNull::new(replay_admission_handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native replay admission creation succeeded with a null handle",
            )
        })?;
        let replay_admission_handle = GeometricAdmissionHandleGuard(replay_admission_handle);
        let mut replay_backend = sys::BG_BACKEND_AUTO;
        // SAFETY: the guarded handle is live and replay_backend is writable.
        status_result(unsafe {
            sys::bg_docking_geometric_admission_v1_get_backend(
                replay_admission_handle.0.as_ptr(),
                &mut replay_backend,
            )
        })?;
        if Backend::from_raw(replay_backend)? != backend {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native replay admission backend changed during construction",
            ));
        }
        Ok(Self {
            handle: handle.into_inner(),
            replay_admission_handle: replay_admission_handle.into_inner(),
            _context: context,
            backend,
            receptor_atom_count: receptor_count,
            ligand_atom_count: ligand_count,
            ligand_heavy_atom_count,
            geometric_hard_rejection_minimum_vdw_ratio,
            geometric_max_batch_exact_pair_evaluations,
            geometric_input,
            rigid_v2_config,
            rigid_v3_config,
            rigid_clearance_config,
            scorer_context,
            maximum_torsion_steps,
            receptor_system_sha256: scientific.identities.receptor_system_sha256,
            ligand_system_sha256: scientific.identities.ligand_system_sha256,
            authority_input_receipt_sha256: scientific.identities.authority_input_receipt_sha256,
            backend_receipt_sha256: scientific.identities.backend_receipt_sha256,
            pocket_center_angstrom: scientific.pocket_center_angstrom,
            expected_admission_context_receipt_sha256,
            expected_refinement_context_receipt_sha256,
            expected_scorer_context_receipt_sha256,
            expected_validity_context_receipt_sha256,
            expected_component_binding_receipt_sha256,
            rotatable_child_atom_indices,
            validity_exclusion_count,
            validity_chirality_count,
            validity_contact_cell_size_angstrom,
            validity_receptor_cells,
            validity_context,
            _not_send_or_sync: PhantomData,
        })
    }

    pub const fn backend(&self) -> Backend {
        self.backend
    }

    pub const fn receptor_atom_count(&self) -> usize {
        self.receptor_atom_count
    }

    pub const fn ligand_atom_count(&self) -> usize {
        self.ligand_atom_count
    }

    pub fn run(&self, input: Fixed64RunInput<'_>) -> Result<Fixed64PipelineReceipt> {
        const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        const TOP_K_LIMIT: usize = sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize;
        const MOVE_COUNT: usize = CANDIDATE_COUNT * sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
        validate_run_input(
            input,
            self.ligand_atom_count,
            self.receptor_system_sha256,
            self.ligand_system_sha256,
        )?;
        let raw_pocket_normal = input.pocket_normal;
        let input = Fixed64RunInput {
            pocket_normal: canonical_pocket_normal(input.pocket_normal)?,
            ..input
        };
        // The producer normalizes the caller vector once, then the indexed-SO3
        // component normalizes that canonical producer value once more. Keep
        // both stages explicit so replay uses the same frozen seed bits.
        let component_pocket_normal = canonical_pocket_normal(input.pocket_normal)?;
        let expected_sources: [Option<Fixed64CoordinateSource<'_>>; CANDIDATE_COUNT] =
            std::array::from_fn(|slot| fixed64_source_for_slot(input, slot));
        let coordinate_count = self
            .ligand_atom_count
            .checked_mul(CANDIDATE_COUNT)
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 output coordinate denominator overflows usize",
                )
            })?;
        let coordinate_count_u64 = checked_count(coordinate_count)?;
        let receptor_atom_count_u64 = checked_count(self.receptor_atom_count)?;
        let ligand_atom_count_u64 = checked_count(self.ligand_atom_count)?;
        let expected_allocation = independent_allocation(input)?;
        let expected_feature_geometry_inventory = independent_feature_geometry_inventory(input)?;
        let source_bundle_receipt_sha256 = canonical_source_bundle_receipt(
            input,
            expected_allocation.receipt_sha256(),
            ligand_atom_count_u64,
            self.pocket_center_angstrom,
            self.authority_input_receipt_sha256,
            self.receptor_system_sha256,
            self.ligand_system_sha256,
            self.backend_receipt_sha256,
        )?;
        let refinement_policy_receipt_sha256 = canonical_refinement_policy_receipt(
            self.expected_refinement_context_receipt_sha256,
            self.expected_component_binding_receipt_sha256,
            expected_allocation.receipt_sha256(),
            input,
        );
        let expected_receipt_graph = ExpectedPipelineReceiptGraph {
            allocation_inventory_sha256: expected_allocation.inventory_sha256(),
            allocation_receipt_sha256: expected_allocation.receipt_sha256(),
            source_bundle_receipt_sha256,
            admission_context_receipt_sha256: self.expected_admission_context_receipt_sha256,
            refinement_context_receipt_sha256: self.expected_refinement_context_receipt_sha256,
            scorer_context_receipt_sha256: self.expected_scorer_context_receipt_sha256,
            validity_context_receipt_sha256: self.expected_validity_context_receipt_sha256,
            component_binding_receipt_sha256: self.expected_component_binding_receipt_sha256,
            refinement_policy_receipt_sha256,
            authority_input_receipt_sha256: self.authority_input_receipt_sha256,
            receptor_system_sha256: self.receptor_system_sha256,
            ligand_system_sha256: self.ligand_system_sha256,
            backend_receipt_sha256: self.backend_receipt_sha256,
            backend: self.backend,
            receptor_atom_count: receptor_atom_count_u64,
            ligand_atom_count: ligand_atom_count_u64,
            ligand_heavy_atom_count: self.ligand_heavy_atom_count,
            geometric_max_batch_exact_pair_evaluations: self
                .geometric_max_batch_exact_pair_evaluations,
            pocket_center_angstrom: self.pocket_center_angstrom,
            pocket_radius_angstrom: self.geometric_input.pocket_radius_angstrom(),
            geometric_hard_rejection_minimum_vdw_ratio: self
                .geometric_hard_rejection_minimum_vdw_ratio,
        };

        let exact_evidence = sys::bg_docking_fixed64_exact_source_evidence_v1 {
            source_receipt_sha256: input.exact_source_evidence.source_receipt_sha256,
            proposal_sha256: input.exact_source_evidence.proposal_sha256,
            ligand_coordinate_sha256: input.exact_source_evidence.ligand_coordinate_sha256,
            receptor_coordinate_sha256: input.exact_source_evidence.receptor_coordinate_sha256,
            prepared_ligand_topology_sha256: input
                .exact_source_evidence
                .prepared_ligand_topology_sha256,
            prepared_receptor_topology_sha256: input
                .exact_source_evidence
                .prepared_receptor_topology_sha256,
            ligand_vdw_radii_sha256: input.exact_source_evidence.ligand_vdw_radii_sha256,
            ligand_heavy_atom_mask_sha256: input
                .exact_source_evidence
                .ligand_heavy_atom_mask_sha256,
            receptor_vdw_radii_sha256: input.exact_source_evidence.receptor_vdw_radii_sha256,
            reserved: [0; 4],
        };
        let atomic_features = input
            .atomic_features
            .iter()
            .map(
                |feature| sys::bg_docking_fixed64_atomic_feature_evidence_v1 {
                    kind: feature.kind.as_raw(),
                    reserved0: 0,
                    receipt_sha256: feature.receipt_sha256,
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let v7_evidence = input
            .v7_control_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_source_evidence_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    source: raw_source_evidence(source.source.evidence),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let conformer_evidence = input
            .conformer_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_conformer_source_evidence_v1 {
                    rank: source.rank,
                    reserved0: [0; 7],
                    source: raw_source_evidence(source.source.evidence),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let retained_evidence = input
            .retained_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_source_evidence_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    source: raw_source_evidence(source.source.evidence),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let mut allocation = init(sys::bg_docking_fixed64_allocation_input_v1_init)?;
        allocation.exact_v11_source = exact_evidence;
        allocation.atomic_feature_count = checked_count(atomic_features.len())?;
        allocation.atomic_features = slice_pointer(&atomic_features);
        allocation.v7_control_source_count = checked_count(v7_evidence.len())?;
        allocation.v7_control_sources = slice_pointer(&v7_evidence);
        allocation.conformer_source_count = checked_count(conformer_evidence.len())?;
        allocation.conformer_sources = slice_pointer(&conformer_evidence);
        allocation.retained_source_count = checked_count(retained_evidence.len())?;
        allocation.retained_sources = slice_pointer(&retained_evidence);

        let exact_source = raw_coordinate_source(input.exact_source, ligand_atom_count_u64);
        let v7_sources = input
            .v7_control_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_coordinate_source_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    payload: raw_coordinate_source(source.source, ligand_atom_count_u64),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let conformer_sources = input
            .conformer_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_conformer_coordinate_source_v1 {
                    rank: source.rank,
                    reserved0: [0; 7],
                    payload: raw_coordinate_source(source.source, ligand_atom_count_u64),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let retained_sources = input
            .retained_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_coordinate_source_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    payload: raw_coordinate_source(source.source, ligand_atom_count_u64),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let mut feature_atom_indices = Vec::new();
        let mut feature_rows = Vec::with_capacity(input.feature_geometries.len());
        for geometry in input.feature_geometries {
            let offset = checked_count(feature_atom_indices.len())?;
            feature_atom_indices.extend_from_slice(geometry.atom_indices);
            feature_rows.push(sys::bg_docking_fixed64_feature_geometry_row_v1 {
                kind: geometry.kind.as_raw(),
                reserved0: 0,
                allocation_feature_receipt_sha256: geometry.allocation_feature_receipt_sha256,
                atom_index_offset: offset,
                atom_index_count: checked_count(geometry.atom_indices.len())?,
                feature_geometry_receipt_sha256: geometry.feature_geometry_receipt_sha256,
                reserved: [0; 4],
            });
        }
        let mut producer_input = init(sys::bg_docking_fixed64_producer_input_v1_init)?;
        producer_input.allocation_input = &allocation;
        producer_input.exact_v11_source = &exact_source;
        producer_input.v7_control_source_count = checked_count(v7_sources.len())?;
        producer_input.v7_control_sources = slice_pointer(&v7_sources);
        producer_input.conformer_source_count = checked_count(conformer_sources.len())?;
        producer_input.conformer_sources = slice_pointer(&conformer_sources);
        producer_input.retained_source_count = checked_count(retained_sources.len())?;
        producer_input.retained_sources = slice_pointer(&retained_sources);
        producer_input.feature_geometry_count = checked_count(feature_rows.len())?;
        producer_input.feature_geometry_rows = slice_pointer(&feature_rows);
        producer_input.feature_atom_index_count = checked_count(feature_atom_indices.len())?;
        producer_input.feature_atom_indices = slice_pointer(&feature_atom_indices);
        producer_input.feature_geometry_inventory_sha256 = input.feature_geometry_inventory_sha256;
        // The native producer performs the same scale-stable normalization once.
        // Preserve the caller vector here while the independent receipt graph uses
        // the once-canonicalized copy above; feeding the canonical copy to native
        // would normalize it twice and change some vectors by several ULPs.
        producer_input.pocket_normal = raw_pocket_normal;

        let raw_modes = input
            .candidate_modes
            .iter()
            .map(|mode| mode.as_raw())
            .collect::<Vec<_>>();
        let mut pipeline_input = init(sys::bg_docking_fixed64_pipeline_input_v1_init)?;
        pipeline_input.producer_input = &producer_input;
        pipeline_input.rmsd_threshold_angstrom = input.rmsd_threshold_angstrom;
        pipeline_input.candidate_mode = raw_modes.as_ptr();
        pipeline_input.rigid_max_steps = input.rigid_max_steps.as_ptr();
        pipeline_input.proposal_is_torsion_eligible = input.proposal_is_torsion_eligible.as_ptr();
        pipeline_input.torsion_max_steps = input.torsion_max_steps.as_ptr();
        pipeline_input.baseline_torsion_angles_radians =
            input.baseline_torsion_angles_radians.as_ptr();
        pipeline_input.predeclared_refinement_policy_sha256 =
            input.predeclared_refinement_policy_sha256;

        let mut producer_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1); CANDIDATE_COUNT];
        let mut producer_x = vec![0.0; coordinate_count];
        let mut producer_y = vec![0.0; coordinate_count];
        let mut producer_z = vec![0.0; coordinate_count];
        let mut producer_output = init(sys::bg_docking_fixed64_producer_output_v1_init)?;
        producer_output.row_capacity = CANDIDATE_COUNT as u64;
        producer_output.coordinate_capacity = coordinate_count_u64;
        producer_output.rows = producer_rows.as_mut_ptr();
        producer_output.x_angstrom = producer_x.as_mut_ptr();
        producer_output.y_angstrom = producer_y.as_mut_ptr();
        producer_output.z_angstrom = producer_z.as_mut_ptr();

        let mut rigid_rows =
            vec![zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1); CANDIDATE_COUNT];
        let mut rigid_coordinates: [Vec<f64>; 12] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut rigid_output = init(sys::bg_docking_rigid_refinement_output_v1_init)?;
        rigid_output.row_capacity = CANDIDATE_COUNT as u64;
        rigid_output.coordinate_capacity = coordinate_count_u64;
        rigid_output.rows = rigid_rows.as_mut_ptr();
        rigid_output.selected_x_angstrom = rigid_coordinates[0].as_mut_ptr();
        rigid_output.selected_y_angstrom = rigid_coordinates[1].as_mut_ptr();
        rigid_output.selected_z_angstrom = rigid_coordinates[2].as_mut_ptr();
        rigid_output.comparison_v2_x_angstrom = rigid_coordinates[3].as_mut_ptr();
        rigid_output.comparison_v2_y_angstrom = rigid_coordinates[4].as_mut_ptr();
        rigid_output.comparison_v2_z_angstrom = rigid_coordinates[5].as_mut_ptr();
        rigid_output.baseline_v3_x_angstrom = rigid_coordinates[6].as_mut_ptr();
        rigid_output.baseline_v3_y_angstrom = rigid_coordinates[7].as_mut_ptr();
        rigid_output.baseline_v3_z_angstrom = rigid_coordinates[8].as_mut_ptr();
        rigid_output.clearance_v4_x_angstrom = rigid_coordinates[9].as_mut_ptr();
        rigid_output.clearance_v4_y_angstrom = rigid_coordinates[10].as_mut_ptr();
        rigid_output.clearance_v4_z_angstrom = rigid_coordinates[11].as_mut_ptr();

        let mut torsion_rows =
            vec![zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1); CANDIDATE_COUNT];
        let mut torsion_moves =
            vec![zeroed_abi_value!(sys::bg_docking_torsion_v7_move_v1); MOVE_COUNT];
        let mut torsion_coordinates: [Vec<f64>; 8] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut torsion_output = init(sys::bg_docking_torsion_v7_output_v1_init)?;
        torsion_output.row_capacity = CANDIDATE_COUNT as u64;
        torsion_output.move_capacity = MOVE_COUNT as u64;
        torsion_output.coordinate_capacity = coordinate_count_u64;
        torsion_output.rows = torsion_rows.as_mut_ptr();
        torsion_output.moves = torsion_moves.as_mut_ptr();
        torsion_output.optimized_x_angstrom = torsion_coordinates[0].as_mut_ptr();
        torsion_output.optimized_y_angstrom = torsion_coordinates[1].as_mut_ptr();
        torsion_output.optimized_z_angstrom = torsion_coordinates[2].as_mut_ptr();
        torsion_output.optimized_torsion_angles_radians = torsion_coordinates[3].as_mut_ptr();
        torsion_output.final_x_angstrom = torsion_coordinates[4].as_mut_ptr();
        torsion_output.final_y_angstrom = torsion_coordinates[5].as_mut_ptr();
        torsion_output.final_z_angstrom = torsion_coordinates[6].as_mut_ptr();
        torsion_output.final_torsion_angles_radians = torsion_coordinates[7].as_mut_ptr();

        let mut scorer_rows =
            vec![zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1); CANDIDATE_COUNT];
        let mut scorer_output = init(sys::bg_docking_scorer_v1_output_v1_init)?;
        scorer_output.row_capacity = CANDIDATE_COUNT as u64;
        scorer_output.rows = scorer_rows.as_mut_ptr();
        let mut validity_rows =
            vec![zeroed_abi_value!(sys::bg_docking_pose_validity_row_v1); CANDIDATE_COUNT];
        let mut validity_output = init(sys::bg_docking_pose_validity_output_v1_init)?;
        validity_output.row_capacity = CANDIDATE_COUNT as u64;
        validity_output.rows = validity_rows.as_mut_ptr();
        let mut ranking_rows =
            vec![zeroed_abi_value!(sys::bg_docking_stable_top_k_row_v1); CANDIDATE_COUNT];
        let mut primary_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut valid_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut ranking_output = init(sys::bg_docking_stable_top_k_output_v1_init)?;
        ranking_output.row_capacity = CANDIDATE_COUNT as u64;
        ranking_output.primary_index_capacity = CANDIDATE_COUNT as u64;
        ranking_output.valid_index_capacity = CANDIDATE_COUNT as u64;
        ranking_output.rows = ranking_rows.as_mut_ptr();
        ranking_output.primary_slot_indices = primary_indices.as_mut_ptr();
        ranking_output.valid_slot_indices = valid_indices.as_mut_ptr();
        let mut cluster_rows =
            vec![zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1); CANDIDATE_COUNT];
        let mut representative_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut top_k_indices = vec![0_u32; TOP_K_LIMIT];
        let mut cluster_output = init(sys::bg_docking_rmsd_cluster_output_v1_init)?;
        cluster_output.row_capacity = CANDIDATE_COUNT as u64;
        cluster_output.representative_index_capacity = CANDIDATE_COUNT as u64;
        cluster_output.top_k_index_capacity = TOP_K_LIMIT as u64;
        cluster_output.rows = cluster_rows.as_mut_ptr();
        cluster_output.representative_slot_indices = representative_indices.as_mut_ptr();
        cluster_output.top_k_slot_indices = top_k_indices.as_mut_ptr();
        let mut refinement_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1); CANDIDATE_COUNT];
        let mut final_coordinates: [Vec<f64>; 3] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut final_quaternions: [Vec<f64>; 4] =
            std::array::from_fn(|_| vec![0.0; CANDIDATE_COUNT]);
        let mut refinement_output = init(sys::bg_docking_fixed64_refinement_output_v1_init)?;
        refinement_output.row_capacity = CANDIDATE_COUNT as u64;
        refinement_output.coordinate_capacity = coordinate_count_u64;
        refinement_output.quaternion_capacity = CANDIDATE_COUNT as u64;
        refinement_output.rows = refinement_rows.as_mut_ptr();
        refinement_output.final_x_angstrom = final_coordinates[0].as_mut_ptr();
        refinement_output.final_y_angstrom = final_coordinates[1].as_mut_ptr();
        refinement_output.final_z_angstrom = final_coordinates[2].as_mut_ptr();
        refinement_output.final_quaternion_x = final_quaternions[0].as_mut_ptr();
        refinement_output.final_quaternion_y = final_quaternions[1].as_mut_ptr();
        refinement_output.final_quaternion_z = final_quaternions[2].as_mut_ptr();
        refinement_output.final_quaternion_w = final_quaternions[3].as_mut_ptr();
        let mut pipeline_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_pipeline_row_v1); CANDIDATE_COUNT];
        let mut pipeline_output = init(sys::bg_docking_fixed64_pipeline_output_v1_init)?;
        pipeline_output.row_capacity = CANDIDATE_COUNT as u64;
        pipeline_output.rows = pipeline_rows.as_mut_ptr();

        // SAFETY: all descriptors and output buffers remain live and uniquely
        // borrowed for the call. Their exact capacities were validated above.
        status_result(unsafe {
            sys::bg_docking_fixed64_pipeline_v1_run(
                self._context.handle.as_ptr(),
                self.handle.as_ptr(),
                &pipeline_input,
                &mut producer_output,
                &mut rigid_output,
                &mut torsion_output,
                &mut scorer_output,
                &mut validity_output,
                &mut ranking_output,
                &mut cluster_output,
                &mut refinement_output,
                &mut pipeline_output,
            )
        })?;
        let native_placement_replays = replay_native_placements(
            self._context,
            self.replay_admission_handle,
            &allocation,
            &producer_input,
            &expected_allocation,
            expected_feature_geometry_inventory.as_ref(),
            &expected_sources,
            self.ligand_atom_count,
            self.pocket_center_angstrom,
            input.pocket_normal,
            self.backend,
        )?;
        validate_native_outputs(
            self.backend,
            &expected_receipt_graph,
            &expected_allocation,
            receptor_atom_count_u64,
            ligand_atom_count_u64,
            coordinate_count_u64,
            &producer_output,
            &rigid_output,
            &torsion_output,
            &scorer_output,
            &validity_output,
            &ranking_output,
            &cluster_output,
            &refinement_output,
            &pipeline_output,
            &producer_rows,
            &expected_sources,
            expected_feature_geometry_inventory.as_ref(),
            &native_placement_replays,
            component_pocket_normal,
            &rigid_rows,
            &torsion_rows,
            &torsion_moves,
            &scorer_rows,
            &validity_rows,
            &ranking_rows,
            &cluster_rows,
            &refinement_rows,
            &pipeline_rows,
            &primary_indices,
            &valid_indices,
            &representative_indices,
            &top_k_indices,
            &raw_modes,
            input.rigid_max_steps,
            [
                producer_x.as_slice(),
                producer_y.as_slice(),
                producer_z.as_slice(),
            ],
            &rigid_coordinates,
            &torsion_coordinates,
            [
                final_coordinates[0].as_slice(),
                final_coordinates[1].as_slice(),
                final_coordinates[2].as_slice(),
            ],
            [
                final_quaternions[0].as_slice(),
                final_quaternions[1].as_slice(),
                final_quaternions[2].as_slice(),
                final_quaternions[3].as_slice(),
            ],
            input.rmsd_threshold_angstrom,
            self.ligand_heavy_atom_count,
            self.geometric_hard_rejection_minimum_vdw_ratio,
            &self.geometric_input,
            self.rigid_v2_config,
            self.rigid_v3_config,
            self.rigid_clearance_config,
            self.maximum_torsion_steps,
            input.proposal_is_torsion_eligible,
            input.torsion_max_steps,
            input.baseline_torsion_angles_radians,
            &self.rotatable_child_atom_indices,
            self.validity_exclusion_count,
            self.validity_chirality_count,
            self.validity_contact_cell_size_angstrom,
            &self.validity_receptor_cells,
            &self.scorer_context,
            &self.validity_context,
        )?;

        primary_indices.truncate(usize::try_from(ranking_output.primary_index_count).map_err(
            |_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "primary rank count does not fit usize",
                )
            },
        )?);
        valid_indices.truncate(usize::try_from(ranking_output.valid_index_count).map_err(
            |_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "valid rank count does not fit usize",
                )
            },
        )?);
        representative_indices.truncate(
            usize::try_from(cluster_output.representative_index_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "cluster representative count does not fit usize",
                )
            })?,
        );
        top_k_indices.truncate(usize::try_from(cluster_output.top_k_index_count).map_err(
            |_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "cluster Top-K count does not fit usize",
                )
            },
        )?);
        let [rigid_selected_x, rigid_selected_y, rigid_selected_z, rigid_comparison_v2_x, rigid_comparison_v2_y, rigid_comparison_v2_z, rigid_baseline_v3_x, rigid_baseline_v3_y, rigid_baseline_v3_z, rigid_clearance_v4_x, rigid_clearance_v4_y, rigid_clearance_v4_z] =
            rigid_coordinates;
        let [torsion_optimized_x, torsion_optimized_y, torsion_optimized_z, torsion_optimized_angles, torsion_final_x, torsion_final_y, torsion_final_z, torsion_final_angles] =
            torsion_coordinates;
        let [final_x, final_y, final_z] = final_coordinates;
        Ok(Fixed64PipelineReceipt {
            backend: self.backend,
            unit_system: UnitSystem::from_raw(pipeline_output.unit_system)?,
            receptor_atom_count: self.receptor_atom_count,
            ligand_atom_count: self.ligand_atom_count,
            generated_count: pipeline_output.generated_count,
            typed_failure_count: producer_output.typed_failure_count,
            initial_admitted_count: pipeline_output.initial_admitted_count,
            refined_count: pipeline_output.refined_count,
            scored_count: pipeline_output.scored_count,
            valid_count: pipeline_output.valid_count,
            cluster_count: pipeline_output.cluster_count,
            producer_coordinates: super::PositionSoaOwned {
                x_angstrom: producer_x,
                y_angstrom: producer_y,
                z_angstrom: producer_z,
            },
            rigid_coordinates: Fixed64RigidCoordinates {
                selected: super::PositionSoaOwned {
                    x_angstrom: rigid_selected_x,
                    y_angstrom: rigid_selected_y,
                    z_angstrom: rigid_selected_z,
                },
                comparison_v2: super::PositionSoaOwned {
                    x_angstrom: rigid_comparison_v2_x,
                    y_angstrom: rigid_comparison_v2_y,
                    z_angstrom: rigid_comparison_v2_z,
                },
                baseline_v3: super::PositionSoaOwned {
                    x_angstrom: rigid_baseline_v3_x,
                    y_angstrom: rigid_baseline_v3_y,
                    z_angstrom: rigid_baseline_v3_z,
                },
                clearance_v4: super::PositionSoaOwned {
                    x_angstrom: rigid_clearance_v4_x,
                    y_angstrom: rigid_clearance_v4_y,
                    z_angstrom: rigid_clearance_v4_z,
                },
            },
            torsion_coordinates: Fixed64TorsionCoordinates {
                optimized: super::PositionSoaOwned {
                    x_angstrom: torsion_optimized_x,
                    y_angstrom: torsion_optimized_y,
                    z_angstrom: torsion_optimized_z,
                },
                optimized_torsion_angles_radians: torsion_optimized_angles,
                final_state: super::PositionSoaOwned {
                    x_angstrom: torsion_final_x,
                    y_angstrom: torsion_final_y,
                    z_angstrom: torsion_final_z,
                },
                final_torsion_angles_radians: torsion_final_angles,
            },
            final_coordinates: super::PositionSoaOwned {
                x_angstrom: final_x,
                y_angstrom: final_y,
                z_angstrom: final_z,
            },
            final_quaternions,
            producer_rows: producer_rows
                .iter()
                .map(producer_evidence)
                .collect::<Result<Vec<_>>>()?,
            rigid_rows: rigid_rows
                .iter()
                .map(rigid_evidence)
                .collect::<Result<Vec<_>>>()?,
            torsion_rows: torsion_rows
                .iter()
                .map(torsion_evidence)
                .collect::<Result<Vec<_>>>()?,
            torsion_moves: torsion_moves
                .iter()
                .map(torsion_move_evidence)
                .collect::<Result<Vec<_>>>()?,
            refinement_rows: refinement_rows
                .iter()
                .map(refinement_evidence)
                .collect::<Result<Vec<_>>>()?,
            scorer_rows: scorer_rows.iter().map(scorer_evidence).collect(),
            validity_rows: validity_rows.iter().map(validity_evidence).collect(),
            ranking_rows: ranking_rows
                .iter()
                .map(ranking_evidence)
                .collect::<Result<Vec<_>>>()?,
            cluster_rows: cluster_rows
                .iter()
                .map(cluster_evidence)
                .collect::<Result<Vec<_>>>()?,
            rows: pipeline_rows.iter().map(pipeline_row).collect(),
            primary_slot_indices: primary_indices,
            valid_slot_indices: valid_indices,
            representative_slot_indices: representative_indices,
            top_k_slot_indices: top_k_indices,
            receipts: Fixed64BatchReceipts {
                allocation_inventory_sha256: producer_output.allocation_inventory_sha256,
                allocation_receipt_sha256: pipeline_output.allocation_receipt_sha256,
                source_bundle_receipt_sha256: pipeline_output.source_bundle_receipt_sha256,
                geometric_admission_batch_receipt_sha256: producer_output
                    .geometric_admission_batch_receipt_sha256,
                admission_context_receipt_sha256: pipeline_output.admission_context_receipt_sha256,
                refinement_context_receipt_sha256: pipeline_output
                    .refinement_context_receipt_sha256,
                scorer_context_receipt_sha256: pipeline_output.scorer_context_receipt_sha256,
                validity_context_receipt_sha256: pipeline_output.validity_context_receipt_sha256,
                component_binding_receipt_sha256: pipeline_output.component_binding_receipt_sha256,
                producer_batch_receipt_sha256: pipeline_output.producer_batch_receipt_sha256,
                refinement_policy_receipt_sha256: pipeline_output.refinement_policy_receipt_sha256,
                refinement_batch_receipt_sha256: pipeline_output.refinement_batch_receipt_sha256,
                scorer_batch_receipt_sha256: pipeline_output.scorer_batch_receipt_sha256,
                validity_batch_receipt_sha256: pipeline_output.validity_batch_receipt_sha256,
                ranking_batch_receipt_sha256: pipeline_output.ranking_batch_receipt_sha256,
                cluster_batch_receipt_sha256: pipeline_output.cluster_batch_receipt_sha256,
                pipeline_batch_receipt_sha256: pipeline_output.pipeline_batch_receipt_sha256,
            },
            authority: authority_disposition(&pipeline_output, &producer_output)?,
        })
    }

    pub fn profile_id() -> Result<&'static str> {
        // SAFETY: the native function returns a process-lifetime NUL-terminated
        // static string or null on an ABI violation.
        let pointer = unsafe { sys::bg_docking_fixed64_pipeline_v1_profile_id() };
        if pointer.is_null() {
            return Err(Error::local(
                ErrorCode::InternalError,
                "native fixed64 pipeline profile id is null",
            ));
        }
        // SAFETY: non-null pointer follows the native static-string contract.
        unsafe { CStr::from_ptr(pointer) }.to_str().map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline profile id is not UTF-8",
            )
        })
    }
}

impl Drop for Fixed64Pipeline<'_> {
    fn drop(&mut self) {
        // SAFETY: this object owns both non-null handles and destroys each once,
        // before the borrowed native Context can be dropped.
        unsafe {
            sys::bg_docking_fixed64_pipeline_v1_destroy(self.handle.as_ptr());
            sys::bg_docking_geometric_admission_v1_destroy(self.replay_admission_handle.as_ptr());
        }
    }
}

fn coordinate_segment_matches(
    channels: &[&[f64]],
    slot: usize,
    ligand_atom_count: u64,
    require_zero: bool,
) -> Result<bool> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 ligand denominator does not fit usize",
        )
    })?;
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 coordinate segment offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 coordinate segment end overflowed",
        )
    })?;
    for channel in channels {
        let segment = channel.get(begin..end).ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 coordinate segment exceeds its owned buffer",
            )
        })?;
        if segment.iter().any(|value| {
            if require_zero {
                *value != 0.0
            } else {
                !value.is_finite()
            }
        }) {
            return Ok(false);
        }
    }
    Ok(true)
}

fn unit_quaternion(values: [f64; 4]) -> bool {
    if values.iter().any(|value| !value.is_finite()) {
        return false;
    }
    let norm = values[0].hypot(values[1]).hypot(values[2].hypot(values[3]));
    norm.is_finite() && (norm - 1.0).abs() <= 1.0e-8
}

fn fixed64_lane_and_placement_for_slot(
    slot: usize,
) -> Option<(
    sys::bg_docking_fixed64_lane,
    sys::bg_docking_fixed64_producer_placement_kind,
)> {
    let (lane, placement) = match slot {
        0..=7 => (
            sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH,
        ),
        8..=23 => (
            sys::BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH,
        ),
        24..=35 => (
            sys::BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3,
        ),
        36..=43 => (
            sys::BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3,
        ),
        44..=47 => (
            sys::BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        48..=51 => (
            sys::BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        52..=55 => (
            sys::BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        56..=57 => (
            sys::BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        58..=59 => (
            sys::BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        60..=63 => (
            sys::BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH,
        ),
        _ => return None,
    };
    Some((lane, placement))
}

fn fixed64_source_for_slot(
    input: Fixed64RunInput<'_>,
    slot: usize,
) -> Option<Fixed64CoordinateSource<'_>> {
    const CONFORMER_RANKS: [u8; 8] = [2, 3, 4, 5, 6, 7, 8, 2];
    const RETAINED_INDICES: [u32; 4] = [36, 45, 54, 63];
    match slot {
        0..=23 => input
            .v7_control_sources
            .iter()
            .find(|source| source.source_index == slot as u32)
            .map(|source| source.source),
        24..=35 | 44..=59 => Some(input.exact_source),
        36..=43 => {
            let rank = CONFORMER_RANKS[slot - 36];
            input
                .conformer_sources
                .iter()
                .find(|source| source.rank == rank)
                .map(|source| source.source)
        }
        60..=63 => {
            let source_index = RETAINED_INDICES[slot - 60];
            input
                .retained_sources
                .iter()
                .find(|source| source.source_index == source_index)
                .map(|source| source.source)
        }
        _ => None,
    }
}

fn coordinate_segment_matches_source(
    channels: [&[f64]; 3],
    slot: usize,
    source: Fixed64CoordinateSource<'_>,
) -> bool {
    coordinate_segment(channels, slot, source.coordinates.x_angstrom.len()).is_some_and(
        |observed| {
            [
                (observed.x_angstrom, source.coordinates.x_angstrom),
                (observed.y_angstrom, source.coordinates.y_angstrom),
                (observed.z_angstrom, source.coordinates.z_angstrom),
            ]
            .iter()
            .all(|(left, right)| {
                left.iter()
                    .zip(*right)
                    .all(|(left, right)| left.to_bits() == right.to_bits())
            })
        },
    )
}

fn coordinate_segment<'a>(
    channels: [&'a [f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> Option<PositionSoa<'a>> {
    let begin = slot.checked_mul(ligand_count)?;
    let end = begin.checked_add(ligand_count)?;
    Some(PositionSoa::new(
        channels[0].get(begin..end)?,
        channels[1].get(begin..end)?,
        channels[2].get(begin..end)?,
    ))
}

fn coordinate_segments_equal(
    left: [&[f64]; 3],
    right: [&[f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> bool {
    let Some(left) = coordinate_segment(left, slot, ligand_count) else {
        return false;
    };
    let Some(right) = coordinate_segment(right, slot, ligand_count) else {
        return false;
    };
    [
        (left.x_angstrom, right.x_angstrom),
        (left.y_angstrom, right.y_angstrom),
        (left.z_angstrom, right.z_angstrom),
    ]
    .iter()
    .all(|(left, right)| {
        left.iter()
            .zip(*right)
            .all(|(left, right)| left.to_bits() == right.to_bits())
    })
}

fn scalar_segments_equal(left: &[f64], right: &[f64], slot: usize, count: usize) -> bool {
    let Some(begin) = slot.checked_mul(count) else {
        return false;
    };
    let Some(end) = begin.checked_add(count) else {
        return false;
    };
    let (Some(left), Some(right)) = (left.get(begin..end), right.get(begin..end)) else {
        return false;
    };
    left.iter()
        .zip(right)
        .all(|(left, right)| left.to_bits() == right.to_bits())
}

fn validate_producer_row_semantics(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
    expected_source: Option<Fixed64CoordinateSource<'_>>,
) -> Result<()> {
    let (expected_lane, expected_placement) = fixed64_lane_and_placement_for_slot(slot)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer slot is outside the frozen profile",
            )
        })?;
    let coordinates_available = bool_from_abi(
        row.coordinates_available,
        "producer coordinate availability",
    )?;
    let steric_precheck = bool_from_abi(row.steric_precheck_passed, "producer steric precheck")?;
    let source_verified = bool_from_abi(row.source_identity_verified, "producer source identity")?;
    let allocation_verified = bool_from_abi(
        row.allocation_identity_verified,
        "producer allocation identity",
    )?;
    let geometric_verified = bool_from_abi(
        row.geometric_identity_verified,
        "producer geometric identity",
    )?;
    let rank_eligible = bool_from_abi(
        row.geometric_admission.rank_eligible,
        "producer geometric rank eligibility",
    )?;
    let source_digests_present = digest_present(&row.source_payload_receipt_sha256)
        && digest_present(&row.source_proposal_sha256)
        && digest_present(&row.source_coordinate_sha256);
    let source_digests_zero = !digest_present(&row.source_payload_receipt_sha256)
        && !digest_present(&row.source_proposal_sha256)
        && !digest_present(&row.source_coordinate_sha256);
    let source_evidence_matches =
        expected_source.map_or(!source_verified && source_digests_zero, |source| {
            source_verified
                && row.source_payload_receipt_sha256
                    == canonical_source_payload_sha256(source, ligand_atom_count)
                && row.source_proposal_sha256 == source.evidence.proposal_sha256
                && row.source_coordinate_sha256 == source.evidence.coordinate_sha256
        });
    if row.reserved0 != 0
        || row.lane != expected_lane
        || row.placement_kind != expected_placement
        || !digest_present(&row.allocation_slot_receipt_sha256)
        || !allocation_verified
        || !geometric_verified
        || source_verified != source_digests_present
        || (!source_verified && !source_digests_zero)
        || !source_evidence_matches
        || steric_precheck != rank_eligible
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 producer identity evidence is inconsistent",
        ));
    }
    let quaternion = [
        row.placement_quaternion_x,
        row.placement_quaternion_y,
        row.placement_quaternion_z,
        row.placement_quaternion_w,
    ];
    match row.status {
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED => {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer ligand denominator does not fit usize",
                )
            })?;
            let output_coordinate_matches = coordinate_segment(coordinates, slot, ligand_count)
                .is_some_and(|segment| {
                    canonical_coordinate_sha256(segment) == row.output_coordinate_sha256
                });
            let exact_passthrough_evidence_matches = row.placement_kind
                != sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
                || expected_source.is_some_and(|source| {
                    quaternion == [0.0, 0.0, 0.0, 1.0]
                        && row.output_proposal_sha256 == source.evidence.proposal_sha256
                        && row.output_coordinate_sha256 == source.evidence.coordinate_sha256
                        && coordinate_segment_matches_source(coordinates, slot, source)
                });
            if row.failure_code != sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE
                || row.component_failure_code != 0
                || row.placement_kind < sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
                || row.placement_kind > sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
                || !coordinates_available
                || !source_verified
                || !digest_present(&row.placement_receipt_sha256)
                || !digest_present(&row.output_proposal_sha256)
                || !digest_present(&row.output_coordinate_sha256)
                || !unit_quaternion(quaternion)
                || !output_coordinate_matches
                || !exact_passthrough_evidence_matches
                || !coordinate_segment_matches(&coordinates, slot, ligand_atom_count, false)?
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 generated producer row retained invalid success evidence",
                ));
            }
        }
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE => {
            let valid_component_failure = match row.failure_code {
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE => {
                    expected_placement
                        == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
                        && (sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY
                            ..=sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT)
                            .contains(&row.component_failure_code)
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE => {
                    expected_placement
                        == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
                        && (sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION
                            ..=sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT)
                            .contains(&row.component_failure_code)
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE
                | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE => {
                    row.component_failure_code == 0
                        && (row.failure_code
                            != sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE
                            || expected_source.is_none())
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE => {
                    expected_placement
                        == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
                        && row.component_failure_code == 0
                }
                _ => false,
            };
            let component_placement_failed = matches!(
                row.failure_code,
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE
                    | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE
            );
            if !valid_component_failure
                || digest_present(&row.placement_receipt_sha256) != component_placement_failed
                || coordinates_available
                || digest_present(&row.output_proposal_sha256)
                || digest_present(&row.output_coordinate_sha256)
                || quaternion.iter().any(|value| *value != 0.0)
                || !coordinate_segment_matches(&coordinates, slot, ligand_atom_count, true)?
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer typed failure retained output evidence",
                ));
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer row status is unknown",
            ));
        }
    }
    Ok(())
}

fn geometric_scientific_fields_are_zero(row: &sys::bg_docking_geometric_admission_row_v1) -> bool {
    row.ligand_atom_count == 0
        && row.receptor_atom_count == 0
        && row.exact_pair_count == 0
        && row.penetration_pair_count == 0
        && row.unique_ligand_penetration_atom_count == 0
        && row.unique_ligand_heavy_atom_penetration_count == 0
        && row.raw_minimum_distance_angstrom == 0.0
        && row.minimum_vdw_surface_gap_angstrom == 0.0
        && row.minimum_vdw_ratio == 0.0
        && row.sphere_overlap_proxy_angstrom3 == 0.0
        && row.pocket_escape_angstrom == 0.0
}

fn backend_numeric_tolerance(backend: Backend, expected: f64, observed: f64) -> f64 {
    let relative = match backend {
        Backend::CppCpuReference | Backend::RustCpu => 2.0e-12,
        Backend::HipSafe => 2.0e-10,
        Backend::HipFast => 2.0e-8,
        Backend::Auto => 2.0e-8,
    };
    relative * 1.0_f64.max(expected.abs()).max(observed.abs())
}

fn numeric_matches(backend: Backend, expected: f64, observed: f64) -> bool {
    expected.is_finite()
        && observed.is_finite()
        && (expected - observed).abs() <= backend_numeric_tolerance(backend, expected, observed)
}

fn canonical_geometric_coordinate_receipt(
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
) -> Result<Sha256> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 geometric ligand denominator does not fit usize",
        )
    })?;
    let owned = coordinate_segment(coordinates, slot, ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 geometric coordinate receipt exceeds its owned buffer",
        )
    })?;
    let mut hash = CanonicalHasher::new("betelgeuze.geometric_admission_coordinate/native-v1");
    hash.u64(slot as u64);
    hash.u64(ligand_atom_count);
    for atom in 0..ligand_count {
        hash.f64(owned.x_angstrom[atom]);
        hash.f64(owned.y_angstrom[atom]);
        hash.f64(owned.z_angstrom[atom]);
    }
    Ok(hash.finish())
}

fn hash_geometric_context(hash: &mut CanonicalHasher, graph: &ExpectedPipelineReceiptGraph) {
    hash.digest(graph.authority_input_receipt_sha256);
    hash.digest(graph.receptor_system_sha256);
    hash.digest(graph.ligand_system_sha256);
    hash.digest(graph.backend_receipt_sha256);
    hash.u32(graph.backend.as_raw() as u32);
    hash.u32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL as u32);
    hash.u64(graph.receptor_atom_count);
    hash.u64(graph.ligand_atom_count);
    hash.u64(graph.ligand_heavy_atom_count);
    hash.u64(graph.geometric_max_batch_exact_pair_evaluations);
    for value in graph.pocket_center_angstrom {
        hash.f64(value);
    }
    hash.f64(graph.pocket_radius_angstrom);
    hash.f64(graph.geometric_hard_rejection_minimum_vdw_ratio);
}

fn canonical_geometric_row_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    producer_status: sys::bg_docking_fixed64_producer_row_status,
    coordinates: [&[f64]; 3],
    slot: usize,
    row: &sys::bg_docking_geometric_admission_row_v1,
) -> Result<Sha256> {
    let candidate_state = if producer_status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED {
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE
    } else {
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE
    };
    let coordinate =
        if candidate_state == sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE {
            [0; 32]
        } else {
            canonical_geometric_coordinate_receipt(coordinates, slot, graph.ligand_atom_count)?
        };
    let mut hash = CanonicalHasher::new("betelgeuze.geometric_admission_row/native-v1");
    hash.string("betelgeuze.engine_v2_native_geometric_admission_row/1.0.0");
    hash_geometric_context(&mut hash, graph);
    hash.u32(candidate_state as u32);
    hash.digest(coordinate);
    hash.u32(row.slot_index);
    hash.u32(row.status as u32);
    hash.u32(row.failure_code as u32);
    hash.u32(row.decision as u32);
    hash.byte(row.rank_eligible);
    hash.u64(row.ligand_atom_count);
    hash.u64(row.receptor_atom_count);
    hash.u64(row.exact_pair_count);
    hash.u64(row.penetration_pair_count);
    hash.u64(row.unique_ligand_penetration_atom_count);
    hash.u64(row.unique_ligand_heavy_atom_penetration_count);
    hash.f64(row.raw_minimum_distance_angstrom);
    hash.f64(row.minimum_vdw_surface_gap_angstrom);
    hash.f64(row.minimum_vdw_ratio);
    hash.f64(row.sphere_overlap_proxy_angstrom3);
    hash.f64(row.pocket_escape_angstrom);
    Ok(hash.finish())
}

fn canonical_geometric_batch_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    rows: &[sys::bg_docking_fixed64_producer_row_v1],
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.geometric_admission_batch/native-v1");
    hash.string("betelgeuze.engine_v2_native_geometric_admission_batch/1.0.0");
    hash_geometric_context(&mut hash, graph);
    hash.usize(rows.len());
    for row in rows {
        hash.digest(row.geometric_admission.row_receipt_sha256);
    }
    for value in [0_u8, 1, 0, 0, 0, 0, 0, 0, 0] {
        hash.byte(value);
    }
    hash.finish()
}

fn canonical_producer_row_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    row: &sys::bg_docking_fixed64_producer_row_v1,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_producer_row_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.0");
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(graph.source_bundle_receipt_sha256);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.u32(row.lane as u32);
    hash.u32(row.status as u32);
    hash.u32(row.failure_code as u32);
    hash.u32(row.placement_kind as u32);
    hash.u32(row.component_failure_code as u32);
    hash.u32(row.backend as u32);
    hash.u64(row.ligand_atom_count);
    hash.u64(row.coordinate_offset);
    hash.digest(row.source_payload_receipt_sha256);
    hash.digest(row.source_proposal_sha256);
    hash.digest(row.source_coordinate_sha256);
    hash.digest(row.placement_receipt_sha256);
    hash.f64(row.placement_quaternion_x);
    hash.f64(row.placement_quaternion_y);
    hash.f64(row.placement_quaternion_z);
    hash.f64(row.placement_quaternion_w);
    hash.digest(row.output_proposal_sha256);
    hash.digest(row.output_coordinate_sha256);
    hash.digest(row.geometric_admission.row_receipt_sha256);
    for value in [
        row.coordinates_available,
        row.steric_precheck_passed,
        row.source_identity_verified,
        row.allocation_identity_verified,
        row.geometric_identity_verified,
        row.result_dependent_input_consumed,
        row.fallback_allowed,
        row.multi_anchor_consumed,
        row.denominator_preserved,
        row.molecular_execution_authorized,
        row.reservation_authorized,
        row.benchmark_execution_authorized,
        row.existing_rank_auto_change_authorized,
        row.customer_pose_emission_authorized,
        row.production_claim_authorized,
        row.scientific_claim_authorized,
    ] {
        hash.byte(value);
    }
    hash.finish()
}

fn canonical_passthrough_placement_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    row: &sys::bg_docking_fixed64_producer_row_v1,
    source: Fixed64CoordinateSource<'_>,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_passthrough_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.0");
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.u32(row.lane as u32);
    hash.u32(graph.backend.as_raw() as u32);
    hash.digest(canonical_source_payload_sha256(
        source,
        graph.ligand_atom_count,
    ));
    hash.digest(source.evidence.coordinate_sha256);
    hash.byte(1);
    hash.byte(0);
    hash.finish()
}

fn canonical_generated_proposal_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    row: &sys::bg_docking_fixed64_producer_row_v1,
    source: Fixed64CoordinateSource<'_>,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_generated_proposal_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.0");
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.digest(canonical_source_payload_sha256(
        source,
        graph.ligand_atom_count,
    ));
    hash.digest(row.placement_receipt_sha256);
    hash.digest(row.output_coordinate_sha256);
    hash.byte(0);
    hash.finish()
}

fn canonical_producer_batch_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    geometric_batch_receipt_sha256: Sha256,
    rows: &[sys::bg_docking_fixed64_producer_row_v1],
    generated_count: u64,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_producer_batch_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer_batch/1.1.0");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.0");
    hash.u32(graph.backend.as_raw() as u32);
    hash.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    hash.u64(generated_count);
    hash.u64(u64::from(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT) - generated_count);
    hash.digest(graph.allocation_inventory_sha256);
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(graph.source_bundle_receipt_sha256);
    hash.digest(geometric_batch_receipt_sha256);
    for row in rows {
        hash.digest(row.row_receipt_sha256);
    }
    for value in [0_u8, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0] {
        hash.byte(value);
    }
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
fn validate_geometric_admission_row_semantics(
    row: &sys::bg_docking_geometric_admission_row_v1,
    producer_status: sys::bg_docking_fixed64_producer_row_status,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    ligand_heavy_atom_count: u64,
    exact_pair_count: u64,
    hard_rejection_minimum_vdw_ratio: f64,
    backend: Backend,
    geometric_input: &IndependentFixed64GeometricInput,
    producer_coordinates: [&[f64]; 3],
    slot: usize,
) -> Result<()> {
    let rank_eligible = bool_from_abi(row.rank_eligible, "geometric rank eligibility")?;
    if row.reserved0.iter().any(|value| *value != 0)
        || row.reserved1 != 0
        || !digest_present(&row.row_receipt_sha256)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 geometric row metadata is non-canonical",
        ));
    }
    match row.status {
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED => {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 geometric ligand denominator does not fit usize",
                )
            })?;
            let owned =
                coordinate_segment(producer_coordinates, slot, ligand_count).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 geometric coordinates exceed the owned producer buffer",
                    )
                })?;
            let independent_coordinates = (0..ligand_count)
                .map(|atom| {
                    Vec3::new(
                        owned.x_angstrom[atom],
                        owned.y_angstrom[atom],
                        owned.z_angstrom[atom],
                    )
                })
                .collect::<Vec<_>>();
            let metrics =
                evaluate_fixed64_geometric_metrics(&independent_coordinates, geometric_input)
                    .map_err(|error| {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            format!("independent fixed64 geometric evaluation failed: {error}"),
                        )
                    })?;
            let values = [
                row.raw_minimum_distance_angstrom,
                row.minimum_vdw_surface_gap_angstrom,
                row.minimum_vdw_ratio,
                row.sphere_overlap_proxy_angstrom3,
                row.pocket_escape_angstrom,
            ];
            let accepted = row.minimum_vdw_ratio >= hard_rejection_minimum_vdw_ratio;
            let expected_decision = if accepted {
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            } else {
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED
            };
            let penetration_counts_valid = if row.penetration_pair_count == 0 {
                row.unique_ligand_penetration_atom_count == 0
                    && row.unique_ligand_heavy_atom_penetration_count == 0
                    && row.minimum_vdw_surface_gap_angstrom >= 0.0
                    && row.sphere_overlap_proxy_angstrom3 == 0.0
            } else {
                row.unique_ligand_penetration_atom_count > 0
                    && row.minimum_vdw_surface_gap_angstrom < 0.0
                    && row.sphere_overlap_proxy_angstrom3 > 0.0
            };
            if producer_status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
                || row.failure_code != sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE
                || row.decision != expected_decision
                || rank_eligible != accepted
                || row.ligand_atom_count != ligand_atom_count
                || row.receptor_atom_count != receptor_atom_count
                || row.exact_pair_count != exact_pair_count
                || row.penetration_pair_count > exact_pair_count
                || row.unique_ligand_penetration_atom_count > ligand_atom_count
                || row.unique_ligand_heavy_atom_penetration_count > ligand_heavy_atom_count
                || row.unique_ligand_heavy_atom_penetration_count
                    > row.unique_ligand_penetration_atom_count
                || values.iter().any(|value| !value.is_finite())
                || row.raw_minimum_distance_angstrom < 0.0
                || row.minimum_vdw_ratio < 0.0
                || row.sphere_overlap_proxy_angstrom3 < 0.0
                || row.pocket_escape_angstrom < 0.0
                || !penetration_counts_valid
                || row.ligand_atom_count != metrics.ligand_atom_count() as u64
                || row.receptor_atom_count != metrics.receptor_atom_count() as u64
                || row.exact_pair_count != metrics.exact_pair_count() as u64
                || row.penetration_pair_count != metrics.penetration_pair_count() as u64
                || row.unique_ligand_penetration_atom_count
                    != metrics.unique_ligand_penetration_atom_count() as u64
                || row.unique_ligand_heavy_atom_penetration_count
                    != metrics.unique_ligand_heavy_atom_penetration_count() as u64
                || !numeric_matches(
                    backend,
                    metrics.raw_minimum_distance_angstrom(),
                    row.raw_minimum_distance_angstrom,
                )
                || !numeric_matches(
                    backend,
                    metrics.minimum_vdw_surface_gap_angstrom(),
                    row.minimum_vdw_surface_gap_angstrom,
                )
                || !numeric_matches(backend, metrics.minimum_vdw_ratio(), row.minimum_vdw_ratio)
                || !numeric_matches(
                    backend,
                    metrics.sphere_overlap_proxy_angstrom3(),
                    row.sphere_overlap_proxy_angstrom3,
                )
                || !numeric_matches(
                    backend,
                    metrics.pocket_escape_angstrom(),
                    row.pocket_escape_angstrom,
                )
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 evaluated geometric evidence is inconsistent",
                ));
            }
        }
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE => {
            if producer_status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
                || row.failure_code
                    != sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE
                || row.decision != sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED
                || rank_eligible
                || !geometric_scientific_fields_are_zero(row)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 upstream geometric failure retained scientific evidence",
                ));
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 geometric row status is invalid for producer output",
            ));
        }
    }
    Ok(())
}

fn rigid_evidence_values(value: &sys::bg_docking_rigid_refinement_evidence_v1) -> [f64; 13] {
    [
        value.initial_penalty,
        value.final_penalty,
        value.total_translation_angstrom[0],
        value.total_translation_angstrom[1],
        value.total_translation_angstrom[2],
        value.total_rotation_vector_radians[0],
        value.total_rotation_vector_radians[1],
        value.total_rotation_vector_radians[2],
        value.total_rotation_path_radians,
        value.initial_centroid_offset_angstrom,
        value.final_centroid_offset_angstrom,
        value.maximum_centroid_offset_angstrom,
        value.accepted_steps as f64,
    ]
}

fn rigid_evidence_is_zero(value: &sys::bg_docking_rigid_refinement_evidence_v1) -> bool {
    value.profile == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE
        && value.available == 0
        && value.reserved0.iter().all(|item| *item == 0)
        && value.accepted_steps == 0
        && value.accepted_translation_steps == 0
        && value.accepted_rotation_steps == 0
        && value.line_search_evaluation_count == 0
        && value.fallback_direction_step_count == 0
        && rigid_evidence_values(value)
            .iter()
            .take(12)
            .all(|item| *item == 0.0)
        && value.reserved.iter().all(|item| *item == 0)
}

fn rigid_evidence_is_consistent(
    value: &sys::bg_docking_rigid_refinement_evidence_v1,
) -> Result<bool> {
    let available = bool_from_abi(value.available, "rigid evidence availability")?;
    if !available {
        return Ok(rigid_evidence_is_zero(value));
    }
    let values = rigid_evidence_values(value);
    let rotation_norm = values[5].hypot(values[6]).hypot(values[7]);
    Ok(value.reserved0.iter().all(|item| *item == 0)
        && value.reserved.iter().all(|item| *item == 0)
        && value.profile >= sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
        && value.profile <= sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4
        && value.accepted_translation_steps <= value.accepted_steps
        && value.accepted_rotation_steps == value.accepted_steps - value.accepted_translation_steps
        && value.fallback_direction_step_count <= value.accepted_steps
        && values.iter().all(|item| item.is_finite())
        && value.initial_penalty >= 0.0
        && value.final_penalty >= 0.0
        && value.total_rotation_path_radians >= 0.0
        && rotation_norm.is_finite()
        && rotation_norm <= value.total_rotation_path_radians + 2.0e-12
        && (value.accepted_rotation_steps != 0
            || (rotation_norm == 0.0 && value.total_rotation_path_radians == 0.0)))
}

fn rigid_evidence_equal(
    left: &sys::bg_docking_rigid_refinement_evidence_v1,
    right: &sys::bg_docking_rigid_refinement_evidence_v1,
) -> bool {
    left.profile == right.profile
        && left.available == right.available
        && left.accepted_steps == right.accepted_steps
        && left.accepted_translation_steps == right.accepted_translation_steps
        && left.accepted_rotation_steps == right.accepted_rotation_steps
        && left.line_search_evaluation_count == right.line_search_evaluation_count
        && left.fallback_direction_step_count == right.fallback_direction_step_count
        && rigid_evidence_values(left)[..12] == rigid_evidence_values(right)[..12]
}

fn validate_rigid_coordinate_channel(
    evidence: &sys::bg_docking_rigid_refinement_evidence_v1,
    coordinates: &[Vec<f64>; 12],
    first_channel: usize,
    slot: usize,
    ligand_atom_count: u64,
) -> Result<bool> {
    let channels = [
        coordinates[first_channel].as_slice(),
        coordinates[first_channel + 1].as_slice(),
        coordinates[first_channel + 2].as_slice(),
    ];
    coordinate_segment_matches(&channels, slot, ligand_atom_count, evidence.available == 0)
}

fn validate_rigid_row_semantics(
    row: &sys::bg_docking_rigid_refinement_row_v1,
    requested_mode: sys::bg_docking_rigid_refinement_candidate_mode,
    requested_max_steps: u64,
    coordinates: &[Vec<f64>; 12],
    slot: usize,
    ligand_atom_count: u64,
) -> Result<()> {
    let baseline_duplicate =
        bool_from_abi(row.baseline_duplicate_of_v2, "rigid baseline duplicate")?;
    let clearance_evaluated = bool_from_abi(row.clearance_evaluated, "rigid clearance evaluation")?;
    let clearance_selected = bool_from_abi(row.clearance_selected, "rigid clearance selection")?;
    if row.slot_index as usize != slot
        || row.candidate_mode != requested_mode
        || row.reserved0 != 0
        || row.reserved.iter().any(|item| *item != 0)
        || !rigid_evidence_is_consistent(&row.selected)?
        || !rigid_evidence_is_consistent(&row.comparison_v2)?
        || !rigid_evidence_is_consistent(&row.baseline_v3)?
        || !rigid_evidence_is_consistent(&row.clearance_v4)?
        || [
            &row.selected,
            &row.comparison_v2,
            &row.baseline_v3,
            &row.clearance_v4,
        ]
        .iter()
        .any(|evidence| evidence.available == 1 && evidence.accepted_steps > requested_max_steps)
        || !validate_rigid_coordinate_channel(
            &row.selected,
            coordinates,
            0,
            slot,
            ligand_atom_count,
        )?
        || !validate_rigid_coordinate_channel(
            &row.comparison_v2,
            coordinates,
            3,
            slot,
            ligand_atom_count,
        )?
        || !validate_rigid_coordinate_channel(
            &row.baseline_v3,
            coordinates,
            6,
            slot,
            ligand_atom_count,
        )?
        || !validate_rigid_coordinate_channel(
            &row.clearance_v4,
            coordinates,
            9,
            slot,
            ligand_atom_count,
        )?
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid row evidence is malformed",
        ));
    }
    match row.status {
        sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE => {
            let active_mode = row.candidate_mode
                >= sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION
                && row.candidate_mode
                    <= sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
            if row.failure_code < sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE
                || row.failure_code
                    > sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE
                || row.selected_profile != sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE
                || baseline_duplicate
                || clearance_evaluated
                || clearance_selected
                || !rigid_evidence_is_zero(&row.selected)
                || !rigid_evidence_is_zero(&row.comparison_v2)
                || !rigid_evidence_is_zero(&row.baseline_v3)
                || !rigid_evidence_is_zero(&row.clearance_v4)
                || (row.candidate_mode == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
                    && row.failure_code
                        != sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE)
                || (active_mode
                    && row.failure_code
                        == sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 rigid typed failure retained refinement evidence",
                ));
            }
        }
        sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED => {
            if row.failure_code != sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE
                || row.candidate_mode != requested_mode
                || row.selected.available != 1
                || row.selected.profile != row.selected_profile
                || clearance_selected && !clearance_evaluated
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 rigid success evidence is inconsistent",
                ));
            }
            let channels_match_mode = match row.candidate_mode {
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION => {
                    row.selected_profile == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
                        && !baseline_duplicate
                        && !clearance_evaluated
                        && !clearance_selected
                        && rigid_evidence_is_zero(&row.comparison_v2)
                        && rigid_evidence_is_zero(&row.baseline_v3)
                        && rigid_evidence_is_zero(&row.clearance_v4)
                }
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION => {
                    row.selected_profile
                        == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION
                        && !baseline_duplicate
                        && !clearance_evaluated
                        && !clearance_selected
                        && rigid_evidence_is_zero(&row.comparison_v2)
                        && rigid_evidence_is_zero(&row.baseline_v3)
                        && rigid_evidence_is_zero(&row.clearance_v4)
                }
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE => {
                    row.selected_profile == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2
                        && !baseline_duplicate
                        && !clearance_evaluated
                        && !clearance_selected
                        && rigid_evidence_is_zero(&row.comparison_v2)
                        && rigid_evidence_is_zero(&row.baseline_v3)
                        && rigid_evidence_is_zero(&row.clearance_v4)
                }
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE => {
                    row.comparison_v2.available == 1
                        && row.comparison_v2.profile
                            == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
                        && row.baseline_v3.available == 1
                        && row.baseline_v3.profile
                            == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3
                        && (clearance_evaluated == (row.clearance_v4.available == 1))
                        && (!clearance_evaluated
                            || row.clearance_v4.profile
                                == sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4)
                        && rigid_evidence_equal(
                            &row.selected,
                            if clearance_selected {
                                &row.clearance_v4
                            } else {
                                &row.baseline_v3
                            },
                        )
                }
                _ => false,
            };
            if !channels_match_mode {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 rigid evidence disagrees with its candidate mode",
                ));
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 rigid row status is unknown",
            ));
        }
    }
    Ok(())
}

fn independent_rigid_profile_raw(
    profile: IndependentRigidProfile,
) -> sys::bg_docking_rigid_refinement_profile {
    match profile {
        IndependentRigidProfile::V2Translation => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION
        }
        IndependentRigidProfile::V3TranslationRotation => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION
        }
        IndependentRigidProfile::V6BaselineV2 => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2
        }
        IndependentRigidProfile::V6BaselineV3 => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3
        }
        IndependentRigidProfile::V6ClearanceV4 => {
            sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4
        }
    }
}

fn validate_independent_rigid_evidence(
    backend: Backend,
    observed: &sys::bg_docking_rigid_refinement_evidence_v1,
    expected: &IndependentRigidOutcome,
    coordinates: &[Vec<f64>; 12],
    first_channel: usize,
    slot: usize,
    ligand_atom_count: usize,
) -> Result<()> {
    let expected_counts = [
        expected.accepted_steps(),
        expected.accepted_translation_steps(),
        expected.accepted_rotation_steps(),
        expected.line_search_evaluation_count(),
        expected.fallback_direction_step_count(),
    ];
    let observed_counts = [
        observed.accepted_steps,
        observed.accepted_translation_steps,
        observed.accepted_rotation_steps,
        observed.line_search_evaluation_count,
        observed.fallback_direction_step_count,
    ];
    let counts_match = expected_counts
        .into_iter()
        .zip(observed_counts)
        .all(|(expected, observed)| u64::try_from(expected).ok() == Some(observed));
    let expected_translation = expected.total_translation_angstrom();
    let expected_rotation = expected.total_rotation_vector_radians();
    let expected_values = [
        expected.initial_penalty(),
        expected.final_penalty(),
        expected_translation.x,
        expected_translation.y,
        expected_translation.z,
        expected_rotation.x,
        expected_rotation.y,
        expected_rotation.z,
        expected.total_rotation_path_radians(),
        expected.initial_centroid_offset_angstrom(),
        expected.final_centroid_offset_angstrom(),
        expected.maximum_centroid_offset_angstrom(),
    ];
    let observed_values = [
        observed.initial_penalty,
        observed.final_penalty,
        observed.total_translation_angstrom[0],
        observed.total_translation_angstrom[1],
        observed.total_translation_angstrom[2],
        observed.total_rotation_vector_radians[0],
        observed.total_rotation_vector_radians[1],
        observed.total_rotation_vector_radians[2],
        observed.total_rotation_path_radians,
        observed.initial_centroid_offset_angstrom,
        observed.final_centroid_offset_angstrom,
        observed.maximum_centroid_offset_angstrom,
    ];
    let values_match = expected_values
        .into_iter()
        .zip(observed_values)
        .all(|(expected, observed)| numeric_matches(backend, expected, observed));
    let begin = slot.checked_mul(ligand_atom_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid coordinate offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_atom_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid coordinate range overflowed",
        )
    })?;
    let coordinate_channels = coordinates
        .get(first_channel..first_channel + 3)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 independent rigid coordinate channel is absent",
            )
        })?;
    let coordinates_match = expected.coordinates_angstrom().len() == ligand_atom_count
        && coordinate_channels
            .iter()
            .all(|channel| channel.len() >= end)
        && expected
            .coordinates_angstrom()
            .iter()
            .enumerate()
            .all(|(atom, expected)| {
                numeric_matches(backend, expected.x, coordinate_channels[0][begin + atom])
                    && numeric_matches(backend, expected.y, coordinate_channels[1][begin + atom])
                    && numeric_matches(backend, expected.z, coordinate_channels[2][begin + atom])
            });
    if observed.available != 1
        || observed.profile != independent_rigid_profile_raw(expected.profile())
        || !counts_match
        || !values_match
        || !coordinates_match
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid evidence disagrees with independent source-pose replay",
        ));
    }
    Ok(())
}

fn independent_rigid_failure_code(code: IndependentRigidErrorCode) -> i32 {
    match code {
        IndependentRigidErrorCode::InvalidInput => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT
        }
        IndependentRigidErrorCode::NonFiniteInput => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_INPUT
        }
        IndependentRigidErrorCode::PairBudgetExceeded => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_PAIR_BUDGET
        }
        IndependentRigidErrorCode::NonFiniteDerivedValue => {
            sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE
        }
    }
}

fn bind_independent_rigid_outcome<T>(
    row: &sys::bg_docking_rigid_refinement_row_v1,
    replay: std::result::Result<T, IndependentRigidError>,
) -> Result<Option<T>> {
    match replay {
        Ok(expected) if row.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED => {
            Ok(Some(expected))
        }
        Ok(_) => Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid failure suppressed an independently successful refinement",
        )),
        Err(error)
            if row.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE
                && row.failure_code == independent_rigid_failure_code(error.code()) =>
        {
            Ok(None)
        }
        Err(error) => Err(Error::local(
            ErrorCode::AbiMismatch,
            format!(
                "native fixed64 rigid outcome disagrees with independent typed failure: {error}"
            ),
        )),
    }
}

#[allow(clippy::too_many_arguments)]
fn validate_independent_rigid_replay(
    backend: Backend,
    row: &sys::bg_docking_rigid_refinement_row_v1,
    requested_mode: sys::bg_docking_rigid_refinement_candidate_mode,
    requested_max_steps: u64,
    producer_coordinates: [&[f64]; 3],
    rigid_coordinates: &[Vec<f64>; 12],
    slot: usize,
    ligand_atom_count: u64,
    geometric_input: &IndependentFixed64GeometricInput,
    v2_config: IndependentRigidV2Config,
    v3_config: IndependentRigidV3Config,
    clearance_config: IndependentRigidV3Config,
) -> Result<()> {
    if requested_mode == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE {
        return Ok(());
    }
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid ligand denominator does not fit usize",
        )
    })?;
    let source = coordinate_segment(producer_coordinates, slot, ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid replay exceeds its producer coordinate buffer",
        )
    })?;
    let source = (0..ligand_count)
        .map(|atom| {
            Vec3::new(
                source.x_angstrom[atom],
                source.y_angstrom[atom],
                source.z_angstrom[atom],
            )
        })
        .collect::<Vec<_>>();
    let max_steps = usize::try_from(requested_max_steps).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 independent rigid step budget does not fit usize",
        )
    })?;
    let context = IndependentRigidContext {
        receptor_coordinates_angstrom: geometric_input.receptor_coordinates_angstrom(),
        receptor_vdw_radii_angstrom: geometric_input.receptor_vdw_radii_angstrom(),
        ligand_vdw_radii_angstrom: geometric_input.ligand_vdw_radii_angstrom(),
        pocket_center_angstrom: geometric_input.pocket_center_angstrom(),
        pocket_radius_angstrom: geometric_input.pocket_radius_angstrom(),
    };
    match requested_mode {
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION => {
            let Some(expected) = bind_independent_rigid_outcome(
                row,
                refine_interaction_aware_rigid_v2(context, &source, max_steps, v2_config),
            )?
            else {
                return Ok(());
            };
            validate_independent_rigid_evidence(
                backend,
                &row.selected,
                &expected,
                rigid_coordinates,
                0,
                slot,
                ligand_count,
            )?;
        }
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION => {
            let Some(expected) = bind_independent_rigid_outcome(
                row,
                refine_interaction_aware_rigid_v3(context, &source, max_steps, v3_config),
            )?
            else {
                return Ok(());
            };
            validate_independent_rigid_evidence(
                backend,
                &row.selected,
                &expected,
                rigid_coordinates,
                0,
                slot,
                ligand_count,
            )?;
        }
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
        | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE => {
            let v3_lane =
                requested_mode == sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
            let Some(expected) = bind_independent_rigid_outcome(
                row,
                refine_interaction_aware_rigid_v6(
                    context,
                    &source,
                    max_steps,
                    v3_lane,
                    v2_config,
                    v3_config,
                    clearance_config,
                ),
            )?
            else {
                return Ok(());
            };
            if bool_from_abi(
                row.baseline_duplicate_of_v2,
                "rigid replay baseline duplicate",
            )? != expected.baseline_duplicate_of_v2()
                || bool_from_abi(row.clearance_evaluated, "rigid replay clearance evaluation")?
                    != expected.clearance_evaluated()
                || bool_from_abi(row.clearance_selected, "rigid replay clearance selection")?
                    != expected.clearance_selected()
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 V6 decision flags disagree with independent source-pose replay",
                ));
            }
            validate_independent_rigid_evidence(
                backend,
                &row.selected,
                expected.selected(),
                rigid_coordinates,
                0,
                slot,
                ligand_count,
            )?;
            for (observed, expected, first_channel) in [
                (&row.comparison_v2, expected.comparison_v2(), 3_usize),
                (&row.baseline_v3, expected.baseline_v3(), 6_usize),
                (&row.clearance_v4, expected.clearance_v4(), 9_usize),
            ] {
                if let Some(expected) = expected {
                    validate_independent_rigid_evidence(
                        backend,
                        observed,
                        expected,
                        rigid_coordinates,
                        first_channel,
                        slot,
                        ligand_count,
                    )?;
                } else if !rigid_evidence_is_zero(observed) {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 V6 retained evidence absent from independent replay",
                    ));
                }
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 rigid replay used an unknown candidate mode",
            ));
        }
    }
    Ok(())
}

fn torsion_row_values(row: &sys::bg_docking_torsion_v7_row_v1) -> [f64; 14] {
    [
        row.source_receptor_penalty,
        row.source_internal_penalty,
        row.source_combined_penalty,
        row.baseline_receptor_penalty,
        row.baseline_internal_penalty,
        row.baseline_combined_penalty,
        row.optimized_receptor_penalty,
        row.optimized_internal_penalty,
        row.optimized_combined_penalty,
        row.final_receptor_penalty,
        row.final_internal_penalty,
        row.final_combined_penalty,
        row.evaluated_total_torsion_path_radians,
        row.accepted_total_torsion_path_radians,
    ]
}

fn torsion_failure_evidence_is_zero(row: &sys::bg_docking_torsion_v7_row_v1) -> bool {
    row.skip_reason == 0
        && row.selection_reason == 0
        && row.selection_window_reachable == 0
        && row.evaluation_stopped_after_selection_window_became_unreachable == 0
        && row.torsion_evaluated == 0
        && row.torsion_variant_available == 0
        && row.torsion_selected == 0
        && row.torsion_step_budget == 0
        && row.fixed_objective_evaluation_count == 0
        && row.torsion_trial_objective_evaluation_count == 0
        && row.evaluated_torsion_steps == 0
        && row.accepted_torsion_steps == 0
        && row.baseline_v6_accepted_steps == 0
        && torsion_row_values(row).iter().all(|value| *value == 0.0)
}

fn torsion_move_is_zero(row: &sys::bg_docking_torsion_v7_move_v1) -> bool {
    row.evaluated == 0
        && row.selected == 0
        && row.rotatable_child_atom_index == 0
        && row.delta_radians == 0.0
        && row.receptor_penalty == 0.0
        && row.internal_penalty == 0.0
        && row.combined_penalty == 0.0
}

#[allow(clippy::too_many_arguments)]
fn validate_torsion_evidence(
    rows: &[sys::bg_docking_torsion_v7_row_v1],
    moves: &[sys::bg_docking_torsion_v7_move_v1],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    proposal_is_torsion_eligible: &[u8],
    torsion_max_steps: &[u64],
    maximum_torsion_steps: u64,
    rotatable_child_atom_indices: &[u64],
    torsion_coordinates: &[Vec<f64>; 8],
    rigid_coordinates: &[Vec<f64>; 12],
    baseline_torsion_angles_radians: &[f64],
    ligand_atom_count: u64,
) -> Result<()> {
    let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion ligand denominator does not fit usize",
        )
    })?;
    let coordinate_count = rows.len().checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion coordinate denominator overflowed",
        )
    })?;
    if rows.len() != sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize
        || moves.len() != rows.len() * moves_per_slot
        || rigid_rows.len() != rows.len()
        || proposal_is_torsion_eligible.len() != rows.len()
        || torsion_max_steps.len() != rows.len()
        || torsion_coordinates
            .iter()
            .any(|channel| channel.len() != coordinate_count)
        || rigid_coordinates
            .iter()
            .any(|channel| channel.len() != coordinate_count)
        || baseline_torsion_angles_radians.len() != coordinate_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion denominator is invalid",
        ));
    }
    for (slot, row) in rows.iter().enumerate() {
        let rigid = &rigid_rows[slot];
        let v6_ready = rigid.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
            && matches!(
                rigid.candidate_mode,
                sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
                    | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE
            );
        let window_reachable = bool_from_abi(
            row.selection_window_reachable,
            "torsion selection-window reachability",
        )?;
        let stopped = bool_from_abi(
            row.evaluation_stopped_after_selection_window_became_unreachable,
            "torsion evaluation stop",
        )?;
        let evaluated = bool_from_abi(row.torsion_evaluated, "torsion evaluation")?;
        let variant_available = bool_from_abi(
            row.torsion_variant_available,
            "torsion variant availability",
        )?;
        let selected = bool_from_abi(row.torsion_selected, "torsion selection")?;
        if row.slot_index as usize != slot
            || row.reserved0.iter().any(|value| *value != 0)
            || row.reserved.iter().any(|value| *value != 0)
            || torsion_row_values(row)
                .iter()
                .any(|value| !value.is_finite())
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 torsion row ABI shape or numeric evidence is invalid",
            ));
        }
        match row.status {
            sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE => {
                if row.failure_code < sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE
                    || row.failure_code > sys::BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE
                    || (!v6_ready
                        && row.failure_code
                            != sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE)
                    || !torsion_failure_evidence_is_zero(row)
                    || !coordinate_segment_matches(
                        &torsion_coordinates
                            .iter()
                            .map(Vec::as_slice)
                            .collect::<Vec<_>>(),
                        slot,
                        ligand_atom_count,
                        true,
                    )?
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion typed failure retained optimization evidence",
                    ));
                }
            }
            sys::BG_DOCKING_TORSION_V7_ROW_REFINED => {
                let expected_baseline_steps = rigid.selected.accepted_steps;
                let expected_step_budget = maximum_torsion_steps
                    .min(torsion_max_steps[slot].saturating_sub(expected_baseline_steps));
                let input_eligible = proposal_is_torsion_eligible[slot] == 1;
                if row.failure_code != sys::BG_DOCKING_TORSION_V7_FAILURE_NONE
                    || !v6_ready
                    || row.baseline_v6_accepted_steps != expected_baseline_steps
                    || row.torsion_step_budget != expected_step_budget
                    || row.skip_reason < sys::BG_DOCKING_TORSION_V7_SKIP_NONE
                    || row.skip_reason
                        > sys::BG_DOCKING_TORSION_V7_SKIP_SELECTION_WINDOW_UNREACHABLE
                    || row.selection_reason
                        < sys::BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW
                    || row.selection_reason
                        > sys::BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_NO_REDUCTION
                    || row.fixed_objective_evaluation_count != 2
                    || row.evaluated_torsion_steps > moves_per_slot as u64
                    || row.evaluated_torsion_steps > row.torsion_step_budget
                    || row.accepted_torsion_steps > row.evaluated_torsion_steps
                    || evaluated != (row.skip_reason == sys::BG_DOCKING_TORSION_V7_SKIP_NONE)
                    || variant_available != (row.evaluated_torsion_steps != 0)
                    || (!evaluated && row.evaluated_torsion_steps != 0)
                    || (selected && row.accepted_torsion_steps != row.evaluated_torsion_steps)
                    || (!selected && row.accepted_torsion_steps != 0)
                    || (selected
                        && row.selection_reason
                            != sys::BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW)
                    || (!selected
                        && row.selection_reason
                            == sys::BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW)
                    || (selected
                        && row.accepted_total_torsion_path_radians
                            != row.evaluated_total_torsion_path_radians)
                    || (!selected && row.accepted_total_torsion_path_radians != 0.0)
                    || row.evaluated_total_torsion_path_radians < 0.0
                    || (stopped
                        && (!window_reachable || !evaluated || row.evaluated_torsion_steps == 0))
                    || (!input_eligible
                        && (row.skip_reason != sys::BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE
                            || evaluated
                            || variant_available
                            || selected
                            || row.evaluated_torsion_steps != 0))
                    || (input_eligible
                        && row.skip_reason == sys::BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE)
                    || !coordinate_segment_matches(
                        &torsion_coordinates
                            .iter()
                            .map(Vec::as_slice)
                            .collect::<Vec<_>>(),
                        slot,
                        ligand_atom_count,
                        false,
                    )?
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion refinement evidence is inconsistent",
                    ));
                }
                let rigid_selected = [
                    rigid_coordinates[0].as_slice(),
                    rigid_coordinates[1].as_slice(),
                    rigid_coordinates[2].as_slice(),
                ];
                let optimized = [
                    torsion_coordinates[0].as_slice(),
                    torsion_coordinates[1].as_slice(),
                    torsion_coordinates[2].as_slice(),
                ];
                let final_coordinates = [
                    torsion_coordinates[4].as_slice(),
                    torsion_coordinates[5].as_slice(),
                    torsion_coordinates[6].as_slice(),
                ];
                let optimized_from_baseline = row.evaluated_torsion_steps != 0
                    || (coordinate_segments_equal(optimized, rigid_selected, slot, ligand_count)
                        && scalar_segments_equal(
                            &torsion_coordinates[3],
                            baseline_torsion_angles_radians,
                            slot,
                            ligand_count,
                        ));
                let final_matches_selection = if selected {
                    coordinate_segments_equal(final_coordinates, optimized, slot, ligand_count)
                        && scalar_segments_equal(
                            &torsion_coordinates[7],
                            &torsion_coordinates[3],
                            slot,
                            ligand_count,
                        )
                } else {
                    coordinate_segments_equal(final_coordinates, rigid_selected, slot, ligand_count)
                        && scalar_segments_equal(
                            &torsion_coordinates[7],
                            baseline_torsion_angles_radians,
                            slot,
                            ligand_count,
                        )
                };
                if !optimized_from_baseline || !final_matches_selection {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion coordinate or angle channel disagrees with selection semantics",
                    ));
                }
            }
            _ => {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 torsion row status is unknown",
                ));
            }
        }
        for move_index in 0..moves_per_slot {
            let movement = &moves[slot * moves_per_slot + move_index];
            let move_evaluated = bool_from_abi(movement.evaluated, "torsion move evaluation")?;
            let move_selected = bool_from_abi(movement.selected, "torsion move selection")?;
            let expected_evaluated = row.status == sys::BG_DOCKING_TORSION_V7_ROW_REFINED
                && move_index < row.evaluated_torsion_steps as usize;
            if movement.slot_index as usize != slot
                || movement.move_index as usize != move_index
                || movement.reserved0 != 0
                || movement.reserved.iter().any(|value| *value != 0)
                || [
                    movement.delta_radians,
                    movement.receptor_penalty,
                    movement.internal_penalty,
                    movement.combined_penalty,
                ]
                .iter()
                .any(|value| !value.is_finite())
                || move_evaluated != expected_evaluated
                || (expected_evaluated
                    && (!rotatable_child_atom_indices
                        .contains(&movement.rotatable_child_atom_index)
                        || movement.delta_radians == 0.0
                        || movement.receptor_penalty < 0.0
                        || movement.internal_penalty < 0.0
                        || movement.combined_penalty < 0.0
                        || move_selected != selected))
                || (!expected_evaluated && !torsion_move_is_zero(movement))
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 torsion move evidence disagrees with its parent row",
                ));
            }
        }
    }
    Ok(())
}

fn independently_composed_final_quaternion(
    producer: &sys::bg_docking_fixed64_producer_row_v1,
    rigid: &sys::bg_docking_rigid_refinement_row_v1,
) -> Result<[f64; 4]> {
    let source = [
        producer.placement_quaternion_x,
        producer.placement_quaternion_y,
        producer.placement_quaternion_z,
        producer.placement_quaternion_w,
    ];
    let rotation = rigid.selected.total_rotation_vector_radians;
    let angle =
        (rotation[0] * rotation[0] + rotation[1] * rotation[1] + rotation[2] * rotation[2]).sqrt();
    if !angle.is_finite() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rigid rotation cannot produce a finite final quaternion",
        ));
    }
    if angle == 0.0 {
        return Ok(source);
    }
    let scale = (0.5 * angle).sin() / angle;
    let delta = [
        rotation[0] * scale,
        rotation[1] * scale,
        rotation[2] * scale,
        (0.5 * angle).cos(),
    ];
    let mut result = [
        delta[3] * source[0] + delta[0] * source[3] + delta[1] * source[2] - delta[2] * source[1],
        delta[3] * source[1] - delta[0] * source[2] + delta[1] * source[3] + delta[2] * source[0],
        delta[3] * source[2] + delta[0] * source[1] - delta[1] * source[0] + delta[2] * source[3],
        delta[3] * source[3] - delta[0] * source[0] - delta[1] * source[1] - delta[2] * source[2],
    ];
    for component in &mut result {
        if *component == 0.0 {
            *component = 0.0;
        }
    }
    Ok(result)
}

#[allow(clippy::too_many_arguments)]
fn validate_refinement_evidence(
    rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    producer_rows: &[sys::bg_docking_fixed64_producer_row_v1],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    requested_modes: &[sys::bg_docking_rigid_refinement_candidate_mode],
    rigid_coordinates: [&[f64]; 3],
    torsion_final_coordinates: [&[f64]; 3],
    final_coordinates: [&[f64]; 3],
    quaternions: [&[f64]; 4],
    ligand_atom_count: u64,
    backend: Backend,
) -> Result<()> {
    if rows.len() != producer_rows.len()
        || rows.len() != rigid_rows.len()
        || rows.len() != torsion_rows.len()
        || rows.len() != requested_modes.len()
        || quaternions.iter().any(|values| values.len() != rows.len())
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement denominator is invalid",
        ));
    }
    for (slot, row) in rows.iter().enumerate() {
        let applicable = bool_from_abi(
            row.torsion_v7_applicable,
            "refinement torsion applicability",
        )?;
        let selected = bool_from_abi(row.torsion_v7_selected, "refinement torsion selection")?;
        let coordinate_available = bool_from_abi(
            row.coordinate_available,
            "refinement coordinate availability",
        )?;
        let rigid = &rigid_rows[slot];
        let torsion = &torsion_rows[slot];
        let v6_mode = matches!(
            rigid.candidate_mode,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
                | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE
        );
        let quaternion = [
            quaternions[0][slot],
            quaternions[1][slot],
            quaternions[2][slot],
            quaternions[3][slot],
        ];
        let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 refinement ligand denominator does not fit usize",
            )
        })?;
        if row.slot_index as usize != slot
            || row.reserved0 != 0
            || row.reserved.iter().any(|value| *value != 0)
            || row.rigid_failure_code != rigid.failure_code
            || row.selected_rigid_profile != rigid.selected_profile
            || selected && !applicable
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 refinement row identity is inconsistent",
            ));
        }
        match row.status {
            sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY => {
                let expected_origin = if v6_mode {
                    sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_TORSION_V7_FINAL
                } else {
                    sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED
                };
                let origin_coordinates = if v6_mode {
                    torsion_final_coordinates
                } else {
                    rigid_coordinates
                };
                let final_coordinate_digest =
                    coordinate_segment(final_coordinates, slot, ligand_count)
                        .map(canonical_coordinate_sha256);
                let expected_quaternion =
                    independently_composed_final_quaternion(&producer_rows[slot], rigid)?;
                let quaternion_matches = expected_quaternion
                    .into_iter()
                    .zip(quaternion)
                    .all(|(expected, observed)| numeric_matches(backend, expected, observed));
                if row.failure_stage != sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE
                    || row.coordinate_origin != expected_origin
                    || rigid.status != sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
                    || rigid.failure_code != sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE
                    || row.downstream_candidate_state != sys::BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE
                    || applicable != v6_mode
                    || (v6_mode
                        && (torsion.status != sys::BG_DOCKING_TORSION_V7_ROW_REFINED
                            || row.torsion_v7_failure_code
                                != sys::BG_DOCKING_TORSION_V7_FAILURE_NONE
                            || selected != (torsion.torsion_selected == 1)))
                    || (!v6_mode && (row.torsion_v7_failure_code != 0 || selected))
                    || !coordinate_available
                    || !digest_present(&row.coordinate_sha256)
                    || final_coordinate_digest != Some(row.coordinate_sha256)
                    || !coordinate_segments_equal(
                        final_coordinates,
                        origin_coordinates,
                        slot,
                        ligand_count,
                    )
                    || !coordinate_segment_matches(
                        &final_coordinates,
                        slot,
                        ligand_atom_count,
                        false,
                    )?
                    || !unit_quaternion(quaternion)
                    || !quaternion_matches
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 coordinate-ready refinement evidence is invalid",
                    ));
                }
            }
            sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE => {
                let rigid_failure = row.failure_stage
                    == sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_RIGID
                    && rigid.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE
                    && row.rigid_failure_code
                        >= sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE
                    && row.rigid_failure_code
                        <= sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE
                    && row.torsion_v7_failure_code == 0
                    && !applicable;
                let torsion_failure = row.failure_stage
                    == sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_TORSION_V7
                    && rigid.status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
                    && v6_mode
                    && applicable
                    && torsion.status == sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE
                    && row.torsion_v7_failure_code == torsion.failure_code;
                if (!rigid_failure && !torsion_failure)
                    || row.coordinate_origin != sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_NONE
                    || row.downstream_candidate_state
                        != sys::BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE
                    || selected
                    || coordinate_available
                    || digest_present(&row.coordinate_sha256)
                    || !coordinate_segment_matches(
                        &final_coordinates,
                        slot,
                        ligand_atom_count,
                        true,
                    )?
                    || quaternion.iter().any(|value| *value != 0.0)
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 refinement typed failure retained coordinate evidence",
                    ));
                }
            }
            _ => {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 refinement row status is unknown",
                ));
            }
        }
    }
    Ok(())
}

fn hash_coordinate_segment(
    hash: &mut CanonicalHasher,
    channels: [&[f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> Result<()> {
    let coordinates = coordinate_segment(channels, slot, ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence coordinate segment exceeds its buffer",
        )
    })?;
    hash.usize(ligand_count);
    for atom in 0..ligand_count {
        hash.f64(coordinates.x_angstrom[atom]);
        hash.f64(coordinates.y_angstrom[atom]);
        hash.f64(coordinates.z_angstrom[atom]);
    }
    Ok(())
}

fn hash_scalar_segment(
    hash: &mut CanonicalHasher,
    values: &[f64],
    slot: usize,
    ligand_count: usize,
) -> Result<()> {
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence scalar offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence scalar end overflowed",
        )
    })?;
    let segment = values.get(begin..end).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence scalar segment exceeds its buffer",
        )
    })?;
    hash.usize(segment.len());
    for value in segment {
        hash.f64(*value);
    }
    Ok(())
}

fn hash_rigid_evidence(
    hash: &mut CanonicalHasher,
    value: &sys::bg_docking_rigid_refinement_evidence_v1,
) {
    hash.i32(value.profile);
    hash.byte(value.available);
    hash.u64(value.accepted_steps);
    hash.u64(value.accepted_translation_steps);
    hash.u64(value.accepted_rotation_steps);
    hash.u64(value.line_search_evaluation_count);
    hash.u64(value.fallback_direction_step_count);
    hash.f64(value.initial_penalty);
    hash.f64(value.final_penalty);
    for component in value.total_translation_angstrom {
        hash.f64(component);
    }
    for component in value.total_rotation_vector_radians {
        hash.f64(component);
    }
    hash.f64(value.total_rotation_path_radians);
    hash.f64(value.initial_centroid_offset_angstrom);
    hash.f64(value.final_centroid_offset_angstrom);
    hash.f64(value.maximum_centroid_offset_angstrom);
}

#[allow(clippy::too_many_arguments)]
fn canonical_refinement_evidence(
    slot: usize,
    ligand_count: usize,
    rigid_row: &sys::bg_docking_rigid_refinement_row_v1,
    torsion_row: &sys::bg_docking_torsion_v7_row_v1,
    torsion_moves: &[sys::bg_docking_torsion_v7_move_v1],
    refinement_row: &sys::bg_docking_fixed64_refinement_row_v1,
    rigid_coordinates: &[Vec<f64>; 12],
    torsion_coordinates: &[Vec<f64>; 8],
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
) -> Result<Sha256> {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_evidence/1.0.0");
    hash.usize(slot);
    hash.i32(rigid_row.status);
    hash.i32(rigid_row.failure_code);
    hash.i32(rigid_row.candidate_mode);
    hash.i32(rigid_row.selected_profile);
    hash.byte(rigid_row.baseline_duplicate_of_v2);
    hash.byte(rigid_row.clearance_evaluated);
    hash.byte(rigid_row.clearance_selected);
    hash_rigid_evidence(&mut hash, &rigid_row.selected);
    hash_rigid_evidence(&mut hash, &rigid_row.comparison_v2);
    hash_rigid_evidence(&mut hash, &rigid_row.baseline_v3);
    hash_rigid_evidence(&mut hash, &rigid_row.clearance_v4);
    for offset in [0, 3, 6, 9] {
        hash_coordinate_segment(
            &mut hash,
            [
                rigid_coordinates[offset].as_slice(),
                rigid_coordinates[offset + 1].as_slice(),
                rigid_coordinates[offset + 2].as_slice(),
            ],
            slot,
            ligand_count,
        )?;
    }
    hash.i32(torsion_row.status);
    hash.i32(torsion_row.failure_code);
    hash.i32(torsion_row.skip_reason);
    hash.i32(torsion_row.selection_reason);
    hash.byte(torsion_row.selection_window_reachable);
    hash.byte(torsion_row.evaluation_stopped_after_selection_window_became_unreachable);
    hash.byte(torsion_row.torsion_evaluated);
    hash.byte(torsion_row.torsion_variant_available);
    hash.byte(torsion_row.torsion_selected);
    hash.u64(torsion_row.torsion_step_budget);
    hash.u64(torsion_row.fixed_objective_evaluation_count);
    hash.u64(torsion_row.torsion_trial_objective_evaluation_count);
    hash.u64(torsion_row.evaluated_torsion_steps);
    hash.u64(torsion_row.accepted_torsion_steps);
    hash.u64(torsion_row.baseline_v6_accepted_steps);
    for value in torsion_row_values(torsion_row) {
        hash.f64(value);
    }
    let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
    let move_begin = slot.checked_mul(moves_per_slot).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement move offset overflowed",
        )
    })?;
    let move_end = move_begin.checked_add(moves_per_slot).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement move end overflowed",
        )
    })?;
    for movement in torsion_moves.get(move_begin..move_end).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement move evidence is incomplete",
        )
    })? {
        hash.u32(movement.slot_index);
        hash.u32(movement.move_index);
        hash.byte(movement.evaluated);
        hash.byte(movement.selected);
        hash.u64(movement.rotatable_child_atom_index);
        hash.f64(movement.delta_radians);
        hash.f64(movement.receptor_penalty);
        hash.f64(movement.internal_penalty);
        hash.f64(movement.combined_penalty);
    }
    hash_coordinate_segment(
        &mut hash,
        [
            torsion_coordinates[0].as_slice(),
            torsion_coordinates[1].as_slice(),
            torsion_coordinates[2].as_slice(),
        ],
        slot,
        ligand_count,
    )?;
    hash_scalar_segment(&mut hash, &torsion_coordinates[3], slot, ligand_count)?;
    hash_coordinate_segment(
        &mut hash,
        [
            torsion_coordinates[4].as_slice(),
            torsion_coordinates[5].as_slice(),
            torsion_coordinates[6].as_slice(),
        ],
        slot,
        ligand_count,
    )?;
    hash_scalar_segment(&mut hash, &torsion_coordinates[7], slot, ligand_count)?;
    hash.i32(refinement_row.status);
    hash.i32(refinement_row.failure_stage);
    hash.i32(refinement_row.coordinate_origin);
    hash.i32(refinement_row.rigid_failure_code);
    hash.i32(refinement_row.torsion_v7_failure_code);
    hash.i32(refinement_row.selected_rigid_profile);
    hash.i32(refinement_row.downstream_candidate_state);
    hash.byte(refinement_row.torsion_v7_applicable);
    hash.byte(refinement_row.torsion_v7_selected);
    hash.byte(refinement_row.coordinate_available);
    hash.digest(refinement_row.coordinate_sha256);
    hash_coordinate_segment(&mut hash, final_coordinates, slot, ligand_count)?;
    hash.f64(final_quaternions[0][slot]);
    hash.f64(final_quaternions[1][slot]);
    hash.f64(final_quaternions[2][slot]);
    hash.f64(final_quaternions[3][slot]);
    Ok(hash.finish())
}

fn canonical_scorer_evidence(row: &sys::bg_docking_scorer_v1_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scorer_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.i32(row.failure_code);
    for term in row.weighted_terms {
        hash.f64(term);
    }
    hash.f64(row.total_score);
    hash.u64(row.receptor_candidate_pair_count);
    hash.u64(row.ligand_pair_count);
    hash.u64(row.hbond_count);
    hash.u64(row.hydrophobic_contact_count);
    hash.u64(row.buried_polar_count);
    hash.finish()
}

fn canonical_validity_evidence(row: &sys::bg_docking_pose_validity_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_validity_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.i32(row.failure_code);
    hash.i32(row.upstream_scorer_failure_code);
    hash.u32(row.passed_check_mask);
    hash.u32(row.blocker_mask);
    hash.u64(row.observed_count);
    hash.u64(row.atom_count);
    hash.f64(row.rotation_orthogonality_max_error);
    hash.f64(row.rotation_determinant);
    hash.f64(row.max_bond_length_delta_angstrom);
    hash.f64(row.minimum_ligand_nonbonded_distance_angstrom);
    hash.u64(row.evaluated_ligand_nonbonded_pair_count);
    hash.u64(row.excluded_ligand_pair_count);
    hash.f64(row.minimum_receptor_ligand_distance_angstrom);
    hash.u64(row.evaluated_receptor_ligand_pair_count);
    hash.f64(row.minimum_declared_chiral_volume);
    hash.u64(row.declared_chirality_center_count);
    hash.f64(row.maximum_pocket_center_distance_angstrom);
    hash.u64(row.element_vdw_ligand_pair_count);
    hash.u64(row.element_vdw_ligand_severe_overlap_count);
    hash.f64(row.element_vdw_ligand_minimum_distance_angstrom);
    hash.f64(row.element_vdw_ligand_minimum_ratio);
    hash.u64(row.element_vdw_receptor_candidate_pair_count);
    hash.u64(row.element_vdw_receptor_full_cartesian_pair_count);
    hash.u64(row.element_vdw_receptor_cell_count);
    hash.u64(row.element_vdw_receptor_severe_overlap_count);
    hash.f64(row.element_vdw_receptor_minimum_distance_angstrom);
    hash.f64(row.element_vdw_receptor_minimum_ratio);
    hash.finish()
}

fn canonical_ranking_evidence(row: &sys::bg_docking_stable_top_k_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_ranking_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.byte(row.rank_eligible);
    hash.byte(row.valid_rank_eligible);
    hash.u32(row.stable_rank);
    hash.u32(row.stable_valid_rank);
    hash.f64(row.total_score);
    hash.digest(row.coordinate_sha256);
    hash.finish()
}

fn canonical_cluster_evidence(row: &sys::bg_docking_rmsd_cluster_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_cluster_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.byte(row.cluster_eligible);
    hash.byte(row.representative);
    hash.byte(row.top_k_representative);
    hash.u32(row.stable_valid_rank);
    hash.u32(row.cluster_id);
    hash.u32(row.representative_slot_index);
    hash.u32(row.cluster_rank);
    hash.u32(row.top_k_rank);
    hash.u32(row.cluster_size);
    hash.f64(row.direct_rmsd_to_representative_angstrom);
    hash.digest(row.coordinate_sha256);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
fn canonical_pipeline_row_receipt(
    row: &sys::bg_docking_fixed64_pipeline_row_v1,
    component_binding_receipt: Sha256,
    refinement_policy_receipt: Sha256,
    refinement_evidence: Sha256,
    scorer_evidence: Sha256,
    validity_evidence: Sha256,
    ranking_evidence: Sha256,
    cluster_evidence: Sha256,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_complete_pipeline_row/1.0.0");
    hash.string("betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0");
    hash.digest(component_binding_receipt);
    hash.digest(refinement_policy_receipt);
    hash.u32(row.slot_index);
    for value in [
        row.producer_status,
        row.producer_failure_code,
        row.initial_admission_decision,
        row.requested_refinement_mode,
        row.effective_refinement_mode,
        row.refinement_status,
        row.refinement_failure_stage,
        row.scorer_status,
        row.scorer_failure_code,
        row.validity_status,
        row.validity_failure_code,
    ] {
        hash.i32(value);
    }
    hash.u32(row.stable_rank);
    hash.u32(row.stable_valid_rank);
    hash.i32(row.cluster_status);
    hash.u32(row.cluster_id);
    hash.u32(row.cluster_rank);
    hash.u32(row.top_k_rank);
    hash.digest(row.producer_row_receipt_sha256);
    hash.digest(row.final_coordinate_sha256);
    hash.digest(refinement_evidence);
    hash.digest(scorer_evidence);
    hash.digest(validity_evidence);
    hash.digest(ranking_evidence);
    hash.digest(cluster_evidence);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
fn validate_pipeline_receipt_bindings(
    row: &sys::bg_docking_fixed64_pipeline_row_v1,
    component_binding_receipt: Sha256,
    refinement_policy_receipt: Sha256,
    expected_refinement_evidence: Sha256,
    expected_scorer_evidence: Sha256,
    expected_validity_evidence: Sha256,
    expected_ranking_evidence: Sha256,
    expected_cluster_evidence: Sha256,
) -> Result<()> {
    let expected_row_receipt = canonical_pipeline_row_receipt(
        row,
        component_binding_receipt,
        refinement_policy_receipt,
        expected_refinement_evidence,
        expected_scorer_evidence,
        expected_validity_evidence,
        expected_ranking_evidence,
        expected_cluster_evidence,
    );
    if row.refinement_evidence_sha256 != expected_refinement_evidence
        || row.scorer_evidence_sha256 != expected_scorer_evidence
        || row.validity_evidence_sha256 != expected_validity_evidence
        || row.ranking_evidence_sha256 != expected_ranking_evidence
        || row.cluster_evidence_sha256 != expected_cluster_evidence
        || row.row_receipt_sha256 != expected_row_receipt
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 pipeline receipt graph does not authenticate its component evidence",
        ));
    }
    Ok(())
}

const NATIVE_FIXED64_SINGLE_ANCHOR_ABI_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_single_anchor_placement/1.0.0";

#[derive(Debug, Clone, PartialEq)]
struct NativePlacementReplay {
    status: i32,
    failure_code: i32,
    coordinates: Vec<Vec3>,
    quaternion: Quaternion,
    output_coordinate_sha256: Sha256,
    placement_receipt_sha256: Sha256,
}

fn canonical_single_anchor_shared_receipt(
    output: &sys::bg_docking_fixed64_single_anchor_output_v1,
    source: Fixed64SourceEvidence,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_single_anchor_abi/native-v1");
    hash.string(NATIVE_FIXED64_SINGLE_ANCHOR_ABI_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID);
    hash.digest(output.allocation_inventory_sha256);
    hash.digest(output.allocation_receipt_sha256);
    hash.digest(output.allocation_slot_receipt_sha256);
    hash.u32(output.slot_index);
    hash.u32(output.lane as u32);
    hash.u32(output.lane_offset);
    hash.u32(output.anchor_kind as u32);
    hash.u32(output.backend as u32);
    hash.digest(source.receipt_sha256);
    hash.digest(source.proposal_sha256);
    hash.digest(source.coordinate_sha256);
    hash.digest(output.feature_geometry_inventory_sha256);
    hash.digest(output.selected_ligand_feature_geometry_sha256);
    hash.digest(output.selected_receptor_feature_geometry_sha256);
    hash.u32(output.status as u32);
    hash.u32(output.failure_code as u32);
    for value in [
        output.ligand_anchor_point_angstrom,
        output.receptor_anchor_point_angstrom,
        output.target_anchor_point_angstrom,
        output.local_surface_normal,
        output.approach_vector,
        output.ligand_direction,
        output.alignment_target_direction,
    ] {
        hash.vec3(Vec3::new(value[0], value[1], value[2]));
    }
    hash.f64(output.target_distance_angstrom);
    hash.f64(output.twist_angle_radians);
    hash.f64(output.quaternion_x);
    hash.f64(output.quaternion_y);
    hash.f64(output.quaternion_z);
    hash.f64(output.quaternion_w);
    hash.vec3(Vec3::new(
        output.translation_angstrom[0],
        output.translation_angstrom[1],
        output.translation_angstrom[2],
    ));
    hash.digest(output.output_coordinate_sha256);
    hash.digest([0; 32]);
    hash.digest([0; 32]);
    for value in [output.coordinates_written, 0, 1, 1, 1, 0, 0, 0, 0, 1] {
        hash.byte(value);
    }
    for _ in 0..7 {
        hash.byte(0);
    }
    hash.finish()
}

fn replay_coordinates(written: u8, x: &[f64], y: &[f64], z: &[f64]) -> Result<Vec<Vec3>> {
    match written {
        0 => Ok(Vec::new()),
        1 => Ok(x
            .iter()
            .zip(y)
            .zip(z)
            .map(|((x, y), z)| Vec3::new(*x, *y, *z))
            .collect()),
        _ => Err(Error::local(
            ErrorCode::AbiMismatch,
            "native placement replay returned a non-boolean coordinate flag",
        )),
    }
}

#[allow(clippy::too_many_arguments)]
fn replay_native_placements(
    context: &Context,
    admission: NonNull<sys::bg_docking_geometric_admission_v1>,
    allocation_input: &sys::bg_docking_fixed64_allocation_input_v1,
    producer_input: &sys::bg_docking_fixed64_producer_input_v1,
    expected_allocation: &IndependentFixed64Allocation,
    expected_feature_geometry_inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
    expected_sources: &[Option<Fixed64CoordinateSource<'_>>],
    ligand_atom_count: usize,
    pocket_center_angstrom: [f64; 3],
    pocket_normal: [f64; 3],
    backend: Backend,
) -> Result<[Option<NativePlacementReplay>; 64]> {
    const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    let mut allocation_rows =
        vec![zeroed_abi_value!(sys::bg_docking_fixed64_allocation_row_v1); CANDIDATE_COUNT];
    let mut allocation_output = init(sys::bg_docking_fixed64_allocation_output_v1_init)?;
    allocation_output.row_capacity = CANDIDATE_COUNT as u64;
    allocation_output.rows = allocation_rows.as_mut_ptr();
    // SAFETY: the input descriptor and exact-capacity output remain live for the call.
    status_result(unsafe {
        sys::bg_docking_fixed64_allocation_v1_build(allocation_input, &mut allocation_output)
    })?;
    if allocation_output.row_count != CANDIDATE_COUNT as u64
        || allocation_output.inventory_sha256 != expected_allocation.inventory_sha256()
        || allocation_output.allocation_receipt_sha256 != expected_allocation.receipt_sha256()
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native placement replay allocation disagrees with independent allocation",
        ));
    }
    let ligand_atom_count_u64 = u64::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::CapacityOverflow,
            "native placement replay ligand denominator does not fit u64",
        )
    })?;
    let mut replays: [Option<NativePlacementReplay>; CANDIDATE_COUNT] =
        std::array::from_fn(|_| None);
    for slot_index in 0..CANDIDATE_COUNT {
        let Some((_, placement_kind)) = fixed64_lane_and_placement_for_slot(slot_index) else {
            continue;
        };
        if !matches!(
            placement_kind,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
                | sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
        ) || !expected_allocation.slots()[slot_index].generation_eligible()
        {
            continue;
        }
        let Some(source) = expected_sources[slot_index] else {
            continue;
        };
        if placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
            && !selected_feature_geometry_available(
                &expected_allocation.slots()[slot_index],
                expected_feature_geometry_inventory,
            )
        {
            continue;
        }
        let source_input = raw_coordinate_source(source, ligand_atom_count_u64);
        let mut x = vec![0.0; ligand_atom_count];
        let mut y = vec![0.0; ligand_atom_count];
        let mut z = vec![0.0; ligand_atom_count];
        if placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3 {
            let mut input = init(sys::bg_docking_fixed64_indexed_so3_input_v1_init)?;
            input.allocation_inventory_sha256 = allocation_output.inventory_sha256;
            input.allocation_receipt_sha256 = allocation_output.allocation_receipt_sha256;
            input.allocation_row_count = allocation_output.row_count;
            input.allocation_rows = allocation_rows.as_ptr();
            input.slot_index = slot_index as u32;
            input.source = source_input.source;
            input.ligand_atom_count = ligand_atom_count_u64;
            input.source_x_angstrom = source_input.x_angstrom;
            input.source_y_angstrom = source_input.y_angstrom;
            input.source_z_angstrom = source_input.z_angstrom;
            input.pocket_center_angstrom = pocket_center_angstrom;
            input.pocket_normal = pocket_normal;
            let mut output = init(sys::bg_docking_fixed64_indexed_so3_output_v1_init)?;
            output.coordinate_capacity = ligand_atom_count_u64;
            output.x_angstrom = x.as_mut_ptr();
            output.y_angstrom = y.as_mut_ptr();
            output.z_angstrom = z.as_mut_ptr();
            // SAFETY: every descriptor and exact-capacity channel remains live.
            status_result(unsafe {
                sys::bg_docking_fixed64_indexed_so3_v1_place(
                    context.handle.as_ptr(),
                    &input,
                    &mut output,
                )
            })?;
            if output.slot_index as usize != slot_index
                || output.backend != backend.as_raw()
                || output.ligand_atom_count != ligand_atom_count_u64
                || output.source_identity_verified != 1
                || output.allocation_identity_verified != 1
                || output.denominator_preserved != 1
                || output.result_dependent_input_consumed != 0
                || output.molecular_execution_authorized != 0
                || output.reservation_authorized != 0
                || output.benchmark_execution_authorized != 0
                || output.production_claim_authorized != 0
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native indexed-SO3 replay violated its identity or authority boundary",
                ));
            }
            replays[slot_index] = Some(NativePlacementReplay {
                status: output.status,
                failure_code: output.failure_code,
                coordinates: replay_coordinates(output.coordinates_written, &x, &y, &z)?,
                quaternion: Quaternion::new(
                    output.quaternion_x,
                    output.quaternion_y,
                    output.quaternion_z,
                    output.quaternion_w,
                ),
                output_coordinate_sha256: output.output_coordinate_sha256,
                placement_receipt_sha256: output.placement_receipt_sha256,
            });
            continue;
        }
        let mut input = init(sys::bg_docking_fixed64_single_anchor_input_v1_init)?;
        input.allocation_input = allocation_input;
        input.slot_index = slot_index as u32;
        input.source = source_input.source;
        input.ligand_atom_count = ligand_atom_count_u64;
        input.source_x_angstrom = source_input.x_angstrom;
        input.source_y_angstrom = source_input.y_angstrom;
        input.source_z_angstrom = source_input.z_angstrom;
        input.feature_geometry_count = producer_input.feature_geometry_count;
        input.feature_geometry_rows = producer_input.feature_geometry_rows;
        input.feature_atom_index_count = producer_input.feature_atom_index_count;
        input.feature_atom_indices = producer_input.feature_atom_indices;
        input.feature_geometry_inventory_sha256 = producer_input.feature_geometry_inventory_sha256;
        let mut output = init(sys::bg_docking_fixed64_single_anchor_output_v1_init)?;
        output.coordinate_capacity = ligand_atom_count_u64;
        output.x_angstrom = x.as_mut_ptr();
        output.y_angstrom = y.as_mut_ptr();
        output.z_angstrom = z.as_mut_ptr();
        // SAFETY: every descriptor, persistent admission, and output remains live.
        status_result(unsafe {
            sys::bg_docking_fixed64_single_anchor_v1_place(
                context.handle.as_ptr(),
                admission.as_ptr(),
                &input,
                &mut output,
            )
        })?;
        if output.slot_index as usize != slot_index
            || output.backend != backend.as_raw()
            || output.ligand_atom_count != ligand_atom_count_u64
            || output.source_identity_verified != 1
            || output.allocation_identity_verified != 1
            || output.feature_identity_verified != 1
            || output.geometric_identity_verified != 1
            || output.denominator_preserved != 1
            || output.result_dependent_input_consumed != 0
            || output.fallback_allowed != 0
            || output.multi_anchor_consumed != 0
            || output.molecular_execution_authorized != 0
            || output.reservation_authorized != 0
            || output.benchmark_execution_authorized != 0
            || output.existing_rank_auto_change_authorized != 0
            || output.customer_pose_emission_authorized != 0
            || output.production_claim_authorized != 0
            || output.scientific_claim_authorized != 0
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native single-anchor replay violated its identity or authority boundary",
            ));
        }
        replays[slot_index] = Some(NativePlacementReplay {
            status: output.status,
            failure_code: output.failure_code,
            coordinates: replay_coordinates(output.coordinates_written, &x, &y, &z)?,
            quaternion: Quaternion::new(
                output.quaternion_x,
                output.quaternion_y,
                output.quaternion_z,
                output.quaternion_w,
            ),
            output_coordinate_sha256: output.output_coordinate_sha256,
            placement_receipt_sha256: canonical_single_anchor_shared_receipt(
                &output,
                source.evidence,
            ),
        });
    }
    Ok(replays)
}

fn placement_tolerance(backend: Backend) -> f64 {
    match backend {
        Backend::HipFast => 2.0e-9,
        Backend::HipSafe => 2.0e-10,
        Backend::Auto | Backend::CppCpuReference | Backend::RustCpu => 2.0e-12,
    }
}

fn placement_scalar_close(backend: Backend, observed: f64, expected: f64) -> bool {
    let scale = 1.0_f64.max(observed.abs()).max(expected.abs());
    observed.is_finite()
        && expected.is_finite()
        && (observed - expected).abs() <= placement_tolerance(backend) * scale
}

fn placement_coordinates_close(
    backend: Backend,
    observed: PositionSoa<'_>,
    expected: &[Vec3],
) -> bool {
    observed.x_angstrom.len() == expected.len()
        && observed.y_angstrom.len() == expected.len()
        && observed.z_angstrom.len() == expected.len()
        && expected.iter().enumerate().all(|(atom, expected)| {
            placement_scalar_close(backend, observed.x_angstrom[atom], expected.x)
                && placement_scalar_close(backend, observed.y_angstrom[atom], expected.y)
                && placement_scalar_close(backend, observed.z_angstrom[atom], expected.z)
        })
}

fn placement_quaternion_close(
    backend: Backend,
    row: &sys::bg_docking_fixed64_producer_row_v1,
    expected: Quaternion,
) -> bool {
    [
        (row.placement_quaternion_x, expected.x),
        (row.placement_quaternion_y, expected.y),
        (row.placement_quaternion_z, expected.z),
        (row.placement_quaternion_w, expected.w),
    ]
    .into_iter()
    .all(|(observed, expected)| placement_scalar_close(backend, observed, expected))
}

fn native_replay_coordinates_match(
    observed: PositionSoa<'_>,
    replay: &NativePlacementReplay,
) -> bool {
    observed.x_angstrom.len() == replay.coordinates.len()
        && replay
            .coordinates
            .iter()
            .enumerate()
            .all(|(atom, expected)| {
                observed.x_angstrom[atom].to_bits() == expected.x.to_bits()
                    && observed.y_angstrom[atom].to_bits() == expected.y.to_bits()
                    && observed.z_angstrom[atom].to_bits() == expected.z.to_bits()
            })
}

fn native_replay_quaternion_matches(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    replay: &NativePlacementReplay,
) -> bool {
    [
        (row.placement_quaternion_x, replay.quaternion.x),
        (row.placement_quaternion_y, replay.quaternion.y),
        (row.placement_quaternion_z, replay.quaternion.z),
        (row.placement_quaternion_w, replay.quaternion.w),
    ]
    .into_iter()
    .all(|(observed, expected)| observed.to_bits() == expected.to_bits())
}

#[derive(Debug, Clone, PartialEq)]
struct IndependentIndexedSo3Replay {
    coordinates: Vec<Vec3>,
    quaternion: Quaternion,
}

fn independent_indexed_so3_replay(
    allocation: &IndependentFixed64Allocation,
    slot_index: usize,
    source: &IndependentFixed64PlacementSource,
    pocket_center: Vec3,
    canonical_pocket_normal: Vec3,
) -> Result<std::result::Result<IndependentIndexedSo3Replay, i32>> {
    let slot = allocation.slots().get(slot_index).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 slot is outside fixed64",
        )
    })?;
    let sequence_index = slot.so3_sequence_index().ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 slot lacks its frozen sequence index",
        )
    })?;
    let parent = slot.generation_parent().ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 slot lacks its generation parent",
        )
    })?;
    let evidence = source.evidence();
    if parent.receipt_sha256 != evidence.receipt_sha256
        || parent.proposal_sha256 != evidence.proposal_sha256
        || parent.coordinate_sha256 != evidence.coordinate_sha256
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 source is cross-wired to its allocation slot",
        ));
    }
    let coordinates = source.coordinates_angstrom();
    let first = coordinates[0];
    if !coordinates[1..]
        .iter()
        .any(|coordinate| coordinate.minus(first).norm_squared() > 1.0e-12)
    {
        return Ok(Err(
            sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY,
        ));
    }
    if !canonical_pocket_normal.is_finite()
        || (canonical_pocket_normal.norm() - 1.0).abs() > 1.0e-15
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 pocket normal is not canonical",
        ));
    }
    let mut seed = CanonicalHasher::new("betelgeuze.fixed64_indexed_so3_seed/native-v1");
    seed.digest(evidence.receipt_sha256);
    seed.digest(evidence.proposal_sha256);
    seed.digest(evidence.coordinate_sha256);
    seed.vec3(pocket_center);
    seed.vec3(canonical_pocket_normal);
    seed.string(NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID);
    let sequence = match orientations(seed.finish(), usize::from(sequence_index) + 1) {
        Ok(sequence) => sequence,
        Err(_) => {
            return Ok(Err(
                sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT,
            ));
        }
    };
    let selected = sequence.get(usize::from(sequence_index)).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 sequence selection is absent",
        )
    })?;
    if selected.orientation_index != u32::from(sequence_index) {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "independent indexed-SO3 accepted sequence index changed",
        ));
    }
    let mut source_center = Vec3::new(0.0, 0.0, 0.0);
    for coordinate in coordinates {
        source_center = source_center.plus(*coordinate);
    }
    source_center = source_center.scale(1.0 / coordinates.len() as f64);
    let translation = pocket_center.minus(selected.quaternion.rotate(source_center));
    let output = coordinates
        .iter()
        .map(|coordinate| selected.quaternion.rotate(*coordinate).plus(translation))
        .collect();
    Ok(Ok(IndependentIndexedSo3Replay {
        coordinates: output,
        quaternion: selected.quaternion,
    }))
}

fn require_preplacement_failure(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    failure_code: sys::bg_docking_fixed64_producer_failure,
) -> Result<()> {
    if row.status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
        || row.failure_code != failure_code
        || row.component_failure_code != 0
        || digest_present(&row.placement_receipt_sha256)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 pre-placement failure disagrees with independent replay",
        ));
    }
    Ok(())
}

fn require_placement_failure(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    producer_failure: sys::bg_docking_fixed64_producer_failure,
    component_failure: i32,
) -> Result<()> {
    if row.status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
        || row.failure_code != producer_failure
        || row.component_failure_code != component_failure
        || !digest_present(&row.placement_receipt_sha256)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 placement failure disagrees with independent replay",
        ));
    }
    Ok(())
}

fn single_anchor_component_failure(code: IndependentFixed64PlacementErrorCode) -> Option<i32> {
    match code {
        IndependentFixed64PlacementErrorCode::DegenerateLigandDirection => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION)
        }
        IndependentFixed64PlacementErrorCode::DegenerateReceptorDirection => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_RECEPTOR_DIRECTION)
        }
        IndependentFixed64PlacementErrorCode::DegenerateLocalSurfaceNormal => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL)
        }
        IndependentFixed64PlacementErrorCode::DegenerateAromaticPlane => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE)
        }
        IndependentFixed64PlacementErrorCode::DegeneratePrincipalAxis => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_PRINCIPAL_AXIS)
        }
        IndependentFixed64PlacementErrorCode::InternalInvariant => {
            Some(sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT)
        }
        _ => None,
    }
}

fn selected_feature_geometry_available(
    slot: &betelgeuze_docking_search::Fixed64Slot,
    inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
) -> bool {
    let Some(inventory) = inventory else {
        return false;
    };
    slot.selected_source_receipt_sha256s().len() == 2
        && slot
            .selected_source_receipt_sha256s()
            .iter()
            .all(|receipt| inventory.feature_for_allocation_receipt(*receipt).is_some())
}

#[allow(clippy::too_many_arguments)]
fn validate_independent_producer_placement(
    backend: Backend,
    allocation: &IndependentFixed64Allocation,
    feature_inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
    geometric_input: &IndependentFixed64GeometricInput,
    canonical_pocket_normal: [f64; 3],
    row: &sys::bg_docking_fixed64_producer_row_v1,
    producer_coordinates: [&[f64]; 3],
    slot_index: usize,
    ligand_atom_count: usize,
    expected_source: Option<Fixed64CoordinateSource<'_>>,
    native_replay: Option<&NativePlacementReplay>,
) -> Result<()> {
    if !matches!(
        row.placement_kind,
        sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
            | sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
    ) {
        return Ok(());
    }
    let slot = allocation.slots().get(slot_index).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 placement slot is outside independent allocation",
        )
    })?;
    if !slot.generation_eligible() {
        if native_replay.is_some() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native placement replay ran for an allocation-ineligible slot",
            ));
        }
        return require_preplacement_failure(
            row,
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE,
        );
    }
    let Some(source) = expected_source else {
        if native_replay.is_some() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native placement replay ran without a frozen source",
            ));
        }
        return require_preplacement_failure(
            row,
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE,
        );
    };
    if row.placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
        && !selected_feature_geometry_available(slot, feature_inventory)
    {
        if native_replay.is_some() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native placement replay ran without selected feature geometry",
            ));
        }
        return require_preplacement_failure(
            row,
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE,
        );
    }
    let native_replay = native_replay.ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native placement replay is absent for an executed placement",
        )
    })?;
    let source = independent_placement_source(source)?;
    let observed = coordinate_segment(producer_coordinates, slot_index, ligand_atom_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 placement coordinate segment is absent",
            )
        })?;
    if row.placement_kind == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3 {
        match independent_indexed_so3_replay(
            allocation,
            slot_index,
            &source,
            Vec3::new(
                geometric_input.pocket_center_angstrom().x,
                geometric_input.pocket_center_angstrom().y,
                geometric_input.pocket_center_angstrom().z,
            ),
            Vec3::new(
                canonical_pocket_normal[0],
                canonical_pocket_normal[1],
                canonical_pocket_normal[2],
            ),
        ) {
            Ok(Ok(placement)) => {
                let status_matches = row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
                let coordinates_match =
                    placement_coordinates_close(backend, observed, &placement.coordinates);
                let quaternion_matches =
                    placement_quaternion_close(backend, row, placement.quaternion);
                let coordinate_receipt_matches =
                    row.output_coordinate_sha256 == canonical_coordinate_sha256(observed);
                let native_replay_matches = native_replay.status
                    == sys::BG_DOCKING_FIXED64_INDEXED_SO3_PLACED
                    && native_replay.failure_code
                        == sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE
                    && native_replay.output_coordinate_sha256 == row.output_coordinate_sha256
                    && native_replay_coordinates_match(observed, native_replay)
                    && native_replay_quaternion_matches(row, native_replay);
                let placement_receipt_matches =
                    row.placement_receipt_sha256 == native_replay.placement_receipt_sha256;
                if !status_matches
                    || !coordinates_match
                    || !quaternion_matches
                    || !coordinate_receipt_matches
                    || !native_replay_matches
                    || !placement_receipt_matches
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        format!(
                            "native fixed64 indexed-SO3 placement disagrees with independent replay: status={status_matches}, coordinates={coordinates_match}, quaternion={quaternion_matches}, coordinate_receipt={coordinate_receipt_matches}, native_replay={native_replay_matches}, placement_receipt={placement_receipt_matches}"
                        ),
                    ));
                }
            }
            Ok(Err(component_failure)) => {
                if native_replay.status != sys::BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE
                    || native_replay.failure_code != component_failure
                    || !native_replay.coordinates.is_empty()
                    || native_replay.output_coordinate_sha256 != [0; 32]
                    || row.placement_receipt_sha256 != native_replay.placement_receipt_sha256
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 indexed-SO3 failure disagrees with native replay",
                    ));
                }
                require_placement_failure(
                    row,
                    sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE,
                    component_failure,
                )?;
            }
            Err(error) => return Err(error),
        }
        return Ok(());
    }
    let feature_inventory = feature_inventory.expect("feature availability was checked");
    match generate_native_fixed64_single_anchor(
        allocation,
        slot_index,
        source,
        feature_inventory,
        geometric_input,
    ) {
        Ok(placement) => {
            let status_matches = row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
            let coordinates_match = placement_coordinates_close(
                backend,
                observed,
                placement.output_coordinates_angstrom(),
            );
            let quaternion_matches =
                placement_quaternion_close(backend, row, placement.quaternion());
            let coordinate_receipt_matches =
                row.output_coordinate_sha256 == canonical_coordinate_sha256(observed);
            let native_replay_matches = native_replay.status
                == sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED
                && native_replay.failure_code == sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONE
                && native_replay.output_coordinate_sha256 == row.output_coordinate_sha256
                && native_replay_coordinates_match(observed, native_replay)
                && native_replay_quaternion_matches(row, native_replay);
            let placement_receipt_matches =
                row.placement_receipt_sha256 == native_replay.placement_receipt_sha256;
            if !status_matches
                || !coordinates_match
                || !quaternion_matches
                || !coordinate_receipt_matches
                || !native_replay_matches
                || !placement_receipt_matches
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    format!(
                        "native fixed64 single-anchor placement disagrees with independent replay: status={status_matches}, coordinates={coordinates_match}, quaternion={quaternion_matches}, coordinate_receipt={coordinate_receipt_matches}, native_replay={native_replay_matches}, placement_receipt={placement_receipt_matches}"
                    ),
                ));
            }
        }
        Err(error) => {
            let component_failure =
                single_anchor_component_failure(error.code()).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!(
                            "independent single-anchor replay produced an impossible error: {error}"
                        ),
                    )
                })?;
            if native_replay.status != sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE
                || native_replay.failure_code != component_failure
                || !native_replay.coordinates.is_empty()
                || native_replay.output_coordinate_sha256 != [0; 32]
                || row.placement_receipt_sha256 != native_replay.placement_receipt_sha256
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 single-anchor failure disagrees with native replay",
                ));
            }
            require_placement_failure(
                row,
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE,
                component_failure,
            )?;
        }
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn validate_native_outputs(
    backend: Backend,
    expected_receipt_graph: &ExpectedPipelineReceiptGraph,
    expected_allocation: &IndependentFixed64Allocation,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    coordinate_count: u64,
    producer: &sys::bg_docking_fixed64_producer_output_v1,
    rigid: &sys::bg_docking_rigid_refinement_output_v1,
    torsion: &sys::bg_docking_torsion_v7_output_v1,
    scorer: &sys::bg_docking_scorer_v1_output_v1,
    validity: &sys::bg_docking_pose_validity_output_v1,
    ranking: &sys::bg_docking_stable_top_k_output_v1,
    cluster: &sys::bg_docking_rmsd_cluster_output_v1,
    refinement: &sys::bg_docking_fixed64_refinement_output_v1,
    pipeline: &sys::bg_docking_fixed64_pipeline_output_v1,
    producer_rows: &[sys::bg_docking_fixed64_producer_row_v1],
    expected_sources: &[Option<Fixed64CoordinateSource<'_>>],
    expected_feature_geometry_inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
    native_placement_replays: &[Option<NativePlacementReplay>],
    canonical_pocket_normal: [f64; 3],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    torsion_moves: &[sys::bg_docking_torsion_v7_move_v1],
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    cluster_rows: &[sys::bg_docking_rmsd_cluster_row_v1],
    refinement_rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    pipeline_rows: &[sys::bg_docking_fixed64_pipeline_row_v1],
    primary_indices: &[u32],
    valid_indices: &[u32],
    representative_indices: &[u32],
    top_k_indices: &[u32],
    requested_modes: &[sys::bg_docking_rigid_refinement_candidate_mode],
    rigid_max_steps: &[u64],
    producer_coordinates: [&[f64]; 3],
    rigid_coordinates: &[Vec<f64>; 12],
    torsion_coordinates: &[Vec<f64>; 8],
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
    rmsd_threshold_angstrom: f64,
    ligand_heavy_atom_count: u64,
    geometric_hard_rejection_minimum_vdw_ratio: f64,
    geometric_input: &IndependentFixed64GeometricInput,
    rigid_v2_config: IndependentRigidV2Config,
    rigid_v3_config: IndependentRigidV3Config,
    rigid_clearance_config: IndependentRigidV3Config,
    maximum_torsion_steps: u64,
    proposal_is_torsion_eligible: &[u8],
    torsion_max_steps: &[u64],
    baseline_torsion_angles_radians: &[f64],
    rotatable_child_atom_indices: &[u64],
    validity_exclusion_count: u64,
    validity_chirality_count: u64,
    validity_contact_cell_size_angstrom: f64,
    validity_receptor_cells: &HashMap<(i64, i64, i64), u64>,
    independent_scorer_context: &IndependentScorerContext,
    independent_validity_context: &IndependentValidityContext,
) -> Result<()> {
    let candidate_count = u64::from(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT);
    let move_count = candidate_count * u64::from(sys::BG_DOCKING_TORSION_V7_MAX_MOVES);
    let top_k_limit = u64::from(sys::BG_DOCKING_STABLE_TOP_K_LIMIT);
    for (observed, expected, label) in [
        (
            producer.row_capacity,
            candidate_count,
            "producer row capacity",
        ),
        (
            producer.coordinate_capacity,
            coordinate_count,
            "producer coordinate capacity",
        ),
        (rigid.row_capacity, candidate_count, "rigid row capacity"),
        (
            rigid.coordinate_capacity,
            coordinate_count,
            "rigid coordinate capacity",
        ),
        (
            torsion.row_capacity,
            candidate_count,
            "torsion row capacity",
        ),
        (torsion.move_capacity, move_count, "torsion move capacity"),
        (
            torsion.coordinate_capacity,
            coordinate_count,
            "torsion coordinate capacity",
        ),
        (scorer.row_capacity, candidate_count, "scorer row capacity"),
        (
            validity.row_capacity,
            candidate_count,
            "validity row capacity",
        ),
        (
            ranking.row_capacity,
            candidate_count,
            "ranking row capacity",
        ),
        (
            ranking.primary_index_capacity,
            candidate_count,
            "primary rank capacity",
        ),
        (
            ranking.valid_index_capacity,
            candidate_count,
            "valid rank capacity",
        ),
        (
            cluster.row_capacity,
            candidate_count,
            "cluster row capacity",
        ),
        (
            cluster.representative_index_capacity,
            candidate_count,
            "cluster representative capacity",
        ),
        (
            cluster.top_k_index_capacity,
            top_k_limit,
            "cluster Top-K capacity",
        ),
        (
            refinement.row_capacity,
            candidate_count,
            "refinement row capacity",
        ),
        (
            refinement.coordinate_capacity,
            coordinate_count,
            "refinement coordinate capacity",
        ),
        (
            refinement.quaternion_capacity,
            candidate_count,
            "refinement quaternion capacity",
        ),
        (
            pipeline.row_capacity,
            candidate_count,
            "pipeline row capacity",
        ),
    ] {
        if observed != expected {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} is {observed}, expected {expected}"),
            ));
        }
    }
    for (observed, expected, label) in [
        (producer.row_count, candidate_count, "producer row count"),
        (
            producer.coordinate_count,
            coordinate_count,
            "producer coordinate count",
        ),
        (rigid.row_count, candidate_count, "rigid row count"),
        (
            rigid.coordinate_count,
            coordinate_count,
            "rigid coordinate count",
        ),
        (torsion.row_count, candidate_count, "torsion row count"),
        (torsion.move_count, move_count, "torsion move count"),
        (
            torsion.coordinate_count,
            coordinate_count,
            "torsion coordinate count",
        ),
        (scorer.row_count, candidate_count, "scorer row count"),
        (validity.row_count, candidate_count, "validity row count"),
        (ranking.row_count, candidate_count, "ranking row count"),
        (cluster.row_count, candidate_count, "cluster row count"),
        (
            refinement.row_count,
            candidate_count,
            "refinement row count",
        ),
        (
            refinement.coordinate_count,
            coordinate_count,
            "refinement coordinate count",
        ),
        (
            refinement.quaternion_count,
            candidate_count,
            "refinement quaternion count",
        ),
        (pipeline.row_count, candidate_count, "pipeline row count"),
    ] {
        if observed != expected {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} is {observed}, expected {expected}"),
            ));
        }
    }
    for (count, capacity, label) in [
        (
            ranking.primary_index_count,
            ranking.primary_index_capacity,
            "primary rank count",
        ),
        (
            ranking.valid_index_count,
            ranking.valid_index_capacity,
            "valid rank count",
        ),
        (
            cluster.representative_index_count,
            cluster.representative_index_capacity,
            "cluster representative count",
        ),
        (
            cluster.top_k_index_count,
            cluster.top_k_index_capacity,
            "cluster Top-K count",
        ),
    ] {
        if count > capacity {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} exceeds its capacity"),
            ));
        }
    }
    let generated_row_count = producer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED)
        .count() as u64;
    let typed_failure_row_count = producer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE)
        .count() as u64;
    let initial_admitted_row_count = producer_rows
        .iter()
        .filter(|row| {
            row.geometric_admission.decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
        })
        .count() as u64;
    let refined_row_count = refinement_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY)
        .count() as u64;
    let scored_row_count = scorer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED)
        .count() as u64;
    let valid_row_count = validity_rows
        .iter()
        .filter(|row| {
            row.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
                && row.passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
                && row.blocker_mask == 0
        })
        .count() as u64;
    for (valid, label) in [
        (
            producer.source_bundle_receipt_sha256
                == expected_receipt_graph.source_bundle_receipt_sha256,
            "producer source-bundle receipt",
        ),
        (
            pipeline.source_bundle_receipt_sha256
                == expected_receipt_graph.source_bundle_receipt_sha256,
            "pipeline source-bundle receipt",
        ),
        (
            producer.generated_count == generated_row_count,
            "producer generated count",
        ),
        (
            producer.typed_failure_count == typed_failure_row_count,
            "producer typed-failure count",
        ),
        (
            pipeline.initial_admitted_count == initial_admitted_row_count,
            "pipeline initial-admitted count",
        ),
        (
            pipeline.refined_count == refined_row_count,
            "pipeline refined count",
        ),
        (
            pipeline.scored_count == scored_row_count,
            "pipeline scored count",
        ),
        (
            pipeline.valid_count == valid_row_count,
            "pipeline valid count",
        ),
    ] {
        if !valid {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} was not independently rederived"),
            ));
        }
    }
    if requested_modes.len() != candidate_count as usize
        || rigid_max_steps.len() != candidate_count as usize
        || pipeline.backend != backend.as_raw()
        || producer.backend != backend.as_raw()
        || [
            producer.unit_system,
            rigid.unit_system,
            torsion.unit_system,
            scorer.unit_system,
            validity.unit_system,
            ranking.unit_system,
            cluster.unit_system,
            refinement.unit_system,
            pipeline.unit_system,
        ]
        .iter()
        .any(|unit| *unit != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL)
        || producer
            .generated_count
            .checked_add(producer.typed_failure_count)
            != Some(candidate_count)
        || pipeline.generated_count != producer.generated_count
        || pipeline.allocation_receipt_sha256 != producer.allocation_receipt_sha256
        || pipeline.source_bundle_receipt_sha256 != producer.source_bundle_receipt_sha256
        || pipeline.producer_batch_receipt_sha256 != producer.producer_batch_receipt_sha256
        || producer.allocation_inventory_sha256
            != expected_receipt_graph.allocation_inventory_sha256
        || producer.allocation_receipt_sha256 != expected_receipt_graph.allocation_receipt_sha256
        || producer.source_bundle_receipt_sha256
            != expected_receipt_graph.source_bundle_receipt_sha256
        || pipeline.allocation_receipt_sha256 != expected_receipt_graph.allocation_receipt_sha256
        || pipeline.source_bundle_receipt_sha256
            != expected_receipt_graph.source_bundle_receipt_sha256
        || pipeline.admission_context_receipt_sha256
            != expected_receipt_graph.admission_context_receipt_sha256
        || pipeline.refinement_context_receipt_sha256
            != expected_receipt_graph.refinement_context_receipt_sha256
        || pipeline.scorer_context_receipt_sha256
            != expected_receipt_graph.scorer_context_receipt_sha256
        || pipeline.validity_context_receipt_sha256
            != expected_receipt_graph.validity_context_receipt_sha256
        || pipeline.component_binding_receipt_sha256
            != expected_receipt_graph.component_binding_receipt_sha256
        || pipeline.refinement_policy_receipt_sha256
            != expected_receipt_graph.refinement_policy_receipt_sha256
        || producer.generated_count != generated_row_count
        || producer.typed_failure_count != typed_failure_row_count
        || pipeline.generated_count != generated_row_count
        || pipeline.initial_admitted_count != initial_admitted_row_count
        || pipeline.refined_count != refined_row_count
        || pipeline.scored_count != scored_row_count
        || pipeline.valid_count != valid_row_count
        || ranking.primary_index_count != pipeline.scored_count
        || ranking.valid_index_count != pipeline.valid_count
        || cluster.representative_index_count != pipeline.cluster_count
        || cluster.top_k_index_count != pipeline.cluster_count.min(top_k_limit)
        || pipeline.initial_admitted_count > pipeline.generated_count
        || pipeline.refined_count > pipeline.initial_admitted_count
        || pipeline.scored_count > pipeline.refined_count
        || pipeline.valid_count > pipeline.scored_count
        || pipeline.cluster_count > pipeline.valid_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 batch counts, backend, or denominator are inconsistent",
        ));
    }
    let authority = authority_disposition(pipeline, producer)?;
    if authority
        != (Fixed64AuthorityDisposition {
            result_dependent_input_consumed: false,
            fallback_allowed: false,
            multi_anchor_consumed: false,
            denominator_preserved: true,
            molecular_execution_authorized: false,
            reservation_authorized: false,
            benchmark_execution_authorized: false,
            existing_rank_auto_change_authorized: false,
            customer_pose_emission_authorized: false,
            production_claim_authorized: false,
            scientific_claim_authorized: false,
        })
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 complete pipeline returned non-frozen authority",
        ));
    }
    require_authority_false(&[
        (
            producer.result_dependent_input_consumed,
            "producer result-dependent input",
        ),
        (producer.fallback_allowed, "producer fallback"),
        (producer.multi_anchor_consumed, "producer multi-anchor"),
        (
            producer.molecular_execution_authorized,
            "producer molecular execution",
        ),
        (producer.reservation_authorized, "producer reservation"),
        (
            producer.benchmark_execution_authorized,
            "producer benchmark execution",
        ),
        (
            producer.existing_rank_auto_change_authorized,
            "producer rank mutation",
        ),
        (
            producer.customer_pose_emission_authorized,
            "producer customer pose emission",
        ),
        (
            producer.production_claim_authorized,
            "producer production claim",
        ),
        (
            producer.scientific_claim_authorized,
            "producer scientific claim",
        ),
        (
            rigid.molecular_execution_authorized,
            "rigid molecular execution",
        ),
        (
            rigid.existing_rank_auto_change_authorized,
            "rigid rank mutation",
        ),
        (
            rigid.customer_pose_emission_authorized,
            "rigid pose emission",
        ),
        (rigid.production_claim_authorized, "rigid production claim"),
        (
            torsion.molecular_execution_authorized,
            "torsion molecular execution",
        ),
        (
            torsion.existing_rank_auto_change_authorized,
            "torsion rank mutation",
        ),
        (
            torsion.customer_pose_emission_authorized,
            "torsion pose emission",
        ),
        (
            torsion.production_claim_authorized,
            "torsion production claim",
        ),
        (
            refinement.molecular_execution_authorized,
            "refinement molecular execution",
        ),
        (refinement.reservation_authorized, "refinement reservation"),
        (
            refinement.benchmark_execution_authorized,
            "refinement benchmark execution",
        ),
        (
            refinement.existing_rank_auto_change_authorized,
            "refinement rank mutation",
        ),
        (
            refinement.customer_pose_emission_authorized,
            "refinement pose emission",
        ),
        (
            refinement.production_claim_authorized,
            "refinement production claim",
        ),
        (
            ranking.existing_rank_auto_change_authorized,
            "ranking mutation",
        ),
        (
            ranking.customer_pose_emission_authorized,
            "ranking pose emission",
        ),
        (
            ranking.production_claim_authorized,
            "ranking production claim",
        ),
        (
            cluster.existing_rank_auto_change_authorized,
            "cluster rank mutation",
        ),
        (
            cluster.customer_pose_emission_authorized,
            "cluster pose emission",
        ),
        (
            cluster.production_claim_authorized,
            "cluster production claim",
        ),
    ])?;
    if !bool_from_abi(producer.denominator_preserved, "producer denominator")? {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 producer did not preserve the denominator",
        ));
    }
    let expected_pair_count = ligand_atom_count
        .checked_mul(receptor_atom_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 geometric exact-pair denominator overflowed",
            )
        })?;
    for (slot, row) in producer_rows.iter().enumerate() {
        let expected_offset = u64::try_from(slot)
            .ok()
            .and_then(|slot| slot.checked_mul(ligand_atom_count))
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer coordinate offset overflowed",
                )
            })?;
        if row.slot_index as usize != slot
            || row.backend != backend.as_raw()
            || row.ligand_atom_count != ligand_atom_count
            || row.coordinate_offset != expected_offset
            || row.allocation_slot_receipt_sha256
                != expected_allocation.slots()[slot].receipt_sha256()
            || !bool_from_abi(row.denominator_preserved, "producer row denominator")?
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer row identity or denominator is invalid",
            ));
        }
        require_authority_false(&[
            (
                row.result_dependent_input_consumed,
                "producer row result input",
            ),
            (row.fallback_allowed, "producer row fallback"),
            (row.multi_anchor_consumed, "producer row multi-anchor"),
            (
                row.molecular_execution_authorized,
                "producer row molecular execution",
            ),
            (row.reservation_authorized, "producer row reservation"),
            (
                row.benchmark_execution_authorized,
                "producer row benchmark execution",
            ),
            (
                row.existing_rank_auto_change_authorized,
                "producer row rank mutation",
            ),
            (
                row.customer_pose_emission_authorized,
                "producer row pose emission",
            ),
            (
                row.production_claim_authorized,
                "producer row production claim",
            ),
            (
                row.scientific_claim_authorized,
                "producer row scientific claim",
            ),
        ])?;
        if !digest_present(&row.row_receipt_sha256) {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer row receipt is absent",
            ));
        }
        validate_geometric_admission_row_semantics(
            &row.geometric_admission,
            row.status,
            receptor_atom_count,
            ligand_atom_count,
            ligand_heavy_atom_count,
            expected_pair_count,
            geometric_hard_rejection_minimum_vdw_ratio,
            backend,
            geometric_input,
            producer_coordinates,
            slot,
        )?;
        let expected_source = expected_sources.get(slot).copied().ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 expected-source inventory is incomplete",
            )
        })?;
        validate_producer_row_semantics(
            row,
            producer_coordinates,
            slot,
            ligand_atom_count,
            expected_source,
        )?;
        validate_independent_producer_placement(
            backend,
            expected_allocation,
            expected_feature_geometry_inventory,
            geometric_input,
            canonical_pocket_normal,
            row,
            producer_coordinates,
            slot,
            usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer ligand denominator does not fit usize",
                )
            })?,
            expected_source,
            native_placement_replays.get(slot).and_then(Option::as_ref),
        )?;
        if row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED {
            let source = expected_source.ok_or_else(|| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 generated producer row lacks an independently selected source",
                )
            })?;
            let proposal_matches = if row.placement_kind
                == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
            {
                row.placement_receipt_sha256
                    == canonical_passthrough_placement_receipt(expected_receipt_graph, row, source)
                    && row.output_proposal_sha256 == source.evidence.proposal_sha256
            } else {
                row.output_proposal_sha256
                    == canonical_generated_proposal_receipt(expected_receipt_graph, row, source)
            };
            if !proposal_matches {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer proposal lineage was not independently rederived",
                ));
            }
        }
        let expected_geometric_row_receipt = canonical_geometric_row_receipt(
            expected_receipt_graph,
            row.status,
            producer_coordinates,
            slot,
            &row.geometric_admission,
        )?;
        let expected_producer_row_receipt =
            canonical_producer_row_receipt(expected_receipt_graph, row);
        if row.geometric_admission.row_receipt_sha256 != expected_geometric_row_receipt
            || row.row_receipt_sha256 != expected_producer_row_receipt
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer or geometric row receipt was not independently rederived",
            ));
        }
    }
    let expected_geometric_batch_receipt =
        canonical_geometric_batch_receipt(expected_receipt_graph, producer_rows);
    let expected_producer_batch_receipt = canonical_producer_batch_receipt(
        expected_receipt_graph,
        expected_geometric_batch_receipt,
        producer_rows,
        producer.generated_count,
    );
    if producer.geometric_admission_batch_receipt_sha256 != expected_geometric_batch_receipt
        || producer.producer_batch_receipt_sha256 != expected_producer_batch_receipt
        || pipeline.producer_batch_receipt_sha256 != expected_producer_batch_receipt
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 producer batch receipt graph was not independently rederived",
        ));
    }
    for (slot, row) in rigid_rows.iter().enumerate() {
        let producer_row = &producer_rows[slot];
        let admitted = producer_row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
            && producer_row.geometric_admission.decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && bool_from_abi(
                producer_row.geometric_admission.rank_eligible,
                "geometric rank eligibility",
            )?;
        let effective_mode = if admitted {
            requested_modes[slot]
        } else {
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
        };
        validate_rigid_row_semantics(
            row,
            effective_mode,
            rigid_max_steps[slot],
            rigid_coordinates,
            slot,
            ligand_atom_count,
        )?;
        validate_independent_rigid_replay(
            backend,
            row,
            effective_mode,
            rigid_max_steps[slot],
            producer_coordinates,
            rigid_coordinates,
            slot,
            ligand_atom_count,
            geometric_input,
            rigid_v2_config,
            rigid_v3_config,
            rigid_clearance_config,
        )?;
    }
    for (label, invalid_order) in [
        (
            "torsion",
            torsion_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "scorer",
            scorer_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "validity",
            validity_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "ranking",
            ranking_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "cluster",
            cluster_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "refinement",
            refinement_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
    ] {
        if invalid_order {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} row order is invalid"),
            ));
        }
    }
    if torsion_moves.iter().enumerate().any(|(index, row)| {
        row.slot_index as usize != index / sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize
            || row.move_index as usize != index % sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize
    }) {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion move order is invalid",
        ));
    }
    validate_torsion_evidence(
        torsion_rows,
        torsion_moves,
        rigid_rows,
        proposal_is_torsion_eligible,
        torsion_max_steps,
        maximum_torsion_steps,
        rotatable_child_atom_indices,
        torsion_coordinates,
        rigid_coordinates,
        baseline_torsion_angles_radians,
        ligand_atom_count,
    )?;
    validate_refinement_evidence(
        refinement_rows,
        producer_rows,
        rigid_rows,
        torsion_rows,
        requested_modes,
        [
            rigid_coordinates[0].as_slice(),
            rigid_coordinates[1].as_slice(),
            rigid_coordinates[2].as_slice(),
        ],
        [
            torsion_coordinates[4].as_slice(),
            torsion_coordinates[5].as_slice(),
            torsion_coordinates[6].as_slice(),
        ],
        final_coordinates,
        final_quaternions,
        ligand_atom_count,
        backend,
    )?;
    validate_scorer_and_validity_evidence(
        scorer_rows,
        validity_rows,
        ranking_rows,
        refinement_rows,
        ligand_atom_count,
        receptor_atom_count,
        validity_exclusion_count,
        validity_chirality_count,
        validity_contact_cell_size_angstrom,
        validity_receptor_cells,
        final_coordinates,
        final_quaternions,
        independent_scorer_context,
        independent_validity_context,
        backend,
    )?;
    validate_index_evidence(
        ranking,
        cluster,
        scorer_rows,
        validity_rows,
        ranking_rows,
        cluster_rows,
        primary_indices,
        valid_indices,
        representative_indices,
        top_k_indices,
        rmsd_threshold_angstrom,
        final_coordinates,
        ligand_atom_count,
    )?;
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence ligand denominator does not fit usize",
        )
    })?;
    let mut refinement_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_evidence/1.0.0");
    let mut scorer_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scorer_evidence/1.0.0");
    let mut validity_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_validity_evidence/1.0.0");
    let mut ranking_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_ranking_evidence/1.0.0");
    let mut cluster_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_cluster_evidence/1.0.0");
    refinement_batch.digest(expected_receipt_graph.refinement_context_receipt_sha256);
    scorer_batch.digest(expected_receipt_graph.scorer_context_receipt_sha256);
    validity_batch.digest(expected_receipt_graph.validity_context_receipt_sha256);
    ranking_batch.digest(expected_receipt_graph.component_binding_receipt_sha256);
    cluster_batch.digest(expected_receipt_graph.component_binding_receipt_sha256);
    for (slot, row) in pipeline_rows.iter().enumerate() {
        let producer_row = &producer_rows[slot];
        let rigid_row = &rigid_rows[slot];
        let refinement_row = &refinement_rows[slot];
        let scorer_row = &scorer_rows[slot];
        let validity_row = &validity_rows[slot];
        let ranking_row = &ranking_rows[slot];
        let cluster_row = &cluster_rows[slot];
        let admitted = producer_row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
            && producer_row.geometric_admission.decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && bool_from_abi(
                producer_row.geometric_admission.rank_eligible,
                "geometric rank eligibility",
            )?;
        let expected_effective_mode = if admitted {
            requested_modes[slot]
        } else {
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
        };
        let ranking_has_coordinate = bool_from_abi(ranking_row.rank_eligible, "rank eligibility")?;
        let cluster_has_coordinate =
            bool_from_abi(cluster_row.cluster_eligible, "cluster eligibility")?;
        let refinement_ready =
            refinement_row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
        let scored = scorer_row.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED;
        let validity_evaluated = validity_row.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
        let valid_rank_eligible =
            bool_from_abi(ranking_row.valid_rank_eligible, "valid-rank eligibility")?;
        let expected_refinement_evidence = canonical_refinement_evidence(
            slot,
            ligand_count,
            rigid_row,
            &torsion_rows[slot],
            torsion_moves,
            refinement_row,
            rigid_coordinates,
            torsion_coordinates,
            final_coordinates,
            final_quaternions,
        )?;
        let expected_scorer_evidence = canonical_scorer_evidence(scorer_row);
        let expected_validity_evidence = canonical_validity_evidence(validity_row);
        let expected_ranking_evidence = canonical_ranking_evidence(ranking_row);
        let expected_cluster_evidence = canonical_cluster_evidence(cluster_row);
        refinement_batch.digest(expected_refinement_evidence);
        scorer_batch.digest(expected_scorer_evidence);
        validity_batch.digest(expected_validity_evidence);
        ranking_batch.digest(expected_ranking_evidence);
        cluster_batch.digest(expected_cluster_evidence);
        validate_pipeline_receipt_bindings(
            row,
            pipeline.component_binding_receipt_sha256,
            pipeline.refinement_policy_receipt_sha256,
            expected_refinement_evidence,
            expected_scorer_evidence,
            expected_validity_evidence,
            expected_ranking_evidence,
            expected_cluster_evidence,
        )?;
        if row.slot_index as usize != slot
            || row.reserved.iter().any(|value| *value != 0)
            || row.producer_status != producer_row.status
            || row.producer_failure_code != producer_row.failure_code
            || row.initial_admission_decision != producer_row.geometric_admission.decision
            || row.requested_refinement_mode != requested_modes[slot]
            || row.effective_refinement_mode != expected_effective_mode
            || rigid_row.candidate_mode != expected_effective_mode
            || row.refinement_status != refinement_row.status
            || row.refinement_failure_stage != refinement_row.failure_stage
            || row.scorer_status != scorer_row.status
            || row.scorer_failure_code != scorer_row.failure_code
            || row.validity_status != validity_row.status
            || row.validity_failure_code != validity_row.failure_code
            || row.stable_rank != ranking_row.stable_rank
            || row.stable_valid_rank != ranking_row.stable_valid_rank
            || row.cluster_status != cluster_row.status
            || row.cluster_id != cluster_row.cluster_id
            || row.cluster_rank != cluster_row.cluster_rank
            || row.top_k_rank != cluster_row.top_k_rank
            || row.producer_row_receipt_sha256 != producer_row.row_receipt_sha256
            || row.final_coordinate_sha256 != refinement_row.coordinate_sha256
            || (refinement_ready && !admitted)
            || (scored && !refinement_ready)
            || (validity_evaluated && !scored)
            || (ranking_has_coordinate && !scored)
            || (valid_rank_eligible
                && (!validity_evaluated
                    || validity_row.passed_check_mask != sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
                    || validity_row.blocker_mask != 0))
            || (cluster_has_coordinate && !valid_rank_eligible)
            || (ranking_has_coordinate
                && ranking_row.coordinate_sha256 != refinement_row.coordinate_sha256)
            || (cluster_has_coordinate
                && cluster_row.coordinate_sha256 != ranking_row.coordinate_sha256)
            || [
                row.producer_row_receipt_sha256,
                row.refinement_evidence_sha256,
                row.scorer_evidence_sha256,
                row.validity_evidence_sha256,
                row.ranking_evidence_sha256,
                row.cluster_evidence_sha256,
                row.row_receipt_sha256,
            ]
            .iter()
            .any(|digest| !digest_present(digest))
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline row identity or evidence receipt is invalid",
            ));
        }
    }
    let primary = counted_index_prefix(
        primary_indices,
        ranking.primary_index_count,
        "primary rank batch receipt",
    )?;
    let valid = counted_index_prefix(
        valid_indices,
        ranking.valid_index_count,
        "valid rank batch receipt",
    )?;
    ranking_batch.u64(ranking.primary_index_count);
    for slot in primary {
        ranking_batch.u32(*slot);
    }
    ranking_batch.u64(ranking.valid_index_count);
    for slot in valid {
        ranking_batch.u32(*slot);
    }
    ranking_batch.byte(ranking.existing_rank_auto_change_authorized);
    ranking_batch.byte(ranking.customer_pose_emission_authorized);
    ranking_batch.byte(ranking.production_claim_authorized);
    let representatives = counted_index_prefix(
        representative_indices,
        cluster.representative_index_count,
        "cluster representative batch receipt",
    )?;
    let top_k = counted_index_prefix(
        top_k_indices,
        cluster.top_k_index_count,
        "cluster Top-K batch receipt",
    )?;
    cluster_batch.u64(cluster.representative_index_count);
    for slot in representatives {
        cluster_batch.u32(*slot);
    }
    cluster_batch.u64(cluster.top_k_index_count);
    for slot in top_k {
        cluster_batch.u32(*slot);
    }
    cluster_batch.byte(cluster.existing_rank_auto_change_authorized);
    cluster_batch.byte(cluster.customer_pose_emission_authorized);
    cluster_batch.byte(cluster.production_claim_authorized);
    let refinement_batch_receipt_sha256 = refinement_batch.finish();
    let scorer_batch_receipt_sha256 = scorer_batch.finish();
    let validity_batch_receipt_sha256 = validity_batch.finish();
    let ranking_batch_receipt_sha256 = ranking_batch.finish();
    let cluster_batch_receipt_sha256 = cluster_batch.finish();
    let mut pipeline_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_complete_pipeline_batch/1.0.0");
    pipeline_batch.string("betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0");
    pipeline_batch.i32(backend.as_raw());
    pipeline_batch.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    pipeline_batch.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    pipeline_batch.digest(expected_receipt_graph.allocation_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.source_bundle_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.admission_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.refinement_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.scorer_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.validity_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.component_binding_receipt_sha256);
    pipeline_batch.digest(expected_producer_batch_receipt);
    pipeline_batch.digest(expected_receipt_graph.refinement_policy_receipt_sha256);
    pipeline_batch.digest(refinement_batch_receipt_sha256);
    pipeline_batch.digest(scorer_batch_receipt_sha256);
    pipeline_batch.digest(validity_batch_receipt_sha256);
    pipeline_batch.digest(ranking_batch_receipt_sha256);
    pipeline_batch.digest(cluster_batch_receipt_sha256);
    pipeline_batch.u64(generated_row_count);
    pipeline_batch.u64(initial_admitted_row_count);
    pipeline_batch.u64(refined_row_count);
    pipeline_batch.u64(scored_row_count);
    pipeline_batch.u64(valid_row_count);
    pipeline_batch.u64(cluster.representative_index_count);
    for row in pipeline_rows {
        pipeline_batch.digest(row.row_receipt_sha256);
    }
    for value in [0_u8, 0, 1, 0, 0, 0, 0, 0, 0, 0] {
        pipeline_batch.byte(value);
    }
    let pipeline_batch_receipt_sha256 = pipeline_batch.finish();
    if pipeline.refinement_batch_receipt_sha256 != refinement_batch_receipt_sha256
        || pipeline.scorer_batch_receipt_sha256 != scorer_batch_receipt_sha256
        || pipeline.validity_batch_receipt_sha256 != validity_batch_receipt_sha256
        || pipeline.ranking_batch_receipt_sha256 != ranking_batch_receipt_sha256
        || pipeline.cluster_batch_receipt_sha256 != cluster_batch_receipt_sha256
        || pipeline.pipeline_batch_receipt_sha256 != pipeline_batch_receipt_sha256
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 complete batch receipt graph was not independently rederived",
        ));
    }
    Ok(())
}

fn scorer_failure_rank_evidence_is_zero(row: &sys::bg_docking_scorer_v1_row_v1) -> bool {
    row.weighted_terms.iter().all(|value| *value == 0.0)
        && row.total_score == 0.0
        && row.hbond_count == 0
        && row.hydrophobic_contact_count == 0
        && row.buried_polar_count == 0
}

fn scorer_failure_pair_evidence_is_valid(row: &sys::bg_docking_scorer_v1_row_v1) -> bool {
    match row.failure_code {
        sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
        | sys::BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES => {
            row.receptor_candidate_pair_count == 0 && row.ligand_pair_count == 0
        }
        sys::BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY => {
            row.receptor_candidate_pair_count > 0 && row.ligand_pair_count == 0
        }
        sys::BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY => row.ligand_pair_count > 0,
        sys::BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR
        | sys::BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE => true,
        _ => false,
    }
}

fn independent_scorer_failure_code(code: IndependentScorerFailureCode) -> i32 {
    match code {
        IndependentScorerFailureCode::ProposalGenerationFailure
        | IndependentScorerFailureCode::SeverePenetrationRejected => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
        }
        IndependentScorerFailureCode::InvalidCandidateCoordinates => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES
        }
        IndependentScorerFailureCode::ReceptorCandidatePairCapacityExceeded => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY
        }
        IndependentScorerFailureCode::LigandPairCapacityExceeded => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY
        }
        IndependentScorerFailureCode::DegenerateRotorGeometry => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR
        }
        IndependentScorerFailureCode::NonfiniteScore => {
            sys::BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE
        }
    }
}

fn validity_measurements_are_finite(row: &sys::bg_docking_pose_validity_row_v1) -> bool {
    [
        row.rotation_orthogonality_max_error,
        row.rotation_determinant,
        row.max_bond_length_delta_angstrom,
        row.minimum_ligand_nonbonded_distance_angstrom,
        row.minimum_receptor_ligand_distance_angstrom,
        row.minimum_declared_chiral_volume,
        row.maximum_pocket_center_distance_angstrom,
        row.element_vdw_ligand_minimum_distance_angstrom,
        row.element_vdw_ligand_minimum_ratio,
        row.element_vdw_receptor_minimum_distance_angstrom,
        row.element_vdw_receptor_minimum_ratio,
    ]
    .iter()
    .all(|value| value.is_finite())
}

fn validity_failure_evidence_is_zero(row: &sys::bg_docking_pose_validity_row_v1) -> bool {
    row.passed_check_mask == 0
        && row.blocker_mask == 0
        && row.atom_count == 0
        && row.rotation_orthogonality_max_error == 0.0
        && row.rotation_determinant == 0.0
        && row.max_bond_length_delta_angstrom == 0.0
        && row.minimum_ligand_nonbonded_distance_angstrom == 0.0
        && row.evaluated_ligand_nonbonded_pair_count == 0
        && row.excluded_ligand_pair_count == 0
        && row.minimum_receptor_ligand_distance_angstrom == 0.0
        && row.evaluated_receptor_ligand_pair_count == 0
        && row.minimum_declared_chiral_volume == 0.0
        && row.declared_chirality_center_count == 0
        && row.maximum_pocket_center_distance_angstrom == 0.0
        && row.element_vdw_ligand_pair_count == 0
        && row.element_vdw_ligand_severe_overlap_count == 0
        && row.element_vdw_ligand_minimum_distance_angstrom == 0.0
        && row.element_vdw_ligand_minimum_ratio == 0.0
        && row.element_vdw_receptor_candidate_pair_count == 0
        && row.element_vdw_receptor_full_cartesian_pair_count == 0
        && row.element_vdw_receptor_cell_count == 0
        && row.element_vdw_receptor_severe_overlap_count == 0
        && row.element_vdw_receptor_minimum_distance_angstrom == 0.0
        && row.element_vdw_receptor_minimum_ratio == 0.0
}

fn independent_validity_check_mask(checks: IndependentValidityChecks) -> u32 {
    let mut mask = 0_u32;
    for (passed, bit) in [
        (
            checks.proper_rotation(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION,
        ),
        (
            checks.bond_lengths_preserved(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS,
        ),
        (
            checks.ligand_self_clash_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_LIGAND_SELF_CLASH,
        ),
        (
            checks.receptor_ligand_clash_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH,
        ),
        (
            checks.declared_chirality_preserved(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_CHIRALITY,
        ),
        (
            checks.inside_declared_pocket(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET,
        ),
        (
            checks.element_vdw_ligand_overlap_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW,
        ),
        (
            checks.element_vdw_receptor_overlap_free(),
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW,
        ),
    ] {
        if passed {
            mask |= bit;
        }
    }
    mask
}

fn independent_validity_failure_code(
    value: IndependentValidityFailureCode,
) -> sys::bg_docking_pose_validity_failure {
    match value {
        IndependentValidityFailureCode::UpstreamScorerFailure => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER
        }
        IndependentValidityFailureCode::InvalidCandidateCoordinates => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES
        }
        IndependentValidityFailureCode::LigandPairCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY
        }
        IndependentValidityFailureCode::ReceptorCrossCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY
        }
        IndependentValidityFailureCode::ElementLigandPairCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY
        }
        IndependentValidityFailureCode::ElementReceptorCandidateCapacityExceeded => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY
        }
        IndependentValidityFailureCode::NonfiniteDerivedMeasurement => {
            sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT
        }
    }
}

fn independent_validity_measurements_match(
    backend: Backend,
    expected: IndependentValidityMeasurements,
    observed: &sys::bg_docking_pose_validity_row_v1,
) -> bool {
    observed.atom_count == expected.atom_count() as u64
        && observed.evaluated_ligand_nonbonded_pair_count
            == expected.evaluated_ligand_nonbonded_pair_count() as u64
        && observed.excluded_ligand_pair_count == expected.excluded_ligand_pair_count() as u64
        && observed.evaluated_receptor_ligand_pair_count
            == expected.evaluated_receptor_ligand_pair_count() as u64
        && observed.declared_chirality_center_count
            == expected.declared_chirality_center_count() as u64
        && observed.element_vdw_ligand_pair_count == expected.element_vdw_ligand_pair_count() as u64
        && observed.element_vdw_ligand_severe_overlap_count
            == expected.element_vdw_ligand_severe_overlap_count() as u64
        && observed.element_vdw_receptor_candidate_pair_count
            == expected.element_vdw_receptor_candidate_pair_count() as u64
        && observed.element_vdw_receptor_full_cartesian_pair_count
            == expected.element_vdw_receptor_full_cartesian_pair_count() as u64
        && observed.element_vdw_receptor_cell_count
            == expected.element_vdw_receptor_cell_count() as u64
        && observed.element_vdw_receptor_severe_overlap_count
            == expected.element_vdw_receptor_severe_overlap_count() as u64
        && [
            (
                expected.rotation_orthogonality_max_error(),
                observed.rotation_orthogonality_max_error,
            ),
            (
                expected.rotation_determinant(),
                observed.rotation_determinant,
            ),
            (
                expected.max_bond_length_delta_angstrom(),
                observed.max_bond_length_delta_angstrom,
            ),
            (
                expected.minimum_ligand_nonbonded_distance_angstrom(),
                observed.minimum_ligand_nonbonded_distance_angstrom,
            ),
            (
                expected.minimum_receptor_ligand_distance_angstrom(),
                observed.minimum_receptor_ligand_distance_angstrom,
            ),
            (
                expected.minimum_declared_chiral_volume(),
                observed.minimum_declared_chiral_volume,
            ),
            (
                expected.maximum_pocket_center_distance_angstrom(),
                observed.maximum_pocket_center_distance_angstrom,
            ),
            (
                expected.element_vdw_ligand_minimum_distance_angstrom(),
                observed.element_vdw_ligand_minimum_distance_angstrom,
            ),
            (
                expected.element_vdw_ligand_minimum_ratio(),
                observed.element_vdw_ligand_minimum_ratio,
            ),
            (
                expected.element_vdw_receptor_minimum_distance_angstrom(),
                observed.element_vdw_receptor_minimum_distance_angstrom,
            ),
            (
                expected.element_vdw_receptor_minimum_ratio(),
                observed.element_vdw_receptor_minimum_ratio,
            ),
        ]
        .iter()
        .all(|(expected, observed)| numeric_matches(backend, *expected, *observed))
}

fn validity_receptor_candidate_pair_count(
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
    cell_size: f64,
    receptor_cells: &HashMap<(i64, i64, i64), u64>,
) -> Result<u64> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity ligand count does not fit usize",
        )
    })?;
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity coordinate offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity coordinate end overflowed",
        )
    })?;
    if coordinates
        .iter()
        .any(|channel| channel.get(begin..end).is_none())
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity coordinate segment exceeds its buffer",
        ));
    }
    let mut count = 0_u64;
    for ((x, y), z) in coordinates[0][begin..end]
        .iter()
        .zip(&coordinates[1][begin..end])
        .zip(&coordinates[2][begin..end])
    {
        let key = (
            validity_cell_component(*x, cell_size).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity x coordinate has an invalid cell key",
                )
            })?,
            validity_cell_component(*y, cell_size).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity y coordinate has an invalid cell key",
                )
            })?,
            validity_cell_component(*z, cell_size).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity z coordinate has an invalid cell key",
                )
            })?,
        );
        for dx in -1_i64..=1 {
            for dy in -1_i64..=1 {
                for dz in -1_i64..=1 {
                    let neighbor = (
                        key.0.checked_add(dx).ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity x cell neighbor overflowed",
                            )
                        })?,
                        key.1.checked_add(dy).ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity y cell neighbor overflowed",
                            )
                        })?,
                        key.2.checked_add(dz).ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity z cell neighbor overflowed",
                            )
                        })?,
                    );
                    count = count
                        .checked_add(receptor_cells.get(&neighbor).copied().unwrap_or(0))
                        .ok_or_else(|| {
                            Error::local(
                                ErrorCode::AbiMismatch,
                                "native fixed64 validity receptor candidate count overflowed",
                            )
                        })?;
                }
            }
        }
    }
    Ok(count)
}

#[allow(clippy::too_many_arguments)]
fn validate_scorer_and_validity_evidence(
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    refinement_rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    ligand_atom_count: u64,
    receptor_atom_count: u64,
    exclusion_count: u64,
    chirality_count: u64,
    contact_cell_size_angstrom: f64,
    receptor_cells: &HashMap<(i64, i64, i64), u64>,
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
    independent_scorer_context: &IndependentScorerContext,
    independent_context: &IndependentValidityContext,
    backend: Backend,
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    if scorer_rows.len() != candidate_count
        || validity_rows.len() != candidate_count
        || ranking_rows.len() != candidate_count
        || refinement_rows.len() != candidate_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 scorer, validity, or ranking denominator is invalid",
        ));
    }
    let total_ligand_pairs = ligand_atom_count
        .checked_mul(ligand_atom_count.checked_sub(1).ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 validity ligand denominator underflowed",
            )
        })?)
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 validity ligand-pair denominator overflowed",
            )
        })?;
    let evaluated_ligand_pairs =
        total_ligand_pairs
            .checked_sub(exclusion_count)
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity exclusions exceed the ligand-pair denominator",
                )
            })?;
    let receptor_pairs = ligand_atom_count
        .checked_mul(receptor_atom_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 validity receptor-pair denominator overflowed",
            )
        })?;
    let receptor_cell_count = u64::try_from(receptor_cells.len()).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 validity receptor-cell count does not fit u64",
        )
    })?;
    for slot in 0..candidate_count {
        let scorer = &scorer_rows[slot];
        let validity = &validity_rows[slot];
        let ranking = &ranking_rows[slot];
        if scorer.slot_index as usize != slot
            || scorer.reserved0 != 0
            || scorer.reserved.iter().any(|value| *value != 0)
            || validity.slot_index as usize != slot
            || validity.reserved.iter().any(|value| *value != 0)
            || ranking.slot_index as usize != slot
            || ranking.reserved0 != 0
            || ranking.reserved.iter().any(|value| *value != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 scorer, validity, or ranking row ABI shape is invalid",
            ));
        }
        let coordinate_ready =
            refinement_rows[slot].status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
        if !coordinate_ready {
            if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
                || scorer.failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
                || !scorer_failure_rank_evidence_is_zero(scorer)
                || scorer.receptor_candidate_pair_count != 0
                || scorer.ligand_pair_count != 0
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 inactive scorer row disagrees with refinement eligibility",
                ));
            }
        } else {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 scorer ligand denominator does not fit usize",
                )
            })?;
            let owned =
                coordinate_segment(final_coordinates, slot, ligand_count).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 scorer coordinates exceed their owned buffer",
                    )
                })?;
            let coordinates = (0..ligand_count)
                .map(|atom| {
                    Vec3::new(
                        owned.x_angstrom[atom],
                        owned.y_angstrom[atom],
                        owned.z_angstrom[atom],
                    )
                })
                .collect::<Vec<_>>();
            let independent = independent_scorer_context
                .score_coordinates(&coordinates)
                .map_err(|error| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!("independent fixed64 scorer evaluation failed: {error}"),
                    )
                })?;
            match independent {
                IndependentScorerOutcome::Scored(expected) => {
                    let term_sum = scorer.weighted_terms.iter().copied().sum::<f64>();
                    let terms_match = expected
                        .weighted_terms()
                        .into_iter()
                        .zip(scorer.weighted_terms)
                        .all(|(expected, observed)| numeric_matches(backend, expected, observed));
                    let count_matches = [
                        (
                            expected.receptor_candidate_pair_count(),
                            scorer.receptor_candidate_pair_count,
                        ),
                        (expected.ligand_pair_count(), scorer.ligand_pair_count),
                        (expected.hbond_count(), scorer.hbond_count),
                        (
                            expected.hydrophobic_contact_count(),
                            scorer.hydrophobic_contact_count,
                        ),
                        (expected.buried_polar_count(), scorer.buried_polar_count),
                    ]
                    .into_iter()
                    .all(|(expected, observed)| u64::try_from(expected).ok() == Some(observed));
                    if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_SCORED
                        || scorer.failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_NONE
                        || !scorer.total_score.is_finite()
                        || scorer.weighted_terms.iter().any(|value| !value.is_finite())
                        || (term_sum - scorer.total_score).abs() > 1.0e-12
                        || !terms_match
                        || !numeric_matches(backend, expected.total_score(), scorer.total_score)
                        || !count_matches
                    {
                        return Err(Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 scored terms, score, or counts disagree with independent replay",
                        ));
                    }
                }
                IndependentScorerOutcome::TypedFailure(expected) => {
                    let receptor_count =
                        u64::try_from(expected.receptor_candidate_pair_count()).ok();
                    let ligand_count = u64::try_from(expected.ligand_pair_count()).ok();
                    if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
                        || scorer.failure_code
                            != independent_scorer_failure_code(expected.failure_code())
                        || !scorer_failure_rank_evidence_is_zero(scorer)
                        || !scorer_failure_pair_evidence_is_valid(scorer)
                        || receptor_count != Some(scorer.receptor_candidate_pair_count)
                        || ligand_count != Some(scorer.ligand_pair_count)
                    {
                        return Err(Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 scorer typed failure disagrees with independent replay",
                        ));
                    }
                }
            }
        }
        if validity.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity ligand denominator does not fit usize",
                )
            })?;
            let owned =
                coordinate_segment(final_coordinates, slot, ligand_count).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 validity coordinates exceed their owned buffer",
                    )
                })?;
            let coordinates = (0..ligand_count)
                .map(|atom| {
                    Vec3::new(
                        owned.x_angstrom[atom],
                        owned.y_angstrom[atom],
                        owned.z_angstrom[atom],
                    )
                })
                .collect::<Vec<_>>();
            let quaternion = Quaternion::new(
                final_quaternions[0][slot],
                final_quaternions[1][slot],
                final_quaternions[2][slot],
                final_quaternions[3][slot],
            );
            let independent = independent_context
                .evaluate_coordinates(&coordinates, quaternion)
                .map_err(|error| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!("independent fixed64 validity evaluation failed: {error}"),
                    )
                })?;
            let (expected_checks, expected_measurements) = match independent {
                IndependentValidityOutcome::Evaluated {
                    checks,
                    measurements,
                } => (checks, measurements),
                IndependentValidityOutcome::TypedFailure(_) => {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 validity reported evaluated evidence for an independently typed failure",
                    ));
                }
            };
            let expected_mask = independent_validity_check_mask(expected_checks);
            let unknown_checks =
                validity.passed_check_mask & !sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
            if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_SCORED
                || validity.failure_code != sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE
                || validity.upstream_scorer_failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_NONE
                || unknown_checks != 0
                || validity.blocker_mask
                    != (sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ validity.passed_check_mask)
                || validity.observed_count != 0
                || validity.atom_count != ligand_atom_count
                || !validity_measurements_are_finite(validity)
                || validity.passed_check_mask != expected_mask
                || validity.blocker_mask
                    != (sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ expected_mask)
                || !independent_validity_measurements_match(
                    backend,
                    expected_measurements,
                    validity,
                )
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 evaluated validity evidence is invalid",
                ));
            }
            let receptor_candidate_pairs = validity_receptor_candidate_pair_count(
                final_coordinates,
                slot,
                ligand_atom_count,
                contact_cell_size_angstrom,
                receptor_cells,
            )?;
            let ligand_vdw_passed = validity.passed_check_mask
                & sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW
                != 0;
            let receptor_vdw_passed = validity.passed_check_mask
                & sys::BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW
                != 0;
            if validity.evaluated_ligand_nonbonded_pair_count != evaluated_ligand_pairs
                || validity.excluded_ligand_pair_count != exclusion_count
                || validity.element_vdw_ligand_pair_count != evaluated_ligand_pairs
                || validity.element_vdw_ligand_severe_overlap_count > evaluated_ligand_pairs
                || validity.evaluated_receptor_ligand_pair_count != receptor_pairs
                || validity.declared_chirality_center_count != chirality_count
                || validity.element_vdw_receptor_candidate_pair_count != receptor_candidate_pairs
                || validity.element_vdw_receptor_full_cartesian_pair_count != receptor_pairs
                || validity.element_vdw_receptor_cell_count != receptor_cell_count
                || validity.element_vdw_receptor_severe_overlap_count > receptor_candidate_pairs
                || ligand_vdw_passed != (validity.element_vdw_ligand_severe_overlap_count == 0)
                || receptor_vdw_passed != (validity.element_vdw_receptor_severe_overlap_count == 0)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity measurement denominators are inconsistent",
                ));
            }
        } else {
            if !validity_failure_evidence_is_zero(validity) {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 failed validity row retained measurements",
                ));
            }
            let valid_upstream_failure = validity.status
                == sys::BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE
                && scorer.status == sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
                && validity.failure_code == sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER
                && validity.upstream_scorer_failure_code == scorer.failure_code
                && validity.observed_count == 0;
            let valid_typed_failure = validity.status
                == sys::BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE
                && scorer.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED
                && validity.failure_code
                    >= sys::BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES
                && validity.failure_code
                    <= sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT
                && validity.upstream_scorer_failure_code == sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            if !valid_upstream_failure && !valid_typed_failure {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 validity failure is cross-wired",
                ));
            }
            if valid_typed_failure {
                let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 validity ligand denominator does not fit usize",
                    )
                })?;
                let owned =
                    coordinate_segment(final_coordinates, slot, ligand_count).ok_or_else(|| {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 validity coordinates exceed their owned buffer",
                        )
                    })?;
                let coordinates = (0..ligand_count)
                    .map(|atom| {
                        Vec3::new(
                            owned.x_angstrom[atom],
                            owned.y_angstrom[atom],
                            owned.z_angstrom[atom],
                        )
                    })
                    .collect::<Vec<_>>();
                let quaternion = Quaternion::new(
                    final_quaternions[0][slot],
                    final_quaternions[1][slot],
                    final_quaternions[2][slot],
                    final_quaternions[3][slot],
                );
                match independent_context
                    .evaluate_coordinates(&coordinates, quaternion)
                    .map_err(|error| {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            format!("independent fixed64 validity evaluation failed: {error}"),
                        )
                    })? {
                    IndependentValidityOutcome::TypedFailure(failure)
                        if validity.failure_code
                            == independent_validity_failure_code(failure.failure_code())
                            && validity.observed_count == failure.observed_count() as u64 => {}
                    _ => {
                        return Err(Error::local(
                            ErrorCode::AbiMismatch,
                            "native fixed64 validity typed failure disagrees with independent evaluation",
                        ));
                    }
                }
            }
        }
        let rank_eligible = bool_from_abi(ranking.rank_eligible, "rank eligibility")?;
        let valid_rank_eligible =
            bool_from_abi(ranking.valid_rank_eligible, "valid-rank eligibility")?;
        if !rank_eligible
            && (valid_rank_eligible
                || ranking.stable_rank != 0
                || ranking.stable_valid_rank != 0
                || ranking.total_score != 0.0
                || digest_present(&ranking.coordinate_sha256))
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 ineligible ranking row retained score or coordinate evidence",
            ));
        }
    }
    Ok(())
}

fn counted_index_prefix<'a>(values: &'a [u32], count: u64, label: &str) -> Result<&'a [u32]> {
    let count = usize::try_from(count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("native fixed64 {label} count does not fit usize"),
        )
    })?;
    values.get(..count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("native fixed64 {label} count exceeds the supplied buffer"),
        )
    })
}

fn direct_coordinate_rmsd(
    coordinates: [&[f64]; 3],
    ligand_atom_count: u64,
    left_slot: usize,
    right_slot: usize,
) -> Result<f64> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD ligand denominator does not fit usize",
        )
    })?;
    if ligand_count == 0 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD ligand denominator is zero",
        ));
    }
    let left_begin = left_slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 left RMSD coordinate offset overflowed",
        )
    })?;
    let right_begin = right_slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 right RMSD coordinate offset overflowed",
        )
    })?;
    let coordinate_count = (sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize)
        .checked_mul(ligand_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 RMSD coordinate denominator overflowed",
            )
        })?;
    if coordinates
        .iter()
        .any(|channel| channel.len() != coordinate_count)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD coordinate denominator is invalid",
        ));
    }
    let mut squared_sum = 0.0;
    for atom in 0..ligand_count {
        let dx = coordinates[0][left_begin + atom] - coordinates[0][right_begin + atom];
        let dy = coordinates[1][left_begin + atom] - coordinates[1][right_begin + atom];
        let dz = coordinates[2][left_begin + atom] - coordinates[2][right_begin + atom];
        if !dx.is_finite() || !dy.is_finite() || !dz.is_finite() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 RMSD coordinate delta is non-finite",
            ));
        }
        squared_sum += dx * dx + dy * dy + dz * dz;
    }
    let rmsd = (squared_sum / ligand_count as f64).sqrt();
    if !rmsd.is_finite() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 direct-coordinate RMSD is non-finite",
        ));
    }
    Ok(rmsd)
}

#[allow(clippy::too_many_arguments)]
fn validate_index_evidence(
    ranking: &sys::bg_docking_stable_top_k_output_v1,
    cluster: &sys::bg_docking_rmsd_cluster_output_v1,
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    cluster_rows: &[sys::bg_docking_rmsd_cluster_row_v1],
    primary_indices: &[u32],
    valid_indices: &[u32],
    representative_indices: &[u32],
    top_k_indices: &[u32],
    rmsd_threshold_angstrom: f64,
    final_coordinates: [&[f64]; 3],
    ligand_atom_count: u64,
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    if scorer_rows.len() != candidate_count
        || validity_rows.len() != candidate_count
        || ranking_rows.len() != candidate_count
        || cluster_rows.len() != candidate_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rank or cluster row denominator is invalid",
        ));
    }
    if !rmsd_threshold_angstrom.is_finite() || rmsd_threshold_angstrom <= 0.0 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD threshold is invalid",
        ));
    }
    let primary =
        counted_index_prefix(primary_indices, ranking.primary_index_count, "primary rank")?;
    let valid = counted_index_prefix(valid_indices, ranking.valid_index_count, "valid rank")?;
    let representatives = counted_index_prefix(
        representative_indices,
        cluster.representative_index_count,
        "cluster representative",
    )?;
    let top_k = counted_index_prefix(top_k_indices, cluster.top_k_index_count, "cluster Top-K")?;
    let mut primary_seen = vec![false; candidate_count];
    let mut previous_ranked: Option<(f64, usize)> = None;
    for (offset, raw_slot) in primary.iter().copied().enumerate() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank slot does not fit usize",
            )
        })?;
        if slot >= candidate_count || primary_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank slots are out of range or duplicated",
            ));
        }
        let row = &ranking_rows[slot];
        let score = row.total_score;
        let incorrectly_ordered = previous_ranked.is_some_and(|(previous_score, previous_slot)| {
            score < previous_score || (score == previous_score && slot < previous_slot)
        });
        if !score.is_finite()
            || incorrectly_ordered
            || !bool_from_abi(row.rank_eligible, "rank eligibility")?
            || row.stable_rank as usize != offset + 1
            || scorer_rows[slot].status != sys::BG_DOCKING_SCORER_V1_ROW_SCORED
            || score != scorer_rows[slot].total_score
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank slots disagree with scorer or ranking rows",
            ));
        }
        primary_seen[slot] = true;
        previous_ranked = Some((score, slot));
    }
    for (slot, row) in ranking_rows.iter().enumerate() {
        let rank_eligible = bool_from_abi(row.rank_eligible, "rank eligibility")?;
        if rank_eligible != primary_seen[slot]
            || rank_eligible != (scorer_rows[slot].status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED)
            || (!rank_eligible && row.stable_rank != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank membership is inconsistent",
            ));
        }
    }

    let expected_valid = primary
        .iter()
        .copied()
        .filter(|raw_slot| {
            let slot = *raw_slot as usize;
            validity_rows[slot].status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
                && validity_rows[slot].passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
                && validity_rows[slot].blocker_mask == 0
        })
        .collect::<Vec<_>>();
    if valid != expected_valid.as_slice() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 valid rank order is not the validity-filtered primary order",
        ));
    }

    let mut valid_seen = vec![false; candidate_count];
    for (offset, raw_slot) in valid.iter().copied().enumerate() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank slot does not fit usize",
            )
        })?;
        if slot >= candidate_count || valid_seen[slot] || !primary_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank slots are out of range, duplicated, or unranked",
            ));
        }
        let row = &ranking_rows[slot];
        if !bool_from_abi(row.valid_rank_eligible, "valid-rank eligibility")?
            || row.stable_valid_rank as usize != offset + 1
            || validity_rows[slot].status != sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
            || validity_rows[slot].passed_check_mask != sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
            || validity_rows[slot].blocker_mask != 0
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank slots disagree with validity or ranking rows",
            ));
        }
        valid_seen[slot] = true;
    }
    for (slot, row) in ranking_rows.iter().enumerate() {
        let valid_rank_eligible = bool_from_abi(row.valid_rank_eligible, "valid-rank eligibility")?;
        let expected_valid = primary_seen[slot]
            && validity_rows[slot].status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
            && validity_rows[slot].passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
            && validity_rows[slot].blocker_mask == 0;
        if valid_rank_eligible != valid_seen[slot]
            || valid_rank_eligible != expected_valid
            || (!valid_rank_eligible && row.stable_valid_rank != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank membership is inconsistent",
            ));
        }
    }

    let mut expected_representatives = Vec::<u32>::new();
    for raw_slot in valid.iter().copied() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid slot does not fit usize during cluster reconstruction",
            )
        })?;
        let mut matched = false;
        for raw_representative in &expected_representatives {
            let representative_slot = usize::try_from(*raw_representative).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 reconstructed representative does not fit usize",
                )
            })?;
            let rmsd = direct_coordinate_rmsd(
                final_coordinates,
                ligand_atom_count,
                slot,
                representative_slot,
            )?;
            let tolerance = 2.0e-12 * 1.0_f64.max(rmsd.abs());
            if rmsd <= rmsd_threshold_angstrom + tolerance {
                matched = true;
                break;
            }
        }
        if !matched {
            expected_representatives.push(raw_slot);
        }
    }
    if representatives != expected_representatives.as_slice() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 representative order disagrees with independent stable-valid-rank reconstruction",
        ));
    }

    let mut representative_seen = vec![false; candidate_count];
    for (offset, raw_slot) in representatives.iter().copied().enumerate() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 representative slot does not fit usize",
            )
        })?;
        if slot >= candidate_count || representative_seen[slot] || !valid_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 representative slots are out of range, duplicated, or invalid",
            ));
        }
        let row = &cluster_rows[slot];
        if !bool_from_abi(row.cluster_eligible, "cluster eligibility")?
            || !bool_from_abi(row.representative, "cluster representative")?
            || row.representative_slot_index as usize != slot
            || row.cluster_id as usize != offset + 1
            || row.cluster_rank as usize != offset + 1
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 representative slots disagree with cluster rows",
            ));
        }
        representative_seen[slot] = true;
    }
    let mut observed_cluster_sizes = vec![0_u32; representatives.len()];
    for (slot, row) in cluster_rows.iter().enumerate() {
        if row.reserved0 != 0 || row.reserved1 != 0 || row.reserved.iter().any(|value| *value != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 cluster row ABI shape is invalid",
            ));
        }
        let eligible = bool_from_abi(row.cluster_eligible, "cluster eligibility")?;
        let representative = bool_from_abi(row.representative, "cluster representative")?;
        if eligible != valid_seen[slot] || representative != representative_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 cluster membership is inconsistent",
            ));
        }
        if eligible {
            let cluster_id = usize::try_from(row.cluster_id).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 cluster id does not fit usize",
                )
            })?;
            let representative_slot =
                usize::try_from(row.representative_slot_index).map_err(|_| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 representative identity does not fit usize",
                    )
                })?;
            if row.status != sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED
                || row.stable_valid_rank != ranking_rows[slot].stable_valid_rank
                || cluster_id == 0
                || cluster_id > representatives.len()
                || row.cluster_rank != row.cluster_id
                || representative_slot >= candidate_count
                || !representative_seen[representative_slot]
                || representatives[cluster_id - 1] as usize != representative_slot
                || row.coordinate_sha256 != ranking_rows[slot].coordinate_sha256
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 clustered row is inconsistent with rank evidence",
                ));
            }
            let expected_rmsd = direct_coordinate_rmsd(
                final_coordinates,
                ligand_atom_count,
                slot,
                representative_slot,
            )?;
            let tolerance = 2.0e-12
                * 1.0_f64
                    .max(expected_rmsd.abs())
                    .max(row.direct_rmsd_to_representative_angstrom.abs());
            let assigned_to_first_matching_representative =
                representatives.iter().take(cluster_id - 1).all(|earlier| {
                    let Ok(earlier_slot) = usize::try_from(*earlier) else {
                        return false;
                    };
                    let Ok(earlier_rmsd) = direct_coordinate_rmsd(
                        final_coordinates,
                        ligand_atom_count,
                        slot,
                        earlier_slot,
                    ) else {
                        return false;
                    };
                    let earlier_tolerance = 2.0e-12 * 1.0_f64.max(earlier_rmsd.abs());
                    earlier_rmsd > rmsd_threshold_angstrom + earlier_tolerance
                });
            if !row.direct_rmsd_to_representative_angstrom.is_finite()
                || row.direct_rmsd_to_representative_angstrom < 0.0
                || row.direct_rmsd_to_representative_angstrom > rmsd_threshold_angstrom + tolerance
                || (row.direct_rmsd_to_representative_angstrom - expected_rmsd).abs() > tolerance
                || (representative && row.direct_rmsd_to_representative_angstrom != 0.0)
                || !assigned_to_first_matching_representative
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 cluster RMSD disagrees with final coordinates",
                ));
            }
            observed_cluster_sizes[cluster_id - 1] += 1;
        } else if row.status != sys::BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID
            || row.stable_valid_rank != 0
            || row.cluster_id != 0
            || row.representative_slot_index != 0
            || row.cluster_rank != 0
            || row.top_k_rank != 0
            || row.cluster_size != 0
            || row.direct_rmsd_to_representative_angstrom != 0.0
            || digest_present(&row.coordinate_sha256)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 non-clustered row retained cluster evidence",
            ));
        }
    }
    for row in cluster_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED)
    {
        if row.cluster_size != observed_cluster_sizes[row.cluster_id as usize - 1] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 cluster size evidence is inconsistent",
            ));
        }
    }

    let expected_top_k_count = representatives
        .len()
        .min(sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize);
    if top_k.len() != expected_top_k_count {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 Top-K count does not contain the complete frozen prefix",
        ));
    }
    let mut top_k_seen = vec![false; candidate_count];
    for (offset, raw_slot) in top_k.iter().copied().enumerate() {
        let slot = raw_slot as usize;
        if slot >= candidate_count
            || top_k_seen[slot]
            || representatives.get(offset).copied() != Some(raw_slot)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 Top-K slots are out of range, duplicated, or reordered",
            ));
        }
        let row = &cluster_rows[slot];
        if !bool_from_abi(row.top_k_representative, "cluster Top-K representative")?
            || row.top_k_rank as usize != offset + 1
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 Top-K slots disagree with cluster rows",
            ));
        }
        top_k_seen[slot] = true;
    }
    for (slot, row) in cluster_rows.iter().enumerate() {
        let top_k_representative =
            bool_from_abi(row.top_k_representative, "cluster Top-K representative")?;
        if top_k_representative != top_k_seen[slot]
            || (!top_k_representative && row.top_k_rank != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 Top-K membership is inconsistent",
            ));
        }
    }
    Ok(())
}

#[cfg(test)]
#[allow(clippy::items_after_test_module)]
mod output_validation_tests {
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
            let mut ranking_rows =
                vec![zeroed_abi_value!(sys::bg_docking_stable_top_k_row_v1); count];
            let mut refinement_rows =
                vec![zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1); count];
            let mut cluster_rows =
                vec![zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1); count];
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
                validity_rows[slot].status =
                    sys::BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE;
                validity_rows[slot].failure_code =
                    sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER;
                validity_rows[slot].upstream_scorer_failure_code =
                    sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
                ranking_rows[slot].slot_index = slot as u32;
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
                refinement_rows[slot].status =
                    sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
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
        fabricated_bit.validity_rows[0].blocker_mask = sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
            ^ fabricated_bit.validity_rows[0].passed_check_mask;
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
        passed_despite_severe_overlap.validity_rows[0].element_vdw_receptor_severe_overlap_count =
            1;
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
        let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_pipeline_row_v1);
        let component_binding = [1; 32];
        let policy = [2; 32];
        let refinement = [3; 32];
        let scorer = [4; 32];
        let validity = [5; 32];
        let ranking = [6; 32];
        let cluster = [7; 32];
        row.refinement_evidence_sha256 = refinement;
        row.scorer_evidence_sha256 = scorer;
        row.validity_evidence_sha256 = validity;
        row.ranking_evidence_sha256 = ranking;
        row.cluster_evidence_sha256 = cluster;
        row.row_receipt_sha256 = canonical_pipeline_row_receipt(
            &row,
            component_binding,
            policy,
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
            refinement,
            scorer,
            validity,
            ranking,
            cluster,
        )
        .is_ok());

        let mut substituted_component = row;
        substituted_component.scorer_evidence_sha256 = [9; 32];
        assert!(validate_pipeline_receipt_bindings(
            &substituted_component,
            component_binding,
            policy,
            refinement,
            scorer,
            validity,
            ranking,
            cluster,
        )
        .is_err());

        let mut substituted_row = row;
        substituted_row.row_receipt_sha256 = [9; 32];
        assert!(validate_pipeline_receipt_bindings(
            &substituted_row,
            component_binding,
            policy,
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
        assert!(validate_producer_row_semantics(
            &cross_wired_passthrough,
            views,
            0,
            1,
            Some(source),
        )
        .is_err());

        let mut cross_wired_source = generated_producer_row(source);
        cross_wired_source.source_proposal_sha256 = [9; 32];
        assert!(
            validate_producer_row_semantics(&cross_wired_source, views, 0, 1, Some(source),)
                .is_err()
        );

        let different_coordinates = [vec![1.0], vec![0.0], vec![0.0]];
        let different_views = [
            different_coordinates[0].as_slice(),
            different_coordinates[1].as_slice(),
            different_coordinates[2].as_slice(),
        ];
        assert!(
            validate_producer_row_semantics(&valid, different_views, 0, 1, Some(source),).is_err()
        );

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
        assert!(validate_producer_row_semantics(
            &transformed,
            transformed_views,
            24,
            1,
            Some(source),
        )
        .is_ok());
        transformed_coordinates[0][24] = 1.0;
        let substituted_views = [
            transformed_coordinates[0].as_slice(),
            transformed_coordinates[1].as_slice(),
            transformed_coordinates[2].as_slice(),
        ];
        assert!(validate_producer_row_semantics(
            &transformed,
            substituted_views,
            24,
            1,
            Some(source),
        )
        .is_err());

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
        wrong_failure.failure_code =
            sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
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
        let torsion_coordinates: [Vec<f64>; 8] =
            std::array::from_fn(|_| vec![0.0; candidate_count]);
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
}

fn require_authority_false(fields: &[(u8, &str)]) -> Result<()> {
    for (value, label) in fields {
        if bool_from_abi(*value, label)? {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} unexpectedly became authorized"),
            ));
        }
    }
    Ok(())
}

fn authority_disposition(
    output: &sys::bg_docking_fixed64_pipeline_output_v1,
    producer: &sys::bg_docking_fixed64_producer_output_v1,
) -> Result<Fixed64AuthorityDisposition> {
    Ok(Fixed64AuthorityDisposition {
        result_dependent_input_consumed: bool_from_abi(
            output.result_dependent_input_consumed,
            "result-dependent input",
        )?,
        fallback_allowed: bool_from_abi(output.fallback_allowed, "fallback")?,
        multi_anchor_consumed: bool_from_abi(
            producer.multi_anchor_consumed,
            "multi-anchor consumption",
        )?,
        denominator_preserved: bool_from_abi(output.denominator_preserved, "denominator")?,
        molecular_execution_authorized: bool_from_abi(
            output.molecular_execution_authorized,
            "molecular execution",
        )?,
        reservation_authorized: bool_from_abi(output.reservation_authorized, "reservation")?,
        benchmark_execution_authorized: bool_from_abi(
            output.benchmark_execution_authorized,
            "benchmark execution",
        )?,
        existing_rank_auto_change_authorized: bool_from_abi(
            output.existing_rank_auto_change_authorized,
            "rank mutation",
        )?,
        customer_pose_emission_authorized: bool_from_abi(
            output.customer_pose_emission_authorized,
            "customer pose emission",
        )?,
        production_claim_authorized: bool_from_abi(
            output.production_claim_authorized,
            "production claim",
        )?,
        scientific_claim_authorized: bool_from_abi(
            output.scientific_claim_authorized,
            "scientific claim",
        )?,
    })
}

fn producer_evidence(
    row: &sys::bg_docking_fixed64_producer_row_v1,
) -> Result<Fixed64ProducerEvidence> {
    Ok(Fixed64ProducerEvidence {
        slot_index: row.slot_index,
        lane: row.lane,
        status: row.status,
        failure_code: row.failure_code,
        placement_kind: row.placement_kind,
        component_failure_code: row.component_failure_code,
        backend: Backend::from_raw(row.backend)?,
        ligand_atom_count: row.ligand_atom_count,
        coordinate_offset: row.coordinate_offset,
        coordinates_available: bool_from_abi(
            row.coordinates_available,
            "producer coordinates available",
        )?,
        steric_precheck_passed: bool_from_abi(
            row.steric_precheck_passed,
            "producer steric precheck",
        )?,
        source_identity_verified: bool_from_abi(
            row.source_identity_verified,
            "producer source identity",
        )?,
        allocation_identity_verified: bool_from_abi(
            row.allocation_identity_verified,
            "producer allocation identity",
        )?,
        geometric_identity_verified: bool_from_abi(
            row.geometric_identity_verified,
            "producer geometric identity",
        )?,
        denominator_preserved: bool_from_abi(
            row.denominator_preserved,
            "producer row denominator",
        )?,
        placement_quaternion: [
            row.placement_quaternion_x,
            row.placement_quaternion_y,
            row.placement_quaternion_z,
            row.placement_quaternion_w,
        ],
        allocation_slot_receipt_sha256: row.allocation_slot_receipt_sha256,
        source_payload_receipt_sha256: row.source_payload_receipt_sha256,
        source_proposal_sha256: row.source_proposal_sha256,
        source_coordinate_sha256: row.source_coordinate_sha256,
        placement_receipt_sha256: row.placement_receipt_sha256,
        output_proposal_sha256: row.output_proposal_sha256,
        output_coordinate_sha256: row.output_coordinate_sha256,
        row_receipt_sha256: row.row_receipt_sha256,
        geometric: Fixed64GeometricEvidence {
            status: row.geometric_admission.status,
            failure_code: row.geometric_admission.failure_code,
            decision: row.geometric_admission.decision,
            rank_eligible: bool_from_abi(
                row.geometric_admission.rank_eligible,
                "geometric rank eligibility",
            )?,
            ligand_atom_count: row.geometric_admission.ligand_atom_count,
            receptor_atom_count: row.geometric_admission.receptor_atom_count,
            exact_pair_count: row.geometric_admission.exact_pair_count,
            penetration_pair_count: row.geometric_admission.penetration_pair_count,
            unique_ligand_penetration_atom_count: row
                .geometric_admission
                .unique_ligand_penetration_atom_count,
            unique_ligand_heavy_atom_penetration_count: row
                .geometric_admission
                .unique_ligand_heavy_atom_penetration_count,
            raw_minimum_distance_angstrom: row.geometric_admission.raw_minimum_distance_angstrom,
            minimum_vdw_surface_gap_angstrom: row
                .geometric_admission
                .minimum_vdw_surface_gap_angstrom,
            minimum_vdw_ratio: row.geometric_admission.minimum_vdw_ratio,
            sphere_overlap_proxy_angstrom3: row.geometric_admission.sphere_overlap_proxy_angstrom3,
            pocket_escape_angstrom: row.geometric_admission.pocket_escape_angstrom,
            row_receipt_sha256: row.geometric_admission.row_receipt_sha256,
        },
    })
}

fn rigid_profile_evidence(
    evidence: &sys::bg_docking_rigid_refinement_evidence_v1,
) -> Result<Fixed64RigidProfileEvidence> {
    Ok(Fixed64RigidProfileEvidence {
        profile: evidence.profile,
        available: bool_from_abi(evidence.available, "rigid profile availability")?,
        accepted_steps: evidence.accepted_steps,
        accepted_translation_steps: evidence.accepted_translation_steps,
        accepted_rotation_steps: evidence.accepted_rotation_steps,
        line_search_evaluation_count: evidence.line_search_evaluation_count,
        fallback_direction_step_count: evidence.fallback_direction_step_count,
        initial_penalty: evidence.initial_penalty,
        final_penalty: evidence.final_penalty,
        total_translation_angstrom: evidence.total_translation_angstrom,
        total_rotation_vector_radians: evidence.total_rotation_vector_radians,
        total_rotation_path_radians: evidence.total_rotation_path_radians,
        initial_centroid_offset_angstrom: evidence.initial_centroid_offset_angstrom,
        final_centroid_offset_angstrom: evidence.final_centroid_offset_angstrom,
        maximum_centroid_offset_angstrom: evidence.maximum_centroid_offset_angstrom,
    })
}

fn rigid_evidence(row: &sys::bg_docking_rigid_refinement_row_v1) -> Result<Fixed64RigidEvidence> {
    Ok(Fixed64RigidEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        candidate_mode: row.candidate_mode,
        selected_profile: row.selected_profile,
        baseline_duplicate_of_v2: bool_from_abi(
            row.baseline_duplicate_of_v2,
            "rigid V3 baseline duplicate",
        )?,
        clearance_evaluated: bool_from_abi(row.clearance_evaluated, "rigid clearance evaluated")?,
        clearance_selected: bool_from_abi(row.clearance_selected, "rigid clearance selected")?,
        selected: rigid_profile_evidence(&row.selected)?,
        comparison_v2: rigid_profile_evidence(&row.comparison_v2)?,
        baseline_v3: rigid_profile_evidence(&row.baseline_v3)?,
        clearance_v4: rigid_profile_evidence(&row.clearance_v4)?,
    })
}

fn torsion_evidence(row: &sys::bg_docking_torsion_v7_row_v1) -> Result<Fixed64TorsionEvidence> {
    Ok(Fixed64TorsionEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        skip_reason: row.skip_reason,
        selection_reason: row.selection_reason,
        selection_window_reachable: bool_from_abi(
            row.selection_window_reachable,
            "torsion selection window reachable",
        )?,
        evaluation_stopped_after_selection_window_became_unreachable: bool_from_abi(
            row.evaluation_stopped_after_selection_window_became_unreachable,
            "torsion evaluation stopped after unreachable selection window",
        )?,
        torsion_evaluated: bool_from_abi(row.torsion_evaluated, "torsion evaluated")?,
        torsion_variant_available: bool_from_abi(
            row.torsion_variant_available,
            "torsion variant available",
        )?,
        torsion_selected: bool_from_abi(row.torsion_selected, "torsion selected")?,
        torsion_step_budget: row.torsion_step_budget,
        fixed_objective_evaluation_count: row.fixed_objective_evaluation_count,
        torsion_trial_objective_evaluation_count: row.torsion_trial_objective_evaluation_count,
        evaluated_torsion_steps: row.evaluated_torsion_steps,
        accepted_torsion_steps: row.accepted_torsion_steps,
        baseline_v6_accepted_steps: row.baseline_v6_accepted_steps,
        source_receptor_penalty: row.source_receptor_penalty,
        source_internal_penalty: row.source_internal_penalty,
        source_combined_penalty: row.source_combined_penalty,
        baseline_receptor_penalty: row.baseline_receptor_penalty,
        baseline_internal_penalty: row.baseline_internal_penalty,
        baseline_combined_penalty: row.baseline_combined_penalty,
        optimized_receptor_penalty: row.optimized_receptor_penalty,
        optimized_internal_penalty: row.optimized_internal_penalty,
        optimized_combined_penalty: row.optimized_combined_penalty,
        final_receptor_penalty: row.final_receptor_penalty,
        final_internal_penalty: row.final_internal_penalty,
        final_combined_penalty: row.final_combined_penalty,
        evaluated_total_torsion_path_radians: row.evaluated_total_torsion_path_radians,
        accepted_total_torsion_path_radians: row.accepted_total_torsion_path_radians,
    })
}

fn torsion_move_evidence(
    move_evidence: &sys::bg_docking_torsion_v7_move_v1,
) -> Result<Fixed64TorsionMoveEvidence> {
    Ok(Fixed64TorsionMoveEvidence {
        slot_index: move_evidence.slot_index,
        move_index: move_evidence.move_index,
        evaluated: bool_from_abi(move_evidence.evaluated, "torsion move evaluated")?,
        selected: bool_from_abi(move_evidence.selected, "torsion move selected")?,
        rotatable_child_atom_index: move_evidence.rotatable_child_atom_index,
        delta_radians: move_evidence.delta_radians,
        receptor_penalty: move_evidence.receptor_penalty,
        internal_penalty: move_evidence.internal_penalty,
        combined_penalty: move_evidence.combined_penalty,
    })
}

fn refinement_evidence(
    row: &sys::bg_docking_fixed64_refinement_row_v1,
) -> Result<Fixed64RefinementEvidence> {
    Ok(Fixed64RefinementEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_stage: row.failure_stage,
        coordinate_origin: row.coordinate_origin,
        rigid_failure_code: row.rigid_failure_code,
        torsion_v7_failure_code: row.torsion_v7_failure_code,
        selected_rigid_profile: row.selected_rigid_profile,
        downstream_candidate_state: row.downstream_candidate_state,
        torsion_v7_applicable: bool_from_abi(
            row.torsion_v7_applicable,
            "torsion V7 applicability",
        )?,
        torsion_v7_selected: bool_from_abi(row.torsion_v7_selected, "torsion V7 selection")?,
        coordinate_available: bool_from_abi(
            row.coordinate_available,
            "refinement coordinate availability",
        )?,
        coordinate_sha256: row.coordinate_sha256,
    })
}

fn scorer_evidence(row: &sys::bg_docking_scorer_v1_row_v1) -> Fixed64ScorerEvidence {
    Fixed64ScorerEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        weighted_terms: row.weighted_terms,
        total_score: row.total_score,
        receptor_candidate_pair_count: row.receptor_candidate_pair_count,
        ligand_pair_count: row.ligand_pair_count,
        hbond_count: row.hbond_count,
        hydrophobic_contact_count: row.hydrophobic_contact_count,
        buried_polar_count: row.buried_polar_count,
    }
}

fn validity_evidence(row: &sys::bg_docking_pose_validity_row_v1) -> Fixed64ValidityEvidence {
    Fixed64ValidityEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        upstream_scorer_failure_code: row.upstream_scorer_failure_code,
        passed_check_mask: row.passed_check_mask,
        blocker_mask: row.blocker_mask,
        observed_count: row.observed_count,
        atom_count: row.atom_count,
        rotation_orthogonality_max_error: row.rotation_orthogonality_max_error,
        rotation_determinant: row.rotation_determinant,
        max_bond_length_delta_angstrom: row.max_bond_length_delta_angstrom,
        minimum_ligand_nonbonded_distance_angstrom: row.minimum_ligand_nonbonded_distance_angstrom,
        evaluated_ligand_nonbonded_pair_count: row.evaluated_ligand_nonbonded_pair_count,
        excluded_ligand_pair_count: row.excluded_ligand_pair_count,
        minimum_receptor_ligand_distance_angstrom: row.minimum_receptor_ligand_distance_angstrom,
        evaluated_receptor_ligand_pair_count: row.evaluated_receptor_ligand_pair_count,
        minimum_declared_chiral_volume: row.minimum_declared_chiral_volume,
        declared_chirality_center_count: row.declared_chirality_center_count,
        maximum_pocket_center_distance_angstrom: row.maximum_pocket_center_distance_angstrom,
        element_vdw_ligand_pair_count: row.element_vdw_ligand_pair_count,
        element_vdw_ligand_severe_overlap_count: row.element_vdw_ligand_severe_overlap_count,
        element_vdw_ligand_minimum_distance_angstrom: row
            .element_vdw_ligand_minimum_distance_angstrom,
        element_vdw_ligand_minimum_ratio: row.element_vdw_ligand_minimum_ratio,
        element_vdw_receptor_candidate_pair_count: row.element_vdw_receptor_candidate_pair_count,
        element_vdw_receptor_full_cartesian_pair_count: row
            .element_vdw_receptor_full_cartesian_pair_count,
        element_vdw_receptor_cell_count: row.element_vdw_receptor_cell_count,
        element_vdw_receptor_severe_overlap_count: row.element_vdw_receptor_severe_overlap_count,
        element_vdw_receptor_minimum_distance_angstrom: row
            .element_vdw_receptor_minimum_distance_angstrom,
        element_vdw_receptor_minimum_ratio: row.element_vdw_receptor_minimum_ratio,
    }
}

fn ranking_evidence(row: &sys::bg_docking_stable_top_k_row_v1) -> Result<Fixed64RankingEvidence> {
    Ok(Fixed64RankingEvidence {
        slot_index: row.slot_index,
        rank_eligible: bool_from_abi(row.rank_eligible, "rank eligibility")?,
        valid_rank_eligible: bool_from_abi(row.valid_rank_eligible, "valid-rank eligibility")?,
        stable_rank: row.stable_rank,
        stable_valid_rank: row.stable_valid_rank,
        total_score: row.total_score,
        coordinate_sha256: row.coordinate_sha256,
    })
}

fn cluster_evidence(row: &sys::bg_docking_rmsd_cluster_row_v1) -> Result<Fixed64ClusterEvidence> {
    Ok(Fixed64ClusterEvidence {
        slot_index: row.slot_index,
        status: row.status,
        cluster_eligible: bool_from_abi(row.cluster_eligible, "cluster eligibility")?,
        representative: bool_from_abi(row.representative, "cluster representative")?,
        top_k_representative: bool_from_abi(
            row.top_k_representative,
            "cluster Top-K representative",
        )?,
        stable_valid_rank: row.stable_valid_rank,
        cluster_id: row.cluster_id,
        representative_slot_index: row.representative_slot_index,
        cluster_rank: row.cluster_rank,
        top_k_rank: row.top_k_rank,
        cluster_size: row.cluster_size,
        direct_rmsd_to_representative_angstrom: row.direct_rmsd_to_representative_angstrom,
        coordinate_sha256: row.coordinate_sha256,
    })
}

fn pipeline_row(row: &sys::bg_docking_fixed64_pipeline_row_v1) -> Fixed64PipelineRow {
    Fixed64PipelineRow {
        slot_index: row.slot_index,
        producer_status: row.producer_status,
        producer_failure_code: row.producer_failure_code,
        initial_admission_decision: row.initial_admission_decision,
        requested_refinement_mode: row.requested_refinement_mode,
        effective_refinement_mode: row.effective_refinement_mode,
        refinement_status: row.refinement_status,
        refinement_failure_stage: row.refinement_failure_stage,
        scorer_status: row.scorer_status,
        scorer_failure_code: row.scorer_failure_code,
        validity_status: row.validity_status,
        validity_failure_code: row.validity_failure_code,
        stable_rank: row.stable_rank,
        stable_valid_rank: row.stable_valid_rank,
        cluster_status: row.cluster_status,
        cluster_id: row.cluster_id,
        cluster_rank: row.cluster_rank,
        top_k_rank: row.top_k_rank,
        producer_row_receipt_sha256: row.producer_row_receipt_sha256,
        final_coordinate_sha256: row.final_coordinate_sha256,
        refinement_evidence_sha256: row.refinement_evidence_sha256,
        scorer_evidence_sha256: row.scorer_evidence_sha256,
        validity_evidence_sha256: row.validity_evidence_sha256,
        ranking_evidence_sha256: row.ranking_evidence_sha256,
        cluster_evidence_sha256: row.cluster_evidence_sha256,
        row_receipt_sha256: row.row_receipt_sha256,
    }
}

fn assign_shared_identities(
    descriptor: &mut sys::bg_docking_geometric_admission_context_soa_v1,
    identities: Fixed64Identities,
) {
    descriptor.authority_input_receipt_sha256 = identities.authority_input_receipt_sha256;
    descriptor.receptor_system_sha256 = identities.receptor_system_sha256;
    descriptor.ligand_system_sha256 = identities.ligand_system_sha256;
    descriptor.backend_receipt_sha256 = identities.backend_receipt_sha256;
}
