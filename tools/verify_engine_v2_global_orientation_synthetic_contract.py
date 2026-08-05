#!/usr/bin/env python3
"""Verify the synthetic-only Engine V2 global-orientation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_ID = "betelgeuze.engine_v2_global_orientation_synthetic_contract/1.0.0"
GENERATOR_ID = "deterministic_surface_aware_rigid_v1"
EXPECTED_FAILURE_CLASSES = (
    "success",
    "proposal_failure",
    "validity_failure",
    "ranking_failure",
)
FORBIDDEN_TRUE_AUTHORITY_KEYS = (
    "customer_pose_emission_authorized",
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "product_execution_authorized",
    "profile_promotion_authority",
    "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
)


class GlobalOrientationSyntheticContractError(ValueError):
    """Raised when the synthetic global-orientation contract fails closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise GlobalOrientationSyntheticContractError(f"{name} must be an object")
    return value


def load_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationSyntheticContractError(
            f"contract is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GlobalOrientationSyntheticContractError(
            "contract must be a JSON object"
        )
    return payload


def verify_contract(contract: Mapping[str, Any]) -> str:
    expected_keys = {
        "algorithm",
        "authority",
        "contract_sha256",
        "metrics",
        "schema_id",
        "status",
    }
    if set(contract) != expected_keys:
        raise GlobalOrientationSyntheticContractError(
            "contract key set is invalid"
        )
    if contract.get("schema_id") != SCHEMA_ID:
        raise GlobalOrientationSyntheticContractError(
            "contract schema is invalid"
        )
    if contract.get("status") != "implemented_synthetic_validation_only":
        raise GlobalOrientationSyntheticContractError(
            "synthetic-only status drifted"
        )
    observed_hash = contract.get("contract_sha256")
    projection = dict(contract)
    projection.pop("contract_sha256", None)
    expected_hash = _sha256(projection)
    if observed_hash != expected_hash:
        raise GlobalOrientationSyntheticContractError(
            "contract self-hash is invalid"
        )

    algorithm = _mapping(contract.get("algorithm"), name="algorithm")
    if set(algorithm) != {
        "candidate_denominator_failure_complete",
        "generator_id",
        "native_pose_input_allowed",
        "receptor_surface_prefilter_allowed",
        "score_feedback_input_allowed",
        "synthetic_contract_only",
    }:
        raise GlobalOrientationSyntheticContractError(
            "algorithm key set is invalid"
        )
    if algorithm.get("generator_id") != GENERATOR_ID:
        raise GlobalOrientationSyntheticContractError(
            "generator identity drifted"
        )
    for required_true in (
        "candidate_denominator_failure_complete",
        "receptor_surface_prefilter_allowed",
        "synthetic_contract_only",
    ):
        if algorithm.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )
    for forbidden_input in (
        "native_pose_input_allowed",
        "score_feedback_input_allowed",
    ):
        if algorithm.get(forbidden_input) is not False:
            raise GlobalOrientationSyntheticContractError(
                f"{forbidden_input} must remain false"
            )

    authority = _mapping(contract.get("authority"), name="authority")
    if set(authority) != set(FORBIDDEN_TRUE_AUTHORITY_KEYS):
        raise GlobalOrientationSyntheticContractError(
            "authority key set is invalid"
        )
    for key in FORBIDDEN_TRUE_AUTHORITY_KEYS:
        if authority.get(key) is not False:
            raise GlobalOrientationSyntheticContractError(
                f"{key} must remain false"
            )

    metrics = _mapping(contract.get("metrics"), name="metrics")
    if set(metrics) != {
        "failure_classes",
        "proposal_oracle_and_selection_separated",
        "selection_regret_reported",
        "top_k_ranked_oracle_reported",
    }:
        raise GlobalOrientationSyntheticContractError(
            "metrics key set is invalid"
        )
    if tuple(metrics.get("failure_classes", ())) != EXPECTED_FAILURE_CLASSES:
        raise GlobalOrientationSyntheticContractError(
            "failure class order drifted"
        )
    for required_true in (
        "proposal_oracle_and_selection_separated",
        "selection_regret_reported",
        "top_k_ranked_oracle_reported",
    ):
        if metrics.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )
    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/engine_v2_global_orientation_synthetic_contract.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    print(verify_contract(load_contract(arguments.contract)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
