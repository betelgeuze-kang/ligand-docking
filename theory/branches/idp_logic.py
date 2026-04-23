# theory/branches/idp_logic.py

from __future__ import annotations

import os
import time

import torch
import torch.nn as nn

from core.rust_hip_backend import RustHipBackend


RES_ARG = 1
RES_ASN = 2
RES_ASP = 3
RES_CYS = 4
RES_GLN = 5
RES_GLU = 6
RES_GLY = 7
RES_HIS = 8
RES_ILE = 9
RES_LEU = 10
RES_LYS = 11
RES_MET = 12
RES_PHE = 13
RES_PRO = 14
RES_SER = 15
RES_THR = 16
RES_TRP = 17
RES_TYR = 18
RES_VAL = 19

AROMATIC_IDS = (RES_HIS, RES_PHE, RES_TRP, RES_TYR)
CATIONIC_IDS = (RES_ARG, RES_LYS, RES_HIS)
POLAR_IDS = (RES_ASN, RES_CYS, RES_GLN, RES_HIS, RES_SER, RES_THR, RES_TYR)
DISORDER_IDS = (0, RES_ARG, RES_ASN, RES_ASP, RES_GLN, RES_GLU, RES_GLY, RES_HIS, RES_LYS, RES_PRO, RES_SER, RES_THR)
HYDROPHOBIC_IDS = (RES_ILE, RES_LEU, RES_MET, RES_PHE, RES_TRP, RES_TYR, RES_VAL)
STICKER_IDS = (RES_ARG, RES_LYS, RES_MET, RES_PHE, RES_TRP, RES_TYR, RES_ILE, RES_LEU, RES_VAL)


def _safe_normalize(v: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    return v / torch.linalg.norm(v, dim=-1, keepdim=True).clamp_min(eps)


def _norm_branch_profile(profile: dict | None) -> dict[str, float]:
    names = ("llps_lcd", "aggregation_prone", "helix_tad")
    raw = {name: float((profile or {}).get(name, 0.0) or 0.0) for name in names}
    total = sum(max(v, 0.0) for v in raw.values())
    if total <= 0.0:
        return {name: 1.0 / len(names) for name in names}
    return {name: max(raw[name], 0.0) / total for name in names}


def _env_enabled(name: str, default: str = "0") -> bool:
    raw = str(os.environ.get(name, default) or default).strip().lower()
    return raw not in {"", "0", "false", "off", "no"}


def _pairwise_contact_diagnostics_enabled() -> bool:
    return _env_enabled("IDP_PAIRWISE_CONTACT_DIAGNOSTICS", "0")


def _mask_from_ids(residue_types: torch.Tensor, ids: tuple[int, ...]) -> torch.Tensor:
    mask = torch.zeros_like(residue_types, dtype=torch.bool)
    for resid in ids:
        mask = mask | (residue_types == resid)
    return mask


class IDPLogic(nn.Module):
    """
    Experimental IDP adapter for a future 3-bead track.

    Default behavior is strictly zero-output. The force path activates only when
    `sim_params["idp_virtual_hbond_enabled"]` is truthy, so current production
    HTVS / folded-protein runs are unaffected.
    """

    always_zero_output = False

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self._rust_backend: RustHipBackend | None = None
        self._hbond_static_cache: dict[str, object] | None = None
        self.cb_offset_A = nn.Parameter(torch.tensor(1.52, device=dev))
        self.sc_offset_A = nn.Parameter(torch.tensor(2.05, device=dev))
        self.virtual_site_offset_A = nn.Parameter(torch.tensor(1.55, device=dev))
        self.virtual_hbond_strength = nn.Parameter(torch.tensor(0.18, device=dev))
        self.transient_helix_strength = nn.Parameter(torch.tensor(0.08, device=dev))
        self.coil_expansion_strength = nn.Parameter(torch.tensor(0.05, device=dev))
        self.unsat_penalty_strength = nn.Parameter(torch.tensor(0.04, device=dev))
        self.anti_collapse_strength = nn.Parameter(torch.tensor(0.09, device=dev))
        self.local_density_strength = nn.Parameter(torch.tensor(0.06, device=dev))
        self.rg_target_scale = nn.Parameter(torch.tensor(2.05, device=dev))
        self.density_cutoff_A = nn.Parameter(torch.tensor(7.2, device=dev))
        self.anti_spread_strength = nn.Parameter(torch.tensor(0.07, device=dev))
        self.sticker_strength = nn.Parameter(torch.tensor(0.11, device=dev))
        self.bridge_strength = nn.Parameter(torch.tensor(0.28, device=dev))

    def _enabled(self, sim_params) -> bool:
        if isinstance(sim_params, (list, tuple)):
            return any(self._enabled(item) for item in sim_params)
        if not isinstance(sim_params, dict):
            return False
        raw = sim_params.get("idp_3bead_enabled", sim_params.get("idp_virtual_hbond_enabled", 0))
        if torch.is_tensor(raw):
            return bool(raw.detach().float().mean().item() > 0.5)
        try:
            return bool(float(raw) > 0.5)
        except Exception:
            return bool(raw)

    def _sim_params_list(self, sim_params, batch_size: int) -> list[dict]:
        if isinstance(sim_params, (list, tuple)):
            items = [dict(item or {}) if isinstance(item, dict) else {} for item in sim_params]
            if len(items) == batch_size:
                return items
            if len(items) == 1:
                return items * batch_size
            raise ValueError(f"sim_params batch mismatch: got {len(items)}, expected {batch_size}")
        if isinstance(sim_params, dict):
            return [dict(sim_params) for _ in range(batch_size)]
        return [{} for _ in range(batch_size)]

    def _residue_types(self, c: torch.Tensor, top) -> torch.Tensor:
        bsz, n_atoms, _ = c.shape
        rt = getattr(top, "residue_types", None)
        if isinstance(rt, torch.Tensor):
            if rt.dim() == 1:
                rt = rt.unsqueeze(0).expand(bsz, -1)
            elif rt.dim() == 2 and rt.shape[0] == 1 and bsz > 1:
                rt = rt.expand(bsz, -1)
            return rt.to(device=c.device, dtype=torch.long)
        return torch.zeros((bsz, n_atoms), dtype=torch.long, device=c.device)

    def _local_frame(self, c: torch.Tensor) -> torch.Tensor:
        bsz, n_atoms, _ = c.shape
        prev = torch.cat([c[:, :1, :], c[:, :-1, :]], dim=1)
        nxt = torch.cat([c[:, 1:, :], c[:, -1:, :]], dim=1)
        tangent = _safe_normalize(nxt - prev)
        return tangent.view(bsz, n_atoms, 3)

    def _orthonormal_frame(self, c: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        tangent = self._local_frame(c)
        prev_tangent = torch.cat([tangent[:, :1, :], tangent[:, :-1, :]], dim=1)
        curvature = tangent - prev_tangent
        proj = (curvature * tangent).sum(dim=-1, keepdim=True) * tangent
        normal = curvature - proj
        fallback_axis = torch.zeros_like(normal)
        fallback_axis[..., 2] = 1.0
        fallback_axis = fallback_axis - (fallback_axis * tangent).sum(dim=-1, keepdim=True) * tangent
        fallback_mask = torch.linalg.norm(normal, dim=-1, keepdim=True) < 1e-5
        normal = torch.where(fallback_mask, fallback_axis, normal)
        normal = _safe_normalize(normal)
        binormal = _safe_normalize(torch.cross(tangent, normal, dim=-1))
        return tangent, normal, binormal

    def _three_bead_sites(self, c: torch.Tensor, residue_types: torch.Tensor):
        tangent, normal, binormal = self._orthonormal_frame(c)
        cb_offset = torch.clamp(self.cb_offset_A, min=0.8, max=2.4).to(dtype=c.dtype)
        sc_offset = torch.clamp(self.sc_offset_A, min=1.2, max=3.2).to(dtype=c.dtype)
        polar = _mask_from_ids(residue_types, POLAR_IDS).to(dtype=c.dtype, device=c.device)
        aromatic = _mask_from_ids(residue_types, AROMATIC_IDS).to(dtype=c.dtype, device=c.device)
        cb_dir = _safe_normalize(0.75 * tangent + 0.45 * binormal + 0.15 * normal)
        sc_dir = _safe_normalize((0.55 + 0.25 * polar).unsqueeze(-1) * normal + (0.25 + 0.15 * aromatic).unsqueeze(-1) * tangent + 0.35 * binormal)
        ca = c
        cb = c + cb_offset * cb_dir
        sc = c + sc_offset * sc_dir
        info = {
            "three_bead_cb_mean_distance_A": torch.linalg.norm(cb - ca, dim=-1).mean(dim=-1),
            "three_bead_sc_mean_distance_A": torch.linalg.norm(sc - ca, dim=-1).mean(dim=-1),
        }
        return ca, cb, sc, tangent, normal, binormal, info

    def _virtual_sites(self, c: torch.Tensor, tangent: torch.Tensor):
        offset = torch.clamp(self.virtual_site_offset_A, min=0.8, max=2.4).to(dtype=c.dtype)
        donor = c + offset * tangent
        acceptor = c - offset * tangent
        return donor, acceptor

    def _disorder_profile(self, residue_types: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
        disordered = _mask_from_ids(residue_types, DISORDER_IDS)
        return disordered.to(dtype=c.dtype, device=c.device)

    def _prepare_step_ctx(self, c: torch.Tensor, top, nb_data, sim_params) -> dict[str, torch.Tensor | float | dict]:
        residue_types = self._residue_types(c, top)
        disorder = self._disorder_profile(residue_types, c)
        env_scale = self._environment_scale(sim_params, c)
        cond = self._conditional_scales(sim_params, c)
        ca, cb, sc, tangent, normal, binormal, bead_info = self._three_bead_sites(c, residue_types)
        offset = torch.clamp(self.virtual_site_offset_A, min=0.8, max=2.4).to(dtype=c.dtype)
        donor = sc + offset * _safe_normalize(sc - ca + 0.35 * tangent + 0.15 * normal)
        acceptor = cb - offset * _safe_normalize(cb - ca - 0.25 * tangent + 0.10 * normal)
        ctx = {
            "residue_types": residue_types,
            "disorder": disorder,
            "env_scale": env_scale,
            "cond": cond,
            "ca": ca,
            "cb": cb,
            "sc": sc,
            "tangent": tangent,
            "normal": normal,
            "binormal": binormal,
            "donor": donor,
            "acceptor": acceptor,
            "bead_info": bead_info,
            "aromatic_mask": _mask_from_ids(residue_types, AROMATIC_IDS),
            "cationic_mask": _mask_from_ids(residue_types, CATIONIC_IDS),
            "sticker_mask": _mask_from_ids(residue_types, STICKER_IDS),
            "virtual_hbond_backend": self._virtual_hbond_backend(sim_params),
            "virtual_hbond_density_backend": self._virtual_hbond_density_backend(sim_params),
            "sticker_bridge_backend": self._sticker_bridge_backend(sim_params),
            "neighbor_generation": self._neighbor_generation(sim_params),
            "virtual_hbond_strength_relu": torch.relu(self.virtual_hbond_strength).to(dtype=c.dtype),
            "unsat_penalty_strength_relu": torch.relu(self.unsat_penalty_strength).to(dtype=c.dtype),
            "sticker_strength_relu": torch.relu(self.sticker_strength).to(dtype=c.dtype),
            "bridge_strength_relu": torch.relu(self.bridge_strength).to(dtype=c.dtype),
        }
        ctx["arg_fraction_flat"] = (residue_types == RES_ARG).float().mean(dim=1).to(dtype=c.dtype)
        ctx["aromatic_fraction_flat"] = (
            ((residue_types == RES_PHE) | (residue_types == RES_TYR) | (residue_types == RES_TRP)).float().mean(dim=1).to(dtype=c.dtype)
        )
        exposure_gain_scale = self._hbond_exposure_gain_scale(ca, cond)
        ctx["hbond_exposure_gain_scale"] = exposure_gain_scale
        ctx["hbond_exposure_gain_scale_flat"] = exposure_gain_scale.view(-1)
        fastpath_mode = self._pairwise_fastpath_mode(sim_params)
        ctx["pairwise_fastpath_mode"] = fastpath_mode
        if fastpath_mode == "hbond":
            if str(ctx["virtual_hbond_backend"]).strip().lower() in {"rust_hip", "rust", "hip"}:
                hbond_pair_ctx = self._prepare_hbond_pairwise_rust_ctx(c, nb_data, ctx)
                if hbond_pair_ctx is not None:
                    ctx["hbond_pairwise_rust_ctx"] = hbond_pair_ctx
            else:
                hbond_pair_ctx = self._prepare_hbond_pairwise_ctx(c, nb_data, ctx)
                if hbond_pair_ctx is not None:
                    ctx["hbond_pairwise_ctx"] = hbond_pair_ctx
        elif fastpath_mode != "none":
            pair_ctx = self._prepare_pairwise_ctx(c, nb_data, ctx)
            if pair_ctx is not None:
                ctx["pairwise_ctx"] = pair_ctx
        return ctx

    def _hbond_exposure_gain_scale(self, ca: torch.Tensor, cond: dict[str, torch.Tensor | list[str]]) -> torch.Tensor:
        bsz, n_atoms, _ = ca.shape
        dtype = ca.dtype
        device = ca.device
        scale = torch.ones((bsz, 1, 1), dtype=dtype, device=device)
        if not (
            _env_enabled("IDP_R11_PHYS_PATCH")
            or _env_enabled("IDP_R12_PHYS_PATCH")
            or _env_enabled("IDP_R13_PHYS_PATCH")
            or _env_enabled("IDP_R14_PHYS_PATCH")
            or _env_enabled("IDP_R17_PHYS_PATCH")
        ):
            return scale

        llps_branch = cond["llps_branch"]
        agg_branch = cond["agg_branch"]
        is_alpha = cond["is_alpha_target"]
        is_llps_target = cond["is_llps_target"]
        anti_spread_scale = cond["anti_spread_scale"]
        rg = torch.sqrt(
            torch.mean(
                torch.sum(torch.square(ca - ca.mean(dim=1, keepdim=True)), dim=-1),
                dim=1,
                keepdim=True,
            )
        ).unsqueeze(-1)
        n_scale = torch.tensor(float(max(n_atoms, 2)) ** 0.58, dtype=dtype, device=device)
        target_rg = torch.relu(self.rg_target_scale).to(dtype=dtype) * n_scale
        if _env_enabled("IDP_R17_PHYS_PATCH"):
            spread_ref_llps = (0.955 - 0.015 * torch.clamp(llps_branch, max=1.0)) * target_rg
            overspread_llps = torch.relu((rg - spread_ref_llps) / target_rg.clamp_min(1e-6))
            spread_gain_llps = 1.0 + (1.18 * anti_spread_scale) * overspread_llps
            spread_gain_llps = torch.clamp(spread_gain_llps, min=0.40, max=2.95)
            spread_ref_agg = torch.where(is_alpha > 0.5, 0.985 * target_rg, (0.975 - 0.03 * agg_branch) * target_rg)
            overspread_agg = torch.relu((rg - spread_ref_agg) / target_rg.clamp_min(1e-6))
            gain_mult_agg = torch.where(is_alpha > 0.5, 0.82 * anti_spread_scale, 1.35 * anti_spread_scale)
            spread_gain_agg = 1.0 + gain_mult_agg * overspread_agg
            spread_gain_agg = torch.where((is_alpha <= 0.5) & (agg_branch >= 0.50), spread_gain_agg * 1.10, spread_gain_agg)
            spread_gain_agg = torch.where(
                is_alpha > 0.5,
                torch.clamp(spread_gain_agg, min=0.35, max=2.15),
                torch.clamp(spread_gain_agg, min=0.35, max=2.80),
            )
            return torch.where(is_llps_target > 0.5, spread_gain_llps, spread_gain_agg)
        if _env_enabled("IDP_R14_PHYS_PATCH"):
            spread_ref = torch.where(is_alpha > 0.5, 0.985 * target_rg, (0.975 - 0.03 * agg_branch) * target_rg)
            overspread = torch.relu((rg - spread_ref) / target_rg.clamp_min(1e-6))
            gain_mult = torch.where(is_alpha > 0.5, 0.82 * anti_spread_scale, 1.35 * anti_spread_scale)
            scale = 1.0 + gain_mult * overspread
            scale = torch.where((is_alpha <= 0.5) & (agg_branch >= 0.50), scale * 1.10, scale)
            return torch.where(
                is_alpha > 0.5,
                torch.clamp(scale, min=0.35, max=2.15),
                torch.clamp(scale, min=0.35, max=2.80),
            )
        if _env_enabled("IDP_R13_PHYS_PATCH"):
            spread_ref = torch.where(is_alpha > 0.5, 1.00 * target_rg, (0.98 - 0.04 * agg_branch) * target_rg)
            overspread = torch.relu((rg - spread_ref) / target_rg.clamp_min(1e-6))
            gain_mult = torch.where(is_alpha > 0.5, 0.95 * anti_spread_scale, 1.55 * anti_spread_scale)
            scale = 1.0 + gain_mult * overspread
            scale = torch.where((is_alpha <= 0.5) & (agg_branch >= 0.50), scale * 1.18, scale)
            return torch.where(
                is_alpha > 0.5,
                torch.clamp(scale, min=0.35, max=2.35),
                torch.clamp(scale, min=0.35, max=3.10),
            )
        if _env_enabled("IDP_R12_PHYS_PATCH"):
            spread_ref = (0.98 - 0.04 * agg_branch) * target_rg
            overspread = torch.relu((rg - spread_ref) / target_rg.clamp_min(1e-6))
            scale = 1.0 + (1.55 * anti_spread_scale) * overspread
            scale = torch.where(agg_branch >= 0.50, scale * 1.18, scale)
            return torch.clamp(scale, min=0.35, max=3.10)
        overspread = torch.relu((rg - 1.02 * target_rg) / target_rg.clamp_min(1e-6))
        scale = 1.0 + anti_spread_scale * overspread
        return torch.clamp(scale, min=0.35, max=2.20)

    def _get_rust_backend(self, device: torch.device) -> RustHipBackend:
        if self._rust_backend is None:
            self._rust_backend = RustHipBackend(device=device)
        return self._rust_backend

    def _pairwise_fastpath_mode(self, sim_params) -> str:
        mode = ""
        if isinstance(sim_params, (list, tuple)):
            for item in sim_params:
                if isinstance(item, dict):
                    raw = str(item.get("idp_pairwise_fastpath_mode", "") or "").strip().lower()
                    if raw:
                        mode = raw
                        break
        elif isinstance(sim_params, dict):
            mode = str(sim_params.get("idp_pairwise_fastpath_mode", "") or "").strip().lower()
        if not mode:
            mode = os.environ.get("IDP_PAIRWISE_FASTPATH_MODE", "").strip().lower()
        if mode in {"", "0", "false", "off", "none"}:
            return "none"
        if mode in {"hbond", "virtual_hbond"}:
            return "hbond"
        if mode in {"hbond_sticker", "virtual_hbond_sticker"}:
            return "hbond_sticker"
        if mode in {"all", "hbond_sticker_bridge", "virtual_hbond_sticker_bridge"}:
            return "all"
        return "none"

    def _virtual_hbond_backend(self, sim_params) -> str:
        mode = ""
        if isinstance(sim_params, (list, tuple)):
            for item in sim_params:
                if isinstance(item, dict):
                    raw = str(item.get("idp_virtual_hbond_backend", "") or "").strip().lower()
                    if raw:
                        mode = raw
                        break
        elif isinstance(sim_params, dict):
            mode = str(sim_params.get("idp_virtual_hbond_backend", "") or "").strip().lower()
        if not mode:
            mode = os.environ.get("IDP_VIRTUAL_HBOND_BACKEND", "").strip().lower()
        if mode in {"", "0", "false", "off", "none"}:
            return "python"
        return mode

    def _virtual_hbond_density_backend(self, sim_params) -> str:
        mode = ""
        if isinstance(sim_params, (list, tuple)):
            for item in sim_params:
                if isinstance(item, dict):
                    raw = str(item.get("idp_virtual_hbond_density_backend", "") or "").strip().lower()
                    if raw:
                        mode = raw
                        break
        elif isinstance(sim_params, dict):
            mode = str(sim_params.get("idp_virtual_hbond_density_backend", "") or "").strip().lower()
        if not mode:
            mode = os.environ.get("IDP_VIRTUAL_HBOND_DENSITY_BACKEND", "").strip().lower()
        if mode in {"", "0", "false", "off", "none"}:
            return "python"
        return mode

    def _sticker_bridge_backend(self, sim_params) -> str:
        mode = ""
        if isinstance(sim_params, (list, tuple)):
            for item in sim_params:
                if isinstance(item, dict):
                    raw = str(item.get("idp_sticker_bridge_backend", "") or "").strip().lower()
                    if raw:
                        mode = raw
                        break
        elif isinstance(sim_params, dict):
            mode = str(sim_params.get("idp_sticker_bridge_backend", "") or "").strip().lower()
        if not mode:
            mode = os.environ.get("IDP_STICKER_BRIDGE_BACKEND", "").strip().lower()
        if mode in {"", "0", "false", "off", "none"}:
            return "python"
        return mode

    def _neighbor_generation(self, sim_params) -> int | None:
        if isinstance(sim_params, (list, tuple)):
            for item in sim_params:
                if isinstance(item, dict) and "idp_neighbor_generation" in item:
                    try:
                        return int(item.get("idp_neighbor_generation"))
                    except Exception:
                        return None
            return None
        if isinstance(sim_params, dict) and "idp_neighbor_generation" in sim_params:
            try:
                return int(sim_params.get("idp_neighbor_generation"))
            except Exception:
                return None
        return None

    def _fastpath_enabled_for(self, ctx: dict, term: str) -> bool:
        mode = str(ctx.get("pairwise_fastpath_mode", "none"))
        if mode == "all":
            return True
        if mode == "hbond_sticker":
            return term in {"hbond", "sticker"}
        if mode == "hbond":
            return term == "hbond"
        return False

    def _neighbor_pair_meta(self, c: torch.Tensor, nb_data, min_gap: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        nb_idx, nb_dist, nb_mask = nb_data
        bsz, n_atoms, _ = c.shape
        safe_idx = nb_idx.clamp_min(0).long()
        batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
        atom_i = torch.arange(n_atoms, device=c.device, dtype=torch.long).view(1, n_atoms, 1).expand_as(safe_idx)
        seq_gap = torch.abs(atom_i - safe_idx)
        valid = (nb_mask > 0.5) & (nb_idx >= 0) & (seq_gap >= int(min_gap))
        return safe_idx, batch_idx, valid

    def _prepare_pairwise_ctx(self, c: torch.Tensor, nb_data, ctx: dict) -> dict | None:
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return None
        nb_idx, nb_dist, nb_mask = nb_data
        if nb_idx.numel() == 0:
            return None
        bsz, n_atoms, _ = c.shape
        safe_idx = nb_idx.clamp_min(0).long()
        batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
        atom_i = torch.arange(n_atoms, device=c.device, dtype=torch.long).view(1, n_atoms, 1).expand_as(safe_idx)
        seq_gap = torch.abs(atom_i - safe_idx)
        valid3 = (nb_mask > 0.5) & (nb_idx >= 0) & (seq_gap >= 3)
        valid4 = (nb_mask > 0.5) & (nb_idx >= 0) & (seq_gap >= 4)

        ca = ctx["ca"]
        cb = ctx["cb"]
        sc = ctx["sc"]
        tangent = ctx["tangent"]
        normal = ctx["normal"]
        disorder = ctx["disorder"]
        aromatic = ctx["aromatic_mask"]
        cationic = ctx["cationic_mask"]
        sticker = ctx["sticker_mask"]
        donor = ctx["donor"]
        acceptor = ctx["acceptor"]

        ca_j = ca[batch_idx, safe_idx]
        ca_i = ca.unsqueeze(2).expand_as(ca_j)
        cb_j = cb[batch_idx, safe_idx]
        cb_i = cb.unsqueeze(2).expand_as(cb_j)
        sc_j = sc[batch_idx, safe_idx]
        sc_i = sc.unsqueeze(2).expand_as(sc_j)
        disorder_j = disorder[batch_idx, safe_idx]

        donor_j = donor[batch_idx, safe_idx]
        donor_i = donor.unsqueeze(2).expand_as(donor_j)
        acceptor_j = acceptor[batch_idx, safe_idx]
        acceptor_i = acceptor.unsqueeze(2).expand_as(acceptor_j)

        aro_i = aromatic.unsqueeze(2).expand_as(valid3)
        aro_j = aromatic[batch_idx, safe_idx]
        cat_i = cationic.unsqueeze(2).expand_as(valid3)
        cat_j = cationic[batch_idx, safe_idx]
        st_i = sticker.unsqueeze(2).expand_as(valid3)
        st_j = sticker[batch_idx, safe_idx]

        d_sc = torch.linalg.norm(sc_i - sc_j, dim=-1).clamp_min(1e-6)
        d_ca = torch.linalg.norm(ca_i - ca_j, dim=-1).clamp_min(1e-6)
        local_density3 = ((nb_dist < 8.0) & valid3).float().sum(dim=-1)
        exposure_local3 = 1.0 / (1.0 + 0.12 * local_density3)
        exposure_pair3 = exposure_local3.unsqueeze(2) * exposure_local3[batch_idx, safe_idx]
        local_density4 = ((nb_dist < 8.0) & valid4).float().sum(dim=-1)
        exposure_local4 = 1.0 / (1.0 + 0.10 * local_density4)
        exposure_pair4 = exposure_local4.unsqueeze(2) * exposure_local4[batch_idx, safe_idx]
        return {
            "safe_idx": safe_idx,
            "batch_idx": batch_idx,
            "valid3": valid3,
            "valid4": valid4,
            "nb_dist": nb_dist,
            "ca_i": ca_i,
            "ca_j": ca_j,
            "cb_i": cb_i,
            "cb_j": cb_j,
            "sc_i": sc_i,
            "sc_j": sc_j,
            "donor_i": donor_i,
            "donor_j": donor_j,
            "acceptor_i": acceptor_i,
            "acceptor_j": acceptor_j,
            "disorder_j": disorder_j,
            "aro_i": aro_i,
            "aro_j": aro_j,
            "cat_i": cat_i,
            "cat_j": cat_j,
            "st_i": st_i,
            "st_j": st_j,
            "d_sc": d_sc,
            "d_ca": d_ca,
            "local_density3": local_density3,
            "exposure_pair3": exposure_pair3,
            "exposure_pair4": exposure_pair4,
        }

    def _prepare_hbond_pairwise_ctx(self, c: torch.Tensor, nb_data, ctx: dict) -> dict | None:
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return None
        nb_idx, nb_dist, nb_mask = nb_data[:3]
        if nb_idx.numel() == 0:
            return None
        static_ctx = self._prepare_hbond_pairwise_static_ctx(c, nb_data, ctx)
        return self._prepare_hbond_pairwise_dynamic_ctx(c, nb_data, ctx, static_ctx)

    def _prepare_hbond_pairwise_rust_ctx(self, c: torch.Tensor, nb_data, ctx: dict) -> dict | None:
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return None
        _nb_idx, nb_dist, _nb_mask = nb_data[:3]
        if nb_dist.numel() == 0:
            return None
        # Rust virtual_hbond now computes local-density on the same stream inside
        # the backend launch, so the Python side only needs the static neighbor
        # metadata for sequence masks and cached indexing.
        return self._prepare_hbond_pairwise_static_ctx(c, nb_data, ctx)

    def _prepare_hbond_pairwise_static_ctx(self, c: torch.Tensor, nb_data, ctx: dict) -> dict:
        nb_idx, _nb_dist, nb_mask = nb_data[:3]
        generation = ctx.get("neighbor_generation")
        # Tie the cache to both the reported neighbor generation and the actual
        # tensor storage identity. Generation alone is not enough because new
        # rollouts can restart from the same generation id while using a
        # different neighbor list tensor.
        cache_generation = int(generation) if generation is not None else -1
        tensor_identity = (int(nb_idx.data_ptr()), int(nb_mask.data_ptr()))
        cache_key = (
            cache_generation,
            tuple(nb_idx.shape),
            nb_idx.device.type,
            int(c.shape[0]),
            int(c.shape[1]),
            tensor_identity,
        )
        cached = self._hbond_static_cache
        if isinstance(cached, dict) and cached.get("key") == cache_key and isinstance(cached.get("ctx"), dict):
            return cached["ctx"]  # type: ignore[return-value]

        bsz, n_atoms, _ = c.shape
        safe_idx = nb_idx.clamp_min(0).long()
        batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
        atom_i = torch.arange(n_atoms, device=c.device, dtype=torch.long).view(1, n_atoms, 1).expand_as(safe_idx)
        seq_gap = torch.abs(atom_i - safe_idx)
        valid3 = (nb_mask > 0.5) & (nb_idx >= 0) & (seq_gap >= 3)
        disorder = ctx["disorder"]
        aromatic = ctx["aromatic_mask"]
        cationic = ctx["cationic_mask"]
        sticker = ctx["sticker_mask"]

        static_ctx = {
            "safe_idx": safe_idx,
            "batch_idx": batch_idx,
            "valid3": valid3,
            "disorder_j": disorder[batch_idx, safe_idx],
            "aro_i": aromatic.unsqueeze(2).expand_as(valid3),
            "aro_j": aromatic[batch_idx, safe_idx],
            "cat_i": cationic.unsqueeze(2).expand_as(valid3),
            "cat_j": cationic[batch_idx, safe_idx],
            "st_i": sticker.unsqueeze(2).expand_as(valid3),
            "st_j": sticker[batch_idx, safe_idx],
        }
        self._hbond_static_cache = {"key": cache_key, "ctx": static_ctx}
        return static_ctx

    def _prepare_hbond_pairwise_dynamic_ctx(self, c: torch.Tensor, nb_data, ctx: dict, static_ctx: dict) -> dict:
        _nb_idx, nb_dist, _nb_mask = nb_data[:3]
        ca = ctx["ca"]
        sc = ctx["sc"]
        donor = ctx["donor"]
        acceptor = ctx["acceptor"]
        safe_idx = static_ctx["safe_idx"]
        batch_idx = static_ctx["batch_idx"]
        valid3 = static_ctx["valid3"]

        ca_j = ca[batch_idx, safe_idx]
        ca_i = ca.unsqueeze(2).expand_as(ca_j)
        sc_j = sc[batch_idx, safe_idx]
        sc_i = sc.unsqueeze(2).expand_as(sc_j)
        donor_j = donor[batch_idx, safe_idx]
        donor_i = donor.unsqueeze(2).expand_as(donor_j)
        acceptor_j = acceptor[batch_idx, safe_idx]
        acceptor_i = acceptor.unsqueeze(2).expand_as(acceptor_j)

        d_sc = torch.linalg.norm(sc_i - sc_j, dim=-1).clamp_min(1e-6)
        local_density3 = ((nb_dist < 8.0) & valid3).float().sum(dim=-1)
        exposure_local3 = 1.0 / (1.0 + 0.12 * local_density3)
        exposure_pair3 = exposure_local3.unsqueeze(2) * exposure_local3[batch_idx, safe_idx]
        return {
            **static_ctx,
            "ca_i": ca_i,
            "ca_j": ca_j,
            "sc_i": sc_i,
            "sc_j": sc_j,
            "donor_i": donor_i,
            "donor_j": donor_j,
            "acceptor_i": acceptor_i,
            "acceptor_j": acceptor_j,
            "d_sc": d_sc,
            "local_density3": local_density3,
            "exposure_pair3": exposure_pair3,
        }

    def _environment_scale_single(self, params: dict) -> float:
        ionic = float(params.get("ionic_strength", 0.15) or 0.15)
        p_h = float(params.get("pH", 7.0) or 7.0)
        ptm = float(params.get("ptm_count", 0.0) or 0.0)
        hydro = float(params.get("hydro_strength", 1.0) or 1.0)
        scale = 1.0
        scale *= (1.0 + 0.25 * max(min(hydro, 2.0), 0.0))
        scale *= (1.0 + 0.08 * min(ptm, 8.0))
        scale *= (1.0 - 0.35 * min(max(ionic, 0.0), 1.0))
        scale *= (1.0 + 0.04 * min(abs(p_h - 7.0), 3.0))
        return float(scale)

    def _environment_scale(self, sim_params, c: torch.Tensor) -> torch.Tensor:
        bsz = int(c.shape[0])
        scales = [self._environment_scale_single(params) for params in self._sim_params_list(sim_params, bsz)]
        return torch.tensor(scales, dtype=c.dtype, device=c.device).view(bsz, 1, 1)

    def _conditional_scales_single(self, params: dict) -> dict[str, float | dict | str]:
        seq = dict(params.get("sequence_features", {}) or {})
        profile = _norm_branch_profile(params.get("idp_branch_profile"))
        target_name = str(params.get("target_name", "")).lower()
        policy = dict(params.get("idp_branch_force_policy", {}) or {})
        branch_defaults = dict(policy.get("branch_defaults", {}) or {})
        target_overrides = dict(policy.get("target_overrides", {}) or {})
        env_ionic = float(params.get("ionic_strength", 0.15) or 0.15)
        env_p_h = float(params.get("pH", 7.2) or 7.2)
        env_ptm = float(params.get("ptm_count", 0.0) or 0.0)
        env_hydro = float(params.get("hydro_strength", 1.0) or 1.0)

        llps_cfg = dict(branch_defaults.get("llps_lcd", {}) or {})
        agg_cfg = dict(branch_defaults.get("aggregation_prone", {}) or {})
        helix_cfg = dict(branch_defaults.get("helix_tad", {}) or {})
        llps_vh = float(llps_cfg.get("virtual_hbond_scale", 0.8))
        agg_vh = float(agg_cfg.get("virtual_hbond_scale", 0.55))
        helix_vh = float(helix_cfg.get("virtual_hbond_scale", 1.25))
        llps_ac = float(llps_cfg.get("anti_collapse_scale", 0.7))
        agg_ac = float(agg_cfg.get("anti_collapse_scale", 0.95))
        helix_ac = float(helix_cfg.get("anti_collapse_scale", 1.10))
        llps_contact = float(llps_cfg.get("contact_gain_scale", 1.20))
        agg_contact = float(agg_cfg.get("contact_gain_scale", 1.10))
        helix_contact = float(helix_cfg.get("contact_gain_scale", 0.90))
        llps_exposure = float(llps_cfg.get("exposure_sensitivity", 0.90))
        agg_exposure = float(agg_cfg.get("exposure_sensitivity", 1.25))
        helix_exposure = float(helix_cfg.get("exposure_sensitivity", 0.75))
        llps_spread = float(llps_cfg.get("anti_spread_scale", 0.75))
        agg_spread = float(agg_cfg.get("anti_spread_scale", 1.35))
        helix_spread = float(helix_cfg.get("anti_spread_scale", 0.65))
        llps_rg_target = float(llps_cfg.get("rg_target_multiplier", 1.0))
        agg_rg_target = float(agg_cfg.get("rg_target_multiplier", 1.0))
        helix_rg_target = float(helix_cfg.get("rg_target_multiplier", 1.0))
        llps_overcollapse_ratio = float(llps_cfg.get("overcollapse_ratio", 0.92))
        agg_overcollapse_ratio = float(agg_cfg.get("overcollapse_ratio", 0.92))
        helix_overcollapse_ratio = float(helix_cfg.get("overcollapse_ratio", 0.92))
        llps_vh_center = float(llps_cfg.get("virtual_hbond_center_A", 3.0))
        agg_vh_center = float(agg_cfg.get("virtual_hbond_center_A", 3.0))
        helix_vh_center = float(helix_cfg.get("virtual_hbond_center_A", 3.0))
        llps_vh_width = float(llps_cfg.get("virtual_hbond_width_A", 1.2))
        agg_vh_width = float(agg_cfg.get("virtual_hbond_width_A", 1.2))
        helix_vh_width = float(helix_cfg.get("virtual_hbond_width_A", 1.2))

        virtual_hbond_scale = (
            profile["llps_lcd"] * llps_vh
            + profile["aggregation_prone"] * agg_vh
            + profile["helix_tad"] * helix_vh
        )
        anti_collapse_scale = (
            profile["llps_lcd"] * llps_ac
            + profile["aggregation_prone"] * agg_ac
            + profile["helix_tad"] * helix_ac
        )
        contact_gain_scale = (
            profile["llps_lcd"] * llps_contact
            + profile["aggregation_prone"] * agg_contact
            + profile["helix_tad"] * helix_contact
        )
        exposure_sensitivity = (
            profile["llps_lcd"] * llps_exposure
            + profile["aggregation_prone"] * agg_exposure
            + profile["helix_tad"] * helix_exposure
        )
        anti_spread_scale = (
            profile["llps_lcd"] * llps_spread
            + profile["aggregation_prone"] * agg_spread
            + profile["helix_tad"] * helix_spread
        )
        rg_target_multiplier = (
            profile["llps_lcd"] * llps_rg_target
            + profile["aggregation_prone"] * agg_rg_target
            + profile["helix_tad"] * helix_rg_target
        )
        overcollapse_ratio = (
            profile["llps_lcd"] * llps_overcollapse_ratio
            + profile["aggregation_prone"] * agg_overcollapse_ratio
            + profile["helix_tad"] * helix_overcollapse_ratio
        )
        virtual_hbond_center_A = (
            profile["llps_lcd"] * llps_vh_center
            + profile["aggregation_prone"] * agg_vh_center
            + profile["helix_tad"] * helix_vh_center
        )
        virtual_hbond_width_A = (
            profile["llps_lcd"] * llps_vh_width
            + profile["aggregation_prone"] * agg_vh_width
            + profile["helix_tad"] * helix_vh_width
        )

        frac_aromatic = float(seq.get("frac_aromatic", 0.0) or 0.0)
        charge_density = float(seq.get("charge_density", seq.get("frac_charged", 0.0)) or 0.0)
        sticker_ratio = float(seq.get("sticker_spacer_ratio", 1.0) or 1.0)
        acidic_fraction = float(seq.get("acidic_fraction", 0.0) or 0.0)
        basic_fraction = float(seq.get("basic_fraction", 0.0) or 0.0)

        motif_scale = 1.0
        motif_scale *= 1.0 + 0.15 * min(frac_aromatic, 0.25) / 0.25
        motif_scale *= 1.0 + 0.10 * min(abs(sticker_ratio - 1.0), 1.0)
        if charge_density > 0.30:
            anti_collapse_scale *= 1.08
            virtual_hbond_scale *= 0.94
        if acidic_fraction + basic_fraction > 0.25:
            contact_gain_scale *= 1.04

        env_scale = 1.0
        env_scale *= 1.0 + 0.05 * min(env_ptm, 3.0)
        env_scale *= 1.0 + 0.06 * min(abs(env_p_h - 7.0), 1.5)
        env_scale *= 1.0 + 0.12 * max(min(env_hydro - 1.0, 0.5), -0.5)
        env_scale *= 1.0 - 0.20 * min(max(env_ionic - 0.15, 0.0), 0.5)

        matched_override = None
        for key, override in target_overrides.items():
            if str(key).lower() in target_name:
                matched_override = dict(override or {})
                break
        if matched_override is None:
            if "tau_k18" in target_name:
                matched_override = {"virtual_hbond_scale": 0.75, "anti_collapse_scale": 1.20}
            elif "hnrnpa1_lcd" in target_name:
                matched_override = {"virtual_hbond_scale": 0.80, "contact_gain_scale": 1.15}
            elif "tp53_tad" in target_name:
                matched_override = {"virtual_hbond_scale": 1.20, "anti_collapse_scale": 0.95}
        if matched_override:
            virtual_hbond_scale *= float(matched_override.get("virtual_hbond_scale", 1.0))
            anti_collapse_scale *= float(matched_override.get("anti_collapse_scale", 1.0))
            contact_gain_scale *= float(matched_override.get("contact_gain_scale", 1.0))
            exposure_sensitivity *= float(matched_override.get("exposure_sensitivity", 1.0))
            anti_spread_scale *= float(matched_override.get("anti_spread_scale", 1.0))
            rg_target_multiplier *= float(matched_override.get("rg_target_multiplier", 1.0))
            overcollapse_ratio *= float(matched_override.get("overcollapse_ratio", 1.0))
            virtual_hbond_center_A *= float(matched_override.get("virtual_hbond_center_A", 1.0))
            virtual_hbond_width_A *= float(matched_override.get("virtual_hbond_width_A", 1.0))

        virtual_hbond_scale *= motif_scale * env_scale
        anti_collapse_scale *= env_scale
        contact_gain_scale *= motif_scale
        return {
            "target_name": target_name,
            "branch_profile": profile,
            "virtual_hbond_scale": float(virtual_hbond_scale),
            "anti_collapse_scale": float(anti_collapse_scale),
            "contact_gain_scale": float(contact_gain_scale),
            "exposure_sensitivity": float(exposure_sensitivity),
            "anti_spread_scale": float(anti_spread_scale),
            "rg_target_multiplier": float(rg_target_multiplier),
            "overcollapse_ratio": float(overcollapse_ratio),
            "virtual_hbond_center_A": float(virtual_hbond_center_A),
            "virtual_hbond_width_A": float(virtual_hbond_width_A),
        }

    def _conditional_scales(self, sim_params, c: torch.Tensor) -> dict[str, torch.Tensor | list[str]]:
        bsz = int(c.shape[0])
        items = [self._conditional_scales_single(params) for params in self._sim_params_list(sim_params, bsz)]
        target_names = [str(item["target_name"]) for item in items]
        branch_profile = torch.tensor(
            [
                [
                    float(item["branch_profile"]["llps_lcd"]),
                    float(item["branch_profile"]["aggregation_prone"]),
                    float(item["branch_profile"]["helix_tad"]),
                ]
                for item in items
            ],
            dtype=c.dtype,
            device=c.device,
        )
        llps_target_mask = torch.tensor(
            [
                (
                    float(item["branch_profile"]["llps_lcd"]) >= max(
                        float(item["branch_profile"]["aggregation_prone"]),
                        float(item["branch_profile"]["helix_tad"]),
                    )
                    or any(tok in str(item["target_name"]) for tok in ("fus", "hnrn", "tia1", "ews", "ddx4", "npm1", "tardbp"))
                )
                for item in items
            ],
            dtype=c.dtype,
            device=c.device,
        ).view(bsz, 1, 1)
        return {
            "target_names": target_names,
            "branch_profile_tensor": branch_profile,
            "llps_branch": branch_profile[:, 0].view(bsz, 1, 1),
            "agg_branch": branch_profile[:, 1].view(bsz, 1, 1),
            "helix_branch": branch_profile[:, 2].view(bsz, 1, 1),
            "virtual_hbond_scale": torch.tensor([float(item["virtual_hbond_scale"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "anti_collapse_scale": torch.tensor([float(item["anti_collapse_scale"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "contact_gain_scale": torch.tensor([float(item["contact_gain_scale"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "exposure_sensitivity": torch.tensor([float(item["exposure_sensitivity"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "anti_spread_scale": torch.tensor([float(item["anti_spread_scale"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "rg_target_multiplier": torch.tensor([float(item["rg_target_multiplier"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "overcollapse_ratio": torch.tensor([float(item["overcollapse_ratio"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "virtual_hbond_center_A": torch.tensor([float(item["virtual_hbond_center_A"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "virtual_hbond_width_A": torch.tensor([float(item["virtual_hbond_width_A"]) for item in items], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "is_alpha_target": torch.tensor([("alpha_syn" in name) for name in target_names], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "is_hnrn_target": torch.tensor([("hnrn" in name) for name in target_names], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "is_fus_target": torch.tensor([("fus" in name) for name in target_names], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "is_tau_target": torch.tensor([("tau" in name) for name in target_names], dtype=c.dtype, device=c.device).view(bsz, 1, 1),
            "is_llps_target": llps_target_mask,
            "virtual_hbond_scale_flat": torch.tensor([float(item["virtual_hbond_scale"]) for item in items], dtype=c.dtype, device=c.device),
            "contact_gain_scale_flat": torch.tensor([float(item["contact_gain_scale"]) for item in items], dtype=c.dtype, device=c.device),
            "exposure_sensitivity_flat": torch.tensor([float(item["exposure_sensitivity"]) for item in items], dtype=c.dtype, device=c.device),
            "virtual_hbond_center_A_flat": torch.tensor([float(item["virtual_hbond_center_A"]) for item in items], dtype=c.dtype, device=c.device),
            "virtual_hbond_width_A_flat": torch.tensor([float(item["virtual_hbond_width_A"]) for item in items], dtype=c.dtype, device=c.device),
            "llps_branch_flat": branch_profile[:, 0].contiguous(),
            "agg_branch_flat": branch_profile[:, 1].contiguous(),
            "helix_branch_flat": branch_profile[:, 2].contiguous(),
        }

    def _pairwise_idp_hbond_force(self, c: torch.Tensor, top, nb_data, sim_params, ctx=None):
        bsz, n_atoms, _ = c.shape
        if ctx is None:
            ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        residue_types = ctx["residue_types"]
        ca = ctx["ca"]
        bead_info = ctx["bead_info"]
        disorder = ctx["disorder"]
        env_scale = ctx["env_scale"]
        cond = ctx["cond"]
        llps_branch = cond["llps_branch"]
        agg_branch = cond["agg_branch"]
        helix_branch = cond["helix_branch"]
        is_alpha = cond["is_alpha_target"]
        is_llps_target = cond["is_llps_target"]
        is_hnrn_target = cond["is_hnrn_target"]
        is_fus_target = cond["is_fus_target"]

        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return torch.zeros_like(c), {
                "virtual_hbond_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "virtual_hbond_mean_distance_A": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "mean_disorder_profile": disorder.mean(dim=-1),
            }

        nb_idx, nb_dist, nb_mask = nb_data
        if nb_idx.numel() == 0:
            return torch.zeros_like(c), {
                "virtual_hbond_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "virtual_hbond_mean_distance_A": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "mean_disorder_profile": disorder.mean(dim=-1),
            }
        backend = str(ctx.get("virtual_hbond_backend", "python")).strip().lower()
        pctx = None
        if self._fastpath_enabled_for(ctx, "hbond"):
            if backend in {"rust_hip", "rust", "hip"}:
                pctx = ctx.get("hbond_pairwise_rust_ctx")
            else:
                pctx = ctx.get("hbond_pairwise_ctx")
            if pctx is None:
                pctx = ctx.get("pairwise_ctx")
        rust_dynamic_ctx_ms = 0.0
        if backend in {"rust_hip", "rust", "hip"} and pctx is None:
            profile_vhbond = str(os.environ.get("IDP_VIRTUAL_HBOND_PROFILE", "0")).strip().lower() not in {"", "0", "false", "off", "no"}
            dynamic_started = time.perf_counter() if profile_vhbond else 0.0
            pctx = self._prepare_hbond_pairwise_rust_ctx(c, nb_data, ctx)
            rust_dynamic_ctx_ms = float((time.perf_counter() - dynamic_started) * 1000.0) if profile_vhbond else 0.0
        if backend in {"rust_hip", "rust", "hip"}:
            rust = self._get_rust_backend(c.device)
            if not rust.supports_idp_virtual_hbond():
                raise RuntimeError("Rust HIP IDP virtual_hbond backend is unavailable")
            f_total, backend_contacts, backend_mean_distance = rust.compute_idp_virtual_hbond_prepared(
                donor=ctx["donor"],
                acceptor=ctx["acceptor"],
                ca=ctx["ca"],
                sc=ctx["sc"],
                disorder=ctx["disorder"],
                aromatic_mask=ctx["aromatic_mask"],
                cationic_mask=ctx["cationic_mask"],
                sticker_mask=ctx["sticker_mask"],
                env_scale=ctx["env_scale"],
                nb_idx=nb_data[0],
                nb_dist=nb_data[1],
                nb_mask=nb_data[2],
                virtual_hbond_scale=cond["virtual_hbond_scale_flat"],
                contact_gain_scale=cond["contact_gain_scale_flat"],
                exposure_sensitivity=cond["exposure_sensitivity_flat"],
                exposure_gain_scale=ctx["hbond_exposure_gain_scale_flat"],
                virtual_hbond_center_A=cond["virtual_hbond_center_A_flat"],
                virtual_hbond_width_A=cond["virtual_hbond_width_A_flat"],
                llps_branch=cond["llps_branch_flat"],
                is_llps_target=cond["is_llps_target"].view(-1),
                is_hnrn_target=cond["is_hnrn_target"].view(-1),
                is_fus_target=cond["is_fus_target"].view(-1),
                virtual_hbond_strength=ctx["virtual_hbond_strength_relu"],
                unsat_penalty_strength=ctx["unsat_penalty_strength_relu"],
            )
            profile = dict(getattr(rust, "last_idp_virtual_hbond_profile", {}) or {})
            info = {
                # Snapshot cached backend outputs per step so rollout aggregation
                # does not accidentally observe the final step repeatedly.
                "virtual_hbond_contacts": backend_contacts.detach().clone(),
                "virtual_hbond_mean_distance_A": backend_mean_distance.detach().clone(),
                "mean_disorder_profile": disorder.mean(dim=-1),
                "conditional_virtual_hbond_scale": cond["virtual_hbond_scale"].view(-1),
                "conditional_contact_gain_scale": cond["contact_gain_scale"].view(-1),
                "conditional_exposure_sensitivity": cond["exposure_sensitivity"].view(-1),
                "virtual_hbond_backend": "rust_hip",
                "vhbond_dynamic_ctx_ms": float(rust_dynamic_ctx_ms),
                "vhbond_rust_buffer_ms": float(profile.get("buffer_ms", 0.0)),
                "vhbond_rust_kernel_ms": float(profile.get("kernel_ms", 0.0)),
                "vhbond_rust_post_ms": float(profile.get("post_ms", 0.0)),
                "vhbond_rust_launch_cpu_ms": float(profile.get("launch_cpu_ms", 0.0)),
                "vhbond_total_ms": float(rust_dynamic_ctx_ms + float(profile.get("launch_cpu_ms", 0.0))),
                **bead_info,
            }
            return f_total, info
        if pctx is None:
            safe_idx, batch_idx, valid = self._neighbor_pair_meta(c, nb_data, min_gap=3)
            sc = ctx["sc"]
            cb = ctx["cb"]
            tangent = ctx["tangent"]
            normal = ctx["normal"]
            offset = torch.clamp(self.virtual_site_offset_A, min=0.8, max=2.4).to(dtype=c.dtype)
            donor = sc + offset * _safe_normalize(sc - ca + 0.35 * tangent + 0.15 * normal)
            acceptor = cb - offset * _safe_normalize(cb - ca - 0.25 * tangent + 0.10 * normal)
            donor_j = donor[batch_idx, safe_idx]
            donor_i = donor.unsqueeze(2).expand_as(donor_j)
            acceptor_j = acceptor[batch_idx, safe_idx]
            acceptor_i = acceptor.unsqueeze(2).expand_as(acceptor_j)
            c_j = ca[batch_idx, safe_idx]
            center_i = ca.unsqueeze(2).expand_as(c_j)
            disorder_j = disorder[batch_idx, safe_idx]
            sc_j = sc[batch_idx, safe_idx]
            sc_i = sc.unsqueeze(2).expand_as(sc_j)
            local_density = ((nb_dist < 8.0) & valid).float().sum(dim=-1)
            exposure_local = 1.0 / (1.0 + 0.12 * local_density)
            exposure_pair = exposure_local.unsqueeze(2) * exposure_local[batch_idx, safe_idx]
            aromatic = ctx["aromatic_mask"]
            cationic = ctx["cationic_mask"]
            sticker = ctx["sticker_mask"]
            aro_i = aromatic.unsqueeze(2).expand_as(valid)
            aro_j = aromatic[batch_idx, safe_idx]
            cat_i = cationic.unsqueeze(2).expand_as(valid)
            cat_j = cationic[batch_idx, safe_idx]
            st_i = sticker.unsqueeze(2).expand_as(valid)
            st_j = sticker[batch_idx, safe_idx]
            d_sc = torch.linalg.norm(sc_i - sc_j, dim=-1).clamp_min(1e-6)
        else:
            donor_i = pctx["donor_i"]
            donor_j = pctx["donor_j"]
            acceptor_i = pctx["acceptor_i"]
            acceptor_j = pctx["acceptor_j"]
            center_i = pctx["ca_i"]
            c_j = pctx["ca_j"]
            disorder_j = pctx["disorder_j"]
            valid = pctx["valid3"]
            sc_i = pctx["sc_i"]
            sc_j = pctx["sc_j"]
            local_density = pctx["local_density3"]
            exposure_pair = pctx["exposure_pair3"]
            aro_i = pctx["aro_i"]
            aro_j = pctx["aro_j"]
            cat_i = pctx["cat_i"]
            cat_j = pctx["cat_j"]
            st_i = pctx["st_i"]
            st_j = pctx["st_j"]
            d_sc = pctx["d_sc"]

        # Symmetric virtual donor/acceptor matching.
        d_ij = torch.linalg.norm(donor_i - acceptor_j, dim=-1).clamp_min(1e-6)
        d_ji = torch.linalg.norm(donor_j - acceptor_i, dim=-1).clamp_min(1e-6)
        d_pair = torch.minimum(d_ij, d_ji)

        # Preferred weak directional contact around 3.0A in coarse space.
        width = torch.clamp(cond["virtual_hbond_width_A"], min=0.8, max=2.8)
        center = torch.clamp(cond["virtual_hbond_center_A"], min=2.2, max=5.0)
        well = torch.exp(-torch.square((d_pair - center) / width))
        unsat = torch.relu(d_pair - 4.4) / 4.4

        pair_weight = disorder.unsqueeze(2) * disorder_j
        exposure_gain = (0.55 + cond["exposure_sensitivity"] * exposure_pair) * ctx["hbond_exposure_gain_scale"]

        llps_mask = (is_llps_target > 0.5).expand_as(valid)
        if bool(torch.any(llps_mask)):
            pi_pi = aro_i & aro_j
            cation_pi = (cat_i & aro_j) | (aro_i & cat_j)
            aromatic_sticker = st_i & st_j
            pi_pi_support = pi_pi.float() * torch.exp(-torch.square((d_sc - 9.2) / 2.2))
            cation_pi_support = cation_pi.float() * torch.exp(-torch.square((d_sc - 10.0) / 2.6))
            sticker_support = aromatic_sticker.float() * torch.exp(-torch.square((d_sc - 9.8) / 2.8))
            llps_transfer = valid.float() * (
                0.45 * pi_pi_support
                + 0.85 * cation_pi_support
                + 0.25 * sticker_support
            )
            transfer_gain = 0.18 + 0.20 * torch.clamp(llps_branch, max=1.0)
            transfer_gain = transfer_gain + 0.10 * is_hnrn_target + 0.06 * is_fus_target
            pair_weight = torch.where(
                llps_mask,
                pair_weight * (1.0 + transfer_gain * torch.clamp(llps_transfer, min=0.0, max=1.6)),
                pair_weight,
            )
            unsat = torch.where(
                llps_mask,
                unsat * (1.0 - 0.18 * torch.clamp(llps_transfer, min=0.0, max=1.0)),
                unsat,
            )

        pair_weight = pair_weight * exposure_gain
        strength = torch.relu(self.virtual_hbond_strength).to(dtype=c.dtype) * env_scale * cond["virtual_hbond_scale"]
        unsat_k = torch.relu(self.unsat_penalty_strength).to(dtype=c.dtype)
        mag = (strength * cond["contact_gain_scale"] * pair_weight * well - unsat_k * pair_weight * unsat) * valid.float()

        dr = center_i - c_j
        unit = dr / torch.linalg.norm(dr, dim=-1, keepdim=True).clamp_min(1e-6)
        f_pair = -mag.unsqueeze(-1) * unit
        f_total = f_pair.sum(dim=2)

        contact_mask = (valid & (well > 0.35)).float()
        mean_dist = (d_pair * contact_mask).sum() / contact_mask.sum().clamp_min(1.0)
        info = {
            "virtual_hbond_contacts": contact_mask.sum(dim=(1, 2)),
            "virtual_hbond_mean_distance_A": (d_pair * contact_mask).sum(dim=(1, 2)) / contact_mask.sum(dim=(1, 2)).clamp_min(1.0),
            "mean_disorder_profile": disorder.mean(dim=-1),
            "conditional_virtual_hbond_scale": cond["virtual_hbond_scale"].view(-1),
            "conditional_contact_gain_scale": cond["contact_gain_scale"].view(-1),
            "conditional_exposure_sensitivity": cond["exposure_sensitivity"].view(-1),
            "virtual_hbond_backend": str(ctx.get("virtual_hbond_backend", "python")),
            "vhbond_dynamic_ctx_ms": 0.0,
            "vhbond_rust_buffer_ms": 0.0,
            "vhbond_rust_kernel_ms": 0.0,
            "vhbond_rust_post_ms": 0.0,
            "vhbond_rust_launch_cpu_ms": 0.0,
            "vhbond_total_ms": 0.0,
            **bead_info,
        }
        return f_total, info

    def build_virtual_hbond_parity_packet(self, c: torch.Tensor, top, nb_data, sim_params) -> dict[str, object]:
        if c.ndim == 2:
            c = c.unsqueeze(0)
        ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        pctx = ctx.get("hbond_pairwise_ctx")
        if pctx is None:
            pctx = self._prepare_hbond_pairwise_ctx(c, nb_data, ctx)
            if pctx is not None:
                ctx["hbond_pairwise_ctx"] = pctx
        f_hbond, info = self._pairwise_idp_hbond_force(c, top, nb_data, sim_params, ctx=ctx)
        offset = torch.clamp(self.virtual_site_offset_A, min=0.8, max=2.4).to(dtype=c.dtype)
        donor = ctx["sc"] + offset * _safe_normalize(ctx["sc"] - ctx["ca"] + 0.35 * ctx["tangent"] + 0.15 * ctx["normal"])
        acceptor = ctx["cb"] - offset * _safe_normalize(ctx["cb"] - ctx["ca"] - 0.25 * ctx["tangent"] + 0.10 * ctx["normal"])

        def _cpu_tensor_dict(src: dict[str, object] | None) -> dict[str, object]:
            out: dict[str, object] = {}
            if not isinstance(src, dict):
                return out
            for key, value in src.items():
                if torch.is_tensor(value):
                    out[key] = value.detach().cpu()
                else:
                    out[key] = value
            return out

        raw_nb: dict[str, object] = {}
        if isinstance(nb_data, (tuple, list)) and len(nb_data) >= 3:
            raw_nb = {
                "nb_idx": nb_data[0].detach().cpu(),
                "nb_dist": nb_data[1].detach().cpu(),
                "nb_mask": nb_data[2].detach().cpu(),
            }

        raw_top: dict[str, object] = {}
        residue_types = getattr(top, "residue_types", None)
        if torch.is_tensor(residue_types):
            raw_top["residue_types"] = residue_types.detach().cpu()
        box_size = getattr(top, "box_size", None)
        if torch.is_tensor(box_size):
            raw_top["box_size"] = box_size.detach().cpu()
        elif box_size is not None:
            raw_top["box_size"] = box_size

        info_cpu = _cpu_tensor_dict(info)
        cond_src = dict(ctx.get("cond", {}) or {})
        cond = _cpu_tensor_dict(cond_src)
        vh_scale_flat = cond_src.get("virtual_hbond_scale_flat", cond_src.get("virtual_hbond_scale"))
        contact_gain_flat = cond_src.get("contact_gain_scale_flat", cond_src.get("contact_gain_scale"))
        exposure_flat = cond_src.get("exposure_sensitivity_flat", cond_src.get("exposure_sensitivity"))
        center_flat = cond_src.get("virtual_hbond_center_A_flat", cond_src.get("virtual_hbond_center_A"))
        width_flat = cond_src.get("virtual_hbond_width_A_flat", cond_src.get("virtual_hbond_width_A"))
        llps_branch_flat = cond_src.get("llps_branch_flat", cond_src.get("llps_branch"))
        is_llps_flat = cond_src.get("is_llps_target")
        is_hnrn_flat = cond_src.get("is_hnrn_target")
        is_fus_flat = cond_src.get("is_fus_target")
        packet = {
            "meta": {
                "batch_size": int(c.shape[0]),
                "n_atoms": int(c.shape[1]),
                "virtual_hbond_backend": str(ctx.get("virtual_hbond_backend", "python")),
                "pairwise_fastpath_mode": str(ctx.get("pairwise_fastpath_mode", "none")),
            },
            "raw": {
                "coords": c.detach().cpu(),
                **raw_nb,
                "top": raw_top,
                "sim_params": sim_params,
            },
            "derived": {
                "env_scale": ctx["env_scale"].detach().cpu() if torch.is_tensor(ctx.get("env_scale")) else ctx.get("env_scale"),
                "cond": cond,
                "pair_ctx": _cpu_tensor_dict(pctx),
                "backend_inputs": {
                    "donor": donor.detach().cpu(),
                    "acceptor": acceptor.detach().cpu(),
                    "ca": ctx["ca"].detach().cpu(),
                    "sc": ctx["sc"].detach().cpu(),
                    "disorder": ctx["disorder"].detach().cpu(),
                    "aromatic_mask": ctx["aromatic_mask"].detach().cpu(),
                    "cationic_mask": ctx["cationic_mask"].detach().cpu(),
                    "sticker_mask": ctx["sticker_mask"].detach().cpu(),
                    "env_scale": ctx["env_scale"].detach().cpu(),
                    "nb_idx": nb_data[0].detach().cpu() if isinstance(nb_data, (tuple, list)) and len(nb_data) >= 1 else None,
                    "nb_dist": nb_data[1].detach().cpu() if isinstance(nb_data, (tuple, list)) and len(nb_data) >= 2 else None,
                    "nb_mask": (nb_data[2] > 0.5).to(dtype=torch.uint8).detach().cpu() if isinstance(nb_data, (tuple, list)) and len(nb_data) >= 3 else None,
                    "virtual_hbond_scale": vh_scale_flat.reshape(-1).detach().cpu() if torch.is_tensor(vh_scale_flat) else None,
                    "contact_gain_scale": contact_gain_flat.reshape(-1).detach().cpu() if torch.is_tensor(contact_gain_flat) else None,
                    "exposure_sensitivity": exposure_flat.reshape(-1).detach().cpu() if torch.is_tensor(exposure_flat) else None,
                    "exposure_gain_scale": ctx["hbond_exposure_gain_scale_flat"].reshape(-1).detach().cpu(),
                    "virtual_hbond_center_A": center_flat.reshape(-1).detach().cpu() if torch.is_tensor(center_flat) else None,
                    "virtual_hbond_width_A": width_flat.reshape(-1).detach().cpu() if torch.is_tensor(width_flat) else None,
                    "llps_branch": llps_branch_flat.reshape(-1).detach().cpu() if torch.is_tensor(llps_branch_flat) else None,
                    "is_llps_target": is_llps_flat.reshape(-1).detach().cpu() if torch.is_tensor(is_llps_flat) else None,
                    "is_hnrn_target": is_hnrn_flat.reshape(-1).detach().cpu() if torch.is_tensor(is_hnrn_flat) else None,
                    "is_fus_target": is_fus_flat.reshape(-1).detach().cpu() if torch.is_tensor(is_fus_flat) else None,
                    "virtual_hbond_strength": torch.relu(self.virtual_hbond_strength).detach().cpu(),
                    "unsat_penalty_strength": torch.relu(self.unsat_penalty_strength).detach().cpu(),
                },
            },
            "reference": {
                "force": f_hbond.detach().cpu(),
                "info": info_cpu,
            },
        }
        return packet

    def _pairwise_sticker_force(self, c: torch.Tensor, top, nb_data, sim_params, ctx=None):
        bsz, n_atoms, _ = c.shape
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return torch.zeros_like(c), {
                "sticker_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "pi_pi_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "cation_pi_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            }
        nb_idx, nb_dist, nb_mask = nb_data
        if nb_idx.numel() == 0:
            return torch.zeros_like(c), {
                "sticker_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "pi_pi_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "cation_pi_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            }

        if ctx is None:
            ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        cond = ctx["cond"]
        env_scale = ctx["env_scale"]
        llps_branch = cond["llps_branch"]
        agg_branch = cond["agg_branch"]
        helix_branch = cond["helix_branch"]
        is_hnrn_target = cond["is_hnrn_target"]
        is_fus_target = cond["is_fus_target"]
        residue_types = ctx["residue_types"]
        pctx = ctx.get("pairwise_ctx") if self._fastpath_enabled_for(ctx, "sticker") else None
        if pctx is None:
            safe_idx, batch_idx, valid = self._neighbor_pair_meta(c, nb_data, min_gap=3)
            _, _, valid4 = self._neighbor_pair_meta(c, nb_data, min_gap=4)
            sc = ctx["sc"]
            sc_j = sc[batch_idx, safe_idx]
            sc_i = sc.unsqueeze(2).expand_as(sc_j)
            d_sc = torch.linalg.norm(sc_i - sc_j, dim=-1).clamp_min(1e-6)
            aromatic = ctx["aromatic_mask"]
            cationic = ctx["cationic_mask"]
            sticker = ctx["sticker_mask"]
            aro_i = aromatic.unsqueeze(2).expand_as(valid)
            aro_j = aromatic[batch_idx, safe_idx]
            cat_i = cationic.unsqueeze(2).expand_as(valid)
            cat_j = cationic[batch_idx, safe_idx]
            st_i = sticker.unsqueeze(2).expand_as(valid)
            st_j = sticker[batch_idx, safe_idx]
            local_density4 = ((nb_dist < 8.0) & valid4).float().sum(dim=-1)
            exposure_local4 = 1.0 / (1.0 + 0.10 * local_density4)
            exposure_pair = exposure_local4.unsqueeze(2) * exposure_local4[batch_idx, safe_idx]
        else:
            valid = pctx["valid3"]
            aro_i = pctx["aro_i"]
            aro_j = pctx["aro_j"]
            cat_i = pctx["cat_i"]
            cat_j = pctx["cat_j"]
            st_i = pctx["st_i"]
            st_j = pctx["st_j"]
            d_sc = pctx["d_sc"]
            sc_i = pctx["sc_i"]
            sc_j = pctx["sc_j"]
            exposure_pair = pctx["exposure_pair4"]
        pi_pi = aro_i & aro_j
        cation_pi = (cat_i & aro_j) | (aro_i & cat_j)
        aromatic_sticker = st_i & st_j
        base_strength = torch.relu(self.sticker_strength).to(dtype=c.dtype) * env_scale
        llps_gain = 1.05 + 0.95 * llps_branch
        agg_gain = 0.85 + 0.65 * agg_branch
        helix_gain = 0.55 + 0.20 * helix_branch

        arg_fraction = float((residue_types == RES_ARG).float().mean().item())
        aromatic_fraction = float(((residue_types == RES_PHE) | (residue_types == RES_TYR) | (residue_types == RES_TRP)).float().mean().item())
        llps_pair_gain = torch.ones((bsz, 1, 1), dtype=c.dtype, device=c.device)
        pi_pi_gain = torch.ones((bsz, 1, 1), dtype=c.dtype, device=c.device)
        cation_pi_gain = torch.ones((bsz, 1, 1), dtype=c.dtype, device=c.device)
        sticker_gain = torch.ones((bsz, 1, 1), dtype=c.dtype, device=c.device)
        llps_dominant = (llps_branch >= torch.maximum(agg_branch, helix_branch)).to(dtype=c.dtype)
        llps_pair_gain = llps_pair_gain * (1.0 + llps_dominant * (0.55 * min(aromatic_fraction / 0.16, 1.5)))
        cation_pi_gain = cation_pi_gain * (1.0 + llps_dominant * (0.70 * min(arg_fraction / 0.10, 1.5)))
        pi_pi_gain = pi_pi_gain * (1.0 + llps_dominant * (0.35 * min(aromatic_fraction / 0.16, 1.5)))
        sticker_gain = sticker_gain * (1.0 + llps_dominant * (0.25 * min((aromatic_fraction + arg_fraction) / 0.24, 1.5)))
        cation_pi_gain = cation_pi_gain * (1.0 + 0.35 * is_hnrn_target)
        pi_pi_gain = pi_pi_gain * (1.0 + 0.12 * is_hnrn_target + 0.28 * is_fus_target)
        sticker_gain = sticker_gain * (1.0 + 0.10 * is_hnrn_target + 0.12 * is_fus_target)

        # In this 3-bead proxy geometry, sidechain-center distances for
        # long-range aromatic/cation interactions sit much farther out than
        # atomistic contact distances. Keep the wells aligned to the CG edge
        # distribution so LLPS sticker interactions can actually activate.
        pi_pi_well = torch.exp(-torch.square((d_sc - 9.2) / 2.1))
        cation_pi_well = torch.exp(-torch.square((d_sc - 10.0) / 2.5))
        sticker_well = torch.exp(-torch.square((d_sc - 9.8) / 2.7))

        mag = (
            pi_pi_gain * (0.55 * llps_gain + 0.30 * agg_gain) * pi_pi.float() * pi_pi_well
            + cation_pi_gain * (1.05 * llps_gain + 0.10 * helix_gain) * cation_pi.float() * cation_pi_well
            + llps_pair_gain * sticker_gain * (0.28 * llps_gain + 0.42 * agg_gain + 0.12 * helix_gain) * aromatic_sticker.float() * sticker_well
        )
        mag = base_strength * exposure_pair * mag * valid.float()

        dr = sc_i - sc_j
        unit = dr / torch.linalg.norm(dr, dim=-1, keepdim=True).clamp_min(1e-6)
        f_pair = -mag.unsqueeze(-1) * unit
        f_total = f_pair.sum(dim=2)
        contact_diag = _pairwise_contact_diagnostics_enabled()
        zero_vec = torch.zeros(bsz, dtype=c.dtype, device=c.device)
        info = {
            "sticker_contacts": (valid & (mag > 0.02)).float().sum(dim=(1, 2)) if contact_diag else zero_vec,
            "pi_pi_contacts": (valid & pi_pi & (pi_pi_well > 0.4)).float().sum(dim=(1, 2)) if contact_diag else zero_vec,
            "cation_pi_contacts": (valid & cation_pi & (cation_pi_well > 0.4)).float().sum(dim=(1, 2)) if contact_diag else zero_vec,
            "llps_contact_memory_mean": zero_vec,
        }
        return f_total, info

    def _pairwise_llps_bridge_force(self, c: torch.Tensor, top, nb_data, sim_params, ctx=None):
        bsz, n_atoms, _ = c.shape
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return torch.zeros_like(c), {
                "bridge_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "bridge_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            }
        nb_idx, nb_dist, nb_mask = nb_data
        if nb_idx.numel() == 0:
            return torch.zeros_like(c), {
                "bridge_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "bridge_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            }

        if ctx is None:
            ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        cond = ctx["cond"]
        env_scale = ctx["env_scale"]
        llps_branch = cond["llps_branch"]
        is_llps_target = cond["is_llps_target"]
        is_hnrn_target = cond["is_hnrn_target"]
        is_fus_target = cond["is_fus_target"]
        if not bool(torch.any(is_llps_target > 0.5)):
            return torch.zeros_like(c), {
                "bridge_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "bridge_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            }
        pctx = ctx.get("pairwise_ctx") if self._fastpath_enabled_for(ctx, "bridge") else None
        if pctx is None:
            safe_idx, batch_idx, valid = self._neighbor_pair_meta(c, nb_data, min_gap=4)
            ca = ctx["ca"]
            sc = ctx["sc"]
            ca_j = ca[batch_idx, safe_idx]
            ca_i = ca.unsqueeze(2).expand_as(ca_j)
            sc_j = sc[batch_idx, safe_idx]
            sc_i = sc.unsqueeze(2).expand_as(sc_j)
            d_sc = torch.linalg.norm(sc_i - sc_j, dim=-1).clamp_min(1e-6)
            d_ca = torch.linalg.norm(ca_i - ca_j, dim=-1).clamp_min(1e-6)
            aromatic = ctx["aromatic_mask"]
            cationic = ctx["cationic_mask"]
            sticker = ctx["sticker_mask"]
            aro_i = aromatic.unsqueeze(2).expand_as(valid)
            aro_j = aromatic[batch_idx, safe_idx]
            cat_i = cationic.unsqueeze(2).expand_as(valid)
            cat_j = cationic[batch_idx, safe_idx]
            st_i = sticker.unsqueeze(2).expand_as(valid)
            st_j = sticker[batch_idx, safe_idx]
            local_density4 = ((nb_dist < 8.0) & valid).float().sum(dim=-1)
            exposure_local4 = 1.0 / (1.0 + 0.10 * local_density4)
            exposure_pair = exposure_local4.unsqueeze(2) * exposure_local4[batch_idx, safe_idx]
        else:
            valid = pctx["valid4"]
            aro_i = pctx["aro_i"]
            aro_j = pctx["aro_j"]
            cat_i = pctx["cat_i"]
            cat_j = pctx["cat_j"]
            st_i = pctx["st_i"]
            st_j = pctx["st_j"]
            d_sc = pctx["d_sc"]
            d_ca = pctx["d_ca"]
            ca_i = pctx["ca_i"]
            ca_j = pctx["ca_j"]
            sc_i = pctx["sc_i"]
            sc_j = pctx["sc_j"]
            exposure_pair = pctx["exposure_pair4"]
        pi_pi = aro_i & aro_j
        cation_pi = (cat_i & aro_j) | (aro_i & cat_j)
        aromatic_sticker = st_i & st_j

        bridge_support = valid.float() * (
            0.55 * pi_pi.float() * torch.exp(-torch.square((d_ca - 13.4) / 3.0))
            + 1.05 * cation_pi.float() * torch.exp(-torch.square((d_ca - 12.8) / 2.7))
            + 0.32 * aromatic_sticker.float() * torch.exp(-torch.square((d_ca - 13.1) / 3.1))
        )
        base_strength = torch.relu(self.bridge_strength).to(dtype=c.dtype) * env_scale
        bridge_gain = 1.0 + 0.85 * llps_branch
        bridge_gain = bridge_gain * (1.0 + 0.55 * is_hnrn_target + 0.30 * is_fus_target)
        mag = base_strength * bridge_gain * exposure_pair * bridge_support * is_llps_target

        dr = ca_i - ca_j
        unit = dr / torch.linalg.norm(dr, dim=-1, keepdim=True).clamp_min(1e-6)
        f_pair = -mag.unsqueeze(-1) * unit
        f_total = f_pair.sum(dim=2)
        component_diag = _env_enabled("IDP_COMPONENT_FORCE_DIAGNOSTICS", "0")
        contact_diag = _pairwise_contact_diagnostics_enabled()
        info = {
            "bridge_contacts": (
                (valid & (bridge_support > 0.12)).float().sum(dim=(1, 2))
                if contact_diag
                else torch.zeros(bsz, dtype=c.dtype, device=c.device)
            ),
            "bridge_force_mean": (
                torch.linalg.norm(f_total, dim=-1).mean(dim=-1)
                if component_diag
                else torch.zeros(bsz, dtype=c.dtype, device=c.device)
            ),
        }
        return f_total, info

    def _pairwise_sticker_bridge_force_rust(self, c: torch.Tensor, top, nb_data, sim_params, ctx=None):
        bsz = int(c.shape[0])
        zero_vec = torch.zeros(bsz, dtype=c.dtype, device=c.device)
        zero_force = torch.zeros_like(c)
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3 or nb_data[0].numel() == 0:
            return (
                zero_force,
                {
                    "sticker_contacts": zero_vec,
                    "pi_pi_contacts": zero_vec,
                    "cation_pi_contacts": zero_vec,
                    "llps_contact_memory_mean": zero_vec,
                },
                zero_force,
                {
                    "bridge_contacts": zero_vec,
                    "bridge_force_mean": zero_vec,
                },
            )
        if ctx is None:
            ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        rust = self._get_rust_backend(c.device)
        if not rust.supports_idp_sticker_bridge():
            raise RuntimeError("Rust HIP IDP sticker_bridge backend is unavailable")
        cond = ctx["cond"]
        contact_diag = _pairwise_contact_diagnostics_enabled()
        f_sticker, f_bridge, sticker_contacts, pi_pi_contacts, cation_pi_contacts, bridge_contacts = rust.compute_idp_sticker_bridge_prepared(
            ca=ctx["ca"],
            sc=ctx["sc"],
            aromatic_mask=ctx["aromatic_mask"],
            cationic_mask=ctx["cationic_mask"],
            sticker_mask=ctx["sticker_mask"],
            nb_idx=nb_data[0],
            nb_dist=nb_data[1],
            nb_mask=nb_data[2],
            sticker_strength=ctx["sticker_strength_relu"],
            bridge_strength=ctx["bridge_strength_relu"],
            env_scale=ctx["env_scale"].view(-1),
            llps_branch=cond["llps_branch_flat"],
            agg_branch=cond["agg_branch_flat"],
            helix_branch=cond["helix_branch_flat"],
            is_llps_target=cond["is_llps_target"].view(-1),
            is_hnrn_target=cond["is_hnrn_target"].view(-1),
            is_fus_target=cond["is_fus_target"].view(-1),
            arg_fraction=ctx["arg_fraction_flat"],
            aromatic_fraction=ctx["aromatic_fraction_flat"],
            collect_contacts=contact_diag,
        )
        return (
            f_sticker,
            {
                "sticker_contacts": sticker_contacts.detach().clone() if contact_diag else zero_vec,
                "pi_pi_contacts": pi_pi_contacts.detach().clone() if contact_diag else zero_vec,
                "cation_pi_contacts": cation_pi_contacts.detach().clone() if contact_diag else zero_vec,
                "llps_contact_memory_mean": zero_vec,
            },
            f_bridge,
            {
                "bridge_contacts": bridge_contacts.detach().clone() if contact_diag else zero_vec,
                "bridge_force_mean": (
                    torch.linalg.norm(f_bridge, dim=-1).mean(dim=-1)
                    if _env_enabled("IDP_COMPONENT_FORCE_DIAGNOSTICS", "0")
                    else zero_vec
                ),
            },
        )

    def _anti_collapse_force(self, c: torch.Tensor, top, nb_data, sim_params, ctx=None):
        bsz, n_atoms, _ = c.shape
        params_list = self._sim_params_list(sim_params, bsz)
        if ctx is None:
            ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        residue_types = ctx["residue_types"]
        disorder = ctx["disorder"]
        env_scale = ctx["env_scale"]
        cond = ctx["cond"]
        agg_branch = cond["agg_branch"]
        llps_branch = cond["llps_branch"]
        helix_branch = cond["helix_branch"]
        is_alpha = cond["is_alpha_target"]
        is_llps_target = cond["is_llps_target"]
        center = c.mean(dim=1, keepdim=True)
        radial = c - center
        radial_norm = torch.linalg.norm(radial, dim=-1, keepdim=True).clamp_min(1e-6)
        rg = torch.sqrt(torch.mean(torch.sum(torch.square(radial), dim=-1), dim=1, keepdim=True)).unsqueeze(-1)
        n_scale = torch.tensor(float(max(n_atoms, 2)) ** 0.58, dtype=c.dtype, device=c.device)
        disorder_scale = 1.0 + 0.45 * disorder.mean(dim=1, keepdim=True).unsqueeze(-1)
        target_rg = torch.relu(self.rg_target_scale).to(dtype=c.dtype) * n_scale * disorder_scale
        target_rg = target_rg * torch.clamp(cond["rg_target_multiplier"], min=0.65, max=1.10)
        deficit = torch.relu(target_rg - rg)
        anti_k = torch.relu(self.anti_collapse_strength).to(dtype=c.dtype) * env_scale * cond["anti_collapse_scale"]
        agg_mask = agg_branch >= 0.50
        anti_k = torch.where(agg_mask, anti_k * 1.20, anti_k)
        target_rg = torch.where(agg_mask, target_rg * 1.08, target_rg)
        llps_contract = []
        for params in params_list:
            seq = params.get("sequence_features", {}) if isinstance(params.get("sequence_features", {}), dict) else {}
            sticker_density = float(seq.get("sticker_density", 0.0) or 0.0)
            basic_fraction = float(seq.get("basic_fraction", 0.0) or 0.0)
            contract_mult = 0.90
            contract_mult -= 0.05 * min(sticker_density / 0.22, 1.2)
            contract_mult -= 0.03 * min(basic_fraction / 0.10, 1.2)
            llps_contract.append(max(contract_mult, 0.72))
        llps_contract_t = torch.tensor(llps_contract, dtype=c.dtype, device=c.device).view(bsz, 1, 1)
        target_rg = torch.where(is_llps_target > 0.5, target_rg * llps_contract_t, target_rg)
        expand_force = anti_k * deficit * radial / radial_norm
        anti_spread_info = {
            "anti_spread_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            "conditional_anti_spread_scale": cond["anti_spread_scale"].view(-1),
        }
        inward_force = torch.zeros_like(c)
        if _env_enabled("IDP_R11_PHYS_PATCH") or _env_enabled("IDP_R12_PHYS_PATCH") or _env_enabled("IDP_R13_PHYS_PATCH") or _env_enabled("IDP_R14_PHYS_PATCH") or _env_enabled("IDP_R17_PHYS_PATCH"):
            if _env_enabled("IDP_R17_PHYS_PATCH"):
                spread_target_llps = target_rg * (0.985 - 0.015 * torch.clamp(llps_branch, max=1.0))
                overspread_llps = torch.relu(rg - spread_target_llps)
                anti_spread_k_llps = torch.relu(self.anti_spread_strength).to(dtype=c.dtype) * env_scale * cond["anti_spread_scale"] * 1.08
                spread_target_agg = target_rg * torch.where(is_alpha > 0.5, torch.ones_like(target_rg) * 0.988, 0.972 - 0.02 * agg_branch)
                overspread_agg = torch.relu(rg - spread_target_agg)
                anti_spread_k_agg = torch.relu(self.anti_spread_strength).to(dtype=c.dtype) * env_scale * cond["anti_spread_scale"] * torch.where(
                    is_alpha > 0.5,
                    torch.ones_like(target_rg) * 1.08,
                    torch.where(agg_branch >= 0.50, torch.ones_like(target_rg) * 1.85, torch.ones_like(target_rg) * 1.35),
                )
                overspread = torch.where(is_llps_target > 0.5, overspread_llps, overspread_agg)
                anti_spread_k = torch.where(is_llps_target > 0.5, anti_spread_k_llps, anti_spread_k_agg)
            elif _env_enabled("IDP_R14_PHYS_PATCH"):
                spread_target = target_rg * torch.where(is_alpha > 0.5, torch.ones_like(target_rg) * 0.988, 0.972 - 0.02 * agg_branch)
                overspread = torch.relu(rg - spread_target)
                anti_spread_k = torch.relu(self.anti_spread_strength).to(dtype=c.dtype) * env_scale * cond["anti_spread_scale"] * torch.where(
                    is_alpha > 0.5,
                    torch.ones_like(target_rg) * 1.08,
                    torch.where(agg_branch >= 0.50, torch.ones_like(target_rg) * 1.85, torch.ones_like(target_rg) * 1.35),
                )
            elif _env_enabled("IDP_R13_PHYS_PATCH"):
                spread_target = target_rg * torch.where(is_alpha > 0.5, torch.ones_like(target_rg) * 0.995, 0.97 - 0.03 * agg_branch)
                overspread = torch.relu(rg - spread_target)
                anti_spread_k = torch.relu(self.anti_spread_strength).to(dtype=c.dtype) * env_scale * cond["anti_spread_scale"] * torch.where(
                    is_alpha > 0.5,
                    torch.ones_like(target_rg) * 1.25,
                    torch.where(agg_branch >= 0.50, torch.ones_like(target_rg) * 2.15, torch.ones_like(target_rg) * 1.45),
                )
            elif _env_enabled("IDP_R12_PHYS_PATCH"):
                spread_target = target_rg * (0.97 - 0.03 * agg_branch)
                overspread = torch.relu(rg - spread_target)
                anti_spread_k = torch.relu(self.anti_spread_strength).to(dtype=c.dtype) * env_scale * cond["anti_spread_scale"] * torch.where(
                    agg_branch >= 0.50,
                    torch.ones_like(target_rg) * 2.15,
                    torch.ones_like(target_rg) * 1.45,
                )
            else:
                overspread = torch.relu(rg - 1.02 * target_rg)
                anti_spread_k = torch.relu(self.anti_spread_strength).to(dtype=c.dtype) * env_scale * cond["anti_spread_scale"]
            inward_force = anti_spread_k * overspread * (-radial / radial_norm)
            anti_spread_info["anti_spread_force_mean"] = torch.linalg.norm(inward_force, dim=-1).mean(dim=-1)

        crowd_force = torch.zeros_like(c)
        density_count = torch.zeros((bsz, n_atoms), dtype=c.dtype, device=c.device)
        if isinstance(nb_data, (tuple, list)) and len(nb_data) >= 3:
            nb_idx, nb_dist, nb_mask = nb_data
            safe_idx = nb_idx.clamp_min(0).long()
            batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
            atom_i = torch.arange(n_atoms, device=c.device, dtype=torch.long).view(1, n_atoms, 1).expand_as(safe_idx)
            seq_gap = torch.abs(atom_i - safe_idx)
            density_cutoff = torch.clamp(self.density_cutoff_A, min=4.0, max=12.0).to(dtype=c.dtype)
            overcrowded = (nb_mask > 0.5) & (nb_idx >= 0) & (seq_gap >= 3) & (nb_dist < density_cutoff)
            density_count = overcrowded.float().sum(dim=-1)
            local_k = torch.relu(self.local_density_strength).to(dtype=c.dtype)
            neigh = c[batch_idx, safe_idx]
            pair_vec = c.unsqueeze(2) - neigh
            unit = pair_vec / torch.linalg.norm(pair_vec, dim=-1, keepdim=True).clamp_min(1e-6)
            crowd_mag = local_k * disorder.unsqueeze(-1) * torch.relu(density_count.unsqueeze(-1) - 2.0) / 6.0
            crowd_pair = overcrowded.unsqueeze(-1).float() * unit
            crowd_force = crowd_mag * crowd_pair.sum(dim=2)

        f_total = expand_force + crowd_force + inward_force
        overcollapse_ratio = torch.clamp(cond["overcollapse_ratio"], min=0.70, max=0.98)
        overcollapse_rate = (rg.squeeze(-1).squeeze(-1) < (overcollapse_ratio * target_rg).squeeze(-1).squeeze(-1)).float()
        info = {
            "anti_collapse_force_mean": torch.linalg.norm(f_total, dim=-1).mean(dim=-1),
            "anti_collapse_rg_target_A": target_rg.view(bsz, -1).mean(dim=-1),
            "anti_collapse_rg_observed_A": rg.view(bsz, -1).mean(dim=-1),
            "anti_collapse_density_mean": density_count.mean(dim=-1),
            "anti_collapse_overcollapse_rate": overcollapse_rate,
            "anti_collapse_overcollapse_ratio": overcollapse_ratio.view(-1),
            "conditional_anti_collapse_scale": cond["anti_collapse_scale"].view(-1),
            **anti_spread_info,
        }
        return f_total, info

    def _transient_helix_force(self, c: torch.Tensor, top, sim_params, ctx=None):
        if c.shape[1] < 3:
            return torch.zeros_like(c), {
                "helix_proxy_mean": 0.0,
                "coil_expansion_mean": 0.0,
            }
        if ctx is None:
            ctx = self._prepare_step_ctx(c, top, None, sim_params)
        residue_types = ctx["residue_types"]
        disorder = ctx["disorder"]
        env_scale = ctx["env_scale"]

        prev = torch.cat([c[:, :1, :], c[:, :-1, :]], dim=1)
        nxt = torch.cat([c[:, 1:, :], c[:, -1:, :]], dim=1)
        curvature = nxt - 2.0 * c + prev
        helix_k = torch.relu(self.transient_helix_strength).to(dtype=c.dtype) * env_scale
        coil_k = torch.relu(self.coil_expansion_strength).to(dtype=c.dtype)

        # Helix-like smoothing on locally disordered segments, with mild expansion to
        # avoid over-collapse.
        f_helix = -helix_k * disorder.unsqueeze(-1) * curvature
        center = c.mean(dim=1, keepdim=True)
        radial = c - center
        f_coil = coil_k * disorder.unsqueeze(-1) * radial / torch.linalg.norm(radial, dim=-1, keepdim=True).clamp_min(1e-6)

        info = {
            "helix_proxy_mean": torch.linalg.norm(curvature, dim=-1).mean(dim=-1),
            "coil_expansion_mean": torch.linalg.norm(f_coil, dim=-1).mean(dim=-1),
        }
        return f_helix + f_coil, info

    def forward(self, c, top, nb_data, pe, sim_params):
        if not self._enabled(sim_params):
            f_idp = torch.zeros_like(c, device=self.dev)
            bsz = int(c.shape[0])
            info = {
                "enabled": False,
                "mean_fuzzy_force": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "hbond_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "sticker_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "bridge_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "helix_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "helix_propensity_mean": torch.full((bsz,), float(self.transient_helix_strength.detach().item()), dtype=c.dtype, device=c.device),
                "virtual_hbond_contacts": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "anti_collapse_force_mean": torch.zeros(bsz, dtype=c.dtype, device=c.device),
                "anti_collapse_overcollapse_rate": torch.zeros(bsz, dtype=c.dtype, device=c.device),
            }
            return f_idp, info

        ctx = self._prepare_step_ctx(c, top, nb_data, sim_params)
        f_hbond, info_h = self._pairwise_idp_hbond_force(c, top, nb_data, sim_params, ctx=ctx)
        sticker_bridge_backend = str(ctx.get("sticker_bridge_backend", "python")).strip().lower()
        if sticker_bridge_backend in {"rust_hip", "rust", "hip"}:
            f_sticker, info_st, f_bridge, info_b = self._pairwise_sticker_bridge_force_rust(c, top, nb_data, sim_params, ctx=ctx)
        else:
            f_sticker, info_st = self._pairwise_sticker_force(c, top, nb_data, sim_params, ctx=ctx)
            f_bridge, info_b = self._pairwise_llps_bridge_force(c, top, nb_data, sim_params, ctx=ctx)
        f_helix, info_s = self._transient_helix_force(c, top, sim_params, ctx=ctx)
        f_collapse, info_c = self._anti_collapse_force(c, top, nb_data, sim_params, ctx=ctx)
        f_idp = f_hbond + f_sticker + f_bridge + f_helix + f_collapse
        component_diag = _env_enabled("IDP_COMPONENT_FORCE_DIAGNOSTICS", "0")
        zero_vec = torch.zeros(c.shape[0], dtype=c.dtype, device=c.device)
        info = {
            "enabled": True,
            "mean_fuzzy_force": torch.linalg.norm(f_idp, dim=-1).mean(dim=-1),
            "hbond_force_mean": torch.linalg.norm(f_hbond, dim=-1).mean(dim=-1) if component_diag else zero_vec,
            "sticker_force_mean": torch.linalg.norm(f_sticker, dim=-1).mean(dim=-1) if component_diag else zero_vec,
            "bridge_force_mean": torch.linalg.norm(f_bridge, dim=-1).mean(dim=-1) if component_diag else zero_vec,
            "helix_force_mean": torch.linalg.norm(f_helix, dim=-1).mean(dim=-1) if component_diag else zero_vec,
            "helix_propensity_mean": torch.full((c.shape[0],), float(self.transient_helix_strength.detach().item()), dtype=c.dtype, device=c.device),
            **info_h,
            **info_st,
            **info_b,
            **info_s,
            **info_c,
        }
        return f_idp, info
