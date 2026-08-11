use std::collections::BTreeSet;
use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    generate_native_fixed64_indexed_so3, generate_native_fixed64_single_anchor,
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, Fixed64Allocation, Fixed64FeatureGeometryInventory,
    Fixed64GeometricInput, Fixed64IndexedSo3Placement, Fixed64Lane, Fixed64MissingFeature,
    Fixed64PlacementErrorCode, Fixed64PlacementSource, Fixed64SingleAnchorPlacement,
    Fixed64SourceEvidence, Vec3, FIXED64_CANDIDATE_COUNT, FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM,
    RETAINED_SOURCE_INDICES,
};

pub const NATIVE_FIXED64_COORDINATE_SOURCE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_coordinate_source/1.0.0";
pub const NATIVE_FIXED64_SOURCE_BUNDLE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_source_bundle/1.0.0";
pub const NATIVE_FIXED64_PASSTHROUGH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_exact_passthrough/1.0.0";
pub const NATIVE_FIXED64_GENERATION_FAILURE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_generation_failure/1.0.0";
pub const NATIVE_FIXED64_PROPOSAL_RECORD_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_proposal_record/1.0.0";
pub const NATIVE_FIXED64_PRODUCER_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_producer_batch/1.0.0";
pub const NATIVE_FIXED64_PRODUCER_PROFILE_ID: &str =
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_producer/1.0.0";

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Fixed64CoordinateSourceKind {
    ExactV11Base,
    V7Control,
    TrueConformer,
    RetainedControl,
}

impl Fixed64CoordinateSourceKind {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::ExactV11Base => "exact_v11_base",
            Self::V7Control => "v7_control",
            Self::TrueConformer => "true_conformer",
            Self::RetainedControl => "retained_control",
        }
    }

    const fn tag(self) -> u8 {
        match self {
            Self::ExactV11Base => 0,
            Self::V7Control => 1,
            Self::TrueConformer => 2,
            Self::RetainedControl => 3,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64ProducerErrorCode {
    InvalidInput,
    AllocationCrossWired,
    SourcePayloadCrossWired,
    ExactSystemCrossWired,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64ProducerError {
    code: Fixed64ProducerErrorCode,
    message: &'static str,
}

impl Fixed64ProducerError {
    const fn new(code: Fixed64ProducerErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> Fixed64ProducerErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for Fixed64ProducerError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "native fixed64 proposal producer: {}",
            self.message
        )
    }
}

impl std::error::Error for Fixed64ProducerError {}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64CoordinateSourcePayload {
    source_kind: Fixed64CoordinateSourceKind,
    source_ordinal: Option<u32>,
    source: Fixed64PlacementSource,
    receipt_sha256: [u8; 32],
}

impl Fixed64CoordinateSourcePayload {
    pub fn new(
        source_kind: Fixed64CoordinateSourceKind,
        source_ordinal: Option<u32>,
        evidence: Fixed64SourceEvidence,
        coordinates_angstrom: Vec<Vec3>,
    ) -> Result<Self, Fixed64ProducerError> {
        if !source_ordinal_valid(source_kind, source_ordinal) {
            return Err(source_cross_wired("source kind or ordinal is invalid"));
        }
        let source = Fixed64PlacementSource::new(evidence, coordinates_angstrom)
            .map_err(|_| source_cross_wired("source coordinate identity is invalid"))?;
        let mut value = Self {
            source_kind,
            source_ordinal,
            source,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = coordinate_source_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub const fn source_kind(&self) -> Fixed64CoordinateSourceKind {
        self.source_kind
    }

    #[must_use]
    pub const fn source_ordinal(&self) -> Option<u32> {
        self.source_ordinal
    }

    #[must_use]
    pub fn source(&self) -> &Fixed64PlacementSource {
        &self.source
    }

    #[must_use]
    pub const fn evidence(&self) -> Fixed64SourceEvidence {
        self.source.evidence()
    }

    #[must_use]
    pub fn coordinates_angstrom(&self) -> &[Vec3] {
        self.source.coordinates_angstrom()
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        source_ordinal_valid(self.source_kind, self.source_ordinal)
            && self.source.has_valid_receipt()
            && coordinate_source_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64ProposalSourceBundle {
    allocation: Fixed64Allocation,
    exact_v11_source: Option<Fixed64CoordinateSourcePayload>,
    v7_control_sources: Vec<Fixed64CoordinateSourcePayload>,
    conformer_sources: Vec<Fixed64CoordinateSourcePayload>,
    retained_sources: Vec<Fixed64CoordinateSourcePayload>,
    feature_geometry_inventory: Fixed64FeatureGeometryInventory,
    geometric_input: Fixed64GeometricInput,
    pocket_normal: Vec3,
    receipt_sha256: [u8; 32],
}

impl Fixed64ProposalSourceBundle {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        allocation: &Fixed64Allocation,
        exact_v11_source: Option<Fixed64CoordinateSourcePayload>,
        v7_control_sources: Vec<Fixed64CoordinateSourcePayload>,
        conformer_sources: Vec<Fixed64CoordinateSourcePayload>,
        retained_sources: Vec<Fixed64CoordinateSourcePayload>,
        feature_geometry_inventory: Fixed64FeatureGeometryInventory,
        geometric_input: Fixed64GeometricInput,
        pocket_normal: Vec3,
    ) -> Result<Self, Fixed64ProducerError> {
        if !allocation.has_valid_receipt()
            || !feature_geometry_inventory.has_valid_receipt()
            || !geometric_input.has_valid_receipt()
        {
            return Err(cross_wired(
                "allocation, feature geometry, or geometric input receipt is invalid",
            ));
        }
        validate_exact_system(allocation, &geometric_input)?;
        let pocket_normal = normalized_pocket_normal(pocket_normal)?;
        if let Some(source) = exact_v11_source.as_ref() {
            validate_source_payload(
                allocation,
                source,
                Fixed64CoordinateSourceKind::ExactV11Base,
            )?;
        }
        validate_source_group(
            allocation,
            &v7_control_sources,
            Fixed64CoordinateSourceKind::V7Control,
        )?;
        validate_source_group(
            allocation,
            &conformer_sources,
            Fixed64CoordinateSourceKind::TrueConformer,
        )?;
        validate_source_group(
            allocation,
            &retained_sources,
            Fixed64CoordinateSourceKind::RetainedControl,
        )?;
        let receipts = exact_v11_source
            .iter()
            .chain(&v7_control_sources)
            .chain(&conformer_sources)
            .chain(&retained_sources)
            .map(Fixed64CoordinateSourcePayload::receipt_sha256)
            .collect::<Vec<_>>();
        if receipts.iter().copied().collect::<BTreeSet<_>>().len() != receipts.len() {
            return Err(source_cross_wired(
                "coordinate source payload receipts are duplicated",
            ));
        }
        let mut value = Self {
            allocation: allocation.clone(),
            exact_v11_source,
            v7_control_sources,
            conformer_sources,
            retained_sources,
            feature_geometry_inventory,
            geometric_input,
            pocket_normal,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = source_bundle_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub fn allocation(&self) -> &Fixed64Allocation {
        &self.allocation
    }

    #[must_use]
    pub fn exact_v11_source(&self) -> Option<&Fixed64CoordinateSourcePayload> {
        self.exact_v11_source.as_ref()
    }

    #[must_use]
    pub fn v7_control_sources(&self) -> &[Fixed64CoordinateSourcePayload] {
        &self.v7_control_sources
    }

    #[must_use]
    pub fn conformer_sources(&self) -> &[Fixed64CoordinateSourcePayload] {
        &self.conformer_sources
    }

    #[must_use]
    pub fn retained_sources(&self) -> &[Fixed64CoordinateSourcePayload] {
        &self.retained_sources
    }

    #[must_use]
    pub fn feature_geometry_inventory(&self) -> &Fixed64FeatureGeometryInventory {
        &self.feature_geometry_inventory
    }

    #[must_use]
    pub fn geometric_input(&self) -> &Fixed64GeometricInput {
        &self.geometric_input
    }

    #[must_use]
    pub const fn pocket_normal(&self) -> Vec3 {
        self.pocket_normal
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.allocation.has_valid_receipt()
            && self.feature_geometry_inventory.has_valid_receipt()
            && self.geometric_input.has_valid_receipt()
            && validate_exact_system(&self.allocation, &self.geometric_input).is_ok()
            && pocket_normal_is_unit(self.pocket_normal)
            && self.exact_v11_source.as_ref().is_none_or(|source| {
                validate_source_payload(
                    &self.allocation,
                    source,
                    Fixed64CoordinateSourceKind::ExactV11Base,
                )
                .is_ok()
            })
            && validate_source_group(
                &self.allocation,
                &self.v7_control_sources,
                Fixed64CoordinateSourceKind::V7Control,
            )
            .is_ok()
            && validate_source_group(
                &self.allocation,
                &self.conformer_sources,
                Fixed64CoordinateSourceKind::TrueConformer,
            )
            .is_ok()
            && validate_source_group(
                &self.allocation,
                &self.retained_sources,
                Fixed64CoordinateSourceKind::RetainedControl,
            )
            .is_ok()
            && source_bundle_sha256(self) == self.receipt_sha256
    }

    fn source_for_slot(&self, slot_index: usize) -> Option<&Fixed64CoordinateSourcePayload> {
        let slot = &self.allocation.slots()[slot_index];
        match slot.lane() {
            Fixed64Lane::PocketCenteredControls | Fixed64Lane::UniformSourceControls => {
                let index = slot.v7_control_source_index()?;
                self.v7_control_sources
                    .iter()
                    .find(|source| source.source_ordinal == Some(index))
            }
            Fixed64Lane::TrueConformerIndependentSo3 => {
                let rank = u32::from(slot.true_conformer_rank()?);
                self.conformer_sources
                    .iter()
                    .find(|source| source.source_ordinal == Some(rank))
            }
            Fixed64Lane::PairedRetainedControls => {
                let index = slot.retained_source_index()?;
                self.retained_sources
                    .iter()
                    .find(|source| source.source_ordinal == Some(index))
            }
            _ => self.exact_v11_source.as_ref(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64PassthroughPlacement {
    allocation_receipt_sha256: [u8; 32],
    allocation_slot_receipt_sha256: [u8; 32],
    source_bundle_receipt_sha256: [u8; 32],
    slot_index: usize,
    lane: Fixed64Lane,
    source_payload: Fixed64CoordinateSourcePayload,
    output_coordinates_angstrom: Vec<Vec3>,
    output_coordinate_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

impl Fixed64PassthroughPlacement {
    fn new(
        allocation: &Fixed64Allocation,
        source_bundle_receipt_sha256: [u8; 32],
        slot_index: usize,
        source_payload: Fixed64CoordinateSourcePayload,
    ) -> Result<Self, Fixed64ProducerError> {
        let slot = allocation
            .slots()
            .get(slot_index)
            .ok_or_else(|| cross_wired("passthrough slot is outside fixed64"))?;
        if !slot.generation_eligible()
            || !matches!(
                slot.lane(),
                Fixed64Lane::PocketCenteredControls
                    | Fixed64Lane::UniformSourceControls
                    | Fixed64Lane::PairedRetainedControls
            )
        {
            return Err(cross_wired("slot is not a ready passthrough lane"));
        }
        validate_source_for_slot(allocation, slot_index, &source_payload)?;
        let output_coordinates_angstrom = source_payload.coordinates_angstrom().to_vec();
        let output_coordinate_sha256 = source_payload.evidence().coordinate_sha256;
        let mut value = Self {
            allocation_receipt_sha256: allocation.receipt_sha256(),
            allocation_slot_receipt_sha256: slot.receipt_sha256(),
            source_bundle_receipt_sha256,
            slot_index,
            lane: slot.lane(),
            source_payload,
            output_coordinates_angstrom,
            output_coordinate_sha256,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = passthrough_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn lane(&self) -> Fixed64Lane {
        self.lane
    }

    #[must_use]
    pub fn source_payload(&self) -> &Fixed64CoordinateSourcePayload {
        &self.source_payload
    }

    #[must_use]
    pub fn output_coordinates_angstrom(&self) -> &[Vec3] {
        &self.output_coordinates_angstrom
    }

    #[must_use]
    pub const fn output_coordinate_sha256(&self) -> [u8; 32] {
        self.output_coordinate_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.source_payload.has_valid_receipt()
            && self.output_coordinates_angstrom == self.source_payload.coordinates_angstrom()
            && native_fixed64_coordinate_sha256(&self.output_coordinates_angstrom)
                .is_ok_and(|value| value == self.output_coordinate_sha256)
            && passthrough_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum Fixed64ProposalPlacement {
    ExactPassthrough(Box<Fixed64PassthroughPlacement>),
    IndexedSo3(Box<Fixed64IndexedSo3Placement>),
    SingleAnchor(Box<Fixed64SingleAnchorPlacement>),
}

impl Fixed64ProposalPlacement {
    #[must_use]
    pub fn output_coordinates_angstrom(&self) -> &[Vec3] {
        match self {
            Self::ExactPassthrough(value) => value.output_coordinates_angstrom(),
            Self::IndexedSo3(value) => value.output_coordinates_angstrom(),
            Self::SingleAnchor(value) => value.output_coordinates_angstrom(),
        }
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        match self {
            Self::ExactPassthrough(value) => value.receipt_sha256(),
            Self::IndexedSo3(value) => value.receipt_sha256(),
            Self::SingleAnchor(value) => value.receipt_sha256(),
        }
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        match self {
            Self::ExactPassthrough(value) => value.has_valid_receipt(),
            Self::IndexedSo3(value) => value.has_valid_receipt(),
            Self::SingleAnchor(value) => value.has_valid_receipt(),
        }
    }

    const fn tag(&self) -> u8 {
        match self {
            Self::ExactPassthrough(_) => 0,
            Self::IndexedSo3(_) => 1,
            Self::SingleAnchor(_) => 2,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64ProposalFailureCode {
    AllocationMissingFeature,
    MissingExactV11Source,
    MissingV7ControlSource,
    MissingConformerSource,
    MissingRetainedSource,
    LigandAtomDenominatorMismatch,
    SourcePayloadCrossWired,
    Placement(Fixed64PlacementErrorCode),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fixed64ProposalGenerationFailure {
    slot_index: usize,
    allocation_slot_receipt_sha256: [u8; 32],
    source_bundle_receipt_sha256: [u8; 32],
    failure_code: Fixed64ProposalFailureCode,
    allocation_missing_features: Vec<Fixed64MissingFeature>,
    attempted_source_payload_receipt_sha256: Option<[u8; 32]>,
    receipt_sha256: [u8; 32],
}

impl Fixed64ProposalGenerationFailure {
    #[must_use]
    pub const fn failure_code(&self) -> Fixed64ProposalFailureCode {
        self.failure_code
    }

    #[must_use]
    pub fn allocation_missing_features(&self) -> &[Fixed64MissingFeature] {
        &self.allocation_missing_features
    }

    #[must_use]
    pub const fn attempted_source_payload_receipt_sha256(&self) -> Option<[u8; 32]> {
        self.attempted_source_payload_receipt_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        generation_failure_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64ProposalStatus {
    Generated,
    TypedGenerationFailure,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64ProposalRecord {
    slot_index: usize,
    allocation_slot_receipt_sha256: [u8; 32],
    lane: Fixed64Lane,
    source_bundle_receipt_sha256: [u8; 32],
    status: Fixed64ProposalStatus,
    generation_input_source_payload_receipt_sha256: Option<[u8; 32]>,
    source_proposal_sha256: Option<[u8; 32]>,
    source_coordinate_sha256: Option<[u8; 32]>,
    output_coordinates_angstrom: Option<Vec<Vec3>>,
    placement: Option<Fixed64ProposalPlacement>,
    failure: Option<Fixed64ProposalGenerationFailure>,
    receipt_sha256: [u8; 32],
}

impl Fixed64ProposalRecord {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn lane(&self) -> Fixed64Lane {
        self.lane
    }

    #[must_use]
    pub const fn status(&self) -> Fixed64ProposalStatus {
        self.status
    }

    #[must_use]
    pub const fn generation_input_source_payload_receipt_sha256(&self) -> Option<[u8; 32]> {
        self.generation_input_source_payload_receipt_sha256
    }

    #[must_use]
    pub const fn source_proposal_sha256(&self) -> Option<[u8; 32]> {
        self.source_proposal_sha256
    }

    #[must_use]
    pub const fn source_coordinate_sha256(&self) -> Option<[u8; 32]> {
        self.source_coordinate_sha256
    }

    #[must_use]
    pub const fn placement(&self) -> Option<&Fixed64ProposalPlacement> {
        self.placement.as_ref()
    }

    #[must_use]
    pub fn output_coordinates_angstrom(&self) -> Option<&[Vec3]> {
        self.output_coordinates_angstrom.as_deref()
    }

    #[must_use]
    pub const fn failure(&self) -> Option<&Fixed64ProposalGenerationFailure> {
        self.failure.as_ref()
    }

    #[must_use]
    pub const fn failure_code(&self) -> Option<Fixed64ProposalFailureCode> {
        match self.failure.as_ref() {
            Some(failure) => Some(failure.failure_code),
            None => None,
        }
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let content_valid = match self.status {
            Fixed64ProposalStatus::Generated => {
                let (Some(coordinates), Some(placement), None) = (
                    self.output_coordinates_angstrom.as_ref(),
                    self.placement.as_ref(),
                    self.failure.as_ref(),
                ) else {
                    return false;
                };
                self.generation_input_source_payload_receipt_sha256
                    .is_some()
                    && self.source_proposal_sha256.is_some()
                    && self.source_coordinate_sha256.is_some()
                    && placement.has_valid_receipt()
                    && coordinates.as_slice() == placement.output_coordinates_angstrom()
                    && native_fixed64_coordinate_sha256(coordinates)
                        .is_ok_and(|value| Some(value) == self.source_coordinate_sha256)
            }
            Fixed64ProposalStatus::TypedGenerationFailure => {
                self.generation_input_source_payload_receipt_sha256
                    .is_none()
                    && self.source_proposal_sha256.is_none()
                    && self.source_coordinate_sha256.is_none()
                    && self.output_coordinates_angstrom.is_none()
                    && self.placement.is_none()
                    && self
                        .failure
                        .as_ref()
                        .is_some_and(Fixed64ProposalGenerationFailure::has_valid_receipt)
            }
        };
        content_valid && proposal_record_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64ProposalBatch {
    allocation: Fixed64Allocation,
    source_bundle: Fixed64ProposalSourceBundle,
    records: [Fixed64ProposalRecord; FIXED64_CANDIDATE_COUNT],
    producer_policy_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

impl Fixed64ProposalBatch {
    #[must_use]
    pub fn allocation(&self) -> &Fixed64Allocation {
        &self.allocation
    }

    #[must_use]
    pub fn source_bundle(&self) -> &Fixed64ProposalSourceBundle {
        &self.source_bundle
    }

    #[must_use]
    pub fn records(&self) -> &[Fixed64ProposalRecord; FIXED64_CANDIDATE_COUNT] {
        &self.records
    }

    #[must_use]
    pub fn candidate_coordinates_angstrom(&self, slot_index: usize) -> Option<&[Vec3]> {
        self.records
            .get(slot_index)
            .and_then(Fixed64ProposalRecord::output_coordinates_angstrom)
    }

    #[must_use]
    pub const fn producer_policy_sha256(&self) -> [u8; 32] {
        self.producer_policy_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn generated_count(&self) -> usize {
        self.records
            .iter()
            .filter(|record| record.status == Fixed64ProposalStatus::Generated)
            .count()
    }

    #[must_use]
    pub fn typed_failure_count(&self) -> usize {
        FIXED64_CANDIDATE_COUNT - self.generated_count()
    }

    #[must_use]
    pub const fn result_dependent_input_consumed(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn product_mutation_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.allocation.has_valid_receipt()
            && self.source_bundle.has_valid_receipt()
            && self.source_bundle.allocation.receipt_sha256() == self.allocation.receipt_sha256()
            && self.producer_policy_sha256 == native_fixed64_producer_policy_sha256()
            && self.records.iter().enumerate().all(|(index, record)| {
                record.slot_index == index
                    && record.allocation_slot_receipt_sha256
                        == self.allocation.slots()[index].receipt_sha256()
                    && record.lane == self.allocation.slots()[index].lane()
                    && record.source_bundle_receipt_sha256 == self.source_bundle.receipt_sha256
                    && record.has_valid_receipt()
            })
            && producer_batch_sha256(self) == self.receipt_sha256
    }
}

pub fn produce_native_fixed64_proposals(
    allocation: &Fixed64Allocation,
    source_bundle: Fixed64ProposalSourceBundle,
) -> Result<Fixed64ProposalBatch, Fixed64ProducerError> {
    if !allocation.has_valid_receipt() || !source_bundle.has_valid_receipt() {
        return Err(cross_wired(
            "allocation or source bundle receipt is invalid",
        ));
    }
    if source_bundle.allocation.receipt_sha256() != allocation.receipt_sha256() {
        return Err(cross_wired("source bundle belongs to another allocation"));
    }
    let producer_policy_sha256 = native_fixed64_producer_policy_sha256();
    let mut records = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for slot in allocation.slots() {
        if !slot.generation_eligible() {
            records.push(failure_record(
                slot,
                source_bundle.receipt_sha256,
                Fixed64ProposalFailureCode::AllocationMissingFeature,
                None,
            ));
            continue;
        }
        let Some(source) = source_bundle.source_for_slot(slot.slot_index()) else {
            records.push(failure_record(
                slot,
                source_bundle.receipt_sha256,
                missing_source_code(slot.lane()),
                None,
            ));
            continue;
        };
        if source.coordinates_angstrom().len()
            != source_bundle
                .geometric_input
                .ligand_vdw_radii_angstrom()
                .len()
        {
            records.push(failure_record(
                slot,
                source_bundle.receipt_sha256,
                Fixed64ProposalFailureCode::LigandAtomDenominatorMismatch,
                Some(source.receipt_sha256()),
            ));
            continue;
        }
        if validate_source_for_slot(allocation, slot.slot_index(), source).is_err() {
            records.push(failure_record(
                slot,
                source_bundle.receipt_sha256,
                Fixed64ProposalFailureCode::SourcePayloadCrossWired,
                Some(source.receipt_sha256()),
            ));
            continue;
        }
        let placement = match generate_placement(&source_bundle, slot.slot_index(), source.clone())
        {
            Ok(value) => value,
            Err(code) => {
                records.push(failure_record(
                    slot,
                    source_bundle.receipt_sha256,
                    Fixed64ProposalFailureCode::Placement(code),
                    Some(source.receipt_sha256()),
                ));
                continue;
            }
        };
        records.push(success_record(
            slot,
            source_bundle.receipt_sha256,
            source,
            placement,
            producer_policy_sha256,
        )?);
    }
    let records: [Fixed64ProposalRecord; FIXED64_CANDIDATE_COUNT] = records
        .try_into()
        .map_err(|_| internal("fixed64 proposal denominator changed"))?;
    let mut value = Fixed64ProposalBatch {
        allocation: allocation.clone(),
        source_bundle,
        records,
        producer_policy_sha256,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = producer_batch_sha256(&value);
    if !value.has_valid_receipt() {
        return Err(internal("native producer receipt failed self-verification"));
    }
    Ok(value)
}

#[must_use]
pub fn native_fixed64_producer_policy_sha256() -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_producer_policy/native-v1");
    hash.string(NATIVE_FIXED64_PRODUCER_PROFILE_ID);
    hash.usize(FIXED64_CANDIDATE_COUNT);
    hash.string("exact_passthrough,indexed_so3,single_anchor");
    hash.bool(true);
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn generate_placement(
    bundle: &Fixed64ProposalSourceBundle,
    slot_index: usize,
    source: Fixed64CoordinateSourcePayload,
) -> Result<Fixed64ProposalPlacement, Fixed64PlacementErrorCode> {
    let lane = bundle.allocation.slots()[slot_index].lane();
    match lane {
        Fixed64Lane::PocketCenteredControls
        | Fixed64Lane::UniformSourceControls
        | Fixed64Lane::PairedRetainedControls => Fixed64PassthroughPlacement::new(
            &bundle.allocation,
            bundle.receipt_sha256,
            slot_index,
            source,
        )
        .map(Box::new)
        .map(Fixed64ProposalPlacement::ExactPassthrough)
        .map_err(|_| Fixed64PlacementErrorCode::SourceIdentityMismatch),
        Fixed64Lane::DeterministicIndependentSo3 | Fixed64Lane::TrueConformerIndependentSo3 => {
            generate_native_fixed64_indexed_so3(
                &bundle.allocation,
                slot_index,
                source.source.clone(),
                bundle.geometric_input.pocket_center_angstrom(),
                bundle.pocket_normal,
            )
            .map(Box::new)
            .map(Fixed64ProposalPlacement::IndexedSo3)
            .map_err(|error| error.code())
        }
        Fixed64Lane::LigandDonorToReceptorAcceptor
        | Fixed64Lane::LigandAcceptorToReceptorDonor
        | Fixed64Lane::ComplementaryCharge
        | Fixed64Lane::AromaticPlane
        | Fixed64Lane::PrincipalAxisShape => generate_native_fixed64_single_anchor(
            &bundle.allocation,
            slot_index,
            source.source.clone(),
            &bundle.feature_geometry_inventory,
            &bundle.geometric_input,
        )
        .map(Box::new)
        .map(Fixed64ProposalPlacement::SingleAnchor)
        .map_err(|error| error.code()),
    }
}

fn success_record(
    slot: &crate::Fixed64Slot,
    source_bundle_receipt_sha256: [u8; 32],
    source: &Fixed64CoordinateSourcePayload,
    placement: Fixed64ProposalPlacement,
    producer_policy_sha256: [u8; 32],
) -> Result<Fixed64ProposalRecord, Fixed64ProducerError> {
    let output_coordinates_angstrom = placement.output_coordinates_angstrom().to_vec();
    let output_coordinate_sha256 = native_fixed64_coordinate_sha256(&output_coordinates_angstrom)
        .map_err(|_| internal("generated coordinates are invalid"))?;
    let source_proposal_sha256 = match placement {
        Fixed64ProposalPlacement::ExactPassthrough(_) => source.evidence().proposal_sha256,
        _ => generated_proposal_sha256(
            slot,
            source.receipt_sha256(),
            placement.receipt_sha256(),
            output_coordinate_sha256,
            producer_policy_sha256,
        ),
    };
    let mut value = Fixed64ProposalRecord {
        slot_index: slot.slot_index(),
        allocation_slot_receipt_sha256: slot.receipt_sha256(),
        lane: slot.lane(),
        source_bundle_receipt_sha256,
        status: Fixed64ProposalStatus::Generated,
        generation_input_source_payload_receipt_sha256: Some(source.receipt_sha256()),
        source_proposal_sha256: Some(source_proposal_sha256),
        source_coordinate_sha256: Some(output_coordinate_sha256),
        output_coordinates_angstrom: Some(output_coordinates_angstrom),
        placement: Some(placement),
        failure: None,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = proposal_record_sha256(&value);
    Ok(value)
}

fn failure_record(
    slot: &crate::Fixed64Slot,
    source_bundle_receipt_sha256: [u8; 32],
    failure_code: Fixed64ProposalFailureCode,
    attempted_source_payload_receipt_sha256: Option<[u8; 32]>,
) -> Fixed64ProposalRecord {
    let mut failure = Fixed64ProposalGenerationFailure {
        slot_index: slot.slot_index(),
        allocation_slot_receipt_sha256: slot.receipt_sha256(),
        source_bundle_receipt_sha256,
        failure_code,
        allocation_missing_features: slot.missing_features().to_vec(),
        attempted_source_payload_receipt_sha256,
        receipt_sha256: [0; 32],
    };
    failure.receipt_sha256 = generation_failure_sha256(&failure);
    let mut value = Fixed64ProposalRecord {
        slot_index: slot.slot_index(),
        allocation_slot_receipt_sha256: slot.receipt_sha256(),
        lane: slot.lane(),
        source_bundle_receipt_sha256,
        status: Fixed64ProposalStatus::TypedGenerationFailure,
        generation_input_source_payload_receipt_sha256: None,
        source_proposal_sha256: None,
        source_coordinate_sha256: None,
        output_coordinates_angstrom: None,
        placement: None,
        failure: Some(failure),
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = proposal_record_sha256(&value);
    value
}

fn validate_exact_system(
    allocation: &Fixed64Allocation,
    input: &Fixed64GeometricInput,
) -> Result<(), Fixed64ProducerError> {
    let exact = allocation.inventory().exact_v11_source();
    let receptor_coordinate_sha256 =
        native_fixed64_coordinate_sha256(input.receptor_coordinates_angstrom())
            .map_err(|_| exact_cross_wired("receptor coordinates are invalid"))?;
    let ligand_vdw_radii_sha256 = native_fixed64_radii_sha256(input.ligand_vdw_radii_angstrom())
        .map_err(|_| exact_cross_wired("ligand vdW radii are invalid"))?;
    let ligand_heavy_atom_mask_sha256 =
        native_fixed64_heavy_atom_mask_sha256(input.ligand_heavy_atom_mask())
            .map_err(|_| exact_cross_wired("ligand heavy-atom mask is invalid"))?;
    let receptor_vdw_radii_sha256 =
        native_fixed64_radii_sha256(input.receptor_vdw_radii_angstrom())
            .map_err(|_| exact_cross_wired("receptor vdW radii are invalid"))?;
    if receptor_coordinate_sha256 != exact.receptor_coordinate_sha256
        || ligand_vdw_radii_sha256 != exact.ligand_vdw_radii_sha256
        || ligand_heavy_atom_mask_sha256 != exact.ligand_heavy_atom_mask_sha256
        || receptor_vdw_radii_sha256 != exact.receptor_vdw_radii_sha256
    {
        return Err(exact_cross_wired(
            "geometric system identities disagree with exact V1.1 evidence",
        ));
    }
    Ok(())
}

fn validate_source_group(
    allocation: &Fixed64Allocation,
    sources: &[Fixed64CoordinateSourcePayload],
    expected_kind: Fixed64CoordinateSourceKind,
) -> Result<(), Fixed64ProducerError> {
    if sources
        .iter()
        .any(|source| source.source_kind != expected_kind || source.source_ordinal.is_none())
        || sources
            .windows(2)
            .any(|rows| rows[0].source_ordinal >= rows[1].source_ordinal)
    {
        return Err(source_cross_wired(
            "coordinate sources are duplicated or noncanonical",
        ));
    }
    sources
        .iter()
        .try_for_each(|source| validate_source_payload(allocation, source, expected_kind))
}

fn validate_source_payload(
    allocation: &Fixed64Allocation,
    source: &Fixed64CoordinateSourcePayload,
    expected_kind: Fixed64CoordinateSourceKind,
) -> Result<(), Fixed64ProducerError> {
    if source.source_kind != expected_kind || !source.has_valid_receipt() {
        return Err(source_cross_wired(
            "coordinate source kind or receipt is cross-wired",
        ));
    }
    let expected = match source.source_kind {
        Fixed64CoordinateSourceKind::ExactV11Base => {
            Some(allocation.inventory().exact_v11_source().ligand_source())
        }
        Fixed64CoordinateSourceKind::V7Control => source
            .source_ordinal
            .and_then(|index| allocation.inventory().v7_control_source(index)),
        Fixed64CoordinateSourceKind::TrueConformer => source
            .source_ordinal
            .and_then(|rank| u8::try_from(rank).ok())
            .and_then(|rank| allocation.inventory().conformer_source(rank)),
        Fixed64CoordinateSourceKind::RetainedControl => source
            .source_ordinal
            .and_then(|index| allocation.inventory().retained_source(index)),
    };
    if expected != Some(source.evidence()) {
        return Err(source_cross_wired(
            "coordinate source evidence belongs to another allocation",
        ));
    }
    Ok(())
}

fn validate_source_for_slot(
    allocation: &Fixed64Allocation,
    slot_index: usize,
    source: &Fixed64CoordinateSourcePayload,
) -> Result<(), Fixed64ProducerError> {
    let slot = allocation
        .slots()
        .get(slot_index)
        .ok_or_else(|| cross_wired("slot is outside fixed64"))?;
    let parent = slot
        .generation_parent()
        .ok_or_else(|| source_cross_wired("slot lacks its generation parent"))?;
    if source.evidence().proposal_sha256 != parent.proposal_sha256
        || source.evidence().coordinate_sha256 != parent.coordinate_sha256
    {
        return Err(source_cross_wired(
            "source proposal or coordinate is cross-wired to another slot",
        ));
    }
    let identity_matches = match slot.lane() {
        Fixed64Lane::PocketCenteredControls | Fixed64Lane::UniformSourceControls => {
            source.source_kind == Fixed64CoordinateSourceKind::V7Control
                && source.source_ordinal == slot.v7_control_source_index()
        }
        Fixed64Lane::DeterministicIndependentSo3 => {
            source.source_kind == Fixed64CoordinateSourceKind::ExactV11Base
                && source.source_ordinal.is_none()
                && source.evidence() == allocation.inventory().exact_v11_source().ligand_source()
        }
        Fixed64Lane::TrueConformerIndependentSo3 => {
            source.source_kind == Fixed64CoordinateSourceKind::TrueConformer
                && source.source_ordinal == slot.true_conformer_rank().map(u32::from)
        }
        Fixed64Lane::LigandDonorToReceptorAcceptor
        | Fixed64Lane::LigandAcceptorToReceptorDonor
        | Fixed64Lane::ComplementaryCharge
        | Fixed64Lane::AromaticPlane
        | Fixed64Lane::PrincipalAxisShape => {
            source.source_kind == Fixed64CoordinateSourceKind::ExactV11Base
                && source.source_ordinal.is_none()
                && source.evidence() == allocation.inventory().exact_v11_source().ligand_source()
        }
        Fixed64Lane::PairedRetainedControls => {
            source.source_kind == Fixed64CoordinateSourceKind::RetainedControl
                && source.source_ordinal == slot.retained_source_index()
        }
    };
    if !identity_matches {
        return Err(source_cross_wired("source kind or ordinal is cross-wired"));
    }
    Ok(())
}

const fn source_ordinal_valid(kind: Fixed64CoordinateSourceKind, ordinal: Option<u32>) -> bool {
    match (kind, ordinal) {
        (Fixed64CoordinateSourceKind::ExactV11Base, None) => true,
        (Fixed64CoordinateSourceKind::V7Control, Some(index)) => index < 24,
        (Fixed64CoordinateSourceKind::TrueConformer, Some(rank)) => rank >= 2 && rank <= 8,
        (Fixed64CoordinateSourceKind::RetainedControl, Some(index)) => {
            index == RETAINED_SOURCE_INDICES[0]
                || index == RETAINED_SOURCE_INDICES[1]
                || index == RETAINED_SOURCE_INDICES[2]
                || index == RETAINED_SOURCE_INDICES[3]
        }
        _ => false,
    }
}

fn normalized_pocket_normal(value: Vec3) -> Result<Vec3, Fixed64ProducerError> {
    if !value.is_finite()
        || value.x.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || value.y.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || value.z.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
    {
        return Err(invalid("pocket normal is outside its safety envelope"));
    }
    let maximum = value.x.abs().max(value.y.abs()).max(value.z.abs());
    if maximum <= 1.0e-12 {
        return Err(invalid("pocket normal is degenerate"));
    }
    let scaled = value.scale(1.0 / maximum);
    Ok(scaled.scale(1.0 / scaled.norm()))
}

fn pocket_normal_is_unit(value: Vec3) -> bool {
    value.is_finite()
        && value.x.abs() <= FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        && value.y.abs() <= FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        && value.z.abs() <= FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        && (value.norm() - 1.0).abs() <= 1.0e-15
}

const fn missing_source_code(lane: Fixed64Lane) -> Fixed64ProposalFailureCode {
    match lane {
        Fixed64Lane::PocketCenteredControls | Fixed64Lane::UniformSourceControls => {
            Fixed64ProposalFailureCode::MissingV7ControlSource
        }
        Fixed64Lane::TrueConformerIndependentSo3 => {
            Fixed64ProposalFailureCode::MissingConformerSource
        }
        Fixed64Lane::PairedRetainedControls => Fixed64ProposalFailureCode::MissingRetainedSource,
        _ => Fixed64ProposalFailureCode::MissingExactV11Source,
    }
}

fn coordinate_source_sha256(value: &Fixed64CoordinateSourcePayload) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_coordinate_source/native-v1");
    hash.string(NATIVE_FIXED64_COORDINATE_SOURCE_SCHEMA_ID);
    hash.byte(value.source_kind.tag());
    hash.option(value.source_ordinal, |hash, ordinal| hash.u32(ordinal));
    hash.digest(value.source.receipt_sha256());
    hash.bool(false);
    hash.finish()
}

fn source_bundle_sha256(value: &Fixed64ProposalSourceBundle) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_source_bundle/native-v1");
    hash.string(NATIVE_FIXED64_SOURCE_BUNDLE_SCHEMA_ID);
    hash.digest(value.allocation.receipt_sha256());
    hash.option(value.exact_v11_source.as_ref(), |hash, source| {
        hash.digest(source.receipt_sha256())
    });
    source_group_sha256(&mut hash, &value.v7_control_sources);
    source_group_sha256(&mut hash, &value.conformer_sources);
    source_group_sha256(&mut hash, &value.retained_sources);
    hash.digest(value.feature_geometry_inventory.receipt_sha256());
    hash.digest(value.geometric_input.receipt_sha256());
    hash.vec3(value.pocket_normal);
    hash.bool(true);
    hash.bool(false);
    hash.finish()
}

fn source_group_sha256(hash: &mut CanonicalHash, values: &[Fixed64CoordinateSourcePayload]) {
    hash.usize(values.len());
    for value in values {
        hash.digest(value.receipt_sha256());
    }
}

fn passthrough_sha256(value: &Fixed64PassthroughPlacement) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_passthrough/native-v1");
    hash.string(NATIVE_FIXED64_PASSTHROUGH_SCHEMA_ID);
    hash.digest(value.allocation_receipt_sha256);
    hash.digest(value.allocation_slot_receipt_sha256);
    hash.digest(value.source_bundle_receipt_sha256);
    hash.usize(value.slot_index);
    hash.string(value.lane.id());
    hash.digest(value.source_payload.receipt_sha256());
    hash.digest(value.output_coordinate_sha256);
    hash.bool(true);
    hash.bool(false);
    hash.finish()
}

fn generated_proposal_sha256(
    slot: &crate::Fixed64Slot,
    source_payload_receipt_sha256: [u8; 32],
    placement_receipt_sha256: [u8; 32],
    output_coordinate_sha256: [u8; 32],
    producer_policy_sha256: [u8; 32],
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_generated_proposal/native-v1");
    hash.digest(producer_policy_sha256);
    hash.digest(slot.receipt_sha256());
    hash.usize(slot.slot_index());
    hash.digest(source_payload_receipt_sha256);
    hash.digest(placement_receipt_sha256);
    hash.digest(output_coordinate_sha256);
    hash.finish()
}

fn generation_failure_sha256(value: &Fixed64ProposalGenerationFailure) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_generation_failure/native-v1");
    hash.string(NATIVE_FIXED64_GENERATION_FAILURE_SCHEMA_ID);
    hash.usize(value.slot_index);
    hash.digest(value.allocation_slot_receipt_sha256);
    hash.digest(value.source_bundle_receipt_sha256);
    failure_code_sha256(&mut hash, value.failure_code);
    hash.usize(value.allocation_missing_features.len());
    for feature in &value.allocation_missing_features {
        missing_feature_sha256(&mut hash, *feature);
    }
    hash.option(
        value.attempted_source_payload_receipt_sha256,
        |hash, receipt| hash.digest(receipt),
    );
    hash.bool(true);
    hash.bool(false);
    hash.finish()
}

fn proposal_record_sha256(value: &Fixed64ProposalRecord) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_proposal_record/native-v1");
    hash.string(NATIVE_FIXED64_PROPOSAL_RECORD_SCHEMA_ID);
    hash.usize(value.slot_index);
    hash.digest(value.allocation_slot_receipt_sha256);
    hash.string(value.lane.id());
    hash.digest(value.source_bundle_receipt_sha256);
    hash.byte(match value.status {
        Fixed64ProposalStatus::Generated => 0,
        Fixed64ProposalStatus::TypedGenerationFailure => 1,
    });
    hash.option(
        value.generation_input_source_payload_receipt_sha256,
        |hash, receipt| hash.digest(receipt),
    );
    hash.option(value.source_proposal_sha256, |hash, digest| {
        hash.digest(digest)
    });
    hash.option(value.source_coordinate_sha256, |hash, digest| {
        hash.digest(digest)
    });
    hash.option(value.placement.as_ref(), |hash, placement| {
        hash.byte(placement.tag());
        hash.digest(placement.receipt_sha256());
    });
    hash.option(value.failure.as_ref(), |hash, failure| {
        hash.digest(failure.receipt_sha256())
    });
    hash.bool(true);
    hash.bool(false);
    hash.finish()
}

fn producer_batch_sha256(value: &Fixed64ProposalBatch) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_producer_batch/native-v1");
    hash.string(NATIVE_FIXED64_PRODUCER_BATCH_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_PRODUCER_PROFILE_ID);
    hash.digest(value.allocation.receipt_sha256());
    hash.digest(value.source_bundle.receipt_sha256());
    hash.digest(value.producer_policy_sha256);
    hash.usize(value.records.len());
    for record in &value.records {
        hash.digest(record.receipt_sha256());
    }
    hash.usize(value.generated_count());
    hash.usize(value.typed_failure_count());
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn failure_code_sha256(hash: &mut CanonicalHash, value: Fixed64ProposalFailureCode) {
    match value {
        Fixed64ProposalFailureCode::AllocationMissingFeature => hash.byte(0),
        Fixed64ProposalFailureCode::MissingExactV11Source => hash.byte(1),
        Fixed64ProposalFailureCode::MissingV7ControlSource => hash.byte(2),
        Fixed64ProposalFailureCode::MissingConformerSource => hash.byte(3),
        Fixed64ProposalFailureCode::MissingRetainedSource => hash.byte(4),
        Fixed64ProposalFailureCode::LigandAtomDenominatorMismatch => hash.byte(5),
        Fixed64ProposalFailureCode::SourcePayloadCrossWired => hash.byte(6),
        Fixed64ProposalFailureCode::Placement(code) => {
            hash.byte(7);
            placement_error_code_sha256(hash, code);
        }
    }
}

fn placement_error_code_sha256(hash: &mut CanonicalHash, value: Fixed64PlacementErrorCode) {
    hash.byte(match value {
        Fixed64PlacementErrorCode::InvalidInput => 0,
        Fixed64PlacementErrorCode::AllocationSlotNotEligible => 1,
        Fixed64PlacementErrorCode::UnsupportedLane => 2,
        Fixed64PlacementErrorCode::SourceIdentityMismatch => 3,
        Fixed64PlacementErrorCode::FeatureCrossWired => 4,
        Fixed64PlacementErrorCode::FeatureAtomIndexOutOfRange => 5,
        Fixed64PlacementErrorCode::DegenerateSo3SourceGeometry => 6,
        Fixed64PlacementErrorCode::DegenerateLigandDirection => 7,
        Fixed64PlacementErrorCode::DegenerateReceptorDirection => 8,
        Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal => 9,
        Fixed64PlacementErrorCode::DegenerateAromaticPlane => 10,
        Fixed64PlacementErrorCode::DegeneratePrincipalAxis => 11,
        Fixed64PlacementErrorCode::GeometricPrecheckFailed => 12,
        Fixed64PlacementErrorCode::InternalInvariant => 13,
    });
}

fn missing_feature_sha256(hash: &mut CanonicalHash, value: Fixed64MissingFeature) {
    match value {
        Fixed64MissingFeature::V7ControlSource(index) => {
            hash.byte(0);
            hash.byte(index);
        }
        Fixed64MissingFeature::TrueConformer(rank) => {
            hash.byte(1);
            hash.byte(rank);
        }
        Fixed64MissingFeature::LigandDonor => hash.byte(2),
        Fixed64MissingFeature::ReceptorAcceptor => hash.byte(3),
        Fixed64MissingFeature::LigandAcceptor => hash.byte(4),
        Fixed64MissingFeature::ReceptorDonor => hash.byte(5),
        Fixed64MissingFeature::ComplementaryChargeAnchor => hash.byte(6),
        Fixed64MissingFeature::LigandAromaticPlane => hash.byte(7),
        Fixed64MissingFeature::ReceptorAromaticPlane => hash.byte(8),
        Fixed64MissingFeature::LigandShapeAxis => hash.byte(9),
        Fixed64MissingFeature::PocketShapeAxis => hash.byte(10),
        Fixed64MissingFeature::RetainedSource(index) => {
            hash.byte(11);
            hash.u32(index);
        }
    }
}

const fn invalid(message: &'static str) -> Fixed64ProducerError {
    Fixed64ProducerError::new(Fixed64ProducerErrorCode::InvalidInput, message)
}

const fn cross_wired(message: &'static str) -> Fixed64ProducerError {
    Fixed64ProducerError::new(Fixed64ProducerErrorCode::AllocationCrossWired, message)
}

const fn source_cross_wired(message: &'static str) -> Fixed64ProducerError {
    Fixed64ProducerError::new(Fixed64ProducerErrorCode::SourcePayloadCrossWired, message)
}

const fn exact_cross_wired(message: &'static str) -> Fixed64ProducerError {
    Fixed64ProducerError::new(Fixed64ProducerErrorCode::ExactSystemCrossWired, message)
}

const fn internal(message: &'static str) -> Fixed64ProducerError {
    Fixed64ProducerError::new(Fixed64ProducerErrorCode::InternalInvariant, message)
}
