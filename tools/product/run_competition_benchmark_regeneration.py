#!/usr/bin/env python3
"""Regenerate competition benchmark / Package C artifact chain."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def regenerate_competition_benchmark_chain(*, slot_count: int = 40, skip_replay: bool = False) -> list[str]:
    steps: list[str] = []
    if not skip_replay:
        _run(
            [
                sys.executable,
                "tools/product/build_casp17_strict_blind_historical_replay_materializer.py",
                "--slot-count",
                str(slot_count),
            ]
        )
        steps.append("strict_blind_historical_replay_materializer")
        _run(
            [
                sys.executable,
                "tools/build_casp17_sidechain_native_benchmark_packet.py",
                "--manifest-csv",
                "runs/casp17_historical_benchmark_manifest_current.csv",
            ]
        )
        steps.append("sidechain_native_benchmark_packet")
    _run([sys.executable, "tools/build_casp17_strict_blind_internal_prediction_source_gate.py"])
    steps.append("strict_blind_internal_prediction_source_gate")
    _run([sys.executable, "tools/casp17/build_casp17_historical_winner_normalized_bands.py"])
    steps.append("historical_winner_normalized_bands")
    _run([sys.executable, "tools/build_cameo_official_results_intake_gate.py"])
    steps.append("cameo_official_results_intake_gate")
    _run(
        [
            sys.executable,
            "tools/build_cameo_performance_scorecard.py",
            "--results-csv",
            "runs/cameo_official_results_operator_intake.csv",
        ]
    )
    steps.append("cameo_performance_scorecard")
    _run([sys.executable, "tools/build_cameo_validation_readiness_gate.py"])
    steps.append("cameo_validation_readiness_gate")
    _run(
        [
            sys.executable,
            "tools/build_cameo_capability_preflight.py",
            "--public-registration-requested",
            "--registration-approval-token",
            "APPROVE_CAMEO_SERVER_REGISTRATION",
            "--outbound-email-approval-token",
            "APPROVE_CAMEO_OUTBOUND_EMAIL",
        ]
    )
    steps.append("cameo_capability_preflight")
    _run([sys.executable, "tools/build_cameo_validation_operations_dossier.py"])
    steps.append("cameo_validation_operations_dossier")
    _run([sys.executable, "tools/build_cameo_public_registration_approval_gate.py"])
    steps.append("cameo_public_registration_approval_gate")
    _run([sys.executable, "tools/build_cameo_outbound_email_send_preflight.py"])
    steps.append("cameo_outbound_email_send_preflight")
    _run([sys.executable, "tools/build_competition_external_operator_track.py"])
    steps.append("competition_external_operator_track")
    _run([sys.executable, "tools/build_casp16_ligand_materialization_manifest.py"])
    steps.append("casp16_ligand_materialization_manifest")
    _run([sys.executable, "tools/build_casp16_ligand_scorecard.py"])
    steps.append("casp16_ligand_scorecard")
    _run([sys.executable, "tools/build_casp16_ligand_source_manifest.py"])
    steps.append("casp16_ligand_source_manifest")
    _run([sys.executable, "tools/build_bm5_capri_raw_data_custody_plan.py"])
    steps.append("bm5_capri_raw_data_custody_plan")
    _run([sys.executable, "tools/apply_bm5_capri_raw_data_custody_plan.py", "--mode", "preview"])
    steps.append("bm5_capri_raw_data_untrack_apply_preflight")
    _run([sys.executable, "tools/build_bm5_capri_complex_source_manifest.py"])
    steps.append("bm5_capri_complex_source_manifest")
    _run([sys.executable, "tools/build_competition_benchmark_custody_work_order.py"])
    steps.append("competition_benchmark_custody_work_order")
    _run([sys.executable, "tools/build_competition_benchmark_rollup.py"])
    steps.append("competition_benchmark_rollup")
    _run([sys.executable, "tools/build_package_b_competition_bridge.py"])
    steps.append("package_b_competition_bridge")
    _run([sys.executable, "tools/build_architecture_validation_package_report.py"])
    steps.append("architecture_validation_package_report")
    return steps


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Regenerate competition benchmark and architecture validation artifacts.")
    parser.add_argument("--slot-count", type=int, default=40)
    parser.add_argument("--skip-replay", action="store_true")
    args = parser.parse_args(argv)
    steps = regenerate_competition_benchmark_chain(slot_count=max(1, args.slot_count), skip_replay=args.skip_replay)
    print("regenerated:", ",".join(steps))


if __name__ == "__main__":
    main()
