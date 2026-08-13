//! Result-independent, rederivable scientific metrics for one fixed64 receipt.
//!
//! This module is deliberately downstream of proposal generation, geometric
//! admission, scoring, validity, and ranking.  It cannot change allocation or
//! return a candidate to the product path.  The full 64-row denominator and a
//! frozen 2.0 Angstrom direct heavy-atom RMSD definition are retained in every
//! receipt.

use std::collections::{BTreeMap, BTreeSet};

use betelgeuze_docking_search::{
    Fixed64Lane, FIXED64_CANDIDATE_COUNT, FIXED64_LANE_RANGES, FIXED64_MAX_LIGAND_ATOMS,
};
use betelgeuze_sys as sys;

use crate::docking::{CanonicalHasher, Fixed64AuthorityDisposition, Fixed64PipelineReceipt};
use crate::{Error, ErrorCode, PositionSoa, PositionSoaOwned, Result};

pub const FIXED64_LANE_METRICS_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_lane_metrics/1.0.0";
pub const FIXED64_LANE_METRICS_REFERENCE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_lane_metrics_reference/1.0.0";
pub const FIXED64_LANE_METRICS_OBSERVATION_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_lane_metric_observation/1.0.0";
pub const FIXED64_ORACLE_RMSD_THRESHOLD_ANGSTROM: f64 = 2.0;
pub const FIXED64_MAX_SYMMETRY_PERMUTATIONS: usize = 1024;

const MISSING_SLOT_INDEX: u32 = u32::MAX;
const CONTROL_LANES: [Fixed64Lane; 3] = [
    Fixed64Lane::PocketCenteredControls,
    Fixed64Lane::UniformSourceControls,
    Fixed64Lane::PairedRetainedControls,
];
const CONFORMER_ORIENTATION_PAIRS: [(usize, usize); 8] = [
    (24, 36),
    (25, 37),
    (26, 38),
    (27, 39),
    (28, 40),
    (29, 41),
    (30, 42),
    (31, 43),
];

// floor(log2(n) * 2^32), generated once for n in 0..=64.  Receipt entropy
// remains an exact rational over this frozen table instead of depending on a
// platform libm implementation.
const LOG2_Q32: [u64; 65] = [
    0,
    0,
    4_294_967_296,
    6_807_362_106,
    8_589_934_592,
    9_972_605_231,
    11_102_329_402,
    12_057_497_579,
    12_884_901_888,
    13_614_724_212,
    14_267_572_527,
    14_858_145_665,
    15_397_296_698,
    15_893_267_570,
    16_352_464_875,
    16_779_967_337,
    17_179_869_184,
    17_555_519_227,
    17_909_691_508,
    18_244_709_746,
    18_562_539_823,
    18_864_859_684,
    19_153_112_961,
    19_428_550_663,
    19_692_263_994,
    19_945_210_462,
    20_188_234_866,
    20_422_086_318,
    20_647_432_171,
    20_864_869_499,
    21_074_934_633,
    21_278_111_131,
    21_474_836_480,
    21_665_507_771,
    21_850_486_523,
    22_030_102_810,
    22_204_658_804,
    22_374_431_835,
    22_539_677_042,
    22_700_629_676,
    22_857_507_119,
    23_010_510_646,
    23_159_826_980,
    23_305_629_661,
    23_448_080_257,
    23_587_329_443,
    23_723_517_959,
    23_856_777_461,
    23_987_231_290,
    24_114_995_157,
    24_240_177_758,
    24_362_881_333,
    24_483_202_162,
    24_601_231_026,
    24_717_053_614,
    24_830_750_896,
    24_942_399_467,
    25_052_071_852,
    25_159_836_795,
    25_265_759_511,
    25_369_901_929,
    25_472_322_906,
    25_573_078_427,
    25_672_221_790,
    25_769_803_776,
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64MetricRate {
    pub numerator: u64,
    pub denominator: u64,
}

impl Fixed64MetricRate {
    #[must_use]
    pub fn value(self) -> Option<f64> {
        (self.denominator != 0).then(|| self.numerator as f64 / self.denominator as f64)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64LaneMetricsReference {
    pub case_id: String,
    pub reference_pose_source_receipt_sha256: [u8; 32],
    pub prepared_ligand_topology_sha256: [u8; 32],
    pub reference_coordinates: PositionSoaOwned,
    pub heavy_atom_mask: Vec<u8>,
    /// Mapping direction is reference-position -> candidate-position.
    pub symmetry_permutations: Vec<Vec<u32>>,
    pub receipt_sha256: [u8; 32],
}

impl Fixed64LaneMetricsReference {
    pub fn new(
        case_id: impl Into<String>,
        reference_pose_source_receipt_sha256: [u8; 32],
        prepared_ligand_topology_sha256: [u8; 32],
        reference_coordinates: PositionSoa<'_>,
        heavy_atom_mask: &[u8],
        symmetry_permutations: &[Vec<u32>],
    ) -> Result<Self> {
        let case_id = case_id.into();
        require_case_id(&case_id)?;
        require_digest(
            reference_pose_source_receipt_sha256,
            "reference pose source receipt",
        )?;
        require_digest(prepared_ligand_topology_sha256, "prepared ligand topology")?;
        let atom_count = validate_reference_coordinates(reference_coordinates)?;
        validate_heavy_atom_mask(heavy_atom_mask, atom_count)?;
        let symmetry_permutations =
            canonical_symmetry_permutations(symmetry_permutations, heavy_atom_mask)?;
        let mut value = Self {
            case_id,
            reference_pose_source_receipt_sha256,
            prepared_ligand_topology_sha256,
            reference_coordinates: PositionSoaOwned {
                x_angstrom: reference_coordinates.x_angstrom.to_vec(),
                y_angstrom: reference_coordinates.y_angstrom.to_vec(),
                z_angstrom: reference_coordinates.z_angstrom.to_vec(),
            },
            heavy_atom_mask: heavy_atom_mask.to_vec(),
            symmetry_permutations,
            receipt_sha256: [0; 32],
        };
        value.receipt_sha256 = reference_sha256(&value);
        Ok(value)
    }

    fn validate(&self) -> Result<()> {
        require_case_id(&self.case_id)?;
        require_digest(
            self.reference_pose_source_receipt_sha256,
            "reference pose source receipt",
        )?;
        require_digest(
            self.prepared_ligand_topology_sha256,
            "prepared ligand topology",
        )?;
        let coordinates = PositionSoa::new(
            &self.reference_coordinates.x_angstrom,
            &self.reference_coordinates.y_angstrom,
            &self.reference_coordinates.z_angstrom,
        );
        let atom_count = validate_reference_coordinates(coordinates)?;
        validate_heavy_atom_mask(&self.heavy_atom_mask, atom_count)?;
        let canonical =
            canonical_symmetry_permutations(&self.symmetry_permutations, &self.heavy_atom_mask)?;
        if canonical != self.symmetry_permutations {
            return Err(invalid("symmetry permutations are not canonical"));
        }
        if self.receipt_sha256 != reference_sha256(self) {
            return Err(abi_mismatch("lane-metrics reference receipt changed"));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64LaneMetricObservation {
    pub slot_index: u32,
    pub lane: Fixed64Lane,
    pub coordinate_ready: bool,
    pub final_coordinate_sha256: [u8; 32],
    pub orientation_available: bool,
    pub canonical_orientation_sha256: [u8; 32],
    pub initial_severe_penetration: bool,
    pub post_refinement_severe_penetration: bool,
    pub exact_valid: bool,
    pub rmsd_evaluated: bool,
    pub symmetry_aware_direct_heavy_atom_rmsd_angstrom: f64,
    pub symmetry_permutation_index: u32,
    pub oracle_2a: bool,
    pub valid_oracle_2a: bool,
    pub stable_rank: u32,
    pub stable_valid_rank: u32,
    pub receipt_sha256: [u8; 32],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64CoordinateEntropy {
    pub coordinate_ready_count: u64,
    pub distinct_coordinate_count: u64,
    pub entropy_q32_numerator: u64,
    pub entropy_q32_denominator: u64,
    pub maximum_entropy_q32: u64,
}

impl Fixed64CoordinateEntropy {
    #[must_use]
    pub fn entropy_bits(self) -> f64 {
        self.entropy_q32_numerator as f64 / self.entropy_q32_denominator as f64 / 4_294_967_296.0
    }

    #[must_use]
    pub fn normalized(self) -> Option<f64> {
        (self.maximum_entropy_q32 != 0).then(|| {
            self.entropy_q32_numerator as f64
                / self.entropy_q32_denominator as f64
                / self.maximum_entropy_q32 as f64
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64LaneMetricSummary {
    pub lane: Fixed64Lane,
    pub first_slot_index: u32,
    pub slot_count: u64,
    pub generated_count: u64,
    pub typed_failure_count: u64,
    pub coordinate_ready_count: u64,
    pub exact_coordinate_unique_count: u64,
    pub exact_coordinate_duplicate_count: u64,
    pub cluster_eligible_count: u64,
    pub unique_valid_pose_cluster_count: u64,
    pub orientation_available_count: u64,
    pub unique_orientation_count: u64,
    pub orientation_duplicate_count: u64,
    pub initial_geometric_evaluated_count: u64,
    pub initial_severe_penetration_count: u64,
    pub post_geometric_evaluated_count: u64,
    pub post_severe_penetration_count: u64,
    pub exact_valid_count: u64,
    pub oracle_2a_count: u64,
    pub valid_oracle_2a_count: u64,
    pub exact_coordinate_unique_rate: Fixed64MetricRate,
    pub unique_valid_pose_rate: Fixed64MetricRate,
    pub orientation_duplicate_rate: Fixed64MetricRate,
    pub initial_severe_penetration_rate: Fixed64MetricRate,
    pub post_severe_penetration_rate: Fixed64MetricRate,
    pub exact_valid_contribution: Fixed64MetricRate,
    pub oracle_contribution: Fixed64MetricRate,
    pub valid_oracle_contribution: Fixed64MetricRate,
    pub incremental_oracle_case_recovery: bool,
    pub incremental_valid_oracle_case_recovery: bool,
    pub coordinate_entropy: Fixed64CoordinateEntropy,
    pub receipt_sha256: [u8; 32],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64ConformerOrientationInteraction {
    pub predeclared_pair_count: u64,
    pub both_coordinate_ready_count: u64,
    pub conformer_lower_rmsd_count: u64,
    pub source_lower_rmsd_count: u64,
    pub rmsd_tie_count: u64,
    pub conformer_oracle_gain_count: u64,
    pub conformer_oracle_loss_count: u64,
    pub both_oracle_count: u64,
    pub neither_oracle_count: u64,
    pub conformer_valid_oracle_gain_count: u64,
    pub conformer_valid_oracle_loss_count: u64,
    pub receipt_sha256: [u8; 32],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fixed64OracleFailureClass {
    Success,
    ProposalFailure,
    ValidityFailure,
    RankingFailure,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64OracleSelectionSummary {
    pub proposal_oracle_slot_index: u32,
    pub proposal_oracle_rmsd_angstrom: f64,
    pub proposal_oracle_success: bool,
    pub valid_proposal_oracle_slot_index: u32,
    pub valid_proposal_oracle_rmsd_angstrom: f64,
    pub valid_proposal_oracle_success: bool,
    pub selected_top1_slot_index: u32,
    pub selected_top1_rmsd_evaluated: bool,
    pub selected_top1_rmsd_angstrom: f64,
    pub selected_top1_exact_valid: bool,
    pub selected_top1_oracle_success: bool,
    pub selected_top5_oracle_present: bool,
    pub selected_top5_valid_oracle_present: bool,
    pub failure_class: Fixed64OracleFailureClass,
    pub receipt_sha256: [u8; 32],
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64LaneMetricsReceipt {
    pub reference: Fixed64LaneMetricsReference,
    pub pipeline_source_bundle_receipt_sha256: [u8; 32],
    pub pipeline_cluster_batch_receipt_sha256: [u8; 32],
    pub scientific_projection_sha256: [u8; 32],
    pub candidate_denominator: u64,
    pub rmsd_threshold_angstrom: f64,
    pub observations: Vec<Fixed64LaneMetricObservation>,
    pub lane_summaries: Vec<Fixed64LaneMetricSummary>,
    pub global_coordinate_entropy: Fixed64CoordinateEntropy,
    pub oracle_selection: Fixed64OracleSelectionSummary,
    pub conformer_orientation_interaction: Fixed64ConformerOrientationInteraction,
    pub authority: Fixed64AuthorityDisposition,
    pub result_dependent_allocation_consumed: bool,
    pub metrics_used_to_change_rank: bool,
    pub product_execution_authorized: bool,
    pub public_or_scientific_claim_authorized: bool,
    pub decision_sha256: [u8; 32],
    pub receipt_sha256: [u8; 32],
}

impl Fixed64LaneMetricsReceipt {
    pub fn build(
        pipeline: &Fixed64PipelineReceipt,
        reference: Fixed64LaneMetricsReference,
    ) -> Result<Self> {
        reference.validate()?;
        let projection = pipeline.scientific_projection()?;
        if projection.candidate_denominator != FIXED64_CANDIDATE_COUNT
            || projection.candidate_rows.len() != FIXED64_CANDIDATE_COUNT
        {
            return Err(abi_mismatch(
                "lane metrics require the complete 64-row denominator",
            ));
        }
        if reference.reference_coordinates.x_angstrom.len() != projection.ligand_atom_count {
            return Err(invalid(
                "lane-metrics reference atom count does not match the pipeline ligand",
            ));
        }
        require_non_authoritative(projection.authority)?;
        require_digest(
            pipeline.receipts.source_bundle_receipt_sha256,
            "pipeline source bundle receipt",
        )?;
        require_digest(
            pipeline.receipts.cluster_batch_receipt_sha256,
            "pipeline cluster batch receipt",
        )?;

        let observations = projection
            .candidate_rows
            .iter()
            .enumerate()
            .map(|(slot, row)| {
                let expected_lane = lane_for_slot(slot).ok_or_else(|| {
                    abi_mismatch(format!("slot {slot} is outside the fixed64 lane ranges"))
                })?;
                let observed_lane = lane_from_raw(row.lane).ok_or_else(|| {
                    abi_mismatch(format!("slot {slot} has unknown lane {}", row.lane))
                })?;
                if expected_lane != observed_lane || row.slot_index as usize != slot {
                    return Err(abi_mismatch(format!(
                        "lane-metrics row {slot} is not aligned with the frozen allocation"
                    )));
                }
                derive_observation(&projection, &reference, slot, observed_lane)
            })
            .collect::<Result<Vec<_>>>()?;

        let global_exact_valid_count = observations.iter().filter(|row| row.exact_valid).count();
        let global_oracle_count = observations.iter().filter(|row| row.oracle_2a).count();
        let global_valid_oracle_count = observations
            .iter()
            .filter(|row| row.valid_oracle_2a)
            .count();
        let control_oracle = observations
            .iter()
            .any(|row| CONTROL_LANES.contains(&row.lane) && row.oracle_2a);
        let control_valid_oracle = observations
            .iter()
            .any(|row| CONTROL_LANES.contains(&row.lane) && row.valid_oracle_2a);

        let lane_summaries = FIXED64_LANE_RANGES
            .iter()
            .map(|(lane, first, last)| {
                derive_lane_summary(
                    *lane,
                    *first,
                    *last,
                    &observations,
                    &projection,
                    global_exact_valid_count,
                    global_oracle_count,
                    global_valid_oracle_count,
                    control_oracle,
                    control_valid_oracle,
                )
            })
            .collect::<Vec<_>>();
        let global_coordinate_entropy = coordinate_entropy(&observations);
        let oracle_selection = oracle_selection_summary(&observations, &projection);
        let conformer_orientation_interaction = conformer_orientation_interaction(&observations);

        let mut value = Self {
            reference,
            pipeline_source_bundle_receipt_sha256: pipeline.receipts.source_bundle_receipt_sha256,
            pipeline_cluster_batch_receipt_sha256: pipeline.receipts.cluster_batch_receipt_sha256,
            scientific_projection_sha256: projection.sha256,
            candidate_denominator: FIXED64_CANDIDATE_COUNT as u64,
            rmsd_threshold_angstrom: FIXED64_ORACLE_RMSD_THRESHOLD_ANGSTROM,
            observations,
            lane_summaries,
            global_coordinate_entropy,
            oracle_selection,
            conformer_orientation_interaction,
            authority: projection.authority,
            result_dependent_allocation_consumed: false,
            metrics_used_to_change_rank: false,
            product_execution_authorized: false,
            public_or_scientific_claim_authorized: false,
            decision_sha256: [0; 32],
            receipt_sha256: [0; 32],
        };
        value.decision_sha256 = lane_metrics_decision_sha256(&value);
        value.receipt_sha256 = lane_metrics_sha256(&value);
        Ok(value)
    }

    /// Rebuild every observation and aggregate from the original pipeline
    /// receipt and the materialized reference held by this receipt.
    pub fn verify_against(&self, pipeline: &Fixed64PipelineReceipt) -> Result<()> {
        let expected = Self::build(pipeline, self.reference.clone())?;
        if expected != *self {
            return Err(abi_mismatch(
                "lane-metrics receipt does not equal full pipeline rederivation",
            ));
        }
        Ok(())
    }
}

fn derive_observation(
    projection: &crate::docking::Fixed64ScientificProjection,
    reference: &Fixed64LaneMetricsReference,
    slot: usize,
    lane: Fixed64Lane,
) -> Result<Fixed64LaneMetricObservation> {
    let row = projection.candidate_rows[slot];
    let coordinate_ready = row.refinement.status
        == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY
        && row.refinement.coordinate_available;
    let final_coordinate_sha256 = if coordinate_ready {
        require_digest(row.refinement.coordinate_sha256, "final coordinate")?;
        row.refinement.coordinate_sha256
    } else {
        [0; 32]
    };
    let orientation_available = row.coordinates_available;
    let canonical_orientation_sha256 = if orientation_available {
        canonical_orientation_sha256(row.placement_quaternion)?
    } else {
        [0; 32]
    };
    let initial_severe_penetration = row.geometric_status
        == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
        && row.geometric_decision
            == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED;
    let post_refinement_severe_penetration = row.post_admission.status
        == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
        && row.post_admission.decision
            == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED;
    let exact_valid = row.validity.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
        && row.validity.passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
        && row.validity.blocker_mask == 0
        && row.ranking.valid_rank_eligible;
    let (rmsd_evaluated, rmsd, permutation_index) = if coordinate_ready {
        let (value, index) = symmetry_aware_direct_heavy_atom_rmsd(
            reference,
            &projection.final_coordinates,
            projection.ligand_atom_count,
            slot,
        )?;
        (true, value, index)
    } else {
        (false, 0.0, MISSING_SLOT_INDEX)
    };
    let oracle_2a = rmsd_evaluated && rmsd <= FIXED64_ORACLE_RMSD_THRESHOLD_ANGSTROM;
    let valid_oracle_2a = oracle_2a && exact_valid;
    let mut value = Fixed64LaneMetricObservation {
        slot_index: slot as u32,
        lane,
        coordinate_ready,
        final_coordinate_sha256,
        orientation_available,
        canonical_orientation_sha256,
        initial_severe_penetration,
        post_refinement_severe_penetration,
        exact_valid,
        rmsd_evaluated,
        symmetry_aware_direct_heavy_atom_rmsd_angstrom: rmsd,
        symmetry_permutation_index: permutation_index,
        oracle_2a,
        valid_oracle_2a,
        stable_rank: row.ranking.stable_rank,
        stable_valid_rank: row.ranking.stable_valid_rank,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = observation_sha256(&value);
    Ok(value)
}

#[allow(clippy::too_many_arguments)]
fn derive_lane_summary(
    lane: Fixed64Lane,
    first: usize,
    last: usize,
    observations: &[Fixed64LaneMetricObservation],
    projection: &crate::docking::Fixed64ScientificProjection,
    global_exact_valid_count: usize,
    global_oracle_count: usize,
    global_valid_oracle_count: usize,
    control_oracle: bool,
    control_valid_oracle: bool,
) -> Fixed64LaneMetricSummary {
    let rows = &observations[first..=last];
    let projection_rows = &projection.candidate_rows[first..=last];
    let coordinate_ready_count = rows.iter().filter(|row| row.coordinate_ready).count();
    let coordinate_identities = rows
        .iter()
        .filter(|row| row.coordinate_ready)
        .map(|row| row.final_coordinate_sha256)
        .collect::<BTreeSet<_>>();
    let orientations = rows
        .iter()
        .filter(|row| row.orientation_available)
        .map(|row| row.canonical_orientation_sha256)
        .collect::<BTreeSet<_>>();
    let cluster_ids = projection_rows
        .iter()
        .filter(|row| row.cluster.cluster_eligible)
        .map(|row| row.cluster.cluster_id)
        .collect::<BTreeSet<_>>();
    let generated_count = projection_rows
        .iter()
        .filter(|row| row.coordinates_available)
        .count();
    let initial_evaluated_count = projection_rows
        .iter()
        .filter(|row| row.geometric_status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED)
        .count();
    let post_evaluated_count = projection_rows
        .iter()
        .filter(|row| {
            row.post_admission.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
        })
        .count();
    let cluster_eligible_count = projection_rows
        .iter()
        .filter(|row| row.cluster.cluster_eligible)
        .count();
    let exact_valid_count = rows.iter().filter(|row| row.exact_valid).count();
    let oracle_count = rows.iter().filter(|row| row.oracle_2a).count();
    let valid_oracle_count = rows.iter().filter(|row| row.valid_oracle_2a).count();
    let orientation_count = rows.iter().filter(|row| row.orientation_available).count();
    let exact_unique = coordinate_identities.len();
    let mut value = Fixed64LaneMetricSummary {
        lane,
        first_slot_index: first as u32,
        slot_count: rows.len() as u64,
        generated_count: generated_count as u64,
        typed_failure_count: (rows.len() - generated_count) as u64,
        coordinate_ready_count: coordinate_ready_count as u64,
        exact_coordinate_unique_count: exact_unique as u64,
        exact_coordinate_duplicate_count: (coordinate_ready_count - exact_unique) as u64,
        cluster_eligible_count: cluster_eligible_count as u64,
        unique_valid_pose_cluster_count: cluster_ids.len() as u64,
        orientation_available_count: orientation_count as u64,
        unique_orientation_count: orientations.len() as u64,
        orientation_duplicate_count: (orientation_count - orientations.len()) as u64,
        initial_geometric_evaluated_count: initial_evaluated_count as u64,
        initial_severe_penetration_count: rows
            .iter()
            .filter(|row| row.initial_severe_penetration)
            .count() as u64,
        post_geometric_evaluated_count: post_evaluated_count as u64,
        post_severe_penetration_count: rows
            .iter()
            .filter(|row| row.post_refinement_severe_penetration)
            .count() as u64,
        exact_valid_count: exact_valid_count as u64,
        oracle_2a_count: oracle_count as u64,
        valid_oracle_2a_count: valid_oracle_count as u64,
        exact_coordinate_unique_rate: rate(exact_unique, coordinate_ready_count),
        unique_valid_pose_rate: rate(cluster_ids.len(), cluster_eligible_count),
        orientation_duplicate_rate: rate(orientation_count - orientations.len(), orientation_count),
        initial_severe_penetration_rate: rate(
            rows.iter()
                .filter(|row| row.initial_severe_penetration)
                .count(),
            initial_evaluated_count,
        ),
        post_severe_penetration_rate: rate(
            rows.iter()
                .filter(|row| row.post_refinement_severe_penetration)
                .count(),
            post_evaluated_count,
        ),
        exact_valid_contribution: rate(exact_valid_count, global_exact_valid_count),
        oracle_contribution: rate(oracle_count, global_oracle_count),
        valid_oracle_contribution: rate(valid_oracle_count, global_valid_oracle_count),
        incremental_oracle_case_recovery: !CONTROL_LANES.contains(&lane)
            && !control_oracle
            && oracle_count > 0,
        incremental_valid_oracle_case_recovery: !CONTROL_LANES.contains(&lane)
            && !control_valid_oracle
            && valid_oracle_count > 0,
        coordinate_entropy: coordinate_entropy(rows),
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = lane_summary_sha256(&value);
    value
}

fn oracle_selection_summary(
    observations: &[Fixed64LaneMetricObservation],
    projection: &crate::docking::Fixed64ScientificProjection,
) -> Fixed64OracleSelectionSummary {
    let proposal = minimum_rmsd(observations.iter().filter(|row| row.rmsd_evaluated));
    let valid = minimum_rmsd(
        observations
            .iter()
            .filter(|row| row.rmsd_evaluated && row.exact_valid),
    );
    let top1 = projection
        .primary_slot_indices
        .first()
        .and_then(|slot| observations.get(*slot as usize));
    let top5 = projection
        .primary_slot_indices
        .iter()
        .take(5)
        .filter_map(|slot| observations.get(*slot as usize))
        .collect::<Vec<_>>();
    let proposal_success =
        proposal.is_some_and(|row| row.symmetry_aware_direct_heavy_atom_rmsd_angstrom <= 2.0);
    let valid_success =
        valid.is_some_and(|row| row.symmetry_aware_direct_heavy_atom_rmsd_angstrom <= 2.0);
    let top1_success = top1.is_some_and(|row| row.valid_oracle_2a);
    let failure_class = if !proposal_success {
        Fixed64OracleFailureClass::ProposalFailure
    } else if !valid_success {
        Fixed64OracleFailureClass::ValidityFailure
    } else if !top1_success {
        Fixed64OracleFailureClass::RankingFailure
    } else {
        Fixed64OracleFailureClass::Success
    };
    let mut value = Fixed64OracleSelectionSummary {
        proposal_oracle_slot_index: proposal.map_or(MISSING_SLOT_INDEX, |row| row.slot_index),
        proposal_oracle_rmsd_angstrom: proposal.map_or(0.0, |row| {
            row.symmetry_aware_direct_heavy_atom_rmsd_angstrom
        }),
        proposal_oracle_success: proposal_success,
        valid_proposal_oracle_slot_index: valid.map_or(MISSING_SLOT_INDEX, |row| row.slot_index),
        valid_proposal_oracle_rmsd_angstrom: valid.map_or(0.0, |row| {
            row.symmetry_aware_direct_heavy_atom_rmsd_angstrom
        }),
        valid_proposal_oracle_success: valid_success,
        selected_top1_slot_index: top1.map_or(MISSING_SLOT_INDEX, |row| row.slot_index),
        selected_top1_rmsd_evaluated: top1.is_some_and(|row| row.rmsd_evaluated),
        selected_top1_rmsd_angstrom: top1.map_or(0.0, |row| {
            row.symmetry_aware_direct_heavy_atom_rmsd_angstrom
        }),
        selected_top1_exact_valid: top1.is_some_and(|row| row.exact_valid),
        selected_top1_oracle_success: top1_success,
        selected_top5_oracle_present: top5.iter().any(|row| row.oracle_2a),
        selected_top5_valid_oracle_present: top5.iter().any(|row| row.valid_oracle_2a),
        failure_class,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = oracle_selection_sha256(&value);
    value
}

fn conformer_orientation_interaction(
    observations: &[Fixed64LaneMetricObservation],
) -> Fixed64ConformerOrientationInteraction {
    let mut value = Fixed64ConformerOrientationInteraction {
        predeclared_pair_count: CONFORMER_ORIENTATION_PAIRS.len() as u64,
        both_coordinate_ready_count: 0,
        conformer_lower_rmsd_count: 0,
        source_lower_rmsd_count: 0,
        rmsd_tie_count: 0,
        conformer_oracle_gain_count: 0,
        conformer_oracle_loss_count: 0,
        both_oracle_count: 0,
        neither_oracle_count: 0,
        conformer_valid_oracle_gain_count: 0,
        conformer_valid_oracle_loss_count: 0,
        receipt_sha256: [0; 32],
    };
    for (source_slot, conformer_slot) in CONFORMER_ORIENTATION_PAIRS {
        let source = observations[source_slot];
        let conformer = observations[conformer_slot];
        if source.rmsd_evaluated && conformer.rmsd_evaluated {
            value.both_coordinate_ready_count += 1;
            match conformer
                .symmetry_aware_direct_heavy_atom_rmsd_angstrom
                .total_cmp(&source.symmetry_aware_direct_heavy_atom_rmsd_angstrom)
            {
                std::cmp::Ordering::Less => value.conformer_lower_rmsd_count += 1,
                std::cmp::Ordering::Greater => value.source_lower_rmsd_count += 1,
                std::cmp::Ordering::Equal => value.rmsd_tie_count += 1,
            }
        }
        match (source.oracle_2a, conformer.oracle_2a) {
            (false, true) => value.conformer_oracle_gain_count += 1,
            (true, false) => value.conformer_oracle_loss_count += 1,
            (true, true) => value.both_oracle_count += 1,
            (false, false) => value.neither_oracle_count += 1,
        }
        match (source.valid_oracle_2a, conformer.valid_oracle_2a) {
            (false, true) => value.conformer_valid_oracle_gain_count += 1,
            (true, false) => value.conformer_valid_oracle_loss_count += 1,
            _ => {}
        }
    }
    value.receipt_sha256 = conformer_interaction_sha256(&value);
    value
}

fn minimum_rmsd<'a>(
    rows: impl Iterator<Item = &'a Fixed64LaneMetricObservation>,
) -> Option<&'a Fixed64LaneMetricObservation> {
    rows.min_by(|left, right| {
        left.symmetry_aware_direct_heavy_atom_rmsd_angstrom
            .total_cmp(&right.symmetry_aware_direct_heavy_atom_rmsd_angstrom)
            .then(left.slot_index.cmp(&right.slot_index))
    })
}

fn coordinate_entropy(rows: &[Fixed64LaneMetricObservation]) -> Fixed64CoordinateEntropy {
    let mut groups = BTreeMap::<[u8; 32], usize>::new();
    for row in rows.iter().filter(|row| row.coordinate_ready) {
        *groups.entry(row.final_coordinate_sha256).or_default() += 1;
    }
    let count = groups.values().sum::<usize>();
    if count == 0 {
        return Fixed64CoordinateEntropy {
            coordinate_ready_count: 0,
            distinct_coordinate_count: 0,
            entropy_q32_numerator: 0,
            entropy_q32_denominator: 1,
            maximum_entropy_q32: 0,
        };
    }
    let numerator = count as u64 * LOG2_Q32[count]
        - groups
            .values()
            .map(|size| *size as u64 * LOG2_Q32[*size])
            .sum::<u64>();
    Fixed64CoordinateEntropy {
        coordinate_ready_count: count as u64,
        distinct_coordinate_count: groups.len() as u64,
        entropy_q32_numerator: numerator,
        entropy_q32_denominator: count as u64,
        maximum_entropy_q32: LOG2_Q32[count],
    }
}

fn symmetry_aware_direct_heavy_atom_rmsd(
    reference: &Fixed64LaneMetricsReference,
    candidates: &PositionSoaOwned,
    atom_count: usize,
    slot: usize,
) -> Result<(f64, u32)> {
    let offset = slot
        .checked_mul(atom_count)
        .ok_or_else(|| abi_mismatch("candidate coordinate offset overflowed"))?;
    let end = offset
        .checked_add(atom_count)
        .ok_or_else(|| abi_mismatch("candidate coordinate range overflowed"))?;
    if candidates.x_angstrom.len() < end
        || candidates.y_angstrom.len() < end
        || candidates.z_angstrom.len() < end
    {
        return Err(abi_mismatch(
            "final-coordinate channels do not cover the 64-row denominator",
        ));
    }
    let heavy_count = reference
        .heavy_atom_mask
        .iter()
        .filter(|value| **value == 1)
        .count();
    let mut best = f64::INFINITY;
    let mut best_index = MISSING_SLOT_INDEX;
    for (permutation_index, permutation) in reference.symmetry_permutations.iter().enumerate() {
        let mut squared_sum = 0.0;
        for (atom, candidate_atom) in permutation.iter().copied().enumerate().take(atom_count) {
            if reference.heavy_atom_mask[atom] == 0 {
                continue;
            }
            let candidate_atom = candidate_atom as usize;
            let dx = reference.reference_coordinates.x_angstrom[atom]
                - candidates.x_angstrom[offset + candidate_atom];
            let dy = reference.reference_coordinates.y_angstrom[atom]
                - candidates.y_angstrom[offset + candidate_atom];
            let dz = reference.reference_coordinates.z_angstrom[atom]
                - candidates.z_angstrom[offset + candidate_atom];
            squared_sum += dx * dx + dy * dy + dz * dz;
        }
        let rmsd = (squared_sum / heavy_count as f64).sqrt();
        if !rmsd.is_finite() {
            return Err(abi_mismatch("lane-metrics RMSD is not finite"));
        }
        if rmsd < best {
            best = rmsd;
            best_index = permutation_index as u32;
        }
    }
    Ok((best, best_index))
}

fn canonical_orientation_sha256(quaternion: [f64; 4]) -> Result<[u8; 32]> {
    if quaternion.iter().any(|value| !value.is_finite()) {
        return Err(abi_mismatch("placement quaternion is not finite"));
    }
    let mut canonical = quaternion.map(|value| if value == 0.0 { 0.0 } else { value });
    if let Some(first_nonzero) = canonical.iter().find(|value| **value != 0.0) {
        if first_nonzero.is_sign_negative() {
            canonical = canonical.map(|value| -value);
        }
    }
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_canonical_orientation/1.0.0");
    for value in canonical {
        hash.f64(value);
    }
    Ok(hash.finish())
}

fn canonical_symmetry_permutations(
    permutations: &[Vec<u32>],
    heavy_atom_mask: &[u8],
) -> Result<Vec<Vec<u32>>> {
    if permutations.is_empty() || permutations.len() > FIXED64_MAX_SYMMETRY_PERMUTATIONS {
        return Err(invalid(format!(
            "symmetry permutation count must be in [1,{FIXED64_MAX_SYMMETRY_PERMUTATIONS}]"
        )));
    }
    let atom_count = heavy_atom_mask.len();
    let expected = (0..atom_count as u32).collect::<Vec<_>>();
    let mut canonical = permutations.to_vec();
    for permutation in &canonical {
        if permutation.len() != atom_count {
            return Err(invalid(
                "symmetry permutation length must match the ligand atom count",
            ));
        }
        let mut sorted = permutation.clone();
        sorted.sort_unstable();
        if sorted != expected {
            return Err(invalid(
                "symmetry permutation must be a bijection over ligand atoms",
            ));
        }
        if permutation
            .iter()
            .enumerate()
            .any(|(reference_atom, candidate_atom)| {
                heavy_atom_mask[reference_atom] != heavy_atom_mask[*candidate_atom as usize]
            })
        {
            return Err(invalid(
                "symmetry permutation must preserve the heavy-atom mask",
            ));
        }
    }
    canonical.sort();
    if canonical.windows(2).any(|pair| pair[0] == pair[1]) {
        return Err(invalid("symmetry permutations must be unique"));
    }
    if canonical.first() != Some(&expected) {
        return Err(invalid(
            "symmetry permutations must include the identity mapping",
        ));
    }
    Ok(canonical)
}

fn lane_for_slot(slot: usize) -> Option<Fixed64Lane> {
    FIXED64_LANE_RANGES
        .iter()
        .find_map(|(lane, first, last)| (*first <= slot && slot <= *last).then_some(*lane))
}

fn lane_from_raw(value: i32) -> Option<Fixed64Lane> {
    match value {
        sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS => {
            Some(Fixed64Lane::PocketCenteredControls)
        }
        sys::BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS => {
            Some(Fixed64Lane::UniformSourceControls)
        }
        sys::BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3 => {
            Some(Fixed64Lane::DeterministicIndependentSo3)
        }
        sys::BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3 => {
            Some(Fixed64Lane::TrueConformerIndependentSo3)
        }
        sys::BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR => {
            Some(Fixed64Lane::LigandDonorToReceptorAcceptor)
        }
        sys::BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR => {
            Some(Fixed64Lane::LigandAcceptorToReceptorDonor)
        }
        sys::BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE => Some(Fixed64Lane::ComplementaryCharge),
        sys::BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE => Some(Fixed64Lane::AromaticPlane),
        sys::BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE => Some(Fixed64Lane::PrincipalAxisShape),
        sys::BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS => {
            Some(Fixed64Lane::PairedRetainedControls)
        }
        _ => None,
    }
}

fn rate(numerator: usize, denominator: usize) -> Fixed64MetricRate {
    Fixed64MetricRate {
        numerator: numerator as u64,
        denominator: denominator as u64,
    }
}

fn validate_reference_coordinates(value: PositionSoa<'_>) -> Result<usize> {
    let count = value.x_angstrom.len();
    if count == 0
        || count > FIXED64_MAX_LIGAND_ATOMS
        || value.y_angstrom.len() != count
        || value.z_angstrom.len() != count
    {
        return Err(invalid(format!(
            "reference coordinates must contain 1..={FIXED64_MAX_LIGAND_ATOMS} aligned atoms"
        )));
    }
    if value
        .x_angstrom
        .iter()
        .chain(value.y_angstrom)
        .chain(value.z_angstrom)
        .any(|coordinate| !coordinate.is_finite())
    {
        return Err(invalid("reference coordinates must be finite"));
    }
    Ok(count)
}

fn validate_heavy_atom_mask(values: &[u8], atom_count: usize) -> Result<()> {
    if values.len() != atom_count || values.iter().any(|value| *value > 1) || !values.contains(&1) {
        return Err(invalid(
            "heavy-atom mask must be aligned, binary, and select at least one atom",
        ));
    }
    Ok(())
}

fn require_case_id(value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 128
        || value.trim() != value
        || !value.bytes().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'/')
        })
    {
        return Err(invalid(
            "case ID must be 1..=128 canonical ASCII identifier bytes",
        ));
    }
    Ok(())
}

fn require_digest(value: [u8; 32], label: &str) -> Result<()> {
    if value == [0; 32] {
        return Err(invalid(format!("{label} SHA-256 is absent")));
    }
    Ok(())
}

fn require_non_authoritative(value: Fixed64AuthorityDisposition) -> Result<()> {
    if value.result_dependent_input_consumed
        || value.fallback_allowed
        || value.multi_anchor_consumed
        || !value.denominator_preserved
        || value.molecular_execution_authorized
        || value.reservation_authorized
        || value.benchmark_execution_authorized
        || value.existing_rank_auto_change_authorized
        || value.customer_pose_emission_authorized
        || value.production_claim_authorized
        || value.scientific_claim_authorized
    {
        return Err(abi_mismatch(
            "lane metrics require a denominator-preserving authority-false pipeline receipt",
        ));
    }
    Ok(())
}

fn invalid(message: impl Into<String>) -> Error {
    Error {
        code: ErrorCode::InvalidArgument,
        message: message.into(),
    }
}

fn abi_mismatch(message: impl Into<String>) -> Error {
    Error {
        code: ErrorCode::AbiMismatch,
        message: message.into(),
    }
}

fn hash_bool(hash: &mut CanonicalHasher, value: bool) {
    hash.byte(u8::from(value));
}

fn hash_lane(hash: &mut CanonicalHasher, lane: Fixed64Lane) {
    hash.string(lane.id());
}

fn hash_rate(hash: &mut CanonicalHasher, value: Fixed64MetricRate) {
    hash.u64(value.numerator);
    hash.u64(value.denominator);
}

fn hash_entropy(hash: &mut CanonicalHasher, value: Fixed64CoordinateEntropy) {
    hash.u64(value.coordinate_ready_count);
    hash.u64(value.distinct_coordinate_count);
    hash.u64(value.entropy_q32_numerator);
    hash.u64(value.entropy_q32_denominator);
    hash.u64(value.maximum_entropy_q32);
}

fn hash_authority(hash: &mut CanonicalHasher, value: Fixed64AuthorityDisposition) {
    for field in [
        value.result_dependent_input_consumed,
        value.fallback_allowed,
        value.multi_anchor_consumed,
        value.denominator_preserved,
        value.molecular_execution_authorized,
        value.reservation_authorized,
        value.benchmark_execution_authorized,
        value.existing_rank_auto_change_authorized,
        value.customer_pose_emission_authorized,
        value.production_claim_authorized,
        value.scientific_claim_authorized,
    ] {
        hash_bool(hash, field);
    }
}

fn reference_sha256(value: &Fixed64LaneMetricsReference) -> [u8; 32] {
    let mut hash = CanonicalHasher::new(FIXED64_LANE_METRICS_REFERENCE_SCHEMA_ID);
    hash.string(&value.case_id);
    hash.digest(value.reference_pose_source_receipt_sha256);
    hash.digest(value.prepared_ligand_topology_sha256);
    hash.usize(value.reference_coordinates.x_angstrom.len());
    for atom in 0..value.reference_coordinates.x_angstrom.len() {
        hash.f64(value.reference_coordinates.x_angstrom[atom]);
        hash.f64(value.reference_coordinates.y_angstrom[atom]);
        hash.f64(value.reference_coordinates.z_angstrom[atom]);
    }
    hash.bytes(&value.heavy_atom_mask);
    hash.usize(value.symmetry_permutations.len());
    for permutation in &value.symmetry_permutations {
        hash.usize(permutation.len());
        for atom in permutation {
            hash.u32(*atom);
        }
    }
    hash.finish()
}

fn observation_sha256(value: &Fixed64LaneMetricObservation) -> [u8; 32] {
    let mut hash = CanonicalHasher::new(FIXED64_LANE_METRICS_OBSERVATION_SCHEMA_ID);
    hash.u32(value.slot_index);
    hash_lane(&mut hash, value.lane);
    hash_bool(&mut hash, value.coordinate_ready);
    hash.digest(value.final_coordinate_sha256);
    hash_bool(&mut hash, value.orientation_available);
    hash.digest(value.canonical_orientation_sha256);
    hash_bool(&mut hash, value.initial_severe_penetration);
    hash_bool(&mut hash, value.post_refinement_severe_penetration);
    hash_bool(&mut hash, value.exact_valid);
    hash_bool(&mut hash, value.rmsd_evaluated);
    hash.f64(value.symmetry_aware_direct_heavy_atom_rmsd_angstrom);
    hash.u32(value.symmetry_permutation_index);
    hash_bool(&mut hash, value.oracle_2a);
    hash_bool(&mut hash, value.valid_oracle_2a);
    hash.u32(value.stable_rank);
    hash.u32(value.stable_valid_rank);
    hash.finish()
}

fn lane_summary_sha256(value: &Fixed64LaneMetricSummary) -> [u8; 32] {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_lane_metric_summary/1.0.0");
    hash_lane(&mut hash, value.lane);
    for field in [
        value.first_slot_index as u64,
        value.slot_count,
        value.generated_count,
        value.typed_failure_count,
        value.coordinate_ready_count,
        value.exact_coordinate_unique_count,
        value.exact_coordinate_duplicate_count,
        value.cluster_eligible_count,
        value.unique_valid_pose_cluster_count,
        value.orientation_available_count,
        value.unique_orientation_count,
        value.orientation_duplicate_count,
        value.initial_geometric_evaluated_count,
        value.initial_severe_penetration_count,
        value.post_geometric_evaluated_count,
        value.post_severe_penetration_count,
        value.exact_valid_count,
        value.oracle_2a_count,
        value.valid_oracle_2a_count,
    ] {
        hash.u64(field);
    }
    for rate in [
        value.exact_coordinate_unique_rate,
        value.unique_valid_pose_rate,
        value.orientation_duplicate_rate,
        value.initial_severe_penetration_rate,
        value.post_severe_penetration_rate,
        value.exact_valid_contribution,
        value.oracle_contribution,
        value.valid_oracle_contribution,
    ] {
        hash_rate(&mut hash, rate);
    }
    hash_bool(&mut hash, value.incremental_oracle_case_recovery);
    hash_bool(&mut hash, value.incremental_valid_oracle_case_recovery);
    hash_entropy(&mut hash, value.coordinate_entropy);
    hash.finish()
}

fn oracle_selection_sha256(value: &Fixed64OracleSelectionSummary) -> [u8; 32] {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_oracle_selection_summary/1.0.0");
    hash.u32(value.proposal_oracle_slot_index);
    hash.f64(value.proposal_oracle_rmsd_angstrom);
    hash_bool(&mut hash, value.proposal_oracle_success);
    hash.u32(value.valid_proposal_oracle_slot_index);
    hash.f64(value.valid_proposal_oracle_rmsd_angstrom);
    hash_bool(&mut hash, value.valid_proposal_oracle_success);
    hash.u32(value.selected_top1_slot_index);
    hash_bool(&mut hash, value.selected_top1_rmsd_evaluated);
    hash.f64(value.selected_top1_rmsd_angstrom);
    hash_bool(&mut hash, value.selected_top1_exact_valid);
    hash_bool(&mut hash, value.selected_top1_oracle_success);
    hash_bool(&mut hash, value.selected_top5_oracle_present);
    hash_bool(&mut hash, value.selected_top5_valid_oracle_present);
    hash.byte(match value.failure_class {
        Fixed64OracleFailureClass::Success => 0,
        Fixed64OracleFailureClass::ProposalFailure => 1,
        Fixed64OracleFailureClass::ValidityFailure => 2,
        Fixed64OracleFailureClass::RankingFailure => 3,
    });
    hash.finish()
}

fn conformer_interaction_sha256(value: &Fixed64ConformerOrientationInteraction) -> [u8; 32] {
    let mut hash = CanonicalHasher::new(
        "betelgeuze.engine_v2_native_fixed64_conformer_orientation_interaction/1.0.0",
    );
    for field in [
        value.predeclared_pair_count,
        value.both_coordinate_ready_count,
        value.conformer_lower_rmsd_count,
        value.source_lower_rmsd_count,
        value.rmsd_tie_count,
        value.conformer_oracle_gain_count,
        value.conformer_oracle_loss_count,
        value.both_oracle_count,
        value.neither_oracle_count,
        value.conformer_valid_oracle_gain_count,
        value.conformer_valid_oracle_loss_count,
    ] {
        hash.u64(field);
    }
    hash.finish()
}

fn lane_metrics_sha256(value: &Fixed64LaneMetricsReceipt) -> [u8; 32] {
    let mut hash = CanonicalHasher::new(FIXED64_LANE_METRICS_SCHEMA_ID);
    hash.digest(value.reference.receipt_sha256);
    hash.digest(value.pipeline_source_bundle_receipt_sha256);
    hash.digest(value.pipeline_cluster_batch_receipt_sha256);
    hash.digest(value.scientific_projection_sha256);
    hash.digest(value.decision_sha256);
    hash.u64(value.candidate_denominator);
    hash.f64(value.rmsd_threshold_angstrom);
    hash.usize(value.observations.len());
    for row in &value.observations {
        hash.digest(row.receipt_sha256);
    }
    hash.usize(value.lane_summaries.len());
    for lane in &value.lane_summaries {
        hash.digest(lane.receipt_sha256);
    }
    hash_entropy(&mut hash, value.global_coordinate_entropy);
    hash.digest(value.oracle_selection.receipt_sha256);
    hash.digest(value.conformer_orientation_interaction.receipt_sha256);
    hash_authority(&mut hash, value.authority);
    hash_bool(&mut hash, value.result_dependent_allocation_consumed);
    hash_bool(&mut hash, value.metrics_used_to_change_rank);
    hash_bool(&mut hash, value.product_execution_authorized);
    hash_bool(&mut hash, value.public_or_scientific_claim_authorized);
    hash.finish()
}

fn lane_metrics_decision_sha256(value: &Fixed64LaneMetricsReceipt) -> [u8; 32] {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_lane_metrics_decision/1.0.0");
    hash.u64(value.candidate_denominator);
    hash.f64(value.rmsd_threshold_angstrom);
    hash.usize(value.observations.len());
    for row in &value.observations {
        hash.u32(row.slot_index);
        hash_lane(&mut hash, row.lane);
        hash_bool(&mut hash, row.coordinate_ready);
        hash_bool(&mut hash, row.orientation_available);
        hash_bool(&mut hash, row.initial_severe_penetration);
        hash_bool(&mut hash, row.post_refinement_severe_penetration);
        hash_bool(&mut hash, row.exact_valid);
        hash_bool(&mut hash, row.rmsd_evaluated);
        hash_bool(&mut hash, row.oracle_2a);
        hash_bool(&mut hash, row.valid_oracle_2a);
        hash.u32(row.stable_rank);
        hash.u32(row.stable_valid_rank);
    }
    hash.usize(value.lane_summaries.len());
    for lane in &value.lane_summaries {
        hash.digest(lane.receipt_sha256);
    }
    let oracle = value.oracle_selection;
    hash.u32(oracle.proposal_oracle_slot_index);
    hash_bool(&mut hash, oracle.proposal_oracle_success);
    hash.u32(oracle.valid_proposal_oracle_slot_index);
    hash_bool(&mut hash, oracle.valid_proposal_oracle_success);
    hash.u32(oracle.selected_top1_slot_index);
    hash_bool(&mut hash, oracle.selected_top1_rmsd_evaluated);
    hash_bool(&mut hash, oracle.selected_top1_exact_valid);
    hash_bool(&mut hash, oracle.selected_top1_oracle_success);
    hash_bool(&mut hash, oracle.selected_top5_oracle_present);
    hash_bool(&mut hash, oracle.selected_top5_valid_oracle_present);
    hash.byte(match oracle.failure_class {
        Fixed64OracleFailureClass::Success => 0,
        Fixed64OracleFailureClass::ProposalFailure => 1,
        Fixed64OracleFailureClass::ValidityFailure => 2,
        Fixed64OracleFailureClass::RankingFailure => 3,
    });
    hash.digest(value.conformer_orientation_interaction.receipt_sha256);
    hash_authority(&mut hash, value.authority);
    hash_bool(&mut hash, value.result_dependent_allocation_consumed);
    hash_bool(&mut hash, value.metrics_used_to_change_rank);
    hash_bool(&mut hash, value.product_execution_authorized);
    hash_bool(&mut hash, value.public_or_scientific_claim_authorized);
    hash.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn two_atom_reference(permutations: &[Vec<u32>]) -> Fixed64LaneMetricsReference {
        Fixed64LaneMetricsReference::new(
            "synthetic-two-atom",
            [0x11; 32],
            [0x22; 32],
            PositionSoa::new(&[0.0, 2.0], &[0.0, 0.0], &[0.0, 0.0]),
            &[1, 1],
            permutations,
        )
        .unwrap()
    }

    #[test]
    fn reference_canonicalizes_and_seals_symmetry_mappings() {
        let reference = two_atom_reference(&[vec![1, 0], vec![0, 1]]);
        assert_eq!(
            reference.symmetry_permutations,
            vec![vec![0, 1], vec![1, 0]]
        );
        reference.validate().unwrap();
        let error = Fixed64LaneMetricsReference::new(
            "synthetic-two-atom",
            [0x11; 32],
            [0x22; 32],
            PositionSoa::new(&[0.0, 2.0], &[0.0, 0.0], &[0.0, 0.0]),
            &[1, 1],
            &[vec![0, 1], vec![0, 1]],
        )
        .unwrap_err();
        assert_eq!(error.code, ErrorCode::InvalidArgument);
        assert!(error.message.contains("unique"));
    }

    #[test]
    fn direct_heavy_atom_rmsd_uses_reference_to_candidate_symmetry() {
        let reference = two_atom_reference(&[vec![0, 1], vec![1, 0]]);
        let mut x = vec![0.0; FIXED64_CANDIDATE_COUNT * 2];
        let y = vec![0.0; FIXED64_CANDIDATE_COUNT * 2];
        let z = vec![0.0; FIXED64_CANDIDATE_COUNT * 2];
        x[0] = 2.0;
        x[1] = 0.0;
        let candidates = PositionSoaOwned {
            x_angstrom: x,
            y_angstrom: y,
            z_angstrom: z,
        };
        let (rmsd, permutation) =
            symmetry_aware_direct_heavy_atom_rmsd(&reference, &candidates, 2, 0).unwrap();
        assert_eq!(rmsd, 0.0);
        assert_eq!(permutation, 1);
    }

    #[test]
    fn canonical_orientation_treats_quaternion_sign_as_equivalent() {
        let first = canonical_orientation_sha256([0.5, -0.5, 0.5, -0.5]).unwrap();
        let negated = canonical_orientation_sha256([-0.5, 0.5, -0.5, 0.5]).unwrap();
        let other = canonical_orientation_sha256([0.5, 0.5, 0.5, -0.5]).unwrap();
        assert_eq!(first, negated);
        assert_ne!(first, other);
    }
}
