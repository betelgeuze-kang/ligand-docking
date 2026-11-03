"""Opt-in copied coordinate observations, excluded from numerical contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable, Mapping

import torch

from .identity import coordinate_fingerprint
from .proposals import DockingProposal

DevelopmentObserver = Callable[[str, str, Mapping[str, object]], None]


def emit_coordinate_snapshot(
    observer: DevelopmentObserver | None,
    stage: str,
    proposal: DockingProposal,
    *,
    coordinates: torch.Tensor | None = None,
    **details: object,
) -> None:
    """Copy all tensor values before calling a sink; never expose mutable state."""
    if observer is None:
        return
    values = proposal.coordinates if coordinates is None else coordinates
    payload = {
        "shape": [int(size) for size in values.shape],
        "values_hex": [
            float(value).hex()
            for value in values.detach()
            .to(dtype=torch.float64, device="cpu")
            .contiguous()
            .reshape(-1)
            .tolist()
        ],
    }
    observer(
        stage,
        "snapshot",
        {
            "schema_id": "betelgeuze.development_coordinate_lineage/1.0.0",
            "proposal_index": proposal.proposal_index,
            "candidate_id": proposal.candidate_id,
            "proposal_fingerprint_sha256": proposal.fingerprint_sha256,
            "coordinate_fingerprint_sha256": coordinate_fingerprint(values),
            "coordinates_binary64": payload,
            "coordinate_unit": "angstrom",
            **deepcopy(details),
        },
    )
