#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMPARISON_JSON = "runs/cross_family_locked_decoy_shadow_comparison_current.json"
DEFAULT_OUT_JSON = "runs/cross_family_locked_decoy_shadow_decision_current.json"
DEFAULT_OUT_CSV = "runs/cross_family_locked_decoy_shadow_decision_current.csv"
DEFAULT_OUT_MD = "runs/cross_family_locked_decoy_shadow_decision_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(comparison: dict[str, Any]) -> dict[str, Any]:
    summary_in = comparison.get("summary", comparison) if isinstance(comparison, dict) else {}
    family_rows = list(comparison.get("family_rows", []))
    task_rows = list(comparison.get("task_rows", []))
    comparison_ready = bool(summary_in.get("comparison_ready", False))
    candidate_fail_count = int(summary_in.get("candidate_fail_count", 0) or 0)
    live_process_count = int(summary_in.get("live_process_count", 0) or 0)
    max_abs_delta = 0.0
    for row in family_rows:
        value = row.get("max_abs_delta_pr_auc")
        if value is None:
            continue
        try:
            max_abs_delta = max(max_abs_delta, abs(float(value)))
        except Exception:
            continue

    keep_noop_shadow = (
        comparison_ready
        and candidate_fail_count == 0
        and live_process_count == 0
        and max_abs_delta <= 0.005
    )
    decision = (
        "keep_shadow_noop_contract_for_ion_kinase"
        if keep_noop_shadow
        else "retain_shadow_only_recheck_noop_contract"
    )
    next_required_step = (
        "Keep ion/kinase in the cross-family shell as measured shadow-ready noop families while CA2/PXR authoritative rows continue to fill."
        if keep_noop_shadow
        else "Recheck ion/kinase shadow deltas before promoting any noop-family contract decision."
    )
    return {
        "summary": {
            "decision": decision,
            "comparison_ready": comparison_ready,
            "candidate_fail_count": candidate_fail_count,
            "live_process_count": live_process_count,
            "max_abs_delta_pr_auc": max_abs_delta,
            "family_count": len(family_rows),
            "task_count": len(task_rows),
            "next_required_step": next_required_step,
        },
        "family_rows": family_rows,
        "task_rows": task_rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Cross-Family Locked-Decoy Shadow Decision",
        "",
        f"- decision: `{summary['decision']}`",
        f"- comparison_ready: `{str(summary['comparison_ready']).lower()}`",
        f"- candidate_fail_count: `{summary['candidate_fail_count']}`",
        f"- live_process_count: `{summary['live_process_count']}`",
        f"- max_abs_delta_pr_auc: `{summary['max_abs_delta_pr_auc']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Family Rows",
        "",
        "| family | task_count | candidate_fail_count | max_abs_delta_pr_auc |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in payload["family_rows"]:
        lines.append(
            f"| {row.get('family','')} | {row.get('task_count','')} | {row.get('candidate_fail_count','')} | {row.get('max_abs_delta_pr_auc','')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a decision artifact from the ion/kinase locked-decoy shadow comparison.")
    parser.add_argument("--comparison-json", default=DEFAULT_COMPARISON_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison = json.loads(_resolve(args.comparison_json).read_text(encoding="utf-8"))
    payload = build_payload(comparison)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["family_rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
