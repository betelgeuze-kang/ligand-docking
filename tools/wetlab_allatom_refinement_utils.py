#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.native_target_registry import find_matching_target_row, resolve_repo_native_entry
from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _optional_float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except Exception:
        return None


def _optional_int(value: Any) -> int | None:
    try:
        if value in {None, ""}:
            return None
        return int(value)
    except Exception:
        return None


def _is_empty_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            text = _text(item)
            if text and text not in items:
                items.append(text)
        return items
    text = _text(value)
    return [text] if text else []


_RANKING_SCORE_PRIORITY = (
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "binding_score_composite_v6",
    "binding_score_composite_v5",
    "binding_score_composite_v4",
    "binding_score_composite_v3",
    "binding_score_composite_v2",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
)

_RANKING_OVERRIDE_KEYS = (
    "selection_score_col",
    "ranking_score_col_override",
    "ranking_score_col",
    "selected_score_col",
    "active_score_col",
    "score_col",
)

_COMMERCIAL_V2_OPTIONAL_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "replicate_count": (
        "replicate_count",
        "replicate_group_size",
        "replica_count",
        "replicates_observed",
        "replicates_total",
        "replicates",
        "n_replicates",
        "num_replicates",
        "seed_replicates",
        "trajectory_replicates",
    ),
    "replicate_pass_fraction": (
        "replicate_pass_fraction",
        "replicate_success_fraction",
        "replicate_hit_fraction",
        "replicate_support_fraction",
        "replicate_consensus_fraction",
        "pass_fraction",
        "success_fraction",
        "support_fraction",
    ),
    "median_mean_min_distance_A": (
        "median_mean_min_distance_A",
        "mean_min_distance_median_A",
        "distance_median_A",
        "replicate_median_mean_min_distance_A",
    ),
    "mean_min_distance_iqr_A": (
        "mean_min_distance_iqr_A",
        "distance_iqr_A",
        "replicate_distance_iqr_A",
        "median_mean_min_distance_iqr_A",
    ),
    "median_contact_fraction": (
        "median_contact_fraction",
        "contact_fraction_median",
        "contact_occupancy_fraction",
        "contact_occupancy",
        "replicate_contact_fraction_median",
    ),
    "pose_cluster_dominance": (
        "pose_cluster_dominance",
        "cluster_dominance",
        "dominant_pose_fraction",
        "pose_cluster_fraction",
        "largest_pose_cluster_fraction",
    ),
    "pose_preservation_rmsd_A": (
        "pose_preservation_rmsd_A",
        "replicate_pose_preservation_rmsd_A",
        "pose_rmsd_A",
        "backmapping_pose_rmsd_A",
    ),
    "backmapping_consistency_score": (
        "backmapping_consistency_score",
        "backmap_consistency_score",
        "pose_consistency_score",
    ),
    "local_minimization_survival_fraction": (
        "local_minimization_survival_fraction",
        "minimization_survival_fraction",
        "local_min_survival_fraction",
        "survival_fraction",
    ),
}

_COMMERCIAL_V2_OPTIONAL_ROW_FIELDS = tuple(
    dict.fromkeys(
        alias
        for aliases in _COMMERCIAL_V2_OPTIONAL_FIELD_ALIASES.values()
        for alias in aliases
    )
)

_CLAIM_GATE_SEMANTICS_VERSION = "claim_equivalence_semantics_v2"
_CLAIM_GATE_SEMI_HARD_TARGET_GROUPS: dict[str, frozenset[str]] = {
    "neglected_disease_priority_v1": frozenset(
        {
            "t_cruzi_pde",
            "t_cruzi_krs1",
            "l_braziliensis_dhodh",
            "dpre1",
            "dengue_ns2b_ns3_protease",
        }
    )
}


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = _text(value).lower()
    if text in {"true", "1", "yes", "y", "required", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _normalize_claim_requirement_mode(value: Any) -> str:
    text = _text(value).lower().replace("-", "_")
    if text in {"semi_hard", "semihard", "required", "claim_required"}:
        return "semi_hard"
    if text == "optional":
        return "optional"
    return ""


def _resolve_claim_requirement_policy(
    *,
    target_id: str,
    runner_summary: dict[str, Any],
    runner_structured: dict[str, Any],
    claim_summary: dict[str, Any],
    gate_summary: dict[str, Any],
) -> dict[str, Any]:
    target_slug = slug(target_id) if _text(target_id) else ""
    target_group = ""
    requirement_mode = ""
    requirement_provenance = ""

    explicit_mode = ""
    for source, provenance in (
        (claim_summary, "claim_readiness_json"),
        (gate_summary, "equivalence_gate_json"),
        (runner_structured, "runner_structured"),
        (runner_summary, "runner_summary"),
    ):
        explicit_mode = _normalize_claim_requirement_mode(
            source.get("claim_gate_requirement_mode")
            or source.get("claim_gate_mode")
            or source.get("claim_gate_requirement")
        )
        if explicit_mode:
            requirement_mode = explicit_mode
            requirement_provenance = provenance
            target_group = _text(source.get("claim_gate_target_group"))
            break

    if not requirement_mode:
        for group_name, members in _CLAIM_GATE_SEMI_HARD_TARGET_GROUPS.items():
            if target_slug in members:
                requirement_mode = "semi_hard"
                requirement_provenance = "target_group_default"
                target_group = group_name
                break

    if not requirement_mode:
        requirement_mode = "optional"
        requirement_provenance = "fallback_optional"

    required_for_final_wetlab = requirement_mode == "semi_hard"
    required_for_commercial_readiness = requirement_mode == "semi_hard"

    explicit_required_for_final = None
    explicit_required_for_commercial = None
    for source in (claim_summary, gate_summary, runner_structured, runner_summary):
        if explicit_required_for_final is None:
            explicit_required_for_final = _optional_bool(source.get("claim_gate_required_for_final_wetlab"))
        if explicit_required_for_commercial is None:
            explicit_required_for_commercial = _optional_bool(
                source.get("claim_gate_required_for_commercial_readiness")
            )
    if explicit_required_for_final is not None:
        required_for_final_wetlab = explicit_required_for_final
    if explicit_required_for_commercial is not None:
        required_for_commercial_readiness = explicit_required_for_commercial

    requirement_reason = ""
    for source in (claim_summary, gate_summary, runner_structured, runner_summary):
        requirement_reason = _text(source.get("claim_gate_requirement_reason"))
        if requirement_reason:
            break
    if not requirement_reason:
        if requirement_mode == "semi_hard":
            requirement_reason = (
                f"{target_id or target_slug} is in the {target_group or 'claim-sensitive'} target group, "
                "so final wetlab advancement expects claim/equivalence evidence before release."
            )
        else:
            requirement_reason = (
                f"{target_id or target_slug} uses optional claim/equivalence semantics; missing claim evidence "
                "does not block the band gate by default."
            )

    requirement_actions = ["resolve_claim_equivalence_gate"]
    if required_for_final_wetlab or required_for_commercial_readiness:
        requirement_actions.insert(0, "produce_claim_equivalence_packet")
    requirement_actions = list(dict.fromkeys(_normalize_text_list(requirement_actions)))

    return {
        "claim_gate_semantics_version": _CLAIM_GATE_SEMANTICS_VERSION,
        "claim_gate_requirement_mode": requirement_mode,
        "claim_gate_requirement_provenance": requirement_provenance,
        "claim_gate_target_group": target_group,
        "claim_gate_target_slug": target_slug,
        "claim_gate_required_for_final_wetlab": required_for_final_wetlab,
        "claim_gate_required_for_commercial_readiness": required_for_commercial_readiness,
        "claim_gate_requirement_reason": requirement_reason,
        "claim_gate_requirement_actions": requirement_actions,
    }


def _resolve_claim_gate_status(
    *,
    claim_gate_available: bool,
    claim_ready_for_allatom: Any,
    pass_core_gate: Any,
    requirement_mode: str,
    required_for_final_wetlab: bool,
    required_for_commercial_readiness: bool,
    requirement_actions: list[str],
) -> dict[str, Any]:
    claim_ready = _optional_bool(claim_ready_for_allatom)
    core_gate_pass = _optional_bool(pass_core_gate)

    if claim_gate_available:
        if claim_ready is True:
            status = "claim_ready"
            satisfied = True
            status_reason = "Claim/equivalence evidence is available and passes the all-atom claim readiness gate."
            primary_action = ""
        elif claim_ready is False:
            status = "claim_blocked"
            satisfied = False
            status_reason = "Claim/equivalence evidence is available but did not reach claim-ready status."
            primary_action = "resolve_claim_equivalence_gate"
        else:
            status = "claim_incomplete"
            satisfied = False
            status_reason = "Claim/equivalence artifacts exist, but the final claim-ready field is still missing."
            primary_action = "complete_claim_equivalence_metrics"
    elif required_for_final_wetlab or required_for_commercial_readiness or requirement_mode == "semi_hard":
        status = "claim_required_unavailable"
        satisfied = False
        status_reason = (
            "This target uses semi-hard claim semantics, but no claim/equivalence artifact is attached yet."
        )
        primary_action = "produce_claim_equivalence_packet"
    else:
        status = "claim_optional_unavailable"
        satisfied = None
        status_reason = "Claim/equivalence artifacts are not attached, but this target is currently optional."
        primary_action = "produce_claim_equivalence_packet"

    blocking_metrics: list[str] = []
    missing_metrics: list[str] = []
    if status == "claim_required_unavailable":
        missing_metrics.append("claim_gate_required_unavailable")
    elif status == "claim_blocked":
        if core_gate_pass is False:
            blocking_metrics.append("pass_core_gate")
        blocking_metrics.append("claim_ready_for_allatom")
    elif status == "claim_incomplete":
        if core_gate_pass is False:
            blocking_metrics.append("pass_core_gate")
        missing_metrics.append("claim_ready_for_allatom_missing")

    action_rollup = ", ".join(
        list(
            dict.fromkeys(
                [primary_action] + _normalize_text_list(requirement_actions)
                if primary_action
                else _normalize_text_list(requirement_actions)
            )
        )
    )

    return {
        "claim_gate_status": status,
        "claim_gate_satisfied": satisfied,
        "claim_gate_status_reason": status_reason,
        "claim_gate_primary_action": primary_action,
        "claim_gate_action_rollup": action_rollup,
        "claim_gate_blocking_metrics": blocking_metrics,
        "claim_gate_missing_metrics_detail": missing_metrics,
    }


def _collect_score_col_requests(*sources: Any) -> list[str]:
    requested: list[str] = []

    def _push(value: Any) -> None:
        text = _text(value)
        if text and text not in requested:
            requested.append(text)

    def _visit(source: Any) -> None:
        if isinstance(source, dict):
            for key in _RANKING_OVERRIDE_KEYS:
                _push(source.get(key))
            residual_proto = source.get("residual_prototype")
            if isinstance(residual_proto, dict):
                _push(residual_proto.get("active_score_col"))
            for nested_key in ("summary", "structured"):
                nested = source.get(nested_key)
                if isinstance(nested, dict):
                    _visit(nested)
            stages = source.get("stages")
            if isinstance(stages, dict):
                for stage_key in ("stage3_scoring", "stage5_ranking", "stage6_operational_gate"):
                    stage_payload = stages.get(stage_key)
                    if isinstance(stage_payload, dict):
                        _visit(stage_payload)
                        _push(stage_payload.get("ranking_score_col_used"))
                        _push(stage_payload.get("probability_score_col_used"))
            return
        if isinstance(source, (list, tuple, set)):
            for item in source:
                _visit(item)
            return
        _push(source)

    for source in sources:
        _visit(source)
    return requested


def _score_col_has_numeric_values(rows: list[dict[str, Any]], score_col: str) -> bool:
    if not _text(score_col):
        return False
    for row in rows:
        if _optional_float((row or {}).get(score_col)) is not None:
            return True
    return False


def _choose_active_score_column(
    rows: list[dict[str, Any]],
    *,
    requested_score_col: Any = "",
    score_sources: tuple[Any, ...] = (),
) -> dict[str, Any]:
    available_columns = [col for col in _RANKING_SCORE_PRIORITY if _score_col_has_numeric_values(rows, col)]
    requested_columns = _collect_score_col_requests(requested_score_col, *score_sources)
    for score_col in requested_columns:
        if _score_col_has_numeric_values(rows, score_col):
            return {
                "score_col": score_col,
                "score_source": "explicit_override",
                "requested_score_col": score_col,
                "available_score_cols": available_columns,
            }
    for score_col in _RANKING_SCORE_PRIORITY:
        if _score_col_has_numeric_values(rows, score_col):
            return {
                "score_col": score_col,
                "score_source": "auto_priority",
                "requested_score_col": requested_columns[0] if requested_columns else "",
                "available_score_cols": available_columns,
            }
    fallback_col = requested_columns[0] if requested_columns else "binding_energy_proxy"
    return {
        "score_col": fallback_col,
        "score_source": "fallback_default",
        "requested_score_col": requested_columns[0] if requested_columns else "",
        "available_score_cols": available_columns,
    }


def _selection_ranking_score_value(row: dict[str, Any], score_col: str) -> float | None:
    return _optional_float((row or {}).get(score_col))


def _selection_ranking_key(row: dict[str, Any], score_col: str) -> tuple[Any, ...]:
    score_value = _selection_ranking_score_value(row, score_col)
    distance_value = _optional_float((row or {}).get("mean_min_distance_A"))
    return (
        score_value is None,
        score_value if score_value is not None else float("inf"),
        -_safe_float((row or {}).get("stability_score"), 0.0),
        distance_value if distance_value is not None else float("inf"),
        _text((row or {}).get("ligand_id")),
        _text((row or {}).get("queue_id")),
    )


def _rank_rows_by_active_score(
    rows: list[dict[str, Any]],
    *,
    requested_score_col: Any = "",
    score_sources: tuple[Any, ...] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranking_meta = _choose_active_score_column(
        rows,
        requested_score_col=requested_score_col,
        score_sources=score_sources,
    )
    score_col = _text(ranking_meta.get("score_col")) or "binding_energy_proxy"
    return sorted(rows, key=lambda row: _selection_ranking_key(row, score_col)), ranking_meta


def _count_rows_in_distance_band(
    rows: list[dict[str, Any]],
    *,
    lower_exclusive_A: float,
    upper_inclusive_A: float,
) -> int:
    return sum(
        1
        for row in rows
        if lower_exclusive_A < _safe_float((row or {}).get("mean_min_distance_A")) <= upper_inclusive_A
    )


def compute_wetlab_gate_summary(
    *,
    promoted_rows: list[dict[str, Any]],
    selected_threshold_A: float,
    strict_threshold_A: float = 2.5,
    near_threshold_A: float = 3.0,
) -> dict[str, Any]:
    packet_ready_for_operator_review = bool(promoted_rows)
    strict_candidate_count = _count_rows_in_distance_band(
        promoted_rows,
        lower_exclusive_A=0.0,
        upper_inclusive_A=strict_threshold_A,
    )
    near_candidate_count = _count_rows_in_distance_band(
        promoted_rows,
        lower_exclusive_A=strict_threshold_A,
        upper_inclusive_A=near_threshold_A,
    )

    gate_mode = "manual_review_only"
    intended_band_label = "unsupported_selected_threshold"
    intended_min_exclusive_A = 0.0
    intended_max_inclusive_A = 0.0
    band_candidate_count = 0
    failed_metrics: list[str] = []

    selected_threshold_A = _safe_float(selected_threshold_A, strict_threshold_A)
    if 0 < selected_threshold_A <= strict_threshold_A:
        gate_mode = "strict_only"
        intended_band_label = f"0 < mean_min_distance_A <= {strict_threshold_A:.3f}A"
        intended_max_inclusive_A = strict_threshold_A
        band_candidate_count = strict_candidate_count
    elif strict_threshold_A < selected_threshold_A <= near_threshold_A:
        gate_mode = "near_only"
        intended_band_label = f"{strict_threshold_A:.3f}A < mean_min_distance_A <= {near_threshold_A:.3f}A"
        intended_min_exclusive_A = strict_threshold_A
        intended_max_inclusive_A = near_threshold_A
        band_candidate_count = near_candidate_count
    else:
        failed_metrics.append("selected_threshold_A")

    wetlab_gate_pass = packet_ready_for_operator_review and gate_mode != "manual_review_only" and band_candidate_count > 0
    if not packet_ready_for_operator_review:
        failed_metrics.append("promoted_rows")
        wetlab_gate_reason = (
            "No promoted pseudo all-atom rows are available yet, so this packet is not wetlab-ready."
        )
    elif gate_mode == "manual_review_only":
        wetlab_gate_reason = (
            f"Selected threshold {selected_threshold_A:.3f}A does not map to a supported strict/near wetlab gate; manual review only."
        )
    elif band_candidate_count <= 0:
        failed_metrics.append("mean_min_distance_A")
        wetlab_gate_reason = (
            f"Promoted rows are available for operator review, but none met the {gate_mode} wetlab gate band ({intended_band_label})."
        )
    else:
        wetlab_gate_reason = (
            f"At least one promoted row met the {gate_mode} wetlab gate band ({intended_band_label})."
        )

    return {
        "packet_ready_for_operator_review": packet_ready_for_operator_review,
        "strict_candidate_count": strict_candidate_count,
        "near_candidate_count": near_candidate_count,
        "wetlab_gate_pass": wetlab_gate_pass,
        "wetlab_gate_mode": gate_mode,
        "wetlab_gate_band_candidate_count": band_candidate_count,
        "wetlab_gate_failed_metrics": failed_metrics,
        "wetlab_gate_failed_metric_count": len(failed_metrics),
        "wetlab_gate_reason": wetlab_gate_reason,
        "wetlab_gate_thresholds": {
            "strict_threshold_A": strict_threshold_A,
            "near_threshold_A": near_threshold_A,
            "selected_threshold_A": selected_threshold_A,
            "intended_band": intended_band_label,
            "intended_min_exclusive_A": intended_min_exclusive_A,
            "intended_max_inclusive_A": intended_max_inclusive_A,
        },
    }


def resolve_optional_claim_gate_summary(
    *,
    target_id: str = "",
    claim_readiness_json: str = "",
    equivalence_gate_json: str = "",
    runner_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runner_payload = runner_payload or {}
    runner_summary = _summary(runner_payload)
    runner_structured = dict((runner_payload or {}).get("structured", {}) or {})

    claim_json = (
        _text(claim_readiness_json)
        or _text(runner_structured.get("allatom_claim_readiness_json"))
        or _text(runner_summary.get("allatom_claim_readiness_json"))
    )
    claim_payload = _load_json_if_exists(_under_root(claim_json)) if claim_json else {}
    claim_summary = _summary(claim_payload)
    claim_artifacts = dict(claim_payload.get("artifacts", {}) or {})

    gate_json = (
        _text(equivalence_gate_json)
        or _text(runner_structured.get("allatom_equivalence_gate_json"))
        or _text(runner_summary.get("allatom_equivalence_gate_json"))
        or _text(claim_artifacts.get("gate_json"))
    )
    gate_payload = _load_json_if_exists(_under_root(gate_json)) if gate_json else {}
    gate_summary = _summary(gate_payload)
    gate_csv = (
        _text(runner_structured.get("allatom_equivalence_gate_csv"))
        or _text(runner_summary.get("allatom_equivalence_gate_csv"))
        or _text(claim_artifacts.get("gate_csv"))
    )

    claim_gate_available = bool(claim_summary or gate_summary)
    pass_core_gate = None
    claim_ready_for_allatom = None
    core_failed_metrics = None
    core_missing_metrics = None
    claim_failed_metrics = None
    claim_missing_metrics = None
    if claim_gate_available:
        pass_core_gate = claim_summary.get("pass_core_gate", gate_summary.get("pass_core_gate"))
        claim_ready_for_allatom = claim_summary.get(
            "claim_ready_for_allatom",
            gate_summary.get("claim_ready_for_allatom"),
        )
        core_failed_metrics = claim_summary.get("core_failed_metrics", gate_summary.get("core_failed_metrics"))
        core_missing_metrics = claim_summary.get("core_missing_metrics", gate_summary.get("core_missing_metrics"))
        claim_failed_metrics = claim_summary.get("claim_failed_metrics", gate_summary.get("claim_failed_metrics"))
        claim_missing_metrics = claim_summary.get("claim_missing_metrics", gate_summary.get("claim_missing_metrics"))

    claim_gate_source = ""
    if claim_summary:
        claim_gate_source = "claim_readiness_json"
    elif gate_summary:
        claim_gate_source = "equivalence_gate_json"

    policy = _resolve_claim_requirement_policy(
        target_id=target_id,
        runner_summary=runner_summary,
        runner_structured=runner_structured,
        claim_summary=claim_summary,
        gate_summary=gate_summary,
    )
    status = _resolve_claim_gate_status(
        claim_gate_available=claim_gate_available,
        claim_ready_for_allatom=claim_ready_for_allatom,
        pass_core_gate=pass_core_gate,
        requirement_mode=_text(policy.get("claim_gate_requirement_mode")),
        required_for_final_wetlab=bool(policy.get("claim_gate_required_for_final_wetlab", False)),
        required_for_commercial_readiness=bool(
            policy.get("claim_gate_required_for_commercial_readiness", False)
        ),
        requirement_actions=_normalize_text_list(policy.get("claim_gate_requirement_actions")),
    )

    return {
        "claim_gate_available": claim_gate_available,
        "claim_gate_source": claim_gate_source,
        "claim_readiness_json": claim_json,
        "equivalence_gate_json": gate_json,
        "equivalence_gate_csv": gate_csv,
        "policy_version": _text(claim_summary.get("policy_version")) or _text(gate_summary.get("policy_version")),
        "pass_core_gate": pass_core_gate,
        "claim_ready_for_allatom": claim_ready_for_allatom,
        "core_failed_metrics": core_failed_metrics,
        "core_missing_metrics": core_missing_metrics,
        "claim_failed_metrics": claim_failed_metrics,
        "claim_missing_metrics": claim_missing_metrics,
        **policy,
        **status,
    }


def compute_final_wetlab_gate_summary(
    *,
    wetlab_gate_summary: dict[str, Any],
    claim_gate_summary: dict[str, Any],
) -> dict[str, Any]:
    band_gate_pass = bool((wetlab_gate_summary or {}).get("wetlab_gate_pass", False))
    claim_gate_available = bool((claim_gate_summary or {}).get("claim_gate_available", False))
    claim_requirement_mode = _text((claim_gate_summary or {}).get("claim_gate_requirement_mode"))
    claim_required_for_final_wetlab = bool(
        (claim_gate_summary or {}).get("claim_gate_required_for_final_wetlab", False)
    )
    claim_gate_status = _text((claim_gate_summary or {}).get("claim_gate_status"))
    claim_gate_satisfied = (claim_gate_summary or {}).get("claim_gate_satisfied")
    claim_gate_primary_action = _text((claim_gate_summary or {}).get("claim_gate_primary_action"))
    claim_gate_status_reason = _text((claim_gate_summary or {}).get("claim_gate_status_reason"))
    claim_blocking_metrics = _normalize_text_list(
        (claim_gate_summary or {}).get("claim_gate_blocking_metrics")
    )
    claim_missing_metrics = _normalize_text_list(
        (claim_gate_summary or {}).get("claim_gate_missing_metrics_detail")
    )

    final_gate_mode = "band_only"
    final_gate_failed_metrics = list((wetlab_gate_summary or {}).get("wetlab_gate_failed_metrics", []) or [])
    final_gate_missing_metrics: list[str] = []
    final_gate_blocking_domain = "band_gate"
    if claim_required_for_final_wetlab:
        final_gate_mode = "band_plus_semi_hard_claim_ready_for_allatom"
        final_gate_blocking_domain = "claim_equivalence_gate"
        final_gate_failed_metrics.extend(claim_blocking_metrics)
        final_gate_missing_metrics.extend(claim_missing_metrics)
    elif claim_gate_available:
        final_gate_mode = "band_plus_optional_claim_ready_for_allatom"
        final_gate_blocking_domain = "claim_equivalence_gate" if claim_gate_status.startswith("claim_") else "band_gate"
        final_gate_failed_metrics.extend(claim_blocking_metrics)
        final_gate_missing_metrics.extend(claim_missing_metrics)

    final_gate_failed_metrics = list(
        dict.fromkeys(_text(metric) for metric in final_gate_failed_metrics if _text(metric))
    )
    final_gate_missing_metrics = list(
        dict.fromkeys(_text(metric) for metric in final_gate_missing_metrics if _text(metric))
    )
    if claim_required_for_final_wetlab:
        final_gate_pass = band_gate_pass and claim_gate_satisfied is True
    elif claim_gate_available:
        final_gate_pass = band_gate_pass and claim_gate_satisfied is True
    else:
        final_gate_pass = band_gate_pass
    if final_gate_pass:
        reason = (
            "passed the pseudo all-atom wetlab band gate and the required semi-hard claim/equivalence gate."
            if claim_required_for_final_wetlab
            else "passed the pseudo all-atom wetlab band gate and the optional claim/equivalence gate."
            if claim_gate_available
            else "passed the pseudo all-atom wetlab band gate."
        )
    elif claim_required_for_final_wetlab and band_gate_pass:
        reason = (
            "passed the pseudo all-atom wetlab band gate but the semi-hard claim/equivalence requirement is still unsatisfied."
        )
    elif claim_gate_available and band_gate_pass:
        reason = "passed the pseudo all-atom wetlab band gate but failed the optional claim/equivalence gate."
    else:
        reason = _text((wetlab_gate_summary or {}).get("wetlab_gate_reason"))
    if claim_gate_status_reason and claim_required_for_final_wetlab and not final_gate_pass:
        reason = f"{reason} {claim_gate_status_reason}".strip()

    required_next_actions = []
    if claim_required_for_final_wetlab and not final_gate_pass:
        required_next_actions = _normalize_text_list(
            [claim_gate_primary_action]
            + list((claim_gate_summary or {}).get("claim_gate_requirement_actions", []) or [])
        )

    return {
        "wetlab_final_gate_mode": final_gate_mode,
        "wetlab_final_gate_pass": final_gate_pass,
        "wetlab_final_gate_failed_metrics": final_gate_failed_metrics,
        "wetlab_final_gate_missing_metrics": final_gate_missing_metrics,
        "wetlab_final_gate_failed_metric_count": len(final_gate_failed_metrics),
        "wetlab_final_gate_missing_metric_count": len(final_gate_missing_metrics),
        "wetlab_final_gate_reason": reason,
        "wetlab_final_gate_blocking_domain": final_gate_blocking_domain,
        "wetlab_final_gate_required_next_actions": required_next_actions,
    }


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _distance_component_score(distance_A: float | None, *, strict_threshold_A: float, near_threshold_A: float) -> float:
    if distance_A is None or distance_A <= 0:
        return 0.0
    if distance_A <= strict_threshold_A:
        return 100.0
    if distance_A <= near_threshold_A:
        band_width = max(near_threshold_A - strict_threshold_A, 1e-6)
        frac = (distance_A - strict_threshold_A) / band_width
        return _clamp_score(100.0 - frac * 45.0)
    if distance_A <= near_threshold_A + 0.5:
        frac = (distance_A - near_threshold_A) / 0.5
        return _clamp_score(55.0 - frac * 40.0)
    return 0.0


def _energy_component_score(energy_value: float | None) -> float:
    if energy_value is None:
        return 0.0
    if energy_value <= -0.20:
        return 100.0
    if energy_value <= -0.15:
        return 90.0
    if energy_value <= -0.10:
        return 75.0
    if energy_value <= -0.07:
        return 60.0
    if energy_value <= -0.05:
        return 50.0
    if energy_value <= 0.0:
        return 25.0
    return 0.0


def _stability_component_score(stability_score: float | None) -> float:
    if stability_score is None:
        return 0.0
    if stability_score >= 0.50:
        return 100.0
    if stability_score >= 0.40:
        return 85.0
    if stability_score >= 0.35:
        return 75.0
    if stability_score >= 0.30:
        return 60.0
    if stability_score >= 0.25:
        return 45.0
    return 20.0


def _contact_component_score(contact_fraction: float | None) -> float:
    if contact_fraction is None:
        return 0.0
    if contact_fraction >= 0.70:
        return 100.0
    if contact_fraction >= 0.60:
        return 85.0
    if contact_fraction >= 0.50:
        return 70.0
    if contact_fraction >= 0.40:
        return 55.0
    if contact_fraction >= 0.30:
        return 35.0
    return 15.0


def _uncertainty_component_score(std_value: float | None) -> float:
    if std_value is None:
        return 0.0
    if std_value <= 0.08:
        return 100.0
    if std_value <= 0.12:
        return 85.0
    if std_value <= 0.18:
        return 70.0
    if std_value <= 0.25:
        return 45.0
    if std_value <= 0.35:
        return 20.0
    return 0.0


def _support_component_score(trajectory_frames: int | None) -> float:
    if trajectory_frames is None or trajectory_frames <= 0:
        return 0.0
    if trajectory_frames >= 250:
        return 100.0
    if trajectory_frames >= 200:
        return 85.0
    if trajectory_frames >= 150:
        return 70.0
    if trajectory_frames >= 100:
        return 50.0
    return 25.0


def _first_present_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and not _is_empty_value(payload.get(key)):
            return payload.get(key)
    return None


def _resolve_optional_metric_float(payload: dict[str, Any], metric_name: str) -> float | None:
    return _optional_float(_first_present_value(payload, _COMMERCIAL_V2_OPTIONAL_FIELD_ALIASES.get(metric_name, ())))


def _resolve_optional_metric_int(payload: dict[str, Any], metric_name: str) -> int | None:
    return _optional_int(_first_present_value(payload, _COMMERCIAL_V2_OPTIONAL_FIELD_ALIASES.get(metric_name, ())))


def _extract_commercial_v2_optional_fields(payload: dict[str, Any]) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    for key in _COMMERCIAL_V2_OPTIONAL_ROW_FIELDS:
        if key in payload and not _is_empty_value(payload.get(key)):
            extracted[key] = payload.get(key)
    return extracted


def _weighted_optional_score(*weighted_scores: tuple[float | None, float]) -> float | None:
    total_weight = 0.0
    total_score = 0.0
    for score, weight in weighted_scores:
        if score is None or weight <= 0:
            continue
        total_score += float(score) * float(weight)
        total_weight += float(weight)
    if total_weight <= 0:
        return None
    return _clamp_score(total_score / total_weight)


def _replicate_support_component_score(replicate_count: int | None) -> float | None:
    if replicate_count is None or replicate_count <= 0:
        return None
    if replicate_count >= 8:
        return 100.0
    if replicate_count >= 5:
        return 85.0
    if replicate_count >= 3:
        return 70.0
    if replicate_count >= 2:
        return 55.0
    return 35.0


def _fraction_component_score(value: float | None) -> float | None:
    if value is None:
        return None
    if value >= 0.90:
        return 100.0
    if value >= 0.75:
        return 85.0
    if value >= 0.60:
        return 70.0
    if value >= 0.45:
        return 55.0
    if value >= 0.30:
        return 35.0
    return 15.0


def _iqr_component_score(iqr_A: float | None) -> float | None:
    if iqr_A is None:
        return None
    if iqr_A <= 0.10:
        return 100.0
    if iqr_A <= 0.20:
        return 85.0
    if iqr_A <= 0.35:
        return 70.0
    if iqr_A <= 0.50:
        return 55.0
    if iqr_A <= 0.75:
        return 30.0
    return 10.0


def _rmsd_component_score(rmsd_A: float | None) -> float | None:
    if rmsd_A is None or rmsd_A < 0:
        return None
    if rmsd_A <= 1.0:
        return 100.0
    if rmsd_A <= 1.5:
        return 85.0
    if rmsd_A <= 2.0:
        return 70.0
    if rmsd_A <= 2.5:
        return 55.0
    if rmsd_A <= 3.5:
        return 30.0
    return 0.0


def _commercial_decision_class(
    *,
    hard_gate_pass: bool,
    overall_score: float,
    soft_score: float,
    confidence_score: float,
    distance_A: float | None,
    near_threshold_A: float,
    packet_ready_for_operator_review: bool,
) -> str:
    if hard_gate_pass and overall_score >= 80.0 and confidence_score >= 70.0:
        return "commercial_wetlab_ready"
    if packet_ready_for_operator_review and distance_A is not None and 0 < distance_A <= near_threshold_A and soft_score >= 60.0:
        return "commercial_borderline_refine"
    if packet_ready_for_operator_review and soft_score >= 45.0:
        return "commercial_review_only"
    if packet_ready_for_operator_review:
        return "commercial_recycle_or_rework"
    return "commercial_insufficient_signal"


def _commercial_risk_bucket(*, hard_gate_pass: bool, overall_score: float, confidence_score: float) -> str:
    if hard_gate_pass and overall_score >= 80.0 and confidence_score >= 70.0:
        return "low"
    if overall_score >= 65.0 and confidence_score >= 60.0:
        return "moderate"
    if overall_score >= 45.0:
        return "high"
    return "critical"


def _commercial_upgrade_actions(
    *,
    distance_A: float | None,
    selected_threshold_A: float,
    energy_value: float | None,
    stability_score: float | None,
    contact_fraction: float | None,
    std_value: float | None,
    trajectory_frames: int | None,
    claim_gate_summary: dict[str, Any] | None,
) -> list[str]:
    claim_gate_summary = dict(claim_gate_summary or {})
    actions: list[str] = []
    if distance_A is None or distance_A <= 0:
        actions.append("restore_pose_distance_metric")
    elif distance_A > selected_threshold_A:
        actions.append("tighten_pose_geometry_under_strict_gate")
    if energy_value is None:
        actions.append("restore_binding_energy_metric")
    elif energy_value > -0.05:
        actions.append("strengthen_binding_energy_proxy")
    if stability_score is None:
        actions.append("restore_stability_metric")
    elif stability_score < 0.35:
        actions.append("raise_trajectory_stability")
    if contact_fraction is None:
        actions.append("restore_contact_occupancy_metric")
    elif contact_fraction < 0.50:
        actions.append("raise_contact_occupancy")
    if std_value is None:
        actions.append("restore_uncertainty_metric")
    elif std_value > 0.18:
        actions.append("reduce_mmpbsa_uncertainty")
    if trajectory_frames is None or trajectory_frames <= 0:
        actions.append("restore_trajectory_support_metric")
    elif trajectory_frames < 180:
        actions.append("increase_trajectory_support")
    claim_gate_available = bool(claim_gate_summary.get("claim_gate_available", False))
    claim_gate_satisfied = claim_gate_summary.get("claim_gate_satisfied")
    claim_primary_action = _text(claim_gate_summary.get("claim_gate_primary_action"))
    claim_requirement_mode = _text(claim_gate_summary.get("claim_gate_requirement_mode"))
    if claim_gate_available and claim_gate_satisfied is not True:
        actions.append(claim_primary_action or "resolve_claim_equivalence_gate")
    elif claim_requirement_mode == "semi_hard" and claim_gate_satisfied is not True:
        actions.append(claim_primary_action or "produce_claim_equivalence_packet")
    return actions


def _commercial_claim_semantics_fields(
    claim_gate_summary: dict[str, Any] | None,
    *,
    schema_suffix: str,
) -> dict[str, Any]:
    suffix = _text(schema_suffix).lower() or "v1"
    if not suffix.startswith("v"):
        suffix = f"v{suffix}"
    claim_gate_summary = dict(claim_gate_summary or {})
    key = lambda name: f"commercial_{name}_{suffix}"
    return {
        key("claim_semantics_version"): _text(claim_gate_summary.get("claim_gate_semantics_version")),
        key("claim_gate_available"): bool(claim_gate_summary.get("claim_gate_available", False)),
        key("claim_gate_status"): _text(claim_gate_summary.get("claim_gate_status")),
        key("claim_gate_satisfied"): claim_gate_summary.get("claim_gate_satisfied"),
        key("claim_requirement_mode"): _text(claim_gate_summary.get("claim_gate_requirement_mode")),
        key("claim_requirement_provenance"): _text(
            claim_gate_summary.get("claim_gate_requirement_provenance")
        ),
        key("claim_target_group"): _text(claim_gate_summary.get("claim_gate_target_group")),
        key("claim_required_for_final_wetlab"): bool(
            claim_gate_summary.get("claim_gate_required_for_final_wetlab", False)
        ),
        key("claim_required_for_commercial_readiness"): bool(
            claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
        ),
        key("claim_requirement_reason"): _text(claim_gate_summary.get("claim_gate_requirement_reason")),
        key("claim_primary_action"): _text(claim_gate_summary.get("claim_gate_primary_action")),
        key("claim_action_rollup"): _text(claim_gate_summary.get("claim_gate_action_rollup")),
        key("claim_status_reason"): _text(claim_gate_summary.get("claim_gate_status_reason")),
        key("claim_requirement_actions"): _normalize_text_list(
            claim_gate_summary.get("claim_gate_requirement_actions")
        ),
    }


def build_commercial_grade_rollups(
    payload: dict[str, Any] | None,
    *,
    schema_suffix: str = "v1",
    prefix: str = "",
) -> dict[str, Any]:
    source = dict(payload or {})
    suffix = _text(schema_suffix).lower() or "v1"
    if not suffix.startswith("v"):
        suffix = f"v{suffix}"
    key_prefix = _text(prefix)

    hard_gate_pass = source.get(f"commercial_hard_gate_pass_{suffix}")
    risk_bucket = _text(source.get(f"commercial_risk_bucket_{suffix}"))
    decision_class = _text(source.get(f"commercial_decision_class_{suffix}"))
    overall_score = _optional_float(source.get(f"commercial_overall_score_{suffix}"))
    confidence_score = _optional_float(source.get(f"commercial_confidence_score_{suffix}"))
    soft_score = _optional_float(source.get(f"commercial_soft_score_{suffix}"))
    actions = _normalize_text_list(source.get(f"commercial_primary_upgrade_actions_{suffix}"))
    if not actions:
        actions = _normalize_text_list(source.get(f"commercial_upgrade_actions_{suffix}"))

    robustness_score = _optional_float(source.get(f"commercial_robustness_score_{suffix}"))
    robustness_inputs_available = bool(source.get(f"commercial_robustness_inputs_available_{suffix}", False))
    robustness_metric_count = _safe_int(source.get(f"commercial_robustness_metric_count_{suffix}"))

    if hard_gate_pass is True:
        gate_rollup = "hard gate pass"
    elif hard_gate_pass is False:
        gate_rollup = "hard gate blocked"
    else:
        gate_rollup = "hard gate pending"

    label_parts: list[str] = []
    if decision_class:
        label_parts.append(decision_class)
    if risk_bucket:
        label_parts.append(f"risk {risk_bucket}")
    if overall_score is not None:
        label_parts.append(f"overall {overall_score:.1f}")
    commercial_label = " | ".join(label_parts)

    score_parts: list[str] = []
    if soft_score is not None:
        score_parts.append(f"soft {soft_score:.1f}")
    if confidence_score is not None:
        score_parts.append(f"confidence {confidence_score:.1f}")
    if overall_score is not None:
        score_parts.append(f"overall {overall_score:.1f}")
    commercial_score_rollup = " | ".join(score_parts)

    if suffix == "v2":
        if robustness_inputs_available and robustness_score is not None:
            robustness_rollup = f"robustness {robustness_score:.1f} across {robustness_metric_count} optional signals"
        elif robustness_inputs_available:
            robustness_rollup = f"robustness inputs available ({robustness_metric_count} optional signals)"
        else:
            robustness_rollup = "robustness inputs unavailable"
    else:
        robustness_rollup = ""

    commercial_action_rollup = ", ".join(actions)

    summary_bits: list[str] = []
    if decision_class:
        summary_bits.append(decision_class)
    summary_bits.append(gate_rollup)
    if risk_bucket:
        summary_bits.append(f"risk {risk_bucket}")
    if overall_score is not None:
        summary_bits.append(f"overall {overall_score:.1f}")
    if confidence_score is not None:
        summary_bits.append(f"confidence {confidence_score:.1f}")
    if suffix == "v2" and robustness_rollup:
        summary_bits.append(robustness_rollup)
    commercial_human_summary = "; ".join(summary_bits)
    if commercial_action_rollup:
        commercial_human_summary = (
            f"{commercial_human_summary}; upgrades {commercial_action_rollup}"
            if commercial_human_summary
            else f"upgrades {commercial_action_rollup}"
        )
    if commercial_human_summary:
        commercial_human_summary += "."

    return {
        f"{key_prefix}commercial_label_{suffix}": commercial_label,
        f"{key_prefix}commercial_gate_rollup_{suffix}": gate_rollup,
        f"{key_prefix}commercial_score_rollup_{suffix}": commercial_score_rollup,
        f"{key_prefix}commercial_action_rollup_{suffix}": commercial_action_rollup,
        f"{key_prefix}commercial_robustness_rollup_{suffix}": robustness_rollup,
        f"{key_prefix}commercial_human_summary_{suffix}": commercial_human_summary,
    }


def _commercial_row_schema_v1(
    row: dict[str, Any],
    *,
    selected_threshold_A: float,
    strict_threshold_A: float,
    near_threshold_A: float,
    claim_gate_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    claim_gate_summary = dict(claim_gate_summary or {})
    claim_gate_available = bool(claim_gate_summary.get("claim_gate_available", False))
    claim_ready_for_allatom = claim_gate_summary.get("claim_ready_for_allatom")
    claim_required_for_commercial_readiness = bool(
        claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
    )
    distance_A = _optional_float(row.get("mean_min_distance_A"))
    energy_value = _optional_float(row.get("binding_energy_mmpbsa_kcal_mol_proxy"))
    if energy_value is None:
        energy_value = _optional_float(row.get("binding_energy_proxy"))
    stability_score = _optional_float(row.get("stability_score"))
    contact_fraction = _optional_float(row.get("contact_fraction"))
    std_value = _optional_float(row.get("binding_energy_mmpbsa_std"))
    trajectory_frames = _safe_int(row.get("trajectory_frames"), 0)
    trajectory_frames_opt = trajectory_frames if trajectory_frames > 0 else None

    hard_gate_failed_metrics: list[str] = []
    hard_gate_missing_metrics: list[str] = []

    if distance_A is None:
        hard_gate_missing_metrics.append("mean_min_distance_A")
    elif distance_A <= 0 or distance_A > selected_threshold_A:
        hard_gate_failed_metrics.append("mean_min_distance_A")

    if energy_value is None:
        hard_gate_missing_metrics.append("binding_energy_proxy")
    elif energy_value > -0.05:
        hard_gate_failed_metrics.append("binding_energy_proxy")

    if stability_score is None:
        hard_gate_missing_metrics.append("stability_score")
    elif stability_score < 0.35:
        hard_gate_failed_metrics.append("stability_score")

    if contact_fraction is None:
        hard_gate_missing_metrics.append("contact_fraction")
    elif contact_fraction < 0.50:
        hard_gate_failed_metrics.append("contact_fraction")

    if std_value is None:
        hard_gate_missing_metrics.append("binding_energy_mmpbsa_std")
    elif std_value > 0.18:
        hard_gate_failed_metrics.append("binding_energy_mmpbsa_std")

    if trajectory_frames_opt is None:
        hard_gate_missing_metrics.append("trajectory_frames")
    elif trajectory_frames_opt < 180:
        hard_gate_failed_metrics.append("trajectory_frames")

    if claim_gate_available and claim_ready_for_allatom is not True:
        if claim_ready_for_allatom in {"", None}:
            hard_gate_missing_metrics.append("claim_ready_for_allatom")
        else:
            hard_gate_failed_metrics.append("claim_ready_for_allatom")
    elif (not claim_gate_available) and claim_required_for_commercial_readiness:
        hard_gate_missing_metrics.append("claim_gate_required_unavailable")

    distance_score = _distance_component_score(
        distance_A,
        strict_threshold_A=strict_threshold_A,
        near_threshold_A=near_threshold_A,
    )
    energy_score = _energy_component_score(energy_value)
    stability_component = _stability_component_score(stability_score)
    contact_score = _contact_component_score(contact_fraction)
    uncertainty_score = _uncertainty_component_score(std_value)
    support_score = _support_component_score(trajectory_frames_opt)

    soft_score = _clamp_score(
        0.40 * distance_score
        + 0.20 * energy_score
        + 0.15 * stability_component
        + 0.15 * contact_score
        + 0.10 * uncertainty_score
    )
    confidence_score = _clamp_score(
        0.35 * support_score
        + 0.25 * uncertainty_score
        + 0.20 * contact_score
        + 0.20 * distance_score
    )
    overall_score = _clamp_score(0.75 * soft_score + 0.25 * confidence_score)
    hard_gate_pass = not hard_gate_failed_metrics and not hard_gate_missing_metrics
    decision_class = _commercial_decision_class(
        hard_gate_pass=hard_gate_pass,
        overall_score=overall_score,
        soft_score=soft_score,
        confidence_score=confidence_score,
        distance_A=distance_A,
        near_threshold_A=near_threshold_A,
        packet_ready_for_operator_review=True,
    )
    risk_bucket = _commercial_risk_bucket(
        hard_gate_pass=hard_gate_pass,
        overall_score=overall_score,
        confidence_score=confidence_score,
    )
    upgrade_actions = _commercial_upgrade_actions(
        distance_A=distance_A,
        selected_threshold_A=selected_threshold_A,
        energy_value=energy_value,
        stability_score=stability_score,
        contact_fraction=contact_fraction,
        std_value=std_value,
        trajectory_frames=trajectory_frames_opt,
        claim_gate_summary=claim_gate_summary,
    )
    row_schema = {
        "commercial_schema_version": "wetlab_commercial_grade_v1",
        "commercial_schema_version_v1": "wetlab_commercial_grade_v1",
        "commercial_distance_score_v1": round(distance_score, 1),
        "commercial_energy_score_v1": round(energy_score, 1),
        "commercial_stability_score_v1": round(stability_component, 1),
        "commercial_contact_score_v1": round(contact_score, 1),
        "commercial_uncertainty_score_v1": round(uncertainty_score, 1),
        "commercial_support_score_v1": round(support_score, 1),
        "commercial_soft_score_v1": round(soft_score, 1),
        "commercial_confidence_score_v1": round(confidence_score, 1),
        "commercial_overall_score_v1": round(overall_score, 1),
        "commercial_hard_gate_pass_v1": hard_gate_pass,
        "commercial_hard_gate_failed_metrics_v1": hard_gate_failed_metrics,
        "commercial_hard_gate_missing_metrics_v1": hard_gate_missing_metrics,
        "commercial_hard_gate_failed_metric_count_v1": len(hard_gate_failed_metrics),
        "commercial_hard_gate_missing_metric_count_v1": len(hard_gate_missing_metrics),
        "commercial_risk_bucket_v1": risk_bucket,
        "commercial_decision_class_v1": decision_class,
        "commercial_upgrade_actions_v1": upgrade_actions,
        "commercial_strict_margin_A_v1": round(selected_threshold_A - distance_A, 3) if distance_A is not None else None,
    }
    row_schema.update(_commercial_claim_semantics_fields(claim_gate_summary, schema_suffix="v1"))
    row_schema.update(build_commercial_grade_rollups(row_schema, schema_suffix="v1"))
    return row_schema


def compute_commercial_grade_schema_v1(
    *,
    promoted_rows: list[dict[str, Any]],
    selected_threshold_A: float,
    strict_threshold_A: float,
    near_threshold_A: float,
    wetlab_gate_summary: dict[str, Any],
    claim_gate_summary: dict[str, Any],
    final_gate_summary: dict[str, Any],
) -> dict[str, Any]:
    claim_gate_summary = dict(claim_gate_summary or {})
    claim_gate_available = bool(claim_gate_summary.get("claim_gate_available", False))
    claim_ready_for_allatom = claim_gate_summary.get("claim_ready_for_allatom")
    claim_required_for_commercial_readiness = bool(
        claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
    )
    claim_gate_satisfied = claim_gate_summary.get("claim_gate_satisfied")
    enriched_rows: list[dict[str, Any]] = []
    for row in promoted_rows:
        row_schema = _commercial_row_schema_v1(
            row,
            selected_threshold_A=selected_threshold_A,
            strict_threshold_A=strict_threshold_A,
            near_threshold_A=near_threshold_A,
            claim_gate_summary=claim_gate_summary,
        )
        enriched_rows.append({**dict(row or {}), **row_schema})

    best_row = enriched_rows[0] if enriched_rows else {}
    strict_candidate_count = _safe_int((wetlab_gate_summary or {}).get("strict_candidate_count"))
    near_candidate_count = _safe_int((wetlab_gate_summary or {}).get("near_candidate_count"))
    promoted_count = len(enriched_rows)

    if strict_candidate_count >= 2:
        consistency_score = 100.0
    elif strict_candidate_count == 1:
        consistency_score = 80.0
    elif near_candidate_count >= 2:
        consistency_score = 65.0
    elif near_candidate_count == 1:
        consistency_score = 50.0
    elif promoted_count > 0:
        consistency_score = 25.0
    else:
        consistency_score = 0.0

    if claim_gate_satisfied is True:
        claim_observability_score = 100.0
    elif claim_required_for_commercial_readiness and not claim_gate_available:
        claim_observability_score = 20.0
    elif claim_required_for_commercial_readiness:
        claim_observability_score = 35.0
    elif not claim_gate_available:
        claim_observability_score = 65.0
    else:
        claim_observability_score = 40.0

    final_gate_support_score = (
        100.0
        if bool((final_gate_summary or {}).get("wetlab_final_gate_pass", False))
        else 65.0
        if bool((wetlab_gate_summary or {}).get("wetlab_gate_pass", False))
        else 35.0
        if promoted_count > 0
        else 0.0
    )

    best_soft_score = _safe_float(best_row.get("commercial_soft_score_v1"))
    best_confidence_score = _safe_float(best_row.get("commercial_confidence_score_v1"))
    summary_confidence_score = _clamp_score(
        0.65 * best_confidence_score
        + 0.15 * consistency_score
        + 0.10 * claim_observability_score
        + 0.10 * final_gate_support_score
    )
    summary_overall_score = _clamp_score(0.75 * best_soft_score + 0.25 * summary_confidence_score)

    hard_gate_failed_metrics = list(best_row.get("commercial_hard_gate_failed_metrics_v1", []) or [])
    hard_gate_missing_metrics = list(best_row.get("commercial_hard_gate_missing_metrics_v1", []) or [])
    if not bool((final_gate_summary or {}).get("wetlab_final_gate_pass", False)):
        hard_gate_failed_metrics.extend(list((final_gate_summary or {}).get("wetlab_final_gate_failed_metrics", []) or []))
        hard_gate_missing_metrics.extend(list((final_gate_summary or {}).get("wetlab_final_gate_missing_metrics", []) or []))
    hard_gate_failed_metrics = list(dict.fromkeys(_text(metric) for metric in hard_gate_failed_metrics if _text(metric)))
    hard_gate_missing_metrics = list(dict.fromkeys(_text(metric) for metric in hard_gate_missing_metrics if _text(metric)))
    hard_gate_pass = not hard_gate_failed_metrics and not hard_gate_missing_metrics

    decision_class = _commercial_decision_class(
        hard_gate_pass=hard_gate_pass,
        overall_score=summary_overall_score,
        soft_score=best_soft_score,
        confidence_score=summary_confidence_score,
        distance_A=_optional_float(best_row.get("mean_min_distance_A")),
        near_threshold_A=near_threshold_A,
        packet_ready_for_operator_review=bool((wetlab_gate_summary or {}).get("packet_ready_for_operator_review", False)),
    )
    risk_bucket = _commercial_risk_bucket(
        hard_gate_pass=hard_gate_pass,
        overall_score=summary_overall_score,
        confidence_score=summary_confidence_score,
    )
    summary_payload = {
        "commercial_schema_version": "wetlab_commercial_grade_v1",
        "commercial_schema_version_v1": "wetlab_commercial_grade_v1",
        "commercial_primary_row_packet_rank_v1": _safe_int(best_row.get("packet_rank")),
        "commercial_hard_gate_pass_v1": hard_gate_pass,
        "commercial_hard_gate_failed_metrics_v1": hard_gate_failed_metrics,
        "commercial_hard_gate_missing_metrics_v1": hard_gate_missing_metrics,
        "commercial_hard_gate_failed_metric_count_v1": len(hard_gate_failed_metrics),
        "commercial_hard_gate_missing_metric_count_v1": len(hard_gate_missing_metrics),
        "commercial_soft_score_v1": round(best_soft_score, 1),
        "commercial_confidence_score_v1": round(summary_confidence_score, 1),
        "commercial_overall_score_v1": round(summary_overall_score, 1),
        "commercial_distance_score_v1": round(_safe_float(best_row.get("commercial_distance_score_v1")), 1),
        "commercial_energy_score_v1": round(_safe_float(best_row.get("commercial_energy_score_v1")), 1),
        "commercial_stability_score_v1": round(_safe_float(best_row.get("commercial_stability_score_v1")), 1),
        "commercial_contact_score_v1": round(_safe_float(best_row.get("commercial_contact_score_v1")), 1),
        "commercial_uncertainty_score_v1": round(_safe_float(best_row.get("commercial_uncertainty_score_v1")), 1),
        "commercial_support_score_v1": round(_safe_float(best_row.get("commercial_support_score_v1")), 1),
        "commercial_consistency_score_v1": round(consistency_score, 1),
        "commercial_claim_observability_score_v1": round(claim_observability_score, 1),
        "commercial_final_gate_support_score_v1": round(final_gate_support_score, 1),
        "commercial_risk_bucket_v1": risk_bucket,
        "commercial_decision_class_v1": decision_class,
        "commercial_primary_upgrade_actions_v1": list(best_row.get("commercial_upgrade_actions_v1", []) or []),
        "commercial_score_thresholds_v1": {
            "selected_threshold_A": selected_threshold_A,
            "strict_threshold_A": strict_threshold_A,
            "near_threshold_A": near_threshold_A,
            "binding_energy_proxy_max_kcal_mol": -0.05,
            "stability_score_min": 0.35,
            "contact_fraction_min": 0.50,
            "binding_energy_mmpbsa_std_max": 0.18,
            "trajectory_frames_min": 180,
        },
    }
    summary_payload.update(_commercial_claim_semantics_fields(claim_gate_summary, schema_suffix="v1"))
    summary_payload.update(build_commercial_grade_rollups(summary_payload, schema_suffix="v1"))

    return {
        "rows": enriched_rows,
        "summary": summary_payload,
    }


def _commercial_row_schema_v2(
    row: dict[str, Any],
    *,
    selected_threshold_A: float,
    strict_threshold_A: float,
    near_threshold_A: float,
    claim_gate_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    claim_gate_summary = dict(claim_gate_summary or {})
    base_row = dict(row or {})
    if _optional_float(base_row.get("commercial_soft_score_v1")) is None:
        base_row = {
            **base_row,
            **_commercial_row_schema_v1(
                base_row,
                selected_threshold_A=selected_threshold_A,
                strict_threshold_A=strict_threshold_A,
                near_threshold_A=near_threshold_A,
                claim_gate_summary=claim_gate_summary,
            ),
        }

    distance_A = _optional_float(base_row.get("mean_min_distance_A"))
    energy_score_v1 = _optional_float(base_row.get("commercial_energy_score_v1"))
    if energy_score_v1 is None:
        energy_value = _optional_float(base_row.get("binding_energy_mmpbsa_kcal_mol_proxy"))
        if energy_value is None:
            energy_value = _optional_float(base_row.get("binding_energy_proxy"))
        energy_score_v1 = _energy_component_score(energy_value)
    stability_score_v1 = _optional_float(base_row.get("commercial_stability_score_v1"))
    if stability_score_v1 is None:
        stability_score_v1 = _stability_component_score(_optional_float(base_row.get("stability_score")))
    uncertainty_score_v1 = _optional_float(base_row.get("commercial_uncertainty_score_v1"))
    if uncertainty_score_v1 is None:
        uncertainty_score_v1 = _uncertainty_component_score(_optional_float(base_row.get("binding_energy_mmpbsa_std")))
    base_distance_score_v1 = _optional_float(base_row.get("commercial_distance_score_v1"))
    if base_distance_score_v1 is None:
        base_distance_score_v1 = _distance_component_score(
            distance_A,
            strict_threshold_A=strict_threshold_A,
            near_threshold_A=near_threshold_A,
        )
    base_contact_score_v1 = _optional_float(base_row.get("commercial_contact_score_v1"))
    if base_contact_score_v1 is None:
        base_contact_score_v1 = _contact_component_score(_optional_float(base_row.get("contact_fraction")))
    base_support_score_v1 = _optional_float(base_row.get("commercial_support_score_v1"))
    if base_support_score_v1 is None:
        base_support_score_v1 = _support_component_score(_optional_int(base_row.get("trajectory_frames")))
    base_soft_score_v1 = _optional_float(base_row.get("commercial_soft_score_v1"))
    if base_soft_score_v1 is None:
        base_soft_score_v1 = _clamp_score(
            0.40 * base_distance_score_v1
            + 0.20 * energy_score_v1
            + 0.15 * stability_score_v1
            + 0.15 * base_contact_score_v1
            + 0.10 * uncertainty_score_v1
        )
    base_confidence_score_v1 = _optional_float(base_row.get("commercial_confidence_score_v1"))
    if base_confidence_score_v1 is None:
        base_confidence_score_v1 = _clamp_score(
            0.35 * base_support_score_v1
            + 0.25 * uncertainty_score_v1
            + 0.20 * base_contact_score_v1
            + 0.20 * base_distance_score_v1
        )
    base_overall_score_v1 = _optional_float(base_row.get("commercial_overall_score_v1"))
    if base_overall_score_v1 is None:
        base_overall_score_v1 = _clamp_score(0.75 * base_soft_score_v1 + 0.25 * base_confidence_score_v1)

    replicate_count = _resolve_optional_metric_int(base_row, "replicate_count")
    replicate_pass_fraction = _resolve_optional_metric_float(base_row, "replicate_pass_fraction")
    median_distance_A = _resolve_optional_metric_float(base_row, "median_mean_min_distance_A")
    distance_iqr_A = _resolve_optional_metric_float(base_row, "mean_min_distance_iqr_A")
    median_contact_fraction = _resolve_optional_metric_float(base_row, "median_contact_fraction")
    pose_cluster_dominance = _resolve_optional_metric_float(base_row, "pose_cluster_dominance")
    pose_preservation_rmsd_A = _resolve_optional_metric_float(base_row, "pose_preservation_rmsd_A")
    backmapping_consistency_score = _resolve_optional_metric_float(base_row, "backmapping_consistency_score")
    local_minimization_survival_fraction = _resolve_optional_metric_float(
        base_row,
        "local_minimization_survival_fraction",
    )

    robustness_metrics_used: list[str] = []

    def _mark(metric_name: str, value: Any) -> None:
        if value is not None and metric_name not in robustness_metrics_used:
            robustness_metrics_used.append(metric_name)

    _mark("replicate_count", replicate_count)
    _mark("replicate_pass_fraction", replicate_pass_fraction)
    _mark("median_mean_min_distance_A", median_distance_A)
    _mark("mean_min_distance_iqr_A", distance_iqr_A)
    _mark("median_contact_fraction", median_contact_fraction)
    _mark("pose_cluster_dominance", pose_cluster_dominance)
    _mark("pose_preservation_rmsd_A", pose_preservation_rmsd_A)
    _mark("backmapping_consistency_score", backmapping_consistency_score)
    _mark("local_minimization_survival_fraction", local_minimization_survival_fraction)
    robustness_inputs_available = bool(robustness_metrics_used)

    replicate_support_score = _replicate_support_component_score(replicate_count)
    replicate_pass_score = _fraction_component_score(replicate_pass_fraction)
    median_distance_score = (
        _distance_component_score(
            median_distance_A,
            strict_threshold_A=strict_threshold_A,
            near_threshold_A=near_threshold_A,
        )
        if median_distance_A is not None
        else None
    )
    distance_iqr_score = _iqr_component_score(distance_iqr_A)
    distance_robustness_score = _weighted_optional_score(
        (median_distance_score, 0.70),
        (distance_iqr_score, 0.30),
    )
    contact_robustness_score = _contact_component_score(median_contact_fraction) if median_contact_fraction is not None else None
    pose_consistency_score = _weighted_optional_score(
        (_fraction_component_score(pose_cluster_dominance), 0.30),
        (_rmsd_component_score(pose_preservation_rmsd_A), 0.25),
        (_fraction_component_score(backmapping_consistency_score), 0.25),
        (_fraction_component_score(local_minimization_survival_fraction), 0.20),
    )
    robustness_score = _weighted_optional_score(
        (replicate_support_score, 0.20),
        (replicate_pass_score, 0.20),
        (distance_robustness_score, 0.25),
        (contact_robustness_score, 0.10),
        (pose_consistency_score, 0.25),
    )
    robustness_confidence_score = _weighted_optional_score(
        (replicate_support_score, 0.30),
        (replicate_pass_score, 0.25),
        (distance_iqr_score, 0.15),
        (contact_robustness_score, 0.10),
        (pose_consistency_score, 0.20),
    )

    if robustness_inputs_available:
        distance_score_v2 = _weighted_optional_score(
            (base_distance_score_v1, 0.70),
            (distance_robustness_score, 0.30),
        )
        contact_score_v2 = _weighted_optional_score(
            (base_contact_score_v1, 0.75),
            (contact_robustness_score, 0.25),
        )
        support_score_v2 = _weighted_optional_score(
            (base_support_score_v1, 0.60),
            (replicate_support_score, 0.40),
        )
        distance_score_v2 = distance_score_v2 if distance_score_v2 is not None else base_distance_score_v1
        contact_score_v2 = contact_score_v2 if contact_score_v2 is not None else base_contact_score_v1
        support_score_v2 = support_score_v2 if support_score_v2 is not None else base_support_score_v1
        base_soft_score_v2 = _clamp_score(
            0.40 * distance_score_v2
            + 0.20 * energy_score_v1
            + 0.15 * stability_score_v1
            + 0.15 * contact_score_v2
            + 0.10 * uncertainty_score_v1
        )
        soft_score_v2 = _clamp_score(
            0.85 * base_soft_score_v2 + 0.15 * (robustness_score if robustness_score is not None else base_soft_score_v2)
        )
        base_confidence_score_v2 = _clamp_score(
            0.35 * support_score_v2
            + 0.25 * uncertainty_score_v1
            + 0.20 * contact_score_v2
            + 0.20 * distance_score_v2
        )
        confidence_score_v2 = _clamp_score(
            0.60 * base_confidence_score_v2
            + 0.40 * (robustness_confidence_score if robustness_confidence_score is not None else base_confidence_score_v2)
        )
        overall_score_v2 = _clamp_score(0.72 * soft_score_v2 + 0.28 * confidence_score_v2)
    else:
        distance_score_v2 = base_distance_score_v1
        contact_score_v2 = base_contact_score_v1
        support_score_v2 = base_support_score_v1
        soft_score_v2 = base_soft_score_v1
        confidence_score_v2 = base_confidence_score_v1
        overall_score_v2 = base_overall_score_v1

    hard_gate_failed_metrics = _normalize_text_list(base_row.get("commercial_hard_gate_failed_metrics_v1"))
    hard_gate_missing_metrics = _normalize_text_list(base_row.get("commercial_hard_gate_missing_metrics_v1"))
    claim_gate_available = bool(claim_gate_summary.get("claim_gate_available", False))
    claim_ready_for_allatom = claim_gate_summary.get("claim_ready_for_allatom")
    claim_required_for_commercial_readiness = bool(
        claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
    )

    if replicate_count is not None and replicate_count < 3:
        hard_gate_failed_metrics.append("replicate_count")
    if replicate_pass_fraction is not None and replicate_pass_fraction < 0.60:
        hard_gate_failed_metrics.append("replicate_pass_fraction")
    if median_distance_A is not None and (median_distance_A <= 0 or median_distance_A > selected_threshold_A):
        hard_gate_failed_metrics.append("median_mean_min_distance_A")
    if distance_iqr_A is not None and distance_iqr_A > 0.50:
        hard_gate_failed_metrics.append("mean_min_distance_iqr_A")
    if median_contact_fraction is not None and median_contact_fraction < 0.50:
        hard_gate_failed_metrics.append("median_contact_fraction")
    if pose_cluster_dominance is not None and pose_cluster_dominance < 0.50:
        hard_gate_failed_metrics.append("pose_cluster_dominance")
    if pose_preservation_rmsd_A is not None and pose_preservation_rmsd_A > 2.50:
        hard_gate_failed_metrics.append("pose_preservation_rmsd_A")
    if backmapping_consistency_score is not None and backmapping_consistency_score < 0.60:
        hard_gate_failed_metrics.append("backmapping_consistency_score")
    if (
        local_minimization_survival_fraction is not None
        and local_minimization_survival_fraction < 0.60
    ):
        hard_gate_failed_metrics.append("local_minimization_survival_fraction")
    if (not claim_gate_available) and claim_required_for_commercial_readiness:
        hard_gate_missing_metrics.append("claim_gate_required_unavailable")
    elif claim_gate_available and claim_ready_for_allatom is not True:
        if claim_ready_for_allatom in {"", None}:
            hard_gate_missing_metrics.append("claim_ready_for_allatom")
        else:
            hard_gate_failed_metrics.append("claim_ready_for_allatom")

    hard_gate_failed_metrics = list(dict.fromkeys(_normalize_text_list(hard_gate_failed_metrics)))
    hard_gate_missing_metrics = list(dict.fromkeys(_normalize_text_list(hard_gate_missing_metrics)))
    hard_gate_pass = not hard_gate_failed_metrics and not hard_gate_missing_metrics

    upgrade_actions = _normalize_text_list(base_row.get("commercial_upgrade_actions_v1"))
    if replicate_count is not None and replicate_count < 3:
        upgrade_actions.append("increase_replicate_coverage")
    if replicate_pass_fraction is not None and replicate_pass_fraction < 0.60:
        upgrade_actions.append("raise_replicate_pass_fraction")
    if median_distance_A is not None and median_distance_A > selected_threshold_A:
        upgrade_actions.append("tighten_replicate_median_geometry")
    if distance_iqr_A is not None and distance_iqr_A > 0.50:
        upgrade_actions.append("reduce_replicate_distance_dispersion")
    if median_contact_fraction is not None and median_contact_fraction < 0.50:
        upgrade_actions.append("raise_replicate_contact_occupancy")
    if pose_cluster_dominance is not None and pose_cluster_dominance < 0.50:
        upgrade_actions.append("stabilize_dominant_pose_cluster")
    if pose_preservation_rmsd_A is not None and pose_preservation_rmsd_A > 2.50:
        upgrade_actions.append("improve_pose_preservation_rmsd")
    if backmapping_consistency_score is not None and backmapping_consistency_score < 0.60:
        upgrade_actions.append("stabilize_backmapping_consistency")
    if (
        local_minimization_survival_fraction is not None
        and local_minimization_survival_fraction < 0.60
    ):
        upgrade_actions.append("improve_local_minimization_survival")
    upgrade_actions = list(dict.fromkeys(_normalize_text_list(upgrade_actions)))

    decision_class_v2 = _commercial_decision_class(
        hard_gate_pass=hard_gate_pass,
        overall_score=overall_score_v2,
        soft_score=soft_score_v2,
        confidence_score=confidence_score_v2,
        distance_A=median_distance_A if median_distance_A is not None else distance_A,
        near_threshold_A=near_threshold_A,
        packet_ready_for_operator_review=True,
    )
    risk_bucket_v2 = _commercial_risk_bucket(
        hard_gate_pass=hard_gate_pass,
        overall_score=overall_score_v2,
        confidence_score=confidence_score_v2,
    )

    row_schema = {
        "commercial_schema_version_v2": "wetlab_commercial_grade_v2",
        "commercial_replicate_count_v2": replicate_count,
        "commercial_replicate_pass_fraction_v2": round(replicate_pass_fraction, 3) if replicate_pass_fraction is not None else None,
        "commercial_median_mean_min_distance_A_v2": round(median_distance_A, 3) if median_distance_A is not None else None,
        "commercial_mean_min_distance_iqr_A_v2": round(distance_iqr_A, 3) if distance_iqr_A is not None else None,
        "commercial_median_contact_fraction_v2": round(median_contact_fraction, 3) if median_contact_fraction is not None else None,
        "commercial_pose_cluster_dominance_v2": round(pose_cluster_dominance, 3) if pose_cluster_dominance is not None else None,
        "commercial_pose_preservation_rmsd_A_v2": round(pose_preservation_rmsd_A, 3) if pose_preservation_rmsd_A is not None else None,
        "commercial_backmapping_consistency_score_v2": round(backmapping_consistency_score, 3) if backmapping_consistency_score is not None else None,
        "commercial_local_minimization_survival_fraction_v2": (
            round(local_minimization_survival_fraction, 3)
            if local_minimization_survival_fraction is not None
            else None
        ),
        "commercial_robustness_inputs_available_v2": robustness_inputs_available,
        "commercial_robustness_metric_count_v2": len(robustness_metrics_used),
        "commercial_robustness_metrics_used_v2": robustness_metrics_used,
        "commercial_replicate_support_score_v2": round(replicate_support_score, 1) if replicate_support_score is not None else None,
        "commercial_replicate_pass_score_v2": round(replicate_pass_score, 1) if replicate_pass_score is not None else None,
        "commercial_distance_robustness_score_v2": round(distance_robustness_score, 1) if distance_robustness_score is not None else None,
        "commercial_contact_robustness_score_v2": round(contact_robustness_score, 1) if contact_robustness_score is not None else None,
        "commercial_pose_consistency_score_v2": round(pose_consistency_score, 1) if pose_consistency_score is not None else None,
        "commercial_robustness_score_v2": round(robustness_score, 1) if robustness_score is not None else None,
        "commercial_distance_score_v2": round(distance_score_v2, 1),
        "commercial_energy_score_v2": round(energy_score_v1, 1),
        "commercial_stability_score_v2": round(stability_score_v1, 1),
        "commercial_contact_score_v2": round(contact_score_v2, 1),
        "commercial_uncertainty_score_v2": round(uncertainty_score_v1, 1),
        "commercial_support_score_v2": round(support_score_v2, 1),
        "commercial_soft_score_v2": round(soft_score_v2, 1),
        "commercial_confidence_score_v2": round(confidence_score_v2, 1),
        "commercial_overall_score_v2": round(overall_score_v2, 1),
        "commercial_hard_gate_pass_v2": hard_gate_pass,
        "commercial_hard_gate_failed_metrics_v2": hard_gate_failed_metrics,
        "commercial_hard_gate_missing_metrics_v2": hard_gate_missing_metrics,
        "commercial_hard_gate_failed_metric_count_v2": len(hard_gate_failed_metrics),
        "commercial_hard_gate_missing_metric_count_v2": len(hard_gate_missing_metrics),
        "commercial_risk_bucket_v2": risk_bucket_v2,
        "commercial_decision_class_v2": decision_class_v2,
        "commercial_upgrade_actions_v2": upgrade_actions,
        "commercial_strict_margin_A_v2": (
            round(selected_threshold_A - (median_distance_A if median_distance_A is not None else distance_A), 3)
            if (median_distance_A if median_distance_A is not None else distance_A) is not None
            else None
        ),
    }
    row_schema.update(_commercial_claim_semantics_fields(claim_gate_summary, schema_suffix="v2"))
    row_schema.update(build_commercial_grade_rollups(row_schema, schema_suffix="v2"))
    return row_schema


def compute_commercial_grade_schema_v2(
    *,
    promoted_rows: list[dict[str, Any]],
    selected_threshold_A: float,
    strict_threshold_A: float,
    near_threshold_A: float,
    wetlab_gate_summary: dict[str, Any],
    claim_gate_summary: dict[str, Any],
    final_gate_summary: dict[str, Any],
) -> dict[str, Any]:
    claim_gate_summary = dict(claim_gate_summary or {})
    claim_gate_available = bool(claim_gate_summary.get("claim_gate_available", False))
    claim_ready_for_allatom = claim_gate_summary.get("claim_ready_for_allatom")
    claim_required_for_commercial_readiness = bool(
        claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
    )
    claim_gate_satisfied = claim_gate_summary.get("claim_gate_satisfied")
    enriched_rows: list[dict[str, Any]] = []
    for row in promoted_rows:
        base_row = dict(row or {})
        if _optional_float(base_row.get("commercial_soft_score_v1")) is None:
            base_row = {
                **base_row,
                **_commercial_row_schema_v1(
                    base_row,
                    selected_threshold_A=selected_threshold_A,
                    strict_threshold_A=strict_threshold_A,
                    near_threshold_A=near_threshold_A,
                    claim_gate_summary=claim_gate_summary,
                ),
            }
        row_schema = _commercial_row_schema_v2(
            base_row,
            selected_threshold_A=selected_threshold_A,
            strict_threshold_A=strict_threshold_A,
            near_threshold_A=near_threshold_A,
            claim_gate_summary=claim_gate_summary,
        )
        enriched_rows.append({**base_row, **row_schema})

    best_row = enriched_rows[0] if enriched_rows else {}
    strict_candidate_count = _safe_int((wetlab_gate_summary or {}).get("strict_candidate_count"))
    near_candidate_count = _safe_int((wetlab_gate_summary or {}).get("near_candidate_count"))
    promoted_count = len(enriched_rows)

    if strict_candidate_count >= 2:
        consistency_score = 100.0
    elif strict_candidate_count == 1:
        consistency_score = 80.0
    elif near_candidate_count >= 2:
        consistency_score = 65.0
    elif near_candidate_count == 1:
        consistency_score = 50.0
    elif promoted_count > 0:
        consistency_score = 25.0
    else:
        consistency_score = 0.0

    if claim_gate_satisfied is True:
        claim_observability_score = 100.0
    elif claim_required_for_commercial_readiness and not claim_gate_available:
        claim_observability_score = 20.0
    elif claim_required_for_commercial_readiness:
        claim_observability_score = 35.0
    elif not claim_gate_available:
        claim_observability_score = 65.0
    else:
        claim_observability_score = 40.0

    final_gate_support_score = (
        100.0
        if bool((final_gate_summary or {}).get("wetlab_final_gate_pass", False))
        else 65.0
        if bool((wetlab_gate_summary or {}).get("wetlab_gate_pass", False))
        else 35.0
        if promoted_count > 0
        else 0.0
    )

    best_soft_score = _safe_float(best_row.get("commercial_soft_score_v2"))
    best_confidence_score = _safe_float(best_row.get("commercial_confidence_score_v2"))
    best_robustness_inputs_available = bool(best_row.get("commercial_robustness_inputs_available_v2", False))
    summary_confidence_score = _clamp_score(
        0.65 * best_confidence_score
        + 0.15 * consistency_score
        + 0.10 * claim_observability_score
        + 0.10 * final_gate_support_score
    )
    summary_overall_score = _clamp_score(
        (0.72 if best_robustness_inputs_available else 0.75) * best_soft_score
        + (0.28 if best_robustness_inputs_available else 0.25) * summary_confidence_score
    )

    hard_gate_failed_metrics = _normalize_text_list(best_row.get("commercial_hard_gate_failed_metrics_v2"))
    hard_gate_missing_metrics = _normalize_text_list(best_row.get("commercial_hard_gate_missing_metrics_v2"))
    if not bool((final_gate_summary or {}).get("wetlab_final_gate_pass", False)):
        hard_gate_failed_metrics.extend(list((final_gate_summary or {}).get("wetlab_final_gate_failed_metrics", []) or []))
        hard_gate_missing_metrics.extend(list((final_gate_summary or {}).get("wetlab_final_gate_missing_metrics", []) or []))
    hard_gate_failed_metrics = list(dict.fromkeys(_normalize_text_list(hard_gate_failed_metrics)))
    hard_gate_missing_metrics = list(dict.fromkeys(_normalize_text_list(hard_gate_missing_metrics)))
    hard_gate_pass = not hard_gate_failed_metrics and not hard_gate_missing_metrics

    decision_class = _commercial_decision_class(
        hard_gate_pass=hard_gate_pass,
        overall_score=summary_overall_score,
        soft_score=best_soft_score,
        confidence_score=summary_confidence_score,
        distance_A=(
            _optional_float(best_row.get("commercial_median_mean_min_distance_A_v2"))
            or _optional_float(best_row.get("mean_min_distance_A"))
        ),
        near_threshold_A=near_threshold_A,
        packet_ready_for_operator_review=bool((wetlab_gate_summary or {}).get("packet_ready_for_operator_review", False)),
    )
    risk_bucket = _commercial_risk_bucket(
        hard_gate_pass=hard_gate_pass,
        overall_score=summary_overall_score,
        confidence_score=summary_confidence_score,
    )

    summary_payload = {
        "commercial_schema_version_v2": "wetlab_commercial_grade_v2",
        "commercial_primary_row_packet_rank_v2": _safe_int(best_row.get("packet_rank")),
        "commercial_hard_gate_pass_v2": hard_gate_pass,
        "commercial_hard_gate_failed_metrics_v2": hard_gate_failed_metrics,
        "commercial_hard_gate_missing_metrics_v2": hard_gate_missing_metrics,
        "commercial_hard_gate_failed_metric_count_v2": len(hard_gate_failed_metrics),
        "commercial_hard_gate_missing_metric_count_v2": len(hard_gate_missing_metrics),
        "commercial_soft_score_v2": round(best_soft_score, 1),
        "commercial_confidence_score_v2": round(summary_confidence_score, 1),
        "commercial_overall_score_v2": round(summary_overall_score, 1),
        "commercial_distance_score_v2": round(_safe_float(best_row.get("commercial_distance_score_v2")), 1),
        "commercial_energy_score_v2": round(_safe_float(best_row.get("commercial_energy_score_v2")), 1),
        "commercial_stability_score_v2": round(_safe_float(best_row.get("commercial_stability_score_v2")), 1),
        "commercial_contact_score_v2": round(_safe_float(best_row.get("commercial_contact_score_v2")), 1),
        "commercial_uncertainty_score_v2": round(_safe_float(best_row.get("commercial_uncertainty_score_v2")), 1),
        "commercial_support_score_v2": round(_safe_float(best_row.get("commercial_support_score_v2")), 1),
        "commercial_consistency_score_v2": round(consistency_score, 1),
        "commercial_claim_observability_score_v2": round(claim_observability_score, 1),
        "commercial_final_gate_support_score_v2": round(final_gate_support_score, 1),
        "commercial_robustness_inputs_available_v2": bool(best_row.get("commercial_robustness_inputs_available_v2", False)),
        "commercial_robustness_metric_count_v2": _safe_int(best_row.get("commercial_robustness_metric_count_v2")),
        "commercial_robustness_metrics_used_v2": _normalize_text_list(best_row.get("commercial_robustness_metrics_used_v2")),
        "commercial_replicate_count_v2": _optional_int(best_row.get("commercial_replicate_count_v2")),
        "commercial_replicate_pass_fraction_v2": _optional_float(best_row.get("commercial_replicate_pass_fraction_v2")),
        "commercial_median_mean_min_distance_A_v2": _optional_float(best_row.get("commercial_median_mean_min_distance_A_v2")),
        "commercial_mean_min_distance_iqr_A_v2": _optional_float(best_row.get("commercial_mean_min_distance_iqr_A_v2")),
        "commercial_median_contact_fraction_v2": _optional_float(best_row.get("commercial_median_contact_fraction_v2")),
        "commercial_pose_cluster_dominance_v2": _optional_float(best_row.get("commercial_pose_cluster_dominance_v2")),
        "commercial_pose_preservation_rmsd_A_v2": _optional_float(best_row.get("commercial_pose_preservation_rmsd_A_v2")),
        "commercial_backmapping_consistency_score_v2": _optional_float(best_row.get("commercial_backmapping_consistency_score_v2")),
        "commercial_local_minimization_survival_fraction_v2": _optional_float(
            best_row.get("commercial_local_minimization_survival_fraction_v2")
        ),
        "commercial_replicate_support_score_v2": _optional_float(best_row.get("commercial_replicate_support_score_v2")),
        "commercial_replicate_pass_score_v2": _optional_float(best_row.get("commercial_replicate_pass_score_v2")),
        "commercial_distance_robustness_score_v2": _optional_float(best_row.get("commercial_distance_robustness_score_v2")),
        "commercial_contact_robustness_score_v2": _optional_float(best_row.get("commercial_contact_robustness_score_v2")),
        "commercial_pose_consistency_score_v2": _optional_float(best_row.get("commercial_pose_consistency_score_v2")),
        "commercial_robustness_score_v2": _optional_float(best_row.get("commercial_robustness_score_v2")),
        "commercial_risk_bucket_v2": risk_bucket,
        "commercial_decision_class_v2": decision_class,
        "commercial_primary_upgrade_actions_v2": _normalize_text_list(best_row.get("commercial_upgrade_actions_v2")),
        "commercial_score_thresholds_v2": {
            "selected_threshold_A": selected_threshold_A,
            "strict_threshold_A": strict_threshold_A,
            "near_threshold_A": near_threshold_A,
            "binding_energy_proxy_max_kcal_mol": -0.05,
            "stability_score_min": 0.35,
            "contact_fraction_min": 0.50,
            "binding_energy_mmpbsa_std_max": 0.18,
            "trajectory_frames_min": 180,
            "replicate_count_min": 3,
            "replicate_pass_fraction_min": 0.60,
            "mean_min_distance_iqr_A_max": 0.50,
            "median_contact_fraction_min": 0.50,
            "pose_cluster_dominance_min": 0.50,
            "pose_preservation_rmsd_A_max": 2.50,
            "backmapping_consistency_score_min": 0.60,
            "local_minimization_survival_fraction_min": 0.60,
        },
    }
    summary_payload.update(_commercial_claim_semantics_fields(claim_gate_summary, schema_suffix="v2"))
    summary_payload.update(build_commercial_grade_rollups(summary_payload, schema_suffix="v2"))

    return {
        "rows": enriched_rows,
        "summary": summary_payload,
    }


def _under_root(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _base_prefix_for_command_kind(command_kind: str) -> str:
    kind = _text(command_kind)
    if kind == "throughput_preflight_tuned_gate45":
        return "throughput_run_gate45"
    if kind == "throughput_preflight_tuned_gate51":
        return "throughput_run_gate51"
    if kind == "throughput_preflight_tuned_gate55":
        return "throughput_run_gate55"
    if kind.startswith("throughput_preflight_"):
        suffix = kind.removeprefix("throughput_preflight_").strip()
        if suffix:
            return f"throughput_run_{suffix}"
    return "throughput_run"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if (not str(path).strip()) or (not path.exists()) or path.is_dir():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists() or path.is_dir():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_target_native_reference(
    *,
    target_id: str,
    candidate_csv_paths: list[str],
) -> dict[str, Any]:
    for csv_path in [path for path in candidate_csv_paths if _text(path)]:
        resolved_csv = _under_root(csv_path)
        rows = _read_csv_rows(resolved_csv)
        if not rows:
            continue
        selected_row = find_matching_target_row(rows, target_id)
        native_path = _text(selected_row.get("native_pdb_path"))
        if not native_path:
            continue
        resolved_native = _under_root(native_path)
        if not resolved_native.exists() or resolved_native.is_dir():
            continue
        return {
            "native_pdb_path": str(resolved_native),
            "pdb_id": _text(selected_row.get("pdb_id")),
            "notes": _text(selected_row.get("notes")),
            "source_csv": str(resolved_csv),
            "pocket_x": _text(selected_row.get("pocket_x")),
            "pocket_y": _text(selected_row.get("pocket_y")),
            "pocket_z": _text(selected_row.get("pocket_z")),
            "provenance": "target_native_csv",
        }
    registry_entry = resolve_repo_native_entry(target_id)
    if registry_entry:
        native_path = _text(registry_entry.get("native_pdb_path"))
        resolved_native = _under_root(native_path)
        if resolved_native.exists() and not resolved_native.is_dir():
            return {
                "native_pdb_path": str(resolved_native),
                "pdb_id": _text(registry_entry.get("pdb_id")),
                "notes": _text(registry_entry.get("notes")),
                "source_csv": _text(registry_entry.get("source_csv")),
                "pocket_x": _text(registry_entry.get("pocket_x")),
                "pocket_y": _text(registry_entry.get("pocket_y")),
                "pocket_z": _text(registry_entry.get("pocket_z")),
                "provenance": "repo_native_registry",
            }
    return {}


def _inject_target_native_reference(
    queue_rows: list[dict[str, Any]],
    *,
    target_id: str,
    native_reference: dict[str, Any],
) -> list[dict[str, Any]]:
    if not queue_rows or not native_reference:
        return [dict(row or {}) for row in queue_rows]
    native_path = _text(native_reference.get("native_pdb_path"))
    pdb_id = _text(native_reference.get("pdb_id"))
    notes = _text(native_reference.get("notes"))
    pocket_x = _text(native_reference.get("pocket_x"))
    pocket_y = _text(native_reference.get("pocket_y"))
    pocket_z = _text(native_reference.get("pocket_z"))
    provenance = _text(native_reference.get("provenance"))
    enriched_rows: list[dict[str, Any]] = []
    for row in queue_rows:
        enriched = dict(row or {})
        if not _text(enriched.get("native_pdb_path")) and native_path:
            enriched["native_pdb_path"] = native_path
        if not _text(enriched.get("pdb_id")) and pdb_id:
            enriched["pdb_id"] = pdb_id
        if not _text(enriched.get("notes")) and notes:
            enriched["notes"] = notes
        if not _text(enriched.get("target")):
            enriched["target"] = target_id
        if not _text(enriched.get("pocket_x")) and pocket_x:
            enriched["pocket_x"] = pocket_x
        if not _text(enriched.get("pocket_y")) and pocket_y:
            enriched["pocket_y"] = pocket_y
        if not _text(enriched.get("pocket_z")) and pocket_z:
            enriched["pocket_z"] = pocket_z
        enriched["native_reference_provenance"] = provenance
        enriched_rows.append(enriched)
    return enriched_rows


def _latest_result_ready_row(execution_queue_payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for row in execution_queue_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) != _text(target_id):
            continue
        if _text(candidate.get("queue_status")) != "result_ready":
            continue
        selected = candidate
    return selected


def _resolve_source_summary_json(
    *,
    target_slug: str,
    shard_id: str,
    source_command_kind: str,
) -> Path:
    shard_dir = ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_id
    prefix = _base_prefix_for_command_kind(source_command_kind)
    candidates = [
        shard_dir / f"{prefix}_summary.json",
        shard_dir / "throughput_run_gate45_summary.json",
        shard_dir / "throughput_run_gate51_summary.json",
        shard_dir / "throughput_run_gate55_summary.json",
        shard_dir / "throughput_run_summary.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return shard_dir / f"{prefix}_summary.json"


def _resolve_artifact_path(summary_payload: dict[str, Any], summary_json: Path, artifact_key: str, fallback_name: str) -> Path:
    artifacts = dict(summary_payload.get("artifacts", {}) or {})
    text = _text(artifacts.get(artifact_key))
    if text:
        return _under_root(text)
    return summary_json.parent / fallback_name


def build_target_allatom_refinement_lane_payload(
    *,
    target_id: str,
    execution_queue_payload: dict[str, Any],
    branch_summary_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any],
    top_n: int,
    lane_label: str,
    selected_command_kind: str,
    selected_threshold_A: float,
    review_unit_label: str,
) -> dict[str, Any]:
    branch_summary = _summary(branch_summary_payload)
    tuning_summary = _summary(stage6_tuning_surface_payload)
    source_row = _latest_result_ready_row(execution_queue_payload, target_id)
    source_shard_id = _text(source_row.get("shard_id")) or _text(branch_summary.get("shard_id"))
    target_slug = _text(source_row.get("target_slug")) or slug(target_id)
    source_command_kind = _text(branch_summary.get("selected_command_kind")) or _text(tuning_summary.get("immediately_runnable_command_kind"))
    source_summary_override = (
        _text(source_row.get("source_summary_json"))
        or _text(branch_summary.get("source_summary_json"))
        or _text(tuning_summary.get("source_summary_json"))
    )
    source_summary_json = (
        _under_root(source_summary_override)
        if source_summary_override
        else _resolve_source_summary_json(
            target_slug=target_slug,
            shard_id=source_shard_id,
            source_command_kind=source_command_kind,
        )
    )
    source_summary_payload = _load_json_if_exists(source_summary_json)

    queue_csv = _resolve_artifact_path(
        source_summary_payload,
        source_summary_json,
        "queue_csv",
        f"{_base_prefix_for_command_kind(source_command_kind)}_stage1_queue.csv",
    )
    stage2_manifest_csv = _resolve_artifact_path(
        source_summary_payload,
        source_summary_json,
        "stage2_trajectory_summary_json",
        f"{_base_prefix_for_command_kind(source_command_kind)}_stage2_traj_manifest.csv",
    )
    if stage2_manifest_csv.name.endswith("_summary.json"):
        prefix = _base_prefix_for_command_kind(source_command_kind)
        stage2_manifest_csv = source_summary_json.parent / f"{prefix}_stage2_traj_manifest.csv"
    trajectory_root = _resolve_artifact_path(
        source_summary_payload,
        source_summary_json,
        "trajectory_root",
        f"{_base_prefix_for_command_kind(source_command_kind)}_stage2_traj_frames",
    )
    stage3_scores_csv = _resolve_artifact_path(
        source_summary_payload,
        source_summary_json,
        "stage3_scores_csv",
        f"{_base_prefix_for_command_kind(source_command_kind)}_stage3_scores.csv",
    )

    stage3_rows = _read_csv_rows(stage3_scores_csv)
    ranked_rows, ranking_meta = _rank_rows_by_active_score(
        stage3_rows,
        score_sources=(
            source_row,
            branch_summary_payload,
            stage6_tuning_surface_payload,
            source_summary_payload,
        ),
    )
    selection_score_col = _text(ranking_meta.get("score_col")) or "binding_energy_proxy"
    candidate_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked_rows[: max(1, int(top_n))], start=1):
        selection_score_value = _selection_ranking_score_value(row, selection_score_col)
        candidate_rows.append(
            {
                "row_kind": "allatom_refinement_candidate",
                "target_id": target_id,
                "target_slug": target_slug,
                "source_shard_id": source_shard_id,
                "priority_rank": idx,
                "ligand_id": _text(row.get("ligand_id")),
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "stability_score": _safe_float(row.get("stability_score")),
                "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                "selection_score_col": selection_score_col,
                "selection_score_value": selection_score_value,
                "selection_score_source": _text(ranking_meta.get("score_source")),
                "selected_command_kind": selected_command_kind,
                "selected_threshold_A": selected_threshold_A,
                "selected_ligand_model": "3bead_implicit_hbond",
                "source_command_kind": source_command_kind,
            }
        )

    ready = bool(
        source_shard_id
        and source_summary_json.exists()
        and queue_csv.exists()
        and stage2_manifest_csv.exists()
        and trajectory_root.exists()
        and candidate_rows
    )
    result_ready_count = sum(
        1
        for row in execution_queue_payload.get("rows", []) or []
        if _text((row or {}).get("target_id")) == target_id and _text((row or {}).get("queue_status")) == "result_ready"
    )
    summary = {
        "status": f"wetlab_{target_slug}_allatom_refinement_lane_ready",
        "target_id": target_id,
        "source_shard_id": source_shard_id,
        "source_success_shard_count": result_ready_count,
        "lane_label": lane_label,
        "review_unit_label": review_unit_label,
        "selected_command_kind": selected_command_kind,
        "selected_threshold_A": selected_threshold_A,
        "selected_ligand_model": "3bead_implicit_hbond",
        "source_command_kind": source_command_kind,
        "recommended_observed_threshold_A": _safe_float(tuning_summary.get("recommended_observed_threshold_A")),
        "top_n_requested": int(top_n),
        "source_summary_json": str(source_summary_json),
        "source_queue_csv": str(queue_csv),
        "source_stage2_manifest_csv": str(stage2_manifest_csv),
        "source_trajectory_root": str(trajectory_root),
        "source_stage3_scores_csv": str(stage3_scores_csv),
        "selection_score_col": selection_score_col,
        "selection_score_source": _text(ranking_meta.get("score_source")),
        "selection_requested_score_col": _text(ranking_meta.get("requested_score_col")),
        "selection_available_score_cols": list(ranking_meta.get("available_score_cols", []) or []),
        "selection_score_direction": "ascending",
        "focus_selection_score_value": candidate_rows[0].get("selection_score_value") if candidate_rows else None,
        "candidate_row_count": len(candidate_rows),
        "ready_for_manual_retry": ready,
        "default_lane_reopen_allowed": False,
        "next_required_step": (
            f"Run the {target_id} pseudo all-atom top-{int(top_n)} refinement lane from {source_shard_id} and keep the default lane closed until the review packet lands."
            if ready
            else f"Refresh {target_id} source tuned artifacts before launching the pseudo all-atom refinement lane."
        ),
    }
    return {
        "summary": summary,
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "branch_summary_artifact": "",
            "stage6_tuning_surface_artifact": "",
        },
        "rows": candidate_rows,
    }


def run_target_allatom_refinement_slice(
    *,
    lane_json: str,
    target_id: str,
    out_md: str,
    top_k: int,
    claim_readiness_json: str,
    equivalence_gate_json: str,
    python_bin: str,
    execute: bool,
    slice_group: str,
) -> dict[str, Any]:
    lane_payload = load_json(lane_json)
    lane_summary = _summary(lane_payload)
    resolved_target = _text(lane_summary.get("target_id")) or target_id
    source_shard_id = _text(lane_summary.get("source_shard_id"))
    if _text(resolved_target) != _text(target_id):
        raise SystemExit(f"all-atom refinement lane target mismatch: expected {target_id}, got {resolved_target}")
    if not bool(lane_summary.get("ready_for_manual_retry", False)):
        raise SystemExit(f"{target_id} all-atom refinement lane is not ready_for_manual_retry")

    requested_top_k = max(1, int(top_k))
    candidate_rows = [dict(row or {}) for row in (lane_payload.get("rows", []) or [])]
    slice_rows = candidate_rows[:requested_top_k]
    if not slice_rows:
        raise SystemExit(f"no all-atom candidates found for {target_id}")

    target_slug = _text(slice_rows[0].get("target_slug")) or slug(target_id)
    slice_dir = _under_root(f"runs/{slice_group}/{target_slug}/{source_shard_id}/top_{requested_top_k}")
    slice_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv = slice_dir / "allatom_slice_manifest.csv"
    queue_subset_csv = slice_dir / "allatom_slice_queue.csv"
    state_json = slice_dir / "allatom_slice_state.json"
    scores_csv = slice_dir / "allatom_slice_scores.csv"
    summary_json = slice_dir / "allatom_slice_summary.json"
    summary_md = slice_dir / "allatom_slice_summary.md"
    scoring_log = slice_dir / "allatom_slice_scoring.log"
    out_dir = slice_dir / "allatom_delivery"

    selected_ligand_ids = {_text(row.get("ligand_id")) for row in slice_rows}
    queue_csv = _under_root(_text(lane_summary.get("source_queue_csv")))
    stage2_manifest_csv = _under_root(_text(lane_summary.get("source_stage2_manifest_csv")))
    trajectory_root = _under_root(_text(lane_summary.get("source_trajectory_root")))
    target_native_csv_candidates = [
        _text(lane_summary.get("source_target_native_csv")),
        str(trajectory_root.parent / "target_native_stub.csv") if str(trajectory_root).strip() else "",
    ]
    if not queue_csv.exists():
        raise SystemExit(f"missing source queue for all-atom refinement: {queue_csv}")
    if not stage2_manifest_csv.exists():
        raise SystemExit(f"missing stage2 manifest for all-atom refinement: {stage2_manifest_csv}")
    if not trajectory_root.exists():
        raise SystemExit(f"missing trajectory root for all-atom refinement: {trajectory_root}")

    manifest_rows: list[dict[str, Any]] = []
    for row in slice_rows:
        manifest_rows.append(
            {
                "target_id": target_id,
                "target_slug": target_slug,
                "source_shard_id": source_shard_id,
                "priority_rank": _safe_int(row.get("priority_rank"), 0),
                "ligand_id": _text(row.get("ligand_id")),
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "stability_score": _safe_float(row.get("stability_score")),
                "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                "selection_score_col": _text(row.get("selection_score_col")),
                "selection_score_value": _optional_float(row.get("selection_score_value")),
                "selected_command_kind": _text(lane_summary.get("selected_command_kind")),
                "selected_threshold_A": _safe_float(lane_summary.get("selected_threshold_A"), 2.5),
                "selected_ligand_model": _text(lane_summary.get("selected_ligand_model")) or "3bead_implicit_hbond",
            }
        )
    write_csv_rows(manifest_csv, manifest_rows)

    queue_subset_rows: list[dict[str, Any]] = []
    with queue_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if _text(row.get("ligand_id")) in selected_ligand_ids:
                queue_subset_rows.append(dict(row))
    if not queue_subset_rows:
        raise SystemExit(f"no queue rows matched all-atom slice ligands for {target_id} {source_shard_id}")
    native_reference = _resolve_target_native_reference(
        target_id=target_id,
        candidate_csv_paths=target_native_csv_candidates,
    )
    queue_subset_rows = _inject_target_native_reference(
        queue_subset_rows,
        target_id=target_id,
        native_reference=native_reference,
    )
    write_csv_rows(queue_subset_csv, queue_subset_rows)

    execution_mode = "controller_manifest_only"
    scoring_status = "not_executed"
    scoring_returncode: int | None = None
    if execute:
        scoring_cmd = [
            python_bin,
            str(ROOT / "tools" / "run_ligand_backmapping_scoring.py"),
            "--queue-csv",
            str(queue_subset_csv),
            "--stage2-manifest-csv",
            str(stage2_manifest_csv),
            "--trajectory-root",
            str(trajectory_root),
            "--min-frames",
            "100",
            "--max-jobs",
            str(len(manifest_rows)),
            "--ligand-model",
            _text(lane_summary.get("selected_ligand_model")) or "3bead_implicit_hbond",
            "--out-dir",
            str(out_dir),
            "--out-scores-csv",
            str(scores_csv),
            "--out-summary-json",
            str(summary_json),
            "--out-summary-md",
            str(summary_md),
            "--workers",
            "0",
            "--parallel-threshold",
            "2",
            "--make-bundle-zip",
            "--no-allow-missing-trajectory",
        ]
        with scoring_log.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.run(
                scoring_cmd,
                cwd=ROOT,
                text=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        scoring_returncode = int(proc.returncode)
        execution_mode = "pseudo_allatom_backmapping_scoring_executed"
        if summary_json.exists():
            scoring_payload = load_json(str(summary_json))
            scoring_summary = dict(scoring_payload.get("summary", {}) or {})
            scoring_pass = bool(
                scoring_summary.get("pass", False)
                or scoring_payload.get("pass", False)
                or proc.returncode == 0
            )
            scoring_status = "pass" if scoring_pass else "error"
        else:
            scoring_status = "error"

    payload = {
        "summary": {
            "status": f"wetlab_{target_slug}_allatom_refinement_runner_ready",
            "target_id": target_id,
            "source_shard_id": source_shard_id,
            "selected_command_kind": _text(lane_summary.get("selected_command_kind")),
            "selected_threshold_A": _safe_float(lane_summary.get("selected_threshold_A"), 2.5),
            "selected_ligand_model": _text(lane_summary.get("selected_ligand_model")) or "3bead_implicit_hbond",
            "requested_top_k": requested_top_k,
            "slice_candidate_count": len(manifest_rows),
            "source_candidate_count": len(candidate_rows),
            "focus_ligand_id": _text(manifest_rows[0].get("ligand_id")),
            "selection_score_col": _text(lane_summary.get("selection_score_col")),
            "selection_score_source": _text(lane_summary.get("selection_score_source")),
            "selection_requested_score_col": _text(lane_summary.get("selection_requested_score_col")),
            "selection_score_direction": _text(lane_summary.get("selection_score_direction")) or "ascending",
            "focus_selection_score_value": manifest_rows[0].get("selection_score_value") if manifest_rows else None,
            "allatom_claim_readiness_json": _text(claim_readiness_json),
            "allatom_equivalence_gate_json": _text(equivalence_gate_json),
            "slice_manifest_csv": str(manifest_csv),
            "slice_queue_csv": str(queue_subset_csv),
            "slice_state_json": str(state_json),
            "stage2_manifest_csv": str(stage2_manifest_csv),
            "trajectory_root": str(trajectory_root),
            "target_native_csv": _text(native_reference.get("source_csv")),
            "target_native_pdb_path": _text(native_reference.get("native_pdb_path")),
            "target_native_pdb_id": _text(native_reference.get("pdb_id")),
            "target_native_provenance": _text(native_reference.get("provenance")),
            "allatom_scores_csv": str(scores_csv),
            "allatom_summary_json": str(summary_json),
            "allatom_summary_md": str(summary_md),
            "allatom_scoring_log": str(scoring_log),
            "execution_mode": execution_mode,
            "scoring_status": scoring_status,
            "scoring_returncode": scoring_returncode,
            "next_required_step": (
                f"Review the top-{len(manifest_rows)} pseudo all-atom refinement slice results for {target_id} {source_shard_id} before reopening any default lane."
            ),
        },
        "structured": {
            "allatom_refinement_lane_artifact": lane_json.replace(".json", ".md"),
            "allatom_claim_readiness_json": _text(claim_readiness_json),
            "allatom_equivalence_gate_json": _text(equivalence_gate_json),
        },
        "rows": manifest_rows,
    }
    state_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_artifact(out_md, f"Wet-Lab {target_id} All-Atom Refinement Runner", payload)
    return payload


def build_target_allatom_review_packet(
    *,
    target_id: str,
    lane_payload: dict[str, Any],
    runner_payload: dict[str, Any],
    lane_label: str,
    branch_mode: str,
    default_lane_reopen_allowed: bool = False,
    claim_readiness_json: str = "",
    equivalence_gate_json: str = "",
) -> dict[str, Any]:
    lane_summary = _summary(lane_payload)
    runner_summary = _summary(runner_payload)
    runner_rows = [dict(row or {}) for row in (runner_payload.get("rows", []) or [])]
    runner_rows_by_ligand = {
        _text(row.get("ligand_id")): row
        for row in runner_rows
        if _text(row.get("ligand_id"))
    }
    allatom_summary_json = _text(runner_summary.get("allatom_summary_json"))
    scoring_payload = load_json(allatom_summary_json) if allatom_summary_json else {}
    topk_rows = [dict(row or {}) for row in (scoring_payload.get("topk", []) or [])]
    promoted_rows = []
    for idx, row in enumerate(topk_rows[:4], start=1):
        selection_row = runner_rows_by_ligand.get(_text(row.get("ligand_id")), {})
        promoted_rows.append(
            {
                "row_kind": "allatom_review_packet_row",
                "packet_rank": idx,
                "target_id": target_id,
                "source_shard_id": _text(lane_summary.get("source_shard_id")),
                "ligand_id": _text(row.get("ligand_id")),
                "queue_id": _text(row.get("queue_id")),
                "mean_min_distance_A": round(_safe_float(row.get("mean_min_distance_A")), 3),
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "binding_energy_mmpbsa_kcal_mol_proxy": _safe_float(row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
                "binding_energy_mmpbsa_std": _safe_float(row.get("binding_energy_mmpbsa_std")),
                "stability_score": _safe_float(row.get("stability_score")),
                "contact_fraction": _safe_float(row.get("contact_fraction")),
                "trajectory_frames": _safe_int(row.get("trajectory_frames")),
                "ligand_model": _text(row.get("ligand_model")),
                "backmapped_pdb": _text(row.get("backmapped_pdb")),
                "score_json": _text(row.get("score_json")),
                "selection_score_col": _text(selection_row.get("selection_score_col")) or _text(runner_summary.get("selection_score_col")),
                "selection_score_value": _optional_float(selection_row.get("selection_score_value")),
                **_extract_commercial_v2_optional_fields(dict(row or {})),
            }
        )
    best_row = promoted_rows[0] if promoted_rows else {}
    strict_threshold = 2.5
    near_threshold = 3.0
    gate_summary = compute_wetlab_gate_summary(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
    )
    claim_gate_summary = resolve_optional_claim_gate_summary(
        target_id=target_id,
        claim_readiness_json=claim_readiness_json,
        equivalence_gate_json=equivalence_gate_json,
        runner_payload=runner_payload,
    )
    final_gate_summary = compute_final_wetlab_gate_summary(
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
    )
    commercial_schema_v1 = compute_commercial_grade_schema_v1(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
        final_gate_summary=final_gate_summary,
    )
    promoted_rows = list(commercial_schema_v1.get("rows", []) or promoted_rows)
    commercial_schema_v2 = compute_commercial_grade_schema_v2(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
        final_gate_summary=final_gate_summary,
    )
    promoted_rows = list(commercial_schema_v2.get("rows", []) or promoted_rows)
    best_row = promoted_rows[0] if promoted_rows else {}
    wetlab_gate_pass = bool(gate_summary.get("wetlab_gate_pass"))
    wetlab_final_gate_pass = bool(final_gate_summary.get("wetlab_final_gate_pass"))
    packet_ready_for_operator_review = bool(gate_summary.get("packet_ready_for_operator_review"))
    wetlab_gate_mode = _text(gate_summary.get("wetlab_gate_mode"))
    claim_gate_required_for_final_wetlab = bool(
        claim_gate_summary.get("claim_gate_required_for_final_wetlab", False)
    )
    claim_gate_primary_action = _text(claim_gate_summary.get("claim_gate_primary_action"))
    if wetlab_final_gate_pass:
        next_required_step = (
            f"Review the promoted pseudo all-atom top-4 packet for {target_id}, keep the default lane closed, and only advance as wetlab-ready after operator sign-off on the {wetlab_gate_mode} gate pass."
        )
    elif packet_ready_for_operator_review and wetlab_gate_pass and claim_gate_required_for_final_wetlab:
        next_required_step = (
            f"Review the promoted pseudo all-atom top-4 packet for {target_id} manually only, keep the default lane closed, and do not treat it as final wetlab-ready until the semi-hard claim/equivalence requirement is cleared; next action: {claim_gate_primary_action or 'produce_claim_equivalence_packet'}."
        )
    elif packet_ready_for_operator_review and wetlab_gate_pass and bool(claim_gate_summary.get("claim_gate_available")):
        next_required_step = (
            f"Review the promoted pseudo all-atom top-4 packet for {target_id} manually only, keep the default lane closed, and do not treat it as final wetlab-ready because the optional claim/equivalence gate did not pass."
        )
    elif packet_ready_for_operator_review:
        next_required_step = (
            f"Review the promoted pseudo all-atom top-4 packet for {target_id} manually only, keep the default lane closed, and do not treat it as wetlab-ready because the {wetlab_gate_mode} gate did not pass."
        )
    else:
        next_required_step = (
            f"No promoted pseudo all-atom packet rows are ready yet for {target_id}; do not treat this target as wetlab-ready."
        )
    return {
        "summary": {
            "status": f"wetlab_{slug(target_id)}_allatom_review_packet_ready",
            "target_id": target_id,
            "source_shard_id": _text(lane_summary.get("source_shard_id")),
            "surface_label": f"{slug(target_id)}_allatom_review_packet",
            "packet_scope": "partner_operator_allatom_refinement_review",
            "packet_ready": bool(promoted_rows),
            "packet_ready_for_operator_review": packet_ready_for_operator_review,
            "wetlab_gate_pass": wetlab_gate_pass,
            "wetlab_gate_mode": wetlab_gate_mode,
            "wetlab_gate_band_candidate_count": _safe_int(gate_summary.get("wetlab_gate_band_candidate_count")),
            "wetlab_gate_failed_metrics": list(gate_summary.get("wetlab_gate_failed_metrics", []) or []),
            "wetlab_gate_failed_metric_count": _safe_int(gate_summary.get("wetlab_gate_failed_metric_count")),
            "wetlab_gate_reason": _text(gate_summary.get("wetlab_gate_reason")),
            "wetlab_gate_thresholds": dict(gate_summary.get("wetlab_gate_thresholds", {}) or {}),
            "claim_gate_available": bool(claim_gate_summary.get("claim_gate_available")),
            "claim_gate_source": _text(claim_gate_summary.get("claim_gate_source")),
            "claim_gate_policy_version": _text(claim_gate_summary.get("policy_version")),
            "claim_gate_semantics_version": _text(claim_gate_summary.get("claim_gate_semantics_version")),
            "claim_gate_requirement_mode": _text(claim_gate_summary.get("claim_gate_requirement_mode")),
            "claim_gate_requirement_provenance": _text(
                claim_gate_summary.get("claim_gate_requirement_provenance")
            ),
            "claim_gate_target_group": _text(claim_gate_summary.get("claim_gate_target_group")),
            "claim_gate_required_for_final_wetlab": claim_gate_required_for_final_wetlab,
            "claim_gate_required_for_commercial_readiness": bool(
                claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
            ),
            "claim_gate_requirement_reason": _text(
                claim_gate_summary.get("claim_gate_requirement_reason")
            ),
            "claim_gate_requirement_actions": _normalize_text_list(
                claim_gate_summary.get("claim_gate_requirement_actions")
            ),
            "claim_gate_status": _text(claim_gate_summary.get("claim_gate_status")),
            "claim_gate_satisfied": claim_gate_summary.get("claim_gate_satisfied"),
            "claim_gate_status_reason": _text(claim_gate_summary.get("claim_gate_status_reason")),
            "claim_gate_primary_action": claim_gate_primary_action,
            "claim_gate_action_rollup": _text(claim_gate_summary.get("claim_gate_action_rollup")),
            "claim_gate_blocking_metrics": _normalize_text_list(
                claim_gate_summary.get("claim_gate_blocking_metrics")
            ),
            "claim_gate_missing_metrics_detail": _normalize_text_list(
                claim_gate_summary.get("claim_gate_missing_metrics_detail")
            ),
            "pass_core_gate": claim_gate_summary.get("pass_core_gate"),
            "claim_ready_for_allatom": claim_gate_summary.get("claim_ready_for_allatom"),
            "core_failed_metrics": claim_gate_summary.get("core_failed_metrics"),
            "core_missing_metrics": claim_gate_summary.get("core_missing_metrics"),
            "claim_failed_metrics": claim_gate_summary.get("claim_failed_metrics"),
            "claim_missing_metrics": claim_gate_summary.get("claim_missing_metrics"),
            "wetlab_final_gate_mode": _text(final_gate_summary.get("wetlab_final_gate_mode")),
            "wetlab_final_gate_pass": wetlab_final_gate_pass,
            "wetlab_final_gate_failed_metrics": list(final_gate_summary.get("wetlab_final_gate_failed_metrics", []) or []),
            "wetlab_final_gate_missing_metrics": list(
                final_gate_summary.get("wetlab_final_gate_missing_metrics", []) or []
            ),
            "wetlab_final_gate_failed_metric_count": _safe_int(final_gate_summary.get("wetlab_final_gate_failed_metric_count")),
            "wetlab_final_gate_missing_metric_count": _safe_int(
                final_gate_summary.get("wetlab_final_gate_missing_metric_count")
            ),
            "wetlab_final_gate_reason": _text(final_gate_summary.get("wetlab_final_gate_reason")),
            "wetlab_final_gate_blocking_domain": _text(
                final_gate_summary.get("wetlab_final_gate_blocking_domain")
            ),
            "wetlab_final_gate_required_next_actions": _normalize_text_list(
                final_gate_summary.get("wetlab_final_gate_required_next_actions")
            ),
            "lane_label": lane_label,
            "branch_mode": branch_mode,
            "default_lane_reopen_allowed": bool(default_lane_reopen_allowed),
            "selected_command_kind": _text(lane_summary.get("selected_command_kind")),
            "selected_threshold_A": _safe_float(lane_summary.get("selected_threshold_A"), 2.5),
            "selected_ligand_model": _text(lane_summary.get("selected_ligand_model")) or "3bead_implicit_hbond",
            "selection_score_col": _text(runner_summary.get("selection_score_col")) or _text(lane_summary.get("selection_score_col")),
            "selection_score_source": _text(runner_summary.get("selection_score_source")) or _text(lane_summary.get("selection_score_source")),
            "selection_score_direction": _text(runner_summary.get("selection_score_direction")) or "ascending",
            "strict_threshold_A": strict_threshold,
            "near_threshold_A": near_threshold,
            "promoted_candidate_count": len(promoted_rows),
            "under_2p5_candidate_count": _safe_int(gate_summary.get("strict_candidate_count")),
            "near_candidate_count": _safe_int(gate_summary.get("near_candidate_count")),
            "best_ligand_id": _text(best_row.get("ligand_id")),
            "best_mean_min_distance_A": round(_safe_float(best_row.get("mean_min_distance_A")), 3),
            "best_binding_energy_proxy": _safe_float(best_row.get("binding_energy_proxy")),
            "best_binding_energy_mmpbsa_kcal_mol_proxy": _safe_float(best_row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
            "best_binding_energy_mmpbsa_std": _safe_float(best_row.get("binding_energy_mmpbsa_std")),
            "best_stability_score": _safe_float(best_row.get("stability_score")),
            "best_selection_score_value": _optional_float(best_row.get("selection_score_value")),
            "allatom_scoring_status": _text(runner_summary.get("scoring_status")),
            "execution_mode": _text(runner_summary.get("execution_mode")),
            "next_required_step": next_required_step,
            **dict(commercial_schema_v1.get("summary", {}) or {}),
            **dict(commercial_schema_v2.get("summary", {}) or {}),
        },
        "structured": {
            "allatom_refinement_lane_artifact": "",
            "allatom_runner_artifact": "",
            "allatom_scores_csv": _text(runner_summary.get("allatom_scores_csv")),
            "allatom_summary_json": allatom_summary_json,
            "allatom_claim_readiness_json": _text(claim_gate_summary.get("claim_readiness_json")),
            "allatom_equivalence_gate_json": _text(claim_gate_summary.get("equivalence_gate_json")),
            "allatom_equivalence_gate_csv": _text(claim_gate_summary.get("equivalence_gate_csv")),
        },
        "rows": promoted_rows,
    }
