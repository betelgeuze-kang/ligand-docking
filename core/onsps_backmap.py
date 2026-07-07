"""Compatibility shim; canonical module: betelgeuze_engine.backmapping.onsps.

The queue builder only needs lightweight O/N/P/S site counting to annotate rows.
Importing the canonical backend at module import time pulls in the full engine
contract surface and torch. Keep the common counting helpers local and delegate
heavier backmapping functions lazily.
"""

from __future__ import annotations

from importlib import import_module as _import_module
from typing import Any

MAX_ONSPS_SITES = 4
ONSPS_BACKMAP_SCHEMA_VERSION = "onsps_backmap_evidence_v1"
_MODULE_NAME = "betelgeuze_engine.backmapping.onsps"


def _module() -> Any:
    return _import_module(_MODULE_NAME)


def onsps_site_count(smiles: str) -> int:
    text = str(smiles or "").upper()
    return int(min(MAX_ONSPS_SITES, sum(1 for ch in text if ch in {"O", "N", "S", "P"})))


def needs_onsps_4bead(
    *,
    smiles: str,
    family: str = "",
    rank_pct: float = 1.0,
    top_k_threshold_pct: float = 0.05,
) -> bool:
    if onsps_site_count(smiles) <= 0:
        return False
    fam = str(family or "").strip().lower().replace("-", "_")
    if fam in {"gpcr", "kinase", "ion_channel"}:
        return True
    return float(rank_pct) <= float(top_k_threshold_pct)


def onsps_hbond_sites_from_smiles(smiles: str):
    return _module().onsps_hbond_sites_from_smiles(smiles)


def backmap_4bead_onsps(two_bead_xyz, smiles: str):
    return _module().backmap_4bead_onsps(two_bead_xyz, smiles)


def evaluate_onsps_backmap_evidence(two_bead_xyz, smiles: str):
    return _module().evaluate_onsps_backmap_evidence(two_bead_xyz, smiles)


def hbond_angle_score(protein_xyz, ligand_bead, pocket_center) -> float:
    return float(_module().hbond_angle_score(protein_xyz, ligand_bead, pocket_center))


def __getattr__(name: str) -> Any:
    if name.startswith("__"):
        raise AttributeError(name)
    return getattr(_module(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()))


__all__ = [
    "MAX_ONSPS_SITES",
    "ONSPS_BACKMAP_SCHEMA_VERSION",
    "backmap_4bead_onsps",
    "evaluate_onsps_backmap_evidence",
    "hbond_angle_score",
    "needs_onsps_4bead",
    "onsps_hbond_sites_from_smiles",
    "onsps_site_count",
]
