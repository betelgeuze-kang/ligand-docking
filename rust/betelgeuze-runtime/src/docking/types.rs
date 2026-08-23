use betelgeuze_docking_search::Fixed64FeatureKind as IndependentFixed64FeatureKind;
use betelgeuze_sys as sys;

use crate::PositionSoa;

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
