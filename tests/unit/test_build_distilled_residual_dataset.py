import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from tools import build_distilled_residual_dataset as distill


def _write_h5(path: Path, target: str, residual_mode: bool = False, two_bead: bool = False) -> None:
    n_res = 10
    n_atoms = n_res * 2 if two_bead else n_res
    coords = np.zeros((4, n_atoms, 3), dtype=np.float32)
    physics = np.ones((4, n_atoms, 3), dtype=np.float32) * 2.0
    target_forces = np.ones((4, n_atoms, 3), dtype=np.float32) * 5.0
    residue_types = np.arange(n_res, dtype=np.int32)
    residue_types = np.tile(residue_types[None, :], (4, 1))
    quality = np.asarray([0.1, 0.4, 0.8, 0.9], dtype=np.float32)

    with h5py.File(path, "w") as f:
        f.create_dataset("coords", data=coords)
        f.create_dataset("physics_forces", data=physics)
        f.create_dataset("target_forces", data=target_forces)
        f.create_dataset("residue_types", data=residue_types)
        f.create_dataset("quality_score", data=quality)
        f.attrs["target"] = target
        f.attrs["residual_mode"] = bool(residual_mode)


def test_build_distilled_residual_dataset_basic(tmp_path):
    src = tmp_path / "chignolin_airouter_train_data.h5"
    _write_h5(src, target="Chignolin", residual_mode=False, two_bead=False)

    summary = distill.build_distilled_residual_dataset(
        input_glob=str(tmp_path / "*.h5"),
        targets="Chignolin",
        out_dir=str(tmp_path / "out"),
        out_manifest_csv=str(tmp_path / "manifest.csv"),
        out_summary_json=str(tmp_path / "summary.json"),
        float_dtype="float16",
        keep_coords=True,
        max_samples_per_file=2,
        min_quality=None,
        skip_if_exists=False,
    )
    assert summary["files_processed"] == 1
    manifest = pd.read_csv(tmp_path / "manifest.csv")
    assert int(manifest.loc[0, "samples_saved"]) == 2
    out_npz = Path(str(manifest.loc[0, "output_npz"]))
    payload = np.load(out_npz)
    assert payload["residual_forces"].dtype == np.float16
    # residual = target(5) - physics(2) = 3
    assert float(payload["residual_forces"][0, 0, 0]) == 3.0


def test_build_distilled_residual_dataset_quality_filter_and_two_bead(tmp_path):
    src = tmp_path / "chignolin_airouter_val_data.h5"
    _write_h5(src, target="Chignolin", residual_mode=False, two_bead=True)

    summary = distill.build_distilled_residual_dataset(
        input_glob=str(tmp_path / "*.h5"),
        targets="all",
        out_dir=str(tmp_path / "out"),
        out_manifest_csv=str(tmp_path / "manifest.csv"),
        out_summary_json=str(tmp_path / "summary.json"),
        float_dtype="float32",
        keep_coords=False,
        max_samples_per_file=None,
        min_quality=0.5,
        skip_if_exists=False,
    )
    assert summary["files_failed"] == 0
    manifest = pd.read_csv(tmp_path / "manifest.csv")
    assert int(manifest.loc[0, "samples_saved"]) == 2
    out_npz = Path(str(manifest.loc[0, "output_npz"]))
    payload = np.load(out_npz)
    # coords dropped
    assert "coords" not in payload
    # residue_types expanded to 2-bead atom count
    assert payload["residue_types"].shape[1] == 20


def test_build_distilled_residual_dataset_residual_mode_direct(tmp_path):
    src = tmp_path / "chignolin_airouter_test_data.h5"
    _write_h5(src, target="Chignolin", residual_mode=True, two_bead=False)

    distill.build_distilled_residual_dataset(
        input_glob=str(tmp_path / "*.h5"),
        targets="Chignolin",
        out_dir=str(tmp_path / "out"),
        out_manifest_csv=str(tmp_path / "manifest.csv"),
        out_summary_json=str(tmp_path / "summary.json"),
        float_dtype="float32",
        keep_coords=True,
        max_samples_per_file=1,
        min_quality=None,
        skip_if_exists=False,
    )
    manifest = pd.read_csv(tmp_path / "manifest.csv")
    out_npz = Path(str(manifest.loc[0, "output_npz"]))
    payload = np.load(out_npz)
    # residual_mode=True -> residual_forces == target_forces == 5
    assert float(payload["residual_forces"][0, 0, 0]) == 5.0
    j = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert j["files_processed"] == 1


def test_build_distilled_residual_dataset_repair_zero_residual(tmp_path, monkeypatch):
    src = tmp_path / "chignolin_airouter_train_data.h5"
    _write_h5(src, target="Chignolin", residual_mode=False, two_bead=False)
    # Make residual exactly zero: target == physics
    with h5py.File(src, "a") as f:
        physics = np.asarray(f["physics_forces"][:], dtype=np.float32)
        del f["target_forces"]
        f.create_dataset("target_forces", data=physics)

    class _FakeRepairer:
        def __init__(self, *args, **kwargs):
            pass

        def compute(self, coords, physics_forces):
            return np.ones_like(physics_forces, dtype=np.float32) * 0.25

    monkeypatch.setattr(distill, "_ReferenceResidualRepairer", _FakeRepairer)

    summary = distill.build_distilled_residual_dataset(
        input_glob=str(tmp_path / "*.h5"),
        targets="Chignolin",
        out_dir=str(tmp_path / "out"),
        out_manifest_csv=str(tmp_path / "manifest.csv"),
        out_summary_json=str(tmp_path / "summary.json"),
        float_dtype="float32",
        keep_coords=True,
        max_samples_per_file=2,
        min_quality=None,
        skip_if_exists=False,
        repair_zero_residual=True,
        zero_residual_atol=1e-8,
        repair_device="cpu",
        repair_reference_cutoff=14.0,
        repair_reference_max_neighbors=160,
    )
    assert summary["total_zero_like_before_repair"] == 2
    assert summary["total_repaired_nonzero_samples"] == 2
    assert summary["total_zero_like_after_repair"] == 0
    manifest = pd.read_csv(tmp_path / "manifest.csv")
    assert int(manifest.loc[0, "zero_like_before_repair"]) == 2
    assert int(manifest.loc[0, "repaired_nonzero_samples"]) == 2

    out_npz = Path(str(manifest.loc[0, "output_npz"]))
    payload = np.load(out_npz)
    assert float(payload["residual_forces"][0, 0, 0]) == 0.25
