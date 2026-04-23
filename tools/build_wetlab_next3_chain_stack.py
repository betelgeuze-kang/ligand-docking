#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_CRUZAIN_RENDER_JSON = "runs/cruzain_render_suite_current.json"
DEFAULT_PLPRO_RENDER_JSON = "runs/sarscov2_plpro_render_suite_current.json"
DEFAULT_ALK2_RENDER_JSON = "runs/alk2_render_suite_current.json"
DEFAULT_CRUZAIN_LAUNCH_JSON = "runs/cruzain_launch_packet_current.json"
DEFAULT_PLPRO_LAUNCH_JSON = "runs/sarscov2_plpro_launch_packet_current.json"
DEFAULT_ALK2_LAUNCH_JSON = "runs/alk2_launch_packet_current.json"
DEFAULT_CRUZAIN_RUN_RECORD_JSON = "runs/cruzain_run_record_current.json"
DEFAULT_PLPRO_RUN_RECORD_JSON = "runs/sarscov2_plpro_run_record_current.json"
DEFAULT_ALK2_RUN_RECORD_JSON = "runs/alk2_run_record_current.json"
DEFAULT_CRUZAIN_RUN_STATUS_JSON = "runs/cruzain_run_status_current.json"
DEFAULT_PLPRO_RESULT_REVIEW_JSON = "runs/sarscov2_plpro_result_review_current.json"
DEFAULT_ALK2_RESULT_REVIEW_JSON = "runs/alk2_result_review_current.json"
DEFAULT_QUEUE_JSON = "runs/wetlab_next3_protein_run_queue_current.json"
DEFAULT_PRIORITY3_FINAL_REVIEW_JSON = "runs/tcruzi_pde_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_next3_chain_stack_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _first_text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "open", "opened", "ready", "result_ready", "explicit_hold"}:
        return True
    if text in {"0", "false", "no", "n", "blocked", "blocked_on_previous_review", "wave2_release_blocked"}:
        return False
    return bool(text)


def _priority3_final_gate_open(summary: dict[str, Any]) -> bool:
    if "priority3_final_gate_open" in summary:
        return _truthy(summary.get("priority3_final_gate_open"))
    if "wave2_release_blocked" in summary:
        return not _truthy(summary.get("wave2_release_blocked"))
    gate_text = _first_text(
        summary,
        "wave2_release_gate_status",
        "result_review_gate_status",
        "queue_status_now",
        "execution_gate_open",
    ).lower()
    if not gate_text:
        return False
    if "blocked" in gate_text:
        return False
    if gate_text in {"result_ready", "explicit_hold"}:
        return True
    return "open" in gate_text or "ready" in gate_text


def build_payload(
    cruzain_render: dict[str, Any] | None,
    plpro_render: dict[str, Any] | None,
    alk2_render: dict[str, Any] | None,
    cruzain_launch: dict[str, Any] | None,
    plpro_launch: dict[str, Any] | None,
    alk2_launch: dict[str, Any] | None,
    cruzain_run_record: dict[str, Any] | None,
    plpro_run_record: dict[str, Any] | None,
    alk2_run_record: dict[str, Any] | None,
    cruzain_run_status: dict[str, Any] | None,
    plpro_result_review: dict[str, Any] | None,
    alk2_result_review: dict[str, Any] | None,
    next3_queue: dict[str, Any] | None,
    priority3_final_review: dict[str, Any] | None,
) -> dict[str, Any]:
    crs = _summary(cruzain_render)
    prs = _summary(plpro_render)
    ars = _summary(alk2_render)
    cls = _summary(cruzain_launch)
    pls = _summary(plpro_launch)
    als = _summary(alk2_launch)
    crr = _summary(cruzain_run_record)
    prr = _summary(plpro_run_record)
    arr = _summary(alk2_run_record)
    crstatus = _summary(cruzain_run_status)
    plreview = _summary(plpro_result_review)
    alreview = _summary(alk2_result_review)
    qs = _summary(next3_queue)
    p3 = _summary(priority3_final_review)

    rows = [
        {
            "chain_item": "priority3_final_review",
            "artifact_path": "runs/tcruzi_pde_result_review_current.md",
            "current_signal": str(p3.get("result_review_gate_status", "")).strip() or str(p3.get("status", "")).strip() or "missing",
            "queue_effect": "must_open_before_cruzain_can_leave_blocked_on_previous_review",
        },
        {
            "chain_item": "cruzain_run_status",
            "artifact_path": "runs/cruzain_run_status_current.md",
            "current_signal": str(crstatus.get("queue_status_now", "")).strip() or "missing",
            "queue_effect": "first_active_slot_in_next3",
        },
        {
            "chain_item": "sarscov2_plpro_result_review",
            "artifact_path": "runs/sarscov2_plpro_result_review_current.md",
            "current_signal": str(plreview.get("queue_status_now", "")).strip() or "missing",
            "queue_effect": "second_slot_gate_after_cruzain_resolution",
        },
        {
            "chain_item": "alk2_result_review",
            "artifact_path": "runs/alk2_result_review_current.md",
            "current_signal": str(alreview.get("queue_status_now", "")).strip() or "missing",
            "queue_effect": "third_slot_gate_after_plpro_resolution",
        },
        {
            "chain_item": "next3_protein_run_queue",
            "artifact_path": "runs/wetlab_next3_protein_run_queue_current.md",
            "current_signal": str(qs.get("status", "")).strip() or "missing",
            "queue_effect": "serialized_queue_source_of_truth_for_next3",
        },
    ]

    cruzain_run_record_ready = bool(
        str(crr.get("artifact_kind", "")).strip() == "run_record"
        and str(crr.get("target_id", "")).strip() == "Cruzain"
    )
    plpro_run_record_ready = bool(
        str(prr.get("artifact_kind", "")).strip() == "run_record"
        and str(prr.get("target_id", "")).strip() == "SARS-CoV-2 PLpro"
    )
    alk2_run_record_ready = bool(
        str(arr.get("artifact_kind", "")).strip() == "run_record"
        and str(arr.get("target_id", "")).strip() == "ALK2"
    )

    return {
        "summary": {
            "status": "wetlab_next3_chain_stack_ready",
            "target_count": 3,
            "artifact_kind": "chain_stack",
            "priority3_final_review_ready": bool(str(p3.get("status", "")).strip() == "tcruzi_pde_result_review_ready"),
            "priority3_final_gate_open": _priority3_final_gate_open(p3),
            "cruzain_render_suite_ready": bool(str(crs.get("status", "")).strip() == "cruzain_render_suite_ready"),
            "sarscov2_plpro_render_suite_ready": bool(str(prs.get("status", "")).strip() == "sarscov2_plpro_render_suite_ready"),
            "alk2_render_suite_ready": bool(str(ars.get("status", "")).strip() == "alk2_render_suite_ready"),
            "cruzain_launch_packet_ready": bool(str(cls.get("status", "")).strip() == "cruzain_launch_packet_ready"),
            "sarscov2_plpro_launch_packet_ready": bool(str(pls.get("status", "")).strip() == "sarscov2_plpro_launch_packet_ready"),
            "alk2_launch_packet_ready": bool(str(als.get("status", "")).strip() == "alk2_launch_packet_ready"),
            "cruzain_run_record_ready": cruzain_run_record_ready,
            "sarscov2_plpro_run_record_ready": plpro_run_record_ready,
            "alk2_run_record_ready": alk2_run_record_ready,
            "cruzain_run_status_ready": bool(str(crstatus.get("status", "")).strip() == "cruzain_run_status_ready"),
            "sarscov2_plpro_result_review_ready": bool(str(plreview.get("status", "")).strip() == "sarscov2_plpro_result_review_ready"),
            "alk2_result_review_ready": bool(str(alreview.get("status", "")).strip() == "alk2_result_review_ready"),
            "next3_queue_ready": bool(str(qs.get("status", "")).strip() == "wetlab_next3_protein_run_queue_ready"),
            "cruzain_queue_status": str(crstatus.get("queue_status_now", "")).strip(),
            "sarscov2_plpro_queue_status": str(plreview.get("queue_status_now", "")).strip(),
            "alk2_queue_status": str(alreview.get("queue_status_now", "")).strip(),
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "running_target_count": int(qs.get("running_target_count", 0) or 0),
            "resolved_target_count": int(qs.get("resolved_target_count", 0) or 0),
            "next_required_step": "Once priority3 final review opens the chain, run Cruzain first, let PLpro open only after the Cruzain live result resolves, and let ALK2 open only after the PLpro live result resolves.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_priority3",
            "queue_artifact": "runs/wetlab_next3_protein_run_queue_current.md",
            "runtime_runbook_artifact": "runs/wetlab_next3_runtime_runbook_current.md",
            "execution_console_artifact": "runs/wetlab_next3_execution_console_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the next3 chain stack for Cruzain -> PLpro -> ALK2.")
    parser.add_argument("--cruzain-render-json", default=DEFAULT_CRUZAIN_RENDER_JSON)
    parser.add_argument("--plpro-render-json", default=DEFAULT_PLPRO_RENDER_JSON)
    parser.add_argument("--alk2-render-json", default=DEFAULT_ALK2_RENDER_JSON)
    parser.add_argument("--cruzain-launch-json", default=DEFAULT_CRUZAIN_LAUNCH_JSON)
    parser.add_argument("--plpro-launch-json", default=DEFAULT_PLPRO_LAUNCH_JSON)
    parser.add_argument("--alk2-launch-json", default=DEFAULT_ALK2_LAUNCH_JSON)
    parser.add_argument("--cruzain-run-record-json", default=DEFAULT_CRUZAIN_RUN_RECORD_JSON)
    parser.add_argument("--plpro-run-record-json", default=DEFAULT_PLPRO_RUN_RECORD_JSON)
    parser.add_argument("--alk2-run-record-json", default=DEFAULT_ALK2_RUN_RECORD_JSON)
    parser.add_argument("--cruzain-run-status-json", default=DEFAULT_CRUZAIN_RUN_STATUS_JSON)
    parser.add_argument("--plpro-result-review-json", default=DEFAULT_PLPRO_RESULT_REVIEW_JSON)
    parser.add_argument("--alk2-result-review-json", default=DEFAULT_ALK2_RESULT_REVIEW_JSON)
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--priority3-final-review-json", default=DEFAULT_PRIORITY3_FINAL_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.cruzain_render_json),
        maybe_load_json(args.plpro_render_json),
        maybe_load_json(args.alk2_render_json),
        maybe_load_json(args.cruzain_launch_json),
        maybe_load_json(args.plpro_launch_json),
        maybe_load_json(args.alk2_launch_json),
        maybe_load_json(args.cruzain_run_record_json),
        maybe_load_json(args.plpro_run_record_json),
        maybe_load_json(args.alk2_run_record_json),
        maybe_load_json(args.cruzain_run_status_json),
        maybe_load_json(args.plpro_result_review_json),
        maybe_load_json(args.alk2_result_review_json),
        maybe_load_json(args.queue_json),
        maybe_load_json(args.priority3_final_review_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Next3 Chain Stack", payload)


if __name__ == "__main__":
    main()
