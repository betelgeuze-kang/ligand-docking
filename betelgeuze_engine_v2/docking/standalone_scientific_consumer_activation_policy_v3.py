"""Dependency-free policy for exact synthetic-D0 consumer activation."""

from __future__ import annotations

import hashlib
import json
from typing import Final

from .standalone_scientific_core_policy_v3 import (
    BOUND_REQUEST_SHA256,
    STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256,
    STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID,
)


STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_standalone_scientific_consumer_activation_policy/1.0.0"
)
STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_standalone_scientific_consumer_activation_v3/1.0.0"
)
STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_SCOPE: Final = (
    "exact_repository_synthetic_d0_only"
)


def frozen_standalone_scientific_consumer_activation_policy() -> dict[str, object]:
    """Return the exact, claim-blocked consumer routing contract."""

    return {
        "schema_id": (
            STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SCHEMA_ID
        ),
        "component_id": STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_COMPONENT_ID,
        "activation_scope": STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_SCOPE,
        "bound_request_sha256": BOUND_REQUEST_SHA256,
        "bound_scientific_core_policy_sha256": (
            STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256
        ),
        "bound_scientific_core_receipt_schema_id": (
            STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID
        ),
        "candidate_denominator": 64,
        "top_k": 5,
        "surfaces": {
            "canonical_pipeline": "DockingPipeline.run",
            "cli": "betelgeuze-dock dock",
            "python_api": "StandaloneDockingPythonApi.run",
            "diagnostic_benchmark": "StandaloneDiagnosticBenchmarkAdapter.run",
            "product_shadow": "StandaloneProductShadowAdapter.run",
        },
        "routing_contract": {
            "canonical_pipeline_calls_exact_scientific_executor_once": True,
            "consumer_invocation_calls_no_argument_pipeline_once": True,
            "consumer_receipt_embedded_unmodified": True,
            "cli_serializes_exact_core_receipt": True,
            "cli_verify_rederives_scoring_validity_and_ranks": True,
            "benchmark_scope_is_repository_synthetic_d0": True,
            "product_shadow_evidence_display_only": True,
            "operator_second_opinion_only": True,
            "rank_or_selection_rewrite_allowed": False,
            "result_dependent_retry_allowed": False,
            "external_network_or_reservation_call_allowed": False,
        },
        "authority": {
            "reservation_allowed": False,
            "molecular_cohort_execution_authorized": False,
            "historical_ab_authorized": False,
            "fresh_holdout_authorized": False,
            "product_execution_authorized": False,
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


STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_standalone_scientific_consumer_activation_policy())
).hexdigest()


__all__ = [
    "STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_COMPONENT_ID",
    "STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SCHEMA_ID",
    "STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_POLICY_SHA256",
    "STANDALONE_SCIENTIFIC_CONSUMER_ACTIVATION_SCOPE",
    "frozen_standalone_scientific_consumer_activation_policy",
]
