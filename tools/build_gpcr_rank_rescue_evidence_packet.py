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

DEFAULT_RANKING_JSON = "runs/gpcr_coverage_v2_supervised_logreg_l2_c10_shadow_replay_ranking_summary_current.json"
DEFAULT_REPLAY_JSON = "runs/gpcr_coverage_v2_supervised_logreg_l2_c10_shadow_replay_summary_current.json"
DEFAULT_WEIGHT_SPEC_JSON = "runs/gpcr_coverage_v2_supervised_logreg_l2_c10_feature_weights_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_rank_rescue_evidence_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_rank_rescue_evidence_packet_current.md"

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


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass"}:
        return True
    if text in {"false", "0", "no", "fail"}:
        return False
    return None


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
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metrics_ci_unique = payload.get("metrics_ci_unique") if isinstance(payload.get("metrics_ci_unique"), dict) else {}
    metrics_ci = payload.get("metrics_ci") if isinstance(payload.get("metrics_ci"), dict) else {}
    pr_ci = metrics_ci_unique.get("pr_auc") if isinstance(metrics_ci_unique.get("pr_auc"), dict) else {}
    if not pr_ci:
        pr_ci = metrics_ci.get("pr_auc") if isinstance(metrics_ci.get("pr_auc"), dict) else {}
    return {
        "ranking_pr_auc": _float(metrics.get("pr_auc_unique_key") or metrics.get("pr_auc")),
        "ranking_pr_auc_ci_low": _float(pr_ci.get("low")),
        "ranking_topk_hit_rate": _top20(payload),
        "positive_count": _int(metrics.get("positive_count_unique_key") or metrics.get("positive_count")),
        "ranking_score_col_used": metrics.get("probability_score_col_used") or payload.get("score_col"),
        "worst_positive_global_rank": None,
        "worst_positive_within_target_rank": None,
    }


def _read_optional_json(path_like: str | Path) -> dict[str, Any]:
    if not str(path_like or "").strip():
        return {}
    path = _resolve(path_like)
    if not path.exists():
        return {}
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def _crossfit_validation_ready(summary: dict[str, Any]) -> bool:
    return bool(
        _bool(summary.get("out_of_fold_scoring")) is True
        and _bool(summary.get("same_row_label_leakage")) is False
        and _bool(summary.get("same_ligand_label_leakage")) is False
        and _bool(summary.get("score_feature_policy_pass")) is True
        and _bool(summary.get("validation_claim_promotion_allowed")) is True
    )


def build_packet(
    *,
    ranking_json: str | Path = DEFAULT_RANKING_JSON,
    replay_json: str | Path = DEFAULT_REPLAY_JSON,
    weight_spec_json: str | Path = DEFAULT_WEIGHT_SPEC_JSON,
    independent_repeat_completed: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    ranking_payload = _read_json(ranking_json)
    replay_summary = _summary(_read_json(replay_json))
    weight_payload = _read_optional_json(weight_spec_json)
    metrics = _ranking_metrics(ranking_payload)

    blockers: list[str] = []
    if metrics["ranking_pr_auc"] is None or metrics["ranking_pr_auc"] < PR_AUC_MIN:
        blockers.append("ranking_pr_auc_below_threshold")
    if metrics["ranking_pr_auc_ci_low"] is None or metrics["ranking_pr_auc_ci_low"] < PR_AUC_CI_LOW_MIN:
        blockers.append("ranking_pr_auc_ci_low_below_threshold")
    if metrics["ranking_topk_hit_rate"] is None or metrics["ranking_topk_hit_rate"] < TOP20_MIN:
        blockers.append("topk_hit_rate_below_threshold")
    crossfit_ready = _crossfit_validation_ready(replay_summary)
    raw_label_derived = (
        _bool(replay_summary.get("diagnostic_weight_search_used_labels")) is True
        or _bool(weight_payload.get("diagnostic_weight_search_used_labels")) is True
    )
    label_derived = bool(raw_label_derived and not crossfit_ready)
    if label_derived:
        blockers.append("label_derived_weight_selection_requires_independent_repeat")
    if not independent_repeat_completed:
        blockers.append("independent_repeat_missing")
    validation_claim_allowed = bool(
        _bool(replay_summary.get("validation_claim_promotion_allowed")) is True
        or _bool(replay_summary.get("claim_promotion_allowed")) is True
    )
    if not validation_claim_allowed:
        blockers.append("claim_promotion_not_allowed")
    blockers = sorted(set(blockers))
    metric_blockers = {
        "ranking_pr_auc_below_threshold",
        "ranking_pr_auc_ci_low_below_threshold",
        "topk_hit_rate_below_threshold",
    }
    metric_thresholds_pass = not any(blocker in metric_blockers for blocker in blockers)
    claim_allowed = bool(
        metric_thresholds_pass
        and independent_repeat_completed
        and validation_claim_allowed
        and not label_derived
    )
    if metric_thresholds_pass and claim_allowed:
        status = "metric_pass_claim_ready"
    elif metric_thresholds_pass:
        status = "metric_pass_claim_locked"
    else:
        status = "metric_blocked_claim_locked"
    source_artifacts = [_artifact(ranking_json), _artifact(replay_json)]
    weight_artifact = _artifact(weight_spec_json) if str(weight_spec_json or "").strip() else ""
    if weight_artifact:
        source_artifacts.append(weight_artifact)
    return {
        "packet_type": "gpcr_rank_rescue_evidence_packet",
        "summary": {
            "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "ranking_pr_auc": metrics["ranking_pr_auc"],
            "ranking_pr_auc_ci_low": metrics["ranking_pr_auc_ci_low"],
            "ranking_topk_hit_rate": metrics["ranking_topk_hit_rate"],
            "positive_count": metrics["positive_count"],
            "ranking_score_col_used": metrics["ranking_score_col_used"],
            "worst_positive_global_rank": metrics["worst_positive_global_rank"],
            "worst_positive_within_target_rank": metrics["worst_positive_within_target_rank"],
            "metric_thresholds_pass": metric_thresholds_pass,
            "independent_repeat_completed": bool(independent_repeat_completed),
            "crossfit_validation_ready": crossfit_ready,
            "raw_label_derived_weight_selection": raw_label_derived,
            "label_derived_weight_selection": label_derived,
            "validation_claim_promotion_allowed": validation_claim_allowed,
            "claim_promotion_allowed": claim_allowed,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "blockers": blockers,
            "ranking_source_artifact": _artifact(ranking_json),
            "replay_source_artifact": _artifact(replay_json),
            "weight_spec_artifact": weight_artifact,
            "next_required_step": (
                "GPCR ranking metrics pass on independent repeat with out-of-fold supervised evidence; keep "
                "router/platform deployment separate from this ranking-parity claim."
                if claim_allowed
                else (
                    "Metric thresholds are green, but keep the GPCR ranking claim blocked until a fresh independent "
                    "repeat reproduces the result without using current evaluation labels for weight selection."
                    if metric_thresholds_pass
                    else "Repair GPCR ranking metrics before launching another independent repeat."
                )
            ),
        },
        "claim_boundary": {
            "metric_pass_is_not_claim_authorization": not claim_allowed,
            "claim_promotion_allowed": claim_allowed,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "requires_independent_repeat_before_claim": not bool(independent_repeat_completed),
        },
        "source_artifacts": source_artifacts,
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Rank Rescue Evidence Packet",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- ranking_pr_auc: `{summary['ranking_pr_auc']}`",
        f"- ranking_pr_auc_ci_low: `{summary['ranking_pr_auc_ci_low']}`",
        f"- ranking_topk_hit_rate: `{summary['ranking_topk_hit_rate']}`",
        f"- metric_thresholds_pass: `{str(summary['metric_thresholds_pass']).lower()}`",
        f"- label_derived_weight_selection: `{str(summary['label_derived_weight_selection']).lower()}`",
        f"- independent_repeat_completed: `{str(summary['independent_repeat_completed']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- blockers: `{', '.join(summary['blockers']) or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed GPCR rank rescue evidence packet.")
    parser.add_argument("--ranking-json", default=DEFAULT_RANKING_JSON)
    parser.add_argument("--replay-json", default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--weight-spec-json", default=DEFAULT_WEIGHT_SPEC_JSON)
    parser.add_argument("--independent-repeat-completed", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_packet(
        ranking_json=args.ranking_json,
        replay_json=args.replay_json,
        weight_spec_json=args.weight_spec_json,
        independent_repeat_completed=bool(args.independent_repeat_completed),
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
