use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    native_fixed64_coordinate_sha256, Fixed64ProposalPlacement, NativeScorerV1Backend,
    NativeScorerV1Batch, NativeScorerV1Context, NativeScorerV1FailureCode, NativeScorerV1RowStatus,
    Quaternion, Vec3, FIXED64_CANDIDATE_COUNT, FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM,
    FIXED64_MAX_LIGAND_ATOMS, FIXED64_MAX_RECEPTOR_ATOMS,
};

pub const NATIVE_FIXED64_VALIDITY_CONFIG_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pose_validity_config/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_CONTEXT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pose_validity_context/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_RESULT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pose_validity_result/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_FAILURE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pose_validity_failure/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_ROW_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pose_validity_row/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_pose_validity_batch/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_ALGORITHM_ID: &str =
    "proper_rotation_bond_self_receptor_chirality_pocket_element_vdw/1.0.0";
pub const NATIVE_FIXED64_VALIDITY_RECEPTOR_TRAVERSAL_ID: &str =
    "ligand_index_then_full_receptor_index";
pub const NATIVE_FIXED64_ELEMENT_RECEPTOR_TRAVERSAL_ID: &str =
    "ligand_index_then_neighbor_cell_xyz_then_receptor_index";
pub const NATIVE_FIXED64_VALIDITY_MAX_PAIR_CHECKS: usize = 2_000_000;
pub const NATIVE_FIXED64_VALIDITY_MAX_CROSS_CHECKS: usize = 4_000_000;
pub const NATIVE_FIXED64_VALIDITY_MAX_CHIRALITY_CENTERS: usize = FIXED64_MAX_LIGAND_ATOMS;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64ValidityBackend {
    RustCpu,
    HipSafe,
    HipFast,
    CppCpuQualification,
}

impl NativeFixed64ValidityBackend {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::RustCpu => "rust_cpu",
            Self::HipSafe => "hip_safe",
            Self::HipFast => "hip_fast",
            Self::CppCpuQualification => "cpp_cpu_reference_qualification_only",
        }
    }

    #[must_use]
    pub const fn product_eligible(self) -> bool {
        !matches!(self, Self::CppCpuQualification)
    }

    const fn tag(self) -> u8 {
        match self {
            Self::RustCpu => 0,
            Self::HipSafe => 1,
            Self::HipFast => 2,
            Self::CppCpuQualification => 3,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64ValidityConfig {
    bond_length_tolerance_angstrom: f64,
    ligand_self_clash_angstrom: f64,
    receptor_ligand_clash_angstrom: f64,
    rotation_tolerance: f64,
    chirality_volume_tolerance: f64,
    severe_overlap_scale: f64,
    contact_cell_size_angstrom: f64,
    max_pair_checks: usize,
    max_cross_checks: usize,
    max_element_ligand_pair_checks: usize,
    max_element_receptor_candidate_pairs: usize,
    receipt_sha256: [u8; 32],
}

impl Default for NativeFixed64ValidityConfig {
    fn default() -> Self {
        let mut value = Self {
            bond_length_tolerance_angstrom: 0.15,
            ligand_self_clash_angstrom: 0.75,
            receptor_ligand_clash_angstrom: 0.8,
            rotation_tolerance: 1.0e-6,
            chirality_volume_tolerance: 1.0e-8,
            severe_overlap_scale: 0.55,
            contact_cell_size_angstrom: 3.5,
            max_pair_checks: 250_000,
            max_cross_checks: 1_000_000,
            max_element_ligand_pair_checks: 250_000,
            max_element_receptor_candidate_pairs: 1_000_000,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = config_sha256(&value);
        value
    }
}

impl NativeFixed64ValidityConfig {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        bond_length_tolerance_angstrom: f64,
        ligand_self_clash_angstrom: f64,
        receptor_ligand_clash_angstrom: f64,
        rotation_tolerance: f64,
        chirality_volume_tolerance: f64,
        severe_overlap_scale: f64,
        contact_cell_size_angstrom: f64,
        max_pair_checks: usize,
        max_cross_checks: usize,
        max_element_ligand_pair_checks: usize,
        max_element_receptor_candidate_pairs: usize,
    ) -> Result<Self, NativeFixed64ValidityError> {
        let mut value = Self {
            bond_length_tolerance_angstrom,
            ligand_self_clash_angstrom,
            receptor_ligand_clash_angstrom,
            rotation_tolerance,
            chirality_volume_tolerance,
            severe_overlap_scale,
            contact_cell_size_angstrom,
            max_pair_checks,
            max_cross_checks,
            max_element_ligand_pair_checks,
            max_element_receptor_candidate_pairs,
            receipt_sha256: [0; 32],
        };
        validate_config(&value)?;
        value.receipt_sha256 = config_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn bond_length_tolerance_angstrom(&self) -> f64 {
        self.bond_length_tolerance_angstrom
    }

    #[must_use]
    pub const fn ligand_self_clash_angstrom(&self) -> f64 {
        self.ligand_self_clash_angstrom
    }

    #[must_use]
    pub const fn receptor_ligand_clash_angstrom(&self) -> f64 {
        self.receptor_ligand_clash_angstrom
    }

    #[must_use]
    pub const fn rotation_tolerance(&self) -> f64 {
        self.rotation_tolerance
    }

    #[must_use]
    pub const fn chirality_volume_tolerance(&self) -> f64 {
        self.chirality_volume_tolerance
    }

    #[must_use]
    pub const fn severe_overlap_scale(&self) -> f64 {
        self.severe_overlap_scale
    }

    #[must_use]
    pub const fn contact_cell_size_angstrom(&self) -> f64 {
        self.contact_cell_size_angstrom
    }

    #[must_use]
    pub const fn max_pair_checks(&self) -> usize {
        self.max_pair_checks
    }

    #[must_use]
    pub const fn max_cross_checks(&self) -> usize {
        self.max_cross_checks
    }

    #[must_use]
    pub const fn max_element_ligand_pair_checks(&self) -> usize {
        self.max_element_ligand_pair_checks
    }

    #[must_use]
    pub const fn max_element_receptor_candidate_pairs(&self) -> usize {
        self.max_element_receptor_candidate_pairs
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        validate_config(self).is_ok() && config_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64ValidityErrorCode {
    InvalidConfig,
    InvalidContext,
    UpstreamCrossWired,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeFixed64ValidityError {
    code: NativeFixed64ValidityErrorCode,
    message: &'static str,
}

impl NativeFixed64ValidityError {
    const fn new(code: NativeFixed64ValidityErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeFixed64ValidityErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeFixed64ValidityError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native fixed64 pose validity: {}", self.message)
    }
}

impl std::error::Error for NativeFixed64ValidityError {}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64ValidityContext {
    authority_input_receipt_sha256: [u8; 32],
    receptor_system_sha256: [u8; 32],
    ligand_system_sha256: [u8; 32],
    scorer_context_receipt_sha256: [u8; 32],
    backend: NativeFixed64ValidityBackend,
    backend_receipt_sha256: [u8; 32],
    contact_policy_sha256: [u8; 32],
    reference_coordinates_angstrom: Vec<Vec3>,
    receptor_coordinates_angstrom: Vec<Vec3>,
    ligand_vdw_radii_angstrom: Vec<f64>,
    receptor_vdw_radii_angstrom: Vec<f64>,
    bond_pairs: Vec<[usize; 2]>,
    excluded_nonbonded_pairs: Vec<[usize; 2]>,
    chirality_centers: Vec<[usize; 4]>,
    pocket_center_angstrom: Vec3,
    pocket_radius_angstrom: f64,
    config: NativeFixed64ValidityConfig,
    receptor_cells: BTreeMap<(i64, i64, i64), Vec<usize>>,
    exclusion_set: BTreeSet<(usize, usize)>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64ValidityContext {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        authority_input_receipt_sha256: [u8; 32],
        receptor_system_sha256: [u8; 32],
        ligand_system_sha256: [u8; 32],
        scorer_context_receipt_sha256: [u8; 32],
        backend: NativeFixed64ValidityBackend,
        backend_receipt_sha256: [u8; 32],
        contact_policy_sha256: [u8; 32],
        reference_coordinates_angstrom: Vec<Vec3>,
        receptor_coordinates_angstrom: Vec<Vec3>,
        ligand_vdw_radii_angstrom: Vec<f64>,
        receptor_vdw_radii_angstrom: Vec<f64>,
        bond_pairs: Vec<[usize; 2]>,
        excluded_nonbonded_pairs: Vec<[usize; 2]>,
        chirality_centers: Vec<[usize; 4]>,
        pocket_center_angstrom: Vec3,
        pocket_radius_angstrom: f64,
        config: NativeFixed64ValidityConfig,
    ) -> Result<Self, NativeFixed64ValidityError> {
        let mut value = Self {
            authority_input_receipt_sha256,
            receptor_system_sha256,
            ligand_system_sha256,
            scorer_context_receipt_sha256,
            backend,
            backend_receipt_sha256,
            contact_policy_sha256,
            reference_coordinates_angstrom,
            receptor_coordinates_angstrom,
            ligand_vdw_radii_angstrom,
            receptor_vdw_radii_angstrom,
            bond_pairs,
            excluded_nonbonded_pairs,
            chirality_centers,
            pocket_center_angstrom,
            pocket_radius_angstrom,
            config,
            receptor_cells: BTreeMap::new(),
            exclusion_set: BTreeSet::new(),
            receipt_sha256: [0; 32],
        };
        validate_context_inputs(&value)?;
        value.receptor_cells = receptor_cells(&value);
        value.exclusion_set = value
            .excluded_nonbonded_pairs
            .iter()
            .map(|pair| (pair[0], pair[1]))
            .collect();
        value.receipt_sha256 = context_sha256(&value);
        Ok(value)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn from_scorer_context(
        scorer_context: &NativeScorerV1Context,
        backend: NativeFixed64ValidityBackend,
        backend_receipt_sha256: [u8; 32],
        contact_policy_sha256: [u8; 32],
        bond_pairs: Vec<[usize; 2]>,
        chirality_centers: Vec<[usize; 4]>,
        config: NativeFixed64ValidityConfig,
    ) -> Result<Self, NativeFixed64ValidityError> {
        if !scorer_context.has_valid_receipt() {
            return Err(context_error("ScorerV1 context receipt is invalid"));
        }
        Self::new(
            scorer_context.authority_input_receipt_sha256(),
            scorer_context.receptor_system_sha256(),
            scorer_context.ligand_system_sha256(),
            scorer_context.receipt_sha256(),
            backend,
            backend_receipt_sha256,
            contact_policy_sha256,
            scorer_context
                .ligand_reference_coordinates_angstrom()
                .to_vec(),
            scorer_context.receptor_coordinates_angstrom().to_vec(),
            scorer_context
                .ligand_atoms()
                .iter()
                .map(|atom| atom.vdw_radius_angstrom)
                .collect(),
            scorer_context
                .receptor_atoms()
                .iter()
                .map(|atom| atom.vdw_radius_angstrom)
                .collect(),
            bond_pairs,
            scorer_context.ligand_exclusions().to_vec(),
            chirality_centers,
            scorer_context.pocket_center_angstrom(),
            scorer_context.pocket_radius_angstrom(),
            config,
        )
    }

    #[must_use]
    pub const fn backend(&self) -> NativeFixed64ValidityBackend {
        self.backend
    }

    #[must_use]
    pub const fn authority_input_receipt_sha256(&self) -> [u8; 32] {
        self.authority_input_receipt_sha256
    }

    #[must_use]
    pub const fn receptor_system_sha256(&self) -> [u8; 32] {
        self.receptor_system_sha256
    }

    #[must_use]
    pub const fn ligand_system_sha256(&self) -> [u8; 32] {
        self.ligand_system_sha256
    }

    #[must_use]
    pub const fn scorer_context_receipt_sha256(&self) -> [u8; 32] {
        self.scorer_context_receipt_sha256
    }

    #[must_use]
    pub const fn backend_receipt_sha256(&self) -> [u8; 32] {
        self.backend_receipt_sha256
    }

    #[must_use]
    pub const fn contact_policy_sha256(&self) -> [u8; 32] {
        self.contact_policy_sha256
    }

    #[must_use]
    pub fn reference_coordinates_angstrom(&self) -> &[Vec3] {
        &self.reference_coordinates_angstrom
    }

    #[must_use]
    pub fn receptor_coordinates_angstrom(&self) -> &[Vec3] {
        &self.receptor_coordinates_angstrom
    }

    #[must_use]
    pub fn ligand_vdw_radii_angstrom(&self) -> &[f64] {
        &self.ligand_vdw_radii_angstrom
    }

    #[must_use]
    pub fn receptor_vdw_radii_angstrom(&self) -> &[f64] {
        &self.receptor_vdw_radii_angstrom
    }

    #[must_use]
    pub fn bond_pairs(&self) -> &[[usize; 2]] {
        &self.bond_pairs
    }

    #[must_use]
    pub fn excluded_nonbonded_pairs(&self) -> &[[usize; 2]] {
        &self.excluded_nonbonded_pairs
    }

    #[must_use]
    pub fn chirality_centers(&self) -> &[[usize; 4]] {
        &self.chirality_centers
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
    pub const fn config(&self) -> &NativeFixed64ValidityConfig {
        &self.config
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        validate_context_inputs(self).is_ok()
            && self.receptor_cells == receptor_cells(self)
            && self.exclusion_set
                == self
                    .excluded_nonbonded_pairs
                    .iter()
                    .map(|pair| (pair[0], pair[1]))
                    .collect()
            && context_sha256(self) == self.receipt_sha256
    }

    pub fn evaluate_coordinates(
        &self,
        coordinates_angstrom: &[Vec3],
        quaternion: Quaternion,
    ) -> Result<NativeFixed64ValidityKernelOutcome, NativeFixed64ValidityError> {
        Ok(self
            .prepare_rust_cpu_kernel()?
            .evaluate_coordinates(coordinates_angstrom, quaternion))
    }

    pub fn prepare_rust_cpu_kernel(
        &self,
    ) -> Result<NativeFixed64ValidityRustCpuKernel<'_>, NativeFixed64ValidityError> {
        if !self.has_valid_receipt() {
            return Err(context_error("pose validity context receipt is invalid"));
        }
        if self.backend != NativeFixed64ValidityBackend::RustCpu {
            return Err(cross_wired(
                "Rust pose validity kernel cannot claim an unexecuted backend",
            ));
        }
        Ok(NativeFixed64ValidityRustCpuKernel { context: self })
    }
}

#[derive(Clone, Copy)]
pub struct NativeFixed64ValidityRustCpuKernel<'context> {
    context: &'context NativeFixed64ValidityContext,
}

impl NativeFixed64ValidityRustCpuKernel<'_> {
    #[must_use]
    pub fn evaluate_coordinates(
        &self,
        coordinates_angstrom: &[Vec3],
        quaternion: Quaternion,
    ) -> NativeFixed64ValidityKernelOutcome {
        match evaluate_candidate(coordinates_angstrom, quaternion, self.context) {
            Ok((checks, measurements)) => NativeFixed64ValidityKernelOutcome::Evaluated {
                checks,
                measurements,
            },
            Err((failure_code, observed_count)) => {
                NativeFixed64ValidityKernelOutcome::TypedFailure(
                    NativeFixed64ValidityKernelFailure {
                        failure_code,
                        observed_count,
                    },
                )
            }
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeFixed64ValidityChecks {
    proper_rotation: bool,
    bond_lengths_preserved: bool,
    ligand_self_clash_free: bool,
    receptor_ligand_clash_free: bool,
    declared_chirality_preserved: bool,
    inside_declared_pocket: bool,
    element_vdw_ligand_overlap_free: bool,
    element_vdw_receptor_overlap_free: bool,
}

impl NativeFixed64ValidityChecks {
    #[must_use]
    pub const fn proper_rotation(self) -> bool {
        self.proper_rotation
    }

    #[must_use]
    pub const fn bond_lengths_preserved(self) -> bool {
        self.bond_lengths_preserved
    }

    #[must_use]
    pub const fn ligand_self_clash_free(self) -> bool {
        self.ligand_self_clash_free
    }

    #[must_use]
    pub const fn receptor_ligand_clash_free(self) -> bool {
        self.receptor_ligand_clash_free
    }

    #[must_use]
    pub const fn declared_chirality_preserved(self) -> bool {
        self.declared_chirality_preserved
    }

    #[must_use]
    pub const fn inside_declared_pocket(self) -> bool {
        self.inside_declared_pocket
    }

    #[must_use]
    pub const fn element_vdw_ligand_overlap_free(self) -> bool {
        self.element_vdw_ligand_overlap_free
    }

    #[must_use]
    pub const fn element_vdw_receptor_overlap_free(self) -> bool {
        self.element_vdw_receptor_overlap_free
    }

    #[must_use]
    pub const fn all(self) -> bool {
        self.proper_rotation
            && self.bond_lengths_preserved
            && self.ligand_self_clash_free
            && self.receptor_ligand_clash_free
            && self.declared_chirality_preserved
            && self.inside_declared_pocket
            && self.element_vdw_ligand_overlap_free
            && self.element_vdw_receptor_overlap_free
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeFixed64ValidityMeasurements {
    atom_count: usize,
    rotation_orthogonality_max_error: f64,
    rotation_determinant: f64,
    max_bond_length_delta_angstrom: f64,
    minimum_ligand_nonbonded_distance_angstrom: f64,
    evaluated_ligand_nonbonded_pair_count: usize,
    excluded_ligand_pair_count: usize,
    minimum_receptor_ligand_distance_angstrom: f64,
    evaluated_receptor_ligand_pair_count: usize,
    minimum_declared_chiral_volume: f64,
    declared_chirality_center_count: usize,
    maximum_pocket_center_distance_angstrom: f64,
    element_vdw_ligand_pair_count: usize,
    element_vdw_ligand_severe_overlap_count: usize,
    element_vdw_ligand_minimum_distance_angstrom: f64,
    element_vdw_ligand_minimum_ratio: f64,
    element_vdw_receptor_candidate_pair_count: usize,
    element_vdw_receptor_full_cartesian_pair_count: usize,
    element_vdw_receptor_cell_count: usize,
    element_vdw_receptor_severe_overlap_count: usize,
    element_vdw_receptor_minimum_distance_angstrom: f64,
    element_vdw_receptor_minimum_ratio: f64,
}

impl NativeFixed64ValidityMeasurements {
    #[must_use]
    pub const fn atom_count(self) -> usize {
        self.atom_count
    }

    #[must_use]
    pub const fn rotation_orthogonality_max_error(self) -> f64 {
        self.rotation_orthogonality_max_error
    }

    #[must_use]
    pub const fn rotation_determinant(self) -> f64 {
        self.rotation_determinant
    }

    #[must_use]
    pub const fn max_bond_length_delta_angstrom(self) -> f64 {
        self.max_bond_length_delta_angstrom
    }

    #[must_use]
    pub const fn minimum_ligand_nonbonded_distance_angstrom(self) -> f64 {
        self.minimum_ligand_nonbonded_distance_angstrom
    }

    #[must_use]
    pub const fn evaluated_ligand_nonbonded_pair_count(self) -> usize {
        self.evaluated_ligand_nonbonded_pair_count
    }

    #[must_use]
    pub const fn excluded_ligand_pair_count(self) -> usize {
        self.excluded_ligand_pair_count
    }

    #[must_use]
    pub const fn minimum_receptor_ligand_distance_angstrom(self) -> f64 {
        self.minimum_receptor_ligand_distance_angstrom
    }

    #[must_use]
    pub const fn evaluated_receptor_ligand_pair_count(self) -> usize {
        self.evaluated_receptor_ligand_pair_count
    }

    #[must_use]
    pub const fn minimum_declared_chiral_volume(self) -> f64 {
        self.minimum_declared_chiral_volume
    }

    #[must_use]
    pub const fn declared_chirality_center_count(self) -> usize {
        self.declared_chirality_center_count
    }

    #[must_use]
    pub const fn maximum_pocket_center_distance_angstrom(self) -> f64 {
        self.maximum_pocket_center_distance_angstrom
    }

    #[must_use]
    pub const fn element_vdw_ligand_pair_count(self) -> usize {
        self.element_vdw_ligand_pair_count
    }

    #[must_use]
    pub const fn element_vdw_ligand_severe_overlap_count(self) -> usize {
        self.element_vdw_ligand_severe_overlap_count
    }

    #[must_use]
    pub const fn element_vdw_ligand_minimum_distance_angstrom(self) -> f64 {
        self.element_vdw_ligand_minimum_distance_angstrom
    }

    #[must_use]
    pub const fn element_vdw_ligand_minimum_ratio(self) -> f64 {
        self.element_vdw_ligand_minimum_ratio
    }

    #[must_use]
    pub const fn element_vdw_receptor_severe_overlap_count(self) -> usize {
        self.element_vdw_receptor_severe_overlap_count
    }

    #[must_use]
    pub const fn element_vdw_receptor_candidate_pair_count(self) -> usize {
        self.element_vdw_receptor_candidate_pair_count
    }

    #[must_use]
    pub const fn element_vdw_receptor_full_cartesian_pair_count(self) -> usize {
        self.element_vdw_receptor_full_cartesian_pair_count
    }

    #[must_use]
    pub const fn element_vdw_receptor_cell_count(self) -> usize {
        self.element_vdw_receptor_cell_count
    }

    #[must_use]
    pub const fn element_vdw_receptor_minimum_distance_angstrom(self) -> f64 {
        self.element_vdw_receptor_minimum_distance_angstrom
    }

    #[must_use]
    pub const fn element_vdw_receptor_minimum_ratio(self) -> f64 {
        self.element_vdw_receptor_minimum_ratio
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64ValidityBlocker {
    RigidRotationNotProperOrthogonal,
    BondLengthPreservationFailed,
    LigandSelfClashDetected,
    ReceptorLigandClashDetected,
    DeclaredChiralityNotPreserved,
    PoseOutsideDeclaredPocket,
    ElementVdwLigandSevereOverlapDetected,
    ElementVdwReceptorSevereOverlapDetected,
}

impl NativeFixed64ValidityBlocker {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::RigidRotationNotProperOrthogonal => "rigid_rotation_not_proper_orthogonal",
            Self::BondLengthPreservationFailed => "bond_length_preservation_failed",
            Self::LigandSelfClashDetected => "ligand_self_clash_detected",
            Self::ReceptorLigandClashDetected => "receptor_ligand_clash_detected",
            Self::DeclaredChiralityNotPreserved => "declared_chirality_not_preserved",
            Self::PoseOutsideDeclaredPocket => "pose_outside_declared_pocket",
            Self::ElementVdwLigandSevereOverlapDetected => {
                "element_vdw_ligand_severe_overlap_detected"
            }
            Self::ElementVdwReceptorSevereOverlapDetected => {
                "element_vdw_receptor_severe_overlap_detected"
            }
        }
    }

    const fn tag(self) -> u8 {
        match self {
            Self::RigidRotationNotProperOrthogonal => 0,
            Self::BondLengthPreservationFailed => 1,
            Self::LigandSelfClashDetected => 2,
            Self::ReceptorLigandClashDetected => 3,
            Self::DeclaredChiralityNotPreserved => 4,
            Self::PoseOutsideDeclaredPocket => 5,
            Self::ElementVdwLigandSevereOverlapDetected => 6,
            Self::ElementVdwReceptorSevereOverlapDetected => 7,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64ValidityResult {
    proposal_record_receipt_sha256: [u8; 32],
    scorer_row_receipt_sha256: [u8; 32],
    coordinate_sha256: [u8; 32],
    authority_input_receipt_sha256: [u8; 32],
    context_receipt_sha256: [u8; 32],
    config_receipt_sha256: [u8; 32],
    backend: NativeFixed64ValidityBackend,
    backend_receipt_sha256: [u8; 32],
    contact_policy_sha256: [u8; 32],
    checks: NativeFixed64ValidityChecks,
    measurements: NativeFixed64ValidityMeasurements,
    blockers: Vec<NativeFixed64ValidityBlocker>,
    complete: bool,
    valid_within_evaluated_scope: bool,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64ValidityResult {
    #[must_use]
    pub const fn proposal_record_receipt_sha256(&self) -> [u8; 32] {
        self.proposal_record_receipt_sha256
    }

    #[must_use]
    pub const fn scorer_row_receipt_sha256(&self) -> [u8; 32] {
        self.scorer_row_receipt_sha256
    }

    #[must_use]
    pub const fn coordinate_sha256(&self) -> [u8; 32] {
        self.coordinate_sha256
    }

    #[must_use]
    pub const fn authority_input_receipt_sha256(&self) -> [u8; 32] {
        self.authority_input_receipt_sha256
    }

    #[must_use]
    pub const fn context_receipt_sha256(&self) -> [u8; 32] {
        self.context_receipt_sha256
    }

    #[must_use]
    pub const fn config_receipt_sha256(&self) -> [u8; 32] {
        self.config_receipt_sha256
    }

    #[must_use]
    pub const fn backend(&self) -> NativeFixed64ValidityBackend {
        self.backend
    }

    #[must_use]
    pub const fn backend_receipt_sha256(&self) -> [u8; 32] {
        self.backend_receipt_sha256
    }

    #[must_use]
    pub const fn contact_policy_sha256(&self) -> [u8; 32] {
        self.contact_policy_sha256
    }

    #[must_use]
    pub const fn checks(&self) -> NativeFixed64ValidityChecks {
        self.checks
    }

    #[must_use]
    pub const fn measurements(&self) -> NativeFixed64ValidityMeasurements {
        self.measurements
    }

    #[must_use]
    pub fn blockers(&self) -> &[NativeFixed64ValidityBlocker] {
        &self.blockers
    }

    #[must_use]
    pub const fn complete(&self) -> bool {
        self.complete
    }

    #[must_use]
    pub const fn valid(&self) -> bool {
        self.complete && self.valid_within_evaluated_scope
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.complete
            && self.valid_within_evaluated_scope == self.checks.all()
            && self.blockers == blockers_for(self.checks)
            && measurements_finite(&self.measurements)
            && result_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64ValidityFailureCode {
    UpstreamScorerFailure,
    InvalidCandidateCoordinates,
    LigandPairCapacityExceeded,
    ReceptorCrossCapacityExceeded,
    ElementLigandPairCapacityExceeded,
    ElementReceptorCandidateCapacityExceeded,
    NonfiniteDerivedMeasurement,
}

impl NativeFixed64ValidityFailureCode {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::UpstreamScorerFailure => "upstream_scorer_failure",
            Self::InvalidCandidateCoordinates => "invalid_candidate_coordinates",
            Self::LigandPairCapacityExceeded => "ligand_pair_capacity_exceeded",
            Self::ReceptorCrossCapacityExceeded => "receptor_cross_capacity_exceeded",
            Self::ElementLigandPairCapacityExceeded => "element_ligand_pair_capacity_exceeded",
            Self::ElementReceptorCandidateCapacityExceeded => {
                "element_receptor_candidate_capacity_exceeded"
            }
            Self::NonfiniteDerivedMeasurement => "nonfinite_derived_measurement",
        }
    }

    const fn tag(self) -> u8 {
        match self {
            Self::UpstreamScorerFailure => 0,
            Self::InvalidCandidateCoordinates => 1,
            Self::LigandPairCapacityExceeded => 2,
            Self::ReceptorCrossCapacityExceeded => 3,
            Self::ElementLigandPairCapacityExceeded => 4,
            Self::ElementReceptorCandidateCapacityExceeded => 5,
            Self::NonfiniteDerivedMeasurement => 6,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeFixed64ValidityKernelFailure {
    failure_code: NativeFixed64ValidityFailureCode,
    observed_count: usize,
}

impl NativeFixed64ValidityKernelFailure {
    #[must_use]
    pub const fn failure_code(self) -> NativeFixed64ValidityFailureCode {
        self.failure_code
    }

    #[must_use]
    pub const fn observed_count(self) -> usize {
        self.observed_count
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum NativeFixed64ValidityKernelOutcome {
    Evaluated {
        checks: NativeFixed64ValidityChecks,
        measurements: NativeFixed64ValidityMeasurements,
    },
    TypedFailure(NativeFixed64ValidityKernelFailure),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NativeFixed64ValidityFailure {
    proposal_record_receipt_sha256: [u8; 32],
    scorer_row_receipt_sha256: [u8; 32],
    upstream_scorer_failure_code: Option<NativeScorerV1FailureCode>,
    failure_code: NativeFixed64ValidityFailureCode,
    observed_count: usize,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64ValidityFailure {
    #[must_use]
    pub const fn upstream_scorer_failure_code(&self) -> Option<NativeScorerV1FailureCode> {
        self.upstream_scorer_failure_code
    }

    #[must_use]
    pub const fn failure_code(&self) -> NativeFixed64ValidityFailureCode {
        self.failure_code
    }

    #[must_use]
    pub const fn observed_count(&self) -> usize {
        self.observed_count
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        failure_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64ValidityRowStatus {
    Evaluated,
    UpstreamScorerFailure,
    TypedFailure,
}

impl NativeFixed64ValidityRowStatus {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::Evaluated => "evaluated",
            Self::UpstreamScorerFailure => "upstream_scorer_failure",
            Self::TypedFailure => "typed_failure",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64ValidityRow {
    slot_index: usize,
    proposal_record_receipt_sha256: [u8; 32],
    scorer_row_receipt_sha256: [u8; 32],
    status: NativeFixed64ValidityRowStatus,
    result: Option<NativeFixed64ValidityResult>,
    failure: Option<NativeFixed64ValidityFailure>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64ValidityRow {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn status(&self) -> NativeFixed64ValidityRowStatus {
        self.status
    }

    #[must_use]
    pub const fn result(&self) -> Option<&NativeFixed64ValidityResult> {
        self.result.as_ref()
    }

    #[must_use]
    pub const fn failure(&self) -> Option<&NativeFixed64ValidityFailure> {
        self.failure.as_ref()
    }

    #[must_use]
    pub const fn valid(&self) -> bool {
        match &self.result {
            Some(result) => result.valid(),
            None => false,
        }
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let content_valid = match self.status {
            NativeFixed64ValidityRowStatus::Evaluated => {
                self.result
                    .as_ref()
                    .is_some_and(NativeFixed64ValidityResult::has_valid_receipt)
                    && self.failure.is_none()
            }
            NativeFixed64ValidityRowStatus::UpstreamScorerFailure
            | NativeFixed64ValidityRowStatus::TypedFailure => {
                self.result.is_none()
                    && self
                        .failure
                        .as_ref()
                        .is_some_and(NativeFixed64ValidityFailure::has_valid_receipt)
            }
        };
        content_valid && row_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64ValidityBatch {
    scorer_batch: Box<NativeScorerV1Batch>,
    context: NativeFixed64ValidityContext,
    rows: Box<[NativeFixed64ValidityRow; FIXED64_CANDIDATE_COUNT]>,
    receipt_sha256: [u8; 32],
}

impl NativeFixed64ValidityBatch {
    #[must_use]
    pub const fn scorer_batch(&self) -> &NativeScorerV1Batch {
        &self.scorer_batch
    }

    #[must_use]
    pub const fn context(&self) -> &NativeFixed64ValidityContext {
        &self.context
    }

    #[must_use]
    pub const fn rows(&self) -> &[NativeFixed64ValidityRow; FIXED64_CANDIDATE_COUNT] {
        &self.rows
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn evaluated_count(&self) -> usize {
        self.rows
            .iter()
            .filter(|row| row.status == NativeFixed64ValidityRowStatus::Evaluated)
            .count()
    }

    #[must_use]
    pub fn valid_count(&self) -> usize {
        self.rows.iter().filter(|row| row.valid()).count()
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
        if validate_bound_inputs(&self.scorer_batch, &self.context).is_err() {
            return false;
        }
        let Ok(expected_rows) = build_rows(&self.scorer_batch, &self.context) else {
            return false;
        };
        self.rows == expected_rows && batch_sha256(self) == self.receipt_sha256
    }
}

pub fn evaluate_native_fixed64_pose_validity(
    scorer_batch: NativeScorerV1Batch,
    context: NativeFixed64ValidityContext,
) -> Result<NativeFixed64ValidityBatch, NativeFixed64ValidityError> {
    validate_bound_inputs(&scorer_batch, &context)?;
    let rows = build_rows(&scorer_batch, &context)?;
    let mut value = NativeFixed64ValidityBatch {
        scorer_batch: Box::new(scorer_batch),
        context,
        rows,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = batch_sha256(&value);
    Ok(value)
}

fn validate_config(value: &NativeFixed64ValidityConfig) -> Result<(), NativeFixed64ValidityError> {
    if [
        value.bond_length_tolerance_angstrom,
        value.ligand_self_clash_angstrom,
        value.receptor_ligand_clash_angstrom,
        value.rotation_tolerance,
        value.chirality_volume_tolerance,
    ]
    .iter()
    .any(|item| !item.is_finite() || !(0.0..=100.0).contains(item))
        || !value.severe_overlap_scale.is_finite()
        || !(0.1..=1.0).contains(&value.severe_overlap_scale)
        || !value.contact_cell_size_angstrom.is_finite()
        || !(0.5..=10.0).contains(&value.contact_cell_size_angstrom)
        || value.max_pair_checks > NATIVE_FIXED64_VALIDITY_MAX_PAIR_CHECKS
        || value.max_cross_checks > NATIVE_FIXED64_VALIDITY_MAX_CROSS_CHECKS
        || value.max_element_ligand_pair_checks > NATIVE_FIXED64_VALIDITY_MAX_PAIR_CHECKS
        || value.max_element_receptor_candidate_pairs > NATIVE_FIXED64_VALIDITY_MAX_CROSS_CHECKS
    {
        return Err(config_error(
            "pose validity configuration is outside frozen bounds",
        ));
    }
    Ok(())
}

fn validate_context_inputs(
    value: &NativeFixed64ValidityContext,
) -> Result<(), NativeFixed64ValidityError> {
    if [
        value.authority_input_receipt_sha256,
        value.receptor_system_sha256,
        value.ligand_system_sha256,
        value.scorer_context_receipt_sha256,
        value.backend_receipt_sha256,
        value.contact_policy_sha256,
    ]
    .contains(&[0; 32])
        || !value.config.has_valid_receipt()
    {
        return Err(context_error(
            "pose validity identity or config receipt is invalid",
        ));
    }
    native_fixed64_coordinate_sha256(&value.reference_coordinates_angstrom)
        .map_err(|_| context_error("reference coordinates are invalid"))?;
    native_fixed64_coordinate_sha256(&value.receptor_coordinates_angstrom)
        .map_err(|_| context_error("receptor coordinates are invalid"))?;
    let ligand_count = value.reference_coordinates_angstrom.len();
    let receptor_count = value.receptor_coordinates_angstrom.len();
    if ligand_count == 0
        || ligand_count > FIXED64_MAX_LIGAND_ATOMS
        || receptor_count == 0
        || receptor_count > FIXED64_MAX_RECEPTOR_ATOMS
        || ligand_count != value.ligand_vdw_radii_angstrom.len()
        || receptor_count != value.receptor_vdw_radii_angstrom.len()
    {
        return Err(context_error("pose validity atom denominators disagree"));
    }
    if value
        .ligand_vdw_radii_angstrom
        .iter()
        .chain(&value.receptor_vdw_radii_angstrom)
        .any(|radius| !radius.is_finite() || !(0.1..=10.0).contains(radius))
    {
        return Err(context_error("pose validity vdW radii are invalid"));
    }
    validate_pairs(&value.bond_pairs, ligand_count, "bond pairs")?;
    validate_pairs(
        &value.excluded_nonbonded_pairs,
        ligand_count,
        "excluded pairs",
    )?;
    let exclusions = value
        .excluded_nonbonded_pairs
        .iter()
        .copied()
        .collect::<BTreeSet<_>>();
    if value
        .bond_pairs
        .iter()
        .any(|pair| !exclusions.contains(pair))
    {
        return Err(context_error("excluded pairs must contain every bond"));
    }
    if value.chirality_centers.len() > NATIVE_FIXED64_VALIDITY_MAX_CHIRALITY_CENTERS
        || value.chirality_centers.iter().any(|row| {
            row.iter().any(|index| *index >= ligand_count)
                || row.iter().copied().collect::<BTreeSet<_>>().len() != 4
        })
        || value
            .chirality_centers
            .iter()
            .copied()
            .collect::<BTreeSet<_>>()
            .len()
            != value.chirality_centers.len()
    {
        return Err(context_error("chirality centers are invalid or duplicated"));
    }
    if !value.pocket_center_angstrom.is_finite()
        || value.pocket_center_angstrom.x.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || value.pocket_center_angstrom.y.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || value.pocket_center_angstrom.z.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        || !value.pocket_radius_angstrom.is_finite()
        || !(0.0..=1_000.0).contains(&value.pocket_radius_angstrom)
        || value.pocket_radius_angstrom == 0.0
    {
        return Err(context_error("pocket geometry is outside frozen bounds"));
    }
    let maximum_radius = value
        .ligand_vdw_radii_angstrom
        .iter()
        .chain(&value.receptor_vdw_radii_angstrom)
        .copied()
        .fold(0.0_f64, f64::max);
    if value.config.contact_cell_size_angstrom + 1.0e-12
        < 2.0 * maximum_radius * value.config.severe_overlap_scale
    {
        return Err(context_error(
            "contact cell does not cover the maximum severe-overlap cutoff",
        ));
    }
    Ok(())
}

fn validate_pairs(
    values: &[[usize; 2]],
    atom_count: usize,
    label: &'static str,
) -> Result<(), NativeFixed64ValidityError> {
    if values.windows(2).any(|rows| rows[0] >= rows[1])
        || values
            .iter()
            .any(|[first, second]| first >= second || *second >= atom_count)
    {
        return Err(context_error(label));
    }
    Ok(())
}

fn validate_bound_inputs(
    scorer_batch: &NativeScorerV1Batch,
    context: &NativeFixed64ValidityContext,
) -> Result<(), NativeFixed64ValidityError> {
    if !scorer_batch.has_valid_receipt() || !context.has_valid_receipt() {
        return Err(cross_wired(
            "scorer batch or validity context receipt is invalid",
        ));
    }
    if context.backend != NativeFixed64ValidityBackend::RustCpu {
        return Err(cross_wired(
            "Rust validity entry point cannot claim an unexecuted backend",
        ));
    }
    let scorer_context = scorer_batch.context();
    if context.scorer_context_receipt_sha256 != scorer_context.receipt_sha256()
        || context.authority_input_receipt_sha256 != scorer_context.authority_input_receipt_sha256()
        || context.receptor_system_sha256 != scorer_context.receptor_system_sha256()
        || context.ligand_system_sha256 != scorer_context.ligand_system_sha256()
        || context.reference_coordinates_angstrom
            != scorer_context.ligand_reference_coordinates_angstrom()
        || context.receptor_coordinates_angstrom != scorer_context.receptor_coordinates_angstrom()
        || context.ligand_vdw_radii_angstrom
            != scorer_context
                .ligand_atoms()
                .iter()
                .map(|atom| atom.vdw_radius_angstrom)
                .collect::<Vec<_>>()
        || context.receptor_vdw_radii_angstrom
            != scorer_context
                .receptor_atoms()
                .iter()
                .map(|atom| atom.vdw_radius_angstrom)
                .collect::<Vec<_>>()
        || scorer_context.backend() != NativeScorerV1Backend::RustCpu
    {
        return Err(cross_wired(
            "pose validity context is cross-wired to another scorer system",
        ));
    }
    Ok(())
}

fn build_rows(
    scorer_batch: &NativeScorerV1Batch,
    context: &NativeFixed64ValidityContext,
) -> Result<Box<[NativeFixed64ValidityRow; FIXED64_CANDIDATE_COUNT]>, NativeFixed64ValidityError> {
    let kernel = context.prepare_rust_cpu_kernel()?;
    let proposals = scorer_batch
        .admission()
        .proposal_batch()
        .ok_or_else(|| cross_wired("pose validity requires proposal evidence"))?;
    let mut rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for slot_index in 0..FIXED64_CANDIDATE_COUNT {
        let scorer_row = &scorer_batch.rows()[slot_index];
        let proposal = &proposals.records()[slot_index];
        if scorer_row.slot_index() != slot_index || proposal.slot_index() != slot_index {
            return Err(cross_wired("pose validity slot index is cross-wired"));
        }
        if scorer_row.status() != NativeScorerV1RowStatus::Scored {
            let upstream = scorer_row
                .failure()
                .map(|failure| failure.failure_code())
                .ok_or_else(|| cross_wired("failed scorer row lacks typed evidence"))?;
            rows.push(failure_row(
                slot_index,
                proposal.receipt_sha256(),
                scorer_row.receipt_sha256(),
                NativeFixed64ValidityRowStatus::UpstreamScorerFailure,
                NativeFixed64ValidityFailureCode::UpstreamScorerFailure,
                Some(upstream),
                0,
            ));
            continue;
        }
        let coordinates = scorer_batch
            .admission()
            .candidate_coordinates_angstrom(slot_index)
            .ok_or_else(|| cross_wired("scored row lacks candidate coordinates"))?;
        let quaternion = proposal
            .placement()
            .map(placement_quaternion)
            .ok_or_else(|| cross_wired("scored row lacks placement evidence"))?;
        match kernel.evaluate_coordinates(coordinates, quaternion) {
            NativeFixed64ValidityKernelOutcome::Evaluated {
                checks,
                measurements,
            } => rows.push(result_row(
                slot_index,
                proposal.receipt_sha256(),
                scorer_row.receipt_sha256(),
                native_fixed64_coordinate_sha256(coordinates)
                    .map_err(|_| cross_wired("candidate coordinate identity is invalid"))?,
                checks,
                measurements,
                context,
            )),
            NativeFixed64ValidityKernelOutcome::TypedFailure(failure) => rows.push(failure_row(
                slot_index,
                proposal.receipt_sha256(),
                scorer_row.receipt_sha256(),
                NativeFixed64ValidityRowStatus::TypedFailure,
                failure.failure_code(),
                None,
                failure.observed_count(),
            )),
        }
    }
    rows.into_boxed_slice()
        .try_into()
        .map_err(|_| internal("pose validity row denominator changed"))
}

fn placement_quaternion(placement: &Fixed64ProposalPlacement) -> Quaternion {
    match placement {
        Fixed64ProposalPlacement::ExactPassthrough(_) => Quaternion::new(0.0, 0.0, 0.0, 1.0),
        Fixed64ProposalPlacement::IndexedSo3(value) => value.quaternion(),
        Fixed64ProposalPlacement::SingleAnchor(value) => value.quaternion(),
    }
}

fn evaluate_candidate(
    coordinates: &[Vec3],
    quaternion: Quaternion,
    context: &NativeFixed64ValidityContext,
) -> Result<
    (
        NativeFixed64ValidityChecks,
        NativeFixed64ValidityMeasurements,
    ),
    (NativeFixed64ValidityFailureCode, usize),
> {
    if coordinates.len() != context.reference_coordinates_angstrom.len()
        || native_fixed64_coordinate_sha256(coordinates).is_err()
    {
        return Err((
            NativeFixed64ValidityFailureCode::InvalidCandidateCoordinates,
            coordinates.len(),
        ));
    }
    let (rotation_orthogonality_max_error, rotation_determinant) =
        rotation_measurements(quaternion);
    let proper_rotation = rotation_orthogonality_max_error <= context.config.rotation_tolerance
        && (rotation_determinant - 1.0).abs() <= context.config.rotation_tolerance;

    let mut max_bond_length_delta_angstrom = 0.0_f64;
    for [first, second] in context.bond_pairs.iter().copied() {
        let reference = distance(
            context.reference_coordinates_angstrom[first],
            context.reference_coordinates_angstrom[second],
        );
        let observed = distance(coordinates[first], coordinates[second]);
        max_bond_length_delta_angstrom =
            max_bond_length_delta_angstrom.max((reference - observed).abs());
    }
    let bond_lengths_preserved =
        max_bond_length_delta_angstrom <= context.config.bond_length_tolerance_angstrom;

    let total_ligand_pairs = coordinates
        .len()
        .checked_mul(coordinates.len().saturating_sub(1))
        .map(|value| value / 2)
        .ok_or((
            NativeFixed64ValidityFailureCode::LigandPairCapacityExceeded,
            usize::MAX,
        ))?;
    if total_ligand_pairs > context.config.max_pair_checks {
        return Err((
            NativeFixed64ValidityFailureCode::LigandPairCapacityExceeded,
            total_ligand_pairs,
        ));
    }
    let mut minimum_ligand_nonbonded_distance_angstrom = f64::INFINITY;
    let mut evaluated_ligand_nonbonded_pair_count = 0usize;
    let mut element_vdw_ligand_severe_overlap_count = 0usize;
    let mut element_vdw_ligand_minimum_distance_angstrom = f64::INFINITY;
    let mut element_vdw_ligand_minimum_ratio = f64::INFINITY;
    for first in 0..coordinates.len() {
        for second in (first + 1)..coordinates.len() {
            if context.exclusion_set.contains(&(first, second)) {
                continue;
            }
            evaluated_ligand_nonbonded_pair_count += 1;
            if evaluated_ligand_nonbonded_pair_count > context.config.max_element_ligand_pair_checks
            {
                return Err((
                    NativeFixed64ValidityFailureCode::ElementLigandPairCapacityExceeded,
                    evaluated_ligand_nonbonded_pair_count,
                ));
            }
            let observed = distance(coordinates[first], coordinates[second]);
            minimum_ligand_nonbonded_distance_angstrom =
                minimum_ligand_nonbonded_distance_angstrom.min(observed);
            element_vdw_ligand_minimum_distance_angstrom =
                element_vdw_ligand_minimum_distance_angstrom.min(observed);
            let ratio = observed
                / (context.ligand_vdw_radii_angstrom[first]
                    + context.ligand_vdw_radii_angstrom[second]);
            element_vdw_ligand_minimum_ratio = element_vdw_ligand_minimum_ratio.min(ratio);
            if ratio < context.config.severe_overlap_scale {
                element_vdw_ligand_severe_overlap_count += 1;
            }
        }
    }
    let minimum_ligand_nonbonded_distance_angstrom =
        minimum_or_sentinel(minimum_ligand_nonbonded_distance_angstrom);
    let ligand_self_clash_free =
        minimum_ligand_nonbonded_distance_angstrom >= context.config.ligand_self_clash_angstrom;

    let cross_count = coordinates
        .len()
        .checked_mul(context.receptor_coordinates_angstrom.len())
        .ok_or((
            NativeFixed64ValidityFailureCode::ReceptorCrossCapacityExceeded,
            usize::MAX,
        ))?;
    if cross_count > context.config.max_cross_checks {
        return Err((
            NativeFixed64ValidityFailureCode::ReceptorCrossCapacityExceeded,
            cross_count,
        ));
    }
    let mut minimum_receptor_ligand_distance_angstrom = f64::INFINITY;
    for coordinate in coordinates {
        for receptor in &context.receptor_coordinates_angstrom {
            minimum_receptor_ligand_distance_angstrom =
                minimum_receptor_ligand_distance_angstrom.min(distance(*coordinate, *receptor));
        }
    }
    let receptor_ligand_clash_free =
        minimum_receptor_ligand_distance_angstrom >= context.config.receptor_ligand_clash_angstrom;

    let mut minimum_declared_chiral_volume = f64::INFINITY;
    let mut declared_chirality_preserved = true;
    for indices in context.chirality_centers.iter().copied() {
        let reference = signed_volume(&context.reference_coordinates_angstrom, indices);
        let observed = signed_volume(coordinates, indices);
        minimum_declared_chiral_volume = minimum_declared_chiral_volume
            .min(reference.abs())
            .min(observed.abs());
        if reference.abs() <= context.config.chirality_volume_tolerance
            || observed.abs() <= context.config.chirality_volume_tolerance
            || reference * observed < 0.0
        {
            declared_chirality_preserved = false;
        }
    }
    let minimum_declared_chiral_volume = if minimum_declared_chiral_volume.is_finite() {
        minimum_declared_chiral_volume
    } else {
        0.0
    };

    let maximum_pocket_center_distance_angstrom = coordinates
        .iter()
        .map(|coordinate| distance(*coordinate, context.pocket_center_angstrom))
        .fold(0.0_f64, f64::max);
    let inside_declared_pocket =
        maximum_pocket_center_distance_angstrom <= context.pocket_radius_angstrom;

    let mut element_vdw_receptor_candidate_pair_count = 0usize;
    let mut element_vdw_receptor_severe_overlap_count = 0usize;
    let mut element_vdw_receptor_minimum_distance_angstrom = f64::INFINITY;
    let mut element_vdw_receptor_minimum_ratio = f64::INFINITY;
    for (ligand_index, coordinate) in coordinates.iter().copied().enumerate() {
        let center = cell_key(coordinate, context.config.contact_cell_size_angstrom);
        for x in (center.0 - 1)..=(center.0 + 1) {
            for y in (center.1 - 1)..=(center.1 + 1) {
                for z in (center.2 - 1)..=(center.2 + 1) {
                    let Some(receptor_indices) = context.receptor_cells.get(&(x, y, z)) else {
                        continue;
                    };
                    for receptor_index in receptor_indices.iter().copied() {
                        element_vdw_receptor_candidate_pair_count += 1;
                        if element_vdw_receptor_candidate_pair_count
                            > context.config.max_element_receptor_candidate_pairs
                        {
                            return Err((
                                NativeFixed64ValidityFailureCode::ElementReceptorCandidateCapacityExceeded,
                                element_vdw_receptor_candidate_pair_count,
                            ));
                        }
                        let observed = distance(
                            coordinate,
                            context.receptor_coordinates_angstrom[receptor_index],
                        );
                        element_vdw_receptor_minimum_distance_angstrom =
                            element_vdw_receptor_minimum_distance_angstrom.min(observed);
                        let ratio = observed
                            / (context.ligand_vdw_radii_angstrom[ligand_index]
                                + context.receptor_vdw_radii_angstrom[receptor_index]);
                        element_vdw_receptor_minimum_ratio =
                            element_vdw_receptor_minimum_ratio.min(ratio);
                        if ratio < context.config.severe_overlap_scale {
                            element_vdw_receptor_severe_overlap_count += 1;
                        }
                    }
                }
            }
        }
    }

    let checks = NativeFixed64ValidityChecks {
        proper_rotation,
        bond_lengths_preserved,
        ligand_self_clash_free,
        receptor_ligand_clash_free,
        declared_chirality_preserved,
        inside_declared_pocket,
        element_vdw_ligand_overlap_free: element_vdw_ligand_severe_overlap_count == 0,
        element_vdw_receptor_overlap_free: element_vdw_receptor_severe_overlap_count == 0,
    };
    let measurements = NativeFixed64ValidityMeasurements {
        atom_count: coordinates.len(),
        rotation_orthogonality_max_error,
        rotation_determinant,
        max_bond_length_delta_angstrom,
        minimum_ligand_nonbonded_distance_angstrom,
        evaluated_ligand_nonbonded_pair_count,
        excluded_ligand_pair_count: context.excluded_nonbonded_pairs.len(),
        minimum_receptor_ligand_distance_angstrom,
        evaluated_receptor_ligand_pair_count: cross_count,
        minimum_declared_chiral_volume,
        declared_chirality_center_count: context.chirality_centers.len(),
        maximum_pocket_center_distance_angstrom,
        element_vdw_ligand_pair_count: evaluated_ligand_nonbonded_pair_count,
        element_vdw_ligand_severe_overlap_count,
        element_vdw_ligand_minimum_distance_angstrom: minimum_or_sentinel(
            element_vdw_ligand_minimum_distance_angstrom,
        ),
        element_vdw_ligand_minimum_ratio: minimum_or_sentinel(element_vdw_ligand_minimum_ratio),
        element_vdw_receptor_candidate_pair_count,
        element_vdw_receptor_full_cartesian_pair_count: cross_count,
        element_vdw_receptor_cell_count: context.receptor_cells.len(),
        element_vdw_receptor_severe_overlap_count,
        element_vdw_receptor_minimum_distance_angstrom: minimum_or_sentinel(
            element_vdw_receptor_minimum_distance_angstrom,
        ),
        element_vdw_receptor_minimum_ratio: minimum_or_sentinel(element_vdw_receptor_minimum_ratio),
    };
    if !measurements_finite(&measurements) {
        return Err((
            NativeFixed64ValidityFailureCode::NonfiniteDerivedMeasurement,
            0,
        ));
    }
    Ok((checks, measurements))
}

fn result_row(
    slot_index: usize,
    proposal_record_receipt_sha256: [u8; 32],
    scorer_row_receipt_sha256: [u8; 32],
    coordinate_sha256: [u8; 32],
    checks: NativeFixed64ValidityChecks,
    measurements: NativeFixed64ValidityMeasurements,
    context: &NativeFixed64ValidityContext,
) -> NativeFixed64ValidityRow {
    let blockers = blockers_for(checks);
    let mut result = NativeFixed64ValidityResult {
        proposal_record_receipt_sha256,
        scorer_row_receipt_sha256,
        coordinate_sha256,
        authority_input_receipt_sha256: context.authority_input_receipt_sha256,
        context_receipt_sha256: context.receipt_sha256,
        config_receipt_sha256: context.config.receipt_sha256,
        backend: context.backend,
        backend_receipt_sha256: context.backend_receipt_sha256,
        contact_policy_sha256: context.contact_policy_sha256,
        checks,
        measurements,
        blockers,
        complete: true,
        valid_within_evaluated_scope: checks.all(),
        receipt_sha256: [0; 32],
    };
    result.receipt_sha256 = result_sha256(&result);
    let mut row = NativeFixed64ValidityRow {
        slot_index,
        proposal_record_receipt_sha256,
        scorer_row_receipt_sha256,
        status: NativeFixed64ValidityRowStatus::Evaluated,
        result: Some(result),
        failure: None,
        receipt_sha256: [0; 32],
    };
    row.receipt_sha256 = row_sha256(&row);
    row
}

#[allow(clippy::too_many_arguments)]
fn failure_row(
    slot_index: usize,
    proposal_record_receipt_sha256: [u8; 32],
    scorer_row_receipt_sha256: [u8; 32],
    status: NativeFixed64ValidityRowStatus,
    failure_code: NativeFixed64ValidityFailureCode,
    upstream_scorer_failure_code: Option<NativeScorerV1FailureCode>,
    observed_count: usize,
) -> NativeFixed64ValidityRow {
    let mut failure = NativeFixed64ValidityFailure {
        proposal_record_receipt_sha256,
        scorer_row_receipt_sha256,
        upstream_scorer_failure_code,
        failure_code,
        observed_count,
        receipt_sha256: [0; 32],
    };
    failure.receipt_sha256 = failure_sha256(&failure);
    let mut row = NativeFixed64ValidityRow {
        slot_index,
        proposal_record_receipt_sha256,
        scorer_row_receipt_sha256,
        status,
        result: None,
        failure: Some(failure),
        receipt_sha256: [0; 32],
    };
    row.receipt_sha256 = row_sha256(&row);
    row
}

fn blockers_for(checks: NativeFixed64ValidityChecks) -> Vec<NativeFixed64ValidityBlocker> {
    let mut blockers = Vec::new();
    if !checks.proper_rotation {
        blockers.push(NativeFixed64ValidityBlocker::RigidRotationNotProperOrthogonal);
    }
    if !checks.bond_lengths_preserved {
        blockers.push(NativeFixed64ValidityBlocker::BondLengthPreservationFailed);
    }
    if !checks.ligand_self_clash_free {
        blockers.push(NativeFixed64ValidityBlocker::LigandSelfClashDetected);
    }
    if !checks.receptor_ligand_clash_free {
        blockers.push(NativeFixed64ValidityBlocker::ReceptorLigandClashDetected);
    }
    if !checks.declared_chirality_preserved {
        blockers.push(NativeFixed64ValidityBlocker::DeclaredChiralityNotPreserved);
    }
    if !checks.inside_declared_pocket {
        blockers.push(NativeFixed64ValidityBlocker::PoseOutsideDeclaredPocket);
    }
    if !checks.element_vdw_ligand_overlap_free {
        blockers.push(NativeFixed64ValidityBlocker::ElementVdwLigandSevereOverlapDetected);
    }
    if !checks.element_vdw_receptor_overlap_free {
        blockers.push(NativeFixed64ValidityBlocker::ElementVdwReceptorSevereOverlapDetected);
    }
    blockers
}

fn rotation_measurements(quaternion: Quaternion) -> (f64, f64) {
    let x = quaternion.x;
    let y = quaternion.y;
    let z = quaternion.z;
    let w = quaternion.w;
    let matrix = [
        [
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
        ],
        [
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
        ],
        [
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
        ],
    ];
    let mut maximum = 0.0_f64;
    for row in 0..3 {
        for column in 0..3 {
            let value = (0..3)
                .map(|index| matrix[index][row] * matrix[index][column])
                .sum::<f64>();
            maximum = maximum.max((value - f64::from(row == column)).abs());
        }
    }
    let determinant = matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]);
    (maximum, determinant)
}

fn signed_volume(coordinates: &[Vec3], indices: [usize; 4]) -> f64 {
    let origin = coordinates[indices[0]];
    coordinates[indices[1]]
        .minus(origin)
        .cross(coordinates[indices[2]].minus(origin))
        .dot(coordinates[indices[3]].minus(origin))
}

fn distance(first: Vec3, second: Vec3) -> f64 {
    libm::sqrt(first.minus(second).dot(first.minus(second)))
}

fn minimum_or_sentinel(value: f64) -> f64 {
    if value.is_finite() {
        value
    } else {
        999.0
    }
}

fn cell_key(value: Vec3, size: f64) -> (i64, i64, i64) {
    (
        (value.x / size).floor() as i64,
        (value.y / size).floor() as i64,
        (value.z / size).floor() as i64,
    )
}

fn receptor_cells(value: &NativeFixed64ValidityContext) -> BTreeMap<(i64, i64, i64), Vec<usize>> {
    let mut cells = BTreeMap::new();
    for (index, coordinate) in value
        .receptor_coordinates_angstrom
        .iter()
        .copied()
        .enumerate()
    {
        cells
            .entry(cell_key(
                coordinate,
                value.config.contact_cell_size_angstrom,
            ))
            .or_insert_with(Vec::new)
            .push(index);
    }
    cells
}

fn measurements_finite(value: &NativeFixed64ValidityMeasurements) -> bool {
    [
        value.rotation_orthogonality_max_error,
        value.rotation_determinant,
        value.max_bond_length_delta_angstrom,
        value.minimum_ligand_nonbonded_distance_angstrom,
        value.minimum_receptor_ligand_distance_angstrom,
        value.minimum_declared_chiral_volume,
        value.maximum_pocket_center_distance_angstrom,
        value.element_vdw_ligand_minimum_distance_angstrom,
        value.element_vdw_ligand_minimum_ratio,
        value.element_vdw_receptor_minimum_distance_angstrom,
        value.element_vdw_receptor_minimum_ratio,
    ]
    .iter()
    .all(|item| item.is_finite())
}

fn config_sha256(value: &NativeFixed64ValidityConfig) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_VALIDITY_CONFIG_SCHEMA_ID);
    hash.string(NATIVE_FIXED64_VALIDITY_ALGORITHM_ID);
    hash.f64(value.bond_length_tolerance_angstrom);
    hash.f64(value.ligand_self_clash_angstrom);
    hash.f64(value.receptor_ligand_clash_angstrom);
    hash.f64(value.rotation_tolerance);
    hash.f64(value.chirality_volume_tolerance);
    hash.f64(value.severe_overlap_scale);
    hash.f64(value.contact_cell_size_angstrom);
    hash.usize(value.max_pair_checks);
    hash.usize(value.max_cross_checks);
    hash.usize(value.max_element_ligand_pair_checks);
    hash.usize(value.max_element_receptor_candidate_pairs);
    hash.finish()
}

fn context_sha256(value: &NativeFixed64ValidityContext) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_VALIDITY_CONTEXT_SCHEMA_ID);
    hash.digest(value.authority_input_receipt_sha256);
    hash.digest(value.receptor_system_sha256);
    hash.digest(value.ligand_system_sha256);
    hash.digest(value.scorer_context_receipt_sha256);
    hash.byte(value.backend.tag());
    hash.digest(value.backend_receipt_sha256);
    hash.digest(value.contact_policy_sha256);
    hash.usize(value.reference_coordinates_angstrom.len());
    for coordinate in &value.reference_coordinates_angstrom {
        hash.vec3(*coordinate);
    }
    hash.usize(value.receptor_coordinates_angstrom.len());
    for coordinate in &value.receptor_coordinates_angstrom {
        hash.vec3(*coordinate);
    }
    hash.usize(value.ligand_vdw_radii_angstrom.len());
    for radius in &value.ligand_vdw_radii_angstrom {
        hash.f64(*radius);
    }
    hash.usize(value.receptor_vdw_radii_angstrom.len());
    for radius in &value.receptor_vdw_radii_angstrom {
        hash.f64(*radius);
    }
    hash.usize(value.bond_pairs.len());
    for pair in &value.bond_pairs {
        hash.usize(pair[0]);
        hash.usize(pair[1]);
    }
    hash.usize(value.excluded_nonbonded_pairs.len());
    for pair in &value.excluded_nonbonded_pairs {
        hash.usize(pair[0]);
        hash.usize(pair[1]);
    }
    hash.usize(value.chirality_centers.len());
    for row in &value.chirality_centers {
        for index in row {
            hash.usize(*index);
        }
    }
    hash.vec3(value.pocket_center_angstrom);
    hash.f64(value.pocket_radius_angstrom);
    hash.digest(value.config.receipt_sha256);
    hash.finish()
}

fn hash_checks(hash: &mut CanonicalHash, value: NativeFixed64ValidityChecks) {
    hash.bool(value.proper_rotation);
    hash.bool(value.bond_lengths_preserved);
    hash.bool(value.ligand_self_clash_free);
    hash.bool(value.receptor_ligand_clash_free);
    hash.bool(value.declared_chirality_preserved);
    hash.bool(value.inside_declared_pocket);
    hash.bool(value.element_vdw_ligand_overlap_free);
    hash.bool(value.element_vdw_receptor_overlap_free);
}

fn hash_measurements(hash: &mut CanonicalHash, value: NativeFixed64ValidityMeasurements) {
    hash.usize(value.atom_count);
    hash.f64(value.rotation_orthogonality_max_error);
    hash.f64(value.rotation_determinant);
    hash.f64(value.max_bond_length_delta_angstrom);
    hash.f64(value.minimum_ligand_nonbonded_distance_angstrom);
    hash.usize(value.evaluated_ligand_nonbonded_pair_count);
    hash.usize(value.excluded_ligand_pair_count);
    hash.f64(value.minimum_receptor_ligand_distance_angstrom);
    hash.usize(value.evaluated_receptor_ligand_pair_count);
    hash.f64(value.minimum_declared_chiral_volume);
    hash.usize(value.declared_chirality_center_count);
    hash.f64(value.maximum_pocket_center_distance_angstrom);
    hash.usize(value.element_vdw_ligand_pair_count);
    hash.usize(value.element_vdw_ligand_severe_overlap_count);
    hash.f64(value.element_vdw_ligand_minimum_distance_angstrom);
    hash.f64(value.element_vdw_ligand_minimum_ratio);
    hash.usize(value.element_vdw_receptor_candidate_pair_count);
    hash.usize(value.element_vdw_receptor_full_cartesian_pair_count);
    hash.usize(value.element_vdw_receptor_cell_count);
    hash.usize(value.element_vdw_receptor_severe_overlap_count);
    hash.f64(value.element_vdw_receptor_minimum_distance_angstrom);
    hash.f64(value.element_vdw_receptor_minimum_ratio);
}

fn result_sha256(value: &NativeFixed64ValidityResult) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_VALIDITY_RESULT_SCHEMA_ID);
    hash.digest(value.proposal_record_receipt_sha256);
    hash.digest(value.scorer_row_receipt_sha256);
    hash.digest(value.coordinate_sha256);
    hash.digest(value.authority_input_receipt_sha256);
    hash.digest(value.context_receipt_sha256);
    hash.digest(value.config_receipt_sha256);
    hash.byte(value.backend.tag());
    hash.digest(value.backend_receipt_sha256);
    hash.digest(value.contact_policy_sha256);
    hash_checks(&mut hash, value.checks);
    hash_measurements(&mut hash, value.measurements);
    hash.usize(value.blockers.len());
    for blocker in &value.blockers {
        hash.byte(blocker.tag());
    }
    hash.bool(value.complete);
    hash.bool(value.valid_within_evaluated_scope);
    hash.finish()
}

fn failure_sha256(value: &NativeFixed64ValidityFailure) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_VALIDITY_FAILURE_SCHEMA_ID);
    hash.digest(value.proposal_record_receipt_sha256);
    hash.digest(value.scorer_row_receipt_sha256);
    hash.option(value.upstream_scorer_failure_code, |hash, code| {
        hash.string(code.id());
    });
    hash.byte(value.failure_code.tag());
    hash.usize(value.observed_count);
    hash.finish()
}

fn row_sha256(value: &NativeFixed64ValidityRow) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_VALIDITY_ROW_SCHEMA_ID);
    hash.usize(value.slot_index);
    hash.digest(value.proposal_record_receipt_sha256);
    hash.digest(value.scorer_row_receipt_sha256);
    hash.byte(match value.status {
        NativeFixed64ValidityRowStatus::Evaluated => 0,
        NativeFixed64ValidityRowStatus::UpstreamScorerFailure => 1,
        NativeFixed64ValidityRowStatus::TypedFailure => 2,
    });
    hash.option(value.result.as_ref(), |hash, result| {
        hash.digest(result.receipt_sha256);
    });
    hash.option(value.failure.as_ref(), |hash, failure| {
        hash.digest(failure.receipt_sha256);
    });
    hash.finish()
}

fn batch_sha256(value: &NativeFixed64ValidityBatch) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_FIXED64_VALIDITY_BATCH_SCHEMA_ID);
    hash.digest(value.scorer_batch.receipt_sha256());
    hash.digest(value.context.receipt_sha256);
    hash.usize(value.rows.len());
    for row in value.rows.iter() {
        hash.digest(row.receipt_sha256);
    }
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

const fn config_error(message: &'static str) -> NativeFixed64ValidityError {
    NativeFixed64ValidityError::new(NativeFixed64ValidityErrorCode::InvalidConfig, message)
}

const fn context_error(message: &'static str) -> NativeFixed64ValidityError {
    NativeFixed64ValidityError::new(NativeFixed64ValidityErrorCode::InvalidContext, message)
}

const fn cross_wired(message: &'static str) -> NativeFixed64ValidityError {
    NativeFixed64ValidityError::new(NativeFixed64ValidityErrorCode::UpstreamCrossWired, message)
}

const fn internal(message: &'static str) -> NativeFixed64ValidityError {
    NativeFixed64ValidityError::new(NativeFixed64ValidityErrorCode::InternalInvariant, message)
}
