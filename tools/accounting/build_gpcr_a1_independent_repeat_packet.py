#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.lib.artifacts import artifact as _artifact
from tools.lib.artifacts import read_json as _read_json
from tools.lib.artifacts import resolve as _resolve
from tools.lib.artifacts import summary as _summary
from tools.lib.artifacts import write_json as _write_json

DEFAULT_A1_QUEUE_JSON = "runs/gpcr_a1_accuracy_repair_queue_current.json"
DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_RANKING_JSON = (
    "runs/external_validation_2026-05-13_gpcr_a1_independent_repeat_r2_"
    "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
)
DEFAULT_SET_SPEC_JSON = (
    "runs/gpcr_scaleup_100k_family_balanced_coverage_v1_candidate_current/specs/"
    "gpcr_core_family_balanced_rescore_100k_coverage-v1-family-balanced100k.json"
)
DEFAULT_REPEAT_TAG = "2026-05-13_gpcr_a1_independent_repeat_r2"
DEFAULT_OUT_JSON = "runs/gpcr_a1_independent_repeat_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_a1_independent_repeat_packet_current.md"

PR_AUC_MIN = 0.55
PR_AUC_CI_LOW_MIN = 0.45
TOP20_MIN = 0.50


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    out = _float(value)
    return int(out) if out is not None else None


def _top20(payload: dict[str, Any]) -> float | None:
    for key in ("topk_unique", "topk"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and _int(row.get("k")) == 20:
                return _float(row.get("hit_rate"))
    return None


def _ranking_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(payload)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metrics_ci_unique = payload.get("metrics_ci_unique") if isinstance(payload.get("metrics_ci_unique"), dict) else {}
    metrics_ci = payload.get("metrics_ci") if isinstance(payload.get("metrics_ci"), dict) else {}
    pr_ci = metrics_ci_unique.get("pr_auc") if isinstance(metrics_ci_unique.get("pr_auc"), dict) else {}
    if not pr_ci:
        pr_ci = metrics_ci.get("pr_auc") if isinstance(metrics_ci.get("pr_auc"), dict) else {}
    return {
        "ranking_pr_auc": _float(summary.get("ranking_pr_auc") or metrics.get("pr_auc_unique_key") or metrics.get("pr_auc")),
        "ranking_pr_auc_ci_low": _float(summary.get("ranking_pr_auc_ci_low") or pr_ci.get("low")),
        "ranking_top20_hit_rate": _float(summary.get("ranking_topk_hit_rate") or _top20(payload)),
        "positive_count": _int(summary.get("positive_count") or metrics.get("positive_count_unique_key") or metrics.get("positive_count")),
        "score_col": summary.get("ranking_score_col_used") or metrics.get("probability_score_col_used") or payload.get("score_col"),
    }


def build_packet(
    *,
    a1_queue_json: str | Path = DEFAULT_A1_QUEUE_JSON,
    accuracy_scorecard_json: str | Path = DEFAULT_ACCURACY_SCORECARD_JSON,
    ranking_json: str | Path = DEFAULT_RANKING_JSON,
    set_spec_json: str | Path = DEFAULT_SET_SPEC_JSON,
    repeat_tag: str = DEFAULT_REPEAT_TAG,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    a1_summary = _summary(_read_json(a1_queue_json))
    scorecard_summary = _summary(_read_json(accuracy_scorecard_json))
    ranking_payload = _read_json(ranking_json)
    metrics = _ranking_metrics(ranking_payload)
    set_spec_path = _resolve(set_spec_json)
    ranking_source_artifact = _artifact(ranking_json)
    ranking_summary = _summary(ranking_payload)
    repeat_result_completed = bool(
        ranking_payload
        and (
            repeat_tag in ranking_source_artifact
            or bool(ranking_summary.get("independent_repeat_completed"))
        )
    )

    a1_cleared = (
        a1_summary.get("status") == "a1_accuracy_repair_queue_cleared_claim_locked"
        and bool(a1_summary.get("full_guarded_100k_review_passed"))
        and int(a1_summary.get("open_queue_row_count", 0) or 0) == 0
    )
    ranking_provenance_blockers = [str(item) for item in a1_summary.get("ranking_provenance_blockers") or []]
    repeat_only_blockers = {
        "independent_repeat_missing",
        "label_derived_weight_selection_requires_independent_repeat",
    }
    metric_blockers: list[str] = []
    if metrics["ranking_pr_auc"] is None or metrics["ranking_pr_auc"] < PR_AUC_MIN:
        metric_blockers.append("ranking_pr_auc_below_threshold")
    if metrics["ranking_pr_auc_ci_low"] is None or metrics["ranking_pr_auc_ci_low"] < PR_AUC_CI_LOW_MIN:
        metric_blockers.append("ranking_pr_auc_ci_low_below_threshold")
    if metrics["ranking_top20_hit_rate"] is None or metrics["ranking_top20_hit_rate"] < TOP20_MIN:
        metric_blockers.append("ranking_top20_hit_rate_below_threshold")
    provenance_repeat_ready = bool(
        a1_summary.get("status") == "open_a1_repair_queue"
        and int(a1_summary.get("open_queue_row_count", 0) or 0) == 1
        and set(ranking_provenance_blockers).issubset(repeat_only_blockers)
        and set(ranking_provenance_blockers)
        and not metric_blockers
    )
    a1_ready_for_repeat = a1_cleared or provenance_repeat_ready
    set_spec_available = set_spec_path.exists()
    scorecard_blocked = scorecard_summary.get("status") == "blocked_accuracy_parity"
    launch_ready = a1_ready_for_repeat and set_spec_available and not repeat_result_completed
    result_passed = a1_cleared and set_spec_available and repeat_result_completed and not metric_blockers
    blockers: list[str] = []
    if not a1_ready_for_repeat:
        blockers.append("a1_queue_not_cleared_claim_locked")
    if not set_spec_available:
        blockers.append("set_spec_missing")
    blockers.extend(metric_blockers)

    set_spec_artifact = _artifact(set_spec_json)
    validate_command = (
        "python3 tools/run_external_validation_blind_sets.py "
        f"--tag {repeat_tag} --set-spec-json {set_spec_artifact} --sets set1_core_blind --validate-only"
    )
    run_command = (
        "python3 tools/run_external_validation_blind_sets.py "
        f"--tag {repeat_tag} --set-spec-json {set_spec_artifact} --sets set1_core_blind"
    )
    if result_passed:
        status = "independent_repeat_passed_claim_locked"
    elif repeat_result_completed:
        status = "independent_repeat_completed_metric_blocked"
    elif launch_ready:
        status = "independent_repeat_ready_claim_locked"
    else:
        status = "independent_repeat_blocked"
    return {
        "packet_type": "gpcr_a1_independent_repeat_packet",
        "summary": {
            "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "independent_repeat_ready": launch_ready,
            "independent_repeat_required": True,
            "independent_repeat_completed": repeat_result_completed,
            "independent_repeat_result_passed": result_passed,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "blocker_count": len(blockers),
            "blockers": blockers,
            "a1_queue_status": a1_summary.get("status"),
            "a1_full_guarded_100k_review_passed": bool(a1_summary.get("full_guarded_100k_review_passed")),
            "a1_ready_for_repeat": a1_ready_for_repeat,
            "a1_provenance_repeat_ready": provenance_repeat_ready,
            "a1_ranking_provenance_blockers": ranking_provenance_blockers,
            "accuracy_parity_status": scorecard_summary.get("status"),
            "accuracy_parity_blocked_row_count": int(scorecard_summary.get("blocked_row_count", 0) or 0),
            "scorecard_still_blocks_broad_parity": scorecard_blocked,
            "ranking_pr_auc": metrics["ranking_pr_auc"],
            "ranking_pr_auc_ci_low": metrics["ranking_pr_auc_ci_low"],
            "ranking_top20_hit_rate": metrics["ranking_top20_hit_rate"],
            "positive_count": metrics["positive_count"],
            "score_col": metrics["score_col"],
            "repeat_tag": repeat_tag,
            "set_spec_artifact": set_spec_artifact,
            "ranking_source_artifact": ranking_source_artifact,
            "validate_command": validate_command,
            "run_command": run_command,
            "next_required_step": (
                "Independent repeat completed and cleared the guarded metric thresholds; keep claim promotion false "
                "until the accuracy scorecard, leakage/pose guardrails, and broader review clear."
                if result_passed
                else "Independent repeat completed but metric blockers remain; repair GPCR ranking/pose support before another repeat."
                if repeat_result_completed
                else
                "Run validate_command, then run_command as an independent repeat; regenerate A1 queue and accuracy "
                "scorecard from the repeat result while keeping claim promotion false."
                if launch_ready
                else "Resolve independent-repeat packet blockers before launching another guarded 100k repeat."
            ),
        },
        "acceptance_checks": [
            "repeat result uses a new tag and the frozen coverage-v1 family-balanced set spec",
            "ranking_pr_auc >= 0.55",
            "ranking_pr_auc_ci_low >= 0.45",
            "ranking_top20_hit_rate >= 0.50",
            "no target-identity leakage",
            "no threshold relaxation",
            "claim_promotion_allowed remains false until an independent repeat and broader scorecard review clear",
        ],
        "claim_boundary": {
            "repeat_packet_is_not_claim_authorization": True,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR A1 Independent Repeat Packet",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- independent_repeat_ready: `{str(summary['independent_repeat_ready']).lower()}`",
        f"- independent_repeat_required: `{str(summary['independent_repeat_required']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- blockers: `{', '.join(summary['blockers']) or '-'}`",
        f"- a1_queue_status: `{summary['a1_queue_status']}`",
        f"- accuracy_parity_status: `{summary['accuracy_parity_status']}`",
        f"- ranking_pr_auc: `{summary['ranking_pr_auc']}`",
        f"- ranking_pr_auc_ci_low: `{summary['ranking_pr_auc_ci_low']}`",
        f"- ranking_top20_hit_rate: `{summary['ranking_top20_hit_rate']}`",
        f"- positive_count: `{summary['positive_count']}`",
        f"- repeat_tag: `{summary['repeat_tag']}`",
        "",
        "## Commands",
        "",
        "```bash",
        summary["validate_command"],
        summary["run_command"],
        "```",
        "",
        "## Acceptance Checks",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload["acceptance_checks"])
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the GPCR A1 independent repeat handoff packet.")
    parser.add_argument("--a1-queue-json", default=DEFAULT_A1_QUEUE_JSON)
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--ranking-json", default=DEFAULT_RANKING_JSON)
    parser.add_argument("--set-spec-json", default=DEFAULT_SET_SPEC_JSON)
    parser.add_argument("--repeat-tag", default=DEFAULT_REPEAT_TAG)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_packet(
        a1_queue_json=args.a1_queue_json,
        accuracy_scorecard_json=args.accuracy_scorecard_json,
        ranking_json=args.ranking_json,
        set_spec_json=args.set_spec_json,
        repeat_tag=args.repeat_tag,
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
