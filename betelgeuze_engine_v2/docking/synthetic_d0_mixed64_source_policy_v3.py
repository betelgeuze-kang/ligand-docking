"""Dependency-free policy for the repository synthetic-D0 mixed64 adapter."""

from __future__ import annotations

import hashlib
import json
from typing import Final


SYNTHETIC_D0_MIXED64_SOURCE_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_mixed64_source_v3/1.0.0"
)
SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_mixed64_source_policy/1.0.0"
)
SYNTHETIC_D0_MIXED64_SOURCE_RECEIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_mixed64_source_receipt/1.0.0"
)
SYNTHETIC_D0_MIXED64_SOURCE_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_repository_synthetic_d0_fixed64_source/1.0.0"
)
BOUND_FIXTURE_ID: Final = (
    "betelgeuze.engine_v2.synthetic_d0_standalone_fixture/1.0.0"
)
BOUND_FIXTURE_MANIFEST_SHA256: Final = (
    "12919355ac208aaa11d9560ebc95db05a30a5d4379bf741f89e81482d131693b"
)
BOUND_REQUEST_SHA256: Final = (
    "bbf826bbdc30818f27c95f04763696bd09b7aa3e9cbd75c5d1597442d8129629"
)
BOUND_PIPELINE_PROFILE_RECEIPT_SHA256: Final = (
    "81c7b64b9ca9cc61933bfb8de61553a6a0ebcb655a9ec28de63f2a475f61fca9"
)
BOUND_GUIDED_POLICY_SHA256: Final = (
    "2974e9ba80479cccc97dce1b51567e8e7309e7f89c983401c9a8966a3d08633f"
)
BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256: Final = (
    "388cd22cbd16f34006041b87d0e49fccdb8e1acb33891d98f85cc74ae42756ed"
)
V7_CONTROL_SOURCE_INDICES: Final = tuple(range(24))
RETAINED_SOURCE_INDICES: Final = (36, 45, 54, 63)
PARTIAL_CHARGE_SITE_THRESHOLD: Final = 0.25


def frozen_synthetic_d0_mixed64_source_policy() -> dict[str, object]:
    return {
        "schema_id": SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SCHEMA_ID,
        "component_id": SYNTHETIC_D0_MIXED64_SOURCE_COMPONENT_ID,
        "profile_id": SYNTHETIC_D0_MIXED64_SOURCE_PROFILE_ID,
        "fixture": {
            "fixture_id": BOUND_FIXTURE_ID,
            "manifest_sha256": BOUND_FIXTURE_MANIFEST_SHA256,
            "request_sha256": BOUND_REQUEST_SHA256,
            "pipeline_profile_receipt_sha256": (
                BOUND_PIPELINE_PROFILE_RECEIPT_SHA256
            ),
            "candidate_denominator": 64,
            "seed": 4301,
            "repository_manifest_required": True,
        },
        "source_generation": {
            "generator": "generate_guided_docking_proposals",
            "guided_policy_sha256": BOUND_GUIDED_POLICY_SHA256,
            "one_call": True,
            "result_dependent_retry_allowed": False,
            "v7_control_source_indices": list(V7_CONTROL_SOURCE_INDICES),
            "retained_source_indices": list(RETAINED_SOURCE_INDICES),
            "true_conformer_generation_allowed": False,
            "true_conformer_sources": [],
        },
        "feature_extraction": {
            "donor_acceptor_source": "authenticated_guided_context",
            "donor_attached_hydrogen_required": True,
            "charge_source": "prepared_atom_partial_charge",
            "partial_charge_site_threshold_binary64_hex": (
                PARTIAL_CHARGE_SITE_THRESHOLD.hex()
            ),
            "aromatic_source": "authenticated_guided_context",
            "ligand_shape_atoms": "all_prepared_heavy_atoms",
            "pocket_shape_atoms": "all_authenticated_heavy_receptor_atoms",
            "pocket_normal": "pocket_center_minus_receptor_centroid_then_shape_axis",
            "feature_geometry_receipt_required": True,
            "missing_feature_remains_typed_allocation_failure": True,
            "result_fields_consumed": False,
        },
        "receipt_binding": {
            "exact_prepared_source_receipt_required": True,
            "proposal_identity_payload_required": True,
            "proposal_lineage_payload_required": True,
            "guided_receipt_required": True,
            "allocation_receipt_required": True,
            "source_bundle_receipt_required": True,
            "adapter_source_stable_before_and_after": True,
            "scientific_pipeline_policy_sha256": (
                BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256
            ),
        },
        "consumer_contract": {
            "standalone_binding_ready": True,
            "standalone_activation_authorized": False,
            "benchmark_activation_authorized": False,
            "api_activation_authorized": False,
            "product_shadow_activation_authorized": False,
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
        "status": "repository_synthetic_d0_source_adapter_only",
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256: Final = hashlib.sha256(
    _canonical_bytes(frozen_synthetic_d0_mixed64_source_policy())
).hexdigest()


__all__ = [
    "BOUND_FIXTURE_ID",
    "BOUND_FIXTURE_MANIFEST_SHA256",
    "BOUND_GUIDED_POLICY_SHA256",
    "BOUND_PIPELINE_PROFILE_RECEIPT_SHA256",
    "BOUND_REQUEST_SHA256",
    "BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256",
    "PARTIAL_CHARGE_SITE_THRESHOLD",
    "RETAINED_SOURCE_INDICES",
    "SYNTHETIC_D0_MIXED64_SOURCE_COMPONENT_ID",
    "SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SCHEMA_ID",
    "SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256",
    "SYNTHETIC_D0_MIXED64_SOURCE_PROFILE_ID",
    "SYNTHETIC_D0_MIXED64_SOURCE_RECEIPT_SCHEMA_ID",
    "V7_CONTROL_SOURCE_INDICES",
    "frozen_synthetic_d0_mixed64_source_policy",
]
