#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_throughput_bridge as bridge_mod
from tools import build_wetlab_hard_target_rescue_lane as lane_mod
from tools import build_wetlab_rescue_anchor_artifacts as anchor_mod
from tools import run_wetlab_broad_screen_runtime_event as runtime_mod
from tools.wetlab_broad_screen_watch_utils import primary_bridge_paths
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_RESCUE_ANCHOR_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_hard_target_rescue_runner_current.md"
DEFAULT_WATCH_LAUNCHER = "tools/launch_wetlab_broad_screen_primary_watch_loop.py"


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _remove_flag(argv: list[str], flag: str, *, takes_value: bool) -> list[str]:
    out: list[str] = []
    skip_next = False
    for idx, token in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if token == flag:
            if takes_value:
                skip_next = True
            continue
        out.append(token)
    return out


def _rewrite_command(
    command: str,
    *,
    rescue_native_csv: str,
    rescue_pocket_csv: str,
    rescue_ligand_csv: str = "",
    stage2_preset_override: str = "",
    max_pocket_radius_a: str = "",
) -> str:
    argv = shlex.split(command)
    for flag, takes_value in [
        ("--target-native-csv", True),
        ("--target-pocket-csv", True),
        ("--eval-split-csv", True),
        ("--target-ligand-csv", True),
        ("--target-ligand-roles", True),
        ("--traj-prod-stage2-preset", True),
        ("--gate-max-mean-min-distance-A", True),
        ("--strict-gate-max-mean-min-distance-A", True),
        ("--traj-prod-profile-intent", True),
        ("--traj-prod-min-frames-smoke", True),
        ("--traj-prod-min-frames-full", True),
        ("--traj-prod-early-stop-min-frames-smoke", True),
        ("--traj-prod-early-stop-min-frames-full", True),
        ("--traj-prod-early-stop-window", True),
        ("--traj-prod-early-stop-max-mean-min-distance-A", True),
        ("--traj-step-size", True),
        ("--traj-noise-scale", True),
        ("--traj-dynamic-adress-max-protein-residues", True),
        ("--traj-dynamic-adress-fraction", True),
        ("--traj-max-pocket-radius-A", True),
        ("--traj-prod-speedpack", False),
        ("--no-traj-prod-speedpack", False),
        ("--traj-prod-light-artifacts", False),
        ("--no-traj-prod-light-artifacts", False),
        ("--traj-prod-early-stop-enabled", False),
        ("--no-traj-prod-early-stop-enabled", False),
        ("--traj-prod-stage2-preset-strict", False),
        ("--no-traj-prod-stage2-preset-strict", False),
    ]:
        argv = _remove_flag(argv, flag, takes_value=takes_value)
    argv.extend(
        [
            "--target-native-csv",
            rescue_native_csv,
            "--gate-max-mean-min-distance-A",
            "2.5",
            "--strict-gate-max-mean-min-distance-A",
            "2.5",
            "--traj-prod-profile-intent",
            "hard_target_rescue_local_refine_v1",
            "--no-traj-prod-speedpack",
            "--no-traj-prod-light-artifacts",
            "--traj-prod-stage2-preset-strict",
            "--traj-prod-min-frames-smoke",
            "128",
            "--traj-prod-min-frames-full",
            "256",
            "--traj-prod-early-stop-enabled",
            "--traj-prod-early-stop-min-frames-smoke",
            "112",
            "--traj-prod-early-stop-min-frames-full",
            "224",
            "--traj-prod-early-stop-window",
            "20",
            "--traj-prod-early-stop-max-mean-min-distance-A",
            "2.8",
            "--traj-step-size",
            "0.03",
            "--traj-noise-scale",
            "0.10",
            "--traj-dynamic-adress-max-protein-residues",
            "260",
            "--traj-dynamic-adress-fraction",
            "0.20",
        ]
    )
    if rescue_pocket_csv:
        argv.extend(["--target-pocket-csv", rescue_pocket_csv])
    if rescue_ligand_csv:
        argv.extend(["--eval-split-csv", rescue_ligand_csv])
    if stage2_preset_override:
        argv.extend(["--traj-prod-stage2-preset", stage2_preset_override])
    if max_pocket_radius_a:
        argv.extend(["--traj-max-pocket-radius-A", max_pocket_radius_a])
    return shlex.join(argv)


def run(
    *,
    rescue_lane_json: str,
    rescue_anchor_json: str,
    python_bin: str,
    execution_queue_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    target_native_csv: str,
    shard_id: str,
    interval_sec: float,
    replace_heartbeat: bool,
    refresh_lane: bool = True,
    refresh_anchor: bool = True,
) -> dict[str, Any]:
    execution_queue = load_json(execution_queue_json)
    compound_universe = load_json(compound_universe_json)
    portfolio = load_json(portfolio_json)
    if refresh_lane:
        lane_payload = lane_mod.build_payload(
            execution_queue,
            load_json("runs/wetlab_primary_stage6_failure_surface_current.json"),
            load_json("runs/wetlab_primary_hold_guard_surface_current.json"),
            load_json("runs/wetlab_target_retry_policy_templates_current.json"),
        )
        write_artifact(rescue_lane_json.replace(".json", ".md"), "Wet-Lab Hard Target Rescue Lane", lane_payload)
    else:
        lane_payload = load_json(rescue_lane_json)
    lane_summary = dict(lane_payload.get("summary", {}) or {})
    target_id = _text(lane_summary.get("target_id")) or _text(lane_summary.get("focus_target_id"))
    selected_shard = _text(shard_id) or _text(lane_summary.get("shard_id")) or _text(lane_summary.get("focus_shard_id"))
    ready = bool(lane_summary.get("ready_for_manual_retry", lane_summary.get("focus_ready_for_manual_retry", False)))
    if not target_id or not selected_shard:
        raise SystemExit("hard-target rescue lane has no focus target/shard")
    if not ready:
        raise SystemExit(f"hard-target rescue lane is not ready_for_manual_retry for {target_id} {selected_shard}")

    if refresh_anchor:
        anchor_payload = anchor_mod.build_payload(lane_payload)
        write_artifact(rescue_anchor_json.replace(".json", ".md"), "Wet-Lab Rescue Anchor Artifacts", anchor_payload)
    else:
        anchor_payload = load_json(rescue_anchor_json)
    anchor_summary = dict(anchor_payload.get("summary", {}) or {})
    rescue_native_csv = _text(anchor_summary.get("rescue_target_native_csv"))
    rescue_pocket_csv = _text(anchor_summary.get("rescue_target_pocket_csv"))
    rescue_ligand_csv = _text(anchor_summary.get("rescue_target_ligand_csv"))
    attach_rescue_pocket_csv = bool(anchor_summary.get("attach_rescue_target_pocket_csv", bool(rescue_pocket_csv)))
    attach_rescue_native_csv = bool(anchor_summary.get("attach_rescue_target_native_csv", bool(rescue_native_csv)))
    attach_rescue_ligand_csv = bool(anchor_summary.get("attach_rescue_target_ligand_csv", bool(rescue_ligand_csv)))
    if not (rescue_native_csv and attach_rescue_native_csv):
        raise SystemExit("rescue anchor artifacts are incomplete")

    bridge_payload = bridge_mod.build_payload(
        execution_queue=execution_queue,
        compound_universe=compound_universe,
        portfolio=portfolio,
        target_native_csv=target_native_csv,
        target_id=target_id,
        shard_id=selected_shard,
    )
    bridge_rows = [dict(row) for row in (bridge_payload.get("rows", []) or [])]
    base_kind = ""
    stage2_preset_override = _text(lane_summary.get("stage2_preset_override"))
    for row in lane_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) == target_id and _text(candidate.get("shard_id")) == selected_shard:
            base_kind = _text(candidate.get("rescue_base_command_kind"))
            stage2_preset_override = _text(candidate.get("stage2_preset_override")) or stage2_preset_override
            break
    if not base_kind:
        base_kind = _text(lane_summary.get("rescue_base_command_kind")) or _text(lane_summary.get("focus_rescue_base_command_kind")) or "throughput_preflight"
    bridge_row = next((row for row in bridge_rows if _text(row.get("command_kind")) == base_kind and _text(row.get("command"))), {})
    if not bridge_row:
        raise SystemExit(f"no bridge command found for hard-target rescue base kind {base_kind}")
    rewritten_command = _rewrite_command(
        _text(bridge_row.get("command")),
        rescue_native_csv=rescue_native_csv,
        rescue_pocket_csv=rescue_pocket_csv if attach_rescue_pocket_csv else "",
        rescue_ligand_csv=rescue_ligand_csv if attach_rescue_ligand_csv else "",
        stage2_preset_override=stage2_preset_override,
        max_pocket_radius_a="10.0" if attach_rescue_pocket_csv else "",
    )

    paths = primary_bridge_paths(bridge_payload)
    log_path = Path(paths["preferred_log_path"])
    pid_path = Path(paths["preferred_pid_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if pid_path.exists():
        pid_path.unlink()

    stage_label = "broad_screen_primary_shard_hard_target_rescue"
    runtime_mod.run_event(
        target_id=target_id,
        shard_id=selected_shard,
        event="start",
        python_bin=python_bin,
        active_stage_label=stage_label,
        notes="launched_by_hard_target_rescue_runner_runtime_validation_only",
    )

    heartbeat_cmd = [
        python_bin,
        str(ROOT / "tools" / "launch_wetlab_broad_screen_heartbeat_loop.py"),
        "--target-id",
        target_id,
        "--shard-id",
        selected_shard,
        "--active-stage-label",
        stage_label,
        "--interval-sec",
        str(interval_sec),
    ]
    if replace_heartbeat:
        heartbeat_cmd.append("--replace")
    heartbeat_proc = subprocess.run(heartbeat_cmd, cwd=ROOT, check=True, text=True, capture_output=True)
    heartbeat_pid = int((heartbeat_proc.stdout or "0").strip() or 0)

    watcher_proc = subprocess.run(
        [python_bin, str(ROOT / DEFAULT_WATCH_LAUNCHER), "--replace"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    watcher_pid = int((watcher_proc.stdout or "0").strip() or 0)

    proc = subprocess.Popen(
        ["bash", "-lc", rewritten_command],
        cwd=ROOT,
        stdout=log_path.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")

    payload = {
        "summary": {
            "status": "wetlab_hard_target_rescue_runner_ready",
            "target_id": target_id,
            "shard_id": selected_shard,
            "selected_command_kind": "throughput_preflight_hard_target_rescue",
            "rescue_base_command_kind": base_kind,
            "compute_pid": proc.pid,
            "compute_log_path": str(log_path),
            "heartbeat_pid": heartbeat_pid,
            "watcher_pid": watcher_pid,
            "rescue_target_native_csv": rescue_native_csv,
            "rescue_target_pocket_csv": rescue_pocket_csv if attach_rescue_pocket_csv else "",
            "rescue_target_ligand_csv": rescue_ligand_csv if attach_rescue_ligand_csv else "",
            "attach_rescue_target_pocket_csv": attach_rescue_pocket_csv,
            "attach_rescue_target_native_csv": attach_rescue_native_csv,
            "attach_rescue_target_ligand_csv": attach_rescue_ligand_csv,
            "stage2_preset_override": stage2_preset_override,
            "next_required_step": f"Watch {target_id} {selected_shard} through the primary watcher and keep the default lane closed until this hard-target rescue attempt resolves.",
        },
        "structured": {
            "rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "rescue_anchor_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
            "primary_watch_state_artifact": "runs/wetlab_broad_screen_primary_watch_state_current.md",
        },
        "rows": [
            {
                "target_id": target_id,
                "shard_id": selected_shard,
                "rescue_base_command_kind": base_kind,
                "rewritten_command": rewritten_command,
                "stage2_preset_override": stage2_preset_override,
                "compute_pid": proc.pid,
                "heartbeat_pid": heartbeat_pid,
                "watcher_pid": watcher_pid,
            }
        ],
    }
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Hard Target Rescue Runner", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the focused hard-target rescue lane with rescue-only anchor artifacts and slow local refinement.")
    parser.add_argument("--rescue-lane-json", default=DEFAULT_RESCUE_LANE_JSON)
    parser.add_argument("--rescue-anchor-json", default=DEFAULT_RESCUE_ANCHOR_JSON)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--replace-heartbeat", action="store_true")
    parser.add_argument("--no-refresh-lane", action="store_true")
    parser.add_argument("--no-refresh-anchor", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        rescue_lane_json=args.rescue_lane_json,
        rescue_anchor_json=args.rescue_anchor_json,
        python_bin=args.python_bin,
        execution_queue_json=args.execution_queue_json,
        compound_universe_json=args.compound_universe_json,
        portfolio_json=args.portfolio_json,
        target_native_csv=args.target_native_csv,
        shard_id=args.shard_id,
        interval_sec=args.interval_sec,
        replace_heartbeat=args.replace_heartbeat,
        refresh_lane=not args.no_refresh_lane,
        refresh_anchor=not args.no_refresh_anchor,
    )


if __name__ == "__main__":
    main()
