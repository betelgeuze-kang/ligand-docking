#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


FORCE_KEYS = (
    "on_hbond_force_mean",
    "on_sticker_force_mean",
    "on_bridge_force_component_mean",
    "on_bridge_force_mean",
    "on_helix_force_mean",
    "on_anti_collapse_force_mean",
    "generic_nonbonded_force_mean",
    "on_mean_force",
)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _median(vals: List[float]) -> float:
    return float(statistics.median(vals)) if vals else 0.0


def _mean(vals: List[float]) -> float:
    return float(sum(vals) / max(len(vals), 1))


def _summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"row_count": len(rows), "components": {}}
    total_vals = [float(row.get("on_mean_force", 0.0) or 0.0) for row in rows]
    total_med = _median(total_vals)
    for key in FORCE_KEYS:
        vals = [float(row.get(key, 0.0) or 0.0) for row in rows]
        med = _median(vals)
        mean = _mean(vals)
        frac = float(med / total_med) if total_med > 0.0 else 0.0
        out["components"][key] = {
            "median": med,
            "mean": mean,
            "median_fraction_of_total": frac,
        }
    ranked = sorted(
        (
            (key, item["median"])
            for key, item in out["components"].items()
            if key != "on_mean_force"
        ),
        key=lambda x: x[1],
        reverse=True,
    )
    out["ranked_components_by_median"] = ranked
    return out


def build_profile(eval_jsons: List[str]) -> Dict[str, Any]:
    report: Dict[str, Any] = {"eval_jsons": eval_jsons, "profiles": [], "branch_profiles": {}}
    branch_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_rows: List[Dict[str, Any]] = []
    for path in eval_jsons:
        payload = _read_json(path)
        rows = list(payload.get("targets", []) or [])
        all_rows.extend(rows)
        profile = {
            "eval_json": path,
            "split_groups": sorted({str(r.get("split_group", "")) for r in rows}),
            "summary": _summarize_rows(rows),
        }
        report["profiles"].append(profile)
        for row in rows:
            branch_rows[str(row.get("branch_label", ""))].append(row)
    report["all_rows"] = _summarize_rows(all_rows)
    for branch, rows in sorted(branch_rows.items()):
        report["branch_profiles"][branch] = _summarize_rows(rows)
    return report


def _to_markdown(report: Dict[str, Any]) -> str:
    lines = ["# IDP Force Component Profile", ""]
    lines.append("## Overall")
    lines.append("")
    overall = report["all_rows"]
    lines.append(f"- row_count: `{overall['row_count']}`")
    for key, med in overall["ranked_components_by_median"][:6]:
        frac = overall["components"][key]["median_fraction_of_total"]
        lines.append(f"- {key}: median `{overall['components'][key]['median']:.4f}`, frac `{frac:.4f}`")
    lines.append("")
    lines.append("## By Eval")
    lines.append("")
    for item in report["profiles"]:
        lines.append(f"### `{item['eval_json']}`")
        lines.append("")
        lines.append(f"- split_groups: `{item['split_groups']}`")
        for key, med in item["summary"]["ranked_components_by_median"][:5]:
            frac = item["summary"]["components"][key]["median_fraction_of_total"]
            lines.append(f"- {key}: median `{item['summary']['components'][key]['median']:.4f}`, frac `{frac:.4f}`")
        lines.append("")
    lines.append("## By Branch")
    lines.append("")
    for branch, item in report["branch_profiles"].items():
        lines.append(f"### `{branch}`")
        lines.append("")
        lines.append(f"- row_count: `{item['row_count']}`")
        for key, med in item["ranked_components_by_median"][:5]:
            frac = item["components"][key]["median_fraction_of_total"]
            lines.append(f"- {key}: median `{item['components'][key]['median']:.4f}`, frac `{frac:.4f}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Profile IDP force component magnitudes from evaluator summaries.")
    p.add_argument("--eval-json", action="append", required=True, help="May be passed multiple times.")
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    args = p.parse_args()

    report = build_profile([str(x) for x in args.eval_json])
    Path(args.out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(_to_markdown(report), encoding="utf-8")
    print(args.out_json)
    print(args.out_md)


if __name__ == "__main__":
    main()
