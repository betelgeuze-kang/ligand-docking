#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _slug_target(name: str) -> str:
    out = []
    prev_us = False
    for ch in str(name).lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    slug = "".join(out).strip("_")
    return slug or "target"


def _parse_targets(spec: str) -> List[str]:
    if str(spec).strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in str(spec).split(",") if x.strip()]


def _targets_from_manifest(path: str) -> List[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"manifest not found: {path}")
    df = pd.read_csv(path)
    if "target" not in df.columns:
        raise ValueError(f"manifest missing required column: target ({path})")
    seen: Dict[str, str] = {}
    for t in df["target"].tolist():
        ts = str(t).strip()
        if not ts:
            continue
        k = _normalize_target_key(ts)
        if k not in seen:
            seen[k] = ts
    return list(seen.values())


def _row_map(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        t = str(row.get("target", "")).strip()
        if not t:
            continue
        out[_normalize_target_key(t)] = row
    return out


def scaffold_real_md_source_manifest(
    out_csv: str,
    out_json: str,
    targets_spec: str,
    source_manifest: Optional[str],
    path_pattern: str,
    engine_default: str,
    frame_default: int,
    include_md_config_fields: bool,
    overwrite: bool,
) -> Dict[str, Any]:
    if (not overwrite) and os.path.exists(out_csv):
        raise FileExistsError(f"output already exists: {out_csv} (use --overwrite)")

    targets = _targets_from_manifest(source_manifest) if source_manifest else _parse_targets(targets_spec)
    src_map: Dict[str, Dict[str, Any]] = {}
    if source_manifest:
        df = pd.read_csv(source_manifest)
        src_map = _row_map(df)

    rows: List[Dict[str, Any]] = []
    missing_source_targets: List[str] = []
    for target in targets:
        slug = _slug_target(target)
        k = _normalize_target_key(target)
        src = src_map.get(k, {})
        if source_manifest and (not src):
            missing_source_targets.append(target)

        path_guess = str(path_pattern).replace("{target}", target).replace("{slug}", slug)
        # If pattern resolves to empty/placeholder ".", keep blank to force manual fill.
        if path_guess.strip() in ("", ".", "./"):
            path_guess = ""
        label_default = f"{target}_real_md_source"

        row = {
            "target": target,
            "path": str(src.get("path", "")).strip() if src.get("path") else path_guess,
            "engine": str(src.get("engine", "")).strip() if src.get("engine") else str(engine_default),
            "label": str(src.get("label", "")).strip() if src.get("label") else label_default,
            "frame": int(src.get("frame", frame_default)) if str(src.get("frame", "")).strip() else int(frame_default),
            "key": str(src.get("key", "")).strip() if src.get("key") else "",
            "source_engine": "",
            "source_path": "",
            "source_label": "",
            "notes": "FILL_REAL_MD_SOURCE",
        }
        if include_md_config_fields:
            row.update(
                {
                    "md_forcefield": "",
                    "md_water_model": "",
                    "md_temperature_k": "",
                    "md_timestep_fs": "",
                    "md_steps": "",
                    "md_software_version": "",
                }
            )
        rows.append(row)

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    df_out = pd.DataFrame(rows)
    df_out.to_csv(out_csv, index=False, quoting=csv.QUOTE_MINIMAL)

    summary = {
        "out_csv": out_csv,
        "targets": targets,
        "target_count": int(len(targets)),
        "source_manifest": source_manifest,
        "missing_source_targets": sorted([x for x in missing_source_targets if x]),
        "path_pattern": path_pattern,
        "engine_default": engine_default,
        "frame_default": int(frame_default),
        "include_md_config_fields": bool(include_md_config_fields),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary}, f, indent=2, ensure_ascii=False)
    return {"summary": summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold template CSV for real MD source manifest (target/path/engine/label/frame)."
    )
    parser.add_argument("--out-csv", type=str, default="runs/your_real_md_source_manifest.csv")
    parser.add_argument("--out-json", type=str, default="runs/your_real_md_source_manifest_summary.json")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--source-manifest", type=str, default="runs/external_ref_manifest_real_filled_2026-02-14.csv")
    parser.add_argument("--path-pattern", type=str, default="")
    parser.add_argument("--engine-default", type=str, default="")
    parser.add_argument("--frame-default", type=int, default=-1)
    parser.add_argument("--include-md-config-fields", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = scaffold_real_md_source_manifest(
        out_csv=str(args.out_csv),
        out_json=str(args.out_json),
        targets_spec=str(args.targets),
        source_manifest=(str(args.source_manifest) if args.source_manifest else None),
        path_pattern=str(args.path_pattern),
        engine_default=str(args.engine_default),
        frame_default=int(args.frame_default),
        include_md_config_fields=bool(args.include_md_config_fields),
        overwrite=bool(args.overwrite),
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
