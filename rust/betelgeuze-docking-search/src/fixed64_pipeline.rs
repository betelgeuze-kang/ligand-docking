use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    evaluate_native_fixed64_pose_validity, produce_native_fixed64_proposals,
    rank_native_fixed64_top_k, score_native_fixed64_scorer_v1, Fixed64GeometricBatch,
    Fixed64ProposalSourceBundle, NativeFixed64RankingBatch, NativeFixed64ValidityContext,
    NativeScorerV1Context, FIXED64_CANDIDATE_COUNT, FIXED64_PROFILE_ID,
};

pub const NATIVE_FIXED64_PIPELINE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pipeline_receipt/1.0.0";
pub const NATIVE_FIXED64_CONSUMER_VIEW_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_consumer_view/1.0.0";
pub const NATIVE_FIXED64_PIPELINE_ID: &str =
    "fixed64_proposal_admission_scorer_v1_validity_stable_top_k/1.0.0";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64PipelineStage {
    Input,
    Proposal,
    GeometricAdmission,
    ScorerV1,
    PoseValidity,
    StableTopK,
}

impl NativeFixed64PipelineStage {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::Input => "input",
            Self::Proposal => "proposal",
            Self::GeometricAdmission => "geometric_admission",
            Self::ScorerV1 => "scorer_v1",
            Self::PoseValidity => "pose_validity",
            Self::StableTopK => "stable_top_k",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeFixed64PipelineError {
    stage: NativeFixed64PipelineStage,
    message: &'static str,
}

impl NativeFixed64PipelineError {
    const fn new(stage: NativeFixed64PipelineStage, message: &'static str) -> Self {
        Self { stage, message }
    }

    #[must_use]
    pub const fn stage(self) -> NativeFixed64PipelineStage {
        self.stage
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeFixed64PipelineError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "native fixed64 pipeline {}: {}",
            self.stage.id(),
            self.message
        )
    }
}

impl std::error::Error for NativeFixed64PipelineError {}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64AuthorityBlocker {
    ExternalReservationProviderNotOperational,
    ExternalReservationEndpointNotConfigured,
    ExternalReservationTrustAnchorNotConfigured,
    HistoricalExecutionOperationalAuthorityFalse,
}

impl NativeFixed64AuthorityBlocker {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::ExternalReservationProviderNotOperational => {
                "external_reservation_provider_not_operational"
            }
            Self::ExternalReservationEndpointNotConfigured => {
                "external_reservation_endpoint_not_configured"
            }
            Self::ExternalReservationTrustAnchorNotConfigured => {
                "external_reservation_trust_anchor_not_configured"
            }
            Self::HistoricalExecutionOperationalAuthorityFalse => {
                "historical_execution_operational_authority_false"
            }
        }
    }
}

pub const NATIVE_FIXED64_AUTHORITY_BLOCKERS: [NativeFixed64AuthorityBlocker; 4] = [
    NativeFixed64AuthorityBlocker::ExternalReservationProviderNotOperational,
    NativeFixed64AuthorityBlocker::ExternalReservationEndpointNotConfigured,
    NativeFixed64AuthorityBlocker::ExternalReservationTrustAnchorNotConfigured,
    NativeFixed64AuthorityBlocker::HistoricalExecutionOperationalAuthorityFalse,
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64Consumer {
    Cli,
    Benchmark,
    Api,
    ProductShadow,
}

impl NativeFixed64Consumer {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::Cli => "cli",
            Self::Benchmark => "benchmark",
            Self::Api => "api",
            Self::ProductShadow => "product_shadow",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64PipelineReceipt {
    ranking: Box<NativeFixed64RankingBatch>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64PipelineReceipt {
    #[must_use]
    pub const fn ranking(&self) -> &NativeFixed64RankingBatch {
        &self.ranking
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn candidate_denominator(&self) -> usize {
        FIXED64_CANDIDATE_COUNT
    }

    #[must_use]
    pub fn generated_count(&self) -> usize {
        self.proposal_batch()
            .map_or(0, crate::Fixed64ProposalBatch::generated_count)
    }

    #[must_use]
    pub fn accepted_count(&self) -> usize {
        self.admission().accepted_count()
    }

    #[must_use]
    pub fn scored_count(&self) -> usize {
        self.scorer_batch().scored_count()
    }

    #[must_use]
    pub fn evaluated_count(&self) -> usize {
        self.validity_batch().evaluated_count()
    }

    #[must_use]
    pub fn valid_count(&self) -> usize {
        self.validity_batch().valid_count()
    }

    #[must_use]
    pub const fn evidence_display_authorized(&self) -> bool {
        true
    }

    #[must_use]
    pub const fn operator_second_opinion_authorized(&self) -> bool {
        true
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn reservation_authorized(&self) -> bool {
        false
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
    pub const fn authority_blockers(&self) -> &'static [NativeFixed64AuthorityBlocker; 4] {
        &NATIVE_FIXED64_AUTHORITY_BLOCKERS
    }

    #[must_use]
    pub fn consumer_view(&self, consumer: NativeFixed64Consumer) -> NativeFixed64ConsumerView {
        NativeFixed64ConsumerView::new(self, consumer)
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let admission = self.admission();
        let Some(proposals) = admission.proposal_batch() else {
            return false;
        };
        proposals.has_valid_receipt()
            && admission.has_valid_receipt()
            && self.scorer_batch().has_valid_receipt()
            && self.validity_batch().has_valid_receipt()
            && self.ranking.has_valid_receipt()
            && proposals.records().len() == FIXED64_CANDIDATE_COUNT
            && admission.decisions().len() == FIXED64_CANDIDATE_COUNT
            && self.scorer_batch().rows().len() == FIXED64_CANDIDATE_COUNT
            && self.validity_batch().rows().len() == FIXED64_CANDIDATE_COUNT
            && self.ranking.records().len() == FIXED64_CANDIDATE_COUNT
            && proposals.generated_count() + proposals.typed_failure_count()
                == FIXED64_CANDIDATE_COUNT
            && admission.accepted_count()
                + admission.geometric_rejected_count()
                + admission.typed_generation_failure_count()
                == FIXED64_CANDIDATE_COUNT
            && self.scorer_batch().scored_count() + self.scorer_batch().typed_failure_count()
                == FIXED64_CANDIDATE_COUNT
            && pipeline_sha256(&self.ranking) == self.receipt_sha256
    }

    fn validity_batch(&self) -> &crate::NativeFixed64ValidityBatch {
        self.ranking.validity_batch()
    }

    fn scorer_batch(&self) -> &crate::NativeScorerV1Batch {
        self.validity_batch().scorer_batch()
    }

    fn admission(&self) -> &Fixed64GeometricBatch {
        self.scorer_batch().admission()
    }

    fn proposal_batch(&self) -> Option<&crate::Fixed64ProposalBatch> {
        self.admission().proposal_batch()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NativeFixed64ConsumerView {
    consumer: NativeFixed64Consumer,
    pipeline_receipt_sha256: [u8; 32],
    allocation_receipt_sha256: [u8; 32],
    ranking_receipt_sha256: [u8; 32],
    candidate_denominator: usize,
    top5_slot_indices: Vec<usize>,
    valid_top5_slot_indices: Vec<usize>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64ConsumerView {
    fn new(pipeline: &NativeFixed64PipelineReceipt, consumer: NativeFixed64Consumer) -> Self {
        let mut value = Self {
            consumer,
            pipeline_receipt_sha256: pipeline.receipt_sha256,
            allocation_receipt_sha256: pipeline.admission().allocation().receipt_sha256(),
            ranking_receipt_sha256: pipeline.ranking.receipt_sha256(),
            candidate_denominator: FIXED64_CANDIDATE_COUNT,
            top5_slot_indices: pipeline.ranking.top5_slot_indices().to_vec(),
            valid_top5_slot_indices: pipeline.ranking.valid_top5_slot_indices().to_vec(),
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = consumer_view_sha256(&value);
        value
    }

    #[must_use]
    pub const fn consumer(&self) -> NativeFixed64Consumer {
        self.consumer
    }

    #[must_use]
    pub const fn pipeline_receipt_sha256(&self) -> [u8; 32] {
        self.pipeline_receipt_sha256
    }

    #[must_use]
    pub const fn allocation_receipt_sha256(&self) -> [u8; 32] {
        self.allocation_receipt_sha256
    }

    #[must_use]
    pub const fn ranking_receipt_sha256(&self) -> [u8; 32] {
        self.ranking_receipt_sha256
    }

    #[must_use]
    pub const fn candidate_denominator(&self) -> usize {
        self.candidate_denominator
    }

    #[must_use]
    pub fn top5_slot_indices(&self) -> &[usize] {
        &self.top5_slot_indices
    }

    #[must_use]
    pub fn valid_top5_slot_indices(&self) -> &[usize] {
        &self.valid_top5_slot_indices
    }

    #[must_use]
    pub const fn evidence_display_authorized(&self) -> bool {
        true
    }

    #[must_use]
    pub const fn operator_second_opinion_authorized(&self) -> bool {
        true
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
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn verifies_against(&self, pipeline: &NativeFixed64PipelineReceipt) -> bool {
        pipeline.has_valid_receipt()
            && self.pipeline_receipt_sha256 == pipeline.receipt_sha256()
            && self.allocation_receipt_sha256 == pipeline.admission().allocation().receipt_sha256()
            && self.ranking_receipt_sha256 == pipeline.ranking().receipt_sha256()
            && self.candidate_denominator == FIXED64_CANDIDATE_COUNT
            && self.top5_slot_indices == pipeline.ranking().top5_slot_indices()
            && self.valid_top5_slot_indices == pipeline.ranking().valid_top5_slot_indices()
            && consumer_view_sha256(self) == self.receipt_sha256
    }
}

pub fn run_native_fixed64_pipeline(
    source_bundle: Fixed64ProposalSourceBundle,
    scorer_context: NativeScorerV1Context,
    validity_context: NativeFixed64ValidityContext,
) -> Result<NativeFixed64PipelineReceipt, NativeFixed64PipelineError> {
    if !source_bundle.has_valid_receipt()
        || !scorer_context.has_valid_receipt()
        || !validity_context.has_valid_receipt()
    {
        return Err(NativeFixed64PipelineError::new(
            NativeFixed64PipelineStage::Input,
            "one or more input receipts are invalid",
        ));
    }
    if validity_context.scorer_context_receipt_sha256() != scorer_context.receipt_sha256() {
        return Err(NativeFixed64PipelineError::new(
            NativeFixed64PipelineStage::Input,
            "validity context is cross-wired to another scorer context",
        ));
    }

    let proposals = proposal_stage(source_bundle)?;
    let admission = geometric_admission_stage(proposals)?;
    let scorer = scorer_v1_stage(admission, scorer_context)?;
    let validity = pose_validity_stage(scorer, validity_context)?;
    let ranking = stable_top_k_stage(validity)?;
    let receipt_sha256 = pipeline_sha256(&ranking);
    let value = NativeFixed64PipelineReceipt {
        ranking,
        receipt_sha256,
    };
    if !value.has_valid_receipt() {
        return Err(NativeFixed64PipelineError::new(
            NativeFixed64PipelineStage::StableTopK,
            "composed pipeline receipt failed self-verification",
        ));
    }
    Ok(value)
}

// Keep each fixed-denominator stage in a separate frame and heap-own its output. Besides avoiding
// large debug-stack frames, this makes ownership transfer across future C ABI/HIP providers
// explicit: a completed stage is immutable before the next stage can consume it.
#[inline(never)]
fn proposal_stage(
    source_bundle: Fixed64ProposalSourceBundle,
) -> Result<Box<crate::Fixed64ProposalBatch>, NativeFixed64PipelineError> {
    let allocation = source_bundle.allocation().clone();
    produce_native_fixed64_proposals(&allocation, source_bundle)
        .map(Box::new)
        .map_err(|error| {
            NativeFixed64PipelineError::new(NativeFixed64PipelineStage::Proposal, error.message())
        })
}

#[inline(never)]
fn geometric_admission_stage(
    proposals: Box<crate::Fixed64ProposalBatch>,
) -> Result<Box<Fixed64GeometricBatch>, NativeFixed64PipelineError> {
    Fixed64GeometricBatch::evaluate_proposals(*proposals)
        .map(Box::new)
        .map_err(|error| {
            NativeFixed64PipelineError::new(
                NativeFixed64PipelineStage::GeometricAdmission,
                error.message(),
            )
        })
}

#[inline(never)]
fn scorer_v1_stage(
    admission: Box<Fixed64GeometricBatch>,
    context: NativeScorerV1Context,
) -> Result<Box<crate::NativeScorerV1Batch>, NativeFixed64PipelineError> {
    score_native_fixed64_scorer_v1(*admission, context)
        .map(Box::new)
        .map_err(|error| {
            NativeFixed64PipelineError::new(NativeFixed64PipelineStage::ScorerV1, error.message())
        })
}

#[inline(never)]
fn pose_validity_stage(
    scorer: Box<crate::NativeScorerV1Batch>,
    context: NativeFixed64ValidityContext,
) -> Result<Box<crate::NativeFixed64ValidityBatch>, NativeFixed64PipelineError> {
    evaluate_native_fixed64_pose_validity(*scorer, context)
        .map(Box::new)
        .map_err(|error| {
            NativeFixed64PipelineError::new(
                NativeFixed64PipelineStage::PoseValidity,
                error.message(),
            )
        })
}

#[inline(never)]
fn stable_top_k_stage(
    validity: Box<crate::NativeFixed64ValidityBatch>,
) -> Result<Box<NativeFixed64RankingBatch>, NativeFixed64PipelineError> {
    rank_native_fixed64_top_k(*validity)
        .map(Box::new)
        .map_err(|error| {
            NativeFixed64PipelineError::new(NativeFixed64PipelineStage::StableTopK, error.message())
        })
}

fn pipeline_sha256(ranking: &NativeFixed64RankingBatch) -> [u8; 32] {
    let validity = ranking.validity_batch();
    let scorer = validity.scorer_batch();
    let admission = scorer.admission();
    let proposals = admission
        .proposal_batch()
        .expect("pipeline receipt requires proposal evidence");
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_PIPELINE_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_PIPELINE_ID);
    hash.string(FIXED64_PROFILE_ID);
    hash.usize(FIXED64_CANDIDATE_COUNT);
    hash.digest(proposals.allocation().receipt_sha256());
    hash.digest(proposals.source_bundle().receipt_sha256());
    hash.digest(proposals.receipt_sha256());
    hash.digest(admission.receipt_sha256());
    hash.digest(scorer.context().receipt_sha256());
    hash.string(scorer.context().backend().id());
    hash.digest(scorer.receipt_sha256());
    hash.digest(validity.context().receipt_sha256());
    hash.string(validity.context().backend().id());
    hash.digest(validity.receipt_sha256());
    hash.digest(ranking.receipt_sha256());
    hash.usize(proposals.generated_count());
    hash.usize(proposals.typed_failure_count());
    hash.usize(admission.accepted_count());
    hash.usize(admission.geometric_rejected_count());
    hash.usize(admission.typed_generation_failure_count());
    hash.usize(scorer.scored_count());
    hash.usize(scorer.typed_failure_count());
    hash.usize(validity.evaluated_count());
    hash.usize(validity.valid_count());
    hash.usize(ranking.primary_ranking_slot_indices().len());
    hash.usize(ranking.valid_ranking_slot_indices().len());
    for blocker in NATIVE_FIXED64_AUTHORITY_BLOCKERS {
        hash.string(blocker.id());
    }
    hash.bool(true);
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn consumer_view_sha256(value: &NativeFixed64ConsumerView) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_CONSUMER_VIEW_SCHEMA_ID);
    hash.string(value.consumer.id());
    hash.digest(value.pipeline_receipt_sha256);
    hash.digest(value.allocation_receipt_sha256);
    hash.digest(value.ranking_receipt_sha256);
    hash.usize(value.candidate_denominator);
    hash.usize(value.top5_slot_indices.len());
    for slot_index in &value.top5_slot_indices {
        hash.usize(*slot_index);
    }
    hash.usize(value.valid_top5_slot_indices.len());
    for slot_index in &value.valid_top5_slot_indices {
        hash.usize(*slot_index);
    }
    hash.bool(true);
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}
