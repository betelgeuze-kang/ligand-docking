#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WETLAB_DASHBOARD_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_WETLAB_FINAL_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_selected_allatom_gate_burndown_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_selected_allatom_gate_burndown_packet_current.md"
TCRUZI_PDE_ALLATOM_REVIEW_ARTIFACTS = {
    "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
    "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _summaryish(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    if summary:
        merged = dict(payload)
        merged.update(summary)
        return merged
    return dict(payload or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_float(value: Any, digits: int = 3) -> str:
    parsed = _float(value)
    if parsed is None:
        return "-"
    return f"{parsed:.{digits}f}"


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "passed"}:
        return True
    if text in {"false", "0", "no", "fail", "failed"}:
        return False
    return None


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            text = _text(item)
            if text and text not in out:
                out.append(text)
        return out
    text = _text(value)
    return [text] if text else []


def _status_is_resolved(value: Any) -> bool:
    return _text(value).lower() in {
        "satisfied",
        "pass",
        "passed",
        "resolved",
        "complete",
        "completed",
        "not_applicable",
    }


def _canonical_artifact(path_like: str) -> str:
    return path_like.replace("\\", "/").lstrip("./")


def _review_json_for_focus(focus_artifact: str) -> Path | None:
    artifact = _canonical_artifact(focus_artifact)
    if artifact not in TCRUZI_PDE_ALLATOM_REVIEW_ARTIFACTS:
        return None
    json_artifact = artifact[:-3] + ".json" if artifact.endswith(".md") else artifact
    path = _resolve(json_artifact)
    return path if path.exists() else None


def _review_metric_override(
    focus_artifact: str,
    selected_allatom_review_payload: dict[str, Any] | None,
) -> dict[str, str] | None:
    if _canonical_artifact(focus_artifact) not in TCRUZI_PDE_ALLATOM_REVIEW_ARTIFACTS:
        return None
    if not selected_allatom_review_payload:
        return None

    review = _summaryish(selected_allatom_review_payload)
    value_num = _float(review.get("best_mean_min_distance_A"))
    thresholds = review.get("wetlab_gate_thresholds") if isinstance(review.get("wetlab_gate_thresholds"), dict) else {}
    threshold_num = _float(review.get("selected_threshold_A"))
    if threshold_num is None:
        threshold_num = _float(thresholds.get("selected_threshold_A") or thresholds.get("strict_threshold_A"))
    if value_num is None or threshold_num is None:
        return None

    return {
        "metric": "mean_min_distance_A",
        "value": _fmt_float(value_num),
        "threshold": _fmt_float(threshold_num),
        "delta": _fmt_float(value_num - threshold_num),
        "source_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json",
        "source_kind": "selected_allatom_review_packet_summary",
        "refresh_reason": "review_packet_best_mean_min_distance_A_supersedes_stale_final_campaign_selected_allatom_value",
    }


def _metric_override_passes(metric_override: dict[str, str] | None) -> bool:
    if not metric_override:
        return False
    value_num = _float(metric_override.get("value"))
    threshold_num = _float(metric_override.get("threshold"))
    return bool(value_num is not None and threshold_num is not None and value_num <= threshold_num)


def _renumber_rows(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        row["burndown_rank"] = index


def _insert_claim_required_unavailable_row(
    rows: list[dict[str, Any]],
    *,
    reason: str,
) -> None:
    if any(_text(row.get("code")) == "recompute_claim_gate_required_unavailable" for row in rows):
        return

    row = {
        "burndown_rank": 0,
        "severity": "hard",
        "category": "translation_commercial_hard_gate",
        "operational_bucket": _operational_bucket(
            "recompute_claim_gate_required_unavailable",
            "translation_commercial_hard_gate",
            "hard",
        ),
        "action": "review_claim_gate_required_unavailable",
        "calc_action": "recompute_claim_gate_required_unavailable",
        "status": "missing",
        "code": "recompute_claim_gate_required_unavailable",
        "metric": "claim_gate_required_unavailable",
        "value": "missing",
        "threshold": "missing",
        "delta": "-",
        "gate_dependency": _gate_dependency("translation_commercial_hard_gate", "hard"),
        "reason": reason or "claim_gate_required_unavailable=missing",
        "next_required_action": _next_required_action(
            "recompute_claim_gate_required_unavailable",
            "review_claim_gate_required_unavailable",
        ),
        "repair_lane": "",
        "repair_action": "",
        "repair_source_artifact": "",
        "repair_source_kind": "",
        "repair_source_ligand_id": "",
    }
    insert_at = next((idx for idx, existing in enumerate(rows) if _text(existing.get("severity")) != "hard"), len(rows))
    rows.insert(insert_at, row)
    _renumber_rows(rows)


def _commercial_metric_code(metric: str, action: str = "") -> str:
    metric = _text(metric)
    action = _text(action)
    by_metric = {
        "translation_gate_focus_status": "clear_translation_hard_gate",
        "focus_shortlist_tier": "promote_stronger_physics_shortlist",
        "recommended_next_expensive_lane": "replace_deferred_expensive_lane_with_validated_repair",
        "binding_energy_proxy": "recompute_binding_energy_proxy",
        "mean_min_distance_A": "recompute_mean_min_distance_A",
    }
    if action:
        return action
    return by_metric.get(metric, f"resolve_{metric}" if metric else "resolve_commercial_hard_gate")


def _commercial_metric_threshold(metric: str) -> str:
    metric = _text(metric)
    by_metric = {
        "translation_gate_focus_status": "pass",
        "focus_shortlist_tier": "tier1_gold|tier2_silver|tier3_bronze",
        "recommended_next_expensive_lane": "validated_repair_or_stronger_physics_lane",
        "binding_energy_proxy": "<= -0.050",
        "mean_min_distance_A": "<= selected_threshold_A",
    }
    return by_metric.get(metric, "commercial_hard_gate_pass_v2=true")


def _commercial_metric_value(review: dict[str, Any], metric: str) -> str:
    metric = _text(metric)
    by_metric = {
        "translation_gate_focus_status": review.get("translation_gate_focus_status"),
        "focus_shortlist_tier": review.get("focus_shortlist_tier"),
        "recommended_next_expensive_lane": review.get("recommended_next_expensive_lane"),
        "binding_energy_proxy": review.get("best_binding_energy_proxy"),
        "mean_min_distance_A": review.get("best_mean_min_distance_A"),
    }
    value = by_metric.get(metric)
    if value is None:
        value = review.get(metric)
    return _text(value) or "failed"


def _insert_commercial_hard_gate_rows(
    rows: list[dict[str, Any]],
    *,
    review: dict[str, Any],
) -> None:
    hard_gate_pass = _bool_or_none(review.get("commercial_hard_gate_pass_v2"))
    if hard_gate_pass is not False:
        return

    failed_metrics = _text_list(review.get("commercial_hard_gate_failed_metrics_v2"))
    missing_metrics = _text_list(review.get("commercial_hard_gate_missing_metrics_v2"))
    actions = _text_list(review.get("commercial_primary_upgrade_actions_v2"))
    metrics = failed_metrics + [metric for metric in missing_metrics if metric not in failed_metrics]
    if not metrics:
        metrics = ["commercial_hard_gate_pass_v2"]

    existing_codes = {_text(row.get("code")) for row in rows}
    new_rows: list[dict[str, Any]] = []
    for index, metric in enumerate(metrics):
        action = actions[index] if index < len(actions) else ""
        code = _commercial_metric_code(metric, action)
        if code in existing_codes:
            continue
        existing_codes.add(code)
        status = "missing" if metric in missing_metrics else "failed"
        value = "missing" if status == "missing" else _commercial_metric_value(review, metric)
        row = {
            "burndown_rank": 0,
            "severity": "hard",
            "category": "translation_commercial_hard_gate",
            "operational_bucket": _operational_bucket(code, "translation_commercial_hard_gate", "hard"),
            "action": action or code,
            "calc_action": code,
            "status": status,
            "code": code,
            "metric": metric,
            "value": value,
            "threshold": _commercial_metric_threshold(metric),
            "delta": "-",
            "gate_dependency": _gate_dependency("translation_commercial_hard_gate", "hard"),
            "reason": (
                f"commercial_hard_gate_pass_v2=false; {metric}={value}; "
                f"translation_commercial_fail_closed={bool(review.get('translation_commercial_fail_closed', False))}"
            ),
            "next_required_action": _next_required_action(code, action or code),
            **_repair_provenance(
                code=code,
                metric=metric,
                focus_artifact="runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                selected_allatom_review_payload={"summary": review},
            ),
        }
        new_rows.append(row)

    if not new_rows:
        return
    insert_at = next((idx for idx, existing in enumerate(rows) if _text(existing.get("severity")) != "hard"), len(rows))
    rows[insert_at:insert_at] = new_rows
    _renumber_rows(rows)


def _review_resolves_stale_action_row(review: dict[str, Any], code: str, metric: str) -> bool:
    metric = _text(metric)
    code = _text(code)
    hard_gate_pass = _bool_or_none(review.get("commercial_hard_gate_pass_v2"))
    if hard_gate_pass is True and metric in {
        "translation_gate_focus_status",
        "focus_shortlist_tier",
        "recommended_next_expensive_lane",
    }:
        return True
    if hard_gate_pass is True and code in {
        "clear_translation_hard_gate",
        "promote_stronger_physics_shortlist",
        "replace_deferred_expensive_lane_with_validated_repair",
        "recompute_translation_gate_focus_status",
        "recompute_focus_shortlist_tier",
        "recompute_recommended_next_expensive_lane",
    }:
        return True
    recommended_lane = _text(review.get("recommended_next_expensive_lane")).lower()
    if code == "defer_expensive_lane" and recommended_lane and not recommended_lane.startswith("defer"):
        return True
    return False


def _operational_bucket(code: str, category: str, severity: str) -> str:
    if code == "recompute_mean_min_distance_A":
        return "geometry_hard_block"
    if code == "recompute_binding_energy_proxy":
        return "binding_proxy_hard_block"
    if code == "clear_translation_hard_gate":
        return "translation_hard_gate_block"
    if code == "promote_stronger_physics_shortlist":
        return "stronger_physics_shortlist_block"
    if code == "replace_deferred_expensive_lane_with_validated_repair":
        return "validated_repair_lane_block"
    if code == "recompute_claim_gate_required_unavailable":
        return "claim_gate_metric_missing"
    if category == "claim_equivalence":
        return "claim_equivalence_block"
    if severity == "soft":
        return "expensive_lane_hold"
    return "general_gate_followup"


def _gate_dependency(category: str, severity: str) -> str:
    if severity == "hard":
        return "must_clear_before_claim_or_expensive_lane"
    if category == "claim_equivalence":
        return "blocked_until_translation_hard_gate_clears"
    return "keep_parked_until_hard_gate_clears"


def _next_required_action(code: str, action: str) -> str:
    if code == "recompute_mean_min_distance_A":
        return (
            "Re-minimize the selected all-atom pose, rerun short replicated MD, and refresh the strict 2.5A geometry gate before any stronger-physics escalation."
        )
    if code == "recompute_claim_gate_required_unavailable":
        return (
            "Materialize the missing claim_gate_required_unavailable field on the selected all-atom focus and rerun the translation/commercial hard gate."
        )
    if code == "recompute_binding_energy_proxy":
        return (
            "Use the bounded T. cruzi PDE all-atom rescue lane to rescore or replace the selected strict-geometry pose, then rebuild "
            "the all-atom review packet and selected-allatom burndown packet; do not promote claim/equivalence or expensive-lane "
            "readiness until binding_energy_proxy is <= -0.050 from that source chain."
        )
    if code == "clear_translation_hard_gate":
        return (
            "Clear the selected all-atom translation hard gate with a validated repair or replacement pose, then rebuild the all-atom review packet before execution readiness can turn green."
        )
    if code == "promote_stronger_physics_shortlist":
        return (
            "Promote a stronger-physics shortlist only after the selected pose clears the translation hard gate and has enough support to leave the defer tier."
        )
    if code == "replace_deferred_expensive_lane_with_validated_repair":
        return (
            "Replace the deferred expensive lane with a validated repair lane; do not count `defer_expensive_lane` as commercial readiness evidence."
        )
    if code == "produce_claim_equivalence_packet":
        return (
            "Assemble the neglected-disease claim/equivalence packet and attach it to the selected all-atom focus after all selected all-atom hard blocks are cleared."
        )
    if code == "resolve_claim_equivalence_gate":
        return (
            "Re-evaluate the claim/equivalence gate after the packet is attached; do not mark the lane final-wetlab-ready until this gate explicitly resolves."
        )
    if code == "defer_expensive_lane":
        return (
            "Keep explicit-water rescoring and seed-replicated short MD parked until geometry and claim-gate blockers are both resolved."
        )
    return f"Resolve `{action or code or 'selected_allatom_gate_action'}` before reopening the selected all-atom lane."


def _selected_review_row(review_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not review_payload:
        return {}
    review = _summaryish(review_payload)
    best_ligand_id = _text(review.get("best_ligand_id"))
    rows = [dict(row or {}) for row in (review_payload.get("rows", []) or [])]
    if best_ligand_id:
        for row in rows:
            if _text(row.get("ligand_id")) == best_ligand_id:
                return row
    return rows[0] if rows else {}


def _repair_provenance(
    *,
    code: str,
    metric: str,
    focus_artifact: str,
    selected_allatom_review_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if code != "recompute_binding_energy_proxy" and metric != "binding_energy_proxy":
        return {
            "repair_lane": "",
            "repair_action": "",
            "repair_source_artifact": "",
            "repair_source_kind": "",
            "repair_source_ligand_id": "",
        }

    review = _summaryish(selected_allatom_review_payload or {})
    selected_row = _selected_review_row(selected_allatom_review_payload)
    source_artifact = (
        _text(selected_row.get("score_json"))
        or _text(review.get("allatom_summary_json"))
        or _canonical_artifact(focus_artifact)
        or "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
    )
    return {
        "repair_lane": "tcruzi_pde_allatom_rescue",
        "repair_action": "run_clash_relief_allatom_rescue_then_build_review_packet",
        "repair_source_artifact": source_artifact,
        "repair_source_kind": "selected_allatom_review_packet_best_row_binding_energy_proxy",
        "repair_source_ligand_id": _text(selected_row.get("ligand_id")) or _text(review.get("best_ligand_id")),
    }


def build_payload(
    wetlab_dashboard_payload: dict[str, Any],
    wetlab_final_payload: dict[str, Any],
    selected_allatom_review_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard = _summaryish(wetlab_dashboard_payload)
    final_summary = _summaryish(wetlab_final_payload)

    action_rows = list(
        dashboard.get("selected_allatom_action_recipe_rows")
        or final_summary.get("selected_allatom_action_recipe_rows")
        or []
    )
    target_id = _text(dashboard.get("selected_allatom_target_id")) or _text(final_summary.get("selected_allatom_target_id"))
    focus_artifact = _text(dashboard.get("selected_allatom_focus_artifact")) or "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md"
    selected_command_kind = _text(dashboard.get("selected_allatom_selected_command_kind")) or _text(
        final_summary.get("selected_allatom_selected_command_kind")
    )
    selected_threshold_A = _text(dashboard.get("selected_allatom_selected_threshold_A")) or _text(
        final_summary.get("selected_allatom_selected_threshold_A")
    )
    best_mean_min_distance_A = _text(final_summary.get("selected_allatom_best_mean_min_distance_A"))
    wetlab_gate_pass = bool(dashboard.get("selected_allatom_wetlab_gate_pass", False))
    final_gate_pass = bool(dashboard.get("selected_allatom_final_gate_pass", False))
    claim_gate_available = bool(dashboard.get("selected_allatom_claim_gate_available", False))
    claim_ready_for_allatom = bool(dashboard.get("selected_allatom_claim_ready_for_allatom", False))
    actionability_status = _text(final_summary.get("selected_allatom_effective_actionability_status")) or _text(
        dashboard.get("selected_allatom_actionability_status")
    )
    primary_blocking_domain = _text(final_summary.get("selected_allatom_effective_primary_blocking_domain"))
    claim_requirement_reason = _text(
        final_summary.get("selected_allatom_effective_actionability_claim_requirement_reason")
    ) or _text(dashboard.get("selected_allatom_actionability_claim_requirement_reason"))
    action_recipe_rollup_text = _text(dashboard.get("selected_allatom_action_recipe_rollup_text")) or _text(
        final_summary.get("selected_allatom_action_recipe_rollup_text")
    )
    promoted_candidate_count = _int(final_summary.get("selected_allatom_promoted_candidate_count"))
    strict_candidate_count = _int(final_summary.get("selected_allatom_under_2p5_candidate_count"))
    near_candidate_count = _int(final_summary.get("selected_allatom_near_candidate_count"))
    metric_override = _review_metric_override(focus_artifact, selected_allatom_review_payload)
    metric_override_passes = _metric_override_passes(metric_override)
    review = _summaryish(selected_allatom_review_payload or {})
    review_commercial_hard_gate_pass_v2 = _bool_or_none(review.get("commercial_hard_gate_pass_v2"))
    review_commercial_failed_metrics_v2 = _text_list(review.get("commercial_hard_gate_failed_metrics_v2"))
    review_commercial_missing_metrics_v2 = _text_list(review.get("commercial_hard_gate_missing_metrics_v2"))
    review_translation_commercial_fail_closed = _bool_or_none(review.get("translation_commercial_fail_closed"))
    review_translation_commercial_failed_metrics = _text_list(review.get("translation_commercial_failed_metrics"))

    rows: list[dict[str, Any]] = []
    for action_row in action_rows:
        code = _text(action_row.get("code")) or _text(action_row.get("calc_action"))
        metric = _text(action_row.get("metric"))
        if _review_resolves_stale_action_row(review, code, metric):
            continue
        if code == "recompute_mean_min_distance_A" and metric_override_passes:
            continue
        if _status_is_resolved(action_row.get("status")):
            continue
        rank = len(rows) + 1
        severity = _text(action_row.get("severity"))
        category = _text(action_row.get("category"))
        value = _text(action_row.get("value"))
        threshold = _text(action_row.get("threshold"))
        value_num = _float(value)
        threshold_num = _float(threshold)
        delta_text = (
            _fmt_float(value_num - threshold_num)
            if value_num is not None and threshold_num is not None
            else "-"
        )
        rows.append(
            {
                "burndown_rank": rank,
                "severity": severity,
                "category": category,
                "operational_bucket": _operational_bucket(code, category, severity),
                "action": _text(action_row.get("action")),
                "calc_action": _text(action_row.get("calc_action")),
                "status": _text(action_row.get("status")),
                "code": code,
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "delta": delta_text,
                "gate_dependency": _gate_dependency(category, severity),
                "reason": _text(action_row.get("reason")),
                "next_required_action": _next_required_action(code, _text(action_row.get("action"))),
                **_repair_provenance(
                    code=code,
                    metric=metric,
                    focus_artifact=focus_artifact,
                    selected_allatom_review_payload=selected_allatom_review_payload,
                ),
            }
        )

    if metric_override:
        best_mean_min_distance_A = metric_override["value"]
        selected_threshold_A = metric_override["threshold"]
        for row in rows:
            if row["code"] == "recompute_mean_min_distance_A":
                row["metric"] = metric_override["metric"]
                row["value"] = metric_override["value"]
                row["threshold"] = metric_override["threshold"]
                row["delta"] = metric_override["delta"]
                row["reason"] = (
                    f"mean_min_distance_A={metric_override['value']} threshold={metric_override['threshold']} "
                    f"from {metric_override['source_artifact']}"
                )
                break

        review = _summaryish(selected_allatom_review_payload or {})
        review_wetlab_gate_pass = _bool_or_none(review.get("wetlab_gate_pass"))
        review_final_gate_pass = _bool_or_none(review.get("wetlab_final_gate_pass"))
        review_claim_gate_available = _bool_or_none(review.get("claim_gate_available"))
        if review_wetlab_gate_pass is not None:
            wetlab_gate_pass = review_wetlab_gate_pass
        if review_claim_gate_available is False:
            claim_gate_available = False
            claim_ready_for_allatom = False
            final_gate_pass = False
        elif review_claim_gate_available is not None:
            claim_gate_available = claim_gate_available and review_claim_gate_available
        if review_final_gate_pass is not None:
            final_gate_pass = review_final_gate_pass
        review_claim_ready = _bool_or_none(review.get("claim_ready_for_allatom"))
        review_claim_satisfied = _bool_or_none(review.get("claim_gate_satisfied"))
        if review_claim_ready is not None:
            claim_ready_for_allatom = review_claim_ready
        if review_claim_satisfied is False:
            claim_ready_for_allatom = False
            final_gate_pass = False
        missing_metrics = {
            _text(metric)
            for metric in (
                review.get("wetlab_final_gate_missing_metrics")
                or review.get("commercial_hard_gate_missing_metrics_v2")
                or []
            )
        }
        if (
            review_claim_gate_available is False
            or review_claim_satisfied is False
            or "claim_gate_required_unavailable" in missing_metrics
        ):
            _insert_claim_required_unavailable_row(
                rows,
                reason=(
                    _text(review.get("claim_gate_status_reason"))
                    or _text(review.get("wetlab_final_gate_reason"))
                    or "claim_gate_required_unavailable=missing from selected all-atom review packet"
                ),
            )
        _insert_commercial_hard_gate_rows(rows, review=review)

    hard_block_count = sum(1 for row in rows if row["severity"] == "hard")
    semi_hard_block_count = sum(1 for row in rows if row["severity"] == "semi_hard")
    soft_deferred_count = sum(1 for row in rows if row["severity"] == "soft")
    missing_metric_count = sum(1 for row in rows if row["status"] == "missing")
    primary_row = rows[0] if rows else {}

    primary_metric = _text(primary_row.get("metric")) or "mean_min_distance_A"
    primary_value = _text(primary_row.get("value")) or best_mean_min_distance_A
    primary_threshold = _text(primary_row.get("threshold")) or selected_threshold_A
    primary_delta = _text(primary_row.get("delta"))
    action_recipe_rollup_text = " | ".join(
        f"{row['severity']}:{row['code']} -> {row['action'] or row['code']}"
        for row in rows
    )
    gate_clear = (
        bool(wetlab_gate_pass)
        and bool(final_gate_pass)
        and review_commercial_hard_gate_pass_v2 is not False
        and hard_block_count == 0
        and semi_hard_block_count == 0
        and missing_metric_count == 0
    )
    if gate_clear:
        next_required_step = (
            f"Selected all-atom wetlab gate is green for `{target_id or 'selected_allatom'}`: "
            f"`{primary_metric}` is `{primary_value or '-'}` versus `{primary_threshold or '-'}`. "
            "Keep the current review/claim evidence attached and defer expensive lanes unless a new delivery scope explicitly reopens them."
        )
    else:
        followup = (
            "then recompute the missing claim-gate field and reattach the claim/equivalence packet after all hard blocks clear."
            if missing_metric_count
            else "then rebuild the selected all-atom review, burndown, and execution-readiness chain after all hard blocks clear."
            if claim_gate_available and claim_ready_for_allatom
            else "then produce and resolve the claim/equivalence packet after all selected all-atom hard blocks clear."
        )
        next_required_step = (
            f"Start with `{_text(primary_row.get('code')) or 'recompute_mean_min_distance_A'}` on `{target_id or 'selected_allatom'}`: "
            f"`{primary_metric}` sits at `{primary_value or '-'}` versus `{primary_threshold or '-'}` (delta `{primary_delta or '-'}`), "
            f"repair_lane=`{_text(primary_row.get('repair_lane')) or 'selected_allatom_local_recompute'}` "
            f"repair_action=`{_text(primary_row.get('repair_action')) or _text(primary_row.get('calc_action')) or 'recompute_selected_allatom_metric'}`; "
            f"{followup} Keep expensive lanes deferred until the commercial hard blocks are cleared."
        )

    summary = {
        "packet_ready": True,
        "packet_artifact": "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
        "selected_allatom_target_id": target_id,
        "selected_allatom_focus_artifact": focus_artifact,
        "selected_allatom_selected_command_kind": selected_command_kind,
        "selected_allatom_selected_threshold_A": selected_threshold_A,
        "selected_allatom_best_mean_min_distance_A": best_mean_min_distance_A,
        "selected_allatom_metric_source_artifact": (
            metric_override["source_artifact"] if metric_override else "runs/wetlab_final_campaign_summary_current.json"
        ),
        "selected_allatom_metric_source_kind": (
            metric_override["source_kind"] if metric_override else "final_campaign_summary_selected_allatom"
        ),
        "selected_allatom_metric_refresh_reason": (
            metric_override["refresh_reason"] if metric_override else "default_final_campaign_summary_source"
        ),
        "selected_allatom_effective_execution_gate_pass": gate_clear,
        "selected_allatom_geometry_wetlab_gate_pass": wetlab_gate_pass,
        "selected_allatom_wetlab_gate_pass": wetlab_gate_pass,
        "selected_allatom_final_gate_pass": final_gate_pass,
        "selected_allatom_claim_gate_available": claim_gate_available,
        "selected_allatom_claim_ready_for_allatom": claim_ready_for_allatom,
        "selected_allatom_commercial_hard_gate_pass_v2": review_commercial_hard_gate_pass_v2,
        "selected_allatom_commercial_hard_gate_failed_metrics_v2": review_commercial_failed_metrics_v2,
        "selected_allatom_commercial_hard_gate_missing_metrics_v2": review_commercial_missing_metrics_v2,
        "selected_allatom_translation_commercial_fail_closed": review_translation_commercial_fail_closed,
        "selected_allatom_translation_commercial_failed_metrics": review_translation_commercial_failed_metrics,
        "selected_allatom_translation_gate_focus_status": _text(review.get("translation_gate_focus_status")),
        "selected_allatom_focus_shortlist_tier": _text(review.get("focus_shortlist_tier")),
        "selected_allatom_recommended_next_expensive_lane": _text(review.get("recommended_next_expensive_lane")),
        "selected_allatom_atomized_local_min_evidence_ready": _bool_or_none(
            review.get("atomized_local_min_evidence_ready")
        ),
        "selected_allatom_actionability_status": actionability_status,
        "selected_allatom_primary_blocking_domain": primary_blocking_domain,
        "selected_allatom_claim_requirement_reason": claim_requirement_reason,
        "row_count": len(rows),
        "hard_block_count": hard_block_count,
        "semi_hard_block_count": semi_hard_block_count,
        "soft_deferred_count": soft_deferred_count,
        "missing_metric_count": missing_metric_count,
        "promoted_candidate_count": promoted_candidate_count,
        "strict_candidate_count": strict_candidate_count,
        "near_candidate_count": near_candidate_count,
        "primary_burndown_code": _text(primary_row.get("code")),
        "primary_burndown_action": _text(primary_row.get("action")),
        "primary_burndown_metric": primary_metric,
        "primary_burndown_value": primary_value,
        "primary_burndown_threshold": primary_threshold,
        "primary_burndown_delta": primary_delta,
        "primary_repair_lane": _text(primary_row.get("repair_lane")),
        "primary_repair_action": _text(primary_row.get("repair_action")),
        "primary_repair_source_artifact": _text(primary_row.get("repair_source_artifact")),
        "primary_repair_source_kind": _text(primary_row.get("repair_source_kind")),
        "primary_repair_source_ligand_id": _text(primary_row.get("repair_source_ligand_id")),
        "next_required_step": next_required_step,
        "action_recipe_rollup_text": action_recipe_rollup_text,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wetlab Selected All-Atom Gate Burndown Packet",
        "",
        f"- selected_allatom_target_id: `{summary['selected_allatom_target_id']}`",
        f"- selected_allatom_focus_artifact: `{summary['selected_allatom_focus_artifact']}`",
        f"- selected_allatom_selected_command_kind: `{summary['selected_allatom_selected_command_kind']}`",
        f"- selected_allatom_selected_threshold_A: `{summary['selected_allatom_selected_threshold_A']}`",
        f"- selected_allatom_best_mean_min_distance_A: `{summary['selected_allatom_best_mean_min_distance_A']}`",
        f"- selected_allatom_metric_source_artifact: `{summary['selected_allatom_metric_source_artifact']}`",
        f"- selected_allatom_metric_source_kind: `{summary['selected_allatom_metric_source_kind']}`",
        f"- selected_allatom_metric_refresh_reason: `{summary['selected_allatom_metric_refresh_reason']}`",
        f"- selected_allatom_effective_execution_gate_pass: `{summary['selected_allatom_effective_execution_gate_pass']}`",
        f"- selected_allatom_geometry_wetlab_gate_pass: `{summary['selected_allatom_geometry_wetlab_gate_pass']}`",
        f"- selected_allatom_wetlab_gate_pass: `{summary['selected_allatom_wetlab_gate_pass']}`",
        f"- selected_allatom_final_gate_pass: `{summary['selected_allatom_final_gate_pass']}`",
        f"- selected_allatom_claim_gate_available: `{summary['selected_allatom_claim_gate_available']}`",
        f"- selected_allatom_claim_ready_for_allatom: `{summary['selected_allatom_claim_ready_for_allatom']}`",
        f"- selected_allatom_translation_gate_focus_status: `{summary['selected_allatom_translation_gate_focus_status'] or '-'}`",
        f"- selected_allatom_focus_shortlist_tier: `{summary['selected_allatom_focus_shortlist_tier'] or '-'}`",
        f"- selected_allatom_recommended_next_expensive_lane: `{summary['selected_allatom_recommended_next_expensive_lane'] or '-'}`",
        f"- selected_allatom_atomized_local_min_evidence_ready: `{summary['selected_allatom_atomized_local_min_evidence_ready']}`",
        f"- selected_allatom_actionability_status: `{summary['selected_allatom_actionability_status']}`",
        f"- selected_allatom_primary_blocking_domain: `{summary['selected_allatom_primary_blocking_domain']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- hard_block_count: `{summary['hard_block_count']}`",
        f"- semi_hard_block_count: `{summary['semi_hard_block_count']}`",
        f"- soft_deferred_count: `{summary['soft_deferred_count']}`",
        f"- missing_metric_count: `{summary['missing_metric_count']}`",
        f"- primary_burndown_code: `{summary['primary_burndown_code']}`",
        f"- primary_burndown_metric: `{summary['primary_burndown_metric']}`",
        f"- primary_burndown_delta: `{summary['primary_burndown_delta']}`",
        f"- primary_repair_lane: `{summary['primary_repair_lane'] or '-'}`",
        f"- primary_repair_action: `{summary['primary_repair_action'] or '-'}`",
        f"- primary_repair_source_artifact: `{summary['primary_repair_source_artifact'] or '-'}`",
        f"- primary_repair_source_ligand_id: `{summary['primary_repair_source_ligand_id'] or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Burndown Queue",
        "",
        "| rank | severity | bucket | code | status | metric | value | threshold | delta | repair_lane |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['burndown_rank']} | `{row['severity']}` | `{row['operational_bucket']}` | `{row['code']}` | "
            f"`{row['status']}` | `{row['metric'] or '-'}` | `{row['value'] or '-'}` | `{row['threshold'] or '-'}` | `{row['delta']}` | "
            f"`{row.get('repair_lane') or '-'}` |"
        )
    lines.extend(["", "## Action Recipe Rollup", "", f"- {summary['action_recipe_rollup_text'] or '-'}", "", "## Execution Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['code']}`: {row['next_required_action']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wetlab selected all-atom gate burndown packet.")
    parser.add_argument("--wetlab-dashboard-json", default=DEFAULT_WETLAB_DASHBOARD_JSON)
    parser.add_argument("--wetlab-final-json", default=DEFAULT_WETLAB_FINAL_JSON)
    parser.add_argument("--selected-allatom-review-json", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wetlab_dashboard_payload = _load_json(args.wetlab_dashboard_json)
    wetlab_final_payload = _load_json(args.wetlab_final_json)
    dashboard = _summaryish(wetlab_dashboard_payload)
    final_summary = _summaryish(wetlab_final_payload)
    focus_artifact = _text(dashboard.get("selected_allatom_focus_artifact")) or _text(
        final_summary.get("selected_allatom_focus_artifact")
    )
    review_json = _resolve(args.selected_allatom_review_json) if args.selected_allatom_review_json else _review_json_for_focus(focus_artifact)
    selected_allatom_review_payload = _load_json(review_json) if review_json else None
    payload = build_payload(
        wetlab_dashboard_payload=wetlab_dashboard_payload,
        wetlab_final_payload=wetlab_final_payload,
        selected_allatom_review_payload=selected_allatom_review_payload,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
