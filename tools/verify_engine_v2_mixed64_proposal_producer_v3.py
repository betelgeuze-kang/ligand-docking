#!/usr/bin/env python3
"""Verify the frozen non-authoritative mixed64 fixed64 producer policy."""

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


def _load_producer_module():
    package_name = "_engine_v2_mixed64_producer_verifier_policy"
    package_path = _REPO_ROOT / "betelgeuze_engine_v2" / "docking"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(package_path)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package
    module_name = f"{package_name}.mixed64_proposal_producer_v3"
    try:
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_path / "mixed64_proposal_producer_v3.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("mixed64 proposal producer is unavailable")
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


_PRODUCER = _load_producer_module()
MIXED64_PRODUCER_POLICY_SHA256 = _PRODUCER.MIXED64_PRODUCER_POLICY_SHA256
frozen_mixed64_producer_policy = _PRODUCER.frozen_mixed64_producer_policy
produce_fixed_mixed64_proposals = _PRODUCER.produce_fixed_mixed64_proposals


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_mixed64_proposal_producer_v3.json"
)
_FORBIDDEN_PARAMETERS: Final = {
    "authority",
    "benchmark_outcome",
    "fresh",
    "native_pose",
    "rank",
    "reservation",
    "rmsd",
    "score",
    "validity_result",
}


class Mixed64ProposalProducerPolicyVerificationError(ValueError):
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
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer policy must be one JSON object"
        )
    try:
        canonical = _canonical_bytes(document)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer policy contains non-canonical values"
        ) from exc
    if raw != canonical + b"\n":
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer policy is not canonical JSON"
        )
    if document != frozen_mixed64_producer_policy():
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != MIXED64_PRODUCER_POLICY_SHA256:
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer policy SHA-256 changed"
        )
    if document.get("candidate_denominator") != 64:
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer denominator is not fixed64"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority or any(
        type(value) is not bool or value for value in authority.values()
    ):
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer authority must remain exact false"
        )
    if set(inspect.signature(produce_fixed_mixed64_proposals).parameters) & (
        _FORBIDDEN_PARAMETERS
    ):
        raise Mixed64ProposalProducerPolicyVerificationError(
            "producer gained a result or authority input"
        )
    return {
        "schema_id": "betelgeuze.engine_v2_mixed64_producer_policy_verification/1.0.0",
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
    except Mixed64ProposalProducerPolicyVerificationError as exc:
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
