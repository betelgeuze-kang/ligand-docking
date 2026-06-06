#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCORE_LEDGER_JSON = "casp17/casp17_official_archive_first_baseline_score_ledger_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_replay_comparison"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_replay_comparison_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_replay_comparison_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_REPLAY_COMPARISON.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline replay comparison only. It compares a single "
    "baseline-only proxy score ledger with historical CASP15/16 winner-band constants and model1 "
    "selection diagnostics. It is not an official CASP assessment, not a SUM Z-score replay, not "
    "strict-blind competitive proof, does not import official archive models as internal predictions, "
    "does not push remotes, and does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_replay_comparison_v1"

WINNER_BANDS = [
    {
        "band_id": "casp15_regular_domain",
        "competition": "CASP15",
        "category": "regular protein domains",
        "metric": "official GDT_TS SUM Z-score",
        "winner_group": "Yang-Server",
        "winner_sum_zscore": 90.4273,
        "top3_cutoff": 85.7980,
        "top5_cutoff": 73.3653,
        "winner_proximity_cutoff": 90.4273 * 0.90,
    },
    {
        "band_id": "casp16_regular_domain",
        "competition": "CASP16",
        "category": "regular protein domains",
        "metric": "official GDT_TS SUM Z-score",
        "winner_group": "Yang-Server",
        "winner_sum_zscore": 40.8978,
        "top3_cutoff": 36.3137,
        "top5_cutoff": 33.3229,
        "winner_proximity_cutoff": 40.8978 * 0.90,
    },
    {
        "band_id": "casp16_multimer_complex",
        "competition": "CASP16",
        "category": "protein multimers and complexes",
        "metric": "official multimer assessment z-score",
        "winner_group": "KiharaLab",
        "winner_sum_zscore": 15.4,
        "top3_cutoff": 14.5,
        "top5_cutoff": 0.0,
        "winner_proximity_cutoff": 15.4 * 0.90,
    },
]

ROW_COLUMNS = [
    "band_id",
    "competition",
    "category",
    "metric",
    "winner_group",
    "winner_sum_zscore",
    "top3_cutoff",
    "top5_cutoff",
    "winner_proximity_cutoff",
    "direct_comparison_status",
    "baseline_target_id",
    "baseline_metric",
    "baseline_model1_mean_gdt_ts_proxy",
    "baseline_best_top5_mean_gdt_ts_proxy",
    "baseline_model1_best_rate",
    "baseline_top5_improved_rate",
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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    score_payload = _read_json(args.score_ledger_json)
    score_summary = _summary(score_payload)
    group_rows = _rows(score_payload)
    ready_group_rows = [row for row in group_rows if _text(row.get("group_status")) == "group_score_ready"]
    model1_best_count = sum(
        1 for row in ready_group_rows if abs(_float(row.get("best_minus_model1_gdt_ts_proxy"))) <= 0.001
    )
    top5_improved_count = sum(
        1 for row in ready_group_rows if _float(row.get("best_minus_model1_gdt_ts_proxy")) > 0.001
    )
    group_count = len(group_rows)
    ready_group_count = len(ready_group_rows)
    direct_status = "not_directly_comparable_proxy_single_target_not_sum_zscore"
    rows = []
    for band in WINNER_BANDS:
        rows.append(
            {
                "band_id": band["band_id"],
                "competition": band["competition"],
                "category": band["category"],
                "metric": band["metric"],
                "winner_group": band["winner_group"],
                "winner_sum_zscore": f"{band['winner_sum_zscore']:.4f}",
                "top3_cutoff": f"{band['top3_cutoff']:.4f}" if band["top3_cutoff"] else "",
                "top5_cutoff": f"{band['top5_cutoff']:.4f}" if band["top5_cutoff"] else "",
                "winner_proximity_cutoff": f"{band['winner_proximity_cutoff']:.4f}",
                "direct_comparison_status": direct_status,
                "baseline_target_id": _text(score_summary.get("first_target_id")),
                "baseline_metric": "single-target CA proxy GDT_TS, not official SUM Z-score",
                "baseline_model1_mean_gdt_ts_proxy": _text(score_summary.get("mean_model1_gdt_ts_proxy")),
                "baseline_best_top5_mean_gdt_ts_proxy": _text(score_summary.get("mean_best_top5_gdt_ts_proxy")),
                "baseline_model1_best_rate": _rate(model1_best_count, ready_group_count),
                "baseline_top5_improved_rate": _rate(top5_improved_count, ready_group_count),
                "claim_boundary": CLAIM_BOUNDARY,
                "rule_id": RULE_ID,
            }
        )
    status = (
        "official_archive_first_baseline_replay_comparison_ready_baseline_only"
        if _text(score_summary.get("official_archive_first_baseline_score_ledger_status")) and rows
        else "official_archive_first_baseline_replay_comparison_blocked"
    )
    out_dir = _resolve(args.out_dir)
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_replay_comparison",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_replay_comparison_status": status,
        "score_ledger_json": _artifact(args.score_ledger_json),
        "score_ledger_status": _text(score_summary.get("official_archive_first_baseline_score_ledger_status")),
        "first_baseline_candidate_id": _text(score_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(score_summary.get("first_competition")),
        "first_target_id": _text(score_summary.get("first_target_id")),
        "first_native_pdb_code": _text(score_summary.get("first_native_pdb_code")),
        "band_count": len(rows),
        "direct_comparable_band_count": 0,
        "blocked_band_count": len(rows),
        "direct_comparison_status": direct_status,
        "scored_model_count": int(score_summary.get("scored_model_count") or 0),
        "ready_model_count": int(score_summary.get("ready_model_count") or 0),
        "blocked_model_count": int(score_summary.get("blocked_model_count") or 0),
        "group_count": group_count,
        "ready_group_count": ready_group_count,
        "blocked_group_count": group_count - ready_group_count,
        "model1_best_group_count": model1_best_count,
        "top5_improved_group_count": top5_improved_count,
        "model1_best_rate": _rate(model1_best_count, ready_group_count),
        "top5_improved_rate": _rate(top5_improved_count, ready_group_count),
        "mean_model1_gdt_ts_proxy": _text(score_summary.get("mean_model1_gdt_ts_proxy")),
        "mean_best_top5_gdt_ts_proxy": _text(score_summary.get("mean_best_top5_gdt_ts_proxy")),
        "mean_best_minus_model1_gdt_ts_proxy": _text(score_summary.get("mean_best_minus_model1_gdt_ts_proxy")),
        "max_gap_group_id": _text(score_summary.get("max_gap_group_id")),
        "max_best_minus_model1_gdt_ts_proxy": _text(score_summary.get("max_best_minus_model1_gdt_ts_proxy")),
        "competitive_proof_eligible": bool(score_summary.get("competitive_proof_eligible")),
        "strict_blind_intake_policy": _text(score_summary.get("strict_blind_intake_policy")),
        "comparison_csv": _artifact(out_dir / "winner_band_comparison.csv"),
        "next_action": (
            "keep this as baseline-only model-selection calibration, then close strict-blind source evidence "
            "before any winner-normalized competitive claim"
            if status == "official_archive_first_baseline_replay_comparison_ready_baseline_only"
            else "score the first official archive baseline ledger before replay comparison"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Replay Comparison",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_replay_comparison_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- direct comparison status: `{summary['direct_comparison_status']}`",
        f"- bands comparable/blocked/total: `{summary['direct_comparable_band_count']}/{summary['blocked_band_count']}/{summary['band_count']}`",
        f"- model1 best groups/rate: `{summary['model1_best_group_count']}/{summary['ready_group_count']}` `{summary['model1_best_rate'] or '-'}`",
        f"- top5 improved groups/rate: `{summary['top5_improved_group_count']}/{summary['ready_group_count']}` `{summary['top5_improved_rate'] or '-'}`",
        f"- mean model1/best5/delta GDT_TS proxy: `{summary['mean_model1_gdt_ts_proxy'] or '-'}` `{summary['mean_best_top5_gdt_ts_proxy'] or '-'}` `{summary['mean_best_minus_model1_gdt_ts_proxy'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Winner Bands",
        "",
        "| band | winner | top3 | top5 | 90pct | comparison |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['band_id']}` | `{row['winner_group']}` `{row['winner_sum_zscore']}` | "
            f"`{row['top3_cutoff'] or '-'}` | `{row['top5_cutoff'] or '-'}` | "
            f"`{row['winner_proximity_cutoff']}` | `{row['direct_comparison_status']}` |"
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
    _write_json(out_dir / "replay_comparison.json", payload)
    _write_csv(out_dir / "winner_band_comparison.csv", payload["rows"], ROW_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare first official archive baseline replay with winner bands.")
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
                "status": payload["summary"]["official_archive_first_baseline_replay_comparison_status"],
                "target": payload["summary"]["first_target_id"],
                "bands": payload["summary"]["band_count"],
                "model1_best_rate": payload["summary"]["model1_best_rate"],
                "top5_improved_rate": payload["summary"]["top5_improved_rate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
