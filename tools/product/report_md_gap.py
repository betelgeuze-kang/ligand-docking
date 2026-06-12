#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from typing import Any, Dict, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None


def _read_csv_or_empty(path: Optional[str]) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _engine_counts(df: pd.DataFrame) -> Dict[str, int]:
    if df.empty or "engine" not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df["engine"].astype(str).value_counts(dropna=False).to_dict().items()}


def _matches_md_engine(engine: str, pattern: str) -> bool:
    if engine is None:
        return False
    return re.search(pattern, str(engine), flags=re.IGNORECASE) is not None


def _manifest_stats(df: pd.DataFrame, md_engine_regex: str) -> Dict[str, Any]:
    if df.empty:
        return {
            "rows": 0,
            "existing_paths": 0,
            "missing_paths": 0,
            "targets": 0,
            "engine_counts": {},
            "md_engine_rows": 0,
            "md_engine_existing_rows": 0,
            "md_engine_targets": 0,
            "md_engine_existing_targets": 0,
        }

    paths = df["path"].astype(str).tolist() if "path" in df.columns else []
    existing_mask = [os.path.exists(p) for p in paths]
    rows = int(len(df))
    existing_rows = int(sum(existing_mask))
    missing_rows = int(rows - existing_rows)

    targets = set(str(x).strip() for x in df["target"].astype(str).tolist()) if "target" in df.columns else set()
    engines = df["engine"].astype(str).tolist() if "engine" in df.columns else [""] * rows

    md_mask = [_matches_md_engine(e, md_engine_regex) for e in engines]
    md_rows = int(sum(md_mask))
    md_existing_rows = int(sum(m and ex for m, ex in zip(md_mask, existing_mask)))

    md_targets = set()
    md_existing_targets = set()
    if "target" in df.columns:
        for t, is_md, exists in zip(df["target"].astype(str).tolist(), md_mask, existing_mask):
            if is_md:
                md_targets.add(str(t).strip())
                if exists:
                    md_existing_targets.add(str(t).strip())

    return {
        "rows": rows,
        "existing_paths": existing_rows,
        "missing_paths": missing_rows,
        "targets": int(len(targets)),
        "engine_counts": _engine_counts(df),
        "md_engine_rows": md_rows,
        "md_engine_existing_rows": md_existing_rows,
        "md_engine_targets": int(len(md_targets)),
        "md_engine_existing_targets": int(len(md_existing_targets)),
    }


def _accuracy_stats(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {
            "rows": 0,
            "avg_rmsd_raw_A": None,
            "avg_rmsd_aligned_A": None,
            "avg_rmsd_vs_native_raw_A": None,
            "avg_rmsd_vs_native_aligned_A": None,
            "worst_target_raw": None,
            "worst_rmsd_raw_A": None,
            "worst_target_aligned": None,
            "worst_rmsd_aligned_A": None,
            "reference_engine_counts": {},
        }

    raw_col = "avg_rmsd_raw" if "avg_rmsd_raw" in df.columns else "avg_rmsd"
    aligned_col = "avg_rmsd_aligned" if "avg_rmsd_aligned" in df.columns else None
    vs_native_raw_col = "avg_rmsd_vs_native_raw" if "avg_rmsd_vs_native_raw" in df.columns else "avg_rmsd_vs_native"
    vs_native_aligned_col = (
        "avg_rmsd_vs_native_aligned" if "avg_rmsd_vs_native_aligned" in df.columns else None
    )

    raw_vals = pd.to_numeric(df.get(raw_col), errors="coerce")
    aligned_vals = pd.to_numeric(df.get(aligned_col), errors="coerce") if aligned_col else pd.Series(dtype=float)
    vnr_vals = pd.to_numeric(df.get(vs_native_raw_col), errors="coerce")
    vna_vals = (
        pd.to_numeric(df.get(vs_native_aligned_col), errors="coerce")
        if vs_native_aligned_col
        else pd.Series(dtype=float)
    )

    worst_raw_target = None
    worst_raw = None
    if raw_col in df.columns and not raw_vals.dropna().empty:
        i = int(raw_vals.idxmax())
        worst_raw_target = str(df.loc[i, "target"]) if "target" in df.columns else None
        worst_raw = _to_float(raw_vals.loc[i])

    worst_aligned_target = None
    worst_aligned = None
    if aligned_col and (aligned_col in df.columns) and not aligned_vals.dropna().empty:
        j = int(aligned_vals.idxmax())
        worst_aligned_target = str(df.loc[j, "target"]) if "target" in df.columns else None
        worst_aligned = _to_float(aligned_vals.loc[j])

    ref_engine_counts = {}
    if "reference_engine" in df.columns:
        ref_engine_counts = {
            str(k): int(v)
            for k, v in df["reference_engine"].astype(str).value_counts(dropna=False).to_dict().items()
        }

    return {
        "rows": int(len(df)),
        "avg_rmsd_raw_A": _to_float(raw_vals.mean()),
        "avg_rmsd_aligned_A": _to_float(aligned_vals.mean()) if not aligned_vals.empty else None,
        "avg_rmsd_vs_native_raw_A": _to_float(vnr_vals.mean()),
        "avg_rmsd_vs_native_aligned_A": _to_float(vna_vals.mean()) if not vna_vals.empty else None,
        "worst_target_raw": worst_raw_target,
        "worst_rmsd_raw_A": worst_raw,
        "worst_target_aligned": worst_aligned_target,
        "worst_rmsd_aligned_A": worst_aligned,
        "reference_engine_counts": ref_engine_counts,
    }


def build_gap_report(
    accuracy_csv: str,
    manifest_csv: str,
    md_only_manifest_csv: Optional[str],
    baseline_status_json: Optional[str],
    out_json: str,
    md_engine_regex: str,
    expected_target_count: int,
) -> Dict[str, Any]:
    accuracy_df = _read_csv_or_empty(accuracy_csv)
    manifest_df = _read_csv_or_empty(manifest_csv)
    md_only_df = _read_csv_or_empty(md_only_manifest_csv) if md_only_manifest_csv else pd.DataFrame()

    manifest_info = _manifest_stats(manifest_df, md_engine_regex=md_engine_regex)
    md_only_info = _manifest_stats(md_only_df, md_engine_regex=md_engine_regex) if not md_only_df.empty else {
        "rows": 0,
        "existing_paths": 0,
        "missing_paths": 0,
        "targets": 0,
        "engine_counts": {},
        "md_engine_rows": 0,
        "md_engine_existing_rows": 0,
        "md_engine_targets": 0,
        "md_engine_existing_targets": 0,
    }
    acc_info = _accuracy_stats(accuracy_df)

    ready = bool(
        md_only_info["rows"] >= int(expected_target_count)
        and md_only_info["md_engine_existing_targets"] >= int(expected_target_count)
    )
    reason = None
    if not ready:
        reason = (
            "md-only manifest does not cover expected targets with existing files; "
            f"expected={int(expected_target_count)} md_existing_targets={md_only_info['md_engine_existing_targets']}"
        )

    baseline = None
    if baseline_status_json and os.path.exists(baseline_status_json):
        with open(baseline_status_json, "r", encoding="utf-8") as f:
            baseline = json.load(f)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "status": {
            "real_md_comparison_ready": ready,
            "reason_if_not_ready": reason,
            "expected_target_count": int(expected_target_count),
            "md_engine_regex": md_engine_regex,
        },
        "manifest_summary": {
            "manifest_csv": manifest_csv,
            **manifest_info,
        },
        "md_only_manifest_summary": {
            "md_only_manifest_csv": md_only_manifest_csv,
            **md_only_info,
        },
        "accuracy_summary": {
            "accuracy_csv": accuracy_csv,
            **acc_info,
        },
        "baseline_status": baseline,
    }

    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build MD-gap report (real MD readiness + current accuracy summary)."
    )
    parser.add_argument("--accuracy-csv", type=str, default="runs/accuracy_external_report.csv")
    parser.add_argument("--manifest-csv", type=str, default="runs/external_ref_manifest_real_template.csv")
    parser.add_argument("--md-only-manifest-csv", type=str, default="runs/external_ref_manifest_md_only.csv")
    parser.add_argument("--baseline-status-json", type=str, default="runs/baseline_mode_status.json")
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    parser.add_argument("--out-json", type=str, default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_json = str(args.out_json) if args.out_json else f"runs/md_gap_report_{dt.date.today().isoformat()}.json"
    payload = build_gap_report(
        accuracy_csv=str(args.accuracy_csv),
        manifest_csv=str(args.manifest_csv),
        md_only_manifest_csv=str(args.md_only_manifest_csv) if args.md_only_manifest_csv else None,
        baseline_status_json=str(args.baseline_status_json) if args.baseline_status_json else None,
        out_json=out_json,
        md_engine_regex=str(args.md_engine_regex),
        expected_target_count=int(args.expected_target_count),
    )
    print(f"Wrote: {out_json}")
    print(json.dumps(payload["status"], indent=2))
    print(json.dumps(payload["accuracy_summary"], indent=2))


if __name__ == "__main__":
    main()
