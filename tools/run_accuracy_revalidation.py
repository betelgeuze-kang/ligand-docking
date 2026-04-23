#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import tarfile
from typing import Any, Dict, List, Optional, Sequence

from tools.speed_profile_defaults import (
    resolve_retry_ladder,
    resolve_speed_profile,
    load_speed_profile_section,
)


RETRY_LADDER_FALLBACK: List[Dict[str, Any]] = [
    {"speed_mode": "fast", "speed_mode_replicas": 32, "speed_profile_max_replicas": 128},
    {"speed_mode": "turbo", "speed_mode_replicas": 64, "speed_profile_max_replicas": 256},
    {"speed_mode": "extreme", "speed_mode_replicas": 128, "speed_profile_max_replicas": 512},
]


def _now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _safe_read_json(path: str) -> Dict[str, Any]:
    if (not str(path).strip()) or (not os.path.exists(path)):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _run_gate(
    *,
    gate_script: str,
    targets: str,
    samples: int,
    steps: int,
    runs: int,
    noise: float,
    strict_mode: bool,
    enforce_speed_gate: bool,
    speed_mode: str,
    speed_mode_replicas: int,
    speed_profile_max_replicas: int,
    speedup_threshold: float,
    speedup_per_target_threshold: float,
    sample_gpu_metrics: Optional[bool],
    disable_stochastic_noise: Optional[bool],
    precompute_stochastic_noise: Optional[bool],
    precompute_stochastic_noise_block_steps: Optional[int],
    out_json: str,
    out_csv: str,
    env: Dict[str, str],
) -> Dict[str, Any]:
    cmd: List[str] = [
        sys.executable,
        str(gate_script),
        "--targets",
        str(targets),
        "--samples",
        str(int(samples)),
        "--steps",
        str(int(steps)),
        "--runs",
        str(int(runs)),
        "--noise",
        str(float(noise)),
        "--speed-mode",
        str(speed_mode),
        "--speed-mode-replicas",
        str(int(speed_mode_replicas)),
        "--speed-profile-max-replicas",
        str(int(speed_profile_max_replicas)),
        "--speedup-threshold",
        str(float(speedup_threshold)),
        "--speedup-per-target-threshold",
        str(float(speedup_per_target_threshold)),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(out_csv),
    ]
    if bool(strict_mode):
        cmd.append("--strict-mode")
    if bool(enforce_speed_gate):
        cmd.append("--enforce-speed-gate")
    else:
        cmd.append("--no-enforce-speed-gate")
    if sample_gpu_metrics is True:
        cmd.append("--sample-gpu-metrics")
    elif sample_gpu_metrics is False:
        cmd.append("--no-sample-gpu-metrics")
    if disable_stochastic_noise is True:
        cmd.append("--disable-stochastic-noise")
    elif disable_stochastic_noise is False:
        cmd.append("--no-disable-stochastic-noise")
    if precompute_stochastic_noise is True:
        cmd.append("--precompute-stochastic-noise")
    elif precompute_stochastic_noise is False:
        cmd.append("--no-precompute-stochastic-noise")
    if precompute_stochastic_noise_block_steps is not None:
        cmd.extend(
            [
                "--precompute-stochastic-noise-block-steps",
                str(int(precompute_stochastic_noise_block_steps)),
            ]
        )
    os.makedirs(os.path.dirname(str(out_json)) or ".", exist_ok=True)
    proc = subprocess.run(cmd, env=env)
    payload = _safe_read_json(str(out_json))
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    perf = payload.get("performance_summary", {}) if isinstance(payload.get("performance_summary"), dict) else {}
    failed_metrics = summary.get("failed_metrics", []) if isinstance(summary.get("failed_metrics"), list) else []
    runtime_options = summary.get("runtime_options", {}) if isinstance(summary.get("runtime_options"), dict) else {}
    return {
        "cmd": cmd,
        "exit_code": int(proc.returncode),
        "out_json": os.path.abspath(str(out_json)),
        "out_csv": os.path.abspath(str(out_csv)),
        "summary_pass": bool(summary.get("pass", False)) if summary else None,
        "failed_metrics_count": len(failed_metrics),
        "failed_targets": summary.get("failed_targets", []) if isinstance(summary.get("failed_targets"), list) else [],
        "failed_metrics": failed_metrics,
        "speed_mode_runtime": runtime_options.get("speed_mode"),
        "avg_speedup_on_vs_off": perf.get("avg_speedup_on_vs_off"),
        "avg_throughput_on": perf.get("avg_throughput_on"),
        "avg_throughput_off": perf.get("avg_throughput_off"),
    }


def _run_gate_with_retries(
    *,
    gate_script: str,
    targets: str,
    samples: int,
    steps: int,
    runs: int,
    noise: float,
    strict_mode: bool,
    enforce_speed_gate: bool,
    speedup_threshold: float,
    speedup_per_target_threshold: float,
    sample_gpu_metrics: Optional[bool],
    disable_stochastic_noise: Optional[bool],
    precompute_stochastic_noise: Optional[bool],
    precompute_stochastic_noise_block_steps: Optional[int],
    retry_profiles: List[Dict[str, Any]],
    gate_retry_max: int,
    out_json: str,
    out_csv: str,
    env: Dict[str, str],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    retries = int(max(gate_retry_max, 1))
    if not retry_profiles:
        retry_profiles = [
            {"speed_mode": "fast", "speed_mode_replicas": 32, "speed_profile_max_replicas": 128}
        ]
    for attempt_idx in range(1, retries + 1):
        profile = dict(retry_profiles[min(attempt_idx - 1, len(retry_profiles) - 1)])
        attempt_out_json = out_json
        attempt_out_csv = out_csv
        if retries > 1:
            attempt_out_json = f"{out_json}.attempt{attempt_idx}.json"
            attempt_out_csv = f"{out_csv}.attempt{attempt_idx}.csv"
        rec = _run_gate(
            gate_script=gate_script,
            targets=targets,
            samples=samples,
            steps=steps,
            runs=runs,
            noise=noise,
            strict_mode=strict_mode,
            enforce_speed_gate=enforce_speed_gate,
            speed_mode=str(profile.get("speed_mode", "balanced")),
            speed_mode_replicas=int(profile.get("speed_mode_replicas", 0)),
            speed_profile_max_replicas=int(profile.get("speed_profile_max_replicas", 0)),
            speedup_threshold=speedup_threshold,
            speedup_per_target_threshold=speedup_per_target_threshold,
            sample_gpu_metrics=sample_gpu_metrics,
            disable_stochastic_noise=disable_stochastic_noise,
            precompute_stochastic_noise=precompute_stochastic_noise,
            precompute_stochastic_noise_block_steps=precompute_stochastic_noise_block_steps,
            out_json=attempt_out_json,
            out_csv=attempt_out_csv,
            env=env,
        )
        rec["attempt"] = int(attempt_idx)
        rec["profile"] = profile
        attempts.append(rec)
        attempt_pass = bool(rec.get("summary_pass", False)) and (int(rec.get("exit_code", 1)) == 0)
        if attempt_pass:
            # Normalize final artifacts to canonical stage outputs.
            if str(attempt_out_json) != str(out_json):
                try:
                    os.replace(str(attempt_out_json), str(out_json))
                except Exception:
                    pass
            if str(attempt_out_csv) != str(out_csv):
                try:
                    os.replace(str(attempt_out_csv), str(out_csv))
                except Exception:
                    pass
            break

    final = dict(attempts[-1])
    last_out_json = str(final.get("out_json", "")).strip()
    last_out_csv = str(final.get("out_csv", "")).strip()
    if (not os.path.exists(str(out_json))) and last_out_json and os.path.exists(last_out_json):
        try:
            os.replace(last_out_json, str(out_json))
        except Exception:
            pass
    if (not os.path.exists(str(out_csv))) and last_out_csv and os.path.exists(last_out_csv):
        try:
            os.replace(last_out_csv, str(out_csv))
        except Exception:
            pass
    final["attempt_count"] = int(len(attempts))
    final["attempts"] = attempts
    final["out_json"] = os.path.abspath(str(out_json))
    final["out_csv"] = os.path.abspath(str(out_csv))
    return final


def build_parser() -> argparse.ArgumentParser:
    today = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Run accuracy gate revalidation in smoke->full order.")
    p.add_argument("--gate-script", type=str, default="tools/validate_accuracy_gate.py")
    p.add_argument("--run-scope", type=str, choices=["smoke_only", "smoke_then_full"], default="smoke_then_full")
    p.add_argument("--out-prefix", type=str, default=f"runs/accuracy_revalidation_{today}")
    p.add_argument("--strict-mode", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--enforce-speed-gate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--gate-retry-max", type=int, default=3)
    p.add_argument(
        "--retry-speed-ladder",
        type=str,
        default="",
        help="Optional override ladder: mode:replicas:max,mode:replicas:max",
    )
    p.add_argument(
        "--speed-profile-defaults-json",
        type=str,
        default="config/speed_profile_defaults.json",
    )
    p.add_argument("--speed-profile-defaults-section", type=str, default="revalidation")
    p.add_argument(
        "--speed-mode",
        type=str,
        default="",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
    )
    p.add_argument("--speed-mode-replicas", type=int, default=-1)
    p.add_argument("--speed-profile-max-replicas", type=int, default=-1)
    p.add_argument("--speedup-threshold", type=float, default=12.0)
    p.add_argument("--speedup-per-target-threshold", type=float, default=0.0)
    p.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable per-run GPU metric sampling in stage2 benchmark.",
    )
    p.add_argument(
        "--disable-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force Langevin stochastic term off during stage2 benchmark.",
    )
    p.add_argument(
        "--precompute-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Precompute Langevin noise in fixed-size blocks during stage2 benchmark.",
    )
    p.add_argument(
        "--precompute-stochastic-noise-block-steps",
        type=int,
        default=None,
        help="Noise precompute block size (steps).",
    )

    p.add_argument("--smoke-targets", type=str, default="Chignolin")
    p.add_argument("--smoke-samples", type=int, default=1)
    p.add_argument("--smoke-steps", type=int, default=30)
    p.add_argument("--smoke-runs", type=int, default=1)

    p.add_argument("--full-targets", type=str, default="all")
    p.add_argument("--full-samples", type=int, default=8)
    p.add_argument("--full-steps", type=int, default=60)
    p.add_argument("--full-runs", type=int, default=1)
    p.add_argument("--noise", type=float, default=0.08)

    p.add_argument("--set-rust-hip-env", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--summary-json", type=str, default="")
    p.add_argument("--summary-md", type=str, default="")
    p.add_argument("--attempts-csv", type=str, default="")
    p.add_argument("--archive-attempt-artifacts", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--attempt-archive-dir", type=str, default="runs/_archive_attempts")
    p.add_argument("--attempt-archive-compress", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--remove-attempt-artifacts", action=argparse.BooleanOptionalAction, default=True)
    return p


def _build_attempt_rows(stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for stage in stages:
        stage_name = str(stage.get("name", ""))
        attempts = stage.get("attempts", [])
        if not isinstance(attempts, list) or (not attempts):
            attempts = [stage]
        for attempt in attempts:
            profile = attempt.get("profile", {}) if isinstance(attempt.get("profile"), dict) else {}
            failed_metrics = (
                attempt.get("failed_metrics", [])
                if isinstance(attempt.get("failed_metrics"), list)
                else []
            )
            rows.append(
                {
                    "stage": stage_name,
                    "attempt": int(attempt.get("attempt", 1) or 1),
                    "exit_code": int(attempt.get("exit_code", 1) or 1),
                    "summary_pass": bool(attempt.get("summary_pass", False)),
                    "failed_metrics_count": int(attempt.get("failed_metrics_count", len(failed_metrics)) or 0),
                    "speed_mode_profile": str(profile.get("speed_mode", "")),
                    "speed_mode_runtime": str(attempt.get("speed_mode_runtime", "") or ""),
                    "speed_mode_replicas": int(profile.get("speed_mode_replicas", 0) or 0),
                    "speed_profile_max_replicas": int(
                        profile.get("speed_profile_max_replicas", 0) or 0
                    ),
                    "avg_speedup_on_vs_off": attempt.get("avg_speedup_on_vs_off"),
                    "avg_throughput_on": attempt.get("avg_throughput_on"),
                    "avg_throughput_off": attempt.get("avg_throughput_off"),
                    "failed_metrics_preview": json.dumps(failed_metrics[:3], ensure_ascii=False),
                    "out_json": str(attempt.get("out_json", "")),
                    "out_csv": str(attempt.get("out_csv", "")),
                }
            )
    return rows


def _write_attempt_rows_csv(path: str, rows: List[Dict[str, Any]]) -> str:
    out_path = str(path).strip()
    if not out_path:
        return out_path
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fields = [
        "stage",
        "attempt",
        "exit_code",
        "summary_pass",
        "failed_metrics_count",
        "speed_mode_profile",
        "speed_mode_runtime",
        "speed_mode_replicas",
        "speed_profile_max_replicas",
        "avg_speedup_on_vs_off",
        "avg_throughput_on",
        "avg_throughput_off",
        "failed_metrics_preview",
        "out_json",
        "out_csv",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path


def _collect_attempt_artifact_paths(out_prefix: str) -> List[str]:
    base = str(out_prefix).strip()
    if not base:
        return []
    patterns = [
        f"{base}_smoke.json.attempt*.json",
        f"{base}_smoke.csv.attempt*.csv",
        f"{base}_full.json.attempt*.json",
        f"{base}_full.csv.attempt*.csv",
    ]
    seen = set()
    files: List[str] = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            ap = os.path.abspath(str(path))
            if (ap in seen) or (not os.path.isfile(ap)):
                continue
            seen.add(ap)
            files.append(ap)
    files.sort()
    return files


def _archive_attempt_artifacts(
    *,
    out_prefix: str,
    archive_dir: str,
    compress: bool,
    remove_original: bool,
) -> Dict[str, Any]:
    attempt_files = _collect_attempt_artifact_paths(out_prefix)
    if not attempt_files:
        return {
            "requested": True,
            "found_files": 0,
            "archived_files": 0,
            "archive_path": "",
            "removed_files": 0,
        }

    root = str(archive_dir).strip() or "runs/_archive_attempts"
    os.makedirs(root, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix_name = os.path.basename(str(out_prefix).rstrip("/")) or "accuracy_revalidation"
    ext = ".tar.gz" if bool(compress) else ".tar"
    archive_path = os.path.abspath(os.path.join(root, f"{prefix_name}_attempts_{stamp}{ext}"))
    mode = "w:gz" if bool(compress) else "w"

    archived: List[str] = []
    with tarfile.open(archive_path, mode) as tar:
        for src in attempt_files:
            if not os.path.isfile(src):
                continue
            tar.add(src, arcname=os.path.basename(src))
            archived.append(src)

    removed = 0
    if bool(remove_original):
        for src in archived:
            try:
                os.remove(src)
                removed += 1
            except Exception:
                continue

    return {
        "requested": True,
        "found_files": int(len(attempt_files)),
        "archived_files": int(len(archived)),
        "archive_path": archive_path,
        "removed_files": int(removed),
    }


def _render_md(summary: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Accuracy Revalidation")
    lines.append("")
    lines.append(f"- generated_at_local: {summary.get('generated_at_local', '')}")
    lines.append(f"- pass: {summary.get('pass', False)}")
    lines.append(f"- run_scope: {summary.get('run_scope', '')}")
    lines.append(f"- attempts_csv: {summary.get('attempts_csv', '')}")
    lines.append(f"- attempt_artifact_archive: {summary.get('attempt_artifact_archive', {})}")
    lines.append("")
    for row in summary.get("stages", []):
        lines.append(f"## {row.get('name', '')}")
        lines.append(f"- attempt_count: {row.get('attempt_count', 1)}")
        if isinstance(row.get("profile"), dict):
            lines.append(f"- profile: {row.get('profile')}")
        lines.append(f"- exit_code: {row.get('exit_code', None)}")
        lines.append(f"- summary_pass: {row.get('summary_pass', None)}")
        lines.append(f"- failed_metrics_count: {row.get('failed_metrics_count', None)}")
        lines.append(f"- failed_targets: {row.get('failed_targets', [])}")
        lines.append(f"- out_json: {row.get('out_json', '')}")
        lines.append(f"- out_csv: {row.get('out_csv', '')}")
        attempts = row.get("attempts", [])
        if isinstance(attempts, list) and attempts:
            lines.append("- attempts:")
            for attempt in attempts:
                lines.append(
                    f"  - [{attempt.get('attempt')}] rc={attempt.get('exit_code')} pass={attempt.get('summary_pass')} profile={attempt.get('profile')}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    summary_json = str(args.summary_json).strip() or f"{args.out_prefix}_summary.json"
    summary_md = str(args.summary_md).strip() or f"{args.out_prefix}_summary.md"
    attempts_csv = str(args.attempts_csv).strip() or f"{args.out_prefix}_attempts.csv"

    section_defaults = load_speed_profile_section(
        str(getattr(args, "speed_profile_defaults_json", "")).strip(),
        str(getattr(args, "speed_profile_defaults_section", "revalidation")).strip() or "revalidation",
    )
    base_profile = resolve_speed_profile(
        explicit_mode=args.speed_mode,
        explicit_replicas=args.speed_mode_replicas,
        explicit_max_replicas=args.speed_profile_max_replicas,
        section_defaults=section_defaults,
        fallback={
            "speed_mode": "fast",
            "speed_mode_replicas": 32,
            "speed_profile_max_replicas": 128,
        },
    )
    ladder = resolve_retry_ladder(
        explicit_ladder=str(getattr(args, "retry_speed_ladder", "")).strip(),
        section_defaults=section_defaults,
        fallback_ladder=RETRY_LADDER_FALLBACK,
    )
    retry_profiles: List[Dict[str, Any]] = [dict(base_profile)]
    seen = {
        (
            str(base_profile.get("speed_mode", "")),
            int(base_profile.get("speed_mode_replicas", 0)),
            int(base_profile.get("speed_profile_max_replicas", 0)),
        )
    }
    for item in ladder:
        key = (
            str(item.get("speed_mode", "")),
            int(item.get("speed_mode_replicas", 0)),
            int(item.get("speed_profile_max_replicas", 0)),
        )
        if key in seen:
            continue
        seen.add(key)
        retry_profiles.append(dict(item))

    env = os.environ.copy()
    if bool(args.set_rust_hip_env):
        env.setdefault("FORCE_RUST_HIP", "1")
        env.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")

    smoke = _run_gate_with_retries(
        gate_script=str(args.gate_script),
        targets=str(args.smoke_targets),
        samples=int(args.smoke_samples),
        steps=int(args.smoke_steps),
        runs=int(args.smoke_runs),
        noise=float(args.noise),
        strict_mode=bool(args.strict_mode),
        enforce_speed_gate=bool(args.enforce_speed_gate),
        speedup_threshold=float(args.speedup_threshold),
        speedup_per_target_threshold=float(args.speedup_per_target_threshold),
        sample_gpu_metrics=args.sample_gpu_metrics,
        disable_stochastic_noise=args.disable_stochastic_noise,
        precompute_stochastic_noise=args.precompute_stochastic_noise,
        precompute_stochastic_noise_block_steps=args.precompute_stochastic_noise_block_steps,
        retry_profiles=retry_profiles,
        gate_retry_max=int(args.gate_retry_max),
        out_json=f"{args.out_prefix}_smoke.json",
        out_csv=f"{args.out_prefix}_smoke.csv",
        env=env,
    )

    stages: List[Dict[str, Any]] = [{"name": "smoke", **smoke}]
    passed = (int(smoke.get("exit_code", 1)) == 0) and bool(smoke.get("summary_pass", False))

    if passed and str(args.run_scope).strip() == "smoke_then_full":
        full = _run_gate_with_retries(
            gate_script=str(args.gate_script),
            targets=str(args.full_targets),
            samples=int(args.full_samples),
            steps=int(args.full_steps),
            runs=int(args.full_runs),
            noise=float(args.noise),
            strict_mode=bool(args.strict_mode),
            enforce_speed_gate=bool(args.enforce_speed_gate),
            speedup_threshold=float(args.speedup_threshold),
            speedup_per_target_threshold=float(args.speedup_per_target_threshold),
            sample_gpu_metrics=args.sample_gpu_metrics,
            disable_stochastic_noise=args.disable_stochastic_noise,
            precompute_stochastic_noise=args.precompute_stochastic_noise,
            precompute_stochastic_noise_block_steps=args.precompute_stochastic_noise_block_steps,
            retry_profiles=retry_profiles,
            gate_retry_max=int(args.gate_retry_max),
            out_json=f"{args.out_prefix}_full.json",
            out_csv=f"{args.out_prefix}_full.csv",
            env=env,
        )
        stages.append({"name": "full", **full})
        passed = (int(full.get("exit_code", 1)) == 0) and bool(full.get("summary_pass", False))

    summary = {
        "generated_at_local": _now_local(),
        "pass": bool(passed),
        "run_scope": str(args.run_scope),
        "gate_retry_max": int(args.gate_retry_max),
        "resolved_speed_profile": base_profile,
        "retry_profiles": retry_profiles,
        "attempts_csv": attempts_csv,
        "stages": stages,
    }
    attempt_rows = _build_attempt_rows(stages)
    attempts_csv = _write_attempt_rows_csv(attempts_csv, attempt_rows)
    summary["attempts_csv"] = attempts_csv
    if bool(args.archive_attempt_artifacts):
        summary["attempt_artifact_archive"] = _archive_attempt_artifacts(
            out_prefix=str(args.out_prefix),
            archive_dir=str(args.attempt_archive_dir),
            compress=bool(args.attempt_archive_compress),
            remove_original=bool(args.remove_attempt_artifacts),
        )
    else:
        summary["attempt_artifact_archive"] = {
            "requested": False,
            "found_files": 0,
            "archived_files": 0,
            "archive_path": "",
            "removed_files": 0,
        }
    os.makedirs(os.path.dirname(summary_json) or ".", exist_ok=True)
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write(_render_md(summary))
    print(
        json.dumps(
            {
                "summary_json": summary_json,
                "summary_md": summary_md,
                "attempts_csv": attempts_csv,
                "attempt_artifact_archive": summary.get("attempt_artifact_archive", {}),
                "pass": bool(passed),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
