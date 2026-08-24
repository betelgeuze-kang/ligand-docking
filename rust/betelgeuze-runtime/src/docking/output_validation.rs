//! Independent validation of the complete native fixed64 output graph.

use super::*;

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_native_outputs(
    backend: Backend,
    expected_receipt_graph: &ExpectedPipelineReceiptGraph,
    expected_allocation: &IndependentFixed64Allocation,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    coordinate_count: u64,
    producer: &sys::bg_docking_fixed64_producer_output_v1,
    rigid: &sys::bg_docking_rigid_refinement_output_v1,
    torsion: &sys::bg_docking_torsion_v7_output_v1,
    scorer: &sys::bg_docking_scorer_v1_output_v1,
    validity: &sys::bg_docking_pose_validity_output_v1,
    ranking: &sys::bg_docking_stable_top_k_output_v1,
    cluster: &sys::bg_docking_rmsd_cluster_output_v1,
    refinement: &sys::bg_docking_fixed64_refinement_output_v1,
    post_admission: &sys::bg_docking_geometric_admission_output_v1,
    pipeline: &sys::bg_docking_fixed64_pipeline_output_v2,
    producer_rows: &[sys::bg_docking_fixed64_producer_row_v1],
    expected_sources: &[Option<Fixed64CoordinateSource<'_>>],
    expected_feature_geometry_inventory: Option<&IndependentFixed64FeatureGeometryInventory>,
    native_placement_replays: &[Option<NativePlacementReplay>],
    canonical_pocket_normal: [f64; 3],
    rigid_rows: &[sys::bg_docking_rigid_refinement_row_v1],
    torsion_rows: &[sys::bg_docking_torsion_v7_row_v1],
    torsion_moves: &[sys::bg_docking_torsion_v7_move_v1],
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    cluster_rows: &[sys::bg_docking_rmsd_cluster_row_v1],
    refinement_rows: &[sys::bg_docking_fixed64_refinement_row_v1],
    post_admission_rows: &[sys::bg_docking_geometric_admission_row_v1],
    pipeline_rows: &[sys::bg_docking_fixed64_pipeline_row_v2],
    primary_indices: &[u32],
    valid_indices: &[u32],
    representative_indices: &[u32],
    top_k_indices: &[u32],
    requested_modes: &[sys::bg_docking_rigid_refinement_candidate_mode],
    rigid_max_steps: &[u64],
    producer_coordinates: [&[f64]; 3],
    rigid_coordinates: &[Vec<f64>; 12],
    torsion_coordinates: &[Vec<f64>; 8],
    final_coordinates: [&[f64]; 3],
    final_quaternions: [&[f64]; 4],
    rmsd_threshold_angstrom: f64,
    ligand_heavy_atom_count: u64,
    geometric_hard_rejection_minimum_vdw_ratio: f64,
    geometric_input: &IndependentFixed64GeometricInput,
    rigid_v2_config: IndependentRigidV2Config,
    rigid_v3_config: IndependentRigidV3Config,
    rigid_clearance_config: IndependentRigidV3Config,
    maximum_torsion_steps: u64,
    proposal_is_torsion_eligible: &[u8],
    torsion_max_steps: &[u64],
    baseline_torsion_angles_radians: &[f64],
    rotatable_child_atom_indices: &[u64],
    validity_exclusion_count: u64,
    validity_chirality_count: u64,
    validity_contact_cell_size_angstrom: f64,
    validity_receptor_cells: &HashMap<(i64, i64, i64), u64>,
    independent_scorer_context: &IndependentScorerContext,
    independent_validity_context: &IndependentValidityContext,
) -> Result<()> {
    let candidate_count = u64::from(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT);
    let move_count = candidate_count * u64::from(sys::BG_DOCKING_TORSION_V7_MAX_MOVES);
    let top_k_limit = u64::from(sys::BG_DOCKING_STABLE_TOP_K_LIMIT);
    for (observed, expected, label) in [
        (
            producer.row_capacity,
            candidate_count,
            "producer row capacity",
        ),
        (
            producer.coordinate_capacity,
            coordinate_count,
            "producer coordinate capacity",
        ),
        (rigid.row_capacity, candidate_count, "rigid row capacity"),
        (
            rigid.coordinate_capacity,
            coordinate_count,
            "rigid coordinate capacity",
        ),
        (
            torsion.row_capacity,
            candidate_count,
            "torsion row capacity",
        ),
        (torsion.move_capacity, move_count, "torsion move capacity"),
        (
            torsion.coordinate_capacity,
            coordinate_count,
            "torsion coordinate capacity",
        ),
        (scorer.row_capacity, candidate_count, "scorer row capacity"),
        (
            validity.row_capacity,
            candidate_count,
            "validity row capacity",
        ),
        (
            ranking.row_capacity,
            candidate_count,
            "ranking row capacity",
        ),
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
        (
            refinement.row_capacity,
            candidate_count,
            "refinement row capacity",
        ),
        (
            refinement.coordinate_capacity,
            coordinate_count,
            "refinement coordinate capacity",
        ),
        (
            refinement.quaternion_capacity,
            candidate_count,
            "refinement quaternion capacity",
        ),
        (
            post_admission.row_capacity,
            candidate_count,
            "post-admission row capacity",
        ),
        (
            pipeline.row_capacity,
            candidate_count,
            "pipeline row capacity",
        ),
    ] {
        if observed != expected {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} is {observed}, expected {expected}"),
            ));
        }
    }
    for (observed, expected, label) in [
        (producer.row_count, candidate_count, "producer row count"),
        (
            producer.coordinate_count,
            coordinate_count,
            "producer coordinate count",
        ),
        (rigid.row_count, candidate_count, "rigid row count"),
        (
            rigid.coordinate_count,
            coordinate_count,
            "rigid coordinate count",
        ),
        (torsion.row_count, candidate_count, "torsion row count"),
        (torsion.move_count, move_count, "torsion move count"),
        (
            torsion.coordinate_count,
            coordinate_count,
            "torsion coordinate count",
        ),
        (scorer.row_count, candidate_count, "scorer row count"),
        (validity.row_count, candidate_count, "validity row count"),
        (ranking.row_count, candidate_count, "ranking row count"),
        (cluster.row_count, candidate_count, "cluster row count"),
        (
            refinement.row_count,
            candidate_count,
            "refinement row count",
        ),
        (
            refinement.coordinate_count,
            coordinate_count,
            "refinement coordinate count",
        ),
        (
            refinement.quaternion_count,
            candidate_count,
            "refinement quaternion count",
        ),
        (
            post_admission.row_count,
            candidate_count,
            "post-admission row count",
        ),
        (pipeline.row_count, candidate_count, "pipeline row count"),
    ] {
        if observed != expected {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} is {observed}, expected {expected}"),
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
                format!("native fixed64 {label} exceeds its capacity"),
            ));
        }
    }
    let generated_row_count = producer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED)
        .count() as u64;
    let typed_failure_row_count = producer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE)
        .count() as u64;
    let initial_admitted_row_count = producer_rows
        .iter()
        .filter(|row| {
            row.geometric_admission.decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
        })
        .count() as u64;
    let refined_row_count = refinement_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY)
        .count() as u64;
    let post_admitted_row_count = post_admission_rows
        .iter()
        .filter(|row| {
            row.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
                && row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                && row.rank_eligible == 1
        })
        .count() as u64;
    let post_rejected_row_count = refinement_rows
        .iter()
        .zip(post_admission_rows)
        .filter(|(refinement, post)| {
            refinement.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY
                && !(post.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
                    && post.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                    && post.rank_eligible == 1)
        })
        .count() as u64;
    let scored_row_count = scorer_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED)
        .count() as u64;
    let valid_row_count = validity_rows
        .iter()
        .filter(|row| {
            row.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
                && row.passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
                && row.blocker_mask == 0
        })
        .count() as u64;
    for (valid, label) in [
        (
            producer.source_bundle_receipt_sha256
                == expected_receipt_graph.source_bundle_receipt_sha256,
            "producer source-bundle receipt",
        ),
        (
            pipeline.source_bundle_receipt_sha256
                == expected_receipt_graph.source_bundle_receipt_sha256,
            "pipeline source-bundle receipt",
        ),
        (
            producer.generated_count == generated_row_count,
            "producer generated count",
        ),
        (
            producer.typed_failure_count == typed_failure_row_count,
            "producer typed-failure count",
        ),
        (
            pipeline.initial_admitted_count == initial_admitted_row_count,
            "pipeline initial-admitted count",
        ),
        (
            pipeline.refined_count == refined_row_count,
            "pipeline refined count",
        ),
        (
            pipeline.post_admitted_count == post_admitted_row_count,
            "pipeline post-admitted count",
        ),
        (
            pipeline.post_rejected_count == post_rejected_row_count,
            "pipeline post-rejected count",
        ),
        (
            pipeline.scored_count == scored_row_count,
            "pipeline scored count",
        ),
        (
            pipeline.valid_count == valid_row_count,
            "pipeline valid count",
        ),
    ] {
        if !valid {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} was not independently rederived"),
            ));
        }
    }
    let unit_systems_match = [
        producer.unit_system,
        rigid.unit_system,
        torsion.unit_system,
        scorer.unit_system,
        validity.unit_system,
        ranking.unit_system,
        cluster.unit_system,
        refinement.unit_system,
        post_admission.unit_system,
        pipeline.unit_system,
    ]
    .iter()
    .all(|unit| *unit == sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    for (valid, label) in [
        (
            requested_modes.len() == candidate_count as usize,
            "requested-mode denominator",
        ),
        (
            rigid_max_steps.len() == candidate_count as usize,
            "rigid-step denominator",
        ),
        (pipeline.backend == backend.as_raw(), "pipeline backend"),
        (producer.backend == backend.as_raw(), "producer backend"),
        (unit_systems_match, "unit systems"),
        (
            producer
                .generated_count
                .checked_add(producer.typed_failure_count)
                == Some(candidate_count),
            "producer denominator",
        ),
        (
            pipeline.generated_count == producer.generated_count,
            "producer/pipeline generated count",
        ),
        (
            pipeline.allocation_receipt_sha256 == producer.allocation_receipt_sha256,
            "producer/pipeline allocation receipt",
        ),
        (
            pipeline.source_bundle_receipt_sha256 == producer.source_bundle_receipt_sha256,
            "producer/pipeline source-bundle receipt",
        ),
        (
            pipeline.producer_batch_receipt_sha256 == producer.producer_batch_receipt_sha256,
            "producer/pipeline batch receipt",
        ),
        (
            producer.allocation_inventory_sha256
                == expected_receipt_graph.allocation_inventory_sha256,
            "producer allocation inventory",
        ),
        (
            producer.allocation_receipt_sha256 == expected_receipt_graph.allocation_receipt_sha256,
            "producer allocation receipt",
        ),
        (
            producer.source_bundle_receipt_sha256
                == expected_receipt_graph.source_bundle_receipt_sha256,
            "producer source-bundle receipt",
        ),
        (
            pipeline.allocation_receipt_sha256 == expected_receipt_graph.allocation_receipt_sha256,
            "pipeline allocation receipt",
        ),
        (
            pipeline.source_bundle_receipt_sha256
                == expected_receipt_graph.source_bundle_receipt_sha256,
            "pipeline source-bundle receipt",
        ),
        (
            pipeline.admission_context_receipt_sha256
                == expected_receipt_graph.admission_context_receipt_sha256,
            "pipeline admission-context receipt",
        ),
        (
            pipeline.refinement_context_receipt_sha256
                == expected_receipt_graph.refinement_context_receipt_sha256,
            "pipeline refinement-context receipt",
        ),
        (
            pipeline.scorer_context_receipt_sha256
                == expected_receipt_graph.scorer_context_receipt_sha256,
            "pipeline scorer-context receipt",
        ),
        (
            pipeline.validity_context_receipt_sha256
                == expected_receipt_graph.validity_context_receipt_sha256,
            "pipeline validity-context receipt",
        ),
        (
            pipeline.component_binding_receipt_sha256
                == expected_receipt_graph.component_binding_receipt_sha256,
            "pipeline component-binding receipt",
        ),
        (
            pipeline.refinement_policy_receipt_sha256
                == expected_receipt_graph.refinement_policy_receipt_sha256,
            "pipeline refinement-policy receipt",
        ),
        (
            pipeline.post_admission_policy_receipt_sha256
                == expected_receipt_graph.post_admission_policy_receipt_sha256,
            "pipeline post-admission-policy receipt",
        ),
        (
            pipeline.post_admission_batch_receipt_sha256 == post_admission.batch_receipt_sha256,
            "pipeline post-admission batch receipt",
        ),
        (
            producer.generated_count == generated_row_count,
            "producer generated-row count",
        ),
        (
            producer.typed_failure_count == typed_failure_row_count,
            "producer typed-failure-row count",
        ),
        (
            pipeline.generated_count == generated_row_count,
            "pipeline generated-row count",
        ),
        (
            pipeline.initial_admitted_count == initial_admitted_row_count,
            "pipeline initial-admitted-row count",
        ),
        (
            pipeline.refined_count == refined_row_count,
            "pipeline refined-row count",
        ),
        (
            pipeline.post_admitted_count == post_admitted_row_count,
            "pipeline post-admitted-row count",
        ),
        (
            pipeline.post_rejected_count == post_rejected_row_count,
            "pipeline post-rejected-row count",
        ),
        (
            pipeline.scored_count == scored_row_count,
            "pipeline scored-row count",
        ),
        (
            pipeline.valid_count == valid_row_count,
            "pipeline valid-row count",
        ),
        (
            ranking.primary_index_count == pipeline.scored_count,
            "ranking/scored count",
        ),
        (
            ranking.valid_index_count == pipeline.valid_count,
            "ranking/valid count",
        ),
        (
            cluster.representative_index_count == pipeline.cluster_count,
            "cluster representative count",
        ),
        (
            cluster.top_k_index_count == pipeline.cluster_count.min(top_k_limit),
            "cluster Top-K count",
        ),
        (
            pipeline.initial_admitted_count <= pipeline.generated_count,
            "initial-admitted/generated monotonicity",
        ),
        (
            pipeline.refined_count <= pipeline.initial_admitted_count,
            "refined/initial-admitted monotonicity",
        ),
        (
            pipeline.post_admitted_count <= pipeline.refined_count,
            "post-admitted/refined monotonicity",
        ),
        (
            pipeline.post_rejected_count <= pipeline.refined_count,
            "post-rejected/refined monotonicity",
        ),
        (
            pipeline
                .post_admitted_count
                .checked_add(pipeline.post_rejected_count)
                == Some(pipeline.refined_count),
            "post-admission denominator",
        ),
        (
            pipeline.scored_count <= pipeline.post_admitted_count,
            "scored/post-admitted monotonicity",
        ),
        (
            pipeline.valid_count <= pipeline.scored_count,
            "valid/scored monotonicity",
        ),
        (
            pipeline.cluster_count <= pipeline.valid_count,
            "cluster/valid monotonicity",
        ),
    ] {
        if !valid {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 batch invariant failed: {label}"),
            ));
        }
    }
    let authority = authority_disposition(pipeline, producer)?;
    if authority
        != (Fixed64AuthorityDisposition {
            result_dependent_input_consumed: false,
            fallback_allowed: false,
            multi_anchor_consumed: false,
            denominator_preserved: true,
            molecular_execution_authorized: false,
            reservation_authorized: false,
            benchmark_execution_authorized: false,
            existing_rank_auto_change_authorized: false,
            customer_pose_emission_authorized: false,
            production_claim_authorized: false,
            scientific_claim_authorized: false,
        })
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 complete pipeline returned non-frozen authority",
        ));
    }
    require_authority_false(&[
        (
            producer.result_dependent_input_consumed,
            "producer result-dependent input",
        ),
        (producer.fallback_allowed, "producer fallback"),
        (producer.multi_anchor_consumed, "producer multi-anchor"),
        (
            producer.molecular_execution_authorized,
            "producer molecular execution",
        ),
        (producer.reservation_authorized, "producer reservation"),
        (
            producer.benchmark_execution_authorized,
            "producer benchmark execution",
        ),
        (
            producer.existing_rank_auto_change_authorized,
            "producer rank mutation",
        ),
        (
            producer.customer_pose_emission_authorized,
            "producer customer pose emission",
        ),
        (
            producer.production_claim_authorized,
            "producer production claim",
        ),
        (
            producer.scientific_claim_authorized,
            "producer scientific claim",
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
            refinement.molecular_execution_authorized,
            "refinement molecular execution",
        ),
        (refinement.reservation_authorized, "refinement reservation"),
        (
            refinement.benchmark_execution_authorized,
            "refinement benchmark execution",
        ),
        (
            refinement.existing_rank_auto_change_authorized,
            "refinement rank mutation",
        ),
        (
            refinement.customer_pose_emission_authorized,
            "refinement pose emission",
        ),
        (
            refinement.production_claim_authorized,
            "refinement production claim",
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
    if !bool_from_abi(producer.denominator_preserved, "producer denominator")? {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 producer did not preserve the denominator",
        ));
    }
    let expected_pair_count = ligand_atom_count
        .checked_mul(receptor_atom_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 geometric exact-pair denominator overflowed",
            )
        })?;
    for (slot, row) in producer_rows.iter().enumerate() {
        let expected_offset = u64::try_from(slot)
            .ok()
            .and_then(|slot| slot.checked_mul(ligand_atom_count))
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer coordinate offset overflowed",
                )
            })?;
        if row.slot_index as usize != slot
            || row.backend != backend.as_raw()
            || row.ligand_atom_count != ligand_atom_count
            || row.coordinate_offset != expected_offset
            || row.allocation_slot_receipt_sha256
                != expected_allocation.slots()[slot].receipt_sha256()
            || !bool_from_abi(row.denominator_preserved, "producer row denominator")?
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer row identity or denominator is invalid",
            ));
        }
        require_authority_false(&[
            (
                row.result_dependent_input_consumed,
                "producer row result input",
            ),
            (row.fallback_allowed, "producer row fallback"),
            (row.multi_anchor_consumed, "producer row multi-anchor"),
            (
                row.molecular_execution_authorized,
                "producer row molecular execution",
            ),
            (row.reservation_authorized, "producer row reservation"),
            (
                row.benchmark_execution_authorized,
                "producer row benchmark execution",
            ),
            (
                row.existing_rank_auto_change_authorized,
                "producer row rank mutation",
            ),
            (
                row.customer_pose_emission_authorized,
                "producer row pose emission",
            ),
            (
                row.production_claim_authorized,
                "producer row production claim",
            ),
            (
                row.scientific_claim_authorized,
                "producer row scientific claim",
            ),
        ])?;
        if !digest_present(&row.row_receipt_sha256) {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer row receipt is absent",
            ));
        }
        validate_geometric_admission_row_semantics(
            &row.geometric_admission,
            row.status,
            receptor_atom_count,
            ligand_atom_count,
            ligand_heavy_atom_count,
            expected_pair_count,
            geometric_hard_rejection_minimum_vdw_ratio,
            backend,
            geometric_input,
            producer_coordinates,
            slot,
        )?;
        let expected_source = expected_sources.get(slot).copied().ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 expected-source inventory is incomplete",
            )
        })?;
        validate_producer_row_semantics(
            row,
            producer_coordinates,
            slot,
            ligand_atom_count,
            expected_source,
        )?;
        validate_independent_producer_placement(
            backend,
            expected_allocation,
            expected_feature_geometry_inventory,
            geometric_input,
            canonical_pocket_normal,
            row,
            producer_coordinates,
            slot,
            usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer ligand denominator does not fit usize",
                )
            })?,
            expected_source,
            native_placement_replays.get(slot).and_then(Option::as_ref),
        )?;
        if row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED {
            let source = expected_source.ok_or_else(|| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 generated producer row lacks an independently selected source",
                )
            })?;
            let proposal_matches = if row.placement_kind
                == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
            {
                row.placement_receipt_sha256
                    == canonical_passthrough_placement_receipt(expected_receipt_graph, row, source)
                    && row.output_proposal_sha256 == source.evidence.proposal_sha256
            } else {
                row.output_proposal_sha256
                    == canonical_generated_proposal_receipt(expected_receipt_graph, row, source)
            };
            if !proposal_matches {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer proposal lineage was not independently rederived",
                ));
            }
        }
        let expected_geometric_row_receipt = canonical_geometric_row_receipt(
            expected_receipt_graph,
            row.status,
            producer_coordinates,
            slot,
            &row.geometric_admission,
        )?;
        let expected_producer_row_receipt =
            canonical_producer_row_receipt(expected_receipt_graph, row);
        if row.geometric_admission.row_receipt_sha256 != expected_geometric_row_receipt
            || row.row_receipt_sha256 != expected_producer_row_receipt
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer or geometric row receipt was not independently rederived",
            ));
        }
    }
    let expected_geometric_batch_receipt =
        canonical_geometric_batch_receipt(expected_receipt_graph, producer_rows);
    let expected_producer_batch_receipt = canonical_producer_batch_receipt(
        expected_receipt_graph,
        expected_geometric_batch_receipt,
        producer_rows,
        producer.generated_count,
    );
    if producer.geometric_admission_batch_receipt_sha256 != expected_geometric_batch_receipt
        || producer.producer_batch_receipt_sha256 != expected_producer_batch_receipt
        || pipeline.producer_batch_receipt_sha256 != expected_producer_batch_receipt
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 producer batch receipt graph was not independently rederived",
        ));
    }
    for (slot, row) in rigid_rows.iter().enumerate() {
        let producer_row = &producer_rows[slot];
        let admitted = producer_row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
            && producer_row.geometric_admission.decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && bool_from_abi(
                producer_row.geometric_admission.rank_eligible,
                "geometric rank eligibility",
            )?;
        let effective_mode = if admitted {
            requested_modes[slot]
        } else {
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
        };
        validate_rigid_row_semantics(
            row,
            effective_mode,
            rigid_max_steps[slot],
            rigid_coordinates,
            slot,
            ligand_atom_count,
        )?;
        validate_independent_rigid_replay(
            backend,
            row,
            effective_mode,
            rigid_max_steps[slot],
            producer_coordinates,
            rigid_coordinates,
            slot,
            ligand_atom_count,
            geometric_input,
            rigid_v2_config,
            rigid_v3_config,
            rigid_clearance_config,
        )?;
    }
    for (label, invalid_order) in [
        (
            "torsion",
            torsion_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "scorer",
            scorer_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "validity",
            validity_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "ranking",
            ranking_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "cluster",
            cluster_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
        (
            "refinement",
            refinement_rows
                .iter()
                .enumerate()
                .any(|(slot, row)| row.slot_index as usize != slot),
        ),
    ] {
        if invalid_order {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                format!("native fixed64 {label} row order is invalid"),
            ));
        }
    }
    if torsion_moves.iter().enumerate().any(|(index, row)| {
        row.slot_index as usize != index / sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize
            || row.move_index as usize != index % sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize
    }) {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 torsion move order is invalid",
        ));
    }
    validate_torsion_evidence(
        torsion_rows,
        torsion_moves,
        rigid_rows,
        proposal_is_torsion_eligible,
        torsion_max_steps,
        maximum_torsion_steps,
        rotatable_child_atom_indices,
        torsion_coordinates,
        rigid_coordinates,
        baseline_torsion_angles_radians,
        ligand_atom_count,
    )?;
    validate_refinement_evidence(
        refinement_rows,
        producer_rows,
        rigid_rows,
        torsion_rows,
        requested_modes,
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
        final_coordinates,
        final_quaternions,
        ligand_atom_count,
        backend,
    )?;
    if post_admission_rows.len() != candidate_count as usize {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 post-admission denominator is invalid",
        ));
    }
    for (slot, row) in post_admission_rows.iter().enumerate() {
        let coordinate_ready = refinement_rows[slot].status
            == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY
            && refinement_rows[slot].coordinate_available == 1;
        let synthetic_producer_status = if coordinate_ready {
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
        } else {
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
        };
        validate_geometric_admission_row_semantics(
            row,
            synthetic_producer_status,
            receptor_atom_count,
            ligand_atom_count,
            ligand_heavy_atom_count,
            ligand_atom_count
                .checked_mul(receptor_atom_count)
                .ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 post-admission pair denominator overflowed",
                    )
                })?,
            geometric_hard_rejection_minimum_vdw_ratio,
            backend,
            geometric_input,
            final_coordinates,
            slot,
        )?;
        let expected_row_receipt = canonical_geometric_row_receipt(
            expected_receipt_graph,
            synthetic_producer_status,
            final_coordinates,
            slot,
            row,
        )?;
        if row.row_receipt_sha256 != expected_row_receipt {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 post-admission row receipt was not independently rederived",
            ));
        }
    }
    let expected_post_admission_batch_receipt =
        canonical_geometric_batch_receipt_rows(expected_receipt_graph, post_admission_rows);
    if post_admission.batch_receipt_sha256 != expected_post_admission_batch_receipt {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 post-admission batch receipt was not independently rederived",
        ));
    }
    validate_scorer_and_validity_evidence(
        scorer_rows,
        validity_rows,
        ranking_rows,
        refinement_rows,
        post_admission_rows,
        ligand_atom_count,
        receptor_atom_count,
        validity_exclusion_count,
        validity_chirality_count,
        validity_contact_cell_size_angstrom,
        validity_receptor_cells,
        final_coordinates,
        final_quaternions,
        independent_scorer_context,
        independent_validity_context,
        backend,
    )?;
    validate_index_evidence(
        ranking,
        cluster,
        scorer_rows,
        validity_rows,
        ranking_rows,
        cluster_rows,
        primary_indices,
        valid_indices,
        representative_indices,
        top_k_indices,
        rmsd_threshold_angstrom,
        final_coordinates,
        ligand_atom_count,
    )?;
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 evidence ligand denominator does not fit usize",
        )
    })?;
    let mut refinement_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_evidence/1.0.0");
    let mut scorer_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scorer_evidence/1.0.0");
    let mut validity_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_validity_evidence/1.0.0");
    let mut ranking_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_ranking_evidence/1.0.0");
    let mut cluster_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_cluster_evidence/1.0.0");
    refinement_batch.digest(expected_receipt_graph.refinement_context_receipt_sha256);
    scorer_batch.digest(expected_receipt_graph.scorer_context_receipt_sha256);
    validity_batch.digest(expected_receipt_graph.validity_context_receipt_sha256);
    ranking_batch.digest(expected_receipt_graph.component_binding_receipt_sha256);
    cluster_batch.digest(expected_receipt_graph.component_binding_receipt_sha256);
    for (slot, row) in pipeline_rows.iter().enumerate() {
        let producer_row = &producer_rows[slot];
        let rigid_row = &rigid_rows[slot];
        let refinement_row = &refinement_rows[slot];
        let post_row = &post_admission_rows[slot];
        let scorer_row = &scorer_rows[slot];
        let validity_row = &validity_rows[slot];
        let ranking_row = &ranking_rows[slot];
        let cluster_row = &cluster_rows[slot];
        let admitted = producer_row.status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
            && producer_row.geometric_admission.decision
                == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && bool_from_abi(
                producer_row.geometric_admission.rank_eligible,
                "geometric rank eligibility",
            )?;
        let expected_effective_mode = if admitted {
            requested_modes[slot]
        } else {
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE
        };
        let ranking_has_coordinate = bool_from_abi(ranking_row.rank_eligible, "rank eligibility")?;
        let cluster_has_coordinate =
            bool_from_abi(cluster_row.cluster_eligible, "cluster eligibility")?;
        let refinement_ready =
            refinement_row.status == sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
        let post_admitted = post_row.status == sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED
            && post_row.decision == sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            && bool_from_abi(post_row.rank_eligible, "post-admission rank eligibility")?;
        let scored = scorer_row.status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED;
        let validity_evaluated = validity_row.status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
        let valid_rank_eligible =
            bool_from_abi(ranking_row.valid_rank_eligible, "valid-rank eligibility")?;
        let expected_refinement_evidence = canonical_refinement_evidence(
            slot,
            ligand_count,
            rigid_row,
            &torsion_rows[slot],
            torsion_moves,
            refinement_row,
            std::array::from_fn(|index| rigid_coordinates[index].as_slice()),
            std::array::from_fn(|index| torsion_coordinates[index].as_slice()),
            final_coordinates,
            final_quaternions,
        )?;
        let expected_scorer_evidence = canonical_scorer_evidence(scorer_row);
        let expected_validity_evidence = canonical_validity_evidence(validity_row);
        let expected_ranking_evidence = canonical_ranking_evidence(ranking_row);
        let expected_cluster_evidence = canonical_cluster_evidence(cluster_row);
        refinement_batch.digest(expected_refinement_evidence);
        scorer_batch.digest(expected_scorer_evidence);
        validity_batch.digest(expected_validity_evidence);
        ranking_batch.digest(expected_ranking_evidence);
        cluster_batch.digest(expected_cluster_evidence);
        validate_pipeline_receipt_bindings(
            row,
            pipeline.component_binding_receipt_sha256,
            pipeline.refinement_policy_receipt_sha256,
            pipeline.post_admission_policy_receipt_sha256,
            expected_refinement_evidence,
            expected_scorer_evidence,
            expected_validity_evidence,
            expected_ranking_evidence,
            expected_cluster_evidence,
        )?;
        if row.slot_index as usize != slot
            || row.reserved0.iter().any(|value| *value != 0)
            || row.reserved.iter().any(|value| *value != 0)
            || row.producer_status != producer_row.status
            || row.producer_failure_code != producer_row.failure_code
            || row.initial_admission_decision != producer_row.geometric_admission.decision
            || row.requested_refinement_mode != requested_modes[slot]
            || row.effective_refinement_mode != expected_effective_mode
            || rigid_row.candidate_mode != expected_effective_mode
            || row.refinement_status != refinement_row.status
            || row.refinement_failure_stage != refinement_row.failure_stage
            || row.post_admission_status != post_row.status
            || row.post_admission_failure_code != post_row.failure_code
            || row.post_admission_decision != post_row.decision
            || row.post_admission_rank_eligible != post_row.rank_eligible
            || row.scorer_status != scorer_row.status
            || row.scorer_failure_code != scorer_row.failure_code
            || row.validity_status != validity_row.status
            || row.validity_failure_code != validity_row.failure_code
            || row.stable_rank != ranking_row.stable_rank
            || row.stable_valid_rank != ranking_row.stable_valid_rank
            || row.cluster_status != cluster_row.status
            || row.cluster_id != cluster_row.cluster_id
            || row.cluster_rank != cluster_row.cluster_rank
            || row.top_k_rank != cluster_row.top_k_rank
            || row.producer_row_receipt_sha256 != producer_row.row_receipt_sha256
            || row.final_coordinate_sha256 != refinement_row.coordinate_sha256
            || row.post_admission_row_receipt_sha256 != post_row.row_receipt_sha256
            || (refinement_ready && !admitted)
            || (post_admitted && !refinement_ready)
            || (scored && !post_admitted)
            || (validity_evaluated && !scored)
            || (ranking_has_coordinate && !scored)
            || (valid_rank_eligible
                && (!validity_evaluated
                    || validity_row.passed_check_mask != sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
                    || validity_row.blocker_mask != 0))
            || (cluster_has_coordinate && !valid_rank_eligible)
            || (ranking_has_coordinate
                && ranking_row.coordinate_sha256 != refinement_row.coordinate_sha256)
            || (cluster_has_coordinate
                && cluster_row.coordinate_sha256 != ranking_row.coordinate_sha256)
            || [
                row.producer_row_receipt_sha256,
                row.refinement_evidence_sha256,
                row.post_admission_row_receipt_sha256,
                row.scorer_evidence_sha256,
                row.validity_evidence_sha256,
                row.ranking_evidence_sha256,
                row.cluster_evidence_sha256,
                row.row_receipt_sha256,
            ]
            .iter()
            .any(|digest| !digest_present(digest))
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline row identity or evidence receipt is invalid",
            ));
        }
    }
    let primary = counted_index_prefix(
        primary_indices,
        ranking.primary_index_count,
        "primary rank batch receipt",
    )?;
    let valid = counted_index_prefix(
        valid_indices,
        ranking.valid_index_count,
        "valid rank batch receipt",
    )?;
    ranking_batch.u64(ranking.primary_index_count);
    for slot in primary {
        ranking_batch.u32(*slot);
    }
    ranking_batch.u64(ranking.valid_index_count);
    for slot in valid {
        ranking_batch.u32(*slot);
    }
    ranking_batch.byte(ranking.existing_rank_auto_change_authorized);
    ranking_batch.byte(ranking.customer_pose_emission_authorized);
    ranking_batch.byte(ranking.production_claim_authorized);
    let representatives = counted_index_prefix(
        representative_indices,
        cluster.representative_index_count,
        "cluster representative batch receipt",
    )?;
    let top_k = counted_index_prefix(
        top_k_indices,
        cluster.top_k_index_count,
        "cluster Top-K batch receipt",
    )?;
    cluster_batch.u64(cluster.representative_index_count);
    for slot in representatives {
        cluster_batch.u32(*slot);
    }
    cluster_batch.u64(cluster.top_k_index_count);
    for slot in top_k {
        cluster_batch.u32(*slot);
    }
    cluster_batch.byte(cluster.existing_rank_auto_change_authorized);
    cluster_batch.byte(cluster.customer_pose_emission_authorized);
    cluster_batch.byte(cluster.production_claim_authorized);
    let refinement_batch_receipt_sha256 = refinement_batch.finish();
    let scorer_batch_receipt_sha256 = scorer_batch.finish();
    let validity_batch_receipt_sha256 = validity_batch.finish();
    let ranking_batch_receipt_sha256 = ranking_batch.finish();
    let cluster_batch_receipt_sha256 = cluster_batch.finish();
    let mut pipeline_batch =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_complete_pipeline_batch/2.0.0");
    pipeline_batch.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);
    pipeline_batch.i32(backend.as_raw());
    pipeline_batch.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    pipeline_batch.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    pipeline_batch.digest(expected_receipt_graph.allocation_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.source_bundle_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.admission_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.refinement_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.scorer_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.validity_context_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.component_binding_receipt_sha256);
    pipeline_batch.digest(expected_producer_batch_receipt);
    pipeline_batch.digest(expected_receipt_graph.refinement_policy_receipt_sha256);
    pipeline_batch.digest(refinement_batch_receipt_sha256);
    pipeline_batch.digest(expected_receipt_graph.post_admission_policy_receipt_sha256);
    pipeline_batch.digest(expected_post_admission_batch_receipt);
    pipeline_batch.digest(scorer_batch_receipt_sha256);
    pipeline_batch.digest(validity_batch_receipt_sha256);
    pipeline_batch.digest(ranking_batch_receipt_sha256);
    pipeline_batch.digest(cluster_batch_receipt_sha256);
    pipeline_batch.u64(generated_row_count);
    pipeline_batch.u64(initial_admitted_row_count);
    pipeline_batch.u64(refined_row_count);
    pipeline_batch.u64(post_admitted_row_count);
    pipeline_batch.u64(post_rejected_row_count);
    pipeline_batch.u64(scored_row_count);
    pipeline_batch.u64(valid_row_count);
    pipeline_batch.u64(cluster.representative_index_count);
    for row in pipeline_rows {
        pipeline_batch.digest(row.row_receipt_sha256);
    }
    for value in [0_u8, 0, 1, 0, 0, 0, 0, 0, 0, 0] {
        pipeline_batch.byte(value);
    }
    let pipeline_batch_receipt_sha256 = pipeline_batch.finish();
    if pipeline.refinement_batch_receipt_sha256 != refinement_batch_receipt_sha256
        || pipeline.scorer_batch_receipt_sha256 != scorer_batch_receipt_sha256
        || pipeline.validity_batch_receipt_sha256 != validity_batch_receipt_sha256
        || pipeline.ranking_batch_receipt_sha256 != ranking_batch_receipt_sha256
        || pipeline.cluster_batch_receipt_sha256 != cluster_batch_receipt_sha256
        || pipeline.pipeline_batch_receipt_sha256 != pipeline_batch_receipt_sha256
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 complete batch receipt graph was not independently rederived",
        ));
    }
    Ok(())
}
