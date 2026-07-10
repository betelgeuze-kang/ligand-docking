from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Dict, Mapping, Optional, Sequence, Tuple

import torch
import torch.nn.functional as F

from core.definitions import Config
from core.sim_param_schema import (
    CORE_SIM_PARAM_DEFAULTS,
    DEFAULT_RUNTIME_CONDITIONING_KEYS,
    LEAKAGE_BLOCKED_SIM_KEYS,
    coerce_sim_param_float,
)
from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_NEIGHBORS,
    RadiusGraphConfig,
    build_compact_radius_graph,
)


MAX_RUNTIME_NEIGHBOR_CAPACITY = MAX_COMPACT_NEIGHBORS
RUNTIME_INPUT_SCHEMA_ID = "betelgeuze.legacy_runtime_inputs.compact_radius/2.1.0"


class RuntimeInputSchemaError(ValueError):
    """A checkpoint was trained with incompatible runtime-input semantics."""


def runtime_input_schema_metadata(
    *,
    neighbor_k: int,
    cutoff_angstrom: float,
    max_neighbor_candidates: int,
    max_atoms_per_cell: int,
) -> Dict[str, object]:
    if int(neighbor_k) < 1 or int(neighbor_k) > int(max_neighbor_candidates):
        raise ValueError("neighbor_k must be positive and no larger than max_neighbor_candidates")
    if not math.isfinite(float(cutoff_angstrom)) or float(cutoff_angstrom) <= 0.0:
        raise ValueError("cutoff_angstrom must be finite and positive")
    RadiusGraphConfig(
        cutoff_angstrom=float(cutoff_angstrom),
        max_neighbors=int(max_neighbor_candidates),
        max_atoms_per_cell=int(max_atoms_per_cell),
    )
    return {
        "schema_id": RUNTIME_INPUT_SCHEMA_ID,
        "neighbor_policy": "bounded_local_radius_then_nearest_k",
        "neighbor_k": int(neighbor_k),
        "cutoff_angstrom": float(cutoff_angstrom),
        "max_neighbor_candidates": int(max_neighbor_candidates),
        "max_atoms_per_cell": int(max_atoms_per_cell),
        "periodic": False,
        "potential_proxy": "active_neighbor_inverse_distance_mean",
        "legacy_global_knn_compatible": False,
    }


def current_runtime_input_schema_metadata() -> Dict[str, object]:
    return runtime_input_schema_metadata(
        neighbor_k=int(max(Config.get("training.neighbor_k", 10), 1)),
        cutoff_angstrom=float(Config.get("training.neighbor_cutoff_angstrom", 12.0)),
        max_neighbor_candidates=int(Config.get("training.max_neighbor_candidates", 64)),
        max_atoms_per_cell=int(Config.get("training.max_atoms_per_cell", 64)),
    )


def require_runtime_input_checkpoint_schema(
    payload: object,
    *,
    expected: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise RuntimeInputSchemaError("checkpoint payload has no runtime-input schema metadata")
    metadata = payload.get("runtime_input_schema")
    if not isinstance(metadata, Mapping):
        raise RuntimeInputSchemaError(
            "legacy/raw checkpoint is incompatible with compact-radius runtime inputs; retraining is required"
        )
    if metadata.get("schema_id") != RUNTIME_INPUT_SCHEMA_ID:
        raise RuntimeInputSchemaError(
            f"runtime-input schema mismatch: expected {RUNTIME_INPUT_SCHEMA_ID!r}, "
            f"received {metadata.get('schema_id')!r}"
        )
    if expected is not None:
        mismatched = [
            key
            for key, value in expected.items()
            if metadata.get(key) != value
        ]
        if mismatched:
            raise RuntimeInputSchemaError(
                "runtime-input configuration mismatch for keys: " + ", ".join(sorted(mismatched))
            )
    return metadata


def filter_runtime_conditioning_params(
    sim_params_batch: Optional[Mapping[str, object]],
    *,
    allowed_keys: Sequence[str] = DEFAULT_RUNTIME_CONDITIONING_KEYS,
    blocked_keys: Sequence[str] = LEAKAGE_BLOCKED_SIM_KEYS,
) -> Dict[str, object]:
    if not isinstance(sim_params_batch, Mapping):
        return {}

    blocked = set(blocked_keys)
    out: Dict[str, object] = {}
    for key in allowed_keys:
        if key in blocked:
            continue
        if key in sim_params_batch:
            out[key] = sim_params_batch[key]
    return out


def resolve_sim_params(
    sim_params_batch: Optional[Mapping[str, object]],
) -> Dict[str, float]:
    filtered = filter_runtime_conditioning_params(sim_params_batch)
    out = dict(CORE_SIM_PARAM_DEFAULTS)
    for key in CORE_SIM_PARAM_DEFAULTS.keys():
        raw = filtered.get(key, out[key])
        if torch.is_tensor(raw):
            if raw.numel() == 0:
                out[key] = float(out[key])
            else:
                out[key] = float(raw.float().mean().item())
        else:
            out[key] = coerce_sim_param_float(raw, out[key])

    for key, raw in filtered.items():
        if key in out:
            continue
        if torch.is_tensor(raw):
            if raw.numel() == 0:
                continue
            out[key] = float(raw.float().mean().item())
        else:
            out[key] = coerce_sim_param_float(raw, 0.0)
    return out


def _build_residue_features(
    residue_types_batch: torch.Tensor,
    topo_feature_dim: int,
) -> torch.Tensor:
    if residue_types_batch.dim() == 1:
        residue_types_batch = residue_types_batch.unsqueeze(0)
    residue_mod = residue_types_batch.long().clamp(min=0).remainder(int(topo_feature_dim))
    return F.one_hot(residue_mod, num_classes=int(topo_feature_dim)).float()


def _build_sparse_radius_neighbor_data(
    coords_batch: torch.Tensor,
    neighbor_k: int,
    *,
    cutoff_angstrom: float = 12.0,
    max_neighbor_candidates: int = 64,
    max_atoms_per_cell: int = 64,
) -> Tuple[Tuple[torch.Tensor, torch.Tensor, torch.Tensor], Dict[str, object]]:
    """Build legacy ``[B, N, K]`` inputs through the v2 sparse cell list.

    ``neighbor_k`` is the width consumed by the legacy model.  Candidate
    discovery has a separate, fixed capacity so selecting the nearest K local
    atoms never requires an all-pairs distance matrix.  The v2 builder raises
    on cell or candidate overflow rather than silently weakening the graph.
    """

    if coords_batch.ndim != 3 or coords_batch.shape[-1] != 3:
        raise ValueError("coords_batch must have shape [B, N, 3]")
    bsz, n_atoms, _ = coords_batch.shape
    if bsz < 1:
        raise ValueError("coords_batch must contain at least one batch")
    if not coords_batch.is_floating_point():
        raise TypeError("coords_batch must use a floating dtype")
    if not bool(torch.isfinite(coords_batch).all().item()):
        raise ValueError("coords_batch must be finite")
    k_req = max(int(neighbor_k), 1)
    candidate_capacity = int(max_neighbor_candidates)
    if candidate_capacity < 1 or candidate_capacity > MAX_RUNTIME_NEIGHBOR_CAPACITY:
        raise ValueError(
            "max_neighbor_candidates must be between 1 and "
            f"{MAX_RUNTIME_NEIGHBOR_CAPACITY}"
        )
    if k_req > candidate_capacity:
        raise ValueError(
            "neighbor_k exceeds the fixed candidate capacity; increase the fixed "
            "capacity within the hard bound instead of allocating an N-by-N row"
        )

    if n_atoms == 0:
        raise ValueError("coords_batch must contain at least one atom")
    if n_atoms == 1:
        nb_idx = torch.full((bsz, n_atoms, k_req), -1, dtype=torch.long, device=coords_batch.device)
        nb_dist = torch.zeros((bsz, n_atoms, k_req), dtype=coords_batch.dtype, device=coords_batch.device)
        nb_mask = torch.zeros((bsz, n_atoms, k_req), dtype=coords_batch.dtype, device=coords_batch.device)
        diagnostics: Dict[str, object] = {
            "status": "ready",
            "source": "v2_compact_radius_graph",
            "atom_count": 1,
            "output_neighbor_width": k_req,
            "candidate_capacity": candidate_capacity,
            "truncated_row_count": 0,
            "nxn_allocation_observed": False,
            "expected_complexity": "O(B*N) at fixed cutoff and bounded occupancy",
        }
        return (nb_idx, nb_dist, nb_mask), diagnostics

    neighbors = build_compact_radius_graph(
        coords_batch,
        RadiusGraphConfig(
            cutoff_angstrom=float(cutoff_angstrom),
            max_neighbors=candidate_capacity,
            max_atoms_per_cell=int(max_atoms_per_cell),
        ),
    )
    row_counts = neighbors.mask.sum(dim=-1)
    width = min(k_req, int(neighbors.width))
    nb_idx = neighbors.indices[..., :width]
    nb_dist = neighbors.distances[..., :width]
    nb_mask_bool = neighbors.mask[..., :width]
    if width < k_req:
        pad = k_req - width
        nb_idx = torch.cat(
            (
                nb_idx,
                torch.full((bsz, n_atoms, pad), -1, dtype=torch.long, device=coords_batch.device),
            ),
            dim=-1,
        )
        nb_dist = torch.cat(
            (
                nb_dist,
                torch.zeros((bsz, n_atoms, pad), dtype=coords_batch.dtype, device=coords_batch.device),
            ),
            dim=-1,
        )
        nb_mask_bool = torch.cat(
            (
                nb_mask_bool,
                torch.zeros((bsz, n_atoms, pad), dtype=torch.bool, device=coords_batch.device),
            ),
            dim=-1,
        )
    nb_mask = nb_mask_bool.to(dtype=coords_batch.dtype)
    diagnostics = neighbors.diagnostics.to_dict()
    diagnostics.update(
        {
            "source": "v2_compact_radius_graph",
            "output_neighbor_width": k_req,
            "candidate_capacity": candidate_capacity,
            "truncated_row_count": int((row_counts > k_req).sum().detach().cpu().item()),
        }
    )
    return (nb_idx, nb_dist, nb_mask), diagnostics


def _build_knn_neighbor_data(
    coords_batch: torch.Tensor,
    neighbor_k: int,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Deprecated name for the new local-radius semantics; not global-KNN compatible."""

    data, _diagnostics = _build_sparse_radius_neighbor_data(coords_batch, neighbor_k)
    return data


def build_runtime_inputs(
    coords_batch: torch.Tensor,
    residue_types_batch: torch.Tensor,
    *,
    sim_params_batch: Optional[Mapping[str, object]] = None,
    neighbor_k: int = 10,
    neighbor_cutoff_angstrom: float | None = None,
    max_neighbor_candidates: int | None = None,
    max_atoms_per_cell: int | None = None,
):
    topo_feature_dim = int(getattr(Config, "TOPO_FEATURE_DIM", 64))
    residue_features = _build_residue_features(
        residue_types_batch=residue_types_batch.to(coords_batch.device),
        topo_feature_dim=topo_feature_dim,
    ).to(device=coords_batch.device, dtype=coords_batch.dtype)
    cutoff = float(
        neighbor_cutoff_angstrom
        if neighbor_cutoff_angstrom is not None
        else Config.get("training.neighbor_cutoff_angstrom", 12.0)
    )
    candidate_capacity = int(
        max_neighbor_candidates
        if max_neighbor_candidates is not None
        else Config.get("training.max_neighbor_candidates", 64)
    )
    cell_capacity = int(
        max_atoms_per_cell
        if max_atoms_per_cell is not None
        else Config.get("training.max_atoms_per_cell", 64)
    )
    nb_data, neighbor_diagnostics = _build_sparse_radius_neighbor_data(
        coords_batch,
        neighbor_k=max(int(neighbor_k), 1),
        cutoff_angstrom=cutoff,
        max_neighbor_candidates=candidate_capacity,
        max_atoms_per_cell=cell_capacity,
    )
    top_dummy = SimpleNamespace(
        residue_types=residue_types_batch.to(coords_batch.device),
        residue_features=residue_features,
        neighbor_diagnostics=neighbor_diagnostics,
    )

    # Lightweight potential proxy for modules that expect PE tensor shape [B, 1].
    nb_dist, nb_mask = nb_data[1], nb_data[2]
    inverse_distance = torch.where(
        nb_mask.bool(),
        1.0 / nb_dist.clamp_min(2.0),
        torch.zeros_like(nb_dist),
    )
    active_count = nb_mask.sum(dim=(-1, -2)).clamp_min(1.0)
    pe_proxy = (inverse_distance.sum(dim=(-1, -2)) / active_count).unsqueeze(-1)
    sim_params = resolve_sim_params(sim_params_batch)
    return top_dummy, nb_data, pe_proxy, sim_params
