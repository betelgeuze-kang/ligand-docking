#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
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


def _parse_capture_steps(raw: str, steps: int) -> List[int]:
    vals = []
    for tok in str(raw or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            step = int(tok)
        except Exception:
            continue
        if 1 <= step <= int(steps):
            vals.append(step)
    vals = sorted(set(vals))
    return vals or [max(1, int(steps) // 4), max(1, int(steps) // 2), int(steps)]


def _target_group(runtime: Dict[str, Any], targets: List[Dict[str, Any]], taxonomy_targets: Dict[str, Any], force_policy: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
    rows = [dict(t) for t in targets if str(t.get("name", "")) == str(name)]
    if not rows:
        raise ValueError(f"target not found in config: {name}")
    merged_rows: List[Dict[str, Any]] = []
    first = dict(runtime)
    first.update(rows[0])
    branch_profile = normalize_branch_profile(first.get("branch_profile") or taxonomy_targets.get(str(first.get("name", ""))) or infer_branch_profile(first))
    tmp_cfg = dict(first)
    tmp_cfg["branch_profile"] = dict(branch_profile)
    coords0 = load_target_coords(tmp_cfg, device=torch.device(str(runtime.get("device", "cuda"))))
    box_size = float(tmp_cfg.get("box_size", max(96.0, float((coords0.max(dim=0).values - coords0.min(dim=0).values).max().item()) + 32.0)) or 160.0)
    tmp_cfg["box_size"] = box_size
    seq_features = load_target_sequence_features(tmp_cfg)
    top = build_target_top(tmp_cfg, device=coords0.device)
    for row in rows:
        merged = dict(runtime)
        merged.update(row)
        merged["sequence_features"] = dict(seq_features)
        merged["branch_profile"] = dict(branch_profile)
        merged["idp_branch_force_policy"] = force_policy
        merged.setdefault("box_size", float(top.box_size[0].item()) if torch.is_tensor(top.box_size) else box_size)
        merged_rows.append(merged)
    return [{"merged_rows": merged_rows, "coords0": coords0, "top": top, "branch_profile": branch_profile, "seq_features": seq_features}]


def build_packets(config_json: str, target_names: List[str], steps: int, capture_steps: List[int], device: str) -> Dict[str, Any]:
    cfg = _read_json(config_json)
    runtime = dict(cfg.get("runtime", {}) or {})
    runtime["device"] = str(device)
    targets = list(cfg.get("targets", []) or [])
    taxonomy_targets = dict(_read_json(str(runtime["idp_branch_taxonomy_json"])).get("targets", {})) if str(runtime.get("idp_branch_taxonomy_json", "")).strip() else {}
    force_policy = _read_json(str(runtime["idp_branch_force_policy_json"])) if str(runtime.get("idp_branch_force_policy_json", "")).strip() else {}

    packets: List[Dict[str, Any]] = []
    summary_targets: List[Dict[str, Any]] = []
    for target_name in target_names:
        group = _target_group(runtime, targets, taxonomy_targets, force_policy, target_name)[0]
        merged_rows = list(group["merged_rows"])
        coords0 = group["coords0"]
        top = group["top"]
        dev = coords0.device
        mod = IDPLogic(dev).to(dev)
        engine = IDPNeighborEngine(coords0=coords0, top=top, k=int(merged_rows[0].get("knn_k", 12)), params=merged_rows[0])
        engine.reset()
        batch_size = len(merged_rows)
        c = coords0.unsqueeze(0).expand(batch_size, -1, -1).clone()
        gen = torch.Generator(device="cpu")
        gen.manual_seed(int(merged_rows[0].get("seed", 23) or 23))
        base_noise = torch.randn((max(int(steps), 1),) + tuple(coords0.shape), generator=gen, dtype=torch.float32) * float(merged_rows[0].get("thermal_noise", 0.02) or 0.02)
        noise_bank = base_noise.unsqueeze(1).expand(-1, batch_size, -1, -1).contiguous()
        sim_params_list = [build_sim_params(enabled=True, params=params) for params in merged_rows]
        target_capture_count = 0
        for step_idx in range(int(steps)):
            nb_data = engine.get_neighbor_data(c)
            if (step_idx + 1) in capture_steps:
                packet = mod.build_virtual_hbond_parity_packet(c, top=top, nb_data=nb_data, sim_params=sim_params_list)
                packet["meta"].update(
                    {
                        "target_name": str(target_name),
                        "capture_step": int(step_idx + 1),
                        "condition_groups": [str(item.get("condition_group", "")) for item in merged_rows],
                        "split_group": str(merged_rows[0].get("split_group", target_name)),
                    }
                )
                packets.append(packet)
                target_capture_count += 1
            f, _info = mod(c, top=top, nb_data=nb_data, pe=None, sim_params=sim_params_list)
            noise = noise_bank[step_idx].to(device=dev)
            c = c + float(merged_rows[0].get("dt", 0.045) or 0.045) * f + noise
        summary_targets.append(
            {
                "target_name": str(target_name),
                "condition_count": int(batch_size),
                "captures": int(target_capture_count),
                "n_res": int(coords0.shape[0]),
            }
        )
    return {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(config_json),
        "device": str(device),
        "steps": int(steps),
        "capture_steps": [int(x) for x in capture_steps],
        "target_names": [str(x) for x in target_names],
        "targets": summary_targets,
        "packets": packets,
    }


def _to_markdown(payload: Dict[str, Any], packet_path: str) -> str:
    lines = [
        "# IDP Virtual HBond Parity Packet",
        "",
        f"- device: `{payload['device']}`",
        f"- config_json: `{payload['config_json']}`",
        f"- capture_steps: `{payload['capture_steps']}`",
        f"- packet_count: `{len(payload.get('packets', []))}`",
        f"- packet_path: `{packet_path}`",
        "",
        "## Targets",
        "",
    ]
    for item in payload.get("targets", []):
        lines.append(f"- `{item['target_name']}`: n_res `{item['n_res']}`, conditions `{item['condition_count']}`, captures `{item['captures']}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Build representative parity packets for future IDP virtual_hbond backend replacement.")
    p.add_argument("--config-json", required=True)
    p.add_argument("--target", action="append", default=[])
    p.add_argument("--steps", type=int, default=48)
    p.add_argument("--capture-steps", type=str, default="8,24,40")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--out-prefix", type=str, default=f"runs/idp_virtual_hbond_parity_rep3_{dt.date.today().isoformat()}")
    args = p.parse_args()

    targets = list(args.target) or ["alpha_synuclein_full", "fus_lcd", "hnrnpa1_lcd"]
    capture_steps = _parse_capture_steps(str(args.capture_steps), int(args.steps))
    payload = build_packets(
        config_json=str(args.config_json),
        target_names=targets,
        steps=int(args.steps),
        capture_steps=capture_steps,
        device=str(args.device),
    )
    out_prefix = str(args.out_prefix)
    pt_path = out_prefix + ".pt"
    json_path = out_prefix + ".json"
    md_path = out_prefix + ".md"
    Path(pt_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, pt_path)
    summary = {k: v for k, v in payload.items() if k != "packets"}
    summary["packet_path"] = pt_path
    Path(json_path).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(md_path).write_text(_to_markdown(payload, pt_path), encoding="utf-8")
    print(pt_path)
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
