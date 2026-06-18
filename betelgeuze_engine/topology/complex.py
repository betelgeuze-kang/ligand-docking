from __future__ import annotations

from dataclasses import dataclass

from betelgeuze_engine.topology.ligand import LigandTopology
from betelgeuze_engine.topology.protein import ProteinTopology


@dataclass
class ComplexTopology:
    protein: ProteinTopology
    ligand: LigandTopology
    pocket_residue_indices: list[int]
    claim_scope: str
