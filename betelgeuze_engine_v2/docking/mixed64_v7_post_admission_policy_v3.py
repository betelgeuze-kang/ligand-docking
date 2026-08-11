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
    "9535730901a27ab3009e7b6fff12e532dd5d995e8fa33a038f4d321593885de9"
)
BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256: Final = (
    "feb9c00eb71bb45fe07479c6f5b8e6faa171b9968fa4dbb2370e518c71290526"
)
V7_REFINEMENT_MAX_STEPS: Final = 24
V7_TORSION_ELIGIBLE_SLOT_INDICES: Final = tuple(range(24, 44))
POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO: Final = 0.55
POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS: Final = 16_777_216
MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES: Final = 256 * 1024 * 1024
MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES: Final = 4 * 1024
MAX_V7_IMPLEMENTATION_SOURCE_BYTES: Final = 8 * 1024 * 1024

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
        "receipt_integrity": {
            "maximum_canonical_bytes": (MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES),
            "sealed_snapshot_required": True,
            "recursive_live_integrity_required": True,
        },
        "operational_input_integrity": {
            "recursive_preflight_required": True,
            "recursive_postflight_required": True,
            "recursive_finalization_check_required": True,
            "operational_proposal_index_is_fixed64_slot": True,
        },
        "output_live_integrity": {
            "recursive_finalization_required": True,
            "recursive_downstream_verifier_available": True,
        },
        "refinement": {
            "refiner": "InteractionAwareTorsionContactEnsembleRefinerV7",
            "execution_backend": "python_reference",
            "execution_role": "independent_verifier_oracle_only",
            "max_steps": V7_REFINEMENT_MAX_STEPS,
            "torsion_eligible_slot_indices": list(V7_TORSION_ELIGIBLE_SLOT_INDICES),
            "implementation_source_binding": (
                "single_fd_nofollow_stable_file_sha256_before_after_and_finalization"
            ),
            "maximum_implementation_source_bytes": (
                MAX_V7_IMPLEMENTATION_SOURCE_BYTES
            ),
            "problem_and_search_space_identity_exact_match_required": True,
            "geometric_context_exact_match_required": True,
            "preexisting_refiner_receipts_allowed": False,
            "one_refinement_attempt_per_materialized_slot": True,
            "result_dependent_retry_allowed": False,
        },
        "post_refinement_geometric_admission": {
            "kernel_backend": "python_reference",
            "execution_role": "independent_verifier_oracle_only",
            "geometric_admission_v3_policy_sha256": (
                BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256
            ),
            "traversal": ("full_cartesian_ligand_index_major_receptor_index_minor"),
            "hard_rejection_metric": "minimum_vdw_ratio",
            "hard_rejection_operator": "strictly_less_than",
            "hard_rejection_threshold_binary64_hex": (
                POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
            ),
            "hard_rejection_code": ("severe_receptor_penetration_min_vdw_ratio"),
            "maximum_batch_exact_pair_evaluations": (
                POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS
            ),
            "pair_bound_checked_before_refinement": True,
        },
        "failure_semantics": {
            "upstream_nonmaterialized_refined": False,
            "typed_refinement_failure_preserved": True,
            "typed_refinement_failure_reason_preserved": True,
            "maximum_typed_failure_reason_utf8_bytes": (
                MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES
            ),
            "declared_typed_error": "TorsionContactRefinementError",
            "unexpected_runtime_failure_typed": False,
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
        "status": "synthetic_python_oracle_fixture_only",
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
    "BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256",
    "BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256",
    "MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES",
    "MAX_V7_IMPLEMENTATION_SOURCE_BYTES",
    "MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES",
    "MIXED64_V7_POST_ADMISSION_BATCH_SCHEMA_ID",
    "MIXED64_V7_POST_ADMISSION_COMPONENT_ID",
    "MIXED64_V7_POST_ADMISSION_POLICY_SCHEMA_ID",
    "MIXED64_V7_POST_ADMISSION_POLICY_SHA256",
    "MIXED64_V7_POST_ADMISSION_PROFILE_ID",
    "MIXED64_V7_POST_ADMISSION_RECORD_SCHEMA_ID",
    "POST_REFINEMENT_ACCEPTED_STATUS",
    "POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO",
    "POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS",
    "POST_REFINEMENT_REJECTED_STATUS",
    "TYPED_V7_REFINEMENT_FAILURE_CODE",
    "TYPED_V7_REFINEMENT_FAILURE_STATUS",
    "UPSTREAM_NOT_REFINED_STATUS",
    "V7_REFINEMENT_MAX_STEPS",
    "V7_TORSION_ELIGIBLE_SLOT_INDICES",
    "frozen_mixed64_v7_post_admission_policy",
]
