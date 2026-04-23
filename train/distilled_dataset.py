from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset


class DistilledResidualNPZDataset(Dataset):
    """
    Lightweight dataset for distilled residual NPZ shards.
    Required arrays:
      - residual_forces: [S, N, 3]
      - residue_types: [S, N]
    Optional arrays:
      - coords: [S, N, 3]
      - quality_score: [S]
      - sample_index: [S]
      - optional scalar metadata fields (per-sample):
        energy, Rg, compactness, sasa, cluster_max, is_llps, is_folded, rmsd,
        ionic_strength, ptm_count, force_scale, cooling_rate, hydro_strength,
        k_angle, theta0, k_dihedral, phi0_alpha, violations, ai_correction_active,
        temp, salt_conc, pH
    """

    OPTIONAL_SCALAR_FIELDS = (
        "energy",
        "Rg",
        "compactness",
        "sasa",
        "cluster_max",
        "is_llps",
        "is_folded",
        "rmsd",
        "ionic_strength",
        "ptm_count",
        "force_scale",
        "cooling_rate",
        "hydro_strength",
        "k_angle",
        "theta0",
        "k_dihedral",
        "phi0_alpha",
        "violations",
        "ai_correction_active",
        "temp",
        "salt_conc",
        "pH",
    )

    # Fields grouped by intended role to keep conditioning/targets separated.
    CONDITIONING_SCALAR_FIELDS = (
        "temp",
        "salt_conc",
        "pH",
        "ionic_strength",
        "ptm_count",
        "force_scale",
        "cooling_rate",
        "hydro_strength",
        "k_angle",
        "theta0",
        "k_dihedral",
        "phi0_alpha",
        "ai_correction_active",
    )
    TARGET_LABEL_SCALAR_FIELDS = (
        "energy",
        "Rg",
        "compactness",
        "sasa",
        "cluster_max",
        "is_llps",
        "is_folded",
        "rmsd",
    )
    QUALITY_CONTROL_SCALAR_FIELDS = (
        "violations",
    )

    def __init__(
        self,
        npz_path: str,
        mmap_mode: str = "r",
        min_quality: float | None = None,
        max_samples: int | None = None,
        shard_weight: float = 1.0,
        quality_weight_alpha: float = 0.0,
        min_sampling_weight: float = 1e-6,
    ):
        self.npz_path = npz_path
        self._npz = np.load(npz_path, mmap_mode=mmap_mode)
        if "residual_forces" not in self._npz or "residue_types" not in self._npz:
            raise ValueError(
                f"{npz_path} must include residual_forces and residue_types arrays"
            )
        self.residual_forces = self._npz["residual_forces"]
        self.residue_types = self._npz["residue_types"]
        self.coords = self._npz["coords"] if "coords" in self._npz else None
        self.quality_score = self._npz["quality_score"] if "quality_score" in self._npz else None
        self.sample_index = self._npz["sample_index"] if "sample_index" in self._npz else None
        self.scalar_fields = {}
        for field in self.OPTIONAL_SCALAR_FIELDS:
            arr = self._npz[field] if field in self._npz else None
            if arr is None:
                continue
            if int(arr.shape[0]) != int(self.residual_forces.shape[0]):
                continue
            self.scalar_fields[field] = arr
        self.scalar_field_roles = self.get_scalar_field_roles()
        n_total = int(self.residual_forces.shape[0])
        indices = np.arange(n_total, dtype=np.int64)

        if min_quality is not None and self.quality_score is not None:
            q = np.asarray(self.quality_score, dtype=np.float32)
            indices = indices[q >= float(min_quality)]

        if max_samples is not None and int(max_samples) > 0 and int(max_samples) < int(len(indices)):
            k = int(max_samples)
            if k == 1:
                indices = np.asarray([indices[-1]], dtype=np.int64)
            else:
                pos = np.linspace(0, len(indices) - 1, num=k, dtype=np.int64)
                indices = indices[pos]

        if len(indices) == 0:
            raise ValueError(f"{npz_path} has no samples after filtering")

        self.indices = indices
        self.length = int(len(self.indices))
        self.shard_weight = float(shard_weight)
        self.quality_weight_alpha = float(quality_weight_alpha)
        self.min_sampling_weight = float(min_sampling_weight)

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int):
        i = int(self.indices[idx])
        res = torch.from_numpy(np.asarray(self.residual_forces[i], dtype=np.float32))
        typ = torch.from_numpy(np.asarray(self.residue_types[i], dtype=np.int64))
        if self.coords is None:
            coords = torch.zeros_like(res)
        else:
            coords = torch.from_numpy(np.asarray(self.coords[i], dtype=np.float32))
        q = 1.0
        if self.quality_score is not None:
            q = float(np.asarray(self.quality_score[i]).item())
        if not self.scalar_fields:
            return coords, res, typ, q
        sim_params = {
            key: float(np.asarray(arr[i]).item())
            for key, arr in self.scalar_fields.items()
        }
        return coords, res, typ, q, sim_params

    def get_scalar_field_roles(self):
        present = set(self.scalar_fields.keys())
        return {
            "conditioning": tuple(k for k in self.CONDITIONING_SCALAR_FIELDS if k in present),
            "targets": tuple(k for k in self.TARGET_LABEL_SCALAR_FIELDS if k in present),
            "quality": tuple(k for k in self.QUALITY_CONTROL_SCALAR_FIELDS if k in present),
        }

    def get_sampling_weights(self) -> np.ndarray:
        weights = np.full((self.length,), fill_value=float(self.shard_weight), dtype=np.float64)
        if self.quality_score is not None and self.quality_weight_alpha != 0.0:
            q = np.asarray(self.quality_score[self.indices], dtype=np.float64)
            q = np.clip(q, a_min=float(self.min_sampling_weight), a_max=None)
            weights = weights * np.power(q, float(self.quality_weight_alpha))
        weights = np.clip(weights, a_min=float(self.min_sampling_weight), a_max=None)
        return weights

    def close(self) -> None:
        # NpzFile has close() in recent numpy versions.
        npz = getattr(self, "_npz", None)
        if npz is None:
            return
        close_fn = getattr(npz, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass
        self._npz = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
