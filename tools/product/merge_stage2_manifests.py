"""Merge trajectory and skip-inline stage2 manifests for stage3 scoring."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd


def merge_stage2_manifests(
    traj_manifest_csv: str,
    skip_manifest_csv: str,
    *,
    out_csv: str,
) -> dict[str, Any]:
    frames: list[pd.DataFrame] = []
    if str(traj_manifest_csv).strip() and os.path.exists(traj_manifest_csv):
        tdf = pd.read_csv(traj_manifest_csv)
        if not tdf.empty:
            frames.append(tdf)
    if str(skip_manifest_csv).strip() and os.path.exists(skip_manifest_csv):
        sdf = pd.read_csv(skip_manifest_csv)
        if not sdf.empty:
            frames.append(sdf)
    if not frames:
        raise FileNotFoundError("no stage2 manifests available to merge")
    merged = pd.concat(frames, axis=0, ignore_index=True)
    if "queue_id" in merged.columns:
        merged = merged.drop_duplicates(subset=["queue_id"], keep="first")
    out_path = str(out_csv)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    merged.to_csv(out_path, index=False)
    return {
        "merged_manifest_csv": out_path,
        "row_count": int(len(merged)),
        "traj_manifest_csv": str(traj_manifest_csv),
        "skip_manifest_csv": str(skip_manifest_csv),
    }
