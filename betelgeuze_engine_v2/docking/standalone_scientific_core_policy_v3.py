"""Dependency-free policy for the sealed synthetic standalone scientific core."""

from __future__ import annotations

import hashlib
import json
from typing import Final


STANDALONE_SCIENTIFIC_CORE_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_standalone_scientific_core_v3/1.0.0"
)
STANDALONE_SCIENTIFIC_CORE_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_standalone_scientific_core_policy/1.0.0"
)
STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_standalone_scientific_core_receipt/1.0.0"
)
STANDALONE_SCIENTIFIC_CORE_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_repository_synthetic_d0_fixed64_standalone_core/1.0.0"
)
BOUND_SOURCE_ADAPTER_POLICY_SHA256: Final = (
    "9270080d5f84ae0f9a3e8c2592632ab0c8ecbeb1d33b820a14a92c7cc9ea0e33"
)
BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256: Final = (
    "388cd22cbd16f34006041b87d0e49fccdb8e1acb33891d98f85cc74ae42756ed"
)
BOUND_REQUEST_SHA256: Final = (
    "bbf826bbdc30818f27c95f04763696bd09b7aa3e9cbd75c5d1597442d8129629"
)


def frozen_standalone_scientific_core_policy() -> dict[str, object]:
    return {
        "schema_id": STANDALONE_SCIENTIFIC_CORE_POLICY_SCHEMA_ID,
        "component_id": STANDALONE_SCIENTIFIC_CORE_COMPONENT_ID,
        "profile_id": STANDALONE_SCIENTIFIC_CORE_PROFILE_ID,
        "candidate_denominator": 64,
        "top_k": 5,
        "request_sha256": BOUND_REQUEST_SHA256,
        "bound_policy_sha256s": {
            "repository_synthetic_d0_source_adapter": (
                BOUND_SOURCE_ADAPTER_POLICY_SHA256
            ),
            "fixed64_scientific_pipeline": (
                BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256
            ),
        },
        "execution_order": [
            "repository_synthetic_d0_source_adapter",
            "current_v7_refiner_construction",
            "scorer_v1_construction",
            "fixed64_scientific_pipeline",
            "standalone_scientific_receipt",
        ],
        "execution_semantics": {
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
            "installed_source_sha256s_observed": True,
            "implementation_sources_stable_before_and_after": True,
        },
        "receipt_contract": {
            "source_adapter_receipt_embedded": True,
            "scientific_pipeline_receipt_embedded": True,
            "all_stage_receipt_sha256s_bound": True,
            "complete_scorer_v1_terms_preserved": True,
            "complete_pose_validity_preserved": True,
            "primary_and_valid_only_rank_preserved": True,
            "typed_failure_denominator_preserved": True,
            "request_and_fixture_admission_bound": True,
        },
        "consumer_contract": {
            "canonical_docking_pipeline_activation_authorized": True,
            "cli_activation_authorized": True,
            "api_activation_authorized": True,
            "benchmark_activation_authorized": True,
            "product_shadow_activation_authorized": True,
            "activation_scope": "exact_repository_synthetic_d0_only",
            "product_or_molecular_execution_authorized": False,
        },
        "authority": {
            "reservation_allowed": False,
            "molecular_cohort_execution_authorized": False,
            "historical_ab_authorized": False,
            "fresh_holdout_authorized": False,
            "product_mutation_authorized": False,
            "existing_rank_auto_change_authorized": False,
            "customer_pose_emission_authorized": False,
            "stage0_admission_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "hip_execution_authorized": False,
            "github_actions_production_authority_allowed": False,
            "test_double_production_authority_allowed": False,
        },
        "status": "repository_synthetic_d0_consumers_activated_claim_blocked",
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_standalone_scientific_core_policy())
).hexdigest()


__all__ = [
    "BOUND_REQUEST_SHA256",
    "BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256",
    "BOUND_SOURCE_ADAPTER_POLICY_SHA256",
    "STANDALONE_SCIENTIFIC_CORE_COMPONENT_ID",
    "STANDALONE_SCIENTIFIC_CORE_POLICY_SCHEMA_ID",
    "STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256",
    "STANDALONE_SCIENTIFIC_CORE_PROFILE_ID",
    "STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID",
    "frozen_standalone_scientific_core_policy",
]
