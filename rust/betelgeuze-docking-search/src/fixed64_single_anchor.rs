use crate::fixed64_placement::{
    Fixed64FeatureGeometry, Fixed64FeatureGeometryInventory, Fixed64PlacementError,
    Fixed64PlacementErrorCode, Fixed64PlacementSource,
};
use crate::geometry::{centroid, GEOMETRY_EPSILON};
use crate::native_hash::CanonicalHash;
use crate::{
    evaluate_fixed64_geometric_metrics, native_fixed64_coordinate_sha256,
    native_fixed64_heavy_atom_mask_sha256, native_fixed64_radii_sha256, Fixed64Allocation,
    Fixed64AnchorKind, Fixed64FeatureKind, Fixed64GeometricInput, Fixed64GeometricMetrics,
    Fixed64Lane, Quaternion, Vec3, FIXED64_MAX_LIGAND_ATOMS, HARD_REJECTION_MINIMUM_VDW_RATIO,
    NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID, NATIVE_FIXED64_SINGLE_ANCHOR_SCHEMA_ID,
};

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64SingleAnchorPlacement {
    allocation_receipt_sha256: [u8; 32],
    allocation_slot_receipt_sha256: [u8; 32],
    slot_index: usize,
    lane: Fixed64Lane,
    lane_offset: usize,
    declared_anchor_kind: Fixed64AnchorKind,
    source: Fixed64PlacementSource,
    feature_inventory_receipt_sha256: [u8; 32],
    selected_ligand_feature: Fixed64FeatureGeometry,
    selected_receptor_feature: Fixed64FeatureGeometry,
    geometric_input: Fixed64GeometricInput,
    ligand_anchor_point_angstrom: Vec3,
    receptor_anchor_point_angstrom: Vec3,
    target_anchor_point_angstrom: Vec3,
    local_surface_normal: Vec3,
    approach_vector: Vec3,
    ligand_direction: Vec3,
    alignment_target_direction: Vec3,
    target_distance_angstrom: f64,
    twist_angle_radians: f64,
    quaternion: Quaternion,
    translation_angstrom: Vec3,
    output_coordinates_angstrom: Vec<Vec3>,
    output_coordinate_sha256: [u8; 32],
    geometric_metrics: Fixed64GeometricMetrics,
    steric_precheck_passed: bool,
    receipt_sha256: [u8; 32],
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64SingleAnchorKernelPlacement {
    pub ligand_anchor_point_angstrom: Vec3,
    pub receptor_anchor_point_angstrom: Vec3,
    pub target_anchor_point_angstrom: Vec3,
    pub local_surface_normal: Vec3,
    pub approach_vector: Vec3,
    pub ligand_direction: Vec3,
    pub alignment_target_direction: Vec3,
    pub target_distance_angstrom: f64,
    pub twist_angle_radians: f64,
    pub quaternion: Quaternion,
    pub translation_angstrom: Vec3,
    pub output_coordinates_angstrom: Vec<Vec3>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum NativeFixed64SingleAnchorKernelOutcome {
    Placed(Box<NativeFixed64SingleAnchorKernelPlacement>),
    TypedFailure(Fixed64PlacementErrorCode),
}

const MAX_SINGLE_ANCHOR_FEATURE_COORDINATES: usize = 65_536;
const MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 100_000.0;

const fn anchor_kind_matches_lane(lane: Fixed64Lane, kind: Fixed64AnchorKind) -> bool {
    matches!(
        (lane, kind),
        (
            Fixed64Lane::LigandDonorToReceptorAcceptor,
            Fixed64AnchorKind::LigandDonorToReceptorAcceptor
        ) | (
            Fixed64Lane::LigandAcceptorToReceptorDonor,
            Fixed64AnchorKind::LigandAcceptorToReceptorDonor
        ) | (
            Fixed64Lane::ComplementaryCharge,
            Fixed64AnchorKind::ComplementaryCharge
        ) | (Fixed64Lane::AromaticPlane, Fixed64AnchorKind::AromaticPlane)
            | (
                Fixed64Lane::PrincipalAxisShape,
                Fixed64AnchorKind::PrincipalAxisShape
            )
    )
}

const fn valid_kernel_feature_cardinality(
    lane: Fixed64Lane,
    ligand_count: usize,
    receptor_count: usize,
) -> bool {
    match lane {
        Fixed64Lane::LigandDonorToReceptorAcceptor => ligand_count == 2 && receptor_count == 1,
        Fixed64Lane::LigandAcceptorToReceptorDonor => ligand_count == 1 && receptor_count == 2,
        Fixed64Lane::ComplementaryCharge | Fixed64Lane::PrincipalAxisShape => {
            ligand_count >= 1
                && ligand_count <= MAX_SINGLE_ANCHOR_FEATURE_COORDINATES
                && receptor_count >= 1
                && receptor_count <= MAX_SINGLE_ANCHOR_FEATURE_COORDINATES
        }
        Fixed64Lane::AromaticPlane => {
            ligand_count >= 3
                && ligand_count <= MAX_SINGLE_ANCHOR_FEATURE_COORDINATES
                && receptor_count >= 3
                && receptor_count <= MAX_SINGLE_ANCHOR_FEATURE_COORDINATES
        }
        _ => false,
    }
}

fn valid_kernel_coordinate(value: Vec3) -> bool {
    value.is_finite()
        && value.x.abs() <= MAX_ABSOLUTE_COORDINATE_ANGSTROM
        && value.y.abs() <= MAX_ABSOLUTE_COORDINATE_ANGSTROM
        && value.z.abs() <= MAX_ABSOLUTE_COORDINATE_ANGSTROM
}

pub fn native_fixed64_single_anchor_kernel(
    lane: Fixed64Lane,
    declared_anchor_kind: Fixed64AnchorKind,
    lane_offset: usize,
    source_coordinates_angstrom: &[Vec3],
    ligand_feature_coordinates_angstrom: &[Vec3],
    receptor_feature_coordinates_angstrom: &[Vec3],
    pocket_center_angstrom: Vec3,
) -> NativeFixed64SingleAnchorKernelOutcome {
    if !is_anchor_lane(lane) {
        return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::UnsupportedLane,
        );
    }
    if !anchor_kind_matches_lane(lane, declared_anchor_kind) {
        return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::FeatureCrossWired,
        );
    }
    if source_coordinates_angstrom.is_empty()
        || source_coordinates_angstrom.len() > FIXED64_MAX_LIGAND_ATOMS
        || !valid_kernel_feature_cardinality(
            lane,
            ligand_feature_coordinates_angstrom.len(),
            receptor_feature_coordinates_angstrom.len(),
        )
        || !valid_kernel_coordinate(pocket_center_angstrom)
        || source_coordinates_angstrom
            .iter()
            .chain(ligand_feature_coordinates_angstrom)
            .chain(receptor_feature_coordinates_angstrom)
            .copied()
            .any(|coordinate| !valid_kernel_coordinate(coordinate))
    {
        return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InvalidInput,
        );
    }
    let lane_width = anchor_lane_width(lane);
    if lane_offset >= lane_width {
        return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InternalInvariant,
        );
    }
    let geometry = match derive_anchor_geometry(
        lane,
        source_coordinates_angstrom,
        ligand_feature_coordinates_angstrom,
        receptor_feature_coordinates_angstrom,
        pocket_center_angstrom,
    ) {
        Ok(value) => value,
        Err(error) => return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(error.code()),
    };
    let target_distance_angstrom = anchor_target_distance(declared_anchor_kind);
    let target_anchor_point_angstrom = geometry.receptor_anchor_point.plus(
        geometry
            .local_surface_normal
            .scale(target_distance_angstrom),
    );
    let base_quaternion = match Quaternion::between(
        geometry.ligand_direction,
        geometry.alignment_target_direction,
    ) {
        Ok(value) => value,
        Err(_) => {
            return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
                Fixed64PlacementErrorCode::DegenerateLigandDirection,
            )
        }
    };
    let offset = f64::from(u32::try_from(lane_offset).expect("fixed64 lane offsets fit u32"));
    let width = f64::from(u32::try_from(lane_width).expect("fixed64 lane widths fit u32"));
    let twist_angle_radians = 2.0 * core::f64::consts::PI * offset / width;
    let twist_quaternion = match Quaternion::from_rotation_vector(
        geometry
            .alignment_target_direction
            .scale(twist_angle_radians),
    ) {
        Ok(value) => value,
        Err(_) => {
            return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
                Fixed64PlacementErrorCode::InternalInvariant,
            )
        }
    };
    let quaternion = match twist_quaternion.multiply(base_quaternion) {
        Ok(value) => value,
        Err(_) => {
            return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
                Fixed64PlacementErrorCode::InternalInvariant,
            )
        }
    };
    let translation_angstrom =
        target_anchor_point_angstrom.minus(quaternion.rotate(geometry.ligand_anchor_point));
    let output_coordinates_angstrom = source_coordinates_angstrom
        .iter()
        .map(|coordinate| quaternion.rotate(*coordinate).plus(translation_angstrom))
        .collect::<Vec<_>>();
    if output_coordinates_angstrom.iter().any(|coordinate| {
        !coordinate.is_finite()
            || coordinate.x.abs() > 100_000.0
            || coordinate.y.abs() > 100_000.0
            || coordinate.z.abs() > 100_000.0
    }) {
        return NativeFixed64SingleAnchorKernelOutcome::TypedFailure(
            Fixed64PlacementErrorCode::InternalInvariant,
        );
    }
    NativeFixed64SingleAnchorKernelOutcome::Placed(Box::new(
        NativeFixed64SingleAnchorKernelPlacement {
            ligand_anchor_point_angstrom: geometry.ligand_anchor_point,
            receptor_anchor_point_angstrom: geometry.receptor_anchor_point,
            target_anchor_point_angstrom,
            local_surface_normal: geometry.local_surface_normal,
            approach_vector: geometry.local_surface_normal.scale(-1.0),
            ligand_direction: geometry.ligand_direction,
            alignment_target_direction: geometry.alignment_target_direction,
            target_distance_angstrom,
            twist_angle_radians,
            quaternion,
            translation_angstrom,
            output_coordinates_angstrom,
        },
    ))
}

impl Fixed64SingleAnchorPlacement {
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
    pub const fn declared_anchor_kind(&self) -> Fixed64AnchorKind {
        self.declared_anchor_kind
    }

    #[must_use]
    pub fn source(&self) -> &Fixed64PlacementSource {
        &self.source
    }

    #[must_use]
    pub fn selected_ligand_feature(&self) -> &Fixed64FeatureGeometry {
        &self.selected_ligand_feature
    }

    #[must_use]
    pub fn selected_receptor_feature(&self) -> &Fixed64FeatureGeometry {
        &self.selected_receptor_feature
    }

    #[must_use]
    pub fn geometric_input(&self) -> &Fixed64GeometricInput {
        &self.geometric_input
    }

    #[must_use]
    pub const fn ligand_anchor_point_angstrom(&self) -> Vec3 {
        self.ligand_anchor_point_angstrom
    }

    #[must_use]
    pub const fn receptor_anchor_point_angstrom(&self) -> Vec3 {
        self.receptor_anchor_point_angstrom
    }

    #[must_use]
    pub const fn target_anchor_point_angstrom(&self) -> Vec3 {
        self.target_anchor_point_angstrom
    }

    #[must_use]
    pub const fn local_surface_normal(&self) -> Vec3 {
        self.local_surface_normal
    }

    #[must_use]
    pub const fn approach_vector(&self) -> Vec3 {
        self.approach_vector
    }

    #[must_use]
    pub const fn ligand_direction(&self) -> Vec3 {
        self.ligand_direction
    }

    #[must_use]
    pub const fn alignment_target_direction(&self) -> Vec3 {
        self.alignment_target_direction
    }

    #[must_use]
    pub const fn target_distance_angstrom(&self) -> f64 {
        self.target_distance_angstrom
    }

    #[must_use]
    pub const fn twist_angle_radians(&self) -> f64 {
        self.twist_angle_radians
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
    pub const fn geometric_metrics(&self) -> &Fixed64GeometricMetrics {
        &self.geometric_metrics
    }

    #[must_use]
    pub const fn steric_precheck_passed(&self) -> bool {
        self.steric_precheck_passed
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn fallback_allowed(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn multi_anchor_consumed(&self) -> bool {
        false
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
            && self.selected_ligand_feature.has_valid_receipt()
            && self.selected_receptor_feature.has_valid_receipt()
            && self.geometric_input.has_valid_receipt()
            && self.geometric_metrics.has_valid_receipt()
            && native_fixed64_coordinate_sha256(&self.output_coordinates_angstrom)
                .is_ok_and(|value| value == self.output_coordinate_sha256)
            && self.steric_precheck_passed
                == (self.geometric_metrics.minimum_vdw_ratio() >= HARD_REJECTION_MINIMUM_VDW_RATIO)
            && single_anchor_sha256(self) == self.receipt_sha256
    }
}

pub fn generate_native_fixed64_single_anchor(
    allocation: &Fixed64Allocation,
    slot_index: usize,
    source: Fixed64PlacementSource,
    feature_inventory: &Fixed64FeatureGeometryInventory,
    geometric_input: &Fixed64GeometricInput,
) -> Result<Fixed64SingleAnchorPlacement, Fixed64PlacementError> {
    if !allocation.has_valid_receipt()
        || !source.has_valid_receipt()
        || !feature_inventory.has_valid_receipt()
        || !geometric_input.has_valid_receipt()
    {
        return Err(error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "allocation, source, feature, or geometric receipt is invalid",
        ));
    }
    let slot = allocation.slots().get(slot_index).ok_or_else(|| {
        error(
            Fixed64PlacementErrorCode::UnsupportedLane,
            "slot index is outside fixed64",
        )
    })?;
    let declared_anchor_kind = slot.declared_anchor_kind().ok_or_else(|| {
        error(
            Fixed64PlacementErrorCode::UnsupportedLane,
            "slot is not a single-anchor lane",
        )
    })?;
    if !is_anchor_lane(slot.lane()) {
        return Err(error(
            Fixed64PlacementErrorCode::UnsupportedLane,
            "slot is not a frozen single-anchor lane",
        ));
    }
    if !slot.generation_eligible() {
        return Err(error(
            Fixed64PlacementErrorCode::AllocationSlotNotEligible,
            "single-anchor slot retains typed feature failures",
        ));
    }
    validate_exact_system_source(allocation, &source, geometric_input)?;
    if source.coordinates_angstrom().len() != geometric_input.ligand_vdw_radii_angstrom().len() {
        return Err(error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "ligand coordinates and exact topology denominators disagree",
        ));
    }
    let selected_receipts = slot.selected_source_receipt_sha256s();
    if selected_receipts.len() != 2 {
        return Err(error(
            Fixed64PlacementErrorCode::FeatureCrossWired,
            "single-anchor slot does not select exactly two features",
        ));
    }
    let selected_ligand_feature =
        selected_feature(allocation, feature_inventory, selected_receipts[0])?.clone();
    let selected_receptor_feature =
        selected_feature(allocation, feature_inventory, selected_receipts[1])?.clone();
    if !feature_pair_matches_lane(
        slot.lane(),
        selected_ligand_feature.kind(),
        selected_receptor_feature.kind(),
    ) {
        return Err(error(
            Fixed64PlacementErrorCode::FeatureCrossWired,
            "selected feature kinds are cross-wired to another lane",
        ));
    }
    let ligand_feature_coordinates =
        feature_coordinates(&selected_ligand_feature, source.coordinates_angstrom())?;
    let receptor_feature_coordinates = feature_coordinates(
        &selected_receptor_feature,
        geometric_input.receptor_coordinates_angstrom(),
    )?;
    let geometry = derive_anchor_geometry(
        slot.lane(),
        source.coordinates_angstrom(),
        &ligand_feature_coordinates,
        &receptor_feature_coordinates,
        geometric_input.pocket_center_angstrom(),
    )?;
    let target_distance_angstrom = anchor_target_distance(declared_anchor_kind);
    let target_anchor_point_angstrom = geometry.receptor_anchor_point.plus(
        geometry
            .local_surface_normal
            .scale(target_distance_angstrom),
    );
    let base_quaternion = Quaternion::between(
        geometry.ligand_direction,
        geometry.alignment_target_direction,
    )
    .map_err(|_| {
        error(
            Fixed64PlacementErrorCode::DegenerateLigandDirection,
            "single-anchor direction alignment failed",
        )
    })?;
    let lane_width = anchor_lane_width(slot.lane());
    if slot.lane_offset() >= lane_width {
        return Err(error(
            Fixed64PlacementErrorCode::InternalInvariant,
            "single-anchor lane width changed",
        ));
    }
    let offset =
        f64::from(u32::try_from(slot.lane_offset()).expect("fixed64 lane offsets fit u32"));
    let width = f64::from(u32::try_from(lane_width).expect("fixed64 lane widths fit u32"));
    let twist_angle_radians = 2.0 * core::f64::consts::PI * offset / width;
    let twist_quaternion = Quaternion::from_rotation_vector(
        geometry
            .alignment_target_direction
            .scale(twist_angle_radians),
    )
    .map_err(|_| {
        error(
            Fixed64PlacementErrorCode::InternalInvariant,
            "single-anchor twist quaternion failed",
        )
    })?;
    let quaternion = twist_quaternion.multiply(base_quaternion).map_err(|_| {
        error(
            Fixed64PlacementErrorCode::InternalInvariant,
            "single-anchor quaternion composition failed",
        )
    })?;
    let translation_angstrom =
        target_anchor_point_angstrom.minus(quaternion.rotate(geometry.ligand_anchor_point));
    let output_coordinates_angstrom = source
        .coordinates_angstrom()
        .iter()
        .map(|coordinate| quaternion.rotate(*coordinate).plus(translation_angstrom))
        .collect::<Vec<_>>();
    let output_coordinate_sha256 = native_fixed64_coordinate_sha256(&output_coordinates_angstrom)
        .map_err(|_| {
        error(
            Fixed64PlacementErrorCode::InternalInvariant,
            "single-anchor output coordinates are invalid",
        )
    })?;
    let geometric_metrics =
        evaluate_fixed64_geometric_metrics(&output_coordinates_angstrom, geometric_input).map_err(
            |_| {
                error(
                    Fixed64PlacementErrorCode::GeometricPrecheckFailed,
                    "single-anchor full Cartesian geometric precheck failed",
                )
            },
        )?;
    let steric_precheck_passed =
        geometric_metrics.minimum_vdw_ratio() >= HARD_REJECTION_MINIMUM_VDW_RATIO;
    let mut value = Fixed64SingleAnchorPlacement {
        allocation_receipt_sha256: allocation.receipt_sha256(),
        allocation_slot_receipt_sha256: slot.receipt_sha256(),
        slot_index,
        lane: slot.lane(),
        lane_offset: slot.lane_offset(),
        declared_anchor_kind,
        source,
        feature_inventory_receipt_sha256: feature_inventory.receipt_sha256(),
        selected_ligand_feature,
        selected_receptor_feature,
        geometric_input: geometric_input.clone(),
        ligand_anchor_point_angstrom: geometry.ligand_anchor_point,
        receptor_anchor_point_angstrom: geometry.receptor_anchor_point,
        target_anchor_point_angstrom,
        local_surface_normal: geometry.local_surface_normal,
        approach_vector: geometry.local_surface_normal.scale(-1.0),
        ligand_direction: geometry.ligand_direction,
        alignment_target_direction: geometry.alignment_target_direction,
        target_distance_angstrom,
        twist_angle_radians,
        quaternion,
        translation_angstrom,
        output_coordinates_angstrom,
        output_coordinate_sha256,
        geometric_metrics,
        steric_precheck_passed,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = single_anchor_sha256(&value);
    Ok(value)
}

#[derive(Clone, Copy)]
struct AnchorGeometry {
    ligand_anchor_point: Vec3,
    receptor_anchor_point: Vec3,
    ligand_direction: Vec3,
    local_surface_normal: Vec3,
    alignment_target_direction: Vec3,
}

fn derive_anchor_geometry(
    lane: Fixed64Lane,
    ligand_coordinates: &[Vec3],
    ligand_feature_coordinates: &[Vec3],
    receptor_feature_coordinates: &[Vec3],
    pocket_center: Vec3,
) -> Result<AnchorGeometry, Fixed64PlacementError> {
    let ligand_center = centroid(ligand_coordinates);
    let mut ligand_anchor_point = centroid(ligand_feature_coordinates);
    let mut receptor_anchor_point = centroid(receptor_feature_coordinates);
    let (ligand_direction, local_surface_normal, alignment_target_direction) = match lane {
        Fixed64Lane::LigandDonorToReceptorAcceptor => {
            ligand_anchor_point = ligand_feature_coordinates[0];
            let ligand_direction = normalized_direction(
                ligand_feature_coordinates[1].minus(ligand_feature_coordinates[0]),
                Fixed64PlacementErrorCode::DegenerateLigandDirection,
                "ligand donor-to-hydrogen direction is degenerate",
            )?;
            let local_surface_normal = normalized_direction(
                pocket_center.minus(receptor_anchor_point),
                Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                "receptor acceptor local surface normal is degenerate",
            )?;
            (
                ligand_direction,
                local_surface_normal,
                local_surface_normal.scale(-1.0),
            )
        }
        Fixed64Lane::LigandAcceptorToReceptorDonor => {
            let ligand_direction = normalized_direction(
                ligand_anchor_point.minus(ligand_center),
                Fixed64PlacementErrorCode::DegenerateLigandDirection,
                "ligand acceptor outward direction is degenerate",
            )?;
            receptor_anchor_point = receptor_feature_coordinates[0];
            let local_surface_normal = normalized_direction(
                receptor_feature_coordinates[1].minus(receptor_feature_coordinates[0]),
                Fixed64PlacementErrorCode::DegenerateReceptorDirection,
                "receptor donor-to-hydrogen direction is degenerate",
            )?;
            (
                ligand_direction,
                local_surface_normal,
                local_surface_normal.scale(-1.0),
            )
        }
        Fixed64Lane::ComplementaryCharge => {
            let ligand_direction = normalized_direction(
                ligand_anchor_point.minus(ligand_center),
                Fixed64PlacementErrorCode::DegenerateLigandDirection,
                "ligand charge-site outward direction is degenerate",
            )?;
            let local_surface_normal = normalized_direction(
                pocket_center.minus(receptor_anchor_point),
                Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                "receptor charge-site local surface normal is degenerate",
            )?;
            (
                ligand_direction,
                local_surface_normal,
                local_surface_normal.scale(-1.0),
            )
        }
        Fixed64Lane::AromaticPlane => {
            let ligand_direction = aromatic_normal(ligand_feature_coordinates)?;
            let mut receptor_plane_normal = aromatic_normal(receptor_feature_coordinates)?;
            let toward_pocket = normalized_direction(
                pocket_center.minus(receptor_anchor_point),
                Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                "receptor aromatic pocket-facing direction is degenerate",
            )?;
            let pocket_facing_cosine = receptor_plane_normal.dot(toward_pocket);
            if pocket_facing_cosine.abs() <= GEOMETRY_EPSILON {
                return Err(error(
                    Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                    "receptor aromatic normal is tangent to the pocket direction",
                ));
            }
            if pocket_facing_cosine < 0.0 {
                receptor_plane_normal = receptor_plane_normal.scale(-1.0);
            }
            let local_surface_normal = normalized_direction(
                receptor_plane_normal,
                Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                "receptor aromatic surface normal is degenerate",
            )?;
            (ligand_direction, local_surface_normal, local_surface_normal)
        }
        Fixed64Lane::PrincipalAxisShape => {
            let ligand_direction = principal_axis(ligand_feature_coordinates)?;
            let alignment_target_direction = principal_axis(receptor_feature_coordinates)?;
            let local_surface_normal = normalized_direction(
                pocket_center.minus(receptor_anchor_point),
                Fixed64PlacementErrorCode::DegenerateLocalSurfaceNormal,
                "pocket shape local surface normal is degenerate",
            )?;
            (
                ligand_direction,
                local_surface_normal,
                alignment_target_direction,
            )
        }
        _ => {
            return Err(error(
                Fixed64PlacementErrorCode::UnsupportedLane,
                "lane is not a single-anchor geometry lane",
            ))
        }
    };
    Ok(AnchorGeometry {
        ligand_anchor_point,
        receptor_anchor_point,
        ligand_direction,
        local_surface_normal,
        alignment_target_direction,
    })
}

fn validate_exact_system_source(
    allocation: &Fixed64Allocation,
    source: &Fixed64PlacementSource,
    geometric_input: &Fixed64GeometricInput,
) -> Result<(), Fixed64PlacementError> {
    let exact = allocation.inventory().exact_v11_source();
    if source.evidence() != exact.ligand_source() {
        return Err(error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "single-anchor ligand source is not exact V1.1 evidence",
        ));
    }
    let receptor_coordinate_sha256 = native_fixed64_coordinate_sha256(
        geometric_input.receptor_coordinates_angstrom(),
    )
    .map_err(|_| {
        error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "receptor coordinate identity is invalid",
        )
    })?;
    let ligand_vdw_radii_sha256 =
        native_fixed64_radii_sha256(geometric_input.ligand_vdw_radii_angstrom()).map_err(|_| {
            error(
                Fixed64PlacementErrorCode::SourceIdentityMismatch,
                "ligand vdW radius identity is invalid",
            )
        })?;
    let ligand_heavy_atom_mask_sha256 = native_fixed64_heavy_atom_mask_sha256(
        geometric_input.ligand_heavy_atom_mask(),
    )
    .map_err(|_| {
        error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "ligand heavy-atom mask identity is invalid",
        )
    })?;
    let receptor_vdw_radii_sha256 = native_fixed64_radii_sha256(
        geometric_input.receptor_vdw_radii_angstrom(),
    )
    .map_err(|_| {
        error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "receptor vdW radius identity is invalid",
        )
    })?;
    if receptor_coordinate_sha256 != exact.receptor_coordinate_sha256
        || ligand_vdw_radii_sha256 != exact.ligand_vdw_radii_sha256
        || ligand_heavy_atom_mask_sha256 != exact.ligand_heavy_atom_mask_sha256
        || receptor_vdw_radii_sha256 != exact.receptor_vdw_radii_sha256
    {
        return Err(error(
            Fixed64PlacementErrorCode::SourceIdentityMismatch,
            "single-anchor exact system geometry is cross-wired",
        ));
    }
    Ok(())
}

fn selected_feature<'a>(
    allocation: &Fixed64Allocation,
    inventory: &'a Fixed64FeatureGeometryInventory,
    receipt_sha256: [u8; 32],
) -> Result<&'a Fixed64FeatureGeometry, Fixed64PlacementError> {
    let feature = inventory
        .feature_for_allocation_receipt(receipt_sha256)
        .ok_or_else(|| {
            error(
                Fixed64PlacementErrorCode::FeatureCrossWired,
                "selected feature geometry is absent",
            )
        })?;
    if !allocation
        .inventory()
        .atomic_features()
        .iter()
        .any(|evidence| {
            evidence.receipt_sha256 == receipt_sha256 && evidence.kind == feature.kind()
        })
    {
        return Err(error(
            Fixed64PlacementErrorCode::FeatureCrossWired,
            "feature geometry disagrees with allocation evidence",
        ));
    }
    Ok(feature)
}

fn feature_coordinates(
    feature: &Fixed64FeatureGeometry,
    coordinates: &[Vec3],
) -> Result<Vec<Vec3>, Fixed64PlacementError> {
    feature
        .atom_indices()
        .iter()
        .map(|index| {
            coordinates.get(*index).copied().ok_or_else(|| {
                error(
                    Fixed64PlacementErrorCode::FeatureAtomIndexOutOfRange,
                    "feature atom index exceeds its coordinate denominator",
                )
            })
        })
        .collect()
}

const fn feature_pair_matches_lane(
    lane: Fixed64Lane,
    ligand: Fixed64FeatureKind,
    receptor: Fixed64FeatureKind,
) -> bool {
    matches!(
        (lane, ligand, receptor),
        (
            Fixed64Lane::LigandDonorToReceptorAcceptor,
            Fixed64FeatureKind::LigandDonor,
            Fixed64FeatureKind::ReceptorAcceptor
        ) | (
            Fixed64Lane::LigandAcceptorToReceptorDonor,
            Fixed64FeatureKind::LigandAcceptor,
            Fixed64FeatureKind::ReceptorDonor
        ) | (
            Fixed64Lane::ComplementaryCharge,
            Fixed64FeatureKind::LigandPositiveSite,
            Fixed64FeatureKind::ReceptorNegativeSite
        ) | (
            Fixed64Lane::ComplementaryCharge,
            Fixed64FeatureKind::LigandNegativeSite,
            Fixed64FeatureKind::ReceptorPositiveSite
        ) | (
            Fixed64Lane::AromaticPlane,
            Fixed64FeatureKind::LigandAromaticPlane,
            Fixed64FeatureKind::ReceptorAromaticPlane
        ) | (
            Fixed64Lane::PrincipalAxisShape,
            Fixed64FeatureKind::LigandShapeAxis,
            Fixed64FeatureKind::PocketShapeAxis
        )
    )
}

const fn is_anchor_lane(lane: Fixed64Lane) -> bool {
    matches!(
        lane,
        Fixed64Lane::LigandDonorToReceptorAcceptor
            | Fixed64Lane::LigandAcceptorToReceptorDonor
            | Fixed64Lane::ComplementaryCharge
            | Fixed64Lane::AromaticPlane
            | Fixed64Lane::PrincipalAxisShape
    )
}

const fn anchor_target_distance(kind: Fixed64AnchorKind) -> f64 {
    match kind {
        Fixed64AnchorKind::LigandDonorToReceptorAcceptor
        | Fixed64AnchorKind::LigandAcceptorToReceptorDonor => 2.9,
        Fixed64AnchorKind::ComplementaryCharge => 3.5,
        Fixed64AnchorKind::AromaticPlane => 3.8,
        Fixed64AnchorKind::PrincipalAxisShape => 3.0,
    }
}

const fn anchor_lane_width(lane: Fixed64Lane) -> usize {
    match lane {
        Fixed64Lane::LigandDonorToReceptorAcceptor
        | Fixed64Lane::LigandAcceptorToReceptorDonor
        | Fixed64Lane::ComplementaryCharge => 4,
        Fixed64Lane::AromaticPlane | Fixed64Lane::PrincipalAxisShape => 2,
        _ => 0,
    }
}

fn normalized_direction(
    value: Vec3,
    code: Fixed64PlacementErrorCode,
    message: &'static str,
) -> Result<Vec3, Fixed64PlacementError> {
    value
        .normalized("fixed64 placement direction")
        .map_err(|_| error(code, message))
}

fn canonical_direction(
    value: Vec3,
    code: Fixed64PlacementErrorCode,
    message: &'static str,
) -> Result<Vec3, Fixed64PlacementError> {
    let mut value = normalized_direction(value, code, message)?;
    for component in [value.x, value.y, value.z] {
        if component.abs() <= GEOMETRY_EPSILON {
            continue;
        }
        if component < 0.0 {
            value = value.scale(-1.0);
        }
        break;
    }
    Ok(value)
}

fn aromatic_normal(coordinates: &[Vec3]) -> Result<Vec3, Fixed64PlacementError> {
    let Some(first) = coordinates.first().copied() else {
        return Err(error(
            Fixed64PlacementErrorCode::DegenerateAromaticPlane,
            "aromatic plane is empty",
        ));
    };
    let Some((second_index, baseline)) = coordinates
        .iter()
        .copied()
        .enumerate()
        .skip(1)
        .map(|(index, coordinate)| (index, coordinate.minus(first)))
        .find(|(_, displacement)| displacement.norm() > GEOMETRY_EPSILON)
    else {
        return Err(error(
            Fixed64PlacementErrorCode::DegenerateAromaticPlane,
            "aromatic plane is collinear",
        ));
    };
    for (index, coordinate) in coordinates.iter().copied().enumerate().skip(1) {
        if index == second_index {
            continue;
        }
        let normal = baseline.cross(coordinate.minus(first));
        if normal.norm() > GEOMETRY_EPSILON {
            return canonical_direction(
                normal,
                Fixed64PlacementErrorCode::DegenerateAromaticPlane,
                "aromatic plane is degenerate",
            );
        }
    }
    Err(error(
        Fixed64PlacementErrorCode::DegenerateAromaticPlane,
        "aromatic plane is collinear",
    ))
}

fn principal_axis(coordinates: &[Vec3]) -> Result<Vec3, Fixed64PlacementError> {
    let center = centroid(coordinates);
    let centered = coordinates
        .iter()
        .map(|coordinate| coordinate.minus(center))
        .collect::<Vec<_>>();
    let mut covariance = [[0.0; 3]; 3];
    for point in &centered {
        let components = [point.x, point.y, point.z];
        for left in 0..3 {
            for right in 0..3 {
                covariance[left][right] += components[left] * components[right];
            }
        }
    }
    if (0..3)
        .map(|index| covariance[index][index])
        .fold(0.0_f64, f64::max)
        <= GEOMETRY_EPSILON
    {
        return Err(error(
            Fixed64PlacementErrorCode::DegeneratePrincipalAxis,
            "principal-axis variance is zero",
        ));
    }
    let mut matrix = covariance;
    let mut eigenvectors = [[0.0; 3]; 3];
    for (index, row) in eigenvectors.iter_mut().enumerate() {
        row[index] = 1.0;
    }
    let pairs = [(0, 1), (0, 2), (1, 2)];
    for _ in 0..64 {
        let mut selected = pairs[0];
        let mut selected_value = matrix[selected.0][selected.1].abs();
        for pair in &pairs[1..] {
            let value = matrix[pair.0][pair.1].abs();
            if value > selected_value {
                selected = *pair;
                selected_value = value;
            }
        }
        let scale = (0..3)
            .map(|index| matrix[index][index].abs())
            .fold(0.0_f64, f64::max);
        if selected_value <= GEOMETRY_EPSILON * scale {
            break;
        }
        let (first, second) = selected;
        let angle = 0.5
            * libm::atan2(
                2.0 * matrix[first][second],
                matrix[second][second] - matrix[first][first],
            );
        let cosine = libm::cos(angle);
        let sine = libm::sin(angle);
        let mut rotation = [[0.0; 3]; 3];
        for (index, row) in rotation.iter_mut().enumerate() {
            row[index] = 1.0;
        }
        rotation[first][first] = cosine;
        rotation[second][second] = cosine;
        rotation[first][second] = sine;
        rotation[second][first] = -sine;
        let mut right_product = [[0.0; 3]; 3];
        for row in 0..3 {
            for column in 0..3 {
                right_product[row][column] = (0..3)
                    .map(|inner| matrix[row][inner] * rotation[inner][column])
                    .sum();
            }
        }
        let mut next_matrix = [[0.0; 3]; 3];
        for row in 0..3 {
            for column in 0..3 {
                next_matrix[row][column] = (0..3)
                    .map(|inner| rotation[inner][row] * right_product[inner][column])
                    .sum();
            }
        }
        matrix = next_matrix;
        let mut next_eigenvectors = [[0.0; 3]; 3];
        for row in 0..3 {
            for column in 0..3 {
                next_eigenvectors[row][column] = (0..3)
                    .map(|inner| eigenvectors[row][inner] * rotation[inner][column])
                    .sum();
            }
        }
        eigenvectors = next_eigenvectors;
    }
    let mut dominant_index = 0;
    for index in 1..3 {
        if matrix[index][index] > matrix[dominant_index][dominant_index] {
            dominant_index = index;
        }
    }
    let vector = normalized_direction(
        Vec3::new(
            eigenvectors[0][dominant_index],
            eigenvectors[1][dominant_index],
            eigenvectors[2][dominant_index],
        ),
        Fixed64PlacementErrorCode::DegeneratePrincipalAxis,
        "principal-axis eigenvector is degenerate",
    )?;
    let transformed = Vec3::new(
        covariance[0][0] * vector.x + covariance[0][1] * vector.y + covariance[0][2] * vector.z,
        covariance[1][0] * vector.x + covariance[1][1] * vector.y + covariance[1][2] * vector.z,
        covariance[2][0] * vector.x + covariance[2][1] * vector.y + covariance[2][2] * vector.z,
    );
    let rayleigh = vector.dot(transformed);
    let residual = transformed.minus(vector.scale(rayleigh)).norm();
    if residual > GEOMETRY_EPSILON * GEOMETRY_EPSILON.max(rayleigh.abs()) {
        return Err(error(
            Fixed64PlacementErrorCode::DegeneratePrincipalAxis,
            "principal-axis solver did not converge",
        ));
    }
    canonical_direction(
        vector,
        Fixed64PlacementErrorCode::DegeneratePrincipalAxis,
        "principal-axis direction is degenerate",
    )
}

fn single_anchor_sha256(value: &Fixed64SingleAnchorPlacement) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_single_anchor/native-v1");
    hash.string(NATIVE_FIXED64_SINGLE_ANCHOR_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID);
    hash.digest(value.allocation_receipt_sha256);
    hash.digest(value.allocation_slot_receipt_sha256);
    hash.usize(value.slot_index);
    hash.string(value.lane.id());
    hash.usize(value.lane_offset);
    hash.byte(anchor_kind_tag(value.declared_anchor_kind));
    hash.digest(value.source.receipt_sha256());
    hash.digest(value.feature_inventory_receipt_sha256);
    hash.digest(value.selected_ligand_feature.receipt_sha256());
    hash.digest(value.selected_receptor_feature.receipt_sha256());
    hash.digest(value.geometric_input.receipt_sha256());
    hash.vec3(value.ligand_anchor_point_angstrom);
    hash.vec3(value.receptor_anchor_point_angstrom);
    hash.vec3(value.target_anchor_point_angstrom);
    hash.vec3(value.local_surface_normal);
    hash.vec3(value.approach_vector);
    hash.vec3(value.ligand_direction);
    hash.vec3(value.alignment_target_direction);
    hash.f64(value.target_distance_angstrom);
    hash.f64(value.twist_angle_radians);
    hash.f64(value.quaternion.x);
    hash.f64(value.quaternion.y);
    hash.f64(value.quaternion.z);
    hash.f64(value.quaternion.w);
    hash.vec3(value.translation_angstrom);
    hash.digest(value.output_coordinate_sha256);
    hash.digest(value.geometric_metrics.receipt_sha256());
    hash.f64(HARD_REJECTION_MINIMUM_VDW_RATIO);
    hash.bool(value.steric_precheck_passed);
    hash.usize(1);
    hash.bool(false);
    hash.bool(false);
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

const fn anchor_kind_tag(kind: Fixed64AnchorKind) -> u8 {
    match kind {
        Fixed64AnchorKind::LigandDonorToReceptorAcceptor => 0,
        Fixed64AnchorKind::LigandAcceptorToReceptorDonor => 1,
        Fixed64AnchorKind::ComplementaryCharge => 2,
        Fixed64AnchorKind::AromaticPlane => 3,
        Fixed64AnchorKind::PrincipalAxisShape => 4,
    }
}

const fn error(code: Fixed64PlacementErrorCode, message: &'static str) -> Fixed64PlacementError {
    Fixed64PlacementError::new(code, message)
}
