#!/usr/bin/env python3
"""Verify the full-pipeline CPU profile; live execution remains fail-closed."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.verify_engine_v2_full_pipeline_cpu_performance_v1 import (  # noqa: E402
    profile,
    verify,
)


FullPipelineCPUPerformanceV1Error = profile.FullPipelineCPUPerformanceV1Error
run_live_full_pipeline_cpu_performance_v1 = (
    profile.run_live_full_pipeline_cpu_performance_v1
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-implementation", action="store_true")
    parser.add_argument("--verify-local-runtime", action="store_true")
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--run-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    selected = sum(
        (
            bool(arguments.verify_implementation),
            bool(arguments.verify_local_runtime),
            arguments.run_output is not None,
        )
    )
    if selected != 1:
        raise FullPipelineCPUPerformanceV1Error(
            "select exactly one full-pipeline CPU v1 operation"
        )
    if arguments.verify_implementation:
        if arguments.artifact_directory is not None or arguments.runtime_root is not None:
            raise FullPipelineCPUPerformanceV1Error(
                "static verification does not accept runtime paths"
            )
        result = verify()
    elif arguments.verify_local_runtime:
        if arguments.artifact_directory is None or arguments.runtime_root is None:
            raise FullPipelineCPUPerformanceV1Error(
                "local runtime verification requires both exact paths"
            )
        result = verify(
            artifact_directory=arguments.artifact_directory,
            runtime_root=arguments.runtime_root,
        )
    else:
        if arguments.artifact_directory is not None or arguments.runtime_root is not None:
            raise FullPipelineCPUPerformanceV1Error(
                "inactive execution does not accept runtime paths"
            )
        if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
            raise FullPipelineCPUPerformanceV1Error(
                "GitHub Actions cannot execute full-pipeline CPU qualification"
            )
        # The implementation PR deliberately provides no path that can reach
        # clocks, sessions, attempt state, or the requested output target.
        run_live_full_pipeline_cpu_performance_v1(arguments.run_output)
        raise AssertionError("inactive full-pipeline runner unexpectedly returned")
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
