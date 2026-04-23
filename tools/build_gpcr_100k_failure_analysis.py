#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_CSV = "runs/external_validation_2026-03-22_biorxiv_v7r1_set1_core_blind_gpcr_core_full_p0_n10000_r1_stage5_ranking_rows.csv"
DEFAULT_SCALEUP_CSV = "runs/external_validation_2026-03-23_scaleup_100k_pilot_v2r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _as_float(value: str) -> float:
    return float(str(value).strip())


def _positive_ranks(rows: list[dict[str, str]]) -> list[int]:
    out: list[int] = []
    for idx, row in enumerate(rows, start=1):
        if str(row.get("is_binder", "")).strip() == "1":
            out.append(idx)
    return out


def _topk_counts(rows: list[dict[str, str]], k: int) -> tuple[int, int]:
    top = rows[:k]
    binders = sum(1 for row in top if str(row.get("is_binder", "")).strip() == "1")
    return binders, len(top) - binders


def _top_false_positives(rows: list[dict[str, str]], k: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        if str(row.get("is_binder", "")).strip() == "0":
            out.append(
                {
                    "rank": idx,
                    "ligand_id": str(row.get("ligand_id", "")).strip(),
                    "binding_score_composite_v7": _as_float(row.get("binding_score_composite_v7", "nan")),
                    "mean_min_distance_A": _as_float(row.get("mean_min_distance_A", "nan")),
                    "reference_binding_kcal_mol": _as_float(row.get("reference_binding_kcal_mol", "nan")),
                    "role": str(row.get("role", "")).strip(),
                }
            )
        if len(out) >= k:
            break
    return out


def _payload_for(rows: list[dict[str, str]], label: str) -> dict[str, Any]:
    pos_ranks = _positive_ranks(rows)
    top20_binders, top20_decoys = _topk_counts(rows, 20)
    top100_binders, top100_decoys = _topk_counts(rows, 100)
    false_pos = _top_false_positives(rows, 20)
    fp_scores = [row["binding_score_composite_v7"] for row in false_pos]
    fp_dist = [row["mean_min_distance_A"] for row in false_pos]
    return {
        "label": label,
        "row_count": len(rows),
        "positive_rank_list": pos_ranks,
        "top20_binder_count": top20_binders,
        "top20_decoy_count": top20_decoys,
        "top100_binder_count": top100_binders,
        "top100_decoy_count": top100_decoys,
        "first_positive_rank": pos_ranks[0] if pos_ranks else None,
        "last_positive_rank": pos_ranks[-1] if pos_ranks else None,
        "top_false_positive_mean_score": mean(fp_scores) if fp_scores else None,
        "top_false_positive_mean_min_distance_A": mean(fp_dist) if fp_dist else None,
        "top_false_positives": false_pos,
    }


def build_payload(baseline_rows: list[dict[str, str]], scaleup_rows: list[dict[str, str]]) -> dict[str, Any]:
    baseline = _payload_for(baseline_rows, "baseline_10k")
    scaleup = _payload_for(scaleup_rows, "scaleup_100k")
    summary = {
        "baseline_positive_ranks": baseline["positive_rank_list"],
        "scaleup_positive_ranks": scaleup["positive_rank_list"],
        "baseline_top20_binder_count": baseline["top20_binder_count"],
        "scaleup_top20_binder_count": scaleup["top20_binder_count"],
        "baseline_top100_binder_count": baseline["top100_binder_count"],
        "scaleup_top100_binder_count": scaleup["top100_binder_count"],
        "first_positive_rank_shift": None,
        "last_positive_rank_shift": None,
        "interpretation": "",
    }
    if baseline["first_positive_rank"] is not None and scaleup["first_positive_rank"] is not None:
        summary["first_positive_rank_shift"] = scaleup["first_positive_rank"] - baseline["first_positive_rank"]
    if baseline["last_positive_rank"] is not None and scaleup["last_positive_rank"] is not None:
        summary["last_positive_rank_shift"] = scaleup["last_positive_rank"] - baseline["last_positive_rank"]
    summary["interpretation"] = (
        "The 100k GPCR failure is driven by top-rank decoy intrusion: the first two binders stay at the top, but the remaining binders are pushed much deeper by synthetic hard decoys."
    )
    return {"summary": summary, "baseline": baseline, "scaleup": scaleup}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR 100k Failure Analysis",
        "",
        f"- baseline_positive_ranks: `{s['baseline_positive_ranks']}`",
        f"- scaleup_positive_ranks: `{s['scaleup_positive_ranks']}`",
        f"- baseline_top20_binder_count: `{s['baseline_top20_binder_count']}`",
        f"- scaleup_top20_binder_count: `{s['scaleup_top20_binder_count']}`",
        f"- baseline_top100_binder_count: `{s['baseline_top100_binder_count']}`",
        f"- scaleup_top100_binder_count: `{s['scaleup_top100_binder_count']}`",
        f"- last_positive_rank_shift: `{s['last_positive_rank_shift']}`",
        "",
        "## Interpretation",
        "",
        f"- {s['interpretation']}",
        "",
        "## Top False Positives In 100k",
        "",
        "| rank | ligand_id | score | mean_min_distance_A | role |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["scaleup"]["top_false_positives"][:12]:
        lines.append(
            f"| {row['rank']} | `{row['ligand_id']}` | {row['binding_score_composite_v7']:.4f} | {row['mean_min_distance_A']:.4f} | {row['role']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare GPCR 10k baseline vs 100k pilot ranking rows and summarize top-rank decoy intrusion.")
    parser.add_argument("--baseline-csv", default=DEFAULT_BASELINE_CSV)
    parser.add_argument("--scaleup-csv", default=DEFAULT_SCALEUP_CSV)
    parser.add_argument("--out-json", default="runs/gpcr_100k_failure_analysis_current.json")
    parser.add_argument("--out-csv", default="runs/gpcr_100k_failure_false_positives_current.csv")
    parser.add_argument("--out-md", default="runs/gpcr_100k_failure_analysis_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_read_csv(_resolve(args.baseline_csv)), _read_csv(_resolve(args.scaleup_csv)))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["scaleup"]["top_false_positives"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
