#!/usr/bin/env python3
"""Verify, replay, or execute the sealed synthetic CPU qualification v3."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from betelgeuze_engine_v2.docking.performance_qualification_v3 import (  # noqa: E402
    CPUPerformanceQualificationV3Error,
    require_cpu_performance_artifact_v3_bytes,
    run_sealed_local_performance_runner_v3,
    verify_runner_activation_contract,
    write_cpu_performance_artifact_v3,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-activation", action="store_true")
    parser.add_argument("--verify-artifact", type=Path)
    parser.add_argument("--run-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    selected = sum(
        (
            bool(arguments.verify_activation),
            arguments.verify_artifact is not None,
            arguments.run_output is not None,
        )
    )
    if selected != 1:
        raise CPUPerformanceQualificationV3Error(
            "select exactly one public v3 operation"
        )
    activation = dict(verify_runner_activation_contract())
    if arguments.verify_activation:
        output: dict[str, object] = {
            **activation,
            "execution_attested": False,
            "verification_only": True,
        }
    elif arguments.verify_artifact is not None:
        raw = arguments.verify_artifact.read_bytes()
        verified = require_cpu_performance_artifact_v3_bytes(raw)
        output = {
            "authority": activation["authority"],
            "execution_attested": False,
            "live_run_capability": verified.live_run_capability,
            "local_numeric_gate_eligible": verified.local_numeric_gate_eligible,
            "offline_replay_only": verified.offline_replay_only,
            "qualification_authority": verified.qualification_authority,
            "recorded_decision": verified.recorded_decision,
            "recorded_numeric_gate_passed": (
                verified.recorded_numeric_gate_passed
            ),
            "structural_integrity_verified": True,
            "verification_blockers": list(verified.verification_blockers),
        }
    else:
        if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
            raise CPUPerformanceQualificationV3Error(
                "GitHub Actions cannot execute the live v3 qualification"
            )
        result = run_sealed_local_performance_runner_v3()
        published = write_cpu_performance_artifact_v3(
            result, arguments.run_output
        )
        output = {
            "artifact": str(published),
            "authority": activation["authority"],
            "blockers": list(result.blockers),
            "execution_attested": False,
            "live_run_capability": result.live_run_capability,
            "recorded_decision": result.recorded_decision,
            "recorded_numeric_gate_passed": (
                result.recorded_numeric_gate_passed
            ),
        }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
