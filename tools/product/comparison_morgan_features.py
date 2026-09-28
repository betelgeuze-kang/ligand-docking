"""Lightweight Morgan feature primitive for the offline comparison runner.

Keep this byte-for-byte numeric behavior aligned with
`train_public_assay_selector.features`. The comparison runtime binds this
module's source hash before execution, and its parity is tested separately.
"""

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator


def features(smiles: list[str]) -> np.ndarray:
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=1024, includeChirality=True
    )
    matrix = []
    for text in smiles:
        mol = Chem.MolFromSmiles(text)
        if mol is None:
            raise ValueError("invalid_inference_smiles")
        if any(group.GetGroupType() != Chem.StereoGroupType.STEREO_ABSOLUTE
               for group in mol.GetStereoGroups()):
            raise ValueError("unresolved_enhanced_stereochemistry")
        matrix.append(generator.GetFingerprintAsNumPy(mol))
    return np.asarray(matrix, dtype=np.float64).reshape(len(smiles), 1024)
