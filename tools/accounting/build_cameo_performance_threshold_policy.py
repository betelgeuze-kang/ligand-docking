#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from betelgeuze_cameo.performance_policy import build_cameo_performance_threshold_policy
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/cameo_performance_threshold_policy_current.json"
DEFAULT_OUT_CSV = "runs/cameo_performance_threshold_policy_current.csv"
DEFAULT_OUT_MD = "runs/cameo_performance_threshold_policy_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Performance Threshold Policy",
        "",
        f"- status: `{s['status']}`",
        f"- profile_name: `{s['profile_name']}`",
        f"- threshold_policy_ready: `{s['threshold_policy_ready']}`",
        f"- min_model1_lddt: `{s['min_model1_lddt']}`",
        f"- min_model1_tm_score: `{s['min_model1_tm_score']}`",
        f"- min_model1_qs_score: `{s['min_model1_qs_score']}`",
        f"- max_model1_rmsd_A: `{s['max_model1_rmsd_A']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- prediction_generation_enabled: `{s['prediction_generation_enabled']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CAMEO model1 performance threshold policy.")
    parser.add_argument("--profile-name", default="product_grade_model1")
    parser.add_argument("--min-model1-lddt", type=float, default=0.70)
    parser.add_argument("--min-model1-tm-score", type=float, default=0.50)
    parser.add_argument("--min-model1-qs-score", type=float, default=0.0)
    parser.add_argument("--max-model1-rmsd-A", type=float, default=5.0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_performance_threshold_policy(
        profile_name=args.profile_name,
        thresholds={
            "min_model1_lddt": args.min_model1_lddt,
            "min_model1_tm_score": args.min_model1_tm_score,
            "min_model1_qs_score": args.min_model1_qs_score,
            "max_model1_rmsd_A": args.max_model1_rmsd_A,
        },
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
