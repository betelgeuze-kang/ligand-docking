//! Source-bound native construction of the exact 512-row sampling-funnel pool.
//!
//! Every generated row contains coordinates produced here from the owned search
//! input. No result, score, native pose, RMSD, or caller-supplied proposal
//! coordinate enters this path.

use std::fmt;

use crate::anchors::compatible_anchor_inventory;
use crate::geometry::centroid;
use crate::native_hash::CanonicalHash;
use crate::search::validate_input;
use crate::surface::{place_candidates, Candidate};
use crate::{
    evaluate_fixed64_geometric_metrics, materialize_native_sampling_funnel_preselected_batch,
    native_fixed64_coordinate_sha256, orientations, run_native_sampling_funnel,
    Fixed64GeometricInput, NativeSamplingFunnelCandidate, NativeSamplingFunnelCandidateState,
    NativeSamplingFunnelLane, NativeSamplingFunnelPayloadBatch, NativeSamplingFunnelPayloadRow,
    NativeSamplingFunnelPreselectedBatch, NativeSamplingFunnelReceipt, PlacementMode, Quaternion,
    SearchConfig, SearchInput, Vec3, FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    FIXED64_MAX_RECEPTOR_ATOMS, NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION,
    NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR,
};

pub const NATIVE_SAMPLING_POOL_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_sampling_pool/1.0.0";
pub const NATIVE_SAMPLING_POOL_PROFILE_ID: &str =
    "engine_v2_source_bound_four_lane_512_producer_v1";
pub const NATIVE_SAMPLING_POOL_LANE_DENOMINATOR: usize = 128;
pub const NATIVE_SAMPLING_POOL_PLACEMENT_CLEARANCE_ANGSTROM: f64 = 1.5;
pub const NATIVE_SAMPLING_POOL_DUAL_ANCHOR_TOLERANCE_ANGSTROM: f64 = 0.75;
pub const NATIVE_SAMPLING_POOL_MULTI_ANCHOR_UNAVAILABLE: &str =
    "multi_anchor_compatible_combination_unavailable";
pub const NATIVE_SAMPLING_POOL_SHAPE_PENALTY_ID: &str = "penetrating_ligand_receptor_pair_fraction";
pub const NATIVE_SAMPLING_POOL_ANCHOR_PENALTY_ID: &str =
    "half_one_minus_mean_alignment_cosine_plus_fit_over_dual_tolerance";
pub const NATIVE_SAMPLING_POOL_EMBEDDING_ID: &str =
    "placed_centroid_xyz_angstrom_plus_canonical_quaternion_xyzw";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeSamplingPoolErrorCode {
    InvalidInput,
    InputCrossWired,
    PairBudgetExceeded,
    GenerationFailed,
    InternalInvariant,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NativeSamplingPoolError {
    code: NativeSamplingPoolErrorCode,
    message: String,
}

impl NativeSamplingPoolError {
    fn new(code: NativeSamplingPoolErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }

    #[must_use]
    pub const fn code(&self) -> NativeSamplingPoolErrorCode {
        self.code
    }

    #[must_use]
    pub fn message(&self) -> &str {
        &self.message
    }
}

impl fmt::Display for NativeSamplingPoolError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native sampling pool: {}", self.message)
    }
}

impl std::error::Error for NativeSamplingPoolError {}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeSamplingPoolBatch {
    source_sha256: [u8; 32],
    search_input_sha256: [u8; 32],
    geometric_input_sha256: [u8; 32],
    ligand_atom_count: usize,
    receptor_atom_count: usize,
    exact_pair_evaluation_count: usize,
    funnel: NativeSamplingFunnelReceipt,
    payloads: NativeSamplingFunnelPayloadBatch,
    preselected: NativeSamplingFunnelPreselectedBatch,
    receipt_sha256: [u8; 32],
}

impl NativeSamplingPoolBatch {
    #[must_use]
    pub const fn source_sha256(&self) -> [u8; 32] {
        self.source_sha256
    }

    #[must_use]
    pub const fn search_input_sha256(&self) -> [u8; 32] {
        self.search_input_sha256
    }

    #[must_use]
    pub const fn geometric_input_sha256(&self) -> [u8; 32] {
        self.geometric_input_sha256
    }

    #[must_use]
    pub const fn exact_pair_evaluation_count(&self) -> usize {
        self.exact_pair_evaluation_count
    }

    #[must_use]
    pub const fn ligand_atom_count(&self) -> usize {
        self.ligand_atom_count
    }

    #[must_use]
    pub const fn receptor_atom_count(&self) -> usize {
        self.receptor_atom_count
    }

    #[must_use]
    pub const fn funnel(&self) -> &NativeSamplingFunnelReceipt {
        &self.funnel
    }

    #[must_use]
    pub const fn payloads(&self) -> &NativeSamplingFunnelPayloadBatch {
        &self.payloads
    }

    #[must_use]
    pub const fn preselected(&self) -> &NativeSamplingFunnelPreselectedBatch {
        &self.preselected
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn fresh_128_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn benchmark_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn product_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn scientific_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn reservation_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn stage0_admission_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn hip_device_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn performance_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn rank_mutation_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let generated_candidate_count = self
            .funnel
            .candidates()
            .iter()
            .filter(|candidate| {
                matches!(
                    candidate.state(),
                    NativeSamplingFunnelCandidateState::Generated(_)
                )
            })
            .count();
        let expected_pair_evaluation_count = self
            .ligand_atom_count
            .checked_mul(self.receptor_atom_count)
            .and_then(|count| count.checked_mul(generated_candidate_count));
        self.source_sha256 != [0; 32]
            && self.search_input_sha256 != [0; 32]
            && self.geometric_input_sha256 != [0; 32]
            && self.ligand_atom_count == self.payloads.ligand_atom_count()
            && self.receptor_atom_count > 0
            && self.receptor_atom_count <= FIXED64_MAX_RECEPTOR_ATOMS
            && expected_pair_evaluation_count == Some(self.exact_pair_evaluation_count)
            && self.exact_pair_evaluation_count <= FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS
            && self.funnel.has_valid_receipt()
            && self.payloads.has_valid_receipt()
            && self.preselected.has_valid_receipt()
            && self
                .preselected
                .verifies_against(&self.funnel, &self.payloads)
            && self.payloads.ligand_system_sha256() == self.source_sha256
            && sampling_pool_receipt_sha256(self) == self.receipt_sha256
    }

    #[must_use]
    pub fn verifies_against(
        &self,
        input: &SearchInput,
        geometric_input: &Fixed64GeometricInput,
    ) -> bool {
        produce_native_sampling_pool(input, geometric_input).is_ok_and(|derived| derived == *self)
    }
}

/// Construct, geometrically observe, select, and materialize the four fixed
/// 128-row lanes. The producer seed is derived from both complete input
/// receipts; callers cannot inject an unrelated orientation seed.
pub fn produce_native_sampling_pool(
    input: &SearchInput,
    geometric_input: &Fixed64GeometricInput,
) -> Result<NativeSamplingPoolBatch, NativeSamplingPoolError> {
    let placement_config = SearchConfig {
        orientation_count: NATIVE_SAMPLING_POOL_LANE_DENOMINATOR,
        generated_candidate_limit: NATIVE_SAMPLING_POOL_LANE_DENOMINATOR,
        coarse_keep: NATIVE_SAMPLING_POOL_LANE_DENOMINATOR,
        refinement_keep: NATIVE_SAMPLING_POOL_LANE_DENOMINATOR,
        top_k: 1,
        placement_clearance_angstrom: NATIVE_SAMPLING_POOL_PLACEMENT_CLEARANCE_ANGSTROM,
        dual_anchor_distance_tolerance_angstrom:
            NATIVE_SAMPLING_POOL_DUAL_ANCHOR_TOLERANCE_ANGSTROM,
        ..SearchConfig::default()
    };
    validate_input(input, &placement_config)
        .map_err(|error| invalid(format!("search input is invalid: {error}")))?;
    validate_crosswire(input, geometric_input)?;

    let search_input_sha256 = input.canonical_sha256();
    let geometric_input_sha256 = geometric_input.receipt_sha256();
    let source_sha256 = source_sha256(search_input_sha256, geometric_input_sha256);
    let orientation_seed = orientation_seed_sha256(source_sha256);
    let orientation_values = orientations(orientation_seed, NATIVE_SAMPLING_POOL_LANE_DENOMINATOR)
        .map_err(|error| generation(format!("orientation generation failed: {error}")))?;
    let source_coordinates = input
        .ligand_atoms
        .iter()
        .map(|atom| atom.position_angstrom)
        .collect::<Vec<_>>();
    let source_centroid = centroid(&source_coordinates);

    let inventory = compatible_anchor_inventory(input, &placement_config)
        .map_err(|error| generation(format!("anchor inventory failed: {error}")))?;
    let generated_candidate_count = 3 * NATIVE_SAMPLING_POOL_LANE_DENOMINATOR
        + usize::from(!inventory.duals.is_empty()) * NATIVE_SAMPLING_POOL_LANE_DENOMINATOR;
    let exact_pair_evaluation_count = input
        .ligand_atoms
        .len()
        .checked_mul(input.receptor_atoms.len())
        .and_then(|count| count.checked_mul(generated_candidate_count))
        .ok_or_else(|| pair_budget("sampling-pool pair count overflowed"))?;
    if exact_pair_evaluation_count > FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS {
        return Err(pair_budget(format!(
            "sampling-pool pair count {exact_pair_evaluation_count} exceeds {FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS}"
        )));
    }
    let single_candidates = place_candidates(
        input,
        &placement_config,
        &orientation_values,
        &inventory.singles,
        PlacementMode::SingleAnchorFallback,
    )
    .map_err(|error| generation(format!("single-anchor placement failed: {error}")))?;
    let multi_candidates = if inventory.duals.is_empty() {
        Vec::new()
    } else {
        place_candidates(
            input,
            &placement_config,
            &orientation_values,
            &inventory.duals,
            PlacementMode::DualAnchor,
        )
        .map_err(|error| generation(format!("multi-anchor placement failed: {error}")))?
    };
    if single_candidates.len() != NATIVE_SAMPLING_POOL_LANE_DENOMINATOR
        || (!multi_candidates.is_empty()
            && multi_candidates.len() != NATIVE_SAMPLING_POOL_LANE_DENOMINATOR)
    {
        return Err(internal("anchor placement did not fill its fixed lane"));
    }

    let mut surfaces = input.surface_samples.iter().collect::<Vec<_>>();
    surfaces.sort_by_key(|surface| surface.id);
    let mut candidates = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR);
    let mut payload_rows = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR);
    for (local_index, orientation) in orientation_values.iter().copied().enumerate() {
        let coordinates = rotate_centered_to(
            &source_coordinates,
            source_centroid,
            orientation.quaternion,
            geometric_input.pocket_center_angstrom(),
        );
        push_generated(
            &mut candidates,
            &mut payload_rows,
            NativeSamplingFunnelLane::UniformSo3,
            local_index,
            source_sha256,
            coordinates,
            orientation.quaternion,
            0.0,
            geometric_input,
        )?;
    }
    for (local_index, orientation) in orientation_values.iter().copied().enumerate() {
        let surface = surfaces[local_index % surfaces.len()];
        let normal = surface
            .outward_normal
            .normalized("sampling-pool surface normal")
            .map_err(|error| generation(format!("surface normalization failed: {error}")))?;
        let target = surface
            .position_angstrom
            .plus(normal.scale(NATIVE_SAMPLING_POOL_PLACEMENT_CLEARANCE_ANGSTROM));
        let coordinates = rotate_centered_to(
            &source_coordinates,
            source_centroid,
            orientation.quaternion,
            target,
        );
        push_generated(
            &mut candidates,
            &mut payload_rows,
            NativeSamplingFunnelLane::PocketSurface,
            local_index,
            source_sha256,
            coordinates,
            orientation.quaternion,
            0.0,
            geometric_input,
        )?;
    }
    for (local_index, candidate) in single_candidates.iter().enumerate() {
        push_anchor_generated(
            &mut candidates,
            &mut payload_rows,
            NativeSamplingFunnelLane::SingleAnchor,
            local_index,
            source_sha256,
            candidate,
            geometric_input,
        )?;
    }
    if multi_candidates.is_empty() {
        for local_index in 0..NATIVE_SAMPLING_POOL_LANE_DENOMINATOR {
            let pool_index = lane_pool_index(NativeSamplingFunnelLane::MultiAnchor, local_index);
            candidates.push(
                NativeSamplingFunnelCandidate::typed_failure(
                    pool_index,
                    NativeSamplingFunnelLane::MultiAnchor,
                    NATIVE_SAMPLING_POOL_MULTI_ANCHOR_UNAVAILABLE,
                )
                .map_err(|error| generation(format!("typed failure row failed: {error}")))?,
            );
            payload_rows.push(
                NativeSamplingFunnelPayloadRow::typed_failure(pool_index)
                    .map_err(|error| generation(format!("typed payload row failed: {error}")))?,
            );
        }
    } else {
        for (local_index, candidate) in multi_candidates.iter().enumerate() {
            push_anchor_generated(
                &mut candidates,
                &mut payload_rows,
                NativeSamplingFunnelLane::MultiAnchor,
                local_index,
                source_sha256,
                candidate,
                geometric_input,
            )?;
        }
    }

    let funnel = run_native_sampling_funnel(candidates)
        .map_err(|error| generation(format!("sampling funnel failed: {error}")))?;
    let payloads = NativeSamplingFunnelPayloadBatch::new(
        input.ligand_atoms.len(),
        source_sha256,
        payload_rows,
    )
    .map_err(|error| generation(format!("payload materialization failed: {error}")))?;
    let preselected = materialize_native_sampling_funnel_preselected_batch(&funnel, &payloads)
        .map_err(|error| generation(format!("preselection materialization failed: {error}")))?;
    let mut value = NativeSamplingPoolBatch {
        source_sha256,
        search_input_sha256,
        geometric_input_sha256,
        ligand_atom_count: input.ligand_atoms.len(),
        receptor_atom_count: input.receptor_atoms.len(),
        exact_pair_evaluation_count,
        funnel,
        payloads,
        preselected,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = sampling_pool_receipt_sha256(&value);
    if !value.has_valid_receipt() {
        return Err(internal("sampling-pool receipt did not self-verify"));
    }
    Ok(value)
}

fn validate_crosswire(
    input: &SearchInput,
    geometric_input: &Fixed64GeometricInput,
) -> Result<(), NativeSamplingPoolError> {
    if !geometric_input.has_valid_receipt() {
        return Err(cross_wired("geometric input receipt is invalid"));
    }
    if input.ligand_atoms.len() != geometric_input.ligand_vdw_radii_angstrom().len()
        || input
            .ligand_atoms
            .iter()
            .zip(geometric_input.ligand_vdw_radii_angstrom())
            .any(|(atom, radius)| atom.vdw_radius_angstrom.to_bits() != radius.to_bits())
    {
        return Err(cross_wired("ligand radii are cross-wired"));
    }
    if input.receptor_atoms.len() != geometric_input.receptor_coordinates_angstrom().len()
        || input.receptor_atoms.len() != geometric_input.receptor_vdw_radii_angstrom().len()
        || input
            .receptor_atoms
            .iter()
            .zip(
                geometric_input
                    .receptor_coordinates_angstrom()
                    .iter()
                    .zip(geometric_input.receptor_vdw_radii_angstrom()),
            )
            .any(|(atom, (coordinate, radius))| {
                atom.position_angstrom != *coordinate
                    || atom.vdw_radius_angstrom.to_bits() != radius.to_bits()
            })
    {
        return Err(cross_wired("receptor geometry is cross-wired"));
    }
    Ok(())
}

fn push_anchor_generated(
    candidates: &mut Vec<NativeSamplingFunnelCandidate>,
    payload_rows: &mut Vec<NativeSamplingFunnelPayloadRow>,
    lane: NativeSamplingFunnelLane,
    local_index: usize,
    source_sha256: [u8; 32],
    candidate: &Candidate,
    geometric_input: &Fixed64GeometricInput,
) -> Result<(), NativeSamplingPoolError> {
    let anchor_penalty = (1.0 - candidate.anchor_alignment_cosine).max(0.0) * 0.5
        + candidate.anchor_fit_rmsd_angstrom / NATIVE_SAMPLING_POOL_DUAL_ANCHOR_TOLERANCE_ANGSTROM;
    push_generated(
        candidates,
        payload_rows,
        lane,
        local_index,
        source_sha256,
        candidate.coordinates_angstrom.clone(),
        candidate.source_quaternion,
        anchor_penalty,
        geometric_input,
    )
}

#[allow(clippy::too_many_arguments)]
fn push_generated(
    candidates: &mut Vec<NativeSamplingFunnelCandidate>,
    payload_rows: &mut Vec<NativeSamplingFunnelPayloadRow>,
    lane: NativeSamplingFunnelLane,
    local_index: usize,
    source_sha256: [u8; 32],
    coordinates_angstrom: Vec<Vec3>,
    source_quaternion: Quaternion,
    anchor_penalty: f64,
    geometric_input: &Fixed64GeometricInput,
) -> Result<(), NativeSamplingPoolError> {
    let pool_index = lane_pool_index(lane, local_index);
    let metrics = evaluate_fixed64_geometric_metrics(&coordinates_angstrom, geometric_input)
        .map_err(|error| generation(format!("geometric observation failed: {error}")))?;
    let shape_penalty = metrics.penetration_pair_count() as f64 / metrics.exact_pair_count() as f64;
    let coordinate_sha256 = native_fixed64_coordinate_sha256(&coordinates_angstrom)
        .map_err(|error| generation(format!("coordinate identity failed: {error}")))?;
    let placed_centroid = centroid(&coordinates_angstrom);
    let embedding = [
        placed_centroid.x,
        placed_centroid.y,
        placed_centroid.z,
        source_quaternion.x,
        source_quaternion.y,
        source_quaternion.z,
        source_quaternion.w,
    ];
    debug_assert_eq!(embedding.len(), NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION);
    let proposal_sha256 = proposal_sha256(
        source_sha256,
        lane,
        local_index,
        coordinate_sha256,
        source_quaternion,
        anchor_penalty,
    );
    candidates.push(
        NativeSamplingFunnelCandidate::generated(
            pool_index,
            lane,
            source_sha256,
            proposal_sha256,
            coordinate_sha256,
            metrics.minimum_vdw_ratio(),
            metrics.pocket_escape_angstrom(),
            shape_penalty,
            anchor_penalty,
            embedding,
        )
        .map_err(|error| generation(format!("funnel candidate failed: {error}")))?,
    );
    payload_rows.push(
        NativeSamplingFunnelPayloadRow::generated(
            pool_index,
            source_sha256,
            proposal_sha256,
            coordinates_angstrom,
            source_quaternion,
        )
        .map_err(|error| generation(format!("payload row failed: {error}")))?,
    );
    Ok(())
}

fn rotate_centered_to(
    source_coordinates: &[Vec3],
    source_centroid: Vec3,
    rotation: Quaternion,
    target_centroid: Vec3,
) -> Vec<Vec3> {
    source_coordinates
        .iter()
        .map(|coordinate| {
            rotation
                .rotate(coordinate.minus(source_centroid))
                .plus(target_centroid)
        })
        .collect()
}

const fn lane_pool_index(lane: NativeSamplingFunnelLane, local_index: usize) -> usize {
    let lane_index = match lane {
        NativeSamplingFunnelLane::UniformSo3 => 0,
        NativeSamplingFunnelLane::PocketSurface => 1,
        NativeSamplingFunnelLane::SingleAnchor => 2,
        NativeSamplingFunnelLane::MultiAnchor => 3,
    };
    lane_index * NATIVE_SAMPLING_POOL_LANE_DENOMINATOR + local_index
}

fn source_sha256(search_input_sha256: [u8; 32], geometric_input_sha256: [u8; 32]) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_sampling_pool_source/native-v1");
    hash.digest(search_input_sha256);
    hash.digest(geometric_input_sha256);
    hash.finish()
}

fn orientation_seed_sha256(source_sha256: [u8; 32]) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_sampling_pool_orientation_seed/native-v1");
    hash.digest(source_sha256);
    hash.finish()
}

fn proposal_sha256(
    source_sha256: [u8; 32],
    lane: NativeSamplingFunnelLane,
    local_index: usize,
    coordinate_sha256: [u8; 32],
    quaternion: Quaternion,
    anchor_penalty: f64,
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_sampling_pool_proposal/native-v1");
    hash.digest(source_sha256);
    hash.string(lane.id());
    hash.usize(local_index);
    hash.digest(coordinate_sha256);
    hash.f64(quaternion.x);
    hash.f64(quaternion.y);
    hash.f64(quaternion.z);
    hash.f64(quaternion.w);
    hash.f64(anchor_penalty);
    hash.finish()
}

fn sampling_pool_receipt_sha256(value: &NativeSamplingPoolBatch) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_SAMPLING_POOL_SCHEMA_ID);
    hash.string(NATIVE_SAMPLING_POOL_PROFILE_ID);
    hash.usize(NATIVE_SAMPLING_POOL_LANE_DENOMINATOR);
    hash.f64(NATIVE_SAMPLING_POOL_PLACEMENT_CLEARANCE_ANGSTROM);
    hash.f64(NATIVE_SAMPLING_POOL_DUAL_ANCHOR_TOLERANCE_ANGSTROM);
    hash.string(NATIVE_SAMPLING_POOL_SHAPE_PENALTY_ID);
    hash.string(NATIVE_SAMPLING_POOL_ANCHOR_PENALTY_ID);
    hash.string(NATIVE_SAMPLING_POOL_EMBEDDING_ID);
    hash.usize(FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS);
    hash.digest(value.source_sha256);
    hash.digest(value.search_input_sha256);
    hash.digest(value.geometric_input_sha256);
    hash.usize(value.ligand_atom_count);
    hash.usize(value.receptor_atom_count);
    hash.usize(value.exact_pair_evaluation_count);
    hash.digest(value.funnel.receipt_sha256());
    hash.digest(value.payloads.receipt_sha256());
    hash.digest(value.preselected.receipt_sha256());
    for authority in [
        value.molecular_execution_authorized(),
        value.fresh_128_execution_authorized(),
        value.benchmark_claim_authorized(),
        value.product_authorized(),
        value.scientific_claim_authorized(),
        value.reservation_authorized(),
        value.stage0_admission_authorized(),
        value.hip_device_execution_authorized(),
        value.performance_claim_authorized(),
        value.rank_mutation_authorized(),
    ] {
        hash.bool(authority);
    }
    hash.finish()
}

fn invalid(message: impl Into<String>) -> NativeSamplingPoolError {
    NativeSamplingPoolError::new(NativeSamplingPoolErrorCode::InvalidInput, message)
}

fn cross_wired(message: impl Into<String>) -> NativeSamplingPoolError {
    NativeSamplingPoolError::new(NativeSamplingPoolErrorCode::InputCrossWired, message)
}

fn pair_budget(message: impl Into<String>) -> NativeSamplingPoolError {
    NativeSamplingPoolError::new(NativeSamplingPoolErrorCode::PairBudgetExceeded, message)
}

fn generation(message: impl Into<String>) -> NativeSamplingPoolError {
    NativeSamplingPoolError::new(NativeSamplingPoolErrorCode::GenerationFailed, message)
}

fn internal(message: impl Into<String>) -> NativeSamplingPoolError {
    NativeSamplingPoolError::new(NativeSamplingPoolErrorCode::InternalInvariant, message)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        AnchorId, AnchorKind, LigandAnchor, LigandAtom, NativeSamplingFunnelCandidateState,
        ReceptorAtom, SurfaceId, SurfaceSample,
    };

    fn fixture() -> (SearchInput, Fixed64GeometricInput) {
        let ligand_atoms = vec![
            LigandAtom {
                position_angstrom: Vec3::new(0.0, -0.5, 0.0),
                vdw_radius_angstrom: 1.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.1,
            },
            LigandAtom {
                position_angstrom: Vec3::new(0.0, 0.5, 0.0),
                vdw_radius_angstrom: 1.4,
                epsilon_kcal_per_mol: 0.3,
                charge_elementary: -0.1,
            },
        ];
        let receptor_atoms = vec![ReceptorAtom {
            position_angstrom: Vec3::new(20.0, 0.0, 0.0),
            vdw_radius_angstrom: 1.6,
            epsilon_kcal_per_mol: 0.2,
            charge_elementary: 0.0,
        }];
        let input = SearchInput {
            source_seed: [0x42; 32],
            ligand_atoms,
            ligand_anchors: vec![
                LigandAnchor {
                    id: AnchorId(10),
                    atom_index: 0,
                    direction: Vec3::new(1.0, 0.0, 0.0),
                    kind: AnchorKind::HydrogenBondDonor,
                },
                LigandAnchor {
                    id: AnchorId(20),
                    atom_index: 1,
                    direction: Vec3::new(1.0, 0.0, 0.0),
                    kind: AnchorKind::HydrogenBondAcceptor,
                },
            ],
            receptor_atoms,
            surface_samples: vec![
                SurfaceSample {
                    id: SurfaceId(100),
                    position_angstrom: Vec3::new(4.0, -0.5, 0.0),
                    outward_normal: Vec3::new(1.0, 0.0, 0.0),
                    anchor_kind: AnchorKind::HydrogenBondAcceptor,
                },
                SurfaceSample {
                    id: SurfaceId(200),
                    position_angstrom: Vec3::new(4.0, 0.5, 0.0),
                    outward_normal: Vec3::new(1.0, 0.0, 0.0),
                    anchor_kind: AnchorKind::HydrogenBondDonor,
                },
            ],
        };
        let geometric = Fixed64GeometricInput::new(
            input
                .ligand_atoms
                .iter()
                .map(|atom| atom.vdw_radius_angstrom)
                .collect(),
            vec![true; input.ligand_atoms.len()],
            input
                .receptor_atoms
                .iter()
                .map(|atom| atom.position_angstrom)
                .collect(),
            input
                .receptor_atoms
                .iter()
                .map(|atom| atom.vdw_radius_angstrom)
                .collect(),
            Vec3::new(5.0, 0.0, 0.0),
            20.0,
        )
        .unwrap();
        (input, geometric)
    }

    #[test]
    fn produces_actual_source_bound_four_lane_pool_and_materializes_fixed64() {
        let (input, geometric) = fixture();
        let first = produce_native_sampling_pool(&input, &geometric).unwrap();
        let second = produce_native_sampling_pool(&input, &geometric).unwrap();
        assert_eq!(first, second);
        assert!(first.has_valid_receipt());
        assert!(first.verifies_against(&input, &geometric));
        assert_eq!(first.funnel().candidates().len(), 512);
        assert_eq!(first.payloads().rows().len(), 512);
        assert_eq!(first.preselected().rows().len(), 64);
        assert_eq!(first.ligand_atom_count(), 2);
        assert_eq!(first.receptor_atom_count(), 1);
        assert_eq!(first.exact_pair_evaluation_count(), 1024);
        for lane in crate::NATIVE_SAMPLING_FUNNEL_LANE_ORDER {
            let summary = first.funnel().lane_summary(lane);
            assert_eq!(summary.generated_count(), 128);
            assert_eq!(summary.typed_failure_count(), 0);
            assert_eq!(summary.selected_count(), lane.quota());
        }
        let source_coordinates = input
            .ligand_atoms
            .iter()
            .map(|atom| atom.position_angstrom)
            .collect::<Vec<_>>();
        let first_coordinates = match first.payloads().rows()[0].state() {
            crate::NativeSamplingFunnelPayloadRowState::Generated {
                coordinates_angstrom,
                ..
            } => coordinates_angstrom.as_ref(),
            crate::NativeSamplingFunnelPayloadRowState::TypedFailure => panic!("generated row"),
        };
        assert_ne!(first_coordinates, source_coordinates);
        assert!(!first.molecular_execution_authorized());
        assert!(!first.fresh_128_execution_authorized());
        assert!(!first.benchmark_claim_authorized());
        assert!(!first.product_authorized());
        assert!(!first.scientific_claim_authorized());
        assert!(!first.reservation_authorized());
        assert!(!first.stage0_admission_authorized());
        assert!(!first.hip_device_execution_authorized());
        assert!(!first.performance_claim_authorized());
        assert!(!first.rank_mutation_authorized());
    }

    #[test]
    fn semantic_anchor_and_surface_reordering_does_not_change_output() {
        let (input, geometric) = fixture();
        let expected = produce_native_sampling_pool(&input, &geometric).unwrap();
        let mut reordered = input.clone();
        reordered.ligand_anchors.reverse();
        reordered.surface_samples.reverse();
        assert_eq!(reordered.canonical_sha256(), input.canonical_sha256());
        assert_eq!(
            produce_native_sampling_pool(&reordered, &geometric).unwrap(),
            expected
        );
    }

    #[test]
    fn missing_dual_geometry_is_a_typed_lane_shortfall() {
        let (mut input, geometric) = fixture();
        input.ligand_anchors.truncate(1);
        input.surface_samples.truncate(1);
        let geometric = Fixed64GeometricInput::new(
            geometric.ligand_vdw_radii_angstrom().to_vec(),
            geometric.ligand_heavy_atom_mask().to_vec(),
            geometric.receptor_coordinates_angstrom().to_vec(),
            geometric.receptor_vdw_radii_angstrom().to_vec(),
            geometric.pocket_center_angstrom(),
            geometric.pocket_radius_angstrom(),
        )
        .unwrap();
        let observed = produce_native_sampling_pool(&input, &geometric).unwrap();
        let summary = observed
            .funnel()
            .lane_summary(NativeSamplingFunnelLane::MultiAnchor);
        assert_eq!(summary.generated_count(), 0);
        assert_eq!(summary.typed_failure_count(), 128);
        assert_eq!(summary.shortfall_count(), 8);
        assert_eq!(observed.exact_pair_evaluation_count(), 768);
        for row in &observed.funnel().candidates()[384..] {
            assert!(matches!(
                row.state(),
                NativeSamplingFunnelCandidateState::TypedFailure { failure_code }
                    if failure_code == NATIVE_SAMPLING_POOL_MULTI_ANCHOR_UNAVAILABLE
            ));
        }
    }

    #[test]
    fn crosswired_geometry_and_aggregate_pair_overflow_fail_closed() {
        let (input, _) = fixture();
        let crosswired = Fixed64GeometricInput::new(
            vec![1.5, 1.5],
            vec![true, true],
            vec![Vec3::new(20.0, 0.0, 0.0)],
            vec![1.6],
            Vec3::new(5.0, 0.0, 0.0),
            20.0,
        )
        .unwrap();
        assert_eq!(
            produce_native_sampling_pool(&input, &crosswired)
                .unwrap_err()
                .code(),
            NativeSamplingPoolErrorCode::InputCrossWired
        );

        let (mut large, _) = fixture();
        large.ligand_atoms = (0..256)
            .map(|index| LigandAtom {
                position_angstrom: Vec3::new(index as f64 * 0.01, 0.0, 0.0),
                vdw_radius_angstrom: 1.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.0,
            })
            .collect();
        large.ligand_anchors.truncate(1);
        large.ligand_anchors[0].atom_index = 0;
        large.surface_samples.truncate(1);
        large.receptor_atoms = (0..172)
            .map(|index| ReceptorAtom {
                position_angstrom: Vec3::new(100.0 + index as f64, 0.0, 0.0),
                vdw_radius_angstrom: 1.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.0,
            })
            .collect();
        let large_geometric = Fixed64GeometricInput::new(
            vec![1.5; 256],
            vec![true; 256],
            large
                .receptor_atoms
                .iter()
                .map(|atom| atom.position_angstrom)
                .collect(),
            vec![1.5; 172],
            Vec3::new(5.0, 0.0, 0.0),
            20.0,
        )
        .unwrap();
        assert_eq!(
            produce_native_sampling_pool(&large, &large_geometric)
                .unwrap_err()
                .code(),
            NativeSamplingPoolErrorCode::PairBudgetExceeded
        );
    }
}
