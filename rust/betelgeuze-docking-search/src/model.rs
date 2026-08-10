use crate::{EvaluationError, SearchReceipt, Vec3};

pub const MAX_LIGAND_ATOMS: usize = 512;
pub const MAX_LIGAND_ANCHORS: usize = 256;
pub const MAX_RECEPTOR_ATOMS: usize = 65_536;
pub const MAX_SURFACE_SAMPLES: usize = 4_096;
pub const MAX_ANCHOR_COMBINATIONS: usize = 65_536;
/// Bounds the quadratic dual-anchor geometry comparison stage.
pub const MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS: usize = 4_096;
pub const MAX_ORIENTATIONS: usize = 512;
pub const MAX_GENERATED_CANDIDATES: usize = 65_536;
pub const MAX_REFINEMENT_STEPS: usize = 128;
pub const MAX_TOP_K: usize = 1_024;
/// Aggregate coordinate rows retained by the public candidate ledger.
pub const MAX_CANDIDATE_COORDINATES: usize = 4_000_000;
/// Conservative cap across pruning, refinement, and validity pair evaluations.
pub const MAX_PAIR_EVALUATIONS: usize = 250_000_000;
/// Maximum diagnostic bytes retained for one failed candidate.
pub const MAX_EVALUATION_DETAIL_BYTES: usize = 4_096;
/// Conservative aggregate candidate-row coordinate/metadata/diagnostic payload.
pub const MAX_LEDGER_PAYLOAD_BYTES: usize = 128 * 1_024 * 1_024;

/// Stable ligand anchor identity supplied by the caller.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct AnchorId(pub u32);

/// Stable receptor-surface identity supplied by the caller.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SurfaceId(pub u32);

/// Typed interaction chemistry used only to build compatible proposal slots.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[non_exhaustive]
pub enum AnchorKind {
    HydrogenBondDonor,
    HydrogenBondAcceptor,
    Hydrophobe,
    Aromatic,
    Positive,
    Negative,
}

impl AnchorKind {
    #[must_use]
    pub const fn is_compatible_with(self, other: Self) -> bool {
        matches!(
            (self, other),
            (Self::HydrogenBondDonor, Self::HydrogenBondAcceptor)
                | (Self::HydrogenBondAcceptor, Self::HydrogenBondDonor)
                | (Self::Hydrophobe, Self::Hydrophobe)
                | (Self::Aromatic, Self::Aromatic)
                | (Self::Positive, Self::Negative)
                | (Self::Negative, Self::Positive)
        )
    }
}

/// One ligand atom with canonical angstrom, kcal/mol, and elementary-charge units.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LigandAtom {
    pub position_angstrom: Vec3,
    pub vdw_radius_angstrom: f64,
    pub epsilon_kcal_per_mol: f64,
    pub charge_elementary: f64,
}

/// One typed ligand interaction anchor.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LigandAnchor {
    pub id: AnchorId,
    pub atom_index: usize,
    /// Direction from the ligand atom toward its prospective interaction.
    pub direction: Vec3,
    pub kind: AnchorKind,
}

/// One receptor atom used by pruning, local short-range energy, and clash validity.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ReceptorAtom {
    pub position_angstrom: Vec3,
    pub vdw_radius_angstrom: f64,
    pub epsilon_kcal_per_mol: f64,
    pub charge_elementary: f64,
}

/// An actual receptor surface location, outward normal, and typed interaction.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SurfaceSample {
    pub id: SurfaceId,
    pub position_angstrom: Vec3,
    pub outward_normal: Vec3,
    pub anchor_kind: AnchorKind,
}

/// Complete owned docking-search input. It contains no native/reference pose,
/// RMSD target, external-solver result, or benchmark-validity field.
#[derive(Clone, Debug, PartialEq)]
pub struct SearchInput {
    pub source_seed: [u8; 32],
    pub ligand_atoms: Vec<LigandAtom>,
    pub ligand_anchors: Vec<LigandAnchor>,
    pub receptor_atoms: Vec<ReceptorAtom>,
    pub surface_samples: Vec<SurfaceSample>,
}

impl SearchInput {
    /// SHA-256 over the canonical semantic input projection. Receptor, anchor,
    /// and surface row ordering is normalized; ligand atom order remains
    /// significant because anchor indices and pose coordinates use it.
    #[must_use]
    pub fn canonical_sha256(&self) -> [u8; 32] {
        crate::identity::input_sha256(self)
    }
}

/// Bounded stage budgets and numeric policy. Every count is allocated before
/// evaluator results are observed.
#[derive(Clone, Debug, PartialEq)]
pub struct SearchConfig {
    pub orientation_count: usize,
    pub generated_candidate_limit: usize,
    pub coarse_keep: usize,
    pub refinement_keep: usize,
    pub top_k: usize,
    pub placement_clearance_angstrom: f64,
    pub dual_anchor_distance_tolerance_angstrom: f64,
    pub coarse_clash_weight: f64,
    pub refinement_steps: usize,
    pub translation_step_angstrom2_per_kcal: f64,
    pub rotation_step_per_torque: f64,
    pub maximum_translation_step_angstrom: f64,
    pub maximum_rotation_step_radians: f64,
    pub maximum_absolute_coordinate_angstrom: f64,
    pub minimum_ligand_atom_distance_angstrom: f64,
    pub minimum_receptor_clearance_scale: f64,
    pub cluster_rmsd_angstrom: f64,
}

impl Default for SearchConfig {
    fn default() -> Self {
        Self {
            orientation_count: 24,
            generated_candidate_limit: 4_096,
            coarse_keep: 512,
            refinement_keep: 64,
            top_k: 10,
            placement_clearance_angstrom: 1.5,
            dual_anchor_distance_tolerance_angstrom: 0.75,
            coarse_clash_weight: 8.0,
            refinement_steps: 12,
            translation_step_angstrom2_per_kcal: 0.01,
            rotation_step_per_torque: 0.001,
            maximum_translation_step_angstrom: 0.25,
            maximum_rotation_step_radians: 0.12,
            maximum_absolute_coordinate_angstrom: 100_000.0,
            minimum_ligand_atom_distance_angstrom: 0.05,
            minimum_receptor_clearance_scale: 0.45,
            cluster_rmsd_angstrom: 1.0,
        }
    }
}

impl SearchConfig {
    /// SHA-256 over the frozen canonical binary configuration projection.
    #[must_use]
    pub fn canonical_sha256(&self) -> [u8; 32] {
        crate::identity::config_sha256(self)
    }
}

/// Whether a slot uses a geometrically consistent two-anchor constraint or the
/// explicit single-anchor fallback used only when no dual combination exists.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum PlacementMode {
    DualAnchor,
    SingleAnchorFallback,
}

/// Result-independent identity for one surface/anchor/orientation slot.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct CandidateKey {
    pub orientation_index: u32,
    pub primary_surface_id: SurfaceId,
    pub primary_ligand_anchor_id: AnchorId,
    pub secondary_surface_id: Option<SurfaceId>,
    pub secondary_ligand_anchor_id: Option<AnchorId>,
}

/// Final ledger state for one allocated proposal slot.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum CandidateStatus {
    CoarsePruned,
    DetailedPruned,
    RefinementFailed,
    PhysicalRejected,
    ClusterMember,
    ClusterRepresentative,
    TopK,
}

/// Machine-readable reason associated with non-Top-K ledger states.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum CandidateReason {
    CoarseBudget,
    DetailedBudget,
    EvaluatorFailure,
    NonFiniteEvaluation,
    NonFiniteCoordinate,
    CoordinateOutOfBounds,
    LigandSelfOverlap,
    ReceptorClash,
    ClusteredIntoRepresentative,
    TopKBudget,
}

/// One immutable public candidate-ledger row. Every allocated slot appears
/// exactly once, including pruned and failed candidates.
#[derive(Clone, Debug, PartialEq)]
pub struct CandidateRow {
    pub slot_index: usize,
    pub key: CandidateKey,
    pub placement_mode: PlacementMode,
    pub status: CandidateStatus,
    pub reason: Option<CandidateReason>,
    pub detail: Option<String>,
    pub coordinates_angstrom: Vec<Vec3>,
    pub anchor_fit_rmsd_angstrom: f64,
    pub coarse_score: Option<f64>,
    pub detailed_score: Option<f64>,
    pub energy_kcal_per_mol: Option<f64>,
    pub physically_valid: Option<bool>,
    pub minimum_receptor_gap_angstrom: Option<f64>,
    pub cluster_id: Option<usize>,
    pub final_rank: Option<usize>,
}

/// One representative after physical filtering and deterministic clustering.
#[derive(Clone, Debug, PartialEq)]
pub struct RankedPose {
    pub rank: usize,
    pub key: CandidateKey,
    pub coordinates_angstrom: Vec<Vec3>,
    pub energy_kcal_per_mol: f64,
    pub cluster_size: usize,
    pub minimum_receptor_gap_angstrom: Option<f64>,
}

/// Search poses plus an auditable denominator/budget receipt.
#[derive(Clone, Debug, PartialEq)]
pub struct SearchResult {
    pub candidate_rows: Vec<CandidateRow>,
    pub poses: Vec<RankedPose>,
    pub receipt: SearchReceipt,
}

impl SearchResult {
    /// Verify the candidate ledger digest and sealed receipt digest.
    #[must_use]
    pub fn has_valid_sha256(&self) -> bool {
        self.receipt.has_valid_sha256()
            && crate::identity::candidate_rows_sha256(&self.candidate_rows)
                == self.receipt.candidate_rows_sha256
            && crate::identity::poses_sha256(&self.poses) == self.receipt.poses_sha256
            && self.has_consistent_ledger()
    }

    fn has_consistent_ledger(&self) -> bool {
        if self.candidate_rows.len() != self.receipt.allocated_candidate_slot_count
            || self.poses.len() != self.receipt.returned_pose_count
            || self
                .candidate_rows
                .iter()
                .enumerate()
                .any(|(index, row)| row.slot_index != index)
        {
            return false;
        }
        if self.candidate_rows.iter().any(|row| {
            row.placement_mode != self.receipt.placement_mode || !row_state_is_consistent(row)
        }) {
            return false;
        }
        let status_count = |status| {
            self.candidate_rows
                .iter()
                .filter(|row| row.status == status)
                .count()
        };
        let reason_count = |reason| {
            self.candidate_rows
                .iter()
                .filter(|row| row.reason == Some(reason))
                .count()
        };
        let coarse_pruned = status_count(CandidateStatus::CoarsePruned);
        let detailed_pruned = status_count(CandidateStatus::DetailedPruned);
        let refinement_failed = status_count(CandidateStatus::RefinementFailed);
        let physical_rejected = status_count(CandidateStatus::PhysicalRejected);
        let physically_valid_count = self
            .candidate_rows
            .iter()
            .filter(|row| row.physically_valid == Some(true))
            .count();
        let clusters = self
            .candidate_rows
            .iter()
            .filter_map(|row| row.cluster_id)
            .collect::<std::collections::BTreeSet<_>>();
        let used_combinations = self
            .candidate_rows
            .iter()
            .map(|row| {
                (
                    row.key.primary_surface_id,
                    row.key.primary_ligand_anchor_id,
                    row.key.secondary_surface_id,
                    row.key.secondary_ligand_anchor_id,
                )
            })
            .collect::<std::collections::BTreeSet<_>>();
        if self.receipt.coarse_kept_count + coarse_pruned != self.candidate_rows.len()
            || self.receipt.refinement_selected_count + detailed_pruned
                != self.receipt.coarse_kept_count
            || self.receipt.refinement_succeeded_count + refinement_failed
                != self.receipt.refinement_selected_count
            || physically_valid_count + physical_rejected != self.receipt.refinement_succeeded_count
            || physically_valid_count != self.receipt.physical_valid_count
            || reason_count(CandidateReason::EvaluatorFailure)
                != self.receipt.refinement_evaluator_failed_count
            || reason_count(CandidateReason::NonFiniteEvaluation)
                != self.receipt.refinement_non_finite_failed_count
            || reason_count(CandidateReason::NonFiniteCoordinate)
                != self.receipt.rejected_non_finite_coordinate_count
            || reason_count(CandidateReason::CoordinateOutOfBounds)
                != self.receipt.rejected_coordinate_out_of_bounds_count
            || reason_count(CandidateReason::LigandSelfOverlap)
                != self.receipt.rejected_ligand_self_overlap_count
            || reason_count(CandidateReason::ReceptorClash)
                != self.receipt.rejected_receptor_clash_count
            || clusters.len() != self.receipt.cluster_count
            || used_combinations.len() != self.receipt.used_anchor_combination_count
            || status_count(CandidateStatus::TopK) != self.poses.len()
        {
            return false;
        }
        for (index, pose) in self.poses.iter().enumerate() {
            if pose.rank != index + 1 {
                return false;
            }
            let Some(row) = self
                .candidate_rows
                .iter()
                .find(|row| row.final_rank == Some(pose.rank))
            else {
                return false;
            };
            let Some(cluster_id) = row.cluster_id else {
                return false;
            };
            let cluster_size = self
                .candidate_rows
                .iter()
                .filter(|candidate| candidate.cluster_id == Some(cluster_id))
                .count();
            if row.status != CandidateStatus::TopK
                || row.key != pose.key
                || row.coordinates_angstrom != pose.coordinates_angstrom
                || row.energy_kcal_per_mol != Some(pose.energy_kcal_per_mol)
                || row.minimum_receptor_gap_angstrom != pose.minimum_receptor_gap_angstrom
                || cluster_size != pose.cluster_size
            {
                return false;
            }
        }
        true
    }
}

fn row_state_is_consistent(row: &CandidateRow) -> bool {
    let pruned_or_failed_common = row.energy_kcal_per_mol.is_none()
        && row.physically_valid.is_none()
        && row.cluster_id.is_none()
        && row.final_rank.is_none();
    match row.status {
        CandidateStatus::CoarsePruned => {
            row.reason == Some(CandidateReason::CoarseBudget)
                && row.coarse_score.is_some()
                && row.detailed_score.is_none()
                && row.detail.is_none()
                && pruned_or_failed_common
        }
        CandidateStatus::DetailedPruned => {
            row.reason == Some(CandidateReason::DetailedBudget)
                && row.coarse_score.is_some()
                && row.detailed_score.is_some()
                && row.detail.is_none()
                && pruned_or_failed_common
        }
        CandidateStatus::RefinementFailed => {
            matches!(
                row.reason,
                Some(CandidateReason::EvaluatorFailure | CandidateReason::NonFiniteEvaluation)
            ) && row.coarse_score.is_some()
                && row.detailed_score.is_some()
                && row.detail.is_some()
                && pruned_or_failed_common
        }
        CandidateStatus::PhysicalRejected => {
            matches!(
                row.reason,
                Some(
                    CandidateReason::NonFiniteCoordinate
                        | CandidateReason::CoordinateOutOfBounds
                        | CandidateReason::LigandSelfOverlap
                        | CandidateReason::ReceptorClash
                )
            ) && row.energy_kcal_per_mol.is_some()
                && row.physically_valid == Some(false)
                && row.cluster_id.is_none()
                && row.final_rank.is_none()
        }
        CandidateStatus::ClusterMember => {
            row.reason == Some(CandidateReason::ClusteredIntoRepresentative)
                && row.energy_kcal_per_mol.is_some()
                && row.physically_valid == Some(true)
                && row.cluster_id.is_some()
                && row.final_rank.is_none()
        }
        CandidateStatus::ClusterRepresentative => {
            row.reason == Some(CandidateReason::TopKBudget)
                && row.energy_kcal_per_mol.is_some()
                && row.physically_valid == Some(true)
                && row.cluster_id.is_some()
                && row.final_rank.is_none()
        }
        CandidateStatus::TopK => {
            row.reason.is_none()
                && row.energy_kcal_per_mol.is_some()
                && row.physically_valid == Some(true)
                && row.cluster_id.is_some()
                && row.final_rank.is_some()
        }
    }
}

/// Native potential-energy and analytic-force callback.
///
/// Implementations overwrite every output force. The search clears the buffer
/// before each call and rejects non-finite energy or force values.
pub trait EnergyForceEvaluator {
    fn energy_and_forces(
        &mut self,
        positions_angstrom: &[Vec3],
        forces_kcal_per_mol_angstrom: &mut [Vec3],
    ) -> Result<f64, EvaluationError>;
}

impl<F> EnergyForceEvaluator for F
where
    F: FnMut(&[Vec3], &mut [Vec3]) -> Result<f64, EvaluationError>,
{
    fn energy_and_forces(
        &mut self,
        positions_angstrom: &[Vec3],
        forces_kcal_per_mol_angstrom: &mut [Vec3],
    ) -> Result<f64, EvaluationError> {
        self(positions_angstrom, forces_kcal_per_mol_angstrom)
    }
}
