#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Dict, List

import pandas as pd


def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _classify_row(row: Dict[str, object], speedup_threshold: float) -> Dict[str, object]:
    target = str(row.get("target", "unknown"))
    speedup = _safe_float(row.get("speedup_on_vs_off"), 0.0)
    th_on = _safe_float(row.get("throughput_on"), 0.0)
    th_off = _safe_float(row.get("throughput_off"), 0.0)
    force_off = _safe_float(row.get("force_ms_off"), 0.0)
    ai_off = _safe_float(row.get("ai_ms_off"), 0.0)
    integ_off = _safe_float(row.get("integrator_ms_off"), 0.0)
    neighbor_off = _safe_float(row.get("neighbor_ms_off"), 0.0)
    step_off = _safe_float(row.get("step_ms_off"), 0.0)

    if speedup < speedup_threshold:
        severity = "high"
    elif speedup < (speedup_threshold * 1.25):
        severity = "medium"
    else:
        severity = "low"

    dominant_component = "unknown"
    component_candidates = {
        "ai_off_ms": ai_off,
        "force_off_ms": force_off,
        "integrator_off_ms": integ_off,
        "neighbor_off_ms": neighbor_off,
    }
    if any(v > 0.0 for v in component_candidates.values()):
        dominant_component = max(component_candidates, key=component_candidates.get)

    if dominant_component == "ai_off_ms":
        bottleneck_cause = "ai_inference_dominant"
        recommendation = (
            "raise AI interval/adaptive MTS, enable top-k active modules, and remove python boundary "
            "(TorchScript/ONNX/Rust runtime)"
        )
    elif dominant_component == "force_off_ms":
        bottleneck_cause = "pytorch_force_backend_dominant"
        recommendation = "keep rust_hip on-path and raise benchmark replicas for fair steady-state gating"
    elif dominant_component == "integrator_off_ms":
        bottleneck_cause = "integrator_overhead_dominant"
        recommendation = "increase replicas or reduce per-step python overhead in benchmark loop"
    elif dominant_component == "neighbor_off_ms":
        bottleneck_cause = "neighbor_list_overhead_dominant"
        recommendation = "tune cutoff/skin/rebuild_stride and verify no overflow/saturation"
    else:
        bottleneck_cause = "insufficient_component_profile"
        recommendation = "rerun stage2 with --profile-components to collect component timings"

    return {
        "target": target,
        "severity": severity,
        "speedup_on_vs_off": speedup,
        "throughput_on": th_on,
        "throughput_off": th_off,
        "step_ms_off": step_off,
        "dominant_component": dominant_component,
        "bottleneck_cause": bottleneck_cause,
        "recommendation": recommendation,
    }


def _build_summary(df: pd.DataFrame, items: List[Dict[str, object]], speedup_threshold: float) -> Dict[str, object]:
    total = int(len(df))
    failed = [x for x in items if _safe_float(x.get("speedup_on_vs_off"), 0.0) < float(speedup_threshold)]
    near = [
        x
        for x in items
        if float(speedup_threshold) <= _safe_float(x.get("speedup_on_vs_off"), 0.0) < (float(speedup_threshold) * 1.25)
    ]
    avg_speedup = float(df["speedup_on_vs_off"].mean()) if "speedup_on_vs_off" in df.columns and total > 0 else 0.0
    avg_on = float(df["throughput_on"].mean()) if "throughput_on" in df.columns and total > 0 else 0.0
    avg_off = float(df["throughput_off"].mean()) if "throughput_off" in df.columns and total > 0 else 0.0
    return {
        "targets": total,
        "speedup_threshold": float(speedup_threshold),
        "avg_speedup_on_vs_off": avg_speedup,
        "avg_throughput_on": avg_on,
        "avg_throughput_off": avg_off,
        "failed_targets_count": int(len(failed)),
        "failed_targets": [str(x.get("target", "")) for x in failed],
        "near_threshold_targets_count": int(len(near)),
        "near_threshold_targets": [str(x.get("target", "")) for x in near],
        "pass": len(failed) == 0,
    }


def run_report(args: argparse.Namespace) -> Dict[str, object]:
    df = pd.read_csv(args.input_csv)
    required = {"target", "throughput_on", "throughput_off", "speedup_on_vs_off"}
    missing = sorted([c for c in required if c not in df.columns])
    if missing:
        raise ValueError(f"missing required columns in {args.input_csv}: {missing}")

    rows: List[Dict[str, object]] = []
    for rec in df.to_dict(orient="records"):
        rows.append(_classify_row(rec, speedup_threshold=float(args.speedup_threshold)))
    rows = sorted(rows, key=lambda x: _safe_float(x.get("speedup_on_vs_off"), 0.0))
    summary = _build_summary(df, rows, speedup_threshold=float(args.speedup_threshold))

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "input_csv": os.path.abspath(args.input_csv),
        "summary": summary,
        "rows": rows,
    }

    out_csv = str(args.out_csv)
    out_json = str(args.out_json)
    out_md = str(args.out_md)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)

    pd.DataFrame(rows).to_csv(out_csv, index=False)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    _write_md(out_md, payload)
    return payload


def _write_md(path: str, payload: Dict[str, object]) -> None:
    summary = payload.get("summary", {})
    lines: List[str] = []
    lines.append("# Stage2 Speed Bottleneck Report")
    lines.append("")
    lines.append(f"- input_csv: `{payload.get('input_csv')}`")
    lines.append(f"- targets: `{summary.get('targets')}`")
    lines.append(f"- speedup_threshold: `{summary.get('speedup_threshold')}`")
    lines.append(f"- avg_speedup_on_vs_off: `{summary.get('avg_speedup_on_vs_off')}`")
    lines.append(f"- pass: `{summary.get('pass')}`")
    lines.append(f"- failed_targets: `{','.join(summary.get('failed_targets', []))}`")
    lines.append("")
    lines.append("## Low-Speed Targets")
    lines.append("")
    for row in payload.get("rows", []):
        sp = _safe_float(row.get("speedup_on_vs_off"), 0.0)
        lines.append(
            f"- `{row.get('target')}` speedup={sp:.4f}, severity={row.get('severity')}, "
            f"cause={row.get('bottleneck_cause')}, rec={row.get('recommendation')}"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate target-wise speed bottleneck report from stage2 CSV.")
    p.add_argument("--input-csv", type=str, required=True)
    p.add_argument("--speedup-threshold", type=float, default=12.0)
    p.add_argument("--out-csv", type=str, default="runs/stage2_speed_bottlenecks.csv")
    p.add_argument("--out-json", type=str, default="runs/stage2_speed_bottlenecks.json")
    p.add_argument("--out-md", type=str, default="runs/stage2_speed_bottlenecks.md")
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = run_report(args)
    print(json.dumps(payload.get("summary", {}), ensure_ascii=False, indent=2))
    print(f"Wrote CSV: {args.out_csv}")
    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote MD: {args.out_md}")


if __name__ == "__main__":
    main()
