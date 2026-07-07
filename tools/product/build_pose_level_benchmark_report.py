from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

POSE_RMSD_COL = "pose_rmsd_A"
LDDT_PLI_COL = "lddt_pli"
BISYRMSD_COL = "bisyrmsd"
CLASH_COUNT_COL = "clash_count"
LIGAND_STRAIN_COL = "ligand_strain_kcal_mol"
HBOND_GEOMETRY_COL = "hbond_geometry_score"
CONTACT_RECOVERY_COL = "contact_recovery"
MEAN_MIN_DISTANCE_COL = "mean_min_distance_A"

LOWER_BETTER_METRICS = {
    POSE_RMSD_COL,
    BISYRMSD_COL,
    CLASH_COUNT_COL,
    LIGAND_STRAIN_COL,
    MEAN_MIN_DISTANCE_COL,
}
HIGHER_BETTER_METRICS = {LDDT_PLI_COL, HBOND_GEOMETRY_COL, CONTACT_RECOVERY_COL}

DEFAULT_THRESHOLDS: dict[str, tuple[str, float]] = {
    POSE_RMSD_COL: ("max", 2.0),
    LDDT_PLI_COL: ("min", 0.45),
    BISYRMSD_COL: ("max", 2.5),
    CLASH_COUNT_COL: ("max", 0.0),
    LIGAND_STRAIN_COL: ("max", 8.0),
    HBOND_GEOMETRY_COL: ("min", 0.35),
    CONTACT_RECOVERY_COL: ("min", 0.30),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        if math.isnan(v):
            return None
        return float(v)
    except Exception:
        return None


def _series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").dropna()


def _metric_summary(df: pd.DataFrame, col: str) -> dict[str, Any]:
    vals = _series(df, col)
    if vals.empty:
        return {"present": False, "count": 0}
    threshold_mode, threshold_value = DEFAULT_THRESHOLDS.get(col, ("", 0.0))
    pass_count = 0
    if threshold_mode == "max":
        pass_count = int((vals <= float(threshold_value)).sum())
    elif threshold_mode == "min":
        pass_count = int((vals >= float(threshold_value)).sum())
    return {
        "present": True,
        "count": int(vals.shape[0]),
        "mean": float(vals.mean()),
        "median": float(vals.median()),
        "min": float(vals.min()),
        "max": float(vals.max()),
        "threshold_mode": threshold_mode,
        "threshold_value": float(threshold_value) if threshold_mode else None,
        "pass_count": int(pass_count),
        "pass_rate": float(pass_count / max(int(vals.shape[0]), 1)) if threshold_mode else None,
    }


def _row_id(row: dict[str, Any], idx: int) -> str:
    for keys in [("target", "ligand_id"), ("pdb_id", "ligand_id"), ("target", "pose_id")]:
        left, right = keys
        if _text(row.get(left)) and _text(row.get(right)):
            return f"{_text(row.get(left))}::{_text(row.get(right))}"
    for key in ("row_id", "pose_id", "queue_id"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return f"row_{idx:05d}"


def _row_failures(row: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for metric, (mode, threshold) in DEFAULT_THRESHOLDS.items():
        value = _num(row.get(metric))
        if value is None:
            continue
        failed = value > threshold if mode == "max" else value < threshold
        if failed:
            failures.append(
                {
                    "metric": metric,
                    "value": value,
                    "threshold_mode": mode,
                    "threshold_value": float(threshold),
                }
            )
    return failures


def _available_metrics(df: pd.DataFrame) -> list[str]:
    return [metric for metric in DEFAULT_THRESHOLDS if metric in df.columns]


def build_pose_level_benchmark_report(scores_csv: str, *, out_json: str, out_md: str = "") -> dict[str, Any]:
    src = Path(scores_csv)
    if not src.is_file():
        raise FileNotFoundError(f"pose benchmark scores csv not found: {scores_csv}")
    df = pd.read_csv(src)
    metrics = _available_metrics(df)
    metric_summaries = {metric: _metric_summary(df, metric) for metric in DEFAULT_THRESHOLDS}
    row_failures: list[dict[str, Any]] = []
    for idx, row in enumerate(df.to_dict(orient="records"), start=1):
        failures = _row_failures(row)
        if not failures:
            continue
        row_failures.append(
            {
                "row_id": _row_id(row, idx),
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "failure_count": int(len(failures)),
                "failures": failures,
            }
        )
    required = [POSE_RMSD_COL, CLASH_COUNT_COL, LIGAND_STRAIN_COL, HBOND_GEOMETRY_COL, CONTACT_RECOVERY_COL]
    missing_required = [metric for metric in required if metric not in df.columns]
    present_metric_count = int(len(metrics))
    row_count = int(len(df))
    threshold_metric_count = int(sum(1 for metric in metrics if metric in DEFAULT_THRESHOLDS))
    blocked_metric_rows = int(len(row_failures))
    pass_rate = float((row_count - blocked_metric_rows) / max(row_count, 1)) if row_count else 0.0
    status = "pose_level_benchmark_ready" if row_count > 0 and not missing_required else "pose_level_benchmark_incomplete"
    if blocked_metric_rows > 0:
        status = "pose_level_benchmark_threshold_review"
    payload = {
        "summary": {
            "status": status,
            "scores_csv": str(src),
            "row_count": row_count,
            "present_metric_count": present_metric_count,
            "threshold_metric_count": threshold_metric_count,
            "missing_required_metrics": missing_required,
            "blocked_metric_row_count": blocked_metric_rows,
            "threshold_pass_rate": pass_rate,
            "claim_boundary": "Pose-level benchmark report only; does not promote broad docking parity or wetlab hit claims.",
        },
        "metric_summaries": metric_summaries,
        "blocked_rows": row_failures,
        "metric_definitions": {
            "pose_rmsd_A": "Pose RMSD in Angstrom; lower is better.",
            "lddt_pli": "Ligand-protein interaction lDDT proxy; higher is better.",
            "bisyrmsd": "Binding-site RMSD-style metric; lower is better.",
            "clash_count": "Steric clash count; lower is better.",
            "ligand_strain_kcal_mol": "Ligand strain energy proxy in kcal/mol; lower is better.",
            "hbond_geometry_score": "Hydrogen-bond geometry score; higher is better.",
            "contact_recovery": "Native or reference contact recovery fraction; higher is better.",
        },
    }
    out_path = Path(out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if out_md:
        _write_markdown(payload, Path(out_md))
    return payload


def _write_markdown(payload: dict[str, Any], out_md: Path) -> None:
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Pose-Level Benchmark Report",
        "",
        f"- status: `{summary.get('status')}`",
        f"- row_count: {summary.get('row_count')}",
        f"- present_metric_count: {summary.get('present_metric_count')}",
        f"- missing_required_metrics: `{summary.get('missing_required_metrics')}`",
        f"- blocked_metric_row_count: {summary.get('blocked_metric_row_count')}",
        f"- threshold_pass_rate: {summary.get('threshold_pass_rate')}",
        "",
        "## Metrics",
        "",
        "| metric | present | count | mean | threshold | pass_rate |",
        "| --- | ---: | ---: | ---: | --- | ---: |",
    ]
    summaries = payload.get("metric_summaries", {}) if isinstance(payload.get("metric_summaries"), dict) else {}
    for metric, row in summaries.items():
        if not isinstance(row, dict):
            continue
        threshold = ""
        if row.get("threshold_mode"):
            threshold = f"{row.get('threshold_mode')} {row.get('threshold_value')}"
        lines.append(
            "| {metric} | {present} | {count} | {mean} | {threshold} | {pass_rate} |".format(
                metric=metric,
                present=row.get("present"),
                count=row.get("count"),
                mean="" if row.get("mean") is None else f"{float(row.get('mean')):.4g}",
                threshold=threshold,
                pass_rate="" if row.get("pass_rate") is None else f"{float(row.get('pass_rate')):.4g}",
            )
        )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a pose-level benchmark report from docking score/pose rows.")
    p.add_argument("--scores-csv", required=True)
    p.add_argument("--out-json", default="runs/pose_level_benchmark_report_current.json")
    p.add_argument("--out-md", default="runs/pose_level_benchmark_report_current.md")
    return p


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_pose_level_benchmark_report(args.scores_csv, out_json=args.out_json, out_md=args.out_md)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
