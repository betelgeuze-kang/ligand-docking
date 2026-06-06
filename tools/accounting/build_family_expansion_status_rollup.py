#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.local_engine_surface_helpers import (
    DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON,
    local_engine_summary_from_source,
    summarize_local_engine_commercialization_queue,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CA2_CAPTURE_INTAKE_JSON = "runs/ca2_negative_evidence_capture_intake_current.json"
DEFAULT_CA2_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_PXR_CAPTURE_INTAKE_JSON = "runs/pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_PXR_COMMIT_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_TRANSPORTER_CAPTURE_INTAKE_JSON = "runs/transporter_blocker_capture_intake_current.json"
DEFAULT_TRANSPORTER_APPLY_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_AQP1_CAPTURE_INTAKE_JSON = "runs/aqp1_quantitative_binding_capture_intake_current.json"
DEFAULT_AQP1_FIRST_SEED_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_AQP1_FIRST_WAVE_SOURCE_CONFIRMATION_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_PACKET_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON = "runs/aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_AQP1_FUNCTIONAL_KCAL_SURROGATE_JSON = "runs/aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_EXECUTION_JSON = "runs/execution_handoff_dashboard_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON
DEFAULT_OUT_JSON = "runs/family_expansion_status_rollup_current.json"
DEFAULT_OUT_CSV = "runs/family_expansion_status_rollup_current.csv"
DEFAULT_OUT_MD = "runs/family_expansion_status_rollup_current.md"


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


def _artifact_for(path: str, payload: dict[str, Any] | None) -> str:
    return path if payload else ""


def _compose_aqp1_first_wave_signal(
    focus_ligand: str,
    exact_human_reference_ligand: str,
    signal: str,
) -> str:
    if signal:
        return signal
    if not focus_ligand and not exact_human_reference_ligand:
        return ""
    reference_ligand = exact_human_reference_ligand or "AqB013"
    return (
        f"Review {focus_ligand or 'bacopaside II'} first as the AQP1 core_binder_01 exact-source scope packet, "
        f"keep {reference_ligand} as the exact-human-activity reference row, and leave "
        "replacement_reference_binding_kcal_mol blank."
    )


def _compose_aqp1_first_wave_follow_on_signal(
    follow_on_targets: str,
    follow_on_row_count: int,
    follow_on_artifact: str,
) -> str:
    if not follow_on_targets and not follow_on_row_count and not follow_on_artifact:
        return ""
    targets = follow_on_targets or "core_binder_02, core_binder_03"
    artifact = follow_on_artifact or DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_JSON
    count_prefix = f"{follow_on_row_count}-row " if follow_on_row_count else ""
    return (
        f"Surface {artifact} next as the {count_prefix}AQP1 first-wave follow-on packet so transporter/AQP1 wording "
        f"keeps {targets} in source-only follow-on staging."
    )


def _compose_aqp1_follow_on_blocker_note(next_required_step: str) -> str:
    if not next_required_step:
        return ""
    return f"Follow the AQP1 follow-on blocker decomposition packet next: {next_required_step}"


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
    ca2_capture_intake: dict[str, Any],
    ca2_commit: dict[str, Any],
    pxr_capture_intake: dict[str, Any],
    pxr_commit: dict[str, Any],
    transporter_capture_intake: dict[str, Any],
    transporter_apply_status: dict[str, Any],
    aqp1_capture_intake: dict[str, Any],
    aqp1_first_seed: dict[str, Any],
    aqp1_first_wave_source_confirmation_packet: dict[str, Any],
    aqp1_first_wave_follow_on_packet: dict[str, Any],
    aqp1_quantitative_provenance_packet: dict[str, Any],
    execution: dict[str, Any],
    aqp1_follow_on_blocker_decomposition: dict[str, Any] | None = None,
    aqp1_follow_on_source_confirmation_packet: dict[str, Any] | None = None,
    aqp1_functional_kcal_surrogate_packet: dict[str, Any] | None = None,
    transporter_placeholder_burndown_queue: dict[str, Any] | None = None,
    glut1_second_wave_source_confirmation_packet: dict[str, Any] | None = None,
    local_engine_commercialization_queue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ca2_cap_s = dict(ca2_capture_intake.get("summary", {}) or {})
    ca2_commit_s = dict(ca2_commit.get("summary", {}) or {})
    pxr_cap_s = dict(pxr_capture_intake.get("summary", {}) or {})
    pxr_commit_s = dict(pxr_commit.get("summary", {}) or {})
    transporter_cap_s = dict(transporter_capture_intake.get("summary", {}) or {})
    transporter_apply_s = dict(transporter_apply_status.get("summary", {}) or {})
    aqp1_cap_s = dict(aqp1_capture_intake.get("summary", {}) or {})
    aqp1_seed_s = dict(aqp1_first_seed.get("summary", {}) or {})
    aqp1_source_confirmation_s = dict(aqp1_first_wave_source_confirmation_packet.get("summary", {}) or {})
    aqp1_follow_on_s = dict(aqp1_first_wave_follow_on_packet.get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_s = dict((aqp1_follow_on_blocker_decomposition or {}).get("summary", {}) or {})
    aqp1_follow_on_source_confirmation_packet_s = dict(
        (aqp1_follow_on_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    aqp1_functional_kcal_surrogate_packet_s = dict(
        (aqp1_functional_kcal_surrogate_packet or {}).get("summary", {}) or {}
    )
    transporter_placeholder_burndown_queue_s = dict(
        (transporter_placeholder_burndown_queue or {}).get("summary", {}) or {}
    )
    glut1_second_wave_source_confirmation_packet_s = dict(
        (glut1_second_wave_source_confirmation_packet or {}).get("summary", {}) or {}
    )
    aqp1_quant_prov_s = dict(aqp1_quantitative_provenance_packet.get("summary", {}) or {})
    execution_s = dict(execution.get("summary", {}) or {})
    local_engine_summary = summarize_local_engine_commercialization_queue(
        local_engine_commercialization_queue
    )
    if not local_engine_summary["local_engine_commercialization_queue_ready"]:
        local_engine_summary = local_engine_summary_from_source(execution_s)
    aqp1_quant_focus_ligand = _text(
        execution_s.get(
            "aqp1_quantitative_provenance_primary_focus_ligand",
            aqp1_quant_prov_s.get("primary_focus_ligand", ""),
        )
    )
    aqp1_quant_signal = _text(
        execution_s.get(
            "aqp1_quantitative_provenance_signal",
            aqp1_quant_prov_s.get("signal", ""),
        )
    )
    aqp1_first_wave_focus_ligand = _text(
        execution_s.get(
            "aqp1_first_wave_source_confirmation_primary_focus_ligand",
            aqp1_source_confirmation_s.get("primary_focus_ligand", ""),
        )
    )
    aqp1_first_wave_exact_human_reference_ligand = _text(
        execution_s.get(
            "aqp1_first_wave_source_confirmation_exact_human_reference_ligand",
            aqp1_source_confirmation_s.get("exact_human_reference_ligand", ""),
        )
    ) or aqp1_quant_focus_ligand
    aqp1_first_wave_follow_on_row_count = int(
        execution_s.get(
            "aqp1_first_wave_follow_on_packet_row_count",
            aqp1_follow_on_s.get("row_count", 0),
        )
        or 0
    )
    aqp1_first_wave_follow_on_targets = _text(
        execution_s.get(
            "aqp1_first_wave_follow_on_targets",
            aqp1_follow_on_s.get("follow_on_targets", ""),
        )
    )
    aqp1_first_wave_follow_on_artifact = _text(
        execution_s.get(
            "aqp1_first_wave_follow_on_packet_artifact",
            DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_JSON,
        )
    ) or DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_JSON
    aqp1_first_wave_follow_on_signal = _text(
        execution_s.get("aqp1_first_wave_follow_on_packet_signal", "")
    ) or _compose_aqp1_first_wave_follow_on_signal(
        aqp1_first_wave_follow_on_targets,
        aqp1_first_wave_follow_on_row_count,
        aqp1_first_wave_follow_on_artifact,
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
    aqp1_follow_on_source_confirmation_primary_focus_ligand = _text(
        aqp1_follow_on_blocker_decomposition_s.get("source_confirmation_primary_focus_ligand", "")
    )
    aqp1_follow_on_exact_human_guardrail_ligand = _text(
        aqp1_follow_on_blocker_decomposition_s.get("exact_human_guardrail_ligand", "")
    ) or aqp1_first_wave_exact_human_reference_ligand
    aqp1_follow_on_blocking_signal = _text(
        aqp1_follow_on_blocker_decomposition_s.get("blocking_signal", "")
    )
    aqp1_follow_on_blocker_decomposition_artifact = _text(
        aqp1_follow_on_blocker_decomposition_s.get("blocker_decomposition_artifact")
        or aqp1_follow_on_blocker_decomposition_s.get("packet_artifact")
        or (DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON if aqp1_follow_on_blocker_decomposition_ready else "")
    )
    aqp1_follow_on_source_confirmation_packet_ready = bool(aqp1_follow_on_source_confirmation_packet_s)
    aqp1_follow_on_source_confirmation_packet_artifact = _artifact_for(
        "runs/aqp1_follow_on_source_confirmation_packet_current.md",
        aqp1_follow_on_source_confirmation_packet_s,
    )
    aqp1_follow_on_source_confirmation_packet_row_count = _int(
        aqp1_follow_on_source_confirmation_packet_s.get("row_count", 0)
    )
    aqp1_functional_kcal_surrogate_ready_count = _int(
        aqp1_functional_kcal_surrogate_packet_s.get("functional_kcal_surrogate_ready_count", 0)
    )
    aqp1_functional_kcal_surrogate_closure_allowed = bool(
        aqp1_functional_kcal_surrogate_packet_s.get("functional_kcal_surrogate_closure_allowed", False)
    )
    aqp1_functional_kcal_surrogate_artifact = _artifact_for(
        "runs/aqp1_functional_kcal_surrogate_packet_current.md",
        aqp1_functional_kcal_surrogate_packet_s,
    )
    aqp1_direct_binding_gap_still_open = bool(
        aqp1_functional_kcal_surrogate_packet_s.get("direct_binding_gap_still_open", False)
    )
    transporter_placeholder_burndown_queue_ready = bool(transporter_placeholder_burndown_queue_s)
    transporter_placeholder_burndown_queue_artifact = _artifact_for(
        "runs/transporter_placeholder_burndown_queue_current.md",
        transporter_placeholder_burndown_queue_s,
    )
    transporter_placeholder_burndown_queue_row_count = _int(
        transporter_placeholder_burndown_queue_s.get("row_count", 0)
    )
    glut1_second_wave_source_confirmation_packet_ready = bool(glut1_second_wave_source_confirmation_packet_s)
    glut1_second_wave_source_confirmation_packet_artifact = _artifact_for(
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        glut1_second_wave_source_confirmation_packet_s,
    )
    glut1_second_wave_source_confirmation_packet_row_count = _int(
        glut1_second_wave_source_confirmation_packet_s.get("row_count", 0)
    )
    glut1_second_wave_source_confirmation_primary_focus_ligand = _text(
        glut1_second_wave_source_confirmation_packet_s.get("primary_focus_ligand", "")
    )
    glut1_second_wave_direct_quantitative_binding_count = _int(
        glut1_second_wave_source_confirmation_packet_s.get("direct_quantitative_binding_count", 0)
    )
    transporter_ready_for_apply_rows = _int(
        transporter_placeholder_burndown_queue_s.get(
            "ready_for_apply_rows",
            transporter_apply_s.get("ready_for_apply_rows", 0),
        )
    )
    transporter_placeholder_driven_rows = _int(
        transporter_placeholder_burndown_queue_s.get(
            "placeholder_driven_rows",
            transporter_apply_s.get("placeholder_driven_rows", 0),
        )
    )
    transporter_staged_non_authoritative_rows = _int(
        transporter_placeholder_burndown_queue_s.get(
            "staged_non_authoritative_rows",
            transporter_apply_s.get("staged_non_authoritative_rows", 0),
        )
    )
    transporter_negative_ready_note = _text(transporter_placeholder_burndown_queue_s.get("next_required_step"))
    aqp1_first_wave_signal = _compose_aqp1_first_wave_signal(
        aqp1_first_wave_focus_ligand,
        aqp1_first_wave_exact_human_reference_ligand,
        _text(
            execution_s.get(
                "aqp1_first_wave_source_confirmation_signal",
                aqp1_source_confirmation_s.get("next_required_step", ""),
            )
        ),
    )
    aqp1_follow_on_next_required_step = _text(
        execution_s.get(
            "aqp1_follow_on_next_required_step",
            aqp1_follow_on_blocker_decomposition_s.get("next_required_step", ""),
        )
    )
    aqp1_follow_on_blocker_note = _compose_aqp1_follow_on_blocker_note(aqp1_follow_on_next_required_step)
    aqp1_operator_provenance_note = _text(
        execution_s.get("aqp1_operator_provenance_note", "")
        or (
            f"{aqp1_quant_focus_ligand} carries exact human AQP1 target-activity provenance, but replacement_reference_binding_kcal_mol stays blank until claim-safe quantitative binding is curated."
            if aqp1_quant_focus_ligand and int(aqp1_quant_prov_s.get("exact_human_aqp1_activity_count", 0) or 0) > 0
            else ""
        )
    )
    aqp1_functional_kcal_surrogate_note = _text(
        aqp1_functional_kcal_surrogate_packet_s.get("next_required_step", "")
    )
    local_engine_queue_note = _text(local_engine_summary.get("local_engine_commercialization_queue_blocker_note"))
    local_engine_queue_next_required_step = _text(
        local_engine_summary.get("local_engine_commercialization_queue_next_required_step")
    )
    local_engine_queue_clear = bool(
        local_engine_summary.get("local_engine_commercialization_queue_clear", False)
    ) or (
        bool(local_engine_summary.get("local_engine_commercialization_queue_ready", False))
        and _int(local_engine_summary.get("local_engine_commercialization_queue_blocked_count")) == 0
        and _int(local_engine_summary.get("local_engine_commercialization_queue_partial_count")) == 0
        and _int(local_engine_summary.get("local_engine_commercialization_queue_parked_science_blocker_count")) == 0
    )
    transporter_negative_accounting_closed = (
        transporter_placeholder_burndown_queue_ready
        and transporter_placeholder_driven_rows == 0
        and transporter_ready_for_apply_rows > 0
    )
    aqp1_surrogate_accounting_closed = (
        aqp1_functional_kcal_surrogate_closure_allowed
        and aqp1_functional_kcal_surrogate_ready_count > 0
    )
    all_tracked_family_accounting_closed = (
        local_engine_queue_clear
        and transporter_negative_accounting_closed
        and aqp1_surrogate_accounting_closed
        and int(ca2_cap_s.get("pending_capture_count", 0) or 0) == 0
        and int(pxr_cap_s.get("pending_capture_count", 0) or 0) == 0
    )

    transporter_next_required_step = (
        "Transporter negative placeholder rows are closed for accounting by the authoritative apply gate; "
        "keep AQP1/GLUT1 replacement_reference_binding_kcal_mol blank unless direct binding evidence is curated, "
        "and keep functional/surrogate wording separate from direct-binding claims."
        if transporter_negative_accounting_closed
        else " ".join(
            part
            for part in (
                _text(transporter_apply_s.get("next_required_step", "")),
                transporter_negative_ready_note,
                aqp1_first_wave_signal,
                aqp1_follow_on_blocker_note,
                aqp1_first_wave_follow_on_signal,
                aqp1_operator_provenance_note,
                aqp1_functional_kcal_surrogate_note,
                local_engine_queue_next_required_step or local_engine_queue_note,
                (
                    f"Keep {glut1_second_wave_source_confirmation_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                    if glut1_second_wave_source_confirmation_primary_focus_ligand
                    else ""
                ),
            )
            if part
        ).strip()
    )
    aqp1_next_required_step = (
        "AQP1 functional IC50-derived kcal surrogate coverage is closed for accounting; direct binding kcal remains "
        "explicitly no-claim and replacement_reference_binding_kcal_mol stays blank."
        if aqp1_surrogate_accounting_closed
        else " ".join(
            part
            for part in (
                aqp1_first_wave_signal,
                aqp1_follow_on_blocker_note,
                aqp1_first_wave_follow_on_signal,
                aqp1_functional_kcal_surrogate_note,
                local_engine_queue_next_required_step or local_engine_queue_note,
                _text(aqp1_quant_prov_s.get("next_required_step", "") or aqp1_seed_s.get("next_required_step", "")),
            )
            if part
        ).strip()
    )
    family_next_required_step = (
        "All tracked family-expansion accounting blockers are closed; keep CA2/PXR review-only policy locks, "
        "AQP1 functional-surrogate no-direct-binding wording, transporter negative apply provenance, and local-engine keep-green history attached."
        if all_tracked_family_accounting_closed
        else (
            "Keep CA2 review-only, keep PXR partial-authoritative, keep transporter non-authoritative seed-row blocker closure, "
            + (
                "and "
                + " ".join(
                    part
                    for part in (
                        aqp1_first_wave_signal,
                        aqp1_follow_on_blocker_note,
                        aqp1_first_wave_follow_on_signal,
                        aqp1_operator_provenance_note,
                        aqp1_functional_kcal_surrogate_note,
                        local_engine_queue_next_required_step or local_engine_queue_note,
                        (
                            f"Keep {glut1_second_wave_source_confirmation_primary_focus_ligand} parked as the GLUT1 second-wave source-confirmation lead."
                            if glut1_second_wave_source_confirmation_primary_focus_ligand
                            else ""
                        ),
                    )
                    if part
                )
                if aqp1_first_wave_signal or aqp1_first_wave_follow_on_signal or aqp1_follow_on_blocker_note
                else f"and {aqp1_operator_provenance_note}"
                if aqp1_operator_provenance_note
                else "and keep AQP1 quantitative binding blank until direct binding or a claim-safe kcal anchor is curated."
            )
        )
    )

    rows = [
        {
            "family": "ca2",
            "phase": "review_only_conflict_closure",
            "current_scope": "non_authoritative_negative_review_only",
            "source_linked_count": int(ca2_cap_s.get("source_linked_count", 0) or 0),
            "pending_capture_count": int(ca2_cap_s.get("pending_capture_count", 0) or 0),
            "supportive_count": int(ca2_cap_s.get("direct_negative_evidence_count", 0) or 0),
            "ready_like_count": int(ca2_commit_s.get("confirmed_manual_commit_count", 0) or 0),
            "blocking_signal": (
                f"direct_conflicts={ca2_cap_s.get('direct_conflict_row_count', 0)}; "
                f"no_direct_negative={ca2_cap_s.get('no_direct_negative_found_count', 0)}; "
                "authoritative_negative_closure_allowed=False"
            ),
            "next_required_step": str(ca2_cap_s.get("next_required_step", "")).strip(),
        },
        {
            "family": "pxr",
            "phase": "partial_authoritative_resolution",
            "current_scope": "partial_authoritative_rows_plus_deferred_gaps",
            "source_linked_count": int(pxr_cap_s.get("source_linked_count", 0) or 0),
            "pending_capture_count": int(pxr_cap_s.get("pending_capture_count", 0) or 0),
            "supportive_count": int(pxr_cap_s.get("supportive_target_specific_human_count", 0) or 0),
            "ready_like_count": int(pxr_commit_s.get("ready_for_apply_row_count", 0) or 0),
            "blocking_signal": (
                f"binder_gap_count={pxr_commit_s.get('binder_gap_count', 0)}; "
                f"defer_row_count={pxr_commit_s.get('defer_row_count', 0)}"
            ),
            "next_required_step": str(pxr_commit_s.get("next_required_step", "")).strip(),
        },
        {
            "family": "transporter",
            "phase": (
                "negative_evidence_curated_functional_kcal_surrogate_staging"
                if transporter_ready_for_apply_rows and aqp1_functional_kcal_surrogate_ready_count
                else str(transporter_apply_s.get("current_phase", "")).strip()
            ),
            "current_scope": "non_authoritative_seed_row_blocker_closure",
            "source_linked_count": int(transporter_cap_s.get("source_linked_count", 0) or 0),
            "pending_capture_count": int(transporter_cap_s.get("pending_capture_count", 0) or 0),
            "supportive_count": int(transporter_cap_s.get("supportive_target_specific_packet_evidence_count", 0) or 0),
            "ready_like_count": transporter_ready_for_apply_rows,
            "blocking_signal": (
                f"placeholder_driven_rows={transporter_placeholder_driven_rows}; "
                f"staged_non_authoritative_rows={transporter_staged_non_authoritative_rows}; "
                f"ready_for_apply_rows={transporter_ready_for_apply_rows}; "
                f"aqp1_first_wave_primary_focus={aqp1_first_wave_focus_ligand}; "
                f"aqp1_first_wave_exact_human_reference={aqp1_first_wave_exact_human_reference_ligand}; "
                f"aqp1_first_wave_follow_on_packet_ready={aqp1_first_wave_follow_on_row_count > 0}; "
                f"aqp1_first_wave_follow_on_packet_artifact={aqp1_first_wave_follow_on_artifact}; "
                f"aqp1_first_wave_follow_on_targets={aqp1_first_wave_follow_on_targets}; "
                f"aqp1_first_wave_follow_on_packet_row_count={aqp1_first_wave_follow_on_row_count}; "
                f"aqp1_exact_human_activity_count={transporter_apply_s.get('aqp1_exact_human_activity_count', 0)}; "
                f"aqp1_focus_ligand={aqp1_quant_focus_ligand}; "
                f"aqp1_signal={transporter_apply_s.get('aqp1_quantitative_provenance_signal', '')}; "
                f"aqp1_follow_on_blocker_decomposition_ready={aqp1_follow_on_blocker_decomposition_ready}; "
                f"aqp1_follow_on_blocker_count={aqp1_follow_on_blocker_count}; "
                f"aqp1_follow_on_exact_human_nonbinding_count={aqp1_follow_on_exact_human_nonbinding_count}; "
                f"aqp1_follow_on_exact_target_pair_absent_count={aqp1_follow_on_exact_target_pair_absent_count}; "
                f"aqp1_follow_on_high_or_medium_potential_count={aqp1_follow_on_high_or_medium_potential_count}; "
                f"aqp1_follow_on_claim_safe_kcal_ready_count={aqp1_follow_on_claim_safe_kcal_ready_count}; "
                f"aqp1_follow_on_source_confirmation_primary_focus_ligand={aqp1_follow_on_source_confirmation_primary_focus_ligand}; "
                f"aqp1_follow_on_exact_human_guardrail_ligand={aqp1_follow_on_exact_human_guardrail_ligand}; "
                f"aqp1_follow_on_blocking_signal={aqp1_follow_on_blocking_signal}; "
                f"aqp1_follow_on_next_required_step={aqp1_follow_on_next_required_step}; "
                f"aqp1_follow_on_blocker_decomposition_artifact={aqp1_follow_on_blocker_decomposition_artifact}; "
                f"aqp1_follow_on_source_confirmation_packet_ready={aqp1_follow_on_source_confirmation_packet_ready}; "
                f"aqp1_follow_on_source_confirmation_packet_artifact={aqp1_follow_on_source_confirmation_packet_artifact}; "
                f"transporter_placeholder_burndown_queue_ready={transporter_placeholder_burndown_queue_ready}; "
                f"transporter_placeholder_burndown_queue_artifact={transporter_placeholder_burndown_queue_artifact}; "
                f"glut1_second_wave_source_confirmation_packet_ready={glut1_second_wave_source_confirmation_packet_ready}; "
                f"glut1_second_wave_source_confirmation_packet_artifact={glut1_second_wave_source_confirmation_packet_artifact}; "
                f"glut1_second_wave_source_confirmation_primary_focus_ligand={glut1_second_wave_source_confirmation_primary_focus_ligand}; "
                f"glut1_second_wave_direct_quantitative_binding_count={glut1_second_wave_direct_quantitative_binding_count}; "
                f"aqp1_functional_kcal_surrogate_ready_count={aqp1_functional_kcal_surrogate_ready_count}; "
                f"aqp1_functional_kcal_surrogate_closure_allowed={aqp1_functional_kcal_surrogate_closure_allowed}; "
                + (
                    f"{local_engine_summary['local_engine_commercialization_queue_blocker_signal']}; "
                    if local_engine_summary["local_engine_commercialization_queue_blocker_signal"]
                    else ""
                )
                + "donor_reopen_ready=False"
            ),
            "next_required_step": transporter_next_required_step,
        },
        {
            "family": "aqp1",
            "phase": (
                "functional_kcal_surrogate_ready_direct_binding_gap_open"
                if aqp1_functional_kcal_surrogate_ready_count
                else "first_seed_review_only_quantitative_gap"
            ),
            "current_scope": (
                "functional_ic50_surrogate_claim_safe_not_direct_binding"
                if aqp1_functional_kcal_surrogate_ready_count
                else "functional_potency_staged_review_only"
            ),
            "source_linked_count": int(aqp1_cap_s.get("source_linked_count", 0) or 0),
            "pending_capture_count": int(aqp1_cap_s.get("pending_capture_count", 0) or 0),
            "supportive_count": int(aqp1_cap_s.get("supportive_direct_quantitative_binding_count", 0) or 0)
            + aqp1_functional_kcal_surrogate_ready_count,
            "ready_like_count": max(
                int(aqp1_cap_s.get("kcal_overlay_ready_count", 0) or 0),
                aqp1_functional_kcal_surrogate_ready_count,
            ),
            "blocking_signal": (
                f"quantitative_binding_status={aqp1_seed_s.get('quantitative_binding_status', '')}; "
                f"remaining_unresolved={aqp1_seed_s.get('remaining_unresolved_fields', 'replacement_reference_binding_kcal_mol')}; "
                f"functional_kcal_surrogate_ready_count={aqp1_functional_kcal_surrogate_ready_count}; "
                f"functional_kcal_surrogate_closure_allowed={aqp1_functional_kcal_surrogate_closure_allowed}; "
                f"direct_binding_gap_still_open={aqp1_direct_binding_gap_still_open}; "
                f"functional_kcal_surrogate_artifact={aqp1_functional_kcal_surrogate_artifact}; "
                f"first_wave_primary_focus={aqp1_first_wave_focus_ligand}; "
                f"exact_human_reference={aqp1_first_wave_exact_human_reference_ligand}; "
                f"aqp1_first_wave_follow_on_packet_ready={aqp1_first_wave_follow_on_row_count > 0}; "
                f"aqp1_first_wave_follow_on_packet_artifact={aqp1_first_wave_follow_on_artifact}; "
                f"aqp1_first_wave_follow_on_targets={aqp1_first_wave_follow_on_targets}; "
                f"aqp1_first_wave_follow_on_packet_row_count={aqp1_first_wave_follow_on_row_count}; "
                f"exact_human_activity_count={aqp1_quant_prov_s.get('exact_human_aqp1_activity_count', 0)}; "
                f"focus_ligand={aqp1_quant_focus_ligand}; "
                f"signal={aqp1_quant_signal}; "
                f"aqp1_follow_on_blocker_decomposition_ready={aqp1_follow_on_blocker_decomposition_ready}; "
                f"aqp1_follow_on_blocker_count={aqp1_follow_on_blocker_count}; "
                f"aqp1_follow_on_exact_human_nonbinding_count={aqp1_follow_on_exact_human_nonbinding_count}; "
                f"aqp1_follow_on_exact_target_pair_absent_count={aqp1_follow_on_exact_target_pair_absent_count}; "
                f"aqp1_follow_on_high_or_medium_potential_count={aqp1_follow_on_high_or_medium_potential_count}; "
                f"aqp1_follow_on_claim_safe_kcal_ready_count={aqp1_follow_on_claim_safe_kcal_ready_count}; "
                f"aqp1_follow_on_source_confirmation_primary_focus_ligand={aqp1_follow_on_source_confirmation_primary_focus_ligand}; "
                f"aqp1_follow_on_exact_human_guardrail_ligand={aqp1_follow_on_exact_human_guardrail_ligand}; "
                f"aqp1_follow_on_blocking_signal={aqp1_follow_on_blocking_signal}; "
                f"aqp1_follow_on_next_required_step={aqp1_follow_on_next_required_step}; "
                f"aqp1_follow_on_blocker_decomposition_artifact={aqp1_follow_on_blocker_decomposition_artifact}; "
                f"aqp1_follow_on_source_confirmation_packet_ready={aqp1_follow_on_source_confirmation_packet_ready}; "
                f"aqp1_follow_on_source_confirmation_packet_artifact={aqp1_follow_on_source_confirmation_packet_artifact}; "
                f"transporter_placeholder_burndown_queue_ready={transporter_placeholder_burndown_queue_ready}; "
                f"transporter_placeholder_burndown_queue_artifact={transporter_placeholder_burndown_queue_artifact}; "
                f"glut1_second_wave_source_confirmation_packet_ready={glut1_second_wave_source_confirmation_packet_ready}; "
                f"glut1_second_wave_source_confirmation_packet_artifact={glut1_second_wave_source_confirmation_packet_artifact}"
                + (
                    f"; {local_engine_summary['local_engine_commercialization_queue_blocker_signal']}"
                    if local_engine_summary["local_engine_commercialization_queue_blocker_signal"]
                    else ""
                )
            ),
            "next_required_step": aqp1_next_required_step,
        },
    ]

    highest_gap_family = str(execution_s.get("highest_gap_family", "")).strip() or "transporter"
    if all_tracked_family_accounting_closed:
        highest_gap_family = "none_tracked_family_expansion"
    summary = {
        "family_count": len(rows),
        "highest_gap_family": highest_gap_family,
        "all_tracked_family_accounting_closed": all_tracked_family_accounting_closed,
        "transporter_negative_accounting_closed": transporter_negative_accounting_closed,
        "aqp1_surrogate_accounting_closed": aqp1_surrogate_accounting_closed,
        "local_engine_commercialization_queue_clear": local_engine_queue_clear,
        "pending_capture_total": sum(int(row["pending_capture_count"]) for row in rows),
        "source_linked_total": sum(int(row["source_linked_count"]) for row in rows),
        "supportive_total": sum(int(row["supportive_count"]) for row in rows),
        "ready_like_total": sum(int(row["ready_like_count"]) for row in rows),
        "aqp1_exact_human_activity_count": int(aqp1_quant_prov_s.get("exact_human_aqp1_activity_count", 0) or 0),
        "aqp1_first_wave_source_confirmation_primary_focus_ligand": aqp1_first_wave_focus_ligand,
        "aqp1_first_wave_source_confirmation_exact_human_reference_ligand": aqp1_first_wave_exact_human_reference_ligand,
        "aqp1_first_wave_source_confirmation_signal": aqp1_first_wave_signal,
        "aqp1_first_wave_follow_on_packet_ready": aqp1_first_wave_follow_on_row_count > 0,
        "aqp1_first_wave_follow_on_packet_row_count": aqp1_first_wave_follow_on_row_count,
        "aqp1_first_wave_follow_on_targets": aqp1_first_wave_follow_on_targets,
        "aqp1_first_wave_follow_on_packet_artifact": aqp1_first_wave_follow_on_artifact,
        "aqp1_first_wave_follow_on_packet_signal": aqp1_first_wave_follow_on_signal,
        "aqp1_follow_on_blocker_decomposition_ready": aqp1_follow_on_blocker_decomposition_ready,
        "aqp1_follow_on_blocker_count": aqp1_follow_on_blocker_count,
        "aqp1_follow_on_exact_human_nonbinding_count": aqp1_follow_on_exact_human_nonbinding_count,
        "aqp1_follow_on_exact_target_pair_absent_count": aqp1_follow_on_exact_target_pair_absent_count,
        "aqp1_follow_on_high_or_medium_potential_count": aqp1_follow_on_high_or_medium_potential_count,
        "aqp1_follow_on_claim_safe_kcal_ready_count": aqp1_follow_on_claim_safe_kcal_ready_count,
        "aqp1_follow_on_source_confirmation_primary_focus_ligand": aqp1_follow_on_source_confirmation_primary_focus_ligand,
        "aqp1_follow_on_exact_human_guardrail_ligand": aqp1_follow_on_exact_human_guardrail_ligand,
        "aqp1_follow_on_blocking_signal": aqp1_follow_on_blocking_signal,
        "aqp1_follow_on_next_required_step": aqp1_follow_on_next_required_step,
        "aqp1_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
        "aqp1_follow_on_source_confirmation_packet_ready": aqp1_follow_on_source_confirmation_packet_ready,
        "aqp1_follow_on_source_confirmation_packet_artifact": aqp1_follow_on_source_confirmation_packet_artifact,
        "aqp1_follow_on_source_confirmation_packet_row_count": aqp1_follow_on_source_confirmation_packet_row_count,
        "aqp1_functional_kcal_surrogate_ready": bool(aqp1_functional_kcal_surrogate_packet_s),
        "aqp1_functional_kcal_surrogate_artifact": aqp1_functional_kcal_surrogate_artifact,
        "aqp1_functional_kcal_surrogate_ready_count": aqp1_functional_kcal_surrogate_ready_count,
        "aqp1_functional_kcal_surrogate_closure_allowed": aqp1_functional_kcal_surrogate_closure_allowed,
        "aqp1_direct_binding_gap_still_open": aqp1_direct_binding_gap_still_open,
        "transporter_placeholder_burndown_queue_ready": transporter_placeholder_burndown_queue_ready,
        "transporter_placeholder_burndown_queue_artifact": transporter_placeholder_burndown_queue_artifact,
        "transporter_placeholder_burndown_queue_row_count": transporter_placeholder_burndown_queue_row_count,
        "glut1_second_wave_source_confirmation_packet_ready": glut1_second_wave_source_confirmation_packet_ready,
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_second_wave_source_confirmation_packet_artifact,
        "glut1_second_wave_source_confirmation_packet_row_count": glut1_second_wave_source_confirmation_packet_row_count,
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_second_wave_source_confirmation_primary_focus_ligand,
        "glut1_second_wave_direct_quantitative_binding_count": glut1_second_wave_direct_quantitative_binding_count,
        "aqp1_quantitative_provenance_focus_ligand": aqp1_quant_focus_ligand,
        "aqp1_quantitative_provenance_signal": aqp1_quant_signal,
        "aqp1_operator_provenance_note": aqp1_operator_provenance_note,
        **local_engine_summary,
        "next_required_step": family_next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Expansion Status Rollup",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- highest_gap_family: `{s['highest_gap_family']}`",
        f"- all_tracked_family_accounting_closed: `{s['all_tracked_family_accounting_closed']}`",
        f"- transporter_negative_accounting_closed: `{s['transporter_negative_accounting_closed']}`",
        f"- aqp1_surrogate_accounting_closed: `{s['aqp1_surrogate_accounting_closed']}`",
        f"- local_engine_commercialization_queue_clear: `{s['local_engine_commercialization_queue_clear']}`",
        f"- pending_capture_total: `{s['pending_capture_total']}`",
        f"- source_linked_total: `{s['source_linked_total']}`",
        f"- supportive_total: `{s['supportive_total']}`",
        f"- ready_like_total: `{s['ready_like_total']}`",
        f"- aqp1_exact_human_activity_count: `{s['aqp1_exact_human_activity_count']}`",
        f"- aqp1_first_wave_source_confirmation_primary_focus_ligand: `{s['aqp1_first_wave_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_first_wave_source_confirmation_exact_human_reference_ligand: `{s['aqp1_first_wave_source_confirmation_exact_human_reference_ligand']}`",
        f"- aqp1_first_wave_source_confirmation_signal: `{s['aqp1_first_wave_source_confirmation_signal']}`",
        f"- aqp1_first_wave_follow_on_packet_ready: `{s['aqp1_first_wave_follow_on_packet_ready']}`",
        f"- aqp1_first_wave_follow_on_packet_row_count: `{s['aqp1_first_wave_follow_on_packet_row_count']}`",
        f"- aqp1_first_wave_follow_on_targets: `{s['aqp1_first_wave_follow_on_targets']}`",
        f"- aqp1_first_wave_follow_on_packet_artifact: `{s['aqp1_first_wave_follow_on_packet_artifact']}`",
        f"- aqp1_first_wave_follow_on_packet_signal: `{s['aqp1_first_wave_follow_on_packet_signal']}`",
        f"- aqp1_follow_on_blocker_decomposition_ready: `{s['aqp1_follow_on_blocker_decomposition_ready']}`",
        f"- aqp1_follow_on_blocker_count: `{s['aqp1_follow_on_blocker_count']}`",
        f"- aqp1_follow_on_exact_human_nonbinding_count: `{s['aqp1_follow_on_exact_human_nonbinding_count']}`",
        f"- aqp1_follow_on_exact_target_pair_absent_count: `{s['aqp1_follow_on_exact_target_pair_absent_count']}`",
        f"- aqp1_follow_on_high_or_medium_potential_count: `{s['aqp1_follow_on_high_or_medium_potential_count']}`",
        f"- aqp1_follow_on_claim_safe_kcal_ready_count: `{s['aqp1_follow_on_claim_safe_kcal_ready_count']}`",
        f"- aqp1_follow_on_source_confirmation_primary_focus_ligand: `{s['aqp1_follow_on_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_follow_on_exact_human_guardrail_ligand: `{s['aqp1_follow_on_exact_human_guardrail_ligand']}`",
        f"- aqp1_follow_on_blocking_signal: `{s['aqp1_follow_on_blocking_signal']}`",
        f"- aqp1_follow_on_next_required_step: `{s['aqp1_follow_on_next_required_step']}`",
        f"- aqp1_follow_on_blocker_decomposition_artifact: `{s['aqp1_follow_on_blocker_decomposition_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_ready: `{s['aqp1_follow_on_source_confirmation_packet_ready']}`",
        f"- aqp1_follow_on_source_confirmation_packet_artifact: `{s['aqp1_follow_on_source_confirmation_packet_artifact']}`",
        f"- aqp1_follow_on_source_confirmation_packet_row_count: `{s['aqp1_follow_on_source_confirmation_packet_row_count']}`",
        f"- aqp1_functional_kcal_surrogate_ready: `{s['aqp1_functional_kcal_surrogate_ready']}`",
        f"- aqp1_functional_kcal_surrogate_artifact: `{s['aqp1_functional_kcal_surrogate_artifact']}`",
        f"- aqp1_functional_kcal_surrogate_ready_count: `{s['aqp1_functional_kcal_surrogate_ready_count']}`",
        f"- aqp1_functional_kcal_surrogate_closure_allowed: `{s['aqp1_functional_kcal_surrogate_closure_allowed']}`",
        f"- aqp1_direct_binding_gap_still_open: `{s['aqp1_direct_binding_gap_still_open']}`",
        f"- transporter_placeholder_burndown_queue_ready: `{s['transporter_placeholder_burndown_queue_ready']}`",
        f"- transporter_placeholder_burndown_queue_artifact: `{s['transporter_placeholder_burndown_queue_artifact']}`",
        f"- transporter_placeholder_burndown_queue_row_count: `{s['transporter_placeholder_burndown_queue_row_count']}`",
        f"- aqp1_quantitative_provenance_focus_ligand: `{s['aqp1_quantitative_provenance_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal']}`",
        f"- aqp1_operator_provenance_note: `{s['aqp1_operator_provenance_note']}`",
        f"- local_engine_commercialization_queue_ready: `{s['local_engine_commercialization_queue_ready']}`",
        f"- local_engine_commercialization_queue_artifact: `{s['local_engine_commercialization_queue_artifact']}`",
        f"- local_engine_commercialization_queue_top_priority_id: `{s['local_engine_commercialization_queue_top_priority_id']}`",
        f"- local_engine_commercialization_queue_top_priority_status: `{s['local_engine_commercialization_queue_top_priority_status']}`",
        f"- local_engine_commercialization_queue_blocked_count: `{s['local_engine_commercialization_queue_blocked_count']}`",
        f"- local_engine_commercialization_queue_nightly_gate_burndown_artifact: `{s['local_engine_commercialization_queue_nightly_gate_burndown_artifact']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_metric: `{s['local_engine_commercialization_queue_nightly_gate_primary_metric']}`",
        f"- local_engine_commercialization_queue_nightly_gate_primary_delta: `{s['local_engine_commercialization_queue_nightly_gate_primary_delta']}`",
        f"- local_engine_commercialization_queue_blocker_note: `{s['local_engine_commercialization_queue_blocker_note']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| family | phase | current_scope | source_linked_count | pending_capture_count | supportive_count | ready_like_count | blocking_signal |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['phase']}` | `{row['current_scope']}` | "
            f"{row['source_linked_count']} | {row['pending_capture_count']} | {row['supportive_count']} | {row['ready_like_count']} | "
            f"`{row['blocking_signal']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact current rollup for CA2/PXR/transporter/AQP1 family-expansion status.")
    parser.add_argument("--ca2-capture-intake-json", default=DEFAULT_CA2_CAPTURE_INTAKE_JSON)
    parser.add_argument("--ca2-commit-json", default=DEFAULT_CA2_COMMIT_JSON)
    parser.add_argument("--pxr-capture-intake-json", default=DEFAULT_PXR_CAPTURE_INTAKE_JSON)
    parser.add_argument("--pxr-commit-json", default=DEFAULT_PXR_COMMIT_JSON)
    parser.add_argument("--transporter-capture-intake-json", default=DEFAULT_TRANSPORTER_CAPTURE_INTAKE_JSON)
    parser.add_argument("--transporter-apply-status-json", default=DEFAULT_TRANSPORTER_APPLY_STATUS_JSON)
    parser.add_argument("--aqp1-capture-intake-json", default=DEFAULT_AQP1_CAPTURE_INTAKE_JSON)
    parser.add_argument("--aqp1-first-seed-json", default=DEFAULT_AQP1_FIRST_SEED_JSON)
    parser.add_argument(
        "--aqp1-first-wave-source-confirmation-json",
        default=DEFAULT_AQP1_FIRST_WAVE_SOURCE_CONFIRMATION_JSON,
    )
    parser.add_argument("--aqp1-first-wave-follow-on-json", default=DEFAULT_AQP1_FIRST_WAVE_FOLLOW_ON_JSON)
    parser.add_argument(
        "--aqp1-follow-on-blocker-decomposition-json",
        default=DEFAULT_AQP1_FOLLOW_ON_BLOCKER_DECOMPOSITION_JSON,
    )
    parser.add_argument(
        "--aqp1-follow-on-source-confirmation-packet-json",
        default=DEFAULT_AQP1_FOLLOW_ON_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument(
        "--aqp1-functional-kcal-surrogate-json",
        default=DEFAULT_AQP1_FUNCTIONAL_KCAL_SURROGATE_JSON,
    )
    parser.add_argument(
        "--transporter-placeholder-burndown-queue-json",
        default=DEFAULT_TRANSPORTER_PLACEHOLDER_BURNDOWN_QUEUE_JSON,
    )
    parser.add_argument(
        "--glut1-second-wave-source-confirmation-packet-json",
        default=DEFAULT_GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET_JSON,
    )
    parser.add_argument(
        "--aqp1-quantitative-provenance-packet-json",
        default=DEFAULT_AQP1_QUANTITATIVE_PROVENANCE_PACKET_JSON,
    )
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
    parser.add_argument(
        "--local-engine-commercialization-queue-json",
        default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_capture_intake_json),
        _load_json(args.ca2_commit_json),
        _load_json(args.pxr_capture_intake_json),
        _load_json(args.pxr_commit_json),
        _load_json(args.transporter_capture_intake_json),
        _load_json(args.transporter_apply_status_json),
        _load_json(args.aqp1_capture_intake_json),
        _load_json(args.aqp1_first_seed_json),
        _load_json(args.aqp1_first_wave_source_confirmation_json),
        _load_json(args.aqp1_first_wave_follow_on_json),
        _load_json(args.aqp1_quantitative_provenance_packet_json),
        _load_json(args.execution_json),
        aqp1_follow_on_blocker_decomposition=_load_json(args.aqp1_follow_on_blocker_decomposition_json),
        aqp1_follow_on_source_confirmation_packet=_maybe_load_json(
            args.aqp1_follow_on_source_confirmation_packet_json
        ),
        aqp1_functional_kcal_surrogate_packet=_maybe_load_json(args.aqp1_functional_kcal_surrogate_json),
        transporter_placeholder_burndown_queue=_maybe_load_json(args.transporter_placeholder_burndown_queue_json),
        glut1_second_wave_source_confirmation_packet=_maybe_load_json(
            args.glut1_second_wave_source_confirmation_packet_json
        ),
        local_engine_commercialization_queue=_maybe_load_json(args.local_engine_commercialization_queue_json),
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
