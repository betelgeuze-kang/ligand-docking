#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _match_engine(v: Any, pattern: str) -> bool:
    if v is None:
        return False
    return re.search(pattern, str(v), flags=re.IGNORECASE) is not None


def _str_or_empty(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def _pick_meta(meta: Dict[str, Any], key: str) -> str:
    return _str_or_empty(meta.get(key, ""))


def _pick_with_fallback(meta: Dict[str, Any], row: Dict[str, Any], mkey: str, rkey: str) -> str:
    mv = _pick_meta(meta, mkey)
    if mv:
        return mv
    return _str_or_empty(row.get(rkey, ""))


def prepare_real_md_manifest(
    input_manifest: str,
    metadata_csv: str,
    template_csv: str,
    out_manifest: str,
    out_json: str,
    engine_regex: str,
    write_template: bool,
    require_existing_source_path: bool,
    expected_target_count: int,
    strict: bool,
) -> Dict[str, Any]:
    if not os.path.exists(input_manifest):
        raise FileNotFoundError(f"input manifest not found: {input_manifest}")

    in_df = pd.read_csv(input_manifest)
    for col in ("target", "path"):
        if col not in in_df.columns:
            raise ValueError(f"input manifest missing required column: {col}")
    if "engine" not in in_df.columns:
        in_df["engine"] = ""
    if "label" not in in_df.columns:
        in_df["label"] = ""
    if "frame" not in in_df.columns:
        in_df["frame"] = -1

    meta_df = pd.DataFrame()
    if os.path.exists(metadata_csv):
        meta_df = pd.read_csv(metadata_csv)
    if not meta_df.empty and "target" not in meta_df.columns:
        raise ValueError(f"metadata csv missing required column: target ({metadata_csv})")

    meta_by_target: Dict[str, Dict[str, Any]] = {}
    if not meta_df.empty:
        for row in meta_df.to_dict(orient="records"):
            t = _str_or_empty(row.get("target", ""))
            if not t:
                continue
            meta_by_target[_normalize_target_key(t)] = row

    out_rows: List[Dict[str, Any]] = []
    template_rows: List[Dict[str, Any]] = []
    missing_targets: List[str] = []
    ready_targets: List[str] = []
    failed_targets: List[str] = []
    failures: List[Dict[str, Any]] = []

    for row in in_df.to_dict(orient="records"):
        target = _str_or_empty(row.get("target", ""))
        path = _str_or_empty(row.get("path", ""))
        input_engine = _str_or_empty(row.get("engine", ""))
        meta = meta_by_target.get(_normalize_target_key(target), {})
        meta_present = len(meta) > 0
        if not meta_present:
            missing_targets.append(target)

        engine = _pick_with_fallback(meta, row, "md_engine", "engine")
        label = _pick_with_fallback(meta, row, "label", "label")
        frame = _pick_with_fallback(meta, row, "frame", "frame") or "-1"
        source_engine = _pick_meta(meta, "source_engine")
        source_path = _pick_meta(meta, "source_path")
        source_label = _pick_meta(meta, "source_label")

        row_out = {
            "target": target,
            "path": path,
            "engine": engine,
            "label": label,
            "frame": frame,
            "source_engine": source_engine,
            "source_path": source_path,
            "source_label": source_label,
            "md_forcefield": _pick_meta(meta, "md_forcefield"),
            "md_water_model": _pick_meta(meta, "md_water_model"),
            "md_temperature_k": _pick_meta(meta, "md_temperature_k"),
            "md_timestep_fs": _pick_meta(meta, "md_timestep_fs"),
            "md_steps": _pick_meta(meta, "md_steps"),
            "md_software_version": _pick_meta(meta, "md_software_version"),
            "notes": _pick_meta(meta, "notes"),
            "input_engine": input_engine,
            "metadata_row_present": bool(meta_present),
        }
        out_rows.append(row_out)

        reasons: List[str] = []
        if not meta_present:
            reasons.append("missing_metadata_row")
        if not _match_engine(engine, engine_regex):
            reasons.append("engine_not_md")
        if not _match_engine(source_engine, engine_regex):
            reasons.append("source_engine_not_md")
        if require_existing_source_path:
            if (not source_path) or (not os.path.exists(source_path)):
                reasons.append("source_path_missing_or_not_exists")

        if len(reasons) == 0:
            ready_targets.append(target)
        else:
            failed_targets.append(target)
            failures.append({"target": target, "reasons": reasons})

        template_rows.append(
            {
                "target": target,
                "path": path,
                "label": label,
                "frame": frame,
                "input_engine": input_engine,
                "md_engine": engine if _match_engine(engine, engine_regex) else "",
                "source_engine": source_engine if _match_engine(source_engine, engine_regex) else "",
                "source_path": source_path,
                "source_label": source_label,
                "md_forcefield": row_out["md_forcefield"],
                "md_water_model": row_out["md_water_model"],
                "md_temperature_k": row_out["md_temperature_k"],
                "md_timestep_fs": row_out["md_timestep_fs"],
                "md_steps": row_out["md_steps"],
                "md_software_version": row_out["md_software_version"],
                "notes": row_out["notes"],
            }
        )

    os.makedirs(os.path.dirname(out_manifest) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    pd.DataFrame(out_rows).to_csv(out_manifest, index=False, quoting=csv.QUOTE_MINIMAL)

    if write_template:
        os.makedirs(os.path.dirname(template_csv) or ".", exist_ok=True)
        pd.DataFrame(template_rows).to_csv(template_csv, index=False, quoting=csv.QUOTE_MINIMAL)

    summary: Dict[str, Any] = {
        "input_manifest": input_manifest,
        "metadata_csv": metadata_csv,
        "template_csv": template_csv if write_template else None,
        "out_manifest": out_manifest,
        "rows": int(len(out_rows)),
        "targets": int(len({str(x.get('target', '')).strip() for x in out_rows if str(x.get('target', '')).strip()})),
        "missing_metadata_targets": sorted(set([x for x in missing_targets if x])),
        "ready_targets": sorted(set([x for x in ready_targets if x])),
        "failed_targets": sorted(set([x for x in failed_targets if x])),
        "failure_rows": failures,
        "engine_regex": engine_regex,
        "require_existing_source_path": bool(require_existing_source_path),
        "expected_target_count": int(expected_target_count),
    }
    summary["ready"] = bool(
        len(summary["ready_targets"]) >= int(expected_target_count)
        and len(summary["failed_targets"]) == 0
    )

    payload = {"summary": summary}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if strict and not bool(summary["ready"]):
        raise RuntimeError(
            f"real md manifest not ready: ready_targets={len(summary['ready_targets'])} "
            f"expected={int(expected_target_count)} failed_targets={summary['failed_targets']}"
        )

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare strict-real-MD manifest by merging path manifest and manual MD metadata."
    )
    parser.add_argument("--input-manifest", type=str, default="runs/external_ref_manifest_real_filled_2026-02-14.csv")
    parser.add_argument("--metadata-csv", type=str, default="runs/real_md_metadata.csv")
    parser.add_argument("--template-csv", type=str, default="runs/real_md_metadata_template.csv")
    parser.add_argument("--out-manifest", type=str, default="runs/external_ref_manifest_real_md_candidate.csv")
    parser.add_argument(
        "--out-json",
        type=str,
        default="runs/external_ref_manifest_real_md_candidate_summary.json",
    )
    parser.add_argument("--engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--write-template", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-existing-source-path", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = prepare_real_md_manifest(
            input_manifest=str(args.input_manifest),
            metadata_csv=str(args.metadata_csv),
            template_csv=str(args.template_csv),
            out_manifest=str(args.out_manifest),
            out_json=str(args.out_json),
            engine_regex=str(args.engine_regex),
            write_template=bool(args.write_template),
            require_existing_source_path=bool(args.require_existing_source_path),
            expected_target_count=int(args.expected_target_count),
            strict=bool(args.strict),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
