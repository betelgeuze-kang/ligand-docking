use crate::model::{
    AnchorKind, CandidateKey, CandidateReason, CandidateRow, CandidateStatus, PlacementMode,
    RankedPose, SearchConfig, SearchInput,
};
use crate::receipt::SearchReceipt;
use crate::sha256::Sha256;
use crate::short_range::ShortRangeConfig;
use crate::surface::Candidate;
use crate::Orientation;

struct CanonicalSha256 {
    hasher: Sha256,
}

impl CanonicalSha256 {
    fn new(domain: &str) -> Self {
        let mut value = Self {
            hasher: Sha256::new(),
        };
        value.string(domain);
        value
    }

    fn byte(&mut self, value: u8) {
        self.hasher.update(&[value]);
    }

    fn bool(&mut self, value: bool) {
        self.byte(u8::from(value));
    }

    fn u32(&mut self, value: u32) {
        self.hasher.update(&value.to_be_bytes());
    }

    fn u64(&mut self, value: u64) {
        self.hasher.update(&value.to_be_bytes());
    }

    fn usize(&mut self, value: usize) {
        self.u64(u64::try_from(value).expect("bounded search count fits u64"));
    }

    fn f64(&mut self, value: f64) {
        self.u64(canonical_f64(value).to_bits());
    }

    fn bytes(&mut self, value: &[u8]) {
        self.usize(value.len());
        self.hasher.update(value);
    }

    fn string(&mut self, value: &str) {
        self.bytes(value.as_bytes());
    }

    fn fixed_sha256(&mut self, value: [u8; 32]) {
        self.hasher.update(&value);
    }

    fn finish(self) -> [u8; 32] {
        self.hasher.finalize()
    }
}

pub(crate) fn config_sha256(config: &SearchConfig) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_search_config/canonical-v2");
    hash.usize(config.orientation_count);
    hash.usize(config.generated_candidate_limit);
    hash.usize(config.coarse_keep);
    hash.usize(config.refinement_keep);
    hash.usize(config.top_k);
    hash.f64(config.placement_clearance_angstrom);
    hash.f64(config.dual_anchor_distance_tolerance_angstrom);
    hash.f64(config.coarse_clash_weight);
    hash.usize(config.refinement_steps);
    hash.f64(config.translation_step_angstrom2_per_kcal);
    hash.f64(config.rotation_step_per_torque);
    hash.f64(config.maximum_translation_step_angstrom);
    hash.f64(config.maximum_rotation_step_radians);
    hash.f64(config.maximum_absolute_coordinate_angstrom);
    hash.f64(config.minimum_ligand_atom_distance_angstrom);
    hash.f64(config.minimum_receptor_clearance_scale);
    hash.f64(config.cluster_rmsd_angstrom);
    hash.finish()
}

pub(crate) fn input_sha256(input: &SearchInput) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_search_input/canonical-v2");
    hash.fixed_sha256(input.source_seed);
    hash.usize(input.ligand_atoms.len());
    for atom in &input.ligand_atoms {
        vector(&mut hash, atom.position_angstrom);
        hash.f64(atom.vdw_radius_angstrom);
        hash.f64(atom.epsilon_kcal_per_mol);
        hash.f64(atom.charge_elementary);
    }
    let mut anchors = input.ligand_anchors.clone();
    anchors.sort_by_key(|anchor| anchor.id);
    hash.usize(anchors.len());
    for anchor in anchors {
        hash.u32(anchor.id.0);
        hash.usize(anchor.atom_index);
        direction(&mut hash, anchor.direction);
        anchor_kind(&mut hash, anchor.kind);
    }
    let mut receptor_atoms = input.receptor_atoms.clone();
    receptor_atoms.sort_by(|left, right| {
        canonical_f64(left.position_angstrom.x)
            .total_cmp(&canonical_f64(right.position_angstrom.x))
            .then_with(|| {
                canonical_f64(left.position_angstrom.y)
                    .total_cmp(&canonical_f64(right.position_angstrom.y))
            })
            .then_with(|| {
                canonical_f64(left.position_angstrom.z)
                    .total_cmp(&canonical_f64(right.position_angstrom.z))
            })
            .then_with(|| {
                canonical_f64(left.vdw_radius_angstrom)
                    .total_cmp(&canonical_f64(right.vdw_radius_angstrom))
            })
            .then_with(|| {
                canonical_f64(left.epsilon_kcal_per_mol)
                    .total_cmp(&canonical_f64(right.epsilon_kcal_per_mol))
            })
            .then_with(|| {
                canonical_f64(left.charge_elementary)
                    .total_cmp(&canonical_f64(right.charge_elementary))
            })
    });
    hash.usize(receptor_atoms.len());
    for atom in receptor_atoms {
        vector(&mut hash, atom.position_angstrom);
        hash.f64(atom.vdw_radius_angstrom);
        hash.f64(atom.epsilon_kcal_per_mol);
        hash.f64(atom.charge_elementary);
    }
    let mut surfaces = input.surface_samples.clone();
    surfaces.sort_by_key(|surface| surface.id);
    hash.usize(surfaces.len());
    for surface in surfaces {
        hash.u32(surface.id.0);
        vector(&mut hash, surface.position_angstrom);
        direction(&mut hash, surface.outward_normal);
        anchor_kind(&mut hash, surface.anchor_kind);
    }
    hash.finish()
}

pub(crate) fn short_range_config_sha256(config: ShortRangeConfig) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.short_range_config/canonical-v1");
    hash.f64(config.ligand_shape_force_constant_kcal_per_mol_angstrom2);
    hash.f64(config.cutoff_angstrom);
    hash.f64(config.switch_start_angstrom);
    hash.f64(config.softcore_angstrom);
    hash.f64(config.dielectric);
    hash.finish()
}

pub(crate) fn orientation_sha256(orientations: &[Orientation]) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_orientation_prefix/canonical-v2");
    hash.usize(orientations.len());
    for orientation in orientations {
        hash.u32(orientation.orientation_index);
        hash.u64(orientation.raw_sequence_index);
        hash.f64(orientation.quaternion.x);
        hash.f64(orientation.quaternion.y);
        hash.f64(orientation.quaternion.z);
        hash.f64(orientation.quaternion.w);
    }
    hash.finish()
}

pub(crate) fn allocation_sha256(candidates: &[Candidate]) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_candidate_allocation/canonical-v2");
    hash.usize(candidates.len());
    for candidate in candidates {
        hash.usize(candidate.slot_index);
        candidate_key(&mut hash, candidate.key);
        placement_mode(&mut hash, candidate.placement_mode);
    }
    hash.finish()
}

pub(crate) fn candidate_rows_sha256(rows: &[CandidateRow]) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_candidate_rows/canonical-v2");
    hash.usize(rows.len());
    for row in rows {
        hash.usize(row.slot_index);
        candidate_key(&mut hash, row.key);
        placement_mode(&mut hash, row.placement_mode);
        candidate_status(&mut hash, row.status);
        option_reason(&mut hash, row.reason);
        option_string(&mut hash, row.detail.as_deref());
        hash.usize(row.coordinates_angstrom.len());
        for coordinate in &row.coordinates_angstrom {
            hash.f64(coordinate.x);
            hash.f64(coordinate.y);
            hash.f64(coordinate.z);
        }
        hash.f64(row.anchor_fit_rmsd_angstrom);
        option_f64(&mut hash, row.coarse_score);
        option_f64(&mut hash, row.detailed_score);
        option_f64(&mut hash, row.energy_kcal_per_mol);
        option_bool(&mut hash, row.physically_valid);
        option_f64(&mut hash, row.minimum_receptor_gap_angstrom);
        option_usize(&mut hash, row.cluster_id);
        option_usize(&mut hash, row.final_rank);
    }
    hash.finish()
}

pub(crate) fn poses_sha256(poses: &[RankedPose]) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_ranked_poses/canonical-v2");
    hash.usize(poses.len());
    for pose in poses {
        hash.usize(pose.rank);
        candidate_key(&mut hash, pose.key);
        hash.usize(pose.coordinates_angstrom.len());
        for coordinate in &pose.coordinates_angstrom {
            vector(&mut hash, *coordinate);
        }
        hash.f64(pose.energy_kcal_per_mol);
        hash.usize(pose.cluster_size);
        option_f64(&mut hash, pose.minimum_receptor_gap_angstrom);
    }
    hash.finish()
}

pub(crate) fn receipt_sha256(receipt: &SearchReceipt) -> [u8; 32] {
    let mut hash = CanonicalSha256::new("betelgeuze.docking_search_receipt/canonical-v2");
    hash.string(receipt.schema_id);
    hash.string(receipt.evaluator_id);
    hash.fixed_sha256(receipt.evaluator_config_sha256);
    hash.fixed_sha256(receipt.config_sha256);
    hash.fixed_sha256(receipt.input_sha256);
    hash.bool(receipt.result_independent_allocation);
    placement_mode(&mut hash, receipt.placement_mode);
    hash.usize(receipt.requested_orientation_count);
    hash.usize(receipt.accepted_orientation_count);
    hash.u64(receipt.raw_orientation_attempt_count);
    hash.usize(receipt.compatible_single_anchor_pair_count);
    hash.usize(receipt.compatible_dual_anchor_combination_count);
    hash.usize(receipt.used_anchor_combination_count);
    hash.u64(receipt.possible_candidate_slot_count);
    hash.usize(receipt.generated_candidate_limit);
    hash.usize(receipt.allocated_candidate_slot_count);
    hash.fixed_sha256(receipt.allocation_sha256);
    hash.fixed_sha256(receipt.orientation_sha256);
    hash.fixed_sha256(receipt.candidate_rows_sha256);
    hash.fixed_sha256(receipt.poses_sha256);
    hash.usize(receipt.coarse_keep_budget);
    hash.usize(receipt.coarse_kept_count);
    hash.usize(receipt.refinement_keep_budget);
    hash.usize(receipt.refinement_selected_count);
    hash.usize(receipt.refinement_steps_per_candidate);
    hash.usize(receipt.refinement_succeeded_count);
    hash.usize(receipt.refinement_evaluator_failed_count);
    hash.usize(receipt.refinement_non_finite_failed_count);
    hash.usize(receipt.evaluator_call_count);
    hash.usize(receipt.maximum_evaluator_call_count);
    hash.usize(receipt.physical_valid_count);
    hash.usize(receipt.rejected_non_finite_coordinate_count);
    hash.usize(receipt.rejected_coordinate_out_of_bounds_count);
    hash.usize(receipt.rejected_ligand_self_overlap_count);
    hash.usize(receipt.rejected_receptor_clash_count);
    hash.usize(receipt.cluster_count);
    hash.usize(receipt.top_k_budget);
    hash.usize(receipt.returned_pose_count);
    hash.finish()
}

fn candidate_key(hash: &mut CanonicalSha256, key: CandidateKey) {
    hash.u32(key.orientation_index);
    hash.u32(key.primary_surface_id.0);
    hash.u32(key.primary_ligand_anchor_id.0);
    option_u32(hash, key.secondary_surface_id.map(|value| value.0));
    option_u32(hash, key.secondary_ligand_anchor_id.map(|value| value.0));
}

fn vector(hash: &mut CanonicalSha256, value: crate::Vec3) {
    hash.f64(value.x);
    hash.f64(value.y);
    hash.f64(value.z);
}

fn direction(hash: &mut CanonicalSha256, value: crate::Vec3) {
    // A max-component projection identifies direction independently of positive
    // scale using only basic binary64 arithmetic.  Do not use `hypot` here:
    // Rust/libc and CPython intentionally use different correctly-rounded norm
    // algorithms, which made otherwise identical ABI inputs hash differently.
    // Search validation rejects invalid directions before a receipt is built;
    // retaining `value` keeps the standalone identity method total for them.
    let maximum = value.x.abs().max(value.y.abs()).max(value.z.abs());
    let canonical = if value.is_finite() && maximum > 1.0e-12 {
        value.scale(1.0 / maximum)
    } else {
        value
    };
    vector(hash, canonical);
}

fn canonical_f64(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

fn anchor_kind(hash: &mut CanonicalSha256, value: AnchorKind) {
    hash.byte(match value {
        AnchorKind::HydrogenBondDonor => 0,
        AnchorKind::HydrogenBondAcceptor => 1,
        AnchorKind::Hydrophobe => 2,
        AnchorKind::Aromatic => 3,
        AnchorKind::Positive => 4,
        AnchorKind::Negative => 5,
    });
}

fn placement_mode(hash: &mut CanonicalSha256, value: PlacementMode) {
    hash.byte(match value {
        PlacementMode::DualAnchor => 0,
        PlacementMode::SingleAnchorFallback => 1,
    });
}

fn candidate_status(hash: &mut CanonicalSha256, value: CandidateStatus) {
    hash.byte(match value {
        CandidateStatus::CoarsePruned => 0,
        CandidateStatus::DetailedPruned => 1,
        CandidateStatus::RefinementFailed => 2,
        CandidateStatus::PhysicalRejected => 3,
        CandidateStatus::ClusterMember => 4,
        CandidateStatus::ClusterRepresentative => 5,
        CandidateStatus::TopK => 6,
    });
}

fn option_reason(hash: &mut CanonicalSha256, value: Option<CandidateReason>) {
    if let Some(reason) = value {
        hash.byte(1);
        hash.byte(match reason {
            CandidateReason::CoarseBudget => 0,
            CandidateReason::DetailedBudget => 1,
            CandidateReason::EvaluatorFailure => 2,
            CandidateReason::NonFiniteEvaluation => 3,
            CandidateReason::NonFiniteCoordinate => 4,
            CandidateReason::CoordinateOutOfBounds => 5,
            CandidateReason::LigandSelfOverlap => 6,
            CandidateReason::ReceptorClash => 7,
            CandidateReason::ClusteredIntoRepresentative => 8,
            CandidateReason::TopKBudget => 9,
        });
    } else {
        hash.byte(0);
    }
}

fn option_u32(hash: &mut CanonicalSha256, value: Option<u32>) {
    if let Some(value) = value {
        hash.byte(1);
        hash.u32(value);
    } else {
        hash.byte(0);
    }
}

fn option_usize(hash: &mut CanonicalSha256, value: Option<usize>) {
    if let Some(value) = value {
        hash.byte(1);
        hash.usize(value);
    } else {
        hash.byte(0);
    }
}

fn option_f64(hash: &mut CanonicalSha256, value: Option<f64>) {
    if let Some(value) = value {
        hash.byte(1);
        hash.f64(value);
    } else {
        hash.byte(0);
    }
}

fn option_bool(hash: &mut CanonicalSha256, value: Option<bool>) {
    if let Some(value) = value {
        hash.byte(1);
        hash.bool(value);
    } else {
        hash.byte(0);
    }
}

fn option_string(hash: &mut CanonicalSha256, value: Option<&str>) {
    if let Some(value) = value {
        hash.byte(1);
        hash.string(value);
    } else {
        hash.byte(0);
    }
}
