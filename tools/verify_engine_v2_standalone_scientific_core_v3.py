#!/usr/bin/env python3
"""Verify the sealed repository-synthetic standalone scientific core policy."""

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

from betelgeuze_engine_v2.docking.standalone_scientific_core_policy_v3 import (  # noqa: E402
    BOUND_REQUEST_SHA256,
    BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256,
    BOUND_SOURCE_ADAPTER_POLICY_SHA256,
    STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256,
    frozen_standalone_scientific_core_policy,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_standalone_scientific_core_v3.json"
)
_EXECUTOR_PATH: Final = (
    _REPO_ROOT
    / "betelgeuze_engine_v2"
    / "docking"
    / "standalone_scientific_core_v3.py"
)
_EXECUTOR_NAME: Final = (
    "execute_repository_synthetic_d0_standalone_scientific_core"
)
_EXPECTED_ORDER: Final = (
    "build_repository_synthetic_d0_mixed64_source",
    "InteractionAwareTorsionContactEnsembleRefinerV7",
    "ChemistryPoseScorerV1",
    "execute_synthetic_mixed64_scientific_pipeline",
    "StandaloneScientificCoreReceiptV1",
)
_FORBIDDEN_PARAMETER_TOKENS: Final = {
    "allocation",
    "authority",
    "backend",
    "benchmark",
    "candidate",
    "component",
    "coordinate",
    "fresh",
    "rank",
    "reservation",
    "result",
    "score",
    "source_bundle",
    "terms",
    "threshold",
    "validity",
    "weight",
}
_REQUIRED_RECEIPT_KEYS: Final = {
    "source_adapter_receipt",
    "source_adapter_receipt_sha256",
    "scientific_pipeline_receipt",
    "scientific_pipeline_receipt_sha256",
    "stage_receipt_sha256s",
    "complete_scorer_v1_terms_preserved",
    "complete_pose_validity_preserved",
    "primary_and_valid_only_rank_preserved",
    "failure_denominator_preserved",
}


class StandaloneScientificCorePolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _executor_tree() -> ast.Module:
    try:
        return ast.parse(
            _EXECUTOR_PATH.read_text(encoding="utf-8"),
            filename=str(_EXECUTOR_PATH),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific executor source is unreadable"
        ) from exc


def _named_function(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    if len(matches) != 1:
        raise StandaloneScientificCorePolicyVerificationError(
            f"standalone scientific {name} function is not unique"
        )
    return matches[0]


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _verify_executor_source() -> None:
    tree = _executor_tree()
    executor = _named_function(tree, _EXECUTOR_NAME)
    arguments = executor.args
    if (
        arguments.vararg is not None
        or arguments.kwarg is not None
        or arguments.kwonlyargs
        or len(arguments.posonlyargs) + len(arguments.args) != 1
    ):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific executor API changed"
        )
    parameter = (*arguments.posonlyargs, *arguments.args)[0].arg
    if parameter != "request" or any(
        token in parameter for token in _FORBIDDEN_PARAMETER_TOKENS
    ):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone executor gained result, tuning, source, or authority input"
        )
    ordered_calls = tuple(
        (node.lineno, name)
        for node in ast.walk(executor)
        if isinstance(node, ast.Call)
        and (name := _call_name(node)) in _EXPECTED_ORDER
    )
    observed = tuple(name for _line, name in sorted(ordered_calls))
    if observed != _EXPECTED_ORDER:
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific call order or call count changed"
        )
    forbidden_calls = {
        name
        for node in ast.walk(executor)
        if isinstance(node, ast.Call)
        and (name := _call_name(node)) is not None
        and any(
            token in name.lower()
            for token in (
                "reserve",
                "reservation",
                "fresh128",
                "historical_ab",
                "public_benchmark",
                "hip_",
            )
        )
    }
    if forbidden_calls:
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific executor contains a forbidden authority call"
        )
    projection = _named_function(tree, "_projection")
    returned_keys = {
        key.value
        for node in ast.walk(projection)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and type(key.value) is str
    }
    if not _REQUIRED_RECEIPT_KEYS.issubset(returned_keys):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific receipt lost required evidence bindings"
        )


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific policy must be one JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific policy is not canonical JSON"
        )
    if document != frozen_standalone_scientific_core_policy():
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256:
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone scientific policy SHA-256 changed"
        )
    if (
        document.get("candidate_denominator") != 64
        or document.get("top_k") != 5
        or document.get("request_sha256") != BOUND_REQUEST_SHA256
        or document.get("bound_policy_sha256s")
        != {
            "repository_synthetic_d0_source_adapter": (
                BOUND_SOURCE_ADAPTER_POLICY_SHA256
            ),
            "fixed64_scientific_pipeline": (
                BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256
            ),
        }
    ):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone dependency, request, or denominator binding changed"
        )
    semantics = document.get("execution_semantics")
    if type(semantics) is not dict or not all(
        semantics.get(key) is expected
        for key, expected in {
            "exact_repository_request_only": True,
            "caller_source_bundle_allowed": False,
            "caller_allocation_allowed": False,
            "caller_components_allowed": False,
            "caller_coordinates_allowed": False,
            "caller_thresholds_or_weights_allowed": False,
            "caller_scores_terms_validity_or_ranks_allowed": False,
            "one_source_adapter_call": True,
            "one_scientific_pipeline_call": True,
            "result_dependent_retry_allowed": False,
        }.items()
    ):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone execution semantics changed"
        )
    receipt = document.get("receipt_contract")
    if type(receipt) is not dict or not receipt or any(
        value is not True for value in receipt.values()
    ):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone receipt contract must remain exact true"
        )
    consumer = document.get("consumer_contract")
    authority = document.get("authority")
    if (
        type(consumer) is not dict
        or not consumer
        or any(type(value) is not bool or value for value in consumer.values())
        or type(authority) is not dict
        or not authority
        or any(type(value) is not bool or value for value in authority.values())
    ):
        raise StandaloneScientificCorePolicyVerificationError(
            "standalone consumer and production authority must remain exact false"
        )
    _verify_executor_source()
    return {
        "schema_id": (
            "betelgeuze.engine_v2_standalone_scientific_core_policy_verification/1.0.0"
        ),
        "policy_sha256": observed_sha256,
        "verification_blockers": [],
        "verified": True,
        "candidate_denominator": 64,
        "complete_scoring_validity_rank_receipt": True,
        "canonical_pipeline_activation_authorized": False,
        "molecular_execution_authorized": False,
        "reservation_allowed": False,
        "hip_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    args = parser.parse_args(argv)
    try:
        result = verify_policy(args.policy)
    except StandaloneScientificCorePolicyVerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
