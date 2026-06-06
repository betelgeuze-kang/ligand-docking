"""Sequence helpers for sequence-aware CG topology."""

from __future__ import annotations

import torch

# One-letter to coarse index (0=unknown, 1..20 standard amino acids).
_AA_INDEX = {
    "A": 1,
    "C": 2,
    "D": 3,
    "E": 4,
    "F": 5,
    "G": 6,
    "H": 7,
    "I": 8,
    "K": 9,
    "L": 10,
    "M": 11,
    "N": 12,
    "P": 13,
    "Q": 14,
    "R": 15,
    "S": 16,
    "T": 17,
    "V": 18,
    "W": 19,
    "Y": 20,
}

# Residue indices (1-based in _AA_INDEX) with H-bond capable sidechains.
_HBOND_DONOR_RESIDUES = {9, 15, 16, 17, 19, 7}  # K R S T Y H
_HBOND_ACCEPTOR_RESIDUES = {3, 4, 12, 14, 16, 17, 19, 7}  # D E N Q S T Y H


def residue_indices_from_sequence(sequence: str, *, device: torch.device | str = "cpu") -> torch.Tensor:
    text = str(sequence or "").strip().upper()
    if not text:
        return torch.ones(1, dtype=torch.long, device=device)
    values = [_AA_INDEX.get(ch, 0) for ch in text if ch.isalpha()]
    if not values:
        return torch.ones(1, dtype=torch.long, device=device)
    return torch.tensor(values, dtype=torch.long, device=device)


def hbond_role_for_residue_index(residue_index: int) -> str:
    idx = int(residue_index)
    donor = idx in _HBOND_DONOR_RESIDUES
    acceptor = idx in _HBOND_ACCEPTOR_RESIDUES
    if donor and acceptor:
        return "both"
    if donor:
        return "donor"
    if acceptor:
        return "acceptor"
    return "none"


def virtual_hbond_offset_for_residue_index(residue_index: int) -> tuple[float, float, float]:
    """Local CA→virtual H-bond bead offset (Å) by residue class."""
    role = hbond_role_for_residue_index(int(residue_index))
    if role in {"donor", "both"}:
        return (0.8, 0.6, 0.0)
    if role == "acceptor":
        return (1.0, -0.5, 0.0)
    return (0.0, 1.2, 0.0)
