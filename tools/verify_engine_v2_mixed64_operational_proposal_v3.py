#!/usr/bin/env python3
"""Verify the frozen non-authoritative mixed64 operational proposal policy."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Final


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_policy_module():
    path = (
        _REPO_ROOT
        / "betelgeuze_engine_v2"
        / "docking"
        / "mixed64_operational_proposal_policy_v3.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_engine_v2_mixed64_operational_proposal_policy_v3",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("mixed64 operational proposal policy is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_POLICY = _load_policy_module()
COORDINATE_REPRODUCTION_ABSOLUTE_TOLERANCE = (
    _POLICY.COORDINATE_REPRODUCTION_ABSOLUTE_TOLERANCE
)
DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID = _POLICY.DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID
MAX_OPERATIONAL_PROPOSAL_RECEIPT_CANONICAL_BYTES = (
    _POLICY.MAX_OPERATIONAL_PROPOSAL_RECEIPT_CANONICAL_BYTES
)
MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256 = (
    _POLICY.MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256
)
REQUIRED_PROPOSAL_NUMERIC_POLICY_ID = _POLICY.REQUIRED_PROPOSAL_NUMERIC_POLICY_ID
frozen_mixed64_operational_proposal_policy = (
    _POLICY.frozen_mixed64_operational_proposal_policy
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


def _reject_nonfinite_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


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
    if arguments.vararg is not None or arguments.kwarg is not None:
        raise Mixed64OperationalProposalPolicyVerificationError(
            f"{function_name} must not accept variadic arguments"
        )
    return {
        value.arg
        for value in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }


def _contains_runtime_assert(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal implementation source is unreadable"
        ) from exc
    return any(isinstance(node, ast.Assert) for node in ast.walk(tree))


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(
            raw,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy must be one JSON object"
        )
    try:
        canonical = _canonical_bytes(document)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal policy is not canonical JSON"
        ) from exc
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
    if document.get("admission_live_integrity") != {
        "recursive_preflight_required": True,
        "recursive_postflight_required": True,
        "recursive_finalization_check_required": True,
        "operational_output_recursive_finalization_check_required": True,
    }:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal admission live-integrity boundary changed"
        )
    if document.get("receipt_integrity") != {
        "maximum_canonical_bytes": (MAX_OPERATIONAL_PROPOSAL_RECEIPT_CANONICAL_BYTES),
        "sealed_snapshot_required": True,
        "recursive_live_integrity_required": True,
    }:
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal receipt bound changed"
        )
    transformed_identity = document.get("transformed_identity")
    if (
        type(transformed_identity) is not dict
        or any(
            transformed_identity.get(key) is not True
            for key in (
                "source_operational_identity_preserved_separately",
                "passthrough_source_transform_preserved",
                "operational_proposal_index_is_fixed64_slot",
                "indexed_so3_target_centroid_rebased_to_affine_translation",
                "single_anchor_affine_translation_reused",
            )
        )
        or transformed_identity.get("row_vector_rotation_composition")
        != ("placement_rotation_matrix_multiply_source_rotation")
        or transformed_identity.get("row_vector_translation_composition")
        != (
            "source_translation_multiply_placement_rotation_transpose_plus_placement_affine_translation"
        )
        or transformed_identity.get(
            "coordinate_reproduction_absolute_tolerance_binary64_hex"
        )
        != COORDINATE_REPRODUCTION_ABSOLUTE_TOLERANCE.hex()
    ):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal transform composition changed"
        )
    failure_semantics = document.get("failure_semantics")
    if type(failure_semantics) is not dict or (
        failure_semantics.get("only_declared_domain_failures_are_typed") is not True
        or failure_semantics.get("unexpected_runtime_failure_typed") is not False
    ):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal failure boundary changed"
        )
    authority = document.get("authority")
    if (
        type(authority) is not dict
        or not authority
        or any(type(value) is not bool or value for value in authority.values())
    ):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal authority must remain exact false"
        )
    materializer_path = (
        _REPO_ROOT
        / "betelgeuze_engine_v2"
        / "docking"
        / "mixed64_operational_proposal_v3.py"
    )
    materializer_parameters = _function_parameters(
        materializer_path,
        "materialize_mixed64_operational_proposals",
    )
    proposal_factory_parameters = _function_parameters(
        _REPO_ROOT / "betelgeuze_engine_v2" / "docking" / "proposals.py",
        "bind_docking_proposal_state",
    )
    if _contains_runtime_assert(materializer_path):
        raise Mixed64OperationalProposalPolicyVerificationError(
            "operational proposal implementation contains optimizable runtime asserts"
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
