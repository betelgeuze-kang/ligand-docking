from __future__ import annotations

import json
from pathlib import Path

from deploy import product_release_bundle
from tools.product import build_product_release_source_of_truth_gate as source_of_truth


ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "improvement_items_remaining_work.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _summary(path: str) -> dict:
    payload = _payload(path)
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _payload(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_remaining_work_doc_tracks_current_release_metrics() -> None:
    text = _doc_text()
    bundle = product_release_bundle.build_release_bundle(release_id="doc-metric-check")
    refresh = _summary("runs/product_release_current_refresh_plan_current.json")
    source = _summary("runs/product_release_source_of_truth_gate_current.json")
    action_board = _summary("runs/goal_operator_action_board_current.json")
    command_count = len(source_of_truth.RELEASE_REFRESH_COMMANDS)

    assert f"`artifact_count={bundle['artifact_count']}`" in text
    assert f"`check_count={bundle['check_count']}`" in text
    assert f"`pass_count={bundle['pass_count']}`" in text
    assert f"`product_release_current_refresh_verified`, `command_count={command_count}`" in text
    assert f"`executed_count={command_count}`" in text
    assert f"`release_refresh_command_count={command_count}`" in text
    assert f"`row_count={source['row_count']}`" in text
    assert f"`artifact_row_count={source['artifact_row_count']}`" in text
    assert f"`semantic_status_row_count={source['semantic_status_row_count']}`" in text
    assert f"`readme_row_count={source['readme_row_count']}`" in text
    assert f"`final_gate_count={refresh['final_gate_count']}`" in text
    assert f"`final_gate_blocker_count={refresh['final_gate_blocker_count']}`" in text
    assert (
        f"`goal_release_decision_gate_status={action_board['goal_release_decision_gate_status']}`"
        in text
    )
    assert f"`goal_release_allowed={str(action_board['goal_release_allowed']).lower()}`" in text
    assert f"`goal_release_blocker_count={action_board['goal_release_blocker_count']}`" in text

    assert "`artifact_count=28`" not in text
    assert "`artifact_count=31`" not in text
    assert "`artifact_count=33`" not in text
    assert "`check_count=21`" not in text
    assert "`check_count=24`" not in text
    assert "`check_count=25`" not in text
    assert "`pass_count=21`" not in text
    assert "`pass_count=24`" not in text
    assert "`pass_count=25`" not in text
    assert "`command_count=76`" not in text
    assert "`command_count=88`" not in text
    assert "`executed_count=76`" not in text
    assert "`executed_count=88`" not in text
    assert "`release_refresh_command_count=79`" not in text
    assert "`release_refresh_command_count=88`" not in text
    assert "`final_gate_count=2`" not in text
    assert "`final_gate_count=3`" not in text


def test_remaining_work_doc_tracks_current_third_party_license_review_gate() -> None:
    text = _doc_text()

    assert "`third_party_license_review_gate_ready`, `expected_review_asset_count=1`" in text
    assert "`review_csv_present=true`, `approved_review_asset_count=1`" in text
    assert "`missing_review_asset_count=0`, `blocker_count=0`" in text

    assert "`blocked_third_party_license_review_gate`" not in text
    assert "`review_csv_present=false`" not in text
    assert "`missing_review_asset_count=1`" not in text


def test_remaining_work_doc_tracks_current_full_commercial_bottleneck_matrix() -> None:
    text = _doc_text()
    matrix = _summary("runs/product_full_commercial_blocker_evidence_matrix_current.json")
    audit = _summary("runs/product_goal_completion_audit_current.json")
    bottleneck = _summary("runs/goal_bottleneck_briefing_current.json")
    handoff = _summary("runs/product_commercial_readiness_handoff_bundle_current.json")

    assert f"`{matrix['status']}`" in text
    assert f"`release_blocker_visibility_ready={str(matrix['release_blocker_visibility_ready']).lower()}`" in text
    assert f"`matrix_row_count={matrix['matrix_row_count']}`" in text
    assert f"`blocked_matrix_row_count={matrix['blocked_matrix_row_count']}`" in text
    assert f"`approval_token_count={matrix['approval_token_count']}`" in text
    assert f"`release_blocker_fail_count={audit['release_blocker_fail_count']}`" in text
    assert f"`primary_release_blocker_requirement_id={audit['primary_release_blocker_requirement_id']}`" in text
    assert f"`completion_audit_release_blocker_bottleneck_count={bottleneck['completion_audit_release_blocker_bottleneck_count']}`" in text
    assert (
        f"`commercial_readiness_handoff_bundle_artifact_reference_count="
        f"{audit['commercial_readiness_handoff_bundle_artifact_reference_count']}`"
        in text
    )
    assert f"`artifact_reference_count={handoff['artifact_reference_count']}`" in text
    assert f"`local_required_artifact_reference_count={handoff['local_required_artifact_reference_count']}`" in text
    assert (
        f"`product_scope_next_operator_completion_item_id="
        f"{handoff['product_scope_next_operator_completion_item_id']}`"
        in text
    )
    assert (
        f"`product_scope_transporter_p0_return_bundle_next_artifact_path="
        f"{handoff['product_scope_transporter_p0_return_bundle_next_artifact_path']}`"
        in text
    )
    assert (
        f"`product_goal_scope_transporter_p0_operator_validation_candidate_status="
        f"{handoff['product_goal_scope_transporter_p0_operator_validation_candidate_status']}`"
        in text
    )
    assert "`local_scope_transporter_p0_return_bundle_artifact`" in text
    assert "`config/ligand_binding_reference_blind_aqp1_v1.csv`" in text

    assert "`completion_audit_release_blocker_bottleneck_count=3`" not in text
    assert "`commercial_readiness_handoff_bundle_artifact_reference_count=29`" not in text
    assert "`artifact_reference_count=29`" not in text


def test_remaining_work_doc_tracks_current_license_decision_packet() -> None:
    text = _doc_text()
    license_packet = _summary("runs/product_license_decision_packet_current.json")

    assert f"`{license_packet['status']}`" in text
    assert f"`hard_blocker_count={license_packet['hard_blocker_count']}`" in text
    assert f"`review_item_count={license_packet['review_item_count']}`" in text
    assert (
        f"`commercial_independence_ready="
        f"{str(license_packet['commercial_independence_ready']).lower()}`"
        in text
    )
    assert (
        f"`license_decision_gate_ready="
        f"{str(license_packet['license_decision_gate_ready']).lower()}`"
        in text
    )
    assert f"`license_present={str(license_packet['license_present']).lower()}`" in text
    assert "`license_already_present`" in text


def test_remaining_work_doc_tracks_current_production_ai_priority_bottleneck() -> None:
    text = _doc_text()
    priority = _summary("runs/production_ai_registry_promotion_priority_packet_current.json")

    assert f"`operator_input_required_count={priority['operator_input_required_count']}`" in text
    assert f"`top_gate_id={priority['top_gate_id']}`" in text
    assert f"`{priority['top_gate_id']}`" in text
    assert f"`{priority['top_priority_bucket']}`" in text
    assert "trained/preflight-ready checkpoint는 registry에" in text
    assert "`trained_model_checkpoint_count_positive`는 만족된 gate로 보존된다" in text


def test_remaining_work_doc_tracks_current_enabled_runner_profiles() -> None:
    text = _doc_text()
    payload = _payload("runs/api_runner_profile_enablement_work_order_current.json")
    summary = payload.get("summary", payload)
    enabled_profiles = sorted(
        row["profile_id"]
        for row in payload.get("rows", [])
        if isinstance(row, dict) and row.get("enabled") is True
    )

    assert f"enabled runner profile {summary['enabled_profile_count']}종" in text
    for profile_id in enabled_profiles:
        assert f"`{profile_id}`" in text

    assert "enabled runner profile 2종" not in text
    assert "API runner profile enable + evidence review" in text


def test_remaining_work_doc_tracks_product_readiness_script_entrypoints() -> None:
    text = _doc_text()

    assert "`scripts/check_independent_product_readiness.py`" in text
    assert "`independent_product_readiness_verified`" in text
    assert "`independent_restricted_product_ready=true`" in text
    assert "`full_commercial_claim_promotion_ready=false`" in text
    assert "`full_commercial_open_gap_ids=[]`" in text
    assert "`science_accuracy_frontier_status=blocked_science_accuracy_frontier`" in text
    assert "`science_accuracy_frontier_restricted_ready=true`" in text
    assert "`science_accuracy_frontier_broad_commercial_blocked=true`" in text
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_ready=true`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_row_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_missing_row_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count=136`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count=0`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count=0`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count=51`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_download_executed=false`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_present=true`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count=0`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required=true`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id=r9_statistical_support_coordinate_fetch_001`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker=operator_placeholders_unfilled`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_ready=true`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_present=true`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`"
        in text
    )
    assert (
        "`science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`"
        in text
    )
    assert "`public_benchmark_work_order_receptor_coordinate_validation_ready_row_count=8`" in text
    assert "`public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count=0`" in text
    assert "`public_benchmark_work_order_receptor_coordinate_validation_min_atom_records=20`" in text
    assert "`public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records=20`" in text
    assert "`public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues=5`" in text
    assert "`public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues=5`" in text
    assert "`public_benchmark_work_order_metric_evidence_required=true`" in text
    assert "`public_benchmark_work_order_metric_evidence_ready_row_count=0`" in text
    assert "`public_benchmark_work_order_metric_evidence_blocked_row_count=8`" in text
    assert "`public_benchmark_work_order_metric_evidence_missing_required_input_artifact_row_count=0`" in text
    assert "`public_benchmark_work_order_metric_evidence_missing_dockq_source_row_count=8`" in text
    assert "`public_benchmark_work_order_metric_evidence_missing_lddt_pli_source_row_count=8`" in text
    assert "`public_benchmark_work_order_metric_evidence_missing_internal_deltaG_source_row_count=8`" in text
    assert "`runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv`" in text
    assert "`runs/refine_tier_public_benchmark_metric_evidence_current.csv`" in text
    assert "`refine_tier_public_benchmark_metric_sources_materialized`" in text
    assert "`metric_evidence_pass_row_count=8`" in text
    assert "`free_energy_spearman=0.6190476190476191`" in text
    assert "`free_energy_spearman_bootstrap_p05=-0.14285714285714285`" in text
    assert "`claim_grade_public_benchmark_statistical_support_ready=false`" in text
    assert "`claim_grade_public_benchmark_statistical_support_blocker_count=3`" in text
    assert "`public_benchmark_materialized_claim_grade_statistical_support_ready=false`" in text
    assert "`runs/refine_tier_public_benchmark_statistical_support_work_order_current.json`" in text
    assert "`refine_tier_public_benchmark_statistical_support_work_order_ready`" in text
    assert "`work_order_ready=true`, `expansion_slot_count=17`" in text
    assert "`minimum_new_pair_count=17`, `minimum_new_holdout_pair_count=5`" in text
    assert "`minimum_new_fit_or_holdout_pair_count=12`" in text
    assert "`bootstrap_spearman_p05_deficit=0.6428571428571428`" in text
    assert "`bootstrap_retest_required=true`" in text
    assert "`canonical_intake_promotion_allowed=false`" in text
    assert "`runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json`" in text
    assert "`refine_tier_public_benchmark_statistical_support_candidate_queue_ready`" in text
    assert "`selected_candidate_count=17`" in text
    assert "`holdout_selected_candidate_count=5`" in text
    assert "`fit_or_holdout_selected_candidate_count=12`" in text
    assert "`ligand_pose_artifact_present_count=17`" in text
    assert "`experimental_deltaG_prefilled_count=17`" in text
    assert "`candidate_source_distinct_target_count=276`" in text
    assert "`receptor_coordinate_artifact_present_count=0`" in text
    assert "`receptor_coordinate_artifact_missing_count=17`" in text
    assert "`candidate_ready_for_metric_materialization_count=0`" in text
    assert "`candidate_ready_for_canonical_intake_count=0`" in text
    assert "`candidate_coordinate_archive_count=2`" in text
    assert "`candidate_coordinate_archive_receptor_member_count=0`" in text
    assert "`candidate_coordinate_archive_receptor_member_target_count=0`" in text
    assert "`candidate_coordinate_archive_missing_receptor_member_target_count=17`" in text
    assert "같은 로컬 coordinate matcher를 재사용한다" in text
    assert "`archive.tar::pdbbind/<target>/<target>_protein.pdb`" in text
    assert "현재 로컬 coordinate archive 2개에는 17개 후보의 ligand pose/source member만" in text
    assert "`runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json`" in text
    assert "`refine_tier_public_benchmark_statistical_support_coordinate_intake_ready`" in text
    assert "`coordinate_intake_row_count=17`" in text
    assert "`coordinate_intake_artifact_present_row_count=0`" in text
    assert "`coordinate_intake_missing_row_count=17`" in text
    assert "`coordinate_intake_suggested_public_url_row_count=17`" in text
    assert "`coordinate_intake_suggested_local_path_row_count=17`" in text
    assert "`coordinate_intake_suggested_local_path_candidate_count=136`" in text
    assert "`coordinate_intake_suggested_local_path_present_count=0`" in text
    assert "`coordinate_intake_suggested_local_path_present_target_count=0`" in text
    assert "`coordinate_intake_suggested_local_path_missing_target_count=17`" in text
    assert "`coordinate_intake_expected_archive_member_example_count=51`" in text
    assert "`coordinate_intake_operator_review_required_row_count=17`" in text
    assert "`coordinate_validation_row_count=17`" in text
    assert "`coordinate_validation_pass_row_count=0`" in text
    assert "`coordinate_validation_blocked_row_count=17`" in text
    assert "`coordinate_validation_missing_row_count=17`" in text
    assert (
        "`runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json`"
        in text
    )
    assert "`refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready`" in text
    assert "`coordinate_fetch_row_count=17`" in text
    assert "`coordinate_fetch_required_row_count=17`" in text
    assert "`coordinate_fetch_blocked_row_count=17`" in text
    assert "`coordinate_fetch_primary_url_row_count=17`" in text
    assert "`coordinate_fetch_staging_destination_row_count=17`" in text
    assert "`coordinate_fetch_ready_for_validation_row_count=0`" in text
    assert "`coordinate_fetch_external_download_executed=false`" in text
    assert (
        "`runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json`"
        in text
    )
    assert "`blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply`" in text
    assert "`coordinate_fetch_apply_preview_ready=true`" in text
    assert "`coordinate_fetch_apply_row_count=17`" in text
    assert "`coordinate_fetch_apply_preflight_pass_row_count=17`" in text
    assert "`coordinate_fetch_apply_preview_ready_row_count=17`" in text
    assert "`coordinate_fetch_apply_blocked_row_count=0`" in text
    assert "`coordinate_fetch_apply_downloaded_row_count=0`" in text
    assert "`post_fetch_validation_supported=true`" in text
    assert "`post_fetch_validation_requested=false`" in text
    assert "`post_fetch_validation_executed=false`" in text
    assert "`post_fetch_validation_coordinate_validation_pass_row_count=0`" in text
    assert (
        "`post_fetch_validation_candidate_queue=runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json`"
        in text
    )
    assert "`approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`" in text
    assert "`--mode execute --run-post-fetch-validation`" in text
    assert (
        "`runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json`"
        in text
    )
    assert (
        "`refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready`"
        in text
    )
    assert "`r4_preflight_ready=true`" in text
    assert "`r4_row_count=17`" in text
    assert "`ready_for_r4_review_row_count=17`" in text
    assert "`blocked_r4_row_count=0`" in text
    assert "`required_r4_fields=target;action;impact;risk;rollback;verification`" in text
    assert "`fetch_required_row_count=17`" in text
    assert "`metric_materialization_readiness_present=true`" in text
    assert "`metric_materialization_row_count=17`" in text
    assert "`metric_materialization_candidate_blocked_count=17`" in text
    assert "`planned_metric_source_payload_count=51`" in text
    assert "`metric_materialization_blocked_row_count=17`" in text
    assert "`metric_source_templates_present=true`" in text
    assert "`metric_source_templates_ready=true`" in text
    assert "`metric_source_template_row_count=51`" in text
    assert "`metric_source_template_candidate_row_count=17`" in text
    assert "`metric_source_template_metric_name_count=3`" in text
    assert "`metric_source_template_fill_ready_row_count=0`" in text
    assert "`metric_source_template_fill_blocked_row_count=51`" in text
    assert "`metric_source_template_existing_payload_present_row_count=0`" in text
    assert "최신 metric materialization readiness를 R4 row에 묶어" in text
    assert "51개 metric source template placeholder" in text
    assert "metric source templates," in text
    assert "statistical support metric source template 51개/fill-ready 0개/fill-blocked 51개" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`" in text
    assert (
        "`field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`"
        in text
    )
    assert (
        "`field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`"
        in text
    )
    assert (
        "`field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`"
        in text
    )
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`" in text
    assert "`field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`" in text
    assert (
        "`field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`"
        in text
    )
    assert "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51" in text
    assert "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51" in text
    assert "product_commercial_readiness_operator_packet_semantic_ready" in text
    assert "product_commercial_readiness_handoff_bundle_semantic_ready" in text
    assert "`metric_source_templates_metric_source_payload_fill_blocked_row_count=51`" in text
    assert "`refine_tier_public_benchmark_claim_grade_gap_audit_ready`" in text
    assert "`observed_public_benchmark_pair_count=8`" in text
    assert "`observed_holdout_pair_count=3`" in text
    assert "`observed_bootstrap_spearman_p05=-0.14285714285714285`" in text
    assert "`blocked_gap_row_count=5`" in text
    assert "`top_science_gap_id=coordinate_fetch_r4_approval_required`" in text
    assert "`coordinate_validation_deficit=17`" in text
    assert "`metric_source_payload_fill_deficit=51`" in text
    assert "`execute_command_count=1`" in text
    assert "`authorized_for_external_download=false`" in text
    assert (
        "`runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json`"
        in text
    )
    assert (
        "`refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready`"
        in text
    )
    assert "`metric_materialization_readiness_ready=true`" in text
    assert "`metric_materialization_all_candidates_ready=false`" in text
    assert "`metric_materialization_row_count=17`" in text
    assert "`metric_materialization_candidate_ready_count=0`" in text
    assert "`metric_materialization_candidate_blocked_count=17`" in text
    assert "`metric_materialization_input_artifact_contract_ready=false`" in text
    assert "`required_metric_input_artifact_count=34`" in text
    assert "`present_required_metric_input_artifact_count=17`" in text
    assert "`missing_required_metric_input_artifact_count=17`" in text
    assert "`missing_required_metric_input_artifact_row_count=17`" in text
    assert "`coordinate_validation_blocked_row_count=17`" in text
    assert "`planned_metric_source_payload_count=51`" in text
    assert "`existing_metric_source_payload_count=0`" in text
    assert "`required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`" in text
    assert (
        "`required_metric_source_payload_fields=metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls`"
        in text
    )
    assert "`claim_grade_statistical_support_ready=false`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_readiness_present=true`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_readiness_ready=true`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_all_candidates_ready=false`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_row_count=17`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_candidate_ready_count=0`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_candidate_blocked_count=17`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready=false`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_required_input_artifact_count=34`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count=17`" in text
    assert "`public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count=17`" in text
    assert (
        "`public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count=17`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count=0`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count=17`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count=0`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count=51`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count=11`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields=metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls`"
        in text
    )
    assert "`public_benchmark_statistical_support_metric_source_templates_present=true`" in text
    assert "`public_benchmark_statistical_support_metric_source_templates_ready=true`" in text
    assert "`public_benchmark_statistical_support_metric_source_templates_template_row_count=51`" in text
    assert "`public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count=17`" in text
    assert "`public_benchmark_statistical_support_metric_source_templates_template_metric_name_count=3`" in text
    assert (
        "`public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count=51`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count=51`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count=51`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count=51`"
        in text
    )
    assert "`public_benchmark_statistical_support_metric_source_templates_placeholder_value_count=51`" in text
    assert "`public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total=0`" in text
    assert "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`" in text
    assert "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`" in text
    assert "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`" in text
    assert "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count=0`" in text
    assert (
        "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`"
        in text
    )
    assert "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download=false`" in text
    assert "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed=false`" in text
    assert (
        "`public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`"
        in text
    )
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count=0`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count=51`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`" in text
    assert "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed=false`" in text
    assert (
        "`public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`"
        in text
    )
    assert "`openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized`" in text
    assert (
        "`openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_r4_approval_required`"
        in text
    )
    assert (
        "`openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_not_ready`"
        in text
    )
    assert (
        "`openmm_schrodinger_public_benchmark_statistical_support_metric_source_payload_operator_receipt_not_ready`"
        in text
    )
    assert "`blocker_count=9`" in text
    assert "`blocker_count=6`" in text
    assert "`runs/engine_refinement_claim_evidence_priority_packet_current.json`" in text
    assert "`runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json`" in text
    assert "`Review the R4 coordinate-fetch preflight`" in text
    assert "`public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`" in text
    assert (
        "`public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count=17`"
        in text
    )
    assert (
        "`public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count=17`"
        in text
    )
    assert "`public_benchmark_statistical_support_coordinate_fetch_r4_download_executed=false`" in text
    assert (
        "`runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json`"
        in text
    )
    assert "`refine_tier_public_benchmark_statistical_support_metric_source_templates_ready`" in text
    assert "`metric_source_templates_ready=true`" in text
    assert "`template_row_count=51`" in text
    assert "`template_candidate_row_count=17`" in text
    assert "`template_metric_name_count=3`" in text
    assert "`template_metric_source_artifact_path_row_count=51`" in text
    assert "`template_payload_required_fields_present_row_count=51`" in text
    assert "`metric_source_payload_fill_ready_row_count=0`" in text
    assert "`metric_source_payload_fill_blocked_row_count=51`" in text
    assert "`coordinate_validation_blocked_template_row_count=51`" in text
    assert "`missing_required_input_template_row_count=51`" in text
    assert "`existing_metric_source_payload_present_row_count=0`" in text
    assert "`placeholder_value_count=51`" in text
    assert "`placeholder_method_count=51`" in text
    assert "`placeholder_operator_id_count=51`" in text
    assert "`placeholder_reviewed_at_utc_count=51`" in text
    assert "`placeholder_license_ok_count=51`" in text
    assert "`external_engine_calls_total=0`" in text
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_row_count=17`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_ready_count=0`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_blocked_count=17`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_input_artifact_count=34`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count=17`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count=17`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count=0`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count=51`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count=0`"
        in text
    )
    assert (
        "`engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`"
        in text
    )
    assert "`planned_metric_source_payload_count=51`" in text
    assert "top-level 병목 briefing" in text
    assert "R9 receptor-coordinate validation pass 8개/blocked 0개" in text
    assert "materialized metric-evidence pass 8개" in text
    assert "claim-grade statistical support expansion slot 17개" in text
    assert "statistical support candidate queue 17개" in text
    assert "receptor coordinate missing 17/17개" in text
    assert "statistical support coordinate intake 17개" in text
    assert "coordinate validation pass 0개/blocked 17개" in text
    assert "statistical support coordinate fetch required 17개/ready-for-validation 0개" in text
    assert "statistical support coordinate fetch apply preview preflight pass 17개/downloaded 0개" in text
    assert "`worksheet_field_row_count=389`" in text
    assert "`operator_fill_pending_field_count=296`" in text
    assert "`public_benchmark_statistical_support_expansion_field_count=221`" in text
    assert "`public_benchmark_statistical_support_expansion_pending_field_count=204`" in text
    assert "`public_benchmark_statistical_support_expansion_ready_field_count=17`" in text
    assert "`field_worksheet_pending_field_count=296`" in text
    assert "17개 추가 public benchmark pair" in text
    assert "bootstrap Spearman\np05 >= 0.5 재검증" in text
    assert "`candidate_claim_grade_public_benchmark_ready=true`" in text
    assert "`scripts/verify_quality_gate.py`" in text
    assert "`product_quality_gate_verified`" in text
    assert "`quality_gate_ready=true`" in text
    assert "`runs/product_quality_gate_verification_current.json`" in text
    assert "R9 receptor-coordinate validation blocked 8개" not in text
    assert "receptor/complex coordinate validation 8/8 blocked" not in text
    assert "DockQ/lDDT-PLI/internal ΔG source evidence 8/8/8 missing" not in text
    assert "`selected_candidate_count=0`" not in text
    assert "`coordinate_validation_pass_row_count=17`" not in text
