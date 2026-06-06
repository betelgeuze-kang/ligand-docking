#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_VS_BASELINE_JSON = "runs/gpcr_residual_chembl50_v3_vs_baseline_current.json"
DEFAULT_VS_NARROW_V2_JSON = "runs/gpcr_residual_chembl50_v3_vs_narrow_v2_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_residual_chembl50_v3_decision_current.json"
DEFAULT_OUT_MD = "runs/gpcr_residual_chembl50_v3_decision_current.md"
DEFAULT_VARIANT_LABEL = "chembl50_v3"


def _resolve(path_like: str) -> Path:
    return Path(path_like).expanduser().resolve()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("rows", []))


def build_payload(*, vs_baseline_json: Path, vs_narrow_v2_json: Path, variant_label: str = DEFAULT_VARIANT_LABEL) -> dict[str, Any]:
    baseline_rows = {row.get("task_id"): row for row in _load_rows(vs_baseline_json)}
    narrow_rows = {row.get("task_id"): row for row in _load_rows(vs_narrow_v2_json)}
    task_ids = sorted(set(baseline_rows) | set(narrow_rows))
    tasks: list[dict[str, Any]] = []
    pass_regressions = 0
    pr_regressions_vs_baseline = 0
    ef1_improvements_vs_baseline = 0
    improved_vs_narrow_v2 = 0

    for task_id in task_ids:
        b_row = baseline_rows.get(task_id, {})
        n_row = narrow_rows.get(task_id, {})
        d_pr_base = b_row.get("delta_pr_auc")
        d_ef1_base = b_row.get("delta_ef1")
        d_pr_n2 = n_row.get("delta_pr_auc")
        d_ef1_n2 = n_row.get("delta_ef1")
        candidate_pass = b_row.get("candidate_pass")
        baseline_pass = b_row.get("baseline_pass")
        if baseline_pass and candidate_pass is False:
            pass_regressions += 1
        if isinstance(d_pr_base, (int, float)) and d_pr_base < 0:
            pr_regressions_vs_baseline += 1
        if isinstance(d_ef1_base, (int, float)) and d_ef1_base > 0:
            ef1_improvements_vs_baseline += 1
        if isinstance(d_pr_n2, (int, float)) and d_pr_n2 > 0:
            improved_vs_narrow_v2 += 1
        tasks.append(
            {
                "task_id": task_id,
                "baseline_pass": baseline_pass,
                "candidate_pass": candidate_pass,
                "delta_pr_auc_vs_baseline": d_pr_base,
                "delta_ef1_vs_baseline": d_ef1_base,
                "delta_pr_auc_vs_narrow_v2": d_pr_n2,
                "delta_ef1_vs_narrow_v2": d_ef1_n2,
                "residual_positive_delta_count": b_row.get("residual_positive_delta_count"),
                "residual_mean_delta": b_row.get("residual_mean_delta"),
            }
        )

    decision = "hold_shadow_only"
    rationale = (
        f"{variant_label} shadow is pass-safe and improves or preserves the measured GPCR slices versus the baseline while remaining narrower than earlier GPCR variants. "
        "The next safe step is a locked-decoy apply trial, not router promotion."
    )
    if pass_regressions == 0 and pr_regressions_vs_baseline == 0:
        decision = "go_for_locked_decoy_apply_trial"

    return {
        "variant_label": variant_label,
        "vs_baseline_json": str(vs_baseline_json),
        "vs_narrow_v2_json": str(vs_narrow_v2_json),
        "task_count": len(tasks),
        "pass_regressions": pass_regressions,
        "pr_regressions_vs_baseline": pr_regressions_vs_baseline,
        "ef1_improvements_vs_baseline": ef1_improvements_vs_baseline,
        "improved_vs_narrow_v2_count": improved_vs_narrow_v2,
        "decision": decision,
        "rationale": rationale,
        "tasks": tasks,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# GPCR Residual {payload.get('variant_label', DEFAULT_VARIANT_LABEL)} Decision",
        "",
        f"- variant_label: `{payload.get('variant_label', DEFAULT_VARIANT_LABEL)}`",
        f"- vs_baseline_json: `{payload['vs_baseline_json']}`",
        f"- vs_narrow_v2_json: `{payload['vs_narrow_v2_json']}`",
        f"- task_count: `{payload['task_count']}`",
        f"- pass_regressions: `{payload['pass_regressions']}`",
        f"- pr_regressions_vs_baseline: `{payload['pr_regressions_vs_baseline']}`",
        f"- ef1_improvements_vs_baseline: `{payload['ef1_improvements_vs_baseline']}`",
        f"- improved_vs_narrow_v2_count: `{payload['improved_vs_narrow_v2_count']}`",
        f"- decision: `{payload['decision']}`",
        "",
        payload["rationale"],
        "",
        "| task_id | candidate_pass | d_pr_vs_base | d_ef1_vs_base | d_pr_vs_n2 | d_ef1_vs_n2 | mean_delta |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for task in payload["tasks"]:
        lines.append(
            f"| {task['task_id']} | {task['candidate_pass']} | "
            f"{task['delta_pr_auc_vs_baseline']} | {task['delta_ef1_vs_baseline']} | "
            f"{task['delta_pr_auc_vs_narrow_v2']} | {task['delta_ef1_vs_narrow_v2']} | "
            f"{task['residual_mean_delta']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a decision artifact for a GPCR chembl50-focused residual shadow slice.")
    parser.add_argument("--vs-baseline-json", default=DEFAULT_VS_BASELINE_JSON)
    parser.add_argument("--vs-narrow-v2-json", default=DEFAULT_VS_NARROW_V2_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--variant-label", default=DEFAULT_VARIANT_LABEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        vs_baseline_json=_resolve(args.vs_baseline_json),
        vs_narrow_v2_json=_resolve(args.vs_narrow_v2_json),
        variant_label=str(args.variant_label),
    )
    _write_json(_resolve(args.out_json), payload)
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
