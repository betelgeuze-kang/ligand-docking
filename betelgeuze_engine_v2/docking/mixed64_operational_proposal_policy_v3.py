"""Dependency-free frozen policy for mixed64 operational proposal v3."""

from __future__ import annotations

import hashlib
import json
from typing import Final


MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_mixed64_operational_proposal_v3/1.0.0"
)
MIXED64_OPERATIONAL_PROPOSAL_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_operational_proposal_policy/1.0.0"
)
MIXED64_OPERATIONAL_PROPOSAL_RECORD_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_operational_proposal_record/1.0.0"
)
MIXED64_OPERATIONAL_PROPOSAL_BATCH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_operational_proposal_batch/1.0.0"
)
MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_source_identity_bound_mixed64_operational_proposal/1.0.0"
)
DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_docking_proposal/3.0.0"
)
REQUIRED_PROPOSAL_NUMERIC_POLICY_ID: Final = (
    "betelgeuze.engine_v2_proposal_numeric_identity/1.0.0"
)
BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256: Final = (
    "ef78d3655743c40c5c7fe8524742c178b2f6a6c4120bef445288c056d59d6648"
)

MATERIALIZED_STATUS: Final = "materialized"
TYPED_MATERIALIZATION_FAILURE_STATUS: Final = "typed_materialization_failure"
UPSTREAM_NOT_MATERIALIZED_STATUS: Final = "upstream_not_materialized"
SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL: Final = (
    "source_proposal_identity_not_operational"
)
SOURCE_OPERATIONAL_COORDINATE_CROSS_WIRED: Final = (
    "source_operational_coordinate_cross_wired"
)
SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED: Final = (
    "source_operational_proposal_cross_wired"
)
PLACEMENT_TRANSFORM_CROSS_WIRED: Final = "placement_transform_cross_wired"
UNSUPPORTED_PLACEMENT_RECEIPT: Final = "unsupported_placement_receipt"


def frozen_mixed64_operational_proposal_policy() -> dict[str, object]:
    return {
        "schema_id": MIXED64_OPERATIONAL_PROPOSAL_POLICY_SCHEMA_ID,
        "component_id": MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID,
        "profile_id": MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID,
        "geometric_admission_policy_sha256": (
            BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256
        ),
        "candidate_denominator": 64,
        "admission_live_integrity": {
            "recursive_preflight_required": True,
            "recursive_postflight_required": True,
            "recursive_finalization_check_required": True,
            "operational_output_recursive_finalization_check_required": True,
        },
        "source_identity": {
            "required_schema_id": DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID,
            "required_numeric_policy_id": REQUIRED_PROPOSAL_NUMERIC_POLICY_ID,
            "required_numeric_dtype": "float64",
            "canonical_payload_rederived": True,
            "source_coordinate_rederived": True,
            "unsupported_identity_typed_failure": (
                SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL
            ),
        },
        "transformed_identity": {
            "placement_quaternion_reused": True,
            "placement_translation_reused": True,
            "source_operational_identity_preserved_separately": True,
            "passthrough_source_transform_preserved": True,
            "row_vector_rotation_composition": (
                "placement_rotation_matrix_multiply_source_rotation"
            ),
            "row_vector_translation_composition": (
                "source_translation_multiply_placement_rotation_transpose_plus_placement_translation"
            ),
            "torsion_state_preserved_from_source": True,
            "problem_and_search_identity_preserved_from_source": True,
            "operational_proposal_index_is_fixed64_slot": True,
            "source_dependent_result_independent_seed": True,
        },
        "failure_semantics": {
            "upstream_nonaccepted_materialized": False,
            "typed_materialization_failure_preserved": True,
            "only_declared_domain_failures_are_typed": True,
            "unexpected_runtime_failure_typed": False,
            "slot_reallocation_allowed": False,
        },
        "authority": {
            "reservation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_ab_authorized": False,
            "fresh_holdout_authorized": False,
            "product_mutation_authorized": False,
            "stage0_admission_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "github_actions_production_authority_allowed": False,
            "test_double_production_authority_allowed": False,
        },
        "status": "synthetic_identity_materialization_only",
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_mixed64_operational_proposal_policy())
).hexdigest()


__all__ = [
    "BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256",
    "DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID",
    "MATERIALIZED_STATUS",
    "MIXED64_OPERATIONAL_PROPOSAL_BATCH_SCHEMA_ID",
    "MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID",
    "MIXED64_OPERATIONAL_PROPOSAL_POLICY_SCHEMA_ID",
    "MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256",
    "MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID",
    "MIXED64_OPERATIONAL_PROPOSAL_RECORD_SCHEMA_ID",
    "PLACEMENT_TRANSFORM_CROSS_WIRED",
    "REQUIRED_PROPOSAL_NUMERIC_POLICY_ID",
    "SOURCE_OPERATIONAL_COORDINATE_CROSS_WIRED",
    "SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED",
    "SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL",
    "TYPED_MATERIALIZATION_FAILURE_STATUS",
    "UNSUPPORTED_PLACEMENT_RECEIPT",
    "UPSTREAM_NOT_MATERIALIZED_STATUS",
    "frozen_mixed64_operational_proposal_policy",
]
