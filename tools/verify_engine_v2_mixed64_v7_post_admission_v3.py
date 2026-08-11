#!/usr/bin/env python3
"""Verify the frozen, synthetic-only mixed64 V7 post-admission policy."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Final


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_policy_module():
    path = (
        _REPO_ROOT
        / "betelgeuze_engine_v2"
        / "docking"
        / "mixed64_v7_post_admission_policy_v3.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_engine_v2_mixed64_v7_post_admission_policy_v3",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("mixed64 V7 post-admission policy is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_POLICY = _load_policy_module()
BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256 = (
    _POLICY.BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256
)
BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256 = (
    _POLICY.BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256
)
MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES = _POLICY.MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES
MAX_V7_IMPLEMENTATION_SOURCE_BYTES = _POLICY.MAX_V7_IMPLEMENTATION_SOURCE_BYTES
MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES = (
    _POLICY.MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES
)
MIXED64_V7_POST_ADMISSION_POLICY_SHA256 = (
    _POLICY.MIXED64_V7_POST_ADMISSION_POLICY_SHA256
)
POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO = (
    _POLICY.POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO
)
POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS = (
    _POLICY.POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS
)
V7_REFINEMENT_MAX_STEPS = _POLICY.V7_REFINEMENT_MAX_STEPS
V7_TORSION_ELIGIBLE_SLOT_INDICES = _POLICY.V7_TORSION_ELIGIBLE_SLOT_INDICES
frozen_mixed64_v7_post_admission_policy = (
    _POLICY.frozen_mixed64_v7_post_admission_policy
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_mixed64_v7_post_admission_v3.json"
)
_EXECUTOR_PATH: Final = (
    _REPO_ROOT / "betelgeuze_engine_v2" / "docking" / "mixed64_v7_post_admission_v3.py"
)
_EXECUTOR_NAME: Final = "execute_synthetic_mixed64_v7_post_admission"
_FORBIDDEN_PARAMETERS: Final = {
    "authority",
    "benchmark_outcome",
    "candidate_coordinates",
    "fresh",
    "max_steps",
    "molecular_case",
    "rank",
    "reservation",
    "result",
    "rmsd",
    "score",
    "threshold",
    "validity",
}


class Mixed64V7PostAdmissionPolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _reject_nonfinite_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number is forbidden")
    return parsed


def _executor_contract() -> tuple[set[str], ast.FunctionDef | ast.AsyncFunctionDef]:
    try:
        tree = ast.parse(
            _EXECUTOR_PATH.read_text(encoding="utf-8"),
            filename=str(_EXECUTOR_PATH),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission executor source is unreadable"
        ) from exc
    functions = tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == _EXECUTOR_NAME
    )
    if len(functions) != 1:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission executor is not unique"
        )
    function = functions[0]
    arguments = function.args
    if arguments.vararg is not None or arguments.kwarg is not None:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission API gained variadic input"
        )
    parameters = {
        value.arg
        for value in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    return parameters, function


def _verify_executor_source() -> None:
    parameters, function = _executor_contract()
    if parameters != {"operational_batch", "refiner"} or (
        parameters & _FORBIDDEN_PARAMETERS
    ):
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission API gained result, tuning, or authority input"
        )
    refine_calls = tuple(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "refiner"
        and node.func.attr == "refine"
    )
    if len(refine_calls) != 1:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission refinement call boundary changed"
        )
    keywords = {item.arg: item.value for item in refine_calls[0].keywords}
    max_steps = keywords.get("max_steps")
    if (
        len(refine_calls[0].args) != 1
        or set(keywords) != {"max_steps"}
        or not isinstance(max_steps, ast.Name)
        or max_steps.id != "V7_REFINEMENT_MAX_STEPS"
    ):
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 refinement budget is no longer frozen in the executor"
        )
    refinement_try_blocks = tuple(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Try)
        and any(
            candidate is refine_calls[0]
            for statement in node.body
            for candidate in ast.walk(statement)
        )
    )
    if (
        len(refinement_try_blocks) != 1
        or len(refinement_try_blocks[0].handlers) != 1
        or not isinstance(refinement_try_blocks[0].handlers[0].type, ast.Name)
        or refinement_try_blocks[0].handlers[0].type.id
        != "TorsionContactRefinementError"
    ):
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 refinement exception boundary is not the declared domain error"
        )
    admission_calls = tuple(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "evaluate_geometric_admission_metrics_one_python"
    )
    if len(admission_calls) != 1:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "post-refinement full-Cartesian admission boundary changed"
        )


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(
            raw,
            parse_constant=_reject_nonfinite_constant,
            parse_float=_parse_finite_float,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission policy must be one JSON object"
        )
    try:
        canonical = _canonical_bytes(document)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission policy cannot be canonicalized"
        ) from exc
    if raw != canonical + b"\n":
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission policy is not canonical JSON"
        )
    if document != frozen_mixed64_v7_post_admission_policy():
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != MIXED64_V7_POST_ADMISSION_POLICY_SHA256:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission policy SHA-256 changed"
        )
    refinement = document.get("refinement")
    admission = document.get("post_refinement_geometric_admission")
    if (
        document.get("candidate_denominator") != 64
        or document.get("operational_proposal_policy_sha256")
        != BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256
        or type(refinement) is not dict
        or refinement.get("max_steps") != V7_REFINEMENT_MAX_STEPS == 24
        or refinement.get("maximum_implementation_source_bytes")
        != MAX_V7_IMPLEMENTATION_SOURCE_BYTES
        or refinement.get("implementation_source_binding")
        != "single_fd_nofollow_stable_file_sha256_before_after_and_finalization"
        or refinement.get("torsion_eligible_slot_indices")
        != list(V7_TORSION_ELIGIBLE_SLOT_INDICES)
        or refinement.get("preexisting_refiner_receipts_allowed") is not False
        or (
            refinement.get("problem_and_search_space_identity_exact_match_required")
            is not True
        )
        or refinement.get("geometric_context_exact_match_required") is not True
        or refinement.get("one_refinement_attempt_per_materialized_slot") is not True
        or refinement.get("result_dependent_retry_allowed") is not False
        or type(admission) is not dict
        or admission.get("geometric_admission_v3_policy_sha256")
        != BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256
        or admission.get("hard_rejection_threshold_binary64_hex")
        != POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
        or admission.get("maximum_batch_exact_pair_evaluations")
        != POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS
        or admission.get("pair_bound_checked_before_refinement") is not True
    ):
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7, fixed64, or post-admission contract changed"
        )
    if document.get("operational_input_integrity") != {
        "recursive_preflight_required": True,
        "recursive_postflight_required": True,
        "recursive_finalization_check_required": True,
        "operational_proposal_index_is_fixed64_slot": True,
    }:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 operational input-integrity boundary changed"
        )
    if document.get("output_live_integrity") != {
        "recursive_finalization_required": True,
        "recursive_downstream_verifier_available": True,
    }:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 output live-integrity boundary changed"
        )
    if document.get("receipt_integrity") != {
        "maximum_canonical_bytes": (MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES),
        "sealed_snapshot_required": True,
        "recursive_live_integrity_required": True,
    }:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission receipt bound changed"
        )
    failure_semantics = document.get("failure_semantics")
    if type(failure_semantics) is not dict or failure_semantics != {
        "upstream_nonmaterialized_refined": False,
        "typed_refinement_failure_preserved": True,
        "typed_refinement_failure_reason_preserved": True,
        "maximum_typed_failure_reason_utf8_bytes": (
            MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES
        ),
        "declared_typed_error": "TorsionContactRefinementError",
        "unexpected_runtime_failure_typed": False,
        "failed_slot_retried": False,
        "slot_reallocation_allowed": False,
        "post_rejection_deleted": False,
    }:
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission failure semantics changed"
        )
    authority = document.get("authority")
    if (
        type(authority) is not dict
        or not authority
        or any(type(value) is not bool or value for value in authority.values())
    ):
        raise Mixed64V7PostAdmissionPolicyVerificationError(
            "V7 post-admission authority must remain exact false"
        )
    _verify_executor_source()
    return {
        "schema_id": (
            "betelgeuze.engine_v2_mixed64_v7_post_admission_policy_verification/1.0.0"
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
    except Mixed64V7PostAdmissionPolicyVerificationError as exc:
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
