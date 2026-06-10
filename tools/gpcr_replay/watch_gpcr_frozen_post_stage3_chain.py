#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHAIN_JSON = "runs/gpcr_frozen_post_stage3_v11_claim_review_chain_current.json"
DEFAULT_HTVS_HANDOFF_JSON = "runs/gpcr_frozen_htvs_stage3_handoff_current.json"
DEFAULT_STAGE2_RESUME_JSON = "runs/gpcr_frozen_stage2_resume_handoff_current.json"
DEFAULT_POST_STAGE3_CHAIN_HANDOFF_JSON = "runs/gpcr_frozen_post_stage3_chain_handoff_current.json"
HTVS_RESUME_CMD = [
    sys.executable,
    "tools/run_ligand_stress_validation.py",
    "--profile-json",
    "runs/gpcr_scaleup_100k_family_balanced_rescore_candidate_current/profiles/profile_family-balanced-frozen-r1.json",
    "--ligand-sizes",
    "100000",
    "--repeats",
    "1",
    "--date-tag",
    "2026-05-03_family_balanced_frozen_r2-gpcr-core-full-family-balanced-frozen-r1",
    "--out-prefix",
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full",
    "--resume",
    "--resume-retry-failed-runs",
    "--max-attempts-per-run",
    "3",
    "--fail-fast",
    "--enforce-data-contract",
    "--data-contract-json",
    "config/ligand_data_contract_v1.json",
]
STAGE2_RESUME_CMD = [
    sys.executable,
    "tools/generate_ligand_trajectory_engine.py",
    "--queue-csv",
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_routed_queue.csv",
    "--out-root",
    "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1/stage2_trajectory_frames",
    "--frames",
    "120",
    "--write-every",
    "1",
    "--frame-output-format",
    "npz_bundle",
    "--seed",
    "7",
    "--step-size",
    "0.04",
    "--noise-scale",
    "0.15",
    "--pocket-attract-base",
    "0.16",
    "--protein-repulse",
    "0.22",
    "--bond-k",
    "0.25",
    "--repulse-cutoff-A",
    "4.5",
    "--max-pocket-radius-A",
    "12.0",
    "--native-path-col",
    "native_pdb_path",
    "--out-manifest-csv",
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_manifest.csv",
    "--out-summary-json",
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_summary.json",
    "--out-summary-md",
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_summary.md",
    "--out-progress-json",
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_progress.json",
    "--progress-every-jobs",
    "25",
    "--resume-existing",
    "--multi-start-count",
    "3",
    "--pocket-protein-max-atoms",
    "256",
    "--npz-compression",
    "store",
    "--npz-layout",
    "flat_shard",
    "--npz-shard-size",
    "512",
    "--engine-cache-max-entries",
    "16",
    "--job-batch-size",
    "0",
    "--job-batch-autotune-candidates",
    "2,4,8,16",
    "--job-batch-autotune-frames",
    "12",
    "--job-batch-floor-by-target-json",
    "config/gpcr_stage2_target_batch_floors_v1.json",
    "--writer-workers",
    "4",
    "--writer-mode",
    "process",
    "--writer-max-pending",
    "160",
    "--dt-fs",
    "0.002",
    "--friction",
    "1.0",
    "--kT",
    "0.5961",
    "--force-clip",
    "200.0",
    "--box-size-A",
    "120.0",
    "--ff-sigma",
    "3.8",
    "--ff-eps-solv",
    "25.0",
    "--force-backend",
    "auto",
    "--strategy-mode",
    "dynamic",
    "--dynamic-adress-min-affinity",
    "0.8",
    "--dynamic-adress-max-protein-residues",
    "170",
    "--dynamic-adress-min-ligand-mw",
    "250.0",
    "--dynamic-adress-fraction",
    "0.12",
    "--dynamic-adress-base-radius-A",
    "5.6",
    "--dynamic-adress-affinity-radius-scale",
    "2.7",
    "--dynamic-adress-mw-radius-scale",
    "2.2",
    "--dynamic-adress-max-all-atom-radius-A",
    "7.2",
    "--dynamic-adress-max-atom-ratio",
    "0.08",
    "--prod-mode",
    "--prod-min-frames",
    "120",
    "--prod-adaptive-frame-budget",
    "--prod-frame-budget-tiers",
    "0.90:1.00,0.75:0.82,0.60:0.66,0.00:0.52",
    "--prod-early-stop",
    "--prod-early-stop-min-frames",
    "120",
    "--prod-early-stop-window",
    "12",
    "--prod-early-stop-contact-drift",
    "0.015",
    "--prod-early-stop-min-distance-drift-A",
    "0.12",
    "--prod-early-stop-max-mean-min-distance-A",
    "5.9",
    "--prod-early-stop-by-target-json",
    "config/gpcr_stage2_target_prod_early_stop_v1.json",
    "--prod-light-artifacts",
    "--prod-light-progress-every-jobs",
    "250",
    "--dynamic-adress-cap-force-core-on-radius",
    "--require-rust-hip",
    "--no-dynamic-core-fallback-on-oom",
    "--abort-on-runtime-error",
    "--abort-on-cpu-backend",
    "--fail-on-missing-native",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _chain_done() -> bool:
    summary = _read_json(DEFAULT_CHAIN_JSON).get("summary", {})
    return str(summary.get("status") or "").startswith("post_stage3_review_packets_refreshed")


def _launch_background(cmd: list[str], *, log_path: str, handoff_json: str, handoff_type: str) -> int:
    log_file = _resolve(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
    _write_json(
        handoff_json,
        {
            "handoff_type": handoff_type,
            "pid": int(proc.pid),
            "command": cmd,
            "log_path": str(log_file),
        },
    )
    return int(proc.pid)


def _maybe_launch_htvs() -> int | None:
    handoff = _read_json(DEFAULT_HTVS_HANDOFF_JSON)
    if handoff.get("pid") and _pid_alive(int(handoff["pid"])):
        return int(handoff["pid"])
    return _launch_background(
        HTVS_RESUME_CMD,
        log_path="runs/gpcr_frozen_htvs_stage3_handoff_current.log",
        handoff_json=DEFAULT_HTVS_HANDOFF_JSON,
        handoff_type="htvs_stage3_resume",
    )


def _maybe_launch_stage2_resume() -> int | None:
    handoff = _read_json(DEFAULT_STAGE2_RESUME_JSON)
    if handoff.get("pid") and _pid_alive(int(handoff["pid"])):
        return int(handoff["pid"])
    return _launch_background(
        STAGE2_RESUME_CMD,
        log_path="runs/gpcr_frozen_stage2_resume_tail_current.log",
        handoff_json=DEFAULT_STAGE2_RESUME_JSON,
        handoff_type="stage2_tail_resume",
    )


def _maybe_launch_post_stage3_chain() -> int | None:
    if _chain_done():
        return None
    handoff = _read_json(DEFAULT_POST_STAGE3_CHAIN_HANDOFF_JSON)
    if handoff.get("pid") and _pid_alive(int(handoff["pid"])):
        return int(handoff["pid"])
    cmd = [
        sys.executable,
        "tools/build_gpcr_frozen_post_stage3_v11_claim_review_chain.py",
    ]
    if _resolve("runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_none_stage3_current.csv").exists():
        cmd.append("--skip-cache-build")
    if _resolve("runs/gpcr_cationic_weakbase_v11_frozen_none_stage3_shadow_replay_scores_current.csv").exists():
        cmd.append("--skip-v11-replay")
    return _launch_background(
        cmd,
        log_path="runs/gpcr_frozen_post_stage3_chain_current.log",
        handoff_json=DEFAULT_POST_STAGE3_CHAIN_HANDOFF_JSON,
        handoff_type="post_stage3_v11_claim_review_chain",
    )


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import os

        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll frozen GPCR monitor and hand off stage2->HTVS->post-stage3 claim review chain."
    )
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--poll-sec", type=int, default=120)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run until chain completes.")
    args = parser.parse_args()
    cycles = 0
    while True:
        cycles += 1
        subprocess.run(
            [sys.executable, "tools/build_gpcr_frozen_stage2_monitor_packet.py", "--pid", str(int(args.pid))],
            cwd=str(ROOT),
            check=True,
        )
        monitor_payload = _read_json("runs/gpcr_frozen_stage2_monitor_packet_current.json")
        summary = monitor_payload.get("summary") if isinstance(monitor_payload.get("summary"), dict) else {}
        next_action = str(summary.get("next_action") or "")
        print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)

        if next_action == "resume_stage2_trajectory_engine":
            launched = _maybe_launch_stage2_resume()
            if launched:
                print(json.dumps({"launched_stage2_resume_pid": launched}, indent=2), flush=True)
        elif next_action == "launch_htvs_stage3_resume":
            launched = _maybe_launch_htvs()
            if launched:
                print(json.dumps({"launched_htvs_resume_pid": launched}, indent=2), flush=True)
        elif next_action == "run_post_stage3_v11_claim_review_chain":
            launched = _maybe_launch_post_stage3_chain()
            if launched:
                print(json.dumps({"launched_post_stage3_chain_pid": launched}, indent=2), flush=True)
            if _chain_done():
                break
        elif _chain_done():
            break

        if int(args.max_cycles) > 0 and cycles >= int(args.max_cycles):
            break
        time.sleep(max(30, int(args.poll_sec)))


if __name__ == "__main__":
    main()
