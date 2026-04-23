#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants


def _matches(engine: str, pattern: str) -> bool:
    if engine is None:
        return False
    return re.search(pattern, str(engine), flags=re.IGNORECASE) is not None


def _has_value(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    return len(s) > 0 and s.lower() != "nan"


def _validate_row(
    row: Dict[str, Any],
    engine_regex: str,
    source_engine_regex: str,
    require_source_engine: bool,
    require_source_path: bool,
) -> Dict[str, Any]:
    target = str(row.get("target", "")).strip()
    path = str(row.get("path", "")).strip()
    engine = str(row.get("engine", "")).strip()
    source_engine_raw = row.get("source_engine", "")
    source_path_raw = row.get("source_path", "")
    source_engine = str(source_engine_raw).strip()
    source_path = str(source_path_raw).strip()

    reasons: List[str] = []
    path_exists = bool(path) and os.path.exists(path)
    engine_ok = _matches(engine, engine_regex)

    source_engine_present = _has_value(source_engine_raw)
    source_engine_ok = source_engine_present and _matches(source_engine, source_engine_regex)
    source_path_present = _has_value(source_path_raw)
    source_path_exists = source_path_present and os.path.exists(source_path)

    if not target:
        reasons.append("missing_target")
    if not path:
        reasons.append("missing_path")
    if path and not path_exists:
        reasons.append("missing_path_file")
    if not engine_ok:
        reasons.append("engine_not_md")

    if require_source_engine:
        if not source_engine_present:
            reasons.append("missing_source_engine")
        elif not source_engine_ok:
            reasons.append("source_engine_not_md")

    if require_source_path:
        if not source_path_present:
            reasons.append("missing_source_path")
        elif not source_path_exists:
            reasons.append("missing_source_path_file")

    row_ok = len(reasons) == 0
    return {
        "target": target,
        "path": path,
        "engine": engine,
        "path_exists": path_exists,
        "engine_is_md": engine_ok,
        "source_engine": source_engine if source_engine_present else "",
        "source_engine_present": source_engine_present,
        "source_engine_is_md": source_engine_ok,
        "source_path": source_path if source_path_present else "",
        "source_path_present": source_path_present,
        "source_path_exists": source_path_exists,
        "row_ok": row_ok,
        "reasons": reasons,
    }


def validate_md_provenance(
    manifest_csv: str,
    out_json: str,
    out_csv: str,
    engine_regex: str,
    source_engine_regex: str,
    require_source_engine: bool,
    require_source_path: bool,
    expected_target_count: int,
    strict: bool,
) -> Dict[str, Any]:
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"manifest not found: {manifest_csv}")
    df = pd.read_csv(manifest_csv)
    if "target" not in df.columns or "path" not in df.columns:
        raise ValueError("manifest must include columns: target, path")
    if "engine" not in df.columns:
        df["engine"] = ""

    rows = df.to_dict(orient="records")
    results = [
        _validate_row(
            row=dict(row),
            engine_regex=engine_regex,
            source_engine_regex=source_engine_regex,
            require_source_engine=require_source_engine,
            require_source_path=require_source_path,
        )
        for row in rows
    ]
    out_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    target_ok: Dict[str, bool] = {}
    for _, r in out_df.iterrows():
        t = str(r.get("target", "")).strip()
        if not t:
            continue
        row_ok = bool(r.get("row_ok", False))
        target_ok[t] = bool(target_ok.get(t, True) and row_ok)

    failed_rows = []
    for _, r in out_df.iterrows():
        if bool(r.get("row_ok", False)):
            continue
        reasons_val = r.get("reasons")
        if isinstance(reasons_val, list):
            reasons = [str(x) for x in reasons_val]
        elif reasons_val is None:
            reasons = []
        else:
            reasons = [str(reasons_val)]
        failed_rows.append(
            {
                "target": str(r.get("target", "")).strip(),
                "path": str(r.get("path", "")).strip(),
                "reasons": reasons,
            }
        )

    ok_targets = sorted([t for t, ok in target_ok.items() if ok])
    failed_targets = sorted([t for t, ok in target_ok.items() if not ok])
    summary: Dict[str, Any] = {
        "manifest_csv": manifest_csv,
        "out_csv": out_csv,
        "row_count": int(len(out_df)),
        "target_count": int(len(target_ok)),
        "row_ok_rows": int(out_df["row_ok"].sum()) if not out_df.empty else 0,
        "path_exists_rows": int(out_df["path_exists"].sum()) if not out_df.empty else 0,
        "engine_is_md_rows": int(out_df["engine_is_md"].sum()) if not out_df.empty else 0,
        "source_engine_present_rows": int(out_df["source_engine_present"].sum()) if not out_df.empty else 0,
        "source_engine_is_md_rows": int(out_df["source_engine_is_md"].sum()) if not out_df.empty else 0,
        "source_path_present_rows": int(out_df["source_path_present"].sum()) if not out_df.empty else 0,
        "source_path_exists_rows": int(out_df["source_path_exists"].sum()) if not out_df.empty else 0,
        "engine_regex": engine_regex,
        "source_engine_regex": source_engine_regex,
        "require_source_engine": bool(require_source_engine),
        "require_source_path": bool(require_source_path),
        "expected_target_count": int(expected_target_count),
        "ok_targets": ok_targets,
        "failed_targets": failed_targets,
        "failed_rows": failed_rows,
    }
    summary["ready"] = bool(len(ok_targets) >= int(expected_target_count) and len(failed_targets) == 0)
    payload = {"summary": summary}

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if strict and not bool(summary["ready"]):
        raise RuntimeError(
            f"MD provenance validation failed: ok_targets={len(ok_targets)} "
            f"expected={int(expected_target_count)} failed_targets={failed_targets}"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate MD manifest provenance metadata (engine/source_engine/source_path)."
    )
    parser.add_argument("--manifest-csv", type=str, default="runs/external_ref_manifest_md_only_proxy_openmm.csv")
    parser.add_argument("--out-json", type=str, default="runs/md_reference_validation_provenance.json")
    parser.add_argument("--out-csv", type=str, default="runs/md_reference_validation_provenance.csv")
    parser.add_argument("--engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--source-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--require-source-engine", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-source-path", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = validate_md_provenance(
            manifest_csv=str(args.manifest_csv),
            out_json=str(args.out_json),
            out_csv=str(args.out_csv),
            engine_regex=str(args.engine_regex),
            source_engine_regex=str(args.source_engine_regex),
            require_source_engine=bool(args.require_source_engine),
            require_source_path=bool(args.require_source_path),
            expected_target_count=int(args.expected_target_count),
            strict=bool(args.strict),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
