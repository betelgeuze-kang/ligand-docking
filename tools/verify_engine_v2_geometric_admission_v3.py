#!/usr/bin/env python3
"""Verify the frozen non-authoritative geometric-admission v3 policy."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import sys
import types
from typing import Final


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
for _package_name, _package_path in (
    ("betelgeuze_engine_v2", _REPO_ROOT / "betelgeuze_engine_v2"),
    (
        "betelgeuze_engine_v2.docking",
        _REPO_ROOT / "betelgeuze_engine_v2" / "docking",
    ),
):
    if _package_name not in sys.modules:
        _package = types.ModuleType(_package_name)
        _package.__package__ = _package_name
        _package.__path__ = [str(_package_path)]  # type: ignore[attr-defined]
        sys.modules[_package_name] = _package

from betelgeuze_engine_v2.docking.geometric_admission_v3 import (  # noqa: E402
    GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
    GeometricAdmissionV3,
    frozen_geometric_admission_v3_policy,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_geometric_admission_v3.json"
)
_FORBIDDEN_PARAMETERS: Final = {
    "authority",
    "benchmark_outcome",
    "candidate_coordinates",
    "fresh",
    "native_pose",
    "rank",
    "reservation",
    "rmsd",
    "score",
    "validity",
}


class GeometricAdmissionV3PolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission v3 policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission v3 policy must be one JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission v3 policy is not canonical JSON"
        )
    if document != frozen_geometric_admission_v3_policy():
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission v3 policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != GEOMETRIC_ADMISSION_V3_POLICY_SHA256:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission v3 policy SHA-256 changed"
        )
    if document.get("candidate_denominator") != 64:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission denominator is not fixed64"
        )
    hard_rejection = document.get("hard_rejection")
    if type(hard_rejection) is not dict or hard_rejection != {
        "metric": "minimum_vdw_ratio",
        "operator": "strictly_less_than",
        "threshold_binary64_hex": (0.55).hex(),
        "rejection_code": "severe_receptor_penetration_min_vdw_ratio",
    }:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission hard rejection rule changed"
        )
    failure_semantics = document.get("failure_semantics")
    if type(failure_semantics) is not dict or any(
        failure_semantics.get(key) is not False
        for key in (
            "failure_coordinate_allowed",
            "failure_metrics_allowed",
            "failure_rank_eligible",
            "slot_reallocation_allowed",
        )
    ):
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission failure semantics changed"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority or any(
        type(value) is not bool or value for value in authority.values()
    ):
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission authority must remain exact false"
        )
    parameters = set(
        inspect.signature(GeometricAdmissionV3.admit_producer_batch).parameters
    )
    if parameters != {"self", "producer_batch"} or parameters & _FORBIDDEN_PARAMETERS:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission gained caller coordinates, result, or authority input"
        )
    return {
        "schema_id": (
            "betelgeuze.engine_v2_geometric_admission_v3_policy_verification/1.0.0"
        ),
        "policy_sha256": observed_sha256,
        "verification_blockers": [],
        "verified": True,
        "activation_evidence_eligible": False,
        "producer_attested": False,
        "molecular_execution_authorized": False,
        "reservation_allowed": False,
        "public_or_scientific_claim_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    arguments = parser.parse_args(argv)
    try:
        result = verify_policy(arguments.policy)
    except GeometricAdmissionV3PolicyVerificationError as exc:
        print(
            json.dumps(
                {
                    "verified": False,
                    "verification_blockers": [str(exc)],
                    "activation_evidence_eligible": False,
                    "producer_attested": False,
                    "molecular_execution_authorized": False,
                    "reservation_allowed": False,
                    "public_or_scientific_claim_authorized": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
