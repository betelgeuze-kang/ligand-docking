from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch

from betelgeuze_engine.topology.complex import ComplexTopology
from betelgeuze_engine.topology.ligand import ligand_topology_from_smiles
from betelgeuze_engine.topology.protein import (
    protein_topology_from_residue_indices,
    protein_topology_from_sequence,
)
from betelgeuze_engine.topology.validity import topology_claim_metadata


@dataclass(frozen=True)
class TopologyFactoryResult:
    complex_topology: ComplexTopology
    claim_metadata: dict[str, Any]


@dataclass
class TopologyFactoryFacade:
    """Product-engine topology factory that keeps legacy core factory as a shim."""

    device: torch.device | str = "cpu"
    default_claim_scope: str = "restricted_local_delivery_proxy_refinement_only"
    default_pocket_residue_indices: list[int] = field(default_factory=list)

    def from_sequence_and_smiles(
        self,
        *,
        sequence: str,
        smiles: str,
        n_res: int | None = None,
        pocket_residue_indices: list[int] | None = None,
        claim_scope: str | None = None,
    ) -> TopologyFactoryResult:
        protein = protein_topology_from_sequence(
            sequence,
            n_res=n_res,
            device=self.device,
        )
        ligand = ligand_topology_from_smiles(smiles)
        complex_topology = ComplexTopology(
            protein=protein,
            ligand=ligand,
            pocket_residue_indices=list(
                self.default_pocket_residue_indices
                if pocket_residue_indices is None
                else pocket_residue_indices
            ),
            claim_scope=str(claim_scope or self.default_claim_scope),
        )
        return TopologyFactoryResult(
            complex_topology=complex_topology,
            claim_metadata=topology_claim_metadata(complex_topology),
        )

    def from_residue_indices_and_smiles(
        self,
        *,
        residue_indices: torch.Tensor,
        smiles: str,
        fidelity: str = "sequence_mapped",
        pocket_residue_indices: list[int] | None = None,
        claim_scope: str | None = None,
    ) -> TopologyFactoryResult:
        protein = protein_topology_from_residue_indices(
            residue_indices,
            fidelity=fidelity,
            device=self.device,
        )
        ligand = ligand_topology_from_smiles(smiles)
        complex_topology = ComplexTopology(
            protein=protein,
            ligand=ligand,
            pocket_residue_indices=list(
                self.default_pocket_residue_indices
                if pocket_residue_indices is None
                else pocket_residue_indices
            ),
            claim_scope=str(claim_scope or self.default_claim_scope),
        )
        return TopologyFactoryResult(
            complex_topology=complex_topology,
            claim_metadata=topology_claim_metadata(complex_topology),
        )
