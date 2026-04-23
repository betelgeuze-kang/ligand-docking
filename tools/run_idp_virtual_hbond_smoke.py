#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch

from theory.branches.idp_logic import IDPLogic


def _make_disordered_coords(n_res: int, frames: int, seed: int, device: torch.device) -> torch.Tensor:
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    coords: List[torch.Tensor] = []
    base = torch.zeros((n_res, 3), dtype=torch.float32)
    base[:, 0] = torch.linspace(0.0, float(max(n_res - 1, 1)) * 1.4, n_res)
    drift = torch.randn((frames, n_res, 3), generator=gen, dtype=torch.float32) * 0.35
    bend = torch.zeros((frames, n_res, 3), dtype=torch.float32)
    t = torch.linspace(0.0, 3.14159, n_res).view(1, n_res)
    for f in range(frames):
        phase = float(f) / max(frames - 1, 1)
        bend[f, :, 1] = 1.5 * torch.sin(t + 3.0 * phase)
        bend[f, :, 2] = 0.8 * torch.cos(0.7 * t + 2.0 * phase)
    x = base.view(1, n_res, 3) + bend + drift
    return x.to(device=device)


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
    # Disorder-enriched residue ids.
    pattern = torch.tensor([1, 5, 6, 11, 14, 15, 16, 2], dtype=torch.long, device=device)
    residue_types = pattern.repeat((n_res + len(pattern) - 1) // len(pattern))[:n_res].view(1, n_res)
    return type("Top", (), {"residue_types": residue_types})()


def _run_branch(c: torch.Tensor, top, enabled: bool) -> Dict[str, Any]:
    device = c.device
    mod = IDPLogic(device).to(device)
    nb_data = _knn_nb_data(c, k=12)
    sim_params = {
        "idp_virtual_hbond_enabled": 1 if enabled else 0,
        "ionic_strength": 0.15,
        "pH": 7.2,
        "ptm_count": 1,
        "hydro_strength": 1.0,
    }
    forces = []
    infos: List[Dict[str, Any]] = []
    for frame in c:
        f, info = mod(frame.unsqueeze(0), top=top, nb_data=nb_data, pe=None, sim_params=sim_params)
        forces.append(f)
        infos.append(info)
    f_all = torch.cat(forces, dim=0)
    mean_force = float(torch.linalg.norm(f_all, dim=-1).mean().item())
    max_force = float(torch.linalg.norm(f_all, dim=-1).amax().item())
    out = {
        "enabled": bool(enabled),
        "frames": int(c.shape[0]),
        "n_res": int(c.shape[1]),
        "mean_force": mean_force,
        "max_force": max_force,
        "virtual_hbond_contacts_mean": float(sum(float(i.get("virtual_hbond_contacts", 0.0)) for i in infos) / max(len(infos), 1)),
        "virtual_hbond_mean_distance_A": float(sum(float(i.get("virtual_hbond_mean_distance_A", 0.0)) for i in infos) / max(len(infos), 1)),
        "helix_proxy_mean": float(sum(float(i.get("helix_proxy_mean", 0.0)) for i in infos) / max(len(infos), 1)),
        "coil_expansion_mean": float(sum(float(i.get("coil_expansion_mean", 0.0)) for i in infos) / max(len(infos), 1)),
    }
    return out


def run_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    device = torch.device(str(args.device))
    coords = _make_disordered_coords(
        n_res=int(args.n_res),
        frames=int(args.frames),
        seed=int(args.seed),
        device=device,
    )
    top = _mock_top(int(args.n_res), device=device)
    off = _run_branch(coords, top=top, enabled=False)
    on = _run_branch(coords, top=top, enabled=True)
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "device": str(device),
        "n_res": int(args.n_res),
        "frames": int(args.frames),
        "seed": int(args.seed),
        "off": off,
        "on": on,
        "delta_mean_force": float(on["mean_force"] - off["mean_force"]),
        "delta_virtual_contacts": float(on["virtual_hbond_contacts_mean"] - off["virtual_hbond_contacts_mean"]),
        "pass": bool(on["mean_force"] > 0.0 and on["virtual_hbond_contacts_mean"] >= 0.0),
    }
    out_json = str(args.out_json).strip() or f"runs/idp_virtual_hbond_smoke_{dt.date.today().isoformat()}.json"
    out_md = str(args.out_md).strip() or f"runs/idp_virtual_hbond_smoke_{dt.date.today().isoformat()}.md"
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# IDP Virtual HBond Smoke",
        "",
        f"- pass: {payload['pass']}",
        f"- device: {payload['device']}",
        f"- n_res: {payload['n_res']}",
        f"- frames: {payload['frames']}",
        f"- off.mean_force: {payload['off']['mean_force']}",
        f"- on.mean_force: {payload['on']['mean_force']}",
        f"- on.virtual_hbond_contacts_mean: {payload['on']['virtual_hbond_contacts_mean']}",
        f"- on.virtual_hbond_mean_distance_A: {payload['on']['virtual_hbond_mean_distance_A']}",
        f"- on.helix_proxy_mean: {payload['on']['helix_proxy_mean']}",
        f"- on.coil_expansion_mean: {payload['on']['coil_expansion_mean']}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["out_json"] = out_json
    payload["out_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run isolated smoke validation for experimental IDP virtual-hbond branch.")
    p.add_argument("--n-res", type=int, default=48)
    p.add_argument("--frames", type=int, default=24)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_smoke(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
