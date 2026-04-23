#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bool_text(v: Any) -> str:
    if v is True:
        return "PASS"
    if v is False:
        return "FAIL"
    return "NA"


def _count_passes(set_summary: dict[str, Any], field: str) -> int:
    count = 0
    for row in set_summary.values():
        if row.get(field) is True:
            count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="Build an ablation-style corrective-transition table for the bioRxiv package.")
    ap.add_argument("--v3-v4-summary-json", default="runs/biorxiv_run_comparison_v3r1_vs_v4r1/summary.json")
    ap.add_argument("--v4-v6-summary-json", default="runs/biorxiv_run_comparison_v4r1_vs_v6r3/summary.json")
    ap.add_argument("--v6-v7-summary-json", default="runs/biorxiv_run_comparison_v6r3_vs_v7r1/summary.json")
    ap.add_argument("--out-json", default="runs/biorxiv_ablation_table_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_ablation_table_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_ablation_table_current.md")
    args = ap.parse_args()

    transitions = [
        {
            "transition_id": "v3r1_to_v4r1",
            "summary_json": (ROOT / args.v3_v4_summary_json).resolve(),
            "intervention": "kinase operational-gate correction under preserved blind score wiring",
            "intended_effect": "remove kinase-driven set blockers without relaxing the GPCR core blind claim",
        },
        {
            "transition_id": "v4r1_to_v6r3",
            "summary_json": (ROOT / args.v4_v6_summary_json).resolve(),
            "intervention": "GPCR inline-prior propagation fix and GPCR core close-out with composite_v7",
            "intended_effect": "remove the final model-side core blind blocker while preserving prior set passes",
        },
        {
            "transition_id": "v6r3_to_v7r1",
            "summary_json": (ROOT / args.v6_v7_summary_json).resolve(),
            "intervention": "winner-informed score remapping after frozen baseline gauntlet",
            "intended_effect": "improve selected ligand tasks without losing any accepted set passes",
        },
    ]

    rows: list[dict[str, Any]] = []
    for item in transitions:
        summary = _read_json(item["summary_json"])
        set_summary = summary.get("set_summary", {})
        row = {
            "transition_id": item["transition_id"],
            "baseline_run_root": summary.get("baseline_run_root", ""),
            "candidate_run_root": summary.get("candidate_run_root", ""),
            "intervention": item["intervention"],
            "intended_effect": item["intended_effect"],
            "task_count": int(summary.get("task_count", 0)),
            "profile_changed_task_count": int(summary.get("profile_changed_task_count", 0)),
            "tasks_with_pr_improvement": int(summary.get("tasks_with_pr_improvement", 0)),
            "tasks_with_pr_regression": int(summary.get("tasks_with_pr_regression", 0)),
            "baseline_set_pass_count": _count_passes(set_summary, "baseline_pass"),
            "candidate_set_pass_count": _count_passes(set_summary, "candidate_pass"),
            "set1_core_blind_baseline": set_summary.get("set1_core_blind", {}).get("baseline_pass"),
            "set1_core_blind_candidate": set_summary.get("set1_core_blind", {}).get("candidate_pass"),
            "set2_expanded_ood_baseline": set_summary.get("set2_expanded_ood", {}).get("baseline_pass"),
            "set2_expanded_ood_candidate": set_summary.get("set2_expanded_ood", {}).get("candidate_pass"),
            "set3_operational_smoke_baseline": set_summary.get("set3_operational_smoke", {}).get("baseline_pass"),
            "set3_operational_smoke_candidate": set_summary.get("set3_operational_smoke", {}).get("candidate_pass"),
        }
        rows.append(row)

    payload = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "rows": rows,
    }

    out_json = (ROOT / args.out_json).resolve()
    out_csv = (ROOT / args.out_csv).resolve()
    out_md = (ROOT / args.out_md).resolve()
    _write_json(out_json, payload)

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["transition_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    md_lines = [
        "# bioRxiv Corrective Ablation Table",
        "",
        "| transition | intervention | baseline sets pass | candidate sets pass | improved tasks | regressed tasks | set1 | set2 | set3 |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        md_lines.append(
            "| {transition_id} | {intervention} | {baseline_set_pass_count} | {candidate_set_pass_count} | {tasks_with_pr_improvement} | {tasks_with_pr_regression} | {set1c} | {set2c} | {set3c} |".format(
                transition_id=row["transition_id"],
                intervention=row["intervention"],
                baseline_set_pass_count=row["baseline_set_pass_count"],
                candidate_set_pass_count=row["candidate_set_pass_count"],
                tasks_with_pr_improvement=row["tasks_with_pr_improvement"],
                tasks_with_pr_regression=row["tasks_with_pr_regression"],
                set1c=_bool_text(row["set1_core_blind_candidate"]),
                set2c=_bool_text(row["set2_expanded_ood_candidate"]),
                set3c=_bool_text(row["set3_operational_smoke_candidate"]),
            )
        )
    md_lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `v3r1_to_v4r1` captures the kinase gate correction stage.",
            "- `v4r1_to_v6r3` captures the GPCR core close-out stage.",
            "- `v6r3_to_v7r1` captures the baseline-gauntlet-guided promotion stage.",
        ]
    )
    _write_text(out_md, "\n".join(md_lines) + "\n")

    print(json.dumps({"ok": True, "out_json": str(out_json), "row_count": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
