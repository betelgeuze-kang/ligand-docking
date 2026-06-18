from __future__ import annotations

from dataclasses import dataclass

import torch

from core.sequence_topology import (
    hbond_role_for_residue_index,
    residue_indices_from_sequence,
    virtual_hbond_offset_for_residue_index,
)


@dataclass
class ProteinTopology:
    sequence: str
    residue_indices: torch.Tensor
    hbond_roles: list[str]
    virtual_site_offsets: torch.Tensor
    fidelity: str


def protein_topology_from_residue_indices(
    residue_indices: torch.Tensor,
    *,
    sequence: str = "",
    fidelity: str = "sequence_mapped",
    device: torch.device | str | None = None,
) -> ProteinTopology:
    target_device = device if device is not None else residue_indices.device
    indices = residue_indices.to(dtype=torch.long, device=target_device)
    roles = [hbond_role_for_residue_index(int(v)) for v in indices.detach().cpu().tolist()]
    offsets = torch.tensor(
        [virtual_hbond_offset_for_residue_index(int(v)) for v in indices.detach().cpu().tolist()],
        dtype=torch.float32,
        device=target_device,
    )
    return ProteinTopology(
        sequence=str(sequence or "").strip().upper(),
        residue_indices=indices,
        hbond_roles=roles,
        virtual_site_offsets=offsets,
        fidelity=str(fidelity),
    )


def protein_topology_from_sequence(
    sequence: str,
    *,
    n_res: int | None = None,
    device: torch.device | str = "cpu",
) -> ProteinTopology:
    text = str(sequence or "").strip().upper()
    indices = residue_indices_from_sequence(text, device=device)
    if n_res is not None:
        target = int(n_res)
        if int(indices.numel()) > target:
            indices = indices[:target]
        elif int(indices.numel()) < target:
            pad = torch.ones(target - int(indices.numel()), dtype=torch.long, device=device)
            indices = torch.cat([indices, pad], dim=0)
    fidelity = "sequence_mapped" if text else "placeholder_alanine"
    return protein_topology_from_residue_indices(
        indices,
        sequence=text,
        fidelity=fidelity,
        device=device,
    )
