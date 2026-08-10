#!/usr/bin/env python3
"""Verify the frozen, non-authoritative mixed64 geometry policy."""

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

# The repository package initializer imports optional product/AI dependencies.
# This verifier needs only the pure docking contract, so an isolated invocation
# installs namespace shells and lets normal relative imports load that surface.
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

from betelgeuze_engine_v2.docking.mixed64_proposal_geometry_v3 import (  # noqa: E402
    MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256,
    frozen_mixed64_proposal_geometry_policy,
    generate_indexed_so3_placement,
    generate_single_anchor_placement,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_mixed64_proposal_geometry_v3.json"
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
}


class Mixed64ProposalGeometryPolicyVerificationError(ValueError):
    """Raised when the frozen geometry policy fails closed."""


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
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "policy must be one exact JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "policy file is not canonical JSON with one terminal newline"
        )
    expected = frozen_mixed64_proposal_geometry_policy()
    if document != expected:
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "policy disagrees with the frozen implementation projection"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256:
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "policy SHA-256 disagrees with the implementation"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority:
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "policy authority map is absent"
        )
    if any(type(value) is not bool or value for value in authority.values()):
        raise Mixed64ProposalGeometryPolicyVerificationError(
            "every policy authority must be exact false"
        )
    for function in (
        generate_indexed_so3_placement,
        generate_single_anchor_placement,
    ):
        parameters = set(inspect.signature(function).parameters)
        if parameters & _FORBIDDEN_PARAMETERS:
            raise Mixed64ProposalGeometryPolicyVerificationError(
                f"{function.__name__} gained a result or authority input"
            )
    return {
        "schema_id": "betelgeuze.engine_v2_mixed64_proposal_geometry_policy_verification/1.0.0",
        "policy_sha256": observed_sha256,
        "verification_blockers": [],
        "verified": True,
        "activation_evidence_eligible": False,
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
    except Mixed64ProposalGeometryPolicyVerificationError as exc:
        print(
            json.dumps(
                {
                    "verified": False,
                    "verification_blockers": [str(exc)],
                    "activation_evidence_eligible": False,
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
