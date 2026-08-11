use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{Fixed64Allocation, Fixed64Lane, Fixed64MissingFeature, Vec3, FIXED64_CANDIDATE_COUNT};

pub const NATIVE_FIXED64_GEOMETRIC_INPUT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_geometric_admission_native_inputs/1.0.0";
pub const NATIVE_FIXED64_GEOMETRIC_METRICS_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_geometric_admission_native_metrics/1.0.0";
pub const NATIVE_FIXED64_GEOMETRIC_DECISION_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_geometric_admission_native_decision/1.0.0";
pub const NATIVE_FIXED64_GEOMETRIC_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_geometric_admission_native_batch/1.0.0";
pub const HARD_REJECTION_MINIMUM_VDW_RATIO: f64 = 0.55;
pub const FIXED64_MAX_LIGAND_ATOMS: usize = 512;
pub const FIXED64_MAX_RECEPTOR_ATOMS: usize = 4_096;
pub const FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS: usize = 16_777_216;
pub const FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 100_000.0;
pub const FIXED64_MIN_VDW_RADIUS_ANGSTROM: f64 = 0.1;
pub const FIXED64_MAX_VDW_RADIUS_ANGSTROM: f64 = 10.0;
pub const FIXED64_MAX_POCKET_RADIUS_ANGSTROM: f64 = 1_000.0;

const PAIR_TRAVERSAL_ID: &str = "full_cartesian_ligand_index_major_receptor_index_minor";
const SPHERE_OVERLAP_ID: &str = "sum_of_pairwise_vdw_sphere_intersection_volumes_angstrom3";
const POCKET_ESCAPE_ID: &str =
    "max_zero_or_ligand_center_distance_plus_vdw_radius_minus_pocket_radius";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64GeometricErrorCode {
    InvalidInput,
    AllocationCrossWired,
    PairBudgetExceeded,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixed64GeometricError {
    code: Fixed64GeometricErrorCode,
    message: &'static str,
}

impl Fixed64GeometricError {
    const fn new(code: Fixed64GeometricErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> Fixed64GeometricErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for Fixed64GeometricError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "native fixed64 geometric admission: {}",
            self.message
        )
    }
}

impl std::error::Error for Fixed64GeometricError {}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64GeometricInput {
    ligand_vdw_radii_angstrom: Vec<f64>,
    ligand_heavy_atom_mask: Vec<bool>,
    receptor_coordinates_angstrom: Vec<Vec3>,
    receptor_vdw_radii_angstrom: Vec<f64>,
    pocket_center_angstrom: Vec3,
    pocket_radius_angstrom: f64,
    receipt_sha256: [u8; 32],
}

impl Fixed64GeometricInput {
    pub fn new(
        ligand_vdw_radii_angstrom: Vec<f64>,
        ligand_heavy_atom_mask: Vec<bool>,
        receptor_coordinates_angstrom: Vec<Vec3>,
        receptor_vdw_radii_angstrom: Vec<f64>,
        pocket_center_angstrom: Vec3,
        pocket_radius_angstrom: f64,
    ) -> Result<Self, Fixed64GeometricError> {
        validate_radii(&ligand_vdw_radii_angstrom, FIXED64_MAX_LIGAND_ATOMS)?;
        if ligand_heavy_atom_mask.len() != ligand_vdw_radii_angstrom.len() {
            return Err(invalid("ligand heavy-atom mask denominator changed"));
        }
        validate_coordinates(&receptor_coordinates_angstrom, FIXED64_MAX_RECEPTOR_ATOMS)?;
        validate_radii(&receptor_vdw_radii_angstrom, FIXED64_MAX_RECEPTOR_ATOMS)?;
        if receptor_coordinates_angstrom.len() != receptor_vdw_radii_angstrom.len() {
            return Err(invalid(
                "receptor coordinate and radius denominators disagree",
            ));
        }
        validate_vec3(pocket_center_angstrom)?;
        if !pocket_radius_angstrom.is_finite()
            || !(0.0..=FIXED64_MAX_POCKET_RADIUS_ANGSTROM).contains(&pocket_radius_angstrom)
            || pocket_radius_angstrom == 0.0
        {
            return Err(invalid("pocket radius is outside its safety envelope"));
        }
        let mut value = Self {
            ligand_vdw_radii_angstrom,
            ligand_heavy_atom_mask,
            receptor_coordinates_angstrom,
            receptor_vdw_radii_angstrom,
            pocket_center_angstrom,
            pocket_radius_angstrom,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = geometric_input_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub fn ligand_vdw_radii_angstrom(&self) -> &[f64] {
        &self.ligand_vdw_radii_angstrom
    }

    #[must_use]
    pub fn ligand_heavy_atom_mask(&self) -> &[bool] {
        &self.ligand_heavy_atom_mask
    }

    #[must_use]
    pub fn receptor_coordinates_angstrom(&self) -> &[Vec3] {
        &self.receptor_coordinates_angstrom
    }

    #[must_use]
    pub fn receptor_vdw_radii_angstrom(&self) -> &[f64] {
        &self.receptor_vdw_radii_angstrom
    }

    #[must_use]
    pub const fn pocket_center_angstrom(&self) -> Vec3 {
        self.pocket_center_angstrom
    }

    #[must_use]
    pub const fn pocket_radius_angstrom(&self) -> f64 {
        self.pocket_radius_angstrom
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        validate_radii(&self.ligand_vdw_radii_angstrom, FIXED64_MAX_LIGAND_ATOMS).is_ok()
            && self.ligand_heavy_atom_mask.len() == self.ligand_vdw_radii_angstrom.len()
            && validate_coordinates(
                &self.receptor_coordinates_angstrom,
                FIXED64_MAX_RECEPTOR_ATOMS,
            )
            .is_ok()
            && validate_radii(
                &self.receptor_vdw_radii_angstrom,
                FIXED64_MAX_RECEPTOR_ATOMS,
            )
            .is_ok()
            && self.receptor_coordinates_angstrom.len() == self.receptor_vdw_radii_angstrom.len()
            && validate_vec3(self.pocket_center_angstrom).is_ok()
            && self.pocket_radius_angstrom.is_finite()
            && self.pocket_radius_angstrom > 0.0
            && self.pocket_radius_angstrom <= FIXED64_MAX_POCKET_RADIUS_ANGSTROM
            && geometric_input_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64GeometricMetrics {
    ligand_atom_count: usize,
    receptor_atom_count: usize,
    exact_pair_count: usize,
    raw_minimum_distance_angstrom: f64,
    minimum_vdw_surface_gap_angstrom: f64,
    minimum_vdw_ratio: f64,
    penetration_pair_count: usize,
    unique_ligand_penetration_atom_count: usize,
    unique_ligand_heavy_atom_penetration_count: usize,
    sphere_overlap_proxy_angstrom3: f64,
    pocket_escape_angstrom: f64,
    receipt_sha256: [u8; 32],
}

impl Fixed64GeometricMetrics {
    #[must_use]
    pub const fn ligand_atom_count(&self) -> usize {
        self.ligand_atom_count
    }

    #[must_use]
    pub const fn receptor_atom_count(&self) -> usize {
        self.receptor_atom_count
    }

    #[must_use]
    pub const fn exact_pair_count(&self) -> usize {
        self.exact_pair_count
    }

    #[must_use]
    pub const fn raw_minimum_distance_angstrom(&self) -> f64 {
        self.raw_minimum_distance_angstrom
    }

    #[must_use]
    pub const fn minimum_vdw_surface_gap_angstrom(&self) -> f64 {
        self.minimum_vdw_surface_gap_angstrom
    }

    #[must_use]
    pub const fn minimum_vdw_ratio(&self) -> f64 {
        self.minimum_vdw_ratio
    }

    #[must_use]
    pub const fn penetration_pair_count(&self) -> usize {
        self.penetration_pair_count
    }

    #[must_use]
    pub const fn unique_ligand_penetration_atom_count(&self) -> usize {
        self.unique_ligand_penetration_atom_count
    }

    #[must_use]
    pub const fn unique_ligand_heavy_atom_penetration_count(&self) -> usize {
        self.unique_ligand_heavy_atom_penetration_count
    }

    #[must_use]
    pub const fn sphere_overlap_proxy_angstrom3(&self) -> f64 {
        self.sphere_overlap_proxy_angstrom3
    }

    #[must_use]
    pub const fn pocket_escape_angstrom(&self) -> f64 {
        self.pocket_escape_angstrom
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        metrics_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fixed64GeometricStatus {
    Accepted,
    SeverePenetrationRejected,
    TypedGenerationFailure,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64GeometricDecision {
    slot_index: usize,
    allocation_slot_receipt_sha256: [u8; 32],
    lane: Fixed64Lane,
    allocation_generation_eligible: bool,
    allocation_missing_features: Vec<Fixed64MissingFeature>,
    candidate_coordinate_sha256: Option<[u8; 32]>,
    metrics: Option<Fixed64GeometricMetrics>,
    status: Fixed64GeometricStatus,
    rank_eligible: bool,
    receipt_sha256: [u8; 32],
}

impl Fixed64GeometricDecision {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn lane(&self) -> Fixed64Lane {
        self.lane
    }

    #[must_use]
    pub const fn allocation_generation_eligible(&self) -> bool {
        self.allocation_generation_eligible
    }

    #[must_use]
    pub fn allocation_missing_features(&self) -> &[Fixed64MissingFeature] {
        &self.allocation_missing_features
    }

    #[must_use]
    pub const fn candidate_coordinate_sha256(&self) -> Option<[u8; 32]> {
        self.candidate_coordinate_sha256
    }

    #[must_use]
    pub const fn metrics(&self) -> Option<&Fixed64GeometricMetrics> {
        self.metrics.as_ref()
    }

    #[must_use]
    pub const fn status(&self) -> Fixed64GeometricStatus {
        self.status
    }

    #[must_use]
    pub const fn rank_eligible(&self) -> bool {
        self.rank_eligible
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.metrics
            .as_ref()
            .is_none_or(Fixed64GeometricMetrics::has_valid_receipt)
            && decision_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Fixed64GeometricBatch {
    allocation: Fixed64Allocation,
    input: Fixed64GeometricInput,
    candidate_coordinates_angstrom: [Option<Vec<Vec3>>; FIXED64_CANDIDATE_COUNT],
    exact_input_sha256: [u8; 32],
    decisions: [Fixed64GeometricDecision; FIXED64_CANDIDATE_COUNT],
    receipt_sha256: [u8; 32],
}

impl Fixed64GeometricBatch {
    pub fn evaluate(
        allocation: &Fixed64Allocation,
        input: Fixed64GeometricInput,
        candidate_coordinates_angstrom: [Option<Vec<Vec3>>; FIXED64_CANDIDATE_COUNT],
    ) -> Result<Self, Fixed64GeometricError> {
        if !allocation.has_valid_receipt() || !input.has_valid_receipt() {
            return Err(cross_wired(
                "allocation or geometric input receipt is invalid",
            ));
        }
        let ready_count = candidate_coordinates_angstrom
            .iter()
            .filter(|candidate| candidate.is_some())
            .count();
        let exact_pair_evaluations = ready_count
            .checked_mul(input.ligand_vdw_radii_angstrom.len())
            .and_then(|value| value.checked_mul(input.receptor_coordinates_angstrom.len()))
            .ok_or_else(|| pair_budget("fixed64 exact pair work overflowed"))?;
        if exact_pair_evaluations > FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS {
            return Err(pair_budget(
                "fixed64 exact pair work exceeds its frozen cap",
            ));
        }

        let mut decisions = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
        for (slot, coordinates) in allocation
            .slots()
            .iter()
            .zip(&candidate_coordinates_angstrom)
        {
            if slot.generation_eligible() != coordinates.is_some() {
                return Err(cross_wired(
                    "candidate presence disagrees with allocation generation eligibility",
                ));
            }
            decisions.push(build_decision(slot, coordinates.as_deref(), &input)?);
        }
        let decisions: [Fixed64GeometricDecision; FIXED64_CANDIDATE_COUNT] =
            decisions
                .try_into()
                .map_err(|_| internal("geometric decision denominator changed"))?;
        let exact_input_sha256 = exact_input_sha256(
            allocation,
            &input,
            &candidate_coordinates_angstrom,
            exact_pair_evaluations,
        );
        let receipt_sha256 = batch_sha256(allocation, exact_input_sha256, &decisions);
        Ok(Self {
            allocation: allocation.clone(),
            input,
            candidate_coordinates_angstrom,
            exact_input_sha256,
            decisions,
            receipt_sha256,
        })
    }

    #[must_use]
    pub fn allocation(&self) -> &Fixed64Allocation {
        &self.allocation
    }

    #[must_use]
    pub fn input(&self) -> &Fixed64GeometricInput {
        &self.input
    }

    #[must_use]
    pub fn candidate_coordinates_angstrom(&self, slot_index: usize) -> Option<&[Vec3]> {
        self.candidate_coordinates_angstrom
            .get(slot_index)
            .and_then(Option::as_deref)
    }

    #[must_use]
    pub fn decisions(&self) -> &[Fixed64GeometricDecision; FIXED64_CANDIDATE_COUNT] {
        &self.decisions
    }

    #[must_use]
    pub const fn exact_input_sha256(&self) -> [u8; 32] {
        self.exact_input_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn accepted_count(&self) -> usize {
        self.decisions
            .iter()
            .filter(|decision| decision.status == Fixed64GeometricStatus::Accepted)
            .count()
    }

    #[must_use]
    pub fn geometric_rejected_count(&self) -> usize {
        self.decisions
            .iter()
            .filter(|decision| decision.status == Fixed64GeometricStatus::SeverePenetrationRejected)
            .count()
    }

    #[must_use]
    pub fn typed_generation_failure_count(&self) -> usize {
        self.decisions
            .iter()
            .filter(|decision| decision.status == Fixed64GeometricStatus::TypedGenerationFailure)
            .count()
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn production_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        if !self.allocation.has_valid_receipt() || !self.input.has_valid_receipt() {
            return false;
        }
        let exact_pair_evaluations = self
            .candidate_coordinates_angstrom
            .iter()
            .filter(|candidate| candidate.is_some())
            .count()
            .checked_mul(self.input.ligand_vdw_radii_angstrom.len())
            .and_then(|value| value.checked_mul(self.input.receptor_coordinates_angstrom.len()));
        let Some(exact_pair_evaluations) = exact_pair_evaluations else {
            return false;
        };
        if exact_pair_evaluations > FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS
            || exact_input_sha256(
                &self.allocation,
                &self.input,
                &self.candidate_coordinates_angstrom,
                exact_pair_evaluations,
            ) != self.exact_input_sha256
            || batch_sha256(&self.allocation, self.exact_input_sha256, &self.decisions)
                != self.receipt_sha256
        {
            return false;
        }
        self.allocation
            .slots()
            .iter()
            .zip(&self.candidate_coordinates_angstrom)
            .zip(&self.decisions)
            .all(|((slot, coordinates), observed)| {
                slot.generation_eligible() == coordinates.is_some()
                    && build_decision(slot, coordinates.as_deref(), &self.input)
                        .is_ok_and(|expected| expected == *observed)
            })
    }
}

pub fn native_fixed64_coordinate_sha256(
    coordinates_angstrom: &[Vec3],
) -> Result<[u8; 32], Fixed64GeometricError> {
    validate_coordinates(coordinates_angstrom, FIXED64_MAX_RECEPTOR_ATOMS)?;
    Ok(coordinate_sha256_unchecked(coordinates_angstrom))
}

pub fn evaluate_fixed64_geometric_metrics(
    candidate_coordinates_angstrom: &[Vec3],
    input: &Fixed64GeometricInput,
) -> Result<Fixed64GeometricMetrics, Fixed64GeometricError> {
    if !input.has_valid_receipt() {
        return Err(cross_wired("geometric input receipt is invalid"));
    }
    validate_coordinates(candidate_coordinates_angstrom, FIXED64_MAX_LIGAND_ATOMS)?;
    if candidate_coordinates_angstrom.len() != input.ligand_vdw_radii_angstrom.len() {
        return Err(invalid("candidate ligand atom denominator changed"));
    }
    let exact_pair_count = candidate_coordinates_angstrom
        .len()
        .checked_mul(input.receptor_coordinates_angstrom.len())
        .ok_or_else(|| pair_budget("candidate exact pair count overflowed"))?;

    let mut raw_minimum_distance_angstrom = f64::INFINITY;
    let mut minimum_vdw_surface_gap_angstrom = f64::INFINITY;
    let mut minimum_vdw_ratio = f64::INFINITY;
    let mut penetration_pair_count = 0_usize;
    let mut unique_ligand_penetration_atom_count = 0_usize;
    let mut unique_ligand_heavy_atom_penetration_count = 0_usize;
    let mut sphere_overlap_proxy_angstrom3 = 0.0;
    let mut pocket_escape_angstrom: f64 = 0.0;

    for (ligand_index, (coordinate, ligand_radius)) in candidate_coordinates_angstrom
        .iter()
        .zip(&input.ligand_vdw_radii_angstrom)
        .enumerate()
    {
        let mut ligand_atom_penetrates = false;
        for (receptor_coordinate, receptor_radius) in input
            .receptor_coordinates_angstrom
            .iter()
            .zip(&input.receptor_vdw_radii_angstrom)
        {
            let distance = coordinate.minus(*receptor_coordinate).norm();
            let radius_sum = ligand_radius + receptor_radius;
            raw_minimum_distance_angstrom = raw_minimum_distance_angstrom.min(distance);
            minimum_vdw_surface_gap_angstrom =
                minimum_vdw_surface_gap_angstrom.min(distance - radius_sum);
            minimum_vdw_ratio = minimum_vdw_ratio.min(distance / radius_sum);
            if distance < radius_sum {
                penetration_pair_count += 1;
                ligand_atom_penetrates = true;
                sphere_overlap_proxy_angstrom3 +=
                    sphere_intersection_volume(*ligand_radius, *receptor_radius, distance)?;
            }
        }
        if ligand_atom_penetrates {
            unique_ligand_penetration_atom_count += 1;
            if input.ligand_heavy_atom_mask[ligand_index] {
                unique_ligand_heavy_atom_penetration_count += 1;
            }
        }
        let escape = coordinate.minus(input.pocket_center_angstrom).norm() + ligand_radius
            - input.pocket_radius_angstrom;
        pocket_escape_angstrom = pocket_escape_angstrom.max(escape.max(0.0));
    }
    if !raw_minimum_distance_angstrom.is_finite()
        || !minimum_vdw_surface_gap_angstrom.is_finite()
        || !minimum_vdw_ratio.is_finite()
        || !sphere_overlap_proxy_angstrom3.is_finite()
        || !pocket_escape_angstrom.is_finite()
    {
        return Err(internal("derived geometric metrics are non-finite"));
    }
    let mut metrics = Fixed64GeometricMetrics {
        ligand_atom_count: candidate_coordinates_angstrom.len(),
        receptor_atom_count: input.receptor_coordinates_angstrom.len(),
        exact_pair_count,
        raw_minimum_distance_angstrom,
        minimum_vdw_surface_gap_angstrom,
        minimum_vdw_ratio,
        penetration_pair_count,
        unique_ligand_penetration_atom_count,
        unique_ligand_heavy_atom_penetration_count,
        sphere_overlap_proxy_angstrom3,
        pocket_escape_angstrom,
        receipt_sha256: [0; 32],
    };
    metrics.receipt_sha256 = metrics_sha256(&metrics);
    Ok(metrics)
}

fn build_decision(
    slot: &crate::Fixed64Slot,
    coordinates: Option<&[Vec3]>,
    input: &Fixed64GeometricInput,
) -> Result<Fixed64GeometricDecision, Fixed64GeometricError> {
    let (candidate_coordinate_sha256, metrics, status, rank_eligible) = if slot
        .generation_eligible()
    {
        let coordinates = coordinates
            .ok_or_else(|| cross_wired("generation-eligible slot lacks candidate coordinates"))?;
        let coordinate_sha256 = native_fixed64_coordinate_sha256(coordinates)?;
        let metrics = evaluate_fixed64_geometric_metrics(coordinates, input)?;
        let rank_eligible = metrics.minimum_vdw_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO;
        let status = if rank_eligible {
            Fixed64GeometricStatus::Accepted
        } else {
            Fixed64GeometricStatus::SeverePenetrationRejected
        };
        (
            Some(coordinate_sha256),
            Some(metrics),
            status,
            rank_eligible,
        )
    } else {
        if coordinates.is_some() {
            return Err(cross_wired(
                "generation-failed slot fabricated candidate coordinates",
            ));
        }
        (
            None,
            None,
            Fixed64GeometricStatus::TypedGenerationFailure,
            false,
        )
    };
    let mut decision = Fixed64GeometricDecision {
        slot_index: slot.slot_index(),
        allocation_slot_receipt_sha256: slot.receipt_sha256(),
        lane: slot.lane(),
        allocation_generation_eligible: slot.generation_eligible(),
        allocation_missing_features: slot.missing_features().to_vec(),
        candidate_coordinate_sha256,
        metrics,
        status,
        rank_eligible,
        receipt_sha256: [0; 32],
    };
    decision.receipt_sha256 = decision_sha256(&decision);
    Ok(decision)
}

fn validate_vec3(value: Vec3) -> Result<(), Fixed64GeometricError> {
    if !value.is_finite()
        || value.x.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || value.y.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || value.z.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
    {
        return Err(invalid("coordinate is outside its finite safety envelope"));
    }
    Ok(())
}

fn validate_coordinates(values: &[Vec3], maximum: usize) -> Result<(), Fixed64GeometricError> {
    if values.is_empty() || values.len() > maximum {
        return Err(invalid(
            "coordinate denominator is outside its frozen bounds",
        ));
    }
    values.iter().try_for_each(|value| validate_vec3(*value))
}

fn validate_radii(values: &[f64], maximum: usize) -> Result<(), Fixed64GeometricError> {
    if values.is_empty()
        || values.len() > maximum
        || values.iter().any(|value| {
            !value.is_finite()
                || !(FIXED64_MIN_VDW_RADIUS_ANGSTROM..=FIXED64_MAX_VDW_RADIUS_ANGSTROM)
                    .contains(value)
        })
    {
        return Err(invalid("vdW radii are outside their frozen bounds"));
    }
    Ok(())
}

fn sphere_intersection_volume(
    left_radius: f64,
    right_radius: f64,
    center_distance: f64,
) -> Result<f64, Fixed64GeometricError> {
    let radius_sum = left_radius + right_radius;
    if center_distance >= radius_sum {
        return Ok(0.0);
    }
    let radius_difference = (left_radius - right_radius).abs();
    let volume = if center_distance <= radius_difference {
        let radius = left_radius.min(right_radius);
        (4.0 / 3.0) * core::f64::consts::PI * radius.powi(3)
    } else {
        let numerator = core::f64::consts::PI
            * (radius_sum - center_distance).powi(2)
            * (center_distance.powi(2) + 2.0 * center_distance * radius_sum
                - 3.0 * radius_difference.powi(2));
        numerator / (12.0 * center_distance)
    };
    if !volume.is_finite() {
        return Err(internal("sphere overlap proxy is non-finite"));
    }
    Ok(volume.max(0.0))
}

fn coordinate_sha256_unchecked(values: &[Vec3]) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_coordinates/native-v1");
    hash.usize(values.len());
    for value in values {
        hash.vec3(*value);
    }
    hash.finish()
}

fn geometric_input_sha256(input: &Fixed64GeometricInput) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_geometric_input/native-v1");
    hash.string(NATIVE_FIXED64_GEOMETRIC_INPUT_SCHEMA_ID);
    hash.usize(input.ligand_vdw_radii_angstrom.len());
    for radius in &input.ligand_vdw_radii_angstrom {
        hash.f64(*radius);
    }
    for heavy in &input.ligand_heavy_atom_mask {
        hash.bool(*heavy);
    }
    hash.usize(input.receptor_coordinates_angstrom.len());
    for (coordinate, radius) in input
        .receptor_coordinates_angstrom
        .iter()
        .zip(&input.receptor_vdw_radii_angstrom)
    {
        hash.vec3(*coordinate);
        hash.f64(*radius);
    }
    hash.vec3(input.pocket_center_angstrom);
    hash.f64(input.pocket_radius_angstrom);
    hash.string(POCKET_ESCAPE_ID);
    hash.finish()
}

fn metrics_sha256(metrics: &Fixed64GeometricMetrics) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_geometric_metrics/native-v1");
    hash.string(NATIVE_FIXED64_GEOMETRIC_METRICS_SCHEMA_ID);
    hash.usize(metrics.ligand_atom_count);
    hash.usize(metrics.receptor_atom_count);
    hash.usize(metrics.exact_pair_count);
    hash.string(PAIR_TRAVERSAL_ID);
    hash.f64(metrics.raw_minimum_distance_angstrom);
    hash.f64(metrics.minimum_vdw_surface_gap_angstrom);
    hash.f64(metrics.minimum_vdw_ratio);
    hash.usize(metrics.penetration_pair_count);
    hash.usize(metrics.unique_ligand_penetration_atom_count);
    hash.usize(metrics.unique_ligand_heavy_atom_penetration_count);
    hash.f64(metrics.sphere_overlap_proxy_angstrom3);
    hash.string(SPHERE_OVERLAP_ID);
    hash.f64(metrics.pocket_escape_angstrom);
    hash.string(POCKET_ESCAPE_ID);
    hash.finish()
}

fn decision_sha256(decision: &Fixed64GeometricDecision) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_geometric_decision/native-v1");
    hash.string(NATIVE_FIXED64_GEOMETRIC_DECISION_SCHEMA_ID);
    hash.usize(decision.slot_index);
    hash.digest(decision.allocation_slot_receipt_sha256);
    hash.string(decision.lane.id());
    hash.bool(decision.allocation_generation_eligible);
    hash.usize(decision.allocation_missing_features.len());
    for value in &decision.allocation_missing_features {
        missing_feature(&mut hash, *value);
    }
    hash.option(decision.candidate_coordinate_sha256, |hash, value| {
        hash.digest(value)
    });
    hash.option(decision.metrics.as_ref(), |hash, value| {
        hash.digest(value.receipt_sha256)
    });
    hash.byte(match decision.status {
        Fixed64GeometricStatus::Accepted => 0,
        Fixed64GeometricStatus::SeverePenetrationRejected => 1,
        Fixed64GeometricStatus::TypedGenerationFailure => 2,
    });
    hash.bool(decision.rank_eligible);
    hash.bool(true);
    hash.finish()
}

fn exact_input_sha256(
    allocation: &Fixed64Allocation,
    input: &Fixed64GeometricInput,
    candidates: &[Option<Vec<Vec3>>; FIXED64_CANDIDATE_COUNT],
    exact_pair_evaluations: usize,
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_geometric_exact_inputs/native-v1");
    hash.digest(allocation.receipt_sha256());
    hash.digest(input.receipt_sha256);
    hash.usize(candidates.len());
    for (slot, candidate) in allocation.slots().iter().zip(candidates) {
        hash.digest(slot.receipt_sha256());
        hash.option(candidate.as_deref(), |hash, values| {
            hash.digest(coordinate_sha256_unchecked(values));
        });
    }
    hash.usize(exact_pair_evaluations);
    hash.usize(FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS);
    hash.finish()
}

fn batch_sha256(
    allocation: &Fixed64Allocation,
    exact_input_sha256: [u8; 32],
    decisions: &[Fixed64GeometricDecision; FIXED64_CANDIDATE_COUNT],
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.fixed64_geometric_batch/native-v1");
    hash.string(NATIVE_FIXED64_GEOMETRIC_BATCH_SCHEMA_ID);
    hash.digest(allocation.receipt_sha256());
    hash.digest(exact_input_sha256);
    hash.usize(decisions.len());
    for decision in decisions {
        hash.digest(decision.receipt_sha256);
    }
    hash.bool(true);
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
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

const fn invalid(message: &'static str) -> Fixed64GeometricError {
    Fixed64GeometricError::new(Fixed64GeometricErrorCode::InvalidInput, message)
}

const fn cross_wired(message: &'static str) -> Fixed64GeometricError {
    Fixed64GeometricError::new(Fixed64GeometricErrorCode::AllocationCrossWired, message)
}

const fn pair_budget(message: &'static str) -> Fixed64GeometricError {
    Fixed64GeometricError::new(Fixed64GeometricErrorCode::PairBudgetExceeded, message)
}

const fn internal(message: &'static str) -> Fixed64GeometricError {
    Fixed64GeometricError::new(Fixed64GeometricErrorCode::InternalInvariant, message)
}
