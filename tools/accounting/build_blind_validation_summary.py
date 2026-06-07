#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _pick_metrics(data: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "pass",
        "failed_stage",
        "ranking_unique_auc",
        "ranking_pr_auc",
        "ranking_ef1",
        "ranking_roc_auc_ci_low",
        "ranking_pr_auc_ci_low",
        "ranking_ef1_ci_low",
        "ranking_topk_hit_rate",
        "mean_min_distance_A",
        "ranking_positive_count",
        "ranking_eval_unique_keys",
    ]
    return {k: data.get(k) for k in keys if k in data}


def _md_table(rows: list[dict[str, Any]]) -> str:
    header = [
        "name",
        "pass",
        "failed_stage",
        "auc",
        "pr_auc",
        "ef1",
        "roc_ci_low",
        "pr_ci_low",
        "ef1_ci_low",
        "topk_hit_rate",
        "positives",
        "eval_keys",
    ]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("name", "")),
                    str(row.get("pass", "")),
                    str(row.get("failed_stage", "")),
                    str(row.get("ranking_unique_auc", "")),
                    str(row.get("ranking_pr_auc", "")),
                    str(row.get("ranking_ef1", "")),
                    str(row.get("ranking_roc_auc_ci_low", "")),
                    str(row.get("ranking_pr_auc_ci_low", "")),
                    str(row.get("ranking_ef1_ci_low", "")),
                    str(row.get("ranking_topk_hit_rate", "")),
                    str(row.get("ranking_positive_count", "")),
                    str(row.get("ranking_eval_unique_keys", "")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", action="append", required=True)
    ap.add_argument("--summary-json", action="append", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    if len(args.name) != len(args.summary_json):
        raise SystemExit("name and summary-json counts must match")

    rows: list[dict[str, Any]] = []
    for name, path_str in zip(args.name, args.summary_json):
        path = Path(path_str)
        payload = _load_json(path)
        row = {"name": name, "summary_json": str(path.resolve())}
        row.update(_pick_metrics(payload))
        rows.append(row)

    aggregate = {
        "count": len(rows),
        "passed": sum(1 for r in rows if r.get("pass") is True),
        "failed": sum(1 for r in rows if r.get("pass") is not True),
        "all_pass": all(r.get("pass") is True for r in rows),
    }
    out = {"aggregate": aggregate, "runs": rows}

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.write_text(json.dumps(out, indent=2))

    md = []
    md.append("# Blind Validation Summary")
    md.append("")
    md.append(f"- count: {aggregate['count']}")
    md.append(f"- passed: {aggregate['passed']}")
    md.append(f"- failed: {aggregate['failed']}")
    md.append(f"- all_pass: {aggregate['all_pass']}")
    md.append("")
    md.append(_md_table(rows))
    md.append("")
    md.append("## Source Files")
    for row in rows:
        md.append(f"- {row['name']}: {row['summary_json']}")
    out_md.write_text("\n".join(md) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
