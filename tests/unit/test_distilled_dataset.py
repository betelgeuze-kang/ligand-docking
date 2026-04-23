import numpy as np

from train.distilled_dataset import DistilledResidualNPZDataset


def test_distilled_dataset_with_coords(tmp_path):
    p = tmp_path / "d.npz"
    np.savez_compressed(
        p,
        coords=np.zeros((3, 10, 3), dtype=np.float16),
        residual_forces=np.ones((3, 10, 3), dtype=np.float16),
        residue_types=np.zeros((3, 10), dtype=np.int16),
        quality_score=np.asarray([0.2, 0.5, 0.9], dtype=np.float32),
        sample_index=np.asarray([1, 2, 3], dtype=np.int32),
    )
    ds = DistilledResidualNPZDataset(str(p))
    assert len(ds) == 3
    coords, residual, types, q = ds[0]
    assert tuple(coords.shape) == (10, 3)
    assert tuple(residual.shape) == (10, 3)
    assert tuple(types.shape) == (10,)
    assert abs(float(q) - 0.2) < 1e-6
    ds.close()


def test_distilled_dataset_without_coords(tmp_path):
    p = tmp_path / "d2.npz"
    np.savez_compressed(
        p,
        residual_forces=np.ones((2, 5, 3), dtype=np.float16),
        residue_types=np.zeros((2, 5), dtype=np.int16),
    )
    ds = DistilledResidualNPZDataset(str(p))
    coords, residual, types, q = ds[1]
    assert tuple(coords.shape) == (5, 3)
    assert float(q) == 1.0
    ds.close()


def test_distilled_dataset_sampling_weights_with_quality(tmp_path):
    p = tmp_path / "d3.npz"
    np.savez_compressed(
        p,
        residual_forces=np.ones((3, 4, 3), dtype=np.float16),
        residue_types=np.zeros((3, 4), dtype=np.int16),
        quality_score=np.asarray([0.25, 1.0, 4.0], dtype=np.float32),
    )
    ds = DistilledResidualNPZDataset(
        str(p),
        shard_weight=2.0,
        quality_weight_alpha=0.5,
        min_sampling_weight=1e-6,
    )
    w = ds.get_sampling_weights()
    # 2 * sqrt([0.25, 1, 4]) = [1, 2, 4]
    assert np.allclose(w, np.asarray([1.0, 2.0, 4.0], dtype=np.float64), atol=1e-8)
    ds.close()


def test_distilled_dataset_optional_scalar_fields(tmp_path):
    p = tmp_path / "d4.npz"
    np.savez_compressed(
        p,
        coords=np.zeros((2, 6, 3), dtype=np.float32),
        residual_forces=np.ones((2, 6, 3), dtype=np.float32),
        residue_types=np.zeros((2, 6), dtype=np.int16),
        ionic_strength=np.asarray([0.12, 0.20], dtype=np.float32),
        energy=np.asarray([-10.0, -9.5], dtype=np.float32),
    )
    ds = DistilledResidualNPZDataset(str(p))
    sample = ds[1]
    assert len(sample) == 5
    coords, residual, types, q, sim_params = sample
    assert tuple(coords.shape) == (6, 3)
    assert tuple(residual.shape) == (6, 3)
    assert tuple(types.shape) == (6,)
    assert float(q) == 1.0
    assert abs(float(sim_params["ionic_strength"]) - 0.20) < 1e-6
    assert abs(float(sim_params["energy"]) + 9.5) < 1e-6
    ds.close()


def test_distilled_dataset_scalar_field_roles(tmp_path):
    p = tmp_path / "d5.npz"
    np.savez_compressed(
        p,
        coords=np.zeros((2, 4, 3), dtype=np.float32),
        residual_forces=np.ones((2, 4, 3), dtype=np.float32),
        residue_types=np.zeros((2, 4), dtype=np.int16),
        temp=np.asarray([300.0, 305.0], dtype=np.float32),
        ionic_strength=np.asarray([0.1, 0.2], dtype=np.float32),
        is_llps=np.asarray([1.0, 0.0], dtype=np.float32),
        rmsd=np.asarray([1.2, 0.9], dtype=np.float32),
        violations=np.asarray([0.0, 1.0], dtype=np.float32),
    )
    ds = DistilledResidualNPZDataset(str(p))
    roles = ds.scalar_field_roles
    assert "temp" in roles["conditioning"]
    assert "ionic_strength" in roles["conditioning"]
    assert "is_llps" in roles["targets"]
    assert "rmsd" in roles["targets"]
    assert "violations" in roles["quality"]
    ds.close()
