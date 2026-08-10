#!/usr/bin/env python3
"""Verify the frozen synthetic geometric CPU profile and replay artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from betelgeuze_engine_v2.docking.performance_sidecar import (  # noqa: E402
    AUTHORITY_FALSE,
    PROFILE_ID,
    load_cpu_performance_artifact,
    load_cpu_performance_profile,
)


DEFAULT_PROFILE_PATH = (
    _REPO_ROOT / "config/engine_v2_cpu_performance_profile.json"
)


def verify_profile_and_optional_artifact(
    *,
    profile_path: Path,
    artifact_path: Path | None = None,
) -> Mapping[str, Any]:
    """Return integrity status without ever claiming a live execution proof."""

    profile = load_cpu_performance_profile(profile_path)
    if artifact_path is None:
        return {
            "structural_integrity_verified": True,
            "execution_attested": False,
            "profile_id": PROFILE_ID,
            "profile_sha256": profile.profile_sha256,
            "artifact_structurally_replayed": False,
            "recorded_decision": None,
            "recorded_numeric_gate_passed": None,
            "live_run_capability": False,
            "local_numeric_gate_eligible": False,
            "offline_replay_only": True,
            "qualification_authority": False,
            "verification_blockers": [
                "profile_contract_only_cannot_attest_execution"
            ],
            "authority": dict(AUTHORITY_FALSE),
        }
    artifact = load_cpu_performance_artifact(artifact_path, profile=profile)
    verification_blockers = list(artifact.verification_blockers)
    offline_blocker = "offline_artifact_cannot_attest_execution"
    if offline_blocker not in verification_blockers:
        verification_blockers.append(offline_blocker)
    return {
        "structural_integrity_verified": True,
        "execution_attested": False,
        "profile_id": PROFILE_ID,
        "profile_sha256": profile.profile_sha256,
        "artifact_structurally_replayed": True,
        "recorded_decision": artifact.recorded_decision,
        "recorded_numeric_gate_passed": artifact.recorded_numeric_gate_passed,
        "live_run_capability": False,
        "local_numeric_gate_eligible": False,
        "offline_replay_only": True,
        "qualification_authority": False,
        "verification_blockers": verification_blockers,
        "authority": dict(AUTHORITY_FALSE),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--artifact", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    result = verify_profile_and_optional_artifact(
        profile_path=arguments.profile,
        artifact_path=arguments.artifact,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
