#!/usr/bin/env python3
"""Fail closed on drift in the Engine V2 Phase 2.5 cohort boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_ID = "betelgeuze.engine_v2_phase25_cohort_admission/1.3.0"
EXPECTED_POLICY_SHA256 = (
    "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211"
)
EXPECTED_THRESHOLD_EVIDENCE_SHA256 = (
    "8f6e548bae67e56dbe05e95ae4ac08f4af5b1eb7b8119adc09cb33e366a36ce3"
)
EXPECTED_THRESHOLD_CASE_IDS_SHA256 = (
    "cba8259f2dd99b1b998903f4edffb4696f0bbdcb758f9c4df15573d29db2a621"
)
EXPECTED_CONTAMINATION_REGISTRY_SHA256 = (
    "89a58e6fbadd7e249df20bdf8db36f317e3e2e2dd6f32c32879d1a989dd28f31"
)
EXPECTED_CONTAMINATION_CASE_IDS_SHA256 = (
    "110c9ccc37255c39df3dae5b0213e4cf158cccfaf30071cb5ec9eb8e269ef349"
)
EXPECTED_FRESH_MANIFEST_SHA256 = (
    "459303a54cb1e8ebaf2bfa4320ad2287536d0e20a916fe5d2bac60edbdffdfba"
)
EXPECTED_FRESH_CASE_IDS_SHA256 = (
    "ecc91c660896245f62ad8b583cfa4f45e50038cf513c384f6bdb56d406278248"
)
EXPECTED_SOURCE_PAIRED_ARCHIVE_SHA256 = (
    "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc"
)
EXPECTED_SOURCE_PAIRED_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
EXPECTED_CLEARANCE_POLICY_SHA256 = (
    "e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad"
)
EXPECTED_ADMITTED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_SOURCE_PAIRED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6M73_FNR",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_THRESHOLD_ONLY_CASE_IDS = ("7A9E_R4W", "7MWU_ZPM", "7OSO_0V1")
EXPECTED_THRESHOLD_CASE_IDS = (
    *EXPECTED_SOURCE_PAIRED_CASE_IDS,
    *EXPECTED_THRESHOLD_ONLY_CASE_IDS,
)
EXPECTED_SOURCE_PAIRED_NOT_FAILURE_ATLAS = (
    {"case_id": "6M73_FNR", "reason": "preparation_failure"},
    {"case_id": "6T88_MWQ", "reason": "proposal_oracle_recovered"},
)
EXPECTED_THRESHOLD_NOT_FAILURE_ATLAS = (
    "6M73_FNR",
    "6T88_MWQ",
    *EXPECTED_THRESHOLD_ONLY_CASE_IDS,
)
EXPECTED_BASELINE_RECOVERY_CASE_IDS = ("6T88_MWQ",)
EXPECTED_PREPARATION_FAILURE_CASE_IDS = ("6M73_FNR",)
EXPECTED_ENGINEERING_SMOKE_CASE_IDS = ("5SAK_ZRY", "5SB2_1K2")
EXPECTED_GO_CRITERIA = (
    "new_exact_valid_candidate_in_previously_uncovered_case",
    "proposal_oracle_recovery_at_least_2_of_8",
    "invalid_top1_at_most_4_of_8",
)
EXPECTED_INVARIANTS = (
    "no_preparation_failure_regression",
    "no_top1_or_top5_recovery_regression",
    "candidate_denominator_512",
    "source_control_preserved",
    "score_term_semantics_fully_verified",
    "no_result_dependent_allocation",
)
EXPECTED_NO_GO_CRITERIA = (
    "shadow_eligible_candidate_without_new_case_recovery",
    "no_exact_valid_case_increase",
    "no_invalid_top1_reduction",
    "existing_recovery_regression",
    "selected_state_remains_penetrating_without_posebusters_validity_change",
)
EXPECTED_ARCHIVE_IDENTITY_FIELDS = (
    "archive_file_sha256",
    "member_manifest_sha256",
    "bundle_checksum_sha256",
    "member_count",
    "member_sha256s",
)
EXPECTED_EXECUTION_IDENTITY_FIELDS = (
    "source_commit",
    "algorithm_profile",
    "runner",
    "candidate_schema",
    "diagnostic_schema",
    "result_schema",
    "refinement_receipt_schema",
    "scorer_policy",
    "pocket_policy",
    "charge_policy",
    "proposal_policy",
    "implementation_sha256",
    "evaluation_pipeline_sha256",
    "execution_environment_sha256",
)
TOP_LEVEL_KEYS = {
    "authority_boundary",
    "cohort_relationships",
    "decision",
    "distinguished_non_admission_evidence",
    "expansion_gate",
    "failure_atlas_cohort_authority",
    "governance_base_commit",
    "local_refinement_experiment_stop_rule",
    "policy_sha256",
    "schema_id",
    "status",
}

EXPECTED_AUTHORITY_BOUNDARY = {
    "clearance_selection_policy_failure_atlas_membership_authority": False,
    "cohort_expansion_failure_effect": "retain_exact_7_case_failure_atlas",
    "fresh_holdout_execution_authorized": False,
    "historical_receipt_fresh_execution_fact_preserved": True,
    "new_execution_authorized": False,
    "product_authority": False,
    "profile_promotion_authority": False,
    "public_claim_authority": False,
    "runtime_authority": False,
    "scientific_claim_authority": False,
    "scorer_authority": False,
    "selection_policy_authority": False,
    "v11_clearance_audit_failure_atlas_membership_authority": False,
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_json(path: Path, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not readable canonical JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} keys are invalid")


def _exact_bool(value: object, expected: bool, *, name: str) -> None:
    if type(value) is not bool or value is not expected:
        raise ValueError(f"{name} must be {expected}")


def _exact_int(value: object, expected: int, *, name: str) -> None:
    if type(value) is not int or value != expected:
        raise ValueError(f"{name} must equal {expected}")


def _exact_mapping(
    value: Mapping[str, Any],
    expected: Mapping[str, object],
    *,
    name: str,
) -> None:
    _exact_keys(value, set(expected), name=name)
    for key, expected_value in expected.items():
        observed = value.get(key)
        if type(observed) is not type(expected_value) or observed != expected_value:
            raise ValueError(f"{name}.{key} is invalid")


def _exact_list(value: object, expected: tuple[str, ...], *, name: str) -> None:
    if not isinstance(value, list) or tuple(value) != expected:
        raise ValueError(f"{name} must equal the frozen ordered values")


def _exact_object_list(
    value: object,
    expected: tuple[Mapping[str, str], ...],
    *,
    name: str,
) -> None:
    if not isinstance(value, list) or tuple(value) != expected:
        raise ValueError(f"{name} must equal the frozen ordered objects")


def _verify_self_hash(payload: Mapping[str, Any], *, field: str, name: str) -> None:
    projection = dict(payload)
    observed = projection.pop(field, None)
    if not _is_sha256(observed) or observed != _sha256_payload(projection):
        raise ValueError(f"{name} self-hash is invalid")


def _threshold_case_ids(source_reports: object) -> tuple[str, ...]:
    reports = _mapping(source_reports, name="threshold source_reports_sha256")
    if len(reports) != 36:
        raise ValueError(
            "threshold proposal source map must retain exactly 36 receipt hashes"
        )
    case_engines: dict[str, set[str]] = {}
    for raw_path, digest in reports.items():
        if not isinstance(raw_path, str) or not _is_sha256(digest):
            raise ValueError("threshold source report map contains an invalid row")
        path = Path(raw_path)
        case_id = path.stem
        engine = path.parent.name
        case_engines.setdefault(case_id, set()).add(engine)
    required_engines = {"engine_v2", "vina", "gnina"}
    if any(engines != required_engines for engines in case_engines.values()):
        raise ValueError("every threshold case must retain one receipt per engine")
    return tuple(sorted(case_engines))


def _fresh_case_ids(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    _verify_self_hash(manifest, field="manifest_sha256", name="fresh holdout manifest")
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("fresh holdout cases must be an array")
    case_ids: list[str] = []
    for row in cases:
        if not isinstance(row, dict) or type(row.get("case_id")) is not str:
            raise ValueError("fresh holdout case row is invalid")
        case_ids.append(row["case_id"])
    ordered = tuple(case_ids)
    if len(ordered) != len(set(ordered)):
        raise ValueError("fresh holdout case IDs are duplicated")
    _exact_int(manifest.get("case_count"), len(ordered), name="fresh case_count")
    if manifest.get("case_ids_sha256") != _sha256_payload(list(ordered)):
        raise ValueError("fresh holdout case roster hash is invalid")
    return ordered


def verify_policy(
    policy: Mapping[str, Any],
    threshold: Mapping[str, Any],
    contamination_registry: Mapping[str, Any],
    fresh_holdout_manifest: Mapping[str, Any],
) -> None:
    _exact_keys(policy, TOP_LEVEL_KEYS, name="cohort policy top-level")
    if policy.get("schema_id") != SCHEMA_ID:
        raise ValueError("cohort policy schema_id is invalid")
    _verify_self_hash(policy, field="policy_sha256", name="cohort policy")
    if policy.get("status") != "closed_exact_seven":
        raise ValueError("cohort policy status is not closed")
    if (
        policy.get("decision")
        != "freeze_exact_seven_case_proposal_oracle_uncovered_atlas"
    ):
        raise ValueError("cohort admission decision is not frozen")
    if (
        policy.get("governance_base_commit")
        != "e782fb2dadd83ce4b9e41fc1af5b970fe63e28ca"
    ):
        raise ValueError("governance base commit is invalid")

    admission = _mapping(
        policy.get("failure_atlas_cohort_authority"),
        name="failure_atlas_cohort_authority",
    )
    _exact_keys(
        admission,
        {
            "failure_atlas_membership_authority",
            "admitted_case_count",
            "admitted_case_ids",
            "admitted_case_ids_sha256",
            "classification_criterion",
            "failure_atlas_schema_id",
            "failure_atlas_self_sha256",
            "source_paired_archive",
        },
        name="failure_atlas_cohort_authority",
    )
    _exact_bool(
        admission.get("failure_atlas_membership_authority"),
        True,
        name="failure-atlas membership authority",
    )
    _exact_list(
        admission.get("admitted_case_ids"),
        EXPECTED_ADMITTED_CASE_IDS,
        name="admitted_case_ids",
    )
    _exact_int(
        admission.get("admitted_case_count"),
        len(EXPECTED_ADMITTED_CASE_IDS),
        name="admitted case count",
    )
    if admission.get("admitted_case_ids_sha256") != _sha256_payload(
        list(EXPECTED_ADMITTED_CASE_IDS)
    ):
        raise ValueError("admitted case roster hash is invalid")
    classification = _mapping(
        admission.get("classification_criterion"), name="classification_criterion"
    )
    _exact_mapping(
        classification,
        {
            "comparison": "less_than_or_equal",
            "lane": "proposal_oracle",
            "rmsd_angstrom": 2.0,
        },
        name="classification_criterion",
    )
    if (
        admission.get("failure_atlas_schema_id")
        != "betelgeuze.engine_v2_source_paired_failure_atlas/2.1.0"
        or admission.get("failure_atlas_self_sha256")
        != "58528986f293d96a8a4a3971ecc7abab436c7f27e768589cf0c22d8bc970c1d7"
    ):
        raise ValueError("failure atlas identity is invalid")
    source = _mapping(
        admission.get("source_paired_archive"), name="source_paired_archive"
    )
    _exact_keys(
        source,
        {
            "archive_sha256",
            "case_count",
            "case_ids",
            "case_ids_sha256",
            "scored_case_count",
            "source_commit_git_sha1",
            "source_commit_hash_algorithm",
        },
        name="source_paired_archive",
    )
    _exact_list(
        source.get("case_ids"),
        EXPECTED_SOURCE_PAIRED_CASE_IDS,
        name="source-paired case_ids",
    )
    _exact_int(source.get("case_count"), 9, name="source-paired case_count")
    _exact_int(
        source.get("scored_case_count"), 8, name="source-paired scored_case_count"
    )
    if source.get("case_ids_sha256") != _sha256_payload(
        list(EXPECTED_SOURCE_PAIRED_CASE_IDS)
    ):
        raise ValueError("source-paired roster hash is invalid")
    if (
        source.get("source_commit_git_sha1")
        != "754bebb9ddc2fbffdaca5d4143ff515c3b38c032"
        or source.get("source_commit_hash_algorithm") != "git_sha1"
        or source.get("archive_sha256") != EXPECTED_SOURCE_PAIRED_ARCHIVE_SHA256
        or source.get("case_ids_sha256") != EXPECTED_SOURCE_PAIRED_CASE_IDS_SHA256
    ):
        raise ValueError("source-paired archive identity is invalid")

    non_admission = _mapping(
        policy.get("distinguished_non_admission_evidence"),
        name="distinguished_non_admission_evidence",
    )
    _exact_keys(
        non_admission,
        {"narrative_remainder", "stage0_threshold_proposal_source_map"},
        name="distinguished_non_admission_evidence",
    )
    narrative = _mapping(
        non_admission.get("narrative_remainder"), name="narrative_remainder"
    )
    _exact_keys(
        narrative,
        {
            "failure_atlas_membership_authority",
            "case_ids_sha256",
            "cases_with_any_exact_valid_candidate",
            "ordered_case_ids",
            "remainder",
            "scored_case_count",
        },
        name="narrative_remainder",
    )
    if (
        type(narrative.get("scored_case_count")) is not int
        or narrative.get("scored_case_count") != 29
        or type(narrative.get("cases_with_any_exact_valid_candidate")) is not int
        or narrative.get("cases_with_any_exact_valid_candidate") != 14
        or type(narrative.get("remainder")) is not int
        or narrative.get("remainder") != 15
        or narrative.get("ordered_case_ids") is not None
        or narrative.get("case_ids_sha256") is not None
        or type(narrative.get("failure_atlas_membership_authority")) is not bool
        or narrative.get("failure_atlas_membership_authority") is not False
    ):
        raise ValueError(
            "narrative remainder must remain non-authoritative 29 - 14 = 15"
        )

    threshold_policy = _mapping(
        non_admission.get("stage0_threshold_proposal_source_map"),
        name="stage0_threshold_proposal_source_map",
    )
    _exact_keys(
        threshold_policy,
        {
            "artifact_identity_status",
            "case_count",
            "case_ids",
            "case_ids_sha256",
            "config_path",
            "evidence_self_sha256",
            "failure_atlas_membership_authority",
            "failure_atlas_roster_authority",
            "receipt_hash_count",
            "receipt_payloads_committed",
            "schema_id",
            "stage0_execution_threshold_authority",
            "threshold_value_status",
            "threshold_only_case_ids",
        },
        name="stage0_threshold_proposal_source_map",
    )
    _exact_list(
        threshold_policy.get("case_ids"),
        EXPECTED_THRESHOLD_CASE_IDS,
        name="threshold case_ids",
    )
    _exact_list(
        threshold_policy.get("threshold_only_case_ids"),
        EXPECTED_THRESHOLD_ONLY_CASE_IDS,
        name="threshold_only_case_ids",
    )
    if (
        type(threshold_policy.get("failure_atlas_membership_authority")) is not bool
        or threshold_policy.get("failure_atlas_membership_authority") is not False
        or type(threshold_policy.get("failure_atlas_roster_authority")) is not bool
        or threshold_policy.get("failure_atlas_roster_authority") is not False
        or type(threshold_policy.get("stage0_execution_threshold_authority"))
        is not bool
        or threshold_policy.get("stage0_execution_threshold_authority") is not False
    ):
        raise ValueError(
            "threshold proposal source map cannot admit failure-atlas cases "
            "or authorize Stage 0 execution thresholds"
        )
    if (
        threshold_policy.get("artifact_identity_status")
        != "pinned_for_phase25_cross_check"
        or threshold_policy.get("threshold_value_status")
        != "proposed_not_frozen_for_stage0_execution"
    ):
        raise ValueError("threshold proposal and artifact identity states are invalid")
    if (
        threshold_policy.get("config_path")
        != "config/engine_v2_public_redocking_stage0_threshold_evidence.json"
        or threshold_policy.get("schema_id")
        != "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0"
        or threshold.get("schema_id") != threshold_policy.get("schema_id")
    ):
        raise ValueError("threshold proposal source-map identity is invalid")
    _verify_self_hash(
        threshold,
        field="evidence_sha256",
        name="threshold proposal source map",
    )
    if (
        threshold.get("evidence_sha256") != EXPECTED_THRESHOLD_EVIDENCE_SHA256
        or threshold.get("case_ids_sha256") != EXPECTED_THRESHOLD_CASE_IDS_SHA256
    ):
        raise ValueError(
            "threshold proposal source-map artifact is not the pinned identity"
        )
    threshold_ids = _threshold_case_ids(threshold.get("source_reports_sha256"))
    if threshold_ids != EXPECTED_THRESHOLD_CASE_IDS:
        raise ValueError("threshold proposal source-map case membership drifted")
    if (
        type(threshold.get("case_count")) is not int
        or threshold.get("case_count") != 12
        or threshold.get("case_ids_sha256") != _sha256_payload(list(threshold_ids))
        or threshold_policy.get("case_count") != threshold.get("case_count")
        or threshold_policy.get("case_ids_sha256") != threshold.get("case_ids_sha256")
        or threshold_policy.get("evidence_self_sha256")
        != threshold.get("evidence_sha256")
        or type(threshold_policy.get("receipt_hash_count")) is not int
        or threshold_policy.get("receipt_hash_count") != 36
        or type(threshold_policy.get("receipt_payloads_committed")) is not bool
        or threshold_policy.get("receipt_payloads_committed") is not False
        or type(threshold.get("contains_engineering_smoke")) is not bool
        or threshold.get("contains_engineering_smoke") is not False
        or type(threshold.get("contains_fresh_internal_blind_holdout")) is not bool
        or threshold.get("contains_fresh_internal_blind_holdout") is not False
        or threshold.get("runtime_role") != "descriptive_only"
        or type(threshold.get("public_claim_eligible")) is not bool
        or threshold.get("public_claim_eligible") is not False
        or type(threshold.get("scientific_validation_claimed")) is not bool
        or threshold.get("scientific_validation_claimed") is not False
    ):
        raise ValueError(
            "threshold proposal source-map identity does not match the cohort policy"
        )

    relationships = _mapping(
        policy.get("cohort_relationships"), name="cohort_relationships"
    )
    _exact_keys(
        relationships,
        {
            "failure_atlas_is_strict_subset_of_source_paired",
            "narrative_remainder_has_set_relationship_authority",
            "source_paired_is_strict_subset_of_threshold",
            "source_paired_not_failure_atlas",
            "threshold_not_failure_atlas",
            "threshold_not_source_paired",
        },
        name="cohort_relationships",
    )
    _exact_bool(
        relationships.get("failure_atlas_is_strict_subset_of_source_paired"),
        True,
        name="failure-atlas subset relation",
    )
    _exact_bool(
        relationships.get("source_paired_is_strict_subset_of_threshold"),
        True,
        name="source-paired subset relation",
    )
    _exact_bool(
        relationships.get("narrative_remainder_has_set_relationship_authority"),
        False,
        name="narrative set authority",
    )
    _exact_object_list(
        relationships.get("source_paired_not_failure_atlas"),
        EXPECTED_SOURCE_PAIRED_NOT_FAILURE_ATLAS,
        name="source-paired minus failure-atlas relation",
    )
    _exact_list(
        relationships.get("threshold_not_source_paired"),
        EXPECTED_THRESHOLD_ONLY_CASE_IDS,
        name="threshold minus source-paired relation",
    )
    _exact_list(
        relationships.get("threshold_not_failure_atlas"),
        EXPECTED_THRESHOLD_NOT_FAILURE_ATLAS,
        name="threshold minus failure-atlas relation",
    )
    admitted_ids = set(EXPECTED_ADMITTED_CASE_IDS)
    source_ids = set(EXPECTED_SOURCE_PAIRED_CASE_IDS)
    threshold_id_set = set(EXPECTED_THRESHOLD_CASE_IDS)
    if (
        not admitted_ids < source_ids < threshold_id_set
        or source_ids - admitted_ids
        != {row["case_id"] for row in EXPECTED_SOURCE_PAIRED_NOT_FAILURE_ATLAS}
        or threshold_id_set - source_ids != set(EXPECTED_THRESHOLD_ONLY_CASE_IDS)
        or threshold_id_set - admitted_ids != set(EXPECTED_THRESHOLD_NOT_FAILURE_ATLAS)
    ):
        raise ValueError("frozen cohort set relationships are inconsistent")

    expansion = _mapping(policy.get("expansion_gate"), name="expansion_gate")
    if set(expansion) != {
        "archive_identity",
        "claim_boundary",
        "deterministic_uncovered_derivation",
        "execution_identity",
        "failure_complete_receipts",
        "scope_identity",
        "taxonomy_reconciliation",
    }:
        raise ValueError("expansion gate sections are invalid")
    archive_identity = _mapping(
        expansion.get("archive_identity"), name="archive_identity"
    )
    _exact_keys(archive_identity, {"required"}, name="archive_identity")
    _exact_list(
        archive_identity.get("required"),
        EXPECTED_ARCHIVE_IDENTITY_FIELDS,
        name="archive identity requirements",
    )
    execution_identity = _mapping(
        expansion.get("execution_identity"), name="execution_identity"
    )
    _exact_keys(execution_identity, {"required"}, name="execution_identity")
    _exact_list(
        execution_identity.get("required"),
        EXPECTED_EXECUTION_IDENTITY_FIELDS,
        name="execution identity requirements",
    )
    claim_boundary = _mapping(expansion.get("claim_boundary"), name="claim_boundary")
    _exact_mapping(
        claim_boundary,
        {
            "fresh_execution_authorized": False,
            "historical_development_only": True,
            "product_promotion_eligible": False,
            "public_or_scientific_claim_eligible": False,
            "runtime_or_selection_policy_authority": False,
        },
        name="expansion claim boundary",
    )
    derivation = _mapping(
        expansion.get("deterministic_uncovered_derivation"),
        name="deterministic_uncovered_derivation",
    )
    _exact_mapping(
        derivation,
        {
            "classification_lane_predeclared": True,
            "criterion_comparison": "less_than_or_equal",
            "criterion_rmsd_angstrom": 2.0,
            "derived_from_authenticated_candidate_diagnostics": True,
            "post_result_lane_switch_forbidden": True,
        },
        name="uncovered derivation contract",
    )
    receipts = _mapping(
        expansion.get("failure_complete_receipts"), name="failure_complete_receipts"
    )
    _exact_mapping(
        receipts,
        {
            "complete_candidate_denominator_required_for_preparation_success": True,
            "empty_candidate_list_required_for_preparation_failure": True,
            "mixed_version_rows_rejected": True,
            "typed_preparation_failure_required": True,
        },
        name="failure-complete receipt contract",
    )
    scope = _mapping(expansion.get("scope_identity"), name="scope_identity")
    _exact_keys(
        scope,
        {
            "engineering_smoke_overlap_forbidden",
            "fresh_holdout_overlap_forbidden",
            "historical_registry_case_count",
            "historical_registry_case_ids_sha256",
            "historical_registry_self_sha256",
            "ordered_input_and_uncovered_rosters_required",
        },
        name="scope_identity",
    )
    _verify_self_hash(
        contamination_registry,
        field="registry_sha256",
        name="contamination registry",
    )
    if (
        contamination_registry.get("registry_sha256")
        != EXPECTED_CONTAMINATION_REGISTRY_SHA256
        or contamination_registry.get("contaminated_development_case_ids_sha256")
        != EXPECTED_CONTAMINATION_CASE_IDS_SHA256
        or contamination_registry.get("schema_id")
        != "betelgeuze.engine_v2_public_redocking_contamination_registry/1.1.0"
        or type(contamination_registry.get("contaminated_development_case_count"))
        is not int
        or scope.get("historical_registry_case_count")
        != contamination_registry.get("contaminated_development_case_count")
        or scope.get("historical_registry_case_ids_sha256")
        != contamination_registry.get("contaminated_development_case_ids_sha256")
        or scope.get("historical_registry_self_sha256")
        != contamination_registry.get("registry_sha256")
        or type(scope.get("ordered_input_and_uncovered_rosters_required")) is not bool
        or scope.get("ordered_input_and_uncovered_rosters_required") is not True
        or type(scope.get("engineering_smoke_overlap_forbidden")) is not bool
        or scope.get("engineering_smoke_overlap_forbidden") is not True
        or type(scope.get("fresh_holdout_overlap_forbidden")) is not bool
        or scope.get("fresh_holdout_overlap_forbidden") is not True
    ):
        raise ValueError("historical contamination registry identity drifted")
    fresh_ids = set(_fresh_case_ids(fresh_holdout_manifest))
    if (
        fresh_holdout_manifest.get("manifest_sha256") != EXPECTED_FRESH_MANIFEST_SHA256
        or fresh_holdout_manifest.get("case_ids_sha256")
        != EXPECTED_FRESH_CASE_IDS_SHA256
        or fresh_holdout_manifest.get("schema_id")
        != "betelgeuze.engine_v2_fresh_redocking_holdout_manifest/1.0.0"
        or fresh_holdout_manifest.get("historical_development_case_count")
        != contamination_registry.get("contaminated_development_case_count")
        or fresh_holdout_manifest.get("historical_development_case_ids_sha256")
        != contamination_registry.get("contaminated_development_case_ids_sha256")
        or type(fresh_holdout_manifest.get("result_values_inspected_before_freeze"))
        is not bool
        or fresh_holdout_manifest.get("result_values_inspected_before_freeze")
        is not False
        or set(EXPECTED_THRESHOLD_CASE_IDS) & fresh_ids
        or set(EXPECTED_THRESHOLD_CASE_IDS) & set(EXPECTED_ENGINEERING_SMOKE_CASE_IDS)
    ):
        raise ValueError("cohort scope overlaps smoke or fresh holdout authority")
    taxonomy = _mapping(
        expansion.get("taxonomy_reconciliation"), name="taxonomy_reconciliation"
    )
    _exact_mapping(
        taxonomy,
        {
            "absence_of_evidence_status": "unresolved",
            "allowed_status_per_category_required": True,
            "category_count": 10,
            "deterministic_zero_inclusive_rollups_required": True,
            "self_hash_required": True,
        },
        name="taxonomy reconciliation contract",
    )

    authority = _mapping(policy.get("authority_boundary"), name="authority_boundary")
    _exact_mapping(
        authority,
        EXPECTED_AUTHORITY_BOUNDARY,
        name="cohort policy authority boundary",
    )

    stop_rule = _mapping(
        policy.get("local_refinement_experiment_stop_rule"),
        name="local_refinement_experiment_stop_rule",
    )
    _exact_keys(
        stop_rule,
        {
            "ab_profile",
            "activation_evidence_required_before_run",
            "completed_run_count",
            "decision_logic",
            "execution_authorized",
            "go_criteria_any",
            "invariants_all",
            "new_refinement_versions_prohibited_while_frozen",
            "no_go_criteria_any",
            "no_go_effect",
            "status",
        },
        name="local_refinement_experiment_stop_rule",
    )
    _exact_list(
        stop_rule.get("go_criteria_any"), EXPECTED_GO_CRITERIA, name="go_criteria_any"
    )
    decision_logic = _mapping(stop_rule.get("decision_logic"), name="decision_logic")
    _exact_mapping(
        decision_logic,
        {
            "go_requires_all_invariants": True,
            "go_requires_any_primary_criterion": True,
            "go_requires_no_no_go_trigger": True,
            "no_go_trigger_precedence": True,
        },
        name="local-refinement decision logic",
    )
    _exact_list(
        stop_rule.get("invariants_all"), EXPECTED_INVARIANTS, name="invariants_all"
    )
    _exact_list(
        stop_rule.get("no_go_criteria_any"),
        EXPECTED_NO_GO_CRITERIA,
        name="no_go_criteria_any",
    )
    _exact_list(
        stop_rule.get("new_refinement_versions_prohibited_while_frozen"),
        ("V9", "V10"),
        name="prohibited refinement versions",
    )
    ab_profile = _mapping(stop_rule.get("ab_profile"), name="ab_profile")
    expected_ab_profile = {
        "baseline": "current_v7",
        "baseline_top1_recovery_case_ids": list(EXPECTED_BASELINE_RECOVERY_CASE_IDS),
        "baseline_top5_recovery_case_ids": list(EXPECTED_BASELINE_RECOVERY_CASE_IDS),
        "candidate_denominator": 512,
        "candidate_slots_per_scored_case": 64,
        "clearance_policy_sha256": EXPECTED_CLEARANCE_POLICY_SHA256,
        "experimental": (
            "current_v7_with_only_predeclared_clearance_shadow_selected_states_replaced"
        ),
        "historical_archive_sha256": EXPECTED_SOURCE_PAIRED_ARCHIVE_SHA256,
        "historical_case_count": 9,
        "historical_case_ids": list(EXPECTED_SOURCE_PAIRED_CASE_IDS),
        "historical_case_ids_sha256": EXPECTED_SOURCE_PAIRED_CASE_IDS_SHA256,
        "maximum_lifetime_run_count": 1,
        "preparation_failure_case_count": 1,
        "preparation_failure_case_ids": list(EXPECTED_PREPARATION_FAILURE_CASE_IDS),
        "previously_uncovered_case_ids": list(EXPECTED_ADMITTED_CASE_IDS),
        "scored_case_count": 8,
        "source_control_required": True,
    }
    _exact_mapping(
        ab_profile,
        expected_ab_profile,
        name="local-refinement A/B profile",
    )
    if (
        stop_rule.get("status")
        != "frozen_pending_source_paired_clearance_activation_and_single_ab"
        or type(stop_rule.get("activation_evidence_required_before_run")) is not bool
        or stop_rule.get("activation_evidence_required_before_run") is not True
        or type(stop_rule.get("execution_authorized")) is not bool
        or stop_rule.get("execution_authorized") is not False
        or type(stop_rule.get("completed_run_count")) is not int
        or stop_rule.get("completed_run_count") != 0
        or stop_rule.get("no_go_effect")
        != "close_local_torsion_clearance_refinement_epic"
    ):
        raise ValueError("local-refinement stop rule is not frozen")
    if policy.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise ValueError("cohort policy is not the pinned identity")


def _parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=repo_root / "config/engine_v2_phase25_cohort_admission.json",
    )
    parser.add_argument(
        "--threshold-source-map",
        "--threshold-authority",
        dest="threshold_source_map",
        type=Path,
        default=repo_root
        / "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
        help=(
            "pinned Stage 0 threshold-proposal source-map artifact; "
            "--threshold-authority is a deprecated compatibility alias"
        ),
    )
    parser.add_argument(
        "--contamination-registry",
        type=Path,
        default=repo_root
        / "config/engine_v2_public_redocking_contamination_registry.json",
    )
    parser.add_argument(
        "--fresh-holdout-manifest",
        type=Path,
        default=repo_root / "config/engine_v2_fresh_redocking_holdout_manifest.json",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        policy = _load_json(arguments.policy, name="cohort policy")
        threshold = _load_json(
            arguments.threshold_source_map, name="threshold proposal source map"
        )
        registry = _load_json(
            arguments.contamination_registry, name="contamination registry"
        )
        fresh_manifest = _load_json(
            arguments.fresh_holdout_manifest,
            name="fresh holdout manifest",
        )
        verify_policy(policy, threshold, registry, fresh_manifest)
    except ValueError as exc:
        print(f"engine-v2 Phase 2.5 cohort admission verification failed: {exc}")
        return 1
    print(f"verified {policy['policy_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
