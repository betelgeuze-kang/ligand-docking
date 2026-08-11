#!/usr/bin/env python3
"""Verify the frozen non-authoritative geometric-admission v3 policy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import types
from typing import Final


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_admission_module():
    package_name = "_engine_v2_geometric_admission_v3_verifier_policy"
    package_path = _REPO_ROOT / "betelgeuze_engine_v2" / "docking"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(package_path)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package
    module_name = f"{package_name}.geometric_admission_v3"
    try:
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_path / "geometric_admission_v3.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("geometric admission v3 is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for loaded_name in tuple(sys.modules):
            if loaded_name == package_name or loaded_name.startswith(
                f"{package_name}."
            ):
                sys.modules.pop(loaded_name, None)


_ADMISSION = _load_admission_module()
GEOMETRIC_ADMISSION_V3_POLICY_SHA256 = (
    _ADMISSION.GEOMETRIC_ADMISSION_V3_POLICY_SHA256
)
GeometricAdmissionV3 = _ADMISSION.GeometricAdmissionV3
frozen_geometric_admission_v3_policy = (
    _ADMISSION.frozen_geometric_admission_v3_policy
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
    try:
        canonical = _canonical_bytes(document)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission v3 policy contains non-canonical values"
        ) from exc
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
    producer_integrity = document.get("producer_integrity")
    if producer_integrity != {
        "recursive_live_projection_preflight": True,
        "kernel_inputs_restored_from_sealed_projection": True,
        "recursive_live_projection_postflight": True,
        "decision_projection_rechecked_against_sealed_snapshot": True,
        "admission_decision_and_batch_live_integrity_available": True,
    }:
        raise GeometricAdmissionV3PolicyVerificationError(
            "geometric-admission producer integrity boundary changed"
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
