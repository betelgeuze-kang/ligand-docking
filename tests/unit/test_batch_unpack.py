import pytest
import torch

from train.evaluator import _unpack_batch as unpack_eval
from train.trainer import _unpack_batch as unpack_train


def _sample_tensors():
    coords = torch.zeros((2, 10, 3), dtype=torch.float32)
    forces = torch.ones((2, 10, 3), dtype=torch.float32)
    types = torch.zeros((2, 10), dtype=torch.int64)
    quality = torch.ones((2,), dtype=torch.float32)
    return coords, forces, types, quality


def test_unpack_batch_three_items():
    coords, forces, types, _q = _sample_tensors()
    c, f, t, q, sim = unpack_train((coords, forces, types))
    assert q is None
    assert sim is None
    assert c.shape == coords.shape
    c2, f2, t2, q2, sim2 = unpack_eval((coords, forces, types))
    assert q2 is None
    assert sim2 is None
    assert f2.shape == forces.shape


def test_unpack_batch_four_items():
    coords, forces, types, quality = _sample_tensors()
    c, f, t, q, sim = unpack_train((coords, forces, types, quality))
    assert q.shape == quality.shape
    assert sim is None
    c2, f2, t2, q2, sim2 = unpack_eval((coords, forces, types, quality))
    assert q2.shape == quality.shape
    assert sim2 is None


def test_unpack_batch_five_items():
    coords, forces, types, quality = _sample_tensors()
    sim_params = {"temp": torch.ones((2,), dtype=torch.float32) * 300.0}
    c, f, t, q, sim = unpack_train((coords, forces, types, quality, sim_params))
    assert q.shape == quality.shape
    assert isinstance(sim, dict)
    c2, f2, t2, q2, sim2 = unpack_eval((coords, forces, types, quality, sim_params))
    assert q2.shape == quality.shape
    assert isinstance(sim2, dict)


def test_unpack_batch_invalid_len():
    coords, forces, types, _q = _sample_tensors()
    with pytest.raises(ValueError):
        unpack_train((coords, forces))
    with pytest.raises(ValueError):
        unpack_eval((coords, forces, types, torch.ones(2), {"temp": torch.ones(2)}, torch.ones(2)))
