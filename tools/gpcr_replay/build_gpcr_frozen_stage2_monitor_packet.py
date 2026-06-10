#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PID = 204429
DEFAULT_MOUNT_ROOT = "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs"
DEFAULT_FROZEN_RUN_ID = (
    "external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1"
)
DEFAULT_STAGE2_PROGRESS_JSON = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage2_traj_progress.json"
)
DEFAULT_STAGE2_SUMMARY_JSON = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage2_traj_summary.json"
)
DEFAULT_STAGE3_SCORES_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_BACKGROUND_JSON = "runs/gpcr_frozen_stage2_regeneration_background_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_stage2_monitor_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_stage2_monitor_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _process_running(pattern: str) -> bool:
    proc = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    return proc.returncode == 0


def _stage2_engine_running() -> bool:
    return _process_running(
        "generate_ligand_trajectory_engine.py.*external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_routed_queue"
    )


def _htvs_pipeline_running() -> bool:
    return _process_running(
        "run_ligand_stress_validation.py.*external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full"
    ) or _process_running(
        "run_ligand_htvs_pipeline.py.*external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1"
    )


def _count_npz(mount_root: Path, frozen_run_id: str) -> int:
    stage2_dir = mount_root / frozen_run_id / "stage2_trajectory_frames"
    if not stage2_dir.is_dir():
        return 0
    return sum(1 for _ in stage2_dir.rglob("*.npz"))


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_packet(
    *,
    pid: int = DEFAULT_PID,
    mount_root: str | Path = DEFAULT_MOUNT_ROOT,
    frozen_run_id: str = DEFAULT_FROZEN_RUN_ID,
    stage2_progress_json: str | Path = DEFAULT_STAGE2_PROGRESS_JSON,
    stage2_summary_json: str | Path = DEFAULT_STAGE2_SUMMARY_JSON,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    progress = _read_json(stage2_progress_json)
    summary = _read_json(stage2_summary_json)
    stage3_path = _resolve(stage3_scores_csv)
    mount_npz_count = _count_npz(Path(mount_root), frozen_run_id)
    progress_status = str(progress.get("status") or "").strip()
    queue_total = _as_int(progress.get("queue_rows_total"), _as_int(summary.get("queue_rows"), 40000))
    processed_rows = _as_int(progress.get("processed_rows"), _as_int(summary.get("processed_rows"), 0))
    ok_rows = _as_int(progress.get("ok_rows"), _as_int(summary.get("ok_rows"), 0))
    failed_rows = _as_int(progress.get("failed_rows"), _as_int(summary.get("failed_rows"), 0))
    progress_ratio = float(progress.get("progress_ratio") or (processed_rows / queue_total if queue_total else 0.0))
    stage3_present = stage3_path.exists() and stage3_path.stat().st_size > 0
    pid_running = _pid_alive(int(pid))
    stage2_engine_running = _stage2_engine_running()
    htvs_running = _htvs_pipeline_running()
    stage2_done = progress_status == "done" or (
        not stage2_engine_running
        and processed_rows >= queue_total
        and failed_rows == 0
        and ok_rows >= queue_total
    )

    if stage3_present:
        next_action = "run_post_stage3_v11_claim_review_chain"
        status = "stage3_ready_claim_locked"
    elif stage2_done and not htvs_running:
        next_action = "launch_htvs_stage3_resume"
        status = "stage2_complete_launch_htvs_resume"
    elif stage2_done and htvs_running:
        next_action = "wait_stage3_scores_csv"
        status = "stage2_complete_htvs_running"
    elif progress_status in {"running", "done"} and stage2_engine_running:
        next_action = "wait_stage2_npz_accumulation"
        status = "stage2_running"
    elif progress_status == "running" or pid_running or stage2_engine_running:
        next_action = "wait_stage2_npz_accumulation"
        status = "stage2_running"
    elif summary.get("aborted_early") or progress_status == "aborted":
        next_action = "investigate_stage2_failure"
        status = "stage2_failed"
    elif processed_rows < queue_total and not stage2_engine_running:
        next_action = "resume_stage2_trajectory_engine"
        status = "stage2_stalled_need_resume"
    else:
        next_action = "wait_pipeline"
        status = "stage2_status_unknown"

    packet_summary = {
        "packet_type": "gpcr_frozen_stage2_monitor_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "next_action": next_action,
        "pid": int(pid),
        "pid_running": pid_running or stage2_engine_running or htvs_running,
        "stage2_engine_running": stage2_engine_running,
        "htvs_pipeline_running": htvs_running,
        "stage2_done": stage2_done,
        "mount_root": str(_resolve(mount_root)),
        "frozen_run_id": frozen_run_id,
        "mount_stage2_npz_count": mount_npz_count,
        "stage2_progress_status": progress_status,
        "stage2_queue_rows_total": queue_total,
        "stage2_processed_rows": processed_rows,
        "stage2_ok_rows": ok_rows,
        "stage2_failed_rows": failed_rows,
        "stage2_progress_ratio": round(progress_ratio, 6),
        "stage2_current_target": progress.get("current_target"),
        "stage2_current_ligand_id": progress.get("current_ligand_id"),
        "stage2_last_error": progress.get("last_error") or summary.get("abort_reason"),
        "stage3_scores_csv_present": stage3_present,
        "stage3_scores_csv": str(stage3_path),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "next_required_step": (
            "Run post-stage3 v11 frozen cache rebuild, shadow replay, and guarded 100k readiness refresh."
            if stage3_present
            else (
                "Launch HTVS resume to produce stage3_scores.csv after stage2 completion."
                if next_action == "launch_htvs_stage3_resume"
                else (
                    "Wait for HTVS stage3/scoring while stage2 remains complete on mount."
                    if next_action == "wait_stage3_scores_csv"
                    else (
                        "Resume stage2 trajectory generation for remaining queue rows."
                        if next_action == "resume_stage2_trajectory_engine"
                        else (
                            "Wait for stage2 NPZ accumulation and pipeline stage3_scores.csv before any claim review."
                            if next_action != "investigate_stage2_failure"
                            else "Inspect stage2 abort_reason and relaunch after fix."
                        )
                    )
                )
            )
        ),
    }
    return {"summary": packet_summary, "stage2_progress": progress, "stage2_summary": summary}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Stage2 Monitor Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- next_action: `{summary['next_action']}`",
        f"- pid_running: `{summary['pid_running']}`",
        f"- mount_stage2_npz_count: `{summary['mount_stage2_npz_count']}`",
        f"- stage2_processed_rows: `{summary['stage2_processed_rows']}` / `{summary['stage2_queue_rows_total']}`",
        f"- stage2_progress_ratio: `{summary['stage2_progress_ratio']}`",
        f"- stage3_scores_csv_present: `{summary['stage3_scores_csv_present']}`",
        f"- claim_promotion_allowed: `false`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor frozen GPCR stage2 NPZ accumulation and stage3 readiness.")
    parser.add_argument("--pid", type=int, default=DEFAULT_PID)
    parser.add_argument("--mount-root", default=DEFAULT_MOUNT_ROOT)
    parser.add_argument("--frozen-run-id", default=DEFAULT_FROZEN_RUN_ID)
    parser.add_argument("--stage2-progress-json", default=DEFAULT_STAGE2_PROGRESS_JSON)
    parser.add_argument("--stage2-summary-json", default=DEFAULT_STAGE2_SUMMARY_JSON)
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--background-json", default=DEFAULT_BACKGROUND_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        pid=int(args.pid),
        mount_root=args.mount_root,
        frozen_run_id=args.frozen_run_id,
        stage2_progress_json=args.stage2_progress_json,
        stage2_summary_json=args.stage2_summary_json,
        stage3_scores_csv=args.stage3_scores_csv,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    background = _read_json(args.background_json)
    background.update(
        {
            "monitor_status": payload["summary"]["status"],
            "monitor_next_action": payload["summary"]["next_action"],
            "mount_stage2_npz_count": payload["summary"]["mount_stage2_npz_count"],
            "stage2_progress_ratio": payload["summary"]["stage2_progress_ratio"],
            "stage3_scores_csv_present": payload["summary"]["stage3_scores_csv_present"],
            "monitor_json": str(_resolve(args.out_json)),
            "generated_at_local": payload["summary"]["generated_at_local"],
        }
    )
    _write_json(args.background_json, background)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
