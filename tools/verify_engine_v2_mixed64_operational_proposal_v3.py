#!/usr/bin/env python3
"""Verify the frozen non-authoritative mixed64 operational proposal policy."""

from __future__ import annotations

import argparse
import ast
import hashlib
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

from betelgeuze_engine_v2.docking.mixed64_operational_proposal_policy_v3 import (  # noqa: E402
    DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID,
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    REQUIRED_PROPOSAL_NUMERIC_POLICY_ID,
    frozen_mixed64_operational_proposal_policy,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_mixed64_operational_proposal_v3.json"
)
_FORBIDDEN_PARAMETERS: Final = {
    "authority",
    "benchmark_outcome",
    "candidate_coordinates",
    "fresh",
    "fingerprint_sha256",
    "rank",
    "reservation",
    "result",
    "rmsd",
    "score",
    "validity",
}


class Mixed64OperationalProposalPolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _function_parameters(path: Path, function_name: str) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise Mixed64OperationalProposalPolicyVerificationError(
            f"{function_name} implementation source is unreadable"
        ) from exc
    functions = tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    if len(functions) != 1:
        raise Mixed64OperationalProposalPolicyVerificationError(
            f"{function_name} implementation is not unique"
        )
    arguments = functions[0].args
    return {
        value.arg
        for value in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy must be one JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy is not canonical JSON"
        )
    if document != frozen_mixed64_operational_proposal_policy():
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy SHA-256 changed"
        )
    source_identity = document.get("source_identity")
    if (
        document.get("candidate_denominator") != 64
        or type(source_identity) is not dict
        or source_identity.get("required_schema_id")
        != DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID
        or source_identity.get("required_numeric_policy_id")
        != REQUIRED_PROPOSAL_NUMERIC_POLICY_ID
        or source_identity.get("required_numeric_dtype") != "float64"
    ):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal identity contract changed"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority or any(
        type(value) is not bool or value for value in authority.values()
    ):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal authority must remain exact false"
        )
    materializer_parameters = _function_parameters(
        _REPO_ROOT
        / "betelgeuze_engine_v2"
        / "docking"
        / "mixed64_operational_proposal_v3.py",
        "materialize_mixed64_operational_proposals",
    )
    proposal_factory_parameters = _function_parameters(
        _REPO_ROOT / "betelgeuze_engine_v2" / "docking" / "proposals.py",
        "bind_docking_proposal_state",
    )
    if (
        materializer_parameters != {"admission_batch"}
        or materializer_parameters & _FORBIDDEN_PARAMETERS
        or "fingerprint_sha256" in proposal_factory_parameters
        or "candidate_id" in proposal_factory_parameters
    ):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal API gained caller identity, result, or authority input"
        )
    return {
        "schema_id": (
            "betelgeuze.engine_v2_mixed64_operational_proposal_policy_verification/1.0.0"
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
    except Mixed64OperationalProposalPolicyVerificationError as exc:
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
