#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.wetlab import build_wetlab_wave2_runtime_event as event_mod
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "runs/wetlab_wave2_runtime_state_current.json"
DEFAULT_LOG_PATH = ROOT / "runs/wetlab_wave2_runtime_event_log.jsonl"
TARGETS = {
    "cathepsin_k": "Cathepsin K",
    "dengue_ns2b_ns3_protease": "Dengue NS2B-NS3 protease",
    "dpre1": "DprE1",
    "t_cruzi_krs1": "T. cruzi KRS1",
    "lrrk2": "LRRK2",
}
TARGET_SPECIFIC = {
    "cathepsin_k": {
        "progress_builder": "tools/build_cathepsin_k_live_progress.py",
        "result_builder": "tools/build_cathepsin_k_result_summary.py",
        "run_record_json": "runs/cathepsin_k_run_record_current.json",
        "gate_json": "runs/cathepsin_k_result_review_current.json",
    },
    "dengue_ns2b_ns3_protease": {
        "progress_builder": "tools/build_dengue_ns2b_ns3_protease_live_progress.py",
        "result_builder": "tools/build_dengue_ns2b_ns3_protease_result_summary.py",
        "run_record_json": "runs/dengue_ns2b_ns3_protease_run_record_current.json",
        "gate_json": "runs/dengue_ns2b_ns3_protease_result_review_current.json",
    },
    "dpre1": {
        "progress_builder": "tools/build_dpre1_live_progress.py",
        "result_builder": "tools/build_dpre1_result_summary.py",
        "run_record_json": "runs/dpre1_run_record_current.json",
        "gate_json": "runs/dpre1_result_review_current.json",
    },
    "t_cruzi_krs1": {
        "progress_builder": "tools/build_tcruzi_krs1_live_progress.py",
        "result_builder": "tools/build_tcruzi_krs1_result_summary.py",
        "run_record_json": "runs/tcruzi_krs1_run_record_current.json",
        "gate_json": "runs/tcruzi_krs1_result_review_current.json",
    },
    "lrrk2": {
        "progress_builder": "tools/build_lrrk2_live_progress.py",
        "result_builder": "tools/build_lrrk2_result_summary.py",
        "run_record_json": "runs/lrrk2_run_record_current.json",
        "gate_json": "runs/lrrk2_result_review_current.json",
    },
}
CATHEPSIN_K_STATIC_BUILDERS = [
    ["tools/build_cathepsin_k_render_suite.py"],
    ["tools/build_cathepsin_k_launch_packet.py"],
    ["tools/build_cathepsin_k_result_review.py"],
    ["tools/build_cathepsin_k_run_record.py"],
    ["tools/build_cathepsin_k_result_review.py"],
]
DENGUE_STATIC_BUILDERS = [
    ["tools/build_wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map.py"],
    ["tools/build_wetlab_dengue_ns2b_ns3_protease_novelty_fill_map.py"],
    ["tools/build_dengue_ns2b_ns3_protease_render_suite.py"],
    ["tools/wetlab/wetlab/build_dengue_ns2b_ns3_protease_launch_packet.py"],
    ["tools/build_dengue_ns2b_ns3_protease_result_review.py"],
    ["tools/wetlab/wetlab/build_dengue_ns2b_ns3_protease_run_record.py"],
    ["tools/build_dengue_ns2b_ns3_protease_result_review.py"],
]
DPRE1_STATIC_BUILDERS = [
    ["tools/build_wetlab_dpre1_repurposing_fill_map.py"],
    ["tools/build_wetlab_dpre1_novelty_fill_map.py"],
    ["tools/build_dpre1_render_suite.py"],
    ["tools/build_dpre1_launch_packet.py"],
    ["tools/build_dpre1_result_review.py"],
    ["tools/build_dpre1_run_record.py"],
    ["tools/build_dpre1_result_review.py"],
]
TCRUZI_KRS1_STATIC_BUILDERS = [
    ["tools/build_wetlab_tcruzi_krs1_repurposing_fill_map.py"],
    ["tools/build_wetlab_tcruzi_krs1_novelty_fill_map.py"],
    ["tools/wetlab/wetlab/build_tcruzi_krs1_render_suite.py"],
    ["tools/wetlab/wetlab/build_tcruzi_krs1_launch_packet.py"],
    ["tools/build_tcruzi_krs1_result_review.py"],
    ["tools/wetlab/wetlab/build_tcruzi_krs1_run_record.py"],
    ["tools/build_tcruzi_krs1_result_review.py"],
]
LRRK2_STATIC_BUILDERS = [
    ["tools/build_wetlab_lrrk2_repurposing_fill_map.py"],
    ["tools/build_wetlab_lrrk2_novelty_fill_map.py"],
    ["tools/build_lrrk2_render_suite.py"],
    ["tools/build_lrrk2_launch_packet.py"],
    ["tools/build_lrrk2_result_review.py"],
    ["tools/build_lrrk2_run_record.py"],
    ["tools/build_lrrk2_result_review.py"],
]


def _append_event_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _run(cmd: list[str], python_bin: str) -> None:
    subprocess.run([python_bin, *cmd], cwd=ROOT, check=True)


def _load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {target_id: "ready_to_launch" for target_id in TARGETS.values()}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(row.get("target_id", "")).strip(): str(row.get("execution_state", "ready_to_launch")).strip() or "ready_to_launch" for row in payload.get("rows", []) or [] if str(row.get("target_id", "")).strip()}


def _write_state(path: Path, states: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {"status": "wetlab_wave2_runtime_state_ready", "target_count": len(states)},
        "rows": [{"target_id": target_id, "execution_state": state} for target_id, state in states.items()],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _slug_to_target(slug: str) -> str:
    if slug == "all_wave2":
        return slug
    return TARGETS[slug]


def _queue_rows() -> dict[str, dict[str, Any]]:
    payload = load_json("runs/wetlab_wave2_protein_run_queue_current.json")
    return {str(row.get("target_id", "")).strip(): dict(row) for row in payload.get("rows", []) or [] if str(row.get("target_id", "")).strip()}


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def _rebuild(python_bin: str) -> None:
    for cmd in CATHEPSIN_K_STATIC_BUILDERS:
        _run(cmd, python_bin)
    for cmd in DENGUE_STATIC_BUILDERS:
        _run(cmd, python_bin)
    for cmd in DPRE1_STATIC_BUILDERS:
        _run(cmd, python_bin)
    for cmd in TCRUZI_KRS1_STATIC_BUILDERS:
        _run(cmd, python_bin)
    for cmd in LRRK2_STATIC_BUILDERS:
        _run(cmd, python_bin)
    _run(["tools/build_wetlab_wave2_protein_run_queue.py"], python_bin)
    _run(["tools/build_wetlab_wave2_chain_stack.py"], python_bin)
    _run(["tools/build_wetlab_wave2_runtime_runbook.py"], python_bin)
    _run(["tools/build_wetlab_wave2_execution_console.py"], python_bin)
    _run(["tools/build_wetlab_master_execution_queue.py"], python_bin)
    _run(["tools/build_wetlab_master_runtime_runbook.py"], python_bin)
    _run(["tools/build_wetlab_master_execution_console.py"], python_bin)
    _run(["tools/build_wetlab_partnering_stack.py"], python_bin)


def _apply_target_specific_event(
    *,
    target: str,
    event: str,
    python_bin: str,
    states: dict[str, str],
    queue_status: str,
    active_stage_label: str = "",
    decision_case: str = "",
    action: str = "",
    started_at: str = "",
    updated_at: str = "",
    completed_at: str = "",
    notes: str = "",
) -> dict[str, Any]:
    meta = TARGET_SPECIFIC[target]
    progress_cmd = [meta["progress_builder"]]
    result_cmd = [meta["result_builder"]]

    if event == "reset":
        progress_cmd += ["--status", "not_started"]
        result_cmd += ["--status", "not_ready"]
        states[TARGETS[target]] = "ready_to_launch"
    elif event in {"start", "heartbeat"}:
        progress_cmd += ["--status", "running"]
        result_cmd += ["--status", "not_ready"]
        states[TARGETS[target]] = "running"
        if active_stage_label:
            progress_cmd += ["--active-stage-label", active_stage_label]
        if started_at:
            progress_cmd += ["--started-at", started_at]
        if updated_at:
            progress_cmd += ["--updated-at", updated_at]
        if notes:
            progress_cmd += ["--notes", notes]
    elif event == "complete":
        progress_cmd += ["--status", "completed"]
        result_cmd += ["--status", "completed"]
        states[TARGETS[target]] = "result_ready"
        if active_stage_label:
            progress_cmd += ["--active-stage-label", active_stage_label]
        if started_at:
            progress_cmd += ["--started-at", started_at]
            result_cmd += ["--started-at", started_at]
        if updated_at:
            progress_cmd += ["--updated-at", updated_at]
            result_cmd += ["--updated-at", updated_at]
        if completed_at:
            result_cmd += ["--completed-at", completed_at]
        if decision_case:
            result_cmd += ["--decision-case", decision_case]
        if action:
            result_cmd += ["--action", action]
        if notes:
            progress_cmd += ["--notes", notes]
            result_cmd += ["--notes", notes]
    elif event == "hold":
        progress_cmd += ["--status", "explicit_hold"]
        result_cmd += ["--status", "explicit_hold"]
        states[TARGETS[target]] = "explicit_hold"
        if active_stage_label:
            progress_cmd += ["--active-stage-label", active_stage_label]
        if started_at:
            progress_cmd += ["--started-at", started_at]
            result_cmd += ["--started-at", started_at]
        if updated_at:
            progress_cmd += ["--updated-at", updated_at]
            result_cmd += ["--updated-at", updated_at]
        if completed_at:
            result_cmd += ["--completed-at", completed_at]
        if decision_case:
            result_cmd += ["--decision-case", decision_case]
        if action:
            result_cmd += ["--action", action]
        if notes:
            progress_cmd += ["--notes", notes]
            result_cmd += ["--notes", notes]
    else:
        raise ValueError(f"Unsupported event: {event}")

    _run(progress_cmd, python_bin)
    if event in {"reset", "start", "heartbeat", "complete", "hold"}:
        _run(result_cmd, python_bin)
    _rebuild(python_bin)
    run_record_s = _summary(meta["run_record_json"])
    gate_s = _summary(meta["gate_json"])
    return {
        "target_id": TARGETS[target],
        "event": event,
        "queue_status_now": str(gate_s.get("queue_status_now", run_record_s.get("queue_status_now", queue_status))).strip(),
        "gate_status": str(gate_s.get("status", "")).strip() or "wetlab_wave2_protein_run_queue_ready",
        "execution_state": str(run_record_s.get("execution_state", run_record_s.get("status", ""))).strip(),
        "gate_execution_state": str(gate_s.get("cathepsin_k_review_state", gate_s.get("result_review_gate_status", ""))).strip(),
        "progress_command": " ".join(progress_cmd),
        "result_command": " ".join(result_cmd) if event in {"reset", "start", "heartbeat", "complete", "hold"} else "",
        "active_stage_label": active_stage_label,
        "decision_case": decision_case,
        "action": action,
    }


def apply_and_log_event(*, target: str, event: str, python_bin: str, active_stage_label: str = "", decision_case: str = "", action: str = "", started_at: str = "", updated_at: str = "", completed_at: str = "", notes: str = "", state_path: Path = DEFAULT_STATE_PATH, log_path: Path = DEFAULT_LOG_PATH) -> dict[str, Any]:
    states = _load_state(state_path)
    _rebuild(python_bin)
    queue_rows = _queue_rows()
    if target == "all_wave2":
        for target_id in list(states):
            states[target_id] = "ready_to_launch"
        for target_key in TARGET_SPECIFIC:
            _apply_target_specific_event(
                target=target_key,
                event="reset",
                python_bin=python_bin,
                states=states,
                queue_status="reset",
            )
        applied_target = "all_wave2"
        queue_status_now = "reset"
        _write_state(state_path, states)
        _rebuild(python_bin)
        result = {
            "target_id": applied_target,
            "event": event,
            "queue_status_now": queue_status_now,
            "gate_status": "wetlab_wave2_protein_run_queue_ready",
            "active_stage_label": active_stage_label,
            "decision_case": decision_case,
            "action": action,
            "event_timestamp": completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds"),
        }
        _append_event_log(log_path, result)
        write_artifact(event_mod.DEFAULT_OUT_MD, "Wet-Lab Wave2 Runtime Event", event_mod.build_payload(result))
        _rebuild(python_bin)
        return result
    else:
        applied_target = _slug_to_target(target)
        queue_status = str(queue_rows.get(applied_target, {}).get("queue_status", "")).strip()
        if target in TARGET_SPECIFIC:
            if queue_status in {"blocked_on_previous_review", "blocked_on_target_content"} and event != "reset":
                raise ValueError(f"{applied_target} cannot advance while queue_status={queue_status}.")
            result = _apply_target_specific_event(
                target=target,
                event=event,
                python_bin=python_bin,
                states=states,
                queue_status=queue_status,
                active_stage_label=active_stage_label,
                decision_case=decision_case,
                action=action,
                started_at=started_at,
                updated_at=updated_at,
                completed_at=completed_at,
                notes=notes,
            )
            _write_state(state_path, states)
            result["event_timestamp"] = completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds")
            _append_event_log(log_path, result)
            write_artifact(event_mod.DEFAULT_OUT_MD, "Wet-Lab Wave2 Runtime Event", event_mod.build_payload(result))
            _rebuild(python_bin)
            return result
        if event == "reset":
            states[applied_target] = "ready_to_launch"
        else:
            if queue_status in {"blocked_on_previous_review", "blocked_on_target_content"}:
                raise ValueError(f"{applied_target} cannot advance while queue_status={queue_status}.")
            states[applied_target] = "running" if event in {"start", "heartbeat"} else "result_ready" if event == "complete" else "explicit_hold"
        queue_status_now = queue_status or states[applied_target]
    _write_state(state_path, states)
    _rebuild(python_bin)
    result = {
        "target_id": applied_target,
        "event": event,
        "queue_status_now": queue_status_now,
        "gate_status": "wetlab_wave2_protein_run_queue_ready",
        "active_stage_label": active_stage_label,
        "decision_case": decision_case,
        "action": action,
        "event_timestamp": completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds"),
    }
    _append_event_log(log_path, result)
    write_artifact(event_mod.DEFAULT_OUT_MD, "Wet-Lab Wave2 Runtime Event", event_mod.build_payload(result))
    _rebuild(python_bin)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply and log a Wave 2 runtime event.")
    parser.add_argument("--target", choices=[*sorted(TARGETS), "all_wave2"], required=True)
    parser.add_argument("--event", choices=["reset", "start", "heartbeat", "complete", "hold"], required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--active-stage-label", default="")
    parser.add_argument("--decision-case", default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--updated-at", default="")
    parser.add_argument("--completed-at", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply_and_log_event(target=args.target, event=args.event, python_bin=args.python_bin, active_stage_label=args.active_stage_label, decision_case=args.decision_case, action=args.action, started_at=args.started_at, updated_at=args.updated_at, completed_at=args.completed_at, notes=args.notes, state_path=Path(args.state_path), log_path=Path(args.log_path))


if __name__ == "__main__":
    main()
