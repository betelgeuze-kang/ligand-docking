#!/usr/bin/env python3
"""Verify the repository synthetic-D0 mixed64 source-adapter policy."""

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

from betelgeuze_engine_v2.docking.synthetic_d0_mixed64_source_policy_v3 import (  # noqa: E402
    BOUND_FIXTURE_ID,
    BOUND_FIXTURE_MANIFEST_SHA256,
    BOUND_GUIDED_POLICY_SHA256,
    BOUND_PIPELINE_PROFILE_RECEIPT_SHA256,
    BOUND_REQUEST_SHA256,
    BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256,
    PARTIAL_CHARGE_SITE_THRESHOLD,
    RETAINED_SOURCE_INDICES,
    SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
    V7_CONTROL_SOURCE_INDICES,
    frozen_synthetic_d0_mixed64_source_policy,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT / "config" / "engine_v2_synthetic_d0_mixed64_source_v3.json"
)
_ADAPTER_PATH: Final = (
    _REPO_ROOT
    / "betelgeuze_engine_v2"
    / "docking"
    / "synthetic_d0_mixed64_source_v3.py"
)
_ADAPTER_NAME: Final = "build_repository_synthetic_d0_mixed64_source"
_FORBIDDEN_PARAMETERS: Final = {
    "allocation",
    "authority",
    "benchmark_outcome",
    "candidate_coordinates",
    "conformers",
    "features",
    "fresh",
    "rank",
    "reservation",
    "result",
    "rmsd",
    "score",
    "seed",
    "source_indices",
    "terms",
    "threshold",
    "validity",
    "weights",
}


class SyntheticD0Mixed64SourcePolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _verify_adapter_source() -> None:
    try:
        tree = ast.parse(
            _ADAPTER_PATH.read_text(encoding="utf-8"),
            filename=str(_ADAPTER_PATH),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source adapter is unreadable"
        ) from exc
    functions = tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == _ADAPTER_NAME
    )
    if len(functions) != 1:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source adapter is not unique"
        )
    function = functions[0]
    arguments = function.args
    parameters = {
        value.arg
        for value in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    if parameters != {"request"} or parameters & _FORBIDDEN_PARAMETERS:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source API gained allocation, result, or authority input"
        )
    calls = tuple(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "generate_guided_docking_proposals"
    )
    if len(calls) != 1:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 guided source generation call count changed"
        )
    if any(isinstance(node, (ast.Try, ast.While)) for node in ast.walk(function)):
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source adapter gained retry control flow"
        )


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source policy must be one object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source policy is not canonical JSON"
        )
    if document != frozen_synthetic_d0_mixed64_source_policy():
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source policy SHA-256 changed"
        )
    fixture = document.get("fixture")
    generation = document.get("source_generation")
    features = document.get("feature_extraction")
    binding = document.get("receipt_binding")
    if (
        type(fixture) is not dict
        or fixture.get("fixture_id") != BOUND_FIXTURE_ID
        or fixture.get("manifest_sha256") != BOUND_FIXTURE_MANIFEST_SHA256
        or fixture.get("request_sha256") != BOUND_REQUEST_SHA256
        or fixture.get("pipeline_profile_receipt_sha256")
        != BOUND_PIPELINE_PROFILE_RECEIPT_SHA256
        or fixture.get("candidate_denominator") != 64
        or fixture.get("seed") != 4301
        or type(generation) is not dict
        or generation.get("guided_policy_sha256") != BOUND_GUIDED_POLICY_SHA256
        or generation.get("one_call") is not True
        or generation.get("result_dependent_retry_allowed") is not False
        or generation.get("v7_control_source_indices")
        != list(V7_CONTROL_SOURCE_INDICES)
        or generation.get("retained_source_indices")
        != list(RETAINED_SOURCE_INDICES)
        or generation.get("true_conformer_generation_allowed") is not False
        or generation.get("true_conformer_sources") != []
        or type(features) is not dict
        or features.get("partial_charge_site_threshold_binary64_hex")
        != PARTIAL_CHARGE_SITE_THRESHOLD.hex()
        or features.get("result_fields_consumed") is not False
        or type(binding) is not dict
        or binding.get("scientific_pipeline_policy_sha256")
        != BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256
        or binding.get("adapter_source_stable_before_and_after") is not True
    ):
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source identity or derivation changed"
        )
    consumer = document.get("consumer_contract")
    if type(consumer) is not dict or consumer != {
        "standalone_binding_ready": True,
        "standalone_activation_authorized": False,
        "benchmark_activation_authorized": False,
        "api_activation_authorized": False,
        "product_shadow_activation_authorized": False,
    }:
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source consumer authority changed"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority or any(
        type(value) is not bool or value for value in authority.values()
    ):
        raise SyntheticD0Mixed64SourcePolicyVerificationError(
            "synthetic D0 source authority must remain exact false"
        )
    _verify_adapter_source()
    return {
        "schema_id": (
            "betelgeuze.engine_v2_synthetic_d0_mixed64_source_policy_verification/1.0.0"
        ),
        "policy_sha256": observed_sha256,
        "verification_blockers": [],
        "verified": True,
        "standalone_binding_ready": True,
        "standalone_activation_authorized": False,
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
    except SyntheticD0Mixed64SourcePolicyVerificationError as exc:
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
