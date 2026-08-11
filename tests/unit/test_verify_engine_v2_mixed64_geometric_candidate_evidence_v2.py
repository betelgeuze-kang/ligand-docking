from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_mixed64_geometric_candidate_evidence_v2 import (
    EXPECTED_LANE_RANGES,
    FORBIDDEN_TRUE_AUTHORITY_KEYS,
    Mixed64GeometricCandidateEvidenceV2ContractError,
    load_contract,
    verify_contract,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_PATH = (
    _REPO_ROOT / "config/engine_v2_mixed64_geometric_candidate_evidence_v2.json"
)


def _contract() -> dict[str, object]:
    return load_contract(_CONTRACT_PATH)


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("contract_sha256", None)
    changed["contract_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return changed


def test_current_mixed64_geometric_candidate_evidence_contract_verifies() -> None:
    observed = verify_contract(_contract())

    assert len(observed) == 64
    assert _contract()["schema_id"].endswith("/2.0.0")
    allocation = _contract()["allocation"]
    assert allocation["candidate_denominator"] == 64
    assert [item["count"] for item in allocation["lane_ranges_inclusive"]] == [
        item[3] for item in EXPECTED_LANE_RANGES
    ]
    assert allocation["retained_source_indices"] == [36, 45, 54, 63]
    assert allocation["retained_source_namespace"] == (
        "current_v7_source_proposal_index"
    )
    assert allocation["allocation_schema_id"].endswith("/2.0.0")
    assert allocation["slot_schema_id"].endswith("/2.0.0")
    assert allocation["feature_evidence_schema_id"].endswith("/4.0.0")
    assert allocation["exact_v11_source_schema_id"].endswith("/1.0.0")
    assert allocation["v7_control_source_schema_id"].endswith("/2.0.0")
    assert allocation["v7_control_source_namespace"] == (
        "current_v7_source_proposal_index"
    )
    assert allocation["source_bound_feature_evidence_required"] is True
    evidence = _contract()["candidate_evidence"]
    assert evidence["primary_ranking_includes_complete_invalid_candidates"] is True
    assert evidence["valid_only_ranking_is_separate"] is True
    assert evidence["activation_evidence_eligible"] is False
    assert len(evidence["activation_evidence_blockers"]) == 10
    assert evidence["refinement_source_payload_embedded"] is False
    assert evidence["refinement_source_payload_rederived"] is False
    assert evidence["validity_contract"]["invalid_top1_values"] == [
        True,
        False,
        None,
    ]
    assert evidence["receipt_attestation_contract"][
        "maximum_absolute_json_integer"
    ] == (1 << 53) - 1
    assert evidence["receipt_attestation_contract"][
        "maximum_json_key_bytes"
    ] == 256


@pytest.mark.parametrize("authority_key", FORBIDDEN_TRUE_AUTHORITY_KEYS)
def test_resealed_authority_escalation_fails_closed(authority_key: str) -> None:
    changed = _contract()
    changed["authority"][authority_key] = True

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=authority_key,
    ):
        verify_contract(_reseal(changed))


def test_resealed_lane_count_drift_fails_closed() -> None:
    changed = _contract()
    changed["allocation"]["lane_ranges_inclusive"][2]["count"] = 11

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="lane ranges",
    ):
        verify_contract(_reseal(changed))


def test_resealed_charge_aromatic_shape_split_drift_fails_closed() -> None:
    changed = _contract()
    changed["allocation"]["interaction_lane_split"]["aromatic_plane"] = 3

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="charge/aromatic/shape split",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("v7_control_source_indices", list(range(1, 25)), "V7 control"),
        ("so3_sequence_indices", list(range(1, 13)), "SO3 sequence"),
        (
            "true_conformer_round_robin_ranks",
            [2, 3, 4, 5, 6, 7, 8, 9],
            "true-conformer round-robin",
        ),
        (
            "true_conformer_so3_sequence_indices",
            list(range(1, 9)),
            "true-conformer SO3",
        ),
        ("retained_source_indices", [36, 45, 54, 62], "retained source"),
    ),
)
def test_resealed_source_mapping_drift_fails_closed(
    field: str,
    replacement: list[int],
    message: str,
) -> None:
    changed = _contract()
    changed["allocation"][field] = replacement

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=message,
    ):
        verify_contract(_reseal(changed))


def test_resealed_hard_rejection_threshold_drift_fails_closed() -> None:
    changed = _contract()
    changed["geometric_admission"][
        "hard_rejection_threshold_binary64_hex"
    ] = (0.6).hex()

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="hard rejection threshold drifted",
    ):
        verify_contract(_reseal(changed))


def test_resealed_second_geometric_rejection_semantics_fail_closed() -> None:
    changed = _contract()
    changed["geometric_admission"]["hard_rejection_metric"] = (
        "minimum_vdw_surface_gap"
    )

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="hard_rejection_metric",
    ):
        verify_contract(_reseal(changed))


def test_resealed_scorer_count_bound_must_remain_an_exact_integer() -> None:
    changed = _contract()
    changed["candidate_evidence"]["scorer_v1_evidence_contract"][
        "maximum_exact_count"
    ] = 16_777_216.0

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="ScorerV1 exact count envelope drifted",
    ):
        verify_contract(_reseal(changed))


def test_resealed_heavy_atom_mask_requirement_cannot_be_disabled() -> None:
    changed = _contract()
    changed["geometric_admission"][
        "ligand_heavy_atom_mask_sha256_required"
    ] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="ligand_heavy_atom_mask_sha256_required",
    ):
        verify_contract(_reseal(changed))


def test_resealed_exact_input_payload_requirement_cannot_be_disabled() -> None:
    changed = _contract()
    changed["geometric_admission"]["exact_input_payload_required"] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="exact_input_payload_required",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    "field",
    (
        "full_allocation_payload_required",
        "full_scorer_v1_terms_receipt_required",
        "full_pose_validity_receipt_required",
        "full_refinement_receipt_required",
        "partial_stage_evidence_preserved",
        "refinement_pre_post_coordinate_identities_required",
        "refinement_source_identity_authority_or_eligibility_must_be_false",
    ),
)
def test_resealed_complete_evidence_requirement_fails_closed(field: str) -> None:
    changed = _contract()
    changed["candidate_evidence"][field] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    "field",
    (
        "source_bound_feature_evidence_required",
        "feature_receipt_identity_binding_required",
    ),
)
def test_resealed_feature_source_binding_cannot_be_disabled(field: str) -> None:
    changed = _contract()
    changed["allocation"][field] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


def test_parent_source_payload_rederivation_is_not_overclaimed() -> None:
    changed = _contract()
    assert changed["allocation"]["feature_receipt_source_rederivation_required"] is False
    changed["allocation"]["feature_receipt_source_rederivation_required"] = True

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="feature_receipt_source_rederivation_required",
    ):
        verify_contract(_reseal(changed))


def test_resealed_feature_v4_schema_or_retained_namespace_drift_fails_closed() -> None:
    changed = _contract()
    changed["allocation"]["retained_source_namespace"] = "ambiguous_index"

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="retained source namespace",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    changed["allocation"]["feature_evidence_schema_id"] = "legacy/1.0.0"

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="feature evidence schema",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("allocation_schema_id", "legacy/1.0.0", "allocation schema"),
        ("slot_schema_id", "legacy/1.0.0", "slot schema"),
        (
            "exact_v11_source_schema_id",
            "legacy/1.0.0",
            "exact V1.1 source schema",
        ),
        (
            "v7_control_source_schema_id",
            "legacy/1.0.0",
            "V7 control source schema",
        ),
        (
            "v7_control_source_namespace",
            "ambiguous_index",
            "V7 control source namespace",
        ),
        (
            "v7_control_missing_failure_code_format",
            "missing_v7_control_source",
            "V7 control missing failure code format",
        ),
    ),
)
def test_resealed_allocation_v2_source_identity_contract_fails_closed(
    field: str,
    replacement: str,
    message: str,
) -> None:
    changed = _contract()
    changed["allocation"][field] = replacement

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=message,
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    ("field", "removed", "message"),
    (
        (
            "feature_evidence_required_fields",
            "v7_control_sources",
            "feature evidence fields",
        ),
        (
            "exact_v11_source_required_fields",
            "receptor_coordinate_sha256",
            "exact V1.1 source fields",
        ),
        (
            "v7_control_source_required_fields",
            "proposal_lineage_sha256",
            "V7 control source fields",
        ),
        (
            "slot_generation_parent_binding_fields",
            "selected_generation_parent_coordinate_sha256",
            "slot generation parent binding fields",
        ),
    ),
)
def test_resealed_source_parent_field_removal_fails_closed(
    field: str,
    removed: str,
    message: str,
) -> None:
    changed = _contract()
    changed["allocation"][field].remove(removed)

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=message,
    ):
        verify_contract(_reseal(changed))


def test_resealed_generation_parent_role_drift_fails_closed() -> None:
    changed = _contract()
    changed["allocation"]["generation_parent_roles"][0] = "passthrough"

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="generation parent roles",
    ):
        verify_contract(_reseal(changed))


def test_resealed_feature_availability_or_selected_source_truth_fails_closed() -> None:
    for field, value in (
        ("availability_caller_supplied", True),
        ("slot_selected_source_receipts_required", False),
    ):
        changed = _contract()
        changed["allocation"][field] = value

        with pytest.raises(
            Mixed64GeometricCandidateEvidenceV2ContractError,
            match=field,
        ):
            verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("atomic_feature_max_index", (1 << 53)),
        ("atomic_feature_total_reference_capacity", 65_535),
        ("canonical_receipt_max_bytes", 64 * 1024 * 1024),
    ),
)
def test_resealed_allocation_capacity_drift_fails_closed(
    field: str,
    replacement: int,
) -> None:
    changed = _contract()
    changed["allocation"][field] = replacement

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


def test_resealed_true_conformer_failure_mapping_fails_closed() -> None:
    changed = _contract()
    changed["allocation"]["true_conformer_missing_failure_by_slot"][2][
        "failure_code"
    ] = "missing_true_conformer"

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="true-conformer per-rank failure mapping",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("maximum_absolute_coordinate_angstrom_binary64_hex", (99_999.0).hex()),
        ("minimum_vdw_radius_angstrom_binary64_hex", (0.2).hex()),
        ("maximum_vdw_radius_angstrom_binary64_hex", (9.0).hex()),
        ("maximum_pocket_radius_angstrom_binary64_hex", (999.0).hex()),
    ),
)
def test_resealed_geometric_safety_envelope_drift_fails_closed(
    field: str,
    replacement: str,
) -> None:
    changed = _contract()
    changed["geometric_admission"]["input_safety_envelope"][field] = replacement

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="geometric input safety envelope",
    ):
        verify_contract(_reseal(changed))


def test_resealed_pair_work_or_full_allocation_requirement_fails_closed() -> None:
    changed = _contract()
    changed["geometric_admission"]["batch_pair_work_fail_closed"] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="batch_pair_work_fail_closed",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    changed["geometric_admission"][
        "maximum_batch_exact_pair_evaluations"
    ] = 16_777_217

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="maximum batch exact pair evaluations",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    changed["geometric_admission"]["full_allocation_payload_required"] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="full_allocation_payload_required",
    ):
        verify_contract(_reseal(changed))


def test_resealed_proposal_execution_source_binding_fails_closed() -> None:
    changed = _contract()
    proposal = changed["candidate_evidence"]["proposal_execution_receipt_contract"]
    proposal["selected_source_receipts_exact_match_required"] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="selected_source_receipts_exact_match_required",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    proposal = changed["candidate_evidence"]["proposal_execution_receipt_contract"]
    proposal["required_binding_fields"].remove("source_coordinate_sha256")

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="proposal execution binding fields",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    proposal = changed["candidate_evidence"]["proposal_execution_receipt_contract"]
    proposal["required_binding_fields"].remove(
        "generation_parent_proposal_sha256"
    )

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="proposal execution binding fields",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    "field",
    (
        "batch_generator_identity_uniform_required",
        "batch_refinement_source_schema_uniform_required",
        "batch_refiner_identity_uniform_required",
    ),
)
def test_resealed_batch_producer_uniformity_cannot_be_disabled(field: str) -> None:
    changed = _contract()
    changed["candidate_evidence"][field] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


def test_resealed_activation_evidence_cannot_be_granted() -> None:
    changed = _contract()
    changed["candidate_evidence"]["activation_evidence_eligible"] = True

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="activation_evidence_eligible",
    ):
        verify_contract(_reseal(changed))


def test_resealed_activation_blocker_removal_fails_closed() -> None:
    changed = _contract()
    changed["candidate_evidence"]["activation_evidence_blockers"].pop()

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="activation evidence blockers",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    "field",
    (
        "proposal_generation_failure_receipt_supported",
        "post_refinement_geometric_admission_present",
    ),
)
def test_resealed_unimplemented_activation_stage_cannot_be_claimed(
    field: str,
) -> None:
    changed = _contract()
    changed["candidate_evidence"][field] = True

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


def test_resealed_denominator_completeness_scope_drift_fails_closed() -> None:
    changed = _contract()
    changed["candidate_evidence"]["denominator_failure_completeness_scope"] = (
        "all_pipeline_stages"
    )

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="denominator failure completeness scope",
    ):
        verify_contract(_reseal(changed))


def test_resealed_explicit_coordinate_lifecycle_fails_closed() -> None:
    changed = _contract()
    changed["candidate_evidence"]["minimum_candidate_binding_fields"].remove(
        "result_coordinate_sha256"
    )

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="minimum candidate binding fields",
    ):
        verify_contract(_reseal(changed))


def test_resealed_scorer_search_provenance_fails_closed() -> None:
    changed = _contract()
    scorer = changed["candidate_evidence"]["scorer_v1_evidence_contract"]
    scorer["required_search_provenance_fields"].remove("search_row_sha256")

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="ScorerV1 search provenance fields",
    ):
        verify_contract(_reseal(changed))


def test_resealed_validity_check_set_or_tristate_fails_closed() -> None:
    changed = _contract()
    validity = changed["candidate_evidence"]["validity_contract"]
    validity["required_checks"].remove("proper_rotation")

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="exact pose validity check set",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    validity = changed["candidate_evidence"]["validity_contract"]
    validity["top1_pose_valid_values"][-1] = "unknown"

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="Top-1 pose validity tri-state",
    ):
        verify_contract(_reseal(changed))


def test_resealed_validity_failure_score_ranking_semantics_fail_closed() -> None:
    changed = _contract()
    validity_stage = changed["candidate_evidence"][
        "execution_failure_stage_semantics"
    ][2]
    validity_stage["primary_rank_eligible"] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="execution failure stage semantics",
    ):
        verify_contract(_reseal(changed))

    changed = _contract()
    changed["candidate_evidence"][
        "validity_failure_score_evidence_required"
    ] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="validity_failure_score_evidence_required",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    ("container", "field", "value"),
    (
        ("receipt_attestation_contract", "producer_attested", True),
        ("receipt_attestation_contract", "structurally_complete", False),
        ("proposal_execution_receipt_contract", "producer_attested", True),
        ("proposal_execution_receipt_contract", "structurally_complete", False),
        ("scorer_v1_evidence_contract", "producer_attested", True),
        ("scorer_v1_evidence_contract", "structurally_complete", False),
        ("validity_contract", "producer_attested", True),
        ("validity_contract", "structurally_complete", False),
    ),
)
def test_resealed_structural_receipt_cannot_grant_attestation(
    container: str,
    field: str,
    value: bool,
) -> None:
    changed = _contract()
    changed["candidate_evidence"][container][field] = value

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


def test_resealed_primary_rank_cannot_hide_pose_invalid_candidates() -> None:
    changed = _contract()
    changed["candidate_evidence"][
        "primary_ranking_includes_complete_invalid_candidates"
    ] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="primary_ranking_includes_complete_invalid_candidates",
    ):
        verify_contract(_reseal(changed))


def test_resealed_valid_only_rank_cannot_replace_primary_rank() -> None:
    changed = _contract()
    changed["candidate_evidence"]["valid_only_ranking_is_separate"] = False

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="valid_only_ranking_is_separate",
    ):
        verify_contract(_reseal(changed))


@pytest.mark.parametrize(
    "field",
    (
        "evidence_completion_caller_supplied",
        "rank_eligibility_caller_supplied",
        "top_k_membership_caller_supplied",
        "valid_rank_eligibility_caller_supplied",
    ),
)
def test_resealed_caller_supplied_derived_state_fails_closed(field: str) -> None:
    changed = _contract()
    changed["candidate_evidence"][field] = True

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match=field,
    ):
        verify_contract(_reseal(changed))


def test_duplicate_json_authority_key_fails_before_verification(
    tmp_path: Path,
) -> None:
    duplicate = _CONTRACT_PATH.read_text(encoding="ascii").replace(
        '  "authority": {',
        '  "authority": {},\n  "authority": {',
        1,
    )
    path = tmp_path / "duplicate.json"
    path.write_text(duplicate, encoding="ascii")

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="duplicate JSON key: authority",
    ):
        load_contract(path)


def test_noncanonical_contract_bytes_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "noncanonical.json"
    path.write_text(
        _CONTRACT_PATH.read_text(encoding="ascii").rstrip("\n"),
        encoding="ascii",
    )

    with pytest.raises(
        Mixed64GeometricCandidateEvidenceV2ContractError,
        match="not canonical JSON with one trailing LF",
    ):
        load_contract(path)
