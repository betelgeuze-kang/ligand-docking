#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_PILOT_SUMMARY_JSON = "runs/residual_force_trajectory_regeneration_pilot_summary.json"
DEFAULT_OUT_JSON = "runs/residual_force_trajectory_regeneration_execution_probe_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_trajectory_regeneration_execution_probe_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_trajectory_regeneration_execution_probe_current.md"

CLAIM_BOUNDARY = (
    "Residual force trajectory regeneration execution probe only; summarizes an existing tiny trajectory-engine pilot "
    "summary and the prepared regeneration queue to determine whether the local runtime can produce NPZ bundles. It "
    "does not run docking, regenerate full trajectory queues, derive force labels, train models, create checkpoints, "
    "promote production mode, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row(check_id: str, status: str, observed: str, required: str, next_action: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "next_action": next_action,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "external_state_mutated": False,
    }


def build_residual_force_trajectory_regeneration_execution_probe(
    *,
    regeneration_queue_packet: dict[str, Any],
    pilot_summary_packet: dict[str, Any],
    regeneration_queue_path: str = DEFAULT_REGENERATION_QUEUE_JSON,
    pilot_summary_path: str = DEFAULT_PILOT_SUMMARY_JSON,
) -> dict[str, Any]:
    queue = _summary(regeneration_queue_packet)
    pilot = _summary(pilot_summary_packet)
    queue_execution_ready = queue.get("regeneration_queue_execution_ready") is True
    pilot_summary_present = bool(pilot)
    pilot_ok_rows = _int(pilot.get("ok_rows"))
    pilot_failed_rows = _int(pilot.get("failed_rows"))
    pilot_processed_rows = _int(pilot.get("processed_rows"))
    aborted_early = pilot.get("aborted_early") is True
    abort_reason = _text(pilot.get("abort_reason"))
    backend_counts = pilot.get("backend_counts") if isinstance(pilot.get("backend_counts"), dict) else {}
    gpu_unavailable = "cuda is unavailable" in abort_reason.lower() or "gpu-only mode" in abort_reason.lower()
    engine_runtime_ready = pilot_summary_present and pilot_ok_rows > 0 and not aborted_early

    rows = [
        _row(
            "regeneration_queue_execution_ready",
            "pass" if queue_execution_ready else "fail",
            f"queue_rows={queue.get('queue_rows', 0)};regeneration_queue_execution_ready={queue_execution_ready}",
            "regeneration queue has rows, native paths, and an engine command",
            "Build or repair residual_force_trajectory_regeneration_queue_current.json.",
        ),
        _row(
            "pilot_npz_bundle_smoke",
            "pass" if engine_runtime_ready else "fail",
            (
                f"pilot_summary_present={pilot_summary_present};processed_rows={pilot_processed_rows};"
                f"ok_rows={pilot_ok_rows};failed_rows={pilot_failed_rows};aborted_early={aborted_early}"
            ),
            "tiny pilot produces at least one NPZ bundle without early abort",
            "Run a tiny pilot after backend repair, then rebuild this execution probe.",
        ),
        _row(
            "gpu_backend_available",
            "pass" if pilot_summary_present and not gpu_unavailable else "fail",
            (
                f"force_backend_requested={pilot.get('force_backend_requested', '')};"
                f"require_rust_hip={pilot.get('require_rust_hip', '')};"
                f"backend_counts={json.dumps(backend_counts, sort_keys=True)};"
                f"abort_reason={abort_reason}"
            ),
            "GPU backend required by the trajectory engine is available for production-mode NPZ regeneration",
            "Provision a compatible GPU backend or run on a GPU-equipped worker, then rerun the tiny pilot.",
        ),
    ]
    blockers = [str(row["check_id"]) for row in rows if row["status"] != "pass"]
    status = (
        "residual_force_trajectory_regeneration_execution_probe_ready"
        if not blockers
        else "blocked_residual_force_trajectory_regeneration_execution_probe"
    )
    next_required_step = (
        "Run the full residual force trajectory regeneration queue, then rerun residual_force_derivation_validation."
        if not blockers
        else "Provision a compatible GPU backend or run the pilot on a GPU-equipped worker, then rerun this execution probe."
        if "gpu_backend_available" in blockers
        else "Repair the regeneration queue or pilot summary, then rerun this execution probe."
    )
    summary = {
        "packet_type": "residual_force_trajectory_regeneration_execution_probe",
        "status": status,
        "regeneration_execution_probe_ready": not blockers,
        "engine_runtime_ready": engine_runtime_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "regeneration_queue_artifact": regeneration_queue_path,
        "pilot_summary_artifact": pilot_summary_path,
        "queue_execution_ready": queue_execution_ready,
        "queue_rows": _int(queue.get("queue_rows")),
        "pilot_summary_present": pilot_summary_present,
        "pilot_processed_rows": pilot_processed_rows,
        "pilot_ok_rows": pilot_ok_rows,
        "pilot_failed_rows": pilot_failed_rows,
        "pilot_aborted_early": aborted_early,
        "pilot_abort_reason": abort_reason,
        "gpu_backend_unavailable": gpu_unavailable,
        "force_backend_requested": _text(pilot.get("force_backend_requested")),
        "require_rust_hip": pilot.get("require_rust_hip"),
        "backend_counts": backend_counts,
        "engine_command": _text(queue.get("engine_command")),
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force Trajectory Regeneration Execution Probe",
        "",
        f"- status: `{s['status']}`",
        f"- engine_runtime_ready: `{s['engine_runtime_ready']}`",
        f"- queue_rows: `{s['queue_rows']}`",
        f"- pilot_processed_rows: `{s['pilot_processed_rows']}`",
        f"- pilot_ok_rows: `{s['pilot_ok_rows']}`",
        f"- pilot_aborted_early: `{s['pilot_aborted_early']}`",
        f"- gpu_backend_unavailable: `{s['gpu_backend_unavailable']}`",
        f"- pilot_abort_reason: `{s['pilot_abort_reason']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual force trajectory regeneration execution probe.")
    parser.add_argument("--regeneration-queue-json", default=DEFAULT_REGENERATION_QUEUE_JSON)
    parser.add_argument("--pilot-summary-json", default=DEFAULT_PILOT_SUMMARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_trajectory_regeneration_execution_probe(
        regeneration_queue_packet=_read_json_if_present(args.regeneration_queue_json),
        pilot_summary_packet=_read_json_if_present(args.pilot_summary_json),
        regeneration_queue_path=args.regeneration_queue_json,
        pilot_summary_path=args.pilot_summary_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
