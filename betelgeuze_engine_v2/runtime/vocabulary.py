"""Versioned residue vocabulary for legacy runtime-input migration.

The legacy sequence topology already uses ``0`` for unknown and ``1..20`` for
standard amino acids.  This module makes that mapping explicit and prevents the
old modulo operation from aliasing unrelated or corrupt residue identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import torch
import torch.nn.functional as F


RESIDUE_VOCABULARY_SCHEMA_ID = "betelgeuze.residue_vocabulary/1.0.0"
RESIDUE_UNK_ID = 0
RESIDUE_LABELS = (
    "UNK",
    "ALA",
    "CYS",
    "ASP",
    "GLU",
    "PHE",
    "GLY",
    "HIS",
    "ILE",
    "LYS",
    "LEU",
    "MET",
    "ASN",
    "PRO",
    "GLN",
    "ARG",
    "SER",
    "THR",
    "VAL",
    "TRP",
    "TYR",
)
RESIDUE_VOCABULARY_SIZE = len(RESIDUE_LABELS)
RESIDUE_ID_BY_LABEL = {label: index for index, label in enumerate(RESIDUE_LABELS)}


class ResidueVocabularyError(ValueError):
    """A residue identifier cannot be represented by the declared vocabulary."""


@dataclass(frozen=True)
class ResidueVocabularyMetadata:
    schema_id: str = RESIDUE_VOCABULARY_SCHEMA_ID
    unknown_id: int = RESIDUE_UNK_ID
    labels: tuple[str, ...] = RESIDUE_LABELS

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "unknown_id": int(self.unknown_id),
            "labels": list(self.labels),
            "size": len(self.labels),
            "fingerprint_sha256": self.fingerprint_sha256,
        }

    @property
    def fingerprint_sha256(self) -> str:
        payload = {
            "schema_id": self.schema_id,
            "unknown_id": int(self.unknown_id),
            "labels": list(self.labels),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


RESIDUE_VOCABULARY = ResidueVocabularyMetadata()


def normalize_residue_ids(
    residue_ids: torch.Tensor,
    *,
    unknown_policy: str = "map_to_unk",
) -> tuple[torch.Tensor, torch.Tensor]:
    """Normalize residue IDs without modulo aliasing.

    Returns ``(normalized, unknown_mask)``.  ``unknown_policy`` may be
    ``map_to_unk`` or ``error``.  No other remapping is performed.
    """

    if not isinstance(residue_ids, torch.Tensor):
        raise TypeError("residue_ids must be a torch.Tensor")
    if residue_ids.ndim not in (1, 2):
        raise ValueError("residue_ids must have shape [N] or [B, N]")
    policy = str(unknown_policy or "").strip().lower()
    if policy not in {"map_to_unk", "error"}:
        raise ValueError("unknown_policy must be 'map_to_unk' or 'error'")

    values = residue_ids.to(dtype=torch.long)
    unknown_mask = (values < 0) | (values >= RESIDUE_VOCABULARY_SIZE)
    if policy == "error" and bool(unknown_mask.any().item()):
        invalid = sorted(set(values[unknown_mask].detach().cpu().tolist()))
        preview = ", ".join(str(value) for value in invalid[:8])
        raise ResidueVocabularyError(
            "residue IDs are outside the declared vocabulary: " + preview
        )
    normalized = torch.where(
        unknown_mask,
        torch.full_like(values, RESIDUE_UNK_ID),
        values,
    )
    return normalized, unknown_mask


def residue_one_hot(
    residue_ids: torch.Tensor,
    *,
    output_width: int,
    unknown_policy: str = "map_to_unk",
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Build one-hot rows using explicit IDs and a stable UNK bucket."""

    width = int(output_width)
    if width < RESIDUE_VOCABULARY_SIZE:
        raise ResidueVocabularyError(
            f"output_width must be at least {RESIDUE_VOCABULARY_SIZE}"
        )
    normalized, unknown_mask = normalize_residue_ids(
        residue_ids,
        unknown_policy=unknown_policy,
    )
    encoded = F.one_hot(normalized, num_classes=width).to(dtype=torch.float32)
    diagnostics = {
        **RESIDUE_VOCABULARY.to_dict(),
        "output_width": width,
        "unknown_count": int(unknown_mask.sum().detach().cpu().item()),
        "modulo_aliasing_used": False,
        "unknown_policy": str(unknown_policy),
    }
    return encoded, diagnostics


__all__ = [
    "RESIDUE_ID_BY_LABEL",
    "RESIDUE_LABELS",
    "RESIDUE_UNK_ID",
    "RESIDUE_VOCABULARY",
    "RESIDUE_VOCABULARY_SCHEMA_ID",
    "RESIDUE_VOCABULARY_SIZE",
    "ResidueVocabularyError",
    "ResidueVocabularyMetadata",
    "normalize_residue_ids",
    "residue_one_hot",
]
