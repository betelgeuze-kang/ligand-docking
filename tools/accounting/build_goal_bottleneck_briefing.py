#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_goal_operator_action_board import DEFAULT_OUT_JSON as DEFAULT_ACTION_BOARD_JSON
from tools.build_goal_operator_intake_kit import DEFAULT_OUT_JSON as DEFAULT_INTAKE_KIT_JSON
from tools.build_goal_release_burndown_work_order import DEFAULT_OUT_JSON as DEFAULT_BURNDOWN_JSON
from tools.build_goal_release_decision_gate import DEFAULT_OUT_JSON as DEFAULT_RELEASE_GATE_JSON

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPLETION_AUDIT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_JSON = (
    "runs/engine_refinement_claim_evidence_priority_packet_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON = "runs/product_public_benchmark_work_order_current.json"
DEFAULT_PUBLIC_BENCHMARK_PREFLIGHT_JSONS = [
    "runs/dude_z_decoy_smoke_product_inputs_current.json",
    "runs/pdbbind_casf_pose_affinity_product_preflight_current.json",
    "runs/protein_protein_docking_benchmark_v5_product_preflight_current.json",
    "runs/casp_archive_structure_regression_product_preflight_current.json",
]
DEFAULT_OUT_JSON = "runs/goal_bottleneck_briefing_current.json"
DEFAULT_OUT_CSV = "runs/goal_bottleneck_briefing_current.csv"
DEFAULT_OUT_MD = "runs/goal_bottleneck_briefing_current.md"

CLAIM_BOUNDARY = (
    "Goal bottleneck briefing only; it consolidates release blockers, burndown phases, operator intake templates, "
    "approval tokens, required inputs, and cleanup sizes from existing local artifacts. It does not approve tokens, "
    "fill intake files, run docking, install packages, submit CAMEO predictions, register servers, send email, delete, "
    "archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return _split_semicolon(value)


def _unique(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in _split_semicolon(value):
            if part in seen:
                continue
            seen.add(part)
            output.append(part)
    return output


def _join(values: list[Any]) -> str:
    return ";".join(_unique(values))


FULL_COMMERCIAL_EVIDENCE_RECEIPT_INTAKE_FIELDS = (
    "entry_count",
    "operator_input_required_count",
    "current_action_required_count",
    "template_required_count",
    "template_present_count",
    "approval_token_count",
    "entry_ids",
    "source_gate_statuses",
    "required_inputs",
    "approval_tokens",
)

PRIMARY_FULL_COMMERCIAL_RELEASE_BLOCKER_INTAKE_FIELDS = (
    "id",
    "requirement_id",
    "tier",
    "blocked_row_count",
    "first_blocked_evidence_row_id",
    "receipt_csv",
    "approval_token_required",
    "next_required_step",
)

PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_INTAKE_FIELDS = (
    "source_json",
    "status",
    "packet_ready",
    "registry_promotion_ready",
    "operator_input_required_count",
    "blocked_priority_item_count",
    "missing_gate_count",
    "missing_gate_ids",
    "observed_registry_trained_model_checkpoint_count",
    "top_gate_id",
    "top_priority_bucket",
    "top_required_input",
    "top_acceptance_artifact",
    "top_verification_command",
    "top_next_operator_step",
    "model_promoted",
    "customer_facing_mutation_enabled",
    "external_state_mutated",
)

PRODUCT_SCOPE_BREADTH_EVIDENCE_PRIORITY_INTAKE_FIELDS = (
    "source_json",
    "status",
    "packet_ready",
    "scope_promotion_allowed",
    "authoritative_apply_allowed",
    "queue_item_count",
    "open_item_count",
    "scientific_evidence_request_count",
    "local_crosscheck_candidate_count",
    "external_primary_exact_evidence_required_count",
    "review_only_keep_blocked_count",
    "top_item_id",
    "top_domain",
    "top_bucket",
    "top_required_evidence_type",
    "top_review_template_artifact",
    "top_apply_gate_artifact",
    "top_next_step",
    "external_state_mutated",
)

ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_FIELDS = (
    "source_json",
    "status",
    "priority_packet_ready",
    "claim_promotion_allowed",
    "claim_evidence_receipt_ready",
    "claim_evidence_receipt_status",
    "priority_item_count",
    "operator_input_required_count",
    "blocked_priority_item_count",
    "required_blocker_count",
    "missing_required_blocker_count",
    "blocker_count",
    "public_benchmark_gate_ready",
    "public_benchmark_status",
    "top_blocker_id",
    "top_priority_bucket",
    "top_required_input",
    "top_acceptance_artifact",
    "top_verification_command",
    "top_next_operator_step",
    "public_benchmark_materialized_candidate_ready",
    "public_benchmark_materialized_metric_ready",
    "public_benchmark_materialized_apply_ready",
    "public_benchmark_materialized_apply_status",
    "public_benchmark_materialized_work_order_row_count",
    "public_benchmark_materialized_metric_evidence_pass_row_count",
    "public_benchmark_materialized_metric_evidence_blocked_row_count",
    "public_benchmark_materialized_free_energy_pair_count",
    "public_benchmark_materialized_free_energy_spearman",
    "public_benchmark_materialized_free_energy_spearman_bootstrap_p05",
    "public_benchmark_materialized_free_energy_spearman_gate_ready",
    "public_benchmark_statistical_support_work_order_ready",
    "public_benchmark_statistical_support_work_order_status",
    "public_benchmark_statistical_support_work_order_expansion_slot_count",
    "public_benchmark_statistical_support_work_order_minimum_new_pair_count",
    "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count",
    "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count",
    "public_benchmark_statistical_support_work_order_bootstrap_retest_required",
    "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed",
    "public_benchmark_statistical_support_metric_materialization_readiness_present",
    "public_benchmark_statistical_support_metric_materialization_readiness_ready",
    "public_benchmark_statistical_support_metric_materialization_status",
    "public_benchmark_statistical_support_metric_materialization_row_count",
    "public_benchmark_statistical_support_metric_materialization_candidate_ready_count",
    "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count",
    "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count",
    "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count",
    "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count",
    "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count",
    "public_benchmark_statistical_support_metric_materialization_claim_grade_statistical_support_ready",
    "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads",
    "public_benchmark_statistical_support_metric_materialization_next_required_step",
    "external_state_mutated",
)


def _full_commercial_evidence_receipt_intake_fields(intake: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for suffix in FULL_COMMERCIAL_EVIDENCE_RECEIPT_INTAKE_FIELDS:
        source_key = f"full_commercial_evidence_receipt_{suffix}"
        if suffix.endswith("_count"):
            fields[source_key] = _int(intake.get(source_key))
        elif suffix == "entry_ids":
            value = intake.get(source_key)
            fields[source_key] = (
                [str(item) for item in value if str(item).strip()]
                if isinstance(value, list)
                else _unique([value])
            )
        else:
            fields[source_key] = _text(intake.get(source_key))
    return fields


def _primary_full_commercial_release_blocker_intake_fields(intake: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for suffix in PRIMARY_FULL_COMMERCIAL_RELEASE_BLOCKER_INTAKE_FIELDS:
        source_key = f"primary_full_commercial_release_blocker_{suffix}"
        if suffix.endswith("_count"):
            fields[source_key] = _int(intake.get(source_key))
        else:
            fields[source_key] = _text(intake.get(source_key))
    return fields


def _production_ai_registry_promotion_priority_intake_fields(intake: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for suffix in PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_INTAKE_FIELDS:
        source_key = f"production_ai_registry_promotion_priority_{suffix}"
        if suffix.endswith("_count"):
            fields[source_key] = _int(intake.get(source_key))
        elif suffix in {
            "packet_ready",
            "registry_promotion_ready",
            "model_promoted",
            "customer_facing_mutation_enabled",
            "external_state_mutated",
        }:
            fields[source_key] = bool(intake.get(source_key) is True)
        elif suffix == "missing_gate_ids":
            value = intake.get(source_key)
            fields[source_key] = (
                [str(item) for item in value if str(item).strip()]
                if isinstance(value, list)
                else _unique([value])
            )
        else:
            fields[source_key] = _text(intake.get(source_key))
    return fields


def _product_scope_breadth_evidence_priority_intake_fields(
    intake: dict[str, Any]
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for suffix in PRODUCT_SCOPE_BREADTH_EVIDENCE_PRIORITY_INTAKE_FIELDS:
        source_key = f"product_scope_breadth_evidence_priority_{suffix}"
        if suffix.endswith("_count"):
            fields[source_key] = _int(intake.get(source_key))
        elif suffix in {
            "packet_ready",
            "scope_promotion_allowed",
            "authoritative_apply_allowed",
            "external_state_mutated",
        }:
            fields[source_key] = bool(intake.get(source_key) is True)
        else:
            fields[source_key] = _text(intake.get(source_key))
    return fields


def _engine_refinement_claim_evidence_priority_packet_fields(
    priority: dict[str, Any],
    *,
    source_json: str,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    bool_suffixes = {
        "priority_packet_ready",
        "claim_promotion_allowed",
        "claim_evidence_receipt_ready",
        "public_benchmark_gate_ready",
        "public_benchmark_materialized_candidate_ready",
        "public_benchmark_materialized_metric_ready",
        "public_benchmark_materialized_apply_ready",
        "public_benchmark_materialized_free_energy_spearman_gate_ready",
        "public_benchmark_statistical_support_work_order_ready",
        "public_benchmark_statistical_support_work_order_bootstrap_retest_required",
        "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed",
        "public_benchmark_statistical_support_metric_materialization_readiness_present",
        "public_benchmark_statistical_support_metric_materialization_readiness_ready",
        "public_benchmark_statistical_support_metric_materialization_claim_grade_statistical_support_ready",
        "external_state_mutated",
    }
    float_suffixes = {
        "public_benchmark_materialized_free_energy_spearman",
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p05",
    }
    prefix = "engine_refinement_claim_evidence_priority_packet_"
    for suffix in ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_FIELDS:
        target_key = f"{prefix}{suffix}"
        if suffix == "source_json":
            fields[target_key] = source_json if priority else ""
        elif suffix.endswith("_count") or suffix in {
            "priority_item_count",
            "public_benchmark_materialized_work_order_row_count",
            "public_benchmark_materialized_free_energy_pair_count",
            "public_benchmark_statistical_support_work_order_expansion_slot_count",
            "public_benchmark_statistical_support_work_order_minimum_new_pair_count",
            "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count",
            "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count",
        }:
            fields[target_key] = _int(priority.get(suffix))
        elif suffix in bool_suffixes:
            fields[target_key] = bool(priority.get(suffix) is True)
        elif suffix in float_suffixes:
            fields[target_key] = _float(priority.get(suffix))
        else:
            fields[target_key] = _text(priority.get(suffix))
    return fields


def _release_row_by_check(release_gate_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows_by_check: dict[str, dict[str, Any]] = {}
    for row in _rows(release_gate_packet):
        check = _text(row.get("check"))
        if check:
            rows_by_check[check] = row
    return rows_by_check


def _current_release_field(
    burndown_row: dict[str, Any],
    release_rows_by_check: dict[str, dict[str, Any]],
    *,
    release_field: str,
    fallback_key: str,
) -> str:
    checks = _split_semicolon(burndown_row.get("release_checks") or burndown_row.get("release_check"))
    if not checks:
        return _text(burndown_row.get(fallback_key))
    parts: list[str] = []
    found = False
    for check in checks:
        release_row = release_rows_by_check.get(check)
        value = _text(release_row.get(release_field)) if release_row else ""
        if value:
            found = True
        else:
            value = _text(burndown_row.get(fallback_key))
        parts.append(f"{check}={value}" if check else value)
    return "; ".join(part for part in parts if part) if found else _text(burndown_row.get(fallback_key))


def _matches_release_checks(burndown_row: dict[str, Any], intake_row: dict[str, Any]) -> bool:
    burndown_checks = set(_split_semicolon(burndown_row.get("release_checks") or burndown_row.get("release_check")))
    intake_checks = set(_split_semicolon(intake_row.get("release_checks")))
    return bool(burndown_checks and intake_checks and burndown_checks & intake_checks)


def _matches_action(burndown_row: dict[str, Any], action_row: dict[str, Any], intake_rows: list[dict[str, Any]]) -> bool:
    action_artifacts = set(_split_semicolon(action_row.get("artifact_path")))
    source_artifacts = set(_split_semicolon(burndown_row.get("source_artifact")))
    if action_artifacts and source_artifacts and action_artifacts & source_artifacts:
        return True
    action_type = _text(action_row.get("action_type"))
    if not action_type:
        return False
    for intake in intake_rows:
        if not _matches_release_checks(burndown_row, intake):
            continue
        if action_type in set(_split_semicolon(intake.get("action_types"))):
            return True
    return False


def _filter_current_intake_rows(burndown_row: dict[str, Any], intake_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _text(burndown_row.get("burndown_status")).startswith("blocked_until_"):
        return []
    burndown_tokens = set(_split_semicolon(burndown_row.get("approval_token_required")))
    intake_rows = [row for row in intake_rows if _text(row.get("kit_status")) != "not_surfaced"]
    if not burndown_tokens:
        return intake_rows
    filtered: list[dict[str, Any]] = []
    for row in intake_rows:
        intake_tokens = set(_split_semicolon(row.get("approval_token_required")))
        if not intake_tokens or burndown_tokens & intake_tokens:
            filtered.append(row)
    return filtered


def _bottleneck_kind(row: dict[str, Any]) -> str:
    status = _text(row.get("burndown_status"))
    if status == "official_results_required":
        return "official_cameo_results_missing"
    if status == "policy_decision_required":
        return "protected_payload_policy_decision"
    if status == "approval_required":
        return "operator_approval_required"
    if status == "operator_action_required":
        return "operator_action_board_not_clear"
    if status == "blocked_until_prior_phases_clear":
        return "dependent_refresh_after_prior_phases"
    if status == "operator_input_required":
        return "operator_input_required"
    return status or "unknown"


def _completion_bottleneck_kind(row: dict[str, Any]) -> str:
    requirement_id = _text(row.get("requirement_id"))
    blocker = _text(row.get("blocker"))
    if requirement_id == "R8_full_scope_claim_closure" or blocker == "full_scope_claim_closure_not_ready":
        return "scientific_scope_evidence_required"
    if (
        requirement_id == "R9_engine_refinement_claim_promotion"
        or blocker == "engine_refinement_claim_promotion_not_ready"
    ):
        return "engine_refinement_claim_promotion_required"
    return blocker or "completion_audit_release_blocker"


def _completion_sequence(row: dict[str, Any], fallback: int) -> int:
    requirement_id = _text(row.get("requirement_id"))
    if len(requirement_id) >= 2 and requirement_id[0] == "R":
        digits = ""
        for char in requirement_id[1:]:
            if not char.isdigit():
                break
            digits += char
        if digits:
            return _int(digits)
    return fallback


def _completion_recommended_action(row: dict[str, Any], kind: str) -> str:
    if kind == "scientific_scope_evidence_required":
        return (
            "Acquire exact target-pair quantitative evidence for the blocked scope row, rerun the "
            "scope-breadth gates, and keep authoritative apply disabled until those gates are green."
        )
    if kind == "engine_refinement_claim_promotion_required":
        return (
            "Fill the refine-tier public benchmark and claim-evidence receipt rows, then rerun engine "
            "refinement readiness and the product goal completion audit."
        )
    return _text(row.get("required")) or _text(row.get("requirement"))


def _mutation_flags() -> dict[str, bool]:
    return {
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "upload_executed": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _root_cause_fields(row: dict[str, Any], *, required_inputs: list[str], source_artifacts: list[str]) -> dict[str, Any]:
    kind = _text(row.get("bottleneck_kind"))
    observed = _text(row.get("release_observed"))
    required = _text(row.get("release_required"))
    inputs = ";".join(required_inputs)
    artifacts = ";".join(source_artifacts)
    if kind == "production_ai_checkpoint_evidence_required":
        return {
            "root_cause_category": "external_gpu_runtime_and_return_receipt",
            "root_cause_summary": (
                "Production AI cannot become the customer-facing inference subject until a ROCm/HIP AMD GPU "
                "is visible to PyTorch, the full regeneration summary/manifest/NPZ bundle is returned, and "
                "the checkpoint sidecar/preflight/registry promotion chain passes."
            ),
            "locally_closable_without_operator_return": False,
            "required_external_return": (
                "runs/rocm_environment_manifest_current.json with torch_rocm_ready=true and visible_device_count>0; "
                "runs/residual_force_trajectory_regeneration_current_summary.json; "
                "runs/residual_force_trajectory_regeneration_current_manifest.csv; regenerated NPZ bundles with "
                "operator verification and identity coverage"
            ),
            "first_acceptance_artifact": "runs/rocm_environment_manifest_current.json",
            "post_return_acceptance_artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
        }
    if kind == "scientific_scope_evidence_required" or "AQP1.core_binder_01" in inputs or "scope_closure" in observed:
        return {
            "root_cause_category": "external_exact_scope_evidence",
            "root_cause_summary": (
                "Scope breadth cannot widen until transporter/PXR rows have direct experimental or "
                "operator-verified claim-safe quantitative binding kcal evidence; functional IC50 and "
                "computational MM/GBSA stay review-only."
            ),
            "locally_closable_without_operator_return": False,
            "required_external_return": (
                "completed transporter/PXR review rows with target-pair source, assay, target-match decision, "
                "and replacement_reference_binding_kcal_mol only when direct or claim-safe binding kcal is proven"
            ),
            "first_acceptance_artifact": "runs/transporter_manual_review_intake_template_current.csv",
            "post_return_acceptance_artifact": "runs/product_scope_breadth_contract_current.json",
        }
    if kind == "engine_refinement_claim_promotion_required" or "engine_refinement" in observed:
        return {
            "root_cause_category": "external_public_benchmark_and_calibration_evidence",
            "root_cause_summary": (
                "Refine-tier science claims cannot promote until public benchmark intake, parameter "
                "calibration, metal/cofactor handling, protonation and charge calibration, solvent/FEP "
                "calibration, and external structure-quality parity evidence are all claim-grade."
            ),
            "locally_closable_without_operator_return": False,
            "required_external_return": (
                "curated public benchmark rows; parameter calibration evidence; metal/cofactor parameter "
                "coverage; protonation/charge calibration; solvent/FEP public-pair calibration; external "
                "MolProbity/OpenStructure/native-complex parity packets"
            ),
            "first_acceptance_artifact": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "post_return_acceptance_artifact": "runs/engine_refinement_claim_evidence_receipt_current.json",
        }
    if kind == "dependent_refresh_after_prior_phases":
        return {
            "root_cause_category": "dependent_refresh_after_upstream_acceptance",
            "root_cause_summary": (
                "Release refresh is intentionally blocked until the earlier product AI/scope acceptance phases pass."
            ),
            "locally_closable_without_operator_return": False,
            "required_external_return": "",
            "first_acceptance_artifact": artifacts,
            "post_return_acceptance_artifact": "",
        }
    if kind in {"operator_approval_required", "protected_payload_policy_decision", "official_cameo_results_missing"}:
        return {
            "root_cause_category": "operator_decision_or_external_result_required",
            "root_cause_summary": required or observed or "Operator decision or external result evidence is required.",
            "locally_closable_without_operator_return": False,
            "required_external_return": inputs,
            "first_acceptance_artifact": artifacts,
            "post_return_acceptance_artifact": "",
        }
    return {
        "root_cause_category": kind or "unknown",
        "root_cause_summary": required or observed or "Bottleneck requires review before closure.",
        "locally_closable_without_operator_return": False,
        "required_external_return": inputs,
        "first_acceptance_artifact": artifacts,
        "post_return_acceptance_artifact": "",
    }


def _next_required_step(*, kind_counts: dict[str, int], cleanup_objective_ready: bool) -> str:
    items: list[str] = []

    def add(item: str) -> None:
        if item not in items:
            items.append(item)

    if kind_counts.get("scientific_scope_evidence_required"):
        add("product AI architecture scope closure")
    if kind_counts.get("engine_refinement_claim_promotion_required"):
        add("engine refinement claim evidence and calibration")
    if kind_counts.get("production_ai_checkpoint_evidence_required"):
        add("product AI production inference closure")
    if kind_counts.get("operator_approval_required") or kind_counts.get("operator_action_board_not_clear"):
        add("product benchmark scorecards/license")
    if kind_counts.get("official_cameo_results_missing"):
        add("optional CAMEO live evidence")
    if not cleanup_objective_ready and (
        kind_counts.get("protected_payload_policy_decision") or kind_counts.get("approval_required")
    ):
        add("cleanup approvals/policy")
    if kind_counts.get("dependent_refresh_after_prior_phases") or kind_counts.get("api_contract_refresh_required"):
        add("release evidence refresh")
    if not items:
        return "No current bottlenecks remain; rerun the completion audit before any completion claim."
    return f"Resolve bottlenecks in sequence: {', '.join(items)}."


def _preflight_summaries(packets: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [_summary(packet) for packet in packets or [] if _summary(packet)]


def _public_benchmark_work_order_clear(summary: dict[str, Any]) -> bool:
    status = _text(summary.get("status"))
    if status == "product_public_benchmark_work_order_clear":
        return True
    return (
        summary.get("public_benchmark_validation_ready") is True
        and _int(summary.get("blocked_suite_count")) == 0
        and _int(summary.get("benchmark_result_missing_artifact_count")) == 0
    )


def build_goal_bottleneck_briefing(
    *,
    release_gate_packet: dict[str, Any],
    burndown_packet: dict[str, Any],
    action_board_packet: dict[str, Any],
    intake_kit_packet: dict[str, Any],
    completion_audit_packet: dict[str, Any] | None = None,
    engine_refinement_claim_evidence_priority_packet: dict[str, Any] | None = None,
    public_benchmark_work_order_packet: dict[str, Any] | None = None,
    public_benchmark_preflight_packets: list[dict[str, Any]] | None = None,
    public_benchmark_preflight_paths: list[str] | None = None,
    release_gate_path: str = DEFAULT_RELEASE_GATE_JSON,
    burndown_path: str = DEFAULT_BURNDOWN_JSON,
    action_board_path: str = DEFAULT_ACTION_BOARD_JSON,
    intake_kit_path: str = DEFAULT_INTAKE_KIT_JSON,
    completion_audit_path: str = DEFAULT_COMPLETION_AUDIT_JSON,
    engine_refinement_claim_evidence_priority_packet_path: str = (
        DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_JSON
    ),
    public_benchmark_work_order_path: str = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON,
) -> dict[str, Any]:
    release = _summary(release_gate_packet)
    burndown = _summary(burndown_packet)
    actions = _summary(action_board_packet)
    intake = _summary(intake_kit_packet)
    completion_audit = _summary(completion_audit_packet or {})
    engine_refinement_claim_evidence_priority = _summary(
        engine_refinement_claim_evidence_priority_packet or {}
    )
    engine_refinement_claim_evidence_priority_fields = (
        _engine_refinement_claim_evidence_priority_packet_fields(
            engine_refinement_claim_evidence_priority,
            source_json=engine_refinement_claim_evidence_priority_packet_path,
        )
    )
    engine_refinement_claim_evidence_priority_artifacts = _unique(
        [engine_refinement_claim_evidence_priority_packet_path]
        + _text_list(engine_refinement_claim_evidence_priority.get("source_artifacts"))
    )
    public_benchmark_work_order = _summary(public_benchmark_work_order_packet or {})
    public_benchmark_preflights = _preflight_summaries(public_benchmark_preflight_packets)
    public_benchmark_preflight_tokens = _unique(
        [summary.get("approval_token_required") for summary in public_benchmark_preflights]
    )
    public_benchmark_preflight_statuses = _unique([summary.get("status") for summary in public_benchmark_preflights])
    public_benchmark_preflight_blocked_count = sum(
        1 for summary in public_benchmark_preflights if _text(summary.get("status")).startswith("blocked_")
    )
    public_benchmark_preflight_paths = public_benchmark_preflight_paths or []
    burndown_rows = _rows(burndown_packet)
    action_rows = _rows(action_board_packet)
    intake_rows = _rows(intake_kit_packet)
    release_rows_by_check = _release_row_by_check(release_gate_packet)
    rows: list[dict[str, Any]] = []

    for burndown_row in sorted(burndown_rows, key=lambda row: _int(row.get("sequence"))):
        matched_intake = _filter_current_intake_rows(
            burndown_row,
            [row for row in intake_rows if _matches_release_checks(burndown_row, row)],
        )
        matched_actions = (
            []
            if _text(burndown_row.get("burndown_status")).startswith("blocked_until_")
            else [row for row in action_rows if _matches_action(burndown_row, row, matched_intake)]
        )
        approval_tokens = _unique(
            [burndown_row.get("approval_token_required")]
            + [row.get("approval_token_required") for row in matched_intake]
            + [row.get("approval_token") for row in matched_actions]
        )
        required_inputs = _unique(
            [row.get("required_input") for row in matched_actions]
            + [row.get("intake_path") for row in matched_intake if row.get("operator_input_required")]
        )
        source_artifacts = _unique(
            [burndown_row.get("source_artifact")]
            + [row.get("source_artifacts") for row in matched_intake]
            + [row.get("artifact_path") for row in matched_actions]
        )
        public_benchmark_blocked = _text(burndown_row.get("burndown_status")) == "blocked_until_public_benchmark_validation"
        stale_public_benchmark_block = public_benchmark_blocked and _public_benchmark_work_order_clear(
            public_benchmark_work_order
        )
        if public_benchmark_blocked and public_benchmark_work_order_path not in source_artifacts:
            source_artifacts.append(public_benchmark_work_order_path)
        if public_benchmark_blocked and not stale_public_benchmark_block:
            for token in public_benchmark_preflight_tokens:
                if token not in approval_tokens:
                    approval_tokens.append(token)
            for path in public_benchmark_preflight_paths:
                if path and path not in source_artifacts:
                    source_artifacts.append(path)
        public_benchmark_continuous_command = (
            _text(public_benchmark_work_order.get("continuous_validation_command")) if public_benchmark_blocked else ""
        )
        size_gb = round(sum(_float(row.get("size_gb")) for row in matched_actions), 3)
        if not size_gb:
            size_gb = round(_float(burndown_row.get("size_gb")), 3)
        row = {
            "bottleneck_id": f"P{_int(burndown_row.get('sequence')):02d}_{_text(burndown_row.get('phase')) or 'unknown'}",
            "sequence": _int(burndown_row.get("sequence")),
            "row_source": "release_burndown",
            "phase": _text(burndown_row.get("phase")),
            "lane_id": _text(burndown_row.get("lane_id")),
            "bottleneck_kind": (
                "stale_blocked_until_public_benchmark_validation"
                if stale_public_benchmark_block
                else _bottleneck_kind(burndown_row)
            ),
            "burndown_status": _text(burndown_row.get("burndown_status")),
            "is_current_bottleneck": not stale_public_benchmark_block,
            "superseded_by_current_evidence": stale_public_benchmark_block,
            "release_checks": _text(burndown_row.get("release_checks") or burndown_row.get("release_check")),
            "release_observed": _current_release_field(
                burndown_row,
                release_rows_by_check,
                release_field="observed",
                fallback_key="release_observed",
            ),
            "release_required": _current_release_field(
                burndown_row,
                release_rows_by_check,
                release_field="required",
                fallback_key="release_required",
            ),
            "release_check_count": _int(burndown_row.get("release_check_count")),
            "requires_operator_action": (
                False if stale_public_benchmark_block else bool(burndown_row.get("requires_operator_action") is True)
            ),
            "approval_token_required": ";".join(approval_tokens),
            "approval_token_count": len(approval_tokens),
            "required_inputs": ";".join(required_inputs),
            "required_input_count": len(required_inputs),
            "operator_intake_entries": _join([row.get("kit_entry_id") for row in matched_intake]),
            "operator_intake_statuses": _join([row.get("kit_status") for row in matched_intake]),
            "operator_action_types": _join([row.get("action_type") for row in matched_actions]),
            "operator_action_statuses": _join([row.get("status") for row in matched_actions]),
            "operator_action_reasons": _join([row.get("reason") for row in matched_actions]),
            "operator_action_count": len(matched_actions),
            "source_artifacts": ";".join(source_artifacts),
            "source_artifact_count": len(source_artifacts),
            "command": _text(burndown_row.get("command")),
            "command_candidate_count": len(
                [part for part in _text(burndown_row.get("license_local_source_command_examples")).split("||") if part.strip()]
            ),
            "command_candidates": _text(burndown_row.get("license_local_source_command_examples")),
            "recommended_action": _text(burndown_row.get("recommended_action")),
            "public_benchmark_work_order_json": (public_benchmark_work_order_path if public_benchmark_blocked else ""),
            "public_benchmark_open_suite_count": (
                _int(public_benchmark_work_order.get("open_suite_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_materialization_required_suite_count": (
                _int(public_benchmark_work_order.get("materialization_required_suite_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_scorecard_required_suite_count": (
                _int(public_benchmark_work_order.get("scorecard_required_suite_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_continuous_validation_command_count": (
                _int(public_benchmark_work_order.get("continuous_validation_command_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_suite_run_command_count": (
                _int(public_benchmark_work_order.get("suite_run_command_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_suite_blocker_count": (
                _int(public_benchmark_work_order.get("suite_blocker_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_suite_threshold_count": (
                _int(public_benchmark_work_order.get("suite_threshold_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_suite_materialization_manifest_count": (
                _int(public_benchmark_work_order.get("suite_materialization_manifest_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_suite_materialization_run_command_count": (
                _int(public_benchmark_work_order.get("suite_materialization_run_command_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_suite_scorecard_command_count": (
                _int(public_benchmark_work_order.get("suite_scorecard_command_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_suite_scorecard_row_csv_count": (
                _int(public_benchmark_work_order.get("suite_scorecard_row_csv_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_suite_no_external_dependency_count": (
                _int(public_benchmark_work_order.get("suite_no_external_dependency_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_local_artifact_preflight_ready_suite_count": (
                _int(public_benchmark_work_order.get("local_artifact_preflight_ready_suite_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_local_artifact_preflight_blocked_suite_count": (
                _int(public_benchmark_work_order.get("local_artifact_preflight_blocked_suite_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_missing_local_input_artifact_count": (
                _int(public_benchmark_work_order.get("missing_local_input_artifact_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_missing_local_output_artifact_count": (
                _int(public_benchmark_work_order.get("missing_local_output_artifact_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_result_generation_required_suite_count": (
                _int(public_benchmark_work_order.get("result_generation_required_suite_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_result_generation_approval_token_required": (
                _text(public_benchmark_work_order.get("result_generation_approval_token_required"))
                if public_benchmark_blocked
                else ""
            ),
            "public_benchmark_benchmark_result_missing_artifact_count": (
                _int(public_benchmark_work_order.get("benchmark_result_missing_artifact_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_continuous_validation_command": public_benchmark_continuous_command,
            "public_benchmark_input_preflight_statuses": (
                ";".join(public_benchmark_preflight_statuses) if public_benchmark_blocked else ""
            ),
            "public_benchmark_input_preflight_blocked_count": (
                public_benchmark_preflight_blocked_count if public_benchmark_blocked else 0
            ),
            "public_benchmark_input_preflight_approval_tokens_required": (
                ";".join(public_benchmark_preflight_tokens) if public_benchmark_blocked else ""
            ),
            "size_gb": size_gb,
            **_mutation_flags(),
        }
        row.update(
            _root_cause_fields(
                row,
                required_inputs=required_inputs,
                source_artifacts=source_artifacts,
            )
        )
        rows.append(row)

    completion_blocker_rows: list[dict[str, Any]] = []
    for index, audit_row in enumerate(_rows(completion_audit_packet or {}), start=1):
        if audit_row.get("release_blocker") is not True or _text(audit_row.get("status")) == "pass":
            continue
        kind = _completion_bottleneck_kind(audit_row)
        source_artifacts = _unique(
            [audit_row.get("evidence_artifacts")]
            + (
                engine_refinement_claim_evidence_priority_artifacts
                if kind == "engine_refinement_claim_promotion_required"
                else []
            )
        )
        required_inputs = _unique([audit_row.get("blocker"), audit_row.get("requirement_id")])
        row = {
            "bottleneck_id": _text(audit_row.get("requirement_id")) or f"completion_audit_blocker_{index}",
            "sequence": _completion_sequence(audit_row, 900 + index),
            "row_source": "completion_audit",
            "phase": _text(audit_row.get("requirement_id")) or "product_goal_completion_audit",
            "lane_id": _text(audit_row.get("requirement_tier")) or "full_commercial_completion",
            "bottleneck_kind": kind,
            "burndown_status": "completion_audit_release_blocker",
            "is_current_bottleneck": True,
            "superseded_by_current_evidence": False,
            "release_checks": _text(audit_row.get("requirement_id")),
            "release_observed": _text(audit_row.get("observed")),
            "release_required": _text(audit_row.get("required")),
            "release_check_count": 1,
            "requires_operator_action": True,
            "approval_token_required": _text(audit_row.get("approval_token_required")),
            "approval_token_count": len(_split_semicolon(audit_row.get("approval_token_required"))),
            "required_inputs": ";".join(required_inputs),
            "required_input_count": len(required_inputs),
            "operator_intake_entries": "",
            "operator_intake_statuses": "",
            "operator_action_types": "",
            "operator_action_statuses": "",
            "operator_action_reasons": "",
            "operator_action_count": 0,
            "source_artifacts": ";".join(source_artifacts),
            "source_artifact_count": len(source_artifacts),
            "command": _text(audit_row.get("next_command")),
            "command_candidate_count": 0,
            "command_candidates": "",
            "recommended_action": _completion_recommended_action(audit_row, kind),
            "completion_audit_requirement": _text(audit_row.get("requirement")),
            "completion_audit_requirement_id": _text(audit_row.get("requirement_id")),
            "completion_audit_requirement_tier": _text(audit_row.get("requirement_tier")),
            "completion_audit_blocker": _text(audit_row.get("blocker")),
            "public_benchmark_work_order_json": "",
            "public_benchmark_open_suite_count": 0,
            "public_benchmark_materialization_required_suite_count": 0,
            "public_benchmark_scorecard_required_suite_count": 0,
            "public_benchmark_continuous_validation_command_count": 0,
            "public_benchmark_suite_run_command_count": 0,
            "public_benchmark_suite_blocker_count": 0,
            "public_benchmark_suite_threshold_count": 0,
            "public_benchmark_suite_materialization_manifest_count": 0,
            "public_benchmark_suite_materialization_run_command_count": 0,
            "public_benchmark_suite_scorecard_command_count": 0,
            "public_benchmark_suite_scorecard_row_csv_count": 0,
            "public_benchmark_suite_no_external_dependency_count": 0,
            "public_benchmark_local_artifact_preflight_ready_suite_count": 0,
            "public_benchmark_local_artifact_preflight_blocked_suite_count": 0,
            "public_benchmark_missing_local_input_artifact_count": 0,
            "public_benchmark_missing_local_output_artifact_count": 0,
            "public_benchmark_result_generation_required_suite_count": 0,
            "public_benchmark_result_generation_approval_token_required": "",
            "public_benchmark_benchmark_result_missing_artifact_count": 0,
            "public_benchmark_continuous_validation_command": "",
            "public_benchmark_input_preflight_statuses": "",
            "public_benchmark_input_preflight_blocked_count": 0,
            "public_benchmark_input_preflight_approval_tokens_required": "",
            "size_gb": 0.0,
            **_mutation_flags(),
        }
        row.update(
            _root_cause_fields(
                row,
                required_inputs=required_inputs,
                source_artifacts=source_artifacts,
            )
        )
        if kind == "engine_refinement_claim_promotion_required":
            row.update(engine_refinement_claim_evidence_priority_fields)
            top_operator_step = _text(
                row.get("engine_refinement_claim_evidence_priority_packet_top_next_operator_step")
            )
            if top_operator_step:
                row["recommended_action"] = top_operator_step
        completion_blocker_rows.append(row)
    rows.extend(completion_blocker_rows)

    status_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["burndown_status"]] = status_counts.get(row["burndown_status"], 0) + 1
        kind_counts[row["bottleneck_kind"]] = kind_counts.get(row["bottleneck_kind"], 0) + 1
    approval_tokens = _unique([row.get("approval_token_required") for row in rows])
    current_rows = [row for row in rows if row.get("is_current_bottleneck") is not False]
    primary = current_rows[0] if current_rows else {}
    completion_only_current = bool(current_rows) and all(
        _text(row.get("row_source")) == "completion_audit" for row in current_rows
    )
    derived_primary_action_id = (
        f"{_text(primary.get('lane_id'))}:{_text(primary.get('bottleneck_kind'))}"
        if completion_only_current and primary
        else ""
    )
    primary_action_id = (
        derived_primary_action_id
        or _text(intake.get("primary_action_id"))
        or _text(actions.get("primary_action_id"))
        or _text(burndown.get("primary_action_id"))
    )
    cleanup_objective_ready = bool(release.get("cleanup_objective_ready") is True) or bool(
        release.get("cleanup_completion_complete") is True
    )
    cleanup_transition_size_gb = 0.0 if cleanup_objective_ready else round(
        _float(release.get("cleanup_completion_transition_approval_gated_reclaim_size_gb")), 3
    )
    cleanup_ligand_size_gb = 0.0 if cleanup_objective_ready else round(
        _float(release.get("cleanup_completion_ligand_heavy_candidate_size_gb")), 3
    )
    summary = {
        "packet_type": "goal_bottleneck_briefing",
        "status": "goal_bottleneck_briefing_ready" if rows else "blocked_goal_bottleneck_briefing",
        "release_allowed": bool(release.get("release_allowed") is True),
        "source_release_gate_status": _text(release.get("status")),
        "source_release_blocker_count": _int(release.get("blocker_count")),
        "source_release_check_count": _int(release.get("check_count")),
        "source_burndown_status": _text(burndown.get("status")),
        "source_action_board_status": _text(actions.get("status")),
        "source_intake_kit_status": _text(intake.get("status")),
        "source_completion_audit_status": _text(completion_audit.get("status")),
        "source_completion_audit_json": completion_audit_path,
        "completion_audit_goal_complete": bool(completion_audit.get("goal_complete") is True),
        "completion_audit_release_blocker_fail_count": _int(completion_audit.get("release_blocker_fail_count")),
        "completion_audit_release_blocker_bottleneck_count": len(completion_blocker_rows),
        "bottleneck_count": len(rows),
        "current_bottleneck_count": len(current_rows),
        "superseded_bottleneck_count": sum(1 for row in rows if row.get("superseded_by_current_evidence") is True),
        "operator_action_required_bottleneck_count": sum(1 for row in rows if row["requires_operator_action"]),
        "approval_required_bottleneck_count": status_counts.get("approval_required", 0),
        "official_results_required_bottleneck_count": status_counts.get("official_results_required", 0),
        "policy_decision_required_bottleneck_count": status_counts.get("policy_decision_required", 0),
        "blocked_until_prior_phases_clear_count": status_counts.get("blocked_until_prior_phases_clear", 0),
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "approval_reclaim_size_gb": round(_float(actions.get("approval_reclaim_size_gb") or burndown.get("approval_reclaim_size_gb")), 3),
        "cleanup_transition_approval_gated_reclaim_size_gb": cleanup_transition_size_gb,
        "cleanup_ligand_heavy_candidate_size_gb": cleanup_ligand_size_gb,
        "protected_cleanup_payload_size_gb": round(_float(release.get("protected_cleanup_payload_size_gb")), 3),
        "operator_intake_kit_release_burndown_linked_entry_count": _int(
            intake.get("release_burndown_linked_entry_count")
        ),
        "full_commercial_release_allowed": bool(intake.get("full_commercial_release_allowed") is True),
        "full_commercial_release_blocker_count": _int(intake.get("full_commercial_release_blocker_count")),
        "full_commercial_release_blocker_ids": [
            str(item) for item in (intake.get("full_commercial_release_blocker_ids") or [])
        ],
        "full_commercial_release_next_required_step": _text(
            intake.get("full_commercial_release_next_required_step")
        ),
        "science_claim_promotion_gap_closure_open_gap_ids": [
            str(item) for item in (intake.get("science_claim_promotion_gap_closure_open_gap_ids") or [])
        ],
        "science_claim_promotion_gap_closure_current_next_action": _text(
            intake.get("science_claim_promotion_gap_closure_current_next_action")
        ),
        "product_accuracy_parity_ligand_ranking_action_id": _text(
            intake.get("product_accuracy_parity_ligand_ranking_action_id")
        ),
        "product_accuracy_parity_ligand_ranking_action_present": bool(
            intake.get("product_accuracy_parity_ligand_ranking_action_present") is True
        ),
        "product_accuracy_parity_ligand_ranking_required_input": _text(
            intake.get("product_accuracy_parity_ligand_ranking_required_input")
        ),
        "product_accuracy_parity_ligand_ranking_artifact_path": _text(
            intake.get("product_accuracy_parity_ligand_ranking_artifact_path")
        ),
        "product_accuracy_parity_ligand_ranking_recommended_action": _text(
            intake.get("product_accuracy_parity_ligand_ranking_recommended_action")
        ),
        "accuracy_parity_ligand_ranking_status": _text(
            intake.get("accuracy_parity_ligand_ranking_status")
        ),
        "accuracy_parity_ligand_ranking_pr_auc": _float(
            intake.get("accuracy_parity_ligand_ranking_pr_auc")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_ci_low": _float(
            intake.get("accuracy_parity_ligand_ranking_pr_auc_ci_low")
        ),
        "accuracy_parity_ligand_ranking_topk_hit_rate": _float(
            intake.get("accuracy_parity_ligand_ranking_topk_hit_rate")
        ),
        "accuracy_parity_ligand_ranking_next_required_step": _text(
            intake.get("accuracy_parity_ligand_ranking_next_required_step")
        ),
        **_primary_full_commercial_release_blocker_intake_fields(intake),
        **_full_commercial_evidence_receipt_intake_fields(intake),
        "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": _text(
            intake.get(
                "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"
            )
        ),
        "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": _text(
            intake.get(
                "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact"
            )
        ),
        "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": _text(
            intake.get(
                "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status"
            )
        ),
        "product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": _text(
            intake.get(
                "product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status"
            )
        ),
        "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": _text_list(
            intake.get(
                "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields"
            )
        ),
        "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers": _text_list(
            intake.get(
                "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers"
            )
        ),
        "product_goal_scope_breadth_evidence_receipt_most_common_row_blocker": _text(
            intake.get("product_goal_scope_breadth_evidence_receipt_most_common_row_blocker")
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": _text(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"
            )
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": _text(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact"
            )
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": _text(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status"
            )
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": _text(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status"
            )
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": _text_list(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields"
            )
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": _text_list(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers"
            )
        ),
        "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker": _text(
            intake.get(
                "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker"
            )
        ),
        **engine_refinement_claim_evidence_priority_fields,
        **_product_scope_breadth_evidence_priority_intake_fields(intake),
        **_production_ai_registry_promotion_priority_intake_fields(intake),
        "public_benchmark_work_order_status": _text(public_benchmark_work_order.get("status")),
        "public_benchmark_work_order_json": public_benchmark_work_order_path,
        "public_benchmark_open_suite_count": _int(public_benchmark_work_order.get("open_suite_count")),
        "public_benchmark_materialization_required_suite_count": _int(
            public_benchmark_work_order.get("materialization_required_suite_count")
        ),
        "public_benchmark_scorecard_required_suite_count": _int(
            public_benchmark_work_order.get("scorecard_required_suite_count")
        ),
        "public_benchmark_continuous_validation_command_count": _int(
            public_benchmark_work_order.get("continuous_validation_command_count")
        ),
        "public_benchmark_suite_run_command_count": _int(public_benchmark_work_order.get("suite_run_command_count")),
        "public_benchmark_suite_blocker_count": _int(public_benchmark_work_order.get("suite_blocker_count")),
        "public_benchmark_suite_threshold_count": _int(public_benchmark_work_order.get("suite_threshold_count")),
        "public_benchmark_suite_materialization_manifest_count": _int(
            public_benchmark_work_order.get("suite_materialization_manifest_count")
        ),
        "public_benchmark_suite_materialization_run_command_count": _int(
            public_benchmark_work_order.get("suite_materialization_run_command_count")
        ),
        "public_benchmark_suite_scorecard_command_count": _int(
            public_benchmark_work_order.get("suite_scorecard_command_count")
        ),
        "public_benchmark_suite_scorecard_row_csv_count": _int(
            public_benchmark_work_order.get("suite_scorecard_row_csv_count")
        ),
        "public_benchmark_suite_no_external_dependency_count": _int(
            public_benchmark_work_order.get("suite_no_external_dependency_count")
        ),
        "public_benchmark_local_artifact_preflight_ready_suite_count": _int(
            public_benchmark_work_order.get("local_artifact_preflight_ready_suite_count")
        ),
        "public_benchmark_local_artifact_preflight_blocked_suite_count": _int(
            public_benchmark_work_order.get("local_artifact_preflight_blocked_suite_count")
        ),
        "public_benchmark_missing_local_input_artifact_count": _int(
            public_benchmark_work_order.get("missing_local_input_artifact_count")
        ),
        "public_benchmark_missing_local_output_artifact_count": _int(
            public_benchmark_work_order.get("missing_local_output_artifact_count")
        ),
        "public_benchmark_result_generation_required_suite_count": _int(
            public_benchmark_work_order.get("result_generation_required_suite_count")
        ),
        "public_benchmark_result_generation_approval_token_required": _text(
            public_benchmark_work_order.get("result_generation_approval_token_required")
        ),
        "public_benchmark_benchmark_result_missing_artifact_count": _int(
            public_benchmark_work_order.get("benchmark_result_missing_artifact_count")
        ),
        "public_benchmark_benchmark_result_missing_artifacts": public_benchmark_work_order.get(
            "benchmark_result_missing_artifacts"
        )
        or [],
        "public_benchmark_missing_local_input_artifacts": public_benchmark_work_order.get(
            "missing_local_input_artifacts"
        )
        or [],
        "public_benchmark_missing_local_output_artifacts": public_benchmark_work_order.get(
            "missing_local_output_artifacts"
        )
        or [],
        "public_benchmark_continuous_validation_command": _text(
            public_benchmark_work_order.get("continuous_validation_command")
        ),
        "public_benchmark_input_preflight_statuses": ";".join(public_benchmark_preflight_statuses),
        "public_benchmark_input_preflight_blocked_count": public_benchmark_preflight_blocked_count,
        "public_benchmark_input_preflight_approval_tokens_required": ";".join(public_benchmark_preflight_tokens),
        "primary_action_id": primary_action_id,
        "top_action_id": (
            primary_action_id
            if completion_only_current
            else _text(intake.get("top_action_id")) or _text(actions.get("top_action_id")) or primary_action_id
        ),
        "primary_action_priority": _int(
            0
            if completion_only_current
            else intake.get("primary_action_priority")
            or actions.get("primary_action_priority")
            or burndown.get("primary_action_priority")
        ),
        "primary_action_lane_id": _text(
            primary.get("lane_id")
            if completion_only_current
            else intake.get("primary_action_lane_id")
            or actions.get("primary_action_lane_id")
            or burndown.get("primary_action_lane_id")
        ),
        "primary_action_type": _text(
            primary.get("bottleneck_kind")
            if completion_only_current
            else intake.get("primary_action_type")
            or actions.get("primary_action_type")
            or burndown.get("primary_action_type")
        ),
        "primary_action_status": _text(
            "required"
            if completion_only_current
            else intake.get("primary_action_status")
            or actions.get("primary_action_status")
            or burndown.get("primary_action_status")
        ),
        "primary_action_required_input": _text(
            primary.get("required_external_return") or primary.get("required_inputs")
            if completion_only_current
            else intake.get("primary_action_required_input")
            or actions.get("primary_action_required_input")
            or burndown.get("primary_action_required_input")
        ),
        "primary_action_artifact_path": _text(
            primary.get("source_artifacts")
            if completion_only_current
            else intake.get("primary_action_artifact_path")
            or actions.get("primary_action_artifact_path")
            or burndown.get("primary_action_artifact_path")
        ),
        "primary_action_command": _text(
            primary.get("command")
            if completion_only_current
            else intake.get("primary_action_command")
            or actions.get("primary_action_command")
            or burndown.get("primary_action_command")
        ),
        "primary_action_recommended_action": _text(
            primary.get("recommended_action")
            if completion_only_current
            else intake.get("primary_action_recommended_action")
            or actions.get("primary_action_recommended_action")
            or burndown.get("primary_action_recommended_action")
        ),
        "parallel_product_action_count": _int(actions.get("parallel_product_action_count")),
        "parallel_product_action_ids": [
            str(item) for item in (actions.get("parallel_product_action_ids") or [])
        ],
        "first_parallel_product_action_id": _text(actions.get("first_parallel_product_action_id")),
        "first_parallel_product_action_lane_id": _text(
            actions.get("first_parallel_product_action_lane_id")
        ),
        "first_parallel_product_action_type": _text(actions.get("first_parallel_product_action_type")),
        "first_parallel_product_action_required_input": _text(
            actions.get("first_parallel_product_action_required_input")
        ),
        "first_parallel_product_action_artifact_path": _text(
            actions.get("first_parallel_product_action_artifact_path")
        ),
        "first_parallel_product_action_recommended_action": _text(
            actions.get("first_parallel_product_action_recommended_action")
        ),
        "first_parallel_product_action_primary_action_id": _text(
            actions.get("first_parallel_product_action_primary_action_id")
        ),
        "first_parallel_product_action_precondition": _text(
            actions.get("first_parallel_product_action_precondition")
        ),
        "primary_bottleneck_sequence": _int(primary.get("sequence")),
        "primary_bottleneck_kind": _text(primary.get("bottleneck_kind")),
        "primary_bottleneck_phase": _text(primary.get("phase")),
        "primary_bottleneck_command": _text(primary.get("command")),
        "primary_bottleneck_root_cause_category": _text(primary.get("root_cause_category")),
        "primary_bottleneck_root_cause_summary": _text(primary.get("root_cause_summary")),
        "primary_bottleneck_locally_closable_without_operator_return": bool(
            primary.get("locally_closable_without_operator_return") is True
        ),
        "primary_bottleneck_required_external_return": _text(primary.get("required_external_return")),
        "primary_bottleneck_first_acceptance_artifact": _text(primary.get("first_acceptance_artifact")),
        "primary_bottleneck_post_return_acceptance_artifact": _text(
            primary.get("post_return_acceptance_artifact")
        ),
        "irreducible_external_return_bottleneck_count": sum(
            1
            for row in current_rows
            if row.get("locally_closable_without_operator_return") is False
            and _text(row.get("required_external_return"))
        ),
        "primary_bottleneck_command_candidate_count": _int(primary.get("command_candidate_count")),
        "primary_bottleneck_command_candidates": [
            part.strip() for part in _text(primary.get("command_candidates")).split("||") if part.strip()
        ],
        "source_release_gate_json": release_gate_path,
        "source_burndown_json": burndown_path,
        "source_action_board_json": action_board_path,
        "source_intake_kit_json": intake_kit_path,
        "status_counts": status_counts,
        "kind_counts": kind_counts,
        **_mutation_flags(),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": _next_required_step(kind_counts=kind_counts, cleanup_objective_ready=cleanup_objective_ready),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Bottleneck Briefing",
        "",
        f"- status: `{s['status']}`",
        f"- release_allowed: `{s['release_allowed']}`",
        f"- source_release_blocker_count: `{s['source_release_blocker_count']}`",
        f"- bottleneck_count: `{s['bottleneck_count']}`",
        f"- approval_required_bottleneck_count: `{s['approval_required_bottleneck_count']}`",
        f"- official_results_required_bottleneck_count: `{s['official_results_required_bottleneck_count']}`",
        f"- policy_decision_required_bottleneck_count: `{s['policy_decision_required_bottleneck_count']}`",
        f"- approval_reclaim_size_gb: `{s['approval_reclaim_size_gb']}`",
        f"- cleanup_transition_approval_gated_reclaim_size_gb: `{s['cleanup_transition_approval_gated_reclaim_size_gb']}`",
        f"- cleanup_ligand_heavy_candidate_size_gb: `{s['cleanup_ligand_heavy_candidate_size_gb']}`",
        f"- protected_cleanup_payload_size_gb: `{s['protected_cleanup_payload_size_gb']}`",
        f"- approval_tokens_required: `{';'.join(s['approval_tokens_required'])}`",
        f"- full_commercial_release_allowed: `{s['full_commercial_release_allowed']}`",
        f"- full_commercial_release_blocker_count: `{s['full_commercial_release_blocker_count']}`",
        f"- full_commercial_release_blocker_ids: `{';'.join(s['full_commercial_release_blocker_ids'])}`",
        f"- full_commercial_release_next_required_step: `{s['full_commercial_release_next_required_step']}`",
        f"- science_claim_promotion_gap_closure_open_gap_ids: `{';'.join(s['science_claim_promotion_gap_closure_open_gap_ids'])}`",
        f"- science_claim_promotion_gap_closure_current_next_action: `{s['science_claim_promotion_gap_closure_current_next_action']}`",
        f"- accuracy_parity_ligand_ranking_status: `{s['accuracy_parity_ligand_ranking_status']}`",
        f"- accuracy_parity_ligand_ranking_pr_auc: `{s['accuracy_parity_ligand_ranking_pr_auc']}`",
        f"- accuracy_parity_ligand_ranking_pr_auc_ci_low: `{s['accuracy_parity_ligand_ranking_pr_auc_ci_low']}`",
        f"- accuracy_parity_ligand_ranking_topk_hit_rate: `{s['accuracy_parity_ligand_ranking_topk_hit_rate']}`",
        f"- accuracy_parity_ligand_ranking_next_required_step: `{s['accuracy_parity_ligand_ranking_next_required_step']}`",
        f"- primary_full_commercial_release_blocker_id: `{s['primary_full_commercial_release_blocker_id']}`",
        f"- primary_full_commercial_release_blocker_requirement_id: `{s['primary_full_commercial_release_blocker_requirement_id']}`",
        f"- primary_full_commercial_release_blocker_tier: `{s['primary_full_commercial_release_blocker_tier']}`",
        f"- primary_full_commercial_release_blocker_blocked_row_count: `{s['primary_full_commercial_release_blocker_blocked_row_count']}`",
        f"- primary_full_commercial_release_blocker_first_blocked_evidence_row_id: `{s['primary_full_commercial_release_blocker_first_blocked_evidence_row_id']}`",
        f"- primary_full_commercial_release_blocker_receipt_csv: `{s['primary_full_commercial_release_blocker_receipt_csv']}`",
        f"- primary_full_commercial_release_blocker_approval_token_required: `{s['primary_full_commercial_release_blocker_approval_token_required']}`",
        f"- engine_refinement_claim_evidence_priority_packet_source_json: `{s['engine_refinement_claim_evidence_priority_packet_source_json']}`",
        f"- engine_refinement_claim_evidence_priority_packet_status: `{s['engine_refinement_claim_evidence_priority_packet_status']}`",
        f"- engine_refinement_claim_evidence_priority_packet_top_blocker_id: `{s['engine_refinement_claim_evidence_priority_packet_top_blocker_id']}`",
        f"- engine_refinement_claim_evidence_priority_packet_top_next_operator_step: `{s['engine_refinement_claim_evidence_priority_packet_top_next_operator_step']}`",
        "- engine_refinement_claim_evidence_priority_packet_metric_materialization_row_count: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_row_count']}`",
        "- engine_refinement_claim_evidence_priority_packet_metric_materialization_candidate_ready_count: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_ready_count']}`",
        "- engine_refinement_claim_evidence_priority_packet_metric_materialization_candidate_blocked_count: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_blocked_count']}`",
        "- engine_refinement_claim_evidence_priority_packet_coordinate_validation_pass_row_count: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count']}`",
        "- engine_refinement_claim_evidence_priority_packet_planned_metric_source_payload_count: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count']}`",
        "- engine_refinement_claim_evidence_priority_packet_existing_metric_source_payload_count: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count']}`",
        "- engine_refinement_claim_evidence_priority_packet_required_metric_source_payloads: "
        f"`{s['engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads']}`",
        f"- production_ai_registry_promotion_priority_status: `{s['production_ai_registry_promotion_priority_status']}`",
        f"- production_ai_registry_promotion_priority_top_gate_id: `{s['production_ai_registry_promotion_priority_top_gate_id']}`",
        f"- production_ai_registry_promotion_priority_top_required_input: `{s['production_ai_registry_promotion_priority_top_required_input']}`",
        f"- public_benchmark_work_order_status: `{s['public_benchmark_work_order_status']}`",
        f"- public_benchmark_open_suite_count: `{s['public_benchmark_open_suite_count']}`",
        f"- public_benchmark_materialization_required_suite_count: `{s['public_benchmark_materialization_required_suite_count']}`",
        f"- public_benchmark_scorecard_required_suite_count: `{s['public_benchmark_scorecard_required_suite_count']}`",
        f"- public_benchmark_continuous_validation_command_count: `{s['public_benchmark_continuous_validation_command_count']}`",
        f"- public_benchmark_input_preflight_blocked_count: `{s['public_benchmark_input_preflight_blocked_count']}`",
        f"- public_benchmark_input_preflight_approval_tokens_required: `{s['public_benchmark_input_preflight_approval_tokens_required']}`",
        f"- public_benchmark_suite_run_command_count: `{s['public_benchmark_suite_run_command_count']}`",
        f"- public_benchmark_suite_blocker_count: `{s['public_benchmark_suite_blocker_count']}`",
        f"- public_benchmark_suite_threshold_count: `{s['public_benchmark_suite_threshold_count']}`",
        f"- public_benchmark_suite_materialization_manifest_count: `{s['public_benchmark_suite_materialization_manifest_count']}`",
        f"- public_benchmark_suite_materialization_run_command_count: `{s['public_benchmark_suite_materialization_run_command_count']}`",
        f"- public_benchmark_suite_scorecard_command_count: `{s['public_benchmark_suite_scorecard_command_count']}`",
        f"- public_benchmark_suite_scorecard_row_csv_count: `{s['public_benchmark_suite_scorecard_row_csv_count']}`",
        f"- public_benchmark_suite_no_external_dependency_count: `{s['public_benchmark_suite_no_external_dependency_count']}`",
        f"- public_benchmark_local_artifact_preflight_ready_suite_count: `{s['public_benchmark_local_artifact_preflight_ready_suite_count']}`",
        f"- public_benchmark_local_artifact_preflight_blocked_suite_count: `{s['public_benchmark_local_artifact_preflight_blocked_suite_count']}`",
        f"- public_benchmark_missing_local_input_artifact_count: `{s['public_benchmark_missing_local_input_artifact_count']}`",
        f"- public_benchmark_missing_local_output_artifact_count: `{s['public_benchmark_missing_local_output_artifact_count']}`",
        f"- public_benchmark_result_generation_required_suite_count: `{s['public_benchmark_result_generation_required_suite_count']}`",
        f"- public_benchmark_result_generation_approval_token_required: `{s['public_benchmark_result_generation_approval_token_required']}`",
        f"- public_benchmark_benchmark_result_missing_artifact_count: `{s['public_benchmark_benchmark_result_missing_artifact_count']}`",
        f"- primary_action_id: `{s['primary_action_id']}`",
        f"- primary_action_status: `{s['primary_action_status']}`",
        f"- primary_action_required_input: `{s['primary_action_required_input']}`",
        f"- primary_action_recommended_action: `{s['primary_action_recommended_action']}`",
        f"- primary_bottleneck_sequence: `{s['primary_bottleneck_sequence']}`",
        f"- primary_bottleneck_kind: `{s['primary_bottleneck_kind']}`",
        f"- primary_bottleneck_phase: `{s['primary_bottleneck_phase']}`",
        f"- primary_bottleneck_root_cause_category: `{s['primary_bottleneck_root_cause_category']}`",
        f"- primary_bottleneck_locally_closable_without_operator_return: `{s['primary_bottleneck_locally_closable_without_operator_return']}`",
        f"- primary_bottleneck_required_external_return: `{s['primary_bottleneck_required_external_return']}`",
        f"- irreducible_external_return_bottleneck_count: `{s['irreducible_external_return_bottleneck_count']}`",
        f"- primary_bottleneck_command: `{s['primary_bottleneck_command']}`",
        f"- primary_bottleneck_command_candidate_count: `{s['primary_bottleneck_command_candidate_count']}`",
        "",
        "## Primary Command Candidates",
        "",
    ]
    if s["primary_bottleneck_command_candidates"]:
        lines.extend(f"- `{command}`" for command in s["primary_bottleneck_command_candidates"])
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Bottlenecks",
        "",
        "| seq | phase | kind | root_cause | local_close | inputs | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['phase']}` | `{row['bottleneck_kind']}` | "
            f"`{row['root_cause_category']}` | `{row['locally_closable_without_operator_return']}` | "
            f"`{row['required_inputs']}` | {row['recommended_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only briefing of current full-goal release bottlenecks.")
    parser.add_argument("--release-gate-json", default=DEFAULT_RELEASE_GATE_JSON)
    parser.add_argument("--burndown-json", default=DEFAULT_BURNDOWN_JSON)
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--intake-kit-json", default=DEFAULT_INTAKE_KIT_JSON)
    parser.add_argument("--completion-audit-json", default=DEFAULT_COMPLETION_AUDIT_JSON)
    parser.add_argument(
        "--engine-refinement-claim-evidence-priority-packet-json",
        default=DEFAULT_ENGINE_REFINEMENT_CLAIM_EVIDENCE_PRIORITY_PACKET_JSON,
    )
    parser.add_argument("--public-benchmark-work-order-json", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON)
    parser.add_argument("--public-benchmark-preflight-json", action="append", default=DEFAULT_PUBLIC_BENCHMARK_PREFLIGHT_JSONS)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_bottleneck_briefing(
        release_gate_packet=_read_json_if_present(args.release_gate_json),
        burndown_packet=_read_json_if_present(args.burndown_json),
        action_board_packet=_read_json_if_present(args.action_board_json),
        intake_kit_packet=_read_json_if_present(args.intake_kit_json),
        completion_audit_packet=_read_json_if_present(args.completion_audit_json),
        engine_refinement_claim_evidence_priority_packet=_read_json_if_present(
            args.engine_refinement_claim_evidence_priority_packet_json
        ),
        public_benchmark_work_order_packet=_read_json_if_present(args.public_benchmark_work_order_json),
        public_benchmark_preflight_packets=[
            _read_json_if_present(path) for path in (args.public_benchmark_preflight_json or [])
        ],
        public_benchmark_preflight_paths=list(args.public_benchmark_preflight_json or []),
        release_gate_path=args.release_gate_json,
        burndown_path=args.burndown_json,
        action_board_path=args.action_board_json,
        intake_kit_path=args.intake_kit_json,
        completion_audit_path=args.completion_audit_json,
        engine_refinement_claim_evidence_priority_packet_path=(
            args.engine_refinement_claim_evidence_priority_packet_json
        ),
        public_benchmark_work_order_path=args.public_benchmark_work_order_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
