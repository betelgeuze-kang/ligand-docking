use betelgeuze_docking_search::Fixed64FeatureKind as IndependentFixed64FeatureKind;
use betelgeuze_sys as sys;

use crate::{Backend, PositionSoa, UnitSystem};

pub type Sha256 = [u8; 32];
pub const FIXED64_NATIVE_PIPELINE_PROFILE_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0";
pub(super) const FIXED64_NATIVE_COMPONENT_BINDING_PROFILE_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0";

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
    pub(super) const fn as_raw(self) -> sys::bg_docking_fixed64_feature_kind {
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

    pub(super) const fn as_independent(self) -> IndependentFixed64FeatureKind {
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
    pub(super) const fn as_raw(self) -> sys::bg_docking_rigid_refinement_candidate_mode {
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

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64GeometricEvidence {
    pub slot_index: u32,
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
    pub post_admission_status: i32,
    pub post_admission_failure_code: i32,
    pub post_admission_decision: i32,
    pub post_admission_rank_eligible: bool,
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
    pub post_admission_row_receipt_sha256: Sha256,
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
    pub post_admission_policy_receipt_sha256: Sha256,
    pub post_admission_batch_receipt_sha256: Sha256,
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
    pub post_admitted_count: u64,
    pub post_rejected_count: u64,
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
    pub post_admission_rows: Vec<Fixed64GeometricEvidence>,
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
    pub scientific_projection_sha256: Sha256,
}
