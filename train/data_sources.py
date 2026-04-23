from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
from torch.utils.data import ConcatDataset, Dataset

from train.dataset import AIRouterHDF5Dataset
from train.distilled_dataset import DistilledResidualNPZDataset


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def resolve_hdf5_split_path(target: Optional[str], split: str, configured_path: Optional[str]) -> str:
    """
    Resolve existing HDF5 split path.
    Priority:
    1) configured_path if exists
    2) target-specific generated path (data/{target}_airouter_{split}_data.h5) if exists
    3) configured_path (for explicit error visibility)
    4) target-specific path
    """
    target_path = f"data/{target.lower()}_airouter_{split}_data.h5" if target else None
    if configured_path and os.path.exists(configured_path):
        return configured_path
    if target_path and os.path.exists(target_path):
        return target_path
    if configured_path:
        return configured_path
    if target_path:
        return target_path
    return f"data/{split}.h5"


def build_distilled_split_dataset(
    manifest_csv: str,
    target: str,
    split: str,
    split_col: str = "split",
    min_quality: Optional[float] = None,
    max_samples_per_shard: Optional[int] = None,
    mmap_mode: str = "r",
    sample_weight_col: str = "sampling_weight",
    default_shard_weight: float = 1.0,
    quality_weight_alpha: float = 0.0,
    min_sampling_weight: float = 1e-6,
) -> Dataset:
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"distilled manifest not found: {manifest_csv}")
    df = pd.read_csv(manifest_csv)
    split_col_i = str(split_col).strip() or "split"
    required = {"target", split_col_i, "output_npz"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"distilled manifest missing required columns: {required}")
    if "error" in df.columns:
        df = df[df["error"].isna()]

    split_mask = df[split_col_i].astype(str).str.lower() == str(split).lower()
    target_i = str(target).strip()
    if target_i.lower() in ("all", "*", "any"):
        target_mask = pd.Series([True] * len(df), index=df.index)
    else:
        tnorm = _normalize_target_key(target_i)
        target_mask = df["target"].astype(str).map(_normalize_target_key) == tnorm
    sub = df[target_mask & split_mask].copy()
    if sub.empty:
        raise FileNotFoundError(
            f"no distilled shard found for target={target} split={split} split_col={split_col_i} in manifest={manifest_csv}"
        )

    shards = []
    for _, row in sub.iterrows():
        p = str(row["output_npz"])
        if not os.path.exists(p):
            raise FileNotFoundError(f"distilled shard not found: {p}")
        shard_weight_raw = row.get(sample_weight_col, default_shard_weight)
        try:
            shard_weight = float(shard_weight_raw)
        except Exception:
            shard_weight = float(default_shard_weight)
        shard_weight = max(shard_weight, float(min_sampling_weight))
        shards.append(
            DistilledResidualNPZDataset(
                npz_path=p,
                mmap_mode=mmap_mode,
                min_quality=min_quality,
                max_samples=max_samples_per_shard,
                shard_weight=shard_weight,
                quality_weight_alpha=float(quality_weight_alpha),
                min_sampling_weight=float(min_sampling_weight),
            )
        )
    if len(shards) == 1:
        return shards[0]
    return ConcatDataset(shards)


def build_split_dataset(
    target: str,
    split: str,
    data_source: str,
    configured_hdf5_path: Optional[str] = None,
    distilled_manifest: str = "runs/distilled_residual_manifest.csv",
    distilled_split_col: str = "split",
    distilled_min_quality: Optional[float] = None,
    distilled_max_samples_per_shard: Optional[int] = None,
    distilled_sample_weight_col: str = "sampling_weight",
    distilled_default_shard_weight: float = 1.0,
    distilled_quality_weight_alpha: float = 0.0,
    distilled_min_sampling_weight: float = 1e-6,
) -> Dataset:
    source = str(data_source).strip().lower()
    if source == "hdf5":
        path = resolve_hdf5_split_path(target=target, split=split, configured_path=configured_hdf5_path)
        return AIRouterHDF5Dataset(path)
    if source == "distilled":
        return build_distilled_split_dataset(
            manifest_csv=distilled_manifest,
            target=target,
            split=split,
            split_col=distilled_split_col,
            min_quality=distilled_min_quality,
            max_samples_per_shard=distilled_max_samples_per_shard,
            sample_weight_col=distilled_sample_weight_col,
            default_shard_weight=distilled_default_shard_weight,
            quality_weight_alpha=distilled_quality_weight_alpha,
            min_sampling_weight=distilled_min_sampling_weight,
        )
    raise ValueError(f"unsupported data_source: {data_source}")


def build_sampling_weights(
    dataset: Dataset,
    min_sampling_weight: float = 1e-6,
) -> np.ndarray:
    if hasattr(dataset, "get_sampling_weights"):
        arr = np.asarray(dataset.get_sampling_weights(), dtype=np.float64)
        return np.clip(arr, a_min=float(min_sampling_weight), a_max=None)
    if isinstance(dataset, ConcatDataset):
        chunks = [build_sampling_weights(ds, min_sampling_weight=min_sampling_weight) for ds in dataset.datasets]
        if not chunks:
            return np.asarray([], dtype=np.float64)
        arr = np.concatenate(chunks, axis=0)
        return np.clip(arr, a_min=float(min_sampling_weight), a_max=None)
    return np.full((len(dataset),), fill_value=max(float(min_sampling_weight), 1.0), dtype=np.float64)
