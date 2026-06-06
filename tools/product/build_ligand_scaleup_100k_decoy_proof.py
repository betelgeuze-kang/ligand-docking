#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_PREFIX = "runs/external_validation_2026-03-23_scaleup_100k_pilot_v2r2"

TASKS = [
    {
        "task_id": "gpcr_core_full",
        "domain": "gpcr",
        "hard_decoy_summary": "set1_core_blind_gpcr_core_full_hard_decoy_summary.json",
        "stage1_summary": "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage1_summary.json",
        "stage2_summary": "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_summary.json",
    },
    {
        "task_id": "ion_trpv1_chembl20_full",
        "domain": "ion_channel",
        "hard_decoy_summary": "set1_core_blind_ion_trpv1_chembl20_full_hard_decoy_summary.json",
        "stage1_summary": "set1_core_blind_ion_trpv1_chembl20_full_p0_n100000_r1_stage1_summary.json",
        "stage2_summary": "set1_core_blind_ion_trpv1_chembl20_full_p0_n100000_r1_stage2_traj_summary.json",
    },
    {
        "task_id": "kinase_core_full",
        "domain": "kinase",
        "hard_decoy_summary": "set1_core_blind_kinase_core_full_hard_decoy_summary.json",
        "stage1_summary": "set1_core_blind_kinase_core_full_p0_n100000_r1_stage1_summary.json",
        "stage2_summary": "set1_core_blind_kinase_core_full_p0_n100000_r1_stage2_traj_summary.json",
    },
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
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


def build_payload(run_prefix: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for task in TASKS:
        hard = _load_json(run_prefix.with_name(run_prefix.name + "_" + task["hard_decoy_summary"]))
        stage1 = _load_json(run_prefix.with_name(run_prefix.name + "_" + task["stage1_summary"]))
        stage2 = _load_json(run_prefix.with_name(run_prefix.name + "_" + task["stage2_summary"]))

        synth = dict(hard.get("synthetic_decoys", {}))
        target_stats = list(synth.get("target_generation_stats", []))
        generated_per_target = {str(item.get("target", "")): int(item.get("generated", 0) or 0) for item in target_stats}
        rows.append(
            {
                "task_id": task["task_id"],
                "domain": task["domain"],
                "hard_decoy_requested_total": int(synth.get("requested", 0) or 0),
                "hard_decoy_generated_total": int(synth.get("generated", 0) or 0),
                "hard_decoy_shortfall": int(synth.get("shortfall", 0) or 0),
                "stage1_ligands": int(stage1.get("ligands", 0) or 0),
                "stage1_queue_rows": int(stage1.get("queue_rows", 0) or 0),
                "stage1_jobs_per_target": int(stage1.get("jobs_per_target", 0) or 0),
                "stage2_processed_rows": int(stage2.get("processed_rows", 0) or 0),
                "target_count": int(stage1.get("targets", 0) or 0),
                "downselect_explanation": (
                    "100k ligand CSV enters stage1, then stage1 builds a smaller queue for trajectory evaluation."
                ),
                "generated_per_target_json": json.dumps(generated_per_target, ensure_ascii=False, sort_keys=True),
            }
        )

    all_generated_100k = all(row["hard_decoy_generated_total"] == 100000 for row in rows)
    queue_rows_match_expected = all(
        row["stage1_queue_rows"] == row["stage1_jobs_per_target"] * row["target_count"]
        for row in rows
    )
    summary = {
        "run_prefix": str(run_prefix),
        "task_count": len(rows),
        "all_generated_100k": all_generated_100k,
        "queue_rows_match_expected": queue_rows_match_expected,
        "interpretation": (
            "The run really did generate 100k synthetic hard decoys per full task; the 10k/20k numbers belong to the downstream trajectory queue, not the hard-decoy pool."
            if all_generated_100k and queue_rows_match_expected
            else "The run does not cleanly show 100k hard-decoy generation and expected downstream queue sizing."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Ligand Scale-Up 100k Decoy Proof",
        "",
        f"- task_count: `{payload['summary']['task_count']}`",
        f"- all_generated_100k: `{str(payload['summary']['all_generated_100k']).lower()}`",
        f"- queue_rows_match_expected: `{str(payload['summary']['queue_rows_match_expected']).lower()}`",
        "",
        "## Interpretation",
        "",
        f"- {payload['summary']['interpretation']}",
        "",
        "## Task Rows",
        "",
        "| task_id | domain | hard_decoy_requested_total | hard_decoy_generated_total | stage1_ligands | stage1_queue_rows | stage1_jobs_per_target | target_count | stage2_processed_rows |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['task_id']} | {row['domain']} | {row['hard_decoy_requested_total']} | {row['hard_decoy_generated_total']} | {row['stage1_ligands']} | {row['stage1_queue_rows']} | {row['stage1_jobs_per_target']} | {row['target_count']} | {row['stage2_processed_rows']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show proof that the 100k pilot really generated 100k hard decoys, while downstream stage1/stage2 used a smaller queue.")
    parser.add_argument("--run-prefix", default=DEFAULT_RUN_PREFIX)
    parser.add_argument("--out-json", default="runs/ligand_scaleup_100k_decoy_proof_current.json")
    parser.add_argument("--out-csv", default="runs/ligand_scaleup_100k_decoy_proof_current.csv")
    parser.add_argument("--out-md", default="runs/ligand_scaleup_100k_decoy_proof_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_resolve(args.run_prefix))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
