use std::collections::BTreeSet;
use std::fmt;

use crate::geometry::{centroid, GEOMETRY_EPSILON};
use crate::native_hash::CanonicalHash;
use crate::{
    native_fixed64_coordinate_sha256, orientations, Fixed64Allocation, Fixed64FeatureKind,
    Fixed64Lane, Fixed64SourceEvidence, Quaternion, Vec3, FIXED64_MAX_LIGAND_ATOMS,
};

pub const NATIVE_FIXED64_INDEXED_SO3_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_indexed_so3_native_placement/1.0.0";
pub const NATIVE_FIXED64_SINGLE_ANCHOR_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_single_anchor_native_placement/1.0.0";
pub const NATIVE_FIXED64_FEATURE_GEOMETRY_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_mixed64_native_feature_geometry/1.0.0";
pub const NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID: &str =
    "betelgeuze.engine_v2_mixed64_indexed_source_bound_so3_native/1.0.0";
pub const NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID: &str =
    "betelgeuze.engine_v2_mixed64_single_anchor_rigid_native/1.0.0";

const MAX_FEATURE_ATOM_INDICES: usize = 4_096;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64PlacementErrorCode {
    InvalidInput,
    AllocationSlotNotEligible,
    UnsupportedLane,
    SourceIdentityMismatch,
    FeatureCrossWired,
    FeatureAtomIndexOutOfRange,
    DegenerateSo3SourceGeometry,
    DegenerateLigandDirection,
    DegenerateReceptorDirection,
    DegenerateLocalSurfaceNormal,
    DegenerateAromaticPlane,
    DegeneratePrincipalAxis,
    GeometricPrecheckFailed,
    InternalInvariant,
}

impl Fixed64PlacementErrorCode {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::InvalidInput => "invalid_input",
            Self::AllocationSlotNotEligible => "allocation_slot_not_eligible",
            Self::UnsupportedLane => "unsupported_lane",
            Self::SourceIdentityMismatch => "source_identity_mismatch",
            Self::FeatureCrossWired => "feature_cross_wired",
            Self::FeatureAtomIndexOutOfRange => "feature_atom_index_out_of_range",
            Self::DegenerateSo3SourceGeometry => "degenerate_so3_source_geometry",
            Self::DegenerateLigandDirection => "degenerate_ligand_direction",
            Self::DegenerateReceptorDirection => "degenerate_receptor_direction",
            Self::DegenerateLocalSurfaceNormal => "degenerate_local_surface_normal",
            Self::DegenerateAromaticPlane => "degenerate_aromatic_plane",
            Self::DegeneratePrincipalAxis => "degenerate_principal_axis",
            Self::GeometricPrecheckFailed => "geometric_precheck_failed",
            Self::InternalInvariant => "internal_invariant",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64PlacementError {
    code: Fixed64PlacementErrorCode,
    message: &'static str,
}

impl Fixed64PlacementError {
    pub(crate) const fn new(code: Fixed64PlacementErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> Fixed64PlacementErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for Fixed64PlacementError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native fixed64 placement: {}", self.message)
    }
}

impl std::error::Error for Fixed64PlacementError {}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64PlacementSource {
    evidence: Fixed64SourceEvidence,
    coordinates_angstrom: Vec<Vec3>,
    receipt_sha256: [u8; 32],
}

impl Fixed64PlacementSource {
    pub fn new(
        evidence: Fixed64SourceEvidence,
        coordinates_angstrom: Vec<Vec3>,
    ) -> Result<Self, Fixed64PlacementError> {
        if coordinates_angstrom.is_empty() || coordinates_angstrom.len() > FIXED64_MAX_LIGAND_ATOMS
        {
            return Err(invalid(
                "source coordinate denominator is outside fixed64 bounds",
            ));
        }
        let coordinate_sha256 = native_fixed64_coordinate_sha256(&coordinates_angstrom)
            .map_err(|_| invalid("source coordinates are outside their safety envelope"))?;
        if coordinate_sha256 != evidence.coordinate_sha256 {
            return Err(source_mismatch(
                "source coordinate identity does not match its evidence",
            ));
        }
        let mut value = Self {
            evidence,
            coordinates_angstrom,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = placement_source_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub const fn evidence(&self) -> Fixed64SourceEvidence {
        self.evidence
    }

    #[must_use]
    pub fn coordinates_angstrom(&self) -> &[Vec3] {
        &self.coordinates_angstrom
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        native_fixed64_coordinate_sha256(&self.coordinates_angstrom)
            .is_ok_and(|observed| observed == self.evidence.coordinate_sha256)
            && placement_source_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fixed64FeatureGeometry {
    kind: Fixed64FeatureKind,
    allocation_feature_receipt_sha256: [u8; 32],
    atom_indices: Vec<usize>,
    receipt_sha256: [u8; 32],
}

impl Fixed64FeatureGeometry {
    pub fn new(
        kind: Fixed64FeatureKind,
        allocation_feature_receipt_sha256: [u8; 32],
        atom_indices: Vec<usize>,
    ) -> Result<Self, Fixed64PlacementError> {
        if atom_indices.is_empty()
            || atom_indices.len() > MAX_FEATURE_ATOM_INDICES
            || atom_indices.iter().copied().collect::<BTreeSet<_>>().len() != atom_indices.len()
        {
            return Err(invalid(
                "feature atom indices are empty, duplicated, or over capacity",
            ));
        }
        let valid_count = match kind {
            Fixed64FeatureKind::LigandDonor | Fixed64FeatureKind::ReceptorDonor => {
                atom_indices.len() == 2
            }
            Fixed64FeatureKind::LigandAcceptor | Fixed64FeatureKind::ReceptorAcceptor => {
                atom_indices.len() == 1
            }
            Fixed64FeatureKind::LigandAromaticPlane | Fixed64FeatureKind::ReceptorAromaticPlane => {
                atom_indices.len() >= 3
            }
            _ => true,
        };
        if !valid_count {
            return Err(invalid("feature atom count disagrees with its frozen kind"));
        }
        let mut value = Self {
            kind,
            allocation_feature_receipt_sha256,
            atom_indices,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = feature_geometry_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub const fn kind(&self) -> Fixed64FeatureKind {
        self.kind
    }

    #[must_use]
    pub const fn allocation_feature_receipt_sha256(&self) -> [u8; 32] {
        self.allocation_feature_receipt_sha256
    }

    #[must_use]
    pub fn atom_indices(&self) -> &[usize] {
        &self.atom_indices
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        feature_geometry_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fixed64FeatureGeometryInventory {
    features: Vec<Fixed64FeatureGeometry>,
    receipt_sha256: [u8; 32],
}

impl Fixed64FeatureGeometryInventory {
    pub fn new(features: Vec<Fixed64FeatureGeometry>) -> Result<Self, Fixed64PlacementError> {
        if features.windows(2).any(|rows| {
            (rows[0].kind, rows[0].allocation_feature_receipt_sha256)
                >= (rows[1].kind, rows[1].allocation_feature_receipt_sha256)
        }) || features
            .iter()
            .map(|feature| feature.allocation_feature_receipt_sha256)
            .collect::<BTreeSet<_>>()
            .len()
            != features.len()
            || features.iter().any(|feature| !feature.has_valid_receipt())
        {
            return Err(invalid(
                "feature geometry inventory is duplicated or noncanonical",
            ));
        }
        let mut value = Self {
            features,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = feature_inventory_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub fn features(&self) -> &[Fixed64FeatureGeometry] {
        &self.features
    }

    #[must_use]
    pub fn feature_for_allocation_receipt(
        &self,
        receipt_sha256: [u8; 32],
    ) -> Option<&Fixed64FeatureGeometry> {
        self.features
            .iter()
            .find(|feature| feature.allocation_feature_receipt_sha256 == receipt_sha256)
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.features
            .iter()
            .all(Fixed64FeatureGeometry::has_valid_receipt)
            && feature_inventory_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64IndexedSo3Placement {
    allocation_receipt_sha256: [u8; 32],
    allocation_slot_receipt_sha256: [u8; 32],
    slot_index: usize,
    lane: Fixed64Lane,
    so3_sequence_index: u8,
    source: Fixed64PlacementSource,
    pocket_center_angstrom: Vec3,
    pocket_normal: Vec3,
    source_seed_sha256: [u8; 32],
    raw_sequence_index: u64,
    accepted_sequence_index: u32,
    quaternion: Quaternion,
    translation_angstrom: Vec3,
    output_coordinates_angstrom: Vec<Vec3>,
    output_coordinate_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

impl Fixed64IndexedSo3Placement {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn lane(&self) -> Fixed64Lane {
        self.lane
    }

    #[must_use]
    pub const fn so3_sequence_index(&self) -> u8 {
        self.so3_sequence_index
    }

    #[must_use]
    pub fn source(&self) -> &Fixed64PlacementSource {
        &self.source
    }

    #[must_use]
    pub const fn pocket_center_angstrom(&self) -> Vec3 {
        self.pocket_center_angstrom
    }

    #[must_use]
    pub const fn pocket_normal(&self) -> Vec3 {
        self.pocket_normal
    }

    #[must_use]
    pub const fn source_seed_sha256(&self) -> [u8; 32] {
        self.source_seed_sha256
    }

    #[must_use]
    pub const fn raw_sequence_index(&self) -> u64 {
        self.raw_sequence_index
    }

    #[must_use]
    pub const fn accepted_sequence_index(&self) -> u32 {
        self.accepted_sequence_index
    }

    #[must_use]
    pub const fn quaternion(&self) -> Quaternion {
        self.quaternion
    }

    #[must_use]
    pub const fn translation_angstrom(&self) -> Vec3 {
        self.translation_angstrom
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
    pub const fn result_dependent_input_consumed(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.source.has_valid_receipt()
            && native_fixed64_coordinate_sha256(&self.output_coordinates_angstrom)
                .is_ok_and(|value| value == self.output_coordinate_sha256)
            && indexed_so3_sha256(self) == self.receipt_sha256
    }
}

pub fn generate_native_fixed64_indexed_so3(
    allocation: &Fixed64Allocation,
    slot_index: usize,
    source: Fixed64PlacementSource,
    pocket_center_angstrom: Vec3,
    pocket_normal: Vec3,
) -> Result<Fixed64IndexedSo3Placement, Fixed64PlacementError> {
    if !allocation.has_valid_receipt() || !source.has_valid_receipt() {
        return Err(source_mismatch("allocation or source receipt is invalid"));
    }
    let slot = allocation
        .slots()
        .get(slot_index)
        .ok_or_else(|| unsupported("slot index is outside fixed64"))?;
    if !matches!(
        slot.lane(),
        Fixed64Lane::DeterministicIndependentSo3 | Fixed64Lane::TrueConformerIndependentSo3
    ) {
        return Err(unsupported("slot is not an indexed SO3 lane"));
    }
    if !slot.generation_eligible() {
        return Err(not_eligible(
            "indexed SO3 slot retains typed feature failures",
        ));
    }
    let sequence_index = slot
        .so3_sequence_index()
        .ok_or_else(|| internal("indexed SO3 slot lacks its frozen sequence index"))?;
    validate_source_for_slot(allocation, slot, &source)?;
    validate_placement_vec3(pocket_center_angstrom)?;
    let pocket_normal = pocket_normal
        .normalized("fixed64 pocket normal")
        .map_err(|_| {
            placement_error(
                Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                "pocket normal is degenerate",
            )
        })?;
    let first = source.coordinates_angstrom[0];
    if !source.coordinates_angstrom[1..]
        .iter()
        .any(|coordinate| coordinate.minus(first).norm_squared() > GEOMETRY_EPSILON)
    {
        return Err(placement_error(
            Fixed64PlacementErrorCode::DegenerateSo3SourceGeometry,
            "SO3 source must contain at least two distinct points",
        ));
    }
    let source_seed_sha256 =
        indexed_so3_source_seed_sha256(source.evidence, pocket_center_angstrom, pocket_normal);
    let orientation_count = usize::from(sequence_index) + 1;
    let sequence = orientations(source_seed_sha256, orientation_count).map_err(|_| {
        placement_error(
            Fixed64PlacementErrorCode::InternalInvariant,
            "low-discrepancy SO3 sequence failed",
        )
    })?;
    let selected = sequence
        .get(usize::from(sequence_index))
        .ok_or_else(|| internal("SO3 sequence selection changed"))?;
    if selected.orientation_index != u32::from(sequence_index) {
        return Err(internal("SO3 accepted sequence index changed"));
    }
    let source_center = centroid(&source.coordinates_angstrom);
    let translation_angstrom =
        pocket_center_angstrom.minus(selected.quaternion.rotate(source_center));
    let output_coordinates_angstrom = source
        .coordinates_angstrom
        .iter()
        .map(|coordinate| {
            selected
                .quaternion
                .rotate(*coordinate)
                .plus(translation_angstrom)
        })
        .collect::<Vec<_>>();
    let output_coordinate_sha256 =
        native_fixed64_coordinate_sha256(&output_coordinates_angstrom)
            .map_err(|_| internal("indexed SO3 output coordinates are invalid"))?;
    let mut value = Fixed64IndexedSo3Placement {
        allocation_receipt_sha256: allocation.receipt_sha256(),
        allocation_slot_receipt_sha256: slot.receipt_sha256(),
        slot_index,
        lane: slot.lane(),
        so3_sequence_index: sequence_index,
        source,
        pocket_center_angstrom,
        pocket_normal,
        source_seed_sha256,
        raw_sequence_index: selected.raw_sequence_index,
        accepted_sequence_index: selected.orientation_index,
        quaternion: selected.quaternion,
        translation_angstrom,
        output_coordinates_angstrom,
        output_coordinate_sha256,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = indexed_so3_sha256(&value);
    Ok(value)
}

fn validate_source_for_slot(
    allocation: &Fixed64Allocation,
    slot: &crate::Fixed64Slot,
    source: &Fixed64PlacementSource,
) -> Result<(), Fixed64PlacementError> {
    let parent = slot
        .generation_parent()
        .ok_or_else(|| source_mismatch("slot lacks its generation parent"))?;
    if source.evidence.proposal_sha256 != parent.proposal_sha256
        || source.evidence.coordinate_sha256 != parent.coordinate_sha256
    {
        return Err(source_mismatch(
            "source proposal or coordinate is cross-wired to another slot",
        ));
    }
    match slot.lane() {
        Fixed64Lane::DeterministicIndependentSo3 => {
            let exact = allocation.inventory().exact_v11_source();
            if source.evidence != exact.ligand_source()
                || !slot.selected_source_receipt_sha256s().is_empty()
            {
                return Err(source_mismatch(
                    "independent SO3 source is not the exact V1.1 source",
                ));
            }
        }
        Fixed64Lane::TrueConformerIndependentSo3 => {
            if slot.selected_source_receipt_sha256s() != [source.evidence.receipt_sha256] {
                return Err(source_mismatch(
                    "true-conformer SO3 source receipt is cross-wired",
                ));
            }
        }
        _ => return Err(unsupported("slot is not source-bound indexed SO3")),
    }
    Ok(())
}

fn placement_source_sha256(source: &Fixed64PlacementSource) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_placement_source/native-v1");
    hash.digest(source.evidence.receipt_sha256);
    hash.digest(source.evidence.proposal_sha256);
    hash.digest(source.evidence.coordinate_sha256);
    hash.digest(native_fixed64_coordinate_sha256(&source.coordinates_angstrom).unwrap_or([0; 32]));
    hash.finish()
}

fn feature_geometry_sha256(feature: &Fixed64FeatureGeometry) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_feature_geometry/native-v1");
    hash.string(NATIVE_FIXED64_FEATURE_GEOMETRY_SCHEMA_ID);
    hash.byte(feature_kind_tag(feature.kind));
    hash.digest(feature.allocation_feature_receipt_sha256);
    hash.usize(feature.atom_indices.len());
    for index in &feature.atom_indices {
        hash.usize(*index);
    }
    hash.bool(false);
    hash.finish()
}

fn feature_inventory_sha256(inventory: &Fixed64FeatureGeometryInventory) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_feature_geometry_inventory/native-v1");
    hash.usize(inventory.features.len());
    for feature in &inventory.features {
        hash.digest(feature.receipt_sha256);
    }
    hash.finish()
}

fn indexed_so3_source_seed_sha256(
    source: Fixed64SourceEvidence,
    pocket_center_angstrom: Vec3,
    pocket_normal: Vec3,
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_indexed_so3_seed/native-v1");
    hash.digest(source.receipt_sha256);
    hash.digest(source.coordinate_sha256);
    hash.vec3(pocket_center_angstrom);
    hash.vec3(pocket_normal);
    hash.string(NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID);
    hash.finish()
}

fn indexed_so3_sha256(value: &Fixed64IndexedSo3Placement) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_indexed_so3/native-v1");
    hash.string(NATIVE_FIXED64_INDEXED_SO3_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID);
    hash.digest(value.allocation_receipt_sha256);
    hash.digest(value.allocation_slot_receipt_sha256);
    hash.usize(value.slot_index);
    hash.string(value.lane.id());
    hash.byte(value.so3_sequence_index);
    hash.digest(value.source.receipt_sha256);
    hash.vec3(value.pocket_center_angstrom);
    hash.vec3(value.pocket_normal);
    hash.digest(value.source_seed_sha256);
    hash.u64(value.raw_sequence_index);
    hash.u32(value.accepted_sequence_index);
    hash.f64(value.quaternion.x);
    hash.f64(value.quaternion.y);
    hash.f64(value.quaternion.z);
    hash.f64(value.quaternion.w);
    hash.vec3(value.translation_angstrom);
    hash.digest(value.output_coordinate_sha256);
    hash.bool(true);
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

const fn feature_kind_tag(kind: Fixed64FeatureKind) -> u8 {
    match kind {
        Fixed64FeatureKind::LigandDonor => 0,
        Fixed64FeatureKind::LigandAcceptor => 1,
        Fixed64FeatureKind::ReceptorDonor => 2,
        Fixed64FeatureKind::ReceptorAcceptor => 3,
        Fixed64FeatureKind::LigandPositiveSite => 4,
        Fixed64FeatureKind::LigandNegativeSite => 5,
        Fixed64FeatureKind::ReceptorPositiveSite => 6,
        Fixed64FeatureKind::ReceptorNegativeSite => 7,
        Fixed64FeatureKind::LigandAromaticPlane => 8,
        Fixed64FeatureKind::ReceptorAromaticPlane => 9,
        Fixed64FeatureKind::LigandShapeAxis => 10,
        Fixed64FeatureKind::PocketShapeAxis => 11,
    }
}

fn validate_placement_vec3(value: Vec3) -> Result<(), Fixed64PlacementError> {
    native_fixed64_coordinate_sha256(&[value])
        .map(|_| ())
        .map_err(|_| invalid("placement vector is outside its safety envelope"))
}

const fn placement_error(
    code: Fixed64PlacementErrorCode,
    message: &'static str,
) -> Fixed64PlacementError {
    Fixed64PlacementError::new(code, message)
}

const fn invalid(message: &'static str) -> Fixed64PlacementError {
    placement_error(Fixed64PlacementErrorCode::InvalidInput, message)
}

const fn not_eligible(message: &'static str) -> Fixed64PlacementError {
    placement_error(
        Fixed64PlacementErrorCode::AllocationSlotNotEligible,
        message,
    )
}

const fn unsupported(message: &'static str) -> Fixed64PlacementError {
    placement_error(Fixed64PlacementErrorCode::UnsupportedLane, message)
}

const fn source_mismatch(message: &'static str) -> Fixed64PlacementError {
    placement_error(Fixed64PlacementErrorCode::SourceIdentityMismatch, message)
}

const fn internal(message: &'static str) -> Fixed64PlacementError {
    placement_error(Fixed64PlacementErrorCode::InternalInvariant, message)
}
