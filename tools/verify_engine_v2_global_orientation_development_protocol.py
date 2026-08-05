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
    GLOBAL_ORIENTATION_GENERATOR_ID,
    GlobalOrientationConfig,
    generate_global_orientation_batch,
)

SCHEMA_ID = "betelgeuze.engine_v2_global_orientation_development_protocol/1.0.0"
STATUS = "frozen_not_execution_authorized"
CASE_IDS = (
    "5SD5_HWI", "5SIS_JSM", "6M2B_EZO", "6M73_FNR", "6T88_MWQ",
    "6TW5_9M2", "6TW7_NZB", "6VTA_AKN", "6WTN_RXT",
)
SCORED = (
    "5SD5_HWI", "5SIS_JSM", "6M2B_EZO", "6T88_MWQ",
    "6TW5_9M2", "6TW7_NZB", "6VTA_AKN", "6WTN_RXT",
)
UNCOVERED = (
    "5SD5_HWI", "5SIS_JSM", "6M2B_EZO", "6TW5_9M2",
    "6TW7_NZB", "6VTA_AKN", "6WTN_RXT",
)
CASE_IDS_SHA256 = "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
DEPENDENCIES = {
    "activation_policy_schema_id": "betelgeuze.engine_v2_source_paired_clearance_activation_policy/1.2.0",
    "activation_policy_sha256": "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c",
    "global_orientation_synthetic_contract_schema_id": "betelgeuze.engine_v2_global_orientation_synthetic_contract/1.1.0",
    "global_orientation_synthetic_contract_sha256": "b86059aca76425aacc7a2cc28bac98e9ce87f026b399c6a839e9560ff7332a44",
    "historical_archive_sha256": "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc",
    "historical_case_source_authority_sha256": "4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc",
    "phase25_policy_schema_id": "betelgeuze.engine_v2_phase25_cohort_admission/1.3.0",
    "phase25_policy_sha256": "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211",
    "posebusters_version": "0.3.1",
    "scorer_v1_terms_schema_id": "betelgeuze.engine_v2_scorer_v1_terms/1.1.0",
}
METRICS = (
    "proposal_oracle", "valid_proposal_oracle", "ranked_top_k_oracle",
    "selected_top1", "selection_regret", "rejected_candidate_count",
    "failure_class",
)
FAILURE_CLASSES = ("success", "proposal_failure", "validity_failure", "ranking_failure")
INVARIANTS = (
    "exact_source_receipts_complete",
    "baseline_and_experimental_denominators_equal",
    "no_preparation_failure_regression",
    "no_reference_or_result_dependent_generator_input",
    "all_candidate_slots_failure_complete",
    "all_metrics_independently_rederived",
    "baseline_recovered_case_not_regressed",
)
PRIMARY = (
    "selected_exact_valid_recovery_in_previously_uncovered_case",
    "proposal_oracle_recovery_at_least_2_of_8",
    "valid_proposal_oracle_recovery_at_least_2_of_8",
)
HARD_NO_GO = (
    "required_invariant_failed", "all_primary_go_criteria_failed",
    "baseline_recovered_case_regressed", "candidate_denominator_mismatch",
    "reference_or_result_dependent_generator_input_detected",
)
STOP_RULES = (
    "stop_on_source_identity_mismatch", "stop_on_denominator_mismatch",
    "stop_on_reference_leakage", "stop_on_nonrederivable_evidence",
)
AUTHORITY_KEYS = (
    "customer_pose_emission_authorized", "fresh_holdout_execution_authorized",
    "historical_execution_authorized", "product_execution_authorized",
    "profile_promotion_authority", "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
)


class GlobalOrientationDevelopmentProtocolError(ValueError):
    """Raised when the fixed protocol fails closed."""


def _bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _map(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise GlobalOrientationDevelopmentProtocolError(f"{name} must be an object")
    return value


def _list(value: object, name: str) -> tuple[Any, ...]:
    if not isinstance(value, list):
        raise GlobalOrientationDevelopmentProtocolError(f"{name} must be a list")
    return tuple(value)


def _require_exact(value: object, expected: object, message: str) -> None:
    if value != expected:
        raise GlobalOrientationDevelopmentProtocolError(message)


def load_protocol(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"protocol is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GlobalOrientationDevelopmentProtocolError("protocol must be an object")
    return payload


def _verify_dependency_files(root: Path) -> None:
    rows = (
        ("engine_v2_global_orientation_synthetic_contract.json", "schema_id",
         DEPENDENCIES["global_orientation_synthetic_contract_schema_id"],
         "contract_sha256", DEPENDENCIES["global_orientation_synthetic_contract_sha256"]),
        ("engine_v2_phase25_cohort_admission.json", "schema_id",
         DEPENDENCIES["phase25_policy_schema_id"], "policy_sha256",
         DEPENDENCIES["phase25_policy_sha256"]),
        ("engine_v2_source_paired_clearance_activation.json", "schema_id",
         DEPENDENCIES["activation_policy_schema_id"], "policy_sha256",
         DEPENDENCIES["activation_policy_sha256"]),
    )
    for filename, schema_key, schema, hash_key, identity in rows:
        path = root / "config" / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GlobalOrientationDevelopmentProtocolError(
                f"frozen dependency is unreadable: {filename}"
            ) from exc
        if not isinstance(payload, dict):
            raise GlobalOrientationDevelopmentProtocolError(
                f"frozen dependency is not an object: {filename}"
            )
        _require_exact(payload.get(schema_key), schema, f"dependency schema drifted: {filename}")
        _require_exact(payload.get(hash_key), identity, f"dependency identity drifted: {filename}")


def verify_protocol(protocol: Mapping[str, Any], *, repo_root: Path | None = None) -> str:
    _require_exact(
        set(protocol),
        {"arms", "authority", "cohort", "decision", "evaluation",
         "frozen_dependencies", "protocol_sha256", "schema_id", "status"},
        "protocol key set is invalid",
    )
    _require_exact(protocol.get("schema_id"), SCHEMA_ID, "protocol schema is invalid")
    _require_exact(protocol.get("status"), STATUS, "protocol status is invalid")
    projection = dict(protocol)
    observed_hash = projection.pop("protocol_sha256", None)
    expected_hash = _sha(projection)
    _require_exact(observed_hash, expected_hash, "protocol self-hash is invalid")

    dependencies = _map(protocol.get("frozen_dependencies"), "frozen_dependencies")
    _require_exact(dict(dependencies), DEPENDENCIES, "frozen dependency identities drifted")
    if repo_root is not None:
        _verify_dependency_files(repo_root.resolve(strict=True))

    cohort = _map(protocol.get("cohort"), "cohort")
    _require_exact(
        set(cohort),
        {"baseline_recovered_case_ids", "case_count", "case_ids_sha256",
         "cohort_kind", "exact_case_source_receipt_required",
         "fresh_holdout_overlap_allowed", "ordered_case_ids",
         "preparation_failure_case_ids", "previously_uncovered_case_ids",
         "scored_case_count", "scored_case_ids"},
        "cohort key set is invalid",
    )
    ordered = _list(cohort.get("ordered_case_ids"), "ordered_case_ids")
    scored = _list(cohort.get("scored_case_ids"), "scored_case_ids")
    uncovered = _list(cohort.get("previously_uncovered_case_ids"), "previously_uncovered_case_ids")
    failed = _list(cohort.get("preparation_failure_case_ids"), "preparation_failure_case_ids")
    recovered = _list(cohort.get("baseline_recovered_case_ids"), "baseline_recovered_case_ids")
    _require_exact(ordered, CASE_IDS, "historical case roster drifted")
    _require_exact(cohort.get("case_ids_sha256"), CASE_IDS_SHA256, "case roster identity drifted")
    _require_exact(_sha(list(ordered)), CASE_IDS_SHA256, "case roster cannot be rederived")
    _require_exact(cohort.get("case_count"), 9, "historical case count drifted")
    _require_exact(scored, SCORED, "scored case roster drifted")
    _require_exact(cohort.get("scored_case_count"), 8, "scored case count drifted")
    _require_exact(failed, ("6M73_FNR",), "preparation-failure roster drifted")
    _require_exact(uncovered, UNCOVERED, "previously-uncovered roster drifted")
    _require_exact(recovered, ("6T88_MWQ",), "baseline recovery roster drifted")
    _require_exact(set(scored), set(uncovered) | set(recovered), "scored partition is invalid")
    if set(scored) & set(failed):
        raise GlobalOrientationDevelopmentProtocolError("scored and failed rosters overlap")
    _require_exact(cohort.get("cohort_kind"), "historical_contaminated_development", "cohort kind drifted")
    _require_exact(cohort.get("exact_case_source_receipt_required"), True, "source receipts must be required")
    _require_exact(cohort.get("fresh_holdout_overlap_allowed"), False, "fresh overlap must remain forbidden")

    arms = _map(protocol.get("arms"), "arms")
    _require_exact(set(arms), {"baseline", "experimental", "shared_contract"}, "arm key set is invalid")
    baseline = _map(arms.get("baseline"), "baseline")
    _require_exact(dict(baseline), {
        "arm_id": "current_v7_frozen", "candidate_denominator": 512,
        "candidate_slots_per_scored_case": 64,
        "proposal_policy": "current_v7_source_paired_frozen",
    }, "baseline arm drifted")
    experimental = _map(arms.get("experimental"), "experimental")
    _require_exact(
        set(experimental),
        {"arm_id", "candidate_denominator", "candidate_formula",
         "candidate_slots_per_scored_case", "generator_id",
         "minimum_receptor_distance_angstrom", "orientation_count",
         "translation_points_per_shell", "translation_shell_radii_angstrom"},
        "experimental arm key set is invalid",
    )
    _require_exact(experimental.get("arm_id"), "global_orientation_v1_frozen", "experimental arm identity drifted")
    _require_exact(experimental.get("generator_id"), GLOBAL_ORIENTATION_GENERATOR_ID, "generator identity drifted")
    _require_exact(
        experimental.get("candidate_formula"),
        "orientation_count*(1+shell_count*translation_points_per_shell)",
        "candidate formula drifted",
    )
    try:
        config = GlobalOrientationConfig(
            orientation_count=experimental.get("orientation_count"),
            translation_shell_radii=tuple(experimental.get("translation_shell_radii_angstrom", ())),
            translation_points_per_shell=experimental.get("translation_points_per_shell"),
            minimum_receptor_distance=experimental.get("minimum_receptor_distance_angstrom"),
        )
    except (TypeError, ValueError) as exc:
        raise GlobalOrientationDevelopmentProtocolError("experimental config is invalid") from exc
    _require_exact(config.candidate_slot_count, 64, "experimental candidate budget is not 64")
    _require_exact(experimental.get("candidate_slots_per_scored_case"), 64, "per-case denominator drifted")
    _require_exact(experimental.get("candidate_denominator"), 512, "total denominator drifted")
    _require_exact(config.candidate_slot_count * len(scored), 512, "denominator cannot be rederived")
    _require_exact(baseline.get("candidate_denominator"), 512, "arm denominators differ")

    shared = _map(arms.get("shared_contract"), "shared_contract")
    true_keys = {"same_candidate_denominator", "same_charge_policy", "same_conformer_inputs",
                 "same_pocket_declaration", "same_preparation", "same_scorer_backend"}
    false_keys = {"benchmark_outcome_input_to_generator_allowed",
                  "prior_score_input_to_generator_allowed",
                  "reference_pose_input_to_generator_allowed",
                  "rmsd_input_to_generator_allowed"}
    _require_exact(set(shared), true_keys | false_keys, "shared contract key set is invalid")
    for key in true_keys:
        _require_exact(shared.get(key), True, f"{key} must remain true")
    for key in false_keys:
        _require_exact(shared.get(key), False, f"{key} must remain false")

    parameters = tuple(inspect.signature(generate_global_orientation_batch).parameters)
    _require_exact(
        parameters,
        ("ligand_coordinates", "pocket_center", "pocket_normal",
         "receptor_surface_points", "config"),
        "generator signature drifted",
    )
    forbidden = ("native", "reference", "rmsd", "score", "benchmark", "fresh", "product")
    if any(fragment in parameter.lower() for parameter in parameters for fragment in forbidden):
        raise GlobalOrientationDevelopmentProtocolError("generator signature contains forbidden information")

    evaluation = _map(protocol.get("evaluation"), "evaluation")
    _require_exact(
        set(evaluation),
        {"all_failed_candidate_rows_retained", "all_failed_preparation_rows_retained",
         "failure_classes", "full_observation_rederivation_required", "ranked_top_k",
         "required_metrics", "rmsd_threshold_angstrom", "source_rederivation_required"},
        "evaluation key set is invalid",
    )
    _require_exact(evaluation.get("rmsd_threshold_angstrom"), 2.0, "RMSD threshold drifted")
    _require_exact(_list(evaluation.get("ranked_top_k"), "ranked_top_k"), (1, 5), "Top-K drifted")
    _require_exact(_list(evaluation.get("required_metrics"), "required_metrics"), METRICS, "metrics drifted")
    _require_exact(_list(evaluation.get("failure_classes"), "failure_classes"), FAILURE_CLASSES, "failure classes drifted")
    for key in ("all_failed_candidate_rows_retained", "all_failed_preparation_rows_retained",
                "full_observation_rederivation_required", "source_rederivation_required"):
        _require_exact(evaluation.get(key), True, f"{key} must remain true")

    decision = _map(protocol.get("decision"), "decision")
    _require_exact(
        set(decision),
        {"actual_execution_requires_pr_245_reviewed_terminal_state",
         "go_requires_all_invariants", "go_requires_any_primary_criterion",
         "hard_no_go_criteria_any", "invariants_all",
         "primary_go_criteria_any", "stop_rules"},
        "decision key set is invalid",
    )
    _require_exact(decision.get("go_requires_all_invariants"), True, "all invariants must be required")
    _require_exact(decision.get("go_requires_any_primary_criterion"), True, "one primary criterion must be required")
    _require_exact(
        decision.get("actual_execution_requires_pr_245_reviewed_terminal_state"),
        True, "PR #245 terminal-state dependency must remain required",
    )
    _require_exact(_list(decision.get("invariants_all"), "invariants_all"), INVARIANTS, "invariants drifted")
    _require_exact(_list(decision.get("primary_go_criteria_any"), "primary_go_criteria_any"), PRIMARY, "primary criteria drifted")
    _require_exact(_list(decision.get("hard_no_go_criteria_any"), "hard_no_go_criteria_any"), HARD_NO_GO, "hard No-Go criteria drifted")
    _require_exact(_list(decision.get("stop_rules"), "stop_rules"), STOP_RULES, "stop rules drifted")

    authority = _map(protocol.get("authority"), "authority")
    _require_exact(set(authority), set(AUTHORITY_KEYS), "authority key set is invalid")
    for key in AUTHORITY_KEYS:
        _require_exact(authority.get(key), False, f"{key} must remain false")
    return expected_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve(strict=True)
    path = args.protocol or root / "config/engine_v2_global_orientation_development_protocol.json"
    print(verify_protocol(load_protocol(path), repo_root=root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
