#!/usr/bin/env python3
"""Verify the fixed contaminated-development global-orientation protocol."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping

from betelgeuze_engine_v2.docking.global_orientation import (
    GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID,
    GLOBAL_ORIENTATION_GENERATOR_ID,
    GlobalOrientationConfig,
    generate_global_orientation_batch,
)


SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_contaminated_development_protocol/1.1.0"
)
CASE_IDS = (
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
UNCOVERED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
SOURCE_RECEIPT_FIELDS = (
    "case_id",
    "source_case_member_receipt_sha256",
    "authenticated_input_receipt_sha256",
    "receptor_coordinate_sha256",
    "ligand_coordinate_sha256",
    "ligand_topology_sha256",
    "pocket_declaration_sha256",
    "preparation_policy_sha256",
)
ALLOWED_INPUTS = (
    "prepared_ligand_coordinates",
    "declared_pocket_center",
    "declared_pocket_normal",
    "bounded_receptor_surface_points",
    "frozen_global_orientation_config",
    "source_receipt_sha256",
    "profile_id",
)
FORBIDDEN_INPUTS = (
    "native_pose",
    "reference_pose",
    "rmsd",
    "candidate_score",
    "prior_benchmark_outcome",
    "fresh_holdout_identity",
    "product_routing_state",
)
AUTHORITY_KEYS = (
    "historical_development_execution_authorized",
    "fresh_holdout_execution_authorized",
    "stage0_admission_authority",
    "profile_promotion_authority",
    "product_execution_authorized",
    "customer_pose_emission_authorized",
    "public_or_scientific_claim_authorized",
)


class GlobalOrientationDevelopmentProtocolError(ValueError):
    """Raised when the fixed development protocol fails closed."""


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
    if not isinstance(value, dict):
        raise GlobalOrientationDevelopmentProtocolError(f"{name} must be an object")
    return value


def _exact(value: object, expected: object, *, name: str) -> None:
    if value != expected:
        raise GlobalOrientationDevelopmentProtocolError(f"{name} drifted")


def load_protocol(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"protocol is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GlobalOrientationDevelopmentProtocolError(
            "protocol must be a JSON object"
        )
    return payload


def _verify_generator_boundary() -> None:
    parameters = tuple(inspect.signature(generate_global_orientation_batch).parameters)
    _exact(
        parameters,
        (
            "ligand_coordinates",
            "pocket_center",
            "pocket_normal",
            "receptor_surface_points",
            "config",
            "source_receipt_sha256",
            "profile_id",
        ),
        name="generator signature",
    )
    forbidden_tokens = (
        "native",
        "reference",
        "rmsd",
        "score",
        "benchmark",
        "fresh",
        "product",
    )
    if any(
        token in parameter.lower()
        for parameter in parameters
        for token in forbidden_tokens
    ):
        raise GlobalOrientationDevelopmentProtocolError(
            "generator signature exposes forbidden information"
        )


def _verify_synthetic_contract_binding(
    source_bindings: Mapping[str, Any],
) -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "config/engine_v2_global_orientation_synthetic_contract.json"
    )
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"synthetic contract is not readable JSON: {exc}"
        ) from exc
    if not isinstance(contract, dict):
        raise GlobalOrientationDevelopmentProtocolError(
            "synthetic contract must be a JSON object"
        )
    projection = dict(contract)
    observed_hash = projection.pop("contract_sha256", None)
    _exact(
        contract.get("schema_id"),
        source_bindings.get("global_orientation_synthetic_contract_schema_id"),
        name="live synthetic contract schema binding",
    )
    _exact(
        observed_hash,
        _sha256(projection),
        name="live synthetic contract self-hash",
    )
    _exact(
        observed_hash,
        source_bindings.get("global_orientation_synthetic_contract_sha256"),
        name="live synthetic contract hash binding",
    )


def _verify_phase25_policy_binding(
    source_bindings: Mapping[str, Any],
) -> None:
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "config/engine_v2_phase25_cohort_admission.json"
    )
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"phase 2.5 policy is not readable JSON: {exc}"
        ) from exc
    if not isinstance(policy, dict):
        raise GlobalOrientationDevelopmentProtocolError(
            "phase 2.5 policy must be a JSON object"
        )
    projection = dict(policy)
    observed_hash = projection.pop("policy_sha256", None)
    _exact(
        policy.get("schema_id"),
        source_bindings.get("phase25_policy_schema_id"),
        name="live phase 2.5 policy schema binding",
    )
    _exact(
        observed_hash,
        _sha256(projection),
        name="live phase 2.5 policy self-hash",
    )
    _exact(
        observed_hash,
        source_bindings.get("phase25_policy_sha256"),
        name="live phase 2.5 policy hash binding",
    )


def verify_protocol(protocol: Mapping[str, Any]) -> str:
    expected_top_keys = {
        "arm_contract",
        "authority",
        "cohort",
        "decision",
        "execution_gate",
        "information_boundary",
        "metrics",
        "protocol_role",
        "protocol_sha256",
        "schema_id",
        "shared_execution_contract",
        "source_bindings",
        "status",
    }
    _exact(set(protocol), expected_top_keys, name="protocol key set")
    _exact(protocol.get("schema_id"), SCHEMA_ID, name="protocol schema")
    _exact(
        protocol.get("status"),
        "frozen_protocol_only_execution_blocked",
        name="protocol status",
    )
    _exact(
        protocol.get("protocol_role"),
        "fixed_historical_contaminated_development_global_orientation_ab",
        name="protocol role",
    )
    projection = dict(protocol)
    observed_hash = projection.pop("protocol_sha256", None)
    expected_hash = _sha256(projection)
    _exact(observed_hash, expected_hash, name="protocol self-hash")

    cohort = _mapping(protocol.get("cohort"), name="cohort")
    _exact(
        tuple(cohort.get("historical_case_ids", ())), CASE_IDS, name="historical cohort"
    )
    _exact(cohort.get("historical_case_count"), 9, name="historical count")
    _exact(
        cohort.get("historical_case_ids_sha256"),
        _sha256(list(CASE_IDS)),
        name="historical cohort hash",
    )
    _exact(cohort.get("scored_case_count"), 8, name="scored count")
    _exact(
        tuple(cohort.get("preparation_failure_case_ids", ())),
        ("6M73_FNR",),
        name="preparation-failure roster",
    )
    _exact(
        tuple(cohort.get("baseline_recovered_case_ids", ())),
        ("6T88_MWQ",),
        name="baseline-recovered roster",
    )
    _exact(
        tuple(cohort.get("previously_uncovered_case_ids", ())),
        UNCOVERED_CASE_IDS,
        name="previously-uncovered roster",
    )
    _exact(
        cohort.get("previously_uncovered_case_count"),
        7,
        name="previously-uncovered count",
    )

    sources = _mapping(protocol.get("source_bindings"), name="source_bindings")
    expected_sources = {
        "source_commit_git_sha1": "754bebb9ddc2fbffdaca5d4143ff515c3b38c032",
        "historical_archive_sha256": "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc",
        "historical_member_manifest_sha256": "7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21",
        "historical_bundle_checksum_sha256": "6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9",
        "phase25_policy_schema_id": "betelgeuze.engine_v2_phase25_cohort_admission/1.3.0",
        "phase25_policy_sha256": "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211",
        "global_orientation_synthetic_contract_schema_id": "betelgeuze.engine_v2_global_orientation_synthetic_contract/2.0.0",
        "global_orientation_synthetic_contract_sha256": "02fa37a94f3c1719f5e7b5b808c71d053e313b018ef9bfa7d904869c2ab1dad0",
        "case_source_receipt_schema_id": "betelgeuze.engine_v2_source_paired_clearance_"
        "case_source_receipt/1.0.0",
        "exact_case_source_receipt_required": True,
        "source_receipt_required_fields": list(SOURCE_RECEIPT_FIELDS),
        "source_receipts_committed": False,
        "source_receipt_absence_blocks_execution": True,
    }
    _exact(dict(sources), expected_sources, name="source bindings")
    _verify_phase25_policy_binding(sources)
    _verify_synthetic_contract_binding(sources)

    information = _mapping(
        protocol.get("information_boundary"), name="information_boundary"
    )
    _exact(
        tuple(information.get("generator_allowed_inputs", ())),
        ALLOWED_INPUTS,
        name="generator allowed inputs",
    )
    _exact(
        tuple(information.get("generator_forbidden_inputs", ())),
        FORBIDDEN_INPUTS,
        name="generator forbidden inputs",
    )
    _exact(
        information.get("reference_pose_consumed_only_after_candidate_generation"),
        True,
        name="reference-pose boundary",
    )
    _exact(
        information.get("post_result_candidate_allocation_forbidden"),
        True,
        name="post-result allocation boundary",
    )
    _verify_generator_boundary()

    shared = _mapping(
        protocol.get("shared_execution_contract"),
        name="shared_execution_contract",
    )
    _exact(
        dict(shared),
        {
            "preparation_policy": "exact_source_paired_current_v7_preparation",
            "conformer_authority": "same_prepared_ligand_for_both_arms",
            "scorer_backend": "rust_cpu_required",
            "scorer_terms_schema_id": "betelgeuze.engine_v2_scorer_v1_terms/1.1.0",
            "posebusters_version": "0.3.1",
            "posebusters_check_count": 22,
            "rmsd_contract": "symmetry_aware_heavy_atom_rmsd_angstrom",
            "rmsd_threshold_angstrom": 2.0,
            "seed": 2026080601,
            "cpu_count": 1,
            "native_scorer_threads": 1,
            "torch_intraop_threads": 1,
            "torch_interop_threads": 1,
        },
        name="shared execution contract",
    )

    arms = _mapping(protocol.get("arm_contract"), name="arm_contract")
    _exact(
        tuple(arms.get("arm_ids", ())),
        ("baseline_current_v7", "experimental_global_orientation_v1"),
        name="arm identities",
    )
    _exact(
        arms.get("baseline"),
        {"proposal_authority": "current_v7", "candidate_slot_count": 64},
        name="baseline arm",
    )
    experimental = _mapping(arms.get("experimental"), name="experimental arm")
    _exact(
        experimental.get("proposal_authority"),
        GLOBAL_ORIENTATION_GENERATOR_ID,
        name="experimental proposal authority",
    )
    config = _mapping(
        experimental.get("generator_config"),
        name="experimental generator config",
    )
    _exact(
        config.get("schema_id"),
        GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID,
        name="experimental config schema",
    )
    concrete = GlobalOrientationConfig(
        orientation_count=config.get("orientation_count"),
        translation_shell_radii=tuple(config.get("translation_shell_radii", ())),
        translation_points_per_shell=config.get("translation_points_per_shell"),
        minimum_receptor_distance=config.get("minimum_receptor_distance"),
    )
    _exact(concrete.candidate_slot_count, 64, name="experimental denominator")
    _exact(
        experimental.get("candidate_slot_count"),
        64,
        name="experimental candidate count",
    )
    _exact(
        experimental.get("candidate_slot_formula"),
        "orientation_count*(1+translation_shell_count*translation_points_per_shell)",
        name="candidate formula",
    )
    for key, expected in {
        "candidate_slots_per_scored_case_per_arm": 64,
        "expected_scored_candidate_rows_per_arm": 512,
        "expected_scored_candidate_rows_combined": 1024,
        "denominators_identical_required": True,
        "failed_candidate_slots_retained": True,
        "failed_preparation_rows_retained": True,
        "same_prepared_ligand_required": True,
        "same_pocket_required": True,
        "same_scorer_required": True,
        "same_candidate_budget_required": True,
    }.items():
        _exact(arms.get(key), expected, name=f"arm_contract.{key}")

    metrics = _mapping(protocol.get("metrics"), name="metrics")
    _exact(
        tuple(metrics.get("failure_classes", ())),
        ("success", "proposal_failure", "validity_failure", "ranking_failure"),
        name="failure classes",
    )
    _exact(tuple(metrics.get("top_k", ())), (1, 5), name="Top-K")
    _exact(
        tuple(metrics.get("required_per_case", ())),
        (
            "proposal_oracle_rmsd",
            "valid_proposal_oracle_rmsd",
            "ranked_top1_oracle_rmsd",
            "ranked_top5_oracle_rmsd",
            "selected_top1_rmsd",
            "selection_regret",
            "generated_candidate_count",
            "accepted_candidate_count",
            "rejected_candidate_count",
            "failure_class",
        ),
        name="required per-case metrics",
    )
    for key in (
        "full_observation_rederivation_required",
        "source_geometry_rederivation_required",
        "summary_rederived_from_complete_case_receipts",
    ):
        _exact(metrics.get(key), True, name=f"metrics.{key}")

    decision = _mapping(protocol.get("decision"), name="decision")
    _exact(
        decision.get("go_requires_all_invariants"),
        True,
        name="Go invariant requirement",
    )
    _exact(
        decision.get("result_cannot_change_protocol"), True, name="result independence"
    )
    _exact(
        tuple(decision.get("invariants_all", ())),
        (
            "complete_source_receipts_for_all_nine_cases",
            "identical_failure_complete_64_slot_denominators",
            "no_reference_or_result_dependent_generator_input",
            "no_preparation_failure_regression",
            "no_baseline_recovered_case_regression",
            "complete_source_and_observation_rederivation",
        ),
        name="decision invariants",
    )
    _exact(
        tuple(decision.get("go_criteria_all", ())),
        (
            "valid_proposal_oracle_recovery_in_at_least_2_of_7_"
            "previously_uncovered_cases",
            "no_increase_in_invalid_selected_top1_count",
        ),
        name="Go criteria",
    )
    _exact(
        tuple(decision.get("hard_no_go_any", ())),
        (
            "required_invariant_failed",
            "zero_new_previously_uncovered_valid_proposal_recoveries",
            "baseline_recovered_case_regression",
            "candidate_denominator_or_source_binding_drift",
        ),
        name="hard No-Go criteria",
    )
    _exact(
        decision.get("go_effect"),
        "permit_separate_review_of_global_orientation_development_followup_only",
        name="Go effect",
    )
    _exact(
        decision.get("no_go_effect"),
        "retain_synthetic_only_global_orientation_and_"
        "close_molecular_execution_request",
        name="No-Go effect",
    )

    gate = _mapping(protocol.get("execution_gate"), name="execution_gate")
    _exact(
        dict(gate),
        {
            "pr245_reviewed_terminal_state_required": True,
            "separate_execution_authority_required": True,
            "operator_reservation_required": True,
            "actual_execution_authorized": False,
            "output_root": ".betelgeuze/engine_v2_global_orientation_"
            "contaminated_development",
            "owner_only_directory_mode_octal": "0700",
            "owner_only_receipt_mode_octal": "0600",
        },
        name="execution gate",
    )
    authority = _mapping(protocol.get("authority"), name="authority")
    _exact(set(authority), set(AUTHORITY_KEYS), name="authority key set")
    if any(authority.get(key) is not False for key in AUTHORITY_KEYS):
        raise GlobalOrientationDevelopmentProtocolError(
            "all execution, product, promotion, and claim authority must remain false"
        )
    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1] / "config/engine_v2_global_orientation_"
            "contaminated_development.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    print(verify_protocol(load_protocol(arguments.protocol)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
