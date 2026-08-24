use super::{
    abi_cluster_row_from_evidence, abi_geometric_row_from_evidence, abi_pipeline_row_from_evidence,
    abi_ranking_row_from_evidence, abi_refinement_row_from_evidence, abi_rigid_row_from_evidence,
    abi_scorer_row_from_evidence, abi_torsion_move_from_evidence, abi_torsion_row_from_evidence,
    abi_validity_row_from_evidence, canonical_cluster_evidence, canonical_coordinate_sha256,
    canonical_pipeline_row_receipt, canonical_ranking_evidence, canonical_refinement_evidence,
    canonical_scorer_evidence, canonical_validity_evidence, coordinate_segment,
    coordinate_segment_matches, digest_present, hash_bool, hash_f64_channel,
    hash_position_soa_owned, hash_u32_channel, sys, CanonicalHasher, Error, ErrorCode,
    Fixed64AuthorityDisposition, Fixed64ClusterEvidence, Fixed64GeometricEvidence,
    Fixed64PipelineReceipt, Fixed64RankingEvidence, Fixed64RefinementEvidence,
    Fixed64RigidCoordinates, Fixed64RigidEvidence, Fixed64RigidProfileEvidence,
    Fixed64ScorerEvidence, Fixed64TorsionCoordinates, Fixed64TorsionEvidence,
    Fixed64TorsionMoveEvidence, Fixed64ValidityEvidence, Result, Sha256,
};

/// Backend-independent scientific projection of one complete fixed64 run.
///
/// Native receipt identities intentionally bind the selected backend and must
/// not be compared across providers.  This projection excludes those receipt
/// identities while retaining every fixed-denominator decision, failure code,
/// ScorerV1 term, validity measurement, stable rank, V7 selection, coordinate,
/// and cluster result needed for CPU/HIP parity qualification.
#[derive(Debug, Clone, PartialEq)]
pub struct Fixed64ScientificProjection {
    pub candidate_denominator: usize,
    pub receptor_atom_count: usize,
    pub ligand_atom_count: usize,
    pub generated_count: u64,
    pub typed_failure_count: u64,
    pub initial_admitted_count: u64,
    pub refined_count: u64,
    pub post_admitted_count: u64,
    pub post_rejected_count: u64,
    pub scored_count: u64,
    pub valid_count: u64,
    pub cluster_count: u64,
    pub primary_slot_indices: Vec<u32>,
    pub valid_slot_indices: Vec<u32>,
    pub representative_slot_indices: Vec<u32>,
    pub top_k_slot_indices: Vec<u32>,
    pub candidate_rows: Vec<Fixed64ScientificCandidateProjection>,
    pub torsion_moves: Vec<Fixed64TorsionMoveEvidence>,
    pub producer_coordinates: crate::PositionSoaOwned,
    pub rigid_coordinates: Fixed64RigidCoordinates,
    pub torsion_coordinates: Fixed64TorsionCoordinates,
    pub final_coordinates: crate::PositionSoaOwned,
    pub final_quaternions: [Vec<f64>; 4],
    pub authority: Fixed64AuthorityDisposition,
    pub decision_sha256: Sha256,
    pub sha256: Sha256,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fixed64ScientificCandidateProjection {
    pub slot_index: u32,
    pub lane: i32,
    pub producer_status: i32,
    pub producer_failure_code: i32,
    pub placement_kind: i32,
    pub component_failure_code: i32,
    pub coordinates_available: bool,
    pub steric_precheck_passed: bool,
    pub source_identity_verified: bool,
    pub allocation_identity_verified: bool,
    pub geometric_identity_verified: bool,
    pub denominator_preserved: bool,
    pub placement_quaternion: [f64; 4],
    pub allocation_slot_receipt_sha256: Sha256,
    pub source_payload_receipt_sha256: Sha256,
    pub source_proposal_sha256: Sha256,
    pub source_coordinate_sha256: Sha256,
    pub placement_receipt_sha256: Sha256,
    pub output_proposal_sha256: Sha256,
    pub output_coordinate_sha256: Sha256,
    pub geometric_status: i32,
    pub geometric_failure_code: i32,
    pub geometric_decision: i32,
    pub geometric_rank_eligible: bool,
    pub exact_pair_count: u64,
    pub penetration_pair_count: u64,
    pub penetrating_atom_count: u64,
    pub penetrating_heavy_atom_count: u64,
    pub raw_minimum_distance_angstrom: f64,
    pub minimum_vdw_surface_gap_angstrom: f64,
    pub minimum_vdw_ratio: f64,
    pub sphere_overlap_proxy_angstrom3: f64,
    pub pocket_escape_angstrom: f64,
    pub requested_refinement_mode: i32,
    pub effective_refinement_mode: i32,
    pub rigid: Fixed64RigidEvidence,
    pub torsion: Fixed64TorsionEvidence,
    pub refinement: Fixed64RefinementEvidence,
    pub post_admission: Fixed64GeometricEvidence,
    pub scorer: Fixed64ScorerEvidence,
    pub validity: Fixed64ValidityEvidence,
    pub ranking: Fixed64RankingEvidence,
    pub cluster: Fixed64ClusterEvidence,
}

impl Fixed64PipelineReceipt {
    /// Derive a backend-independent scientific projection from a validated
    /// fixed64 receipt graph.
    ///
    /// The receipt fields remain public for evidence serialization.  Reject a
    /// caller-mutated graph before indexing its parallel row channels so a
    /// malformed artifact cannot panic or silently truncate the denominator.
    pub fn scientific_projection(&self) -> Result<Fixed64ScientificProjection> {
        self.validate_scientific_projection_receipt_graph()?;
        let value = self.derive_scientific_projection();
        if self.scientific_projection_sha256 != value.sha256 {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "fixed64 scientific projection changed after receipt issuance",
            ));
        }
        Ok(value)
    }

    pub(super) fn derive_scientific_projection(&self) -> Fixed64ScientificProjection {
        let candidate_rows = (0..self.rows.len())
            .map(|slot| {
                let producer = self.producer_rows[slot];
                let pipeline = self.rows[slot];
                Fixed64ScientificCandidateProjection {
                    slot_index: pipeline.slot_index,
                    lane: producer.lane,
                    producer_status: pipeline.producer_status,
                    producer_failure_code: pipeline.producer_failure_code,
                    placement_kind: producer.placement_kind,
                    component_failure_code: producer.component_failure_code,
                    coordinates_available: producer.coordinates_available,
                    steric_precheck_passed: producer.steric_precheck_passed,
                    source_identity_verified: producer.source_identity_verified,
                    allocation_identity_verified: producer.allocation_identity_verified,
                    geometric_identity_verified: producer.geometric_identity_verified,
                    denominator_preserved: producer.denominator_preserved,
                    placement_quaternion: producer.placement_quaternion,
                    allocation_slot_receipt_sha256: producer.allocation_slot_receipt_sha256,
                    source_payload_receipt_sha256: producer.source_payload_receipt_sha256,
                    source_proposal_sha256: producer.source_proposal_sha256,
                    source_coordinate_sha256: producer.source_coordinate_sha256,
                    placement_receipt_sha256: producer.placement_receipt_sha256,
                    output_proposal_sha256: producer.output_proposal_sha256,
                    output_coordinate_sha256: producer.output_coordinate_sha256,
                    geometric_status: producer.geometric.status,
                    geometric_failure_code: producer.geometric.failure_code,
                    geometric_decision: producer.geometric.decision,
                    geometric_rank_eligible: producer.geometric.rank_eligible,
                    exact_pair_count: producer.geometric.exact_pair_count,
                    penetration_pair_count: producer.geometric.penetration_pair_count,
                    penetrating_atom_count: producer.geometric.unique_ligand_penetration_atom_count,
                    penetrating_heavy_atom_count: producer
                        .geometric
                        .unique_ligand_heavy_atom_penetration_count,
                    raw_minimum_distance_angstrom: producer.geometric.raw_minimum_distance_angstrom,
                    minimum_vdw_surface_gap_angstrom: producer
                        .geometric
                        .minimum_vdw_surface_gap_angstrom,
                    minimum_vdw_ratio: producer.geometric.minimum_vdw_ratio,
                    sphere_overlap_proxy_angstrom3: producer
                        .geometric
                        .sphere_overlap_proxy_angstrom3,
                    pocket_escape_angstrom: producer.geometric.pocket_escape_angstrom,
                    requested_refinement_mode: pipeline.requested_refinement_mode,
                    effective_refinement_mode: pipeline.effective_refinement_mode,
                    rigid: self.rigid_rows[slot],
                    torsion: self.torsion_rows[slot],
                    refinement: self.refinement_rows[slot],
                    post_admission: self.post_admission_rows[slot],
                    scorer: self.scorer_rows[slot],
                    validity: self.validity_rows[slot],
                    ranking: self.ranking_rows[slot],
                    cluster: self.cluster_rows[slot],
                }
            })
            .collect::<Vec<_>>();
        let mut value = Fixed64ScientificProjection {
            candidate_denominator: self.rows.len(),
            receptor_atom_count: self.receptor_atom_count,
            ligand_atom_count: self.ligand_atom_count,
            generated_count: self.generated_count,
            typed_failure_count: self.typed_failure_count,
            initial_admitted_count: self.initial_admitted_count,
            refined_count: self.refined_count,
            post_admitted_count: self.post_admitted_count,
            post_rejected_count: self.post_rejected_count,
            scored_count: self.scored_count,
            valid_count: self.valid_count,
            cluster_count: self.cluster_count,
            primary_slot_indices: self.primary_slot_indices.clone(),
            valid_slot_indices: self.valid_slot_indices.clone(),
            representative_slot_indices: self.representative_slot_indices.clone(),
            top_k_slot_indices: self.top_k_slot_indices.clone(),
            candidate_rows,
            torsion_moves: self.torsion_moves.clone(),
            producer_coordinates: self.producer_coordinates.clone(),
            rigid_coordinates: self.rigid_coordinates.clone(),
            torsion_coordinates: self.torsion_coordinates.clone(),
            final_coordinates: self.final_coordinates.clone(),
            final_quaternions: self.final_quaternions.clone(),
            authority: self.authority,
            decision_sha256: [0; 32],
            sha256: [0; 32],
        };
        value.decision_sha256 = scientific_decision_sha256(&value);
        value.sha256 = scientific_projection_sha256(&value);
        value
    }

    fn validate_scientific_projection_receipt_graph(&self) -> Result<()> {
        const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        let row_channels = [
            ("pipeline", self.rows.len()),
            ("producer", self.producer_rows.len()),
            ("rigid", self.rigid_rows.len()),
            ("torsion", self.torsion_rows.len()),
            ("refinement", self.refinement_rows.len()),
            ("post-admission", self.post_admission_rows.len()),
            ("scorer", self.scorer_rows.len()),
            ("validity", self.validity_rows.len()),
            ("ranking", self.ranking_rows.len()),
            ("cluster", self.cluster_rows.len()),
        ];
        if row_channels
            .iter()
            .any(|(_, length)| *length != CANDIDATE_COUNT)
        {
            let observed = row_channels
                .iter()
                .map(|(name, length)| format!("{name}={length}"))
                .collect::<Vec<_>>()
                .join(", ");
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!(
                    "fixed64 scientific projection requires {CANDIDATE_COUNT} rows in every channel ({observed})"
                ),
            ));
        }
        const MOVES_PER_CANDIDATE: usize = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
        let expected_move_count = CANDIDATE_COUNT
            .checked_mul(MOVES_PER_CANDIDATE)
            .expect("fixed64 torsion move count fits usize");
        if self.torsion_moves.len() != expected_move_count
            || self.torsion_moves.iter().enumerate().any(|(index, row)| {
                row.slot_index as usize != index / MOVES_PER_CANDIDATE
                    || row.move_index as usize != index % MOVES_PER_CANDIDATE
            })
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "fixed64 scientific projection torsion moves are not index-aligned",
            ));
        }
        let expected_coordinate_count = CANDIDATE_COUNT
            .checked_mul(self.ligand_atom_count)
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 scientific projection coordinate denominator overflowed",
                )
            })?;
        let coordinate_channels = [
            &self.producer_coordinates,
            &self.rigid_coordinates.selected,
            &self.rigid_coordinates.comparison_v2,
            &self.rigid_coordinates.baseline_v3,
            &self.rigid_coordinates.clearance_v4,
            &self.torsion_coordinates.optimized,
            &self.torsion_coordinates.final_state,
            &self.final_coordinates,
        ];
        if coordinate_channels.iter().any(|coordinates| {
            coordinates.x_angstrom.len() != expected_coordinate_count
                || coordinates.y_angstrom.len() != expected_coordinate_count
                || coordinates.z_angstrom.len() != expected_coordinate_count
        }) || self
            .torsion_coordinates
            .optimized_torsion_angles_radians
            .len()
            != expected_coordinate_count
            || self.torsion_coordinates.final_torsion_angles_radians.len()
                != expected_coordinate_count
            || self
                .final_quaternions
                .iter()
                .any(|values| values.len() != CANDIDATE_COUNT)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "fixed64 scientific projection coordinate channels changed length",
            ));
        }
        let producer_coordinates = [
            self.producer_coordinates.x_angstrom.as_slice(),
            self.producer_coordinates.y_angstrom.as_slice(),
            self.producer_coordinates.z_angstrom.as_slice(),
        ];
        let rigid_coordinates = [
            self.rigid_coordinates.selected.x_angstrom.as_slice(),
            self.rigid_coordinates.selected.y_angstrom.as_slice(),
            self.rigid_coordinates.selected.z_angstrom.as_slice(),
            self.rigid_coordinates.comparison_v2.x_angstrom.as_slice(),
            self.rigid_coordinates.comparison_v2.y_angstrom.as_slice(),
            self.rigid_coordinates.comparison_v2.z_angstrom.as_slice(),
            self.rigid_coordinates.baseline_v3.x_angstrom.as_slice(),
            self.rigid_coordinates.baseline_v3.y_angstrom.as_slice(),
            self.rigid_coordinates.baseline_v3.z_angstrom.as_slice(),
            self.rigid_coordinates.clearance_v4.x_angstrom.as_slice(),
            self.rigid_coordinates.clearance_v4.y_angstrom.as_slice(),
            self.rigid_coordinates.clearance_v4.z_angstrom.as_slice(),
        ];
        let torsion_coordinates = [
            self.torsion_coordinates.optimized.x_angstrom.as_slice(),
            self.torsion_coordinates.optimized.y_angstrom.as_slice(),
            self.torsion_coordinates.optimized.z_angstrom.as_slice(),
            self.torsion_coordinates
                .optimized_torsion_angles_radians
                .as_slice(),
            self.torsion_coordinates.final_state.x_angstrom.as_slice(),
            self.torsion_coordinates.final_state.y_angstrom.as_slice(),
            self.torsion_coordinates.final_state.z_angstrom.as_slice(),
            self.torsion_coordinates
                .final_torsion_angles_radians
                .as_slice(),
        ];
        let final_coordinates = [
            self.final_coordinates.x_angstrom.as_slice(),
            self.final_coordinates.y_angstrom.as_slice(),
            self.final_coordinates.z_angstrom.as_slice(),
        ];
        let final_quaternions = [
            self.final_quaternions[0].as_slice(),
            self.final_quaternions[1].as_slice(),
            self.final_quaternions[2].as_slice(),
            self.final_quaternions[3].as_slice(),
        ];
        let abi_torsion_moves = self
            .torsion_moves
            .iter()
            .copied()
            .map(abi_torsion_move_from_evidence)
            .collect::<Vec<_>>();
        let ligand_count_u64 = u64::try_from(self.ligand_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 scientific projection ligand denominator does not fit u64",
            )
        })?;
        for slot in 0..CANDIDATE_COUNT {
            let expected_slot = u32::try_from(slot).expect("fixed64 slot fits u32");
            let pipeline = self.rows[slot];
            let producer = self.producer_rows[slot];
            let rigid = self.rigid_rows[slot];
            let torsion = self.torsion_rows[slot];
            let refinement = self.refinement_rows[slot];
            let post_admission = self.post_admission_rows[slot];
            let scorer = self.scorer_rows[slot];
            let validity = self.validity_rows[slot];
            let ranking = self.ranking_rows[slot];
            let cluster = self.cluster_rows[slot];
            if [
                pipeline.slot_index,
                producer.slot_index,
                rigid.slot_index,
                torsion.slot_index,
                refinement.slot_index,
                post_admission.slot_index,
                scorer.slot_index,
                validity.slot_index,
                ranking.slot_index,
                cluster.slot_index,
            ]
            .iter()
            .any(|observed| *observed != expected_slot)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    format!(
                        "fixed64 scientific projection row channels are not aligned at slot {slot}"
                    ),
                ));
            }
            if pipeline.producer_status != producer.status
                || pipeline.producer_failure_code != producer.failure_code
                || pipeline.initial_admission_decision != producer.geometric.decision
                || pipeline.effective_refinement_mode != rigid.candidate_mode
                || pipeline.refinement_status != refinement.status
                || pipeline.refinement_failure_stage != refinement.failure_stage
                || pipeline.post_admission_status != post_admission.status
                || pipeline.post_admission_failure_code != post_admission.failure_code
                || pipeline.post_admission_decision != post_admission.decision
                || pipeline.post_admission_rank_eligible != post_admission.rank_eligible
                || pipeline.scorer_status != scorer.status
                || pipeline.scorer_failure_code != scorer.failure_code
                || pipeline.validity_status != validity.status
                || pipeline.validity_failure_code != validity.failure_code
                || pipeline.stable_rank != ranking.stable_rank
                || pipeline.stable_valid_rank != ranking.stable_valid_rank
                || pipeline.cluster_status != cluster.status
                || pipeline.cluster_id != cluster.cluster_id
                || pipeline.cluster_rank != cluster.cluster_rank
                || pipeline.top_k_rank != cluster.top_k_rank
                || pipeline.producer_row_receipt_sha256 != producer.row_receipt_sha256
                || pipeline.final_coordinate_sha256 != refinement.coordinate_sha256
                || pipeline.post_admission_row_receipt_sha256 != post_admission.row_receipt_sha256
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    format!(
                        "fixed64 scientific projection mirrored evidence changed at slot {slot}"
                    ),
                ));
            }
            let producer_segment =
                coordinate_segment(producer_coordinates, slot, self.ligand_atom_count).ok_or_else(
                    || {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            format!("fixed64 producer coordinate segment is absent at slot {slot}"),
                        )
                    },
                )?;
            let producer_coordinate_identity_matches = if producer.coordinates_available {
                digest_present(&producer.output_coordinate_sha256)
                    && canonical_coordinate_sha256(producer_segment)
                        == producer.output_coordinate_sha256
                    && coordinate_segment_matches(
                        &producer_coordinates,
                        slot,
                        ligand_count_u64,
                        false,
                    )?
            } else {
                !digest_present(&producer.output_coordinate_sha256)
                    && coordinate_segment_matches(
                        &producer_coordinates,
                        slot,
                        ligand_count_u64,
                        true,
                    )?
            };
            let final_segment = coordinate_segment(final_coordinates, slot, self.ligand_atom_count)
                .ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        format!("fixed64 final coordinate segment is absent at slot {slot}"),
                    )
                })?;
            let final_coordinate_identity_matches = if refinement.coordinate_available {
                digest_present(&refinement.coordinate_sha256)
                    && canonical_coordinate_sha256(final_segment) == refinement.coordinate_sha256
                    && coordinate_segment_matches(
                        &final_coordinates,
                        slot,
                        ligand_count_u64,
                        false,
                    )?
            } else {
                !digest_present(&refinement.coordinate_sha256)
                    && coordinate_segment_matches(&final_coordinates, slot, ligand_count_u64, true)?
            };
            if !producer_coordinate_identity_matches || !final_coordinate_identity_matches {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    format!(
                        "fixed64 scientific projection coordinate identity changed at slot {slot}"
                    ),
                ));
            }
            let abi_rigid = abi_rigid_row_from_evidence(rigid);
            let abi_torsion = abi_torsion_row_from_evidence(torsion);
            let abi_refinement = abi_refinement_row_from_evidence(refinement);
            let abi_post_admission = abi_geometric_row_from_evidence(post_admission);
            let abi_scorer = abi_scorer_row_from_evidence(scorer);
            let abi_validity = abi_validity_row_from_evidence(validity);
            let abi_ranking = abi_ranking_row_from_evidence(ranking);
            let abi_cluster = abi_cluster_row_from_evidence(cluster);
            let abi_pipeline = abi_pipeline_row_from_evidence(pipeline);
            let expected_refinement_evidence = canonical_refinement_evidence(
                slot,
                self.ligand_atom_count,
                &abi_rigid,
                &abi_torsion,
                &abi_torsion_moves,
                &abi_refinement,
                rigid_coordinates,
                torsion_coordinates,
                final_coordinates,
                final_quaternions,
            )?;
            let expected_scorer_evidence = canonical_scorer_evidence(&abi_scorer);
            let expected_validity_evidence = canonical_validity_evidence(&abi_validity);
            let expected_ranking_evidence = canonical_ranking_evidence(&abi_ranking);
            let expected_cluster_evidence = canonical_cluster_evidence(&abi_cluster);
            let expected_pipeline_receipt = canonical_pipeline_row_receipt(
                &abi_pipeline,
                self.receipts.component_binding_receipt_sha256,
                self.receipts.refinement_policy_receipt_sha256,
                self.receipts.post_admission_policy_receipt_sha256,
                expected_refinement_evidence,
                expected_scorer_evidence,
                expected_validity_evidence,
                expected_ranking_evidence,
                expected_cluster_evidence,
            );
            if pipeline.refinement_evidence_sha256 != expected_refinement_evidence
                || abi_pipeline.post_admission_status != abi_post_admission.status
                || abi_pipeline.post_admission_failure_code != abi_post_admission.failure_code
                || abi_pipeline.post_admission_decision != abi_post_admission.decision
                || abi_pipeline.post_admission_rank_eligible != abi_post_admission.rank_eligible
                || abi_pipeline.post_admission_row_receipt_sha256
                    != abi_post_admission.row_receipt_sha256
                || pipeline.scorer_evidence_sha256 != expected_scorer_evidence
                || pipeline.validity_evidence_sha256 != expected_validity_evidence
                || pipeline.ranking_evidence_sha256 != expected_ranking_evidence
                || pipeline.cluster_evidence_sha256 != expected_cluster_evidence
                || pipeline.row_receipt_sha256 != expected_pipeline_receipt
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    format!(
                        "fixed64 scientific projection component evidence changed at slot {slot}"
                    ),
                ));
            }
        }
        Ok(())
    }
}

fn hash_rigid_profile_decision(hash: &mut CanonicalHasher, value: Fixed64RigidProfileEvidence) {
    hash.i32(value.profile);
    hash_bool(hash, value.available);
    hash.u64(value.accepted_steps);
    hash.u64(value.accepted_translation_steps);
    hash.u64(value.accepted_rotation_steps);
    hash.u64(value.line_search_evaluation_count);
    hash.u64(value.fallback_direction_step_count);
}

fn hash_rigid_profile_numeric(hash: &mut CanonicalHasher, value: Fixed64RigidProfileEvidence) {
    hash.f64(value.initial_penalty);
    hash.f64(value.final_penalty);
    hash_f64_channel(hash, &value.total_translation_angstrom);
    hash_f64_channel(hash, &value.total_rotation_vector_radians);
    hash.f64(value.total_rotation_path_radians);
    hash.f64(value.initial_centroid_offset_angstrom);
    hash.f64(value.final_centroid_offset_angstrom);
    hash.f64(value.maximum_centroid_offset_angstrom);
}

fn hash_authority_decision(hash: &mut CanonicalHasher, value: Fixed64AuthorityDisposition) {
    hash_bool(hash, value.result_dependent_input_consumed);
    hash_bool(hash, value.fallback_allowed);
    hash_bool(hash, value.multi_anchor_consumed);
    hash_bool(hash, value.denominator_preserved);
    hash_bool(hash, value.molecular_execution_authorized);
    hash_bool(hash, value.reservation_authorized);
    hash_bool(hash, value.benchmark_execution_authorized);
    hash_bool(hash, value.existing_rank_auto_change_authorized);
    hash_bool(hash, value.customer_pose_emission_authorized);
    hash_bool(hash, value.production_claim_authorized);
    hash_bool(hash, value.scientific_claim_authorized);
}

fn append_scientific_decision(hash: &mut CanonicalHasher, value: &Fixed64ScientificProjection) {
    hash.usize(value.candidate_denominator);
    hash.usize(value.receptor_atom_count);
    hash.usize(value.ligand_atom_count);
    hash.u64(value.generated_count);
    hash.u64(value.typed_failure_count);
    hash.u64(value.initial_admitted_count);
    hash.u64(value.refined_count);
    hash.u64(value.post_admitted_count);
    hash.u64(value.post_rejected_count);
    hash.u64(value.scored_count);
    hash.u64(value.valid_count);
    hash.u64(value.cluster_count);
    hash_u32_channel(hash, &value.primary_slot_indices);
    hash_u32_channel(hash, &value.valid_slot_indices);
    hash_u32_channel(hash, &value.representative_slot_indices);
    hash_u32_channel(hash, &value.top_k_slot_indices);
    hash_authority_decision(hash, value.authority);
    hash.usize(value.candidate_rows.len());
    for row in &value.candidate_rows {
        hash.u32(row.slot_index);
        hash.i32(row.lane);
        hash.i32(row.producer_status);
        hash.i32(row.producer_failure_code);
        hash.i32(row.placement_kind);
        hash.i32(row.component_failure_code);
        hash_bool(hash, row.coordinates_available);
        hash_bool(hash, row.steric_precheck_passed);
        hash_bool(hash, row.source_identity_verified);
        hash_bool(hash, row.allocation_identity_verified);
        hash_bool(hash, row.geometric_identity_verified);
        hash_bool(hash, row.denominator_preserved);
        hash.digest(row.allocation_slot_receipt_sha256);
        hash.digest(row.source_payload_receipt_sha256);
        hash.digest(row.source_proposal_sha256);
        hash.digest(row.source_coordinate_sha256);
        hash.i32(row.geometric_status);
        hash.i32(row.geometric_failure_code);
        hash.i32(row.geometric_decision);
        hash_bool(hash, row.geometric_rank_eligible);
        hash.u64(row.exact_pair_count);
        hash.u64(row.penetration_pair_count);
        hash.u64(row.penetrating_atom_count);
        hash.u64(row.penetrating_heavy_atom_count);
        hash.i32(row.requested_refinement_mode);
        hash.i32(row.effective_refinement_mode);

        let rigid = row.rigid;
        hash.u32(rigid.slot_index);
        hash.i32(rigid.status);
        hash.i32(rigid.failure_code);
        hash.i32(rigid.candidate_mode);
        hash.i32(rigid.selected_profile);
        hash_bool(hash, rigid.baseline_duplicate_of_v2);
        hash_bool(hash, rigid.clearance_evaluated);
        hash_bool(hash, rigid.clearance_selected);
        for profile in [
            rigid.selected,
            rigid.comparison_v2,
            rigid.baseline_v3,
            rigid.clearance_v4,
        ] {
            hash_rigid_profile_decision(hash, profile);
        }

        let torsion = row.torsion;
        hash.u32(torsion.slot_index);
        hash.i32(torsion.status);
        hash.i32(torsion.failure_code);
        hash.i32(torsion.skip_reason);
        hash.i32(torsion.selection_reason);
        hash_bool(hash, torsion.selection_window_reachable);
        hash_bool(
            hash,
            torsion.evaluation_stopped_after_selection_window_became_unreachable,
        );
        hash_bool(hash, torsion.torsion_evaluated);
        hash_bool(hash, torsion.torsion_variant_available);
        hash_bool(hash, torsion.torsion_selected);
        hash.u64(torsion.torsion_step_budget);
        hash.u64(torsion.fixed_objective_evaluation_count);
        hash.u64(torsion.torsion_trial_objective_evaluation_count);
        hash.u64(torsion.evaluated_torsion_steps);
        hash.u64(torsion.accepted_torsion_steps);
        hash.u64(torsion.baseline_v6_accepted_steps);

        let refinement = row.refinement;
        hash.u32(refinement.slot_index);
        hash.i32(refinement.status);
        hash.i32(refinement.failure_stage);
        hash.i32(refinement.coordinate_origin);
        hash.i32(refinement.rigid_failure_code);
        hash.i32(refinement.torsion_v7_failure_code);
        hash.i32(refinement.selected_rigid_profile);
        hash.i32(refinement.downstream_candidate_state);
        hash_bool(hash, refinement.torsion_v7_applicable);
        hash_bool(hash, refinement.torsion_v7_selected);
        hash_bool(hash, refinement.coordinate_available);

        let post_admission = row.post_admission;
        hash.u32(post_admission.slot_index);
        hash.i32(post_admission.status);
        hash.i32(post_admission.failure_code);
        hash.i32(post_admission.decision);
        hash_bool(hash, post_admission.rank_eligible);
        hash.u64(post_admission.ligand_atom_count);
        hash.u64(post_admission.receptor_atom_count);
        hash.u64(post_admission.exact_pair_count);
        hash.u64(post_admission.penetration_pair_count);
        hash.u64(post_admission.unique_ligand_penetration_atom_count);
        hash.u64(post_admission.unique_ligand_heavy_atom_penetration_count);

        let scorer = row.scorer;
        hash.u32(scorer.slot_index);
        hash.i32(scorer.status);
        hash.i32(scorer.failure_code);
        hash.u64(scorer.receptor_candidate_pair_count);
        hash.u64(scorer.ligand_pair_count);
        hash.u64(scorer.hbond_count);
        hash.u64(scorer.hydrophobic_contact_count);
        hash.u64(scorer.buried_polar_count);

        let validity = row.validity;
        hash.u32(validity.slot_index);
        hash.i32(validity.status);
        hash.i32(validity.failure_code);
        hash.i32(validity.upstream_scorer_failure_code);
        hash.u32(validity.passed_check_mask);
        hash.u32(validity.blocker_mask);
        hash.u64(validity.observed_count);
        hash.u64(validity.atom_count);
        hash.u64(validity.evaluated_ligand_nonbonded_pair_count);
        hash.u64(validity.excluded_ligand_pair_count);
        hash.u64(validity.evaluated_receptor_ligand_pair_count);
        hash.u64(validity.declared_chirality_center_count);
        hash.u64(validity.element_vdw_ligand_pair_count);
        hash.u64(validity.element_vdw_ligand_severe_overlap_count);
        hash.u64(validity.element_vdw_receptor_candidate_pair_count);
        hash.u64(validity.element_vdw_receptor_full_cartesian_pair_count);
        hash.u64(validity.element_vdw_receptor_cell_count);
        hash.u64(validity.element_vdw_receptor_severe_overlap_count);

        let ranking = row.ranking;
        hash.u32(ranking.slot_index);
        hash_bool(hash, ranking.rank_eligible);
        hash_bool(hash, ranking.valid_rank_eligible);
        hash.u32(ranking.stable_rank);
        hash.u32(ranking.stable_valid_rank);

        let cluster = row.cluster;
        hash.u32(cluster.slot_index);
        hash.i32(cluster.status);
        hash_bool(hash, cluster.cluster_eligible);
        hash_bool(hash, cluster.representative);
        hash_bool(hash, cluster.top_k_representative);
        hash.u32(cluster.stable_valid_rank);
        hash.u32(cluster.cluster_id);
        hash.u32(cluster.representative_slot_index);
        hash.u32(cluster.cluster_rank);
        hash.u32(cluster.top_k_rank);
        hash.u32(cluster.cluster_size);
    }
    hash.usize(value.torsion_moves.len());
    for movement in &value.torsion_moves {
        hash.u32(movement.slot_index);
        hash.u32(movement.move_index);
        hash_bool(hash, movement.evaluated);
        hash_bool(hash, movement.selected);
        hash.u64(movement.rotatable_child_atom_index);
    }
}

fn scientific_decision_sha256(value: &Fixed64ScientificProjection) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scientific_decision/2.0.0");
    append_scientific_decision(&mut hash, value);
    hash.finish()
}

pub(crate) fn scientific_decision_preimage(
    value: &Fixed64ScientificProjection,
) -> (Sha256, Vec<u8>) {
    let mut hash = CanonicalHasher::new_recording(
        "betelgeuze.engine_v2_native_fixed64_scientific_decision/2.0.0",
    );
    append_scientific_decision(&mut hash, value);
    hash.finish_recording()
}

fn scientific_projection_sha256(value: &Fixed64ScientificProjection) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scientific_projection/2.0.0");
    hash.digest(value.decision_sha256);
    for row in &value.candidate_rows {
        hash.digest(row.placement_receipt_sha256);
        hash.digest(row.output_proposal_sha256);
        hash.digest(row.output_coordinate_sha256);
        hash_f64_channel(&mut hash, &row.placement_quaternion);
        for measurement in [
            row.raw_minimum_distance_angstrom,
            row.minimum_vdw_surface_gap_angstrom,
            row.minimum_vdw_ratio,
            row.sphere_overlap_proxy_angstrom3,
            row.pocket_escape_angstrom,
        ] {
            hash.f64(measurement);
        }
        for measurement in [
            row.post_admission.raw_minimum_distance_angstrom,
            row.post_admission.minimum_vdw_surface_gap_angstrom,
            row.post_admission.minimum_vdw_ratio,
            row.post_admission.sphere_overlap_proxy_angstrom3,
            row.post_admission.pocket_escape_angstrom,
        ] {
            hash.f64(measurement);
        }
        for profile in [
            row.rigid.selected,
            row.rigid.comparison_v2,
            row.rigid.baseline_v3,
            row.rigid.clearance_v4,
        ] {
            hash_rigid_profile_numeric(&mut hash, profile);
        }
        let torsion = row.torsion;
        for objective in [
            torsion.source_receptor_penalty,
            torsion.source_internal_penalty,
            torsion.source_combined_penalty,
            torsion.baseline_receptor_penalty,
            torsion.baseline_internal_penalty,
            torsion.baseline_combined_penalty,
            torsion.optimized_receptor_penalty,
            torsion.optimized_internal_penalty,
            torsion.optimized_combined_penalty,
            torsion.final_receptor_penalty,
            torsion.final_internal_penalty,
            torsion.final_combined_penalty,
            torsion.evaluated_total_torsion_path_radians,
            torsion.accepted_total_torsion_path_radians,
        ] {
            hash.f64(objective);
        }
        hash_f64_channel(&mut hash, &row.scorer.weighted_terms);
        hash.f64(row.scorer.total_score);
        let validity = row.validity;
        for measurement in [
            validity.rotation_orthogonality_max_error,
            validity.rotation_determinant,
            validity.max_bond_length_delta_angstrom,
            validity.minimum_ligand_nonbonded_distance_angstrom,
            validity.minimum_receptor_ligand_distance_angstrom,
            validity.minimum_declared_chiral_volume,
            validity.maximum_pocket_center_distance_angstrom,
            validity.element_vdw_ligand_minimum_distance_angstrom,
            validity.element_vdw_ligand_minimum_ratio,
            validity.element_vdw_receptor_minimum_distance_angstrom,
            validity.element_vdw_receptor_minimum_ratio,
        ] {
            hash.f64(measurement);
        }
        hash.f64(row.ranking.total_score);
        hash.digest(row.refinement.coordinate_sha256);
        hash.digest(row.ranking.coordinate_sha256);
        hash.f64(row.cluster.direct_rmsd_to_representative_angstrom);
        hash.digest(row.cluster.coordinate_sha256);
    }
    for movement in &value.torsion_moves {
        hash.f64(movement.delta_radians);
        hash.f64(movement.receptor_penalty);
        hash.f64(movement.internal_penalty);
        hash.f64(movement.combined_penalty);
    }
    hash_position_soa_owned(&mut hash, &value.producer_coordinates);
    for coordinates in [
        &value.rigid_coordinates.selected,
        &value.rigid_coordinates.comparison_v2,
        &value.rigid_coordinates.baseline_v3,
        &value.rigid_coordinates.clearance_v4,
    ] {
        hash_position_soa_owned(&mut hash, coordinates);
    }
    hash_position_soa_owned(&mut hash, &value.torsion_coordinates.optimized);
    hash_f64_channel(
        &mut hash,
        &value.torsion_coordinates.optimized_torsion_angles_radians,
    );
    hash_position_soa_owned(&mut hash, &value.torsion_coordinates.final_state);
    hash_f64_channel(
        &mut hash,
        &value.torsion_coordinates.final_torsion_angles_radians,
    );
    hash_position_soa_owned(&mut hash, &value.final_coordinates);
    for quaternion_channel in &value.final_quaternions {
        hash_f64_channel(&mut hash, quaternion_channel);
    }
    hash.finish()
}
