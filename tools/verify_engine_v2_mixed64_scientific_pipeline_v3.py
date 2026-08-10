#!/usr/bin/env python3
"""Verify the frozen synthetic fixed64 scientific-pipeline policy."""

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

from betelgeuze_engine_v2.docking.mixed64_scientific_pipeline_policy_v3 import (  # noqa: E402
    BOUND_GEOMETRIC_ADMISSION_POLICY_SHA256,
    BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    BOUND_PRODUCER_POLICY_SHA256,
    BOUND_SCORER_VALIDITY_RANKING_POLICY_SHA256,
    BOUND_V7_POST_ADMISSION_POLICY_SHA256,
    MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256,
    frozen_mixed64_scientific_pipeline_policy,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_mixed64_scientific_pipeline_v3.json"
)
_EXECUTOR_PATH: Final = (
    _REPO_ROOT
    / "betelgeuze_engine_v2"
    / "docking"
    / "mixed64_scientific_pipeline_v3.py"
)
_EXECUTOR_NAME: Final = "execute_synthetic_mixed64_scientific_pipeline"
_EXPECTED_STAGE_ORDER: Final = (
    "fixed64_producer",
    "pre_refinement_geometric_admission",
    "operational_proposal_materialization",
    "current_v7_post_admission",
    "scorer_v1_validity_stable_ranking",
)
_EXPECTED_STAGE_POLICIES: Final = {
    "fixed64_producer": BOUND_PRODUCER_POLICY_SHA256,
    "pre_refinement_geometric_admission": (
        BOUND_GEOMETRIC_ADMISSION_POLICY_SHA256
    ),
    "operational_proposal_materialization": (
        BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256
    ),
    "current_v7_post_admission": BOUND_V7_POST_ADMISSION_POLICY_SHA256,
    "scorer_v1_validity_stable_ranking": (
        BOUND_SCORER_VALIDITY_RANKING_POLICY_SHA256
    ),
}
_STAGE_CALL_NAMES: Final = {
    "produce_fixed_mixed64_proposals": "fixed64_producer",
    "materialize_mixed64_operational_proposals": (
        "operational_proposal_materialization"
    ),
    "execute_synthetic_mixed64_v7_post_admission": (
        "current_v7_post_admission"
    ),
    "execute_synthetic_mixed64_scorer_validity_ranking": (
        "scorer_v1_validity_stable_ranking"
    ),
}
_FORBIDDEN_PARAMETERS: Final = {
    "allocation",
    "authority",
    "backend",
    "benchmark_outcome",
    "candidate_coordinates",
    "config",
    "fresh",
    "rank",
    "reservation",
    "result",
    "rmsd",
    "score",
    "terms",
    "threshold",
    "validity",
    "weights",
}


class Mixed64ScientificPipelinePolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _executor_contract() -> ast.FunctionDef | ast.AsyncFunctionDef:
    try:
        tree = ast.parse(
            _EXECUTOR_PATH.read_text(encoding="utf-8"),
            filename=str(_EXECUTOR_PATH),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline executor source is unreadable"
        ) from exc
    functions = tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == _EXECUTOR_NAME
    )
    if len(functions) != 1:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline executor is not unique"
        )
    return functions[0]


def _verify_executor_source() -> None:
    function = _executor_contract()
    arguments = function.args
    parameters = {
        value.arg
        for value in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    if parameters != {"source_bundle", "refiner", "scorer"} or (
        parameters & _FORBIDDEN_PARAMETERS
    ):
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline API gained result, tuning, or authority input"
        )

    observed_calls: list[tuple[int, str]] = []
    producer_calls: list[ast.Call] = []
    admission_calls = 0
    admission_constructors = 0
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id == "GeometricAdmissionV3":
                admission_constructors += 1
            stage = _STAGE_CALL_NAMES.get(node.func.id)
            if stage is not None:
                observed_calls.append((node.lineno, stage))
                if node.func.id == "produce_fixed_mixed64_proposals":
                    producer_calls.append(node)
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "admit_producer_batch"
        ):
            admission_calls += 1
            observed_calls.append(
                (node.lineno, "pre_refinement_geometric_admission")
            )
    ordered = tuple(stage for _line, stage in sorted(observed_calls))
    if ordered != _EXPECTED_STAGE_ORDER:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline stage order or call count changed"
        )
    if admission_constructors != 1 or admission_calls != 1:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "geometric admission boundary changed"
        )
    if len(producer_calls) != 1:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "fixed64 producer call boundary changed"
        )
    producer_call = producer_calls[0]
    first_argument = producer_call.args[0] if producer_call.args else None
    source_keyword = next(
        (
            keyword.value
            for keyword in producer_call.keywords
            if keyword.arg == "source_bundle"
        ),
        None,
    )
    if not (
        isinstance(first_argument, ast.Attribute)
        and isinstance(first_argument.value, ast.Name)
        and first_argument.value.id == "source_bundle"
        and first_argument.attr == "allocation"
        and isinstance(source_keyword, ast.Name)
        and source_keyword.id == "source_bundle"
    ):
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "producer allocation is not owned by the exact source bundle"
        )


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline policy must be one JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline policy is not canonical JSON"
        )
    if document != frozen_mixed64_scientific_pipeline_policy():
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline policy SHA-256 changed"
        )
    if (
        document.get("candidate_denominator") != 64
        or tuple(document.get("execution_order", ())) != _EXPECTED_STAGE_ORDER
        or document.get("stage_policy_sha256s") != _EXPECTED_STAGE_POLICIES
    ):
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline stage binding changed"
        )
    semantics = document.get("execution_semantics")
    if type(semantics) is not dict or not all(
        semantics.get(key) is expected
        for key, expected in {
            "exact_source_bundle_required": True,
            "source_bundle_owns_allocation": True,
            "one_call_per_stage": True,
            "result_dependent_retry_allowed": False,
            "caller_allocation_allowed": False,
            "caller_coordinates_allowed": False,
            "caller_thresholds_or_weights_allowed": False,
            "caller_scores_terms_validity_or_ranks_allowed": False,
            "stage_receipt_sha256s_required": True,
            "final_complete_scorer_v1_evidence_required": True,
            "pipeline_source_stable_before_and_after": True,
        }.items()
    ):
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline execution semantics changed"
        )
    failure = document.get("failure_semantics")
    if type(failure) is not dict or failure != {
        "one_record_per_slot_required": True,
        "failed_or_rejected_slot_deleted": False,
        "failed_slot_reallocated": False,
        "typed_failures_preserved": True,
        "primary_ranking_includes_pose_invalid": True,
        "valid_only_ranking_preserved": True,
    }:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline failure semantics changed"
        )
    consumer = document.get("consumer_contract")
    if type(consumer) is not dict or consumer != {
        "canonical_scientific_core_receipt": True,
        "standalone_consumer_activation_authorized": False,
        "benchmark_consumer_activation_authorized": False,
        "api_consumer_activation_authorized": False,
        "product_shadow_consumer_activation_authorized": False,
    }:
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline consumer authority changed"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority or any(
        type(value) is not bool or value for value in authority.values()
    ):
        raise Mixed64ScientificPipelinePolicyVerificationError(
            "scientific pipeline authority must remain exact false"
        )
    _verify_executor_source()
    return {
        "schema_id": (
            "betelgeuze.engine_v2_mixed64_scientific_pipeline_policy_verification/1.0.0"
        ),
        "policy_sha256": observed_sha256,
        "verification_blockers": [],
        "verified": True,
        "canonical_scientific_core_receipt": True,
        "activation_evidence_eligible": False,
        "producer_attested": False,
        "molecular_execution_authorized": False,
        "reservation_allowed": False,
        "hip_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    arguments = parser.parse_args(argv)
    try:
        result = verify_policy(arguments.policy)
    except Mixed64ScientificPipelinePolicyVerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
