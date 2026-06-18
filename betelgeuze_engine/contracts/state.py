from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch


@dataclass
class EngineState:
    coords: torch.Tensor
    atom_types: torch.Tensor
    residue_types: torch.Tensor | None = None
    box: torch.Tensor | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.coords.ndim != 3 or self.coords.shape[-1] != 3:
            raise ValueError("coords must have shape [B, N, 3]")
        if self.atom_types.ndim != 1:
            raise ValueError("atom_types must have shape [N]")
        if int(self.atom_types.shape[0]) != int(self.coords.shape[1]):
            raise ValueError("atom_types length must match coords N")
