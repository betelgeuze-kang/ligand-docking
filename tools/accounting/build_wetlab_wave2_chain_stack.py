#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.build_wetlab_wave2_protein_run_queue import (
    DEFAULT_OUT_MD as DEFAULT_QUEUE_MD,
    DEFAULT_PORTFOLIO_JSON,
    DEFAULT_UPSTREAM_FINAL_REVIEW_JSON,
    DEFAULT_VALIDATION_JSON,
    TARGET_SPECS,
    _artifact_present,
    _summary,
    final2_release_gate_open,
    load_target_payloads,
    ordered_wave2_specs,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, queue_status_to_execution_state, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_wave2_protein_run_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_wave2_chain_stack_current.md"


def build_payload(
    portfolio_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    upstream_final_review_payload: dict[str, Any] | None,
    wave2_queue_payload: dict[str, Any] | None,
    launch_payloads: dict[str, dict[str, Any]] | None = None,
    run_record_payloads: dict[str, dict[str, Any]] | None = None,
    transition_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    portfolio_s = _summary(portfolio_payload)
    validation_s = _summary(validation_payload)
    upstream_s = _summary(upstream_final_review_payload)
    queue_s = _summary(wave2_queue_payload)
    queue_rows = {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in ((wave2_queue_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }
    launch_map = dict(launch_payloads or {})
    run_record_map = dict(run_record_payloads or {})
    transition_map = dict(transition_payloads or {})
    specs = ordered_wave2_specs(portfolio_payload)

    rows: list[dict[str, Any]] = [
        {
            "chain_item": "final2_final_review",
            "artifact_path": "runs/lbdhodh_result_review_current.md",
            "current_signal": str(upstream_s.get("final_release_gate_status", "")).strip() or str(upstream_s.get("status", "")).strip() or "missing",
            "queue_effect": "must_open_before_cathepsin_k_can_leave_blocked_on_previous_review",
        }
    ]
    stack_gate_states: dict[str, dict[str, Any]] = {}
    missing_run_record_count = 0

    for spec in specs:
        target_id = spec["target_id"]
        queue_row = queue_rows.get(target_id, {})
        placeholder_state = str(queue_row.get("placeholder_state", "")).strip() or "missing_launch_packet+missing_transition_surface"
        launch_ready = _artifact_present(launch_map.get(spec["target_key"]))
        run_record_ready = _artifact_present(run_record_map.get(spec["target_key"]))
        transition_ready = _artifact_present(transition_map.get(spec["target_key"]))
        if not run_record_ready:
            missing_run_record_count += 1
        stack_gate_states[spec["target_key"]] = {
            "target_id": target_id,
            "queue_status": str(queue_row.get("queue_status", "")).strip(),
            "execution_state": queue_status_to_execution_state(queue_row.get("queue_status", "")),
            "launch_packet_ready": launch_ready,
            "transition_ready": transition_ready,
            "run_record_ready": run_record_ready,
            "placeholder_state": placeholder_state,
        }
        rows.append(
            {
                "chain_item": (
                    f"{spec['target_key']}_runtime_gate"
                    if placeholder_state == "live_target_specific_packet_present"
                    else f"{spec['target_key']}_placeholder_gate"
                ),
                "artifact_path": spec["transition_artifact"],
                "current_signal": str(queue_row.get("queue_status", "")).strip() or "missing_wave2_queue_row",
                "queue_effect": (
                    "serialized_gate_driven_by_target_specific_result_review"
                    if placeholder_state == "live_target_specific_packet_present"
                    else "placeholder_only_until_target_specific_launch_run_artifacts_exist"
                ),
            }
        )

    rows.append(
        {
            "chain_item": "wave2_protein_run_queue",
            "artifact_path": "runs/wetlab_wave2_protein_run_queue_current.md",
            "current_signal": str(queue_s.get("status", "")).strip() or "missing",
            "queue_effect": "serialized_wave2_queue_source_of_truth",
        }
    )

    next_required_step = (
        str(queue_s.get("next_required_step", "")).strip()
        or "Use the wave2 queue summary as the active gate narrative for this chain stack."
    )

    return {
        "summary": {
            "status": "wetlab_wave2_chain_stack_ready",
            "target_count": len(specs),
            "artifact_kind": "chain_stack",
            "portfolio_ready": str(portfolio_s.get("status", "")).strip() == "wetlab_partner_target_portfolio_ready",
            "validation_companion_ready": str(validation_s.get("status", "")).strip() == "wetlab_validation_companion_panels_ready",
            "final2_final_review_ready": bool(upstream_s),
            "final2_final_gate_open": final2_release_gate_open(upstream_s),
            "wave2_queue_ready": str(queue_s.get("status", "")).strip() == "wetlab_wave2_protein_run_queue_ready",
            "ready_now_target_count": int(queue_s.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue_s.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(queue_s.get("blocked_on_target_content_count", 0) or 0),
            "running_target_count": int(queue_s.get("running_target_count", 0) or 0),
            "resolved_target_count": int(queue_s.get("resolved_target_count", 0) or 0),
            "placeholder_target_count": int(queue_s.get("placeholder_target_count", 0) or 0),
            "missing_target_specific_packet_count": int(queue_s.get("missing_target_specific_packet_count", 0) or 0),
            "missing_run_record_count": missing_run_record_count,
            "stack_gate_states": stack_gate_states,
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_final2",
            "queue_artifact": "runs/wetlab_wave2_protein_run_queue_current.md",
            "runtime_runbook_artifact": "runs/wetlab_wave2_runtime_runbook_current.md",
            "execution_console_artifact": "runs/wetlab_wave2_execution_console_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wave2 chain stack for Cathepsin K -> Dengue NS2B-NS3 protease -> DprE1 -> T. cruzi KRS1 -> LRRK2.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--upstream-final-review-json", default=DEFAULT_UPSTREAM_FINAL_REVIEW_JSON)
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.portfolio_json),
        load_json(args.validation_json),
        maybe_load_json(args.upstream_final_review_json),
        maybe_load_json(args.queue_json),
        load_target_payloads("launch"),
        load_target_payloads("run_record"),
        load_target_payloads("transition"),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave2 Chain Stack", payload)


if __name__ == "__main__":
    main()
