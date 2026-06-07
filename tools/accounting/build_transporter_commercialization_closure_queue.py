#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SEED_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_APPLY_DRAFT_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_AQP1_MANUAL_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_JSON = "runs/aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_LAUNCHBOARD_JSON = "runs/transporter_manual_review_launchboard_current.json"
DEFAULT_OPERATOR_CONSOLE_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_DONOR_REOPEN_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_BLOCKER_DECOMPOSITION_JSON = "runs/transporter_authoritative_apply_blocker_decomposition_current.json"
DEFAULT_PLACEHOLDER_BURNDOWN_QUEUE_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_WAVE_DECISION_JSON = "runs/transporter_wave_decision_current.json"
DEFAULT_OUT_JSON = "runs/transporter_commercialization_closure_queue_current.json"
DEFAULT_OUT_CSV = "runs/transporter_commercialization_closure_queue_current.csv"
DEFAULT_OUT_MD = "runs/transporter_commercialization_closure_queue_current.md"


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _lookup(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get(key)) == value:
            return row
    return {}


def _seed_queue_id(seed_target: str) -> str:
    for token in seed_target.split():
        if token.startswith("core_"):
            return f"seed_{token}"
    return "seed_core_binder_01"


def _follow_on_blocker_decomposition_artifact(launch_summary: dict[str, Any], operator_summary: dict[str, Any]) -> str:
    return _text(
        launch_summary.get("today_open_follow_on_blocker_decomposition")
        or launch_summary.get("aqp1_follow_on_blocker_decomposition_artifact")
        or launch_summary.get("follow_on_blocker_decomposition_artifact")
        or operator_summary.get("aqp1_open_follow_on_blocker_decomposition")
        or operator_summary.get("aqp1_follow_on_blocker_decomposition_artifact")
        or ""
    )


def _row(
    *,
    queue_id: str,
    queue_rank: int,
    queue_type: str,
    closure_item: str,
    family: str,
    target_id: str,
    source_step_or_blocker: str,
    focus_label: str,
    lane_status: str,
    primary_artifact: str,
    support_artifact: str,
    closure_signal: str,
    blocking_signal: str,
    unlock_condition: str,
    next_required_action: str,
) -> dict[str, Any]:
    return {
        "queue_id": queue_id,
        "queue_rank": queue_rank,
        "queue_type": queue_type,
        "closure_item": closure_item,
        "family": family,
        "target_id": target_id,
        "source_step_or_blocker": source_step_or_blocker,
        "focus_label": focus_label,
        "lane_status": lane_status,
        "primary_artifact": primary_artifact,
        "support_artifact": support_artifact,
        "closure_signal": closure_signal,
        "blocking_signal": blocking_signal,
        "unlock_condition": unlock_condition,
        "next_required_action": next_required_action,
    }


def build_payload(
    transporter_seed_row_board: dict[str, Any],
    transporter_apply_draft_status: dict[str, Any],
    aqp1_manual_review_queue: dict[str, Any],
    aqp1_quantitative_provenance: dict[str, Any],
    aqp1_source_confirmation: dict[str, Any],
    aqp1_follow_on_packet: dict[str, Any],
    aqp1_follow_on_source_confirmation: dict[str, Any],
    aqp1_follow_on_blocker_decomposition: dict[str, Any],
    transporter_launchboard: dict[str, Any],
    transporter_operator_console: dict[str, Any],
    donor_policy_reopen_checklist: dict[str, Any],
    blocker_decomposition: dict[str, Any],
    placeholder_burndown_queue: dict[str, Any] | None = None,
    wave_decision: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seed_summary = dict(transporter_seed_row_board.get("summary", {}) or {})
    apply_summary = dict(transporter_apply_draft_status.get("summary", {}) or {})
    manual_summary = dict(aqp1_manual_review_queue.get("summary", {}) or {})
    quant_summary = dict(aqp1_quantitative_provenance.get("summary", {}) or {})
    source_confirmation_summary = dict(aqp1_source_confirmation.get("summary", {}) or {})
    follow_on_summary = dict(aqp1_follow_on_packet.get("summary", {}) or {})
    follow_on_source_confirmation_summary = dict(aqp1_follow_on_source_confirmation.get("summary", {}) or {})
    follow_on_blocker_summary = dict(aqp1_follow_on_blocker_decomposition.get("summary", {}) or {})
    glut1_second_wave_source_confirmation_summary = dict(
        (glut1_second_wave_source_confirmation or {}).get("summary", {}) or {}
    )
    launch_summary = dict(transporter_launchboard.get("summary", {}) or {})
    operator_summary = dict(transporter_operator_console.get("summary", {}) or {})
    donor_summary = dict(donor_policy_reopen_checklist.get("summary", {}) or {})
    blocker_summary = dict(blocker_decomposition.get("summary", {}) or {})
    placeholder_burndown_summary = dict((placeholder_burndown_queue or {}).get("summary", {}) or {})
    wave_summary = dict((wave_decision or {}).get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_artifact = _text(
        follow_on_blocker_summary.get("blocker_decomposition_artifact")
        or follow_on_blocker_summary.get("packet_artifact")
    ) or _follow_on_blocker_decomposition_artifact(launch_summary, operator_summary)
    aqp1_follow_on_blocker_decomposition_ready = bool(aqp1_follow_on_blocker_decomposition_artifact)
    aqp1_follow_on_blocker_decomposition_row_count = _int(
        follow_on_blocker_summary.get(
            "blocker_row_count",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_row_count",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_row_count", 0),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_follow_on_targets = _text(
        follow_on_blocker_summary.get(
            "follow_on_targets",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_follow_on_targets",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_follow_on_targets", ""),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_primary_focus_ligand = _text(
        follow_on_blocker_summary.get(
            "primary_focus_ligand",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_primary_focus_ligand",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_primary_focus_ligand", ""),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand = _text(
        follow_on_blocker_summary.get(
            "exact_human_guardrail_ligand",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand", ""),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count = _int(
        follow_on_blocker_summary.get(
            "exact_human_nonbinding_count",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count", 0),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count = _int(
        follow_on_blocker_summary.get(
            "exact_target_pair_absent_count",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count", 0),
            ),
        )
    )
    aqp1_follow_on_blocker_decomposition_next_required_step = _text(
        follow_on_blocker_summary.get(
            "next_required_step",
            launch_summary.get(
                "aqp1_follow_on_blocker_decomposition_next_required_step",
                operator_summary.get("aqp1_follow_on_blocker_decomposition_next_required_step", ""),
            ),
        )
    )
    aqp1_follow_on_source_confirmation_artifact = _text(
        follow_on_source_confirmation_summary.get("packet_artifact")
    ) or (
        "runs/aqp1_follow_on_source_confirmation_packet_current.md" if follow_on_source_confirmation_summary else ""
    )
    aqp1_follow_on_source_confirmation_row_count = _int(follow_on_source_confirmation_summary.get("row_count"))
    aqp1_follow_on_source_confirmation_primary_focus_ligand = _text(
        follow_on_source_confirmation_summary.get("primary_focus_ligand")
    )
    glut1_second_wave_source_confirmation_artifact = _text(
        glut1_second_wave_source_confirmation_summary.get("packet_artifact")
    ) or (
        "runs/glut1_second_wave_source_confirmation_packet_current.md"
        if glut1_second_wave_source_confirmation_summary
        else ""
    )
    glut1_second_wave_source_confirmation_row_count = _int(
        glut1_second_wave_source_confirmation_summary.get("row_count")
    )
    glut1_second_wave_source_confirmation_primary_focus_ligand = _text(
        glut1_second_wave_source_confirmation_summary.get("primary_focus_ligand")
    )
    glut1_second_wave_direct_quantitative_binding_count = _int(
        glut1_second_wave_source_confirmation_summary.get("direct_quantitative_binding_count")
    )
    placeholder_burndown_artifact = _text(placeholder_burndown_summary.get("packet_artifact")) or (
        "runs/transporter_placeholder_burndown_queue_current.md" if placeholder_burndown_summary else ""
    )
    placeholder_burndown_row_count = _int(placeholder_burndown_summary.get("row_count"))
    placeholder_burndown_top_queue_id = _text(placeholder_burndown_summary.get("top_queue_id"))

    manual_rows = list(aqp1_manual_review_queue.get("rows", []) or [])
    donor_rows = list(donor_policy_reopen_checklist.get("rows", []) or [])
    blocker_rows = list(blocker_decomposition.get("rows", []) or [])
    wave_rows = list((wave_decision or {}).get("rows", []) or [])

    aqp1_provenance_row = _lookup(manual_rows, "packet_step", "core_binder_02")
    aqp1_negative_row = _lookup(manual_rows, "packet_step", "core_non_binder_01")
    placeholder_blocker_row = _lookup(blocker_rows, "blocker_id", "placeholder_packet_rows")
    donor_blocker_row = _lookup(blocker_rows, "blocker_id", "donor_policy_frozen")
    donor_non_placeholder_row = _lookup(donor_rows, "check_id", "candidate_has_non_placeholder_packet_row")
    donor_p0_row = _lookup(donor_rows, "check_id", "p0_scaffold_open_count_zero")
    glut1_wave_row = _lookup(wave_rows, "target_id", wave_summary.get("second_wave_target", "GLUT1"))

    seed_target = _text(seed_summary.get("today_seed_target"))
    top_queue_id = _seed_queue_id(seed_target)
    current_phase = _text(launch_summary.get("current_phase")) or _text(apply_summary.get("current_phase"))
    open_now_artifact = _text(launch_summary.get("today_open_now")) or "runs/aqp1_first_seed_row_packet_current.md"
    open_source_confirmation_artifact = (
        _text(launch_summary.get("today_open_source_confirmation"))
        or "runs/aqp1_first_wave_source_confirmation_packet_current.md"
        if source_confirmation_summary
        else ""
    )
    open_now_label = _text(launch_summary.get("today_open_now_label")) or "bacopaside II"
    open_provenance_artifact = (
        _text(launch_summary.get("today_open_provenance"))
        or _text(operator_summary.get("aqp1_open_provenance"))
        or "runs/aqp1_quantitative_provenance_packet_current.md"
    )
    follow_on_targets = (
        aqp1_follow_on_blocker_decomposition_follow_on_targets
        or _text(follow_on_summary.get("follow_on_targets"))
        or _text(launch_summary.get("aqp1_follow_on_seed_targets"))
        or "core_binder_02, core_binder_03"
    )
    follow_on_artifact = (
        "runs/aqp1_first_wave_follow_on_packet_current.md"
        if follow_on_summary
        else _text(launch_summary.get("today_open_follow_on"))
    )
    follow_on_blocker_decomposition_clause = (
        f" Keep `{aqp1_follow_on_blocker_decomposition_artifact}` open as the AQP1 follow-on blocker decomposition surface."
        if aqp1_follow_on_blocker_decomposition_artifact
        else ""
    )
    aqp1_focus_ligand = (
        _text(quant_summary.get("primary_focus_ligand"))
        or _text(operator_summary.get("aqp1_quantitative_provenance_primary_focus_ligand"))
        or _text(aqp1_provenance_row.get("suggested_external_candidate"))
        or "AqB013"
    )
    quantitative_signal = (
        _text(quant_summary.get("signal"))
        or _text(operator_summary.get("aqp1_quantitative_provenance_signal"))
        or _text(aqp1_provenance_row.get("public_provenance_signal"))
        or "exact_human_activity_present_leave_kcal_blank"
    )
    unresolved_field = (
        _text(operator_summary.get("aqp1_remaining_unresolved_fields"))
        or _text(aqp1_provenance_row.get("required_missing_fields"))
        or "replacement_reference_binding_kcal_mol"
    )
    quantitative_binding_status = (
        _text(operator_summary.get("aqp1_quantitative_binding_status"))
        or "quantitative_binding_absent_claim_safe_kcal_missing"
    )
    placeholder_rows = _int(apply_summary.get("placeholder_driven_rows"))
    staged_rows = _int(apply_summary.get("staged_non_authoritative_rows"))
    blocked_donor_check_count = _int(donor_summary.get("blocked_check_count"))

    aqp1_operator_provenance_note = (
        f"{aqp1_focus_ligand} carries exact human AQP1 target-activity provenance, "
        f"but {unresolved_field} stays blank until claim-safe quantitative binding is curated."
    )

    rows = [
        _row(
            queue_id=top_queue_id,
            queue_rank=1,
            queue_type="seed_lane",
            closure_item="aqp1_open_now_lane",
            family="transporter",
            target_id=_text(wave_summary.get("first_wave_target")) or "AQP1",
            source_step_or_blocker="core_binder_01",
            focus_label=open_now_label,
            lane_status="active_now",
            primary_artifact=open_now_artifact,
            support_artifact=open_source_confirmation_artifact or open_provenance_artifact,
            closure_signal=(
                f"phase={current_phase}; start_label={open_now_label}; "
                f"today_seed_target={seed_target}; "
                f"open_source_confirmation={open_source_confirmation_artifact or 'missing'}; "
                f"open_provenance={open_provenance_artifact}"
            ),
            blocking_signal=(
                f"placeholder_driven_rows={placeholder_rows}; staged_non_authoritative_rows={staged_rows}; "
                f"quantitative_binding_status={quantitative_binding_status}; remaining_unresolved_fields={unresolved_field}"
            ),
            unlock_condition="Exhaust AQP1 core_binder_01 before widening to additional AQP1 seed rows or GLUT1 second-wave work.",
            next_required_action=(
                _text(launch_summary.get("today_finish_line"))
                or _text(seed_summary.get("next_required_step"))
            ),
        ),
        _row(
            queue_id="guardrail_core_binder_02",
            queue_rank=2,
            queue_type="guardrail",
            closure_item="aqp1_quantitative_provenance_guardrail",
            family="transporter",
            target_id="AQP1",
            source_step_or_blocker="core_binder_02",
            focus_label=aqp1_focus_ligand,
            lane_status=(
                "guardrail_keep_open"
                if _int(quant_summary.get("exact_human_aqp1_activity_count")) or _text(aqp1_provenance_row.get("public_provenance_status"))
                else "guardrail_missing"
            ),
            primary_artifact="runs/aqp1_quantitative_provenance_packet_current.md",
            support_artifact="runs/aqp1_manual_review_queue_current.md",
            closure_signal=(
                f"public_provenance_status={_text(aqp1_provenance_row.get('public_provenance_status'))}; "
                f"IC50={_text(aqp1_provenance_row.get('chembl_best_activity_value'))} {_text(aqp1_provenance_row.get('chembl_best_activity_units'))}; "
                f"{quantitative_signal}"
            ),
            blocking_signal=(
                f"promotion_blocker={_text(aqp1_provenance_row.get('promotion_blocker'))}; "
                f"required_missing_fields={_text(aqp1_provenance_row.get('required_missing_fields')) or unresolved_field}; "
                f"claim_safe_kcal_ready_count={_int(quant_summary.get('claim_safe_kcal_ready_count'))}"
            ),
            unlock_condition=(
                f"Keep the provenance lane visible, but do not fill {unresolved_field} until claim-safe "
                "quantitative binding support exists."
            ),
            next_required_action=(
                _text(aqp1_provenance_row.get("next_required_action"))
                or _text(quant_summary.get("next_required_step"))
            ),
        ),
        _row(
            queue_id="seed_follow_on_aqp1",
            queue_rank=3,
            queue_type="follow_on",
            closure_item="aqp1_remaining_seed_surfaces",
            family="transporter",
            target_id="AQP1",
            source_step_or_blocker="core_binder_02_to_03",
            focus_label=follow_on_targets,
            lane_status="queued_follow_on",
            primary_artifact=follow_on_artifact or "runs/transporter_seed_row_promotion_board_current.md",
            support_artifact=aqp1_follow_on_source_confirmation_artifact
            or aqp1_follow_on_blocker_decomposition_artifact
            or "runs/transporter_manual_review_launchboard_current.md",
            closure_signal=(
                f"aqp1_seed_surface_count={_int(seed_summary.get('aqp1_seed_surface_count') or 3)}; "
                f"follow_on_targets={follow_on_summary.get('follow_on_targets', follow_on_targets)}; "
                f"follow_on_row_count={_int(follow_on_summary.get('row_count'))}; "
                f"follow_on_source_confirmation_rows={aqp1_follow_on_source_confirmation_row_count}; "
                f"follow_on_source_confirmation_focus={aqp1_follow_on_source_confirmation_primary_focus_ligand}; "
                f"follow_on_blocker_rows={aqp1_follow_on_blocker_decomposition_row_count}; "
                f"exact_human_nonbinding={aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count}; "
                f"exact_target_pair_absent={aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count}; "
                f"first_wave_target={_text(wave_summary.get('first_wave_target')) or 'AQP1'}"
                + (
                    f"; follow_on_blocker_decomposition_artifact={aqp1_follow_on_blocker_decomposition_artifact}"
                    if aqp1_follow_on_blocker_decomposition_artifact
                    else ""
                )
            ),
            blocking_signal=(
                _text(follow_on_blocker_summary.get("blocking_signal"))
                or (
                    f"follow_on_targets={follow_on_targets}; "
                    f"exact_human_nonbinding={aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count}; "
                    f"exact_target_pair_absent={aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count}"
                    if aqp1_follow_on_blocker_decomposition_row_count
                    else ""
                )
                or _text(follow_on_summary.get("blocking_signal"))
                or _text(seed_summary.get("top_blocker_signal"))
                or f"placeholder_driven_rows={placeholder_rows}; staged_non_authoritative_rows={staged_rows}"
            ),
            unlock_condition="Complete the AQP1 first-wave binder surfaces before any GLUT1 second-wave burn-down.",
            next_required_action=(
                (
                    aqp1_follow_on_blocker_decomposition_next_required_step
                    or _text(follow_on_blocker_summary.get("next_required_step"))
                    or _text(follow_on_summary.get("next_required_step"))
                    or _text(seed_summary.get("next_required_step"))
                )
                + follow_on_blocker_decomposition_clause
                + (
                    f" Follow its next step: {aqp1_follow_on_blocker_decomposition_next_required_step}."
                    if aqp1_follow_on_blocker_decomposition_next_required_step
                    else ""
                )
            ),
        ),
        _row(
            queue_id="negative_review_aqp1",
            queue_rank=4,
            queue_type="negative_review",
            closure_item="aqp1_negative_review_closure",
            family="transporter",
            target_id="AQP1",
            source_step_or_blocker="core_non_binder_01_to_03",
            focus_label="AQP1 negative slots",
            lane_status="queued_review_only_after_seed",
            primary_artifact="runs/aqp1_negative_review_handoff_packet_current.md",
            support_artifact="runs/aqp1_manual_review_queue_current.md",
            closure_signal=(
                f"review_only_negative_count={_int(manual_summary.get('review_only_negative_count'))}; "
                f"policy_fixed_pending_count={_int(manual_summary.get('policy_fixed_pending_count'))}"
            ),
            blocking_signal=(
                f"promotion_blocker={_text(aqp1_negative_row.get('promotion_blocker')) or 'no_quantitative_transporter_negative_evidence_curated'}; "
                f"required_missing_fields={_text(aqp1_negative_row.get('required_missing_fields'))}"
            ),
            unlock_condition="Keep transporter negative-like slots review-only; do not inject proxy non-binder quantitative values.",
            next_required_action=(
                _text(aqp1_negative_row.get("next_required_action"))
                or _text(manual_summary.get("next_required_step"))
            ),
        ),
        _row(
            queue_id="family_placeholder_burndown",
            queue_rank=5,
            queue_type="family_blocker",
            closure_item="transporter_family_gap_burndown",
            family="transporter",
            target_id="transporter",
            source_step_or_blocker=_text(placeholder_blocker_row.get("blocker_id")) or "placeholder_packet_rows",
            focus_label="placeholder-driven transporter rows",
            lane_status="family_gap_blocked",
            primary_artifact="runs/transporter_authoritative_apply_blocker_decomposition_current.md",
            support_artifact=placeholder_burndown_artifact or "runs/transporter_donor_policy_reopen_checklist_current.md",
            closure_signal=(
                f"{_text(placeholder_blocker_row.get('current_signal'))}; "
                f"blocked_donor_check_count={blocked_donor_check_count}; "
                f"top_blocker_id={_text(blocker_summary.get('top_blocker_id')) or 'placeholder_packet_rows'}; "
                f"placeholder_queue_rows={placeholder_burndown_row_count}; "
                f"placeholder_queue_top={placeholder_burndown_top_queue_id}"
            ),
            blocking_signal=(
                f"donor_policy={_text(donor_blocker_row.get('current_signal'))}; "
                f"non_placeholder_ready_when={_text(donor_non_placeholder_row.get('ready_when'))}; "
                f"p0_ready_when={_text(donor_p0_row.get('ready_when'))}"
            ),
            unlock_condition=(
                f"Reduce placeholder-driven rows ({placeholder_rows}) and satisfy donor reopen checks before any authoritative transporter apply discussion."
            ),
            next_required_action=(
                _text(placeholder_blocker_row.get("next_action"))
                or _text(blocker_summary.get("next_required_step"))
            ),
        ),
        _row(
            queue_id="wave_hold_glut1",
            queue_rank=6,
            queue_type="wave_hold",
            closure_item="glut1_second_wave_hold",
            family="transporter",
            target_id=_text(wave_summary.get("second_wave_target")) or "GLUT1",
            source_step_or_blocker="second_wave_glut1",
            focus_label=_text(wave_summary.get("second_wave_target")) or "GLUT1",
            lane_status="wave_hold",
            primary_artifact=glut1_second_wave_source_confirmation_artifact or "runs/transporter_wave_decision_current.md",
            support_artifact=glut1_second_wave_source_confirmation_artifact or "runs/transporter_seed_row_promotion_board_current.md",
            closure_signal=(
                f"decision_status={_text(wave_summary.get('decision_status'))}; "
                f"wave_label={_text(glut1_wave_row.get('wave_label'))}; "
                f"placeholder_rows={_int(glut1_wave_row.get('placeholder_rows'))}; "
                f"source_confirmation_rows={glut1_second_wave_source_confirmation_row_count}; "
                f"source_confirmation_focus={glut1_second_wave_source_confirmation_primary_focus_ligand}; "
                f"direct_quantitative_binding_count={glut1_second_wave_direct_quantitative_binding_count}"
            ),
            blocking_signal=(
                f"p0_open_count={_int(glut1_wave_row.get('p0_open_count'))}; "
                f"local_evidence_status={_text(glut1_wave_row.get('local_evidence_status'))}"
            ),
            unlock_condition="Keep GLUT1 as the second-wave hold until AQP1 ligand packets and donor-policy blockers are no longer placeholder-driven.",
            next_required_action=(
                _text(wave_summary.get("next_required_step"))
                + (
                    f" When widened, open {glut1_second_wave_source_confirmation_artifact} first and start with "
                    f"{glut1_second_wave_source_confirmation_primary_focus_ligand or 'cytochalasin B'}."
                    if glut1_second_wave_source_confirmation_artifact
                    else ""
                )
            ).strip(),
        ),
    ]

    rows.sort(key=lambda row: (int(row["queue_rank"]), row["queue_id"]))
    summary = {
        "queue_row_count": len(rows),
        "row_count": len(rows),
        "seed_row_count": _int(seed_summary.get("aqp1_seed_surface_count") or 3),
        "family_blocker_count": sum(1 for row in rows if row["queue_type"] == "family_blocker"),
        "wave_hold_count": sum(1 for row in rows if row["queue_type"] == "wave_hold"),
        "active_now_count": sum(1 for row in rows if row["lane_status"] == "active_now"),
        "queued_count": sum(1 for row in rows if row["lane_status"].startswith("queued_")),
        "guardrail_count": sum(1 for row in rows if row["lane_status"] == "guardrail_keep_open"),
        "blocked_count": sum(1 for row in rows if row["lane_status"] in {"family_gap_blocked", "wave_hold", "guardrail_missing"}),
        "top_queue_id": rows[0]["queue_id"] if rows else "",
        "current_phase": current_phase,
        "today_open_now": open_now_artifact,
        "today_open_now_label": open_now_label,
        "remaining_seed_targets": follow_on_targets,
        "first_wave_target": _text(wave_summary.get("first_wave_target")) or "AQP1",
        "second_wave_target": _text(wave_summary.get("second_wave_target")) or "GLUT1",
        "aqp1_focus_ligand": aqp1_focus_ligand,
        "aqp1_primary_focus_ligand": aqp1_focus_ligand,
        "aqp1_quantitative_signal": quantitative_signal,
        "aqp1_operator_provenance_note": aqp1_operator_provenance_note,
        "aqp1_source_confirmation_row_count": source_confirmation_summary.get("row_count", 0),
        "aqp1_source_confirmation_primary_focus_ligand": source_confirmation_summary.get("primary_focus_ligand", ""),
        "aqp1_follow_on_packet_ready": bool(follow_on_summary),
        "aqp1_follow_on_row_count": follow_on_summary.get("row_count", 0),
        "aqp1_follow_on_targets": follow_on_summary.get("follow_on_targets", follow_on_targets),
        "aqp1_open_follow_on": follow_on_artifact,
        "aqp1_follow_on_source_confirmation_artifact": aqp1_follow_on_source_confirmation_artifact,
        "aqp1_follow_on_source_confirmation_row_count": aqp1_follow_on_source_confirmation_row_count,
        "aqp1_follow_on_source_confirmation_primary_focus_ligand": aqp1_follow_on_source_confirmation_primary_focus_ligand,
        "glut1_second_wave_source_confirmation_artifact": glut1_second_wave_source_confirmation_artifact,
        "glut1_second_wave_source_confirmation_row_count": glut1_second_wave_source_confirmation_row_count,
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_second_wave_source_confirmation_primary_focus_ligand,
        "glut1_second_wave_direct_quantitative_binding_count": glut1_second_wave_direct_quantitative_binding_count,
        "aqp1_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
        "aqp1_follow_on_blocker_decomposition_ready": aqp1_follow_on_blocker_decomposition_ready,
        "aqp1_follow_on_blocker_decomposition_row_count": aqp1_follow_on_blocker_decomposition_row_count,
        "aqp1_follow_on_blocker_decomposition_follow_on_targets": aqp1_follow_on_blocker_decomposition_follow_on_targets,
        "aqp1_follow_on_blocker_decomposition_primary_focus_ligand": aqp1_follow_on_blocker_decomposition_primary_focus_ligand,
        "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand": aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand,
        "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count": aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count,
        "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count": aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count,
        "aqp1_follow_on_blocker_decomposition_blocking_signal": follow_on_blocker_summary.get("blocking_signal", ""),
        "aqp1_follow_on_blocker_decomposition_next_required_step": aqp1_follow_on_blocker_decomposition_next_required_step,
        "placeholder_driven_rows": placeholder_rows,
        "transporter_placeholder_driven_rows": placeholder_rows,
        "transporter_placeholder_burndown_queue_artifact": placeholder_burndown_artifact,
        "transporter_placeholder_burndown_queue_rows": placeholder_burndown_row_count,
        "transporter_placeholder_burndown_top_queue_id": placeholder_burndown_top_queue_id,
        "staged_non_authoritative_rows": staged_rows,
        "blocked_donor_check_count": blocked_donor_check_count,
        "transporter_seed_surface_count": _int(seed_summary.get("binder_row_count") or apply_summary.get("binder_seed_row_count")),
        "highest_gap_family": "transporter",
        "next_required_step": (
            f"Start with {seed_target or 'AQP1 core_binder_01'}, keep {aqp1_focus_ligand} as the exact-human-activity provenance hold, "
            f"leave {unresolved_field} blank, use the AQP1 follow-on packet for {follow_on_summary.get('follow_on_targets', follow_on_targets)} after core_binder_01, reduce placeholder-driven transporter rows ({placeholder_rows}), "
            f"and keep {_text(wave_summary.get('second_wave_target')) or 'GLUT1'} as second-wave until the AQP1 first-wave lane is exhausted."
            + (
                f" Keep {aqp1_follow_on_source_confirmation_primary_focus_ligand} as the primary follow-on exact-source confirmation row."
                if aqp1_follow_on_source_confirmation_primary_focus_ligand
                else ""
            )
            + (
                f" Follow its blocker decomposition next step: {aqp1_follow_on_blocker_decomposition_next_required_step}."
                if aqp1_follow_on_blocker_decomposition_next_required_step
                else ""
            )
            + (
                f" Use the transporter placeholder burndown queue next: {placeholder_burndown_summary.get('next_required_step')}."
                if placeholder_burndown_summary.get("next_required_step")
                else ""
            )
            + (
                f" Keep {glut1_second_wave_source_confirmation_primary_focus_ligand} as the GLUT1 second-wave source-confirmation lead."
                if glut1_second_wave_source_confirmation_primary_focus_ligand
                else ""
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Commercialization Closure Queue",
        "",
        f"- queue_row_count: `{summary['queue_row_count']}`",
        f"- top_queue_id: `{summary['top_queue_id']}`",
        f"- active_now_count: `{summary['active_now_count']}`",
        f"- queued_count: `{summary['queued_count']}`",
        f"- guardrail_count: `{summary['guardrail_count']}`",
        f"- blocked_count: `{summary['blocked_count']}`",
        f"- current_phase: `{summary['current_phase']}`",
        f"- first_wave_target: `{summary['first_wave_target']}`",
        f"- second_wave_target: `{summary['second_wave_target']}`",
        f"- aqp1_focus_ligand: `{summary['aqp1_focus_ligand']}`",
        f"- aqp1_operator_provenance_note: {summary['aqp1_operator_provenance_note']}",
        f"- aqp1_follow_on_packet_ready: `{summary['aqp1_follow_on_packet_ready']}`",
        f"- aqp1_follow_on_row_count: `{summary['aqp1_follow_on_row_count']}`",
        f"- aqp1_follow_on_targets: `{summary['aqp1_follow_on_targets']}`",
        f"- aqp1_open_follow_on: `{summary['aqp1_open_follow_on']}`",
        f"- aqp1_follow_on_source_confirmation_artifact: `{summary['aqp1_follow_on_source_confirmation_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_row_count: `{summary['aqp1_follow_on_source_confirmation_row_count']}`",
        f"- aqp1_follow_on_source_confirmation_primary_focus_ligand: `{summary['aqp1_follow_on_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_second_wave_source_confirmation_artifact: `{summary['glut1_second_wave_source_confirmation_artifact']}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{summary['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{summary['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_second_wave_direct_quantitative_binding_count: `{summary['glut1_second_wave_direct_quantitative_binding_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_artifact: `{summary['aqp1_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_follow_on_blocker_decomposition_ready: `{summary['aqp1_follow_on_blocker_decomposition_ready']}`",
        f"- aqp1_follow_on_blocker_decomposition_row_count: `{summary['aqp1_follow_on_blocker_decomposition_row_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_follow_on_targets: `{summary['aqp1_follow_on_blocker_decomposition_follow_on_targets']}`",
        f"- aqp1_follow_on_blocker_decomposition_primary_focus_ligand: `{summary['aqp1_follow_on_blocker_decomposition_primary_focus_ligand']}`",
        f"- aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand: `{summary['aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand']}`",
        f"- aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count: `{summary['aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count: `{summary['aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count']}`",
        f"- aqp1_follow_on_blocker_decomposition_blocking_signal: `{summary['aqp1_follow_on_blocker_decomposition_blocking_signal']}`",
        f"- aqp1_follow_on_blocker_decomposition_next_required_step: `{summary['aqp1_follow_on_blocker_decomposition_next_required_step']}`",
        f"- transporter_placeholder_driven_rows: `{summary['transporter_placeholder_driven_rows']}`",
        f"- transporter_placeholder_burndown_queue_artifact: `{summary['transporter_placeholder_burndown_queue_artifact']}`",
        f"- transporter_placeholder_burndown_queue_rows: `{summary['transporter_placeholder_burndown_queue_rows']}`",
        f"- transporter_placeholder_burndown_top_queue_id: `{summary['transporter_placeholder_burndown_top_queue_id']}`",
        f"- blocked_donor_check_count: `{summary['blocked_donor_check_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Ordered Queue",
        "",
        "| queue_rank | queue_id | queue_type | focus_label | target_id | lane_status | primary_artifact | support_artifact | closure_signal | blocking_signal | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['queue_id']}` | `{row['queue_type']}` | `{row['focus_label']}` | `{row['target_id']}` | `{row['lane_status']}` | "
            f"`{row['primary_artifact']}` | `{row['support_artifact']}` | `{row['closure_signal']}` | `{row['blocking_signal']}` | {row['next_required_action']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an ordered transporter commercialization closure queue from transporter/AQP1 source artifacts.")
    parser.add_argument("--seed-board-json", default=DEFAULT_SEED_BOARD_JSON)
    parser.add_argument("--apply-draft-status-json", default=DEFAULT_APPLY_DRAFT_STATUS_JSON)
    parser.add_argument("--aqp1-manual-queue-json", default=DEFAULT_AQP1_MANUAL_QUEUE_JSON)
    parser.add_argument("--aqp1-quantitative-provenance-json", default=DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--aqp1-source-confirmation-json", default=DEFAULT_AQP1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--aqp1-follow-on-packet-json", default=DEFAULT_AQP1_FOLLOW_ON_PACKET_JSON)
    parser.add_argument(
        "--aqp1-follow-on-source-confirmation-json",
        default=DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_JSON,
    )
    parser.add_argument(
        "--aqp1-follow-on-blocker-decomposition-json",
        default=DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON,
    )
    parser.add_argument(
        "--glut1-second-wave-source-confirmation-json",
        default=DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_JSON,
    )
    parser.add_argument("--launchboard-json", default=DEFAULT_LAUNCHBOARD_JSON)
    parser.add_argument("--operator-console-json", default=DEFAULT_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--donor-reopen-json", default=DEFAULT_DONOR_REOPEN_JSON)
    parser.add_argument("--blocker-decomposition-json", default=DEFAULT_BLOCKER_DECOMPOSITION_JSON)
    parser.add_argument("--placeholder-burndown-queue-json", default=DEFAULT_PLACEHOLDER_BURNDOWN_QUEUE_JSON)
    parser.add_argument("--wave-decision-json", default=DEFAULT_WAVE_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.seed_board_json),
        _load_json(args.apply_draft_status_json),
        _load_json(args.aqp1_manual_queue_json),
        _load_json(args.aqp1_quantitative_provenance_json),
        _load_json(args.aqp1_source_confirmation_json),
        _maybe_load_json(args.aqp1_follow_on_packet_json),
        _maybe_load_json(args.aqp1_follow_on_source_confirmation_json),
        _maybe_load_json(args.aqp1_follow_on_blocker_decomposition_json),
        _load_json(args.launchboard_json),
        _load_json(args.operator_console_json),
        _load_json(args.donor_reopen_json),
        _load_json(args.blocker_decomposition_json),
        _maybe_load_json(args.placeholder_burndown_queue_json),
        _load_json(args.wave_decision_json),
        _maybe_load_json(args.glut1_second_wave_source_confirmation_json),
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
