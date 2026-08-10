"""Dependency-free policy for synthetic mixed64 scoring and validity."""

from __future__ import annotations

import hashlib
import json
from typing import Final


MIXED64_SCORER_VALIDITY_RANKING_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scorer_validity_ranking_v3/1.0.0"
)
MIXED64_SCORER_VALIDITY_RANKING_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scorer_validity_ranking_policy/1.0.0"
)
MIXED64_SCORER_VALIDITY_RANKING_RECORD_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scorer_validity_ranking_record/1.0.0"
)
MIXED64_SCORER_VALIDITY_RANKING_BATCH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_scorer_validity_ranking_batch/1.0.0"
)
MIXED64_SCORER_VALIDITY_RANKING_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_fixed64_scorer_v1_validity_stable_rank/1.0.0"
)
BOUND_V7_POST_ADMISSION_POLICY_SHA256: Final = (
    "b23d517b1b5d477129670c70fd9894219f14eb5f7bdb4ab06805ff0243e93beb"
)
FROZEN_SCORER_V1_CONFIG_SHA256: Final = (
    "f6592bb681ae1dfad2700291013e04a239c5961687386582ac7c009c5a7de783"
)
FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256: Final = (
    "3e1279f7426288224a1377e9021cc07c3a62115a3ac38534a70871fb8911415f"
)
FROZEN_VDW_CONTACT_POLICY_SHA256: Final = (
    "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
)
SCORER_V1_TERM_NAMES: Final = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
)

UPSTREAM_NOT_SCORED_STATUS: Final = "upstream_not_scored"
TYPED_SCORER_FAILURE_STATUS: Final = "typed_scorer_v1_failure"
TYPED_VALIDITY_FAILURE_STATUS: Final = "typed_pose_validity_failure"
SCORED_VALIDITY_INCOMPLETE_STATUS: Final = "scored_pose_validity_incomplete"
SCORED_POSE_VALID_STATUS: Final = "scored_pose_valid"
SCORED_POSE_INVALID_STATUS: Final = "scored_pose_invalid"
TYPED_SCORER_FAILURE_CODE: Final = "typed_scorer_v1_failure"
TYPED_VALIDITY_FAILURE_CODE: Final = "typed_pose_validity_failure"
VALIDITY_INCOMPLETE_CODE: Final = "pose_validity_incomplete"


def frozen_mixed64_scorer_validity_ranking_policy() -> dict[str, object]:
    return {
        "schema_id": MIXED64_SCORER_VALIDITY_RANKING_POLICY_SCHEMA_ID,
        "component_id": MIXED64_SCORER_VALIDITY_RANKING_COMPONENT_ID,
        "profile_id": MIXED64_SCORER_VALIDITY_RANKING_PROFILE_ID,
        "v7_post_admission_policy_sha256": (
            BOUND_V7_POST_ADMISSION_POLICY_SHA256
        ),
        "candidate_denominator": 64,
        "scoring": {
            "scorer": "ChemistryPoseScorerV1",
            "backend": "python_reference",
            "config_fingerprint_sha256": FROZEN_SCORER_V1_CONFIG_SHA256,
            "backend_options_fingerprint_sha256": (
                FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256
            ),
            "maximum_batch_size": 64,
            "accepted_post_admission_only": True,
            "one_batch_call_when_nonempty": True,
            "one_outcome_per_accepted_slot": True,
            "result_dependent_retry_allowed": False,
            "implementation_source_binding": (
                "stable_file_sha256_before_and_after_batch"
            ),
            "term_names": list(SCORER_V1_TERM_NAMES),
            "complete_terms_receipt_required": True,
            "total_score_rederived_from_terms": True,
            "direction": "minimize",
        },
        "validity": {
            "evaluator": "ElementAwarePoseValidityContext.evaluate",
            "context_source": "exact_scorer_authority",
            "contact_policy_fingerprint_sha256": (
                FROZEN_VDW_CONTACT_POLICY_SHA256
            ),
            "one_call_per_successfully_scored_slot": True,
            "result_dependent_retry_allowed": False,
            "complete_result_preserved": True,
            "incomplete_result_preserved_as_typed_status": True,
            "implementation_source_binding": (
                "contact_validity_and_base_validity_stable_file_sha256"
            ),
        },
        "ranking": {
            "primary_eligibility": "complete_scorer_v1_terms",
            "primary_includes_pose_invalid": True,
            "primary_includes_validity_unavailable": True,
            "valid_only_eligibility": "complete_pose_validity_true",
            "order": [
                "total_score_ascending",
                "slot_index_ascending",
                "result_proposal_sha256_ascending",
            ],
            "top_k": 5,
        },
        "failure_semantics": {
            "upstream_nonaccepted_scored": False,
            "typed_scoring_failure_preserved": True,
            "typed_validity_failure_preserves_score": True,
            "validity_incomplete_preserves_result": True,
            "failed_slot_retried": False,
            "slot_reallocation_allowed": False,
            "failed_or_rejected_slot_deleted": False,
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
            "github_actions_production_authority_allowed": False,
            "test_double_production_authority_allowed": False,
        },
        "status": "synthetic_fixture_execution_only",
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_mixed64_scorer_validity_ranking_policy())
).hexdigest()


__all__ = [
    "BOUND_V7_POST_ADMISSION_POLICY_SHA256",
    "FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256",
    "FROZEN_SCORER_V1_CONFIG_SHA256",
    "FROZEN_VDW_CONTACT_POLICY_SHA256",
    "MIXED64_SCORER_VALIDITY_RANKING_BATCH_SCHEMA_ID",
    "MIXED64_SCORER_VALIDITY_RANKING_COMPONENT_ID",
    "MIXED64_SCORER_VALIDITY_RANKING_POLICY_SCHEMA_ID",
    "MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256",
    "MIXED64_SCORER_VALIDITY_RANKING_PROFILE_ID",
    "MIXED64_SCORER_VALIDITY_RANKING_RECORD_SCHEMA_ID",
    "SCORER_V1_TERM_NAMES",
    "SCORED_POSE_INVALID_STATUS",
    "SCORED_POSE_VALID_STATUS",
    "SCORED_VALIDITY_INCOMPLETE_STATUS",
    "TYPED_SCORER_FAILURE_CODE",
    "TYPED_SCORER_FAILURE_STATUS",
    "TYPED_VALIDITY_FAILURE_CODE",
    "TYPED_VALIDITY_FAILURE_STATUS",
    "UPSTREAM_NOT_SCORED_STATUS",
    "VALIDITY_INCOMPLETE_CODE",
    "frozen_mixed64_scorer_validity_ranking_policy",
]
