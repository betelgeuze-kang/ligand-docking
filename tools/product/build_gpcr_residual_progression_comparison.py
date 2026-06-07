#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V3_MODE_JSON = "runs/gpcr_residual_chembl50_v3_mode_comparison_current.json"
DEFAULT_V4_MODE_JSON = "runs/gpcr_residual_chembl50_v4_mode_comparison_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_residual_progression_comparison_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_progression_comparison_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_progression_comparison_current.md"


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


def build_payload(v3_mode_payload: dict[str, Any], v4_mode_payload: dict[str, Any]) -> dict[str, Any]:
    v3_rows = {str(row.get("task_id", "")).strip(): row for row in list(v3_mode_payload.get("rows", []) or [])}
    v4_rows = {str(row.get("task_id", "")).strip(): row for row in list(v4_mode_payload.get("rows", []) or [])}
    task_ids = sorted(set(v3_rows) | set(v4_rows))
    rows: list[dict[str, Any]] = []
    core_v4_apply_preserves_baseline = False
    chembl50_v4_apply_has_ef1_gain = False
    for task_id in task_ids:
        v3 = v3_rows.get(task_id, {})
        v4 = v4_rows.get(task_id, {})
        row = {
            "task_id": task_id,
            "baseline_pr_auc": v4.get("baseline_pr_auc", v3.get("baseline_pr_auc")),
            "v3_shadow_pr_auc": v3.get("shadow_pr_auc"),
            "v3_apply_pr_auc": v3.get("apply_pr_auc"),
            "v4_shadow_pr_auc": v4.get("shadow_pr_auc"),
            "v4_apply_pr_auc": v4.get("apply_pr_auc"),
            "baseline_ef1": v4.get("baseline_ef1", v3.get("baseline_ef1")),
            "v3_shadow_ef1": v3.get("shadow_ef1"),
            "v3_apply_ef1": v3.get("apply_ef1"),
            "v4_shadow_ef1": v4.get("shadow_ef1"),
            "v4_apply_ef1": v4.get("apply_ef1"),
            "v3_apply_d_pr_vs_baseline": v3.get("delta_pr_auc_apply_vs_baseline"),
            "v4_apply_d_pr_vs_baseline": v4.get("delta_pr_auc_apply_vs_baseline"),
            "v3_apply_d_ef1_vs_baseline": v3.get("delta_ef1_apply_vs_baseline"),
            "v4_apply_d_ef1_vs_baseline": v4.get("delta_ef1_apply_vs_baseline"),
        }
        rows.append(row)
        if task_id == "gpcr_core_full":
            core_v4_apply_preserves_baseline = (row["v4_apply_d_pr_vs_baseline"] == 0) and (row["v4_apply_d_ef1_vs_baseline"] == 0)
        if task_id == "gpcr_chembl50_full":
            chembl50_v4_apply_has_ef1_gain = isinstance(row["v4_apply_d_ef1_vs_baseline"], (int, float)) and row["v4_apply_d_ef1_vs_baseline"] > 0
    return {
        "summary": {
            "task_count": len(rows),
            "core_v4_apply_preserves_baseline": core_v4_apply_preserves_baseline,
            "chembl50_v4_apply_has_ef1_gain": chembl50_v4_apply_has_ef1_gain,
            "next_required_step": "Use this progression table as the GPCR handoff view: v4 apply is the current locked-decoy apply-safe endpoint, but router promotion remains blocked.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Residual Progression Comparison",
        "",
        f"- task_count: `{s['task_count']}`",
        f"- core_v4_apply_preserves_baseline: `{s['core_v4_apply_preserves_baseline']}`",
        f"- chembl50_v4_apply_has_ef1_gain: `{s['chembl50_v4_apply_has_ef1_gain']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Progression",
        "",
        "| task_id | base_pr | v3_shadow_pr | v3_apply_pr | v4_shadow_pr | v4_apply_pr | base_ef1 | v3_apply_ef1 | v4_apply_ef1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['task_id']} | {row['baseline_pr_auc']} | {row['v3_shadow_pr_auc']} | {row['v3_apply_pr_auc']} | {row['v4_shadow_pr_auc']} | {row['v4_apply_pr_auc']} | {row['baseline_ef1']} | {row['v3_apply_ef1']} | {row['v4_apply_ef1']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 5-step GPCR residual progression comparison across v3/v4 shadow/apply runs.")
    parser.add_argument("--v3-mode-json", default=DEFAULT_V3_MODE_JSON)
    parser.add_argument("--v4-mode-json", default=DEFAULT_V4_MODE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.v3_mode_json), _load_json(args.v4_mode_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
