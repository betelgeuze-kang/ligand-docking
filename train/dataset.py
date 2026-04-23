# train/dataset.py

import torch
from torch.utils.data import Dataset
import h5py
import numpy as np

class AIRouterHDF5Dataset(Dataset):
    def __init__(self, data_path, transform=None, target_transform=None):
        """
        Args:
            data_path (str): tools/generate_perturbed_data.py에서 저장한 .h5 파일 경로
            transform (callable, optional): 좌표에 적용할 변환
            target_transform (callable, optional): 힘에 적용할 변환
        """
        self.data_path = data_path
        self.transform = transform
        self.target_transform = target_transform

        # Open HDF5 file and get length without loading everything into memory
        with h5py.File(data_path, 'r') as f:
            self.length = f['coords'].shape[0]
            # Load static attributes if needed
            self.target_name = f.attrs.get('target', 'unknown')
            self.noise_level = f.attrs.get('noise_level', 0.0)

        # Keep file handle open for data access (consider using context manager or reopening per access)
        # This approach keeps the file open throughout the dataset lifetime
        self.file_handle = h5py.File(data_path, 'r')

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        # Load specific sample from HDF5 file
        coords = torch.from_numpy(self.file_handle['coords'][idx]).float()
        target_forces = torch.from_numpy(self.file_handle['target_forces'][idx]).float()
        residue_types = torch.from_numpy(self.file_handle['residue_types'][idx]).long()

        # Backward/forward compatibility:
        # if explicit 2-bead coords are present but residue_types are per-residue,
        # expand residue_types to match coordinate length.
        if coords.shape[0] != residue_types.shape[0]:
            if coords.shape[0] == residue_types.shape[0] * 2:
                residue_types = residue_types.repeat_interleave(2)
            else:
                raise ValueError(
                    f"Shape mismatch in {self.data_path}: coords={tuple(coords.shape)} "
                    f"residue_types={tuple(residue_types.shape)}"
                )

        if self.transform:
            coords = self.transform(coords)
        if self.target_transform:
            target_forces = self.target_transform(target_forces)

        # nb_data, pe, sim_params are not stored in HDF5, need to be generated dynamically in training loop
        # Returning coords, target_forces, residue_types is sufficient for basic loading
        return coords, target_forces, residue_types

    def close(self):
        """Close the HDF5 file handle when done."""
        fh = getattr(self, "file_handle", None)
        if fh is None:
            return
        try:
            fh.close()
        except Exception:
            pass
        self.file_handle = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
