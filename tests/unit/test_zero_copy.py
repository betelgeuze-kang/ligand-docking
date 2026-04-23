import numpy as np
import torch

from core.zero_copy import as_torch_tensor_zero_copy, from_dlpack, to_dlpack


def test_to_from_dlpack_roundtrip_cpu():
    src = torch.randn(3, 4, dtype=torch.float32)
    cap = to_dlpack(src)
    out = from_dlpack(cap)
    assert out.shape == src.shape
    assert out.dtype == src.dtype


def test_as_torch_tensor_zero_copy_numpy():
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)
    t = as_torch_tensor_zero_copy(arr)
    assert tuple(t.shape) == (3, 4)
    assert t.dtype == torch.float32
    arr[0, 0] = 99.0
    assert float(t[0, 0].item()) == 99.0


def test_as_torch_tensor_zero_copy_tensor_passthrough():
    src = torch.randn(2, 2)
    out = as_torch_tensor_zero_copy(src)
    assert out.data_ptr() == src.data_ptr()
