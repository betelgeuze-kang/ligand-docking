# core/topology.py

import torch
import torch.nn as nn
from .claim_boundary import (
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
    default_topology_claim_metadata,
)
from .definitions import StrategyType

class TopologyFactory:
    """
    Creates topology objects based on strategy type (e.g., CA-SC 2-bead model, AdResS).
    """
    def __init__(self, n_res, t_type, box_size, device, target_name=None, strategy_type=StrategyType.CA_ONLY):
        self.n_res = n_res
        self.t_type = t_type
        self.box_size = torch.tensor(box_size, dtype=torch.float32, device=device)
        self.device = device
        self.target_name = target_name
        self.strategy_type = strategy_type
        self.residue_types_source = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        self.claim_metadata = default_topology_claim_metadata(
            residue_types_source=self.residue_types_source
        )

        # [NEW] AdResS support flags
        self.use_adress = strategy_type == StrategyType.ADRESS
        self.use_virtual_sc = strategy_type == StrategyType.CA_ONLY
        self.active_site_residues = None # [NEW] Define active site residues (list of indices)
        self.transition_region = None # [NEW] Define transition region atoms/residues

        if self.use_adress:
            print(f"  🧬 ACTIVE (AdResS: All-Atom + Coarse-Grained)")
        elif self.use_virtual_sc:
            print(f"  ✅ ACTIVE (2-Bead physics: CA + Virtual SC)")
        else:
            print(f"  ❌ INACTIVE (All-Atom physics)")

        # Initialize basic properties
        self.residue_types = self._create_residue_types().to(device) # [N_res]
        if self.use_virtual_sc:
            self.virtual_sc_coords = self._initialize_virtual_sc_coords().to(device) # [1, N_res, 3]
        # [NEW] AdResS-specific properties
        if self.use_adress:
            self.atom_types_adress = self._create_adress_atom_types().to(device) # [N_atoms_total] # Total atoms (AA + CG)
            self.atom_coords_adress = self._initialize_adress_coords().to(device) # [1, N_atoms_total, 3]

    def _create_residue_types(self):
        """
        Creates a tensor of residue types (e.g., amino acid indices).
        """
        # Placeholder: All residues are Alanine (index 1) for simplicity
        # In practice, this would come from a sequence or PDB file
        self.residue_types_source = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        self.claim_metadata = default_topology_claim_metadata(
            residue_types_source=self.residue_types_source
        )
        return torch.ones(self.n_res, dtype=torch.long, device=self.device) # Example: all Alanine

    def set_residue_types_from_sequence(self, residue_type_indices: torch.Tensor) -> None:
        """Inject sequence-mapped residue types when authoritative sequence data exists."""
        if residue_type_indices.shape[0] != self.n_res:
            raise ValueError("residue_type_indices length must match n_res")
        self.residue_types = residue_type_indices.to(dtype=torch.long, device=self.device)
        self.residue_types_source = TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
        self.claim_metadata = default_topology_claim_metadata(
            residue_types_source=self.residue_types_source
        )

    def topology_fidelity(self) -> str:
        return str(self.claim_metadata.get("topology_fidelity", TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE))

    def _initialize_virtual_sc_coords(self):
        """
        Initializes virtual side chain coordinates based on CA positions.
        """
        # Simple initialization: Place SC beads near CA
        # In practice, this would depend on the residue type and secondary structure
        c_ca = torch.linspace(0, self.n_res-1, self.n_res, device=self.device).view(1, self.n_res, 1).repeat(1, 1, 3) # Linear init for CA
        return self.compute_virtual_sc_coords(c_ca)

    def compute_virtual_sc_coords(self, c_ca):
        """
        Compute virtual SC coordinates from CA coordinates.
        Args:
            c_ca: [B, N_res, 3]
        Returns:
            c_sc: [B, N_res, 3]
        """
        # Fixed local offset baseline for the lightweight CA-SC model.
        c_sc_offset = torch.tensor([0.0, 1.5, 0.0], dtype=c_ca.dtype, device=c_ca.device).view(1, 1, 3)
        return c_ca + c_sc_offset.expand(c_ca.shape[0], c_ca.shape[1], 3)

    def expand_residue_types_for_virtual_sc(self):
        """
        Returns residue types aligned to a CA+SC representation.
        Each residue type is repeated for (CA, SC) beads.
        """
        if not self.use_virtual_sc:
            return self.residue_types
        return self.residue_types.repeat_interleave(2)

    # [NEW] AdResS-specific methods
    def _create_adress_atom_types(self):
        """
        Defines atom types for AdResS simulation.
        Returns a tensor mapping atom index to type (e.g., 0=AA, 1=CG).
        This is a simplified example. Real implementation needs detailed mapping.
        """
        # Example: Assume each residue has 10 AA atoms and 1 CG bead
        # Total atoms = n_res * 10 (AA) + n_res (CG) = n_res * 11
        # If active_site_residues is defined, those residues remain AA, others become CG
        total_atoms_aa = self.n_res * 10 # Approximate AA atoms per residue
        total_atoms_cg = self.n_res # One CG bead per residue
        total_atoms = total_atoms_aa + total_atoms_cg

        atom_types = torch.zeros(total_atoms, dtype=torch.long, device=self.device)
        # Mark CG beads (example: every 11th atom starting from 10th index per residue)
        cg_indices = torch.arange(10, total_atoms, 11, device=self.device)
        atom_types[cg_indices] = 1 # Mark as CG

        return atom_types

    def _initialize_adress_coords(self):
        """
        Initializes coordinates for AdResS simulation.
        Combines CA coordinates (for CG beads) and detailed AA coordinates (for active site).
        This is a simplified example. Real implementation needs detailed structure.
        """
        # Example: Start with CA coordinates for CG beads
        c_ca = torch.linspace(0, self.n_res-1, self.n_res, device=self.device).view(1, self.n_res, 1).repeat(1, 1, 3) # Linear init for CA
        # Create placeholder for AA coordinates (not detailed here)
        c_aa = torch.zeros(1, self.n_res * 10, 3, device=self.device) # Placeholder for AA atoms
        # Combine coordinates (CG beads first, then AA atoms)
        c_combined = torch.cat([c_ca.repeat(1, 1, 10).view(1, -1, 3), c_aa], dim=1) # [1, total_atoms, 3]
        return c_combined

    def set_active_site(self, residue_indices):
        """
        Sets the active site residues for AdResS simulation.
        Args:
            residue_indices (list): List of residue indices (0-based) considered as active site.
        """
        self.active_site_residues = residue_indices
        print(f"AdResS: Active site set to residues {residue_indices}")

    def set_transition_region(self, atom_indices):
        """
        Sets the transition region atoms for AdResS simulation.
        Args:
            atom_indices (list): List of atom indices (0-based) in the transition region.
        """
        self.transition_region = atom_indices
        print(f"AdResS: Transition region set to atoms {atom_indices}")

    def calculate_aa_cg_distance(self, aa_coords, cg_coords):
        """
        Calculates distances between AA atoms and CG beads.
        This is a placeholder for the actual distance calculation logic needed in the force field.
        Args:
            aa_coords: [B, N_aa, 3] coordinates of AA atoms
            cg_coords: [B, N_cg, 3] coordinates of CG beads
        Returns:
            distances: [B, N_aa, N_cg] distance matrix
        """
        # Simple pairwise distance calculation (can be optimized with neighbor lists later)
        aa_expanded = aa_coords.unsqueeze(2) # [B, N_aa, 1, 3]
        cg_expanded = cg_coords.unsqueeze(1) # [B, 1, N_cg, 3]
        diff = aa_expanded - cg_expanded # [B, N_aa, N_cg, 3]
        distances = torch.norm(diff, dim=-1) # [B, N_aa, N_cg]
        return distances

    def update_virtual_sc_coords(self, c_ca, new_sc_coords_func=None):
        """
        Updates virtual SC coordinates based on current CA coordinates.
        Args:
            c_ca: Current CA coordinates [B, N_res, 3]
            new_sc_coords_func: Optional function to calculate new SC coords from CA coords
        """
        if self.use_virtual_sc:
            if new_sc_coords_func:
                self.virtual_sc_coords = new_sc_coords_func(c_ca)
            else:
                # Default: regenerate virtual SC from current CA.
                self.virtual_sc_coords = self.compute_virtual_sc_coords(c_ca)

    # [NEW] Method to get AdResS-specific neighbor data (if needed)
    def get_adress_neighbor_data(self, c):
        """
        Calculates neighbor data considering both AA and CG particles.
        This is a placeholder. Real implementation requires AdResS-specific logic.
        """
        if self.use_adress:
            # Use spatial hash or other method on combined coordinates (c_combined)
            # Return neighbor indices, distances, masks for both AA and CG regions
            # This is highly complex and depends on the specific AdResS scheme
            # For now, return a dummy structure
            B, N_total, _ = c.shape
            K_max = 100 # Example max neighbors
            nb_idx = torch.randint(0, N_total, (B, N_total, K_max), device=self.device)
            nb_dist = torch.randn(B, N_total, K_max, device=self.device)
            nb_mask = torch.ones(B, N_total, K_max, device=self.device)
            return nb_idx, nb_dist, nb_mask
        else:
            return None, None, None # Not applicable
