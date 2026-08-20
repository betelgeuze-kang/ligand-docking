//! Producer-bypass composition for a verified native 512-to-64 funnel batch.

use betelgeuze_docking_search::{
    NativeSamplingFunnelLane, NativeSamplingFunnelPreselectedBatch,
    NativeSamplingFunnelSelectedState,
};

use crate::PositionSoaOwned;

use super::*;

pub const FIXED64_PRESELECTED_PIPELINE_PROFILE_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_preselected_pipeline/1.0.0";
const PRESELECTED_POLICY_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_preselected_policy/1.0.0";
const PRESELECTED_ROW_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_preselected_pipeline_row/1.0.0";

#[derive(Debug, Clone, Copy)]
pub struct Fixed64PreselectedRunInput<'a> {
    pub preselected: &'a NativeSamplingFunnelPreselectedBatch,
    pub rmsd_threshold_angstrom: f64,
    pub candidate_modes: &'a [Fixed64RefinementMode],
    pub rigid_max_steps: &'a [u64],
    pub proposal_is_torsion_eligible: &'a [u8],
    pub torsion_max_steps: &'a [u64],
    pub baseline_torsion_angles_radians: &'a [f64],
    pub predeclared_refinement_policy_sha256: Sha256,
    pub predeclared_post_refinement_admission_policy_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fixed64PreselectedBatchReceipts {
    pub preselected_batch_receipt_sha256: Sha256,
    pub admission_context_receipt_sha256: Sha256,
    pub refinement_context_receipt_sha256: Sha256,
    pub scorer_context_receipt_sha256: Sha256,
    pub validity_context_receipt_sha256: Sha256,
    pub component_binding_receipt_sha256: Sha256,
    pub policy_receipt_sha256: Sha256,
    pub initial_admission_batch_receipt_sha256: Sha256,
    pub refinement_batch_receipt_sha256: Sha256,
    pub post_admission_batch_receipt_sha256: Sha256,
    pub scorer_batch_receipt_sha256: Sha256,
    pub validity_batch_receipt_sha256: Sha256,
    pub ranking_batch_receipt_sha256: Sha256,
    pub cluster_batch_receipt_sha256: Sha256,
    pub pipeline_batch_receipt_sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64PreselectedPipelineRow {
    pub slot_index: u32,
    pub lane: NativeSamplingFunnelLane,
    pub selected_state: NativeSamplingFunnelSelectedState,
    pub requested_refinement_mode: i32,
    pub effective_refinement_mode: i32,
    pub initial_admission: Fixed64GeometricEvidence,
    pub rigid: Fixed64RigidEvidence,
    pub torsion: Fixed64TorsionEvidence,
    pub refinement: Fixed64RefinementEvidence,
    pub post_admission: Fixed64GeometricEvidence,
    pub scorer: Fixed64ScorerEvidence,
    pub validity: Fixed64ValidityEvidence,
    pub ranking: Fixed64RankingEvidence,
    pub cluster: Fixed64ClusterEvidence,
    pub refinement_evidence_sha256: Sha256,
    pub scorer_evidence_sha256: Sha256,
    pub validity_evidence_sha256: Sha256,
    pub ranking_evidence_sha256: Sha256,
    pub cluster_evidence_sha256: Sha256,
    pub row_receipt_sha256: Sha256,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64PreselectedPipelineReceipt {
    pub backend: Backend,
    pub unit_system: UnitSystem,
    pub ligand_system_sha256: Sha256,
    pub ligand_atom_count: usize,
    pub selected_count: u64,
    pub lane_shortfall_count: u64,
    pub initial_admitted_count: u64,
    pub refined_count: u64,
    pub post_admitted_count: u64,
    pub post_rejected_count: u64,
    pub scored_count: u64,
    pub valid_count: u64,
    pub rmsd_threshold_angstrom: f64,
    pub requested_refinement_modes: Vec<i32>,
    pub rigid_max_steps: Vec<u64>,
    pub proposal_is_torsion_eligible: Vec<u8>,
    pub torsion_max_steps: Vec<u64>,
    pub baseline_torsion_angles_radians: Vec<f64>,
    pub maximum_torsion_steps: u64,
    pub rotatable_child_atom_indices: Vec<u64>,
    pub predeclared_refinement_policy_sha256: Sha256,
    pub predeclared_post_refinement_admission_policy_sha256: Sha256,
    pub source_coordinates: PositionSoaOwned,
    pub source_quaternions: [Vec<f64>; 4],
    pub rigid_coordinates: Fixed64RigidCoordinates,
    pub torsion_coordinates: Fixed64TorsionCoordinates,
    pub final_coordinates: PositionSoaOwned,
    pub final_quaternions: [Vec<f64>; 4],
    pub initial_admission_rows: Vec<Fixed64GeometricEvidence>,
    pub rigid_rows: Vec<Fixed64RigidEvidence>,
    pub torsion_rows: Vec<Fixed64TorsionEvidence>,
    pub torsion_moves: Vec<Fixed64TorsionMoveEvidence>,
    pub refinement_rows: Vec<Fixed64RefinementEvidence>,
    pub post_admission_rows: Vec<Fixed64GeometricEvidence>,
    pub scorer_rows: Vec<Fixed64ScorerEvidence>,
    pub validity_rows: Vec<Fixed64ValidityEvidence>,
    pub ranking_rows: Vec<Fixed64RankingEvidence>,
    pub cluster_rows: Vec<Fixed64ClusterEvidence>,
    pub rows: Vec<Fixed64PreselectedPipelineRow>,
    pub primary_slot_indices: Vec<u32>,
    pub valid_slot_indices: Vec<u32>,
    pub representative_slot_indices: Vec<u32>,
    pub top_k_slot_indices: Vec<u32>,
    pub receipts: Fixed64PreselectedBatchReceipts,
    pub authority: Fixed64AuthorityDisposition,
}

impl Fixed64PreselectedPipelineReceipt {
    /// Verifies persisted receipt integrity and the self-contained refinement,
    /// ranking, and clustering policies. Molecular-context admission, scorer,
    /// and validity semantics are verified before issuance by `run_preselected`.
    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        validate_receipt_shape(self).is_ok()
            && derive_pipeline_receipt(self)
                .is_ok_and(|derived| derived == self.receipts.pipeline_batch_receipt_sha256)
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn benchmark_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn product_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn scientific_claim_authorized(&self) -> bool {
        false
    }
}

/// Pipeline variant that owns the additional ABI 1.21 component handles only
/// when preselected composition is explicitly requested.
pub struct Fixed64PreselectedPipeline {
    handles: PreselectedHandles,
    pipeline: Fixed64Pipeline,
}

impl std::ops::Deref for Fixed64PreselectedPipeline {
    type Target = Fixed64Pipeline;

    fn deref(&self) -> &Self::Target {
        &self.pipeline
    }
}

impl Fixed64PreselectedPipeline {
    pub fn new(context: &Context, scientific: Fixed64PipelineContext<'_>) -> Result<Self> {
        let (pipeline, handles) = Fixed64Pipeline::new_preselected(context, scientific)?;
        Ok(Self { handles, pipeline })
    }

    pub fn run_preselected(
        &self,
        input: Fixed64PreselectedRunInput<'_>,
    ) -> Result<Fixed64PreselectedPipelineReceipt> {
        const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        const TOP_K_LIMIT: usize = sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize;
        const MOVES_PER_SLOT: usize = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
        const MOVE_COUNT: usize = CANDIDATE_COUNT * MOVES_PER_SLOT;

        validate_preselected_input(self, input)?;
        let ligand_count = self.ligand_atom_count;
        let coordinate_count = ligand_count.checked_mul(CANDIDATE_COUNT).ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "preselected fixed64 coordinate denominator overflowed",
            )
        })?;
        let coordinate_count_u64 = checked_count(coordinate_count)?;
        let ligand_count_u64 = checked_count(ligand_count)?;
        let receptor_count_u64 = checked_count(self.receptor_atom_count)?;
        let raw_modes = input
            .candidate_modes
            .iter()
            .map(|mode| mode.as_raw())
            .collect::<Vec<_>>();
        let source_channels = [
            input.preselected.x_angstrom(),
            input.preselected.y_angstrom(),
            input.preselected.z_angstrom(),
        ];
        let source_quaternions = [
            input.preselected.source_quaternion_x(),
            input.preselected.source_quaternion_y(),
            input.preselected.source_quaternion_z(),
            input.preselected.source_quaternion_w(),
        ];

        let initial_states = input
            .preselected
            .rows()
            .iter()
            .map(|row| match row.state() {
                NativeSamplingFunnelSelectedState::Selected { .. } => {
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE
                }
                NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => {
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE
                }
            })
            .collect::<Vec<_>>();
        let mut initial_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut initial_output = init(sys::bg_docking_geometric_admission_output_v1_init)?;
        initial_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        initial_output.rows = initial_rows.as_mut_ptr();
        let mut initial_batch =
            init(sys::bg_docking_geometric_admission_candidate_batch_soa_v1_init)?;
        initial_batch.candidate_count = checked_count(CANDIDATE_COUNT)?;
        initial_batch.ligand_atom_count = ligand_count_u64;
        initial_batch.candidate_state = initial_states.as_ptr();
        initial_batch.x_angstrom = source_channels[0].as_ptr();
        initial_batch.y_angstrom = source_channels[1].as_ptr();
        initial_batch.z_angstrom = source_channels[2].as_ptr();
        // SAFETY: every descriptor and exact-capacity buffer remains live for the call.
        status_result(unsafe {
            sys::bg_docking_geometric_admission_v1_evaluate_fixed64(
                self.context_lease.raw_handle(),
                self.replay_admission_handle.as_ptr(),
                &initial_batch,
                &mut initial_output,
            )
        })?;

        let effective_modes = initial_rows
            .iter()
            .enumerate()
            .map(|(slot, row)| {
                let admitted = initial_states[slot]
                    == sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE
                    && row.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
                    && row.failure_code == sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE
                    && row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                    && row.rank_eligible == 1;
                if admitted {
                    raw_modes[slot]
                } else {
                    sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
                }
            })
            .collect::<Vec<_>>();

        let mut rigid_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut rigid_coordinates: [Vec<f64>; 12] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut rigid_output = init(sys::bg_docking_rigid_refinement_output_v1_init)?;
        rigid_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        rigid_output.coordinate_capacity = coordinate_count_u64;
        rigid_output.rows = rigid_rows.as_mut_ptr();
        assign_rigid_output_channels(&mut rigid_output, &mut rigid_coordinates);
        let mut rigid_batch = init(sys::bg_docking_rigid_refinement_candidate_batch_soa_v1_init)?;
        rigid_batch.candidate_count = checked_count(CANDIDATE_COUNT)?;
        rigid_batch.ligand_atom_count = ligand_count_u64;
        rigid_batch.candidate_mode = effective_modes.as_ptr();
        rigid_batch.max_steps = input.rigid_max_steps.as_ptr();
        rigid_batch.x_angstrom = source_channels[0].as_ptr();
        rigid_batch.y_angstrom = source_channels[1].as_ptr();
        rigid_batch.z_angstrom = source_channels[2].as_ptr();
        // SAFETY: every descriptor and exact-capacity buffer remains live for the call.
        status_result(unsafe {
            sys::bg_docking_rigid_refinement_fixed64(
                self.context_lease.raw_handle(),
                self.handles.rigid.as_ptr(),
                &rigid_batch,
                &mut rigid_output,
            )
        })?;

        let mut torsion_states =
            vec![sys::BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE; CANDIDATE_COUNT];
        let mut baseline_steps = vec![0_u64; CANDIDATE_COUNT];
        for slot in 0..CANDIDATE_COUNT {
            if rigid_rows[slot].status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED
                && mode_uses_v6(effective_modes[slot])
            {
                torsion_states[slot] = sys::BG_DOCKING_TORSION_V7_CANDIDATE_REFINE;
                baseline_steps[slot] = rigid_rows[slot].selected.accepted_steps;
            }
        }
        let mut torsion_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut torsion_moves = vec![zeroed(); MOVE_COUNT];
        let mut torsion_coordinates: [Vec<f64>; 8] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut torsion_output = init(sys::bg_docking_torsion_v7_output_v1_init)?;
        torsion_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        torsion_output.move_capacity = checked_count(MOVE_COUNT)?;
        torsion_output.coordinate_capacity = coordinate_count_u64;
        torsion_output.rows = torsion_rows.as_mut_ptr();
        torsion_output.moves = torsion_moves.as_mut_ptr();
        assign_torsion_output_channels(&mut torsion_output, &mut torsion_coordinates);
        let mut torsion_batch = init(sys::bg_docking_torsion_v7_candidate_batch_soa_v1_init)?;
        torsion_batch.candidate_count = checked_count(CANDIDATE_COUNT)?;
        torsion_batch.ligand_atom_count = ligand_count_u64;
        torsion_batch.candidate_state = torsion_states.as_ptr();
        torsion_batch.proposal_is_torsion_eligible = input.proposal_is_torsion_eligible.as_ptr();
        torsion_batch.max_steps = input.torsion_max_steps.as_ptr();
        torsion_batch.baseline_v6_accepted_steps = baseline_steps.as_ptr();
        torsion_batch.source_x_angstrom = source_channels[0].as_ptr();
        torsion_batch.source_y_angstrom = source_channels[1].as_ptr();
        torsion_batch.source_z_angstrom = source_channels[2].as_ptr();
        torsion_batch.baseline_v6_x_angstrom = rigid_coordinates[0].as_ptr();
        torsion_batch.baseline_v6_y_angstrom = rigid_coordinates[1].as_ptr();
        torsion_batch.baseline_v6_z_angstrom = rigid_coordinates[2].as_ptr();
        torsion_batch.baseline_v6_torsion_angles_radians =
            input.baseline_torsion_angles_radians.as_ptr();
        // SAFETY: every descriptor and exact-capacity buffer remains live for the call.
        status_result(unsafe {
            sys::bg_docking_torsion_v7_refine_fixed64(
                self.context_lease.raw_handle(),
                self.handles.torsion.as_ptr(),
                &torsion_batch,
                &mut torsion_output,
            )
        })?;

        let mut refinement_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut final_coordinates: [Vec<f64>; 3] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut final_quaternions: [Vec<f64>; 4] =
            std::array::from_fn(|_| vec![0.0; CANDIDATE_COUNT]);
        materialize_refinement_rows(
            ligand_count,
            &effective_modes,
            &rigid_rows,
            &rigid_coordinates,
            &torsion_rows,
            &torsion_coordinates,
            source_quaternions,
            &mut refinement_rows,
            &mut final_coordinates,
            &mut final_quaternions,
        )?;

        let post_states = refinement_rows
            .iter()
            .map(|row| {
                if row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY
                    && row.coordinate_available == 1
                {
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE
                } else {
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE
                }
            })
            .collect::<Vec<_>>();
        let mut post_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut post_output = init(sys::bg_docking_geometric_admission_output_v1_init)?;
        post_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        post_output.rows = post_rows.as_mut_ptr();
        let mut post_batch = init(sys::bg_docking_geometric_admission_candidate_batch_soa_v1_init)?;
        post_batch.candidate_count = checked_count(CANDIDATE_COUNT)?;
        post_batch.ligand_atom_count = ligand_count_u64;
        post_batch.candidate_state = post_states.as_ptr();
        post_batch.x_angstrom = final_coordinates[0].as_ptr();
        post_batch.y_angstrom = final_coordinates[1].as_ptr();
        post_batch.z_angstrom = final_coordinates[2].as_ptr();
        // SAFETY: every descriptor and exact-capacity buffer remains live for the call.
        status_result(unsafe {
            sys::bg_docking_geometric_admission_v1_evaluate_fixed64(
                self.context_lease.raw_handle(),
                self.replay_admission_handle.as_ptr(),
                &post_batch,
                &mut post_output,
            )
        })?;

        let downstream_states = post_rows
            .iter()
            .map(|row| {
                let admitted = row.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
                    && row.failure_code == sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE
                    && row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                    && row.rank_eligible == 1;
                if admitted {
                    sys::BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE
                } else {
                    sys::BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE
                }
            })
            .collect::<Vec<_>>();
        let mut scorer_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut scorer_output = init(sys::bg_docking_scorer_v1_output_v1_init)?;
        scorer_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        scorer_output.rows = scorer_rows.as_mut_ptr();
        let mut validity_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut validity_output = init(sys::bg_docking_pose_validity_output_v1_init)?;
        validity_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        validity_output.rows = validity_rows.as_mut_ptr();
        let mut ranking_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut primary_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut valid_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut ranking_output = init(sys::bg_docking_stable_top_k_output_v1_init)?;
        ranking_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        ranking_output.primary_index_capacity = checked_count(CANDIDATE_COUNT)?;
        ranking_output.valid_index_capacity = checked_count(CANDIDATE_COUNT)?;
        ranking_output.rows = ranking_rows.as_mut_ptr();
        ranking_output.primary_slot_indices = primary_indices.as_mut_ptr();
        ranking_output.valid_slot_indices = valid_indices.as_mut_ptr();
        let mut downstream_batch = init(sys::bg_docking_scorer_v1_candidate_batch_soa_v1_init)?;
        downstream_batch.candidate_count = checked_count(CANDIDATE_COUNT)?;
        downstream_batch.ligand_atom_count = ligand_count_u64;
        downstream_batch.candidate_state = downstream_states.as_ptr();
        downstream_batch.x_angstrom = final_coordinates[0].as_ptr();
        downstream_batch.y_angstrom = final_coordinates[1].as_ptr();
        downstream_batch.z_angstrom = final_coordinates[2].as_ptr();
        // SAFETY: every descriptor and exact-capacity buffer remains live for the call.
        status_result(unsafe {
            sys::bg_docking_fixed64_downstream_v1_run(
                self.context_lease.raw_handle(),
                self.handles.downstream.as_ptr(),
                &downstream_batch,
                final_quaternions[0].as_ptr(),
                final_quaternions[1].as_ptr(),
                final_quaternions[2].as_ptr(),
                final_quaternions[3].as_ptr(),
                &mut scorer_output,
                &mut validity_output,
                &mut ranking_output,
            )
        })?;

        let primary_count = usize::try_from(ranking_output.primary_index_count).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "preselected primary rank count overflows usize",
            )
        })?;
        let valid_count = usize::try_from(ranking_output.valid_index_count).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "preselected valid rank count overflows usize",
            )
        })?;
        if primary_count > CANDIDATE_COUNT || valid_count > CANDIDATE_COUNT {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "preselected native rank count exceeds fixed64 capacity",
            ));
        }
        primary_indices.truncate(primary_count);
        valid_indices.truncate(valid_count);

        let mut cluster_rows = vec![zeroed(); CANDIDATE_COUNT];
        let mut representative_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut top_k_indices = vec![0_u32; TOP_K_LIMIT];
        let mut cluster_output = init(sys::bg_docking_rmsd_cluster_output_v1_init)?;
        cluster_output.row_capacity = checked_count(CANDIDATE_COUNT)?;
        cluster_output.representative_index_capacity = checked_count(CANDIDATE_COUNT)?;
        cluster_output.top_k_index_capacity = checked_count(TOP_K_LIMIT)?;
        cluster_output.rows = cluster_rows.as_mut_ptr();
        cluster_output.representative_slot_indices = representative_indices.as_mut_ptr();
        cluster_output.top_k_slot_indices = top_k_indices.as_mut_ptr();
        let mut cluster_input = init(sys::bg_docking_rmsd_cluster_input_v1_init)?;
        cluster_input.candidate_count = checked_count(CANDIDATE_COUNT)?;
        cluster_input.ligand_atom_count = ligand_count_u64;
        cluster_input.valid_index_count = checked_count(valid_indices.len())?;
        cluster_input.top_k_limit = u32::try_from(TOP_K_LIMIT).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "preselected Top-K limit overflows u32",
            )
        })?;
        cluster_input.rmsd_threshold_angstrom = input.rmsd_threshold_angstrom;
        cluster_input.ranking_rows = ranking_rows.as_ptr();
        cluster_input.valid_slot_indices = valid_indices.as_ptr();
        cluster_input.x_angstrom = final_coordinates[0].as_ptr();
        cluster_input.y_angstrom = final_coordinates[1].as_ptr();
        cluster_input.z_angstrom = final_coordinates[2].as_ptr();
        // SAFETY: every descriptor and exact-capacity buffer remains live for the call.
        status_result(unsafe {
            sys::bg_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
                self.context_lease.raw_handle(),
                self.handles.ranker.as_ptr(),
                &cluster_input,
                &mut cluster_output,
            )
        })?;
        validate_component_output_counts(
            checked_count(CANDIDATE_COUNT)?,
            coordinate_count_u64,
            checked_count(MOVE_COUNT)?,
            &initial_output,
            &rigid_output,
            &torsion_output,
            &post_output,
            &scorer_output,
            &validity_output,
            &ranking_output,
            &cluster_output,
        )?;
        let representative_count = usize::try_from(cluster_output.representative_index_count)
            .map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "preselected representative count overflows usize",
                )
            })?;
        let top_k_count = usize::try_from(cluster_output.top_k_index_count).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "preselected Top-K count overflows usize",
            )
        })?;
        if representative_count > CANDIDATE_COUNT || top_k_count > TOP_K_LIMIT {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "preselected native cluster count exceeds output capacity",
            ));
        }
        representative_indices.truncate(representative_count);
        top_k_indices.truncate(top_k_count);

        validate_preselected_outputs(
            self,
            input,
            &effective_modes,
            initial_output.batch_receipt_sha256,
            &initial_rows,
            &rigid_rows,
            &rigid_coordinates,
            &torsion_rows,
            &torsion_moves,
            &torsion_coordinates,
            &refinement_rows,
            post_output.batch_receipt_sha256,
            &post_rows,
            &scorer_rows,
            &validity_rows,
            &ranking_rows,
            &cluster_rows,
            &primary_indices,
            &valid_indices,
            &representative_indices,
            &top_k_indices,
            &final_coordinates,
            &final_quaternions,
            receptor_count_u64,
            ligand_count_u64,
        )?;

        build_receipt(
            self,
            input,
            &raw_modes,
            &effective_modes,
            initial_output.batch_receipt_sha256,
            post_output.batch_receipt_sha256,
            source_quaternions,
            initial_rows,
            rigid_rows,
            rigid_coordinates,
            torsion_rows,
            torsion_moves,
            torsion_coordinates,
            refinement_rows,
            post_rows,
            scorer_rows,
            validity_rows,
            ranking_rows,
            cluster_rows,
            primary_indices,
            valid_indices,
            representative_indices,
            top_k_indices,
            final_coordinates,
            final_quaternions,
        )
    }
}

fn zeroed<T>() -> T {
    // SAFETY: callers use repr(C) ABI aggregates containing only zero-valid
    // numeric fields, pointers, and recursively zero-valid aggregates.
    unsafe { MaybeUninit::<T>::zeroed().assume_init() }
}

fn validate_preselected_input(
    pipeline: &Fixed64Pipeline,
    input: Fixed64PreselectedRunInput<'_>,
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    let coordinate_count = pipeline
        .ligand_atom_count
        .checked_mul(candidate_count)
        .ok_or_else(|| invalid("preselected coordinate denominator overflowed"))?;
    if !input.preselected.has_valid_receipt()
        || input.preselected.ligand_atom_count() != pipeline.ligand_atom_count
        || input.preselected.ligand_system_sha256() != pipeline.ligand_system_sha256
        || input.preselected.rows().len() != candidate_count
        || input.candidate_modes.len() != candidate_count
        || input.rigid_max_steps.len() != candidate_count
        || input.proposal_is_torsion_eligible.len() != candidate_count
        || input.torsion_max_steps.len() != candidate_count
        || input.baseline_torsion_angles_radians.len() != coordinate_count
        || !input.rmsd_threshold_angstrom.is_finite()
        || input.rmsd_threshold_angstrom <= 0.0
        || !finite(input.baseline_torsion_angles_radians)
        || input
            .proposal_is_torsion_eligible
            .iter()
            .any(|value| *value > 1)
        || !digest_present(&input.predeclared_refinement_policy_sha256)
        || !digest_present(&input.predeclared_post_refinement_admission_policy_sha256)
    {
        return Err(invalid(
            "preselected fixed64 input denominator, policy, or numeric field is invalid",
        ));
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn validate_component_output_counts(
    candidate_count: u64,
    coordinate_count: u64,
    move_count: u64,
    initial_admission: &sys::bg_docking_geometric_admission_output_v1,
    rigid: &sys::bg_docking_rigid_refinement_output_v1,
    torsion: &sys::bg_docking_torsion_v7_output_v1,
    post_admission: &sys::bg_docking_geometric_admission_output_v1,
    scorer: &sys::bg_docking_scorer_v1_output_v1,
    validity: &sys::bg_docking_pose_validity_output_v1,
    ranking: &sys::bg_docking_stable_top_k_output_v1,
    cluster: &sys::bg_docking_rmsd_cluster_output_v1,
) -> Result<()> {
    let top_k_limit = u64::from(sys::BG_DOCKING_STABLE_TOP_K_LIMIT);
    if [
        initial_admission.unit_system,
        rigid.unit_system,
        torsion.unit_system,
        post_admission.unit_system,
        scorer.unit_system,
        validity.unit_system,
        ranking.unit_system,
        cluster.unit_system,
    ]
    .iter()
    .any(|unit| *unit != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected native component returned a non-canonical unit system",
        ));
    }
    for (observed, expected, label) in [
        (
            initial_admission.row_capacity,
            candidate_count,
            "initial-admission row capacity",
        ),
        (
            initial_admission.row_count,
            candidate_count,
            "initial-admission row count",
        ),
        (rigid.row_capacity, candidate_count, "rigid row capacity"),
        (rigid.row_count, candidate_count, "rigid row count"),
        (
            rigid.coordinate_capacity,
            coordinate_count,
            "rigid coordinate capacity",
        ),
        (
            rigid.coordinate_count,
            coordinate_count,
            "rigid coordinate count",
        ),
        (
            torsion.row_capacity,
            candidate_count,
            "torsion row capacity",
        ),
        (torsion.row_count, candidate_count, "torsion row count"),
        (torsion.move_capacity, move_count, "torsion move capacity"),
        (torsion.move_count, move_count, "torsion move count"),
        (
            torsion.coordinate_capacity,
            coordinate_count,
            "torsion coordinate capacity",
        ),
        (
            torsion.coordinate_count,
            coordinate_count,
            "torsion coordinate count",
        ),
        (
            post_admission.row_capacity,
            candidate_count,
            "post-admission row capacity",
        ),
        (
            post_admission.row_count,
            candidate_count,
            "post-admission row count",
        ),
        (scorer.row_capacity, candidate_count, "scorer row capacity"),
        (scorer.row_count, candidate_count, "scorer row count"),
        (
            validity.row_capacity,
            candidate_count,
            "validity row capacity",
        ),
        (validity.row_count, candidate_count, "validity row count"),
        (
            ranking.row_capacity,
            candidate_count,
            "ranking row capacity",
        ),
        (ranking.row_count, candidate_count, "ranking row count"),
        (
            ranking.primary_index_capacity,
            candidate_count,
            "primary rank capacity",
        ),
        (
            ranking.valid_index_capacity,
            candidate_count,
            "valid rank capacity",
        ),
        (
            cluster.row_capacity,
            candidate_count,
            "cluster row capacity",
        ),
        (cluster.row_count, candidate_count, "cluster row count"),
        (
            cluster.representative_index_capacity,
            candidate_count,
            "cluster representative capacity",
        ),
        (
            cluster.top_k_index_capacity,
            top_k_limit,
            "cluster Top-K capacity",
        ),
    ] {
        if observed != expected {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("preselected native {label} is {observed}, expected {expected}"),
            ));
        }
    }
    for (count, capacity, label) in [
        (
            ranking.primary_index_count,
            ranking.primary_index_capacity,
            "primary rank count",
        ),
        (
            ranking.valid_index_count,
            ranking.valid_index_capacity,
            "valid rank count",
        ),
        (
            cluster.representative_index_count,
            cluster.representative_index_capacity,
            "cluster representative count",
        ),
        (
            cluster.top_k_index_count,
            cluster.top_k_index_capacity,
            "cluster Top-K count",
        ),
    ] {
        if count > capacity {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("preselected native {label} exceeds its capacity"),
            ));
        }
    }
    require_authority_false(&[
        (
            initial_admission.molecular_execution_authorized,
            "initial-admission molecular execution",
        ),
        (
            initial_admission.reservation_authorized,
            "initial-admission reservation",
        ),
        (
            initial_admission.benchmark_execution_authorized,
            "initial-admission benchmark execution",
        ),
        (
            initial_admission.existing_rank_auto_change_authorized,
            "initial-admission rank mutation",
        ),
        (
            initial_admission.customer_pose_emission_authorized,
            "initial-admission pose emission",
        ),
        (
            initial_admission.production_claim_authorized,
            "initial-admission production claim",
        ),
        (
            initial_admission.scientific_claim_authorized,
            "initial-admission scientific claim",
        ),
        (
            rigid.molecular_execution_authorized,
            "rigid molecular execution",
        ),
        (
            rigid.existing_rank_auto_change_authorized,
            "rigid rank mutation",
        ),
        (
            rigid.customer_pose_emission_authorized,
            "rigid pose emission",
        ),
        (rigid.production_claim_authorized, "rigid production claim"),
        (
            torsion.molecular_execution_authorized,
            "torsion molecular execution",
        ),
        (
            torsion.existing_rank_auto_change_authorized,
            "torsion rank mutation",
        ),
        (
            torsion.customer_pose_emission_authorized,
            "torsion pose emission",
        ),
        (
            torsion.production_claim_authorized,
            "torsion production claim",
        ),
        (
            post_admission.molecular_execution_authorized,
            "post-admission molecular execution",
        ),
        (
            post_admission.reservation_authorized,
            "post-admission reservation",
        ),
        (
            post_admission.benchmark_execution_authorized,
            "post-admission benchmark execution",
        ),
        (
            post_admission.existing_rank_auto_change_authorized,
            "post-admission rank mutation",
        ),
        (
            post_admission.customer_pose_emission_authorized,
            "post-admission pose emission",
        ),
        (
            post_admission.production_claim_authorized,
            "post-admission production claim",
        ),
        (
            post_admission.scientific_claim_authorized,
            "post-admission scientific claim",
        ),
        (
            ranking.existing_rank_auto_change_authorized,
            "ranking mutation",
        ),
        (
            ranking.customer_pose_emission_authorized,
            "ranking pose emission",
        ),
        (
            ranking.production_claim_authorized,
            "ranking production claim",
        ),
        (
            cluster.existing_rank_auto_change_authorized,
            "cluster rank mutation",
        ),
        (
            cluster.customer_pose_emission_authorized,
            "cluster pose emission",
        ),
        (
            cluster.production_claim_authorized,
            "cluster production claim",
        ),
    ])?;
    Ok(())
}

fn assign_rigid_output_channels(
    output: &mut sys::bg_docking_rigid_refinement_output_v1,
    channels: &mut [Vec<f64>; 12],
) {
    output.selected_x_angstrom = channels[0].as_mut_ptr();
    output.selected_y_angstrom = channels[1].as_mut_ptr();
    output.selected_z_angstrom = channels[2].as_mut_ptr();
    output.comparison_v2_x_angstrom = channels[3].as_mut_ptr();
    output.comparison_v2_y_angstrom = channels[4].as_mut_ptr();
    output.comparison_v2_z_angstrom = channels[5].as_mut_ptr();
    output.baseline_v3_x_angstrom = channels[6].as_mut_ptr();
    output.baseline_v3_y_angstrom = channels[7].as_mut_ptr();
    output.baseline_v3_z_angstrom = channels[8].as_mut_ptr();
    output.clearance_v4_x_angstrom = channels[9].as_mut_ptr();
    output.clearance_v4_y_angstrom = channels[10].as_mut_ptr();
    output.clearance_v4_z_angstrom = channels[11].as_mut_ptr();
}

fn assign_torsion_output_channels(
    output: &mut sys::bg_docking_torsion_v7_output_v1,
    channels: &mut [Vec<f64>; 8],
) {
    output.optimized_x_angstrom = channels[0].as_mut_ptr();
    output.optimized_y_angstrom = channels[1].as_mut_ptr();
    output.optimized_z_angstrom = channels[2].as_mut_ptr();
    output.optimized_torsion_angles_radians = channels[3].as_mut_ptr();
    output.final_x_angstrom = channels[4].as_mut_ptr();
    output.final_y_angstrom = channels[5].as_mut_ptr();
    output.final_z_angstrom = channels[6].as_mut_ptr();
    output.final_torsion_angles_radians = channels[7].as_mut_ptr();
}

fn mode_uses_v6(mode: i32) -> bool {
    matches!(
        mode,
        sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE
            | sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE
    )
}

fn compose_quaternion(source: [f64; 4], rotation: [f64; 3]) -> Result<[f64; 4]> {
    let angle =
        (rotation[0] * rotation[0] + rotation[1] * rotation[1] + rotation[2] * rotation[2]).sqrt();
    if !angle.is_finite() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected rigid rotation cannot produce a finite quaternion",
        ));
    }
    if angle == 0.0 {
        return Ok(source);
    }
    let scale = (0.5 * angle).sin() / angle;
    let delta = [
        rotation[0] * scale,
        rotation[1] * scale,
        rotation[2] * scale,
        (0.5 * angle).cos(),
    ];
    let mut result = [
        delta[3] * source[0] + delta[0] * source[3] + delta[1] * source[2] - delta[2] * source[1],
        delta[3] * source[1] - delta[0] * source[2] + delta[1] * source[3] + delta[2] * source[0],
        delta[3] * source[2] + delta[0] * source[1] - delta[1] * source[0] + delta[2] * source[3],
        delta[3] * source[3] - delta[0] * source[0] - delta[1] * source[1] - delta[2] * source[2],
    ];
    for component in &mut result {
        if *component == 0.0 {
            *component = 0.0;
        }
    }
    Ok(result)
}

#[allow(clippy::too_many_arguments)]
fn materialize_refinement_rows(
    ligand_count: usize,
    modes: &[i32],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    rigid_coordinates: &[Vec<f64>; 12],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    torsion_coordinates: &[Vec<f64>; 8],
    source_quaternions: [&[f64]; 4],
    rows: &mut [sys::bg_docking_fixed64_refinement_row_v1],
    final_coordinates: &mut [Vec<f64>; 3],
    final_quaternions: &mut [Vec<f64>; 4],
) -> Result<()> {
    for (slot, row) in rows.iter_mut().enumerate() {
        row.slot_index = u32::try_from(slot).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "preselected slot index overflows u32",
            )
        })?;
        row.rigid_failure_code = rigid_rows[slot].failure_code;
        row.selected_rigid_profile = rigid_rows[slot].selected_profile;
        let rigid_ready = rigid_rows[slot].status == sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
        let v6_mode = mode_uses_v6(modes[slot]);
        row.torsion_v7_applicable = u8::from(rigid_ready && v6_mode);
        let selected_channels = if !rigid_ready {
            row.status = sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE;
            row.failure_stage = sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_RIGID;
            None
        } else if v6_mode && torsion_rows[slot].status != sys::BG_DOCKING_TORSION_V7_ROW_REFINED {
            row.status = sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE;
            row.failure_stage = sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_TORSION_V7;
            row.torsion_v7_failure_code = torsion_rows[slot].failure_code;
            None
        } else {
            row.status = sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
            row.failure_stage = sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE;
            row.coordinate_available = 1;
            row.downstream_candidate_state = sys::BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
            if v6_mode {
                row.coordinate_origin =
                    sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_TORSION_V7_FINAL;
                row.torsion_v7_selected = torsion_rows[slot].torsion_selected;
                Some([4_usize, 5, 6])
            } else {
                row.coordinate_origin =
                    sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED;
                Some([0_usize, 1, 2])
            }
        };
        let Some(selected_channels) = selected_channels else {
            continue;
        };
        let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "preselected coordinate offset overflowed",
            )
        })?;
        let end = begin.checked_add(ligand_count).ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "preselected coordinate end overflowed",
            )
        })?;
        let channels: [&[f64]; 3] = if v6_mode {
            [
                &torsion_coordinates[selected_channels[0]],
                &torsion_coordinates[selected_channels[1]],
                &torsion_coordinates[selected_channels[2]],
            ]
        } else {
            [
                &rigid_coordinates[selected_channels[0]],
                &rigid_coordinates[selected_channels[1]],
                &rigid_coordinates[selected_channels[2]],
            ]
        };
        for axis in 0..3 {
            final_coordinates[axis][begin..end].copy_from_slice(&channels[axis][begin..end]);
        }
        let source = [
            source_quaternions[0][slot],
            source_quaternions[1][slot],
            source_quaternions[2][slot],
            source_quaternions[3][slot],
        ];
        let quaternion = compose_quaternion(
            source,
            rigid_rows[slot].selected.total_rotation_vector_radians,
        )?;
        for axis in 0..4 {
            final_quaternions[axis][slot] = quaternion[axis];
        }
        let segment = PositionSoa::new(
            &final_coordinates[0][begin..end],
            &final_coordinates[1][begin..end],
            &final_coordinates[2][begin..end],
        );
        row.coordinate_sha256 = canonical_coordinate_sha256(segment);
    }
    Ok(())
}

// Remaining validation and receipt construction live below to keep the ABI
// orchestration above readable.

#[allow(clippy::too_many_arguments)]
fn validate_preselected_outputs(
    pipeline: &Fixed64Pipeline,
    input: Fixed64PreselectedRunInput<'_>,
    effective_modes: &[i32],
    initial_batch_receipt_sha256: Sha256,
    initial_rows: &[sys::bg_docking_geometric_admission_row_v1],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    rigid_coordinates: &[Vec<f64>; 12],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    torsion_moves: &[sys::bg_docking_torsion_v7_move_v1],
    torsion_coordinates: &[Vec<f64>; 8],
    refinement_rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    post_batch_receipt_sha256: Sha256,
    post_rows: &[sys::bg_docking_geometric_admission_row_v1],
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    cluster_rows: &[sys::bg_docking_rmsd_cluster_row_v1],
    primary_indices: &[u32],
    valid_indices: &[u32],
    representative_indices: &[u32],
    top_k_indices: &[u32],
    final_coordinates: &[Vec<f64>; 3],
    final_quaternions: &[Vec<f64>; 4],
    receptor_count: u64,
    ligand_count: u64,
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    let exact_pairs = receptor_count.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::CapacityOverflow,
            "preselected exact pair count overflowed",
        )
    })?;
    let source_coordinates = [
        input.preselected.x_angstrom(),
        input.preselected.y_angstrom(),
        input.preselected.z_angstrom(),
    ];
    let expected_receipt_graph = ExpectedPipelineReceiptGraph {
        allocation_inventory_sha256: [0; 32],
        allocation_receipt_sha256: [0; 32],
        source_bundle_receipt_sha256: input.preselected.receipt_sha256(),
        admission_context_receipt_sha256: pipeline.expected_admission_context_receipt_sha256,
        refinement_context_receipt_sha256: pipeline.expected_refinement_context_receipt_sha256,
        scorer_context_receipt_sha256: pipeline.expected_scorer_context_receipt_sha256,
        validity_context_receipt_sha256: pipeline.expected_validity_context_receipt_sha256,
        component_binding_receipt_sha256: pipeline.expected_component_binding_receipt_sha256,
        refinement_policy_receipt_sha256: input.predeclared_refinement_policy_sha256,
        post_admission_policy_receipt_sha256: input
            .predeclared_post_refinement_admission_policy_sha256,
        authority_input_receipt_sha256: pipeline.authority_input_receipt_sha256,
        receptor_system_sha256: pipeline.receptor_system_sha256,
        ligand_system_sha256: pipeline.ligand_system_sha256,
        backend_receipt_sha256: pipeline.backend_receipt_sha256,
        backend: pipeline.backend,
        receptor_atom_count: receptor_count,
        ligand_atom_count: ligand_count,
        ligand_heavy_atom_count: pipeline.ligand_heavy_atom_count,
        geometric_max_batch_exact_pair_evaluations: pipeline
            .geometric_max_batch_exact_pair_evaluations,
        pocket_center_angstrom: pipeline.pocket_center_angstrom,
        pocket_radius_angstrom: pipeline.geometric_input.pocket_radius_angstrom(),
        geometric_hard_rejection_minimum_vdw_ratio: pipeline
            .geometric_hard_rejection_minimum_vdw_ratio,
    };
    for slot in 0..candidate_count {
        let producer_status = match input.preselected.rows()[slot].state() {
            NativeSamplingFunnelSelectedState::Selected { .. } => {
                sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
            }
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => {
                sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
            }
        };
        validate_geometric_admission_row_semantics(
            &initial_rows[slot],
            producer_status,
            receptor_count,
            ligand_count,
            pipeline.ligand_heavy_atom_count,
            exact_pairs,
            pipeline.geometric_hard_rejection_minimum_vdw_ratio,
            pipeline.backend,
            &pipeline.geometric_input,
            source_coordinates,
            slot,
        )?;
        if initial_rows[slot].row_receipt_sha256
            != canonical_geometric_row_receipt(
                &expected_receipt_graph,
                producer_status,
                source_coordinates,
                slot,
                &initial_rows[slot],
            )?
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "preselected initial-admission row receipt was not independently rederived",
            ));
        }
        validate_rigid_row_semantics(
            &rigid_rows[slot],
            effective_modes[slot],
            input.rigid_max_steps[slot],
            rigid_coordinates,
            slot,
            ligand_count,
        )?;
        validate_independent_rigid_replay(
            pipeline.backend,
            &rigid_rows[slot],
            effective_modes[slot],
            input.rigid_max_steps[slot],
            source_coordinates,
            rigid_coordinates,
            slot,
            ligand_count,
            &pipeline.geometric_input,
            pipeline.rigid_v2_config,
            pipeline.rigid_v3_config,
            pipeline.rigid_clearance_config,
        )?;
        let synthetic_status = if refinement_rows[slot].status
            == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY
            && refinement_rows[slot].coordinate_available == 1
        {
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
        } else {
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
        };
        validate_geometric_admission_row_semantics(
            &post_rows[slot],
            synthetic_status,
            receptor_count,
            ligand_count,
            pipeline.ligand_heavy_atom_count,
            exact_pairs,
            pipeline.geometric_hard_rejection_minimum_vdw_ratio,
            pipeline.backend,
            &pipeline.geometric_input,
            [
                final_coordinates[0].as_slice(),
                final_coordinates[1].as_slice(),
                final_coordinates[2].as_slice(),
            ],
            slot,
        )?;
        if post_rows[slot].row_receipt_sha256
            != canonical_geometric_row_receipt(
                &expected_receipt_graph,
                synthetic_status,
                [
                    final_coordinates[0].as_slice(),
                    final_coordinates[1].as_slice(),
                    final_coordinates[2].as_slice(),
                ],
                slot,
                &post_rows[slot],
            )?
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "preselected post-admission row receipt was not independently rederived",
            ));
        }
    }
    if initial_batch_receipt_sha256
        != canonical_geometric_batch_receipt_rows(&expected_receipt_graph, initial_rows)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected initial-admission batch receipt was not independently rederived",
        ));
    }
    if post_batch_receipt_sha256
        != canonical_geometric_batch_receipt_rows(&expected_receipt_graph, post_rows)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected post-admission batch receipt was not independently rederived",
        ));
    }
    validate_torsion_evidence(
        torsion_rows,
        torsion_moves,
        rigid_rows,
        input.proposal_is_torsion_eligible,
        input.torsion_max_steps,
        pipeline.maximum_torsion_steps,
        &pipeline.rotatable_child_atom_indices,
        torsion_coordinates,
        rigid_coordinates,
        input.baseline_torsion_angles_radians,
        ligand_count,
    )?;
    let mut synthetic_producer_rows: Vec<sys::bg_docking_fixed64_producer_row_v1> =
        vec![zeroed(); candidate_count];
    for (slot, row) in synthetic_producer_rows.iter_mut().enumerate() {
        row.placement_quaternion_x = input.preselected.source_quaternion_x()[slot];
        row.placement_quaternion_y = input.preselected.source_quaternion_y()[slot];
        row.placement_quaternion_z = input.preselected.source_quaternion_z()[slot];
        row.placement_quaternion_w = input.preselected.source_quaternion_w()[slot];
    }
    validate_refinement_evidence(
        refinement_rows,
        &synthetic_producer_rows,
        rigid_rows,
        torsion_rows,
        effective_modes,
        [
            rigid_coordinates[0].as_slice(),
            rigid_coordinates[1].as_slice(),
            rigid_coordinates[2].as_slice(),
        ],
        [
            torsion_coordinates[4].as_slice(),
            torsion_coordinates[5].as_slice(),
            torsion_coordinates[6].as_slice(),
        ],
        [
            final_coordinates[0].as_slice(),
            final_coordinates[1].as_slice(),
            final_coordinates[2].as_slice(),
        ],
        [
            final_quaternions[0].as_slice(),
            final_quaternions[1].as_slice(),
            final_quaternions[2].as_slice(),
            final_quaternions[3].as_slice(),
        ],
        ligand_count,
        pipeline.backend,
    )?;
    validate_scorer_and_validity_evidence(
        scorer_rows,
        validity_rows,
        ranking_rows,
        refinement_rows,
        post_rows,
        ligand_count,
        receptor_count,
        pipeline.validity_exclusion_count,
        pipeline.validity_chirality_count,
        pipeline.validity_contact_cell_size_angstrom,
        &pipeline.validity_receptor_cells,
        [
            final_coordinates[0].as_slice(),
            final_coordinates[1].as_slice(),
            final_coordinates[2].as_slice(),
        ],
        [
            final_quaternions[0].as_slice(),
            final_quaternions[1].as_slice(),
            final_quaternions[2].as_slice(),
            final_quaternions[3].as_slice(),
        ],
        &pipeline.scorer_context,
        &pipeline.validity_context,
        pipeline.backend,
    )?;
    let mut ranking_output = init(sys::bg_docking_stable_top_k_output_v1_init)?;
    ranking_output.primary_index_count = checked_count(primary_indices.len())?;
    ranking_output.valid_index_count = checked_count(valid_indices.len())?;
    let mut cluster_output = init(sys::bg_docking_rmsd_cluster_output_v1_init)?;
    cluster_output.representative_index_count = checked_count(representative_indices.len())?;
    cluster_output.top_k_index_count = checked_count(top_k_indices.len())?;
    validate_index_evidence(
        &ranking_output,
        &cluster_output,
        scorer_rows,
        validity_rows,
        ranking_rows,
        cluster_rows,
        primary_indices,
        valid_indices,
        representative_indices,
        top_k_indices,
        input.rmsd_threshold_angstrom,
        [
            final_coordinates[0].as_slice(),
            final_coordinates[1].as_slice(),
            final_coordinates[2].as_slice(),
        ],
        ligand_count,
    )
}

fn policy_receipt(
    pipeline: &Fixed64Pipeline,
    input: Fixed64PreselectedRunInput<'_>,
    raw_modes: &[i32],
) -> Sha256 {
    policy_receipt_fields(
        input.preselected.receipt_sha256(),
        pipeline.expected_component_binding_receipt_sha256,
        input.predeclared_refinement_policy_sha256,
        input.predeclared_post_refinement_admission_policy_sha256,
        input.rmsd_threshold_angstrom,
        raw_modes,
        input.rigid_max_steps,
        input.proposal_is_torsion_eligible,
        input.torsion_max_steps,
        input.baseline_torsion_angles_radians,
    )
}

#[allow(clippy::too_many_arguments)]
fn policy_receipt_fields(
    preselected_receipt_sha256: Sha256,
    component_binding_receipt_sha256: Sha256,
    refinement_policy_sha256: Sha256,
    post_admission_policy_sha256: Sha256,
    rmsd_threshold_angstrom: f64,
    raw_modes: &[i32],
    rigid_max_steps: &[u64],
    proposal_is_torsion_eligible: &[u8],
    torsion_max_steps: &[u64],
    baseline_torsion_angles_radians: &[f64],
) -> Sha256 {
    let mut hash = CanonicalHasher::new(PRESELECTED_POLICY_SCHEMA_ID);
    hash.digest(preselected_receipt_sha256);
    hash.digest(component_binding_receipt_sha256);
    hash.digest(refinement_policy_sha256);
    hash.digest(post_admission_policy_sha256);
    hash.f64(rmsd_threshold_angstrom);
    hash.usize(raw_modes.len());
    for (slot, mode) in raw_modes.iter().enumerate() {
        hash.i32(*mode);
        hash.u64(rigid_max_steps[slot]);
        hash.byte(proposal_is_torsion_eligible[slot]);
        hash.u64(torsion_max_steps[slot]);
    }
    hash.usize(baseline_torsion_angles_radians.len());
    for value in baseline_torsion_angles_radians {
        hash.f64(*value);
    }
    hash.finish()
}

fn hash_geometric_evidence(hash: &mut CanonicalHasher, value: Fixed64GeometricEvidence) {
    hash.u32(value.slot_index);
    hash.i32(value.status);
    hash.i32(value.failure_code);
    hash.i32(value.decision);
    hash.byte(u8::from(value.rank_eligible));
    hash.u64(value.ligand_atom_count);
    hash.u64(value.receptor_atom_count);
    hash.u64(value.exact_pair_count);
    hash.u64(value.penetration_pair_count);
    hash.u64(value.unique_ligand_penetration_atom_count);
    hash.u64(value.unique_ligand_heavy_atom_penetration_count);
    hash.f64(value.raw_minimum_distance_angstrom);
    hash.f64(value.minimum_vdw_surface_gap_angstrom);
    hash.f64(value.minimum_vdw_ratio);
    hash.f64(value.sphere_overlap_proxy_angstrom3);
    hash.f64(value.pocket_escape_angstrom);
    hash.digest(value.row_receipt_sha256);
}

fn hash_position(hash: &mut CanonicalHasher, value: &PositionSoaOwned) {
    hash_f64_channel(hash, &value.x_angstrom);
    hash_f64_channel(hash, &value.y_angstrom);
    hash_f64_channel(hash, &value.z_angstrom);
}

fn hash_quaternions(hash: &mut CanonicalHasher, values: &[Vec<f64>; 4]) {
    for channel in values {
        hash_f64_channel(hash, channel);
    }
}

fn backend_id(value: Backend) -> u8 {
    match value {
        Backend::Auto => 0,
        Backend::CppCpuReference => 1,
        Backend::RustCpu => 2,
        Backend::HipFast => 3,
        Backend::HipSafe => 4,
    }
}

fn hash_authority(hash: &mut CanonicalHasher, value: Fixed64AuthorityDisposition) {
    for flag in [
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
        hash.byte(u8::from(flag));
    }
}

fn validate_receipt_shape(value: &Fixed64PreselectedPipelineReceipt) -> Result<()> {
    let count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    let coordinate_count = value.ligand_atom_count.checked_mul(count).ok_or_else(|| {
        Error::local(
            ErrorCode::CapacityOverflow,
            "preselected receipt denominator overflowed",
        )
    })?;
    let exact_rows = [
        value.initial_admission_rows.len(),
        value.rigid_rows.len(),
        value.torsion_rows.len(),
        value.refinement_rows.len(),
        value.post_admission_rows.len(),
        value.scorer_rows.len(),
        value.validity_rows.len(),
        value.ranking_rows.len(),
        value.cluster_rows.len(),
        value.rows.len(),
    ]
    .iter()
    .all(|length| *length == count);
    let exact_policy = value.requested_refinement_modes.len() == count
        && value.rigid_max_steps.len() == count
        && value.proposal_is_torsion_eligible.len() == count
        && value.torsion_max_steps.len() == count
        && value.baseline_torsion_angles_radians.len() == coordinate_count
        && value.rmsd_threshold_angstrom.is_finite()
        && value.rmsd_threshold_angstrom > 0.0
        && finite(&value.baseline_torsion_angles_radians)
        && value
            .proposal_is_torsion_eligible
            .iter()
            .all(|value| *value <= 1)
        && value
            .torsion_max_steps
            .iter()
            .all(|steps| *steps <= value.maximum_torsion_steps)
        && digest_present(&value.predeclared_refinement_policy_sha256)
        && digest_present(&value.predeclared_post_refinement_admission_policy_sha256);
    let coordinate_channels = [
        &value.source_coordinates,
        &value.rigid_coordinates.selected,
        &value.rigid_coordinates.comparison_v2,
        &value.rigid_coordinates.baseline_v3,
        &value.rigid_coordinates.clearance_v4,
        &value.torsion_coordinates.optimized,
        &value.torsion_coordinates.final_state,
        &value.final_coordinates,
    ]
    .iter()
    .all(|coordinates| {
        coordinates.x_angstrom.len() == coordinate_count
            && coordinates.y_angstrom.len() == coordinate_count
            && coordinates.z_angstrom.len() == coordinate_count
    });
    let authority_valid = value.authority.denominator_preserved
        && !value.authority.result_dependent_input_consumed
        && !value.authority.fallback_allowed
        && !value.authority.molecular_execution_authorized
        && !value.authority.reservation_authorized
        && !value.authority.benchmark_execution_authorized
        && !value.authority.existing_rank_auto_change_authorized
        && !value.authority.customer_pose_emission_authorized
        && !value.authority.production_claim_authorized
        && !value.authority.scientific_claim_authorized;
    if value.ligand_atom_count == 0
        || !digest_present(&value.ligand_system_sha256)
        || !exact_rows
        || !exact_policy
        || !coordinate_channels
        || value.torsion_moves.len() != count * sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize
        || value
            .source_quaternions
            .iter()
            .chain(value.final_quaternions.iter())
            .any(|channel| channel.len() != count)
        || !authority_valid
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected pipeline receipt shape or authority is invalid",
        ));
    }
    validate_receipt_evidence(value)
}

fn validate_receipt_evidence(value: &Fixed64PreselectedPipelineReceipt) -> Result<()> {
    let rigid_rows = value
        .rigid_rows
        .iter()
        .copied()
        .map(abi_rigid_row_from_evidence)
        .collect::<Vec<_>>();
    let torsion_rows = value
        .torsion_rows
        .iter()
        .copied()
        .map(abi_torsion_row_from_evidence)
        .collect::<Vec<_>>();
    let torsion_moves = value
        .torsion_moves
        .iter()
        .copied()
        .map(abi_torsion_move_from_evidence)
        .collect::<Vec<_>>();
    let refinement_rows = value
        .refinement_rows
        .iter()
        .copied()
        .map(abi_refinement_row_from_evidence)
        .collect::<Vec<_>>();
    let scorer_rows = value
        .scorer_rows
        .iter()
        .copied()
        .map(abi_scorer_row_from_evidence)
        .collect::<Vec<_>>();
    let validity_rows = value
        .validity_rows
        .iter()
        .copied()
        .map(abi_validity_row_from_evidence)
        .collect::<Vec<_>>();
    let ranking_rows = value
        .ranking_rows
        .iter()
        .copied()
        .map(abi_ranking_row_from_evidence)
        .collect::<Vec<_>>();
    let cluster_rows = value
        .cluster_rows
        .iter()
        .copied()
        .map(abi_cluster_row_from_evidence)
        .collect::<Vec<_>>();
    let expected_policy_receipt = policy_receipt_fields(
        value.receipts.preselected_batch_receipt_sha256,
        value.receipts.component_binding_receipt_sha256,
        value.predeclared_refinement_policy_sha256,
        value.predeclared_post_refinement_admission_policy_sha256,
        value.rmsd_threshold_angstrom,
        &value.requested_refinement_modes,
        &value.rigid_max_steps,
        &value.proposal_is_torsion_eligible,
        &value.torsion_max_steps,
        &value.baseline_torsion_angles_radians,
    );
    if value.receipts.policy_receipt_sha256 != expected_policy_receipt {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected pipeline policy receipt changed",
        ));
    }
    let rigid_coordinates: [&[f64]; 12] = [
        value.rigid_coordinates.selected.x_angstrom.as_slice(),
        value.rigid_coordinates.selected.y_angstrom.as_slice(),
        value.rigid_coordinates.selected.z_angstrom.as_slice(),
        value.rigid_coordinates.comparison_v2.x_angstrom.as_slice(),
        value.rigid_coordinates.comparison_v2.y_angstrom.as_slice(),
        value.rigid_coordinates.comparison_v2.z_angstrom.as_slice(),
        value.rigid_coordinates.baseline_v3.x_angstrom.as_slice(),
        value.rigid_coordinates.baseline_v3.y_angstrom.as_slice(),
        value.rigid_coordinates.baseline_v3.z_angstrom.as_slice(),
        value.rigid_coordinates.clearance_v4.x_angstrom.as_slice(),
        value.rigid_coordinates.clearance_v4.y_angstrom.as_slice(),
        value.rigid_coordinates.clearance_v4.z_angstrom.as_slice(),
    ];
    let torsion_coordinates: [&[f64]; 8] = [
        value.torsion_coordinates.optimized.x_angstrom.as_slice(),
        value.torsion_coordinates.optimized.y_angstrom.as_slice(),
        value.torsion_coordinates.optimized.z_angstrom.as_slice(),
        value
            .torsion_coordinates
            .optimized_torsion_angles_radians
            .as_slice(),
        value.torsion_coordinates.final_state.x_angstrom.as_slice(),
        value.torsion_coordinates.final_state.y_angstrom.as_slice(),
        value.torsion_coordinates.final_state.z_angstrom.as_slice(),
        value
            .torsion_coordinates
            .final_torsion_angles_radians
            .as_slice(),
    ];
    let final_coordinates = [
        value.final_coordinates.x_angstrom.as_slice(),
        value.final_coordinates.y_angstrom.as_slice(),
        value.final_coordinates.z_angstrom.as_slice(),
    ];
    let final_quaternions = [
        value.final_quaternions[0].as_slice(),
        value.final_quaternions[1].as_slice(),
        value.final_quaternions[2].as_slice(),
        value.final_quaternions[3].as_slice(),
    ];
    let rigid_coordinates_owned: [Vec<f64>; 12] =
        std::array::from_fn(|index| rigid_coordinates[index].to_vec());
    let torsion_coordinates_owned: [Vec<f64>; 8] =
        std::array::from_fn(|index| torsion_coordinates[index].to_vec());
    let mut refinement_batch = CanonicalHasher::new(
        "betelgeuze.engine_v2_native_fixed64_preselected_refinement_batch/1.0.0",
    );
    let mut scorer_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_preselected_scorer_batch/1.0.0");
    let mut validity_batch = CanonicalHasher::new(
        "betelgeuze.engine_v2_native_fixed64_preselected_validity_batch/1.0.0",
    );
    let mut ranking_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_preselected_ranking_batch/1.0.0");
    let mut cluster_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_preselected_cluster_batch/1.0.0");
    for slot in 0..value.rows.len() {
        let row = &value.rows[slot];
        validate_rigid_row_semantics(
            &rigid_rows[slot],
            row.effective_refinement_mode,
            value.rigid_max_steps[slot],
            &rigid_coordinates_owned,
            slot,
            value.ligand_atom_count as u64,
        )?;
        let rigid_budget_valid = [
            row.rigid.selected,
            row.rigid.comparison_v2,
            row.rigid.baseline_v3,
            row.rigid.clearance_v4,
        ]
        .iter()
        .all(|profile| profile.accepted_steps <= value.rigid_max_steps[slot]);
        let torsion_budget_valid = row.torsion.torsion_step_budget <= value.torsion_max_steps[slot]
            && row.torsion.evaluated_torsion_steps <= value.torsion_max_steps[slot]
            && row.torsion.accepted_torsion_steps <= row.torsion.evaluated_torsion_steps;
        if row.slot_index as usize != slot
            || row.requested_refinement_mode != value.requested_refinement_modes[slot]
            || (row.effective_refinement_mode != row.requested_refinement_mode
                && row.effective_refinement_mode
                    != sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE)
            || !rigid_budget_valid
            || !torsion_budget_valid
            || row.initial_admission != value.initial_admission_rows[slot]
            || row.rigid != value.rigid_rows[slot]
            || row.torsion != value.torsion_rows[slot]
            || row.refinement != value.refinement_rows[slot]
            || row.post_admission != value.post_admission_rows[slot]
            || row.scorer != value.scorer_rows[slot]
            || row.validity != value.validity_rows[slot]
            || row.ranking != value.ranking_rows[slot]
            || row.cluster != value.cluster_rows[slot]
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "preselected pipeline component evidence is not row-aligned",
            ));
        }
        let refinement_digest = canonical_refinement_evidence(
            slot,
            value.ligand_atom_count,
            &rigid_rows[slot],
            &torsion_rows[slot],
            &torsion_moves,
            &refinement_rows[slot],
            rigid_coordinates,
            torsion_coordinates,
            final_coordinates,
            final_quaternions,
        )?;
        let scorer_digest = canonical_scorer_evidence(&scorer_rows[slot]);
        let validity_digest = canonical_validity_evidence(&validity_rows[slot]);
        let ranking_digest = canonical_ranking_evidence(&ranking_rows[slot]);
        let cluster_digest = canonical_cluster_evidence(&cluster_rows[slot]);
        let mut row_hash = CanonicalHasher::new(PRESELECTED_ROW_SCHEMA_ID);
        row_hash.digest(value.receipts.preselected_batch_receipt_sha256);
        row_hash.usize(slot);
        row_hash.i32(row.requested_refinement_mode);
        row_hash.i32(row.effective_refinement_mode);
        row_hash.digest(row.initial_admission.row_receipt_sha256);
        row_hash.digest(refinement_digest);
        row_hash.digest(row.post_admission.row_receipt_sha256);
        row_hash.digest(scorer_digest);
        row_hash.digest(validity_digest);
        row_hash.digest(ranking_digest);
        row_hash.digest(cluster_digest);
        if row.refinement_evidence_sha256 != refinement_digest
            || row.scorer_evidence_sha256 != scorer_digest
            || row.validity_evidence_sha256 != validity_digest
            || row.ranking_evidence_sha256 != ranking_digest
            || row.cluster_evidence_sha256 != cluster_digest
            || row.row_receipt_sha256 != row_hash.finish()
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "preselected pipeline component evidence digest changed",
            ));
        }
        refinement_batch.digest(refinement_digest);
        scorer_batch.digest(scorer_digest);
        validity_batch.digest(validity_digest);
        ranking_batch.digest(ranking_digest);
        cluster_batch.digest(cluster_digest);
    }
    validate_torsion_evidence(
        &torsion_rows,
        &torsion_moves,
        &rigid_rows,
        &value.proposal_is_torsion_eligible,
        &value.torsion_max_steps,
        value.maximum_torsion_steps,
        &value.rotatable_child_atom_indices,
        &torsion_coordinates_owned,
        &rigid_coordinates_owned,
        &value.baseline_torsion_angles_radians,
        value.ligand_atom_count as u64,
    )?;
    let mut producer_rows: Vec<sys::bg_docking_fixed64_producer_row_v1> =
        vec![zeroed(); value.rows.len()];
    for (slot, producer) in producer_rows.iter_mut().enumerate() {
        producer.placement_quaternion_x = value.source_quaternions[0][slot];
        producer.placement_quaternion_y = value.source_quaternions[1][slot];
        producer.placement_quaternion_z = value.source_quaternions[2][slot];
        producer.placement_quaternion_w = value.source_quaternions[3][slot];
    }
    let effective_modes = value
        .rows
        .iter()
        .map(|row| row.effective_refinement_mode)
        .collect::<Vec<_>>();
    validate_refinement_evidence(
        &refinement_rows,
        &producer_rows,
        &rigid_rows,
        &torsion_rows,
        &effective_modes,
        [
            rigid_coordinates[0],
            rigid_coordinates[1],
            rigid_coordinates[2],
        ],
        [
            torsion_coordinates[4],
            torsion_coordinates[5],
            torsion_coordinates[6],
        ],
        final_coordinates,
        final_quaternions,
        value.ligand_atom_count as u64,
        value.backend,
    )?;
    let mut ranking_output = init(sys::bg_docking_stable_top_k_output_v1_init)?;
    ranking_output.primary_index_count = checked_count(value.primary_slot_indices.len())?;
    ranking_output.valid_index_count = checked_count(value.valid_slot_indices.len())?;
    let mut cluster_output = init(sys::bg_docking_rmsd_cluster_output_v1_init)?;
    cluster_output.representative_index_count =
        checked_count(value.representative_slot_indices.len())?;
    cluster_output.top_k_index_count = checked_count(value.top_k_slot_indices.len())?;
    validate_index_evidence(
        &ranking_output,
        &cluster_output,
        &scorer_rows,
        &validity_rows,
        &ranking_rows,
        &cluster_rows,
        &value.primary_slot_indices,
        &value.valid_slot_indices,
        &value.representative_slot_indices,
        &value.top_k_slot_indices,
        value.rmsd_threshold_angstrom,
        final_coordinates,
        value.ligand_atom_count as u64,
    )?;
    let selected_count = value
        .rows
        .iter()
        .filter(|row| {
            matches!(
                row.selected_state,
                NativeSamplingFunnelSelectedState::Selected { .. }
            )
        })
        .count() as u64;
    let initial_admitted_count = value
        .initial_admission_rows
        .iter()
        .filter(|row| {
            row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                && row.rank_eligible
        })
        .count() as u64;
    let refined_count = value
        .refinement_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY)
        .count() as u64;
    let post_admitted_count = value
        .post_admission_rows
        .iter()
        .filter(|row| {
            row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                && row.rank_eligible
        })
        .count() as u64;
    let scored_count = value
        .scorer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED)
        .count() as u64;
    let valid_count = value
        .validity_rows
        .iter()
        .filter(|row| {
            row.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED && row.blocker_mask == 0
        })
        .count() as u64;
    let multi_anchor_consumed = value.rows.iter().any(|row| {
        row.lane == NativeSamplingFunnelLane::MultiAnchor
            && matches!(
                row.selected_state,
                NativeSamplingFunnelSelectedState::Selected { .. }
            )
    });
    let post_rejected_count = refined_count
        .checked_sub(post_admitted_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "preselected post-admission count exceeds the refined count",
            )
        })?;
    if value.unit_system != UnitSystem::AngstromKcalMol
        || value.selected_count != selected_count
        || value.lane_shortfall_count != value.rows.len() as u64 - selected_count
        || value.initial_admitted_count != initial_admitted_count
        || value.refined_count != refined_count
        || value.post_admitted_count != post_admitted_count
        || value.post_rejected_count != post_rejected_count
        || value.scored_count != scored_count
        || value.valid_count != valid_count
        || value.authority.multi_anchor_consumed != multi_anchor_consumed
        || value.receipts.refinement_batch_receipt_sha256 != refinement_batch.finish()
        || value.receipts.scorer_batch_receipt_sha256 != scorer_batch.finish()
        || value.receipts.validity_batch_receipt_sha256 != validity_batch.finish()
        || value.receipts.ranking_batch_receipt_sha256 != ranking_batch.finish()
        || value.receipts.cluster_batch_receipt_sha256 != cluster_batch.finish()
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "preselected pipeline counts or evidence batches changed",
        ));
    }
    Ok(())
}

fn derive_pipeline_receipt(value: &Fixed64PreselectedPipelineReceipt) -> Result<Sha256> {
    validate_receipt_shape(value)?;
    let mut hash = CanonicalHasher::new(FIXED64_PRESELECTED_PIPELINE_PROFILE_ID);
    hash.byte(backend_id(value.backend));
    hash.digest(value.ligand_system_sha256);
    hash.usize(value.ligand_atom_count);
    for count in [
        value.selected_count,
        value.lane_shortfall_count,
        value.initial_admitted_count,
        value.refined_count,
        value.post_admitted_count,
        value.post_rejected_count,
        value.scored_count,
        value.valid_count,
    ] {
        hash.u64(count);
    }
    hash.f64(value.rmsd_threshold_angstrom);
    hash.usize(value.requested_refinement_modes.len());
    for slot in 0..value.requested_refinement_modes.len() {
        hash.i32(value.requested_refinement_modes[slot]);
        hash.u64(value.rigid_max_steps[slot]);
        hash.byte(value.proposal_is_torsion_eligible[slot]);
        hash.u64(value.torsion_max_steps[slot]);
    }
    hash_f64_channel(&mut hash, &value.baseline_torsion_angles_radians);
    hash.u64(value.maximum_torsion_steps);
    hash.usize(value.rotatable_child_atom_indices.len());
    for atom_index in &value.rotatable_child_atom_indices {
        hash.u64(*atom_index);
    }
    hash.digest(value.predeclared_refinement_policy_sha256);
    hash.digest(value.predeclared_post_refinement_admission_policy_sha256);
    for digest in [
        value.receipts.preselected_batch_receipt_sha256,
        value.receipts.admission_context_receipt_sha256,
        value.receipts.refinement_context_receipt_sha256,
        value.receipts.scorer_context_receipt_sha256,
        value.receipts.validity_context_receipt_sha256,
        value.receipts.component_binding_receipt_sha256,
        value.receipts.policy_receipt_sha256,
        value.receipts.initial_admission_batch_receipt_sha256,
        value.receipts.refinement_batch_receipt_sha256,
        value.receipts.post_admission_batch_receipt_sha256,
        value.receipts.scorer_batch_receipt_sha256,
        value.receipts.validity_batch_receipt_sha256,
        value.receipts.ranking_batch_receipt_sha256,
        value.receipts.cluster_batch_receipt_sha256,
    ] {
        hash.digest(digest);
    }
    hash_position(&mut hash, &value.source_coordinates);
    hash_quaternions(&mut hash, &value.source_quaternions);
    for coordinates in [
        &value.rigid_coordinates.selected,
        &value.rigid_coordinates.comparison_v2,
        &value.rigid_coordinates.baseline_v3,
        &value.rigid_coordinates.clearance_v4,
        &value.torsion_coordinates.optimized,
        &value.torsion_coordinates.final_state,
        &value.final_coordinates,
    ] {
        hash_position(&mut hash, coordinates);
    }
    hash_f64_channel(
        &mut hash,
        &value.torsion_coordinates.optimized_torsion_angles_radians,
    );
    hash_f64_channel(
        &mut hash,
        &value.torsion_coordinates.final_torsion_angles_radians,
    );
    hash_quaternions(&mut hash, &value.final_quaternions);
    hash.usize(value.rows.len());
    for row in &value.rows {
        hash.u32(row.slot_index);
        hash.string(row.lane.id());
        match row.selected_state {
            NativeSamplingFunnelSelectedState::Selected {
                source_pool_index,
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
            } => {
                hash.byte(0);
                hash.usize(source_pool_index);
                hash.digest(source_sha256);
                hash.digest(proposal_sha256);
                hash.digest(coordinate_sha256);
            }
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => hash.byte(1),
        }
        hash.i32(row.requested_refinement_mode);
        hash.i32(row.effective_refinement_mode);
        hash_geometric_evidence(&mut hash, row.initial_admission);
        hash.digest(row.refinement_evidence_sha256);
        hash_geometric_evidence(&mut hash, row.post_admission);
        hash.digest(row.scorer_evidence_sha256);
        hash.digest(row.validity_evidence_sha256);
        hash.digest(row.ranking_evidence_sha256);
        hash.digest(row.cluster_evidence_sha256);
        hash.digest(row.row_receipt_sha256);
    }
    for indices in [
        &value.primary_slot_indices,
        &value.valid_slot_indices,
        &value.representative_slot_indices,
        &value.top_k_slot_indices,
    ] {
        hash.usize(indices.len());
        for index in indices {
            hash.u32(*index);
        }
    }
    hash_authority(&mut hash, value.authority);
    Ok(hash.finish())
}

#[allow(clippy::too_many_arguments)]
fn build_receipt(
    pipeline: &Fixed64Pipeline,
    input: Fixed64PreselectedRunInput<'_>,
    raw_modes: &[i32],
    effective_modes: &[i32],
    initial_admission_batch_receipt: Sha256,
    post_admission_batch_receipt: Sha256,
    source_quaternions: [&[f64]; 4],
    initial_rows: Vec<sys::bg_docking_geometric_admission_row_v1>,
    rigid_rows: Vec<sys::bg_docking_rigid_refinement_row_v1>,
    rigid_coordinates: [Vec<f64>; 12],
    torsion_rows: Vec<sys::bg_docking_torsion_v7_row_v1>,
    torsion_moves: Vec<sys::bg_docking_torsion_v7_move_v1>,
    torsion_coordinates: [Vec<f64>; 8],
    refinement_rows: Vec<sys::bg_docking_fixed64_refinement_row_v1>,
    post_rows: Vec<sys::bg_docking_geometric_admission_row_v1>,
    scorer_rows: Vec<sys::bg_docking_scorer_v1_row_v1>,
    validity_rows: Vec<sys::bg_docking_pose_validity_row_v1>,
    ranking_rows: Vec<sys::bg_docking_stable_top_k_row_v1>,
    cluster_rows: Vec<sys::bg_docking_rmsd_cluster_row_v1>,
    primary_indices: Vec<u32>,
    valid_indices: Vec<u32>,
    representative_indices: Vec<u32>,
    top_k_indices: Vec<u32>,
    final_coordinates: [Vec<f64>; 3],
    final_quaternions: [Vec<f64>; 4],
) -> Result<Fixed64PreselectedPipelineReceipt> {
    let ligand_count = pipeline.ligand_atom_count;
    let rigid_slices: [&[f64]; 12] =
        std::array::from_fn(|index| rigid_coordinates[index].as_slice());
    let torsion_slices: [&[f64]; 8] =
        std::array::from_fn(|index| torsion_coordinates[index].as_slice());
    let final_slices = [
        final_coordinates[0].as_slice(),
        final_coordinates[1].as_slice(),
        final_coordinates[2].as_slice(),
    ];
    let quaternion_slices = [
        final_quaternions[0].as_slice(),
        final_quaternions[1].as_slice(),
        final_quaternions[2].as_slice(),
        final_quaternions[3].as_slice(),
    ];
    let mut refinement_batch = CanonicalHasher::new(
        "betelgeuze.engine_v2_native_fixed64_preselected_refinement_batch/1.0.0",
    );
    let mut scorer_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_preselected_scorer_batch/1.0.0");
    let mut validity_batch = CanonicalHasher::new(
        "betelgeuze.engine_v2_native_fixed64_preselected_validity_batch/1.0.0",
    );
    let mut ranking_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_preselected_ranking_batch/1.0.0");
    let mut cluster_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_preselected_cluster_batch/1.0.0");
    let mut rows = Vec::with_capacity(raw_modes.len());
    for slot in 0..raw_modes.len() {
        let refinement_digest = canonical_refinement_evidence(
            slot,
            ligand_count,
            &rigid_rows[slot],
            &torsion_rows[slot],
            &torsion_moves,
            &refinement_rows[slot],
            rigid_slices,
            torsion_slices,
            final_slices,
            quaternion_slices,
        )?;
        let scorer_digest = canonical_scorer_evidence(&scorer_rows[slot]);
        let validity_digest = canonical_validity_evidence(&validity_rows[slot]);
        let ranking_digest = canonical_ranking_evidence(&ranking_rows[slot]);
        let cluster_digest = canonical_cluster_evidence(&cluster_rows[slot]);
        refinement_batch.digest(refinement_digest);
        scorer_batch.digest(scorer_digest);
        validity_batch.digest(validity_digest);
        ranking_batch.digest(ranking_digest);
        cluster_batch.digest(cluster_digest);
        let mut row_hash = CanonicalHasher::new(PRESELECTED_ROW_SCHEMA_ID);
        row_hash.digest(input.preselected.receipt_sha256());
        row_hash.usize(slot);
        row_hash.i32(raw_modes[slot]);
        row_hash.i32(effective_modes[slot]);
        row_hash.digest(initial_rows[slot].row_receipt_sha256);
        row_hash.digest(refinement_digest);
        row_hash.digest(post_rows[slot].row_receipt_sha256);
        row_hash.digest(scorer_digest);
        row_hash.digest(validity_digest);
        row_hash.digest(ranking_digest);
        row_hash.digest(cluster_digest);
        let row_receipt = row_hash.finish();
        rows.push(Fixed64PreselectedPipelineRow {
            slot_index: u32::try_from(slot).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "preselected row index overflows",
                )
            })?,
            lane: input.preselected.rows()[slot].lane(),
            selected_state: input.preselected.rows()[slot].state(),
            requested_refinement_mode: raw_modes[slot],
            effective_refinement_mode: effective_modes[slot],
            initial_admission: geometric_evidence(&initial_rows[slot])?,
            rigid: rigid_evidence(&rigid_rows[slot])?,
            torsion: torsion_evidence(&torsion_rows[slot])?,
            refinement: refinement_evidence(&refinement_rows[slot])?,
            post_admission: geometric_evidence(&post_rows[slot])?,
            scorer: scorer_evidence(&scorer_rows[slot]),
            validity: validity_evidence(&validity_rows[slot]),
            ranking: ranking_evidence(&ranking_rows[slot])?,
            cluster: cluster_evidence(&cluster_rows[slot])?,
            refinement_evidence_sha256: refinement_digest,
            scorer_evidence_sha256: scorer_digest,
            validity_evidence_sha256: validity_digest,
            ranking_evidence_sha256: ranking_digest,
            cluster_evidence_sha256: cluster_digest,
            row_receipt_sha256: row_receipt,
        });
    }
    let selected_count = input
        .preselected
        .rows()
        .iter()
        .filter(|row| {
            matches!(
                row.state(),
                NativeSamplingFunnelSelectedState::Selected { .. }
            )
        })
        .count();
    let initial_admitted_count = initial_rows
        .iter()
        .filter(|row| {
            row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                && row.rank_eligible == 1
        })
        .count();
    let refined_count = refinement_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY)
        .count();
    let post_admitted_count = post_rows
        .iter()
        .filter(|row| {
            row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                && row.rank_eligible == 1
        })
        .count();
    let scored_count = scorer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED)
        .count();
    let valid_count_count = validity_rows
        .iter()
        .filter(|row| {
            row.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED && row.blocker_mask == 0
        })
        .count();
    let authority = Fixed64AuthorityDisposition {
        result_dependent_input_consumed: false,
        fallback_allowed: false,
        multi_anchor_consumed: input.preselected.rows().iter().any(|row| {
            row.lane() == NativeSamplingFunnelLane::MultiAnchor
                && matches!(
                    row.state(),
                    NativeSamplingFunnelSelectedState::Selected { .. }
                )
        }),
        denominator_preserved: true,
        molecular_execution_authorized: false,
        reservation_authorized: false,
        benchmark_execution_authorized: false,
        existing_rank_auto_change_authorized: false,
        customer_pose_emission_authorized: false,
        production_claim_authorized: false,
        scientific_claim_authorized: false,
    };
    let receipts = Fixed64PreselectedBatchReceipts {
        preselected_batch_receipt_sha256: input.preselected.receipt_sha256(),
        admission_context_receipt_sha256: pipeline.expected_admission_context_receipt_sha256,
        refinement_context_receipt_sha256: pipeline.expected_refinement_context_receipt_sha256,
        scorer_context_receipt_sha256: pipeline.expected_scorer_context_receipt_sha256,
        validity_context_receipt_sha256: pipeline.expected_validity_context_receipt_sha256,
        component_binding_receipt_sha256: pipeline.expected_component_binding_receipt_sha256,
        policy_receipt_sha256: policy_receipt(pipeline, input, raw_modes),
        initial_admission_batch_receipt_sha256: initial_admission_batch_receipt,
        refinement_batch_receipt_sha256: refinement_batch.finish(),
        post_admission_batch_receipt_sha256: post_admission_batch_receipt,
        scorer_batch_receipt_sha256: scorer_batch.finish(),
        validity_batch_receipt_sha256: validity_batch.finish(),
        ranking_batch_receipt_sha256: ranking_batch.finish(),
        cluster_batch_receipt_sha256: cluster_batch.finish(),
        pipeline_batch_receipt_sha256: [0; 32],
    };
    let [rigid_selected_x, rigid_selected_y, rigid_selected_z, rigid_comparison_x, rigid_comparison_y, rigid_comparison_z, rigid_baseline_x, rigid_baseline_y, rigid_baseline_z, rigid_clearance_x, rigid_clearance_y, rigid_clearance_z] =
        rigid_coordinates;
    let [torsion_optimized_x, torsion_optimized_y, torsion_optimized_z, optimized_angles, torsion_final_x, torsion_final_y, torsion_final_z, final_angles] =
        torsion_coordinates;
    let [final_x, final_y, final_z] = final_coordinates;
    let mut receipt = Fixed64PreselectedPipelineReceipt {
        backend: pipeline.backend,
        unit_system: UnitSystem::AngstromKcalMol,
        ligand_system_sha256: pipeline.ligand_system_sha256,
        ligand_atom_count: ligand_count,
        selected_count: checked_count(selected_count)?,
        lane_shortfall_count: checked_count(raw_modes.len() - selected_count)?,
        initial_admitted_count: checked_count(initial_admitted_count)?,
        refined_count: checked_count(refined_count)?,
        post_admitted_count: checked_count(post_admitted_count)?,
        post_rejected_count: checked_count(
            refined_count
                .checked_sub(post_admitted_count)
                .ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "preselected post-admission count exceeds the refined count",
                    )
                })?,
        )?,
        scored_count: checked_count(scored_count)?,
        valid_count: checked_count(valid_count_count)?,
        rmsd_threshold_angstrom: input.rmsd_threshold_angstrom,
        requested_refinement_modes: raw_modes.to_vec(),
        rigid_max_steps: input.rigid_max_steps.to_vec(),
        proposal_is_torsion_eligible: input.proposal_is_torsion_eligible.to_vec(),
        torsion_max_steps: input.torsion_max_steps.to_vec(),
        baseline_torsion_angles_radians: input.baseline_torsion_angles_radians.to_vec(),
        maximum_torsion_steps: pipeline.maximum_torsion_steps,
        rotatable_child_atom_indices: pipeline.rotatable_child_atom_indices.clone(),
        predeclared_refinement_policy_sha256: input.predeclared_refinement_policy_sha256,
        predeclared_post_refinement_admission_policy_sha256: input
            .predeclared_post_refinement_admission_policy_sha256,
        source_coordinates: PositionSoaOwned {
            x_angstrom: input.preselected.x_angstrom().to_vec(),
            y_angstrom: input.preselected.y_angstrom().to_vec(),
            z_angstrom: input.preselected.z_angstrom().to_vec(),
        },
        source_quaternions: source_quaternions.map(<[f64]>::to_vec),
        rigid_coordinates: Fixed64RigidCoordinates {
            selected: PositionSoaOwned {
                x_angstrom: rigid_selected_x,
                y_angstrom: rigid_selected_y,
                z_angstrom: rigid_selected_z,
            },
            comparison_v2: PositionSoaOwned {
                x_angstrom: rigid_comparison_x,
                y_angstrom: rigid_comparison_y,
                z_angstrom: rigid_comparison_z,
            },
            baseline_v3: PositionSoaOwned {
                x_angstrom: rigid_baseline_x,
                y_angstrom: rigid_baseline_y,
                z_angstrom: rigid_baseline_z,
            },
            clearance_v4: PositionSoaOwned {
                x_angstrom: rigid_clearance_x,
                y_angstrom: rigid_clearance_y,
                z_angstrom: rigid_clearance_z,
            },
        },
        torsion_coordinates: Fixed64TorsionCoordinates {
            optimized: PositionSoaOwned {
                x_angstrom: torsion_optimized_x,
                y_angstrom: torsion_optimized_y,
                z_angstrom: torsion_optimized_z,
            },
            optimized_torsion_angles_radians: optimized_angles,
            final_state: PositionSoaOwned {
                x_angstrom: torsion_final_x,
                y_angstrom: torsion_final_y,
                z_angstrom: torsion_final_z,
            },
            final_torsion_angles_radians: final_angles,
        },
        final_coordinates: PositionSoaOwned {
            x_angstrom: final_x,
            y_angstrom: final_y,
            z_angstrom: final_z,
        },
        final_quaternions,
        initial_admission_rows: initial_rows
            .iter()
            .map(geometric_evidence)
            .collect::<Result<_>>()?,
        rigid_rows: rigid_rows
            .iter()
            .map(rigid_evidence)
            .collect::<Result<_>>()?,
        torsion_rows: torsion_rows
            .iter()
            .map(torsion_evidence)
            .collect::<Result<_>>()?,
        torsion_moves: torsion_moves
            .iter()
            .map(torsion_move_evidence)
            .collect::<Result<_>>()?,
        refinement_rows: refinement_rows
            .iter()
            .map(refinement_evidence)
            .collect::<Result<_>>()?,
        post_admission_rows: post_rows
            .iter()
            .map(geometric_evidence)
            .collect::<Result<_>>()?,
        scorer_rows: scorer_rows.iter().map(scorer_evidence).collect(),
        validity_rows: validity_rows.iter().map(validity_evidence).collect(),
        ranking_rows: ranking_rows
            .iter()
            .map(ranking_evidence)
            .collect::<Result<_>>()?,
        cluster_rows: cluster_rows
            .iter()
            .map(cluster_evidence)
            .collect::<Result<_>>()?,
        rows,
        primary_slot_indices: primary_indices,
        valid_slot_indices: valid_indices,
        representative_slot_indices: representative_indices,
        top_k_slot_indices: top_k_indices,
        receipts,
        authority,
    };
    receipt.receipts.pipeline_batch_receipt_sha256 = derive_pipeline_receipt(&receipt)?;
    if !receipt.has_valid_receipt() {
        return Err(Error::local(
            ErrorCode::InternalError,
            "preselected pipeline receipt did not self-verify",
        ));
    }
    Ok(receipt)
}
