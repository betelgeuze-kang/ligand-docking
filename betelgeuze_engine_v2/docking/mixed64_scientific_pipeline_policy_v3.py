"""Dependency-free policy for the synthetic fixed64 scientific pipeline."""

from __future__ import annotations

import hashlib
import json
from typing import Final


MIXED64_SCIENTIFIC_PIPELINE_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scientific_pipeline_v3/1.0.0"
)
MIXED64_SCIENTIFIC_PIPELINE_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scientific_pipeline_policy/1.0.0"
)
MIXED64_SCIENTIFIC_PIPELINE_RECEIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scientific_pipeline_receipt/1.0.0"
)
MIXED64_SCIENTIFIC_PIPELINE_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_fixed64_scientific_core_v3/1.0.0"
)

BOUND_PRODUCER_POLICY_SHA256: Final = (
    "a5cc354ef227d6d187d565dfbc6d0cfc631218e201198ed5b8a61b43baf6ad6d"
)
BOUND_GEOMETRIC_ADMISSION_POLICY_SHA256: Final = (
    "0d3203daeb245d29fe4b03a73204d8cddb25ce84b310b008d61729d89659a2c6"
)
BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256: Final = (
    "dcf594a97648abce918ddac4c45f7f88108d6db4981e03893e4a82638fded354"
)
BOUND_V7_POST_ADMISSION_POLICY_SHA256: Final = (
    "b23d517b1b5d477129670c70fd9894219f14eb5f7bdb4ab06805ff0243e93beb"
)
BOUND_SCORER_VALIDITY_RANKING_POLICY_SHA256: Final = (
    "dfaec532a6eacc5f268f69e98788a7c63620659063cf0719f8d865c0817568eb"
)


def frozen_mixed64_scientific_pipeline_policy() -> dict[str, object]:
    return {
        "schema_id": MIXED64_SCIENTIFIC_PIPELINE_POLICY_SCHEMA_ID,
        "component_id": MIXED64_SCIENTIFIC_PIPELINE_COMPONENT_ID,
        "profile_id": MIXED64_SCIENTIFIC_PIPELINE_PROFILE_ID,
        "candidate_denominator": 64,
        "stage_policy_sha256s": {
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
        },
        "execution_order": [
            "fixed64_producer",
            "pre_refinement_geometric_admission",
            "operational_proposal_materialization",
            "current_v7_post_admission",
            "scorer_v1_validity_stable_ranking",
        ],
        "execution_semantics": {
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
        },
        "failure_semantics": {
            "one_record_per_slot_required": True,
            "failed_or_rejected_slot_deleted": False,
            "failed_slot_reallocated": False,
            "typed_failures_preserved": True,
            "primary_ranking_includes_pose_invalid": True,
            "valid_only_ranking_preserved": True,
        },
        "consumer_contract": {
            "canonical_scientific_core_receipt": True,
            "standalone_consumer_activation_authorized": False,
            "benchmark_consumer_activation_authorized": False,
            "api_consumer_activation_authorized": False,
            "product_shadow_consumer_activation_authorized": False,
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
        "status": "synthetic_fixture_scientific_core_only",
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_mixed64_scientific_pipeline_policy())
).hexdigest()


__all__ = [
    "BOUND_GEOMETRIC_ADMISSION_POLICY_SHA256",
    "BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256",
    "BOUND_PRODUCER_POLICY_SHA256",
    "BOUND_SCORER_VALIDITY_RANKING_POLICY_SHA256",
    "BOUND_V7_POST_ADMISSION_POLICY_SHA256",
    "MIXED64_SCIENTIFIC_PIPELINE_COMPONENT_ID",
    "MIXED64_SCIENTIFIC_PIPELINE_POLICY_SCHEMA_ID",
    "MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256",
    "MIXED64_SCIENTIFIC_PIPELINE_PROFILE_ID",
    "MIXED64_SCIENTIFIC_PIPELINE_RECEIPT_SCHEMA_ID",
    "frozen_mixed64_scientific_pipeline_policy",
]
