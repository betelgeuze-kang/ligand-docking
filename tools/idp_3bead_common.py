from __future__ import annotations

import math
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import torch

from core.spatial import GridSpatialHash
from core.rust_hip_backend import RustHipBackend
from run_validation import calculate_rg, calculate_sasa_proxy
from theory.branches.idp_logic import IDPLogic


CHARGED_POS = {"LYS", "ARG", "HIS"}
CHARGED_NEG = {"ASP", "GLU"}
AROMATIC = {"PHE", "TYR", "TRP", "HIS"}
POLAR = {"SER", "THR", "ASN", "GLN", "CYS", "TYR", "HIS"}
HYDROPHOBIC = {"ALA", "VAL", "ILE", "LEU", "MET", "PHE", "TRP", "PRO"}
DISORDER_PROMOTING = {"ALA", "ARG", "GLY", "GLN", "SER", "GLU", "LYS", "PRO"}
BRANCH_NAMES = ["llps_lcd", "aggregation_prone", "helix_tad"]
STATE_NAMES = [
    "expanded_disordered",
    "compact_disordered",
    "helix_enriched",
    "sticky_condensed",
]

RESNAME_TO_ID = {
    "ALA": 0,
    "ARG": 1,
    "ASN": 2,
    "ASP": 3,
    "CYS": 4,
    "GLN": 5,
    "GLU": 6,
    "GLY": 7,
    "HIS": 8,
    "ILE": 9,
    "LEU": 10,
    "LYS": 11,
    "MET": 12,
    "PHE": 13,
    "PRO": 14,
    "SER": 15,
    "THR": 16,
    "TRP": 17,
    "TYR": 18,
    "VAL": 19,
    "UNK": 20,
}


def _residue_id(resname: str) -> int:
    return int(RESNAME_TO_ID.get(str(resname).upper().strip(), RESNAME_TO_ID["UNK"]))


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def normalize_branch_profile(profile: Dict[str, Any] | None) -> Dict[str, float]:
    raw = {name: float((profile or {}).get(name, 0.0) or 0.0) for name in BRANCH_NAMES}
    total = sum(max(v, 0.0) for v in raw.values())
    if total <= 0.0:
        return {name: 1.0 / len(BRANCH_NAMES) for name in BRANCH_NAMES}
    return {name: max(raw[name], 0.0) / total for name in BRANCH_NAMES}


def infer_branch_profile(target_cfg: Dict[str, Any]) -> Dict[str, float]:
    explicit = target_cfg.get("branch_profile")
    if isinstance(explicit, dict):
        return normalize_branch_profile(explicit)
    name = str(target_cfg.get("name", "")).lower()
    if any(tok in name for tok in ("fus", "hnrnpa1", "tardbp", "ews", "tia1", "ddx4", "npm1", "lcd", "idr")):
        return {"llps_lcd": 0.80, "aggregation_prone": 0.15, "helix_tad": 0.05}
    if any(tok in name for tok in ("alpha_syn", "tau", "amyloid", "prion", "polyq")):
        return {"llps_lcd": 0.10, "aggregation_prone": 0.80, "helix_tad": 0.10}
    if any(tok in name for tok in ("tp53", "sic1", "p27", "cmyc", "ash1", "tad", "kid")):
        return {"llps_lcd": 0.10, "aggregation_prone": 0.15, "helix_tad": 0.75}
    return {name: 1.0 / len(BRANCH_NAMES) for name in BRANCH_NAMES}


def branch_label_from_profile(profile: Dict[str, Any] | None) -> str:
    prof = normalize_branch_profile(profile)
    return max(prof.items(), key=lambda kv: kv[1])[0]


def dominant_state_from_metrics(
    rg_mean: float,
    sasa_proxy_mean: float,
    contact_persistence: float,
    transient_helicity: float,
    ensemble_diversity: float,
    rg_percentile: float,
) -> str:
    if float(transient_helicity) >= 0.18:
        return "helix_enriched"
    if float(contact_persistence) >= 0.18 and float(ensemble_diversity) <= 10.0:
        return "sticky_condensed"
    if float(rg_percentile) <= 0.40 and float(contact_persistence) >= 0.10:
        return "compact_disordered"
    return "expanded_disordered"


def flags_from_metrics(
    contact_persistence: float,
    ensemble_diversity: float,
    frac_aromatic: float,
    net_charge_proxy: float,
) -> Dict[str, int]:
    aggregation_flag = int(
        float(contact_persistence) >= 0.18
        and float(ensemble_diversity) <= 8.0
        and float(frac_aromatic) >= 0.08
    )
    llps_flag = int(
        float(contact_persistence) >= 0.12
        and float(frac_aromatic) >= 0.10
        and abs(float(net_charge_proxy)) <= 0.25
        and float(ensemble_diversity) <= 14.0
    )
    return {
        "aggregation_flag": aggregation_flag,
        "llps_flag": llps_flag,
    }


def ranking_scores_from_metrics(
    rg_mean: float,
    sasa_proxy_mean: float,
    contact_persistence: float,
    transient_helicity: float,
    ensemble_diversity: float,
    llps_flag: int,
) -> Dict[str, float]:
    compactness = (-0.55 * float(rg_mean)) + (-0.20 * float(sasa_proxy_mean) / 100.0) + (3.0 * float(contact_persistence))
    helicity = float(transient_helicity)
    condensation = (3.5 * float(contact_persistence)) + (-0.25 * float(ensemble_diversity)) + (0.5 * float(llps_flag))
    return {
        "compactness_score": float(compactness),
        "helicity_score": float(helicity),
        "condensation_score": float(condensation),
    }


def load_ca_coords_from_pdb(path: str, device: torch.device) -> torch.Tensor:
    coords: List[List[float]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            if line[12:16].strip() != "CA":
                continue
            try:
                coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            except Exception:
                continue
    if not coords:
        raise ValueError(f"no CA coordinates found in pdb: {path}")
    return torch.tensor(coords, dtype=torch.float32, device=device)


def _load_ca_records_from_pdb(path: str) -> List[Tuple[str, List[float]]]:
    records: List[Tuple[str, List[float]]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            if line[12:16].strip() != "CA":
                continue
            try:
                resname = line[17:20].strip().upper()
                xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
            except Exception:
                continue
            records.append((resname, xyz))
    return records


def make_synthetic_idp_coords(
    n_res: int,
    seed: int,
    device: torch.device,
    noise_scale: float,
    collapse_bias: float = 0.0,
) -> torch.Tensor:
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    base = torch.zeros((n_res, 3), dtype=torch.float32)
    base[:, 0] = torch.linspace(0.0, float(max(n_res - 1, 1)) * 1.42, n_res)
    phase = torch.linspace(0.0, 2.0 * math.pi, n_res)
    base[:, 1] = 2.1 * torch.sin(phase)
    base[:, 2] = 1.3 * torch.cos(0.55 * phase)
    noise = torch.randn((n_res, 3), generator=gen, dtype=torch.float32) * float(noise_scale)
    coords = base + noise
    if float(collapse_bias) > 0.0:
        center = coords.mean(dim=0, keepdim=True)
        coords = center + (coords - center) * max(0.25, 1.0 - float(collapse_bias))
    return coords.to(device=device)


def _slice_records(records: List[Tuple[str, List[float]]], target_cfg: Dict[str, Any]) -> List[Tuple[str, List[float]]]:
    start = max(1, int(target_cfg.get("residue_start", 1)))
    end = int(target_cfg.get("residue_end", len(records)))
    end = max(start, min(end, len(records)))
    records = records[start - 1 : end]
    max_res = int(target_cfg.get("max_residues", 0))
    if max_res > 0 and len(records) > max_res:
        records = records[:max_res]
    return records


def _synthetic_resnames(n_res: int, branch_profile: Dict[str, Any] | None) -> List[str]:
    prof = normalize_branch_profile(branch_profile)
    if prof["llps_lcd"] >= max(prof["aggregation_prone"], prof["helix_tad"]):
        palette = ["GLY", "ARG", "PHE", "TYR", "SER", "GLN", "ASP", "ASN"]
    elif prof["aggregation_prone"] >= max(prof["llps_lcd"], prof["helix_tad"]):
        palette = ["GLY", "VAL", "PHE", "TYR", "LYS", "GLN", "ALA", "THR"]
    else:
        palette = ["ALA", "GLU", "LEU", "LYS", "GLN", "SER", "THR", "MET"]
    return [palette[i % len(palette)] for i in range(max(int(n_res), 1))]


def build_target_top(target_cfg: Dict[str, Any], device: torch.device):
    source = str(target_cfg.get("source", "synthetic")).strip().lower()
    if source == "pdb":
        pdb_path = os.path.abspath(str(target_cfg["pdb_path"]))
        records = _slice_records(_load_ca_records_from_pdb(pdb_path), target_cfg)
        resnames = [r[0] for r in records]
    else:
        resnames = _synthetic_resnames(
            n_res=int(target_cfg.get("n_res", 64)),
            branch_profile=target_cfg.get("branch_profile"),
        )
    residue_types = torch.tensor([_residue_id(name) for name in resnames], dtype=torch.long, device=device).view(1, -1)
    box_size = float(target_cfg.get("box_size", 160.0) or 160.0)
    return type(
        "Top",
        (),
        {
            "residue_types": residue_types,
            "residue_names": tuple(resnames),
            "box_size": torch.tensor([box_size, box_size, box_size], dtype=torch.float32, device=device),
            "n_res": int(residue_types.shape[1]),
            "use_virtual_sc": False,
        },
    )()


def build_mock_top(n_res: int, device: torch.device):
    return build_target_top({"source": "synthetic", "n_res": int(n_res)}, device=device)


_CELL_OFFSETS = torch.tensor(
    [[dx, dy, dz] for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)],
    dtype=torch.long,
)


def _cell_list_knn_single(
    coords: torch.Tensor,
    k: int,
    cell_size: float = 8.0,
    seq_window: int = 8,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    n_atoms = int(coords.shape[0])
    if n_atoms <= 1:
        return (
            torch.full((n_atoms, 0), -1, dtype=torch.long, device=coords.device),
            torch.zeros((n_atoms, 0), dtype=coords.dtype, device=coords.device),
            torch.zeros((n_atoms, 0), dtype=coords.dtype, device=coords.device),
        )
    k_eff = int(max(1, min(k, n_atoms - 1)))
    device = coords.device
    cell = torch.floor(coords / float(cell_size)).to(dtype=torch.long)
    mins = cell.min(dim=0).values - 1
    local = cell - mins
    dims = local.max(dim=0).values + 3
    hash_vals = local[:, 0] + dims[0] * (local[:, 1] + dims[1] * local[:, 2])
    unique_hash, inverse = torch.unique(hash_vals, sorted=True, return_inverse=True)
    counts = torch.bincount(inverse, minlength=int(unique_hash.numel()))
    max_bucket = int(max(int(counts.max().item()), 1))
    perm = torch.argsort(inverse)
    inv_sorted = inverse[perm]
    sorted_idx = torch.arange(n_atoms, device=device, dtype=torch.long)
    change = torch.ones_like(inv_sorted, dtype=torch.bool)
    if int(inv_sorted.numel()) > 1:
        change[1:] = inv_sorted[1:] != inv_sorted[:-1]
    starts = torch.where(change, sorted_idx, torch.zeros_like(sorted_idx))
    group_start = torch.cummax(starts, dim=0).values
    rank_sorted = sorted_idx - group_start
    rank = torch.empty_like(rank_sorted)
    rank[perm] = rank_sorted
    bucket = torch.full((int(unique_hash.numel()), max_bucket), -1, dtype=torch.long, device=device)
    bucket[inverse, rank] = torch.arange(n_atoms, device=device, dtype=torch.long)

    offsets = _CELL_OFFSETS.to(device=device)
    query_local = local.unsqueeze(1) + offsets.unsqueeze(0)
    valid_query = (
        (query_local[..., 0] >= 0)
        & (query_local[..., 1] >= 0)
        & (query_local[..., 2] >= 0)
        & (query_local[..., 0] < dims[0])
        & (query_local[..., 1] < dims[1])
        & (query_local[..., 2] < dims[2])
    )
    q_hash = query_local[..., 0] + dims[0] * (query_local[..., 1] + dims[1] * query_local[..., 2])
    flat_hash = q_hash.reshape(-1)
    pos = torch.searchsorted(unique_hash, flat_hash)
    safe_pos = pos.clamp(max=max(int(unique_hash.numel()) - 1, 0))
    flat_valid = valid_query.reshape(-1) & (pos < int(unique_hash.numel()))
    if int(unique_hash.numel()) > 0:
        flat_valid = flat_valid & (unique_hash[safe_pos] == flat_hash)
    cell_ids = torch.where(flat_valid, safe_pos, torch.full_like(safe_pos, -1)).view(n_atoms, -1)
    safe_cell_ids = cell_ids.clamp_min(0)
    cand_idx = bucket[safe_cell_ids].reshape(n_atoms, -1)
    cand_valid = ((cell_ids.unsqueeze(-1) >= 0) & (bucket[safe_cell_ids] >= 0)).reshape(n_atoms, -1)

    if seq_window > 0:
        seq_offsets = torch.arange(-seq_window, seq_window + 1, device=device, dtype=torch.long)
        seq_offsets = seq_offsets[seq_offsets != 0]
        seq_idx = torch.arange(n_atoms, device=device, dtype=torch.long).unsqueeze(1) + seq_offsets.unsqueeze(0)
        seq_valid = (seq_idx >= 0) & (seq_idx < n_atoms)
        cand_idx = torch.cat([cand_idx, seq_idx.clamp(0, n_atoms - 1)], dim=1)
        cand_valid = torch.cat([cand_valid, seq_valid], dim=1)

    self_idx = torch.arange(n_atoms, device=device, dtype=torch.long).unsqueeze(1)
    cand_valid = cand_valid & (cand_idx != self_idx)
    safe_cand = cand_idx.clamp_min(0)
    cand_coords = coords[safe_cand]
    dist = torch.linalg.norm(cand_coords - coords.unsqueeze(1), dim=-1)
    inf = torch.full_like(dist, float("inf"))
    dist = torch.where(cand_valid, dist, inf)
    topk_dist, topk_pos = torch.topk(dist, k=k_eff, largest=False, dim=1)
    topk_idx = cand_idx.gather(1, topk_pos)
    topk_mask = torch.isfinite(topk_dist)
    topk_dist = torch.where(topk_mask, topk_dist, torch.zeros_like(topk_dist))
    topk_idx = torch.where(topk_mask, topk_idx, torch.full_like(topk_idx, -1))
    return topk_idx.long(), topk_dist.float(), topk_mask.float()


def knn_nb_data(c: torch.Tensor, k: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if int(c.dim()) != 3:
        raise ValueError(f"expected [B,N,3] coords, got shape={tuple(c.shape)}")
    idx_rows: List[torch.Tensor] = []
    dist_rows: List[torch.Tensor] = []
    mask_rows: List[torch.Tensor] = []
    for batch_idx in range(int(c.shape[0])):
        nb_idx, nb_dist, nb_mask = _cell_list_knn_single(c[batch_idx], k=k)
        idx_rows.append(nb_idx)
        dist_rows.append(nb_dist)
        mask_rows.append(nb_mask)
    return torch.stack(idx_rows, dim=0), torch.stack(dist_rows, dim=0), torch.stack(mask_rows, dim=0)


def _infer_box_size(coords0: torch.Tensor, margin: float = 32.0) -> float:
    span = torch.max(coords0, dim=0).values - torch.min(coords0, dim=0).values
    max_span = float(span.max().item()) if int(span.numel()) > 0 else 0.0
    return float(max(max_span + float(margin), 96.0))


def _neighbor_settings_from_params(params: Dict[str, Any], k: int) -> Dict[str, float]:
    runtime = dict(params.get("idp_neighbor_settings", {}) or {})
    candidate_neighbors = int(runtime.get("candidate_max_neighbors", max(int(k) * 4, int(k) + 16)) or max(int(k) * 4, int(k) + 16))
    generic_mode = str(runtime.get("generic_nonbonded_mode", params.get("idp_generic_nonbonded_mode", "additive")) or "additive").strip().lower()
    if generic_mode not in {"additive", "replace_partial"}:
        generic_mode = "additive"
    replace_fraction = float(runtime.get("generic_nonbonded_replace_fraction", params.get("idp_generic_nonbonded_replace_fraction", 0.0)) or 0.0)
    return {
        "grid_spacing": float(runtime.get("grid_spacing", 12.0) or 12.0),
        "cutoff": float(runtime.get("cutoff", 12.0) or 12.0),
        "skin": float(runtime.get("skin", 2.0) or 2.0),
        "rebuild_stride": int(runtime.get("rebuild_stride", 4) or 4),
        "max_neighbors": int(runtime.get("max_neighbors", candidate_neighbors) or candidate_neighbors),
        "candidate_max_neighbors": int(candidate_neighbors),
        "max_atoms_per_cell": int(runtime.get("max_atoms_per_cell", 64) or 64),
        "seq_window": int(runtime.get("seq_window", 8) or 8),
        "force_backend": str(runtime.get("force_backend", params.get("idp_force_backend", "auto")) or "auto").strip().lower(),
        "generic_nonbonded_enabled": bool(runtime.get("generic_nonbonded_enabled", params.get("idp_generic_nonbonded_enabled", False))),
        "generic_nonbonded_scale": float(runtime.get("generic_nonbonded_scale", params.get("idp_generic_nonbonded_scale", 0.05)) or 0.05),
        "generic_nonbonded_mode": str(generic_mode),
        "generic_nonbonded_replace_fraction": float(max(0.0, min(replace_fraction, 1.0))),
        "sigma": float(runtime.get("sigma", 3.8) or 3.8),
        "epsilon": float(runtime.get("epsilon", 0.03) or 0.03),
    }


def _merge_seq_window_neighbors(
    base_nb: Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    coords_batch: torch.Tensor,
    *,
    k: int,
    seq_window: int,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    nb_idx, _nb_dist, nb_mask = base_nb
    device = coords_batch.device
    B, N, _ = coords_batch.shape
    if int(seq_window) <= 0:
        safe_idx = nb_idx.clamp_min(0)
        batch_idx = torch.arange(B, device=device).view(B, 1, 1).expand_as(safe_idx)
        neigh = coords_batch[batch_idx, safe_idx]
        center = coords_batch.unsqueeze(2).expand_as(neigh)
        dist = torch.linalg.norm(center - neigh, dim=-1)
        mask = (nb_mask > 0) & (nb_idx >= 0)
        dist = torch.where(mask, dist, torch.zeros_like(dist))
        return nb_idx, dist.float(), mask.float()

    seq_offsets = torch.arange(-int(seq_window), int(seq_window) + 1, device=device, dtype=torch.long)
    seq_offsets = seq_offsets[seq_offsets != 0]
    if int(seq_offsets.numel()) == 0:
        return _merge_seq_window_neighbors(base_nb, coords_batch, k=k, seq_window=0)
    seq_idx = torch.arange(N, device=device, dtype=torch.long).view(1, N, 1) + seq_offsets.view(1, 1, -1)
    seq_valid = (seq_idx >= 0) & (seq_idx < N)
    seq_idx = seq_idx.clamp(0, max(N - 1, 0)).expand(B, -1, -1)
    seq_valid = seq_valid.expand(B, -1, -1)

    cand_idx = torch.cat([nb_idx, seq_idx], dim=-1)
    cand_valid = torch.cat([(nb_mask > 0) & (nb_idx >= 0), seq_valid], dim=-1)
    self_idx = torch.arange(N, device=device, dtype=torch.long).view(1, N, 1).expand_as(cand_idx)
    cand_valid = cand_valid & (cand_idx != self_idx)
    safe_idx = cand_idx.clamp_min(0)
    batch_idx = torch.arange(B, device=device).view(B, 1, 1).expand_as(safe_idx)
    neigh = coords_batch[batch_idx, safe_idx]
    center = coords_batch.unsqueeze(2).expand_as(neigh)
    dist = torch.linalg.norm(center - neigh, dim=-1)
    inf = torch.full_like(dist, float("inf"))
    dist = torch.where(cand_valid, dist, inf)
    k_eff = max(1, min(int(k), max(N - 1, 1)))
    topk_dist, topk_pos = torch.topk(dist, k=k_eff, largest=False, dim=-1)
    topk_idx = cand_idx.gather(-1, topk_pos)
    topk_mask = torch.isfinite(topk_dist)
    topk_dist = torch.where(topk_mask, topk_dist, torch.zeros_like(topk_dist))
    topk_idx = torch.where(topk_mask, topk_idx, torch.full_like(topk_idx, -1))
    return topk_idx.long(), topk_dist.float(), topk_mask.float()


def _merge_seq_window_neighbors_static(
    base_nb: Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    *,
    batch_size: int,
    n_atoms: int,
    device: torch.device,
    k: int,
    seq_window: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    nb_idx, _nb_dist, nb_mask = base_nb
    if int(seq_window) <= 0:
        return nb_idx.long(), ((nb_mask > 0) & (nb_idx >= 0)).float()

    seq_offsets = torch.arange(-int(seq_window), int(seq_window) + 1, device=device, dtype=torch.long)
    seq_offsets = seq_offsets[seq_offsets != 0]
    if int(seq_offsets.numel()) == 0:
        return nb_idx.long(), ((nb_mask > 0) & (nb_idx >= 0)).float()

    seq_idx = torch.arange(n_atoms, device=device, dtype=torch.long).view(1, n_atoms, 1) + seq_offsets.view(1, 1, -1)
    seq_valid = (seq_idx >= 0) & (seq_idx < n_atoms)
    seq_idx = seq_idx.clamp(0, max(n_atoms - 1, 0)).expand(batch_size, -1, -1)
    seq_valid = seq_valid.expand(batch_size, -1, -1)

    cand_idx = torch.cat([nb_idx, seq_idx], dim=-1)
    cand_valid = torch.cat([(nb_mask > 0) & (nb_idx >= 0), seq_valid], dim=-1)
    self_idx = torch.arange(n_atoms, device=device, dtype=torch.long).view(1, n_atoms, 1).expand_as(cand_idx)
    cand_valid = cand_valid & (cand_idx != self_idx)

    inf = torch.full(cand_valid.shape, float("inf"), dtype=torch.float32, device=device)
    priority = torch.where(cand_valid, torch.zeros_like(inf), inf)
    k_eff = max(1, min(int(k), max(n_atoms - 1, 1)))
    _topk_priority, topk_pos = torch.topk(priority, k=k_eff, largest=False, dim=-1)
    topk_idx = cand_idx.gather(-1, topk_pos)
    topk_mask = cand_valid.gather(-1, topk_pos)
    topk_idx = torch.where(topk_mask, topk_idx, torch.full_like(topk_idx, -1))
    return topk_idx.long(), topk_mask.float()


def _neighbor_dist_from_indices(
    coords_batch: torch.Tensor,
    nb_idx: torch.Tensor,
    nb_mask: torch.Tensor,
) -> torch.Tensor:
    safe_idx = nb_idx.clamp_min(0)
    batch_idx = torch.arange(coords_batch.shape[0], device=coords_batch.device).view(-1, 1, 1).expand_as(safe_idx)
    neigh = coords_batch[batch_idx, safe_idx]
    center = coords_batch.unsqueeze(2).expand_as(neigh)
    dist = torch.linalg.norm(center - neigh, dim=-1)
    mask = (nb_mask > 0) & (nb_idx >= 0)
    return torch.where(mask, dist, torch.zeros_like(dist)).float()


class IDPNeighborEngine:
    def __init__(self, *, coords0: torch.Tensor, top, k: int, params: Dict[str, Any]):
        self.device = coords0.device
        self.k = int(max(k, 1))
        self.settings = _neighbor_settings_from_params(params, self.k)
        if str(self.settings["force_backend"]) in {"auto", "rust_hip"}:
            os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        self.box_size = float(getattr(top, "box_size", torch.tensor([_infer_box_size(coords0)]))[0].item() if torch.is_tensor(getattr(top, "box_size", None)) else _infer_box_size(coords0))
        self.grid = GridSpatialHash(
            torch.tensor([self.box_size, self.box_size, self.box_size], dtype=torch.float32, device=self.device),
            float(self.settings["grid_spacing"]),
            self.device,
            cutoff=float(self.settings["cutoff"]),
            max_neighbors=int(self.settings["max_neighbors"]),
            skin=float(self.settings["skin"]),
            rebuild_stride=int(self.settings["rebuild_stride"]),
            max_atoms_per_cell=int(self.settings["max_atoms_per_cell"]),
            use_morton_presort=True,
        )
        self.rust_backend = RustHipBackend(device=self.device)
        self.use_rust_hip_builder = (
            str(self.settings["force_backend"]) in {"auto", "rust_hip"}
            and bool(getattr(self.rust_backend, "enabled", False))
            and getattr(self.rust_backend, "_neighbor_builder", None) is not None
        )
        self._base_nb_cache: Optional[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = None
        self._base_ref_coords: Optional[torch.Tensor] = None
        self._base_shape: Optional[Tuple[int, ...]] = None
        self._base_call_counter = 0
        self._base_last_displacement_check_call = -1
        self._base_generation = 0
        self._last_grid_rebuild_call = -1
        self._merged_generation = -1
        self._merged_static_nb: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        self.last_neighbor_generation = 0

    def reset(self) -> None:
        self.grid.reset_cache()
        self._base_nb_cache = None
        self._base_ref_coords = None
        self._base_shape = None
        self._base_call_counter = 0
        self._base_last_displacement_check_call = -1
        self._base_generation = 0
        self._last_grid_rebuild_call = -1
        self._merged_generation = -1
        self._merged_static_nb = None
        self.last_neighbor_generation = 0

    def _minimum_image(self, dr: torch.Tensor) -> torch.Tensor:
        box = torch.tensor([self.box_size, self.box_size, self.box_size], dtype=dr.dtype, device=dr.device)
        return dr - box * torch.floor(dr / box + 0.5)

    def _rust_base_needs_rebuild(self, coords_batch: torch.Tensor) -> bool:
        if self._base_nb_cache is None or self._base_ref_coords is None or self._base_shape is None:
            return True
        if tuple(coords_batch.shape) != tuple(self._base_shape):
            return True
        if coords_batch.device != self._base_ref_coords.device:
            return True
        skin = float(self.settings["skin"])
        if skin <= 0.0:
            return True
        if (self._base_call_counter - self._base_last_displacement_check_call) < int(self.settings["rebuild_stride"]):
            return False
        self._base_last_displacement_check_call = self._base_call_counter
        disp = self._minimum_image(coords_batch - self._base_ref_coords)
        max_disp = disp.norm(dim=-1).amax()
        return bool(max_disp.item() >= (0.5 * skin))

    def get_neighbor_data(self, coords_batch: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.use_rust_hip_builder:
            self._base_call_counter += 1
            if self._rust_base_needs_rebuild(coords_batch):
                try:
                    grid_dims = self.grid.grid_dims
                    base_nb = self.rust_backend.build_neighbor_list(
                        coords_batch.float().contiguous(),
                        box_size=float(self.box_size),
                        cutoff=float(self.grid.list_cutoff),
                        max_neighbors=int(self.settings["candidate_max_neighbors"]),
                        grid_dims=grid_dims,
                        max_atoms_per_cell=int(self.settings["max_atoms_per_cell"]),
                    )
                except Exception:
                    base_nb = self.grid.get_neighbor_data(coords_batch)
                self._base_nb_cache = base_nb
                self._base_ref_coords = coords_batch.detach().clone()
                self._base_shape = tuple(coords_batch.shape)
                self._base_last_displacement_check_call = self._base_call_counter
                self._base_generation += 1
            else:
                base_nb = self._base_nb_cache
        else:
            base_nb = self.grid.get_neighbor_data(coords_batch)
            grid_rebuild_call = int(getattr(self.grid, "_last_rebuild_call", -1))
            if grid_rebuild_call != self._last_grid_rebuild_call:
                self._last_grid_rebuild_call = grid_rebuild_call
                self._base_generation += 1

        if base_nb is None:
            return _merge_seq_window_neighbors(
                knn_nb_data(coords_batch, k=self.k),
                coords_batch,
                k=self.k,
                seq_window=int(self.settings["seq_window"]),
            )

        if self._merged_static_nb is None or self._merged_generation != self._base_generation:
            self._merged_static_nb = _merge_seq_window_neighbors_static(
                base_nb,
                batch_size=int(coords_batch.shape[0]),
                n_atoms=int(coords_batch.shape[1]),
                device=coords_batch.device,
                k=self.k,
                seq_window=int(self.settings["seq_window"]),
            )
            self._merged_generation = self._base_generation
        nb_idx, nb_mask = self._merged_static_nb
        nb_dist = _neighbor_dist_from_indices(coords_batch, nb_idx, nb_mask)
        self.last_neighbor_generation = int(self._merged_generation)
        return nb_idx, nb_dist, nb_mask

    def compute_generic_nonbonded(
        self,
        coords_batch: torch.Tensor,
        nb_data: Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    ) -> Tuple[Optional[torch.Tensor], float]:
        if not bool(self.settings["generic_nonbonded_enabled"]):
            return None, 0.0
        if not bool(getattr(self.rust_backend, "enabled", False)):
            return None, 0.0
        try:
            f_nb, _ = self.rust_backend.compute_nonbonded(
                coords_batch.float().contiguous(),
                nb_data,
                {
                    "box_size": float(self.box_size),
                    "sigma": float(self.settings["sigma"]),
                    "eps_solv": float(self.settings["epsilon"]),
                },
            )
            scale = float(self.settings["generic_nonbonded_scale"])
            return (scale * f_nb.to(device=coords_batch.device, dtype=coords_batch.dtype)), scale
        except Exception:
            return None, 0.0

    def generic_nonbonded_mode(self) -> str:
        return str(self.settings.get("generic_nonbonded_mode", "additive") or "additive")

    def generic_nonbonded_replace_fraction(self) -> float:
        return float(self.settings.get("generic_nonbonded_replace_fraction", 0.0) or 0.0)


def _combine_generic_nonbonded_force(
    force_main: torch.Tensor,
    force_nb: torch.Tensor,
    *,
    mode: str,
    replace_fraction: float,
) -> Tuple[torch.Tensor, str, float]:
    eff_mode = str(mode or "additive").strip().lower()
    eff_replace = float(max(0.0, min(float(replace_fraction), 1.0)))
    if eff_mode == "replace_partial" and eff_replace > 0.0:
        return ((1.0 - eff_replace) * force_main) + force_nb, eff_mode, eff_replace
    return force_main + force_nb, "additive", 0.0


def end_to_end(c: torch.Tensor) -> float:
    if int(c.shape[0]) < 2:
        return 0.0
    return float(torch.linalg.norm(c[-1] - c[0]).item())


def contact_persistence(traj: torch.Tensor, cutoff: float = 8.0) -> float:
    if int(traj.shape[1]) < 6:
        return 0.0
    frame_scores: List[float] = []
    for frame in traj:
        nb_idx, nb_dist, nb_mask = knn_nb_data(frame.unsqueeze(0), k=12)
        safe_idx = nb_idx.clamp_min(0)
        atom_i = torch.arange(frame.shape[0], device=traj.device, dtype=torch.long).view(1, -1, 1).expand_as(safe_idx)
        seq_gap = torch.abs(atom_i - safe_idx)
        valid = (nb_mask > 0.5) & (nb_idx >= 0) & (seq_gap >= 6)
        contacts = ((nb_dist < float(cutoff)) & valid).float()
        frame_scores.append(float(contacts.mean().item()))
    return float(sum(frame_scores) / max(len(frame_scores), 1))


def transient_helicity_proxy(traj: torch.Tensor) -> float:
    if int(traj.shape[1]) < 3:
        return 0.0
    prev = traj[:, :-2, :]
    curr = traj[:, 1:-1, :]
    nxt = traj[:, 2:, :]
    curvature = torch.linalg.norm(nxt - 2.0 * curr + prev, dim=-1)
    helix_like = torch.exp(-torch.square(curvature / 1.15))
    return float(helix_like.mean().item())


def ensemble_diversity(traj: torch.Tensor) -> float:
    if int(traj.shape[0]) <= 1:
        return 0.0
    mean_conf = traj.mean(dim=0, keepdim=True)
    rmsf = torch.sqrt(torch.mean(torch.square(traj - mean_conf), dim=(-1, -2)) + 1e-8)
    if int(traj.shape[0]) == 2:
        return float(rmsf.mean().item())
    lag = torch.sqrt(torch.mean(torch.square(traj[1:] - traj[:-1]), dim=(-1, -2)) + 1e-8)
    return float((0.6 * rmsf.mean() + 0.4 * lag.mean()).item())


def overcollapse_rate(traj: torch.Tensor, baseline_rg: float, ratio: float = 0.88) -> float:
    if int(traj.shape[0]) == 0:
        return 0.0
    rg_series = torch.tensor([float(calculate_rg(frame)) for frame in traj], dtype=torch.float32, device=traj.device)
    return float((rg_series < float(baseline_rg) * float(ratio)).float().mean().item())


def metrics_for_traj(traj: torch.Tensor, baseline_rg: float) -> Dict[str, float]:
    rg_vals = [float(calculate_rg(frame)) for frame in traj]
    sasa_vals = [float(calculate_sasa_proxy(frame)) for frame in traj]
    e2e_vals = [end_to_end(frame) for frame in traj]
    return {
        "rg_mean": float(sum(rg_vals) / max(len(rg_vals), 1)),
        "sasa_proxy_mean": float(sum(sasa_vals) / max(len(sasa_vals), 1)),
        "end_to_end_mean": float(sum(e2e_vals) / max(len(e2e_vals), 1)),
        "contact_persistence": contact_persistence(traj),
        "transient_helicity": transient_helicity_proxy(traj),
        "ensemble_diversity": ensemble_diversity(traj),
        "overcollapse_rate": overcollapse_rate(traj, baseline_rg=baseline_rg),
    }


def build_sim_params(enabled: bool, params: Dict[str, Any]) -> Dict[str, Any]:
    vh_backend = str(
        params.get("idp_virtual_hbond_backend", os.environ.get("IDP_VIRTUAL_HBOND_BACKEND", "python"))
        or "python"
    ).strip().lower()
    sticker_bridge_backend = str(
        params.get("idp_sticker_bridge_backend", os.environ.get("IDP_STICKER_BRIDGE_BACKEND", "python"))
        or "python"
    ).strip().lower()
    return {
        "idp_virtual_hbond_enabled": 1 if enabled else 0,
        "idp_3bead_enabled": 1 if enabled else 0,
        "idp_virtual_hbond_backend": vh_backend,
        "idp_sticker_bridge_backend": sticker_bridge_backend,
        "target_name": str(params.get("name", "")),
        "ionic_strength": float(params.get("ionic_strength", 0.15)),
        "pH": float(params.get("pH", 7.2)),
        "ptm_count": float(params.get("ptm_count", 0.0)),
        "hydro_strength": float(params.get("hydro_strength", 1.0)),
        "cooling_rate": float(params.get("cooling_rate", 0.0)),
        "idp_branch_profile": normalize_branch_profile(params.get("branch_profile")),
        "sequence_features": {k: float(v) for k, v in params.get("sequence_features", {}).items()},
        "idp_branch_force_policy": dict(params.get("idp_branch_force_policy", {}) or {}),
        "_llps_contact_memory": None,
    }


def _info_value_scalar(value: Any) -> float:
    if torch.is_tensor(value):
        flat = value.detach().float().reshape(-1)
        if int(flat.numel()) == 0:
            return 0.0
        return float(flat.mean().item())
    try:
        return float(value)
    except Exception:
        return 0.0


def _info_value_vector(value: Any, batch_size: int, *, device: torch.device) -> torch.Tensor:
    if torch.is_tensor(value):
        flat = value.detach().to(device=device, dtype=torch.float32).reshape(-1)
        if int(flat.numel()) == 0:
            return torch.zeros(batch_size, dtype=torch.float32, device=device)
        if int(flat.numel()) == batch_size:
            return flat
        if int(flat.numel()) == 1:
            return flat.repeat(batch_size)
        if int(flat.numel()) % batch_size == 0:
            return flat.view(batch_size, -1).mean(dim=1)
        return flat[:batch_size]
    return torch.full((batch_size,), _info_value_scalar(value), dtype=torch.float32, device=device)


def rollout_condition(
    coords0: torch.Tensor,
    top,
    enabled: bool,
    params: Dict[str, Any],
    steps: int,
    sample_stride: int,
    dt: float,
    thermal_noise: float,
    seed: int,
    progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    progress_phase: str = "",
    progress_target: str = "",
    progress_stride: int = 0,
    neighbor_engine: Optional[IDPNeighborEngine] = None,
    idp_mod: Optional[IDPLogic] = None,
    shared_noise_bank: Optional[torch.Tensor] = None,
) -> Dict[str, Any]:
    device = coords0.device
    mod = idp_mod if idp_mod is not None else IDPLogic(device).to(device)
    c = coords0.clone()
    baseline_rg = float(calculate_rg(c))
    traj_frames: List[torch.Tensor] = [c.clone()]
    infos: List[Dict[str, Any]] = []
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    if isinstance(shared_noise_bank, torch.Tensor) and tuple(shared_noise_bank.shape) == (max(int(steps), 1),) + tuple(c.shape):
        noise_bank = shared_noise_bank
    else:
        noise_bank = torch.randn((max(int(steps), 1),) + tuple(c.shape), generator=gen, dtype=torch.float32) * float(thermal_noise)
    sim_params = build_sim_params(enabled=enabled, params=params)
    stride = int(progress_stride) if int(progress_stride) > 0 else max(int(steps) // 20, 1)
    disabled_fast_path = not bool(enabled)
    engine = neighbor_engine
    if engine is None and not disabled_fast_path:
        engine = IDPNeighborEngine(coords0=coords0, top=top, k=int(params.get("knn_k", 12)), params=params)
    if engine is not None:
        engine.reset()
    with torch.inference_mode():
        for step in range(int(steps)):
            noise = noise_bank[step].to(device=device)
            if disabled_fast_path:
                c = c + noise
            else:
                nb_data = engine.get_neighbor_data(c.unsqueeze(0)) if engine is not None else knn_nb_data(c.unsqueeze(0), k=int(params.get("knn_k", 12)))
                if engine is not None:
                    sim_params["idp_neighbor_generation"] = int(engine.last_neighbor_generation)
                f, info = mod(c.unsqueeze(0), top=top, nb_data=nb_data, pe=None, sim_params=sim_params)
                if engine is not None:
                    f_nb, nb_scale = engine.compute_generic_nonbonded(c.unsqueeze(0), nb_data)
                    if isinstance(f_nb, torch.Tensor):
                        f, nb_mode, nb_replace = _combine_generic_nonbonded_force(
                            f,
                            f_nb,
                            mode=engine.generic_nonbonded_mode(),
                            replace_fraction=engine.generic_nonbonded_replace_fraction(),
                        )
                        info = dict(info)
                        info["generic_nonbonded_scale"] = float(nb_scale)
                        info["generic_nonbonded_mode"] = str(nb_mode)
                        info["generic_nonbonded_replace_fraction"] = float(nb_replace)
                        info["generic_nonbonded_force_mean"] = float(torch.linalg.norm(f_nb, dim=-1).mean().item())
                f = f.squeeze(0)
                c = c + float(dt) * f + noise
            if ((step + 1) % max(int(sample_stride), 1)) == 0:
                traj_frames.append(c.clone())
            if not disabled_fast_path:
                infos.append(info)
            if progress_hook is not None and (((step + 1) % stride) == 0 or (step + 1) == int(steps)):
                progress_hook(
                    {
                        "current_phase": str(progress_phase),
                        "current_target": str(progress_target),
                        "phase_step": int(step + 1),
                        "phase_total_steps": int(max(int(steps), 1)),
                        "phase_ratio": float((step + 1) / max(int(steps), 1)),
                    }
                )
    traj = torch.stack(traj_frames, dim=0)
    metrics = metrics_for_traj(traj, baseline_rg=baseline_rg)
    metrics.update(
        {
            "baseline_rg": float(baseline_rg),
            "mean_force": float(sum(_info_value_scalar(i.get("mean_fuzzy_force", 0.0)) for i in infos) / max(len(infos), 1)),
            "hbond_force_mean": float(sum(_info_value_scalar(i.get("hbond_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "sticker_force_mean": float(sum(_info_value_scalar(i.get("sticker_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "bridge_force_mean_component": float(sum(_info_value_scalar(i.get("bridge_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "helix_force_mean": float(sum(_info_value_scalar(i.get("helix_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "generic_nonbonded_force_mean": float(sum(_info_value_scalar(i.get("generic_nonbonded_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "generic_nonbonded_scale": float(sum(_info_value_scalar(i.get("generic_nonbonded_scale", 0.0)) for i in infos) / max(len(infos), 1)),
            "generic_nonbonded_mode": str((infos[-1].get("generic_nonbonded_mode", "additive") if infos else "additive")),
            "generic_nonbonded_replace_fraction": float(sum(_info_value_scalar(i.get("generic_nonbonded_replace_fraction", 0.0)) for i in infos) / max(len(infos), 1)),
            "virtual_hbond_contacts_mean": float(sum(_info_value_scalar(i.get("virtual_hbond_contacts", 0.0)) for i in infos) / max(len(infos), 1)),
            "virtual_hbond_mean_distance_A": float(sum(_info_value_scalar(i.get("virtual_hbond_mean_distance_A", 0.0)) for i in infos) / max(len(infos), 1)),
            "sticker_contacts_mean": float(sum(_info_value_scalar(i.get("sticker_contacts", 0.0)) for i in infos) / max(len(infos), 1)),
            "pi_pi_contacts_mean": float(sum(_info_value_scalar(i.get("pi_pi_contacts", 0.0)) for i in infos) / max(len(infos), 1)),
            "cation_pi_contacts_mean": float(sum(_info_value_scalar(i.get("cation_pi_contacts", 0.0)) for i in infos) / max(len(infos), 1)),
            "bridge_contacts_mean": float(sum(_info_value_scalar(i.get("bridge_contacts", 0.0)) for i in infos) / max(len(infos), 1)),
            "bridge_force_mean": float(sum(_info_value_scalar(i.get("bridge_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "llps_contact_memory_mean": float(sum(_info_value_scalar(i.get("llps_contact_memory_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "conditional_virtual_hbond_scale": float(sum(_info_value_scalar(i.get("conditional_virtual_hbond_scale", 1.0)) for i in infos) / max(len(infos), 1)),
            "conditional_contact_gain_scale": float(sum(_info_value_scalar(i.get("conditional_contact_gain_scale", 1.0)) for i in infos) / max(len(infos), 1)),
            "anti_collapse_force_mean": float(sum(_info_value_scalar(i.get("anti_collapse_force_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "anti_collapse_rg_target_A": float(sum(_info_value_scalar(i.get("anti_collapse_rg_target_A", 0.0)) for i in infos) / max(len(infos), 1)),
            "anti_collapse_density_mean": float(sum(_info_value_scalar(i.get("anti_collapse_density_mean", 0.0)) for i in infos) / max(len(infos), 1)),
            "anti_collapse_overcollapse_rate_force": float(sum(_info_value_scalar(i.get("anti_collapse_overcollapse_rate", 0.0)) for i in infos) / max(len(infos), 1)),
            "conditional_anti_collapse_scale": float(sum(_info_value_scalar(i.get("conditional_anti_collapse_scale", 1.0)) for i in infos) / max(len(infos), 1)),
            "three_bead_cb_mean_distance_A": float(sum(_info_value_scalar(i.get("three_bead_cb_mean_distance_A", 0.0)) for i in infos) / max(len(infos), 1)),
            "three_bead_sc_mean_distance_A": float(sum(_info_value_scalar(i.get("three_bead_sc_mean_distance_A", 0.0)) for i in infos) / max(len(infos), 1)),
            "vhbond_dynamic_ctx_ms": float(sum(_info_value_scalar(i.get("vhbond_dynamic_ctx_ms", 0.0)) for i in infos) / max(len(infos), 1)),
            "vhbond_rust_buffer_ms": float(sum(_info_value_scalar(i.get("vhbond_rust_buffer_ms", 0.0)) for i in infos) / max(len(infos), 1)),
            "vhbond_rust_kernel_ms": float(sum(_info_value_scalar(i.get("vhbond_rust_kernel_ms", 0.0)) for i in infos) / max(len(infos), 1)),
            "vhbond_rust_post_ms": float(sum(_info_value_scalar(i.get("vhbond_rust_post_ms", 0.0)) for i in infos) / max(len(infos), 1)),
            "vhbond_rust_launch_cpu_ms": float(sum(_info_value_scalar(i.get("vhbond_rust_launch_cpu_ms", 0.0)) for i in infos) / max(len(infos), 1)),
            "vhbond_total_ms": float(sum(_info_value_scalar(i.get("vhbond_total_ms", 0.0)) for i in infos) / max(len(infos), 1)),
        }
    )
    return metrics


def rollout_condition_bundle(
    coords0: torch.Tensor,
    top,
    enabled: bool,
    params_list: List[Dict[str, Any]],
    steps: int,
    sample_stride: int,
    dt: float,
    thermal_noise: float,
    seed: int,
    progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    progress_phase: str = "",
) -> List[Dict[str, Any]]:
    device = coords0.device
    if not params_list:
        return []
    if len(params_list) == 1:
        return [
            rollout_condition(
                coords0=coords0,
                top=top,
                enabled=enabled,
                params=params_list[0],
                steps=steps,
                sample_stride=sample_stride,
                dt=dt,
                thermal_noise=thermal_noise,
                seed=int(params_list[0].get("seed", seed) or seed),
                progress_hook=progress_hook,
                progress_phase=progress_phase,
                progress_target=str(params_list[0].get("name", "")),
            )
        ]

    mod = IDPLogic(device).to(device)
    engine = None
    if enabled:
        engine = IDPNeighborEngine(coords0=coords0, top=top, k=int(params_list[0].get("knn_k", 12)), params=params_list[0])
        engine.reset()

    batch_size = int(len(params_list))
    c = coords0.unsqueeze(0).expand(batch_size, -1, -1).clone()
    baseline_rg = torch.full((batch_size,), float(calculate_rg(coords0)), dtype=torch.float32, device=device)
    traj_frames: List[torch.Tensor] = [c.clone()]
    infos: List[Dict[str, Any]] = []
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    base_noise = torch.randn((max(int(steps), 1),) + tuple(coords0.shape), generator=gen, dtype=torch.float32) * float(thermal_noise)
    noise_bank = base_noise.unsqueeze(1).expand(-1, batch_size, -1, -1).contiguous()
    sim_params_list = [build_sim_params(enabled=enabled, params=params) for params in params_list]
    stride = max(int(steps) // 20, 1)

    with torch.inference_mode():
        for step in range(int(steps)):
            noise = noise_bank[step].to(device=device)
            if not bool(enabled):
                c = c + noise
            else:
                nb_data = engine.get_neighbor_data(c) if engine is not None else knn_nb_data(c, k=int(params_list[0].get("knn_k", 12)))
                if engine is not None:
                    for sim_params in sim_params_list:
                        sim_params["idp_neighbor_generation"] = int(engine.last_neighbor_generation)
                f, info = mod(c, top=top, nb_data=nb_data, pe=None, sim_params=sim_params_list)
                if engine is not None:
                    f_nb, nb_scale = engine.compute_generic_nonbonded(c, nb_data)
                    if isinstance(f_nb, torch.Tensor):
                        f, nb_mode, nb_replace = _combine_generic_nonbonded_force(
                            f,
                            f_nb,
                            mode=engine.generic_nonbonded_mode(),
                            replace_fraction=engine.generic_nonbonded_replace_fraction(),
                        )
                        info = dict(info)
                        info["generic_nonbonded_scale"] = torch.full((batch_size,), float(nb_scale), dtype=torch.float32, device=device)
                        info["generic_nonbonded_replace_fraction"] = torch.full((batch_size,), float(nb_replace), dtype=torch.float32, device=device)
                        info["generic_nonbonded_mode"] = [str(nb_mode)] * batch_size
                        info["generic_nonbonded_force_mean"] = torch.linalg.norm(f_nb, dim=-1).mean(dim=-1).to(dtype=torch.float32)
                c = c + float(dt) * f + noise
                infos.append(info)
            if ((step + 1) % max(int(sample_stride), 1)) == 0:
                traj_frames.append(c.clone())
            if progress_hook is not None and (((step + 1) % stride) == 0 or (step + 1) == int(steps)):
                progress_hook(
                    {
                        "current_phase": str(progress_phase),
                        "current_target": str(params_list[-1].get("name", "")),
                        "phase_step": int(step + 1),
                        "phase_total_steps": int(max(int(steps), 1)),
                        "phase_ratio": float((step + 1) / max(int(steps), 1)),
                        "bundle_ratio": float((step + 1) / max(int(steps), 1)),
                    }
                )

    traj = torch.stack(traj_frames, dim=0)
    out: List[Dict[str, Any]] = []
    metric_keys = (
        "mean_fuzzy_force",
        "hbond_force_mean",
        "sticker_force_mean",
        "helix_force_mean",
        "generic_nonbonded_force_mean",
        "generic_nonbonded_scale",
        "generic_nonbonded_replace_fraction",
        "virtual_hbond_contacts",
        "virtual_hbond_mean_distance_A",
        "sticker_contacts",
        "pi_pi_contacts",
        "cation_pi_contacts",
        "bridge_contacts",
        "bridge_force_mean",
        "llps_contact_memory_mean",
        "conditional_virtual_hbond_scale",
        "conditional_contact_gain_scale",
        "anti_collapse_force_mean",
        "anti_collapse_rg_target_A",
        "anti_collapse_density_mean",
        "anti_collapse_overcollapse_rate",
        "conditional_anti_collapse_scale",
        "three_bead_cb_mean_distance_A",
        "three_bead_sc_mean_distance_A",
        "vhbond_dynamic_ctx_ms",
        "vhbond_rust_buffer_ms",
        "vhbond_rust_kernel_ms",
        "vhbond_rust_post_ms",
        "vhbond_rust_launch_cpu_ms",
        "vhbond_total_ms",
    )
    per_step_vectors = {
        key: [_info_value_vector(step_info.get(key, 0.0), batch_size, device=device) for step_info in infos]
        for key in metric_keys
    }
    for batch_idx in range(batch_size):
        traj_b = traj[:, batch_idx]
        metrics = metrics_for_traj(traj_b, baseline_rg=float(baseline_rg[batch_idx].item()))
        metrics.update(
            {
                "baseline_rg": float(baseline_rg[batch_idx].item()),
                "mean_force": float(torch.stack(per_step_vectors["mean_fuzzy_force"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "hbond_force_mean": float(torch.stack(per_step_vectors["hbond_force_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "sticker_force_mean": float(torch.stack(per_step_vectors["sticker_force_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "helix_force_mean": float(torch.stack(per_step_vectors["helix_force_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "generic_nonbonded_force_mean": float(torch.stack(per_step_vectors["generic_nonbonded_force_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "generic_nonbonded_scale": float(torch.stack(per_step_vectors["generic_nonbonded_scale"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "generic_nonbonded_mode": str((infos[-1].get("generic_nonbonded_mode", ["additive"] * batch_size)[batch_idx] if infos else "additive")),
                "generic_nonbonded_replace_fraction": float(torch.stack(per_step_vectors["generic_nonbonded_replace_fraction"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "virtual_hbond_contacts_mean": float(torch.stack(per_step_vectors["virtual_hbond_contacts"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "virtual_hbond_mean_distance_A": float(torch.stack(per_step_vectors["virtual_hbond_mean_distance_A"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "sticker_contacts_mean": float(torch.stack(per_step_vectors["sticker_contacts"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "pi_pi_contacts_mean": float(torch.stack(per_step_vectors["pi_pi_contacts"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "cation_pi_contacts_mean": float(torch.stack(per_step_vectors["cation_pi_contacts"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "bridge_contacts_mean": float(torch.stack(per_step_vectors["bridge_contacts"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "bridge_force_mean": float(torch.stack(per_step_vectors["bridge_force_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "llps_contact_memory_mean": float(torch.stack(per_step_vectors["llps_contact_memory_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "conditional_virtual_hbond_scale": float(torch.stack(per_step_vectors["conditional_virtual_hbond_scale"]).mean(dim=0)[batch_idx].item()) if infos else 1.0,
                "conditional_contact_gain_scale": float(torch.stack(per_step_vectors["conditional_contact_gain_scale"]).mean(dim=0)[batch_idx].item()) if infos else 1.0,
                "anti_collapse_force_mean": float(torch.stack(per_step_vectors["anti_collapse_force_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "anti_collapse_rg_target_A": float(torch.stack(per_step_vectors["anti_collapse_rg_target_A"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "anti_collapse_density_mean": float(torch.stack(per_step_vectors["anti_collapse_density_mean"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "anti_collapse_overcollapse_rate_force": float(torch.stack(per_step_vectors["anti_collapse_overcollapse_rate"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "conditional_anti_collapse_scale": float(torch.stack(per_step_vectors["conditional_anti_collapse_scale"]).mean(dim=0)[batch_idx].item()) if infos else 1.0,
                "three_bead_cb_mean_distance_A": float(torch.stack(per_step_vectors["three_bead_cb_mean_distance_A"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "three_bead_sc_mean_distance_A": float(torch.stack(per_step_vectors["three_bead_sc_mean_distance_A"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "vhbond_dynamic_ctx_ms": float(torch.stack(per_step_vectors["vhbond_dynamic_ctx_ms"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "vhbond_rust_buffer_ms": float(torch.stack(per_step_vectors["vhbond_rust_buffer_ms"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "vhbond_rust_kernel_ms": float(torch.stack(per_step_vectors["vhbond_rust_kernel_ms"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "vhbond_rust_post_ms": float(torch.stack(per_step_vectors["vhbond_rust_post_ms"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "vhbond_rust_launch_cpu_ms": float(torch.stack(per_step_vectors["vhbond_rust_launch_cpu_ms"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
                "vhbond_total_ms": float(torch.stack(per_step_vectors["vhbond_total_ms"]).mean(dim=0)[batch_idx].item()) if infos else 0.0,
            }
        )
        out.append(metrics)
    return out


def load_target_coords(target_cfg: Dict[str, Any], device: torch.device) -> torch.Tensor:
    source = str(target_cfg.get("source", "synthetic")).strip().lower()
    if source == "pdb":
        pdb_path = os.path.abspath(str(target_cfg["pdb_path"]))
        records = _slice_records(_load_ca_records_from_pdb(pdb_path), target_cfg)
        coords = torch.tensor([r[1] for r in records], dtype=torch.float32, device=device)
        return coords
    return make_synthetic_idp_coords(
        n_res=int(target_cfg.get("n_res", 64)),
        seed=int(target_cfg.get("seed", 23)),
        device=device,
        noise_scale=float(target_cfg.get("noise_scale", 0.35)),
        collapse_bias=float(target_cfg.get("collapse_bias", 0.0)),
    )


def load_target_sequence_features(target_cfg: Dict[str, Any]) -> Dict[str, float]:
    source = str(target_cfg.get("source", "synthetic")).strip().lower()
    if source == "pdb":
        pdb_path = os.path.abspath(str(target_cfg["pdb_path"]))
        records = _slice_records(_load_ca_records_from_pdb(pdb_path), target_cfg)
        if not records:
            raise ValueError(f"no CA residue records found in pdb: {pdb_path}")
        resnames = [r[0] for r in records]
    else:
        n_res = max(int(target_cfg.get("n_res", 64)), 1)
        frac_gly = 0.08
        frac_pro = 0.06
        frac_charged = 0.22
        frac_aromatic = 0.08
        frac_polar = 0.24
        frac_hydrophobic = 0.32
        acidic_fraction = 0.11
        basic_fraction = 0.11
        charge_density = frac_charged
        charge_asymmetry = 0.0
        sticker_density = frac_aromatic + 0.15 * frac_hydrophobic
        spacer_density = min(1.0, frac_gly + frac_pro + frac_polar)
        return {
            "residue_count_log": float(math.log1p(n_res)),
            "frac_gly": frac_gly,
            "frac_pro": frac_pro,
            "frac_charged": frac_charged,
            "frac_aromatic": frac_aromatic,
            "frac_polar": frac_polar,
            "frac_hydrophobic": frac_hydrophobic,
            "net_charge_proxy": 0.0,
            "frac_disorder_promoting": 0.48,
            "charge_density": charge_density,
            "charge_asymmetry": charge_asymmetry,
            "kappa_proxy": 0.0,
            "sticker_density": sticker_density,
            "spacer_density": spacer_density,
            "sticker_spacer_ratio": _safe_div(sticker_density, spacer_density + 1e-6),
            "acidic_fraction": acidic_fraction,
            "basic_fraction": basic_fraction,
        }

    n = float(max(len(resnames), 1))
    pos = sum(1 for r in resnames if r in CHARGED_POS)
    neg = sum(1 for r in resnames if r in CHARGED_NEG)
    acidic_fraction = float(sum(1 for r in resnames if r in CHARGED_NEG) / n)
    basic_fraction = float(sum(1 for r in resnames if r in CHARGED_POS) / n)
    charges = []
    sticker_count = 0
    spacer_count = 0
    for r in resnames:
        q = 1 if r in CHARGED_POS else -1 if r in CHARGED_NEG else 0
        charges.append(q)
        if r in AROMATIC or r in {"ARG", "LYS", "MET", "LEU", "ILE", "VAL"}:
            sticker_count += 1
        if r in {"GLY", "SER", "THR", "GLN", "ASN", "PRO", "ASP", "GLU"}:
            spacer_count += 1
    charge_density = float(sum(abs(q) for q in charges) / n)
    charge_asymmetry = float(abs(pos - neg) / n)
    if charges:
        weighted = sum((((i + 1) / len(charges)) - 0.5) * q for i, q in enumerate(charges))
        kappa_proxy = float(abs(weighted) / max(sum(abs(q) for q in charges), 1))
    else:
        kappa_proxy = 0.0
    sticker_density = float(sticker_count / n)
    spacer_density = float(spacer_count / n)
    return {
        "residue_count_log": float(math.log1p(n)),
        "frac_gly": float(sum(1 for r in resnames if r == "GLY") / n),
        "frac_pro": float(sum(1 for r in resnames if r == "PRO") / n),
        "frac_charged": float(sum(1 for r in resnames if (r in CHARGED_POS or r in CHARGED_NEG)) / n),
        "frac_aromatic": float(sum(1 for r in resnames if r in AROMATIC) / n),
        "frac_polar": float(sum(1 for r in resnames if r in POLAR) / n),
        "frac_hydrophobic": float(sum(1 for r in resnames if r in HYDROPHOBIC) / n),
        "net_charge_proxy": float((pos - neg) / n),
        "frac_disorder_promoting": float(sum(1 for r in resnames if r in DISORDER_PROMOTING) / n),
        "charge_density": charge_density,
        "charge_asymmetry": charge_asymmetry,
        "kappa_proxy": kappa_proxy,
        "sticker_density": sticker_density,
        "spacer_density": spacer_density,
        "sticker_spacer_ratio": _safe_div(sticker_density, spacer_density + 1e-6),
        "acidic_fraction": acidic_fraction,
        "basic_fraction": basic_fraction,
    }
