#!/usr/bin/env python3
"""Regenerate Package B external defense artifact chain (Tier β scaffold)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BUILDERS = [
    "tools/build_product_public_benchmark_contract.py",
    "tools/build_external_metric_scorecard.py",
    "tools/build_accuracy_parity_scorecard.py",
    "tools/build_residual_energy_force_label_validation.py",
    "tools/build_architecture_validation_public_benchmark_subset_manifests.py",
    "tools/build_architecture_validation_speedpack_ab_retrospective.py",
    "tools/build_commercial_gap_closure_status.py",
    "tools/build_data_science_expansion_gap_closure.py",
    "tools/build_master_gap_closure_rollup.py",
]


def regenerate_package_b_external_defense_chain() -> list[str]:
    steps: list[str] = []
    for script in BUILDERS:
        subprocess.run([sys.executable, script], cwd=ROOT, check=True)
        steps.append(Path(script).stem)
    return steps


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Regenerate Package B external defense artifacts.")
    parser.parse_args(argv)
    steps = regenerate_package_b_external_defense_chain()
    print("regenerated:", ",".join(steps))


if __name__ == "__main__":
    main()
