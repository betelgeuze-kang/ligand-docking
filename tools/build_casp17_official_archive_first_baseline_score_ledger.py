#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.build_casp17_historical_seed_native_oracle_metric_candidates import _score_candidate


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MODEL_POOL_JSON = "casp17/casp17_official_archive_first_baseline_model_pool_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_score_ledger"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_score_ledger_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_score_ledger_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_SCORE_LEDGER.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline score ledger only. It scores external CASP "
    "archive model1/top5 rows against a local native PDB with deterministic CA proxy metrics for "
    "historical replay calibration. It is not an official CASP assessment, does not import official "
    "archive models as internal predictions, does not fill strict-blind operator values, does not "
    "push remotes, and does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_score_ledger_v1"

GROUP_COLUMNS = [
    "group_rank",
    "target_id",
    "group_id",
    "group_status",
    "model1_model_id",
    "model1_metric_status",
    "model1_gdt_ts_proxy",
    "model1_gdt_ha_proxy",
    "model1_ca_lddt_proxy",
    "model1_tm_score_proxy",
    "model1_ca_rmsd_angstrom",
    "best_top5_model_id",
    "best_top5_model_number",
    "best_top5_metric_status",
    "best_top5_gdt_ts_proxy",
    "best_top5_gdt_ha_proxy",
    "best_top5_ca_lddt_proxy",
    "best_top5_tm_score_proxy",
    "best_top5_ca_rmsd_angstrom",
    "best_minus_model1_gdt_ts_proxy",
    "top5_model_count",
    "top5_ready_count",
    "complete_top5_group",
    "blockers",
    "claim_boundary",
    "rule_id",
]

MODEL_COLUMNS = [
    "target_id",
    "group_id",
    "model_id",
    "model_number",
    "pool_role",
    "path",
    "native_pdb",
    "metric_status",
    "gdt_ts_proxy",
    "gdt_ha_proxy",
    "ca_lddt_proxy",
    "tm_score_proxy",
    "ca_rmsd_angstrom",
    "ca_match_count",
    "ca_match_basis",
    "blockers",
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


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


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


def _mean(values: list[float]) -> str:
    if not values:
        return ""
    return f"{sum(values) / len(values):.3f}"


def _score_model_rows(model_rows: list[dict[str, Any]], native_pdb: str) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for fallback_rank, row in enumerate(model_rows, start=1):
        raw = {
            "target_id": _text(row.get("target_id")),
            "benchmark_id": "official_archive_first_baseline",
            "scope": "monomer",
            "candidate_rank": fallback_rank,
            "role": _text(row.get("pool_role")),
            "path": _text(row.get("extracted_pdb")),
            "notes": "official archive baseline-only model row",
        }
        metric = _score_candidate(raw, native_pdb, fallback_rank)
        scored.append(
            {
                "target_id": _text(row.get("target_id")),
                "group_id": _text(row.get("group_id")),
                "model_id": _text(row.get("model_id")),
                "model_number": _int(row.get("model_number")),
                "pool_role": _text(row.get("pool_role")),
                "path": _text(row.get("extracted_pdb")),
                "native_pdb": _text(metric.get("native_pdb")),
                "metric_status": _text(metric.get("metric_status")),
                "gdt_ts_proxy": _text(metric.get("gdt_ts_proxy")),
                "gdt_ha_proxy": _text(metric.get("gdt_ha_proxy")),
                "ca_lddt_proxy": _text(metric.get("ca_lddt_proxy")),
                "tm_score_proxy": _text(metric.get("tm_score_proxy")),
                "ca_rmsd_angstrom": _text(metric.get("ca_rmsd_angstrom")),
                "ca_match_count": metric.get("ca_match_count", 0),
                "ca_match_basis": _text(metric.get("ca_match_basis")),
                "blockers": _text(metric.get("blockers")),
                "claim_boundary": CLAIM_BOUNDARY,
                "rule_id": RULE_ID,
            }
        )
    return scored


def _group_rows(scored_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in scored_rows:
        by_group.setdefault(_text(row.get("group_id")), []).append(row)
    rows: list[dict[str, Any]] = []
    for rank, group_id in enumerate(sorted(by_group), start=1):
        group_models = sorted(by_group[group_id], key=lambda row: int(row["model_number"]))
        ready = [row for row in group_models if row["metric_status"] == "metric_ready"]
        top5 = [row for row in group_models if 1 <= int(row["model_number"]) <= 5]
        ready_top5 = [row for row in top5 if row["metric_status"] == "metric_ready"]
        model1 = next((row for row in group_models if int(row["model_number"]) == 1), {})
        best = max(ready_top5, key=lambda row: _float(row.get("gdt_ts_proxy")), default={})
        complete_top5 = {1, 2, 3, 4, 5}.issubset({int(row["model_number"]) for row in top5})
        model1_ready = _text(model1.get("metric_status")) == "metric_ready"
        best_ready = bool(best)
        model1_score = _float(model1.get("gdt_ts_proxy")) if model1_ready else 0.0
        best_score = _float(best.get("gdt_ts_proxy")) if best_ready else 0.0
        blockers = []
        if not model1_ready:
            blockers.append("model1_missing_or_blocked")
        if not best_ready:
            blockers.append("top5_metric_missing")
        row = {
            "group_rank": rank,
            "target_id": _text(group_models[0].get("target_id")) if group_models else "",
            "group_id": group_id,
            "group_status": "group_score_ready" if not blockers else "group_score_blocked",
            "model1_model_id": _text(model1.get("model_id")),
            "model1_metric_status": _text(model1.get("metric_status")),
            "model1_gdt_ts_proxy": _text(model1.get("gdt_ts_proxy")),
            "model1_gdt_ha_proxy": _text(model1.get("gdt_ha_proxy")),
            "model1_ca_lddt_proxy": _text(model1.get("ca_lddt_proxy")),
            "model1_tm_score_proxy": _text(model1.get("tm_score_proxy")),
            "model1_ca_rmsd_angstrom": _text(model1.get("ca_rmsd_angstrom")),
            "best_top5_model_id": _text(best.get("model_id")),
            "best_top5_model_number": _text(best.get("model_number")),
            "best_top5_metric_status": _text(best.get("metric_status")),
            "best_top5_gdt_ts_proxy": _text(best.get("gdt_ts_proxy")),
            "best_top5_gdt_ha_proxy": _text(best.get("gdt_ha_proxy")),
            "best_top5_ca_lddt_proxy": _text(best.get("ca_lddt_proxy")),
            "best_top5_tm_score_proxy": _text(best.get("tm_score_proxy")),
            "best_top5_ca_rmsd_angstrom": _text(best.get("ca_rmsd_angstrom")),
            "best_minus_model1_gdt_ts_proxy": f"{best_score - model1_score:.3f}" if model1_ready and best_ready else "",
            "top5_model_count": len(top5),
            "top5_ready_count": len(ready_top5),
            "complete_top5_group": str(complete_top5),
            "blockers": ",".join(blockers),
            "claim_boundary": CLAIM_BOUNDARY,
            "rule_id": RULE_ID,
        }
        rows.append(row)
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_pool_payload = _read_json(args.model_pool_json)
    model_pool_summary = _summary(model_pool_payload)
    model_pool_rows = _rows(model_pool_payload)
    native_pdb = _text(model_pool_summary.get("native_pdb_path"))
    top5_rows = [
        row
        for row in model_pool_rows
        if _text(row.get("model_status")) == "model_ready" and 1 <= int(float(str(row.get("model_number", 0)))) <= 5
    ]
    scored_rows = _score_model_rows(top5_rows, native_pdb) if top5_rows and native_pdb else []
    group_rows = _group_rows(scored_rows)
    ready_model_rows = [row for row in scored_rows if row["metric_status"] == "metric_ready"]
    ready_group_rows = [row for row in group_rows if row["group_status"] == "group_score_ready"]
    model1_scores = [_float(row["model1_gdt_ts_proxy"]) for row in ready_group_rows if row["model1_gdt_ts_proxy"]]
    best_top5_scores = [_float(row["best_top5_gdt_ts_proxy"]) for row in ready_group_rows if row["best_top5_gdt_ts_proxy"]]
    deltas = [_float(row["best_minus_model1_gdt_ts_proxy"]) for row in ready_group_rows if row["best_minus_model1_gdt_ts_proxy"]]
    first_gap = max(ready_group_rows, key=lambda row: _float(row.get("best_minus_model1_gdt_ts_proxy")), default={})
    complete_top5_group_count = sum(1 for row in group_rows if row.get("complete_top5_group") == "True")
    top5_improved_group_count = sum(
        1 for row in ready_group_rows if _float(row.get("best_minus_model1_gdt_ts_proxy")) > 0.001
    )
    status = (
        "official_archive_first_baseline_score_ledger_ready_baseline_only"
        if scored_rows and len(ready_model_rows) == len(scored_rows) and ready_group_rows
        else "official_archive_first_baseline_score_ledger_blocked"
    )
    out_dir = _resolve(args.out_dir)
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_score_ledger",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_score_ledger_status": status,
        "model_pool_json": _artifact(args.model_pool_json),
        "model_pool_status": _text(model_pool_summary.get("official_archive_first_baseline_model_pool_status")),
        "first_baseline_candidate_id": _text(model_pool_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(model_pool_summary.get("first_competition")),
        "first_target_id": _text(model_pool_summary.get("first_target_id")),
        "first_native_pdb_code": _text(model_pool_summary.get("first_native_pdb_code")),
        "native_pdb": _artifact(native_pdb) if native_pdb else "",
        "competitive_proof_eligible": bool(model_pool_summary.get("competitive_proof_eligible")),
        "strict_blind_intake_policy": _text(model_pool_summary.get("strict_blind_intake_policy")),
        "top5_model_count": len(top5_rows),
        "scored_model_count": len(scored_rows),
        "ready_model_count": len(ready_model_rows),
        "blocked_model_count": len(scored_rows) - len(ready_model_rows),
        "group_count": len(group_rows),
        "ready_group_count": len(ready_group_rows),
        "blocked_group_count": len(group_rows) - len(ready_group_rows),
        "complete_top5_group_count": complete_top5_group_count,
        "model1_scored_group_count": len(model1_scores),
        "model1_group_count": len(model1_scores),
        "best_top5_scored_group_count": len(best_top5_scores),
        "best_top5_group_count": len(best_top5_scores),
        "top5_improved_group_count": top5_improved_group_count,
        "mean_model1_gdt_ts_proxy": _mean(model1_scores),
        "mean_best_top5_gdt_ts_proxy": _mean(best_top5_scores),
        "mean_best_minus_model1_gdt_ts_proxy": _mean(deltas),
        "max_best_minus_model1_gdt_ts_proxy": _text(first_gap.get("best_minus_model1_gdt_ts_proxy")),
        "max_gap_group_id": _text(first_gap.get("group_id")),
        "max_gap_model1_model_id": _text(first_gap.get("model1_model_id")),
        "max_gap_best_top5_model_id": _text(first_gap.get("best_top5_model_id")),
        "model_score_csv": _artifact(out_dir / "model_score_rows.csv"),
        "group_score_csv": _artifact(out_dir / "group_score_ledger.csv"),
        "next_action": (
            "use the baseline-only score ledger for historical replay calibration; keep strict-blind proof blocked"
            if status == "official_archive_first_baseline_score_ledger_ready_baseline_only"
            else "repair baseline model/native metric inputs before historical replay calibration"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": group_rows, "model_score_rows": scored_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Score Ledger",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_score_ledger_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- model scores ready/blocked/total: `{summary['ready_model_count']}/{summary['blocked_model_count']}/{summary['scored_model_count']}`",
        f"- group scores ready/blocked/total: `{summary['ready_group_count']}/{summary['blocked_group_count']}/{summary['group_count']}`",
        f"- top5 models/complete groups/improved groups: `{summary['top5_model_count']}/{summary['complete_top5_group_count']}/{summary['top5_improved_group_count']}`",
        f"- mean model1/best5/delta GDT_TS proxy: `{summary['mean_model1_gdt_ts_proxy'] or '-'}` `{summary['mean_best_top5_gdt_ts_proxy'] or '-'}` `{summary['mean_best_minus_model1_gdt_ts_proxy'] or '-'}`",
        f"- max gap: `{summary['max_best_minus_model1_gdt_ts_proxy'] or '-'}` group `{summary['max_gap_group_id'] or '-'}` `{summary['max_gap_model1_model_id'] or '-'}` -> `{summary['max_gap_best_top5_model_id'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Group Ledger",
        "",
        "| group | model1 | model1 GDT | best top5 | best GDT | delta |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:30]:
        lines.append(
            f"| `{row['group_id']}` | `{row['model1_model_id'] or '-'}` | `{row['model1_gdt_ts_proxy'] or '-'}` | "
            f"`{row['best_top5_model_id'] or '-'}` | `{row['best_top5_gdt_ts_proxy'] or '-'}` | "
            f"`{row['best_minus_model1_gdt_ts_proxy'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], GROUP_COLUMNS)
    _write_md(args.out_md, payload)
    _write_json(out_dir / "score_ledger.json", payload)
    _write_csv(out_dir / "group_score_ledger.csv", payload["rows"], GROUP_COLUMNS)
    _write_csv(out_dir / "model_score_rows.csv", payload["model_score_rows"], MODEL_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score first official archive baseline model1/top5 rows.")
    parser.add_argument("--model-pool-json", default=DEFAULT_MODEL_POOL_JSON)
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
                "status": payload["summary"]["official_archive_first_baseline_score_ledger_status"],
                "target": payload["summary"]["first_target_id"],
                "models": payload["summary"]["ready_model_count"],
                "groups": payload["summary"]["ready_group_count"],
                "mean_model1": payload["summary"]["mean_model1_gdt_ts_proxy"],
                "mean_best5": payload["summary"]["mean_best_top5_gdt_ts_proxy"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
