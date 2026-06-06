#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SUMMARY_JSON = (
    "runs/external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json"
)
DEFAULT_OUT_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_ci_low_recovery_packet_current.md"
DEFAULT_CI_LOW_THRESHOLD = 0.45
DEFAULT_TOP20_K = 20

STAGE6_FIELDS = [
    "pass",
    "failed_metrics",
    "ranking_pr_auc",
    "ranking_pr_auc_ci_low",
    "ranking_topk_hit_rate",
    "ranking_positive_count",
    "ranking_topk_hit_rate_max_possible",
    "ranking_unique_auc",
    "ranking_score_col_used",
]

RECOMMENDED_NEXT_ACTIONS = [
    "non-leaky positive coverage expansion before re-claiming GPCR 100k readiness",
    "family-held-out scorecard to separate within-family recovery from deployable generalization",
    "bootstrap stability validation for PR-AUC CI-low before any operator promotion",
    "no threshold relaxation/fake pass; keep the operational gate failed until evidence improves",
]

REQUIRED_NEXT_EVIDENCE_TEMPLATE = [
    "add at least {positive_coverage_gap} non-leaky GPCR positive examples before re-claiming",
    "rebuild the blind ranking packet with top20 ceiling >= {top20_ceiling_threshold}",
    "demonstrate ranking_pr_auc_ci_low >= {ci_low_threshold} under the unchanged operational gate",
    "keep claim_promotion_allowed=false until both positive coverage and CI-low gates clear",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _maybe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _metric_name(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("metric", "")).strip()
    return ""


def _failed_metric_rows(failed_metrics: Any) -> list[dict[str, Any]]:
    if not isinstance(failed_metrics, list):
        return []
    return [row for row in failed_metrics if isinstance(row, dict)]


def _threshold_from_failed_metrics(failed_metrics: Any) -> float:
    for row in _failed_metric_rows(failed_metrics):
        if _metric_name(row) == "ranking_pr_auc_ci_low":
            threshold = _maybe_float(row.get("threshold"))
            if threshold is not None:
                return threshold
    return DEFAULT_CI_LOW_THRESHOLD


def _has_failed_metric(failed_metrics: Any, metric: str) -> bool:
    return any(_metric_name(row) == metric for row in _failed_metric_rows(failed_metrics))


def _triage_context(triage_json: Path | None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "triage_json": str(triage_json) if triage_json else None,
        "triage_json_available": False,
        "claim_safe_status": None,
        "candidate_count": None,
        "rejected_candidate_count": None,
    }
    if triage_json is None or not triage_json.exists():
        return context

    payload = _read_json(triage_json)
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        summary = {}
    context.update(
        {
            "triage_json_available": True,
            "claim_safe_status": summary.get("claim_safe_status"),
            "candidate_count": summary.get("candidate_count"),
            "rejected_candidate_count": summary.get("rejected_candidate_count"),
        }
    )
    return context


def _ranking_summary_path(summary_path: Path) -> Path:
    name = summary_path.name
    if name.endswith("_summary.json"):
        return summary_path.with_name(name[: -len("_summary.json")] + "_stage5_ranking_summary.json")
    return summary_path.with_name(summary_path.stem + "_stage5_ranking_summary.json")


def _ranking_rows_path(summary_path: Path) -> Path:
    name = summary_path.name
    if name.endswith("_summary.json"):
        return summary_path.with_name(name[: -len("_summary.json")] + "_stage5_ranking_rows.csv")
    return summary_path.with_name(summary_path.stem + "_stage5_ranking_rows.csv")


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _score_column(stage6: dict[str, Any], ranking_summary: dict[str, Any], ranking_rows: list[dict[str, str]]) -> str:
    direct = _text(stage6.get("ranking_score_col_used"))
    if direct:
        return direct
    metrics = ranking_summary.get("metrics") if isinstance(ranking_summary.get("metrics"), dict) else {}
    for key in ("probability_score_col_used", "score_col", "score_column"):
        value = _text(metrics.get(key) or ranking_summary.get(key))
        if value:
            return value
    for row in ranking_rows:
        for key in row:
            if key.startswith("binding_score_"):
                return key
    return ""


def _positive_rank_diagnostics(
    *,
    stage6: dict[str, Any],
    ranking_summary: dict[str, Any],
    ranking_rows: list[dict[str, str]],
) -> dict[str, Any]:
    score_col = _score_column(stage6, ranking_summary, ranking_rows)
    scored_rows = [row for row in ranking_rows if _maybe_float(row.get(score_col)) is not None] if score_col else []
    ranked_rows = sorted(scored_rows, key=lambda row: float(row[score_col])) if scored_rows else list(ranking_rows)
    positives: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked_rows, start=1):
        if not _is_positive(row):
            continue
        positives.append(
            {
                "rank": int(rank),
                "ligand_id": _text(row.get("ligand_id")),
                "target": _text(row.get("target")),
                "score": _maybe_float(row.get(score_col)) if score_col else None,
                "mean_min_distance_A": _maybe_float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _maybe_float(row.get("reference_binding_kcal_mol")),
            }
        )
    positive_count = int(stage6.get("ranking_positive_count") or len(positives) or 0)
    top20_hits = [row for row in positives if int(row["rank"]) <= 20]
    top20_missing = [row for row in positives if int(row["rank"]) > 20]
    top20_ceiling = _maybe_float(stage6.get("ranking_topk_hit_rate_max_possible"))
    if top20_ceiling is None and positive_count > 0:
        top20_ceiling = float(min(positive_count, 20) / 20.0)
    return {
        "score_column": score_col,
        "ranking_rows_available": bool(ranking_rows),
        "ranking_row_count": int(len(ranking_rows)),
        "positive_count": positive_count,
        "positive_ranks": positives,
        "positive_rank_list": [int(row["rank"]) for row in positives],
        "top20_hit_count": int(len(top20_hits)),
        "top20_positive_hits": top20_hits,
        "top20_missing_positives": top20_missing,
        "top20_hit_rate_max_possible": top20_ceiling,
    }


def _bootstrap_diagnostics(ranking_summary: dict[str, Any]) -> dict[str, Any]:
    ci = ranking_summary.get("metrics_ci") if isinstance(ranking_summary.get("metrics_ci"), dict) else {}
    unique = ci.get("pr_auc_unique_key") if isinstance(ci.get("pr_auc_unique_key"), dict) else {}
    row = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    selected = unique or row
    return {
        "available": bool(selected),
        "source": "pr_auc_unique_key" if unique else ("pr_auc" if row else ""),
        "low": _maybe_float(selected.get("low")) if selected else None,
        "high": _maybe_float(selected.get("high")) if selected else None,
        "mean": _maybe_float(selected.get("mean")) if selected else None,
        "std": _maybe_float(selected.get("std")) if selected else None,
        "valid_bootstrap_n": int(selected.get("n")) if selected and selected.get("n") is not None else None,
    }


def _stage6_summary(stage6: dict[str, Any]) -> dict[str, Any]:
    failed_metrics = stage6.get("failed_metrics", [])
    threshold = _threshold_from_failed_metrics(failed_metrics)
    ci_low = _maybe_float(stage6.get("ranking_pr_auc_ci_low"))
    ci_low_blocker = _has_failed_metric(failed_metrics, "ranking_pr_auc_ci_low") or (
        ci_low is not None and ci_low < threshold
    )

    summary = {field: stage6.get(field) for field in STAGE6_FIELDS}
    summary.update(
        {
            "threshold": threshold,
            "ci_low_blocker": bool(ci_low_blocker),
            "blocker_reason": "ranking_pr_auc_ci_low_below_operational_threshold"
            if ci_low_blocker
            else "ranking_pr_auc_ci_low_meets_operational_threshold",
        }
    )
    return summary


def _coverage_requirement(summary: dict[str, Any]) -> dict[str, Any]:
    ci_low_threshold = _maybe_float(summary.get("threshold")) or DEFAULT_CI_LOW_THRESHOLD
    top20_ceiling_threshold = ci_low_threshold
    observed_positive_count = int(summary.get("ranking_positive_count") or 0)
    observed_ceiling = _maybe_float(summary.get("ranking_topk_hit_rate_max_possible"))
    if observed_ceiling is None:
        observed_ceiling = float(min(observed_positive_count, DEFAULT_TOP20_K) / DEFAULT_TOP20_K)
    minimum_positive_count = int(math.ceil(top20_ceiling_threshold * DEFAULT_TOP20_K))
    positive_coverage_gap = max(0, minimum_positive_count - observed_positive_count)
    ceiling_gap = max(0.0, top20_ceiling_threshold - observed_ceiling)
    ci_low_blocked = bool(summary.get("ci_low_blocker"))

    required_next_evidence = [
        item.format(
            positive_coverage_gap=positive_coverage_gap,
            top20_ceiling_threshold=top20_ceiling_threshold,
            ci_low_threshold=ci_low_threshold,
        )
        for item in REQUIRED_NEXT_EVIDENCE_TEMPLATE
    ]
    return {
        "ci_low_policy": {
            "status": "blocked" if ci_low_blocked else "meets_threshold",
            "metric": "ranking_pr_auc_ci_low",
            "observed": _maybe_float(summary.get("ranking_pr_auc_ci_low")),
            "threshold": ci_low_threshold,
            "claim_promotion_allowed": False,
            "threshold_relaxation_allowed": False,
        },
        "top20_k": DEFAULT_TOP20_K,
        "observed_positive_count": observed_positive_count,
        "minimum_positive_count_for_claim": minimum_positive_count,
        "positive_coverage_gap": positive_coverage_gap,
        "top20_ceiling_observed": observed_ceiling,
        "top20_ceiling_threshold": top20_ceiling_threshold,
        "top20_ceiling_gap_to_threshold": round(ceiling_gap, 12),
        "required_next_evidence": required_next_evidence,
    }


def build_packet(*, summary_json: str | Path, triage_json: str | Path | None = None) -> dict[str, Any]:
    summary_path = _resolve(summary_json)
    triage_path = _resolve(triage_json) if triage_json else None
    payload = _read_json(summary_path)
    stage6 = ((payload.get("stages") or {}).get("stage6_operational_gate") or {})
    if not isinstance(stage6, dict):
        stage6 = {}
    ranking_summary_path = _ranking_summary_path(summary_path)
    ranking_rows_path = _ranking_rows_path(summary_path)
    ranking_summary = _read_json(ranking_summary_path)
    ranking_rows = _read_csv(ranking_rows_path)

    summary = _stage6_summary(stage6)

    return {
        "packet_type": "gpcr_ci_low_recovery_packet",
        "source_summary_json": str(summary_path),
        "source_artifacts": {
            "summary_json": str(summary_path),
            "stage5_ranking_summary_json": str(ranking_summary_path),
            "stage5_ranking_rows_csv": str(ranking_rows_path),
        },
        "summary": summary,
        "rank_diagnostics": _positive_rank_diagnostics(
            stage6=stage6,
            ranking_summary=ranking_summary,
            ranking_rows=ranking_rows,
        ),
        "bootstrap_diagnostics": _bootstrap_diagnostics(ranking_summary),
        "claim_coverage_requirement": _coverage_requirement(summary),
        "input_context": {
            "summary_json": str(summary_path),
            **_triage_context(triage_path),
        },
        "recovery_interpretation": {
            "claim_safe": False,
            "comparison_only": True,
            "claim_promotion_allowed": False,
        },
        "recommended_next_actions": list(RECOMMENDED_NEXT_ACTIONS),
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    ranks = payload.get("rank_diagnostics", {})
    boot = payload.get("bootstrap_diagnostics", {})
    requirement = payload.get("claim_coverage_requirement", {})
    ci_low_policy = requirement.get("ci_low_policy", {}) if isinstance(requirement.get("ci_low_policy"), dict) else {}
    ci_low_status = "blocker" if summary.get("ci_low_blocker") else "pass"
    metric_rows = [
        ("ranking_pr_auc", summary.get("ranking_pr_auc"), "", "observed"),
        ("ranking_pr_auc_ci_low", summary.get("ranking_pr_auc_ci_low"), summary.get("threshold"), ci_low_status),
        ("ranking_topk_hit_rate", summary.get("ranking_topk_hit_rate"), "", "observed"),
        (
            "ranking_topk_hit_rate_max_possible",
            summary.get("ranking_topk_hit_rate_max_possible"),
            "",
            "coverage ceiling",
        ),
        ("ranking_positive_count", summary.get("ranking_positive_count"), "", "coverage"),
        ("ranking_unique_auc", summary.get("ranking_unique_auc"), "", "diagnostic"),
        ("ranking_score_col_used", summary.get("ranking_score_col_used"), "", "score source"),
    ]
    recovery = payload["recovery_interpretation"]
    context = payload["input_context"]

    lines = [
        "# GPCR CI-low Recovery Packet",
        "",
        "## Metric Table",
        "",
        "| metric | value | threshold | status |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| {name} | {_fmt(value)} | {_fmt(threshold)} | {status} |" for name, value, threshold, status in metric_rows)
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            f"- stage6_pass={_fmt(summary.get('pass'))}",
            f"- ci_low_blocker={_fmt(summary.get('ci_low_blocker'))}",
            f"- claim_safe={_fmt(recovery.get('claim_safe'))}",
            f"- comparison_only={_fmt(recovery.get('comparison_only'))}",
            f"- claim_promotion_allowed={_fmt(recovery.get('claim_promotion_allowed'))}",
            "- interpretation: recovery work may be compared diagnostically, but this packet does not authorize a GPCR 100k claim.",
            "",
            "## Claim Coverage Requirement",
            "",
            f"- ci_low_policy_status={_fmt(ci_low_policy.get('status'))}",
            f"- ci_low_threshold={_fmt(ci_low_policy.get('threshold'))}",
            f"- threshold_relaxation_allowed={_fmt(ci_low_policy.get('threshold_relaxation_allowed'))}",
            f"- observed_positive_count={_fmt(requirement.get('observed_positive_count'))}",
            f"- minimum_positive_count_for_claim={_fmt(requirement.get('minimum_positive_count_for_claim'))}",
            f"- positive_coverage_gap={_fmt(requirement.get('positive_coverage_gap'))}",
            f"- top20_ceiling_observed={_fmt(requirement.get('top20_ceiling_observed'))}",
            f"- top20_ceiling_threshold={_fmt(requirement.get('top20_ceiling_threshold'))}",
            f"- top20_ceiling_gap_to_threshold={_fmt(requirement.get('top20_ceiling_gap_to_threshold'))}",
            "",
            "Required next evidence:",
            "",
            *[f"- {item}" for item in requirement.get("required_next_evidence", [])],
            "",
            "## Input Context",
            "",
            f"- summary_json={context.get('summary_json')}",
            f"- triage_json_available={_fmt(context.get('triage_json_available'))}",
            f"- claim_safe_status={_fmt(context.get('claim_safe_status'))}",
            f"- candidate_count={_fmt(context.get('candidate_count'))}",
            f"- rejected_candidate_count={_fmt(context.get('rejected_candidate_count'))}",
            "",
            "## Rank And Bootstrap Diagnostics",
            "",
            f"- positive_ranks={_fmt(ranks.get('positive_rank_list'))}",
            f"- top20_hit_count={_fmt(ranks.get('top20_hit_count'))}",
            f"- top20_hit_rate_max_possible={_fmt(ranks.get('top20_hit_rate_max_possible'))}",
            f"- top20_missing_positives={_fmt([row.get('ligand_id') for row in ranks.get('top20_missing_positives', [])])}",
            f"- bootstrap_source={_fmt(boot.get('source'))}",
            f"- bootstrap_valid_n={_fmt(boot.get('valid_bootstrap_n'))}",
            f"- bootstrap_pr_auc_low={_fmt(boot.get('low'))}",
            f"- bootstrap_pr_auc_high={_fmt(boot.get('high'))}",
            f"- bootstrap_pr_auc_mean={_fmt(boot.get('mean'))}",
            f"- bootstrap_pr_auc_std={_fmt(boot.get('std'))}",
            "",
            "## Recommended Next Actions",
            "",
        ]
    )
    lines.extend(f"- {action}" for action in payload["recommended_next_actions"])
    lines.append("")
    return "\n".join(lines)


def write_outputs(*, summary_json: str | Path, triage_json: str | Path | None, out_json: str | Path, out_md: str | Path) -> dict[str, Any]:
    payload = build_packet(summary_json=summary_json, triage_json=triage_json)
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-facing GPCR stage6 PR-AUC CI-low recovery packet.")
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--triage-json", default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        summary_json=args.summary_json,
        triage_json=args.triage_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
