#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXECUTION_JSON = "runs/execution_handoff_dashboard_current.json"
DEFAULT_OPERATOR_CONSOLE_JSON = "runs/operator_evidence_closure_console_current.json"
DEFAULT_PLATFORM_INDEX_JSON = "runs/platform_packet_index_current.json"
DEFAULT_PLATFORM_QUICKSTART_JSON = "runs/platform_operator_quickstart_packet_current.json"
DEFAULT_PRETEST_SEQUENCE_JSON = "runs/pretest_execution_sequence_note_current.json"
DEFAULT_PRETEST_CHECKLIST_JSON = "runs/pretest_command_checklist_current.json"
DEFAULT_RUN_NOW_PACKET_JSON = "runs/run_now_family_operator_packet_current.json"
DEFAULT_RUN_NOW_SAFE_COMMAND_JSON = "runs/run_now_safe_command_packet_current.json"
DEFAULT_IDP_PRETEST_SCOPE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_BROADER_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_IDP_BROADER_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_PROMOTION_REVIEW_JSON = "runs/idp_broader_promotion_review_packet_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_IDP_BROADER_REVIEW_PACKET_JSON = "runs/idp_broader_shadow_review_packet_current.json"
DEFAULT_IDP_BROADER_REVIEW_RESOLUTION_JSON = "runs/idp_broader_shadow_review_resolution_current.json"
DEFAULT_IDP_BROADER_LAUNCH_PACKET_JSON = "runs/idp_broader_shadow_launch_packet_current.json"
DEFAULT_IDP_PAGE4_CURATION_PACKET_JSON = "runs/idp_page4_anchor_curation_packet_current.json"
DEFAULT_IDP_PAGE4_EVIDENCE_SEED_JSON = "runs/idp_page4_anchor_evidence_seed_current.json"
DEFAULT_IDP_PAGE4_PROVENANCE_FILL_JSON = "runs/idp_page4_anchor_provenance_fill_draft_current.json"
DEFAULT_IDP_PAGE4_CITATION_CONFIRMED_JSON = "runs/idp_page4_anchor_citation_confirmed_packet_current.json"
DEFAULT_IDP_PAGE4_PHOSPHO_FOLLOWUP_JSON = "runs/idp_page4_phosphorylation_followup_packet_current.json"
DEFAULT_IDP_PAGE4_PHOSPHO_FILL_DRAFT_JSON = "runs/idp_page4_phosphorylation_fill_draft_current.json"
DEFAULT_IDP_PAGE4_READINESS_JSON = "runs/idp_page4_anchor_backed_candidate_readiness_current.json"
DEFAULT_IDP_PAGE4_PH_LOW_FILL_JSON = "runs/idp_page4_ph_low_fill_value_packet_current.json"
DEFAULT_IDP_PAGE4_PH_HIGH_FILL_JSON = "runs/idp_page4_ph_high_fill_value_packet_current.json"
DEFAULT_IDP_PAGE4_REVIEW_JSON = "runs/idp_page4_anchor_backed_candidate_review_current.json"
DEFAULT_IDP_PAGE4_DECISION_JSON = "runs/idp_page4_anchor_backed_candidate_decision_current.json"
DEFAULT_IDP_PAGE4_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_IDP_PAGE4_CONFIRMATION_RECOMMENDATION_JSON = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.json"
DEFAULT_IDP_PAGE4_PROMOTION_REVIEW_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_IDP_PAGE4_CONFIRMATION_LAUNCH_JSON = "runs/idp_page4_manual_confirmation_launch_packet_current.json"
DEFAULT_IDP_PAGE4_CONFIRMATION_CONSOLE_JSON = "runs/idp_page4_manual_confirmation_console_current.json"
DEFAULT_IDP_PAGE4_CONFIRMATION_WORKBENCH_JSON = "runs/idp_page4_manual_confirmation_workbench_current.json"
DEFAULT_IDP_PAGE4_CONFIRMATION_NOTE_TEMPLATES_JSON = "runs/idp_page4_manual_confirmation_note_templates_current.json"
DEFAULT_IDP_PAGE4_QUANTITATIVE_REPLACEMENT_JSON = "runs/idp_page4_quantitative_anchor_replacement_packet_current.json"
DEFAULT_HEATMAP_JSON = "runs/family_readiness_heatmap_current.json"
DEFAULT_COMMERCIALIZATION_GAP_JSON = "runs/commercialization_gap_burndown_current.json"
DEFAULT_COMMERCIAL_CORE_JSON = "runs/commercial_core_preservation_packet_current.json"
DEFAULT_PARTIAL_CONSOLE_JSON = "runs/partial_authoritative_family_handoff_current.json"
DEFAULT_PARTIAL_OPERATOR_CONSOLE_JSON = "runs/partial_authoritative_operator_console_current.json"
DEFAULT_PARTIAL_QUICKSTART_JSON = "runs/partial_authoritative_quickstart_packet_current.json"
DEFAULT_PARTIAL_REVIEWER_CONSOLE_JSON = "runs/partial_authoritative_reviewer_console_current.json"
DEFAULT_CA2_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_PXR_DAY_PLAN_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_CA2_WORKBENCH_JSON = "runs/ca2_reviewer_workbench_current.json"
DEFAULT_CA2_DRAFT_PACKET_JSON = "runs/ca2_negative_reviewer_draft_packet_current.json"
DEFAULT_CA2_COMMIT_PACKET_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_PXR_WORKBENCH_JSON = "runs/pxr_reviewer_workbench_current.json"
DEFAULT_PXR_DRAFT_PACKET_JSON = "runs/pxr_pending_resolution_reviewer_draft_packet_current.json"
DEFAULT_PXR_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_PXR_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_PXR_CAPTURE_INTAKE_JSON = "runs/pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_PXR_EXACT_SOURCE_CONFIRMATION_JSON = "runs/pxr_exact_source_confirmation_packet_current.json"
DEFAULT_PXR_CONFLICT_RESOLVER_JSON = "runs/pxr_conflict_resolver_packet_current.json"
DEFAULT_PXR_QUANTITATIVE_PROVENANCE_JSON = "runs/pxr_quantitative_provenance_packet_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_TRANSPORTER_APPLY_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_TRANSPORTER_QUICKSTART_JSON = "runs/transporter_manual_review_quickstart_packet_current.json"
DEFAULT_TRANSPORTER_OPERATOR_CONSOLE_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_TRANSPORTER_LAUNCHBOARD_JSON = "runs/transporter_manual_review_launchboard_current.json"
DEFAULT_TRANSPORTER_DAY_PLAN_JSON = "runs/transporter_reviewer_day_plan_current.json"
DEFAULT_TRANSPORTER_NEG_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_TRANSPORTER_DONOR_BLOCKER_JSON = "runs/transporter_donor_policy_blocker_packet_current.json"
DEFAULT_TRANSPORTER_CAPTURE_SHEET_JSON = "runs/transporter_blocker_capture_sheet_current.json"
DEFAULT_TRANSPORTER_CAPTURE_INTAKE_JSON = "runs/transporter_blocker_capture_intake_current.json"
DEFAULT_AQP1_WORKBENCH_JSON = "runs/aqp1_reviewer_workbench_current.json"
DEFAULT_AQP1_FIRST_SEED_ROW_PACKET_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_AQP1_NEGATIVE_SLOT_CLOSURE_JSON = "runs/aqp1_negative_slot_closure_packet_current.json"
DEFAULT_AQP1_NEGATIVE_ACQUISITION_JSON = "runs/aqp1_negative_evidence_acquisition_packet_current.json"
DEFAULT_AQP1_NEGATIVE_CONFIRMATION_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_AQP1_NEGATIVE_SLOT_RESOLUTION_JSON = "runs/aqp1_negative_slot_resolution_packet_current.json"
DEFAULT_AQP1_NEGATIVE_CANDIDATE_FRONTIER_JSON = "runs/aqp1_negative_candidate_frontier_packet_current.json"
DEFAULT_AQP1_NEGATIVE_FRONTIER_RESOLUTION_JSON = "runs/aqp1_negative_frontier_resolution_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_JSON = "runs/aqp1_negative_primary_probe_packet_current.json"
DEFAULT_AQP1_NEGATIVE_EXACT_SOURCE_OUTCOME_JSON = "runs/aqp1_negative_exact_source_outcome_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON = "runs/aqp1_negative_primary_probe_resolution_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON = "runs/aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_EXECUTION_PACKET_JSON = "runs/transporter_seed_row_execution_packet_current.json"
DEFAULT_AQP1_SEED_ROW_FILL_DRAFT_JSON = "runs/aqp1_seed_row_fill_draft_current.json"
DEFAULT_AQP1_DRAFT_PACKET_JSON = "runs/aqp1_manual_verdict_draft_packet_current.json"
DEFAULT_AQP1_COMMIT_PACKET_JSON = "runs/aqp1_manual_verdict_commit_packet_current.json"
DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_GLUT1_WORKBENCH_JSON = "runs/glut1_reviewer_workbench_current.json"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_GLUT1_DRAFT_PACKET_JSON = "runs/glut1_manual_verdict_draft_packet_current.json"
DEFAULT_GLUT1_COMMIT_PACKET_JSON = "runs/glut1_manual_verdict_commit_packet_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_TRANSPORTER_NEGATIVE_TARGET_PACKETS_JSON = "runs/transporter_negative_evidence_target_packets_current.json"
DEFAULT_OUT_JSON = "runs/family_packet_catalog_current.json"
DEFAULT_OUT_CSV = "runs/family_packet_catalog_current.csv"
DEFAULT_OUT_MD = "runs/family_packet_catalog_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _artifact_for(path: str, payload: dict[str, Any] | None) -> str:
    return path if payload else ""


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    execution: dict[str, Any],
    operator_console: dict[str, Any],
    platform_index: dict[str, Any],
    platform_quickstart: dict[str, Any],
    pretest_sequence: dict[str, Any],
    pretest_checklist: dict[str, Any],
    run_now_packet: dict[str, Any],
    run_now_safe_command: dict[str, Any],
    idp_pretest_scope: dict[str, Any],
    idp_commercial_pretest: dict[str, Any],
    idp_broader_result: dict[str, Any],
    idp_broader_decision: dict[str, Any],
    idp_broader_review_packet: dict[str, Any],
    idp_broader_review_resolution: dict[str, Any],
    idp_broader_launch_packet: dict[str, Any],
    idp_page4_curation_packet: dict[str, Any],
    idp_page4_evidence_seed: dict[str, Any],
    idp_page4_provenance_fill: dict[str, Any],
    idp_page4_citation_confirmed: dict[str, Any],
    idp_page4_phospho_followup: dict[str, Any],
    idp_page4_phospho_fill_draft: dict[str, Any],
    idp_page4_readiness: dict[str, Any],
    idp_page4_ph_low_fill: dict[str, Any],
    idp_page4_ph_high_fill: dict[str, Any],
    idp_page4_review: dict[str, Any],
    idp_page4_decision: dict[str, Any],
    idp_page4_confirmation: dict[str, Any],
    idp_page4_confirmation_recommendation: dict[str, Any],
    idp_page4_promotion_review: dict[str, Any],
    idp_page4_confirmation_launch: dict[str, Any],
    idp_page4_confirmation_console: dict[str, Any],
    idp_page4_confirmation_workbench: dict[str, Any],
    idp_page4_confirmation_note_templates: dict[str, Any],
    idp_page4_quantitative_replacement: dict[str, Any],
    heatmap: dict[str, Any],
    commercialization_gap: dict[str, Any],
    commercial_core: dict[str, Any],
    partial_console: dict[str, Any],
    partial_operator_console: dict[str, Any],
    partial_quickstart: dict[str, Any],
    partial_reviewer_console: dict[str, Any],
    ca2_day_plan: dict[str, Any],
    pxr_day_plan: dict[str, Any],
    ca2_workbench: dict[str, Any],
    ca2_draft_packet: dict[str, Any],
    ca2_commit_packet: dict[str, Any],
    pxr_workbench: dict[str, Any],
    pxr_draft_packet: dict[str, Any],
    pxr_commit_packet: dict[str, Any],
    pxr_capture_sheet: dict[str, Any],
    pxr_capture_intake: dict[str, Any],
    pxr_exact_source_confirmation: dict[str, Any],
    pxr_quantitative_provenance: dict[str, Any],
    transporter_dashboard: dict[str, Any],
    transporter_apply_status: dict[str, Any],
    transporter_quickstart: dict[str, Any],
    transporter_operator_console: dict[str, Any],
    transporter_launchboard: dict[str, Any],
    transporter_day_plan: dict[str, Any],
    transporter_neg_day_plan: dict[str, Any],
    transporter_donor_blocker: dict[str, Any],
    transporter_capture_sheet: dict[str, Any],
    transporter_capture_intake: dict[str, Any],
    aqp1_workbench: dict[str, Any],
    aqp1_first_seed_row_packet: dict[str, Any],
    aqp1_source_confirmation: dict[str, Any],
    aqp1_negative_source_exclusion: dict[str, Any] | None,
    aqp1_negative_slot_closure: dict[str, Any] | None,
    aqp1_negative_acquisition: dict[str, Any] | None,
    transporter_seed_row_execution_packet: dict[str, Any],
    aqp1_seed_row_fill_draft: dict[str, Any],
    aqp1_draft_packet: dict[str, Any],
    aqp1_commit_packet: dict[str, Any],
    aqp1_quantitative_provenance: dict[str, Any],
    glut1_workbench: dict[str, Any],
    glut1_draft_packet: dict[str, Any],
    glut1_commit_packet: dict[str, Any],
    transporter_seed_row_board: dict[str, Any],
    transporter_negative_target_packets: dict[str, Any] | None = None,
    aqp1_negative_confirmation: dict[str, Any] | None = None,
    aqp1_negative_slot_resolution: dict[str, Any] | None = None,
    aqp1_negative_candidate_frontier: dict[str, Any] | None = None,
    aqp1_negative_frontier_resolution: dict[str, Any] | None = None,
    aqp1_negative_primary_probe: dict[str, Any] | None = None,
    aqp1_negative_exact_source_outcome: dict[str, Any] | None = None,
    aqp1_negative_primary_probe_resolution: dict[str, Any] | None = None,
    aqp1_follow_on_packet: dict[str, Any] | None = None,
    aqp1_follow_on_blocker_decomposition: dict[str, Any] | None = None,
    aqp1_follow_on_source_confirmation_packet: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation_packet: dict[str, Any] | None = None,
    transporter_placeholder_burndown_queue: dict[str, Any] | None = None,
    idp_broader_promotion_review: dict[str, Any] | None = None,
    idp_broader_promotion_resolution: dict[str, Any] | None = None,
    idp_one_wider_repeatability_packet: dict[str, Any] | None = None,
    idp_one_wider_repeatability_result: dict[str, Any] | None = None,
    pxr_conflict_resolver: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_s = dict(execution.get("summary", {}) or {})
    platform_s = dict(platform_index.get("summary", {}) or {})
    platform_quickstart_s = dict(platform_quickstart.get("summary", {}) or {})
    run_now_s = dict(run_now_packet.get("summary", {}) or {})
    run_now_safe_s = dict(run_now_safe_command.get("summary", {}) or {})
    idp_pretest_s = dict((idp_pretest_scope or {}).get("summary", {}) or {})
    idp_packet_s = dict((idp_commercial_pretest or {}).get("summary", {}) or {})
    idp_broader_result_s = dict((idp_broader_result or {}).get("summary", {}) or {})
    idp_broader_decision_s = dict((idp_broader_decision or {}).get("summary", {}) or {})
    idp_broader_promotion_review_s = dict((idp_broader_promotion_review or {}).get("summary", {}) or {})
    idp_broader_promotion_resolution_s = dict((idp_broader_promotion_resolution or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_packet_s = dict((idp_one_wider_repeatability_packet or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_result_s = dict((idp_one_wider_repeatability_result or {}).get("summary", {}) or {})
    idp_review_s = dict((idp_broader_review_packet or {}).get("summary", {}) or {})
    idp_review_resolution_s = dict((idp_broader_review_resolution or {}).get("summary", {}) or {})
    idp_launch_s = dict((idp_broader_launch_packet or {}).get("summary", {}) or {})
    idp_page4_s = dict((idp_page4_curation_packet or {}).get("summary", {}) or {})
    idp_page4_seed_s = dict((idp_page4_evidence_seed or {}).get("summary", {}) or {})
    idp_page4_fill_s = dict((idp_page4_provenance_fill or {}).get("summary", {}) or {})
    idp_page4_citation_s = dict((idp_page4_citation_confirmed or {}).get("summary", {}) or {})
    idp_page4_followup_s = dict((idp_page4_phospho_followup or {}).get("summary", {}) or {})
    idp_page4_followup_fill_s = dict((idp_page4_phospho_fill_draft or {}).get("summary", {}) or {})
    idp_page4_readiness_s = dict((idp_page4_readiness or {}).get("summary", {}) or {})
    idp_page4_ph_low_s = dict((idp_page4_ph_low_fill or {}).get("summary", {}) or {})
    idp_page4_ph_high_s = dict((idp_page4_ph_high_fill or {}).get("summary", {}) or {})
    idp_page4_review_s = dict((idp_page4_review or {}).get("summary", {}) or {})
    idp_page4_decision_s = dict((idp_page4_decision or {}).get("summary", {}) or {})
    idp_page4_confirmation_s = dict((idp_page4_confirmation or {}).get("summary", {}) or {})
    idp_page4_confirmation_recommendation_s = dict((idp_page4_confirmation_recommendation or {}).get("summary", {}) or {})
    idp_page4_promotion_review_s = dict((idp_page4_promotion_review or {}).get("summary", {}) or {})
    idp_page4_confirmation_launch_s = dict((idp_page4_confirmation_launch or {}).get("summary", {}) or {})
    idp_page4_confirmation_console_s = dict((idp_page4_confirmation_console or {}).get("summary", {}) or {})
    idp_page4_confirmation_workbench_s = dict((idp_page4_confirmation_workbench or {}).get("summary", {}) or {})
    idp_page4_confirmation_note_templates_s = dict((idp_page4_confirmation_note_templates or {}).get("summary", {}) or {})
    idp_page4_quantitative_replacement_s = dict((idp_page4_quantitative_replacement or {}).get("summary", {}) or {})
    heatmap_rows = {str(row.get("family", "")): dict(row) for row in heatmap.get("rows", []) or []}
    partial_operator_s = dict(partial_operator_console.get("summary", {}) or {})
    partial_quickstart_s = dict(partial_quickstart.get("summary", {}) or {})
    partial_reviewer_s = dict(partial_reviewer_console.get("summary", {}) or {})
    ca2_workbench_s = dict(ca2_workbench.get("summary", {}) or {})
    ca2_draft_s = dict(ca2_draft_packet.get("summary", {}) or {})
    ca2_commit_s = dict(ca2_commit_packet.get("summary", {}) or {})
    pxr_workbench_s = dict(pxr_workbench.get("summary", {}) or {})
    pxr_draft_s = dict(pxr_draft_packet.get("summary", {}) or {})
    pxr_commit_s = dict(pxr_commit_packet.get("summary", {}) or {})
    pxr_capture_sheet_s = dict((pxr_capture_sheet or {}).get("summary", {}) or {})
    pxr_capture_intake_s = dict((pxr_capture_intake or {}).get("summary", {}) or {})
    pxr_confirmation_s = dict((pxr_exact_source_confirmation or {}).get("summary", {}) or {})
    pxr_conflict_s = dict((pxr_conflict_resolver or {}).get("summary", {}) or {})
    pxr_quantitative_s = dict((pxr_quantitative_provenance or {}).get("summary", {}) or {})
    aqp1_workbench_s = dict(aqp1_workbench.get("summary", {}) or {})
    aqp1_first_seed_s = dict((aqp1_first_seed_row_packet or {}).get("summary", {}) or {})
    aqp1_source_confirmation_s = dict((aqp1_source_confirmation or {}).get("summary", {}) or {})
    aqp1_negative_source_exclusion_s = dict((aqp1_negative_source_exclusion or {}).get("summary", {}) or {})
    aqp1_negative_slot_closure_s = dict((aqp1_negative_slot_closure or {}).get("summary", {}) or {})
    aqp1_negative_acquisition_s = dict((aqp1_negative_acquisition or {}).get("summary", {}) or {})
    aqp1_negative_confirmation_s = dict((aqp1_negative_confirmation or {}).get("summary", {}) or {})
    aqp1_negative_slot_resolution_s = dict((aqp1_negative_slot_resolution or {}).get("summary", {}) or {})
    aqp1_negative_candidate_frontier_s = dict((aqp1_negative_candidate_frontier or {}).get("summary", {}) or {})
    aqp1_negative_frontier_resolution_s = dict((aqp1_negative_frontier_resolution or {}).get("summary", {}) or {})
    aqp1_negative_primary_probe_s = dict((aqp1_negative_primary_probe or {}).get("summary", {}) or {})
    aqp1_negative_exact_source_outcome_s = dict((aqp1_negative_exact_source_outcome or {}).get("summary", {}) or {})
    aqp1_negative_primary_probe_resolution_s = dict(
        (aqp1_negative_primary_probe_resolution or {}).get("summary", {}) or {}
    )
    aqp1_follow_on_s = dict((aqp1_follow_on_packet or {}).get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_s = dict((aqp1_follow_on_blocker_decomposition or {}).get("summary", {}) or {})
    aqp1_follow_on_source_confirmation_packet_s = dict(
        (aqp1_follow_on_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    transporter_placeholder_burndown_queue_s = dict(
        (transporter_placeholder_burndown_queue or {}).get("summary", {}) or {}
    )
    transporter_negative_target_packets_s = dict(
        (transporter_negative_target_packets or {}).get("summary", {}) or {}
    )
    aqp1_execution_s = dict((transporter_seed_row_execution_packet or {}).get("summary", {}) or {})
    aqp1_seed_fill_s = dict((aqp1_seed_row_fill_draft or {}).get("summary", {}) or {})
    aqp1_draft_s = dict(aqp1_draft_packet.get("summary", {}) or {})
    aqp1_commit_s = dict(aqp1_commit_packet.get("summary", {}) or {})
    aqp1_quantitative_s = dict((aqp1_quantitative_provenance or {}).get("summary", {}) or {})
    aqp1_follow_on_row_count = int(aqp1_follow_on_s.get("row_count", 0) or 0)
    aqp1_follow_on_targets = str(aqp1_follow_on_s.get("follow_on_targets", "")).strip() or "core_binder_02, core_binder_03"
    aqp1_follow_on_primary_follow_on_target = str(aqp1_follow_on_s.get("primary_follow_on_target", "")).strip() or aqp1_follow_on_targets.split(",")[0].strip()
    aqp1_follow_on_primary_focus_ligand = (
        str(aqp1_follow_on_s.get("primary_focus_ligand", "")).strip()
        or str(aqp1_quantitative_s.get("primary_focus_ligand", "")).strip()
        or str(aqp1_source_confirmation_s.get("exact_human_reference_ligand", "")).strip()
    )
    aqp1_follow_on_exact_human_guardrail_ligand = (
        str(aqp1_follow_on_s.get("exact_human_guardrail_ligand", "")).strip()
        or aqp1_follow_on_primary_focus_ligand
    )
    aqp1_follow_on_review_only_count = int(
        aqp1_follow_on_s.get("review_only_follow_on_count", aqp1_follow_on_s.get("row_count", 0)) or 0
    )
    aqp1_follow_on_blocking_signal = str(aqp1_follow_on_s.get("blocking_signal", "")).strip() or (
        f"follow_on_targets={aqp1_follow_on_targets}; "
        f"exact_human_guardrail={aqp1_follow_on_exact_human_guardrail_ligand}; "
        "authoritative_apply_allowed=False"
    )
    aqp1_follow_on_next_required_step = str(aqp1_follow_on_s.get("next_required_step", "")).strip() or (
        f"After core_binder_01, use {aqp1_follow_on_primary_follow_on_target} as the first AQP1 follow-on lane, "
        "keep replacement_reference_binding_kcal_mol blank, then continue core_binder_03 before widening to GLUT1."
        if aqp1_follow_on_row_count
        else "No AQP1 follow-on rows are available."
    )
    aqp1_follow_on_blocker_decomposition_ready = bool(aqp1_follow_on_blocker_decomposition_s)
    aqp1_follow_on_blocker_count = int(aqp1_follow_on_blocker_decomposition_s.get("blocker_row_count", 0) or 0)
    aqp1_follow_on_exact_human_nonbinding_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("exact_human_nonbinding_count", 0) or 0
    )
    aqp1_follow_on_exact_target_pair_absent_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("exact_target_pair_absent_count", 0) or 0
    )
    aqp1_follow_on_high_or_medium_potential_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("high_or_medium_potential_count", 0) or 0
    )
    aqp1_follow_on_claim_safe_kcal_ready_count = int(
        aqp1_follow_on_blocker_decomposition_s.get("claim_safe_kcal_ready_count", 0) or 0
    )
    aqp1_follow_on_source_confirmation_primary_focus_ligand = str(
        aqp1_follow_on_blocker_decomposition_s.get("source_confirmation_primary_focus_ligand", "") or ""
    ).strip()
    aqp1_follow_on_exact_human_guardrail_ligand = (
        str(aqp1_follow_on_blocker_decomposition_s.get("exact_human_guardrail_ligand", "") or "").strip()
        or aqp1_follow_on_primary_focus_ligand
    )
    aqp1_follow_on_blocking_signal = str(
        aqp1_follow_on_blocker_decomposition_s.get("blocking_signal", "") or ""
    ).strip() or (
        f"follow_on_targets={aqp1_follow_on_targets}; "
        f"exact_human_guardrail={aqp1_follow_on_exact_human_guardrail_ligand or aqp1_follow_on_primary_focus_ligand}; "
        f"exact_human_nonbinding={aqp1_follow_on_exact_human_nonbinding_count}; "
        f"exact_target_pair_absent={aqp1_follow_on_exact_target_pair_absent_count}; "
        "authoritative_apply_allowed=False"
    )
    aqp1_follow_on_next_required_step = str(
        aqp1_follow_on_blocker_decomposition_s.get("next_required_step", "") or ""
    ).strip() or (
        f"Keep {aqp1_follow_on_primary_follow_on_target} as the exact-human-activity follow-on guardrail, "
        f"hold {aqp1_follow_on_exact_human_guardrail_ligand or aqp1_follow_on_primary_focus_ligand} as the human guardrail ligand, "
        f"and defer {aqp1_follow_on_targets.split(',')[-1].strip() if ',' in aqp1_follow_on_targets else aqp1_follow_on_targets} until exact target-pair evidence is curated."
        if aqp1_follow_on_blocker_count
        else (
            f"After core_binder_01, use {aqp1_follow_on_primary_follow_on_target} as the first AQP1 follow-on lane, "
            "keep replacement_reference_binding_kcal_mol blank, then continue the remaining follow-on targets before widening to GLUT1."
            if aqp1_follow_on_row_count
            else "No AQP1 follow-on blocker decomposition rows are available."
        )
    )
    aqp1_follow_on_blocker_decomposition_artifact = str(
        aqp1_follow_on_blocker_decomposition_s.get("blocker_decomposition_artifact")
        or aqp1_follow_on_blocker_decomposition_s.get("packet_artifact")
        or (DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON if aqp1_follow_on_blocker_decomposition_ready else "")
    ).strip()
    aqp1_follow_on_blocker_follow_on_targets = str(
        aqp1_follow_on_blocker_decomposition_s.get("follow_on_targets", "") or aqp1_follow_on_targets
    ).strip()
    aqp1_follow_on_blocker_primary_focus_ligand = str(
        aqp1_follow_on_blocker_decomposition_s.get("primary_focus_ligand", "") or aqp1_follow_on_primary_focus_ligand
    ).strip()
    aqp1_follow_on_source_confirmation_packet_ready = bool(aqp1_follow_on_source_confirmation_packet_s)
    aqp1_follow_on_source_confirmation_packet_artifact = _artifact_for(
        "runs/aqp1_follow_on_source_confirmation_packet_current.md",
        aqp1_follow_on_source_confirmation_packet_s,
    )
    aqp1_follow_on_source_confirmation_packet_row_count = int(
        aqp1_follow_on_source_confirmation_packet_s.get("row_count", 0) or 0
    )
    transporter_placeholder_burndown_queue_ready = bool(transporter_placeholder_burndown_queue_s)
    transporter_placeholder_burndown_queue_artifact = _artifact_for(
        "runs/transporter_placeholder_burndown_queue_current.md",
        transporter_placeholder_burndown_queue_s,
    )
    transporter_placeholder_burndown_queue_row_count = int(
        transporter_placeholder_burndown_queue_s.get("row_count", 0) or 0
    )
    glut1_workbench_s = dict(glut1_workbench.get("summary", {}) or {})
    glut1_second_wave_source_confirmation_packet_s = dict(
        (glut1_second_wave_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    glut1_draft_s = dict(glut1_draft_packet.get("summary", {}) or {})
    glut1_commit_s = dict(glut1_commit_packet.get("summary", {}) or {})
    glut1_second_wave_source_confirmation_packet_ready = bool(glut1_second_wave_source_confirmation_packet_s)
    glut1_second_wave_source_confirmation_packet_artifact = _artifact_for(
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        glut1_second_wave_source_confirmation_packet_s,
    )
    glut1_second_wave_source_confirmation_packet_row_count = int(
        glut1_second_wave_source_confirmation_packet_s.get("row_count", 0) or 0
    )
    glut1_second_wave_source_confirmation_packet_primary_focus_ligand = str(
        glut1_second_wave_source_confirmation_packet_s.get("primary_focus_ligand", "") or ""
    ).strip()
    glut1_second_wave_source_confirmation_packet_primary_confirmation_target = str(
        glut1_second_wave_source_confirmation_packet_s.get("primary_confirmation_target", "") or ""
    ).strip()
    glut1_second_wave_source_confirmation_packet_direct_quantitative_binding_count = int(
        glut1_second_wave_source_confirmation_packet_s.get("direct_quantitative_binding_count", 0) or 0
    )
    glut1_second_wave_source_confirmation_packet_exact_target_pair_activity_count = int(
        glut1_second_wave_source_confirmation_packet_s.get("exact_target_pair_activity_count", 0) or 0
    )
    glut1_second_wave_source_confirmation_packet_structured_pair_absent_count = int(
        glut1_second_wave_source_confirmation_packet_s.get("structured_pair_absent_count", 0) or 0
    )
    glut1_second_wave_source_confirmation_packet_next_required_step = str(
        glut1_second_wave_source_confirmation_packet_s.get("next_required_step", "") or ""
    ).strip()
    transporter_seed_s = dict((transporter_seed_row_board or {}).get("summary", {}) or {})
    transporter_apply_status_s = dict((transporter_apply_status or {}).get("summary", {}) or {})
    transporter_quickstart_s = dict(transporter_quickstart.get("summary", {}) or {})
    transporter_operator_s = dict(transporter_operator_console.get("summary", {}) or {})
    transporter_launchboard_s = dict(transporter_launchboard.get("summary", {}) or {})
    transporter_capture_sheet_s = dict((transporter_capture_sheet or {}).get("summary", {}) or {})
    transporter_capture_intake_s = dict((transporter_capture_intake or {}).get("summary", {}) or {})
    transporter_launch_today = (
        transporter_launchboard_s.get("today_open_now_label")
        or transporter_launchboard_s.get("first_wave_target")
        or transporter_launchboard_s.get("today_first_target")
        or ""
    )

    pxr_signal = (
        f"review_only_{pxr_capture_sheet_s.get('review_only_candidate_count', 0)}"
        f"_deferred_{pxr_commit_s.get('must_remain_deferred_count', 0)}"
        "_keep_human_support_explicit"
    )

    rows = [
        {
            "family": "platform",
            "packet_kind": "top_level_index",
            "primary_artifact": "runs/platform_packet_index_current.md",
            "secondary_artifact": "runs/platform_operator_quickstart_packet_current.md",
            "status_signal": f"run_now={platform_s.get('run_now_count', execution_s.get('run_now_count', 0))}; prepare_next={platform_s.get('prepare_next_count', execution_s.get('prepare_next_count', 0))}; manual_review_lanes={platform_s.get('manual_review_count', execution_s.get('manual_review_only_count', 0))}; blocked={platform_quickstart_s.get('blocked_lane_count', 0)}",
        },
        {
            "family": "commercial_core",
            "packet_kind": "preservation",
            "primary_artifact": "runs/commercial_core_preservation_packet_current.md",
            "secondary_artifact": "runs/commercialization_gap_burndown_current.md",
            "status_signal": f"highest_gap_family={commercialization_gap.get('summary', {}).get('highest_gap_family', '')}",
        },
        {
            "family": "run_now",
            "packet_kind": "sanity",
            "primary_artifact": "runs/run_now_safe_command_packet_current.md",
            "secondary_artifact": "runs/run_now_family_operator_packet_current.md",
            "status_signal": f"bounded_runs={run_now_safe_s.get('run_now_family_count', run_now_safe_s.get('bounded_family_count', 0))}; noop_packets={run_now_s.get('measured_noop_packet_count', 0)}",
        },
        {
            "family": "idp",
            "packet_kind": "wider_shadow_safe_lane" if idp_broader_promotion_resolution_s else "controlled_shadow_pretest",
            "primary_artifact": (
                "runs/idp_broader_promotion_resolution_current.md"
                if idp_broader_promotion_resolution_s
                else
                "runs/idp_broader_shadow_decision_current.md"
                if idp_broader_decision_s
                else "runs/idp_commercial_pretest_decision_current.md"
            ),
            "secondary_artifact": (
                "runs/idp_one_wider_shadow_repeatability_result_current.md"
                if idp_broader_promotion_resolution_s and idp_one_wider_repeatability_result_s
                else
                "runs/idp_one_wider_shadow_repeatability_packet_current.md"
                if idp_broader_promotion_resolution_s and idp_one_wider_repeatability_packet_s
                else
                "runs/idp_broader_shadow_result_current.md"
                if idp_broader_promotion_resolution_s and idp_broader_result_s
                else
                "runs/idp_broader_promotion_review_packet_current.md"
                if idp_broader_promotion_review_s
                else
                "runs/idp_broader_shadow_result_current.md"
                if idp_broader_result_s
                else
                "runs/idp_broader_shadow_launch_packet_current.md"
                if idp_launch_s and bool(idp_review_resolution_s.get("true_broader_rerun_ready", False))
                else
                "runs/idp_broader_shadow_review_resolution_current.md"
                if idp_review_resolution_s and bool(idp_review_resolution_s.get("true_broader_rerun_ready", False))
                else
                "runs/idp_page4_quantitative_anchor_replacement_packet_current.md"
                if idp_page4_quantitative_replacement_s
                and bool(idp_page4_promotion_review_s.get("anchor_backed_candidate_ready_now", False))
                and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_manual_confirmation_console_current.md"
                if idp_page4_confirmation_console_s
                and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_manual_confirmation_launch_packet_current.md"
                if idp_page4_confirmation_launch_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_backed_promotion_review_current.md"
                if idp_page4_promotion_review_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.md"
                if idp_page4_confirmation_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_backed_candidate_decision_current.md"
                if idp_page4_decision_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_backed_candidate_review_current.md"
                if idp_page4_review_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_backed_candidate_readiness_current.md"
                if idp_page4_readiness_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_phosphorylation_fill_draft_current.md"
                if idp_page4_followup_fill_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_phosphorylation_followup_packet_current.md"
                if idp_page4_followup_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_citation_confirmed_packet_current.md"
                if idp_page4_citation_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_provenance_fill_draft_current.md"
                if idp_page4_fill_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_page4_anchor_evidence_seed_current.md"
                if idp_page4_seed_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else "runs/idp_page4_anchor_curation_packet_current.md"
                if idp_page4_s and str(idp_review_s.get("status", "")).strip() == "broader_shadow_review_packet_ready_no_true_broader_roster"
                else
                "runs/idp_broader_shadow_review_packet_current.md"
                if idp_review_s
                else "runs/idp_pretest_scope_note_current.md"
            ),
            "status_signal": (
                f"subset_safe={idp_pretest_s.get('subset_safe', False)}; "
                f"controlled_targets={idp_packet_s.get('row_count', 0)}; "
                f"watchlist={idp_packet_s.get('watchlist_target_count', 0)}; "
                f"promotion_blocked={idp_broader_decision_s.get('broader_promotion_blocked', idp_packet_s.get('broader_promotion_blocked', True))}; "
                f"review_ready={bool(idp_review_s)}; "
                f"broader_review_resolved={bool(idp_review_resolution_s)}; "
                f"true_broader_launch_ready={bool(idp_launch_s) and bool(idp_review_resolution_s.get('true_broader_rerun_ready', False))}; "
                f"broader_shadow_completed={bool(idp_broader_result_s.get('true_broader_shadow_completed', False))}; "
                f"broader_shadow_passed={bool(idp_broader_result_s.get('true_broader_shadow_passed', False))}; "
                f"promotion_review_reopen={str(idp_broader_decision_s.get('blocking_class', '')).strip() == 'explicit_promotion_decision_required'}; "
                f"promotion_review_ready={bool(idp_broader_promotion_review_s)}; "
                f"promotion_review_resolved={bool(idp_broader_promotion_resolution_s)}; "
                f"wider_lane_admitted={bool(idp_broader_promotion_resolution_s.get('wider_shadow_safe_lane_admitted', False))}; "
                f"repeatability_packet_ready={bool(idp_one_wider_repeatability_packet_s)}; "
                f"repeatability_confirmed={str(idp_one_wider_repeatability_result_s.get('status', '')).strip() == 'one_wider_shadow_repeatability_confirmed'}; "
                f"page4_ready={bool(idp_page4_s)}; "
                f"page4_seed_ready={bool(idp_page4_seed_s)}; "
                f"page4_fill_ready={bool(idp_page4_fill_s)}; "
                f"page4_citation_ready={bool(idp_page4_citation_s)}; "
                f"page4_followup_ready={bool(idp_page4_followup_s)}; "
                f"page4_followup_fill_ready={bool(idp_page4_followup_fill_s)}; "
                f"page4_readiness_ready={bool(idp_page4_readiness_s)}; "
                f"page4_fill_values_ready={bool(idp_page4_ph_low_s) and bool(idp_page4_ph_high_s)}; "
                f"page4_candidate_review_ready={bool(idp_page4_review_s)}; "
                f"page4_candidate_decision_ready={bool(idp_page4_decision_s)}; "
                f"page4_confirmation_sheet_ready={bool(idp_page4_confirmation_s)}; "
                f"page4_confirmation_recommendation_ready={bool(idp_page4_confirmation_recommendation_s)}; "
                f"page4_promotion_review_ready={bool(idp_page4_promotion_review_s)}; "
                f"page4_confirmation_console_ready={bool(idp_page4_confirmation_console_s)}; "
                f"page4_confirmation_launch_ready={bool(idp_page4_confirmation_launch_s)}; "
                f"page4_confirmation_workbench_ready={bool(idp_page4_confirmation_workbench_s)}; "
                f"page4_confirmation_note_templates_ready={bool(idp_page4_confirmation_note_templates_s)}; "
                f"page4_confirmation_pending={idp_page4_confirmation_s.get('pending_manual_confirmation_count', 0)}; "
                f"page4_candidate_ready_now={bool(idp_page4_promotion_review_s.get('anchor_backed_candidate_ready_now', False))}; "
                f"page4_quantitative_replacement_ready={bool(idp_page4_quantitative_replacement_s)}"
            ),
        },
        {
            "family": "ca2",
            "packet_kind": "evidence_closure",
            "primary_artifact": "runs/ca2_reviewer_workbench_current.md",
            "secondary_artifact": "runs/ca2_pending_burndown_console_current.md",
            "status_signal": (
                f"heat_bucket={heatmap_rows.get('non_kinase_enzyme_ca2', {}).get('heat_bucket', '')}; "
                f"closure_mode={ca2_workbench_s.get('closure_mode', 'review_only_conflict_closure')}; "
                f"today_focus={ca2_workbench_s.get('today_focus_count', 0)}; "
                f"direct_conflicts={ca2_commit_s.get('conflict_review_row_count', 0)}; "
                f"no_direct_negative={ca2_commit_s.get('no_direct_negative_source_row_count', 0)}; "
                f"authoritative_negative_closure_allowed={ca2_workbench_s.get('authoritative_negative_closure_allowed', False)}; "
                f"remaining_blank_field={ca2_commit_s.get('remaining_blank_field', 'replacement_reference_binding_kcal_mol')}; "
                f"family_ready={partial_quickstart_s.get('ca2_ready_rows', 0)}; "
                f"commit_rows={ca2_commit_s.get('commit_row_count', ca2_draft_s.get('draft_row_count', 0))}"
            ),
        },
        {
            "family": "pxr",
            "packet_kind": "evidence_closure",
            "primary_artifact": "runs/pxr_reviewer_workbench_current.md",
            "secondary_artifact": "runs/pxr_pending_burndown_console_current.md",
            "status_signal": (
                f"heat_bucket={heatmap_rows.get('nuclear_receptor_pxr', {}).get('heat_bucket', '')}; "
                f"first_hour={pxr_workbench_s.get('first_hour_count', 0)}; "
                f"family_ready={partial_quickstart_s.get('pxr_ready_rows', 0)}; "
                f"commit_rows={pxr_commit_s.get('commit_row_count', pxr_draft_s.get('reviewer_draft_row_count', 0))}; "
                f"review_only={pxr_commit_s.get('review_only_row_count', 0)}; "
                f"defer={pxr_commit_s.get('defer_row_count', 0)}; "
                f"binder_gap={pxr_commit_s.get('binder_gap_count', 0)}; "
                f"capture_sources={pxr_capture_intake_s.get('source_linked_count', pxr_capture_sheet_s.get('source_linked_count', 0))}; "
                f"supportive_human={pxr_capture_intake_s.get('supportive_target_specific_human_count', pxr_capture_sheet_s.get('supportive_target_specific_human_count', 0))}; "
                f"captured_conflict_or_gap={pxr_capture_intake_s.get('captured_conflict_or_gap_count', 0)}; "
                f"conflict_resolver_focus={pxr_conflict_s.get('row_count', 0)}; "
                f"exact_dual_mode_conflicts={pxr_conflict_s.get('exact_human_dual_mode_conflict_count', 0)}; "
                f"qhts_conflicts={pxr_conflict_s.get('direct_human_qhts_conflict_count', 0)}; "
                f"nonhuman_boundary_contexts={pxr_conflict_s.get('nonhuman_boundary_context_count', 0)}; "
                f"signal={pxr_signal}"
            ),
        },
        {
            "family": "pxr",
            "packet_kind": "exact_source_confirmation",
            "primary_artifact": "runs/pxr_exact_source_confirmation_packet_current.md",
            "secondary_artifact": "runs/family_evidence_investigator_packet_current.md",
            "status_signal": (
                f"confirmation_rows={pxr_confirmation_s.get('row_count', 0)}; "
                f"supportive_binder={pxr_confirmation_s.get('supportive_binder_confirmation_count', 0)}; "
                f"conflict_rows={pxr_confirmation_s.get('conflict_confirmation_count', 0)}; "
                f"title_direct_nonhuman={pxr_confirmation_s.get('title_direct_nonhuman_count', 0)}; "
                f"primary_focus={pxr_confirmation_s.get('primary_focus_ligand', '')}"
            ),
        },
        {
            "family": "pxr",
            "packet_kind": "conflict_resolver",
            "primary_artifact": "runs/pxr_conflict_resolver_packet_current.md",
            "secondary_artifact": "runs/family_evidence_investigator_packet_current.md",
            "status_signal": (
                f"resolver_rows={pxr_conflict_s.get('row_count', 0)}; "
                f"pubchem_conflicts={pxr_conflict_s.get('pubchem_conflict_count', 0)}; "
                f"title_direct_nonhuman_conflicts={pxr_conflict_s.get('title_direct_nonhuman_conflict_count', 0)}; "
                f"exact_dual_mode_conflicts={pxr_conflict_s.get('exact_human_dual_mode_conflict_count', 0)}; "
                f"qhts_conflicts={pxr_conflict_s.get('direct_human_qhts_conflict_count', 0)}; "
                f"nonhuman_boundary_contexts={pxr_conflict_s.get('nonhuman_boundary_context_count', 0)}; "
                f"primary_focus={pxr_conflict_s.get('primary_focus_ligand', '')}"
            ),
        },
        {
            "family": "pxr",
            "packet_kind": "quantitative_provenance",
            "primary_artifact": "runs/pxr_quantitative_provenance_packet_current.md",
            "secondary_artifact": "runs/pxr_pending_resolution_commit_packet_current.md",
            "status_signal": (
                f"trace_rows={pxr_quantitative_s.get('row_count', 0)}; "
                f"value_found={pxr_quantitative_s.get('quantitative_value_found_count', 0)}; "
                f"chembl_zero={pxr_quantitative_s.get('chembl_zero_activity_count', 0)}; "
                f"bindingdb_exact_gap={pxr_quantitative_s.get('bindingdb_exact_gap_count', 0)}; "
                f"primary_focus={pxr_quantitative_s.get('primary_focus_ligand', '')}"
            ),
        },
        {
            "family": "pxr",
            "packet_kind": "capture_sheet",
            "primary_artifact": "runs/pxr_unresolved_evidence_capture_sheet_current.md",
            "secondary_artifact": "runs/pxr_unresolved_evidence_capture_intake_current.md",
            "status_signal": (
                f"rows={pxr_capture_sheet_s.get('row_count', 0)}; "
                f"source_linked={pxr_capture_sheet_s.get('source_linked_count', 0)}; "
                f"supportive_human={pxr_capture_sheet_s.get('supportive_target_specific_human_count', 0)}; "
                f"review_only_candidates={pxr_capture_sheet_s.get('review_only_candidate_count', 0)}; "
                f"deferred_candidates={pxr_capture_sheet_s.get('deferred_candidate_count', 0)}; "
                f"captured_conflict_or_gap={pxr_capture_intake_s.get('captured_conflict_or_gap_count', 0)}; "
                f"pending_capture={pxr_capture_intake_s.get('pending_capture_count', pxr_capture_sheet_s.get('pending_capture_count', 0))}; "
                f"signal={pxr_signal}"
            ),
        },
        {
            "family": "transporter",
            "packet_kind": "blocker_closure",
            "primary_artifact": "runs/transporter_operator_console_current.md",
            "secondary_artifact": "runs/transporter_seed_row_promotion_board_current.md",
            "status_signal": (
                f"phase={transporter_dashboard.get('summary', {}).get('current_phase', 'manual_verdict_burndown')}; "
                f"seed_rows={transporter_dashboard.get('summary', {}).get('binder_seed_row_count', transporter_quickstart_s.get('binder_lane_count', 0))}; "
                f"seed_now={transporter_seed_s.get('seed_now_count', 0)}; "
                f"placeholder_rows={transporter_apply_status_s.get('placeholder_driven_rows', transporter_dashboard.get('summary', {}).get('placeholder_row_count_total', 0))}; "
                f"staged_non_authoritative={transporter_apply_status_s.get('staged_non_authoritative_rows', 0)}; "
                f"aqp1_evidence={aqp1_first_seed_s.get('evidence_mode', 'functional_potency_staged_review_only')}; "
                f"aqp1_quantitative_binding={aqp1_first_seed_s.get('quantitative_binding_status', 'quantitative_binding_absent_claim_safe_kcal_missing')}; "
                f"aqp1_exact_human_activity={aqp1_quantitative_s.get('exact_human_aqp1_activity_count', 0)}; "
                f"aqp1_provenance_focus={aqp1_quantitative_s.get('primary_focus_ligand', '')}; "
                f"aqp1_provenance_signal={aqp1_quantitative_s.get('signal', '')}; "
                f"aqp1_first_seed_unresolved={aqp1_first_seed_s.get('remaining_unresolved_fields', 'replacement_reference_binding_kcal_mol')}; "
                f"donor_reopen_ready={transporter_quickstart_s.get('donor_policy_reopen_ready', transporter_quickstart_s.get('donor_reopen_ready', False))}; "
                f"today_target={transporter_seed_s.get('today_seed_target', transporter_launch_today)}"
            ),
        },
        {
            "family": "transporter",
            "packet_kind": "capture_sheet",
            "primary_artifact": "runs/transporter_blocker_capture_sheet_current.md",
            "secondary_artifact": "runs/transporter_blocker_capture_intake_current.md",
            "status_signal": (
                f"rows={transporter_capture_sheet_s.get('row_count', 0)}; "
                f"source_linked={transporter_capture_sheet_s.get('source_linked_count', 0)}; "
                f"supportive={transporter_capture_sheet_s.get('supportive_target_specific_packet_evidence_count', 0)}; "
                f"pending_capture={transporter_capture_intake_s.get('pending_capture_count', transporter_capture_sheet_s.get('pending_capture_count', 0))}"
            ),
        },
        {
            "family": "aqp1",
            "packet_kind": "seed_row_promotion",
            "primary_artifact": "runs/aqp1_first_seed_row_packet_current.md",
            "secondary_artifact": "runs/transporter_seed_row_execution_packet_current.md",
            "status_signal": (
                f"seed_candidate={aqp1_first_seed_s.get('candidate_name', '')}; "
                f"exec_ready={bool(aqp1_execution_s)}; "
                f"safe_prefill={aqp1_seed_fill_s.get('safe_prefill_field_count', 0)}; "
                f"blocked_fields={aqp1_seed_fill_s.get('blocked_field_count', 0)}; "
                f"commit_ready={aqp1_commit_s.get('commit_ready_count', aqp1_draft_s.get('ready_for_reviewer_copy_count', 0))}; "
                f"evidence={aqp1_first_seed_s.get('evidence_mode', 'functional_potency_staged_review_only')}; "
                f"quantitative_binding={aqp1_first_seed_s.get('quantitative_binding_status', 'quantitative_binding_absent_claim_safe_kcal_missing')}; "
                f"exact_human_activity={aqp1_quantitative_s.get('exact_human_aqp1_activity_count', 0)}; "
                f"provenance_focus={aqp1_quantitative_s.get('primary_focus_ligand', '')}; "
                f"provenance_signal={aqp1_quantitative_s.get('signal', '')}; "
                f"remaining_unresolved={aqp1_first_seed_s.get('remaining_unresolved_fields', 'replacement_reference_binding_kcal_mol')}"
            ),
        },
        {
            "family": "aqp1",
            "packet_kind": "quantitative_provenance",
            "primary_artifact": "runs/aqp1_quantitative_provenance_packet_current.md",
            "secondary_artifact": "runs/aqp1_reviewer_workbench_current.md",
            "status_signal": (
                f"trace_rows={aqp1_quantitative_s.get('row_count', 0)}; "
                f"pubchem_resolved={aqp1_quantitative_s.get('pubchem_resolved_count', 0)}; "
                f"chembl_exact_match={aqp1_quantitative_s.get('chembl_exact_match_count', 0)}; "
                f"exact_human_activity={aqp1_quantitative_s.get('exact_human_aqp1_activity_count', 0)}; "
                f"claim_safe_kcal_ready={aqp1_quantitative_s.get('claim_safe_kcal_ready_count', 0)}; "
                f"primary_focus={aqp1_quantitative_s.get('primary_focus_ligand', '')}; "
                f"signal={aqp1_quantitative_s.get('signal', '')}"
            ),
        },
        {
            "family": "aqp1",
            "packet_kind": "source_confirmation",
            "primary_artifact": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
            "secondary_artifact": "runs/aqp1_first_seed_row_packet_current.md",
            "status_signal": (
                f"rows={aqp1_source_confirmation_s.get('row_count', 0)}; "
                f"primary_focus={aqp1_source_confirmation_s.get('primary_focus_ligand', '')}; "
                f"exact_human_reference={aqp1_source_confirmation_s.get('exact_human_reference_ligand', '')}; "
                f"exact_pair_absent={aqp1_source_confirmation_s.get('exact_pair_absent_count', 0)}; "
                f"exact_human_reference_count={aqp1_source_confirmation_s.get('exact_human_activity_reference_count', 0)}"
            ),
        },
        {
            "family": "aqp1",
            "packet_kind": "negative_source_exclusion",
            "primary_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
            "secondary_artifact": "runs/aqp1_negative_review_handoff_packet_current.md",
            "status_signal": (
                f"rows={aqp1_negative_source_exclusion_s.get('row_count', 0)}; "
                f"primary_focus={aqp1_negative_source_exclusion_s.get('primary_focus_ligand', '')}; "
                f"exact_target_pair_absent={aqp1_negative_source_exclusion_s.get('exact_target_pair_absent_count', 0)}; "
                f"query_error_count={aqp1_negative_source_exclusion_s.get('query_error_count', 0)}"
            ),
        },
        {
            "family": "aqp1",
            "packet_kind": "follow_on",
            "primary_artifact": "runs/aqp1_first_wave_follow_on_packet_current.md",
            "secondary_artifact": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
            "status_signal": (
                f"rows={aqp1_follow_on_row_count}; "
                f"follow_on_targets={aqp1_follow_on_targets}; "
                f"primary_follow_on_target={aqp1_follow_on_primary_follow_on_target}; "
                f"primary_focus={aqp1_follow_on_primary_focus_ligand}; "
                f"exact_human_guardrail={aqp1_follow_on_exact_human_guardrail_ligand}; "
                f"review_only_follow_on={aqp1_follow_on_review_only_count}; "
                f"signal={aqp1_follow_on_blocking_signal}"
            ),
        },
        {
            "family": "aqp1",
            "packet_kind": "follow_on_blocker_decomposition",
            "primary_artifact": "runs/aqp1_follow_on_blocker_decomposition_current.md",
            "secondary_artifact": "runs/aqp1_first_wave_follow_on_packet_current.md",
            "status_signal": (
                f"ready={aqp1_follow_on_blocker_decomposition_ready}; "
                f"blocker_row_count={aqp1_follow_on_blocker_count}; "
                f"follow_on_targets={aqp1_follow_on_blocker_follow_on_targets}; "
                f"primary_focus_ligand={aqp1_follow_on_blocker_primary_focus_ligand}; "
                f"exact_human_guardrail_ligand={aqp1_follow_on_exact_human_guardrail_ligand}; "
                f"exact_human_nonbinding_count={aqp1_follow_on_exact_human_nonbinding_count}; "
                f"exact_target_pair_absent_count={aqp1_follow_on_exact_target_pair_absent_count}; "
                f"high_or_medium_potential_count={aqp1_follow_on_high_or_medium_potential_count}; "
                f"claim_safe_kcal_ready_count={aqp1_follow_on_claim_safe_kcal_ready_count}; "
                f"source_confirmation_primary_focus_ligand={aqp1_follow_on_source_confirmation_primary_focus_ligand}; "
                f"blocking_signal={aqp1_follow_on_blocking_signal}; "
                f"next_required_step={aqp1_follow_on_next_required_step}; "
                f"artifact={aqp1_follow_on_blocker_decomposition_artifact}"
            ),
        },
        {
            "family": "glut1",
            "packet_kind": "reviewer_workbench",
            "primary_artifact": "runs/glut1_reviewer_workbench_current.md",
            "secondary_artifact": "runs/glut1_manual_verdict_staging_sheet_current.md",
            "status_signal": f"pending_manual={glut1_workbench_s.get('pending_manual_verdict_count', 0)}; commit_ready={glut1_commit_s.get('staged_confirmation_count', glut1_draft_s.get('suggested_prefill_count', 0))}",
        },
    ]
    if glut1_second_wave_source_confirmation_packet_ready:
        rows.append(
            {
                "family": "glut1",
                "packet_kind": "source_confirmation",
                "primary_artifact": glut1_second_wave_source_confirmation_packet_artifact,
                "secondary_artifact": "runs/transporter_seed_row_promotion_board_current.md",
                "status_signal": (
                    f"ready={glut1_second_wave_source_confirmation_packet_ready}; "
                    f"primary_confirmation_target={glut1_second_wave_source_confirmation_packet_primary_confirmation_target}; "
                    f"primary_focus={glut1_second_wave_source_confirmation_packet_primary_focus_ligand}; "
                    f"rows={glut1_second_wave_source_confirmation_packet_row_count}; "
                    f"direct_quantitative_binding_count={glut1_second_wave_source_confirmation_packet_direct_quantitative_binding_count}; "
                    f"exact_target_pair_activity_count={glut1_second_wave_source_confirmation_packet_exact_target_pair_activity_count}; "
                    f"structured_pair_absent_count={glut1_second_wave_source_confirmation_packet_structured_pair_absent_count}; "
                    f"next_required_step={glut1_second_wave_source_confirmation_packet_next_required_step}"
                ),
            }
        )
    if transporter_negative_target_packets_s:
        rows.append(
            {
                "family": "transporter",
                "packet_kind": "negative_target_packets",
                "primary_artifact": "runs/transporter_negative_evidence_target_packets_current.md",
                "secondary_artifact": "runs/transporter_negative_reviewer_day_plan_current.md",
                "status_signal": (
                    f"ready={bool(transporter_negative_target_packets_s)}; "
                    f"target_count={transporter_negative_target_packets_s.get('target_count', 0)}; "
                    f"top_target={transporter_negative_target_packets_s.get('top_target_id', '')}; "
                    f"top_queue_range={transporter_negative_target_packets_s.get('top_queue_rank_start', 0)}-{transporter_negative_target_packets_s.get('top_queue_rank_end', 0)}; "
                    f"aqp1_negative_slots={transporter_negative_target_packets_s.get('aqp1_negative_slot_count', 0)}; "
                    f"glut1_negative_slots={transporter_negative_target_packets_s.get('glut1_negative_slot_count', 0)}; "
                    f"glut1_source_focus={transporter_negative_target_packets_s.get('glut1_source_context_primary_focus_ligand', '')}"
                ),
            }
        )
    if aqp1_negative_slot_closure_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_slot_closure",
                "primary_artifact": aqp1_negative_slot_closure_s.get(
                    "packet_artifact", "runs/aqp1_negative_slot_closure_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_slot_closure_s)}; "
                    f"rows={aqp1_negative_slot_closure_s.get('row_count', 0)}; "
                    f"top_packet_step={aqp1_negative_slot_closure_s.get('top_packet_step', '')}; "
                    f"primary_focus={aqp1_negative_slot_closure_s.get('primary_focus_ligand', '')}; "
                    f"shared_blocker_signal_count={aqp1_negative_slot_closure_s.get('shared_blocker_signal_count', 0)}; "
                    f"exclusion_reference_row_count={aqp1_negative_slot_closure_s.get('exclusion_reference_row_count', 0)}; "
                    f"exclusion_exact_target_pair_absent_count={aqp1_negative_slot_closure_s.get('exclusion_exact_target_pair_absent_count', 0)}"
                ),
            }
        )
    if aqp1_negative_acquisition_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_evidence_acquisition",
                "primary_artifact": aqp1_negative_acquisition_s.get(
                    "packet_artifact", "runs/aqp1_negative_evidence_acquisition_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_slot_closure_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_acquisition_s)}; "
                    f"rows={aqp1_negative_acquisition_s.get('row_count', 0)}; "
                    f"primary_query={aqp1_negative_acquisition_s.get('primary_query_label', '')}; "
                    f"primary_anchor_pmid={aqp1_negative_acquisition_s.get('primary_anchor_pmid', '')}; "
                    f"exclusion_primary_focus={aqp1_negative_acquisition_s.get('exclusion_primary_focus_ligand', '')}"
                ),
            }
        )
    if aqp1_negative_confirmation_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_evidence_confirmation",
                "primary_artifact": aqp1_negative_confirmation_s.get(
                    "packet_artifact", "runs/aqp1_negative_evidence_confirmation_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_confirmation_s)}; "
                    f"rows={aqp1_negative_confirmation_s.get('row_count', 0)}; "
                    f"top_packet_step={aqp1_negative_confirmation_s.get('top_packet_step', '')}; "
                    f"primary_anchor_pmid={aqp1_negative_confirmation_s.get('primary_anchor_pmid', '')}; "
                    f"boundary_positive_pmid={aqp1_negative_confirmation_s.get('boundary_positive_pmid', '')}; "
                    f"exact_target_pair_absent_count={aqp1_negative_confirmation_s.get('exact_target_pair_absent_count', 0)}; "
                    f"decision={aqp1_negative_confirmation_s.get('confirmation_decision', '')}"
                ),
            }
        )
    if aqp1_negative_slot_resolution_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_slot_resolution",
                "primary_artifact": aqp1_negative_slot_resolution_s.get(
                    "packet_artifact", "runs/aqp1_negative_slot_resolution_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_slot_resolution_s)}; "
                    f"rows={aqp1_negative_slot_resolution_s.get('row_count', 0)}; "
                    f"top_packet_step={aqp1_negative_slot_resolution_s.get('top_packet_step', '')}; "
                    f"primary_anchor_pmid={aqp1_negative_slot_resolution_s.get('primary_anchor_pmid', '')}; "
                    f"acetazolamide_boundary_pmid={aqp1_negative_slot_resolution_s.get('acetazolamide_boundary_pmid', '')}; "
                    f"tetraethylammonium_exact_target_pair_absent_count={aqp1_negative_slot_resolution_s.get('tetraethylammonium_exact_target_pair_absent_count', 0)}; "
                    f"decision={aqp1_negative_slot_resolution_s.get('confirmation_decision', '')}"
                ),
            }
        )
    if aqp1_negative_candidate_frontier_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_candidate_frontier",
                "primary_artifact": aqp1_negative_candidate_frontier_s.get(
                    "packet_artifact", "runs/aqp1_negative_candidate_frontier_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_slot_resolution_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_candidate_frontier_s)}; "
                    f"rows={aqp1_negative_candidate_frontier_s.get('row_count', 0)}; "
                    f"exact_source_tested={aqp1_negative_candidate_frontier_s.get('exact_source_tested_row_count', 0)}; "
                    f"exact_target_pair_absent={aqp1_negative_candidate_frontier_s.get('exact_target_pair_absent_count', 0)}; "
                    f"frontier_candidate_count={aqp1_negative_candidate_frontier_s.get('frontier_candidate_count', 0)}; "
                    f"primary_frontier_candidate={aqp1_negative_candidate_frontier_s.get('primary_frontier_candidate', '')}"
                ),
            }
        )
    if aqp1_negative_frontier_resolution_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_frontier_resolution",
                "primary_artifact": aqp1_negative_frontier_resolution_s.get(
                    "packet_artifact", "runs/aqp1_negative_frontier_resolution_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_candidate_frontier_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_frontier_resolution_s)}; "
                    f"rows={aqp1_negative_frontier_resolution_s.get('row_count', 0)}; "
                    f"primary_frontier_candidate={aqp1_negative_frontier_resolution_s.get('primary_frontier_candidate', '')}; "
                    f"solvent_fallback_candidate={aqp1_negative_frontier_resolution_s.get('solvent_fallback_candidate', '')}; "
                    f"indirect_context_rows={aqp1_negative_frontier_resolution_s.get('indirect_context_row_count', 0)}; "
                    f"exact_target_pair_absent={aqp1_negative_frontier_resolution_s.get('exact_target_pair_absent_count', 0)}"
                ),
            }
        )
    if aqp1_negative_primary_probe_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_primary_probe",
                "primary_artifact": aqp1_negative_primary_probe_s.get(
                    "packet_artifact", "runs/aqp1_negative_primary_probe_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_primary_probe_s)}; "
                    f"rows={aqp1_negative_primary_probe_s.get('row_count', 0)}; "
                    f"primary_probe_candidate={aqp1_negative_primary_probe_s.get('primary_probe_candidate', '')}; "
                    f"source_anchor_pmid={aqp1_negative_primary_probe_s.get('source_anchor_pmid', '')}; "
                    f"indirect_context_pmid={aqp1_negative_primary_probe_s.get('indirect_context_pmid', '')}; "
                    f"assay_context_pmid={aqp1_negative_primary_probe_s.get('assay_context_pmid', '')}; "
                    f"exact_target_pair_absent_count={aqp1_negative_primary_probe_s.get('exact_target_pair_absent_count', 0)}"
                ),
            }
        )
    if aqp1_negative_exact_source_outcome_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_exact_source_outcome",
                "primary_artifact": aqp1_negative_exact_source_outcome_s.get(
                    "packet_artifact", "runs/aqp1_negative_exact_source_outcome_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_exact_source_outcome_s)}; "
                    f"rows={aqp1_negative_exact_source_outcome_s.get('row_count', 0)}; "
                    f"primary_negative_probe_candidate={aqp1_negative_exact_source_outcome_s.get('primary_negative_probe_candidate', '')}; "
                    f"small_inhibitor_signal_candidate={aqp1_negative_exact_source_outcome_s.get('small_inhibitor_signal_candidate', '')}; "
                    f"source_pmid={aqp1_negative_exact_source_outcome_s.get('source_pmid', '')}"
                ),
            }
        )
    if aqp1_negative_primary_probe_resolution_s:
        rows.append(
            {
                "family": "aqp1",
                "packet_kind": "negative_primary_probe_resolution",
                "primary_artifact": aqp1_negative_primary_probe_resolution_s.get(
                    "packet_artifact", "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
                ),
                "secondary_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
                "status_signal": (
                    f"ready={bool(aqp1_negative_primary_probe_resolution_s)}; "
                    f"rows={aqp1_negative_primary_probe_resolution_s.get('row_count', 0)}; "
                    f"primary_probe_candidate={aqp1_negative_primary_probe_resolution_s.get('primary_probe_candidate', '')}; "
                    f"source_anchor_pmid={aqp1_negative_primary_probe_resolution_s.get('source_anchor_pmid', '')}; "
                    f"solvent_fallback_candidate={aqp1_negative_primary_probe_resolution_s.get('solvent_fallback_candidate', '')}; "
                    f"direct_negative_quantitative_row_found_count={aqp1_negative_primary_probe_resolution_s.get('direct_negative_quantitative_row_found_count', 0)}; "
                    f"resolution_decision={aqp1_negative_primary_probe_resolution_s.get('resolution_decision', '')}"
                ),
            }
        )

    summary = {
        "catalog_row_count": len(rows),
        "top_level_packet_count": 3,
        "family_packet_count": len(rows) - 3,
        "ca2_closure_mode": ca2_workbench_s.get("closure_mode", "review_only_conflict_closure"),
        "ca2_direct_conflict_row_count": ca2_commit_s.get("conflict_review_row_count", 0),
        "ca2_no_direct_negative_source_row_count": ca2_commit_s.get("no_direct_negative_source_row_count", 0),
        "ca2_authoritative_negative_closure_allowed": ca2_workbench_s.get("authoritative_negative_closure_allowed", False),
        "ca2_remaining_blank_field": ca2_commit_s.get("remaining_blank_field", "replacement_reference_binding_kcal_mol"),
        "pxr_unresolved_row_count": pxr_capture_sheet_s.get("row_count", 0),
        "pxr_source_linked_count": pxr_capture_intake_s.get("source_linked_count", pxr_capture_sheet_s.get("source_linked_count", 0)),
        "pxr_supportive_target_specific_human_count": pxr_capture_intake_s.get("supportive_target_specific_human_count", pxr_capture_sheet_s.get("supportive_target_specific_human_count", 0)),
        "pxr_review_only_candidate_count": pxr_capture_sheet_s.get("review_only_candidate_count", 0),
        "pxr_captured_conflict_or_gap_count": pxr_capture_intake_s.get("captured_conflict_or_gap_count", 0),
        "pxr_confirm_now_count": pxr_commit_s.get("confirm_now_count", 0),
        "pxr_must_defer_count": pxr_commit_s.get("must_remain_deferred_count", 0),
        "pxr_binder_gap_count": pxr_commit_s.get("binder_gap_count", 0),
        "pxr_confirmation_focus_count": pxr_confirmation_s.get("row_count", 0),
        "pxr_confirmation_supportive_binder_count": pxr_confirmation_s.get(
            "supportive_binder_confirmation_count", 0
        ),
        "pxr_confirmation_conflict_count": pxr_confirmation_s.get("conflict_confirmation_count", 0),
        "pxr_conflict_resolver_focus_count": pxr_conflict_s.get("row_count", 0),
        "pxr_conflict_resolver_pubchem_conflict_count": pxr_conflict_s.get("pubchem_conflict_count", 0),
        "pxr_conflict_resolver_title_direct_nonhuman_conflict_count": pxr_conflict_s.get(
            "title_direct_nonhuman_conflict_count", 0
        ),
        "pxr_conflict_resolver_exact_human_dual_mode_conflict_count": pxr_conflict_s.get(
            "exact_human_dual_mode_conflict_count", 0
        ),
        "pxr_conflict_resolver_direct_human_qhts_conflict_count": pxr_conflict_s.get(
            "direct_human_qhts_conflict_count", 0
        ),
        "pxr_conflict_resolver_nonhuman_boundary_context_count": pxr_conflict_s.get(
            "nonhuman_boundary_context_count", 0
        ),
        "pxr_quantitative_provenance_focus_count": pxr_quantitative_s.get("row_count", 0),
        "pxr_quantitative_provenance_value_found_count": pxr_quantitative_s.get("quantitative_value_found_count", 0),
        "pxr_quantitative_provenance_chembl_zero_count": pxr_quantitative_s.get("chembl_zero_activity_count", 0),
        "pxr_quantitative_provenance_bindingdb_exact_gap_count": pxr_quantitative_s.get(
            "bindingdb_exact_gap_count", 0
        ),
        "aqp1_quantitative_provenance_focus_count": aqp1_quantitative_s.get("row_count", 0),
        "aqp1_quantitative_provenance_exact_human_activity_count": aqp1_quantitative_s.get(
            "exact_human_aqp1_activity_count", 0
        ),
        "aqp1_source_confirmation_focus_count": aqp1_source_confirmation_s.get("row_count", 0),
        "aqp1_source_confirmation_exact_pair_absent_count": aqp1_source_confirmation_s.get("exact_pair_absent_count", 0),
        "aqp1_source_confirmation_primary_focus_ligand": aqp1_source_confirmation_s.get("primary_focus_ligand", ""),
        "aqp1_negative_source_exclusion_ready": bool(aqp1_negative_source_exclusion_s),
        "aqp1_negative_source_exclusion_row_count": aqp1_negative_source_exclusion_s.get("row_count", 0),
        "aqp1_negative_source_exclusion_primary_focus_ligand": aqp1_negative_source_exclusion_s.get("primary_focus_ligand", ""),
        "aqp1_negative_source_exclusion_exact_target_pair_absent_count": aqp1_negative_source_exclusion_s.get(
            "exact_target_pair_absent_count", 0
        ),
        "aqp1_negative_slot_closure_ready": bool(aqp1_negative_slot_closure_s),
        "aqp1_negative_slot_closure_row_count": aqp1_negative_slot_closure_s.get("row_count", 0),
        "aqp1_negative_slot_closure_top_packet_step": aqp1_negative_slot_closure_s.get("top_packet_step", ""),
        "aqp1_negative_slot_closure_primary_focus_ligand": aqp1_negative_slot_closure_s.get(
            "primary_focus_ligand", ""
        ),
        "aqp1_negative_acquisition_ready": bool(aqp1_negative_acquisition_s),
        "aqp1_negative_acquisition_row_count": aqp1_negative_acquisition_s.get("row_count", 0),
        "aqp1_negative_acquisition_primary_query_label": aqp1_negative_acquisition_s.get(
            "primary_query_label", ""
        ),
        "aqp1_negative_acquisition_primary_anchor_pmid": aqp1_negative_acquisition_s.get(
            "primary_anchor_pmid", ""
        ),
        "aqp1_negative_confirmation_ready": bool(aqp1_negative_confirmation_s),
        "aqp1_negative_confirmation_row_count": aqp1_negative_confirmation_s.get("row_count", 0),
        "aqp1_negative_confirmation_top_packet_step": aqp1_negative_confirmation_s.get("top_packet_step", ""),
        "aqp1_negative_confirmation_primary_anchor_pmid": aqp1_negative_confirmation_s.get(
            "primary_anchor_pmid", ""
        ),
        "aqp1_negative_confirmation_boundary_positive_pmid": aqp1_negative_confirmation_s.get(
            "boundary_positive_pmid", ""
        ),
        "aqp1_negative_confirmation_decision": aqp1_negative_confirmation_s.get(
            "confirmation_decision", ""
        ),
        "aqp1_negative_slot_resolution_ready": bool(aqp1_negative_slot_resolution_s),
        "aqp1_negative_slot_resolution_row_count": aqp1_negative_slot_resolution_s.get("row_count", 0),
        "aqp1_negative_slot_resolution_top_packet_step": aqp1_negative_slot_resolution_s.get(
            "top_packet_step", ""
        ),
        "aqp1_negative_slot_resolution_primary_anchor_pmid": aqp1_negative_slot_resolution_s.get(
            "primary_anchor_pmid", ""
        ),
        "aqp1_negative_slot_resolution_acetazolamide_boundary_pmid": aqp1_negative_slot_resolution_s.get(
            "acetazolamide_boundary_pmid", ""
        ),
        "aqp1_negative_slot_resolution_tetraethylammonium_exact_target_pair_absent_count": aqp1_negative_slot_resolution_s.get(
            "tetraethylammonium_exact_target_pair_absent_count", 0
        ),
        "aqp1_negative_candidate_frontier_ready": bool(aqp1_negative_candidate_frontier_s),
        "aqp1_negative_candidate_frontier_row_count": aqp1_negative_candidate_frontier_s.get("row_count", 0),
        "aqp1_negative_candidate_frontier_exact_source_tested_row_count": aqp1_negative_candidate_frontier_s.get(
            "exact_source_tested_row_count", 0
        ),
        "aqp1_negative_candidate_frontier_exact_target_pair_absent_count": aqp1_negative_candidate_frontier_s.get(
            "exact_target_pair_absent_count", 0
        ),
        "aqp1_negative_candidate_frontier_frontier_candidate_count": aqp1_negative_candidate_frontier_s.get(
            "frontier_candidate_count", 0
        ),
        "aqp1_negative_candidate_frontier_primary_frontier_candidate": aqp1_negative_candidate_frontier_s.get(
            "primary_frontier_candidate", ""
        ),
        "aqp1_negative_frontier_resolution_ready": bool(aqp1_negative_frontier_resolution_s),
        "aqp1_negative_frontier_resolution_row_count": aqp1_negative_frontier_resolution_s.get("row_count", 0),
        "aqp1_negative_frontier_resolution_primary_frontier_candidate": aqp1_negative_frontier_resolution_s.get(
            "primary_frontier_candidate", ""
        ),
        "aqp1_negative_frontier_resolution_solvent_fallback_candidate": aqp1_negative_frontier_resolution_s.get(
            "solvent_fallback_candidate", ""
        ),
        "aqp1_negative_frontier_resolution_indirect_context_row_count": aqp1_negative_frontier_resolution_s.get(
            "indirect_context_row_count", 0
        ),
        "aqp1_negative_primary_probe_ready": bool(aqp1_negative_primary_probe_s),
        "aqp1_negative_primary_probe_row_count": aqp1_negative_primary_probe_s.get("row_count", 0),
        "aqp1_negative_primary_probe_candidate": aqp1_negative_primary_probe_s.get("primary_probe_candidate", ""),
        "aqp1_negative_primary_probe_source_anchor_pmid": aqp1_negative_primary_probe_s.get("source_anchor_pmid", ""),
        "aqp1_negative_primary_probe_indirect_context_pmid": aqp1_negative_primary_probe_s.get("indirect_context_pmid", ""),
        "aqp1_negative_exact_source_outcome_ready": bool(aqp1_negative_exact_source_outcome_s),
        "aqp1_negative_exact_source_outcome_row_count": aqp1_negative_exact_source_outcome_s.get("row_count", 0),
        "aqp1_negative_exact_source_primary_probe_candidate": aqp1_negative_exact_source_outcome_s.get(
            "primary_negative_probe_candidate", ""
        ),
        "aqp1_negative_exact_source_small_inhibitor_signal_candidate": aqp1_negative_exact_source_outcome_s.get(
            "small_inhibitor_signal_candidate", ""
        ),
        "aqp1_negative_exact_source_source_pmid": aqp1_negative_exact_source_outcome_s.get("source_pmid", ""),
        "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_negative_primary_probe_resolution_s),
        "aqp1_negative_primary_probe_resolution_row_count": aqp1_negative_primary_probe_resolution_s.get("row_count", 0),
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_negative_primary_probe_resolution_s.get(
            "primary_probe_candidate", ""
        ),
        "aqp1_negative_primary_probe_resolution_source_anchor_pmid": aqp1_negative_primary_probe_resolution_s.get(
            "source_anchor_pmid", ""
        ),
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_negative_primary_probe_resolution_s.get(
            "solvent_fallback_candidate", ""
        ),
        "aqp1_negative_primary_probe_resolution_decision": aqp1_negative_primary_probe_resolution_s.get(
            "resolution_decision", ""
        ),
        "aqp1_follow_on_row_count": aqp1_follow_on_row_count,
        "aqp1_follow_on_targets": aqp1_follow_on_targets,
        "aqp1_follow_on_primary_follow_on_target": aqp1_follow_on_primary_follow_on_target,
        "aqp1_follow_on_primary_focus_ligand": aqp1_follow_on_primary_focus_ligand,
        "aqp1_follow_on_exact_human_guardrail_ligand": aqp1_follow_on_exact_human_guardrail_ligand,
        "aqp1_follow_on_review_only_follow_on_count": aqp1_follow_on_review_only_count,
        "aqp1_follow_on_blocking_signal": aqp1_follow_on_blocking_signal,
        "aqp1_follow_on_next_required_step": aqp1_follow_on_next_required_step,
        "aqp1_follow_on_blocker_decomposition_ready": aqp1_follow_on_blocker_decomposition_ready,
        "aqp1_follow_on_blocker_count": aqp1_follow_on_blocker_count,
        "aqp1_follow_on_exact_human_nonbinding_count": aqp1_follow_on_exact_human_nonbinding_count,
        "aqp1_follow_on_exact_target_pair_absent_count": aqp1_follow_on_exact_target_pair_absent_count,
        "aqp1_follow_on_high_or_medium_potential_count": aqp1_follow_on_high_or_medium_potential_count,
        "aqp1_follow_on_claim_safe_kcal_ready_count": aqp1_follow_on_claim_safe_kcal_ready_count,
        "aqp1_follow_on_source_confirmation_primary_focus_ligand": aqp1_follow_on_source_confirmation_primary_focus_ligand,
        "aqp1_follow_on_exact_human_guardrail_ligand": aqp1_follow_on_exact_human_guardrail_ligand,
        "aqp1_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
        "aqp1_follow_on_source_confirmation_packet_ready": aqp1_follow_on_source_confirmation_packet_ready,
        "aqp1_follow_on_source_confirmation_packet_artifact": aqp1_follow_on_source_confirmation_packet_artifact,
        "aqp1_follow_on_source_confirmation_packet_row_count": aqp1_follow_on_source_confirmation_packet_row_count,
        "glut1_second_wave_source_confirmation_packet_ready": glut1_second_wave_source_confirmation_packet_ready,
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_second_wave_source_confirmation_packet_artifact,
        "glut1_second_wave_source_confirmation_packet_row_count": glut1_second_wave_source_confirmation_packet_row_count,
        "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": glut1_second_wave_source_confirmation_packet_primary_focus_ligand,
        "glut1_second_wave_source_confirmation_packet_primary_confirmation_target": glut1_second_wave_source_confirmation_packet_primary_confirmation_target,
        "glut1_second_wave_source_confirmation_packet_direct_quantitative_binding_count": glut1_second_wave_source_confirmation_packet_direct_quantitative_binding_count,
        "glut1_second_wave_source_confirmation_packet_exact_target_pair_activity_count": glut1_second_wave_source_confirmation_packet_exact_target_pair_activity_count,
        "glut1_second_wave_source_confirmation_packet_structured_pair_absent_count": glut1_second_wave_source_confirmation_packet_structured_pair_absent_count,
        "glut1_second_wave_source_confirmation_packet_next_required_step": glut1_second_wave_source_confirmation_packet_next_required_step,
        "transporter_placeholder_burndown_queue_ready": transporter_placeholder_burndown_queue_ready,
        "transporter_placeholder_burndown_queue_artifact": transporter_placeholder_burndown_queue_artifact,
        "transporter_placeholder_burndown_queue_row_count": transporter_placeholder_burndown_queue_row_count,
        "transporter_negative_target_packets_ready": bool(transporter_negative_target_packets_s),
        "transporter_negative_target_packets_target_count": transporter_negative_target_packets_s.get("target_count", 0),
        "transporter_negative_target_packets_top_target_id": transporter_negative_target_packets_s.get("top_target_id", ""),
        "transporter_negative_target_packets_top_queue_rank_start": transporter_negative_target_packets_s.get("top_queue_rank_start", 0),
        "transporter_negative_target_packets_top_queue_rank_end": transporter_negative_target_packets_s.get("top_queue_rank_end", 0),
        "transporter_negative_target_packets_aqp1_negative_slot_count": transporter_negative_target_packets_s.get(
            "aqp1_negative_slot_count", 0
        ),
        "transporter_negative_target_packets_glut1_negative_slot_count": transporter_negative_target_packets_s.get(
            "glut1_negative_slot_count", 0
        ),
        "aqp1_quantitative_provenance_claim_safe_kcal_ready_count": aqp1_quantitative_s.get(
            "claim_safe_kcal_ready_count", 0
        ),
        "aqp1_quantitative_provenance_primary_focus_ligand": aqp1_quantitative_s.get(
            "primary_focus_ligand", ""
        ),
        "aqp1_quantitative_provenance_signal": aqp1_quantitative_s.get("signal", ""),
        "pxr_signal": pxr_signal,
        "next_required_step": "Open the primary artifact for the family you are touching first, then use the secondary artifact as the guardrail/checklist companion.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Packet Catalog",
        "",
        f"- catalog_row_count: `{s['catalog_row_count']}`",
        f"- top_level_packet_count: `{s['top_level_packet_count']}`",
        f"- family_packet_count: `{s['family_packet_count']}`",
        f"- ca2_closure_mode: `{s['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_no_direct_negative_source_row_count: `{s['ca2_no_direct_negative_source_row_count']}`",
        f"- ca2_authoritative_negative_closure_allowed: `{s['ca2_authoritative_negative_closure_allowed']}`",
        f"- ca2_remaining_blank_field: `{s['ca2_remaining_blank_field']}`",
        f"- pxr_unresolved_row_count: `{s['pxr_unresolved_row_count']}`",
        f"- pxr_source_linked_count: `{s['pxr_source_linked_count']}`",
        f"- pxr_supportive_target_specific_human_count: `{s['pxr_supportive_target_specific_human_count']}`",
        f"- pxr_review_only_candidate_count: `{s['pxr_review_only_candidate_count']}`",
        f"- pxr_captured_conflict_or_gap_count: `{s['pxr_captured_conflict_or_gap_count']}`",
        f"- pxr_confirm_now_count: `{s['pxr_confirm_now_count']}`",
        f"- pxr_must_defer_count: `{s['pxr_must_defer_count']}`",
        f"- pxr_binder_gap_count: `{s['pxr_binder_gap_count']}`",
        f"- pxr_confirmation_focus_count: `{s['pxr_confirmation_focus_count']}`",
        f"- pxr_confirmation_supportive_binder_count: `{s['pxr_confirmation_supportive_binder_count']}`",
        f"- pxr_confirmation_conflict_count: `{s['pxr_confirmation_conflict_count']}`",
        f"- pxr_conflict_resolver_focus_count: `{s['pxr_conflict_resolver_focus_count']}`",
        f"- pxr_conflict_resolver_pubchem_conflict_count: `{s['pxr_conflict_resolver_pubchem_conflict_count']}`",
        f"- pxr_conflict_resolver_title_direct_nonhuman_conflict_count: `{s['pxr_conflict_resolver_title_direct_nonhuman_conflict_count']}`",
        f"- pxr_conflict_resolver_exact_human_dual_mode_conflict_count: `{s['pxr_conflict_resolver_exact_human_dual_mode_conflict_count']}`",
        f"- pxr_conflict_resolver_direct_human_qhts_conflict_count: `{s['pxr_conflict_resolver_direct_human_qhts_conflict_count']}`",
        f"- pxr_conflict_resolver_nonhuman_boundary_context_count: `{s['pxr_conflict_resolver_nonhuman_boundary_context_count']}`",
        f"- pxr_quantitative_provenance_focus_count: `{s['pxr_quantitative_provenance_focus_count']}`",
        f"- pxr_quantitative_provenance_value_found_count: `{s['pxr_quantitative_provenance_value_found_count']}`",
        f"- pxr_quantitative_provenance_chembl_zero_count: `{s['pxr_quantitative_provenance_chembl_zero_count']}`",
        f"- pxr_quantitative_provenance_bindingdb_exact_gap_count: `{s['pxr_quantitative_provenance_bindingdb_exact_gap_count']}`",
        f"- aqp1_quantitative_provenance_focus_count: `{s['aqp1_quantitative_provenance_focus_count']}`",
        f"- aqp1_quantitative_provenance_exact_human_activity_count: `{s['aqp1_quantitative_provenance_exact_human_activity_count']}`",
        f"- aqp1_source_confirmation_focus_count: `{s['aqp1_source_confirmation_focus_count']}`",
        f"- aqp1_source_confirmation_exact_pair_absent_count: `{s['aqp1_source_confirmation_exact_pair_absent_count']}`",
        f"- aqp1_source_confirmation_primary_focus_ligand: `{s['aqp1_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_negative_source_exclusion_ready: `{s['aqp1_negative_source_exclusion_ready']}`",
        f"- aqp1_negative_source_exclusion_row_count: `{s['aqp1_negative_source_exclusion_row_count']}`",
        f"- aqp1_negative_source_exclusion_primary_focus_ligand: `{s['aqp1_negative_source_exclusion_primary_focus_ligand']}`",
        f"- aqp1_negative_source_exclusion_exact_target_pair_absent_count: `{s['aqp1_negative_source_exclusion_exact_target_pair_absent_count']}`",
        f"- aqp1_negative_slot_closure_ready: `{s['aqp1_negative_slot_closure_ready']}`",
        f"- aqp1_negative_slot_closure_row_count: `{s['aqp1_negative_slot_closure_row_count']}`",
        f"- aqp1_negative_slot_closure_top_packet_step: `{s['aqp1_negative_slot_closure_top_packet_step']}`",
        f"- aqp1_negative_slot_closure_primary_focus_ligand: `{s['aqp1_negative_slot_closure_primary_focus_ligand']}`",
        f"- aqp1_negative_acquisition_ready: `{s['aqp1_negative_acquisition_ready']}`",
        f"- aqp1_negative_acquisition_row_count: `{s['aqp1_negative_acquisition_row_count']}`",
        f"- aqp1_negative_acquisition_primary_query_label: `{s['aqp1_negative_acquisition_primary_query_label']}`",
        f"- aqp1_negative_acquisition_primary_anchor_pmid: `{s['aqp1_negative_acquisition_primary_anchor_pmid']}`",
        f"- aqp1_negative_confirmation_ready: `{s['aqp1_negative_confirmation_ready']}`",
        f"- aqp1_negative_confirmation_row_count: `{s['aqp1_negative_confirmation_row_count']}`",
        f"- aqp1_negative_confirmation_top_packet_step: `{s['aqp1_negative_confirmation_top_packet_step']}`",
        f"- aqp1_negative_confirmation_primary_anchor_pmid: `{s['aqp1_negative_confirmation_primary_anchor_pmid']}`",
        f"- aqp1_negative_confirmation_boundary_positive_pmid: `{s['aqp1_negative_confirmation_boundary_positive_pmid']}`",
        f"- aqp1_negative_confirmation_decision: `{s['aqp1_negative_confirmation_decision']}`",
        f"- aqp1_negative_slot_resolution_ready: `{s['aqp1_negative_slot_resolution_ready']}`",
        f"- aqp1_negative_slot_resolution_row_count: `{s['aqp1_negative_slot_resolution_row_count']}`",
        f"- aqp1_negative_slot_resolution_top_packet_step: `{s['aqp1_negative_slot_resolution_top_packet_step']}`",
        f"- aqp1_negative_slot_resolution_primary_anchor_pmid: `{s['aqp1_negative_slot_resolution_primary_anchor_pmid']}`",
        f"- aqp1_negative_slot_resolution_acetazolamide_boundary_pmid: `{s['aqp1_negative_slot_resolution_acetazolamide_boundary_pmid']}`",
        f"- aqp1_negative_slot_resolution_tetraethylammonium_exact_target_pair_absent_count: `{s['aqp1_negative_slot_resolution_tetraethylammonium_exact_target_pair_absent_count']}`",
        f"- aqp1_negative_candidate_frontier_ready: `{s['aqp1_negative_candidate_frontier_ready']}`",
        f"- aqp1_negative_candidate_frontier_row_count: `{s['aqp1_negative_candidate_frontier_row_count']}`",
        f"- aqp1_negative_candidate_frontier_exact_source_tested_row_count: `{s['aqp1_negative_candidate_frontier_exact_source_tested_row_count']}`",
        f"- aqp1_negative_candidate_frontier_exact_target_pair_absent_count: `{s['aqp1_negative_candidate_frontier_exact_target_pair_absent_count']}`",
        f"- aqp1_negative_candidate_frontier_frontier_candidate_count: `{s['aqp1_negative_candidate_frontier_frontier_candidate_count']}`",
        f"- aqp1_negative_candidate_frontier_primary_frontier_candidate: `{s['aqp1_negative_candidate_frontier_primary_frontier_candidate']}`",
        f"- aqp1_negative_frontier_resolution_ready: `{s['aqp1_negative_frontier_resolution_ready']}`",
        f"- aqp1_negative_frontier_resolution_row_count: `{s['aqp1_negative_frontier_resolution_row_count']}`",
        f"- aqp1_negative_frontier_resolution_primary_frontier_candidate: `{s['aqp1_negative_frontier_resolution_primary_frontier_candidate']}`",
        f"- aqp1_negative_frontier_resolution_solvent_fallback_candidate: `{s['aqp1_negative_frontier_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_frontier_resolution_indirect_context_row_count: `{s['aqp1_negative_frontier_resolution_indirect_context_row_count']}`",
        f"- aqp1_negative_primary_probe_ready: `{s['aqp1_negative_primary_probe_ready']}`",
        f"- aqp1_negative_primary_probe_row_count: `{s['aqp1_negative_primary_probe_row_count']}`",
        f"- aqp1_negative_primary_probe_candidate: `{s['aqp1_negative_primary_probe_candidate']}`",
        f"- aqp1_negative_primary_probe_source_anchor_pmid: `{s['aqp1_negative_primary_probe_source_anchor_pmid']}`",
        f"- aqp1_negative_primary_probe_indirect_context_pmid: `{s['aqp1_negative_primary_probe_indirect_context_pmid']}`",
        f"- aqp1_negative_exact_source_outcome_ready: `{s['aqp1_negative_exact_source_outcome_ready']}`",
        f"- aqp1_negative_exact_source_outcome_row_count: `{s['aqp1_negative_exact_source_outcome_row_count']}`",
        f"- aqp1_negative_exact_source_primary_probe_candidate: `{s['aqp1_negative_exact_source_primary_probe_candidate']}`",
        f"- aqp1_negative_exact_source_small_inhibitor_signal_candidate: `{s['aqp1_negative_exact_source_small_inhibitor_signal_candidate']}`",
        f"- aqp1_negative_exact_source_source_pmid: `{s['aqp1_negative_exact_source_source_pmid']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_row_count: `{s['aqp1_negative_primary_probe_resolution_row_count']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_source_anchor_pmid: `{s['aqp1_negative_primary_probe_resolution_source_anchor_pmid']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_follow_on_row_count: `{s['aqp1_follow_on_row_count']}`",
        f"- aqp1_follow_on_targets: `{s['aqp1_follow_on_targets']}`",
        f"- aqp1_follow_on_primary_follow_on_target: `{s['aqp1_follow_on_primary_follow_on_target']}`",
        f"- aqp1_follow_on_primary_focus_ligand: `{s['aqp1_follow_on_primary_focus_ligand']}`",
        f"- aqp1_follow_on_exact_human_guardrail_ligand: `{s['aqp1_follow_on_exact_human_guardrail_ligand']}`",
        f"- aqp1_follow_on_review_only_follow_on_count: `{s['aqp1_follow_on_review_only_follow_on_count']}`",
        f"- aqp1_follow_on_blocking_signal: `{s['aqp1_follow_on_blocking_signal']}`",
        f"- aqp1_follow_on_next_required_step: `{s['aqp1_follow_on_next_required_step']}`",
        f"- aqp1_follow_on_blocker_decomposition_ready: `{s['aqp1_follow_on_blocker_decomposition_ready']}`",
        f"- aqp1_follow_on_blocker_count: `{s['aqp1_follow_on_blocker_count']}`",
        f"- aqp1_follow_on_exact_human_nonbinding_count: `{s['aqp1_follow_on_exact_human_nonbinding_count']}`",
        f"- aqp1_follow_on_exact_target_pair_absent_count: `{s['aqp1_follow_on_exact_target_pair_absent_count']}`",
        f"- aqp1_follow_on_high_or_medium_potential_count: `{s['aqp1_follow_on_high_or_medium_potential_count']}`",
        f"- aqp1_follow_on_claim_safe_kcal_ready_count: `{s['aqp1_follow_on_claim_safe_kcal_ready_count']}`",
        f"- aqp1_follow_on_source_confirmation_primary_focus_ligand: `{s['aqp1_follow_on_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_follow_on_exact_human_guardrail_ligand: `{s['aqp1_follow_on_exact_human_guardrail_ligand']}`",
        f"- aqp1_follow_on_blocker_decomposition_artifact: `{s['aqp1_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_ready: `{s['aqp1_follow_on_source_confirmation_packet_ready']}`",
        f"- aqp1_follow_on_source_confirmation_packet_artifact: `{s['aqp1_follow_on_source_confirmation_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_row_count: `{s['aqp1_follow_on_source_confirmation_packet_row_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_ready: `{s['glut1_second_wave_source_confirmation_packet_ready']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{s['glut1_second_wave_source_confirmation_packet_artifact']}`",
        f"- glut1_second_wave_source_confirmation_packet_row_count: `{s['glut1_second_wave_source_confirmation_packet_row_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_packet_primary_focus_ligand']}`",
        f"- glut1_second_wave_source_confirmation_packet_primary_confirmation_target: `{s['glut1_second_wave_source_confirmation_packet_primary_confirmation_target']}`",
        f"- glut1_second_wave_source_confirmation_packet_direct_quantitative_binding_count: `{s['glut1_second_wave_source_confirmation_packet_direct_quantitative_binding_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_exact_target_pair_activity_count: `{s['glut1_second_wave_source_confirmation_packet_exact_target_pair_activity_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_structured_pair_absent_count: `{s['glut1_second_wave_source_confirmation_packet_structured_pair_absent_count']}`",
        f"- glut1_second_wave_source_confirmation_packet_next_required_step: `{s['glut1_second_wave_source_confirmation_packet_next_required_step']}`",
        f"- transporter_placeholder_burndown_queue_ready: `{s['transporter_placeholder_burndown_queue_ready']}`",
        f"- transporter_placeholder_burndown_queue_artifact: `{s['transporter_placeholder_burndown_queue_artifact']}`",
        f"- transporter_placeholder_burndown_queue_row_count: `{s['transporter_placeholder_burndown_queue_row_count']}`",
        f"- transporter_negative_target_packets_ready: `{s['transporter_negative_target_packets_ready']}`",
        f"- transporter_negative_target_packets_target_count: `{s['transporter_negative_target_packets_target_count']}`",
        f"- transporter_negative_target_packets_top_target_id: `{s['transporter_negative_target_packets_top_target_id']}`",
        f"- transporter_negative_target_packets_top_queue_range: `{s['transporter_negative_target_packets_top_queue_rank_start']}-{s['transporter_negative_target_packets_top_queue_rank_end']}`",
        f"- transporter_negative_target_packets_aqp1_negative_slot_count: `{s['transporter_negative_target_packets_aqp1_negative_slot_count']}`",
        f"- transporter_negative_target_packets_glut1_negative_slot_count: `{s['transporter_negative_target_packets_glut1_negative_slot_count']}`",
        f"- aqp1_quantitative_provenance_claim_safe_kcal_ready_count: `{s['aqp1_quantitative_provenance_claim_safe_kcal_ready_count']}`",
        f"- aqp1_quantitative_provenance_primary_focus_ligand: `{s['aqp1_quantitative_provenance_primary_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal']}`",
        f"- pxr_signal: `{s['pxr_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Catalog",
        "",
        "| family | packet_kind | primary_artifact | secondary_artifact | status_signal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['packet_kind']}` | `{row['primary_artifact']}` | `{row['secondary_artifact']}` | `{row['status_signal']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a lightweight catalog of the current family/operator packets.")
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
    parser.add_argument("--operator-console-json", default=DEFAULT_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--platform-index-json", default=DEFAULT_PLATFORM_INDEX_JSON)
    parser.add_argument("--platform-quickstart-json", default=DEFAULT_PLATFORM_QUICKSTART_JSON)
    parser.add_argument("--pretest-sequence-json", default=DEFAULT_PRETEST_SEQUENCE_JSON)
    parser.add_argument("--pretest-checklist-json", default=DEFAULT_PRETEST_CHECKLIST_JSON)
    parser.add_argument("--run-now-packet-json", default=DEFAULT_RUN_NOW_PACKET_JSON)
    parser.add_argument("--run-now-safe-command-json", default=DEFAULT_RUN_NOW_SAFE_COMMAND_JSON)
    parser.add_argument("--idp-pretest-scope-json", default=DEFAULT_IDP_PRETEST_SCOPE_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-broader-result-json", default=DEFAULT_IDP_BROADER_RESULT_JSON)
    parser.add_argument("--idp-broader-decision-json", default=DEFAULT_IDP_BROADER_DECISION_JSON)
    parser.add_argument("--idp-broader-promotion-review-json", default=DEFAULT_IDP_BROADER_PROMOTION_REVIEW_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--idp-one-wider-repeatability-packet-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON)
    parser.add_argument("--idp-one-wider-repeatability-result-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON)
    parser.add_argument("--idp-broader-review-packet-json", default=DEFAULT_IDP_BROADER_REVIEW_PACKET_JSON)
    parser.add_argument("--idp-broader-review-resolution-json", default=DEFAULT_IDP_BROADER_REVIEW_RESOLUTION_JSON)
    parser.add_argument("--idp-broader-launch-packet-json", default=DEFAULT_IDP_BROADER_LAUNCH_PACKET_JSON)
    parser.add_argument("--idp-page4-curation-packet-json", default=DEFAULT_IDP_PAGE4_CURATION_PACKET_JSON)
    parser.add_argument("--idp-page4-evidence-seed-json", default=DEFAULT_IDP_PAGE4_EVIDENCE_SEED_JSON)
    parser.add_argument("--idp-page4-provenance-fill-json", default=DEFAULT_IDP_PAGE4_PROVENANCE_FILL_JSON)
    parser.add_argument("--idp-page4-citation-confirmed-json", default=DEFAULT_IDP_PAGE4_CITATION_CONFIRMED_JSON)
    parser.add_argument("--idp-page4-phospho-followup-json", default=DEFAULT_IDP_PAGE4_PHOSPHO_FOLLOWUP_JSON)
    parser.add_argument("--idp-page4-phospho-fill-draft-json", default=DEFAULT_IDP_PAGE4_PHOSPHO_FILL_DRAFT_JSON)
    parser.add_argument("--idp-page4-readiness-json", default=DEFAULT_IDP_PAGE4_READINESS_JSON)
    parser.add_argument("--idp-page4-ph-low-fill-json", default=DEFAULT_IDP_PAGE4_PH_LOW_FILL_JSON)
    parser.add_argument("--idp-page4-ph-high-fill-json", default=DEFAULT_IDP_PAGE4_PH_HIGH_FILL_JSON)
    parser.add_argument("--idp-page4-review-json", default=DEFAULT_IDP_PAGE4_REVIEW_JSON)
    parser.add_argument("--idp-page4-decision-json", default=DEFAULT_IDP_PAGE4_DECISION_JSON)
    parser.add_argument("--idp-page4-confirmation-json", default=DEFAULT_IDP_PAGE4_CONFIRMATION_JSON)
    parser.add_argument("--idp-page4-confirmation-recommendation-json", default=DEFAULT_IDP_PAGE4_CONFIRMATION_RECOMMENDATION_JSON)
    parser.add_argument("--idp-page4-promotion-review-json", default=DEFAULT_IDP_PAGE4_PROMOTION_REVIEW_JSON)
    parser.add_argument("--idp-page4-confirmation-launch-json", default=DEFAULT_IDP_PAGE4_CONFIRMATION_LAUNCH_JSON)
    parser.add_argument("--idp-page4-confirmation-console-json", default=DEFAULT_IDP_PAGE4_CONFIRMATION_CONSOLE_JSON)
    parser.add_argument("--idp-page4-confirmation-workbench-json", default=DEFAULT_IDP_PAGE4_CONFIRMATION_WORKBENCH_JSON)
    parser.add_argument("--idp-page4-confirmation-note-templates-json", default=DEFAULT_IDP_PAGE4_CONFIRMATION_NOTE_TEMPLATES_JSON)
    parser.add_argument("--idp-page4-quantitative-replacement-json", default=DEFAULT_IDP_PAGE4_QUANTITATIVE_REPLACEMENT_JSON)
    parser.add_argument("--heatmap-json", default=DEFAULT_HEATMAP_JSON)
    parser.add_argument("--commercialization-gap-json", default=DEFAULT_COMMERCIALIZATION_GAP_JSON)
    parser.add_argument("--commercial-core-json", default=DEFAULT_COMMERCIAL_CORE_JSON)
    parser.add_argument("--partial-console-json", default=DEFAULT_PARTIAL_CONSOLE_JSON)
    parser.add_argument("--partial-operator-console-json", default=DEFAULT_PARTIAL_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--partial-quickstart-json", default=DEFAULT_PARTIAL_QUICKSTART_JSON)
    parser.add_argument("--partial-reviewer-console-json", default=DEFAULT_PARTIAL_REVIEWER_CONSOLE_JSON)
    parser.add_argument("--ca2-day-plan-json", default=DEFAULT_CA2_DAY_PLAN_JSON)
    parser.add_argument("--pxr-day-plan-json", default=DEFAULT_PXR_DAY_PLAN_JSON)
    parser.add_argument("--ca2-workbench-json", default=DEFAULT_CA2_WORKBENCH_JSON)
    parser.add_argument("--ca2-draft-packet-json", default=DEFAULT_CA2_DRAFT_PACKET_JSON)
    parser.add_argument("--ca2-commit-packet-json", default=DEFAULT_CA2_COMMIT_PACKET_JSON)
    parser.add_argument("--pxr-workbench-json", default=DEFAULT_PXR_WORKBENCH_JSON)
    parser.add_argument("--pxr-draft-packet-json", default=DEFAULT_PXR_DRAFT_PACKET_JSON)
    parser.add_argument("--pxr-commit-packet-json", default=DEFAULT_PXR_COMMIT_PACKET_JSON)
    parser.add_argument("--pxr-capture-sheet-json", default=DEFAULT_PXR_CAPTURE_SHEET_JSON)
    parser.add_argument("--pxr-capture-intake-json", default=DEFAULT_PXR_CAPTURE_INTAKE_JSON)
    parser.add_argument("--pxr-exact-source-confirmation-json", default=DEFAULT_PXR_EXACT_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--pxr-conflict-resolver-json", default=DEFAULT_PXR_CONFLICT_RESOLVER_JSON)
    parser.add_argument("--pxr-quantitative-provenance-json", default=DEFAULT_PXR_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--transporter-apply-status-json", default=DEFAULT_TRANSPORTER_APPLY_STATUS_JSON)
    parser.add_argument("--transporter-quickstart-json", default=DEFAULT_TRANSPORTER_QUICKSTART_JSON)
    parser.add_argument("--transporter-operator-console-json", default=DEFAULT_TRANSPORTER_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--transporter-launchboard-json", default=DEFAULT_TRANSPORTER_LAUNCHBOARD_JSON)
    parser.add_argument("--transporter-day-plan-json", default=DEFAULT_TRANSPORTER_DAY_PLAN_JSON)
    parser.add_argument("--transporter-neg-day-plan-json", default=DEFAULT_TRANSPORTER_NEG_DAY_PLAN_JSON)
    parser.add_argument("--transporter-donor-blocker-json", default=DEFAULT_TRANSPORTER_DONOR_BLOCKER_JSON)
    parser.add_argument("--transporter-capture-sheet-json", default=DEFAULT_TRANSPORTER_CAPTURE_SHEET_JSON)
    parser.add_argument("--transporter-capture-intake-json", default=DEFAULT_TRANSPORTER_CAPTURE_INTAKE_JSON)
    parser.add_argument("--aqp1-workbench-json", default=DEFAULT_AQP1_WORKBENCH_JSON)
    parser.add_argument("--aqp1-first-seed-row-packet-json", default=DEFAULT_AQP1_FIRST_SEED_ROW_PACKET_JSON)
    parser.add_argument("--aqp1-source-confirmation-json", default=DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--aqp1-negative-source-exclusion-json", default=DEFAULT_AQP1_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--aqp1-negative-slot-closure-json", default=DEFAULT_AQP1_NEGATIVE_SLOT_CLOSURE_JSON)
    parser.add_argument("--aqp1-negative-acquisition-json", default=DEFAULT_AQP1_NEGATIVE_ACQUISITION_JSON)
    parser.add_argument("--aqp1-negative-confirmation-json", default=DEFAULT_AQP1_NEGATIVE_CONFIRMATION_JSON)
    parser.add_argument("--aqp1-negative-slot-resolution-json", default=DEFAULT_AQP1_NEGATIVE_SLOT_RESOLUTION_JSON)
    parser.add_argument("--aqp1-negative-candidate-frontier-json", default=DEFAULT_AQP1_NEGATIVE_CANDIDATE_FRONTIER_JSON)
    parser.add_argument("--aqp1-negative-frontier-resolution-json", default=DEFAULT_AQP1_NEGATIVE_FRONTIER_RESOLUTION_JSON)
    parser.add_argument("--aqp1-negative-primary-probe-json", default=DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_JSON)
    parser.add_argument(
        "--aqp1-negative-exact-source-outcome-json",
        default=DEFAULT_AQP1_NEGATIVE_EXACT_SOURCE_OUTCOME_JSON,
    )
    parser.add_argument(
        "--aqp1-negative-primary-probe-resolution-json",
        default=DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON,
    )
    parser.add_argument("--aqp1-follow-on-packet-json", default=DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON)
    parser.add_argument(
        "--aqp1-follow-on-blocker-decomposition-json",
        default=DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON,
    )
    parser.add_argument(
        "--aqp1-follow-on-source-confirmation-packet-json",
        default=DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument("--transporter-seed-row-execution-packet-json", default=DEFAULT_TRANSPORTER_SEED_ROW_EXECUTION_PACKET_JSON)
    parser.add_argument("--aqp1-seed-row-fill-draft-json", default=DEFAULT_AQP1_SEED_ROW_FILL_DRAFT_JSON)
    parser.add_argument("--aqp1-draft-packet-json", default=DEFAULT_AQP1_DRAFT_PACKET_JSON)
    parser.add_argument("--aqp1-commit-packet-json", default=DEFAULT_AQP1_COMMIT_PACKET_JSON)
    parser.add_argument("--aqp1-quantitative-provenance-json", default=DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--glut1-workbench-json", default=DEFAULT_GLUT1_WORKBENCH_JSON)
    parser.add_argument(
        "--glut1-second-wave-source-confirmation-packet-json",
        default=DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument("--glut1-draft-packet-json", default=DEFAULT_GLUT1_DRAFT_PACKET_JSON)
    parser.add_argument("--glut1-commit-packet-json", default=DEFAULT_GLUT1_COMMIT_PACKET_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument(
        "--transporter-placeholder-burndown-queue-json",
        default=DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON,
    )
    parser.add_argument(
        "--transporter-negative-target-packets-json",
        default=DEFAULT_TRANSPORTER_NEGATIVE_TARGET_PACKETS_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.execution_json),
        _load_json(args.operator_console_json),
        _load_json(args.platform_index_json),
        _load_json(args.platform_quickstart_json),
        _load_json(args.pretest_sequence_json),
        _load_json(args.pretest_checklist_json),
        _load_json(args.run_now_packet_json),
        _load_json(args.run_now_safe_command_json),
        _load_json(args.idp_pretest_scope_json),
        _load_json(args.idp_commercial_pretest_json),
        _maybe_load_json(args.idp_broader_result_json),
        _maybe_load_json(args.idp_broader_decision_json),
        _load_json(args.idp_broader_review_packet_json),
        _maybe_load_json(args.idp_broader_review_resolution_json),
        _maybe_load_json(args.idp_broader_launch_packet_json),
        _maybe_load_json(args.idp_page4_curation_packet_json),
        _maybe_load_json(args.idp_page4_evidence_seed_json),
        _maybe_load_json(args.idp_page4_provenance_fill_json),
        _maybe_load_json(args.idp_page4_citation_confirmed_json),
        _maybe_load_json(args.idp_page4_phospho_followup_json),
        _maybe_load_json(args.idp_page4_phospho_fill_draft_json),
        _maybe_load_json(args.idp_page4_readiness_json),
        _maybe_load_json(args.idp_page4_ph_low_fill_json),
        _maybe_load_json(args.idp_page4_ph_high_fill_json),
        _maybe_load_json(args.idp_page4_review_json),
        _maybe_load_json(args.idp_page4_decision_json),
        _maybe_load_json(args.idp_page4_confirmation_json),
        _maybe_load_json(args.idp_page4_confirmation_recommendation_json),
        _maybe_load_json(args.idp_page4_promotion_review_json),
        _maybe_load_json(args.idp_page4_confirmation_launch_json),
        _maybe_load_json(args.idp_page4_confirmation_console_json),
        _maybe_load_json(args.idp_page4_confirmation_workbench_json),
        _maybe_load_json(args.idp_page4_confirmation_note_templates_json),
        _maybe_load_json(args.idp_page4_quantitative_replacement_json),
        _load_json(args.heatmap_json),
        _load_json(args.commercialization_gap_json),
        _load_json(args.commercial_core_json),
        _load_json(args.partial_console_json),
        _load_json(args.partial_operator_console_json),
        _load_json(args.partial_quickstart_json),
        _load_json(args.partial_reviewer_console_json),
        _load_json(args.ca2_day_plan_json),
        _load_json(args.pxr_day_plan_json),
        _load_json(args.ca2_workbench_json),
        _load_json(args.ca2_draft_packet_json),
        _load_json(args.ca2_commit_packet_json),
        _load_json(args.pxr_workbench_json),
        _load_json(args.pxr_draft_packet_json),
        _load_json(args.pxr_commit_packet_json),
        _maybe_load_json(args.pxr_capture_sheet_json),
        _maybe_load_json(args.pxr_capture_intake_json),
        _maybe_load_json(args.pxr_exact_source_confirmation_json),
        _maybe_load_json(args.pxr_quantitative_provenance_json),
        transporter_dashboard=_load_json(args.transporter_dashboard_json),
        transporter_apply_status=_maybe_load_json(args.transporter_apply_status_json),
        transporter_quickstart=_load_json(args.transporter_quickstart_json),
        transporter_operator_console=_load_json(args.transporter_operator_console_json),
        transporter_launchboard=_load_json(args.transporter_launchboard_json),
        transporter_day_plan=_load_json(args.transporter_day_plan_json),
        transporter_neg_day_plan=_load_json(args.transporter_neg_day_plan_json),
        transporter_donor_blocker=_load_json(args.transporter_donor_blocker_json),
        transporter_capture_sheet=_maybe_load_json(args.transporter_capture_sheet_json),
        transporter_capture_intake=_maybe_load_json(args.transporter_capture_intake_json),
        aqp1_workbench=_load_json(args.aqp1_workbench_json),
        aqp1_first_seed_row_packet=_load_json(args.aqp1_first_seed_row_packet_json),
        aqp1_source_confirmation=_load_json(args.aqp1_source_confirmation_json),
        aqp1_negative_source_exclusion=_maybe_load_json(args.aqp1_negative_source_exclusion_json),
        aqp1_negative_slot_closure=_maybe_load_json(args.aqp1_negative_slot_closure_json),
        aqp1_negative_acquisition=_maybe_load_json(args.aqp1_negative_acquisition_json),
        aqp1_negative_confirmation=_maybe_load_json(args.aqp1_negative_confirmation_json),
        aqp1_negative_slot_resolution=_maybe_load_json(args.aqp1_negative_slot_resolution_json),
        aqp1_negative_candidate_frontier=_maybe_load_json(args.aqp1_negative_candidate_frontier_json),
        aqp1_negative_frontier_resolution=_maybe_load_json(args.aqp1_negative_frontier_resolution_json),
        aqp1_negative_primary_probe=_maybe_load_json(args.aqp1_negative_primary_probe_json),
        aqp1_negative_exact_source_outcome=_maybe_load_json(args.aqp1_negative_exact_source_outcome_json),
        aqp1_negative_primary_probe_resolution=_maybe_load_json(args.aqp1_negative_primary_probe_resolution_json),
        transporter_seed_row_execution_packet=_load_json(args.transporter_seed_row_execution_packet_json),
        aqp1_seed_row_fill_draft=_load_json(args.aqp1_seed_row_fill_draft_json),
        aqp1_draft_packet=_load_json(args.aqp1_draft_packet_json),
        aqp1_commit_packet=_load_json(args.aqp1_commit_packet_json),
        aqp1_quantitative_provenance=_load_json(args.aqp1_quantitative_provenance_json),
        glut1_workbench=_load_json(args.glut1_workbench_json),
        glut1_draft_packet=_load_json(args.glut1_draft_packet_json),
        glut1_commit_packet=_load_json(args.glut1_commit_packet_json),
        transporter_seed_row_board=_load_json(args.transporter_seed_row_board_json),
        transporter_negative_target_packets=_maybe_load_json(args.transporter_negative_target_packets_json),
        aqp1_follow_on_packet=_maybe_load_json(args.aqp1_follow_on_packet_json),
        aqp1_follow_on_blocker_decomposition=_maybe_load_json(args.aqp1_follow_on_blocker_decomposition_json),
        aqp1_follow_on_source_confirmation_packet=_maybe_load_json(
            args.aqp1_follow_on_source_confirmation_packet_json
        ),
        glut1_second_wave_source_confirmation_packet=_maybe_load_json(
            args.glut1_second_wave_source_confirmation_packet_json
        ),
        transporter_placeholder_burndown_queue=_maybe_load_json(args.transporter_placeholder_burndown_queue_json),
        idp_broader_promotion_review=_maybe_load_json(args.idp_broader_promotion_review_json),
        idp_broader_promotion_resolution=_maybe_load_json(args.idp_broader_promotion_resolution_json),
        idp_one_wider_repeatability_packet=_maybe_load_json(args.idp_one_wider_repeatability_packet_json),
        idp_one_wider_repeatability_result=_maybe_load_json(args.idp_one_wider_repeatability_result_json),
        pxr_conflict_resolver=_maybe_load_json(args.pxr_conflict_resolver_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
