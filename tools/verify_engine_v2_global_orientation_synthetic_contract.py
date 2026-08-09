#!/usr/bin/env python3
"""Verify the synthetic-only Engine V2 global-orientation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_ID = "betelgeuze.engine_v2_global_orientation_synthetic_contract/2.0.0"
GENERATOR_ID = "deterministic_surface_aware_rigid_v2"
GEODESIC_DUPLICATE_THRESHOLD_RADIANS = 1.0e-10
EXPECTED_SOURCE_SEED_BINDING_FIELDS = (
    "source_receipt_sha256",
    "ligand_input_sha256",
    "pocket_center_binary64_hex",
    "pocket_normal_binary64_hex",
    "profile_id",
)
EXPECTED_COVERAGE_STATISTIC_FIELDS = (
    "requested_orientation_count",
    "raw_sequence_count",
    "accepted_sequence_count",
    "duplicate_orientation_count",
    "geodesic_duplicate_tolerance_radians_binary64_hex",
    "minimum_pairwise_geodesic_distance_radians_binary64_hex",
    "mean_nearest_neighbor_geodesic_distance_radians_binary64_hex",
    "maximum_nearest_neighbor_geodesic_distance_radians_binary64_hex",
)
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
        "orientation_receipt",
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
        "index_stable_orientation_sequence_required",
        "native_pose_input_allowed",
        "orientation_count_prefix_invariant_required",
        "receptor_surface_prefilter_allowed",
        "score_feedback_input_allowed",
        "source_dependent_seed_required",
        "source_rederivation_evidence_required",
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
        "index_stable_orientation_sequence_required",
        "orientation_count_prefix_invariant_required",
        "receptor_surface_prefilter_allowed",
        "source_dependent_seed_required",
        "source_rederivation_evidence_required",
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

    orientation_receipt = _mapping(
        contract.get("orientation_receipt"),
        name="orientation_receipt",
    )
    if set(orientation_receipt) != {
        "accepted_sequence_indices_required",
        "canonical_quaternion_binary64_hex_required",
        "coverage_statistic_fields",
        "coverage_statistics_required",
        "duplicate_statistics_required",
        "geodesic_duplicate_threshold_radians_binary64_hex",
        "quaternion_sign_canonicalization_required",
        "raw_sequence_indices_required",
        "source_seed_binding_fields",
        "source_seed_sha256_required",
    }:
        raise GlobalOrientationSyntheticContractError(
            "orientation receipt key set is invalid"
        )
    for required_true in (
        "accepted_sequence_indices_required",
        "canonical_quaternion_binary64_hex_required",
        "coverage_statistics_required",
        "duplicate_statistics_required",
        "quaternion_sign_canonicalization_required",
        "raw_sequence_indices_required",
        "source_seed_sha256_required",
    ):
        if orientation_receipt.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )
    if tuple(orientation_receipt.get("source_seed_binding_fields", ())) != (
        EXPECTED_SOURCE_SEED_BINDING_FIELDS
    ):
        raise GlobalOrientationSyntheticContractError(
            "source seed binding fields drifted"
        )
    if tuple(orientation_receipt.get("coverage_statistic_fields", ())) != (
        EXPECTED_COVERAGE_STATISTIC_FIELDS
    ):
        raise GlobalOrientationSyntheticContractError(
            "coverage statistic fields drifted"
        )
    encoded_threshold = orientation_receipt.get(
        "geodesic_duplicate_threshold_radians_binary64_hex"
    )
    if type(encoded_threshold) is not str:
        raise GlobalOrientationSyntheticContractError(
            "geodesic duplicate threshold must be binary64 hex"
        )
    try:
        observed_threshold = float.fromhex(encoded_threshold)
    except ValueError as exc:
        raise GlobalOrientationSyntheticContractError(
            "geodesic duplicate threshold must be binary64 hex"
        ) from exc
    if observed_threshold != GEODESIC_DUPLICATE_THRESHOLD_RADIANS:
        raise GlobalOrientationSyntheticContractError(
            "geodesic duplicate threshold drifted"
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
        "full_observation_rederivation_required",
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
        "full_observation_rederivation_required",
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
