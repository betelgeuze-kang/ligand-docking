#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import rows_by_family, write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_GPCR_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_ION_KIN_JSON = "runs/cross_family_locked_decoy_shadow_decision_current.json"
DEFAULT_IDP_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_IDP_BROADER_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_CA2_BURNDOWN_JSON = "runs/ca2_pending_burndown_console_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PXR_BURNDOWN_JSON = "runs/pxr_pending_burndown_console_current.json"
DEFAULT_TRANSPORTER_BLOCKER_JSON = "runs/transporter_authoritative_apply_blocker_decomposition_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_OUT_JSON = "runs/domain_completion_status_current.json"
DEFAULT_OUT_CSV = "runs/domain_completion_status_current.csv"
DEFAULT_OUT_MD = "runs/domain_completion_status_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _join_signal_parts(parts: list[str]) -> str:
    return "; ".join(part for part in parts if part)


def build_payload(
    commercialization: dict[str, Any],
    gpcr: dict[str, Any],
    ion_kin: dict[str, Any],
    idp: dict[str, Any],
    idp_broader_scaffold: dict[str, Any],
    idp_commercial_pretest: dict[str, Any],
    ca2_readiness: dict[str, Any],
    ca2_burndown: dict[str, Any],
    pxr_readiness: dict[str, Any],
    pxr_burndown: dict[str, Any],
    transporter_blocker: dict[str, Any],
    transporter_dashboard: dict[str, Any],
    transporter_seed_row_board: dict[str, Any],
    idp_commercial_pretest_decision: dict[str, Any] | None = None,
    idp_broader_shadow_result: dict[str, Any] | None = None,
    idp_broader_shadow_decision: dict[str, Any] | None = None,
    idp_broader_promotion_resolution: dict[str, Any] | None = None,
    idp_one_wider_repeatability_packet: dict[str, Any] | None = None,
    idp_one_wider_repeatability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    commercial_rows = rows_by_family(commercialization)
    gpcr_s = dict(gpcr.get("summary", {}) or {})
    ion_kin_s = dict(ion_kin.get("summary", {}) or {})
    idp_s = dict(idp.get("summary", {}) or {})
    idp_scaffold_s = dict((idp_broader_scaffold or {}).get("summary", {}) or {})
    idp_pretest_s = dict((idp_commercial_pretest or {}).get("summary", {}) or {})
    idp_pretest_decision_s = dict((idp_commercial_pretest_decision or {}).get("summary", {}) or {})
    idp_broader_result_s = dict((idp_broader_shadow_result or {}).get("summary", {}) or {})
    idp_broader_decision_s = dict((idp_broader_shadow_decision or {}).get("summary", {}) or {})
    idp_broader_promotion_resolution_s = dict((idp_broader_promotion_resolution or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_packet_s = dict((idp_one_wider_repeatability_packet or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_result_s = dict((idp_one_wider_repeatability_result or {}).get("summary", {}) or {})
    idp_repeatability_s = idp_one_wider_repeatability_result_s or idp_one_wider_repeatability_packet_s
    idp_additional_anchor_backed_target_count = int(idp_pretest_decision_s.get("additional_anchor_backed_target_count", 0) or 0)
    idp_same_scope_reproducibility_confirmed = bool(idp_pretest_decision_s.get("same_scope_reproducibility_confirmed", False))
    idp_page4_candidate_ready_now = bool(idp_pretest_decision_s.get("page4_candidate_ready_now", False))
    ca2r_s = dict(ca2_readiness.get("summary", {}) or {})
    ca2b_s = dict(ca2_burndown.get("summary", {}) or {})
    pxrr_s = dict(pxr_readiness.get("summary", {}) or {})
    pxrb_s = dict(pxr_burndown.get("summary", {}) or {})
    tblock_s = dict(transporter_blocker.get("summary", {}) or {})
    tdash_s = dict(transporter_dashboard.get("summary", {}) or {})
    tseed_s = dict(transporter_seed_row_board.get("summary", {}) or {})
    transporter_top_blocker_signal = str(tseed_s.get("top_blocker_signal", tblock_s.get("top_blocker_signal", "")) or "").strip()
    transporter_glut1_second_wave_ready = bool(tdash_s.get("glut1_second_wave_source_confirmation_ready", False))
    transporter_glut1_second_wave_artifact = str(tdash_s.get("glut1_second_wave_source_confirmation_packet_artifact", "") or "").strip()
    transporter_glut1_primary_focus_ligand = str(
        tdash_s.get("glut1_second_wave_source_confirmation_primary_focus_ligand", "") or ""
    ).strip()
    transporter_glut1_direct_binding_count_explicit = "glut1_direct_quantitative_binding_count" in tdash_s
    transporter_glut1_direct_binding_count = int(tdash_s.get("glut1_direct_quantitative_binding_count", 0) or 0)
    transporter_glut1_exact_target_pair_count_explicit = "glut1_exact_target_pair_activity_count" in tdash_s
    transporter_glut1_exact_target_pair_count = int(tdash_s.get("glut1_exact_target_pair_activity_count", 0) or 0)
    transporter_glut1_structured_pair_absent_count_explicit = "glut1_structured_pair_absent_count" in tdash_s
    transporter_glut1_structured_pair_absent_count = int(tdash_s.get("glut1_structured_pair_absent_count", 0) or 0)
    transporter_has_glut1_second_wave_source_confirmation = bool(
        transporter_glut1_second_wave_ready
        or transporter_glut1_second_wave_artifact
        or transporter_glut1_primary_focus_ligand
        or transporter_glut1_direct_binding_count_explicit
        or transporter_glut1_exact_target_pair_count_explicit
        or transporter_glut1_structured_pair_absent_count_explicit
    )
    transporter_completion_note = (
        f"manual-verdict phase is complete; blocker-closure and AQP1-first seed-row promotion are active, and GLUT1 second-wave source confirmation is staged around {transporter_glut1_primary_focus_ligand}."
        if transporter_has_glut1_second_wave_source_confirmation and transporter_glut1_primary_focus_ligand
        else
        "manual-verdict phase is complete; blocker-closure and AQP1-first seed-row promotion are active, and GLUT1 second-wave source confirmation is staged."
        if transporter_has_glut1_second_wave_source_confirmation
        else
        "manual-verdict phase is complete; blocker-closure and seed-row promotion are active"
    )
    transporter_strongest_signal = _join_signal_parts(
        [
            f"manual_backlog_cleared={tblock_s.get('manual_review_backlog_cleared', '')}",
            f"current_phase={tdash_s.get('current_phase', '')}",
            f"today_seed_target={tseed_s.get('today_seed_target', '')}",
            transporter_top_blocker_signal,
            (
                f"glut1_second_wave_source_confirmation_ready={transporter_glut1_second_wave_ready}"
                if transporter_has_glut1_second_wave_source_confirmation
                and "glut1_second_wave_source_confirmation_ready" in tdash_s
                else ""
            ),
            (
                f"glut1_second_wave_primary_focus_ligand={transporter_glut1_primary_focus_ligand}"
                if transporter_glut1_primary_focus_ligand
                else ""
            ),
            (
                f"glut1_direct_quantitative_binding_count={transporter_glut1_direct_binding_count}"
                if transporter_glut1_direct_binding_count_explicit
                else ""
            ),
            (
                f"glut1_exact_target_pair_activity_count={transporter_glut1_exact_target_pair_count}"
                if transporter_glut1_exact_target_pair_count_explicit
                else ""
            ),
            (
                f"glut1_structured_pair_absent_count={transporter_glut1_structured_pair_absent_count}"
                if transporter_glut1_structured_pair_absent_count_explicit
                else ""
            ),
        ]
    )
    transporter_next_step_clause = (
        "use transporter for blocker-closure and AQP1-first seed-row promotion; keep GLUT1 second-wave, and when it opens, use "
        f"{transporter_glut1_second_wave_artifact} with {transporter_glut1_primary_focus_ligand} as the first source-confirmation lead while keeping transporter rows non-authoritative."
        if transporter_glut1_second_wave_artifact and transporter_glut1_primary_focus_ligand
        else
        "use transporter for blocker-closure and AQP1-first seed-row promotion; keep GLUT1 second-wave, and when it opens, start with "
        f"{transporter_glut1_primary_focus_ligand} as the first explicit source-confirmation lead while keeping transporter rows non-authoritative."
        if transporter_glut1_primary_focus_ligand
        else "use transporter for blocker-closure and AQP1-first seed-row promotion."
    )

    rows = [
        {
            "family": "gpcr",
            "score": commercial_rows["gpcr"]["score"],
            "stage": commercial_rows["gpcr"]["stage"],
            "status": commercial_rows["gpcr"]["status"],
            "completion_note": "locked-decoy apply-safe endpoint is ready; router remains blocked",
            "current_scope": commercial_rows["gpcr"]["claim_safe_scope"],
            "strongest_signal": f"core_pr_delta={gpcr_s.get('core_pr_delta_vs_baseline', '')}; chembl50_ef1_delta={gpcr_s.get('chembl50_ef1_delta_vs_baseline', '')}",
            "remaining_blocker": commercial_rows["gpcr"]["primary_blocker"],
            "source_artifact": commercial_rows["gpcr"]["source_artifact"],
        },
        {
            "family": "ion_channel",
            "score": commercial_rows["ion_channel"]["score"],
            "stage": commercial_rows["ion_channel"]["stage"],
            "status": commercial_rows["ion_channel"]["status"],
            "completion_note": "measured noop-shadow family is stable on the commercial lane",
            "current_scope": commercial_rows["ion_channel"]["claim_safe_scope"],
            "strongest_signal": f"candidate_fail_count={ion_kin_s.get('candidate_fail_count', '')}; max_abs_delta_pr_auc={ion_kin_s.get('max_abs_delta_pr_auc', '')}",
            "remaining_blocker": commercial_rows["ion_channel"]["primary_blocker"],
            "source_artifact": commercial_rows["ion_channel"]["source_artifact"],
        },
        {
            "family": "kinase",
            "score": commercial_rows["kinase"]["score"],
            "stage": commercial_rows["kinase"]["stage"],
            "status": commercial_rows["kinase"]["status"],
            "completion_note": "measured noop-shadow family is stable on the commercial lane",
            "current_scope": commercial_rows["kinase"]["claim_safe_scope"],
            "strongest_signal": f"candidate_fail_count={ion_kin_s.get('candidate_fail_count', '')}; max_abs_delta_pr_auc={ion_kin_s.get('max_abs_delta_pr_auc', '')}",
            "remaining_blocker": commercial_rows["kinase"]["primary_blocker"],
            "source_artifact": commercial_rows["kinase"]["source_artifact"],
        },
        {
            "family": "idp",
            "score": commercial_rows["idp"]["score"],
            "stage": commercial_rows["idp"]["stage"],
            "status": (
                str(idp_broader_promotion_resolution_s.get("status", "")).strip()
                or str(idp_broader_decision_s.get("status", "")).strip()
                or commercial_rows["idp"]["status"]
            ),
            "completion_note": (
                "shadow-safe controlled commercial-pretest is retained; one wider shadow-safe lane is admitted on the frozen validated-7-plus-PAGE4 roster, and bounded repeatability is now the active evidence step before any further promotion review"
                if idp_broader_promotion_resolution_s and idp_repeatability_s
                else
                "shadow-safe controlled commercial-pretest is retained; one wider shadow-safe lane is now admitted on the frozen validated-7-plus-PAGE4 roster, but broader_full_idp_promotion and commercialization beyond that bounded lane remain blocked"
                if idp_broader_promotion_resolution_s
                else
                "shadow-safe controlled commercial-pretest is retained; the first true broader shadow-only rerun with PAGE4 passed cleanly, and only explicit promotion review remains before any wider lane change"
                if idp_broader_decision_s
                else
                "shadow-safe controlled commercial-pretest is retained; true broader rerun is not launch-ready because no additional anchor-backed targets exist yet"
                if idp_pretest_decision_s and idp_additional_anchor_backed_target_count == 0
                else "shadow-safe controlled commercial-pretest is retained; broader promotion is now review-required rather than auto-approved"
                if idp_pretest_decision_s
                else "subset-safe is ready and a controlled shadow-only commercial-pretest packet is now defined"
            ),
            "current_scope": (
                "one wider shadow-safe lane admitted on the frozen validated-7-plus-PAGE4 roster under the same no-override guardrails"
                if idp_broader_promotion_resolution_s
                else "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis"
            ),
            "strongest_signal": (
                f"wider_lane_admitted={idp_broader_promotion_resolution_s.get('wider_shadow_safe_lane_admitted', False)}; "
                f"repeatability_status={idp_repeatability_s.get('status', '')}; "
                f"frozen_total_target_count={idp_broader_promotion_resolution_s.get('frozen_total_target_count', 0)}; "
                f"page4_fold_pass={idp_broader_promotion_resolution_s.get('page4_fold_pass', False)}; "
                f"tau_k18_fold_pass={idp_broader_promotion_resolution_s.get('tau_k18_fold_pass', False)}; "
                f"shadow_safe={idp_broader_promotion_resolution_s.get('shadow_safe_retained', False)}"
                if idp_broader_promotion_resolution_s and idp_repeatability_s
                else
                f"wider_lane_admitted={idp_broader_promotion_resolution_s.get('wider_shadow_safe_lane_admitted', False)}; "
                f"frozen_total_target_count={idp_broader_promotion_resolution_s.get('frozen_total_target_count', 0)}; "
                f"page4_fold_pass={idp_broader_promotion_resolution_s.get('page4_fold_pass', False)}; "
                f"tau_k18_fold_pass={idp_broader_promotion_resolution_s.get('tau_k18_fold_pass', False)}; "
                f"shadow_safe={idp_broader_promotion_resolution_s.get('shadow_safe_retained', False)}"
                if idp_broader_promotion_resolution_s
                else
                f"broader_shadow_pass_folds={idp_broader_decision_s.get('corrected_pass_folds', 0)}/"
                f"{idp_broader_decision_s.get('fold_count', 0)}; "
                f"page4_fold_pass={idp_broader_decision_s.get('page4_fold_pass', False)}; "
                f"tau_k18_fold_pass={idp_broader_decision_s.get('tau_k18_fold_pass', False)}; "
                f"shadow_safe={idp_broader_decision_s.get('shadow_safe_retained', False)}"
                if idp_broader_decision_s
                else
                f"folds={idp_pretest_decision_s.get('corrected_pass_folds', idp_s.get('corrected_pass_folds', ''))}/"
                f"{idp_pretest_decision_s.get('fold_count', idp_s.get('fold_count', ''))}; "
                f"mask={idp_pretest_decision_s.get('default_feature_mask', idp_s.get('default_feature_mask', ''))}; "
                f"broader_scaffold={idp_scaffold_s.get('controlled_target_count', 0)}; "
                f"pretest_status={idp_pretest_decision_s.get('status', idp_pretest_s.get('status', '')) or bool(idp_pretest_s)}; "
                f"shadow_safe={idp_pretest_decision_s.get('shadow_safe_retained', False)}"
            ),
            "remaining_blocker": (
                str(idp_broader_promotion_resolution_s.get("blocker_reason", "")).strip()
                or
                str(idp_broader_decision_s.get("blocker_reason", "")).strip()
                or str(idp_pretest_decision_s.get("blocker_reason", "")).strip()
                or commercial_rows["idp"]["primary_blocker"]
            ),
            "source_artifact": (
                "runs/idp_one_wider_shadow_repeatability_result_current.md"
                if idp_one_wider_repeatability_result_s
                else
                "runs/idp_one_wider_shadow_repeatability_packet_current.md"
                if idp_one_wider_repeatability_packet_s
                else
                "runs/idp_broader_promotion_resolution_current.md"
                if idp_broader_promotion_resolution_s
                else
                "runs/idp_broader_shadow_decision_current.md"
                if idp_broader_decision_s
                else
                "runs/idp_commercial_pretest_decision_current.md"
                if idp_pretest_decision_s
                else "runs/idp_commercial_pretest_packet_current.md"
                if idp_pretest_s
                else commercial_rows["idp"]["source_artifact"]
            ),
        },
        {
            "family": "non_kinase_enzyme_ca2",
            "score": commercial_rows["non_kinase_enzyme_ca2"]["score"],
            "stage": commercial_rows["non_kinase_enzyme_ca2"]["stage"],
            "status": commercial_rows["non_kinase_enzyme_ca2"]["status"],
            "completion_note": "partial-authoritative binder tranche is ready; negatives remain review-only",
            "current_scope": commercial_rows["non_kinase_enzyme_ca2"]["claim_safe_scope"],
            "strongest_signal": f"ready_rows={ca2r_s.get('ready_row_count', '')}; confirmed_commits={ca2b_s.get('confirmed_commit_count', '')}",
            "remaining_blocker": commercial_rows["non_kinase_enzyme_ca2"]["primary_blocker"],
            "source_artifact": commercial_rows["non_kinase_enzyme_ca2"]["source_artifact"],
        },
        {
            "family": "nuclear_receptor_pxr",
            "score": commercial_rows["nuclear_receptor_pxr"]["score"],
            "stage": commercial_rows["nuclear_receptor_pxr"]["stage"],
            "status": commercial_rows["nuclear_receptor_pxr"]["status"],
            "completion_note": "strongest expansion family; partial-authoritative rows are mostly ready",
            "current_scope": commercial_rows["nuclear_receptor_pxr"]["claim_safe_scope"],
            "strongest_signal": f"ready_rows={pxrr_s.get('ready_for_apply_row_count', '')}; confirmed_commits={pxrb_s.get('confirmed_commit_count', '')}",
            "remaining_blocker": commercial_rows["nuclear_receptor_pxr"]["primary_blocker"],
            "source_artifact": commercial_rows["nuclear_receptor_pxr"]["source_artifact"],
        },
        {
            "family": "transporter",
            "score": commercial_rows["transporter"]["score"],
            "stage": commercial_rows["transporter"]["stage"],
            "status": commercial_rows["transporter"]["status"],
            "completion_note": transporter_completion_note,
            "current_scope": commercial_rows["transporter"]["claim_safe_scope"],
            "strongest_signal": transporter_strongest_signal,
            "remaining_blocker": commercial_rows["transporter"]["primary_blocker"],
            "source_artifact": "runs/transporter_seed_row_promotion_board_current.md" if tseed_s else commercial_rows["transporter"]["source_artifact"],
        },
    ]
    summary = {
        "family_count": len(rows),
        "core_commercial_lane_score": commercialization["summary"]["core_commercial_lane_score"],
        "all_category_expansion_score": commercialization["summary"]["all_category_expansion_score"],
        "run_now_ready_count": sum(1 for row in rows if row["family"] in {"gpcr", "ion_channel", "kinase"}),
        "subset_safe_count": sum(1 for row in rows if row["family"] == "idp"),
        "partial_authoritative_count": sum(1 for row in rows if row["family"] in {"non_kinase_enzyme_ca2", "nuclear_receptor_pxr"}),
        "manual_review_or_blocker_closure_count": sum(1 for row in rows if row["family"] == "transporter"),
        "next_required_step": (
            str(idp_repeatability_s.get("next_required_step", "")).strip()
            if idp_broader_promotion_resolution_s and idp_repeatability_s
            else
            "Keep GPCR, ion_channel, and kinase within their current safe scope; retain IDP on the admitted one-wider shadow-safe lane only, keep broader_full_idp_promotion blocked, and do not widen the roster or claim commercialization beyond that bounded lane; use CA2/PXR for evidence closure; "
            f"{transporter_next_step_clause}"
            if idp_broader_promotion_resolution_s
            else
            "Keep GPCR, ion_channel, and kinase within their current safe scope; retain IDP on the controlled commercial-pretest lane, record that the first broader shadow-only rerun with PAGE4 passed cleanly, keep broader promotion blocked, and reopen only explicit promotion review; use CA2/PXR for evidence closure; "
            f"{transporter_next_step_clause}"
            if idp_broader_decision_s
            else
            "Keep GPCR, ion_channel, and kinase within their current safe scope; retain IDP on the controlled commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 quantitative anchor replacement before any true broader rerun; use CA2/PXR for evidence closure; "
            f"{transporter_next_step_clause}"
            if idp_pretest_decision_s and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0 and idp_page4_candidate_ready_now
            else
            "Keep GPCR, ion_channel, and kinase within their current safe scope; retain IDP on the controlled commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 manual-confirmation console before any true broader rerun; use CA2/PXR for evidence closure; "
            f"{transporter_next_step_clause}"
            if idp_pretest_decision_s and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0
            else
            "Keep GPCR, ion_channel, and kinase within their current safe scope; retain IDP on the controlled commercial-pretest lane, keep broader promotion blocked, and do not label the next IDP run broader yet; either approve one same-scope process check on the validated 7-target literature-anchor subset or curate at least one additional anchor-backed target first; use CA2/PXR for evidence closure; "
            f"{transporter_next_step_clause}"
            if idp_pretest_decision_s and idp_additional_anchor_backed_target_count == 0
            else
            "Keep GPCR, ion_channel, and kinase within their current safe scope; retain IDP on the controlled commercial-pretest lane, keep broader promotion blocked pending explicit broader-shadow review, then consider one broader full-IDP shadow rerun under the same no-override guardrails; use CA2/PXR for evidence closure; "
            f"{transporter_next_step_clause}"
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Domain Completion Status",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        f"- run_now_ready_count: `{s['run_now_ready_count']}`",
        f"- subset_safe_count: `{s['subset_safe_count']}`",
        f"- partial_authoritative_count: `{s['partial_authoritative_count']}`",
        f"- manual_review_or_blocker_closure_count: `{s['manual_review_or_blocker_closure_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Families",
        "",
        "| family | score | stage | status | completion_note | current_scope | strongest_signal | remaining_blocker | source_artifact |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['score']} | `{row['stage']}` | `{row['status']}` | {row['completion_note']} | "
            f"`{row['current_scope']}` | `{row['strongest_signal']}` | {row['remaining_blocker']} | `{row['source_artifact']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single current-status view across all protein domains.")
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--gpcr-json", default=DEFAULT_GPCR_JSON)
    parser.add_argument("--ion-kin-json", default=DEFAULT_ION_KIN_JSON)
    parser.add_argument("--idp-json", default=DEFAULT_IDP_JSON)
    parser.add_argument("--idp-broader-scaffold-json", default=DEFAULT_IDP_BROADER_SCAFFOLD_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-commercial-pretest-decision-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--idp-broader-shadow-result-json", default=DEFAULT_IDP_BROADER_SHADOW_RESULT_JSON)
    parser.add_argument("--idp-broader-shadow-decision-json", default=DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--idp-one-wider-repeatability-packet-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON)
    parser.add_argument("--idp-one-wider-repeatability-result-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--ca2-burndown-json", default=DEFAULT_CA2_BURNDOWN_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--pxr-burndown-json", default=DEFAULT_PXR_BURNDOWN_JSON)
    parser.add_argument("--transporter-blocker-json", default=DEFAULT_TRANSPORTER_BLOCKER_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commercialization_json),
        _load_json(args.gpcr_json),
        _load_json(args.ion_kin_json),
        _load_json(args.idp_json),
        _load_json(args.idp_broader_scaffold_json),
        _load_json(args.idp_commercial_pretest_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.ca2_burndown_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.pxr_burndown_json),
        _load_json(args.transporter_blocker_json),
        _load_json(args.transporter_dashboard_json),
        _load_json(args.transporter_seed_row_board_json),
        _maybe_load_json(args.idp_commercial_pretest_decision_json),
        _maybe_load_json(args.idp_broader_shadow_result_json),
        _maybe_load_json(args.idp_broader_shadow_decision_json),
        _maybe_load_json(args.idp_broader_promotion_resolution_json),
        _maybe_load_json(args.idp_one_wider_repeatability_packet_json),
        _maybe_load_json(args.idp_one_wider_repeatability_result_json),
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
