#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import torch

from theory.branches.idp_logic import IDPLogic
from tools.idp_3bead_common import (
    IDPNeighborEngine,
    build_sim_params,
    build_target_top,
    infer_branch_profile,
    load_target_coords,
    load_target_sequence_features,
    normalize_branch_profile,
)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _prepare_group(config_json: str, target_name: str, device: torch.device):
    cfg = _read_json(config_json)
    runtime = dict(cfg.get("runtime", {}) or {})
    runtime["device"] = str(device)
    targets = list(cfg.get("targets", []) or [])
    taxonomy_targets = {}
    taxonomy_path = str(runtime.get("idp_branch_taxonomy_json", "")).strip()
    if taxonomy_path:
        taxonomy_targets = dict(_read_json(taxonomy_path).get("targets", {}))
    force_policy = {}
    force_policy_path = str(runtime.get("idp_branch_force_policy_json", "")).strip()
    if force_policy_path:
        force_policy = _read_json(force_policy_path)

    rows = [dict(t) for t in targets if str(t.get("name", "")) == str(target_name)]
    if not rows:
        raise ValueError(f"target not found: {target_name}")

    first = dict(runtime)
    first.update(rows[0])
    branch_profile = normalize_branch_profile(
        first.get("branch_profile") or taxonomy_targets.get(str(first.get("name", ""))) or infer_branch_profile(first)
    )
    tmp_cfg = dict(first)
    tmp_cfg["branch_profile"] = dict(branch_profile)
    coords0 = load_target_coords(tmp_cfg, device=device)
    box_size = float(
        tmp_cfg.get(
            "box_size",
            max(96.0, float((coords0.max(dim=0).values - coords0.min(dim=0).values).max().item()) + 32.0),
        )
        or 160.0
    )
    tmp_cfg["box_size"] = box_size
    seq_features = load_target_sequence_features(tmp_cfg)
    top = build_target_top(tmp_cfg, device=device)
    merged_rows: List[Dict[str, Any]] = []
    for row in rows:
        merged = dict(runtime)
        merged.update(row)
        merged["sequence_features"] = dict(seq_features)
        merged["branch_profile"] = dict(branch_profile)
        merged["idp_branch_force_policy"] = force_policy
        merged.setdefault("box_size", float(top.box_size[0].item()) if torch.is_tensor(top.box_size) else box_size)
        merged_rows.append(merged)

    c = coords0.unsqueeze(0).expand(len(merged_rows), -1, -1).clone()
    engine = IDPNeighborEngine(coords0=coords0, top=top, k=int(merged_rows[0].get("knn_k", 12)), params=merged_rows[0])
    engine.reset()
    nb_data = engine.get_neighbor_data(c)
    sim_params = [build_sim_params(enabled=True, params=params) for params in merged_rows]
    mod = IDPLogic(device).to(device)
    ctx = mod._prepare_step_ctx(c, top, nb_data, sim_params)
    return mod, c, top, nb_data, sim_params, ctx


def _bench_cuda(fn, warmup: int = 20, iters: int = 200) -> float:
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / float(iters)


def build_report(config_json: str, target_names: List[str], device: str, iters: int) -> Dict[str, Any]:
    dev = torch.device(device)
    results = []
    for target_name in target_names:
        mod, c, top, nb_data, sim_params, ctx = _prepare_group(config_json, target_name, dev)
        static_ctx = mod._prepare_hbond_pairwise_static_ctx(c, nb_data, ctx)
        _nb_idx, nb_dist, _nb_mask = nb_data[:3]
        valid3 = static_ctx["valid3"]

        def run_static():
            mod._prepare_hbond_pairwise_static_ctx(c, nb_data, ctx)

        def run_local_density():
            ((nb_dist < 8.0) & valid3).float().sum(dim=-1)

        def run_rust_ctx():
            mod._prepare_hbond_pairwise_rust_ctx(c, nb_data, ctx)

        t_static = _bench_cuda(run_static, iters=iters)
        t_local_density = _bench_cuda(run_local_density, iters=iters)
        t_rust_ctx = _bench_cuda(run_rust_ctx, iters=iters)
        results.append(
            {
                "target_name": str(target_name),
                "batch_size": int(c.shape[0]),
                "n_atoms": int(c.shape[1]),
                "max_neighbors": int(nb_data[0].shape[-1]),
                "static_ctx_ms": float(t_static * 1000.0),
                "local_density_ms": float(t_local_density * 1000.0),
                "rust_ctx_total_ms": float(t_rust_ctx * 1000.0),
                "local_density_frac_of_rust_ctx": float((t_local_density / t_rust_ctx) if t_rust_ctx > 0 else 0.0),
            }
        )
    med = {}
    if results:
        for key in ("static_ctx_ms", "local_density_ms", "rust_ctx_total_ms", "local_density_frac_of_rust_ctx"):
            vals = sorted(float(item[key]) for item in results)
            med[key] = float(vals[len(vals) // 2])
    return {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(config_json),
        "device": str(device),
        "iters": int(iters),
        "targets": results,
        "median": med,
    }


def _to_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# IDP HBond Prepare Benchmark",
        "",
        f"- generated_at_local: `{report['generated_at_local']}`",
        f"- config_json: `{report['config_json']}`",
        f"- device: `{report['device']}`",
        f"- iters: `{report['iters']}`",
        "",
        "## Targets",
        "",
    ]
    for item in report.get("targets", []):
        lines.extend(
            [
                f"- `{item['target_name']}`",
                f"  - static_ctx_ms: `{item['static_ctx_ms']:.4f}`",
                f"  - local_density_ms: `{item['local_density_ms']:.4f}`",
                f"  - rust_ctx_total_ms: `{item['rust_ctx_total_ms']:.4f}`",
                f"  - local_density_frac_of_rust_ctx: `{item['local_density_frac_of_rust_ctx']:.4f}`",
            ]
        )
    med = dict(report.get("median", {}) or {})
    if med:
        lines.extend(
            [
                "",
                "## Median",
                "",
                f"- static_ctx_ms: `{med.get('static_ctx_ms', 0.0):.4f}`",
                f"- local_density_ms: `{med.get('local_density_ms', 0.0):.4f}`",
                f"- rust_ctx_total_ms: `{med.get('rust_ctx_total_ms', 0.0):.4f}`",
                f"- local_density_frac_of_rust_ctx: `{med.get('local_density_frac_of_rust_ctx', 0.0):.4f}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark Python-side hbond prepare components for IDP Rust/HIP path.")
    p.add_argument("--config-json", default="config/idp_3bead_benchmark_v7.json")
    p.add_argument("--target", action="append", default=[])
    p.add_argument("--device", default="cuda")
    p.add_argument("--iters", type=int, default=200)
    p.add_argument("--out-json", default=f"runs/idp_hbond_prepare_bench_{dt.date.today().isoformat()}.json")
    p.add_argument("--out-md", default=f"runs/idp_hbond_prepare_bench_{dt.date.today().isoformat()}.md")
    args = p.parse_args()

    targets = list(args.target) or ["alpha_synuclein_full", "fus_lcd", "hnrnpa1_lcd"]
    report = build_report(str(args.config_json), targets, str(args.device), int(args.iters))
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(_to_markdown(report), encoding="utf-8")
    print(args.out_json)
    print(args.out_md)
