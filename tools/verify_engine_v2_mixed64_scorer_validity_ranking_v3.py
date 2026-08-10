#!/usr/bin/env python3
"""Verify the frozen synthetic mixed64 score/validity/rank policy."""

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

from betelgeuze_engine_v2.docking.mixed64_scorer_validity_ranking_policy_v3 import (  # noqa: E402
    BOUND_V7_POST_ADMISSION_POLICY_SHA256,
    FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256,
    FROZEN_SCORER_V1_CONFIG_SHA256,
    FROZEN_VDW_CONTACT_POLICY_SHA256,
    MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
    SCORER_V1_TERM_NAMES,
    frozen_mixed64_scorer_validity_ranking_policy,
)


DEFAULT_POLICY_PATH: Final = (
    _REPO_ROOT
    / "config"
    / "engine_v2_mixed64_scorer_validity_ranking_v3.json"
)
_EXECUTOR_PATH: Final = (
    _REPO_ROOT
    / "betelgeuze_engine_v2"
    / "docking"
    / "mixed64_scorer_validity_ranking_v3.py"
)
_EXECUTOR_NAME: Final = "execute_synthetic_mixed64_scorer_validity_ranking"
_FORBIDDEN_PARAMETERS: Final = {
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


class Mixed64ScorerValidityRankingPolicyVerificationError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _executor_contract() -> tuple[set[str], ast.FunctionDef | ast.AsyncFunctionDef]:
    try:
        tree = ast.parse(
            _EXECUTOR_PATH.read_text(encoding="utf-8"),
            filename=str(_EXECUTOR_PATH),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity executor source is unreadable"
        ) from exc
    functions = tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == _EXECUTOR_NAME
    )
    if len(functions) != 1:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity executor is not unique"
        )
    function = functions[0]
    arguments = function.args
    return (
        {
            value.arg
            for value in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            )
        },
        function,
    )


def _count_attribute_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    owner: str,
    method: str,
) -> int:
    return sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == owner
        and node.func.attr == method
        for node in ast.walk(function)
    )


def _verify_executor_source() -> None:
    parameters, function = _executor_contract()
    if parameters != {"post_admission_batch", "scorer"} or (
        parameters & _FORBIDDEN_PARAMETERS
    ):
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity API gained result, tuning, or authority input"
        )
    if _count_attribute_calls(function, owner="scorer", method="score_batch") != 1:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "Scorer V1 batch call boundary changed"
        )
    if (
        _count_attribute_calls(
            function,
            owner="validity_context",
            method="evaluate",
        )
        != 1
    ):
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "pose-validity call boundary changed"
        )


def verify_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity policy is unreadable or invalid JSON"
        ) from exc
    if type(document) is not dict:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity policy must be one JSON object"
        )
    canonical = _canonical_bytes(document)
    if raw != canonical + b"\n":
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity policy is not canonical JSON"
        )
    if document != frozen_mixed64_scorer_validity_ranking_policy():
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity policy disagrees with implementation"
        )
    observed_sha256 = hashlib.sha256(canonical).hexdigest()
    if observed_sha256 != MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity policy SHA-256 changed"
        )
    scoring = document.get("scoring")
    validity = document.get("validity")
    ranking = document.get("ranking")
    if (
        document.get("candidate_denominator") != 64
        or document.get("v7_post_admission_policy_sha256")
        != BOUND_V7_POST_ADMISSION_POLICY_SHA256
        or type(scoring) is not dict
        or scoring.get("backend") != "python_reference"
        or scoring.get("config_fingerprint_sha256")
        != FROZEN_SCORER_V1_CONFIG_SHA256
        or scoring.get("backend_options_fingerprint_sha256")
        != FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256
        or scoring.get("maximum_batch_size") != 64
        or scoring.get("term_names") != list(SCORER_V1_TERM_NAMES)
        or scoring.get("result_dependent_retry_allowed") is not False
        or type(validity) is not dict
        or validity.get("contact_policy_fingerprint_sha256")
        != FROZEN_VDW_CONTACT_POLICY_SHA256
        or validity.get("result_dependent_retry_allowed") is not False
        or type(ranking) is not dict
        or ranking.get("top_k") != 5
        or ranking.get("primary_includes_pose_invalid") is not True
        or ranking.get("primary_includes_validity_unavailable") is not True
    ):
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "fixed64 scorer, validity, or ranking contract changed"
        )
    failure_semantics = document.get("failure_semantics")
    if type(failure_semantics) is not dict or failure_semantics != {
        "upstream_nonaccepted_scored": False,
        "typed_scoring_failure_preserved": True,
        "typed_validity_failure_preserves_score": True,
        "validity_incomplete_preserves_result": True,
        "failed_slot_retried": False,
        "slot_reallocation_allowed": False,
        "failed_or_rejected_slot_deleted": False,
    }:
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity failure semantics changed"
        )
    authority = document.get("authority")
    if type(authority) is not dict or not authority or any(
        type(value) is not bool or value for value in authority.values()
    ):
        raise Mixed64ScorerValidityRankingPolicyVerificationError(
            "score/validity authority must remain exact false"
        )
    _verify_executor_source()
    return {
        "schema_id": (
            "betelgeuze.engine_v2_mixed64_scorer_validity_ranking_policy_verification/1.0.0"
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
    except Mixed64ScorerValidityRankingPolicyVerificationError as exc:
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
