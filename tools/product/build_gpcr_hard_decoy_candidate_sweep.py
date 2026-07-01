#!/usr/bin/env python3
"""Sweep local GPCR hard-decoy replay candidates for actual closure evidence.

Read-only: this searches current retained top-rank GPCR artifacts and checks
the fixed Phase 3 gate:

* ranking_pr_auc_ci_low >= 0.45
* top20_hit_rate >= 0.20
* every required target has decoys_above_positive_count == 0
* every required target's positive is not out-anchored by its best decoy

It does not run scoring, regenerate rows, copy restored data, relax thresholds,
or promote a GPCR claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_GLOB = "runs/*top_rank_retained_top50_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_candidate_sweep_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_candidate_sweep_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_candidate_sweep_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_candidate_sweep"
SCHEMA_VERSION = "gpcr_hard_decoy_candidate_sweep_v1"

CI_LOW_MIN = 0.45
TOP20_MIN = 0.20

REQUIRED_TARGETS = {
    "CHEMBL217_DRD2_HUMAN": "DRD2",
    "CHEMBL224_HTR2A_HUMAN": "HTR2A",
    "CHEMBL233_OPRM1_HUMAN": "OPRM1",
}

CLAIM_BOUNDARY = (
    "GPCR hard-decoy candidate sweep only; it inspects local retained ranking artifacts and matching summary "
    "metrics for closure evidence. It does not run scoring, regenerate decoys, restore files, relax thresholds, "
    "promote a broad GPCR claim, fetch external data, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "candidate_path",
    "summary_json",
    "candidate_status",
    "metric_gate_ready",
    "ranking_pr_auc_ci_low",
    "top20_hit_rate",
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
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


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


def _summary_path_candidates(path: Path) -> list[Path]:
    name = path.name
    replacements = (
        ("_ranking_unique_top_rank_retained_top50_current.csv", "_ranking_summary_current.json"),
        ("_ranking_rows_top_rank_retained_top50_current.csv", "_ranking_summary_current.json"),
        ("_stage5_ranking_unique_top_rank_retained_top50_current.csv", "_stage5_ranking_summary.json"),
        ("_stage5_ranking_rows_top_rank_retained_top50_current.csv", "_stage5_ranking_summary.json"),
        ("_ranking_eval_unique_top_rank_retained_top50_current.csv", "_ranking_eval_current.json"),
        ("_ranking_eval_rows_top_rank_retained_top50_current.csv", "_ranking_eval_current.json"),
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
    for key in ("topk_unique", "topk"):
        rows = summary.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and int(float(row.get("k", -1))) == 20:
                return _float(row.get("hit_rate"))
    return None


def _ranking_pr_auc_ci_low(summary: dict[str, Any]) -> float | None:
    for key in ("metrics_ci_unique", "metrics_ci"):
        metrics_ci = summary.get(key)
        if not isinstance(metrics_ci, dict):
            continue
        pr_auc = metrics_ci.get("pr_auc")
        if isinstance(pr_auc, dict):
            value = _float(pr_auc.get("low"))
            if value is not None:
                return value
    return None


def _score(row: dict[str, Any]) -> float | None:
    score_col = _text(row.get("score_col"))
    for value in (
        row.get("score_value"),
        row.get(score_col) if score_col else None,
        row.get("score"),
        row.get("binding_score"),
    ):
        number = _float(value)
        if number is not None:
            return number
    return None


def _group_target_rows(path: Path) -> dict[str, list[dict[str, Any]]] | None:
    grouped: dict[str, list[dict[str, Any]]] = {target: [] for target in REQUIRED_TARGETS}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "target" not in reader.fieldnames or "is_binder" not in reader.fieldnames:
                return None
            for row in reader:
                target = _text(row.get("target"))
                if target not in grouped:
                    continue
                score = _score(row)
                if score is None:
                    continue
                copied = dict(row)
                copied["_score"] = score
                grouped[target].append(copied)
    except OSError:
        return None
    return grouped


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
    positives = [row for row in ranked if _bool(row.get("is_binder"))]
    decoys = [row for row in ranked if not _bool(row.get("is_binder"))]
    first_positive = positives[0] if positives else None
    top_decoy = decoys[0] if decoys else None
    positive_rank = ranked.index(first_positive) + 1 if first_positive is not None else None
    decoys_above = (
        None
        if positive_rank is None
        else sum(1 for row in ranked[: positive_rank - 1] if not _bool(row.get("is_binder")))
    )
    positive_anchor = (
        None
        if first_positive is None
        else _float(
            first_positive.get("mean_min_distance_A")
            or first_positive.get("anchor_distance_a")
            or first_positive.get("native_anchor_mean_distance_a")
        )
    )
    top_decoy_anchor = (
        None
        if top_decoy is None
        else _float(
            top_decoy.get("mean_min_distance_A")
            or top_decoy.get("anchor_distance_a")
            or top_decoy.get("native_anchor_mean_distance_a")
        )
    )
    anchor_margin = (
        None if positive_anchor is None or top_decoy_anchor is None else top_decoy_anchor - positive_anchor
    )

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


def _candidate_assessment(path: Path) -> dict[str, Any] | None:
    grouped = _group_target_rows(path)
    if grouped is None:
        return None
    summary_path, summary = _find_summary(path)
    lower_better = bool(summary.get("lower_better", True))
    ci_low = _ranking_pr_auc_ci_low(summary)
    top20 = _top20_hit_rate(summary)
    metric_blockers: list[str] = []
    if ci_low is None:
        metric_blockers.append("ranking_pr_auc_ci_low_missing")
    elif ci_low < CI_LOW_MIN:
        metric_blockers.append("ranking_pr_auc_ci_low_below_gate")
    if top20 is None:
        metric_blockers.append("top20_hit_rate_missing")
    elif top20 < TOP20_MIN:
        metric_blockers.append("top20_hit_rate_below_gate")
    targets = [
        _target_assessment(target, grouped[target], lower_better=lower_better)
        for target in REQUIRED_TARGETS
    ]
    target_green_count = sum(1 for row in targets if row["target_green"])
    target_blocker_count = sum(len(row["blockers"]) for row in targets)
    metric_gate_ready = not metric_blockers
    closure_ready = bool(metric_gate_ready and target_green_count == len(REQUIRED_TARGETS))
    return {
        "candidate_path": _display(path),
        "summary_json": _display(summary_path) if summary_path else "",
        "candidate_status": "closure_candidate_ready" if closure_ready else "blocked",
        "closure_candidate_ready": closure_ready,
        "metric_gate_ready": metric_gate_ready,
        "ranking_pr_auc_ci_low": ci_low,
        "top20_hit_rate": top20,
        "metric_blockers": metric_blockers,
        "target_green_count": target_green_count,
        "target_blocker_count": target_blocker_count,
        "targets": targets,
        **_READ_ONLY_FLAGS,
    }


def build_gpcr_hard_decoy_candidate_sweep(
    *,
    candidate_glob: str = DEFAULT_CANDIDATE_GLOB,
) -> dict[str, Any]:
    paths = sorted(_resolve(".").glob(candidate_glob) if not Path(candidate_glob).is_absolute() else Path("/").glob(candidate_glob.lstrip("/")))
    candidates = [candidate for path in paths if (candidate := _candidate_assessment(path)) is not None]
    closure_candidates = [row for row in candidates if row["closure_candidate_ready"]]
    best = max(
        candidates,
        key=lambda row: (
            int(row["metric_gate_ready"]),
            int(row["target_green_count"]),
            -int(row["target_blocker_count"]),
        ),
        default={},
    )
    status = (
        "gpcr_hard_decoy_candidate_sweep_closure_candidate_ready"
        if closure_candidates
        else "blocked_gpcr_hard_decoy_candidate_sweep_no_closure_candidate"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "gpcr_actual_closure_ready": bool(closure_candidates),
        "candidate_glob": candidate_glob,
        "candidate_count": len(candidates),
        "closure_candidate_count": len(closure_candidates),
        "best_candidate_path": best.get("candidate_path", ""),
        "best_candidate_metric_gate_ready": bool(best.get("metric_gate_ready") is True),
        "best_candidate_target_green_count": int(best.get("target_green_count", 0) or 0),
        "required_target_count": len(REQUIRED_TARGETS),
        "ci_low_min": CI_LOW_MIN,
        "top20_min": TOP20_MIN,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the closure candidate as the GPCR hard-decoy suite input and rerun the suite report."
            if closure_candidates
            else "No local retained ranking candidate closes all GPCR hard-decoy conditions; run or restore a new replay that fixes DRD2 anchor separation and supplies OPRM1 top-decoy evidence."
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
                }
                writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Candidate Sweep",
        "",
        f"- status: `{summary['status']}`",
        f"- gpcr_actual_closure_ready: `{str(summary['gpcr_actual_closure_ready']).lower()}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- closure_candidate_count: `{summary['closure_candidate_count']}`",
        f"- best_candidate_path: `{summary['best_candidate_path'] or '(none)'}`",
        f"- best_candidate_target_green_count: `{summary['best_candidate_target_green_count']}` / `{summary['required_target_count']}`",
        "",
        "| candidate | metric gate | target green | status |",
        "| --- | --- | ---: | --- |",
    ]
    for candidate in sorted(
        payload["candidates"],
        key=lambda row: (int(row["metric_gate_ready"]), int(row["target_green_count"])),
        reverse=True,
    )[:20]:
        lines.append(
            "| `{path}` | `{metric}` | {green} | `{status}` |".format(
                path=candidate["candidate_path"],
                metric=str(candidate["metric_gate_ready"]).lower(),
                green=candidate["target_green_count"],
                status=candidate["candidate_status"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep local GPCR hard-decoy candidates for closure evidence.")
    parser.add_argument("--candidate-glob", default=DEFAULT_CANDIDATE_GLOB)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_gpcr_hard_decoy_candidate_sweep(candidate_glob=args.candidate_glob)
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
