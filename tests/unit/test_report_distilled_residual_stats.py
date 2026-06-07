import json

import numpy as np
import pandas as pd

from tools.product import report_distilled_residual_stats as rstats


def test_report_distilled_residual_stats_basic(tmp_path):
    p1 = tmp_path / "a.npz"
    p2 = tmp_path / "b.npz"
    np.savez_compressed(
        p1,
        residual_forces=np.ones((3, 10, 3), dtype=np.float32) * 0.1,
        residue_types=np.zeros((3, 10), dtype=np.int16),
    )
    np.savez_compressed(
        p2,
        residual_forces=np.ones((2, 20, 3), dtype=np.float32) * 0.01,
        residue_types=np.zeros((2, 20), dtype=np.int16),
    )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "split": "train", "output_npz": str(p1)},
            {"target": "Trp_Cage", "split": "val", "output_npz": str(p2)},
        ]
    ).to_csv(manifest, index=False)

    summary = rstats.build_stats(
        manifest_csv=str(manifest),
        out_csv=str(tmp_path / "stats.csv"),
        out_json=str(tmp_path / "stats.json"),
        max_samples_per_file=None,
    )
    assert summary["files"] == 2
    out_df = pd.read_csv(tmp_path / "stats.csv")
    assert len(out_df) == 2
    assert out_df["mean_abs_force"].max() > out_df["mean_abs_force"].min()
    saved = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
    assert saved["targets"] == 2
    assert saved["gate"]["pass"] is True


def test_report_distilled_residual_stats_gate_fail(tmp_path):
    p1 = tmp_path / "a.npz"
    np.savez_compressed(
        p1,
        residual_forces=np.zeros((3, 10, 3), dtype=np.float32),
        residue_types=np.zeros((3, 10), dtype=np.int16),
    )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "split": "train", "output_npz": str(p1)},
        ]
    ).to_csv(manifest, index=False)

    summary = rstats.build_stats(
        manifest_csv=str(manifest),
        out_csv=str(tmp_path / "stats.csv"),
        out_json=str(tmp_path / "stats.json"),
        min_global_mean_abs_force=1e-4,
        max_global_zero_like_ratio_1e6=0.99,
    )
    assert summary["gate"]["pass"] is False
    assert len(summary["gate"]["failed_reasons"]) >= 1
