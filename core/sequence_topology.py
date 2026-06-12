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


def residue_nonbonded_scale_for_index(residue_index: int) -> tuple[float, float]:
    """Coarse residue-class LJ scale factors as (sigma_scale, epsilon_scale)."""
    idx = int(residue_index)
    if idx == 0:
        return (1.0, 1.0)
    if idx == 6:  # Gly
        return (0.90, 0.75)
    if idx in {3, 4, 9, 15, 7}:  # D E K R H
        return (1.02, 0.90)
    if idx in {12, 14, 16, 17, 2}:  # N Q S T C
        return (0.96, 0.82)
    if idx in {5, 8, 10, 11, 18, 19, 20, 13}:  # hydrophobic/aromatic/proline
        return (1.08, 1.12)
    return (1.0, 1.0)


def residue_nonbonded_params_from_indices(
    residue_indices: torch.Tensor,
    *,
    base_sigma: float,
    base_epsilon: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Map residue indices to coarse LJ sigma/epsilon tensors."""
    values = residue_indices.detach().to(dtype=torch.long).reshape(-1).cpu().tolist()
    scales = [residue_nonbonded_scale_for_index(int(v)) for v in values]
    sigma = torch.tensor(
        [base_sigma * s for s, _ in scales],
        dtype=torch.float32,
        device=residue_indices.device,
    )
    epsilon = torch.tensor(
        [base_epsilon * e for _, e in scales],
        dtype=torch.float32,
        device=residue_indices.device,
    )
    return sigma, epsilon


def residue_coarse_charge_for_index(residue_index: int) -> float:
    """Claim-safe coarse residue charge proxy for fast-tier screening."""
    idx = int(residue_index)
    if idx in {3, 4}:  # D E
        return -1.0
    if idx in {9, 15}:  # K R
        return 1.0
    if idx == 7:  # H
        return 0.5
    return 0.0


def residue_coarse_charges_from_indices(
    residue_indices: torch.Tensor,
    *,
    charge_scale: float = 1.0,
) -> torch.Tensor:
    values = residue_indices.detach().to(dtype=torch.long).reshape(-1).cpu().tolist()
    return torch.tensor(
        [float(charge_scale) * residue_coarse_charge_for_index(int(v)) for v in values],
        dtype=torch.float32,
        device=residue_indices.device,
    )
