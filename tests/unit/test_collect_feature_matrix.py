import numpy as np
import pytest

pytest.importorskip("torch")
import torch

from tools.collect_feature_matrix import _compactness_and_cluster, _unwrap_polymer_coords


def test_unwrap_polymer_coords_removes_periodic_jumps():
    wrapped = np.array(
        [
            [99.918, 99.916, 2.082],
            [1.516, 1.971, 99.663],
            [3.067, 99.220, 97.919],
            [4.454, 98.332, 0.926],
            [6.074, 1.319, 1.671],
        ],
        dtype=np.float32,
    )
    out = _unwrap_polymer_coords(wrapped, np.array([100.0, 100.0, 100.0], dtype=np.float32))
    jumps = np.linalg.norm(np.diff(out, axis=0), axis=1)
    assert float(np.max(jumps)) < 12.0
    assert np.all(np.abs(np.mean(out, axis=0)) < 1e-5)


def test_unwrap_polymer_coords_passthrough_small_input():
    wrapped = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    out = _unwrap_polymer_coords(wrapped, np.array([100.0, 100.0, 100.0], dtype=np.float32))
    assert out.shape == wrapped.shape
    assert np.allclose(out, wrapped)


def test_compactness_uses_provider_backed_contact_graph():
    coords = torch.zeros(4, 3)
    compactness, cluster_max = _compactness_and_cluster(coords, cutoff=8.0, max_neighbors=3)
    assert compactness == pytest.approx(1.0)
    assert cluster_max == 4


def test_compactness_provider_overflow_blocks_claim_unsafe_graph():
    coords = torch.zeros(4, 3)
    with pytest.raises(ValueError, match="feature_matrix_contact_graph neighbor provider overflow"):
        _compactness_and_cluster(coords, cutoff=8.0, max_neighbors=2)
