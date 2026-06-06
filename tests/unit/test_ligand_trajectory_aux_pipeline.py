from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.product import build_ligand_trajectory_aux_dataset as build_aux
from tools.product import train_ligand_trajectory_aux_model as train_aux


def _write_npz(path: Path, offset: float) -> None:
    protein_ca = np.asarray([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]], dtype=np.float32)
    ligand_frames = np.asarray(
        [
            [[1.0 + offset, 0.0, 0.0]],
            [[1.5 + offset, 0.0, 0.0]],
            [[2.0 + offset, 0.0, 0.0]],
        ],
        dtype=np.float32,
    )
    frame_indices = np.asarray([0, 1, 2], dtype=np.int32)
    np.savez(path, protein_ca=protein_ca, ligand_frames=ligand_frames, frame_indices=frame_indices)


def test_build_and_train_aux_pipeline(tmp_path: Path) -> None:
    npz_a = tmp_path / "a.npz"
    npz_b = tmp_path / "b.npz"
    _write_npz(npz_a, 0.0)
    _write_npz(npz_b, 4.0)

    manifest = tmp_path / "stage2_manifest.csv"
    pd.DataFrame(
        [
            {
                "queue_id": "T__lig1",
                "target": "T",
                "ligand_id": "lig1",
                "status": "ok",
                "trajectory_npz": str(npz_a),
                "affinity_hint": 0.8,
                "k_attr": 0.2,
                "protein_repulse": 0.1,
                "sim_fps": 1000.0,
            },
            {
                "queue_id": "T__lig2",
                "target": "T",
                "ligand_id": "lig2",
                "status": "ok",
                "trajectory_npz": str(npz_b),
                "affinity_hint": 0.1,
                "k_attr": 0.1,
                "protein_repulse": 0.2,
                "sim_fps": 900.0,
            },
        ]
    ).to_csv(manifest, index=False)

    labels = tmp_path / "labels.csv"
    pd.DataFrame(
        [
            {"target": "T", "ligand_id": "lig1", "is_binder": 1},
            {"target": "T", "ligand_id": "lig2", "is_binder": 0},
        ]
    ).to_csv(labels, index=False)

    split = tmp_path / "split.csv"
    pd.DataFrame(
        [
            {"target": "T", "ligand_id": "lig1", "role": "fit"},
            {"target": "T", "ligand_id": "lig2", "role": "far_ood_eval"},
        ]
    ).to_csv(split, index=False)

    out_csv = tmp_path / "aux_rows.csv"
    out_npz = tmp_path / "aux_rows.npz"
    out_json = tmp_path / "aux_rows.json"
    out_md = tmp_path / "aux_rows.md"
    build_aux.build_dataset(
        build_aux.build_parser().parse_args(
            [
                "--stage2-manifest-csv",
                str(manifest),
                "--labels-csv",
                str(labels),
                "--split-csv",
                str(split),
                "--workers",
                "2",
                "--parallel-threshold",
                "1",
                "--chunksize",
                "1",
                "--out-csv",
                str(out_csv),
                "--out-npz",
                str(out_npz),
                "--out-json",
                str(out_json),
                "--out-md",
                str(out_md),
            ]
        )
    )
    payload = np.load(out_npz, allow_pickle=False)
    assert payload["feature_matrix"].shape[0] == 2
    assert "contact_fraction_6A" in payload["feature_names"].tolist()
    js = json.loads(out_json.read_text(encoding="utf-8"))
    assert js["rows_emitted"] == 2
    assert js["parallel_enabled"] is True

    ckpt = tmp_path / "aux_model.pt"
    train_json = tmp_path / "train.json"
    train_md = tmp_path / "train.md"
    summary = train_aux.train(
        train_aux.build_parser().parse_args(
            [
                "--input-npz",
                str(out_npz),
                "--epochs",
                "2",
                "--batch-size",
                "1",
                "--device",
                "cpu",
                "--out-checkpoint",
                str(ckpt),
                "--out-json",
                str(train_json),
                "--out-md",
                str(train_md),
            ]
        )
    )
    assert summary["ok"] is True
    assert ckpt.exists()

    ckpt_csv = tmp_path / "aux_model_csv.pt"
    train_csv_json = tmp_path / "train_csv.json"
    train_csv_md = tmp_path / "train_csv.md"
    summary_csv = train_aux.train(
        train_aux.build_parser().parse_args(
            [
                "--input-csv",
                str(out_csv),
                "--epochs",
                "2",
                "--batch-size",
                "1",
                "--device",
                "cpu",
                "--out-checkpoint",
                str(ckpt_csv),
                "--out-json",
                str(train_csv_json),
                "--out-md",
                str(train_csv_md),
            ]
        )
    )
    assert summary_csv["ok"] is True
    assert ckpt_csv.exists()
