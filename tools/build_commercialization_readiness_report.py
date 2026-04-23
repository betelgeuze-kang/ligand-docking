#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.ligand_scaleup_surface_helpers import (
    DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON as LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON,
    DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON as LIGAND_SCALEUP_SUITE_STATUS_JSON,
    summarize_ligand_scaleup_blocker,
)
from tools.local_engine_surface_helpers import (
    DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON,
    summarize_local_engine_commercialization_queue,
)
from tools.wetlab_surface_helpers import (
    DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON,
    summarize_wetlab_execution_readiness_queue,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CROSSFAMILY_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_GPCR_ENDPOINT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_IDP_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_TRANSPORTER_CLOSURE_QUEUE_JSON = "runs/transporter_commercialization_closure_queue_current.json"
DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON = "runs/aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON = "runs/aqp1_negative_primary_probe_resolution_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD = "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON
DEFAULT_WETLAB_EXECUTION_QUEUE_JSON = DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON
DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON = LIGAND_SCALEUP_SUITE_STATUS_JSON
DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON = LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON
DEFAULT_OUT_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_OUT_CSV = "runs/commercialization_readiness_current.csv"
DEFAULT_OUT_MD = "runs/commercialization_readiness_current.md"


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


def _stage_label(score: int) -> str:
    if score >= 85:
        return "measured_family_commercial_lane"
    if score >= 75:
        return "apply_safe_claim_lane"
    if score >= 60:
        return "subset_or_partial_authoritative_lane"
    if score >= 40:
        return "manual_review_or_blocked_expansion_lane"
    return "scaffold_only_lane"


def _aqp1_source_confirmation_artifact(aqp1_source_confirmation_packet: dict[str, Any] | None) -> str:
    if aqp1_source_confirmation_packet:
        return "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    return ""


def _aqp1_follow_on_packet_artifact(aqp1_follow_on_packet: dict[str, Any] | None) -> str:
    if aqp1_follow_on_packet:
        return "runs/aqp1_first_wave_follow_on_packet_current.md"
    return ""


def _aqp1_follow_on_blocker_decomposition_artifact(
    aqp1_follow_on_blocker_decomposition: dict[str, Any] | None,
) -> str:
    if aqp1_follow_on_blocker_decomposition:
        return "runs/aqp1_follow_on_blocker_decomposition_current.md"
    return ""


def _aqp1_follow_on_source_confirmation_packet_artifact(
    aqp1_follow_on_source_confirmation_packet: dict[str, Any] | None,
) -> str:
    if aqp1_follow_on_source_confirmation_packet:
        return "runs/aqp1_follow_on_source_confirmation_packet_current.md"
    return ""


def _transporter_placeholder_burndown_queue_artifact(
    transporter_placeholder_burndown_queue: dict[str, Any] | None,
) -> str:
    if transporter_placeholder_burndown_queue:
        return "runs/transporter_placeholder_burndown_queue_current.md"
    return ""


def _aqp1_negative_primary_probe_resolution_artifact(
    aqp1_negative_primary_probe_resolution_packet: dict[str, Any] | None,
) -> str:
    if aqp1_negative_primary_probe_resolution_packet:
        return DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD
    return ""


def _follow_on_seed_targets(
    aqp1_follow_on_blocker_decomposition_summary: dict[str, Any],
    aqp1_follow_on_packet_summary: dict[str, Any],
    transporter_closure_queue_summary: dict[str, Any],
) -> str:
    return str(
        aqp1_follow_on_blocker_decomposition_summary.get("follow_on_targets")
        or aqp1_follow_on_packet_summary.get("aqp1_follow_on_seed_targets")
        or aqp1_follow_on_packet_summary.get("follow_on_seed_targets")
        or aqp1_follow_on_packet_summary.get("follow_on_targets")
        or transporter_closure_queue_summary.get("remaining_seed_targets")
        or "core_binder_02, core_binder_03"
    ).strip()


def _follow_on_lane_label(follow_on_seed_targets: str) -> str:
    parts = [part.strip() for part in follow_on_seed_targets.split(",") if part.strip()]
    if parts == ["core_binder_02", "core_binder_03"]:
        return "core_binder_02/03"
    return " / ".join(parts) if len(parts) > 1 else follow_on_seed_targets.strip()


def _follow_on_lane_text(follow_on_lane_label: str) -> str:
    return f"the {follow_on_lane_label or 'core_binder_02/03'} follow-on AQP1 lane"


def _aqp1_provenance_clause(exact_human_reference_ligand: str) -> str:
    reference = exact_human_reference_ligand or "AqB013"
    return f", keep {reference} exact human AQP1 target-activity provenance, kcal blank"


def _transporter_claim_safe_scope(
    primary_focus_ligand: str,
    exact_human_reference_ligand: str,
    follow_on_lane_label: str,
) -> str:
    follow_on_lane_text = _follow_on_lane_text(follow_on_lane_label)
    if primary_focus_ligand and exact_human_reference_ligand:
        return (
            "non-authoritative AQP1 first-wave seed-row promotion with "
            f"{primary_focus_ligand} as the primary exact-source scope and "
            f"{exact_human_reference_ligand} as the exact-human-activity guardrail, "
            f"while {follow_on_lane_text} stays parked, plus GLUT1 second-wave blocker closure"
        )
    if primary_focus_ligand:
        return (
            "non-authoritative AQP1 first-wave seed-row promotion with "
            f"{primary_focus_ligand} as the primary exact-source scope, while {follow_on_lane_text} stays parked, plus GLUT1 second-wave blocker closure"
        )
    return "non-authoritative AQP1 first-wave seed-row promotion plus GLUT1 second-wave blocker closure"


def _transporter_story_tail(
    primary_focus_ligand: str,
    exact_human_reference_ligand: str,
    follow_on_lane_label: str,
) -> str:
    follow_on_lane_text = _follow_on_lane_text(follow_on_lane_label)
    provenance_clause = _aqp1_provenance_clause(exact_human_reference_ligand)
    if primary_focus_ligand and exact_human_reference_ligand:
        return (
            f" Transporter blocker-closure stays queue-led, with {primary_focus_ligand} as the AQP1 first-wave exact-source scope "
            f"and {exact_human_reference_ligand} as the exact-human-activity guardrail while "
            f"{follow_on_lane_text} stays parked{provenance_clause} and replacement_reference_binding_kcal_mol remains blank."
        )
    if primary_focus_ligand:
        return (
            f" Transporter blocker-closure stays queue-led, with {primary_focus_ligand} as the AQP1 first-wave exact-source scope "
            f"while {follow_on_lane_text} stays parked{provenance_clause} and replacement_reference_binding_kcal_mol remains blank."
        )
    return ""


def _transporter_next_step_tail(
    primary_focus_ligand: str,
    exact_human_reference_ligand: str,
    follow_on_lane_label: str,
    follow_on_blocker_decomposition_next_required_step: str,
) -> str:
    follow_on_clause = f", park {_follow_on_lane_text(follow_on_lane_label)}" if primary_focus_ligand or exact_human_reference_ligand or follow_on_lane_label else ""
    provenance_clause = _aqp1_provenance_clause(exact_human_reference_ligand)
    if primary_focus_ligand and exact_human_reference_ligand:
        return (
            "keep commercial expansion work focused on the transporter closure queue starting with AQP1 core_binder_01, "
            f"confirm {primary_focus_ligand} as the first-wave exact-source scope packet{provenance_clause}{follow_on_clause}, "
            "leave replacement_reference_binding_kcal_mol blank, "
            "then CA2/PXR evidence closure."
            + (
                f" Use the AQP1 follow-on blocker decomposition: {follow_on_blocker_decomposition_next_required_step}."
                if follow_on_blocker_decomposition_next_required_step
                else ""
            )
        )
    if primary_focus_ligand:
        return (
            "keep commercial expansion work focused on the transporter closure queue starting with AQP1 core_binder_01, "
            f"confirm {primary_focus_ligand} as the first-wave exact-source scope packet{provenance_clause}{follow_on_clause}, "
            "leave replacement_reference_binding_kcal_mol blank, then CA2/PXR evidence closure."
            + (
                f" Use the AQP1 follow-on blocker decomposition: {follow_on_blocker_decomposition_next_required_step}."
                if follow_on_blocker_decomposition_next_required_step
                else ""
            )
        )
    return (
        "keep commercial expansion work focused on the transporter closure queue starting with AQP1 core_binder_01"
        f"{provenance_clause}{follow_on_clause}, then CA2/PXR evidence closure."
        + (
            f" Use the AQP1 follow-on blocker decomposition: {follow_on_blocker_decomposition_next_required_step}."
            if follow_on_blocker_decomposition_next_required_step
            else ""
        )
    )


def build_payload(
    crossfamily: dict[str, Any],
    gpcr_endpoint: dict[str, Any],
    idp_decision: dict[str, Any],
    idp_commercial_pretest: dict[str, Any],
    ca2_readiness: dict[str, Any],
    pxr_readiness: dict[str, Any],
    transporter_dashboard: dict[str, Any],
    transporter_seed_row_board: dict[str, Any],
    transporter_closure_queue: dict[str, Any] | None = None,
    idp_commercial_pretest_decision: dict[str, Any] | None = None,
    idp_broader_shadow_decision: dict[str, Any] | None = None,
    idp_broader_promotion_resolution: dict[str, Any] | None = None,
    idp_one_wider_repeatability_packet: dict[str, Any] | None = None,
    idp_one_wider_repeatability_result: dict[str, Any] | None = None,
    aqp1_source_confirmation_packet: dict[str, Any] | None = None,
    aqp1_follow_on_packet: dict[str, Any] | None = None,
    aqp1_follow_on_blocker_decomposition: dict[str, Any] | None = None,
    aqp1_follow_on_source_confirmation_packet: dict[str, Any] | None = None,
    transporter_placeholder_burndown_queue: dict[str, Any] | None = None,
    aqp1_negative_primary_probe_resolution_packet: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation_packet: dict[str, Any] | None = None,
    ligand_scaleup_suite_status: dict[str, Any] | None = None,
    ligand_scaleup_benchmark_summary: dict[str, Any] | None = None,
    local_engine_commercialization_queue: dict[str, Any] | None = None,
    wetlab_execution_readiness_queue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gpcr_summary = dict(gpcr_endpoint.get("summary", {}) or {})
    idp_summary = dict(idp_decision.get("summary", {}) or {})
    idp_pretest_summary = dict(idp_commercial_pretest.get("summary", {}) or {})
    idp_pretest_decision_summary = dict((idp_commercial_pretest_decision or {}).get("summary", {}) or {})
    idp_broader_decision_summary = dict((idp_broader_shadow_decision or {}).get("summary", {}) or {})
    idp_broader_promotion_resolution_summary = dict((idp_broader_promotion_resolution or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_packet_summary = dict((idp_one_wider_repeatability_packet or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_result_summary = dict((idp_one_wider_repeatability_result or {}).get("summary", {}) or {})
    idp_effective_decision = idp_broader_promotion_resolution_summary or idp_broader_decision_summary or idp_pretest_decision_summary
    idp_repeatability_summary = idp_one_wider_repeatability_result_summary or idp_one_wider_repeatability_packet_summary
    idp_additional_anchor_backed_target_count = int(idp_pretest_decision_summary.get("additional_anchor_backed_target_count", 0) or 0)
    idp_same_scope_reproducibility_confirmed = bool(idp_pretest_decision_summary.get("same_scope_reproducibility_confirmed", False))
    idp_page4_candidate_ready_now = bool(idp_pretest_decision_summary.get("page4_candidate_ready_now", False))
    ca2_summary = dict(ca2_readiness.get("summary", {}) or {})
    pxr_summary = dict(pxr_readiness.get("summary", {}) or {})
    transporter_summary = dict(transporter_dashboard.get("summary", {}) or {})
    transporter_seed_summary = dict(transporter_seed_row_board.get("summary", {}) or {})
    transporter_closure_queue_summary = dict((transporter_closure_queue or {}).get("summary", {}) or {})
    aqp1_source_confirmation_summary = dict((aqp1_source_confirmation_packet or {}).get("summary", {}) or {})
    aqp1_follow_on_packet_summary = dict((aqp1_follow_on_packet or {}).get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_summary = dict((aqp1_follow_on_blocker_decomposition or {}).get("summary", {}) or {})
    aqp1_follow_on_source_confirmation_packet_summary = dict(
        (aqp1_follow_on_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    transporter_placeholder_burndown_queue_summary = dict(
        (transporter_placeholder_burndown_queue or {}).get("summary", {}) or {}
    )
    aqp1_negative_primary_probe_resolution_summary = dict(
        (aqp1_negative_primary_probe_resolution_packet or {}).get("summary", {}) or {}
    )
    glut1_second_wave_source_confirmation_packet_summary = dict(
        (glut1_second_wave_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    aqp1_source_confirmation_artifact = _aqp1_source_confirmation_artifact(aqp1_source_confirmation_packet)
    aqp1_follow_on_packet_artifact = _aqp1_follow_on_packet_artifact(aqp1_follow_on_packet)
    aqp1_follow_on_blocker_decomposition_artifact = _aqp1_follow_on_blocker_decomposition_artifact(
        aqp1_follow_on_blocker_decomposition
    )
    aqp1_follow_on_source_confirmation_packet_artifact = _aqp1_follow_on_source_confirmation_packet_artifact(
        aqp1_follow_on_source_confirmation_packet
    )
    transporter_placeholder_burndown_queue_artifact = _transporter_placeholder_burndown_queue_artifact(
        transporter_placeholder_burndown_queue
    )
    aqp1_negative_primary_probe_resolution_artifact = _aqp1_negative_primary_probe_resolution_artifact(
        aqp1_negative_primary_probe_resolution_packet
    )
    ligand_scaleup_summary = summarize_ligand_scaleup_blocker(
        ligand_scaleup_suite_status,
        ligand_scaleup_benchmark_summary,
    )
    local_engine_summary = summarize_local_engine_commercialization_queue(
        local_engine_commercialization_queue
    )
    wetlab_summary = summarize_wetlab_execution_readiness_queue(
        wetlab_execution_readiness_queue
    )
    aqp1_negative_primary_probe_resolution_row_count = int(
        aqp1_negative_primary_probe_resolution_summary.get("row_count", 0) or 0
    )
    aqp1_negative_primary_probe_resolution_candidate = str(
        aqp1_negative_primary_probe_resolution_summary.get("primary_probe_candidate", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate = str(
        aqp1_negative_primary_probe_resolution_summary.get("solvent_fallback_candidate", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_decision = str(
        aqp1_negative_primary_probe_resolution_summary.get("resolution_decision", "") or ""
    ).strip()
    aqp1_negative_primary_probe_resolution_next_required_step = str(
        aqp1_negative_primary_probe_resolution_summary.get("next_required_step", "") or ""
    ).strip()
    glut1_second_wave_source_confirmation_packet_artifact = (
        "runs/glut1_second_wave_source_confirmation_packet_current.md"
        if glut1_second_wave_source_confirmation_packet_summary
        else ""
    )
    glut1_second_wave_source_confirmation_packet_primary_focus_ligand = str(
        glut1_second_wave_source_confirmation_packet_summary.get("primary_focus_ligand", "") or ""
    ).strip()
    glut1_second_wave_direct_quantitative_binding_count = int(
        glut1_second_wave_source_confirmation_packet_summary.get("direct_quantitative_binding_count", 0) or 0
    )
    aqp1_first_wave_primary_focus_ligand = str(
        aqp1_source_confirmation_summary.get(
            "primary_focus_ligand",
            transporter_closure_queue_summary.get("aqp1_source_confirmation_primary_focus_ligand", ""),
        )
        or ""
    ).strip()
    aqp1_exact_human_reference_ligand = str(
        aqp1_source_confirmation_summary.get(
            "exact_human_reference_ligand",
            transporter_closure_queue_summary.get("aqp1_focus_ligand", ""),
        )
        or ""
    ).strip()
    aqp1_follow_on_targets = _follow_on_seed_targets(
        aqp1_follow_on_blocker_decomposition_summary,
        aqp1_follow_on_packet_summary,
        transporter_closure_queue_summary,
    )
    aqp1_follow_on_lane_label = _follow_on_lane_label(aqp1_follow_on_targets)
    aqp1_follow_on_row_count = int(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "blocker_row_count",
            aqp1_follow_on_packet_summary.get("row_count", 0),
        )
        or 0
    )
    aqp1_follow_on_blocker_decomposition_primary_focus_ligand = str(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "primary_focus_ligand",
            aqp1_follow_on_packet_summary.get("primary_focus_ligand", ""),
        )
        or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand = str(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_human_guardrail_ligand",
            aqp1_follow_on_packet_summary.get("exact_human_guardrail_ligand", ""),
        )
        or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count = int(
        aqp1_follow_on_blocker_decomposition_summary.get("exact_human_nonbinding_count", 0) or 0
    )
    aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count = int(
        aqp1_follow_on_blocker_decomposition_summary.get("exact_target_pair_absent_count", 0) or 0
    )
    aqp1_follow_on_blocker_decomposition_claim_safe_kcal_ready_count = int(
        aqp1_follow_on_blocker_decomposition_summary.get("claim_safe_kcal_ready_count", 0) or 0
    )
    aqp1_follow_on_blocker_decomposition_blocking_signal = str(
        aqp1_follow_on_blocker_decomposition_summary.get("blocking_signal", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_next_required_step = str(
        aqp1_follow_on_blocker_decomposition_summary.get("next_required_step", "") or ""
    ).strip()
    transporter_story_tail = _transporter_story_tail(
        aqp1_first_wave_primary_focus_ligand,
        aqp1_exact_human_reference_ligand,
        aqp1_follow_on_lane_label,
    )
    transporter_next_step_tail = _transporter_next_step_tail(
        aqp1_first_wave_primary_focus_ligand,
        aqp1_exact_human_reference_ligand,
        aqp1_follow_on_lane_label,
        aqp1_follow_on_blocker_decomposition_next_required_step,
    )
    glut1_second_wave_tail = (
        f" Keep {glut1_second_wave_source_confirmation_packet_artifact or 'runs/glut1_second_wave_source_confirmation_packet_current.md'} open as the GLUT1 second-wave source-confirmation packet handoff, "
        f"with {glut1_second_wave_source_confirmation_packet_primary_focus_ligand} as the direct quantitative binding lead and direct quantitative binding rows={glut1_second_wave_direct_quantitative_binding_count}."
        if glut1_second_wave_source_confirmation_packet_primary_focus_ligand
        else ""
    )
    aqp1_negative_primary_probe_resolution_tail = (
        f" Keep {aqp1_negative_primary_probe_resolution_artifact or DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD} open as the AQP1 negative primary-probe-resolution handoff. "
        + (
            aqp1_negative_primary_probe_resolution_next_required_step
            if aqp1_negative_primary_probe_resolution_next_required_step
            else (
                f"Keep {aqp1_negative_primary_probe_resolution_candidate or 'the current primary negative probe candidate'} review-only, "
                f"preserve {aqp1_negative_primary_probe_resolution_solvent_fallback_candidate or 'the solvent fallback candidate'} as solvent fallback only, "
                f"and hold the lane at {aqp1_negative_primary_probe_resolution_decision or 'keep_review_only_no_authoritative_negative_promotion'}."
            )
        )
        if aqp1_negative_primary_probe_resolution_summary
        else ""
    )
    combined_transporter_story_tail = transporter_story_tail + aqp1_negative_primary_probe_resolution_tail
    combined_transporter_next_step_tail = transporter_next_step_tail + aqp1_negative_primary_probe_resolution_tail
    local_engine_story_tail = (
        f" {local_engine_summary['local_engine_commercialization_queue_blocker_note']}"
        if local_engine_summary["local_engine_commercialization_queue_blocker_note"]
        else ""
    )
    local_engine_next_step_tail = (
        f" {local_engine_summary['local_engine_commercialization_queue_next_required_step']}"
        if local_engine_summary["local_engine_commercialization_queue_next_required_step"]
        else ""
    )
    wetlab_story_tail = (
        f" {wetlab_summary['wetlab_execution_readiness_queue_blocker_note']}"
        if wetlab_summary["wetlab_execution_readiness_queue_blocker_note"]
        else ""
    )
    wetlab_next_step_tail = (
        f" {wetlab_summary['wetlab_execution_readiness_queue_next_required_step']}"
        if wetlab_summary["wetlab_execution_readiness_queue_next_required_step"]
        else ""
    )

    rows = [
        {
            "family": "gpcr",
            "score": 82,
            "stage": _stage_label(82),
            "status": "apply_safe_endpoint_ready_router_blocked",
            "claim_safe_scope": "locked-decoy equal-size shadow/apply endpoint",
            "primary_blocker": "100k router still blocked by tiny residual chembl50 PR regression",
            "source_artifact": "runs/gpcr_apply_safe_endpoint_current.md",
        },
        {
            "family": "ion_channel",
            "score": 88,
            "stage": _stage_label(88),
            "status": "measured_noop_shadow_ready",
            "claim_safe_scope": "measured family with locked-decoy shadow stability",
            "primary_blocker": "no blocker on current commercial lane; expansion waits on cross-family breadth",
            "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md",
        },
        {
            "family": "kinase",
            "score": 90,
            "stage": _stage_label(90),
            "status": "measured_noop_shadow_ready",
            "claim_safe_scope": "measured family with locked-decoy shadow stability",
            "primary_blocker": "no blocker on current commercial lane; expansion waits on cross-family breadth",
            "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md",
        },
        {
            "family": "idp",
            "score": 70,
            "stage": _stage_label(70),
            "status": (
                str(idp_effective_decision.get("status", "")).strip()
                if idp_broader_promotion_resolution_summary
                else
                str(idp_effective_decision.get("status", "")).strip()
                if idp_effective_decision
                else "controlled_shadow_only_commercial_pretest_ready_broader_blocked"
                if idp_pretest_summary
                else "literature_anchor_default_mask_ready"
            ),
            "claim_safe_scope": (
                "one wider shadow-safe lane admitted on a frozen 8-target roster under the same no-override guardrails; broader_full_idp_promotion still blocked"
                if idp_broader_promotion_resolution_summary
                else
                "controlled shadow-only commercial-pretest lane with one completed broader shadow-only pass still held behind explicit promotion review"
                if idp_broader_decision_summary
                else str(idp_pretest_decision_summary.get("operator_scope_now", "")).strip().replace("_", " ")
                if idp_pretest_decision_summary
                else "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis"
                if idp_pretest_summary
                else "literature-anchor subset shadow default only"
            ),
            "primary_blocker": (
                str(idp_effective_decision.get("blocker_reason", "") or "").strip()
                or str(idp_pretest_summary.get("blocker_reason", "") or "").strip()
                or "broader full-IDP corrected-path promotion remains blocked"
            ),
            "source_artifact": (
                "runs/idp_broader_promotion_resolution_current.md"
                if idp_broader_promotion_resolution_summary
                else
                "runs/idp_broader_shadow_decision_current.md"
                if idp_broader_decision_summary
                else
                "runs/idp_commercial_pretest_decision_current.md"
                if idp_pretest_decision_summary
                else "runs/idp_commercial_pretest_packet_current.md"
                if idp_pretest_summary
                else "runs/idp_feature_state_subset_decision_current.md"
            ),
        },
        {
            "family": "non_kinase_enzyme_ca2",
            "score": 58,
            "stage": _stage_label(58),
            "status": "partial_authoritative_rows_ready",
            "claim_safe_scope": f"authoritative-ready rows {ca2_summary.get('ready_row_count', 0)}/{ca2_summary.get('workbook_row_count', 0)}",
            "primary_blocker": "remaining negative-like rows are still review-only with no direct target-specific negative evidence",
            "source_artifact": "runs/ca2_packet_replacement_readiness_current.md",
        },
        {
            "family": "nuclear_receptor_pxr",
            "score": 62,
            "stage": _stage_label(62),
            "status": "partial_authoritative_rows_ready",
            "claim_safe_scope": f"authoritative-ready rows {pxr_summary.get('ready_for_apply_row_count', 0)}/{pxr_summary.get('matched_queue_rows', 0)}",
            "primary_blocker": "remaining rows are split between one review-only negative and multiple deferred unresolved evidence rows",
            "source_artifact": "runs/pxr_packet_fill_readiness_current.md",
        },
        {
            "family": "transporter",
            "score": 32,
            "stage": _stage_label(32),
            "status": (
                "manual_verdict_complete_blocker_closure_seed_row_promotion"
                if transporter_summary
                else "manual_review_only_first_wave_second_wave"
            ),
            "claim_safe_scope": (
                _transporter_claim_safe_scope(
                    aqp1_first_wave_primary_focus_ligand,
                    aqp1_exact_human_reference_ligand,
                    aqp1_follow_on_lane_label,
                )
                if transporter_summary
                else (
                    f"draft/manual-review only with {aqp1_first_wave_primary_focus_ligand} staged as the first-wave exact-source scope packet"
                    + (
                        f" and {aqp1_follow_on_lane_label} staged as the follow-on AQP1 lane"
                        if aqp1_follow_on_lane_label
                        else ""
                    )
                    if aqp1_first_wave_primary_focus_ligand
                    else "draft/manual-review only"
                )
            ),
            "primary_blocker": (
                (
                    f"top_queue_id={transporter_closure_queue_summary.get('top_queue_id', '')}; "
                    f"placeholder_driven_rows={transporter_closure_queue_summary.get('placeholder_driven_rows', 0)}; "
                    f"blocked_donor_check_count={transporter_closure_queue_summary.get('blocked_donor_check_count', 0)}"
                    + (
                        f"; first_wave_primary_focus={aqp1_first_wave_primary_focus_ligand}"
                        if aqp1_first_wave_primary_focus_ligand
                        else ""
                    )
                    + (
                        f"; exact_human_guardrail={aqp1_exact_human_reference_ligand}"
                        if aqp1_exact_human_reference_ligand
                        else ""
                    )
                )
                if transporter_closure_queue_summary
                else f"{transporter_seed_summary.get('top_blocker_signal', '')}; donor_reopen_ready=False".strip("; ")
                if transporter_seed_summary
                else "no authoritative transporter packet rows and donor policy reopen is still false"
            ),
            "source_artifact": (
                "runs/transporter_commercialization_closure_queue_current.md"
                if transporter_closure_queue_summary
                else "runs/transporter_seed_row_promotion_board_current.md"
                if transporter_seed_summary
                else "runs/transporter_manual_review_dashboard_current.md"
            ),
            "supporting_artifact": aqp1_source_confirmation_artifact,
        },
    ]

    core_families = {"gpcr", "ion_channel", "kinase", "idp"}
    core_scores = [row["score"] for row in rows if row["family"] in core_families]
    all_scores = [row["score"] for row in rows]

    summary = {
        "family_count": len(rows),
        "core_commercial_lane_score": round(sum(core_scores) / len(core_scores), 1),
        "all_category_expansion_score": round(sum(all_scores) / len(all_scores), 1),
        "strongest_ready_families": ["kinase", "ion_channel", "gpcr"],
        "transporter_commercialization_closure_queue_ready": bool(transporter_closure_queue_summary),
        "transporter_commercialization_closure_queue_rows": transporter_closure_queue_summary.get("queue_row_count", 0),
        "transporter_commercialization_top_queue_id": transporter_closure_queue_summary.get("top_queue_id", ""),
        "transporter_placeholder_burndown_queue_ready": bool(transporter_placeholder_burndown_queue_summary),
        "transporter_placeholder_burndown_queue_artifact": transporter_placeholder_burndown_queue_artifact,
        "transporter_placeholder_burndown_queue_rows": transporter_placeholder_burndown_queue_summary.get("queue_row_count", 0),
        "transporter_placeholder_burndown_queue_top_blocker_id": transporter_placeholder_burndown_queue_summary.get(
            "top_blocker_id", ""
        ),
        "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_negative_primary_probe_resolution_summary),
        "aqp1_negative_primary_probe_resolution_artifact": aqp1_negative_primary_probe_resolution_artifact,
        "aqp1_negative_primary_probe_resolution_row_count": aqp1_negative_primary_probe_resolution_row_count,
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_negative_primary_probe_resolution_candidate,
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_negative_primary_probe_resolution_solvent_fallback_candidate,
        "aqp1_negative_primary_probe_resolution_decision": aqp1_negative_primary_probe_resolution_decision,
        "aqp1_negative_primary_probe_resolution_next_required_step": aqp1_negative_primary_probe_resolution_next_required_step,
        "glut1_second_wave_source_confirmation_packet_ready": bool(glut1_second_wave_source_confirmation_packet_summary),
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_second_wave_source_confirmation_packet_artifact,
        "glut1_second_wave_source_confirmation_packet_rows": glut1_second_wave_source_confirmation_packet_summary.get(
            "row_count", 0
        ),
        "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": glut1_second_wave_source_confirmation_packet_primary_focus_ligand,
        "glut1_second_wave_direct_quantitative_binding_count": glut1_second_wave_direct_quantitative_binding_count,
        "aqp1_first_wave_source_confirmation_artifact": aqp1_source_confirmation_artifact,
        "aqp1_first_wave_follow_on_packet_artifact": aqp1_follow_on_packet_artifact,
        "aqp1_follow_on_source_confirmation_packet_ready": bool(aqp1_follow_on_source_confirmation_packet_summary),
        "aqp1_follow_on_source_confirmation_packet_artifact": aqp1_follow_on_source_confirmation_packet_artifact,
        "aqp1_follow_on_source_confirmation_packet_rows": aqp1_follow_on_source_confirmation_packet_summary.get(
            "row_count", 0
        ),
        "aqp1_follow_on_source_confirmation_packet_primary_focus_ligand": aqp1_follow_on_source_confirmation_packet_summary.get(
            "primary_focus_ligand", ""
        ),
        "aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand": aqp1_follow_on_source_confirmation_packet_summary.get(
            "exact_human_reference_ligand", ""
        ),
        "aqp1_first_wave_primary_focus_ligand": aqp1_first_wave_primary_focus_ligand,
        "aqp1_exact_human_reference_ligand": aqp1_exact_human_reference_ligand,
        "aqp1_first_wave_claim_safe_kcal_ready_count": aqp1_source_confirmation_summary.get("claim_safe_kcal_ready_count", 0),
        "aqp1_first_wave_follow_on_targets": aqp1_follow_on_targets,
        "aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets": aqp1_follow_on_targets,
        "aqp1_first_wave_follow_on_lane_label": aqp1_follow_on_lane_label,
        "aqp1_first_wave_follow_on_row_count": aqp1_follow_on_row_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
        "aqp1_first_wave_follow_on_blocker_decomposition_row_count": aqp1_follow_on_row_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand": aqp1_follow_on_blocker_decomposition_primary_focus_ligand,
        "aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand": aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand,
        "aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count": aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count": aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_claim_safe_kcal_ready_count": aqp1_follow_on_blocker_decomposition_claim_safe_kcal_ready_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal": aqp1_follow_on_blocker_decomposition_blocking_signal,
        "aqp1_first_wave_follow_on_blocker_decomposition_next_required_step": aqp1_follow_on_blocker_decomposition_next_required_step,
        **wetlab_summary,
        **local_engine_summary,
        **ligand_scaleup_summary,
        "main_platform_story": (
            "Commercial core is strong in measured families, IDP now has one admitted wider shadow-safe lane frozen to the validated 7-target scaffold plus PAGE4 and a bounded repeatability check prepared or running for that lane, but broader_full_idp_promotion and commercialization beyond that bounded lane remain blocked, and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
            if idp_broader_promotion_resolution_summary and idp_repeatability_summary
            else
            "Commercial core is strong in measured families, IDP now retains a shadow-safe controlled commercial-pretest lane and has admitted one wider shadow-safe lane frozen to the validated 7-target scaffold plus PAGE4, but broader_full_idp_promotion and commercialization beyond that bounded lane remain blocked, and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
            if idp_broader_promotion_resolution_summary
            else
            "Commercial core is strong in measured families, IDP now retains a shadow-safe controlled commercial-pretest lane and has completed a clean first broader shadow-only pass with PAGE4 as the first additional anchor-backed target, but broader promotion still remains behind an explicit promotion review, and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
            if idp_broader_decision_summary
            else
            "Commercial core is strong in measured families, IDP now retains a shadow-safe controlled commercial-pretest lane with same-scope reproducibility confirmed while any true broader rerun remains blocked until at least one extra anchor-backed target exists, and page4 has moved from manual confirmation into quantitative anchor replacement, and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0 and idp_page4_candidate_ready_now
            else
            "Commercial core is strong in measured families, IDP now retains a shadow-safe controlled commercial-pretest lane with same-scope reproducibility confirmed while any true broader rerun remains blocked until at least one extra anchor-backed target exists, "
            "and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0
            else
            "Commercial core is strong in measured families, IDP now retains a shadow-safe controlled commercial-pretest lane while any true broader rerun remains blocked until at least one extra anchor-backed target exists, "
            "and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
            if idp_pretest_decision_summary and idp_additional_anchor_backed_target_count == 0
            else "Commercial core is strong in measured families, IDP now retains a shadow-safe controlled commercial-pretest lane while broader promotion stays blocked, and all-category commercialization is still held back by expansion-family evidence maturity, especially transporter blocker-closure."
            + combined_transporter_story_tail
            + local_engine_story_tail
            + wetlab_story_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_blocker_note']}"
                if ligand_scaleup_summary["ligand_scaleup_blocker_note"]
                else ""
            )
        ),
        "next_required_step": (
            "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, run or monitor the admitted IDP one-wider shadow-safe repeatability rerun only, keep broader_full_idp_promotion blocked, and do not expand the IDP roster, loosen guardrails, or claim commercialization beyond that bounded lane; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if idp_broader_promotion_resolution_summary and idp_repeatability_summary
            else
            "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, retain IDP on the admitted one-wider shadow-safe lane only, keep broader_full_idp_promotion blocked, and do not expand the IDP roster, loosen guardrails, or claim commercialization beyond that bounded lane; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if idp_broader_promotion_resolution_summary
            else
            "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, and use the completed first broader shadow-only pass to reopen only the explicit promotion review rather than auto-widening the lane; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if idp_broader_decision_summary
            else
            "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 quantitative anchor replacement before any true broader rerun; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0 and idp_page4_candidate_ready_now
            else
            "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 manual-confirmation console before any true broader rerun; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0
            else
            "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, and do not call the next IDP run broader yet; either approve one same-scope process check on the validated 7-target literature-anchor subset or curate at least one additional anchor-backed target first; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
            if idp_pretest_decision_summary and idp_additional_anchor_backed_target_count == 0
            else "Keep GPCR as an apply-safe endpoint, keep ion/kinase as measured noop-shadow families, retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, use the broader-shadow review step to freeze promotion policy/roster/guardrails, and only then consider one broader full-IDP shadow rerun; "
            + combined_transporter_next_step_tail
            + local_engine_next_step_tail
            + wetlab_next_step_tail
            + glut1_second_wave_tail
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Commercialization Readiness",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- core_commercial_lane_score: `{summary['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{summary['all_category_expansion_score']}`",
        f"- strongest_ready_families: `{', '.join(summary['strongest_ready_families'])}`",
        f"- transporter_commercialization_closure_queue_ready: `{summary['transporter_commercialization_closure_queue_ready']}`",
        f"- transporter_commercialization_closure_queue_rows: `{summary['transporter_commercialization_closure_queue_rows']}`",
        f"- transporter_commercialization_top_queue_id: `{summary['transporter_commercialization_top_queue_id']}`",
        f"- transporter_placeholder_burndown_queue_ready: `{summary['transporter_placeholder_burndown_queue_ready']}`",
        f"- transporter_placeholder_burndown_queue_artifact: `{summary['transporter_placeholder_burndown_queue_artifact']}`",
        f"- transporter_placeholder_burndown_queue_rows: `{summary['transporter_placeholder_burndown_queue_rows']}`",
        f"- transporter_placeholder_burndown_queue_top_blocker_id: `{summary['transporter_placeholder_burndown_queue_top_blocker_id']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{summary['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{summary['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_row_count: `{summary['aqp1_negative_primary_probe_resolution_row_count']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{summary['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{summary['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{summary['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_next_required_step: `{summary['aqp1_negative_primary_probe_resolution_next_required_step']}`",
        f"- aqp1_first_wave_source_confirmation_artifact: `{summary['aqp1_first_wave_source_confirmation_artifact']}`",
        f"- aqp1_first_wave_follow_on_packet_artifact: `{summary['aqp1_first_wave_follow_on_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_ready: `{summary['aqp1_follow_on_source_confirmation_packet_ready']}`",
        f"- aqp1_follow_on_source_confirmation_packet_artifact: `{summary['aqp1_follow_on_source_confirmation_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_rows: `{summary['aqp1_follow_on_source_confirmation_packet_rows']}`",
        f"- aqp1_follow_on_source_confirmation_packet_primary_focus_ligand: `{summary['aqp1_follow_on_source_confirmation_packet_primary_focus_ligand']}`",
        f"- aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand: `{summary['aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_primary_focus_ligand: `{summary['aqp1_first_wave_primary_focus_ligand']}`",
        f"- aqp1_exact_human_reference_ligand: `{summary['aqp1_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_claim_safe_kcal_ready_count: `{summary['aqp1_first_wave_claim_safe_kcal_ready_count']}`",
        f"- aqp1_first_wave_follow_on_targets: `{summary['aqp1_first_wave_follow_on_targets']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets']}`",
        f"- aqp1_first_wave_follow_on_lane_label: `{summary['aqp1_first_wave_follow_on_lane_label']}`",
        f"- aqp1_first_wave_follow_on_row_count: `{summary['aqp1_first_wave_follow_on_row_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_artifact: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_row_count: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_row_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_claim_safe_kcal_ready_count: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_claim_safe_kcal_ready_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_next_required_step: `{summary['aqp1_first_wave_follow_on_blocker_decomposition_next_required_step']}`",
        f"- wetlab_execution_readiness_queue_ready: `{summary['wetlab_execution_readiness_queue_ready']}`",
        f"- wetlab_execution_readiness_queue_json: `{summary['wetlab_execution_readiness_queue_json']}`",
        f"- wetlab_execution_readiness_queue_csv: `{summary['wetlab_execution_readiness_queue_csv']}`",
        f"- wetlab_execution_readiness_queue_artifact: `{summary['wetlab_execution_readiness_queue_artifact']}`",
        f"- wetlab_execution_readiness_queue_top_priority_lane_id: `{summary['wetlab_execution_readiness_queue_top_priority_lane_id']}`",
        f"- wetlab_execution_readiness_queue_top_priority_status: `{summary['wetlab_execution_readiness_queue_top_priority_status']}`",
        f"- wetlab_execution_readiness_queue_status_line: `{summary['wetlab_execution_readiness_queue_status_line']}`",
        f"- wetlab_execution_readiness_queue_blocker_note: `{summary['wetlab_execution_readiness_queue_blocker_note']}`",
        f"- local_engine_commercialization_queue_ready: `{summary['local_engine_commercialization_queue_ready']}`",
        f"- local_engine_commercialization_queue_artifact: `{summary['local_engine_commercialization_queue_artifact']}`",
        f"- local_engine_commercialization_queue_top_priority_id: `{summary['local_engine_commercialization_queue_top_priority_id']}`",
        f"- local_engine_commercialization_queue_top_priority_status: `{summary['local_engine_commercialization_queue_top_priority_status']}`",
        f"- local_engine_commercialization_queue_blocked_count: `{summary['local_engine_commercialization_queue_blocked_count']}`",
        f"- local_engine_commercialization_queue_nightly_gate_burndown_artifact: `{summary['local_engine_commercialization_queue_nightly_gate_burndown_artifact']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_metric: `{summary['local_engine_commercialization_queue_nightly_gate_primary_metric']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_delta: `{summary['local_engine_commercialization_queue_nightly_gate_primary_delta']}`",
        f"- local_engine_commercialization_queue_blocker_note: `{summary['local_engine_commercialization_queue_blocker_note']}`",
        f"- ligand_scaleup_blocker_ready: `{summary['ligand_scaleup_blocker_ready']}`",
        f"- ligand_scaleup_blocked: `{summary['ligand_scaleup_blocked']}`",
        f"- ligand_scaleup_blocker_note: `{summary['ligand_scaleup_blocker_note']}`",
        f"- ligand_scaleup_next_required_step: `{summary['ligand_scaleup_next_required_step']}`",
        "",
        "## Interpretation",
        "",
        f"- {summary['main_platform_story']}",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Family Readiness",
        "",
        "| family | score | stage | status | claim_safe_scope | primary_blocker | source_artifact | supporting_artifact |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['score']} | `{row['stage']}` | `{row['status']}` | {row['claim_safe_scope']} | {row['primary_blocker']} | `{row['source_artifact']}` | `{row.get('supporting_artifact', '')}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a commercialization readiness assessment across protein families.")
    parser.add_argument("--crossfamily-json", default=DEFAULT_CROSSFAMILY_JSON)
    parser.add_argument("--gpcr-endpoint-json", default=DEFAULT_GPCR_ENDPOINT_JSON)
    parser.add_argument("--idp-decision-json", default=DEFAULT_IDP_DECISION_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-commercial-pretest-decision-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--transporter-closure-queue-json", default=DEFAULT_TRANSPORTER_CLOSURE_QUEUE_JSON)
    parser.add_argument("--aqp1-source-confirmation-json", default=DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--aqp1-follow-on-json", default=DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON)
    parser.add_argument(
        "--aqp1-follow-on-blocker-decomposition-json",
        default=DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON,
    )
    parser.add_argument(
        "--aqp1-follow-on-source-confirmation-packet-json",
        default=DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument(
        "--transporter-placeholder-burndown-queue-json",
        default=DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON,
    )
    parser.add_argument(
        "--aqp1-negative-primary-probe-resolution-json",
        default=DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON,
    )
    parser.add_argument(
        "--glut1-second-wave-source-confirmation-packet-json",
        default=DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument(
        "--local-engine-commercialization-queue-json",
        default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON,
    )
    parser.add_argument(
        "--wetlab-execution-readiness-queue-json",
        default=DEFAULT_WETLAB_EXECUTION_QUEUE_JSON,
    )
    parser.add_argument("--ligand-scaleup-suite-status-json", default=DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON)
    parser.add_argument(
        "--ligand-scaleup-benchmark-summary-json",
        default=DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON,
    )
    parser.add_argument("--idp-broader-shadow-decision-json", default=DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--idp-one-wider-repeatability-packet-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON)
    parser.add_argument("--idp-one-wider-repeatability-result-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.crossfamily_json),
        _load_json(args.gpcr_endpoint_json),
        _load_json(args.idp_decision_json),
        _load_json(args.idp_commercial_pretest_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.transporter_dashboard_json),
        _load_json(args.transporter_seed_row_board_json),
        _maybe_load_json(args.transporter_closure_queue_json),
        _maybe_load_json(args.idp_commercial_pretest_decision_json),
        _maybe_load_json(args.idp_broader_shadow_decision_json),
        _maybe_load_json(args.idp_broader_promotion_resolution_json),
        _maybe_load_json(args.idp_one_wider_repeatability_packet_json),
        _maybe_load_json(args.idp_one_wider_repeatability_result_json),
        _maybe_load_json(args.aqp1_source_confirmation_json),
        _maybe_load_json(args.aqp1_follow_on_json),
        _maybe_load_json(args.aqp1_follow_on_blocker_decomposition_json),
        _maybe_load_json(args.aqp1_follow_on_source_confirmation_packet_json),
        _maybe_load_json(args.transporter_placeholder_burndown_queue_json),
        _maybe_load_json(args.aqp1_negative_primary_probe_resolution_json),
        _maybe_load_json(args.glut1_second_wave_source_confirmation_packet_json),
        _maybe_load_json(args.ligand_scaleup_suite_status_json),
        _maybe_load_json(args.ligand_scaleup_benchmark_summary_json),
        _maybe_load_json(args.local_engine_commercialization_queue_json),
        _maybe_load_json(args.wetlab_execution_readiness_queue_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
