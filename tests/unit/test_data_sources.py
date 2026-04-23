from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from train import data_sources as ds


def _write_min_h5(path: Path, n_samples: int = 2, n_res: int = 10):
    coords = np.zeros((n_samples, n_res, 3), dtype=np.float32)
    target_forces = np.ones((n_samples, n_res, 3), dtype=np.float32)
    residue_types = np.zeros((n_samples, n_res), dtype=np.int32)
    with h5py.File(path, "w") as f:
        f.create_dataset("coords", data=coords)
        f.create_dataset("target_forces", data=target_forces)
        f.create_dataset("residue_types", data=residue_types)


def test_resolve_hdf5_split_path_prefers_existing_configured(tmp_path):
    p = tmp_path / "train.h5"
    _write_min_h5(p)
    out = ds.resolve_hdf5_split_path(target="Chignolin", split="train", configured_path=str(p))
    assert out == str(p)


def test_build_distilled_split_dataset_from_manifest(tmp_path):
    npz_path = tmp_path / "chig_train.npz"
    np.savez_compressed(
        npz_path,
        coords=np.zeros((3, 10, 3), dtype=np.float16),
        residual_forces=np.ones((3, 10, 3), dtype=np.float16),
        residue_types=np.zeros((3, 10), dtype=np.int16),
        quality_score=np.asarray([0.1, 0.7, 0.9], dtype=np.float32),
    )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "split": "train",
                "output_npz": str(npz_path),
            }
        ]
    ).to_csv(manifest, index=False)

    dataset = ds.build_distilled_split_dataset(
        manifest_csv=str(manifest),
        target="Chignolin",
        split="train",
        min_quality=0.5,
        max_samples_per_shard=None,
    )
    assert len(dataset) == 2


def test_build_split_dataset_distilled_source(tmp_path):
    npz_path = tmp_path / "chig_val.npz"
    np.savez_compressed(
        npz_path,
        residual_forces=np.ones((2, 10, 3), dtype=np.float16),
        residue_types=np.zeros((2, 10), dtype=np.int16),
    )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "split": "val", "output_npz": str(npz_path)}]
    ).to_csv(manifest, index=False)
    dataset = ds.build_split_dataset(
        target="Chignolin",
        split="val",
        data_source="distilled",
        distilled_manifest=str(manifest),
    )
    assert len(dataset) == 2


def test_build_sampling_weights_from_manifest_and_quality(tmp_path):
    npz_path = tmp_path / "chig_train.npz"
    np.savez_compressed(
        npz_path,
        residual_forces=np.ones((3, 6, 3), dtype=np.float16),
        residue_types=np.zeros((3, 6), dtype=np.int16),
        quality_score=np.asarray([0.25, 1.0, 4.0], dtype=np.float32),
    )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "split": "train",
                "output_npz": str(npz_path),
                "sampling_weight": 3.0,
            }
        ]
    ).to_csv(manifest, index=False)

    dataset = ds.build_distilled_split_dataset(
        manifest_csv=str(manifest),
        target="Chignolin",
        split="train",
        quality_weight_alpha=0.5,
        min_sampling_weight=1e-6,
    )
    weights = ds.build_sampling_weights(dataset, min_sampling_weight=1e-6)
    # 3 * sqrt([0.25, 1, 4]) = [1.5, 3.0, 6.0]
    assert np.allclose(weights, np.asarray([1.5, 3.0, 6.0], dtype=np.float64), atol=1e-8)


def test_build_distilled_split_dataset_supports_custom_split_col_and_all_target(tmp_path):
    npz_a = tmp_path / "a_train.npz"
    npz_b = tmp_path / "b_train.npz"
    np.savez_compressed(
        npz_a,
        residual_forces=np.ones((2, 5, 3), dtype=np.float16),
        residue_types=np.zeros((2, 5), dtype=np.int16),
    )
    np.savez_compressed(
        npz_b,
        residual_forces=np.ones((3, 7, 3), dtype=np.float16),
        residue_types=np.zeros((3, 7), dtype=np.int16),
    )
    manifest = tmp_path / "manifest_custom_split.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "generalization_split": "train", "output_npz": str(npz_a)},
            {"target": "Ubiquitin_Mini", "generalization_split": "train", "output_npz": str(npz_b)},
        ]
    ).to_csv(manifest, index=False)

    dataset = ds.build_distilled_split_dataset(
        manifest_csv=str(manifest),
        target="all",
        split="train",
        split_col="generalization_split",
    )
    assert len(dataset) == 5
