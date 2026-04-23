# tools/pdb_loader.py

import os
import numpy as np
import torch
from core.definitions import Config

def load_native_structure(target_name):
    """
    Loads native structure coordinates from a PDB file.
    Args:
        target_name (str): Name of the target (e.g., 'Chignolin')
    Returns:
        coords (torch.Tensor): [N, 3] native coordinates
        seq (str): Sequence string
    """
    pdb_file_path = f"data/native/{target_name.lower()}.pdb"
    if not os.path.exists(pdb_file_path):
        print(f"Warning: Native PDB file for {target_name} not found at {pdb_file_path}.")
        return None, ""

    coords = []
    coords_ca = []
    seq = []
    with open(pdb_file_path, 'r') as f:
        for line in f:
            if line.startswith('ATOM') or line.startswith('HETATM'):
                atom_name = line[12:16].strip()
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append([x, y, z])
                if atom_name == 'CA':
                    coords_ca.append([x, y, z])
            elif line.startswith('SEQRES'):
                seq_part = line[19:].strip()
                seq.extend(list(seq_part))

    if not coords:
        print(f"Warning: No ATOM/HETATM records found in {pdb_file_path}.")
        return None, "".join(seq)

    # Prefer CA-only coordinates to match coarse-grained residue-level topology.
    # Fallback to all atoms when CA is unavailable.
    coords_use = coords_ca if coords_ca else coords
    coords_tensor = torch.tensor(coords_use, dtype=torch.float32, device=Config.DEVICE)
    seq_str = "".join(seq)
    return coords_tensor, seq_str

# Usage example:
# native_coords, sequence = load_native_structure('Chignolin')
