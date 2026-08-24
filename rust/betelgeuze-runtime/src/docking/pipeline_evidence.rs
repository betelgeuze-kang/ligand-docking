//! Canonical fixed64 pipeline evidence conversion and receipt authentication.

use super::*;

fn hash_coordinate_segment(
    hash: &mut CanonicalHasher,
    channels: [&[f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> Result<()> {
    let coordinates = coordinate_segment(channels, slot, ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence coordinate segment exceeds its buffer",
        )
    })?;
    hash.usize(ligand_count);
    for atom in 0..ligand_count {
        hash.f64(coordinates.x_angstrom[atom]);
        hash.f64(coordinates.y_angstrom[atom]);
        hash.f64(coordinates.z_angstrom[atom]);
    }
    Ok(())
}

fn hash_scalar_segment(
    hash: &mut CanonicalHasher,
    values: &[f64],
    slot: usize,
    ligand_count: usize,
) -> Result<()> {
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence scalar offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence scalar end overflowed",
        )
    })?;
    let segment = values.get(begin..end).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence scalar segment exceeds its buffer",
        )
    })?;
    hash.usize(segment.len());
    for value in segment {
        hash.f64(*value);
    }
    Ok(())
}

fn abi_rigid_profile_from_evidence(
    value: Fixed64RigidProfileEvidence,
) -> sys::bg_docking_rigid_refinement_evidence_v1 {
    sys::bg_docking_rigid_refinement_evidence_v1 {
        profile: value.profile,
        available: u8::from(value.available),
        reserved0: [0; 3],
        accepted_steps: value.accepted_steps,
        accepted_translation_steps: value.accepted_translation_steps,
        accepted_rotation_steps: value.accepted_rotation_steps,
        line_search_evaluation_count: value.line_search_evaluation_count,
        fallback_direction_step_count: value.fallback_direction_step_count,
        initial_penalty: value.initial_penalty,
        final_penalty: value.final_penalty,
        total_translation_angstrom: value.total_translation_angstrom,
        total_rotation_vector_radians: value.total_rotation_vector_radians,
        total_rotation_path_radians: value.total_rotation_path_radians,
        initial_centroid_offset_angstrom: value.initial_centroid_offset_angstrom,
        final_centroid_offset_angstrom: value.final_centroid_offset_angstrom,
        maximum_centroid_offset_angstrom: value.maximum_centroid_offset_angstrom,
        reserved: [0; 4],
    }
}

pub(super) fn abi_rigid_row_from_evidence(
    value: Fixed64RigidEvidence,
) -> sys::bg_docking_rigid_refinement_row_v1 {
    sys::bg_docking_rigid_refinement_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        failure_code: value.failure_code,
        candidate_mode: value.candidate_mode,
        selected_profile: value.selected_profile,
        baseline_duplicate_of_v2: u8::from(value.baseline_duplicate_of_v2),
        clearance_evaluated: u8::from(value.clearance_evaluated),
        clearance_selected: u8::from(value.clearance_selected),
        reserved0: 0,
        selected: abi_rigid_profile_from_evidence(value.selected),
        comparison_v2: abi_rigid_profile_from_evidence(value.comparison_v2),
        baseline_v3: abi_rigid_profile_from_evidence(value.baseline_v3),
        clearance_v4: abi_rigid_profile_from_evidence(value.clearance_v4),
        reserved: [0; 8],
    }
}

pub(super) fn abi_torsion_row_from_evidence(
    value: Fixed64TorsionEvidence,
) -> sys::bg_docking_torsion_v7_row_v1 {
    sys::bg_docking_torsion_v7_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        failure_code: value.failure_code,
        skip_reason: value.skip_reason,
        selection_reason: value.selection_reason,
        selection_window_reachable: u8::from(value.selection_window_reachable),
        evaluation_stopped_after_selection_window_became_unreachable: u8::from(
            value.evaluation_stopped_after_selection_window_became_unreachable,
        ),
        torsion_evaluated: u8::from(value.torsion_evaluated),
        torsion_variant_available: u8::from(value.torsion_variant_available),
        torsion_selected: u8::from(value.torsion_selected),
        reserved0: [0; 3],
        torsion_step_budget: value.torsion_step_budget,
        fixed_objective_evaluation_count: value.fixed_objective_evaluation_count,
        torsion_trial_objective_evaluation_count: value.torsion_trial_objective_evaluation_count,
        evaluated_torsion_steps: value.evaluated_torsion_steps,
        accepted_torsion_steps: value.accepted_torsion_steps,
        baseline_v6_accepted_steps: value.baseline_v6_accepted_steps,
        source_receptor_penalty: value.source_receptor_penalty,
        source_internal_penalty: value.source_internal_penalty,
        source_combined_penalty: value.source_combined_penalty,
        baseline_receptor_penalty: value.baseline_receptor_penalty,
        baseline_internal_penalty: value.baseline_internal_penalty,
        baseline_combined_penalty: value.baseline_combined_penalty,
        optimized_receptor_penalty: value.optimized_receptor_penalty,
        optimized_internal_penalty: value.optimized_internal_penalty,
        optimized_combined_penalty: value.optimized_combined_penalty,
        final_receptor_penalty: value.final_receptor_penalty,
        final_internal_penalty: value.final_internal_penalty,
        final_combined_penalty: value.final_combined_penalty,
        evaluated_total_torsion_path_radians: value.evaluated_total_torsion_path_radians,
        accepted_total_torsion_path_radians: value.accepted_total_torsion_path_radians,
        reserved: [0; 8],
    }
}

pub(super) fn abi_torsion_move_from_evidence(
    value: Fixed64TorsionMoveEvidence,
) -> sys::bg_docking_torsion_v7_move_v1 {
    sys::bg_docking_torsion_v7_move_v1 {
        slot_index: value.slot_index,
        move_index: value.move_index,
        evaluated: u8::from(value.evaluated),
        selected: u8::from(value.selected),
        reserved0: 0,
        rotatable_child_atom_index: value.rotatable_child_atom_index,
        delta_radians: value.delta_radians,
        receptor_penalty: value.receptor_penalty,
        internal_penalty: value.internal_penalty,
        combined_penalty: value.combined_penalty,
        reserved: [0; 4],
    }
}

pub(super) fn abi_refinement_row_from_evidence(
    value: Fixed64RefinementEvidence,
) -> sys::bg_docking_fixed64_refinement_row_v1 {
    sys::bg_docking_fixed64_refinement_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        failure_stage: value.failure_stage,
        coordinate_origin: value.coordinate_origin,
        rigid_failure_code: value.rigid_failure_code,
        torsion_v7_failure_code: value.torsion_v7_failure_code,
        selected_rigid_profile: value.selected_rigid_profile,
        downstream_candidate_state: value.downstream_candidate_state,
        torsion_v7_applicable: u8::from(value.torsion_v7_applicable),
        torsion_v7_selected: u8::from(value.torsion_v7_selected),
        coordinate_available: u8::from(value.coordinate_available),
        reserved0: 0,
        coordinate_sha256: value.coordinate_sha256,
        reserved: [0; 4],
    }
}

pub(super) fn abi_geometric_row_from_evidence(
    value: Fixed64GeometricEvidence,
) -> sys::bg_docking_geometric_admission_row_v1 {
    sys::bg_docking_geometric_admission_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        failure_code: value.failure_code,
        decision: value.decision,
        rank_eligible: u8::from(value.rank_eligible),
        reserved0: [0; 3],
        ligand_atom_count: value.ligand_atom_count,
        receptor_atom_count: value.receptor_atom_count,
        exact_pair_count: value.exact_pair_count,
        penetration_pair_count: value.penetration_pair_count,
        unique_ligand_penetration_atom_count: value.unique_ligand_penetration_atom_count,
        unique_ligand_heavy_atom_penetration_count: value
            .unique_ligand_heavy_atom_penetration_count,
        raw_minimum_distance_angstrom: value.raw_minimum_distance_angstrom,
        minimum_vdw_surface_gap_angstrom: value.minimum_vdw_surface_gap_angstrom,
        minimum_vdw_ratio: value.minimum_vdw_ratio,
        sphere_overlap_proxy_angstrom3: value.sphere_overlap_proxy_angstrom3,
        pocket_escape_angstrom: value.pocket_escape_angstrom,
        row_receipt_sha256: value.row_receipt_sha256,
        reserved1: 0,
    }
}

pub(super) fn abi_scorer_row_from_evidence(
    value: Fixed64ScorerEvidence,
) -> sys::bg_docking_scorer_v1_row_v1 {
    sys::bg_docking_scorer_v1_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        failure_code: value.failure_code,
        reserved0: 0,
        weighted_terms: value.weighted_terms,
        total_score: value.total_score,
        receptor_candidate_pair_count: value.receptor_candidate_pair_count,
        ligand_pair_count: value.ligand_pair_count,
        hbond_count: value.hbond_count,
        hydrophobic_contact_count: value.hydrophobic_contact_count,
        buried_polar_count: value.buried_polar_count,
        reserved: [0; 4],
    }
}

pub(super) fn abi_validity_row_from_evidence(
    value: Fixed64ValidityEvidence,
) -> sys::bg_docking_pose_validity_row_v1 {
    sys::bg_docking_pose_validity_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        failure_code: value.failure_code,
        upstream_scorer_failure_code: value.upstream_scorer_failure_code,
        passed_check_mask: value.passed_check_mask,
        blocker_mask: value.blocker_mask,
        observed_count: value.observed_count,
        atom_count: value.atom_count,
        rotation_orthogonality_max_error: value.rotation_orthogonality_max_error,
        rotation_determinant: value.rotation_determinant,
        max_bond_length_delta_angstrom: value.max_bond_length_delta_angstrom,
        minimum_ligand_nonbonded_distance_angstrom: value
            .minimum_ligand_nonbonded_distance_angstrom,
        evaluated_ligand_nonbonded_pair_count: value.evaluated_ligand_nonbonded_pair_count,
        excluded_ligand_pair_count: value.excluded_ligand_pair_count,
        minimum_receptor_ligand_distance_angstrom: value.minimum_receptor_ligand_distance_angstrom,
        evaluated_receptor_ligand_pair_count: value.evaluated_receptor_ligand_pair_count,
        minimum_declared_chiral_volume: value.minimum_declared_chiral_volume,
        declared_chirality_center_count: value.declared_chirality_center_count,
        maximum_pocket_center_distance_angstrom: value.maximum_pocket_center_distance_angstrom,
        element_vdw_ligand_pair_count: value.element_vdw_ligand_pair_count,
        element_vdw_ligand_severe_overlap_count: value.element_vdw_ligand_severe_overlap_count,
        element_vdw_ligand_minimum_distance_angstrom: value
            .element_vdw_ligand_minimum_distance_angstrom,
        element_vdw_ligand_minimum_ratio: value.element_vdw_ligand_minimum_ratio,
        element_vdw_receptor_candidate_pair_count: value.element_vdw_receptor_candidate_pair_count,
        element_vdw_receptor_full_cartesian_pair_count: value
            .element_vdw_receptor_full_cartesian_pair_count,
        element_vdw_receptor_cell_count: value.element_vdw_receptor_cell_count,
        element_vdw_receptor_severe_overlap_count: value.element_vdw_receptor_severe_overlap_count,
        element_vdw_receptor_minimum_distance_angstrom: value
            .element_vdw_receptor_minimum_distance_angstrom,
        element_vdw_receptor_minimum_ratio: value.element_vdw_receptor_minimum_ratio,
        reserved: [0; 4],
    }
}

pub(super) fn abi_ranking_row_from_evidence(
    value: Fixed64RankingEvidence,
) -> sys::bg_docking_stable_top_k_row_v1 {
    sys::bg_docking_stable_top_k_row_v1 {
        slot_index: value.slot_index,
        rank_eligible: u8::from(value.rank_eligible),
        valid_rank_eligible: u8::from(value.valid_rank_eligible),
        reserved0: 0,
        stable_rank: value.stable_rank,
        stable_valid_rank: value.stable_valid_rank,
        total_score: value.total_score,
        coordinate_sha256: value.coordinate_sha256,
        reserved: [0; 4],
    }
}

pub(super) fn abi_cluster_row_from_evidence(
    value: Fixed64ClusterEvidence,
) -> sys::bg_docking_rmsd_cluster_row_v1 {
    sys::bg_docking_rmsd_cluster_row_v1 {
        slot_index: value.slot_index,
        status: value.status,
        cluster_eligible: u8::from(value.cluster_eligible),
        representative: u8::from(value.representative),
        top_k_representative: u8::from(value.top_k_representative),
        reserved0: 0,
        stable_valid_rank: value.stable_valid_rank,
        cluster_id: value.cluster_id,
        representative_slot_index: value.representative_slot_index,
        cluster_rank: value.cluster_rank,
        top_k_rank: value.top_k_rank,
        cluster_size: value.cluster_size,
        reserved1: 0,
        direct_rmsd_to_representative_angstrom: value.direct_rmsd_to_representative_angstrom,
        coordinate_sha256: value.coordinate_sha256,
        reserved: [0; 4],
    }
}

pub(super) fn abi_pipeline_row_from_evidence(
    value: Fixed64PipelineRow,
) -> sys::bg_docking_fixed64_pipeline_row_v2 {
    sys::bg_docking_fixed64_pipeline_row_v2 {
        slot_index: value.slot_index,
        producer_status: value.producer_status,
        producer_failure_code: value.producer_failure_code,
        initial_admission_decision: value.initial_admission_decision,
        requested_refinement_mode: value.requested_refinement_mode,
        effective_refinement_mode: value.effective_refinement_mode,
        refinement_status: value.refinement_status,
        refinement_failure_stage: value.refinement_failure_stage,
        post_admission_status: value.post_admission_status,
        post_admission_failure_code: value.post_admission_failure_code,
        post_admission_decision: value.post_admission_decision,
        post_admission_rank_eligible: u8::from(value.post_admission_rank_eligible),
        reserved0: [0; 3],
        scorer_status: value.scorer_status,
        scorer_failure_code: value.scorer_failure_code,
        validity_status: value.validity_status,
        validity_failure_code: value.validity_failure_code,
        stable_rank: value.stable_rank,
        stable_valid_rank: value.stable_valid_rank,
        cluster_status: value.cluster_status,
        cluster_id: value.cluster_id,
        cluster_rank: value.cluster_rank,
        top_k_rank: value.top_k_rank,
        producer_row_receipt_sha256: value.producer_row_receipt_sha256,
        final_coordinate_sha256: value.final_coordinate_sha256,
        refinement_evidence_sha256: value.refinement_evidence_sha256,
        post_admission_row_receipt_sha256: value.post_admission_row_receipt_sha256,
        scorer_evidence_sha256: value.scorer_evidence_sha256,
        validity_evidence_sha256: value.validity_evidence_sha256,
        ranking_evidence_sha256: value.ranking_evidence_sha256,
        cluster_evidence_sha256: value.cluster_evidence_sha256,
        row_receipt_sha256: value.row_receipt_sha256,
        reserved: [0; 4],
    }
}

fn hash_rigid_evidence(
    hash: &mut CanonicalHasher,
    value: &sys::bg_docking_rigid_refinement_evidence_v1,
) {
    hash.i32(value.profile);
    hash.byte(value.available);
    hash.u64(value.accepted_steps);
    hash.u64(value.accepted_translation_steps);
    hash.u64(value.accepted_rotation_steps);
    hash.u64(value.line_search_evaluation_count);
    hash.u64(value.fallback_direction_step_count);
    hash.f64(value.initial_penalty);
    hash.f64(value.final_penalty);
    for component in value.total_translation_angstrom {
        hash.f64(component);
    }
    for component in value.total_rotation_vector_radians {
        hash.f64(component);
    }
    hash.f64(value.total_rotation_path_radians);
    hash.f64(value.initial_centroid_offset_angstrom);
    hash.f64(value.final_centroid_offset_angstrom);
    hash.f64(value.maximum_centroid_offset_angstrom);
}

#[allow(clippy::too_many_arguments)]
pub(super) fn canonical_refinement_evidence(
    slot: usize,
    ligand_count: usize,
    rigid_row: &sys::bg_docking_rigid_refinement_row_v1,
    torsion_row: &sys::bg_docking_torsion_v7_row_v1,
    torsion_moves: &[sys::bg_docking_torsion_v7_move_v1],
    refinement_row: &sys::bg_docking_fixed64_refinement_row_v1,
    rigid_coordinates: [&[f64]; 12],
    torsion_coordinates: [&[f64]; 8],
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
) -> Result<Sha256> {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_evidence/1.0.0");
    hash.usize(slot);
    hash.i32(rigid_row.status);
    hash.i32(rigid_row.failure_code);
    hash.i32(rigid_row.candidate_mode);
    hash.i32(rigid_row.selected_profile);
    hash.byte(rigid_row.baseline_duplicate_of_v2);
    hash.byte(rigid_row.clearance_evaluated);
    hash.byte(rigid_row.clearance_selected);
    hash_rigid_evidence(&mut hash, &rigid_row.selected);
    hash_rigid_evidence(&mut hash, &rigid_row.comparison_v2);
    hash_rigid_evidence(&mut hash, &rigid_row.baseline_v3);
    hash_rigid_evidence(&mut hash, &rigid_row.clearance_v4);
    for offset in [0, 3, 6, 9] {
        hash_coordinate_segment(
            &mut hash,
            [
                rigid_coordinates[offset],
                rigid_coordinates[offset + 1],
                rigid_coordinates[offset + 2],
            ],
            slot,
            ligand_count,
        )?;
    }
    hash.i32(torsion_row.status);
    hash.i32(torsion_row.failure_code);
    hash.i32(torsion_row.skip_reason);
    hash.i32(torsion_row.selection_reason);
    hash.byte(torsion_row.selection_window_reachable);
    hash.byte(torsion_row.evaluation_stopped_after_selection_window_became_unreachable);
    hash.byte(torsion_row.torsion_evaluated);
    hash.byte(torsion_row.torsion_variant_available);
    hash.byte(torsion_row.torsion_selected);
    hash.u64(torsion_row.torsion_step_budget);
    hash.u64(torsion_row.fixed_objective_evaluation_count);
    hash.u64(torsion_row.torsion_trial_objective_evaluation_count);
    hash.u64(torsion_row.evaluated_torsion_steps);
    hash.u64(torsion_row.accepted_torsion_steps);
    hash.u64(torsion_row.baseline_v6_accepted_steps);
    for value in torsion_row_values(torsion_row) {
        hash.f64(value);
    }
    let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
    let move_begin = slot.checked_mul(moves_per_slot).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement move offset overflowed",
        )
    })?;
    let move_end = move_begin.checked_add(moves_per_slot).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement move end overflowed",
        )
    })?;
    for movement in torsion_moves.get(move_begin..move_end).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 refinement move evidence is incomplete",
        )
    })? {
        hash.u32(movement.slot_index);
        hash.u32(movement.move_index);
        hash.byte(movement.evaluated);
        hash.byte(movement.selected);
        hash.u64(movement.rotatable_child_atom_index);
        hash.f64(movement.delta_radians);
        hash.f64(movement.receptor_penalty);
        hash.f64(movement.internal_penalty);
        hash.f64(movement.combined_penalty);
    }
    hash_coordinate_segment(
        &mut hash,
        [
            torsion_coordinates[0],
            torsion_coordinates[1],
            torsion_coordinates[2],
        ],
        slot,
        ligand_count,
    )?;
    hash_scalar_segment(&mut hash, torsion_coordinates[3], slot, ligand_count)?;
    hash_coordinate_segment(
        &mut hash,
        [
            torsion_coordinates[4],
            torsion_coordinates[5],
            torsion_coordinates[6],
        ],
        slot,
        ligand_count,
    )?;
    hash_scalar_segment(&mut hash, torsion_coordinates[7], slot, ligand_count)?;
    hash.i32(refinement_row.status);
    hash.i32(refinement_row.failure_stage);
    hash.i32(refinement_row.coordinate_origin);
    hash.i32(refinement_row.rigid_failure_code);
    hash.i32(refinement_row.torsion_v7_failure_code);
    hash.i32(refinement_row.selected_rigid_profile);
    hash.i32(refinement_row.downstream_candidate_state);
    hash.byte(refinement_row.torsion_v7_applicable);
    hash.byte(refinement_row.torsion_v7_selected);
    hash.byte(refinement_row.coordinate_available);
    hash.digest(refinement_row.coordinate_sha256);
    hash_coordinate_segment(&mut hash, final_coordinates, slot, ligand_count)?;
    hash.f64(final_quaternions[0][slot]);
    hash.f64(final_quaternions[1][slot]);
    hash.f64(final_quaternions[2][slot]);
    hash.f64(final_quaternions[3][slot]);
    Ok(hash.finish())
}

pub(super) fn canonical_scorer_evidence(row: &sys::bg_docking_scorer_v1_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scorer_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.i32(row.failure_code);
    for term in row.weighted_terms {
        hash.f64(term);
    }
    hash.f64(row.total_score);
    hash.u64(row.receptor_candidate_pair_count);
    hash.u64(row.ligand_pair_count);
    hash.u64(row.hbond_count);
    hash.u64(row.hydrophobic_contact_count);
    hash.u64(row.buried_polar_count);
    hash.finish()
}

pub(super) fn canonical_validity_evidence(row: &sys::bg_docking_pose_validity_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_validity_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.i32(row.failure_code);
    hash.i32(row.upstream_scorer_failure_code);
    hash.u32(row.passed_check_mask);
    hash.u32(row.blocker_mask);
    hash.u64(row.observed_count);
    hash.u64(row.atom_count);
    hash.f64(row.rotation_orthogonality_max_error);
    hash.f64(row.rotation_determinant);
    hash.f64(row.max_bond_length_delta_angstrom);
    hash.f64(row.minimum_ligand_nonbonded_distance_angstrom);
    hash.u64(row.evaluated_ligand_nonbonded_pair_count);
    hash.u64(row.excluded_ligand_pair_count);
    hash.f64(row.minimum_receptor_ligand_distance_angstrom);
    hash.u64(row.evaluated_receptor_ligand_pair_count);
    hash.f64(row.minimum_declared_chiral_volume);
    hash.u64(row.declared_chirality_center_count);
    hash.f64(row.maximum_pocket_center_distance_angstrom);
    hash.u64(row.element_vdw_ligand_pair_count);
    hash.u64(row.element_vdw_ligand_severe_overlap_count);
    hash.f64(row.element_vdw_ligand_minimum_distance_angstrom);
    hash.f64(row.element_vdw_ligand_minimum_ratio);
    hash.u64(row.element_vdw_receptor_candidate_pair_count);
    hash.u64(row.element_vdw_receptor_full_cartesian_pair_count);
    hash.u64(row.element_vdw_receptor_cell_count);
    hash.u64(row.element_vdw_receptor_severe_overlap_count);
    hash.f64(row.element_vdw_receptor_minimum_distance_angstrom);
    hash.f64(row.element_vdw_receptor_minimum_ratio);
    hash.finish()
}

pub(super) fn canonical_ranking_evidence(row: &sys::bg_docking_stable_top_k_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_ranking_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.byte(row.rank_eligible);
    hash.byte(row.valid_rank_eligible);
    hash.u32(row.stable_rank);
    hash.u32(row.stable_valid_rank);
    hash.f64(row.total_score);
    hash.digest(row.coordinate_sha256);
    hash.finish()
}

pub(super) fn canonical_cluster_evidence(row: &sys::bg_docking_rmsd_cluster_row_v1) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_cluster_evidence/1.0.0");
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.byte(row.cluster_eligible);
    hash.byte(row.representative);
    hash.byte(row.top_k_representative);
    hash.u32(row.stable_valid_rank);
    hash.u32(row.cluster_id);
    hash.u32(row.representative_slot_index);
    hash.u32(row.cluster_rank);
    hash.u32(row.top_k_rank);
    hash.u32(row.cluster_size);
    hash.f64(row.direct_rmsd_to_representative_angstrom);
    hash.digest(row.coordinate_sha256);
    hash.finish()
}
#[allow(clippy::too_many_arguments)]
pub(super) fn canonical_pipeline_row_receipt(
    row: &sys::bg_docking_fixed64_pipeline_row_v2,
    component_binding_receipt: Sha256,
    refinement_policy_receipt: Sha256,
    post_admission_policy_receipt: Sha256,
    refinement_evidence: Sha256,
    scorer_evidence: Sha256,
    validity_evidence: Sha256,
    ranking_evidence: Sha256,
    cluster_evidence: Sha256,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_complete_pipeline_row/2.0.0");
    hash.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);
    hash.digest(component_binding_receipt);
    hash.digest(refinement_policy_receipt);
    hash.digest(post_admission_policy_receipt);
    hash.u32(row.slot_index);
    for value in [
        row.producer_status,
        row.producer_failure_code,
        row.initial_admission_decision,
        row.requested_refinement_mode,
        row.effective_refinement_mode,
        row.refinement_status,
        row.refinement_failure_stage,
        row.post_admission_status,
        row.post_admission_failure_code,
        row.post_admission_decision,
    ] {
        hash.i32(value);
    }
    hash.byte(row.post_admission_rank_eligible);
    for value in [
        row.scorer_status,
        row.scorer_failure_code,
        row.validity_status,
        row.validity_failure_code,
    ] {
        hash.i32(value);
    }
    hash.u32(row.stable_rank);
    hash.u32(row.stable_valid_rank);
    hash.i32(row.cluster_status);
    hash.u32(row.cluster_id);
    hash.u32(row.cluster_rank);
    hash.u32(row.top_k_rank);
    hash.digest(row.producer_row_receipt_sha256);
    hash.digest(row.final_coordinate_sha256);
    hash.digest(refinement_evidence);
    hash.digest(row.post_admission_row_receipt_sha256);
    hash.digest(scorer_evidence);
    hash.digest(validity_evidence);
    hash.digest(ranking_evidence);
    hash.digest(cluster_evidence);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_pipeline_receipt_bindings(
    row: &sys::bg_docking_fixed64_pipeline_row_v2,
    component_binding_receipt: Sha256,
    refinement_policy_receipt: Sha256,
    post_admission_policy_receipt: Sha256,
    expected_refinement_evidence: Sha256,
    expected_scorer_evidence: Sha256,
    expected_validity_evidence: Sha256,
    expected_ranking_evidence: Sha256,
    expected_cluster_evidence: Sha256,
) -> Result<()> {
    let expected_row_receipt = canonical_pipeline_row_receipt(
        row,
        component_binding_receipt,
        refinement_policy_receipt,
        post_admission_policy_receipt,
        expected_refinement_evidence,
        expected_scorer_evidence,
        expected_validity_evidence,
        expected_ranking_evidence,
        expected_cluster_evidence,
    );
    if row.refinement_evidence_sha256 != expected_refinement_evidence
        || !digest_present(&row.post_admission_row_receipt_sha256)
        || row.scorer_evidence_sha256 != expected_scorer_evidence
        || row.validity_evidence_sha256 != expected_validity_evidence
        || row.ranking_evidence_sha256 != expected_ranking_evidence
        || row.cluster_evidence_sha256 != expected_cluster_evidence
        || row.row_receipt_sha256 != expected_row_receipt
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 pipeline receipt graph does not authenticate its component evidence",
        ));
    }
    Ok(())
}
