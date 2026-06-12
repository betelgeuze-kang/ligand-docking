#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List

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


def _sync_if_needed(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _time_call(device: torch.device, fn: Callable[[], Any], repeats: int) -> Dict[str, float]:
    samples_ms: List[float] = []
    for _ in range(max(repeats, 1)):
        _sync_if_needed(device)
        t0 = time.perf_counter()
        _ = fn()
        _sync_if_needed(device)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    return {
        "median_ms": float(statistics.median(samples_ms)),
        "mean_ms": float(sum(samples_ms) / max(len(samples_ms), 1)),
        "min_ms": float(min(samples_ms)),
        "max_ms": float(max(samples_ms)),
    }


def _prepare_batch(eval_json: str, device: torch.device) -> Dict[str, Any]:
    cfg = _read_json(eval_json)
    runtime = dict(cfg.get("runtime", {}) or {})
    targets = list(cfg.get("targets", []) or [])
    if not targets:
        raise ValueError(f"no targets in {eval_json}")
    first = dict(targets[0])
    coords0 = load_target_coords(first, device=device)
    top = build_target_top(first, device=device)
    seq_features = load_target_sequence_features(first)
    policy_path = str(runtime.get("idp_branch_force_policy_json", ""))
    force_policy = _read_json(policy_path) if policy_path and Path(policy_path).exists() else {}

    params_list: List[Dict[str, Any]] = []
    for t in targets:
        merged = dict(runtime)
        merged.update(t)
        branch_profile = normalize_branch_profile(infer_branch_profile(merged))
        merged["sequence_features"] = seq_features
        merged["idp_branch_profile"] = branch_profile
        merged["idp_branch_force_policy"] = force_policy
        merged["target_name"] = str(t.get("name", ""))
        params_list.append(build_sim_params(enabled=True, params=merged))

    batch_size = len(params_list)
    c = coords0.unsqueeze(0).expand(batch_size, -1, -1).clone()
    engine = IDPNeighborEngine(coords0=coords0, top=top, k=int(runtime.get("knn_k", 12) or 12), params=runtime)
    nb_data = engine.get_neighbor_data(c)
    mod = IDPLogic(device).to(device)
    return {
        "config_json": eval_json,
        "split_groups": sorted({str(t.get("split_group", "")) for t in targets}),
        "target_count": batch_size,
        "coords": c,
        "top": top,
        "nb_data": nb_data,
        "sim_params": params_list,
        "mod": mod,
    }


def benchmark_eval(eval_json: str, device: torch.device, warmup: int, repeats: int) -> Dict[str, Any]:
    batch = _prepare_batch(eval_json, device)
    c = batch["coords"]
    top = batch["top"]
    nb_data = batch["nb_data"]
    sim_params = batch["sim_params"]
    mod: IDPLogic = batch["mod"]

    with torch.inference_mode():
        ctx = mod._prepare_step_ctx(c, top, nb_data, sim_params)

        fns = {
            "hbond": lambda: mod._pairwise_idp_hbond_force(c, top, nb_data, sim_params, ctx=ctx),
            "sticker": lambda: mod._pairwise_sticker_force(c, top, nb_data, sim_params, ctx=ctx),
            "bridge": lambda: mod._pairwise_llps_bridge_force(c, top, nb_data, sim_params, ctx=ctx),
            "helix": lambda: mod._transient_helix_force(c, top, sim_params, ctx=ctx),
            "anti_collapse": lambda: mod._anti_collapse_force(c, top, nb_data, sim_params, ctx=ctx),
            "forward_total": lambda: mod(c, top, nb_data, None, sim_params),
        }
        for _ in range(max(warmup, 0)):
            for fn in fns.values():
                fn()
        _sync_if_needed(device)

        timings = {name: _time_call(device, fn, repeats) for name, fn in fns.items()}

    out = {
        "config_json": batch["config_json"],
        "split_groups": batch["split_groups"],
        "target_count": batch["target_count"],
        "batch_residue_count": int(c.shape[1]),
        "warmup": int(warmup),
        "repeats": int(repeats),
        "timings_ms": timings,
    }
    total = timings["forward_total"]["median_ms"]
    for name, item in timings.items():
        item["median_fraction_of_total"] = float(item["median_ms"] / total) if total > 0.0 else 0.0
    return out


def _to_markdown(report: Dict[str, Any]) -> str:
    lines = ["# IDP Force Component Benchmark", ""]
    for item in report["profiles"]:
        lines.append(f"## `{item['config_json']}`")
        lines.append("")
        lines.append(f"- split_groups: `{item['split_groups']}`")
        lines.append(f"- target_count: `{item['target_count']}`")
        lines.append(f"- residue_count: `{item['batch_residue_count']}`")
        for key in ("forward_total", "helix", "anti_collapse", "hbond", "sticker", "bridge"):
            t = item["timings_ms"][key]
            lines.append(
                f"- {key}: median `{t['median_ms']:.4f} ms`, frac `{t['median_fraction_of_total']:.4f}`"
            )
        lines.append("")
    lines.append("## Overall Median Fractions")
    lines.append("")
    for key, value in report["overall_median_fraction"].items():
        lines.append(f"- {key}: `{value:.4f}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark IDP force components on representative eval batches.")
    p.add_argument("--eval-json", action="append", required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--warmup", type=int, default=8)
    p.add_argument("--repeats", type=int, default=40)
    p.add_argument("--fastpath-mode", default="none", choices=["none", "hbond", "hbond_sticker", "all"])
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    args = p.parse_args()

    device = torch.device(str(args.device))
    os.environ["IDP_PAIRWISE_FASTPATH_MODE"] = str(args.fastpath_mode)
    profiles = [benchmark_eval(path, device, warmup=int(args.warmup), repeats=int(args.repeats)) for path in args.eval_json]
    accum: Dict[str, List[float]] = defaultdict(list)
    for item in profiles:
        for key, t in item["timings_ms"].items():
            if key == "forward_total":
                continue
            accum[key].append(float(t["median_fraction_of_total"]))
    report = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fastpath_mode": str(args.fastpath_mode),
        "profiles": profiles,
        "overall_median_fraction": {key: float(statistics.median(vals)) for key, vals in accum.items()},
    }
    Path(args.out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(_to_markdown(report), encoding="utf-8")
    print(args.out_json)
    print(args.out_md)


if __name__ == "__main__":
    main()
