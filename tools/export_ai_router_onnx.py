#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Sequence

import torch

from core.definitions import Config, ResearchConstants
from theory.strategy import StrategicOrchestrator, _AIRouterTensorWrapper


def _load_checkpoint_if_any(model: torch.nn.Module, checkpoint_path: str, strict: bool) -> Dict[str, Any]:
    path = str(checkpoint_path or "").strip()
    if not path:
        return {"loaded": False, "path": None, "state_source": None}
    payload = torch.load(path, map_location="cpu")
    state = payload
    source = "root"
    if isinstance(payload, dict):
        for key in ("state_dict", "model_state_dict", "airouter_state_dict"):
            if key in payload and isinstance(payload[key], dict):
                state = payload[key]
                source = key
                break
    if not isinstance(state, dict):
        raise TypeError(f"checkpoint at {path} does not contain a state_dict-like payload")
    missing, unexpected = model.load_state_dict(state, strict=bool(strict))
    return {
        "loaded": True,
        "path": os.path.abspath(path),
        "state_source": source,
        "missing_keys_count": int(len(missing)),
        "unexpected_keys_count": int(len(unexpected)),
    }


def export_router_onnx(args: argparse.Namespace) -> Dict[str, Any]:
    target = str(args.target).strip()
    if target not in ResearchConstants.CHALLENGES:
        raise KeyError(f"unknown target: {target}")
    n_res = int(ResearchConstants.CHALLENGES[target]["n_res"])

    orch = StrategicOrchestrator(Config.DEVICE).to(Config.DEVICE)
    ckpt_info = _load_checkpoint_if_any(
        orch,
        checkpoint_path=str(getattr(args, "ai_router_checkpoint", "")).strip(),
        strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
    )
    orch.eval()

    router = orch.ai_router
    router.set_runtime_mode("eager")
    router.set_disable_exploration(True)
    wrapper = _AIRouterTensorWrapper(router).to(device="cpu").eval()

    batch = int(max(getattr(args, "batch", 1), 1))
    atoms = int(max(getattr(args, "atoms", n_res), 1))
    topo_dim = int(getattr(router, "topo_feature_dim", 64))
    sim_dim = int(getattr(router, "sim_param_dim", 19))

    c = torch.randn(batch, atoms, 3, dtype=torch.float32, device="cpu")
    topo = torch.randn(batch, atoms, topo_dim, dtype=torch.float32, device="cpu")
    sim = torch.randn(batch, sim_dim, dtype=torch.float32, device="cpu")

    out_path = os.path.abspath(str(args.out_onnx))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with torch.inference_mode():
        torch.onnx.export(
            wrapper,
            (c, topo, sim),
            out_path,
            opset_version=int(getattr(args, "opset", 17)),
            do_constant_folding=True,
            input_names=["c", "topo_features_batch", "sim_param_tensor"],
            output_names=["weights", "active_mask"],
            dynamic_axes={
                "c": {0: "batch", 1: "atoms"},
                "topo_features_batch": {0: "batch", 1: "atoms"},
                "sim_param_tensor": {0: "batch"},
                "weights": {0: "batch"},
                "active_mask": {0: "batch"},
            },
        )

    out_json = os.path.abspath(str(args.out_json))
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    payload = {
        "target": target,
        "batch": batch,
        "atoms": atoms,
        "topo_dim": topo_dim,
        "sim_dim": sim_dim,
        "out_onnx": out_path,
        "checkpoint": ckpt_info,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export AIRouter tensor wrapper to ONNX.")
    p.add_argument("--target", type=str, default="Chignolin")
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--atoms", type=int, default=0, help="0 means target n_res")
    p.add_argument("--opset", type=int, default=17)
    p.add_argument("--ai-router-checkpoint", type=str, default="")
    p.add_argument(
        "--ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--out-onnx",
        type=str,
        default="runtime/cache/ai_router/airouter_router_export.onnx",
    )
    p.add_argument(
        "--out-json",
        type=str,
        default="runs/airouter_router_onnx_export.json",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if int(args.atoms) <= 0:
        args.atoms = int(ResearchConstants.CHALLENGES[str(args.target)]["n_res"])
    out = export_router_onnx(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
