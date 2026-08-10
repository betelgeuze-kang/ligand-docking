"""Dependency-free policy for synthetic mixed64 V7 post-admission."""

from __future__ import annotations

import hashlib
import json
from typing import Final


MIXED64_V7_POST_ADMISSION_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_mixed64_v7_post_admission_v3/1.0.0"
)
MIXED64_V7_POST_ADMISSION_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_v7_post_admission_policy/1.0.0"
)
MIXED64_V7_POST_ADMISSION_RECORD_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_v7_post_admission_record/1.0.0"
)
MIXED64_V7_POST_ADMISSION_BATCH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_v7_post_admission_batch/1.0.0"
)
MIXED64_V7_POST_ADMISSION_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_fixed64_current_v7_then_post_geometric_admission/1.0.0"
)
BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256: Final = (
    "dcf594a97648abce918ddac4c45f7f88108d6db4981e03893e4a82638fded354"
)
V7_REFINEMENT_MAX_STEPS: Final = 24
V7_TORSION_ELIGIBLE_SLOT_INDICES: Final = tuple(range(24, 44))

POST_REFINEMENT_ACCEPTED_STATUS: Final = "post_refinement_accepted"
POST_REFINEMENT_REJECTED_STATUS: Final = "post_refinement_geometric_rejection"
TYPED_V7_REFINEMENT_FAILURE_STATUS: Final = "typed_v7_refinement_failure"
UPSTREAM_NOT_REFINED_STATUS: Final = "upstream_not_refined"
TYPED_V7_REFINEMENT_FAILURE_CODE: Final = "typed_v7_refinement_failure"


def frozen_mixed64_v7_post_admission_policy() -> dict[str, object]:
    return {
        "schema_id": MIXED64_V7_POST_ADMISSION_POLICY_SCHEMA_ID,
        "component_id": MIXED64_V7_POST_ADMISSION_COMPONENT_ID,
        "profile_id": MIXED64_V7_POST_ADMISSION_PROFILE_ID,
        "operational_proposal_policy_sha256": (
            BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256
        ),
        "candidate_denominator": 64,
        "refinement": {
            "refiner": "InteractionAwareTorsionContactEnsembleRefinerV7",
            "max_steps": V7_REFINEMENT_MAX_STEPS,
            "torsion_eligible_slot_indices": list(
                V7_TORSION_ELIGIBLE_SLOT_INDICES
            ),
            "implementation_source_binding": (
                "stable_file_sha256_before_and_after_batch"
            ),
            "problem_and_search_space_identity_exact_match_required": True,
            "geometric_context_exact_match_required": True,
            "preexisting_refiner_receipts_allowed": False,
            "one_refinement_attempt_per_materialized_slot": True,
            "result_dependent_retry_allowed": False,
        },
        "post_refinement_geometric_admission": {
            "traversal": (
                "full_cartesian_ligand_index_major_receptor_index_minor"
            ),
            "hard_rejection_metric": "minimum_vdw_ratio",
            "hard_rejection_operator": "strictly_less_than",
            "hard_rejection_threshold_binary64_hex": (0.55).hex(),
            "hard_rejection_code": (
                "severe_receptor_penetration_min_vdw_ratio"
            ),
            "maximum_batch_exact_pair_evaluations": 16_777_216,
            "pair_bound_checked_before_refinement": True,
        },
        "failure_semantics": {
            "upstream_nonmaterialized_refined": False,
            "typed_refinement_failure_preserved": True,
            "failed_slot_retried": False,
            "slot_reallocation_allowed": False,
            "post_rejection_deleted": False,
        },
        "authority": {
            "reservation_allowed": False,
            "molecular_cohort_execution_authorized": False,
            "historical_ab_authorized": False,
            "fresh_holdout_authorized": False,
            "product_mutation_authorized": False,
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


MIXED64_V7_POST_ADMISSION_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_mixed64_v7_post_admission_policy())
).hexdigest()


__all__ = [
    "BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256",
    "MIXED64_V7_POST_ADMISSION_BATCH_SCHEMA_ID",
    "MIXED64_V7_POST_ADMISSION_COMPONENT_ID",
    "MIXED64_V7_POST_ADMISSION_POLICY_SCHEMA_ID",
    "MIXED64_V7_POST_ADMISSION_POLICY_SHA256",
    "MIXED64_V7_POST_ADMISSION_PROFILE_ID",
    "MIXED64_V7_POST_ADMISSION_RECORD_SCHEMA_ID",
    "POST_REFINEMENT_ACCEPTED_STATUS",
    "POST_REFINEMENT_REJECTED_STATUS",
    "TYPED_V7_REFINEMENT_FAILURE_CODE",
    "TYPED_V7_REFINEMENT_FAILURE_STATUS",
    "UPSTREAM_NOT_REFINED_STATUS",
    "V7_REFINEMENT_MAX_STEPS",
    "V7_TORSION_ELIGIBLE_SLOT_INDICES",
    "frozen_mixed64_v7_post_admission_policy",
]
