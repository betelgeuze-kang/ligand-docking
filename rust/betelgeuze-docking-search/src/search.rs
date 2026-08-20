use std::collections::BTreeSet;

use crate::anchors::compatible_combinations;
use crate::cluster::cluster_and_top_k;
use crate::identity::{
    allocation_sha256, candidate_rows_sha256, input_sha256, orientation_sha256, poses_sha256,
};
use crate::model::{
    CandidateReason, CandidateRow, CandidateStatus, EnergyForceEvaluator, SearchConfig,
    SearchInput, SearchResult, MAX_CANDIDATE_COORDINATES, MAX_EVALUATION_DETAIL_BYTES,
    MAX_GENERATED_CANDIDATES, MAX_LEDGER_PAYLOAD_BYTES, MAX_LIGAND_ANCHORS, MAX_LIGAND_ATOMS,
    MAX_ORIENTATIONS, MAX_PAIR_EVALUATIONS, MAX_RECEPTOR_ATOMS, MAX_REFINEMENT_STEPS,
    MAX_SURFACE_SAMPLES, MAX_TOP_K,
};
use crate::prune::{coarse_select, detailed_select};
use crate::receipt::SearchReceipt;
use crate::refine::refine_candidate;
use crate::short_range::{ShortRangeConfig, ShortRangeEvaluator};
use crate::so3::orientations;
use crate::surface::place_candidates;
use crate::validity::physical_validity;
use crate::{SearchError, SearchErrorCode, SEARCH_RECEIPT_SCHEMA_ID};

const CUSTOM_EVALUATOR_ID: &str = "betelgeuze.caller_supplied_energy_force_evaluator/1";
const SHORT_RANGE_EVALUATOR_ID: &str = "betelgeuze_short_range_analytic/1.0.0";

/// Execute the full pipeline with a caller-supplied product-owned evaluator.
pub fn search<E: EnergyForceEvaluator>(
    input: &SearchInput,
    config: &SearchConfig,
    evaluator: &mut E,
) -> Result<SearchResult, SearchError> {
    search_with_evaluator_identity(input, config, evaluator, CUSTOM_EVALUATOR_ID, [0; 32])
}

/// Execute the product path with the built-in deterministic short-range model.
pub fn search_short_range(
    input: &SearchInput,
    config: &SearchConfig,
    short_range_config: ShortRangeConfig,
) -> Result<SearchResult, SearchError> {
    let evaluator_config_sha256 = short_range_config.canonical_sha256();
    let mut evaluator = ShortRangeEvaluator::from_input(input, short_range_config)?;
    search_with_evaluator_identity(
        input,
        config,
        &mut evaluator,
        SHORT_RANGE_EVALUATOR_ID,
        evaluator_config_sha256,
    )
}

/// Execute the default product path with frozen built-in short-range defaults.
pub fn search_default(
    input: &SearchInput,
    config: &SearchConfig,
) -> Result<SearchResult, SearchError> {
    search_short_range(input, config, ShortRangeConfig::default())
}

fn search_with_evaluator_identity<E: EnergyForceEvaluator>(
    input: &SearchInput,
    config: &SearchConfig,
    evaluator: &mut E,
    evaluator_id: &'static str,
    evaluator_config_sha256: [u8; 32],
) -> Result<SearchResult, SearchError> {
    validate_config(config)?;
    validate_input(input, config)?;

    let orientation_values = orientations(input.source_seed, config.orientation_count)?;
    let combination_set = compatible_combinations(input, config)?;
    let possible_candidate_slot_count = u64::try_from(orientation_values.len())
        .ok()
        .and_then(|orientation_count| {
            u64::try_from(combination_set.combinations.len())
                .ok()
                .and_then(|combination_count| orientation_count.checked_mul(combination_count))
        })
        .ok_or_else(|| {
            SearchError::new(
                SearchErrorCode::AllocationOverflow,
                "possible candidate slot count overflowed",
            )
        })?;
    let prospective_allocated_count = usize::try_from(possible_candidate_slot_count)
        .unwrap_or(usize::MAX)
        .min(config.generated_candidate_limit);
    validate_composite_budget(input, config, prospective_allocated_count)?;
    let mut candidates = place_candidates(
        input,
        config,
        &orientation_values,
        &combination_set.combinations,
        combination_set.placement_mode,
    )?;
    let allocated_candidate_slot_count = candidates.len();
    let used_anchor_combination_count = candidates
        .iter()
        .map(|candidate| {
            (
                candidate.key.primary_surface_id,
                candidate.key.primary_ligand_anchor_id,
                candidate.key.secondary_surface_id,
                candidate.key.secondary_ligand_anchor_id,
            )
        })
        .collect::<BTreeSet<_>>()
        .len();
    let allocation_identity = allocation_sha256(&candidates);
    let orientation_identity = orientation_sha256(&orientation_values);
    let mut metadata = vec![CandidateMetadata::default(); candidates.len()];

    let coarse_indices = coarse_select(&mut candidates, input, config);
    let coarse_kept_count = coarse_indices.len();
    let mut coarse_mask = vec![false; candidates.len()];
    for &index in &coarse_indices {
        coarse_mask[index] = true;
    }
    for (index, entry) in metadata.iter_mut().enumerate() {
        if !coarse_mask[index] {
            entry.status = Some(CandidateStatus::CoarsePruned);
            entry.reason = Some(CandidateReason::CoarseBudget);
        }
    }

    let refinement_indices = detailed_select(&mut candidates, &coarse_indices, input, config);
    let refinement_selected_count = refinement_indices.len();
    let mut refinement_mask = vec![false; candidates.len()];
    for &index in &refinement_indices {
        refinement_mask[index] = true;
    }
    for &index in &coarse_indices {
        if !refinement_mask[index] {
            metadata[index].status = Some(CandidateStatus::DetailedPruned);
            metadata[index].reason = Some(CandidateReason::DetailedBudget);
        }
    }

    let mut evaluator_call_count = 0usize;
    let mut evaluator_failed_count = 0usize;
    let mut non_finite_failed_count = 0usize;
    let mut refinement_succeeded_indices = Vec::with_capacity(refinement_indices.len());
    for &index in &refinement_indices {
        let outcome = refine_candidate(&mut candidates[index], config, evaluator);
        evaluator_call_count = evaluator_call_count
            .checked_add(outcome.evaluator_calls)
            .ok_or_else(|| {
                SearchError::new(
                    SearchErrorCode::AllocationOverflow,
                    "evaluator call count overflowed",
                )
            })?;
        if let Some(error) = outcome.error {
            metadata[index].status = Some(CandidateStatus::RefinementFailed);
            metadata[index].detail = Some(bounded_evaluation_detail(error.detail()));
            if error.code() == SearchErrorCode::Evaluator {
                evaluator_failed_count += 1;
                metadata[index].reason = Some(CandidateReason::EvaluatorFailure);
            } else {
                non_finite_failed_count += 1;
                metadata[index].reason = Some(CandidateReason::NonFiniteEvaluation);
            }
        } else {
            refinement_succeeded_indices.push(index);
        }
    }

    let mut valid_indices = Vec::with_capacity(refinement_succeeded_indices.len());
    let mut rejected_non_finite = 0usize;
    let mut rejected_out_of_bounds = 0usize;
    let mut rejected_self_overlap = 0usize;
    let mut rejected_receptor_clash = 0usize;
    for index in refinement_succeeded_indices.iter().copied() {
        match physical_validity(&candidates[index], input, config) {
            Ok(minimum_gap) => {
                candidates[index].minimum_receptor_gap_angstrom = minimum_gap;
                metadata[index].physically_valid = Some(true);
                valid_indices.push(index);
            }
            Err(reason) => {
                metadata[index].status = Some(CandidateStatus::PhysicalRejected);
                metadata[index].reason = Some(reason);
                metadata[index].physically_valid = Some(false);
                match reason {
                    CandidateReason::NonFiniteCoordinate => rejected_non_finite += 1,
                    CandidateReason::CoordinateOutOfBounds => rejected_out_of_bounds += 1,
                    CandidateReason::LigandSelfOverlap => rejected_self_overlap += 1,
                    CandidateReason::ReceptorClash => rejected_receptor_clash += 1,
                    _ => {
                        return Err(SearchError::new(
                            SearchErrorCode::InternalInvariant,
                            "physical validity returned a non-physical reason",
                        ));
                    }
                }
            }
        }
    }

    let cluster_outcome = cluster_and_top_k(
        &candidates,
        &valid_indices,
        config.cluster_rmsd_angstrom,
        config.top_k,
    );
    for assignment in &cluster_outcome.assignments {
        let entry = &mut metadata[assignment.candidate_index];
        entry.cluster_id = Some(assignment.cluster_id);
        entry.final_rank = assignment.final_rank;
        if let Some(rank) = assignment.final_rank {
            entry.status = Some(CandidateStatus::TopK);
            entry.reason = None;
            entry.final_rank = Some(rank);
        } else if assignment.representative {
            entry.status = Some(CandidateStatus::ClusterRepresentative);
            entry.reason = Some(CandidateReason::TopKBudget);
        } else {
            entry.status = Some(CandidateStatus::ClusterMember);
            entry.reason = Some(CandidateReason::ClusteredIntoRepresentative);
        }
    }

    let mut candidate_rows = Vec::with_capacity(candidates.len());
    for (candidate, metadata) in candidates.into_iter().zip(metadata) {
        let status = metadata.status.ok_or_else(|| {
            SearchError::new(
                SearchErrorCode::InternalInvariant,
                format!(
                    "candidate slot {} has no terminal ledger status",
                    candidate.slot_index
                ),
            )
        })?;
        candidate_rows.push(CandidateRow {
            slot_index: candidate.slot_index,
            key: candidate.key,
            placement_mode: candidate.placement_mode,
            status,
            reason: metadata.reason,
            detail: metadata.detail,
            coordinates_angstrom: candidate.coordinates_angstrom,
            anchor_fit_rmsd_angstrom: candidate.anchor_fit_rmsd_angstrom,
            coarse_score: candidate
                .coarse_score
                .is_finite()
                .then_some(candidate.coarse_score),
            detailed_score: candidate
                .detailed_score
                .is_finite()
                .then_some(candidate.detailed_score),
            energy_kcal_per_mol: candidate
                .energy_kcal_per_mol
                .is_finite()
                .then_some(candidate.energy_kcal_per_mol),
            physically_valid: metadata.physically_valid,
            minimum_receptor_gap_angstrom: candidate.minimum_receptor_gap_angstrom,
            cluster_id: metadata.cluster_id,
            final_rank: metadata.final_rank,
        });
    }
    if candidate_rows
        .iter()
        .enumerate()
        .any(|(index, row)| row.slot_index != index)
    {
        return Err(SearchError::new(
            SearchErrorCode::InternalInvariant,
            "candidate ledger slot indices are not contiguous",
        ));
    }
    let candidate_rows_identity = candidate_rows_sha256(&candidate_rows);
    let poses_identity = poses_sha256(&cluster_outcome.poses);
    let maximum_evaluator_call_count = refinement_selected_count
        .checked_mul(config.refinement_steps + 1)
        .ok_or_else(|| {
            SearchError::new(
                SearchErrorCode::AllocationOverflow,
                "maximum evaluator call count overflowed",
            )
        })?;
    let mut receipt = SearchReceipt {
        schema_id: SEARCH_RECEIPT_SCHEMA_ID,
        evaluator_id,
        evaluator_config_sha256,
        config_sha256: config.canonical_sha256(),
        input_sha256: input_sha256(input),
        result_independent_allocation: true,
        placement_mode: combination_set.placement_mode,
        requested_orientation_count: config.orientation_count,
        accepted_orientation_count: orientation_values.len(),
        raw_orientation_attempt_count: orientation_values
            .last()
            .map_or(0, |orientation| orientation.raw_sequence_index + 1),
        compatible_single_anchor_pair_count: combination_set.compatible_single_pair_count,
        compatible_dual_anchor_combination_count: combination_set.compatible_dual_combination_count,
        used_anchor_combination_count,
        possible_candidate_slot_count,
        generated_candidate_limit: config.generated_candidate_limit,
        allocated_candidate_slot_count,
        allocation_sha256: allocation_identity,
        orientation_sha256: orientation_identity,
        candidate_rows_sha256: candidate_rows_identity,
        poses_sha256: poses_identity,
        coarse_keep_budget: config.coarse_keep,
        coarse_kept_count,
        refinement_keep_budget: config.refinement_keep,
        refinement_selected_count,
        refinement_steps_per_candidate: config.refinement_steps,
        refinement_succeeded_count: refinement_succeeded_indices.len(),
        refinement_evaluator_failed_count: evaluator_failed_count,
        refinement_non_finite_failed_count: non_finite_failed_count,
        evaluator_call_count,
        maximum_evaluator_call_count,
        physical_valid_count: valid_indices.len(),
        rejected_non_finite_coordinate_count: rejected_non_finite,
        rejected_coordinate_out_of_bounds_count: rejected_out_of_bounds,
        rejected_ligand_self_overlap_count: rejected_self_overlap,
        rejected_receptor_clash_count: rejected_receptor_clash,
        cluster_count: cluster_outcome.cluster_count,
        top_k_budget: config.top_k,
        returned_pose_count: cluster_outcome.poses.len(),
        receipt_sha256: [0; 32],
    };
    receipt.seal();
    receipt.validate()?;
    Ok(SearchResult {
        candidate_rows,
        poses: cluster_outcome.poses,
        receipt,
    })
}

#[derive(Clone, Debug, Default)]
struct CandidateMetadata {
    status: Option<CandidateStatus>,
    reason: Option<CandidateReason>,
    detail: Option<String>,
    physically_valid: Option<bool>,
    cluster_id: Option<usize>,
    final_rank: Option<usize>,
}

fn validate_config(config: &SearchConfig) -> Result<(), SearchError> {
    if config.orientation_count == 0 || config.orientation_count > MAX_ORIENTATIONS {
        return invalid_config("orientation_count is outside its bounded range");
    }
    if config.generated_candidate_limit == 0
        || config.generated_candidate_limit > MAX_GENERATED_CANDIDATES
    {
        return invalid_config("generated_candidate_limit is outside its bounded range");
    }
    if config.coarse_keep == 0 || config.coarse_keep > config.generated_candidate_limit {
        return invalid_config("coarse_keep must be within the generated candidate budget");
    }
    if config.refinement_keep == 0 || config.refinement_keep > config.coarse_keep {
        return invalid_config("refinement_keep must be within the coarse budget");
    }
    if config.top_k == 0 || config.top_k > config.refinement_keep || config.top_k > MAX_TOP_K {
        return invalid_config("top_k must be within the refinement budget and hard cap");
    }
    if config.refinement_steps > MAX_REFINEMENT_STEPS {
        return invalid_config("refinement_steps exceeds its hard cap");
    }
    validate_nonnegative_finite(
        config.placement_clearance_angstrom,
        "placement_clearance_angstrom",
    )?;
    if config.placement_clearance_angstrom > 10_000.0 {
        return invalid_config("placement_clearance_angstrom exceeds 10000");
    }
    if !config.dual_anchor_distance_tolerance_angstrom.is_finite()
        || !(1.0e-6..=10.0).contains(&config.dual_anchor_distance_tolerance_angstrom)
    {
        return invalid_config("dual_anchor_distance_tolerance_angstrom must be within [1e-6, 10]");
    }
    validate_nonnegative_finite(config.coarse_clash_weight, "coarse_clash_weight")?;
    if config.coarse_clash_weight > 1.0e12 {
        return invalid_config("coarse_clash_weight exceeds 1e12");
    }
    validate_nonnegative_finite(
        config.translation_step_angstrom2_per_kcal,
        "translation_step_angstrom2_per_kcal",
    )?;
    validate_nonnegative_finite(config.rotation_step_per_torque, "rotation_step_per_torque")?;
    if config.translation_step_angstrom2_per_kcal > 1.0e6 || config.rotation_step_per_torque > 1.0e6
    {
        return invalid_config("local refinement coefficients exceed 1e6");
    }
    for (value, label) in [
        (
            config.maximum_translation_step_angstrom,
            "maximum_translation_step_angstrom",
        ),
        (
            config.maximum_rotation_step_radians,
            "maximum_rotation_step_radians",
        ),
        (
            config.maximum_absolute_coordinate_angstrom,
            "maximum_absolute_coordinate_angstrom",
        ),
        (
            config.minimum_ligand_atom_distance_angstrom,
            "minimum_ligand_atom_distance_angstrom",
        ),
        (config.cluster_rmsd_angstrom, "cluster_rmsd_angstrom"),
    ] {
        if !value.is_finite() || value <= 0.0 {
            return invalid_config(&format!("{label} must be finite and positive"));
        }
    }
    if config.maximum_translation_step_angstrom > 10_000.0
        || config.maximum_rotation_step_radians > core::f64::consts::PI
        || config.maximum_absolute_coordinate_angstrom > 1.0e9
        || config.minimum_ligand_atom_distance_angstrom > 100.0
        || config.cluster_rmsd_angstrom > 10_000.0
    {
        return invalid_config("one or more numeric configuration values exceed hard limits");
    }
    if !config.minimum_receptor_clearance_scale.is_finite()
        || !(0.0..=1.0).contains(&config.minimum_receptor_clearance_scale)
        || config.minimum_receptor_clearance_scale == 0.0
    {
        return invalid_config("minimum_receptor_clearance_scale must be within (0, 1]");
    }
    Ok(())
}

pub(crate) fn validate_input(
    input: &SearchInput,
    config: &SearchConfig,
) -> Result<(), SearchError> {
    if input.ligand_atoms.is_empty() {
        return Err(SearchError::new(
            SearchErrorCode::EmptyLigand,
            "ligand must contain at least one atom",
        ));
    }
    if input.ligand_atoms.len() > MAX_LIGAND_ATOMS {
        return too_many("ligand atoms", MAX_LIGAND_ATOMS);
    }
    if input.ligand_anchors.is_empty() {
        return Err(SearchError::new(
            SearchErrorCode::MissingLigandAnchor,
            "ligand must contain at least one typed anchor",
        ));
    }
    if input.ligand_anchors.len() > MAX_LIGAND_ANCHORS {
        return too_many("ligand anchors", MAX_LIGAND_ANCHORS);
    }
    if input.receptor_atoms.len() > MAX_RECEPTOR_ATOMS {
        return too_many("receptor atoms", MAX_RECEPTOR_ATOMS);
    }
    if input.surface_samples.is_empty() {
        return Err(SearchError::new(
            SearchErrorCode::EmptySurface,
            "receptor must contain at least one surface sample",
        ));
    }
    if input.surface_samples.len() > MAX_SURFACE_SAMPLES {
        return too_many("surface samples", MAX_SURFACE_SAMPLES);
    }
    for (index, atom) in input.ligand_atoms.iter().enumerate() {
        validate_position(
            atom.position_angstrom,
            &format!("ligand atom {index}"),
            config.maximum_absolute_coordinate_angstrom,
        )?;
        validate_radius(atom.vdw_radius_angstrom, &format!("ligand atom {index}"))?;
        validate_atom_parameters(
            atom.epsilon_kcal_per_mol,
            atom.charge_elementary,
            &format!("ligand atom {index}"),
        )?;
    }
    for (index, atom) in input.receptor_atoms.iter().enumerate() {
        validate_position(
            atom.position_angstrom,
            &format!("receptor atom {index}"),
            config.maximum_absolute_coordinate_angstrom,
        )?;
        validate_radius(atom.vdw_radius_angstrom, &format!("receptor atom {index}"))?;
        validate_atom_parameters(
            atom.epsilon_kcal_per_mol,
            atom.charge_elementary,
            &format!("receptor atom {index}"),
        )?;
    }
    let mut anchor_ids = BTreeSet::new();
    for (index, anchor) in input.ligand_anchors.iter().enumerate() {
        if anchor.atom_index >= input.ligand_atoms.len() {
            return Err(SearchError::new(
                SearchErrorCode::AtomIndexOutOfRange,
                format!("ligand anchor {index} atom index is out of range"),
            ));
        }
        anchor.direction.normalized("ligand anchor direction")?;
        if !anchor_ids.insert(anchor.id) {
            return Err(SearchError::new(
                SearchErrorCode::DuplicateIdentifier,
                format!("ligand anchor id {} is duplicated", anchor.id.0),
            ));
        }
    }
    let mut surface_ids = BTreeSet::new();
    for (index, surface) in input.surface_samples.iter().enumerate() {
        validate_position(
            surface.position_angstrom,
            &format!("surface sample {index}"),
            config.maximum_absolute_coordinate_angstrom,
        )?;
        surface
            .outward_normal
            .normalized("surface outward normal")?;
        if !surface_ids.insert(surface.id) {
            return Err(SearchError::new(
                SearchErrorCode::DuplicateIdentifier,
                format!("surface id {} is duplicated", surface.id.0),
            ));
        }
    }
    Ok(())
}

fn validate_composite_budget(
    input: &SearchInput,
    config: &SearchConfig,
    allocated_candidate_count: usize,
) -> Result<(), SearchError> {
    let ligand_count = input.ligand_atoms.len();
    let receptor_count = input.receptor_atoms.len();
    let candidate_coordinates = checked_product(&[allocated_candidate_count, ligand_count])?;
    if candidate_coordinates > MAX_CANDIDATE_COORDINATES {
        return Err(SearchError::new(
            SearchErrorCode::CompositeWorkLimit,
            format!(
                "candidate coordinate count {candidate_coordinates} exceeds {MAX_CANDIDATE_COORDINATES}"
            ),
        ));
    }
    let coarse_count = config.coarse_keep.min(allocated_candidate_count);
    let refinement_count = config.refinement_keep.min(coarse_count);
    let coordinate_bytes = checked_product(&[candidate_coordinates, size_of::<crate::Vec3>()])?;
    let row_metadata_bytes = checked_product(&[allocated_candidate_count, 256])?;
    let maximum_detail_bytes = checked_product(&[refinement_count, MAX_EVALUATION_DETAIL_BYTES])?;
    let maximum_pose_bytes = checked_product(&[
        config.top_k.min(refinement_count),
        ligand_count,
        size_of::<crate::Vec3>(),
    ])?;
    let ledger_payload_bytes = coordinate_bytes
        .checked_add(row_metadata_bytes)
        .and_then(|value| value.checked_add(maximum_detail_bytes))
        .and_then(|value| value.checked_add(maximum_pose_bytes))
        .ok_or_else(allocation_overflow)?;
    if ledger_payload_bytes > MAX_LEDGER_PAYLOAD_BYTES {
        return Err(SearchError::new(
            SearchErrorCode::CompositeWorkLimit,
            format!(
                "conservative ledger payload {ledger_payload_bytes} bytes exceeds {MAX_LEDGER_PAYLOAD_BYTES}"
            ),
        ));
    }
    let ligand_receptor_pairs = checked_product(&[ligand_count, receptor_count])?;
    let ligand_shape_pairs = checked_product(&[ligand_count, ligand_count.saturating_sub(1)])? / 2;
    let evaluator_pairs_per_call = ligand_receptor_pairs
        .checked_add(ligand_shape_pairs)
        .ok_or_else(allocation_overflow)?;
    let evaluator_calls = checked_product(&[refinement_count, config.refinement_steps + 1])?;
    let work_rows = [
        candidate_coordinates,
        checked_product(&[allocated_candidate_count, receptor_count])?,
        checked_product(&[coarse_count, ligand_receptor_pairs])?,
        checked_product(&[refinement_count, ligand_receptor_pairs])?,
        checked_product(&[refinement_count, ligand_shape_pairs])?,
        checked_product(&[evaluator_calls, evaluator_pairs_per_call])?,
    ];
    let total_pair_evaluations = work_rows.into_iter().try_fold(0usize, |total, value| {
        total.checked_add(value).ok_or_else(allocation_overflow)
    })?;
    if total_pair_evaluations > MAX_PAIR_EVALUATIONS {
        return Err(SearchError::new(
            SearchErrorCode::CompositeWorkLimit,
            format!(
                "conservative pair-evaluation budget {total_pair_evaluations} exceeds {MAX_PAIR_EVALUATIONS}"
            ),
        ));
    }
    Ok(())
}

fn checked_product(values: &[usize]) -> Result<usize, SearchError> {
    values.iter().try_fold(1usize, |product, value| {
        product.checked_mul(*value).ok_or_else(allocation_overflow)
    })
}

fn allocation_overflow() -> SearchError {
    SearchError::new(
        SearchErrorCode::AllocationOverflow,
        "composite search work calculation overflowed",
    )
}

fn bounded_evaluation_detail(detail: &str) -> String {
    if detail.len() <= MAX_EVALUATION_DETAIL_BYTES {
        return detail.to_owned();
    }
    let mut end = MAX_EVALUATION_DETAIL_BYTES;
    while !detail.is_char_boundary(end) {
        end -= 1;
    }
    detail[..end].to_owned()
}

fn validate_position(
    position: crate::Vec3,
    label: &str,
    maximum_absolute_coordinate: f64,
) -> Result<(), SearchError> {
    if !position.is_finite() {
        return Err(SearchError::new(
            SearchErrorCode::NonFiniteInput,
            format!("{label} position must contain only finite coordinates"),
        ));
    }
    if position.x.abs() > maximum_absolute_coordinate
        || position.y.abs() > maximum_absolute_coordinate
        || position.z.abs() > maximum_absolute_coordinate
    {
        return Err(SearchError::new(
            SearchErrorCode::NonFiniteInput,
            format!("{label} position exceeds maximum_absolute_coordinate_angstrom"),
        ));
    }
    Ok(())
}

fn validate_radius(radius: f64, label: &str) -> Result<(), SearchError> {
    if radius.is_finite() && (0.0..=100.0).contains(&radius) && radius != 0.0 {
        Ok(())
    } else {
        Err(SearchError::new(
            SearchErrorCode::InvalidRadius,
            format!("{label} radius must be finite and within (0, 100] angstrom"),
        ))
    }
}

fn validate_atom_parameters(
    epsilon_kcal_per_mol: f64,
    charge_elementary: f64,
    label: &str,
) -> Result<(), SearchError> {
    if !epsilon_kcal_per_mol.is_finite()
        || !(0.0..=1_000.0).contains(&epsilon_kcal_per_mol)
        || !charge_elementary.is_finite()
        || !(-16.0..=16.0).contains(&charge_elementary)
    {
        return Err(SearchError::new(
            SearchErrorCode::InvalidAtomParameter,
            format!(
                "{label} epsilon must be within [0, 1000] kcal/mol and charge within [-16, 16] e"
            ),
        ));
    }
    Ok(())
}

fn validate_nonnegative_finite(value: f64, label: &str) -> Result<(), SearchError> {
    if value.is_finite() && value >= 0.0 {
        Ok(())
    } else {
        invalid_config(&format!("{label} must be finite and non-negative"))
    }
}

fn invalid_config<T>(detail: &str) -> Result<T, SearchError> {
    Err(SearchError::new(
        SearchErrorCode::InvalidConfiguration,
        detail,
    ))
}

fn too_many<T>(label: &str, maximum: usize) -> Result<T, SearchError> {
    Err(SearchError::new(
        SearchErrorCode::TooManyItems,
        format!("{label} exceed the cap of {maximum}"),
    ))
}
