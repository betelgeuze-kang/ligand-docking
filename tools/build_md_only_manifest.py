#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Dict, Optional, Sequence

import pandas as pd


def _engine_matches(engine: str, pattern: str) -> bool:
    if engine is None:
        return False
    return re.search(pattern, str(engine), flags=re.IGNORECASE) is not None


def build_md_only_manifest(
    input_manifest: str,
    out_manifest: str,
    out_json: str,
    md_engine_regex: str,
    require_existing_paths: bool,
    strict_target_count: Optional[int],
) -> Dict[str, object]:
    if not os.path.exists(input_manifest):
        raise FileNotFoundError(f"input manifest not found: {input_manifest}")

    df = pd.read_csv(input_manifest)
    if "target" not in df.columns or "path" not in df.columns:
        raise ValueError("input manifest must include columns: target, path")
    if "engine" not in df.columns:
        df["engine"] = ""

    keep = []
    for _, row in df.iterrows():
        engine = str(row.get("engine", ""))
        path = str(row.get("path", ""))
        if not _engine_matches(engine, md_engine_regex):
            continue
        if require_existing_paths and (not os.path.exists(path)):
            continue
        keep.append(row.to_dict())

    out_df = pd.DataFrame(keep, columns=list(df.columns))
    os.makedirs(os.path.dirname(out_manifest) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    out_df.to_csv(out_manifest, index=False)

    summary: Dict[str, object] = {
        "input_manifest": input_manifest,
        "out_manifest": out_manifest,
        "total_rows_input": int(len(df)),
        "total_rows_output": int(len(out_df)),
        "md_engine_regex": md_engine_regex,
        "require_existing_paths": bool(require_existing_paths),
        "engine_counts_input": {
            str(k): int(v)
            for k, v in df["engine"].astype(str).value_counts(dropna=False).to_dict().items()
        },
        "engine_counts_output": (
            {
                str(k): int(v)
                for k, v in out_df["engine"].astype(str).value_counts(dropna=False).to_dict().items()
            }
            if (not out_df.empty and "engine" in out_df.columns)
            else {}
        ),
        "targets_output": (
            sorted(set(str(x) for x in out_df["target"].astype(str).tolist()))
            if (not out_df.empty and "target" in out_df.columns)
            else []
        ),
    }

    if strict_target_count is not None and int(strict_target_count) > 0:
        out_targets = set(summary["targets_output"])  # type: ignore[arg-type]
        if len(out_targets) != int(strict_target_count):
            raise ValueError(
                f"strict_target_count failed: expected={int(strict_target_count)} "
                f"got={len(out_targets)}"
            )

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Filter external reference manifest to MD-engine-only rows."
    )
    parser.add_argument("--input-manifest", type=str, default="runs/external_ref_manifest_real_template.csv")
    parser.add_argument("--out-manifest", type=str, default="runs/external_ref_manifest_md_only.csv")
    parser.add_argument("--out-json", type=str, default="runs/external_ref_manifest_md_only_summary.json")
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--require-existing-paths", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--strict-target-count", type=int, default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_md_only_manifest(
        input_manifest=str(args.input_manifest),
        out_manifest=str(args.out_manifest),
        out_json=str(args.out_json),
        md_engine_regex=str(args.md_engine_regex),
        require_existing_paths=bool(args.require_existing_paths),
        strict_target_count=args.strict_target_count,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
