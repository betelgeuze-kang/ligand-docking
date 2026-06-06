#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.performance import build_cameo_performance_packet
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HANDOFF_JSON = "runs/cameo_dry_run_handoff_packet_current.json"
DEFAULT_THRESHOLD_POLICY_JSON = "runs/cameo_performance_threshold_policy_current.json"
DEFAULT_OUT_JSON = "runs/cameo_performance_scorecard_current.json"
DEFAULT_OUT_CSV = "runs/cameo_performance_scorecard_current.csv"
DEFAULT_OUT_MD = "runs/cameo_performance_scorecard_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not str(path_like).strip() or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Performance Scorecard",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- result_row_count: `{s['result_row_count']}`",
        f"- accepted_official_result_count: `{s['accepted_official_result_count']}`",
        f"- model1_official_result_count: `{s['model1_official_result_count']}`",
        f"- threshold_gate_status: `{s['threshold_gate_status']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- official_cameo_results_used: `{s['official_cameo_results_used']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Model1 Metrics",
        "",
        f"- lddt: `{s['model1_lddt']}`",
        f"- tm_score: `{s['model1_tm_score']}`",
        f"- qs_score: `{s['model1_qs_score']}`",
        f"- rmsd_A: `{s['model1_rmsd_A']}`",
        "",
        "## Rows",
        "",
        "| rank | candidate | status | lddt | tm_score | qs_score | rmsd_A |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            f"| {row.get('cameo_model_rank', '')} | `{row.get('candidate_id', '')}` | "
            f"`{row.get('result_status', '')}` | `{row.get('lddt')}` | `{row.get('tm_score')}` | "
            f"`{row.get('qs_score')}` | `{row.get('rmsd_A')}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Threshold Failures", ""])
    failures = payload.get("threshold_failures") or []
    if failures:
        lines.extend(
            f"- `{failure['metric']}` {failure['operator']} `{failure['threshold']}` failed with `{failure['value']}`"
            for failure in failures
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CAMEO official-results performance scorecard.")
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--results-csv", default="")
    parser.add_argument("--threshold-policy-json", default=DEFAULT_THRESHOLD_POLICY_JSON)
    parser.add_argument("--min-model1-lddt", type=float, default=None)
    parser.add_argument("--min-model1-tm-score", type=float, default=None)
    parser.add_argument("--min-model1-qs-score", type=float, default=0.0)
    parser.add_argument("--max-model1-rmsd-A", type=float, default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    threshold_overrides = {
        key: value
        for key, value in {
            "min_model1_lddt": args.min_model1_lddt,
            "min_model1_tm_score": args.min_model1_tm_score,
            "min_model1_qs_score": args.min_model1_qs_score,
            "max_model1_rmsd_A": args.max_model1_rmsd_A,
        }.items()
        if value is not None
    }
    payload = build_cameo_performance_packet(
        _read_json_if_present(args.handoff_json),
        _read_csv_rows(args.results_csv),
        thresholds=threshold_overrides or None,
        threshold_policy_packet=_read_json_if_present(args.threshold_policy_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
