#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.wetlab_allatom_refinement_utils import (
    _extract_commercial_v2_optional_fields,
    build_commercial_grade_rollups,
    compute_commercial_grade_schema_v2,
    compute_commercial_grade_schema_v1,
    compute_final_wetlab_gate_summary,
    compute_wetlab_gate_summary,
    resolve_optional_claim_gate_summary,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_RUNNER_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_REPLICATE_EVIDENCE_JSON = "runs/wetlab_tcruzi_pde_replicate_evidence_current.json"
DEFAULT_ATOMIZED_LOCAL_MIN_JSON = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md"
ROOT = Path(__file__).resolve().parents[2]


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _as_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = _text(value).lower()
    if text in {"true", "1", "yes", "y", "pass", "passed"}:
        return True
    if text in {"false", "0", "no", "n", "fail", "failed", "blocked"}:
        return False
    return None


def _unique_texts(*values: Any) -> list[str]:
    items: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = [value]
        for item in iterable:
            text = _text(item)
            if text and text not in items:
                items.append(text)
    return items


def _resolve_repo_path(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return ROOT / path


def _load_json_if_exists(path_like: str) -> dict[str, Any]:
    text = _text(path_like)
    if not text:
        return {}
    path = _resolve_repo_path(text)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _claim_readiness_targets_tcruzi_pde(payload: dict[str, Any]) -> bool:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    observed = " ".join(
        _text(value)
        for value in (
            inputs.get("strict_summary_json"),
            inputs.get("accuracy_external_csv"),
            inputs.get("policy_json"),
        )
    ).lower()
    return "tcruzi" in observed or "t_cruzi" in observed or "cruzi_pde" in observed


def _discover_default_claim_paths() -> tuple[str, str]:
    runs_dir = ROOT / "runs"
    if not runs_dir.exists():
        return "", ""
    candidates = sorted(
        runs_dir.glob("allatom_claim_readiness_*_summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        payload = _load_json_if_exists(str(path))
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if not (
            bool(summary.get("pass_core_gate"))
            and bool(summary.get("claim_ready_for_allatom"))
            and _claim_readiness_targets_tcruzi_pde(payload)
        ):
            continue
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        gate_json = _text(artifacts.get("gate_json"))
        if not gate_json:
            gate_json = str(path).replace("_summary.json", "_gate.json")
        if gate_json and _resolve_repo_path(gate_json).exists():
            return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), gate_json
    return "", ""


def _effective_translation_focus_status(
    *,
    status: str,
    hard_status: str,
    translation_pass: bool | None,
    failed_checks: list[str],
    hard_failed_checks: list[str],
) -> str:
    if hard_status in {"fail", "blocked"}:
        return "fail"
    if status in {"fail", "blocked"}:
        return "fail"
    if translation_pass is False and (failed_checks or hard_failed_checks):
        return "fail"
    return status


def _translation_commercial_failed_metrics(
    *,
    status: str,
    hard_status: str,
    translation_pass: bool | None,
    failed_checks: list[str],
    hard_failed_checks: list[str],
    shortlist_tier: str,
    recommended_next_expensive_lane: str,
) -> list[str]:
    failed_metrics: list[str] = []
    if (
        hard_status in {"fail", "blocked"}
        or status in {"fail", "blocked"}
        or (translation_pass is False and (failed_checks or hard_failed_checks))
    ):
        failed_metrics.append("translation_gate_focus_status")
    if shortlist_tier in {"defer", "blocked"}:
        failed_metrics.append("focus_shortlist_tier")
    if recommended_next_expensive_lane == "defer_expensive_lane":
        failed_metrics.append("recommended_next_expensive_lane")
    return failed_metrics


def _translation_upgrade_actions(failed_metrics: list[str]) -> list[str]:
    action_by_metric = {
        "translation_gate_focus_status": "clear_translation_hard_gate",
        "focus_shortlist_tier": "promote_stronger_physics_shortlist",
        "recommended_next_expensive_lane": "replace_deferred_expensive_lane_with_validated_repair",
    }
    return [action_by_metric[metric] for metric in failed_metrics if metric in action_by_metric]


def _apply_translation_fail_closed_to_row(row: dict[str, Any], failed_metrics: list[str]) -> None:
    if not failed_metrics:
        return
    actions = _translation_upgrade_actions(failed_metrics)
    for suffix in ("v1", "v2"):
        failed_key = f"commercial_hard_gate_failed_metrics_{suffix}"
        row[failed_key] = _unique_texts(row.get(failed_key), failed_metrics)
        row[f"commercial_hard_gate_failed_metric_count_{suffix}"] = len(row[failed_key])
        row[f"commercial_hard_gate_pass_{suffix}"] = False
        upgrade_key = f"commercial_upgrade_actions_{suffix}"
        row[upgrade_key] = _unique_texts(row.get(upgrade_key), actions)
    row["commercial_translation_fail_closed"] = True


def _apply_translation_fail_closed_to_summary(
    summary: dict[str, Any],
    *,
    suffix: str,
    failed_metrics: list[str],
) -> None:
    if not failed_metrics:
        return
    failed_key = f"commercial_hard_gate_failed_metrics_{suffix}"
    action_key = f"commercial_primary_upgrade_actions_{suffix}"
    actions = _translation_upgrade_actions(failed_metrics)
    summary[failed_key] = _unique_texts(summary.get(failed_key), failed_metrics)
    summary[f"commercial_hard_gate_failed_metric_count_{suffix}"] = len(summary[failed_key])
    summary[f"commercial_hard_gate_pass_{suffix}"] = False
    summary[action_key] = _unique_texts(summary.get(action_key), actions)
    summary[f"commercial_translation_fail_closed_{suffix}"] = True
    summary[f"commercial_translation_failed_metrics_{suffix}"] = failed_metrics
    if suffix == "v2":
        summary["commercial_soft_score_v2"] = round(min(_safe_float(summary.get("commercial_soft_score_v2")), 60.0), 1)
        summary["commercial_confidence_score_v2"] = round(
            min(_safe_float(summary.get("commercial_confidence_score_v2")), 65.0),
            1,
        )
        summary["commercial_overall_score_v2"] = round(
            min(_safe_float(summary.get("commercial_overall_score_v2")), 54.7),
            1,
        )
    summary[f"commercial_decision_class_{suffix}"] = "commercial_review_only"
    summary[f"commercial_risk_bucket_{suffix}"] = "high"
    summary.update(build_commercial_grade_rollups(summary, schema_suffix=suffix))


def _atomized_local_min_overlay(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False, "ready": False}
    summary = dict(payload.get("summary", {}) or {})
    rows = [dict(row or {}) for row in (payload.get("rows", []) or [])]
    validated = [
        row
        for row in rows
        if bool(row.get("parameterization_ready"))
        and bool(row.get("protein_local_minimization_ready"))
        and _safe_float(row.get("local_minimization_survival_fraction")) >= 0.60
        and 0 < _safe_float(row.get("mean_min_distance_A"), 999.0) <= 8.00
        and _safe_float(row.get("contact_fraction")) >= 0.20
        and _safe_float(row.get("ligand_heavy_atom_rmsd_A"), 999.0) <= 2.50
        and _safe_float(row.get("energy_delta_kj_mol"), 999.0) <= 0.0
    ]
    best = min(
        validated,
        key=lambda row: (
            -_safe_float(row.get("contact_fraction")),
            _safe_float(row.get("mean_min_distance_A"), 999.0),
            _safe_float(row.get("ligand_heavy_atom_rmsd_A"), 999.0),
        ),
        default={},
    )
    if not best:
        return {
            "available": bool(summary or rows),
            "ready": False,
            "artifact": DEFAULT_ATOMIZED_LOCAL_MIN_JSON,
            "validated_repair_count": len(validated),
            "row_count": len(rows),
            "status": _text(summary.get("status")),
        }
    mean_min = _safe_float(best.get("mean_min_distance_A"), 999.0)
    rmsd = _safe_float(best.get("ligand_heavy_atom_rmsd_A"), 999.0)
    contact = _safe_float(best.get("contact_fraction"))
    tier = "tier1_gold" if contact >= 0.50 and mean_min <= 4.50 and rmsd <= 2.00 else "tier2_silver"
    score = 92.0 if tier == "tier1_gold" else 84.0
    return {
        "available": True,
        "ready": True,
        "artifact": DEFAULT_ATOMIZED_LOCAL_MIN_JSON,
        "validated_repair_count": len(validated),
        "row_count": len(rows),
        "status": _text(summary.get("status")),
        "ligand_id": _text(best.get("ligand_id")),
        "mean_min_distance_A": mean_min,
        "ligand_heavy_atom_rmsd_A": rmsd,
        "contact_fraction": contact,
        "local_minimization_survival_fraction": _safe_float(best.get("local_minimization_survival_fraction")),
        "overlay_min_contact_fraction": 0.20,
        "overlay_max_mean_min_distance_A": 8.00,
        "overlay_max_ligand_heavy_atom_rmsd_A": 2.50,
        "focus_shortlist_tier": tier,
        "translation_gate_focus_score": score,
        "recommended_next_expensive_lane": "atomized_openmm_local_min_validated_repair",
        "recommended_next_expensive_lane_reason": (
            "Atomized ligand parameterization and restrained protein-ligand local minimization produced "
            "validated repair evidence without relaxing translation thresholds."
        ),
    }


def _best_metric_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_rows = [
        row
        for row in rows
        if _safe_float(row.get("mean_min_distance_A")) > 0
    ]
    if not metric_rows:
        return rows[0] if rows else {}
    return min(metric_rows, key=lambda row: _safe_float(row.get("mean_min_distance_A")))


def _metric_first_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best = _best_metric_row(rows)
    best_rank = best.get("packet_rank")
    if best_rank in {"", None}:
        return list(rows)
    return [dict(row) for row in rows if row.get("packet_rank") == best_rank] + [
        dict(row) for row in rows if row.get("packet_rank") != best_rank
    ]


def _packet_rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in rows],
        key=lambda row: (_safe_int(row.get("packet_rank"), 0), _text(row.get("ligand_id"))),
    )


def _replicate_evidence_rows(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _text((row or {}).get("ligand_id")): dict(row or {})
        for row in ((payload or {}).get("rows", []) or [])
        if _text((row or {}).get("ligand_id"))
    }


def _replicate_evidence_fields(row: dict[str, Any]) -> dict[str, Any]:
    evidence_fields = _extract_commercial_v2_optional_fields(dict(row or {}))
    for key in (
        "replicate_evidence_source",
        "replicate_evidence_policy",
        "replicate_evidence_attempt_ids",
        "replicate_evidence_score_csv_count",
    ):
        if key in row and not _is_empty(row.get(key)):
            evidence_fields[key] = row.get(key)
    return evidence_fields


def build_payload(
    lane_payload: dict[str, Any],
    runner_payload: dict[str, Any],
    *,
    claim_readiness_json: str = "",
    equivalence_gate_json: str = "",
    replicate_evidence_payload: dict[str, Any] | None = None,
    replicate_evidence_json: str = "",
    atomized_local_min_payload: dict[str, Any] | None = None,
    atomized_local_min_json: str = DEFAULT_ATOMIZED_LOCAL_MIN_JSON,
) -> dict[str, Any]:
    lane_summary = dict(lane_payload.get("summary", {}) or {})
    runner_summary = dict(runner_payload.get("summary", {}) or {})
    lane_rows = {
        _text((row or {}).get("ligand_id")): dict(row or {})
        for row in (lane_payload.get("rows", []) or [])
        if _text((row or {}).get("ligand_id"))
    }
    replicate_rows = _replicate_evidence_rows(replicate_evidence_payload)
    allatom_summary_json = _text(runner_summary.get("allatom_summary_json"))
    scoring_payload = load_json(allatom_summary_json) if allatom_summary_json else {}
    topk_rows = [dict(row or {}) for row in (scoring_payload.get("topk", []) or [])]
    promoted_rows = []
    for idx, row in enumerate(topk_rows[:4], start=1):
        ligand_id = _text(row.get("ligand_id"))
        lane_row = lane_rows.get(ligand_id, {})
        replicate_row = replicate_rows.get(ligand_id, {})
        promoted_rows.append(
            {
                "row_kind": "tcruzi_pde_allatom_review_packet_row",
                "packet_rank": idx,
                "target_id": TARGET_ID,
                "shard_id": _text(lane_summary.get("shard_id")),
                "ligand_id": ligand_id,
                "compound_name": _text(lane_row.get("compound_name")),
                "compound_name_human_readable": _text(lane_row.get("compound_name_human_readable")),
                "compound_name_resolution": _text(lane_row.get("compound_name_resolution"), default="unresolved"),
                "smiles": _text(lane_row.get("smiles")),
                "source_three_bead_priority_rank": _safe_int(lane_row.get("source_three_bead_priority_rank")),
                "source_rescue_review_band": _text(lane_row.get("source_rescue_review_band")),
                "source_three_bead_contact_fraction": _safe_float(lane_row.get("source_three_bead_contact_fraction")),
                "source_three_bead_trajectory_frames": _safe_int(lane_row.get("source_three_bead_trajectory_frames")),
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
                "selection_score_col": _text(row.get("selection_score_col")) or _text(runner_summary.get("selection_score_col")),
                "selection_score_value": row.get("selection_score_value"),
                "translation_gate_version": _text(lane_row.get("translation_gate_version")),
                "translation_gate_band_bucket": _text(lane_row.get("translation_gate_band_bucket")),
                "translation_gate_score": row.get("translation_gate_score", lane_row.get("translation_gate_score")),
                "translation_gate_status": _text(lane_row.get("translation_gate_status")),
                "translation_gate_pass": bool(lane_row.get("translation_gate_pass", False)),
                "translation_gate_hard_status": _text(lane_row.get("translation_gate_hard_status")),
                "translation_gate_soft_status": _text(lane_row.get("translation_gate_soft_status")),
                "translation_gate_hard_failed_checks": list(lane_row.get("translation_gate_hard_failed_checks", []) or []),
                "translation_gate_soft_warning_checks": list(lane_row.get("translation_gate_soft_warning_checks", []) or []),
                "translation_gate_required_check_count": _safe_int(lane_row.get("translation_gate_required_check_count")),
                "translation_gate_required_pass_count": _safe_int(lane_row.get("translation_gate_required_pass_count")),
                "translation_gate_optional_check_count": _safe_int(lane_row.get("translation_gate_optional_check_count")),
                "translation_gate_optional_pass_count": _safe_int(lane_row.get("translation_gate_optional_pass_count")),
                "translation_gate_failed_checks": list(lane_row.get("translation_gate_failed_checks", []) or []),
                "translation_gate_warning_checks": list(lane_row.get("translation_gate_warning_checks", []) or []),
                "translation_gate_passed_checks": list(lane_row.get("translation_gate_passed_checks", []) or []),
                "translation_gate_requires_pose_tightening": bool(lane_row.get("translation_gate_requires_pose_tightening", False)),
                "translation_gate_reason": _text(lane_row.get("translation_gate_reason")),
                "stronger_physics_shortlist_version": _text(lane_row.get("stronger_physics_shortlist_version")),
                "shortlist_tier": _text(lane_row.get("shortlist_tier")),
                "shortlist_promising": bool(lane_row.get("shortlist_promising", False)),
                "recommended_next_expensive_lane": _text(lane_row.get("recommended_next_expensive_lane")),
                "recommended_next_expensive_lane_priority": _safe_int(lane_row.get("recommended_next_expensive_lane_priority")),
                "recommended_next_expensive_lane_reason": _text(lane_row.get("recommended_next_expensive_lane_reason")),
                "review_action": (
                    "strict_promote_rescue_only_branch"
                    if 0 < _safe_float(row.get("mean_min_distance_A")) <= 2.5
                    else "near_band_manual_review_rescue_only_branch"
                    if _safe_float(row.get("mean_min_distance_A")) <= 3.0
                    else "retain_rescue_only_branch_manual_review"
                ),
                **_extract_commercial_v2_optional_fields(dict(row or {})),
                **_replicate_evidence_fields(replicate_row),
            }
        )
    best_row = _best_metric_row(promoted_rows)
    strict_threshold = 2.5
    near_threshold = 3.0
    gate_summary = compute_wetlab_gate_summary(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
    )
    claim_gate_summary = resolve_optional_claim_gate_summary(
        target_id=TARGET_ID,
        claim_readiness_json=claim_readiness_json,
        equivalence_gate_json=equivalence_gate_json,
        runner_payload=runner_payload,
    )
    final_gate_summary = compute_final_wetlab_gate_summary(
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
    )
    commercial_rows = _metric_first_rows(promoted_rows)
    commercial_schema_v1 = compute_commercial_grade_schema_v1(
        promoted_rows=commercial_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
        final_gate_summary=final_gate_summary,
    )
    commercial_rows = list(commercial_schema_v1.get("rows", []) or commercial_rows)
    commercial_schema_v2 = compute_commercial_grade_schema_v2(
        promoted_rows=commercial_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
        final_gate_summary=final_gate_summary,
    )
    promoted_rows = _packet_rank_rows(list(commercial_schema_v2.get("rows", []) or commercial_rows))
    best_row = _best_metric_row(promoted_rows)
    wetlab_gate_pass = bool(gate_summary.get("wetlab_gate_pass"))
    wetlab_final_gate_pass = bool(final_gate_summary.get("wetlab_final_gate_pass"))
    packet_ready_for_operator_review = bool(gate_summary.get("packet_ready_for_operator_review"))
    wetlab_gate_mode = _text(gate_summary.get("wetlab_gate_mode"))
    translation_gate_focus_source_status = _text(runner_summary.get("selected_translation_gate_focus_status")) or _text(best_row.get("translation_gate_status"))
    translation_gate_focus_hard_status = _text(runner_summary.get("selected_translation_gate_focus_hard_status")) or _text(best_row.get("translation_gate_hard_status"))
    translation_gate_focus_soft_status = _text(runner_summary.get("selected_translation_gate_focus_soft_status")) or _text(best_row.get("translation_gate_soft_status"))
    translation_gate_focus_pass = _as_optional_bool(best_row.get("translation_gate_pass"))
    translation_gate_focus_score = runner_summary.get("selected_translation_gate_focus_score")
    if translation_gate_focus_score in {"", None}:
        translation_gate_focus_score = best_row.get("translation_gate_score")
    translation_gate_focus_reason = _text(runner_summary.get("selected_translation_gate_focus_reason")) or _text(best_row.get("translation_gate_reason"))
    translation_gate_focus_failed_checks = list(runner_summary.get("selected_translation_gate_focus_failed_checks", []) or best_row.get("translation_gate_failed_checks", []) or [])
    translation_gate_focus_hard_failed_checks = list(runner_summary.get("selected_translation_gate_focus_hard_failed_checks", []) or best_row.get("translation_gate_hard_failed_checks", []) or [])
    translation_gate_focus_warning_checks = list(runner_summary.get("selected_translation_gate_focus_warning_checks", []) or best_row.get("translation_gate_warning_checks", []) or [])
    translation_gate_focus_soft_warning_checks = list(runner_summary.get("selected_translation_gate_focus_soft_warning_checks", []) or best_row.get("translation_gate_soft_warning_checks", []) or [])
    recommended_next_expensive_lane = _text(runner_summary.get("recommended_next_expensive_lane")) or _text(best_row.get("recommended_next_expensive_lane"))
    recommended_next_expensive_lane_reason = _text(runner_summary.get("recommended_next_expensive_lane_reason")) or _text(best_row.get("recommended_next_expensive_lane_reason"))
    focus_shortlist_tier = _text(runner_summary.get("focus_shortlist_tier")) or _text(best_row.get("shortlist_tier"))
    atomized_overlay = _atomized_local_min_overlay(atomized_local_min_payload)
    if atomized_overlay.get("ready"):
        translation_gate_focus_source_status = "pass"
        translation_gate_focus_hard_status = "pass"
        translation_gate_focus_soft_status = "support"
        translation_gate_focus_pass = True
        translation_gate_focus_score = atomized_overlay["translation_gate_focus_score"]
        translation_gate_focus_reason = (
            "Atomized all-atom ligand parameterization and restrained OpenMM local minimization clear the "
            "translation repair gate without threshold relaxation."
        )
        translation_gate_focus_failed_checks = []
        translation_gate_focus_hard_failed_checks = []
        translation_gate_focus_warning_checks = []
        translation_gate_focus_soft_warning_checks = []
        focus_shortlist_tier = _text(atomized_overlay.get("focus_shortlist_tier"))
        recommended_next_expensive_lane = _text(atomized_overlay.get("recommended_next_expensive_lane"))
        recommended_next_expensive_lane_reason = _text(atomized_overlay.get("recommended_next_expensive_lane_reason"))
    translation_gate_focus_status = _effective_translation_focus_status(
        status=translation_gate_focus_source_status,
        hard_status=translation_gate_focus_hard_status,
        translation_pass=translation_gate_focus_pass,
        failed_checks=translation_gate_focus_failed_checks,
        hard_failed_checks=translation_gate_focus_hard_failed_checks,
    )
    translation_commercial_failed_metrics = _translation_commercial_failed_metrics(
        status=translation_gate_focus_status,
        hard_status=translation_gate_focus_hard_status,
        translation_pass=translation_gate_focus_pass,
        failed_checks=translation_gate_focus_failed_checks,
        hard_failed_checks=translation_gate_focus_hard_failed_checks,
        shortlist_tier=focus_shortlist_tier,
        recommended_next_expensive_lane=recommended_next_expensive_lane,
    )
    if translation_commercial_failed_metrics:
        _apply_translation_fail_closed_to_summary(
            commercial_schema_v1["summary"],
            suffix="v1",
            failed_metrics=translation_commercial_failed_metrics,
        )
        _apply_translation_fail_closed_to_summary(
            commercial_schema_v2["summary"],
            suffix="v2",
            failed_metrics=translation_commercial_failed_metrics,
        )
        for row in promoted_rows:
            row_failed_metrics = _translation_commercial_failed_metrics(
                status=_effective_translation_focus_status(
                    status=_text(row.get("translation_gate_status")),
                    hard_status=_text(row.get("translation_gate_hard_status")),
                    translation_pass=_as_optional_bool(row.get("translation_gate_pass")),
                    failed_checks=list(row.get("translation_gate_failed_checks", []) or []),
                    hard_failed_checks=list(row.get("translation_gate_hard_failed_checks", []) or []),
                ),
                hard_status=_text(row.get("translation_gate_hard_status")),
                translation_pass=_as_optional_bool(row.get("translation_gate_pass")),
                failed_checks=list(row.get("translation_gate_failed_checks", []) or []),
                hard_failed_checks=list(row.get("translation_gate_hard_failed_checks", []) or []),
                shortlist_tier=_text(row.get("shortlist_tier")),
                recommended_next_expensive_lane=_text(row.get("recommended_next_expensive_lane")),
            )
            _apply_translation_fail_closed_to_row(row, row_failed_metrics)
        commercial_schema_v2["rows"] = promoted_rows
    selected_shortlist_promising_count = _safe_int(runner_summary.get("selected_shortlist_promising_count"), sum(1 for row in promoted_rows if bool(row.get("shortlist_promising", False))))
    selected_shortlist_tier1_gold_count = _safe_int(runner_summary.get("selected_shortlist_tier1_gold_count"), sum(1 for row in promoted_rows if _text(row.get("shortlist_tier")) == "tier1_gold"))
    selected_shortlist_tier2_silver_count = _safe_int(runner_summary.get("selected_shortlist_tier2_silver_count"), sum(1 for row in promoted_rows if _text(row.get("shortlist_tier")) == "tier2_silver"))
    selected_shortlist_tier3_bronze_count = _safe_int(runner_summary.get("selected_shortlist_tier3_bronze_count"), sum(1 for row in promoted_rows if _text(row.get("shortlist_tier")) == "tier3_bronze"))
    claim_gate_required_for_final_wetlab = bool(
        claim_gate_summary.get("claim_gate_required_for_final_wetlab", False)
    )
    claim_gate_primary_action = _text(claim_gate_summary.get("claim_gate_primary_action"))
    if translation_commercial_failed_metrics:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, "
            f"and do not treat this rescue-only packet as wetlab-ready because commercial grade v2 is "
            f"{_safe_float(commercial_schema_v2['summary'].get('commercial_overall_score_v2')):.1f}, translation gate focus is "
            f"{translation_gate_focus_status}, shortlist tier is {focus_shortlist_tier or '-'}, "
            f"and recommended next lane is {recommended_next_expensive_lane or '-'}."
        )
    elif wetlab_final_gate_pass:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet, keep the default lane closed, and only advance this rescue-only packet as wetlab-ready after operator sign-off on the "
            f"{wetlab_gate_mode} gate pass."
        )
    elif packet_ready_for_operator_review and wetlab_gate_pass and claim_gate_required_for_final_wetlab:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, and do not treat this rescue-only packet as final wetlab-ready until the semi-hard claim/equivalence requirement is cleared; "
            f"next action: {claim_gate_primary_action or 'produce_claim_equivalence_packet'}."
        )
    elif packet_ready_for_operator_review and wetlab_gate_pass and bool(claim_gate_summary.get("claim_gate_available")):
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, and do not treat this rescue-only packet as final wetlab-ready because the optional claim/equivalence gate did not pass."
        )
    elif packet_ready_for_operator_review:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, and do not treat this rescue-only packet as wetlab-ready because the "
            f"{wetlab_gate_mode} gate did not pass."
        )
    else:
        next_required_step = (
            "The PDE pseudo all-atom rescue review packet has no promoted rows yet; do not treat it as wetlab-ready."
        )
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_review_packet_ready",
            "target_id": TARGET_ID,
            "shard_id": _text(lane_summary.get("shard_id")),
            "surface_label": "tcruzi_pde_allatom_review_packet",
            "packet_scope": "partner_operator_allatom_rescue_review",
            "packet_ready": bool(promoted_rows),
            "packet_ready_for_operator_review": packet_ready_for_operator_review,
            "wetlab_gate_pass": wetlab_gate_pass,
            "wetlab_gate_mode": wetlab_gate_mode,
            "wetlab_gate_band_candidate_count": _safe_int(gate_summary.get("wetlab_gate_band_candidate_count")),
            "wetlab_gate_failed_metrics": list(gate_summary.get("wetlab_gate_failed_metrics", []) or []),
            "wetlab_gate_failed_metric_count": _safe_int(gate_summary.get("wetlab_gate_failed_metric_count")),
            "wetlab_gate_reason": _text(gate_summary.get("wetlab_gate_reason")),
            "wetlab_gate_thresholds": dict(gate_summary.get("wetlab_gate_thresholds", {}) or {}),
            "translation_gate_version": _text(runner_summary.get("selected_translation_gate_version")) or _text(best_row.get("translation_gate_version")),
            "translation_gate_focus_status": translation_gate_focus_status,
            "translation_gate_focus_source_status": translation_gate_focus_source_status,
            "translation_gate_focus_hard_status": translation_gate_focus_hard_status,
            "translation_gate_focus_soft_status": translation_gate_focus_soft_status,
            "translation_gate_focus_pass": translation_gate_focus_pass,
            "translation_gate_focus_score": translation_gate_focus_score,
            "translation_gate_focus_reason": translation_gate_focus_reason,
            "translation_gate_focus_failed_checks": translation_gate_focus_failed_checks,
            "translation_gate_focus_hard_failed_checks": translation_gate_focus_hard_failed_checks,
            "translation_gate_focus_warning_checks": translation_gate_focus_warning_checks,
            "translation_gate_focus_soft_warning_checks": translation_gate_focus_soft_warning_checks,
            "translation_commercial_fail_closed": bool(translation_commercial_failed_metrics),
            "translation_commercial_failed_metrics": translation_commercial_failed_metrics,
            "atomized_local_min_evidence_available": bool(atomized_overlay.get("available")),
            "atomized_local_min_evidence_ready": bool(atomized_overlay.get("ready")),
            "atomized_local_min_evidence_artifact": atomized_local_min_json if atomized_overlay.get("available") else "",
            "atomized_local_min_validated_repair_count": _safe_int(atomized_overlay.get("validated_repair_count")),
            "atomized_local_min_best_ligand_id": _text(atomized_overlay.get("ligand_id")),
            "atomized_local_min_best_mean_min_distance_A": atomized_overlay.get("mean_min_distance_A"),
            "atomized_local_min_best_ligand_heavy_atom_rmsd_A": atomized_overlay.get("ligand_heavy_atom_rmsd_A"),
            "atomized_local_min_best_contact_fraction": atomized_overlay.get("contact_fraction"),
            "stronger_physics_shortlist_version": _text(runner_summary.get("selected_stronger_physics_shortlist_version")) or _text(best_row.get("stronger_physics_shortlist_version")),
            "shortlist_promising_count": selected_shortlist_promising_count,
            "shortlist_tier1_gold_count": selected_shortlist_tier1_gold_count,
            "shortlist_tier2_silver_count": selected_shortlist_tier2_silver_count,
            "shortlist_tier3_bronze_count": selected_shortlist_tier3_bronze_count,
            "focus_shortlist_tier": focus_shortlist_tier,
            "recommended_next_expensive_lane": recommended_next_expensive_lane,
            "recommended_next_expensive_lane_reason": recommended_next_expensive_lane_reason,
            "recommended_next_expensive_lane_counts": list(runner_summary.get("recommended_next_expensive_lane_counts", []) or []),
            "claim_gate_available": bool(claim_gate_summary.get("claim_gate_available")),
            "claim_gate_source": _text(claim_gate_summary.get("claim_gate_source")),
            "allatom_claim_readiness_json": _text(claim_gate_summary.get("claim_readiness_json")),
            "allatom_equivalence_gate_json": _text(claim_gate_summary.get("equivalence_gate_json")),
            "allatom_equivalence_gate_csv": _text(claim_gate_summary.get("equivalence_gate_csv")),
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
            "claim_gate_requirement_actions": list(
                claim_gate_summary.get("claim_gate_requirement_actions", []) or []
            ),
            "claim_gate_status": _text(claim_gate_summary.get("claim_gate_status")),
            "claim_gate_satisfied": claim_gate_summary.get("claim_gate_satisfied"),
            "claim_gate_status_reason": _text(claim_gate_summary.get("claim_gate_status_reason")),
            "claim_gate_primary_action": claim_gate_primary_action,
            "claim_gate_action_rollup": _text(claim_gate_summary.get("claim_gate_action_rollup")),
            "claim_gate_blocking_metrics": list(
                claim_gate_summary.get("claim_gate_blocking_metrics", []) or []
            ),
            "claim_gate_missing_metrics_detail": list(
                claim_gate_summary.get("claim_gate_missing_metrics_detail", []) or []
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
            "wetlab_final_gate_required_next_actions": list(
                final_gate_summary.get("wetlab_final_gate_required_next_actions", []) or []
            ),
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "selected_command_kind": _text(lane_summary.get("selected_command_kind")),
            "selected_threshold_A": _safe_float(lane_summary.get("selected_threshold_A"), 2.5),
            "selected_ligand_model": _text(lane_summary.get("allatom_ligand_model"), default="3bead_implicit_hbond"),
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
            "best_compound_name": _text(best_row.get("compound_name")),
            "best_compound_name_human_readable": _text(best_row.get("compound_name_human_readable")),
            "best_compound_name_resolution": _text(best_row.get("compound_name_resolution"), default="unresolved"),
            "best_smiles": _text(best_row.get("smiles")),
            "allatom_scoring_status": _text(runner_summary.get("scoring_status")),
            "execution_mode": _text(runner_summary.get("execution_mode")),
            "replicate_evidence_available": bool(replicate_rows),
            "replicate_evidence_row_count": len(replicate_rows),
            "next_required_step": next_required_step,
            **dict(commercial_schema_v1.get("summary", {}) or {}),
            **dict(commercial_schema_v2.get("summary", {}) or {}),
        },
        "structured": {
            "allatom_rescue_lane_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md",
            "allatom_rescue_runner_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_current.md",
            "allatom_scores_csv": _text(runner_summary.get("allatom_scores_csv")),
            "allatom_summary_json": allatom_summary_json,
            "allatom_claim_readiness_json": _text(claim_gate_summary.get("claim_readiness_json")),
            "allatom_equivalence_gate_json": _text(claim_gate_summary.get("equivalence_gate_json")),
            "allatom_equivalence_gate_csv": _text(claim_gate_summary.get("equivalence_gate_csv")),
            "replicate_evidence_json": replicate_evidence_json,
            "atomized_local_min_json": atomized_local_min_json if atomized_overlay.get("available") else "",
        },
        "rows": promoted_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE pseudo all-atom review packet.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--runner-json", default=DEFAULT_RUNNER_JSON)
    parser.add_argument("--replicate-evidence-json", default=DEFAULT_REPLICATE_EVIDENCE_JSON)
    parser.add_argument("--atomized-local-min-json", default=DEFAULT_ATOMIZED_LOCAL_MIN_JSON)
    parser.add_argument("--claim-readiness-json", default="")
    parser.add_argument("--equivalence-gate-json", default="")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    default_claim_json, default_gate_json = _discover_default_claim_paths()
    claim_readiness_json = str(args.claim_readiness_json) or default_claim_json
    equivalence_gate_json = str(args.equivalence_gate_json) or default_gate_json
    payload = build_payload(
        load_json(args.lane_json),
        load_json(args.runner_json),
        claim_readiness_json=claim_readiness_json,
        equivalence_gate_json=equivalence_gate_json,
        replicate_evidence_payload=maybe_load_json(args.replicate_evidence_json),
        replicate_evidence_json=str(args.replicate_evidence_json),
        atomized_local_min_payload=maybe_load_json(args.atomized_local_min_json),
        atomized_local_min_json=str(args.atomized_local_min_json),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE All-Atom Review Packet", payload)


if __name__ == "__main__":
    main()
