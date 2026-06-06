#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import (
    load_json,
    maybe_load_json,
    queue_status_is_resolved,
    queue_status_to_execution_state,
    write_artifact,
)

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_VALIDATION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_UPSTREAM_FINAL_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_wave2_protein_run_queue_current.md"

TARGET_SPECS: tuple[dict[str, str], ...] = (
    {
        "target_key": "cathepsin_k",
        "target_id": "Cathepsin K",
        "partner_track_id": "acidic_protease_wave2",
        "launch_json": "runs/cathepsin_k_launch_packet_current.json",
        "transition_json": "runs/cathepsin_k_result_review_current.json",
        "run_record_json": "runs/cathepsin_k_run_record_current.json",
        "launch_packet_artifact": "runs/cathepsin_k_launch_packet_current.md",
        "transition_artifact": "runs/cathepsin_k_result_review_current.md",
        "run_record_artifact": "runs/cathepsin_k_run_record_current.md",
        "companion_gate_label": "cathepsin-family / acidic-pH specificity panel",
    },
    {
        "target_key": "dengue_ns2b_ns3_protease",
        "target_id": "Dengue NS2B-NS3 protease",
        "partner_track_id": "IPK_dengue",
        "launch_json": "runs/dengue_ns2b_ns3_protease_launch_packet_current.json",
        "transition_json": "runs/dengue_ns2b_ns3_protease_result_review_current.json",
        "run_record_json": "runs/dengue_ns2b_ns3_protease_run_record_current.json",
        "launch_packet_artifact": "runs/dengue_ns2b_ns3_protease_launch_packet_current.md",
        "transition_artifact": "runs/dengue_ns2b_ns3_protease_result_review_current.md",
        "run_record_artifact": "runs/dengue_ns2b_ns3_protease_run_record_current.md",
        "companion_gate_label": "flaviviral protease orthogonal panel plus shallow-pocket negative controls",
    },
    {
        "target_key": "dpre1",
        "target_id": "DprE1",
        "partner_track_id": "TB_Alliance",
        "launch_json": "runs/dpre1_launch_packet_current.json",
        "transition_json": "runs/dpre1_result_review_current.json",
        "run_record_json": "runs/dpre1_run_record_current.json",
        "launch_packet_artifact": "runs/dpre1_launch_packet_current.md",
        "transition_artifact": "runs/dpre1_result_review_current.md",
        "run_record_artifact": "runs/dpre1_run_record_current.md",
        "companion_gate_label": "host-enzyme and whole-cell orthogonal validation panel",
    },
    {
        "target_key": "tcruzi_krs1",
        "target_id": "T. cruzi KRS1",
        "partner_track_id": "DNDi_Chagas_backup",
        "launch_json": "runs/tcruzi_krs1_launch_packet_current.json",
        "transition_json": "runs/tcruzi_krs1_result_review_current.json",
        "run_record_json": "runs/tcruzi_krs1_run_record_current.json",
        "launch_packet_artifact": "runs/tcruzi_krs1_launch_packet_current.md",
        "transition_artifact": "runs/tcruzi_krs1_result_review_current.md",
        "run_record_artifact": "runs/tcruzi_krs1_run_record_current.md",
        "companion_gate_label": "host aaRS selectivity panel",
    },
    {
        "target_key": "lrrk2",
        "target_id": "LRRK2",
        "partner_track_id": "MJFF_LRRK2",
        "launch_json": "runs/lrrk2_launch_packet_current.json",
        "transition_json": "runs/lrrk2_result_review_current.json",
        "run_record_json": "runs/lrrk2_run_record_current.json",
        "launch_packet_artifact": "runs/lrrk2_launch_packet_current.md",
        "transition_artifact": "runs/lrrk2_result_review_current.md",
        "run_record_artifact": "runs/lrrk2_run_record_current.md",
        "companion_gate_label": "kinase selectivity and CNS-relevant liability panel",
    },
)


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _rows_by_target(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in ((payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }


def _first_text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _artifact_present(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    if (payload.get("summary", {}) or {}):
        return True
    return bool(payload.get("rows", []) or [])


def _transition_queue_status(summary: dict[str, Any]) -> str:
    text = _first_text(summary, "queue_status_now", "result_review_gate_status")
    if text:
        return text
    raw = _first_text(summary, "execution_state")
    if raw in {"ready_to_launch", "running", "result_ready", "explicit_hold", "blocked_on_previous_review", "blocked_on_target_content"}:
        return raw if raw.startswith("blocked") or raw == "running" else {
            "ready_to_launch": "ready_after_previous_review",
            "result_ready": "result_ready_for_wave2_release",
            "explicit_hold": "explicit_hold_ready_for_wave2_release",
        }.get(raw, raw)
    return ""


def final2_release_gate_open(summary: dict[str, Any]) -> bool:
    if "final_release_blocked" in summary:
        return not bool(summary.get("final_release_blocked", True))
    gate_text = _first_text(summary, "final_release_gate_status", "next_queue_release_gate_status", "queue_status_now", "status").lower()
    if not gate_text:
        return False
    if "blocked" in gate_text:
        return False
    return "open" in gate_text or "result_ready" in gate_text or "explicit_hold" in gate_text


def ordered_wave2_specs(portfolio_payload: dict[str, Any] | None) -> list[dict[str, str]]:
    rows = [dict(row) for row in ((portfolio_payload or {}).get("rows", []) or []) if str(row.get("wave", "")).strip() == "Wave 2"]
    spec_by_target = {spec["target_id"]: dict(spec) for spec in TARGET_SPECS}
    ordered = [spec_by_target[row["target_id"]] for row in rows if row.get("target_id") in spec_by_target]
    if ordered:
        return ordered
    return [dict(spec) for spec in TARGET_SPECS]


def load_target_payloads(kind: str) -> dict[str, dict[str, Any]]:
    path_key = f"{kind}_json"
    return {spec["target_key"]: maybe_load_json(spec[path_key]) for spec in TARGET_SPECS}


def _queue_next_required_step(rows: list[dict[str, Any]], upstream_gate_open: bool) -> str:
    if not upstream_gate_open:
        return "Keep Wave 2 behind the LbDHODH final-release gate. Once that gate opens, Cathepsin K becomes the first live Wave 2 slot."

    active_index = next(
        (idx for idx, row in enumerate(rows) if not queue_status_is_resolved(row.get("queue_status", ""))),
        None,
    )
    if active_index is None:
        return "Wave 2 is fully wired for serialized execution after final2; start only the first ready row when needed."

    active_row = rows[active_index]
    active_target = str(active_row.get("target_id", "")).strip() or "the current Wave 2 target"
    queue_status = str(active_row.get("queue_status", "")).strip()
    placeholder_state = str(active_row.get("placeholder_state", "")).strip()
    predecessor = rows[active_index - 1]["target_id"] if active_index > 0 else "LbDHODH"

    if queue_status == "blocked_on_target_content":
        return f"The final2 gate is open, but {active_target} still needs its compound-fill-backed launch readiness before the serialized Wave 2 chain can advance."
    if queue_status in {"ready_first", "ready_after_previous_review"}:
        return f"{active_target} is the current active Wave 2 slot. Launch it before any later Wave 2 target advances."
    if "running" in queue_status:
        return f"{active_target} is running. Keep later Wave 2 targets blocked until it reaches result-ready or explicit hold."
    if queue_status == "blocked_on_previous_review":
        if active_index == 0:
            return "Keep Wave 2 behind the LbDHODH final-release gate. Once that gate opens, Cathepsin K becomes the first live Wave 2 slot."
        if placeholder_state != "live_target_specific_packet_present":
            return f"{active_target} is still blocked behind {predecessor}; its own launch/result surfaces must already be present before it can become the next active slot."
        return f"Keep {active_target} blocked until {predecessor} reaches result-ready or explicit hold."
    return f"Use the {active_target} queue row as the active Wave 2 control surface."


def build_payload(
    portfolio_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    upstream_final_review_payload: dict[str, Any] | None,
    launch_payloads: dict[str, dict[str, Any]] | None = None,
    transition_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    portfolio_s = _summary(portfolio_payload)
    validation_s = _summary(validation_payload)
    upstream_s = _summary(upstream_final_review_payload)
    portfolio_rows = _rows_by_target(portfolio_payload)
    validation_rows = _rows_by_target(validation_payload)
    launch_map = dict(launch_payloads or {})
    transition_map = dict(transition_payloads or {})
    specs = ordered_wave2_specs(portfolio_payload)

    upstream_gate_open = final2_release_gate_open(upstream_s)
    upstream_gate_status = _first_text(upstream_s, "final_release_gate_status", "next_queue_release_gate_status", "status") or "blocked_on_final2_final_review"
    previous_resolved = upstream_gate_open

    rows: list[dict[str, Any]] = []
    placeholder_target_count = 0
    missing_target_specific_packet_count = 0
    missing_launch_packet_count = 0
    missing_transition_packet_count = 0

    for queue_order, spec in enumerate(specs, start=1):
        portfolio_row = portfolio_rows.get(spec["target_id"], {})
        validation_row = validation_rows.get(spec["target_id"], {})
        launch_s = _summary(launch_map.get(spec["target_key"]))
        transition_s = _summary(transition_map.get(spec["target_key"]))
        has_launch = _artifact_present(launch_map.get(spec["target_key"]))
        has_transition = _artifact_present(transition_map.get(spec["target_key"]))
        placeholder_parts: list[str] = []
        if not has_launch:
            placeholder_parts.append("missing_launch_packet")
            missing_launch_packet_count += 1
        if not has_transition:
            placeholder_parts.append("missing_transition_surface")
            missing_transition_packet_count += 1
        if placeholder_parts:
            placeholder_target_count += 1
            missing_target_specific_packet_count += 1

        queue_status = _transition_queue_status(transition_s)
        if not queue_status:
            if not previous_resolved:
                queue_status = "blocked_on_previous_review"
            elif placeholder_parts:
                queue_status = "blocked_on_target_content"
            else:
                queue_status = "ready_first" if queue_order == 1 else "ready_after_previous_review"

        next_target_id = specs[queue_order]["target_id"] if queue_order < len(specs) else "any later Wave 2 release"
        previous_target_id = specs[queue_order - 2]["target_id"] if queue_order > 1 else "LbDHODH"
        if queue_order == 1:
            advance_gate = (
                f"{spec['target_id']} stays behind the final2 release gate until LbDHODH reaches result-ready or explicit hold"
                if not upstream_gate_open
                else f"Replace the {spec['target_id']} launch/result surfaces before the first Wave 2 slot can go live"
                if placeholder_parts
                else f"{spec['target_id']} is the active first Wave 2 slot; keep {next_target_id} blocked until it reaches result-ready or explicit hold"
            )
        else:
            advance_gate = (
                f"{spec['target_id']} cannot open before {previous_target_id} resolves and its own launch/result surfaces are present"
                if not previous_resolved and placeholder_parts
                else f"{spec['target_id']} cannot open before {previous_target_id} resolves"
                if not previous_resolved
                else f"{previous_target_id} is resolved, but {spec['target_id']} still needs launch/result surfaces before it can open"
                if placeholder_parts
                else f"{spec['target_id']} may open now that {previous_target_id} is resolved"
            )

        rows.append(
            {
                "queue_order": queue_order,
                "target_id": spec["target_id"],
                "launch_packet_artifact": spec["launch_packet_artifact"],
                "transition_artifact": spec["transition_artifact"],
                "partner_track_id": str(launch_s.get("partner_track_id", spec["partner_track_id"])).strip() or spec["partner_track_id"],
                "transition_status": _first_text(transition_s, "status") or "missing_transition_surface",
                "queue_status": queue_status,
                "advance_gate": advance_gate,
                "parallel_lane_artifact": "runs/wetlab_validation_companion_panels_current.md",
                "placeholder_state": "+".join(placeholder_parts) or "live_target_specific_packet_present",
                "companion_panel": _first_text(validation_row, "primary_companion_panel") or spec["companion_gate_label"],
                "portfolio_wave": _first_text(portfolio_row, "wave") or "Wave 2",
                "portfolio_priority_score": portfolio_row.get("total_priority_score", ""),
                "upstream_gate_status": upstream_gate_status,
            }
        )
        previous_resolved = queue_status_is_resolved(queue_status)

    ready_now_target_count = sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready"))
    blocked_on_previous_review_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_previous_review")
    blocked_on_target_content_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_target_content")
    running_target_count = sum(1 for row in rows if "running" in str(row.get("queue_status", "")))
    resolved_target_count = sum(1 for row in rows if queue_status_is_resolved(row.get("queue_status", "")))

    next_required_step = _queue_next_required_step(rows, upstream_gate_open)

    return {
        "summary": {
            "status": "wetlab_wave2_protein_run_queue_ready",
            "queue_target_count": len(rows),
            "portfolio_status": str(portfolio_s.get("status", "")).strip(),
            "validation_companion_status": str(validation_s.get("status", "")).strip(),
            "upstream_final2_review_status": str(upstream_s.get("status", "")).strip(),
            "upstream_final2_gate_open": upstream_gate_open,
            "upstream_final2_gate_status": upstream_gate_status,
            "ready_now_target_count": ready_now_target_count,
            "blocked_on_previous_review_count": blocked_on_previous_review_count,
            "blocked_on_target_content_count": blocked_on_target_content_count,
            "running_target_count": running_target_count,
            "resolved_target_count": resolved_target_count,
            "placeholder_target_count": placeholder_target_count,
            "missing_target_specific_packet_count": missing_target_specific_packet_count,
            "missing_launch_packet_count": missing_launch_packet_count,
            "missing_transition_packet_count": missing_transition_packet_count,
            "first_target": rows[0]["target_id"] if rows else "",
            "last_target": rows[-1]["target_id"] if rows else "",
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_final2",
            "portfolio_artifact": "runs/wetlab_partner_target_portfolio_current.md",
            "validation_companion_artifact": "runs/wetlab_validation_companion_panels_current.md",
            "upstream_final2_review_artifact": "runs/lbdhodh_result_review_current.md",
            "current_wave2_packet_artifacts": "launch_and_result_review_artifacts_are_loaded_when_present",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized wave2 wet-lab protein run queue.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--upstream-final-review-json", default=DEFAULT_UPSTREAM_FINAL_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.portfolio_json),
        load_json(args.validation_json),
        maybe_load_json(args.upstream_final_review_json),
        load_target_payloads("launch"),
        load_target_payloads("transition"),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave2 Protein Run Queue", payload)


if __name__ == "__main__":
    main()
