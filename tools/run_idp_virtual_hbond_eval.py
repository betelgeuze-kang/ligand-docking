#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch

from run_validation import calculate_rg, calculate_sasa_proxy
from theory.branches.idp_logic import IDPLogic


def _make_disordered_coords(
    n_res: int,
    frames: int,
    seed: int,
    device: torch.device,
    noise_scale: float,
) -> torch.Tensor:
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    base = torch.zeros((n_res, 3), dtype=torch.float32)
    base[:, 0] = torch.linspace(0.0, float(max(n_res - 1, 1)) * 1.45, n_res)
    t = torch.linspace(0.0, 2.0 * math.pi, n_res).view(1, n_res)
    bend = torch.zeros((frames, n_res, 3), dtype=torch.float32)
    for f in range(frames):
        phase = 2.0 * math.pi * (float(f) / max(frames - 1, 1))
        bend[f, :, 1] = 1.8 * torch.sin(t + phase)
        bend[f, :, 2] = 1.1 * torch.cos(0.6 * t + 0.7 * phase)
    drift = torch.randn((frames, n_res, 3), generator=gen, dtype=torch.float32) * float(noise_scale)
    coords = base.view(1, n_res, 3) + bend + drift
    return coords.to(device=device)


def _knn_nb_data(c: torch.Tensor, k: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    bsz, n_atoms, _ = c.shape
    dmat = torch.cdist(c, c)
    eye = torch.eye(n_atoms, device=c.device, dtype=torch.bool).view(1, n_atoms, n_atoms)
    dmat = dmat.masked_fill(eye, float("inf"))
    k_eff = int(max(1, min(k, n_atoms - 1)))
    nb_dist, nb_idx = torch.topk(dmat, k=k_eff, largest=False, dim=-1)
    nb_mask = torch.isfinite(nb_dist).float()
    nb_dist = torch.where(torch.isfinite(nb_dist), nb_dist, torch.zeros_like(nb_dist))
    return nb_idx.long(), nb_dist.float(), nb_mask.float()


def _mock_top(n_res: int, device: torch.device):
    pattern = torch.tensor([1, 5, 6, 11, 14, 15, 16, 2], dtype=torch.long, device=device)
    residue_types = pattern.repeat((n_res + len(pattern) - 1) // len(pattern))[:n_res].view(1, n_res)
    return type("Top", (), {"residue_types": residue_types})()


def _end_to_end(c: torch.Tensor) -> float:
    if c.shape[0] < 2:
        return 0.0
    return float(torch.linalg.norm(c[-1] - c[0]).item())


def _contact_persistence(traj: torch.Tensor, cutoff: float = 8.0) -> float:
    if traj.shape[1] < 6:
        return 0.0
    dmat = torch.cdist(traj, traj)
    idx = torch.arange(traj.shape[1], device=traj.device)
    sep = torch.abs(idx.view(-1, 1) - idx.view(1, -1))
    mask = (sep >= 6).view(1, traj.shape[1], traj.shape[1])
    contacts = ((dmat < float(cutoff)) & mask).float()
    if contacts.numel() == 0:
        return 0.0
    per_pair = contacts.mean(dim=0)
    return float(per_pair.mean().item())


def _transient_helicity_proxy(traj: torch.Tensor) -> float:
    if traj.shape[1] < 3:
        return 0.0
    prev = traj[:, :-2, :]
    curr = traj[:, 1:-1, :]
    nxt = traj[:, 2:, :]
    curvature = torch.linalg.norm(nxt - 2.0 * curr + prev, dim=-1)
    helix_like = torch.exp(-torch.square(curvature / 1.2))
    return float(helix_like.mean().item())


def _metrics_for_traj(traj: torch.Tensor) -> Dict[str, float]:
    rg_vals = [float(calculate_rg(frame)) for frame in traj]
    sasa_vals = [float(calculate_sasa_proxy(frame)) for frame in traj]
    e2e_vals = [_end_to_end(frame) for frame in traj]
    return {
        "rg_mean": float(sum(rg_vals) / max(len(rg_vals), 1)),
        "sasa_proxy_mean": float(sum(sasa_vals) / max(len(sasa_vals), 1)),
        "end_to_end_mean": float(sum(e2e_vals) / max(len(e2e_vals), 1)),
        "contact_persistence": _contact_persistence(traj),
        "transient_helicity": _transient_helicity_proxy(traj),
    }


def _sim_params(enabled: bool, ionic_strength: float, p_h: float, ptm_count: float, hydro_strength: float) -> Dict[str, Any]:
    return {
        "idp_virtual_hbond_enabled": 1 if enabled else 0,
        "ionic_strength": float(ionic_strength),
        "pH": float(p_h),
        "ptm_count": float(ptm_count),
        "hydro_strength": float(hydro_strength),
    }


def _run_condition(
    coords: torch.Tensor,
    top,
    enabled: bool,
    ionic_strength: float,
    p_h: float,
    ptm_count: float,
    hydro_strength: float,
) -> Dict[str, Any]:
    device = coords.device
    mod = IDPLogic(device).to(device)
    nb_data = _knn_nb_data(coords, k=12)
    params = _sim_params(enabled, ionic_strength, p_h, ptm_count, hydro_strength)
    forces: List[torch.Tensor] = []
    infos: List[Dict[str, Any]] = []
    with torch.inference_mode():
        for frame in coords:
            f, info = mod(frame.unsqueeze(0), top=top, nb_data=nb_data, pe=None, sim_params=params)
            forces.append(f)
            infos.append(info)
    force_all = torch.cat(forces, dim=0)
    metrics = _metrics_for_traj(coords)
    metrics.update(
        {
            "mean_force": float(torch.linalg.norm(force_all, dim=-1).mean().item()),
            "max_force": float(torch.linalg.norm(force_all, dim=-1).amax().item()),
            "virtual_hbond_contacts_mean": float(
                sum(float(i.get("virtual_hbond_contacts", 0.0)) for i in infos) / max(len(infos), 1)
            ),
            "virtual_hbond_mean_distance_A": float(
                sum(float(i.get("virtual_hbond_mean_distance_A", 0.0)) for i in infos) / max(len(infos), 1)
            ),
            "helix_proxy_force_mean": float(
                sum(float(i.get("helix_proxy_mean", 0.0)) for i in infos) / max(len(infos), 1)
            ),
            "coil_expansion_force_mean": float(
                sum(float(i.get("coil_expansion_mean", 0.0)) for i in infos) / max(len(infos), 1)
            ),
        }
    )
    return metrics


def run_eval(args: argparse.Namespace) -> Dict[str, Any]:
    device = torch.device(str(args.device))
    coords = _make_disordered_coords(
        n_res=int(args.n_res),
        frames=int(args.frames),
        seed=int(args.seed),
        device=device,
        noise_scale=float(args.noise_scale),
    )
    top = _mock_top(int(args.n_res), device=device)

    off = _run_condition(
        coords,
        top=top,
        enabled=False,
        ionic_strength=float(args.ionic_strength),
        p_h=float(args.p_h),
        ptm_count=float(args.ptm_count),
        hydro_strength=float(args.hydro_strength),
    )
    on = _run_condition(
        coords,
        top=top,
        enabled=True,
        ionic_strength=float(args.ionic_strength),
        p_h=float(args.p_h),
        ptm_count=float(args.ptm_count),
        hydro_strength=float(args.hydro_strength),
    )

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "device": str(device),
        "n_res": int(args.n_res),
        "frames": int(args.frames),
        "seed": int(args.seed),
        "ionic_strength": float(args.ionic_strength),
        "pH": float(args.p_h),
        "ptm_count": float(args.ptm_count),
        "hydro_strength": float(args.hydro_strength),
        "off": off,
        "on": on,
        "delta_rg_mean": float(on["rg_mean"] - off["rg_mean"]),
        "delta_sasa_proxy_mean": float(on["sasa_proxy_mean"] - off["sasa_proxy_mean"]),
        "delta_contact_persistence": float(on["contact_persistence"] - off["contact_persistence"]),
        "delta_transient_helicity": float(on["transient_helicity"] - off["transient_helicity"]),
    }
    payload["pass"] = bool(
        float(on["mean_force"]) > 0.0
        and float(on["virtual_hbond_mean_distance_A"]) > 0.0
        and float(on["transient_helicity"]) >= float(off["transient_helicity"])
    )

    out_json = str(args.out_json).strip() or f"runs/idp_virtual_hbond_eval_{dt.date.today().isoformat()}.json"
    out_md = str(args.out_md).strip() or f"runs/idp_virtual_hbond_eval_{dt.date.today().isoformat()}.md"
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# IDP Virtual HBond Eval",
        "",
        f"- pass: {payload['pass']}",
        f"- device: {payload['device']}",
        f"- frames: {payload['frames']}",
        f"- n_res: {payload['n_res']}",
        f"- ionic_strength: {payload['ionic_strength']}",
        f"- pH: {payload['pH']}",
        f"- ptm_count: {payload['ptm_count']}",
        f"- hydro_strength: {payload['hydro_strength']}",
        "",
        "## Off",
        f"- rg_mean: {off['rg_mean']}",
        f"- sasa_proxy_mean: {off['sasa_proxy_mean']}",
        f"- end_to_end_mean: {off['end_to_end_mean']}",
        f"- contact_persistence: {off['contact_persistence']}",
        f"- transient_helicity: {off['transient_helicity']}",
        "",
        "## On",
        f"- rg_mean: {on['rg_mean']}",
        f"- sasa_proxy_mean: {on['sasa_proxy_mean']}",
        f"- end_to_end_mean: {on['end_to_end_mean']}",
        f"- contact_persistence: {on['contact_persistence']}",
        f"- transient_helicity: {on['transient_helicity']}",
        f"- virtual_hbond_mean_distance_A: {on['virtual_hbond_mean_distance_A']}",
        "",
        "## Delta",
        f"- delta_rg_mean: {payload['delta_rg_mean']}",
        f"- delta_sasa_proxy_mean: {payload['delta_sasa_proxy_mean']}",
        f"- delta_contact_persistence: {payload['delta_contact_persistence']}",
        f"- delta_transient_helicity: {payload['delta_transient_helicity']}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["out_json"] = out_json
    payload["out_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run isolated evaluation for experimental IDP virtual-hbond branch.")
    p.add_argument("--n-res", type=int, default=64)
    p.add_argument("--frames", type=int, default=64)
    p.add_argument("--seed", type=int, default=23)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--noise-scale", type=float, default=0.4)
    p.add_argument("--ionic-strength", type=float, default=0.15)
    p.add_argument("--p-h", dest="p_h", type=float, default=7.2)
    p.add_argument("--ptm-count", type=float, default=1.0)
    p.add_argument("--hydro-strength", type=float, default=1.0)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_eval(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
