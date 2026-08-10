#!/usr/bin/env python3
"""Verify exact synthetic-D0 standalone consumer routing and authority."""

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

from betelgeuze_engine_v2.docking.standalone_scientific_consumer_activation_policy_v3 import (  # noqa: E402
    STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SHA256,
    STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_SCOPE,
    frozen_standalone_scientific_consumer_activation_policy,
)
from betelgeuze_engine_v2.docking.standalone_scientific_core_policy_v3 import (  # noqa: E402
    BOUND_REQUEST_SHA256,
    STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256,
    STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT
    / "config"
    / "engine_v2_standalone_scientific_consumer_activation_v3.json"
)
_PIPELINE_PATH: Path = (
    _REPO_ROOT / "betelgeuze_engine_v2" / "docking" / "pipeline.py"
)
_CONSUMERS_PATH: Path = (
    _REPO_ROOT / "betelgeuze_engine_v2" / "docking" / "consumers.py"
)
_CLI_PATH: Path = _REPO_ROOT / "betelgeuze_engine_v2" / "standalone_cli.py"
_FORBIDDEN_CALL_TOKENS: Final = (
    "reserve",
    "reservation",
    "historical_ab",
    "fresh128",
    "public_benchmark",
    "hip_",
)
_FALSE_ENVELOPE_FIELDS: Final = {
    "pipeline_result_rewritten",
    "rank_or_selection_rewritten",
    "benchmark_dataset_accessed",
    "external_reservation_requested",
    "authority",
    "claim_safe",
}


class StandaloneScientificConsumerActivationVerificationError(ValueError):
    """The synthetic-only consumer activation contract failed closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _tree(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise StandaloneScientificConsumerActivationVerificationError(
            f"consumer activation source is unreadable: {path.name}"
        ) from exc


def _named_function(
    tree: ast.AST,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    if len(matches) != 1:
        raise StandaloneScientificConsumerActivationVerificationError(
            f"consumer activation function {name} is not unique"
        )
    return matches[0]


def _class_method(
    tree: ast.Module,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    classes = tuple(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    if len(classes) != 1:
        raise StandaloneScientificConsumerActivationVerificationError(
            f"consumer activation class {class_name} is not unique"
        )
    methods = tuple(
        node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    )
    if len(methods) != 1:
        raise StandaloneScientificConsumerActivationVerificationError(
            f"consumer activation method {class_name}.{method_name} is not unique"
        )
    return methods[0]


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _call_count(node: ast.AST, name: str) -> int:
    return sum(
        isinstance(item, ast.Call) and _call_name(item) == name
        for item in ast.walk(node)
    )


def _reject_forbidden_calls(node: ast.AST, *, surface: str) -> None:
    forbidden = {
        name
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and (name := _call_name(item)) is not None
        and any(token in name.lower() for token in _FORBIDDEN_CALL_TOKENS)
    }
    if forbidden:
        raise StandaloneScientificConsumerActivationVerificationError(
            f"{surface} contains forbidden execution or authority calls"
        )


def _verify_pipeline_route() -> None:
    tree = _tree(_PIPELINE_PATH)
    run = _class_method(tree, "DockingPipeline", "run")
    argument_names = tuple(
        argument.arg
        for argument in (*run.args.posonlyargs, *run.args.args)
    )
    if (
        argument_names != ("self", "request")
        or run.args.vararg is not None
        or run.args.kwarg is not None
        or run.args.kwonlyargs
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "canonical DockingPipeline.run API changed"
        )
    if (
        _call_count(
            run,
            "execute_repository_synthetic_d0_standalone_scientific_core",
        )
        != 1
        or _call_count(run, "_run_legacy_v1") != 1
        or _call_count(run, "_assert_fixture_admission") != 1
        or _call_count(run, "_assert_component_contracts") != 1
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "canonical pipeline scientific route or fallback changed"
        )
    names = {
        node.id for node in ast.walk(run) if isinstance(node, ast.Name)
    }
    if not {
        "SEALED_CANONICAL_COMPONENT_BINDING",
        "StandaloneScientificCoreReceiptV1",
    }.issubset(names):
        raise StandaloneScientificConsumerActivationVerificationError(
            "canonical pipeline lost sealed binding or exact receipt check"
        )
    _reject_forbidden_calls(run, surface="canonical pipeline")


def _constant_false_dict_keys(node: ast.AST) -> set[str]:
    return {
        key.value
        for item in ast.walk(node)
        if isinstance(item, ast.Dict)
        for key, value in zip(item.keys, item.values, strict=True)
        if isinstance(key, ast.Constant)
        and type(key.value) is str
        and isinstance(value, ast.Constant)
        and value.value is False
    }


def _verify_consumer_routes() -> None:
    tree = _tree(_CONSUMERS_PATH)
    exact_surface = _named_function(tree, "_run_exact_surface")
    direct = _named_function(tree, "run_standalone_docking")
    if any(
        _call_count(function, "DockingPipeline") != 1
        or _call_count(function, "run") != 1
        for function in (exact_surface, direct)
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer no-argument canonical pipeline call count changed"
        )
    if _call_count(exact_surface, "StandaloneConsumerEnvelopeV1") != 1:
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer envelope route changed"
        )
    for class_name in (
        "StandaloneDockingPythonApi",
        "StandaloneDiagnosticBenchmarkAdapter",
        "StandaloneProductShadowAdapter",
    ):
        run = _class_method(tree, class_name, "run")
        if (
            _call_count(run, "_run_exact_surface") != 1
            or _call_count(run, "DockingPipeline") != 0
        ):
            raise StandaloneScientificConsumerActivationVerificationError(
                f"{class_name} bypassed the exact consumer route"
            )
        _reject_forbidden_calls(run, surface=class_name)
    post_init = _class_method(
        tree,
        "StandaloneConsumerEnvelopeV1",
        "__post_init__",
    )
    projection = _class_method(
        tree,
        "StandaloneConsumerEnvelopeV1",
        "_projection",
    )
    if (
        "StandaloneScientificCoreReceiptV1"
        not in {
            node.id
            for node in ast.walk(post_init)
            if isinstance(node, ast.Name)
        }
        or not _FALSE_ENVELOPE_FIELDS.issubset(
            _constant_false_dict_keys(projection)
        )
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer envelope lost exact receipt or false-authority declarations"
        )
    _reject_forbidden_calls(exact_surface, surface="consumer envelope route")
    _reject_forbidden_calls(direct, surface="direct Python consumer route")


def _verify_cli_route() -> None:
    tree = _tree(_CLI_PATH)
    dock = _named_function(tree, "dock")
    verify = _named_function(tree, "verify_pipeline_result")
    report = _named_function(tree, "report_pipeline_result")
    if _call_count(dock, "DockingPipeline") != 1 or _call_count(dock, "run") != 1:
        raise StandaloneScientificConsumerActivationVerificationError(
            "CLI dock no longer calls the canonical pipeline exactly once"
        )
    if (
        _call_count(verify, "_verify_scientific_core_result") != 1
        or _call_count(report, "verify_pipeline_result") != 1
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "CLI verify/report scientific receipt route changed"
        )
    if "STANDALONE_SCIENTIFIC_CORE_RESULT_SCHEMA_ID" not in {
        node.id for node in ast.walk(verify) if isinstance(node, ast.Name)
    }:
        raise StandaloneScientificConsumerActivationVerificationError(
            "CLI verifier lost the exact scientific receipt schema dispatch"
        )
    for name, function in (
        ("CLI dock", dock),
        ("CLI verify", verify),
        ("CLI report", report),
    ):
        _reject_forbidden_calls(function, surface=name)


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer activation policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer activation policy must be one JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer activation policy is not canonical JSON"
        )
    if document != frozen_standalone_scientific_consumer_activation_policy():
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer activation policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if (
        observed_sha256
        != STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SHA256
        or document.get("activation_scope")
        != STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_SCOPE
        or document.get("bound_request_sha256") != BOUND_REQUEST_SHA256
        or document.get("bound_scientific_core_policy_sha256")
        != STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256
        or document.get("bound_scientific_core_receipt_schema_id")
        != STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID
        or document.get("candidate_denominator") != 64
        or document.get("top_k") != 5
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer activation dependency or fixed64 binding changed"
        )
    authority = document.get("authority")
    routing = document.get("routing_contract")
    if (
        type(authority) is not dict
        or not authority
        or any(type(value) is not bool or value for value in authority.values())
        or type(routing) is not dict
        or routing.get("rank_or_selection_rewrite_allowed") is not False
        or routing.get("result_dependent_retry_allowed") is not False
        or routing.get("external_network_or_reservation_call_allowed") is not False
        or any(
            routing.get(key) is not True
            for key in (
                "canonical_pipeline_calls_exact_scientific_executor_once",
                "consumer_invocation_calls_no_argument_pipeline_once",
                "consumer_receipt_embedded_unmodified",
                "cli_serializes_exact_core_receipt",
                "cli_verify_rederives_scoring_validity_and_ranks",
                "benchmark_scope_is_repository_synthetic_d0",
                "product_shadow_evidence_display_only",
                "operator_second_opinion_only",
            )
        )
    ):
        raise StandaloneScientificConsumerActivationVerificationError(
            "consumer routing or authority contract is invalid"
        )
    _verify_pipeline_route()
    _verify_consumer_routes()
    _verify_cli_route()
    return {
        "schema_id": (
            "betelgeuze.engine_v2_standalone_scientific_consumer_"
            "activation_verification/1.0.0"
        ),
        "policy_sha256": observed_sha256,
        "activation_scope": STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_SCOPE,
        "verified_surfaces": [
            "canonical_pipeline",
            "cli",
            "python_api",
            "diagnostic_benchmark",
            "product_shadow",
        ],
        "candidate_denominator": 64,
        "same_core_receipt_route_verified": True,
        "rank_or_selection_rewrite_authorized": False,
        "product_or_molecular_execution_authorized": False,
        "reservation_allowed": False,
        "hip_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
        "verification_blockers": [],
        "verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    args = parser.parse_args(argv)
    try:
        result = verify_policy(args.policy)
    except StandaloneScientificConsumerActivationVerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
