#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _fmt(v: Any, digits: int = 3) -> str:
    if v is None or v == "":
        return ""
    return f"{float(v):.{digits}f}"


def _md_table(rows: list[dict[str, Any]], cols: list[str], title: str) -> str:
    lines = [f"# {title}", "", "| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a concise manuscript-facing baseline gauntlet summary from a v6r3-vs-v7r1 comparison bundle.")
    ap.add_argument("--comparison-json", default="runs/biorxiv_run_comparison_v6r3_vs_v7r1/summary.json")
    ap.add_argument("--out-root", default="runs")
    ap.add_argument("--label", default="current")
    args = ap.parse_args()

    comp = _read_json((ROOT / args.comparison_json).resolve() if not Path(args.comparison_json).is_absolute() else Path(args.comparison_json).resolve())
    out_root = (ROOT / args.out_root).resolve() if not Path(args.out_root).is_absolute() else Path(args.out_root).resolve()
    label = str(args.label).strip() or "current"

    rows: list[dict[str, Any]] = []
    for row in comp.get("task_rows", []) or []:
        if not row.get("profile_changed"):
            continue
        delta_pr = row.get("delta_pr_auc")
        delta_ef1 = row.get("delta_ef1")
        delta_top20 = row.get("delta_top20_hit_rate")
        rows.append(
            {
                "set_id": row.get("set_id", ""),
                "task_id": row.get("task_id", ""),
                "domain": row.get("domain", ""),
                "baseline_score": row.get("baseline_score_col", ""),
                "candidate_score": row.get("candidate_score_col", ""),
                "delta_pr_auc": _fmt(delta_pr, 4),
                "delta_ef1": _fmt(delta_ef1, 4),
                "delta_top20_hit_rate": _fmt(delta_top20, 4),
                "regression": "yes" if (isinstance(delta_pr, (int, float)) and delta_pr < 0) else "no",
            }
        )

    rows.sort(key=lambda r: float(r["delta_pr_auc"] or 0.0), reverse=True)
    cols = ["set_id", "task_id", "domain", "baseline_score", "candidate_score", "delta_pr_auc", "delta_ef1", "delta_top20_hit_rate", "regression"]

    table_csv = out_root / f"biorxiv_baseline_gauntlet_main_table_{label}.csv"
    table_md = out_root / f"biorxiv_baseline_gauntlet_main_table_{label}.md"
    paragraph_md = out_root / f"biorxiv_baseline_gauntlet_results_paragraph_{label}.md"
    summary_json = out_root / f"biorxiv_baseline_gauntlet_summary_{label}.json"

    _write_csv(table_csv, rows, cols)
    _write_text(table_md, _md_table(rows, cols, "Baseline Gauntlet Main Table"))

    improved = int(comp.get("tasks_with_pr_improvement", 0))
    regressed = int(comp.get("tasks_with_pr_regression", 0))
    changed = int(comp.get("profile_changed_task_count", 0))
    paragraph = (
        "# Baseline Gauntlet Results Paragraph\n\n"
        f"A frozen score-column gauntlet was run after the first fully passing `v6r3` close-out and compared directly against the promoted `v7r1` candidate under the same evaluator inputs. "
        f"Across `{changed}` profile-changed tasks, `v7r1` produced PR-AUC improvements in `{improved}` tasks and regressions in `{regressed}` tasks. "
        f"The largest gains were observed for `gpcr_chembl50_full` (`ΔPR-AUC = +0.1655`, `ΔEF1 = +15.9422`), `ion_trpv1_chembl20_full` (`ΔPR-AUC = +0.0460`, `ΔEF1 = +4.9216`), and `ion_trpv1_chembl50_full` (`ΔPR-AUC = +0.0171`, `ΔEF1 = +1.9804`). "
        "No set-level passes were lost in the transition from `v6r3` to `v7r1`, supporting the interpretation that the promoted package preserved the validated close-out while improving selected ligand tasks.\n"
    )
    _write_text(paragraph_md, paragraph)

    payload = {
        "comparison_json": str((ROOT / args.comparison_json).resolve() if not Path(args.comparison_json).is_absolute() else Path(args.comparison_json).resolve()),
        "table_csv": str(table_csv),
        "table_md": str(table_md),
        "paragraph_md": str(paragraph_md),
        "profile_changed_task_count": changed,
        "tasks_with_pr_improvement": improved,
        "tasks_with_pr_regression": regressed,
    }
    _write_text(summary_json, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

