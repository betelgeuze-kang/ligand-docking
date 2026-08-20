//! Deterministic, result-independent 512-to-64 proposal selection.
//!
//! This module is the Rust CPU implementation of the development reference in
//! `tools/run_engine_v2_sampling_funnel_v1.py`. It deliberately accepts only
//! pre-result geometry, source identities, and a seven-value diversity
//! embedding. Native/reference RMSD, validity, score, and downstream rank have
//! no representation in the input type.

use std::cmp::Ordering;
use std::collections::BTreeSet;
use std::fmt;

use crate::native_hash::CanonicalHash;

pub const NATIVE_SAMPLING_FUNNEL_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_sampling_funnel_receipt/1.0.0";
pub const NATIVE_SAMPLING_FUNNEL_INPUT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_sampling_funnel_input/1.0.0";
pub const NATIVE_SAMPLING_FUNNEL_PROFILE_ID: &str = "engine_v2_deterministic_512_to_64_funnel_v1";
pub const NATIVE_SAMPLING_FUNNEL_DUPLICATE_POLICY: &str =
    "global_coordinate_sha256_first_pool_index";
pub const NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256: [u8; 32] = [
    0x5f, 0x9a, 0x3f, 0x30, 0xdd, 0xb1, 0xcf, 0x76, 0xa6, 0x4c, 0xb6, 0x4d, 0xff, 0x67, 0x8c, 0x19,
    0x17, 0x51, 0xe2, 0xea, 0xd3, 0x68, 0xc8, 0xe9, 0xf7, 0x3f, 0x08, 0xd4, 0x4e, 0xc6, 0x9a, 0x28,
];
pub const NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR: usize = 512;
pub const NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR: usize = 64;
pub const NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION: usize = 7;
pub const NATIVE_SAMPLING_FUNNEL_HARD_MINIMUM_VDW_RATIO: f64 = 0.55;
pub const NATIVE_SAMPLING_FUNNEL_MAXIMUM_POCKET_ESCAPE_ANGSTROM: f64 = 4.0;
pub const NATIVE_SAMPLING_FUNNEL_QUALITY_PREFILTER_MULTIPLIER: usize = 4;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum NativeSamplingFunnelLane {
    UniformSo3,
    PocketSurface,
    SingleAnchor,
    MultiAnchor,
}

impl NativeSamplingFunnelLane {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::UniformSo3 => "uniform_so3",
            Self::PocketSurface => "pocket_surface",
            Self::SingleAnchor => "single_anchor",
            Self::MultiAnchor => "multi_anchor",
        }
    }

    #[must_use]
    pub const fn quota(self) -> usize {
        match self {
            Self::UniformSo3 => 24,
            Self::PocketSurface | Self::SingleAnchor => 16,
            Self::MultiAnchor => 8,
        }
    }

    const fn index(self) -> usize {
        match self {
            Self::UniformSo3 => 0,
            Self::PocketSurface => 1,
            Self::SingleAnchor => 2,
            Self::MultiAnchor => 3,
        }
    }

    const fn tag(self) -> u8 {
        self.index() as u8
    }
}

pub const NATIVE_SAMPLING_FUNNEL_LANE_ORDER: [NativeSamplingFunnelLane; 4] = [
    NativeSamplingFunnelLane::UniformSo3,
    NativeSamplingFunnelLane::PocketSurface,
    NativeSamplingFunnelLane::SingleAnchor,
    NativeSamplingFunnelLane::MultiAnchor,
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeSamplingFunnelErrorCode {
    InvalidInput,
    InputCrossWired,
    NonFiniteDerivedValue,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeSamplingFunnelError {
    code: NativeSamplingFunnelErrorCode,
    message: &'static str,
}

impl NativeSamplingFunnelError {
    const fn new(code: NativeSamplingFunnelErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeSamplingFunnelErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeSamplingFunnelError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native sampling funnel: {}", self.message)
    }
}

impl std::error::Error for NativeSamplingFunnelError {}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeSamplingFunnelGeneratedCandidate {
    source_sha256: [u8; 32],
    proposal_sha256: [u8; 32],
    coordinate_sha256: [u8; 32],
    minimum_vdw_ratio: f64,
    pocket_escape_angstrom: f64,
    shape_penalty: f64,
    anchor_penalty: f64,
    embedding: [f64; NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION],
}

impl NativeSamplingFunnelGeneratedCandidate {
    #[must_use]
    pub const fn source_sha256(self) -> [u8; 32] {
        self.source_sha256
    }

    #[must_use]
    pub const fn proposal_sha256(self) -> [u8; 32] {
        self.proposal_sha256
    }

    #[must_use]
    pub const fn coordinate_sha256(self) -> [u8; 32] {
        self.coordinate_sha256
    }

    #[must_use]
    pub const fn minimum_vdw_ratio(self) -> f64 {
        self.minimum_vdw_ratio
    }

    #[must_use]
    pub const fn pocket_escape_angstrom(self) -> f64 {
        self.pocket_escape_angstrom
    }

    #[must_use]
    pub const fn shape_penalty(self) -> f64 {
        self.shape_penalty
    }

    #[must_use]
    pub const fn anchor_penalty(self) -> f64 {
        self.anchor_penalty
    }

    #[must_use]
    pub const fn embedding(self) -> [f64; NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION] {
        self.embedding
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum NativeSamplingFunnelCandidateState {
    Generated(NativeSamplingFunnelGeneratedCandidate),
    TypedFailure { failure_code: String },
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeSamplingFunnelCandidate {
    pool_index: usize,
    lane: NativeSamplingFunnelLane,
    state: NativeSamplingFunnelCandidateState,
}

impl NativeSamplingFunnelCandidate {
    #[allow(clippy::too_many_arguments)]
    pub fn generated(
        pool_index: usize,
        lane: NativeSamplingFunnelLane,
        source_sha256: [u8; 32],
        proposal_sha256: [u8; 32],
        coordinate_sha256: [u8; 32],
        minimum_vdw_ratio: f64,
        pocket_escape_angstrom: f64,
        shape_penalty: f64,
        anchor_penalty: f64,
        embedding: [f64; NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION],
    ) -> Result<Self, NativeSamplingFunnelError> {
        if pool_index >= NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR
            || [source_sha256, proposal_sha256, coordinate_sha256].contains(&[0; 32])
        {
            return Err(invalid(
                "generated candidate identity is absent or out of range",
            ));
        }
        let minimum_vdw_ratio = finite_nonnegative(minimum_vdw_ratio)?;
        let pocket_escape_angstrom = finite_nonnegative(pocket_escape_angstrom)?;
        let shape_penalty = finite_nonnegative(shape_penalty)?;
        let anchor_penalty = finite_nonnegative(anchor_penalty)?;
        if !(shape_penalty + anchor_penalty).is_finite() {
            return Err(invalid("generated candidate quality sum is non-finite"));
        }
        let mut canonical_embedding = [0.0; NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION];
        for (target, value) in canonical_embedding.iter_mut().zip(embedding) {
            if !value.is_finite() {
                return Err(invalid("generated candidate embedding is non-finite"));
            }
            *target = canonical_zero(value);
        }
        Ok(Self {
            pool_index,
            lane,
            state: NativeSamplingFunnelCandidateState::Generated(
                NativeSamplingFunnelGeneratedCandidate {
                    source_sha256,
                    proposal_sha256,
                    coordinate_sha256,
                    minimum_vdw_ratio,
                    pocket_escape_angstrom,
                    shape_penalty,
                    anchor_penalty,
                    embedding: canonical_embedding,
                },
            ),
        })
    }

    pub fn typed_failure(
        pool_index: usize,
        lane: NativeSamplingFunnelLane,
        failure_code: impl Into<String>,
    ) -> Result<Self, NativeSamplingFunnelError> {
        let failure_code = failure_code.into();
        if pool_index >= NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR || failure_code.is_empty() {
            return Err(invalid("typed-failure candidate identity is invalid"));
        }
        Ok(Self {
            pool_index,
            lane,
            state: NativeSamplingFunnelCandidateState::TypedFailure { failure_code },
        })
    }

    #[must_use]
    pub const fn pool_index(&self) -> usize {
        self.pool_index
    }

    #[must_use]
    pub const fn lane(&self) -> NativeSamplingFunnelLane {
        self.lane
    }

    #[must_use]
    pub const fn state(&self) -> &NativeSamplingFunnelCandidateState {
        &self.state
    }

    const fn generated_payload(&self) -> Option<NativeSamplingFunnelGeneratedCandidate> {
        match self.state {
            NativeSamplingFunnelCandidateState::Generated(value) => Some(value),
            NativeSamplingFunnelCandidateState::TypedFailure { .. } => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeSamplingFunnelDecision {
    TypedFailure,
    DuplicateCoordinate,
    HardRejectVdw,
    HardRejectPocket,
    Eligible,
}

impl NativeSamplingFunnelDecision {
    const fn tag(self) -> u8 {
        match self {
            Self::TypedFailure => 0,
            Self::DuplicateCoordinate => 1,
            Self::HardRejectVdw => 2,
            Self::HardRejectPocket => 3,
            Self::Eligible => 4,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NativeSamplingFunnelObservation {
    pool_index: usize,
    lane: NativeSamplingFunnelLane,
    failure_code: Option<String>,
    decision: NativeSamplingFunnelDecision,
}

impl NativeSamplingFunnelObservation {
    #[must_use]
    pub const fn pool_index(&self) -> usize {
        self.pool_index
    }

    #[must_use]
    pub const fn lane(&self) -> NativeSamplingFunnelLane {
        self.lane
    }

    #[must_use]
    pub fn failure_code(&self) -> Option<&str> {
        self.failure_code.as_deref()
    }

    #[must_use]
    pub const fn decision(&self) -> NativeSamplingFunnelDecision {
        self.decision
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeSamplingFunnelSelectedState {
    Selected {
        source_pool_index: usize,
        source_sha256: [u8; 32],
        proposal_sha256: [u8; 32],
        coordinate_sha256: [u8; 32],
    },
    LaneQuotaUnfilled,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeSamplingFunnelSelectedRow {
    output_index: usize,
    lane: NativeSamplingFunnelLane,
    state: NativeSamplingFunnelSelectedState,
}

impl NativeSamplingFunnelSelectedRow {
    #[must_use]
    pub const fn output_index(self) -> usize {
        self.output_index
    }

    #[must_use]
    pub const fn lane(self) -> NativeSamplingFunnelLane {
        self.lane
    }

    #[must_use]
    pub const fn state(self) -> NativeSamplingFunnelSelectedState {
        self.state
    }

    #[must_use]
    pub const fn source_pool_index(self) -> Option<usize> {
        match self.state {
            NativeSamplingFunnelSelectedState::Selected {
                source_pool_index, ..
            } => Some(source_pool_index),
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeSamplingFunnelLaneSummary {
    lane: NativeSamplingFunnelLane,
    quota: usize,
    generated_count: usize,
    typed_failure_count: usize,
    hard_rejected_vdw_count: usize,
    hard_rejected_pocket_count: usize,
    duplicate_count: usize,
    filtered_count: usize,
    eligible_count: usize,
    selected_count: usize,
    shortfall_count: usize,
}

impl NativeSamplingFunnelLaneSummary {
    const fn empty(lane: NativeSamplingFunnelLane) -> Self {
        Self {
            lane,
            quota: lane.quota(),
            generated_count: 0,
            typed_failure_count: 0,
            hard_rejected_vdw_count: 0,
            hard_rejected_pocket_count: 0,
            duplicate_count: 0,
            filtered_count: 0,
            eligible_count: 0,
            selected_count: 0,
            shortfall_count: 0,
        }
    }

    #[must_use]
    pub const fn lane(self) -> NativeSamplingFunnelLane {
        self.lane
    }

    #[must_use]
    pub const fn quota(self) -> usize {
        self.quota
    }

    #[must_use]
    pub const fn generated_count(self) -> usize {
        self.generated_count
    }

    #[must_use]
    pub const fn typed_failure_count(self) -> usize {
        self.typed_failure_count
    }

    #[must_use]
    pub const fn hard_rejected_vdw_count(self) -> usize {
        self.hard_rejected_vdw_count
    }

    #[must_use]
    pub const fn hard_rejected_pocket_count(self) -> usize {
        self.hard_rejected_pocket_count
    }

    #[must_use]
    pub const fn duplicate_count(self) -> usize {
        self.duplicate_count
    }

    #[must_use]
    pub const fn filtered_count(self) -> usize {
        self.filtered_count
    }

    #[must_use]
    pub const fn eligible_count(self) -> usize {
        self.eligible_count
    }

    #[must_use]
    pub const fn selected_count(self) -> usize {
        self.selected_count
    }

    #[must_use]
    pub const fn shortfall_count(self) -> usize {
        self.shortfall_count
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeSamplingFunnelReceipt {
    candidates: Box<[NativeSamplingFunnelCandidate]>,
    observations: Box<[NativeSamplingFunnelObservation]>,
    selected_rows: Box<[NativeSamplingFunnelSelectedRow]>,
    lane_summaries: [NativeSamplingFunnelLaneSummary; 4],
    input_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

impl NativeSamplingFunnelReceipt {
    #[must_use]
    pub fn candidates(&self) -> &[NativeSamplingFunnelCandidate] {
        &self.candidates
    }

    #[must_use]
    pub fn observations(&self) -> &[NativeSamplingFunnelObservation] {
        &self.observations
    }

    #[must_use]
    pub fn selected_rows(&self) -> &[NativeSamplingFunnelSelectedRow] {
        &self.selected_rows
    }

    #[must_use]
    pub const fn lane_summaries(&self) -> &[NativeSamplingFunnelLaneSummary; 4] {
        &self.lane_summaries
    }

    #[must_use]
    pub fn lane_summary(&self, lane: NativeSamplingFunnelLane) -> NativeSamplingFunnelLaneSummary {
        self.lane_summaries[lane.index()]
    }

    #[must_use]
    pub const fn input_sha256(&self) -> [u8; 32] {
        self.input_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn input_denominator(&self) -> usize {
        NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR
    }

    #[must_use]
    pub const fn output_denominator(&self) -> usize {
        NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
    }

    #[must_use]
    pub const fn fresh_128_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn scientific_claim_authorized(&self) -> bool {
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
    pub const fn rank_mutation_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let Ok(derived) = derive(&self.candidates) else {
            return false;
        };
        self.candidates.len() == NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR
            && self.observations.len() == NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR
            && self.selected_rows.len() == NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            && self.observations.as_ref() == derived.observations
            && self.selected_rows.as_ref() == derived.selected_rows
            && self.lane_summaries == derived.lane_summaries
            && self.input_sha256 == derived.input_sha256
            && self.receipt_sha256 == derived.receipt_sha256
    }
}

struct DerivedFunnel {
    observations: Vec<NativeSamplingFunnelObservation>,
    selected_rows: Vec<NativeSamplingFunnelSelectedRow>,
    lane_summaries: [NativeSamplingFunnelLaneSummary; 4],
    input_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

/// Select exactly 64 result-independent rows from an exact 512-row pool.
///
/// Coordinate identities are deduplicated globally in ascending pool order.
/// Each lane retains its frozen quota; a short lane produces typed
/// `LaneQuotaUnfilled` rows and never borrows capacity from another lane.
pub fn run_native_sampling_funnel(
    candidates: Vec<NativeSamplingFunnelCandidate>,
) -> Result<NativeSamplingFunnelReceipt, NativeSamplingFunnelError> {
    let derived = derive(&candidates)?;
    let value = NativeSamplingFunnelReceipt {
        candidates: candidates.into_boxed_slice(),
        observations: derived.observations.into_boxed_slice(),
        selected_rows: derived.selected_rows.into_boxed_slice(),
        lane_summaries: derived.lane_summaries,
        input_sha256: derived.input_sha256,
        receipt_sha256: derived.receipt_sha256,
    };
    if !value.has_valid_receipt() {
        return Err(internal(
            "derived sampling-funnel receipt did not self-verify",
        ));
    }
    Ok(value)
}

fn derive(
    candidates: &[NativeSamplingFunnelCandidate],
) -> Result<DerivedFunnel, NativeSamplingFunnelError> {
    if candidates.len() != NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR {
        return Err(invalid("sampling funnel requires exactly 512 input rows"));
    }
    let mut observations = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR);
    let mut eligible_by_lane: [Vec<usize>; 4] = std::array::from_fn(|_| Vec::new());
    let mut summaries =
        NATIVE_SAMPLING_FUNNEL_LANE_ORDER.map(NativeSamplingFunnelLaneSummary::empty);
    let mut seen_coordinate_sha256 = BTreeSet::new();

    for (expected_index, candidate) in candidates.iter().enumerate() {
        if candidate.pool_index != expected_index {
            return Err(cross_wired("sampling-funnel pool order is cross-wired"));
        }
        let summary = &mut summaries[candidate.lane.index()];
        let (failure_code, decision) = match &candidate.state {
            NativeSamplingFunnelCandidateState::TypedFailure { failure_code } => {
                if failure_code.is_empty() {
                    return Err(cross_wired("typed-failure candidate lost its failure code"));
                }
                summary.typed_failure_count += 1;
                (
                    Some(failure_code.clone()),
                    NativeSamplingFunnelDecision::TypedFailure,
                )
            }
            NativeSamplingFunnelCandidateState::Generated(payload) => {
                validate_generated(*payload)?;
                summary.generated_count += 1;
                let decision = if !seen_coordinate_sha256.insert(payload.coordinate_sha256) {
                    summary.duplicate_count += 1;
                    summary.filtered_count += 1;
                    NativeSamplingFunnelDecision::DuplicateCoordinate
                } else if payload.minimum_vdw_ratio < NATIVE_SAMPLING_FUNNEL_HARD_MINIMUM_VDW_RATIO
                {
                    summary.hard_rejected_vdw_count += 1;
                    summary.filtered_count += 1;
                    NativeSamplingFunnelDecision::HardRejectVdw
                } else if payload.pocket_escape_angstrom
                    > NATIVE_SAMPLING_FUNNEL_MAXIMUM_POCKET_ESCAPE_ANGSTROM
                {
                    summary.hard_rejected_pocket_count += 1;
                    summary.filtered_count += 1;
                    NativeSamplingFunnelDecision::HardRejectPocket
                } else {
                    eligible_by_lane[candidate.lane.index()].push(candidate.pool_index);
                    NativeSamplingFunnelDecision::Eligible
                };
                (None, decision)
            }
        };
        observations.push(NativeSamplingFunnelObservation {
            pool_index: candidate.pool_index,
            lane: candidate.lane,
            failure_code,
            decision,
        });
    }

    let mut selected_rows = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    for lane in NATIVE_SAMPLING_FUNNEL_LANE_ORDER {
        let summary = &mut summaries[lane.index()];
        summary.eligible_count = eligible_by_lane[lane.index()].len();
        let selected = select_lane(candidates, &eligible_by_lane[lane.index()], lane.quota())?;
        summary.selected_count = selected.len();
        summary.shortfall_count = lane.quota() - selected.len();
        for lane_output_index in 0..lane.quota() {
            let output_index = selected_rows.len();
            let state = if let Some(pool_index) = selected.get(lane_output_index).copied() {
                let payload = candidates[pool_index]
                    .generated_payload()
                    .ok_or_else(|| internal("selected funnel row is not generated"))?;
                NativeSamplingFunnelSelectedState::Selected {
                    source_pool_index: pool_index,
                    source_sha256: payload.source_sha256,
                    proposal_sha256: payload.proposal_sha256,
                    coordinate_sha256: payload.coordinate_sha256,
                }
            } else {
                NativeSamplingFunnelSelectedState::LaneQuotaUnfilled
            };
            selected_rows.push(NativeSamplingFunnelSelectedRow {
                output_index,
                lane,
                state,
            });
        }
    }
    if selected_rows.len() != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
        || summaries.iter().map(|summary| summary.quota).sum::<usize>()
            != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
    {
        return Err(internal("sampling-funnel output denominator changed"));
    }
    let selected_coordinate_sha256 = selected_rows
        .iter()
        .filter_map(|row| match row.state {
            NativeSamplingFunnelSelectedState::Selected {
                coordinate_sha256, ..
            } => Some(coordinate_sha256),
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => None,
        })
        .collect::<BTreeSet<_>>();
    if selected_coordinate_sha256.len()
        != selected_rows
            .iter()
            .filter(|row| {
                matches!(
                    row.state,
                    NativeSamplingFunnelSelectedState::Selected { .. }
                )
            })
            .count()
    {
        return Err(internal("sampling funnel selected a duplicate coordinate"));
    }

    let input_sha256 = input_sha256(candidates);
    let receipt_sha256 = receipt_sha256(input_sha256, &observations, &selected_rows, &summaries);
    Ok(DerivedFunnel {
        observations,
        selected_rows,
        lane_summaries: summaries,
        input_sha256,
        receipt_sha256,
    })
}

fn select_lane(
    candidates: &[NativeSamplingFunnelCandidate],
    eligible: &[usize],
    quota: usize,
) -> Result<Vec<usize>, NativeSamplingFunnelError> {
    let mut prefiltered = eligible.to_vec();
    prefiltered.sort_by(|left, right| quality_cmp(&candidates[*left], &candidates[*right]));
    prefiltered.truncate(
        quota
            .checked_mul(NATIVE_SAMPLING_FUNNEL_QUALITY_PREFILTER_MULTIPLIER)
            .ok_or_else(|| internal("sampling-funnel prefilter capacity overflowed"))?,
    );
    if prefiltered.is_empty() {
        return Ok(Vec::new());
    }
    let mut selected = vec![prefiltered.remove(0)];
    while !prefiltered.is_empty() && selected.len() < quota {
        let mut best_position = 0usize;
        let mut best_distance = minimum_distance(candidates, prefiltered[0], &selected)?;
        for (position, pool_index) in prefiltered.iter().copied().enumerate().skip(1) {
            let distance = minimum_distance(candidates, pool_index, &selected)?;
            let distance_order = distance.total_cmp(&best_distance);
            if distance_order == Ordering::Greater
                || (distance_order == Ordering::Equal
                    && quality_cmp(
                        &candidates[pool_index],
                        &candidates[prefiltered[best_position]],
                    ) == Ordering::Less)
            {
                best_position = position;
                best_distance = distance;
            }
        }
        selected.push(prefiltered.remove(best_position));
    }
    Ok(selected)
}

fn minimum_distance(
    candidates: &[NativeSamplingFunnelCandidate],
    pool_index: usize,
    selected: &[usize],
) -> Result<f64, NativeSamplingFunnelError> {
    let embedding = generated(candidates, pool_index)?.embedding;
    let mut minimum = f64::INFINITY;
    for selected_index in selected {
        let selected_embedding = generated(candidates, *selected_index)?.embedding;
        let mut squared = 0.0;
        for (left, right) in embedding.into_iter().zip(selected_embedding) {
            let delta = left - right;
            squared += delta * delta;
        }
        let distance = libm::sqrt(squared);
        if !distance.is_finite() {
            return Err(non_finite(
                "sampling-funnel embedding distance is non-finite",
            ));
        }
        minimum = minimum.min(distance);
    }
    if !minimum.is_finite() {
        return Err(internal("sampling-funnel selected set is empty"));
    }
    Ok(minimum)
}

fn quality_cmp(
    left: &NativeSamplingFunnelCandidate,
    right: &NativeSamplingFunnelCandidate,
) -> Ordering {
    let left_payload = left
        .generated_payload()
        .expect("eligible sampling-funnel candidate is generated");
    let right_payload = right
        .generated_payload()
        .expect("eligible sampling-funnel candidate is generated");
    (left_payload.shape_penalty + left_payload.anchor_penalty)
        .total_cmp(&(right_payload.shape_penalty + right_payload.anchor_penalty))
        .then_with(|| {
            left_payload
                .shape_penalty
                .total_cmp(&right_payload.shape_penalty)
        })
        .then_with(|| {
            left_payload
                .anchor_penalty
                .total_cmp(&right_payload.anchor_penalty)
        })
        // Pool indices are unique and complete, so this final key makes every
        // quality comparison total and matches the Python reference tuple.
        .then_with(|| left.pool_index.cmp(&right.pool_index))
}

fn generated(
    candidates: &[NativeSamplingFunnelCandidate],
    pool_index: usize,
) -> Result<NativeSamplingFunnelGeneratedCandidate, NativeSamplingFunnelError> {
    candidates
        .get(pool_index)
        .and_then(NativeSamplingFunnelCandidate::generated_payload)
        .ok_or_else(|| internal("eligible sampling-funnel row is not generated"))
}

fn validate_generated(
    payload: NativeSamplingFunnelGeneratedCandidate,
) -> Result<(), NativeSamplingFunnelError> {
    if [
        payload.source_sha256,
        payload.proposal_sha256,
        payload.coordinate_sha256,
    ]
    .contains(&[0; 32])
        || [
            payload.minimum_vdw_ratio,
            payload.pocket_escape_angstrom,
            payload.shape_penalty,
            payload.anchor_penalty,
        ]
        .iter()
        .any(|value| !value.is_finite() || *value < 0.0)
        || !(payload.shape_penalty + payload.anchor_penalty).is_finite()
        || payload.embedding.iter().any(|value| !value.is_finite())
    {
        return Err(cross_wired("generated sampling-funnel evidence is invalid"));
    }
    Ok(())
}

fn input_sha256(candidates: &[NativeSamplingFunnelCandidate]) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_SAMPLING_FUNNEL_INPUT_SCHEMA_ID);
    hash.string(NATIVE_SAMPLING_FUNNEL_PROFILE_ID);
    hash.digest(NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256);
    hash.string(NATIVE_SAMPLING_FUNNEL_DUPLICATE_POLICY);
    hash.usize(NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR);
    for candidate in candidates {
        hash.usize(candidate.pool_index);
        hash.byte(candidate.lane.tag());
        match &candidate.state {
            NativeSamplingFunnelCandidateState::Generated(payload) => {
                hash.byte(0);
                hash.digest(payload.source_sha256);
                hash.digest(payload.proposal_sha256);
                hash.digest(payload.coordinate_sha256);
                hash.f64(payload.minimum_vdw_ratio);
                hash.f64(payload.pocket_escape_angstrom);
                hash.f64(payload.shape_penalty);
                hash.f64(payload.anchor_penalty);
                for value in payload.embedding {
                    hash.f64(value);
                }
            }
            NativeSamplingFunnelCandidateState::TypedFailure { failure_code } => {
                hash.byte(1);
                hash.string(failure_code);
            }
        }
    }
    hash.finish()
}

fn receipt_sha256(
    input_sha256: [u8; 32],
    observations: &[NativeSamplingFunnelObservation],
    selected_rows: &[NativeSamplingFunnelSelectedRow],
    summaries: &[NativeSamplingFunnelLaneSummary; 4],
) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_SAMPLING_FUNNEL_SCHEMA_ID);
    hash.string(NATIVE_SAMPLING_FUNNEL_PROFILE_ID);
    hash.digest(NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256);
    hash.string(NATIVE_SAMPLING_FUNNEL_DUPLICATE_POLICY);
    hash.usize(NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR);
    hash.usize(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    hash.digest(input_sha256);
    hash.usize(observations.len());
    for observation in observations {
        hash.usize(observation.pool_index);
        hash.byte(observation.lane.tag());
        hash.option(observation.failure_code.as_deref(), |hash, value| {
            hash.string(value);
        });
        hash.byte(observation.decision.tag());
    }
    hash.usize(selected_rows.len());
    for row in selected_rows {
        hash.usize(row.output_index);
        hash.byte(row.lane.tag());
        match row.state {
            NativeSamplingFunnelSelectedState::Selected {
                source_pool_index,
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
            } => {
                hash.byte(0);
                hash.usize(source_pool_index);
                hash.digest(source_sha256);
                hash.digest(proposal_sha256);
                hash.digest(coordinate_sha256);
            }
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => hash.byte(1),
        }
    }
    for summary in summaries {
        hash.byte(summary.lane.tag());
        hash.usize(summary.quota);
        hash.usize(summary.generated_count);
        hash.usize(summary.typed_failure_count);
        hash.usize(summary.hard_rejected_vdw_count);
        hash.usize(summary.hard_rejected_pocket_count);
        hash.usize(summary.duplicate_count);
        hash.usize(summary.filtered_count);
        hash.usize(summary.eligible_count);
        hash.usize(summary.selected_count);
        hash.usize(summary.shortfall_count);
    }
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn finite_nonnegative(value: f64) -> Result<f64, NativeSamplingFunnelError> {
    if !value.is_finite() || value < 0.0 {
        return Err(invalid("sampling-funnel numeric input is out of range"));
    }
    Ok(canonical_zero(value))
}

const fn canonical_zero(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

const fn invalid(message: &'static str) -> NativeSamplingFunnelError {
    NativeSamplingFunnelError::new(NativeSamplingFunnelErrorCode::InvalidInput, message)
}

const fn cross_wired(message: &'static str) -> NativeSamplingFunnelError {
    NativeSamplingFunnelError::new(NativeSamplingFunnelErrorCode::InputCrossWired, message)
}

const fn non_finite(message: &'static str) -> NativeSamplingFunnelError {
    NativeSamplingFunnelError::new(
        NativeSamplingFunnelErrorCode::NonFiniteDerivedValue,
        message,
    )
}

const fn internal(message: &'static str) -> NativeSamplingFunnelError {
    NativeSamplingFunnelError::new(NativeSamplingFunnelErrorCode::InternalInvariant, message)
}
