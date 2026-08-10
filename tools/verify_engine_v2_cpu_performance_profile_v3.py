#!/usr/bin/env python3
"""Verify the non-consuming CPU performance successor profile v3."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from betelgeuze_engine_v2.docking import (  # noqa: E402
    performance_host_preflight_v3 as preflight,
)
from betelgeuze_engine_v2.docking import performance_sidecar as v2  # noqa: E402
from tools.verify_engine_v2_cpu_performance_v2_terminal_decision import (  # noqa: E402
    CPUPerformanceTerminalDecisionError,
    DEFAULT_DECISION_PATH,
    verify_terminal_decision,
)


DEFAULT_PROFILE_V3_PATH = (
    _REPO_ROOT / "config/engine_v2_cpu_performance_profile_v3.json"
)
DEFAULT_PREDECESSOR_PROFILE_PATH = (
    _REPO_ROOT / "config/engine_v2_cpu_performance_profile.json"
)
_MAX_PROFILE_BYTES = 64 * 1024
_PROFILE_V2_SHA256 = "1d6d3da4dc1d3d0a2734cd2a19ee45409e105fe67c3bc6518b3df566d86b7560"
_TERMINAL_V2_SHA256 = "047f157c8d5d3228c180aca6af392eb8cf13d828659b9a83c38c74c34cc0cf0f"
_PREFLIGHT_SOURCE_SHA256 = (
    "236496cb7342040191db51f6c801948ab1c6b859d09a85b35e3c8a9c00a38adf"
)
_PERFORMANCE_V2_SOURCE_SHA256 = (
    "04253e3897bb5746e1c1082dbf8e27922835ffb075aeb3268c18a0895662173f"
)


class CPUPerformanceProfileV3Error(ValueError):
    """Raised when the successor profile is not the exact frozen contract."""


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _canonical_value_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _load_canonical_profile(path: Path) -> tuple[Mapping[str, Any], bytes]:
    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise ValueError(f"duplicate JSON key: {key}")
            observed[key] = value
        return observed

    def reject_float(value: str) -> object:
        raise ValueError(f"JSON float is forbidden: {value}")

    try:
        raw = v2._read_bounded_regular_file(
            path,
            name="CPU performance profile v3",
            maximum_bytes=_MAX_PROFILE_BYTES,
            require_single_link=True,
            require_stable_size=True,
        )
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            raise ValueError("CPU performance profile v3 needs one trailing newline")
        document = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
        if type(document) is not dict:
            raise ValueError("CPU performance profile v3 must be an object")
    except (v2.CPUPerformanceError, UnicodeError, ValueError) as exc:
        raise CPUPerformanceProfileV3Error(str(exc)) from exc
    if raw != _canonical_bytes(document):
        raise CPUPerformanceProfileV3Error(
            "CPU performance profile v3 must use canonical indented JSON"
        )
    return document, raw


def _expected_predecessor_hashes(
    predecessor: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "authority_sha256": _canonical_value_sha256(predecessor["authority"]),
        "fixtures_sha256": _canonical_value_sha256(predecessor["fixtures"]),
        "gates_sha256": _canonical_value_sha256(predecessor["gates"]),
        "kernel_sha256": _canonical_value_sha256(predecessor["kernel"]),
        "parity_sha256": _canonical_value_sha256(predecessor["parity"]),
        "performance_source_sha256": _PERFORMANCE_V2_SOURCE_SHA256,
        "restrictions_sha256": _canonical_value_sha256(
            predecessor["restrictions"]
        ),
        "runtime_sha256": _canonical_value_sha256(predecessor["runtime"]),
        "sampling_sha256": _canonical_value_sha256(predecessor["sampling"]),
    }


def _expected_document(predecessor: Mapping[str, Any]) -> dict[str, object]:
    return {
        "authority": dict(v2.AUTHORITY_FALSE),
        "change_control": {
            "change_reason": (
                "replace_regular_file_size_bound_with_actual_byte_bound_for_exact_"
                "sysfs_boost_path"
            ),
            "numeric_contract_changed": False,
            "permitted_changes": [
                "profile_identity",
                "profile_schema_identity",
                "boost_state_reader_contract",
            ],
            "predecessor_blocker": "boost_state_unavailable",
            "predecessor_profile_id": v2.PROFILE_ID,
            "predecessor_profile_sha256": _PROFILE_V2_SHA256,
            "predecessor_terminal_decision": "BLOCKED",
            "predecessor_terminal_decision_sha256": _TERMINAL_V2_SHA256,
        },
        "host_preflight": {
            "boost_disabled_required": True,
            "boost_state_reader": {
                "accepted_payload_sha256": [
                    hashlib.sha256(raw).hexdigest()
                    for raw in (b"0", b"0\n", b"1", b"1\n")
                ],
                "exact_path": str(preflight.CPU_BOOST_SYSFS_PATH),
                "expected_uid": 0,
                "group_or_world_writable_allowed": False,
                "maximum_actual_bytes": preflight.CPU_BOOST_MAXIMUM_ACTUAL_BYTES,
                "nofollow_required": True,
                "regular_file_required": True,
                "reported_size_is_advisory": True,
                "reader_id": preflight.CPU_BOOST_READER_ID,
                "single_link_required": True,
                "source_sha256": _PREFLIGHT_SOURCE_SHA256,
                "stable_value_read_count": 2,
            },
            "consumes_qualification": False,
            "launches_measurements": False,
            "molecular_inputs_allowed": False,
            "otherwise_unchanged_v2_host_contract_sha256": (
                _canonical_value_sha256(predecessor["host"])
            ),
            "persists_result": False,
            "reservation_allowed": False,
        },
        "predecessor_contract": _expected_predecessor_hashes(predecessor),
        "profile_id": "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v3",
        "restrictions": dict(v2.RESTRICTIONS),
        "schema_id": "betelgeuze.engine_v2_cpu_performance_profile/3.0.0",
        "status": "synthetic_geometric_kernel_development_only",
    }


def verify_cpu_performance_profile_v3(
    *,
    profile_path: Path = DEFAULT_PROFILE_V3_PATH,
    predecessor_profile_path: Path = DEFAULT_PREDECESSOR_PROFILE_PATH,
    terminal_decision_path: Path = DEFAULT_DECISION_PATH,
) -> Mapping[str, Any]:
    """Verify profile v3 without executing its preflight or a benchmark."""

    try:
        predecessor_profile = v2.load_cpu_performance_profile(
            predecessor_profile_path
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceProfileV3Error(str(exc)) from exc
    if predecessor_profile.profile_sha256 != _PROFILE_V2_SHA256:
        raise CPUPerformanceProfileV3Error("predecessor profile identity changed")
    predecessor = predecessor_profile.document

    try:
        terminal = verify_terminal_decision(
            decision_path=terminal_decision_path,
            profile_path=predecessor_profile_path,
        )
    except CPUPerformanceTerminalDecisionError as exc:
        raise CPUPerformanceProfileV3Error(str(exc)) from exc
    if (
        terminal["decision_record_sha256"] != _TERMINAL_V2_SHA256
        or terminal["terminal_decision"] != "BLOCKED"
        or terminal["qualification_consumed"] is not True
        or terminal["rerun_allowed"] is not False
    ):
        raise CPUPerformanceProfileV3Error(
            "predecessor terminal disposition is not frozen"
        )

    observed_v2_source = hashlib.sha256(
        Path(v2.__file__).resolve().read_bytes()
    ).hexdigest()
    if observed_v2_source != _PERFORMANCE_V2_SOURCE_SHA256:
        raise CPUPerformanceProfileV3Error("predecessor performance source changed")
    observed_preflight_source = hashlib.sha256(
        Path(preflight.__file__).resolve().read_bytes()
    ).hexdigest()
    if observed_preflight_source != _PREFLIGHT_SOURCE_SHA256:
        raise CPUPerformanceProfileV3Error("v3 host-preflight source changed")

    document, raw = _load_canonical_profile(profile_path)
    if document != _expected_document(predecessor):
        raise CPUPerformanceProfileV3Error("CPU performance profile v3 changed")
    profile_sha256 = hashlib.sha256(raw).hexdigest()
    return {
        "authority": dict(v2.AUTHORITY_FALSE),
        "live_run_capability": False,
        "molecular_execution": False,
        "non_consuming_preflight_only": True,
        "numeric_contract_changed": False,
        "predecessor_profile_sha256": _PROFILE_V2_SHA256,
        "predecessor_terminal_decision_sha256": _TERMINAL_V2_SHA256,
        "profile_id": document["profile_id"],
        "profile_sha256": profile_sha256,
        "profile_verified": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_V3_PATH)
    parser.add_argument(
        "--predecessor-profile",
        type=Path,
        default=DEFAULT_PREDECESSOR_PROFILE_PATH,
    )
    parser.add_argument(
        "--terminal-decision",
        type=Path,
        default=DEFAULT_DECISION_PATH,
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    result = verify_cpu_performance_profile_v3(
        profile_path=arguments.profile,
        predecessor_profile_path=arguments.predecessor_profile,
        terminal_decision_path=arguments.terminal_decision,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
