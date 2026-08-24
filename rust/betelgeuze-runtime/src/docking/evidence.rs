//! Conversion from authenticated native ABI rows to public fixed64 evidence.

use super::*;

pub(super) fn require_authority_false(fields: &[(u8, &str)]) -> Result<()> {
    for (value, label) in fields {
        if bool_from_abi(*value, label)? {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} unexpectedly became authorized"),
            ));
        }
    }
    Ok(())
}

pub(super) fn authority_disposition(
    output: &sys::bg_docking_fixed64_pipeline_output_v2,
    producer: &sys::bg_docking_fixed64_producer_output_v1,
) -> Result<Fixed64AuthorityDisposition> {
    Ok(Fixed64AuthorityDisposition {
        result_dependent_input_consumed: bool_from_abi(
            output.result_dependent_input_consumed,
            "result-dependent input",
        )?,
        fallback_allowed: bool_from_abi(output.fallback_allowed, "fallback")?,
        multi_anchor_consumed: bool_from_abi(
            producer.multi_anchor_consumed,
            "multi-anchor consumption",
        )?,
        denominator_preserved: bool_from_abi(output.denominator_preserved, "denominator")?,
        molecular_execution_authorized: bool_from_abi(
            output.molecular_execution_authorized,
            "molecular execution",
        )?,
        reservation_authorized: bool_from_abi(output.reservation_authorized, "reservation")?,
        benchmark_execution_authorized: bool_from_abi(
            output.benchmark_execution_authorized,
            "benchmark execution",
        )?,
        existing_rank_auto_change_authorized: bool_from_abi(
            output.existing_rank_auto_change_authorized,
            "rank mutation",
        )?,
        customer_pose_emission_authorized: bool_from_abi(
            output.customer_pose_emission_authorized,
            "customer pose emission",
        )?,
        production_claim_authorized: bool_from_abi(
            output.production_claim_authorized,
            "production claim",
        )?,
        scientific_claim_authorized: bool_from_abi(
            output.scientific_claim_authorized,
            "scientific claim",
        )?,
    })
}

pub(super) fn geometric_evidence(
    row: &sys::bg_docking_geometric_admission_row_v1,
) -> Result<Fixed64GeometricEvidence> {
    Ok(Fixed64GeometricEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        decision: row.decision,
        rank_eligible: bool_from_abi(row.rank_eligible, "geometric rank eligibility")?,
        ligand_atom_count: row.ligand_atom_count,
        receptor_atom_count: row.receptor_atom_count,
        exact_pair_count: row.exact_pair_count,
        penetration_pair_count: row.penetration_pair_count,
        unique_ligand_penetration_atom_count: row.unique_ligand_penetration_atom_count,
        unique_ligand_heavy_atom_penetration_count: row.unique_ligand_heavy_atom_penetration_count,
        raw_minimum_distance_angstrom: row.raw_minimum_distance_angstrom,
        minimum_vdw_surface_gap_angstrom: row.minimum_vdw_surface_gap_angstrom,
        minimum_vdw_ratio: row.minimum_vdw_ratio,
        sphere_overlap_proxy_angstrom3: row.sphere_overlap_proxy_angstrom3,
        pocket_escape_angstrom: row.pocket_escape_angstrom,
        row_receipt_sha256: row.row_receipt_sha256,
    })
}

pub(super) fn producer_evidence(
    row: &sys::bg_docking_fixed64_producer_row_v1,
) -> Result<Fixed64ProducerEvidence> {
    Ok(Fixed64ProducerEvidence {
        slot_index: row.slot_index,
        lane: row.lane,
        status: row.status,
        failure_code: row.failure_code,
        placement_kind: row.placement_kind,
        component_failure_code: row.component_failure_code,
        backend: Backend::from_raw(row.backend)?,
        ligand_atom_count: row.ligand_atom_count,
        coordinate_offset: row.coordinate_offset,
        coordinates_available: bool_from_abi(
            row.coordinates_available,
            "producer coordinates available",
        )?,
        steric_precheck_passed: bool_from_abi(
            row.steric_precheck_passed,
            "producer steric precheck",
        )?,
        source_identity_verified: bool_from_abi(
            row.source_identity_verified,
            "producer source identity",
        )?,
        allocation_identity_verified: bool_from_abi(
            row.allocation_identity_verified,
            "producer allocation identity",
        )?,
        geometric_identity_verified: bool_from_abi(
            row.geometric_identity_verified,
            "producer geometric identity",
        )?,
        denominator_preserved: bool_from_abi(
            row.denominator_preserved,
            "producer row denominator",
        )?,
        placement_quaternion: [
            row.placement_quaternion_x,
            row.placement_quaternion_y,
            row.placement_quaternion_z,
            row.placement_quaternion_w,
        ],
        allocation_slot_receipt_sha256: row.allocation_slot_receipt_sha256,
        source_payload_receipt_sha256: row.source_payload_receipt_sha256,
        source_proposal_sha256: row.source_proposal_sha256,
        source_coordinate_sha256: row.source_coordinate_sha256,
        placement_receipt_sha256: row.placement_receipt_sha256,
        output_proposal_sha256: row.output_proposal_sha256,
        output_coordinate_sha256: row.output_coordinate_sha256,
        row_receipt_sha256: row.row_receipt_sha256,
        geometric: geometric_evidence(&row.geometric_admission)?,
    })
}

fn rigid_profile_evidence(
    evidence: &sys::bg_docking_rigid_refinement_evidence_v1,
) -> Result<Fixed64RigidProfileEvidence> {
    Ok(Fixed64RigidProfileEvidence {
        profile: evidence.profile,
        available: bool_from_abi(evidence.available, "rigid profile availability")?,
        accepted_steps: evidence.accepted_steps,
        accepted_translation_steps: evidence.accepted_translation_steps,
        accepted_rotation_steps: evidence.accepted_rotation_steps,
        line_search_evaluation_count: evidence.line_search_evaluation_count,
        fallback_direction_step_count: evidence.fallback_direction_step_count,
        initial_penalty: evidence.initial_penalty,
        final_penalty: evidence.final_penalty,
        total_translation_angstrom: evidence.total_translation_angstrom,
        total_rotation_vector_radians: evidence.total_rotation_vector_radians,
        total_rotation_path_radians: evidence.total_rotation_path_radians,
        initial_centroid_offset_angstrom: evidence.initial_centroid_offset_angstrom,
        final_centroid_offset_angstrom: evidence.final_centroid_offset_angstrom,
        maximum_centroid_offset_angstrom: evidence.maximum_centroid_offset_angstrom,
    })
}

pub(super) fn rigid_evidence(
    row: &sys::bg_docking_rigid_refinement_row_v1,
) -> Result<Fixed64RigidEvidence> {
    Ok(Fixed64RigidEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        candidate_mode: row.candidate_mode,
        selected_profile: row.selected_profile,
        baseline_duplicate_of_v2: bool_from_abi(
            row.baseline_duplicate_of_v2,
            "rigid V3 baseline duplicate",
        )?,
        clearance_evaluated: bool_from_abi(row.clearance_evaluated, "rigid clearance evaluated")?,
        clearance_selected: bool_from_abi(row.clearance_selected, "rigid clearance selected")?,
        selected: rigid_profile_evidence(&row.selected)?,
        comparison_v2: rigid_profile_evidence(&row.comparison_v2)?,
        baseline_v3: rigid_profile_evidence(&row.baseline_v3)?,
        clearance_v4: rigid_profile_evidence(&row.clearance_v4)?,
    })
}

pub(super) fn torsion_evidence(
    row: &sys::bg_docking_torsion_v7_row_v1,
) -> Result<Fixed64TorsionEvidence> {
    Ok(Fixed64TorsionEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        skip_reason: row.skip_reason,
        selection_reason: row.selection_reason,
        selection_window_reachable: bool_from_abi(
            row.selection_window_reachable,
            "torsion selection window reachable",
        )?,
        evaluation_stopped_after_selection_window_became_unreachable: bool_from_abi(
            row.evaluation_stopped_after_selection_window_became_unreachable,
            "torsion evaluation stopped after unreachable selection window",
        )?,
        torsion_evaluated: bool_from_abi(row.torsion_evaluated, "torsion evaluated")?,
        torsion_variant_available: bool_from_abi(
            row.torsion_variant_available,
            "torsion variant available",
        )?,
        torsion_selected: bool_from_abi(row.torsion_selected, "torsion selected")?,
        torsion_step_budget: row.torsion_step_budget,
        fixed_objective_evaluation_count: row.fixed_objective_evaluation_count,
        torsion_trial_objective_evaluation_count: row.torsion_trial_objective_evaluation_count,
        evaluated_torsion_steps: row.evaluated_torsion_steps,
        accepted_torsion_steps: row.accepted_torsion_steps,
        baseline_v6_accepted_steps: row.baseline_v6_accepted_steps,
        source_receptor_penalty: row.source_receptor_penalty,
        source_internal_penalty: row.source_internal_penalty,
        source_combined_penalty: row.source_combined_penalty,
        baseline_receptor_penalty: row.baseline_receptor_penalty,
        baseline_internal_penalty: row.baseline_internal_penalty,
        baseline_combined_penalty: row.baseline_combined_penalty,
        optimized_receptor_penalty: row.optimized_receptor_penalty,
        optimized_internal_penalty: row.optimized_internal_penalty,
        optimized_combined_penalty: row.optimized_combined_penalty,
        final_receptor_penalty: row.final_receptor_penalty,
        final_internal_penalty: row.final_internal_penalty,
        final_combined_penalty: row.final_combined_penalty,
        evaluated_total_torsion_path_radians: row.evaluated_total_torsion_path_radians,
        accepted_total_torsion_path_radians: row.accepted_total_torsion_path_radians,
    })
}

pub(super) fn torsion_move_evidence(
    move_evidence: &sys::bg_docking_torsion_v7_move_v1,
) -> Result<Fixed64TorsionMoveEvidence> {
    Ok(Fixed64TorsionMoveEvidence {
        slot_index: move_evidence.slot_index,
        move_index: move_evidence.move_index,
        evaluated: bool_from_abi(move_evidence.evaluated, "torsion move evaluated")?,
        selected: bool_from_abi(move_evidence.selected, "torsion move selected")?,
        rotatable_child_atom_index: move_evidence.rotatable_child_atom_index,
        delta_radians: move_evidence.delta_radians,
        receptor_penalty: move_evidence.receptor_penalty,
        internal_penalty: move_evidence.internal_penalty,
        combined_penalty: move_evidence.combined_penalty,
    })
}

pub(super) fn refinement_evidence(
    row: &sys::bg_docking_fixed64_refinement_row_v1,
) -> Result<Fixed64RefinementEvidence> {
    Ok(Fixed64RefinementEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_stage: row.failure_stage,
        coordinate_origin: row.coordinate_origin,
        rigid_failure_code: row.rigid_failure_code,
        torsion_v7_failure_code: row.torsion_v7_failure_code,
        selected_rigid_profile: row.selected_rigid_profile,
        downstream_candidate_state: row.downstream_candidate_state,
        torsion_v7_applicable: bool_from_abi(
            row.torsion_v7_applicable,
            "torsion V7 applicability",
        )?,
        torsion_v7_selected: bool_from_abi(row.torsion_v7_selected, "torsion V7 selection")?,
        coordinate_available: bool_from_abi(
            row.coordinate_available,
            "refinement coordinate availability",
        )?,
        coordinate_sha256: row.coordinate_sha256,
    })
}

pub(super) fn scorer_evidence(row: &sys::bg_docking_scorer_v1_row_v1) -> Fixed64ScorerEvidence {
    Fixed64ScorerEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        weighted_terms: row.weighted_terms,
        total_score: row.total_score,
        receptor_candidate_pair_count: row.receptor_candidate_pair_count,
        ligand_pair_count: row.ligand_pair_count,
        hbond_count: row.hbond_count,
        hydrophobic_contact_count: row.hydrophobic_contact_count,
        buried_polar_count: row.buried_polar_count,
    }
}

pub(super) fn validity_evidence(
    row: &sys::bg_docking_pose_validity_row_v1,
) -> Fixed64ValidityEvidence {
    Fixed64ValidityEvidence {
        slot_index: row.slot_index,
        status: row.status,
        failure_code: row.failure_code,
        upstream_scorer_failure_code: row.upstream_scorer_failure_code,
        passed_check_mask: row.passed_check_mask,
        blocker_mask: row.blocker_mask,
        observed_count: row.observed_count,
        atom_count: row.atom_count,
        rotation_orthogonality_max_error: row.rotation_orthogonality_max_error,
        rotation_determinant: row.rotation_determinant,
        max_bond_length_delta_angstrom: row.max_bond_length_delta_angstrom,
        minimum_ligand_nonbonded_distance_angstrom: row.minimum_ligand_nonbonded_distance_angstrom,
        evaluated_ligand_nonbonded_pair_count: row.evaluated_ligand_nonbonded_pair_count,
        excluded_ligand_pair_count: row.excluded_ligand_pair_count,
        minimum_receptor_ligand_distance_angstrom: row.minimum_receptor_ligand_distance_angstrom,
        evaluated_receptor_ligand_pair_count: row.evaluated_receptor_ligand_pair_count,
        minimum_declared_chiral_volume: row.minimum_declared_chiral_volume,
        declared_chirality_center_count: row.declared_chirality_center_count,
        maximum_pocket_center_distance_angstrom: row.maximum_pocket_center_distance_angstrom,
        element_vdw_ligand_pair_count: row.element_vdw_ligand_pair_count,
        element_vdw_ligand_severe_overlap_count: row.element_vdw_ligand_severe_overlap_count,
        element_vdw_ligand_minimum_distance_angstrom: row
            .element_vdw_ligand_minimum_distance_angstrom,
        element_vdw_ligand_minimum_ratio: row.element_vdw_ligand_minimum_ratio,
        element_vdw_receptor_candidate_pair_count: row.element_vdw_receptor_candidate_pair_count,
        element_vdw_receptor_full_cartesian_pair_count: row
            .element_vdw_receptor_full_cartesian_pair_count,
        element_vdw_receptor_cell_count: row.element_vdw_receptor_cell_count,
        element_vdw_receptor_severe_overlap_count: row.element_vdw_receptor_severe_overlap_count,
        element_vdw_receptor_minimum_distance_angstrom: row
            .element_vdw_receptor_minimum_distance_angstrom,
        element_vdw_receptor_minimum_ratio: row.element_vdw_receptor_minimum_ratio,
    }
}

pub(super) fn ranking_evidence(
    row: &sys::bg_docking_stable_top_k_row_v1,
) -> Result<Fixed64RankingEvidence> {
    Ok(Fixed64RankingEvidence {
        slot_index: row.slot_index,
        rank_eligible: bool_from_abi(row.rank_eligible, "rank eligibility")?,
        valid_rank_eligible: bool_from_abi(row.valid_rank_eligible, "valid-rank eligibility")?,
        stable_rank: row.stable_rank,
        stable_valid_rank: row.stable_valid_rank,
        total_score: row.total_score,
        coordinate_sha256: row.coordinate_sha256,
    })
}

pub(super) fn cluster_evidence(
    row: &sys::bg_docking_rmsd_cluster_row_v1,
) -> Result<Fixed64ClusterEvidence> {
    Ok(Fixed64ClusterEvidence {
        slot_index: row.slot_index,
        status: row.status,
        cluster_eligible: bool_from_abi(row.cluster_eligible, "cluster eligibility")?,
        representative: bool_from_abi(row.representative, "cluster representative")?,
        top_k_representative: bool_from_abi(
            row.top_k_representative,
            "cluster Top-K representative",
        )?,
        stable_valid_rank: row.stable_valid_rank,
        cluster_id: row.cluster_id,
        representative_slot_index: row.representative_slot_index,
        cluster_rank: row.cluster_rank,
        top_k_rank: row.top_k_rank,
        cluster_size: row.cluster_size,
        direct_rmsd_to_representative_angstrom: row.direct_rmsd_to_representative_angstrom,
        coordinate_sha256: row.coordinate_sha256,
    })
}

pub(super) fn pipeline_row(
    row: &sys::bg_docking_fixed64_pipeline_row_v2,
) -> Result<Fixed64PipelineRow> {
    Ok(Fixed64PipelineRow {
        slot_index: row.slot_index,
        producer_status: row.producer_status,
        producer_failure_code: row.producer_failure_code,
        initial_admission_decision: row.initial_admission_decision,
        requested_refinement_mode: row.requested_refinement_mode,
        effective_refinement_mode: row.effective_refinement_mode,
        refinement_status: row.refinement_status,
        refinement_failure_stage: row.refinement_failure_stage,
        post_admission_status: row.post_admission_status,
        post_admission_failure_code: row.post_admission_failure_code,
        post_admission_decision: row.post_admission_decision,
        post_admission_rank_eligible: bool_from_abi(
            row.post_admission_rank_eligible,
            "post-admission rank eligibility",
        )?,
        scorer_status: row.scorer_status,
        scorer_failure_code: row.scorer_failure_code,
        validity_status: row.validity_status,
        validity_failure_code: row.validity_failure_code,
        stable_rank: row.stable_rank,
        stable_valid_rank: row.stable_valid_rank,
        cluster_status: row.cluster_status,
        cluster_id: row.cluster_id,
        cluster_rank: row.cluster_rank,
        top_k_rank: row.top_k_rank,
        producer_row_receipt_sha256: row.producer_row_receipt_sha256,
        final_coordinate_sha256: row.final_coordinate_sha256,
        refinement_evidence_sha256: row.refinement_evidence_sha256,
        post_admission_row_receipt_sha256: row.post_admission_row_receipt_sha256,
        scorer_evidence_sha256: row.scorer_evidence_sha256,
        validity_evidence_sha256: row.validity_evidence_sha256,
        ranking_evidence_sha256: row.ranking_evidence_sha256,
        cluster_evidence_sha256: row.cluster_evidence_sha256,
        row_receipt_sha256: row.row_receipt_sha256,
    })
}
