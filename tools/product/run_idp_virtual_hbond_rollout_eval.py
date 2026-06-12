#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Sequence

import torch

from theory.branches.idp_logic import IDPLogic
from tools.run_idp_virtual_hbond_eval import _knn_nb_data, _make_disordered_coords, _metrics_for_traj, _mock_top, _sim_params


def _rollout(
    *,
    init_coords: torch.Tensor,
    top,
    enabled: bool,
    frames: int,
    dt_step: float,
    damping: float,
    noise_scale: float,
    seed: int,
    ionic_strength: float,
    p_h: float,
    ptm_count: float,
    hydro_strength: float,
) -> Dict[str, Any]:
    device = init_coords.device
    mod = IDPLogic(device).to(device)
    params = _sim_params(enabled, ionic_strength, p_h, ptm_count, hydro_strength)
    coords = init_coords.clone()
    vel = torch.zeros_like(coords)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    traj = []
    force_norms = []
    virtual_contacts = []
    virtual_distance = []
    helicity_force = []
    coil_force = []

    with torch.inference_mode():
        for _ in range(int(frames)):
            nb_data = _knn_nb_data(coords.unsqueeze(0), k=12)
            force, info = mod(coords.unsqueeze(0), top=top, nb_data=nb_data, pe=None, sim_params=params)
            force = force.squeeze(0)
            noise = torch.randn(coords.shape, generator=gen, dtype=coords.dtype) * float(noise_scale)
            noise = noise.to(device=device)
            vel = float(damping) * vel + float(dt_step) * force + noise
            coords = coords + float(dt_step) * vel
            traj.append(coords.clone())
            force_norms.append(float(torch.linalg.norm(force, dim=-1).mean().item()))
            virtual_contacts.append(float(info.get("virtual_hbond_contacts", 0.0)))
            virtual_distance.append(float(info.get("virtual_hbond_mean_distance_A", 0.0)))
            helicity_force.append(float(info.get("helix_proxy_mean", 0.0)))
            coil_force.append(float(info.get("coil_expansion_mean", 0.0)))

    traj_t = torch.stack(traj, dim=0)
    metrics = _metrics_for_traj(traj_t)
    metrics.update(
        {
            "mean_force": float(sum(force_norms) / max(len(force_norms), 1)),
            "max_force": float(max(force_norms) if force_norms else 0.0),
            "virtual_hbond_contacts_mean": float(sum(virtual_contacts) / max(len(virtual_contacts), 1)),
            "virtual_hbond_mean_distance_A": float(sum(virtual_distance) / max(len(virtual_distance), 1)),
            "helix_proxy_force_mean": float(sum(helicity_force) / max(len(helicity_force), 1)),
            "coil_expansion_force_mean": float(sum(coil_force) / max(len(coil_force), 1)),
        }
    )
    return metrics


def run_eval(args: argparse.Namespace) -> Dict[str, Any]:
    device = torch.device(str(args.device))
    init_coords = _make_disordered_coords(
        n_res=int(args.n_res),
        frames=1,
        seed=int(args.seed),
        device=device,
        noise_scale=float(args.init_noise_scale),
    )[0]
    top = _mock_top(int(args.n_res), device=device)
    common = dict(
        init_coords=init_coords,
        top=top,
        frames=int(args.frames),
        dt_step=float(args.dt_step),
        damping=float(args.damping),
        noise_scale=float(args.rollout_noise_scale),
        ionic_strength=float(args.ionic_strength),
        p_h=float(args.p_h),
        ptm_count=float(args.ptm_count),
        hydro_strength=float(args.hydro_strength),
    )
    off = _rollout(enabled=False, seed=int(args.seed) + 11, **common)
    on = _rollout(enabled=True, seed=int(args.seed) + 17, **common)
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "device": str(device),
        "n_res": int(args.n_res),
        "frames": int(args.frames),
        "seed": int(args.seed),
        "dt_step": float(args.dt_step),
        "damping": float(args.damping),
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
        and abs(float(payload["delta_transient_helicity"])) + abs(float(payload["delta_contact_persistence"])) > 1e-6
    )
    out_json = str(args.out_json).strip() or f"/home/betelgeuze/분자동역학/runs/idp_virtual_hbond_rollout_eval_{dt.date.today().isoformat()}.json"
    out_md = str(args.out_md).strip() or f"/home/betelgeuze/분자동역학/runs/idp_virtual_hbond_rollout_eval_{dt.date.today().isoformat()}.md"
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# IDP Virtual HBond Rollout Eval",
        "",
        f"- pass: {payload['pass']}",
        f"- device: {payload['device']}",
        f"- frames: {payload['frames']}",
        f"- n_res: {payload['n_res']}",
        f"- delta_rg_mean: {payload['delta_rg_mean']}",
        f"- delta_sasa_proxy_mean: {payload['delta_sasa_proxy_mean']}",
        f"- delta_contact_persistence: {payload['delta_contact_persistence']}",
        f"- delta_transient_helicity: {payload['delta_transient_helicity']}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not payload["pass"]:
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run rollout-based evaluation for experimental IDP virtual-hbond branch.")
    p.add_argument("--n-res", type=int, default=64)
    p.add_argument("--frames", type=int, default=512)
    p.add_argument("--seed", type=int, default=41)
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--init-noise-scale", type=float, default=0.4)
    p.add_argument("--rollout-noise-scale", type=float, default=0.002)
    p.add_argument("--dt-step", type=float, default=0.05)
    p.add_argument("--damping", type=float, default=0.985)
    p.add_argument("--ionic-strength", type=float, default=0.15)
    p.add_argument("--p-h", dest="p_h", type=float, default=7.2)
    p.add_argument("--ptm-count", type=float, default=1.0)
    p.add_argument("--hydro-strength", type=float, default=1.0)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    run_eval(args)


if __name__ == "__main__":
    main()
