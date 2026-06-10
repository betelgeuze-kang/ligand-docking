#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import rows_by_family, write_csv_rows
from tools.ligand_scaleup_surface_helpers import (
    DEFAULT_GPCR_SCALEUP_GUARDRAIL_FRONTIER_JSON,
    DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON as LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON,
    DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON as LIGAND_SCALEUP_SUITE_STATUS_JSON,
    ligand_scaleup_summary_from_source,
    summarize_ligand_scaleup_blocker,
)
from tools.local_engine_surface_helpers import (
    DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON,
    local_engine_summary_from_source,
    summarize_local_engine_commercialization_queue,
)
from tools.wetlab.wetlab_surface_helpers import (
    DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON,
    summarize_wetlab_execution_readiness_queue,
    wetlab_summary_from_source,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_PRETEST_JSON = "runs/pretest_execution_readiness_current.json"
DEFAULT_CROSSFAMILY_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_EXECUTION_JSON = "runs/execution_handoff_dashboard_current.json"
DEFAULT_TRANSPORTER_CLOSURE_QUEUE_JSON = "runs/transporter_commercialization_closure_queue_current.json"
DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON = "runs/aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_AQP1_FUNCTIONAL_KCAL_SURROGATE_JSON = "runs/aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON = "runs/aqp1_negative_primary_probe_resolution_packet_current.json"
DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD = "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON
DEFAULT_WETLAB_EXECUTION_QUEUE_JSON = DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON
DEFAULT_LIGAND_SCALEUP_SUITE_STATUS_JSON = LIGAND_SCALEUP_SUITE_STATUS_JSON
DEFAULT_LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON = LIGAND_SCALEUP_BENCHMARK_SUMMARY_JSON
DEFAULT_GPCR_SCALEUP_FRONTIER_JSON = DEFAULT_GPCR_SCALEUP_GUARDRAIL_FRONTIER_JSON
DEFAULT_OUT_JSON = "runs/commercialization_gap_burndown_current.json"
DEFAULT_OUT_CSV = "runs/commercialization_gap_burndown_current.csv"
DEFAULT_OUT_MD = "runs/commercialization_gap_burndown_current.md"


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _signal_text(value: Any) -> str:
    return _text(value).replace("; ", ", ").replace(";", ", ")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _burndown_bucket(pretest_ready: str, claim_scope: str, blocker: str) -> str:
    if pretest_ready == "yes" and claim_scope == "yes":
        return "near_term"
    if pretest_ready == "yes" and claim_scope == "subset_only":
        return "subset_only"
    if pretest_ready == "partial":
        return "evidence_fill"
    if "router" in blocker.lower():
        return "optimization"
    return "blocked"


def _aqp1_source_confirmation_artifact(
    aqp1_source_confirmation_payload: dict[str, Any] | None,
    commercialization_summary: dict[str, Any],
) -> str:
    if aqp1_source_confirmation_payload:
        return "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    return str(commercialization_summary.get("aqp1_first_wave_source_confirmation_artifact", "")).strip()


def _aqp1_follow_on_packet_artifact(
    aqp1_follow_on_packet_payload: dict[str, Any] | None,
    commercialization_summary: dict[str, Any],
) -> str:
    if aqp1_follow_on_packet_payload:
        return "runs/aqp1_first_wave_follow_on_packet_current.md"
    return str(commercialization_summary.get("aqp1_first_wave_follow_on_packet_artifact", "")).strip()


def _aqp1_follow_on_blocker_decomposition_artifact(
    aqp1_follow_on_blocker_decomposition_payload: dict[str, Any] | None,
    commercialization_summary: dict[str, Any],
) -> str:
    if aqp1_follow_on_blocker_decomposition_payload:
        return "runs/aqp1_follow_on_blocker_decomposition_current.md"
    return str(
        commercialization_summary.get("aqp1_first_wave_follow_on_blocker_decomposition_artifact", "")
    ).strip()


def _aqp1_negative_primary_probe_resolution_artifact(
    aqp1_negative_primary_probe_resolution_payload: dict[str, Any] | None,
    commercialization_summary: dict[str, Any],
    execution_summary: dict[str, Any],
) -> str:
    payload_summary = dict((aqp1_negative_primary_probe_resolution_payload or {}).get("summary", {}) or {})
    if payload_summary:
        return _text(payload_summary.get("packet_artifact")) or DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD
    for summary in (commercialization_summary, execution_summary):
        artifact = _text(summary.get("aqp1_negative_primary_probe_resolution_artifact"))
        if artifact:
            return artifact
    return ""


def _follow_on_seed_targets(
    aqp1_follow_on_blocker_decomposition_summary: dict[str, Any],
    aqp1_follow_on_packet_summary: dict[str, Any],
    commercialization_summary: dict[str, Any],
    queue_summary: dict[str, Any],
) -> str:
    return str(
        aqp1_follow_on_blocker_decomposition_summary.get("follow_on_targets")
        or aqp1_follow_on_packet_summary.get("follow_on_targets")
        or aqp1_follow_on_packet_summary.get("aqp1_follow_on_targets")
        or commercialization_summary.get("aqp1_first_wave_follow_on_targets")
        or commercialization_summary.get("aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets")
        or commercialization_summary.get("aqp1_follow_on_seed_targets")
        or queue_summary.get("remaining_seed_targets")
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


def _aqp1_source_confirmation_clause(
    aqp1_source_confirmation_summary: dict[str, Any],
    primary_focus_ligand: str,
    exact_human_reference_ligand: str,
) -> str:
    next_required_step = str(aqp1_source_confirmation_summary.get("next_required_step", "") or "").strip()
    if next_required_step:
        return next_required_step
    if primary_focus_ligand and exact_human_reference_ligand:
        return (
            f"Review {primary_focus_ligand} first as the AQP1 core_binder_01 exact-source scope packet, keep "
            f"{exact_human_reference_ligand} as the exact-human-activity reference row, and leave "
            "replacement_reference_binding_kcal_mol blank."
        )
    if primary_focus_ligand:
        return (
            f"Review {primary_focus_ligand} first as the AQP1 core_binder_01 exact-source scope packet and leave "
            "replacement_reference_binding_kcal_mol blank."
        )
    return ""


def _closure_signal(
    family: str,
    execution_summary: dict[str, Any],
    queue_summary: dict[str, Any],
    aqp1_source_confirmation_artifact: str,
    aqp1_follow_on_packet_artifact: str,
    aqp1_follow_on_blocker_decomposition_artifact: str,
    aqp1_follow_on_blocker_decomposition_blocking_signal: str,
    aqp1_primary_focus_ligand: str,
    aqp1_exact_human_reference_ligand: str,
    aqp1_follow_on_targets: str,
    aqp1_follow_on_lane_label: str,
    aqp1_negative_primary_probe_resolution_artifact: str,
    aqp1_negative_primary_probe_resolution_candidate: str,
    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: str,
    aqp1_negative_primary_probe_resolution_decision: str,
    glut1_second_wave_primary_focus_ligand: str,
    glut1_second_wave_direct_quantitative_binding_count: int,
) -> str:
    if family == "transporter":
        base = (
            f"placeholder_rows={execution_summary.get('transporter_placeholder_driven_rows', 0)}; "
            f"seed_rows={execution_summary.get('transporter_seed_row_count', 0)}; "
            f"aqp1_focus={execution_summary.get('aqp1_quantitative_provenance_primary_focus_ligand', '')}; "
            f"aqp1_signal={execution_summary.get('aqp1_quantitative_provenance_signal', '')}"
        )
        if aqp1_source_confirmation_artifact:
            base += f"; source_confirmation_artifact={aqp1_source_confirmation_artifact}"
        if aqp1_follow_on_packet_artifact:
            base += f"; follow_on_artifact={aqp1_follow_on_packet_artifact}"
        if aqp1_follow_on_blocker_decomposition_artifact:
            base += f"; follow_on_blocker_decomposition_artifact={aqp1_follow_on_blocker_decomposition_artifact}"
        if aqp1_follow_on_blocker_decomposition_blocking_signal:
            base += f"; follow_on_blocker_decomposition_signal={aqp1_follow_on_blocker_decomposition_blocking_signal}"
        if aqp1_primary_focus_ligand:
            base += f"; first_wave_primary_focus={aqp1_primary_focus_ligand}"
        if aqp1_exact_human_reference_ligand:
            base += f"; exact_human_guardrail={aqp1_exact_human_reference_ligand}"
        if aqp1_follow_on_targets:
            base += f"; follow_on_targets={aqp1_follow_on_targets}"
        if aqp1_follow_on_lane_label:
            base += f"; follow_on_lane={aqp1_follow_on_lane_label}"
        if aqp1_negative_primary_probe_resolution_artifact:
            base += f"; negative_primary_probe_resolution_artifact={aqp1_negative_primary_probe_resolution_artifact}"
        if aqp1_negative_primary_probe_resolution_candidate:
            base += f"; negative_primary_probe_candidate={aqp1_negative_primary_probe_resolution_candidate}"
        if aqp1_negative_primary_probe_resolution_solvent_fallback_candidate:
            base += (
                f"; negative_primary_probe_solvent_fallback={aqp1_negative_primary_probe_resolution_solvent_fallback_candidate}"
            )
        if aqp1_negative_primary_probe_resolution_decision:
            base += f"; negative_primary_probe_resolution_decision={aqp1_negative_primary_probe_resolution_decision}"
        if glut1_second_wave_primary_focus_ligand:
            base += f"; glut1_second_wave_primary_focus={glut1_second_wave_primary_focus_ligand}"
        if glut1_second_wave_direct_quantitative_binding_count:
            base += f"; glut1_second_wave_direct_quantitative_binding_count={glut1_second_wave_direct_quantitative_binding_count}"
        if queue_summary:
            base += (
                f"; queue_rows={queue_summary.get('queue_row_count', 0)}; "
                f"top_queue_id={queue_summary.get('top_queue_id', '')}"
            )
        return base
    if family == "non_kinase_enzyme_ca2":
        return (
            f"direct_conflicts={execution_summary.get('ca2_direct_conflict_row_count', 0)}; "
            f"no_direct_negative={execution_summary.get('ca2_no_direct_negative_source_row_count', 0)}; "
            f"source_linked={execution_summary.get('ca2_source_linked_count', 0)}"
        )
    if family == "nuclear_receptor_pxr":
        return (
            f"review_only_candidate={execution_summary.get('pxr_review_only_candidate_count', 0)}; "
            f"must_defer={execution_summary.get('pxr_must_defer_count', 0)}; "
            f"confirmation_focus={execution_summary.get('pxr_confirmation_primary_focus_ligand', '')}; "
            f"low_prob_conflicts={execution_summary.get('evidence_acquisition_low_probability_conflict_count', 0)}"
        )
    if family == "idp":
        return "broader_full_idp_promotion_blocked; bounded_shadow_safe_lane_only"
    return ""


def _transporter_closure_queue_artifact(
    queue_payload: dict[str, Any],
    execution_summary: dict[str, Any],
) -> str:
    if queue_payload:
        return "runs/transporter_commercialization_closure_queue_current.md"
    for key in (
        "transporter_commercialization_closure_queue_artifact",
        "transporter_closure_queue_artifact",
        "transporter_blocker_capture_intake_artifact",
    ):
        artifact = str(execution_summary.get(key, "")).strip()
        if artifact:
            return artifact
    return "runs/transporter_commercialization_closure_queue_current.md"


def _next_burndown_action(
    family: str,
    pretest_row: dict[str, Any],
    execution_summary: dict[str, Any],
    queue_summary: dict[str, Any],
    aqp1_source_confirmation_summary: dict[str, Any],
    aqp1_primary_focus_ligand: str,
    aqp1_exact_human_reference_ligand: str,
    aqp1_follow_on_lane_label: str,
    aqp1_follow_on_blocker_decomposition_next_required_step: str,
    aqp1_negative_primary_probe_resolution_artifact: str,
    aqp1_negative_primary_probe_resolution_candidate: str,
    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: str,
    aqp1_negative_primary_probe_resolution_decision: str,
    aqp1_negative_primary_probe_resolution_next_required_step: str,
    glut1_second_wave_primary_focus_ligand: str,
) -> str:
    follow_on_blocker_decomposition_clause = (
        f" Use the AQP1 follow-on blocker decomposition: {aqp1_follow_on_blocker_decomposition_next_required_step}."
        if aqp1_follow_on_blocker_decomposition_next_required_step
        else ""
    )
    negative_primary_probe_resolution_clause = (
        (
            f" Keep {aqp1_negative_primary_probe_resolution_artifact or DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD} open as the AQP1 negative primary-probe-resolution handoff. "
            + aqp1_negative_primary_probe_resolution_next_required_step
        )
        if aqp1_negative_primary_probe_resolution_artifact and aqp1_negative_primary_probe_resolution_next_required_step
        else (
            f" Keep {aqp1_negative_primary_probe_resolution_candidate} review-only in the AQP1 negative primary-probe-resolution lane, "
            f"preserve {aqp1_negative_primary_probe_resolution_solvent_fallback_candidate} as solvent fallback only, "
            f"and hold the lane at {aqp1_negative_primary_probe_resolution_decision}."
            if aqp1_negative_primary_probe_resolution_candidate
            and aqp1_negative_primary_probe_resolution_solvent_fallback_candidate
            and aqp1_negative_primary_probe_resolution_decision
            else ""
        )
    )
    if family == "gpcr":
        return "Keep GPCR at the apply-safe endpoint and do not spend burndown time on router promotion until a future variant removes the remaining tiny PR regression."
    if family in {"ion_channel", "kinase"}:
        return "No urgent burndown action on the measured lane; preserve stability and use these families as commercial anchors."
    if family == "idp":
        return "Keep IDP on the current controlled commercial-pretest lane, using the literature-anchor subset as the validated basis while only expanding anchor-backed shadow slices with zero state/gate changes."
    if family == "non_kinase_enzyme_ca2":
        return (
            f"Keep CA2 in review-only conflict closure, preserve replacement_reference_binding_kcal_mol as blank, and work the {execution_summary.get('ca2_direct_conflict_row_count', 0)} direct-conflict rows before any commercialization promotion."
        )
    if family == "nuclear_receptor_pxr":
        return (
            f"Keep PXR partial-authoritative only, leave {execution_summary.get('pxr_must_defer_count', 0)} deferred rows parked, and use {execution_summary.get('pxr_confirmation_primary_focus_ligand', 'the current confirmation focus')} as the exact-source confirmation focus before any broader commercialization claim."
        )
    if family == "transporter":
        source_confirmation_clause = _aqp1_source_confirmation_clause(
            aqp1_source_confirmation_summary,
            aqp1_primary_focus_ligand,
            aqp1_exact_human_reference_ligand,
        )
        provenance_clause = _aqp1_provenance_clause(aqp1_exact_human_reference_ligand)
        follow_on_clause = (
            f" Park {_follow_on_lane_text(aqp1_follow_on_lane_label)} behind core_binder_01."
            if aqp1_follow_on_lane_label
            else ""
        )
        if queue_summary:
            queue_step = str(queue_summary.get("next_required_step", "")).strip()
            if queue_step and source_confirmation_clause:
                return (
                    f"{queue_step} {source_confirmation_clause}{provenance_clause}{follow_on_clause}{follow_on_blocker_decomposition_clause}"
                    + (f" {negative_primary_probe_resolution_clause}" if negative_primary_probe_resolution_clause else "")
                    + (
                        f" Keep {glut1_second_wave_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                        if glut1_second_wave_primary_focus_ligand
                        else ""
                    )
                ).strip()
            if "replacement_reference_binding_kcal_mol" in queue_step:
                return (
                    f"{queue_step}{provenance_clause}{follow_on_clause}{follow_on_blocker_decomposition_clause}"
                    + (f" {negative_primary_probe_resolution_clause}" if negative_primary_probe_resolution_clause else "")
                    + (
                        f" Keep {glut1_second_wave_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                        if glut1_second_wave_primary_focus_ligand
                        else ""
                    )
                ).strip()
            return (
                f"{queue_step} Keep replacement_reference_binding_kcal_mol blank until claim-safe "
                f"quantitative binding support exists.{provenance_clause}{follow_on_clause}{follow_on_blocker_decomposition_clause}"
                + (f" {negative_primary_probe_resolution_clause}" if negative_primary_probe_resolution_clause else "")
                + (
                    f" Keep {glut1_second_wave_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                    if glut1_second_wave_primary_focus_ligand
                    else ""
                )
            ).strip()
        if aqp1_primary_focus_ligand:
            return (
                "Keep transporter in seed-row blocker closure, use AQP1 core_binder_01 first, "
                f"confirm {aqp1_primary_focus_ligand} as the first-wave exact-source scope packet{provenance_clause}{follow_on_clause}, "
                "keep replacement_reference_binding_kcal_mol blank, "
                f"and reduce {execution_summary.get('transporter_placeholder_driven_rows', 0)} placeholder-driven rows "
                f"before revisiting donor policy or authoritative apply.{follow_on_blocker_decomposition_clause}"
                + (f" {negative_primary_probe_resolution_clause}" if negative_primary_probe_resolution_clause else "")
                + (
                    f" Keep {glut1_second_wave_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                    if glut1_second_wave_primary_focus_ligand
                    else ""
                )
            )
        return (
            "Keep transporter in seed-row blocker closure, use AQP1 core_binder_01 first"
            f"{provenance_clause}{follow_on_clause}, "
            f"keep replacement_reference_binding_kcal_mol blank, and reduce {execution_summary.get('transporter_placeholder_driven_rows', 0)} placeholder-driven rows before revisiting donor policy or authoritative apply.{follow_on_blocker_decomposition_clause}"
            + (f" {negative_primary_probe_resolution_clause}" if negative_primary_probe_resolution_clause else "")
            + (
                f" Keep {glut1_second_wave_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                if glut1_second_wave_primary_focus_ligand
                else ""
            )
        )
    return str(pretest_row.get("next_required_step", "")).strip()


def build_payload(
    commercialization_payload: dict[str, Any],
    pretest_payload: dict[str, Any],
    crossfamily_payload: dict[str, Any],
    execution_payload: dict[str, Any],
    transporter_closure_queue_payload: dict[str, Any],
    aqp1_source_confirmation_payload: dict[str, Any] | None = None,
    aqp1_follow_on_packet_payload: dict[str, Any] | None = None,
    aqp1_follow_on_blocker_decomposition_payload: dict[str, Any] | None = None,
    aqp1_follow_on_source_confirmation_packet_payload: dict[str, Any] | None = None,
    transporter_placeholder_burndown_queue_payload: dict[str, Any] | None = None,
    aqp1_functional_kcal_surrogate_payload: dict[str, Any] | None = None,
    aqp1_negative_primary_probe_resolution_payload: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation_packet_payload: dict[str, Any] | None = None,
    ligand_scaleup_suite_status_payload: dict[str, Any] | None = None,
    ligand_scaleup_benchmark_summary_payload: dict[str, Any] | None = None,
    gpcr_scaleup_frontier_payload: dict[str, Any] | None = None,
    local_engine_commercialization_queue_payload: dict[str, Any] | None = None,
    wetlab_execution_readiness_queue_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    commercialization_summary = dict(commercialization_payload.get("summary", {}) or {})
    comm_rows = rows_by_family(commercialization_payload)
    pretest_rows = rows_by_family(pretest_payload)
    cross_rows = rows_by_family(crossfamily_payload)
    execution_summary = dict(execution_payload.get("summary", {}) or {})
    transporter_closure_queue_summary = dict(transporter_closure_queue_payload.get("summary", {}) or {})
    aqp1_source_confirmation_summary = dict((aqp1_source_confirmation_payload or {}).get("summary", {}) or {})
    aqp1_follow_on_packet_summary = dict((aqp1_follow_on_packet_payload or {}).get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_summary = dict(
        (aqp1_follow_on_blocker_decomposition_payload or {}).get("summary", {}) or {}
    )
    aqp1_follow_on_source_confirmation_packet_summary = dict(
        (aqp1_follow_on_source_confirmation_packet_payload or {}).get("summary", {}) or {}
    )
    transporter_placeholder_burndown_queue_summary = dict(
        (transporter_placeholder_burndown_queue_payload or {}).get("summary", {}) or {}
    )
    aqp1_functional_kcal_surrogate_summary = dict(
        (aqp1_functional_kcal_surrogate_payload or {}).get("summary", {}) or {}
    )
    aqp1_negative_primary_probe_resolution_summary = dict(
        (aqp1_negative_primary_probe_resolution_payload or {}).get("summary", {}) or {}
    )
    glut1_second_wave_source_confirmation_packet_summary = dict(
        (glut1_second_wave_source_confirmation_packet_payload or {}).get("summary", {}) or {}
    )
    ligand_scaleup_summary = summarize_ligand_scaleup_blocker(
        ligand_scaleup_suite_status_payload,
        ligand_scaleup_benchmark_summary_payload,
        gpcr_scaleup_frontier_payload,
    )
    if not ligand_scaleup_summary["ligand_scaleup_blocker_ready"]:
        ligand_scaleup_summary = ligand_scaleup_summary_from_source(commercialization_summary)
    if not ligand_scaleup_summary["ligand_scaleup_blocker_ready"]:
        ligand_scaleup_summary = ligand_scaleup_summary_from_source(execution_summary)
    local_engine_summary = summarize_local_engine_commercialization_queue(
        local_engine_commercialization_queue_payload
    )
    if not local_engine_summary["local_engine_commercialization_queue_ready"]:
        local_engine_summary = local_engine_summary_from_source(commercialization_summary)
    if not local_engine_summary["local_engine_commercialization_queue_ready"]:
        local_engine_summary = local_engine_summary_from_source(execution_summary)
    wetlab_summary = summarize_wetlab_execution_readiness_queue(
        wetlab_execution_readiness_queue_payload
    )
    if not wetlab_summary["wetlab_execution_readiness_queue_ready"]:
        wetlab_summary = wetlab_summary_from_source(commercialization_summary)
    if not wetlab_summary["wetlab_execution_readiness_queue_ready"]:
        wetlab_summary = wetlab_summary_from_source(execution_summary)
    transporter_closure_queue_artifact = _transporter_closure_queue_artifact(
        transporter_closure_queue_payload,
        execution_summary,
    )
    aqp1_source_confirmation_artifact = _aqp1_source_confirmation_artifact(
        aqp1_source_confirmation_payload,
        commercialization_summary,
    )
    aqp1_follow_on_packet_artifact = _aqp1_follow_on_packet_artifact(
        aqp1_follow_on_packet_payload,
        commercialization_summary,
    )
    aqp1_follow_on_blocker_decomposition_artifact = _aqp1_follow_on_blocker_decomposition_artifact(
        aqp1_follow_on_blocker_decomposition_payload,
        commercialization_summary,
    )
    aqp1_follow_on_source_confirmation_packet_artifact = _artifact_for(
        "runs/aqp1_follow_on_source_confirmation_packet_current.md",
        aqp1_follow_on_source_confirmation_packet_payload,
    )
    transporter_placeholder_burndown_queue_artifact = _artifact_for(
        "runs/transporter_placeholder_burndown_queue_current.md",
        transporter_placeholder_burndown_queue_payload,
    )
    aqp1_functional_kcal_surrogate_artifact = _artifact_for(
        "runs/aqp1_functional_kcal_surrogate_packet_current.md",
        aqp1_functional_kcal_surrogate_payload,
    )
    aqp1_negative_primary_probe_resolution_artifact = _aqp1_negative_primary_probe_resolution_artifact(
        aqp1_negative_primary_probe_resolution_payload,
        commercialization_summary,
        execution_summary,
    )
    aqp1_negative_primary_probe_resolution_row_count = _int(
        aqp1_negative_primary_probe_resolution_summary.get(
            "row_count",
            commercialization_summary.get("aqp1_negative_primary_probe_resolution_row_count", 0),
        )
    )
    aqp1_negative_primary_probe_resolution_candidate = _text(
        aqp1_negative_primary_probe_resolution_summary.get(
            "primary_probe_candidate",
            commercialization_summary.get("aqp1_negative_primary_probe_resolution_candidate", ""),
        )
        or execution_summary.get("aqp1_negative_primary_probe_resolution_candidate", "")
    )
    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate = _text(
        aqp1_negative_primary_probe_resolution_summary.get(
            "solvent_fallback_candidate",
            commercialization_summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", ""),
        )
        or execution_summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "")
    )
    aqp1_negative_primary_probe_resolution_decision = _text(
        aqp1_negative_primary_probe_resolution_summary.get(
            "resolution_decision",
            commercialization_summary.get("aqp1_negative_primary_probe_resolution_decision", ""),
        )
        or execution_summary.get("aqp1_negative_primary_probe_resolution_decision", "")
    )
    aqp1_negative_primary_probe_resolution_next_required_step = _text(
        aqp1_negative_primary_probe_resolution_summary.get(
            "next_required_step",
            commercialization_summary.get("aqp1_negative_primary_probe_resolution_next_required_step", ""),
        )
        or execution_summary.get("aqp1_negative_primary_probe_resolution_next_required_step", "")
    )
    glut1_second_wave_source_confirmation_packet_artifact = _artifact_for(
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        glut1_second_wave_source_confirmation_packet_payload,
    )
    glut1_second_wave_source_confirmation_packet_primary_focus_ligand = _text(
        glut1_second_wave_source_confirmation_packet_summary.get("primary_focus_ligand", "")
    )
    glut1_second_wave_direct_quantitative_binding_count = _int(
        glut1_second_wave_source_confirmation_packet_summary.get("direct_quantitative_binding_count", 0)
    )
    aqp1_first_wave_primary_focus_ligand = str(
        aqp1_source_confirmation_summary.get(
            "primary_focus_ligand",
            commercialization_summary.get(
                "aqp1_first_wave_primary_focus_ligand",
                transporter_closure_queue_summary.get("aqp1_source_confirmation_primary_focus_ligand", ""),
            ),
        )
        or ""
    ).strip()
    aqp1_exact_human_reference_ligand = str(
        aqp1_source_confirmation_summary.get(
            "exact_human_reference_ligand",
            commercialization_summary.get(
                "aqp1_exact_human_reference_ligand",
                execution_summary.get("aqp1_quantitative_provenance_primary_focus_ligand", ""),
            ),
        )
        or ""
    ).strip()
    aqp1_follow_on_targets = _follow_on_seed_targets(
        aqp1_follow_on_blocker_decomposition_summary,
        aqp1_follow_on_packet_summary,
        commercialization_summary,
        transporter_closure_queue_summary,
    )
    aqp1_follow_on_blocker_decomposition_follow_on_targets = _text(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "follow_on_targets",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets",
                aqp1_follow_on_targets,
            ),
        )
    )
    aqp1_follow_on_lane_label = _follow_on_lane_label(aqp1_follow_on_targets)
    aqp1_follow_on_blocker_decomposition_row_count = _int(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "blocker_row_count",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_row_count",
                aqp1_follow_on_packet_summary.get("row_count", 0),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_primary_focus_ligand = _text(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "primary_focus_ligand",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand",
                aqp1_follow_on_packet_summary.get("primary_focus_ligand", ""),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand = _text(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_human_guardrail_ligand",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand",
                aqp1_follow_on_packet_summary.get("exact_human_guardrail_ligand", ""),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count = _int(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_human_nonbinding_count",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count",
                0,
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count = _int(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "exact_target_pair_absent_count",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count",
                0,
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_next_required_step = _text(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "next_required_step",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_next_required_step",
                "",
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_blocking_signal = _text(
        aqp1_follow_on_blocker_decomposition_summary.get(
            "blocking_signal",
            commercialization_summary.get(
                "aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal",
                "",
            ),
        )
    )
    aqp1_follow_on_row_count = aqp1_follow_on_blocker_decomposition_row_count or int(
        aqp1_follow_on_packet_summary.get("row_count", 0) or 0
    )
    aqp1_source_confirmation_claim_safe_kcal_ready_count = int(
        aqp1_source_confirmation_summary.get(
            "claim_safe_kcal_ready_count",
            commercialization_summary.get("aqp1_first_wave_claim_safe_kcal_ready_count", 0),
        )
        or 0
    )
    aqp1_source_confirmation_clause = _aqp1_source_confirmation_clause(
        aqp1_source_confirmation_summary,
        aqp1_first_wave_primary_focus_ligand,
        aqp1_exact_human_reference_ligand,
    )
    aqp1_operator_provenance_note = (
        f"{aqp1_exact_human_reference_ligand or 'AqB013'} exact human AQP1 target-activity provenance, kcal blank; "
        "replacement_reference_binding_kcal_mol remains blank until claim-safe quantitative binding is curated."
    )
    transporter_placeholder_driven_rows = _int(
        transporter_placeholder_burndown_queue_summary.get(
            "placeholder_driven_rows",
            execution_summary.get("transporter_placeholder_driven_rows", 0),
        )
    )
    transporter_ready_for_apply_rows = _int(
        transporter_placeholder_burndown_queue_summary.get("ready_for_apply_rows", 0)
    )
    aqp1_functional_kcal_surrogate_ready_count = _int(
        aqp1_functional_kcal_surrogate_summary.get("functional_kcal_surrogate_ready_count", 0)
    )
    aqp1_functional_kcal_surrogate_closure_allowed = bool(
        aqp1_functional_kcal_surrogate_summary.get("functional_kcal_surrogate_closure_allowed", False)
    )
    aqp1_direct_binding_gap_still_open = bool(
        aqp1_functional_kcal_surrogate_summary.get("direct_binding_gap_still_open", False)
    )
    aqp1_functional_kcal_next_required_step = _text(
        aqp1_functional_kcal_surrogate_summary.get("next_required_step", "")
    )

    rows: list[dict[str, Any]] = []
    for family, comm in comm_rows.items():
        pre = pretest_rows.get(family, {})
        cross = cross_rows.get(family, {})
        score = int(comm.get("score", 0) or 0)
        score_gap = max(0, 100 - score)
        pretest_ready = str(pre.get("pretest_ready", "")).strip()
        claim_scope = str(pre.get("claim_safe_test_ready", "")).strip()
        blocker = str(pre.get("primary_blocker", comm.get("primary_blocker", ""))).strip()
        bucket = _burndown_bucket(pretest_ready, claim_scope, blocker)
        rows.append(
            {
                "family": family,
                "commercialization_score": score,
                "score_gap_to_100": score_gap,
                "pretest_ready": pretest_ready,
                "claim_safe_test_ready": claim_scope,
                "current_state": str(pre.get("current_state", cross.get("current_state", ""))).strip(),
                "primary_blocker": blocker,
                "burndown_bucket": bucket,
                "burndown_priority": (
                    1 if family == "transporter"
                    else 2 if family in {"non_kinase_enzyme_ca2", "nuclear_receptor_pxr"}
                    else 3 if family == "idp"
                    else 4
                ),
                "commercialization_closure_queue_artifact": transporter_closure_queue_artifact if family == "transporter" else "",
                "source_confirmation_artifact": aqp1_source_confirmation_artifact if family == "transporter" else "",
                "closure_signal": _closure_signal(
                    family,
                    execution_summary,
                    transporter_closure_queue_summary,
                    aqp1_source_confirmation_artifact,
                    aqp1_follow_on_packet_artifact,
                    aqp1_follow_on_blocker_decomposition_artifact,
                    aqp1_follow_on_blocker_decomposition_blocking_signal,
                    aqp1_first_wave_primary_focus_ligand,
                    aqp1_exact_human_reference_ligand,
                    aqp1_follow_on_targets,
                    aqp1_follow_on_lane_label,
                    aqp1_negative_primary_probe_resolution_artifact,
                    aqp1_negative_primary_probe_resolution_candidate,
                    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate,
                    aqp1_negative_primary_probe_resolution_decision,
                    glut1_second_wave_source_confirmation_packet_primary_focus_ligand,
                    glut1_second_wave_direct_quantitative_binding_count,
                ),
                "next_burndown_action": _next_burndown_action(
                    family,
                    pre,
                    execution_summary,
                    transporter_closure_queue_summary,
                    aqp1_source_confirmation_summary,
                    aqp1_first_wave_primary_focus_ligand,
                    aqp1_exact_human_reference_ligand,
                    aqp1_follow_on_lane_label,
                    aqp1_follow_on_blocker_decomposition_next_required_step,
                    aqp1_negative_primary_probe_resolution_artifact,
                    aqp1_negative_primary_probe_resolution_candidate,
                    aqp1_negative_primary_probe_resolution_solvent_fallback_candidate,
                    aqp1_negative_primary_probe_resolution_decision,
                    aqp1_negative_primary_probe_resolution_next_required_step,
                    glut1_second_wave_source_confirmation_packet_primary_focus_ligand,
                ),
                "source_artifact": str(comm.get("source_artifact", "")).strip(),
            }
        )
        if family == "transporter" and local_engine_summary["local_engine_commercialization_queue_blocker_signal"]:
            rows[-1]["closure_signal"] += (
                f"; {local_engine_summary['local_engine_commercialization_queue_blocker_signal']}"
            )
        if family == "transporter" and wetlab_summary["wetlab_execution_readiness_queue_blocker_signal"]:
            rows[-1]["closure_signal"] += (
                f"; {wetlab_summary['wetlab_execution_readiness_queue_blocker_signal']}"
            )
        if family == "transporter" and wetlab_summary["wetlab_execution_readiness_queue_top_priority_signal"]:
            rows[-1]["closure_signal"] += (
                f"; wetlab_top_priority_signal={_signal_text(wetlab_summary['wetlab_execution_readiness_queue_top_priority_signal'])}"
            )
        if family == "transporter" and wetlab_summary["wetlab_execution_readiness_queue_selected_allatom_block_reason"]:
            rows[-1]["closure_signal"] += (
                "; wetlab_selected_allatom_block_reason="
                f"{wetlab_summary['wetlab_execution_readiness_queue_selected_allatom_block_reason']}"
            )
        if family == "transporter":
            if aqp1_functional_kcal_surrogate_artifact:
                rows[-1]["closure_signal"] += (
                    f"; aqp1_functional_kcal_surrogate_artifact={aqp1_functional_kcal_surrogate_artifact}; "
                    f"aqp1_functional_kcal_surrogate_ready_count={aqp1_functional_kcal_surrogate_ready_count}; "
                    f"aqp1_functional_kcal_surrogate_closure_allowed={aqp1_functional_kcal_surrogate_closure_allowed}; "
                    f"aqp1_direct_binding_gap_still_open={aqp1_direct_binding_gap_still_open}"
                )
            if aqp1_functional_kcal_next_required_step:
                rows[-1]["next_burndown_action"] += f" {aqp1_functional_kcal_next_required_step}"
            local_engine_next_step = str(
                local_engine_summary.get("local_engine_commercialization_queue_next_required_step", "") or ""
            ).strip()
            local_engine_note = str(
                local_engine_summary.get("local_engine_commercialization_queue_blocker_note", "") or ""
            ).strip()
            if local_engine_next_step:
                rows[-1]["next_burndown_action"] += f" {local_engine_next_step}"
            elif local_engine_note:
                rows[-1]["next_burndown_action"] += f" {local_engine_note}"
            wetlab_next_step = str(
                wetlab_summary.get("wetlab_execution_readiness_queue_next_required_step", "") or ""
            ).strip()
            wetlab_note = str(
                wetlab_summary.get("wetlab_execution_readiness_queue_blocker_note", "") or ""
            ).strip()
            if wetlab_next_step:
                rows[-1]["next_burndown_action"] += f" {wetlab_next_step}"
            elif wetlab_note:
                rows[-1]["next_burndown_action"] += f" {wetlab_note}"
        if family == "transporter" and ligand_scaleup_summary["ligand_scaleup_blocker_signal"]:
            rows[-1]["closure_signal"] += f"; {ligand_scaleup_summary['ligand_scaleup_blocker_signal']}"
        if family == "transporter" and ligand_scaleup_summary["ligand_scaleup_next_required_step"]:
            rows[-1]["next_burndown_action"] += f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"

    rows.sort(key=lambda row: (row["burndown_priority"], -row["score_gap_to_100"], row["family"]))
    local_engine_queue_clear = bool(
        local_engine_summary.get("local_engine_commercialization_queue_clear", False)
    ) or (
        bool(local_engine_summary.get("local_engine_commercialization_queue_ready", False))
        and _int(local_engine_summary.get("local_engine_commercialization_queue_blocked_count")) == 0
        and _int(local_engine_summary.get("local_engine_commercialization_queue_partial_count")) == 0
        and _int(local_engine_summary.get("local_engine_commercialization_queue_parked_science_blocker_count")) == 0
    )
    transporter_placeholder_accounting_closed = (
        bool(transporter_placeholder_burndown_queue_summary)
        and transporter_placeholder_driven_rows == 0
        and transporter_ready_for_apply_rows > 0
    )
    aqp1_functional_surrogate_accounting_closed = (
        bool(aqp1_functional_kcal_surrogate_closure_allowed)
        and aqp1_functional_kcal_surrogate_ready_count > 0
    )
    tracked_gap_accounting_closed = (
        local_engine_queue_clear
        and transporter_placeholder_accounting_closed
        and aqp1_functional_surrogate_accounting_closed
    )
    if tracked_gap_accounting_closed:
        for row in rows:
            if row["family"] == "transporter":
                row["closure_signal"] += (
                    "; transporter_placeholder_accounting_closed=True; "
                    "aqp1_functional_surrogate_accounting_closed=True; local_engine_queue_clear=True"
                )
                row["next_burndown_action"] = (
                    "Transporter placeholder and AQP1 functional-surrogate accounting are closed; keep direct-binding kcal "
                    "claims blank and carry transporter/AQP1 evidence as guarded provenance."
                )
                break
    highest_gap_family = "none_tracked_commercialization_gap" if tracked_gap_accounting_closed else (rows[0]["family"] if rows else "")
    raw_blocked_count = sum(1 for row in rows if row["burndown_bucket"] == "blocked")
    active_blocked_count = 0 if tracked_gap_accounting_closed else raw_blocked_count
    parked_or_review_only_blocked_count = raw_blocked_count if tracked_gap_accounting_closed else 0
    next_required_step = (
        "All tracked commercialization gap accounting blockers are closed; keep local-engine keep-green history, "
        "transporter authoritative-apply provenance, AQP1 functional-surrogate no-direct-binding guardrails, and wetlab readiness evidence attached."
        if tracked_gap_accounting_closed
        else (
            (
                "Use this board to burn down commercialization gaps in order: CA2/PXR evidence closure next, then IDP broader-scope risk, while preserving GPCR/ion/kinase as the stable commercial core. "
                f"Transporter negative placeholders are closed and AQP1 has {aqp1_functional_kcal_surrogate_ready_count} functional kcal surrogate rows; keep direct binding kcal claims blank."
                if transporter_placeholder_driven_rows == 0 and aqp1_functional_kcal_surrogate_closure_allowed
                else (
                    "Use this board to burn down commercialization gaps in order: transporter first, then CA2/PXR evidence closure, then IDP broader-scope risk, while preserving GPCR/ion/kinase as the stable commercial core. "
                    f"Start by reducing transporter placeholder-driven rows ({transporter_placeholder_driven_rows}) while keeping the queue order intact: AQP1 core_binder_01 first, "
                    f"{aqp1_exact_human_reference_ligand or 'AqB013'} exact human AQP1 target-activity provenance, kcal blank, then "
                    f"{aqp1_follow_on_lane_label or 'core_binder_02/03'} as the follow-on AQP1 lane."
                )
            )
            + (f" {aqp1_source_confirmation_clause}" if aqp1_source_confirmation_clause else "")
            + (
                f" {aqp1_operator_provenance_note}"
                if aqp1_operator_provenance_note and aqp1_operator_provenance_note not in aqp1_source_confirmation_clause
                else ""
            )
            + (
                f" Use the AQP1 follow-on blocker decomposition: {aqp1_follow_on_blocker_decomposition_next_required_step}."
                if aqp1_follow_on_blocker_decomposition_next_required_step
                else ""
            )
            + (
                " Keep "
                f"{aqp1_negative_primary_probe_resolution_artifact or DEFAULT_AQP1_NEGATIVE_PRIMARY_PROBE_RESOLUTION_MD} "
                "open as the AQP1 negative primary-probe-resolution handoff. "
                + aqp1_negative_primary_probe_resolution_next_required_step
                if aqp1_negative_primary_probe_resolution_artifact
                and aqp1_negative_primary_probe_resolution_next_required_step
                else ""
            )
            + (
                f" {aqp1_functional_kcal_next_required_step}"
                if aqp1_functional_kcal_next_required_step
                else ""
            )
            + (
                f" {local_engine_summary['local_engine_commercialization_queue_next_required_step']}"
                if local_engine_summary["local_engine_commercialization_queue_next_required_step"]
                else (
                    f" {local_engine_summary['local_engine_commercialization_queue_blocker_note']}"
                    if local_engine_summary["local_engine_commercialization_queue_blocker_note"]
                    else ""
                )
            )
            + (
                f" {wetlab_summary['wetlab_execution_readiness_queue_next_required_step']}"
                if wetlab_summary["wetlab_execution_readiness_queue_next_required_step"]
                else (
                    f" {wetlab_summary['wetlab_execution_readiness_queue_blocker_note']}"
                    if wetlab_summary["wetlab_execution_readiness_queue_blocker_note"]
                    else ""
                )
            )
            + (
                f" {ligand_scaleup_summary['ligand_scaleup_next_required_step']}"
                if ligand_scaleup_summary["ligand_scaleup_next_required_step"]
                else ""
            )
        )
    )
    summary = {
        "family_count": len(rows),
        "core_commercial_lane_score": commercialization_payload.get("summary", {}).get("core_commercial_lane_score", ""),
        "all_category_expansion_score": commercialization_payload.get("summary", {}).get("all_category_expansion_score", ""),
        "near_term_count": sum(1 for row in rows if row["burndown_bucket"] == "near_term"),
        "subset_only_count": sum(1 for row in rows if row["burndown_bucket"] == "subset_only"),
        "evidence_fill_count": sum(1 for row in rows if row["burndown_bucket"] == "evidence_fill"),
        "optimization_count": sum(1 for row in rows if row["burndown_bucket"] == "optimization"),
        "blocked_count": active_blocked_count,
        "raw_blocked_bucket_count": raw_blocked_count,
        "parked_or_review_only_blocked_count": parked_or_review_only_blocked_count,
        "highest_gap_family": highest_gap_family,
        "tracked_gap_accounting_closed": tracked_gap_accounting_closed,
        "transporter_placeholder_accounting_closed": transporter_placeholder_accounting_closed,
        "aqp1_functional_surrogate_accounting_closed": aqp1_functional_surrogate_accounting_closed,
        "local_engine_commercialization_queue_clear": local_engine_queue_clear,
        **wetlab_summary,
        **local_engine_summary,
        **ligand_scaleup_summary,
        "transporter_placeholder_driven_rows": transporter_placeholder_driven_rows,
        "transporter_placeholder_driven_rows_current": transporter_placeholder_driven_rows,
        "transporter_placeholder_driven_rows_legacy_execution": execution_summary.get("transporter_placeholder_driven_rows", 0),
        "transporter_ready_for_apply_rows_current": transporter_ready_for_apply_rows,
        "transporter_commercialization_closure_queue_artifact": transporter_closure_queue_artifact,
        "transporter_commercialization_closure_queue_rows": transporter_closure_queue_summary.get("queue_row_count", 0),
        "transporter_commercialization_top_queue_id": transporter_closure_queue_summary.get("top_queue_id", ""),
        "transporter_placeholder_burndown_queue_ready": bool(transporter_placeholder_burndown_queue_summary),
        "transporter_placeholder_burndown_queue_artifact": transporter_placeholder_burndown_queue_artifact,
        "transporter_placeholder_burndown_queue_rows": transporter_placeholder_burndown_queue_summary.get("queue_row_count", 0),
        "transporter_placeholder_burndown_queue_top_blocker_id": transporter_placeholder_burndown_queue_summary.get(
            "top_blocker_id", ""
        ),
        "aqp1_functional_kcal_surrogate_ready": bool(aqp1_functional_kcal_surrogate_summary),
        "aqp1_functional_kcal_surrogate_artifact": aqp1_functional_kcal_surrogate_artifact,
        "aqp1_functional_kcal_surrogate_ready_count": aqp1_functional_kcal_surrogate_ready_count,
        "aqp1_functional_kcal_surrogate_closure_allowed": aqp1_functional_kcal_surrogate_closure_allowed,
        "aqp1_direct_binding_gap_still_open": aqp1_direct_binding_gap_still_open,
        "aqp1_negative_primary_probe_resolution_ready": bool(
            aqp1_negative_primary_probe_resolution_artifact
            or aqp1_negative_primary_probe_resolution_summary
        ),
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
        "aqp1_first_wave_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
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
        "aqp1_first_wave_claim_safe_kcal_ready_count": aqp1_source_confirmation_claim_safe_kcal_ready_count,
        "aqp1_first_wave_follow_on_targets": aqp1_follow_on_targets,
        "aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets": aqp1_follow_on_blocker_decomposition_follow_on_targets,
        "aqp1_first_wave_follow_on_lane_label": aqp1_follow_on_lane_label,
        "aqp1_first_wave_follow_on_row_count": aqp1_follow_on_row_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_row_count": aqp1_follow_on_blocker_decomposition_row_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand": aqp1_follow_on_blocker_decomposition_primary_focus_ligand,
        "aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand": aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand,
        "aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count": aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count": aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count,
        "aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal": aqp1_follow_on_blocker_decomposition_blocking_signal,
        "aqp1_first_wave_follow_on_blocker_decomposition_next_required_step": aqp1_follow_on_blocker_decomposition_next_required_step,
        "aqp1_focus_ligand": execution_summary.get("aqp1_quantitative_provenance_primary_focus_ligand", ""),
        "aqp1_operator_provenance_note": aqp1_operator_provenance_note,
        "ca2_direct_conflict_row_count": execution_summary.get("ca2_direct_conflict_row_count", 0),
        "ca2_direct_conflict_parked_review_only_count": execution_summary.get(
            "ca2_direct_conflict_parked_review_only_count", 0
        ),
        "ca2_direct_conflict_active_blocker_count": execution_summary.get("ca2_direct_conflict_active_blocker_count", 0),
        "pxr_must_defer_count": execution_summary.get("pxr_must_defer_count", 0),
        "pxr_must_defer_parked_review_only_count": execution_summary.get("pxr_must_defer_parked_review_only_count", 0),
        "pxr_must_defer_active_blocker_count": execution_summary.get("pxr_must_defer_active_blocker_count", 0),
        "science_lane_parked_review_only_count": execution_summary.get("science_lane_parked_review_only_count", 0),
        "science_lane_active_blocker_count": execution_summary.get("science_lane_active_blocker_count", 0),
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Commercialization Gap Burndown",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        f"- near_term_count: `{s['near_term_count']}`",
        f"- subset_only_count: `{s['subset_only_count']}`",
        f"- evidence_fill_count: `{s['evidence_fill_count']}`",
        f"- optimization_count: `{s['optimization_count']}`",
        f"- blocked_count: `{s['blocked_count']}`",
        f"- raw_blocked_bucket_count: `{s['raw_blocked_bucket_count']}`",
        f"- parked_or_review_only_blocked_count: `{s['parked_or_review_only_blocked_count']}`",
        f"- highest_gap_family: `{s['highest_gap_family']}`",
        f"- tracked_gap_accounting_closed: `{s['tracked_gap_accounting_closed']}`",
        f"- transporter_placeholder_accounting_closed: `{s['transporter_placeholder_accounting_closed']}`",
        f"- aqp1_functional_surrogate_accounting_closed: `{s['aqp1_functional_surrogate_accounting_closed']}`",
        f"- local_engine_commercialization_queue_clear: `{s['local_engine_commercialization_queue_clear']}`",
        f"- wetlab_execution_readiness_queue_ready: `{s['wetlab_execution_readiness_queue_ready']}`",
        f"- wetlab_execution_readiness_queue_json: `{s['wetlab_execution_readiness_queue_json']}`",
        f"- wetlab_execution_readiness_queue_csv: `{s['wetlab_execution_readiness_queue_csv']}`",
        f"- wetlab_execution_readiness_queue_artifact: `{s['wetlab_execution_readiness_queue_artifact']}`",
        f"- wetlab_execution_readiness_queue_top_priority_lane_id: `{s['wetlab_execution_readiness_queue_top_priority_lane_id']}`",
        f"- wetlab_execution_readiness_queue_top_priority_status: `{s['wetlab_execution_readiness_queue_top_priority_status']}`",
        f"- wetlab_execution_readiness_queue_blocked_count: `{s['wetlab_execution_readiness_queue_blocked_count']}`",
        f"- wetlab_execution_readiness_queue_top_priority_signal: `{s['wetlab_execution_readiness_queue_top_priority_signal']}`",
        f"- wetlab_execution_readiness_queue_status_line: `{s['wetlab_execution_readiness_queue_status_line']}`",
        f"- wetlab_execution_readiness_queue_selected_allatom_block_reason: `{s['wetlab_execution_readiness_queue_selected_allatom_block_reason']}`",
        f"- wetlab_execution_readiness_queue_blocker_note: `{s['wetlab_execution_readiness_queue_blocker_note']}`",
        f"- local_engine_commercialization_queue_ready: `{s['local_engine_commercialization_queue_ready']}`",
        f"- local_engine_commercialization_queue_artifact: `{s['local_engine_commercialization_queue_artifact']}`",
        f"- local_engine_commercialization_queue_top_priority_id: `{s['local_engine_commercialization_queue_top_priority_id']}`",
        f"- local_engine_commercialization_queue_top_priority_status: `{s['local_engine_commercialization_queue_top_priority_status']}`",
        f"- local_engine_commercialization_queue_blocked_count: `{s['local_engine_commercialization_queue_blocked_count']}`",
        f"- local_engine_commercialization_queue_nightly_gate_burndown_artifact: `{s['local_engine_commercialization_queue_nightly_gate_burndown_artifact']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_metric: `{s['local_engine_commercialization_queue_nightly_gate_primary_metric']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_delta: `{s['local_engine_commercialization_queue_nightly_gate_primary_delta']}`",
        f"- local_engine_commercialization_queue_blocker_note: `{s['local_engine_commercialization_queue_blocker_note']}`",
        f"- transporter_placeholder_driven_rows: `{s['transporter_placeholder_driven_rows']}`",
        f"- transporter_placeholder_driven_rows_current: `{s['transporter_placeholder_driven_rows_current']}`",
        f"- transporter_placeholder_driven_rows_legacy_execution: `{s['transporter_placeholder_driven_rows_legacy_execution']}`",
        f"- transporter_ready_for_apply_rows_current: `{s['transporter_ready_for_apply_rows_current']}`",
        f"- transporter_commercialization_closure_queue_artifact: `{s['transporter_commercialization_closure_queue_artifact']}`",
        f"- transporter_commercialization_closure_queue_rows: `{s['transporter_commercialization_closure_queue_rows']}`",
        f"- transporter_commercialization_top_queue_id: `{s['transporter_commercialization_top_queue_id']}`",
        f"- transporter_placeholder_burndown_queue_ready: `{s['transporter_placeholder_burndown_queue_ready']}`",
        f"- transporter_placeholder_burndown_queue_artifact: `{s['transporter_placeholder_burndown_queue_artifact']}`",
        f"- transporter_placeholder_burndown_queue_rows: `{s['transporter_placeholder_burndown_queue_rows']}`",
        f"- transporter_placeholder_burndown_queue_top_blocker_id: `{s['transporter_placeholder_burndown_queue_top_blocker_id']}`",
        f"- aqp1_functional_kcal_surrogate_ready: `{s['aqp1_functional_kcal_surrogate_ready']}`",
        f"- aqp1_functional_kcal_surrogate_artifact: `{s['aqp1_functional_kcal_surrogate_artifact']}`",
        f"- aqp1_functional_kcal_surrogate_ready_count: `{s['aqp1_functional_kcal_surrogate_ready_count']}`",
        f"- aqp1_functional_kcal_surrogate_closure_allowed: `{s['aqp1_functional_kcal_surrogate_closure_allowed']}`",
        f"- aqp1_direct_binding_gap_still_open: `{s['aqp1_direct_binding_gap_still_open']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_row_count: `{s['aqp1_negative_primary_probe_resolution_row_count']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_next_required_step: `{s['aqp1_negative_primary_probe_resolution_next_required_step']}`",
        f"- aqp1_first_wave_source_confirmation_artifact: `{s['aqp1_first_wave_source_confirmation_artifact']}`",
        f"- aqp1_first_wave_follow_on_packet_artifact: `{s['aqp1_first_wave_follow_on_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_ready: `{s['aqp1_follow_on_source_confirmation_packet_ready']}`",
        f"- aqp1_follow_on_source_confirmation_packet_artifact: `{s['aqp1_follow_on_source_confirmation_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_rows: `{s['aqp1_follow_on_source_confirmation_packet_rows']}`",
        f"- aqp1_follow_on_source_confirmation_packet_primary_focus_ligand: `{s['aqp1_follow_on_source_confirmation_packet_primary_focus_ligand']}`",
        f"- aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand: `{s['aqp1_follow_on_source_confirmation_packet_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_artifact: `{s['aqp1_first_wave_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_first_wave_primary_focus_ligand: `{s['aqp1_first_wave_primary_focus_ligand']}`",
        f"- aqp1_exact_human_reference_ligand: `{s['aqp1_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_claim_safe_kcal_ready_count: `{s['aqp1_first_wave_claim_safe_kcal_ready_count']}`",
        f"- aqp1_first_wave_follow_on_targets: `{s['aqp1_first_wave_follow_on_targets']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets: `{s['aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets']}`",
        f"- aqp1_first_wave_follow_on_lane_label: `{s['aqp1_first_wave_follow_on_lane_label']}`",
        f"- aqp1_first_wave_follow_on_row_count: `{s['aqp1_first_wave_follow_on_row_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_row_count: `{s['aqp1_first_wave_follow_on_blocker_decomposition_row_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand: `{s['aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand: `{s['aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count: `{s['aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count: `{s['aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal: `{s['aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal']}`",
        f"- aqp1_first_wave_follow_on_blocker_decomposition_next_required_step: `{s['aqp1_first_wave_follow_on_blocker_decomposition_next_required_step']}`",
        f"- aqp1_focus_ligand: `{s['aqp1_focus_ligand']}`",
        f"- aqp1_operator_provenance_note: `{s['aqp1_operator_provenance_note']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_direct_conflict_parked_review_only_count: `{s['ca2_direct_conflict_parked_review_only_count']}`",
        f"- ca2_direct_conflict_active_blocker_count: `{s['ca2_direct_conflict_active_blocker_count']}`",
        f"- pxr_must_defer_count: `{s['pxr_must_defer_count']}`",
        f"- pxr_must_defer_parked_review_only_count: `{s['pxr_must_defer_parked_review_only_count']}`",
        f"- pxr_must_defer_active_blocker_count: `{s['pxr_must_defer_active_blocker_count']}`",
        f"- science_lane_parked_review_only_count: `{s['science_lane_parked_review_only_count']}`",
        f"- science_lane_active_blocker_count: `{s['science_lane_active_blocker_count']}`",
        f"- ligand_scaleup_blocker_ready: `{s['ligand_scaleup_blocker_ready']}`",
        f"- ligand_scaleup_blocked: `{s['ligand_scaleup_blocked']}`",
        f"- ligand_scaleup_blocker_note: `{s['ligand_scaleup_blocker_note']}`",
        f"- ligand_scaleup_next_required_step: `{s['ligand_scaleup_next_required_step']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Burndown Board",
        "",
        "| family | commercialization_score | score_gap_to_100 | pretest_ready | claim_safe_test_ready | burndown_bucket | primary_blocker | commercialization_closure_queue_artifact | source_confirmation_artifact | closure_signal | next_burndown_action |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['commercialization_score']} | {row['score_gap_to_100']} | `{row['pretest_ready']}` | "
            f"`{row['claim_safe_test_ready']}` | `{row['burndown_bucket']}` | `{row['primary_blocker']}` | `{row['commercialization_closure_queue_artifact']}` | "
            f"`{row.get('source_confirmation_artifact', '')}` | `{row['closure_signal']}` | {row['next_burndown_action']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a commercialization gap burndown board across all families.")
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--pretest-json", default=DEFAULT_PRETEST_JSON)
    parser.add_argument("--crossfamily-json", default=DEFAULT_CROSSFAMILY_JSON)
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
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
        "--aqp1-functional-kcal-surrogate-json",
        default=DEFAULT_AQP1_FUNCTIONAL_KCAL_SURROGATE_JSON,
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
    parser.add_argument("--gpcr-scaleup-frontier-json", default=DEFAULT_GPCR_SCALEUP_FRONTIER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commercialization_json),
        _load_json(args.pretest_json),
        _load_json(args.crossfamily_json),
        _load_json(args.execution_json),
        _load_json(args.transporter_closure_queue_json),
        _maybe_load_json(args.aqp1_source_confirmation_json),
        _maybe_load_json(args.aqp1_follow_on_json),
        _maybe_load_json(args.aqp1_follow_on_blocker_decomposition_json),
        _maybe_load_json(args.aqp1_follow_on_source_confirmation_packet_json),
        _maybe_load_json(args.transporter_placeholder_burndown_queue_json),
        _maybe_load_json(args.aqp1_functional_kcal_surrogate_json),
        _maybe_load_json(args.aqp1_negative_primary_probe_resolution_json),
        _maybe_load_json(args.glut1_second_wave_source_confirmation_packet_json),
        _maybe_load_json(args.ligand_scaleup_suite_status_json),
        _maybe_load_json(args.ligand_scaleup_benchmark_summary_json),
        _maybe_load_json(args.gpcr_scaleup_frontier_json),
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
