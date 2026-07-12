from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Dict, Mapping, Optional, Sequence, Tuple

import torch

from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_NEIGHBORS,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.runtime import (
    RESIDUE_VOCABULARY,
    RuntimeConditioningBatch,
    RuntimeConditioningError,
    build_runtime_conditioning_batch,
    residue_one_hot,
)
from core.definitions import Config
from core.sim_param_schema import (
    CORE_SIM_PARAM_DEFAULTS,
    DEFAULT_RUNTIME_CONDITIONING_KEYS,
    LEAKAGE_BLOCKED_SIM_KEYS,
)


MAX_RUNTIME_NEIGHBOR_CAPACITY = MAX_COMPACT_NEIGHBORS
RUNTIME_INPUT_SCHEMA_ID = "betelgeuze.legacy_runtime_inputs.compact_radius/2.2.0"


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
        "dense_all_pairs_distance_used": False,
        "residue_vocabulary": RESIDUE_VOCABULARY.to_dict(),
        "residue_modulo_aliasing_used": False,
        "runtime_conditioning_shape": "[B,P]",
        "runtime_conditioning_batch_mean_used": False,
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
    vocabulary = metadata.get("residue_vocabulary")
    if not isinstance(vocabulary, Mapping):
        raise RuntimeInputSchemaError("checkpoint runtime schema has no residue vocabulary metadata")
    if vocabulary.get("fingerprint_sha256") != RESIDUE_VOCABULARY.fingerprint_sha256:
        raise RuntimeInputSchemaError("checkpoint residue vocabulary fingerprint mismatch")
    if bool(metadata.get("residue_modulo_aliasing_used", True)):
        raise RuntimeInputSchemaError("checkpoint used unsafe residue modulo aliasing")
    if bool(metadata.get("runtime_conditioning_batch_mean_used", True)):
        raise RuntimeInputSchemaError("checkpoint used unsafe batch-mean conditioning")
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
    return {
        key: sim_params_batch[key]
        for key in allowed_keys
        if key not in blocked and key in sim_params_batch
    }


def _conditioning_keys(
    *,
    allowed_keys: Sequence[str] = DEFAULT_RUNTIME_CONDITIONING_KEYS,
    blocked_keys: Sequence[str] = LEAKAGE_BLOCKED_SIM_KEYS,
) -> tuple[str, ...]:
    blocked = set(blocked_keys)
    return tuple(str(key) for key in allowed_keys if key not in blocked)


def resolve_sim_params_batch(
    sim_params_batch: Optional[Mapping[str, object]],
    *,
    batch_size: int,
    dtype: torch.dtype,
    device: torch.device | str,
    allowed_keys: Sequence[str] = DEFAULT_RUNTIME_CONDITIONING_KEYS,
    blocked_keys: Sequence[str] = LEAKAGE_BLOCKED_SIM_KEYS,
) -> RuntimeConditioningBatch:
    filtered = filter_runtime_conditioning_params(
        sim_params_batch,
        allowed_keys=allowed_keys,
        blocked_keys=blocked_keys,
    )
    keys = _conditioning_keys(allowed_keys=allowed_keys, blocked_keys=blocked_keys)
    defaults = {key: float(CORE_SIM_PARAM_DEFAULTS.get(key, 0.0)) for key in keys}
    return build_runtime_conditioning_batch(
        filtered,
        defaults=defaults,
        keys=keys,
        batch_size=int(batch_size),
        dtype=dtype,
        device=device,
    )


def _infer_conditioning_batch_size(parameters: Mapping[str, object]) -> int:
    observed: set[int] = set()
    for raw in parameters.values():
        if isinstance(raw, torch.Tensor):
            if raw.numel() <= 1:
                continue
            if raw.ndim == 1:
                observed.add(int(raw.shape[0]))
            elif raw.ndim == 2 and raw.shape[1] == 1:
                observed.add(int(raw.shape[0]))
            else:
                raise RuntimeConditioningError(
                    "scalar compatibility accepts only scalar, [B], or [B,1] tensors"
                )
        elif isinstance(raw, (list, tuple)) and len(raw) > 1:
            observed.add(len(raw))
    if len(observed) > 1:
        raise RuntimeConditioningError("runtime parameters disagree on batch size")
    return next(iter(observed), 1)


def resolve_sim_params(
    sim_params_batch: Optional[Mapping[str, object]],
) -> Dict[str, float]:
    """Compatibility path for scalar-only consumers.

    Unlike the previous implementation, this never averages a heterogeneous
    batch.  Every batch row must be identical or the call fails closed.
    """

    filtered = filter_runtime_conditioning_params(sim_params_batch)
    batch_size = _infer_conditioning_batch_size(filtered)
    batch = resolve_sim_params_batch(
        filtered,
        batch_size=batch_size,
        dtype=torch.float64,
        device="cpu",
    )
    return batch.require_uniform_scalar_mapping()


def _build_residue_features(
    residue_types_batch: torch.Tensor,
    topo_feature_dim: int,
    *,
    unknown_policy: str = "map_to_unk",
) -> tuple[torch.Tensor, torch.Tensor, dict[str, object]]:
    if residue_types_batch.dim() == 1:
        residue_types_batch = residue_types_batch.unsqueeze(0)
    encoded, diagnostics = residue_one_hot(
        residue_types_batch,
        output_width=int(topo_feature_dim),
        unknown_policy=unknown_policy,
    )
    normalized = torch.argmax(encoded, dim=-1).to(dtype=torch.long)
    return encoded, normalized, diagnostics


def _build_sparse_radius_neighbor_data(
    coords_batch: torch.Tensor,
    neighbor_k: int,
    *,
    cutoff_angstrom: float = 12.0,
    max_neighbor_candidates: int = 64,
    max_atoms_per_cell: int = 64,
) -> Tuple[Tuple[torch.Tensor, torch.Tensor, torch.Tensor], Dict[str, object]]:
    """Build legacy `[B,N,K]` tensors through the bounded v2 cell list."""

    if coords_batch.ndim != 3 or coords_batch.shape[-1] != 3:
        raise ValueError("coords_batch must have shape [B, N, 3]")
    bsz, n_atoms, _ = coords_batch.shape
    if bsz < 1 or n_atoms < 1:
        raise ValueError("coords_batch must contain at least one batch and one atom")
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
            "neighbor_k exceeds the fixed candidate capacity; increase the bounded capacity instead"
        )

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
            (nb_idx, torch.full((bsz, n_atoms, pad), -1, dtype=torch.long, device=coords_batch.device)),
            dim=-1,
        )
        nb_dist = torch.cat(
            (nb_dist, torch.zeros((bsz, n_atoms, pad), dtype=coords_batch.dtype, device=coords_batch.device)),
            dim=-1,
        )
        nb_mask_bool = torch.cat(
            (nb_mask_bool, torch.zeros((bsz, n_atoms, pad), dtype=torch.bool, device=coords_batch.device)),
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
            "dense_all_pairs_distance_used": False,
        }
    )
    return (nb_idx, nb_dist, nb_mask), diagnostics


def _build_knn_neighbor_data(
    coords_batch: torch.Tensor,
    neighbor_k: int,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Deprecated name; semantics are bounded local radius, not global KNN."""

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
    residue_unknown_policy: str = "map_to_unk",
):
    if coords_batch.ndim != 3 or coords_batch.shape[-1] != 3:
        raise ValueError("coords_batch must have shape [B,N,3]")
    batch_size, atom_count, _ = coords_batch.shape
    residue_ids = residue_types_batch.to(device=coords_batch.device, dtype=torch.long)
    if residue_ids.ndim == 1:
        if int(batch_size) != 1:
            raise ValueError("rank-one residue IDs are allowed only for batch size one")
        residue_ids = residue_ids.unsqueeze(0)
    if tuple(residue_ids.shape) != (int(batch_size), int(atom_count)):
        raise ValueError("residue_types_batch must have shape [B,N]")

    topo_feature_dim = int(getattr(Config, "TOPO_FEATURE_DIM", 64))
    residue_features, normalized_residue_ids, residue_diagnostics = _build_residue_features(
        residue_ids,
        topo_feature_dim,
        unknown_policy=residue_unknown_policy,
    )
    residue_features = residue_features.to(device=coords_batch.device, dtype=coords_batch.dtype)

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

    conditioning = resolve_sim_params_batch(
        sim_params_batch,
        batch_size=int(batch_size),
        dtype=coords_batch.dtype,
        device=coords_batch.device,
    )
    top_dummy = SimpleNamespace(
        residue_types=normalized_residue_ids,
        residue_features=residue_features,
        residue_vocabulary=RESIDUE_VOCABULARY.to_dict(),
        residue_diagnostics=residue_diagnostics,
        neighbor_diagnostics=neighbor_diagnostics,
        runtime_conditioning=conditioning,
    )

    nb_dist, nb_mask = nb_data[1], nb_data[2]
    inverse_distance = torch.where(
        nb_mask.bool(),
        1.0 / nb_dist.clamp_min(2.0),
        torch.zeros_like(nb_dist),
    )
    active_count = nb_mask.sum(dim=(-1, -2)).clamp_min(1.0)
    pe_proxy = (inverse_distance.sum(dim=(-1, -2)) / active_count).unsqueeze(-1)
    return top_dummy, nb_data, pe_proxy, conditioning.as_mapping()
