#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence

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
        raise FileNotFoundError(f"source manifest not found: {path}")
    df = pd.read_csv(path)
    if "target" not in df.columns:
        raise ValueError(f"source manifest missing required column 'target': {path}")
    ordered: "OrderedDict[str, str]" = OrderedDict()
    for raw in df["target"].tolist():
        t = str(raw).strip()
        if not t:
            continue
        k = _normalize_target_key(t)
        if k not in ordered:
            ordered[k] = t
    targets = list(ordered.values())
    if len(targets) == 0:
        raise ValueError(f"source manifest has no valid targets: {path}")
    return targets


def scaffold_md_manifest(
    out_manifest: str,
    out_json: str,
    md_dir: str,
    targets_spec: str = "all",
    source_manifest: Optional[str] = None,
    engine: str = "openmm",
    frame: int = -1,
    label_suffix: str = "md_reference",
    file_suffix: str = "_md_ref.npy",
    strict_existing_paths: bool = False,
) -> Dict[str, object]:
    targets = _targets_from_manifest(source_manifest) if source_manifest else _parse_targets(targets_spec)
    if len(targets) == 0:
        raise ValueError("targets must not be empty")

    md_dir_abs = os.path.abspath(str(md_dir))
    os.makedirs(md_dir_abs, exist_ok=True)
    os.makedirs(os.path.dirname(out_manifest) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)

    rows: List[Dict[str, object]] = []
    missing_paths: List[str] = []
    for target in targets:
        stem = _slug_target(target)
        path = os.path.join(md_dir_abs, f"{stem}{file_suffix}")
        exists = os.path.exists(path)
        rows.append(
            {
                "target": target,
                "path": path,
                "engine": str(engine),
                "label": f"{target}_{label_suffix}",
                "frame": int(frame),
            }
        )
        if not exists:
            missing_paths.append(path)

    with open(out_manifest, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["target", "path", "engine", "label", "frame"])
        writer.writeheader()
        writer.writerows(rows)

    summary: Dict[str, object] = {
        "source_manifest": source_manifest,
        "out_manifest": out_manifest,
        "md_dir": md_dir_abs,
        "targets": targets,
        "target_count": int(len(targets)),
        "engine": str(engine),
        "frame": int(frame),
        "label_suffix": str(label_suffix),
        "file_suffix": str(file_suffix),
        "existing_paths": int(len(rows) - len(missing_paths)),
        "missing_paths": int(len(missing_paths)),
        "missing_path_examples": missing_paths[:5],
    }

    if strict_existing_paths and len(missing_paths) > 0:
        raise FileNotFoundError(
            f"strict_existing_paths failed: missing={len(missing_paths)} examples={missing_paths[:3]}"
        )

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate MD manifest template for 10-target baseline (or selected targets)."
    )
    parser.add_argument("--out-manifest", type=str, default="runs/external_ref_manifest_md_template.csv")
    parser.add_argument(
        "--out-json",
        type=str,
        default="runs/external_ref_manifest_md_template_summary.json",
    )
    parser.add_argument("--md-dir", type=str, default="runs/external_refs_md")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--source-manifest", type=str, default=None)
    parser.add_argument("--engine", type=str, default="openmm")
    parser.add_argument("--frame", type=int, default=-1)
    parser.add_argument("--label-suffix", type=str, default="md_reference")
    parser.add_argument("--file-suffix", type=str, default="_md_ref.npy")
    parser.add_argument("--strict-existing-paths", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = scaffold_md_manifest(
        out_manifest=str(args.out_manifest),
        out_json=str(args.out_json),
        md_dir=str(args.md_dir),
        targets_spec=str(args.targets),
        source_manifest=(str(args.source_manifest) if args.source_manifest else None),
        engine=str(args.engine),
        frame=int(args.frame),
        label_suffix=str(args.label_suffix),
        file_suffix=str(args.file_suffix),
        strict_existing_paths=bool(args.strict_existing_paths),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
