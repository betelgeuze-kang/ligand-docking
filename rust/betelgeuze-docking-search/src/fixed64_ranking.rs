use std::cmp::Ordering;
use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    NativeFixed64ValidityBatch, NativeFixed64ValidityRowStatus, NativeScorerV1RowStatus,
    FIXED64_CANDIDATE_COUNT,
};

pub const NATIVE_FIXED64_RANKING_RECORD_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_ranking_record/1.0.0";
pub const NATIVE_FIXED64_RANKING_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_ranking_batch/1.0.0";
pub const NATIVE_FIXED64_RANKING_ALGORITHM_ID: &str =
    "score_ascending_then_slot_then_coordinate_sha256/1.0.0";
pub const NATIVE_FIXED64_PRIMARY_RANKING_SEMANTICS: &str =
    "complete_native_scorer_v1_rows_including_pose_invalid_and_validity_unavailable";
pub const NATIVE_FIXED64_VALID_RANKING_SEMANTICS: &str =
    "primary_score_order_filtered_by_complete_native_pose_validity_true";
pub const NATIVE_FIXED64_TOP_K_LIMIT: usize = 5;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64RankingErrorCode {
    UpstreamCrossWired,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeFixed64RankingError {
    code: NativeFixed64RankingErrorCode,
    message: &'static str,
}

impl NativeFixed64RankingError {
    const fn new(code: NativeFixed64RankingErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeFixed64RankingErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeFixed64RankingError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native fixed64 ranking: {}", self.message)
    }
}

impl std::error::Error for NativeFixed64RankingError {}

/// Receipt-free, fixed-denominator input to the reusable stable Top-K kernel.
///
/// The higher-level ranking receipt and the native ABI both use this exact
/// numerical ordering primitive. A scored row must carry its finite total and
/// coordinate identity; a scorer failure must carry neither. Pose validity
/// may filter the valid-only ranking but can never remove a row from the
/// primary score ordering.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeFixed64StableTopKInputRow {
    slot_index: usize,
    scorer_status: NativeScorerV1RowStatus,
    validity_status: NativeFixed64ValidityRowStatus,
    total_score: Option<f64>,
    coordinate_sha256: Option<[u8; 32]>,
    valid: bool,
}

impl NativeFixed64StableTopKInputRow {
    pub fn new(
        slot_index: usize,
        scorer_status: NativeScorerV1RowStatus,
        validity_status: NativeFixed64ValidityRowStatus,
        total_score: Option<f64>,
        coordinate_sha256: Option<[u8; 32]>,
        valid: bool,
    ) -> Result<Self, NativeFixed64RankingError> {
        if slot_index >= FIXED64_CANDIDATE_COUNT {
            return Err(cross_wired("ranking input slot index is outside fixed64"));
        }
        match scorer_status {
            NativeScorerV1RowStatus::Scored => {
                if !total_score.is_some_and(f64::is_finite) || coordinate_sha256.is_none() {
                    return Err(cross_wired("scored ranking row lacks finite evidence"));
                }
                if validity_status == NativeFixed64ValidityRowStatus::UpstreamScorerFailure {
                    return Err(cross_wired(
                        "scored ranking row has upstream validity failure",
                    ));
                }
            }
            NativeScorerV1RowStatus::TypedFailure => {
                if total_score.is_some()
                    || coordinate_sha256.is_some()
                    || validity_status != NativeFixed64ValidityRowStatus::UpstreamScorerFailure
                {
                    return Err(cross_wired(
                        "failed ranking row has scored or validity evidence",
                    ));
                }
            }
        }
        if validity_status != NativeFixed64ValidityRowStatus::Evaluated && valid {
            return Err(cross_wired("unevaluated ranking row cannot be pose-valid"));
        }
        Ok(Self {
            slot_index,
            scorer_status,
            validity_status,
            total_score: total_score.map(canonical_score),
            coordinate_sha256,
            valid,
        })
    }

    #[must_use]
    pub const fn slot_index(self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn scorer_status(self) -> NativeScorerV1RowStatus {
        self.scorer_status
    }

    #[must_use]
    pub const fn validity_status(self) -> NativeFixed64ValidityRowStatus {
        self.validity_status
    }

    #[must_use]
    pub const fn total_score(self) -> Option<f64> {
        self.total_score
    }

    #[must_use]
    pub const fn coordinate_sha256(self) -> Option<[u8; 32]> {
        self.coordinate_sha256
    }

    #[must_use]
    pub const fn valid(self) -> bool {
        self.valid
    }
}

/// Allocation-free result shared by Rust, C++ parity tests, and HIP kernels.
/// Rank zero is kept internal as the fixed-width "not ranked" sentinel.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NativeFixed64StableTopKKernelOutcome {
    primary_slot_indices: [usize; FIXED64_CANDIDATE_COUNT],
    primary_count: usize,
    valid_slot_indices: [usize; FIXED64_CANDIDATE_COUNT],
    valid_count: usize,
    stable_rank: [usize; FIXED64_CANDIDATE_COUNT],
    stable_valid_rank: [usize; FIXED64_CANDIDATE_COUNT],
}

impl NativeFixed64StableTopKKernelOutcome {
    #[must_use]
    pub fn primary_slot_indices(&self) -> &[usize] {
        &self.primary_slot_indices[..self.primary_count]
    }

    #[must_use]
    pub fn valid_slot_indices(&self) -> &[usize] {
        &self.valid_slot_indices[..self.valid_count]
    }

    #[must_use]
    pub fn top5_slot_indices(&self) -> &[usize] {
        &self.primary_slot_indices[..self.primary_count.min(NATIVE_FIXED64_TOP_K_LIMIT)]
    }

    #[must_use]
    pub fn valid_top5_slot_indices(&self) -> &[usize] {
        &self.valid_slot_indices[..self.valid_count.min(NATIVE_FIXED64_TOP_K_LIMIT)]
    }

    #[must_use]
    pub fn stable_rank(&self, slot_index: usize) -> Option<usize> {
        self.stable_rank
            .get(slot_index)
            .copied()
            .filter(|rank| *rank != 0)
    }

    #[must_use]
    pub fn stable_valid_rank(&self, slot_index: usize) -> Option<usize> {
        self.stable_valid_rank
            .get(slot_index)
            .copied()
            .filter(|rank| *rank != 0)
    }
}

/// Derive the frozen score-ascending, slot-ascending stable rankings without
/// heap allocation or result-dependent work. Coordinate identity remains the
/// final declared tie-break even though unique slot identity already resolves
/// every score tie in fixed64.
pub fn rank_native_fixed64_stable_top_k_kernel(
    rows: &[NativeFixed64StableTopKInputRow; FIXED64_CANDIDATE_COUNT],
) -> Result<NativeFixed64StableTopKKernelOutcome, NativeFixed64RankingError> {
    let mut primary = [(0usize, 0.0f64, [0u8; 32]); FIXED64_CANDIDATE_COUNT];
    let mut primary_count = 0usize;
    for (expected_slot, row) in rows.iter().copied().enumerate() {
        if row.slot_index != expected_slot {
            return Err(cross_wired("ranking input slot indices are cross-wired"));
        }
        let evidence = match (row.scorer_status, row.total_score, row.coordinate_sha256) {
            (NativeScorerV1RowStatus::Scored, Some(score), Some(coordinate_sha256))
                if score.is_finite() =>
            {
                Some((expected_slot, canonical_score(score), coordinate_sha256))
            }
            (NativeScorerV1RowStatus::TypedFailure, None, None) => None,
            _ => return Err(cross_wired("ranking row evidence shape is invalid")),
        };
        if (row.scorer_status == NativeScorerV1RowStatus::Scored
            && row.validity_status == NativeFixed64ValidityRowStatus::UpstreamScorerFailure)
            || (row.scorer_status == NativeScorerV1RowStatus::TypedFailure
                && row.validity_status != NativeFixed64ValidityRowStatus::UpstreamScorerFailure)
            || (row.validity_status != NativeFixed64ValidityRowStatus::Evaluated && row.valid)
        {
            return Err(cross_wired("ranking scorer/validity binding is invalid"));
        }
        let Some(entry) = evidence else {
            continue;
        };
        let mut position = primary_count;
        while position > 0 && ranking_cmp(entry, primary[position - 1]) == Ordering::Less {
            primary[position] = primary[position - 1];
            position -= 1;
        }
        primary[position] = entry;
        primary_count += 1;
    }

    let mut primary_slot_indices = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut valid_slot_indices = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut stable_rank = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut stable_valid_rank = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut valid_count = 0usize;
    for (offset, (slot_index, _, _)) in primary[..primary_count].iter().copied().enumerate() {
        primary_slot_indices[offset] = slot_index;
        stable_rank[slot_index] = offset + 1;
        let row = rows[slot_index];
        if row.validity_status == NativeFixed64ValidityRowStatus::Evaluated && row.valid {
            valid_slot_indices[valid_count] = slot_index;
            stable_valid_rank[slot_index] = valid_count + 1;
            valid_count += 1;
        }
    }
    Ok(NativeFixed64StableTopKKernelOutcome {
        primary_slot_indices,
        primary_count,
        valid_slot_indices,
        valid_count,
        stable_rank,
        stable_valid_rank,
    })
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64RankingRecord {
    slot_index: usize,
    scorer_row_receipt_sha256: [u8; 32],
    validity_row_receipt_sha256: [u8; 32],
    rank_eligible: bool,
    valid_rank_eligible: bool,
    total_score: Option<f64>,
    coordinate_sha256: Option<[u8; 32]>,
    stable_rank: Option<usize>,
    stable_valid_rank: Option<usize>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64RankingRecord {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn rank_eligible(&self) -> bool {
        self.rank_eligible
    }

    #[must_use]
    pub const fn valid_rank_eligible(&self) -> bool {
        self.valid_rank_eligible
    }

    #[must_use]
    pub const fn total_score(&self) -> Option<f64> {
        self.total_score
    }

    #[must_use]
    pub const fn coordinate_sha256(&self) -> Option<[u8; 32]> {
        self.coordinate_sha256
    }

    #[must_use]
    pub const fn stable_rank(&self) -> Option<usize> {
        self.stable_rank
    }

    #[must_use]
    pub const fn stable_valid_rank(&self) -> Option<usize> {
        self.stable_valid_rank
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let evidence_shape_valid = if self.rank_eligible {
            self.total_score.is_some_and(f64::is_finite)
                && self.coordinate_sha256.is_some()
                && self.stable_rank.is_some()
        } else {
            self.total_score.is_none()
                && self.coordinate_sha256.is_none()
                && self.stable_rank.is_none()
        };
        let valid_shape = if self.valid_rank_eligible {
            self.rank_eligible && self.stable_valid_rank.is_some()
        } else {
            self.stable_valid_rank.is_none()
        };
        evidence_shape_valid && valid_shape && record_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64RankingBatch {
    validity_batch: Box<NativeFixed64ValidityBatch>,
    records: Box<[NativeFixed64RankingRecord; FIXED64_CANDIDATE_COUNT]>,
    primary_ranking_slot_indices: Vec<usize>,
    valid_ranking_slot_indices: Vec<usize>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64RankingBatch {
    #[must_use]
    pub const fn validity_batch(&self) -> &NativeFixed64ValidityBatch {
        &self.validity_batch
    }

    #[must_use]
    pub const fn records(&self) -> &[NativeFixed64RankingRecord; FIXED64_CANDIDATE_COUNT] {
        &self.records
    }

    #[must_use]
    pub fn primary_ranking_slot_indices(&self) -> &[usize] {
        &self.primary_ranking_slot_indices
    }

    #[must_use]
    pub fn valid_ranking_slot_indices(&self) -> &[usize] {
        &self.valid_ranking_slot_indices
    }

    #[must_use]
    pub fn top1_slot_index(&self) -> Option<usize> {
        self.primary_ranking_slot_indices.first().copied()
    }

    #[must_use]
    pub fn top5_slot_indices(&self) -> &[usize] {
        &self.primary_ranking_slot_indices[..self
            .primary_ranking_slot_indices
            .len()
            .min(NATIVE_FIXED64_TOP_K_LIMIT)]
    }

    #[must_use]
    pub fn valid_top1_slot_index(&self) -> Option<usize> {
        self.valid_ranking_slot_indices.first().copied()
    }

    #[must_use]
    pub fn valid_top5_slot_indices(&self) -> &[usize] {
        &self.valid_ranking_slot_indices[..self
            .valid_ranking_slot_indices
            .len()
            .min(NATIVE_FIXED64_TOP_K_LIMIT)]
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn existing_rank_auto_change_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn customer_pose_emission_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn production_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        if !self.validity_batch.has_valid_receipt() {
            return false;
        }
        let Ok((records, primary, valid)) = derive(&self.validity_batch) else {
            return false;
        };
        self.records == records
            && self.primary_ranking_slot_indices == primary
            && self.valid_ranking_slot_indices == valid
            && batch_sha256(self) == self.receipt_sha256
    }
}

pub fn rank_native_fixed64_top_k(
    validity_batch: NativeFixed64ValidityBatch,
) -> Result<NativeFixed64RankingBatch, NativeFixed64RankingError> {
    if !validity_batch.has_valid_receipt() {
        return Err(cross_wired("pose validity batch receipt is invalid"));
    }
    let (records, primary_ranking_slot_indices, valid_ranking_slot_indices) =
        derive(&validity_batch)?;
    let mut value = NativeFixed64RankingBatch {
        validity_batch: Box::new(validity_batch),
        records,
        primary_ranking_slot_indices,
        valid_ranking_slot_indices,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = batch_sha256(&value);
    Ok(value)
}

type DerivedRanking = (
    Box<[NativeFixed64RankingRecord; FIXED64_CANDIDATE_COUNT]>,
    Vec<usize>,
    Vec<usize>,
);

fn derive(
    validity_batch: &NativeFixed64ValidityBatch,
) -> Result<DerivedRanking, NativeFixed64RankingError> {
    let scorer_rows = validity_batch.scorer_batch().rows();
    let validity_rows = validity_batch.rows();
    let mut kernel_rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for slot_index in 0..FIXED64_CANDIDATE_COUNT {
        let scorer = &scorer_rows[slot_index];
        let validity = &validity_rows[slot_index];
        if scorer.slot_index() != slot_index || validity.slot_index() != slot_index {
            return Err(cross_wired("ranking input slot indices are cross-wired"));
        }
        let terms = scorer.terms();
        kernel_rows.push(NativeFixed64StableTopKInputRow::new(
            slot_index,
            scorer.status(),
            validity.status(),
            terms.map(|value| value.total_score()),
            terms.map(|value| value.coordinate_sha256()),
            validity.valid(),
        )?);
    }
    let kernel_rows: [NativeFixed64StableTopKInputRow; FIXED64_CANDIDATE_COUNT] = kernel_rows
        .try_into()
        .map_err(|_| internal("ranking kernel denominator changed"))?;
    let kernel = rank_native_fixed64_stable_top_k_kernel(&kernel_rows)?;
    let primary_ranking_slot_indices = kernel.primary_slot_indices().to_vec();
    let valid_ranking_slot_indices = kernel.valid_slot_indices().to_vec();
    let mut records = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for slot_index in 0..FIXED64_CANDIDATE_COUNT {
        let scorer = &scorer_rows[slot_index];
        let validity = &validity_rows[slot_index];
        let terms = scorer.terms();
        let rank_eligible = scorer.status() == NativeScorerV1RowStatus::Scored;
        let valid_rank_eligible = rank_eligible
            && validity.status() == NativeFixed64ValidityRowStatus::Evaluated
            && validity.valid();
        let mut record = NativeFixed64RankingRecord {
            slot_index,
            scorer_row_receipt_sha256: scorer.receipt_sha256(),
            validity_row_receipt_sha256: validity.receipt_sha256(),
            rank_eligible,
            valid_rank_eligible,
            total_score: terms.map(|value| canonical_score(value.total_score())),
            coordinate_sha256: terms.map(|value| value.coordinate_sha256()),
            stable_rank: kernel.stable_rank(slot_index),
            stable_valid_rank: kernel.stable_valid_rank(slot_index),
            receipt_sha256: [0; 32],
        };
        if rank_eligible != terms.is_some()
            || rank_eligible != record.stable_rank.is_some()
            || valid_rank_eligible != record.stable_valid_rank.is_some()
        {
            return Err(internal("ranking eligibility and evidence shape disagree"));
        }
        record.receipt_sha256 = record_sha256(&record);
        records.push(record);
    }
    let records = records
        .into_boxed_slice()
        .try_into()
        .map_err(|_| internal("ranking record denominator changed"))?;
    Ok((
        records,
        primary_ranking_slot_indices,
        valid_ranking_slot_indices,
    ))
}

fn ranking_cmp(left: (usize, f64, [u8; 32]), right: (usize, f64, [u8; 32])) -> Ordering {
    left.1
        .total_cmp(&right.1)
        .then_with(|| left.0.cmp(&right.0))
        .then_with(|| left.2.cmp(&right.2))
}

fn canonical_score(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

fn record_sha256(value: &NativeFixed64RankingRecord) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_RANKING_RECORD_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_RANKING_ALGORITHM_ID);
    hash.usize(value.slot_index);
    hash.digest(value.scorer_row_receipt_sha256);
    hash.digest(value.validity_row_receipt_sha256);
    hash.bool(value.rank_eligible);
    hash.bool(value.valid_rank_eligible);
    hash.option(value.total_score, |hash, score| hash.f64(score));
    hash.option(value.coordinate_sha256, |hash, digest| hash.digest(digest));
    hash.option(value.stable_rank, |hash, rank| hash.usize(rank));
    hash.option(value.stable_valid_rank, |hash, rank| hash.usize(rank));
    hash.finish()
}

fn batch_sha256(value: &NativeFixed64RankingBatch) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_RANKING_BATCH_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_RANKING_ALGORITHM_ID);
    hash.string(NATIVE_FIXED64_PRIMARY_RANKING_SEMANTICS);
    hash.string(NATIVE_FIXED64_VALID_RANKING_SEMANTICS);
    hash.usize(NATIVE_FIXED64_TOP_K_LIMIT);
    hash.digest(value.validity_batch.receipt_sha256());
    hash.usize(value.records.len());
    for record in value.records.iter() {
        hash.digest(record.receipt_sha256);
    }
    hash.usize(value.primary_ranking_slot_indices.len());
    for slot_index in &value.primary_ranking_slot_indices {
        hash.usize(*slot_index);
    }
    hash.usize(value.valid_ranking_slot_indices.len());
    for slot_index in &value.valid_ranking_slot_indices {
        hash.usize(*slot_index);
    }
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

const fn cross_wired(message: &'static str) -> NativeFixed64RankingError {
    NativeFixed64RankingError::new(NativeFixed64RankingErrorCode::UpstreamCrossWired, message)
}

const fn internal(message: &'static str) -> NativeFixed64RankingError {
    NativeFixed64RankingError::new(NativeFixed64RankingErrorCode::InternalInvariant, message)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scored(slot: usize, score: f64, valid: bool) -> NativeFixed64StableTopKInputRow {
        let mut digest = [0u8; 32];
        digest[0] = u8::try_from(slot + 1).unwrap();
        NativeFixed64StableTopKInputRow::new(
            slot,
            NativeScorerV1RowStatus::Scored,
            NativeFixed64ValidityRowStatus::Evaluated,
            Some(score),
            Some(digest),
            valid,
        )
        .unwrap()
    }

    fn failed(slot: usize) -> NativeFixed64StableTopKInputRow {
        NativeFixed64StableTopKInputRow::new(
            slot,
            NativeScorerV1RowStatus::TypedFailure,
            NativeFixed64ValidityRowStatus::UpstreamScorerFailure,
            None,
            None,
            false,
        )
        .unwrap()
    }

    #[test]
    fn reusable_kernel_is_fixed_width_stable_and_canonicalizes_zero() {
        let rows = core::array::from_fn(|slot| match slot {
            0 => scored(slot, 2.0, true),
            1 | 2 => scored(slot, -1.0, true),
            3 => scored(slot, -0.0, false),
            _ => failed(slot),
        });
        let first = rank_native_fixed64_stable_top_k_kernel(&rows).unwrap();
        let second = rank_native_fixed64_stable_top_k_kernel(&rows).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.primary_slot_indices(), &[1, 2, 3, 0]);
        assert_eq!(first.valid_slot_indices(), &[1, 2, 0]);
        assert_eq!(first.top5_slot_indices(), &[1, 2, 3, 0]);
        assert_eq!(first.stable_rank(3), Some(3));
        assert_eq!(first.stable_valid_rank(3), None);
        assert!(!rows[3].total_score().unwrap().is_sign_negative());
    }

    #[test]
    fn reusable_kernel_rejects_invalid_shapes_and_slot_cross_wiring() {
        assert!(NativeFixed64StableTopKInputRow::new(
            0,
            NativeScorerV1RowStatus::Scored,
            NativeFixed64ValidityRowStatus::Evaluated,
            None,
            Some([1; 32]),
            true,
        )
        .is_err());
        let rows = core::array::from_fn(|slot| failed(if slot == 0 { 1 } else { slot }));
        let error = rank_native_fixed64_stable_top_k_kernel(&rows).unwrap_err();
        assert_eq!(
            error.code(),
            NativeFixed64RankingErrorCode::UpstreamCrossWired
        );
    }
}
