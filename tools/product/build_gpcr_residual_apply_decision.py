#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_COMPARISON_JSON = "runs/gpcr_residual_mode_comparison_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_residual_apply_decision_current.json"
DEFAULT_OUT_MD = "runs/gpcr_residual_apply_decision_current.md"


def _resolve(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def build_payload(*, comparison_json: Path) -> dict[str, Any]:
    comparison = json.loads(comparison_json.read_text(encoding="utf-8"))
    rows = comparison.get("rows", [])
    pass_regressions = 0
    pr_regressions = 0
    ef1_improvements = 0
    ef1_regressions = 0
    tasks: list[dict[str, Any]] = []

    for row in rows:
        apply_pass = row.get("apply_pass")
        baseline_pass = row.get("baseline_pass")
        d_pr = row.get("delta_pr_auc_apply_vs_baseline")
        d_ef1 = row.get("delta_ef1_apply_vs_baseline")
        if baseline_pass and apply_pass is False:
            pass_regressions += 1
        if isinstance(d_pr, (int, float)) and d_pr < 0:
            pr_regressions += 1
        if isinstance(d_ef1, (int, float)):
            if d_ef1 > 0:
                ef1_improvements += 1
            elif d_ef1 < 0:
                ef1_regressions += 1
        tasks.append(
            {
                "task_id": row.get("task_id"),
                "baseline_pass": baseline_pass,
                "apply_pass": apply_pass,
                "delta_pr_auc_apply_vs_baseline": d_pr,
                "delta_ef1_apply_vs_baseline": d_ef1,
                "apply_residual_mean_delta": row.get("apply_residual_mean_delta"),
            }
        )

    decision = "no_go_for_100k_router"
    rationale = (
        "apply-mode remains claim-safe on locked decoys, but it does not improve EF1 on the GPCR tasks and "
        "it still leaves PR-AUC regression on at least one task versus the baseline. Promote only after a "
        "narrower correction target or penalty revision improves top-rank quality without PR-AUC degradation."
    )
    if pass_regressions == 0 and pr_regressions == 0 and ef1_improvements > 0:
        decision = "go_for_100k_router"
        rationale = (
            "apply-mode preserved task passes, avoided PR-AUC regressions, and improved EF1 on at least one GPCR task."
        )

    return {
        "comparison_json": str(comparison_json),
        "task_count": len(tasks),
        "pass_regressions": pass_regressions,
        "pr_regressions": pr_regressions,
        "ef1_improvements": ef1_improvements,
        "ef1_regressions": ef1_regressions,
        "decision": decision,
        "rationale": rationale,
        "tasks": tasks,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GPCR Residual Apply Decision",
        "",
        f"- comparison_json: `{payload['comparison_json']}`",
        f"- task_count: `{payload['task_count']}`",
        f"- pass_regressions: `{payload['pass_regressions']}`",
        f"- pr_regressions: `{payload['pr_regressions']}`",
        f"- ef1_improvements: `{payload['ef1_improvements']}`",
        f"- ef1_regressions: `{payload['ef1_regressions']}`",
        f"- decision: `{payload['decision']}`",
        "",
        payload["rationale"],
        "",
        "| task_id | apply_pass | d_pr_apply_base | d_ef1_apply_base | apply_mean_delta |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for task in payload["tasks"]:
        lines.append(
            f"| {task['task_id']} | {task['apply_pass']} | "
            f"{task['delta_pr_auc_apply_vs_baseline']} | {task['delta_ef1_apply_vs_baseline']} | "
            f"{task['apply_residual_mean_delta']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a go/no-go decision summary for the current GPCR residual apply experiment.")
    p.add_argument("--comparison-json", default=DEFAULT_COMPARISON_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(comparison_json=_resolve(args.comparison_json))
    _write_json(_resolve(args.out_json), payload)
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
