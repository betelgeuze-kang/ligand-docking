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

use betelgeuze_sys as sys;

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
    _context: &'context Context,
    backend: Backend,
    receptor_atom_count: usize,
    ligand_atom_count: usize,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    rotatable_child_atom_indices: Vec<u64>,
    validity_exclusion_count: u64,
    validity_chirality_count: u64,
    validity_contact_cell_size_angstrom: f64,
    validity_receptor_cells: HashMap<(i64, i64, i64), u64>,
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

impl<'context> Fixed64Pipeline<'context> {
    pub fn new(context: &'context Context, scientific: Fixed64PipelineContext<'_>) -> Result<Self> {
        let counts = scientific.validate()?;
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
        let validity_contact_cell_size_angstrom = validity.contact_cell_size_angstrom;
        let validity_receptor_cells = validity_receptor_cells(
            scientific.receptor.coordinates,
            validity_contact_cell_size_angstrom,
        )?;
        let rotatable_child_atom_indices = scientific.ligand.rotatable_child_atom_index.to_vec();

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
        Ok(Self {
            handle: handle.into_inner(),
            _context: context,
            backend,
            receptor_atom_count: receptor_count,
            ligand_atom_count: ligand_count,
            receptor_system_sha256: scientific.identities.receptor_system_sha256,
            ligand_system_sha256: scientific.identities.ligand_system_sha256,
            rotatable_child_atom_indices,
            validity_exclusion_count,
            validity_chirality_count,
            validity_contact_cell_size_angstrom,
            validity_receptor_cells,
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
        producer_input.pocket_normal = input.pocket_normal;

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
        validate_native_outputs(
            self.backend,
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
            [
                producer_x.as_slice(),
                producer_y.as_slice(),
                producer_z.as_slice(),
            ],
            &rigid_coordinates,
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
            &self.rotatable_child_atom_indices,
            self.validity_exclusion_count,
            self.validity_chirality_count,
            self.validity_contact_cell_size_angstrom,
            &self.validity_receptor_cells,
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
        // SAFETY: this object owns the non-null handle and destroys it once,
        // before the borrowed native Context can be dropped.
        unsafe { sys::bg_docking_fixed64_pipeline_v1_destroy(self.handle.as_ptr()) };
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

fn validate_producer_row_semantics(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
) -> Result<()> {
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
    if row.reserved0 != 0
        || !digest_present(&row.allocation_slot_receipt_sha256)
        || !allocation_verified
        || !geometric_verified
        || source_verified != source_digests_present
        || (!source_verified && !source_digests_zero)
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
                    (sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY
                        ..=sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT)
                        .contains(&row.component_failure_code)
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE => {
                    (sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION
                        ..=sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT)
                        .contains(&row.component_failure_code)
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE
                | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE
                | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_LIGAND_DENOMINATOR_MISMATCH
                | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE => {
                    row.component_failure_code == 0
                }
                _ => false,
            };
            if !valid_component_failure
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
    coordinates: &[Vec<f64>; 12],
    slot: usize,
    ligand_atom_count: u64,
) -> Result<()> {
    let baseline_duplicate =
        bool_from_abi(row.baseline_duplicate_of_v2, "rigid baseline duplicate")?;
    let clearance_evaluated = bool_from_abi(row.clearance_evaluated, "rigid clearance evaluation")?;
    let clearance_selected = bool_from_abi(row.clearance_selected, "rigid clearance selection")?;
    if row.slot_index as usize != slot
        || row.reserved0 != 0
        || row.reserved.iter().any(|item| *item != 0)
        || !rigid_evidence_is_consistent(&row.selected)?
        || !rigid_evidence_is_consistent(&row.comparison_v2)?
        || !rigid_evidence_is_consistent(&row.baseline_v3)?
        || !rigid_evidence_is_consistent(&row.clearance_v4)?
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

fn validate_torsion_evidence(
    rows: &[sys::bg_docking_torsion_v7_row_v1],
    moves: &[sys::bg_docking_torsion_v7_move_v1],
    rotatable_child_atom_indices: &[u64],
) -> Result<()> {
    let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
    if rows.len() != sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize
        || moves.len() != rows.len() * moves_per_slot
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion denominator is invalid",
        ));
    }
    for (slot, row) in rows.iter().enumerate() {
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
                    || !torsion_failure_evidence_is_zero(row)
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion typed failure retained optimization evidence",
                    ));
                }
            }
            sys::BG_DOCKING_TORSION_V7_ROW_REFINED => {
                if row.failure_code != sys::BG_DOCKING_TORSION_V7_FAILURE_NONE
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
                {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 torsion refinement evidence is inconsistent",
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

fn validate_refinement_evidence(
    rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    requested_modes: &[sys::bg_docking_rigid_refinement_candidate_mode],
    coordinates: [&[f64]; 3],
    quaternions: [&[f64]; 4],
    ligand_atom_count: u64,
) -> Result<()> {
    if rows.len() != rigid_rows.len()
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
                    || !coordinate_segment_matches(&coordinates, slot, ligand_atom_count, false)?
                    || !unit_quaternion(quaternion)
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
                    || !coordinate_segment_matches(&coordinates, slot, ligand_atom_count, true)?
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

#[allow(clippy::too_many_arguments)]
fn validate_native_outputs(
    backend: Backend,
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
    producer_coordinates: [&[f64]; 3],
    rigid_coordinates: &[Vec<f64>; 12],
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
    rmsd_threshold_angstrom: f64,
    rotatable_child_atom_indices: &[u64],
    validity_exclusion_count: u64,
    validity_chirality_count: u64,
    validity_contact_cell_size_angstrom: f64,
    validity_receptor_cells: &HashMap<(i64, i64, i64), u64>,
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
    if requested_modes.len() != candidate_count as usize
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
        let geometric = &row.geometric_admission;
        let evaluated = geometric.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
        let upstream_failure =
            geometric.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE;
        let rank_eligible = bool_from_abi(geometric.rank_eligible, "geometric rank eligibility")?;
        let accepted = geometric.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED;
        let penetration_rejected = geometric.decision
            == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED;
        if (evaluated
            && (geometric.ligand_atom_count != ligand_atom_count
                || geometric.receptor_atom_count != receptor_atom_count
                || geometric.exact_pair_count != expected_pair_count
                || (!accepted && !penetration_rejected)
                || rank_eligible != accepted))
            || (upstream_failure
                && (geometric.ligand_atom_count != 0
                    || geometric.receptor_atom_count != 0
                    || geometric.exact_pair_count != 0
                    || geometric.decision
                        != sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED
                    || rank_eligible))
            || (!evaluated && !upstream_failure)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 geometric atom or exact-pair denominator is invalid",
            ));
        }
        validate_producer_row_semantics(row, producer_coordinates, slot, ligand_atom_count)?;
    }
    for (slot, row) in rigid_rows.iter().enumerate() {
        validate_rigid_row_semantics(
            row,
            requested_modes[slot],
            rigid_coordinates,
            slot,
            ligand_atom_count,
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
    validate_torsion_evidence(torsion_rows, torsion_moves, rotatable_child_atom_indices)?;
    validate_refinement_evidence(
        refinement_rows,
        rigid_rows,
        torsion_rows,
        requested_modes,
        final_coordinates,
        final_quaternions,
        ligand_atom_count,
    )?;
    validate_scorer_and_validity_evidence(
        scorer_rows,
        validity_rows,
        ranking_rows,
        ligand_atom_count,
        receptor_atom_count,
        validity_exclusion_count,
        validity_chirality_count,
        validity_contact_cell_size_angstrom,
        validity_receptor_cells,
        final_coordinates,
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
        if row.slot_index as usize != slot
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
    for digest in [
        producer.allocation_inventory_sha256,
        producer.geometric_admission_batch_receipt_sha256,
        pipeline.allocation_receipt_sha256,
        pipeline.source_bundle_receipt_sha256,
        pipeline.admission_context_receipt_sha256,
        pipeline.refinement_context_receipt_sha256,
        pipeline.scorer_context_receipt_sha256,
        pipeline.validity_context_receipt_sha256,
        pipeline.component_binding_receipt_sha256,
        pipeline.producer_batch_receipt_sha256,
        pipeline.refinement_policy_receipt_sha256,
        pipeline.refinement_batch_receipt_sha256,
        pipeline.scorer_batch_receipt_sha256,
        pipeline.validity_batch_receipt_sha256,
        pipeline.ranking_batch_receipt_sha256,
        pipeline.cluster_batch_receipt_sha256,
        pipeline.pipeline_batch_receipt_sha256,
    ] {
        if !digest_present(&digest) {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 batch receipt is absent",
            ));
        }
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
    ligand_atom_count: u64,
    receptor_atom_count: u64,
    exclusion_count: u64,
    chirality_count: u64,
    contact_cell_size_angstrom: f64,
    receptor_cells: &HashMap<(i64, i64, i64), u64>,
    final_coordinates: [&[f64]; 3],
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    if scorer_rows.len() != candidate_count
        || validity_rows.len() != candidate_count
        || ranking_rows.len() != candidate_count
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
        if scorer.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED {
            let term_sum = scorer.weighted_terms.iter().copied().sum::<f64>();
            if scorer.failure_code != sys::BG_DOCKING_SCORER_V1_FAILURE_NONE
                || !scorer.total_score.is_finite()
                || scorer.weighted_terms.iter().any(|value| !value.is_finite())
                || (term_sum - scorer.total_score).abs() > 1.0e-12
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 scored row has invalid ScorerV1 term semantics",
                ));
            }
        } else if scorer.status != sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE
            || scorer.failure_code < sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED
            || scorer.failure_code > sys::BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE
            || !scorer_failure_rank_evidence_is_zero(scorer)
            || !scorer_failure_pair_evidence_is_valid(scorer)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 typed scorer failure retained invalid evidence",
            ));
        }
        if validity.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED {
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
        for channel in coordinates {
            let delta = channel[left_begin + atom] - channel[right_begin + atom];
            if !delta.is_finite() {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 RMSD coordinate delta is non-finite",
                ));
            }
            squared_sum += delta * delta;
        }
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
            if !row.direct_rmsd_to_representative_angstrom.is_finite()
                || row.direct_rmsd_to_representative_angstrom < 0.0
                || row.direct_rmsd_to_representative_angstrom > rmsd_threshold_angstrom + tolerance
                || (row.direct_rmsd_to_representative_angstrom - expected_rmsd).abs() > tolerance
                || (representative && row.direct_rmsd_to_representative_angstrom != 0.0)
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

    if top_k.len() > representatives.len() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 Top-K count exceeds the representative count",
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

    struct IndexFixture {
        ranking: sys::bg_docking_stable_top_k_output_v1,
        cluster: sys::bg_docking_rmsd_cluster_output_v1,
        scorer_rows: Vec<sys::bg_docking_scorer_v1_row_v1>,
        validity_rows: Vec<sys::bg_docking_pose_validity_row_v1>,
        ranking_rows: Vec<sys::bg_docking_stable_top_k_row_v1>,
        cluster_rows: Vec<sys::bg_docking_rmsd_cluster_row_v1>,
        primary_indices: Vec<u32>,
        valid_indices: Vec<u32>,
        representative_indices: Vec<u32>,
        top_k_indices: Vec<u32>,
        final_coordinates: [Vec<f64>; 3],
        receptor_cells: HashMap<(i64, i64, i64), u64>,
    }

    impl IndexFixture {
        fn valid() -> Self {
            let count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
            let mut scorer_rows = vec![zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1); count];
            let mut validity_rows =
                vec![zeroed_abi_value!(sys::bg_docking_pose_validity_row_v1); count];
            let mut ranking_rows =
                vec![zeroed_abi_value!(sys::bg_docking_stable_top_k_row_v1); count];
            let mut cluster_rows =
                vec![zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1); count];
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
            for (slot, score) in [(0_usize, 1.0_f64), (1, 2.0)] {
                scorer_rows[slot].status = sys::BG_DOCKING_SCORER_V1_ROW_SCORED;
                scorer_rows[slot].failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
                scorer_rows[slot].weighted_terms[0] = score;
                scorer_rows[slot].total_score = score;
                ranking_rows[slot].rank_eligible = 1;
                ranking_rows[slot].stable_rank = slot as u32 + 1;
                ranking_rows[slot].total_score = score;
                ranking_rows[slot].coordinate_sha256 = [slot as u8 + 1; 32];
            }
            validity_rows[0].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
            validity_rows[0].failure_code = sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
            validity_rows[0].upstream_scorer_failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            validity_rows[0].passed_check_mask = sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
            validity_rows[0].atom_count = 1;
            validity_rows[0].evaluated_receptor_ligand_pair_count = 1;
            validity_rows[0].element_vdw_receptor_candidate_pair_count = 1;
            validity_rows[0].element_vdw_receptor_full_cartesian_pair_count = 1;
            validity_rows[0].element_vdw_receptor_cell_count = 1;
            validity_rows[1].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
            validity_rows[1].failure_code = sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
            validity_rows[1].upstream_scorer_failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            validity_rows[1].blocker_mask = sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
            validity_rows[1].atom_count = 1;
            validity_rows[1].evaluated_receptor_ligand_pair_count = 1;
            validity_rows[1].element_vdw_receptor_candidate_pair_count = 1;
            validity_rows[1].element_vdw_receptor_full_cartesian_pair_count = 1;
            validity_rows[1].element_vdw_receptor_cell_count = 1;
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
                cluster_rows,
                primary_indices,
                valid_indices: vec![0; count],
                representative_indices: vec![0; count],
                top_k_indices: vec![0; sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize],
                final_coordinates: std::array::from_fn(|_| vec![0.0; count]),
                receptor_cells: HashMap::from([((0, 0, 0), 1)]),
            }
        }

        fn validate(&self) -> Result<()> {
            validate_scorer_and_validity_evidence(
                &self.scorer_rows,
                &self.validity_rows,
                &self.ranking_rows,
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
    }

    #[test]
    fn rejects_valid_rank_with_inconsistent_blocker_mask() {
        let mut fixture = IndexFixture::valid();
        fixture.validity_rows[0].blocker_mask =
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH;
        assert!(fixture.validate().is_err());
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
    }

    fn generated_producer_row() -> sys::bg_docking_fixed64_producer_row_v1 {
        let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
        row.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
        row.failure_code = sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE;
        row.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
        row.ligand_atom_count = 1;
        row.allocation_slot_receipt_sha256 = [1; 32];
        row.source_payload_receipt_sha256 = [2; 32];
        row.source_proposal_sha256 = [3; 32];
        row.source_coordinate_sha256 = [4; 32];
        row.placement_receipt_sha256 = [5; 32];
        row.output_proposal_sha256 = [6; 32];
        row.output_coordinate_sha256 = [7; 32];
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
        let valid = generated_producer_row();
        assert!(validate_producer_row_semantics(&valid, views, 0, 1).is_ok());

        let mut nonunit = generated_producer_row();
        nonunit.placement_quaternion_w = 0.5;
        assert!(validate_producer_row_semantics(&nonunit, views, 0, 1).is_err());

        let mut failure = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
        failure.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
        failure.failure_code = sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE;
        failure.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
        failure.ligand_atom_count = 1;
        failure.allocation_slot_receipt_sha256 = [1; 32];
        failure.allocation_identity_verified = 1;
        failure.geometric_identity_verified = 1;
        failure.denominator_preserved = 1;
        assert!(validate_producer_row_semantics(&failure, views, 0, 1).is_ok());
        failure.coordinates_available = 1;
        assert!(validate_producer_row_semantics(&failure, views, 0, 1).is_err());
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
            &coordinates,
            0,
            1,
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
        let validation = validate_torsion_evidence(&rows, &moves, &[5]);
        assert!(validation.is_ok(), "{validation:?}");

        let mut wrong_child = moves.clone();
        wrong_child[0].rotatable_child_atom_index = 6;
        assert!(validate_torsion_evidence(&rows, &wrong_child, &[5]).is_err());

        let mut outside_prefix = moves;
        outside_prefix[1].evaluated = 1;
        outside_prefix[1].rotatable_child_atom_index = 5;
        outside_prefix[1].delta_radians = 0.1;
        assert!(validate_torsion_evidence(&rows, &outside_prefix, &[5]).is_err());
    }

    struct RefinementFixture {
        rows: Vec<sys::bg_docking_fixed64_refinement_row_v1>,
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
        row.coordinate_sha256 = [1; 32];
        let rigid = valid_rigid_v2_row();
        let mut torsion = zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1);
        torsion.status = sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
        torsion.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE;
        RefinementFixture {
            rows: vec![row],
            rigid: vec![rigid],
            torsion: vec![torsion],
            coordinates: std::array::from_fn(|_| vec![0.0]),
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
            &fixture.rigid,
            &fixture.torsion,
            &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
            coordinate_views,
            quaternion_views,
            1,
        )
        .is_ok());

        fixture.rows[0].coordinate_available = 0;
        assert!(validate_refinement_evidence(
            &fixture.rows,
            &fixture.rigid,
            &fixture.torsion,
            &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
            coordinate_views,
            quaternion_views,
            1,
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
