"""Batch-preserving runtime conditioning contracts.

Legacy code averaged condition tensors across a batch.  That silently mixed
samples with different temperatures or solvent conditions.  The canonical
runtime representation keeps one value per sample and allows scalar consumers
only when every sample carries the same value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import torch


class RuntimeConditioningError(ValueError):
    """Runtime conditions are malformed or unsafe for the requested consumer."""


@dataclass(frozen=True)
class RuntimeConditioningBatch:
    keys: tuple[str, ...]
    values: torch.Tensor

    def __post_init__(self) -> None:
        if self.values.ndim != 2:
            raise ValueError("conditioning values must have shape [B, P]")
        if self.values.shape[1] != len(self.keys):
            raise ValueError("conditioning keys must match the parameter dimension")
        if not self.values.is_floating_point():
            raise TypeError("conditioning values must use a floating dtype")
        if not bool(torch.isfinite(self.values).all().item()):
            raise RuntimeConditioningError("conditioning values must be finite")

    @property
    def batch_size(self) -> int:
        return int(self.values.shape[0])

    def as_mapping(self) -> dict[str, torch.Tensor]:
        return {
            key: self.values[:, index]
            for index, key in enumerate(self.keys)
        }

    def require_uniform_scalar_mapping(
        self,
        *,
        atol: float = 0.0,
        rtol: float = 0.0,
    ) -> dict[str, float]:
        """Return scalars only when every row agrees for every parameter."""

        out: dict[str, float] = {}
        for index, key in enumerate(self.keys):
            column = self.values[:, index]
            reference = column[0]
            if not bool(
                torch.allclose(
                    column,
                    reference.expand_as(column),
                    atol=float(atol),
                    rtol=float(rtol),
                )
            ):
                raise RuntimeConditioningError(
                    f"scalar consumer requires a uniform batch for parameter {key!r}"
                )
            out[key] = float(reference.detach().cpu().item())
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "keys": list(self.keys),
            "batch_size": self.batch_size,
            "parameter_count": len(self.keys),
            "shape": list(self.values.shape),
            "batch_preserved": True,
            "batch_mean_applied": False,
        }


def _coerce_parameter_column(
    raw: object,
    *,
    default: float,
    batch_size: int,
    dtype: torch.dtype,
    device: torch.device,
    key: str,
) -> torch.Tensor:
    if raw is None:
        return torch.full((batch_size,), float(default), dtype=dtype, device=device)
    if isinstance(raw, torch.Tensor):
        tensor = raw.to(dtype=dtype, device=device)
    elif isinstance(raw, (list, tuple)):
        tensor = torch.as_tensor(raw, dtype=dtype, device=device)
    else:
        try:
            scalar = float(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeConditioningError(
                f"runtime parameter {key!r} must be numeric"
            ) from exc
        tensor = torch.tensor(scalar, dtype=dtype, device=device)

    if tensor.numel() == 0:
        return torch.full((batch_size,), float(default), dtype=dtype, device=device)
    if tensor.ndim == 0 or tensor.numel() == 1:
        return tensor.reshape(1).expand(batch_size).clone()
    if tensor.ndim == 2 and tensor.shape[1] == 1:
        tensor = tensor[:, 0]
    if tensor.ndim != 1 or int(tensor.shape[0]) != int(batch_size):
        raise RuntimeConditioningError(
            f"runtime parameter {key!r} must be scalar, [B], or [B,1]"
        )
    if not bool(torch.isfinite(tensor).all().item()):
        raise RuntimeConditioningError(
            f"runtime parameter {key!r} contains non-finite values"
        )
    return tensor


def build_runtime_conditioning_batch(
    parameters: Mapping[str, object] | None,
    *,
    defaults: Mapping[str, float],
    keys: Sequence[str],
    batch_size: int,
    dtype: torch.dtype,
    device: torch.device | str,
) -> RuntimeConditioningBatch:
    """Build a stable `[B,P]` matrix in the declared key order."""

    if int(batch_size) < 1:
        raise ValueError("batch_size must be positive")
    mapping = parameters if isinstance(parameters, Mapping) else {}
    target_device = torch.device(device)
    ordered_keys = tuple(str(key) for key in keys)
    columns = [
        _coerce_parameter_column(
            mapping.get(key),
            default=float(defaults.get(key, 0.0)),
            batch_size=int(batch_size),
            dtype=dtype,
            device=target_device,
            key=key,
        )
        for key in ordered_keys
    ]
    values = torch.stack(columns, dim=-1)
    return RuntimeConditioningBatch(keys=ordered_keys, values=values)


__all__ = [
    "RuntimeConditioningBatch",
    "RuntimeConditioningError",
    "build_runtime_conditioning_batch",
]
