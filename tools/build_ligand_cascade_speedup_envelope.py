#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_KPI_JSON = "runs/ligand_scaleup_kpi_current.json"
DEFAULT_OUT_JSON = "runs/ligand_cascade_speedup_envelope_current.json"
DEFAULT_OUT_CSV = "runs/ligand_cascade_speedup_envelope_current.csv"
DEFAULT_OUT_MD = "runs/ligand_cascade_speedup_envelope_current.md"

AVOID_FRACTIONS = [0.50, 0.70, 0.80, 0.90, 0.95]
TARGET_SPEEDUPS = [2.0, 3.0, 5.0]


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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _overall_speedup(stage2_share_pct: float, avoided_fraction: float) -> float:
    share = stage2_share_pct / 100.0
    denom = 1.0 - (share * avoided_fraction)
    if denom <= 0.0:
        return float("inf")
    return 1.0 / denom


def _required_avoid_fraction(stage2_share_pct: float, target_speedup: float) -> float | None:
    share = stage2_share_pct / 100.0
    if share <= 0.0 or target_speedup <= 1.0:
        return None
    required = (1.0 - (1.0 / target_speedup)) / share
    return required


def build_payload(kpi_payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(kpi_payload.get("rows", []))
    envelope_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []

    pacing_rows = sorted(
        rows,
        key=lambda row: _safe_float(row.get("projected_1m_wall_hr")),
        reverse=True,
    )

    for row in rows:
        task = str(row.get("task_id", "")).strip()
        stage2_share_pct = _safe_float(row.get("stage2_share_pct"))
        projected_100k_wall_min = _safe_float(row.get("projected_100k_wall_min"))
        projected_1m_wall_hr = _safe_float(row.get("projected_1m_wall_hr"))
        for avoided_fraction in AVOID_FRACTIONS:
            speedup = _overall_speedup(stage2_share_pct, avoided_fraction)
            envelope_rows.append(
                {
                    "task_id": task,
                    "set_id": str(row.get("set_id", "")).strip(),
                    "domain": str(row.get("domain", "")).strip(),
                    "priority": str(row.get("priority", "")).strip(),
                    "stage2_share_pct": round(stage2_share_pct, 2),
                    "avoided_stage2_fraction": round(avoided_fraction, 2),
                    "overall_speedup_x": round(speedup, 3),
                    "projected_100k_wall_min_after_cascade": round(projected_100k_wall_min / speedup, 2),
                    "projected_1m_wall_hr_after_cascade": round(projected_1m_wall_hr / speedup, 2),
                }
            )
        for target_speedup in TARGET_SPEEDUPS:
            required = _required_avoid_fraction(stage2_share_pct, target_speedup)
            route_rows.append(
                {
                    "task_id": task,
                    "set_id": str(row.get("set_id", "")).strip(),
                    "domain": str(row.get("domain", "")).strip(),
                    "priority": str(row.get("priority", "")).strip(),
                    "stage2_share_pct": round(stage2_share_pct, 2),
                    "target_speedup_x": target_speedup,
                    "required_avoided_stage2_fraction": "" if required is None else round(required, 3),
                    "feasible_with_stage2_only_avoidance": "yes" if required is not None and required <= 1.0 else "no",
                }
            )

    pacing_task_ids = [str(row.get("task_id", "")).strip() for row in pacing_rows[:3]]
    highlight_task_ids = list(dict.fromkeys(pacing_task_ids + ["gpcr_core_full"]))
    summary = {
        "task_count": len(rows),
        "scenario_count": len(envelope_rows),
        "route_target_count": len(route_rows),
        "mean_stage2_share_pct": _safe_float(kpi_payload.get("summary", {}).get("mean_stage2_share_pct")),
        "pacing_task_ids": pacing_task_ids,
        "highlight_task_ids": highlight_task_ids,
        "next_required_step": (
            "Use this envelope to decide whether the residual layer should stay as a score-only "
            "correction or become a true router that avoids expensive stage2 work."
        ),
    }
    return {"summary": summary, "envelope_rows": envelope_rows, "route_rows": route_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Ligand Cascade Speedup Envelope",
        "",
        f"- task_count: `{summary['task_count']}`",
        f"- scenario_count: `{summary['scenario_count']}`",
        f"- route_target_count: `{summary['route_target_count']}`",
        f"- mean_stage2_share_pct: `{summary['mean_stage2_share_pct']}`",
        f"- pacing_task_ids: `{summary['pacing_task_ids']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Pacing Envelope",
        "",
        "| task_id | avoided_stage2_fraction | overall_speedup_x | 100k(min) after cascade | 1M(hr) after cascade |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    highlight = set(summary["highlight_task_ids"])
    for row in payload["envelope_rows"]:
        if row["task_id"] not in highlight:
            continue
        lines.append(
            f"| {row['task_id']} | {row['avoided_stage2_fraction']:.2f} | {row['overall_speedup_x']:.3f} | "
            f"{row['projected_100k_wall_min_after_cascade']:.2f} | {row['projected_1m_wall_hr_after_cascade']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Required Stage2 Avoidance",
            "",
            "| task_id | target_speedup_x | required_avoided_stage2_fraction | feasible_with_stage2_only_avoidance |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["route_rows"]:
        if row["task_id"] not in highlight:
            continue
        required = row["required_avoided_stage2_fraction"]
        rendered = required if required != "" else "NA"
        lines.append(
            f"| {row['task_id']} | {row['target_speedup_x']:.1f} | {rendered} | "
            f"{row['feasible_with_stage2_only_avoidance']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a throughput envelope for a top-k cascade/global residual layer "
            "using the current ligand scale-up KPI artifact."
        )
    )
    parser.add_argument("--kpi-json", default=DEFAULT_KPI_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(_resolve(args.kpi_json)))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["envelope_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
