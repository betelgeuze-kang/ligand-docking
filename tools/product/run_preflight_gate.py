#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import List

from tools.speed_profile_defaults import load_speed_profile_section, resolve_speed_profile
from tools.validate_accuracy_gate import build_parser as build_gate_parser
from tools.validate_accuracy_gate import run_accuracy_gate


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run strict preflight accuracy gate with speed-profile preset support."
        )
    )
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--noise", type=float, default=0.08)
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--warmup-steps", type=int, default=40)
    p.add_argument("--benchmark-replicas", type=int, default=4)
    p.add_argument("--speed-profile-defaults-json", type=str, default="config/speed_profile_defaults.json")
    p.add_argument("--speed-profile-defaults-section", type=str, default="preflight")
    p.add_argument(
        "--speed-mode",
        type=str,
        default="",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
    )
    p.add_argument("--speed-mode-replicas", type=int, default=-1)
    p.add_argument(
        "--speed-profile-max-replicas",
        type=int,
        default=-1,
        help="Optional max replicas cap applied to speed profile.",
    )
    p.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable per-run GPU metric sampling in speed benchmark.",
    )
    p.add_argument(
        "--disable-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force Langevin stochastic term off during preflight benchmark.",
    )
    p.add_argument(
        "--precompute-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Precompute Langevin noise in fixed-size blocks.",
    )
    p.add_argument(
        "--precompute-stochastic-noise-block-steps",
        type=int,
        default=None,
        help="Noise precompute block size (steps).",
    )
    p.add_argument("--speedup-threshold", type=float, default=12.0)
    p.add_argument("--speedup-per-target-threshold", type=float, default=10.0)
    p.add_argument("--label", type=str, default="")
    p.add_argument("--dry-run", action="store_true")
    return p


def _sanitize_label(s: str) -> str:
    out = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in s.strip())
    return out.strip("_")


def _resolve_speed_profile_args(args: argparse.Namespace) -> dict:
    section_defaults = load_speed_profile_section(
        str(getattr(args, "speed_profile_defaults_json", "")).strip(),
        str(getattr(args, "speed_profile_defaults_section", "preflight")).strip() or "preflight",
    )
    return resolve_speed_profile(
        explicit_mode=getattr(args, "speed_mode", ""),
        explicit_replicas=getattr(args, "speed_mode_replicas", -1),
        explicit_max_replicas=getattr(args, "speed_profile_max_replicas", -1),
        section_defaults=section_defaults,
        fallback={
            "speed_mode": "fast",
            "speed_mode_replicas": 32,
            "speed_profile_max_replicas": 128,
        },
    )


def _build_gate_argv(args: argparse.Namespace) -> List[str]:
    resolved_speed = _resolve_speed_profile_args(args)
    date_tag = datetime.now().strftime("%Y-%m-%d")
    label = _sanitize_label(args.label) if str(args.label).strip() else f"rep{int(args.benchmark_replicas)}_per_target10_{date_tag}"
    base = f"runs/accuracy_gate_{label}"
    argv = [
        "--targets",
        str(args.targets),
        "--samples",
        str(int(args.samples)),
        "--noise",
        str(float(args.noise)),
        "--steps",
        str(int(args.steps)),
        "--runs",
        str(int(args.runs)),
        "--warmup-steps",
        str(int(args.warmup_steps)),
        "--benchmark-replicas",
        str(int(args.benchmark_replicas)),
        "--strict-mode",
        "--enforce-speed-gate",
        "--speedup-threshold",
        str(float(args.speedup_threshold)),
        "--speed-mode",
        str(resolved_speed["speed_mode"]),
        "--speed-mode-replicas",
        str(int(resolved_speed["speed_mode_replicas"])),
        "--speed-profile-max-replicas",
        str(int(resolved_speed["speed_profile_max_replicas"])),
        "--speedup-per-target-threshold",
        str(float(args.speedup_per_target_threshold)),
        "--out-json",
        f"{base}.json",
        "--out-csv",
        f"{base}.csv",
        "--parity-prefix",
        f"{base}_parity",
        "--stage2-prefix",
        f"{base}_stage2",
        "--benchmark-csv",
        f"{base}_bench.csv",
    ]
    if args.sample_gpu_metrics is True:
        argv.extend(["--sample-gpu-metrics"])
    elif args.sample_gpu_metrics is False:
        argv.extend(["--no-sample-gpu-metrics"])

    if args.disable_stochastic_noise is True:
        argv.extend(["--disable-stochastic-noise"])
    elif args.disable_stochastic_noise is False:
        argv.extend(["--no-disable-stochastic-noise"])

    if args.precompute_stochastic_noise is True:
        argv.extend(["--precompute-stochastic-noise"])
    elif args.precompute_stochastic_noise is False:
        argv.extend(["--no-precompute-stochastic-noise"])

    if args.precompute_stochastic_noise_block_steps is not None:
        argv.extend(
            [
                "--precompute-stochastic-noise-block-steps",
                str(int(args.precompute_stochastic_noise_block_steps)),
            ]
        )
    return argv


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    gate_argv = _build_gate_argv(args)
    print("Preflight gate argv:")
    print("python3 tools/validate_accuracy_gate.py " + " ".join(gate_argv))

    if args.dry_run:
        return

    gate_parser = build_gate_parser()
    gate_args = gate_parser.parse_args(gate_argv)
    payload = run_accuracy_gate(gate_args)
    print(json.dumps(payload["summary"], indent=2))
    if not payload["summary"]["pass"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
