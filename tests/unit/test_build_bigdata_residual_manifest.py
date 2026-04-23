from pathlib import Path

import numpy as np
import pandas as pd

from tools import build_bigdata_residual_manifest as big


def _touch_npz(path: Path) -> None:
    np.savez_compressed(
        path,
        residual_forces=np.zeros((1, 4, 3), dtype=np.float32),
        residue_types=np.zeros((1, 4), dtype=np.int16),
    )


def test_build_bigdata_residual_manifest_weights_and_dedupe(tmp_path):
    shared = tmp_path / "shared.npz"
    hard_only = tmp_path / "hard_only.npz"
    _touch_npz(shared)
    _touch_npz(hard_only)

    base_manifest = tmp_path / "base.csv"
    hard_manifest = tmp_path / "hard.csv"
    target_weights = tmp_path / "target_weights.csv"
    out_manifest = tmp_path / "out.csv"
    out_summary = tmp_path / "out.json"

    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "split": "train",
                "output_npz": str(shared),
            }
        ]
    ).to_csv(base_manifest, index=False)
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "split": "train",
                "output_npz": str(shared),
            },
            {
                "target": "Ubiquitin_Mini",
                "split": "train",
                "output_npz": str(hard_only),
            },
        ]
    ).to_csv(hard_manifest, index=False)
    pd.DataFrame(
        [
            {"target": "Ubiquitin_Mini", "multiplier": 2.0},
        ]
    ).to_csv(target_weights, index=False)

    summary = big.build_bigdata_residual_manifest(
        targets="Chignolin,Ubiquitin_Mini",
        base_manifest_csv=str(base_manifest),
        hardcase_manifest_csv=str(hard_manifest),
        out_manifest_csv=str(out_manifest),
        out_summary_json=str(out_summary),
        base_weight=1.0,
        hardcase_weight=3.0,
        target_weights_csv=str(target_weights),
        min_sampling_weight=1e-6,
    )
    assert summary["rows_total"] == 2

    out_df = pd.read_csv(out_manifest)
    # duplicate "shared.npz" should keep hardcase row (weight 3.0 > 1.0)
    shared_row = out_df[out_df["output_npz"] == str(shared)].iloc[0]
    assert shared_row["source_tag"] == "hardcase"
    assert float(shared_row["sampling_weight"]) == 3.0

    hard_row = out_df[out_df["output_npz"] == str(hard_only)].iloc[0]
    # hardcase base 3.0 * target multiplier 2.0
    assert float(hard_row["sampling_weight"]) == 6.0


def test_build_bigdata_residual_manifest_bead_consistency_max_atoms(tmp_path):
    low = tmp_path / "low.npz"
    high = tmp_path / "high.npz"
    _touch_npz(low)
    _touch_npz(high)

    base_manifest = tmp_path / "base2.csv"
    hard_manifest = tmp_path / "hard2.csv"
    out_manifest = tmp_path / "out2.csv"
    out_summary = tmp_path / "out2.json"

    pd.DataFrame(
        [
            {"target": "Crambin", "split": "train", "output_npz": str(low), "n_atoms": 46},
        ]
    ).to_csv(base_manifest, index=False)
    pd.DataFrame(
        [
            {"target": "Crambin", "split": "train", "output_npz": str(high), "n_atoms": 92},
        ]
    ).to_csv(hard_manifest, index=False)

    summary = big.build_bigdata_residual_manifest(
        targets="Crambin",
        base_manifest_csv=str(base_manifest),
        hardcase_manifest_csv=str(hard_manifest),
        out_manifest_csv=str(out_manifest),
        out_summary_json=str(out_summary),
        bead_consistency_policy="max_atoms",
    )
    assert summary["bead_consistency"]["rows_removed"] == 1
    out_df = pd.read_csv(out_manifest)
    assert len(out_df) == 1
    assert int(out_df.iloc[0]["n_atoms"]) == 92


def test_build_bigdata_residual_manifest_applies_length_weight(tmp_path):
    a = tmp_path / "a.npz"
    b = tmp_path / "b.npz"
    _touch_npz(a)
    _touch_npz(b)

    base_manifest = tmp_path / "base_len.csv"
    hard_manifest = tmp_path / "hard_len.csv"
    out_manifest = tmp_path / "out_len.csv"
    out_summary = tmp_path / "out_len.json"

    pd.DataFrame(
        [
            {"target": "Chignolin", "split": "train", "output_npz": str(a), "n_res_expected": 10},
        ]
    ).to_csv(base_manifest, index=False)
    pd.DataFrame(
        [
            {"target": "Ubiquitin_Mini", "split": "train", "output_npz": str(b), "n_res_expected": 76},
        ]
    ).to_csv(hard_manifest, index=False)

    summary = big.build_bigdata_residual_manifest(
        targets="Chignolin,Ubiquitin_Mini",
        base_manifest_csv=str(base_manifest),
        hardcase_manifest_csv=str(hard_manifest),
        out_manifest_csv=str(out_manifest),
        out_summary_json=str(out_summary),
        base_weight=1.0,
        hardcase_weight=1.0,
        length_weight_beta=1.0,
        length_reference_n_res=10.0,
        bead_consistency_policy="none",
    )
    assert summary["rows_total"] == 2

    out_df = pd.read_csv(out_manifest)
    row_small = out_df[out_df["target"] == "Chignolin"].iloc[0]
    row_large = out_df[out_df["target"] == "Ubiquitin_Mini"].iloc[0]
    assert abs(float(row_small["sampling_weight"]) - 1.0) < 1e-8
    assert abs(float(row_large["sampling_weight"]) - 7.6) < 1e-8
    assert abs(float(row_large["length_weight_multiplier"]) - 7.6) < 1e-8
