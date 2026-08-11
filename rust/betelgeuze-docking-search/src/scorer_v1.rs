use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    native_fixed64_coordinate_sha256, Fixed64GeometricBatch, Fixed64GeometricDecision,
    Fixed64GeometricStatus, Fixed64PlacementErrorCode, Fixed64ProposalFailureCode,
    Fixed64ProposalRecord, Fixed64ProposalStatus, Vec3, FIXED64_CANDIDATE_COUNT,
    FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM, FIXED64_MAX_LIGAND_ATOMS, FIXED64_MAX_RECEPTOR_ATOMS,
    FIXED64_MAX_VDW_RADIUS_ANGSTROM, FIXED64_MIN_VDW_RADIUS_ANGSTROM,
};

pub const NATIVE_SCORER_V1_CONFIG_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_scorer_v1_config/1.0.0";
pub const NATIVE_SCORER_V1_CONTEXT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_scorer_v1_context/1.0.0";
pub const NATIVE_SCORER_V1_TERMS_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_scorer_v1_terms/1.0.0";
pub const NATIVE_SCORER_V1_FAILURE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_scorer_v1_failure/1.0.0";
pub const NATIVE_SCORER_V1_ROW_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_scorer_v1_row/1.0.0";
pub const NATIVE_SCORER_V1_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_scorer_v1_batch/1.0.0";
pub const NATIVE_SCORER_V1_SCORE_ID: &str = "betelgeuze.engine_v2_chemistry_pose_scorer/1.0.0";
pub const NATIVE_SCORER_V1_ALGORITHM_ID: &str =
    "sparse_typed_lj_charge_hbond_hydrophobic_geometry_torsion_strain/1.0.0";
pub const NATIVE_SCORER_V1_PAIR_TRAVERSAL_ID: &str =
    "ligand_index_then_neighbor_cell_xyz_then_receptor_index";
pub const NATIVE_SCORER_V1_MAX_RECEPTOR_CANDIDATE_PAIRS: usize = 4_000_000;
pub const NATIVE_SCORER_V1_MAX_LIGAND_PAIR_CHECKS: usize = 250_000;
pub const NATIVE_SCORER_V1_MAX_ROTORS: usize = FIXED64_MAX_LIGAND_ATOMS;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeScorerV1Backend {
    RustCpu,
    HipSafe,
    HipFast,
    CppCpuQualification,
}

impl NativeScorerV1Backend {
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
pub struct NativeScorerV1Config {
    weights: [f64; 8],
    electrostatic_dielectric: f64,
    pair_cutoff_angstrom: f64,
    hbond_distance_max_angstrom: f64,
    polar_burial_distance_angstrom: f64,
    max_receptor_candidate_pairs: usize,
    max_ligand_pair_checks: usize,
    receipt_sha256: [u8; 32],
}

impl Default for NativeScorerV1Config {
    fn default() -> Self {
        let mut value = Self {
            weights: [1.0, 0.35, 1.5, 0.6, 0.4, 0.15, 0.5, 0.05],
            electrostatic_dielectric: 4.0,
            pair_cutoff_angstrom: 8.0,
            hbond_distance_max_angstrom: 3.0,
            polar_burial_distance_angstrom: 4.5,
            max_receptor_candidate_pairs: 1_000_000,
            max_ligand_pair_checks: NATIVE_SCORER_V1_MAX_LIGAND_PAIR_CHECKS,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = config_sha256(&value);
        value
    }
}

impl NativeScorerV1Config {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        weights: [f64; 8],
        electrostatic_dielectric: f64,
        pair_cutoff_angstrom: f64,
        hbond_distance_max_angstrom: f64,
        polar_burial_distance_angstrom: f64,
        max_receptor_candidate_pairs: usize,
        max_ligand_pair_checks: usize,
    ) -> Result<Self, NativeScorerV1Error> {
        let mut value = Self {
            weights,
            electrostatic_dielectric,
            pair_cutoff_angstrom,
            hbond_distance_max_angstrom,
            polar_burial_distance_angstrom,
            max_receptor_candidate_pairs,
            max_ligand_pair_checks,
            receipt_sha256: [0; 32],
        };
        validate_config(&value)?;
        value.receipt_sha256 = config_sha256(&value);
        Ok(value)
    }

    #[must_use]
    pub const fn weights(&self) -> [f64; 8] {
        self.weights
    }

    #[must_use]
    pub const fn electrostatic_dielectric(&self) -> f64 {
        self.electrostatic_dielectric
    }

    #[must_use]
    pub const fn pair_cutoff_angstrom(&self) -> f64 {
        self.pair_cutoff_angstrom
    }

    #[must_use]
    pub const fn hbond_distance_max_angstrom(&self) -> f64 {
        self.hbond_distance_max_angstrom
    }

    #[must_use]
    pub const fn polar_burial_distance_angstrom(&self) -> f64 {
        self.polar_burial_distance_angstrom
    }

    #[must_use]
    pub const fn max_receptor_candidate_pairs(&self) -> usize {
        self.max_receptor_candidate_pairs
    }

    #[must_use]
    pub const fn max_ligand_pair_checks(&self) -> usize {
        self.max_ligand_pair_checks
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        validate_config(self).is_ok() && config_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeScorerV1Atom {
    pub charge_elementary: f64,
    pub vdw_radius_angstrom: f64,
    pub epsilon_kcal_per_mol: f64,
    pub hydrophobic: bool,
    pub acceptor: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct NativeScorerV1Donor {
    pub donor_atom_index: usize,
    pub hydrogen_atom_index: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeScorerV1ErrorCode {
    InvalidConfig,
    InvalidContext,
    UpstreamCrossWired,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeScorerV1Error {
    code: NativeScorerV1ErrorCode,
    message: &'static str,
}

impl NativeScorerV1Error {
    const fn new(code: NativeScorerV1ErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeScorerV1ErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeScorerV1Error {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native ScorerV1: {}", self.message)
    }
}

impl std::error::Error for NativeScorerV1Error {}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeScorerV1Context {
    authority_input_receipt_sha256: [u8; 32],
    receptor_system_sha256: [u8; 32],
    ligand_system_sha256: [u8; 32],
    backend: NativeScorerV1Backend,
    backend_receipt_sha256: [u8; 32],
    receptor_coordinates_angstrom: Vec<Vec3>,
    receptor_atoms: Vec<NativeScorerV1Atom>,
    ligand_reference_coordinates_angstrom: Vec<Vec3>,
    ligand_atoms: Vec<NativeScorerV1Atom>,
    receptor_donors: Vec<NativeScorerV1Donor>,
    ligand_donors: Vec<NativeScorerV1Donor>,
    ligand_exclusions: Vec<[usize; 2]>,
    rotor_quads: Vec<[usize; 4]>,
    reference_dihedrals_radians: Vec<f64>,
    reference_internal_vdw: f64,
    reference_ligand_pair_count: usize,
    pocket_center_angstrom: Vec3,
    pocket_radius_angstrom: f64,
    config: NativeScorerV1Config,
    receptor_cells: BTreeMap<(i64, i64, i64), Vec<usize>>,
    receptor_donor_by_hydrogen: Vec<Option<usize>>,
    ligand_donor_by_hydrogen: Vec<Option<usize>>,
    ligand_donor_heavy_mask: Vec<bool>,
    ligand_exclusion_set: BTreeSet<(usize, usize)>,
    receipt_sha256: [u8; 32],
}

impl NativeScorerV1Context {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        authority_input_receipt_sha256: [u8; 32],
        receptor_system_sha256: [u8; 32],
        ligand_system_sha256: [u8; 32],
        backend: NativeScorerV1Backend,
        backend_receipt_sha256: [u8; 32],
        receptor_coordinates_angstrom: Vec<Vec3>,
        receptor_atoms: Vec<NativeScorerV1Atom>,
        ligand_reference_coordinates_angstrom: Vec<Vec3>,
        ligand_atoms: Vec<NativeScorerV1Atom>,
        receptor_donors: Vec<NativeScorerV1Donor>,
        ligand_donors: Vec<NativeScorerV1Donor>,
        ligand_exclusions: Vec<[usize; 2]>,
        rotor_quads: Vec<[usize; 4]>,
        pocket_center_angstrom: Vec3,
        pocket_radius_angstrom: f64,
        config: NativeScorerV1Config,
    ) -> Result<Self, NativeScorerV1Error> {
        let mut value = Self {
            authority_input_receipt_sha256,
            receptor_system_sha256,
            ligand_system_sha256,
            backend,
            backend_receipt_sha256,
            receptor_coordinates_angstrom,
            receptor_atoms,
            ligand_reference_coordinates_angstrom,
            ligand_atoms,
            receptor_donors,
            ligand_donors,
            ligand_exclusions,
            rotor_quads,
            reference_dihedrals_radians: Vec::new(),
            reference_internal_vdw: 0.0,
            reference_ligand_pair_count: 0,
            pocket_center_angstrom,
            pocket_radius_angstrom,
            config,
            receptor_cells: BTreeMap::new(),
            receptor_donor_by_hydrogen: Vec::new(),
            ligand_donor_by_hydrogen: Vec::new(),
            ligand_donor_heavy_mask: Vec::new(),
            ligand_exclusion_set: BTreeSet::new(),
            receipt_sha256: [0; 32],
        };
        validate_context_inputs(&value)?;
        let derived = derive_context_state(&value)?;
        value.reference_dihedrals_radians = derived.reference_dihedrals_radians;
        value.reference_internal_vdw = derived.reference_internal_vdw;
        value.reference_ligand_pair_count = derived.reference_ligand_pair_count;
        value.receptor_cells = derived.receptor_cells;
        value.receptor_donor_by_hydrogen = derived.receptor_donor_by_hydrogen;
        value.ligand_donor_by_hydrogen = derived.ligand_donor_by_hydrogen;
        value.ligand_donor_heavy_mask = derived.ligand_donor_heavy_mask;
        value.ligand_exclusion_set = derived.ligand_exclusion_set;
        value.receipt_sha256 = context_sha256(&value);
        Ok(value)
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
    pub const fn backend(&self) -> NativeScorerV1Backend {
        self.backend
    }

    #[must_use]
    pub const fn backend_receipt_sha256(&self) -> [u8; 32] {
        self.backend_receipt_sha256
    }

    #[must_use]
    pub fn receptor_coordinates_angstrom(&self) -> &[Vec3] {
        &self.receptor_coordinates_angstrom
    }

    #[must_use]
    pub fn receptor_atoms(&self) -> &[NativeScorerV1Atom] {
        &self.receptor_atoms
    }

    #[must_use]
    pub fn ligand_reference_coordinates_angstrom(&self) -> &[Vec3] {
        &self.ligand_reference_coordinates_angstrom
    }

    #[must_use]
    pub fn ligand_atoms(&self) -> &[NativeScorerV1Atom] {
        &self.ligand_atoms
    }

    #[must_use]
    pub fn ligand_exclusions(&self) -> &[[usize; 2]] {
        &self.ligand_exclusions
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
    pub fn config(&self) -> &NativeScorerV1Config {
        &self.config
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        if validate_context_inputs(self).is_err() {
            return false;
        }
        let Ok(derived) = derive_context_state(self) else {
            return false;
        };
        self.reference_dihedrals_radians == derived.reference_dihedrals_radians
            && self.reference_internal_vdw == derived.reference_internal_vdw
            && self.reference_ligand_pair_count == derived.reference_ligand_pair_count
            && self.receptor_cells == derived.receptor_cells
            && self.receptor_donor_by_hydrogen == derived.receptor_donor_by_hydrogen
            && self.ligand_donor_by_hydrogen == derived.ligand_donor_by_hydrogen
            && self.ligand_donor_heavy_mask == derived.ligand_donor_heavy_mask
            && self.ligand_exclusion_set == derived.ligand_exclusion_set
            && context_sha256(self) == self.receipt_sha256
    }

    pub fn score_coordinates(
        &self,
        coordinates_angstrom: &[Vec3],
    ) -> Result<NativeScorerV1KernelOutcome, NativeScorerV1Error> {
        Ok(self
            .prepare_rust_cpu_kernel()?
            .score_coordinates(coordinates_angstrom))
    }

    pub fn prepare_rust_cpu_kernel(
        &self,
    ) -> Result<NativeScorerV1RustCpuKernel<'_>, NativeScorerV1Error> {
        if !self.has_valid_receipt() {
            return Err(context_error("ScorerV1 context receipt is invalid"));
        }
        if self.backend != NativeScorerV1Backend::RustCpu {
            return Err(cross_wired(
                "Rust ScorerV1 kernel cannot claim an unexecuted backend",
            ));
        }
        Ok(NativeScorerV1RustCpuKernel { context: self })
    }
}

#[derive(Clone, Copy)]
pub struct NativeScorerV1RustCpuKernel<'context> {
    context: &'context NativeScorerV1Context,
}

impl NativeScorerV1RustCpuKernel<'_> {
    #[must_use]
    pub fn score_coordinates(&self, coordinates_angstrom: &[Vec3]) -> NativeScorerV1KernelOutcome {
        match score_kernel(coordinates_angstrom, self.context) {
            Ok(terms) => NativeScorerV1KernelOutcome::Scored(terms),
            Err(failure) => NativeScorerV1KernelOutcome::TypedFailure(failure),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
struct DerivedContextState {
    reference_dihedrals_radians: Vec<f64>,
    reference_internal_vdw: f64,
    reference_ligand_pair_count: usize,
    receptor_cells: BTreeMap<(i64, i64, i64), Vec<usize>>,
    receptor_donor_by_hydrogen: Vec<Option<usize>>,
    ligand_donor_by_hydrogen: Vec<Option<usize>>,
    ligand_donor_heavy_mask: Vec<bool>,
    ligand_exclusion_set: BTreeSet<(usize, usize)>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeScorerV1Terms {
    proposal_record_receipt_sha256: [u8; 32],
    proposal_sha256: [u8; 32],
    coordinate_sha256: [u8; 32],
    admission_decision_receipt_sha256: [u8; 32],
    authority_input_receipt_sha256: [u8; 32],
    context_receipt_sha256: [u8; 32],
    config_receipt_sha256: [u8; 32],
    backend: NativeScorerV1Backend,
    backend_receipt_sha256: [u8; 32],
    typed_vdw: f64,
    electrostatics: f64,
    directional_hbond: f64,
    hydrophobic_contact: f64,
    desolvation_proxy: f64,
    torsion_energy: f64,
    ligand_strain: f64,
    weak_pocket_prior: f64,
    total_score: f64,
    receptor_candidate_pair_count: usize,
    ligand_pair_count: usize,
    hbond_count: usize,
    hydrophobic_contact_count: usize,
    buried_polar_count: usize,
    receipt_sha256: [u8; 32],
}

impl NativeScorerV1Terms {
    #[must_use]
    pub const fn proposal_record_receipt_sha256(&self) -> [u8; 32] {
        self.proposal_record_receipt_sha256
    }

    #[must_use]
    pub const fn proposal_sha256(&self) -> [u8; 32] {
        self.proposal_sha256
    }

    #[must_use]
    pub const fn coordinate_sha256(&self) -> [u8; 32] {
        self.coordinate_sha256
    }

    #[must_use]
    pub const fn admission_decision_receipt_sha256(&self) -> [u8; 32] {
        self.admission_decision_receipt_sha256
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
    pub const fn backend(&self) -> NativeScorerV1Backend {
        self.backend
    }

    #[must_use]
    pub const fn backend_receipt_sha256(&self) -> [u8; 32] {
        self.backend_receipt_sha256
    }

    #[must_use]
    pub const fn weighted_terms(&self) -> [f64; 8] {
        [
            self.typed_vdw,
            self.electrostatics,
            self.directional_hbond,
            self.hydrophobic_contact,
            self.desolvation_proxy,
            self.torsion_energy,
            self.ligand_strain,
            self.weak_pocket_prior,
        ]
    }

    #[must_use]
    pub const fn typed_vdw(&self) -> f64 {
        self.typed_vdw
    }

    #[must_use]
    pub const fn electrostatics(&self) -> f64 {
        self.electrostatics
    }

    #[must_use]
    pub const fn directional_hbond(&self) -> f64 {
        self.directional_hbond
    }

    #[must_use]
    pub const fn hydrophobic_contact(&self) -> f64 {
        self.hydrophobic_contact
    }

    #[must_use]
    pub const fn desolvation_proxy(&self) -> f64 {
        self.desolvation_proxy
    }

    #[must_use]
    pub const fn torsion_energy(&self) -> f64 {
        self.torsion_energy
    }

    #[must_use]
    pub const fn ligand_strain(&self) -> f64 {
        self.ligand_strain
    }

    #[must_use]
    pub const fn weak_pocket_prior(&self) -> f64 {
        self.weak_pocket_prior
    }

    #[must_use]
    pub const fn total_score(&self) -> f64 {
        self.total_score
    }

    #[must_use]
    pub const fn receptor_candidate_pair_count(&self) -> usize {
        self.receptor_candidate_pair_count
    }

    #[must_use]
    pub const fn ligand_pair_count(&self) -> usize {
        self.ligand_pair_count
    }

    #[must_use]
    pub const fn hbond_count(&self) -> usize {
        self.hbond_count
    }

    #[must_use]
    pub const fn hydrophobic_contact_count(&self) -> usize {
        self.hydrophobic_contact_count
    }

    #[must_use]
    pub const fn buried_polar_count(&self) -> usize {
        self.buried_polar_count
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let terms = self.weighted_terms();
        terms.iter().all(|value| value.is_finite())
            && self.total_score.is_finite()
            && (terms.into_iter().sum::<f64>() - self.total_score).abs() <= 1.0e-12
            && terms_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeScorerV1FailureCode {
    ProposalGenerationFailure,
    SeverePenetrationRejected,
    InvalidCandidateCoordinates,
    ReceptorCandidatePairCapacityExceeded,
    LigandPairCapacityExceeded,
    DegenerateRotorGeometry,
    NonfiniteScore,
}

impl NativeScorerV1FailureCode {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::ProposalGenerationFailure => "proposal_generation_failure",
            Self::SeverePenetrationRejected => "severe_penetration_rejected",
            Self::InvalidCandidateCoordinates => "invalid_candidate_coordinates",
            Self::ReceptorCandidatePairCapacityExceeded => {
                "receptor_candidate_pair_capacity_exceeded"
            }
            Self::LigandPairCapacityExceeded => "ligand_pair_capacity_exceeded",
            Self::DegenerateRotorGeometry => "degenerate_rotor_geometry",
            Self::NonfiniteScore => "nonfinite_score",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeScorerV1KernelTerms {
    weighted_terms: [f64; 8],
    total_score: f64,
    receptor_candidate_pair_count: usize,
    ligand_pair_count: usize,
    hbond_count: usize,
    hydrophobic_contact_count: usize,
    buried_polar_count: usize,
}

impl NativeScorerV1KernelTerms {
    #[must_use]
    pub const fn weighted_terms(&self) -> [f64; 8] {
        self.weighted_terms
    }

    #[must_use]
    pub const fn total_score(&self) -> f64 {
        self.total_score
    }

    #[must_use]
    pub const fn receptor_candidate_pair_count(&self) -> usize {
        self.receptor_candidate_pair_count
    }

    #[must_use]
    pub const fn ligand_pair_count(&self) -> usize {
        self.ligand_pair_count
    }

    #[must_use]
    pub const fn hbond_count(&self) -> usize {
        self.hbond_count
    }

    #[must_use]
    pub const fn hydrophobic_contact_count(&self) -> usize {
        self.hydrophobic_contact_count
    }

    #[must_use]
    pub const fn buried_polar_count(&self) -> usize {
        self.buried_polar_count
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeScorerV1KernelFailure {
    failure_code: NativeScorerV1FailureCode,
    receptor_candidate_pair_count: usize,
    ligand_pair_count: usize,
}

impl NativeScorerV1KernelFailure {
    #[must_use]
    pub const fn failure_code(self) -> NativeScorerV1FailureCode {
        self.failure_code
    }

    #[must_use]
    pub const fn receptor_candidate_pair_count(self) -> usize {
        self.receptor_candidate_pair_count
    }

    #[must_use]
    pub const fn ligand_pair_count(self) -> usize {
        self.ligand_pair_count
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum NativeScorerV1KernelOutcome {
    Scored(NativeScorerV1KernelTerms),
    TypedFailure(NativeScorerV1KernelFailure),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NativeScorerV1Failure {
    proposal_record_receipt_sha256: [u8; 32],
    admission_decision_receipt_sha256: [u8; 32],
    upstream_proposal_failure_code: Option<Fixed64ProposalFailureCode>,
    failure_code: NativeScorerV1FailureCode,
    receptor_candidate_pair_count: usize,
    ligand_pair_count: usize,
    receipt_sha256: [u8; 32],
}

impl NativeScorerV1Failure {
    #[must_use]
    pub const fn upstream_proposal_failure_code(&self) -> Option<Fixed64ProposalFailureCode> {
        self.upstream_proposal_failure_code
    }

    #[must_use]
    pub const fn failure_code(&self) -> NativeScorerV1FailureCode {
        self.failure_code
    }

    #[must_use]
    pub const fn receptor_candidate_pair_count(&self) -> usize {
        self.receptor_candidate_pair_count
    }

    #[must_use]
    pub const fn ligand_pair_count(&self) -> usize {
        self.ligand_pair_count
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
pub enum NativeScorerV1RowStatus {
    Scored,
    TypedFailure,
}

impl NativeScorerV1RowStatus {
    #[must_use]
    pub const fn id(self) -> &'static str {
        match self {
            Self::Scored => "scored",
            Self::TypedFailure => "typed_failure",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeScorerV1Row {
    slot_index: usize,
    proposal_record_receipt_sha256: [u8; 32],
    admission_decision_receipt_sha256: [u8; 32],
    status: NativeScorerV1RowStatus,
    terms: Option<NativeScorerV1Terms>,
    failure: Option<NativeScorerV1Failure>,
    receipt_sha256: [u8; 32],
}

impl NativeScorerV1Row {
    #[must_use]
    pub const fn slot_index(&self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn status(&self) -> NativeScorerV1RowStatus {
        self.status
    }

    #[must_use]
    pub const fn terms(&self) -> Option<&NativeScorerV1Terms> {
        self.terms.as_ref()
    }

    #[must_use]
    pub const fn failure(&self) -> Option<&NativeScorerV1Failure> {
        self.failure.as_ref()
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let content_valid = match self.status {
            NativeScorerV1RowStatus::Scored => {
                self.terms
                    .as_ref()
                    .is_some_and(NativeScorerV1Terms::has_valid_receipt)
                    && self.failure.is_none()
            }
            NativeScorerV1RowStatus::TypedFailure => {
                self.terms.is_none()
                    && self
                        .failure
                        .as_ref()
                        .is_some_and(NativeScorerV1Failure::has_valid_receipt)
            }
        };
        content_valid && row_sha256(self) == self.receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeScorerV1Batch {
    admission: Fixed64GeometricBatch,
    context: NativeScorerV1Context,
    rows: [NativeScorerV1Row; FIXED64_CANDIDATE_COUNT],
    receipt_sha256: [u8; 32],
}

impl NativeScorerV1Batch {
    #[must_use]
    pub fn admission(&self) -> &Fixed64GeometricBatch {
        &self.admission
    }

    #[must_use]
    pub fn context(&self) -> &NativeScorerV1Context {
        &self.context
    }

    #[must_use]
    pub fn rows(&self) -> &[NativeScorerV1Row; FIXED64_CANDIDATE_COUNT] {
        &self.rows
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn scored_count(&self) -> usize {
        self.rows
            .iter()
            .filter(|row| row.status == NativeScorerV1RowStatus::Scored)
            .count()
    }

    #[must_use]
    pub fn typed_failure_count(&self) -> usize {
        FIXED64_CANDIDATE_COUNT - self.scored_count()
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
        if validate_bound_inputs(&self.admission, &self.context).is_err() {
            return false;
        }
        let Ok(expected_rows) = build_rows(&self.admission, &self.context) else {
            return false;
        };
        self.rows == expected_rows && batch_sha256(self) == self.receipt_sha256
    }
}

pub fn score_native_fixed64_scorer_v1(
    admission: Fixed64GeometricBatch,
    context: NativeScorerV1Context,
) -> Result<NativeScorerV1Batch, NativeScorerV1Error> {
    validate_bound_inputs(&admission, &context)?;
    let rows = build_rows(&admission, &context)?;
    let mut value = NativeScorerV1Batch {
        admission,
        context,
        rows,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = batch_sha256(&value);
    Ok(value)
}

fn validate_config(value: &NativeScorerV1Config) -> Result<(), NativeScorerV1Error> {
    if value
        .weights
        .iter()
        .any(|weight| !weight.is_finite() || !(0.0..=100.0).contains(weight))
        || !value.electrostatic_dielectric.is_finite()
        || !(1.0..=100.0).contains(&value.electrostatic_dielectric)
        || !value.pair_cutoff_angstrom.is_finite()
        || !(3.0..=20.0).contains(&value.pair_cutoff_angstrom)
        || !value.hbond_distance_max_angstrom.is_finite()
        || !(2.0..=4.0).contains(&value.hbond_distance_max_angstrom)
        || !value.polar_burial_distance_angstrom.is_finite()
        || !(3.0..=8.0).contains(&value.polar_burial_distance_angstrom)
        || value.pair_cutoff_angstrom
            < value
                .hbond_distance_max_angstrom
                .max(value.polar_burial_distance_angstrom)
        || value.max_receptor_candidate_pairs == 0
        || value.max_receptor_candidate_pairs > NATIVE_SCORER_V1_MAX_RECEPTOR_CANDIDATE_PAIRS
        || value.max_ligand_pair_checks == 0
        || value.max_ligand_pair_checks > NATIVE_SCORER_V1_MAX_LIGAND_PAIR_CHECKS
    {
        return Err(config_error(
            "ScorerV1 configuration is outside frozen bounds",
        ));
    }
    Ok(())
}

fn validate_context_inputs(value: &NativeScorerV1Context) -> Result<(), NativeScorerV1Error> {
    if [
        value.authority_input_receipt_sha256,
        value.receptor_system_sha256,
        value.ligand_system_sha256,
        value.backend_receipt_sha256,
    ]
    .contains(&[0; 32])
    {
        return Err(context_error("ScorerV1 identity digest is missing"));
    }
    if !value.config.has_valid_receipt() {
        return Err(context_error("ScorerV1 config receipt is invalid"));
    }
    native_fixed64_coordinate_sha256(&value.receptor_coordinates_angstrom)
        .map_err(|_| context_error("receptor coordinates are invalid"))?;
    native_fixed64_coordinate_sha256(&value.ligand_reference_coordinates_angstrom)
        .map_err(|_| context_error("ligand reference coordinates are invalid"))?;
    if value.receptor_coordinates_angstrom.len() > FIXED64_MAX_RECEPTOR_ATOMS
        || value.ligand_reference_coordinates_angstrom.len() > FIXED64_MAX_LIGAND_ATOMS
        || value.receptor_coordinates_angstrom.len() != value.receptor_atoms.len()
        || value.ligand_reference_coordinates_angstrom.len() != value.ligand_atoms.len()
    {
        return Err(context_error("ScorerV1 atom denominators disagree"));
    }
    value
        .receptor_atoms
        .iter()
        .chain(&value.ligand_atoms)
        .try_for_each(validate_atom)?;
    validate_donors(&value.receptor_donors, value.receptor_atoms.len())?;
    validate_donors(&value.ligand_donors, value.ligand_atoms.len())?;
    if value
        .ligand_exclusions
        .windows(2)
        .any(|rows| rows[0] >= rows[1])
        || value
            .ligand_exclusions
            .iter()
            .any(|[first, second]| first >= second || *second >= value.ligand_atoms.len())
    {
        return Err(context_error(
            "ligand exclusions are duplicated or noncanonical",
        ));
    }
    if value.rotor_quads.len() > NATIVE_SCORER_V1_MAX_ROTORS
        || value
            .rotor_quads
            .iter()
            .any(|quad| quad.iter().any(|index| *index >= value.ligand_atoms.len()))
        || value
            .rotor_quads
            .iter()
            .copied()
            .collect::<BTreeSet<_>>()
            .len()
            != value.rotor_quads.len()
    {
        return Err(context_error("rotor quads are invalid or duplicated"));
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
    Ok(())
}

fn validate_atom(value: &NativeScorerV1Atom) -> Result<(), NativeScorerV1Error> {
    if !value.charge_elementary.is_finite()
        || !value.vdw_radius_angstrom.is_finite()
        || !(FIXED64_MIN_VDW_RADIUS_ANGSTROM..=FIXED64_MAX_VDW_RADIUS_ANGSTROM)
            .contains(&value.vdw_radius_angstrom)
        || !value.epsilon_kcal_per_mol.is_finite()
        || value.epsilon_kcal_per_mol <= 0.0
        || value.epsilon_kcal_per_mol > 100.0
    {
        return Err(context_error("ScorerV1 atom parameters are invalid"));
    }
    Ok(())
}

fn validate_donors(
    values: &[NativeScorerV1Donor],
    atom_count: usize,
) -> Result<(), NativeScorerV1Error> {
    if values.windows(2).any(|rows| rows[0] >= rows[1])
        || values.iter().any(|row| {
            row.donor_atom_index == row.hydrogen_atom_index
                || row.donor_atom_index >= atom_count
                || row.hydrogen_atom_index >= atom_count
        })
        || values
            .iter()
            .map(|row| row.hydrogen_atom_index)
            .collect::<BTreeSet<_>>()
            .len()
            != values.len()
    {
        return Err(context_error("ScorerV1 donor rows are invalid"));
    }
    Ok(())
}

fn derive_context_state(
    value: &NativeScorerV1Context,
) -> Result<DerivedContextState, NativeScorerV1Error> {
    let ligand_exclusion_set = value
        .ligand_exclusions
        .iter()
        .map(|row| (row[0], row[1]))
        .collect::<BTreeSet<_>>();
    let reference_dihedrals_radians = value
        .rotor_quads
        .iter()
        .map(|quad| {
            dihedral(&value.ligand_reference_coordinates_angstrom, *quad)
                .map_err(|_| context_error("reference rotor geometry is degenerate"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    let (reference_internal_vdw, reference_ligand_pair_count) = ligand_internal_vdw(
        &value.ligand_reference_coordinates_angstrom,
        &value.ligand_atoms,
        &ligand_exclusion_set,
        value.config.max_ligand_pair_checks,
    )
    .map_err(|_| context_error("reference ligand pair capacity is invalid"))?;
    if !reference_internal_vdw.is_finite() {
        return Err(context_error("reference internal vdW is non-finite"));
    }
    let mut receptor_cells = BTreeMap::new();
    for (index, coordinate) in value.receptor_coordinates_angstrom.iter().enumerate() {
        receptor_cells
            .entry(cell_key(*coordinate, value.config.pair_cutoff_angstrom))
            .or_insert_with(Vec::new)
            .push(index);
    }
    let receptor_donor_by_hydrogen = donor_map(&value.receptor_donors, value.receptor_atoms.len());
    let ligand_donor_by_hydrogen = donor_map(&value.ligand_donors, value.ligand_atoms.len());
    let mut ligand_donor_heavy_mask = vec![false; value.ligand_atoms.len()];
    for donor in &value.ligand_donors {
        ligand_donor_heavy_mask[donor.donor_atom_index] = true;
    }
    Ok(DerivedContextState {
        reference_dihedrals_radians,
        reference_internal_vdw,
        reference_ligand_pair_count,
        receptor_cells,
        receptor_donor_by_hydrogen,
        ligand_donor_by_hydrogen,
        ligand_donor_heavy_mask,
        ligand_exclusion_set,
    })
}

fn donor_map(values: &[NativeScorerV1Donor], atom_count: usize) -> Vec<Option<usize>> {
    let mut result = vec![None; atom_count];
    for donor in values {
        result[donor.hydrogen_atom_index] = Some(donor.donor_atom_index);
    }
    result
}

fn validate_bound_inputs(
    admission: &Fixed64GeometricBatch,
    context: &NativeScorerV1Context,
) -> Result<(), NativeScorerV1Error> {
    if !admission.has_valid_receipt() || !context.has_valid_receipt() {
        return Err(cross_wired(
            "admission or scorer context receipt is invalid",
        ));
    }
    if context.backend != NativeScorerV1Backend::RustCpu {
        return Err(cross_wired(
            "Rust ScorerV1 entry point cannot claim an unexecuted backend",
        ));
    }
    let Some(proposals) = admission.proposal_batch() else {
        return Err(cross_wired(
            "ScorerV1 requires complete proposal producer evidence",
        ));
    };
    let exact = proposals.allocation().inventory().exact_v11_source();
    if context.authority_input_receipt_sha256 != exact.source_receipt_sha256
        || context.receptor_coordinates_angstrom
            != admission.input().receptor_coordinates_angstrom()
        || context.receptor_atoms.len() != admission.input().receptor_vdw_radii_angstrom().len()
        || context
            .receptor_atoms
            .iter()
            .map(|atom| atom.vdw_radius_angstrom)
            .ne(admission
                .input()
                .receptor_vdw_radii_angstrom()
                .iter()
                .copied())
        || context.ligand_atoms.len() != admission.input().ligand_vdw_radii_angstrom().len()
        || context
            .ligand_atoms
            .iter()
            .map(|atom| atom.vdw_radius_angstrom)
            .ne(admission
                .input()
                .ligand_vdw_radii_angstrom()
                .iter()
                .copied())
    {
        return Err(cross_wired(
            "ScorerV1 context is cross-wired to another exact system",
        ));
    }
    Ok(())
}

fn build_rows(
    admission: &Fixed64GeometricBatch,
    context: &NativeScorerV1Context,
) -> Result<[NativeScorerV1Row; FIXED64_CANDIDATE_COUNT], NativeScorerV1Error> {
    let proposals = admission
        .proposal_batch()
        .ok_or_else(|| cross_wired("proposal evidence is absent"))?;
    let mut rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for index in 0..FIXED64_CANDIDATE_COUNT {
        let decision = &admission.decisions()[index];
        let proposal = &proposals.records()[index];
        if decision.proposal_record_receipt_sha256() != Some(proposal.receipt_sha256()) {
            return Err(cross_wired("admission decision lost its proposal binding"));
        }
        rows.push(build_row(index, decision, proposal, admission, context)?);
    }
    rows.try_into()
        .map_err(|_| internal("ScorerV1 row denominator changed"))
}

fn build_row(
    slot_index: usize,
    decision: &Fixed64GeometricDecision,
    proposal: &Fixed64ProposalRecord,
    admission: &Fixed64GeometricBatch,
    context: &NativeScorerV1Context,
) -> Result<NativeScorerV1Row, NativeScorerV1Error> {
    if decision.slot_index() != slot_index || proposal.slot_index() != slot_index {
        return Err(cross_wired("ScorerV1 slot index is cross-wired"));
    }
    if decision.status() != Fixed64GeometricStatus::Accepted || !decision.rank_eligible() {
        let failure_code = match decision.status() {
            Fixed64GeometricStatus::TypedGenerationFailure => {
                NativeScorerV1FailureCode::ProposalGenerationFailure
            }
            Fixed64GeometricStatus::SeverePenetrationRejected => {
                NativeScorerV1FailureCode::SeverePenetrationRejected
            }
            Fixed64GeometricStatus::Accepted => {
                return Err(cross_wired(
                    "accepted admission row is unexpectedly rank-ineligible",
                ));
            }
        };
        return Ok(failure_row(
            slot_index,
            proposal,
            decision,
            failure_code,
            0,
            0,
        ));
    }
    if proposal.status() != Fixed64ProposalStatus::Generated {
        return Err(cross_wired(
            "accepted admission row is not a generated proposal",
        ));
    }
    let coordinates = admission
        .candidate_coordinates_angstrom(slot_index)
        .ok_or_else(|| cross_wired("accepted ScorerV1 row lacks coordinates"))?;
    match score_one(coordinates, proposal, decision, context) {
        Ok(terms) => {
            let mut row = NativeScorerV1Row {
                slot_index,
                proposal_record_receipt_sha256: proposal.receipt_sha256(),
                admission_decision_receipt_sha256: decision.receipt_sha256(),
                status: NativeScorerV1RowStatus::Scored,
                terms: Some(terms),
                failure: None,
                receipt_sha256: [0; 32],
            };
            row.receipt_sha256 = row_sha256(&row);
            Ok(row)
        }
        Err(failure) => Ok(failure_row(
            slot_index,
            proposal,
            decision,
            failure.failure_code,
            failure.receptor_candidate_pair_count,
            failure.ligand_pair_count,
        )),
    }
}

fn failure_row(
    slot_index: usize,
    proposal: &Fixed64ProposalRecord,
    decision: &Fixed64GeometricDecision,
    failure_code: NativeScorerV1FailureCode,
    receptor_candidate_pair_count: usize,
    ligand_pair_count: usize,
) -> NativeScorerV1Row {
    let mut failure = NativeScorerV1Failure {
        proposal_record_receipt_sha256: proposal.receipt_sha256(),
        admission_decision_receipt_sha256: decision.receipt_sha256(),
        upstream_proposal_failure_code: decision.proposal_failure_code(),
        failure_code,
        receptor_candidate_pair_count,
        ligand_pair_count,
        receipt_sha256: [0; 32],
    };
    failure.receipt_sha256 = failure_sha256(&failure);
    let mut row = NativeScorerV1Row {
        slot_index,
        proposal_record_receipt_sha256: proposal.receipt_sha256(),
        admission_decision_receipt_sha256: decision.receipt_sha256(),
        status: NativeScorerV1RowStatus::TypedFailure,
        terms: None,
        failure: Some(failure),
        receipt_sha256: [0; 32],
    };
    row.receipt_sha256 = row_sha256(&row);
    row
}

fn score_one(
    pose: &[Vec3],
    proposal: &Fixed64ProposalRecord,
    decision: &Fixed64GeometricDecision,
    context: &NativeScorerV1Context,
) -> Result<NativeScorerV1Terms, NativeScorerV1KernelFailure> {
    let kernel = score_kernel(pose, context)?;
    let proposal_sha256 = proposal.source_proposal_sha256().ok_or_else(|| {
        candidate_failure(
            NativeScorerV1FailureCode::InvalidCandidateCoordinates,
            kernel.receptor_candidate_pair_count,
            kernel.ligand_pair_count,
        )
    })?;
    let coordinate_sha256 = proposal.source_coordinate_sha256().ok_or_else(|| {
        candidate_failure(
            NativeScorerV1FailureCode::InvalidCandidateCoordinates,
            kernel.receptor_candidate_pair_count,
            kernel.ligand_pair_count,
        )
    })?;
    let weighted = kernel.weighted_terms;
    let mut terms = NativeScorerV1Terms {
        proposal_record_receipt_sha256: proposal.receipt_sha256(),
        proposal_sha256,
        coordinate_sha256,
        admission_decision_receipt_sha256: decision.receipt_sha256(),
        authority_input_receipt_sha256: context.authority_input_receipt_sha256,
        context_receipt_sha256: context.receipt_sha256,
        config_receipt_sha256: context.config.receipt_sha256,
        backend: context.backend,
        backend_receipt_sha256: context.backend_receipt_sha256,
        typed_vdw: weighted[0],
        electrostatics: weighted[1],
        directional_hbond: weighted[2],
        hydrophobic_contact: weighted[3],
        desolvation_proxy: weighted[4],
        torsion_energy: weighted[5],
        ligand_strain: weighted[6],
        weak_pocket_prior: weighted[7],
        total_score: kernel.total_score,
        receptor_candidate_pair_count: kernel.receptor_candidate_pair_count,
        ligand_pair_count: kernel.ligand_pair_count,
        hbond_count: kernel.hbond_count,
        hydrophobic_contact_count: kernel.hydrophobic_contact_count,
        buried_polar_count: kernel.buried_polar_count,
        receipt_sha256: [0; 32],
    };
    terms.receipt_sha256 = terms_sha256(&terms);
    Ok(terms)
}

fn score_kernel(
    pose: &[Vec3],
    context: &NativeScorerV1Context,
) -> Result<NativeScorerV1KernelTerms, NativeScorerV1KernelFailure> {
    if pose.len() != context.ligand_atoms.len() || native_fixed64_coordinate_sha256(pose).is_err() {
        return Err(candidate_failure(
            NativeScorerV1FailureCode::InvalidCandidateCoordinates,
            0,
            0,
        ));
    }
    let mut typed_vdw_raw = 0.0;
    let mut electro_raw = 0.0;
    let mut hbond_raw = 0.0;
    let mut hydrophobic_raw = 0.0;
    let mut hbond_count = 0usize;
    let mut hydrophobic_contact_count = 0usize;
    let mut receptor_candidate_pair_count = 0usize;
    let mut polar_buried = vec![false; pose.len()];
    let mut polar_satisfied = vec![false; pose.len()];
    for (ligand_index, coordinate) in pose.iter().copied().enumerate() {
        let center = cell_key(coordinate, context.config.pair_cutoff_angstrom);
        for x in (center.0 - 1)..=(center.0 + 1) {
            for y in (center.1 - 1)..=(center.1 + 1) {
                for z in (center.2 - 1)..=(center.2 + 1) {
                    let Some(receptor_indices) = context.receptor_cells.get(&(x, y, z)) else {
                        continue;
                    };
                    for receptor_index in receptor_indices.iter().copied() {
                        receptor_candidate_pair_count += 1;
                        if receptor_candidate_pair_count
                            > context.config.max_receptor_candidate_pairs
                        {
                            return Err(candidate_failure(
                                NativeScorerV1FailureCode::ReceptorCandidatePairCapacityExceeded,
                                receptor_candidate_pair_count,
                                0,
                            ));
                        }
                        let distance = scorer_norm(
                            coordinate.minus(context.receptor_coordinates_angstrom[receptor_index]),
                        );
                        if distance > context.config.pair_cutoff_angstrom {
                            continue;
                        }
                        let ligand_atom = context.ligand_atoms[ligand_index];
                        let receptor_atom = context.receptor_atoms[receptor_index];
                        let sigma =
                            ligand_atom.vdw_radius_angstrom + receptor_atom.vdw_radius_angstrom;
                        typed_vdw_raw += typed_lj(
                            ligand_atom.epsilon_kcal_per_mol,
                            receptor_atom.epsilon_kcal_per_mol,
                            sigma,
                            distance,
                        );
                        electro_raw += ligand_atom.charge_elementary
                            * receptor_atom.charge_elementary
                            / (context.config.electrostatic_dielectric * distance.max(0.5));
                        if ligand_atom.hydrophobic
                            && receptor_atom.hydrophobic
                            && distance <= 1.25 * sigma
                        {
                            hydrophobic_contact_count += 1;
                            hydrophobic_raw += (1.0 - distance / (1.25 * sigma)).max(0.0);
                        }
                        if (ligand_atom.acceptor || context.ligand_donor_heavy_mask[ligand_index])
                            && distance <= context.config.polar_burial_distance_angstrom
                        {
                            polar_buried[ligand_index] = true;
                        }
                        if let Some(donor) = context.ligand_donor_by_hydrogen[ligand_index] {
                            if receptor_atom.acceptor {
                                let reward = hbond_reward(
                                    pose[donor],
                                    pose[ligand_index],
                                    context.receptor_coordinates_angstrom[receptor_index],
                                    context.config.hbond_distance_max_angstrom,
                                );
                                if reward > 0.0 {
                                    hbond_raw += reward;
                                    hbond_count += 1;
                                    polar_satisfied[donor] = true;
                                }
                            }
                        }
                        if let Some(donor) = context.receptor_donor_by_hydrogen[receptor_index] {
                            if ligand_atom.acceptor {
                                let reward = hbond_reward(
                                    context.receptor_coordinates_angstrom[donor],
                                    context.receptor_coordinates_angstrom[receptor_index],
                                    pose[ligand_index],
                                    context.config.hbond_distance_max_angstrom,
                                );
                                if reward > 0.0 {
                                    hbond_raw += reward;
                                    hbond_count += 1;
                                    polar_satisfied[ligand_index] = true;
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    let (current_internal_vdw, ligand_pair_count) = ligand_internal_vdw(
        pose,
        &context.ligand_atoms,
        &context.ligand_exclusion_set,
        context.config.max_ligand_pair_checks,
    )
    .map_err(|count| {
        candidate_failure(
            NativeScorerV1FailureCode::LigandPairCapacityExceeded,
            receptor_candidate_pair_count,
            count,
        )
    })?;
    let ligand_strain_raw = (current_internal_vdw - context.reference_internal_vdw).max(0.0);
    let mut torsion_raw = 0.0;
    for (quad, reference) in context
        .rotor_quads
        .iter()
        .zip(&context.reference_dihedrals_radians)
    {
        let observed = dihedral(pose, *quad).map_err(|_| {
            candidate_failure(
                NativeScorerV1FailureCode::DegenerateRotorGeometry,
                receptor_candidate_pair_count,
                ligand_pair_count,
            )
        })?;
        let delta = (observed - reference)
            .sin()
            .atan2((observed - reference).cos());
        torsion_raw += 0.5 * (1.0 - (3.0 * delta).cos());
    }
    let inverse_count = 1.0 / pose.len() as f64;
    let centroid = pose
        .iter()
        .copied()
        .fold(Vec3::new(0.0, 0.0, 0.0), Vec3::plus)
        .scale(inverse_count);
    let pocket_raw = (scorer_norm(centroid.minus(context.pocket_center_angstrom))
        / context.pocket_radius_angstrom)
        .powi(2);
    let buried_polar_count = polar_buried.iter().filter(|value| **value).count();
    let desolvation_raw = polar_buried
        .iter()
        .zip(&polar_satisfied)
        .filter(|(buried, satisfied)| **buried && !**satisfied)
        .count() as f64;
    let raw = [
        typed_vdw_raw,
        electro_raw,
        -hbond_raw,
        -hydrophobic_raw,
        desolvation_raw,
        torsion_raw,
        ligand_strain_raw,
        pocket_raw,
    ];
    let weighted =
        std::array::from_fn::<_, 8, _>(|index| raw[index] * context.config.weights[index]);
    let total_score = weighted.into_iter().sum::<f64>();
    if weighted
        .iter()
        .chain(std::iter::once(&total_score))
        .any(|value| !value.is_finite())
    {
        return Err(candidate_failure(
            NativeScorerV1FailureCode::NonfiniteScore,
            receptor_candidate_pair_count,
            ligand_pair_count,
        ));
    }
    Ok(NativeScorerV1KernelTerms {
        weighted_terms: weighted,
        total_score,
        receptor_candidate_pair_count,
        ligand_pair_count,
        hbond_count,
        hydrophobic_contact_count,
        buried_polar_count,
    })
}

fn ligand_internal_vdw(
    coordinates: &[Vec3],
    atoms: &[NativeScorerV1Atom],
    exclusions: &BTreeSet<(usize, usize)>,
    maximum_pair_count: usize,
) -> Result<(f64, usize), usize> {
    let mut value = 0.0;
    let mut count = 0usize;
    for first in 0..coordinates.len() {
        for second in (first + 1)..coordinates.len() {
            if exclusions.contains(&(first, second)) {
                continue;
            }
            count += 1;
            if count > maximum_pair_count {
                return Err(count);
            }
            value += typed_lj(
                atoms[first].epsilon_kcal_per_mol,
                atoms[second].epsilon_kcal_per_mol,
                atoms[first].vdw_radius_angstrom + atoms[second].vdw_radius_angstrom,
                scorer_norm(coordinates[first].minus(coordinates[second])),
            );
        }
    }
    Ok((value, count))
}

fn typed_lj(first_epsilon: f64, second_epsilon: f64, sigma: f64, distance: f64) -> f64 {
    if distance <= 1.0e-8 {
        return 1.0e6;
    }
    let ratio = (sigma / distance).min(2.0);
    let sixth = ratio.powi(6);
    (first_epsilon * second_epsilon).sqrt() * (sixth * sixth - 2.0 * sixth)
}

fn hbond_reward(donor: Vec3, hydrogen: Vec3, acceptor: Vec3, cutoff: f64) -> f64 {
    let distance = scorer_norm(hydrogen.minus(acceptor));
    if distance > cutoff || distance <= 1.0e-8 {
        return 0.0;
    }
    let first = donor.minus(hydrogen);
    let second = acceptor.minus(hydrogen);
    let denominator = scorer_norm(first) * scorer_norm(second);
    if denominator <= 1.0e-12 {
        return 0.0;
    }
    let cosine = first.dot(second) / denominator;
    let angular = ((-cosine - 0.5) / 0.5).clamp(0.0, 1.0);
    let radial = (1.0 - distance / cutoff).max(0.0);
    angular * radial
}

fn dihedral(coordinates: &[Vec3], atoms: [usize; 4]) -> Result<f64, ()> {
    let first = coordinates[atoms[0]];
    let second = coordinates[atoms[1]];
    let third = coordinates[atoms[2]];
    let fourth = coordinates[atoms[3]];
    let middle = third.minus(second);
    let middle_norm = scorer_norm(middle);
    if middle_norm <= 1.0e-12 {
        return Err(());
    }
    let axis = middle.scale(1.0 / middle_norm);
    let mut left = first.minus(second);
    let mut right = fourth.minus(third);
    left = left.minus(axis.scale(left.dot(axis)));
    right = right.minus(axis.scale(right.dot(axis)));
    let left_norm = scorer_norm(left);
    let right_norm = scorer_norm(right);
    if left_norm.min(right_norm) <= 1.0e-12 {
        return Err(());
    }
    left = left.scale(1.0 / left_norm);
    right = right.scale(1.0 / right_norm);
    Ok(left.cross(right).dot(axis).atan2(left.dot(right)))
}

fn scorer_norm(value: Vec3) -> f64 {
    value.dot(value).sqrt()
}

fn cell_key(value: Vec3, cell_size: f64) -> (i64, i64, i64) {
    (
        (value.x / cell_size).floor() as i64,
        (value.y / cell_size).floor() as i64,
        (value.z / cell_size).floor() as i64,
    )
}

const fn candidate_failure(
    failure_code: NativeScorerV1FailureCode,
    receptor_candidate_pair_count: usize,
    ligand_pair_count: usize,
) -> NativeScorerV1KernelFailure {
    NativeScorerV1KernelFailure {
        failure_code,
        receptor_candidate_pair_count,
        ligand_pair_count,
    }
}

fn config_sha256(value: &NativeScorerV1Config) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_scorer_v1_config/native-v1");
    hash.string(NATIVE_SCORER_V1_CONFIG_SCHEMA_ID);
    hash.string(NATIVE_SCORER_V1_ALGORITHM_ID);
    for weight in value.weights {
        hash.f64(weight);
    }
    hash.f64(value.electrostatic_dielectric);
    hash.f64(value.pair_cutoff_angstrom);
    hash.f64(value.hbond_distance_max_angstrom);
    hash.f64(value.polar_burial_distance_angstrom);
    hash.usize(value.max_receptor_candidate_pairs);
    hash.usize(value.max_ligand_pair_checks);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn context_sha256(value: &NativeScorerV1Context) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_scorer_v1_context/native-v1");
    hash.string(NATIVE_SCORER_V1_CONTEXT_SCHEMA_ID);
    hash.digest(value.authority_input_receipt_sha256);
    hash.digest(value.receptor_system_sha256);
    hash.digest(value.ligand_system_sha256);
    hash.byte(value.backend.tag());
    hash.digest(value.backend_receipt_sha256);
    hash_coordinates(&mut hash, &value.receptor_coordinates_angstrom);
    hash_atoms(&mut hash, &value.receptor_atoms);
    hash_coordinates(&mut hash, &value.ligand_reference_coordinates_angstrom);
    hash_atoms(&mut hash, &value.ligand_atoms);
    hash_donors(&mut hash, &value.receptor_donors);
    hash_donors(&mut hash, &value.ligand_donors);
    hash.usize(value.ligand_exclusions.len());
    for [first, second] in &value.ligand_exclusions {
        hash.usize(*first);
        hash.usize(*second);
    }
    hash.usize(value.rotor_quads.len());
    for quad in &value.rotor_quads {
        for index in quad {
            hash.usize(*index);
        }
    }
    hash.usize(value.reference_dihedrals_radians.len());
    for angle in &value.reference_dihedrals_radians {
        hash.f64(*angle);
    }
    hash.f64(value.reference_internal_vdw);
    hash.usize(value.reference_ligand_pair_count);
    hash.vec3(value.pocket_center_angstrom);
    hash.f64(value.pocket_radius_angstrom);
    hash.digest(value.config.receipt_sha256);
    hash.string(NATIVE_SCORER_V1_PAIR_TRAVERSAL_ID);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn hash_coordinates(hash: &mut CanonicalHash, values: &[Vec3]) {
    hash.usize(values.len());
    for value in values {
        hash.vec3(*value);
    }
}

fn hash_atoms(hash: &mut CanonicalHash, values: &[NativeScorerV1Atom]) {
    hash.usize(values.len());
    for atom in values {
        hash.f64(atom.charge_elementary);
        hash.f64(atom.vdw_radius_angstrom);
        hash.f64(atom.epsilon_kcal_per_mol);
        hash.bool(atom.hydrophobic);
        hash.bool(atom.acceptor);
    }
}

fn hash_donors(hash: &mut CanonicalHash, values: &[NativeScorerV1Donor]) {
    hash.usize(values.len());
    for donor in values {
        hash.usize(donor.donor_atom_index);
        hash.usize(donor.hydrogen_atom_index);
    }
}

fn terms_sha256(value: &NativeScorerV1Terms) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_scorer_v1_terms/native-v1");
    hash.string(NATIVE_SCORER_V1_TERMS_SCHEMA_ID);
    hash.string(NATIVE_SCORER_V1_SCORE_ID);
    hash.string(NATIVE_SCORER_V1_ALGORITHM_ID);
    hash.digest(value.proposal_record_receipt_sha256);
    hash.digest(value.proposal_sha256);
    hash.digest(value.coordinate_sha256);
    hash.digest(value.admission_decision_receipt_sha256);
    hash.digest(value.authority_input_receipt_sha256);
    hash.digest(value.context_receipt_sha256);
    hash.digest(value.config_receipt_sha256);
    hash.byte(value.backend.tag());
    hash.digest(value.backend_receipt_sha256);
    for term in value.weighted_terms() {
        hash.f64(term);
    }
    hash.f64(value.total_score);
    hash.usize(value.receptor_candidate_pair_count);
    hash.usize(value.ligand_pair_count);
    hash.usize(value.hbond_count);
    hash.usize(value.hydrophobic_contact_count);
    hash.usize(value.buried_polar_count);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn failure_sha256(value: &NativeScorerV1Failure) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_scorer_v1_failure/native-v1");
    hash.string(NATIVE_SCORER_V1_FAILURE_SCHEMA_ID);
    hash.digest(value.proposal_record_receipt_sha256);
    hash.digest(value.admission_decision_receipt_sha256);
    hash.option(value.upstream_proposal_failure_code, |hash, code| {
        proposal_failure_code_sha256(hash, code)
    });
    hash.byte(match value.failure_code {
        NativeScorerV1FailureCode::ProposalGenerationFailure => 0,
        NativeScorerV1FailureCode::SeverePenetrationRejected => 1,
        NativeScorerV1FailureCode::InvalidCandidateCoordinates => 2,
        NativeScorerV1FailureCode::ReceptorCandidatePairCapacityExceeded => 3,
        NativeScorerV1FailureCode::LigandPairCapacityExceeded => 4,
        NativeScorerV1FailureCode::DegenerateRotorGeometry => 5,
        NativeScorerV1FailureCode::NonfiniteScore => 6,
    });
    hash.usize(value.receptor_candidate_pair_count);
    hash.usize(value.ligand_pair_count);
    hash.bool(true);
    hash.finish()
}

fn row_sha256(value: &NativeScorerV1Row) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_scorer_v1_row/native-v1");
    hash.string(NATIVE_SCORER_V1_ROW_SCHEMA_ID);
    hash.usize(value.slot_index);
    hash.digest(value.proposal_record_receipt_sha256);
    hash.digest(value.admission_decision_receipt_sha256);
    hash.byte(match value.status {
        NativeScorerV1RowStatus::Scored => 0,
        NativeScorerV1RowStatus::TypedFailure => 1,
    });
    hash.option(value.terms.as_ref(), |hash, terms| {
        hash.digest(terms.receipt_sha256)
    });
    hash.option(value.failure.as_ref(), |hash, failure| {
        hash.digest(failure.receipt_sha256)
    });
    hash.bool(true);
    hash.finish()
}

fn batch_sha256(value: &NativeScorerV1Batch) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.native_scorer_v1_batch/native-v1");
    hash.string(NATIVE_SCORER_V1_BATCH_SCHEMA_ID);
    hash.digest(value.admission.receipt_sha256());
    hash.digest(value.context.receipt_sha256);
    hash.usize(value.rows.len());
    for row in &value.rows {
        hash.digest(row.receipt_sha256);
    }
    hash.usize(value.scored_count());
    hash.usize(value.typed_failure_count());
    hash.bool(true);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn proposal_failure_code_sha256(hash: &mut CanonicalHash, value: Fixed64ProposalFailureCode) {
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
            hash.byte(placement_error_tag(code));
        }
    }
}

const fn placement_error_tag(value: Fixed64PlacementErrorCode) -> u8 {
    match value {
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
    }
}

const fn config_error(message: &'static str) -> NativeScorerV1Error {
    NativeScorerV1Error::new(NativeScorerV1ErrorCode::InvalidConfig, message)
}

const fn context_error(message: &'static str) -> NativeScorerV1Error {
    NativeScorerV1Error::new(NativeScorerV1ErrorCode::InvalidContext, message)
}

const fn cross_wired(message: &'static str) -> NativeScorerV1Error {
    NativeScorerV1Error::new(NativeScorerV1ErrorCode::UpstreamCrossWired, message)
}

const fn internal(message: &'static str) -> NativeScorerV1Error {
    NativeScorerV1Error::new(NativeScorerV1ErrorCode::InternalInvariant, message)
}
