#!/usr/bin/env python3
"""Audit broad local GPCR hard-decoy candidates for Phase 3 closure.

Read-only: this expands beyond retained top-50 candidate sweeps and inspects
local GPCR eval/ranking CSV artifacts plus matching evaluator summaries. It
does not run scoring, regenerate decoys, relax thresholds, edit suite inputs,
or promote a GPCR claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_GLOBS = (
    "runs/*gpcr*eval_unique_current.csv",
    "runs/*gpcr*eval_frozen*_unique_top_rank_retained_top50_current.csv",
    "runs/*gpcr*ranking_unique*current.csv",
    "runs/*gpcr*ranking_rows*current.csv",
    "runs/*gpcr*scores_current.csv",
)
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_broad_local_candidate_audit_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_broad_local_candidate_audit_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_broad_local_candidate_audit_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_broad_local_candidate_audit"
SCHEMA_VERSION = "gpcr_hard_decoy_broad_local_candidate_audit_v1"

CI_LOW_MIN = 0.45
TOP20_MIN = 0.20
DEFAULT_BOOTSTRAP_N = 64
DEFAULT_BOOTSTRAP_SEED = 31

REQUIRED_TARGETS = {
    "CHEMBL217_DRD2_HUMAN": "DRD2",
    "CHEMBL224_HTR2A_HUMAN": "HTR2A",
    "CHEMBL233_OPRM1_HUMAN": "OPRM1",
}

SCORE_COLUMN_PRIORITY = (
    "score_value",
    "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow",
    "binding_score_composite_v7_coverage_v2_adaptive_rank_rescue_shadow",
    "binding_score_composite_v7_residual_shadow",
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "binding_score",
    "score",
)

ANCHOR_COLUMNS = (
    "mean_min_distance_A",
    "anchor_distance_a",
    "native_anchor_mean_distance_a",
)

CLAIM_BOUNDARY = (
    "GPCR hard-decoy broad local candidate audit only; it inspects local GPCR CSV artifacts and matching "
    "summary metrics for Phase 3 closure evidence. It does not run scoring, regenerate decoys, edit suite "
    "inputs, relax thresholds, promote a GPCR claim, fetch external data, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "suite_input_write_allowed": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "candidate_path",
    "summary_json",
    "candidate_status",
    "metric_gate_ready",
    "ranking_pr_auc_ci_low",
    "ranking_pr_auc_ci_low_source",
    "top20_hit_rate",
    "top20_hit_rate_source",
    "metric_blockers",
    "row_count",
    "positive_count",
    "score_column_used",
    "target_id",
    "target_status",
    "target_green",
    "retained_target_row_count",
    "retained_positive_count",
    "top_decoy_retained_count",
    "positive_target_rank",
    "decoys_above_positive_count",
    "positive_anchor_distance_a",
    "top_decoy_anchor_distance_a",
    "anchor_margin_a",
    "top_decoy_ligand_id",
    "blockers",
    "execution_enabled",
    "external_state_mutated",
    "scoring_execution_enabled",
    "threshold_relaxation_enabled",
    "suite_input_write_allowed",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path | None) -> str:
    if path_like is None:
        return ""
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _glob_paths(patterns: Sequence[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        path_pattern = Path(pattern)
        matches: Iterable[Path]
        if path_pattern.is_absolute():
            matches = Path("/").glob(str(path_pattern).lstrip("/"))
        else:
            matches = ROOT.glob(pattern)
        for path in sorted(matches):
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            paths.append(path)
    return paths


def _summary_path_candidates(path: Path) -> list[Path]:
    name = path.name
    replacements = (
        ("_eval_unique_current.csv", "_eval_current.json"),
        ("_eval_detail_current.csv", "_eval_current.json"),
        ("_eval_frozen_r2_unique_top_rank_retained_top50_current.csv", "_eval_frozen_r2_current.json"),
        ("_eval_frozen_r2_detail_top_rank_retained_top50_current.csv", "_eval_frozen_r2_current.json"),
        ("_ranking_unique_top_rank_retained_top50_current.csv", "_ranking_summary_current.json"),
        ("_ranking_rows_top_rank_retained_top50_current.csv", "_ranking_summary_current.json"),
        ("_stage5_ranking_unique_top_rank_retained_top50_current.csv", "_stage5_ranking_summary.json"),
        ("_stage5_ranking_rows_top_rank_retained_top50_current.csv", "_stage5_ranking_summary.json"),
        ("_ranking_eval_unique_top_rank_retained_top50_current.csv", "_ranking_eval_current.json"),
        ("_ranking_eval_rows_top_rank_retained_top50_current.csv", "_ranking_eval_current.json"),
        ("_scores_current.csv", "_summary_current.json"),
        ("_scores_top_rank_retained_top50_current.csv", "_summary_current.json"),
    )
    candidates: list[Path] = []
    for old, new in replacements:
        if name.endswith(old):
            candidates.append(path.with_name(name[: -len(old)] + new))
    stem = path.stem.replace("_top_rank_retained_top50_current", "")
    candidates.extend(
        [
            path.with_name(stem + "_summary_current.json"),
            path.with_name(stem + "_ranking_summary_current.json"),
            path.with_name(stem + "_ranking_eval_current.json"),
            path.with_name(stem + "_eval_current.json"),
        ]
    )
    deduped: list[Path] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _find_summary(path: Path) -> tuple[Path | None, dict[str, Any]]:
    for candidate in _summary_path_candidates(path):
        if candidate.exists():
            return candidate, _read_json(candidate)
    return None, {}


def _top20_hit_rate(summary: dict[str, Any]) -> float | None:
    for key in ("topk_unique", "topk", "topk_ood_unique", "topk_ood"):
        rows = summary.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            k = _float(row.get("k"))
            if k is not None and int(k) == 20:
                return _float(row.get("hit_rate"))
    return None


def _ranking_pr_auc_ci_low(summary: dict[str, Any]) -> float | None:
    candidate_metric_names = ("pr_auc", "pr_auc_unique_key", "pr_auc_ood_unique_key")
    for key in ("metrics_ci_unique", "metrics_ci", "metrics_ci_ood_unique", "metrics_ci_ood"):
        metrics_ci = summary.get(key)
        if not isinstance(metrics_ci, dict):
            continue
        for metric_name in candidate_metric_names:
            pr_auc = metrics_ci.get(metric_name)
            if isinstance(pr_auc, dict):
                value = _float(pr_auc.get("low"))
                if value is not None:
                    return value
    return None


def _score_from_row(row: dict[str, Any], fieldnames: Sequence[str]) -> tuple[float | None, str]:
    choices: list[str] = []
    score_col = _text(row.get("score_col"))
    if score_col:
        choices.append(score_col)
    choices.extend(SCORE_COLUMN_PRIORITY)
    for column in choices:
        if column not in fieldnames:
            continue
        value = _float(row.get(column))
        if value is not None:
            return value, column
    return None, ""


def _anchor_distance(row: dict[str, Any]) -> float | None:
    for column in ANCHOR_COLUMNS:
        value = _float(row.get(column))
        if value is not None:
            return value
    return None


def _read_candidate_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], set[str]] | None:
    grouped: dict[str, list[dict[str, Any]]] = {target: [] for target in REQUIRED_TARGETS}
    rows: list[dict[str, Any]] = []
    score_columns: set[str] = set()
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            required = {"target", "ligand_id", "is_binder"}
            if not required.issubset(fieldnames):
                return None
            for row in reader:
                score, score_column = _score_from_row(row, fieldnames)
                if score is None:
                    continue
                copied = dict(row)
                copied["_score"] = score
                copied["_score_column"] = score_column
                copied["_is_binder"] = _bool(row.get("is_binder"))
                rows.append(copied)
                if score_column:
                    score_columns.add(score_column)
                target = _text(row.get("target"))
                if target in grouped:
                    grouped[target].append(copied)
    except OSError:
        return None
    return rows, grouped, score_columns


def _average_precision(labels: np.ndarray, scores: np.ndarray, *, lower_better: bool) -> float | None:
    y = labels.astype(int)
    pos_count = int(np.sum(y == 1))
    if pos_count <= 0:
        return None
    order = np.argsort(scores if lower_better else -scores, kind="mergesort")
    ranked = y[order]
    hits = np.cumsum(ranked == 1)
    ranks = np.arange(1, ranked.size + 1, dtype=np.float64)
    precision_at_hits = hits[ranked == 1] / ranks[ranked == 1]
    if precision_at_hits.size <= 0:
        return None
    return float(np.sum(precision_at_hits) / float(pos_count))


def _direct_metric_estimate(
    rows: list[dict[str, Any]],
    *,
    lower_better: bool,
    bootstrap_n: int,
    bootstrap_seed: int,
) -> tuple[float | None, float | None, dict[str, Any]]:
    if not rows:
        return None, None, {"metric_estimate_status": "no_rows"}
    labels = np.asarray([1 if row["_is_binder"] else 0 for row in rows], dtype=np.int64)
    scores = np.asarray([float(row["_score"]) for row in rows], dtype=np.float64)
    pos_count = int(np.sum(labels == 1))
    neg_count = int(np.sum(labels == 0))
    if pos_count <= 0 or neg_count <= 0:
        return None, None, {
            "metric_estimate_status": "missing_positive_or_negative",
            "positive_count": pos_count,
            "negative_count": neg_count,
        }

    order = np.argsort(scores if lower_better else -scores, kind="mergesort")
    ranked = labels[order]
    topk = int(min(20, ranked.size))
    top20 = float(np.mean(ranked[:topk] == 1)) if topk > 0 else None
    rng = np.random.default_rng(int(bootstrap_seed))
    pr_values: list[float] = []
    for _ in range(int(max(0, bootstrap_n))):
        idx = rng.integers(0, labels.size, size=labels.size)
        sampled_labels = labels[idx]
        if int(np.sum(sampled_labels == 1)) <= 0 or int(np.sum(sampled_labels == 0)) <= 0:
            continue
        sampled_ap = _average_precision(sampled_labels, scores[idx], lower_better=lower_better)
        if sampled_ap is not None:
            pr_values.append(sampled_ap)
    if pr_values:
        ci_low = float(np.percentile(np.asarray(pr_values, dtype=np.float64), 2.5))
    else:
        ci_low = None
    diagnostics = {
        "metric_estimate_status": "direct_bootstrap_ready" if ci_low is not None else "direct_bootstrap_unavailable",
        "positive_count": pos_count,
        "negative_count": neg_count,
        "bootstrap_n_requested": int(max(0, bootstrap_n)),
        "bootstrap_n_valid": len(pr_values),
    }
    return ci_low, top20, diagnostics


def _target_assessment(target: str, rows: list[dict[str, Any]], *, lower_better: bool) -> dict[str, Any]:
    target_id = REQUIRED_TARGETS[target]
    blockers: list[str] = []
    if not rows:
        blockers.append("target_rows_missing")
        return {
            "target_id": target_id,
            "target_source_id": target,
            "target_status": "missing",
            "target_green": False,
            "retained_target_row_count": 0,
            "retained_positive_count": 0,
            "top_decoy_retained_count": 0,
            "positive_target_rank": None,
            "decoys_above_positive_count": None,
            "positive_anchor_distance_a": None,
            "top_decoy_anchor_distance_a": None,
            "anchor_margin_a": None,
            "top_decoy_ligand_id": "",
            "blockers": blockers,
        }

    ranked = sorted(rows, key=lambda row: row["_score"], reverse=not lower_better)
    positives = [row for row in ranked if bool(row["_is_binder"])]
    decoys = [row for row in ranked if not bool(row["_is_binder"])]
    first_positive = positives[0] if positives else None
    top_decoy = decoys[0] if decoys else None
    positive_rank = ranked.index(first_positive) + 1 if first_positive is not None else None
    decoys_above = None if positive_rank is None else sum(1 for row in ranked[: positive_rank - 1] if not row["_is_binder"])
    positive_anchor = None if first_positive is None else _anchor_distance(first_positive)
    top_decoy_anchor = None if top_decoy is None else _anchor_distance(top_decoy)
    anchor_margin = None if positive_anchor is None or top_decoy_anchor is None else top_decoy_anchor - positive_anchor

    if first_positive is None:
        blockers.append("positive_missing_from_candidate_rows")
    if top_decoy is None:
        blockers.append("top_decoy_missing_from_candidate_rows")
    if decoys_above is None:
        blockers.append("decoys_above_positive_count_missing")
    elif decoys_above != 0:
        blockers.append("decoys_above_positive_present")
    if positive_anchor is None:
        blockers.append("positive_anchor_distance_missing")
    if top_decoy_anchor is None:
        blockers.append("top_decoy_anchor_distance_missing")
    if anchor_margin is not None and anchor_margin < 0.0:
        blockers.append("decoy_over_anchored_vs_positive")

    return {
        "target_id": target_id,
        "target_source_id": target,
        "target_status": "green" if not blockers else "blocked",
        "target_green": not blockers,
        "retained_target_row_count": len(ranked),
        "retained_positive_count": len(positives),
        "top_decoy_retained_count": len(decoys),
        "positive_target_rank": positive_rank,
        "decoys_above_positive_count": decoys_above,
        "positive_anchor_distance_a": positive_anchor,
        "top_decoy_anchor_distance_a": top_decoy_anchor,
        "anchor_margin_a": anchor_margin,
        "top_decoy_ligand_id": _text(top_decoy.get("ligand_id")) if top_decoy is not None else "",
        "blockers": blockers,
    }


def _candidate_assessment(path: Path, *, bootstrap_n: int, bootstrap_seed: int) -> dict[str, Any] | None:
    read = _read_candidate_rows(path)
    if read is None:
        return None
    rows, grouped, score_columns = read
    if not rows:
        return None
    summary_path, summary = _find_summary(path)
    lower_better = bool(summary.get("lower_better", True))

    summary_ci_low = _ranking_pr_auc_ci_low(summary)
    summary_top20 = _top20_hit_rate(summary)
    direct_ci_low: float | None = None
    direct_top20: float | None = None
    direct_diagnostics: dict[str, Any] = {}
    if summary_ci_low is None or summary_top20 is None:
        direct_ci_low, direct_top20, direct_diagnostics = _direct_metric_estimate(
            rows,
            lower_better=lower_better,
            bootstrap_n=bootstrap_n,
            bootstrap_seed=bootstrap_seed,
        )

    ci_low = summary_ci_low if summary_ci_low is not None else direct_ci_low
    top20 = summary_top20 if summary_top20 is not None else direct_top20
    ci_source = "summary_json" if summary_ci_low is not None else direct_diagnostics.get("metric_estimate_status", "")
    top20_source = "summary_json" if summary_top20 is not None else direct_diagnostics.get("metric_estimate_status", "")

    metric_blockers: list[str] = []
    if ci_low is None:
        metric_blockers.append("ranking_pr_auc_ci_low_missing")
    elif ci_low < CI_LOW_MIN:
        metric_blockers.append("ranking_pr_auc_ci_low_below_gate")
    if top20 is None:
        metric_blockers.append("top20_hit_rate_missing")
    elif top20 < TOP20_MIN:
        metric_blockers.append("top20_hit_rate_below_gate")

    targets = [_target_assessment(target, grouped[target], lower_better=lower_better) for target in REQUIRED_TARGETS]
    target_green_count = sum(1 for row in targets if row["target_green"])
    target_blocker_count = sum(len(row["blockers"]) for row in targets)
    metric_gate_ready = not metric_blockers
    closure_ready = bool(metric_gate_ready and target_green_count == len(REQUIRED_TARGETS))

    score_column_used = ",".join(sorted(score_columns))
    return {
        "candidate_path": _display(path),
        "summary_json": _display(summary_path),
        "candidate_status": "closure_candidate_ready" if closure_ready else "blocked",
        "closure_candidate_ready": closure_ready,
        "metric_gate_ready": metric_gate_ready,
        "ranking_pr_auc_ci_low": ci_low,
        "ranking_pr_auc_ci_low_source": ci_source,
        "top20_hit_rate": top20,
        "top20_hit_rate_source": top20_source,
        "metric_blockers": metric_blockers,
        "row_count": len(rows),
        "positive_count": sum(1 for row in rows if row["_is_binder"]),
        "score_column_used": score_column_used,
        "lower_better": lower_better,
        "direct_metric_diagnostics": direct_diagnostics,
        "target_green_count": target_green_count,
        "target_blocker_count": target_blocker_count,
        "targets": targets,
        **_READ_ONLY_FLAGS,
    }


def build_gpcr_hard_decoy_broad_local_candidate_audit(
    *,
    candidate_globs: Sequence[str] | None = None,
    bootstrap_n: int = DEFAULT_BOOTSTRAP_N,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    patterns = tuple(candidate_globs or DEFAULT_CANDIDATE_GLOBS)
    paths = _glob_paths(patterns)
    candidates = [
        candidate
        for path in paths
        if (candidate := _candidate_assessment(path, bootstrap_n=bootstrap_n, bootstrap_seed=bootstrap_seed)) is not None
    ]
    closure_candidates = [row for row in candidates if row["closure_candidate_ready"]]
    best = max(
        candidates,
        key=lambda row: (
            int(row["metric_gate_ready"]),
            int(row["target_green_count"]),
            -int(row["target_blocker_count"]),
            int(row["row_count"]),
        ),
        default={},
    )
    status = (
        "gpcr_hard_decoy_broad_local_candidate_audit_closure_candidate_ready"
        if closure_candidates
        else "blocked_gpcr_hard_decoy_broad_local_candidate_audit_no_closure_candidate"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "gpcr_actual_closure_ready": bool(closure_candidates),
        "candidate_globs": list(patterns),
        "candidate_count": len(candidates),
        "closure_candidate_count": len(closure_candidates),
        "best_candidate_path": best.get("candidate_path", ""),
        "best_candidate_metric_gate_ready": bool(best.get("metric_gate_ready") is True),
        "best_candidate_target_green_count": int(best.get("target_green_count", 0) or 0),
        "best_candidate_metric_blockers": list(best.get("metric_blockers", []) or []),
        "required_target_count": len(REQUIRED_TARGETS),
        "ci_low_min": CI_LOW_MIN,
        "top20_min": TOP20_MIN,
        "bootstrap_n_for_missing_summary_metrics": int(max(0, bootstrap_n)),
        "bootstrap_seed_for_missing_summary_metrics": int(bootstrap_seed),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the closure candidate as read-only evidence for the GPCR hard-decoy suite input review, then rerun the suite report."
            if closure_candidates
            else "No local GPCR eval/ranking artifact closes all Phase 3 hard-decoy conditions; run or restore a replay that moves each required target positive above every decoy and restores nonnegative anchor margins."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "candidates": candidates,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for candidate in candidates:
            for target in candidate["targets"]:
                row = {
                    **{key: candidate.get(key) for key in _CSV_COLUMNS},
                    **target,
                    "blockers": target["blockers"],
                    "metric_blockers": candidate["metric_blockers"],
                }
                writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Broad Local Candidate Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- gpcr_actual_closure_ready: `{str(summary['gpcr_actual_closure_ready']).lower()}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- closure_candidate_count: `{summary['closure_candidate_count']}`",
        f"- best_candidate_path: `{summary['best_candidate_path'] or '(none)'}`",
        f"- best_candidate_metric_gate_ready: `{str(summary['best_candidate_metric_gate_ready']).lower()}`",
        f"- best_candidate_target_green_count: `{summary['best_candidate_target_green_count']}` / `{summary['required_target_count']}`",
        "",
        "| candidate | metric gate | target green | CI-low | top20 | status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for candidate in sorted(
        payload["candidates"],
        key=lambda row: (int(row["metric_gate_ready"]), int(row["target_green_count"]), int(row["row_count"])),
        reverse=True,
    )[:20]:
        lines.append(
            "| `{path}` | `{metric}` | {green} | `{ci}` | `{top20}` | `{status}` |".format(
                path=candidate["candidate_path"],
                metric=str(candidate["metric_gate_ready"]).lower(),
                green=candidate["target_green_count"],
                ci=_fmt(candidate["ranking_pr_auc_ci_low"]),
                top20=_fmt(candidate["top20_hit_rate"]),
                status=candidate["candidate_status"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit broad local GPCR hard-decoy candidates for closure evidence.")
    parser.add_argument(
        "--candidate-glob",
        action="append",
        dest="candidate_globs",
        help="Candidate glob to inspect. Repeat to add multiple globs. Defaults to broad local GPCR eval/ranking globs.",
    )
    parser.add_argument("--bootstrap-n", type=int, default=DEFAULT_BOOTSTRAP_N)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_gpcr_hard_decoy_broad_local_candidate_audit(
        candidate_globs=args.candidate_globs,
        bootstrap_n=args.bootstrap_n,
        bootstrap_seed=args.bootstrap_seed,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["candidates"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
