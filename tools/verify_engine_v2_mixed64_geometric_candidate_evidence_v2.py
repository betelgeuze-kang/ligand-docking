#!/usr/bin/env python3
"""Verify the frozen synthetic-only mixed64/geometric/evidence-v2 contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_ID = (
    "betelgeuze.engine_v2_mixed64_geometric_candidate_evidence_v2_contract/"
    "3.0.0"
)
STATUS = "implemented_synthetic_validation_only"
CANDIDATE_DENOMINATOR = 64
HARD_REJECTION_MINIMUM_VDW_RATIO = 0.55
EXPECTED_ALLOCATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_allocation/2.0.0"
)
EXPECTED_SLOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_slot/2.0.0"
)
EXPECTED_FEATURE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_"
    "feature_evidence/5.0.0"
)
EXPECTED_EXACT_V11_SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_exact_v11_source/2.0.0"
)
EXPECTED_V7_CONTROL_SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_v7_control_source/2.0.0"
)
EXPECTED_V7_CONTROL_SOURCE_NAMESPACE = "current_v7_source_proposal_index"
EXPECTED_LANE_RANGES = (
    ("pocket_centered_controls", 0, 7, 8),
    ("uniform_source_controls", 8, 23, 16),
    ("deterministic_independent_so3", 24, 35, 12),
    ("true_conformer_independent_so3", 36, 43, 8),
    ("ligand_donor_to_receptor_acceptor", 44, 47, 4),
    ("ligand_acceptor_to_receptor_donor", 48, 51, 4),
    ("complementary_charge", 52, 55, 4),
    ("aromatic_plane", 56, 57, 2),
    ("principal_axis_shape", 58, 59, 2),
    ("paired_retained_controls", 60, 63, 4),
)
EXPECTED_INTERACTION_LANE_SPLIT = {
    "complementary_charge": 4,
    "aromatic_plane": 2,
    "principal_axis_shape": 2,
}
EXPECTED_BATCH_BINDING_FIELDS = (
    "allocation_receipt_sha256",
    "allocation_profile_id",
    "allocation",
    "geometric_admission_batch_receipt_sha256",
    "geometric_admission_batch",
    "candidate_receipt_sha256s",
)
EXPECTED_CANDIDATE_BINDING_FIELDS = (
    "allocation_slot_receipt_sha256",
    "geometric_admission_decision_receipt_sha256",
    "proposal_execution_receipt_sha256",
    "source_proposal_sha256",
    "source_coordinate_sha256",
    "result_proposal_sha256",
    "result_coordinate_sha256",
    "scorer_v1_evidence_binding_sha256",
    "pose_validity_receipt_sha256",
    "refinement_receipt_binding_sha256",
)
EXPECTED_FEATURE_EVIDENCE_FIELDS = (
    "exact_v11_source_receipt_sha256",
    "exact_v11_source_evidence_receipt_sha256",
    "exact_v11_source",
    "prepared_ligand_topology_sha256",
    "prepared_receptor_topology_sha256",
    "feature_extractor_policy_sha256",
    "atomic_features",
    "v7_control_sources",
    "conformer_sources",
    "retained_sources",
)
EXPECTED_EXACT_V11_SOURCE_FIELDS = (
    "source_receipt_sha256",
    "proposal_sha256",
    "ligand_coordinate_sha256",
    "receptor_coordinate_sha256",
    "prepared_ligand_topology_sha256",
    "prepared_receptor_topology_sha256",
    "ligand_vdw_radii_sha256",
    "ligand_heavy_atom_mask_sha256",
    "receptor_vdw_radii_sha256",
)
EXPECTED_ATOMIC_FEATURE_FIELDS = (
    "kind",
    "atom_indices",
    "source_receipt_sha256",
    "geometry_receipt_sha256",
)
EXPECTED_CONFORMER_SOURCE_FIELDS = (
    "rank",
    "proposal_sha256",
    "coordinate_sha256",
    "source_receipt_sha256",
)
EXPECTED_RETAINED_SOURCE_FIELDS = (
    "source_namespace",
    "source_index",
    "proposal_sha256",
    "coordinate_sha256",
    "source_receipt_sha256",
)
EXPECTED_V7_CONTROL_SOURCE_FIELDS = (
    "source_namespace",
    "source_index",
    "proposal_mode",
    "proposal_sha256",
    "coordinate_sha256",
    "proposal_lineage_sha256",
    "source_receipt_sha256",
    "generation_parent_role",
)
EXPECTED_SLOT_GENERATION_PARENT_BINDING_FIELDS = (
    "selected_generation_parent_proposal_sha256",
    "selected_generation_parent_coordinate_sha256",
    "generation_parent_role",
)
EXPECTED_GENERATION_PARENT_ROLES = (
    "exact_passthrough_parent",
    "generator_input_parent",
)
EXPECTED_TRUE_CONFORMER_FAILURES = [
    {
        "failure_code": f"missing_true_conformer:{rank}",
        "rank": rank,
        "slot_index": slot_index,
    }
    for slot_index, rank in zip(
        range(36, 44),
        (2, 3, 4, 5, 6, 7, 8, 2),
        strict=True,
    )
]
EXPECTED_PROPOSAL_EXECUTION_BINDING_FIELDS = (
    "slot_index",
    "allocation_slot_receipt_sha256",
    "allocation_source_receipt_sha256s",
    "generation_parent_proposal_sha256",
    "generation_parent_coordinate_sha256",
    "source_proposal_sha256",
    "source_coordinate_sha256",
    "generation_input_receipt_sha256",
    "generator_config_sha256",
    "generator_implementation_source_sha256",
    "generator_component_id",
)
EXPECTED_ACTIVATION_EVIDENCE_BLOCKERS = (
    "uniform_source_control_lineage_not_rederived",
    "independent_so3_base_source_not_bound",
    "independent_so3_orientation_receipt_not_implemented",
    "single_anchor_placement_receipt_not_implemented",
    "proposal_generation_failure_receipt_not_implemented",
    "post_refinement_geometric_admission_not_implemented",
    "source_parent_payload_rederivation_not_implemented",
    "producer_attestation_not_implemented",
    "score_term_reexecution_not_implemented",
    "pose_validity_reexecution_not_implemented",
)
EXPECTED_DENOMINATOR_FAILURE_COMPLETENESS_SCOPE = (
    "allocation_and_supported_post_proposal_structural_stages_only"
)
EXPECTED_SCORER_SEARCH_PROVENANCE_FIELDS = (
    "search_row_sha256",
    "search_term_row_receipt_sha256",
    "source_search_result_receipt_sha256",
    "scorer_implementation_source_sha256",
    "scorer_v1_terms_receipt_sha256",
    "scorer_v1_terms",
)
EXPECTED_REFINEMENT_BINDING_FIELDS = (
    "source_proposal_sha256",
    "result_proposal_sha256",
    "source_coordinate_sha256",
    "result_coordinate_sha256",
    "refiner_config_sha256",
    "refiner_implementation_source_sha256",
    "source_receipt_sha256",
    "source_receipt",
)
EXPECTED_VALIDITY_CHECKS = frozenset(
    {
        "proper_rotation",
        "bond_lengths_preserved",
        "ligand_self_clash_free",
        "receptor_ligand_clash_free",
        "declared_chirality_preserved",
        "inside_declared_pocket",
        "element_vdw_ligand_overlap_free",
        "element_vdw_receptor_overlap_free",
    }
)
EXPECTED_VALIDITY_RECEIPT_BINDING_FIELDS = (
    "result_proposal_sha256",
    "coordinate_sha256",
    "validity_context_fingerprint_sha256",
    "validity_config_fingerprint_sha256",
    "evaluator_implementation_source_sha256",
)
EXPECTED_STRUCTURAL_RECEIPT_SCHEMA_IDS = (
    "betelgeuze.engine_v2_mixed64_proposal_execution_receipt_v2/1.0.0",
    "betelgeuze.engine_v2_pipeline_scorer_v1_evidence_binding_v2/1.0.0",
    "betelgeuze.engine_v2_pipeline_pose_validity_receipt_v2/1.0.0",
    "betelgeuze.engine_v2_pipeline_refinement_receipt_binding_v2/1.0.0",
    "betelgeuze.engine_v2_pipeline_refinement_source_receipt_identity_v2/1.0.0",
)
EXPECTED_REFINEMENT_SOURCE_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_pipeline_refinement_source_receipt_identity_v2/1.0.0"
)
EXPECTED_EXECUTION_FAILURE_STAGES = ("refinement", "scoring", "validity")
EXPECTED_EXECUTION_FAILURE_STAGE_SEMANTICS = [
    {
        "failure_stage": "refinement",
        "forbidden_evidence": [
            "result_proposal_sha256",
            "result_coordinate_sha256",
            "refinement_receipt",
            "scorer_v1_evidence",
            "pose_validity_receipt",
        ],
        "pose_validity_state": "unavailable",
        "primary_rank_eligible": False,
        "required_evidence": [
            "proposal_execution_receipt",
            "source_proposal_sha256",
            "source_coordinate_sha256",
        ],
    },
    {
        "failure_stage": "scoring",
        "forbidden_evidence": [
            "scorer_v1_evidence",
            "pose_validity_receipt",
        ],
        "pose_validity_state": "unavailable",
        "primary_rank_eligible": False,
        "required_evidence": [
            "proposal_execution_receipt",
            "source_proposal_sha256",
            "source_coordinate_sha256",
            "result_proposal_sha256",
            "result_coordinate_sha256",
            "refinement_receipt",
        ],
    },
    {
        "failure_stage": "validity",
        "forbidden_evidence": ["pose_validity_receipt"],
        "pose_validity_state": "unavailable",
        "primary_rank_eligible": True,
        "required_evidence": [
            "proposal_execution_receipt",
            "source_proposal_sha256",
            "source_coordinate_sha256",
            "result_proposal_sha256",
            "result_coordinate_sha256",
            "refinement_receipt",
            "scorer_v1_evidence",
        ],
    },
]
EXPECTED_FAILURE_STATUSES = (
    "allocation_typed_failure",
    "geometric_rejection",
    "typed_execution_failure",
)
EXPECTED_METRIC_FIELDS = (
    "ligand_atom_count",
    "receptor_atom_count",
    "exact_pair_count",
    "raw_minimum_distance_angstrom_binary64_hex",
    "minimum_vdw_surface_gap_angstrom_binary64_hex",
    "minimum_vdw_ratio_binary64_hex",
    "penetration_pair_count",
    "unique_ligand_penetration_atom_count",
    "unique_ligand_heavy_atom_penetration_count",
    "sphere_overlap_proxy_angstrom3_binary64_hex",
    "pocket_escape_angstrom_binary64_hex",
)
FORBIDDEN_TRUE_AUTHORITY_KEYS = (
    "customer_pose_emission_authorized",
    "existing_rank_auto_change_authorized",
    "fresh_holdout_execution_authorized",
    "historical_execution_authorized",
    "molecular_execution_authorized",
    "product_execution_authorized",
    "product_mutation_authorized",
    "profile_promotion_authority",
    "public_benchmark_execution_authorized",
    "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
)


class Mixed64GeometricCandidateEvidenceV2ContractError(ValueError):
    """Raised when the frozen synthetic-only contract fails closed."""


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
    if type(value) is not dict:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"{name} must be an object"
        )
    return value


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    name: str,
) -> None:
    if set(value) != expected:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"{name} key set is invalid"
        )


def _exact_sequence(
    value: object,
    expected: tuple[object, ...],
    *,
    name: str,
) -> None:
    if type(value) is not list or len(value) != len(expected):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"{name} drifted"
        )
    if any(
        type(observed) is not type(required) or observed != required
        for observed, required in zip(value, expected, strict=True)
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"{name} drifted"
        )


def _typed_json_equal(observed: object, expected: object) -> bool:
    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        observed_mapping = observed
        expected_mapping = expected
        assert isinstance(observed_mapping, dict)
        assert isinstance(expected_mapping, dict)
        return set(observed_mapping) == set(expected_mapping) and all(
            _typed_json_equal(observed_mapping[key], expected_mapping[key])
            for key in expected_mapping
        )
    if type(expected) is list:
        observed_list = observed
        expected_list = expected
        assert isinstance(observed_list, list)
        assert isinstance(expected_list, list)
        return len(observed_list) == len(expected_list) and all(
            _typed_json_equal(left, right)
            for left, right in zip(observed_list, expected_list, strict=True)
        )
    return bool(observed == expected)


def _exact_json_value(observed: object, expected: object, *, name: str) -> None:
    if not _typed_json_equal(observed, expected):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"{name} drifted"
        )


def _required_boolean(
    value: Mapping[str, Any],
    key: str,
    *,
    expected: bool,
) -> None:
    if type(value.get(key)) is not bool or value.get(key) is not expected:
        qualifier = "true" if expected else "false"
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"{key} must remain {qualifier}"
        )


def load_contract(path: Path) -> dict[str, Any]:
    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise Mixed64GeometricCandidateEvidenceV2ContractError(
                    f"contract contains duplicate JSON key: {key}"
                )
            observed[key] = value
        return observed

    def reject_nonfinite_constant(value: str) -> object:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"contract contains non-finite JSON constant: {value}"
        )

    try:
        text = path.read_bytes().decode("ascii")
        payload = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
    except Mixed64GeometricCandidateEvidenceV2ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            f"contract is not readable JSON: {exc}"
        ) from exc
    if type(payload) is not dict:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "contract must be a JSON object"
        )
    canonical_text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    if text != canonical_text:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "contract bytes are not canonical JSON with one trailing LF"
        )
    return payload


def _verify_allocation(value: object) -> None:
    allocation = _mapping(value, name="allocation")
    _exact_keys(
        allocation,
        {
            "allocation_schema_id",
            "atomic_feature_max_index",
            "atomic_feature_required_fields",
            "atomic_feature_total_reference_capacity",
            "availability_caller_supplied",
            "canonical_receipt_max_bytes",
            "candidate_denominator",
            "conformer_source_required_fields",
            "failed_slots_preserved_in_denominator",
            "fallback_allowed",
            "exact_v11_source_required_fields",
            "exact_v11_source_schema_id",
            "feature_evidence_required_fields",
            "feature_evidence_schema_id",
            "feature_receipt_identity_binding_required",
            "feature_receipt_source_rederivation_required",
            "generation_parent_roles",
            "interaction_lane_split",
            "lane_ranges_inclusive",
            "multi_anchor_allowed",
            "result_dependent_allocation_allowed",
            "retained_source_indices",
            "retained_source_namespace",
            "retained_source_required_fields",
            "slot_generation_parent_binding_fields",
            "slot_schema_id",
            "slot_selected_source_receipts_required",
            "so3_sequence_indices",
            "source_bound_feature_evidence_required",
            "true_conformer_round_robin_ranks",
            "true_conformer_so3_sequence_indices",
            "true_conformer_missing_failure_by_slot",
            "typed_missing_feature_failures_required",
            "v7_control_missing_failure_code_format",
            "v7_control_source_indices",
            "v7_control_source_namespace",
            "v7_control_source_required_fields",
            "v7_control_source_schema_id",
        },
        name="allocation",
    )
    if (
        type(allocation.get("candidate_denominator")) is not int
        or allocation.get("candidate_denominator") != CANDIDATE_DENOMINATOR
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "candidate denominator drifted"
        )
    expected_integer_bounds = {
        "atomic_feature_max_index": (1 << 53) - 1,
        "atomic_feature_total_reference_capacity": 65_536,
        "canonical_receipt_max_bytes": 32 * 1024 * 1024,
    }
    for key, expected in expected_integer_bounds.items():
        if type(allocation.get(key)) is not int or allocation.get(key) != expected:
            raise Mixed64GeometricCandidateEvidenceV2ContractError(
                f"{key} drifted"
            )
    for key in (
        "failed_slots_preserved_in_denominator",
        "feature_receipt_identity_binding_required",
        "slot_selected_source_receipts_required",
        "source_bound_feature_evidence_required",
        "typed_missing_feature_failures_required",
    ):
        _required_boolean(allocation, key, expected=True)
    for key in (
        "availability_caller_supplied",
        "feature_receipt_source_rederivation_required",
        "fallback_allowed",
        "multi_anchor_allowed",
        "result_dependent_allocation_allowed",
    ):
        _required_boolean(allocation, key, expected=False)
    for key, expected, label in (
        (
            "allocation_schema_id",
            EXPECTED_ALLOCATION_SCHEMA_ID,
            "allocation schema",
        ),
        ("slot_schema_id", EXPECTED_SLOT_SCHEMA_ID, "slot schema"),
        (
            "feature_evidence_schema_id",
            EXPECTED_FEATURE_EVIDENCE_SCHEMA_ID,
            "feature evidence schema",
        ),
        (
            "exact_v11_source_schema_id",
            EXPECTED_EXACT_V11_SOURCE_SCHEMA_ID,
            "exact V1.1 source schema",
        ),
        (
            "v7_control_source_schema_id",
            EXPECTED_V7_CONTROL_SOURCE_SCHEMA_ID,
            "V7 control source schema",
        ),
    ):
        if allocation.get(key) != expected:
            raise Mixed64GeometricCandidateEvidenceV2ContractError(
                f"{label} drifted"
            )
    if allocation.get("retained_source_namespace") != (
        "current_v7_source_proposal_index"
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "retained source namespace drifted"
        )
    if allocation.get("v7_control_source_namespace") != (
        EXPECTED_V7_CONTROL_SOURCE_NAMESPACE
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "V7 control source namespace drifted"
        )
    if allocation.get("v7_control_missing_failure_code_format") != (
        "missing_v7_control_source:<source_index>"
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "V7 control missing failure code format drifted"
        )
    for field_name, expected_fields, label in (
        (
            "feature_evidence_required_fields",
            EXPECTED_FEATURE_EVIDENCE_FIELDS,
            "feature evidence fields",
        ),
        (
            "exact_v11_source_required_fields",
            EXPECTED_EXACT_V11_SOURCE_FIELDS,
            "exact V1.1 source fields",
        ),
        (
            "atomic_feature_required_fields",
            EXPECTED_ATOMIC_FEATURE_FIELDS,
            "atomic feature fields",
        ),
        (
            "conformer_source_required_fields",
            EXPECTED_CONFORMER_SOURCE_FIELDS,
            "conformer source fields",
        ),
        (
            "retained_source_required_fields",
            EXPECTED_RETAINED_SOURCE_FIELDS,
            "retained source fields",
        ),
        (
            "v7_control_source_required_fields",
            EXPECTED_V7_CONTROL_SOURCE_FIELDS,
            "V7 control source fields",
        ),
        (
            "slot_generation_parent_binding_fields",
            EXPECTED_SLOT_GENERATION_PARENT_BINDING_FIELDS,
            "slot generation parent binding fields",
        ),
    ):
        _exact_sequence(
            allocation.get(field_name),
            expected_fields,
            name=label,
        )
    _exact_sequence(
        allocation.get("generation_parent_roles"),
        EXPECTED_GENERATION_PARENT_ROLES,
        name="generation parent roles",
    )

    lane_ranges = allocation.get("lane_ranges_inclusive")
    if type(lane_ranges) is not list or len(lane_ranges) != len(
        EXPECTED_LANE_RANGES
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "lane ranges drifted"
        )
    for observed, (lane, start, end, count) in zip(
        lane_ranges,
        EXPECTED_LANE_RANGES,
        strict=True,
    ):
        item = _mapping(observed, name="allocation lane range")
        _exact_keys(item, {"lane", "start", "end", "count"}, name="lane range")
        expected_item = {
            "lane": lane,
            "start": start,
            "end": end,
            "count": count,
        }
        if any(
            type(item.get(key)) is not type(required)
            or item.get(key) != required
            for key, required in expected_item.items()
        ):
            raise Mixed64GeometricCandidateEvidenceV2ContractError(
                "lane ranges drifted"
            )
    if sum(count for _, _, _, count in EXPECTED_LANE_RANGES) != 64:
        raise AssertionError("frozen lane counts do not sum to fixed64")

    split = _mapping(
        allocation.get("interaction_lane_split"),
        name="interaction_lane_split",
    )
    if dict(split) != EXPECTED_INTERACTION_LANE_SPLIT or any(
        type(value) is not int for value in split.values()
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "charge/aromatic/shape split drifted"
        )
    _exact_sequence(
        allocation.get("v7_control_source_indices"),
        tuple(range(24)),
        name="V7 control source indices",
    )
    _exact_sequence(
        allocation.get("so3_sequence_indices"),
        tuple(range(12)),
        name="SO3 sequence indices",
    )
    _exact_sequence(
        allocation.get("true_conformer_round_robin_ranks"),
        (2, 3, 4, 5, 6, 7, 8, 2),
        name="true-conformer round-robin ranks",
    )
    _exact_sequence(
        allocation.get("true_conformer_so3_sequence_indices"),
        tuple(range(8)),
        name="true-conformer SO3 sequence indices",
    )
    _exact_sequence(
        allocation.get("retained_source_indices"),
        (36, 45, 54, 63),
        name="retained source indices",
    )
    _exact_json_value(
        allocation.get("true_conformer_missing_failure_by_slot"),
        EXPECTED_TRUE_CONFORMER_FAILURES,
        name="true-conformer per-rank failure mapping",
    )


def _verify_geometric_admission(value: object) -> None:
    geometric = _mapping(value, name="geometric_admission")
    _exact_keys(
        geometric,
        {
            "batch_pair_work_fail_closed",
            "exact_pair_traversal_order",
            "exact_input_payload_required",
            "full_allocation_payload_required",
            "hard_rejection_metric",
            "hard_rejection_operator",
            "hard_rejection_threshold_binary64_hex",
            "input_safety_envelope",
            "ligand_heavy_atom_mask_sha256_required",
            "maximum_batch_exact_pair_evaluations",
            "metric_fields",
            "only_hard_rejection_code",
            "rejected_slots_preserved_in_denominator",
            "rejected_slots_rank_ineligible",
            "typed_missing_feature_rejection_code",
        },
        name="geometric_admission",
    )
    expected_strings = {
        "exact_pair_traversal_order": (
            "full_cartesian_ligand_index_major_receptor_index_minor"
        ),
        "hard_rejection_metric": "minimum_vdw_ratio",
        "hard_rejection_operator": "strictly_less_than",
        "only_hard_rejection_code": (
            "severe_receptor_penetration_min_vdw_ratio"
        ),
        "typed_missing_feature_rejection_code": "mixed64_typed_missing_feature",
    }
    for key, required in expected_strings.items():
        if type(geometric.get(key)) is not str or geometric.get(key) != required:
            raise Mixed64GeometricCandidateEvidenceV2ContractError(
                f"{key} drifted"
            )
    for key in (
        "batch_pair_work_fail_closed",
        "exact_input_payload_required",
        "full_allocation_payload_required",
        "ligand_heavy_atom_mask_sha256_required",
        "rejected_slots_preserved_in_denominator",
        "rejected_slots_rank_ineligible",
    ):
        _required_boolean(geometric, key, expected=True)
    safety_envelope = _mapping(
        geometric.get("input_safety_envelope"),
        name="input_safety_envelope",
    )
    expected_safety_envelope = {
        "maximum_absolute_coordinate_angstrom_binary64_hex": (
            "0x1.86a0000000000p+16"
        ),
        "maximum_pocket_radius_angstrom_binary64_hex": "0x1.f400000000000p+9",
        "maximum_vdw_radius_angstrom_binary64_hex": "0x1.4000000000000p+3",
        "minimum_vdw_radius_angstrom_binary64_hex": "0x1.999999999999ap-4",
    }
    _exact_json_value(
        dict(safety_envelope),
        expected_safety_envelope,
        name="geometric input safety envelope",
    )
    decoded_safety = {
        key: float.fromhex(value)
        for key, value in expected_safety_envelope.items()
    }
    if decoded_safety != {
        "maximum_absolute_coordinate_angstrom_binary64_hex": 100_000.0,
        "maximum_pocket_radius_angstrom_binary64_hex": 1_000.0,
        "maximum_vdw_radius_angstrom_binary64_hex": 10.0,
        "minimum_vdw_radius_angstrom_binary64_hex": 0.1,
    }:
        raise AssertionError("frozen geometric safety envelope is invalid")
    if (
        type(geometric.get("maximum_batch_exact_pair_evaluations")) is not int
        or geometric.get("maximum_batch_exact_pair_evaluations") != 16_777_216
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "maximum batch exact pair evaluations drifted"
        )
    threshold = geometric.get("hard_rejection_threshold_binary64_hex")
    if type(threshold) is not str:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "hard rejection threshold must be binary64 hex"
        )
    try:
        observed_threshold = float.fromhex(threshold)
    except ValueError as exc:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "hard rejection threshold must be binary64 hex"
        ) from exc
    if observed_threshold != HARD_REJECTION_MINIMUM_VDW_RATIO:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "hard rejection threshold drifted"
        )
    _exact_sequence(
        geometric.get("metric_fields"),
        EXPECTED_METRIC_FIELDS,
        name="geometric metric fields",
    )


def _verify_candidate_evidence(value: object) -> None:
    evidence = _mapping(value, name="candidate_evidence")
    _exact_keys(
        evidence,
        {
            "activation_evidence_blockers",
            "activation_evidence_eligible",
            "batch_generator_identity_uniform_required",
            "batch_refinement_source_schema_uniform_required",
            "batch_refiner_identity_uniform_required",
            "candidate_denominator",
            "denominator_failure_complete",
            "denominator_failure_completeness_scope",
            "evidence_completion_caller_supplied",
            "execution_failure_stage_semantics",
            "execution_failure_stages",
            "failure_statuses",
            "full_allocation_payload_required",
            "full_pose_validity_receipt_required",
            "full_refinement_receipt_required",
            "full_scorer_v1_terms_receipt_required",
            "geometric_rejections_rank_ineligible",
            "invalid_top1_derived",
            "minimum_batch_binding_fields",
            "minimum_candidate_binding_fields",
            "refinement_source_identity_authority_or_eligibility_must_be_false",
            "partial_stage_evidence_preserved",
            "post_refinement_geometric_admission_present",
            "primary_ranking_includes_complete_invalid_candidates",
            "primary_ranking_includes_validity_unavailable_score_complete_candidates",
            "primary_ranking_order",
            "primary_ranking_semantics",
            "proposal_execution_receipt_contract",
            "proposal_generation_failure_receipt_supported",
            "rank_eligibility_caller_supplied",
            "receipt_attestation_contract",
            "refinement_receipt_binding_fields",
            "refinement_pre_post_coordinate_identities_required",
            "refinement_source_identity_schema_id",
            "refinement_source_payload_embedded",
            "refinement_source_payload_rederived",
            "scorer_v1_evidence_contract",
            "scored_success_status",
            "top1_pose_valid_derived",
            "top_k_limits",
            "top_k_membership_caller_supplied",
            "valid_only_ranking_semantics",
            "valid_only_ranking_is_separate",
            "valid_rank_eligibility_caller_supplied",
            "validity_contract",
            "validity_failure_primary_rank_eligible",
            "validity_failure_score_evidence_required",
            "validity_is_post_score_ranking_evidence",
        },
        name="candidate_evidence",
    )
    if (
        type(evidence.get("candidate_denominator")) is not int
        or evidence.get("candidate_denominator") != CANDIDATE_DENOMINATOR
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "candidate evidence denominator drifted"
        )
    for key in (
        "batch_generator_identity_uniform_required",
        "batch_refinement_source_schema_uniform_required",
        "batch_refiner_identity_uniform_required",
        "denominator_failure_complete",
        "full_allocation_payload_required",
        "full_pose_validity_receipt_required",
        "full_refinement_receipt_required",
        "full_scorer_v1_terms_receipt_required",
        "geometric_rejections_rank_ineligible",
        "invalid_top1_derived",
        "refinement_source_identity_authority_or_eligibility_must_be_false",
        "partial_stage_evidence_preserved",
        "primary_ranking_includes_complete_invalid_candidates",
        "primary_ranking_includes_validity_unavailable_score_complete_candidates",
        "refinement_pre_post_coordinate_identities_required",
        "top1_pose_valid_derived",
        "valid_only_ranking_is_separate",
        "validity_is_post_score_ranking_evidence",
        "validity_failure_primary_rank_eligible",
        "validity_failure_score_evidence_required",
    ):
        _required_boolean(evidence, key, expected=True)
    for key in (
        "activation_evidence_eligible",
        "evidence_completion_caller_supplied",
        "post_refinement_geometric_admission_present",
        "proposal_generation_failure_receipt_supported",
        "rank_eligibility_caller_supplied",
        "refinement_source_payload_embedded",
        "refinement_source_payload_rederived",
        "top_k_membership_caller_supplied",
        "valid_rank_eligibility_caller_supplied",
    ):
        _required_boolean(evidence, key, expected=False)
    if (
        evidence.get("refinement_source_identity_schema_id")
        != EXPECTED_REFINEMENT_SOURCE_IDENTITY_SCHEMA_ID
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "refinement source identity schema drifted"
        )
    _exact_sequence(
        evidence.get("activation_evidence_blockers"),
        EXPECTED_ACTIVATION_EVIDENCE_BLOCKERS,
        name="activation evidence blockers",
    )
    if evidence.get("denominator_failure_completeness_scope") != (
        EXPECTED_DENOMINATOR_FAILURE_COMPLETENESS_SCOPE
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "denominator failure completeness scope drifted"
        )
    if evidence.get("scored_success_status") != "scored_success":
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "scored success status drifted"
        )
    if evidence.get("primary_ranking_order") != (
        "finite_total_score_ascending_then_slot_index_then_result_sha256"
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "primary ranking order drifted"
        )
    if evidence.get("primary_ranking_semantics") != (
        "all_complete_score_evidence_geometrically_admitted_candidates_"
        "including_pose_invalid_and_validity_unavailable"
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "primary ranking semantics drifted"
        )
    if evidence.get("valid_only_ranking_semantics") != (
        "primary_score_order_filtered_by_complete_pose_validity_true"
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "valid-only ranking semantics drifted"
        )

    proposal_contract = _mapping(
        evidence.get("proposal_execution_receipt_contract"),
        name="proposal_execution_receipt_contract",
    )
    _exact_keys(
        proposal_contract,
        {
            "producer_attested",
            "required_binding_fields",
            "selected_source_receipts_exact_match_required",
            "structurally_complete",
        },
        name="proposal execution receipt contract",
    )
    _required_boolean(proposal_contract, "producer_attested", expected=False)
    for key in (
        "selected_source_receipts_exact_match_required",
        "structurally_complete",
    ):
        _required_boolean(proposal_contract, key, expected=True)
    _exact_sequence(
        proposal_contract.get("required_binding_fields"),
        EXPECTED_PROPOSAL_EXECUTION_BINDING_FIELDS,
        name="proposal execution binding fields",
    )

    attestation_contract = _mapping(
        evidence.get("receipt_attestation_contract"),
        name="receipt_attestation_contract",
    )
    _exact_keys(
        attestation_contract,
        {
            "maximum_absolute_json_integer",
            "maximum_json_key_bytes",
            "producer_attested",
            "receipt_schema_ids",
            "structurally_complete",
        },
        name="receipt attestation contract",
    )
    _required_boolean(attestation_contract, "producer_attested", expected=False)
    maximum_json_integer = attestation_contract.get(
        "maximum_absolute_json_integer"
    )
    if (
        type(maximum_json_integer) is not int
        or maximum_json_integer != (1 << 53) - 1
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "canonical JSON integer envelope drifted"
        )
    maximum_json_key_bytes = attestation_contract.get("maximum_json_key_bytes")
    if type(maximum_json_key_bytes) is not int or maximum_json_key_bytes != 256:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "canonical JSON key envelope drifted"
        )
    _required_boolean(attestation_contract, "structurally_complete", expected=True)
    _exact_sequence(
        attestation_contract.get("receipt_schema_ids"),
        EXPECTED_STRUCTURAL_RECEIPT_SCHEMA_IDS,
        name="structural receipt schema IDs",
    )

    scorer_contract = _mapping(
        evidence.get("scorer_v1_evidence_contract"),
        name="scorer_v1_evidence_contract",
    )
    _exact_keys(
        scorer_contract,
        {
            "full_scorer_v1_terms_required",
            "maximum_exact_count",
            "producer_attested",
            "required_search_provenance_fields",
            "result_proposal_binding_required",
            "structurally_complete",
        },
        name="ScorerV1 evidence contract",
    )
    _required_boolean(scorer_contract, "producer_attested", expected=False)
    for key in (
        "full_scorer_v1_terms_required",
        "result_proposal_binding_required",
        "structurally_complete",
    ):
        _required_boolean(scorer_contract, key, expected=True)
    maximum_exact_count = scorer_contract.get("maximum_exact_count")
    if type(maximum_exact_count) is not int or maximum_exact_count != 16_777_216:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "ScorerV1 exact count envelope drifted"
        )
    _exact_sequence(
        scorer_contract.get("required_search_provenance_fields"),
        EXPECTED_SCORER_SEARCH_PROVENANCE_FIELDS,
        name="ScorerV1 search provenance fields",
    )

    validity_contract = _mapping(
        evidence.get("validity_contract"),
        name="validity_contract",
    )
    _exact_keys(
        validity_contract,
        {
            "exact_check_set_required",
            "invalid_top1_values",
            "invalid_top1_requires_explicit_false",
            "maximum_absolute_measurement",
            "maximum_blocker_count",
            "maximum_measurement_count",
            "producer_attested",
            "required_checks",
            "required_receipt_binding_fields",
            "structurally_complete",
            "top1_pose_valid_values",
            "unavailable_encoded_as_null",
            "validity_failure_state",
        },
        name="validity contract",
    )
    _required_boolean(validity_contract, "producer_attested", expected=False)
    if validity_contract.get("maximum_measurement_count") != 256:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "pose validity measurement capacity drifted"
        )
    if validity_contract.get("maximum_blocker_count") != 256:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "pose validity blocker capacity drifted"
        )
    maximum_measurement = validity_contract.get("maximum_absolute_measurement")
    if (
        type(maximum_measurement) is not float
        or maximum_measurement != 1.0e15
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "pose validity measurement magnitude envelope drifted"
        )
    for key in (
        "exact_check_set_required",
        "invalid_top1_requires_explicit_false",
        "structurally_complete",
        "unavailable_encoded_as_null",
    ):
        _required_boolean(validity_contract, key, expected=True)
    required_checks = validity_contract.get("required_checks")
    if (
        type(required_checks) is not list
        or len(required_checks) != len(EXPECTED_VALIDITY_CHECKS)
        or any(type(value) is not str for value in required_checks)
        or frozenset(required_checks) != EXPECTED_VALIDITY_CHECKS
    ):
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "exact pose validity check set drifted"
        )
    _exact_sequence(
        validity_contract.get("required_receipt_binding_fields"),
        EXPECTED_VALIDITY_RECEIPT_BINDING_FIELDS,
        name="validity receipt binding fields",
    )
    _exact_json_value(
        validity_contract.get("top1_pose_valid_values"),
        [True, False, None],
        name="Top-1 pose validity tri-state",
    )
    _exact_json_value(
        validity_contract.get("invalid_top1_values"),
        [True, False, None],
        name="invalid Top-1 tri-state",
    )
    if validity_contract.get("validity_failure_state") != "unavailable":
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "validity failure state drifted"
        )

    _exact_sequence(
        evidence.get("minimum_batch_binding_fields"),
        EXPECTED_BATCH_BINDING_FIELDS,
        name="minimum batch binding fields",
    )
    _exact_sequence(
        evidence.get("minimum_candidate_binding_fields"),
        EXPECTED_CANDIDATE_BINDING_FIELDS,
        name="minimum candidate binding fields",
    )
    _exact_sequence(
        evidence.get("failure_statuses"),
        EXPECTED_FAILURE_STATUSES,
        name="failure statuses",
    )
    _exact_sequence(
        evidence.get("execution_failure_stages"),
        EXPECTED_EXECUTION_FAILURE_STAGES,
        name="execution failure stages",
    )
    _exact_json_value(
        evidence.get("execution_failure_stage_semantics"),
        EXPECTED_EXECUTION_FAILURE_STAGE_SEMANTICS,
        name="execution failure stage semantics",
    )
    _exact_sequence(
        evidence.get("refinement_receipt_binding_fields"),
        EXPECTED_REFINEMENT_BINDING_FIELDS,
        name="refinement receipt binding fields",
    )
    _exact_sequence(
        evidence.get("top_k_limits"),
        (1, 5),
        name="Top-K limits",
    )


def verify_contract(contract: Mapping[str, Any]) -> str:
    _exact_keys(
        contract,
        {
            "allocation",
            "authority",
            "candidate_evidence",
            "contract_sha256",
            "geometric_admission",
            "schema_id",
            "status",
        },
        name="contract",
    )
    if contract.get("schema_id") != SCHEMA_ID:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "contract schema is invalid"
        )
    if contract.get("status") != STATUS:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "synthetic-only status drifted"
        )
    observed_hash = contract.get("contract_sha256")
    projection = dict(contract)
    projection.pop("contract_sha256", None)
    expected_hash = _sha256(projection)
    if observed_hash != expected_hash:
        raise Mixed64GeometricCandidateEvidenceV2ContractError(
            "contract self-hash is invalid"
        )

    _verify_allocation(contract.get("allocation"))
    _verify_geometric_admission(contract.get("geometric_admission"))
    _verify_candidate_evidence(contract.get("candidate_evidence"))

    authority = _mapping(contract.get("authority"), name="authority")
    _exact_keys(
        authority,
        set(FORBIDDEN_TRUE_AUTHORITY_KEYS),
        name="authority",
    )
    for key in FORBIDDEN_TRUE_AUTHORITY_KEYS:
        _required_boolean(authority, key, expected=False)
    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/engine_v2_mixed64_geometric_candidate_evidence_v2.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    print(verify_contract(load_contract(arguments.contract)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
