use std::collections::BTreeSet;
use std::fmt;

use crate::native_hash::CanonicalHash;

pub const FIXED64_CANDIDATE_COUNT: usize = 64;
pub const FIXED64_PROFILE_ID: &str = "betelgeuze.engine_v2_global_orientation_fixed_mixed64/1.0.0";
pub const NATIVE_FIXED64_ALLOCATION_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_allocation/1.0.0";
pub const NATIVE_FIXED64_SLOT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_slot/1.0.0";

pub const RETAINED_SOURCE_INDICES: [u32; 4] = [36, 45, 54, 63];
pub const TRUE_CONFORMER_SLOT_RANKS: [u8; 8] = [2, 3, 4, 5, 6, 7, 8, 2];

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Fixed64Lane {
    PocketCenteredControls,
    UniformSourceControls,
    DeterministicIndependentSo3,
    TrueConformerIndependentSo3,
    LigandDonorToReceptorAcceptor,
    LigandAcceptorToReceptorDonor,
    ComplementaryCharge,
    AromaticPlane,
    PrincipalAxisShape,
    PairedRetainedControls,
}

impl Fixed64Lane {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::PocketCenteredControls => "pocket_centered_controls",
            Self::UniformSourceControls => "uniform_source_controls",
            Self::DeterministicIndependentSo3 => "deterministic_independent_so3",
            Self::TrueConformerIndependentSo3 => "true_conformer_independent_so3",
            Self::LigandDonorToReceptorAcceptor => "ligand_donor_to_receptor_acceptor",
            Self::LigandAcceptorToReceptorDonor => "ligand_acceptor_to_receptor_donor",
            Self::ComplementaryCharge => "complementary_charge",
            Self::AromaticPlane => "aromatic_plane",
            Self::PrincipalAxisShape => "principal_axis_shape",
            Self::PairedRetainedControls => "paired_retained_controls",
        }
    }

    const fn tag(self) -> u8 {
        match self {
            Self::PocketCenteredControls => 0,
            Self::UniformSourceControls => 1,
            Self::DeterministicIndependentSo3 => 2,
            Self::TrueConformerIndependentSo3 => 3,
            Self::LigandDonorToReceptorAcceptor => 4,
            Self::LigandAcceptorToReceptorDonor => 5,
            Self::ComplementaryCharge => 6,
            Self::AromaticPlane => 7,
            Self::PrincipalAxisShape => 8,
            Self::PairedRetainedControls => 9,
        }
    }
}

pub const FIXED64_LANE_RANGES: [(Fixed64Lane, usize, usize); 10] = [
    (Fixed64Lane::PocketCenteredControls, 0, 7),
    (Fixed64Lane::UniformSourceControls, 8, 23),
    (Fixed64Lane::DeterministicIndependentSo3, 24, 35),
    (Fixed64Lane::TrueConformerIndependentSo3, 36, 43),
    (Fixed64Lane::LigandDonorToReceptorAcceptor, 44, 47),
    (Fixed64Lane::LigandAcceptorToReceptorDonor, 48, 51),
    (Fixed64Lane::ComplementaryCharge, 52, 55),
    (Fixed64Lane::AromaticPlane, 56, 57),
    (Fixed64Lane::PrincipalAxisShape, 58, 59),
    (Fixed64Lane::PairedRetainedControls, 60, 63),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
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
    const fn tag(self) -> u8 {
        match self {
            Self::LigandDonor => 0,
            Self::LigandAcceptor => 1,
            Self::ReceptorDonor => 2,
            Self::ReceptorAcceptor => 3,
            Self::LigandPositiveSite => 4,
            Self::LigandNegativeSite => 5,
            Self::ReceptorPositiveSite => 6,
            Self::ReceptorNegativeSite => 7,
            Self::LigandAromaticPlane => 8,
            Self::ReceptorAromaticPlane => 9,
            Self::LigandShapeAxis => 10,
            Self::PocketShapeAxis => 11,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Fixed64AnchorKind {
    LigandDonorToReceptorAcceptor,
    LigandAcceptorToReceptorDonor,
    ComplementaryCharge,
    AromaticPlane,
    PrincipalAxisShape,
}

impl Fixed64AnchorKind {
    const fn tag(self) -> u8 {
        match self {
            Self::LigandDonorToReceptorAcceptor => 0,
            Self::LigandAcceptorToReceptorDonor => 1,
            Self::ComplementaryCharge => 2,
            Self::AromaticPlane => 3,
            Self::PrincipalAxisShape => 4,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Fixed64Requirement {
    V7ControlSource(u8),
    TrueConformerRank(u8),
    Feature(Fixed64FeatureKind),
    ComplementaryChargeAnchor,
    RetainedSource(u32),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Fixed64MissingFeature {
    V7ControlSource(u8),
    TrueConformer(u8),
    LigandDonor,
    ReceptorAcceptor,
    LigandAcceptor,
    ReceptorDonor,
    ComplementaryChargeAnchor,
    LigandAromaticPlane,
    ReceptorAromaticPlane,
    LigandShapeAxis,
    PocketShapeAxis,
    RetainedSource(u32),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Fixed64GenerationParentRole {
    ExactPassthroughParent,
    GeneratorInputParent,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64SourceEvidence {
    pub receipt_sha256: [u8; 32],
    pub proposal_sha256: [u8; 32],
    pub coordinate_sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64ExactV11SourceEvidence {
    pub source_receipt_sha256: [u8; 32],
    pub proposal_sha256: [u8; 32],
    pub ligand_coordinate_sha256: [u8; 32],
    pub receptor_coordinate_sha256: [u8; 32],
    pub prepared_ligand_topology_sha256: [u8; 32],
    pub prepared_receptor_topology_sha256: [u8; 32],
    pub ligand_vdw_radii_sha256: [u8; 32],
    pub ligand_heavy_atom_mask_sha256: [u8; 32],
    pub receptor_vdw_radii_sha256: [u8; 32],
}

impl Fixed64ExactV11SourceEvidence {
    #[must_use]
    pub const fn ligand_source(self) -> Fixed64SourceEvidence {
        Fixed64SourceEvidence {
            receipt_sha256: self.source_receipt_sha256,
            proposal_sha256: self.proposal_sha256,
            coordinate_sha256: self.ligand_coordinate_sha256,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64IndexedSourceEvidence {
    pub source_index: u32,
    pub source: Fixed64SourceEvidence,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64ConformerSourceEvidence {
    pub rank: u8,
    pub source: Fixed64SourceEvidence,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Fixed64AtomicFeatureEvidence {
    pub kind: Fixed64FeatureKind,
    pub receipt_sha256: [u8; 32],
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fixed64FeatureInventory {
    exact_v11_source: Fixed64ExactV11SourceEvidence,
    atomic_features: Vec<Fixed64AtomicFeatureEvidence>,
    v7_control_sources: Vec<Fixed64IndexedSourceEvidence>,
    conformer_sources: Vec<Fixed64ConformerSourceEvidence>,
    retained_sources: Vec<Fixed64IndexedSourceEvidence>,
}

impl Fixed64FeatureInventory {
    pub fn new(
        exact_v11_source: Fixed64ExactV11SourceEvidence,
        atomic_features: Vec<Fixed64AtomicFeatureEvidence>,
        v7_control_sources: Vec<Fixed64IndexedSourceEvidence>,
        conformer_sources: Vec<Fixed64ConformerSourceEvidence>,
        retained_sources: Vec<Fixed64IndexedSourceEvidence>,
    ) -> Result<Self, Fixed64AllocationError> {
        let value = Self {
            exact_v11_source,
            atomic_features,
            v7_control_sources,
            conformer_sources,
            retained_sources,
        };
        value.validate()?;
        Ok(value)
    }

    #[must_use]
    pub const fn exact_v11_source(&self) -> Fixed64ExactV11SourceEvidence {
        self.exact_v11_source
    }

    #[must_use]
    pub fn atomic_features(&self) -> &[Fixed64AtomicFeatureEvidence] {
        &self.atomic_features
    }

    #[must_use]
    pub fn v7_control_source(&self, index: u32) -> Option<Fixed64SourceEvidence> {
        self.v7_control(index)
    }

    #[must_use]
    pub fn conformer_source(&self, rank: u8) -> Option<Fixed64SourceEvidence> {
        self.conformer(rank)
    }

    #[must_use]
    pub fn retained_source(&self, index: u32) -> Option<Fixed64SourceEvidence> {
        self.retained(index)
    }

    fn validate(&self) -> Result<(), Fixed64AllocationError> {
        if self.atomic_features.len() > 12 * 256 {
            return Err(Fixed64AllocationError::InvalidInventory(
                "atomic feature capacity exceeded",
            ));
        }
        if self
            .atomic_features
            .windows(2)
            .any(|rows| rows[0] >= rows[1])
        {
            return Err(Fixed64AllocationError::InvalidInventory(
                "atomic features must be unique and canonically ordered",
            ));
        }
        for kind in all_feature_kinds() {
            if self.features_for_kind(kind).count() > 256 {
                return Err(Fixed64AllocationError::InvalidInventory(
                    "per-kind atomic feature capacity exceeded",
                ));
            }
        }
        validate_indexed_sources(
            &self.v7_control_sources,
            24,
            |index| index < 24,
            "V7 control sources are invalid",
        )?;
        if self.conformer_sources.len() > 7
            || self
                .conformer_sources
                .iter()
                .any(|row| !(2..=8).contains(&row.rank))
            || self
                .conformer_sources
                .windows(2)
                .any(|rows| rows[0].rank >= rows[1].rank)
            || !unique_receipts(
                self.conformer_sources
                    .iter()
                    .map(|row| row.source.receipt_sha256),
            )
        {
            return Err(Fixed64AllocationError::InvalidInventory(
                "conformer sources are invalid",
            ));
        }
        validate_indexed_sources(
            &self.retained_sources,
            4,
            |index| RETAINED_SOURCE_INDICES.contains(&index),
            "retained sources are invalid",
        )?;
        Ok(())
    }

    fn features_for_kind(
        &self,
        kind: Fixed64FeatureKind,
    ) -> impl Iterator<Item = &Fixed64AtomicFeatureEvidence> {
        self.atomic_features
            .iter()
            .filter(move |feature| feature.kind == kind)
    }

    fn feature_receipt(&self, kind: Fixed64FeatureKind, offset: usize) -> Option<[u8; 32]> {
        let values: Vec<_> = self.features_for_kind(kind).collect();
        (!values.is_empty()).then(|| values[offset % values.len()].receipt_sha256)
    }

    fn v7_control(&self, index: u32) -> Option<Fixed64SourceEvidence> {
        self.v7_control_sources
            .iter()
            .find(|row| row.source_index == index)
            .map(|row| row.source)
    }

    fn conformer(&self, rank: u8) -> Option<Fixed64SourceEvidence> {
        self.conformer_sources
            .iter()
            .find(|row| row.rank == rank)
            .map(|row| row.source)
    }

    fn retained(&self, index: u32) -> Option<Fixed64SourceEvidence> {
        self.retained_sources
            .iter()
            .find(|row| row.source_index == index)
            .map(|row| row.source)
    }

    fn has_feature(&self, kind: Fixed64FeatureKind) -> bool {
        self.features_for_kind(kind).next().is_some()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64GenerationParent {
    pub proposal_sha256: [u8; 32],
    pub coordinate_sha256: [u8; 32],
    pub role: Fixed64GenerationParentRole,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fixed64Slot {
    slot_index: usize,
    lane: Fixed64Lane,
    lane_offset: usize,
    declared_anchor_kind: Option<Fixed64AnchorKind>,
    required_features: Vec<Fixed64Requirement>,
    missing_features: Vec<Fixed64MissingFeature>,
    v7_control_source_index: Option<u32>,
    so3_sequence_index: Option<u8>,
    true_conformer_rank: Option<u8>,
    retained_source_index: Option<u32>,
    selected_source_receipt_sha256s: Vec<[u8; 32]>,
    generation_parent: Option<Fixed64GenerationParent>,
    receipt_sha256: [u8; 32],
}

impl Fixed64Slot {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn lane(&self) -> Fixed64Lane {
        self.lane
    }

    #[must_use]
    pub const fn lane_offset(&self) -> usize {
        self.lane_offset
    }

    #[must_use]
    pub const fn declared_anchor_kind(&self) -> Option<Fixed64AnchorKind> {
        self.declared_anchor_kind
    }

    #[must_use]
    pub const fn declared_anchor_count(&self) -> usize {
        if self.declared_anchor_kind.is_some() {
            1
        } else {
            0
        }
    }

    #[must_use]
    pub fn required_features(&self) -> &[Fixed64Requirement] {
        &self.required_features
    }

    #[must_use]
    pub fn missing_features(&self) -> &[Fixed64MissingFeature] {
        &self.missing_features
    }

    #[must_use]
    pub fn generation_eligible(&self) -> bool {
        self.missing_features.is_empty()
    }

    #[must_use]
    pub const fn v7_control_source_index(&self) -> Option<u32> {
        self.v7_control_source_index
    }

    #[must_use]
    pub const fn so3_sequence_index(&self) -> Option<u8> {
        self.so3_sequence_index
    }

    #[must_use]
    pub const fn true_conformer_rank(&self) -> Option<u8> {
        self.true_conformer_rank
    }

    #[must_use]
    pub const fn retained_source_index(&self) -> Option<u32> {
        self.retained_source_index
    }

    #[must_use]
    pub fn selected_source_receipt_sha256s(&self) -> &[[u8; 32]] {
        &self.selected_source_receipt_sha256s
    }

    #[must_use]
    pub const fn generation_parent(&self) -> Option<Fixed64GenerationParent> {
        self.generation_parent
    }

    #[must_use]
    pub const fn fallback_allowed(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn multi_anchor_allowed(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fixed64Allocation {
    inventory: Fixed64FeatureInventory,
    inventory_sha256: [u8; 32],
    slots: [Fixed64Slot; FIXED64_CANDIDATE_COUNT],
    receipt_sha256: [u8; 32],
}

impl Fixed64Allocation {
    pub fn build(inventory: Fixed64FeatureInventory) -> Result<Self, Fixed64AllocationError> {
        inventory.validate()?;
        let inventory_sha256 = inventory_sha256(&inventory);
        let slots = std::array::from_fn(|index| build_slot(&inventory, index));
        let receipt_sha256 = allocation_sha256(inventory_sha256, &slots);
        let value = Self {
            inventory,
            inventory_sha256,
            slots,
            receipt_sha256,
        };
        value.validate()?;
        Ok(value)
    }

    #[must_use]
    pub fn slots(&self) -> &[Fixed64Slot; FIXED64_CANDIDATE_COUNT] {
        &self.slots
    }

    #[must_use]
    pub fn inventory(&self) -> &Fixed64FeatureInventory {
        &self.inventory
    }

    #[must_use]
    pub const fn inventory_sha256(&self) -> [u8; 32] {
        self.inventory_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn ready_count(&self) -> usize {
        self.slots
            .iter()
            .filter(|slot| slot.generation_eligible())
            .count()
    }

    #[must_use]
    pub fn typed_failure_count(&self) -> usize {
        FIXED64_CANDIDATE_COUNT - self.ready_count()
    }

    #[must_use]
    pub const fn result_dependent_allocation(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.validate().is_ok()
    }

    fn validate(&self) -> Result<(), Fixed64AllocationError> {
        self.inventory.validate()?;
        if inventory_sha256(&self.inventory) != self.inventory_sha256 {
            return Err(Fixed64AllocationError::InternalInvariant(
                "fixed64 inventory identity changed",
            ));
        }
        for (index, observed) in self.slots.iter().enumerate() {
            let expected = build_slot(&self.inventory, index);
            if observed != &expected
                || observed.slot_index != index
                || observed.declared_anchor_count() > 1
            {
                return Err(Fixed64AllocationError::InternalInvariant(
                    "fixed64 slot mapping changed",
                ));
            }
        }
        if allocation_sha256(self.inventory_sha256, &self.slots) != self.receipt_sha256 {
            return Err(Fixed64AllocationError::InternalInvariant(
                "fixed64 allocation receipt changed",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64AllocationError {
    InvalidInventory(&'static str),
    InternalInvariant(&'static str),
}

impl fmt::Display for Fixed64AllocationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidInventory(message) => {
                write!(formatter, "invalid fixed64 inventory: {message}")
            }
            Self::InternalInvariant(message) => {
                write!(formatter, "fixed64 internal invariant failed: {message}")
            }
        }
    }
}

impl std::error::Error for Fixed64AllocationError {}

fn lane_for_slot(slot_index: usize) -> (Fixed64Lane, usize) {
    FIXED64_LANE_RANGES
        .iter()
        .find_map(|(lane, start, end)| {
            (*start..=*end)
                .contains(&slot_index)
                .then_some((*lane, slot_index - *start))
        })
        .expect("frozen fixed64 ranges cover every slot")
}

fn build_slot(inventory: &Fixed64FeatureInventory, slot_index: usize) -> Fixed64Slot {
    let (lane, lane_offset) = lane_for_slot(slot_index);
    let mut slot = Fixed64Slot {
        slot_index,
        lane,
        lane_offset,
        declared_anchor_kind: declared_anchor_kind(lane),
        required_features: Vec::new(),
        missing_features: Vec::new(),
        v7_control_source_index: None,
        so3_sequence_index: None,
        true_conformer_rank: None,
        retained_source_index: None,
        selected_source_receipt_sha256s: Vec::new(),
        generation_parent: None,
        receipt_sha256: [0; 32],
    };

    match lane {
        Fixed64Lane::PocketCenteredControls | Fixed64Lane::UniformSourceControls => {
            let control_offset = if lane == Fixed64Lane::UniformSourceControls {
                8
            } else {
                0
            };
            let index =
                u32::try_from(lane_offset + control_offset).expect("fixed control index fits u32");
            slot.v7_control_source_index = Some(index);
            slot.required_features
                .push(Fixed64Requirement::V7ControlSource(index as u8));
            if let Some(source) = inventory.v7_control(index) {
                slot.selected_source_receipt_sha256s
                    .push(source.receipt_sha256);
                slot.generation_parent = Some(parent(
                    source,
                    Fixed64GenerationParentRole::ExactPassthroughParent,
                ));
            } else {
                slot.missing_features
                    .push(Fixed64MissingFeature::V7ControlSource(index as u8));
            }
        }
        Fixed64Lane::DeterministicIndependentSo3 => {
            slot.so3_sequence_index = Some(lane_offset as u8);
            slot.generation_parent = Some(parent(
                inventory.exact_v11_source.ligand_source(),
                Fixed64GenerationParentRole::GeneratorInputParent,
            ));
        }
        Fixed64Lane::TrueConformerIndependentSo3 => {
            let rank = TRUE_CONFORMER_SLOT_RANKS[lane_offset];
            slot.so3_sequence_index = Some(lane_offset as u8);
            slot.true_conformer_rank = Some(rank);
            slot.required_features
                .push(Fixed64Requirement::TrueConformerRank(rank));
            if let Some(source) = inventory.conformer(rank) {
                slot.selected_source_receipt_sha256s
                    .push(source.receipt_sha256);
                slot.generation_parent = Some(parent(
                    source,
                    Fixed64GenerationParentRole::GeneratorInputParent,
                ));
            } else {
                slot.missing_features
                    .push(Fixed64MissingFeature::TrueConformer(rank));
            }
        }
        Fixed64Lane::LigandDonorToReceptorAcceptor => {
            select_feature_pair(
                inventory,
                &mut slot,
                Fixed64FeatureKind::LigandDonor,
                Fixed64FeatureKind::ReceptorAcceptor,
                Fixed64MissingFeature::LigandDonor,
                Fixed64MissingFeature::ReceptorAcceptor,
            );
            use_exact_parent(inventory, &mut slot);
        }
        Fixed64Lane::LigandAcceptorToReceptorDonor => {
            select_feature_pair(
                inventory,
                &mut slot,
                Fixed64FeatureKind::LigandAcceptor,
                Fixed64FeatureKind::ReceptorDonor,
                Fixed64MissingFeature::LigandAcceptor,
                Fixed64MissingFeature::ReceptorDonor,
            );
            use_exact_parent(inventory, &mut slot);
        }
        Fixed64Lane::ComplementaryCharge => {
            slot.required_features
                .push(Fixed64Requirement::ComplementaryChargeAnchor);
            let positive = (
                Fixed64FeatureKind::LigandPositiveSite,
                Fixed64FeatureKind::ReceptorNegativeSite,
            );
            let negative = (
                Fixed64FeatureKind::LigandNegativeSite,
                Fixed64FeatureKind::ReceptorPositiveSite,
            );
            let available: Vec<_> = [positive, negative]
                .into_iter()
                .filter(|(left, right)| {
                    inventory.has_feature(*left) && inventory.has_feature(*right)
                })
                .collect();
            if available.is_empty() {
                slot.missing_features
                    .push(Fixed64MissingFeature::ComplementaryChargeAnchor);
            } else {
                let (left, right) = available[lane_offset % available.len()];
                push_feature_receipt(inventory, &mut slot, left);
                push_feature_receipt(inventory, &mut slot, right);
            }
            use_exact_parent(inventory, &mut slot);
        }
        Fixed64Lane::AromaticPlane => {
            select_feature_pair(
                inventory,
                &mut slot,
                Fixed64FeatureKind::LigandAromaticPlane,
                Fixed64FeatureKind::ReceptorAromaticPlane,
                Fixed64MissingFeature::LigandAromaticPlane,
                Fixed64MissingFeature::ReceptorAromaticPlane,
            );
            use_exact_parent(inventory, &mut slot);
        }
        Fixed64Lane::PrincipalAxisShape => {
            select_feature_pair(
                inventory,
                &mut slot,
                Fixed64FeatureKind::LigandShapeAxis,
                Fixed64FeatureKind::PocketShapeAxis,
                Fixed64MissingFeature::LigandShapeAxis,
                Fixed64MissingFeature::PocketShapeAxis,
            );
            use_exact_parent(inventory, &mut slot);
        }
        Fixed64Lane::PairedRetainedControls => {
            let index = RETAINED_SOURCE_INDICES[lane_offset];
            slot.retained_source_index = Some(index);
            slot.required_features
                .push(Fixed64Requirement::RetainedSource(index));
            if let Some(source) = inventory.retained(index) {
                slot.selected_source_receipt_sha256s
                    .push(source.receipt_sha256);
                slot.generation_parent = Some(parent(
                    source,
                    Fixed64GenerationParentRole::ExactPassthroughParent,
                ));
            } else {
                slot.missing_features
                    .push(Fixed64MissingFeature::RetainedSource(index));
            }
        }
    }
    slot.receipt_sha256 = slot_sha256(&slot);
    slot
}

fn declared_anchor_kind(lane: Fixed64Lane) -> Option<Fixed64AnchorKind> {
    match lane {
        Fixed64Lane::LigandDonorToReceptorAcceptor => {
            Some(Fixed64AnchorKind::LigandDonorToReceptorAcceptor)
        }
        Fixed64Lane::LigandAcceptorToReceptorDonor => {
            Some(Fixed64AnchorKind::LigandAcceptorToReceptorDonor)
        }
        Fixed64Lane::ComplementaryCharge => Some(Fixed64AnchorKind::ComplementaryCharge),
        Fixed64Lane::AromaticPlane => Some(Fixed64AnchorKind::AromaticPlane),
        Fixed64Lane::PrincipalAxisShape => Some(Fixed64AnchorKind::PrincipalAxisShape),
        _ => None,
    }
}

fn select_feature_pair(
    inventory: &Fixed64FeatureInventory,
    slot: &mut Fixed64Slot,
    first: Fixed64FeatureKind,
    second: Fixed64FeatureKind,
    missing_first: Fixed64MissingFeature,
    missing_second: Fixed64MissingFeature,
) {
    slot.required_features.extend([
        Fixed64Requirement::Feature(first),
        Fixed64Requirement::Feature(second),
    ]);
    if inventory.has_feature(first) {
        push_feature_receipt(inventory, slot, first);
    } else {
        slot.missing_features.push(missing_first);
    }
    if inventory.has_feature(second) {
        push_feature_receipt(inventory, slot, second);
    } else {
        slot.missing_features.push(missing_second);
    }
}

fn push_feature_receipt(
    inventory: &Fixed64FeatureInventory,
    slot: &mut Fixed64Slot,
    kind: Fixed64FeatureKind,
) {
    if let Some(receipt) = inventory.feature_receipt(kind, slot.lane_offset) {
        slot.selected_source_receipt_sha256s.push(receipt);
    }
}

fn use_exact_parent(inventory: &Fixed64FeatureInventory, slot: &mut Fixed64Slot) {
    slot.generation_parent = Some(parent(
        inventory.exact_v11_source.ligand_source(),
        Fixed64GenerationParentRole::GeneratorInputParent,
    ));
}

const fn parent(
    source: Fixed64SourceEvidence,
    role: Fixed64GenerationParentRole,
) -> Fixed64GenerationParent {
    Fixed64GenerationParent {
        proposal_sha256: source.proposal_sha256,
        coordinate_sha256: source.coordinate_sha256,
        role,
    }
}

fn validate_indexed_sources(
    values: &[Fixed64IndexedSourceEvidence],
    maximum: usize,
    allowed: impl Fn(u32) -> bool,
    message: &'static str,
) -> Result<(), Fixed64AllocationError> {
    if values.len() > maximum
        || values.iter().any(|row| !allowed(row.source_index))
        || values
            .windows(2)
            .any(|rows| rows[0].source_index >= rows[1].source_index)
        || !unique_receipts(values.iter().map(|row| row.source.receipt_sha256))
    {
        return Err(Fixed64AllocationError::InvalidInventory(message));
    }
    Ok(())
}

fn unique_receipts(values: impl Iterator<Item = [u8; 32]>) -> bool {
    let mut observed = BTreeSet::new();
    values.into_iter().all(|value| observed.insert(value))
}

const fn all_feature_kinds() -> [Fixed64FeatureKind; 12] {
    [
        Fixed64FeatureKind::LigandDonor,
        Fixed64FeatureKind::LigandAcceptor,
        Fixed64FeatureKind::ReceptorDonor,
        Fixed64FeatureKind::ReceptorAcceptor,
        Fixed64FeatureKind::LigandPositiveSite,
        Fixed64FeatureKind::LigandNegativeSite,
        Fixed64FeatureKind::ReceptorPositiveSite,
        Fixed64FeatureKind::ReceptorNegativeSite,
        Fixed64FeatureKind::LigandAromaticPlane,
        Fixed64FeatureKind::ReceptorAromaticPlane,
        Fixed64FeatureKind::LigandShapeAxis,
        Fixed64FeatureKind::PocketShapeAxis,
    ]
}

fn inventory_sha256(inventory: &Fixed64FeatureInventory) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_feature_inventory/native-v1");
    exact_source_evidence(&mut hash, inventory.exact_v11_source);
    hash.usize(inventory.atomic_features.len());
    for feature in &inventory.atomic_features {
        hash.byte(feature.kind.tag());
        hash.digest(feature.receipt_sha256);
    }
    indexed_sources(&mut hash, &inventory.v7_control_sources);
    hash.usize(inventory.conformer_sources.len());
    for row in &inventory.conformer_sources {
        hash.byte(row.rank);
        source_evidence(&mut hash, row.source);
    }
    indexed_sources(&mut hash, &inventory.retained_sources);
    hash.finish()
}

fn indexed_sources(hash: &mut CanonicalHash, values: &[Fixed64IndexedSourceEvidence]) {
    hash.usize(values.len());
    for row in values {
        hash.u32(row.source_index);
        source_evidence(hash, row.source);
    }
}

fn source_evidence(hash: &mut CanonicalHash, source: Fixed64SourceEvidence) {
    hash.digest(source.receipt_sha256);
    hash.digest(source.proposal_sha256);
    hash.digest(source.coordinate_sha256);
}

fn exact_source_evidence(hash: &mut CanonicalHash, source: Fixed64ExactV11SourceEvidence) {
    hash.digest(source.source_receipt_sha256);
    hash.digest(source.proposal_sha256);
    hash.digest(source.ligand_coordinate_sha256);
    hash.digest(source.receptor_coordinate_sha256);
    hash.digest(source.prepared_ligand_topology_sha256);
    hash.digest(source.prepared_receptor_topology_sha256);
    hash.digest(source.ligand_vdw_radii_sha256);
    hash.digest(source.ligand_heavy_atom_mask_sha256);
    hash.digest(source.receptor_vdw_radii_sha256);
}

fn slot_sha256(slot: &Fixed64Slot) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_slot/native-v1");
    hash.string(NATIVE_FIXED64_SLOT_SCHEMA_ID);
    hash.usize(slot.slot_index);
    hash.byte(slot.lane.tag());
    hash.usize(slot.lane_offset);
    hash.option(slot.declared_anchor_kind, |hash, value| {
        hash.byte(value.tag())
    });
    hash.usize(slot.required_features.len());
    for value in &slot.required_features {
        requirement(&mut hash, *value);
    }
    hash.usize(slot.missing_features.len());
    for value in &slot.missing_features {
        missing_feature(&mut hash, *value);
    }
    hash.option(slot.v7_control_source_index, |hash, value| hash.u32(value));
    hash.option(slot.so3_sequence_index, |hash, value| hash.byte(value));
    hash.option(slot.true_conformer_rank, |hash, value| hash.byte(value));
    hash.option(slot.retained_source_index, |hash, value| hash.u32(value));
    hash.usize(slot.selected_source_receipt_sha256s.len());
    for value in &slot.selected_source_receipt_sha256s {
        hash.digest(*value);
    }
    hash.option(slot.generation_parent, |hash, value| {
        hash.digest(value.proposal_sha256);
        hash.digest(value.coordinate_sha256);
        hash.byte(match value.role {
            Fixed64GenerationParentRole::ExactPassthroughParent => 0,
            Fixed64GenerationParentRole::GeneratorInputParent => 1,
        });
    });
    hash.bool(slot.generation_eligible());
    hash.bool(false);
    hash.bool(false);
    hash.bool(true);
    hash.finish()
}

fn requirement(hash: &mut CanonicalHash, value: Fixed64Requirement) {
    match value {
        Fixed64Requirement::V7ControlSource(index) => {
            hash.byte(0);
            hash.byte(index);
        }
        Fixed64Requirement::TrueConformerRank(rank) => {
            hash.byte(1);
            hash.byte(rank);
        }
        Fixed64Requirement::Feature(kind) => {
            hash.byte(2);
            hash.byte(kind.tag());
        }
        Fixed64Requirement::ComplementaryChargeAnchor => hash.byte(3),
        Fixed64Requirement::RetainedSource(index) => {
            hash.byte(4);
            hash.u32(index);
        }
    }
}

fn missing_feature(hash: &mut CanonicalHash, value: Fixed64MissingFeature) {
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

fn allocation_sha256(
    inventory_sha256: [u8; 32],
    slots: &[Fixed64Slot; FIXED64_CANDIDATE_COUNT],
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_allocation/native-v1");
    hash.string(NATIVE_FIXED64_ALLOCATION_SCHEMA_ID);
    hash.string(FIXED64_PROFILE_ID);
    hash.digest(inventory_sha256);
    hash.usize(FIXED64_CANDIDATE_COUNT);
    for slot in slots {
        hash.digest(slot.receipt_sha256);
    }
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(true);
    hash.bool(false);
    hash.finish()
}
