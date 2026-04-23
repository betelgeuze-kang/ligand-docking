import math
import torch

from tools.pdb_loader import load_native_structure
from core.config import config
from core.definitions import ResearchConstants
from core.topology import TopologyFactory
from core.forcefield import ForceField


def calculate_rg(coords):
    center = coords.mean(dim=0, keepdim=True)
    return torch.sqrt(((coords - center).pow(2).sum(dim=-1)).mean()).item()


def calculate_sasa_proxy(coords, cutoff=8.0, atom_radius=1.7, probe_radius=1.4):
    """
    Lightweight SASA proxy.
    인접 원자 수가 많을수록 노출도를 낮게 보는 간단한 근사치입니다.
    """
    n = coords.shape[0]
    if n == 0:
        return 0.0

    from tools.idp_3bead_common import knn_nb_data

    k = int(max(8, min(max(n - 1, 1), 24)))
    nb_idx, nb_dist, nb_mask = knn_nb_data(coords.unsqueeze(0), k=k)
    neigh_mask = (nb_mask > 0.5) & (nb_idx >= 0) & (nb_dist < float(cutoff))
    neigh_count = neigh_mask[0].sum(dim=-1).float()
    exposure = 1.0 / (1.0 + neigh_count)

    area_per_atom = 4.0 * math.pi * (atom_radius + probe_radius) ** 2
    return float((exposure * area_per_atom).sum().item())


def calculate_proxy_energy(coords, bond_eq=3.8, nonbond_scale=4.0, bond_weight=1.0, rep_weight=0.1):
    """
    Lightweight energy proxy for regression checks.
    - bond term: 인접 좌표 간 길이 편차
    - nonbond term: 비인접 원자 간 soft repulsion
    """
    n = coords.shape[0]
    if n <= 1:
        return 0.0

    bond_lengths = (coords[1:] - coords[:-1]).norm(dim=-1)
    bond_energy = ((bond_lengths - bond_eq) ** 2).sum()

    dmat = torch.cdist(coords, coords)
    tri_mask = torch.triu(torch.ones((n, n), dtype=torch.bool, device=coords.device), diagonal=2)
    nonbond_dist = dmat[tri_mask]
    rep_energy = torch.exp(-nonbond_dist / nonbond_scale).sum()

    energy = bond_weight * bond_energy + rep_weight * rep_energy
    return float(energy.item())


def _run_placeholder_target(native_coords, steps, noise_scale, seed):
    # Legacy lightweight placeholder kept for compatibility/debug use.
    scale = min(max(float(steps), 0.0), 5000.0) / 5000.0
    generator = torch.Generator(device=native_coords.device)
    generator.manual_seed(int(seed))
    noise = torch.randn(native_coords.shape, generator=generator, device=native_coords.device)
    return native_coords + noise * (noise_scale * scale)


def _run_physics_refinement_target(target, native_coords, steps, noise_scale, seed, **kwargs):
    t_conf = ResearchConstants.CHALLENGES[target]
    n_res = t_conf["n_res"]
    refinement_dt = float(kwargs.get("refinement_dt", 1e-5))
    restraint_k = float(kwargs.get("restraint_k", 3.0))
    force_clip = float(kwargs.get("force_clip", 200.0))
    energy_ref_cutoff = float(kwargs.get("energy_ref_cutoff", 14.0))
    energy_ref_max_neighbors = int(kwargs.get("energy_ref_max_neighbors", 160))
    force_backend = str(kwargs.get("force_backend", "auto"))
    ff_params = kwargs.get("ff_params", {"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2})
    neighbor_settings = kwargs.get(
        "neighbor_settings",
        {
            "grid_spacing": 12.0,
            "cutoff": 12.0,
            "skin": 2.0,
            "max_neighbors": 100,
            "max_atoms_per_cell": 64,
            "rebuild_stride": 4,
        },
    )

    native = native_coords.to(config.DEVICE, dtype=torch.float32)
    top = TopologyFactory(n_res, t_conf["type"], t_conf["box"], config.DEVICE, target_name=target)
    ff = ForceField(top, params=ff_params, neighbor_settings=neighbor_settings, force_backend=force_backend).to(config.DEVICE)

    generator = torch.Generator(device=native.device)
    generator.manual_seed(int(seed))
    c = native.unsqueeze(0) + torch.randn((1, native.shape[0], 3), generator=generator, device=native.device) * float(
        noise_scale
    )
    native_batch = native.unsqueeze(0)

    with torch.no_grad():
        _, pe_start_raw = ff.compute(c, None)
        energy_source = "backend_raw"
        try:
            _, pe_start_ref = ff.compute_reference_pytorch(
                c,
                cutoff=energy_ref_cutoff,
                max_neighbors=energy_ref_max_neighbors,
                skin=0.0,
            )
            pe_start = pe_start_ref
            energy_source = "reference_pytorch"
        except Exception:
            pe_start = pe_start_raw
        for _ in range(max(int(steps), 0)):
            f_core, _ = ff.compute(c, None)
            f_total = f_core - restraint_k * (c - native_batch)
            f_total = torch.clamp(f_total, min=-force_clip, max=force_clip)
            c = c + refinement_dt * f_total
        _, pe_end_raw = ff.compute(c, None)
        if energy_source == "reference_pytorch":
            try:
                _, pe_end_ref = ff.compute_reference_pytorch(
                    c,
                    cutoff=energy_ref_cutoff,
                    max_neighbors=energy_ref_max_neighbors,
                    skin=0.0,
                )
                pe_end = pe_end_ref
            except Exception:
                pe_end = pe_end_raw
                energy_source = "backend_raw"
        else:
            pe_end = pe_end_raw

    pe_start_val = float(pe_start.squeeze().item()) if pe_start.numel() > 0 else 0.0
    pe_end_val = float(pe_end.squeeze().item()) if pe_end.numel() > 0 else 0.0
    return c.squeeze(0), pe_start_val, pe_end_val, energy_source


def run_target(target, steps=1000, noise_scale=0.02, seed=42, return_metrics=False, **kwargs):
    """
    Validation/benchmark 공통 엔트리.
    기본 모드(mode='physics')는 물리 force 기반의 restrained refinement를 수행합니다.
    필요 시 mode='placeholder'로 legacy noise 경로를 사용할 수 있습니다.
    """
    native_coords, _ = load_native_structure(target)
    if native_coords is None:
        raise FileNotFoundError(f"Native structure for {target} was not found.")

    mode = str(kwargs.get("mode", "physics")).lower()
    physics_kwargs = dict(kwargs)
    if mode in ("physics_unrestrained", "unrestrained"):
        physics_kwargs["restraint_k"] = float(physics_kwargs.get("restraint_k", 0.0))
        mode_for_exec = "physics"
    else:
        mode_for_exec = mode

    if mode_for_exec == "placeholder":
        result_coords = _run_placeholder_target(native_coords, steps=steps, noise_scale=noise_scale, seed=seed)
        energy_start = calculate_proxy_energy(native_coords)
        energy_end = calculate_proxy_energy(result_coords)
        energy_metric_source = "proxy_placeholder"
    else:
        physics_out = _run_physics_refinement_target(
            target=target,
            native_coords=native_coords,
            steps=steps,
            noise_scale=noise_scale,
            seed=seed,
            **physics_kwargs,
        )
        if not isinstance(physics_out, tuple) or len(physics_out) < 3:
            raise RuntimeError("physics refinement path returned invalid result tuple")
        result_coords = physics_out[0]
        energy_start = physics_out[1]
        energy_end = physics_out[2]
        energy_metric_source = str(physics_out[3]) if len(physics_out) >= 4 else "unknown"

    if not return_metrics:
        return result_coords

    energy_drift_abs = abs(energy_end - energy_start)
    energy_drift_ratio = energy_drift_abs / (abs(energy_start) + 1e-8)
    proxy_energy_start = calculate_proxy_energy(native_coords)
    proxy_energy_end = calculate_proxy_energy(result_coords)
    proxy_energy_drift_abs = abs(proxy_energy_end - proxy_energy_start)
    proxy_energy_drift_ratio = proxy_energy_drift_abs / (abs(proxy_energy_start) + 1e-8)

    metrics = {
        "mode": mode,
        "energy_metric_source": energy_metric_source,
        "energy_start": energy_start,
        "energy_end": energy_end,
        "energy_drift_abs": energy_drift_abs,
        "energy_drift_ratio": energy_drift_ratio,
        "proxy_energy_start": proxy_energy_start,
        "proxy_energy_end": proxy_energy_end,
        "proxy_energy_drift_abs": proxy_energy_drift_abs,
        "proxy_energy_drift_ratio": proxy_energy_drift_ratio,
        "native_rg": calculate_rg(native_coords),
        "result_rg": calculate_rg(result_coords),
        "native_sasa_proxy": calculate_sasa_proxy(native_coords),
        "result_sasa_proxy": calculate_sasa_proxy(result_coords),
    }
    return result_coords, metrics
