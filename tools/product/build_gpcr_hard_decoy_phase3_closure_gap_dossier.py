#!/usr/bin/env python3
"""Build the GPCR hard-decoy Phase 3 closure gap dossier.

Read-only: this consolidates the official suite gate, the current-fit upper
bound probe, target-heldout diagnostics, candidate sweep, and replay
materialization readiness into one fail-closed Phase 3 status packet. It does
not run scoring, regenerate decoys, relax thresholds, or promote a claim.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OFFICIAL_SUITE_JSON = "runs/gpcr_hard_decoy_suite_current.json"
DEFAULT_CURRENT_FIT_PROBE_JSON = "runs/gpcr_hard_decoy_current_fit_closure_probe_current.json"
DEFAULT_CANDIDATE_SWEEP_JSON = "runs/gpcr_hard_decoy_candidate_sweep_current.json"
DEFAULT_MATERIALIZATION_READINESS_JSON = "runs/gpcr_hard_decoy_replay_materialization_readiness_current.json"
DEFAULT_ADORA2A_RESCUE_JSON = "runs/gpcr_hard_decoy_adora2a_neutral_rescue_probe_current.json"
DEFAULT_ADORA2A_PREREGISTERED_REPLAY_JSON = (
    "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json"
)
DEFAULT_CLAIM_UNLOCK_AUDIT_JSON = "runs/gpcr_hard_decoy_claim_unlock_audit_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_phase3_closure_gap_dossier_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_phase3_closure_gap_dossier_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_phase3_closure_gap_dossier_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_phase3_closure_gap_dossier"
SCHEMA_VERSION = "gpcr_hard_decoy_phase3_closure_gap_dossier_v1"

CI_LOW_MIN = 0.45
TOP20_MIN = 0.20

CLAIM_BOUNDARY = (
    "GPCR hard-decoy Phase 3 closure gap dossier only. It reads local evidence artifacts and reports "
    "which closure gates remain blocked. It does not run scoring, regenerate decoys, relax thresholds, "
    "promote a broad-GPCR claim, fetch external data, or mutate external state."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "claim_promotion_allowed": False,
}

CSV_COLUMNS = (
    "gate_id",
    "status",
    "observed",
    "threshold",
    "gap_to_threshold",
    "blocker",
    "evidence",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _read_json(path_like: str | Path) -> tuple[dict[str, Any], str]:
    path = _resolve(path_like)
    if not path.exists():
        return {}, f"missing:{_display(path)}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, f"unreadable:{_display(path)}"
    if not isinstance(payload, dict):
        return {}, f"invalid:{_display(path)}"
    return payload, _display(path)


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "y"}


def _gate_row(
    *,
    gate_id: str,
    ready: bool,
    observed: Any,
    threshold: Any,
    blocker: str,
    evidence: str,
    gap_to_threshold: float | None = None,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "ready" if ready else "blocked",
        "observed": observed,
        "threshold": threshold,
        "gap_to_threshold": "" if gap_to_threshold is None else gap_to_threshold,
        "blocker": "" if ready else blocker,
        "evidence": evidence,
    }


def _probe_metrics(probe: dict[str, Any], key: str) -> dict[str, Any]:
    metrics = probe.get(key)
    return metrics if isinstance(metrics, dict) else {}


def build_gpcr_hard_decoy_phase3_closure_gap_dossier(
    *,
    official_suite_json: str | Path = DEFAULT_OFFICIAL_SUITE_JSON,
    current_fit_probe_json: str | Path = DEFAULT_CURRENT_FIT_PROBE_JSON,
    candidate_sweep_json: str | Path = DEFAULT_CANDIDATE_SWEEP_JSON,
    materialization_readiness_json: str | Path = DEFAULT_MATERIALIZATION_READINESS_JSON,
    adora2a_rescue_json: str | Path = DEFAULT_ADORA2A_RESCUE_JSON,
    adora2a_preregistered_replay_json: str | Path = DEFAULT_ADORA2A_PREREGISTERED_REPLAY_JSON,
    claim_unlock_audit_json: str | Path = DEFAULT_CLAIM_UNLOCK_AUDIT_JSON,
) -> dict[str, Any]:
    official, official_evidence = _read_json(official_suite_json)
    probe, probe_evidence = _read_json(current_fit_probe_json)
    sweep, sweep_evidence = _read_json(candidate_sweep_json)
    materialization, materialization_evidence = _read_json(materialization_readiness_json)
    adora2a_rescue, adora2a_rescue_evidence = _read_json(adora2a_rescue_json)
    adora2a_preregistered_replay, adora2a_preregistered_replay_evidence = _read_json(
        adora2a_preregistered_replay_json
    )
    claim_unlock_audit, claim_unlock_audit_evidence = _read_json(claim_unlock_audit_json)

    official_summary = official.get("summary") if isinstance(official.get("summary"), dict) else {}
    sweep_summary = sweep.get("summary") if isinstance(sweep.get("summary"), dict) else {}
    materialization_summary = materialization.get("summary") if isinstance(materialization.get("summary"), dict) else {}
    claim_unlock_summary = (
        claim_unlock_audit.get("summary") if isinstance(claim_unlock_audit.get("summary"), dict) else {}
    )
    claim_unlock_metrics = (
        claim_unlock_summary.get("effective_phase3_metrics")
        if isinstance(claim_unlock_summary.get("effective_phase3_metrics"), dict)
        else {}
    )

    heldout = _probe_metrics(probe, "selected_target_heldout")
    current_fit = _probe_metrics(probe, "selected_current_fit")
    adora2a_rescue_metrics = _probe_metrics(adora2a_rescue, "rescue_target_heldout")
    adora2a_preregistered_metrics = _probe_metrics(
        adora2a_preregistered_replay,
        "runner_replay_target_heldout",
    )
    positive_rank_rows = probe.get("selected_target_heldout_positive_rank_rows")
    if not isinstance(positive_rank_rows, list):
        positive_rank_rows = []
    target_metric_rows = probe.get("selected_target_heldout_target_metric_rows")
    if not isinstance(target_metric_rows, list):
        target_metric_rows = []

    heldout_ci = _float(heldout.get("ranking_pr_auc_ci_low"))
    heldout_top20 = _float(heldout.get("top20_hit_rate"))
    heldout_decoys = _float(heldout.get("target_decoys_above_positive_total"))
    heldout_anchor_ready = heldout.get("all_required_targets_anchor_margin_nonnegative") is True
    rescue_ci = _float(adora2a_rescue_metrics.get("ranking_pr_auc_ci_low"))
    rescue_top20 = _float(adora2a_rescue_metrics.get("top20_hit_rate"))
    rescue_decoys = _float(adora2a_rescue_metrics.get("target_decoys_above_positive_total"))
    rescue_gate_pass = adora2a_rescue.get("rescue_closure_gate_pass") is True
    rescue_claim_locked = adora2a_rescue.get("claim_promotion_allowed") is False
    preregistered_ci = _float(adora2a_preregistered_metrics.get("ranking_pr_auc_ci_low"))
    preregistered_top20 = _float(adora2a_preregistered_metrics.get("top20_hit_rate"))
    preregistered_decoys = _float(
        adora2a_preregistered_metrics.get("target_decoys_above_positive_total")
    )
    preregistered_gate_pass = adora2a_preregistered_replay.get("runner_replay_closure_gate_pass") is True
    preregistered_score_match = (
        adora2a_preregistered_replay.get("score_matches_probe") is True
        or adora2a_preregistered_replay.get("runner_replay_matches_probe_score") is True
    )
    preregistered_claim_locked = (
        adora2a_preregistered_replay.get("claim_promotion_allowed") is False
        and adora2a_preregistered_replay.get("canonical_runner_shadow_only_active_locked") is True
    )
    preregistered_replay_complete = (
        adora2a_preregistered_replay.get("pre_registered_runner_replay_complete") is True
    )

    current_fit_ready = probe.get("current_fit_closure_gate_pass") is True
    current_fit_claim_locked = probe.get("claim_promotion_allowed") is False
    official_ready = official_summary.get("family_claim_safe") is True and official_summary.get("status") == "gpcr_hard_decoy_family_ready"
    official_claim_locked = official_summary.get("claim_locked") is True
    official_diagnostic_family_ready_before_claim_lock = (
        official_summary.get("diagnostic_family_claim_safe_before_claim_lock") is True
        and official_summary.get("diagnostic_status_before_claim_lock") == "gpcr_hard_decoy_family_ready"
    )
    claim_unlock_metric_ready = claim_unlock_summary.get("phase3_exit_metric_conditions_ready") is True
    claim_unlock_broad_promotion_locked = claim_unlock_summary.get("broad_promotion_remains_locked") is True
    claim_unlock_effective_ci = _float(claim_unlock_metrics.get("ranking_pr_auc_ci_low"))
    claim_unlock_effective_top20 = _float(claim_unlock_metrics.get("top20_hit_rate"))
    claim_unlock_effective_decoys = _float(claim_unlock_metrics.get("decoys_above_positive_count"))
    claim_unlock_effective_anchor_ready = claim_unlock_metrics.get("anchor_margin_nonnegative") is True
    use_claim_unlock_effective_metrics = claim_unlock_metric_ready

    effective_ci = claim_unlock_effective_ci if use_claim_unlock_effective_metrics else heldout_ci
    effective_top20 = claim_unlock_effective_top20 if use_claim_unlock_effective_metrics else heldout_top20
    effective_decoys = claim_unlock_effective_decoys if use_claim_unlock_effective_metrics else heldout_decoys
    effective_anchor_ready = (
        claim_unlock_effective_anchor_ready if use_claim_unlock_effective_metrics else heldout_anchor_ready
    )
    effective_decoy_ready = (
        effective_decoys == 0
        and (
            claim_unlock_metric_ready
            or heldout.get("all_required_targets_decoy_clear") is True
        )
    )
    effective_ci_ready = effective_ci is not None and effective_ci >= CI_LOW_MIN
    effective_top20_ready = effective_top20 is not None and effective_top20 >= TOP20_MIN
    effective_metric_evidence = claim_unlock_audit_evidence if use_claim_unlock_effective_metrics else probe_evidence
    effective_metric_source = (
        "claim_unlock_audit"
        if use_claim_unlock_effective_metrics
        else "target_heldout_current_fit_probe"
    )
    official_gate_ready = (official_ready and not official_claim_locked) or claim_unlock_metric_ready
    claim_unlock_required = official_claim_locked or official_diagnostic_family_ready_before_claim_lock
    claim_unlock_gate_ready = (not claim_unlock_required) or claim_unlock_metric_ready
    claim_unlock_metric_blockers = claim_unlock_summary.get("metric_blockers")
    if not isinstance(claim_unlock_metric_blockers, list):
        claim_unlock_metric_blockers = []
    claim_unlock_promotion_blockers = claim_unlock_summary.get("promotion_blockers")
    if not isinstance(claim_unlock_promotion_blockers, list):
        claim_unlock_promotion_blockers = []

    raw_ci_gap = None if heldout_ci is None else max(0.0, CI_LOW_MIN - heldout_ci)
    effective_ci_gap = None if effective_ci is None else max(0.0, CI_LOW_MIN - effective_ci)
    effective_top20_gap = None if effective_top20 is None else max(0.0, TOP20_MIN - effective_top20)

    rows = [
        _gate_row(
            gate_id="official_suite_family_claim_safe",
            ready=official_gate_ready,
            observed=official_summary.get("status", "missing"),
            threshold="family-ready, or claim-locked diagnostic family-ready plus claim-unlock metric audit",
            blocker="official_suite_not_family_ready",
            evidence=official_evidence,
        ),
        _gate_row(
            gate_id="claim_unlock_metric_evidence",
            ready=claim_unlock_gate_ready,
            observed=claim_unlock_summary.get("status", "missing"),
            threshold="not required, or phase3_exit_metric_conditions_ready=true",
            blocker="claim_unlock_metric_evidence_not_ready",
            evidence=claim_unlock_audit_evidence,
        ),
        _gate_row(
            gate_id="target_heldout_ranking_pr_auc_ci_low",
            ready=effective_ci_ready,
            observed="" if effective_ci is None else effective_ci,
            threshold=CI_LOW_MIN,
            gap_to_threshold=effective_ci_gap,
            blocker="target_heldout_pr_auc_ci_low_below_phase3_gate",
            evidence=effective_metric_evidence,
        ),
        _gate_row(
            gate_id="target_heldout_top20_hit_rate",
            ready=effective_top20_ready,
            observed="" if effective_top20 is None else effective_top20,
            threshold=TOP20_MIN,
            gap_to_threshold=effective_top20_gap,
            blocker="target_heldout_top20_hit_rate_below_phase3_gate",
            evidence=effective_metric_evidence,
        ),
        _gate_row(
            gate_id="target_heldout_decoys_above_positive_count",
            ready=effective_decoy_ready,
            observed="" if effective_decoys is None else int(effective_decoys),
            threshold=0,
            blocker="target_heldout_decoys_above_positive_present",
            evidence=effective_metric_evidence,
        ),
        _gate_row(
            gate_id="target_heldout_anchor_margin",
            ready=effective_anchor_ready,
            observed=effective_anchor_ready,
            threshold="all required targets nonnegative",
            blocker="target_heldout_positive_out_anchored_by_top_decoy",
            evidence=effective_metric_evidence,
        ),
        _gate_row(
            gate_id="current_fit_upper_bound",
            ready=current_fit_ready and current_fit_claim_locked,
            observed=probe.get("status", "missing"),
            threshold="current-fit pass but claim locked",
            blocker="current_fit_upper_bound_missing_or_not_claim_locked",
            evidence=probe_evidence,
        ),
    ]

    blocked = [row["blocker"] for row in rows if row["status"] != "ready" and row["blocker"]]
    phase3_ready = not blocked
    if phase3_ready:
        status = "gpcr_hard_decoy_phase3_closure_evidence_ready"
    elif "target_heldout_pr_auc_ci_low_below_phase3_gate" in blocked:
        status = "blocked_gpcr_hard_decoy_phase3_target_heldout_ci_low"
    else:
        status = "blocked_gpcr_hard_decoy_phase3_closure_gap"
    if phase3_ready and claim_unlock_metric_ready and claim_unlock_broad_promotion_locked:
        next_required_step = (
            "Phase 3 hard-decoy metric evidence is ready under the claim-unlock audit, but broad/router/scorer "
            "promotion remains locked. Keep claim_promotion_allowed=false until the formal broad-claim review "
            "and scorer/router promotion gates clear."
        )
    elif phase3_ready:
        next_required_step = "Operator review can decide whether this read-only evidence supports claim promotion."
    elif official_diagnostic_family_ready_before_claim_lock and official_claim_locked:
        next_required_step = (
            "Suite targets are green under the pre-registered replay, but the suite is claim-locked because the "
            "ADORA2A rule came from the current failure slice. Run an independent claim-unlock replay before "
            "Phase 3 closure."
        )
    elif preregistered_replay_complete and preregistered_gate_pass and preregistered_score_match and preregistered_claim_locked:
        next_required_step = (
            "Run the official Phase 3 family suite with the pre-registered ADORA2A replay evidence in scope; "
            "keep Phase 3 blocked until the official suite is family-ready and the target-held-out CI-low gate clears."
        )
    elif rescue_gate_pass and rescue_claim_locked:
        next_required_step = (
            "Run the pre-registered ADORA2A neutral-antagonist rescue through the canonical runner replay; keep "
            "Phase 3 blocked until the official suite, not this diagnostic, clears."
        )
    else:
        next_required_step = (
            "Improve or independently validate a target-heldout scorer until PR-AUC CI-low >= 0.45 while "
            "preserving top20, decoy-above-positive, and anchor-margin gates."
        )

    summary = {
        "status": status,
        "phase3_closure_evidence_ready": phase3_ready,
        "official_suite_status": official_summary.get("status", "missing"),
        "official_family_claim_safe": bool(official_summary.get("family_claim_safe")),
        "official_claim_locked": official_claim_locked,
        "official_diagnostic_status_before_claim_lock": official_summary.get(
            "diagnostic_status_before_claim_lock",
            "",
        ),
        "official_diagnostic_family_claim_safe_before_claim_lock": bool(
            official_summary.get("diagnostic_family_claim_safe_before_claim_lock")
        ),
        "official_claim_lock_reason": official_summary.get("claim_lock_reason", ""),
        "official_blocked_target_ids": list(official_summary.get("blocked_target_ids") or []),
        "current_fit_closure_gate_pass": bool(probe.get("current_fit_closure_gate_pass")),
        "current_fit_claim_locked": current_fit_claim_locked,
        "current_fit_ranking_pr_auc_ci_low": _float(current_fit.get("ranking_pr_auc_ci_low")),
        "target_heldout_closure_gate_pass": bool(probe.get("target_heldout_closure_gate_pass")),
        "target_heldout_ranking_pr_auc": _float(heldout.get("ranking_pr_auc")),
        "target_heldout_ranking_pr_auc_ci_low": heldout_ci,
        "target_heldout_pr_auc_ci_low_min": CI_LOW_MIN,
        "target_heldout_pr_auc_ci_low_gap": raw_ci_gap,
        "target_heldout_top20_hit_rate": heldout_top20,
        "target_heldout_decoys_above_positive_total": None if heldout_decoys is None else int(heldout_decoys),
        "target_heldout_all_required_targets_anchor_margin_nonnegative": heldout_anchor_ready,
        "target_heldout_score_col": probe.get("target_heldout_score_col", ""),
        "target_heldout_positive_rank_row_count": len(positive_rank_rows),
        "target_heldout_worst_positive_rank": probe.get("selected_target_heldout_worst_positive_rank"),
        "target_heldout_top20_positive_count": probe.get("selected_target_heldout_top20_positive_count"),
        "target_heldout_lowest_target_pr_auc": probe.get("selected_target_heldout_lowest_target_pr_auc"),
        "candidate_sweep_status": sweep_summary.get("status", "missing"),
        "candidate_sweep_closure_candidate_count": sweep_summary.get("closure_candidate_count"),
        "materialization_readiness_status": materialization_summary.get("status", "missing"),
        "adora2a_neutral_rescue_status": adora2a_rescue.get("status", "missing"),
        "adora2a_neutral_rescue_gate_pass": rescue_gate_pass,
        "adora2a_neutral_rescue_claim_locked": rescue_claim_locked,
        "adora2a_neutral_rescue_independent_replay_required": adora2a_rescue.get(
            "independent_replay_required"
        )
        is True,
        "adora2a_neutral_rescue_score_col": adora2a_rescue.get("score_col", ""),
        "adora2a_neutral_rescue_ranking_pr_auc_ci_low": rescue_ci,
        "adora2a_neutral_rescue_top20_hit_rate": rescue_top20,
        "adora2a_neutral_rescue_decoys_above_positive_total": (
            None if rescue_decoys is None else int(rescue_decoys)
        ),
        "adora2a_neutral_rescue_anchor_margin_gate": (
            adora2a_rescue_metrics.get("all_required_targets_anchor_margin_nonnegative") is True
        ),
        "adora2a_neutral_rescue_support_counts": adora2a_rescue.get("support_counts", {}),
        "adora2a_neutral_rescue_pressure_counts": adora2a_rescue.get("pressure_counts", {}),
        "adora2a_preregistered_replay_status": adora2a_preregistered_replay.get("status", "missing"),
        "adora2a_preregistered_replay_complete": preregistered_replay_complete,
        "adora2a_preregistered_replay_gate_pass": preregistered_gate_pass,
        "adora2a_preregistered_replay_claim_locked": preregistered_claim_locked,
        "adora2a_preregistered_replay_score_matches_probe": preregistered_score_match,
        "adora2a_preregistered_replay_score_col": adora2a_preregistered_replay.get("score_col", ""),
        "adora2a_preregistered_replay_ranking_pr_auc_ci_low": preregistered_ci,
        "adora2a_preregistered_replay_top20_hit_rate": preregistered_top20,
        "adora2a_preregistered_replay_decoys_above_positive_total": (
            None if preregistered_decoys is None else int(preregistered_decoys)
        ),
        "adora2a_preregistered_replay_anchor_margin_gate": (
            adora2a_preregistered_metrics.get("all_required_targets_anchor_margin_nonnegative") is True
        ),
        "adora2a_preregistered_replay_max_abs_score_diff_vs_probe": adora2a_preregistered_replay.get(
            "max_abs_score_diff_vs_probe"
        ),
        "claim_unlock_audit_status": claim_unlock_summary.get("status", "missing"),
        "claim_unlock_phase3_exit_metric_conditions_ready": claim_unlock_metric_ready,
        "claim_unlock_hard_decoy_metric_claim_unlock_ready": bool(
            claim_unlock_summary.get("hard_decoy_metric_claim_unlock_ready")
        ),
        "claim_unlock_broad_promotion_remains_locked": claim_unlock_broad_promotion_locked,
        "claim_unlock_metric_blockers": list(claim_unlock_metric_blockers),
        "claim_unlock_promotion_blockers": list(claim_unlock_promotion_blockers),
        "effective_phase3_metric_source": effective_metric_source,
        "effective_phase3_ranking_pr_auc_ci_low": effective_ci,
        "effective_phase3_pr_auc_ci_low_gap": effective_ci_gap,
        "effective_phase3_top20_hit_rate": effective_top20,
        "effective_phase3_decoys_above_positive_total": (
            None if effective_decoys is None else int(effective_decoys)
        ),
        "effective_phase3_anchor_margin_nonnegative": effective_anchor_ready,
        "blockers": blocked,
        "gate_count": len(rows),
        "blocked_gate_count": len(blocked),
        "next_required_step": next_required_step,
        **READ_ONLY_FLAGS,
    }

    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": summary,
        "rows": rows,
        "target_heldout_positive_rank_rows": positive_rank_rows,
        "target_heldout_target_metric_rows": target_metric_rows,
        "evidence": {
            "official_suite_json": official_evidence,
            "current_fit_probe_json": probe_evidence,
            "candidate_sweep_json": sweep_evidence,
            "materialization_readiness_json": materialization_evidence,
            "adora2a_rescue_json": adora2a_rescue_evidence,
            "adora2a_preregistered_replay_json": adora2a_preregistered_replay_evidence,
            "claim_unlock_audit_json": claim_unlock_audit_evidence,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def write_outputs(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path, out_csv: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    csv_path = _resolve(out_csv)
    for path in (json_path, md_path, csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    summary = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Phase 3 Closure Gap Dossier",
        "",
        f"- status: `{summary.get('status')}`",
        f"- phase3_closure_evidence_ready: `{str(summary.get('phase3_closure_evidence_ready')).lower()}`",
        f"- official_suite_status: `{summary.get('official_suite_status')}`",
        f"- official_family_claim_safe: `{str(summary.get('official_family_claim_safe')).lower()}`",
        f"- official_claim_locked: `{str(summary.get('official_claim_locked')).lower()}`",
        f"- official_diagnostic_status_before_claim_lock: `{summary.get('official_diagnostic_status_before_claim_lock')}`",
        "- official_diagnostic_family_claim_safe_before_claim_lock: "
        f"`{str(summary.get('official_diagnostic_family_claim_safe_before_claim_lock')).lower()}`",
        f"- current_fit_closure_gate_pass: `{str(summary.get('current_fit_closure_gate_pass')).lower()}`",
        f"- current_fit_claim_locked: `{str(summary.get('current_fit_claim_locked')).lower()}`",
        f"- target_heldout_ranking_pr_auc_ci_low: `{summary.get('target_heldout_ranking_pr_auc_ci_low')}`",
        f"- target_heldout_pr_auc_ci_low_gap: `{summary.get('target_heldout_pr_auc_ci_low_gap')}`",
        f"- target_heldout_top20_hit_rate: `{summary.get('target_heldout_top20_hit_rate')}`",
        f"- target_heldout_decoys_above_positive_total: `{summary.get('target_heldout_decoys_above_positive_total')}`",
        f"- target_heldout_anchor_margin_gate: `{str(summary.get('target_heldout_all_required_targets_anchor_margin_nonnegative')).lower()}`",
        f"- target_heldout_worst_positive_rank: `{summary.get('target_heldout_worst_positive_rank')}`",
        f"- target_heldout_top20_positive_count: `{summary.get('target_heldout_top20_positive_count')}`",
        f"- target_heldout_lowest_target_pr_auc: `{summary.get('target_heldout_lowest_target_pr_auc')}`",
        f"- adora2a_neutral_rescue_status: `{summary.get('adora2a_neutral_rescue_status')}`",
        f"- adora2a_neutral_rescue_gate_pass: `{str(summary.get('adora2a_neutral_rescue_gate_pass')).lower()}`",
        f"- adora2a_neutral_rescue_ci_low: `{summary.get('adora2a_neutral_rescue_ranking_pr_auc_ci_low')}`",
        f"- adora2a_neutral_rescue_top20_hit_rate: `{summary.get('adora2a_neutral_rescue_top20_hit_rate')}`",
        f"- adora2a_neutral_rescue_decoys_above_positive_total: `{summary.get('adora2a_neutral_rescue_decoys_above_positive_total')}`",
        f"- adora2a_neutral_rescue_claim_locked: `{str(summary.get('adora2a_neutral_rescue_claim_locked')).lower()}`",
        f"- adora2a_preregistered_replay_status: `{summary.get('adora2a_preregistered_replay_status')}`",
        f"- adora2a_preregistered_replay_complete: `{str(summary.get('adora2a_preregistered_replay_complete')).lower()}`",
        f"- adora2a_preregistered_replay_gate_pass: `{str(summary.get('adora2a_preregistered_replay_gate_pass')).lower()}`",
        f"- adora2a_preregistered_replay_score_matches_probe: `{str(summary.get('adora2a_preregistered_replay_score_matches_probe')).lower()}`",
        f"- adora2a_preregistered_replay_ci_low: `{summary.get('adora2a_preregistered_replay_ranking_pr_auc_ci_low')}`",
        f"- adora2a_preregistered_replay_max_abs_score_diff_vs_probe: `{summary.get('adora2a_preregistered_replay_max_abs_score_diff_vs_probe')}`",
        f"- claim_unlock_audit_status: `{summary.get('claim_unlock_audit_status')}`",
        "- claim_unlock_phase3_exit_metric_conditions_ready: "
        f"`{str(summary.get('claim_unlock_phase3_exit_metric_conditions_ready')).lower()}`",
        "- claim_unlock_broad_promotion_remains_locked: "
        f"`{str(summary.get('claim_unlock_broad_promotion_remains_locked')).lower()}`",
        f"- effective_phase3_metric_source: `{summary.get('effective_phase3_metric_source')}`",
        f"- effective_phase3_ranking_pr_auc_ci_low: `{summary.get('effective_phase3_ranking_pr_auc_ci_low')}`",
        f"- effective_phase3_pr_auc_ci_low_gap: `{summary.get('effective_phase3_pr_auc_ci_low_gap')}`",
        f"- effective_phase3_top20_hit_rate: `{summary.get('effective_phase3_top20_hit_rate')}`",
        "- effective_phase3_decoys_above_positive_total: "
        f"`{summary.get('effective_phase3_decoys_above_positive_total')}`",
        "- effective_phase3_anchor_margin_nonnegative: "
        f"`{str(summary.get('effective_phase3_anchor_margin_nonnegative')).lower()}`",
        f"- blockers: `{', '.join(summary.get('blockers') or []) or '(none)'}`",
        "",
        "## Gates",
        "",
        "| gate | status | observed | threshold | gap | blocker |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{gate}` | `{status}` | `{observed}` | `{threshold}` | `{gap}` | {blocker} |".format(
                gate=row["gate_id"],
                status=row["status"],
                observed=row["observed"],
                threshold=row["threshold"],
                gap=row["gap_to_threshold"],
                blocker=row["blocker"] or "(none)",
            )
        )
    positive_rows = payload.get("target_heldout_positive_rank_rows") or []
    if positive_rows:
        lines.extend(
            [
                "",
                "## Target-Heldout Positive Ranks",
                "",
                "| target | ligand | rank | decoys above | in top20 |",
                "| --- | --- | ---: | ---: | --- |",
            ]
        )
        for row in sorted(positive_rows, key=lambda item: int(item.get("positive_target_rank") or 10**9))[:20]:
            lines.append(
                "| `{target}` | `{ligand}` | {rank} | {decoys} | `{top20}` |".format(
                    target=row.get("target_id", ""),
                    ligand=row.get("ligand_id", ""),
                    rank=row.get("positive_target_rank", ""),
                    decoys=row.get("decoys_above_positive_count", ""),
                    top20=str(row.get("in_top20")).lower(),
                )
            )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for row in payload["rows"]:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-suite-json", default=DEFAULT_OFFICIAL_SUITE_JSON)
    parser.add_argument("--current-fit-probe-json", default=DEFAULT_CURRENT_FIT_PROBE_JSON)
    parser.add_argument("--candidate-sweep-json", default=DEFAULT_CANDIDATE_SWEEP_JSON)
    parser.add_argument("--materialization-readiness-json", default=DEFAULT_MATERIALIZATION_READINESS_JSON)
    parser.add_argument("--adora2a-rescue-json", default=DEFAULT_ADORA2A_RESCUE_JSON)
    parser.add_argument(
        "--adora2a-preregistered-replay-json",
        default=DEFAULT_ADORA2A_PREREGISTERED_REPLAY_JSON,
    )
    parser.add_argument("--claim-unlock-audit-json", default=DEFAULT_CLAIM_UNLOCK_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=args.official_suite_json,
        current_fit_probe_json=args.current_fit_probe_json,
        candidate_sweep_json=args.candidate_sweep_json,
        materialization_readiness_json=args.materialization_readiness_json,
        adora2a_rescue_json=args.adora2a_rescue_json,
        adora2a_preregistered_replay_json=args.adora2a_preregistered_replay_json,
        claim_unlock_audit_json=args.claim_unlock_audit_json,
    )
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md, out_csv=args.out_csv)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
