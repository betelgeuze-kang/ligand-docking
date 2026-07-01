#!/usr/bin/env python3
"""Build the GPCR hard-decoy claim-unlock audit.

This read-only packet separates metric closure evidence from broad GPCR/router
promotion. It can mark Phase 3 hard-decoy metric evidence ready only when the
claim-locked official suite is green before the claim lock, the pre-registered
runner replay clears the hard-decoy gates, and an independent repeat clears its
guarded ranking thresholds. It never promotes claims or mutates external state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.gpcr_replay.build_gpcr_active_scorer_promotion_decision_packet import (
    scorecard_metric_ready_under_claim_lock,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OFFICIAL_SUITE_JSON = "runs/gpcr_hard_decoy_suite_current.json"
DEFAULT_PREREGISTERED_REPLAY_JSON = "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json"
DEFAULT_INDEPENDENT_REPEAT_JSON = "runs/gpcr_a1_independent_repeat_packet_current.json"
DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_BROAD_SCOPE_READINESS_JSON = "runs/gpcr_broad_claim_scope_readiness_current.json"
DEFAULT_ACTIVE_SCORER_DECISION_JSON = "runs/gpcr_active_scorer_promotion_decision_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_claim_unlock_audit_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_claim_unlock_audit_current.md"

PACKET_TYPE = "gpcr_hard_decoy_claim_unlock_audit"
SCHEMA_VERSION = "gpcr_hard_decoy_claim_unlock_audit_v1"

CI_LOW_MIN = 0.45
TOP20_MIN = 0.20

CLAIM_BOUNDARY = (
    "GPCR hard-decoy claim-unlock audit only. It reads local evidence artifacts and records whether "
    "the claim-locked hard-decoy diagnostic has enough independent metric evidence for Phase 3 metric "
    "closure review. It does not promote broad GPCR, router, platform, or active-scorer claims; run "
    "formal broad-claim review and scorer/router promotion gates separately."
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
    return (payload, _display(path)) if isinstance(payload, dict) else ({}, f"invalid:{_display(path)}")


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _gate_row(
    *,
    gate_id: str,
    ready: bool,
    observed: Any,
    threshold: Any,
    blocker: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "ready" if ready else "blocked",
        "observed": observed,
        "threshold": threshold,
        "blocker": "" if ready else blocker,
        "evidence": evidence,
    }


def _metric_ready(ci_low: float | None, top20: float | None, decoys: float | None, anchor_ready: bool) -> bool:
    return (
        ci_low is not None
        and ci_low >= CI_LOW_MIN
        and top20 is not None
        and top20 >= TOP20_MIN
        and decoys == 0
        and anchor_ready
    )


def build_gpcr_hard_decoy_claim_unlock_audit(
    *,
    official_suite_json: str | Path = DEFAULT_OFFICIAL_SUITE_JSON,
    preregistered_replay_json: str | Path = DEFAULT_PREREGISTERED_REPLAY_JSON,
    independent_repeat_json: str | Path = DEFAULT_INDEPENDENT_REPEAT_JSON,
    accuracy_scorecard_json: str | Path = DEFAULT_ACCURACY_SCORECARD_JSON,
    broad_scope_readiness_json: str | Path = DEFAULT_BROAD_SCOPE_READINESS_JSON,
    active_scorer_decision_json: str | Path = DEFAULT_ACTIVE_SCORER_DECISION_JSON,
) -> dict[str, Any]:
    official, official_evidence = _read_json(official_suite_json)
    preregistered, preregistered_evidence = _read_json(preregistered_replay_json)
    independent_repeat, independent_repeat_evidence = _read_json(independent_repeat_json)
    scorecard, scorecard_evidence = _read_json(accuracy_scorecard_json)
    broad_scope, broad_scope_evidence = _read_json(broad_scope_readiness_json)
    active_scorer, active_scorer_evidence = _read_json(active_scorer_decision_json)

    official_summary = _summary(official)
    repeat_summary = _summary(independent_repeat)
    broad_summary = _summary(broad_scope)
    active_summary = _summary(active_scorer)
    scorecard_readiness = scorecard_metric_ready_under_claim_lock(scorecard)

    official_required_targets = [str(item) for item in _list(official_summary.get("required_target_ids"))]
    official_green_targets = [str(item) for item in _list(official_summary.get("green_target_ids"))]
    official_blocked_targets = [str(item) for item in _list(official_summary.get("blocked_target_ids"))]
    official_missing_targets = [str(item) for item in _list(official_summary.get("missing_required_target_ids"))]
    official_diagnostic_green = (
        official_summary.get("claim_locked") is True
        and official_summary.get("diagnostic_status_before_claim_lock") == "gpcr_hard_decoy_family_ready"
        and official_summary.get("diagnostic_family_claim_safe_before_claim_lock") is True
        and not official_blocked_targets
        and not official_missing_targets
        and set(official_required_targets).issubset(set(official_green_targets))
    )

    preregistered_metrics = _dict(preregistered.get("runner_replay_target_heldout"))
    preregistered_ci = _float(preregistered_metrics.get("ranking_pr_auc_ci_low"))
    preregistered_top20 = _float(preregistered_metrics.get("top20_hit_rate"))
    preregistered_decoys = _float(preregistered_metrics.get("target_decoys_above_positive_total"))
    preregistered_anchor_ready = preregistered_metrics.get("all_required_targets_anchor_margin_nonnegative") is True
    preregistered_decoy_clear = (
        preregistered_metrics.get("all_required_targets_decoy_clear") is True and preregistered_decoys == 0
    )
    preregistered_metric_ready = _metric_ready(
        preregistered_ci,
        preregistered_top20,
        preregistered_decoys,
        preregistered_anchor_ready and preregistered_decoy_clear,
    )
    preregistered_replay_ready = (
        preregistered.get("status") == "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked"
        and preregistered.get("pre_registered_runner_replay_complete") is True
        and preregistered.get("runner_replay_closure_gate_pass") is True
        and (
            preregistered.get("score_matches_probe") is True
            or preregistered.get("runner_replay_matches_probe_score") is True
        )
        and preregistered.get("claim_promotion_allowed") is False
        and preregistered.get("canonical_runner_shadow_only_active_locked") is True
        and preregistered_metric_ready
    )

    repeat_ci = _float(repeat_summary.get("ranking_pr_auc_ci_low"))
    repeat_top20 = _float(repeat_summary.get("ranking_top20_hit_rate"))
    repeat_metric_ready = (
        repeat_summary.get("status") == "independent_repeat_passed_claim_locked"
        and repeat_summary.get("independent_repeat_completed") is True
        and repeat_summary.get("independent_repeat_result_passed") is True
        and repeat_summary.get("claim_promotion_allowed") is False
        and repeat_ci is not None
        and repeat_ci >= CI_LOW_MIN
        and repeat_top20 is not None
        and repeat_top20 >= TOP20_MIN
    )
    scorecard_metric_ready = bool(scorecard_readiness.get("metric_ready"))
    hard_decoy_metric_ready = bool(
        official_diagnostic_green
        and preregistered_replay_ready
        and repeat_metric_ready
        and scorecard_metric_ready
    )

    effective_ci_values = [value for value in (preregistered_ci, repeat_ci) if value is not None]
    effective_top20_values = [value for value in (preregistered_top20, repeat_top20) if value is not None]
    effective_metrics = {
        "ranking_pr_auc_ci_low": min(effective_ci_values) if effective_ci_values else None,
        "top20_hit_rate": min(effective_top20_values) if effective_top20_values else None,
        "decoys_above_positive_count": None if preregistered_decoys is None else int(preregistered_decoys),
        "anchor_margin_nonnegative": preregistered_anchor_ready,
        "source": "claim_locked_official_suite_plus_preregistered_replay_plus_independent_repeat",
    }

    metric_blockers: list[str] = []
    if not official_diagnostic_green:
        metric_blockers.append("official_suite_not_diagnostic_green_claim_locked")
    if not preregistered_replay_ready:
        metric_blockers.append("preregistered_runner_replay_not_ready")
    if not repeat_metric_ready:
        metric_blockers.append("independent_repeat_metric_evidence_not_passed")
    if not scorecard_metric_ready:
        metric_blockers.append("accuracy_parity_metric_not_ready")

    broad_blockers = [str(item) for item in _list(broad_summary.get("blockers"))]
    active_blockers = [str(item) for item in _list(active_summary.get("blockers"))]
    promotion_blockers: list[str] = []
    if broad_summary.get("target_heldout_broad_scope_review_approved") is not True:
        promotion_blockers.append("target_heldout_broad_scope_review_not_approved")
    if broad_summary.get("scorer_router_promotion_gate_ready") is not True:
        promotion_blockers.append("scorer_router_promotion_gate_not_ready")
    if active_summary.get("active_scorer_apply_allowed") is not True:
        promotion_blockers.append("active_scorer_apply_not_allowed")
    promotion_blockers.extend(f"broad_scope:{item}" for item in broad_blockers)
    promotion_blockers.extend(f"active_scorer:{item}" for item in active_blockers)
    promotion_blockers = sorted(set(promotion_blockers))

    rows = [
        _gate_row(
            gate_id="official_suite_diagnostic_green_claim_locked",
            ready=official_diagnostic_green,
            observed=official_summary.get("status", "missing"),
            threshold="claim_locked diagnostic family-ready with all required targets green",
            blocker="official_suite_not_diagnostic_green_claim_locked",
            evidence=official_evidence,
        ),
        _gate_row(
            gate_id="preregistered_runner_replay_gate",
            ready=preregistered_replay_ready,
            observed=preregistered.get("status", "missing"),
            threshold="pre-registered replay complete, score-match, hard-decoy gates pass, claim locked",
            blocker="preregistered_runner_replay_not_ready",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_ranking_pr_auc_ci_low",
            ready=preregistered_ci is not None and preregistered_ci >= CI_LOW_MIN,
            observed="" if preregistered_ci is None else preregistered_ci,
            threshold=CI_LOW_MIN,
            blocker="hard_decoy_ranking_pr_auc_ci_low_below_gate",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_top20_hit_rate",
            ready=preregistered_top20 is not None and preregistered_top20 >= TOP20_MIN,
            observed="" if preregistered_top20 is None else preregistered_top20,
            threshold=TOP20_MIN,
            blocker="hard_decoy_top20_hit_rate_below_gate",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_decoys_above_positive_count",
            ready=preregistered_decoys == 0 and preregistered_decoy_clear,
            observed="" if preregistered_decoys is None else int(preregistered_decoys),
            threshold=0,
            blocker="hard_decoy_decoys_above_positive_present",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="hard_decoy_anchor_margin",
            ready=preregistered_anchor_ready,
            observed=preregistered_anchor_ready,
            threshold="all required targets nonnegative",
            blocker="hard_decoy_positive_out_anchored_by_top_decoy",
            evidence=preregistered_evidence,
        ),
        _gate_row(
            gate_id="independent_repeat_metric_passed",
            ready=repeat_metric_ready,
            observed=repeat_summary.get("status", "missing"),
            threshold="independent repeat completed and passed guarded ranking thresholds",
            blocker="independent_repeat_metric_evidence_not_passed",
            evidence=independent_repeat_evidence,
        ),
        _gate_row(
            gate_id="accuracy_parity_metric_ready_under_claim_lock",
            ready=scorecard_metric_ready,
            observed=scorecard_readiness.get("status", "missing"),
            threshold="metric-ready restricted pass or green scorecard",
            blocker="accuracy_parity_metric_not_ready",
            evidence=scorecard_evidence,
        ),
    ]

    if hard_decoy_metric_ready:
        status = "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked"
        next_required_step = (
            "Phase 3 hard-decoy metric evidence is ready for operator review, but broad/router/scorer promotion "
            "remains locked. Fill the broad-claim review receipt and scorer/router promotion gates before any "
            "claim promotion."
        )
    else:
        status = "blocked_gpcr_hard_decoy_claim_unlock_audit"
        next_required_step = "Resolve metric blockers before treating the claim-locked hard-decoy suite as Phase 3 ready."

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "phase3_exit_metric_conditions_ready": hard_decoy_metric_ready,
        "hard_decoy_metric_claim_unlock_ready": hard_decoy_metric_ready,
        "operator_claim_review_ready": hard_decoy_metric_ready,
        "broad_promotion_remains_locked": bool(promotion_blockers),
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "official_suite_diagnostic_green_claim_locked": official_diagnostic_green,
        "official_suite_status": official_summary.get("status", "missing"),
        "official_claim_lock_reason": official_summary.get("claim_lock_reason", ""),
        "preregistered_replay_status": preregistered.get("status", "missing"),
        "preregistered_replay_complete": preregistered.get("pre_registered_runner_replay_complete") is True,
        "preregistered_replay_gate_pass": preregistered.get("runner_replay_closure_gate_pass") is True,
        "preregistered_replay_score_matches_probe": (
            preregistered.get("score_matches_probe") is True
            or preregistered.get("runner_replay_matches_probe_score") is True
        ),
        "preregistered_ranking_pr_auc_ci_low": preregistered_ci,
        "preregistered_top20_hit_rate": preregistered_top20,
        "preregistered_decoys_above_positive_count": (
            None if preregistered_decoys is None else int(preregistered_decoys)
        ),
        "preregistered_anchor_margin_nonnegative": preregistered_anchor_ready,
        "independent_repeat_status": repeat_summary.get("status", "missing"),
        "independent_repeat_completed": repeat_summary.get("independent_repeat_completed") is True,
        "independent_repeat_result_passed": repeat_summary.get("independent_repeat_result_passed") is True,
        "independent_repeat_ready_to_launch": repeat_summary.get("independent_repeat_ready") is True,
        "independent_repeat_ranking_pr_auc_ci_low": repeat_ci,
        "independent_repeat_top20_hit_rate": repeat_top20,
        "accuracy_parity_metric_ready": scorecard_metric_ready,
        "accuracy_parity_metric_blockers": scorecard_readiness.get("metric_blockers", []),
        "accuracy_parity_claim_scope_lock_only": bool(scorecard_readiness.get("claim_scope_lock_only")),
        "effective_phase3_metrics": effective_metrics,
        "metric_blocker_count": len(metric_blockers),
        "metric_blockers": sorted(metric_blockers),
        "promotion_blocker_count": len(promotion_blockers),
        "promotion_blockers": promotion_blockers,
        "broad_scope_readiness_status": broad_summary.get("status", "missing"),
        "active_scorer_decision_status": active_summary.get("status", "missing"),
        "next_required_step": next_required_step,
    }

    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "evidence": {
            "official_suite_json": official_evidence,
            "preregistered_replay_json": preregistered_evidence,
            "independent_repeat_json": independent_repeat_evidence,
            "accuracy_scorecard_json": scorecard_evidence,
            "broad_scope_readiness_json": broad_scope_evidence,
            "active_scorer_decision_json": active_scorer_evidence,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    metric_blockers = summary.get("metric_blockers") if isinstance(summary.get("metric_blockers"), list) else []
    promotion_blockers = (
        summary.get("promotion_blockers") if isinstance(summary.get("promotion_blockers"), list) else []
    )
    lines = [
        "# GPCR Hard-Decoy Claim-Unlock Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- phase3_exit_metric_conditions_ready: `{str(summary['phase3_exit_metric_conditions_ready']).lower()}`",
        f"- hard_decoy_metric_claim_unlock_ready: `{str(summary['hard_decoy_metric_claim_unlock_ready']).lower()}`",
        f"- broad_promotion_remains_locked: `{str(summary['broad_promotion_remains_locked']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- preregistered_ranking_pr_auc_ci_low: `{summary['preregistered_ranking_pr_auc_ci_low']}`",
        f"- preregistered_top20_hit_rate: `{summary['preregistered_top20_hit_rate']}`",
        f"- preregistered_decoys_above_positive_count: `{summary['preregistered_decoys_above_positive_count']}`",
        f"- independent_repeat_ranking_pr_auc_ci_low: `{summary['independent_repeat_ranking_pr_auc_ci_low']}`",
        f"- independent_repeat_top20_hit_rate: `{summary['independent_repeat_top20_hit_rate']}`",
        f"- metric_blockers: `{', '.join(metric_blockers) or '(none)'}`",
        f"- promotion_blockers: `{', '.join(promotion_blockers) or '(none)'}`",
        "",
        "## Gates",
        "",
        "| gate | status | observed | threshold | blocker |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{gate}` | `{status}` | `{observed}` | `{threshold}` | {blocker} |".format(
                gate=row["gate_id"],
                status=row["status"],
                observed=row["observed"],
                threshold=row["threshold"],
                blocker=row["blocker"] or "(none)",
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-suite-json", default=DEFAULT_OFFICIAL_SUITE_JSON)
    parser.add_argument("--preregistered-replay-json", default=DEFAULT_PREREGISTERED_REPLAY_JSON)
    parser.add_argument("--independent-repeat-json", default=DEFAULT_INDEPENDENT_REPEAT_JSON)
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--broad-scope-readiness-json", default=DEFAULT_BROAD_SCOPE_READINESS_JSON)
    parser.add_argument("--active-scorer-decision-json", default=DEFAULT_ACTIVE_SCORER_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_gpcr_hard_decoy_claim_unlock_audit(
        official_suite_json=args.official_suite_json,
        preregistered_replay_json=args.preregistered_replay_json,
        independent_repeat_json=args.independent_repeat_json,
        accuracy_scorecard_json=args.accuracy_scorecard_json,
        broad_scope_readiness_json=args.broad_scope_readiness_json,
        active_scorer_decision_json=args.active_scorer_decision_json,
    )
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
