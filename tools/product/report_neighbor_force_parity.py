#!/usr/bin/env python3

import argparse
import json
import os
from typing import Dict, List, Tuple

import pandas as pd
import torch

from core.config import config
from core.definitions import ResearchConstants
from core.forcefield import ForceField
from core.topology import TopologyFactory
from tools.pdb_loader import load_native_structure


def _parse_targets(spec: str) -> List[str]:
    if spec.strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in spec.split(",") if x.strip()]


def _native_coords(target: str, n_res: int) -> torch.Tensor:
    coords, _ = load_native_structure(target)
    if coords is None:
        coords = torch.linspace(0, n_res - 1, n_res, device=config.DEVICE).view(1, n_res, 1).repeat(1, 1, 3)
    elif coords.dim() == 2:
        coords = coords.unsqueeze(0)
    return coords.to(config.DEVICE, dtype=torch.float32)


def _nb_set(nb, b: int, i: int):
    idx, _, mask = nb
    m = mask[b, i].bool() & (idx[b, i] >= 0)
    return set(idx[b, i][m].tolist())


def _mean_jaccard(nb_a, nb_b) -> float:
    idx_a, _, mask_a = nb_a
    idx_b, _, mask_b = nb_b
    bsz, n, _ = idx_a.shape
    vals = []
    for b in range(bsz):
        for i in range(n):
            sa = set(idx_a[b, i][mask_a[b, i].bool() & (idx_a[b, i] >= 0)].tolist())
            sb = set(idx_b[b, i][mask_b[b, i].bool() & (idx_b[b, i] >= 0)].tolist())
            union = sa | sb
            if not union:
                vals.append(1.0)
            else:
                vals.append(len(sa & sb) / len(union))
    return float(sum(vals) / max(len(vals), 1))


def _avg_neighbor_count(nb) -> float:
    _, _, mask = nb
    return float(mask.bool().sum(dim=-1).float().mean().item())


def _per_atom_jaccard(nb_a, nb_b) -> torch.Tensor:
    idx_a, _, _ = nb_a
    bsz, n, _ = idx_a.shape
    out = torch.zeros((bsz, n), dtype=torch.float32, device=idx_a.device)
    for b in range(bsz):
        for i in range(n):
            sa = _nb_set(nb_a, b, i)
            sb = _nb_set(nb_b, b, i)
            union = sa | sb
            if not union:
                out[b, i] = 1.0
            else:
                out[b, i] = float(len(sa & sb) / len(union))
    return out


def _force_diff_stats(f_ref: torch.Tensor, f_test: torch.Tensor, clip: float = 200.0) -> Dict[str, float]:
    diff = f_ref - f_test
    rmse_raw = torch.sqrt(torch.mean(diff * diff)).item()
    max_abs = diff.abs().max().item()

    f_ref_c = torch.clamp(f_ref, min=-clip, max=clip)
    f_test_c = torch.clamp(f_test, min=-clip, max=clip)
    diff_c = f_ref_c - f_test_c
    rmse_clip = torch.sqrt(torch.mean(diff_c * diff_c)).item()
    denom = torch.sqrt(torch.mean(f_ref_c * f_ref_c)).item() + 1e-8
    rel_rmse = rmse_clip / denom
    return {
        "rmse_raw": float(rmse_raw),
        "rmse_clipped": float(rmse_clip),
        "rel_rmse_clipped": float(rel_rmse),
        "max_abs": float(max_abs),
    }


def _minimum_image_distance(coords_b: torch.Tensor, i: int, j: int, box: torch.Tensor) -> float:
    dr = coords_b[i] - coords_b[j]
    dr -= box * torch.floor(dr / box + 0.5)
    return float(torch.sqrt(torch.clamp((dr * dr).sum(), min=1e-12)).item())


def _safe_mean(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns or len(df) == 0:
        return 0.0
    return float(df[col].mean())


def _rows_to_df(rows: List[dict], columns: List[str]) -> pd.DataFrame:
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=columns)


def run_parity(
    targets: List[str],
    samples: int,
    noise: float,
    neighbor_settings: Dict[str, float],
    out_target_csv: str,
    out_sample_csv: str,
    out_atom_csv: str,
    out_pair_csv: str,
    out_json: str,
    clip: float,
    topk_atoms: int,
    topk_pairs_per_atom: int,
    outlier_mode: str,
):
    os.environ["FORCE_RUST_HIP"] = "1"
    os.environ["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"

    target_rows = []
    sample_rows = []
    atom_rows = []
    pair_rows = []

    comparison_pairs = (
        ("e2e", "End-to-end parity: PyTorch(nb_py) vs Rust(nb_rs)"),
        ("kernel_shared_py", "Kernel-only on shared Python neighbor list"),
        ("kernel_shared_rs", "Kernel-only on shared Rust neighbor list"),
        ("nblist_effect_py", "Neighbor-list-only effect in PyTorch"),
        ("nblist_effect_rs", "Neighbor-list-only effect in Rust"),
    )

    outlier_map = {
        "end_to_end": "e2e",
        "shared_py_nblist": "kernel_shared_py",
        "shared_rs_nblist": "kernel_shared_rs",
    }
    outlier_comp = outlier_map[outlier_mode]

    for target in targets:
        conf = ResearchConstants.CHALLENGES[target]
        n_res = conf["n_res"]
        top = TopologyFactory(n_res, conf["type"], conf["box"], config.DEVICE, target_name=target)
        ff = ForceField(
            top,
            params={"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2},
            neighbor_settings=neighbor_settings,
            force_backend="auto",
        ).to(config.DEVICE)

        base = _native_coords(target, n_res)
        box = torch.as_tensor(conf["box"], dtype=torch.float32, device=config.DEVICE).view(1, 1, 3)

        metrics_acc = {
            "neighbor_jaccard": [],
            "neighbor_count_py": [],
            "neighbor_count_rs": [],
            "rs_neighbor_saturated": [],
            "rs_cell_overflow": [],
            "rs_saturated_atoms": [],
            "rs_max_cell_count": [],
            "rs_builder_max_neighbors": [],
            "rs_builder_max_atoms_per_cell": [],
            "py_saturated_atoms": [],
            "py_max_required_neighbors": [],
            "py_effective_max_neighbors": [],
        }
        for key, _ in comparison_pairs:
            metrics_acc[f"{key}_rmse_raw"] = []
            metrics_acc[f"{key}_rmse_clipped"] = []
            metrics_acc[f"{key}_rel_rmse_clipped"] = []
            metrics_acc[f"{key}_max_abs"] = []

        for sample_idx in range(samples):
            c = base + torch.randn_like(base) * noise
            c = torch.remainder(c, box)

            # Compare on model coords (CA+SC when active) to isolate neighbor/kernel parity.
            coords_model = c.float()
            if top.use_virtual_sc:
                c_sc = top.compute_virtual_sc_coords(coords_model)
                coords_model = torch.cat([coords_model, c_sc], dim=1)

            runtime = {
                "box_size": float(top.box_size[0].item()),
                "sigma": 3.8,
                "eps_solv": 25.0,
            }
            nb_py = ff.sh.get_neighbor_data(coords_model, force_rebuild=True)
            nb_rs = ff.rust_backend.build_neighbor_list(
                coords_model.float(),
                box_size=runtime["box_size"],
                cutoff=float(ff.sh.list_cutoff),
                max_neighbors=int(ff.sh.max_neighbors),
                grid_dims=ff.sh.grid_dims,
                max_atoms_per_cell=int(ff.sh.max_atoms_per_cell),
            )
            rs_stats = dict(getattr(ff.rust_backend, "last_neighbor_build_stats", {}) or {})
            py_saturated_atoms = int(getattr(ff.sh, "_last_neighbor_saturated_atoms", 0))
            py_max_required_neighbors = int(getattr(ff.sh, "_last_max_required_neighbors", 0))
            py_effective_max_neighbors = int(getattr(ff.sh, "max_neighbors", 0))

            jacc = _mean_jaccard(nb_py, nb_rs)
            ncnt_py = _avg_neighbor_count(nb_py)
            ncnt_rs = _avg_neighbor_count(nb_rs)
            metrics_acc["neighbor_jaccard"].append(jacc)
            metrics_acc["neighbor_count_py"].append(ncnt_py)
            metrics_acc["neighbor_count_rs"].append(ncnt_rs)
            metrics_acc["rs_neighbor_saturated"].append(1.0 if rs_stats.get("neighbor_saturated", False) else 0.0)
            metrics_acc["rs_cell_overflow"].append(1.0 if rs_stats.get("cell_overflow", False) else 0.0)
            metrics_acc["rs_saturated_atoms"].append(float(rs_stats.get("saturated_atoms", 0)))
            metrics_acc["rs_max_cell_count"].append(float(rs_stats.get("max_cell_count", 0)))
            metrics_acc["rs_builder_max_neighbors"].append(float(rs_stats.get("max_neighbors", 0)))
            metrics_acc["rs_builder_max_atoms_per_cell"].append(float(rs_stats.get("max_atoms_per_cell", 0)))
            metrics_acc["py_saturated_atoms"].append(float(py_saturated_atoms))
            metrics_acc["py_max_required_neighbors"].append(float(py_max_required_neighbors))
            metrics_acc["py_effective_max_neighbors"].append(float(py_effective_max_neighbors))

            # Cross-matrix for list-vs-kernel attribution.
            f_py_py, _ = ff._compute_nonbonded_pytorch(coords_model, nb_py, to_fp32=True)
            f_py_rs, _ = ff._compute_nonbonded_pytorch(coords_model, nb_rs, to_fp32=True)
            f_rs_py, _ = ff.rust_backend.compute_nonbonded(coords_model.float(), nb_py, runtime)
            f_rs_rs, _ = ff.rust_backend.compute_nonbonded(coords_model.float(), nb_rs, runtime)

            comp_forces: Dict[str, Tuple[torch.Tensor, torch.Tensor]] = {
                "e2e": (f_py_py, f_rs_rs),
                "kernel_shared_py": (f_py_py, f_rs_py),
                "kernel_shared_rs": (f_py_rs, f_rs_rs),
                "nblist_effect_py": (f_py_py, f_py_rs),
                "nblist_effect_rs": (f_rs_py, f_rs_rs),
            }

            sample_row = {
                "target": target,
                "sample_idx": int(sample_idx),
                "neighbor_jaccard": float(jacc),
                "neighbor_count_py": float(ncnt_py),
                "neighbor_count_rs": float(ncnt_rs),
                "rs_neighbor_saturated": bool(rs_stats.get("neighbor_saturated", False)),
                "rs_cell_overflow": bool(rs_stats.get("cell_overflow", False)),
                "rs_saturated_atoms": int(rs_stats.get("saturated_atoms", 0)),
                "rs_max_cell_count": int(rs_stats.get("max_cell_count", 0)),
                "rs_builder_max_neighbors": int(rs_stats.get("max_neighbors", 0)),
                "rs_builder_max_atoms_per_cell": int(rs_stats.get("max_atoms_per_cell", 0)),
                "py_saturated_atoms": int(py_saturated_atoms),
                "py_max_required_neighbors": int(py_max_required_neighbors),
                "py_effective_max_neighbors": int(py_effective_max_neighbors),
            }
            for key, _desc in comparison_pairs:
                stats = _force_diff_stats(comp_forces[key][0], comp_forces[key][1], clip=clip)
                metrics_acc[f"{key}_rmse_raw"].append(stats["rmse_raw"])
                metrics_acc[f"{key}_rmse_clipped"].append(stats["rmse_clipped"])
                metrics_acc[f"{key}_rel_rmse_clipped"].append(stats["rel_rmse_clipped"])
                metrics_acc[f"{key}_max_abs"].append(stats["max_abs"])
                sample_row[f"{key}_rmse_raw"] = stats["rmse_raw"]
                sample_row[f"{key}_rmse_clipped"] = stats["rmse_clipped"]
                sample_row[f"{key}_rel_rmse_clipped"] = stats["rel_rmse_clipped"]
                sample_row[f"{key}_max_abs"] = stats["max_abs"]
            sample_rows.append(sample_row)

            f_ref, f_test = comp_forces[outlier_comp]
            diff = f_ref - f_test
            atom_diff_l2 = torch.norm(diff, dim=-1)
            atom_jacc = _per_atom_jaccard(nb_py, nb_rs)
            _, _, nb_mask_py = nb_py
            _, _, nb_mask_rs = nb_rs
            box_vec = top.box_size.to(dtype=torch.float32, device=coords_model.device)
            bsz = atom_diff_l2.shape[0]
            n_atoms = atom_diff_l2.shape[1]
            topk = min(int(topk_atoms), int(n_atoms))

            for b in range(bsz):
                top_vals, top_idxs = torch.topk(atom_diff_l2[b], k=topk, largest=True)
                coords_b = coords_model[b]
                for rank in range(topk):
                    atom_i = int(top_idxs[rank].item())
                    force_l2 = float(top_vals[rank].item())
                    atom_rows.append(
                        {
                            "target": target,
                            "sample_idx": int(sample_idx),
                            "batch_idx": int(b),
                            "outlier_mode": outlier_mode,
                            "rank": int(rank + 1),
                            "atom_idx": atom_i,
                            "force_diff_l2": force_l2,
                            "force_diff_abs_x": float(abs(diff[b, atom_i, 0].item())),
                            "force_diff_abs_y": float(abs(diff[b, atom_i, 1].item())),
                            "force_diff_abs_z": float(abs(diff[b, atom_i, 2].item())),
                            "force_ref_norm": float(torch.norm(f_ref[b, atom_i]).item()),
                            "force_test_norm": float(torch.norm(f_test[b, atom_i]).item()),
                            "atom_neighbor_jaccard": float(atom_jacc[b, atom_i].item()),
                            "atom_neighbor_count_py": int(nb_mask_py[b, atom_i].bool().sum().item()),
                            "atom_neighbor_count_rs": int(nb_mask_rs[b, atom_i].bool().sum().item()),
                        }
                    )

                    py_set = _nb_set(nb_py, b, atom_i)
                    rs_set = _nb_set(nb_rs, b, atom_i)

                    py_only_ranked = sorted(
                        py_set - rs_set,
                        key=lambda j: _minimum_image_distance(coords_b, atom_i, int(j), box_vec),
                    )
                    rs_only_ranked = sorted(
                        rs_set - py_set,
                        key=lambda j: _minimum_image_distance(coords_b, atom_i, int(j), box_vec),
                    )

                    for pair_rank, atom_j in enumerate(py_only_ranked[:topk_pairs_per_atom], start=1):
                        pair_rows.append(
                            {
                                "target": target,
                                "sample_idx": int(sample_idx),
                                "batch_idx": int(b),
                                "outlier_mode": outlier_mode,
                                "atom_i": atom_i,
                                "atom_j": int(atom_j),
                                "pair_kind": "py_only",
                                "pair_rank": int(pair_rank),
                                "distance": _minimum_image_distance(coords_b, atom_i, int(atom_j), box_vec),
                                "atom_i_force_diff_l2": force_l2,
                                "atom_i_neighbor_jaccard": float(atom_jacc[b, atom_i].item()),
                            }
                        )
                    for pair_rank, atom_j in enumerate(rs_only_ranked[:topk_pairs_per_atom], start=1):
                        pair_rows.append(
                            {
                                "target": target,
                                "sample_idx": int(sample_idx),
                                "batch_idx": int(b),
                                "outlier_mode": outlier_mode,
                                "atom_i": atom_i,
                                "atom_j": int(atom_j),
                                "pair_kind": "rs_only",
                                "pair_rank": int(pair_rank),
                                "distance": _minimum_image_distance(coords_b, atom_i, int(atom_j), box_vec),
                                "atom_i_force_diff_l2": force_l2,
                                "atom_i_neighbor_jaccard": float(atom_jacc[b, atom_i].item()),
                            }
                        )

        row = {
            "target": target,
            "samples": samples,
            "noise": noise,
            "neighbor_jaccard_mean": float(sum(metrics_acc["neighbor_jaccard"]) / len(metrics_acc["neighbor_jaccard"])),
            "neighbor_count_py_mean": float(sum(metrics_acc["neighbor_count_py"]) / len(metrics_acc["neighbor_count_py"])),
            "neighbor_count_rs_mean": float(sum(metrics_acc["neighbor_count_rs"]) / len(metrics_acc["neighbor_count_rs"])),
            "rs_neighbor_saturated_samples": int(sum(metrics_acc["rs_neighbor_saturated"])),
            "rs_cell_overflow_samples": int(sum(metrics_acc["rs_cell_overflow"])),
            "rs_saturated_atoms_max": int(max(metrics_acc["rs_saturated_atoms"]) if metrics_acc["rs_saturated_atoms"] else 0),
            "rs_max_cell_count_max": int(max(metrics_acc["rs_max_cell_count"]) if metrics_acc["rs_max_cell_count"] else 0),
            "rs_builder_max_neighbors_max": int(
                max(metrics_acc["rs_builder_max_neighbors"]) if metrics_acc["rs_builder_max_neighbors"] else 0
            ),
            "rs_builder_max_atoms_per_cell_max": int(
                max(metrics_acc["rs_builder_max_atoms_per_cell"]) if metrics_acc["rs_builder_max_atoms_per_cell"] else 0
            ),
            "py_saturated_atoms_max": int(max(metrics_acc["py_saturated_atoms"]) if metrics_acc["py_saturated_atoms"] else 0),
            "py_max_required_neighbors_max": int(
                max(metrics_acc["py_max_required_neighbors"]) if metrics_acc["py_max_required_neighbors"] else 0
            ),
            "py_effective_max_neighbors_max": int(
                max(metrics_acc["py_effective_max_neighbors"]) if metrics_acc["py_effective_max_neighbors"] else 0
            ),
            # Backward-compatible aliases from end-to-end parity.
            "force_rmse_mean_raw": float(sum(metrics_acc["e2e_rmse_raw"]) / len(metrics_acc["e2e_rmse_raw"])),
            "force_rmse_mean_clipped200": float(sum(metrics_acc["e2e_rmse_clipped"]) / len(metrics_acc["e2e_rmse_clipped"])),
            "force_rel_rmse_mean_clipped200": float(
                sum(metrics_acc["e2e_rel_rmse_clipped"]) / len(metrics_acc["e2e_rel_rmse_clipped"])
            ),
            "force_max_abs_mean": float(sum(metrics_acc["e2e_max_abs"]) / len(metrics_acc["e2e_max_abs"])),
            "neighbor_settings": json.dumps(neighbor_settings),
            "outlier_mode": outlier_mode,
        }
        for key, _ in comparison_pairs:
            row[f"{key}_rmse_mean_raw"] = float(sum(metrics_acc[f"{key}_rmse_raw"]) / len(metrics_acc[f"{key}_rmse_raw"]))
            row[f"{key}_rmse_mean_clipped"] = float(
                sum(metrics_acc[f"{key}_rmse_clipped"]) / len(metrics_acc[f"{key}_rmse_clipped"])
            )
            row[f"{key}_rel_rmse_mean_clipped"] = float(
                sum(metrics_acc[f"{key}_rel_rmse_clipped"]) / len(metrics_acc[f"{key}_rel_rmse_clipped"])
            )
            row[f"{key}_max_abs_mean"] = float(sum(metrics_acc[f"{key}_max_abs"]) / len(metrics_acc[f"{key}_max_abs"]))
        target_rows.append(row)

    for path in (out_target_csv, out_sample_csv, out_atom_csv, out_pair_csv, out_json):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    atom_columns = [
        "target",
        "sample_idx",
        "batch_idx",
        "outlier_mode",
        "rank",
        "atom_idx",
        "force_diff_l2",
        "force_diff_abs_x",
        "force_diff_abs_y",
        "force_diff_abs_z",
        "force_ref_norm",
        "force_test_norm",
        "atom_neighbor_jaccard",
        "atom_neighbor_count_py",
        "atom_neighbor_count_rs",
    ]
    pair_columns = [
        "target",
        "sample_idx",
        "batch_idx",
        "outlier_mode",
        "atom_i",
        "atom_j",
        "pair_kind",
        "pair_rank",
        "distance",
        "atom_i_force_diff_l2",
        "atom_i_neighbor_jaccard",
    ]

    df_target = pd.DataFrame(target_rows)
    df_sample = pd.DataFrame(sample_rows)
    df_atom = _rows_to_df(atom_rows, atom_columns)
    df_pair = _rows_to_df(pair_rows, pair_columns)

    df_target.to_csv(out_target_csv, index=False)
    df_sample.to_csv(out_sample_csv, index=False)
    df_atom.to_csv(out_atom_csv, index=False)
    df_pair.to_csv(out_pair_csv, index=False)

    summary = {
        "targets": len(target_rows),
        "samples_per_target": int(samples),
        "outlier_mode": outlier_mode,
        "avg_neighbor_jaccard": _safe_mean(df_target, "neighbor_jaccard_mean"),
        "avg_neighbor_count_py": _safe_mean(df_target, "neighbor_count_py_mean"),
        "avg_neighbor_count_rs": _safe_mean(df_target, "neighbor_count_rs_mean"),
        "avg_force_rmse_raw": _safe_mean(df_target, "force_rmse_mean_raw"),
        "avg_force_rmse_clipped200": _safe_mean(df_target, "force_rmse_mean_clipped200"),
        "avg_force_rel_rmse_clipped200": _safe_mean(df_target, "force_rel_rmse_mean_clipped200"),
        "avg_force_max_abs": _safe_mean(df_target, "force_max_abs_mean"),
        "avg_kernel_shared_py_rmse_raw": _safe_mean(df_target, "kernel_shared_py_rmse_mean_raw"),
        "avg_kernel_shared_rs_rmse_raw": _safe_mean(df_target, "kernel_shared_rs_rmse_mean_raw"),
        "avg_nblist_effect_py_rmse_raw": _safe_mean(df_target, "nblist_effect_py_rmse_mean_raw"),
        "avg_nblist_effect_rs_rmse_raw": _safe_mean(df_target, "nblist_effect_rs_rmse_mean_raw"),
        "total_rs_neighbor_saturated_samples": int(df_target["rs_neighbor_saturated_samples"].sum())
        if "rs_neighbor_saturated_samples" in df_target.columns
        else 0,
        "total_rs_cell_overflow_samples": int(df_target["rs_cell_overflow_samples"].sum())
        if "rs_cell_overflow_samples" in df_target.columns
        else 0,
        "targets_with_py_saturation": int((df_target["py_saturated_atoms_max"] > 0).sum())
        if "py_saturated_atoms_max" in df_target.columns
        else 0,
        "total_atom_outliers": int(len(df_atom)),
        "total_pair_outliers": int(len(df_pair)),
    }
    top_atom_preview = sorted(atom_rows, key=lambda x: x["force_diff_l2"], reverse=True)[:50]
    payload = {
        "summary": summary,
        "rows": target_rows,
        "files": {
            "target_csv": out_target_csv,
            "sample_csv": out_sample_csv,
            "atom_csv": out_atom_csv,
            "pair_csv": out_pair_csv,
        },
        "top_atom_preview": top_atom_preview,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(summary, indent=2))
    return payload


def main():
    parser = argparse.ArgumentParser(description="Neighbor/force parity report for Rust GPU neighbor builder.")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--noise", type=float, default=0.12)
    parser.add_argument("--cutoff", type=float, default=12.0)
    parser.add_argument("--skin", type=float, default=2.0)
    parser.add_argument("--max-neighbors", type=int, default=100)
    parser.add_argument("--max-atoms-per-cell", type=int, default=64)
    parser.add_argument("--rebuild-stride", type=int, default=4)
    parser.add_argument("--clip", type=float, default=200.0)
    parser.add_argument("--topk-atoms", type=int, default=16)
    parser.add_argument("--topk-pairs-per-atom", type=int, default=4)
    parser.add_argument(
        "--outlier-mode",
        type=str,
        default="shared_rs_nblist",
        choices=("end_to_end", "shared_py_nblist", "shared_rs_nblist"),
        help="Force comparison used to rank atom-level outliers.",
    )
    parser.add_argument("--out-csv", type=str, default="runs/neighbor_force_parity.csv")
    parser.add_argument("--out-sample-csv", type=str, default="runs/neighbor_force_parity_samples.csv")
    parser.add_argument("--out-atom-csv", type=str, default="runs/neighbor_force_atom_outliers.csv")
    parser.add_argument("--out-pair-csv", type=str, default="runs/neighbor_force_pair_outliers.csv")
    parser.add_argument("--out-json", type=str, default="runs/neighbor_force_parity.json")
    args = parser.parse_args()

    settings = {
        "grid_spacing": float(args.cutoff),
        "cutoff": float(args.cutoff),
        "skin": float(args.skin),
        "max_neighbors": int(args.max_neighbors),
        "max_atoms_per_cell": int(args.max_atoms_per_cell),
        "rebuild_stride": int(args.rebuild_stride),
    }
    run_parity(
        targets=_parse_targets(args.targets),
        samples=args.samples,
        noise=args.noise,
        neighbor_settings=settings,
        out_target_csv=args.out_csv,
        out_sample_csv=args.out_sample_csv,
        out_atom_csv=args.out_atom_csv,
        out_pair_csv=args.out_pair_csv,
        out_json=args.out_json,
        clip=float(args.clip),
        topk_atoms=int(args.topk_atoms),
        topk_pairs_per_atom=int(args.topk_pairs_per_atom),
        outlier_mode=args.outlier_mode,
    )


if __name__ == "__main__":
    main()
