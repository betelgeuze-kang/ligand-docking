#!/usr/bin/env python3
"""Regenerate Tier α product wiring artifacts (WS2–WS3 partial)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def regenerate_tier_alpha_product_chain(
    *,
    skip_architecture_report: bool = False,
    run_dispatch_smoke: bool = False,
    smoke_timeout_seconds: int = 1800,
) -> list[str]:
    steps: list[str] = []
    _run([sys.executable, "tools/build_api_runner_profile_promotion_readiness.py"])
    steps.append("api_runner_profile_promotion_readiness")
    if run_dispatch_smoke:
        _run(
            [
                sys.executable,
                "tools/gpcr_replay/run_tier_alpha_adrb2_dispatch_smoke.py",
                "--timeout-seconds",
                str(max(30, int(smoke_timeout_seconds))),
            ]
        )
        steps.append("tier_alpha_adrb2_dispatch_smoke")
    _run([sys.executable, "tools/product/build_api_docking_dispatch_e2e_evidence.py"])
    steps.append("api_docking_dispatch_e2e_evidence")
    _run([sys.executable, "tools/product/build_engine_refinement_tier_readiness.py"])
    steps.append("engine_refinement_tier_readiness")
    if not skip_architecture_report:
        _run([sys.executable, "tools/build_architecture_validation_package_report.py"])
        steps.append("architecture_validation_package_report")
    _run([sys.executable, "tools/product/build_restricted_unattended_execution_readiness.py"])
    steps.append("restricted_unattended_execution_readiness")
    _run([sys.executable, "tools/build_product_capability_surface_contract.py"])
    steps.append("product_capability_surface_contract")
    _run([sys.executable, "tools/build_architecture_validation_package_report.py"])
    steps.append("architecture_validation_package_report_final")
    return steps


def regenerate_product_full_implementation(*, include_package_b: bool = False, include_package_c: bool = False) -> list[str]:
    steps = regenerate_tier_alpha_product_chain()
    if include_package_b:
        _run([sys.executable, "tools/product/run_package_b_external_defense_regeneration.py"])
        steps.append("package_b_external_defense_regeneration")
    if include_package_c:
        _run([sys.executable, "tools/run_competition_benchmark_regeneration.py"])
        steps.append("competition_benchmark_regeneration")
    return steps


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Regenerate product full implementation Tier α artifacts.")
    parser.add_argument("--skip-architecture-report", action="store_true")
    parser.add_argument("--include-package-b", action="store_true")
    parser.add_argument("--include-package-c", action="store_true")
    parser.add_argument("--run-dispatch-smoke", action="store_true")
    parser.add_argument("--smoke-timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    steps = regenerate_tier_alpha_product_chain(
        skip_architecture_report=args.skip_architecture_report,
        run_dispatch_smoke=args.run_dispatch_smoke,
        smoke_timeout_seconds=args.smoke_timeout_seconds,
    )
    if args.include_package_b:
        _run([sys.executable, "tools/product/run_package_b_external_defense_regeneration.py"])
        steps.append("package_b_external_defense_regeneration")
    if args.include_package_c:
        _run([sys.executable, "tools/run_competition_benchmark_regeneration.py"])
        steps.append("competition_benchmark_regeneration")
    print("regenerated:", ",".join(steps))


if __name__ == "__main__":
    main()
