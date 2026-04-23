from __future__ import annotations

from typing import Any, Optional

import numpy as np
import torch


def to_dlpack(tensor: torch.Tensor):
    if not isinstance(tensor, torch.Tensor):
        raise TypeError("to_dlpack expects torch.Tensor input")
    return torch.utils.dlpack.to_dlpack(tensor)


def from_dlpack(obj: Any, *, dtype: Optional[torch.dtype] = None, device: Optional[torch.device] = None) -> torch.Tensor:
    if hasattr(obj, "__dlpack__"):
        out = torch.utils.dlpack.from_dlpack(obj)
    else:
        out = torch.utils.dlpack.from_dlpack(obj)
    if dtype is not None and out.dtype != dtype:
        out = out.to(dtype=dtype)
    if device is not None and out.device != device:
        out = out.to(device=device)
    return out


def as_torch_tensor_zero_copy(
    obj: Any,
    *,
    dtype: Optional[torch.dtype] = None,
    device: Optional[torch.device] = None,
) -> torch.Tensor:
    if isinstance(obj, torch.Tensor):
        out = obj
    elif hasattr(obj, "__dlpack__"):
        out = torch.utils.dlpack.from_dlpack(obj)
    elif isinstance(obj, np.ndarray):
        out = torch.from_numpy(obj)
    else:
        raise TypeError(f"unsupported zero-copy input type: {type(obj).__name__}")

    if dtype is not None and out.dtype != dtype:
        out = out.to(dtype=dtype)
    if device is not None and out.device != device:
        out = out.to(device=device)
    return out
