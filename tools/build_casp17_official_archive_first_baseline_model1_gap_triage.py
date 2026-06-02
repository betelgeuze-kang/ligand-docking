#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SCORE_LEDGER_JSON = "casp17/casp17_official_archive_first_baseline_score_ledger_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_model1_gap_triage"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_triage_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_model1_gap_triage_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_MODEL1_GAP_TRIAGE.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline model1 gap triage only. It mines a baseline-only "
    "proxy score ledger for model1-vs-best-of-5 selection failures and calibration examples. It is "
    "not an official CASP assessment, not strict-blind competitive proof, does not import official "
    "archive models as internal predictions, does not push remotes, and does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_model1_gap_triage_v1"

ROW_COLUMNS = [
    "triage_rank",
    "target_id",
    "group_id",
    "triage_band",
    "triage_action",
    "model1_model_id",
    "model1_gdt_ts_proxy",
    "best_top5_model_id",
    "best_top5_model_number",
    "best_top5_gdt_ts_proxy",
    "best_minus_model1_gdt_ts_proxy",
    "model1_metric_status",
    "best_top5_metric_status",
    "complete_top5_group",
    "top5_ready_count",
    "claim_boundary",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / denominator:.3f}"


def _band(delta: float) -> str:
    if delta <= 0.001:
        return "model1_best_or_tied"
    if delta < 5.0:
        return "small_selection_gap"
    if delta < 20.0:
        return "medium_selection_gap"
    if delta < 50.0:
        return "large_selection_gap"
    return "catastrophic_model1_selection_gap"


def _action(band: str) -> str:
    if band == "model1_best_or_tied":
        return "retain_as_positive_model1_selection_control"
    if band == "small_selection_gap":
        return "calibrate_tie_breakers_and_confidence_precision"
    if band == "medium_selection_gap":
        return "calibrate_confidence_geometry_and_protocol_diversity_features"
    if band == "large_selection_gap":
        return "audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features"
    return "critical_model1_failure_case_for_accuracy_estimation_training"


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _triage_rows(group_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ready = [row for row in group_rows if _text(row.get("group_status")) == "group_score_ready"]
    sorted_rows = sorted(ready, key=lambda row: _float(row.get("best_minus_model1_gdt_ts_proxy")), reverse=True)
    output: list[dict[str, Any]] = []
    for rank, row in enumerate(sorted_rows, start=1):
        delta = _float(row.get("best_minus_model1_gdt_ts_proxy"))
        band = _band(delta)
        output.append(
            {
                "triage_rank": rank,
                "target_id": _text(row.get("target_id")),
                "group_id": _text(row.get("group_id")),
                "triage_band": band,
                "triage_action": _action(band),
                "model1_model_id": _text(row.get("model1_model_id")),
                "model1_gdt_ts_proxy": _text(row.get("model1_gdt_ts_proxy")),
                "best_top5_model_id": _text(row.get("best_top5_model_id")),
                "best_top5_model_number": _text(row.get("best_top5_model_number")),
                "best_top5_gdt_ts_proxy": _text(row.get("best_top5_gdt_ts_proxy")),
                "best_minus_model1_gdt_ts_proxy": _text(row.get("best_minus_model1_gdt_ts_proxy")),
                "model1_metric_status": _text(row.get("model1_metric_status")),
                "best_top5_metric_status": _text(row.get("best_top5_metric_status")),
                "complete_top5_group": _text(row.get("complete_top5_group")),
                "top5_ready_count": _text(row.get("top5_ready_count")),
                "claim_boundary": CLAIM_BOUNDARY,
                "rule_id": RULE_ID,
            }
        )
    return output


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    score_payload = _read_json(args.score_ledger_json)
    score_summary = _summary(score_payload)
    group_rows = _rows(score_payload)
    rows = _triage_rows(group_rows)
    group_count = len(group_rows)
    ready_group_count = len(rows)
    blocked_group_count = group_count - ready_group_count
    model1_best_count = sum(1 for row in rows if row["triage_band"] == "model1_best_or_tied")
    small_count = sum(1 for row in rows if row["triage_band"] == "small_selection_gap")
    medium_count = sum(1 for row in rows if row["triage_band"] == "medium_selection_gap")
    large_count = sum(1 for row in rows if row["triage_band"] == "large_selection_gap")
    catastrophic_count = sum(1 for row in rows if row["triage_band"] == "catastrophic_model1_selection_gap")
    improved_count = ready_group_count - model1_best_count
    first = rows[0] if rows else {}
    status = (
        "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
        if _text(score_summary.get("official_archive_first_baseline_score_ledger_status")) and rows
        else "official_archive_first_baseline_model1_gap_triage_blocked"
    )
    out_dir = _resolve(args.out_dir)
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_model1_gap_triage",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_model1_gap_triage_status": status,
        "score_ledger_json": _artifact(args.score_ledger_json),
        "score_ledger_status": _text(score_summary.get("official_archive_first_baseline_score_ledger_status")),
        "first_baseline_candidate_id": _text(score_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(score_summary.get("first_competition")),
        "first_target_id": _text(score_summary.get("first_target_id")),
        "first_native_pdb_code": _text(score_summary.get("first_native_pdb_code")),
        "group_count": group_count,
        "ready_group_count": ready_group_count,
        "blocked_group_count": blocked_group_count,
        "model1_best_group_count": model1_best_count,
        "top5_improved_group_count": improved_count,
        "model1_best_rate": _rate(model1_best_count, ready_group_count),
        "top5_improved_rate": _rate(improved_count, ready_group_count),
        "small_gap_count": small_count,
        "medium_gap_count": medium_count,
        "large_gap_count": large_count,
        "catastrophic_gap_count": catastrophic_count,
        "calibration_case_count": improved_count,
        "critical_calibration_case_count": large_count + catastrophic_count,
        "first_triage_group_id": _text(first.get("group_id")),
        "first_triage_band": _text(first.get("triage_band")),
        "first_triage_delta": _text(first.get("best_minus_model1_gdt_ts_proxy")),
        "first_triage_action": _text(first.get("triage_action")),
        "first_triage_model1_model_id": _text(first.get("model1_model_id")),
        "first_triage_best_top5_model_id": _text(first.get("best_top5_model_id")),
        "mean_model1_gdt_ts_proxy": _text(score_summary.get("mean_model1_gdt_ts_proxy")),
        "mean_best_top5_gdt_ts_proxy": _text(score_summary.get("mean_best_top5_gdt_ts_proxy")),
        "mean_best_minus_model1_gdt_ts_proxy": _text(score_summary.get("mean_best_minus_model1_gdt_ts_proxy")),
        "competitive_proof_eligible": bool(score_summary.get("competitive_proof_eligible")),
        "strict_blind_intake_policy": _text(score_summary.get("strict_blind_intake_policy")),
        "triage_csv": _artifact(out_dir / "model1_gap_triage.csv"),
        "top_gap_worklist_csv": _artifact(out_dir / "top_gap_worklist.csv"),
        "next_action": (
            "use high-gap baseline-only cases to calibrate no-native model1 selection features; keep strict-blind "
            "competitive proof blocked until internal evidence is supplied"
            if status == "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
            else "score the first official archive baseline ledger before model1 gap triage"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Model1 Gap Triage",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_model1_gap_triage_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- groups ready/blocked/total: `{summary['ready_group_count']}/{summary['blocked_group_count']}/{summary['group_count']}`",
        f"- model1-best/top5-improved rates: `{summary['model1_best_group_count']}/{summary['ready_group_count']}` `{summary['model1_best_rate'] or '-'}` / `{summary['top5_improved_group_count']}/{summary['ready_group_count']}` `{summary['top5_improved_rate'] or '-'}`",
        f"- gap bands small/medium/large/catastrophic: `{summary['small_gap_count']}/{summary['medium_gap_count']}/{summary['large_gap_count']}/{summary['catastrophic_gap_count']}`",
        f"- critical calibration cases: `{summary['critical_calibration_case_count']}`",
        f"- first triage: group `{summary['first_triage_group_id'] or '-'}` `{summary['first_triage_band'] or '-'}` delta `{summary['first_triage_delta'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Top Gap Worklist",
        "",
        "| rank | group | band | model1 | best top5 | delta | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:20]:
        lines.append(
            f"| `{row['triage_rank']}` | `{row['group_id']}` | `{row['triage_band']}` | "
            f"`{row['model1_model_id']}` `{row['model1_gdt_ts_proxy']}` | "
            f"`{row['best_top5_model_id']}` `{row['best_top5_gdt_ts_proxy']}` | "
            f"`{row['best_minus_model1_gdt_ts_proxy']}` | `{row['triage_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_json(out_dir / "model1_gap_triage.json", payload)
    _write_csv(out_dir / "model1_gap_triage.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(out_dir / "top_gap_worklist.csv", payload["rows"][:20], ROW_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build official archive first baseline model1 gap triage.")
    parser.add_argument("--score-ledger-json", default=DEFAULT_SCORE_LEDGER_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["official_archive_first_baseline_model1_gap_triage_status"],
                "target": payload["summary"]["first_target_id"],
                "model1_best_rate": payload["summary"]["model1_best_rate"],
                "top5_improved_rate": payload["summary"]["top5_improved_rate"],
                "critical_cases": payload["summary"]["critical_calibration_case_count"],
                "first_group": payload["summary"]["first_triage_group_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
