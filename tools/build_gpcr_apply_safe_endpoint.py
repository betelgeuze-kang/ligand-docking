#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISION_JSON = "runs/gpcr_residual_chembl50_v4_apply_decision_current.json"
DEFAULT_COMPARISON_JSON = "runs/gpcr_residual_chembl50_v4_mode_comparison_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_apply_safe_endpoint_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_apply_safe_endpoint_current.md"
DEFAULT_VARIANT_LABEL = "chembl50_v4"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    decision_payload: dict[str, Any],
    comparison_payload: dict[str, Any],
    *,
    variant_label: str = DEFAULT_VARIANT_LABEL,
) -> dict[str, Any]:
    task_rows = list(comparison_payload.get("rows", []) or [])
    pass_safe = int(decision_payload.get("pass_regressions", 0) or 0) == 0
    router_blocked = str(decision_payload.get("decision", "") or "").strip() == "no_go_for_100k_router"
    rows: list[dict[str, Any]] = []
    chembl50_ef1_gain = 0.0
    chembl50_pr_delta = 0.0
    core_pr_delta = 0.0
    for row in task_rows:
        task_id = str(row.get("task_id", "")).strip()
        d_pr = row.get("delta_pr_auc_apply_vs_baseline")
        d_ef1 = row.get("delta_ef1_apply_vs_baseline")
        if task_id == "gpcr_core_full" and isinstance(d_pr, (int, float)):
            core_pr_delta = float(d_pr)
        if task_id == "gpcr_chembl50_full":
            if isinstance(d_pr, (int, float)):
                chembl50_pr_delta = float(d_pr)
            if isinstance(d_ef1, (int, float)):
                chembl50_ef1_gain = float(d_ef1)
        rows.append(
            {
                "task_id": task_id,
                "baseline_pass": row.get("baseline_pass"),
                "apply_pass": row.get("apply_pass"),
                "baseline_pr_auc": row.get("baseline_pr_auc"),
                "apply_pr_auc": row.get("apply_pr_auc"),
                "delta_pr_auc_apply_vs_baseline": d_pr,
                "baseline_ef1": row.get("baseline_ef1"),
                "apply_ef1": row.get("apply_ef1"),
                "delta_ef1_apply_vs_baseline": d_ef1,
            }
        )
    endpoint_status = (
        "locked_decoy_apply_safe_router_blocked"
        if pass_safe and router_blocked
        else ("locked_decoy_apply_safe" if pass_safe else "not_apply_safe")
    )
    next_required_step = (
        "Treat chembl50_v4 as a GPCR locked-decoy apply-safe endpoint, but keep the 100k router blocked until a future variant removes the remaining tiny chembl50 PR regression."
        if endpoint_status == "locked_decoy_apply_safe_router_blocked"
        else "Do not promote this GPCR apply variant beyond locked-decoy evaluation until pass safety is restored."
    )
    return {
        "summary": {
            "variant_label": variant_label,
            "task_count": len(rows),
            "endpoint_status": endpoint_status,
            "apply_safe": pass_safe,
            "router_blocked": router_blocked,
            "decision": str(decision_payload.get("decision", "") or ""),
            "core_pr_delta_vs_baseline": core_pr_delta,
            "chembl50_pr_delta_vs_baseline": chembl50_pr_delta,
            "chembl50_ef1_delta_vs_baseline": chembl50_ef1_gain,
            "next_required_step": next_required_step,
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Apply-Safe Endpoint",
        "",
        f"- variant_label: `{s['variant_label']}`",
        f"- task_count: `{s['task_count']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- apply_safe: `{s['apply_safe']}`",
        f"- router_blocked: `{s['router_blocked']}`",
        f"- decision: `{s['decision']}`",
        f"- core_pr_delta_vs_baseline: `{s['core_pr_delta_vs_baseline']}`",
        f"- chembl50_pr_delta_vs_baseline: `{s['chembl50_pr_delta_vs_baseline']}`",
        f"- chembl50_ef1_delta_vs_baseline: `{s['chembl50_ef1_delta_vs_baseline']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Task Rows",
        "",
        "| task_id | apply_pass | d_pr_vs_baseline | d_ef1_vs_baseline |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['task_id']} | {row['apply_pass']} | {row['delta_pr_auc_apply_vs_baseline']} | {row['delta_ef1_apply_vs_baseline']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GPCR apply-safe endpoint summary from a locked-decoy apply comparison.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--comparison-json", default=DEFAULT_COMPARISON_JSON)
    parser.add_argument("--variant-label", default=DEFAULT_VARIANT_LABEL)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.comparison_json),
        variant_label=str(args.variant_label),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
