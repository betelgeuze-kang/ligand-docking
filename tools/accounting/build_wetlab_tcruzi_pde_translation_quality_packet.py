#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_TRANSLATION_EVIDENCE_JSON = "runs/wetlab_tcruzi_pde_translation_evidence_probe_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_translation_quality_packet_current.md"


CHECK_CATALOG: dict[str, dict[str, str]] = {
    "binding_energy_proxy_too_weak_for_translation": {
        "axis": "binding_energy_proxy",
        "action_code": "strengthen_binding_energy_proxy",
        "required_closure": "Re-score or calibrate the proxy before using the selected pose for broad translation claims.",
    },
    "binding_energy_proxy_source_pool_exhausted": {
        "axis": "binding_energy_proxy_candidate_pool",
        "action_code": "generate_stronger_three_bead_binding_candidate_pool",
        "required_closure": "Generate or source a stronger three-bead candidate pool before reopening expensive all-atom promotion.",
    },
    "candidate_pool_geometry_stability_blocked": {
        "axis": "candidate_pool_geometry_stability",
        "action_code": "repair_energy_pass_candidate_geometry_stability",
        "required_closure": "Run geometry and stability rescue on energy-pass candidates before reopening expensive all-atom promotion.",
    },
    "pose_preservation_rmsd_not_observed": {
        "axis": "pose_preservation_rmsd",
        "action_code": "measure_pose_preservation_rmsd",
        "required_closure": "Record pose-preservation RMSD for the selected backmapped pose.",
    },
    "pose_preservation_rmsd_too_high": {
        "axis": "pose_preservation_rmsd",
        "action_code": "repair_pose_preservation_geometry",
        "required_closure": "Repair or reject the pose until pose-preservation RMSD returns to the accepted band.",
    },
    "backmapping_consistency_not_observed": {
        "axis": "backmapping_consistency",
        "action_code": "measure_backmapping_consistency",
        "required_closure": "Measure backmapping consistency across deterministic reconstruction attempts.",
    },
    "backmapping_consistency_too_low": {
        "axis": "backmapping_consistency",
        "action_code": "repair_backmapping_consistency",
        "required_closure": "Improve reconstruction consistency before treating the pose as translation-stable.",
    },
    "local_minimization_survival_not_observed": {
        "axis": "local_minimization_survival",
        "action_code": "measure_local_minimization_survival",
        "required_closure": "Run and record local minimization survival for the selected pose.",
    },
    "local_minimization_survival_too_low": {
        "axis": "local_minimization_survival",
        "action_code": "repair_local_minimization_survival",
        "required_closure": "Repair pose contacts until the selected pose survives local minimization.",
    },
    "replicate_pass_fraction_not_observed": {
        "axis": "replicate_pass_fraction",
        "action_code": "collect_replicate_pass_fraction",
        "required_closure": "Collect replicate support for the selected pose before broadening the claim.",
    },
    "replicate_pass_fraction_too_low": {
        "axis": "replicate_pass_fraction",
        "action_code": "increase_replicate_support",
        "required_closure": "Increase replicate support or keep the pose in post-P0 follow-up scope.",
    },
}


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _best_metric_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_rows = [row for row in rows if _safe_float(row.get("mean_min_distance_A")) is not None]
    if not metric_rows:
        return rows[0] if rows else {}
    return min(metric_rows, key=lambda row: _safe_float(row.get("mean_min_distance_A"), 999999.0) or 999999.0)


def _evidence_status(check_id: str, failed_checks: set[str]) -> str:
    if check_id in failed_checks:
        return "failed"
    if check_id.endswith("_not_observed"):
        return "missing"
    return "warning"


def _catalog_entry(check_id: str) -> dict[str, str]:
    if check_id in CHECK_CATALOG:
        return dict(CHECK_CATALOG[check_id])
    return {
        "axis": check_id,
        "action_code": "manual_translation_quality_review",
        "required_closure": "Review this translation-quality signal manually before broadening the claim.",
    }


def _ordered_checks(failed_checks: list[str], warning_checks: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for check_id in [*failed_checks, *warning_checks]:
        clean = _text(check_id)
        if clean and clean not in seen:
            ordered.append(clean)
            seen.add(clean)
    return ordered


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "pass", "passed", "ready"}:
        return True
    if text in {"0", "false", "f", "no", "n", "fail", "failed", "blocked"}:
        return False
    return default


def build_payload(
    review_payload: dict[str, Any],
    *,
    source_review_json: str = DEFAULT_REVIEW_JSON,
    translation_evidence_payload: dict[str, Any] | None = None,
    source_translation_evidence_json: str = DEFAULT_TRANSLATION_EVIDENCE_JSON,
) -> dict[str, Any]:
    review_summary = dict(review_payload.get("summary", {}) or {})
    review_rows = [dict(row or {}) for row in (review_payload.get("rows", []) or [])]
    translation_evidence_summary = dict((translation_evidence_payload or {}).get("summary", {}) or {})
    best_row = _best_metric_row(review_rows)

    failed_checks = [_text(check) for check in (review_summary.get("translation_gate_focus_failed_checks", []) or []) if _text(check)]
    warning_checks = [_text(check) for check in (review_summary.get("translation_gate_focus_warning_checks", []) or []) if _text(check)]
    failed_set = set(failed_checks)
    ordered_checks = _ordered_checks(failed_checks, warning_checks)
    candidate_pool_row_count = _safe_int(translation_evidence_summary.get("translation_score_candidate_row_count"))
    candidate_pool_energy_pass_count = _safe_int(translation_evidence_summary.get("translation_energy_pass_count"))
    candidate_pool_core_pass_count = _safe_int(translation_evidence_summary.get("translation_core_pass_count"))
    candidate_pool_energy_pass_unique_ligand_count = _safe_int(
        translation_evidence_summary.get("translation_energy_pass_unique_ligand_count")
    )
    candidate_pool_core_pass_unique_ligand_count = _safe_int(
        translation_evidence_summary.get("translation_core_pass_unique_ligand_count")
    )
    candidate_pool_core_like_count = _safe_int(translation_evidence_summary.get("translation_core_like_count"))
    external_homolog_seed_row_count = _safe_int(
        translation_evidence_summary.get("external_homolog_seed_candidate_row_count")
    )
    external_homolog_seed_energy_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_seed_energy_pass_count")
    )
    external_homolog_seed_core_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_seed_core_pass_count")
    )
    external_homolog_geomstab_rescore_row_count = _safe_int(
        translation_evidence_summary.get("external_homolog_geomstab_rescore_candidate_row_count")
    )
    external_homolog_geomstab_rescore_energy_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_geomstab_rescore_energy_pass_count")
    )
    external_homolog_geomstab_rescore_core_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_geomstab_rescore_core_pass_count")
    )
    external_homolog_adress_rescue_row_count = _safe_int(
        translation_evidence_summary.get("external_homolog_adress_rescue_candidate_row_count")
    )
    external_homolog_adress_rescue_energy_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_adress_rescue_energy_pass_count")
    )
    external_homolog_adress_rescue_core_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_adress_rescue_core_pass_count")
    )
    external_homolog_contact_rescue_row_count = _safe_int(
        translation_evidence_summary.get("external_homolog_contact_rescue_candidate_row_count")
    )
    external_homolog_contact_rescue_energy_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_contact_rescue_energy_pass_count")
    )
    external_homolog_contact_rescue_core_pass_count = _safe_int(
        translation_evidence_summary.get("external_homolog_contact_rescue_core_pass_count")
    )
    external_bindingdb_similarity_row_count = _safe_int(
        translation_evidence_summary.get("external_bindingdb_similarity_candidate_row_count")
    )
    external_bindingdb_similarity_energy_pass_count = _safe_int(
        translation_evidence_summary.get("external_bindingdb_similarity_energy_pass_count")
    )
    external_bindingdb_similarity_core_pass_count = _safe_int(
        translation_evidence_summary.get("external_bindingdb_similarity_core_pass_count")
    )
    candidate_pool_best_binding_energy_proxy = _safe_float(translation_evidence_summary.get("best_binding_energy_proxy"))
    candidate_pool_best_core_like_binding_energy_proxy = _safe_float(
        translation_evidence_summary.get("best_core_like_binding_energy_proxy")
    )
    external_homolog_seed_best_binding_energy_proxy = _safe_float(
        translation_evidence_summary.get("external_homolog_seed_best_binding_energy_proxy")
    )
    external_homolog_geomstab_rescore_best_binding_energy_proxy = _safe_float(
        translation_evidence_summary.get("external_homolog_geomstab_rescore_best_binding_energy_proxy")
    )
    external_homolog_adress_rescue_best_binding_energy_proxy = _safe_float(
        translation_evidence_summary.get("external_homolog_adress_rescue_best_binding_energy_proxy")
    )
    external_homolog_contact_rescue_best_binding_energy_proxy = _safe_float(
        translation_evidence_summary.get("external_homolog_contact_rescue_best_binding_energy_proxy")
    )
    external_bindingdb_similarity_best_binding_energy_proxy = _safe_float(
        translation_evidence_summary.get("external_bindingdb_similarity_best_binding_energy_proxy")
    )
    candidate_pool_energy_gap_closed = _safe_bool(translation_evidence_summary.get("candidate_pool_energy_gap_closed", False))
    candidate_pool_core_gate_closed = _safe_bool(translation_evidence_summary.get("candidate_pool_core_gate_closed", False))
    candidate_pool_observed = candidate_pool_row_count > 0
    binding_energy_source_pool_exhausted = (
        candidate_pool_observed
        and "binding_energy_proxy_too_weak_for_translation" in failed_set
        and candidate_pool_energy_pass_count == 0
        and candidate_pool_core_pass_count == 0
    )
    candidate_pool_geometry_stability_blocked = (
        candidate_pool_observed
        and "binding_energy_proxy_too_weak_for_translation" in failed_set
        and candidate_pool_energy_pass_count > 0
        and candidate_pool_core_pass_count == 0
    )
    adress_rescue_attempted_without_core_pass = (
        external_homolog_adress_rescue_row_count > 0
        and external_homolog_adress_rescue_core_pass_count == 0
    )
    contact_aware_rescue_attempted_without_core_pass = (
        external_homolog_contact_rescue_row_count > 0
        and external_homolog_contact_rescue_core_pass_count == 0
    )
    bindingdb_similarity_seed_attempted_without_core_pass = (
        external_bindingdb_similarity_row_count > 0
        and external_bindingdb_similarity_core_pass_count == 0
    )
    if binding_energy_source_pool_exhausted and "binding_energy_proxy_source_pool_exhausted" not in ordered_checks:
        insert_at = (
            ordered_checks.index("binding_energy_proxy_too_weak_for_translation") + 1
            if "binding_energy_proxy_too_weak_for_translation" in ordered_checks
            else 0
        )
        ordered_checks.insert(insert_at, "binding_energy_proxy_source_pool_exhausted")
        failed_set.add("binding_energy_proxy_source_pool_exhausted")
    if candidate_pool_geometry_stability_blocked and "candidate_pool_geometry_stability_blocked" not in ordered_checks:
        insert_at = (
            ordered_checks.index("binding_energy_proxy_too_weak_for_translation") + 1
            if "binding_energy_proxy_too_weak_for_translation" in ordered_checks
            else 0
        )
        ordered_checks.insert(insert_at, "candidate_pool_geometry_stability_blocked")
        failed_set.add("candidate_pool_geometry_stability_blocked")

    wetlab_final_gate_pass = _safe_bool(review_summary.get("wetlab_final_gate_pass", False))
    commercial_hard_gate_pass = _safe_bool(
        review_summary.get("commercial_hard_gate_pass_v2", review_summary.get("commercial_hard_gate_pass_v1", False))
    )
    allatom_delivery_p0_green = wetlab_final_gate_pass and commercial_hard_gate_pass
    translation_focus_status = _text(review_summary.get("translation_gate_focus_status"), "unknown")
    translation_quality_ready = allatom_delivery_p0_green and translation_focus_status == "pass" and not ordered_checks
    primary_blocker = ordered_checks[0] if ordered_checks else ""

    target_id = _text(review_summary.get("target_id"), TARGET_ID)
    best_ligand_id = _text(review_summary.get("best_ligand_id")) or _text(best_row.get("ligand_id"))
    best_mean_min_distance_A = _safe_float(
        review_summary.get("best_mean_min_distance_A", best_row.get("mean_min_distance_A"))
    )
    best_binding_energy_proxy = _safe_float(
        review_summary.get("best_binding_energy_proxy", best_row.get("binding_energy_proxy"))
    )

    rows = []
    for idx, check_id in enumerate(ordered_checks, start=1):
        catalog = _catalog_entry(check_id)
        evidence_status = _evidence_status(check_id, failed_set)
        rows.append(
            {
                "row_kind": "tcruzi_pde_translation_quality_action",
                "priority_rank": idx,
                "target_id": target_id,
                "check_id": check_id,
                "quality_axis": catalog["axis"],
                "evidence_status": evidence_status,
                "action_code": catalog["action_code"],
                "required_closure": catalog["required_closure"],
                "best_ligand_id": best_ligand_id,
                "best_mean_min_distance_A": best_mean_min_distance_A,
                "best_binding_energy_proxy": best_binding_energy_proxy,
                "source_review_json": source_review_json,
                "source_translation_evidence_json": source_translation_evidence_json if translation_evidence_summary else "",
                "candidate_pool_row_count": candidate_pool_row_count,
                "candidate_pool_energy_pass_count": candidate_pool_energy_pass_count,
                "candidate_pool_core_pass_count": candidate_pool_core_pass_count,
                "candidate_pool_energy_pass_unique_ligand_count": candidate_pool_energy_pass_unique_ligand_count,
                "candidate_pool_core_pass_unique_ligand_count": candidate_pool_core_pass_unique_ligand_count,
                "external_homolog_seed_row_count": external_homolog_seed_row_count,
                "external_homolog_seed_energy_pass_count": external_homolog_seed_energy_pass_count,
                "external_homolog_seed_core_pass_count": external_homolog_seed_core_pass_count,
                "external_homolog_geomstab_rescore_row_count": external_homolog_geomstab_rescore_row_count,
                "external_homolog_geomstab_rescore_energy_pass_count": external_homolog_geomstab_rescore_energy_pass_count,
                "external_homolog_geomstab_rescore_core_pass_count": external_homolog_geomstab_rescore_core_pass_count,
                "external_homolog_adress_rescue_row_count": external_homolog_adress_rescue_row_count,
                "external_homolog_adress_rescue_energy_pass_count": external_homolog_adress_rescue_energy_pass_count,
                "external_homolog_adress_rescue_core_pass_count": external_homolog_adress_rescue_core_pass_count,
                "external_homolog_contact_rescue_row_count": external_homolog_contact_rescue_row_count,
                "external_homolog_contact_rescue_energy_pass_count": external_homolog_contact_rescue_energy_pass_count,
                "external_homolog_contact_rescue_core_pass_count": external_homolog_contact_rescue_core_pass_count,
                "external_bindingdb_similarity_row_count": external_bindingdb_similarity_row_count,
                "external_bindingdb_similarity_energy_pass_count": external_bindingdb_similarity_energy_pass_count,
                "external_bindingdb_similarity_core_pass_count": external_bindingdb_similarity_core_pass_count,
                "candidate_pool_best_binding_energy_proxy": candidate_pool_best_binding_energy_proxy,
                "candidate_pool_best_core_like_binding_energy_proxy": candidate_pool_best_core_like_binding_energy_proxy,
                "external_homolog_seed_best_binding_energy_proxy": external_homolog_seed_best_binding_energy_proxy,
                "external_homolog_geomstab_rescore_best_binding_energy_proxy": (
                    external_homolog_geomstab_rescore_best_binding_energy_proxy
                ),
                "external_homolog_adress_rescue_best_binding_energy_proxy": (
                    external_homolog_adress_rescue_best_binding_energy_proxy
                ),
                "external_homolog_contact_rescue_best_binding_energy_proxy": (
                    external_homolog_contact_rescue_best_binding_energy_proxy
                ),
                "external_bindingdb_similarity_best_binding_energy_proxy": (
                    external_bindingdb_similarity_best_binding_energy_proxy
                ),
                "claim_policy": "do_not_expand_claim_scope_until_closed",
            }
        )

    failed_evidence_count = sum(1 for row in rows if row["evidence_status"] == "failed")
    missing_evidence_count = sum(1 for row in rows if row["evidence_status"] == "missing")
    warning_evidence_count = sum(1 for row in rows if row["evidence_status"] == "warning")
    failed_quality_axes = [row["quality_axis"] for row in rows if row["evidence_status"] == "failed"]
    missing_quality_axes = [row["quality_axis"] for row in rows if row["evidence_status"] == "missing"]
    recommended_next_expensive_lane = _text(review_summary.get("recommended_next_expensive_lane"), "defer_expensive_lane")
    next_required_step = (
        "Translation quality evidence is closed; broad wetlab claim review may proceed."
        if translation_quality_ready
        else (
            "Run geometry and stability rescue on energy-pass PDEB1 homolog seed candidates before reopening expensive all-atom promotion."
            if candidate_pool_geometry_stability_blocked
            and not adress_rescue_attempted_without_core_pass
            and not contact_aware_rescue_attempted_without_core_pass
            else (
                "Add a contact-aware pocket objective or all-atom-style pose-preservation signal for the energy-pass PDEB1 homolog seed candidates; the ADRESS rescue attempt did not close geometry/stability."
                if candidate_pool_geometry_stability_blocked
                and adress_rescue_attempted_without_core_pass
                and not contact_aware_rescue_attempted_without_core_pass
                else (
                    "BindingDB similarity seed expansion also failed to close the full core gate; next closure requires all-atom-style pose preservation/backmapping evidence or broader/new PDE chemistry, not claim promotion."
                    if candidate_pool_geometry_stability_blocked
                    and bindingdb_similarity_seed_attempted_without_core_pass
                    else (
                        "Contact-aware GPU rescue also failed to close geometry/stability; next closure requires all-atom-style pose preservation/backmapping evidence or new PDEB1-like chemistry, not more claim promotion."
                        if candidate_pool_geometry_stability_blocked
                        and contact_aware_rescue_attempted_without_core_pass
                        else (
                            "Generate a stronger three-bead binding candidate pool before reopening expensive all-atom promotion; existing evidence does not close the translation energy gate."
                            if binding_energy_source_pool_exhausted
                            else "Close translation-quality evidence before broad wetlab or scale-up claims."
                        )
                    )
                )
            )
        )
    )
    required_next_calculations = [row["action_code"] for row in rows]
    closure_gate_requirements = {
        "status": "pass" if translation_quality_ready else "blocked",
        "claim_promotion_allowed": translation_quality_ready,
        "expensive_lane_allowed": translation_quality_ready,
        "failed_quality_axes": failed_quality_axes,
        "missing_quality_axes": missing_quality_axes,
        "required_closed_axes": sorted({row["quality_axis"] for row in rows}),
        "required_next_calculations": required_next_calculations,
        "blocker_count": failed_evidence_count + missing_evidence_count,
        "measurement_gap_count": missing_evidence_count,
        "next_gate": "broad_translation_claim_review" if translation_quality_ready else "translation_quality_closure",
        "claim_policy": "do_not_expand_broad_translation_or_scaleup_claim_until_all_axes_close",
    }

    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_translation_quality_packet_ready",
            "target_id": target_id,
            "source_review_json": source_review_json,
            "allatom_delivery_p0_green": allatom_delivery_p0_green,
            "wetlab_final_gate_pass": wetlab_final_gate_pass,
            "commercial_hard_gate_pass": commercial_hard_gate_pass,
            "translation_quality_ready": translation_quality_ready,
            "claim_scope": "broad_translation_claim_candidate" if translation_quality_ready else "post_p0_quality_followup_only",
            "claim_promotion_allowed": translation_quality_ready,
            "claim_policy_status": "eligible_for_broad_translation_claim_review"
            if translation_quality_ready
            else "blocked_post_p0_quality_followup",
            "translation_gate_focus_status": translation_focus_status,
            "translation_gate_focus_score": review_summary.get("translation_gate_focus_score"),
            "primary_blocker": primary_blocker,
            "quality_action_count": len(rows),
            "failed_evidence_count": failed_evidence_count,
            "missing_evidence_count": missing_evidence_count,
            "warning_evidence_count": warning_evidence_count,
            "measurement_gap_count": missing_evidence_count,
            "failed_quality_axes": failed_quality_axes,
            "missing_quality_axes": missing_quality_axes,
            "best_ligand_id": best_ligand_id,
            "best_mean_min_distance_A": best_mean_min_distance_A,
            "best_binding_energy_proxy": best_binding_energy_proxy,
            "source_translation_evidence_json": source_translation_evidence_json if translation_evidence_summary else "",
            "candidate_pool_row_count": candidate_pool_row_count,
            "candidate_pool_energy_pass_count": candidate_pool_energy_pass_count,
            "candidate_pool_core_pass_count": candidate_pool_core_pass_count,
            "candidate_pool_energy_pass_unique_ligand_count": candidate_pool_energy_pass_unique_ligand_count,
            "candidate_pool_core_pass_unique_ligand_count": candidate_pool_core_pass_unique_ligand_count,
            "candidate_pool_core_like_count": candidate_pool_core_like_count,
            "external_homolog_seed_row_count": external_homolog_seed_row_count,
            "external_homolog_seed_energy_pass_count": external_homolog_seed_energy_pass_count,
            "external_homolog_seed_core_pass_count": external_homolog_seed_core_pass_count,
            "external_homolog_geomstab_rescore_row_count": external_homolog_geomstab_rescore_row_count,
            "external_homolog_geomstab_rescore_energy_pass_count": external_homolog_geomstab_rescore_energy_pass_count,
            "external_homolog_geomstab_rescore_core_pass_count": external_homolog_geomstab_rescore_core_pass_count,
            "external_homolog_adress_rescue_row_count": external_homolog_adress_rescue_row_count,
            "external_homolog_adress_rescue_energy_pass_count": external_homolog_adress_rescue_energy_pass_count,
            "external_homolog_adress_rescue_core_pass_count": external_homolog_adress_rescue_core_pass_count,
            "external_homolog_contact_rescue_row_count": external_homolog_contact_rescue_row_count,
            "external_homolog_contact_rescue_energy_pass_count": external_homolog_contact_rescue_energy_pass_count,
            "external_homolog_contact_rescue_core_pass_count": external_homolog_contact_rescue_core_pass_count,
            "external_bindingdb_similarity_row_count": external_bindingdb_similarity_row_count,
            "external_bindingdb_similarity_energy_pass_count": external_bindingdb_similarity_energy_pass_count,
            "external_bindingdb_similarity_core_pass_count": external_bindingdb_similarity_core_pass_count,
            "candidate_pool_best_binding_energy_proxy": candidate_pool_best_binding_energy_proxy,
            "candidate_pool_best_core_like_binding_energy_proxy": candidate_pool_best_core_like_binding_energy_proxy,
            "external_homolog_seed_best_binding_energy_proxy": external_homolog_seed_best_binding_energy_proxy,
            "external_homolog_geomstab_rescore_best_binding_energy_proxy": (
                external_homolog_geomstab_rescore_best_binding_energy_proxy
            ),
            "external_homolog_adress_rescue_best_binding_energy_proxy": (
                external_homolog_adress_rescue_best_binding_energy_proxy
            ),
            "external_homolog_contact_rescue_best_binding_energy_proxy": (
                external_homolog_contact_rescue_best_binding_energy_proxy
            ),
            "external_bindingdb_similarity_best_binding_energy_proxy": (
                external_bindingdb_similarity_best_binding_energy_proxy
            ),
            "candidate_pool_energy_gap_closed": candidate_pool_energy_gap_closed,
            "candidate_pool_core_gate_closed": candidate_pool_core_gate_closed,
            "binding_energy_source_pool_exhausted": binding_energy_source_pool_exhausted,
            "candidate_pool_geometry_stability_blocked": candidate_pool_geometry_stability_blocked,
            "adress_rescue_attempted_without_core_pass": adress_rescue_attempted_without_core_pass,
            "contact_aware_rescue_attempted_without_core_pass": contact_aware_rescue_attempted_without_core_pass,
            "bindingdb_similarity_seed_attempted_without_core_pass": (
                bindingdb_similarity_seed_attempted_without_core_pass
            ),
            "recommended_next_expensive_lane": recommended_next_expensive_lane,
            "expensive_lane_status": "eligible_for_review" if translation_quality_ready else "deferred_until_translation_quality_closed",
            "next_required_step": next_required_step,
        },
        "closure_gate_requirements": closure_gate_requirements,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--translation-evidence-json", default=DEFAULT_TRANSLATION_EVIDENCE_JSON)
    parser.add_argument("--out", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(
        load_json(args.review_json),
        source_review_json=args.review_json,
        translation_evidence_payload=maybe_load_json(args.translation_evidence_json),
        source_translation_evidence_json=args.translation_evidence_json,
    )
    write_artifact(args.out, "Wetlab T. cruzi PDE Translation Quality Packet", payload)
    print(args.out)


if __name__ == "__main__":
    main()
