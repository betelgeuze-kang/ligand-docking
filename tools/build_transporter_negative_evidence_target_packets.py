#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_AQP1_NEGATIVE_HANDOFF_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
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
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_negative_evidence_target_packets_current.json"
DEFAULT_OUT_CSV = "runs/transporter_negative_evidence_target_packets_current.csv"
DEFAULT_OUT_MD = "runs/transporter_negative_evidence_target_packets_current.md"

TARGET_PACKET_ARTIFACTS = {
    "AQP1": "runs/aqp1_negative_review_handoff_packet_current.md",
    "GLUT1": "runs/glut1_negative_review_handoff_packet_current.md",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _queue_ranges(review_rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    negative_rows = [
        row
        for row in review_rows
        if _text(row.get("review_phase")) == "negative_slots_first"
    ]
    by_target: dict[str, dict[str, int]] = {}
    for queue_rank, row in enumerate(negative_rows, start=1):
        target_id = _text(row.get("target_id"))
        if not target_id:
            continue
        if target_id not in by_target:
            by_target[target_id] = {"queue_rank_start": queue_rank, "queue_rank_end": queue_rank, "queue_row_count": 1}
        else:
            by_target[target_id]["queue_rank_end"] = queue_rank
            by_target[target_id]["queue_row_count"] += 1
    return by_target


def _phase_count(review_rows: list[dict[str, Any]], target_id: str, phase: str) -> int:
    return sum(
        1
        for row in review_rows
        if _text(row.get("target_id")) == target_id and _text(row.get("review_phase")) == phase
    )


def build_payload(
    negative_day_plan_payload: dict[str, Any],
    aqp1_negative_handoff_payload: dict[str, Any] | None = None,
    aqp1_negative_source_exclusion_payload: dict[str, Any] | None = None,
    aqp1_negative_slot_closure_payload: dict[str, Any] | None = None,
    aqp1_negative_acquisition_payload: dict[str, Any] | None = None,
    glut1_source_confirmation_payload: dict[str, Any] | None = None,
    aqp1_negative_confirmation_payload: dict[str, Any] | None = None,
    aqp1_negative_slot_resolution_payload: dict[str, Any] | None = None,
    aqp1_negative_candidate_frontier_payload: dict[str, Any] | None = None,
    aqp1_negative_frontier_resolution_payload: dict[str, Any] | None = None,
    aqp1_negative_primary_probe_payload: dict[str, Any] | None = None,
    aqp1_negative_exact_source_outcome_payload: dict[str, Any] | None = None,
    aqp1_negative_primary_probe_resolution_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    day_summary = dict((negative_day_plan_payload or {}).get("summary", {}) or {})
    target_rows = list((negative_day_plan_payload or {}).get("target_rows", []) or [])
    review_rows = list((negative_day_plan_payload or {}).get("review_rows", []) or [])
    aqp1_summary = dict((aqp1_negative_handoff_payload or {}).get("summary", {}) or {})
    aqp1_exclusion_summary = dict((aqp1_negative_source_exclusion_payload or {}).get("summary", {}) or {})
    aqp1_slot_closure_summary = dict((aqp1_negative_slot_closure_payload or {}).get("summary", {}) or {})
    aqp1_acquisition_summary = dict((aqp1_negative_acquisition_payload or {}).get("summary", {}) or {})
    glut1_source_summary = dict((glut1_source_confirmation_payload or {}).get("summary", {}) or {})
    aqp1_confirmation_summary = dict((aqp1_negative_confirmation_payload or {}).get("summary", {}) or {})
    aqp1_slot_resolution_summary = dict((aqp1_negative_slot_resolution_payload or {}).get("summary", {}) or {})
    aqp1_candidate_frontier_summary = dict((aqp1_negative_candidate_frontier_payload or {}).get("summary", {}) or {})
    aqp1_frontier_resolution_summary = dict((aqp1_negative_frontier_resolution_payload or {}).get("summary", {}) or {})
    aqp1_primary_probe_summary = dict((aqp1_negative_primary_probe_payload or {}).get("summary", {}) or {})
    aqp1_exact_source_outcome_summary = dict((aqp1_negative_exact_source_outcome_payload or {}).get("summary", {}) or {})
    aqp1_primary_probe_resolution_summary = dict((aqp1_negative_primary_probe_resolution_payload or {}).get("summary", {}) or {})
    queue_ranges = _queue_ranges(review_rows)

    rows: list[dict[str, Any]] = []
    for target_rank, target_row in enumerate(target_rows, start=1):
        target_id = _text(target_row.get("target_id"))
        queue_info = queue_ranges.get(target_id, {})
        negative_slot_count = _int(target_row.get("negative_slot_count"))
        caution_reference_count = _phase_count(review_rows, target_id, "caution_references_second")
        blocker_reference_count = _phase_count(review_rows, target_id, "blocker_reference_only")
        primary_artifact = TARGET_PACKET_ARTIFACTS.get(target_id, "")
        secondary_artifact = "runs/transporter_negative_reviewer_day_plan_current.md"
        source_context_artifact = _text(target_row.get("second_wave_source_confirmation_packet_artifact"))
        source_context_focus_ligand = _text(target_row.get("second_wave_source_confirmation_primary_focus_ligand"))
        if target_id == "AQP1":
            primary_artifact = _text(aqp1_slot_closure_summary.get("packet_artifact")) or primary_artifact
            secondary_artifact = (
                _text(aqp1_slot_resolution_summary.get("packet_artifact"))
                or _text(aqp1_confirmation_summary.get("packet_artifact"))
                or _text(aqp1_acquisition_summary.get("packet_artifact"))
                or "runs/aqp1_negative_review_handoff_packet_current.md"
            )
            source_context_artifact = _text(aqp1_exclusion_summary.get("packet_artifact")) or "runs/aqp1_negative_source_exclusion_packet_current.md"
            source_context_focus_ligand = _text(aqp1_exclusion_summary.get("primary_focus_ligand"))
        if target_id == "AQP1" and not secondary_artifact:
            secondary_artifact = (
                _text(aqp1_confirmation_summary.get("packet_artifact"))
                or _text(aqp1_acquisition_summary.get("packet_artifact"))
                or "runs/aqp1_negative_review_handoff_packet_current.md"
            )
        if target_id == "GLUT1" and not source_context_artifact:
            source_context_artifact = "runs/glut1_second_wave_source_confirmation_packet_current.md"
        if target_id == "GLUT1" and not source_context_focus_ligand:
            source_context_focus_ligand = _text(glut1_source_summary.get("primary_focus_ligand")) or "cytochalasin B"

        rows.append(
            {
                "target_rank": target_rank,
                "target_id": target_id,
                "queue_rank_start": _int(queue_info.get("queue_rank_start")),
                "queue_rank_end": _int(queue_info.get("queue_rank_end")),
                "queue_row_count": _int(queue_info.get("queue_row_count")),
                "negative_slot_count": negative_slot_count,
                "caution_reference_count": caution_reference_count,
                "blocker_reference_count": blocker_reference_count,
                "reference_signal_count": caution_reference_count + blocker_reference_count,
                "primary_artifact": primary_artifact,
                "secondary_artifact": secondary_artifact,
                "source_context_artifact": source_context_artifact,
                "source_context_focus_ligand": source_context_focus_ligand,
                "local_evidence_status": _text(target_row.get("local_evidence_status")),
                "authoritative_negative_apply_allowed": False,
                "next_required_step": _text(target_row.get("next_required_step")),
            }
        )

    top_row = rows[0] if rows else {}
    summary = {
        "target_count": len(rows),
        "queue_row_count": sum(_int(row.get("queue_row_count")) for row in rows),
        "top_target_id": _text(top_row.get("target_id")),
        "top_queue_rank_start": _int(top_row.get("queue_rank_start")),
        "top_queue_rank_end": _int(top_row.get("queue_rank_end")),
        "top_primary_artifact": _text(top_row.get("primary_artifact")),
        "aqp1_negative_slot_count": _phase_count(review_rows, "AQP1", "negative_slots_first"),
        "aqp1_reference_signal_count": (
            _phase_count(review_rows, "AQP1", "caution_references_second")
            + _phase_count(review_rows, "AQP1", "blocker_reference_only")
        ),
        "aqp1_source_context_artifact": _text(aqp1_exclusion_summary.get("packet_artifact"))
        or "runs/aqp1_negative_source_exclusion_packet_current.md",
        "aqp1_source_context_primary_focus_ligand": _text(aqp1_exclusion_summary.get("primary_focus_ligand")),
        "aqp1_exact_target_pair_absent_count": _int(aqp1_exclusion_summary.get("exact_target_pair_absent_count")),
        "aqp1_slot_closure_artifact": _text(aqp1_slot_closure_summary.get("packet_artifact"))
        or "runs/aqp1_negative_slot_closure_packet_current.md",
        "aqp1_slot_closure_row_count": _int(aqp1_slot_closure_summary.get("row_count")),
        "aqp1_slot_closure_top_packet_step": _text(aqp1_slot_closure_summary.get("top_packet_step")),
        "aqp1_negative_acquisition_artifact": _text(aqp1_acquisition_summary.get("packet_artifact"))
        or "runs/aqp1_negative_evidence_acquisition_packet_current.md",
        "aqp1_negative_acquisition_row_count": _int(aqp1_acquisition_summary.get("row_count")),
        "aqp1_negative_acquisition_primary_query_label": _text(aqp1_acquisition_summary.get("primary_query_label")),
        "aqp1_negative_acquisition_primary_anchor_pmid": _text(aqp1_acquisition_summary.get("primary_anchor_pmid")),
        "aqp1_negative_confirmation_artifact": _text(aqp1_confirmation_summary.get("packet_artifact"))
        or "runs/aqp1_negative_evidence_confirmation_packet_current.md",
        "aqp1_negative_confirmation_row_count": _int(aqp1_confirmation_summary.get("row_count")),
        "aqp1_negative_confirmation_primary_anchor_pmid": _text(aqp1_confirmation_summary.get("primary_anchor_pmid")),
        "aqp1_negative_confirmation_boundary_positive_pmid": _text(
            aqp1_confirmation_summary.get("boundary_positive_pmid")
        ),
        "aqp1_negative_confirmation_decision": _text(aqp1_confirmation_summary.get("confirmation_decision")),
        "aqp1_negative_slot_resolution_artifact": _text(aqp1_slot_resolution_summary.get("packet_artifact"))
        or "runs/aqp1_negative_slot_resolution_packet_current.md",
        "aqp1_negative_slot_resolution_row_count": _int(aqp1_slot_resolution_summary.get("row_count")),
        "aqp1_negative_slot_resolution_top_packet_step": _text(
            aqp1_slot_resolution_summary.get("top_packet_step")
        ),
        "aqp1_negative_slot_resolution_primary_anchor_pmid": _text(
            aqp1_slot_resolution_summary.get("primary_anchor_pmid")
        ),
        "aqp1_negative_candidate_frontier_artifact": _text(aqp1_candidate_frontier_summary.get("packet_artifact"))
        or "runs/aqp1_negative_candidate_frontier_packet_current.md",
        "aqp1_negative_candidate_frontier_row_count": _int(aqp1_candidate_frontier_summary.get("row_count")),
        "aqp1_negative_candidate_frontier_primary_frontier_candidate": _text(
            aqp1_candidate_frontier_summary.get("primary_frontier_candidate")
        ),
        "aqp1_negative_candidate_frontier_exact_target_pair_absent_count": _int(
            aqp1_candidate_frontier_summary.get("exact_target_pair_absent_count")
        ),
        "aqp1_negative_frontier_resolution_artifact": _text(
            aqp1_frontier_resolution_summary.get("packet_artifact")
        )
        or "runs/aqp1_negative_frontier_resolution_packet_current.md",
        "aqp1_negative_frontier_resolution_row_count": _int(aqp1_frontier_resolution_summary.get("row_count")),
        "aqp1_negative_frontier_resolution_primary_frontier_candidate": _text(
            aqp1_frontier_resolution_summary.get("primary_frontier_candidate")
        ),
        "aqp1_negative_frontier_resolution_solvent_fallback_candidate": _text(
            aqp1_frontier_resolution_summary.get("solvent_fallback_candidate")
        ),
        "aqp1_negative_primary_probe_artifact": _text(aqp1_primary_probe_summary.get("packet_artifact"))
        or "runs/aqp1_negative_primary_probe_packet_current.md",
        "aqp1_negative_primary_probe_row_count": _int(aqp1_primary_probe_summary.get("row_count")),
        "aqp1_negative_primary_probe_candidate": _text(aqp1_primary_probe_summary.get("primary_probe_candidate")),
        "aqp1_negative_primary_probe_source_anchor_pmid": _text(aqp1_primary_probe_summary.get("source_anchor_pmid")),
        "aqp1_negative_exact_source_outcome_artifact": _text(
            aqp1_exact_source_outcome_summary.get("packet_artifact")
        )
        or "runs/aqp1_negative_exact_source_outcome_packet_current.md",
        "aqp1_negative_exact_source_outcome_row_count": _int(
            aqp1_exact_source_outcome_summary.get("row_count")
        ),
        "aqp1_negative_exact_source_almost_unaffected_candidate_count": _int(
            aqp1_exact_source_outcome_summary.get("almost_unaffected_candidate_count")
        ),
        "aqp1_negative_exact_source_primary_probe_candidate": _text(
            aqp1_exact_source_outcome_summary.get("primary_negative_probe_candidate")
        ),
        "aqp1_negative_exact_source_small_inhibitor_signal_candidate": _text(
            aqp1_exact_source_outcome_summary.get("small_inhibitor_signal_candidate")
        ),
        "aqp1_negative_exact_source_source_pmid": _text(aqp1_exact_source_outcome_summary.get("source_pmid")),
        "aqp1_negative_exact_source_direct_negative_quantitative_row_found_count": _int(
            aqp1_exact_source_outcome_summary.get("direct_negative_quantitative_row_found_count")
        ),
        "aqp1_negative_exact_source_authoritative_negative_apply_allowed_count": _int(
            aqp1_exact_source_outcome_summary.get("authoritative_negative_apply_allowed_count")
        ),
        "aqp1_negative_primary_probe_resolution_artifact": _text(
            aqp1_primary_probe_resolution_summary.get("packet_artifact")
        )
        or "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
        "aqp1_negative_primary_probe_resolution_row_count": _int(
            aqp1_primary_probe_resolution_summary.get("row_count")
        ),
        "aqp1_negative_primary_probe_resolution_candidate": _text(
            aqp1_primary_probe_resolution_summary.get("primary_probe_candidate")
        ),
        "aqp1_negative_primary_probe_resolution_decision": _text(
            aqp1_primary_probe_resolution_summary.get("resolution_decision")
        ),
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": _text(
            aqp1_primary_probe_resolution_summary.get("solvent_fallback_candidate")
        ),
        "aqp1_negative_primary_probe_resolution_source_anchor_hemolysis_outcome": _text(
            aqp1_primary_probe_resolution_summary.get("source_anchor_hemolysis_outcome")
        ),
        "aqp1_negative_primary_probe_resolution_source_anchor_direct_negative_quantitative_row_found": _bool(
            aqp1_primary_probe_resolution_summary.get("source_anchor_direct_negative_quantitative_row_found")
        ),
        "glut1_negative_slot_count": _phase_count(review_rows, "GLUT1", "negative_slots_first"),
        "glut1_reference_signal_count": (
            _phase_count(review_rows, "GLUT1", "caution_references_second")
            + _phase_count(review_rows, "GLUT1", "blocker_reference_only")
        ),
        "glut1_source_context_artifact": _text(day_summary.get("glut1_second_wave_source_confirmation_packet_artifact"))
        or "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "glut1_source_context_primary_focus_ligand": _text(
            day_summary.get("glut1_second_wave_source_confirmation_primary_focus_ligand")
        )
        or _text(glut1_source_summary.get("primary_focus_ligand"))
        or "cytochalasin B",
        "aqp1_endpoint_status": _text(aqp1_summary.get("endpoint_status")),
        "next_required_step": (
            "Open the AQP1 negative handoff first for queue ranks 1-3, close core_non_binder_01 through core_non_binder_03 in order, "
            "then move to the GLUT1 negative handoff for queue ranks 4-6 while keeping the GLUT1 second-wave source-confirmation packet open as context only."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Negative Evidence Target Packets",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- queue_row_count: `{s['queue_row_count']}`",
        f"- top_target_id: `{s['top_target_id']}`",
        f"- top_queue_range: `{s['top_queue_rank_start']}-{s['top_queue_rank_end']}`",
        f"- aqp1_negative_slot_count: `{s['aqp1_negative_slot_count']}`",
        f"- aqp1_reference_signal_count: `{s['aqp1_reference_signal_count']}`",
        f"- aqp1_source_context_artifact: `{s['aqp1_source_context_artifact']}`",
        f"- aqp1_source_context_primary_focus_ligand: `{s['aqp1_source_context_primary_focus_ligand']}`",
        f"- aqp1_exact_target_pair_absent_count: `{s['aqp1_exact_target_pair_absent_count']}`",
        f"- aqp1_slot_closure_artifact: `{s['aqp1_slot_closure_artifact']}`",
        f"- aqp1_slot_closure_row_count: `{s['aqp1_slot_closure_row_count']}`",
        f"- aqp1_slot_closure_top_packet_step: `{s['aqp1_slot_closure_top_packet_step']}`",
        f"- aqp1_negative_acquisition_artifact: `{s['aqp1_negative_acquisition_artifact']}`",
        f"- aqp1_negative_acquisition_row_count: `{s['aqp1_negative_acquisition_row_count']}`",
        f"- aqp1_negative_acquisition_primary_query_label: `{s['aqp1_negative_acquisition_primary_query_label']}`",
        f"- aqp1_negative_acquisition_primary_anchor_pmid: `{s['aqp1_negative_acquisition_primary_anchor_pmid']}`",
        f"- aqp1_negative_confirmation_artifact: `{s['aqp1_negative_confirmation_artifact']}`",
        f"- aqp1_negative_confirmation_row_count: `{s['aqp1_negative_confirmation_row_count']}`",
        f"- aqp1_negative_confirmation_primary_anchor_pmid: `{s['aqp1_negative_confirmation_primary_anchor_pmid']}`",
        f"- aqp1_negative_confirmation_boundary_positive_pmid: `{s['aqp1_negative_confirmation_boundary_positive_pmid']}`",
        f"- aqp1_negative_confirmation_decision: `{s['aqp1_negative_confirmation_decision']}`",
        f"- aqp1_negative_slot_resolution_artifact: `{s['aqp1_negative_slot_resolution_artifact']}`",
        f"- aqp1_negative_slot_resolution_row_count: `{s['aqp1_negative_slot_resolution_row_count']}`",
        f"- aqp1_negative_slot_resolution_top_packet_step: `{s['aqp1_negative_slot_resolution_top_packet_step']}`",
        f"- aqp1_negative_slot_resolution_primary_anchor_pmid: `{s['aqp1_negative_slot_resolution_primary_anchor_pmid']}`",
        f"- aqp1_negative_candidate_frontier_artifact: `{s['aqp1_negative_candidate_frontier_artifact']}`",
        f"- aqp1_negative_candidate_frontier_row_count: `{s['aqp1_negative_candidate_frontier_row_count']}`",
        f"- aqp1_negative_candidate_frontier_primary_frontier_candidate: `{s['aqp1_negative_candidate_frontier_primary_frontier_candidate']}`",
        f"- aqp1_negative_candidate_frontier_exact_target_pair_absent_count: `{s['aqp1_negative_candidate_frontier_exact_target_pair_absent_count']}`",
        f"- aqp1_negative_frontier_resolution_artifact: `{s['aqp1_negative_frontier_resolution_artifact']}`",
        f"- aqp1_negative_frontier_resolution_row_count: `{s['aqp1_negative_frontier_resolution_row_count']}`",
        f"- aqp1_negative_frontier_resolution_primary_frontier_candidate: `{s['aqp1_negative_frontier_resolution_primary_frontier_candidate']}`",
        f"- aqp1_negative_frontier_resolution_solvent_fallback_candidate: `{s['aqp1_negative_frontier_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_primary_probe_artifact: `{s['aqp1_negative_primary_probe_artifact']}`",
        f"- aqp1_negative_primary_probe_row_count: `{s['aqp1_negative_primary_probe_row_count']}`",
        f"- aqp1_negative_primary_probe_candidate: `{s['aqp1_negative_primary_probe_candidate']}`",
        f"- aqp1_negative_primary_probe_source_anchor_pmid: `{s['aqp1_negative_primary_probe_source_anchor_pmid']}`",
        f"- aqp1_negative_exact_source_outcome_artifact: `{s['aqp1_negative_exact_source_outcome_artifact']}`",
        f"- aqp1_negative_exact_source_outcome_row_count: `{s['aqp1_negative_exact_source_outcome_row_count']}`",
        f"- aqp1_negative_exact_source_almost_unaffected_candidate_count: `{s['aqp1_negative_exact_source_almost_unaffected_candidate_count']}`",
        f"- aqp1_negative_exact_source_primary_probe_candidate: `{s['aqp1_negative_exact_source_primary_probe_candidate']}`",
        f"- aqp1_negative_exact_source_small_inhibitor_signal_candidate: `{s['aqp1_negative_exact_source_small_inhibitor_signal_candidate']}`",
        f"- aqp1_negative_exact_source_source_pmid: `{s['aqp1_negative_exact_source_source_pmid']}`",
        f"- aqp1_negative_exact_source_direct_negative_quantitative_row_found_count: `{s['aqp1_negative_exact_source_direct_negative_quantitative_row_found_count']}`",
        f"- aqp1_negative_exact_source_authoritative_negative_apply_allowed_count: `{s['aqp1_negative_exact_source_authoritative_negative_apply_allowed_count']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_row_count: `{s['aqp1_negative_primary_probe_resolution_row_count']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_source_anchor_hemolysis_outcome: `{s['aqp1_negative_primary_probe_resolution_source_anchor_hemolysis_outcome']}`",
        f"- aqp1_negative_primary_probe_resolution_source_anchor_direct_negative_quantitative_row_found: `{s['aqp1_negative_primary_probe_resolution_source_anchor_direct_negative_quantitative_row_found']}`",
        f"- glut1_negative_slot_count: `{s['glut1_negative_slot_count']}`",
        f"- glut1_reference_signal_count: `{s['glut1_reference_signal_count']}`",
        f"- glut1_source_context_artifact: `{s['glut1_source_context_artifact']}`",
        f"- glut1_source_context_primary_focus_ligand: `{s['glut1_source_context_primary_focus_ligand']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Target Packets",
        "",
        "| target_rank | target_id | queue_range | negative_slot_count | reference_signal_count | primary_artifact | source_context_artifact | source_context_focus_ligand |",
        "| ---: | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['target_rank']} | `{row['target_id']}` | `{row['queue_rank_start']}-{row['queue_rank_end']}` | "
            f"{row['negative_slot_count']} | {row['reference_signal_count']} | `{row['primary_artifact']}` | "
            f"`{row['source_context_artifact']}` | `{row['source_context_focus_ligand']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target-level transporter negative-evidence packet navigation.")
    parser.add_argument("--negative-day-plan-json", default=DEFAULT_NEGATIVE_DAY_PLAN_JSON)
    parser.add_argument("--aqp1-negative-handoff-json", default=DEFAULT_AQP1_NEGATIVE_HANDOFF_JSON)
    parser.add_argument("--aqp1-negative-source-exclusion-json", default=DEFAULT_AQP1_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--aqp1-negative-slot-closure-json", default=DEFAULT_AQP1_NEGATIVE_SLOT_CLOSURE_JSON)
    parser.add_argument("--aqp1-negative-acquisition-json", default=DEFAULT_AQP1_NEGATIVE_ACQUISITION_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
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
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_day_plan_json),
        _load_json(args.aqp1_negative_handoff_json),
        _load_json(args.aqp1_negative_source_exclusion_json),
        _load_json(args.aqp1_negative_slot_closure_json),
        _load_json(args.aqp1_negative_acquisition_json),
        _load_json(args.glut1_source_confirmation_json),
        _load_json(args.aqp1_negative_confirmation_json),
        _load_json(args.aqp1_negative_slot_resolution_json),
        _load_json(args.aqp1_negative_candidate_frontier_json),
        _load_json(args.aqp1_negative_frontier_resolution_json),
        _load_json(args.aqp1_negative_primary_probe_json),
        _load_json(args.aqp1_negative_exact_source_outcome_json),
        _load_json(args.aqp1_negative_primary_probe_resolution_json),
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
