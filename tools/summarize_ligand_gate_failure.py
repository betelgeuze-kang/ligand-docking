#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _to_float(v: Any) -> Optional[float]:
    try:
        x = float(v)
        if x != x:
            return None
        return x
    except Exception:
        return None


def _metric_brief(row: Dict[str, Any]) -> Dict[str, Any]:
    metric = str(row.get("metric", "") or "")
    value = row.get("value")
    threshold = row.get("threshold")
    direction = str(row.get("direction", "") or "")
    delta = None
    fv = _to_float(value)
    ft = _to_float(threshold)
    if fv is not None and ft is not None:
        delta = fv - ft
    return {
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "direction": direction,
        "delta": delta,
        "min_change_to_pass": _min_change_to_pass(metric=metric, value=value, threshold=threshold, direction=direction),
        "recommended_action": _recommended_action(metric),
    }


def _min_change_to_pass(*, metric: str, value: Any, threshold: Any, direction: str) -> Optional[float]:
    fv = _to_float(value)
    ft = _to_float(threshold)
    if fv is None or ft is None:
        return None
    d = str(direction or "").strip().lower()
    if d == "min":
        return max(0.0, ft - fv)
    if d == "max":
        return max(0.0, fv - ft)
    # Fallback: infer by metric family.
    if any(tok in str(metric).lower() for tok in ["auc", "ef", "bedroc", "hit_rate"]):
        return max(0.0, ft - fv)
    return max(0.0, fv - ft)


def _recommended_action(metric: str) -> str:
    m = str(metric or "").lower()
    if "mean_min_distance" in m or "distance" in m:
        return "stage3 sampling/contact cutoff review"
    if "pr_auc" in m or "ef1" in m or "bedroc" in m or "topk" in m:
        return "stage5 score reweight + ranking separation review"
    if "ece" in m or "brier" in m:
        return "stage4 calibration review"
    if "auc" in m:
        return "stage5 ranking separation review"
    if "coverage" in m or "positive_count" in m:
        return "stage1/stage3 data readiness review"
    return "manual inspection"


def _next_actions(blockers: List[Dict[str, Any]]) -> List[str]:
    seen: List[str] = []
    for row in blockers:
        act = str(row.get("recommended_action", "") or "").strip()
        if act and act not in seen:
            seen.append(act)
    return seen[:5]


def summarize(summary_json: str) -> Dict[str, Any]:
    payload = _read_json(summary_json)
    stages = payload.get("stages", {}) if isinstance(payload.get("stages"), dict) else {}
    op_gate = stages.get("stage6_operational_gate", {}) if isinstance(stages.get("stage6_operational_gate"), dict) else {}
    strict_gate = stages.get("stage6_strict_gate", {}) if isinstance(stages.get("stage6_strict_gate"), dict) else {}
    failed_metrics = op_gate.get("failed_metrics", [])
    if not isinstance(failed_metrics, list):
        failed_metrics = []
    ranking_snapshot = {
        "ranking_unique_auc": op_gate.get("ranking_unique_auc"),
        "ranking_pr_auc": op_gate.get("ranking_pr_auc"),
        "ranking_ef1": op_gate.get("ranking_ef1"),
        "ranking_ece": op_gate.get("ranking_ece"),
        "ranking_topk_hit_rate": op_gate.get("ranking_topk_hit_rate"),
        "ranking_roc_auc_ci_low": op_gate.get("ranking_roc_auc_ci_low"),
        "ranking_pr_auc_ci_low": op_gate.get("ranking_pr_auc_ci_low"),
        "ranking_ef1_ci_low": op_gate.get("ranking_ef1_ci_low"),
        "mean_min_distance_A": op_gate.get("mean_min_distance_A"),
    }
    blockers = [_metric_brief(x) for x in failed_metrics if isinstance(x, dict)]
    dominant = blockers[:5]
    next_actions = _next_actions(blockers)
    return {
        "generated_at_local": payload.get("generated_at_local"),
        "source_summary_json": str(Path(summary_json).resolve()),
        "pass": bool(payload.get("pass", False)),
        "failed_stage": payload.get("failed_stage"),
        "service_result": payload.get("service_result", {}),
        "stage6_operational_pass": bool(op_gate.get("pass", False)) if op_gate else None,
        "stage6_strict_pass": bool(strict_gate.get("pass", False)) if strict_gate else None,
        "failed_metric_count": len(blockers),
        "dominant_blockers": dominant,
        "next_actions": next_actions,
        "ranking_snapshot": ranking_snapshot,
        "artifacts": payload.get("artifacts", {}),
        "artifacts_abs": payload.get("artifacts_abs", {}),
    }


def write_outputs(payload: Dict[str, Any], out_json: str, out_md: str) -> None:
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    if out_md:
        os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
        lines: List[str] = [
            "# Ligand Gate Failure Summary",
            "",
            f"- source_summary_json: `{payload.get('source_summary_json')}`",
            f"- pass: `{payload.get('pass')}`",
            f"- failed_stage: `{payload.get('failed_stage')}`",
            f"- failed_metric_count: `{payload.get('failed_metric_count')}`",
            "",
            "## Ranking Snapshot",
        ]
        snap = payload.get("ranking_snapshot", {})
        if isinstance(snap, dict):
            for k, v in snap.items():
                lines.append(f"- {k}: `{v}`")
        lines.extend(["", "## Dominant Blockers"])
        blockers = payload.get("dominant_blockers", [])
        if isinstance(blockers, list) and blockers:
            for row in blockers:
                if isinstance(row, dict):
                    lines.append(
                        f"- `{row.get('metric')}`: value=`{row.get('value')}`, "
                        f"threshold=`{row.get('threshold')}`, delta=`{row.get('delta')}`, "
                        f"min_change_to_pass=`{row.get('min_change_to_pass')}`, "
                        f"action=`{row.get('recommended_action')}`"
                    )
        else:
            lines.append("- none")
        lines.extend(["", "## Recommended Next Actions"])
        for action in payload.get("next_actions", []) or []:
            lines.append(f"- {action}")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Summarize HTVS gate failures from a run summary.")
    p.add_argument("--summary-json", type=str, required=True)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = summarize(str(args.summary_json))
    out_json = str(args.out_json).strip()
    out_md = str(args.out_md).strip()
    if not out_json:
        out_json = str(Path(str(args.summary_json)).with_name(Path(str(args.summary_json)).stem + "_failure_summary.json"))
    if not out_md:
        out_md = str(Path(str(args.summary_json)).with_name(Path(str(args.summary_json)).stem + "_failure_summary.md"))
    write_outputs(payload, out_json, out_md)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
