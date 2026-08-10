#!/usr/bin/env python3
"""Verify the consumed terminal disposition of CPU performance profile v2."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from betelgeuze_engine_v2.docking.performance_sidecar import (
    AUTHORITY_FALSE,
    CPUPerformanceError,
    _read_bounded_regular_file,
    load_cpu_performance_profile,
    require_canonical_json_object_bytes,
    require_cpu_performance_artifact_bytes,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISION_PATH = (
    _REPO_ROOT / "config/engine_v2_cpu_performance_v2_terminal_decision.json"
)
DEFAULT_PROFILE_PATH = _REPO_ROOT / "config/engine_v2_cpu_performance_profile.json"
_MAX_DECISION_BYTES = 32 * 1024
_MAX_ARTIFACT_BYTES = 32 * 1024 * 1024

_PROFILE_ID = "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v2"
_PROFILE_SHA256 = "1d6d3da4dc1d3d0a2734cd2a19ee45409e105fe67c3bc6518b3df566d86b7560"
_IMPLEMENTATION_COMMIT_OID = (
    "33bb355ef2d6e7fea7f4f6b796806e12e5acb70a"
)
_ARTIFACT_SHA256 = "a4a6dd39655a2477ecece142273400d86252c72056059c7485f3b30ed09d1e93"
_ARTIFACT_RECEIPT_SHA256 = (
    "65a9ef733be8820f9db0abe0c51da284143c6f0c9ad2478ad393b2ac8fc8afa6"
)
_RUN_NONCE = "87efbcce82f8e9186cb637ace246ff4f6e7ab2f16ae7d75ca7f667f22b7849fc"
_ARTIFACT_BYTE_COUNT = 666_910
_ARTIFACT_LOCATOR = (
    ".betelgeuze/evidence/engine-v2-cpu-performance-v2/"
    "geometric-cpu-qualification-a4a6dd39655a.json"
)


class CPUPerformanceTerminalDecisionError(ValueError):
    """Raised when the frozen terminal decision is not exact."""


def _expected_document() -> dict[str, object]:
    return {
        "artifact": {
            "byte_count": _ARTIFACT_BYTE_COUNT,
            "offline_artifact_gate_eligible": False,
            "offline_replay_only": True,
            "owner_local_retention_locator": _ARTIFACT_LOCATOR,
            "receipt_sha256": _ARTIFACT_RECEIPT_SHA256,
            "sha256": _ARTIFACT_SHA256,
            "tracked_in_repository": False,
        },
        "authority": dict(AUTHORITY_FALSE),
        "disposition": {
            "numeric_gate_evaluated": False,
            "profile_closed": True,
            "profile_mutation_allowed": False,
            "qualification_consumed": True,
            "rerun_allowed": False,
            "successor_requires_new_profile_id": True,
            "terminal_decision": "BLOCKED",
        },
        "execution": {
            "attempt_count": 1,
            "blockers": ["boost_state_unavailable"],
            "fixture_result_count": 0,
            "recorded_numeric_gate_passed": None,
            "run_nonce": _RUN_NONCE,
            "status": "blocked_preflight",
            "transcript_row_count": 0,
        },
        "implementation_commit_oid": _IMPLEMENTATION_COMMIT_OID,
        "profile_id": _PROFILE_ID,
        "profile_sha256": _PROFILE_SHA256,
        "schema_id": (
            "betelgeuze.engine_v2_cpu_performance_terminal_decision/1.0.0"
        ),
    }


def _load_exact_decision(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = _read_bounded_regular_file(
            path,
            name="CPU performance v2 terminal decision",
            maximum_bytes=_MAX_DECISION_BYTES,
            require_single_link=True,
            require_stable_size=True,
        )
        document = require_canonical_json_object_bytes(
            raw,
            name="CPU performance v2 terminal decision",
            maximum_bytes=_MAX_DECISION_BYTES,
            trailing_newline_required=True,
        )
    except CPUPerformanceError as exc:
        raise CPUPerformanceTerminalDecisionError(str(exc)) from exc
    expected = _expected_document()
    if document != expected:
        raise CPUPerformanceTerminalDecisionError(
            "CPU performance v2 terminal decision changed"
        )
    return document, raw


def verify_terminal_decision(
    *,
    decision_path: Path = DEFAULT_DECISION_PATH,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    artifact_path: Path | None = None,
) -> Mapping[str, Any]:
    """Verify the frozen decision and optionally replay the retained artifact."""

    document, decision_raw = _load_exact_decision(decision_path)
    try:
        profile = load_cpu_performance_profile(profile_path)
    except CPUPerformanceError as exc:
        raise CPUPerformanceTerminalDecisionError(str(exc)) from exc
    if profile.profile_sha256 != _PROFILE_SHA256:
        raise CPUPerformanceTerminalDecisionError(
            "terminal decision is cross-wired to another profile"
        )

    artifact_replayed = False
    verification_blockers = ["owner_local_artifact_not_supplied"]
    if artifact_path is not None:
        try:
            artifact_raw = _read_bounded_regular_file(
                artifact_path,
                name="retained CPU performance v2 artifact",
                maximum_bytes=_MAX_ARTIFACT_BYTES,
                require_single_link=True,
                require_owner_only=True,
                require_stable_size=True,
            )
            if len(artifact_raw) != _ARTIFACT_BYTE_COUNT:
                raise CPUPerformanceTerminalDecisionError(
                    "retained artifact byte count changed"
                )
            if hashlib.sha256(artifact_raw).hexdigest() != _ARTIFACT_SHA256:
                raise CPUPerformanceTerminalDecisionError(
                    "retained artifact SHA-256 changed"
                )
            verified = require_cpu_performance_artifact_bytes(
                artifact_raw,
                profile=profile,
            )
        except CPUPerformanceError as exc:
            raise CPUPerformanceTerminalDecisionError(str(exc)) from exc
        artifact_document = verified.document
        expected_artifact_fields = {
            "receipt_sha256": _ARTIFACT_RECEIPT_SHA256,
            "run_nonce": _RUN_NONCE,
            "status": "blocked_preflight",
            "recorded_decision": "BLOCKED",
            "recorded_numeric_gate_passed": None,
            "blockers": ["boost_state_unavailable"],
            "transcript": [],
            "fixture_results": [],
            "offline_replay_only": True,
            "offline_artifact_gate_eligible": False,
            "live_run_capability_serialized": False,
            "qualification_authority": False,
            "authority": dict(AUTHORITY_FALSE),
        }
        for key, expected in expected_artifact_fields.items():
            if artifact_document.get(key) != expected:
                raise CPUPerformanceTerminalDecisionError(
                    f"retained artifact terminal field changed: {key}"
                )
        artifact_replayed = True
        verification_blockers = ["offline_artifact_cannot_attest_execution"]

    return {
        "artifact_structurally_replayed": artifact_replayed,
        "authority": dict(AUTHORITY_FALSE),
        "decision_record_sha256": hashlib.sha256(decision_raw).hexdigest(),
        "execution_attested": False,
        "implementation_commit_oid": document["implementation_commit_oid"],
        "profile_id": document["profile_id"],
        "profile_sha256": document["profile_sha256"],
        "qualification_consumed": True,
        "rerun_allowed": False,
        "terminal_decision": "BLOCKED",
        "terminal_record_verified": True,
        "verification_blockers": verification_blockers,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION_PATH)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--artifact", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    result = verify_terminal_decision(
        decision_path=arguments.decision,
        profile_path=arguments.profile,
        artifact_path=arguments.artifact,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
