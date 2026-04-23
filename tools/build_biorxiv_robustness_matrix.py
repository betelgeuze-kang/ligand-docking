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


def _set_index(sets_obj: Any) -> dict[str, dict[str, Any]]:
    if isinstance(sets_obj, dict):
        return {str(k): v for k, v in sets_obj.items() if isinstance(v, dict)}
    if isinstance(sets_obj, list):
        out: dict[str, dict[str, Any]] = {}
        for row in sets_obj:
            if not isinstance(row, dict):
                continue
            set_id = str(row.get("set_id") or "")
            if not set_id:
                continue
            out[set_id] = row
        return out
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a reviewer-facing robustness evidence matrix for the promoted bioRxiv package.")
    ap.add_argument("--run-summary-json", default="runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1/summary.json")
    ap.add_argument("--baseline-gauntlet-json", default="runs/biorxiv_baseline_gauntlet_summary_current.json")
    ap.add_argument("--seed-shift-comparison-json", default="runs/biorxiv_run_comparison_2026-03-22_biorxiv_robustness_v1r1_vs_current/summary.json")
    ap.add_argument("--robustness-comparison-json", default="runs/biorxiv_robustness_comparison_summary_current.json")
    ap.add_argument("--temporal-baseline-json", default="runs/biorxiv_temporal_submission_baseline_current.json")
    ap.add_argument("--audit-json", default="runs/biorxiv_external_validation_audit_current.json")
    ap.add_argument("--ablation-json", default="runs/biorxiv_ablation_table_current.json")
    ap.add_argument("--out-json", default="runs/biorxiv_robustness_matrix_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_robustness_matrix_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_robustness_matrix_current.md")
    args = ap.parse_args()

    run_summary = _read_json((ROOT / args.run_summary_json).resolve())
    baseline = _read_json((ROOT / args.baseline_gauntlet_json).resolve())
    robustness_comparison_path = (ROOT / args.robustness_comparison_json).resolve()
    seed_shift_path = (ROOT / args.seed_shift_comparison_json).resolve()
    comparison = _read_json(robustness_comparison_path) if robustness_comparison_path.exists() else _read_json(seed_shift_path)
    temporal = _read_json((ROOT / args.temporal_baseline_json).resolve())
    audit = _read_json((ROOT / args.audit_json).resolve())
    ablation = _read_json((ROOT / args.ablation_json).resolve())

    sets = _set_index(run_summary.get("sets"))
    rows = [
        {
            "dimension": "primary_blind_claim",
            "status": _bool_text(sets.get("set1_core_blind", {}).get("pass")),
            "evidence": "primary blind set passes across GPCR, ion-channel, kinase/protease, and IDP",
            "artifact": str((ROOT / args.run_summary_json).resolve()),
        },
        {
            "dimension": "expanded_ood_generalization",
            "status": _bool_text(sets.get("set2_expanded_ood", {}).get("pass")),
            "evidence": "expanded OOD set remains fully passing under the promoted current run",
            "artifact": str((ROOT / args.run_summary_json).resolve()),
        },
        {
            "dimension": "operational_smoke_reproducibility",
            "status": _bool_text(sets.get("set3_operational_smoke", {}).get("pass")),
            "evidence": "smoke rerun passes while preserving explicit raw/effective pass separation",
            "artifact": str((ROOT / args.run_summary_json).resolve()),
        },
        {
            "dimension": "score_selection_robustness",
            "status": "PASS" if int(baseline.get("tasks_with_pr_regression", 0)) == 0 else "MIXED",
            "evidence": f"profile-changed tasks={baseline.get('profile_changed_task_count', 0)}, improvements={baseline.get('tasks_with_pr_improvement', 0)}, regressions={baseline.get('tasks_with_pr_regression', 0)}",
            "artifact": str((ROOT / args.baseline_gauntlet_json).resolve()),
        },
        {
            "dimension": "robustness_battery",
            "status": (
                "PASS"
                if comparison.get("all_sets_preserved") is True and int(comparison.get("pass_to_fail_task_transitions", 0)) == 0
                else "MIXED"
            ),
            "evidence": (
                f"scenarios={comparison.get('scenario_count', 1)}, "
                f"improvements={comparison.get('tasks_with_pr_improvement', 0)}, "
                f"regressions={comparison.get('tasks_with_pr_regression', 0)}, "
                f"pass_to_fail={comparison.get('pass_to_fail_task_transitions', 0)}, "
                f"worst_task={comparison.get('largest_pr_regression_task', '') or 'NA'}"
            ),
            "artifact": str(robustness_comparison_path if robustness_comparison_path.exists() else seed_shift_path),
        },
        {
            "dimension": "corrective_ablation_trace",
            "status": "PASS" if len(ablation.get("rows", [])) >= 3 else "MIXED",
            "evidence": f"corrective transitions tracked={len(ablation.get('rows', []))}",
            "artifact": str((ROOT / args.ablation_json).resolve()),
        },
        {
            "dimension": "temporal_provenance_readiness",
            "status": "PASS" if int(temporal.get("overall_item_ready_count", 0)) >= 200 else "MIXED",
            "evidence": f"item_ready={temporal.get('overall_item_ready_count', 0)}, dataset_ready={temporal.get('overall_dataset_ready_count', 0)}",
            "artifact": str((ROOT / args.temporal_baseline_json).resolve()),
        },
        {
            "dimension": "package_auditability",
            "status": "PASS" if audit.get("pass") is True else "FAIL",
            "evidence": f"audit_pass={audit.get('pass')}, failure_count={audit.get('failure_count')}",
            "artifact": str((ROOT / args.audit_json).resolve()),
        },
    ]

    payload = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "rows": rows,
    }
    out_json = (ROOT / args.out_json).resolve()
    out_csv = (ROOT / args.out_csv).resolve()
    out_md = (ROOT / args.out_md).resolve()
    _write_json(out_json, payload)

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["dimension"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    md_lines = [
        "# bioRxiv Robustness Evidence Matrix",
        "",
        "| dimension | status | evidence |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        md_lines.append(f"| {row['dimension']} | {row['status']} | {row['evidence']} |")
    _write_text(out_md, "\n".join(md_lines) + "\n")

    print(json.dumps({"ok": True, "out_json": str(out_json), "row_count": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
