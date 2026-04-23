#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _coerce_coords_array(arr: np.ndarray, frame: int = -1) -> np.ndarray:
    a = np.asarray(arr)
    if a.ndim == 3:
        idx = int(frame)
        if idx < 0:
            idx = a.shape[0] - 1
        if idx >= a.shape[0]:
            raise ValueError(f"Requested frame index {idx} out of range for shape {a.shape}")
        a = a[idx]
    if a.ndim != 2:
        raise ValueError(f"Coordinate array must be [N,3] or [T,N,3], got shape {a.shape}")
    if a.shape[1] != 3 and a.shape[0] == 3:
        a = a.T
    if a.shape[1] != 3:
        raise ValueError(f"Coordinate array must have 3 columns, got shape {a.shape}")
    return np.asarray(a, dtype=np.float32)


def _load_coords_csv(path: str, frame: int = -1) -> np.ndarray:
    df = pd.read_csv(path)
    cols = set(df.columns)
    xyz_sets = [
        ("x", "y", "z"),
        ("coord_x", "coord_y", "coord_z"),
        ("X", "Y", "Z"),
    ]
    xyz = None
    for cset in xyz_sets:
        if set(cset).issubset(cols):
            xyz = cset
            break
    if xyz is None:
        raise ValueError(f"CSV reference {path} must include xyz columns (x/y/z or coord_x/y/z)")

    use_df = df
    if "frame" in use_df.columns:
        if int(frame) < 0:
            selected = int(use_df["frame"].max())
        else:
            selected = int(frame)
        use_df = use_df[use_df["frame"] == selected]
        if use_df.empty:
            raise ValueError(f"CSV reference {path} has no rows for frame={selected}")
    arr = use_df.loc[:, list(xyz)].to_numpy(dtype=np.float32)
    return _coerce_coords_array(arr, frame=-1)


def _load_coords(path: str, key: Optional[str] = None, frame: int = -1) -> np.ndarray:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npy":
        arr = np.load(path)
        return _coerce_coords_array(arr, frame=frame)
    if ext == ".npz":
        z = np.load(path)
        if key:
            if key not in z:
                raise KeyError(f"Key '{key}' not found in {path}. Available: {list(z.keys())}")
            arr = z[key]
        else:
            if len(z.files) == 0:
                raise ValueError(f"NPZ file {path} has no arrays.")
            arr = z[z.files[0]]
        return _coerce_coords_array(arr, frame=frame)
    if ext == ".csv":
        return _load_coords_csv(path=path, frame=frame)
    raise ValueError(f"Unsupported coordinate file extension: {ext} (path={path})")


def _resolve_policy_value(
    policy: str,
    template_value: Any,
    source_value: Any,
    override_value: Optional[str],
) -> str:
    p = str(policy).strip().lower()
    if p == "template":
        return str(template_value) if template_value is not None else ""
    if p == "source":
        return str(source_value) if source_value is not None else ""
    if p == "override":
        return str(override_value) if override_value is not None else ""
    raise ValueError(f"unknown policy: {policy}")


def materialize_md_references(
    template_manifest: str,
    source_manifest: str,
    out_manifest: str,
    out_json: str,
    engine_policy: str = "template",
    engine_override: Optional[str] = None,
    label_policy: str = "template",
    label_override: Optional[str] = None,
    strict_target_count: Optional[int] = None,
) -> Dict[str, object]:
    if not os.path.exists(template_manifest):
        raise FileNotFoundError(f"template manifest not found: {template_manifest}")
    if not os.path.exists(source_manifest):
        raise FileNotFoundError(f"source manifest not found: {source_manifest}")

    tdf = pd.read_csv(template_manifest)
    sdf = pd.read_csv(source_manifest)
    for col in ("target", "path"):
        if col not in tdf.columns:
            raise ValueError(f"template manifest missing required column: {col}")
        if col not in sdf.columns:
            raise ValueError(f"source manifest missing required column: {col}")
    if "engine" not in tdf.columns:
        tdf["engine"] = ""
    if "label" not in tdf.columns:
        tdf["label"] = ""
    if "frame" not in tdf.columns:
        tdf["frame"] = -1

    src_by_target: Dict[str, Dict[str, Any]] = {}
    for row in sdf.to_dict(orient="records"):
        t = str(row.get("target", "")).strip()
        if not t:
            continue
        src_by_target[_normalize_target_key(t)] = row

    rows: List[Dict[str, Any]] = []
    missing_targets: List[str] = []
    failures: List[Dict[str, str]] = []
    created_files: List[str] = []

    for row in tdf.to_dict(orient="records"):
        target = str(row.get("target", "")).strip()
        dst_path = str(row.get("path", "")).strip()
        if not target or not dst_path:
            failures.append({"target": target, "reason": "missing_target_or_path_in_template"})
            continue
        src = src_by_target.get(_normalize_target_key(target))
        if src is None:
            missing_targets.append(target)
            failures.append({"target": target, "reason": "missing_source_target"})
            continue

        src_path = str(src.get("path", "")).strip()
        if not src_path or not os.path.exists(src_path):
            failures.append({"target": target, "reason": "missing_source_file"})
            continue

        src_key = src.get("key", None)
        src_frame_raw = src.get("frame", -1)
        try:
            src_frame = int(src_frame_raw) if src_frame_raw is not None else -1
        except Exception:
            src_frame = -1
        try:
            coords = _load_coords(path=src_path, key=(str(src_key) if src_key else None), frame=src_frame)
            os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
            np.save(dst_path, coords)
            created_files.append(dst_path)
        except Exception as exc:
            failures.append({"target": target, "reason": f"materialize_failed:{type(exc).__name__}"})
            continue

        engine_out = _resolve_policy_value(
            policy=engine_policy,
            template_value=row.get("engine"),
            source_value=src.get("engine"),
            override_value=engine_override,
        )
        label_out = _resolve_policy_value(
            policy=label_policy,
            template_value=row.get("label"),
            source_value=src.get("label"),
            override_value=label_override,
        )
        rows.append(
            {
                "target": target,
                "path": dst_path,
                "engine": engine_out,
                "label": label_out,
                "frame": -1,
                "source_path": src_path,
                "source_engine": str(src.get("engine", "")),
                "source_label": str(src.get("label", "")),
            }
        )

    os.makedirs(os.path.dirname(out_manifest) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_manifest, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "target",
                "path",
                "engine",
                "label",
                "frame",
                "source_path",
                "source_engine",
                "source_label",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    out_targets = sorted({str(r["target"]) for r in rows})
    summary: Dict[str, object] = {
        "template_manifest": template_manifest,
        "source_manifest": source_manifest,
        "out_manifest": out_manifest,
        "rows_written": int(len(rows)),
        "targets_written": int(len(out_targets)),
        "missing_targets": sorted(set(missing_targets)),
        "failure_count": int(len(failures)),
        "failures": failures[:20],
        "created_files": int(len(created_files)),
        "engine_policy": engine_policy,
        "label_policy": label_policy,
    }

    if strict_target_count is not None and int(strict_target_count) > 0:
        if len(out_targets) != int(strict_target_count):
            raise ValueError(
                f"strict_target_count failed: expected={int(strict_target_count)} got={len(out_targets)}"
            )

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize canonical MD reference files from a source manifest into template paths."
    )
    parser.add_argument("--template-manifest", type=str, default="runs/external_ref_manifest_md_template.csv")
    parser.add_argument("--source-manifest", type=str, default="runs/external_ref_manifest_real_filled_2026-02-14.csv")
    parser.add_argument("--out-manifest", type=str, default="runs/external_ref_manifest_md_materialized.csv")
    parser.add_argument("--out-json", type=str, default="runs/external_ref_manifest_md_materialized_summary.json")
    parser.add_argument("--engine-policy", type=str, choices=["template", "source", "override"], default="template")
    parser.add_argument("--engine-override", type=str, default=None)
    parser.add_argument("--label-policy", type=str, choices=["template", "source", "override"], default="template")
    parser.add_argument("--label-override", type=str, default=None)
    parser.add_argument("--strict-target-count", type=int, default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = materialize_md_references(
        template_manifest=str(args.template_manifest),
        source_manifest=str(args.source_manifest),
        out_manifest=str(args.out_manifest),
        out_json=str(args.out_json),
        engine_policy=str(args.engine_policy),
        engine_override=(str(args.engine_override) if args.engine_override is not None else None),
        label_policy=str(args.label_policy),
        label_override=(str(args.label_override) if args.label_override is not None else None),
        strict_target_count=args.strict_target_count,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
