#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_KINASE_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_kinase_retry_policy_templates_current.json"
DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"
DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_krs1_branch_review_surface_current.json"
DEFAULT_TCRUZI_KRS1_GUARDED_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.json"
DEFAULT_CATHEPSIN_K_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.json"
DEFAULT_CATHEPSIN_K_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json"
DEFAULT_SARSCOV2_MPRO_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.json"
DEFAULT_TCRUZI_PDE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_tcruzi_pde_stage6_tuning_surface_current.json"
DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON = "runs/wetlab_plpro_manual_retry_lane_current.json"
DEFAULT_PRIMARY_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_BROAD_SCREEN_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_target_retry_policy_templates_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _find_row_by_target(payload: dict[str, Any] | None, target_id: str) -> dict[str, Any]:
    wanted = _text(target_id)
    for row in ((payload or {}).get("rows", []) or []):
        if _text((row or {}).get("target_id")) == wanted:
            return dict(row or {})
    return {}


def _has_command_kind(payload: dict[str, Any] | None, command_kind: str) -> bool:
    wanted = _text(command_kind)
    for row in ((payload or {}).get("rows", []) or []):
        if _text((row or {}).get("command_kind")) == wanted:
            return True
    return False


def _stage6_candidate_row(
    *,
    target_id: str,
    tuning_summary: dict[str, Any],
    lane_summary: dict[str, Any] | None = None,
    target_class: str,
    template_label: str,
    recommended_retry_mode: str,
    default_lane_policy: str,
    companion_panel: str,
    decision_rationale: str,
    evidence_source: str,
) -> dict[str, Any]:
    lane_summary = lane_summary or {}
    selected_kind = _text(lane_summary.get("selected_command_kind"), tuning_summary.get("immediately_runnable_command_kind"))
    selected_threshold = _safe_float(lane_summary.get("selected_threshold_A"), _safe_float(tuning_summary.get("immediately_runnable_threshold_A")))
    next_required_step = _text(lane_summary.get("next_required_step"), tuning_summary.get("next_required_step"))
    return {
        "row_kind": "target_retry_policy_template",
        "target_id": target_id,
        "template_label": template_label,
        "template_scope": "guarded_stage6_tuning_candidate",
        "target_class": target_class,
        "selected_command_kind": selected_kind,
        "selected_threshold_A": selected_threshold,
        "default_lane_policy": default_lane_policy,
        "autostart_policy": "manual_review_before_any_reopen",
        "companion_panel": companion_panel,
        "recommended_retry_mode": recommended_retry_mode,
        "empirical_validated": False,
        "decision": "pause_target_autostart_and_review_retry_preset",
        "decision_rationale": decision_rationale,
        "evidence_source": evidence_source,
        "next_required_step": next_required_step,
    }


def _krs1_gate51_validated(krs1_branch_review_summary: dict[str, Any], krs1_guarded_branch_summary: dict[str, Any]) -> bool:
    branch_state = _text(
        krs1_guarded_branch_summary.get("branch_state"),
        krs1_branch_review_summary.get("branch_state"),
    )
    return bool(
        (
            _text(krs1_guarded_branch_summary.get("status")) == "wetlab_tcruzi_krs1_guarded_branch_summary_validated"
            and bool(krs1_guarded_branch_summary.get("branch_validated", False))
        )
        or (
            _text(krs1_branch_review_summary.get("status")) == "wetlab_tcruzi_krs1_branch_review_surface_ready"
            and bool(krs1_branch_review_summary.get("branch_validated", False))
        )
        or branch_state == "guarded_gate51_validated_default_lane_closed"
    )


def build_payload(
    kinase_retry_policy_templates: dict[str, Any] | None,
    lbdhodh_gate51_validation_review_surface: dict[str, Any] | None,
    lbdhodh_stage6_tuning_surface: dict[str, Any] | None = None,
    lbdhodh_exploratory_retry_lane: dict[str, Any] | None = None,
    cathepsin_k_stage6_tuning_surface: dict[str, Any] | None = None,
    cathepsin_k_exploratory_retry_lane: dict[str, Any] | None = None,
    sarscov2_mpro_stage6_tuning_surface: dict[str, Any] | None = None,
    tcruzi_pde_stage6_tuning_surface: dict[str, Any] | None = None,
    plpro_manual_retry_lane: dict[str, Any] | None = None,
    primary_hold_guard: dict[str, Any] | None = None,
    broad_screen_throughput_bridge: dict[str, Any] | None = None,
    tcruzi_krs1_branch_review_surface: dict[str, Any] | None = None,
    tcruzi_krs1_guarded_branch_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    krt = _summary(kinase_retry_policy_templates)
    lvr = _summary(lbdhodh_gate51_validation_review_surface)
    lts = _summary(lbdhodh_stage6_tuning_surface)
    lrl = _summary(lbdhodh_exploratory_retry_lane)
    cks = _summary(cathepsin_k_stage6_tuning_surface)
    ckl = _summary(cathepsin_k_exploratory_retry_lane)
    mpros = _summary(sarscov2_mpro_stage6_tuning_surface)
    pdes = _summary(tcruzi_pde_stage6_tuning_surface)
    pml = _summary(plpro_manual_retry_lane)
    phg_row = _find_row_by_target(primary_hold_guard, "Cathepsin K")
    btb = _summary(broad_screen_throughput_bridge)
    krs1_review = _summary(tcruzi_krs1_branch_review_surface)
    krs1_guarded = _summary(tcruzi_krs1_guarded_branch_summary)
    kinase_rows = [dict(row or {}) for row in ((kinase_retry_policy_templates or {}).get("rows", []) or [])]

    rows = list(kinase_rows)
    dhodh_validated = bool(
        _text(lvr.get("status")) == "wetlab_lbdhodh_gate51_validation_review_surface_ready"
        and bool(lvr.get("gate51_validated", False))
    )
    if dhodh_validated:
        rows.append(
            {
                "row_kind": "target_retry_policy_template",
                "target_id": _text(lvr.get("target_id")),
                "template_label": "gate51_branch_only_empirical",
                "template_scope": "empirical_validation_promoted",
                "target_class": "pathogen_metabolic_enzyme",
                "selected_command_kind": _text(lvr.get("validated_command_kind"), lrl.get("selected_command_kind"), lts.get("immediately_runnable_command_kind")),
                "selected_threshold_A": _safe_float(lvr.get("validated_threshold_A"), _safe_float(lts.get("recommended_observed_threshold_A"), 5.1)),
                "default_lane_policy": "keep_default_closed_branch_gate51_only",
                "autostart_policy": "manual_review_before_any_reopen",
                "companion_panel": "pathogen DHODH comparator panel",
                "recommended_retry_mode": "gate51_validated_branch_only",
                "empirical_validated": True,
                "decision": _text(lvr.get("decision")),
                "decision_rationale": _text(lvr.get("decision_rationale")),
                "evidence_source": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
                "next_required_step": _text(lvr.get("next_required_step")),
            }
        )

    krs1_validated = _krs1_gate51_validated(krs1_review, krs1_guarded)
    if krs1_validated:
        rows.append(
            {
                "row_kind": "target_retry_policy_template",
                "target_id": _text(krs1_guarded.get("target_id"), krs1_review.get("target_id"), default="T. cruzi KRS1"),
                "template_label": "gate51_branch_only_empirical",
                "template_scope": "empirical_validation_promoted",
                "target_class": "pathogen_trna_synthetase",
                "selected_command_kind": _text(
                    krs1_guarded.get("selected_command_kind"),
                    krs1_review.get("selected_command_kind"),
                    krs1_review.get("exploratory_retry_selected_command_kind"),
                    default="throughput_preflight_tuned_gate51",
                ),
                "selected_threshold_A": _safe_float(
                    krs1_guarded.get("selected_threshold_A"),
                    _safe_float(
                        krs1_review.get("selected_threshold_A"),
                        _safe_float(krs1_review.get("exploratory_retry_selected_threshold_A"), 5.1),
                    ),
                ),
                "default_lane_policy": "keep_default_closed_branch_gate51_only",
                "autostart_policy": "manual_review_before_any_reopen",
                "companion_panel": "LRRK2 successor broad lane",
                "recommended_retry_mode": "gate51_validated_branch_only",
                "empirical_validated": True,
                "decision": "promote_gate51_validated_keep_default_closed",
                "decision_rationale": _text(
                    krs1_review.get("next_required_step"),
                    krs1_guarded.get("next_required_step"),
                    default=(
                        "The guarded T. cruzi KRS1 gate5.1 branch is fully resolved and validated, so the default lane stays "
                        "closed while LRRK2 continues as the successor broad lane."
                    ),
                ),
                "evidence_source": "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md",
                "next_required_step": _text(krs1_guarded.get("next_required_step"), krs1_review.get("next_required_step")),
            }
        )

    if _text(pml.get("status")) == "wetlab_plpro_manual_retry_lane_ready" and bool(pml.get("ready_for_manual_retry", False)):
        rows.append(
            {
                "row_kind": "target_retry_policy_template",
                "target_id": _text(pml.get("target_id")),
                "template_label": "guarded_gate55_candidate",
                "template_scope": "guarded_manual_retry_candidate",
                "target_class": "viral_protease",
                "selected_command_kind": _text(pml.get("selected_command_kind"), default="throughput_preflight_tuned_gate55"),
                "selected_threshold_A": 5.5,
                "default_lane_policy": "keep_default_closed_guarded_gate55_retry_only",
                "autostart_policy": "manual_review_before_any_reopen",
                "companion_panel": "host DUB sanity panel",
                "recommended_retry_mode": _text(pml.get("recommended_retry_mode"), default="guarded_manual_preflight_retry"),
                "empirical_validated": False,
                "decision": _text(pml.get("retry_handoff_decision"), default="pause_auto_start"),
                "decision_rationale": "Guarded manual retry lane exists and remains the safest non-kinase retry path while the default lane stays blocked after repeated auto-holds.",
                "evidence_source": "runs/wetlab_plpro_manual_retry_lane_current.md",
                "next_required_step": _text(pml.get("next_required_step")),
            }
        )

    cathepsin_gate45_candidate = (
        _text(cks.get("status")) == "wetlab_cathepsin_k_stage6_tuning_surface_ready"
        and _text(ckl.get("status")).startswith("wetlab_cathepsin_k_exploratory_retry_lane_")
        and _text(phg_row.get("recommended_policy_action")) == "pause_target_autostart_and_review_retry_preset"
    )
    if cathepsin_gate45_candidate:
        rows.append(
            _stage6_candidate_row(
                target_id="Cathepsin K",
                tuning_summary=cks,
                lane_summary=ckl,
                target_class="acidic_protease",
                template_label="guarded_gate45_candidate",
                recommended_retry_mode="guarded_tuned_gate45_candidate",
                default_lane_policy="pause_default_lane_review_gate45_candidate",
                companion_panel="related cathepsin selectivity panel",
                decision_rationale="Cathepsin K is guard-blocked after repeated default-lane holds and now has a dedicated stage6 tuning surface plus a gate4.5 retry lane for guarded review.",
                evidence_source="runs/wetlab_cathepsin_k_stage6_tuning_surface_current.md",
            )
        )

    if _text(mpros.get("status")) == "wetlab_sarscov2_mpro_stage6_tuning_surface_ready":
        rows.append(
            _stage6_candidate_row(
                target_id="SARS-CoV-2 Mpro",
                tuning_summary=mpros,
                target_class="viral_protease",
                template_label="guarded_gate45_candidate",
                recommended_retry_mode="guarded_tuned_gate45_candidate",
                default_lane_policy="keep_default_closed_branch_gate45_only",
                companion_panel="viral protease stage6 review lane",
                decision_rationale="Stage1 mapping is now clean for SARS-CoV-2 Mpro, and the persistent failure mode is stage6, so this target should move out of mapping-fix and into a gate4.5 tuning branch.",
                evidence_source="runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.md",
            )
        )

    if _text(pdes.get("status")) == "wetlab_tcruzi_pde_stage6_tuning_surface_ready":
        rows.append(
            _stage6_candidate_row(
                target_id="T. cruzi PDE",
                tuning_summary=pdes,
                target_class="pathogen_phosphodiesterase",
                template_label="guarded_gate51_candidate",
                recommended_retry_mode="guarded_tuned_gate51_candidate",
                default_lane_policy="keep_default_closed_branch_gate51_only",
                companion_panel="pathogen PDE stage6 review lane",
                decision_rationale="Stage1 mapping is now clean for T. cruzi PDE, and the persistent failure mode is stage6, so this target should move out of mapping-fix and into a gate5.1 tuning branch.",
                evidence_source="runs/wetlab_tcruzi_pde_stage6_tuning_surface_current.md",
            )
        )

    empirical_validated_count = sum(1 for row in rows if bool(row.get("empirical_validated", False)))
    target_count = len(rows)
    non_kinase_rows = [
        row
        for row in rows
        if _text(row.get("row_kind")) != "kinase_retry_policy_template"
        and _text(row.get("target_class")) != "kinase"
    ]
    focus_row = next(
        (
            row
            for row in rows
            if _text(row.get("target_id")) == "T. cruzi KRS1"
            and _text(row.get("template_label")) == "gate51_branch_only_empirical"
            and bool(row.get("empirical_validated", False))
        ),
        next(
            (row for row in rows if _text(row.get("target_id")) == _text(lvr.get("target_id")) and dhodh_validated),
            rows[0] if rows else {},
        ),
    )

    next_required_step = _text(
        focus_row.get("next_required_step"),
        krt.get("next_required_step"),
        default="Use the validated retry policy templates before reopening any default broad-screen lane.",
    )

    return {
        "summary": {
            "status": "wetlab_target_retry_policy_templates_ready",
            "template_target_count": target_count,
            "empirical_validated_target_count": empirical_validated_count,
            "validated_branch_only_target_count": sum(
                1 for row in rows if "branch_only" in _text(row.get("template_label"))
            ),
            "non_kinase_template_target_count": len(non_kinase_rows),
            "non_kinase_empirical_validated_target_count": sum(
                1 for row in non_kinase_rows if bool(row.get("empirical_validated", False))
            ),
            "guarded_gate55_candidate_target_count": sum(
                1 for row in rows if _text(row.get("template_label")) == "guarded_gate55_candidate"
            ),
            "guarded_gate51_candidate_target_count": sum(
                1 for row in rows if _text(row.get("template_label")) == "guarded_gate51_candidate"
            ),
            "guarded_gate45_candidate_target_count": sum(
                1 for row in rows if _text(row.get("template_label")) == "guarded_gate45_candidate"
            ),
            "focus_target_id": _text(focus_row.get("target_id")),
            "focus_template_label": _text(focus_row.get("template_label")),
            "focus_selected_command_kind": _text(focus_row.get("selected_command_kind")),
            "focus_selected_threshold_A": _safe_float(focus_row.get("selected_threshold_A")),
            "next_required_step": next_required_step,
        },
        "structured": {
            "kinase_retry_policy_templates_artifact": "runs/wetlab_kinase_retry_policy_templates_current.md",
            "lbdhodh_gate51_validation_review_surface_artifact": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
            "lbdhodh_stage6_tuning_surface_artifact": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
            "tcruzi_krs1_branch_review_surface_artifact": "runs/wetlab_tcruzi_krs1_branch_review_surface_current.md",
            "tcruzi_krs1_guarded_branch_summary_artifact": "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md",
            "cathepsin_k_stage6_tuning_surface_artifact": "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.md",
            "sarscov2_mpro_stage6_tuning_surface_artifact": "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.md",
            "tcruzi_pde_stage6_tuning_surface_artifact": "runs/wetlab_tcruzi_pde_stage6_tuning_surface_current.md",
            "plpro_manual_retry_lane_artifact": "runs/wetlab_plpro_manual_retry_lane_current.md",
            "broad_screen_throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build generalized target retry policy templates.")
    parser.add_argument("--kinase-retry-policy-templates-json", default=DEFAULT_KINASE_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--lbdhodh-stage6-tuning-surface-json", default=DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--lbdhodh-exploratory-retry-lane-json", default=DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--tcruzi-krs1-branch-review-surface-json", default=DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-krs1-guarded-branch-summary-json", default=DEFAULT_TCRUZI_KRS1_GUARDED_BRANCH_SUMMARY_JSON)
    parser.add_argument("--cathepsin-k-stage6-tuning-surface-json", default=DEFAULT_CATHEPSIN_K_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--cathepsin-k-exploratory-retry-lane-json", default=DEFAULT_CATHEPSIN_K_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--sarscov2-mpro-stage6-tuning-surface-json", default=DEFAULT_SARSCOV2_MPRO_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-stage6-tuning-surface-json", default=DEFAULT_TCRUZI_PDE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--plpro-manual-retry-lane-json", default=DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--primary-hold-guard-json", default=DEFAULT_PRIMARY_HOLD_GUARD_JSON)
    parser.add_argument("--broad-screen-throughput-bridge-json", default=DEFAULT_BROAD_SCREEN_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Target Retry Policy Templates",
        build_payload(
            load_json(args.kinase_retry_policy_templates_json),
            maybe_load_json(args.lbdhodh_gate51_validation_review_surface_json),
            maybe_load_json(args.lbdhodh_stage6_tuning_surface_json),
            maybe_load_json(args.lbdhodh_exploratory_retry_lane_json),
            maybe_load_json(args.cathepsin_k_stage6_tuning_surface_json),
            maybe_load_json(args.cathepsin_k_exploratory_retry_lane_json),
            maybe_load_json(args.sarscov2_mpro_stage6_tuning_surface_json),
            maybe_load_json(args.tcruzi_pde_stage6_tuning_surface_json),
            maybe_load_json(args.plpro_manual_retry_lane_json),
            maybe_load_json(args.primary_hold_guard_json),
            maybe_load_json(args.broad_screen_throughput_bridge_json),
            maybe_load_json(args.tcruzi_krs1_branch_review_surface_json),
            maybe_load_json(args.tcruzi_krs1_guarded_branch_summary_json),
        ),
    )


if __name__ == "__main__":
    main()
